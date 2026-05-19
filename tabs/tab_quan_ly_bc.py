"""Tab cha Quản lý Báo cáo định kỳ — wrapper điều hướng 2 sub-module."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from utils import get_tab_context
from tabs import tab_tien_do_nop, tab_checklist_bc


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = get_tab_context(tab)
    with ctx:
        t1, t2 = st.tabs(["📥 BC từ PGD", "📤 BC lên cấp trên"])
        with t1:
            tab_tien_do_nop.render(t1, **kwargs)
        with t2:
            tab_checklist_bc.render(t2, **kwargs)
