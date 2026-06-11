"""Tab Toàn cảnh 22 PGD — giám sát đa chiều.

4 sub-tab:
  🃏 Thẻ PGD       — card 7 metrics + risk bar + drill-down
  📊 Bảng Đa chiều  — 12 cột, xếp hạng theo Điểm RR tổng hợp
  🌡️ Heatmap Rủi ro — ma trận 22 PGD × 6 tiêu chí, màu đỏ=rủi ro/xanh=tốt
  📈 Biểu đồ        — dư nợ+NQH%, BQ/hộ xếp hạng
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
    COT_TEN_TO,
    COT_DVUT,
    DS_PGD,
    DON_VI_CHI_NHANH,
    PGD_DATA_DIR,
)
import plotly.graph_objects as go

from services import tongquan_service as _tqsvc
from utils import fmt_ty, fmt_so, hien_thi_dataframe_phan_trang, vn
from tabs.base_tab import TabContext


# ── Upload helpers ────────────────────────────────────────────────────────────

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


def _pgd_khnv_path(ten_pgd: str) -> Path:
    try:
        from data.pgd import duong_dan_pgd
        return Path(duong_dan_pgd(ten_pgd, "hstd_khnv"))
    except Exception as e:
        logger.error("_pgd_khnv_path(%s): %s", ten_pgd, e, exc_info=True)
        import re, unicodedata
        s = unicodedata.normalize("NFD", ten_pgd.lower())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        slug = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return Path(PGD_DATA_DIR) / slug / "hstd_khnv.xlsx"


def _upload_info(ten_pgd: str) -> tuple[bool, str]:
    p = _pgd_file_path(ten_pgd)
    p_khnv = _pgd_khnv_path(ten_pgd)
    exists, exists_khnv = p.exists(), p_khnv.exists()
    if not exists and not exists_khnv:
        return False, "—"
    ts = max(
        os.path.getmtime(str(p)) if exists else 0,
        os.path.getmtime(str(p_khnv)) if exists_khnv else 0,
    )
    return True, datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")


# ── Cache ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _cache_da_chieu_pgd(
    _df: pd.DataFrame,
    ts: float,
    ds_don_vi_key: str,
) -> pd.DataFrame:
    _ = (ts, ds_don_vi_key)
    ds_don_vi = ds_don_vi_key.split("|")
    return _tqsvc.tinh_toan_da_chieu_pgd(_df, ds_don_vi)


# ── CSS ───────────────────────────────────────────────────────────────────────

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
.pgd-card:hover { border-color: #2979FF; box-shadow: 0 4px 18px rgba(41,121,255,0.18); }
.pgd-card-title {
    font-size: 12px; font-weight: 700; color: #90CAF9;
    margin-bottom: 8px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    display: flex; justify-content: space-between; align-items: center;
}
.pgd-card-row { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 5px; }
.pgd-kpi-block { flex: 1 1 22%; min-width: 68px; }
.pgd-kpi-label { font-size: 9px; color: #607D8B; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.4px; }
.pgd-kpi-value { font-size: 13px; font-weight: 700; color: #E3F2FD; }
.pgd-kpi-value.red   { color: #EF5350; }
.pgd-kpi-value.amber { color: #FFA726; }
.pgd-kpi-value.green { color: #66BB6A; }
.pgd-kpi-value.cyan  { color: #4DD0E1; }
.nqh-badge {
    display: inline-block; padding: 1px 6px; border-radius: 20px;
    font-size: 11px; font-weight: 700; line-height: 1.6;
}
.nqh-badge.red   { background: rgba(239,83,80,0.18); color: #EF5350; border: 1px solid #EF5350; }
.nqh-badge.amber { background: rgba(255,167,38,0.18); color: #FFA726; border: 1px solid #FFA726; }
.nqh-badge.green { background: rgba(102,187,106,0.18); color: #66BB6A; border: 1px solid #66BB6A; }
.pgd-risk-bar-wrap {
    height: 4px; background: #1E3A5F; border-radius: 2px;
    overflow: hidden; margin: 8px 0 6px;
}
.pgd-upload-row {
    font-size: 10px; color: #7B8EA0;
    border-top: 1px solid #1E3A5F; padding-top: 5px;
    display: flex; justify-content: space-between; align-items: center;
}
.pgd-upload-ok  { color: #66BB6A; }
.pgd-upload-miss { color: #EF5350; }
</style>
"""


