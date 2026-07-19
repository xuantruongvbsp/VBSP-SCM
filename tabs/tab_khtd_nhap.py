"""Nhập dữ liệu cho tab Kế hoạch Tín dụng (Chi nhánh + theo Xã/PGD)."""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import json
import re
import unicodedata
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

import db
from auth import get_permissions, normalize_role
from pdf_service import xuat_pdf_bang
from state_manager import SCMStateManager
from config import (
    CHUONG_TRINH_KHTD,
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_PGD,
    PGD_XA_MAP,
    CACHE_GQVL,
    CACHE_HSTD,
    HSTD_DS_CHO_VAY_NAM_ALIASES,
    HSTD_THU_NO_NAM_ALIASES,
)
from data.core import ts_file
from utils import fmt, xuat_excel, ten_file_xuat, vn

from tabs.tab_khtd import (
    DATA_DIR,
    KHTD_CN_NHOM_MA_CT,
    KV_KEY_CN,
    KV_KEY_XA,
    MA_KEYS_CO_KHTD,
    _chon_ds_ct,
    _doc_kv,
    _dong_bo_gqvl_tong_keys,
    _fvn,
    _fmt_vn,
    _iter_khtd_cn_group_rows,
    _khtd_cn_hdr_cell,
    _luu_kv,
    _quet_ct_co_du_no,
    _ten_ct_base,
    _tinh_thuc_hien_khtd_cn,
    _tinh_thuc_hien_theo_ct,
)
# NOTE: _hien_thi_bang_cn_readonly import lazy (tránh circular import)
# tab_khtd_xuat → tab_khtd → tab_khtd_nhap → tab_khtd_xuat (vòng tròn)
from services.khtd_nhap_service import (


    clean_sheet_name as _clean_sheet_name,
    format_kich_thuoc as _format_kich_thuoc,
    doc_meta_qd as _doc_meta_qd,
    luu_meta_qd as _svc_luu_meta_qd,
    luu_file_qd as _svc_luu_file_qd,
    tao_df_mau_khtd_cn as _tao_df_mau_khtd_cn,
    doc_excel_khtd_cn_upload as _svc_doc_excel_khtd_cn_upload,
    doc_excel_khtd_xa_upload as _svc_doc_excel_khtd_xa_upload,
    luu_pdf_khtd_xa as _svc_luu_pdf_khtd_xa,
)


def _dong_bo_nsvsmt_dp_keys(data: dict[str, float]) -> dict[str, float]:
    """Giữ tương thích dữ liệu cũ nhưng ưu tiên key tổng `6_DP` làm chuẩn hiện tại."""
    out = dict(data or {})
    base = float(out.get("6_DP", 0.0) or 0.0)
    co_split = "6_DP_TINH" in out or "6_DP_XA" in out
    if base > 0:
        out["6_DP_TINH"] = base
        out["6_DP_XA"] = 0.0
        return out
    if co_split:
        out["6_DP"] = float(out.get("6_DP_TINH", 0.0) or 0.0) + float(out.get("6_DP_XA", 0.0) or 0.0)
    return out


def _fmt_trieu_input(value: float | int | None) -> str:
    """Format số triệu đồng theo kiểu 1.234.567 để dễ rà soát trước khi lưu."""
    try:
        num = int(round(float(value or 0.0)))
    except Exception:
        return ""
    if num <= 0:
        return ""
    return f"{num:,}".replace(",", ".")


def _parse_trieu_input(raw: object, field_label: str = "") -> float:
    """Parse chuỗi nhập liệu triệu đồng; chấp nhận cả dạng 1250000 và 1.250.000."""
    text = str(raw or "").strip()
    if not text:
        return 0.0
    normalized = text.replace(" ", "").replace(".", "").replace(",", "")
    if not normalized.isdigit():
        ten_truong = field_label or "Giá trị nhập"
        raise ValueError(
            f"{ten_truong}: chỉ nhập số nguyên triệu đồng; có thể gõ `1250000` hoặc `1.250.000`."
        )
    return float(int(normalized))


def _doc_trieu_input_safe(widget_key: str, fallback: float = 0.0) -> float:
    """Đọc nhanh giá trị hiện có trong session_state mà không làm vỡ UI nếu user gõ lỗi."""
    try:
        return _parse_trieu_input(st.session_state.get(widget_key, ""), widget_key)
    except ValueError:
        return float(fallback or 0.0)


def _apply_pending_trieu_inputs(state_key: str) -> None:
    """Áp lại giá trị đã parse vào text_input ở lần rerun kế tiếp để hiện dấu phân cách."""
    pending = st.session_state.pop(state_key, None)
    if not isinstance(pending, dict):
        return
    for widget_key, value_trieu in pending.items():
        st.session_state[widget_key] = _fmt_trieu_input(value_trieu)


def _render_trieu_text_input(
    container,
    *,
    label: str,
    widget_key: str,
    value_trieu: float,
    help_text: str | None = None,
) -> float:
    """Ô nhập KH dạng text để có thể chuẩn hóa dấu phân cách sau khi xem trước/lưu."""
    if widget_key not in st.session_state:
        st.session_state[widget_key] = _fmt_trieu_input(value_trieu)
    container.text_input(
        label,
        key=widget_key,
        help=help_text,
        label_visibility="collapsed",
        placeholder="0",
    )
    return _doc_trieu_input_safe(widget_key, value_trieu)


def _editor_num(value: object) -> float:
    """Chuẩn hóa số từ data_editor về float an toàn."""
    try:
        if value is None or pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _editor_con_lai(kh_trieu: float | None, th_trieu: float | None, applicable: bool) -> float | None:
    """Tính cột Còn phải TH; để trống nếu dòng không áp dụng hoặc KH = 0."""
    if not applicable:
        return None
    kh_val = _editor_num(kh_trieu)
    if kh_val <= 0:
        return None
    return kh_val - _editor_num(th_trieu)


def _fmt_khtd_editor_cell(value: object) -> str:
    """Định dạng ô chỉ đọc trong data_editor, tránh hiện `None`/format literal."""
    if value is None or pd.isna(value):
        return ""
    return _fmt_vn(float(value), 0)


def _series_editor_int(values: list[object]) -> pd.Series:
    """Tạo series số nguyên nullable cho 2 cột KH editable."""
    out: list[object] = []
    for value in values:
        if value is None or pd.isna(value):
            out.append(pd.NA)
            continue
        out.append(int(round(float(value))))
    return pd.Series(pd.array(out, dtype="Int64"))


