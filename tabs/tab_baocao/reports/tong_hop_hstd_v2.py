"""Báo cáo tổng hợp từ HSTD v2 - UX nâng cao."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON, COT_TEN_CT,
    COT_NGUON_VON, COT_DVUT, COT_TEN_TO,
    COT_MA_KH, COT_SO_KU, COT_TONG_DU_NO,
    COT_DU_NO_TH, COT_DU_NO_QH,
)
from auth import la_phan_he_pgd
from utils import fmt_ty, vn

from ..components.inline_filter import render_combined_filter_search
from ..components.sticky_table import render_sticky_table
from ..components.quick_export import render_quick_export_buttons
from ..components.tooltip import render_header_with_tooltip, render_formula_reference
from ..components.alert_suggestion import render_combined_alerts_suggestions
from logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _fmt_df_trieu(df: pd.DataFrame) -> pd.DataFrame:
    """Format cột tiền sang triệu đồng."""
    d = df.copy()
    tien_cols = ["Tổng_dư_nợ", "Dư_nợ_trong_hạn", "Dư_nợ_quá_hạn"]
    for col in tien_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
    return d


def render_tong_hop_hstd_v2(
    tab: DeltaGenerator | None = None,
    df: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    specific_report: str | None = None,
    **kwargs
) -> None:
    """
    Render báo cáo tổng hợp từ HSTD với UX nâng cao.
    
    Args:
        tab: Streamlit container
        df: DataFrame HSTD
        role: Role người dùng
        pgd_user: Tên PGD
        username: Username
        specific_report: Key của báo cáo cụ thể (pgd, xa, thon, ct, nv, dvut, cbtd)
    """
    ctx = tab if tab is not None else st
    
    if df is None or df.empty:
        ctx.warning("⚠️ Chưa có dữ liệu HSTD.")
        return
    
    # Cảnh báo và gợi ý
    render_combined_alerts_suggestions(df, container=ctx)
    ctx.divider()
    
    # Xác định báo cáo cần render
    report_options = {
        "pgd": ("🏢 Theo PGD", COT_TEN_PGD),
        "xa": ("🏘️ Theo Xã", COT_TEN_XA),
        "thon": ("🏡 Theo Thôn/ấp", COT_TEN_THON),
        "ct": ("📌 Theo Chương trình", COT_TEN_CT),
        "nv": ("🏦 Theo Nguồn vốn", COT_NGUON_VON),
        "dvut": ("🤝 Theo ĐVUT", COT_DVUT),
        "cbtd": ("👤 Theo CBTD/Tổ", COT_TEN_TO),
    }
    
    # Nếu không chỉ định, cho phép chọn
    if specific_report is None or specific_report not in report_options:
        col1, col2 = ctx.columns([2, 1])
        with col1:
            selected_report = ctx.radio(
                "Tổng hợp theo",
                list(report_options.keys()),
                format_func=lambda k: report_options[k][0],
                horizontal=True,
                key="th_loai_hstd_v2",
            )
        with col2:
            render_formula_reference(ctx)
    else:
        selected_report = specific_report
    
    report_label, group_col = report_options[selected_report]
    
    # Kiểm tra cột tồn tại
    if group_col not in df.columns:
        ctx.error(f"❌ Không có cột {group_col} trong dữ liệu.")
        return
    
    # Bộ lọc PGD
    df_filtered = df.copy()
    if la_phan_he_pgd(role) and pgd_user:
        if COT_TEN_PGD in df_filtered.columns:
            df_filtered = df_filtered[df_filtered[COT_TEN_PGD] == pgd_user]
            ctx.info(f"📍 Đang xem báo cáo của PGD: **{pgd_user}**")
    
    # Inline filter và search
    ctx.markdown(f"### {report_label}")
    
    # Xác định cột filter
    filter_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT] if c in df_filtered.columns and c != group_col]
    search_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_MA_KH] if c in df_filtered.columns]
    
    df_filtered = render_combined_filter_search(
        df_filtered,
        filter_cols[:2],  # Tối đa 2 filter
        search_cols,
        key=f"th_{selected_report}",
        container=ctx,
    )
    
    # Tạo báo cáo tổng hợp
    try:
        df_th = df_filtered.groupby(group_col).agg(
            Số_KH=(COT_MA_KH, "nunique"),
            Số_món=(COT_SO_KU, "nunique"),
            Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
            Dư_nợ_trong_hạn=(COT_DU_NO_TH, "sum"),
            Dư_nợ_quá_hạn=(COT_DU_NO_QH, "sum"),
        ).reset_index()
        
        # Tính tỷ lệ QH
        df_th["Tỷ_lệ_QH_%"] = (
            df_th["Dư_nợ_quá_hạn"] / df_th["Tổng_dư_nợ"].replace(0, float("nan")) * 100
        ).round(2).fillna(0)
        
        # Sắp xếp
        df_th = df_th.sort_values("Tổng_dư_nợ", ascending=False)
        
        # Metrics
        col1, col2, col3, col4 = ctx.columns(4)
        col1.metric("Số nhóm", fmt_ty(len(df_th)))
        col2.metric("Tổng dư nợ", f"{df_th['Tổng_dư_nợ'].sum()/1e9:.1f} tỷ".replace(".", ","))
        col3.metric("Tổng KH", fmt_ty(df_th['Số_KH'].sum()))
        
        ty_le_qh_tb = (df_th['Dư_nợ_quá_hạn'].sum() / df_th['Tổng_dư_nợ'].sum() * 100) if df_th['Tổng_dư_nợ'].sum() > 0 else 0
        col4.metric("Tỷ lệ QH TB", f"{ty_le_qh_tb:.2f}%".replace(".", ","))
        
        ctx.divider()
        
        # Quick export
        render_quick_export_buttons(
            df_th,
            f"TongHop_{selected_report}",
            f"Báo cáo tổng hợp {report_label}",
            username,
            f"BC_TH_{selected_report.upper()}",
            key=f"th_{selected_report}",
            container=ctx,
        )
        
        # Bảng với sticky header
        render_header_with_tooltip(
            "📊 Chi tiết",
            tooltip_key="Tổng dư nợ",
            container=ctx,
        )
        
        render_sticky_table(
            _fmt_df_trieu(df_th),
            key=f"th_table_{selected_report}",
            height=400,
            container=ctx,
        )
        
    except Exception as e:
        logger.error("tong_hop_hstd_v2: lỗi tạo báo cáo — %s", e, exc_info=True)
        ctx.error(f"❌ Lỗi tạo báo cáo: {e}")
