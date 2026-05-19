"""Dashboard Tổng hợp Quản lý Nợ khoanh.

KPI tổng quan + biểu đồ tròn lý do khoanh + cột ngang dư nợ theo PGD + top 10.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_KHOANH,
    COT_NGAY_HH_KHOANH,
    COT_SO_KU,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_PGD,
    LY_DO_KHOANH_LABEL,
)
from utils import fmt_so, fmt_ty

try:
    import plotly.express as px
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False


def _loc_khoanh(df: pd.DataFrame) -> pd.DataFrame:
    if COT_DU_NO_KHOANH not in df.columns or df.empty:
        return pd.DataFrame()
    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    return df[du_kh > 0].copy()


def _doc_ly_do_khoanh(df_kh: pd.DataFrame) -> pd.Series | None:
    """Tổng hợp lý do khoanh từ qlnk_bo_sung, fallback về cột dữ liệu nếu có."""
    import db
    if df_kh.empty or COT_SO_KU not in df_kh.columns:
        return None
    counts: dict[str, int] = {}
    for ku in df_kh[COT_SO_KU].dropna().unique():
        bs = db.doc_bo_sung_mon_vay(str(ku))
        if bs and bs.get("ly_do_khoanh"):
            ld = bs["ly_do_khoanh"]
            counts[ld] = counts.get(ld, 0) + 1
    if not counts:
        return None
    return pd.Series(counts, name="Số món")


def _pie_ly_do(series: pd.Series, key: str) -> None:
    if not _HAS_PLOTLY:
        return
    labels_mapped = [LY_DO_KHOANH_LABEL.get(k, k) for k in series.index]
    fig = px.pie(
        names=labels_mapped,
        values=series.values,
        hole=0.4,
    )
    fig.update_traces(textinfo="percent+label", textfont_size=11)
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    st.plotly_chart(fig, width='stretch', key=key)


def _bar_pgd(df_kh: pd.DataFrame, key: str) -> None:
    if not _HAS_PLOTLY or df_kh.empty:
        return

    du_kh = pd.to_numeric(df_kh[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df = df_kh.copy()
    df["_du"] = du_kh

    if COT_TEN_PGD in df.columns:
        nhom = df.groupby(COT_TEN_PGD)["_du"].sum().reset_index()
    else:
        nhom = pd.DataFrame({"_du": [df["_du"].sum()]})
        nhom["_label"] = "Toàn Chi nhánh"

    nhom = nhom[nhom["_du"] > 0].sort_values("_du", ascending=True)
    if nhom.empty:
        return

    label_col = COT_TEN_PGD if COT_TEN_PGD in nhom.columns else "_label"
    nhom["label_text"] = nhom["_du"].apply(fmt_ty)

    fig = px.bar(
        nhom,
        y=label_col,
        x="_du",
        orientation="h",
        text="label_text",
        color="_du",
        color_continuous_scale=["#FFF3E0", "#E65100"],
    )
    fig.update_traces(textposition="outside", textfont_size=12)
    fig.update_layout(
        height=max(260, len(nhom) * 34 + 80),
        margin=dict(t=10, b=20, l=10, r=100),
        coloraxis_showscale=False,
        xaxis_title="Dư nợ khoanh (VND)",
        yaxis_title="",
    )
    st.plotly_chart(fig, width='stretch', key=key)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df = kwargs.get("df")
    df_full = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username", "unknown")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📊 Chuyên Đề Nợ Khoanh — Tổng hợp")
        st.caption(
            "Dashboard tổng quan tình hình nợ khoanh toàn Chi nhánh. "
            "KPI · Biểu đồ lý do khoanh · Dư nợ theo PGD · Top 10 món lớn nhất."
        )

        use_df = df_full if la_phan_he_cn(role) else df
        if use_df is None or use_df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        if COT_DU_NO_KHOANH not in use_df.columns:
            st.info(f"ℹ️ Dữ liệu không có cột '{COT_DU_NO_KHOANH}'.")
            return

        df_kh = _loc_khoanh(use_df)

        tong_du_no = (
            pd.to_numeric(use_df[COT_TONG_DU_NO], errors="coerce").fillna(0).sum()
            if COT_TONG_DU_NO in use_df.columns else 0
        )
        tong_khoanh = (
            pd.to_numeric(use_df[COT_DU_NO_KHOANH], errors="coerce").fillna(0).sum()
        )
        so_mon_khoanh = len(df_kh)
        so_ho = (
            df_kh["Mã KH"].nunique()
            if not df_kh.empty and "Mã KH" in df_kh.columns
            else 0
        )
        tl_khoanh = tong_khoanh / tong_du_no * 100 if tong_du_no > 0 else 0

        so_mon_sap_het_han = 0
        if COT_NGAY_HH_KHOANH in df_kh.columns and not df_kh.empty:
            hom_nay = date.today()
            ngay_hh = pd.to_datetime(
                df_kh[COT_NGAY_HH_KHOANH], errors="coerce", dayfirst=True
            )
            so_mon_sap_het_han = int(
                (ngay_hh.notna() & (ngay_hh.dt.date <= hom_nay)).sum()
            )

        import db
        rows_kt = db.doc_ket_qua_kiem_tra()
        da_kiem_tra_set = {r["ma_mon_vay"] for r in rows_kt} if rows_kt else set()
        so_mon_da_kt = 0
        if COT_SO_KU in df_kh.columns and not df_kh.empty:
            so_mon_da_kt = int(df_kh[COT_SO_KU].astype(str).isin(da_kiem_tra_set).sum())
        tl_kiem_tra = so_mon_da_kt / so_mon_khoanh * 100 if so_mon_khoanh > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🔒 Tổng món khoanh", fmt_so(so_mon_khoanh) + " món")
        k2.metric(
            "✅ Tỷ lệ kiểm tra",
            f"{tl_kiem_tra:.1f}".replace(".", ",") + "%",
            delta=f"{so_mon_da_kt}/{so_mon_khoanh} món",
        )
        k3.metric(
            "⏰ Sắp hết hạn khoanh",
            fmt_so(so_mon_sap_het_han) + " món",
            delta="Cần rà soát" if so_mon_sap_het_han > 0 else None,
            delta_color="inverse" if so_mon_sap_het_han > 0 else "off",
        )
        k4.metric(
            "💰 Dư nợ khoanh",
            fmt_ty(tong_khoanh),
            delta=f"{tl_khoanh:.2f}".replace(".", ",") + "% tổng DN",
            delta_color="inverse" if tl_khoanh > 2 else "off",
        )

        if df_kh.empty:
            st.success("✅ Hiện không có món vay nào đang khoanh nợ.")
            return

        st.divider()

        key_prefix = "cn_"
        if la_phan_he_cn(role):
            col_f, _ = st.columns([2, 4])
            with col_f:
                pgd_chon = st.selectbox(
                    "🔍 Lọc PGD",
                    ["Tất cả"] + DS_PGD,
                    key="qlnk_dash_pgd_loc",
                )
            if pgd_chon != "Tất cả" and COT_TEN_PGD in df_kh.columns:
                df_kh_view = df_kh[df_kh[COT_TEN_PGD] == pgd_chon].copy()
            else:
                df_kh_view = df_kh.copy()
        else:
            from data.pgd import pgd_slug
            key_prefix = f"pgd_{pgd_slug(pgd_user)}_"
            df_kh_view = df_kh.copy()

        c_pie, c_bar = st.columns([1, 1])

        with c_pie:
            st.markdown("#### 🥧 Lý do khoanh nợ")
            ly_do_series = _doc_ly_do_khoanh(df_kh_view)
            if ly_do_series is not None and not ly_do_series.empty:
                _pie_ly_do(ly_do_series, key=f"{key_prefix}qlnk_pie")
            else:
                st.info(
                    "Chưa có dữ liệu phân loại lý do khoanh. "
                    "Vào tab **🔒 Chuyên Đề Nợ Khoanh → Kế hoạch → Bổ sung** để nhập."
                )

        with c_bar:
            st.markdown("#### 📊 Dư nợ khoanh theo PGD")
            if df_kh_view.empty:
                st.info("Không có dữ liệu trong phạm vi đã chọn.")
            else:
                _bar_pgd(df_kh_view, key=f"{key_prefix}qlnk_bar")

        st.divider()

        st.markdown("#### 🔝 Top 10 món vay có dư nợ khoanh lớn nhất")

        cols_hien = [c for c in [
            COT_TEN_PGD, COT_TEN_XA, COT_TEN_KH, COT_SO_KU,
            COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH,
        ] if c in df_kh_view.columns]

        if cols_hien and not df_kh_view.empty:
            du_numeric = pd.to_numeric(
                df_kh_view[COT_DU_NO_KHOANH], errors="coerce"
            ).fillna(0)
            df_top = df_kh_view.loc[du_numeric.nlargest(10).index].copy()
            df_show = df_top[cols_hien].copy()

            if COT_DU_NO_KHOANH in df_show.columns:
                df_show[COT_DU_NO_KHOANH] = df_show[COT_DU_NO_KHOANH].apply(fmt_ty)

            st.dataframe(
                df_show,
                width='stretch',
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("Không đủ cột dữ liệu để hiển thị.")