def _tao_bang_nhap_khtd_cn(
    kh_cn: dict[str, float],
    th_cn: dict[str, float],
    th_gqvl: dict[str, float],
    ten_map_q: dict[str, str],
    draft: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Dựng bảng nhập KHTD CN dạng data_editor có lưới rõ ràng."""
    draft = _dong_bo_gqvl_tong_keys(draft or {})
    kh_cn = _dong_bo_gqvl_tong_keys(kh_cn)
    th_cn = _dong_bo_gqvl_tong_keys(th_cn)
    rows: list[dict[str, object]] = []

    def _kh_trieu(key: str | None) -> float | None:
        if not key:
            return None
        if key in draft:
            return _editor_num(draft.get(key))
        return float(kh_cn.get(key, 0.0) or 0.0) / 1_000_000

    def _them_dong(
        nhom: str,
        ten_ct: str,
        key_tw: str | None = None,
        key_dp: str | None = None,
        th_tw_vnd: float = 0.0,
        th_dp_vnd: float = 0.0,
    ) -> None:
        kh_tw = _kh_trieu(key_tw)
        kh_dp = _kh_trieu(key_dp)
        th_tw = float(th_tw_vnd or 0.0) / 1_000_000 if key_tw else None
        th_dp = float(th_dp_vnd or 0.0) / 1_000_000 if key_dp else None
        th_tong = None
        if key_tw or key_dp:
            th_tong = _editor_num(th_tw) + _editor_num(th_dp)
        kh_tong = _editor_num(kh_tw) + _editor_num(kh_dp)
        rows.append(
            {
                "_key_tw": key_tw or "",
                "_key_dp": key_dp or "",
                "Nhóm": nhom,
                "Chương trình": ten_ct,
                "KH TW": kh_tw if key_tw else None,
                "TH TW": th_tw,
                "Còn TH TW": _editor_con_lai(kh_tw, th_tw, bool(key_tw)),
                "KH ĐP": kh_dp if key_dp else None,
                "TH ĐP": th_dp,
                "Còn TH ĐP": _editor_con_lai(kh_dp, th_dp, bool(key_dp)),
                "TH tổng": th_tong,
                "Còn TH tổng": _editor_con_lai(kh_tong, th_tong, bool(key_tw or key_dp)),
            }
        )

    for tieu_de_nhom, ds_rows in _iter_khtd_cn_group_rows(ten_map_q):
        for row in ds_rows:
            key_tw = row.get("key_tw")
            key_dp = row.get("key_dp")
            _them_dong(
                tieu_de_nhom,
                str(row.get("label", "") or ""),
                key_tw=str(key_tw) if key_tw else None,
                key_dp=str(key_dp) if key_dp else None,
                th_tw_vnd=float((th_gqvl or {}).get(str(key_tw), (th_cn or {}).get(str(key_tw), 0.0)) or 0.0),
                th_dp_vnd=float((th_gqvl or {}).get(str(key_dp), (th_cn or {}).get(str(key_dp), 0.0)) or 0.0),
            )

    return pd.DataFrame(rows)


def _trich_patch_khtd_cn_tu_bang(
    df_values: pd.DataFrame,
    df_meta: pd.DataFrame,
) -> dict[str, float]:
    """Trích draft kế hoạch (triệu đồng) từ data_editor theo key kỹ thuật."""
    out: dict[str, float] = {}
    loi_parse: list[str] = []
    for idx, meta in df_meta.reset_index(drop=True).iterrows():
        key_tw = str(meta.get("_key_tw", "") or "").strip()
        key_dp = str(meta.get("_key_dp", "") or "").strip()
        if key_tw:
            try:
                out[key_tw] = _parse_trieu_input(df_values.at[idx, "KH TW"], "KH TW")
            except ValueError:
                out[key_tw] = _editor_num(meta.get("KH TW"))
                loi_parse.append(str(meta.get("Chương trình", "KH TW")))
        if key_dp:
            try:
                out[key_dp] = _parse_trieu_input(df_values.at[idx, "KH ĐP"], "KH ĐP")
            except ValueError:
                out[key_dp] = _editor_num(meta.get("KH ĐP"))
                loi_parse.append(str(meta.get("Chương trình", "KH ĐP")))
    if loi_parse:
        st.warning("⚠️ Có ô kế hoạch nhập chưa đúng định dạng số nguyên triệu đồng; hệ thống đang giữ tạm giá trị cũ.")
    return out


def _tao_view_editor_khtd_cn(df_editor_meta: pd.DataFrame) -> pd.DataFrame:
    """Tạo DataFrame hiển thị cho data_editor: cột tính toán là text, cột KH là số nguyên editable."""
    df_view = df_editor_meta[
        [
            "Chương trình",
            "KH TW",
            "TH TW",
            "Còn TH TW",
            "KH ĐP",
            "TH ĐP",
            "Còn TH ĐP",
            "TH tổng",
            "Còn TH tổng",
        ]
    ].copy()
    for col in ["KH TW", "KH ĐP"]:
        df_view[col] = df_view[col].map(_fmt_trieu_input)
    for col in ["TH TW", "Còn TH TW", "TH ĐP", "Còn TH ĐP", "TH tổng", "Còn TH tổng"]:
        df_view[col] = df_view[col].map(_fmt_khtd_editor_cell)
    return df_view


@st.cache_data(show_spinner=False)
def _tinh_th_cn_cached(
    _df_full: "pd.DataFrame | None",
    _df_gqvl: "pd.DataFrame | None",
    hstd_mtime: float = 0.0,
    gqvl_mtime: float = 0.0,
) -> tuple[dict[str, float], dict[str, float]]:
    """Tính TH KHTD Chi nhánh theo mtime parquet để tránh quét lại mỗi rerun."""
    _ = (hstd_mtime, gqvl_mtime)
    if _df_full is None:
        return {}, {}
    return _tinh_thuc_hien_khtd_cn(_df_full, _df_gqvl)


@st.cache_data(show_spinner=False)
def _du_lieu_khtd_pgd_cached(
    _df_full: "pd.DataFrame | None",
    pgd_chon: str,
    hstd_mtime: float = 0.0,
    rules_ver: int = 0,
) -> tuple[dict[str, float], dict[str, str]]:
    """Lọc dữ liệu theo PGD rồi tính TH/ten_map một lần theo mtime HSTD."""
    _ = (hstd_mtime, rules_ver)
    if _df_full is None or _df_full.empty or COT_TEN_PGD not in _df_full.columns:
        return {}, {}

    pgd_norm = str(pgd_chon).strip()
    s_pgd = _df_full[COT_TEN_PGD].astype(str).str.strip()
    df_loc = _df_full[s_pgd == pgd_norm]
    th_xa = _tinh_thuc_hien_theo_ct(df_loc) if not df_loc.empty else {}
    _, ten_map_q = _quet_ct_co_du_no(df_loc)
    return th_xa, ten_map_q


def _norm_xa_text(text: object) -> str:
    """Chuẩn hóa tên xã/phường để khớp PGD_XA_MAP với HSTD."""
    s = unicodedata.normalize("NFD", str(text or "").strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d")
    s = re.sub(r"^(xa|phuong|thi tran)\s+", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _ma_keys_phat_sinh_nam(df_xa: "pd.DataFrame | None") -> set[str]:
    """Các ma_key có dư nợ hiện tại hoặc phát sinh giải ngân/thu nợ trong năm."""
    if df_xa is None or df_xa.empty:
        return set()
    if COT_MA_CHUONG_TRINH not in df_xa.columns or COT_NGUON_VON not in df_xa.columns:
        return set()

    active = pd.Series(False, index=df_xa.index)
    cols_phat_sinh = [COT_TONG_DU_NO]
    cols_phat_sinh.extend(c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df_xa.columns)
    cols_phat_sinh.extend(c for c in HSTD_THU_NO_NAM_ALIASES if c in df_xa.columns)

    for col in dict.fromkeys(cols_phat_sinh):
        if col in df_xa.columns:
            active = active | (pd.to_numeric(df_xa[col], errors="coerce").fillna(0) > 0)
    if not active.any():
        return set()

    lookup: dict[tuple[int, int], list[str]] = {}
    for ma_key, ma_ct, _, nguon_von, _ in CHUONG_TRINH_KHTD:
        nv_int = 1 if nguon_von == "TW" else 2
        lookup.setdefault((int(ma_ct), nv_int), []).append(ma_key)

    tmp = pd.DataFrame(
        {
            "ma_ct": pd.to_numeric(df_xa.loc[active, COT_MA_CHUONG_TRINH], errors="coerce").fillna(0).astype(int),
            "nv": pd.to_numeric(df_xa.loc[active, COT_NGUON_VON], errors="coerce").fillna(0).astype(int),
        }
    )
    keys: set[str] = set()
    for row in tmp.itertuples(index=False):
        keys.update(lookup.get((int(row.ma_ct), int(row.nv)), []))
    return keys


@st.cache_data(show_spinner=False)
def _du_lieu_khtd_xa_cached(
    _df_full: "pd.DataFrame | None",
    pgd_chon: str,
    xa_chon: str,
    hstd_mtime: float = 0.0,
    rules_ver: int = 0,
) -> tuple[dict[str, float], dict[str, str], set[str]]:
    """Lọc đúng PGD + xã rồi tính TH và danh sách chương trình có phát sinh."""
    _ = (hstd_mtime, rules_ver)
    if _df_full is None or _df_full.empty:
        return {}, {}, set()
    if COT_TEN_PGD not in _df_full.columns or COT_TEN_XA not in _df_full.columns:
        return {}, {}, set()

    s_pgd = _df_full[COT_TEN_PGD].astype(str).str.strip()
    df_pgd = _df_full[s_pgd == str(pgd_chon).strip()]
    if df_pgd.empty:
        return {}, {}, set()

    xa_norm = _norm_xa_text(xa_chon)
    s_xa = df_pgd[COT_TEN_XA].map(_norm_xa_text)
    df_xa = df_pgd[s_xa == xa_norm]
    if df_xa.empty:
        return {}, {}, set()

    th_xa = _tinh_thuc_hien_theo_ct(df_xa)
    _, ten_map_q = _quet_ct_co_du_no(df_xa)
    keys_phat_sinh = _ma_keys_phat_sinh_nam(df_xa)
    return th_xa, ten_map_q, keys_phat_sinh


@st.cache_data(show_spinner=False)
def _du_lieu_hien_thi_khtd_cn_cached(
    _df_full: "pd.DataFrame | None",
    nv_chon: str,
    them_keys: tuple[str, ...],
    hstd_mtime: float = 0.0,
) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Cache danh sách CT hiển thị và ten_map cho màn KHTD Chi nhánh."""
    _ = hstd_mtime
    ds_ct = _chon_ds_ct(nv_chon, _df_full, them_keys=set(them_keys))
    _, ten_map_q = _quet_ct_co_du_no(_df_full)
    return ds_ct, ten_map_q


# Thư mục lưu văn bản QĐ cấp Chi nhánh
QD_DIR_CN = DATA_DIR / "qd"


def _luu_meta_qd(kv_key: str, danh_sach: list[dict], username: str) -> None:
    """Ghi danh sách metadata file QĐ vào kv_store. Hiển thị st.error nếu thất bại."""
    try:
        _svc_luu_meta_qd(kv_key, danh_sach, username)
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        st.error(f"Lỗi lưu metadata file QĐ: {e}")


def _luu_file_qd(uploaded, thu_muc: Path, kv_key: str, username: str) -> Path:
    """Lưu file mới với timestamp prefix, cập nhật metadata trong kv_store."""
    return _svc_luu_file_qd(uploaded, thu_muc, kv_key, username)


def _hien_thi_lich_su_qd(kv_key: str, nhan: str, role: str, username: str) -> None:
    """Hiển thị bảng lịch sử file QĐ, nút tải xuống và (admin) nút xóa."""
    danh_sach = _doc_meta_qd(kv_key)
    st.markdown(f"**{nhan}**")
    if not danh_sach:
        st.info("📭 Chưa có file nào được upload.")
        return

    # Header bảng
    h1, h2, h3, h4, h5, h6 = st.columns([3, 2, 2, 1.5, 1, 1])
    h1.markdown("**Tên file**")
    h2.markdown("**Ngày upload**")
    h3.markdown("**Người upload**")
    h4.markdown("**Dung lượng**")

    for idx_rev, meta in enumerate(reversed(danh_sach)):
        idx_thuc = len(danh_sach) - 1 - idx_rev
        c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 1.5, 1, 1])
        c1.text(meta.get("ten_file", "—"))
        c2.text(meta.get("ngay_upload", "—"))
        c3.text(meta.get("nguoi_upload", "—"))
        c4.text(_format_kich_thuoc(meta.get("kich_thuoc", 0)))

        duong_dan = Path(meta.get("duong_dan", ""))
        if duong_dan.exists():
            c5.download_button(
                "⬇",
                data=duong_dan.read_bytes(),
                file_name=meta.get("ten_file", duong_dan.name),
                key=f"dl_{kv_key}_{idx_rev}",
                help="Tải xuống",
            )
        else:
            c5.markdown("⚠️")

        if get_permissions(role)["can_edit_khtd"]:
            if c6.button("🗑", key=f"del_{kv_key}_{idx_rev}", help="Xóa file"):
                if duong_dan.exists():
                    duong_dan.unlink()
                danh_sach.pop(idx_thuc)
                _luu_meta_qd(kv_key, danh_sach, username)
                db.ghi_audit(
                    username, "xoa_van_ban_qd",
                    f"File: {meta.get('ten_file')} · key: {kv_key}",
                )
                st.rerun()


