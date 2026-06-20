"""Donut chart — cơ cấu dư nợ theo chương trình tín dụng, phạm vi PGD."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit.delta_generator import DeltaGenerator

from config import COT_TEN_CT, COT_TONG_DU_NO, COT_DU_NO_TH
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Donut cơ cấu dư nợ — Top N chương trình."""
    df_loc = kwargs.get("df")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🍩 Donut — Cơ cấu Dư nợ theo Chương trình")

        if df_loc is None or df_loc.empty:
            st.info("Chưa có dữ liệu HSTD.")
            return

        nhom_ct = COT_TEN_CT if COT_TEN_CT in df_loc.columns else None
        if nhom_ct is None:
            st.warning("Không tìm thấy cột Chương trình.")
            return

        cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else (COT_DU_NO_TH if COT_DU_NO_TH in df_loc.columns else None)
        if cot_tien is None:
            st.warning("Không tìm thấy cột dư nợ.")
            return

        df_donut = df_loc.copy()
        df_donut[cot_tien] = pd.to_numeric(df_donut[cot_tien], errors="coerce").fillna(0)
        df_donut = df_donut[df_donut[cot_tien] > 0]

        if df_donut.empty:
            st.info("Không có dữ liệu dư nợ dương.")
            return

        ct_group = df_donut.groupby(nhom_ct)[cot_tien].sum().sort_values(ascending=False)

        top_n    = st.slider("Hiển thị Top N chương trình", min_value=3, max_value=10, value=5, key="op_donut_top")
        ct_show  = ct_group.head(top_n)
        ct_others = ct_group.iloc[top_n:].sum() if len(ct_group) > top_n else 0

        labels = list(ct_show.index)
        values = [v / 1e6 for v in ct_show.values]
        if ct_others > 0:
            labels.append("Khác")
            values.append(ct_others / 1e6)

        colors = ["#2E7D32", "#1565C0", "#F9A825", "#C62828", "#6A1B9A",
                  "#00838F", "#E65100", "#4E342E", "#37474F", "#827717"]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(colors=colors[:len(labels)]),
            textinfo="label+percent",
            texttemplate="%{label}<br>%{percent:.1f}%",
            hovertemplate="<b>%{label}</b><br>Dư nợ: %{value:,.0f} tr.đ<br>Tỷ trọng: %{percent:.1f}%<extra></extra>",
        )])
        fig.update_layout(
            height=450,
            margin=dict(l=0, r=0, t=10, b=0),
            font_family="Arial",
            legend=dict(orientation="h", y=-0.1),
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 Bảng số liệu", expanded=False):
            df_ct = ct_group.reset_index()
            df_ct.columns = ["Chương trình", "Dư nợ (đồng)"]
            df_ct["Dư nợ (triệu)"] = (df_ct["Dư nợ (đồng)"] / 1e6).round(1)
            df_ct["Tỷ trọng %"]    = (df_ct["Dư nợ (đồng)"] / df_ct["Dư nợ (đồng)"].sum() * 100).round(1)
            st.dataframe(df_ct, hide_index=True, use_container_width=True)
