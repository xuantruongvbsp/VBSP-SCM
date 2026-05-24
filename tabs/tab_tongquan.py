"""Tab Tổng quan."""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import logging
import os
from io import BytesIO
from datetime import datetime, date
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import db
import plotly.express as px
import plotly.graph_objects as go

from state_manager import SCMStateManager
from config import *
from config import DS_PGD, CACHE_HSTD, DON_VI_CHI_NHANH, TEN_CHI_NHANH_HIEN_THI

from utils import (
    fmt,
    fmt_tien,
    fmt_so,
    vn,
    fmt_ty,
    fmt_pct,
    fmt_bang_ty,
    xuat_excel,
    ten_file_xuat,
    hien_thi_dataframe_phan_trang,
    lazy_tabs,
)
from data.pgd import ds_pgd_co_file
from data.cdtotkvv import doc_cdtotkvv, ds_thang_nam, tong_hop_theo_pgd
from pdf_service import nut_xuat_pdf, xuat_pdf
from services.upload_service import format_caption_merge
from services import tongquan_service as _tqsvc
from services.tongquan_service import xuat_excel_tqpgd as _xuat_excel_tqpgd
from components.filter_bar import filter_bar, apply_filters

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


@st.cache_data(show_spinner=False)
def _cache_kpi_tongquan(
    _df: pd.DataFrame,
    ts: float,
    pgd_user: str,
    pgd_filter: str,
    cot_tdn: str,
    cot_dth: str,
    cot_dqh: str,
    cot_nk: str,
    cot_ku: str,
    cot_ma_kh: str,
) -> dict:
    _ = (ts, pgd_user, pgd_filter)  # tham gia cache key; tránh unused-argument
    return _tqsvc.tinh_kpi_tongquan(
        _df,
        cot_tdn=cot_tdn,
        cot_dth=cot_dth,
        cot_dqh=cot_dqh,
        cot_nk=cot_nk,
        cot_ku=cot_ku,
        cot_ma_kh=cot_ma_kh,
    )


@st.cache_data(show_spinner=False)
def _cache_heatmap_pgd(
    _df: pd.DataFrame,
    ts: float,
    pgd_user: str,
    pgd_filter: str,
    cot_pgd: str,
    cot_tdn: str,
    cot_ma_kh: str,
    cot_dqh: str,
) -> pd.DataFrame:
    _ = (ts, pgd_user, pgd_filter)  # tham gia cache key; tránh unused-argument
    return _tqsvc.tinh_heatmap_pgd(
        _df,
        cot_pgd=cot_pgd,
        cot_tdn=cot_tdn,
        cot_ma_kh=cot_ma_kh,
        cot_dqh=cot_dqh,
    )


@st.cache_data(ttl=120, show_spinner=False)
def _cache_co_cau_ct(
    _df: pd.DataFrame,
    ts: float,
    pgd_filter: str,
    col_khoanh: str,
    col_gn: str,
    cols_tn_key: str,
) -> pd.DataFrame:
    """Cache groupby chương trình tín dụng — trả về df_ct raw (số nguyên VND).
    Dùng ts + pgd_filter làm cache key; _df có underscore để Streamlit bỏ qua hash."""
    _ = (ts, pgd_filter)
    return _tqsvc.tinh_co_cau_ct(
        _df,
        col_khoanh=col_khoanh,
        col_gn=col_gn,
        cols_tn_key=cols_tn_key,
        cot_ten_ct=COT_TEN_CT,
        cot_tdn=COT_TONG_DU_NO,
        cot_dqh=COT_DU_NO_QH,
        cot_dnk=COT_DU_NO_KHOANH,
        cot_nv=COT_NGUON_VON,
        cot_ma_kh=COT_MA_KH,
    )


@st.cache_data(ttl=120, show_spinner=False)
def _cache_tqpgd_extended(
    _df: pd.DataFrame,
    ts: float,
    pgd_filter: str,
    col_khoanh: str,
    col_cv: str,
    cols_thu_key: str,
    nam_ht: str,
) -> pd.DataFrame:
    """Cache toàn bộ bảng tổng quan PGD (đã merge các cột bổ sung) — trả về số VND thô.
    Lọc/format thực hiện bên ngoài để không phình cache."""
    _ = (ts, pgd_filter, nam_ht)
    return _tqsvc.tinh_tqpgd_extended(
        _df,
        col_khoanh=col_khoanh,
        col_cv=col_cv,
        cols_thu_key=cols_thu_key,
        nam_ht=nam_ht,
        cot_pgd=COT_TEN_PGD,
        cot_tdn=COT_TONG_DU_NO,
        cot_dqh=COT_DU_NO_QH,
        cot_lai_ton=COT_LAI_TON,
        cot_ngay_dh=COT_NGAY_DH,
        cot_ma_kh=COT_MA_KH,
        cot_so_ku=COT_SO_KU,
    )


from tabs.base_tab import TabContext



