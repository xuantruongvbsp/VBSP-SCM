"""Nhập dữ liệu cho tab Kế hoạch Tín dụng (Chi nhánh + theo Xã/PGD)."""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

import db
from auth import get_permissions, normalize_role
from pdf_service import xuat_pdf_bang
from state_manager import SCMStateManager
from config import CHUONG_TRINH_KHTD, COT_TEN_PGD, DS_PGD, PGD_XA_MAP
from utils import fmt, xuat_excel, ten_file_xuat, vn

from tabs.tab_khtd import (
    DATA_DIR,
    KV_KEY_CN,
    KV_KEY_XA,
    KHTD_CN_NHOM_MA_CT,
    MA_KEYS_CO_KHTD,
    GQVL_SUB_NHOM,
    NSVSMT_DP_SUB_NHOM,
    _chon_ds_ct,
    _doc_kv,
    _fvn,
    _fmt_vn,
    _khtd_cn_hdr_cell,
    _luu_kv,
    _quet_ct_co_du_no,
    _ten_ct_base,
    _tinh_thuc_hien_theo_ct,
    _tinh_th_nsvsmt_dp_phan_tang,
)
# NOTE: _hien_thi_bang_cn_readonly import lazy (tránh circular import)
# tab_khtd_xuat → tab_khtd → tab_khtd_nhap → tab_khtd_xuat (vòng tròn)
from services.khtd_nhap_service import (


    clean_sheet_name as _clean_sheet_name,
    tinh_th_gqvl_phan_tang as _tinh_th_gqvl_phan_tang,
    format_kich_thuoc as _format_kich_thuoc,
    doc_meta_qd as _doc_meta_qd,
    luu_meta_qd as _svc_luu_meta_qd,
    luu_file_qd as _svc_luu_file_qd,
    tao_df_mau_khtd_cn as _tao_df_mau_khtd_cn,
    doc_excel_khtd_cn_upload as _svc_doc_excel_khtd_cn_upload,
    doc_excel_khtd_xa_upload as _svc_doc_excel_khtd_xa_upload,
    luu_pdf_khtd_xa as _svc_luu_pdf_khtd_xa,
)


# Nhãn ngắn cho bảng nhập KHTD CN để cột "Chương trình" dễ đọc hơn.
_TEN_CT_NGAN_CN: dict[int, str] = {
    1: "Hộ nghèo",
    2: "HSSV",
    4: "XKLĐ",
    6: "Nước sạch",
    7: "Nhà ở hộ nghèo",
    9: "Hộ mới thoát nghèo",
    10: "SXKD vùng khó khăn",
    12: "Nhà ở xã hội",
    15: "Thương nhân vùng khó khăn",
    17: "DTTS QĐ 755",
    19: "Hộ cận nghèo",
    21: "DTTS QĐ 2085",
    25: "Vùng DTTS và miền núi",
    26: "Chấp hành xong án",
    99: "Cho vay khác",
}


def _ten_ct_hien_thi_nhap_cn(ma_ct: int, ten_map: dict[str, str] | None = None) -> str:
    """Tên hiển thị ngắn, rõ cho cột Chương trình ở bảng nhập KHTD Chi nhánh."""
    return _TEN_CT_NGAN_CN.get(int(ma_ct), _ten_ct_base(ma_ct, ten_map))


