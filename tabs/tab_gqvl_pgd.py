"""
Tab Giải quyết Việc làm (GQVL) — Phân hệ PGD.
──────────────────────────────────────────────
Dashboard GQVL cho CBTD địa bàn:
  • Theo dõi chỉ tiêu GQVL theo xã
  • Phân tích dư nợ, giải ngân GQVL
  • So sánh với kế hoạch (nếu có)
"""

from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

from io import BytesIO
from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.express as px

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TONG_DU_NO,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_MA_KH, COT_TEN_KH,
)
from data import doc_gqvl_pgd, ds_pgd_co_gqvl, ts_file
from data.pgd import duong_dan_pgd
from utils import fmt_ty, fmt_so, hien_thi_dataframe_phan_trang
from auth import la_phan_he_pgd

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _tinh_ty_le_qh(du_no_th: float, du_no_qh: float) -> float:
    """Tính tỷ lệ quá hạn."""
    tong = du_no_th + du_no_qh
    return (du_no_qh / tong * 100) if tong > 0 else 0.0


def _render_kpi_gqvl(df_gqvl: pd.DataFrame) -> None:
    """Render các KPI cards cho GQVL."""
    if df_gqvl.empty:
        st.info("ℹ️ Chưa có dữ liệu GQVL")
        return
    
    # Tính KPI — dùng COT_* constants, tránh hardcode tên cột với gạch dưới
    tong_ho = len(df_gqvl)
    tong_du_no = pd.to_numeric(df_gqvl[COT_TONG_DU_NO], errors="coerce").sum() if COT_TONG_DU_NO in df_gqvl.columns else 0.0
    du_no_th  = pd.to_numeric(df_gqvl[COT_DU_NO_TH],    errors="coerce").sum() if COT_DU_NO_TH   in df_gqvl.columns else 0.0
    du_no_qh  = pd.to_numeric(df_gqvl[COT_DU_NO_QH],    errors="coerce").sum() if COT_DU_NO_QH   in df_gqvl.columns else 0.0
    ty_le_qh = _tinh_ty_le_qh(du_no_th, du_no_qh)
    
    # Hiển thị KPI
    cols = st.columns(4)
    with cols[0]:
        st.metric("👥 Tổng hộ vay", fmt_so(tong_ho))
    with cols[1]:
        st.metric("💰 Tổng dư nợ", fmt_ty(tong_du_no))
    with cols[2]:
        st.metric("✅ Dư nợ TH", fmt_ty(du_no_th))
    with cols[3]:
        st.metric("⚠️ Tỷ lệ QH", f"{ty_le_qh:.2f}%", 
                 delta=None if ty_le_qh < 5 else "⚠️ Cao",
                 delta_color="inverse")


def _render_bang_theo_xa(df_gqvl: pd.DataFrame, pgd_user: str) -> None:
    """Render bảng tổng hợp GQVL theo xã."""
    if df_gqvl.empty or COT_TEN_XA not in df_gqvl.columns:
        return
    
    st.subheader("📊 Tổng hợp theo Xã")

    # Build agg_dict từ cột thực tế — tránh hardcode tên cột với gạch dưới
    agg_dict = {}
    if COT_MA_KH in df_gqvl.columns:
        agg_dict[COT_MA_KH] = "count"
    for c in [COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH]:
        if c in df_gqvl.columns:
            agg_dict[c] = "sum"

    if not agg_dict:
        st.info("ℹ️ Không đủ cột để tổng hợp theo xã.")
        return

    try:
        grouped = df_gqvl.groupby(COT_TEN_XA).agg(agg_dict).reset_index()
    except Exception as e:
        logger.error("_render_bang_theo_xa agg: %s", e, exc_info=True)
        st.error(f"❌ Lỗi tổng hợp: {e}")
        return

    # Đổi tên cột hiển thị
    rename_map = {
        COT_MA_KH: "Số hộ", COT_TONG_DU_NO: "Tổng dư nợ",
        COT_DU_NO_TH: "Dư nợ TH", COT_DU_NO_QH: "Dư nợ QH", COT_TEN_XA: "Xã",
    }
    grouped = grouped.rename(columns={k: v for k, v in rename_map.items() if k in grouped.columns})

    # Tính tỷ lệ QH nếu có đủ cột
    if "Dư nợ TH" in grouped.columns and "Dư nợ QH" in grouped.columns:
        grouped["Tỷ lệ QH %"] = grouped.apply(
            lambda r: _tinh_ty_le_qh(r["Dư nợ TH"], r["Dư nợ QH"]), axis=1
        ).round(2)

    # Format tiền tệ
    for col in ["Tổng dư nợ", "Dư nợ TH", "Dư nợ QH"]:
        if col in grouped.columns:
            grouped[col] = grouped[col].apply(fmt_ty)
    if "Tỷ lệ QH %" in grouped.columns:
        grouped["Tỷ lệ QH %"] = grouped["Tỷ lệ QH %"].apply(lambda x: f"{x:.2f}%")

    hien_thi_dataframe_phan_trang(grouped, key="gqvl_pgd_bang_xa")


