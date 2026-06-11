"""Tab cha Quản lý Báo cáo định kỳ — wrapper điều hướng 3 sub-module."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from tabs import bc_tong_hop, tab_tien_do_nop, tab_checklist_bc
from tabs.base_tab import TabContext


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    with ctx:
        t1, t2, t3 = st.tabs([
            "📊 Báo cáo tổng hợp",
            "📥 BC từ PGD",
            "📤 BC lên cấp trên"
        ])
        with t1:
            bc_tong_hop.render(t1, **kwargs)
        with t2:
            tab_tien_do_nop.render(t2, **kwargs)
        with t3:
            tab_checklist_bc.render(t3, **kwargs)
