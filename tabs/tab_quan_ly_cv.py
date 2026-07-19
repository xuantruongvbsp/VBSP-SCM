"""Wrapper: Dashboard Công việc — Quản lý Tiến độ & Nhiệm vụ."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from tabs.base_tab import TabContext
from tabs import tab_tien_do, tab_nhiem_vu, tab_tong_hop_cv, tab_ke_hoach_cv_khnv
from tabs import bc_tong_hop, tab_tien_do_nop, tab_checklist_bc, tab_theo_doi_nhap


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    with ctx:
        t_cv, t_bc = st.tabs([
            "� Dashboard Công việc",
            "� Báo cáo",
        ])
        with t_cv:
            s1, s2, s3, s4 = st.tabs([
                "� Tổng quan toàn bộ",
                "📅 Tiến độ Công việc",
                "📌 Nhiệm vụ định kỳ",
                "📝 KH Cán bộ KHNV",
            ])
            with s1:
                tab_tong_hop_cv.render(s1, **kwargs)
            with s2:
                tab_tien_do.render(s2, **kwargs)
            with s3:
                tab_nhiem_vu.render(s3, **kwargs)
            with s4:
                tab_ke_hoach_cv_khnv.render(s4, **kwargs)
        with t_bc:
            s1, s2, s3, s4 = st.tabs([
                "📊 Báo cáo tổng hợp",
                "📥 Báo cáo từ PGD",
                "📤 Báo cáo lên cấp trên",
                "📋 Theo dõi nhập liệu",
            ])
            with s1:
                bc_tong_hop.render(s1, **kwargs)
            with s2:
                tab_tien_do_nop.render(s2, **kwargs)
            with s3:
                tab_checklist_bc.render(s3, **kwargs)
            with s4:
                tab_theo_doi_nhap.render(s4, **kwargs)
