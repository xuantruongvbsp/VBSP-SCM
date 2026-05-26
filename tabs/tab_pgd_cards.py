"""Tab Card 22 PGD — tổng quan nhanh từng đơn vị.

Mỗi PGD hiển thị 1 card gồm:
  - Dư nợ (tỷ đồng)
  - Tỷ lệ NQH%
  - Khoản đến hạn trong tháng (triệu đồng)
  - Dư nợ bình quân hộ (triệu đồng/hộ)
  - Số KH + trạng thái upload file HSTD

Biểu đồ so sánh Plotly (bar dư nợ + line NQH%), bảng xếp hạng color-coded.
Click tên PGD → drill-down: lọc df theo PGD và hiển thị bảng chi tiết.
"""

from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_MA_KH,
    COT_SO_KU,
    COT_NGAY_DH,
    DS_PGD,
    DON_VI_CHI_NHANH,
    PGD_DATA_DIR,
)
import plotly.graph_objects as go

from services import tongquan_service as _tqsvc
from utils import fmt_ty, fmt_so, hien_thi_dataframe_phan_trang
from tabs.base_tab import TabContext


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pgd_file_path(ten_pgd: str) -> Path:
    try:
        from data.pgd import duong_dan_pgd
        return Path(duong_dan_pgd(ten_pgd, "hstd"))
    except Exception as e:
        logger.error("_pgd_file_path(%s): %s", ten_pgd, e, exc_info=True)
        import re, unicodedata
        s = unicodedata.normalize("NFD", ten_pgd.lower())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        slug = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return Path(PGD_DATA_DIR) / slug / "hstd_latest.xlsx"


def _upload_info(ten_pgd: str) -> tuple[bool, str]:
    """Trả về (co_file, ngay_cap_nhat_str)."""
    p = _pgd_file_path(ten_pgd)
    if not p.exists():
        return False, "—"
    ts = os.path.getmtime(str(p))
    return True, datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")


@st.cache_data(ttl=300, show_spinner=False)
def _cache_card_pgd(
    _df: pd.DataFrame,
    ts: float,
    ds_don_vi_key: str,
) -> pd.DataFrame:
    _ = (ts, ds_don_vi_key)
    ds_don_vi = ds_don_vi_key.split("|")
    return _tqsvc.tinh_card_pgd(
        _df,
        cot_pgd=COT_TEN_PGD,
        cot_tdn=COT_TONG_DU_NO,
        cot_dqh=COT_DU_NO_QH,
        cot_ma_kh=COT_MA_KH,
        cot_so_ku=COT_SO_KU,
        cot_ngay_dh=COT_NGAY_DH,
        ds_don_vi=ds_don_vi,
    )


# ── CSS card ─────────────────────────────────────────────────────────────────

_CARD_CSS = """
<style>
.pgd-card {
    background: linear-gradient(145deg, #0D1B2A 0%, #112240 100%);
    border: 1px solid #1E3A5F;
    border-radius: 12px;
    padding: 14px 16px 10px;
    margin-bottom: 10px;
    position: relative;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.pgd-card:hover {
    border-color: #2979FF;
    box-shadow: 0 4px 18px rgba(41,121,255,0.18);
}
.pgd-card-title {
    font-size: 13px; font-weight: 700;
    color: #90CAF9; margin-bottom: 10px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    letter-spacing: 0.3px;
}
.pgd-card-kpi { display: flex; gap: 6px; flex-wrap: wrap; }
.pgd-kpi-block { flex: 1 1 30%; min-width: 80px; }
.pgd-kpi-label {
    font-size: 9.5px; color: #607D8B;
    margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.5px;
}
.pgd-kpi-value { font-size: 14px; font-weight: 700; color: #E3F2FD; }
.pgd-kpi-value.red   { color: #EF5350; }
.pgd-kpi-value.amber { color: #FFA726; }
.pgd-kpi-value.green { color: #66BB6A; }
.pgd-kpi-value.cyan  { color: #4DD0E1; }
.nqh-badge {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    line-height: 1.6;
}
.nqh-badge.red   { background: rgba(239,83,80,0.18); color: #EF5350; border: 1px solid #EF5350; }
.nqh-badge.amber { background: rgba(255,167,38,0.18); color: #FFA726; border: 1px solid #FFA726; }
.nqh-badge.green { background: rgba(102,187,106,0.18); color: #66BB6A; border: 1px solid #66BB6A; }
.pgd-upload-row {
    font-size: 10px; color: #7B8EA0;
    margin-top: 8px; border-top: 1px solid #1E3A5F; padding-top: 6px;
    display: flex; justify-content: space-between; align-items: center;
}
.pgd-upload-ok   { color: #66BB6A; }
.pgd-upload-miss { color: #EF5350; }
.pgd-rank {
    position: absolute; top: 10px; right: 12px;
    font-size: 10px; color: #455A64;
    font-weight: 600;
}
</style>
"""