def _nqh_color(pct: float) -> str:
    if pct >= 3:
        return "red"
    if pct >= 1:
        return "amber"
    return "green"


def _khd_color(pct: float) -> str:
    if pct >= 5:
        return "red"
    if pct >= 2:
        return "amber"
    return "green"


def _rr_color_css(score: float) -> str:
    if score < 60:
        return "#EF5350"
    if score < 80:
        return "#FFA726"
    return "#66BB6A"


def _fmt_bq_ho(dn_binh_quan_ho: float) -> str:
    val = dn_binh_quan_ho / 1_000_000
    return f"{val:,.0f} tr" if val >= 100 else f"{val:,.1f} tr"


# ── Card HTML ─────────────────────────────────────────────────────────────────

def _render_card_html(row: dict, upload_ok: bool, upload_ts: str, rank: int) -> str:
    du_no_str  = vn(float(row["du_no"]) / 1_000_000_000, 3) + " tỷ"
    nqh_pct    = float(row.get("ty_le_nqh", 0))
    khoanh_pct = float(row.get("ty_le_khoanh", 0))
    khd_pct    = float(row.get("pct_3m_khd", 0))
    lai_ton_tr = int(row.get("lai_ton", 0) / 1_000_000)
    bq_ho_str  = _fmt_bq_ho(row.get("dn_binh_quan_ho", 0))
    so_kh      = int(row.get("so_kh", 0))
    dh_thang   = int(row.get("no_den_han_thang", 0) / 1_000_000)
    so_mon     = int(row.get("so_mon", 0))
    diem_rr    = float(row.get("diem_rui_ro", 0))

    rr_css   = _rr_color_css(diem_rr)
    rank_lbl = f"#{rank}" if rank > 0 else ""
    upload_cls  = "pgd-upload-ok" if upload_ok else "pgd-upload-miss"
    upload_icon = "✅" if upload_ok else "❌"

    return f"""
<div class="pgd-card">
  <div class="pgd-card-title">
    <span>🏢 {row['ten_pgd']}</span>
    <span style="font-size:10px;color:#455A64">{rank_lbl} &nbsp;
      <span style="color:{rr_css};font-weight:700">⭐ {diem_rr:.0f}</span>
    </span>
  </div>
  <div class="pgd-card-row">
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Dư nợ (tỷ)</div>
      <div class="pgd-kpi-value">{du_no_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">NQH%</div>
      <div class="nqh-badge {_nqh_color(nqh_pct)}">{nqh_pct:.2f}%</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Khoanh%</div>
      <div class="nqh-badge {_nqh_color(khoanh_pct * 1.5)}">{khoanh_pct:.2f}%</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">3m KHĐ%</div>
      <div class="pgd-kpi-value {_khd_color(khd_pct)}">{khd_pct:.1f}%</div>
    </div>
  </div>
  <div class="pgd-card-row">
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Lãi tồn</div>
      <div class="pgd-kpi-value amber">{fmt_so(lai_ton_tr)} tr</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">BQ/hộ</div>
      <div class="pgd-kpi-value cyan">{bq_ho_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Số KH</div>
      <div class="pgd-kpi-value">{fmt_so(so_kh)}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">ĐH T.này</div>
      <div class="pgd-kpi-value">{fmt_so(dh_thang)} tr</div>
    </div>
  </div>
  <div class="pgd-risk-bar-wrap">
    <div style="width:{min(100, diem_rr):.1f}%;height:100%;background:{rr_css};border-radius:2px;transition:width 0.3s"></div>
  </div>
  <div class="pgd-upload-row">
    <span class="{upload_cls}">{upload_icon} HSTD {upload_ts}</span>
    <span style="color:#546E7A;font-size:9.5px">{fmt_so(so_mon)} món</span>
  </div>
</div>"""


# ── Biểu đồ ───────────────────────────────────────────────────────────────────

