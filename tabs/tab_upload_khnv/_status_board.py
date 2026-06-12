"""Bảng trạng thái upload 22 đơn vị × 5 loại."""
from __future__ import annotations

import os
from datetime import date as _date, datetime as _dt
from pathlib import Path as _P

import streamlit as st

from config import (
    DS_PGD, DON_VI_CHI_NHANH,
    LOAI_BASELINE,
    danh_sach_nam_baseline_pgd,
    trang_thai_baseline_pgd_loai,
)
from data.pgd import duong_dan_pgd as _dp, lay_trang_thai_upload_pgd
from services.file_detection_service import DS_DON_VI
from utils import hien_thi_dataframe_phan_trang
from ._state import lay_hang_cho


def render_bang_trang_thai() -> None:
    """Bảng trạng thái 22 hàng × 6 cột: Đơn vị | HSTD | NQ11 | GQVL | CDTOTKVV | 31/12."""
    if "trang_thai_upload_pgd" not in st.session_state:
        st.session_state["trang_thai_upload_pgd"] = lay_trang_thai_upload_pgd(DS_DON_VI)
    df_tt = st.session_state["trang_thai_upload_pgd"].copy()

    # Patch: nếu session còn cache ❌ cũ, đọc thẳng từ đĩa để kiểm tra hstd_khnv
    mask_thieu = df_tt["HSTD"].astype(str).str.startswith("❌", na=False)
    if mask_thieu.any():
        for idx in df_tt[mask_thieu].index:
            dv = df_tt.at[idx, "Đơn vị"]
            p = _P(_dp(dv, "hstd_khnv"))
            if p.exists():
                ngay_up = _dt.fromtimestamp(os.path.getmtime(p))
                df_tt.at[idx, "HSTD"] = f"✅ {ngay_up.strftime('%d/%m')}"

    # Cột 31/12: kiểm tra cả 4 loại
    if "_blcache_nam_list" not in st.session_state:
        st.session_state["_blcache_nam_list"] = danh_sach_nam_baseline_pgd()
    ds_nam_bl = st.session_state["_blcache_nam_list"]
    nam_bl = ds_nam_bl[0] if ds_nam_bl else (_date.today().year - 1)

    _bl_loai_key = f"_blcache_tt_loai_col_{nam_bl}"
    if _bl_loai_key not in st.session_state:
        st.session_state[_bl_loai_key] = {
            loai: trang_thai_baseline_pgd_loai(nam_bl, loai) for loai in LOAI_BASELINE
        }
    tt_bl_loai = st.session_state[_bl_loai_key]

    col_bl = f"31/12/{nam_bl}"

    def _nhan_bl(dv):
        dem = sum(1 for loai in LOAI_BASELINE if tt_bl_loai[loai].get(dv, False))
        tong = len(LOAI_BASELINE)
        if dem == 0:
            return "❌ Chưa loại nào"
        if dem == tong:
            return f"✅ Đủ {tong}/{tong}"
        loai_thieu = [loai for loai in LOAI_BASELINE if not tt_bl_loai[loai].get(dv, False)]
        return f"⚠️ {dem}/{tong} (thiếu {','.join(loai_thieu)})"

    df_tt[col_bl] = df_tt["Đơn vị"].apply(_nhan_bl)

    def style_trang_thai(val: str) -> str:
        v = str(val)
        if v.startswith("✅"):
            return "background-color: #d4edda; color: #155724; font-weight: bold"
        if v.startswith("⚠️"):
            return "background-color: #fff3cd; color: #856404"
        if v.startswith("❌"):
            return "background-color: #f8d7da; color: #721c24"
        return ""

    cols_loai = ["HSTD", "NQ11", "GQVL", "CDTOTKVV", col_bl]
    styled = df_tt.style.map(style_trang_thai, subset=cols_loai)
    hien_thi_dataframe_phan_trang(styled, key="upload_khnv_trang_thai", height=800)


def render_pending_badge() -> None:
    """Hiển thị badge pending merge nếu có dữ liệu chờ merge."""
    hang_cho = lay_hang_cho()
    if not hang_cho:
        return
    loai_str = " + ".join(sorted(hang_cho)).upper()
    st.warning(
        f"⏳ **{len(hang_cho)} loại đang chờ merge:** {loai_str}  \n"
        "Chuyển sang tab **📊 Tổng quan** → bấm **🔄 Merge toàn CN** để cập nhật.",
        icon="⚠️",
    )
