"""Phân tích Nợ khoanh — danh mục khoản vay đang trong giai đoạn khoanh nợ QĐ 62.

Port từ VSPPRO Khoanh.tsx.
KPI cards + breakdown theo Chương trình / Xã / ĐVUT + danh sách chi tiết.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_QH,
    COT_DVUT,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_PGD,
)
from utils import fmt_so, fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel

COT_DU_NO_KHOANH = "Dư nợ khoanh"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _loc_khoanh(df: pd.DataFrame) -> pd.DataFrame:
    """Lọc các món vay đang khoanh nợ (Dư nợ khoanh > 0)."""
    if COT_DU_NO_KHOANH not in df.columns:
        return pd.DataFrame()
    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    return df[du_kh > 0].copy()


def _bang_theo_nhom(df: pd.DataFrame, nhom_col: str) -> pd.DataFrame:
    """Bảng tổng hợp: nhóm | Số món | Dư nợ khoanh | Tỷ trọng%."""
    if nhom_col not in df.columns or df.empty:
        return pd.DataFrame()

    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df = df.copy()
    df["_du_kh"] = du_kh

    nhom = (
        df.groupby(nhom_col)
        .agg(so_mon=(COT_SO_KU, "nunique"), du_no_khoanh=("_du_kh", "sum"))
        .reset_index()
        .sort_values("du_no_khoanh", ascending=False)
    )

    tong = nhom["du_no_khoanh"].sum()
    nhom["Tỷ trọng%"] = (nhom["du_no_khoanh"] / tong * 100).round(1).apply(
        lambda x: f"{x:.1f}".replace(".", ",") + "%"
    ) if tong > 0 else "0%"
    nhom["Dư nợ khoanh"] = nhom["du_no_khoanh"].apply(fmt_ty)
    nhom = nhom.rename(columns={"so_mon": "Số món"})
    return nhom[[nhom_col, "Số món", "Dư nợ khoanh", "Tỷ trọng%"]]


def _chart_nhom(df: pd.DataFrame, nhom_col: str, key: str) -> None:
    """Horizontal bar chart: top 15 nhóm theo dư nợ khoanh."""
    try:
        import plotly.express as px
    except ImportError:
        return

    if df.empty or nhom_col not in df.columns:
        return

    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df = df.copy()
    df["_du_kh"] = du_kh

    nhom = df.groupby(nhom_col)["_du_kh"].sum().reset_index()
    nhom.columns = [nhom_col, "_val"]
    nhom = nhom[nhom["_val"] > 0].sort_values("_val", ascending=True).tail(15)
    if nhom.empty:
        return

    nhom["Label"] = nhom["_val"].apply(fmt_ty)

    fig = px.bar(
        nhom, y=nhom_col, x="_val",
        orientation="h",
        text="Label",
        color="_val",
        color_continuous_scale=["#fff3e0", "#e65100"],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=max(260, len(nhom) * 28 + 80),
        margin=dict(t=10, b=20, l=10, r=70),
        coloraxis_showscale=False,
        xaxis_title="Dư nợ khoanh (VND)",
        yaxis_title="",
    )
    st.plotly_chart(fig, width='stretch', key=key)


def _heatmap_dao_han(df: pd.DataFrame, key: str) -> None:
    """Bar chart phân bổ khoanh theo tháng đáo hạn."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    if COT_NGAY_DH not in df.columns or df.empty:
        return

    ngay_dh = pd.to_datetime(df[COT_NGAY_DH], errors="coerce", dayfirst=True)
    df = df.copy()
    df["_du_kh"] = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df["_ym"] = ngay_dh.dt.to_period("Y").astype(str)  # nhóm theo năm

    nhom = (
        df.groupby("_ym")
        .agg(so_mon=("_ym", "count"), du_no=("_du_kh", "sum"))
        .reset_index()
        .sort_values("_ym")
    )
    nhom = nhom[nhom["_ym"].str.match(r"\d{4}")]  # loại NaT

    if nhom.empty:
        return

    fig = go.Figure(go.Bar(
        x=nhom["_ym"],
        y=nhom["so_mon"],
        name="Số món",
        marker_color="#e64a19",
        text=nhom["so_mon"].astype(str),
        textposition="outside",
        hovertext=nhom["du_no"].apply(fmt_ty),
        hoverinfo="x+text",
    ))
    fig.update_layout(
        xaxis_title="Năm đáo hạn",
        yaxis_title="Số khoản khoanh",
        height=260,
        margin=dict(t=10, b=30, l=40, r=20),
    )
    st.markdown("**📅 Phân bổ theo năm đáo hạn**")
    st.plotly_chart(fig, width='stretch', key=key)


