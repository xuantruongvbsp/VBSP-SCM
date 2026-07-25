"""Skeleton loading component cho báo cáo."""
from __future__ import annotations

import streamlit as st
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def render_skeleton_metrics(container: DeltaGenerator | None = None) -> None:
    """Hiển thị skeleton cho metric cards."""
    ctx = container if container is not None else st
    c1, c2, c3, c4 = ctx.columns(4)
    
    for col in [c1, c2, c3, c4]:
        with col:
            st.markdown("""
                <div style="background:#1E2130;color:#E0E6ED;height:60px;border-radius:8px;margin:4px;">
                    <div style="background:linear-gradient(90deg,#262B3D 25%,#1E2130 50%,#262B3D 75%);color:#E0E6ED;background-size:200% 100%;height:100%;border-radius:8px;animation:shimmer 1.5s infinite;"></div>
                </div>
                <style>@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}</style>
            """, unsafe_allow_html=True)


def render_skeleton_table(n_rows: int = 5, container: DeltaGenerator | None = None) -> None:
    """Hiển thị skeleton cho bảng dữ liệu."""
    ctx = container if container is not None else st
    
    # Header skeleton
    ctx.markdown("""
        <div style="background:#262B3D;color:#E0E6ED;height:40px;border-radius:4px;margin-bottom:8px;"></div>
    """, unsafe_allow_html=True)
    
    # Row skeletons
    for _ in range(n_rows):
        ctx.markdown("""
            <div style="background:#1E2130;color:#E0E6ED;height:35px;border-radius:4px;margin-bottom:4px;
                background:linear-gradient(90deg,#262B3D 25%,#1E2130 50%,#262B3D 75%);
                background-size:200% 100%;animation:shimmer 1.5s infinite;">
            </div>
            <style>@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}</style>
        """, unsafe_allow_html=True)


def render_skeleton_card(title: str = "Đang tải...", container: DeltaGenerator | None = None) -> None:
    """Hiển thị skeleton card đơn lẻ."""
    ctx = container if container is not None else st
    
    ctx.markdown(f"""
        <div style="border:1px solid #2A2D3E;border-radius:8px;padding:16px;background:#1E2130;color:#E0E6ED;">
            <div style="background:#262B3D;color:#E0E6ED;height:20px;width:60%;border-radius:4px;margin-bottom:12px;"></div>
            <div style="background:#262B3D;color:#E0E6ED;height:40px;width:80%;border-radius:4px;
                background:linear-gradient(90deg,#2A2D3E 25%,#262B3D 50%,#2A2D3E 75%);
                background-size:200% 100%;animation:shimmer 1.5s infinite;">
            </div>
        </div>
        <style>@keyframes shimmer{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}</style>
    """, unsafe_allow_html=True)


def with_loading_state(func, *args, **kwargs):
    """Decorator-style wrapper để hiển thị skeleton khi loading."""
    render_skeleton_metrics()
    render_skeleton_table()
    result = func(*args, **kwargs)
    return result
