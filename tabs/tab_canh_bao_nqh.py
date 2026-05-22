"""Tab Cảnh báo Tín dụng — 8 sub-tab gom tất cả cảnh báo.
Hoạt động ở cả phân hệ Chi nhánh (CN) lẫn PGD.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from alert_center import canh_bao_no_khoanh_sap_het_han
from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_QH,
    COT_DVUT,
    COT_LAI_THANG,
    COT_LAI_TON,
    COT_NGAY_DH,
    COT_NGAY_DH_HD,
    COT_NGAY_GH_GN,
    COT_NGAY_SL,
    COT_SO_KU,
    COT_SO_LAN_GH,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
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
from utils import (
    fmt,
    fmt_so,
    fmt_ty,
    hien_thi_dataframe_phan_trang,
    vn,
    xuat_excel,
)

_COT_KHOANH = "Dư nợ khoanh"


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


def _dem_den_han(df: pd.DataFrame, n_thang: int) -> int:
    if df.empty or COT_NGAY_DH not in df.columns:
        return 0
    today = pd.Timestamp.today()
    ngay_dh = pd.to_datetime(df[COT_NGAY_DH], errors="coerce", dayfirst=True)
    end_date = today + pd.DateOffset(months=n_thang)
    return int(((ngay_dh >= today) & (ngay_dh <= end_date)).sum())


# ─── Sub-tab 1: Tổng hợp ──────────────────────────────────────────────────────

def _render_tong_hop(
    df_full: pd.DataFrame, df_kh: pd.DataFrame, ds_pgd_all: list, la_cn: bool, key_prefix: str
) -> None:
    today = datetime.now()

    khoanh_data = canh_bao_no_khoanh_sap_het_han(
        df_full[df_full.get(_COT_KHOANH, pd.Series(0)).fillna(0) > 0]
        if _COT_KHOANH in df_full.columns
        else pd.DataFrame()
    )

    khd_tong = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    co_nqh = COT_DU_NO_QH in df_full.columns and (df_full[COT_DU_NO_QH].fillna(0) > 0).any()

    co_gia_han = COT_NGAY_DH_HD in df_full.columns and COT_NGAY_DH in df_full.columns
    if co_gia_han:
        ngay_hd = pd.to_datetime(df_full[COT_NGAY_DH_HD], errors="coerce", dayfirst=True)
        ngay_gh = pd.to_datetime(df_full[COT_NGAY_DH], errors="coerce", dayfirst=True)
        da_gh = ngay_gh > ngay_hd
        # dùng ngay_gh trực tiếp để tránh lệch index khi subset
        so_gh_thang = da_gh & (ngay_gh.dt.year == today.year) & (ngay_gh.dt.month == today.month)
        so_gh_nam   = da_gh & (ngay_gh.dt.year == today.year) & (ngay_gh.dt.month > today.month)

    cols_kpi = st.columns(5)
    with cols_kpi[0]:
        st.metric("Đến hạn (3 tháng)", _dem_den_han(df_full, 3))
    with cols_kpi[1]:
        st.metric("3 tháng không HĐ", fmt_so(khd_tong),
                  delta_color="inverse" if khd_tong > 0 else "off")
    with cols_kpi[2]:
        st.metric("Có nợ quá hạn", "Có" if co_nqh else "Không")
    with cols_kpi[3]:
        st.metric("Khoanh khẩn", fmt_so(khoanh_data.get("so_khan", 0)),
                  delta=f"{khoanh_data.get('so_canh_bao', 0)} cảnh báo",
                  delta_color="inverse")
    with cols_kpi[4]:
        st.metric("Đã gia hạn",
                  f"{so_gh_thang.sum()}/{so_gh_nam.sum()}" if co_gia_han else "—",
                  help="Tháng/Năm")

    st.divider()
    st.markdown("**Tổng hợp cảnh báo theo PGD**")

    rows_th = []
    for pgd in ds_pgd_all:
        df_pgd = df_full[df_full[COT_TEN_PGD] == pgd]
        df_kh_pgd = df_kh[df_kh[COT_TEN_PGD] == pgd]
        khd = int(df_kh_pgd["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh_pgd.columns else 0
        nqh = int((df_pgd[COT_DU_NO_QH].fillna(0) > 0).sum()) if COT_DU_NO_QH in df_pgd.columns else 0
        gh = int(so_gh_thang[df_full[COT_TEN_PGD] == pgd].sum()) if co_gia_han else 0
        rows_th.append({"PGD": pgd, "Đến hạn": _dem_den_han(df_pgd, 3),
                        "3 tháng KHĐ": khd, "Nợ QH": nqh, "GH tháng": gh,
                        "Tổng": _dem_den_han(df_pgd, 3) + khd + nqh + gh})

    df_th = pd.DataFrame(rows_th)
    if not df_th.empty:
        hien_thi_dataframe_phan_trang(df_th, key=f"{key_prefix}th_pgd", height=340)

    cxl, cpdf = st.columns(2)
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


# ─── Sub-tab 2: Đến hạn ───────────────────────────────────────────────────────

def _render_den_han_tab(role: str) -> None:
    from tabs.tab_den_han import render as render_den_han
    render_den_han(role=role)


# ─── Sub-tab 3: 3 tháng KHĐ ───────────────────────────────────────────────────

def _render_khd(
    df_kh: pd.DataFrame, ds_pgd_all: list, la_cn: bool, key_prefix: str
) -> None:
    khd_tong = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    tong_mon = len(df_kh)
    tl_khd = khd_tong / tong_mon * 100 if tong_mon > 0 else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Tổng món vay", fmt_so(tong_mon))
    k2.metric("3 tháng không HĐ", fmt_so(khd_tong),
              delta=f"{tl_khd:.1f}%", delta_color="inverse" if tl_khd > 2 else "off")
    if COT_LAI_TON in df_kh.columns and "is_3m_inactive" in df_kh.columns:
        _mask_khd = df_kh["is_3m_inactive"].fillna(False).astype(bool)
        tong_lai = pd.to_numeric(df_kh.loc[_mask_khd, COT_LAI_TON], errors="coerce").sum()
    else:
        tong_lai = 0
    k3.metric("Lãi tồn (đồng)", fmt(tong_lai))

    st.markdown("**Tổng hợp theo PGD**")
    nhom_pgd = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_PGD)
    if not nhom_pgd.empty:
        hien_thi_dataframe_phan_trang(nhom_pgd, key=f"{key_prefix}khd_pgd", height=280)

    st.markdown("**Tổng hợp theo Hội đoàn thể**")
    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_DVUT)
    if not nhom_dvut.empty:
        hien_thi_dataframe_phan_trang(nhom_dvut, key=f"{key_prefix}khd_dvut", height=220)

    ds_chi = ds_chi_tiet_khong_hd(df_kh)
    if not ds_chi.empty:
        if la_cn:
            col_loc, col_xuat = st.columns([2, 1])
            with col_loc:
                loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key=f"{key_prefix}khd_loc_pgd")
            df_chi_loc = ds_chi if loc_pgd == "Tất cả" else ds_chi[ds_chi[COT_TEN_PGD] == loc_pgd]
        else:
            col_xuat = st.container()
            df_chi_loc = ds_chi
        with col_xuat:
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

    if la_cn:
        col_loc, col_xuat = st.columns([2, 1])
        with col_loc:
            loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key=f"{key_prefix}mg_loc_pgd")
        df_loc = df_amber if loc_pgd == "Tất cả" else df_amber[df_amber[COT_TEN_PGD] == loc_pgd]
    else:
        col_xuat = st.container()
        df_loc = df_amber
    with col_xuat:
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
    cot_ngay_sl = _tim_cot(df_kh, COT_NGAY_SL)

    if cot_nqh and cot_nqh in df_kh.columns:
        mask_nqh = pd.to_numeric(df_kh[cot_nqh], errors="coerce").fillna(0) > 0
        df_nqh_all = df_kh[mask_nqh].copy()
    else:
        st.warning("Không tìm thấy cột dư nợ quá hạn trong dữ liệu.")
        return

    if df_nqh_all.empty:
        st.success("Không có nợ quá hạn phát sinh.")
        return

    col_thang, col_dvut = st.columns(2)
    if cot_ngay_sl and cot_ngay_sl in df_nqh_all.columns:
        _ngay = pd.to_datetime(df_nqh_all[cot_ngay_sl], errors="coerce")
        df_nqh_all["_thang_sl"] = _ngay.dt.to_period("M")
        ds_th = sorted(df_nqh_all["_thang_sl"].dropna().unique(), reverse=True)
        ds_th_lb = {p: f"Tháng {p.month:02d}/{p.year}" for p in ds_th}
        options = ["Tất cả"] + [ds_th_lb[p] for p in ds_th]
        with col_thang:
            chon = st.selectbox("Lọc theo tháng số liệu", options=options,
                                index=1 if len(options) > 1 else 0, key=f"{key_prefix}nqh_thang")
        if chon != "Tất cả":
            period = next((p for p, lb in ds_th_lb.items() if lb == chon), None)
            if period:
                df_nqh_all = df_nqh_all[df_nqh_all["_thang_sl"] == period]
    else:
        with col_thang:
            st.caption("Không có cột Ngày số liệu.")

    cot_dvut_nqh = _tim_cot(df_nqh_all, COT_DVUT)
    with col_dvut:
        if cot_dvut_nqh and cot_dvut_nqh in df_nqh_all.columns:
            ds_dvut = sorted(df_nqh_all[cot_dvut_nqh].dropna().unique().tolist())
            loc_dvut = st.selectbox("Lọc theo Hội đoàn thể",
                                    options=["Tất cả"] + ds_dvut, key=f"{key_prefix}nqh_dvut")
            if loc_dvut != "Tất cả":
                df_nqh_all = df_nqh_all[df_nqh_all[cot_dvut_nqh] == loc_dvut]

    if la_cn:
        col_pgd, _ = st.columns([2, 1])
        with col_pgd:
            loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key=f"{key_prefix}nqh_pgd")
        if loc_pgd != "Tất cả":
            cot_pgd = _tim_cot(df_nqh_all, COT_TEN_PGD)
            if cot_pgd and cot_pgd in df_nqh_all.columns:
                df_nqh_all = df_nqh_all[df_nqh_all[cot_pgd] == loc_pgd]

    df_nqh = df_nqh_all.drop(columns=["_thang_sl"], errors="ignore").copy()
    if df_nqh.empty:
        st.info("Không có hồ sơ nợ quá hạn trong phạm vi đã lọc.")
        return

    tong_qh = df_nqh[cot_nqh].sum() if cot_nqh and cot_nqh in df_nqh.columns else 0
    cot_tong_dn = _tim_cot(df_nqh, COT_TONG_DU_NO)
    tong_dn = df_nqh[cot_tong_dn].sum() if cot_tong_dn and cot_tong_dn in df_nqh.columns else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Số hồ sơ NQH", fmt_so(len(df_nqh)))
    k2.metric("Dư nợ QH", fmt_ty(tong_qh) if tong_qh else "0")
    k3.metric("Tỷ lệ NQH", f"{tong_qh / tong_dn * 100:.2f}%" if tong_dn else "0%")

    cols_ct = [c for c in [
        COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT, cot_nqh, cot_tong_dn,
        COT_NGAY_DH_HD, COT_NGAY_DH, COT_NGAY_SL,
    ] if c and c in df_nqh.columns]
    df_ct = df_nqh[cols_ct].reset_index(drop=True)

    if st.button(f"Xuất Excel ({len(df_ct)} món)", key=f"{key_prefix}nqh_xuat_btn"):
        st.session_state[f"_{key_prefix}nqh_buf"] = xuat_excel({"NQH": df_ct})
    if st.session_state.get(f"_{key_prefix}nqh_buf"):
        st.download_button(
            "Tải về", data=st.session_state[f"_{key_prefix}nqh_buf"],
            file_name=f"NQH_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}nqh_xuat",
        )
    cpn, _ = st.columns([1, 1])
    with cpn:
        nut_xuat_pdf(df_ct, "Nợ quá hạn phát sinh",
                     st.session_state.get("username", "unknown"),
                     cols_tien=[COT_DU_NO_QH, COT_TONG_DU_NO] if COT_TONG_DU_NO in df_ct.columns else None,
                     prefix_file="NQH", key=f"{key_prefix}nqh_pdf")
    hien_thi_dataframe_phan_trang(df_ct, key=f"{key_prefix}nqh_chi", height=380)


# ─── Sub-tab 6: Cảnh báo sớm ───────────────────────────────────────────────────

def _render_canh_bao_som_tab(df_kh: pd.DataFrame, ds_pgd_all: list, key_prefix: str, la_cn: bool) -> None:
    from tabs import tab_canh_bao_som
    tab_canh_bao_som._render_canh_bao(df_kh, ds_pgd_all, key_prefix=key_prefix, la_cn=la_cn)


# ─── Sub-tab 7: Khoanh sắp hết hạn ─────────────────────────────────────────────

def _render_khoanh_sap_hh(df_full: pd.DataFrame, key_prefix: str) -> None:
    if _COT_KHOANH not in df_full.columns:
        st.warning("Dữ liệu không có cột Dư nợ khoanh.")
        return

    du_kh = pd.to_numeric(df_full[_COT_KHOANH], errors="coerce").fillna(0)
    df_khoanh = df_full[du_kh > 0]
    data = canh_bao_no_khoanh_sap_het_han(df_khoanh)

    k1, k2 = st.columns(2)
    k1.metric("Khẩn (<= 30 ngày)", fmt_so(data["so_khan"]),
              delta_color="inverse" if data["so_khan"] > 0 else "off")
    k2.metric("Cảnh báo (<= 180 ngày)", fmt_so(data["so_canh_bao"]),
              delta_color="inverse" if data["so_canh_bao"] > 0 else "off")

    if data["so_khan"] == 0 and data["so_canh_bao"] == 0:
        st.success("Không có món khoanh nào sắp hết hạn.")
        return

    if data["so_khan"] > 0:
        st.markdown("**Danh sách khẩn — hết hạn trong 30 ngày**")
        df_khan = pd.DataFrame(data["chi_tiet_khan"])
        if not df_khan.empty:
            if "con_lai" in df_khan.columns:
                df_khan = df_khan.rename(columns={"con_lai": "Còn lại (ngày)"})
            hien_thi_dataframe_phan_trang(df_khan, key=f"{key_prefix}kh_khan", height=220)

    if data["so_canh_bao"] > 0:
        st.markdown("**Danh sách cảnh báo — hết hạn trong 180 ngày**")
        df_cb = pd.DataFrame(data["chi_tiet_canh_bao"])
        if not df_cb.empty:
            if "con_lai" in df_cb.columns:
                df_cb = df_cb.rename(columns={"con_lai": "Còn lại (ngày)"})
            hien_thi_dataframe_phan_trang(df_cb, key=f"{key_prefix}kh_cb", height=280)

    tong = data["so_khan"] + data["so_canh_bao"]
    if tong > 0:
        all_rows = data["chi_tiet_khan"] + data["chi_tiet_canh_bao"]
        for r in all_rows:
            if "con_lai" in r:
                r["Còn lại (ngày)"] = r.pop("con_lai")
        if st.button(f"Xuất Excel ({tong} món)", key=f"{key_prefix}kh_xuat_btn"):
            st.session_state[f"_{key_prefix}kh_buf"] = xuat_excel(
                {"KhoanhSapHetHan": pd.DataFrame(all_rows)}
            )
        if st.session_state.get(f"_{key_prefix}kh_buf"):
            st.download_button(
                "Tải về", data=st.session_state[f"_{key_prefix}kh_buf"],
                file_name=f"KhoanhSapHetHan_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}kh_dl",
            )
        nut_xuat_pdf(pd.DataFrame(all_rows), "Khoanh sắp hết hạn",
                     st.session_state.get("username", "unknown"),
                     prefix_file="KhoanhSapHetHan", key=f"{key_prefix}kh_pdf")


# ─── Sub-tab 8: Gia hạn nợ ─────────────────────────────────────────────────────

def _render_gia_han(
    df_full: pd.DataFrame, ds_pgd_all: list, ds_dvut_all: list, la_cn: bool, key_prefix: str
) -> None:
    if COT_NGAY_DH_HD not in df_full.columns or COT_NGAY_DH not in df_full.columns:
        st.warning("Dữ liệu không có đủ cột Ngày ĐH theo hợp đồng và Ngày ĐH theo Gia hạn. "
                   "Không thể phát hiện món đã gia hạn.")
        return

    today = datetime.now()
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
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            loc_pgd = st.selectbox("Lọc PGD", ["Tất cả"] + ds_pgd_all, key=f"{key_prefix}gh_pgd")
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


# ─── Public render ────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role = normalize_role(str(kwargs.get("role", "user") or "user"))
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)   # tránh `or` trên DataFrame → ambiguous truth value
    ds_pgd_all = list(kwargs.get("ds_pgd_all", DS_PGD) or DS_PGD)

    ctx = tab if tab is not None else st.container()
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
            "Đến hạn",
            "3 tháng KHĐ",
            "BT sang Rủi ro",
            "Nợ quá hạn phát sinh",
            "Cảnh báo sớm",
            "Khoanh sắp hết hạn",
            "Gia hạn nợ",
        ]

        tabs = st.tabs(sub_labels)

        with tabs[0]:
            _render_tong_hop(df_full, df_kh, ds_pgd_all, la_cn, key_prefix)

        with tabs[1]:
            _render_den_han_tab(role)

        with tabs[2]:
            _render_khd(df_kh, ds_pgd_all, la_cn, key_prefix)

        with tabs[3]:
            _render_migration(df_kh, ds_pgd_all, la_cn, key_prefix)

        with tabs[4]:
            _render_nqh(df_kh, ds_pgd_all, la_cn, key_prefix)

        with tabs[5]:
            _render_canh_bao_som_tab(df_kh, ds_pgd_all, key_prefix, la_cn)

        with tabs[6]:
            _render_khoanh_sap_hh(df_full, key_prefix)

        with tabs[7]:
            _render_gia_han(df_full, ds_pgd_all, ds_dvut_all, la_cn, key_prefix)