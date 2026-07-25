"""Sticky header table component cho báo cáo."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING, List, Dict, Any

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def render_sticky_table(
    df: pd.DataFrame,
    key: str,
    height: int = 400,
    container: DeltaGenerator | None = None,
    column_config: Dict[str, Any] | None = None,
) -> None:
    """
    Hiển thị bảng với sticky header.
    
    Args:
        df: DataFrame cần hiển thị
        key: Streamlit key
        height: Chiều cao bảng (px)
        container: Streamlit container
        column_config: Cấu hình cột (width, help, format)
    """
    ctx = container if container is not None else st
    
    # CSS cho sticky header
    sticky_css = f"""
    <style>
    .sticky-table-{key} {{
        position: relative;
        height: {height}px;
        overflow: auto;
        border: 1px solid #2A2D3E;
        border-radius: 8px;
    }}
    .sticky-table-{key} thead {{
        position: sticky;
        top: 0;
        z-index: 10;
        background: #262B3D;
        color: #E0E6ED;
    }}
    .sticky-table-{key} th {{
        background: #262B3D;
        color: #E0E6ED;
        font-weight: 600;
        padding: 12px;
        border-bottom: 2px solid #2A2D3E;
        text-align: left;
        font-size: 13px;
    }}
    .sticky-table-{key} td {{
        padding: 10px 12px;
        border-bottom: 1px solid #2A2D3E;
        font-size: 13px;
    }}
    .sticky-table-{key} tr:hover td {{
        background: #262B3D;
        color: #E0E6ED;
    }}
    .sticky-table-{key} tbody tr:nth-child(even) {{
        background: #1E2130;
        color: #E0E6ED;
    }}
    </style>
    """
    
    ctx.markdown(sticky_css, unsafe_allow_html=True)
    
    # Chuyển DataFrame sang HTML với class
    html_table = df.to_html(
        index=False,
        classes=f'sticky-table-{key}',
        escape=False,
    )
    
    ctx.markdown(html_table, unsafe_allow_html=True)


def render_sortable_table(
    df: pd.DataFrame,
    key: str,
    sortable_cols: List[str] | None = None,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị bảng có thể sort (dùng session_state).
    
    Args:
        df: DataFrame cần hiển thị
        key: Streamlit key
        sortable_cols: Các cột có thể sort
        container: Streamlit container
    """
    ctx = container if container is not None else st
    
    # Khởi tạo sort state
    sort_key = f"sort_{key}"
    if sort_key not in st.session_state:
        st.session_state[sort_key] = {"col": None, "asc": True}
    
    # Hiển thị control sort
    col1, col2 = ctx.columns([2, 1])
    
    with col1:
        if sortable_cols:
            sort_col = st.selectbox(
                "Sắp xếp theo",
                ["Mặc định"] + sortable_cols,
                key=f"select_{sort_key}",
            )
    
    with col2:
        if st.session_state[sort_key]["col"]:
            if st.button("🔄 Đảo chiều", key=f"btn_reverse_{key}"):
                st.session_state[sort_key]["asc"] = not st.session_state[sort_key]["asc"]
    
    # Apply sort
    df_display = df.copy()
    if sort_col != "Mặc định" and sort_col in df_display.columns:
        df_display = df_display.sort_values(
            sort_col,
            ascending=st.session_state[sort_key]["asc"]
        )
    
    render_sticky_table(df_display, key, container=ctx)