def _nqh_color(ty_le: float) -> str:
    if ty_le >= 3:
        return "red"
    if ty_le >= 1:
        return "amber"
    return "green"


def _fmt_bq_ho(dn_binh_quan_ho: float) -> str:
    """Hiển thị dư nợ bình quân hộ dạng triệu đồng."""
    val = dn_binh_quan_ho / 1_000_000
    if val >= 100:
        return f"{val:,.0f} tr"
    return f"{val:,.1f} tr"


def _render_card_html(row: dict, upload_ok: bool, upload_ts: str, rank: int) -> str:
    du_no_str   = fmt_ty(row["du_no"])
    nqh_pct     = row["ty_le_nqh"]
    nqh_str     = f"{nqh_pct:.2f}%"
    dh_str      = fmt_so(int(row["no_den_han_thang"] / 1_000_000)) + " tr"
    so_kh_str   = fmt_so(int(row["so_kh"]))
    bq_ho_str   = _fmt_bq_ho(row.get("dn_binh_quan_ho", 0))
    color       = _nqh_color(nqh_pct)

    upload_cls  = "pgd-upload-ok" if upload_ok else "pgd-upload-miss"
    upload_icon = "✅" if upload_ok else "❌"
    upload_lbl  = f"{upload_icon} HSTD {upload_ts}"
    rank_lbl    = f"#{rank}" if rank > 0 else ""

    return f"""
<div class="pgd-card">
  <div class="pgd-rank">{rank_lbl}</div>
  <div class="pgd-card-title">🏢 {row['ten_pgd']}</div>
  <div class="pgd-card-kpi">
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Dư nợ</div>
      <div class="pgd-kpi-value">{du_no_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">NQH%</div>
      <div class="nqh-badge {color}">{nqh_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Đến hạn T.này</div>
      <div class="pgd-kpi-value">{dh_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Số KH</div>
      <div class="pgd-kpi-value">{so_kh_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">BQ/hộ</div>
      <div class="pgd-kpi-value cyan">{bq_ho_str}</div>
    </div>
  </div>
  <div class="pgd-upload-row">
    <span class="{upload_cls}">{upload_lbl}</span>
    <span style="color:#546E7A;font-size:9.5px">{int(row['so_mon']):,} món</span>
  </div>
</div>"""


# ── Biểu đồ so sánh Plotly ──────────────────────────────────────────────────

