"""Wrapper: Dashboard Công việc — Quản lý Tiến độ & Nhiệm vụ."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from tabs.base_tab import TabContext
from tabs import tab_tien_do, tab_nhiem_vu, tab_tong_hop_cv
from tabs import bc_tong_hop, tab_tien_do_nop, tab_checklist_bc


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    with ctx:
        t_cv, t_bc = st.tabs([
            "� Dashboard Công việc",
            "� Báo cáo",
        ])
        with t_cv:
            s1, s2, s3 = st.tabs([
                "📊 Tổng quan toàn bộ",
                "📅 Tiến độ Công việc",
                "📌 Nhiệm vụ định kỳ",
            ])
            with s1:
                tab_tong_hop_cv.render(s1, **kwargs)
            with s2:
                tab_tien_do.render(s2, **kwargs)
            with s3:
                tab_nhiem_vu.render(s3, **kwargs)
        with t_bc:
            s1, s2, s3 = st.tabs([
                "📊 Báo cáo tổng hợp",
                "📥 Báo cáo từ PGD",
                "📤 Báo cáo lên cấp trên",
            ])
            with s1:
                bc_tong_hop.render(s1, **kwargs)
            with s2:
                tab_tien_do_nop.render(s2, **kwargs)
            with s3:
                tab_checklist_bc.render(s3, **kwargs)
