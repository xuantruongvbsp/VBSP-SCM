"""Module tab_baocao - Báo cáo tín dụng từ 4 nguồn dữ liệu: HSTD, NQ11, GQVL, CDTOTKVV."""
from __future__ import annotations

import streamlit as st
from typing import TYPE_CHECKING

from auth import la_phan_he_pgd, normalize_role
from logger import get_logger
from tabs.base_tab import TabContext
from .dashboard import render_dashboard
from .tree_navigation import render_tree_navigation, render_compact_navigation, get_report_info
from .components.metric_cards import render_metric_cards
from .components.data_source_indicator import render_data_source_status
from .components.export_panel import render_export_panel
from .reports import (
    render_tong_hop_hstd,
    render_no_rui_ro,
    render_nq11,
    render_gqvl,
    render_cdtotkvv,
    render_tong_hop_hstd_v2,
    render_no_rui_ro_v2,
    render_nong_nghiep,
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
    "render_nong_nghiep",
]


def render(tab: "DeltaGenerator | None" = None, **kwargs) -> None:
    """Entry point tab Báo cáo Tín dụng — được gọi qua _get_tab("tab_baocao").render()."""
    ctx = TabContext(tab, **kwargs)

    df = kwargs.get("df")
    df_full = kwargs.get("df_full", df)
    df_nq11 = kwargs.get("df_nq11")
    df_gqvl = kwargs.get("df_gqvl")
    df_cdtotkvv = kwargs.get("df_cdtotkvv")
    role = kwargs.get("role", "")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")
    role_norm = normalize_role(str(role or "user"))

    if df_cdtotkvv is None or df_cdtotkvv.empty:
        try:
            from services.tongquan_cdto_service import load_cdto_toan_cn

            cdto_state = load_cdto_toan_cn()
            df_cdtotkvv = cdto_state.get("df_raw")

            if (
                df_cdtotkvv is not None
                and not df_cdtotkvv.empty
                and la_phan_he_pgd(role_norm)
                and pgd_user
            ):
                from services.cdtotkvv_service import loc_df as _loc_df_cdtotkvv

                df_cdtotkvv = _loc_df_cdtotkvv(df_cdtotkvv, "pgd", pgd_user)
        except Exception as e:
            logger.error("tab_baocao: load df_cdtotkvv fallback lỗi — %s", e, exc_info=True)
            df_cdtotkvv = None

    with ctx:
        st.subheader("📊 Dashboard Báo cáo Tín dụng")

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
            render_tong_hop_hstd_v2(tab=None, df=df, role=role, pgd_user=pgd_user, username=username)
        elif selected_report == "noruiro":
            render_no_rui_ro_v2(tab=None, df=df, role=role, pgd_user=pgd_user, username=username)
        elif selected_report == "nq11":
            render_nq11(
                tab=None,
                df_nq11=df_nq11,
                df_hstd_full=df_full,
                role=role,
                pgd_user=pgd_user,
                username=username,
            )
        elif selected_report == "gqvl":
            render_gqvl(tab=None, df_gqvl=df_gqvl, role=role, pgd_user=pgd_user, username=username)
        elif selected_report == "cdtotkvv":
            render_cdtotkvv(tab=None, df_cdtotkvv=df_cdtotkvv, role=role, pgd_user=pgd_user, username=username)
        elif selected_report == "nongnghiep":
            render_nong_nghiep(tab=None, df=df, role=role, pgd_user=pgd_user, username=username)
        else:
            st.info("👆 Vui lòng chọn loại báo cáo từ Dashboard bên trên")
