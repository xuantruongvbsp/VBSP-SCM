"""Tab cha Quản lý Báo cáo định kỳ — wrapper điều hướng các sub-module báo cáo."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from tabs import bc_tong_hop, tab_bao_cao_dinh_ky, tab_checklist_bc, tab_tien_do_nop
from tabs.base_tab import TabContext


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.title("📅 Quản lý Báo cáo định kỳ")
        st.caption("Một nơi để tạo báo cáo tự động, theo dõi PGD nộp báo cáo và kiểm soát báo cáo gửi cấp trên.")

        t1, t2, t3, t4 = st.tabs([
            "📅 BC tự động",
            "📥 BC từ PGD",
            "📤 BC lên cấp trên",
            "📊 Báo cáo tổng hợp",
        ])
        with t1:
            tab_bao_cao_dinh_ky.render(t1, **kwargs)
        with t2:
            tab_tien_do_nop.render(t2, **kwargs)
        with t3:
            tab_checklist_bc.render(t3, **kwargs)
        with t4:
            bc_tong_hop.render(t4, **kwargs)
