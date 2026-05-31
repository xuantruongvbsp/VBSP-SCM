"""Cảnh báo sớm đầy đủ cho PGD — Migration & 3 tháng không hoạt động."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime

from config import (
    COT_TEN_XA, COT_DVUT, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
    COT_LAI_TON, COT_LAI_THANG, COT_LAI_TON_QH,
    TEMPLATES_DIR,
)
from data import danh_dau_khong_hd_cached, tong_hop_khong_hd_cached, canh_bao_migration_cached
from utils import fmt, fmt_so, fmt_ty, xuat_excel, hien_thi_dataframe_phan_trang, auto_fill_klgb, quet_templates
from components.delta_card import kpi_row
from state_manager import SCMStateManager
from logger import get_logger

logger = get_logger(__name__)


def render(tab=None, **kwargs) -> None:
    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")

    st.subheader("🚨 Cảnh báo sớm — Phân loại nợ & 3 tháng không HĐ")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD.")
        return

    df_kh = danh_dau_khong_hd_cached(df)

    tong_mon = len(df_kh)
    khd_tong = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    df_amber = canh_bao_migration_cached(df_kh)
    amber_tong = len(df_amber)
    tl_khd = khd_tong / tong_mon * 100 if tong_mon > 0 else 0
    tong_lai_khd = 0.0
    if not df_kh.empty and "is_3m_inactive" in df_kh.columns:
        df_khd_only = df_kh[df_kh["is_3m_inactive"]]
        for col in (COT_LAI_TON, COT_LAI_TON_QH):
            if col in df_kh.columns:
                tong_lai_khd += pd.to_numeric(df_khd_only[col], errors="coerce").fillna(0).sum()

    kpi_row([
        {"label": "Tổng món vay", "value": tong_mon, "icon": "📊", "suffix": "", "precision": 0,
         "help": f"Tổng số món vay {pgd_user or 'PGD'}"},
        {"label": "3 tháng KHĐ", "value": khd_tong, "icon": "🔴", "suffix": "", "precision": 0,
         "delta": tl_khd, "delta_label": "% tổng món", "delta_color": "inverse" if tl_khd > 2 else "off",
         "help": "Số món 3 tháng không hoạt động"},
        {"label": "Sắp chuyển KHĐ", "value": amber_tong, "icon": "⚠️", "suffix": "", "precision": 0,
         "delta_color": "off", "help": "Lãi tồn 2-3 tháng, cần đôn đốc ngay"},
        {"label": "Lãi tồn KHĐ", "value": tong_lai_khd, "icon": "💰", "suffix": "đồng", "precision": 0,
         "help": "Tổng lãi tồn các món 3 tháng KHĐ"},
    ], num_columns=4)

    st.divider()

    if COT_TEN_XA in df_kh.columns:
        st.markdown("**📋 Tổng hợp theo Xã/Phường**")
        nhom_xa = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_XA)
        if not nhom_xa.empty:
            hien_thi_dataframe_phan_trang(nhom_xa, key="pgd_khd_nhom_xa", height=300)

    st.markdown("**📋 Tổng hợp theo Hội đoàn thể (ĐVUT)**")
    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_DVUT)
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(nhom_dvut, key="pgd_khd_nhom_dvut", height=220)

    st.divider()

    st.markdown("**⚠️ Danh sách sắp chuyển 03 tháng không hoạt động — Đang tồn lãi 2–3 tháng (cần đôn đốc ngay)**")
    if not df_amber.empty:
        col_amber_loc, col_amber_xuat = st.columns([2, 1])
        with col_amber_loc:
            if COT_TEN_XA in df_amber.columns:
                ds_xa = ["Tất cả"] + sorted(df_amber[COT_TEN_XA].dropna().unique().tolist())
                loc_xa_a = st.selectbox("Lọc Xã", ds_xa, key="pgd_amber_xa")
            else:
                loc_xa_a = "Tất cả"
        with col_amber_xuat:
            st.markdown("<br>", unsafe_allow_html=True)
            if COT_TEN_XA in df_amber.columns and loc_xa_a != "Tất cả":
                df_amber_loc = df_amber[df_amber[COT_TEN_XA] == loc_xa_a]
            else:
                df_amber_loc = df_amber
            buf_a = xuat_excel({"SapChuyen3mKHD": df_amber_loc})
            st.download_button(
                f"⬇️ Xuất Excel Amber ({len(df_amber_loc)} món)",
                data=buf_a,
                file_name=f"SapChuyen3mKHD_{pgd_user or 'PGD'}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="pgd_cb_xuat_amber",
            )
        cols_hien = [c for c in [
            COT_TEN_XA, COT_DVUT, COT_TEN_KH,
            COT_SO_KU, COT_TEN_CT, COT_LAI_TON, COT_LAI_THANG,
            "so_thang_ton_uoc", "muc_canh_bao",
        ] if c in df_amber_loc.columns]
        hien_thi_dataframe_phan_trang(
            df_amber_loc[cols_hien] if cols_hien else df_amber_loc,
            key="pgd_amber_ds", height=320,
        )
    else:
        st.success("✅ Không có món vay nào sắp chuyển 03 tháng không hoạt động.")

    st.divider()

    st.markdown("**📄 Xuất Thông báo KL Giao ban (Bảng II tự động điền)**")
    templates = quet_templates(TEMPLATES_DIR)
    mau_klgb = [(t, p) for t, p in templates
                if "giao" in t.lower() or "kl" in t.lower() or "thong bao" in t.lower()]

    if not mau_klgb:
        st.info("⚠️ Chưa có mẫu KL giao ban trong thư mục `templates/`. "
                "Đặt file `.docx` vào thư mục đó và reload.")
    else:
        col_xa_kl, col_mau_kl = st.columns(2)
        with col_xa_kl:
            if COT_TEN_XA in df_kh.columns:
                ds_xa_kl = sorted(df_kh[COT_TEN_XA].dropna().unique().tolist())
                xa_kl = st.selectbox("Chọn Xã", ["Toàn PGD"] + ds_xa_kl, key="pgd_kl_xa")
            else:
                xa_kl = "Toàn PGD"
        with col_mau_kl:
            ten_mau_kl = st.selectbox("Mẫu biểu", [t[0] for t in mau_klgb], key="pgd_kl_mau")

        if st.button("🖨️ Tạo KL giao ban", type="primary", key="pgd_kl_btn"):
            try:
                if COT_TEN_XA in df_kh.columns and xa_kl != "Toàn PGD":
                    df_kl = df_kh[df_kh[COT_TEN_XA] == xa_kl]
                else:
                    df_kl = df_kh
                idx_mau = [t[0] for t in mau_klgb].index(ten_mau_kl)
                path_mau = mau_klgb[idx_mau][1]
                data = auto_fill_klgb(df_kl, str(path_mau), pgd_user or "")
                fname = f"KL_GiaoBan_{pgd_user or 'PGD'}_{xa_kl.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y')}.docx"
                state = SCMStateManager()
                state.downloads.set("pgd_kl_giao_ban_docx", data, fname)
                st.success("✅ Đã tạo xong — nhấn nút bên dưới để tải về.")
            except Exception as e:
                logger.error("Lỗi tạo KL giao ban PGD: %s", e, exc_info=True)
                st.error(f"Lỗi tạo KL giao ban: {e}")

        state = SCMStateManager()
        if state.downloads.has("pgd_kl_giao_ban_docx"):
            fname = state.downloads.get_filename("pgd_kl_giao_ban_docx") or "KL_GiaoBan.docx"
            if st.download_button(
                f"⬇️ Tải KL giao ban — {fname}",
                data=state.downloads.get_bytes("pgd_kl_giao_ban_docx"),
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="pgd_kl_dl",
            ):
                state.downloads.clear("pgd_kl_giao_ban_docx")
