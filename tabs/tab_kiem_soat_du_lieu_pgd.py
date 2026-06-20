"""Kiểm soát nội bộ PGD — xem dữ liệu 3 tháng KHĐ và NQH cho 1 PGD."""
from __future__ import annotations

from datetime import datetime

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from config import (
    COT_TEN_XA, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_NGAY_DH,
)
from data import (
    danh_dau_khong_hd_cached, tong_hop_khong_hd_cached, ds_chi_tiet_khong_hd,
)
from utils import hien_thi_dataframe_phan_trang, xuat_excel
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Kiểm soát nội bộ PGD — Phiên bản rút gọn, chỉ xem dữ liệu 1 PGD."""
    df_pgd   = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")
    role     = kwargs.get("role")
    username = kwargs.get("username", "")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🔍 Kiểm soát Nội bộ PGD")
        st.caption(f"Phạm vi: **{pgd_user or 'PGD'}** — Chế độ chỉ xem")

        if df_pgd is None or df_pgd.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return

        cache_key = (pgd_user or "", len(df_pgd))
        ks_pgd_key = f"ks_pgd_cache_{pgd_user or 'all'}"
        ks = st.session_state.get(ks_pgd_key, {})

        if ks.get("_key") != cache_key:
            with st.spinner("Đang phân tích dữ liệu PGD..."):
                df_kh = danh_dau_khong_hd_cached(df_pgd)

                df_khd_xa = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_XA) if COT_TEN_XA in df_kh.columns else pd.DataFrame()
                df_khd_chi = ds_chi_tiet_khong_hd(df_kh)

                if COT_DU_NO_QH in df_kh.columns and COT_TEN_XA in df_kh.columns:
                    df_nqh_xa = df_kh[df_kh[COT_DU_NO_QH] > 0].groupby(COT_TEN_XA).agg({
                        COT_SO_KU: "count",
                        COT_DU_NO_QH: "sum",
                        COT_TONG_DU_NO: "sum"
                    }).reset_index()
                    if not df_nqh_xa.empty:
                        df_nqh_xa["Tỷ_lệ_QH_%"] = (
                            df_nqh_xa[COT_DU_NO_QH] /
                            df_nqh_xa[COT_TONG_DU_NO].replace(0, pd.NA) * 100
                        ).round(1).fillna(0)
                else:
                    df_nqh_xa = pd.DataFrame()

                mask_nqh = df_kh[COT_DU_NO_QH] > 0 if COT_DU_NO_QH in df_kh.columns else pd.Series([False] * len(df_kh))
                cols_nqh = [c for c in [COT_TEN_XA, COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_DU_NO_QH, COT_TONG_DU_NO, COT_NGAY_DH] if c in df_kh.columns]
                df_nqh_chi = df_kh[mask_nqh][cols_nqh] if cols_nqh else pd.DataFrame()

                ks = {
                    "_key": cache_key,
                    "df_kh": df_kh,
                    "df_khd_xa": df_khd_xa,
                    "df_khd_chi": df_khd_chi,
                    "df_nqh_xa": df_nqh_xa,
                    "df_nqh_chi": df_nqh_chi,
                }
                st.session_state[ks_pgd_key] = ks

        tab_3mkhd, tab_nqh = st.tabs(["📋 3 tháng KHĐ", "⚠️ Nợ Quá Hạn"])

        with tab_3mkhd:
            st.markdown("**📊 Tổng hợp theo Xã**")
            if not ks["df_khd_xa"].empty:
                hien_thi_dataframe_phan_trang(ks["df_khd_xa"], key="pgd_ks_khd_xa", height=280)
            else:
                st.info("Không có dữ liệu 3 tháng KHĐ theo xã.")

            st.divider()
            st.markdown("**📋 Chi tiết**")
            if not ks["df_khd_chi"].empty:
                hien_thi_dataframe_phan_trang(ks["df_khd_chi"], key="pgd_ks_khd_chi", height=320)
            else:
                st.success("✅ Không có món vay 3 tháng không hoạt động.")

        with tab_nqh:
            st.markdown("**📊 Tổng hợp theo Xã**")
            if not ks["df_nqh_xa"].empty:
                hien_thi_dataframe_phan_trang(ks["df_nqh_xa"], key="pgd_ks_nqh_xa", height=280)
            else:
                st.info("Không có dữ liệu NQH theo xã.")

            st.divider()
            st.markdown("**📋 Chi tiết**")
            if not ks["df_nqh_chi"].empty:
                hien_thi_dataframe_phan_trang(ks["df_nqh_chi"], key="pgd_ks_nqh_chi", height=320)
            else:
                st.success("✅ Không có nợ quá hạn.")

        st.divider()
        col_x1, col_x2 = st.columns(2)
        with col_x1:
            if not ks["df_khd_xa"].empty:
                buf_khd = xuat_excel({"3m_KHD_theo_Xa": ks["df_khd_xa"], "Chi_tiet_3m_KHD": ks["df_khd_chi"]})
                st.download_button(
                    "⬇️ Xuất Excel 3 tháng KHĐ",
                    data=buf_khd,
                    file_name=f"KiemSoat_3mKHD_{pgd_user or 'PGD'}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="pgd_ks_xuat_khd",
                )
        with col_x2:
            if not ks["df_nqh_xa"].empty:
                buf_nqh = xuat_excel({"NQH_theo_Xa": ks["df_nqh_xa"], "Chi_tiet_NQH": ks["df_nqh_chi"]})
                st.download_button(
                    "⬇️ Xuất Excel NQH",
                    data=buf_nqh,
                    file_name=f"KiemSoat_NQH_{pgd_user or 'PGD'}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="pgd_ks_xuat_nqh",
                )
