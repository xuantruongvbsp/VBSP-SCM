"""Inline filter component cho báo cáo."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING, List, Dict, Any, Callable

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def render_inline_filter(
    df: pd.DataFrame,
    filter_columns: List[str],
    key: str,
    container: DeltaGenerator | None = None,
    on_filter_change: Callable | None = None,
) -> pd.DataFrame:
    """
    Hiển thị inline filter ngay trên đầu bảng.
    
    Args:
        df: DataFrame gốc
        filter_columns: Các cột cần filter
        key: Streamlit key
        container: Streamlit container
        on_filter_change: Callback khi filter thay đổi
    
    Returns:
        DataFrame đã filter
    """
    ctx = container if container is not None else st
    
    df_filtered = df.copy()
    
    # Tạo row cho filters
    n_cols = len(filter_columns)
    cols = ctx.columns(min(n_cols, 4))  # Tối đa 4 filter trên 1 row
    
    for idx, col_name in enumerate(filter_columns):
        if idx < len(cols) and col_name in df.columns:
            with cols[idx]:
                # Lấy unique values
                unique_vals = ["Tất cả"] + sorted(df[col_name].dropna().unique().tolist())
                
                # Selectbox cho mỗi cột
                selected = st.selectbox(
                    f"🔍 {col_name}",
                    unique_vals,
                    key=f"filter_{key}_{col_name}",
                    label_visibility="visible",
                )
                
                # Apply filter
                if selected != "Tất cả":
                    df_filtered = df_filtered[df_filtered[col_name] == selected]
    
    # Hiển thị số lượng kết quả
    ctx.caption(f"📊 Hiển thị **{len(df_filtered):,}** / **{len(df):,}** dòng".replace(",", "."))
    
    # Callback nếu có
    if on_filter_change:
        on_filter_change(df_filtered)
    
    return df_filtered


def render_quick_search(
    df: pd.DataFrame,
    search_columns: List[str],
    key: str,
    placeholder: str = "🔍 Tìm kiếm nhanh...",
    container: DeltaGenerator | None = None,
) -> pd.DataFrame:
    """
    Tìm kiếm nhanh across multiple columns.
    
    Args:
        df: DataFrame gốc
        search_columns: Các cột để tìm kiếm
        key: Streamlit key
        placeholder: Placeholder text
        container: Streamlit container
    
    Returns:
        DataFrame đã filter
    """
    ctx = container if container is not None else st
    
    # Search input
    search_term = st.text_input(
        "",
        placeholder=placeholder,
        key=f"quick_search_{key}",
        label_visibility="collapsed",
    )
    
    df_filtered = df.copy()
    
    if search_term:
        # Tìm kiếm substring trong các cột
        mask = pd.Series([False] * len(df), index=df.index)
        
        for col in search_columns:
            if col in df.columns:
                # Chuyển về string và tìm kiếm không phân biệt case
                col_values = df[col].astype(str).str.lower()
                mask |= col_values.str.contains(search_term.lower(), na=False)
        
        df_filtered = df[mask]
        
        ctx.caption(f"🔎 Tìm thấy **{len(df_filtered):,}** kết quả cho \"{search_term}\"".replace(",", "."))
    
    return df_filtered


def render_combined_filter_search(
    df: pd.DataFrame,
    filter_columns: List[str],
    search_columns: List[str],
    key: str,
    container: DeltaGenerator | None = None,
) -> pd.DataFrame:
    """
    Kết hợp filter và search.
    
    Returns:
        DataFrame đã filter và search
    """
    ctx = container if container is not None else st
    
    # Filter section
    ctx.markdown("**🔧 Bộ lọc**")
    df_filtered = render_inline_filter(
        df, filter_columns, f"{key}_filter", container=ctx
    )
    
    ctx.divider()
    
    # Search section
    ctx.markdown("**🔍 Tìm kiếm**")
    df_searched = render_quick_search(
        df_filtered, search_columns, f"{key}_search", container=ctx
    )
    
    return df_searched
