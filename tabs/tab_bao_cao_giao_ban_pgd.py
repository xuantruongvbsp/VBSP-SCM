"""Báo cáo Giao ban — tổng hợp dư nợ, cho vay, thu nợ theo ĐVUT và Xã."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime

import db
from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT,
    COT_MA_KH, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DVUT,
)
from auth import is_pgd_role, is_cn_role
from data import danh_dau_khong_hd_cached
from utils import fmt, fmt_so, fmt_ty, hien_thi_dataframe_phan_trang
from logger import get_logger

logger = get_logger(__name__)


def render(tab=None, **kwargs) -> None:
    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user")
    role = kwargs.get("role")

    st.subheader("📝 Báo cáo Giao ban")
    st.caption("Tổng hợp tình hình dư nợ, cho vay, thu nợ theo ĐVUT và Xã")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD.")
        return

    st.markdown("**① Bộ lọc dữ liệu**")

    df_filtered = df.copy()
    if is_pgd_role(role) and pgd_user:
        if COT_TEN_PGD in df.columns:
            df_filtered = df[df[COT_TEN_PGD] == pgd_user].copy()
        st.info(f"Dữ liệu đã lọc theo PGD: **{pgd_user}**")
    elif is_cn_role(role):
        if COT_TEN_PGD in df.columns:
            ds_pgd = sorted(df[COT_TEN_PGD].dropna().unique().tolist())
            if ds_pgd:
                chon_pgd = st.selectbox("Chọn Phòng Giao dịch", ds_pgd, key="op_gb_pgd")
                df_filtered = df[df[COT_TEN_PGD] == chon_pgd].copy()

    if COT_TEN_XA in df_filtered.columns:
        ds_xa = sorted(df_filtered[COT_TEN_XA].dropna().unique().tolist())
        if not ds_xa:
            st.warning("Không có dữ liệu xã nào trong PGD được chọn.")
            return
        chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="op_gb_xa")
        df_xa = df_filtered[df_filtered[COT_TEN_XA] == chon_xa].copy()
    else:
        st.warning("Không tìm thấy cột 'Tên xã' trong dữ liệu.")
        return

    if df_xa.empty:
        st.warning(f"Không có dữ liệu cho xã **{chon_xa}**")
        return

    dgd_map = db.doc_dgd_map()
    current_pgd = pgd_user if is_pgd_role(role) else (
        chon_pgd if 'chon_pgd' in dir() else pgd_user
    )

    ds_dgd = []
    chon_dgd = None
    ds_thon_dgd = None
    ten_dgd = None

    if current_pgd and current_pgd in dgd_map and chon_xa in dgd_map[current_pgd]:
        ds_dgd = list(dgd_map[current_pgd][chon_xa].keys())

    if not ds_dgd:
        st.info(
            "⚠️ Xã này chưa cấu hình điểm giao dịch. "
            "Vào tab **📍 Điểm GD của tôi** để thêm/cập nhật."
        )
        chon_dgd = None
        ds_thon_dgd = None
        df_dgd = df_xa.copy()
        ten_dgd = chon_xa
    else:
        chon_dgd = st.selectbox("📍 Điểm giao dịch", ds_dgd, key="op_gb_dgd")
        ds_thon_dgd = dgd_map[current_pgd][chon_xa][chon_dgd]
        ten_dgd = chon_dgd
        st.caption(f"Quản lý: {', '.join(ds_thon_dgd)}")

        if "Tên thôn" in df_xa.columns:
            df_dgd = df_xa[df_xa["Tên thôn"].isin(ds_thon_dgd)].copy()
        else:
            df_dgd = df_xa.copy()
            st.warning("Không tìm thấy cột 'Tên thôn' để lọc theo điểm giao dịch.")

    if df_dgd.empty:
        st.warning(f"Không có dữ liệu cho điểm giao dịch **{chon_dgd or chon_xa}**")
        return

    st.divider()

    st.markdown("**② Tổng hợp theo ĐVUT**")

    df_dgd_marked = danh_dau_khong_hd_cached(df_dgd)

    if COT_DVUT not in df_dgd.columns:
        st.warning("Không tìm thấy cột 'Tên ĐVUT' trong dữ liệu.")
        return

    agg_dict = {
        "Số Tổ": ("Tên tổ", lambda x: x.nunique() if "Tên tổ" in df_dgd.columns else 0),
        "Số KH": (COT_MA_KH, lambda x: x.nunique()),
        "Tổng dư nợ": (COT_TONG_DU_NO, lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
        "Nợ quá hạn": (COT_DU_NO_QH, lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
    }

    if "Giải ngân trong tháng" in df_dgd.columns:
        agg_dict["Doanh số cho vay tháng"] = (
            "Giải ngân trong tháng",
            lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum(),
        )

    thu_no_cols = ["Thu nợ TH tháng", "Thu nợ QH tháng", "Thu nợ khoanh tháng"]
    existing_thu = [c for c in thu_no_cols if c in df_dgd.columns]
    if existing_thu:
        for c in existing_thu:
            df_dgd[c] = pd.to_numeric(df_dgd[c], errors="coerce").fillna(0)
        df_dgd["Tổng thu nợ tháng"] = df_dgd[existing_thu].sum(axis=1)
        agg_dict["Doanh số thu nợ tháng"] = ("Tổng thu nợ tháng", "sum")

    if "Dư nợ khoanh" in df_dgd.columns:
        agg_dict["Nợ khoanh"] = (
            "Dư nợ khoanh",
            lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum(),
        )

    if "is_3m_inactive" in df_dgd_marked.columns:
        df_dgd["is_3m_inactive"] = df_dgd_marked["is_3m_inactive"]
        agg_dict["Số khoản 3m KHĐ"] = ("is_3m_inactive", "sum")

    valid_agg = {}
    for col_name, (data_col, agg_func) in agg_dict.items():
        if data_col in df_dgd.columns:
            valid_agg[data_col] = agg_func

    if valid_agg and COT_DVUT in df_dgd.columns:
        df_bang = df_dgd.groupby(COT_DVUT).agg(valid_agg).reset_index()
        rename_dict = {}
        for col_name, (data_col, _) in agg_dict.items():
            if data_col in df_dgd.columns and data_col in df_bang.columns:
                rename_dict[data_col] = col_name
        df_bang = df_bang.rename(columns=rename_dict)
    else:
        df_bang = pd.DataFrame({COT_DVUT: []})

    if "Tổng dư nợ" in df_bang.columns and df_bang["Tổng dư nợ"].sum() > 0:
        df_bang["Tỷ trọng %"] = (
            df_bang["Tổng dư nợ"] / df_bang["Tổng dư nợ"].sum() * 100
        ).round(1)

    dong_cong = {COT_DVUT: "CỘNG"}
    for col in df_bang.columns:
        if col != COT_DVUT:
            dong_cong[col] = 100.0 if col == "Tỷ trọng %" else df_bang[col].sum()
    df_bang = pd.concat([df_bang, pd.DataFrame([dong_cong])], ignore_index=True)

    df_display = df_bang.copy()
    tien_cols = [
        "Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh",
        "Doanh số cho vay tháng", "Doanh số thu nợ tháng",
    ]
    for col in tien_cols:
        if col in df_display.columns:
            df_display[col] = (df_display[col] / 1e6).round(1)

    hien_thi_dataframe_phan_trang(df_display, key="op_bao_cao_dvut_bang")
    st.caption("*Đơn vị tiền: triệu đồng*")

    st.divider()

    st.markdown("**③ Tóm tắt báo cáo**")
    dong_cong_data = df_bang[df_bang[COT_DVUT] == "CỘNG"].iloc[0]

    tong_dn = dong_cong_data.get("Tổng dư nợ", 0) / 1e6
    so_kh = int(dong_cong_data.get("Số KH", 0))
    so_to = int(dong_cong_data.get("Số Tổ", 0))
    nqh = dong_cong_data.get("Nợ quá hạn", 0) / 1e6
    nkh = dong_cong_data.get("Nợ khoanh", 0) / 1e6
    ds_cv = dong_cong_data.get("Doanh số cho vay tháng", 0) / 1e6
    ds_thu = dong_cong_data.get("Doanh số thu nợ tháng", 0) / 1e6

    don_vi_ten = f"{ten_dgd} ({chon_xa})"
    tom_tat_md = f"""
📌 **{don_vi_ten}** — Tổng dư nợ: **{tong_dn:,.0f}** triệu đồng

| Chỉ tiêu | Giá trị |
|---|---|
| Số KH | {so_kh} |
| Số Tổ | {so_to} |
| Nợ quá hạn | {nqh:,.0f} triệu |
| Nợ khoanh | {nkh:,.0f} triệu |
| Cho vay tháng | {ds_cv:,.0f} triệu |
| Thu nợ tháng | {ds_thu:,.0f} triệu |
    """
    st.markdown(tom_tat_md)
