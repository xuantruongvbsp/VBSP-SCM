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
from components.delta_card import delta_card, kpi_row
from config import (
    CHUONG_TRINH_KHTD,
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    DS_PGD,
    PGD_XA_MAP,
    CACHE_GQVL,
    CACHE_HSTD,
    HSTD_DS_CHO_VAY_NAM_ALIASES,
    HSTD_THU_NO_NAM_ALIASES,
)
from data.core import ts_file
from data.pgd import pgd_slug
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


_KHTD_CACHE_MAX_ENTRIES = 3

_PGD_XA_STT_CHUAN: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    ("I",  "Hội sở chi nhánh tỉnh", (
        ("1", "Phường Phước Tân"),
        ("2", "Phường Biên Hòa"),
        ("3", "Phường Trấn Biên"),
        ("4", "Phường Long Hưng"),
        ("5", "Phường Long Bình"),
        ("6", "Phường Trảng Dài"),
        ("7", "Phường Tam Phước"),
        ("8", "Phường Hố Nai"),
        ("9", "Phường Tam Hiệp"),
    )),
    ("II", "PGD Long Thành", (
        ("1", "Xã Phước Thái"),
        ("2", "Xã An Phước"),
        ("3", "Xã Bình An"),
        ("4", "Xã Long Thành"),
        ("5", "Xã Long Phước"),
    )),
    ("III", "PGD Trảng Bom", (
        ("1", "Xã An Viễn"),
        ("2", "Xã Hưng Thịnh"),
        ("3", "Xã Trảng Bom"),
        ("4", "Xã Bàu Hàm"),
        ("5", "Xã Bình Minh"),
    )),
    ("IV", "PGD Long Khánh", (
        ("1", "Phường Bảo Vinh"),
        ("2", "Phường Xuân Lập"),
        ("3", "Phường Long Khánh"),
        ("4", "Phường Bình Lộc"),
        ("5", "Phường Hàng Gòn"),
    )),
    ("V", "PGD Xuân Lộc", (
        ("1", "Xã Xuân Thành"),
        ("2", "Xã Xuân Bắc"),
        ("3", "Xã Xuân Định"),
        ("4", "Xã Xuân Lộc"),
        ("5", "Xã Xuân Phú"),
        ("6", "Xã Xuân Hòa"),
    )),
    ("VI", "PGD Định Quán", (
        ("1", "Xã Phú Vinh"),
        ("2", "Xã Định Quán"),
        ("3", "Xã Thanh Sơn"),
        ("4", "Xã Phú Hòa"),
        ("5", "Xã La Ngà"),
    )),
    ("VII", "PGD Vĩnh Cửu", (
        ("1", "Xã Tân An"),
        ("2", "Phường Tân Triều"),
        ("3", "Xã Trị An"),
        ("4", "Xã Phú Lý"),
    )),
    ("VIII", "PGD Tân Phú", (
        ("1", "Xã Phú Lâm"),
        ("2", "Xã Nam Cát Tiên"),
        ("3", "Xã Tân Phú"),
        ("4", "Xã Tà Lài"),
        ("5", "Xã Đak Lua"),
    )),
    ("IX", "PGD Thống Nhất", (
        ("1", "Xã Dầu Giây"),
        ("2", "Xã Thống Nhất"),
        ("3", "Xã Gia Kiệm"),
    )),
    ("X", "PGD Cẩm Mỹ", (
        ("1", "Xã Xuân Quế"),
        ("2", "Xã Xuân Đường"),
        ("3", "Xã Cẩm Mỹ"),
        ("4", "Xã Xuân Đông"),
        ("5", "Xã Sông Ray"),
    )),
    ("XI", "PGD Nhơn Trạch", (
        ("1", "Xã Đại Phước"),
        ("2", "Xã Nhơn Trạch"),
        ("3", "Xã Phước An"),
    )),
    ("XII", "PGD Bình Long", (
        ("1", "Phường An Lộc"),
        ("2", "Phường Bình Long"),
    )),
    ("XIII", "PGD Lộc Ninh", (
        ("1", "Xã Lộc Tấn"),
        ("2", "Xã Lộc Thạnh"),
        ("3", "Xã Lộc Thành"),
        ("4", "Xã Lộc Quang"),
        ("5", "Xã Lộc Ninh"),
        ("6", "Xã Lộc Hưng"),
    )),
    ("XIV", "PGD Bình Phước", (
        ("1", "Phường Đồng Xoài"),
        ("2", "Phường Bình Phước"),
    )),
    ("XV", "PGD Phước Long", (
        ("1", "Phường Phước Long"),
        ("2", "Phường Phước Bình"),
    )),
    ("XVI", "PGD Bù Đăng", (
        ("1", "Xã Thọ Sơn"),
        ("2", "Xã Bù Đăng"),
        ("3", "Xã Đăk Nhau"),
        ("4", "Xã Phước Sơn"),
        ("5", "Xã Bom Bo"),
        ("6", "Xã Nghĩa Trung"),
    )),
    ("XVII", "PGD Đồng Phú", (
        ("1", "Xã Thuận Lợi"),
        ("2", "Xã Đồng Phú"),
        ("3", "Xã Đồng Tâm"),
        ("4", "Xã Tân Lợi"),
    )),
    ("XVIII", "PGD Chơn Thành", (
        ("1", "Phường Minh Hưng"),
        ("2", "Xã Nha Bích"),
        ("3", "Phường Chơn Thành"),
    )),
    ("XIX", "PGD Bù Đốp", (
        ("1", "Xã Hưng Phước"),
        ("2", "Xã Thiện Hưng"),
        ("3", "Xã Tân Tiến"),
    )),
    ("XX", "PGD Bù Gia Mập", (
        ("1", "Xã Bù Gia Mập"),
        ("2", "Xã Phú Nghĩa"),
        ("3", "Xã Đa Kia"),
        ("4", "Xã Đăk Ơ"),
    )),
    ("XXI", "PGD Phú Riềng", (
        ("1", "Xã Bình Tân"),
        ("2", "Xã Long Hà"),
        ("3", "Xã Phú Trung"),
        ("4", "Xã Phú Riềng"),
    )),
    ("XXII", "PGD Hớn Quản", (
        ("1", "Xã Minh Đức"),
        ("2", "Xã Tân Hưng"),
        ("3", "Xã Tân Khai"),
        ("4", "Xã Tân Quan"),
    )),
)


def _stt_pgd_xa(pgd_name: str, xa_name: str | None = None) -> tuple[str, str | None, str | None]:
    """Tra số thứ tự chuẩn (PGD số la mã + xã số Ả-rập) theo danh sách hành chính.

    Returns:
        (stt_pgd_str, stt_xa_str or None, display_header_for_title):
            ví dụ ("III", "3", "III — PGD Trảng Bom · Mục 3 · Xã Trảng Bom")
    Nếu không tìm thấy → trả về ("", "", f"{pgd_name} · {xa_name}").
    """
    norm = lambda s: re.sub(r"\s+", " ", str(s or "").strip().lower())
    pgd_n = norm(pgd_name).replace("pgd ", "").replace(" hội sở", "")
    for stt_p, ten_p, dxs in _PGD_XA_STT_CHUAN:
        ten_p_n = norm(ten_p).replace("pgd ", "").replace(" hội sở", "")
        if ten_p_n != pgd_n:
            continue
        if xa_name is None:
            return stt_p, None, f"{stt_p} — {ten_p}"
        xa_n = norm(xa_name).replace("xã ", "").replace("phường ", "")
        for stt_x, ten_x in dxs:
            ten_x_n = norm(ten_x).replace("xã ", "").replace("phường ", "")
            if ten_x_n == xa_n:
                return stt_p, stt_x, f"{stt_p} — {ten_p} · Mục {stt_x} · {ten_x}"
        # PGD match nhưng xã không match → fallback
        return stt_p, None, f"{stt_p} — {ten_p} · {xa_name}"
    # Không khớp PGD → trả nguyên mẫu
    return "", "", f"{pgd_name}" + (f" · {xa_name}" if xa_name else "")