def _render_chart(df_cards: pd.DataFrame) -> None:
    df_ch = df_cards[df_cards["du_no"] > 0].sort_values("du_no", ascending=True).copy()
    if df_ch.empty:
        st.info("Chưa có dữ liệu để vẽ biểu đồ.")
        return

    labels   = df_ch["ten_pgd"].str.replace("PGD ", "", regex=False)
    du_no_ty = (df_ch["du_no"] / 1e9).round(3)
    nqh_pct  = df_ch["ty_le_nqh"]
    bq_ho_tr = (df_ch["dn_binh_quan_ho"] / 1e6).round(1)

    bar_colors = ["#EF5350" if v >= 3 else "#FFA726" if v >= 1 else "#42A5F5" for v in nqh_pct]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Dư nợ (tỷ đ)", x=du_no_ty, y=labels, orientation="h",
        marker_color=bar_colors,
        text=[f"{v:.2f} tỷ" for v in du_no_ty],
        textposition="outside", textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Dư nợ: %{x:.3f} tỷ<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="NQH%", x=nqh_pct, y=labels, mode="markers+text",
        marker=dict(symbol="diamond", size=9, color="#FFA726", line=dict(width=1, color="#fff")),
        text=[f"{v:.2f}%" for v in nqh_pct], textposition="middle right",
        textfont=dict(size=8, color="#FFA726"),
        hovertemplate="<b>%{y}</b><br>NQH: %{x:.2f}%<extra></extra>",
        xaxis="x2",
    ))
    fig.add_trace(go.Scatter(
        name="BQ/hộ (tr đ)", x=bq_ho_tr, y=labels, mode="markers",
        marker=dict(symbol="circle", size=7, color="#4DD0E1", line=dict(width=1, color="#fff")),
        hovertemplate="<b>%{y}</b><br>BQ/hộ: %{x:.1f} tr<extra></extra>",
        xaxis="x3",
    ))

    max_dn  = float(du_no_ty.max()) if len(du_no_ty) else 1
    max_nqh = max(float(nqh_pct.max()) * 1.4, 1.0) if len(nqh_pct) else 5
    max_bq  = max(float(bq_ho_tr.max()) * 1.3, 1.0) if len(bq_ho_tr) else 100

    fig.update_layout(
        height=max(360, len(df_ch) * 24 + 80),
        margin=dict(l=10, r=120, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,27,42,0.6)",
        font=dict(color="#B0BEC5", size=10),
        legend=dict(orientation="h", x=0, y=1.06, bgcolor="rgba(0,0,0,0)", font_size=10),
        xaxis=dict(title=dict(text="Dư nợ (tỷ đồng)", font_size=10),
                   range=[0, max_dn * 1.25], gridcolor="#1E3A5F", zeroline=False),
        xaxis2=dict(title=dict(text="NQH%", font=dict(size=10, color="#FFA726")),
                    range=[0, max_nqh], overlaying="x", side="top",
                    showgrid=False, zeroline=False, tickfont=dict(size=9, color="#FFA726")),
        xaxis3=dict(title=dict(text="BQ/hộ (tr đ)", font=dict(size=10, color="#4DD0E1")),
                    range=[0, max_bq], overlaying="x", side="bottom",
                    anchor="free", position=0, showgrid=False, zeroline=False,
                    tickfont=dict(size=9, color="#4DD0E1"), visible=False),
        yaxis=dict(gridcolor="#1E3A5F"),
        bargap=0.35,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_chart_bq(df_cards: pd.DataFrame) -> None:
    df_ch = df_cards[df_cards["dn_binh_quan_ho"] > 0].sort_values("dn_binh_quan_ho", ascending=True).copy()
    if df_ch.empty:
        st.info("Chưa có dữ liệu BQ/hộ.")
        return

    labels   = df_ch["ten_pgd"].str.replace("PGD ", "", regex=False)
    bq_ho_tr = (df_ch["dn_binh_quan_ho"] / 1e6).round(1)
    _tong_dn = df_cards["du_no"].sum()
    _tong_kh = df_cards["so_kh"].sum()
    bq_cn    = (_tong_dn / _tong_kh / 1e6) if _tong_kh > 0 else 0
    bar_colors = ["#4DD0E1" if v >= bq_cn else "#78909C" for v in bq_ho_tr]

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        name="BQ/hộ (tr đ)", x=bq_ho_tr, y=labels, orientation="h",
        marker_color=bar_colors,
        text=[f"{v:,.1f} tr" for v in bq_ho_tr],
        textposition="outside", textfont_size=9,
        hovertemplate="<b>%{y}</b><br>BQ/hộ: %{x:,.1f} tr đ<extra></extra>",
    ))
    fig2.add_vline(x=bq_cn, line_dash="dot", line_color="#FFA726",
                   annotation_text=f"BQ CN: {bq_cn:,.1f} tr",
                   annotation_font_color="#FFA726", annotation_font_size=10)
    fig2.update_layout(
        height=max(360, len(df_ch) * 24 + 80),
        margin=dict(l=10, r=100, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,27,42,0.6)",
        font=dict(color="#B0BEC5", size=10), showlegend=False,
        xaxis=dict(title=dict(text="Dư nợ BQ/hộ (triệu đồng)", font_size=10),
                   range=[0, float(bq_ho_tr.max()) * 1.25 if len(bq_ho_tr) else 100],
                   gridcolor="#1E3A5F", zeroline=False),
        yaxis=dict(gridcolor="#1E3A5F"),
        bargap=0.35,
    )
    st.caption(f"🔵 Trên BQ toàn CN ({bq_cn:,.1f} tr) · 🔘 Dưới BQ toàn CN")
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})


