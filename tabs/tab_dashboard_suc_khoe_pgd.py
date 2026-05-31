"""Dashboard Sức khỏe Tín dụng cho PGD — Gauge NQH + Heatmap rủi ro theo Xã."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_MA_KH, COT_TEN_XA
from utils import fmt_so, fmt_ty
from components.delta_card import kpi_row
from logger import get_logger

logger = get_logger(__name__)

_GAUGE_THRESHOLDS = (1.0, 2.0)


def _mau_nqh_pgd(tlqh: float) -> tuple[str, str, str]:
    if tlqh < _GAUGE_THRESHOLDS[0]:
        return "#2e7d32", "AN TOÀN", "✅"
    if tlqh < _GAUGE_THRESHOLDS[1]:
        return "#f57f17", "CẦN THEO DÕI", "⚠️"
    return "#c62828", "VƯỢT NGƯỠNG", "🚨"


def _gauge_nqh_pgd(tlqh: float, ten_pgd: str = "") -> go.Figure:
    mau, tinh_trang, _ = _mau_nqh_pgd(tlqh)
    gio_han = 5.0
    title_text = (
        f"Tỷ lệ NQH {ten_pgd or 'PGD'}<br>"
        f"<span style='font-size:14px;color:{mau};font-weight:bold'>{tinh_trang}</span>"
    )
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(tlqh, 3),
        number={"suffix": "%", "font": {"size": 40, "color": mau, "family": "Arial"}, "valueformat": ".3f"},
        delta={"reference": _GAUGE_THRESHOLDS[0], "increasing": {"color": "#c62828"}, "decreasing": {"color": "#2e7d32"},
               "suffix": "% so ngưỡng", "valueformat": ".3f"},
        gauge={
            "axis": {"range": [0, gio_han], "tickwidth": 1, "tickcolor": "#666", "ticksuffix": "%", "nticks": 6},
            "bar": {"color": mau, "thickness": 0.28},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, _GAUGE_THRESHOLDS[0]], "color": "rgba(46,125,50,0.12)"},
                {"range": [_GAUGE_THRESHOLDS[0], _GAUGE_THRESHOLDS[1]], "color": "rgba(245,127,23,0.12)"},
                {"range": [_GAUGE_THRESHOLDS[1], gio_han], "color": "rgba(198,40,40,0.12)"},
            ],
            "threshold": {"line": {"color": "#e65100", "width": 3}, "thickness": 0.82, "value": _GAUGE_THRESHOLDS[0]},
        },
        title={"text": title_text, "font": {"size": 16}},
    ))
    fig.update_layout(height=270, margin=dict(l=20, r=20, t=50, b=10),
                       paper_bgcolor="rgba(0,0,0,0)", font_family="Arial")
    return fig


def _heatmap_rui_ro_xa(df_pgd: pd.DataFrame, pgd_user: str) -> None:
    if COT_TEN_XA not in df_pgd.columns or COT_DU_NO_QH not in df_pgd.columns:
        return

    df_pgd = df_pgd.copy()
    for col in [COT_DU_NO_QH, COT_TONG_DU_NO]:
        if col in df_pgd.columns:
            df_pgd[col] = pd.to_numeric(df_pgd[col], errors="coerce").fillna(0)

    df_agg = df_pgd.groupby(COT_TEN_XA).agg({
        COT_TONG_DU_NO: "sum",
        COT_DU_NO_QH: "sum",
        COT_MA_KH: "nunique" if COT_MA_KH in df_pgd.columns else "count",
    }).reset_index()
    df_agg = df_agg.rename(columns={COT_MA_KH: "so_kh"})

    df_agg["nqh_pct"] = (df_agg[COT_DU_NO_QH] / df_agg[COT_TONG_DU_NO].replace(0, pd.NA) * 100).round(2)
    df_agg = df_agg.sort_values("nqh_pct", ascending=False)

    if df_agg.empty:
        st.info("Không đủ dữ liệu để hiển thị heatmap.")
        return

    html_rows = ""
    max_nqh = df_agg["nqh_pct"].max()
    for _, r in df_agg.iterrows():
        pct = r["nqh_pct"]
        intensity = min(pct / max(max_nqh, 1), 1.0) if max_nqh > 0 else 0
        r_int = int(255 - 200 * intensity)
        g_int = int(255 - 255 * intensity)
        b_int = int(255 - 200 * intensity)
        bg = f"rgba({r_int},{g_int},{b_int},0.35)"
        tc = "#b71c1c" if pct >= 2 else ("#ef6c00" if pct >= 1 else "#2e7d32")
        html_rows += (
            f'<tr><td style="padding:4px 8px;font-weight:500;">{r[COT_TEN_XA]}</td>'
            f'<td style="padding:4px 8px;text-align:right;">{fmt_ty(r[COT_TONG_DU_NO])}</td>'
            f'<td style="padding:4px 8px;text-align:right;">{fmt_so(r.get("so_kh", 0))}</td>'
            f'<td style="padding:4px 8px;text-align:right;color:{tc};font-weight:600;background:{bg};">{pct:.2f}%</td>'
            f'</tr>'
        )

    st.html(f"""
    <div style="overflow-x:auto;border-radius:8px;border:1px solid var(--border-color,#ddd);font-size:12px;">
      <table style="border-collapse:collapse;width:100%;">
        <thead><tr style="background:var(--secondary-background-color,#f0f2f6);">
          <th style="padding:6px 8px;">Xã/Phường</th><th style="padding:6px 8px;">Dư nợ</th>
          <th style="padding:6px 8px;">Số KH</th><th style="padding:6px 8px;">NQH%</th>
        </tr></thead>
        <tbody>{html_rows}</tbody>
      </table>
    </div>
    """)


def render(tab=None, **kwargs) -> None:
    df_pgd = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")
    role = kwargs.get("role", "user")

    st.subheader("📊 Dashboard Sức Khỏe Tín Dụng")
    st.caption(f"Phạm vi: **{pgd_user or 'PGD'}** — Đánh giá rủi ro theo các xã/phường")

    if df_pgd is None or df_pgd.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD để hiển thị dashboard.")
        return

    tdn = df_pgd[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_pgd.columns else 0
    dth = pd.to_numeric(df_pgd[COT_DU_NO_TH], errors="coerce").sum() if COT_DU_NO_TH in df_pgd.columns else 0
    dqh = df_pgd[COT_DU_NO_QH].sum() if COT_DU_NO_QH in df_pgd.columns else 0
    tlqh = dqh / tdn * 100 if tdn > 0 else 0.0
    n_kh = df_pgd[COT_MA_KH].nunique() if COT_MA_KH in df_pgd.columns else 0

    mau, tinh_trang, icon = _mau_nqh_pgd(tlqh)

    col_gauge, col_kpi = st.columns([2, 3], gap="large")
    with col_gauge:
        st.plotly_chart(_gauge_nqh_pgd(tlqh, pgd_user or "PGD"), use_container_width=True)

    with col_kpi:
        st.markdown(f"### {icon} Chỉ số Tín dụng {pgd_user or 'PGD'}")
        kpi_row([
            {"label": "Tổng dư nợ", "value": fmt_ty(tdn), "icon": "💰", "suffix": "triệu đ", "precision": 0,
             "help": f"Tổng dư nợ {pgd_user or 'PGD'}"},
            {"label": "Dư nợ trong hạn", "value": fmt_ty(dth), "icon": "✅", "suffix": "triệu đ", "precision": 0,
             "help": "Dư nợ chưa đến hạn thanh toán"},
            {"label": "Nợ quá hạn", "value": fmt_ty(dqh), "icon": "⚠️", "suffix": "triệu đ", "precision": 0,
             "delta": tlqh, "delta_label": "% NQH", "delta_color": "inverse" if tlqh >= 1 else "normal",
             "help": f"{tinh_trang}" if dqh > 0 else "✅ Không có NQH"},
            {"label": "Số khách hàng", "value": fmt_so(n_kh), "icon": "👥", "suffix": "", "precision": 0,
             "help": f"Tổng {fmt_so(len(df_pgd))} hồ sơ"},
        ], num_columns=4)

        st.markdown("---")
        pct_th = dth / tdn * 100 if tdn > 0 else 100
        st.markdown(
            f"**Tỷ lệ Dư nợ trong hạn:** "
            f"<span style='color:#90CAF9;font-weight:bold'>{pct_th:.1f}%</span> "
            f"&nbsp;|&nbsp; **NQH:** "
            f"<span style='color:{mau};font-weight:bold'>{tlqh:.3f}%</span>",
            unsafe_allow_html=True,
        )
        st.progress(
            min(pct_th / 100, 1.0),
            text=f"Sức khỏe: {pct_th:.1f}% dư nợ đang trong hạn",
        )

    st.divider()
    st.markdown("### 🔥 Heatmap Rủi ro theo Xã/Phường")
    st.caption("Điểm RR (Risk Rating) = NQH%×3 + KHĐ/KH% + Mg/KH% · Cao = Rủi ro lớn")
    _heatmap_rui_ro_xa(df_pgd, pgd_user)
