"""Dự phóng Doanh số & Kế hoạch Dòng tiền — phạm vi 1 PGD."""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit.delta_generator import DeltaGenerator

from config import COT_TEN_XA, COT_TEN_CT
from utils import fmt_ty, fmt_so
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Dự phóng dòng tiền thu gốc theo từng tháng."""
    from services.du_phong_service import du_phong_dong_tien, du_phong_chi_tiet

    df_loc = kwargs.get("df")
    pgd    = kwargs.get("pgd_user") or kwargs.get("pgd_filter") or ""

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📈 Dự phóng Doanh số & Kế hoạch Dòng tiền")

        if df_loc is None or df_loc.empty:
            st.info("Chưa có dữ liệu HSTD.")
            return

        if pgd:
            st.caption(f"📍 Địa bàn: **{pgd}**")

        hom_nay  = datetime.now().date()
        thang_ht = date(hom_nay.year, hom_nay.month, 1)

        col_xa, col_ct = st.columns(2)
        with col_xa:
            ds_xa  = ["Tất cả"] + sorted(df_loc[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df_loc.columns else ["Tất cả"]
            loc_xa = st.selectbox("🏘️ Xã", ds_xa, key="op_dp_xa")
        with col_ct:
            ds_ct  = ["Tất cả"] + sorted(df_loc[COT_TEN_CT].dropna().unique().tolist()) if COT_TEN_CT in df_loc.columns else ["Tất cả"]
            loc_ct = st.selectbox("📌 Chương trình", ds_ct, key="op_dp_ct")

        df_work = df_loc.copy()
        if loc_xa != "Tất cả" and COT_TEN_XA in df_work.columns:
            df_work = df_work[df_work[COT_TEN_XA] == loc_xa]
        if loc_ct != "Tất cả" and COT_TEN_CT in df_work.columns:
            df_work = df_work[df_work[COT_TEN_CT] == loc_ct]

        if df_work.empty:
            st.info("Không có dữ liệu phù hợp với bộ lọc.")
            return

        df_dp = du_phong_dong_tien(df_work)

        if df_dp.empty:
            st.warning("⚠️ Không đủ dữ liệu Ngày vay / Ngày ĐH để dự phóng.")
            return

        df_qua = df_dp[df_dp["thang"] < thang_ht].copy()
        df_lai = df_dp[df_dp["thang"] >= thang_ht].copy()

        tong_goc_qua = df_qua["du_kien_thu_goc"].sum() if not df_qua.empty else 0
        tong_goc_lai = df_lai["du_kien_thu_goc"].sum() if not df_lai.empty else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("📊 Số tháng dự phóng", f"{len(df_dp)} tháng")
        c2.metric("✅ Đã qua (dự kiến)",   fmt_ty(tong_goc_qua))
        c3.metric("🔮 Tương lai (dự kiến)", fmt_ty(tong_goc_lai))

        st.divider()
        st.markdown("**📊 Biểu đồ Dự phóng Dòng tiền theo tháng**")

        fig = go.Figure()
        if not df_qua.empty:
            fig.add_trace(go.Bar(
                x=df_qua["thang_label"],
                y=df_qua["du_kien_thu_goc_trieu"],
                name="Đã qua (dự kiến)",
                marker_color="#9e9e9e",
                hovertemplate="%{y:,.0f} triệu<extra></extra>",
            ))
        if not df_lai.empty:
            fig.add_trace(go.Bar(
                x=df_lai["thang_label"],
                y=df_lai["du_kien_thu_goc_trieu"],
                name="Tương lai (dự kiến)",
                marker_color="#1565c0",
                hovertemplate="%{y:,.0f} triệu<extra></extra>",
            ))
        fig.update_layout(
            barmode="stack",
            height=350,
            margin=dict(l=0, r=20, t=10, b=10),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_family="Arial",
            xaxis=dict(title=""),
            yaxis=dict(title="Triệu đồng", tickformat=",.0f"),
            legend=dict(orientation="h", y=1.08),
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 Xem bảng số liệu chi tiết", expanded=False):
            df_show = df_dp[["thang_label", "so_mon", "tong_du_no_trieu", "du_kien_thu_goc_trieu"]].copy()
            df_show.columns = ["Tháng", "Số món", "Tổng dư nợ (tr.đ)", "Dự kiến thu gốc (tr.đ)"]
            st.dataframe(df_show, hide_index=True, use_container_width=True)

        st.markdown("**🔍 Xem chi tiết tháng cụ thể**")
        thang_xem  = st.selectbox("Chọn tháng", df_dp["thang_label"].tolist(), key="op_dp_thang_xem")
        thang_date = df_dp[df_dp["thang_label"] == thang_xem]["thang"].iloc[0]

        df_ct_detail = du_phong_chi_tiet(df_work, thang_date)
        if not df_ct_detail.empty:
            st.caption(f"**{len(df_ct_detail)}** khế ước có gốc đến hạn trong tháng {thang_xem}")
            cols_show = [c for c in ["ten_kh", "ten_xa", "ten_ct", "du_no_trieu", "goc_ht_trieu", "ngay_vay", "ngay_dh"]
                         if c in df_ct_detail.columns]
            df_ct_show = df_ct_detail[cols_show].copy()
            col_map = {
                "ten_kh": "Khách hàng", "ten_xa": "Xã", "ten_ct": "Chương trình",
                "du_no_trieu": "Dư nợ (tr.đ)", "goc_ht_trieu": "Gốc/tháng (tr.đ)",
                "ngay_vay": "Ngày vay", "ngay_dh": "Ngày ĐH",
            }
            df_ct_show = df_ct_show.rename(columns={k: v for k, v in col_map.items() if k in df_ct_show.columns})
            st.dataframe(df_ct_show, hide_index=True, use_container_width=True, height=300)
        else:
            st.info("Không có khế ước nào đến hạn thu gốc trong tháng này.")