# ── Heatmap Rủi ro ────────────────────────────────────────────────────────────

def _render_heatmap(df_cards: pd.DataFrame) -> None:
    """Heatmap 22 PGD × 6 tiêu chí — Đỏ=rủi ro, Xanh=tốt."""
    df = df_cards[df_cards["du_no"] > 0].sort_values("diem_rui_ro", ascending=True).copy()
    if df.empty:
        st.info("Chưa có dữ liệu.")
        return

    labels = df["ten_pgd"].str.replace("PGD ", "", regex=False).tolist()

    criteria = [
        {"name": "NQH%",       "col": "ty_le_nqh",      "bad_high": True,  "fmt": "{:.2f}%"},
        {"name": "Khoanh%",    "col": "ty_le_khoanh",   "bad_high": True,  "fmt": "{:.2f}%"},
        {"name": "NPL%",       "col": "ty_le_npl",      "bad_high": True,  "fmt": "{:.2f}%"},
        {"name": "3m KHĐ%",    "col": "pct_3m_khd",     "bad_high": True,  "fmt": "{:.1f}%"},
        {"name": "Lãi tồn%",  "col": "pct_lai_ton",    "bad_high": True,  "fmt": "{:.2f}%"},
        {"name": "⭐ Điểm RR", "col": "diem_rui_ro",    "bad_high": False, "fmt": "{:.0f}"},
    ]

    z_cols:   list[list] = []
    txt_cols: list[list] = []

    for crit in criteria:
        col = crit["col"]
        if col not in df.columns:
            z_cols.append([0.5] * len(df))
            txt_cols.append(["N/A"] * len(df))
            continue

        vals = df[col].values.astype(float)
        v_min, v_max = vals.min(), vals.max()

        if v_max > v_min:
            norm = (vals - v_min) / (v_max - v_min)
        else:
            norm = [0.5] * len(vals)

        if not crit["bad_high"]:
            # Điểm RR: cao = tốt → invert để màu xanh = tốt
            norm = 1.0 - norm

        z_cols.append(norm.tolist())
        txt_cols.append([crit["fmt"].format(v) for v in vals])

    # Transpose: hàng = PGD, cột = tiêu chí
    z_matrix   = [[z_cols[j][i] for j in range(len(criteria))] for i in range(len(df))]
    txt_matrix = [[txt_cols[j][i] for j in range(len(criteria))] for i in range(len(df))]
    x_labels   = [c["name"] for c in criteria]

    colorscale = [
        [0.0,  "#1B5E20"],
        [0.25, "#4CAF50"],
        [0.5,  "#FFC107"],
        [0.75, "#FF5722"],
        [1.0,  "#B71C1C"],
    ]

    fig = go.Figure(go.Heatmap(
        z=z_matrix,
        x=x_labels,
        y=labels,
        text=txt_matrix,
        texttemplate="%{text}",
        colorscale=colorscale,
        showscale=True,
        hoverongaps=False,
        textfont={"size": 10, "color": "white"},
        colorbar=dict(
            title=dict(text="Rủi ro", font_size=10),
            tickvals=[0, 0.25, 0.5, 0.75, 1.0],
            ticktext=["Tốt", "Khá", "TB", "Cần ch.", "Cảnh báo"],
            tickfont_size=9,
        ),
        hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text="Heatmap Rủi ro Tín dụng 22 PGD  —  🟢 Tốt  /  🟡 Cần chú ý  /  🔴 Cảnh báo",
            font=dict(size=12, color="#B0BEC5"),
        ),
        height=max(480, len(df) * 30 + 100),
        margin=dict(l=10, r=20, t=60, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#B0BEC5", size=11),
        xaxis=dict(side="top", tickfont_size=11),
        yaxis=dict(tickfont_size=10),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        "📌 Xếp từ **rủi ro nhất** (trên) → **tốt nhất** (dưới) theo Điểm RR tổng hợp.  "
        "Điểm RR = 0–100 (100 = lành mạnh nhất). Màu xanh = tốt, đỏ = cần chú ý."
    )


# ── Bảng đa chiều ─────────────────────────────────────────────────────────────

def _render_ranking_table(df_show: pd.DataFrame, upload_info_map: dict) -> None:
    """Bảng 12 tiêu chí đa chiều, xếp hạng theo Điểm RR tổng hợp."""
    df_t = df_show.copy().sort_values("diem_rui_ro", ascending=False).reset_index(drop=True)
    df_t.insert(0, "#", range(1, len(df_t) + 1))

    df_t["PGD"]              = df_t["ten_pgd"]
    df_t["Dư nợ (tỷ)"]      = (df_t["du_no"] / 1e9).round(3)
    df_t["NQH%"]             = df_t["ty_le_nqh"].round(2)
    df_t["Khoanh%"]          = df_t["ty_le_khoanh"].round(2)
    df_t["NPL%"]             = df_t["ty_le_npl"].round(2)
    df_t["3m KHĐ%"]          = df_t["pct_3m_khd"].round(1)
    df_t["Lãi tồn (tr)"]     = (df_t["lai_ton"] / 1e6).round(0).astype(int)
    df_t["ĐH tháng (tr)"]    = (df_t["no_den_han_thang"] / 1e6).round(0).astype(int)
    df_t["ĐH 3 tháng (tr)"]  = (df_t["no_den_han_3thang"] / 1e6).round(0).astype(int)
    df_t["Số KH"]             = df_t["so_kh"]
    df_t["BQ/hộ (tr)"]        = (df_t["dn_binh_quan_ho"] / 1e6).round(1)
    df_t["⭐ Điểm RR"]        = df_t["diem_rui_ro"].round(1)
    df_t["HSTD"]              = df_t["ten_pgd"].map(
        lambda dv: ("✅ " + upload_info_map.get(dv, (False, "—"))[1])
        if upload_info_map.get(dv, (False, ""))[0] else "❌"
    )

    cols_out = [
        "#", "PGD", "Dư nợ (tỷ)", "NQH%", "Khoanh%", "NPL%",
        "3m KHĐ%", "Lãi tồn (tr)", "ĐH tháng (tr)", "ĐH 3 tháng (tr)",
        "Số KH", "BQ/hộ (tr)", "⭐ Điểm RR", "HSTD",
    ]
    df_out = df_t[cols_out]

    def _style_nqh(val):
        if isinstance(val, (int, float)):
            if val >= 3:
                return "background-color:rgba(239,83,80,.15);color:#EF5350;font-weight:700"
            if val >= 1:
                return "background-color:rgba(255,167,38,.12);color:#FFA726;font-weight:700"
            return "color:#66BB6A"
        return ""

    def _style_rr(val):
        if isinstance(val, (int, float)):
            if val < 60:
                return "background-color:rgba(239,83,80,.15);color:#EF5350;font-weight:700"
            if val < 80:
                return "background-color:rgba(255,167,38,.12);color:#FFA726;font-weight:700"
            return "background-color:rgba(102,187,106,.10);color:#66BB6A;font-weight:700"
        return ""

    styled = (
        df_out.style
        .map(_style_nqh, subset=["NQH%", "Khoanh%", "NPL%"])
        .map(_style_rr, subset=["⭐ Điểm RR"])
        .format({
            "Dư nợ (tỷ)":     lambda v: vn(v, 3),
            "NQH%":           lambda v: f"{vn(v, 2)}%",
            "Khoanh%":        lambda v: f"{vn(v, 2)}%",
            "NPL%":           lambda v: f"{vn(v, 2)}%",
            "3m KHĐ%":        lambda v: f"{vn(v, 1)}%",
            "Lãi tồn (tr)":   lambda v: fmt_so(v),
            "ĐH tháng (tr)":  lambda v: fmt_so(v),
            "ĐH 3 tháng (tr)": lambda v: fmt_so(v),
            "Số KH":          lambda v: fmt_so(v),
            "BQ/hộ (tr)":     lambda v: vn(v, 1),
            "⭐ Điểm RR":    lambda v: f"{v:.1f}".replace(".", ","),
        })
    )

    st.dataframe(styled, use_container_width=True, height=min(750, len(df_out) * 37 + 55))


# ── Drill-down ────────────────────────────────────────────────────────────────

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

    tong_dn = df_pgd[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_pgd.columns else 0
    st.caption(f"Tổng {len(df_pgd):,} khoản vay — dư nợ: {fmt_ty(tong_dn)} triệu đồng")
    hien_thi_dataframe_phan_trang(df_pgd[cols_hien], key=f"drill_{ten_pgd}", height=400)


# ── Render chính ──────────────────────────────────────────────────────────────

def render(tab_parent=None, **kwargs):
    with TabContext(tab_parent):
        df = kwargs.get("df")

        st.header("🏢 Toàn cảnh 22 PGD")

        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload và merge trước.")
            return

        # ── Tính toán đa chiều ────────────────────────────────────────────
        ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
        from config import CACHE_HSTD
        from data.core import ts_file as _ts_file
        ts = _ts_file(CACHE_HSTD)

        try:
            df_cards = _cache_da_chieu_pgd(df, ts, "|".join(ds_don_vi))
        except Exception as e:
            logger.error("render tab_pgd_cards — _cache_da_chieu_pgd: %s", e, exc_info=True)
            st.error(f"Lỗi tính toán: {e}")
            return

        # Chỉ giữ PGD thực sự có dư nợ (loại Hội sở và PGD chưa upload)
        df_pgd_only = df_cards[df_cards["du_no"] > 0].copy()

        # ── KPI tổng toàn CN ─────────────────────────────────────────────
        tong_dn   = df_pgd_only["du_no"].sum()
        tong_nqh  = df_pgd_only["nqh"].sum()
        tong_npl  = (df_pgd_only["nqh"] + df_pgd_only["du_no_khoanh"]).sum() if "du_no_khoanh" in df_pgd_only.columns else tong_nqh
        tong_kh   = int(df_pgd_only["so_kh"].sum())
        tl_nqh_cn = tong_nqh / tong_dn * 100 if tong_dn > 0 else 0
        tl_npl_cn = tong_npl / tong_dn * 100 if tong_dn > 0 else 0
        bq_ho_cn  = tong_dn / tong_kh if tong_kh > 0 else 0
        n_upload  = sum(
            1 for dv in ds_don_vi
            if _pgd_file_path(dv).exists() or _pgd_khnv_path(dv).exists()
        )
        n_canh_bao = int((df_pgd_only["diem_rui_ro"] < 60).sum()) if "diem_rui_ro" in df_pgd_only.columns else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Tổng dư nợ CN",    vn(tong_dn / 1_000_000_000, 3) + " tỷ")
        c2.metric("NQH% toàn CN",     f"{tl_nqh_cn:.2f}%".replace(".", ","))
        c3.metric("NPL% (NQH+Khoanh)", f"{tl_npl_cn:.2f}%".replace(".", ","))
        c4.metric("BQ/hộ toàn CN",    vn(bq_ho_cn / 1_000_000, 1) + " tr")
        c5.metric(
            "PGD cần chú ý",
            f"{n_canh_bao} đơn vị",
            help="Số PGD có Điểm RR < 60 (Cảnh báo)",
        )

        # BQ mạng lưới
        n_pgd = int((df_pgd_only["du_no"] > 0).sum())
        bq_pgd = tong_dn / n_pgd if n_pgd > 0 else 0

        so_to = int(df.groupby([COT_TEN_PGD, COT_TEN_TO]).ngroups) if COT_TEN_TO in df.columns else 0
        so_hoi = int(df.groupby([COT_TEN_PGD, COT_DVUT]).ngroups) if COT_DVUT in df.columns else 0
        bq_to  = tong_dn / so_to  if so_to  > 0 else 0
        bq_hoi = tong_dn / so_hoi if so_hoi > 0 else 0

        cb1, cb2, cb3, cb4 = st.columns(4)
        cb1.metric("BQ/Phòng GD",     vn(bq_pgd / 1e6, 1) + " tr",
                   help=f"{n_pgd} đơn vị có dư nợ")
        cb2.metric("BQ/Tổ TK&VV",    vn(bq_to / 1e6, 1) + " tr" if so_to > 0 else "—",
                   help=f"{so_to:,} tổ" if so_to else "Không có cột Tên tổ")
        cb3.metric("BQ/Hội ĐVUT",    vn(bq_hoi / 1e6, 1) + " tr" if so_hoi > 0 else "—",
                   help=f"{so_hoi:,} Hội" if so_hoi else "Không có cột Tên ĐVUT")
        cb4.metric("File HSTD",       f"{n_upload}/{len(ds_don_vi)} đơn vị")

        st.divider()

        # ── Upload info map (dùng cho card + bảng) ───────────────────────
        upload_info_map = {dv: _upload_info(dv) for dv in ds_don_vi}

        # ── 4 Sub-tabs (lazy: chỉ render tab đang active) ───────────────
        _sub_labels = ["🃏 Thẻ PGD", "📊 Bảng Đa chiều", "🌡️ Heatmap Rủi ro", "📈 Biểu đồ"]
        _pgd_sub = st.radio(
            "Sub-tab", range(len(_sub_labels)),
            format_func=lambda i: _sub_labels[i],
            horizontal=True, key="pgd_cards_sub_tab", label_visibility="collapsed",
        )
        st.divider()

        # ─── Sub-tab 1: Thẻ PGD ──────────────────────────────────────────
        if _pgd_sub == 0:
            col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
            with col_f1:
                sapxep = st.selectbox(
                    "Sắp xếp theo",
                    ["⭐ Điểm RR (tốt nhất)", "⭐ Điểm RR (rủi ro nhất)",
                     "Dư nợ (giảm)", "NQH% (giảm)", "3m KHĐ% (giảm)",
                     "BQ/hộ (giảm)", "Tên PGD (A→Z)"],
                    key="pgd_cards_sort",
                )
            with col_f2:
                loc_upload = st.selectbox(
                    "Upload HSTD",
                    ["Tất cả", "Có file", "Thiếu file"],
                    key="pgd_cards_upload_filter",
                )
            with col_f3:
                loc_rr = st.selectbox(
                    "Mức Điểm RR",
                    ["Tất cả", "🔴 Cảnh báo (<60)", "🟡 Cần chú ý (60-80)", "🟢 Tốt (≥80)"],
                    key="pgd_cards_rr_filter",
                )

            sort_map = {
                "⭐ Điểm RR (tốt nhất)":  ("diem_rui_ro", False),
                "⭐ Điểm RR (rủi ro nhất)": ("diem_rui_ro", True),
                "Dư nợ (giảm)":           ("du_no", False),
                "NQH% (giảm)":            ("ty_le_nqh", False),
                "3m KHĐ% (giảm)":         ("pct_3m_khd", False),
                "BQ/hộ (giảm)":           ("dn_binh_quan_ho", False),
                "Tên PGD (A→Z)":          ("ten_pgd", True),
            }
            sort_col, sort_asc = sort_map[sapxep]
            df_show = df_cards.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)

            upload_status = {
                dv: (_pgd_file_path(dv).exists() or _pgd_khnv_path(dv).exists())
                for dv in ds_don_vi
            }
            if loc_upload == "Có file":
                df_show = df_show[df_show["ten_pgd"].map(upload_status).fillna(False)]
            elif loc_upload == "Thiếu file":
                df_show = df_show[~df_show["ten_pgd"].map(upload_status).fillna(False)]

            if loc_rr == "🔴 Cảnh báo (<60)":
                df_show = df_show[df_show["diem_rui_ro"] < 60]
            elif loc_rr == "🟡 Cần chú ý (60-80)":
                df_show = df_show[(df_show["diem_rui_ro"] >= 60) & (df_show["diem_rui_ro"] < 80)]
            elif loc_rr == "🟢 Tốt (≥80)":
                df_show = df_show[df_show["diem_rui_ro"] >= 80]

            # Rank dư nợ để hiện trên card
            df_dn_rank = df_cards.sort_values("du_no", ascending=False).reset_index(drop=True)
            rank_map = {r["ten_pgd"]: i + 1 for i, r in df_dn_rank.iterrows()}

            # Drill-down state
            drill_key = "pgd_cards_drilldown"
            if drill_key not in st.session_state:
                st.session_state[drill_key] = None

            st.markdown(_CARD_CSS, unsafe_allow_html=True)

            # Hiển thị số PGD đang lọc
            if len(df_show) < len(df_cards):
                st.caption(f"Hiển thị {len(df_show)}/{len(df_cards)} đơn vị")

            COLS = 3
            for chunk in [df_show.iloc[i:i + COLS] for i in range(0, len(df_show), COLS)]:
                cols = st.columns(COLS)
                for col, (_, row) in zip(cols, chunk.iterrows()):
                    with col:
                        ok, ts_str = upload_info_map.get(row["ten_pgd"], (False, "—"))
                        rank = rank_map.get(row["ten_pgd"], 0)
                        st.markdown(
                            _render_card_html(row.to_dict(), ok, ts_str, rank),
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "🔍 Xem chi tiết",
                            key=f"drill_btn_{row['ten_pgd']}",
                            use_container_width=True,
                        ):
                            cur = st.session_state.get(drill_key)
                            st.session_state[drill_key] = (
                                None if cur == row["ten_pgd"] else row["ten_pgd"]
                            )
                            st.rerun()

            selected = st.session_state.get(drill_key)
            if selected:
                st.divider()
                if st.button("✖ Đóng chi tiết", key="drill_close"):
                    st.session_state[drill_key] = None
                    st.rerun()
                _render_drilldown(df, selected)

        # ─── Sub-tab 2: Bảng Đa chiều ───────────────────────────────────
        elif _pgd_sub == 1:
            st.caption(
                "Xếp hạng từ **tốt nhất** (top) → **cần chú ý** (cuối) theo Điểm RR tổng hợp. "
                "⭐ Điểm RR: 0–100 (100 = lành mạnh nhất). "
                "Màu 🟢 ≥80 | 🟡 60–79 | 🔴 <60."
            )
            _render_ranking_table(df_cards, upload_info_map)

            # Chú thích công thức điểm RR
            with st.expander("ℹ️ Công thức Điểm RR tổng hợp"):
                st.markdown("""
| Tiêu chí | Trọng số | Ý nghĩa |
|---|---|---|
| NQH% | **35%** | Nợ quá hạn / tổng dư nợ |
| 3m KHĐ% | **25%** | Khoản vay không hoạt động 3 tháng / tổng món vay |
| Khoanh% | **20%** | Dư nợ khoanh / tổng dư nợ |
| Lãi tồn% | **15%** | Lãi tồn (TH+QH) / tổng dư nợ |
| Đến hạn 3T% | **5%** | Dư nợ đến hạn 90 ngày / tổng dư nợ |

**Cách tính:** Mỗi tiêu chí quy về điểm 0–100, rồi nhân trọng số.
Ví dụ: NQH 3% → điểm NQH = 100 − 3×15 = 55 → đóng góp 55×35% = 19,25 điểm.
                """)

        # ─── Sub-tab 3: Heatmap ──────────────────────────────────────────
        elif _pgd_sub == 2:
            _render_heatmap(df_cards)

        # ─── Sub-tab 4: Biểu đồ ─────────────────────────────────────────
        elif _pgd_sub == 3:
            tab_c1, tab_c2 = st.tabs(["📊 Dư nợ & NQH%", "💰 BQ/hộ xếp hạng"])
            with tab_c1:
                _render_chart(df_cards)
            with tab_c2:
                _render_chart_bq(df_cards)
