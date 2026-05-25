"""Module tab_baocao - Báo cáo tín dụng từ 4 nguồn dữ liệu: HSTD, NQ11, GQVL, CDTOTKVV."""
from __future__ import annotations

import streamlit as st
from typing import TYPE_CHECKING

from logger import get_logger
from .dashboard import render_dashboard
from .tree_navigation import render_tree_navigation, render_compact_navigation, get_report_info
from .components.metric_cards import render_metric_cards
from .components.data_source_indicator import render_data_source_status
from .components.export_panel import render_export_panel
from .components.skeleton_loader import render_skeleton_metrics, render_skeleton_table
from .components.sticky_table import render_sticky_table
from .components.inline_filter import render_combined_filter_search
from .components.quick_export import render_quick_export_buttons
from .components.alert_suggestion import render_combined_alerts_suggestions
from .reports import (
    render_tong_hop_hstd,
    render_no_rui_ro,
    render_nq11,
    render_gqvl,
    render_cdtotkvv,
    render_tong_hop_hstd_v2,
    render_no_rui_ro_v2,
)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

logger = get_logger(__name__)

__all__ = [
    "render",
    "render_dashboard",
    "render_tree_navigation",
    "render_compact_navigation",
    "get_report_info",
    "render_metric_cards",
    "render_data_source_status",
    "render_export_panel",
    "render_tong_hop_hstd_v2",
    "render_no_rui_ro_v2",
]


def render(tab: "DeltaGenerator | None" = None, **kwargs) -> None:
    """Entry point tab Báo cáo Tín dụng — được gọi qua _get_tab("tab_baocao").render()."""
    ctx = tab if tab is not None else st.container()

    df = kwargs.get("df")
    df_nq11 = kwargs.get("df_nq11")
    df_gqvl = kwargs.get("df_gqvl")
    df_cdtotkvv = kwargs.get("df_cdtotkvv")
    role = kwargs.get("role", "")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")

    with ctx:
        st.subheader("📈 Báo cáo Tín dụng")
        st.caption("📡 Dữ liệu: HSTD | NQ11 | GQVL | CDTOTKVV")

        selected_report = render_dashboard(
            tab=None,
            df=df,
            df_nq11=df_nq11,
            df_gqvl=df_gqvl,
            df_cdtotkvv=df_cdtotkvv,
            role=role,
            pgd_user=pgd_user,
        )

        st.divider()

        if selected_report == "hstd":
            render_tong_hop_hstd(tab=None, df=df, role=role, pgd_user=pgd_user, username=username)
        elif selected_report == "noruiro":
            render_no_rui_ro(tab=None, df=df, role=role, pgd_user=pgd_user, username=username)
        elif selected_report == "nq11":
            render_nq11(tab=None, df_nq11=df_nq11, role=role, pgd_user=pgd_user, username=username)
        elif selected_report == "gqvl":
            render_gqvl(tab=None, df_gqvl=df_gqvl, role=role, pgd_user=pgd_user, username=username)
        elif selected_report == "cdtotkvv":
            render_cdtotkvv(tab=None, df_cdtotkvv=df_cdtotkvv, role=role, pgd_user=pgd_user, username=username)
        else:
            st.info("👆 Vui lòng chọn loại báo cáo từ Dashboard bên trên")
