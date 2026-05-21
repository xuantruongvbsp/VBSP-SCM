"""So sánh số liệu giữa kỳ hiện tại và mốc 31/12 năm đã chọn."""
from __future__ import annotations

import os

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_MA_KH,
    COT_NGAY_SL,
    COT_NGAY_VAY,
    COT_NGUON_VON,
    COT_PHAN_LOAI,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    HSTD_DS_CHO_VAY_NAM_ALIASES,
    baseline_pgd_path,
    danh_sach_nam_baseline,
    danh_sach_nam_baseline_pgd,
)
from data.hstd import doc_baseline_merged
from data.pgd import pgd_slug
from services.migration_service import danh_sach_ky, doc_snapshot
from services.period_compare import (
    CHANGE_LABELS,
    CHANGE_TYPES,
    classify_changes,
    join_by_loan,
    par_breakdown,
    roll_cure_rate,
    vintage_nqh,
)
from services.so_sanh_ky_service import (
    agg_mot_pgd as _agg_mot_pgd,
    agg_theo_pgd as _agg_theo_pgd,
    agg_theo_dvut as _agg_theo_dvut,
    group_bien_dong as _group_bien_dong,
    delta_str as _delta_str,
    tl_nqh as _tl_nqh,
    fmt_pct_vn as _fmt_pct_vn,
    ma_tran_chuyen_nhuong as _ma_tran_chuyen_nhuong,
    phan_loai_khach_hang as _phan_loai_khach_hang,
    top_movers as _top_movers,
    phan_tich_hhi_pgd as _phan_tich_hhi_pgd,
)
from utils import fmt_so, fmt_ty


_DIM_OPTIONS = [
    (COT_TEN_CT,     "Chương trình tín dụng"),
    (COT_NGUON_VON,  "Nguồn vốn"),
    (COT_TEN_XA,     "Xã"),
]


def _bang_par(df: pd.DataFrame, label: str) -> None:
    """Hiển thị PAR30/90/180 cho 1 DataFrame."""
    p = par_breakdown(df)
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "PAR30",
        _fmt_pct_vn(p["par30_pct"] * 100),
        help=f"DN > 30 ngày QH: {fmt_ty(p['par30'])}",
    )
    c2.metric(
        "PAR90",
        _fmt_pct_vn(p["par90_pct"] * 100),
        help=f"DN > 90 ngày QH: {fmt_ty(p['par90'])}",
    )
    c3.metric(
        "PAR180",
        _fmt_pct_vn(p["par180_pct"] * 100),
        help=f"DN > 180 ngày QH: {fmt_ty(p['par180'])}",
    )


def _bang_explorer(df_joined: pd.DataFrame, chon_nam: str, key_prefix: str) -> None:
    """Bảng khế ước biến động — filter theo loại thay đổi."""
    if df_joined.empty:
        st.info("Không đủ dữ liệu để hiển thị biến động khế ước.")
        return

    df_cl = classify_changes(df_joined)
    if "_change_type" not in df_cl.columns:
        return

    all_label = f"Tất cả ({len(df_cl)})"
    type_counts = df_cl["_change_label"].value_counts()
    options = [all_label] + [
        f"{lbl} ({type_counts.get(lbl, 0)})"
        for lbl in CHANGE_LABELS
        if type_counts.get(lbl, 0) > 0
    ]
    choice = st.selectbox(
        "Lọc loại biến động",
        options,
        key=f"{key_prefix}explorer_filter",
    )

    if choice != all_label:
        lbl_filter = choice.rsplit(" (", 1)[0]
        df_show = df_cl[df_cl["_change_label"] == lbl_filter]
    else:
        df_show = df_cl

    col_map = {
        COT_SO_KU + "_curr": "Số KƯ",
        COT_MA_KH + "_curr": "Mã KH",
        COT_TEN_KH + "_curr": "Tên KH",
        COT_TEN_PGD + "_curr": "Tên PGD",
        "_change_label": "Loại biến động",
        COT_TONG_DU_NO + "_prev": f"DN mốc 31/12/{chon_nam}",
        COT_TONG_DU_NO + "_curr": "DN hiện tại",
        "_du_no_delta": "Δ DN",
        COT_DU_NO_QH + "_curr": "DN QH hiện tại",
    }
    available = {k: v for k, v in col_map.items() if k in df_show.columns}

    df_out = df_show[list(available.keys())].rename(columns=available).copy()

    for col_src, col_dst in available.items():
        if col_src in (
            COT_TONG_DU_NO + "_prev",
            COT_TONG_DU_NO + "_curr",
            COT_DU_NO_QH + "_curr",
        ):
            df_out[col_dst] = df_show[col_src].fillna(0).apply(fmt_ty)
        elif col_src == "_du_no_delta":
            df_out[col_dst] = df_show[col_src].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
            )

    if "_du_no_delta" in df_show.columns:
        order = df_show["_du_no_delta"].abs().nlargest(500).index
        df_out = df_out.loc[df_out.index.intersection(order)].reindex(order).dropna(how="all")

    st.caption(f"Hiển thị {min(len(df_out), 500)} / {len(df_cl)} khế ước")
    st.dataframe(df_out.head(500), hide_index=True, use_container_width=True, height=420)


def _bang_vintage_nqh(df_ht: pd.DataFrame, df_bl: pd.DataFrame, chon_nam: str) -> None:
    """Bảng Vintage NQH: so sánh tỷ lệ NQH theo năm vay giữa mốc và hiện tại."""
    vt_ht = vintage_nqh(df_ht)
    vt_bl = vintage_nqh(df_bl)

    if vt_ht.empty and vt_bl.empty:
        st.info("Không có cột ngày vay để phân tích vintage.")
        return

    if vt_ht.empty:
        st.dataframe(vt_bl, hide_index=True, use_container_width=True)
        return
    if vt_bl.empty:
        st.dataframe(vt_ht, hide_index=True, use_container_width=True)
        return

    merged = vt_ht.merge(vt_bl, on="Năm vay", how="outer", suffixes=("_ht", "_bl")).fillna(0)
    merged = merged.sort_values("Năm vay")

    df_out = pd.DataFrame()
    df_out["Năm vay"] = merged["Năm vay"]
    df_out["DN mốc"] = merged["tong_du_no_bl"].apply(fmt_ty)
    df_out["NQH mốc"] = (merged["Tỷ lệ NQH_bl"] * 100).apply(_fmt_pct_vn)
    df_out["DN hiện tại"] = merged["tong_du_no_ht"].apply(fmt_ty)
    df_out["NQH HT"] = (merged["Tỷ lệ NQH_ht"] * 100).apply(_fmt_pct_vn)
    df_out["Δ NQH"] = ((merged["Tỷ lệ NQH_ht"] - merged["Tỷ lệ NQH_bl"]) * 100).apply(
        lambda x: ("+" if x >= 0 else "") + _fmt_pct_vn(abs(x)).replace("%", "") + "%"
    )

    st.dataframe(df_out, hide_index=True, use_container_width=True)


