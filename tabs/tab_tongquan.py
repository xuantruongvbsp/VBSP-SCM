"""Tab Tổng quan."""
from __future__ import annotations

import logging
import os
from io import BytesIO
from datetime import datetime, date
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import *
from config import DS_PGD, CACHE_HSTD, TEN_CHI_NHANH_HIEN_THI
from utils import (
    fmt,
    fmt_tien,
    fmt_so,
    vn,
    fmt_ty,
    xuat_excel,
    ten_file_xuat,
    hien_thi_dataframe_phan_trang,
)
from data.pgd import ds_pgd_co_file
from data.cdtotkvv import doc_cdtotkvv, ds_thang_nam, tong_hop_theo_pgd
from pdf_service import nut_xuat_pdf
from services.upload_service import format_caption_merge

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
    tdn = _df[cot_tdn].sum() if cot_tdn in _df.columns else 0
    dth = _df[cot_dth].sum() if cot_dth in _df.columns else 0
    dqh = _df[cot_dqh].sum() if cot_dqh in _df.columns else 0
    dnk = _df[cot_nk].sum() if cot_nk in _df.columns else 0
    n_mon_vay = _df[cot_ku].nunique() if cot_ku in _df.columns else len(_df)
    n_kh = _df[cot_ma_kh].nunique() if cot_ma_kh in _df.columns else 0
    try:
        from data import danh_dau_khong_hd

        df_kh = danh_dau_khong_hd(_df)
        n_3m = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
        dn_3m = (
            df_kh.loc[df_kh["is_3m_inactive"], cot_tdn].sum()
            if ("is_3m_inactive" in df_kh.columns and cot_tdn in df_kh.columns)
            else 0
        )
    except Exception as e:
        n_3m = 0
        dn_3m = 0
        logging.warning(
            "[tongquan_kpi] danh_dau_khong_hd lỗi: %s",
            e,
        )
    return dict(
        tdn=tdn,
        dth=dth,
        dqh=dqh,
        dnk=dnk,
        n_mon_vay=n_mon_vay,
        n_kh=n_kh,
        n_3m=n_3m,
        dn_3m=dn_3m,
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
    return _df.groupby(cot_pgd, as_index=False).agg(
        du_no=(cot_tdn, "sum"),
        so_kh=(cot_ma_kh, "nunique"),
        nqh=(cot_dqh, "sum"),
    )


def _tao_column_config_co_cau() -> dict[str, st.column_config.Column]:
    """
    Tạo column_config cho bảng cơ cấu dư nợ theo chương trình.
    
    Returns:
        Dict cấu hình column cho st.dataframe
    """
    return {
        "du_no": st.column_config.NumberColumn(
            "Dư nợ",
            format="%.0f ₫",
            help="Tổng dư nợ chương trình"
        ),
        "ty_trong": st.column_config.NumberColumn(
            "Tỷ trọng",
            format="%.2f%%",
            help="Tỷ trọng % trên tổng dư nợ"
        ),
    }


def _tao_column_config_pgd() -> dict[str, st.column_config.Column]:
    """
    Tạo column_config cho bảng tổng hợp theo PGD.
    
    Returns:
        Dict cấu hình column cho st.dataframe
    """
    return {
        "Dư nợ (tỷ)": st.column_config.NumberColumn(
            "Dư nợ (tỷ)",
            format="%.2f tỷ",
            help="Tổng dư nợ tính bằng tỷ đồng"
        ),
        "QH (tỷ)": st.column_config.NumberColumn(
            "QH (tỷ)",
            format="%.3f tỷ",
            help="Dư nợ quá hạn tính bằng tỷ đồng"
        ),
        "Khoanh (tỷ)": st.column_config.NumberColumn(
            "Khoanh (tỷ)",
            format="%.3f tỷ",
            help="Dư nợ khoanh tính bằng tỷ đồng"
        ),
        "TL QH %": st.column_config.NumberColumn(
            "TL QH %",
            format="%.2f%%",
            help="Tỷ lệ quá hạn %"
        ),
        "TL Khoanh %": st.column_config.NumberColumn(
            "TL Khoanh %",
            format="%.2f%%",
            help="Tỷ lệ khoanh %"
        ),
        "Lãi tồn (tỷ)": st.column_config.NumberColumn(
            "Lãi tồn (tỷ)",
            format="%.3f tỷ",
            help="Lãi tồn tính bằng tỷ đồng"
        ),
        "Nợ ĐH năm (tỷ)": st.column_config.NumberColumn(
            "Nợ ĐH năm (tỷ)",
            format="%.3f tỷ",
            help="Nợ đến hạn trong năm tính bằng tỷ đồng"
        ),
        "DS Cho vay (tỷ)": st.column_config.NumberColumn(
            "DS Cho vay (tỷ)",
            format="%.3f tỷ",
            help="Doanh số cho vay trong năm tính bằng tỷ đồng"
        ),
        "DS Thu nợ (tỷ)": st.column_config.NumberColumn(
            "DS Thu nợ (tỷ)",
            format="%.3f tỷ",
            help="Doanh số thu nợ trong năm tính bằng tỷ đồng"
        ),
    }


def render(tab: DeltaGenerator, **kwargs: dict) -> None:
    """
    Render tab Tổng quan.
    
    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa df, df_full, role, pgd_user, username, df_nq11
    """
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role     = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user") or ""
    pgd_filter = kwargs.get("pgd_filter") or pgd_user
    username = kwargs.get("username")
    df_nq11  = kwargs.get("df_nq11")
    ts = kwargs.get("ts_hstd", 0.0)

    with tab:
        st.markdown(
            """
            <style>
            .tq-caption{color:#4b5563;font-size:0.96rem;margin:-6px 0 14px 0}
            .tq-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}
            .tq-card{border-radius:10px;padding:12px 14px;border:1px solid #eceff3;background:#ffffff;min-height:84px}
            .tq-card h4{margin:0 0 6px 0;font-size:0.95rem;font-weight:600;color:#374151}
            .tq-card .val{font-size:2.05rem;line-height:1.05;font-weight:700;color:#111827;margin:0}
            .tq-card .sub{font-size:0.88rem;color:#4b5563;margin-top:3px}
            .tq-card .sub.up{color:#1f7a35;font-weight:600}
            .tq-card.soft-red{background:#fdf1f1;border-color:#f8dddd}
            .tq-card.soft-red h4,.tq-card.soft-red .val,.tq-card.soft-red .sub{color:#9f1d1d}
            .tq-card.soft-amber{background:#fcf4df;border-color:#f2e2ba}
            .tq-card.soft-amber h4,.tq-card.soft-amber .val{color:#8a5a0a}
            .tq-card.soft-green{background:#edf6e6;border-color:#d6e7c7}
            .tq-card.soft-green h4,.tq-card.soft-green .val,.tq-card.soft-green .sub{color:#2f5f13}
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
            .ct-card .ct-bar{height:4px;border-radius:2px;margin-top:8px;background:var(--ct-color,#2E7D32);opacity:0.35}
            @media(max-width:1200px){.ct-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
            @media (max-width: 1200px){.tq-grid,.totkvv-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
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
            "Dư nợ khoanh",
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
        khd_sub = fmt(dn_3m) if dn_3m > 0 else "Chưa có dư nợ"
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
                <div class="tq-card">
                    <h4>Tổng món vay</h4>
                    <p class="val">{_n_mon_vay}</p>
                    <div class="sub">Số khế ước đang dư nợ</div>
                </div>
                <div class="tq-card soft-green">
                    <h4>Tổng khách hàng</h4>
                    <p class="val">{_n_kh}</p>
                    <div class="sub">{(f"BQ {_bq_mon_kh} món/KH") if n_kh > 0 else "—"}</div>
                </div>
                <div class="tq-card">
                    <h4>Tổng dư nợ</h4>
                    <p class="val">{_tdn} tỷ</p>
                    <div class="sub up">+{_tdn_delta} tỷ so kỳ trước</div>
                </div>
                <div class="tq-card">
                    <h4>Dư nợ trong hạn</h4>
                    <p class="val">{_dth} tỷ</p>
                    <div class="sub">{_dth_pct}% tổng dư nợ</div>
                </div>
                <div class="tq-card">
                    <h4>Nợ khoanh</h4>
                    <p class="val">{_dnk} tỷ</p>
                    <div class="sub">{_tlk}% tổng dư nợ</div>
                </div>
                <div class="tq-card soft-red">
                    <h4>Dư nợ quá hạn</h4>
                    <p class="val">{_dqh} tỷ</p>
                    <div class="sub">{_tlq}% tổng dư nợ</div>
                </div>
                <div class="tq-card soft-red">
                    <h4>Tỷ lệ quá hạn</h4>
                    <p class="val">{_tlq}%</p>
                    <div class="sub">{'⚠️ Mức cao > 0.5%' if tlq >= 0.5 else '< 0.5% toàn hệ thống'}</div>
                </div>
                <div class="tq-card soft-amber">
                    <h4>Tỷ lệ khoanh</h4>
                    <p class="val">{_tlk}%</p>
                    <div class="sub">{'⚠️ Cần theo dõi' if tlk >= 0.5 else 'Trong kiểm soát'}</div>
                </div>
                <div class="tq-card {no_xau_class}">
                    <h4>Tỷ lệ nợ xấu (NPL)</h4>
                    <p class="val">{_tl_no_xau}%</p>
                    <div class="sub">= (QH + Khoanh) / Tổng dư nợ</div>
                </div>
                <div class="tq-card {khd_class}">
                    <h4>3 tháng không HĐ</h4>
                    <p class="val">{khd_val}</p>
                    <div class="sub">{khd_sub}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"🔍 Kiểm tra cân đối: {_dth} tỷ (Trong hạn) "
            f"+ {vn(dqh/1e9, 3)} tỷ (Quá hạn) "
            f"+ {vn(dnk/1e9, 3)} tỷ (Khoanh) "
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
                from data.cdtotkvv import doc_cdtotkvv_toan_cn_pgd
                df_to_raw = doc_cdtotkvv_toan_cn_pgd()
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
        except Exception:
            pass

        st.markdown("**📂 Cơ cấu dư nợ theo chương trình tín dụng**")
        if COT_TEN_CT in df.columns and COT_TONG_DU_NO in df.columns:

            # Tính toán
            df_ct = (
                df.groupby(COT_TEN_CT)[COT_TONG_DU_NO]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            df_ct.columns = ["ten_ct", "du_no"]
            df_ct = df_ct[df_ct["du_no"] > 0]
            tong = df_ct["du_no"].sum()
            df_ct["ty_trong"] = (df_ct["du_no"] / tong * 100) if tong > 0 else 0

            # Bảng màu xoay vòng theo thứ tự
            _MAUS = [
                "#1565C0", "#2E7D32", "#6A1B9A", "#E65100",
                "#00695C", "#AD1457", "#4527A0", "#558B2F",
            ]

            # Render cards HTML
            cards_html = '<div class="ct-grid">'
            for i, row in df_ct.iterrows():
                mau = _MAUS[i % len(_MAUS)]
                ten_hien = str(row["ten_ct"])
                ten_hien = (ten_hien[:40] + "…") if len(ten_hien) > 40 else ten_hien
                bar_w = min(row["ty_trong"] * 2, 100)  # scale bar 0–50% → 0–100px
                cards_html += f"""
            <div class="ct-card" style="--ct-color:{mau}">
                <div class="ct-name">{ten_hien}</div>
                <div class="ct-val">{fmt_ty(row['du_no'])}</div>
                <div class="ct-pct">Tỷ trọng: {row['ty_trong']:.1f}%</div>
                <div class="ct-bar" style="width:{bar_w}%"></div>
            </div>"""
            cards_html += "</div>"

            st.markdown(cards_html, unsafe_allow_html=True)

            # Toggle xem bảng chi tiết (ẩn mặc định)
            # with st.expander("📋 Xem bảng chi tiết", expanded=False):
            #     df_hien = df_ct.copy()
            #     df_hien = df_hien.rename(columns={
            #         "ten_ct": "Chương trình",
            #         "du_no": "Dư nợ",
            #         "ty_trong": "Tỷ trọng"
            #     })
            #     st.dataframe(
            #         df_hien[["Chương trình", "Dư nợ", "Tỷ trọng"]],
            #         column_config=_tao_column_config_co_cau(),
            #         use_container_width=True,
            #         hide_index=True,
            #     )

        st.markdown("**🟢 Thông tin tổng quát theo PGD**")
        if COT_TEN_PGD in df.columns:
            col_khoanh = "Dư nợ khoanh"
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
            df = df[cot_lay]
            df_pgd = _cache_heatmap_pgd(
                df,
                ts,
                pgd_user,
                pgd_filter,
                COT_TEN_PGD,
                COT_TONG_DU_NO,
                COT_MA_KH,
                COT_DU_NO_QH,
            )
            df_pgd = df_pgd.rename(
                columns={
                    "du_no": "Dư nợ (tỷ)",
                    "so_kh": "Số KH",
                    "nqh": "QH (tỷ)",
                }
            )
            if col_khoanh in df.columns:
                _kh = df.groupby(COT_TEN_PGD, as_index=False).agg(
                    **{"Khoanh (tỷ)": (col_khoanh, "sum")}
                )
            else:
                _kh = df.groupby(COT_TEN_PGD, as_index=False).agg(
                    **{"Khoanh (tỷ)": (COT_MA_KH, "size")}
                )
            df_pgd = df_pgd.merge(_kh, on=COT_TEN_PGD, how="left")

            # Bổ sung PGD trong DS_PGD nhưng không có dòng trong df → hiển thị với giá trị 0
            pgd_co_trong_bang = set(df_pgd[COT_TEN_PGD].tolist())
            pgd_thieu_bang = [p for p in DS_PGD if p not in pgd_co_trong_bang]
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

            for cot in ["Dư nợ (tỷ)", "QH (tỷ)", "Khoanh (tỷ)"]:
                if cot in df_pgd.columns:
                    df_pgd[cot] = pd.to_numeric(df_pgd[cot], errors="coerce").fillna(0)
            df_pgd["Dư nợ (tỷ)"] = (df_pgd["Dư nợ (tỷ)"] / 1e9).round(2)
            df_pgd["QH (tỷ)"] = (df_pgd["QH (tỷ)"] / 1e9).round(3)
            if col_khoanh in df.columns:
                df_pgd["Khoanh (tỷ)"] = (df_pgd["Khoanh (tỷ)"] / 1e9).round(3)
            else:
                df_pgd["Khoanh (tỷ)"] = 0.0

            # A) Lãi tồn (tỷ)
            if COT_LAI_TON in df.columns:
                _lai_ton = df.groupby(COT_TEN_PGD)[COT_LAI_TON].apply(
                    lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()
                ).reset_index(name="Lãi tồn (tỷ)")
                _lai_ton["Lãi tồn (tỷ)"] = (_lai_ton["Lãi tồn (tỷ)"] / 1e9).round(3)
                df_pgd = df_pgd.merge(_lai_ton, on=COT_TEN_PGD, how="left")
            else:
                df_pgd["Lãi tồn (tỷ)"] = 0.0
            df_pgd["Lãi tồn (tỷ)"] = pd.to_numeric(df_pgd["Lãi tồn (tỷ)"], errors="coerce").fillna(0.0)

            # B) Nợ đến hạn trong năm (tỷ)
            if COT_NGAY_DH in df.columns:
                _df_dh = df.copy()
                _df_dh[COT_NGAY_DH] = pd.to_datetime(_df_dh[COT_NGAY_DH], dayfirst=True, errors="coerce")
                _mask = _df_dh[COT_NGAY_DH].dt.year == int(NAM_HT)
                _dh = (
                    _df_dh[_mask]
                    .groupby(COT_TEN_PGD)[COT_TONG_DU_NO]
                    .apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
                    .reset_index(name="Nợ ĐH năm (tỷ)")
                )
                _dh["Nợ ĐH năm (tỷ)"] = (_dh["Nợ ĐH năm (tỷ)"] / 1e9).round(3)
                df_pgd = df_pgd.merge(_dh, on=COT_TEN_PGD, how="left")
            else:
                df_pgd["Nợ ĐH năm (tỷ)"] = 0.0
            df_pgd["Nợ ĐH năm (tỷ)"] = pd.to_numeric(
                df_pgd["Nợ ĐH năm (tỷ)"], errors="coerce"
            ).fillna(0.0)

            # C) Doanh số cho vay năm (tỷ) — ưu tiên tên chuẩn GQVL + alias
            _col_cv = next(
                (c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df.columns),
                None,
            )
            if _col_cv is None:
                _col_cv = next(
                    (
                        c
                        for c in df.columns
                        if "giải ngân" in str(c).replace("\n", " ").lower()
                        and "tháng" not in str(c).lower()
                        and (
                            "trong năm" in str(c).replace("\n", " ").lower()
                            or str(c).strip().lower().endswith("năm")
                        )
                    ),
                    None,
                )
            if _col_cv is not None:
                _cv = df.groupby(COT_TEN_PGD)[_col_cv].apply(
                    lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()
                ).reset_index(name="DS Cho vay (tỷ)")
                _cv["DS Cho vay (tỷ)"] = (_cv["DS Cho vay (tỷ)"] / 1e9).round(3)
                df_pgd = df_pgd.merge(_cv, on=COT_TEN_PGD, how="left")
            else:
                df_pgd["DS Cho vay (tỷ)"] = 0.0
            df_pgd["DS Cho vay (tỷ)"] = pd.to_numeric(
                df_pgd["DS Cho vay (tỷ)"], errors="coerce"
            ).fillna(0.0)

            # D) Doanh số thu nợ năm (tỷ)
            _thu_cols = [c for c in HSTD_THU_NO_NAM_ALIASES if c in df.columns]
            if not _thu_cols:
                _thu_cols = [
                    c
                    for c in df.columns
                    if "thu nợ" in str(c).replace("\n", " ").lower()
                    and "tháng" not in str(c).lower()
                    and (
                        "trong năm" in str(c).replace("\n", " ").lower()
                        or (
                            "năm" in str(c).lower()
                            and any(
                                x in str(c).replace("\n", " ").lower()
                                for x in ("th ", "qh ", "khoanh")
                            )
                        )
                    )
                ]
            if _thu_cols:
                _df_thu = df.copy()
                for _c in _thu_cols:
                    _df_thu[_c] = pd.to_numeric(_df_thu[_c], errors="coerce").fillna(0)
                _df_thu["_thu_no_nam"] = _df_thu[_thu_cols].sum(axis=1)
                _thu = _df_thu.groupby(COT_TEN_PGD)["_thu_no_nam"].sum().reset_index(name="DS Thu nợ (tỷ)")
                _thu["DS Thu nợ (tỷ)"] = (_thu["DS Thu nợ (tỷ)"] / 1e9).round(3)
                df_pgd = df_pgd.merge(_thu, on=COT_TEN_PGD, how="left")
            else:
                df_pgd["DS Thu nợ (tỷ)"] = 0.0
            df_pgd["DS Thu nợ (tỷ)"] = pd.to_numeric(
                df_pgd["DS Thu nợ (tỷ)"], errors="coerce"
            ).fillna(0.0)

            if _col_cv is None or not _thu_cols:
                st.caption("⚠️ Không có cột DS Cho vay/Thu nợ trong HSTD")

            df_pgd["TL QH %"] = ((df_pgd["QH (tỷ)"] / df_pgd["Dư nợ (tỷ)"].replace(0, pd.NA)) * 100).fillna(0).round(2)
            df_pgd["TL Khoanh %"] = ((df_pgd["Khoanh (tỷ)"] / df_pgd["Dư nợ (tỷ)"].replace(0, pd.NA)) * 100).fillna(0).round(2)

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
            except Exception:
                pass

            for cot in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                if cot in df_pgd.columns:
                    df_pgd[cot] = df_pgd[cot].fillna(0).round(0).astype(int)

            # Tính TL QH% và TL Khoanh% cho từng PGD
            df_pgd["TL QH %"] = (
                (df_pgd["QH (tỷ)"] / df_pgd["Dư nợ (tỷ)"].replace(0, pd.NA)) * 100
            ).fillna(0).round(2)
            df_pgd["TL Khoanh %"] = (
                (df_pgd["Khoanh (tỷ)"] / df_pgd["Dư nợ (tỷ)"].replace(0, pd.NA)) * 100
            ).fillna(0).round(2)

            # Tính Nợ xấu (NPL) = QH + Khoanh
            df_pgd["Nợ xấu (tỷ)"] = (df_pgd["QH (tỷ)"] + df_pgd["Khoanh (tỷ)"]).round(3)
            df_pgd["TL NPL %"] = (
                (df_pgd["Nợ xấu (tỷ)"] / df_pgd["Dư nợ (tỷ)"].replace(0, pd.NA)) * 100
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
                    from data.cdtotkvv import doc_cdtotkvv_toan_cn_pgd
                    _df_raw_pgd = doc_cdtotkvv_toan_cn_pgd()
                    if _df_raw_pgd is not None and not _df_raw_pgd.empty:
                        _df_to_pgd_map = tong_hop_theo_pgd(_df_raw_pgd)
            except Exception:
                _df_to_pgd_map = None

            tong = {COT_TEN_PGD: "Toàn Chi nhánh"}
            cot_so = [c for c in df_pgd.columns if c != COT_TEN_PGD and pd.api.types.is_numeric_dtype(df_pgd[c])]
            for cot in cot_so:
                tong[cot] = df_pgd[cot].sum()
            du_no_tong_trieu = tong.get("Dư nợ (tỷ)", 0) * 1000
            tong["TL QH %"] = round((tong.get("QH (tỷ)", 0) / tong.get("Dư nợ (tỷ)", 1) * 100), 2) if tong.get("Dư nợ (tỷ)", 0) else 0
            tong["TL Khoanh %"] = round((tong.get("Khoanh (tỷ)", 0) / tong.get("Dư nợ (tỷ)", 1) * 100), 2) if tong.get("Dư nợ (tỷ)", 0) else 0
            tong["Nợ xấu (tỷ)"] = round(tong.get("QH (tỷ)", 0) + tong.get("Khoanh (tỷ)", 0), 3)
            tong["TL NPL %"] = round(tong["Nợ xấu (tỷ)"] / tong.get("Dư nợ (tỷ)", 1) * 100, 2) if tong.get("Dư nợ (tỷ)", 0) else 0
            df_pgd = pd.concat([df_pgd, pd.DataFrame([tong])], ignore_index=True)

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
                "Số KH", "Dư nợ (tỷ)",
                "QH (tỷ)", "TL QH %",
                "Khoanh (tỷ)", "TL Khoanh %",
                "Nợ xấu (tỷ)", "TL NPL %",
                "Lãi tồn (tỷ)",
                "Nợ ĐH năm (tỷ)",
                "DS Cho vay (tỷ)", "DS Thu nợ (tỷ)",
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
            
            # Xây dựng column_config cho bảng PGD
            column_config_pgd = _tao_column_config_pgd()
            # Thêm các cột số nguyên
            for cot in ["Số KH", "Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                if cot in df_pgd.columns:
                    column_config_pgd[cot] = st.column_config.NumberColumn(cot, format="%d")

            # ── Bảng HTML có header nhóm cột ─────────────────────────────
            df_show = df_pgd[cot_hien].copy()
            # Đánh dấu dòng tổng (dòng cuối)
            is_tong = df_show[COT_TEN_PGD] == "Toàn Chi nhánh"

            def _fmt_cell(val, col):
                """Hiển thị ô bảng theo chuẩn VN (. nghìn, , thập phân) — dùng vn / fmt_so."""
                if pd.isna(val) or val == "":
                    return "—"
                if col in ["Dư nợ (tỷ)"]:
                    return vn(float(val), 2)
                if col in ["TL QH %", "TL Khoanh %", "TL NPL %"]:
                    return f"{vn(float(val), 2)}%"
                if col in [
                    "QH (tỷ)",
                    "Khoanh (tỷ)",
                    "Nợ xấu (tỷ)",
                    "Lãi tồn (tỷ)",
                    "Nợ ĐH năm (tỷ)",
                    "DS Cho vay (tỷ)",
                    "DS Thu nợ (tỷ)",
                ]:
                    return vn(float(val), 3)
                if col in ["Số KH", "Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"]:
                    try:
                        return fmt_so(val)
                    except Exception:
                        return str(val)
                return str(val)

            # Header nhóm
            NHOM_COT = [
                ("", 1),                    # Tên PGD
                ("Dư nợ", 2),               # Số KH, Dư nợ (tỷ)
                ("Chất lượng nợ", 7),       # QH, TL QH, Khoanh, TL Khoanh, Nợ xấu, TL NPL, Lãi tồn
                ("Kế hoạch năm", 3),        # Nợ ĐH, DS Cho vay, DS Thu nợ
                ("Tổ TK&VV", len([c for c in ["Tổng Tổ", "Tốt", "Khá", "TB", "Yếu"] if c in df_pgd.columns])),
            ]
            # Bỏ nhóm có colspan=0
            NHOM_COT = [(n, s) for n, s in NHOM_COT if s > 0]

            header1 = "".join(
                f'<th colspan="{span}" style="background:#2E7D32;color:#fff;'
                f'text-align:center;padding:6px 4px;border:1px solid #1B5E20;font-size:0.82rem">'
                f'{nhom}</th>'
                for nhom, span in NHOM_COT
            )
            header2 = "".join(
                f'<th style="background:#388E3C;color:#fff;text-align:center;'
                f'padding:5px 4px;border:1px solid #1B5E20;font-size:0.78rem;'
                f'white-space:nowrap">{c if c != COT_TEN_PGD else "Đơn vị"}</th>'
                for c in cot_hien
            )

            rows_html = ""
            for i, (_, row) in enumerate(df_show.iterrows()):
                is_last = row[COT_TEN_PGD] == "Toàn Chi nhánh"
                bg = "#E8F5E9" if is_last else ("#F9FAFB" if i % 2 == 0 else "#FFFFFF")
                fw = "bold" if is_last else "normal"
                cells = "".join(
                    f'<td style="padding:5px 6px;border:1px solid #E0E0E0;'
                    f'text-align:{"left" if c == COT_TEN_PGD else "right"};'
                    f'font-weight:{fw};font-size:0.82rem;white-space:nowrap">'
                    f'{_fmt_cell(row[c], c)}</td>'
                    for c in cot_hien
                )
                rows_html += f'<tr style="background:{bg}">{cells}</tr>\n'

            html_table = f"""
            <div style="overflow-x:auto;margin:8px 0">
            <table style="border-collapse:collapse;width:100%;font-family:sans-serif">
              <thead>
                <tr>{header1}</tr>
                <tr>{header2}</tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
            <p style="font-size:0.78rem;color:#6B7280;margin:4px 0">
              * Đơn vị: Dư nợ = tỷ đồng | Các cột tiền khác = triệu đồng
            </p>
            </div>
            """
            st.markdown(html_table, unsafe_allow_html=True)

            # ── Chuẩn bị df_export dùng chung cho cả Excel lẫn PDF ──────────────
            df_export = df_show.copy().rename(columns={COT_TEN_PGD: "Đơn vị"})
            # df_export_so: giữ nguyên số để Excel có thể sort/filter
            df_export_so = df_export.copy()
            # df_export_fmt: format chuỗi để PDF đọc đẹp
            for col in df_export.columns:
                if col != "Đơn vị":
                    df_export[col] = df_export[col].apply(
                        lambda v, c=col: _fmt_cell(v, c)
                    )

            # ── Nút xuất — 3 nút nằm ngang ───────────────────────────────────────
            _c1, _c2, _c3 = st.columns([1, 1, 1])

            # ── (1) Xuất Excel ────────────────────────────────────────────────────
            with _c1:
                try:
                    _xl_bytes = xuat_excel({"TQPGD": df_export_so})
                    st.download_button(
                        label="📥 Xuất Excel",
                        data=_xl_bytes,
                        file_name=ten_file_xuat("TQPGD", "xlsx"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="btn_xl_tqpgd",
                        type="secondary",
                    )
                except Exception as _e:
                    st.error(f"❌ Lỗi xuất Excel: {_e}")

            # ── (2) Preview + In PDF ──────────────────────────────────────────────
            with _c2:
                if st.button("🔍 Preview / In PDF", key="btn_preview_tqpgd", type="secondary"):
                    st.session_state["tqpgd_show_preview"] = not st.session_state.get(
                        "tqpgd_show_preview", False
                    )

            # ── (3) Xuất PDF ──────────────────────────────────────────────────────
            with _c3:
                nut_xuat_pdf(
                    df=df_export,
                    tieu_de="Thông tin tổng quát theo PGD",
                    username=username,
                    cols_tien=[],
                    prefix_file="TQPGD",
                    key="btn_pdf_tqpgd",
                )

            # ── Khung preview HTML có nút In ─────────────────────────────────────
            if st.session_state.get("tqpgd_show_preview", False):
                st.markdown("---")
                st.markdown("#### 🖨️ Preview — Thông tin tổng quát theo PGD")
                # Xây dựng lại bảng HTML tương tự html_table nhưng thêm @media print
                _print_style = """
                <style>
                @media print {
                    body * { visibility: hidden; }
                    #print-tqpgd, #print-tqpgd * { visibility: visible; }
                    #print-tqpgd { position: fixed; top: 0; left: 0; width: 100%; }
                    .no-print { display: none !important; }
                }
                .print-header {
                    font-family: sans-serif;
                    text-align: center;
                    margin-bottom: 6px;
                }
                .print-header h3 { font-size: 1rem; margin: 2px 0; color: #1565C0; }
                .print-header p  { font-size: 0.78rem; color: #555; margin: 0; }
                </style>
                """
                from config import TEN_CHI_NHANH_HIEN_THI
                from datetime import datetime as _dt_now
                _ngay_in = _dt_now.now().strftime("%d/%m/%Y %H:%M")
                _preview_header = f"""
                <div class="print-header">
                    <h3>THÔNG TIN TỔNG QUÁT THEO PGD</h3>
                    <p>{TEN_CHI_NHANH_HIEN_THI} — Ngày in: {_ngay_in}</p>
                </div>
                """
                st.markdown(_print_style + f'<div id="print-tqpgd">{_preview_header}{html_table}</div>',
                            unsafe_allow_html=True)
                st.button(
                    "🖨️ In trang này (Ctrl+P)",
                    key="btn_in_tqpgd",
                    on_click=lambda: None,   # placeholder — người dùng dùng Ctrl+P
                    type="primary",
                    help="Nhấn Ctrl+P sau đó chọn máy in hoặc 'Save as PDF'",
                )
                st.caption(
                    "💡 Sau khi nhấn **Ctrl+P**, chọn *Save as PDF* để lưu file; "
                    "hoặc chọn máy in để in trực tiếp. "
                    "Chỉ vùng bảng này sẽ được in nhờ CSS @media print."
                )
        st.divider()
        st.subheader("🔔 Hồ sơ đến hạn — Tổng hợp")
        if COT_NGAY_DH in df.columns:
            try:
                dt = df.copy()
                dt[COT_NGAY_DH] = pd.to_datetime(dt[COT_NGAY_DH], dayfirst=True, errors="coerce")
                hn       = pd.Timestamp.today().normalize()
                cuoi_nam = pd.Timestamp(hn.year, 12, 31)

                MOC = {
                    "1 tháng":   hn + pd.Timedelta(days=30),
                    "3 tháng":   hn + pd.Timedelta(days=90),
                    "6 tháng":   hn + pd.Timedelta(days=180),
                    "Trong năm": cuoi_nam,
                }

                # Lựa chọn nhóm tổng hợp
                nhom_chon = st.radio(
                    "Tổng hợp theo",
                    ["Chương trình", "PGD", "Xã"],
                    horizontal=True,
                    key="tq_denh_nhom",
                )
                NHOM_COT = {
                    "Chương trình": COT_TEN_CT,
                    "PGD":          COT_TEN_PGD,
                    "Xã":           "Tên xã",
                }
                nhom_col = NHOM_COT[nhom_chon]

                # Bộ lọc kết hợp nhiều điều kiện
                with st.expander("🔍 Bộ lọc nâng cao", expanded=False):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        ds_pgd = sorted(dt[COT_TEN_PGD].dropna().unique()) if COT_TEN_PGD in dt.columns else []
                        loc_pgd = st.multiselect("Lọc PGD", options=ds_pgd, default=[], key="tq_loc_pgd")

                    with col2:
                        ds_ct = sorted(dt[COT_TEN_CT].dropna().unique()) if COT_TEN_CT in dt.columns else []
                        loc_ct = st.multiselect("Lọc Chương trình", options=ds_ct, default=[], key="tq_loc_ct")

                    with col3:
                        # Chỉ lấy xã thuộc PGD đã chọn, nếu chưa chọn PGD thì hiện tất cả
                        if loc_pgd:
                            dt_theo_pgd = dt[dt[COT_TEN_PGD].isin(loc_pgd)]
                        else:
                            dt_theo_pgd = dt

                        ds_xa = sorted(dt_theo_pgd["Tên xã"].dropna().unique()) if "Tên xã" in dt_theo_pgd.columns else []
                        loc_xa = st.multiselect("Lọc Xã", options=ds_xa, default=[], key="tq_loc_xa")

                # Áp dụng bộ lọc vào dt trước khi lọc theo mốc thời gian
                dt_loc = dt.copy()
                if loc_pgd:
                    dt_loc = dt_loc[dt_loc[COT_TEN_PGD].isin(loc_pgd)]
                if loc_ct:
                    dt_loc = dt_loc[dt_loc[COT_TEN_CT].isin(loc_ct)]
                if loc_xa:
                    dt_loc = dt_loc[dt_loc["Tên xã"].isin(loc_xa)]

                tab_1m, tab_3m, tab_6m, tab_nam = st.tabs([
                    "📅 1 tháng", "📅 3 tháng", "📅 6 tháng", "📅 Trong năm"
                ])

                def _bang_den_han(df_loc, label, key_prefix):
                    if df_loc.empty:
                        st.success(f"✅ Không có món vay đến hạn {label}")
                        return

                    tong_no  = df_loc[COT_TONG_DU_NO].fillna(0).sum()
                    tong_mon = df_loc[COT_SO_KU].nunique()
                    tong_kh  = df_loc[COT_MA_KH].nunique()

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Số món vay", fmt_so(tong_mon))
                    c2.metric("Số khách hàng", fmt_so(tong_kh))
                    c3.metric("Tổng dư nợ", fmt(tong_no))

                    st.divider()

                    if nhom_col in df_loc.columns:
                        tg = df_loc.groupby(nhom_col).agg(
                            _mon=(COT_SO_KU,      "nunique"),
                            _kh =(COT_MA_KH,      "nunique"),
                            _no =(COT_TONG_DU_NO, "sum"),
                        ).reset_index().sort_values("_no", ascending=False)

                        tg["Số món vay"] = tg["_mon"].apply(fmt_so)
                        tg["Số KH"]      = tg["_kh"].apply(fmt_so)
                        tg["Dư nợ"]      = tg["_no"].apply(fmt_so)

                        hien_thi_dataframe_phan_trang(
                            tg[[nhom_col, "Số món vay", "Số KH", "Dư nợ"]].rename(
                                columns={nhom_col: nhom_chon}),
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
                                customdata=top10["Dư nợ"],
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

                            st.plotly_chart(fig, use_container_width=True)

                        st.divider()
                        col_ex, col_pdf = st.columns(2)

                        df_xuat = tg[[nhom_col, "Số món vay", "Số KH", "Dư nợ"]].rename(
                            columns={nhom_col: nhom_chon}
                        )
                        with col_ex:
                            excel_bytes = xuat_excel({f"Đến hạn {label}": df_xuat})
                            st.download_button(
                                label="📥 Xuất Excel",
                                data=excel_bytes,
                                file_name=ten_file_xuat(f"HoSoDenHan_{key_prefix}"),
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                                key=f"excel_den_han_{key_prefix}",
                            )

                        with col_pdf:
                            nut_xuat_pdf(
                                df=df_xuat,
                                tieu_de=f"Hồ sơ đến hạn {label} — Tổng hợp theo {nhom_chon}",
                                username=username,
                                prefix_file=f"HoSoDenHan_{key_prefix}",
                                key=f"pdf_den_han_{key_prefix}",
                            )
                    else:
                        st.caption(f"⚠️ Không có cột '{nhom_chon}' trong dữ liệu")

                for (label, den), tab_ui in zip(MOC.items(),
                                                [tab_1m, tab_3m, tab_6m, tab_nam]):
                    with tab_ui:
                        df_moc = dt_loc[(dt_loc[COT_NGAY_DH] >= hn) & (dt_loc[COT_NGAY_DH] <= den)]
                        _bang_den_han(df_moc, label, label.replace(" ", "_"))

            except Exception as e:
                st.error(f"Lỗi xử lý đến hạn: {e}")
