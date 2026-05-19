"""Wrapper: Quản lý Công việc & Nhiệm vụ — gộp 3 sub-module."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from utils import get_tab_context
from tabs import tab_tien_do, tab_nhiem_vu, tab_quan_ly_bc


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = get_tab_context(tab)
    with ctx:
        t1, t2, t3 = st.tabs([
            "📅 Tiến độ Công việc",
            "📌 Nhiệm vụ định kỳ",
            "📋 Báo cáo",
        ])
        with t1:
            tab_tien_do.render(t1, **kwargs)
        with t2:
            tab_nhiem_vu.render(t2, **kwargs)
        with t3:
            tab_quan_ly_bc.render(t3, **kwargs)