def _render_chart_gqvl(df_gqvl: pd.DataFrame) -> None:
    """Render biểu đồ GQVL."""
    if df_gqvl.empty:
        return
    
    st.subheader("📈 Biểu đồ phân tích")
    
    tab1, tab2 = st.tabs(["Cơ cấu theo xã", "Dư nợ vs Giải ngân"])
    
    with tab1:
        if COT_TEN_XA in df_gqvl.columns and COT_TONG_DU_NO in df_gqvl.columns:
            df_xa = df_gqvl.groupby(COT_TEN_XA)[COT_TONG_DU_NO].sum().reset_index()
            df_xa.columns = ["Xã", "Tổng dư nợ"]

            fig = px.pie(df_xa, values="Tổng dư nợ", names="Xã",
                        title="Cơ cấu dư nợ GQVL theo Xã",
                        hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ℹ️ Không có dữ liệu xã hoặc cột dư nợ")

    with tab2:
        if COT_TONG_DU_NO in df_gqvl.columns and COT_TEN_XA in df_gqvl.columns:
            comp_agg = {COT_TONG_DU_NO: "sum"}
            if COT_DU_NO_QH in df_gqvl.columns:
                comp_agg[COT_DU_NO_QH] = "sum"
            df_comp = df_gqvl.groupby(COT_TEN_XA).agg(comp_agg).reset_index()
            df_comp = df_comp.rename(columns={
                COT_TEN_XA: "Xã", COT_TONG_DU_NO: "Tổng dư nợ", COT_DU_NO_QH: "Dư nợ QH",
            })
            y_cols = [c for c in ["Tổng dư nợ", "Dư nợ QH"] if c in df_comp.columns]
            fig = px.bar(df_comp, x="Xã", y=y_cols,
                        title="Dư nợ & NQH theo Xã",
                        barmode="group")
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ℹ️ Không đủ dữ liệu để vẽ biểu đồ")


def _render_chi_tiet_gqvl(df_gqvl: pd.DataFrame) -> None:
    """Render bảng chi tiết GQVL."""
    st.subheader("📋 Chi tiết hộ vay GQVL")
    
    # Lọc cột hiển thị — dùng COT_* constants thay vì hardcode tên cột gạch dưới
    cols_display = [c for c in [COT_MA_KH, COT_TEN_KH, COT_TEN_XA,
                                COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH]
                   if c in df_gqvl.columns]
    
    if not cols_display:
        cols_display = df_gqvl.columns[:10].tolist()
    
    df_display = df_gqvl[cols_display].copy()
    
    # Format
    for col in df_display.columns:
        if any(x in col.lower() for x in ["dư nợ", "giải ngân", "tổng", "tiền"]):
            df_display[col] = df_display[col].apply(lambda x: fmt_ty(x) if pd.notna(x) else "")
    
    hien_thi_dataframe_phan_trang(df_display, key="gqvl_pgd_chi_tiet")


def render(tab=None, **kwargs) -> None:
    """
    Render tab GQVL cho PGD.
    
    Args:
        tab: Streamlit container
        **kwargs: Bao gồm df, pgd_user, role, username
    """
    ctx = tab if tab is not None else st
    
    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")
    role = kwargs.get("role", "")
    username = kwargs.get("username", "")
    
    ctx.header("📋 Giải quyết Việc làm (GQVL)")
    ctx.caption(f"PGD: **{pgd_user or 'Chưa xác định'}**")
    
    # Kiểm tra có phải phân hệ PGD
    if not la_phan_he_pgd(role):
        ctx.warning("⚠️ Tab này chỉ dành cho phân hệ PGD.")
        return
    
    # Đọc dữ liệu GQVL — doc_gqvl_pgd yêu cầu _ts để bust cache khi file thay đổi
    try:
        if pgd_user:
            _path = duong_dan_pgd(pgd_user, "gqvl")
            _ts = ts_file(_path)
            df_gqvl = doc_gqvl_pgd(pgd_user, _ts) or pd.DataFrame()
        else:
            df_gqvl = pd.DataFrame()
    except Exception as e:
        logger.error("Lỗi đọc GQVL PGD: %s", e, exc_info=True)
        df_gqvl = pd.DataFrame()
    
    if df_gqvl.empty:
        ctx.info("ℹ️ Chưa có dữ liệu GQVL. Vui lòng upload file GQVL tại tab **Upload Dữ liệu**.")
        return
    
    # KPI
    _render_kpi_gqvl(df_gqvl)
    
    ctx.divider()
    
    # Tabs con
    tab_tonghop, tab_chitiet = ctx.tabs(["📊 Tổng hợp", "📋 Chi tiết"])
    
    with tab_tonghop:
        _render_bang_theo_xa(df_gqvl, pgd_user)
        _render_chart_gqvl(df_gqvl)
    
    with tab_chitiet:
        _render_chi_tiet_gqvl(df_gqvl)
    
    # Export
    ctx.divider()
    col1, col2 = ctx.columns([1, 3])
    with col1:
        if ctx.button("📥 Xuất Excel", key="gqvl_pgd_export"):
            try:
                buf = BytesIO()
                df_gqvl.to_excel(buf, index=False, engine="openpyxl")
                buf.seek(0)
                ctx.download_button(
                    label="⬇️ Tải xuống",
                    data=buf.getvalue(),
                    file_name=f"GQVL_{pgd_user}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="gqvl_pgd_download"
                )
            except Exception as e:
                logger.error("Lỗi xuất Excel GQVL: %s", e, exc_info=True)
                ctx.error("❌ Không thể xuất Excel")


def render_tab(tab=None, **kwargs) -> None:
    """Alias cho render() để tương thích với lazy_tabs."""
    render(tab, **kwargs)