def _ndt_dp_rules_cache_key() -> str:
    """Fingerprint rule NĐT ĐP để bust cache khi sửa nội dung rule."""
    rules = []
    for item in db.doc_ndt_dp_rule_list():
        if not isinstance(item, dict):
            continue
        rules.append(
            {
                "ma_ct": item.get("ma_ct"),
                "ma": str(item.get("ma", "") or "").strip(),
                "cap": str(item.get("cap", "") or "").strip().lower(),
                "ghi_chu": str(item.get("ghi_chu", "") or "").strip(),
            }
        )
    rules.sort(
        key=lambda item: (
            "" if item["ma_ct"] is None else str(item["ma_ct"]),
            item["ma"],
            item["cap"],
            item["ghi_chu"],
        )
    )
    return json.dumps(rules, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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


@st.cache_data(show_spinner=False, max_entries=_KHTD_CACHE_MAX_ENTRIES)
def _tinh_th_cn_cached(
    _df_full: "pd.DataFrame | None",
    _df_gqvl: "pd.DataFrame | None",
    hstd_mtime: float = 0.0,
    gqvl_mtime: float = 0.0,
    rules_key: str = "",
) -> tuple[dict[str, float], dict[str, float]]:
    """Tính TH KHTD Chi nhánh theo mtime parquet để tránh quét lại mỗi rerun."""
    _ = (hstd_mtime, gqvl_mtime, rules_key)
    if _df_full is None:
        return {}, {}
    return _tinh_thuc_hien_khtd_cn(_df_full, _df_gqvl)


@st.cache_data(show_spinner=False, max_entries=_KHTD_CACHE_MAX_ENTRIES)
def _du_lieu_khtd_pgd_cached(
    _df_full: "pd.DataFrame | None",
    pgd_chon: str,
    hstd_mtime: float = 0.0,
    rules_key: str = "",
) -> tuple[dict[str, float], dict[str, str]]:
    """Lọc dữ liệu theo PGD rồi tính TH/ten_map một lần theo mtime HSTD."""
    _ = (hstd_mtime, rules_key)
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


_KHTD_XA_PHUONG_HIEN_THI_NORM = frozenset(
    _norm_xa_text(ten_xa)
    for ten_xa in [
        "Phước Tân", "Biên Hòa", "Trấn Biên", "Long Hưng", "Long Bình",
        "Trảng Dài", "Tam Phước", "Hố Nai", "Tam Hiệp",
        "Bảo Vinh", "Xuân Lập", "Long Khánh", "Bình Lộc", "Hàng Gòn",
        "Tân Triều",
        "An Lộc", "Bình Long",
        "Đồng Xoài", "Bình Phước",
        "Phước Long", "Phước Bình",
        "Minh Hưng", "Chơn Thành",
    ]
)

_KHTD_TEN_XA_HIEN_THI_OVERRIDE = {
    "dak lua": "Đak Lua",
}


def _ten_xa_hien_thi_khtd(ten_xa: object) -> str:
    """Tên xã/phường hiển thị theo danh mục hành chính, độc lập tên khớp HSTD."""
    ten = re.sub(
        r"^(xã|phường|thị trấn)\s+",
        "",
        str(ten_xa or "").strip(),
        flags=re.IGNORECASE,
    )
    ten = re.sub(r"\s+", " ", ten).strip()
    ten_norm = _norm_xa_text(ten)
    ten = _KHTD_TEN_XA_HIEN_THI_OVERRIDE.get(ten_norm, ten)
    loai = "Phường" if ten_norm in _KHTD_XA_PHUONG_HIEN_THI_NORM else "Xã"
    return f"{loai} {ten}".strip()


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


@st.cache_data(show_spinner=False, max_entries=_KHTD_CACHE_MAX_ENTRIES)
def _du_lieu_khtd_xa_cached(
    _df_full: "pd.DataFrame | None",
    pgd_chon: str,
    xa_chon: str,
    hstd_mtime: float = 0.0,
    rules_key: str = "",
) -> tuple[dict[str, float], dict[str, str], set[str]]:
    """Lọc đúng PGD + xã rồi tính TH và danh sách chương trình có phát sinh."""
    _ = (hstd_mtime, rules_key)
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


def _ds_ma_ct_khtd_hien_thi() -> list[int]:
    """Danh sách mã chương trình KHTD theo đúng thứ tự nhóm nghiệp vụ trên UI."""
    return list(
        dict.fromkeys(
            int(ma_ct)
            for _, ds_ma_ct in KHTD_CN_NHOM_MA_CT
            for ma_ct in ds_ma_ct
        )
    )


def _ma_keys_khtd_theo_ct_nv(ma_ct_chon: int | None, nv_int: int) -> list[str]:
    """Lấy các key KHTD tương ứng mã chương trình và nguồn vốn."""
    out: list[str] = []
    for ma_key, ma_ct, _, nguon_von, _ in CHUONG_TRINH_KHTD:
        if ma_ct_chon is not None and int(ma_ct) != int(ma_ct_chon):
            continue
        if (str(nguon_von).upper() == "TW" and int(nv_int) == 1) or (
            str(nguon_von).upper() == "DP" and int(nv_int) == 2
        ):
            out.append(str(ma_key))
    return out


def _tong_kh_xa_theo_keys(
    kh_xa: dict[str, float] | None,
    ten_xa_key: str,
    ma_keys: list[str],
) -> float:
    """Tổng kế hoạch đã lưu của một xã theo danh sách key, đơn vị VND."""
    kh_xa = kh_xa or {}
    return sum(float(kh_xa.get(f"{ten_xa_key}|{ma_key}", 0.0) or 0.0) for ma_key in ma_keys)


def _them_ke_hoach_vao_bang_xa(
    df_bang: pd.DataFrame,
    kh_xa: dict[str, float] | None,
    ma_ct_chon: int | None,
) -> pd.DataFrame:
    """Bổ sung cột KH và tỷ lệ hoàn thành vào bảng 95 xã/phường."""
    out = df_bang.copy()
    if out.empty:
        for col in ["KH TW", "KH ĐP", "Tổng KH", "TL %"]:
            out[col] = []
        return out

    keys_tw = _ma_keys_khtd_theo_ct_nv(ma_ct_chon, 1)
    keys_dp = _ma_keys_khtd_theo_ct_nv(ma_ct_chon, 2)
    xa_key_col = "_Xã key" if "_Xã key" in out.columns else "Xã/Phường"

    out["KH TW"] = [
        _tong_kh_xa_theo_keys(kh_xa, str(ten_xa), keys_tw)
        for ten_xa in out[xa_key_col].tolist()
    ]
    out["KH ĐP"] = [
        _tong_kh_xa_theo_keys(kh_xa, str(ten_xa), keys_dp)
        for ten_xa in out[xa_key_col].tolist()
    ]
    out["Tổng KH"] = out["KH TW"] + out["KH ĐP"]
    out["TL %"] = [
        (float(th) / float(kh) * 100.0) if float(kh or 0.0) > 0 else None
        for kh, th in zip(out["Tổng KH"], out["Tổng TH"])
    ]
    return out


def _phan_bo_kh_xa_theo_keys(
    kh_xa: dict[str, float],
    ten_xa_key: str,
    ma_keys: list[str],
    tong_vnd: float,
) -> None:
    """Ghi tổng KH vào một hoặc nhiều key con, giữ tỷ trọng cũ nếu đã có."""
    if not ma_keys:
        return
    tong_vnd = max(float(tong_vnd or 0.0), 0.0)
    if len(ma_keys) == 1:
        kh_xa[f"{ten_xa_key}|{ma_keys[0]}"] = tong_vnd
        return

    gia_tri_cu = [
        float(kh_xa.get(f"{ten_xa_key}|{ma_key}", 0.0) or 0.0)
        for ma_key in ma_keys
    ]
    tong_cu = sum(gia_tri_cu)
    if tong_vnd <= 0:
        for ma_key in ma_keys:
            kh_xa[f"{ten_xa_key}|{ma_key}"] = 0.0
        return
    if tong_cu > 0:
        for ma_key, gia_tri in zip(ma_keys, gia_tri_cu):
            kh_xa[f"{ten_xa_key}|{ma_key}"] = tong_vnd * gia_tri / tong_cu
        return
    chia_deu = tong_vnd / len(ma_keys)
    for ma_key in ma_keys:
        kh_xa[f"{ten_xa_key}|{ma_key}"] = chia_deu


def _tao_bang_thuc_hien_xa_theo_ct(
    df_full: "pd.DataFrame | None",
    ma_ct_chon: int | None,
    pgd_xa_map: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Tổng hợp TH của đủ địa bàn cấu hình, lọc theo một chương trình KHTD."""
    dia_ban = pgd_xa_map if pgd_xa_map is not None else PGD_XA_MAP
    rows = [
        {
            "STT": stt,
            "PGD": ten_pgd,
            "Xã/Phường": _ten_xa_hien_thi_khtd(ten_xa),
            "_Xã key": ten_xa,
            "TH TW": 0.0,
            "TH ĐP": 0.0,
            "Tổng TH": 0.0,
        }
        for stt, (ten_pgd, ten_xa) in enumerate(
            (
                (ten_pgd, ten_xa)
                for ten_pgd, ds_xa in dia_ban.items()
                for ten_xa in ds_xa
            ),
            start=1,
        )
    ]
    out = pd.DataFrame(rows)
    if out.empty or df_full is None or df_full.empty:
        return out

    required = {COT_TEN_PGD, COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON}
    if not required.issubset(df_full.columns):
        return out
    col_th = COT_TONG_DU_NO if COT_TONG_DU_NO in df_full.columns else (
        COT_DU_NO_TH if COT_DU_NO_TH in df_full.columns else None
    )
    if col_th is None:
        return out

    data = pd.DataFrame(
        {
            "_pgd": df_full[COT_TEN_PGD].map(_norm_xa_text),
            "_xa": df_full[COT_TEN_XA].map(_norm_xa_text),
            "_ma_ct": pd.to_numeric(df_full[COT_MA_CHUONG_TRINH], errors="coerce"),
            "_nv": pd.to_numeric(df_full[COT_NGUON_VON], errors="coerce"),
            "_th": pd.to_numeric(df_full[col_th], errors="coerce").fillna(0.0),
        }
    )
    if ma_ct_chon is None:
        data = data[data["_ma_ct"].isin(_ds_ma_ct_khtd_hien_thi())]
    else:
        data = data[data["_ma_ct"] == int(ma_ct_chon)]
    data = data[data["_nv"].isin([1, 2])]
    if data.empty:
        return out

    grouped = data.groupby(["_pgd", "_xa", "_nv"], dropna=False)["_th"].sum()
    for idx, row in out.iterrows():
        key_pgd = _norm_xa_text(row["PGD"])
        key_xa = _norm_xa_text(row["_Xã key"])
        th_tw = float(grouped.get((key_pgd, key_xa, 1), 0.0) or 0.0)
        th_dp = float(grouped.get((key_pgd, key_xa, 2), 0.0) or 0.0)
        out.at[idx, "TH TW"] = th_tw
        out.at[idx, "TH ĐP"] = th_dp
        out.at[idx, "Tổng TH"] = th_tw + th_dp
    return out


@st.cache_data(show_spinner=False, max_entries=_KHTD_CACHE_MAX_ENTRIES)
def _bang_thuc_hien_xa_theo_ct_cached(
    _df_full: "pd.DataFrame | None",
    ma_ct_chon: int | None,
    hstd_mtime: float = 0.0,
) -> pd.DataFrame:
    """Cache bảng TH 95 xã/phường theo chương trình và mtime HSTD."""
    _ = hstd_mtime
    return _tao_bang_thuc_hien_xa_theo_ct(_df_full, ma_ct_chon)


def _render_bang_thuc_hien_95_xa(
    df_full: "pd.DataFrame | None",
    kh_xa: dict[str, float] | None,
    username: str,
    co_quyen_nhap: bool,
) -> None:
    """Hiển thị/nhập kế hoạch toàn bộ xã/phường, có bộ lọc chương trình."""
    st.markdown("#### 📊 Kế hoạch và thực hiện 95 xã/phường theo chương trình")
    ds_ma_ct = _ds_ma_ct_khtd_hien_thi()
    ma_ct_chon = st.selectbox(
        "Chương trình",
        options=[None, *ds_ma_ct],
        format_func=lambda ma_ct: (
            "Tất cả chương trình"
            if ma_ct is None
            else f"{int(ma_ct):02d} — {_ten_ct_base(int(ma_ct))}"
        ),
        key="khtd_95_xa_ma_ct_filter",
    )

    df_bang = _bang_thuc_hien_xa_theo_ct_cached(
        df_full,
        ma_ct_chon,
        ts_file(CACHE_HSTD),
    )
    if df_bang.empty:
        st.warning("Chưa có danh mục xã/phường để tổng hợp.")
        return

    df_bang = _them_ke_hoach_vao_bang_xa(df_bang, kh_xa, ma_ct_chon)
    tong_kh = float(df_bang["Tổng KH"].sum())
    tong_th = float(df_bang["Tổng TH"].sum())
    ty_le = (tong_th / tong_kh * 100.0) if tong_kh > 1e-6 else None
    so_xa_co_th = int((df_bang["Tổng TH"] > 1e-6).sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tổng kế hoạch", f"{_fmt_vn(tong_kh / 1_000_000, d=0)} triệu đồng")
    m2.metric("Tổng thực hiện", f"{_fmt_vn(tong_th / 1_000_000, d=0)} triệu đồng")
    m3.metric("Tỷ lệ TH/KH", "—" if ty_le is None else f"{_fmt_vn(ty_le, d=2)}%")
    m4.metric("Xã/phường có thực hiện", f"{so_xa_co_th}/{len(df_bang)}")

    cot_hien_thi = [
        "STT", "PGD", "Xã/Phường",
        "KH TW", "TH TW", "KH ĐP", "TH ĐP", "Tổng KH", "Tổng TH", "TL %",
    ]
    col_cfg = {
        "STT": st.column_config.NumberColumn(width="small"),
        "PGD": st.column_config.TextColumn(width="medium"),
        "Xã/Phường": st.column_config.TextColumn(width="medium"),
        "KH TW": st.column_config.TextColumn("KH TW (triệu)"),
        "TH TW": st.column_config.TextColumn("TH TW (triệu)"),
        "KH ĐP": st.column_config.TextColumn("KH ĐP (triệu)"),
        "TH ĐP": st.column_config.TextColumn("TH ĐP (triệu)"),
        "Tổng KH": st.column_config.TextColumn("Tổng KH (triệu)"),
        "Tổng TH": st.column_config.TextColumn("Tổng TH (triệu)"),
        "TL %": st.column_config.TextColumn("TL %"),
    }

    df_view = df_bang[cot_hien_thi].copy()
    _ds_cot_tien = ["KH TW", "TH TW", "KH ĐP", "TH ĐP", "Tổng KH", "Tổng TH"]
    for col in _ds_cot_tien:
        _num_s = pd.to_numeric(df_view[col], errors="coerce").fillna(0.0) / 1_000_000
        df_view[col] = _num_s.map(lambda v: _fmt_vn(float(v), d=0))
    _tl_s = pd.to_numeric(df_view["TL %"], errors="coerce").fillna(0.0)
    df_view["TL %"] = _tl_s.map(lambda v: (f"{_fmt_vn(float(v), d=2)}%" if float(v) > 1e-9 or float(v) < -1e-9 else "—"))

    if co_quyen_nhap and ma_ct_chon is not None:
        keys_tw_luu = _ma_keys_khtd_theo_ct_nv(int(ma_ct_chon), 1)
        keys_dp_luu = _ma_keys_khtd_theo_ct_nv(int(ma_ct_chon), 2)
        st.dataframe(
            df_view,
            width='stretch',
            hide_index=True,
            height=360,
            column_config=col_cfg,
        )
        st.caption("Đơn vị nhập: triệu đồng. Các ô dưới đây là ô nhập thường, không bung editor khi click.")

        with st.form(f"khtd_95_xa_form_{int(ma_ct_chon)}"):
            st.markdown("##### Nhập kế hoạch 95 xã/phường")
            header = st.columns([0.6, 2.1, 2.3, 1.2, 1.2, 1.2, 1.2])
            for col, text in zip(header, ["STT", "PGD", "Xã/Phường", "KH TW", "TH TW", "KH ĐP", "TH ĐP"]):
                col.markdown(f"**{text}**")

            gia_tri_sua: dict[tuple[int, str], tuple[float, float]] = {}
            for idx, row in df_bang.reset_index(drop=True).iterrows():
                row_cols = st.columns([0.6, 2.1, 2.3, 1.2, 1.2, 1.2, 1.2])
                row_cols[0].markdown(str(row["STT"]))
                row_cols[1].markdown(str(row["PGD"]))
                row_cols[2].markdown(str(row["Xã/Phường"]))
                kh_tw_trieu = float(row.get("KH TW", 0.0) or 0.0) / 1_000_000
                kh_dp_trieu = float(row.get("KH ĐP", 0.0) or 0.0) / 1_000_000
                th_tw_trieu = float(row.get("TH TW", 0.0) or 0.0) / 1_000_000
                th_dp_trieu = float(row.get("TH ĐP", 0.0) or 0.0) / 1_000_000
                key_tw = f"khtd_95_xa_inp_{int(ma_ct_chon)}_{idx}_tw"
                key_dp = f"khtd_95_xa_inp_{int(ma_ct_chon)}_{idx}_dp"
                if keys_tw_luu:
                    kh_tw_moi = _render_trieu_text_input(
                        row_cols[3],
                        label=f"KH TW {row['Xã/Phường']}",
                        widget_key=key_tw,
                        value_trieu=kh_tw_trieu,
                        help_text="Kế hoạch TW, đơn vị triệu đồng",
                    )
                else:
                    kh_tw_moi = 0.0
                    row_cols[3].caption("—")
                row_cols[4].markdown(f"<div class='khtd-amount'>{_fmt_vn(th_tw_trieu, 0)}</div>", unsafe_allow_html=True)
                if keys_dp_luu:
                    kh_dp_moi = _render_trieu_text_input(
                        row_cols[5],
                        label=f"KH ĐP {row['Xã/Phường']}",
                        widget_key=key_dp,
                        value_trieu=kh_dp_trieu,
                        help_text="Kế hoạch ĐP, đơn vị triệu đồng",
                    )
                else:
                    kh_dp_moi = 0.0
                    row_cols[5].caption("—")
                row_cols[6].markdown(f"<div class='khtd-amount'>{_fmt_vn(th_dp_trieu, 0)}</div>", unsafe_allow_html=True)
                gia_tri_sua[(idx, str(row.get("_Xã key", "")))] = (kh_tw_moi, kh_dp_moi)

            luu_nhanh = st.form_submit_button("💾 Lưu kế hoạch 95 xã/phường", type="primary")

        if luu_nhanh:
            kh_moi = dict(kh_xa or {})
            for idx, row in df_bang.reset_index(drop=True).iterrows():
                ten_xa_key = str(row.get("_Xã key", row.get("Xã/Phường", "")) or "").strip()
                kh_tw_moi, kh_dp_moi = gia_tri_sua.get((idx, ten_xa_key), (0.0, 0.0))
                _phan_bo_kh_xa_theo_keys(
                    kh_moi,
                    ten_xa_key,
                    keys_tw_luu,
                    kh_tw_moi * 1_000_000,
                )
                _phan_bo_kh_xa_theo_keys(
                    kh_moi,
                    ten_xa_key,
                    keys_dp_luu,
                    kh_dp_moi * 1_000_000,
                )
            if _luu_kv(KV_KEY_XA, kh_moi, username):
                db.ghi_audit(
                    username,
                    "luu_khtd_xa",
                    f"Nhập nhanh 95 xã/phường — CT {int(ma_ct_chon):02d}",
                )
                st.success("Đã lưu kế hoạch 95 xã/phường.")
                st.rerun()
    else:
        if ma_ct_chon is None:
            st.caption("Chọn một chương trình cụ thể để nhập và lưu kế hoạch cho 95 xã/phường.")
        elif not co_quyen_nhap:
            st.caption("Anh/chị có thể xem KH/TH; chỉ Admin / Manager mới được nhập kế hoạch.")
        st.dataframe(
            df_view,
            width='stretch',
            hide_index=True,
            height=560,
            column_config=col_cfg,
        )
    st.caption(
        f"Hiển thị đủ **{len(df_bang)} xã/phường** theo danh mục địa bàn; "
        "xã chưa phát sinh vẫn được giữ lại với giá trị 0."
    )

    df_excel = df_bang[cot_hien_thi].copy()
    for col in ["KH TW", "TH TW", "KH ĐP", "TH ĐP", "Tổng KH", "Tổng TH"]:
        df_excel[col] = df_excel[col] / 1_000_000
    st.download_button(
        "⬇️ Tải bảng KH/TH 95 xã/phường",
        data=xuat_excel({"TH theo xã": df_excel}),
        file_name=ten_file_xuat(
            "KH_TH_KHTD_95_Xa"
            if ma_ct_chon is None
            else f"KH_TH_KHTD_95_Xa_CT_{int(ma_ct_chon):02d}"
        ),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="khtd_95_xa_download",
    )


@st.cache_data(show_spinner=False, max_entries=_KHTD_CACHE_MAX_ENTRIES)
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
    co_quyen = get_permissions(role)["can_edit_khtd"]
    kh_cn = _dong_bo_nsvsmt_dp_keys(_doc_kv(KV_KEY_CN))
    hstd_mtime = ts_file(CACHE_HSTD)
    gqvl_mtime = ts_file(CACHE_GQVL)
    rules_key = _ndt_dp_rules_cache_key()
    th_cn, th_gqvl = _tinh_th_cn_cached(df_full, df_gqvl, hstd_mtime, gqvl_mtime, rules_key)

    if not co_quyen:
        st.info("🔒 Chế độ xem — chỉ Admin / Manager mới được nhập kế hoạch.")
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

    # ── Banner trạng thái ────────────────────────────────────────────────────
    tong_ct = len(MA_KEYS_CO_KHTD)
    so_ct_co_kh = sum(
        1 for mk in MA_KEYS_CO_KHTD if float(kh_cn.get(mk, 0.0)) > 0
    )
    tong_kh_trieu = (
        sum(float(kh_cn.get(mk, 0.0)) for mk in MA_KEYS_CO_KHTD) / 1e6
    )
    tong_kh_ty = tong_kh_trieu / 1000.0

    if so_ct_co_kh == 0:
        mau, vien, icon = "rgba(245,158,11,0.12)", "#f59e0b", "🔴"
        noi_dung = f"Chưa có kế hoạch — 0/{tong_ct} chương trình"
    elif so_ct_co_kh < tong_ct:
        mau, vien, icon = "rgba(249,115,22,0.12)", "#f97316", "🟡"
        noi_dung = (
            f"Đã nhập {so_ct_co_kh}/{tong_ct} chương trình · "
            f"Tổng KH: {_fvn(tong_kh_trieu, 0)} triệu đồng"
        )
    else:
        mau, vien, icon = "rgba(34,197,94,0.12)", "#22c55e", "🟢"
        noi_dung = (
            f"Đã nhập đủ {tong_ct}/{tong_ct} chương trình · "
            f"Tổng KH: {_fvn(tong_kh_ty, 3)} tỷ đồng"
        )

    st.markdown(
        f"<div style='padding:10px 16px;background:{mau};border-left:4px solid {vien};"
        f"border-radius:6px;font-size:0.9rem;font-weight:500;margin-bottom:4px'>"
        f"{icon} {noi_dung}</div>",
        unsafe_allow_html=True,
    )

    # ── Tóm tắt hiện trạng (expander — tránh trùng lặp với editor) ──────────
    df_loc = df_full
    with st.expander("📊 Tóm tắt hiện trạng (KH vs TH toàn chi nhánh)", expanded=False):
        nv_chon = st.radio(
            "Nguồn vốn",
            ["Tất cả", "Trung ương", "Địa phương"],
            horizontal=True,
            key="khtd_cn_nv_radio",
        )
        ds_ct, ten_map_q = _du_lieu_hien_thi_khtd_cn_cached(
            df_loc,
            nv_chon,
            tuple(sorted(set(kh_cn.keys()) | set(th_cn.keys()))),
            hstd_mtime,
        )
        from tabs.tab_khtd_xuat import _hien_thi_bang_cn_readonly  # lazy – tránh circular import
        _hien_thi_bang_cn_readonly(
            kh_cn,
            th_cn,
            ds_ct_loc=[mk for mk, _ in ds_ct],
            df_loc=df_loc,
            th_gqvl=th_gqvl,
            username=username,
        )

    # ten_map cho editor (không phụ thuộc filter)
    _, ten_map_q = _du_lieu_hien_thi_khtd_cn_cached(
        df_loc, "Tất cả",
        tuple(sorted(set(kh_cn.keys()) | set(th_cn.keys()))),
        hstd_mtime,
    )

    # ── Nhập kế hoạch (trung tâm) ────────────────────────────────────────────
    st.markdown("##### ✏️ Nhập kế hoạch")
    st.caption("Đơn vị: triệu đồng (số nguyên) · TH tự tính từ HSTD · GQVL tách 4 dòng TW/ĐP")
    draft_cn = st.session_state.get("khtd_cn_editor_draft", {})
    df_editor_meta = _tao_bang_nhap_khtd_cn(kh_cn, th_cn, th_gqvl, ten_map_q, draft_cn)
    df_editor_view = _tao_view_editor_khtd_cn(df_editor_meta)
    patch_hien_tai = _trich_patch_khtd_cn_tu_bang(df_editor_meta, df_editor_meta)

    df_editor = st.data_editor(
        df_editor_view,
        key="khtd_cn_editor",
        hide_index=True,
        width='stretch',
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
        bo_nhap = st.button("↺ Khôi phục số đã lưu", key="khtd_cn_reset_draft", width='stretch')
    with col_f2:
        luu = st.button("💾 Lưu kế hoạch Chi nhánh", key="khtd_cn_save_btn", type="primary", width='stretch')

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
                    width='stretch',
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

    for _, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
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
            html_rows.append(f"<tr>{tds}</tr>")

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


def _reset_khtd_xa_selection_if_stale(danh_sach_xa: list[str]) -> None:
    """Xóa xã đã lưu nếu không còn thuộc danh sách xã hiện tại."""
    xa_luu = st.session_state.get("khtd_xa_xa_sel")
    if xa_luu is not None and xa_luu not in danh_sach_xa:
        st.session_state.pop("khtd_xa_xa_sel", None)


def _tab_khtd_theo_xa(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    co_quyen = get_permissions(role)["can_edit_khtd"]
    kh_xa = _doc_kv(KV_KEY_XA)
    _render_bang_thuc_hien_95_xa(df_full, kh_xa, username, co_quyen)
    st.divider()
    if not co_quyen:
        st.info("🔒 Anh/chị có thể xem số thực hiện; chỉ Admin / Manager mới được nhập kế hoạch theo Xã.")
        return

    st.markdown("#### ✏️ Nhập kế hoạch từng xã/phường")

    # ── Chọn PGD + Xã ──────────────────────────────────────────────────────
    with st.container(border=True):
        st.caption("🏢 Đơn vị đang làm việc")
        col_pgd, col_xa = st.columns(2)
        with col_pgd:
            pgd_chon = st.selectbox("PGD", DS_PGD, key="khtd_xa_pgd_sel")
        danh_sach_xa = PGD_XA_MAP.get(pgd_chon, [])
        if not danh_sach_xa:
            st.warning(f"Chưa có danh sách xã cho **{pgd_chon}**.")
            return

        _reset_khtd_xa_selection_if_stale(danh_sach_xa)

        with col_xa:
            xa_chon = st.selectbox("Xã/Phường", danh_sach_xa, key="khtd_xa_xa_sel")

    # ── Toolbar: Xuất file & Upload hàng loạt ──────────────────────────────
    with st.container(border=True):
        st.caption("📤 Xuất & 📥 Nhập kế hoạch hàng loạt")
        tab_xuat, tab_nhap = st.tabs(["📤 Xuất kế hoạch", "📥 Nhập kế hoạch"])
        with tab_xuat:
            _col_x1, _col_x2 = st.columns([1, 1])
            with _col_x1:
                if st.button("📥 Xuất Excel tất cả xã", width='stretch', key="xuat_excel_tat_ca_xa"):
                    kh_xa_ex = _doc_kv(KV_KEY_XA) or {}
                    sheets: dict[str, pd.DataFrame] = {}
                    rows_th = []

                    _stt_pgd, _, _ = _stt_pgd_xa(pgd_chon, None)
                    ds_xa_chuan: list[tuple[str, str]] | None = None
                    for _stt_p, _ten_p, _dxs in _PGD_XA_STT_CHUAN:
                        if _stt_p == _stt_pgd:
                            ds_xa_chuan = list(_dxs)
                            break

                    def _stt_xa_so(xa_name: str) -> str:
                        if not ds_xa_chuan:
                            return ""
                        norm_fn = lambda s: re.sub(r"\s+", " ", str(s or "").strip().lower()).replace("xã ", "").replace("phường ", "")
                        xn = norm_fn(xa_name)
                        for sx, tx in ds_xa_chuan:
                            if norm_fn(tx) == xn:
                                return sx
                        return ""

                    for ten_xa in danh_sach_xa:
                        kh_tw = sum(
                            kh_xa_ex.get(f"{ten_xa}|{mk}", 0)
                            for mk in MA_KEYS_CO_KHTD if mk.endswith("_TW")
                        ) / 1e6
                        kh_dp = sum(
                            kh_xa_ex.get(f"{ten_xa}|{mk}", 0)
                            for mk in MA_KEYS_CO_KHTD if mk.endswith("_DP")
                        ) / 1e6
                        tong_kh = kh_tw + kh_dp
                        sx = _stt_xa_so(ten_xa)
                        stt_full = f"{_stt_pgd}.{sx}" if sx and _stt_pgd else ""
                        rows_th.append({
                            "STT": stt_full,
                            "Xã/Phường": ten_xa,
                            "KH TW (triệu)": round(kh_tw, 1),
                            "KH ĐP (triệu)": round(kh_dp, 1),
                            "Tổng KH (triệu)": round(tong_kh, 1),
                        })
                    if rows_th:
                        df_th = pd.DataFrame(rows_th)
                        tong_row = {
                            "STT": "",
                            "Xã/Phường": "Tổng cộng",
                            "KH TW (triệu)": round(df_th["KH TW (triệu)"].sum(), 1),
                            "KH ĐP (triệu)": round(df_th["KH ĐP (triệu)"].sum(), 1),
                            "Tổng KH (triệu)": round(df_th["Tổng KH (triệu)"].sum(), 1),
                        }
                        df_th = pd.concat([df_th, pd.DataFrame([tong_row])], ignore_index=True)
                        sheets["Tổng hợp PGD"] = df_th

                    for ten_xa in danh_sach_xa:
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
                                    kh = kh_xa_ex.get(f"{ten_xa}|{mk}", 0) / 1e6
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
                            sx = _stt_xa_so(ten_xa)
                            label_sheet = f"{_stt_pgd}-{sx} {ten_xa}" if (sx and _stt_pgd) else ten_xa
                            ten_sheet = _clean_sheet_name(label_sheet)
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
                            width='stretch',
                            type="primary",
                        )
                    else:
                        st.info("Chưa có dữ liệu kế hoạch để xuất.")
            with _col_x2:
                st.info("**File xuất Excel chứa:**\n- 1 sheet **Tổng hợp PGD** (cột STT I.1 I.2… theo chuẩn hành chính)\n- 1 sheet riêng từng xã (tên sheet format `I-1 Phường Phước Tân` để sắp xếp đúng thứ tự)")

        with tab_nhap:
            _col_n1, _col_n2 = st.columns([1, 1])
            with _col_n1:
                try:
                    _xa_mau = danh_sach_xa[0] if danh_sach_xa else "Xã mẫu"
                    _mk_hien = [mk for mk in MA_KEYS_CO_KHTD if mk.endswith("_TW")][:3] or list(MA_KEYS_CO_KHTD)[:3]
                    _rows_mau = []
                    for mk in _mk_hien:
                        _rows_mau.append({
                            "Tên xã": _xa_mau,
                            "Mã CT": mk,
                            "Giá trị (triệu đồng)": 0,
                        })
                    _df_mau = pd.DataFrame(_rows_mau)
                    _mau_bytes = xuat_excel({"Mẫu KHTD Xã": _df_mau})
                    st.download_button(
                        "📋 Tải mẫu Excel nhập",
                        data=_mau_bytes,
                        file_name=ten_file_xuat(f"Mau_KHTD_Xa_{pgd_slug(pgd_chon)}"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="khtd_xa_mau_dl",
                        width='stretch',
                        help="Mẫu 3 cột chuẩn upload — điền thêm dòng theo đúng cột rồi upload lại",
                    )
                except Exception as _e:
                    logger.warning("Tao mau Excel KHTD xa bi loi: %s", _e)
                    st.caption("⚠️ Không tạo được mẫu (chưa cần khẩn cấp — upload vẫn OK)")
            with _col_n2:
                st.info(
                    "**Cấu trúc file nhập (BẮT BUỘC 3 cột):**\n"
                    "- `Cột A` **Tên xã** (phải trùng khớp trong danh sách xã của PGD, ví dụ: Phường Phước Tân)\n"
                    "- `Cột B` **Mã CT** (mã key KHTD — ví dụ `2_TW`, `1_DP`; xóa các dòng bạn không cần điền)\n"
                    "- `Cột C` **Giá trị (triệu đồng)** (số nguyên, đơn vị triệu — không có dấu chấm phẩy/thưc đồng)"
                )
            file_up = st.file_uploader(
                "Upload Excel hàng loạt",
                type=["xlsx", "xls"],
                key="khtd_xa_file_upload",
                help="File 3 cột Tên xã | Mã CT | Giá trị (triệu đồng) — các dòng xã không thuộc PGD này sẽ bị báo cảnh báo và bỏ qua",
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

    # ── PDF export (đơn xã + tất cả 95 xã) ─────────────────────────────────
    with st.container(border=True):
        st.caption("🖨️ Xuất báo cáo PDF")
        st.session_state.setdefault("khtd_pdf_folder", "")
        col_path, col_btn1, col_btn2 = st.columns([3, 1, 1])
        with col_path:
            pdf_folder = st.text_input(
                "📁 Thư mục lưu PDF",
                value=st.session_state["khtd_pdf_folder"],
                placeholder="Để trống nếu muốn tải về thay vì lưu file",
                help="VD: C:\\KHTD_PDF\\",
                key="khtd_pdf_folder_input",
            )
            st.session_state["khtd_pdf_folder"] = pdf_folder
        with col_btn1:
            st.markdown("<br>", unsafe_allow_html=True)
            xuat_pdf_clicked = st.button("🖨️ Xuất PDF xã", width='stretch', type="primary", key="khtd_xuat_pdf")
        with col_btn2:
            st.markdown("<br>", unsafe_allow_html=True)
            xuat_pdf_95_clicked = st.button("📚 Xuất PDF 95 xã", width='stretch', type="secondary", key="khtd_xuat_pdf_95_xa",
                                            help="Gom toàn bộ 95 xã/phường của 22 PGD theo đúng thứ tự chuẩn I..XXII vào 1 file PDF.")
        st.caption("📌 Đơn vị hiển thị trong bảng / PDF: **triệu đồng**")

    hstd_mtime = ts_file(CACHE_HSTD)
    rules_key = _ndt_dp_rules_cache_key()
    th_xa, ten_map_q, keys_phat_sinh = _du_lieu_khtd_xa_cached(
        df_full,
        pgd_chon,
        xa_chon,
        hstd_mtime,
        rules_key,
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

    _colw_xa = [3, 1, 1, 1, 1, 1, 1]  # Chương trình | KH TW | TH TW | Còn TW | KH ĐP | TH ĐP | Còn ĐP

    _ths_xa = (
        "font-size:0.72rem;font-weight:700;text-align:center;text-transform:uppercase;"
        "letter-spacing:0.3px;padding:6px;border-radius:4px;white-space:nowrap"
    )
    st.markdown(
        f"""
<table style="width:100%;border-collapse:separate;border-spacing:2px;
  table-layout:fixed;margin:4px 0 2px">
<colgroup>
  <col style="width:37%">
  <col style="width:10.5%"><col style="width:10.5%"><col style="width:10.5%">
  <col style="width:10.5%"><col style="width:10.5%"><col style="width:10.5%">
</colgroup>
<tr>
  <th style="{_ths_xa}"></th>
  <th colspan="3" style="{_ths_xa};background:rgba(59,130,246,0.15);color:#3b82f6">Nguồn vốn Trung ương</th>
  <th colspan="3" style="{_ths_xa};background:rgba(34,197,94,0.15);color:#22c55e">Nguồn vốn Địa phương</th>
</tr>
<tr>
  <th style="{_ths_xa};text-align:left;padding-left:10px">Chương trình</th>
  <th style="{_ths_xa}">Kế hoạch</th>
  <th style="{_ths_xa}">Thực hiện</th>
  <th style="{_ths_xa}">Còn phải TH</th>
  <th style="{_ths_xa}">Kế hoạch</th>
  <th style="{_ths_xa}">Thực hiện</th>
  <th style="{_ths_xa}">Còn phải TH</th>
</tr>
</table>""",
        unsafe_allow_html=True,
    )

    # ── Tổng cộng (4 thẻ KPI theo chuẩn delta_card / kpi_row) ───────────────
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
    _pct_tw = round(tong_th_tw / tong_kh_tw * 100, 1) if tong_kh_tw > 0 else None
    _pct_dp = round(tong_th_dp / tong_kh_dp * 100, 1) if tong_kh_dp > 0 else None
    _delta_tw = None
    if tong_kh_tw > 0:
        _delta_tw = round((tong_th_tw - tong_kh_tw) / tong_kh_tw * 100, 1)
    _delta_dp = None
    if tong_kh_dp > 0:
        _delta_dp = round((tong_th_dp - tong_kh_dp) / tong_kh_dp * 100, 1)

    _kh_tw_co_gia_tri = tong_kh_tw > 1e-6
    _kh_dp_co_gia_tri = tong_kh_dp > 1e-6
    _th_tw_co_gia_tri = tong_th_tw > 1e-6
    _th_dp_co_gia_tri = tong_th_dp > 1e-6

    _value_kh_tw  = _fmt_vn(tong_kh_tw, d=1) if _kh_tw_co_gia_tri else "— Chưa có"
    _value_th_tw  = _fmt_vn(tong_th_tw, d=1) if _th_tw_co_gia_tri else "— Chưa có"
    _value_kh_dp  = _fmt_vn(tong_kh_dp, d=1) if _kh_dp_co_gia_tri else "— Chưa có"
    _value_th_dp  = _fmt_vn(tong_th_dp, d=1) if _th_dp_co_gia_tri else "— Chưa có"

    _sub_kh_tw  = (
        f"TH: {_fmt_vn(tong_th_tw, d=1)} tr · Đạt: {_fmt_vn(_pct_tw, d=1)}%" if _pct_tw is not None
        else (
            f"TH: {_fmt_vn(tong_th_tw, d=1)} tr" if _th_tw_co_gia_tri
            else "⚠️ Chưa nhập kế hoạch — nhập giá trị bên dưới rồi 💾 Lưu"
        )
    )
    _sub_kh_dp  = (
        f"TH: {_fmt_vn(tong_th_dp, d=1)} tr · Đạt: {_fmt_vn(_pct_dp, d=1)}%" if _pct_dp is not None
        else (
            f"TH: {_fmt_vn(tong_th_dp, d=1)} tr" if _th_dp_co_gia_tri
            else "⚠️ Chưa nhập kế hoạch — nhập giá trị bên dưới rồi 💾 Lưu"
        )
    )
    _sub_th_tw  = (
        None if _delta_tw is None
        else ("Chênh: +" if _delta_tw>=0 else "Chênh: ") + f"{_fmt_vn(_delta_tw, d=1)}% KH"
    )
    _sub_th_dp  = (
        None if _delta_dp is None
        else ("Chênh: +" if _delta_dp>=0 else "Chênh: ") + f"{_fmt_vn(_delta_dp, d=1)}% KH"
    )
    _suffix_kh_tw = "triệu đ" if _kh_tw_co_gia_tri else ""
    _suffix_th_tw = "triệu đ" if _th_tw_co_gia_tri else ""
    _suffix_kh_dp = "triệu đ" if _kh_dp_co_gia_tri else ""
    _suffix_th_dp = "triệu đ" if _th_dp_co_gia_tri else ""

    st.markdown("###### 📊 Tổng cộng kế hoạch & thực hiện xã")
    kpi_row(
        [
            dict(
                label="Kế hoạch Trung ương",
                value=_value_kh_tw,
                suffix=_suffix_kh_tw,
                icon="🏛️",
                help="Tổng kế hoạch nguồn vốn Trung ương của xã (triệu đồng)",
                sub=_sub_kh_tw,
            ),
            dict(
                label="Thực hiện Trung ương",
                value=_value_th_tw,
                suffix=_suffix_th_tw,
                icon="✅",
                delta=_pct_tw if _pct_tw is not None else None,
                delta_label="% kế hoạch",
                delta_color="normal" if (_pct_tw is None or _pct_tw < 100) else "inverse",
                help="Tổng giải ngân/thu nợ nguồn TW năm nay",
                sub=_sub_th_tw,
            ),
            dict(
                label="Kế hoạch Địa phương",
                value=_value_kh_dp,
                suffix=_suffix_kh_dp,
                icon="🏘️",
                help="Tổng kế hoạch nguồn vốn Địa phương của xã (triệu đồng)",
                sub=_sub_kh_dp,
            ),
            dict(
                label="Thực hiện Địa phương",
                value=_value_th_dp,
                suffix=_suffix_th_dp,
                icon="✅",
                delta=_pct_dp if _pct_dp is not None else None,
                delta_label="% kế hoạch",
                delta_color="normal" if (_pct_dp is None or _pct_dp < 100) else "inverse",
                help="Tổng giải ngân/thu nợ nguồn ĐP năm nay",
                sub=_sub_th_dp,
            ),
        ],
        num_columns=4,
    )

    # ── CSS cho lưới nhập — chỉ dùng custom class, KHÔNG selector global ──
    st.markdown("##### ✏️ Nhập kế hoạch xã")
    st.markdown(
        """
<style>
.khtd-program-name {
    font-size: 0.92rem;
    font-weight: 500;
    padding: 8px 0;
    line-height: 1.35;
}
.khtd-amount {
    font-size: 0.95rem;
    font-weight: 600;
    padding: 8px 0;
    font-variant-numeric: tabular-nums;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # ── Nhóm màu nền (rgba — tương thích dark mode) ──
    nhom_mau_nen = [
        "rgba(59,130,246,0.10)",
        "rgba(34,197,94,0.10)",
        "rgba(245,158,11,0.10)",
    ]
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
                f"background-color:{bg};border-radius:6px;font-weight:600;"
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
                    f"{_fmt_vn(trieu_tw, d=1)} tr" if trieu_tw > 1e-6 else "—"
                )
                cols[2].markdown(
                    f"<div class='khtd-amount' style='text-align:right'>"
                    f"{txt_th_tw}</div>",
                    unsafe_allow_html=True,
                )

                # —— Cột Còn TW (cols[3]) ——
                if co_tw:
                    _kh_trieu_new = float(gia_tri_moi.get(khoa_tw, 0.0) or 0.0)
                    _con_trieu_tw = max(_kh_trieu_new - trieu_tw, 0.0)
                    if _kh_trieu_new <= 1e-6 and trieu_tw <= 1e-6:
                        _txt_con_tw = "—"
                        _color_tw = "inherit"
                    else:
                        _txt_con_tw = f"{_fmt_vn(_con_trieu_tw, d=1)} tr"
                        if trieu_tw - _kh_trieu_new > 1e-3:  # TH vượt KH
                            _color_tw = "#dc2626"
                        elif _con_trieu_tw <= 1e-6:  # TH đủ / vượt
                            _color_tw = "#16a34a"
                        else:
                            _color_tw = "inherit"
                    _tooltip_tw = f"Còn = Kế hoạch ({_fmt_vn(_kh_trieu_new, d=1)} tr) - Thực hiện ({_fmt_vn(trieu_tw, d=1)} tr)"
                    cols[3].markdown(
                        f"<div class='khtd-amount' style='text-align:right;color:{_color_tw}' title='{_tooltip_tw}'>"
                        f"{_txt_con_tw}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    cols[3].caption("—")

                if co_dp:
                    gia_tri_moi[khoa_dp] = cols[4].number_input(
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
                    cols[4].caption("—")

                vnd_dp = float(th_xa.get(mk_dp, 0.0) or 0.0)
                trieu_dp = vnd_dp / 1e6
                txt_th_dp = (
                    f"{_fmt_vn(trieu_dp, d=1)} tr" if trieu_dp > 1e-6 else "—"
                )
                cols[5].markdown(
                    f"<div class='khtd-amount' style='text-align:right'>"
                    f"{txt_th_dp}</div>",
                    unsafe_allow_html=True,
                )

                # —— Cột Còn ĐP (cols[6]) ——
                if co_dp:
                    _kh_trieu_new_dp = float(gia_tri_moi.get(khoa_dp, 0.0) or 0.0)
                    _con_trieu_dp = max(_kh_trieu_new_dp - trieu_dp, 0.0)
                    if _kh_trieu_new_dp <= 1e-6 and trieu_dp <= 1e-6:
                        _txt_con_dp = "—"
                        _color_dp = "inherit"
                    else:
                        _txt_con_dp = f"{_fmt_vn(_con_trieu_dp, d=1)} tr"
                        if trieu_dp - _kh_trieu_new_dp > 1e-3:
                            _color_dp = "#dc2626"
                        elif _con_trieu_dp <= 1e-6:
                            _color_dp = "#16a34a"
                        else:
                            _color_dp = "inherit"
                    _tooltip_dp = f"Còn = Kế hoạch ({_fmt_vn(_kh_trieu_new_dp, d=1)} tr) - Thực hiện ({_fmt_vn(trieu_dp, d=1)} tr)"
                    cols[6].markdown(
                        f"<div class='khtd-amount' style='text-align:right;color:{_color_dp}' title='{_tooltip_dp}'>"
                        f"{_txt_con_dp}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    cols[6].caption("—")

        # ── Xuất PDF nếu được yêu cầu ──────────────────────────────────────
        if xuat_pdf_clicked:
            # --- Build PDF data: KH + TH + Còn + % ---
            _PDF_COLS = [
                "STT", "Chương trình",
                "KH TW", "TH TW", "Còn TW", "Đạt TW%",
                "KH ĐP", "TH ĐP", "Còn ĐP", "Đạt ĐP%",
            ]
            _COLS_TIEN = ["KH TW", "TH TW", "Còn TW", "KH ĐP", "TH ĐP", "Còn ĐP"]
            _COLS_PCT  = ["Đạt TW%", "Đạt ĐP%"]
            pdf_data: list[dict] = []
            stt = 1

            # Running tổng (trieu dong) for weighted %
            _s_kh_tw = _s_th_tw = 0.0
            _s_kh_dp = _s_th_dp = 0.0

            for _tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
                for ma_ct in ds_ma_ct:
                    mk_tw = f"{ma_ct}_TW"
                    mk_dp = f"{ma_ct}_DP"
                    khoa_tw = f"{xa_chon}|{mk_tw}"
                    khoa_dp = f"{xa_chon}|{mk_dp}"

                    # KH — triệu đồng (lấy từ draft trước khi user submit)
                    kh_tw_vnd = float(gia_tri_moi.get(khoa_tw, kh_xa.get(khoa_tw, 0.0)) or 0.0)
                    kh_dp_vnd = float(gia_tri_moi.get(khoa_dp, kh_xa.get(khoa_dp, 0.0)) or 0.0)
                    kh_tw = kh_tw_vnd / 1_000_000          # triệu
                    kh_dp = kh_dp_vnd / 1_000_000

                    # TH — triệu đồng (từ HSTD/GQVL đã tính ở th_xa)
                    th_tw_vnd = float(th_xa.get(mk_tw, 0.0) or 0.0)
                    th_dp_vnd = float(th_xa.get(mk_dp, 0.0) or 0.0)
                    th_tw = th_tw_vnd / 1_000_000
                    th_dp = th_dp_vnd / 1_000_000

                    # Bỏ qua nếu cả 2 nguồn đều không có KH và không có TH
                    if kh_tw <= 0 and th_tw <= 0 and kh_dp <= 0 and th_dp <= 0:
                        continue

                    # Còn lại KH - TH (không âm)
                    con_tw = max(kh_tw - th_tw, 0.0)
                    con_dp = max(kh_dp - th_dp, 0.0)

                    # Tỷ lệ Đạt = TH / KH * 100 (nếu KH = 0 → None)
                    dat_tw_pct = (th_tw / kh_tw * 100.0) if kh_tw > 0 else None
                    dat_dp_pct = (th_dp / kh_dp * 100.0) if kh_dp > 0 else None

                    ten_ct = _ten_ct_base(ma_ct, ten_map_q)
                    row: dict = {
                        "STT": stt,
                        "Chương trình": ten_ct,
                        "KH TW": round(kh_tw, 1) if kh_tw > 0 else None,
                        "TH TW": round(th_tw, 1) if th_tw > 0 else None,
                        "Còn TW": round(con_tw, 1) if con_tw > 0 else None,
                        "Đạt TW%": round(dat_tw_pct, 1) if dat_tw_pct is not None else None,
                        "KH ĐP": round(kh_dp, 1) if kh_dp > 0 else None,
                        "TH ĐP": round(th_dp, 1) if th_dp > 0 else None,
                        "Còn ĐP": round(con_dp, 1) if con_dp > 0 else None,
                        "Đạt ĐP%": round(dat_dp_pct, 1) if dat_dp_pct is not None else None,
                    }
                    pdf_data.append(row)
                    stt += 1

                    # Cộng dồn cho tổng cuối bảng
                    if kh_tw > 0: _s_kh_tw += kh_tw
                    if th_tw > 0: _s_th_tw += th_tw
                    if kh_dp > 0: _s_kh_dp += kh_dp
                    if th_dp > 0: _s_th_dp += th_dp

            if pdf_data:
                df_pdf = pd.DataFrame(pdf_data, columns=_PDF_COLS)

                # --- Dòng TỔNG CỘNG cuối bảng ---
                _s_con_tw = max(_s_kh_tw - _s_th_tw, 0.0)
                _s_con_dp = max(_s_kh_dp - _s_th_dp, 0.0)
                _s_dat_tw_pct = (_s_th_tw / _s_kh_tw * 100.0) if _s_kh_tw > 0 else None
                _s_dat_dp_pct = (_s_th_dp / _s_kh_dp * 100.0) if _s_kh_dp > 0 else None
                dong_tong: dict[str, object] = {
                    "STT": "",
                    "Chương trình": "TỔNG CỘNG",
                    "KH TW":  round(_s_kh_tw, 1),
                    "TH TW":  round(_s_th_tw, 1),
                    "Còn TW": round(_s_con_tw, 1),
                    "Đạt TW%": round(_s_dat_tw_pct, 1) if _s_dat_tw_pct is not None else None,
                    "KH ĐP":  round(_s_kh_dp, 1),
                    "TH ĐP":  round(_s_th_dp, 1),
                    "Còn ĐP": round(_s_con_dp, 1),
                    "Đạt ĐP%": round(_s_dat_dp_pct, 1) if _s_dat_dp_pct is not None else None,
                }

                ngay_hien_tai = datetime.now().strftime("%d/%m/%Y")
                _stt_p, _stt_x, _so_tieu_de = _stt_pgd_xa(pgd_chon, xa_chon)
                tieu_de     = f"KẾ HOẠCH TÍN DỤNG — {_so_tieu_de.upper()}" if _so_tieu_de else f"KẾ HOẠCH TÍN DỤNG — XÃ {xa_chon.upper()}"
                tieu_de_phu = f"Ngày {ngay_hien_tai}"

                try:
                    pdf_bytes = xuat_pdf_bang(
                        df_pdf,
                        tieu_de,
                        tieu_de_phu,
                        nguoi_xuat=username,
                        cols_tien=_COLS_TIEN,
                        cols_percent=_COLS_PCT,
                        don_vi_tien="triệu đồng",
                        dong_tong=dong_tong,
                        them_dong_tong=True,
                        prefix_file="KHTD",
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
                            logger.error("Lỗi lưu PDF KHTD xã: %s", _e, exc_info=True)
                            st.warning(f"⚠️ Không lưu được PDF vào thư mục: {_e}")

                    state = SCMStateManager()
                    state.downloads.set(
                        "khtd_xa_pdf",
                        pdf_bytes,
                        f"KHTD_{xa_chon}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    )
                    db.ghi_audit(username, "xuat_bieu_cn",
                                 f"KHTD xã (PDF mới) — PGD: {pgd_chon} — Xã: {xa_chon}")

                except Exception as e:
                    logger.error("Lỗi xuất PDF KHTD xã: %s", e, exc_info=True)
                    SCMStateManager().downloads.clear("khtd_xa_pdf")
                    st.error(f"Lỗi xuất PDF: {e}")
            else:
                st.warning("Không có dữ liệu kế hoạch hoặc thực hiện để xuất PDF.")
                SCMStateManager().downloads.clear("khtd_xa_pdf")

        if xuat_pdf_95_clicked:
            with st.spinner("📚 Đang xây PDF tổng hợp 95 xã/phường 22 PGD (chờ ~30-90 giây)..."):
                try:
                    kh_xa_full_95 = _doc_kv(KV_KEY_XA) or {}
                    hstd_mt = ts_file(CACHE_HSTD)
                    rules_k = _ndt_dp_rules_cache_key()
                    pdf_bytes_95 = _xuat_pdf_tat_ca_95_xa_bytes(
                        df_full, kh_xa_full_95, hstd_mt, rules_k, nguoi_xuat=username
                    )
                    if pdf_folder:
                        try:
                            dp_path = Path(pdf_folder)
                            dp_path.mkdir(parents=True, exist_ok=True)
                            fn_95 = f"KHTD_95_XA_TONG_HOP_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                            full_p = dp_path / fn_95
                            full_p.write_bytes(pdf_bytes_95)
                            st.success(f"✅ Đã lưu PDF toàn 95 xã: {full_p}")
                        except Exception as _e:
                            logger.error("Lưu PDF 95xa dir fail: %s", _e, exc_info=True)
                            st.warning(f"⚠️ Không lưu vào thư mục ({_e}); vẫn có thể tải về.")
                    state_95 = SCMStateManager()
                    state_95.downloads.set(
                        "khtd_95xa_pdf",
                        pdf_bytes_95,
                        f"KHTD_95XA_{datetime.now().strftime('%Y%m%d')}.pdf",
                    )
                    db.ghi_audit(
                        username, "xuat_pdf_95xa_khtd",
                        f"Tổng hợp 95 xã theo STT chuẩn I..XXII — toàn Chi nhánh. PGD đang chọn: {pgd_chon}"
                    )
                    st.success("✅ Đã xây xong PDF 95 xã. Nhấn nút ⬇️ Tải PDF 95 xã về máy bên dưới.")
                except Exception as e:
                    logger.error("Xuat PDF 95 xa loi: %s", e, exc_info=True)
                    SCMStateManager().downloads.clear("khtd_95xa_pdf")
                    st.error(f"❌ Lỗi xây PDF 95 xã: {e}")

        # ── Submit (trong form) và Download (ngoài form) gom khối cuối ───────
        _col_sb, _col_sp = st.columns([1, 0.001])
        with _col_sb:
            if st.form_submit_button("💾 Lưu kế hoạch xã này", type="primary", width='stretch'):
                for khoa, gia_tri_trieu in gia_tri_moi.items():
                    kh_xa[khoa] = gia_tri_trieu * 1_000_000
                if _luu_kv(KV_KEY_XA, kh_xa, username):
                    db.ghi_audit(username, "luu_khtd_xa",
                                 f"PGD: {pgd_chon} — Xã: {xa_chon}")
                    st.success(f"✅ Đã lưu kế hoạch cho xã **{xa_chon}**")
                    st.rerun()

    # ── Container cuối: Tải file về (ngoài form để không trigger submit) ──
    with st.container(border=True):
        st.caption("⬇️ Tải file đã xuất về máy")
        state = SCMStateManager()
        _dlc1, _dlc2 = st.columns(2)
        with _dlc1:
            if state.downloads.has("khtd_xa_pdf"):
                if st.download_button(
                    label="⬇️ Tải PDF đơn xã về máy",
                    data=state.downloads.get_bytes("khtd_xa_pdf"),
                    file_name=state.downloads.get_filename("khtd_xa_pdf") or "KHTD.pdf",
                    mime="application/pdf",
                    key="download_pdf_khtd_xa",
                    width='stretch',
                ):
                    state.downloads.clear("khtd_xa_pdf")
            else:
                st.button(
                    "⬇️ Tải PDF đơn xã về máy",
                    disabled=True,
                    width='stretch',
                    help="Nhấn nút 🖨️ Xuất PDF xã bên trên để tạo PDF, sau đó tải về tại đây",
                )
        with _dlc2:
            if state.downloads.has("khtd_95xa_pdf"):
                if st.download_button(
                    label="⬇️ Tải PDF 95 xã về máy",
                    data=state.downloads.get_bytes("khtd_95xa_pdf"),
                    file_name=state.downloads.get_filename("khtd_95xa_pdf") or "KHTD_95_XA.pdf",
                    mime="application/pdf",
                    key="download_pdf_khtd_95xa",
                    width='stretch',
                ):
                    state.downloads.clear("khtd_95xa_pdf")
            else:
                st.button(
                    "⬇️ Tải PDF 95 xã về máy",
                    disabled=True,
                    width='stretch',
                    help="Nhấn nút 📚 Xuất PDF 95 xã bên trên để tạo PDF tổng hợp, sau đó tải về tại đây",
                )


def _tao_df_pdf_1_xa(
    pgd_name: str,
    xa_name: str,
    df_full: pd.DataFrame | None,
    kh_xa_full: dict | None,
    hstd_mtime: float,
    rules_key: str,
) -> tuple[pd.DataFrame, dict[str, object], str, str]:
    """Build pdf_data DataFrame + dong_tong + tieu_de/tieu_de_phu cho 1 xã.

    Returns: (df_pdf_10_cols, dong_tong_dict, tieu_de_str, tieu_de_phu_str)
    """
    from config import MA_KEYS_CO_KHTD, KHTD_CN_NHOM_MA_CT

    PDF_COLS = [
        "STT", "Chương trình",
        "KH TW", "TH TW", "Còn TW", "Đạt TW%",
        "KH ĐP", "TH ĐP", "Còn ĐP", "Đạt ĐP%",
    ]

    kh_store = kh_xa_full or {}

    # --- TH ---
    try:
        _th_xa, _ten_map_q, _keys_phat_sinh = _du_lieu_khtd_xa_cached(
            df_full,
            pgd_name,
            xa_name,
            hstd_mtime,
            rules_key,
        )
    except Exception:
        _th_xa, _ten_map_q, _keys_phat_sinh = {}, {}, set()

    pdf_data: list[dict] = []
    stt = 1
    s_kh_tw = s_th_tw = s_kh_dp = s_th_dp = 0.0

    for _tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
        for ma_ct in ds_ma_ct:
            mk_tw = f"{ma_ct}_TW"
            mk_dp = f"{ma_ct}_DP"
            khoa_tw = f"{xa_name}|{mk_tw}"
            khoa_dp = f"{xa_name}|{mk_dp}"

            # KH ( triệu đồng — kv luôn lưu VND nên chia 1e6, draft overlay KH_xa_full đã triệu → giữ)
            # Dùng cơ chế: nếu value > 1e9 thì assume nó là VND, nếu < 1e6 assume triệu
            kh_tw_raw = float(kh_store.get(khoa_tw, 0.0) or 0.0)
            kh_dp_raw = float(kh_store.get(khoa_dp, 0.0) or 0.0)
            kh_tw = kh_tw_raw / 1_000_000 if kh_tw_raw > 1e7 else kh_tw_raw
            kh_dp = kh_dp_raw / 1_000_000 if kh_dp_raw > 1e7 else kh_dp_raw

            th_tw_vnd = float(_th_xa.get(mk_tw, 0.0) or 0.0)
            th_dp_vnd = float(_th_xa.get(mk_dp, 0.0) or 0.0)
            th_tw = th_tw_vnd / 1_000_000
            th_dp = th_dp_vnd / 1_000_000

            if kh_tw <= 0 and th_tw <= 0 and kh_dp <= 0 and th_dp <= 0:
                continue

            con_tw = max(kh_tw - th_tw, 0.0)
            con_dp = max(kh_dp - th_dp, 0.0)
            dat_tw_pct = (th_tw / kh_tw * 100.0) if kh_tw > 0 else None
            dat_dp_pct = (th_dp / kh_dp * 100.0) if kh_dp > 0 else None

            ten_ct = _ten_ct_base(ma_ct, _ten_map_q)
            row: dict = {
                "STT": stt,
                "Chương trình": ten_ct,
                "KH TW":  round(kh_tw, 1)  if kh_tw  > 0 else None,
                "TH TW":  round(th_tw, 1)  if th_tw  > 0 else None,
                "Còn TW": round(con_tw, 1) if con_tw > 0 else None,
                "Đạt TW%": round(dat_tw_pct, 1) if dat_tw_pct is not None else None,
                "KH ĐP":  round(kh_dp, 1)  if kh_dp  > 0 else None,
                "TH ĐP":  round(th_dp, 1)  if th_dp  > 0 else None,
                "Còn ĐP": round(con_dp, 1) if con_dp > 0 else None,
                "Đạt ĐP%": round(dat_dp_pct, 1) if dat_dp_pct is not None else None,
            }
            pdf_data.append(row)
            stt += 1
            if kh_tw > 0: s_kh_tw += kh_tw
            if th_tw > 0: s_th_tw += th_tw
            if kh_dp > 0: s_kh_dp += kh_dp
            if th_dp > 0: s_th_dp += th_dp

    if not pdf_data:
        df_pdf = pd.DataFrame(columns=PDF_COLS)
        dong_tong: dict[str, object] = {}
    else:
        df_pdf = pd.DataFrame(pdf_data, columns=PDF_COLS)
        s_con_tw = max(s_kh_tw - s_th_tw, 0.0)
        s_con_dp = max(s_kh_dp - s_th_dp, 0.0)
        s_dat_tw_pct = (s_th_tw / s_kh_tw * 100.0) if s_kh_tw > 0 else None
        s_dat_dp_pct = (s_th_dp / s_kh_dp * 100.0) if s_kh_dp > 0 else None
        dong_tong = {
            "STT": "",
            "Chương trình": "TỔNG CỘNG",
            "KH TW":  round(s_kh_tw, 1),
            "TH TW":  round(s_th_tw, 1),
            "Còn TW": round(s_con_tw, 1),
            "Đạt TW%": round(s_dat_tw_pct, 1) if s_dat_tw_pct is not None else None,
            "KH ĐP":  round(s_kh_dp, 1),
            "TH ĐP":  round(s_th_dp, 1),
            "Còn ĐP": round(s_con_dp, 1),
            "Đạt ĐP%": round(s_dat_dp_pct, 1) if s_dat_dp_pct is not None else None,
        }

    _stt_p, _stt_x, _so_tieu_de = _stt_pgd_xa(pgd_name, xa_name)
    ngay_hien_tai = datetime.now().strftime("%d/%m/%Y")
    tieu_de     = f"KẾ HOẠCH TÍN DỤNG — {_so_tieu_de.upper()}" if _so_tieu_de else f"KẾ HOẠCH TÍN DỤNG — {xa_name.upper()}"
    tieu_de_phu = f"Ngày {ngay_hien_tai}"
    return df_pdf, dong_tong, tieu_de, tieu_de_phu


def _xuat_pdf_tat_ca_95_xa_bytes(
    df_full: pd.DataFrame | None,
    kh_xa_full: dict | None,
    hstd_mtime: float,
    rules_key: str,
    nguoi_xuat: str = "VBSP-SCM",
) -> bytes:
    """Xây dựng 1 file PDF cho tất cả 95 xã/phường (22 PGD) theo đúng thứ tự chuẩn.

    Cấu trúc:
      - Bìa (Cover) + Trang tính mục lục tóm tắt (số xã có KH, tổng KH CN)
      - Với mỗi PGD: Header lớn "I — Hội sở chi nhánh tỉnh" + HR + từng xã
      - Với mỗi xã: Header "Mục 1 · Phường Phước Tân" + 1 bảng 10 cột KH/TH/Còn/%
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak, Table,
        TableStyle, Image as RLImage,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle as _PS
    from pathlib import Path as _Path
    from config import TEN_CHI_NHANH_HIEN_THI
    from pdf_service import (
        _dang_ky_font, FONT_NORMAL, FONT_BOLD, FONT_ITALIC, _FONT_REGISTERED,
        FONT_FALLBACK, VBSP_GREEN, VBSP_GREEN_LIGHT, VBSP_GREEN_MID,
        ROW_ALT, BORDER_COLOR, BORDER_STRONG, TEXT_MUTED,
    )
    from pdf_service import _format_phan_tram, _format_number_pdf, _pdf_text

    _dang_ky_font()
    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD if _FONT_REGISTERED else FONT_FALLBACK

    page_size = landscape(A4)
    margin = 1.1 * cm
    usable_w = page_size[0] - 2 * margin

    from io import BytesIO
    buf = BytesIO()
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    ngay_ngay = datetime.now().strftime("%d/%m/%Y")

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=1.8 * cm,
        title=f"Kế hoạch tín dụng 95 xã — {TEN_CHI_NHANH_HIEN_THI}",
        author=f"VBSP-SCM - {TEN_CHI_NHANH_HIEN_THI}",
    )

    story: list = []

    # -------- Cover / Trang đầu -----------
    logo_path = _Path("assets/logo.png")
    if logo_path.exists():
        try:
            logo = RLImage(str(logo_path), width=2.2 * cm, height=2.2 * cm)
            hdr = Table(
                [[logo, Paragraph(
                    "<b>NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM</b><br/>"
                    f"<font size='11'>{_pdf_text(TEN_CHI_NHANH_HIEN_THI)}</font>",
                    _PS("hdr_cover_text", fontName=fb, fontSize=13,
                        alignment=TA_CENTER, leading=17, spaceAfter=0)
                )]],
                colWidths=[2.6 * cm, usable_w - 2.6 * cm],
            )
            hdr.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(hdr)
        except Exception:
            story.append(Paragraph("<b>NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM</b>",
                                   _PS("cv_bank", fontName=fb, fontSize=13, alignment=TA_CENTER)))
            story.append(Paragraph(_pdf_text(TEN_CHI_NHANH_HIEN_THI),
                                   _PS("cv_branch", fontName=fn, fontSize=11, alignment=TA_CENTER)))
    else:
        story.append(Paragraph("<b>NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM</b>",
                               _PS("cv_bank2", fontName=fb, fontSize=13, alignment=TA_CENTER)))
        story.append(Paragraph(_pdf_text(TEN_CHI_NHANH_HIEN_THI),
                               _PS("cv_branch2", fontName=fn, fontSize=11, alignment=TA_CENTER)))

    story.append(Spacer(1, 0.2 * cm))
    story.append(HRFlowable(width="100%", thickness=2.2, color=VBSP_GREEN))
    story.append(HRFlowable(width="100%", thickness=0.5, color=VBSP_GREEN_MID, spaceAfter=1.2 * cm))
    story.append(Paragraph(
        "TỔNG HỢP KẾ HOẠCH TÍN DỤNG 95 XÃ/PHƯỜNG",
        _PS("cv_title", fontName=fb, fontSize=22, alignment=TA_CENTER,
            textColor=VBSP_GREEN, leading=30, spaceAfter=0.6 * cm)
    ))
    story.append(Paragraph(
        f"Theo thứ tự chuẩn 22 PGD — Cập nhật đến ngày {ngay_ngay}",
        _PS("cv_sub", fontName=fn, fontSize=11, alignment=TA_CENTER,
            textColor=TEXT_MUTED, spaceAfter=2.2 * cm, leading=15)
    ))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  ·  Người xuất: {_pdf_text(nguoi_xuat)}  ·  Nguồn: Hệ thống HSTD VBSP-SCM",
        _PS("cv_meta", fontName=fn, fontSize=10, alignment=TA_CENTER, textColor=TEXT_MUTED)
    ))

    story.append(PageBreak())

    # --- Nội dung: duyệt qua 22 PGD chuẩn ---
    COLS_TIEN = ["KH TW", "TH TW", "Còn TW", "KH ĐP", "TH ĐP", "Còn ĐP"]
    COLS_PCT  = ["Đạt TW%", "Đạt ĐP%"]
    PDF_COLS_10 = [
        "STT", "Chương trình",
        "KH TW", "TH TW", "Còn TW", "Đạt TW%",
        "KH ĐP", "TH ĐP", "Còn ĐP", "Đạt ĐP%",
    ]

    def _col_ratio(col_name: str) -> float:
        c = str(col_name).strip().lower()
        if c in ("stt",): return 0.45
        if any(k in c for k in ("chương trình", "chuong trinh", "tên ct")): return 2.6
        if any(k in c for k in ("tỷ lệ", "tl ", "%")): return 0.95
        return 1.65

    ratios = [_col_ratio(c) for c in PDF_COLS_10]
    total_r = sum(ratios)
    col_widths = [usable_w * r / total_r for r in ratios]

    for idx_pgd, (stt_p, ten_p, dxs) in enumerate(_PGD_XA_STT_CHUAN):
        # --- Nhóm PGD ---
        if idx_pgd > 0:
            story.append(PageBreak())

        story.append(Paragraph(
            f"<b>{stt_p}. {ten_p.upper()}</b>",
            _PS(f"grp_{stt_p}", fontName=fb, fontSize=15, alignment=TA_LEFT,
                textColor=VBSP_GREEN, leading=20, spaceBefore=0.05 * cm, spaceAfter=0.15 * cm)
        ))
        story.append(HRFlowable(width="100%", thickness=1.1, color=VBSP_GREEN_MID, spaceAfter=0.4 * cm))

        # --- Xã ---
        for (stt_x, ten_x) in dxs:
            story.append(Paragraph(
                f"<b>Mục {stt_x}. {ten_x}</b>",
                _PS(f"xa_{stt_p}_{stt_x}", fontName=fb, fontSize=11.5, alignment=TA_LEFT,
                    textColor=TEXT_MUTED if False else colors.HexColor("#2E7D32"),
                    leading=15, spaceBefore=0.3 * cm, spaceAfter=0.2 * cm)
            ))

            df_xa, dong_tong_xa, _, _ = _tao_df_pdf_1_xa(
                ten_p.replace("Hội sở chi nhánh tỉnh", "Hội sở"),
                ten_x,
                df_full,
                kh_xa_full,
                hstd_mtime,
                rules_key,
            )

            if df_xa.empty:
                story.append(Paragraph(
                    "<i>— Chưa có kế hoạch hoặc thực hiện tại xã/phường này —</i>",
                    _PS(f"empty_{stt_p}_{stt_x}", fontName=fn, fontSize=9.5,
                        alignment=TA_LEFT, textColor=TEXT_MUTED, spaceAfter=0.5 * cm, leading=13),
                ))
                continue

            # Bảng
            header_style = _PS(
                f"th_{stt_p}_{stt_x}", fontName=fb, fontSize=9.5, alignment=TA_CENTER,
                textColor=colors.white, leading=13,
            )
            header_cells = [
                Paragraph(_pdf_text(str(c).replace("_", " ")), header_style)
                for c in PDF_COLS_10
            ]
            table_data: list[list] = [header_cells]

            cell_r = _PS(f"tdr_{stt_p}_{stt_x}", fontName=fn, fontSize=9, alignment=TA_RIGHT, leading=12)
            cell_l = _PS(f"tdl_{stt_p}_{stt_x}", fontName=fn, fontSize=9, alignment=TA_LEFT, leading=12, wordWrap="CJK")
            cell_c = _PS(f"tdc_{stt_p}_{stt_x}", fontName=fn, fontSize=9, alignment=TA_CENTER, leading=12)
            tong_r = _PS(f"tgr_{stt_p}_{stt_x}", fontName=fb, fontSize=9, alignment=TA_RIGHT, leading=12, textColor=VBSP_GREEN)
            tong_l = _PS(f"tgl_{stt_p}_{stt_x}", fontName=fb, fontSize=9, alignment=TA_LEFT, leading=12, textColor=VBSP_GREEN)
            tong_c = _PS(f"tgc_{stt_p}_{stt_x}", fontName=fb, fontSize=9, alignment=TA_CENTER, leading=12, textColor=VBSP_GREEN)

            def _is_left(col_name: str) -> bool:
                c = str(col_name).lower()
                return any(k in c for k in ("chương trình", "chuong trinh")) or c == "chương trình"
            def _is_center(col_name: str) -> bool:
                return str(col_name).lower() in ("stt",)

            for _, row in df_xa.iterrows():
                cells: list = []
                for ci, col in enumerate(PDF_COLS_10):
                    val = row[col]
                    try:
                        na = pd.isna(val)
                    except Exception:
                        na = val is None
                    if na or val == "":
                        p = Paragraph("", cell_r)
                    elif col in COLS_PCT:
                        p = Paragraph(_format_phan_tram(val).replace(" %", "%"), cell_r)
                    elif col in COLS_TIEN:
                        try:
                            txt = _format_number_pdf(float(val), col)
                        except Exception:
                            txt = _pdf_text(val)
                        p = Paragraph(txt, cell_r)
                    elif _is_left(col):
                        p = Paragraph(_pdf_text(val), cell_l)
                    elif _is_center(col):
                        p = Paragraph(_pdf_text(val), cell_c)
                    else:
                        p = Paragraph(_pdf_text(val), cell_r)
                    cells.append(p)
                table_data.append(cells)

            # Dong tong
            tong_cells: list = []
            for ci, col in enumerate(PDF_COLS_10):
                val = dong_tong_xa.get(col, "")
                try:
                    na = pd.isna(val) if not isinstance(val, str) else (val == "")
                except Exception:
                    na = True
                txt = ""
                if col == "Chương trình" and str(val).strip():
                    txt = f"<b>{_pdf_text(val)}</b>"
                elif na:
                    txt = ""
                elif col in COLS_PCT:
                    try:
                        txt = f"<b>{_pdf_text(_format_phan_tram(val).replace(' %', '%'))}</b>"
                    except Exception:
                        txt = f"<b>{_pdf_text(val)}</b>"
                elif col in COLS_TIEN:
                    try:
                        txt = f"<b>{_pdf_text(_format_number_pdf(float(val), col))}</b>"
                    except Exception:
                        txt = f"<b>{_pdf_text(val)}</b>"
                else:
                    if str(val).strip():
                        txt = f"<b>{_pdf_text(val)}</b>"
                if col == "STT":
                    p = Paragraph("", tong_c)
                elif col == "Chương trình":
                    p = Paragraph(txt or "", tong_c)
                elif _is_left(col):
                    p = Paragraph(txt, tong_l)
                elif _is_center(col):
                    p = Paragraph(txt, tong_c)
                else:
                    p = Paragraph(txt, tong_r)
                tong_cells.append(p)
            table_data.append(tong_cells)

            tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
            style_cmds: list = [
                ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), fb),
                ("FONTSIZE", (0, 0), (-1, 0), 9.5),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, 0), 0.5, BORDER_STRONG),
                ("GRID", (0, 1), (-1, -1), 0.3, BORDER_COLOR),
                ("BOX", (0, 0), (-1, -1), 1.2, VBSP_GREEN),
                ("LINEBELOW", (0, 0), (-1, 0), 1.0, VBSP_GREEN_MID),
            ]
            n_rows = len(table_data) - 1  # trừ header
            last_row = len(table_data) - 1
            for r in range(1, n_rows):
                if r % 2 == 0:
                    style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))
            # Tong
            style_cmds.extend([
                ("BACKGROUND", (0, last_row), (-1, last_row), VBSP_GREEN_LIGHT),
                ("FONTNAME",   (0, last_row), (-1, last_row), fb),
                ("LINEABOVE",  (0, last_row), (-1, last_row), 2.0, VBSP_GREEN),
                ("LINEBELOW",  (0, last_row), (-1, last_row), 1.2, VBSP_GREEN),
            ])
            tbl.setStyle(TableStyle(style_cmds))

            # Căn phải cho cột tiền (Reportlab alignment theo cột)
            for ci, col in enumerate(PDF_COLS_10):
                if _is_center(col):
                    tbl.setStyle(TableStyle([("ALIGN", (ci, 1), (ci, -1), "CENTER")]))
                elif not _is_left(col):
                    tbl.setStyle(TableStyle([("ALIGN", (ci, 1), (ci, -1), "RIGHT")]))

            story.append(tbl)
            story.append(Spacer(1, 0.2 * cm))
            story.append(Paragraph(
                "Đơn vị tính: triệu đồng  ·  Đơn vị %: phần trăm (%)",
                _PS(f"fn_{stt_p}_{stt_x}", fontName=fn, fontSize=8.5,
                    alignment=TA_LEFT, textColor=TEXT_MUTED, spaceAfter=0.4 * cm, leading=12)
            ))

    # Footer cuối
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(
        f"Đồng Nai, ngày {datetime.now().strftime('%d')} tháng {datetime.now().strftime('%m')} năm {datetime.now().strftime('%Y')}",
        _PS("sign_date_end", fontName=fn, fontSize=10, alignment=TA_RIGHT, spaceAfter=0.6 * cm)
    ))
    ky_data = [[
        Paragraph("<b>NGƯỜI LẬP BIỂU</b>", _PS("kt1", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
        Paragraph("<b>PHÒNG CHUYÊN MÔN</b>", _PS("kt2", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
        Paragraph("<b>GIÁM ĐỐC</b>", _PS("kt3", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
    ], [
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", _PS("kd1", fontName=FONT_ITALIC if _FONT_REGISTERED else FONT_NORMAL,
                                                    fontSize=9, alignment=TA_CENTER, textColor=TEXT_MUTED)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", _PS("kd2", fontName=FONT_ITALIC if _FONT_REGISTERED else FONT_NORMAL,
                                                    fontSize=9, alignment=TA_CENTER, textColor=TEXT_MUTED)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", _PS("kd3", fontName=FONT_ITALIC if _FONT_REGISTERED else FONT_NORMAL,
                                                    fontSize=9, alignment=TA_CENTER, textColor=TEXT_MUTED)),
    ], [
        Paragraph(" ", _PS("kg1", fontSize=12, leading=30)),
        Paragraph(" ", _PS("kg2", fontSize=12, leading=30)),
        Paragraph(" ", _PS("kg3", fontSize=12, leading=30)),
    ]]
    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ky_tbl)

    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn, 8)
        canvas.setFillColor(TEXT_MUTED)
        canvas.drawRightString(
            page_size[0] - margin,
            0.8 * cm,
            f"Trang {_doc.page} / ?  ·  KHTD 95 xã  ·  VBSP-SCM  ·  {ngay_str}"
        )
        canvas.drawString(
            margin,
            0.8 * cm,
            f"{TEN_CHI_NHANH_HIEN_THI}  ·  Báo cáo nội bộ",
        )
        canvas.setStrokeColor(VBSP_GREEN_MID)
        canvas.setLineWidth(0.8)
        canvas.line(margin, 1.1 * cm, page_size[0] - margin, 1.1 * cm)
        canvas.restoreState()

    try:
        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    except Exception:
        doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def render_nhap_cn(role: str, username: str, df_full: "pd.DataFrame | None", df_gqvl: "pd.DataFrame | None" = None) -> None:
    _tab_khtd_chi_nhanh(role, username, df_full, df_gqvl)


def render_nhap_pgd(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    _tab_khtd_theo_xa(role, username, df_full)
