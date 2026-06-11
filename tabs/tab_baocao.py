"""Tab Báo cáo Tín dụng - Chỉ từ 4 nguồn dữ liệu: HSTD, NQ11, GQVL, CDTOTKVV."""
from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd

from auth import la_phan_he_pgd
from logger import get_logger
from tabs.base_tab import TabContext

# Import từ module tab_baocao
from tabs.tab_baocao.dashboard import render_dashboard
from tabs.tab_baocao.reports import (
    render_tong_hop_hstd,
    render_no_rui_ro,
    render_nq11,
    render_gqvl,
    render_cdtotkvv,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def render(tab: DeltaGenerator | None = None, **kwargs: dict) -> None:
    """
    Render tab Báo cáo Tín dụng - Entry point chính.
    
    Args:
        tab: Streamlit DeltaGenerator
        **kwargs: Chứa df (HSTD), df_nq11, df_gqvl, df_cdtotkvv, role, username, pgd_user
    """
    ctx = TabContext(tab, **kwargs)
    
    # Lấy dữ liệu từ kwargs
    df = kwargs.get("df")  # HSTD
    df_nq11 = kwargs.get("df_nq11")
    df_gqvl = kwargs.get("df_gqvl")
    df_cdtotkvv = kwargs.get("df_cdtotkvv")
    role = kwargs.get("role", "")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")
    
    with ctx:
        st.subheader("📈 Báo cáo Tín dụng")
        st.caption("📡 Dữ liệu: HSTD | NQ11 | GQVL | CDTOTKVV")
        
        # Dashboard tổng quan + Chọn loại báo cáo
        selected_report = render_dashboard(
            tab=None,  # Dùng trong ctx
            df=df,
            df_nq11=df_nq11,
            df_gqvl=df_gqvl,
            df_cdtotkvv=df_cdtotkvv,
            role=role,
            pgd_user=pgd_user,
        )
        
        # Render báo cáo được chọn
        st.divider()
        
        if selected_report == "hstd":
            render_tong_hop_hstd(
                tab=None,
                df=df,
                role=role,
                pgd_user=pgd_user,
                username=username,
            )
        elif selected_report == "noruiro":
            render_no_rui_ro(
                tab=None,
                df=df,
                role=role,
                pgd_user=pgd_user,
                username=username,
            )
        elif selected_report == "nq11":
            render_nq11(
                tab=None,
                df_nq11=df_nq11,
                role=role,
                pgd_user=pgd_user,
                username=username,
            )
        elif selected_report == "gqvl":
            render_gqvl(
                tab=None,
                df_gqvl=df_gqvl,
                role=role,
                pgd_user=pgd_user,
                username=username,
            )
        elif selected_report == "cdtotkvv":
            render_cdtotkvv(
                tab=None,
                df_cdtotkvv=df_cdtotkvv,
                role=role,
                pgd_user=pgd_user,
                username=username,
            )
        else:
            # Mặc định hiển thị tổng hợp
            st.info("👆 Vui lòng chọn loại báo cáo từ Dashboard bên trên")
