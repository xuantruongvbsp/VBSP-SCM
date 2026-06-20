"""Heatmap Đáo hạn — dư nợ đến hạn theo Tháng × Chương trình, phạm vi PGD."""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit.delta_generator import DeltaGenerator

from config import COT_NGAY_VAY, COT_NGAY_DH, COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT
from utils import fmt_so, fmt_ty
from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Heatmap đáo hạn: pivot Tháng × Chương trình."""
    df_loc = kwargs.get("df")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🔥 Heatmap Đáo hạn — Dư nợ đến hạn theo Tháng × Chương trình")

        if df_loc is None or df_loc.empty:
            st.info("Chưa có dữ liệu HSTD.")
            return

        hom_nay  = datetime.now().date()
        thang_ht = date(hom_nay.year, hom_nay.month, 1)

        cot_ngay_vay = COT_NGAY_VAY if COT_NGAY_VAY in df_loc.columns else (COT_NGAY_DH if COT_NGAY_DH in df_loc.columns else None)
        if cot_ngay_vay is None:
            st.warning("Không tìm thấy cột ngày vay/ngày ĐH để tính đáo hạn.")
            return

        cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else COT_DU_NO_TH
        if cot_tien not in df_loc.columns:
            st.warning("Không tìm thấy cột dư nợ để tính.")
            return

        df_hm = df_loc.copy()
        df_hm[cot_ngay_vay] = pd.to_datetime(df_hm[cot_ngay_vay], errors="coerce")
        df_hm = df_hm.dropna(subset=[cot_ngay_vay])

        df_hm["thang_dh"] = df_hm[cot_ngay_vay].dt.to_period("M").astype(str)
        df_hm["nam"]      = df_hm[cot_ngay_vay].dt.year.astype(int)

        nam_min = max(df_hm["nam"].min(), hom_nay.year - 1)
        nam_max = min(df_hm["nam"].max(), hom_nay.year + 2)

        df_loc_hm = df_hm[(df_hm["nam"] >= nam_min) & (df_hm["nam"] <= nam_max)].copy()
        if df_loc_hm.empty:
            st.info("Không có dữ liệu trong khoảng thời gian này.")
            return

        nhom_ct = COT_TEN_CT if COT_TEN_CT in df_loc_hm.columns else None

        if nhom_ct:
            pivot = df_loc_hm.pivot_table(
                index="thang_dh", columns=nhom_ct, values=cot_tien, aggfunc="sum"
            ).fillna(0)
        else:
            pivot = df_loc_hm.groupby("thang_dh")[cot_tien].sum().to_frame("Tổng")

        fig = px.imshow(
            pivot if nhom_ct else pivot.T,
            text_auto=".0f",
            aspect="auto",
            color_continuous_scale="YlOrRd",
            labels=dict(x="Chương trình" if nhom_ct else "", y="Tháng", color="Dư nợ (triệu)"),
            title="Dư nợ đến hạn theo Tháng × Chương trình",
        )
        fig.update_layout(
            height=max(350, len(pivot) * 40),
            margin=dict(l=0, r=0, t=40, b=0),
            font_family="Arial",
        )
        if nhom_ct:
            fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 Bảng số liệu", expanded=False):
            df_show = pivot.reset_index()
            st.dataframe(df_show, hide_index=True, use_container_width=True)

        if not nhom_ct:
            st.caption("💡 Thêm dữ liệu cột Chương trình để xem heatmap chi tiết theo từng CT.")

        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⬇️ Tạo Excel (chuyên nghiệp)", type="primary",
                         key="op_hm_btn_gen_excel", use_container_width=True):
                try:
                    st.session_state["_xls_ws_heatmap_daohn"] = xuat_excel_chuyen_nghiep(
                        df=df_show,
                        title="Heatmap Đáo hạn",
                        subtitle=f"Kỳ: {nam_min}-{nam_max}",
                        nguoi_xuat=st.session_state.get("txt_username", ""),
                        kpi_items=[
                            ("Tổng số tháng",     fmt_so(len(pivot)),             ""),
                            ("Dư nợ b/q tháng",   fmt_ty(pivot.values.mean()),    "triệu đồng"),
                        ],
                    )
                except Exception as e:
                    logger.error("tab_heatmap_dao_han xuat_excel: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất Excel: {e}")
            if st.session_state.get("_xls_ws_heatmap_daohn"):
                st.download_button(
                    label="📥 Tải Excel (chuyên nghiệp)",
                    data=st.session_state["_xls_ws_heatmap_daohn"],
                    file_name=excel_ten_file("Heatmap_DaoHan"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="op_hm_dl_excel",
                )
