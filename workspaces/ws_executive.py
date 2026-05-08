"""
Không gian Lãnh đạo (Executive View)
────────────────────────────────────
Dành cho Ban Giám đốc — Dashboard vĩ mô "Sức Khỏe Tín Dụng" toàn chi nhánh:
  • Đồng hồ đo Tỷ lệ NQH (gauge Plotly)
  • KPI tổng hợp: Tổng dư nợ, NQH, số khách hàng
  • Biểu đồ tăng trưởng & so sánh sức khỏe giữa các Phòng giao dịch
  • Tiến độ kế hoạch, cảnh báo NQH đột biến theo Xã, cảnh báo migration
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

from config import (
    COT_TEN_PGD, COT_MA_KH, COT_SO_KU, COT_TEN_KH,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT,
    COT_NGAY_SL, DB_HT_CACHE, DB_PREV_CACHE, FILE_PATH_DB, FILE_PATH_DB_PREV,
    NAM_HT, NAM_PREV, COT_LAI_TON,
)
from data import (doc_dienbao, db_lookup, db_nqh_con, ts_file, doc_kehoach,
                  danh_dau_khong_hd, tong_hop_khong_hd, canh_bao_migration)
from utils import (
    fmt,
    fmt_tien,
    fmt_ty,
    fmt_pct,
    fmt_so,
    hien_thi_dataframe_phan_trang,
    xuat_excel,
    ten_file_xuat,
)
from tabs import tab_khtd_giao_dc, tab_kiem_soat, tab_no_rui_ro

# ── Hằng số ngưỡng NQH ────────────────────────────────────────────────────────
_NGUONG_AN_TOAN  = 1.0   # % — xanh lá
_NGUONG_CANH_BAO = 2.0   # % — cam
# Ngưỡng cảnh báo xã
_NGUONG_XA_NQH   = 1.0

# Tên cột xã — hằng số cục bộ, không dùng tên trùng với config
_COT_XA = "Tên xã"


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER — Format nội bộ
# ═══════════════════════════════════════════════════════════════════════════════
def _fmt(v) -> str:
    """Format số tiền (đồng) → tỷ/triệu ngắn gọn dùng trong bảng (chuẩn VN: . nghìn, , thập phân)."""
    try:
        v = float(v)
        if abs(v) >= 1e9:
            s = f"{v/1e9:,.3f}".replace(",","X").replace(".",",").replace("X",".")
            return f"{s.rstrip('0').rstrip(',')} tỷ"
        if abs(v) >= 1e6:
            s = f"{v/1e6:,.1f}".replace(",","X").replace(".",",").replace("X",".")
            return f"{s} tr"
        return f"{v:,.0f}".replace(",",".")
    except Exception:
        return "—"


def _mau_nqh(tlqh: float) -> tuple[str, str, str]:
    """Trả về (màu_hex, nhãn_trạng_thái, icon) theo mức NQH."""
    if tlqh < _NGUONG_AN_TOAN:
        return "#2e7d32", "AN TOÀN", "✅"
    if tlqh < _NGUONG_CANH_BAO:
        return "#f57f17", "CẦN THEO DÕI", "⚠️"
    return "#c62828", "VƯỢT NGƯỠNG", "🚨"


# ═══════════════════════════════════════════════════════════════════════════════
# GAUGE — Đồng hồ đo Tỷ lệ NQH Toàn Tỉnh
# ═══════════════════════════════════════════════════════════════════════════════
def _gauge_nqh(tlqh: float) -> go.Figure:
    """
    Tạo biểu đồ đồng hồ đo (Gauge + Number) Tỷ lệ NQH.
    Vùng màu: xanh [0–1%] | cam [1–2%] | đỏ [2–5%].
    """
    mau, tinh_trang, _ = _mau_nqh(tlqh)
    gio_han = 5.0  # Trục gauge tối đa 5%

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(tlqh, 3),
        number={
            "suffix": "%",
            "font": {"size": 40, "color": mau, "family": "Arial"},
            "valueformat": ".3f",
        },
        delta={
            "reference": _NGUONG_AN_TOAN,
            "increasing": {"color": "#c62828"},
            "decreasing": {"color": "#2e7d32"},
            "suffix": "% so ngưỡng",
            "valueformat": ".3f",
        },
        gauge={
            "axis": {
                "range": [0, gio_han],
                "tickwidth": 1,
                "tickcolor": "#666",
                "ticksuffix": "%",
                "nticks": 6,
            },
            "bar": {"color": mau, "thickness": 0.28},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, _NGUONG_AN_TOAN],  "color": "rgba(46,125,50,0.12)"},
                {"range": [_NGUONG_AN_TOAN, _NGUONG_CANH_BAO], "color": "rgba(245,127,23,0.12)"},
                {"range": [_NGUONG_CANH_BAO, gio_han], "color": "rgba(198,40,40,0.12)"},
            ],
            "threshold": {
                "line": {"color": "#e65100", "width": 3},
                "thickness": 0.82,
                "value": _NGUONG_AN_TOAN,
            },
        },
        title={
            "text": (
                f"Tỷ lệ NQH Toàn Tỉnh<br>"
                f"<span style='font-size:14px;color:{mau};font-weight:bold'>"
                f"{tinh_trang}</span>"
            ),
            "font": {"size": 16},
        },
    ))
    fig.update_layout(
        height=270,
        margin=dict(l=20, r=20, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="Arial",
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# FRAGMENTS — Gauge / KPI (rerun độc lập khi tương tác widget bên trong)
# ═══════════════════════════════════════════════════════════════════════════════
@st.fragment
def _render_gauge_du_no(**kwargs) -> None:
    """Đồng hồ đo Tỷ lệ NQH (gauge Plotly)."""
    tlqh = kwargs["tlqh"]
    st.plotly_chart(_gauge_nqh(tlqh), use_container_width=True)


@st.fragment
def _render_metric_cards(**kwargs) -> None:
    """Metric cards + thanh tiến trình sức khỏe tín dụng."""
    tdn = kwargs["tdn"]
    dth = kwargs["dth"]
    dqh = kwargs["dqh"]
    tlqh = kwargs["tlqh"]
    n_hs = kwargs["n_hs"]
    n_kh = kwargs["n_kh"]
    mau = kwargs["mau"]
    tinh_trang = kwargs["tinh_trang"]
    icon = kwargs["icon"]

    st.markdown(f"### {icon} Chỉ số Tín dụng")
    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)

    r1c1.metric(
        label="💰 Tổng dư nợ",
        value=fmt_tien(tdn),
    )
    r1c2.metric(
        label="✅ Dư nợ trong hạn",
        value=fmt_tien(dth),
        help="Dư nợ chưa đến hạn thanh toán",
    )
    r2c1.metric(
        label="⚠️ Nợ quá hạn",
        value=fmt_ty(dqh),
        delta=(f"{icon} {tinh_trang}" if dqh > 0 else "✅ Không có NQH"),
        delta_color="inverse" if tlqh >= _NGUONG_AN_TOAN else "normal",
    )
    r2c2.metric(
        label="👥 Số khách hàng",
        value=fmt_so(n_kh),
        help=f"Tổng {fmt_so(n_hs)} hồ sơ trong hệ thống",
    )

    st.markdown("---")
    pct_th = dth / tdn * 100 if tdn > 0 else 100
    st.markdown(
        f"**Tỷ lệ Dư nợ trong hạn:** "
        f"<span style='color:#1565C0;font-weight:bold'>{pct_th:.1f}%</span> "
        f"&nbsp;|&nbsp; **NQH:** "
        f"<span style='color:{mau};font-weight:bold'>{tlqh:.3f}%</span>",
        unsafe_allow_html=True,
    )
    st.progress(
        min(pct_th / 100, 1.0),
        text=f"Sức khỏe: {pct_th:.1f}% dư nợ đang trong hạn",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Sức Khỏe Tín Dụng (Gauge + KPI tổng hợp)
# ═══════════════════════════════════════════════════════════════════════════════
def _the_suc_khoe(df_full: pd.DataFrame) -> None:
    """
    Hiển thị section 'Sức Khỏe Tín Dụng' gồm:
      • Đồng hồ đo NQH (gauge)
      • 4 KPI chính được format bằng utils.py
      • Thanh chỉ số sức khỏe tổng hợp
    """
    st.markdown("## 🏥 Sức Khỏe Tín Dụng — Toàn Chi Nhánh")

    # Tính chỉ số
    tdn  = df_full[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_full.columns else 0
    dth  = df_full[COT_DU_NO_TH].sum()   if COT_DU_NO_TH   in df_full.columns else 0
    dqh  = df_full[COT_DU_NO_QH].sum()   if COT_DU_NO_QH   in df_full.columns else 0
    tlqh = dqh / tdn * 100 if tdn > 0 else 0.0
    n_hs = len(df_full)
    n_kh = df_full[COT_MA_KH].nunique() if COT_MA_KH in df_full.columns else 0

    mau, tinh_trang, icon = _mau_nqh(tlqh)

    col_gauge, col_kpi = st.columns([2, 3], gap="large")

    with col_gauge:
        _render_gauge_du_no(tlqh=tlqh)

    with col_kpi:
        _render_metric_cards(
            tdn=tdn,
            dth=dth,
            dqh=dqh,
            tlqh=tlqh,
            n_hs=n_hs,
            n_kh=n_kh,
            mau=mau,
            tinh_trang=tinh_trang,
            icon=icon,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Biểu đồ Tăng Trưởng & So Sánh Sức Khỏe Tín Dụng theo PGD
# ═══════════════════════════════════════════════════════════════════════════════
@st.fragment
def _render_heatmap_pgd(**kwargs) -> None:
    """
    Biểu đồ so sánh dư nợ và sức khỏe tín dụng giữa các PGD:
      • Stacked Bar: Dư nợ trong hạn + NQH theo PGD (sắp xếp giảm dần)
      • Scatter: Tổng dư nợ (x) vs Tỷ lệ NQH (y), kích thước = số KH
      • Bảng xếp hạng đầy đủ (expander)
    """
    df_full = kwargs.get("df_full")
    if df_full is None:
        return
    if COT_TEN_PGD not in df_full.columns:
        st.info("Không tìm thấy cột Tên PGD — không thể vẽ biểu đồ so sánh PGD.")
        return

    # Tổng hợp theo PGD
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
    # Sắp xếp tăng dần để bar nằm ngang hiển thị đẹp
    t_pgd_sorted = t_pgd.sort_values("Tổng_dư_nợ", ascending=True)

    st.markdown("## 📈 So Sánh Tăng Trưởng & Sức Khỏe Tín Dụng theo PGD")

    chart_tab_names = ["📊 Cơ cấu Dư nợ", "🎯 Phân tích NQH", "📉 Tỷ lệ NQH theo PGD"]
    nav_ex = "ws_executive_chart_tab"
    if nav_ex not in st.session_state or st.session_state[nav_ex] not in chart_tab_names:
        st.session_state[nav_ex] = chart_tab_names[0]
    st.radio(
        "Biểu đồ so sánh PGD",
        options=chart_tab_names,
        horizontal=True,
        key=nav_ex,
        label_visibility="collapsed",
    )
    _chart_active = st.session_state[nav_ex]
    st.divider()

    # ── TAB 1: Stacked Bar Dư nợ ──────────────────────────────────────────────
    if _chart_active == chart_tab_names[0]:
        chieu_cao = max(350, len(t_pgd) * 44)
        fig_bar = go.Figure()

        fig_bar.add_trace(go.Bar(
            name="Dư nợ trong hạn",
            y=t_pgd_sorted[COT_TEN_PGD],
            x=t_pgd_sorted["Dư_nợ_TH"] / 1e9,
            orientation="h",
            marker_color="#1565C0",
            text=(t_pgd_sorted["Dư_nợ_TH"] / 1e9).apply(
                lambda v: f"{v:,.2f}".replace(",","X").replace(".",",").replace("X",".") + " tỷ"
            ),
            textposition="inside",
            insidetextanchor="middle",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Dư nợ trong hạn: %{x:,.3f} tỷ<extra></extra>"
            ),
        ))
        fig_bar.add_trace(go.Bar(
            name="Nợ quá hạn",
            y=t_pgd_sorted[COT_TEN_PGD],
            x=t_pgd_sorted["NQH"] / 1e9,
            orientation="h",
            marker_color="#C62828",
            text=(t_pgd_sorted["NQH"] / 1e9).apply(
                lambda v: (
                    f"{v:,.3f}".replace(",","X").replace(".",",").replace("X",".") + " tỷ"
                    if v >= 1e-3 else ""
                )
            ),
            textposition="inside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Nợ quá hạn: %{x:,.3f} tỷ<extra></extra>"
            ),
        ))
        fig_bar.update_layout(
            barmode="stack",
            height=chieu_cao,
            margin=dict(l=0, r=80, t=20, b=10),
            xaxis_title="Tỷ đồng",
            yaxis=dict(title=""),
            legend=dict(orientation="h", y=1.04, x=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_family="Arial",
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        st.caption(
            "📌 Cột xanh = Dư nợ trong hạn · Cột đỏ = Nợ quá hạn. "
            "Sắp xếp theo Tổng dư nợ tăng dần."
        )

    # ── TAB 2: Scatter Tổng dư nợ vs NQH ────────────────────────────────────
    elif _chart_active == chart_tab_names[1]:
        fig_sc = px.scatter(
            t_pgd,
            x="Tổng_dư_nợ",
            y="TL_NQH",
            size="Số_KH",
            color="Trạng_thái",
            text=COT_TEN_PGD,
            color_discrete_map={
                "🟢 An toàn":      "#2e7d32",
                "🟡 Cần theo dõi": "#f57f17",
                "🔴 Nguy hiểm":    "#c62828",
            },
            hover_data={
                COT_TEN_PGD:    True,
                "Tổng_dư_nợ":   False,
                "Số_KH":        True,
                "TL_NQH":       ":.3f",
                "Trạng_thái":   True,
            },
            labels={
                "Tổng_dư_nợ": "Tổng dư nợ (đồng)",
                "TL_NQH":     "Tỷ lệ NQH (%)",
                "Số_KH":      "Số khách hàng",
            },
        )
        fig_sc.add_hline(
            y=_NGUONG_AN_TOAN,
            line_dash="dash",
            line_color="#e65100",
            line_width=2,
            annotation_text=f"⚠️ Ngưỡng an toàn {_NGUONG_AN_TOAN}%",
            annotation_position="bottom right",
        )
        fig_sc.add_hline(
            y=_NGUONG_CANH_BAO,
            line_dash="dot",
            line_color="#c62828",
            line_width=1.5,
            annotation_text=f"🚨 Ngưỡng cảnh báo {_NGUONG_CANH_BAO}%",
            annotation_position="top right",
        )
        fig_sc.update_traces(
            textposition="top center",
            textfont_size=9,
            marker=dict(opacity=0.85, line=dict(width=1, color="white")),
        )
        fig_sc.update_layout(
            height=420,
            margin=dict(l=0, r=20, t=20, b=10),
            xaxis=dict(title="Tổng dư nợ (đồng)", tickformat=".3s"),
            yaxis=dict(title="Tỷ lệ NQH (%)"),
            legend=dict(title="Trạng thái", orientation="h", y=-0.18),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_family="Arial",
        )
        st.plotly_chart(fig_sc, use_container_width=True)
        st.caption(
            "💡 Kích thước bong bóng = Số khách hàng. "
            "PGD lý tưởng nằm ở góc phải dưới (dư nợ cao, NQH thấp)."
        )

    # ── TAB 3: Bar ngang Tỷ lệ NQH ───────────────────────────────────────────
    elif _chart_active == chart_tab_names[2]:
        t_nqh = t_pgd.sort_values("TL_NQH", ascending=True)
        mau_bars = [
            "#c62828" if v >= _NGUONG_CANH_BAO
            else ("#f57f17" if v >= _NGUONG_AN_TOAN else "#2e7d32")
            for v in t_nqh["TL_NQH"]
        ]
        fig_nqh = go.Figure(go.Bar(
            name="Tỷ lệ NQH",
            y=t_nqh[COT_TEN_PGD],
            x=t_nqh["TL_NQH"],
            orientation="h",
            marker_color=mau_bars,
            text=t_nqh["TL_NQH"].apply(lambda v: f"{v:.3f}%"),
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Tỷ lệ NQH: %{x:.3f}%<extra></extra>"
            ),
        ))
        fig_nqh.add_vline(
            x=_NGUONG_AN_TOAN,
            line_dash="dash",
            line_color="#e65100",
            line_width=2,
            annotation_text=f"Ngưỡng {_NGUONG_AN_TOAN}%",
        )
        fig_nqh.update_layout(
            height=max(350, len(t_nqh) * 44),
            margin=dict(l=0, r=80, t=20, b=10),
            xaxis=dict(title="Tỷ lệ NQH (%)", ticksuffix="%"),
            yaxis=dict(title=""),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_family="Arial",
        )
        st.plotly_chart(fig_nqh, use_container_width=True)

    # ── Bảng xếp hạng đầy đủ ─────────────────────────────────────────────────
    st.divider()
    with st.expander("📋 Bảng xếp hạng Sức khỏe Tín dụng theo PGD", expanded=False):
        df_xh = t_pgd.sort_values("Tổng_dư_nợ", ascending=False).reset_index(drop=True)
        df_xh.index += 1
        df_display = df_xh[[
            COT_TEN_PGD, "Tổng_dư_nợ", "Dư_nợ_TH",
            "NQH", "TL_NQH", "Số_KH", "TL_TH", "Trạng_thái",
        ]].copy()
        df_display["Tổng_dư_nợ"] = df_display["Tổng_dư_nợ"].apply(fmt)
        df_display["Dư_nợ_TH"]   = df_display["Dư_nợ_TH"].apply(fmt)
        df_display["NQH"]         = df_display["NQH"].apply(fmt)
        df_display["TL_NQH"]      = df_display["TL_NQH"].apply(lambda x: f"{x:.3f}%")
        df_display["TL_TH"]       = df_display["TL_TH"].apply(lambda x: f"{x:.1f}%")
        df_display["Số_KH"]       = df_display["Số_KH"].apply(fmt_so)
        df_display.columns = [
            "PGD", "Tổng dư nợ", "Dư nợ trong hạn",
            "Nợ quá hạn", "Tỷ lệ NQH", "Số KH", "Tỷ lệ TH", "Trạng thái",
        ]
        hien_thi_dataframe_phan_trang(
            df_display,
            key="exec_suc_khoe_pgd",
            hide_index=False,
        )
        # Nút xuất Excel
        st.download_button(
            label="⬇️ Xuất Excel",
            data=xuat_excel({"Sức khỏe PGD": df_display}),
            file_name=ten_file_xuat("SucKhoe_PGD"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Top 10 Chương trình + Tiến độ Kế hoạch
# ═══════════════════════════════════════════════════════════════════════════════
@st.fragment
def _render_bieu_do_tron(**kwargs) -> None:
    """Biểu đồ Top 10 chương trình theo dư nợ (bar ngang)."""
    df_full = kwargs.get("df_full")
    if df_full is None or COT_TEN_CT not in df_full.columns:
        return
    t_ct = (
        df_full.groupby(COT_TEN_CT)[COT_TONG_DU_NO]
        .sum()
        .nlargest(10)
        .reset_index()
    )
    t_ct.columns = ["Chương trình", "Dư nợ"]
    t_ct["Rút gọn"] = t_ct["Chương trình"].apply(
        lambda x: x[:32] + "…" if len(str(x)) > 32 else x
    )
    fig = px.bar(
        t_ct,
        x="Dư nợ",
        y="Rút gọn",
        orientation="h",
        color="Dư nợ",
        color_continuous_scale="Blues",
        text=t_ct["Dư nợ"].apply(fmt_ty),
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=340,
        margin=dict(l=0, r=80, t=10, b=10),
        yaxis=dict(title="", autorange="reversed"),
        xaxis_title="",
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="Arial",
    )
    st.plotly_chart(fig, use_container_width=True)


def _tien_do_ke_hoach() -> None:
    """Biểu đồ Tiến độ Kế hoạch vs Thực hiện từ Điện báo."""
    path_ht = DB_HT_CACHE if os.path.exists(DB_HT_CACHE) else FILE_PATH_DB
    kh_data = doc_kehoach()

    if not (os.path.exists(path_ht) and kh_data):
        st.info("Upload file Điện báo & nhập Kế hoạch trong tab ⚖️ và 🎯 để xem tiến độ.")
        return

    db_rows = doc_dienbao(path_ht, ts_file(path_ht))
    CT_QUAN_TRONG = [
        "Tổng dư nợ", "Dư nợ Kế hoạch A", "Dư nợ Kế hoạch B",
        "Tổng huy động vốn", "Nguồn vốn cân đối từ TW (KHA)",
    ]
    rows_kh = []
    for ten in CT_QUAN_TRONG:
        th  = db_lookup(db_rows, ten)
        kh  = kh_data.get(ten, 0)
        tl  = th / kh * 100 if kh > 0 else 0
        rows_kh.append({"Chỉ tiêu": ten, "Kế hoạch": kh, "Thực hiện": th, "Tỷ lệ %": tl})
    df_kh = pd.DataFrame(rows_kh)
    fig = px.bar(
        df_kh,
        x="Tỷ lệ %",
        y="Chỉ tiêu",
        orientation="h",
        text=df_kh["Tỷ lệ %"].apply(lambda x: f"{x:.1f}%"),
        color="Tỷ lệ %",
        color_continuous_scale="RdYlGn",
        range_color=[0, 120],
    )
    fig.add_vline(x=100, line_dash="dash", line_color="green", line_width=2,
                  annotation_text="100%")
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=290,
        margin=dict(l=0, r=70, t=10, b=10),
        xaxis=dict(title="Tỷ lệ thực hiện (%)", range=[0, 140]),
        yaxis=dict(title="", autorange="reversed"),
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="Arial",
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Cảnh báo NQH tăng đột biến theo Xã
# ═══════════════════════════════════════════════════════════════════════════════
def _canh_bao_xa_nqh(df_full: pd.DataFrame) -> None:
    """Phát hiện và hiển thị xã/phường có tỷ lệ NQH vượt ngưỡng."""
    if _COT_XA not in df_full.columns or COT_DU_NO_QH not in df_full.columns:
        st.info("Không tìm thấy cột Tên xã hoặc Dư nợ quá hạn trong dữ liệu.")
        return

    t_xa = df_full.groupby(_COT_XA).agg(
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        NQH=(COT_DU_NO_QH, "sum"),
        Số_KH=(COT_MA_KH, "nunique"),
    ).reset_index()
    t_xa["TL_NQH_%"] = (t_xa["NQH"] / t_xa["Tổng_dư_nợ"] * 100).round(3).fillna(0)

    canh_bao = t_xa[t_xa["TL_NQH_%"] >= _NGUONG_XA_NQH].sort_values("TL_NQH_%", ascending=False)

    if canh_bao.empty:
        st.success(f"✅ Tất cả xã/phường có tỷ lệ NQH dưới ngưỡng {_NGUONG_XA_NQH}%")
        return

    st.error(f"🚨 Phát hiện **{len(canh_bao)}** xã/phường có tỷ lệ NQH ≥ {_NGUONG_XA_NQH}%")
    df_cb = canh_bao.copy()
    df_cb["Tổng_dư_nợ"] = df_cb["Tổng_dư_nợ"].fillna(0).apply(_fmt)
    df_cb["NQH"]         = df_cb["NQH"].fillna(0).apply(_fmt)
    df_cb["TL_NQH_%"]    = df_cb["TL_NQH_%"].apply(lambda x: f"{x:.3f}%")
    hien_thi_dataframe_phan_trang(
        df_cb[[_COT_XA, "Số_KH", "Tổng_dư_nợ", "NQH", "TL_NQH_%"]],
        key="exec_canh_bao_xa_nqh",
    )

    top_xa = canh_bao.nlargest(min(10, len(canh_bao)), "TL_NQH_%")
    fig = px.bar(
        top_xa,
        x="TL_NQH_%",
        y=_COT_XA,
        orientation="h",
        color="TL_NQH_%",
        color_continuous_scale="Reds",
        text=top_xa["TL_NQH_%"].apply(lambda x: f"{x:.2f}%"),
    )
    fig.add_vline(x=_NGUONG_XA_NQH, line_dash="dash", line_color="red",
                  annotation_text=f"Ngưỡng {_NGUONG_XA_NQH}%")
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=320,
        margin=dict(l=0, r=70, t=10, b=10),
        xaxis_title="Tỷ lệ NQH (%)",
        yaxis=dict(title="", autorange="reversed"),
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="Arial",
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Cảnh báo Phân loại nợ Migration
# ═══════════════════════════════════════════════════════════════════════════════
def _canh_bao_migration(df_full: pd.DataFrame) -> None:
    """Cảnh báo món vay Đủ tiêu chuẩn (E) có nguy cơ chuyển sang NQH."""
    if df_full is None or len(df_full) == 0:
        st.info("Chưa có dữ liệu HSTD để phân tích.")
        return

    df_mg = canh_bao_migration(df_full)
    if df_mg.empty:
        st.success("✅ Không có món vay nào có dấu hiệu rủi ro chuyển NQH.")
        return

    n_khan = len(df_mg[df_mg["muc_canh_bao"].str.startswith("🔴")])
    n_cb   = len(df_mg) - n_khan
    tong_lai = df_mg[COT_LAI_TON].sum() if COT_LAI_TON in df_mg.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "🔴 Khẩn cấp (≥2.5 tháng)", f"{n_khan:,} món",
        delta="Cần xử lý ngay" if n_khan > 0 else None,
        delta_color="inverse",
    )
    c2.metric("⚠️ Cảnh báo (1–2.5 tháng)", f"{n_cb:,} món")
    c3.metric("Tổng lãi tồn rủi ro", fmt_ty(tong_lai))

    if COT_TEN_PGD in df_mg.columns:
        top5 = (
            df_mg.groupby(COT_TEN_PGD)
            .agg(Số_món=(COT_SO_KU, "nunique"), Lãi_tồn=(COT_LAI_TON, "sum"))
            .sort_values("Số_món", ascending=False)
            .head(5)
            .reset_index()
        )
        top5["Lãi_tồn_tr"] = (top5["Lãi_tồn"] / 1e6).round(1)
        st.markdown("**Top 5 PGD có nhiều món vay rủi ro nhất:**")
        hien_thi_dataframe_phan_trang(
            top5[[COT_TEN_PGD, "Số_món", "Lãi_tồn_tr"]].rename(columns={
                COT_TEN_PGD:    "PGD",
                "Số_món":       "Số món rủi ro",
                "Lãi_tồn_tr":  "Lãi tồn (triệu đ)",
            }),
            key="exec_migration_top5_pgd",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT — render()
# ═══════════════════════════════════════════════════════════════════════════════
def render(**kwargs) -> None:
    """
    Điểm vào của Workspace Lãnh đạo.

    Params (qua kwargs)
    ───────────────────
    df      : DataFrame đã lọc theo PGD/xã đang chọn (sidebar)
    df_full : DataFrame toàn chi nhánh (không lọc) — dùng cho KPI tổng
    """
    df      = kwargs.get("df")
    df_full = kwargs.get("df_full", df)

    # ── Header ────────────────────────────────────────────────────────────────
    st.title("📊 Tổng Quan Chi Nhánh")
    if df_full is not None and COT_NGAY_SL in df_full.columns:
        sl = df_full[COT_NGAY_SL].dropna()
        if len(sl):
            st.caption(
                f"📅 Số liệu ngày: **{sl.iloc[0]}** · "
                f"{fmt_so(len(df_full))} hồ sơ toàn hệ thống"
            )

    if df_full is None or df_full.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload file trong tab Quản trị.")
        return

    role = kwargs.get("role", "executive")
    username = kwargs.get("username", "unknown")

    tab_phan_tich, tab_kiem_soat_cn, tab_no_rui_ro_cn = st.tabs(
        ["📊 Phân tích & cảnh báo", "🔍 Kiểm soát CN", "💳 Nợ rủi ro QĐ62"]
    )

    with tab_phan_tich:
        # ═══════════ 1. SỨC KHỎE TÍN DỤNG ═══════════════════════════════════
        _the_suc_khoe(df_full)

        st.divider()

        # ═══════════ 2. TĂNG TRƯỞNG & SO SÁNH PGD ═══════════════════════════
        _render_heatmap_pgd(df_full=df_full)

        st.divider()

        # ═══════════ 3. TOP 10 CHƯƠNG TRÌNH ═══════════════════════════════════
        st.markdown("**📌 Top 10 Chương trình tín dụng theo dư nợ**")
        _render_bieu_do_tron(df_full=df_full)

        st.divider()

        # ═══════════ 4. TIẾN ĐỘ KẾ HOẠCH VS THỰC HIỆN ═══════════════════════
        st.markdown("**🎯 Tiến độ Kế hoạch vs Thực hiện — Toàn Chi nhánh**")
        _tien_do_ke_hoach()

        st.divider()

        # ═══════════ 5. CẢNH BÁO NQH ĐỘT BIẾN THEO XÃ ═══════════════════════
        st.markdown("**⚠️ Cảnh báo: Xã/Phường có NQH tăng đột biến**")
        st.caption("So sánh dữ liệu HSTD hiện tại với kỳ trước (nếu có)")
        _canh_bao_xa_nqh(df_full)

        st.divider()

        # ═══════════ 6. ĐIỀU CHỈNH GIẢM KHTD (Sheet → KV) ══════════════════
        with st.expander("📋 Giao & Điều chỉnh KHTD", expanded=False):
            tab_khtd_giao_dc.render(None, **kwargs)

        st.divider()

        # ═══════════ 7. CẢNH BÁO PHÂN LOẠI NỢ — RỦI RO CHUYỂN NQH ═══════════
        st.subheader("🚨 Cảnh báo Phân loại nợ — Rủi ro chuyển NQH")
        st.caption(
            "Món vay Đủ tiêu chuẩn (E) nhưng đã tồn lãi > 1 tháng "
            "— cần chấn chỉnh trước khi phát sinh NQH"
        )
        _canh_bao_migration(df_full)

    with tab_kiem_soat_cn:
        tab_kiem_soat.render_tab(df_full, role, username)

    with tab_no_rui_ro_cn:
        tab_no_rui_ro.render(tab_no_rui_ro_cn, **kwargs)