def _section_van_ban_qd_cn(role: str, username: str) -> None:
    """Upload / hiển thị lịch sử văn bản QĐ cấp Chi nhánh."""
    with st.expander("📎 Văn bản QĐ", expanded=True):
        # ── Lịch sử từng loại ────────────────────────────────────────────
        col_hist1, col_hist2 = st.columns(2)
        with col_hist1:
            _hien_thi_lich_su_qd("qd_files_hdqt_tinh", "QĐ HĐQT tỉnh", role, username)
        with col_hist2:
            _hien_thi_lich_su_qd("qd_files_tw", "QĐ NHCSXH TW", role, username)

        if not get_permissions(role)["can_edit_khtd"]:
            st.caption("🔒 Chỉ Admin / Manager mới được upload văn bản QĐ.")
            return

        # ── Upload file mới ───────────────────────────────────────────────
        st.divider()
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            f_hdqt = st.file_uploader(
                "Upload QĐ HĐQT tỉnh",
                type=["pdf", "xlsx", "xls"],
                key="vb_hdqt_tinh_cn",
            )
            if f_hdqt:
                _id = f"qd_done_hdqt_tinh_{f_hdqt.name}_{f_hdqt.size}"
                if not st.session_state.get(_id):
                    st.session_state[_id] = True
                    try:
                        dp = _luu_file_qd(
                            f_hdqt,
                            QD_DIR_CN / "hdqt_tinh",
                            "qd_files_hdqt_tinh",
                            username,
                        )
                        db.ghi_audit(username, "upload_vb_qd_hdqt_tinh",
                                     f"File: {dp.name}")
                        st.success(f"✅ Đã lưu: `{dp.name}`")
                        st.rerun()
                    except Exception as e:
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        st.session_state.pop(_id, None)
                        st.error(f"Lỗi lưu file QĐ HĐQT tỉnh: {e}")
        with col_u2:
            f_tw = st.file_uploader(
                "Upload QĐ NHCSXH TW",
                type=["pdf", "xlsx", "xls"],
                key="vb_qd_tw_cn",
            )
            if f_tw:
                _id = f"qd_done_tw_{f_tw.name}_{f_tw.size}"
                if not st.session_state.get(_id):
                    st.session_state[_id] = True
                    try:
                        dp = _luu_file_qd(
                            f_tw,
                            QD_DIR_CN / "tw",
                            "qd_files_tw",
                            username,
                        )
                        db.ghi_audit(username, "upload_vb_qd_tw",
                                     f"File: {dp.name}")
                        st.success(f"✅ Đã lưu: `{dp.name}`")
                        st.rerun()
                    except Exception as e:
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        st.session_state.pop(_id, None)
                        st.error(f"Lỗi lưu file QĐ TW: {e}")


def _doc_excel_khtd_cn_upload(file_bytes: bytes) -> tuple[dict[str, float], int, list[str]] | None:
    try:
        out, dem, bo_qua = _svc_doc_excel_khtd_cn_upload(
            file_bytes,
            ma_keys_co_khtd=set(MA_KEYS_CO_KHTD),
        )
    except ValueError as e:
        st.error(str(e))
        return None
    if bo_qua:
        st.warning(
            f"Bỏ qua **{len(bo_qua)}** dòng có Mã CT không thuộc danh mục KHTD: "
            f"{', '.join(sorted(set(bo_qua))[:12])}"
            + ("…" if len(set(bo_qua)) > 12 else "")
        )
    return out, dem, bo_qua