def _render_chart(df_cards: pd.DataFrame) -> None:
    """Combo chart: bar dư nợ (tỷ) + line NQH% theo PGD, sắp xếp theo dư nợ giảm."""
    df_ch = df_cards[df_cards["du_no"] > 0].sort_values("du_no", ascending=True).copy()
    if df_ch.empty:
        st.info("Chưa có dữ liệu để vẽ biểu đồ.")
        return

    ten_pgd_labels = df_ch["ten_pgd"].str.replace("PGD ", "", regex=False)
    du_no_ty = (df_ch["du_no"] / 1_000_000_000).round(3)
    nqh_pct  = df_ch["ty_le_nqh"]
    bq_ho_tr = (df_ch["dn_binh_quan_ho"] / 1_000_000).round(1)

    bar_colors = [
        "#EF5350" if v >= 3 else "#FFA726" if v >= 1 else "#42A5F5"
        for v in nqh_pct
    ]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Dư nợ (tỷ đ)",
        x=du_no_ty,
        y=ten_pgd_labels,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{v:.2f} tỷ" for v in du_no_ty],
        textposition="outside",
        textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Dư nợ: %{x:.3f} tỷ<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        name="NQH%",
        x=nqh_pct,
        y=ten_pgd_labels,
        mode="markers+text",
        marker=dict(symbol="diamond", size=9, color="#FFA726",
                    line=dict(width=1, color="#fff")),
        text=[f"{v:.2f}%" for v in nqh_pct],
        textposition="middle right",
        textfont=dict(size=8, color="#FFA726"),
        hovertemplate="<b>%{y}</b><br>NQH: %{x:.2f}%<extra></extra>",
        xaxis="x2",
    ))

    fig.add_trace(go.Scatter(
        name="BQ/hộ (tr đ)",
        x=bq_ho_tr,
        y=ten_pgd_labels,
        mode="markers",
        marker=dict(symbol="circle", size=7, color="#4DD0E1",
                    line=dict(width=1, color="#fff")),
        hovertemplate="<b>%{y}</b><br>BQ/hộ: %{x:.1f} tr<extra></extra>",
        xaxis="x3",
    ))

    max_dn = float(du_no_ty.max()) if len(du_no_ty) else 1
    max_nqh = max(float(nqh_pct.max()) * 1.4, 1.0) if len(nqh_pct) else 5
    max_bq  = max(float(bq_ho_tr.max()) * 1.3, 1.0) if len(bq_ho_tr) else 100

    fig.update_layout(
        height=max(360, len(df_ch) * 24 + 80),
        margin=dict(l=10, r=120, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,27,42,0.6)",
        font=dict(color="#B0BEC5", size=10),
        legend=dict(
            orientation="h", x=0, y=1.06,
            bgcolor="rgba(0,0,0,0)", font_size=10,
        ),
        xaxis=dict(
            title="Dư nợ (tỷ đồng)",
            range=[0, max_dn * 1.25],
            gridcolor="#1E3A5F", zeroline=False,
            titlefont_size=10,
        ),
        xaxis2=dict(
            title="NQH%",
            range=[0, max_nqh],
            overlaying="x", side="top",
            showgrid=False, zeroline=False,
            titlefont=dict(size=10, color="#FFA726"),
            tickfont=dict(size=9, color="#FFA726"),
        ),
        xaxis3=dict(
            title="BQ/hộ (tr đ)",
            range=[0, max_bq],
            overlaying="x", side="bottom",
            anchor="free", position=0,
            showgrid=False, zeroline=False,
            titlefont=dict(size=10, color="#4DD0E1"),
            tickfont=dict(size=9, color="#4DD0E1"),
            visible=False,
        ),
        yaxis=dict(gridcolor="#1E3A5F"),
        bargap=0.35,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_chart_bq(df_cards: pd.DataFrame) -> None:
    """Bar chart ngang xếp hạng dư nợ bình quân hộ theo PGD (có màu theo mức)."""
    df_ch = df_cards[df_cards["dn_binh_quan_ho"] > 0].sort_values("dn_binh_quan_ho", ascending=True).copy()
    if df_ch.empty:
        st.info("Chưa có dữ liệu BQ/hộ.")
        return

    ten_pgd_labels = df_ch["ten_pgd"].str.replace("PGD ", "", regex=False)
    bq_ho_tr  = (df_ch["dn_binh_quan_ho"] / 1_000_000).round(1)
    # BQ thực = tổng dư nợ / tổng số KH (weighted mean), không dùng mean() của per-PGD BQ
    _tong_dn  = df_cards["du_no"].sum()
    _tong_kh  = df_cards["so_kh"].sum()
    bq_cn     = (_tong_dn / _tong_kh / 1_000_000) if _tong_kh > 0 else 0

    bar_colors = [
        "#4DD0E1" if v >= bq_cn else "#78909C"
        for v in bq_ho_tr
    ]

    fig2 = go.Figure()

    fig2.add_trace(go.Bar(
        name="BQ/hộ (tr đ)",
        x=bq_ho_tr,
        y=ten_pgd_labels,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{v:,.1f} tr" for v in bq_ho_tr],
        textposition="outside",
        textfont_size=9,
        hovertemplate="<b>%{y}</b><br>BQ/hộ: %{x:,.1f} tr đ<extra></extra>",
    ))

    fig2.add_vline(
        x=bq_cn,
        line_dash="dot",
        line_color="#FFA726",
        annotation_text=f"BQ CN: {bq_cn:,.1f} tr",
        annotation_font_color="#FFA726",
        annotation_font_size=10,
    )

    max_bq = float(bq_ho_tr.max()) if len(bq_ho_tr) else 100

    fig2.update_layout(
        height=max(360, len(df_ch) * 24 + 80),
        margin=dict(l=10, r=100, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,27,42,0.6)",
        font=dict(color="#B0BEC5", size=10),
        showlegend=False,
        xaxis=dict(
            title="Dư nợ BQ/hộ (triệu đồng)",
            range=[0, max_bq * 1.25],
            gridcolor="#1E3A5F", zeroline=False,
            titlefont_size=10,
        ),
        yaxis=dict(gridcolor="#1E3A5F"),
        bargap=0.35,
    )

    st.caption(f"🔵 Trên BQ toàn CN ({bq_cn:,.1f} tr) · 🔘 Dưới BQ toàn CN")
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})


