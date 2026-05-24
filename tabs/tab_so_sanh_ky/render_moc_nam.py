"""So sánh mốc 31/12 — dùng baseline từ file đã upload."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_KHOANH, COT_DU_NO_QH, COT_DU_NO_TH,
    COT_DVUT, COT_MA_KH, COT_NGAY_SL,
    COT_SO_KU, COT_TEN_CT, COT_TEN_PGD,
    COT_TEN_XA, COT_TONG_DU_NO,
    danh_sach_nam_baseline, danh_sach_nam_baseline_pgd,
)
from data.hstd import doc_baseline_merged
from data.pgd import pgd_slug
from services.so_sanh_ky_service import (
    agg_mot_pgd as _agg_mot_pgd,
    agg_theo_pgd as _agg_theo_pgd,
    group_bien_dong as _group_bien_dong,
    tl_nqh as _tl_nqh,
    fmt_pct_vn as _fmt_pct_vn,
)
from services.period_compare import (
    join_by_loan,
)
from tabs.tab_so_sanh_ky._common import (
    delta_str, pct_change_str,
    render_quality_bars_2_ky,
    render_hbar_chart, render_flow_diagram,
)
from tabs.tab_so_sanh_ky._export import (
    render_export_ui,
)
from utils import fmt_ty, fmt_so
import db


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


def _snap(agg: dict) -> dict:
    total = agg["tong_du_no"]
    th = agg.get("du_no_th", 0)
    qh = agg.get("du_no_qh", 0)
    kh = agg.get("du_no_khoanh", 0)
    if th == 0 and total > 0:
        th = max(0.0, total - qh - kh)
    return {"trong_han": th, "qua_han": qh, "khoanh": kh, "total": total}


def _render_top_bien_dong(
    df_bl: pd.DataFrame,
    df_ht: pd.DataFrame,
    label_bl: str,
    label_ht: str,
    key_prefix: str,
) -> None:
    """Top N tăng/giảm theo chiều và chỉ tiêu."""
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


def render_moc_nam(tab: DeltaGenerator = None, **kwargs) -> None:
    """So sánh kỳ hiện tại với mốc 31/12."""
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    pgd_mode = kwargs.get("pgd_mode", False)

    key_prefix = f"pgd_{pgd_slug(pgd_user)}_" if pgd_mode and pgd_user else "cn_"

    ctx = st.container()
    with ctx:
        st.subheader("📈 So sánh mốc 31/12")

        # ── Năm baseline ──
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
        if not ds_nam:
            st.warning("⚠️ Chưa có dữ liệu năm trước. Upload baseline trong tab Hệ thống.")
            return

        chon_nam = st.selectbox("So sánh với mốc 31/12 năm", ds_nam, key=f"{key_prefix}ssk_nam")

        # ── Đọc dữ liệu ──
        df_bl_full = doc_baseline_merged(chon_nam)
        if df_bl_full is None or df_bl_full.empty:
            st.warning(f"⚠️ Chưa có dữ liệu baseline 31/12/{chon_nam}.")
            return

        if pgd_mode and pgd_user and COT_TEN_PGD in df_bl_full.columns:
            df_bl = df_bl_full[df_bl_full[COT_TEN_PGD] == pgd_user].copy()
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

        st.caption(f"**Kỳ hiện tại:** {label_ht} &nbsp;|&nbsp; **Mốc so sánh:** {label_bl}")
        st.divider()

        # ══ SECTION 1: KPI (12 cards: 3 hàng × 4) + quality bars ══════
        st.markdown("**📈 TỔNG QUAN**")

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

        def _ds(v: float, b: float, inv: bool = False) -> str:
            return delta_str(v - b, "tien")

        # Hàng 1 — Tăng trưởng
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        r1c1.metric("Tổng dư nợ", fmt_ty(agg_ht["tong_du_no"]),
                    delta=_ds(agg_ht["tong_du_no"], agg_bl["tong_du_no"]),
                    help=f"Mốc: {fmt_ty(agg_bl['tong_du_no'])}")
        r1c2.metric("Số khế ước", fmt_so(agg_ht["so_ku"]),
                    delta=delta_str(agg_ht["so_ku"] - agg_bl["so_ku"], "so"),
                    help=f"Mốc: {fmt_so(agg_bl['so_ku'])}")
        r1c3.metric("Số hộ vay", fmt_so(agg_ht["so_ho"]),
                    delta=delta_str(agg_ht["so_ho"] - agg_bl["so_ho"], "so"),
                    help=f"Mốc: {fmt_so(agg_bl['so_ho'])}")
        r1c4.metric("Mức vay BQ/KH", fmt_ty(muc_vay_ht),
                    delta=_ds(muc_vay_ht, muc_vay_bl),
                    help=f"Mốc: {fmt_ty(muc_vay_bl)}")

        # Hàng 2 — NQH & khoanh
        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        r2c1.metric("Tỷ lệ NQH", _fmt_pct_vn(tl_nqh_ht),
                    delta=_fmt_pct_vn(tl_nqh_ht - tl_nqh_bl), delta_color="inverse",
                    help=f"Mốc: {_fmt_pct_vn(tl_nqh_bl)}")
        r2c2.metric("Dư nợ quá hạn", fmt_ty(agg_ht["du_no_qh"]),
                    delta=_ds(agg_ht["du_no_qh"], agg_bl["du_no_qh"]), delta_color="inverse",
                    help=f"Mốc: {fmt_ty(agg_bl['du_no_qh'])}")
        r2c3.metric("Dư nợ khoanh", fmt_ty(agg_ht["du_no_khoanh"]),
                    delta=_ds(agg_ht["du_no_khoanh"], agg_bl["du_no_khoanh"]), delta_color="inverse",
                    help=f"Mốc: {fmt_ty(agg_bl['du_no_khoanh'])}")
        r2c4.metric("Tỷ lệ DN khoanh", _fmt_pct_vn(tl_kh_ht),
                    delta=_fmt_pct_vn(tl_kh_ht - tl_kh_bl), delta_color="inverse",
                    help=f"Mốc: {_fmt_pct_vn(tl_kh_bl)}")

        # Hàng 3 — Nợ xấu & lãi tồn
        r3c1, r3c2, r3c3, r3c4 = st.columns(4)
        r3c1.metric("Nợ xấu (QH+Khoanh)", fmt_ty(no_xau_ht),
                    delta=_ds(no_xau_ht, no_xau_bl), delta_color="inverse",
                    help=f"Mốc: {fmt_ty(no_xau_bl)}")
        r3c2.metric("Tỷ lệ nợ xấu", _fmt_pct_vn(tl_nx_ht),
                    delta=_fmt_pct_vn(tl_nx_ht - tl_nx_bl), delta_color="inverse",
                    help=f"Mốc: {_fmt_pct_vn(tl_nx_bl)}")
        r3c3.metric("Tổng lãi tồn", fmt_ty(agg_ht["tong_lai_ton"]),
                    delta=_ds(agg_ht["tong_lai_ton"], agg_bl["tong_lai_ton"]), delta_color="inverse",
                    help=f"Mốc: {fmt_ty(agg_bl['tong_lai_ton'])}")
        r3c4.metric("Giải ngân trong năm", fmt_ty(agg_ht["gn_nam"]),
                    delta=_ds(agg_ht["gn_nam"], agg_bl["gn_nam"]),
                    help=f"Mốc: {fmt_ty(agg_bl['gn_nam'])}")

        # Quality bars
        render_quality_bars_2_ky(
            f"Kỳ trước · {label_bl}", agg_bl["tong_du_no"], agg_bl["du_no_th"],
            agg_bl["du_no_qh"], agg_bl["du_no_khoanh"],
            f"Kỳ sau · {label_ht}", agg_ht["tong_du_no"], agg_ht["du_no_th"],
            agg_ht["du_no_qh"], agg_ht["du_no_khoanh"],
        )

        st.divider()

        # ══ SECTION 2: Multi-dimension tabs ══════════════════════════
        st.markdown("**📋 PHÂN TÍCH ĐA CHIỀU**")

        tab_labels = ["🏢 Theo PGD", "📋 Theo CT", "📍 Theo Xã",
                      "📈 Top biến động", "🔄 Vòng đời"]
        tab_panes = st.tabs(tab_labels)

        # ── Tab 1: Theo PGD ──
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
                    df_out[f"DN mốc"]   = df_merge["tong_du_no_bl"].apply(fmt_ty)
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

        # ── Tab 2: Theo Chương trình ──
        with tab_panes[1]:
            g_ht = _group_bien_dong(df_ht, COT_TEN_CT)
            g_bl = _group_bien_dong(df_bl, COT_TEN_CT)
            if not g_ht.empty and not g_bl.empty:
                merged = g_ht.merge(g_bl, on=COT_TEN_CT, how="outer",
                                    suffixes=("_ht", "_bl")).fillna(0)
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

        # ── Tab 3: Theo Xã ──
        with tab_panes[2]:
            g_ht = _group_bien_dong(df_ht, COT_TEN_XA)
            g_bl = _group_bien_dong(df_bl, COT_TEN_XA)
            if not g_ht.empty and not g_bl.empty:
                merged = g_ht.merge(g_bl, on=COT_TEN_XA, how="outer",
                                    suffixes=("_ht", "_bl")).fillna(0)
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

        # ── Tab 4: Top biến động ──
        with tab_panes[3]:
            _render_top_bien_dong(df_bl, df_ht, label_bl, label_ht, key_prefix)

        # ── Tab 5: Vòng đời ──
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

        # ══ SECTION 3: Export ════════════════════════════════════════
        st.markdown("**📤 XUẤT BÁO CÁO**")

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
                from tabs.tab_so_sanh_ky._export import build_excel_sheets_pgd
                # Tạo sheet PGD từ 2 dataframe đã tổng hợp
                m1 = df_pgd_ht[[COT_TEN_PGD, "tong_du_no", "du_no_qh", "so_ho"]].rename(
                    columns={"tong_du_no": "dn1", "du_no_qh": "nqh1", "so_ho": "ho1"}
                )
                m2 = df_pgd_bl[[COT_TEN_PGD, "tong_du_no", "du_no_qh", "so_ho"]].rename(
                    columns={"tong_du_no": "dn2", "du_no_qh": "nqh2", "so_ho": "ho2"}
                )
                merged_pgd = pd.merge(m1, m2, on=COT_TEN_PGD, how="outer").fillna(0)
                merged_pgd["Δ Dư nợ"] = merged_pgd["dn2"] - merged_pgd["dn1"]
                sheets_extra = {"Theo PGD": merged_pgd}

        render_export_ui(rows_data, label_bl, label_ht, username, sheets_extra,
                         action="xuat_bieu_cn")
