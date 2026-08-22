"""Sticky header table component cho báo cáo."""
from __future__ import annotations

import html as html_mod

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING, List, Dict, Any, Tuple

from utils import vn

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _fmt_trieu(x) -> str:
    """Số đã ở đơn vị triệu đồng → chuỗi VN 0 chữ số lẻ; NaN/vô hạn → '—'."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if x != x or x in (float("inf"), float("-inf")):
        return "—"
    return vn(x, 0)


def _badge_qh(x) -> str:
    """Badge màu cho tỷ lệ quá hạn: <1% tốt, 1–3% cảnh báo, ≥3% nguy hiểm."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if x != x:
        return "—"
    muc = "good" if x < 1 else "warn" if x < 3 else "danger"
    return f'<span class="bct-badge bct-badge-{muc}">{vn(x, 2)}%</span>'


def _thanh_ty_trong(x) -> str:
    """Thanh tiến độ nhỏ + số % cho cột tỷ trọng."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if x != x:
        return "—"
    pct = max(0.0, min(100.0, x))
    return (
        '<div class="bct-share">'
        '<div class="bct-share-track">'
        f'<div class="bct-share-fill" style="width:{pct:.1f}%"></div>'
        '</div>'
        f'<span>{vn(x, 2)}%</span>'
        '</div>'
    )


def render_bang_chi_tiet_html(
    df: pd.DataFrame,
    key: str,
    cot_ten: str,
    cot_dem: List[str] | None = None,
    cot_tien: List[str] | None = None,
    cot_bar: str | None = None,
    cot_badge: str | None = None,
    nhom_header: List[Tuple[str, int]] | None = None,
    dong_tong: Dict[str, Any] | None = None,
    height: int = 520,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Bảng chi tiết HTML theo bảng màu chuẩn UI_GUIDELINES:
    header 2 dòng (nhóm cột + tên cột), zebra, số tiền phải gióng phải,
    badge màu cho cột `cot_badge` (tỷ lệ QH), thanh tiến độ cho `cot_bar`
    (tỷ trọng), dòng TỔNG CỘNG từ `dong_tong`.

    Args:
        df: DataFrame hiển thị; cột tiền/đếm đã ở đơn vị triệu đồng / số nguyên.
        cot_ten: Cột định danh đầu tiên (gióng trái).
        cot_dem / cot_tien: Danh sách cột số đếm / tiền (triệu đồng).
        cot_bar / cot_badge: Cột vẽ thanh tỷ trọng / badge tỷ lệ QH.
        nhom_header: [(tên nhóm, colspan)] cho header dòng 1; None → 1 dòng.
        dong_tong: {cột: giá trị} cho dòng TỔNG CỘNG (định dạng như thân bảng).
        height: Chiều cao tối đa vùng cuộn (px).
    """
    ctx = container if container is not None else st
    cot_dem = cot_dem or []
    cot_tien = cot_tien or []

    def _cell_html(cot: str, val: Any) -> str:
        if cot == cot_ten:
            return f'<td class="bct-name">{html_mod.escape(str(val))}</td>'
        if cot_bar and cot == cot_bar:
            return f'<td class="bct-share-cell">{_thanh_ty_trong(val)}</td>'
        if cot_badge and cot == cot_badge:
            return f'<td class="bct-badge-cell">{_badge_qh(val)}</td>'
        if cot in cot_dem or cot in cot_tien:
            return f'<td class="bct-num">{_fmt_trieu(val)}</td>'
        # Cột số còn lại (vd phần trăm chưa phân loại)
        try:
            text = vn(float(val), 2)
        except (TypeError, ValueError):
            text = html_mod.escape(str(val))
        return f'<td class="bct-num">{text}</td>'

    cols = list(df.columns)

    # Header dòng 1 — nhóm cột
    if nhom_header:
        header1 = "".join(
            f'<th colspan="{span}">{html_mod.escape(nhom)}</th>'
            for nhom, span in nhom_header
        )
        header1_row = f'<tr class="hdr1">{header1}</tr>'
    else:
        header1_row = ""

    # Header dòng 2 — tên cột
    header2 = "".join(
        f'<th>{html_mod.escape(str(c))}</th>'
        for c in cols
    )

    # Thân bảng — zebra/hover do theme toàn cục đảm nhiệm.
    rows_html = ""
    for _, row in df.iterrows():
        cells = "".join(_cell_html(c, row[c]) for c in cols)
        rows_html += f'<tr>{cells}</tr>\n'

    # Dòng TỔNG CỘNG
    foot_html = ""
    if dong_tong:
        cells = "".join(_cell_html(c, dong_tong.get(c, "—")) for c in cols)
        foot_html = f'<tr class="bct-total">{cells}</tr>'

    html_table = f"""
<div class="bct-wrap" data-key="{html_mod.escape(key)}" style="--bct-max-height:{int(height)}px">
<table class="bct-table">
  <thead>
    {header1_row}
    <tr class="hdr2">{header2}</tr>
  </thead>
  <tbody>{rows_html}{foot_html}</tbody>
</table>
</div>
<p class="bct-note">
  * Đơn vị tiền: triệu đồng &nbsp;|&nbsp; Tỷ lệ QH:
  <span class="bct-note-good">&lt;1% tốt</span> ·
  <span class="bct-note-warn">1–3% cảnh báo</span> ·
  <span class="bct-note-danger">≥3% nguy hiểm</span>
</p>
"""
    ctx.markdown(html_table, unsafe_allow_html=True)


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
    
    # CSS dùng class toàn cục trong utils_theme.py; component chỉ dựng HTML.
    html_table = df.to_html(
        index=False,
        classes="sticky-table",
        escape=True,
    )
    wrapper = (
        f'<div class="sticky-table-wrap" data-key="{html_mod.escape(key)}" '
        f'style="--sticky-table-height:{int(height)}px">{html_table}</div>'
    )
    ctx.markdown(wrapper, unsafe_allow_html=True)


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