# ─── New visual helpers (port from PeriodOverview.tsx) ───────────────────────

def _chart_tang_truong(
    df_bl: pd.DataFrame,
    df_ht: pd.DataFrame,
    dim: str,
    label_bl: str,
    label_ht: str,
    key_prefix: str,
) -> None:
    """Grouped bar chart tăng trưởng dư nợ theo dimension, prev vs curr."""
    if COT_TONG_DU_NO not in df_bl.columns or COT_TONG_DU_NO not in df_ht.columns:
        st.info("Không đủ dữ liệu để vẽ biểu đồ.")
        return
    if dim not in df_bl.columns and dim not in df_ht.columns:
        st.info(f"Cột '{dim}' không có trong dữ liệu.")
        return

    def _group(df: pd.DataFrame) -> pd.DataFrame:
        if dim not in df.columns:
            return pd.DataFrame(columns=[dim, "dn"])
        g = df.groupby(dim, dropna=False)[COT_TONG_DU_NO].sum().reset_index()
        g.columns = [dim, "dn"]
        g[dim] = g[dim].fillna("—").astype(str)
        return g

    g_bl = _group(df_bl)
    g_ht = _group(df_ht)

    all_vals = sorted(
        set(g_bl[dim].tolist()) | set(g_ht[dim].tolist()),
    )
    focus = st.selectbox(
        "Tập trung vào",
        ["Tất cả"] + all_vals,
        key=f"{key_prefix}chart_focus_{dim}",
    )
    if focus != "Tất cả":
        g_bl = g_bl[g_bl[dim] == focus]
        g_ht = g_ht[g_ht[dim] == focus]

    g_bl = g_bl.assign(Ky=label_bl)
    g_ht = g_ht.assign(Ky=label_ht)
    combined = pd.concat([g_bl, g_ht], ignore_index=True)
    combined["dn_trieu"] = combined["dn"] / 1_000_000

    if combined.empty or combined["dn_trieu"].sum() == 0:
        st.info("Không có dữ liệu để hiển thị.")
        return

    chart = (
        alt.Chart(combined)
        .mark_bar()
        .encode(
            x=alt.X(f"{dim}:N", title=None, sort="-y",
                    axis=alt.Axis(labelAngle=-35, labelLimit=200)),
            y=alt.Y("dn_trieu:Q", title="Dư nợ (triệu đồng)"),
            color=alt.Color(
                "Ky:N",
                scale=alt.Scale(
                    domain=[label_bl, label_ht],
                    range=["#94a3b8", "#2563eb"],
                ),
                legend=alt.Legend(title="Kỳ"),
            ),
            xOffset="Ky:N",
            tooltip=[
                alt.Tooltip(f"{dim}:N", title=dim),
                alt.Tooltip("Ky:N", title="Kỳ"),
                alt.Tooltip("dn_ty:Q", title="Dư nợ (tỷ)", format=",.3f"),
            ],
        )
        .properties(height=340)
    )
    st.altair_chart(chart, use_container_width=True)


def _flow_diagram(
    prev_label: str,
    curr_label: str,
    prev_total: int,
    curr_total: int,
    left_label: str,
    left_count: int,
    mid_label: str,
    mid_count: int,
    right_label: str,
    right_count: int,
    badge: str = "",
) -> None:
    """Visual flow diagram dạng 3-box (port từ FlowDiagram.tsx)."""
    h1, h2, h3 = st.columns([2, 1, 2])
    with h1:
        st.markdown(
            f"<div style='text-align:center'>"
            f"<div style='font-size:10px;text-transform:uppercase;color:#64748b;letter-spacing:.05em'>{prev_label}</div>"
            f"<div style='font-size:1.6rem;font-weight:700;color:#0f172a'>{fmt_so(prev_total)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            "<div style='text-align:center;color:#94a3b8;font-size:1.2rem;padding-top:18px'>→</div>",
            unsafe_allow_html=True,
        )
    with h3:
        st.markdown(
            f"<div style='text-align:center'>"
            f"<div style='font-size:10px;text-transform:uppercase;color:#1d4ed8;letter-spacing:.05em'>{curr_label}</div>"
            f"<div style='font-size:1.6rem;font-weight:700;color:#1e3a8a'>{fmt_so(curr_total)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin:8px 0'></div>", unsafe_allow_html=True)

    _CELL = (
        "<div style='border-radius:8px;padding:10px 6px;text-align:center;"
        "background:{bg};color:{fg};outline:1px solid {border};'>"
        "<div style='font-size:10px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:.05em;opacity:.8'>{label}</div>"
        "<div style='font-size:1.3rem;font-weight:700'>{count}</div>"
        "{badge}"
        "</div>"
    )
    badge_html = (
        f"<div style='font-size:10px;font-weight:600;margin-top:2px'>{badge}</div>"
        if badge else ""
    )
    b1, b2, b3 = st.columns(3)
    b1.markdown(
        _CELL.format(bg="#f1f5f9", fg="#475569", border="#e2e8f0",
                     label=left_label, count=fmt_so(left_count), badge=""),
        unsafe_allow_html=True,
    )
    b2.markdown(
        _CELL.format(bg="#dbeafe", fg="#1e40af", border="#bfdbfe",
                     label=mid_label, count=fmt_so(mid_count), badge=badge_html),
        unsafe_allow_html=True,
    )
    b3.markdown(
        _CELL.format(bg="#d1fae5", fg="#065f46", border="#a7f3d0",
                     label=right_label, count=fmt_so(right_count), badge=""),
        unsafe_allow_html=True,
    )