# ─── Render ───────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """
    Render tab Phân tích Nợ khoanh.

    Dùng được ở cả phân hệ CN (truyền df_full) và PGD.
    """
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🔒 Phân tích Nợ khoanh")
        st.caption(
            "Khoản vay đang trong giai đoạn khoanh nợ theo QĐ 62/2015/QĐ-TTg. "
            "Phân tích theo Chương trình / Xã / Hội đoàn thể."
        )

        use_df = df_full if la_phan_he_cn(role) else df
        if use_df is None or use_df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        if COT_DU_NO_KHOANH not in use_df.columns:
            st.info(
                f"ℹ️ Dữ liệu không có cột '{COT_DU_NO_KHOANH}'. "
                "Cần upload HSTD có cột Dư nợ khoanh."
            )
            return

        df_kh = _loc_khoanh(use_df)

        # ── KPI tổng quan ─────────────────────────────────────────────────
        tong_du_no = (
            pd.to_numeric(use_df[COT_TONG_DU_NO], errors="coerce").sum()
            if COT_TONG_DU_NO in use_df.columns else 0
        )
        tong_khoanh = (
            pd.to_numeric(use_df[COT_DU_NO_KHOANH], errors="coerce").fillna(0).sum()
        )
        so_mon = (
            df_kh[COT_SO_KU].nunique() if (not df_kh.empty and COT_SO_KU in df_kh.columns)
            else len(df_kh)
        )
        so_ho = (
            df_kh[COT_MA_KH].nunique() if (not df_kh.empty and COT_MA_KH in df_kh.columns)
            else 0
        )
        tl_khoanh = tong_khoanh / tong_du_no * 100 if tong_du_no > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🔒 Số món khoanh", fmt_so(so_mon))
        k2.metric("👤 Số hộ", fmt_so(so_ho))
        k3.metric("💰 Tổng dư nợ khoanh", fmt_ty(tong_khoanh))
        k4.metric(
            "📊 Tỷ lệ khoanh / tổng DN",
            f"{tl_khoanh:.2f}".replace(".", ",") + "%",
            delta=f"{tl_khoanh:.2f}".replace(".", ",") + "%" if tl_khoanh > 0 else None,
            delta_color="inverse" if tl_khoanh > 2 else "off",
        )

        if df_kh.empty:
            st.success("✅ Hiện không có món vay nào đang khoanh nợ.")
            return

        st.divider()

        # ── Lọc PGD (CN only) ─────────────────────────────────────────────
        key_prefix = "cn_"
        if la_phan_he_cn(role):
            col_f, _ = st.columns([2, 4])
            with col_f:
                pgd_chon = st.selectbox(
                    "🔍 Lọc PGD",
                    ["Tất cả"] + DS_PGD,
                    key="khoanh_pgd_loc",
                )
            if pgd_chon != "Tất cả" and COT_TEN_PGD in df_kh.columns:
                df_kh = df_kh[df_kh[COT_TEN_PGD] == pgd_chon]
        else:
            from data.pgd import pgd_slug
            key_prefix = f"pgd_{pgd_slug(pgd_user)}_" if pgd_user else "pgd_"

        # ── Heatmap đáo hạn ───────────────────────────────────────────────
        _heatmap_dao_han(df_kh, key=f"{key_prefix}khoanh_hm")

        st.divider()

        # ── Sub-tabs ──────────────────────────────────────────────────────
        d1, d2, d3, d4 = st.tabs([
            "📋 Theo Chương trình",
            "🏘️ Theo Xã",
            "🤝 Theo Hội đoàn thể",
            "📄 Danh sách chi tiết",
        ])

        for dtab, nhom_col, tag, label in [
            (d1, COT_TEN_CT,  "ct",   "Chương trình"),
            (d2, COT_TEN_XA,  "xa",   "Xã"),
            (d3, COT_DVUT,    "dvut", "Hội đoàn thể"),
        ]:
            with dtab:
                if nhom_col not in df_kh.columns:
                    st.info(f"Không có cột {label} trong dữ liệu.")
                    continue
                c_chart, c_table = st.columns([3, 2])
                with c_chart:
                    _chart_nhom(df_kh, nhom_col, key=f"{key_prefix}khoanh_{tag}_chart")
                with c_table:
                    bng = _bang_theo_nhom(df_kh, nhom_col)
                    if not bng.empty:
                        hien_thi_dataframe_phan_trang(
                            bng, key=f"{key_prefix}khoanh_{tag}_tbl", height=320
                        )

        with d4:
            cols_hien = [c for c in [
                COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_KH, COT_SO_KU,
                COT_TEN_CT, COT_DU_NO_KHOANH, COT_DU_NO_QH, COT_NGAY_DH,
            ] if c in df_kh.columns]

            df_hien = df_kh[cols_hien].copy()
            if COT_DU_NO_KHOANH in df_hien.columns:
                df_hien[COT_DU_NO_KHOANH] = (
                    pd.to_numeric(df_hien[COT_DU_NO_KHOANH], errors="coerce")
                    .apply(fmt_ty)
                )
            if COT_DU_NO_QH in df_hien.columns:
                df_hien[COT_DU_NO_QH] = (
                    pd.to_numeric(df_hien[COT_DU_NO_QH], errors="coerce")
                    .apply(fmt_ty)
                )

            hien_thi_dataframe_phan_trang(
                df_hien, key=f"{key_prefix}khoanh_chitiet", height=420
            )

            if st.button(
                f"📥 Xuất Excel ({len(df_kh)} món)",
                key=f"{key_prefix}khoanh_xuat",
            ):
                st.session_state[f"_{key_prefix}khoanh_buf"] = xuat_excel(
                    {"Nợ khoanh": df_hien}
                )
            if st.session_state.get(f"_{key_prefix}khoanh_buf"):
                st.download_button(
                    "⬇️ Tải về Excel",
                    data=st.session_state[f"_{key_prefix}khoanh_buf"],
                    file_name="NoKhoanh.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"{key_prefix}khoanh_dl",
                )
