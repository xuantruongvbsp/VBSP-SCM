"""Phân tích Nợ Quá Hạn — PGD view."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit.delta_generator import DeltaGenerator

from config import (
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_TEN_XA, COT_TEN_CT,
    COT_TEN_KH, COT_SO_KU, COT_TEN_TO, COT_NGAY_VAY, COT_NGAY_DH,
    COT_MUC_VAY, COT_LAI_TON_QH,
)
from utils import fmt_ty, fmt_so, get_tab_context, hien_thi_dataframe_phan_trang


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df       = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")

    ctx = tab if tab is not None else st.container()
    with get_tab_context(ctx):
        st.subheader("📈 Phân tích Nợ Quá Hạn")
        st.caption(f"📍 Địa bàn: **{pgd_user}**")

        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        cot_nqh = COT_DU_NO_QH if COT_DU_NO_QH in df.columns else None
        cot_tdn = COT_TONG_DU_NO if COT_TONG_DU_NO in df.columns else None
        cot_xa  = COT_TEN_XA if COT_TEN_XA in df.columns else None
        cot_ct  = COT_TEN_CT if COT_TEN_CT in df.columns else None

        if cot_nqh is None:
            st.warning("⚠️ Không tìm thấy cột Dư nợ quá hạn.")
            return

        df_w = df.copy()
        df_w[cot_nqh] = pd.to_numeric(df_w[cot_nqh], errors="coerce").fillna(0)

        df_nqh = df_w[df_w[cot_nqh] > 0].copy()
        tong_nqh = df_w[cot_nqh].sum()

        if cot_tdn:
            df_w[cot_tdn] = pd.to_numeric(df_w[cot_tdn], errors="coerce").fillna(0)
            tong_dn = df_w[cot_tdn].sum()
            ty_le_nqh = (tong_nqh / tong_dn * 100) if tong_dn > 0 else 0.0
        else:
            tong_dn = 0.0
            ty_le_nqh = 0.0

        so_mon_nqh = len(df_nqh)
        tong_mon = len(df_w)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🔴 Tổng NQH", fmt_ty(tong_nqh))
        c2.metric("📊 Tỷ lệ NQH", f"{ty_le_nqh:.2f}%")
        c3.metric("📋 Số món NQH", fmt_so(so_mon_nqh))
        c4.metric("📁 Tổng món", fmt_so(tong_mon))

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            if cot_xa and not df_nqh.empty:
                st.markdown("**🏘️ NQH theo Xã/Phường**")
                nhom_xa = df_nqh.groupby(cot_xa)[cot_nqh].sum().sort_values(ascending=False)

                fig_xa = go.Figure(data=[go.Bar(
                    x=nhom_xa.values / 1e6,
                    y=nhom_xa.index.tolist(),
                    orientation="h",
                    marker_color="#C62828",
                    text=[f"{fmt_ty(v)} tr.đ" for v in nhom_xa.values],
                    textposition="outside",
                )])
                fig_xa.update_layout(
                    height=max(200, 40 * len(nhom_xa)),
                    margin=dict(l=0, r=60, t=10, b=0),
                    xaxis_title="Triệu đồng",
                )
                st.plotly_chart(fig_xa, use_container_width=True)

        with col_right:
            if cot_ct and not df_nqh.empty:
                st.markdown("**📌 NQH theo Chương trình**")
                nhom_ct = df_nqh.groupby(cot_ct)[cot_nqh].sum().sort_values(ascending=False)
                colors_ct = ["#C62828", "#E65100", "#F9A825", "#6A1B9A", "#1565C0",
                             "#00838F", "#2E7D32", "#4E342E", "#37474F", "#827717"]

                fig_ct = go.Figure(data=[go.Pie(
                    labels=nhom_ct.index.tolist(),
                    values=nhom_ct.values / 1e6,
                    hole=0.4,
                    marker=dict(colors=colors_ct[:len(nhom_ct)]),
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>%{value:,.0f} tr.đ<br>%{percent:.1f}%<extra></extra>",
                )])
                fig_ct.update_layout(
                    height=350,
                    margin=dict(l=0, r=0, t=10, b=0),
                    legend=dict(orientation="h", y=-0.1),
                )
                st.plotly_chart(fig_ct, use_container_width=True)

        st.divider()

        if not df_nqh.empty:
            st.markdown(f"**📋 Top {min(20, len(df_nqh))} món NQH lớn nhất**")

            cols_hien = [c for c in [
                COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_TEN_XA, COT_TEN_TO,
                COT_NGAY_VAY, COT_NGAY_DH, COT_MUC_VAY, cot_nqh, COT_LAI_TON_QH,
            ] if c in df_nqh.columns]

            df_top = df_nqh.sort_values(cot_nqh, ascending=False).head(20)
            df_show = df_top[cols_hien].copy()

            for c in [cot_nqh, COT_MUC_VAY]:
                if c in df_show.columns:
                    df_show[c] = pd.to_numeric(df_show[c], errors="coerce").fillna(0).apply(fmt_ty)
            if COT_LAI_TON_QH in df_show.columns:
                df_show[COT_LAI_TON_QH] = pd.to_numeric(df_show[COT_LAI_TON_QH], errors="coerce").fillna(0).apply(fmt_ty)

            hien_thi_dataframe_phan_trang(df_show, key="op_nqh_top", page_size=20)
        else:
            st.success("✅ PGD này không có Nợ quá hạn.")
