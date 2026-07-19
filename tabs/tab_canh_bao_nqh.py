"""Tab Cảnh báo Tín dụng — 7 sub-tab gom tất cả cảnh báo.
Hoạt động ở cả phân hệ Chi nhánh (CN) lẫn PGD.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from alert_center import canh_bao_no_khoanh_sap_het_han
from auth import la_admin_cn, la_phan_he_cn, normalize_role
from logger import get_logger
from config import (
    COT_CHUYEN_QH_TRONG_THANG,
    COT_CQH_NAM,
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DVUT,
    COT_LAI_THANG,
    COT_LAI_TON,
    COT_NGAY_DH,
    COT_NGAY_DH_HD,
    COT_NGAY_GH_GN,
    COT_NGAY_HH_KHOANH,
    COT_NGAY_SL,
    COT_SO_KU,
    COT_SO_LAN_GH,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_TO_TRUONG,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_PGD,
)
from data.hstd import (
    canh_bao_migration_cached,
    danh_dau_khong_hd_cached,
    ds_chi_tiet_khong_hd,
    tong_hop_khong_hd_cached,
)
from pdf_service import nut_xuat_pdf
from state_manager import SCMStateManager
from tabs.base_tab import TabContext
from utils import (
    fmt,
    fmt_so,
    fmt_ty,
    hien_thi_dataframe_phan_trang,
    lay_ngay_so_lieu,
    vn,
    xuat_excel,
)

_COT_KHOANH = "Dư nợ khoanh"
logger = get_logger(__name__)


def _tim_cot(df: pd.DataFrame, *cac_ten: str) -> str | None:
    if not cac_ten:
        return None
    for ten in cac_ten:
        if ten in df.columns:
            return ten
    ten_dau = cac_ten[0]
    for c in df.columns:
        if unicodedata.normalize("NFC", c) == unicodedata.normalize("NFC", ten_dau):
            return c
        if ten_dau.lower() in c.lower() or c.lower() in ten_dau.lower():
            return c
    return None


def _dem_den_han(df: pd.DataFrame, n_thang: int, ref_date: datetime | None = None) -> int:
    if df.empty or COT_NGAY_DH not in df.columns:
        return 0
    today = pd.Timestamp(ref_date or datetime.now()).normalize()
    ngay_dh = pd.to_datetime(df[COT_NGAY_DH], errors="coerce", dayfirst=True)
    end_date = today + pd.DateOffset(months=n_thang)
    return int(((ngay_dh >= today) & (ngay_dh <= end_date)).sum())


def _selectbox_safe(label: str, options: list, key: str):
    if not options:
        options = ["Tất cả"]
    prev = st.session_state.get(key)
    index = 0 if prev not in options else int(options.index(prev))
    return st.selectbox(label, options=options, index=index, key=key)


def _ap_dung_loc_xa_to_truong(df: pd.DataFrame, key_prefix: str) -> tuple[pd.DataFrame, str, str]:
    df_loc = df
    state = SCMStateManager()

    col_xa, col_to = st.columns(2)

    with col_xa:
        if COT_TEN_XA in df_loc.columns:
            ds_xa = sorted(df_loc[COT_TEN_XA].dropna().astype(str).unique().tolist())
            _key_xa = f"{key_prefix}loc_xa"
            _desired_xa = state.filter_xa or "Tất cả"
            if _key_xa not in st.session_state:
                st.session_state[_key_xa] = _desired_xa if _desired_xa in (["Tất cả"] + ds_xa) else "Tất cả"
            loc_xa = _selectbox_safe("Lọc Xã", ["Tất cả"] + ds_xa, key=f"{key_prefix}loc_xa")
        else:
            loc_xa = "Tất cả"
            st.caption("Không có cột Xã")

    if loc_xa != "Tất cả" and COT_TEN_XA in df_loc.columns:
        df_loc = df_loc[df_loc[COT_TEN_XA] == loc_xa]
    state.filter_xa = None if loc_xa == "Tất cả" else loc_xa

    with col_to:
        if COT_TEN_TO_TRUONG in df_loc.columns:
            ds_to = sorted(df_loc[COT_TEN_TO_TRUONG].dropna().astype(str).unique().tolist())
            loc_to = _selectbox_safe(
                "Lọc Tổ trưởng", ["Tất cả"] + ds_to, key=f"{key_prefix}loc_to_truong"
            )
        else:
            loc_to = "Tất cả"
            st.caption("Không có cột Tổ trưởng")

    if loc_to != "Tất cả" and COT_TEN_TO_TRUONG in df_loc.columns:
        df_loc = df_loc[df_loc[COT_TEN_TO_TRUONG] == loc_to]

    return df_loc, loc_xa, loc_to


def _ap_dung_loc_pgd_xa_to_truong(
    df: pd.DataFrame,
    ds_pgd_all: list,
    la_cn: bool,
    key_prefix: str,
    pgd_user: str | None = None,
) -> tuple[pd.DataFrame, str, str, str]:
    df_loc = df
    loc_pgd = "Tất cả"
    state = SCMStateManager()

    col_pgd, col_xa, col_to = st.columns(3)

    with col_pgd:
        if la_cn and COT_TEN_PGD in df_loc.columns:
            ds_pgd = list(ds_pgd_all or [])
            _key_pgd = f"{key_prefix}loc_pgd"
            _desired_pgd = state.filter_pgd or "Tất cả"
            if _key_pgd not in st.session_state:
                st.session_state[_key_pgd] = _desired_pgd if _desired_pgd in (["Tất cả"] + ds_pgd) else "Tất cả"
            loc_pgd = _selectbox_safe("Lọc PGD", ["Tất cả"] + ds_pgd, key=f"{key_prefix}loc_pgd")
        else:
            pgd_fixed = pgd_user
            if not pgd_fixed and COT_TEN_PGD in df_loc.columns:
                _vals = sorted(df_loc[COT_TEN_PGD].dropna().unique().tolist())
                if len(_vals) == 1:
                    pgd_fixed = _vals[0]
            if pgd_fixed:
                loc_pgd = pgd_fixed
                st.caption(f"PGD: {pgd_fixed}")
            else:
                loc_pgd = "Tất cả"
                st.caption("Lọc PGD (CN)")

    if loc_pgd != "Tất cả" and COT_TEN_PGD in df_loc.columns:
        df_loc = df_loc[df_loc[COT_TEN_PGD] == loc_pgd]
    _new_pgd = None if loc_pgd == "Tất cả" else loc_pgd
    if _new_pgd != state.filter_pgd:
        state.filter_pgd = _new_pgd

    with col_xa:
        if COT_TEN_XA in df_loc.columns:
            ds_xa = sorted(df_loc[COT_TEN_XA].dropna().astype(str).unique().tolist())
            _key_xa = f"{key_prefix}loc_xa"
            _desired_xa = state.filter_xa or "Tất cả"
            if _key_xa not in st.session_state:
                st.session_state[_key_xa] = _desired_xa if _desired_xa in (["Tất cả"] + ds_xa) else "Tất cả"
            loc_xa = _selectbox_safe("Lọc Xã", ["Tất cả"] + ds_xa, key=f"{key_prefix}loc_xa")
        else:
            loc_xa = "Tất cả"
            st.caption("Không có cột Xã")

    if loc_xa != "Tất cả" and COT_TEN_XA in df_loc.columns:
        df_loc = df_loc[df_loc[COT_TEN_XA] == loc_xa]
    state.filter_xa = None if loc_xa == "Tất cả" else loc_xa

    with col_to:
        if COT_TEN_TO_TRUONG in df_loc.columns:
            ds_to = sorted(df_loc[COT_TEN_TO_TRUONG].dropna().astype(str).unique().tolist())
            loc_to = _selectbox_safe(
                "Lọc Tổ trưởng", ["Tất cả"] + ds_to, key=f"{key_prefix}loc_to_truong"
            )
        else:
            loc_to = "Tất cả"
            st.caption("Không có cột Tổ trưởng")

    if loc_to != "Tất cả" and COT_TEN_TO_TRUONG in df_loc.columns:
        df_loc = df_loc[df_loc[COT_TEN_TO_TRUONG] == loc_to]

    return df_loc, loc_pgd, loc_xa, loc_to


# ─── Sub-tab 1: Tổng hợp ──────────────────────────────────────────────────────

def _render_tong_hop(
    df_full: pd.DataFrame,
    df_kh: pd.DataFrame,
    ds_pgd_all: list,
    la_cn: bool,
    key_prefix: str,
    role: str,
) -> None:
    df_full_loc, loc_pgd, loc_xa, loc_to = _ap_dung_loc_pgd_xa_to_truong(
        df_full, ds_pgd_all, la_cn, key_prefix
    )
    df_kh_loc = df_kh.copy()
    if loc_pgd != "Tất cả" and COT_TEN_PGD in df_kh_loc.columns:
        df_kh_loc = df_kh_loc[df_kh_loc[COT_TEN_PGD] == loc_pgd]
    if loc_xa != "Tất cả" and COT_TEN_XA in df_kh_loc.columns:
        df_kh_loc = df_kh_loc[df_kh_loc[COT_TEN_XA] == loc_xa]
    if loc_to != "Tất cả" and COT_TEN_TO_TRUONG in df_kh_loc.columns:
        df_kh_loc = df_kh_loc[df_kh_loc[COT_TEN_TO_TRUONG] == loc_to]

    for _df in (df_full_loc, df_kh_loc):
        if COT_TEN_PGD in _df.columns and isinstance(_df[COT_TEN_PGD].dtype, pd.CategoricalDtype):
            _df[COT_TEN_PGD] = _df[COT_TEN_PGD].astype(object)

    # ─── Mốc thời gian tham chiếu: ưu tiên COT_NGAY_SL, fallback datetime.now() ──
    today = lay_ngay_so_lieu(df_full_loc) or datetime.now()

    # ─── Ngưỡng cảnh báo cấu hình được (P2.4) ──
    import db
    nguong_nh = db.doc_kv("nguong_nh") or 10
    nguong_td = db.doc_kv("nguong_td") or 5
    username = st.session_state.get("username", "unknown")

    if la_cn and la_admin_cn(role):
        with st.expander("⚙️ Cài đặt ngưỡng cảnh báo", expanded=False):
            c1, c2 = st.columns(2)
            nguong_nh_new = c1.number_input(
                "Ngưỡng Nguy hiểm (tổng cảnh báo ≥)",
                min_value=1, max_value=100, value=int(nguong_nh), step=1,
                key=f"{key_prefix}nguong_nh",
            )
            nguong_td_new = c2.number_input(
                "Ngưỡng Theo dõi (tổng cảnh báo ≥)",
                min_value=1, max_value=100, value=int(nguong_td), step=1,
                key=f"{key_prefix}nguong_td",
            )
            if nguong_nh_new != nguong_nh or nguong_td_new != nguong_td:
                if st.button("💾 Lưu ngưỡng", key=f"{key_prefix}luu_nguong"):
                    db.ghi_kv("nguong_nh", nguong_nh_new, username)
                    db.ghi_kv("nguong_td", nguong_td_new, username)
                    db.ghi_audit(username, "luu_nguong_canh_bao",
                                 f"Ngưỡng NH={nguong_nh_new}, TD={nguong_td_new}")
                    st.rerun()
            nguong_nh, nguong_td = nguong_nh_new, nguong_td_new

    khoanh_data = canh_bao_no_khoanh_sap_het_han(
        df_full_loc[df_full_loc.get(_COT_KHOANH, pd.Series(0)).fillna(0) > 0]
        if _COT_KHOANH in df_full_loc.columns
        else pd.DataFrame()
    )

    khd_tong = int(df_kh_loc["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh_loc.columns else 0
    co_nqh = COT_DU_NO_QH in df_full_loc.columns and (df_full_loc[COT_DU_NO_QH].fillna(0) > 0).any()

    co_gia_han = COT_NGAY_DH_HD in df_full_loc.columns and COT_NGAY_DH in df_full_loc.columns
    if co_gia_han:
        ngay_hd = pd.to_datetime(df_full_loc[COT_NGAY_DH_HD], errors="coerce", dayfirst=True)
        ngay_gh = pd.to_datetime(df_full_loc[COT_NGAY_DH], errors="coerce", dayfirst=True)
        da_gh = ngay_gh > ngay_hd
        # dùng ngay_gh trực tiếp để tránh lệch index khi subset
        so_gh_thang = da_gh & (ngay_gh.dt.year == today.year) & (ngay_gh.dt.month == today.month)
        so_gh_nam   = da_gh & (ngay_gh.dt.year == today.year) & (ngay_gh.dt.month > today.month)

    st.markdown("""
    <style>
    .cb-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-bottom:14px}
    .cb-card{border-radius:12px;padding:20px 14px 18px;border:2px solid #d1d5db;text-align:center;min-height:120px;display:flex;flex-direction:column;justify-content:center;gap:4px}
    .cb-card .cb-value{font-size:2.4rem;font-weight:800;line-height:1.1;margin:0}
    .cb-card .cb-label{font-size:0.9rem;font-weight:700;margin:0}
    .cb-card .cb-sub{font-size:0.82rem;font-weight:500;margin:0;line-height:1.4;opacity:0.85}
    .cb-blue{background:#dbeafe;border-color:#60a5fa}.cb-blue .cb-value{color:#1e3a8a}.cb-blue .cb-label{color:#1d4ed8}.cb-blue .cb-sub{color:#1d4ed8}
    .cb-green{background:#dcfce7;border-color:#4ade80}.cb-green .cb-value{color:#14532d}.cb-green .cb-label{color:#15803d}.cb-green .cb-sub{color:#15803d}
    .cb-red{background:#fee2e2;border-color:#f87171}.cb-red .cb-value{color:#7f1d1d}.cb-red .cb-label{color:#b91c1c}.cb-red .cb-sub{color:#b91c1c}
    .cb-purple{background:#ede9fe;border-color:#a78bfa}.cb-purple .cb-value{color:#4c1d95}.cb-purple .cb-label{color:#6d28d9}.cb-purple .cb-sub{color:#6d28d9}
    @media(max-width:1000px){.cb-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
    @media(max-width:600px){.cb-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>
    """, unsafe_allow_html=True)

    den_han_3t = _dem_den_han(df_full_loc, 3, today)
    khd_class = "cb-red" if khd_tong > 0 else "cb-green"
    nqh_class = "cb-red" if co_nqh else "cb-green"
    so_khan = khoanh_data.get("so_khan", 0)
    so_cb   = khoanh_data.get("so_canh_bao", 0)
    so_khoanh_can_kt = so_khan + so_cb
    khoanh_class = "cb-red" if so_khoanh_can_kt > 0 else "cb-green"
    gh_str = f"{so_gh_thang.sum()}/{so_gh_nam.sum()}" if co_gia_han else "—"

    st.markdown(f"""
    <div class="cb-grid">
        <div class="cb-card cb-blue">
            <div class="cb-label">🔔 Đến hạn ≤ 3 tháng</div>
            <div class="cb-value">{fmt_so(den_han_3t)}</div>
            <div class="cb-sub">Món vay sắp đến hạn</div>
        </div>
        <div class="cb-card {khd_class}">
            <div class="cb-label">⚠️ ≥ 3 tháng không HĐ</div>
            <div class="cb-value">{fmt_so(khd_tong)}</div>
            <div class="cb-sub">Khách hàng ngưng giao dịch</div>
        </div>
        <div class="cb-card {nqh_class}">
            <div class="cb-label">🚨 Có nợ quá hạn</div>
            <div class="cb-value">{"Có" if co_nqh else "Không"}</div>
            <div class="cb-sub">Phát sinh nợ quá hạn</div>
        </div>
        <div class="cb-card {khoanh_class}">
            <div class="cb-label">📌 Khoanh cần kiểm tra</div>
            <div class="cb-value">{fmt_so(so_khoanh_can_kt)}</div>
            <div class="cb-sub">{so_khan} phải KT (≤120d) · {so_cb} theo dõi (121-180d)</div>
        </div>
        <div class="cb-card cb-purple">
            <div class="cb-label">📅 Đã gia hạn (T/N)</div>
            <div class="cb-value">{gh_str}</div>
            <div class="cb-sub">Tháng này / Còn trong năm</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown("**Tổng hợp cảnh báo theo PGD**")

    today_ts = pd.Timestamp(today).normalize()
    end_date = today_ts + pd.DateOffset(months=3)

    if COT_NGAY_DH in df_full_loc.columns and not df_full_loc.empty:
        ngay_dh_all = pd.to_datetime(df_full_loc[COT_NGAY_DH], errors="coerce", dayfirst=True)
        is_den_han = (ngay_dh_all >= today_ts) & (ngay_dh_all <= end_date)
        den_han_by_pgd = is_den_han.groupby(df_full_loc[COT_TEN_PGD]).sum()
    else:
        den_han_by_pgd = pd.Series(dtype=int)

    if COT_DU_NO_QH in df_full_loc.columns:
        has_nqh = pd.to_numeric(df_full_loc[COT_DU_NO_QH], errors="coerce").fillna(0) > 0
        nqh_by_pgd = has_nqh.groupby(df_full_loc[COT_TEN_PGD]).sum()
    else:
        nqh_by_pgd = pd.Series(dtype=int)

    if "is_3m_inactive" in df_kh_loc.columns:
        khd_by_pgd = df_kh_loc.groupby(COT_TEN_PGD)["is_3m_inactive"].sum()
    else:
        khd_by_pgd = pd.Series(dtype=int)

    gh_by_pgd = so_gh_thang.groupby(df_full_loc[COT_TEN_PGD]).sum() if co_gia_han else pd.Series(dtype=int)

    rows_th = []
    for pgd in ds_pgd_all:
        dh = int(den_han_by_pgd.get(pgd, 0))
        khd = int(khd_by_pgd.get(pgd, 0))
        nqh = int(nqh_by_pgd.get(pgd, 0))
        gh = int(gh_by_pgd.get(pgd, 0))
        rows_th.append({"PGD": pgd, "Đến hạn": dh,
                        "3 tháng KHĐ": khd, "Nợ QH": nqh, "GH tháng": gh,
                        "Tổng": dh + khd + nqh + gh})

    df_th = pd.DataFrame(rows_th)
    if not df_th.empty:
        df_th = df_th.sort_values("Tổng", ascending=False).reset_index(drop=True)
        df_th["Mức độ"] = df_th["Tổng"].apply(
            lambda x: "🔴 Nguy hiểm" if x >= nguong_nh
            else ("🟡 Theo dõi" if x >= nguong_td else "🟢 Ổn định"))
        df_th["_css"] = df_th["Tổng"].apply(
            lambda x: "rnh" if x >= nguong_nh
            else ("rtd" if x >= nguong_td else "rok"))
        so_nh = int((df_th["Tổng"] >= nguong_nh).sum())
        so_td = int(((df_th["Tổng"] >= nguong_td) & (df_th["Tổng"] < nguong_nh)).sum())
        so_od = int((df_th["Tổng"] < nguong_td).sum())
        max_dh = int(df_th["Đến hạn"].max()) or 1
        tong_dh = int(df_th["Đến hạn"].sum())

        st.markdown("""
        <style>
        .thb{border-collapse:collapse;font-size:13px;width:100%}
        .thb th{text-align:center;padding:10px 8px;font-weight:600;font-size:11px;opacity:.7;border-bottom:2px solid #e2e8f0;white-space:nowrap}
        .thb th:first-child{text-align:left;padding-left:14px}
        .thb td{text-align:center;padding:8px 6px;border-bottom:1px solid #f1f5f9}
        .thb td:first-child{text-align:left;padding-left:14px;font-weight:600}
        .thb tr.rnh td{background:#fef2f2}.thb tr.rtd td{background:#fffbeb}
        .thb tr:hover td{filter:brightness(.97)}
        .tbadge{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap}
        .tbadge-nh{background:#fee2e2;color:#b91c1c}.tbadge-td{background:#fef3c7;color:#b45309}.tbadge-od{background:#dcfce7;color:#15803d}
        .tv-hot{color:#b91c1c;font-weight:700}.tv-warm{color:#b45309;font-weight:700}.tv-ok{color:#94a3b8}
        .tbar{display:flex;align-items:center;gap:4px;justify-content:center}
        .tbar-tr{width:36px;height:4px;background:#e2e8f0;border-radius:2px;overflow:hidden;flex-shrink:0}
        .tbar-f{height:100%;border-radius:2px}.tbar-n{font-weight:600;min-width:22px;text-align:right;font-size:12px}
        .tleg{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px;font-size:12px}
        .tleg-i{display:flex;align-items:center;gap:5px}.tleg-d{width:8px;height:8px;border-radius:50%;flex-shrink:0}
        .tfoot{display:flex;gap:16px;padding:10px 14px;font-size:11px;flex-wrap:wrap}
        .twrp{border-radius:12px;border:1px solid #e2e8f0;overflow:hidden;margin-bottom:8px}
        @media(max-width:800px){.tkpi{grid-template-columns:repeat(2,1fr)}}
        </style>
        """, unsafe_allow_html=True)

        # KPI cards
        st.markdown(f"""
        <div class="tleg">
            <div class="tleg-i"><span class="tleg-d" style="background:#ef4444"></span> Nguy hiểm ≥{nguong_nh}</div>
            <div class="tleg-i"><span class="tleg-d" style="background:#f59e0b"></span> Theo dõi {nguong_td}–{nguong_nh - 1}</div>
            <div class="tleg-i"><span class="tleg-d" style="background:#22c55e"></span> Ổn định &lt;{nguong_td}</div>
        </div>
        <div class="tkpi" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px">
            <div style="border-radius:12px;padding:12px 14px;text-align:center;background:#fef2f2;border:1px solid #fecaca">
                <div style="font-size:26px;font-weight:800;color:#b91c1c">🔴 {so_nh}</div>
                <div style="font-size:11px;opacity:.7;margin-top:2px">PGD nguy hiểm</div>
            </div>
            <div style="border-radius:12px;padding:12px 14px;text-align:center;background:#fffbeb;border:1px solid #fde68a">
                <div style="font-size:26px;font-weight:800;color:#b45309">🟡 {so_td}</div>
                <div style="font-size:11px;opacity:.7;margin-top:2px">PGD cần theo dõi</div>
            </div>
            <div style="border-radius:12px;padding:12px 14px;text-align:center;background:#f0fdf4;border:1px solid #bbf7d0">
                <div style="font-size:26px;font-weight:800;color:#15803d">🟢 {so_od}</div>
                <div style="font-size:11px;opacity:.7;margin-top:2px">PGD ổn định</div>
            </div>
            <div style="border-radius:12px;padding:12px 14px;text-align:center;background:#eff6ff;border:1px solid #bfdbfe">
                <div style="font-size:26px;font-weight:800;color:#1d4ed8">🔔 {fmt_so(tong_dh)}</div>
                <div style="font-size:11px;opacity:.7;margin-top:2px">Tổng món đến hạn ≤ 3 tháng</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Bảng HTML
        rows_h = []
        for _, r in df_th.iterrows():
            pct_dh = min(100, int(r["Đến hạn"] / max_dh * 100)) if max_dh else 0
            cls = r["_css"]
            v_cls = lambda v, _cls=cls: "tv-hot" if v >= nguong_nh else ("tv-warm" if v >= nguong_td else "tv-ok")
            b_cls = "tbadge-nh" if cls == "rnh" else ("tbadge-td" if cls == "rtd" else "tbadge-od")
            b_txt = "🔴 Nguy hiểm" if cls == "rnh" else ("🟡 Theo dõi" if cls == "rtd" else "🟢 Ổn định")
            rows_h.append(
                f"""<tr class="{cls}">
                <td>{r['PGD']}</td>
                <td><div class="tbar"><div class="tbar-tr"><div class="tbar-f" style="width:{pct_dh}%;background:#3b82f6"></div></div><span class="tbar-n {v_cls(r['Đến hạn'])}">{r['Đến hạn']}</span></div></td>
                <td><span class="{v_cls(r['3 tháng KHĐ'])}">{r['3 tháng KHĐ']}</span></td>
                <td><span class="{v_cls(r['Nợ QH'])}">{r['Nợ QH']}</span></td>
                <td><span class="{v_cls(r['GH tháng'])}">{r['GH tháng']}</span></td>
                <td><strong>{r['Tổng']}</strong></td>
                <td><span class="tbadge {b_cls}">{b_txt}</span></td>
            </tr>""")
        st.markdown(f"""
        <div class="twrp">
        <table class="thb">
        <thead><tr>
            <th style="width:150px">PGD</th>
            <th>🔔 Đến hạn<br><small>≤ 3 tháng</small></th>
            <th>⚠️ 3 tháng<br><small>không HĐ</small></th>
            <th>🚨 Nợ<br><small>quá hạn</small></th>
            <th>📅 GH<br><small>tháng</small></th>
            <th>Tổng<br><small>cảnh báo</small></th>
            <th>Mức độ<br><small>rủi ro</small></th>
        </tr></thead>
        <tbody>
        {''.join(rows_h)}
        </tbody>
        </table>
        <div class="tfoot" style="background:var(--secondary-background-color);border-radius:0 0 12px 12px">
            <span>🔴 <strong>{so_nh}</strong> nguy hiểm</span>
            <span>🟡 <strong>{so_td}</strong> theo dõi</span>
            <span>🟢 <strong>{so_od}</strong> ổn định</span>
            <span style="margin-left:auto">📅 {today.strftime('%d/%m/%Y')}</span>
        </div>
        </div>
        """, unsafe_allow_html=True)

    # ─── P2.3: Trend chart NQH 12 kỳ ──────────────────────────────────────────
    with st.expander("📈 Xu hướng NQH 12 kỳ", expanded=False):
        try:
            import sqlite3
            from db import get_conn
            with get_conn() as conn:
                ky_list = [r[0] for r in conn.execute(
                    "SELECT DISTINCT ky FROM hstd_snapshot ORDER BY ky DESC LIMIT 12"
                ).fetchall()]
            if len(ky_list) < 2:
                st.info("ℹ️ Cần ít nhất 2 kỳ snapshot để hiển thị xu hướng.")
            else:
                ky_list.reverse()
                with get_conn() as conn:
                    df_trend = pd.read_sql_query(
                        "SELECT ky, SUM(du_no_qh) qh, SUM(du_no_khoanh) khoanh "
                        "FROM hstd_snapshot WHERE ma_ct='ALL' AND nguon_von='ALL' "
                        "AND ten_pgd!='__CN__' AND ky IN ({}) "
                        "GROUP BY ky ORDER BY ky".format(','.join('?' * len(ky_list))),
                        conn, params=ky_list,
                    )
                if df_trend.empty:
                    st.info("ℹ️ Chưa có dữ liệu xu hướng.")
                else:
                    import plotly.graph_objects as go
                    fig = go.Figure()
                    qh_trieu = (df_trend["qh"] / 1e6).round(0)
                    kh_trieu = (df_trend["khoanh"] / 1e6).round(0)

                    fig.add_trace(go.Scatter(
                        x=df_trend["ky"], y=qh_trieu,
                        mode='lines+markers', name='Nợ quá hạn',
                        line=dict(color='#ef4444', width=2),
                        hovertemplate='<b>%{x}</b><br>NQH: %{y:,.0f} triệu<extra></extra>',
                    ))
                    fig.add_trace(go.Scatter(
                        x=df_trend["ky"], y=kh_trieu,
                        mode='lines+markers', name='Nợ khoanh',
                        line=dict(color='#f59e0b', width=2),
                        hovertemplate='<b>%{x}</b><br>Khoanh: %{y:,.0f} triệu<extra></extra>',
                    ))

                    # Add % change annotations
                    if len(df_trend) >= 2:
                        pct_qh = ((df_trend["qh"].iloc[-1] - df_trend["qh"].iloc[0]) /
                                  df_trend["qh"].iloc[0] * 100) if df_trend["qh"].iloc[0] > 0 else 0
                        pct_kh = ((df_trend["khoanh"].iloc[-1] - df_trend["khoanh"].iloc[0]) /
                                  df_trend["khoanh"].iloc[0] * 100) if df_trend["khoanh"].iloc[0] > 0 else 0
                        _mau_qh = "#ef4444" if pct_qh > 0 else "#22c55e"
                        _mau_kh = "#ef4444" if pct_kh > 0 else "#22c55e"
                        st.caption(
                            f"NQH: **{pct_qh:+.1f}%** · "
                            f"Khoanh: **{pct_kh:+.1f}%** "
                            f"({ky_list[-1]} vs {ky_list[0]})"
                        )

                    fig.update_layout(
                        height=350, margin=dict(t=10, b=30, l=40, r=20),
                        hovermode='x unified',
                        legend=dict(orientation='h', yanchor='bottom', y=1.02),
                    )
                    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}trend_nqh")
        except Exception as _e:
            logger.error("_render_tong_hop trend NQH 12 kỳ: %s", _e, exc_info=True)
            st.caption(f"⚠️ Chưa thể hiển thị xu hướng: {_e}")

    cxl, cpdf, cbc = st.columns(3)
    with cxl:
        if st.button(f"Xuất Excel tổng hợp", key=f"{key_prefix}th_xuat"):
            st.session_state[f"_{key_prefix}th_buf"] = xuat_excel({"TongHopCanhBao": df_th})
        if st.session_state.get(f"_{key_prefix}th_buf"):
            st.download_button(
                "Tải về", data=st.session_state[f"_{key_prefix}th_buf"],
                file_name=f"TongHopCanhBao_{today.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}th_dl",
            )
    with cpdf:
        nut_xuat_pdf(df_th, "Tổng hợp Cảnh báo Tín dụng",
                     st.session_state.get("username", "unknown"),
                     prefix_file="TongHopCanhBao", key=f"{key_prefix}th_pdf")
    with cbc:
        if st.button("📥 Xuất Báo cáo Cảnh báo", key=f"{key_prefix}th_full_export",
                     help="Xuất báo cáo tổng hợp 5 sheets: KPI, NQH, Khoanh, Đến hạn, KHĐ"):
            try:
                # Sheet 1: KPI from df_th
                # Sheet 2: NQH list
                nqh_mask = pd.to_numeric(df_full_loc[COT_DU_NO_QH], errors="coerce").fillna(0) > 0 if COT_DU_NO_QH in df_full_loc.columns else pd.Series(False, index=df_full_loc.index)
                df_nqh_sheet = df_full_loc[nqh_mask][[c for c in [COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_DU_NO_QH, COT_TONG_DU_NO] if c in df_full_loc.columns]].copy() if nqh_mask.any() else pd.DataFrame({"Ghi chú": ["Không có NQH"]})

                # Sheet 3: Khoanh sắp hết hạn
                if _COT_KHOANH in df_full_loc.columns and COT_NGAY_HH_KHOANH in df_full_loc.columns:
                    kh_mask = pd.to_numeric(df_full_loc[_COT_KHOANH], errors="coerce").fillna(0) > 0
                    df_kh_sheet = df_full_loc[kh_mask][[c for c in [COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, _COT_KHOANH, COT_NGAY_HH_KHOANH] if c in df_full_loc.columns]].copy()
                else:
                    df_kh_sheet = pd.DataFrame({"Ghi chú": ["Không có dữ liệu khoanh"]})

                # Sheet 4: Đến hạn 3 tháng
                dh_mask = pd.Series(False, index=df_full_loc.index)
                if COT_NGAY_DH in df_full_loc.columns:
                    ngay_dh = pd.to_datetime(df_full_loc[COT_NGAY_DH], errors="coerce", dayfirst=True)
                    end_date = pd.Timestamp(today) + pd.DateOffset(months=3)
                    dh_mask = (ngay_dh >= pd.Timestamp(today)) & (ngay_dh <= end_date)
                df_dh_sheet = df_full_loc[dh_mask][[c for c in [COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_NGAY_DH, COT_TONG_DU_NO] if c in df_full_loc.columns]].copy() if dh_mask.any() else pd.DataFrame({"Ghi chú": ["Không có khoản đến hạn"]})

                # Sheet 5: KHĐ >3 tháng
                if "is_3m_inactive" in df_kh_loc.columns:
                    khd_list = df_kh_loc[df_kh_loc["is_3m_inactive"].fillna(False).astype(bool)][[c for c in [COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_TONG_DU_NO] if c in df_kh_loc.columns]].copy()
                else:
                    khd_list = pd.DataFrame({"Ghi chú": ["Không có dữ liệu KHĐ"]})

                sheets = {
                    "1-KPI_Dashboard": df_th,
                    "2-NQH_PhatSinh": df_nqh_sheet if isinstance(df_nqh_sheet, pd.DataFrame) else pd.DataFrame(),
                    "3-Khoanh_SapHetHan": df_kh_sheet if isinstance(df_kh_sheet, pd.DataFrame) else pd.DataFrame(),
                    "4-DenHan_3Thang": df_dh_sheet if isinstance(df_dh_sheet, pd.DataFrame) else pd.DataFrame(),
                    "5-KHD_3Thang": khd_list if isinstance(khd_list, pd.DataFrame) else pd.DataFrame(),
                }
                st.session_state[f"_{key_prefix}full_bc_buf"] = xuat_excel(sheets)
                db.ghi_audit(username, "xuat_bc_canh_bao",
                             f"Kỳ {today.strftime('%Y%m')} — {len(df_th)} PGD")
                st.success("✅ Đã tạo báo cáo tổng hợp!")
            except Exception as _e:
                logger.error("_render_tong_hop xuat bao cao canh bao: %s", _e, exc_info=True)
                st.error(f"❌ Lỗi tạo báo cáo: {_e}")
        if st.session_state.get(f"_{key_prefix}full_bc_buf"):
            st.download_button(
                "⬇️ Tải Báo cáo Cảnh báo",
                data=st.session_state[f"_{key_prefix}full_bc_buf"],
                file_name=f"BaoCaoCanhBao_{today.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}th_full_dl",
            )


# ─── Sub-tab 3: 3 tháng KHĐ ───────────────────────────────────────────────────

def _render_khd(
    df_kh: pd.DataFrame, ds_pgd_all: list, la_cn: bool, key_prefix: str
) -> None:
    df_kh_loc, _, _, _ = _ap_dung_loc_pgd_xa_to_truong(df_kh, ds_pgd_all, la_cn, key_prefix)
    khd_tong = int(df_kh_loc["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh_loc.columns else 0
    tong_mon = len(df_kh_loc)
    tl_khd = khd_tong / tong_mon * 100 if tong_mon > 0 else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Tổng món vay", fmt_so(tong_mon))
    k2.metric("3 tháng không HĐ", fmt_so(khd_tong),
              delta=f"{tl_khd:.1f}%", delta_color="inverse" if tl_khd > 2 else "off")
    if COT_LAI_TON in df_kh_loc.columns and "is_3m_inactive" in df_kh_loc.columns:
        _mask_khd = df_kh_loc["is_3m_inactive"].fillna(False).astype(bool)
        tong_lai = pd.to_numeric(df_kh_loc.loc[_mask_khd, COT_LAI_TON], errors="coerce").sum()
    else:
        tong_lai = 0
    k3.metric("Lãi tồn (đồng)", fmt(tong_lai))

    st.markdown("**Tổng hợp theo PGD**")
    nhom_pgd = tong_hop_khong_hd_cached(df_kh_loc, nhom_theo=COT_TEN_PGD)
    if not nhom_pgd.empty:
        hien_thi_dataframe_phan_trang(nhom_pgd, key=f"{key_prefix}khd_pgd", height=280)

    st.markdown("**Tổng hợp theo Hội đoàn thể**")
    nhom_dvut = tong_hop_khong_hd_cached(df_kh_loc, nhom_theo=COT_DVUT)
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(nhom_dvut, key=f"{key_prefix}khd_dvut", height=220)

    ds_chi = ds_chi_tiet_khong_hd(df_kh_loc)
    if not ds_chi.empty:
        df_chi_loc = ds_chi
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"Tạo Excel ({len(df_chi_loc)} món)", key=f"{key_prefix}khd_xuat_btn"):
            st.session_state[f"_{key_prefix}khd_buf"] = xuat_excel({"3mKHD": df_chi_loc})
        if st.session_state.get(f"_{key_prefix}khd_buf"):
            st.download_button(
                "Tải về Excel", data=st.session_state[f"_{key_prefix}khd_buf"],
                file_name=f"3mKHD_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}khd_xuat",
            )
        nut_xuat_pdf(df_chi_loc, "3 tháng không hoạt động",
                     st.session_state.get("username", "unknown"),
                     cols_tien=[COT_TONG_DU_NO, COT_LAI_TON] if COT_TONG_DU_NO in df_chi_loc.columns else None,
                     prefix_file="3mKHD", key=f"{key_prefix}khd_pdf")
        hien_thi_dataframe_phan_trang(df_chi_loc, key=f"{key_prefix}khd_chi", height=320)


# ─── Sub-tab 4: BT sang Rủi ro ─────────────────────────────────────────────────

def _render_migration(
    df_kh: pd.DataFrame, ds_pgd_all: list, la_cn: bool, key_prefix: str
) -> None:
    df_amber = canh_bao_migration_cached(df_kh)
    amber_tong = len(df_amber)

    if amber_tong == 0:
        st.success("Không có món vay nào có dấu hiệu rủi ro chuyển nợ quá hạn.")
        return

    if "so_thang_ton_uoc" in df_amber.columns:
        _so_thang = pd.to_numeric(df_amber["so_thang_ton_uoc"], errors="coerce")
        _mask_13 = (_so_thang >= 1) & (_so_thang < 3)
        _df_13 = df_amber[_mask_13]
        _tong_dn_13 = _df_13[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in _df_13.columns else 0
    else:
        _tong_dn_13 = 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Số món cần theo dõi", fmt_so(amber_tong))
    tong_lai = df_amber[COT_LAI_TON].sum() if COT_LAI_TON in df_amber.columns else 0
    k2.metric("Tổng lãi tồn (triệu đồng)", vn(tong_lai / 1e6, 0))
    k3.metric("Tổng dư nợ (1-<3 tháng rủi ro)", fmt_ty(_tong_dn_13))

    df_loc, _, _, _ = _ap_dung_loc_pgd_xa_to_truong(df_amber, ds_pgd_all, la_cn, key_prefix)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(f"Tạo Excel ({len(df_loc)} món)", key=f"{key_prefix}mg_xuat_btn"):
        st.session_state[f"_{key_prefix}mg_buf"] = xuat_excel({"Migration": df_loc})
    if st.session_state.get(f"_{key_prefix}mg_buf"):
        st.download_button(
            "Tải về Excel", data=st.session_state[f"_{key_prefix}mg_buf"],
            file_name=f"Migration_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}mg_xuat",
        )
    nut_xuat_pdf(df_loc, "BT sang Rủi ro",
                 st.session_state.get("username", "unknown"),
                 cols_tien=[COT_TONG_DU_NO, COT_LAI_TON] if COT_TONG_DU_NO in df_loc.columns else None,
                 prefix_file="Migration", key=f"{key_prefix}mg_pdf")
    cols_hien = [c for c in [
        COT_TEN_PGD, "Tên xã", COT_DVUT, COT_TEN_KH, COT_SO_KU,
        COT_TEN_CT, COT_LAI_TON, COT_LAI_THANG, "so_thang_ton_uoc", "muc_canh_bao",
    ] if c in df_loc.columns]
    hien_thi_dataframe_phan_trang(df_loc[cols_hien], key=f"{key_prefix}mg_chi", height=360)


# ─── Sub-tab 5: Nợ quá hạn phát sinh ───────────────────────────────────────────

def _render_nqh(df_kh: pd.DataFrame, ds_pgd_all: list, la_cn: bool, key_prefix: str) -> None:
    cot_nqh = _tim_cot(df_kh, COT_DU_NO_QH)
    cot_tong_dn = _tim_cot(df_kh, COT_TONG_DU_NO)

    # ─── Mốc thời gian tham chiếu: ưu tiên COT_NGAY_SL, fallback datetime.now() ──
    ref_date = lay_ngay_so_lieu(df_kh) or datetime.now()

    if cot_nqh and cot_nqh in df_kh.columns:
        mask_nqh = pd.to_numeric(df_kh[cot_nqh], errors="coerce").fillna(0) > 0
        df_nqh_all = df_kh[mask_nqh].copy()
    else:
        st.warning("Không tìm thấy cột dư nợ quá hạn trong dữ liệu.")
        return

    if df_nqh_all.empty:
        st.success("Không có nợ quá hạn phát sinh.")
        return

    # Tính tổng dư nợ gốc (trước khi lọc) để tính tỷ lệ NQH chính xác
    tong_du_no_goc = df_kh[cot_tong_dn].sum() if cot_tong_dn and cot_tong_dn in df_kh.columns else 0

    # ─── Filter 1: Thời gian (Chuyển QH trong tháng / trong năm / Tất cả) ─────────
    cot_chuyen_qh_thang = _tim_cot(df_nqh_all, COT_CHUYEN_QH_TRONG_THANG)
    cot_cqh_nam = _tim_cot(df_nqh_all, COT_CQH_NAM)
    cot_ngay_dh = _tim_cot(df_nqh_all, COT_NGAY_DH)

    col_time, col_pgd = st.columns(2)

    with col_time:
        loc_thoi_gian = st.selectbox(
            "Lọc theo thời gian",
            options=["Chuyển nợ quá hạn trong tháng", "Chuyển nợ quá hạn trong năm", "Tất cả nợ quá hạn"],
            index=2,
            key=f"{key_prefix}nqh_thoigian"
        )

    if loc_thoi_gian == "Chuyển nợ quá hạn trong tháng":
        if cot_chuyen_qh_thang and cot_chuyen_qh_thang in df_nqh_all.columns:
            # Cách 1: Dùng cột Chuyển QH trong tháng
            mask = pd.to_numeric(df_nqh_all[cot_chuyen_qh_thang], errors="coerce").fillna(0) > 0
            df_nqh_all = df_nqh_all[mask]
        elif cot_ngay_dh and cot_ngay_dh in df_nqh_all.columns:
            # Cách 2 (fallback): Dùng Ngày ĐH theo Gia hạn + mốc từ Ngày số liệu
            ngay_dh = pd.to_datetime(df_nqh_all[cot_ngay_dh], errors="coerce")
            mask = (
                (ngay_dh.dt.year == ref_date.year)
                & (ngay_dh.dt.month == ref_date.month)
                & (ngay_dh.dt.day <= ref_date.day)
            )
            df_nqh_all = df_nqh_all[mask]
        else:
            st.warning("Không có cột 'Chuyển QH trong tháng' hoặc 'Ngày ĐH' để lọc.")
    elif loc_thoi_gian == "Chuyển nợ quá hạn trong năm":
        if cot_cqh_nam and cot_cqh_nam in df_nqh_all.columns:
            mask = pd.to_numeric(df_nqh_all[cot_cqh_nam], errors="coerce").fillna(0) > 0
            df_nqh_all = df_nqh_all[mask]
        elif cot_ngay_dh and cot_ngay_dh in df_nqh_all.columns:
            # Fallback: Dùng Ngày ĐH trong năm + mốc từ Ngày số liệu
            ngay_dh = pd.to_datetime(df_nqh_all[cot_ngay_dh], errors="coerce")
            mask = (ngay_dh.dt.year == ref_date.year) & (ngay_dh <= pd.Timestamp(ref_date))
            df_nqh_all = df_nqh_all[mask]
        else:
            st.warning("Không có cột 'CQH Năm' hoặc 'Ngày ĐH' để lọc.")
    # else: "Tất cả nợ quá hạn" → giữ nguyên df_nqh_all

    # ─── Filter 2: PGD ──────────────────────────────────────────────────────────
    state = SCMStateManager()
    with col_pgd:
        if la_cn:
            _key_pgd = f"{key_prefix}nqh_pgd"
            _desired_pgd = state.filter_pgd or "Tất cả"
            if _key_pgd not in st.session_state:
                st.session_state[_key_pgd] = _desired_pgd if _desired_pgd in (["Tất cả"] + ds_pgd_all) else "Tất cả"
            loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key=_key_pgd)
        else:
            loc_pgd = "Tất cả"
            st.caption("Lọc PGD (CN)")

    if loc_pgd != "Tất cả":
        state.filter_pgd = loc_pgd
        cot_pgd = _tim_cot(df_nqh_all, COT_TEN_PGD)
        if cot_pgd and cot_pgd in df_nqh_all.columns:
            df_nqh_all = df_nqh_all[df_nqh_all[cot_pgd] == loc_pgd]
    else:
        state.filter_pgd = None

    df_nqh_all, loc_xa, loc_to = _ap_dung_loc_xa_to_truong(df_nqh_all, key_prefix=f"{key_prefix}nqh_")

    # ─── Filter 3 & 4: Hội đoàn thể + Chương trình ─────────────────────────────
    col_dvut, col_ct = st.columns(2)

    cot_dvut_nqh = _tim_cot(df_nqh_all, COT_DVUT)
    with col_dvut:
        if cot_dvut_nqh and cot_dvut_nqh in df_nqh_all.columns:
            ds_dvut = sorted(df_nqh_all[cot_dvut_nqh].dropna().unique().tolist())
            loc_dvut = st.selectbox("Lọc theo Hội đoàn thể",
                                    options=["Tất cả"] + ds_dvut, key=f"{key_prefix}nqh_dvut")
        else:
            loc_dvut = "Tất cả"
            st.caption("Không có cột ĐVUT")

    if loc_dvut != "Tất cả":
        df_nqh_all = df_nqh_all[df_nqh_all[cot_dvut_nqh] == loc_dvut]

    # Filter 4: Lọc theo Chương trình
    cot_ct = _tim_cot(df_nqh_all, COT_TEN_CT)
    with col_ct:
        if cot_ct and cot_ct in df_nqh_all.columns:
            ds_ct = sorted(df_nqh_all[cot_ct].dropna().unique().tolist())
            _key_ct = f"{key_prefix}nqh_ct"
            _desired_ct = state.filter_chuong_trinh or "Tất cả"
            if _key_ct not in st.session_state:
                st.session_state[_key_ct] = _desired_ct if _desired_ct in (["Tất cả"] + ds_ct) else "Tất cả"
            loc_ct = st.selectbox("Lọc theo Chương trình",
                                  options=["Tất cả"] + ds_ct, key=_key_ct)
        else:
            loc_ct = "Tất cả"
            st.caption("Không có cột Chương trình")
    state.filter_chuong_trinh = None if loc_ct == "Tất cả" else loc_ct

    if loc_ct != "Tất cả":
        df_nqh_all = df_nqh_all[df_nqh_all[cot_ct] == loc_ct]

    # ─── Lọc cứng: Chỉ lấy món có Dư nợ quá hạn > 0 và Dư nợ khoanh = 0 ───────
    cot_khoanh = _tim_cot(df_nqh_all, COT_DU_NO_KHOANH)
    if cot_khoanh and cot_khoanh in df_nqh_all.columns:
        du_no_khoanh = pd.to_numeric(df_nqh_all[cot_khoanh], errors="coerce").fillna(0)
        df_nqh_all = df_nqh_all[du_no_khoanh == 0]

    df_nqh = df_nqh_all.copy()
    if df_nqh.empty:
        st.info("Không có hồ sơ nợ quá hạn trong phạm vi đã lọc.")
        return

    # ─── Metrics ────────────────────────────────────────────────────────────────
    tong_qh = df_nqh[cot_nqh].sum() if cot_nqh and cot_nqh in df_nqh.columns else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Số hồ sơ NQH", fmt_so(len(df_nqh)))
    k2.metric("Dư nợ QH", fmt_ty(tong_qh) if tong_qh else "0")
    # Tỷ lệ NQH tính trên tổng dư nợ gốc (trước khi lọc)
    ty_le_nqh = (tong_qh / tong_du_no_goc * 100) if tong_du_no_goc else 0
    k3.metric("Tỷ lệ NQH", f"{ty_le_nqh:.2f}%")

    # ─── Bảng chi tiết ──────────────────────────────────────────────────────────
    cols_ct = [c for c in [
        COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT, cot_nqh, cot_tong_dn,
        COT_NGAY_DH, COT_TEN_TO_TRUONG, COT_TEN_XA,
    ] if c and c in df_nqh.columns]
    df_ct = df_nqh[cols_ct].reset_index(drop=True)

    _dl_key = f"{key_prefix}nqh_excel"
    if st.button(f"Xuất Excel ({len(df_ct)} món)", key=f"{key_prefix}nqh_xuat_btn"):
        state.downloads.set(
            _dl_key,
            xuat_excel({"NQH": df_ct}),
            f"NQH_{datetime.now().strftime('%Y%m%d')}.xlsx",
        )
    if state.downloads.has(_dl_key):
        if st.download_button(
            "Tải về",
            data=state.downloads.get_bytes(_dl_key) or b"",
            file_name=state.downloads.get_filename(_dl_key) or f"NQH_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}nqh_xuat",
        ):
            state.downloads.clear(_dl_key)
    cpn, _ = st.columns([1, 1])
    with cpn:
        nut_xuat_pdf(df_ct, "Nợ quá hạn phát sinh",
                     st.session_state.get("username", "unknown"),
                     cols_tien=[COT_DU_NO_QH, COT_TONG_DU_NO] if COT_TONG_DU_NO in df_ct.columns else None,
                     prefix_file="NQH", key=f"{key_prefix}nqh_pdf")
    hien_thi_dataframe_phan_trang(df_ct, key=f"{key_prefix}nqh_chi", height=380)

# ─── Sub-tab 6: Khoanh sắp hết hạn ─────────────────────────────────────────────

def _render_khoanh_sap_hh(
    df_full: pd.DataFrame, ds_pgd_all: list, la_cn: bool, key_prefix: str
) -> None:
    if _COT_KHOANH not in df_full.columns:
        st.warning("Dữ liệu không có cột Dư nợ khoanh.")
        return

    du_kh = pd.to_numeric(df_full[_COT_KHOANH], errors="coerce").fillna(0)
    df_base = df_full[du_kh > 0].copy()

    if df_base.empty:
        st.success("Không có món khoanh nào.")
        return

    today = pd.Timestamp(lay_ngay_so_lieu(df_base) or datetime.now()).normalize()
    if COT_NGAY_HH_KHOANH in df_base.columns:
        df_base["_ngay_het"] = pd.to_datetime(
            df_base[COT_NGAY_HH_KHOANH], errors="coerce", dayfirst=True
        )
        df_base["_con_lai"] = (df_base["_ngay_het"] - today).dt.days
    else:
        df_base["_con_lai"] = pd.NA

    # ─── 4 Filters ───────────────────────────────────────────────────────────────
    col_tg, col_pgd = st.columns(2)
    with col_tg:
        loc_tg = st.selectbox(
            "Thời gian",
            ["Khẩn (≤ 30 ngày)", "Cảnh báo (≤ 180 ngày)", "Tất cả"],
            key=f"{key_prefix}kh_tg",
        )
    state = SCMStateManager()
    with col_pgd:
        if la_cn:
            _key_pgd = f"{key_prefix}kh_pgd"
            _desired_pgd = state.filter_pgd or "Tất cả"
            if _key_pgd not in st.session_state:
                st.session_state[_key_pgd] = _desired_pgd if _desired_pgd in (["Tất cả"] + ds_pgd_all) else "Tất cả"
            loc_pgd = st.selectbox(
                "Lọc PGD", ["Tất cả"] + ds_pgd_all, key=_key_pgd
            )
        else:
            loc_pgd = "Tất cả"
            st.caption("Lọc PGD (CN)")

    df_filt = df_base.copy()
    if loc_pgd != "Tất cả" and COT_TEN_PGD in df_filt.columns:
        df_filt = df_filt[df_filt[COT_TEN_PGD] == loc_pgd]
        state.filter_pgd = loc_pgd
    else:
        state.filter_pgd = None

    df_filt, loc_xa, loc_to = _ap_dung_loc_xa_to_truong(df_filt, key_prefix=f"{key_prefix}kh_")

    col_dvut, col_ct = st.columns(2)
    cot_dvut = _tim_cot(df_base, COT_DVUT)
    with col_dvut:
        if cot_dvut:
            ds_dvut = sorted(df_base[cot_dvut].dropna().unique().tolist())
            loc_dvut = st.selectbox(
                "Lọc Hội đoàn thể", ["Tất cả"] + ds_dvut, key=f"{key_prefix}kh_dvut"
            )
        else:
            loc_dvut = "Tất cả"
            st.caption("Không có cột ĐVUT")

    cot_ct = _tim_cot(df_base, COT_TEN_CT)
    with col_ct:
        if cot_ct:
            ds_ct = sorted(df_base[cot_ct].dropna().unique().tolist())
            _key_ct = f"{key_prefix}kh_ct"
            _desired_ct = state.filter_chuong_trinh or "Tất cả"
            if _key_ct not in st.session_state:
                st.session_state[_key_ct] = _desired_ct if _desired_ct in (["Tất cả"] + ds_ct) else "Tất cả"
            loc_ct = st.selectbox(
                "Lọc Chương trình", ["Tất cả"] + ds_ct, key=_key_ct
            )
        else:
            loc_ct = "Tất cả"
            st.caption("Không có cột Chương trình")
    state.filter_chuong_trinh = None if loc_ct == "Tất cả" else loc_ct

    if loc_dvut != "Tất cả" and cot_dvut and cot_dvut in df_filt.columns:
        df_filt = df_filt[df_filt[cot_dvut] == loc_dvut]
    if loc_ct != "Tất cả" and cot_ct and cot_ct in df_filt.columns:
        df_filt = df_filt[df_filt[cot_ct] == loc_ct]

    # ─── 4 Metrics (tính trên df_filt, không qua time filter) ───────────────────
    con_lai = df_filt["_con_lai"]
    so_khan = int((con_lai.notna() & (con_lai <= 30)).sum())
    so_cb = int((con_lai.notna() & (con_lai > 30) & (con_lai <= 180)).sum())
    tong_dn_kh = pd.to_numeric(df_filt[_COT_KHOANH], errors="coerce").sum()
    tong_sap_hh = pd.to_numeric(
        df_filt[con_lai.notna() & (con_lai <= 180)][_COT_KHOANH], errors="coerce"
    ).sum()
    ty_le = tong_sap_hh / tong_dn_kh * 100 if tong_dn_kh else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Khẩn (≤ 30 ngày)", fmt_so(so_khan),
              delta_color="inverse" if so_khan > 0 else "off")
    k2.metric("Cảnh báo (≤ 180 ngày)", fmt_so(so_cb),
              delta_color="inverse" if so_cb > 0 else "off")
    k3.metric("Dư nợ khoanh (triệu đ)", fmt_ty(tong_dn_kh))
    k4.metric("Tỷ lệ sắp hết hạn",
              f"{ty_le:.2f}".replace(".", ",") + "%")

    if df_filt.empty:
        st.info("Không có món khoanh nào trong phạm vi đã lọc.")
        return

    # ─── Apply time filter → table ───────────────────────────────────────────────
    if loc_tg == "Khẩn (≤ 30 ngày)":
        mask_tg = con_lai.notna() & (con_lai <= 30)
    elif loc_tg == "Cảnh báo (≤ 180 ngày)":
        mask_tg = con_lai.notna() & (con_lai <= 180)
    else:
        mask_tg = pd.Series(True, index=df_filt.index)

    df_loc = df_filt[mask_tg].copy()
    if df_loc.empty:
        st.info(f"Không có món khoanh nào trong phạm vi '{loc_tg}'.")
        return

    df_loc["Còn lại (ngày)"] = df_loc["_con_lai"].astype("Int64")
    cols_ct = [c for c in [
        COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
        COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH, "Còn lại (ngày)",
        COT_TEN_TO_TRUONG, COT_TEN_XA,
    ] if c and c in df_loc.columns]
    df_ct = df_loc[cols_ct].reset_index(drop=True)

    if st.button(f"Xuất Excel ({len(df_ct)} món)", key=f"{key_prefix}kh_xuat_btn"):
        st.session_state[f"_{key_prefix}kh_buf"] = xuat_excel(
            {"KhoanhSapHetHan": df_ct}
        )
    if st.session_state.get(f"_{key_prefix}kh_buf"):
        st.download_button(
            "Tải về", data=st.session_state[f"_{key_prefix}kh_buf"],
            file_name=f"KhoanhSapHetHan_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}kh_dl",
        )
    nut_xuat_pdf(df_ct, "Khoanh sắp hết hạn",
                 st.session_state.get("username", "unknown"),
                 prefix_file="KhoanhSapHetHan", key=f"{key_prefix}kh_pdf")
    hien_thi_dataframe_phan_trang(df_ct, key=f"{key_prefix}kh_tbl", height=380)


# ─── Sub-tab 7: Gia hạn nợ ─────────────────────────────────────────────────────

def _render_gia_han(
    df_full: pd.DataFrame, ds_pgd_all: list, ds_dvut_all: list, la_cn: bool, key_prefix: str
) -> None:
    if COT_NGAY_DH_HD not in df_full.columns or COT_NGAY_DH not in df_full.columns:
        st.warning("Dữ liệu không có đủ cột Ngày ĐH theo hợp đồng và Ngày ĐH theo Gia hạn. "
                   "Không thể phát hiện món đã gia hạn.")
        return

    today = lay_ngay_so_lieu(df_full) or datetime.now()
    ngay_hd = pd.to_datetime(df_full[COT_NGAY_DH_HD], errors="coerce", dayfirst=True)
    ngay_gh = pd.to_datetime(df_full[COT_NGAY_DH], errors="coerce", dayfirst=True)
    da_gh = (ngay_gh > ngay_hd) & ngay_hd.notna() & ngay_gh.notna()

    df_gh = df_full[da_gh].copy()
    df_gh["_so_thang_da_gh"] = ((ngay_gh[da_gh] - ngay_hd[da_gh]).dt.days / 30).round(1)

    if df_gh.empty:
        st.success("Không có món vay nào được gia hạn nợ.")
        return

    gh_thang_series = ngay_gh[da_gh]
    mask_thang = (gh_thang_series.dt.year == today.year) & (gh_thang_series.dt.month == today.month)
    mask_nam = (gh_thang_series.dt.year == today.year) & (gh_thang_series.dt.month > today.month)

    so_gh_thang = int(mask_thang.sum())
    so_gh_nam = int(mask_nam.sum())
    so_lan_bq = round(df_gh[COT_SO_LAN_GH].mean(), 1) if COT_SO_LAN_GH in df_gh.columns else None
    ngay_gh_gn = None
    if COT_NGAY_GH_GN in df_gh.columns:
        gn_dates = pd.to_datetime(df_gh[COT_NGAY_GH_GN], errors="coerce", dayfirst=True)
        if gn_dates.notna().any():
            ngay_gh_gn = gn_dates.max()

    tong_dn = df_gh[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_gh.columns else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Gia hạn trong tháng", fmt_so(so_gh_thang))
    k2.metric("Gia hạn trong năm", fmt_so(so_gh_nam))
    k3.metric("Số lần GH bình quân", f"{so_lan_bq}" if so_lan_bq is not None else "—")
    k4.metric("Ngày gia hạn gần nhất",
              pd.Timestamp(ngay_gh_gn).strftime("%d/%m/%Y") if ngay_gh_gn is not pd.NaT and ngay_gh_gn is not None else "—")
    k5.metric("Tổng dư nợ", fmt_ty(tong_dn))

    scope = st.radio(
        "Phạm vi",
        ["Trong tháng", "Trong năm", "Toàn thời gian"],
        horizontal=True, key=f"{key_prefix}gh_scope",
    )
    if scope == "Trong tháng":
        df_loc = df_gh[mask_thang].copy() if so_gh_thang > 0 else pd.DataFrame()
    elif scope == "Trong năm":
        df_loc = df_gh[mask_nam].copy() if so_gh_nam > 0 else pd.DataFrame()
    else:
        df_loc = df_gh.copy()

    if df_loc.empty:
        st.info(f"Không có món gia hạn nào trong phạm vi '{scope}'.")
        return

    if la_cn:
        state = SCMStateManager()
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            _key_pgd = f"{key_prefix}gh_pgd"
            _desired_pgd = state.filter_pgd or "Tất cả"
            if _key_pgd not in st.session_state:
                st.session_state[_key_pgd] = _desired_pgd if _desired_pgd in (["Tất cả"] + ds_pgd_all) else "Tất cả"
            loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key=_key_pgd)
        with col_f2:
            loc_dvut = st.selectbox("Lọc Hội đoàn thể", ["Tất cả"] + ds_dvut_all,
                                    key=f"{key_prefix}gh_dvut")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f2:
            loc_dvut = st.selectbox("Lọc Hội đoàn thể", ["Tất cả"] + ds_dvut_all,
                                    key=f"{key_prefix}gh_dvut")
        loc_pgd = "Tất cả"

    if loc_pgd != "Tất cả" and COT_TEN_PGD in df_loc.columns:
        df_loc = df_loc[df_loc[COT_TEN_PGD] == loc_pgd]
        state.filter_pgd = loc_pgd
    else:
        if la_cn:
            state.filter_pgd = None

    df_loc, loc_xa, loc_to = _ap_dung_loc_xa_to_truong(df_loc, key_prefix=f"{key_prefix}gh_")

    if loc_dvut != "Tất cả" and COT_DVUT in df_loc.columns:
        df_loc = df_loc[df_loc[COT_DVUT] == loc_dvut]

    if df_loc.empty:
        st.info("Không có dữ liệu trong phạm vi đã lọc.")
        return

    if la_cn and COT_TEN_PGD in df_loc.columns:
        st.markdown("**Tổng hợp theo PGD**")
        agg_pgd = {
            "Số món GH": (COT_TEN_PGD, "count"),
            "_du_no_sum": (COT_TONG_DU_NO, "sum") if COT_TONG_DU_NO in df_loc.columns else None,
            "GH bình quân (tháng)": ("_so_thang_da_gh", "mean"),
            "GH nhiều nhất (tháng)": ("_so_thang_da_gh", "max"),
        }
        agg_pgd = {k: v for k, v in agg_pgd.items() if v is not None}
        if COT_SO_LAN_GH in df_loc.columns:
            agg_pgd["SL GH bình quân"] = (COT_SO_LAN_GH, "mean")
        nhom_pgd = df_loc.groupby(COT_TEN_PGD, dropna=False).agg(**agg_pgd).reset_index()
        for c in ["GH bình quân (tháng)", "GH nhiều nhất (tháng)", "SL GH bình quân"]:
            if c in nhom_pgd.columns:
                nhom_pgd[c] = nhom_pgd[c].round(1)
        hien_thi_dataframe_phan_trang(nhom_pgd, key=f"{key_prefix}gh_th_pgd", height=280)

    if COT_DVUT in df_loc.columns:
        st.markdown("**Tổng hợp theo Hội đoàn thể**")
        agg_dv = {
            "Số món GH": (COT_DVUT, "count"),
            "_du_no_sum": (COT_TONG_DU_NO, "sum") if COT_TONG_DU_NO in df_loc.columns else None,
        }
        agg_dv = {k: v for k, v in agg_dv.items() if v is not None}
        nhom_dv = df_loc.groupby(COT_DVUT, dropna=False).agg(**agg_dv).reset_index()
        hien_thi_dataframe_phan_trang(nhom_dv, key=f"{key_prefix}gh_th_dvut", height=220)

    st.markdown(f"**Chi tiết — {len(df_loc)} món**")
    cols_ct = [c for c in [
        COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
        COT_DVUT, COT_TEN_XA,
        COT_NGAY_DH_HD, COT_NGAY_DH,
        COT_SO_LAN_GH, COT_NGAY_GH_GN,
        "_so_thang_da_gh", COT_TONG_DU_NO,
    ] if c and c in df_loc.columns]
    df_hien = df_loc[cols_ct].copy()
    for c in [COT_NGAY_DH_HD, COT_NGAY_DH, COT_NGAY_GH_GN]:
        if c in df_hien.columns:
            df_hien[c] = pd.to_datetime(df_hien[c], errors="coerce").dt.strftime("%d/%m/%Y")
    if "_so_thang_da_gh" in df_hien.columns:
        df_hien = df_hien.rename(columns={"_so_thang_da_gh": "Số tháng đã GH"})
    hien_thi_dataframe_phan_trang(df_hien, key=f"{key_prefix}gh_chi", height=380)

    if st.button(f"Xuất Excel ({len(df_loc)} món)", key=f"{key_prefix}gh_xuat_btn"):
        st.session_state[f"_{key_prefix}gh_buf"] = xuat_excel({"GiaHanNo": df_hien})
    if st.session_state.get(f"_{key_prefix}gh_buf"):
        st.download_button(
            "Tải về", data=st.session_state[f"_{key_prefix}gh_buf"],
            file_name=f"GiaHanNo_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}gh_dl",
        )
    nut_xuat_pdf(df_hien, "Gia hạn nợ",
                 st.session_state.get("username", "unknown"),
                 cols_tien=[COT_TONG_DU_NO, "Số tháng đã GH"] if "Số tháng đã GH" in df_hien.columns else None,
                 prefix_file="GiaHanNo", key=f"{key_prefix}gh_pdf")


# ─── P3.1: Risk Heatmap toàn Chi nhánh ────────────────────────────────────────

def _render_risk_heatmap(
    df_full: pd.DataFrame, df_kh: pd.DataFrame, ds_pgd_all: list, key_prefix: str
) -> None:
    """Bảng ma trận PGD × Chỉ số rủi ro (NQH, khoanh, KHĐ, đến hạn)."""
    st.subheader("🗺️ Bản đồ rủi ro toàn Chi nhánh")
    st.caption("Ma trận PGD × Chỉ số rủi ro — màu đỏ = nguy hiểm, vàng = theo dõi, xanh = ổn định.")

    rows = []
    for pgd in ds_pgd_all:
        df_p = df_full[df_full[COT_TEN_PGD] == pgd] if COT_TEN_PGD in df_full.columns else pd.DataFrame()
        df_k = df_kh[df_kh[COT_TEN_PGD] == pgd] if COT_TEN_PGD in df_kh.columns else pd.DataFrame()

        # % NQH
        tong_dn = pd.to_numeric(df_p[COT_TONG_DU_NO], errors="coerce").sum() if COT_TONG_DU_NO in df_p.columns else 0
        nqh = pd.to_numeric(df_p[COT_DU_NO_QH], errors="coerce").sum() if COT_DU_NO_QH in df_p.columns else 0
        pct_nqh = nqh / tong_dn * 100 if tong_dn > 0 else 0

        # % Khoanh
        khoanh = pd.to_numeric(df_p[_COT_KHOANH], errors="coerce").sum() if _COT_KHOANH in df_p.columns else 0
        pct_khoanh = khoanh / tong_dn * 100 if tong_dn > 0 else 0

        # Số KHĐ (3 tháng không hoạt động)
        khd = int(df_k["is_3m_inactive"].sum()) if "is_3m_inactive" in df_k.columns else 0

        # Đến hạn 3 tháng
        ref_date = lay_ngay_so_lieu(df_p) or lay_ngay_so_lieu(df_full) or datetime.now()
        den_han = _dem_den_han(df_p, 3, ref_date)

        rows.append({
            "PGD": pgd, "% NQH": round(pct_nqh, 2), "% Khoanh": round(pct_khoanh, 2),
            "KHĐ": khd, "Đến hạn 3T": den_han,
        })

    df_hm = pd.DataFrame(rows)
    if df_hm.empty:
        st.info("ℹ️ Chưa có dữ liệu.")
        return

    # ── CSS cho heatmap ──
    def _heat_class(v, col):
        if col in ("% NQH", "% Khoanh"):
            if v >= 5: return "hm-red"
            if v >= 2: return "hm-yellow"
            return "hm-green"
        elif col == "KHĐ":
            if v >= 10: return "hm-red"
            if v >= 3: return "hm-yellow"
            return "hm-green"
        else:  # Đến hạn 3T
            if v >= 20: return "hm-red"
            if v >= 5: return "hm-yellow"
            return "hm-green"

    rows_html = []
    for _, r in df_hm.iterrows():
        cells = [f"<td class='hm-pgd'>{r['PGD']}</td>"]
        for col in ["% NQH", "% Khoanh", "KHĐ", "Đến hạn 3T"]:
            cls = _heat_class(r[col], col)
            val = f"{r[col]:.1f}" if isinstance(r[col], float) else str(r[col])
            cells.append(f"<td class='{cls}'>{val}</td>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    st.markdown("""
    <style>
    .hm-table{border-collapse:collapse;font-size:13px;width:100%}
    .hm-table th{text-align:center;padding:10px 8px;font-weight:600;font-size:11px;border-bottom:2px solid #e2e8f0}
    .hm-table th:first-child{text-align:left;padding-left:14px}
    .hm-table td{text-align:center;padding:10px 8px;border-bottom:1px solid #f1f5f9;font-weight:700}
    .hm-pgd{text-align:left !important;padding-left:14px;font-weight:600}
    .hm-red{background:#fee2e2;color:#b91c1c}.hm-yellow{background:#fef3c7;color:#b45309}.hm-green{background:#dcfce7;color:#15803d}
    .hm-table tr:hover td{filter:brightness(.95)}
    .hm-leg{display:flex;gap:14px;margin-bottom:10px;font-size:12px;flex-wrap:wrap}
    .hm-leg i{display:flex;align-items:center;gap:5px;font-style:normal}
    .hm-leg span{width:12px;height:12px;border-radius:3px;display:inline-block;flex-shrink:0}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="hm-leg">
        <i><span style="background:#ef4444"></span> Nguy hiểm</i>
        <i><span style="background:#f59e0b"></span> Theo dõi</i>
        <i><span style="background:#22c55e"></span> Ổn định</i>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <table class="hm-table">
    <thead><tr>
        <th>PGD</th>
        <th>% NQH<br><small>≥5% 🔴</small></th>
        <th>% Khoanh<br><small>≥5% 🔴</small></th>
        <th>KHĐ<br><small>≥10 🔴</small></th>
        <th>Đến hạn 3T<br><small>≥20 🔴</small></th>
    </tr></thead>
    <tbody>
    {''.join(rows_html)}
    </tbody>
    </table>
    """, unsafe_allow_html=True)

    # Export
    buf = xuat_excel({"RiskHeatmap": df_hm})
    st.download_button(
        "📥 Xuất Excel Bản đồ rủi ro",
        data=buf,
        file_name=f"RiskHeatmap_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{key_prefix}hm_xl",
    )


@st.cache_data(show_spinner=False, ttl=300)
def _doc_snapshot_nqh_delta() -> pd.DataFrame:
    """Lấy delta NQH giữa 2 kỳ gần nhất từ hstd_snapshot."""
    import sqlite3
    from db import get_conn
    with get_conn() as conn:
        ky_list = [r[0] for r in conn.execute(
            "SELECT DISTINCT ky FROM hstd_snapshot ORDER BY ky DESC LIMIT 2"
        ).fetchall()]
    if len(ky_list) < 2:
        return pd.DataFrame()
    ky_curr, ky_prev = ky_list[0], ky_list[1]
    with get_conn() as conn:
        df_c = pd.read_sql_query(
            "SELECT ten_pgd, SUM(du_no_qh) qh_curr, SUM(tong_du_no) dn_curr "
            "FROM hstd_snapshot WHERE ky=? AND ma_ct='ALL' AND nguon_von='ALL' "
            "AND ten_pgd!='__CN__' GROUP BY ten_pgd",
            conn, params=(ky_curr,),
        )
        df_p = pd.read_sql_query(
            "SELECT ten_pgd, SUM(du_no_qh) qh_prev, SUM(tong_du_no) dn_prev "
            "FROM hstd_snapshot WHERE ky=? AND ma_ct='ALL' AND nguon_von='ALL' "
            "AND ten_pgd!='__CN__' GROUP BY ten_pgd",
            conn, params=(ky_prev,),
        )
    df = df_c.merge(df_p, on="ten_pgd", how="left").fillna(0)
    df["delta_qh"] = df["qh_curr"] - df["qh_prev"]
    df["pct_qh"] = df.apply(
        lambda r: r["delta_qh"] / r["qh_prev"] * 100 if r["qh_prev"] != 0 else float("nan"), axis=1
    )
    df.attrs["ky_curr"] = ky_curr
    df.attrs["ky_prev"] = ky_prev
    return df


def _render_nqh_so_sanh_ky(key_prefix: str) -> None:
    """So sánh NQH giữa N kỳ gần nhất từ hstd_snapshot — hỗ trợ chọn 3/6/12 kỳ."""
    st.subheader("📈 NQH so sánh kỳ")

    import sqlite3
    from db import get_conn

    # ── Chọn số kỳ ──
    n_ky = st.radio(
        "Số kỳ so sánh",
        [3, 6, 12],
        horizontal=True,
        index=1,
        key=f"{key_prefix}nqh_nky",
    )

    with get_conn() as conn:
        ky_list = [r[0] for r in conn.execute(
            f"SELECT DISTINCT ky FROM hstd_snapshot ORDER BY ky DESC LIMIT {n_ky}"
        ).fetchall()]

    if len(ky_list) < 2:
        st.info(f"ℹ️ Chưa đủ 2 kỳ snapshot để so sánh (hiện có {len(ky_list)}). Hãy thực hiện merge HSTD ít nhất 2 kỳ liên tiếp.")
        return

    ky_list.reverse()
    ky_curr = ky_list[-1]
    ky_prev = ky_list[0]
    st.caption(f"So sánh **{len(ky_list)}** kỳ: {ky_prev} → {ky_curr}")

    # ── Truy vấn N kỳ ──
    with get_conn() as conn:
        placeholders = ','.join('?' * len(ky_list))
        df_all = pd.read_sql_query(
            f"SELECT ky, ten_pgd, SUM(du_no_qh) qh, SUM(tong_du_no) dn, SUM(du_no_khoanh) khoanh "
            f"FROM hstd_snapshot WHERE ma_ct='ALL' AND nguon_von='ALL' "
            f"AND ten_pgd!='__CN__' AND ky IN ({placeholders}) "
            f"GROUP BY ky, ten_pgd ORDER BY ky",
            conn, params=ky_list,
        )

    if df_all.empty:
        st.info("ℹ️ Chưa có dữ liệu snapshot.")
        return

    # ── Bảng so sánh kỳ cuối vs kỳ đầu (giữ nguyên hành vi cũ) ──
    df_curr = df_all[df_all["ky"] == ky_curr][["ten_pgd", "qh", "dn"]].rename(columns={"qh": "qh_curr", "dn": "dn_curr"})
    df_prev = df_all[df_all["ky"] == ky_prev][["ten_pgd", "qh"]].rename(columns={"qh": "qh_prev"})
    df_delta = df_curr.merge(df_prev, on="ten_pgd", how="left").fillna(0)
    df_delta["delta_qh"] = df_delta["qh_curr"] - df_delta["qh_prev"]
    df_delta["pct_qh"] = df_delta.apply(
        lambda r: r["delta_qh"] / r["qh_prev"] * 100 if r["qh_prev"] != 0 else float("nan"), axis=1
    )
    df_delta = df_delta.sort_values("delta_qh", ascending=False)

    tang = df_delta[df_delta["delta_qh"] > 0]
    giam = df_delta[df_delta["delta_qh"] < 0]
    khong_doi = df_delta[df_delta["delta_qh"] == 0]

    c1, c2, c3 = st.columns(3)
    c1.metric("PGD có NQH tăng", len(tang),
              delta_color="inverse" if len(tang) > 0 else "off")
    c2.metric("PGD có NQH giảm", len(giam),
              delta_color="normal" if len(giam) > 0 else "off")
    c3.metric("Không đổi / Mới", len(khong_doi))

    # ── Trend chart N kỳ ──
    try:
        import plotly.graph_objects as go

        df_trend = df_all.groupby("ky").agg(
            qh=("qh", "sum"), khoanh=("khoanh", "sum")
        ).reset_index().sort_values("ky")

        qh_trieu = (df_trend["qh"] / 1e6).round(0)
        kh_trieu = (df_trend["khoanh"] / 1e6).round(0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_trend["ky"], y=qh_trieu,
            mode='lines+markers+text',
            name='Nợ quá hạn',
            line=dict(color='#ef4444', width=2),
            text=[f"{v:,.0f}" for v in qh_trieu],
            textposition='top center',
            hovertemplate='<b>%{x}</b><br>NQH: %{y:,.0f} triệu<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=df_trend["ky"], y=kh_trieu,
            mode='lines+markers',
            name='Nợ khoanh',
            line=dict(color='#f59e0b', width=2, dash='dash'),
            hovertemplate='<b>%{x}</b><br>Khoanh: %{y:,.0f} triệu<extra></extra>',
        ))
        fig.update_layout(
            height=350, margin=dict(t=30, b=30, l=40, r=20),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}nqh_trend_nky")
    except Exception as _e:
        logger.error("_render_nqh_so_sanh_ky trend chart: %s", _e, exc_info=True)
        st.caption(f"⚠️ Chưa thể vẽ biểu đồ xu hướng: {_e}")

    st.divider()

    # ── Bảng chi tiết delta ──
    df_out = df_delta.copy()
    df_out[f"NQH kỳ {ky_prev} (triệu)"] = df_out["qh_prev"].apply(fmt_ty)
    df_out[f"NQH kỳ {ky_curr} (triệu)"] = df_out["qh_curr"].apply(fmt_ty)
    df_out["Tăng/Giảm (triệu)"] = df_out["delta_qh"].apply(fmt_ty)
    df_out["% thay đổi"] = df_out["pct_qh"].apply(
        lambda x: (f"+{x:.1f}" if x > 0 else f"{x:.1f}").replace(".", ",") + "%" if not pd.isna(x) else "—"
    )
    cols_show = ["ten_pgd", f"NQH kỳ {ky_prev} (triệu)", f"NQH kỳ {ky_curr} (triệu)", "Tăng/Giảm (triệu)", "% thay đổi"]
    df_final = df_out[cols_show].rename(columns={"ten_pgd": "PGD"})
    st.dataframe(df_final, use_container_width=True, height=500)

    if not tang.empty:
        st.warning(f"⚠️ **{len(tang)} PGD có NQH tăng** — cần theo dõi chặt: " +
                   ", ".join(tang["ten_pgd"].head(5).tolist()))

    buf = xuat_excel({"NQH_SoSanh": df_final})
    st.download_button(
        "⬇️ Xuất Excel so sánh NQH",
        data=buf,
        file_name=f"NQH_SoSanh_{ky_curr}_{ky_prev}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{key_prefix}nqh_delta_xl",
    )


# ─── Public render ────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role = normalize_role(str(kwargs.get("role", "user") or "user"))
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)   # tránh `or` trên DataFrame → ambiguous truth value
    ds_pgd_all = list(kwargs.get("ds_pgd_all", DS_PGD) or DS_PGD)

    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.subheader("Cảnh báo Tín dụng")
        st.caption("Tổng hợp tất cả cảnh báo: đến hạn, không hoạt động, "
                   "chuyển nợ quá hạn, nợ khoanh sắp hết hạn, gia hạn nợ.")

        if df_full is None or df_full.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return

        la_cn = la_phan_he_cn(role)
        if not la_cn and COT_TEN_PGD in df_full.columns:
            df_full = df_full[df_full[COT_TEN_PGD] == pgd_user]
            ds_pgd_all = sorted(df_full[COT_TEN_PGD].dropna().unique().tolist())

        df_kh = danh_dau_khong_hd_cached(df_full)

        if la_cn:
            key_prefix = "cn_cbtd_"
        else:
            from data.pgd import pgd_slug
            slug = pgd_slug(pgd_user) if pgd_user else "pgd"
            key_prefix = f"pgd_{slug}_cbtd_"

        ds_dvut_all = sorted(
            df_full[COT_DVUT].dropna().unique().tolist()
        ) if COT_DVUT in df_full.columns else []

        sub_labels = [
            "Tổng hợp",
            "3 tháng KHĐ",
            "BT sang Rủi ro",
            "Nợ quá hạn phát sinh",
            "📈 NQH so sánh kỳ",
            "Khoanh sắp hết hạn",
            "Gia hạn nợ",
            "🗺️ Bản đồ rủi ro",
        ]

        tab_chon = st.radio(
            "",
            sub_labels,
            horizontal=True,
            label_visibility="collapsed",
            key=f"{key_prefix}sub_tab",
        )

        if tab_chon == "Tổng hợp":
            _render_tong_hop(df_full, df_kh, ds_pgd_all, la_cn, key_prefix, role)
        elif tab_chon == "3 tháng KHĐ":
            _render_khd(df_kh, ds_pgd_all, la_cn, key_prefix)
        elif tab_chon == "BT sang Rủi ro":
            _render_migration(df_kh, ds_pgd_all, la_cn, key_prefix)
        elif tab_chon == "Nợ quá hạn phát sinh":
            _render_nqh(df_kh, ds_pgd_all, la_cn, key_prefix)
        elif tab_chon == "📈 NQH so sánh kỳ":
            _render_nqh_so_sanh_ky(key_prefix)
        elif tab_chon == "Khoanh sắp hết hạn":
            _render_khoanh_sap_hh(df_full, ds_pgd_all, la_cn, key_prefix)
        elif tab_chon == "Gia hạn nợ":
            _render_gia_han(df_full, ds_pgd_all, ds_dvut_all, la_cn, key_prefix)
        elif tab_chon == "🗺️ Bản đồ rủi ro":
            _render_risk_heatmap(df_full, df_kh, ds_pgd_all, key_prefix)
