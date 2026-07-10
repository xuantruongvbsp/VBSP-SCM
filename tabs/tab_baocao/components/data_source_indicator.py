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
    Trả về (icon, css_class, status_text) cho một nguồn dữ liệu.
    
    Returns:
        tuple: (icon, css_class, status_text)
    """
    if df is None or df.empty:
        return "🔴", "status-error", "Chưa có dữ liệu"
    
    # Kiểm tra thời gian cập nhật nếu có cache
    if cache_path:
        try:
            ts = ts_file(cache_path)
            days_ago = (datetime.now() - ts).days
            if days_ago <= 1:
                return "🟢", "status-ok", "Cập nhật hôm nay"
            elif days_ago <= warning_days:
                return "🟡", "status-warn", f"Cập nhật {days_ago} ngày trước"
            else:
                return "🔴", "status-error", f"Cập nhật {days_ago} ngày trước"
        except Exception:
            pass
    
    return "🟢", "status-ok", "Có dữ liệu"


def render_data_source_status(
    df: pd.DataFrame | None = None,
    df_nq11: pd.DataFrame | None = None,
    df_gqvl: pd.DataFrame | None = None,
    df_cdtotkvv: pd.DataFrame | None = None,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị trạng thái 4 nguồn dữ liệu dạng pill/badge.
    
    Args:
        df: DataFrame HSTD
        df_nq11: DataFrame NQ11
        df_gqvl: DataFrame GQVL
        df_cdtotkvv: DataFrame CDTOTKVV
        container: Streamlit container (optional)
    """
    ctx = container if container is not None else st
    
    # Lấy trạng thái từng nguồn
    hstd_icon, hstd_cls, hstd_text = _get_data_status(df, CACHE_HSTD, 3)
    nq11_icon, nq11_cls, nq11_text = _get_data_status(df_nq11, CACHE_NQ11, 3)
    gqvl_icon, gqvl_cls, gqvl_text = _get_data_status(df_gqvl, None, 7)
    cdto_icon, cdto_cls, cdto_text = _get_data_status(df_cdtotkvv, None, 35)
    
    ctx.markdown("#### 📡 Trạng thái dữ liệu")
    
    # Dùng st.html để hiển thị pill badge — dùng CSS variable tương thích dark mode
    html = f"""<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
    <div class="ds-pill {hstd_cls}">{hstd_icon} <b>HSTD</b> · {hstd_text}</div>
    <div class="ds-pill {nq11_cls}">{nq11_icon} <b>NQ11</b> · {nq11_text}</div>
    <div class="ds-pill {gqvl_cls}">{gqvl_icon} <b>GQVL</b> · {gqvl_text}</div>
    <div class="ds-pill {cdto_cls}">{cdto_icon} <b>CDTOTKVV</b> · {cdto_text}</div>
    </div>"""
    ctx.html(html)