# ── Bảng xếp hạng color-coded ────────────────────────────────────────────────

def _render_ranking_table(df_show: pd.DataFrame, upload_info_map: dict) -> None:
    """Bảng tổng hợp có màu NQH, cột xếp hạng dư nợ và BQ/hộ."""
    df_t = df_show.copy()

    df_dn_rank = df_show.sort_values("du_no", ascending=False).reset_index(drop=True)
    rank_map = {row["ten_pgd"]: i + 1 for i, row in df_dn_rank.iterrows()}

    df_t["#"]                = df_t["ten_pgd"].map(rank_map)
    df_t["PGD"]              = df_t["ten_pgd"]
    df_t["Dư nợ (tỷ)"]      = (df_t["du_no"] / 1_000_000_000).round(3)
    df_t["NQH (tỷ)"]         = (df_t["nqh"] / 1_000_000_000).round(3)
    df_t["NQH%"]             = df_t["ty_le_nqh"].round(2)
    df_t["Đến hạn T (tr)"]  = (df_t["no_den_han_thang"] / 1_000_000).round(0).astype(int)
    df_t["Số KH"]            = df_t["so_kh"]
    df_t["BQ/hộ (tr)"]       = (df_t["dn_binh_quan_ho"] / 1_000_000).round(1)
    df_t["Upload HSTD"]      = df_t["ten_pgd"].map(
        lambda dv: ("✅ " + upload_info_map[dv][1]) if upload_info_map.get(dv, (False, ""))[0] else "❌ Thiếu"
    )

    cols_out = ["#", "PGD", "Dư nợ (tỷ)", "NQH (tỷ)", "NQH%",
                "Đến hạn T (tr)", "Số KH", "BQ/hộ (tr)", "Upload HSTD"]
    df_out = df_t[cols_out].sort_values("#").reset_index(drop=True)

    def _style_nqh(val):
        if isinstance(val, (int, float)):
            if val >= 3:
                return "background-color: rgba(239,83,80,0.15); color: #EF5350; font-weight:700"
            if val >= 1:
                return "background-color: rgba(255,167,38,0.12); color: #FFA726; font-weight:700"
            return "background-color: rgba(102,187,106,0.10); color: #66BB6A"
        return ""

    def _style_bq(val):
        if isinstance(val, (int, float)) and val > 0:
            return "color: #4DD0E1; font-weight:600"
        return ""

    styled = (
        df_out.style
        .map(_style_nqh, subset=["NQH%"])          # pandas 3.0+: map thay applymap
        .map(_style_bq, subset=["BQ/hộ (tr)"])
        .format({"Dư nợ (tỷ)": "{:,.3f}", "NQH (tỷ)": "{:,.3f}",
                 "NQH%": "{:.2f}%", "BQ/hộ (tr)": "{:,.1f}",
                 "Đến hạn T (tr)": "{:,}", "Số KH": "{:,}"})
    )
    st.dataframe(styled, use_container_width=True, height=min(700, len(df_out) * 36 + 50))


