"""Tab Kiểm toán Nội bộ (KTNB) — wrapper cho render_ktnb() từ ktnb_service."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn
from logger import get_logger
from services.ktnb_service import render_ktnb
from tabs.base_tab import TabContext

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    role = ctx.role_norm
    username = ctx.username or "unknown"
    df_full = ctx.df_full if ctx.df_full is not None else kwargs.get("df")

    with ctx:
        st.subheader("🔍 Kiểm toán Nội bộ (KTNB)")

        if not la_phan_he_cn(role):
            st.info("ℹ️ Chức năng này chỉ dành cho Phòng KH-NV / Ban Giám đốc.")
            return

        try:
            render_ktnb(df_full, role, username)
        except Exception as e:
            logger.error("tab_ktnb.render: %s", e, exc_info=True)
            st.error(f"❌ Lỗi: {e}")
