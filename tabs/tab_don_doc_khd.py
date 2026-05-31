"""Đôn đốc 3 tháng không hoạt động — CBTD địa bàn PGD."""
from __future__ import annotations

import streamlit as st
import pandas as pd

from config import COT_TEN_XA, COT_DVUT, COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_LAI_TON
from data import danh_dau_khong_hd_cached, tong_hop_khong_hd_cached, ds_chi_tiet_khong_hd
from utils import fmt, fmt_so, fmt_ty, hien_thi_dataframe_phan_trang
from components.loan_drawer import loan_detail_drawer
from logger import get_logger

logger = get_logger(__name__)


def render(tab=None, **kwargs) -> None:
    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")
    role = kwargs.get("role", "user")

    st.subheader("🔴 Món vay 3 tháng không hoạt động")
    st.caption("Lãi tồn > 3 tháng lãi dự thu — cần đôn đốc thu hồi trước khi phát sinh NQH")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu.")
        return

    df_kh = danh_dau_khong_hd_cached(df)
    n_khd = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    n_tong = len(df_kh)

    k1, k2, k3 = st.columns(3)
    k1.metric("Tổng món vay", fmt_so(n_tong))
    k2.metric(
        "Cần đôn đốc 🔴", fmt_so(n_khd),
        delta=f"{n_khd / n_tong * 100:.1f}% tổng món" if n_tong > 0 else "0%",
        delta_color="inverse" if n_khd > 0 else "off",
    )
    tong_lai = (
        df_kh[df_kh.get("is_3m_inactive", False)][COT_LAI_TON].sum()
        if COT_LAI_TON in df_kh.columns else 0
    )
    k3.metric("Lãi tồn cần thu (đồng)", fmt(tong_lai))

    if n_khd == 0:
        st.success("✅ Không có món vay nào quá 3 tháng không hoạt động!")
        return

    st.divider()

    st.markdown("**Tổng hợp theo Hội đoàn thể (ĐVUT)**")
    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_DVUT)
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(nhom_dvut, key="op_khd_nhom_dvut", height=220)

    st.markdown("**Tổng hợp theo Xã/Phường**")
    nhom_xa = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_XA)
    if not nhom_xa.empty:
        hien_thi_dataframe_phan_trang(nhom_xa, key="op_khd_nhom_xa", height=220)

    st.divider()

    st.markdown("**📋 Danh sách hộ cần đôn đốc**")
    col_loc, col_xuat = st.columns([2, 1])

    with col_loc:
        ds_dvut = ["Tất cả"]
        if COT_DVUT in df_kh.columns:
            ds_dvut += sorted(df_kh[COT_DVUT].dropna().unique().tolist())
        chon_dvut = st.selectbox("Lọc Hội đoàn thể", ds_dvut, key="op_khd_dvut")

    gia_tri = None if chon_dvut == "Tất cả" else chon_dvut
    df_dondoc = ds_chi_tiet_khong_hd(df_kh, nhom_theo=COT_DVUT, gia_tri_nhom=gia_tri)

    with col_xuat:
        st.markdown("<br>", unsafe_allow_html=True)
        if not df_dondoc.empty:
            from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
            kpi_don_doc = [
                ("Số hộ KHĐ", fmt_so(len(df_dondoc)), f"Lọc: {chon_dvut}"),
            ]
            if COT_LAI_TON in df_dondoc.columns:
                kpi_don_doc.append(("Lãi tồn", fmt_ty(df_dondoc[COT_LAI_TON].sum()), "triệu đồng"))
            st.download_button(
                label=f"⬇️ Xuất Excel chuyên nghiệp ({len(df_dondoc)} hộ)",
                type="primary",
                data=xuat_excel_chuyen_nghiep(
                    df=df_dondoc,
                    title="Danh sách Đôn đốc 3 tháng KHĐ",
                    subtitle=f"PGD: {pgd_user} - {chon_dvut}",
                    nguoi_xuat=st.session_state.get("txt_username", ""),
                    kpi_items=kpi_don_doc,
                ),
                file_name=excel_ten_file("DonDoc_3m_KHD"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="op_xuat_khd_pro",
            )

    if not df_dondoc.empty:
        hien_thi_dataframe_phan_trang(df_dondoc, key="op_khd_dondoc", height=360)
        tong_lai_ds = (
            df_dondoc[COT_LAI_TON].sum()
            if COT_LAI_TON in df_dondoc.columns else 0
        )
        st.caption(
            f"**{fmt_so(len(df_dondoc))}** món · "
            f"Lãi tồn: **{fmt(tong_lai_ds)}** triệu đồng"
        )

        st.divider()
        st.markdown("**🔍 Tra cứu chi tiết khoản vay**")
        cols_chon = [c for c in [COT_SO_KU, COT_TEN_KH, COT_TEN_CT] if c in df_dondoc.columns]
        if cols_chon:
            df_chon = df_dondoc.copy()
            df_chon["_hien_thi"] = df_chon[cols_chon[0]].astype(str)
            if len(cols_chon) > 1:
                for c in cols_chon[1:]:
                    df_chon["_hien_thi"] += " | " + df_chon[c].astype(str)
            options = dict(zip(df_chon["_hien_thi"], df_dondoc.index))
            selected_label = st.selectbox(
                "Chọn khoản vay để xem chi tiết",
                options=list(options.keys()),
                key="op_khd_chon_drawer",
            )
            if selected_label:
                row_idx = options[selected_label]
                row_data = df_dondoc.loc[row_idx]
                loan_detail_drawer(row_data)
    else:
        st.info("Không có hộ nào thỏa điều kiện.")
