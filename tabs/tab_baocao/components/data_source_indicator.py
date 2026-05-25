"""Component hiển thị trạng thái 4 nguồn dữ liệu."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import TYPE_CHECKING

from data.core import ts_file
from config import CACHE_HSTD, CACHE_NQ11

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _get_data_status(
    df: pd.DataFrame | None,
    cache_path: str | None = None,
    warning_days: int = 3
) -> tuple[str, str, str]:
    """
    Trả về (icon, text_color, status_text) cho một nguồn dữ liệu.
    
    Returns:
        tuple: (icon, color_class, status_text)
    """
    if df is None or df.empty:
        return "🔴", "red", "Chưa có dữ liệu"
    
    # Kiểm tra thời gian cập nhật nếu có cache
    if cache_path:
        try:
            ts = ts_file(cache_path)
            days_ago = (datetime.now() - ts).days
            if days_ago <= 1:
                return "🟢", "green", f"Cập nhật hôm nay"
            elif days_ago <= warning_days:
                return "🟡", "orange", f"Cập nhật {days_ago} ngày trước"
            else:
                return "🔴", "red", f"Cập nhật {days_ago} ngày trước"
        except Exception:
            pass
    
    return "🟢", "green", "Có dữ liệu"


def render_data_source_status(
    df: pd.DataFrame | None = None,
    df_nq11: pd.DataFrame | None = None,
    df_gqvl: pd.DataFrame | None = None,
    df_cdtotkvv: pd.DataFrame | None = None,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị trạng thái 4 nguồn dữ liệu.
    
    Args:
        df: DataFrame HSTD
        df_nq11: DataFrame NQ11
        df_gqvl: DataFrame GQVL
        df_cdtotkvv: DataFrame CDTOTKVV
        container: Streamlit container (optional)
    """
    ctx = container if container is not None else st
    
    # Lấy trạng thái từng nguồn
    hstd_icon, hstd_color, hstd_text = _get_data_status(df, CACHE_HSTD, 3)
    nq11_icon, nq11_color, nq11_text = _get_data_status(df_nq11, CACHE_NQ11, 3)
    gqvl_icon, gqvl_color, gqvl_text = _get_data_status(df_gqvl, None, 7)
    cdto_icon, cdto_color, cdto_text = _get_data_status(df_cdtotkvv, None, 35)
    
    ctx.markdown("#### 📡 Trạng thái dữ liệu")
    
    col1, col2, col3, col4 = ctx.columns(4)
    
    with col1:
        st.markdown(f"**{hstd_icon} HSTD**<br><small style='color: {hstd_color}'>{hstd_text}</small>", unsafe_allow_html=True)

    with col2:
        st.markdown(f"**{nq11_icon} NQ11**<br><small style='color: {nq11_color}'>{nq11_text}</small>", unsafe_allow_html=True)

    with col3:
        st.markdown(f"**{gqvl_icon} GQVL**<br><small style='color: {gqvl_color}'>{gqvl_text}</small>", unsafe_allow_html=True)

    with col4:
        st.markdown(f"**{cdto_icon} CDTOTKVV**<br><small style='color: {cdto_color}'>{cdto_text}</small>", unsafe_allow_html=True)
    
    ctx.divider()
