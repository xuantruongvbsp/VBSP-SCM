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
from datetime import datetime

from config import (
    COT_TEN_PGD, COT_MA_KH, COT_SO_KU, COT_TEN_KH,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT,
    COT_NGAY_SL, DB_HT_CACHE, DB_PREV_CACHE, FILE_PATH_DB, FILE_PATH_DB_PREV,
    NAM_HT, NAM_PREV, COT_LAI_TON, COT_TEN_XA, COT_PHAN_LOAI,
)
from data import (doc_dienbao, db_lookup, db_nqh_con, ts_file,
                  canh_bao_migration, canh_bao_migration_cached)
from data.khtd import doc_kehoach
from data.hstd import (danh_dau_khong_hd, danh_dau_khong_hd_cached,
                       tong_hop_khong_hd)
from utils import (
    fmt,
    fmt_tien,
    fmt_ty,
    fmt_pct,
    fmt_so,
    fmt_bang_ty,
    vn,
    hien_thi_dataframe_phan_trang,
    xuat_excel,
    ten_file_xuat,
)
from services.excel_service import ExcelReport, xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from pdf_service import xuat_pdf_bao_cao, xuat_pdf, kiem_tra_pdf_dependency, render_huong_dan
from tabs import tab_khtd_giao_dc, tab_kiem_soat, tab_qd62, tab_tien_do, tab_so_sanh_ky
from tabs import tab_qlnk_dashboard
from snapshot_service import doc_snapshot, doc_snapshot_range, danh_sach_ky
from services.hhi_service import tinh_hhi, tinh_hhi_breakdown, danh_gia_hhi
from components.delta_card import delta_card, kpi_row

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
    """Format số tiền (đồng) → triệu đồng (chuẩn VN: . nghìn, , thập phân, 0 số lẻ)."""
    try:
        v = float(v)
        if abs(v) > 0:
            trieu = v / 1_000_000
            s = f"{trieu:,.0f}".replace(",","X").replace(".",",").replace("X",".")
            return s
        return "—"
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
    st.plotly_chart(_gauge_nqh(tlqh), width='stretch')


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

    kpi_row([
        {"label": "Tổng dư nợ", "value": tdn, "icon": "💰", "suffix": "đồng", "precision": 0, "help": "Tổng dư nợ toàn chi nhánh"},  # noqa: COT
        {"label": "Dư nợ trong hạn", "value": dth, "icon": "✅", "suffix": "đồng", "precision": 0, "help": "Dư nợ chưa đến hạn thanh toán"},  # noqa: COT
        {"label": "Nợ quá hạn", "value": dqh, "icon": "⚠️", "suffix": "đồng", "precision": 0,  # noqa: COT
         "delta": tlqh, "delta_label": "% NQH", "delta_color": "inverse" if tlqh >= _NGUONG_AN_TOAN else "normal",
         "help": f"{tinh_trang}" if dqh > 0 else "✅ Không có NQH"},
        {"label": "Số khách hàng", "value": n_kh, "icon": "👥", "suffix": "", "precision": 0, "help": f"Tổng {fmt_so(n_hs)} hồ sơ trong hệ thống"},
    ], num_columns=4)

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
def _kpi_tang_truong(df_full: pd.DataFrame) -> None:
    """4 metric so sánh với snapshot tháng trước (nếu có)."""
    tdn = float(df_full[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_full.columns else 0
    dqh = float(df_full[COT_DU_NO_QH].sum())   if COT_DU_NO_QH   in df_full.columns else 0
    nkh = int(df_full[COT_MA_KH].nunique())     if COT_MA_KH      in df_full.columns else 0
    tlqh = dqh / tdn * 100 if tdn > 0 else 0

    ds_ky = danh_sach_ky()
    prev = None
    if len(ds_ky) >= 2:
        df_p = doc_snapshot(ds_ky[1])
        cn = df_p[df_p["ten_pgd"] == "__CN__"] if not df_p.empty else pd.DataFrame()
        if not cn.empty:
            prev = cn.iloc[0]

    def _d(now, col, scale=1e6):
        if prev is None:
            return None
        return (now - float(prev.get(col, now) or now)) / scale

    c1, c2, c3, c4 = st.columns(4)
    d_tdn = _d(tdn, "tong_du_no")
    d_dqh = _d(dqh, "du_no_qh")

    with c1:
        delta_card("Tổng dư nợ", fmt_ty(tdn),  # noqa: COT
                    delta=d_tdn, delta_label="triệu so tháng trước",
                    suffix="triệu đ", precision=0, help="So với snapshot tháng trước",
                    key="exe_tdn")
    with c2:
        delta_card("Dư nợ quá hạn", fmt_ty(dqh),
                    delta=d_dqh, delta_label="triệu so tháng trước",
                    delta_color="inverse",
                    suffix="triệu đ", precision=0, help="So với snapshot tháng trước",
                    key="exe_dqh")
    with c3:
        delta_card("Tỷ lệ NQH", vn(tlqh, 2),
                    delta=0, delta_label="%",
                    delta_color="off",
                    suffix="%", precision=2,
                    key="exe_tlqh")
    with c4:
        delta_card("Số hộ vay", fmt_so(nkh),
                    suffix="hộ", precision=0,
                    key="exe_nkh")


def _heatmap_rui_ro_pgd(df_full: pd.DataFrame) -> None:
    """Bảng HTML 7 cột: PGD | Dư nợ | NQH% | 3T KHĐ | Migration | Tăng trưởng | Điểm RR."""
    if COT_TEN_PGD not in df_full.columns:
        return

    g = df_full.groupby(COT_TEN_PGD)
    t = g.agg(
        du_no=(COT_TONG_DU_NO, "sum"),
        dqh=(COT_DU_NO_QH, "sum"),
        nkh=(COT_MA_KH, "nunique"),
    ).reset_index()
    t["tl_nqh"] = (t["dqh"] / t["du_no"].replace(0, float("nan")) * 100).round(3).fillna(0)

    df_k = danh_dau_khong_hd_cached(df_full)
    khd = df_k[df_k["is_3m_inactive"]].groupby(COT_TEN_PGD).size().reset_index(name="khd")
    t = t.merge(khd, on=COT_TEN_PGD, how="left")
    t["khd"] = t["khd"].fillna(0).astype(int)

    df_mg = canh_bao_migration_cached(df_full)
    mg = (
        df_mg.groupby(COT_TEN_PGD).size().reset_index(name="mg")
        if not df_mg.empty
        else pd.DataFrame(columns=[COT_TEN_PGD, "mg"])
    )
    t = t.merge(mg, on=COT_TEN_PGD, how="left")
    t["mg"] = t["mg"].fillna(0).astype(int)

    ds_ky = danh_sach_ky()
    t["tt"] = None
    if len(ds_ky) >= 2:
        _df_prev = doc_snapshot(ds_ky[1])
        prev_map = (
            _df_prev.set_index("ten_pgd")["tong_du_no"].to_dict()
            if _df_prev is not None and not _df_prev.empty
            else {}
        )
        if prev_map:
            t["tt"] = t.apply(
                lambda r: (r["du_no"] - prev_map.get(r[COT_TEN_PGD], r["du_no"])) / 1e6,
                axis=1,
            )

    t["rr"] = (
        t["tl_nqh"] * 3
        + t["khd"] / t["nkh"].replace(0, 1) * 100
        + t["mg"] / t["nkh"].replace(0, 1) * 100
    ).round(1)
    t = t.sort_values("rr", ascending=False).reset_index(drop=True)

    BD = "#d1d5db"; H = "#003D7A"; W = "#fff"; A = "#f8fafc"
    R = "#dc2626"; AM = "#d97706"; G = "#16a34a"; GR = "#9ca3af"

    def td(v, al="right", c="", bg="", fw=""):
        s = f"text-align:{al};padding:5px 8px;border:1px solid {BD};font-size:0.8rem;white-space:nowrap"
        if c:
            s += f";color:{c}"
        if bg:
            s += f";background:{bg}"
        if fw:
            s += f";font-weight:{fw}"
        return f"<td style='{s}'>{v}</td>"

    def nc(tl): return R if tl >= 2 else (AM if tl >= 0.5 else G)

    hdrs = ["#", "PGD", "Dư nợ (triệu đồng)", "NQH%", "3T KHĐ", "Migration", "Tăng trưởng", "Điểm RR"]
    thead = "".join(
        f'<th style="background:{H};color:#fff;text-align:{"center" if i==0 else "left" if i==1 else "right"};padding:6px 8px;border:1px solid {BD};font-size:0.8rem">{h}</th>'
        for i, h in enumerate(hdrs)
    )
    rows_h = []
    for i, row in t.iterrows():
        bg = W if i % 2 == 0 else A
        tl = row["tl_nqh"]
        tt_s = "—"
        if row["tt"] is not None:
            col = G if row["tt"] >= 0 else R
            tt_vn = f"{abs(row['tt']):,.0f}".replace(",","X").replace(".",",").replace("X",".")
            tt_s = f'<span style="color:{col}">{"+" if row["tt"] >= 0 else "-"}{tt_vn}</span>'
        rows_h.append(
            "<tr>" + "".join(
                [
                    td(str(i + 1), "center", "", bg),
                    td(row[COT_TEN_PGD], "left", "", bg),
                    td(fmt_ty(row["du_no"]), bg=bg),
                    td(f"{tl:.3f}%", c=nc(tl), bg=bg, fw="bold" if tl >= 0.5 else ""),
                    td(str(row["khd"]), c=R if row["khd"] > 0 else GR, bg=bg),
                    td(str(row["mg"]), c=AM if row["mg"] > 0 else GR, bg=bg),
                    td(tt_s, bg=bg),
                    td(f"{row['rr']:.1f}", c=R if row["rr"] >= 5 else (AM if row["rr"] >= 2 else G), bg=bg, fw="bold"),
                ]
            ) + "</tr>"
        )

    st.markdown(
        f"""
<div style="overflow-x:auto;margin:8px 0">
<table style="border-collapse:collapse;width:100%;font-family:'Inter','Segoe UI',sans-serif">
  <thead><tr>{thead}</tr></thead>
  <tbody>{"".join(rows_h)}</tbody>
</table>
<p style="font-size:0.75rem;color:#6b7280;margin:4px 0 0">
NQH%: <span style="color:{G}">■</span>&lt;0.5% &nbsp;
<span style="color:{AM}">■</span>0.5–2% &nbsp;
<span style="color:{R}">■</span>≥2% &nbsp;·&nbsp;
Điểm RR = NQH%×3 + KHĐ/KH% + Mg/KH%
</p></div>""",
        unsafe_allow_html=True,
    )


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
            name="Dư nợ trong hạn",  # noqa: COT
            y=t_pgd_sorted[COT_TEN_PGD],
            x=t_pgd_sorted["Dư_nợ_TH"] / 1e6,
            orientation="h",
            marker_color="#1565C0",
            text=(t_pgd_sorted["Dư_nợ_TH"] / 1e6).apply(
                lambda v: f"{v:,.0f}".replace(",","X").replace(".",",").replace("X",".")
            ),
            textposition="inside",
            insidetextanchor="middle",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Dư nợ trong hạn: %{x:,.0f} triệu đồng<extra></extra>"
            ),
        ))
        fig_bar.add_trace(go.Bar(
            name="Nợ quá hạn",  # noqa: COT
            y=t_pgd_sorted[COT_TEN_PGD],
            x=t_pgd_sorted["NQH"] / 1e6,
            orientation="h",
            marker_color="#C62828",
            text=(t_pgd_sorted["NQH"] / 1e6).apply(
                lambda v: (
                    f"{v:,.0f}".replace(",","X").replace(".",",").replace("X",".")
                    if v >= 1 else ""
                )
            ),
            textposition="inside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Nợ quá hạn: %{x:,.0f} triệu đồng<extra></extra>"
            ),
        ))
        fig_bar.update_layout(
            barmode="stack",
            height=chieu_cao,
            margin=dict(l=0, r=80, t=20, b=10),
            xaxis_title="Triệu đồng",
            yaxis=dict(title=""),
            legend=dict(orientation="h", y=1.04, x=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_family="Arial",
        )
        st.plotly_chart(fig_bar, width='stretch')
        st.caption(
            "📌 Cột xanh = Dư nợ trong hạn · Cột đỏ = Nợ quá hạn. "
            "Sắp xếp theo Tổng dư nợ tăng dần."
        )

    # ── TAB 2: Scatter Tổng dư nợ vs NQH ────────────────────────────────────
    elif _chart_active == chart_tab_names[1]:
        t_pgd_chart = t_pgd.copy()
        t_pgd_chart["Tổng_dư_nợ_tr"] = t_pgd_chart["Tổng_dư_nợ"] / 1e6
        fig_sc = px.scatter(
            t_pgd_chart,
            x="Tổng_dư_nợ_tr",
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
                "Tổng_dư_nợ_tr": True,
                "Số_KH":        True,
                "TL_NQH":       ":.3f",
                "Trạng_thái":   True,
            },
            labels={
                "Tổng_dư_nợ_tr": "Tổng dư nợ (triệu đồng)",
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
            xaxis=dict(title="Tổng dư nợ (triệu đồng)", tickformat=",.0f"),
            yaxis=dict(title="Tỷ lệ NQH (%)"),
            legend=dict(title="Trạng thái", orientation="h", y=-0.18),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_family="Arial",
        )
        st.plotly_chart(fig_sc, width='stretch')
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
        st.plotly_chart(fig_nqh, width='stretch')

    # ── Bảng xếp hạng đầy đủ ─────────────────────────────────────────────────
    st.divider()
    with st.expander("📋 Bảng xếp hạng Sức khỏe Tín dụng theo PGD", expanded=False):
        df_xh = t_pgd.sort_values("Tổng_dư_nợ", ascending=False).reset_index(drop=True)
        df_xh.index += 1
        df_display = df_xh[[
            COT_TEN_PGD, "Tổng_dư_nợ", "Dư_nợ_TH",
            "NQH", "TL_NQH", "Số_KH", "TL_TH", "Trạng_thái",
        ]].copy()
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
        hien_thi_dataframe_phan_trang(
            df_display,
            key="exec_suc_khoe_pgd",
            hide_index=False,
        )
        # Nút xuất Excel chuyên nghiệp
        kpi_suc_khoe = [
            ("Tổng PGD",                fmt_so(len(df_xh)), ""),
            ("Tổng dư nợ",              fmt_bang_ty(df_xh["Tổng_dư_nợ"].sum()), ""),  # noqa: COT
            ("Tổng NQH",                fmt_bang_ty(df_xh["NQH"].sum()), ""),
            ("TL NQH b/q",              f"{df_xh['TL_NQH'].mean():.2f}%", ""),
            ("Số KH vay",               fmt_so(df_xh["Số_KH"].sum()), ""),
        ]
        col1, col2 = st.columns([1, 1])
        with col1:
            st.download_button(
                label="⬇️ Xuất Excel (chuyên nghiệp)",
                type="primary",
                data=xuat_excel_chuyen_nghiep(
                    df=df_display,
                    title="Báo cáo Sức khỏe Tín dụng theo PGD",
                    subtitle="Phân hệ Chi nhánh",
                    nguoi_xuat=st.session_state.get("txt_username", ""),
                    kpi_items=kpi_suc_khoe,
                ),
                file_name=excel_ten_file("SucKhoe_PGD"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch',
            )
        with col2:
            st.download_button(
                label="⬇️ Xuất Excel (cơ bản)",
                data=xuat_excel({"Sức khỏe PGD": df_display}),
                file_name=ten_file_xuat("SucKhoe_PGD"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch',
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
    st.plotly_chart(fig, width='stretch')


def _tien_do_ke_hoach() -> None:
    """Biểu đồ Tiến độ Kế hoạch vs Thực hiện từ Điện báo."""
    path_ht = DB_HT_CACHE if os.path.exists(DB_HT_CACHE) else FILE_PATH_DB
    kh_data = doc_kehoach()

    if not (os.path.exists(path_ht) and kh_data):
        st.info("Upload file Điện báo & nhập Kế hoạch trong tab ⚖️ và 🎯 để xem tiến độ.")
        return

    db_rows = doc_dienbao(path_ht, ts_file(path_ht))
    CT_QUAN_TRONG = [
        "Tổng dư nợ", "Dư nợ Kế hoạch A", "Dư nợ Kế hoạch B",  # noqa: COT
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
    st.plotly_chart(fig, width='stretch')


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
    st.plotly_chart(fig, width='stretch')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4b — Giám sát Tập trung Rủi ro (HHI)
# ═══════════════════════════════════════════════════════════════════════════════
def _hhi_giam_sat(df_full: pd.DataFrame) -> None:
    """Giám sát mức độ tập trung danh mục cho vay — HHI theo Xã và Chương trình."""
    st.markdown("#### 🎯 Giám sát Tập trung Rủi ro — HHI")

    if df_full is None or df_full.empty:
        st.info("Chưa có dữ liệu để phân tích.")
        return

    cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_full.columns else ""

    if not cot_tien:
        st.warning("Không tìm thấy cột Tổng dư nợ trong dữ liệu.")
        return

    # ── HHI theo Xã ────────────────────────────────────────────────────
    hhi_xa = tinh_hhi(df_full, COT_TEN_XA, cot_tien) if COT_TEN_XA in df_full.columns else 0
    # ── HHI theo Chương trình ──────────────────────────────────────────
    hhi_ct = tinh_hhi(df_full, COT_TEN_CT, cot_tien) if COT_TEN_CT in df_full.columns else 0

    muc_xa, icon_xa, mau_xa = danh_gia_hhi(hhi_xa)
    muc_ct, icon_ct, mau_ct = danh_gia_hhi(hhi_ct)

    c_xa, c_ct = st.columns(2)

    with c_xa:
        st.markdown(
            f"**🏘️ Tập trung theo Xã**",
            help="HHI càng cao → dư nợ tập trung vào ít xã → rủi ro địa lý",
        )
        st.markdown(
            f"<span style='font-size:2.2rem;font-weight:800;color:{mau_xa}'>"
            f"{hhi_xa * 10000:.0f}</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"{icon_xa} {muc_xa}")
        st.progress(min(hhi_xa * 10000 / 5000, 1.0))

    with c_ct:
        st.markdown(
            f"**📌 Tập trung theo Chương trình**",
            help="HHI càng cao → dư nợ tập trung vào ít chương trình → rủi ro sản phẩm",
        )
        st.markdown(
            f"<span style='font-size:2.2rem;font-weight:800;color:{mau_ct}'>"
            f"{hhi_ct * 10000:.0f}</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"{icon_ct} {muc_ct}")
        st.progress(min(hhi_ct * 10000 / 5000, 1.0))

    # ── Thang tham chiếu ──────────────────────────────────────────────
    st.caption(
        "Thang HHI: **<1000** ✅ Đa dạng hóa tốt · "
        "**1000–2500** ⚠️ Tập trung vừa · "
        "**>2500** 🚨 Tập trung cao"
    )

    # ── Breakdown chi tiết ─────────────────────────────────────────────
    with st.expander("📊 Xem chi tiết phân bổ", expanded=False):
        tab_xa, tab_ct = st.tabs(["🏘️ Theo Xã", "📌 Theo Chương trình"])

        with tab_xa:
            if COT_TEN_XA in df_full.columns:
                br = tinh_hhi_breakdown(df_full, COT_TEN_XA, cot_tien)
                br.columns = ["Xã", "Dư nợ (đồng)", "Tỷ trọng %", "Đóng góp HHI"]
                br["Dư nợ (triệu đồng)"] = (br["Dư nợ (đồng)"] / 1e6).round(0)
                br["Dư nợ (triệu đồng)"] = br["Dư nợ (triệu đồng)"].apply(
                    lambda x: f"{x:,.0f}".replace(",", ".")
                )
                st.dataframe(
                    br[["Xã", "Dư nợ (triệu đồng)", "Tỷ trọng %", "Đóng góp HHI"]],
                    hide_index=True,
                    width='stretch',
                )

        with tab_ct:
            if COT_TEN_CT in df_full.columns:
                br = tinh_hhi_breakdown(df_full, COT_TEN_CT, cot_tien)
                br.columns = ["Chương trình", "Dư nợ (đồng)", "Tỷ trọng %", "Đóng góp HHI"]
                br["Dư nợ (triệu đồng)"] = (br["Dư nợ (đồng)"] / 1e6).round(0)
                br["Dư nợ (triệu đồng)"] = br["Dư nợ (triệu đồng)"].apply(
                    lambda x: f"{x:,.0f}".replace(",", ".")
                )
                st.dataframe(
                    br[["Chương trình", "Dư nợ (triệu đồng)", "Tỷ trọng %", "Đóng góp HHI"]],
                    hide_index=True,
                    width='stretch',
                )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4c — Ma trận Chuyển dịch Nhóm nợ (Migration Matrix)
# ═══════════════════════════════════════════════════════════════════════════════
def _migration_matrix_section(df_full: pd.DataFrame, username: str) -> None:
    st.markdown("#### 🔄 Ma trận Chuyển dịch Nhóm nợ (Migration Matrix)")

    from services.migration_service import (
        luu_snapshot as luu_snap_loan,
        danh_sach_ky as ds_ky_loan,
        migration_matrix as mig_mat,
    )

    ds_ky = ds_ky_loan()

    # ── Nút chụp snapshot ────────────────────────────────────────────────
    col_snap, col_info = st.columns([2, 3])
    with col_snap:
        ky_moi = ""
        if COT_NGAY_SL in df_full.columns:
            sl = df_full[COT_NGAY_SL].dropna()
            if len(sl):
                try:
                    val = str(sl.iloc[0])
                    if "/" in val:
                        parts = val.split("/")
                        ky_moi = f"{parts[2][:4]}-{parts[1].zfill(2)}"
                except Exception:
                    pass
        if not ky_moi:
            ky_moi = datetime.now().strftime("%Y-%m")

        da_co = ky_moi in ds_ky
        if st.button(
            f"📸 Chụp Snapshot kỳ **{ky_moi}**",
            type="primary",
            disabled=da_co,
            help="Đã có snapshot kỳ này" if da_co else "Lưu trạng thái hiện tại để so sánh",
            key="btn_snap_loan",
        ):
            with st.spinner("⏳ Đang lưu snapshot..."):
                ky = luu_snap_loan(df_full, username)
            st.success(f"✅ Đã lưu snapshot kỳ **{ky}**")
            st.rerun()

    with col_info:
        if ds_ky:
            st.caption(f"📂 Các kỳ đã lưu: {', '.join(ds_ky[:5])}" + ("..." if len(ds_ky) > 5 else ""))
        else:
            st.caption("👆 Chưa có snapshot nào. Bấm nút bên trái để chụp kỳ đầu tiên.")

    if len(ds_ky) < 2:
        st.info("⏳ Cần **ít nhất 2 kỳ snapshot** để hiển thị Ma trận chuyển dịch. Hãy quay lại vào kỳ sau và chụp thêm snapshot.")
        return

    # ── Chọn 2 kỳ để so sánh ─────────────────────────────────────────────
    ky_sau = ds_ky[0]
    ky_truoc = ds_ky[1]

    k1, k2 = st.columns(2)
    with k1:
        ky_truoc_chon = st.selectbox("Kỳ trước", ds_ky[1:], index=0, key="mig_ky_truoc")
    with k2:
        ky_sau_chon = st.selectbox("Kỳ sau", ds_ky[:-1], index=0, key="mig_ky_sau")

    # ── Tính ma trận ────────────────────────────────────────────────────
    matrix, chi_tiet = mig_mat(ky_truoc_chon, ky_sau_chon)

    if matrix.empty:
        st.warning("⚠️ Không đủ dữ liệu để tạo ma trận chuyển dịch.")
        return

    st.markdown("##### 📊 Ma trận Chuyển dịch Nhóm nợ")
    st.caption(f"Từ **{ky_truoc_chon}** → **{ky_sau_chon}**")

    # Style heatmap
    def _mau_nen(val):
        if val == 0:
            return ""
        ti_le = min(val / matrix.max().max(), 1.0)
        r = int(255 - ti_le * 155)
        g = int(255 - ti_le * 200)
        return f"background-color:rgb({r},{g},200);color:{'#fff' if ti_le > 0.5 else '#333'}"

    st.dataframe(
        matrix.style.applymap(_mau_nen).format("{:.0f}"),
        width='stretch',
    )
    st.caption(
        "📖 Cách đọc: Hàng = Nhóm nợ kỳ trước · Cột = Nhóm nợ kỳ sau. "
        "Đường chéo = số món giữ nguyên nhóm. Ô ngoài chéo = số món chuyển nhóm."
    )

    # Chi tiết món chuyển nhóm
    if not chi_tiet.empty:
        with st.expander(f"📋 Chi tiết các món chuyển nhóm ({len(chi_tiet)} món)", expanded=False):
            st.dataframe(chi_tiet, hide_index=True, width='stretch')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Cảnh báo Phân loại nợ Migration
# ═══════════════════════════════════════════════════════════════════════════════
def _canh_bao_migration(df_full: pd.DataFrame) -> None:
    """Cảnh báo món vay Đủ tiêu chuẩn (E) có nguy cơ chuyển sang NQH."""
    if df_full is None or len(df_full) == 0:
        st.info("Chưa có dữ liệu HSTD để phân tích.")
        return

    df_mg = canh_bao_migration_cached(df_full)
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
    c3.metric("Tổng lãi tồn rủi ro (triệu đồng)", fmt_ty(tong_lai))

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
# SECTION 6 — RADAR SO SÁNH PGD ĐA CHIỀU
# ═══════════════════════════════════════════════════════════════════════════════
def _radar_compare_pgd(df_full: pd.DataFrame) -> None:
    import plotly.graph_objects as go
    import plotly.express as px

    st.markdown("#### 📊 So sánh PGD đa chiều (Radar)")
    if df_full is None or df_full.empty:
        st.info("Chưa có dữ liệu.")
        return

    cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_full.columns else COT_DU_NO_TH
    if COT_TEN_PGD not in df_full.columns:
        st.warning("Không có thông tin PGD để so sánh.")
        return

    pgd_list = df_full[COT_TEN_PGD].dropna().unique()
    if len(pgd_list) < 2:
        st.info("Cần ít nhất 2 PGD để so sánh.")
        return

    max_pgd = 8
    if len(pgd_list) > max_pgd:
        pgd_list = pgd_list[:max_pgd]

    categories = ["Dư nợ", "Tỷ lệ QH", "Lãi tồn b/q", "Dư nợ b/q món", "Số KH"]
    data_radar = []
    for pgd in pgd_list:
        grp = df_full[df_full[COT_TEN_PGD] == pgd]
        du_no = grp[cot_tien].sum() if cot_tien in grp.columns else 0
        nqh = grp[COT_DU_NO_QH].sum() if COT_DU_NO_QH in grp.columns else 0
        tl_qh = (nqh / du_no * 100) if du_no > 0 else 0
        lai_ton = grp[COT_LAI_TON].sum() if COT_LAI_TON in grp.columns else 0
        lai_ton_bq = lai_ton / len(grp) if len(grp) > 0 else 0
        dn_bq_mon = du_no / len(grp) if len(grp) > 0 else 0
        so_kh = grp[COT_MA_KH].nunique() if COT_MA_KH in grp.columns else 0

        data_radar.append({
            "PGD": pgd,
            "Dư nợ": du_no,
            "Tỷ lệ QH": tl_qh,
            "Lãi tồn b/q": lai_ton_bq,
            "Dư nợ b/q món": dn_bq_mon,
            "Số KH": so_kh,
        })

    df_radar = pd.DataFrame(data_radar)

    # Chuẩn hoá Min-Max cho từng chỉ tiêu
    df_norm = df_radar.copy()
    norm_cols = [c for c in categories if c in df_norm.columns]
    for col in norm_cols:
        _min = df_norm[col].min()
        _max = df_norm[col].max()
        if _max - _min > 0:
            df_norm[col] = (df_norm[col] - _min) / (_max - _min)
        else:
            df_norm[col] = 0.5

    COLORS_RADAR = px.colors.qualitative.Set2
    fig = go.Figure()
    for i, (_, row) in enumerate(df_norm.iterrows()):
        values = [row[c] for c in norm_cols]
        values += [values[0]]
        theta = [c for c in norm_cols] + [norm_cols[0]]
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=theta,
            name=df_radar.iloc[i]["PGD"],
            line_color=COLORS_RADAR[i % len(COLORS_RADAR)],
            fill="toself",
            opacity=0.3,
        ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        height=400,
        margin=dict(l=60, r=40, t=10, b=20),
        font_family="Arial",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )

    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        st.plotly_chart(fig, width='stretch')
    with col_table:
        st.dataframe(
            df_radar.round(1),
            column_config={
                "Dư nợ": st.column_config.NumberColumn("Dư nợ", format=",.0f"),
                "Tỷ lệ QH": st.column_config.NumberColumn("TL QH %", format=".2f"),
                "Lãi tồn b/q": st.column_config.NumberColumn("Lãi tồn b/q", format=",.0f"),
                "Dư nợ b/q món": st.column_config.NumberColumn("DN b/q món", format=",.0f"),
                "Số KH": st.column_config.NumberColumn("Số KH", format=",.0f"),
            },
            hide_index=True,
            width='stretch',
            height=200,
        )

    # Export
    st.download_button(
        label="⬇️ Xuất Excel",
        type="primary",
        data=xuat_excel_chuyen_nghiep(
            df=df_radar,
            title="So sánh PGD đa chiều (Radar)",
            kpi_items=[("Số PGD so sánh", fmt_so(len(pgd_list)), ""),
                       ("Chỉ tiêu", ", ".join(norm_cols), "")],
        ),
        file_name=excel_ten_file("Radar_SoSanh_PGD"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width='stretch',
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — WATERFALL BIẾN ĐỘNG DƯ NỢ
# ═══════════════════════════════════════════════════════════════════════════════
def _waterfall_du_no(df_full: pd.DataFrame) -> None:
    import plotly.graph_objects as go

    st.markdown("#### 📈 Biến động Dư nợ (Waterfall)")
    if df_full is None or df_full.empty:
        st.info("Chưa có dữ liệu.")
        return

    cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_full.columns else COT_DU_NO_TH
    cot_nqh = COT_DU_NO_QH if COT_DU_NO_QH in df_full.columns else None

    tong_dn = df_full[cot_tien].sum() if cot_tien in df_full.columns else 0
    nqh = df_full[cot_nqh].sum() if cot_nqh and cot_nqh in df_full.columns else 0
    th = tong_dn - nqh

    # Nhóm theo chương trình
    if COT_TEN_CT in df_full.columns:
        ct_groups = df_full.groupby(COT_TEN_CT)[cot_tien].sum().sort_values(ascending=False)
        top_ct = ct_groups.head(6)
        khac = ct_groups.iloc[6:].sum()
    else:
        top_ct = pd.Series({"Không có CT": tong_dn})
        khac = 0

    labels = list(top_ct.index)
    values = [round(v) for v in top_ct.values]
    if khac > 0:
        labels.append("Khác")
        values.append(round(khac))

    total = round(tong_dn)

    # Waterfall: [TH, NQH, CT1, CT2, ..., Tổng]
    fig = go.Figure(go.Waterfall(
        name="Dư nợ",
        orientation="v",
        measure=["relative", "relative"] + ["relative"] * len(values) + ["total"],
        x=["Trong hạn", "Quá hạn"] + labels + ["Tổng dư nợ"],
        y=[round(th), round(nqh)] + values + [total],
        text=[fmt_ty(v / 1e6) + "tr" for v in [round(th), round(nqh)] + values + [total]],
        textposition="outside",
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#2E7D32"}},
        decreasing={"marker": {"color": "#C62828"}},
        totals={"marker": {"color": "#1565C0"}},
    ))

    fig.update_layout(
        height=400,
        margin=dict(l=40, r=20, t=20, b=60),
        font_family="Arial",
        xaxis_tickangle=-45,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        st.plotly_chart(fig, width='stretch')
    with col_info:
        st.metric("Tổng dư nợ", fmt_ty(tong_dn / 1e6) + " tr")
        st.metric("Trong hạn", fmt_ty(th / 1e6) + " tr", delta_color="normal")
        st.metric("Quá hạn", fmt_ty(nqh / 1e6) + " tr", delta_color="inverse")
        st.caption("Waterfall thể hiện cấu trúc dư nợ: trong hạn, quá hạn, và đóng góp theo chương trình.")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — RANKING PGD (LOLLIPOP)
# ═══════════════════════════════════════════════════════════════════════════════
def _ranking_pgd(df_full: pd.DataFrame) -> None:
    st.markdown("#### 🏆 Bảng xếp hạng PGD")
    if df_full is None or df_full.empty or COT_TEN_PGD not in df_full.columns:
        st.info("Chưa có dữ liệu hoặc không có thông tin PGD.")
        return

    import plotly.graph_objects as go

    cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_full.columns else COT_DU_NO_TH
    cot_nqh = COT_DU_NO_QH if COT_DU_NO_QH in df_full.columns else None

    ranking = df_full.groupby(COT_TEN_PGD).agg(
        Dư_nợ=(cot_tien, "sum"),
        NQH=(cot_nqh, "sum") if cot_nqh else (cot_tien, lambda x: 0),
        Số_KH=(COT_MA_KH, "nunique") if COT_MA_KH in df_full.columns else (cot_tien, "count"),
    ).reset_index()

    ranking.columns = ["PGD", "Dư_nợ", "NQH", "Số_KH"]
    ranking["TL_NQH"] = (ranking["NQH"] / ranking["Dư_nợ"] * 100).round(2)
    ranking["Dư_nợ_tr"] = (ranking["Dư_nợ"] / 1e6).round(0)
    ranking = ranking.sort_values("Dư_nợ", ascending=True).reset_index(drop=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ranking["Dư_nợ_tr"],
        y=ranking["PGD"],
        mode="markers+lines",
        marker=dict(
            size=12,
            color=ranking["Dư_nợ_tr"],
            colorscale="Blues",
            showscale=True,
            colorbar=dict(title="Dư nợ (tr)"),
        ),
        line=dict(color="lightgray", width=2),
        text=ranking["Dư_nợ_tr"].apply(lambda x: f"{x:,.0f} tr"),
        textposition="middle right",
        hovertemplate="<b>%{y}</b><br>Dư nợ: %{x:,.0f} tr<extra></extra>",
    ))

    fig.update_layout(
        title="Xếp hạng PGD theo Dư nợ",
        xaxis_title="Dư nợ (triệu đồng)",
        yaxis=dict(autorange="reversed"),
        height=max(300, len(ranking) * 35 + 60),
        margin=dict(l=10, r=40, t=30, b=10),
        font_family="Arial",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="y",
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(fig, width='stretch')
    with col2:
        st.dataframe(
            ranking.sort_values("Dư_nợ", ascending=False).reset_index(drop=True),
            column_config={
                "PGD": "PGD",
                "Dư_nợ_tr": st.column_config.NumberColumn("Dư nợ (tr)", format=",.0f"),
                "TL_NQH": st.column_config.NumberColumn("TL NQH %", format=".2f"),
                "Số_KH": st.column_config.NumberColumn("Số KH", format=",.0f"),
            },
            hide_index=True,
            width='stretch',
            height=200,
        )

    st.download_button(
        label="⬇️ Xuất Excel",
        type="primary",
        data=xuat_excel_chuyen_nghiep(
            df=ranking.sort_values("Dư_nợ", ascending=False).reset_index(drop=True),
            title="Bảng xếp hạng PGD",
            kpi_items=[
                ("Tổng PGD", fmt_so(len(ranking)), ""),
                ("Dư nợ toàn CN", fmt_ty(ranking["Dư_nợ"].sum() / 1e6), "triệu đồng"),
                ("PGD dẫn đầu", ranking.sort_values("Dư_nợ", ascending=False).iloc[0]["PGD"], ""),
            ],
        ),
        file_name=excel_ten_file("XepHang_PGD"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width='stretch',
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION WRAPPERS — gom logic thành từng mục menu độc lập
# ═══════════════════════════════════════════════════════════════════════════════

def _render_suc_khoe_tong_quan(df_full: pd.DataFrame) -> None:
    """KPI tăng trưởng + Bảng rủi ro PGD + Đồng hồ sức khỏe tín dụng."""
    _kpi_tang_truong(df_full)
    st.divider()
    st.markdown("**🗺️ Bảng Rủi ro Tổng hợp theo PGD**")
    _heatmap_rui_ro_pgd(df_full)
    st.divider()
    _the_suc_khoe(df_full)


def _render_tien_do_va_kh(df_full: pd.DataFrame, **kwargs) -> None:
    """Top 10 CT + Tiến độ KH + Tăng trưởng liên tháng + Tiến độ tổng quan."""
    st.markdown("**📌 Top 10 Chương trình tín dụng theo dư nợ**")
    _render_bieu_do_tron(df_full=df_full)
    st.divider()
    _tien_do_ke_hoach()

    _ds_ky = danh_sach_ky()
    if len(_ds_ky) >= 2:
        st.divider()
        st.markdown("**📈 Tăng trưởng Dư nợ liên tháng (từ snapshot)**")
        _df_range = doc_snapshot_range(_ds_ky[-1], _ds_ky[0])
        if not _df_range.empty:
            _df_range["du_no_ty"] = _df_range["tong_du_no"] / 1e6
            _fig_tt = px.line(
                _df_range,
                x="ky",
                y="du_no_ty",
                markers=True,
                labels={"ky": "Kỳ", "du_no_ty": "Dư nợ (triệu đồng)"},
            )
            _fig_tt.update_layout(
                height=260,
                margin=dict(l=0, r=20, t=10, b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_family="Arial",
            )
            st.plotly_chart(_fig_tt, width='stretch')

    st.divider()
    tab_tien_do.render_tong_quan_only(None, **kwargs)


def _render_so_sanh_xep_hang_pgd(df_full: pd.DataFrame) -> None:
    """Biểu đồ so sánh PGD + Bảng xếp hạng + Radar + Waterfall."""
    _render_heatmap_pgd(df_full=df_full)
    st.divider()
    with st.expander("🏆 Bảng xếp hạng PGD", expanded=True):
        _ranking_pgd(df_full)
    with st.expander("📊 So sánh PGD đa chiều (Radar)", expanded=False):
        _radar_compare_pgd(df_full)
    with st.expander("📈 Biến động Dư nợ (Waterfall)", expanded=False):
        _waterfall_du_no(df_full)


def _render_nqh_xa_canh_bao(df_full: pd.DataFrame) -> None:
    """Cảnh báo xã/phường có NQH tăng đột biến."""
    st.markdown("**⚠️ Cảnh báo: Xã/Phường có NQH tăng đột biến**")
    st.caption("So sánh dữ liệu HSTD hiện tại với kỳ trước (nếu có)")
    _canh_bao_xa_nqh(df_full)


def _render_migration_section(df_full: pd.DataFrame, username: str) -> None:
    """Cảnh báo migration + Ma trận chuyển dịch nhóm nợ."""
    st.subheader("🚨 Cảnh báo Phân loại nợ — Rủi ro chuyển NQH")
    _canh_bao_migration(df_full)
    st.divider()
    _migration_matrix_section(df_full, username)


def _render_pdf_section(df_full: pd.DataFrame, username: str) -> None:
    """Xuất báo cáo PDF đầy đủ."""
    st.markdown("### 📄 Xuất báo cáo PDF đầy đủ")
    st.caption("Báo cáo tổng hợp: KPI + Bảng dữ liệu — chuẩn NĐ30/2020")

    _pdf_dep = kiem_tra_pdf_dependency()
    if not _pdf_dep["ready"]:
        for msg in _pdf_dep["messages"]:
            st.warning(msg)
    elif not _pdf_dep["kaleido"]:
        st.info("ℹ️ Nhúng biểu đồ tự động vào PDF cần `pip install kaleido`. Hiện tại chỉ xuất KPI + bảng.")

    df_pdf = df_full.copy() if df_full is not None else pd.DataFrame()
    _kpi_items = []
    if df_full is not None and not df_full.empty:
        tdn = float(df_full[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_full.columns else 0
        dqh = float(df_full[COT_DU_NO_QH].sum()) if COT_DU_NO_QH in df_full.columns else 0
        nkh = int(df_full[COT_MA_KH].nunique()) if COT_MA_KH in df_full.columns else 0
        tlqh = dqh / tdn * 100 if tdn > 0 else 0
        _kpi_items = [
            ("Số khế ước", fmt_so(len(df_full)), ""),
            ("Số khách hàng", fmt_so(nkh), ""),
            ("Tổng dư nợ", fmt_ty(tdn), ""),
            ("Dư nợ quá hạn", fmt_ty(dqh), "accent"),
            ("Tỷ lệ NQH", fmt_pct(tlqh), "accent"),
            ("Dư nợ trong hạn", fmt_ty(tdn - dqh), ""),
        ]

    cols_tien_pdf = [c for c in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_TH, COT_LAI_TON] if c in df_pdf.columns]
    col_pdf1, col_pdf2 = st.columns([1, 1])
    with col_pdf1:
        st.download_button(
            label="📄 Xuất PDF báo cáo đầy đủ",
            type="primary",
            data=xuat_pdf_bao_cao(
                df=df_pdf,
                tieu_de="Báo cáo Sức khỏe Tín dụng Toàn Chi nhánh",
                nguoi_xuat=username,
                kpi_items=_kpi_items,
                cols_tien=cols_tien_pdf,
                tieu_de_phu=f"Ngày số liệu: {df_full[COT_NGAY_SL].iloc[0] if COT_NGAY_SL in df_full.columns else '—'}",
            ),
            file_name=f"BaoCao_SucKhoeTD_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            width='stretch',
            key="pdf_sk_full",
        )
    with col_pdf2:
        st.download_button(
            label="📄 PDF bảng dữ liệu (đơn giản)",
            data=xuat_pdf(
                df=df_pdf,
                tieu_de="Báo cáo Sức khỏe Tín dụng",
                nguoi_xuat=username,
                cols_tien=cols_tien_pdf,
                prefix_file="SKTD",
            ),
            file_name=f"SKTD_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            width='stretch',
            key="pdf_sk_simple",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MENU BUILDER — dùng chung cho sidebar và render()
# ═══════════════════════════════════════════════════════════════════════════════

def _build_exec_items(df_full, role: str, username: str, **kwargs) -> list:
    """Xây danh sách ALL_ITEMS cho workspace Lãnh đạo."""
    return [
        {"group": "Tổng quan",       "label": "Sức khỏe tín dụng",          "fn": lambda: _render_suc_khoe_tong_quan(df_full)},
        {"group": "Tổng quan",       "label": "Tiến độ & Kế hoạch",         "fn": lambda: _render_tien_do_va_kh(df_full, **kwargs)},
        {"group": "Tổng quan",       "label": "So sánh PGD",                 "fn": lambda: _render_so_sanh_xep_hang_pgd(df_full)},
        {"group": "Cảnh báo rủi ro", "label": "HHI — Tập trung rủi ro",     "fn": lambda: _hhi_giam_sat(df_full)},
        {"group": "Cảnh báo rủi ro", "label": "NQH theo Xã",                "fn": lambda: _render_nqh_xa_canh_bao(df_full)},
        {"group": "Cảnh báo rủi ro", "label": "Migration & Chuyển dịch nợ", "fn": lambda: _render_migration_section(df_full, username)},
        {"group": "Cảnh báo rủi ro", "label": "📊 Tổng hợp nợ khoanh",     "fn": lambda: tab_qlnk_dashboard.render(None, **kwargs)},
        {"group": "Kiểm soát",       "label": "Kiểm soát CN",                "fn": lambda: tab_kiem_soat.render_tab(df_full, role, username)},
        {"group": "Kiểm soát",       "label": "Nợ rủi ro QĐ62",             "fn": lambda: tab_qd62.render(mode="cn")},
        {"group": "Kiểm soát",       "label": "Giao & Điều chỉnh KHTD",     "fn": lambda: tab_khtd_giao_dc.render(None, **kwargs)},
        {"group": "Báo cáo",         "label": "So sánh kỳ",                 "fn": lambda: tab_so_sanh_ky.render(None, df=df_full, df_full=df_full, role=role, username=username)},
        {"group": "Báo cáo",         "label": "Xuất PDF báo cáo",           "fn": lambda: _render_pdf_section(df_full, username)},
        {"group": "Hệ thống",        "label": "Hướng dẫn",                  "fn": lambda: render_huong_dan()},
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR MENU — gọi từ app.py bên trong with st.sidebar
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar_menu(role: str, username: str, **kwargs) -> None:
    """Render menu LÃNH ĐẠO — gọi từ app.py bên trong with st.sidebar."""

    GROUP_COLORS = {
        "Tổng quan":         {"bg": "#E6F1FB", "border": "#378ADD", "text": "#185FA5"},
        "Cảnh báo rủi ro":   {"bg": "#FCEBEB", "border": "#E24B4A", "text": "#A32D2D"},
        "Kiểm soát":         {"bg": "#EAF3DE", "border": "#639922", "text": "#3B6D11"},
        "Báo cáo":           {"bg": "#FAEEDA", "border": "#BA7517", "text": "#854F0B"},
        "Hệ thống":          {"bg": "#F1EFE8", "border": "#888780", "text": "#5F5E5A"},
    }

    df_full = kwargs.get("df_full")
    all_items = _build_exec_items(df_full, role, username, **kwargs)
    if not all_items:
        return

    if "ws_exec_menu" not in st.session_state:
        st.session_state["ws_exec_menu"] = all_items[0]["label"]

    valid_labels = [x["label"] for x in all_items]
    if st.session_state["ws_exec_menu"] not in valid_labels:
        st.session_state["ws_exec_menu"] = all_items[0]["label"]

    st.markdown(
        "<p style='font-size:12px;font-weight:500;"
        "color:#444;margin-bottom:4px'>MENU LÃNH ĐẠO</p>",
        unsafe_allow_html=True,
    )

    current_group = None
    for item in all_items:
        grp = item["group"]
        clr = GROUP_COLORS.get(grp, {"bg": "#F1EFE8", "border": "#888", "text": "#444"})

        if grp != current_group:
            current_group = grp
            st.markdown(
                f"<p style='font-size:10px;font-weight:500;"
                f"color:{clr['text']};text-transform:uppercase;"
                f"letter-spacing:0.06em;padding:10px 4px 2px;margin:0'>"
                f"{grp}</p>",
                unsafe_allow_html=True,
            )

        is_active = st.session_state["ws_exec_menu"] == item["label"]

        if is_active:
            st.markdown(
                f"<div style='"
                f"background:#185FA5;"
                f"border-left:2px solid #0D3F73;"
                f"color:#FFFFFF;"
                f"font-size:13px;font-weight:600;"
                f"padding:6px 8px 6px 10px;"
                f"border-radius:0 5px 5px 0;"
                f"margin-bottom:2px'>"
                f"{item['label']}</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.button(
                item["label"],
                key=f"exec_menu_{item['label']}",
                width='stretch',
            ):
                st.session_state["ws_exec_menu"] = item["label"]
                st.rerun()


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
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role     = kwargs.get("role", "executive")
    username = kwargs.get("username", "unknown")

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

    # ── BƯỚC 1: Xây danh sách tất cả menu items ───────────────────────────
    _kw = {k: v for k, v in kwargs.items() if k not in ("df", "df_full", "role", "username")}
    ALL_ITEMS = _build_exec_items(df_full, role, username, **_kw)

    # ── Navigation lazy: Nhóm → Mục → chỉ render mục được chọn ───────────
    valid_labels = [x["label"] for x in ALL_ITEMS]

    # Handle jump từ shortcut / nút điều hướng ngoài ws_executive
    jump_label = st.session_state.pop("ws_exec_jump", None)
    if jump_label and jump_label in valid_labels:
        st.session_state["ws_exec_menu"] = jump_label
        st.toast(f"✨ Đã chuyển tới: {jump_label}", icon="👆")

    # Khởi tạo / validate ws_exec_menu
    if "ws_exec_menu" not in st.session_state or \
            st.session_state["ws_exec_menu"] not in valid_labels:
        st.session_state["ws_exec_menu"] = ALL_ITEMS[0]["label"]

    active_label = st.session_state["ws_exec_menu"]

    # Nhóm thứ tự xuất hiện đầu tiên (giữ thứ tự)
    groups_ordered = list(dict.fromkeys(x["group"] for x in ALL_ITEMS))
    active_group = next(
        (x["group"] for x in ALL_ITEMS if x["label"] == active_label),
        groups_ordered[0],
    )

    # ── Level 1: radio chọn nhóm ──────────────────────────────────────────
    # Force-set chỉ khi jump từ sidebar, hoặc chưa init / giá trị không hợp lệ
    # KHÔNG force-set mỗi lần render — sẽ override click của user
    if jump_label or \
            "ws_exec_group_radio" not in st.session_state or \
            st.session_state["ws_exec_group_radio"] not in groups_ordered:
        st.session_state["ws_exec_group_radio"] = active_group
    sel_group = st.radio(
        "Nhóm",
        groups_ordered,
        horizontal=True,
        key="ws_exec_group_radio",
        label_visibility="collapsed",
    )

    # ── Level 2: radio chọn mục trong nhóm ───────────────────────────────
    items_in_group = [x for x in ALL_ITEMS if x["group"] == sel_group]
    item_labels    = [x["label"] for x in items_in_group]
    item_key       = f"ws_exec_item_{sel_group}"

    # Pre-select item chỉ khi jump từ sidebar, hoặc chưa init key này
    # KHÔNG force-set mỗi lần render — sẽ override click của user
    if jump_label and active_label in item_labels:
        st.session_state[item_key] = item_labels.index(active_label)
    elif item_key not in st.session_state:
        st.session_state[item_key] = 0

    sel_idx = st.radio(
        "Mục",
        range(len(item_labels)),
        format_func=lambda i: item_labels[i],
        horizontal=True,
        key=item_key,
        label_visibility="collapsed",
    )
    sel_label = item_labels[sel_idx]

    # Ghi ngược lại ws_exec_menu để sidebar highlight đúng
    st.session_state["ws_exec_menu"] = sel_label

    st.divider()

    # ── Render DUY NHẤT mục đang chọn ────────────────────────────────────
    active_item = next((x for x in ALL_ITEMS if x["label"] == sel_label), None)
    if active_item:
        fn = active_item.get("fn")
        if callable(fn):
            try:
                fn()
            except Exception as e:
                import traceback
                st.error(f"❌ Lỗi render **{sel_label}**: {e}")
                st.code(traceback.format_exc())
        else:
            st.info(f"Tính năng **{sel_label}** đang được phát triển.")
