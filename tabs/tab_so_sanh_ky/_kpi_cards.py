"""Dashboard KPI Cards - Components cho giao diện So sánh mốc năm hiện đại.

Style: Card-based với gradient, shadow, icon và biểu đồ donut.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils import fmt_ty, fmt_so
from tabs.tab_so_sanh_ky._common import delta_str, pct_change_str, fmt_pct_vn


# ─── CSS INJECTION ─────────────────────────────────────────────────────────

_CARD_CSS = """
<style>
/* Big Metric Card */
.big-metric-card {
    background: linear-gradient(135deg, {bg_from} 0%, {bg_to} 100%);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 4px 15px -3px rgba(0,0,0,0.1);
    border: 1px solid {border_color};
    transition: transform 0.2s ease;
}
.big-metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px -5px rgba(0,0,0,0.15);
}
.big-metric-icon {
    font-size: 2.5rem;
    margin-bottom: 12px;
    display: block;
}
.big-metric-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: {text_color};
    line-height: 1.2;
}
.big-metric-label {
    font-size: 0.95rem;
    color: {label_color};
    margin-top: 4px;
    font-weight: 500;
}
.big-metric-delta {
    font-size: 1.1rem;
    font-weight: 600;
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.delta-up { color: #16a34a; }
.delta-down { color: #dc2626; }
.delta-neutral { color: #6b7280; }

/* Progress bar in card */
.card-progress-wrap {
    margin-top: 16px;
    background: rgba(255,255,255,0.5);
    border-radius: 8px;
    height: 8px;
    overflow: hidden;
}
.card-progress-bar {
    height: 100%;
    border-radius: 8px;
    background: {progress_color};
    transition: width 0.5s ease;
}
.card-progress-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: {label_color};
    margin-top: 6px;
}

/* Mini Card */
.mini-card {
    background: white;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 2px 8px -2px rgba(0,0,0,0.08);
    border-left: 4px solid {accent_color};
    display: flex;
    align-items: center;
    gap: 12px;
}
.mini-card-icon {
    font-size: 1.5rem;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: {icon_bg};
    border-radius: 10px;
}
.mini-card-content {
    flex: 1;
}
.mini-card-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: #1f2937;
    line-height: 1.3;
}
.mini-card-label {
    font-size: 0.8rem;
    color: #6b7280;
    font-weight: 500;
}
.mini-card-delta {
    font-size: 0.85rem;
    font-weight: 600;
    margin-top: 2px;
}

/* Comparison Table */
.compact-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.9rem;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px -2px rgba(0,0,0,0.08);
}
.compact-table th {
    background: #1e3a5f;
    color: white;
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    font-size: 0.85rem;
}
.compact-table td {
    padding: 10px 16px;
    border-bottom: 1px solid #e5e7eb;
    background: white;
}
.compact-table tr:last-child td {
    border-bottom: none;
}
.compact-table tr:hover td {
    background: #f9fafb;
}
.compact-table .row-risk {
    background: #fef2f2 !important;
}
.compact-table .row-risk:hover {
    background: #fee2e2 !important;
}
.compact-table .delta-arrow {
    font-weight: 700;
    font-size: 1.1em;
}
.compact-table .arrow-up { color: #16a34a; }
.compact-table .arrow-down { color: #dc2626; }
.compact-table .value-num {
    font-weight: 600;
    font-family: 'SF Mono', monospace;
}
.compact-table .badge {
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-red { background: #fef2f2; color: #dc2626; }
.badge-green { background: #f0fdf4; color: #16a34a; }
.badge-yellow { background: #fefce8; color: #ca8a04; }
</style>
"""


def _inject_card_css(bg_from: str, bg_to: str, border_color: str, text_color: str,
                     label_color: str, progress_color: str, accent_color: str, icon_bg: str) -> None:
    """Inject CSS với dynamic colors."""
    css = _CARD_CSS.format(
        bg_from=bg_from, bg_to=bg_to, border_color=border_color,
        text_color=text_color, label_color=label_color,
        progress_color=progress_color, accent_color=accent_color, icon_bg=icon_bg
    )
    st.markdown(css, unsafe_allow_html=True)


# ─── BIG METRIC CARD ─────────────────────────────────────────────────────────

def render_big_metric_card(
    icon: str,
    label: str,
    value: str,
    delta_pct: float,
    delta_value: float,
    baseline_value: float,
    progress_pct: float,  # % so với mốc (100% = bằng mốc)
    is_inverse: bool = False,
    color_scheme: str = "blue",  # blue, red, green, purple
    key: str = "big_card",
) -> None:
    """Card lớn cho chỉ tiêu chính (Tổng dư nợ, Nợ xấu).
    
    Args:
        icon: Emoji icon
        label: Tên chỉ tiêu
        value: Giá trị hiển thị (đã format)
        delta_pct: % thay đổi so với mốc
        delta_value: Giá trị chênh lệch
        baseline_value: Giá trị mốc
        progress_pct: Phần trăm so với mốc
        is_inverse: True nếu tăng là xấu (NQH, Nợ xấu)
        color_scheme: blue|red|green|purple
        key: Streamlit key
    """
    # Color schemes
    colors = {
        "blue": {
            "bg_from": "#e0f2fe", "bg_to": "#f0f9ff",
            "border": "#7dd3fc", "text": "#0369a1",
            "label": "#0ea5e9", "progress": "#0ea5e9",
        },
        "red": {
            "bg_from": "#fef2f2", "bg_to": "#fff7ed",
            "border": "#fecaca", "text": "#dc2626",
            "label": "#ef4444", "progress": "#ef4444",
        },
        "green": {
            "bg_from": "#f0fdf4", "bg_to": "#ecfdf5",
            "border": "#bbf7d0", "text": "#16a34a",
            "label": "#22c55e", "progress": "#22c55e",
        },
        "purple": {
            "bg_from": "#f3e8ff", "bg_to": "#faf5ff",
            "border": "#d8b4fe", "text": "#9333ea",
            "label": "#a855f7", "progress": "#a855f7",
        },
    }
    c = colors.get(color_scheme, colors["blue"])
    
    # Determine if trend is good
    is_good = delta_pct > 0
    if is_inverse:
        is_good = not is_good
    
    delta_class = "delta-up" if is_good else "delta-down" if delta_pct != 0 else "delta-neutral"
    arrow = "↑" if delta_pct > 0 else "↓" if delta_pct < 0 else "→"
    delta_str_val = f"{arrow} {abs(delta_pct):.1f}% ({delta_str(delta_value, 'tien')})"
    
    # Inject CSS
    _inject_card_css(
        c["bg_from"], c["bg_to"], c["border"], c["text"],
        c["label"], c["progress"], c["progress"], f"{c['bg_from']}; color: {c['text']}"
    )
    
    # Progress bar width (cap at 100%)
    bar_width = min(abs(progress_pct), 100)
    
    html = f"""
    <div class="big-metric-card" style="background: linear-gradient(135deg, {c['bg_from']} 0%, {c['bg_to']} 100%);
                border: 1px solid {c['border']};">
        <span class="big-metric-icon">{icon}</span>
        <div class="big-metric-value" style="color: {c['text']};">{value}</div>
        <div class="big-metric-label" style="color: {c['label']};">{label}</div>
        <div class="big-metric-delta {delta_class}">
            {delta_str_val}
        </div>
        <div class="card-progress-wrap" style="background: rgba(255,255,255,0.6);">
            <div class="card-progress-bar" style="width: {bar_width}%; background: {c['progress']};"></div>
        </div>
        <div class="card-progress-labels">
            <span>Mốc: {fmt_ty(baseline_value)}</span>
            <span>{progress_pct:.1f}% vs mốc</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ─── MINI METRIC CARD ────────────────────────────────────────────────────────

def render_mini_card(
    icon: str,
    label: str,
    value: str,
    delta_value: float,
    unit: str = "tien",  # tien | so | pct
    accent_color: str = "#3b82f6",  # border-left color
    key: str = "mini_card",
) -> None:
    """Card nhỏ cho chỉ tiêu phụ.
    
    Args:
        icon: Emoji icon
        label: Tên chỉ tiêu
        value: Giá trị đã format
        delta_value: Giá trị chênh lệch
        unit: tien|so|pct
        accent_color: Màu viền trái và icon background
        key: Streamlit key
    """
    # Icon background (lighter version of accent)
    icon_bg = f"{accent_color}20"  # 20 = 12% opacity in hex
    
    delta_str_val = delta_str(delta_value, unit)
    is_positive = delta_value > 0
    delta_class = "delta-up" if is_positive else "delta-down" if delta_value < 0 else "delta-neutral"
    
    _inject_card_css(
        "#ffffff", "#ffffff", accent_color, "#1f2937",
        "#6b7280", accent_color, accent_color, icon_bg
    )
    
    html = f"""
    <div class="mini-card" style="border-left-color: {accent_color};">
        <div class="mini-card-icon" style="background: {icon_bg}; color: {accent_color};">
            {icon}
        </div>
        <div class="mini-card-content">
            <div class="mini-card-value">{value}</div>
            <div class="mini-card-label">{label}</div>
            <div class="mini-card-delta {delta_class}">{delta_str_val}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ─── MINI CARDS ROW ──────────────────────────────────────────────────────────

def render_mini_cards_row(cards_data: list[dict], key_prefix: str = "mini") -> None:
    """Render 4 mini cards trong 1 row.
    
    cards_data: list of dict with keys: icon, label, value, delta, unit, color
    """
    cols = st.columns(4)
    default_colors = ["#3b82f6", "#8b5cf6", "#eab308", "#22c55e"]
    
    for i, (col, card) in enumerate(zip(cols, cards_data)):
        with col:
            render_mini_card(
                icon=card.get("icon", "📊"),
                label=card.get("label", ""),
                value=card.get("value", ""),
                delta_value=card.get("delta", 0),
                unit=card.get("unit", "tien"),
                accent_color=card.get("color", default_colors[i]),
                key=f"{key_prefix}_{i}",
            )


# ─── DONUT CHART ─────────────────────────────────────────────────────────────

def render_debt_structure_donut(
    trong_han: float,
    qua_han: float,
    khoanh: float,
    title: str = "Cấu trúc dư nợ",
    key: str = "donut",
) -> None:
    """Biểu đồ donut hiển thị cấu trúc dư nợ.
    
    Args:
        trong_han: Dư nợ trong hạn
        qua_han: Dư nợ quá hạn
        khoanh: Dư nợ khoanh
        title: Tiêu đề biểu đồ
        key: Streamlit key
    """
    total = trong_han + qua_han + khoanh
    
    colors = ["#10b981", "#ef4444", "#f59e0b"]  # Xanh lá, đỏ, cam
    labels = ["Trong hạn", "Quá hạn", "Khoanh"]
    values = [trong_han, qua_han, khoanh]
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker_colors=colors,
        textinfo="percent",
        textposition="outside",
        textfont_size=12,
        hovertemplate="<b>%{label}</b><br>" +
                      "Giá trị: %{value:,.0f} triệu<br>" +
                      "Tỷ lệ: %{percent}<br>" +
                      "<extra></extra>",
    )])
    
    # Center annotation
    fig.add_annotation(
        text=f"<b>{fmt_ty(total)}</b><br><span style='font-size:11px'>Tổng DN</span>",
        x=0.5, y=0.5,
        font_size=16,
        showarrow=False,
    )
    
    fig.update_layout(
        title=dict(text=title, font_size=14, x=0.5),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(t=40, b=20, l=20, r=120),
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    
    st.plotly_chart(fig, use_container_width=True, key=key)


# ─── COMPARISON TABLE ────────────────────────────────────────────────────────

def render_compact_comparison_table(
    rows: list[dict],
    label_bl: str,
    label_ht: str,
    key: str = "comp_table",
) -> None:
    """Bảng so sánh compact với màu sắc.
    
    Args:
        rows: list of dict with keys:
            - label: Tên chỉ tiêu
            - value_bl: Giá trị mốc
            - value_ht: Giá trị hiện tại
            - is_risk: True nếu là chỉ tiêu rủi ro (tô màu đỏ)
            - unit: tien|so|pct
        label_bl: Tên kỳ mốc
        label_ht: Tên kỳ hiện tại
        key: Streamlit key
    """
    # Inject CSS
    _inject_card_css(
        "#ffffff", "#ffffff", "#e5e7eb", "#1f2937",
        "#6b7280", "#0ea5e9", "#0ea5e9", "#e0f2fe"
    )
    
    rows_html = []
    for row in rows:
        is_risk = row.get("is_risk", False)
        row_class = "row-risk" if is_risk else ""
        
        value_bl = row["value_bl"]
        value_ht = row["value_ht"]
        unit = row.get("unit", "tien")
        
        # Format values
        if unit == "tien":
            fmt_bl, fmt_ht = fmt_ty(value_bl), fmt_ty(value_ht)
        elif unit == "so":
            fmt_bl, fmt_ht = fmt_so(int(value_bl)), fmt_so(int(value_ht))
        else:  # pct
            fmt_bl, fmt_ht = fmt_pct_vn(value_bl), fmt_pct_vn(value_ht)
        
        # Delta
        delta_val = value_ht - value_bl
        delta_pct = ((value_ht - value_bl) / abs(value_bl) * 100) if value_bl != 0 else 0
        
        arrow = "↑" if delta_val > 0 else "↓" if delta_val < 0 else "→"
        arrow_class = "arrow-up" if delta_val > 0 else "arrow-down" if delta_val < 0 else ""
        
        delta_html = f'<span class="delta-arrow {arrow_class}">{arrow}</span> {abs(delta_pct):.1f}%'
        
        # Badge for risk indicators
        badge = ""
        if is_risk:
            if value_ht > value_bl:
                badge = '<span class="badge badge-red">↑ Tăng</span>'
            else:
                badge = '<span class="badge badge-green">↓ Giảm</span>'
        
        rows_html.append(f"""
        <tr class="{row_class}">
            <td><b>{row['label']}</b> {badge}</td>
            <td class="value-num">{fmt_bl}</td>
            <td class="value-num"><b>{fmt_ht}</b></td>
            <td>{delta_html}</td>
        </tr>
        """)
    
    html = f"""
    <table class="compact-table">
        <thead>
            <tr>
                <th>Chỉ tiêu</th>
                <th>{label_bl}</th>
                <th>{label_ht}</th>
                <th>Δ %</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows_html)}
        </tbody>
    </table>
    """
    st.markdown(html, unsafe_allow_html=True)


# ─── DASHBOARD HEADER ────────────────────────────────────────────────────────

def render_dashboard_header(
    label_ht: str,
    label_bl: str,
    key_prefix: str = "header",
) -> None:
    """Header với badge so sánh 2 kỳ."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, #1e3a5f 0%, #3b5998 100%);
        color: white;
        padding: 16px 24px;
        border-radius: 12px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    ">
        <div style="font-size: 1.1rem; font-weight: 600;">
            📊 So sánh mốc năm
        </div>
        <div style="display: flex; gap: 16px; font-size: 0.9rem;">
            <span style="background: rgba(255,255,255,0.2); padding: 6px 12px; border-radius: 20px;">
                📅 {label_bl}
            </span>
            <span>→</span>
            <span style="background: rgba(255,255,255,0.3); padding: 6px 12px; border-radius: 20px; font-weight: 600;">
                📅 {label_ht}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
