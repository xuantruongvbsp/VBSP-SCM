"""So sánh tăng trưởng & sức khỏe tín dụng giữa 22 PGD — stacked bar, scatter, bar NQH."""
from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from streamlit.delta_generator import DeltaGenerator

from config import COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_MA_KH
from utils import fmt_bang_ty, fmt_so, hien_thi_dataframe_phan_trang, xuat_excel, ten_file_xuat
from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from logger import get_logger

logger = get_logger(__name__)

_NGUONG_AN_TOAN  = 1.0   # % — xanh lá
_NGUONG_CANH_BAO = 2.0   # % — cam


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """So sánh Cơ cấu Dư nợ / Phân tích NQH / Tỷ lệ NQH theo PGD."""
    df_full = kwargs.get("df_full") or kwargs.get("df")

    ctx = tab if tab is not None else st.container()
    with ctx:
        if df_full is None:
            st.info("Chưa có dữ liệu.")
            return
        if COT_TEN_PGD not in df_full.columns:
            st.info("Không tìm thấy cột Tên PGD — không thể vẽ biểu đồ so sánh PGD.")
            return

        t_pgd = (
            df_full.groupby(COT_TEN_PGD)
            .agg(
                Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
                Dư_nợ_TH=(COT_DU_NO_TH, "sum"),
                NQH=(COT_DU_NO_QH, "sum"),
                Số_KH=(COT_MA_KH, "nunique"),
            )
            .reset_index()
        )
        t_pgd["TL_NQH"] = (t_pgd["NQH"] / t_pgd["Tổng_dư_nợ"] * 100).round(3).fillna(0)
        t_pgd["TL_TH"]  = (t_pgd["Dư_nợ_TH"] / t_pgd["Tổng_dư_nợ"] * 100).round(1).fillna(0)
        t_pgd["Trạng_thái"] = t_pgd["TL_NQH"].apply(
            lambda x: "🟢 An toàn" if x < _NGUONG_AN_TOAN
            else ("🟡 Cần theo dõi" if x < _NGUONG_CANH_BAO else "🔴 Nguy hiểm")
        )
        t_pgd_sorted = t_pgd.sort_values("Tổng_dư_nợ", ascending=True)

        st.markdown("## 📈 So Sánh Tăng Trưởng & Sức Khỏe Tín Dụng theo PGD")

        chart_tab_names = ["📊 Cơ cấu Dư nợ", "🎯 Phân tích NQH", "📉 Tỷ lệ NQH theo PGD"]
        nav_ex = "ws_executive_chart_tab"
        if nav_ex not in st.session_state or st.session_state[nav_ex] not in chart_tab_names:
            st.session_state[nav_ex] = chart_tab_names[0]
        st.radio(
            "Biểu đồ so sánh PGD", options=chart_tab_names,
            horizontal=True, key=nav_ex, label_visibility="collapsed",
        )
        _chart_active = st.session_state[nav_ex]
        st.divider()

        if _chart_active == chart_tab_names[0]:
            chieu_cao = max(350, len(t_pgd) * 44)
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                name="Dư nợ trong hạn",
                y=t_pgd_sorted[COT_TEN_PGD],
                x=t_pgd_sorted["Dư_nợ_TH"] / 1e6,
                orientation="h",
                marker_color="#1565C0",
                text=(t_pgd_sorted["Dư_nợ_TH"] / 1e6).apply(
                    lambda v: f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ),
                textposition="inside",
                insidetextanchor="middle",
                hovertemplate="<b>%{y}</b><br>Dư nợ trong hạn: %{x:,.0f} triệu đồng<extra></extra>",
            ))
            fig_bar.add_trace(go.Bar(
                name="Nợ quá hạn",
                y=t_pgd_sorted[COT_TEN_PGD],
                x=t_pgd_sorted["NQH"] / 1e6,
                orientation="h",
                marker_color="#C62828",
                text=(t_pgd_sorted["NQH"] / 1e6).apply(
                    lambda v: f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".") if v >= 1 else ""
                ),
                textposition="inside",
                hovertemplate="<b>%{y}</b><br>Nợ quá hạn: %{x:,.0f} triệu đồng<extra></extra>",
            ))
            fig_bar.update_layout(
                barmode="stack", height=chieu_cao,
                margin=dict(l=0, r=80, t=20, b=10),
                xaxis_title="Triệu đồng", yaxis=dict(title=""),
                legend=dict(orientation="h", y=1.04, x=0),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Arial",
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            st.caption("📌 Cột xanh = Dư nợ trong hạn · Cột đỏ = Nợ quá hạn. Sắp xếp theo Tổng dư nợ tăng dần.")

        elif _chart_active == chart_tab_names[1]:
            t_pgd_chart = t_pgd.copy()
            t_pgd_chart["Tổng_dư_nợ_tr"] = t_pgd_chart["Tổng_dư_nợ"] / 1e6
            fig_sc = px.scatter(
                t_pgd_chart, x="Tổng_dư_nợ_tr", y="TL_NQH",
                size="Số_KH", color="Trạng_thái", text=COT_TEN_PGD,
                color_discrete_map={
                    "🟢 An toàn": "#2e7d32", "🟡 Cần theo dõi": "#f57f17", "🔴 Nguy hiểm": "#c62828",
                },
                hover_data={COT_TEN_PGD: True, "Tổng_dư_nợ_tr": True, "Số_KH": True,
                            "TL_NQH": ":.3f", "Trạng_thái": True},
                labels={"Tổng_dư_nợ_tr": "Tổng dư nợ (triệu đồng)", "TL_NQH": "Tỷ lệ NQH (%)", "Số_KH": "Số khách hàng"},
            )
            fig_sc.add_hline(y=_NGUONG_AN_TOAN, line_dash="dash", line_color="#e65100", line_width=2,
                             annotation_text=f"⚠️ Ngưỡng an toàn {_NGUONG_AN_TOAN}%", annotation_position="bottom right")
            fig_sc.add_hline(y=_NGUONG_CANH_BAO, line_dash="dot", line_color="#c62828", line_width=1.5,
                             annotation_text=f"🚨 Ngưỡng cảnh báo {_NGUONG_CANH_BAO}%", annotation_position="top right")
            fig_sc.update_traces(textposition="top center", textfont_size=9,
                                 marker=dict(opacity=0.85, line=dict(width=1, color="white")))
            fig_sc.update_layout(
                height=420, margin=dict(l=0, r=20, t=20, b=10),
                xaxis=dict(title="Tổng dư nợ (triệu đồng)", tickformat=",.0f"),
                yaxis=dict(title="Tỷ lệ NQH (%)"),
                legend=dict(title="Trạng thái", orientation="h", y=-0.18),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Arial",
            )
            st.plotly_chart(fig_sc, use_container_width=True)
            st.caption("💡 Kích thước bong bóng = Số khách hàng. PGD lý tưởng nằm ở góc phải dưới (dư nợ cao, NQH thấp).")

        elif _chart_active == chart_tab_names[2]:
            t_nqh = t_pgd.sort_values("TL_NQH", ascending=True)
            mau_bars = [
                "#c62828" if v >= _NGUONG_CANH_BAO else ("#f57f17" if v >= _NGUONG_AN_TOAN else "#2e7d32")
                for v in t_nqh["TL_NQH"]
            ]
            fig_nqh = go.Figure(go.Bar(
                name="Tỷ lệ NQH", y=t_nqh[COT_TEN_PGD], x=t_nqh["TL_NQH"],
                orientation="h", marker_color=mau_bars,
                text=t_nqh["TL_NQH"].apply(lambda v: f"{v:.3f}%"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Tỷ lệ NQH: %{x:.3f}%<extra></extra>",
            ))
            fig_nqh.add_vline(x=_NGUONG_AN_TOAN, line_dash="dash", line_color="#e65100", line_width=2,
                              annotation_text=f"Ngưỡng {_NGUONG_AN_TOAN}%")
            fig_nqh.update_layout(
                height=max(350, len(t_nqh) * 44),
                margin=dict(l=0, r=80, t=20, b=10),
                xaxis=dict(title="Tỷ lệ NQH (%)", ticksuffix="%"),
                yaxis=dict(title=""),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Arial",
            )
            st.plotly_chart(fig_nqh, use_container_width=True)

        st.divider()
        with st.expander("📋 Bảng xếp hạng Sức khỏe Tín dụng theo PGD", expanded=False):
            df_xh = t_pgd.sort_values("Tổng_dư_nợ", ascending=False).reset_index(drop=True)
            df_xh.index += 1
            df_display = df_xh[[COT_TEN_PGD, "Tổng_dư_nợ", "Dư_nợ_TH", "NQH", "TL_NQH", "Số_KH", "TL_TH", "Trạng_thái"]].copy()
            df_display["Tổng_dư_nợ"] = df_display["Tổng_dư_nợ"].apply(fmt_bang_ty)
            df_display["Dư_nợ_TH"]   = df_display["Dư_nợ_TH"].apply(fmt_bang_ty)
            df_display["NQH"]         = df_display["NQH"].apply(fmt_bang_ty)
            df_display["TL_NQH"]      = df_display["TL_NQH"].apply(lambda x: f"{x:.3f}%")
            df_display["TL_TH"]       = df_display["TL_TH"].apply(lambda x: f"{x:.1f}%")
            df_display["Số_KH"]       = df_display["Số_KH"].apply(fmt_so)
            df_display.columns = [
                "PGD", "Tổng dư nợ (triệu đồng)", "Dư nợ trong hạn (triệu đồng)",
                "Nợ quá hạn (triệu đồng)", "Tỷ lệ NQH", "Số KH", "Tỷ lệ TH", "Trạng thái",
            ]
            hien_thi_dataframe_phan_trang(df_display, key="exec_suc_khoe_pgd", hide_index=False)

            kpi_suc_khoe = [
                ("Tổng PGD",    fmt_so(len(df_xh)),                      ""),
                ("Tổng dư nợ",  fmt_bang_ty(df_xh["Tổng_dư_nợ"].sum()), ""),
                ("Tổng NQH",    fmt_bang_ty(df_xh["NQH"].sum()),          ""),
                ("TL NQH b/q",  f"{df_xh['TL_NQH'].mean():.2f}%",        ""),
                ("Số KH vay",   fmt_so(df_xh["Số_KH"].sum()),             ""),
            ]
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("⬇️ Tạo Excel (chuyên nghiệp)", type="primary",
                             key="btn_gen_xls_sk_pgd_cn", use_container_width=True):
                    try:
                        st.session_state["_xls_sk_pgd_cn"] = xuat_excel_chuyen_nghiep(
                            df=df_display, title="Báo cáo Sức khỏe Tín dụng theo PGD",
                            subtitle="Phân hệ Chi nhánh",
                            nguoi_xuat=st.session_state.get("txt_username", ""),
                            kpi_items=kpi_suc_khoe,
                        )
                    except Exception as e:
                        logger.error("tab_so_sanh_suc_khoe_pgd xuat_excel: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất Excel: {e}")
                if st.session_state.get("_xls_sk_pgd_cn"):
                    st.download_button(
                        label="📥 Tải Excel (chuyên nghiệp)",
                        data=st.session_state["_xls_sk_pgd_cn"],
                        file_name=excel_ten_file("SucKhoe_PGD"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
            with col2:
                if st.button("⬇️ Tạo Excel (cơ bản)", key="btn_gen_xls_sk_pgd_basic", use_container_width=True):
                    try:
                        st.session_state["_xls_sk_pgd_basic"] = xuat_excel({"Sức khỏe PGD": df_display})
                    except Exception as e:
                        logger.error("tab_so_sanh_suc_khoe_pgd xuat_excel_basic: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất Excel: {e}")
                if st.session_state.get("_xls_sk_pgd_basic"):
                    st.download_button(
                        label="📥 Tải Excel (cơ bản)",
                        data=st.session_state["_xls_sk_pgd_basic"],
                        file_name=ten_file_xuat("SucKhoe_PGD"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
