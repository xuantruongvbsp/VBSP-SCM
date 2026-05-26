"""Tab Card 22 PGD — tổng quan nhanh từng đơn vị.

Mỗi PGD hiển thị 1 card gồm:
  - Dư nợ (tỷ đồng)
  - Tỷ lệ NQH%
  - Khoản đến hạn trong tháng (triệu đồng)
  - Trạng thái upload file HSTD (có/thiếu + ngày cập nhật)

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
    background: #0D1B2A;
    border: 1px solid #1E3A5F;
    border-radius: 10px;
    padding: 14px 16px 12px;
    margin-bottom: 10px;
    position: relative;
    transition: border-color 0.2s;
}
.pgd-card:hover { border-color: #2979FF; }
.pgd-card-title {
    font-size: 13px; font-weight: 700;
    color: #90CAF9; margin-bottom: 8px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pgd-card-kpi { display: flex; gap: 8px; flex-wrap: wrap; }
.pgd-kpi-block { flex: 1 1 45%; }
.pgd-kpi-label { font-size: 10px; color: #7B8EA0; margin-bottom: 1px; }
.pgd-kpi-value { font-size: 15px; font-weight: 700; color: #E3F2FD; }
.pgd-kpi-value.red  { color: #EF5350; }
.pgd-kpi-value.amber{ color: #FFA726; }
.pgd-kpi-value.green{ color: #66BB6A; }
.pgd-upload-row {
    font-size: 10px; color: #7B8EA0;
    margin-top: 8px; border-top: 1px solid #1E3A5F; padding-top: 6px;
}
.pgd-upload-ok  { color: #66BB6A; }
.pgd-upload-miss{ color: #EF5350; }
</style>
"""


def _nqh_color(ty_le: float) -> str:
    if ty_le >= 3:
        return "red"
    if ty_le >= 1:
        return "amber"
    return "green"


def _render_card_html(row: dict, upload_ok: bool, upload_ts: str) -> str:
    du_no_str   = fmt_ty(row["du_no"])
    nqh_pct     = row["ty_le_nqh"]
    nqh_str     = f"{nqh_pct:.2f}%"
    dh_str      = fmt_so(int(row["no_den_han_thang"] / 1_000_000)) + " tr"
    so_kh_str   = fmt_so(int(row["so_kh"]))
    color       = _nqh_color(nqh_pct)

    upload_cls  = "pgd-upload-ok" if upload_ok else "pgd-upload-miss"
    upload_icon = "✅" if upload_ok else "❌"
    upload_lbl  = f"HSTD: {upload_icon} {upload_ts}"

    return f"""
<div class="pgd-card">
  <div class="pgd-card-title">🏢 {row['ten_pgd']}</div>
  <div class="pgd-card-kpi">
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Dư nợ</div>
      <div class="pgd-kpi-value">{du_no_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">NQH%</div>
      <div class="pgd-kpi-value {color}">{nqh_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Đến hạn tháng này</div>
      <div class="pgd-kpi-value">{dh_str}</div>
    </div>
    <div class="pgd-kpi-block">
      <div class="pgd-kpi-label">Số KH</div>
      <div class="pgd-kpi-value">{so_kh_str}</div>
    </div>
  </div>
  <div class="pgd-upload-row">
    <span class="{upload_cls}">{upload_lbl}</span>
  </div>
</div>"""


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
        df      = kwargs.get("df")
        role    = kwargs.get("role", "")

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

        # ── Tóm tắt toàn CN ──────────────────────────────────────────────
        tong_dn   = df_cards["du_no"].sum()
        tong_nqh  = df_cards["nqh"].sum()
        tl_nqh_cn = tong_nqh / tong_dn * 100 if tong_dn > 0 else 0
        n_upload  = sum(1 for dv in ds_don_vi if _pgd_file_path(dv).exists())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng dư nợ CN", fmt_ty(tong_dn))
        c2.metric("NQH% toàn CN", f"{tl_nqh_cn:.2f}%")
        c3.metric("Đến hạn tháng này", fmt_ty(df_cards["no_den_han_thang"].sum()))
        c4.metric("Đơn vị có file HSTD", f"{n_upload}/{len(ds_don_vi)}")

        st.divider()

        # ── Bộ lọc & sắp xếp ─────────────────────────────────────────────
        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            sapxep = st.selectbox(
                "Sắp xếp theo",
                ["Dư nợ (giảm)", "NQH% (giảm)", "Đến hạn tháng (giảm)", "Tên PGD (A→Z)"],
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
            "Dư nợ (giảm)":            ("du_no", False),
            "NQH% (giảm)":             ("ty_le_nqh", False),
            "Đến hạn tháng (giảm)":    ("no_den_han_thang", False),
            "Tên PGD (A→Z)":           ("ten_pgd", True),
        }
        sort_col, sort_asc = sort_map[sapxep]
        df_show = df_cards.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)

        # Lấy trạng thái upload để lọc
        upload_status = {dv: _pgd_file_path(dv).exists() for dv in ds_don_vi}

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
                    ok, ts_str = _upload_info(row["ten_pgd"])
                    st.markdown(_render_card_html(row.to_dict(), ok, ts_str), unsafe_allow_html=True)
                    if st.button(
                        f"🔍 Xem chi tiết",
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

        # ── Bảng tổng hợp dạng bảng ───────────────────────────────────────
        with st.expander("📋 Xem dạng bảng tổng hợp", expanded=False):
            df_table = df_show.copy()
            df_table["Dư nợ (tỷ)"]           = (df_table["du_no"] / 1_000_000_000).round(3)
            df_table["NQH (tỷ)"]              = (df_table["nqh"] / 1_000_000_000).round(3)
            df_table["NQH%"]                  = df_table["ty_le_nqh"].map(lambda x: f"{x:.2f}%")
            df_table["Đến hạn tháng (tr)"]    = (df_table["no_den_han_thang"] / 1_000_000).round(0).astype(int)
            df_table["Số KH"]                 = df_table["so_kh"]
            _uinfo = {dv: _upload_info(dv) for dv in df_show["ten_pgd"]}
            df_table["Upload HSTD"]           = df_table["ten_pgd"].map(
                lambda dv: ("✅ " + _uinfo[dv][1]) if _uinfo[dv][0] else "❌ Thiếu"
            )
            df_table = df_table.rename(columns={"ten_pgd": "PGD"})
            hien_thi_dataframe_phan_trang(
                df_table[["PGD", "Dư nợ (tỷ)", "NQH (tỷ)", "NQH%", "Đến hạn tháng (tr)", "Số KH", "Upload HSTD"]],
                key="pgd_cards_table",
                height=500,
            )
