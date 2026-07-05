"""So sánh mốc 31/12 — hỗ trợ nhiều loại dữ liệu: HSTD, NQ11, GQVL, CDTOTKVV.

Cấu trúc:
  1. Chọn loại dữ liệu (tabs)
  2. Chọn năm baseline
  3. Render phân tích tương ứng

Improvements:
  - Modular: mỗi loại dữ liệu = 1 hàm riêng
  - Shared components từ _common.py
  - Consistent UI với render_2_ky.py
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_KHOANH, COT_DU_NO_QH, COT_DU_NO_TH,
    COT_DVUT, COT_MA_KH, COT_NGAY_SL,
    COT_SO_KU, COT_TEN_CT, COT_TEN_PGD,
    COT_TEN_XA, COT_TONG_DU_NO,
    danh_sach_nam_baseline, danh_sach_nam_baseline_pgd,
)
from data.hstd import doc_baseline_merged, ts_baseline_merged
from data.pgd import pgd_slug
from snapshot_service import (
    doc_nq11_snapshot, danh_sach_ky_nq11, luu_nq11_snapshot,
    doc_gqvl_snapshot, danh_sach_ky_gqvl,
    doc_cdtotkvv_snapshot, danh_sach_ky_cdtotkvv,
)
from services.so_sanh_ky_service import (
    agg_mot_pgd as _agg_mot_pgd,
    agg_theo_pgd as _agg_theo_pgd,
    group_bien_dong as _group_bien_dong,
    tl_nqh as _tl_nqh,
    fmt_pct_vn as _fmt_pct_vn,
)
from services.period_compare import join_by_loan
from tabs.tab_so_sanh_ky._common import (
    delta_str, pct_change_str, fmt_pct_vn, tl_nqh,
    render_kpi_row, render_quality_bars_2_ky,
    render_comparison_table, render_hbar_chart, render_flow_diagram,
)
from tabs.tab_so_sanh_ky._kpi_cards import (
    render_big_metric_card,
    render_mini_cards_row,
    render_debt_structure_donut,
    render_compact_comparison_table,
    render_dashboard_header,
)
from tabs.tab_so_sanh_ky._export import render_export_ui, render_export_hstd_ui
from utils import fmt_ty, fmt_so, vn
import db


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS & HELPERS
# ═══════════════════════════════════════════════════════════════════════════

_DIM_BIEN_DONG = [
    (COT_TEN_PGD, "PGD"),
    (COT_TEN_XA,  "Xã"),
    (COT_TEN_CT,  "Chương trình"),
    (COT_DVUT,    "Hội đoàn thể"),
]

_METRIC_OPTS = {
    "du_no":   "Tổng dư nợ",
    "nqh_pct": "Tỷ lệ NQH%",
    "so_ku":   "Số khế ước",
}

# Data source options: key -> (icon_label, description)
_DATA_SOURCES = {
    "hstd":     ("📊 HSTD",     "Hồ sơ tín dụng"),
    "nq11":     ("⚖️ NQ11",     "Nghị quyết 11"),
    "gqvl":     ("💼 GQVL",     "Giải quyết việc làm"),
    "cdtotkvv": ("⭐ CDTOTKVV", "Chấm điểm tổ"),
}


def _get_ds_nam_baseline() -> list[int]:
    """Lấy danh sách năm baseline từ file hoặc config."""
    ds_nam = []
    from config import BASELINE_PGD_DIR
    if BASELINE_PGD_DIR.exists():
        years = set()
        for f in BASELINE_PGD_DIR.rglob("HSTD_3112_*.XLSX"):
            try:
                years.add(int(f.stem.split("_")[-1]))
            except ValueError:
                continue
        ds_nam = sorted(years, reverse=True)
    if not ds_nam:
        ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()
    return ds_nam


def _snap(agg: dict) -> dict:
    """Tính toán cấu trúc dư nợ từ aggregate."""
    total = agg["tong_du_no"]
    th = agg.get("du_no_th", 0)
    qh = agg.get("du_no_qh", 0)
    kh = agg.get("du_no_khoanh", 0)
    if th == 0 and total > 0:
        th = max(0.0, total - qh - kh)
    return {"trong_han": th, "qua_han": qh, "khoanh": kh, "total": total}


def _ds(v: float, b: float) -> str:
    """Delta string helper."""
    return delta_str(v - b, "tien")


def _render_nq11_manual_snap(df_nq11: "pd.DataFrame", key_prefix: str) -> None:
    """Widget tạo snapshot NQ11 thủ công cho admin — dùng khi thiếu snapshot tháng 12."""
    with st.expander("🔧 Tạo snapshot NQ11 tháng 12 (Admin)", expanded=True):
        st.caption("Tạo snapshot từ dữ liệu NQ11 hiện đang tải, với kỳ do bạn chỉ định.")
        username = st.session_state.get("username", "unknown")
        c1, c2 = st.columns([2, 1])
        with c1:
            ky_input = st.text_input(
                "Kỳ snapshot (YYYY-MM)",
                value="2024-12",
                placeholder="Ví dụ: 2024-12",
                key=f"{key_prefix}nq11_manual_ky",
            )
        with c2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            btn = st.button("✅ Tạo snapshot", key=f"{key_prefix}nq11_manual_btn", type="primary")

        if btn:
            import re
            if not re.fullmatch(r"\d{4}-\d{2}", ky_input.strip()):
                st.error("❌ Kỳ không đúng định dạng YYYY-MM (vd: 2024-12).")
            else:
                result = luu_nq11_snapshot(df_nq11, username, ky=ky_input.strip())
                result.hien_thi()
                if result.thanh_cong:
                    st.cache_data.clear()
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# SHARED UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════

def _render_top_bien_dong(
    df_bl: pd.DataFrame,
    df_ht: pd.DataFrame,
    label_bl: str,
    label_ht: str,
    key_prefix: str,
) -> None:
    """Top N tăng/giảm theo chiều và chỉ tiêu."""
    import plotly.graph_objects as go
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
        st.info("Không đủ dữ liệu.")
        return

    g_ht = _group_bien_dong(df_ht, dim_sel)
    g_bl = _group_bien_dong(df_bl, dim_sel)
    merged = g_ht.merge(g_bl, on=dim_sel, how="outer", suffixes=("_ht", "_bl")).fillna(0)
    for _mc in (f"{metric_sel}_ht", f"{metric_sel}_bl"):
        if _mc in merged.columns:
            merged[_mc] = pd.to_numeric(merged[_mc], errors="coerce").fillna(0)
    merged["delta"] = merged[f"{metric_sel}_ht"] - merged[f"{metric_sel}_bl"]
    merged = merged[merged[dim_sel].astype(str).str.strip() != ""]

    top_tang = merged.nlargest(n, "delta")
    top_giam = merged.nsmallest(n, "delta")

    def _label_val(val: float) -> str:
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
            text=df_top["delta"].apply(_label_val),
            textposition="outside",
        ))
        fig.update_layout(
            height=max(220, n * 38 + 60),
            margin=dict(t=10, b=20, l=10, r=80),
            xaxis_title=_METRIC_OPTS[metric_sel],
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True, key=key)

    col_tang, col_giam = st.columns(2)
    with col_tang:
        st.markdown(f"**📈 Top {n} tăng mạnh — {_METRIC_OPTS[metric_sel]}**")
        _make_bar(top_tang.sort_values("delta", ascending=True), "#2e7d32",
                  f"{key_prefix}tbdong_tang")
    with col_giam:
        st.markdown(f"**📉 Top {n} giảm mạnh — {_METRIC_OPTS[metric_sel]}**")
        _make_bar(top_giam.sort_values("delta", ascending=False), "#c62828",
                  f"{key_prefix}tbdong_giam")


def _render_export_section(
    rows_data: list[tuple],
    label_bl: str,
    label_ht: str,
    username: str,
    sheets_extra: dict[str, pd.DataFrame] | None = None,
    key_prefix: str = "moc",
    df_ht: pd.DataFrame | None = None,
    df_bl: pd.DataFrame | None = None,
) -> None:
    """Section xuất báo cáo. Nếu có df_ht/df_bl → dùng giao diện HSTD 3 loại PDF."""
    if df_ht is not None and df_bl is not None:
        render_export_hstd_ui(
            df_ht, df_bl, label_ht, label_bl,
            rows_data, username, sheets_extra,
            action="xuat_bieu_cn", key_prefix=key_prefix,
        )
    else:
        st.markdown("**📤 XUẤT BÁO CÁO**")
        render_export_ui(rows_data, label_bl, label_ht, username, sheets_extra,
                         action="xuat_bieu_cn", key_prefix=key_prefix)


# ═══════════════════════════════════════════════════════════════════════════
# DATA SOURCE RENDERERS
# ═══════════════════════════════════════════════════════════════════════════

def _render_hstd_section(
    df_full: pd.DataFrame,
    df: pd.DataFrame,
    role: str,
    pgd_user: str | None,
    pgd_mode: bool,
    key_prefix: str,
) -> None:
    """Render section cho HSTD baseline comparison."""
    ds_nam = _get_ds_nam_baseline()
    if not ds_nam:
        st.warning("⚠️ Chưa có dữ liệu năm trước. Upload baseline trong tab Hệ thống.")
        return

    chon_nam = st.selectbox("So sánh với mốc 31/12 năm", ds_nam, key=f"{key_prefix}ssk_nam")

    df_bl_full = doc_baseline_merged(chon_nam, ts=ts_baseline_merged(chon_nam))
    if df_bl_full is None or df_bl_full.empty:
        st.warning(f"⚠️ Chưa có dữ liệu baseline 31/12/{chon_nam}.")
        return

    if pgd_mode and pgd_user:
        if COT_TEN_PGD in df_bl_full.columns:
            df_bl = df_bl_full[df_bl_full[COT_TEN_PGD] == pgd_user].copy()
            if df_bl.empty:
                st.warning(f"⚠️ Baseline 31/12/{chon_nam} không có dữ liệu cho **{pgd_user}**.")
                return
        else:
            st.warning(
                f"⚠️ File baseline 31/12/{chon_nam} không có cột '{COT_TEN_PGD}' — "
                "không thể lọc theo PGD. Đang hiển thị toàn Chi nhánh làm mốc."
            )
            df_bl = df_bl_full.copy()
    else:
        df_bl = df_bl_full.copy()

    df_ht = df if pgd_mode else df_full
    if df_ht is None or df_ht.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD hiện tại.")
        return

    agg_ht = _agg_mot_pgd(df_ht)
    agg_bl = _agg_mot_pgd(df_bl)

    ngay_sl = ""
    if COT_NGAY_SL in df_ht.columns:
        sl = df_ht[COT_NGAY_SL].dropna()
        if len(sl):
            ngay_sl = str(sl.iloc[0])
    label_bl = f"31/12/{chon_nam}"
    label_ht = ngay_sl or "Hiện tại"

    # ═══════════════════════════════════════════════════════════════════════
    # 📊 DASHBOARD TỔNG QUAN MỚI
    # ═══════════════════════════════════════════════════════════════════════
    render_dashboard_header(label_ht, label_bl, key_prefix)

    # ── Tính toán các chỉ tiêu ──
    tl_nqh_ht = _tl_nqh(agg_ht["du_no_qh"], agg_ht["tong_du_no"])
    tl_nqh_bl = _tl_nqh(agg_bl["du_no_qh"], agg_bl["tong_du_no"])
    tl_kh_ht  = _tl_nqh(agg_ht["du_no_khoanh"], agg_ht["tong_du_no"])
    tl_kh_bl  = _tl_nqh(agg_bl["du_no_khoanh"], agg_bl["tong_du_no"])
    no_xau_ht = agg_ht["du_no_qh"] + agg_ht["du_no_khoanh"]
    no_xau_bl = agg_bl["du_no_qh"] + agg_bl["du_no_khoanh"]
    tl_nx_ht  = _tl_nqh(no_xau_ht, agg_ht["tong_du_no"])
    tl_nx_bl  = _tl_nqh(no_xau_bl, agg_bl["tong_du_no"])
    muc_vay_ht = agg_ht["tong_du_no"] / agg_ht["so_ho"] if agg_ht["so_ho"] > 0 else 0
    muc_vay_bl = agg_bl["tong_du_no"] / agg_bl["so_ho"] if agg_bl["so_ho"] > 0 else 0

    # ── ROW 1: Big Cards (Tổng dư nợ + Nợ xấu) ──
    col1, col2 = st.columns(2)
    
    with col1:
        # Card Tổng dư nợ - luôn xanh (tăng là tốt)
        delta_dn_pct = ((agg_ht["tong_du_no"] - agg_bl["tong_du_no"]) / agg_bl["tong_du_no"] * 100) if agg_bl["tong_du_no"] else 0
        progress_dn = (agg_ht["tong_du_no"] / agg_bl["tong_du_no"] * 100) if agg_bl["tong_du_no"] else 100
        
        render_big_metric_card(
            icon="💰",
            label="Tổng dư nợ",
            value=vn(agg_ht["tong_du_no"] / 1e9, 3) + " tỷ",
            delta_pct=delta_dn_pct,
            delta_value=agg_ht["tong_du_no"] - agg_bl["tong_du_no"],
            baseline_value=agg_bl["tong_du_no"],
            progress_pct=progress_dn,
            is_inverse=False,
            color_scheme="blue" if delta_dn_pct >= 0 else "red",
            key=f"{key_prefix}big_dn",
        )

    with col2:
        # Card Nợ xấu - đỏ nếu tăng, xanh nếu giảm
        delta_nx_pct = ((no_xau_ht - no_xau_bl) / no_xau_bl * 100) if no_xau_bl else 0
        progress_nx = (no_xau_ht / no_xau_bl * 100) if no_xau_bl else 100

        render_big_metric_card(
            icon="⚠️",
            label="Nợ xấu QH + Khoanh",
            value=vn(no_xau_ht / 1e9, 3) + " tỷ",
            delta_pct=delta_nx_pct,
            delta_value=no_xau_ht - no_xau_bl,
            baseline_value=no_xau_bl,
            progress_pct=progress_nx,
            is_inverse=True,  # Tăng là xấu
            color_scheme="green" if delta_nx_pct <= 0 else "red",
            key=f"{key_prefix}big_nx",
        )
    
    # Badge tỷ lệ nợ xấu
    col_badge1, col_badge2, _ = st.columns([1, 1, 2])
    with col_badge1:
        st.markdown(f"<div style='text-align:center;padding:8px;background:var(--surface-lo,#f0fdf4);border-radius:8px;color:var(--green,#166534);font-weight:600;'>📉 Tỷ lệ nợ xấu: <b>{fmt_pct_vn(tl_nx_ht)}</b> (mốc: {fmt_pct_vn(tl_nx_bl)})</div>", unsafe_allow_html=True)
    with col_badge2:
        st.markdown(f"<div style='text-align:center;padding:8px;background:var(--surface-lo,#fefce8);border-radius:8px;color:var(--text-sub,#854d0e);font-weight:600;'>📊 Tỷ lệ NQH: <b>{fmt_pct_vn(tl_nqh_ht)}</b> (mốc: {fmt_pct_vn(tl_nqh_bl)})</div>", unsafe_allow_html=True)
    
    st.markdown("")  # Spacing
    
    # ── ROW 2: Mini Cards ──
    mini_cards = [
        {
            "icon": "👥",
            "label": "Số hộ vay",
            "value": fmt_so(agg_ht["so_ho"]),
            "delta": agg_ht["so_ho"] - agg_bl["so_ho"],
            "unit": "so",
            "color": "#3b82f6",  # blue
        },
        {
            "icon": "📋",
            "label": "Số khế ước",
            "value": fmt_so(agg_ht["so_ku"]),
            "delta": agg_ht["so_ku"] - agg_bl["so_ku"],
            "unit": "so",
            "color": "#8b5cf6",  # purple
        },
        {
            "icon": "💹",
            "label": "Tổng lãi tồn",
            "value": vn(agg_ht["tong_lai_ton"] / 1e9, 3) + " tỷ",
            "delta": agg_ht["tong_lai_ton"] - agg_bl["tong_lai_ton"],
            "unit": "ty",
            "color": "#eab308",
        },
        {
            "icon": "📈",
            "label": "Giải ngân năm",
            "value": vn(agg_ht["gn_nam"] / 1e9, 3) + " tỷ",
            "delta": agg_ht["gn_nam"] - agg_bl["gn_nam"],
            "unit": "ty",
            "color": "#22c55e",
        },
    ]
    render_mini_cards_row(mini_cards, key_prefix=f"{key_prefix}mini")
    
    st.markdown("")  # Spacing
    st.divider()
    
    # ── ROW 3: Donut Chart + Comparison Table ──
    st.markdown("**📊 Cấu trúc dư nợ & So sánh chi tiết**")
    
    col_chart, col_table = st.columns([1, 1])
    
    with col_chart:
        render_debt_structure_donut(
            trong_han=agg_ht["du_no_th"],
            qua_han=agg_ht["du_no_qh"],
            khoanh=agg_ht["du_no_khoanh"],
            title=f"Cấu trúc dư nợ - {label_ht}",
            key=f"{key_prefix}donut",
        )
    
    with col_table:
        # Prepare comparison rows
        comp_rows = [
            {"label": "Tổng dư nợ", "value_bl": agg_bl["tong_du_no"], "value_ht": agg_ht["tong_du_no"], "is_risk": False, "unit": "tien"},
            {"label": "Dư nợ trong hạn", "value_bl": agg_bl["du_no_th"], "value_ht": agg_ht["du_no_th"], "is_risk": False, "unit": "tien"},
            {"label": "Dư nợ quá hạn", "value_bl": agg_bl["du_no_qh"], "value_ht": agg_ht["du_no_qh"], "is_risk": True, "unit": "tien"},
            {"label": "Dư nợ khoanh", "value_bl": agg_bl["du_no_khoanh"], "value_ht": agg_ht["du_no_khoanh"], "is_risk": True, "unit": "tien"},
            {"label": "Tỷ lệ NQH (%)", "value_bl": tl_nqh_bl, "value_ht": tl_nqh_ht, "is_risk": True, "unit": "pct"},
            {"label": "Mức vay BQ/KH", "value_bl": muc_vay_bl, "value_ht": muc_vay_ht, "is_risk": False, "unit": "tien"},
        ]
        render_compact_comparison_table(
            rows=comp_rows,
            label_bl=label_bl,
            label_ht=label_ht,
            key=f"{key_prefix}comptable",
        )
    
    st.divider()

    # ── SECTION 2: Multi-dimension tabs ───────────────────────────────────
    st.markdown("**📋 PHÂN TÍCH ĐA CHIỀU**")

    tab_labels = ["🏢 Theo PGD", "📋 Theo CT", "📍 Theo Xã", "📈 Top biến động", "🔄 Vòng đời"]
    tab_panes = st.tabs(tab_labels)

    # Tab 1: Theo PGD
    with tab_panes[0]:
        if la_phan_he_cn(role) and not pgd_mode:
            df_pgd_ht = _agg_theo_pgd(df_full)
            df_pgd_bl = _agg_theo_pgd(df_bl_full)
            if df_pgd_ht.empty or df_pgd_bl.empty:
                st.info("Không đủ dữ liệu PGD.")
            else:
                df_merge = df_pgd_ht.merge(
                    df_pgd_bl, on=COT_TEN_PGD, how="outer",
                    suffixes=("_ht", "_bl"),
                ).fillna(0)
                for col in ["tong_du_no_ht", "tong_du_no_bl", "du_no_qh_ht", "du_no_qh_bl"]:
                    if col in df_merge.columns:
                        df_merge[col] = pd.to_numeric(df_merge[col], errors="coerce").fillna(0)
                df_merge["Δ DN"] = df_merge["tong_du_no_ht"] - df_merge["tong_du_no_bl"]
                df_merge["Δ DN%"] = df_merge.apply(
                    lambda r: (r["Δ DN"] / r["tong_du_no_bl"] * 100) if r["tong_du_no_bl"] != 0 else 0.0,
                    axis=1,
                )
                df_merge["NQH mốc"] = df_merge.apply(
                    lambda r: _tl_nqh(r["du_no_qh_bl"], r["tong_du_no_bl"]), axis=1
                )
                df_merge["NQH HT"] = df_merge.apply(
                    lambda r: _tl_nqh(r["du_no_qh_ht"], r["tong_du_no_ht"]), axis=1
                )
                df_merge["Δ NQH"] = df_merge["NQH HT"] - df_merge["NQH mốc"]

                df_out = pd.DataFrame()
                df_out["Tên PGD"] = df_merge[COT_TEN_PGD]
                df_out["DN mốc"]   = df_merge["tong_du_no_bl"].apply(fmt_ty)
                df_out["DN HT"]     = df_merge["tong_du_no_ht"].apply(fmt_ty)
                df_out["±DN"] = df_merge["Δ DN"].apply(
                    lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
                )
                df_out["±DN%"] = df_merge["Δ DN%"].apply(
                    lambda x: ("+" if x >= 0 else "") + f"{x:.2f}".replace(".", ",") + "%"
                )
                df_out["NQH mốc"] = df_merge["NQH mốc"].apply(_fmt_pct_vn)
                df_out["NQH HT"]  = df_merge["NQH HT"].apply(_fmt_pct_vn)
                df_out["±NQH"] = df_merge["Δ NQH"].apply(
                    lambda x: ("+" if x >= 0 else "") + _fmt_pct_vn(abs(x)).replace("%", "") + "%"
                )
                st.dataframe(df_out, hide_index=True, use_container_width=True, height=400)

                # Bar chart
                sorted_df = df_merge[~df_merge[COT_TEN_PGD].str.startswith("⬛", na=False)] \
                    .sort_values("Δ DN")
                render_hbar_chart(
                    labels=sorted_df[COT_TEN_PGD].astype(str).tolist(),
                    values=sorted_df["Δ DN"].tolist(),
                    title=f"Biến động dư nợ: {label_bl} → {label_ht}",
                    key=f"{key_prefix}hbar_pgd",
                )
        else:
            st.info("ℹ️ Dữ liệu PGD chỉ hiển thị ở phân hệ Chi nhánh.")

    # Tab 2: Theo Chương trình
    with tab_panes[1]:
        g_ht = _group_bien_dong(df_ht, COT_TEN_CT)
        g_bl = _group_bien_dong(df_bl, COT_TEN_CT)
        if not g_ht.empty and not g_bl.empty:
            merged = g_ht.merge(g_bl, on=COT_TEN_CT, how="outer",
                                suffixes=("_ht", "_bl")).fillna(0)
            for col in ["du_no_ht", "du_no_bl", "du_no_qh_ht", "du_no_qh_bl"]:
                if col in merged.columns:
                    merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
            merged["Δ DN"] = merged["du_no_ht"] - merged["du_no_bl"]
            merged = merged.sort_values("Δ DN", ascending=False)
            df_out = pd.DataFrame()
            df_out["Chương trình"] = merged[COT_TEN_CT].astype(str)
            df_out["DN mốc"] = merged["du_no_bl"].apply(fmt_ty)
            df_out["DN HT"]   = merged["du_no_ht"].apply(fmt_ty)
            df_out["±DN"] = merged["Δ DN"].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
            )
            df_out["NQH mốc"] = merged["nqh_pct_bl"].apply(_fmt_pct_vn)
            df_out["NQH HT"]  = merged["nqh_pct_ht"].apply(_fmt_pct_vn)
            st.dataframe(df_out, hide_index=True, use_container_width=True, height=320)
        else:
            st.info("Không có dữ liệu chương trình.")

    # Tab 3: Theo Xã
    with tab_panes[2]:
        g_ht = _group_bien_dong(df_ht, COT_TEN_XA)
        g_bl = _group_bien_dong(df_bl, COT_TEN_XA)
        if not g_ht.empty and not g_bl.empty:
            merged = g_ht.merge(g_bl, on=COT_TEN_XA, how="outer",
                                suffixes=("_ht", "_bl")).fillna(0)
            for col in ["du_no_ht", "du_no_bl", "du_no_qh_ht", "du_no_qh_bl"]:
                if col in merged.columns:
                    merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
            merged["Δ DN"] = merged["du_no_ht"] - merged["du_no_bl"]
            merged = merged.sort_values("Δ DN", ascending=False)
            df_out = pd.DataFrame()
            df_out["Xã"] = merged[COT_TEN_XA].astype(str)
            df_out["DN mốc"] = merged["du_no_bl"].apply(fmt_ty)
            df_out["DN HT"]  = merged["du_no_ht"].apply(fmt_ty)
            df_out["±DN"] = merged["Δ DN"].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
            )
            df_out["NQH mốc"] = merged["nqh_pct_bl"].apply(_fmt_pct_vn)
            df_out["NQH HT"]  = merged["nqh_pct_ht"].apply(_fmt_pct_vn)
            st.dataframe(df_out, hide_index=True, use_container_width=True, height=400)
        else:
            st.info("Không có dữ liệu xã.")

    # Tab 4: Top biến động
    with tab_panes[3]:
        _render_top_bien_dong(df_bl, df_ht, label_bl, label_ht, key_prefix)

    # Tab 5: Vòng đời
    with tab_panes[4]:
        df_joined = join_by_loan(df_bl, df_ht)
        prev_total_loans = agg_bl["so_ku"]
        curr_total_loans = agg_ht["so_ku"]
        prev_col = COT_SO_KU + "_prev"
        curr_col = COT_SO_KU + "_curr"
        if (not df_joined.empty and prev_col in df_joined.columns
                and curr_col in df_joined.columns):
            retained_loans = int(df_joined[[prev_col, curr_col]].notna().all(axis=1).sum())
        else:
            retained_loans = min(prev_total_loans, curr_total_loans)
        closed_loans = max(0, prev_total_loans - retained_loans)
        new_loans    = max(0, curr_total_loans - retained_loans)

        ma_kh_bl = set(df_bl[COT_MA_KH].astype(str).str.strip()) if COT_MA_KH in df_bl.columns else set()
        ma_kh_ht = set(df_ht[COT_MA_KH].astype(str).str.strip()) if COT_MA_KH in df_ht.columns else set()
        prev_total_cust = len(ma_kh_bl)
        curr_total_cust = len(ma_kh_ht)
        retained_cust   = len(ma_kh_bl & ma_kh_ht)
        churned_cust    = len(ma_kh_bl - ma_kh_ht)
        new_cust        = len(ma_kh_ht - ma_kh_bl)

        lc1, lc2 = st.columns(2)
        with lc1:
            st.markdown("**Khế ước**")
            render_flow_diagram(
                prev_label=f"KƯ {label_bl}", curr_label=f"KƯ {label_ht}",
                prev_total=prev_total_loans, curr_total=curr_total_loans,
                retained=retained_loans, churned=closed_loans, new_cust=new_loans,
            )
        with lc2:
            st.markdown("**Khách hàng**")
            render_flow_diagram(
                prev_label=f"KH {label_bl}", curr_label=f"KH {label_ht}",
                prev_total=prev_total_cust, curr_total=curr_total_cust,
                retained=retained_cust, churned=churned_cust, new_cust=new_cust,
            )

    st.divider()

    # ── SECTION 3: Export ─────────────────────────────────────────────────
    _nx_bl = agg_bl["du_no_qh"] + agg_bl["du_no_khoanh"]
    _nx_ht = agg_ht["du_no_qh"] + agg_ht["du_no_khoanh"]
    rows_data = [
        ("Tổng dư nợ (triệu đồng)",      fmt_ty(agg_bl["tong_du_no"]),   fmt_ty(agg_ht["tong_du_no"]),
         delta_str(agg_ht["tong_du_no"] - agg_bl["tong_du_no"], "tien"),
         pct_change_str(agg_bl["tong_du_no"], agg_ht["tong_du_no"])),
        ("Dư nợ trong hạn (triệu đồng)", fmt_ty(agg_bl["du_no_th"]),     fmt_ty(agg_ht["du_no_th"]),
         delta_str(agg_ht["du_no_th"] - agg_bl["du_no_th"], "tien"),
         pct_change_str(agg_bl["du_no_th"], agg_ht["du_no_th"])),
        ("Dư nợ quá hạn (triệu đồng)",   fmt_ty(agg_bl["du_no_qh"]),     fmt_ty(agg_ht["du_no_qh"]),
         delta_str(agg_ht["du_no_qh"] - agg_bl["du_no_qh"], "tien"),
         pct_change_str(agg_bl["du_no_qh"], agg_ht["du_no_qh"])),
        ("Dư nợ khoanh (triệu đồng)",    fmt_ty(agg_bl["du_no_khoanh"]), fmt_ty(agg_ht["du_no_khoanh"]),
         delta_str(agg_ht["du_no_khoanh"] - agg_bl["du_no_khoanh"], "tien"),
         pct_change_str(agg_bl["du_no_khoanh"], agg_ht["du_no_khoanh"])),
        ("Nợ xấu (QH+Khoanh)",           fmt_ty(_nx_bl),                  fmt_ty(_nx_ht),
         delta_str(_nx_ht - _nx_bl, "tien"),
         pct_change_str(_nx_bl, _nx_ht)),
        ("Tỷ lệ NQH (%)",                _fmt_pct_vn(tl_nqh_bl),          _fmt_pct_vn(tl_nqh_ht),
         delta_str(tl_nqh_ht - tl_nqh_bl, "pct"), "—"),
        ("Tổng lãi tồn (triệu đồng)",    fmt_ty(agg_bl["tong_lai_ton"]), fmt_ty(agg_ht["tong_lai_ton"]),
         delta_str(agg_ht["tong_lai_ton"] - agg_bl["tong_lai_ton"], "tien"),
         pct_change_str(agg_bl["tong_lai_ton"], agg_ht["tong_lai_ton"])),
        ("Số hộ vay",                    fmt_so(int(agg_bl["so_ho"])),    fmt_so(int(agg_ht["so_ho"])),
         delta_str(agg_ht["so_ho"] - agg_bl["so_ho"], "so"),
         pct_change_str(agg_bl["so_ho"], agg_ht["so_ho"])),
        ("Số khế ước",                   fmt_so(int(agg_bl["so_ku"])),    fmt_so(int(agg_ht["so_ku"])),
         delta_str(agg_ht["so_ku"] - agg_bl["so_ku"], "so"),
         pct_change_str(agg_bl["so_ku"], agg_ht["so_ku"])),
        ("Giải ngân trong năm (triệu đồng)", fmt_ty(agg_bl["gn_nam"]), fmt_ty(agg_ht["gn_nam"]),
         delta_str(agg_ht["gn_nam"] - agg_bl["gn_nam"], "tien"),
         pct_change_str(agg_bl["gn_nam"], agg_ht["gn_nam"])),
    ]

    username = st.session_state.get("username", "unknown")

    # Sheets extra cho PGD level
    sheets_extra = None
    if la_phan_he_cn(role) and not pgd_mode:
        df_pgd_ht = _agg_theo_pgd(df_full)
        df_pgd_bl = _agg_theo_pgd(df_bl_full)
        if not df_pgd_ht.empty and not df_pgd_bl.empty:
            m1 = df_pgd_ht[[COT_TEN_PGD, "tong_du_no", "du_no_qh", "so_ho"]].rename(
                columns={"tong_du_no": "dn1", "du_no_qh": "nqh1", "so_ho": "ho1"}
            )
            m2 = df_pgd_bl[[COT_TEN_PGD, "tong_du_no", "du_no_qh", "so_ho"]].rename(
                columns={"tong_du_no": "dn2", "du_no_qh": "nqh2", "so_ho": "ho2"}
            )
            merged_pgd = pd.merge(m1, m2, on=COT_TEN_PGD, how="outer").fillna(0)
            for col in ["dn1", "dn2", "nqh1", "nqh2", "ho1", "ho2"]:
                if col in merged_pgd.columns:
                    merged_pgd[col] = pd.to_numeric(merged_pgd[col], errors="coerce").fillna(0)
            merged_pgd["Δ Dư nợ"] = merged_pgd["dn2"] - merged_pgd["dn1"]
            sheets_extra = {"Theo PGD": merged_pgd}

    _render_export_section(rows_data, label_bl, label_ht, username, sheets_extra,
                           key_prefix=f"{key_prefix}hstd",
                           df_ht=df_ht, df_bl=df_bl)


# ═══════════════════════════════════════════════════════════════════════════
# NQ11 SECTION
# ═══════════════════════════════════════════════════════════════════════════

def _render_nq11_section(
    role: str,
    pgd_user: str | None,
    pgd_mode: bool,
    key_prefix: str,
    df_nq11: "pd.DataFrame | None" = None,
) -> None:
    """Render section cho NQ11 snapshot comparison."""
    ds_ky = danh_sach_ky_nq11()
    if not ds_ky:
        st.warning("⚠️ Chưa có dữ liệu NQ11 snapshot.")
        if la_phan_he_cn(role) and df_nq11 is not None and not df_nq11.empty:
            _render_nq11_manual_snap(df_nq11, key_prefix)
        return

    # Ưu tiên kỳ tháng 12 làm mốc — nếu không có thì dùng tất cả kỳ
    ds_nam_12 = sorted([k for k in ds_ky if k.endswith("-12")], reverse=True)
    co_thang_12 = bool(ds_nam_12)
    if not co_thang_12:
        st.caption("ℹ️ Chưa có snapshot tháng 12 — hiển thị tất cả kỳ có sẵn.")
        ds_nam = ds_ky
        if la_phan_he_cn(role) and df_nq11 is not None and not df_nq11.empty:
            _render_nq11_manual_snap(df_nq11, key_prefix)
    else:
        ds_nam = ds_nam_12

    if len(ds_ky) < 2:
        st.info("ℹ️ Cần ít nhất 2 kỳ snapshot để so sánh.")
        return

    col1, col2 = st.columns(2)
    with col1:
        lbl_bl = "Mốc năm (31/12)" if co_thang_12 else "Mốc so sánh"
        ky_bl = st.selectbox(lbl_bl, ds_nam, key=f"{key_prefix}nq11_bl")
    with col2:
        ds_ht = [k for k in ds_ky if k != ky_bl]
        ky_ht = st.selectbox("Kỳ hiện tại", ds_ht[:8] if ds_ht else ds_ky[:8],
                             key=f"{key_prefix}nq11_ht")

    if ky_bl == ky_ht:
        st.warning("⚠️ Vui lòng chọn 2 kỳ khác nhau.")
        return

    df_bl_full = doc_nq11_snapshot(ky_bl)
    df_ht_full = doc_nq11_snapshot(ky_ht)

    if df_bl_full.empty or df_ht_full.empty:
        st.warning("⚠️ Không đủ dữ liệu NQ11.")
        return

    # Filter theo PGD nếu cần
    if pgd_mode and pgd_user:
        df_bl = df_bl_full[df_bl_full["ten_pgd"] == pgd_user].reset_index(drop=True)
        df_ht = df_ht_full[df_ht_full["ten_pgd"] == pgd_user].reset_index(drop=True)
    else:
        df_bl = df_bl_full[df_bl_full["ten_pgd"] == "__CN__"].reset_index(drop=True)
        df_ht = df_ht_full[df_ht_full["ten_pgd"] == "__CN__"].reset_index(drop=True)

    if df_bl.empty or df_ht.empty:
        st.info("ℹ️ Không có dữ liệu NQ11 cho đơn vị đã chọn.")
        return

    a_bl = df_bl.iloc[0].to_dict() if not df_bl.empty else {}
    a_ht = df_ht.iloc[0].to_dict() if not df_ht.empty else {}

    # Tính tl_nqh từ dữ liệu (cột này không lưu trong DB)
    def _nq11_tl_nqh(a: dict) -> float:
        qh = float(a.get("no_qh", 0))
        dn = float(a.get("tong_du_no", 0))
        return qh / dn * 100 if dn > 0 else 0.0

    tl_nqh_ht = _nq11_tl_nqh(a_ht)
    tl_nqh_bl = _nq11_tl_nqh(a_bl)

    label_bl = f"NQ11 {ky_bl}"
    label_ht = f"NQ11 {ky_ht}"

    st.caption(f"**Mốc so sánh:** {label_bl} &nbsp;|&nbsp; **Kỳ hiện tại:** {label_ht}")
    st.divider()

    # KPI Row
    def _ty(x): return vn(float(x) / 1e9, 3) + " tỷ"
    render_kpi_row([
        {"label": "💰 Tổng dư nợ NQ11", "value": _ty(a_ht.get("tong_du_no", 0)),
         "delta": float(a_ht.get("tong_du_no", 0)) - float(a_bl.get("tong_du_no", 0)), "unit": "ty",
         "help": f"Mốc: {_ty(a_bl.get('tong_du_no', 0))}"},
        {"label": "⚠️ Nợ quá hạn NQ11", "value": _ty(a_ht.get("no_qh", 0)),
         "delta": float(a_ht.get("no_qh", 0)) - float(a_bl.get("no_qh", 0)), "unit": "ty", "inverse": True,
         "help": f"Mốc: {_ty(a_bl.get('no_qh', 0))}"},
        {"label": "👥 Số KH NQ11", "value": fmt_so(int(a_ht.get("so_kh", 0))),
         "delta": float(a_ht.get("so_kh", 0)) - float(a_bl.get("so_kh", 0)), "unit": "so",
         "help": f"Mốc: {fmt_so(int(a_bl.get('so_kh', 0)))}"},
        {"label": "📊 Tỷ lệ NQH", "value": fmt_pct_vn(tl_nqh_ht),
         "delta": tl_nqh_ht - tl_nqh_bl, "unit": "pct", "inverse": True,
         "help": f"Mốc: {fmt_pct_vn(tl_nqh_bl)}"},
    ])

    # Table
    rows_nq11 = [
        ("Tổng dư nợ NQ11 (triệu đồng)", float(a_bl.get("tong_du_no", 0)), float(a_ht.get("tong_du_no", 0)), False, "tien"),
        ("Nợ trong hạn NQ11 (triệu đồng)", float(a_bl.get("no_th", 0)), float(a_ht.get("no_th", 0)), False, "tien"),
        ("Nợ quá hạn NQ11 (triệu đồng)", float(a_bl.get("no_qh", 0)), float(a_ht.get("no_qh", 0)), True, "tien"),
        ("Giải ngân NQ11 trong năm (triệu đồng)", float(a_bl.get("gn_nam", 0)), float(a_ht.get("gn_nam", 0)), False, "tien"),
        ("Số khách hàng NQ11", float(a_bl.get("so_kh", 0)), float(a_ht.get("so_kh", 0)), False, "so"),
        ("Tỷ lệ NQH (%)", tl_nqh_bl, tl_nqh_ht, True, "pct"),
    ]
    render_comparison_table(rows_nq11, label_bl, label_ht, title="Chỉ tiêu NQ11")

    # Export
    rows_data = [
        ("Tổng dư nợ NQ11 (triệu đồng)", fmt_ty(float(a_bl.get("tong_du_no", 0))), fmt_ty(float(a_ht.get("tong_du_no", 0))),
         delta_str(float(a_ht.get("tong_du_no", 0)) - float(a_bl.get("tong_du_no", 0)), "tien"),
         pct_change_str(float(a_bl.get("tong_du_no", 0)), float(a_ht.get("tong_du_no", 0)))),
        ("Nợ quá hạn NQ11 (triệu đồng)", fmt_ty(float(a_bl.get("no_qh", 0))), fmt_ty(float(a_ht.get("no_qh", 0))),
         delta_str(float(a_ht.get("no_qh", 0)) - float(a_bl.get("no_qh", 0)), "tien"),
         pct_change_str(float(a_bl.get("no_qh", 0)), float(a_ht.get("no_qh", 0)))),
        ("Số KH NQ11", fmt_so(int(a_bl.get("so_kh", 0))), fmt_so(int(a_ht.get("so_kh", 0))),
         delta_str(float(a_ht.get("so_kh", 0)) - float(a_bl.get("so_kh", 0)), "so"),
         pct_change_str(float(a_bl.get("so_kh", 0)), float(a_ht.get("so_kh", 0)))),
    ]
    username = st.session_state.get("username", "unknown")
    _render_export_section(rows_data, label_bl, label_ht, username,
                           key_prefix=f"{key_prefix}nq11")


# ═══════════════════════════════════════════════════════════════════════════
# GQVL SECTION
# ═══════════════════════════════════════════════════════════════════════════

def _render_gqvl_section(
    role: str,
    pgd_user: str | None,
    pgd_mode: bool,
    key_prefix: str,
) -> None:
    """Render section cho GQVL snapshot comparison."""
    ds_ky = danh_sach_ky_gqvl()
    if not ds_ky:
        st.warning("⚠️ Chưa có dữ liệu GQVL snapshot.")
        return

    ds_nam_12 = sorted([k for k in ds_ky if k.endswith("-12")], reverse=True)
    co_thang_12 = bool(ds_nam_12)
    
    if not co_thang_12:
        st.info("""
        ℹ️ **Chưa có snapshot tháng 12 (mốc năm)**
        
        Hệ thống đang hiển thị tất cả các kỳ có sẵn để bạn có thể chọn kỳ so sánh thay thế.
        
        💡 **Gợi ý:** Upload báo cáo tháng 12 trong tab **Hệ thống** để có mốc năm chuẩn.
        """)
        ds_nam = ds_ky
    else:
        ds_nam = ds_nam_12

    if len(ds_ky) < 2:
        st.info("ℹ️ Cần ít nhất 2 kỳ snapshot để so sánh.")
        return

    col1, col2 = st.columns(2)
    with col1:
        lbl_bl = "Mốc năm (31/12)" if co_thang_12 else "Mốc so sánh"
        ky_bl = st.selectbox(lbl_bl, ds_nam, key=f"{key_prefix}gqvl_bl")
    with col2:
        ds_ht = [k for k in ds_ky if k != ky_bl]
        ky_ht = st.selectbox("Kỳ hiện tại", ds_ht[:8] if ds_ht else ds_ky[:8],
                             key=f"{key_prefix}gqvl_ht")

    if ky_bl == ky_ht:
        st.warning("⚠️ Vui lòng chọn 2 kỳ khác nhau.")
        return

    df_bl_full = doc_gqvl_snapshot(ky_bl)
    df_ht_full = doc_gqvl_snapshot(ky_ht)

    if df_bl_full.empty or df_ht_full.empty:
        st.warning("⚠️ Không đủ dữ liệu GQVL.")
        return

    if pgd_mode and pgd_user:
        df_bl = df_bl_full[df_bl_full["ten_pgd"] == pgd_user].reset_index(drop=True)
        df_ht = df_ht_full[df_ht_full["ten_pgd"] == pgd_user].reset_index(drop=True)
    else:
        df_bl = df_bl_full[df_bl_full["ten_pgd"] == "__CN__"].reset_index(drop=True)
        df_ht = df_ht_full[df_ht_full["ten_pgd"] == "__CN__"].reset_index(drop=True)

    if df_bl.empty or df_ht.empty:
        st.info("ℹ️ Không có dữ liệu GQVL cho đơn vị đã chọn.")
        return

    a_bl = df_bl.iloc[0].to_dict() if not df_bl.empty else {}
    a_ht = df_ht.iloc[0].to_dict() if not df_ht.empty else {}

    label_bl = f"GQVL {ky_bl}"
    label_ht = f"GQVL {ky_ht}"

    st.caption(f"**Mốc so sánh:** {label_bl} &nbsp;|&nbsp; **Kỳ hiện tại:** {label_ht}")
    st.divider()

    # KPI
    def _ty(x): return vn(float(x) / 1e9, 3) + " tỷ"
    render_kpi_row([
        {"label": "💰 DN trong hạn GQVL", "value": _ty(a_ht.get("dn_th", 0)),
         "delta": float(a_ht.get("dn_th", 0)) - float(a_bl.get("dn_th", 0)), "unit": "ty",
         "help": f"Mốc: {_ty(a_bl.get('dn_th', 0))}"},
        {"label": "⚠️ DN quá hạn GQVL", "value": _ty(a_ht.get("dn_qh", 0)),
         "delta": float(a_ht.get("dn_qh", 0)) - float(a_bl.get("dn_qh", 0)), "unit": "ty", "inverse": True,
         "help": f"Mốc: {_ty(a_bl.get('dn_qh', 0))}"},
        {"label": "🟡 DN khoanh GQVL", "value": _ty(a_ht.get("dn_khoanh", 0)),
         "delta": float(a_ht.get("dn_khoanh", 0)) - float(a_bl.get("dn_khoanh", 0)), "unit": "ty", "inverse": True,
         "help": f"Mốc: {_ty(a_bl.get('dn_khoanh', 0))}"},
        {"label": "📈 Giải ngân GQVL", "value": _ty(a_ht.get("gn_nam", 0)),
         "delta": float(a_ht.get("gn_nam", 0)) - float(a_bl.get("gn_nam", 0)), "unit": "ty",
         "help": f"Mốc: {_ty(a_bl.get('gn_nam', 0))}"},
    ])

    # Table
    rows_gqvl = [
        ("Dư nợ trong hạn (triệu đồng)", float(a_bl.get("dn_th", 0)), float(a_ht.get("dn_th", 0)), False, "tien"),
        ("Dư nợ quá hạn (triệu đồng)", float(a_bl.get("dn_qh", 0)), float(a_ht.get("dn_qh", 0)), True, "tien"),
        ("Dư nợ khoanh (triệu đồng)", float(a_bl.get("dn_khoanh", 0)), float(a_ht.get("dn_khoanh", 0)), True, "tien"),
        ("Giải ngân trong năm (triệu đồng)", float(a_bl.get("gn_nam", 0)), float(a_ht.get("gn_nam", 0)), False, "tien"),
        ("Số khách hàng GQVL", float(a_bl.get("so_kh", 0)), float(a_ht.get("so_kh", 0)), False, "so"),
    ]
    render_comparison_table(rows_gqvl, label_bl, label_ht, title="Chỉ tiêu GQVL")

    # Export
    rows_data = [
        ("DN trong hạn GQVL", fmt_ty(float(a_bl.get("dn_th", 0))), fmt_ty(float(a_ht.get("dn_th", 0))),
         delta_str(float(a_ht.get("dn_th", 0)) - float(a_bl.get("dn_th", 0)), "tien"),
         pct_change_str(float(a_bl.get("dn_th", 0)), float(a_ht.get("dn_th", 0)))),
        ("DN quá hạn GQVL", fmt_ty(float(a_bl.get("dn_qh", 0))), fmt_ty(float(a_ht.get("dn_qh", 0))),
         delta_str(float(a_ht.get("dn_qh", 0)) - float(a_bl.get("dn_qh", 0)), "tien"),
         pct_change_str(float(a_bl.get("dn_qh", 0)), float(a_ht.get("dn_qh", 0)))),
        ("Số KH GQVL", fmt_so(int(a_bl.get("so_kh", 0))), fmt_so(int(a_ht.get("so_kh", 0))),
         delta_str(float(a_ht.get("so_kh", 0)) - float(a_bl.get("so_kh", 0)), "so"),
         pct_change_str(float(a_bl.get("so_kh", 0)), float(a_ht.get("so_kh", 0)))),
    ]
    username = st.session_state.get("username", "unknown")
    _render_export_section(rows_data, label_bl, label_ht, username,
                           key_prefix=f"{key_prefix}gqvl")


# ═══════════════════════════════════════════════════════════════════════════
# CDTOTKVV SECTION
# ═══════════════════════════════════════════════════════════════════════════

def _render_cdtotkvv_section(
    role: str,
    pgd_user: str | None,
    pgd_mode: bool,
    key_prefix: str,
) -> None:
    """Render section cho CDTOTKVV snapshot comparison."""
    ds_ky = danh_sach_ky_cdtotkvv()
    if not ds_ky:
        st.warning("⚠️ Chưa có dữ liệu CDTOTKVV snapshot.")
        return

    ds_nam_12 = sorted([k for k in ds_ky if k.endswith("-12")], reverse=True)
    co_thang_12 = bool(ds_nam_12)
    
    if not co_thang_12:
        st.info("""
        ℹ️ **Chưa có snapshot tháng 12 (mốc năm)**
        
        Hệ thống đang hiển thị tất cả các kỳ có sẵn để bạn có thể chọn kỳ so sánh thay thế.
        
        💡 **Gợi ý:** Upload báo cáo tháng 12 trong tab **Hệ thống** để có mốc năm chuẩn.
        """)
        ds_nam = ds_ky
    else:
        ds_nam = ds_nam_12

    if len(ds_ky) < 2:
        st.info("ℹ️ Cần ít nhất 2 kỳ snapshot để so sánh.")
        return

    col1, col2 = st.columns(2)
    with col1:
        lbl_bl = "Mốc năm (31/12)" if co_thang_12 else "Mốc so sánh"
        ky_bl = st.selectbox(lbl_bl, ds_nam, key=f"{key_prefix}cdt_bl")
    with col2:
        ds_ht = [k for k in ds_ky if k != ky_bl]
        ky_ht = st.selectbox("Kỳ hiện tại", ds_ht[:8] if ds_ht else ds_ky[:8],
                             key=f"{key_prefix}cdt_ht")

    if ky_bl == ky_ht:
        st.warning("⚠️ Vui lòng chọn 2 kỳ khác nhau.")
        return

    df_bl_full = doc_cdtotkvv_snapshot(ky_bl)
    df_ht_full = doc_cdtotkvv_snapshot(ky_ht)

    if df_bl_full.empty or df_ht_full.empty:
        st.warning("⚠️ Không đủ dữ liệu CDTOTKVV.")
        return

    if pgd_mode and pgd_user:
        df_bl = df_bl_full[df_bl_full["ten_pgd"] == pgd_user].reset_index(drop=True)
        df_ht = df_ht_full[df_ht_full["ten_pgd"] == pgd_user].reset_index(drop=True)
        if df_bl.empty or df_ht.empty:
            df_bl = df_bl_full[df_bl_full["ten_pgd"] == "__CN__"].reset_index(drop=True)
            df_ht = df_ht_full[df_ht_full["ten_pgd"] == "__CN__"].reset_index(drop=True)
    else:
        df_bl = df_bl_full[df_bl_full["ten_pgd"] == "__CN__"].reset_index(drop=True)
        df_ht = df_ht_full[df_ht_full["ten_pgd"] == "__CN__"].reset_index(drop=True)

    if df_bl.empty or df_ht.empty:
        st.info("ℹ️ Không có dữ liệu CDTOTKVV tổng hợp cho kỳ đã chọn.")
        return

    a_bl = df_bl.iloc[0].to_dict() if not df_bl.empty else {}
    a_ht = df_ht.iloc[0].to_dict() if not df_ht.empty else {}

    # Tính tl_tot_kha từ dữ liệu (cột này không lưu trong DB)
    def _cdt_tl_tot_kha(a: dict) -> float:
        tot = int(a.get("so_tot", 0))
        kha = int(a.get("so_kha", 0))
        so_to = int(a.get("so_to", 0))
        return (tot + kha) / so_to * 100 if so_to > 0 else 0.0

    tl_tot_kha_ht = _cdt_tl_tot_kha(a_ht)
    tl_tot_kha_bl = _cdt_tl_tot_kha(a_bl)

    label_bl = f"CDT {ky_bl}"
    label_ht = f"CDT {ky_ht}"

    st.caption(f"**Mốc so sánh:** {label_bl} &nbsp;|&nbsp; **Kỳ hiện tại:** {label_ht}")
    st.divider()

    # KPI Row 1
    render_kpi_row([
        {"label": "🏆 Tổng số tổ", "value": fmt_so(int(a_ht.get("so_to", 0))),
         "delta": float(a_ht.get("so_to", 0)) - float(a_bl.get("so_to", 0)), "unit": "so"},
        {"label": "🟢 Tổ Tốt", "value": fmt_so(int(a_ht.get("so_tot", 0))),
         "delta": float(a_ht.get("so_tot", 0)) - float(a_bl.get("so_tot", 0)), "unit": "so",
         "help": f"Mốc: {fmt_so(int(a_bl.get('so_tot', 0)))}"},
        {"label": "🔵 Tổ Khá", "value": fmt_so(int(a_ht.get("so_kha", 0))),
         "delta": float(a_ht.get("so_kha", 0)) - float(a_bl.get("so_kha", 0)), "unit": "so",
         "help": f"Mốc: {fmt_so(int(a_bl.get('so_kha', 0)))}"},
        {"label": "🟡 Tổ Trung bình", "value": fmt_so(int(a_ht.get("so_tb", 0))),
         "delta": float(a_ht.get("so_tb", 0)) - float(a_bl.get("so_tb", 0)), "unit": "so", "inverse": True,
         "help": f"Mốc: {fmt_so(int(a_bl.get('so_tb', 0)))}"},
    ])

    # KPI Row 2
    render_kpi_row([
        {"label": "🔴 Tổ Yếu", "value": fmt_so(int(a_ht.get("so_yeu", 0))),
         "delta": float(a_ht.get("so_yeu", 0)) - float(a_bl.get("so_yeu", 0)), "unit": "so", "inverse": True,
         "help": f"Mốc: {fmt_so(int(a_bl.get('so_yeu', 0)))}"},
        {"label": "📊 Tỷ lệ tổ Tốt/Khá", "value": fmt_pct_vn(tl_tot_kha_ht),
         "delta": tl_tot_kha_ht - tl_tot_kha_bl, "unit": "pct",
         "help": f"Mốc: {fmt_pct_vn(tl_tot_kha_bl)}"},
        {"label": "", "value": "", "delta": None},
        {"label": "", "value": "", "delta": None},
    ])

    # Table
    rows_cdt = [
        ("Tổng số tổ", float(a_bl.get("so_to", 0)), float(a_ht.get("so_to", 0)), False, "so"),
        ("Tổ Tốt", float(a_bl.get("so_tot", 0)), float(a_ht.get("so_tot", 0)), False, "so"),
        ("Tổ Khá", float(a_bl.get("so_kha", 0)), float(a_ht.get("so_kha", 0)), False, "so"),
        ("Tổ Trung bình", float(a_bl.get("so_tb", 0)), float(a_ht.get("so_tb", 0)), True, "so"),
        ("Tổ Yếu", float(a_bl.get("so_yeu", 0)), float(a_ht.get("so_yeu", 0)), True, "so"),
        ("Tỷ lệ tổ Tốt/Khá (%)", tl_tot_kha_bl, tl_tot_kha_ht, False, "pct"),
    ]
    render_comparison_table(rows_cdt, label_bl, label_ht, title="Chỉ tiêu Chấm điểm tổ")

    # Export
    rows_data = [
        ("Tổng số tổ", fmt_so(int(a_bl.get("so_to", 0))), fmt_so(int(a_ht.get("so_to", 0))),
         delta_str(float(a_ht.get("so_to", 0)) - float(a_bl.get("so_to", 0)), "so"),
         pct_change_str(float(a_bl.get("so_to", 0)), float(a_ht.get("so_to", 0)))),
        ("Tổ Tốt", fmt_so(int(a_bl.get("so_tot", 0))), fmt_so(int(a_ht.get("so_tot", 0))),
         delta_str(float(a_ht.get("so_tot", 0)) - float(a_bl.get("so_tot", 0)), "so"),
         pct_change_str(float(a_bl.get("so_tot", 0)), float(a_ht.get("so_tot", 0)))),
        ("Tổ Khá", fmt_so(int(a_bl.get("so_kha", 0))), fmt_so(int(a_ht.get("so_kha", 0))),
         delta_str(float(a_ht.get("so_kha", 0)) - float(a_bl.get("so_kha", 0)), "so"),
         pct_change_str(float(a_bl.get("so_kha", 0)), float(a_ht.get("so_kha", 0)))),
        ("Tổ Yếu", fmt_so(int(a_bl.get("so_yeu", 0))), fmt_so(int(a_ht.get("so_yeu", 0))),
         delta_str(float(a_ht.get("so_yeu", 0)) - float(a_bl.get("so_yeu", 0)), "so"),
         pct_change_str(float(a_bl.get("so_yeu", 0)), float(a_ht.get("so_yeu", 0)))),
    ]
    username = st.session_state.get("username", "unknown")
    _render_export_section(rows_data, label_bl, label_ht, username,
                           key_prefix=f"{key_prefix}cdt")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def render_moc_nam(tab: DeltaGenerator = None, **kwargs) -> None:
    """So sánh mốc năm — entry point với tabs chọn loại dữ liệu."""
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    pgd_mode = kwargs.get("pgd_mode", False)
    df_nq11  = kwargs.get("df_nq11")

    key_prefix = f"pgd_{pgd_slug(pgd_user)}_" if pgd_mode and pgd_user else "cn_"

    ctx = st.container()
    with ctx:
        st.subheader("📈 So sánh mốc năm")

        # ── Tabs chọn loại dữ liệu ──
        ds_labels = [v[0] for v in _DATA_SOURCES.values()]
        ds_keys   = list(_DATA_SOURCES.keys())

        tab_sel = st.radio(
            "Loại dữ liệu so sánh",
            ds_labels,
            horizontal=True,
            key=f"{key_prefix}moc_nam_ds",
            label_visibility="collapsed",
        )
        st.divider()

        # Map tab selection to key
        selected_key = ds_keys[ds_labels.index(tab_sel)]

        # ── Route to appropriate renderer ──
        if selected_key == "hstd":
            _render_hstd_section(df_full, df, role, pgd_user, pgd_mode, key_prefix)
        elif selected_key == "nq11":
            _render_nq11_section(role, pgd_user, pgd_mode, key_prefix, df_nq11=df_nq11)
        elif selected_key == "gqvl":
            _render_gqvl_section(role, pgd_user, pgd_mode, key_prefix)
        elif selected_key == "cdtotkvv":
            _render_cdtotkvv_section(role, pgd_user, pgd_mode, key_prefix)