# ── Drill-down ───────────────────────────────────────────────────────────────

def _render_drilldown(df: pd.DataFrame, ten_pgd: str) -> None:
    st.markdown(f"#### 🔍 Chi tiết: {ten_pgd}")
    df_pgd = df[df[COT_TEN_PGD] == ten_pgd] if COT_TEN_PGD in df.columns else df
    if df_pgd.empty:
        st.info(f"Không có dữ liệu cho {ten_pgd}.")
        return

    cols_hien = [c for c in [
        COT_TEN_PGD, "Tên xã", "Tên tổ TK&VV", "Tên KH",
        COT_SO_KU, "Tên chương trình",
        COT_TONG_DU_NO, COT_DU_NO_QH, COT_NGAY_DH,
    ] if c in df_pgd.columns]

    st.caption(f"Tổng {len(df_pgd):,} khoản vay — dư nợ: {fmt_ty(df_pgd[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_pgd.columns else 0)}")
    hien_thi_dataframe_phan_trang(df_pgd[cols_hien], key=f"drill_{ten_pgd}", height=400)


# ── Render chính ─────────────────────────────────────────────────────────────

def render(tab_parent=None, **kwargs):
    with TabContext(tab_parent):
        df   = kwargs.get("df")

        st.header("🏢 Toàn cảnh 22 PGD")

        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload và merge trước.")
            return

        # ── Tính card data ────────────────────────────────────────────────
        ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
        from config import CACHE_HSTD
        from data.core import ts_file as _ts_file
        ts = _ts_file(CACHE_HSTD)

        try:
            df_cards = _cache_card_pgd(df, ts, "|".join(ds_don_vi))
        except Exception as e:
            logger.error("render tab_pgd_cards — _cache_card_pgd: %s", e, exc_info=True)
            st.error(f"Lỗi tính toán card PGD: {e}")
            return

        # ── KPI tổng toàn CN (5 chỉ tiêu) ───────────────────────────────
        tong_dn   = df_cards["du_no"].sum()
        tong_nqh  = df_cards["nqh"].sum()
        tl_nqh_cn = tong_nqh / tong_dn * 100 if tong_dn > 0 else 0
        tong_kh   = int(df_cards["so_kh"].sum())
        bq_ho_cn  = tong_dn / tong_kh if tong_kh > 0 else 0
        n_upload  = sum(1 for dv in ds_don_vi if _pgd_file_path(dv).exists())

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Tổng dư nợ CN",      fmt_ty(tong_dn))
        c2.metric("NQH% toàn CN",       f"{tl_nqh_cn:.2f}%")
        c3.metric("Đến hạn tháng này",  fmt_ty(df_cards["no_den_han_thang"].sum()))
        c4.metric("BQ/hộ toàn CN",      f"{bq_ho_cn/1_000_000:,.1f} tr")
        c5.metric("File HSTD",           f"{n_upload}/{len(ds_don_vi)} đơn vị")

        st.divider()

        # ── Biểu đồ so sánh ──────────────────────────────────────────────
        with st.expander("📊 Biểu đồ so sánh 22 đơn vị", expanded=True):
            tab_chart1, tab_chart2 = st.tabs(["📊 Dư nợ & NQH%", "💰 BQ/hộ xếp hạng"])
            with tab_chart1:
                _render_chart(df_cards)
            with tab_chart2:
                _render_chart_bq(df_cards)

        st.divider()

        # ── Bộ lọc & sắp xếp ─────────────────────────────────────────────
        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            sapxep = st.selectbox(
                "Sắp xếp card theo",
                ["Dư nợ (giảm)", "NQH% (giảm)", "BQ/hộ (giảm)",
                 "Đến hạn tháng (giảm)", "Tên PGD (A→Z)"],
                key="pgd_cards_sort",
            )
        with col_f2:
            loc_upload = st.selectbox(
                "Trạng thái upload",
                ["Tất cả", "Có file HSTD", "Thiếu file HSTD"],
                key="pgd_cards_upload_filter",
            )
        with col_f3:
            loc_nqh = st.selectbox(
                "Mức NQH",
                ["Tất cả", "🔴 ≥3%", "🟠 1–3%", "🟢 <1%"],
                key="pgd_cards_nqh_filter",
            )

        sort_map = {
            "Dư nợ (giảm)":           ("du_no", False),
            "NQH% (giảm)":            ("ty_le_nqh", False),
            "BQ/hộ (giảm)":           ("dn_binh_quan_ho", False),
            "Đến hạn tháng (giảm)":   ("no_den_han_thang", False),
            "Tên PGD (A→Z)":          ("ten_pgd", True),
        }
        sort_col, sort_asc = sort_map[sapxep]
        df_show = df_cards.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)

        # Lấy trạng thái upload
        upload_status  = {dv: _pgd_file_path(dv).exists() for dv in ds_don_vi}
        upload_info_map = {dv: _upload_info(dv) for dv in ds_don_vi}

        if loc_upload == "Có file HSTD":
            df_show = df_show[df_show["ten_pgd"].map(upload_status).fillna(False)]
        elif loc_upload == "Thiếu file HSTD":
            df_show = df_show[~df_show["ten_pgd"].map(upload_status).fillna(False)]

        if loc_nqh == "🔴 ≥3%":
            df_show = df_show[df_show["ty_le_nqh"] >= 3]
        elif loc_nqh == "🟠 1–3%":
            df_show = df_show[(df_show["ty_le_nqh"] >= 1) & (df_show["ty_le_nqh"] < 3)]
        elif loc_nqh == "🟢 <1%":
            df_show = df_show[df_show["ty_le_nqh"] < 1]

        # Tính rank dư nợ để hiện trên card
        df_dn_rank = df_cards.sort_values("du_no", ascending=False).reset_index(drop=True)
        rank_map = {row["ten_pgd"]: i + 1 for i, row in df_dn_rank.iterrows()}

        # ── Drill-down state ──────────────────────────────────────────────
        drill_key = "pgd_cards_drilldown"
        if drill_key not in st.session_state:
            st.session_state[drill_key] = None

        st.markdown(_CARD_CSS, unsafe_allow_html=True)

        # ── Grid card: 3 cột ──────────────────────────────────────────────
        COLS = 3
        rows_iter = [df_show.iloc[i:i + COLS] for i in range(0, len(df_show), COLS)]

        for chunk in rows_iter:
            cols = st.columns(COLS)
            for col, (_, row) in zip(cols, chunk.iterrows()):
                with col:
                    ok, ts_str = upload_info_map.get(row["ten_pgd"], (False, "—"))
                    rank = rank_map.get(row["ten_pgd"], 0)
                    st.markdown(_render_card_html(row.to_dict(), ok, ts_str, rank), unsafe_allow_html=True)
                    if st.button(
                        "🔍 Xem chi tiết",
                        key=f"drill_btn_{row['ten_pgd']}",
                        use_container_width=True,
                    ):
                        cur = st.session_state.get(drill_key)
                        st.session_state[drill_key] = None if cur == row["ten_pgd"] else row["ten_pgd"]
                        st.rerun()

        # ── Drill-down panel ──────────────────────────────────────────────
        selected = st.session_state.get(drill_key)
        if selected:
            st.divider()
            if st.button("✖ Đóng chi tiết", key="drill_close"):
                st.session_state[drill_key] = None
                st.rerun()
            _render_drilldown(df, selected)

        # ── Bảng xếp hạng ────────────────────────────────────────────────
        st.divider()
        st.markdown("#### 📋 Bảng xếp hạng tổng hợp")
        _render_ranking_table(df_show, upload_info_map)
