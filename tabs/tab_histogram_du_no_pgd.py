"""Histogram — phân bố dư nợ theo khoản vay, phạm vi 1 PGD."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit.delta_generator import DeltaGenerator

from config import COT_TONG_DU_NO, COT_DU_NO_TH
from utils import fmt_ty, fmt_so
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Histogram phân bố dư nợ từng khoản vay."""
    df_loc = kwargs.get("df")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📊 Histogram — Phân bố Dư nợ theo Khoản vay")

        if df_loc is None or df_loc.empty:
            st.info("Chưa có dữ liệu HSTD.")
            return

        cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else (COT_DU_NO_TH if COT_DU_NO_TH in df_loc.columns else None)
        if cot_tien is None:
            st.warning("Không tìm thấy cột dư nợ.")
            return

        df_hist = df_loc.copy()
        df_hist[cot_tien] = pd.to_numeric(df_hist[cot_tien], errors="coerce").fillna(0)
        df_hist = df_hist[df_hist[cot_tien] > 0]

        if df_hist.empty:
            st.info("Không có dữ liệu dư nợ dương.")
            return

        bins = st.slider("Số khoảng (bins)", min_value=5, max_value=50, value=20, key="op_hist_bins")

        fig = px.histogram(
            df_hist,
            x=cot_tien,
            nbins=bins,
            labels={cot_tien: "Dư nợ (đồng)"},
            title="Phân bố dư nợ",
            color_discrete_sequence=["#2E7D32"],
        )
        fig.update_layout(
            height=400,
            margin=dict(l=0, r=20, t=40, b=0),
            font_family="Arial",
            xaxis=dict(tickformat=",.0f"),
            yaxis=dict(title="Số khoản vay"),
            bargap=0.05,
        )
        fig.add_vline(
            x=df_hist[cot_tien].median(),
            line_dash="dash",
            line_color="#C62828",
            annotation_text=f"Trung vị: {df_hist[cot_tien].median():,.0f}",
        )
        st.plotly_chart(fig, use_container_width=True)

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("Trung bình", fmt_ty(df_hist[cot_tien].mean()), help="Dư nợ bình quân/khoản")
        with col_s2:
            st.metric("Trung vị",   fmt_ty(df_hist[cot_tien].median()), help="Dư nợ trung vị")
        with col_s3:
            st.metric("Tổng số khoản", fmt_so(len(df_hist)), help="Số khoản vay có dư nợ")
