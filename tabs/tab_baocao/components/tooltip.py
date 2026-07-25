"""Tooltip component cho báo cáo - hiển thị giải thích công thức."""
from __future__ import annotations

import streamlit as st
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


# Mapping công thức và giải thích
FORMULA_TOOLTIPS = {
    "Tổng dư nợ": "Tổng dư nợ trong hạn + quá hạn + khoanh",
    "Nợ quá hạn": "Dư nợ các món vay đã quá hạn thanh toán",
    "Nợ khoanh": "Dư nợ bị khoanh để xử lý rủi ro",
    "Tỷ lệ nợ xấu": "(Nợ quá hạn + Nợ khoanh) / Tổng dư nợ × 100%",
    "Tỷ_lệ_QH_%": "Nợ quá hạn / Tổng dư nợ × 100%",
    "DNO NQ11": "Dư nợ theo Nghị quyết 11 của Chính phủ",
    "Điểm GDTX": "Điểm Giao dịch tại xã (thang 100 điểm)",
    "Điểm NQH": "Điểm Nợ quá hạn (thang 100 điểm)",
    "Tổng điểm": "Tổng điểm các tiêu chí chấm điểm",
    "Giải ngân": "Số tiền giải ngân trong năm",
    "Món có NQ11": "Món vay có thông tin trong NQ11",
    "Món không NQ11": "Món vay chưa có thông tin trong NQ11",
}


def render_tooltip(
    text: str,
    tooltip_text: str,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị text với tooltip.
    
    Args:
        text: Text hiển thị
        tooltip_text: Nội dung tooltip
        container: Streamlit container
    """
    ctx = container if container is not None else st
    
    tooltip_html = f"""
        <span style="position:relative;cursor:help;border-bottom:1px dotted #666;" 
              title="{tooltip_text}">
            {text} ℹ️
        </span>
    """
    ctx.markdown(tooltip_html, unsafe_allow_html=True)


def render_header_with_tooltip(
    header_text: str,
    tooltip_key: str | None = None,
    custom_tooltip: str | None = None,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị header với tooltip tự động.
    
    Args:
        header_text: Text header
        tooltip_key: Key trong FORMULA_TOOLTIPS (optional)
        custom_tooltip: Tooltip tùy chỉnh (optional)
        container: Streamlit container
    """
    ctx = container if container is not None else st
    
    # Lấy tooltip text
    tooltip_text = custom_tooltip
    if tooltip_key and tooltip_key in FORMULA_TOOLTIPS:
        tooltip_text = FORMULA_TOOLTIPS[tooltip_key]
    
    if tooltip_text:
        # Có tooltip
        header_html = f"""
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-weight:600;">{header_text}</span>
                <span style="cursor:help;color:#94A3B8;font-size:14px;" 
                      title="{tooltip_text}">ⓘ</span>
            </div>
        """
        ctx.markdown(header_html, unsafe_allow_html=True)
    else:
        # Không có tooltip
        ctx.markdown(f"**{header_text}**")


def render_metric_with_tooltip(
    label: str,
    value: str,
    tooltip_text: str | None = None,
    delta: str | None = None,
    delta_color: str = "normal",
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị metric với tooltip.
    
    Args:
        label: Nhãn metric
        value: Giá trị
        tooltip_text: Giải thích (optional)
        delta: Giá trị thay đổi (optional)
        delta_color: Màu delta (normal, inverse, off)
        container: Streamlit container
    """
    ctx = container if container is not None else st
    
    # Màu delta
    delta_color_map = {
        "normal": "#10b981",
        "inverse": "#ef4444",
        "off": "#6b7280",
    }
    delta_color_hex = delta_color_map.get(delta_color, "#6b7280")
    
    # Tạo HTML cho metric
    delta_html = ""
    if delta:
        delta_html = f'<div style="color:{delta_color_hex};font-size:14px;font-weight:500;">{delta}</div>'
    
    tooltip_icon = ""
    if tooltip_text:
        tooltip_icon = f'<span style="cursor:help;color:#94A3B8;font-size:12px;margin-left:4px;" title="{tooltip_text}">ⓘ</span>'
    
    metric_html = f"""
        <div style="background:#1E2130;color:#E0E6ED;border-radius:8px;padding:16px;border:1px solid #2A2D3E;">
            <div style="color:#94A3B8;font-size:14px;margin-bottom:4px;display:flex;align-items:center;">
                {label}{tooltip_icon}
            </div>
            <div style="font-size:24px;font-weight:700;color:#E0E6ED;">{value}</div>
            {delta_html}
        </div>
    """
    
    ctx.markdown(metric_html, unsafe_allow_html=True)


def render_formula_reference(
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị bảng tham khảo công thức tính.
    
    Args:
        container: Streamlit container
    """
    ctx = container if container is not None else st
    
    with ctx.expander("📖 Tham khảo công thức tính", expanded=False):
        st.markdown("**Các chỉ số chính:**")
        
        for metric, formula in FORMULA_TOOLTIPS.items():
            st.markdown(f"- **{metric}**: {formula}")