def _quality_bars(
    snap_bl: dict,
    snap_ht: dict,
    label_bl: str,
    label_ht: str,
) -> None:
    """Stacked bar Trong hạn / Quá hạn / Khoanh cho 2 kỳ (port từ QualityStackedBars.tsx)."""
    max_total = max(snap_bl.get("total", 0), snap_ht.get("total", 0), 1)

    def _row(label: str, snap: dict) -> None:
        total = snap.get("total", 0)
        th = snap.get("trong_han", 0)
        qh = snap.get("qua_han", 0)
        kh = snap.get("khoanh", 0)

        width_pct = (total / max_total * 100) if max_total > 0 else 0
        th_pct = (th / total * 100) if total > 0 else 0
        qh_pct = (qh / total * 100) if total > 0 else 0
        kh_pct = (kh / total * 100) if total > 0 else 0

        st.markdown(
            f"<div style='margin-bottom:2px;display:flex;justify-content:space-between'>"
            f"<span style='font-size:12px;font-weight:600;color:#334155'>{label}</span>"
            f"<span style='font-size:11px;color:#64748b'>{fmt_ty(total)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        seg_th = (
            f"<div style='width:{th_pct:.2f}%;background:#34d399;height:100%' "
            f"title='Trong hạn {fmt_ty(th)}'></div>"
        ) if th_pct > 0 else ""
        seg_qh = (
            f"<div style='width:{qh_pct:.2f}%;background:#f43f5e;height:100%' "
            f"title='Quá hạn {fmt_ty(qh)}'></div>"
        ) if qh_pct > 0 else ""
        seg_kh = (
            f"<div style='width:{kh_pct:.2f}%;background:#fbbf24;height:100%' "
            f"title='Khoanh {fmt_ty(kh)}'></div>"
        ) if kh_pct > 0 else ""
        st.markdown(
            f"<div style='position:relative;height:28px;background:#f1f5f9;border-radius:6px;overflow:hidden'>"
            f"<div style='position:absolute;inset:0;display:flex;width:{width_pct:.2f}%'>"
            f"{seg_th}{seg_qh}{seg_kh}"
            f"</div></div>"
            f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;font-size:10px;color:#64748b;margin-top:3px'>"
            f"<span>Trong hạn: <strong style='color:#059669'>{_fmt_pct_vn(th_pct)}</strong></span>"
            f"<span style='text-align:center'>Quá hạn: <strong style='color:#e11d48'>{_fmt_pct_vn(qh_pct)}</strong></span>"
            f"<span style='text-align:right'>Khoanh: <strong style='color:#d97706'>{_fmt_pct_vn(kh_pct)}</strong></span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    _row(label_bl, snap_bl)
    st.markdown("<div style='margin:12px 0'></div>", unsafe_allow_html=True)
    _row(label_ht, snap_ht)


# ─── Top biến động (VSPPRO PeriodMovers) ─────────────────────────────────────

_METRIC_OPTS = {
    "du_no":   "Tổng dư nợ",
    "nqh_pct": "Tỷ lệ NQH%",
    "so_ku":   "Số khế ước",
}
_DIM_BIEN_DONG = [
    (COT_TEN_PGD, "PGD"),
    (COT_TEN_XA,  "Xã"),
    (COT_TEN_CT,  "Chương trình"),
    (COT_DVUT,    "Hội đoàn thể"),
]


def _render_top_bien_dong(
    df_bl: pd.DataFrame,
    df_ht: pd.DataFrame,
    label_bl: str,
    label_ht: str,
    key_prefix: str,
) -> None:
    """
    Top biến động 2 kỳ — VSPPRO PeriodMovers port.
    Hiển thị Top N tăng / Top N giảm theo chiều và chỉ tiêu.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.info("Cần cài plotly để xem biểu đồ Top biến động.")
        return

    dim_labels = {k: v for k, v in _DIM_BIEN_DONG}
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        dim_sel = st.selectbox(
            "Phân tích theo chiều",
            [k for k, _ in _DIM_BIEN_DONG],
            format_func=lambda x: dim_labels.get(x, x),
            key=f"{key_prefix}tbdong_dim",
        )
    with c2:
        metric_sel = st.selectbox(
            "Chỉ tiêu so sánh",
            list(_METRIC_OPTS.keys()),
            format_func=lambda x: _METRIC_OPTS[x],
            key=f"{key_prefix}tbdong_metric",
        )
    with c3:
        n = st.slider("Top N", 3, 10, 5, key=f"{key_prefix}tbdong_n")

    if df_bl.empty or df_ht.empty:
        st.info("Không đủ dữ liệu để hiển thị top biến động.")
        return

    g_ht = _group_bien_dong(df_ht, dim_sel)
    g_bl = _group_bien_dong(df_bl, dim_sel)

    merged = g_ht.merge(g_bl, on=dim_sel, how="outer", suffixes=("_ht", "_bl")).fillna(0)
    merged["delta"] = merged[f"{metric_sel}_ht"] - merged[f"{metric_sel}_bl"]
    merged = merged[merged[dim_sel].astype(str).str.strip() != ""]

    top_tang  = merged.nlargest(n, "delta")
    top_giam  = merged.nsmallest(n, "delta")

    def _label(val: float) -> str:
        sign = "+" if val >= 0 else ""
        if metric_sel == "du_no":
            return sign + fmt_ty(val)
        if metric_sel == "nqh_pct":
            return sign + f"{val:.2f}".replace(".", ",") + " pp"
        return sign + fmt_so(int(val))

    def _make_bar(df_top: pd.DataFrame, color: str, key: str) -> None:
        if df_top.empty:
            return
        fig = go.Figure(go.Bar(
            y=df_top[dim_sel].astype(str),
            x=df_top["delta"],
            orientation="h",
            marker_color=color,
            text=df_top["delta"].apply(_label),
            textposition="outside",
        ))
        fig.update_layout(
            height=max(220, n * 38 + 60),
            margin=dict(t=10, b=20, l=10, r=70),
            xaxis_title=_METRIC_OPTS[metric_sel],
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True, key=key)

    col_tang, col_giam = st.columns(2)
    with col_tang:
        st.markdown(f"**📈 Top {n} tăng mạnh — {_METRIC_OPTS[metric_sel]}**")
        _make_bar(
            top_tang.sort_values("delta", ascending=True),
            "#2e7d32",
            f"{key_prefix}tbdong_tang",
        )
    with col_giam:
        st.markdown(f"**📉 Top {n} giảm mạnh — {_METRIC_OPTS[metric_sel]}**")
        _make_bar(
            top_giam.sort_values("delta", ascending=False),
            "#c62828",
            f"{key_prefix}tbdong_giam",
        )

    # Bảng tổng hợp
    with st.expander(f"📋 Bảng đầy đủ ({_METRIC_OPTS[metric_sel]})", expanded=False):
        out = merged.sort_values("delta", ascending=False).copy()
        out["Giá trị mốc"] = out[f"{metric_sel}_bl"].apply(_label)
        out["Giá trị HT"]  = out[f"{metric_sel}_ht"].apply(_label)
        out["Δ thay đổi"]  = out["delta"].apply(_label)
        cols_show = [dim_sel, "Giá trị mốc", "Giá trị HT", "Δ thay đổi"]
        st.dataframe(out[cols_show], hide_index=True, use_container_width=True)


# ─── Radar + Ranking (VSPPRO Compare port) ───────────────────────────────────

def _render_radar_ranking(
    df_ht: pd.DataFrame,
    key_prefix: str,
) -> None:
    """
    Ranking horizontal bar + Radar đa trục so sánh PGD.
    Port từ VSPPRO Compare.tsx.
    """
    try:
        import plotly.graph_objects as go
        import numpy as np
    except ImportError:
        st.info("Cần cài plotly để xem biểu đồ Radar/Ranking.")
        return

    if df_ht.empty or COT_TEN_PGD not in df_ht.columns:
        st.info("Cần dữ liệu theo PGD để hiển thị biểu đồ.")
        return

    # Tổng hợp theo PGD
    agg: dict = {"so_ku": (COT_SO_KU, "nunique")}
    if COT_TONG_DU_NO in df_ht.columns:
        agg["du_no"] = (COT_TONG_DU_NO, "sum")
    if COT_DU_NO_QH in df_ht.columns:
        agg["du_no_qh"] = (COT_DU_NO_QH, "sum")
    if COT_LAI_TON in df_ht.columns:
        agg["lai_ton"] = (COT_LAI_TON, "sum")
    if COT_MA_KH in df_ht.columns:
        agg["so_ho"] = (COT_MA_KH, "nunique")

    g = df_ht.groupby(COT_TEN_PGD, dropna=False).agg(**agg).reset_index()
    if "du_no" not in g.columns:
        g["du_no"] = 0
    if "du_no_qh" not in g.columns:
        g["du_no_qh"] = 0
    g["nqh_pct"] = (g["du_no_qh"] / g["du_no"].replace(0, float("nan")) * 100).fillna(0)
    tong_cn = g["du_no"].sum()
    g["ty_trong_pct"] = (g["du_no"] / tong_cn * 100).fillna(0) if tong_cn > 0 else 0

    # ── Sub-tabs Ranking / Radar ──────────────────────────────────────────
    r1, r2 = st.tabs(["📊 Xếp hạng PGD", "🕸️ Radar đa chiều"])

    with r1:
        metric_rank = st.selectbox(
            "Xếp hạng theo",
            ["du_no", "nqh_pct", "so_ku", "ty_trong_pct"],
            format_func=lambda x: {
                "du_no": "Tổng dư nợ",
                "nqh_pct": "Tỷ lệ NQH%",
                "so_ku": "Số khế ước",
                "ty_trong_pct": "Tỷ trọng DN%",
            }[x],
            key=f"{key_prefix}rank_metric",
        )
        g_sorted = g.sort_values(metric_rank, ascending=True)

        if metric_rank == "du_no":
            text_vals = g_sorted["du_no"].apply(fmt_ty)
            xlab = "Tỷ đồng"
        elif metric_rank == "nqh_pct":
            text_vals = g_sorted["nqh_pct"].apply(
                lambda x: f"{x:.2f}".replace(".", ",") + "%"
            )
            xlab = "Tỷ lệ NQH%"
        elif metric_rank == "so_ku":
            text_vals = g_sorted["so_ku"].apply(fmt_so)
            xlab = "Số khế ước"
        else:
            text_vals = g_sorted["ty_trong_pct"].apply(
                lambda x: f"{x:.1f}".replace(".", ",") + "%"
            )
            xlab = "Tỷ trọng%"

        # Màu: đỏ nếu NQH trên trung bình, xanh ngược lại
        if metric_rank == "nqh_pct":
            avg = g["nqh_pct"].mean()
            colors = ["#c62828" if v > avg else "#1565c0" for v in g_sorted["nqh_pct"]]
        else:
            colors = "#1565c0"

        fig = go.Figure(go.Bar(
            y=g_sorted[COT_TEN_PGD].astype(str),
            x=g_sorted[metric_rank],
            orientation="h",
            marker_color=colors,
            text=text_vals,
            textposition="outside",
        ))
        fig.update_layout(
            height=max(420, len(g_sorted) * 26 + 80),
            margin=dict(t=10, b=30, l=10, r=90),
            xaxis_title=xlab,
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}ranking_chart")

    with r2:
        st.caption(
            "Mỗi trục = 1 chỉ tiêu (chuẩn hóa về [0,1]). "
            "Polygon lớn hơn = hiệu suất tốt hơn (trừ NQH — polygon nhỏ hơn = tốt hơn)."
        )
        n_top = st.slider(
            "Hiển thị top N PGD theo dư nợ",
            3, min(10, len(g)), min(8, len(g)),
            key=f"{key_prefix}radar_n",
        )
        top_pgd = g.nlargest(n_top, "du_no")

        kpis = ["du_no", "so_ku", "ty_trong_pct"]
        kpi_labels = ["Dư nợ", "Số KƯ", "Tỷ trọng%"]
        if "lai_ton" in g.columns:
            kpis.append("lai_ton")
            kpi_labels.append("Lãi tồn")
        kpis.append("nqh_pct")
        kpi_labels.append("NQH% (inv)")

        # Normalize [0,1], invert NQH
        def _norm(series: pd.Series, invert: bool = False) -> pd.Series:
            mn, mx = series.min(), series.max()
            if mx == mn:
                return pd.Series(0.5, index=series.index)
            n = (series - mn) / (mx - mn)
            return 1 - n if invert else n

        top_pgd = top_pgd.copy()
        for kpi in kpis:
            if kpi in top_pgd.columns:
                inv = kpi == "nqh_pct"
                top_pgd[f"_n_{kpi}"] = _norm(top_pgd[kpi], invert=inv).values

        fig_r = go.Figure()
        theta = kpi_labels + [kpi_labels[0]]

        for _, row in top_pgd.iterrows():
            r_vals = [row.get(f"_n_{k}", 0) for k in kpis]
            r_vals += [r_vals[0]]
            fig_r.add_trace(go.Scatterpolar(
                r=r_vals,
                theta=theta,
                fill="toself",
                opacity=0.35,
                name=str(row[COT_TEN_PGD]),
            ))

        fig_r.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            legend=dict(orientation="v", x=1.05),
            height=420,
            margin=dict(t=40, b=20, l=40, r=160),
        )
        st.plotly_chart(fig_r, use_container_width=True, key=f"{key_prefix}radar_chart")


# ─────────────────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    pgd_mode = kwargs.get("pgd_mode", False)

    ctx = tab if tab is not None else st.container()

    if pgd_mode and pgd_user:
        key_prefix = f"pgd_{pgd_slug(pgd_user)}_"
    else:
        key_prefix = "cn_"

    with ctx:
        st.subheader("📈 So sánh kỳ — Hiện tại vs Mốc 31/12")

        # ── Chọn năm baseline ─────────────────────────────────────────────
        ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()
        if not ds_nam:
            st.warning("⚠️ Chưa có dữ liệu năm trước để so sánh.")
            st.markdown(
                """
**Cách thêm dữ liệu mốc 31/12:**

1. Vào menu **Hệ thống → Upload dữ liệu**
2. Mở phần **📅 Upload mốc số liệu 31/12 (Baseline)**
3. Chọn năm (ví dụ: 2025) và upload file HSTD của ngày 31/12 năm đó
4. Quay lại tab này — dữ liệu so sánh sẽ hiện ra tự động

> File cần upload có định dạng giống file HSTD thường (sheet **BCQUERY**, header dòng 5).
                """
            )
            return

        chon_nam = st.selectbox(
            "So sánh với mốc 31/12 năm",
            ds_nam,
            key=f"{key_prefix}ssk_nam",
        )

        # ── Đọc baseline ──────────────────────────────────────────────────
        fp_check = baseline_pgd_path(pgd_user if pgd_user else "hoi_so", chon_nam)
        _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0
        df_bl_full = doc_baseline_merged(chon_nam, _ts=_ts)

        if df_bl_full is None or df_bl_full.empty:
            st.warning(f"⚠️ Chưa có dữ liệu baseline 31/12/{chon_nam}.")
            return

        if pgd_mode and pgd_user and COT_TEN_PGD in df_bl_full.columns:
            df_bl = df_bl_full[df_bl_full[COT_TEN_PGD] == pgd_user].copy()
        else:
            df_bl = df_bl_full

        df_ht = df if pgd_mode else df_full
        if df_ht is None or df_ht.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD hiện tại.")
            return

        # ── Tổng hợp toàn bộ ─────────────────────────────────────────────
        agg_ht = _agg_mot_pgd(df_ht)
        agg_bl = _agg_mot_pgd(df_bl)

        df_joined = join_by_loan(df_bl, df_ht)

        ngay_sl = ""
        if COT_NGAY_SL in df_ht.columns:
            sl = df_ht[COT_NGAY_SL].dropna()
            if len(sl):
                ngay_sl = str(sl.iloc[0])

        label_bl = f"31/12/{chon_nam}"
        label_ht = ngay_sl or "Hiện tại"

        st.caption(
            f"**Kỳ hiện tại:** {label_ht} &nbsp;|&nbsp; "
            f"**Mốc so sánh:** {label_bl}"
        )
        st.divider()

        # ═══════════ 12 KPI CARDS (3 hàng × 4) ══════════════════════════
        st.markdown("**📊 Chỉ tiêu cốt lõi · Δ giữa hai kỳ**")

        tl_nqh_ht   = _tl_nqh(agg_ht["du_no_qh"], agg_ht["tong_du_no"])
        tl_nqh_bl   = _tl_nqh(agg_bl["du_no_qh"], agg_bl["tong_du_no"])
        tl_kh_ht    = _tl_nqh(agg_ht["du_no_khoanh"], agg_ht["tong_du_no"])
        tl_kh_bl    = _tl_nqh(agg_bl["du_no_khoanh"], agg_bl["tong_du_no"])
        no_xau_ht   = agg_ht["du_no_qh"] + agg_ht["du_no_khoanh"]
        no_xau_bl   = agg_bl["du_no_qh"] + agg_bl["du_no_khoanh"]
        tl_nx_ht    = _tl_nqh(no_xau_ht, agg_ht["tong_du_no"])
        tl_nx_bl    = _tl_nqh(no_xau_bl, agg_bl["tong_du_no"])
        muc_vay_ht  = agg_ht["tong_du_no"] / agg_ht["so_ho"] if agg_ht["so_ho"] > 0 else 0
        muc_vay_bl  = agg_bl["tong_du_no"] / agg_bl["so_ho"] if agg_bl["so_ho"] > 0 else 0

        # Hàng 1 — tăng trưởng
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        r1c1.metric("Tổng dư nợ", fmt_ty(agg_ht["tong_du_no"]),
                    delta=_delta_str(agg_ht["tong_du_no"], agg_bl["tong_du_no"]),
                    help=f"Mốc {label_bl}: {fmt_ty(agg_bl['tong_du_no'])}")
        r1c2.metric("Số khế ước", fmt_so(agg_ht["so_ku"]),
                    delta=_delta_str(agg_ht["so_ku"], agg_bl["so_ku"], unit="so"),
                    help=f"Mốc {label_bl}: {fmt_so(agg_bl['so_ku'])}")
        r1c3.metric("Số hộ vay", fmt_so(agg_ht["so_ho"]),
                    delta=_delta_str(agg_ht["so_ho"], agg_bl["so_ho"], unit="so"),
                    help=f"Mốc {label_bl}: {fmt_so(agg_bl['so_ho'])}")
        r1c4.metric("Mức vay BQ/KH", fmt_ty(muc_vay_ht),
                    delta=_delta_str(muc_vay_ht, muc_vay_bl),
                    help=f"Mốc {label_bl}: {fmt_ty(muc_vay_bl)}")

        # Hàng 2 — NQH & khoanh
        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        r2c1.metric("Tỷ lệ NQH", _fmt_pct_vn(tl_nqh_ht),
                    delta=_fmt_pct_vn(tl_nqh_ht - tl_nqh_bl), delta_color="inverse",
                    help=f"Mốc {label_bl}: {_fmt_pct_vn(tl_nqh_bl)}")
        r2c2.metric("Dư nợ quá hạn", fmt_ty(agg_ht["du_no_qh"]),
                    delta=_delta_str(agg_ht["du_no_qh"], agg_bl["du_no_qh"]), delta_color="inverse",
                    help=f"Mốc {label_bl}: {fmt_ty(agg_bl['du_no_qh'])}")
        r2c3.metric("Dư nợ khoanh", fmt_ty(agg_ht["du_no_khoanh"]),
                    delta=_delta_str(agg_ht["du_no_khoanh"], agg_bl["du_no_khoanh"]), delta_color="inverse",
                    help=f"Mốc {label_bl}: {fmt_ty(agg_bl['du_no_khoanh'])}")
        r2c4.metric("Tỷ lệ DN khoanh", _fmt_pct_vn(tl_kh_ht),
                    delta=_fmt_pct_vn(tl_kh_ht - tl_kh_bl), delta_color="inverse",
                    help=f"Mốc {label_bl}: {_fmt_pct_vn(tl_kh_bl)}")

        # Hàng 3 — Nợ xấu & lãi tồn
        r3c1, r3c2, r3c3, r3c4 = st.columns(4)
        r3c1.metric("Nợ xấu (QH + Khoanh)", fmt_ty(no_xau_ht),
                    delta=_delta_str(no_xau_ht, no_xau_bl), delta_color="inverse",
                    help=f"Mốc {label_bl}: {fmt_ty(no_xau_bl)}")
        r3c2.metric("Tỷ lệ Nợ xấu", _fmt_pct_vn(tl_nx_ht),
                    delta=_fmt_pct_vn(tl_nx_ht - tl_nx_bl), delta_color="inverse",
                    help=f"Mốc {label_bl}: {_fmt_pct_vn(tl_nx_bl)}")
        r3c3.metric("Tổng lãi tồn (TH+QH)", fmt_ty(agg_ht["tong_lai_ton"]),
                    delta=_delta_str(agg_ht["tong_lai_ton"], agg_bl["tong_lai_ton"]), delta_color="inverse",
                    help=f"Mốc {label_bl}: {fmt_ty(agg_bl['tong_lai_ton'])}")
        r3c4.metric("Giải ngân trong năm", fmt_ty(agg_ht["gn_nam"]),
                    delta=_delta_str(agg_ht["gn_nam"], agg_bl["gn_nam"]),
                    help=f"Mốc {label_bl}: {fmt_ty(agg_bl['gn_nam'])}")

        st.divider()

        # ── Chi tiết chỉ tiêu ─────────────────────────────────────────────
        with st.expander("📋 Chi tiết chỉ tiêu", expanded=True):
            rows = [
                ("Tổng dư nợ",           agg_bl["tong_du_no"],    agg_ht["tong_du_no"],    "ty"),
                ("  Dư nợ trong hạn",    agg_bl["du_no_th"],      agg_ht["du_no_th"],      "ty"),
                ("  Dư nợ quá hạn",      agg_bl["du_no_qh"],      agg_ht["du_no_qh"],      "ty"),
                ("  Dư nợ khoanh",       agg_bl["du_no_khoanh"],  agg_ht["du_no_khoanh"],  "ty"),
                ("Nợ xấu (QH + Khoanh)", no_xau_bl,               no_xau_ht,               "ty"),
                ("Tổng lãi tồn (TH+QH)", agg_bl["tong_lai_ton"],  agg_ht["tong_lai_ton"],  "ty"),
                ("Giải ngân trong năm",  agg_bl["gn_nam"],        agg_ht["gn_nam"],        "ty"),
                ("Số hộ vay",            agg_bl["so_ho"],         agg_ht["so_ho"],         "so"),
                ("Số khế ước",           agg_bl["so_ku"],         agg_ht["so_ku"],         "so"),
            ]
            data_ct = []
            for ten, bl_val, ht_val, unit in rows:
                delta = ht_val - bl_val
                pct = (delta / bl_val * 100) if bl_val != 0 else 0.0
                sign = "+" if delta >= 0 else ""
                data_ct.append({
                    "Chỉ tiêu": ten,
                    f"Mốc {label_bl}": fmt_ty(bl_val) if unit == "ty" else fmt_so(int(bl_val)),
                    "Hiện tại":        fmt_ty(ht_val) if unit == "ty" else fmt_so(int(ht_val)),
                    "Chênh lệch":      f"{sign}{fmt_ty(delta)}" if unit == "ty" else f"{sign}{fmt_so(int(delta))}",
                    "% thay đổi":      f"{sign}{pct:.2f}".replace(".", ",") + "%",
                })
            df_ct = pd.DataFrame(data_ct)
            st.dataframe(df_ct, hide_index=True, use_container_width=True)

        # ═══════════ TĂNG TRƯỞNG DƯ NỢ ══════════════════════════════════
        st.divider()
        st.markdown("**📊 Tăng trưởng dư nợ**")

        dim_labels = {col: lbl for col, lbl in _DIM_OPTIONS}
        dim_sel = st.radio(
            "Phân tích theo",
            options=[col for col, _ in _DIM_OPTIONS],
            format_func=lambda x: dim_labels[x],
            horizontal=True,
            key=f"{key_prefix}chart_dim",
        )
        _chart_tang_truong(df_bl, df_ht, dim_sel, label_bl, label_ht, key_prefix)

        # ═══════════ VÒNG ĐỜI KHẾ ƯỚC / KHÁCH HÀNG ═════════════════════
        st.divider()
        st.markdown("**🔄 Vòng đời danh mục**")

        # Tính loan lifecycle
        prev_total_loans = agg_bl["so_ku"]
        curr_total_loans = agg_ht["so_ku"]
        prev_col = COT_SO_KU + "_prev"
        curr_col = COT_SO_KU + "_curr"
        if (
            not df_joined.empty
            and prev_col in df_joined.columns
            and curr_col in df_joined.columns
        ):
            retained_loans = int(
                df_joined[[prev_col, curr_col]].notna().all(axis=1).sum()
            )
        else:
            retained_loans = min(prev_total_loans, curr_total_loans)
        closed_loans = max(0, prev_total_loans - retained_loans)
        new_loans    = max(0, curr_total_loans - retained_loans)

        # Tính customer lifecycle
        ma_kh_bl = (
            set(df_bl[COT_MA_KH].astype(str).str.strip())
            if COT_MA_KH in df_bl.columns else set()
        )
        ma_kh_ht = (
            set(df_ht[COT_MA_KH].astype(str).str.strip())
            if COT_MA_KH in df_ht.columns else set()
        )
        prev_total_cust = len(ma_kh_bl)
        curr_total_cust = len(ma_kh_ht)
        retained_cust   = len(ma_kh_bl & ma_kh_ht)
        churned_cust    = len(ma_kh_bl - ma_kh_ht)
        new_cust        = len(ma_kh_ht - ma_kh_bl)

        lc1, lc2 = st.columns(2)
        with lc1:
            st.markdown("**Khế ước**")
            _flow_diagram(
                prev_label=f"KƯ {label_bl}",
                curr_label=f"KƯ {label_ht}",
                prev_total=prev_total_loans,
                curr_total=curr_total_loans,
                left_label="Đã tất toán",
                left_count=closed_loans,
                mid_label="Duy trì",
                mid_count=retained_loans,
                right_label="Khế ước mới",
                right_count=new_loans,
            )
        with lc2:
            st.markdown("**Khách hàng**")
            _flow_diagram(
                prev_label=f"KH {label_bl}",
                curr_label=f"KH {label_ht}",
                prev_total=prev_total_cust,
                curr_total=curr_total_cust,
                left_label="Đã rời danh mục",
                left_count=churned_cust,
                mid_label="Còn vay",
                mid_count=retained_cust,
                right_label="Khách hàng mới",
                right_count=new_cust,
            )

        # ═══════════ CHẤT LƯỢNG DƯ NỢ ════════════════════════════════════
        st.divider()
        st.markdown("**📐 Cơ cấu chất lượng dư nợ**")

        def _snap(agg: dict) -> dict:
            total = agg["tong_du_no"]
            th = agg["du_no_th"]
            qh = agg["du_no_qh"]
            kh = agg["du_no_khoanh"]
            if th == 0 and total > 0:
                th = max(0.0, total - qh - kh)
            return {"trong_han": th, "qua_han": qh, "khoanh": kh, "total": total}

        _quality_bars(
            snap_bl=_snap(agg_bl),
            snap_ht=_snap(agg_ht),
            label_bl=f"Kỳ trước · {label_bl}",
            label_ht=f"Kỳ sau · {label_ht}",
        )

        # ═══════════ BẢNG THEO PGD (chỉ CN role) ═════════════════════════
        if la_phan_he_cn(role) and not pgd_mode:
            st.divider()
            st.markdown("**🗺️ Chi tiết theo PGD**")

            df_pgd_ht = _agg_theo_pgd(df_full)
            df_pgd_bl = _agg_theo_pgd(df_bl_full)

            if df_pgd_ht.empty or df_pgd_bl.empty:
                st.info("Không đủ dữ liệu để so sánh theo PGD.")
                return

            df_merge = df_pgd_ht.merge(
                df_pgd_bl,
                on=COT_TEN_PGD,
                how="outer",
                suffixes=("_ht", "_bl"),
            ).fillna(0)

            df_merge["Δ Dư nợ"] = df_merge["tong_du_no_ht"] - df_merge["tong_du_no_bl"]
            df_merge["Δ DN %"]  = df_merge.apply(
                lambda r: (r["Δ Dư nợ"] / r["tong_du_no_bl"] * 100) if r["tong_du_no_bl"] != 0 else 0.0,
                axis=1,
            )
            df_merge["NQH mốc"] = df_merge.apply(
                lambda r: _tl_nqh(r["du_no_qh_bl"], r["tong_du_no_bl"]), axis=1
            )
            df_merge["NQH HT"] = df_merge.apply(
                lambda r: _tl_nqh(r["du_no_qh_ht"], r["tong_du_no_ht"]), axis=1
            )
            df_merge["Δ NQH"] = df_merge["NQH HT"] - df_merge["NQH mốc"]
            df_merge["Δ Hộ"]  = (df_merge["so_ho_ht"] - df_merge["so_ho_bl"]).astype(int)

            df_out = pd.DataFrame()
            df_out["Tên PGD"]              = df_merge[COT_TEN_PGD]
            df_out[f"DN mốc {label_bl}"]   = df_merge["tong_du_no_bl"].apply(fmt_ty)
            df_out["DN hiện tại"]          = df_merge["tong_du_no_ht"].apply(fmt_ty)
            df_out["±DN"]                  = df_merge["Δ Dư nợ"].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
            )
            df_out["±DN%"] = df_merge["Δ DN %"].apply(
                lambda x: ("+" if x >= 0 else "") + f"{x:.2f}".replace(".", ",") + "%"
            )
            df_out[f"Hộ mốc {label_bl}"]   = df_merge["so_ho_bl"].apply(lambda x: fmt_so(int(x)))
            df_out["Hộ HT"]               = df_merge["so_ho_ht"].apply(lambda x: fmt_so(int(x)))
            df_out["±Hộ"]                  = df_merge["Δ Hộ"].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_so(x)
            )
            df_out["NQH mốc"]  = df_merge["NQH mốc"].apply(_fmt_pct_vn)
            df_out["NQH HT"]   = df_merge["NQH HT"].apply(_fmt_pct_vn)
            df_out["±NQH"] = df_merge["Δ NQH"].apply(
                lambda x: ("+" if x >= 0 else "") + _fmt_pct_vn(abs(x)).replace("%", "") + "%"
            )

            st.dataframe(df_out, hide_index=True, use_container_width=True, height=520)

        # ═══════════ KPI THEO HỘI ĐOÀN THỂ (ĐVUT) ══════════════════════════
        st.divider()
        with st.expander("🏛️ So sánh theo Hội đoàn thể (ĐVUT)", expanded=False):
            df_dvut_ht = _agg_theo_dvut(df_ht)
            df_dvut_bl = _agg_theo_dvut(df_bl)

            if df_dvut_ht.empty or df_dvut_bl.empty:
                st.info("Không có cột Tên ĐVUT trong dữ liệu.")
            else:
                df_dvut = df_dvut_ht.merge(
                    df_dvut_bl, on=COT_DVUT, how="outer",
                    suffixes=("_ht", "_bl"),
                ).fillna(0)

                no_xau_dvut_ht = df_dvut["du_no_qh_ht"] + df_dvut.get("du_no_khoanh_ht", pd.Series(0, index=df_dvut.index)).fillna(0)
                no_xau_dvut_bl = df_dvut["du_no_qh_bl"] + df_dvut.get("du_no_khoanh_bl", pd.Series(0, index=df_dvut.index)).fillna(0)

                df_out = pd.DataFrame()
                df_out["Hội đoàn thể"]      = df_dvut[COT_DVUT]
                df_out[f"DN mốc {label_bl}"] = df_dvut["tong_du_no_bl"].apply(fmt_ty)
                df_out["DN hiện tại"]        = df_dvut["tong_du_no_ht"].apply(fmt_ty)
                df_out["±DN"] = (df_dvut["tong_du_no_ht"] - df_dvut["tong_du_no_bl"]).apply(
                    lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
                )
                df_out["±DN%"] = df_dvut.apply(
                    lambda r: ("+" if r["tong_du_no_ht"] >= r["tong_du_no_bl"] else "")
                    + f"{(r['tong_du_no_ht'] - r['tong_du_no_bl']) / r['tong_du_no_bl'] * 100:.2f}".replace(".", ",") + "%"
                    if r["tong_du_no_bl"] != 0 else "—", axis=1,
                )
                df_out["Hộ mốc"]   = df_dvut["so_ho_bl"].apply(lambda x: fmt_so(int(x)))
                df_out["Hộ HT"]    = df_dvut["so_ho_ht"].apply(lambda x: fmt_so(int(x)))
                df_out["±Hộ"] = (df_dvut["so_ho_ht"] - df_dvut["so_ho_bl"]).apply(
                    lambda x: ("+" if x >= 0 else "") + fmt_so(int(x))
                )
                df_out["NQH mốc"]  = df_dvut.apply(
                    lambda r: _fmt_pct_vn(_tl_nqh(r["du_no_qh_bl"], r["tong_du_no_bl"])), axis=1
                )
                df_out["NQH HT"]   = df_dvut.apply(
                    lambda r: _fmt_pct_vn(_tl_nqh(r["du_no_qh_ht"], r["tong_du_no_ht"])), axis=1
                )
                df_out["Nợ xấu HT"]    = no_xau_dvut_ht.apply(fmt_ty)
                df_out["TL Nợ xấu HT"] = df_dvut.apply(
                    lambda r: _fmt_pct_vn(
                        _tl_nqh(r["du_no_qh_ht"] + r.get("du_no_khoanh_ht", 0), r["tong_du_no_ht"])
                    ), axis=1
                )

                st.dataframe(df_out, hide_index=True, use_container_width=True, height=480)

        # ═══════════ MA TRẬN CHUYỂN NHÓM NỢ ═════════════════════════════════
        st.divider()
        with st.expander("📊 Ma trận chuyển nhóm nợ", expanded=False):
            kys = danh_sach_ky()
            if len(kys) >= 2:
                ky_map = {k: k for k in kys}
                ky_truoc = st.selectbox(
                    "Kỳ trước",
                    kys[1:],
                    key=f"{key_prefix}mm_ky_truoc",
                    format_func=lambda x: ky_map.get(x, x),
                )
                ky_sau = st.selectbox(
                    "Kỳ sau",
                    kys,
                    key=f"{key_prefix}mm_ky_sau",
                    format_func=lambda x: ky_map.get(x, x),
                )

                if ky_truoc and ky_sau and ky_truoc != ky_sau:
                    matrix, chi_tiet = _ma_tran_chuyen_nhuong(ky_truoc, ky_sau)
                    if not matrix.empty:
                        st.subheader(f"Ma trận: {ky_truoc} → {ky_sau}")
                        st.dataframe(matrix, use_container_width=True)

                        if not chi_tiet.empty:
                            with st.expander(
                                f"📋 Chi tiết ({len(chi_tiet)} khoản)",
                                expanded=False,
                            ):
                                st.dataframe(
                                    chi_tiet,
                                    hide_index=True,
                                    use_container_width=True,
                                    height=400,
                                )
                    else:
                        st.info("Không đủ dữ liệu snapshot để so sánh.")
            else:
                st.info("Cần ít nhất 2 kỳ để hiển thị ma trận chuyển nhóm nợ.")

        # ═══════════ PHÂN LOẠI KHÁCH HÀNG ═════════════════════════════════
        st.divider()
        with st.expander("👥 Phân loại khách hàng", expanded=False):
            st.markdown("**Phân tích thay đổi nhóm khách hàng giữa hai kỳ:**")
            df_lifecycle = _phan_loai_khach_hang(df_bl, df_ht)
            if not df_lifecycle.empty:
                st.dataframe(df_lifecycle, hide_index=True, use_container_width=True)
            else:
                st.info("Không đủ dữ liệu khách hàng để phân loại.")

        # ═══════════ PHÂN TÍCH PAR ═════════════════════════════════════════
        st.divider()
        with st.expander("🎯 Phân tích PAR (Portfolio at Risk)", expanded=False):
            st.markdown(
                "**PAR30/PAR90/PAR180** — tỷ lệ dư nợ có ngày đáo hạn > 30/90/180 ngày"
            )
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Mốc {label_bl}**")
                _bang_par(df_bl, f"Mốc {label_bl}")
            with c2:
                st.markdown("**Hiện tại**")
                _bang_par(df_ht, "Hiện tại")

        # ═══════════ PHÂN TÍCH HHI ═════════════════════════════════════════
        st.divider()
        with st.expander(
            "🎲 Phân tích tập trung rủi ro (HHI Index)", expanded=False
        ):
            st.markdown(
                "**Herfindahl-Hirschman Index (HHI)** — đo lường nồng độ rủi ro theo PGD"
            )
            c1, c2 = st.columns(2)

            with c1:
                st.subheader("Mốc 31/12")
                hhi_bl, bd_bl, muc_bl, icon_bl, mau_bl = _phan_tich_hhi_pgd(df_bl)
                col1, col2 = st.columns(2)
                col1.metric(
                    "HHI Score",
                    f"{hhi_bl * 10000:.0f}",
                    help="Thang 0–10000. Cao = rủi ro tập trung.",
                )
                col2.markdown(f"### {icon_bl} {muc_bl}")
                if not bd_bl.empty:
                    st.dataframe(
                        bd_bl[["du_no", "ty_trong_pct", "dong_gop_hhi"]],
                        hide_index=True,
                        use_container_width=True,
                        height=250,
                    )

            with c2:
                st.subheader("Hiện tại")
                hhi_ht, bd_ht, muc_ht, icon_ht, mau_ht = _phan_tich_hhi_pgd(df_ht)
                col1, col2 = st.columns(2)
                col1.metric(
                    "HHI Score",
                    f"{hhi_ht * 10000:.0f}",
                    help="Thang 0–10000. Cao = rủi ro tập trung.",
                )
                col2.markdown(f"### {icon_ht} {muc_ht}")
                if not bd_ht.empty:
                    st.dataframe(
                        bd_ht[["du_no", "ty_trong_pct", "dong_gop_hhi"]],
                        hide_index=True,
                        use_container_width=True,
                        height=250,
                    )

        # ═══════════ TOP BIẾN ĐỘNG (VSPPRO PeriodMovers) ═════════════════
        st.divider()
        with st.expander(
            "🚀 Top biến động — so sánh tăng/giảm theo chiều và chỉ tiêu",
            expanded=False,
        ):
            _render_top_bien_dong(df_bl, df_ht, label_bl, label_ht, key_prefix)

        # ═══════════ RADAR & RANKING (VSPPRO Compare) ════════════════════
        st.divider()
        with st.expander(
            "🕸️ Radar & Ranking — so sánh đa chiều PGD",
            expanded=False,
        ):
            _render_radar_ranking(df_ht, key_prefix)

        # ═══════════ BIẾN ĐỘNG KHẾƯỚC (EXPLORER) ════════════════════════
        st.divider()
        with st.expander("🔍 Biến động khế ước chi tiết", expanded=False):
            st.markdown(
                "Phân loại **8 loại biến động** cấp độ khế ước giữa mốc và hiện tại. "
                "Sắp xếp theo |Δ dư nợ| giảm dần."
            )
            _bang_explorer(df_joined, chon_nam, key_prefix)

        # ═══════════ ROLL RATE / CURE RATE (từ join trực tiếp) ══════════
        st.divider()
        with st.expander("📊 Roll rate / Cure rate", expanded=False):
            rc = roll_cure_rate(df_joined)
            st.markdown(
                "**Roll rate** = tỷ lệ dư nợ Trong hạn ở kỳ trước chuyển sang Quá hạn kỳ này.  \n"
                "**Cure rate** = tỷ lệ dư nợ Quá hạn ở kỳ trước phục hồi về Trong hạn kỳ này."
            )
            r1, r2 = st.columns(2)
            r1.metric(
                "Roll rate",
                _fmt_pct_vn(rc["roll_rate"] * 100),
                help=f"DN TH kỳ trước: {fmt_ty(rc['base_th_prev'])} | Số KƯ roll: {fmt_so(rc['roll_count'])}",
                delta_color="inverse",
            )
            r2.metric(
                "Cure rate",
                _fmt_pct_vn(rc["cure_rate"] * 100),
                help=f"DN QH kỳ trước: {fmt_ty(rc['base_qh_prev'])} | Số KƯ cure: {fmt_so(rc['cure_count'])}",
            )

        # ═══════════ VINTAGE NQH ════════════════════════════════════════
        st.divider()
        with st.expander("📅 Vintage NQH (theo năm vay)", expanded=False):
            st.markdown(
                "Tỷ lệ NQH phân tích theo **năm phát sinh khoản vay** — "
                "cho thấy nhóm vintage nào có rủi ro cao nhất."
            )
            _bang_vintage_nqh(df_ht, df_bl, chon_nam)
