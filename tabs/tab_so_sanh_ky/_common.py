"""Shared helpers cho tab So sánh kỳ.

Formatting, KPI cards, quality bars, HTML tables, charts, flow diagram.
Tất cả hàm đều standalone (không st.*) hoặc nhận ctx để render.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from utils import fmt_ty, fmt_so, vn


# ─── FORMAT HELPERS (standalone) ──────────────────────────────────────────

def delta_str(delta: float, unit: str = "tien") -> str:
    """Format ±delta."""
    if delta == 0:
        return "0" if unit != "pct" else "0,00%"
    sign = "+" if delta > 0 else ""
    if unit == "tien":
        return f"{sign}{fmt_ty(delta)}"
    if unit == "ty":
        return f"{sign}{vn(abs(delta) / 1e9, 3)} tỷ"
    if unit == "so":
        return f"{sign}{fmt_so(int(round(delta)))}"
    return f"{sign}{abs(delta):.2f}".replace(".", ",") + "%"


def pct_change_str(v1: float, v2: float) -> str:
    """% thay đổi, trả '—' nếu v1 = 0."""
    if v1 == 0:
        return "—"
    pct = (v2 - v1) / abs(v1) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}".replace(".", ",") + "%"


def fmt_pct_vn(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + "%"


def tl_nqh(du_no_qh: float, tong_du_no: float) -> float:
    return (du_no_qh / tong_du_no * 100) if tong_du_no > 0 else 0.0


def mau_delta(delta: float, inverse: bool = False) -> str:
    """Màu CSS hex: xanh nếu delta tốt, đỏ nếu xấu."""
    if delta == 0:
        return "var(--text-muted, #6b7280)"
    good = delta > 0
    if inverse:
        good = not good
    return "var(--green, #16a34a)" if good else "var(--red, #dc2626)"


def css_delta_class(delta: float, inverse: bool = False) -> str:
    """CSS class name cho delta."""
    if delta == 0:
        return "delta-zero"
    good = delta > 0
    if inverse:
        good = not good
    return "delta-pos" if good else "delta-neg"


# ─── KPI CARDS ────────────────────────────────────────────────────────────

def render_kpi_row(metrics: list[dict], ctx=None) -> None:
    """Render 1 hàng KPI cards.

    metrics: [{"label", "value", "delta", "delta_str", "help", "inverse"", "unit"}, ...]
    """
    if ctx is None:
        ctx = st
    cols = ctx.columns(len(metrics))
    for col, m in zip(cols, metrics):
        delta_color = "inverse" if m.get("inverse") else "normal"
        d = m.get("delta")
        d_str = delta_str(d, m.get("unit", "tien")) if d is not None else None
        with col:
            st.metric(
                label=m["label"],
                value=m["value"],
                delta=d_str,
                delta_color=delta_color,
                help=m.get("help"),
            )


# ─── QUALITY BARS ────────────────────────────────────────────────────────

Q_BAR_CSS = """
<style>
.qb-wrap { margin-bottom: 20px; }
.qb-header { display:flex; justify-content:space-between; margin-bottom:4px; }
.qb-label { font-weight:600; font-size:0.84rem; }
.qb-total { color:var(--text-muted); font-size:0.8rem; }
.qb-bar { height:30px; background:var(--surface-lo,#f1f5f9); border-radius:6px; overflow:hidden; display:flex; }
.qb-bar .seg-th { background:#34d399; height:100%; }
.qb-bar .seg-qh { background:#f43f5e; height:100%; }
.qb-bar .seg-kh { background:#fbbf24; height:100%; }
.qb-legend { display:grid; grid-template-columns:1fr 1fr 1fr; font-size:0.72rem; color:var(--text-sub); margin-top:4px; }
.qb-legend .cl-th { color:#059669; font-weight:700; }
.qb-legend .cl-qh { color:#e11d48; font-weight:700; }
.qb-legend .cl-kh { color:#d97706; font-weight:700; }
/* Delta table colors — dùng bởi render_comparison_table và _render_bang_pgd */
.delta-pos { color: var(--green, #16a34a) !important; font-weight: 600; }
.delta-neg { color: var(--red,   #dc2626) !important; font-weight: 600; }
.delta-zero { color: var(--text-muted, #6b7280); }
</style>
"""


def inject_qb_css() -> None:
    st.markdown(Q_BAR_CSS, unsafe_allow_html=True)


def render_quality_bar(label: str, total: float, trong_han: float,
                       qua_han: float, khoanh: float) -> None:
    """1 thanh stacked bar chất lượng dư nợ."""
    th_pct = trong_han / total * 100 if total > 0 else 0
    qh_pct = qua_han / total * 100 if total > 0 else 0
    kh_pct = khoanh / total * 100 if total > 0 else 0
    st.markdown(
        f"""<div class="qb-wrap">
        <div class="qb-header">
          <span class="qb-label">{label}</span>
          <span class="qb-total">{fmt_ty(total)} triệu</span>
        </div>
        <div class="qb-bar">
          <div class="seg-th" style="width:{th_pct:.1f}%"></div>
          <div class="seg-qh" style="width:{qh_pct:.1f}%"></div>
          <div class="seg-kh" style="width:{kh_pct:.1f}%"></div>
        </div>
        <div class="qb-legend">
          <span>Trong hạn: <strong class="cl-th">{fmt_pct_vn(th_pct)}</strong></span>
          <span style="text-align:center">Quá hạn: <strong class="cl-qh">{fmt_pct_vn(qh_pct)}</strong></span>
          <span style="text-align:right">Khoanh: <strong class="cl-kh">{fmt_pct_vn(kh_pct)}</strong></span>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_quality_bars_2_ky(
    label1: str, total1: float, th1: float, qh1: float, kh1: float,
    label2: str, total2: float, th2: float, qh2: float, kh2: float,
) -> None:
    """2 quality bars song song cho 2 kỳ."""
    inject_qb_css()
    st.markdown("**⚡ Chất lượng dư nợ — 2 kỳ**")
    render_quality_bar(f"📅 {label1}", total1, th1, qh1, kh1)
    render_quality_bar(f"📅 {label2}", total2, th2, qh2, kh2)


# ─── HTML COMPARISON TABLE ───────────────────────────────────────────────

def render_comparison_table(
    rows: list[tuple],
    ky1: str,
    ky2: str,
    col_labels: list[str] | None = None,
    title: str = "Chỉ tiêu",
) -> None:
    """HTML table so sánh 2 kỳ.

    rows: list of (label, v1, v2, inverse, unit)
    """
    if col_labels is None:
        col_labels = [f"Kỳ {ky1}", f"Kỳ {ky2}", "Chênh lệch", "% thay đổi"]

    rows_html = ""
    for label, v1, v2, inv, unit in rows:
        d = v2 - v1
        d_str = delta_str(d, unit)
        p_str = pct_change_str(v1, v2) if unit != "pct" else delta_str(d, "pct")
        fv1 = _fv(v1, unit)
        fv2 = _fv(v2, unit)
        cl = css_delta_class(d, inv)
        rows_html += (
            f"<tr>"
            f"<td style='padding:8px 12px;font-weight:500'>{label}</td>"
            f"<td style='padding:8px 12px;text-align:right'>{fv1}</td>"
            f"<td style='padding:8px 12px;text-align:right;font-weight:600'>{fv2}</td>"
            f"<td style='padding:8px 12px;text-align:right' class='{cl}'><strong>{d_str}</strong></td>"
            f"<td style='padding:8px 12px;text-align:right' class='{cl}'>{p_str}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid var(--border,#e5e7eb)">
        <table style="width:100%;border-collapse:collapse;font-size:0.88rem">
          <thead>
            <tr style="background:var(--surface-hi,#1e3a5f);color:var(--text-head,white)">
              <th style="padding:10px 12px;text-align:left">{title}</th>
              <th style="padding:10px 12px;text-align:right">{col_labels[0]}</th>
              <th style="padding:10px 12px;text-align:right">{col_labels[1]}</th>
              <th style="padding:10px 12px;text-align:right">{col_labels[2]}</th>
              <th style="padding:10px 12px;text-align:right">{col_labels[3]}</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )


def _fv(v: float, unit: str) -> str:
    if unit == "tien":
        return fmt_ty(v)
    if unit == "so":
        return fmt_so(int(round(v)))
    return f"{v:.2f}".replace(".", ",") + "%"


# ─── HORIZONTAL BAR CHART ────────────────────────────────────────────────

def render_hbar_chart(
    labels: list[str],
    values: list[float],
    title: str = "",
    xlab: str = "Triệu đồng",
    height: int | None = None,
    key: str = "hbar",
) -> None:
    """Horizontal bar chart với màu tùy dấu."""
    colors = ["var(--green, #16a34a)" if v >= 0 else "var(--red, #dc2626)" for v in values]
    text_vals = [delta_str(v, "tien") for v in values]
    fig = go.Figure(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        text=text_vals,
        textposition="outside",
    ))
    fig.update_layout(
        title=dict(text=title, font_size=13),
        height=height or max(260, len(labels) * 34 + 60),
        margin=dict(t=30, b=20, l=10, r=100),
        xaxis_title=xlab,
        yaxis_title="",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


# ─── TREND CHART ─────────────────────────────────────────────────────────

def render_trend_chart(
    df_multi: pd.DataFrame,
    metric_cols: "str | list[str]",
    title: str = "",
    y_label: str = "Triệu đồng",
    key: str = "trend",
) -> None:
    """Line chart xu hướng nhiều kỳ.

    df_multi: DataFrame có cột 'ky' và các cột metric.
    metric_cols: tên cột (str) hoặc list để vẽ nhiều đường.
    """
    if df_multi is None or df_multi.empty or "ky" not in df_multi.columns:
        st.info("ℹ️ Chưa đủ dữ liệu để vẽ xu hướng.")
        return
    if isinstance(metric_cols, str):
        metric_cols = [metric_cols]

    fig = go.Figure()
    for col in metric_cols:
        if col not in df_multi.columns:
            continue
        fig.add_trace(go.Scatter(
            x=df_multi["ky"].astype(str).tolist(),
            y=df_multi[col].tolist(),
            mode="lines+markers",
            name=col,
            line=dict(width=2),
            marker=dict(size=6),
        ))
    fig.update_layout(
        title=dict(text=title, font_size=13),
        height=280,
        margin=dict(t=36, b=20, l=10, r=10),
        yaxis_title=y_label,
        xaxis_title="Kỳ",
        showlegend=len(metric_cols) > 1,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


# ─── MULTI-PERIOD TABLE ───────────────────────────────────────────────────

def render_multi_period_table(
    rows_multi: list[tuple],
    ky_list: list[str],
    title: str = "Chỉ tiêu",
) -> None:
    """HTML table so sánh N kỳ.

    rows_multi: list of (label, values_list, inverse, unit)
      - values_list: list float tương ứng ky_list (cùng thứ tự)
      - unit: 'tien' | 'so' | 'pct'
    """
    n = len(ky_list)
    head_ky = "".join(
        f"<th style='padding:9px 10px;text-align:right;white-space:nowrap'>Kỳ {k}</th>"
        for k in ky_list
    )
    rows_html = ""
    for label, values, inv, unit in rows_multi:
        cells = ""
        for i, v in enumerate(values):
            fv = _fv(v, unit)
            bold = " font-weight:600;" if i == n - 1 else ""
            cells += f"<td style='padding:8px 10px;text-align:right;{bold}'>{fv}</td>"
        if n >= 2 and values[0] != 0:
            d = values[-1] - values[0]
            cl = css_delta_class(d, inv)
            d_str = delta_str(d, unit)
            pct_str = pct_change_str(values[0], values[-1]) if unit != "pct" else delta_str(d, "pct")
            delta_cell = (
                f"<td style='padding:8px 10px;text-align:right' class='{cl}'>"
                f"<strong>{d_str}</strong></td>"
                f"<td style='padding:8px 10px;text-align:right' class='{cl}'>{pct_str}</td>"
            )
        else:
            delta_cell = "<td style='padding:8px 10px;text-align:right'>—</td><td style='padding:8px 10px'>—</td>"
        rows_html += (
            f"<tr style='border-bottom:1px solid var(--border,#e5e7eb)'>"
            f"<td style='padding:8px 10px;font-weight:500'>{label}</td>"
            f"{cells}{delta_cell}</tr>"
        )

    st.markdown(
        f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid var(--border,#e5e7eb)">
        <table style="width:100%;border-collapse:collapse;font-size:0.87rem">
          <thead>
            <tr style="background:var(--surface-hi,#1e3a5f);color:var(--text-head,white)">
              <th style="padding:9px 10px;text-align:left">{title}</th>
              {head_ky}
              <th style="padding:9px 10px;text-align:right">Δ (đầu→cuối)</th>
              <th style="padding:9px 10px;text-align:right">% Δ</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )


# ─── CT BREAKDOWN TABLE ───────────────────────────────────────────────────

def render_ct_breakdown_table(
    df_ct: pd.DataFrame,
    ky_label: str,
    ct_names: dict,
) -> None:
    """HTML table phân tích theo chương trình tín dụng.

    df_ct: cột [ma_ct, tong_du_no, du_no_qh, so_ho, gn_nam]
    ct_names: {ma_ct_int_or_str: ten_ct}
    """
    if df_ct is None or df_ct.empty:
        st.info("ℹ️ Chưa có dữ liệu chương trình tín dụng cho kỳ này.")
        return

    tong_dn = float(df_ct["tong_du_no"].sum()) if "tong_du_no" in df_ct.columns else 0.0

    rows_html = ""
    for _, r in df_ct.iterrows():
        ma = int(r.get("ma_ct", 0))
        ten = ct_names.get(ma) or ct_names.get(str(ma)) or f"CT {ma}"
        dn = float(r.get("tong_du_no", 0))
        nqh = float(r.get("du_no_qh", 0))
        ho = int(r.get("so_ho", 0))
        gn = float(r.get("gn_nam", 0))
        pct = dn / tong_dn * 100 if tong_dn > 0 else 0
        tl_nqh_val = nqh / dn * 100 if dn > 0 else 0
        cl_nqh = "delta-neg" if tl_nqh_val > 1 else "delta-pos"
        rows_html += (
            f"<tr style='border-bottom:1px solid var(--border,#e5e7eb)'>"
            f"<td style='padding:7px 10px'>{ten}</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_ty(dn)}</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_pct_vn(pct)}</td>"
            f"<td style='padding:7px 10px;text-align:right' class='{cl_nqh}'>{fmt_pct_vn(tl_nqh_val)}</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_so(ho)}</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_ty(gn)}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid var(--border,#e5e7eb)">
        <table style="width:100%;border-collapse:collapse;font-size:0.84rem">
          <thead>
            <tr style="background:var(--surface-hi,#1e3a5f);color:var(--text-head,white)">
              <th style="padding:9px 10px;text-align:left">Chương trình (kỳ {ky_label})</th>
              <th style="padding:9px 10px;text-align:right">Dư nợ (triệu)</th>
              <th style="padding:9px 10px;text-align:right">Cơ cấu %</th>
              <th style="padding:9px 10px;text-align:right">TL NQH%</th>
              <th style="padding:9px 10px;text-align:right">Số hộ</th>
              <th style="padding:9px 10px;text-align:right">Giải ngân (triệu)</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )


# ─── FLOW DIAGRAM ────────────────────────────────────────────────────────

def render_flow_diagram(
    prev_label: str,
    curr_label: str,
    prev_total: int,
    curr_total: int,
    retained: int,
    churned: int,
    new_cust: int,
) -> None:
    """Flow 3-box: retained → churned → new."""
    h1, h2, h3 = st.columns([2, 1, 2])
    with h1:
        st.markdown(
            f"<div style='text-align:center'>"
            f"<div style='font-size:10px;text-transform:uppercase;color:var(--text-sub);letter-spacing:.05em'>{prev_label}</div>"
            f"<div style='font-size:1.5rem;font-weight:700;color:var(--text-head)'>{fmt_so(prev_total)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            "<div style='text-align:center;color:var(--text-muted);font-size:1.3rem;padding-top:16px'>→</div>",
            unsafe_allow_html=True,
        )
    with h3:
        st.markdown(
            f"<div style='text-align:center'>"
            f"<div style='font-size:10px;text-transform:uppercase;color:var(--blue);letter-spacing:.05em'>{curr_label}</div>"
            f"<div style='font-size:1.5rem;font-weight:700;color:var(--text-head)'>{fmt_so(curr_total)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin:6px 0'></div>", unsafe_allow_html=True)

    _CELL = (
        "<div style='border-radius:8px;padding:10px 6px;text-align:center;"
        "background:{bg};outline:1px solid {border};'>"
        "<div style='font-size:10px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:.05em;opacity:.8;color:{fg}'>{label}</div>"
        "<div style='font-size:1.3rem;font-weight:700'>{count}</div>"
        "{pct}"
        "</div>"
    )
    retained_pct = (retained / prev_total * 100) if prev_total else 0
    churned_pct = (churned / prev_total * 100) if prev_total else 0
    new_pct = (new_cust / curr_total * 100) if curr_total else 0

    b1, b2, b3 = st.columns(3)
    b1.markdown(
        _CELL.format(
            bg="rgba(37,99,235,0.08)", border="rgba(37,99,235,0.25)", fg="var(--blue,#1d4ed8)",
            label="Tồn tại từ kỳ trước",
            count=fmt_so(retained),
            pct=f"<div style='font-size:10px;color:var(--text-muted)'>{fmt_pct_vn(retained_pct)} KH kỳ trước</div>",
        ),
        unsafe_allow_html=True,
    )
    b2.markdown(
        _CELL.format(
            bg="rgba(220,38,38,0.08)", border="rgba(220,38,38,0.25)", fg="var(--red,#dc2626)",
            label="Rời khỏi",
            count=fmt_so(churned),
            pct=f"<div style='font-size:10px;color:var(--text-muted)'>{fmt_pct_vn(churned_pct)} KH kỳ trước</div>",
        ),
        unsafe_allow_html=True,
    )
    b3.markdown(
        _CELL.format(
            bg="rgba(22,163,74,0.08)", border="rgba(22,163,74,0.25)", fg="var(--green,#16a34a)",
            label="Mới",
            count=fmt_so(new_cust),
            pct=f"<div style='font-size:10px;color:var(--text-muted)'>{fmt_pct_vn(new_pct)} KH kỳ này</div>",
        ),
        unsafe_allow_html=True,
    )
