"""Dashboard tổng quan cho tab báo cáo."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_DU_NO_KHOANH,
    COT_DNO_NQ11,
)
from auth import la_phan_he_pgd
from utils import fmt_ty
from .components.metric_cards import render_metric_cards
from .components.data_source_indicator import render_data_source_status
from .components.inline_filter import chuan_bi_du_lieu_bao_cao, loc_nguon_von

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _loc_hstd_metric(
    df: pd.DataFrame | None,
    selected_pgd: str = "Tất cả",
    selected_nv: str = "all",
) -> pd.DataFrame | None:
    """Áp dụng cùng bộ lọc PGD/nguồn vốn cho các metric HSTD trên dashboard."""
    if df is None or df.empty:
        return df

    result = df
    if (
        selected_pgd != "Tất cả"
        and COT_TEN_PGD in result.columns
        and result[COT_TEN_PGD].eq(selected_pgd).any()
    ):
        result = result.loc[result[COT_TEN_PGD].eq(selected_pgd)].copy()
    result = loc_nguon_von(result, selected_nv)
    return chuan_bi_du_lieu_bao_cao(result)


def render_dashboard(
    tab: DeltaGenerator | None = None,
    df: pd.DataFrame | None = None,
    df_nq11: pd.DataFrame | None = None,
    df_gqvl: pd.DataFrame | None = None,
    df_cdtotkvv: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    **kwargs
) -> str:
    """
    Render dashboard tổng quan và trả về loại báo cáo được chọn.
    
    Args:
        tab: Streamlit container
        df: DataFrame HSTD
        df_nq11: DataFrame NQ11
        df_gqvl: DataFrame GQVL
        df_cdtotkvv: DataFrame CDTOTKVV
        role: Role người dùng
        pgd_user: Tên PGD
    
    Returns:
        str: Loại báo cáo được chọn để render tiếp theo
    """
    ctx = tab if tab is not None else st
    
    # Hiển thị trạng thái nguồn dữ liệu
    render_data_source_status(df, df_nq11, df_gqvl, df_cdtotkvv, container=ctx)
    
    # Chọn loại báo cáo
    ctx.markdown("### 🔍 Chọn báo cáo")
    
    # Lọc theo role
    is_pgd = la_phan_he_pgd(role) and pgd_user
    
    # Danh sách báo cáo theo role
    baocao_options = [
        "📁 Báo cáo Tổng hợp (HSTD)",
        "⚠️ Báo cáo Nợ rủi ro (HSTD)",
        "📑 Báo cáo NQ11",
        "💼 Báo cáo GQVL",
        "⭐ Báo cáo Chấm điểm Tổ TK&VV",
    ]
    
    # Thêm thông báo nếu là PGD
    if is_pgd:
        ctx.info(f"📍 Bạn đang xem báo cáo của PGD: **{pgd_user}**")
    
    # Dropdown chọn báo cáo
    selected = ctx.selectbox(
        "Loại báo cáo",
        baocao_options,
        key="bc_dashboard_select",
    )

    # Mapping từ lựa chọn sang key
    report_key_map = {
        "📁 Báo cáo Tổng hợp (HSTD)": "hstd",
        "⚠️ Báo cáo Nợ rủi ro (HSTD)": "noruiro",
        "📑 Báo cáo NQ11": "nq11",
        "💼 Báo cáo GQVL": "gqvl",
        "⭐ Báo cáo Chấm điểm Tổ TK&VV": "cdtotkvv",
    }
    
    selected_key = report_key_map.get(selected, "hstd")

    # Đồng bộ metric HSTD với bộ lọc PGD/nguồn vốn của báo cáo đang chọn.
    selected_pgd = "Tất cả"
    selected_nv = "all"
    if not is_pgd:
        if selected_key == "hstd":
            selected_group = st.session_state.get("th_loai_hstd_v2", "pgd")
            selected_pgd = st.session_state.get(
                f"filter_th_{selected_group}_pgd_{COT_TEN_PGD}", "Tất cả"
            )
        elif selected_key == "noruiro":
            selected_pgd = st.session_state.get(
                f"filter_nr_v2_pgd_{COT_TEN_PGD}", "Tất cả"
            )
    if selected_key == "hstd":
        selected_group = st.session_state.get("th_loai_hstd_v2", "pgd")
        selected_nv = st.session_state.get(f"nv_filter_th_{selected_group}", "all")
    elif selected_key == "noruiro":
        selected_nv = st.session_state.get("nv_filter_nr_v2", "all")

    df_metric = _loc_hstd_metric(df, selected_pgd, selected_nv)
    render_metric_cards(df_metric, df_nq11, df_gqvl, container=ctx)
    ctx.divider()

    return selected_key
