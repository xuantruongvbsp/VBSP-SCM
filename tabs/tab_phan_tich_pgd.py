"""Phân tích PGD — Dự phóng dòng tiền + Heatmap đáo hạn + Histogram dư nợ + Donut cơ cấu CT."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date, datetime

import plotly.express as px
import plotly.graph_objects as go

from config import (
    COT_TEN_XA, COT_TEN_CT,
    COT_TONG_DU_NO, COT_DU_NO_TH,
    COT_NGAY_VAY, COT_NGAY_DH,
)
from utils import fmt_so, fmt_ty
from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from logger import get_logger

logger = get_logger(__name__)


def _render_du_phong(tab_parent, **kw) -> None:
    from services.du_phong_service import du_phong_dong_tien, du_phong_chi_tiet

    df_loc = kw.get("df")
    pgd = kw.get("pgd_user") or kw.get("pgd_filter") or ""

    st.subheader("📈 Dự phóng Doanh số & Kế hoạch Dòng tiền")

    if df_loc is None or df_loc.empty:
        st.info("Chưa có dữ liệu HSTD.")
        return

    if pgd:
        st.caption(f"📍 Địa bàn: **{pgd}**")

    hom_nay = datetime.now().date()
    thang_ht = date(hom_nay.year, hom_nay.month, 1)

    col_xa, col_ct = st.columns(2)
    with col_xa:
        ds_xa = ["Tất cả"] + sorted(df_loc[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df_loc.columns else ["Tất cả"]
        loc_xa = st.selectbox("🏘️ Xã", ds_xa, key="op_dp_xa")
    with col_ct:
        ds_ct = ["Tất cả"] + sorted(df_loc[COT_TEN_CT].dropna().unique().tolist()) if COT_TEN_CT in df_loc.columns else ["Tất cả"]
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

    c1, c2, c3 = st.columns(3)
    c1.metric("📊 Số tháng dự phóng", f"{len(df_dp)} tháng")
    c2.metric("✅ Đã qua (dự kiến)", fmt_ty(df_qua["du_kien_thu_goc"].sum() if not df_qua.empty else 0))
    c3.metric("🔮 Tương lai (dự kiến)", fmt_ty(df_lai["du_kien_thu_goc"].sum() if not df_lai.empty else 0))

    st.divider()
    st.markdown("**📊 Biểu đồ Dự phóng Dòng tiền theo tháng**")

    fig = go.Figure()
    if not df_qua.empty:
        fig.add_trace(go.Bar(x=df_qua["thang_label"], y=df_qua["du_kien_thu_goc_trieu"],
            name="Đã qua (dự kiến)", marker_color="#9e9e9e",
            hovertemplate="%{y:,.0f} triệu<extra></extra>"))
    if not df_lai.empty:
        fig.add_trace(go.Bar(x=df_lai["thang_label"], y=df_lai["du_kien_thu_goc_trieu"],
            name="Tương lai (dự kiến)", marker_color="#1565c0",
            hovertemplate="%{y:,.0f} triệu<extra></extra>"))

    fig.update_layout(barmode="stack", height=350, margin=dict(l=0, r=20, t=10, b=10),
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       font_family="Arial", xaxis=dict(title=""),
                       yaxis=dict(title="Triệu đồng", tickformat=",.0f"),
                       legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Xem bảng số liệu chi tiết", expanded=False):
        df_show = df_dp[["thang_label", "so_mon", "tong_du_no_trieu", "du_kien_thu_goc_trieu"]].copy()
        df_show.columns = ["Tháng", "Số món", "Tổng dư nợ (tr.đ)", "Dự kiến thu gốc (tr.đ)"]
        st.dataframe(df_show, hide_index=True, use_container_width=True)

    st.markdown("**🔍 Xem chi tiết tháng cụ thể**")
    thang_xem = st.selectbox("Chọn tháng", df_dp["thang_label"].tolist(), key="op_dp_thang_xem")
    thang_date = df_dp[df_dp["thang_label"] == thang_xem]["thang"].iloc[0]
    df_ct_detail = du_phong_chi_tiet(df_work, thang_date)
    if not df_ct_detail.empty:
        st.caption(f"**{len(df_ct_detail)}** khế ước có gốc đến hạn trong tháng {thang_xem}")
        cols_show = [c for c in ["ten_kh", "ten_xa", "ten_ct", "du_no_trieu", "goc_ht_trieu", "ngay_vay", "ngay_dh"]
                     if c in df_ct_detail.columns]
        df_ct_show = df_ct_detail[cols_show].copy()
        col_map = {"ten_kh": "Khách hàng", "ten_xa": "Xã", "ten_ct": "Chương trình",
                   "du_no_trieu": "Dư nợ (tr.đ)", "goc_ht_trieu": "Gốc/tháng (tr.đ)",
                   "ngay_vay": "Ngày vay", "ngay_dh": "Ngày ĐH"}
        df_ct_show = df_ct_show.rename(columns={k: v for k, v in col_map.items() if k in df_ct_show.columns})
        st.dataframe(df_ct_show, hide_index=True, use_container_width=True, height=300)
    else:
        st.info("Không có khế ước nào đến hạn thu gốc trong tháng này.")


def _render_heatmap(tab_parent, **kw) -> None:
    df_loc = kw.get("df")
    st.subheader("🔥 Heatmap Đáo hạn — Dư nợ đến hạn theo Tháng × Chương trình")

    if df_loc is None or df_loc.empty:
        st.info("Chưa có dữ liệu HSTD.")
        return

    hom_nay = datetime.now().date()
    cot_ngay = COT_NGAY_VAY if COT_NGAY_VAY in df_loc.columns else (COT_NGAY_DH if COT_NGAY_DH in df_loc.columns else None)
    if cot_ngay is None:
        st.warning("Không tìm thấy cột ngày vay/ngày ĐH.")
        return

    cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else COT_DU_NO_TH
    if cot_tien not in df_loc.columns:
        st.warning("Không tìm thấy cột dư nợ.")
        return

    df_hm = df_loc.copy()
    df_hm[cot_ngay] = pd.to_datetime(df_hm[cot_ngay], errors="coerce")
    df_hm = df_hm.dropna(subset=[cot_ngay])
    df_hm["thang_dh"] = df_hm[cot_ngay].dt.to_period("M").astype(str)
    df_hm["nam"] = df_hm[cot_ngay].dt.year.astype(int)

    nam_min = max(df_hm["nam"].min(), hom_nay.year - 1)
    nam_max = min(df_hm["nam"].max(), hom_nay.year + 2)
    df_loc_hm = df_hm[(df_hm["nam"] >= nam_min) & (df_hm["nam"] <= nam_max)].copy()
    if df_loc_hm.empty:
        st.info("Không có dữ liệu trong khoảng thời gian này.")
        return

    nhom_ct = COT_TEN_CT if COT_TEN_CT in df_loc_hm.columns else None
    if nhom_ct:
        pivot = df_loc_hm.pivot_table(index="thang_dh", columns=nhom_ct, values=cot_tien, aggfunc="sum").fillna(0)
    else:
        pivot = df_loc_hm.groupby("thang_dh")[cot_tien].sum().to_frame("Tổng")

    fig = px.imshow(
        pivot if nhom_ct else pivot.T,
        text_auto=".0f", aspect="auto", color_continuous_scale="YlOrRd",
        labels=dict(x="Chương trình" if nhom_ct else "", y="Tháng", color="Dư nợ (triệu)"),
        title="Dư nợ đến hạn theo Tháng × Chương trình",
    )
    fig.update_layout(height=max(350, len(pivot) * 40), margin=dict(l=0, r=0, t=40, b=0), font_family="Arial")
    if nhom_ct:
        fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Bảng số liệu", expanded=False):
        df_show = pivot.reset_index() if nhom_ct else pivot.reset_index()
        st.dataframe(df_show, hide_index=True, use_container_width=True)

    if not nhom_ct:
        st.caption("💡 Thêm dữ liệu cột Chương trình để xem heatmap chi tiết theo từng CT.")

    st.divider()
    if st.button("⬇️ Xuất Excel (chuyên nghiệp)", key="op_hm_xuat", type="primary"):
        st.download_button(
            label="⬇️ Xuất Excel",
            type="primary",
            data=xuat_excel_chuyen_nghiep(
                df=df_show, title="Heatmap Đáo hạn",
                subtitle=f"Kỳ: {nam_min}-{nam_max}",
                nguoi_xuat=st.session_state.get("txt_username", ""),
                kpi_items=[
                    ("Tổng số tháng", fmt_so(len(pivot)), ""),
                    ("Dư nợ b/q tháng", fmt_ty(pivot.values.mean()), "triệu đồng"),
                ],
            ),
            file_name=excel_ten_file("Heatmap_DaoHan"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def _render_histogram(tab_parent, **kw) -> None:
    df_loc = kw.get("df")
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
    fig = px.histogram(df_hist, x=cot_tien, nbins=bins,
                        labels={cot_tien: "Dư nợ (đồng)"},
                        title="Phân bố dư nợ", color_discrete_sequence=["#2E7D32"])
    fig.update_layout(height=400, margin=dict(l=0, r=20, t=40, b=0), font_family="Arial",
                       xaxis=dict(tickformat=",.0f"), yaxis=dict(title="Số khoản vay"), bargap=0.05)
    fig.add_vline(x=df_hist[cot_tien].median(), line_dash="dash", line_color="#C62828",
                  annotation_text=f"Trung vị: {df_hist[cot_tien].median():,.0f}")
    st.plotly_chart(fig, use_container_width=True)

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.metric("Trung bình", fmt_ty(df_hist[cot_tien].mean()))
    with col_s2:
        st.metric("Trung vị", fmt_ty(df_hist[cot_tien].median()))
    with col_s3:
        st.metric("Tổng số khoản", fmt_so(len(df_hist)))


def _render_donut(tab_parent, **kw) -> None:
    df_loc = kw.get("df")
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
    top_n = st.slider("Hiển thị Top N chương trình", min_value=3, max_value=10, value=5, key="op_donut_top")
    ct_show = ct_group.head(top_n)
    ct_others = ct_group.iloc[top_n:].sum() if len(ct_group) > top_n else 0

    labels = list(ct_show.index)
    values = [v / 1e6 for v in ct_show.values]
    if ct_others > 0:
        labels.append("Khác")
        values.append(ct_others / 1e6)

    colors = ["#2E7D32", "#1565C0", "#F9A825", "#C62828", "#6A1B9A",
              "#00838F", "#E65100", "#4E342E", "#37474F", "#827717"]

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.4,
        marker=dict(colors=colors[:len(labels)]),
        textinfo="label+percent", texttemplate="%{label}<br>%{percent:.1f}%",
        hovertemplate="<b>%{label}</b><br>Dư nợ: %{value:,.0f} tr.đ<br>Tỷ trọng: %{percent:.1f}%<extra></extra>",
    )])
    fig.update_layout(height=450, margin=dict(l=0, r=0, t=10, b=0),
                       font_family="Arial", legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Bảng số liệu", expanded=False):
        df_ct = ct_group.reset_index()
        df_ct.columns = ["Chương trình", "Dư nợ (đồng)"]
        df_ct["Dư nợ (triệu)"] = (df_ct["Dư nợ (đồng)"] / 1e6).round(1)
        df_ct["Tỷ trọng %"] = (df_ct["Dư nợ (đồng)"] / df_ct["Dư nợ (đồng)"].sum() * 100).round(1)
        st.dataframe(df_ct, hide_index=True, use_container_width=True)


def render(tab=None, **kwargs) -> None:
    sub_tabs = st.tabs(["📈 Dự phóng", "🔥 Heatmap", "📊 Histogram", "🍩 Cơ cấu CT"])
    with sub_tabs[0]:
        _render_du_phong(sub_tabs[0], **kwargs)
    with sub_tabs[1]:
        _render_heatmap(sub_tabs[1], **kwargs)
    with sub_tabs[2]:
        _render_histogram(sub_tabs[2], **kwargs)
    with sub_tabs[3]:
        _render_donut(sub_tabs[3], **kwargs)
