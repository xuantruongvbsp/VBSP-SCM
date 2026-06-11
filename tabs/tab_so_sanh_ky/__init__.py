"""Package So sánh kỳ — tái cấu trúc khoa học từ tab_so_sanh_ky.py + tab_so_sanh_2_ky.py."""
from __future__ import annotations

from streamlit.delta_generator import DeltaGenerator

from auth import normalize_role
from tabs.base_tab import TabContext
from tabs.tab_so_sanh_ky.render_moc_nam import render_moc_nam
from tabs.tab_so_sanh_ky.render_2_ky import render_2_ky

import streamlit as st


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Entry point: router chọn loại so sánh."""
    ctx = TabContext(tab, **kwargs)
    role = normalize_role(str(kwargs.get("role", "user") or "user"))
    kwargs["role"] = role

    with ctx:
        sub = st.radio(
            "Loại so sánh",
            ["📊 So sánh mốc năm", "🔄 So sánh 2 kỳ"],
            horizontal=True,
            key="ss_ky_sub",
            label_visibility="collapsed",
        )
        st.divider()
        if sub == "📊 So sánh mốc năm":
            render_moc_nam(None, **kwargs)
        else:
            render_2_ky(None, **kwargs)