def _dong_bo_nsvsmt_dp_keys(data: dict[str, float]) -> dict[str, float]:
    """Giữ tương thích giữa key tổng `6_DP` và 2 sub-key chi tiết."""
    out = dict(data or {})
    base = float(out.get("6_DP", 0.0) or 0.0)
    co_split = "6_DP_TINH" in out or "6_DP_XA" in out
    if not co_split and base > 0:
        out["6_DP_TINH"] = base
        out["6_DP_XA"] = 0.0
    if co_split:
        out["6_DP"] = float(out.get("6_DP_TINH", 0.0) or 0.0) + float(out.get("6_DP_XA", 0.0) or 0.0)
    return out


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
    th_cn = _tinh_thuc_hien_theo_ct(df_full) if df_full is not None else {}
    # Merge TH NSVSMT phân tầng (6_DP_TINH / 6_DP_XA) vào th_cn
    th_nsvsmt = _tinh_th_nsvsmt_dp_phan_tang(df_full)
    th_cn = {**(th_cn or {}), **th_nsvsmt}
    # Tính TH GQVL phân tầng 4 nhóm
    th_gqvl = _tinh_th_gqvl_phan_tang(df_gqvl)

    if not co_quyen:
        st.warning("⚠️ Chỉ Admin / Manager mới được nhập kế hoạch cấp Chi nhánh.")
        df_loc = df_full
        from tabs.tab_khtd_xuat import _hien_thi_bang_cn_readonly  # lazy – tránh circular import
        _hien_thi_bang_cn_readonly(kh_cn, th_cn, df_loc=df_loc, username=username)
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
    ds_ct = _chon_ds_ct(nv_chon, df_loc, them_keys=set(kh_cn.keys()) | set(th_cn.keys()))

    # ── Phương thức 2: Nhập thủ công (bảng gọn) ──────────────────────────
    _, ten_map_q = _quet_ct_co_du_no(df_loc)

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

    st.caption("📌 Đơn vị nhập và hiển thị: triệu đồng — số nguyên, không có thập phân")

    _colw = [2, 1, 1, 1, 1, 1, 1, 1, 1]
    _ths = (
        "font-size:0.82rem;font-weight:600;text-align:center;"
        "padding:7px 6px;border-radius:4px;white-space:nowrap"
    )
    st.markdown(
        f"""
<table style="width:100%;border-collapse:collapse;border-spacing:0;
  table-layout:fixed;margin-bottom:2px;border:1px solid #cbd5e1">
<colgroup>
  <col style="width:20%">
  <col style="width:10%"><col style="width:10%"><col style="width:10%">
  <col style="width:10%"><col style="width:10%"><col style="width:10%">
  <col style="width:10%"><col style="width:10%">
</colgroup>
<tr>
  <th style="{_ths};background:#f0f4fa;border:1px solid #cbd5e1"></th>
  <th colspan="3" style="{_ths};background:#bbdefb;color:#1565c0;border:1px solid #cbd5e1">NGUỒN VỐN TRUNG ƯƠNG</th>
  <th colspan="3" style="{_ths};background:#c8e6c9;color:#2e7d32;border:1px solid #cbd5e1">NGUỒN VỐN ĐỊA PHƯƠNG</th>
  <th colspan="2" style="{_ths};background:#ffe0b2;color:#e65100;border:1px solid #cbd5e1">TỔNG CỘNG</th>
</tr>
<tr>
  <th style="{_ths};background:#f0f4fa;color:#37474f;border:1px solid #cbd5e1">Chương trình</th>
  <th style="{_ths};background:#e3f2fd;color:#1565c0;border:1px solid #cbd5e1">Kế hoạch</th>
  <th style="{_ths};background:#e3f2fd;color:#1565c0;border:1px solid #cbd5e1">Thực hiện</th>
  <th style="{_ths};background:#e3f2fd;color:#1565c0;border:1px solid #cbd5e1">Còn phải TH</th>
  <th style="{_ths};background:#e8f5e9;color:#2e7d32;border:1px solid #cbd5e1">Kế hoạch</th>
  <th style="{_ths};background:#e8f5e9;color:#2e7d32;border:1px solid #cbd5e1">Thực hiện</th>
  <th style="{_ths};background:#e8f5e9;color:#2e7d32;border:1px solid #cbd5e1">Còn phải TH</th>
  <th style="{_ths};background:#fff3e0;color:#e65100;border:1px solid #cbd5e1">TH cả hai nguồn</th>
  <th style="{_ths};background:#fff3e0;color:#e65100;border:1px solid #cbd5e1">Còn phải TH</th>
</tr>
</table>""",
        unsafe_allow_html=True,
    )

    def _fvn_form(x: float, d: int = 1) -> str:
        return f"{float(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _md_right(val: str, color: str = "var(--text-color)") -> str:
        return (
            f"<div style='text-align:right;color:{color};font-size:0.88rem;"
            f"padding:2px 0'>{val}</div>"
        )

    st.markdown(
        """
<style>
:root {
  --khtd-neg: #c62828;
  --khtd-ok: #2e7d32;
  --khtd-muted: #64748b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --khtd-neg: #ff8787;
    --khtd-ok: #69db7c;
    --khtd-muted: #9ca3af;
  }
}
[data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid #e2e8f0 !important;
    border-right: 1px solid #e2e8f0 !important;
    border-left: 1px solid #e2e8f0 !important;
    padding: 2px 0 !important;
}
[data-testid="stHorizontalBlock"] > div {
    border-right: 1px solid #e2e8f0 !important;
    padding: 4px 8px !important;
}
[data-testid="stHorizontalBlock"] > div:last-child {
    border-right: none !important;
}
[data-testid="stHorizontalBlock"]:hover {
    background-color: rgba(128,128,128,0.12) !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
    nhom_style = [
        ("#1d4ed8", "#ffffff"),
        ("#15803d", "#ffffff"),
        ("#b45309", "#ffffff"),
    ]
    idx_nhom = 0
    for tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
        bg, fg = nhom_style[idx_nhom % len(nhom_style)]
        idx_nhom += 1
        st.markdown(
            f"<p style='margin:0.8rem 0 0.4rem 0;padding:7px 12px;"
            f"background-color:{bg};color:{fg};border-radius:6px;font-weight:700;"
            f"font-size:0.9rem;border-left:4px solid rgba(255,255,255,0.45);"
            f"letter-spacing:0.1px'>{tieu_de_nhom}</p>",
            unsafe_allow_html=True,
        )
        for ma_ct in ds_ma_ct:
            # ── Xử lý đặc biệt: GQVL (ma_ct=3) phân tầng 4 nhóm ─────────────────
            if ma_ct == 3:
                # Header GQVL (chỉ hiển thị, không có input)
                cols_hdr = st.columns(_colw)
                cols_hdr[0].markdown(
                    "<div style='font-size:0.88rem;font-weight:600;"
                    "padding:4px 0;color:var(--text-color, inherit);line-height:1.35'>"
                    "Cho vay giải quyết việc làm</div>",
                    unsafe_allow_html=True
                )
                # Tổng TW và ĐP để hiển thị ở header
                th_3_tw = (th_gqvl.get("3_TW_NHCSXH", 0.0) + th_gqvl.get("3_TW_NSNN", 0.0)) / 1e6
                th_3_dp = (th_gqvl.get("3_DP_TINH", 0.0) + th_gqvl.get("3_DP_XA", 0.0)) / 1e6
                cols_hdr[2].markdown(_md_right(_fvn_form(th_3_tw, 0)), unsafe_allow_html=True)
                cols_hdr[5].markdown(_md_right(_fvn_form(th_3_dp, 0)), unsafe_allow_html=True)
                cols_hdr[7].markdown(_md_right(_fvn_form(th_3_tw + th_3_dp, 0)), unsafe_allow_html=True)

                # 4 sub-dòng thụt vào
                GQVL_SUB_ROWS = [
                    ("GQVL TW — NHCSXH huy động", "3_TW_NHCSXH", "TW"),
                    ("GQVL TW — NSNN (Quỹ QG TW)", "3_TW_NSNN", "TW"),
                    ("GQVL ĐP — Cấp tỉnh", "3_DP_TINH", "ĐP"),
                    ("GQVL ĐP — Cấp xã/khác", "3_DP_XA", "ĐP"),
                ]
                for sub_ten, sub_key, sub_nv in GQVL_SUB_ROWS:
                    k_inp = f"khtd_cn_inp_{sub_key}"
                    kh_vnd = float(kh_cn.get(sub_key, 0.0))
                    kh_trieu = kh_vnd / 1_000_000
                    th_trieu = th_gqvl.get(sub_key, 0.0) / 1e6

                    cols_sub = st.columns(_colw)
                    # Tên sub: thụt vào, màu nhạt hơn
                    cols_sub[0].markdown(
                        f"<div style='font-size:0.83rem;color:var(--text-color);opacity:0.75;"
                        f"padding:3px 0 3px 16px'>  {sub_ten}</div>",
                        unsafe_allow_html=True
                    )
                    # Cột KH: TW ở cols[1], ĐP ở cols[4]
                    col_kh_idx = 1 if sub_nv == "TW" else 4
                    col_th_idx = 2 if sub_nv == "TW" else 5
                    col_cp_idx = 3 if sub_nv == "TW" else 6

                    cols_sub[col_kh_idx].number_input(
                        sub_ten,
                        value=kh_trieu,
                        min_value=0.0,
                        step=1000.0,
                        format="%.0f",
                        label_visibility="collapsed",
                        key=k_inp,
                    )
                    kh_inp = float(st.session_state.get(k_inp, kh_trieu))

                    cols_sub[col_th_idx].markdown(
                        _md_right(_fvn_form(th_trieu, 0)), unsafe_allow_html=True
                    )
                    # Còn phải TH
                    cpth = kh_inp - th_trieu
                    if kh_inp == 0:
                        cols_sub[col_cp_idx].markdown(
                            _md_right("—", "var(--khtd-muted)"), unsafe_allow_html=True
                        )
                    elif cpth < 0:
                        cols_sub[col_cp_idx].markdown(
                            _md_right(_fvn_form(cpth, 0), "var(--khtd-neg)"), unsafe_allow_html=True
                        )
                    elif cpth == 0:
                        cols_sub[col_cp_idx].markdown(
                            _md_right("0 ✓", "var(--khtd-ok)"), unsafe_allow_html=True
                        )
                    else:
                        cols_sub[col_cp_idx].markdown(
                            _md_right(_fvn_form(cpth, 0)), unsafe_allow_html=True
                        )
                    # Các cột tổng để trống cho sub-dòng
                continue  # Bỏ qua xử lý mặc định cho ma_ct == 3

            if ma_ct == 6:
                cols_hdr = st.columns(_colw)
                cols_hdr[0].markdown(
                    "<div style='font-size:0.88rem;font-weight:600;"
                    "padding:4px 0;color:var(--text-color, inherit);line-height:1.35'>"
                    "Cho vay nước sạch và vệ sinh môi trường nông thôn</div>",
                    unsafe_allow_html=True,
                )

                k_tw = "khtd_cn_inp_6_tw"
                kh_tw_vnd = float(kh_cn.get("6_TW", 0.0))
                kh_tw_trieu_ht = kh_tw_vnd / 1_000_000
                th_tw_trieu = float((th_cn or {}).get("6_TW", 0.0)) / 1e6
                cols_hdr[1].number_input(
                    "tw_6",
                    value=kh_tw_trieu_ht,
                    min_value=0.0,
                    step=1000.0,
                    format="%.0f",
                    label_visibility="collapsed",
                    help="Kế hoạch Trung ương — đơn vị: triệu đồng",
                    key=k_tw,
                )
                kh_tw_trieu = float(st.session_state.get(k_tw, kh_tw_trieu_ht))
                cols_hdr[2].markdown(_md_right(_fvn_form(th_tw_trieu, 0)), unsafe_allow_html=True)
                cpth_tw = kh_tw_trieu - th_tw_trieu
                if kh_tw_trieu == 0:
                    cols_hdr[3].markdown(_md_right("—", "var(--khtd-muted)"), unsafe_allow_html=True)
                elif cpth_tw < 0:
                    cols_hdr[3].markdown(
                        _md_right(_fvn_form(cpth_tw, 0), "var(--khtd-neg)"),
                        unsafe_allow_html=True,
                    )
                elif cpth_tw == 0:
                    cols_hdr[3].markdown(_md_right("0 ✓", "var(--khtd-ok)"), unsafe_allow_html=True)
                else:
                    cols_hdr[3].markdown(_md_right(_fvn_form(cpth_tw, 0)), unsafe_allow_html=True)

                kh_6_dp_tinh = float(kh_cn.get("6_DP_TINH", kh_cn.get("6_DP", 0.0)))
                kh_6_dp_xa = float(kh_cn.get("6_DP_XA", 0.0))
                kh_6_dp_tong_trieu = (kh_6_dp_tinh + kh_6_dp_xa) / 1_000_000
                th_6_dp_tinh = float((th_cn or {}).get("6_DP_TINH", 0.0)) / 1e6
                th_6_dp_xa = float((th_cn or {}).get("6_DP_XA", 0.0)) / 1e6
                th_6_dp_tong = th_6_dp_tinh + th_6_dp_xa
                cols_hdr[4].markdown(_md_right(_fvn_form(kh_6_dp_tong_trieu, 0)), unsafe_allow_html=True)
                cols_hdr[5].markdown(_md_right(_fvn_form(th_6_dp_tong, 0)), unsafe_allow_html=True)
                cpth_6_dp = kh_6_dp_tong_trieu - th_6_dp_tong
                if kh_6_dp_tong_trieu == 0:
                    cols_hdr[6].markdown(_md_right("—", "var(--khtd-muted)"), unsafe_allow_html=True)
                elif cpth_6_dp < 0:
                    cols_hdr[6].markdown(
                        _md_right(_fvn_form(cpth_6_dp, 0), "var(--khtd-neg)"),
                        unsafe_allow_html=True,
                    )
                elif cpth_6_dp == 0:
                    cols_hdr[6].markdown(_md_right("0 ✓", "var(--khtd-ok)"), unsafe_allow_html=True)
                else:
                    cols_hdr[6].markdown(_md_right(_fvn_form(cpth_6_dp, 0)), unsafe_allow_html=True)

                th_tong = th_tw_trieu + th_6_dp_tong
                cols_hdr[7].markdown(_md_right(_fvn_form(th_tong, 0)), unsafe_allow_html=True)
                kh_tong = kh_tw_trieu + kh_6_dp_tong_trieu
                cpth_tong = kh_tong - th_tong
                if kh_tong == 0:
                    cols_hdr[8].markdown(_md_right("—", "var(--khtd-muted)"), unsafe_allow_html=True)
                elif cpth_tong < 0:
                    cols_hdr[8].markdown(
                        _md_right(_fvn_form(cpth_tong, 0), "var(--khtd-neg)"),
                        unsafe_allow_html=True,
                    )
                elif cpth_tong == 0:
                    cols_hdr[8].markdown(_md_right("0 ✓", "var(--khtd-ok)"), unsafe_allow_html=True)
                else:
                    cols_hdr[8].markdown(_md_right(_fvn_form(cpth_tong, 0)), unsafe_allow_html=True)

                NSVSMT_SUB_ROWS = [
                    ("NSVSMT ĐP — Cấp tỉnh", "6_DP_TINH"),
                    ("NSVSMT ĐP — Cấp xã/khác", "6_DP_XA"),
                ]
                for sub_ten, sub_key in NSVSMT_SUB_ROWS:
                    k_inp = f"khtd_cn_inp_{sub_key}"
                    kh_vnd = float(kh_cn.get(sub_key, 0.0))
                    kh_trieu = kh_vnd / 1_000_000
                    th_trieu = float((th_cn or {}).get(sub_key, 0.0)) / 1e6

                    cols_sub = st.columns(_colw)
                    cols_sub[0].markdown(
                        f"<div style='font-size:0.83rem;color:var(--text-color);opacity:0.75;"
                        f"padding:3px 0 3px 16px'>  {sub_ten}</div>",
                        unsafe_allow_html=True,
                    )
                    cols_sub[4].number_input(
                        sub_ten,
                        value=kh_trieu,
                        min_value=0.0,
                        step=1000.0,
                        format="%.0f",
                        label_visibility="collapsed",
                        key=k_inp,
                    )
                    kh_inp = float(st.session_state.get(k_inp, kh_trieu))
                    cols_sub[5].markdown(_md_right(_fvn_form(th_trieu, 0)), unsafe_allow_html=True)
                    cpth = kh_inp - th_trieu
                    if kh_inp == 0:
                        cols_sub[6].markdown(_md_right("—", "var(--khtd-muted)"), unsafe_allow_html=True)
                    elif cpth < 0:
                        cols_sub[6].markdown(
                            _md_right(_fvn_form(cpth, 0), "var(--khtd-neg)"),
                            unsafe_allow_html=True,
                        )
                    elif cpth == 0:
                        cols_sub[6].markdown(_md_right("0 ✓", "var(--khtd-ok)"), unsafe_allow_html=True)
                    else:
                        cols_sub[6].markdown(_md_right(_fvn_form(cpth, 0)), unsafe_allow_html=True)
                continue

            # ── Xử lý mặc định cho các CT khác ────────────────────────────────────
            mk_tw = f"{ma_ct}_TW"
            mk_dp = f"{ma_ct}_DP"
            co_tw = mk_tw in MA_KEYS_CO_KHTD
            co_dp = mk_dp in MA_KEYS_CO_KHTD
            if not co_tw and not co_dp:
                continue
            cols = st.columns(_colw)
            ten_hang = _ten_ct_hien_thi_nhap_cn(ma_ct, ten_map_q)
            cols[0].markdown(
                f"<div style='font-size:0.88rem;padding:4px 0;color:var(--text-color, inherit);"
                f"font-weight:600;line-height:1.35'>{ten_hang}</div>",
                unsafe_allow_html=True,
            )

            k_tw = f"khtd_cn_inp_{ma_ct}_tw"
            k_dp = f"khtd_cn_inp_{ma_ct}_dp"
            kh_tw_vnd = float(kh_cn.get(mk_tw, 0.0))
            kh_dp_vnd = float(kh_cn.get(mk_dp, 0.0))
            ht_tw = kh_tw_vnd / 1_000_000
            ht_dp = kh_dp_vnd / 1_000_000
            th_tw_trieu = float((th_cn or {}).get(mk_tw, 0.0)) / 1e6
            th_dp_trieu = float((th_cn or {}).get(mk_dp, 0.0)) / 1e6

            if co_tw:
                cols[1].number_input(
                    f"tw_{ma_ct}",
                    value=ht_tw,
                    min_value=0.0,
                    step=1000.0,
                    format="%.0f",
                    label_visibility="collapsed",
                    help="Kế hoạch Trung ương — đơn vị: triệu đồng",
                    key=k_tw,
                )
                kh_tw_trieu = float(
                    st.session_state[k_tw]
                    if k_tw in st.session_state
                    else ht_tw
                )
            else:
                cols[1].caption("—")
                kh_tw_trieu = 0.0

            cols[2].markdown(
                _md_right(_fvn_form(th_tw_trieu, 0)), unsafe_allow_html=True
            )
            if kh_tw_trieu == 0:
                cols[3].markdown(
                    _md_right("—", "var(--khtd-muted)"), unsafe_allow_html=True
                )
            else:
                cpth_tw = kh_tw_trieu - th_tw_trieu
                if cpth_tw < 0:
                    cols[3].markdown(
                        _md_right(_fvn_form(cpth_tw, 0), "var(--khtd-neg)"),
                        unsafe_allow_html=True,
                    )
                elif cpth_tw == 0:
                    cols[3].markdown(
                        _md_right("0,0 ✓", "var(--khtd-ok)"), unsafe_allow_html=True
                    )
                else:
                    cols[3].markdown(
                        _md_right(_fvn_form(cpth_tw, 0)), unsafe_allow_html=True
                    )

            if co_dp:
                cols[4].number_input(
                    f"dp_{ma_ct}",
                    value=ht_dp,
                    min_value=0.0,
                    step=1000.0,
                    format="%.0f",
                    label_visibility="collapsed",
                    help="Kế hoạch Địa phương — đơn vị: triệu đồng",
                    key=k_dp,
                )
                kh_dp_trieu = float(
                    st.session_state[k_dp]
                    if k_dp in st.session_state
                    else ht_dp
                )
            else:
                cols[4].caption("—")
                kh_dp_trieu = 0.0

            cols[5].markdown(
                _md_right(_fvn_form(th_dp_trieu, 0)), unsafe_allow_html=True
            )
            if kh_dp_trieu == 0:
                cols[6].markdown(
                    _md_right("—", "var(--khtd-muted)"), unsafe_allow_html=True
                )
            else:
                cpth_dp = kh_dp_trieu - th_dp_trieu
                if cpth_dp < 0:
                    cols[6].markdown(
                        _md_right(_fvn_form(cpth_dp, 0), "var(--khtd-neg)"),
                        unsafe_allow_html=True,
                    )
                elif cpth_dp == 0:
                    cols[6].markdown(
                        _md_right("0,0 ✓", "var(--khtd-ok)"), unsafe_allow_html=True
                    )
                else:
                    cols[6].markdown(
                        _md_right(_fvn_form(cpth_dp, 0)), unsafe_allow_html=True
                    )

            th_tong = th_tw_trieu + th_dp_trieu
            cols[7].markdown(
                _md_right(_fvn_form(th_tong, 0)), unsafe_allow_html=True
            )
            kh_tong = kh_tw_trieu + kh_dp_trieu
            cpth_tong = kh_tong - th_tong
            if kh_tong == 0:
                cols[8].markdown(
                    _md_right("—", "var(--khtd-muted)"), unsafe_allow_html=True
                )
            elif cpth_tong < 0:
                cols[8].markdown(
                    _md_right(_fvn_form(cpth_tong, 0), "var(--khtd-neg)"),
                    unsafe_allow_html=True,
                )
            elif cpth_tong == 0:
                cols[8].markdown(
                    _md_right("0,0 ✓", "var(--khtd-ok)"), unsafe_allow_html=True
                )
            else:
                cols[8].markdown(
                    _md_right(_fvn_form(cpth_tong, 0)), unsafe_allow_html=True
                )

    tong_kh_trieu_hien_tai = 0.0
    for _tieu_de, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
        for ma_ct in ds_ma_ct:
            # Bỏ qua CT 3 (GQVL) - đã tính qua sub-key bên dưới
            if ma_ct == 3:
                continue
            if ma_ct == 6:
                tong_kh_trieu_hien_tai += float(
                    st.session_state.get(
                        "khtd_cn_inp_6_tw",
                        float(kh_cn.get("6_TW", 0.0)) / 1_000_000,
                    )
                )
                for sub_key, _, _ in NSVSMT_DP_SUB_NHOM:
                    k_inp = f"khtd_cn_inp_{sub_key}"
                    tong_kh_trieu_hien_tai += float(
                        st.session_state.get(
                            k_inp,
                            float(kh_cn.get(sub_key, 0.0)) / 1_000_000,
                        )
                    )
                continue
            mk_tw = f"{ma_ct}_TW"
            mk_dp = f"{ma_ct}_DP"
            if mk_tw in MA_KEYS_CO_KHTD:
                k_tw = f"khtd_cn_inp_{ma_ct}_tw"
                tong_kh_trieu_hien_tai += float(
                    st.session_state[k_tw]
                    if k_tw in st.session_state
                    else float(kh_cn.get(mk_tw, 0.0)) / 1_000_000
                )
            if mk_dp in MA_KEYS_CO_KHTD:
                k_dp = f"khtd_cn_inp_{ma_ct}_dp"
                tong_kh_trieu_hien_tai += float(
                    st.session_state[k_dp]
                    if k_dp in st.session_state
                    else float(kh_cn.get(mk_dp, 0.0)) / 1_000_000
                )
    # Thêm 4 sub-key GQVL vào tổng (thay vì đếm 3_TW/3_DP)
    for sub_key, _, _ in GQVL_SUB_NHOM:
        k_inp = f"khtd_cn_inp_{sub_key}"
        tong_kh_trieu_hien_tai += float(
            st.session_state.get(k_inp,
                float(kh_cn.get(sub_key, 0.0)) / 1_000_000)
        )
    tong_kh_nhap_form = tong_kh_trieu_hien_tai * 1_000_000

    if tong_kh_nhap_form <= 0:
        st.warning(
            "⚠️ Tất cả chỉ tiêu đang = 0, kiểm tra lại trước khi lưu"
        )

    if st.button("💾 Lưu kế hoạch Chi nhánh", type="primary", key="btn_luu_khtd_cn"):
        patch: dict[str, float] = {}
        for tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
            for ma_ct in ds_ma_ct:
                # Bỏ qua CT 3 khi lưu mặc định - sẽ lưu qua sub-key
                if ma_ct == 3:
                    continue
                if ma_ct == 6:
                    patch["6_TW"] = float(st.session_state.get("khtd_cn_inp_6_tw", 0.0))
                    for sub_key, _, _ in NSVSMT_DP_SUB_NHOM:
                        k_inp = f"khtd_cn_inp_{sub_key}"
                        patch[sub_key] = float(st.session_state.get(k_inp, 0.0))
                    patch["6_DP"] = patch.get("6_DP_TINH", 0.0) + patch.get("6_DP_XA", 0.0)
                    continue
                mk_tw = f"{ma_ct}_TW"
                mk_dp = f"{ma_ct}_DP"
                if mk_tw in MA_KEYS_CO_KHTD:
                    patch[mk_tw] = float(
                        st.session_state.get(f"khtd_cn_inp_{ma_ct}_tw", 0.0)
                    )
                if mk_dp in MA_KEYS_CO_KHTD:
                    patch[mk_dp] = float(
                        st.session_state.get(f"khtd_cn_inp_{ma_ct}_dp", 0.0)
                    )
        # Lưu 4 sub-key GQVL
        for sub_key, _, _ in GQVL_SUB_NHOM:
            k_inp = f"khtd_cn_inp_{sub_key}"
            patch[sub_key] = float(st.session_state.get(k_inp, 0.0))
        # Backward compat: ghi tổng vào key cũ
        patch["3_TW"] = patch.get("3_TW_NHCSXH", 0.0) + patch.get("3_TW_NSNN", 0.0)
        patch["3_DP"] = patch.get("3_DP_TINH", 0.0) + patch.get("3_DP_XA", 0.0)
        tong_kh_luu = sum(v * 1_000_000 for v in patch.values())
        if tong_kh_luu <= 0:
            st.warning(
                "⚠️ Tất cả chỉ tiêu đang = 0, kiểm tra lại trước khi lưu"
            )
        else:
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
                    float((th_cn or {}).get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "TW"
                )
                dp_th_d = sum(
                    float((th_cn or {}).get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "DP"
                )
                pt_tw = (
                    round(tw_th_d / tw_kh_d * 100, 1) if tw_kh_d > 0 else None
                )
                pt_dp = (
                    round(dp_th_d / dp_kh_d * 100, 1) if dp_kh_d > 0 else None
                )
                all_kh_d = tw_kh_d + dp_kh_d
                all_th_d = tw_th_d + dp_th_d
                pt_all = (
                    round(all_th_d / all_kh_d * 100, 1) if all_kh_d > 0 else None
                )
                db.ghi_audit(
                    username,
                    "luu_khtd_cn",
                    f"{len(patch)} chỉ tiêu, tổng {vn(sum(patch.values()), 1)} triệu",
                )
                st.cache_data.clear()
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

    # ── Tóm tắt hiện trạng (luôn hiển thị) ───────────────────────────────
    st.markdown("##### 📊 Tóm tắt hiện trạng")
    from tabs.tab_khtd_xuat import _hien_thi_bang_cn_readonly  # lazy – tránh circular import
    _hien_thi_bang_cn_readonly(
        kh_cn,
        th_cn,
        ds_ct_loc=[mk for mk, _ in ds_ct],
        df_loc=df_loc,
        username=username,
    )

    st.divider()
    _section_van_ban_qd_cn(role, username)

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


def _tab_khtd_theo_xa(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    st.subheader("📍 Kế hoạch Tín dụng theo Xã")

    co_quyen = get_permissions(role)["can_edit_khtd"]
    if not co_quyen:
        st.warning("⚠️ Chỉ Admin / Manager mới được nhập kế hoạch theo Xã.")
        return

    kh_xa = _doc_kv(KV_KEY_XA)

    # ── Chọn PGD → Xã ────────────────────────────────────────────────────
    col_pgd, col_xa = st.columns(2)
    with col_pgd:
        pgd_chon = st.selectbox("Chọn PGD", DS_PGD, key="khtd_xa_pgd_sel")
    danh_sach_xa = PGD_XA_MAP.get(pgd_chon, [])
    with col_xa:
        xa_chon = st.selectbox(
            "Chọn Xã", danh_sach_xa if danh_sach_xa else ["(Không có xã)"],
            key="khtd_xa_xa_sel",
        )

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

    df_loc = df_full
    if df_loc is not None and not df_loc.empty and COT_TEN_PGD in df_loc.columns:
        pgd_norm = str(pgd_chon).strip()
        s_pgd = df_loc[COT_TEN_PGD].astype(str).str.strip()
        df_loc = df_loc[s_pgd == pgd_norm]

    th_xa = (
        _tinh_thuc_hien_theo_ct(df_loc)
        if df_loc is not None and not df_loc.empty
        else {}
    )

    st.divider()
    _, ten_map_q = _quet_ct_co_du_no(df_loc)
    st.caption("📌 Đơn vị nhập và hiển thị: triệu đồng")

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
            bg = nhom_mau_nen[idx_nhom % len(nhom_mau_nen)]
            idx_nhom += 1
            st.markdown(
                f"<p style='margin:0.8rem 0 0.4rem 0;padding:7px 12px;"
                f"background-color:{bg};color:#1f2937;border-radius:6px;font-weight:600;"
                f"font-size:0.9rem'>{tieu_de_nhom}</p>",
                unsafe_allow_html=True,
            )
            for ma_ct in ds_ma_ct:
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
