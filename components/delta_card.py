"""DeltaCard - Thẻ KPI thông minh có so sánh kỳ trước và InfoPopover."""

from __future__ import annotations

import streamlit as st


def _fmt_vn_num(val: str | float | int) -> str:
    """Format số với dấu phân cách hàng nghìn kiểu Việt Nam (dấu chấm)."""
    if isinstance(val, (int, float)):
        if val == int(val):
            return f"{int(val):,}".replace(",", ".")
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(val)


def delta_card(
    label: str,
    value: str | float | int,
    delta: float | None = None,
    delta_label: str = "so với kỳ trước",
    delta_color: str = "normal",
    help: str | None = None,
    icon: str = "",
    suffix: str = "",
    precision: int = 0,
    key: str | None = None,
    use_container_width: bool = True,
):
    """Thẻ KPI có delta + info popover.

    Args:
        label: Tên chỉ tiêu (hiển thị trên thẻ)
        value: Giá trị hiện tại
        delta: % thay đổi so với kỳ trước (vd: 5.2 = tăng 5.2%, -2.1 = giảm 2.1%)
        delta_label: Nhãn delta (mặc định "so với kỳ trước")
        delta_color: "normal" (xanh), "inverse" (đỏ ngược), "off" (xám)
        help: Nội dung giải thích (hiện khi hover icon ⓘ)
        icon: Icon emoji (vd: "💰", "📈")
        suffix: Hậu tố (vd: "triệu", "%")
        precision: Số chữ số thập phân cho delta
        key: Key cho Streamlit widget
        use_container_width: Tự động giãn chiều rộng
    """
    _value_str = _fmt_vn_num(value)
    display_value = f"{icon} {_value_str}" if icon else _value_str
    if suffix:
        display_value = f"{display_value} {suffix}"

    delta_str = None
    if delta is not None:
        sign = "+" if delta >= 0 else ""
        delta_str = f"{sign}{delta:.{precision}f}%"
    else:
        delta_str = None
        delta_color = "off"

    col1, col2 = st.columns([1, 0.05])

    with col1:
        st.metric(
            label=label,
            value=display_value,
            delta=delta_str,
            delta_color=delta_color if delta is not None else "off",
            help=help,
        )

    if help:
        with col2:
            st.markdown(
                f'<div style="padding-top:6px;cursor:help;" title="{help}">'
                f'<span style="color:#6b7a8d;font-size:14px;">ⓘ</span></div>',
                unsafe_allow_html=True,
            )


def info_popover(content: str):
    """Chú thích giải thích chỉ tiêu (dùng kèm với delta_card).

    Args:
        content: Nội dung giải thích (hỗ trợ Markdown)
    """
    st.markdown(
        f'<span style="cursor:help;color:#6b7a8d;font-size:13px;border-bottom:1px dashed #ccc;" '
        f'title="{content}">ⓘ</span>',
        unsafe_allow_html=True,
    )


def kpi_row(
    cols: list[dict],
    num_columns: int = 4,
):
    """Một hàng KPI cards.

    Args:
        cols: List các dict, mỗi dict chứa kwargs cho delta_card
        num_columns: Số cột (mặc định 4)
    """
    columns = st.columns(num_columns)
    for i, col_data in enumerate(cols):
        with columns[i % num_columns]:
            delta_card(**col_data)