def _tab_khtd_chi_nhanh(
    role: str, username: str, df_full: "pd.DataFrame | None",
    df_gqvl: "pd.DataFrame | None" = None
) -> None:
    st.subheader("🏛️ Kế hoạch Tín dụng Chi nhánh")

    co_quyen = get_permissions(role)["can_edit_khtd"]
    kh_cn = _dong_bo_nsvsmt_dp_keys(_doc_kv(KV_KEY_CN))
    hstd_mtime = ts_file(CACHE_HSTD)
    gqvl_mtime = ts_file(CACHE_GQVL)
    th_cn, th_gqvl = _tinh_th_cn_cached(df_full, df_gqvl, hstd_mtime, gqvl_mtime)

    if not co_quyen:
        st.warning("⚠️ Chỉ Admin / Manager mới được nhập kế hoạch cấp Chi nhánh.")
        df_loc = df_full
        from tabs.tab_khtd_xuat import _hien_thi_bang_cn_readonly  # lazy – tránh circular import
        _hien_thi_bang_cn_readonly(
            kh_cn,
            th_cn,
            df_loc=df_loc,
            th_gqvl=th_gqvl,
            username=username,
        )
        st.divider()
        _section_van_ban_qd_cn(role, username)
        return

    nv_chon = st.radio(
        "Hiển thị nguồn vốn (bảng tóm tắt)",
        ["Tất cả", "Trung ương", "Địa phương"],
        horizontal=True,
        key="khtd_cn_nv_radio",
    )
    df_loc = df_full
    ds_ct, ten_map_q = _du_lieu_hien_thi_khtd_cn_cached(
        df_loc,
        nv_chon,
        tuple(sorted(set(kh_cn.keys()) | set(th_cn.keys()))),
        hstd_mtime,
    )

    # ── Banner trạng thái KH ──
    tong_ct = len(MA_KEYS_CO_KHTD)
    so_ct_co_kh = sum(
        1 for mk in MA_KEYS_CO_KHTD if float(kh_cn.get(mk, 0.0)) > 0
    )
    tong_kh_trieu = (
        sum(float(kh_cn.get(mk, 0.0)) for mk in MA_KEYS_CO_KHTD) / 1e6
    )
    tong_kh_ty = tong_kh_trieu / 1000.0

    if so_ct_co_kh == 0:
        mau = "#fff3cd"
        vien = "#ffc107"
        icon = "🔴"
        noi_dung = f"Chưa có kế hoạch — 0/{tong_ct} chương trình"
    elif so_ct_co_kh < tong_ct:
        mau = "#fff8e1"
        vien = "#ff9800"
        icon = "🟡"
        noi_dung = (
            f"Đã nhập {so_ct_co_kh}/{tong_ct} chương trình · "
            f"Tổng KH: {_fvn(tong_kh_trieu, 0)} triệu đồng"
        )
    else:
        mau = "#e8f5e9"
        vien = "#4caf50"
        icon = "🟢"
        noi_dung = (
            f"Đã nhập đủ {tong_ct}/{tong_ct} chương trình · "
            f"Tổng KH: {_fvn(tong_kh_ty, 3)} tỷ đồng"
        )

    st.markdown(
        f"<div style='padding:8px 14px;background:{mau};border-left:4px solid {vien};"
        f"border-radius:6px;font-size:0.9rem;font-weight:500;margin-bottom:8px;color:#1f2937'>"
        f"{icon} {noi_dung}</div>",
        unsafe_allow_html=True,
    )

    # ── Tóm tắt hiện trạng (luôn hiển thị) ───────────────────────────────
    st.markdown("##### 📊 Tóm tắt hiện trạng")
    from tabs.tab_khtd_xuat import _hien_thi_bang_cn_readonly  # lazy – tránh circular import
    _hien_thi_bang_cn_readonly(
        kh_cn,
        th_cn,
        ds_ct_loc=[mk for mk, _ in ds_ct],
        df_loc=df_loc,
        th_gqvl=th_gqvl,
        username=username,
    )

    st.caption(
        "📌 Đơn vị nhập và hiển thị: triệu đồng — số nguyên. "
        "HSTD là nguồn chính để tính thực hiện; riêng GQVL được tách 4 dòng theo nguồn TW/ĐP. "
        "Bảng bên dưới là lưới nhập liệu trực tiếp; số kế hoạch hiển thị có phân cách hàng nghìn để dễ nhìn, "
        "số thực hiện và còn phải thực hiện sẽ tự tính lại ngay khi chỉnh sửa."
    )
    draft_cn = st.session_state.get("khtd_cn_editor_draft", {})
    df_editor_meta = _tao_bang_nhap_khtd_cn(kh_cn, th_cn, th_gqvl, ten_map_q, draft_cn)
    df_editor_view = _tao_view_editor_khtd_cn(df_editor_meta)
    patch_hien_tai = _trich_patch_khtd_cn_tu_bang(df_editor_meta, df_editor_meta)

    df_editor = st.data_editor(
        df_editor_view,
        key="khtd_cn_editor",
        hide_index=True,
        use_container_width=True,
        height=720,
        num_rows="fixed",
        column_config={
            "Chương trình": st.column_config.TextColumn(width="large"),
            "KH TW": st.column_config.TextColumn("KH TW", width="small"),
            "TH TW": st.column_config.TextColumn("TH TW", width="small"),
            "Còn TH TW": st.column_config.TextColumn("Còn TH TW", width="small"),
            "KH ĐP": st.column_config.TextColumn("KH ĐP", width="small"),
            "TH ĐP": st.column_config.TextColumn("TH ĐP", width="small"),
            "Còn TH ĐP": st.column_config.TextColumn("Còn TH ĐP", width="small"),
            "TH tổng": st.column_config.TextColumn("TH tổng", width="small"),
            "Còn TH tổng": st.column_config.TextColumn("Còn TH tổng", width="small"),
        },
        disabled=[
            "Chương trình",
            "TH TW",
            "Còn TH TW",
            "TH ĐP",
            "Còn TH ĐP",
            "TH tổng",
            "Còn TH tổng",
        ],
    )
    patch_moi = _trich_patch_khtd_cn_tu_bang(df_editor, df_editor_meta)
    if patch_moi != patch_hien_tai:
        st.session_state["khtd_cn_editor_draft"] = patch_moi

    tong_kh_nhap_form = sum(float(v or 0.0) for v in patch_moi.values()) * 1_000_000
    if tong_kh_nhap_form <= 0:
        st.warning("⚠️ Tất cả chỉ tiêu đang = 0, kiểm tra lại trước khi lưu.")

    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        bo_nhap = st.button("↺ Khôi phục số đã lưu", key="khtd_cn_reset_draft", use_container_width=True)
    with col_f2:
        luu = st.button("💾 Lưu kế hoạch Chi nhánh", key="khtd_cn_save_btn", type="primary", use_container_width=True)

    if bo_nhap:
        st.session_state.pop("khtd_cn_editor_draft", None)
        st.session_state.pop("khtd_cn_editor", None)
        st.rerun()

    if luu:
        patch = _dong_bo_gqvl_tong_keys(dict(patch_moi))
        tong_kh_luu = sum(float(v or 0.0) for v in patch_moi.values()) * 1_000_000
        if tong_kh_luu <= 0:
            st.warning("⚠️ Tất cả chỉ tiêu đang = 0, kiểm tra lại trước khi lưu.")
        else:
            kh_cn.pop("6_DP_TINH", None)
            kh_cn.pop("6_DP_XA", None)
            for ma_key, gia_tri_trieu in patch.items():
                kh_cn[ma_key] = gia_tri_trieu * 1_000_000
            if _luu_kv(KV_KEY_CN, kh_cn, username):
                tw_kh_d = sum(
                    float(kh_cn.get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "TW"
                )
                dp_kh_d = sum(
                    float(kh_cn.get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "DP"
                )
                tw_th_d = sum(
                    float(th_cn.get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "TW"
                )
                dp_th_d = sum(
                    float(th_cn.get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "DP"
                )
                pt_tw = round(tw_th_d / tw_kh_d * 100, 1) if tw_kh_d > 0 else None
                pt_dp = round(dp_th_d / dp_kh_d * 100, 1) if dp_kh_d > 0 else None
                all_kh_d = tw_kh_d + dp_kh_d
                all_th_d = tw_th_d + dp_th_d
                pt_all = round(all_th_d / all_kh_d * 100, 1) if all_kh_d > 0 else None
                db.ghi_audit(
                    username,
                    "luu_khtd_cn",
                    f"{len(patch_moi)} chỉ tiêu, tổng {vn(sum(patch_moi.values()), 1)} triệu",
                )
                st.cache_data.clear()
                st.session_state.pop("khtd_cn_editor_draft", None)
                st.session_state.pop("khtd_cn_editor", None)
                st.session_state["khtd_cn_save_info"] = (
                    tw_kh_d,
                    tw_th_d,
                    pt_tw,
                    dp_kh_d,
                    dp_th_d,
                    pt_dp,
                    all_kh_d,
                    all_th_d,
                    pt_all,
                )
                st.rerun()

    _info_luu = st.session_state.pop("khtd_cn_save_info", None)
    if isinstance(_info_luu, tuple) and len(_info_luu) == 9:
        (
            tw_kh_d,
            tw_th_d,
            pt_tw,
            dp_kh_d,
            dp_th_d,
            pt_dp,
            all_kh_d,
            all_th_d,
            pt_all,
        ) = _info_luu
        _pt = lambda p: (f"{_fvn(p, 1)}%") if p is not None else "—"
        st.info(
            "💰 "
            f"KH Trung ương: **{_fvn(tw_kh_d / 1e6, 0)}** triệu đồng · "
            f"Thực hiện: **{_fvn(tw_th_d / 1e6, 0)}** triệu đồng · "
            f"Đạt **{_pt(pt_tw)}**\n\n"
            f"KH Địa phương: **{_fvn(dp_kh_d / 1e6, 0)}** triệu đồng · "
             f"Thực hiện: **{_fvn(dp_th_d / 1e6, 0)}** triệu đồng · "
            f"Đạt **{_pt(pt_dp)}**\n\n"
            f"Tổng cộng: KH **{_fvn(all_kh_d / 1e6, 0)}** triệu đồng · "
            f"Thực hiện: **{_fvn(all_th_d / 1e6, 0)}** triệu đồng · "
            f"Đạt **{_pt(pt_all)}**"
        )

    st.divider()
    _section_van_ban_qd_cn(role, username)

    with st.expander("📥 Upload Excel kế hoạch — nhanh nhất", expanded=False):
        df_mau = _tao_df_mau_khtd_cn()
        st.download_button(
            "⬇️ Tải file mẫu Excel",
            data=xuat_excel({"KHTD_CN": df_mau}),
            file_name=ten_file_xuat("Mau_KHTD_Chi_nhanh", "xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="khtd_cn_dl_mau",
        )
        f_up = st.file_uploader(
            "Chọn file Excel đã điền KH (triệu đồng)",
            type=["xlsx", "xls"],
            key="khtd_cn_upload",
        )
        if f_up:
            _uid = f"khtd_cn_up_done_{f_up.name}_{f_up.size}"
            if not st.session_state.get(_uid):
                try:
                    parsed = _doc_excel_khtd_cn_upload(f_up.getvalue())
                    if parsed is not None:
                        patch, dem, _bo_qua = parsed
                        if dem == 0:
                            st.session_state[_uid] = True
                            st.info(
                                "Không có dòng KH > 0 để lưu (đã bỏ qua giá trị 0 và ô trống)."
                            )
                        else:
                            kh_moi = dict(kh_cn)
                            kh_moi.update(patch)
                            kh_moi = _dong_bo_nsvsmt_dp_keys(kh_moi)
                            if _luu_kv(KV_KEY_CN, kh_moi, username):
                                db.ghi_audit(
                                    username,
                                    "upload_khtd_cn",
                                    f"{dem} chỉ tiêu từ Excel",
                                )
                                st.session_state[_uid] = True
                                st.success(
                                    f"✅ Đã lưu **{dem}** chỉ tiêu kế hoạch Chi nhánh từ Excel."
                                )
                                st.rerun()
                except Exception as e:
                    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                    st.error(f"Lỗi xử lý file: {e}")

    with st.expander("ℹ️ Hướng dẫn nhập kế hoạch", expanded=False):
        st.markdown("""
**Cách 1 — Upload Excel** (khuyến nghị):
1. Nhấn **⬇️ Tải file mẫu Excel** → điền số KH vào cột **KH (triệu đồng)** → lưu file
2. Kéo thả file vào ô Upload → nhấn **✅ Xác nhận lưu**

**Cách 2 — Nhập thủ công**:
1. Điền số kế hoạch vào cột **KH Trung ương** và/hoặc **KH Địa phương**
2. Nhấn **💾 Lưu kế hoạch**

> ⚠️ Đơn vị: **triệu đồng**, số nguyên. Cột Thực hiện và Còn phải TH tự động tính từ HSTD — không cần nhập.
""")

    # ── Lịch sử phiên bản (chỉ admin / admin_cn) ───────────────────────────
    if normalize_role(str(role or "user")) == "admin_cn":
        with st.expander("🕐 Lịch sử chỉnh sửa KHTD Chi nhánh", expanded=False):
            history = db.doc_kv_history(KV_KEY_CN, limit=15)
            if not history:
                st.info("Chưa có lịch sử chỉnh sửa.")
            else:
                df_hist = pd.DataFrame(history)
                df_hist_display = df_hist.rename(columns={
                    "changed_at": "Thời điểm",
                    "changed_by": "Người sửa",
                    "note": "Ghi chú",
                })
                st.dataframe(
                    df_hist_display[["Thời điểm", "Người sửa", "Ghi chú"]],
                    use_container_width=True,
                    hide_index=True,
                )

                options = ["-- Chọn --"] + [
                    f"#{row['id']} — {row['changed_at']} ({row['changed_by']})"
                    for row in history
                ]
                lua_chon = st.selectbox(
                    "Chọn phiên bản để xem trước",
                    options=options,
                    key="khtd_cn_history_select",
                )
                if lua_chon != "-- Chọn --":
                    try:
                        hist_id = int(lua_chon.split(" — ")[0].lstrip("#"))
                        row_match = next((r for r in history if r["id"] == hist_id), None)
                        if row_match:
                            value_preview = json.loads(row_match["value"])
                            st.json(value_preview)
                            if st.button(
                                "♻️ Khôi phục phiên bản này",
                                type="secondary",
                                key=f"khtd_restore_{hist_id}",
                            ):
                                ok = db.khoi_phuc_kv(
                                    KV_KEY_CN, hist_id, username
                                )
                                if ok:
                                    st.success("✅ Đã khôi phục. Tải lại trang để xem.")
                                    st.cache_data.clear()
                                else:
                                    st.error("Không tìm thấy phiên bản.")
                    except (ValueError, StopIteration):
                        st.error("Không tìm thấy phiên bản.")


def _hien_thi_bang_tom_tat_xa(
    xa_chon: str,
    kh_xa: dict,
    th_xa: dict[str, float],
    keys_phat_sinh: set[str] | None = None,
    show_all: bool = False,
) -> None:
    """Bảng tóm tắt hiện trạng KHTD theo Xã — giống format CN read-only."""
    st.markdown("##### 📊 Tóm tắt hiện trạng")
    keys_phat_sinh = set(keys_phat_sinh or set())

    BD = "#d1d5db"
    H_BG = "#003D7A"
    NHOM_BG = "#e8f0f8"
    TONG_BG = "#E8F4FD"
    RED = "#DC2626"
    AMBER = "#D97706"
    GREEN = "#16A34A"

    def _tl_color(tl: float | None) -> str:
        if tl is None:
            return "#9ca3af"
        if tl >= 100:
            return GREEN
        if tl >= 95:
            return AMBER
        return RED

    def _td(v: str, align: str = "right", color: str = "", bg: str = "", fw: str = "") -> str:
        s = f'text-align:{align};padding:5px 8px;border:1px solid {BD};font-size:0.82rem;white-space:nowrap'
        if color:
            s += f";color:{color}"
        if bg:
            s += f";background:{bg}"
        if fw:
            s += f";font-weight:{fw}"
        return f"<td style='{s}'>{v}</td>"

    def _co_du_lieu(ma_ct: int) -> bool:
        if show_all:
            return True
        for mk in (f"{ma_ct}_TW", f"{ma_ct}_DP"):
            if mk not in MA_KEYS_CO_KHTD:
                continue
            if float(kh_xa.get(f"{xa_chon}|{mk}", 0.0) or 0.0) > 0:
                return True
            if float(th_xa.get(mk, 0.0) or 0.0) > 0:
                return True
            if mk in keys_phat_sinh:
                return True
        return False

    html_rows: list[str] = []
    stt_no = 0
    tong_kh = 0.0
    tong_th = 0.0

    html_rows.append(
        "<table style='width:100%;border-collapse:collapse;font-size:0.82rem'>"
        "<colgroup>"
        "<col style='width:4%'><col style='width:36%'>"
        "<col style='width:15%'><col style='width:15%'>"
        "<col style='width:15%'><col style='width:15%'>"
        "</colgroup>"
        "<tr>"
        + _td("STT", "center", "", H_BG, "bold")
        + _td("Chỉ tiêu", "left", "#fff", H_BG, "bold")
        + _td("KH (tr.đ)", "right", "#fff", H_BG, "bold")
        + _td("TH (tr.đ)", "right", "#fff", H_BG, "bold")
        + _td("Còn phải TH (tr.đ)", "right", "#fff", H_BG, "bold")
        + _td("TL%", "right", "#fff", H_BG, "bold")
        + "</tr>"
    )

    for tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
        group_rows: list[str] = []
        for ma_ct in ds_ma_ct:
            mk_tw = f"{ma_ct}_TW"
            mk_dp = f"{ma_ct}_DP"
            co_tw = mk_tw in MA_KEYS_CO_KHTD
            co_dp = mk_dp in MA_KEYS_CO_KHTD
            if not co_tw and not co_dp:
                continue
            if not _co_du_lieu(ma_ct):
                continue

            kh_vnd = 0.0
            th_vnd = 0.0
            if co_tw:
                kh_vnd += float(kh_xa.get(f"{xa_chon}|{mk_tw}", 0.0) or 0.0)
                th_vnd += float(th_xa.get(mk_tw, 0.0) or 0.0)
            if co_dp:
                kh_vnd += float(kh_xa.get(f"{xa_chon}|{mk_dp}", 0.0) or 0.0)
                th_vnd += float(th_xa.get(mk_dp, 0.0) or 0.0)

            kh_v = kh_vnd / 1e6
            th_v = th_vnd / 1e6
            con_phai_th_v = max(kh_vnd - th_vnd, 0) / 1e6
            tl = th_v / kh_v * 100 if kh_v > 0 else None

            if kh_vnd > 0 or th_vnd > 0:
                tong_kh += kh_vnd
                tong_th += th_vnd

            stt_no += 1
            kh_str = _fvn(kh_v, 0) if kh_v > 0 else "—"
            th_str = _fvn(th_v, 0) if th_v > 0 else "—"
            con_str = _fvn(con_phai_th_v, 0)
            tl_str = f"{_fvn(tl, 1)}%" if tl is not None else "—"
            tl_c = _tl_color(tl)

            tds = (
                _td(str(stt_no), "center")
                + _td(_ten_ct_base(ma_ct), "left")
                + _td(kh_str, "right")
                + _td(th_str, "right")
                + _td(con_str, "right")
                + _td(tl_str, "right", tl_c)
            )
            group_rows.append(f"<tr>{tds}</tr>")

        if group_rows:
            tds = (
                _td("", "center", "", NHOM_BG, "bold")
                + _td(tieu_de_nhom, "left", "#1f2937", NHOM_BG, "bold")
                + _td("", "right", "", NHOM_BG)
                + _td("", "right", "", NHOM_BG)
                + _td("", "right", "", NHOM_BG)
                + _td("", "right", "", NHOM_BG)
            )
            html_rows.append(f"<tr>{tds}</tr>")
            html_rows.extend(group_rows)

    if stt_no == 0:
        st.info("Xã này chưa có dư nợ, giải ngân, thu nợ trong năm hoặc kế hoạch đã nhập.")
        return

    # Dòng tổng cộng
    tong_kh_v = tong_kh / 1e6
    tong_th_v = tong_th / 1e6
    tong_con_v = max(tong_kh - tong_th, 0) / 1e6
    tong_tl = tong_th_v / tong_kh_v * 100 if tong_kh_v > 0 else None
    tds_tong = (
        _td("", "center", "#1f2937", TONG_BG, "bold")
        + _td("Tổng cộng", "left", "#1f2937", TONG_BG, "bold")
        + _td(_fvn(tong_kh_v, 0) if tong_kh_v > 0 else "—", "right", "#1f2937", TONG_BG, "bold")
        + _td(_fvn(tong_th_v, 0) if tong_th_v > 0 else "—", "right", "#1f2937", TONG_BG, "bold")
        + _td(_fvn(tong_con_v, 0), "right", "#1f2937", TONG_BG, "bold")
        + _td(f"{_fvn(tong_tl, 1)}%" if tong_tl is not None else "—", "right",
              _tl_color(tong_tl), TONG_BG, "bold")
    )
    html_rows.append(f"<tr>{tds_tong}</tr>")
    html_rows.append("</table>")

    st.markdown("".join(html_rows), unsafe_allow_html=True)
    st.caption("📌 Đơn vị: triệu đồng. Mặc định chỉ hiện chương trình có KH hoặc có dư nợ/giải ngân/thu nợ trong năm của xã đang chọn.")


def _tab_khtd_theo_xa(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    st.subheader("📍 Kế hoạch Tín dụng theo Xã")

    co_quyen = get_permissions(role)["can_edit_khtd"]
    if not co_quyen:
        st.warning("⚠️ Chỉ Admin / Manager mới được nhập kế hoạch theo Xã.")
        return

    kh_xa = _doc_kv(KV_KEY_XA)

    # ── Chọn PGD ─────────────────────────────────────────────────────────
    pgd_chon = st.selectbox("Chọn PGD", DS_PGD, key="khtd_xa_pgd_sel")
    danh_sach_xa = PGD_XA_MAP.get(pgd_chon, [])
    if not danh_sach_xa:
        st.warning(f"Chưa có danh sách xã cho **{pgd_chon}**.")
        return

    # Nút xuất Excel tất cả xã
    if st.button("📥 Xuất Excel tất cả xã", key="xuat_excel_tat_ca_xa"):
        kh_xa = _doc_kv(KV_KEY_XA) or {}
        ds_xa = PGD_XA_MAP.get(pgd_chon, [])
        sheets = {}

        # Sheet tổng hợp PGD
        rows_th = []
        for ten_xa in ds_xa:
            kh_tw = sum(
                kh_xa.get(f"{ten_xa}|{mk}", 0)
                for mk in MA_KEYS_CO_KHTD if mk.endswith("_TW")
            ) / 1e6
            kh_dp = sum(
                kh_xa.get(f"{ten_xa}|{mk}", 0)
                for mk in MA_KEYS_CO_KHTD if mk.endswith("_DP")
            ) / 1e6
            tong_kh = kh_tw + kh_dp
            rows_th.append({
                "Xã/Phường": ten_xa,
                "KH TW (triệu)": round(kh_tw, 1),
                "KH ĐP (triệu)": round(kh_dp, 1),
                "Tổng KH (triệu)": round(tong_kh, 1),
            })
        if rows_th:
            df_th = pd.DataFrame(rows_th)
            tong_row = {
                "Xã/Phường": "Tổng cộng",
                "KH TW (triệu)": round(df_th["KH TW (triệu)"].sum(), 1),
                "KH ĐP (triệu)": round(df_th["KH ĐP (triệu)"].sum(), 1),
                "Tổng KH (triệu)": round(df_th["Tổng KH (triệu)"].sum(), 1),
            }
            df_th = pd.concat([df_th, pd.DataFrame([tong_row])], ignore_index=True)
            sheets["Tổng hợp PGD"] = df_th

        # Sheet từng xã
        for ten_xa in ds_xa:
            rows_xa = []
            stt = 1
            for _, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
                for ma_ct in ds_ma_ct:
                    for mk, nv_label in [
                        (f"{ma_ct}_TW", "TW"),
                        (f"{ma_ct}_DP", "ĐP"),
                    ]:
                        if mk not in MA_KEYS_CO_KHTD:
                            continue
                        kh = kh_xa.get(f"{ten_xa}|{mk}", 0) / 1e6
                        if kh <= 0:
                            continue
                        rows_xa.append({
                            "STT": stt,
                            "Chương trình": _ten_ct_base(ma_ct),
                            "Nguồn vốn": nv_label,
                            "KH (triệu)": round(kh, 1),
                        })
                        stt += 1
            if rows_xa:
                df_xa = pd.DataFrame(rows_xa)
                tong_xa = {
                    "STT": "",
                    "Chương trình": "Tổng cộng",
                    "Nguồn vốn": "",
                    "KH (triệu)": round(df_xa["KH (triệu)"].sum(), 1),
                }
                df_xa = pd.concat(
                    [df_xa, pd.DataFrame([tong_xa])], ignore_index=True
                )
                ten_sheet = _clean_sheet_name(ten_xa)
                sheets[ten_sheet] = df_xa

        if sheets:
            excel_bytes = xuat_excel(sheets)
            ten_file = ten_file_xuat(f"KHTD_XA_{pgd_chon}")
            st.download_button(
                "⬇️ Tải Excel",
                data=excel_bytes,
                file_name=ten_file,
                mime="application/vnd.openxmlformats-officedocument"
                     ".spreadsheetml.sheet",
                key="dl_khtd_xa_excel",
            )
        else:
            st.info("Chưa có dữ liệu kế hoạch để xuất.")

    # ── Thư mục lưu PDF ────────────────────────────────────────────────────
    st.session_state.setdefault("khtd_pdf_folder", "")
    col_path, col_btn = st.columns([3, 1])
    with col_path:
        pdf_folder = st.text_input(
            "📁 Thư mục lưu PDF",
            value=st.session_state["khtd_pdf_folder"],
            placeholder="C:\\KHTD_PDF\\ hoặc /home/user/khtd_pdf/",
            help="Để trống nếu muốn tải về thay vì lưu file",
            key="khtd_pdf_folder_input"
        )
        st.session_state["khtd_pdf_folder"] = pdf_folder
    
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        xuat_pdf_clicked = st.button("🖨️ Xuất PDF", use_container_width=True, type="primary")

    # ── Upload Excel hàng loạt ────────────────────────────────────────────
    with st.expander("📤 Upload Excel kế hoạch hàng loạt", expanded=False):
        st.caption(
            "Cấu trúc file: **Cột A** = Tên xã · **Cột B** = Mã CT (vd: `1_TW`) · "
            "**Cột C** = Giá trị (triệu đồng)"
        )
        file_up = st.file_uploader(
            "Chọn file Excel",
            type=["xlsx", "xls"],
            key="khtd_xa_file_upload",
        )
        if file_up:
            try:
                updates, dem, canh_bao = _svc_doc_excel_khtd_xa_upload(
                    file_up.getvalue(),
                    ds_xa_hop_le=set(danh_sach_xa),
                    ma_keys_co_khtd=set(MA_KEYS_CO_KHTD),
                )
                kh_xa.update(updates)
                if _luu_kv(KV_KEY_XA, kh_xa, username):
                    db.ghi_audit(username, "upload_khtd_xa",
                                 f"{dem} chỉ tiêu từ Excel")
                    st.success(f"✅ Đã lưu {dem} chỉ tiêu kế hoạch xã từ file Excel!")
                    if canh_bao:
                        st.warning(
                            f"⚠️ Có {len(canh_bao)} dòng bị bỏ qua:\n- "
                            + "\n- ".join(canh_bao[:8])
                            + ("\n- …" if len(canh_bao) > 8 else "")
                        )
                    st.rerun()
            except Exception as e:
                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                st.error(f"Lỗi đọc file Excel: {e}")

    st.divider()
    xa_chon = st.selectbox("Chọn Xã/Phường", danh_sach_xa, key="khtd_xa_xa_sel")
    st.caption("📌 Đơn vị nhập và hiển thị: triệu đồng")

    hstd_mtime = ts_file(CACHE_HSTD)
    rules_ver = len(db.doc_ndt_dp_rule_list())
    th_xa, ten_map_q, keys_phat_sinh = _du_lieu_khtd_xa_cached(
        df_full,
        pgd_chon,
        xa_chon,
        hstd_mtime,
        rules_ver,
    )
    hien_tat_ca_ct = st.checkbox(
        "Hiện tất cả chương trình",
        value=False,
        key="khtd_xa_show_all_ct",
    )

    def _ma_ct_hien_thi(ma_ct: int) -> bool:
        if hien_tat_ca_ct:
            return True
        for mk in (f"{ma_ct}_TW", f"{ma_ct}_DP"):
            if mk not in MA_KEYS_CO_KHTD:
                continue
            if float(kh_xa.get(f"{xa_chon}|{mk}", 0.0) or 0.0) > 0:
                return True
            if float(th_xa.get(mk, 0.0) or 0.0) > 0:
                return True
            if mk in keys_phat_sinh:
                return True
        return False

    # ── Tóm tắt hiện trạng ─────────────────────────────────────────────
    _hien_thi_bang_tom_tat_xa(
        xa_chon,
        kh_xa,
        th_xa,
        keys_phat_sinh,
        show_all=hien_tat_ca_ct,
    )

    _colw_xa = [3, 1, 1, 1, 1]  # Chương trình | KH TW | TH TW | KH ĐP | TH ĐP

    _ths_xa = (
        "font-size:0.82rem;font-weight:600;text-align:center;"
        "padding:7px 6px;border-radius:4px;white-space:nowrap"
    )
    st.markdown(
        f"""
<table style="width:100%;border-collapse:separate;border-spacing:3px 3px;
  table-layout:fixed;margin-bottom:2px">
<colgroup>
  <col style="width:42.86%">
  <col style="width:14.28%"><col style="width:14.28%">
  <col style="width:14.28%"><col style="width:14.28%">
</colgroup>
<tr>
  <th style="{_ths_xa};background:#f0f4fa"></th>
  <th colspan="2" style="{_ths_xa};background:#bbdefb;color:#1565c0">NGUỒN VỐN TRUNG ƯƠNG</th>
  <th colspan="2" style="{_ths_xa};background:#c8e6c9;color:#2e7d32">NGUỒN VỐN ĐỊA PHƯƠNG</th>
</tr>
<tr>
  <th style="{_ths_xa};background:#f0f4fa;color:#37474f">Chương trình</th>
  <th style="{_ths_xa};background:#e3f2fd;color:#1565c0">Kế hoạch</th>
  <th style="{_ths_xa};background:#e3f2fd;color:#1565c0">Thực hiện</th>
  <th style="{_ths_xa};background:#e8f5e9;color:#2e7d32">Kế hoạch</th>
  <th style="{_ths_xa};background:#e8f5e9;color:#2e7d32">Thực hiện</th>
</tr>
</table>""",
        unsafe_allow_html=True,
    )

    # ── Dòng tổng cộng ───────────────────────────────────────────────────
    ma_ct_hien_thi = [
        int(ma_ct)
        for _, ds_ma_ct in KHTD_CN_NHOM_MA_CT
        for ma_ct in ds_ma_ct
        if _ma_ct_hien_thi(int(ma_ct))
    ]
    keys_tw_hien = {f"{ma_ct}_TW" for ma_ct in ma_ct_hien_thi if f"{ma_ct}_TW" in MA_KEYS_CO_KHTD}
    keys_dp_hien = {f"{ma_ct}_DP" for ma_ct in ma_ct_hien_thi if f"{ma_ct}_DP" in MA_KEYS_CO_KHTD}
    tong_kh_tw = sum(float(kh_xa.get(f"{xa_chon}|{mk}", 0.0) or 0.0) for mk in keys_tw_hien) / 1_000_000
    tong_kh_dp = sum(float(kh_xa.get(f"{xa_chon}|{mk}", 0.0) or 0.0) for mk in keys_dp_hien) / 1_000_000
    tong_th_tw = sum(float(th_xa.get(mk, 0.0) or 0.0) for mk in keys_tw_hien) / 1e6
    tong_th_dp = sum(float(th_xa.get(mk, 0.0) or 0.0) for mk in keys_dp_hien) / 1e6
    _txt_kh_tw = f"{_fmt_vn(int(tong_kh_tw), 0)} tr" if tong_kh_tw > 0 else "—"
    _txt_th_tw = f"{_fmt_vn(int(tong_th_tw), 0)} tr" if tong_th_tw > 0 else "—"
    _txt_kh_dp = f"{_fmt_vn(int(tong_kh_dp), 0)} tr" if tong_kh_dp > 0 else "—"
    _txt_th_dp = f"{_fmt_vn(int(tong_th_dp), 0)} tr" if tong_th_dp > 0 else "—"
    st.markdown(
        f"<div style='display:flex;gap:12px;padding:8px 14px;background:#e8f4fd;color:#1f2937;"
        f"border-radius:6px;margin:6px 0;font-size:0.9rem'>"
        f"<span style='font-weight:600'>📊 Tổng cộng:</span>"
        f"<span>KH TW: <b>{_txt_kh_tw}</b></span>"
        f"<span>TH TW: <b>{_txt_th_tw}</b></span>"
        f"<span>KH ĐP: <b>{_txt_kh_dp}</b></span>"
        f"<span>TH ĐP: <b>{_txt_th_dp}</b></span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── CSS kẻ bảng ──
    st.markdown(
        """
<style>
[data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid #e2e8f0 !important;
    border-right: 1px solid #e2e8f0 !important;
    padding: 4px 0 !important;
    margin: 0 !important;
}
[data-testid="stHorizontalBlock"]:hover {
    background-color: rgba(128,128,128,0.12) !important;
}
[data-testid="column"] {
    border-right: 1px solid #e2e8f0 !important;
    padding: 0 8px !important;
}
[data-testid="column"]:last-child {
    border-right: none !important;
}
.khtd-program-name {
    font-size: 17px !important;
    font-weight: 500 !important;
    padding: 6px 0 !important;
}
.khtd-amount {
    font-size: 18px !important;
    font-weight: 600 !important;
    padding: 4px 0 !important;
}
/* Tăng font size cho ô nhập số KHTD */
.stNumberInput input[type="number"] {
    font-size: 17px !important;
    font-weight: 500 !important;
    padding: 6px 8px !important;
    height: 36px !important;
}
.stTextInput input {
    font-size: 16px !important;
    font-weight: 600 !important;
    text-align: right !important;
    padding: 8px 10px !important;
    min-height: 38px !important;
}
.stTextInput > div,
.stNumberInput > div {
    width: 100% !important;
}
.stTextInput,
.stNumberInput {
    margin: 2px 0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # ── Nhóm màu nền ──
    nhom_mau_nen = ["#eef6ff", "#eefaf3", "#fff8ee"]
    idx_nhom = 0

    with st.form(f"form_khtd_xa_{pgd_chon}_{xa_chon}"):
        gia_tri_moi: dict[str, float] = {}

        for tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
            ds_ma_ct_hien = [ma_ct for ma_ct in ds_ma_ct if _ma_ct_hien_thi(int(ma_ct))]
            if not ds_ma_ct_hien:
                continue
            bg = nhom_mau_nen[idx_nhom % len(nhom_mau_nen)]
            idx_nhom += 1
            st.markdown(
                f"<p style='margin:0.8rem 0 0.4rem 0;padding:7px 12px;"
                f"background-color:{bg};color:#1f2937;border-radius:6px;font-weight:600;"
                f"font-size:0.9rem'>{tieu_de_nhom}</p>",
                unsafe_allow_html=True,
            )
            for ma_ct in ds_ma_ct_hien:
                mk_tw = f"{ma_ct}_TW"
                mk_dp = f"{ma_ct}_DP"
                khoa_tw = f"{xa_chon}|{mk_tw}"
                khoa_dp = f"{xa_chon}|{mk_dp}"
                co_tw = mk_tw in MA_KEYS_CO_KHTD
                co_dp = mk_dp in MA_KEYS_CO_KHTD
                if not co_tw and not co_dp:
                    continue

                cols = st.columns(_colw_xa)
                ten_hang = _ten_ct_base(ma_ct, ten_map_q)
                cols[0].markdown(
                    f"<div class='khtd-program-name'>{ten_hang}</div>",
                    unsafe_allow_html=True,
                )

                if co_tw:
                    gia_tri_moi[khoa_tw] = cols[1].number_input(
                        f"tw_{ma_ct}",
                        value=float(kh_xa.get(khoa_tw, 0.0)) / 1_000_000,
                        min_value=0.0,
                        step=1000.0,
                        format="%.0f",
                        label_visibility="collapsed",
                        help="Kế hoạch Trung ương — đơn vị: triệu đồng",
                        key=f"khtd_xa_inp_{xa_chon}_{ma_ct}_tw",
                    )
                else:
                    cols[1].caption("—")

                vnd_tw = float(th_xa.get(mk_tw, 0.0) or 0.0)
                trieu_tw = vnd_tw / 1e6
                txt_th_tw = (
                    f"{_fmt_vn(int(trieu_tw), 0)} tr" if trieu_tw > 0 else "—"
                )
                cols[2].markdown(
                    f"<div class='khtd-amount' style='text-align:right'>"
                    f"{txt_th_tw}</div>",
                    unsafe_allow_html=True,
                )

                if co_dp:
                    gia_tri_moi[khoa_dp] = cols[3].number_input(
                        f"dp_{ma_ct}",
                        value=float(kh_xa.get(khoa_dp, 0.0)) / 1_000_000,
                        min_value=0.0,
                        step=1000.0,
                        format="%.0f",
                        label_visibility="collapsed",
                        help="Kế hoạch Địa phương — đơn vị: triệu đồng",
                        key=f"khtd_xa_inp_{xa_chon}_{ma_ct}_dp",
                    )
                else:
                    cols[3].caption("—")

                vnd_dp = float(th_xa.get(mk_dp, 0.0) or 0.0)
                trieu_dp = vnd_dp / 1e6
                txt_th_dp = (
                    f"{_fmt_vn(int(trieu_dp), 0)} tr" if trieu_dp > 0 else "—"
                )
                cols[4].markdown(
                    f"<div class='khtd-amount' style='text-align:right'>"
                    f"{txt_th_dp}</div>",
                    unsafe_allow_html=True,
                )

        # ── Xuất PDF nếu được yêu cầu ──────────────────────────────────────
        if xuat_pdf_clicked:
            # Tạo DataFrame cho PDF
            pdf_data = []
            stt = 1
            
            for tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
                for ma_ct in ds_ma_ct:
                    mk_tw = f"{ma_ct}_TW"
                    mk_dp = f"{ma_ct}_DP"
                    khoa_tw = f"{xa_chon}|{mk_tw}"
                    khoa_dp = f"{xa_chon}|{mk_dp}"
                    
                    # Lấy giá trị kế hoạch (triệu đồng)
                    kh_tw = float(gia_tri_moi.get(khoa_tw, kh_xa.get(khoa_tw, 0.0))) / 1_000_000
                    kh_dp = float(gia_tri_moi.get(khoa_dp, kh_xa.get(khoa_dp, 0.0))) / 1_000_000
                    
                    # Chỉ thêm vào PDF nếu có kế hoạch TW hoặc ĐP
                    if kh_tw > 0 or kh_dp > 0:
                        ten_ct = _ten_ct_base(ma_ct, ten_map_q)
                        pdf_data.append({
                            "STT": stt,
                            "Chương trình": ten_ct,
                            "KH TW (triệu đ)": fmt(kh_tw) if kh_tw > 0 else "—",
                            "KH ĐP (triệu đ)": fmt(kh_dp) if kh_dp > 0 else "—"
                        })
                        stt += 1
            
            if pdf_data:
                df_pdf = pd.DataFrame(pdf_data)
                ngay_hien_tai = datetime.now().strftime("%d/%m/%Y")
                tieu_de = f"KẾ HOẠCH TÍN DỤNG - XÃ {xa_chon.upper()}"
                tieu_de_phu = f"PGD {pgd_chon} - Ngày {ngay_hien_tai}"
                
                try:
                    pdf_bytes = xuat_pdf_bang(
                        df_pdf,
                        tieu_de,
                        tieu_de_phu,
                        nguoi_xuat=username,
                        cols_tien=["KH TW (triệu đ)", "KH ĐP (triệu đ)"],
                        prefix_file="KHTD"
                    )
                    
                    if pdf_folder:
                        try:
                            dp = _svc_luu_pdf_khtd_xa(
                                pdf_bytes,
                                pdf_folder,
                                pgd=pgd_chon,
                                xa=xa_chon,
                            )
                            st.success(f"✅ Đã lưu PDF: {dp}")
                        except Exception as _e:
                            logger.error("Lỗi trong khối except: %s", _e, exc_info=True)
                            st.warning(f"⚠️ Không lưu được PDF vào thư mục: {_e}")
                    
                    state = SCMStateManager()
                    state.downloads.set(
                        "khtd_xa_pdf",
                        pdf_bytes,
                        f"KHTD_{xa_chon}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    )
                    db.ghi_audit(username, "xuat_bieu_cn", f"KHTD xã — PGD: {pgd_chon} — Xã: {xa_chon}")
                    
                except Exception as e:
                    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                    SCMStateManager().downloads.clear("khtd_xa_pdf")
                    st.error(f"Lỗi xuất PDF: {e}")
            else:
                st.warning("Không có dữ liệu kế hoạch để xuất PDF")
                SCMStateManager().downloads.clear("khtd_xa_pdf")

        if st.form_submit_button("💾 Lưu kế hoạch xã này", type="primary"):
            for khoa, gia_tri_trieu in gia_tri_moi.items():
                kh_xa[khoa] = gia_tri_trieu * 1_000_000
            if _luu_kv(KV_KEY_XA, kh_xa, username):
                db.ghi_audit(username, "luu_khtd_xa",
                             f"PGD: {pgd_chon} — Xã: {xa_chon}")
                st.success(f"✅ Đã lưu kế hoạch cho xã **{xa_chon}**")
                st.rerun()

    state = SCMStateManager()
    if state.downloads.has("khtd_xa_pdf"):
        if st.download_button(
            label="⬇️ Tải PDF về máy",
            data=state.downloads.get_bytes("khtd_xa_pdf"),
            file_name=state.downloads.get_filename("khtd_xa_pdf") or "KHTD.pdf",
            mime="application/pdf",
            key="download_pdf_khtd_xa"
        ):
            state.downloads.clear("khtd_xa_pdf")


def render_nhap_cn(role: str, username: str, df_full: "pd.DataFrame | None", df_gqvl: "pd.DataFrame | None" = None) -> None:
    _tab_khtd_chi_nhanh(role, username, df_full, df_gqvl)


def render_nhap_pgd(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    _tab_khtd_theo_xa(role, username, df_full)
