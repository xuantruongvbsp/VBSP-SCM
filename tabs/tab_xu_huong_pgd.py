"""
Tab Phân tích Xu hướng — Phân hệ PGD.
────────────────────────────────────────
Phân tích xu hướng dư nợ 6 tháng qua:
  • Biểu đồ đường: Dư nợ, NQH, Giải ngân theo tháng
  • Phân tích tăng trưởng/tăng trưởng âm
  • So sánh với cùng kỳ năm trước (nếu có dữ liệu)
"""

from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

from datetime import datetime, timedelta
from io import BytesIO
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (
    COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH,
    COT_NGAY_VAY, COT_MA_KH
)
from utils import fmt_ty, fmt_so, hien_thi_dataframe_phan_trang
from auth import la_phan_he_pgd

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _tinh_xu_huong_6_thang(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tính xu hướng dư nợ 6 tháng từ dữ liệu HSTD hiện tại.
    Sử dụng Ngày vay để ước tính xu hướng.
    
    Returns:
        DataFrame với cột: Tháng, Tổng dư nợ, Dư nợ QH, Số khoản, Giải ngân mới
    """
    if df.empty or COT_NGAY_VAY not in df.columns:
        return pd.DataFrame()
    
    # Chuyển ngày vay thành datetime
    df = df.copy()
    df["ngay_vay_dt"] = pd.to_datetime(df[COT_NGAY_VAY], dayfirst=True, errors="coerce")
    
    # Tạo cột tháng-năm
    df["thang_nam"] = df["ngay_vay_dt"].dt.to_period("M").astype(str)
    
    # Lấy 6 tháng gần nhất
    today = datetime.now()
    six_months_ago = today - timedelta(days=180)
    
    # Kiểm tra các cột bắt buộc
    missing = [c for c in [COT_TONG_DU_NO, COT_DU_NO_QH] if c not in df.columns]
    if missing:
        logger.warning("_tinh_xu_huong_6_thang: thiếu cột %s", missing)
        return pd.DataFrame()

    df_loc = df[df["ngay_vay_dt"] >= six_months_ago]

    # Tổng hợp theo tháng — count riêng để tránh xung đột key
    agg_result = df_loc.groupby("thang_nam").agg(
        tong_du_no=(COT_TONG_DU_NO, "sum"),
        du_no_qh=(COT_DU_NO_QH, "sum"),
        so_khoan=(COT_MA_KH if COT_MA_KH in df.columns else COT_TONG_DU_NO, "count"),
    ).reset_index()

    result = agg_result.rename(columns={
        "thang_nam": "Tháng",
        "tong_du_no": "Tổng dư nợ",
        "du_no_qh": "Dư nợ QH",
        "so_khoan": "Số khoản",
    })
    
    # Sắp xếp theo tháng
    result["thang_sort"] = pd.to_datetime(result["Tháng"], format="%Y-%m")
    result = result.sort_values("thang_sort")
    
    # Tính tỷ lệ NQH
    result["Tỷ lệ QH %"] = (result["Dư nợ QH"] / result["Tổng dư nợ"] * 100).round(2)
    
    return result


def _render_kpi_xu_huong(df: pd.DataFrame) -> None:
    """Render KPI xu hướng."""
    if df.empty or len(df) < 2:
        st.info("ℹ️ Chưa đủ dữ liệu 2 tháng để phân tích xu hướng")
        return
    
    # Lấy tháng đầu và cuối
    first_month = df.iloc[0]
    last_month = df.iloc[-1]
    
    # Tính thay đổi
    delta_du_no = last_month["Tổng dư nợ"] - first_month["Tổng dư nợ"]
    delta_qh = last_month["Dư nợ QH"] - first_month["Dư nợ QH"]
    delta_so = last_month["Số khoản"] - first_month["Số khoản"]
    
    pct_du_no = (delta_du_no / first_month["Tổng dư nợ"] * 100) if first_month["Tổng dư nợ"] > 0 else 0
    pct_qh = (delta_qh / first_month["Dư nợ QH"] * 100) if first_month["Dư nợ QH"] > 0 else 0
    
    cols = st.columns(4)
    with cols[0]:
        st.metric(
            "📈 Dư nợ (6 tháng)",
            fmt_ty(last_month["Tổng dư nợ"]),
            delta=f"{pct_du_no:+.1f}%",
            delta_color="normal" if delta_du_no >= 0 else "inverse"
        )
    with cols[1]:
        st.metric(
            "⚠️ NQH (6 tháng)",
            fmt_ty(last_month["Dư nợ QH"]),
            delta=f"{pct_qh:+.1f}%",
            delta_color="inverse"  # NQH tăng là xấu
        )
    with cols[2]:
        st.metric(
            "📊 Số khoản",
            fmt_so(int(last_month["Số khoản"])),
            delta=f"{delta_so:+d}",
            delta_color="normal" if delta_so >= 0 else "inverse"
        )
    with cols[3]:
        ty_le_qh = last_month.get("Tỷ lệ QH %", 0)
        st.metric("📉 Tỷ lệ QH", f"{ty_le_qh:.2f}%")


def _render_chart_xu_huong(df: pd.DataFrame) -> None:
    """Render biểu đồ xu hướng."""
    if df.empty:
        return
    
    st.subheader("📈 Biểu đồ xu hướng 6 tháng")
    
    # Tạo figure với 2 subplots
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Dư nợ theo thời gian", "Tỷ lệ NQH theo thời gian"),
        vertical_spacing=0.15
    )
    
    # Biểu đồ 1: Dư nợ
    fig.add_trace(
        go.Scatter(
            x=df["Tháng"],
            y=df[COT_TONG_DU_NO],
            mode="lines+markers",
            name="Tổng dư nợ",
            line=dict(color="#1f77b4", width=3),
            marker=dict(size=8)
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df["Tháng"],
            y=df["Dư nợ QH"],
            mode="lines+markers",
            name="Dư nợ QH",
            line=dict(color="#ff7f0e", width=2, dash="dash"),
            marker=dict(size=6)
        ),
        row=1, col=1
    )
    
    # Biểu đồ 2: Tỷ lệ QH
    fig.add_trace(
        go.Bar(
            x=df["Tháng"],
            y=df["Tỷ lệ QH %"],
            name="Tỷ lệ QH %",
            marker_color="#d62728"
        ),
        row=2, col=1
    )
    
    # Layout
    fig.update_layout(
        height=600,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_xaxes(title_text="Tháng", row=2, col=1)
    fig.update_yaxes(title_text="Dư nợ (VNĐ)", row=1, col=1)
    fig.update_yaxes(title_text="Tỷ lệ QH (%)", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)


def _render_bang_xu_huong(df: pd.DataFrame) -> None:
    """Render bảng xu hướng chi tiết."""
    st.subheader("📋 Bảng xu hướng chi tiết")
    
    # Format số liệu
    df_display = df.copy()
    df_display["Tổng dư nợ"] = df_display["Tổng dư nợ"].apply(fmt_ty)
    df_display["Dư nợ QH"] = df_display["Dư nợ QH"].apply(fmt_ty)
    df_display["Tỷ lệ QH %"] = df_display["Tỷ lệ QH %"].apply(lambda x: f"{x:.2f}%")
    df_display["Số khoản"] = df_display["Số khoản"].apply(lambda x: fmt_so(int(x)))
    
    # Thêm cột đánh giá
    def danh_gia(row):
        if row["Tỷ lệ QH %"] > 5:
            return "🔴 Cao"
        elif row["Tỷ lệ QH %"] > 2:
            return "🟡 TB"
        return "🟢 Tốt"
    
    df_display["Đánh giá"] = df.apply(danh_gia, axis=1)
    
    # Bỏ cột sort
    if "thang_sort" in df_display.columns:
        df_display = df_display.drop(columns=["thang_sort"])
    
    hien_thi_dataframe_phan_trang(df_display, key="xu_huong_pgd_bang")


def _render_phan_tich_tang_truong(df: pd.DataFrame) -> None:
    """Render phân tích tăng trưởng."""
    if len(df) < 2:
        return

    st.subheader("📊 Phân tích tăng trưởng")

    # Tính tăng trưởng tháng-tháng — dùng copy để tránh mutate caller
    df = df.copy()
    df["Tăng trưởng DN"] = df[COT_TONG_DU_NO].pct_change() * 100
    df["Tăng trưởng QH"] = df["Dư nợ QH"].pct_change() * 100
    
    # Tìm tháng tăng trưởng cao nhất/thấp nhất
    max_growth = df.loc[df["Tăng trưởng DN"].idxmax()]
    min_growth = df.loc[df["Tăng trưởng DN"].idxmin()]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "📈 Tăng trưởng cao nhất",
            f"{max_growth['Tăng trưởng DN']:.1f}%",
            delta=f"Tháng {max_growth['Tháng']}"
        )
    
    with col2:
        st.metric(
            "📉 Tăng trưởng thấp nhất",
            f"{min_growth['Tăng trưởng DN']:.1f}%",
            delta=f"Tháng {min_growth['Tháng']}"
        )
    
    # Biểu đồ tăng trưởng
    fig = px.bar(
        df.dropna(subset=["Tăng trưởng DN"]),
        x="Tháng",
        y="Tăng trưởng DN",
        title="Tăng trưởng dư nợ tháng-tháng (%)",
        color="Tăng trưởng DN",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def render(tab=None, **kwargs) -> None:
    """
    Render tab Phân tích Xu hướng cho PGD.
    
    Args:
        tab: Streamlit container
        **kwargs: Bao gồm df, pgd_user, role, username
    """
    ctx = tab if tab is not None else st
    
    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")
    role = kwargs.get("role", "")
    username = kwargs.get("username", "")
    
    ctx.header("📈 Phân tích Xu hướng")
    ctx.caption(f"PGD: **{pgd_user or 'Chưa xác định'}** — Phân tích 6 tháng gần nhất")
    
    # Kiểm tra dữ liệu
    if df is None or df.empty:
        ctx.info("ℹ️ Chưa có dữ liệu HSTD. Vui lòng upload dữ liệu tại tab **Upload Dữ liệu**.")
        return
    
    # Tính xu hướng
    df_xu_huong = _tinh_xu_huong_6_thang(df)
    
    if df_xu_huong.empty:
        ctx.warning("⚠️ Không thể tính xu hướng. Cần có cột 'Ngày vay' trong dữ liệu HSTD.")
        return
    
    # KPI
    _render_kpi_xu_huong(df_xu_huong)
    
    ctx.divider()
    
    # Tabs
    tab1, tab2, tab3 = ctx.tabs(["📊 Biểu đồ", "📋 Bảng số liệu", "📈 Tăng trưởng"])
    
    with tab1:
        _render_chart_xu_huong(df_xu_huong)
    
    with tab2:
        _render_bang_xu_huong(df_xu_huong)
    
    with tab3:
        _render_phan_tich_tang_truong(df_xu_huong)
    
    # Export
    ctx.divider()
    if ctx.button("📥 Xuất Excel", key="xu_huong_pgd_export"):
        try:
            buf = BytesIO()
            df_xu_huong.to_excel(buf, index=False, engine="openpyxl")
            buf.seek(0)
            ctx.download_button(
                label="⬇️ Tải xuống",
                data=buf.getvalue(),
                file_name=f"XuHuong_{pgd_user}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="xu_huong_pgd_download"
            )
        except Exception as e:
            logger.error("Lỗi xuất Excel: %s", e, exc_info=True)
            ctx.error("❌ Không thể xuất Excel")


def render_tab(tab=None, **kwargs) -> None:
    """Alias cho render() để tương thích với lazy_tabs."""
    render(tab, **kwargs)