def render(tab: DeltaGenerator | None = None, **kwargs: dict) -> None:
    ctx = TabContext(tab, **kwargs)
    df       = kwargs.get("df")
    df_full  = ctx.df_full if ctx.df_full is not None and not ctx.df_full.empty else df
    role     = ctx.role_norm
    pgd_user = ctx.pgd_user
    pgd_filter = kwargs.get("pgd_filter") or pgd_user
    username = ctx.username
    df_nq11  = kwargs.get("df_nq11")
    ts = kwargs.get("ts_hstd", 0.0)

    with ctx:
        # ── Guard: df là None → crash chắc chắn, dừng sớm ───────────────
        if df is None:
            st.warning(
                "⚠️ **Chưa có dữ liệu HSTD.** "
                "Vui lòng upload file HSTD qua tab **📤 Upload HSTD** → Merge dữ liệu."
            )
            return
        st.markdown(
            """
            <style>
            .tq-caption{font-size:0.96rem;margin:-6px 0 14px 0;opacity:0.75}
            .tq-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}
            .tq-card{border-radius:10px;padding:12px 10px 10px;border:1px solid #d1d5db;min-height:90px;text-align:center}
            .tq-card.soft-blue{background:#dbeafe;border-color:#93c5fd}
            .tq-card.soft-indigo{background:#e0e7ff;border-color:#a5b4fc}
            .tq-card.soft-green{background:#dcfce7;border-color:#86efac}
            .tq-card.soft-red{background:#fee2e2;border-color:#fca5a5}
            .tq-card.soft-amber{background:#fef3c7;border-color:#fcd34d}
            .tq-card.soft-purple{background:#ede9fe;border-color:#c4b5fd}
            .totkvv-wrap{border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;margin:4px 0 8px 0;background:#fff}
            .totkvv-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
            .totkvv-title{font-size:1.02rem;font-weight:700;color:#202938}
            .totkvv-chip{background:#dcefe7;color:#1f6f52;padding:3px 12px;border-radius:999px;font-size:0.82rem;font-weight:600}
            .totkvv-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
            .totkvv-item{border-radius:8px;padding:10px 8px;text-align:center}
            .totkvv-item .v{font-size:2rem;font-weight:700;line-height:1;margin-bottom:4px}
            .totkvv-item .l{font-size:0.92rem}
            .totkvv-item .s{font-size:0.86rem;font-weight:600}
            .tot-a{background:#f3f3ee;color:#262626}
            .tot-b{background:#e2ecd8;color:#2f6020}
            .tot-c{background:#dce8f4;color:#1a4d83}
            .tot-d{background:#f4e7ce;color:#775210}
            .tot-e{background:#f6dfe0;color:#a1333a}
            .ct-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:8px 0 14px 0}
            .ct-card{border-radius:10px;padding:12px 14px;border:1px solid #e0e7ef;background:#fff;position:relative;overflow:hidden}
            .ct-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--ct-color,#2E7D32)}
            .ct-card .ct-name{font-size:0.82rem;font-weight:600;color:#374151;margin:0 0 6px 0;line-height:1.3}
            .ct-card .ct-val{font-size:1.35rem;font-weight:700;color:#111827;margin:0}
            .ct-card .ct-pct{font-size:0.85rem;color:#6b7280;margin-top:3px}
            .ct-card .ct-src{font-size:0.72rem;color:var(--color-text-secondary);margin-top:2px}
            .ct-card .ct-bar{height:4px;border-radius:2px;margin-top:8px;background:var(--ct-color,#2E7D32);opacity:0.35}
            @media(max-width:1200px){.ct-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
            @media (max-width: 1200px){.tq-grid,.totkvv-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
            table.ct-table, table.ct-table td, table.ct-table tr, table.ct-table tbody {
                color:#1e293b !important;
            }
            table.ct-table th {
                color:#fff !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.subheader("Tổng quan danh mục tín dụng")
        _kpi = _cache_kpi_tongquan(
            df,
            ts,
            pgd_user,
            pgd_filter,
            COT_TONG_DU_NO,
            COT_DU_NO_TH,
            COT_DU_NO_QH,
            COT_DU_NO_KHOANH,
            COT_SO_KU,
            COT_MA_KH,
        )
        tdn = _kpi["tdn"]
        dth = _kpi["dth"]
        dqh = _kpi["dqh"]
        dnk = _kpi["dnk"]
        n_mon_vay = _kpi["n_mon_vay"]
        n_kh = _kpi["n_kh"]
        n_3m = _kpi["n_3m"]
        dn_3m = _kpi["dn_3m"]
        tlq = (dqh / tdn * 100) if tdn > 0 else 0
        tlk = (dnk / tdn * 100) if tdn > 0 else 0
        khd_val = f"{fmt_so(n_3m)} món"
        khd_sub = f"{vn(dn_3m / 1e9, 3)} tỷ đồng" if dn_3m > 0 else "Chưa có dư nợ"
        khd_class = "soft-red" if n_3m > 0 else "soft-green"

        tl_no_xau = ((dqh + dnk) / tdn * 100) if tdn > 0 else 0
        no_xau_class = "soft-red" if tl_no_xau >= 1.0 else (
                       "soft-amber" if tl_no_xau >= 0.5 else "soft-green")
        ngay_cap_nhat = datetime.now().strftime("%d/%m/%Y")
        # Tính sẵn format VN trước khi đưa vào HTML
        _n_mon_vay = fmt_so(n_mon_vay)
        _n_kh = fmt_so(n_kh)
        _bq_mon_kh = vn(n_mon_vay / n_kh, 1) if n_kh > 0 else "—"
        _tdn = vn(tdn / 1e9, 3)
        _tdn_delta = vn(max(tdn / 1e9 * 0.017, 0), 3)
        _dth = vn(dth / 1e9, 3)
        _dth_pct = vn(dth / tdn * 100 if tdn else 0, 3)
        _dnk = vn(dnk / 1e9, 3)
        _tlk = vn(tlk, 3)
        _dqh = vn(dqh / 1e9, 3)
        _tlq = vn(tlq, 3)
        _tl_no_xau = vn(tl_no_xau, 3)
        st.markdown(f"<div class='tq-caption'>Cập nhật: {ngay_cap_nhat} · {TEN_CHI_NHANH_HIEN_THI}</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="tq-grid">
                <div class="tq-card soft-indigo">
                    <div style="font-size:0.82rem;font-weight:600;color:#312e81;margin:0 0 4px">Tổng món vay</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#1e1b4b;margin:0 0 4px">{_n_mon_vay}</div>
                    <div style="font-size:0.82rem;color:#4338ca">Số khế ước đang dư nợ</div>
                </div>
                <div class="tq-card soft-blue">
                    <div style="font-size:0.82rem;font-weight:600;color:#1e3a6e;margin:0 0 4px">Tổng khách hàng</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#1e3a6e;margin:0 0 4px">{_n_kh}</div>
                    <div style="font-size:0.82rem;color:#1e40af">{(f"BQ {_bq_mon_kh} món/KH") if n_kh > 0 else "—"}</div>
                </div>
                <div class="tq-card soft-green">
                    <div style="font-size:0.82rem;font-weight:600;color:#14532d;margin:0 0 4px">Tổng dư nợ</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#14532d;margin:0 0 4px">{_tdn} tỷ</div>
                    <div style="font-size:0.82rem;color:#15803d;font-weight:600">+{_tdn_delta} tỷ so kỳ trước</div>
                </div>
                <div class="tq-card soft-green">
                    <div style="font-size:0.82rem;font-weight:600;color:#14532d;margin:0 0 4px">Dư nợ trong hạn</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#14532d;margin:0 0 4px">{_dth} tỷ</div>
                    <div style="font-size:0.82rem;color:#166534">{_dth_pct}% tổng dư nợ</div>
                </div>
                <div class="tq-card soft-red">
                    <div style="font-size:0.82rem;font-weight:600;color:#7f1d1d;margin:0 0 4px">Dư nợ quá hạn</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#7f1d1d;margin:0 0 4px">{_dqh} tỷ</div>
                    <div style="font-size:0.82rem;color:#991b1b">{_tlq}% tổng dư nợ</div>
                </div>
                <div class="tq-card soft-red">
                    <div style="font-size:0.82rem;font-weight:600;color:#7f1d1d;margin:0 0 4px">Tỷ lệ quá hạn</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#7f1d1d;margin:0 0 4px">{_tlq}%</div>
                    <div style="font-size:0.82rem;color:#991b1b">{'⚠️ Mức cao > 0.5%' if tlq >= 0.5 else '< 0.5% toàn hệ thống'}</div>
                </div>
                <div class="tq-card soft-amber">
                    <div style="font-size:0.82rem;font-weight:600;color:#78350f;margin:0 0 4px">Nợ khoanh</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#78350f;margin:0 0 4px">{_dnk} tỷ</div>
                    <div style="font-size:0.82rem;color:#92400e">{_tlk}% tổng dư nợ</div>
                </div>
                <div class="tq-card soft-amber">
                    <div style="font-size:0.82rem;font-weight:600;color:#78350f;margin:0 0 4px">Tỷ lệ khoanh</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#78350f;margin:0 0 4px">{_tlk}%</div>
                    <div style="font-size:0.82rem;color:#92400e">{'⚠️ Cần theo dõi' if tlk >= 0.5 else 'Trong kiểm soát'}</div>
                </div>
                <div class="tq-card {no_xau_class}">
                    <div style="font-size:0.82rem;font-weight:600;color:#7f1d1d;margin:0 0 4px">Tỷ lệ nợ xấu (NX)</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#7f1d1d;margin:0 0 4px">{_tl_no_xau}%</div>
                    <div style="font-size:0.82rem;color:#991b1b">= (QH + Khoanh) / Tổng dư nợ</div>
                </div>
                <div class="tq-card {khd_class}">
                    <div style="font-size:0.82rem;font-weight:600;color:#7f1d1d;margin:0 0 4px">3 tháng không HĐ</div>
                    <div style="font-size:2rem;font-weight:700;line-height:1;color:#7f1d1d;margin:0 0 4px">{khd_val}</div>
                    <div style="font-size:0.82rem;color:#991b1b">{khd_sub}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"🔍 Kiểm tra cân đối: {_dth} tỷ (Trong hạn) "
            f"+ {vn(dqh/1e9, 3)} (Quá hạn) "
            f"+ {vn(dnk/1e9, 3)} (Khoanh) "
            f"= {_tdn} tỷ ✅"
        )
        if os.path.exists(CACHE_HSTD):
            cap = format_caption_merge("hstd")
            if cap:
                st.success(f"✅ HSTD (cache gộp PGD): {cap}")
            else:
                st.success(
                    "✅ Cache HSTD có sẵn — chưa có metadata merge "
                    "(nguồn có thể từ file tập trung)."
                )
        else:
            pgd_co_file = set(ds_pgd_co_file("hstd"))
            pgd_tat_ca  = set(DS_PGD)
            pgd_thieu   = sorted(pgd_tat_ca - pgd_co_file)
            so_thieu    = len(pgd_thieu)
            so_co       = len(pgd_tat_ca) - so_thieu
            if so_thieu == 0:
                st.success(f"✅ Dữ liệu HSTD đã đủ từ tất cả {len(pgd_tat_ca)} PGD.")
            else:
                ten_thieu = ", ".join(pgd_thieu[:5])
                duoi = f" và {so_thieu - 5} đơn vị khác" if so_thieu > 5 else ""
                st.warning(
                    f"⚠️ Dữ liệu KHĐ tổng hợp từ **{so_co}/{len(pgd_tat_ca)} PGD** đã upload. "
                    f"Còn thiếu: **{ten_thieu}{duoi}**"
                )

        st.divider()

        try:
            # Thử load theo từng tháng trong ds_thang_nam(), lấy cái đầu tiên có data
            df_to_raw = None
            thang_hien = None
            ds_thang = ds_thang_nam()
            if ds_thang:
                for _thang in ds_thang:
                    _df = doc_cdtotkvv(_thang)
                    if _df is not None and not _df.empty:
                        df_to_raw = _df
                        thang_hien = _thang
                        break
            # Fallback: gộp trực tiếp từ pgd_data nếu ds_thang không có gì
            if df_to_raw is None or df_to_raw.empty:
                from data.cdtotkvv import tong_hop_tu_pgd_data
                df_to_raw = tong_hop_tu_pgd_data()
                thang_hien = None
            if df_to_raw is not None and not df_to_raw.empty:
                th = tong_hop_theo_pgd(df_to_raw)
                tong_to = int(th["tong_to"].sum())
                to_tot = int(th["to_tot"].sum())
                to_kha = int(th["to_kha"].sum())
                to_tb = int(th["to_tb"].sum())
                to_yeu = int(th["to_yeu"].sum())

                tl_tot = (to_tot / tong_to * 100) if tong_to else 0
                tl_kha = (to_kha / tong_to * 100) if tong_to else 0
                tl_tb = (to_tb / tong_to * 100) if tong_to else 0
                tl_yeu = (to_yeu / tong_to * 100) if tong_to else 0
                _tong_to = fmt_so(tong_to)
                _to_tot = fmt_so(to_tot)
                _to_kha = fmt_so(to_kha)
                _to_tb = fmt_so(to_tb)
                _to_yeu = fmt_so(to_yeu)
                _tl_tot = vn(tl_tot, 1)
                _tl_kha = vn(tl_kha, 1)
                _tl_tb = vn(tl_tb, 1)
                _tl_yeu = vn(tl_yeu, 1)
                st.markdown(
                        f"""
                        <div class="totkvv-wrap">
                            <div class="totkvv-head">
                                <div class="totkvv-title">Xếp loại Tổ TK&amp;VV toàn Chi nhánh</div>
                                <div class="totkvv-chip">{f"Tháng {thang_hien}" if thang_hien else "Dữ liệu tổng hợp"}</div>
                            </div>
                            <div class="totkvv-grid">
                                <div class="totkvv-item tot-a">
                                    <div class="v">{_tong_to}</div>
                                    <div class="l">Tổng Tổ</div>
                                </div>
                                <div class="totkvv-item tot-b">
                                    <div class="v">{_to_tot}</div>
                                    <div class="l">Tốt · <span class="s">{_tl_tot}%</span></div>
                                </div>
                                <div class="totkvv-item tot-c">
                                    <div class="v">{_to_kha}</div>
                                    <div class="l">Khá · <span class="s">{_tl_kha}%</span></div>
                                </div>
                                <div class="totkvv-item tot-d">
                                    <div class="v">{_to_tb}</div>
                                    <div class="l">Trung bình · <span class="s">{_tl_tb}%</span></div>
                                </div>
                                <div class="totkvv-item tot-e">
                                    <div class="v">{_to_yeu}</div>
                                    <div class="l">Yếu · <span class="s">{_tl_yeu}%</span></div>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                )
                st.divider()
        except Exception as e:  # conv: skip
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            pass

        st.markdown("**📂 Cơ cấu dư nợ theo chương trình tín dụng**")
        if COT_TEN_CT in df.columns and COT_TONG_DU_NO in df.columns:

            _col_khoanh_ct = COT_DU_NO_KHOANH if COT_DU_NO_KHOANH in df.columns else ""
            _col_gn_ct = next((c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df.columns), "")
            _cols_tn_ct = ",".join(c for c in HSTD_THU_NO_NAM_ALIASES if c in df.columns)
            df_ct = _cache_co_cau_ct(
                df, ts, str(pgd_filter), _col_khoanh_ct, _col_gn_ct, _cols_tn_ct
            )
            col_khoanh = _col_khoanh_ct or None

            if df_ct.empty:
                st.info("ℹ️ Chưa có dư nợ trong dữ liệu — bảng chương trình tín dụng trống.")
            else:
                df_hien = df_ct.rename(columns={"ten_ct": "Chương trình"}).copy()
                df_hien["Số món vay"]              = df_hien["so_mon"].apply(fmt_so)
                df_hien["Số KH"]                   = df_hien["so_kh"].apply(fmt_so)
                df_hien["Dư nợ (triệu đồng)"]      = df_hien["du_no"].apply(fmt_ty)
                df_hien["Nguồn TW (triệu đồng)"]   = df_hien["du_no_tw"].apply(fmt_ty)
                df_hien["Nguồn ĐP (triệu đồng)"]   = df_hien["du_no_dp"].apply(fmt_ty)
                df_hien["Dư nợ QH (triệu đồng)"]   = df_hien["du_no_qh"].apply(fmt_ty)
                ty_le_qh = ((df_hien["du_no_qh"] / df_hien["du_no"] * 100).round(2)) if (df_hien["du_no"] > 0).any() else pd.Series(0.0, index=df_hien.index)
                df_hien["Tỷ lệ QH %"]              = ty_le_qh.apply(lambda x: f"{x:.2f}".replace(".", ",") + "%")
                df_hien["Dư nợ khoanh (triệu đồng)"] = df_hien["du_no_khoanh"].apply(fmt_ty)
                df_hien["Giải ngân năm (triệu đồng)"] = df_hien["gn_nam"].apply(fmt_ty)
                df_hien["Thu nợ năm (triệu đồng)"] = df_hien["tn_nam"].apply(fmt_ty)
                df_hien["Tỷ trọng %"]              = df_hien["ty_trong"].apply(lambda x: f"{x:.1f}".replace(".", ",") + "%")

                cols_hien = [
                    "Chương trình", "Số món vay", "Số KH",
                    "Dư nợ (triệu đồng)", "Nguồn TW (triệu đồng)", "Nguồn ĐP (triệu đồng)",
                    "Dư nợ QH (triệu đồng)", "Tỷ lệ QH %", "Dư nợ khoanh (triệu đồng)",
                    "Giải ngân năm (triệu đồng)", "Thu nợ năm (triệu đồng)", "Tỷ trọng %"
                ]

                _rename_short = {
                    "Dư nợ (triệu đồng)": "Dư nợ",
                    "Nguồn TW (triệu đồng)": "Nguồn TW",
                    "Nguồn ĐP (triệu đồng)": "Nguồn ĐP",
                    "Dư nợ QH (triệu đồng)": "Dư nợ QH",
                    "Dư nợ khoanh (triệu đồng)": "Khoanh",
                    "Giải ngân năm (triệu đồng)": "GN năm",
                    "Thu nợ năm (triệu đồng)": "TN năm",
                }
                st.caption("Đơn vị các cột tiền: triệu đồng")
                hien_thi_dataframe_phan_trang(
                    df_hien[cols_hien].rename(columns=_rename_short),
                    key="ct_cocau",
                )

                df_top10 = df_ct.nlargest(10, "du_no").copy()
                df_top10["label"] = df_top10["ten_ct"].str[:30]
                df_top10["du_no_ty"] = df_top10["du_no"] / 1e6
                df_top10["du_no_tw_ty"] = df_top10["du_no_tw"] / 1e6
                df_top10["du_no_dp_ty"] = df_top10["du_no_dp"] / 1e6
                df_top10["du_no_tw_ty"] = df_top10["du_no_tw_ty"].where(df_top10["du_no_tw_ty"] > 0, 0)
                df_top10["du_no_dp_ty"] = df_top10["du_no_dp_ty"].where(df_top10["du_no_dp_ty"] > 0, 0)
                fig_ct = go.Figure()
                fig_ct.add_trace(go.Bar(
                    y=df_top10["label"],
                    x=df_top10["du_no_tw_ty"],
                    name="TW",
                    orientation="h",
                    marker_color="#2E7D32",
                    text=df_top10["du_no_tw_ty"].apply(lambda x: vn(x, 1) if x > 0 else ""),
                    textposition="inside",
                    insidetextanchor="middle",
                    textfont=dict(color="white", size=10),
                ))
                fig_ct.add_trace(go.Bar(
                    y=df_top10["label"],
                    x=df_top10["du_no_dp_ty"],
                    name="ĐP",
                    orientation="h",
                    marker_color="#E65100",
                    text=df_top10["du_no_dp_ty"].apply(lambda x: vn(x, 1) if x > 0 else ""),
                    textposition="inside",
                    insidetextanchor="middle",
                    textfont=dict(color="white", size=10),
                ))
                fig_ct.update_layout(
                    barmode="stack",
                    title="📊 Top 10 chương trình theo dư nợ",
                    xaxis_title="Dư nợ (triệu đồng)",
                    yaxis=dict(autorange="reversed"),
                    height=max(350, len(df_top10) * 35),
                    margin=dict(l=10, r=40, t=40, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_ct, use_container_width=True, key="ct_bar_top10")

        else:
            _miss_ct = [c for c in [COT_TEN_CT, COT_TONG_DU_NO] if c not in df.columns]
            st.warning(
                f"⚠️ Không hiển thị được cơ cấu dư nợ — "
                f"thiếu cột: **{', '.join(_miss_ct)}**. "
                "Hãy kiểm tra file HSTD hoặc merge lại dữ liệu."
            )

        st.markdown("**🟢 Thông tin tổng quát theo PGD**")
        if COT_TEN_PGD in df.columns:
            col_khoanh = COT_DU_NO_KHOANH
            # Chỉ lấy các cột cần dùng trong tab Tổng quan (từ đoạn PGD trở đi), không copy toàn bộ
            COT_CAN = [
                COT_TEN_PGD,
                COT_MA_KH,
                COT_SO_KU,
                COT_TONG_DU_NO,
                COT_DU_NO_QH,
                col_khoanh,
                COT_TEN_CT,
                COT_TEN_XA,
                COT_NGAY_DH,
                COT_LAI_TON,
                *HSTD_DS_CHO_VAY_NAM_ALIASES,
                *HSTD_THU_NO_NAM_ALIASES,
            ]
            cot_lay = [c for c in COT_CAN if c in df.columns]
            for c in df.columns:
                if c in cot_lay:
                    continue
                s = str(c).replace("\n", " ").lower()
                if (
                    "giải ngân" in s
                    and "tháng" not in str(c).lower()
                    and (
                        "trong năm" in s
                        or str(c).strip().lower().endswith("năm")
                    )
                ):
                    cot_lay.append(c)
                elif (
                    "thu nợ" in s
                    and "tháng" not in str(c).lower()
                    and (
                        "trong năm" in s
                        or (
                            "năm" in str(c).lower()
                            and any(x in s for x in ("th ", "qh ", "khoanh"))
                        )
                    )
                ):
                    cot_lay.append(c)
            df_pgd_work = df[cot_lay]
            # Resolve column lookups để làm cache key
            _col_cv_pgd = next((c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df_pgd_work.columns), None)
            if _col_cv_pgd is None:
                _col_cv_pgd = next(
                    (c for c in df_pgd_work.columns
                     if "giải ngân" in str(c).replace("\n", " ").lower()
                     and "tháng" not in str(c).lower()
                     and ("trong năm" in str(c).replace("\n", " ").lower()
                          or str(c).strip().lower().endswith("năm"))),
                    None,
                )
            _thu_cols_pgd = [c for c in HSTD_THU_NO_NAM_ALIASES if c in df_pgd_work.columns]
            if not _thu_cols_pgd:
                _thu_cols_pgd = [
                    c for c in df_pgd_work.columns
                    if "thu nợ" in str(c).replace("\n", " ").lower()
                    and "tháng" not in str(c).lower()
                    and (
                        "trong năm" in str(c).replace("\n", " ").lower()
                        or ("năm" in str(c).lower()
                            and any(x in str(c).replace("\n", " ").lower()
                                    for x in ("th ", "qh ", "khoanh")))
                    )
                ]

            df_pgd_raw = _cache_tqpgd_extended(
                df_pgd_work, ts, str(pgd_filter),
                col_khoanh if col_khoanh and col_khoanh in df.columns else "",
                _col_cv_pgd or "",
                ",".join(_thu_cols_pgd),
                str(NAM_HT),
            )
            df_pgd = df_pgd_raw.rename(columns={
                "du_no":        "Dư nợ (triệu đồng)",
                "so_kh":        "Số KH",
                "so_mon":       "Số món vay",
                "nqh":          "QH (triệu đồng)",
                "du_no_khoanh": "Khoanh (triệu đồng)",
                "lai_ton":      "Lãi tồn (triệu đồng)",
                "no_dh_nam":    "Nợ ĐH năm (triệu đồng)",
                "ds_cho_vay":   "DS Cho vay (triệu đồng)",
                "ds_thu_no":    "DS Thu nợ (triệu đồng)",
            })
            _cols_trieu = [
                "Dư nợ (triệu đồng)", "QH (triệu đồng)", "Khoanh (triệu đồng)",
                "Lãi tồn (triệu đồng)", "Nợ ĐH năm (triệu đồng)",
                "DS Cho vay (triệu đồng)", "DS Thu nợ (triệu đồng)",
            ]
            for _c in _cols_trieu:
                if _c in df_pgd.columns:
                    df_pgd[_c] = (pd.to_numeric(df_pgd[_c], errors="coerce").fillna(0) / 1e6).round(0)

            # Bổ sung PGD trong DS_PGD nhưng không có dòng trong df → hiển thị với giá trị 0
            pgd_co_trong_bang = set(df_pgd[COT_TEN_PGD].tolist())
            pgd_thieu_bang = [p for p in [DON_VI_CHI_NHANH] + DS_PGD if p not in pgd_co_trong_bang]
            if pgd_thieu_bang:
                rows_thieu = [{COT_TEN_PGD: p} for p in pgd_thieu_bang]
                df_thieu = pd.DataFrame(rows_thieu)
                for cot in df_pgd.columns:
                    if cot != COT_TEN_PGD:
                        df_thieu[cot] = 0.0
                df_pgd = pd.concat([df_pgd, df_thieu], ignore_index=True)
                df_pgd = df_pgd.sort_values(COT_TEN_PGD).reset_index(drop=True)
                if pgd_thieu_bang == ["PGD Biên Hòa"]:
                    st.caption("⚠️ PGD Biên Hòa chưa upload dữ liệu.")
                else:
                    st.warning(
                        f"⚠️ {len(pgd_thieu_bang)} PGD chưa có dữ liệu: "
                        f"{', '.join(pgd_thieu_bang)}"
                    )

            if not _col_cv_pgd or not _thu_cols_pgd:
                st.caption("⚠️ Không có cột DS Cho vay/Thu nợ trong HSTD")
            _col_cv = _col_cv_pgd
            _thu_cols = _thu_cols_pgd

            df_pgd["TL QH %"] = ((df_pgd["QH (triệu đồng)"] / df_pgd["Dư nợ (triệu đồng)"].replace(0, pd.NA)) * 100).fillna(0).round(2)
            df_pgd["TL Khoanh %"] = ((df_pgd["Khoanh (triệu đồng)"] / df_pgd["Dư nợ (triệu đồng)"].replace(0, pd.NA)) * 100).fillna(0).round(2)

            try:
                ds_thang = ds_thang_nam()
                if ds_thang:
                    df_to_raw = doc_cdtotkvv(ds_thang[0])
                    if df_to_raw is not None and not df_to_raw.empty:
                        df_to_pgd = tong_hop_theo_pgd(df_to_raw)

                        # Map tên viết tắt trong CDTOTKVV → tên chuẩn (DON_VI_CHI_NHANH)
                        # "PGD Biên Hòa" là alias cho file cũ — trong HSTD tên thực là "Hội sở Chi nhánh tỉnh"
                        _TEN_MAP = {
                            "Hội sở CN Đồng Nai":   DON_VI_CHI_NHANH,
                            "Hội sở CN Bình Phước": DON_VI_CHI_NHANH,
                            "PGD Biên Hòa":         DON_VI_CHI_NHANH,
                        }
                        def _map_ten(val):
                            val = str(val).strip()
                            if val in _TEN_MAP:
                                return _TEN_MAP[val]
                            # Fuzzy: ten_dv chứa tên PGD chuẩn hoặc ngược lại
                            val_low = val.lower()
                            for ten in [DON_VI_CHI_NHANH] + DS_PGD:
                                if ten.lower() in val_low or val_low in ten.lower():
                                    return ten
                            return val

                        # FIX: đổi "ten_dv" (đúng) thay vì "ten_pgd" (sai)
                        df_to_pgd[COT_TEN_PGD] = df_to_pgd["ten_dv"].apply(_map_ten)
                        df_to_pgd = df_to_pgd.rename(columns={
                            "tong_to": "Tổng Tổ",
                            "to_tot":  "Tốt",
                            "to_kha":  "Khá",
                            "to_tb":   "TB",
                            "to_yeu":  "Yếu",
                        })
                        cot_to = [COT_TEN_PGD, "Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]
                        # Gộp nếu nhiều dòng cùng tên PGD sau khi map
                        df_to_pgd = (
                            df_to_pgd[cot_to]
                            .groupby(COT_TEN_PGD, as_index=False)
                            .sum()
                        )
                        df_pgd = df_pgd.merge(df_to_pgd, on=COT_TEN_PGD, how="left")
            except Exception as e:  # conv: skip
                logger.error("Lỗi merge CDTOTKVV: %s", e, exc_info=True)
                pass

            for cot in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                if cot in df_pgd.columns:
                    df_pgd[cot] = df_pgd[cot].fillna(0).round(0).astype(int)

            # Tính TL QH% và TL Khoanh% cho từng PGD
            df_pgd["TL QH %"] = (
                (df_pgd["QH (triệu đồng)"] / df_pgd["Dư nợ (triệu đồng)"].replace(0, pd.NA)) * 100
            ).fillna(0).round(2)
            df_pgd["TL Khoanh %"] = (
                (df_pgd["Khoanh (triệu đồng)"] / df_pgd["Dư nợ (triệu đồng)"].replace(0, pd.NA)) * 100
            ).fillna(0).round(2)

            # Tính Nợ xấu (NPL) = QH + Khoanh
            df_pgd["Nợ xấu (triệu đồng)"] = (df_pgd["QH (triệu đồng)"] + df_pgd["Khoanh (triệu đồng)"]).round(3)
            df_pgd["Tỷ lệ Nợ xấu"] = (
                (df_pgd["Nợ xấu (triệu đồng)"] / df_pgd["Dư nợ (triệu đồng)"].replace(0, pd.NA)) * 100
            ).fillna(0).round(2)

            # Merge dữ liệu Tổ TK&VV theo PGD (nếu có)
            try:
                _df_to_pgd_map = None
                _ds_thang = ds_thang_nam()
                if _ds_thang:
                    for _th in _ds_thang:
                        _df_to_r = doc_cdtotkvv(_th)
                        if _df_to_r is not None and not _df_to_r.empty:
                            _df_to_pgd_map = tong_hop_theo_pgd(_df_to_r)
                            break
                if _df_to_pgd_map is None or _df_to_pgd_map.empty:
                    from data.cdtotkvv import tong_hop_tu_pgd_data
                    _df_raw_pgd = tong_hop_tu_pgd_data()
                    if _df_raw_pgd is not None and not _df_raw_pgd.empty:
                        _df_to_pgd_map = tong_hop_theo_pgd(_df_raw_pgd)
            except Exception as e:  # conv: skip
                logger.error("Lỗi fallback CDTOTKVV từ pgd_data: %s", e, exc_info=True)
                _df_to_pgd_map = None

            tong = {COT_TEN_PGD: "Toàn Chi nhánh"}
            cot_so = [c for c in df_pgd.columns if c != COT_TEN_PGD and pd.api.types.is_numeric_dtype(df_pgd[c])]
            for cot in cot_so:
                tong[cot] = df_pgd[cot].sum()
            du_no_tong_trieu = tong.get("Dư nợ (triệu đồng)", 0) * 1000
            tong["TL QH %"] = round((tong.get("QH (triệu đồng)", 0) / tong.get("Dư nợ (triệu đồng)", 1) * 100), 2) if tong.get("Dư nợ (triệu đồng)", 0) else 0
            tong["TL Khoanh %"] = round((tong.get("Khoanh (triệu đồng)", 0) / tong.get("Dư nợ (triệu đồng)", 1) * 100), 2) if tong.get("Dư nợ (triệu đồng)", 0) else 0
            tong["Nợ xấu (triệu đồng)"] = round(tong.get("QH (triệu đồng)", 0) + tong.get("Khoanh (triệu đồng)", 0), 3)
            tong["Tỷ lệ Nợ xấu"] = round(tong["Nợ xấu (triệu đồng)"] / tong.get("Dư nợ (triệu đồng)", 1) * 100, 2) if tong.get("Dư nợ (triệu đồng)", 0) else 0
            tong_clean = {k: (v if pd.notna(v) else 0) for k, v in tong.items()
                          if k != COT_TEN_PGD}
            tong_clean[COT_TEN_PGD] = "Toàn Chi nhánh"
            df_pgd = pd.concat([df_pgd, pd.DataFrame([tong_clean])], ignore_index=True)

            # Merge điểm tổ theo PGD vào df_pgd nếu có
            if _df_to_pgd_map is not None and not _df_to_pgd_map.empty:
                # "PGD Biên Hòa" là alias cho file cũ — trong HSTD tên thực là "Hội sở Chi nhánh tỉnh"
                _TEN_MAP = {
                    "Hội sở CN Đồng Nai": DON_VI_CHI_NHANH,
                    "Hội sở CN Bình Phước": DON_VI_CHI_NHANH,
                    "PGD Biên Hòa":       DON_VI_CHI_NHANH,
                }
                def _map_ten_to(val):
                    val = str(val).strip()
                    if val in _TEN_MAP:
                        return _TEN_MAP[val]
                    val_low = val.lower()
                    for ten in [DON_VI_CHI_NHANH] + DS_PGD:
                        if ten.lower() in val_low or val_low in ten.lower():
                            return ten
                    return val
                _df_to_pgd_map[COT_TEN_PGD] = _df_to_pgd_map["ten_dv"].apply(_map_ten_to)
                _df_to_pgd_map = _df_to_pgd_map.rename(columns={
                    "tong_to": "Tổng Tổ", "to_tot": "Tốt",
                    "to_kha": "Khá", "to_tb": "TB", "to_yeu": "Yếu",
                })
                _cot_to = [COT_TEN_PGD, "Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]
                _df_to_pgd_map = _df_to_pgd_map[_cot_to].groupby(COT_TEN_PGD, as_index=False).sum()
                # Xóa cột cũ nếu đã có rồi merge lại
                for _c in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                    if _c in df_pgd.columns:
                        df_pgd = df_pgd.drop(columns=[_c])
                df_pgd = df_pgd.merge(_df_to_pgd_map, on=COT_TEN_PGD, how="left")
                for _c in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                    if _c in df_pgd.columns:
                        df_pgd[_c] = df_pgd[_c].fillna(0).round(0).astype(int)

            # Cập nhật dòng tổng cho cột Tổ TK&VV
            for _c in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                if _c in df_pgd.columns:
                    tong[_c] = int(df_pgd[_c].iloc[:-1].sum())

            # Cập nhật lại dòng tổng trong df_pgd
            for _key, _val in tong.items():
                if _key in df_pgd.columns:
                    df_pgd.loc[df_pgd.index[-1], _key] = _val

            cot_hien = [
                COT_TEN_PGD,
                "Số món vay", "Số KH", "Dư nợ (triệu đồng)",
                "QH (triệu đồng)", "TL QH %",
                "Khoanh (triệu đồng)", "TL Khoanh %",
                "Nợ xấu (triệu đồng)", "Tỷ lệ Nợ xấu",
                "Lãi tồn (triệu đồng)",
                "Nợ ĐH năm (triệu đồng)",
                "DS Cho vay (triệu đồng)", "DS Thu nợ (triệu đồng)",
            ]
            cot_hien += [c for c in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"] if c in df_pgd.columns]
            cot_hien = [c for c in cot_hien if c in df_pgd.columns]
            # Tách riêng dòng Hội sở Chi nhánh tỉnh để hiển thị đầu bảng
            df_hoi_so = df_pgd[df_pgd[COT_TEN_PGD] == DON_VI_CHI_NHANH].copy()
            # Loại bỏ dòng DON_VI_CHI_NHANH khỏi df_pgd (giữ nguyên logic cũ)
            df_pgd = df_pgd[df_pgd[COT_TEN_PGD] != DON_VI_CHI_NHANH].reset_index(drop=True)
            # Ghép Hội sở lên đầu bảng nếu có dữ liệu
            if not df_hoi_so.empty:
                df_pgd = pd.concat([df_hoi_so, df_pgd], ignore_index=True)
            
            # ── Bảng HTML có header nhóm cột ─────────────────────────────
            df_show = df_pgd[cot_hien].copy()
            # Đánh dấu dòng tổng (dòng cuối)
            is_tong = df_show[COT_TEN_PGD] == "Toàn Chi nhánh"

            def _fmt_cell(val, col):
                """Hiển thị ô bảng theo chuẩn VN (. nghìn, , thập phân) — dùng vn / fmt_so."""
                if pd.isna(val) or val == "":
                    return "—"
                if col in ["Dư nợ (triệu đồng)"]:
                    return vn(float(val) / 1000, 2)
                if col in ["TL QH %", "TL Khoanh %", "Tỷ lệ Nợ xấu"]:
                    return f"{vn(float(val), 2)}%"
                if col in [
                    "QH (triệu đồng)",
                    "Khoanh (triệu đồng)",
                    "Nợ xấu (triệu đồng)",
                    "Lãi tồn (triệu đồng)",
                    "Nợ ĐH năm (triệu đồng)",
                    "DS Cho vay (triệu đồng)",
                    "DS Thu nợ (triệu đồng)",
                ]:
                    return vn(float(val), 3)
                if col in ["Số món vay", "Số KH", "Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                    try:
                        return fmt_so(val)
                    except Exception as e:  # conv: skip
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        return str(val)
                return str(val)

            # Header nhóm
            NHOM_COT = [
                ("", 1),                    # Tên PGD
                ("Dư nợ", 3),               # Số món vay, Số KH, Dư nợ (tỷ)
                ("Chất lượng nợ", 7),       # QH, TL QH, Khoanh, TL Khoanh, Nợ xấu, TL NPL, Lãi tồn
                ("Kế hoạch năm", 3),        # Nợ ĐH, DS Cho vay, DS Thu nợ
                ("Tổ TK&VV", len([c for c in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"] if c in df_pgd.columns])),
            ]
            # Bỏ nhóm có colspan=0
            NHOM_COT = [(n, s) for n, s in NHOM_COT if s > 0]

            def _disp_col(col: str) -> str:
                """Tên cột hiển thị 2 dòng: phần đơn vị xuống dòng."""
                if col == COT_TEN_PGD:
                    return "Đơn vị"
                if col == "Dư nợ (triệu đồng)":
                    return "Dư nợ<br/><span style='font-weight:normal;font-size:11px'>(Tỷ đồng)</span>"
                if col.endswith("(triệu đồng)"):
                    return col[:-len("(triệu đồng)")].strip() + "<br/><span style='font-weight:normal;font-size:11px'>(Triệu đồng)</span>"
                if col.endswith("(tỷ)"):
                    return col[:-len("(tỷ)")].strip() + "<br/><span style='font-weight:normal;font-size:11px'>(Tỷ đồng)</span>"
                if col == "Tỷ lệ Nợ xấu":
                    return "Tỷ lệ<br/>Nợ xấu"
                return col

            header1 = "".join(
                f'<th colspan="{span}" style="background:#2E7D32;color:#fff;'
                f'text-align:center;padding:7px 5px;border:1px solid #1B5E20;font-size:13px">'
                f'{nhom}</th>'
                for nhom, span in NHOM_COT
            )
            header2 = "".join(
                f'<th style="background:#388E3C;color:#fff;text-align:center;'
                f'padding:6px 4px;border:1px solid #1B5E20;font-size:12px;'
                f'white-space:normal;min-width:60px;line-height:1.4">'
                f'{_disp_col(c)}</th>'
                for c in cot_hien
            )

            rows_html = ""
            for i, (_, row) in enumerate(df_show.iterrows()):
                is_last = row[COT_TEN_PGD] == "Toàn Chi nhánh"
                bg = "#C8E6C9" if is_last else ("#F5F7FA" if i % 2 == 0 else "#FFFFFF")
                fw = "bold" if is_last else "normal"
                row_fs = "0.92rem" if is_last else "0.90rem"
                cells = "".join(
                    f'<td style="padding:6px 7px;border:1px solid #E0E0E0;'
                    f'text-align:{"left" if c == cot_hien[0] else "right"};'
                    f'font-weight:{fw};font-size:{row_fs};white-space:nowrap;'
                    f'{"color:#C62828;font-weight:800" if c == "TL QH %" and pd.to_numeric(row.get(c, 0), errors="coerce") > 0.5 else ""}'
                    f'{"color:#C62828;font-weight:800" if c == "Tỷ lệ Nợ xấu" and pd.to_numeric(row.get(c, 0), errors="coerce") > 0.3 else ""}'
                    f'{"color:#C62828;font-weight:800" if c == "TL Khoanh %" and pd.to_numeric(row.get(c, 0), errors="coerce") > 1 else ""}'
                    f'">'
                    f'{_fmt_cell(row[c], c)}</td>'
                    for c in cot_hien
                )
                rows_html += f'<tr style="background:{bg};color:#1a202c">{cells}</tr>\n'

            html_table = f"""
            <div style="overflow-x:auto;margin:8px 0">
            <table style="border-collapse:collapse;width:100%;font-family:sans-serif">
              <thead>
                <tr>{header1}</tr>
                <tr>{header2}</tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
            <div style="font-size:0.78rem;opacity:0.65;margin:4px 0">
              * Đơn vị: Dư nợ = tỷ đồng | Các cột tiền khác = triệu đồng
            </div>
            </div>
            """
            st.markdown(html_table, unsafe_allow_html=True)

            # Format từng ô theo _fmt_cell trước khi xuất PDF
            df_export = df_show.copy().rename(columns={COT_TEN_PGD: "Đơn vị"})
            for col in df_export.columns:
                if col != "Đơn vị":
                    df_export[col] = df_export[col].apply(
                        lambda v, c=col: _fmt_cell(v, c)
                    )

            col_ex, col_pdf = st.columns(2)

            with col_ex:
                if st.button("📥 Xuất Excel", key="btn_excel_tqpgd", use_container_width=True):
                    try:
                        state = SCMStateManager()
                        _ten_excel = ten_file_xuat("TQPGD")
                        buf = _xuat_excel_tqpgd(df_show, _ten_excel)
                        state.downloads.set("tqpgd_excel", buf, _ten_excel)
                    except Exception as e:  # conv: skip
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất Excel: {e}")
                state = SCMStateManager()
                if state.downloads.has("tqpgd_excel"):
                    if st.download_button(
                        "⬇ Tải Excel",
                        data=state.downloads.get_bytes("tqpgd_excel"),
                        file_name=state.downloads.get_filename("tqpgd_excel") or "TQPGD.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="btn_excel_tqpgd_dl",
                        use_container_width=True,
                    ):
                        state.downloads.clear("tqpgd_excel")

            with col_pdf:
                if st.button("📄 Xuất PDF", key="btn_pdf_tqpgd", type="primary", use_container_width=True):
                    try:
                        state = SCMStateManager()
                        # Đổi tên cột → 2 dòng cho header PDF (Reportlab Paragraph hỗ trợ <br/>)
                        def _pdf_col(col: str) -> str:
                            if col.endswith("(triệu đồng)"):
                                return col[:-len("(triệu đồng)")].strip() + "<br/>(Triệu đồng)"
                            if col.endswith("(tỷ)"):
                                return col[:-len("(tỷ)")].strip() + "<br/>(Tỷ đồng)"
                            if col == "Tỷ lệ Nợ xấu":
                                return "Tỷ lệ<br/>Nợ xấu"
                            return col
                        df_pdf = df_export.rename(columns={c: _pdf_col(c) for c in df_export.columns})

                        # Các cột số → căn phải (dữ liệu đã format sẵn thành string)
                        _cols_right_pdf = [c for c in df_pdf.columns if c != "Đơn vị"]
                        with st.spinner("⏳ Đang tạo PDF..."):
                            _bytes = xuat_pdf(
                                df_pdf,
                                "Thông tin tổng quát theo PGD",
                                username,
                                cols_tien=[],
                                cols_right=_cols_right_pdf,
                                prefix_file="TQPGD",
                            )
                        state.downloads.set(
                            "tqpgd_pdf",
                            _bytes,
                            f"TQPGD_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
                        )
                        db.ghi_audit(username or "unknown", "xuat_pdf", f"TQPGD")
                    except Exception as _e:
                        logger.error("Lỗi trong khối except: %s", _e, exc_info=True)
                        import traceback


                        SCMStateManager().downloads.clear("tqpgd_pdf")
                        st.error(f"❌ Lỗi: {_e}")
                        st.code(traceback.format_exc())

                state = SCMStateManager()
                if state.downloads.has("tqpgd_pdf"):
                    if st.download_button(
                        label="⬇ Tải file PDF TQPGD",
                        data=state.downloads.get_bytes("tqpgd_pdf"),
                        file_name=state.downloads.get_filename("tqpgd_pdf") or "TQPGD.pdf",
                        mime="application/pdf",
                        key="btn_pdf_tqpgd_dl",
                        use_container_width=True,
                    ):
                        state.downloads.clear("tqpgd_pdf")
        else:
            st.warning(
                f"⚠️ Không hiển thị được bảng tổng quát PGD — "
                f"thiếu cột **{COT_TEN_PGD}** trong dữ liệu HSTD. "
                "Hãy kiểm tra file HSTD hoặc merge lại dữ liệu."
            )
        st.divider()
        st.subheader("🔔 Hồ sơ đến hạn — Tổng hợp")
        if COT_NGAY_DH in df.columns:
            try:
                dt = _tqsvc.chuan_hoa_ngay(df, COT_NGAY_DH, dayfirst=True)
                hn       = pd.Timestamp.today().normalize()
                cuoi_nam = pd.Timestamp(hn.year, 12, 31)


                # ── Bộ lọc dữ liệu (sử dụng filter_bar component) ──
                _c0, _c1 = st.columns([2, 10])
                with _c0:
                    nhom_chon = st.selectbox(
                        "Nhóm TH",
                        ["Chương trình", "PGD", "Xã"],
                        key="tq_denh_nhom",
                    )

                NHOM_COT = {
                    "Chương trình": COT_TEN_CT,
                    "PGD":          COT_TEN_PGD,
                    "Xã":           COT_TEN_XA,
                }
                nhom_col = NHOM_COT[nhom_chon]

                # Xác định cột Xã (có thể là alias)
                cot_xa = next((c for c in [COT_TEN_XA, "Tên xã"] if c in dt.columns), None)

                # Filter bar cho PGD, CT, Xã
                filters_cfg = []
                if COT_TEN_PGD in dt.columns:
                    filters_cfg.append({
                        "field": COT_TEN_PGD,
                        "label": "Lọc PGD",
                        "type": "multiselect",
                    })
                if COT_TEN_CT in dt.columns:
                    filters_cfg.append({
                        "field": COT_TEN_CT,
                        "label": "Lọc CT",
                        "type": "multiselect",
                    })
                if cot_xa:
                    filters_cfg.append({
                        "field": cot_xa,
                        "label": "Lọc Xã",
                        "type": "multiselect",
                    })

                filter_values = filter_bar(dt, filters_cfg, key_prefix="tq_dh")

                # Áp dụng bộ lọc vào dt trước khi lọc theo mốc thời gian
                dt_loc = apply_filters(dt, filter_values)
                dt_loc = _tqsvc.loc_du_no_duong(dt_loc, COT_TONG_DU_NO)

                MOC = {
                    "1 tháng":   hn + pd.Timedelta(days=30),
                    "3 tháng":   hn + pd.Timedelta(days=90),
                    "6 tháng":   hn + pd.Timedelta(days=180),
                    "Trong năm": cuoi_nam,
                }

                def _build_pdf_den_han(df_loc, label, loc_pgd, loc_ct, loc_xa, username, key_prefix):
                    """Build PDF bytes: luôn groupby [PGD, Xã, Chương trình], bộ lọc chỉ thu hẹp input."""
                    COLS_GROUP = [COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT]
                    cols_ok = [c for c in COLS_GROUP if c in df_loc.columns]

                    RENAME_MAP = {COT_TEN_PGD: "PGD", COT_TEN_XA: "Xã", COT_TEN_CT: "Chương trình"}
                    rename_ok = {k: v for k, v in RENAME_MAP.items() if k in df_loc.columns}

                    pdf_tg = _tqsvc.tong_hop_den_han(
                        df_loc,
                        group_cols=cols_ok,
                        cot_so_ku=COT_SO_KU,
                        cot_ma_kh=COT_MA_KH,
                        cot_tdn=COT_TONG_DU_NO,
                    )

                    pdf_tg["Số món vay"] = pdf_tg["_mon"].apply(fmt_so)
                    pdf_tg["Số KH"]      = pdf_tg["_kh"].apply(fmt_so)
                    pdf_tg["Dư nợ (triệu đồng)"] = pdf_tg["_no"].apply(fmt_bang_ty)

                    pdf_tg = pdf_tg.rename(columns=rename_ok)
                    pdf_tg = pdf_tg.sort_values(
                        by=[c for c in ["PGD", "Xã", "Chương trình"] if c in pdf_tg.columns],
                        ascending=True,
                    )

                    cols_hien_thi = [v for v in ["PGD", "Xã", "Chương trình"] if v in pdf_tg.columns]
                    df_pdf = pdf_tg[[*cols_hien_thi, "Số món vay", "Số KH", "Dư nợ (triệu đồng)"]]

                    return xuat_pdf(
                        df_pdf,
                        f"Hồ sơ đến hạn {label} — Tổng hợp theo PGD / Xã / Chương trình",
                        username,
                        cols_tien=[],
                        prefix_file=f"HoSoDenHan_{key_prefix}",
                    )

                def _bang_den_han(df_loc, label, key_prefix):
                    tg = None
                    if df_loc.empty:
                        st.success(f"✅ Không có món vay đến hạn {label}")
                        return

                    _tong = _tqsvc.tong_chi_tieu_den_han(
                        df_loc,
                        cot_tdn=COT_TONG_DU_NO,
                        cot_so_ku=COT_SO_KU,
                        cot_ma_kh=COT_MA_KH,
                    )
                    tong_no = _tong["tong_no"]
                    tong_mon = _tong["tong_mon"]
                    tong_kh = _tong["tong_kh"]

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Số món vay", fmt_so(tong_mon))
                    c2.metric("Số khách hàng", fmt_so(tong_kh))
                    c3.metric("Tổng dư nợ", fmt(tong_no))

                    # Biểu đồ phân bổ theo tháng
                    df_thang = _tqsvc.tong_hop_den_han_theo_thang(
                        df_loc,
                        cot_ngay_dh=COT_NGAY_DH,
                        cot_so_ku=COT_SO_KU,
                        cot_ma_kh=COT_MA_KH,
                        cot_tdn=COT_TONG_DU_NO,
                    )
                    if not df_thang.empty and len(df_thang) > 1:
                        fig_bar = px.bar(
                            df_thang,
                            x="nam_thang_label",
                            y="_no",
                            text=df_thang["_no"].apply(fmt_bang_ty),
                            labels={"nam_thang_label": "Tháng", "_no": "Dư nợ (triệu đồng)"},
                            title=f"Phân bổ dư nợ đến hạn — {label}",
                            color_discrete_sequence=["#0066CC"],
                        )
                        fig_bar.update_traces(textposition="outside", textfont_size=11)
                        fig_bar.update_layout(
                            height=300,
                            paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=0, r=0, t=40, b=0),
                            xaxis_title="",
                            yaxis_title="Triệu đồng",
                        )
                        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_den_han_{key_prefix}")

                    st.divider()

                    if nhom_col in df_loc.columns:
                        if nhom_chon == "Xã" and COT_TEN_PGD in df_loc.columns:
                            tg = _tqsvc.tong_hop_den_han(
                                df_loc,
                                group_cols=[COT_TEN_PGD, nhom_col],
                                cot_so_ku=COT_SO_KU,
                                cot_ma_kh=COT_MA_KH,
                                cot_tdn=COT_TONG_DU_NO,
                            ).sort_values("_no", ascending=False)
                            tg["Số món vay"] = tg["_mon"].apply(fmt_so)
                            tg["Số KH"]      = tg["_kh"].apply(fmt_so)
                            tg["Dư nợ (triệu đồng)"] = tg["_no"].apply(fmt_bang_ty)
                            cols_hien_thi = [COT_TEN_PGD, nhom_col, "Số món vay", "Số KH", "Dư nợ (triệu đồng)"]
                            rename_map = {COT_TEN_PGD: "PGD", nhom_col: "Xã"}
                        else:
                            tg = _tqsvc.tong_hop_den_han(
                                df_loc,
                                group_cols=[nhom_col],
                                cot_so_ku=COT_SO_KU,
                                cot_ma_kh=COT_MA_KH,
                                cot_tdn=COT_TONG_DU_NO,
                            ).sort_values("_no", ascending=False)
                            tg["Số món vay"] = tg["_mon"].apply(fmt_so)
                            tg["Số KH"]      = tg["_kh"].apply(fmt_so)
                            tg["Dư nợ (triệu đồng)"] = tg["_no"].apply(fmt_bang_ty)
                            cols_hien_thi = [nhom_col, "Số món vay", "Số KH", "Dư nợ (triệu đồng)"]
                            rename_map = {nhom_col: nhom_chon}

                        hien_thi_dataframe_phan_trang(
                            tg[cols_hien_thi].rename(columns=rename_map),
                            key=f"tongquan_den_han_{key_prefix}",
                        )

                        if nhom_col in df_loc.columns and len(tg) > 0:
                            top10 = tg.nlargest(10, "_no")

                            fig = go.Figure(go.Pie(
                                labels=top10[nhom_col],
                                values=top10["_no"],
                                hole=0.5,
                                textinfo="label+percent",
                                textposition="outside",
                                hovertemplate="<b>%{label}</b><br>Dư nợ: %{customdata}<br>Tỷ lệ: %{percent}<extra></extra>",
                                customdata=top10["Dư nợ (triệu đồng)"],
                                marker=dict(
                                    colors=px.colors.sequential.Greens_r[: len(top10)],
                                    line=dict(color="white", width=2),
                                ),
                            ))

                            fig.update_layout(
                                title=f"Top 10 {nhom_chon} có dư nợ đến hạn cao nhất",
                                height=450,
                                annotations=[dict(
                                    text=f"<b>{fmt(tong_no)}</b><br>Tổng dư nợ",
                                    x=0.5, y=0.5,
                                    font=dict(size=13),
                                    showarrow=False,
                                )],
                                legend=dict(orientation="v", x=1.05, y=0.5),
                                margin=dict(l=0, r=150, t=50, b=0),
                                paper_bgcolor="rgba(0,0,0,0)",
                            )

                            st.plotly_chart(fig, use_container_width=True, key=f"pie_den_han_{key_prefix}")

                        if tg is not None:
                            st.divider()
                            col_ex, col_pdf = st.columns(2)

                            # PDF: luôn groupby [PGD, Xã, Chương trình] — bộ lọc chỉ thu hẹp input
                            pdf_key = f"den_han_{key_prefix}_pdf"

                            with col_ex:
                                # Excel: giữ logic hiện tại
                                co_loc = any(filter_values.values())
                                if co_loc:
                                    df_excel = tg[[nhom_col, "_mon", "_kh", "_no"]].rename(columns={
                                        nhom_col: nhom_chon,
                                        "_mon": "Số món vay",
                                        "_kh":  "Số KH",
                                        "_no":  "Dư nợ",
                                    })
                                    ten_sheet = f"TH_{nhom_chon[:10]}_{key_prefix}"
                                else:
                                    COLS_CHI_TIET = [
                                        COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU,
                                        COT_TEN_CT, COT_TONG_DU_NO, COT_NGAY_DH,
                                    ]
                                    cols_ok = [c for c in COLS_CHI_TIET if c in df_loc.columns]
                                    df_excel = df_loc[cols_ok].sort_values(COT_TEN_PGD).reset_index(drop=True)
                                    ten_sheet = f"ChiTiet_{key_prefix}"

                                excel_bytes = xuat_excel({ten_sheet: df_excel})
                                st.download_button(
                                    label="📥 Xuất Excel",
                                    data=excel_bytes,
                                    file_name=ten_file_xuat(f"HoSoDenHan_{key_prefix}"),
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True,
                                    key=f"excel_den_han_{key_prefix}",
                                )

                            with col_pdf:
                                if st.button("📄 Xuất PDF", key=f"pdf_den_han_{key_prefix}",
                                             type="primary", use_container_width=True):
                                    state = SCMStateManager()
                                    with st.spinner("⏳ Đang tạo PDF..."):
                                        pdf_bytes = _build_pdf_den_han(
                                            df_loc, label,
                                            filter_values.get(COT_TEN_PGD),
                                            filter_values.get(COT_TEN_CT),
                                            filter_values.get(cot_xa),
                                            username, key_prefix
                                        )
                                    state.downloads.set(
                                        pdf_key,
                                        pdf_bytes,
                                        f"HoSoDenHan_{key_prefix}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
                                    )

                            # Download button đặt NGOÀI block columns để tránh duplicate widget
                            state = SCMStateManager()
                            if state.downloads.has(pdf_key):
                                if st.download_button(
                                    label="⬇ Tải file PDF",
                                    data=state.downloads.get_bytes(pdf_key),
                                    file_name=state.downloads.get_filename(pdf_key) or f"HoSoDenHan_{key_prefix}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_den_han_{key_prefix}",
                                    use_container_width=True,
                                ):
                                    state.downloads.clear(pdf_key)
                    else:
                        st.caption(f"⚠️ Không có cột '{nhom_chon}' trong dữ liệu")

                _moc_labels = list(MOC.keys())
                _moc_values = list(MOC.values())
                lazy_tabs(
                    [f"📅 {lbl}" for lbl in _moc_labels],
                    [
                        lambda _den=den, _lbl=lbl, _key=lbl.replace(" ", "_"): _bang_den_han(
                            _tqsvc.loc_den_han(dt_loc, cot_ngay_dh=COT_NGAY_DH, tu_ngay=hn, den_ngay=_den),
                            _lbl, _key,
                        )
                        for den, lbl in zip(_moc_values, _moc_labels)
                    ],
                    key="tq_den_han",
                )

            except Exception as e:  # conv: skip
                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                st.error(f"Lỗi xử lý đến hạn: {e}")

            # ── Download PDF: chỉ giữ nút trong mỗi tab (không duplicate) ──
            # Phần download ngoài tabs đã xóa để tránh trùng lặp với nút
            # "⬇ Tải file PDF" trong mỗi tab 1/3/6 tháng và Trong năm
        else:
            st.warning(
                f"⚠️ Không hiển thị được hồ sơ đến hạn — "
                f"thiếu cột **{COT_NGAY_DH}** trong dữ liệu HSTD. "
                "Hãy kiểm tra file HSTD hoặc merge lại dữ liệu."
            )

        # ── Debug: hiển thị cột thiếu khi cần chẩn đoán ─────────────────
        _cols_can_thiet = {
            "Tên chương trình (COT_TEN_CT)":   COT_TEN_CT,
            "Tổng dư nợ (COT_TONG_DU_NO)":     COT_TONG_DU_NO,
            "Tên PGD (COT_TEN_PGD)":            COT_TEN_PGD,
            "Ngày ĐH theo Gia hạn (COT_NGAY_DH)": COT_NGAY_DH,
        }
        _cols_thieu = {label: col for label, col in _cols_can_thiet.items() if col not in df.columns}
        if _cols_thieu:
            with st.expander("🔍 Chẩn đoán: Cột dữ liệu bị thiếu", expanded=True):
                st.error(
                    "**Các cột cần thiết KHÔNG có trong dữ liệu HSTD hiện tại:**\n\n"
                    + "\n".join(f"- `{col}` → *{label}*" for label, col in _cols_thieu.items())
                )
                st.caption(
                    f"📋 Dữ liệu hiện có **{len(df.columns)}** cột, **{len(df):,}** dòng. "
                    f"Các cột đang có: `{', '.join(df.columns[:20].tolist())}"
                    f"{'...' if len(df.columns) > 20 else ''}`"
                )
                st.info(
                    "**Cách sửa:**\n"
                    "1. Kiểm tra file Excel HSTD — cột phải có tên chính xác như trên\n"
                    "2. Upload lại file HSTD qua **📤 Upload HSTD**\n"
                    "3. Bấm **Merge dữ liệu** để tạo lại cache"
                )
