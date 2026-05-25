"""Tab Báo cáo."""
from __future__ import annotations

from datetime import datetime, date
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd

import db
from config import (
    COT_DIA_CHI,
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_LAI_SUAT,
    COT_LAI_TON,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGAY_VAY,
    COT_NGUON_VON,
    COT_SDT,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_THON,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_THOI_HAN,
    COT_TINH_TRANG,
    COT_TONG_DU_NO,
)
from utils import fmt_so, fmt_ty, vn, ten_file_xuat, hien_thi_dataframe_phan_trang, xuat_excel
from services import xuat_bao_cao, ten_file_bao_cao
from pdf_service import xuat_pdf_pivot, xuat_pdf_chi_tiet, xuat_pdf_theo_nhom
from data import (danh_dau_khong_hd_cached, tong_hop_khong_hd_cached, tong_hop_khong_hd, ds_chi_tiet_khong_hd)
from data.core import ts_file
from config import CACHE_HSTD
from auth import la_phan_he_pgd, la_phan_he_cn, la_executive
from state_manager import SCMStateManager
from logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


_COLS_TIEN = {
    COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_LAI_TON,
    "Tổng_dư_nợ", "Dư_nợ_trong_hạn", "Dư_nợ_quá_hạn",
    "Lãi_tồn_KHĐ", "Dư nợ TH", "Dư nợ QH", "Nợ khoanh", "Tổng dư nợ", "Lãi tồn",
    "Dư nợ khoanh", "Nợ_khoanh",
}
_COLS_PCT = {"Tỷ_lệ_QH_%", "Tỷ_lệ_KHĐ_%", "QH%", "TL Nợ xấu %"}


def _fmt_df(df: pd.DataFrame) -> pd.DataFrame:
    """Cột tiền → triệu đồng (VN format, 0 chữ số thập phân). Cột % → chuỗi VN."""
    d = df.copy()
    for col in d.columns:
        if col in _COLS_TIEN:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
        elif col in _COLS_PCT:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: f"{x:.2f}".replace(".", ",") + "%" if pd.notna(x) else "—"
            )
    return d


def _hien_thi_bc(df: pd.DataFrame, **kw) -> None:
    """Hiển thị bảng báo cáo kèm dòng đơn vị tính."""
    st.caption("ĐVT: triệu đồng")
    hien_thi_dataframe_phan_trang(df, **kw)


def _bc_fmt_metric(x: float) -> str:
    """Format số tiền cho metric display (triệu đồng, 0 dp)."""
    try:
        x = float(x)
        if abs(x) > 0:
            trieu = x / 1_000_000
            s = f"{trieu:,.0f}".replace(",","X").replace(".",",").replace("X",".")
            return s
        return "—"
    except Exception:
        logger.error("Lỗi format số: x=%s", x, exc_info=True)
        return "—"


from tabs.base_tab import TabContext


def render(tab: DeltaGenerator | None = None, **kwargs: dict) -> None:
    ctx = TabContext(tab, **kwargs)
    df = kwargs.get("df")
    df_full = ctx.df_full if ctx.df_full is not None and not ctx.df_full.empty else df
    role = ctx.role_norm
    pgd_user = ctx.pgd_user
    username = ctx.username
    df_nq11 = kwargs.get("df_nq11")
    state = SCMStateManager()

    with ctx:
        st.subheader("📈 Báo cáo")

        COL_CHUNG = [c for c in [
            COT_TEN_PGD,COT_TEN_XA,COT_TEN_THON,COT_DVUT,COT_TEN_TO,
            COT_MA_KH, COT_TEN_KH,COT_SDT,COT_DIA_CHI,
            COT_SO_KU, COT_NGAY_VAY, COT_NGAY_DH, COT_THOI_HAN,
            COT_LAI_SUAT, COT_DU_NO_TH, COT_DU_NO_QH,
            COT_TONG_DU_NO, COT_TEN_CT,COT_NGUON_VON,"Tên cấp QLV",
            COT_TINH_TRANG
        ] if c in df.columns]

        # ── Chọn mảng ──
        mang = st.radio("Loại báo cáo",
            ["📊 Tổng hợp theo PGD", "📋 Báo cáo chi tiết"],
            horizontal=True, key="bc_mang")

        st.divider()

        if mang == "📊 Tổng hợp theo PGD":
            col_f1, col_f2, col_f3 = st.columns(3)

            with col_f1:
                if la_phan_he_pgd(role) and pgd_user:
                    loc_pgd = pgd_user
                    st.markdown(f"📍 PGD: **{loc_pgd}**")
                    state.filter_pgd = pgd_user
                else:
                    ds_pgd = (
                        sorted(df[COT_TEN_PGD].dropna().unique())
                        if COT_TEN_PGD in df.columns
                        else []
                    )
                    _opts_pgd = ["Tất cả"] + ds_pgd
                    _desired_pgd = state.filter_pgd or "Tất cả"
                    if "bc_pc_pgd" not in st.session_state:
                        st.session_state["bc_pc_pgd"] = _desired_pgd if _desired_pgd in _opts_pgd else "Tất cả"
                    elif st.session_state.get("bc_pc_pgd") not in _opts_pgd:
                        st.session_state["bc_pc_pgd"] = "Tất cả"
                    loc_pgd = st.selectbox(
                        "📍 PGD",
                        _opts_pgd,
                        key="bc_pc_pgd",
                    )
                    _new_pgd = None if loc_pgd == "Tất cả" else loc_pgd
                    if _new_pgd != state.filter_pgd:
                        state.filter_pgd = _new_pgd
                        if "bc_pc_xa" in st.session_state:
                            st.session_state["bc_pc_xa"] = "Tất cả"

            with col_f2:
                if loc_pgd != "Tất cả":
                    ds_xa = (
                        sorted(df[df[COT_TEN_PGD] == loc_pgd][COT_TEN_XA].dropna().unique())
                        if COT_TEN_XA in df.columns and COT_TEN_PGD in df.columns
                        else []
                    )
                else:
                    ds_xa = (
                        sorted(df[COT_TEN_XA].dropna().unique())
                        if COT_TEN_XA in df.columns
                        else []
                    )
                _opts_xa = ["Tất cả"] + ds_xa
                _desired_xa = state.filter_xa or "Tất cả"
                if "bc_pc_xa" not in st.session_state:
                    st.session_state["bc_pc_xa"] = _desired_xa if _desired_xa in _opts_xa else "Tất cả"
                elif st.session_state.get("bc_pc_xa") not in _opts_xa:
                    st.session_state["bc_pc_xa"] = "Tất cả"
                loc_xa = st.selectbox("🏘️ Xã", _opts_xa, key="bc_pc_xa")
                state.filter_xa = None if loc_xa == "Tất cả" else loc_xa

            with col_f3:
                ds_ct = []
                if loc_pgd != "Tất cả":
                    from data.pgd import pgd_slug

                    ds_ct = db.doc_kv(f"ct_registry_{pgd_slug(loc_pgd)}") or []
                if not ds_ct:
                    ds_ct = (
                        sorted(df[COT_TEN_CT].dropna().unique())
                        if COT_TEN_CT in df.columns
                        else []
                    )
                _opts_ct = ["Tất cả"] + ds_ct
                _desired_ct = state.filter_chuong_trinh or "Tất cả"
                if "bc_pc_ct" not in st.session_state:
                    st.session_state["bc_pc_ct"] = _desired_ct if _desired_ct in _opts_ct else "Tất cả"
                elif st.session_state.get("bc_pc_ct") not in _opts_ct:
                    st.session_state["bc_pc_ct"] = "Tất cả"
                loc_ct = st.selectbox("📌 Chương trình", _opts_ct, key="bc_pc_ct")
                state.filter_chuong_trinh = None if loc_ct == "Tất cả" else loc_ct

            df_filtered = df.copy()
            if loc_pgd != "Tất cả" and COT_TEN_PGD in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[COT_TEN_PGD] == loc_pgd]
            if loc_xa != "Tất cả" and COT_TEN_XA in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[COT_TEN_XA] == loc_xa]
            if loc_ct != "Tất cả" and COT_TEN_CT in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[COT_TEN_CT] == loc_ct]

            df_base = df_filtered
            if COT_TONG_DU_NO in df_base.columns:
                df_base = df_base[df_base[COT_TONG_DU_NO] > 0]

            
            _required_cols = [
                COT_TEN_PGD,
                COT_TEN_XA,
                COT_TEN_CT,
                COT_MA_KH,
                COT_SO_KU,
                COT_DU_NO_TH,
                COT_DU_NO_QH,
                COT_TONG_DU_NO,
                COT_LAI_TON,
            ]
            _missing_cols = [c for c in _required_cols if c not in df_base.columns]
            df_pdf = pd.DataFrame()
            if not _missing_cols:
                df_pdf_src = df_base.copy()
                if COT_DU_NO_KHOANH not in df_pdf_src.columns:
                    df_pdf_src[COT_DU_NO_KHOANH] = 0

                _DN_SO_KH = "Số KH"
                _DN_SO_MON = "Số món"
                _DN_DU_NO_TH = "Dư nợ TH"
                _DN_DU_NO_QH = "Dư nợ QH"
                _DN_NO_KHOANH = "Nợ khoanh"
                _DN_TONG_DU_NO = "Tổng dư nợ"
                _DN_LAI_TON = "Lãi tồn"
                _DN_TL_NO_XAU = "TL Nợ xấu %"

                df_pdf = (
                    df_pdf_src.groupby([COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT])
                    .agg(
                        **{
                            _DN_SO_KH: (COT_MA_KH, "nunique"),
                            _DN_SO_MON: (COT_SO_KU, "nunique"),
                            _DN_DU_NO_TH: (COT_DU_NO_TH, "sum"),
                            _DN_DU_NO_QH: (COT_DU_NO_QH, "sum"),
                            _DN_NO_KHOANH: (COT_DU_NO_KHOANH, "sum"),
                            _DN_TONG_DU_NO: (COT_TONG_DU_NO, "sum"),
                            _DN_LAI_TON: (COT_LAI_TON, "sum"),
                        }
                    )
                    .reset_index()
                )

                df_pdf[_DN_TL_NO_XAU] = (
                    (df_pdf[_DN_DU_NO_QH] + df_pdf[_DN_NO_KHOANH])
                    / df_pdf[_DN_TONG_DU_NO].replace(0, float("nan"))
                    * 100
                ).round(2).fillna(0)


                COLS_PDF = [
                    COT_TEN_PGD,
                    COT_TEN_XA,
                    COT_TEN_CT,
                    _DN_SO_KH,
                    _DN_SO_MON,
                    _DN_DU_NO_TH,
                    _DN_DU_NO_QH,
                    _DN_NO_KHOANH,
                    _DN_TONG_DU_NO,
                    _DN_LAI_TON,
                    _DN_TL_NO_XAU,
                ]
                COLS_PDF = [c for c in COLS_PDF if c in df_pdf.columns]
                df_pdf = df_pdf[COLS_PDF].sort_values([COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT])

            if st.button("📄 Xuất PDF phân cấp", key="btn_pdf_bc_phancap", type="primary"):
                if _missing_cols:
                    st.warning(f"⚠️ Thiếu cột dữ liệu để xuất PDF: {', '.join(_missing_cols)}")
                elif df_pdf.empty:
                    st.warning("⚠️ Không có dữ liệu để xuất.")
                else:
                    try:
                        from pdf_service import xuat_pdf_group_header

                        _phu = []
                        if loc_pgd != "Tất cả":
                            _phu.append(f"PGD: {loc_pgd}")
                        if loc_xa != "Tất cả":
                            _phu.append(f"Xã: {loc_xa}")
                        if loc_ct != "Tất cả":
                            _phu.append(f"CT: {loc_ct}")
                        tieu_de_phu = "  |  ".join(_phu) if _phu else "Toàn Chi nhánh"

                        with st.spinner("⏳ Đang tạo PDF..."):
                            pdf_bytes = xuat_pdf_group_header(
                                df=df_pdf,
                                tieu_de="Báo cáo Tổng hợp Tín dụng — Phân cấp PGD > Xã > Chương trình",
                                nhom_theo=COT_TEN_PGD,
                                nguoi_xuat=username or "unknown",
                                cols_tien=[
                                    "Dư nợ TH",
                                    "Dư nợ QH",
                                    "Nợ khoanh",
                                    "Tổng dư nợ",
                                    "Lãi tồn",
                                ],
                                tieu_de_phu=tieu_de_phu,
                            )
                        state.downloads.set(
                            "bc_phancap_pdf",
                            pdf_bytes,
                            ten_file_xuat("BC_PhanCap_PGD_Xa_CT").replace(".xlsx", ".pdf"),
                        )
                        db.ghi_audit(
                            username or "unknown",
                            "xuat_pdf_bao_cao",
                            f"PDF phân cấp — {tieu_de_phu}",
                        )
                    except Exception as _e:
                        logger.error("Lỗi tạo PDF phân cấp: %s", _e, exc_info=True)
                        st.error(f"❌ Lỗi tạo PDF: {_e}")

            if state.downloads.has("bc_phancap_pdf"):
                if st.download_button(
                    "⬇ Tải PDF phân cấp",
                    data=state.downloads.get_bytes("bc_phancap_pdf"),
                    file_name=state.downloads.get_filename("bc_phancap_pdf") or "BC_PhanCap.pdf",
                    mime="application/pdf",
                    key="btn_pdf_bc_phancap_dl",
                ):
                    state.downloads.clear("bc_phancap_pdf")
        else:
            if (la_phan_he_cn(role) and not la_executive(role)) and COT_TEN_PGD in df.columns:
                _ds_pgd_bc = sorted(df[COT_TEN_PGD].dropna().unique().tolist())
                _opts_pgd_bc = ["Tất cả"] + _ds_pgd_bc
                _desired_pgd_bc = state.filter_pgd or "Tất cả"
                if "bc_pgd_chung" not in st.session_state:
                    st.session_state["bc_pgd_chung"] = _desired_pgd_bc if _desired_pgd_bc in _opts_pgd_bc else "Tất cả"
                elif st.session_state.get("bc_pgd_chung") not in _opts_pgd_bc:
                    st.session_state["bc_pgd_chung"] = "Tất cả"
                loc_pgd_bc = st.selectbox(
                    "📍 PGD",
                    _opts_pgd_bc,
                    key="bc_pgd_chung",
                )
                state.filter_pgd = None if loc_pgd_bc == "Tất cả" else loc_pgd_bc
            else:
                loc_pgd_bc = pgd_user or "Tất cả"
                st.markdown(f"📍 PGD: **{loc_pgd_bc}**")
                if pgd_user:
                    state.filter_pgd = pgd_user

            df_base = df.copy()
            if (la_phan_he_cn(role) and not la_executive(role)) and loc_pgd_bc != "Tất cả":
                df_base = df_base[df_base[COT_TEN_PGD] == loc_pgd_bc]
            elif la_phan_he_pgd(role) and pgd_user:
                df_base = df_base[df_base[COT_TEN_PGD] == loc_pgd_bc] if loc_pgd_bc != "Tất cả" else df_base
            if COT_TONG_DU_NO in df_base.columns:
                df_base = df_base[df_base[COT_TONG_DU_NO] > 0]

        # ══════════════════════════════
        # MẢNG 1: TỔNG HỢP
        # ══════════════════════════════
        if mang == "📊 Tổng hợp theo PGD":

            loai_th = st.radio("Tổng hợp theo",
                ["🏘️ Theo xã/thôn",
                 "🤝 Theo hội đoàn thể (ĐVUT)",
                 "📌 Theo chương trình vay"],
                horizontal=True, key="bc_loai_th")

            dbc_raw = None
            group_col = None

            # ── Xã / thôn ──
            if loai_th == "🏘️ Theo xã/thôn":
                cap_xa = st.radio("Cấp", ["Theo xã","Theo thôn/ấp"], horizontal=True, key="bc_cap_xa")
                nhom = COT_TEN_XA if cap_xa == "Theo xã" else COT_TEN_THON
                group_col = nhom
                if nhom in df_base.columns:
                    dbc_raw = df_base.groupby(nhom).agg(
                        Số_KH          =(COT_MA_KH,"nunique"),
                        Số_món_vay     =(COT_SO_KU,"nunique"),
                        Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                        Dư_nợ_trong_hạn=(COT_DU_NO_TH,"sum"),
                        Dư_nợ_quá_hạn  =(COT_DU_NO_QH,"sum"),
                    ).sort_values("Tổng_dư_nợ",ascending=False).reset_index()
                    dbc_raw["Tỷ_lệ_QH_%"] = (
                        dbc_raw["Dư_nợ_quá_hạn"]
                        / dbc_raw["Tổng_dư_nợ"].replace(0, float("nan"))
                        * 100
                    ).round(2).fillna(0)
                    st.info(f"**{fmt_so(len(dbc_raw))}** {nhom.lower()}")
                    _hien_thi_bc(
                        _fmt_df(dbc_raw),
                        key="baocao_th_xa_thon",
                    )

            # ── ĐVUT ──
            elif loai_th == "🤝 Theo hội đoàn thể (ĐVUT)":
                if COT_DVUT in df_base.columns:
                    group_col = COT_DVUT
                    # Đánh dấu 3 tháng không hoạt động
                    df_kh = danh_dau_khong_hd_cached(df_base, ts=ts_file(CACHE_HSTD))

                    dbc_raw = df_kh.groupby(COT_DVUT).agg(
                        Số_KH          =(COT_MA_KH,    "nunique"),
                        Số_món_vay     =(COT_SO_KU,    "nunique"),
                        Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                        Dư_nợ_trong_hạn=(COT_DU_NO_TH, "sum"),
                        Dư_nợ_quá_hạn  =(COT_DU_NO_QH, "sum"),
                    ).sort_values("Tổng_dư_nợ", ascending=False).reset_index()
                    dbc_raw["Tỷ_lệ_QH_%"] = (
                        dbc_raw["Dư_nợ_quá_hạn"]
                        / dbc_raw["Tổng_dư_nợ"].replace(0, float("nan"))
                        * 100
                    ).round(2).fillna(0)

                    # Tổng hợp 3 tháng không hoạt động theo ĐVUT
                    khd = tong_hop_khong_hd(df_kh, nhom_theo=COT_DVUT)
                    if not khd.empty:
                        dbc_raw = dbc_raw.merge(
                            khd[[COT_DVUT, "Món_3m_KHĐ",
                                 "Lãi_tồn_KHĐ", "Tỷ_lệ_KHĐ_%"]],
                            on=COT_DVUT, how="left"
                        ).fillna(0)
                        dbc_raw["Món_3m_KHĐ"] = dbc_raw["Món_3m_KHĐ"].astype(int)

                    st.info(f"**{fmt_so(len(dbc_raw))}** hội đoàn thể")
                    _hien_thi_bc(
                        _fmt_df(dbc_raw),
                        key="baocao_th_dvut",
                    )

                    # ── Xuất danh sách chi tiết để đôn đốc ───────────────
                    st.markdown("**📋 Danh sách hộ cần đôn đốc (3 tháng không hoạt động)**")
                    col_dvut, col_xuat = st.columns([2, 1])
                    with col_dvut:
                        ds_dvut = sorted(df_kh[COT_DVUT].dropna().unique().tolist())
                        chon_dvut = st.selectbox(
                            "Lọc theo Hội đoàn thể",
                            ["Tất cả"] + ds_dvut,
                            key="bc_dvut_khd",
                        )
                    with col_xuat:
                        st.markdown("<br>", unsafe_allow_html=True)
                        gia_tri = None if chon_dvut == "Tất cả" else chon_dvut
                        df_dondoc = ds_chi_tiet_khong_hd(
                            df_kh, nhom_theo=COT_DVUT, gia_tri_nhom=gia_tri)

                        if not df_dondoc.empty:
                            buf = xuat_excel({"Đôn đốc 3m KHĐ": df_dondoc})
                            st.download_button(
                                label=f"⬇️ Xuất Excel ({len(df_dondoc)} hộ)",
                                data=buf,
                                file_name=f"DonDoc_3m_{chon_dvut}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="bc_xuat_khd",
                                type="primary",
                            )

                    if not df_dondoc.empty:
                        _hien_thi_bc(
                            _fmt_df(df_dondoc),
                            key="baocao_dondoc_dvut",
                            height=340,
                        )
                        tong_lai = df_dondoc[COT_LAI_TON].sum() \
                                   if COT_LAI_TON in df_dondoc.columns else 0
                        st.caption(
                            f"Tổng **{fmt_so(len(df_dondoc))}** món · "
                            f"Lãi tồn: **{vn(tong_lai/1e6,0)}** triệu đồng"
                        )
                    else:
                        st.success("✅ Không có món vay nào quá 3 tháng không hoạt động.")

            # ── Chương trình ──
            elif loai_th == "📌 Theo chương trình vay":
                group_col = COT_TEN_CT
                # Lọc thêm nguồn vốn
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    loc_nv = st.selectbox(COT_NGUON_VON,
                        ["Tất cả","1 - Trung ương (TW)","2 - Địa phương (ĐP)"],
                        key="bc_th_nv")
                with col_f2:
                    if COT_TEN_CT in df_base.columns:
                        _ds_ct_th = sorted(df_base[COT_TEN_CT].dropna().unique().tolist())
                        _opts_ct_th = ["Tất cả"] + _ds_ct_th
                        _desired_ct_th = state.filter_chuong_trinh or "Tất cả"
                        if "bc_th_ct" not in st.session_state:
                            st.session_state["bc_th_ct"] = _desired_ct_th if _desired_ct_th in _opts_ct_th else "Tất cả"
                        elif st.session_state.get("bc_th_ct") not in _opts_ct_th:
                            st.session_state["bc_th_ct"] = "Tất cả"
                        loc_ct_th = st.selectbox("Chương trình", _opts_ct_th, key="bc_th_ct")
                        state.filter_chuong_trinh = None if loc_ct_th == "Tất cả" else loc_ct_th
                    else:
                        loc_ct_th = "Tất cả"

                df_ct_th = df_base.copy()
                if loc_nv == "1 - Trung ương (TW)" and COT_NGUON_VON in df_ct_th.columns:
                    df_ct_th = df_ct_th[df_ct_th[COT_NGUON_VON] == 1]
                elif loc_nv == "2 - Địa phương (ĐP)" and COT_NGUON_VON in df_ct_th.columns:
                    df_ct_th = df_ct_th[df_ct_th[COT_NGUON_VON] == 2]
                if loc_ct_th != "Tất cả" and COT_TEN_CT in df_ct_th.columns:
                    df_ct_th = df_ct_th[df_ct_th[COT_TEN_CT] == loc_ct_th]

                try:
                    agg_dict = {
                        "Số_KH":          (COT_MA_KH, "nunique"),
                        "Số_món_vay":     (COT_SO_KU, "nunique"),
                        "Tổng_dư_nợ":     (COT_TONG_DU_NO, "sum"),
                        "Dư_nợ_trong_hạn":(COT_DU_NO_TH, "sum"),
                        "Dư_nợ_quá_hạn":  (COT_DU_NO_QH, "sum"),
                    }
                    if COT_LAI_TON in df_ct_th.columns:
                        agg_dict["Lãi_tồn_KHĐ"] = (COT_LAI_TON, "sum")

                    dbc_raw = (
                        df_ct_th.groupby(COT_TEN_CT)
                        .agg(**agg_dict)
                        .sort_values("Tổng_dư_nợ", ascending=False)
                        .reset_index()
                    ) if COT_TEN_CT in df_ct_th.columns else None

                    if dbc_raw is not None:
                        dbc_raw["Tỷ_lệ_QH_%"] = (
                            dbc_raw["Dư_nợ_quá_hạn"]
                            / dbc_raw["Tổng_dư_nợ"].replace(0, float("nan"))
                            * 100
                        ).round(2).fillna(0)
                        st.info(f"**{fmt_so(len(dbc_raw))}** chương trình · {fmt_so(len(df_ct_th))} hồ sơ")
                        _hien_thi_bc(
                            _fmt_df(dbc_raw),
                            key="baocao_th_chuong_trinh",
                        )
                except Exception as e:
                    logger.error("tab_baocao: nhóm theo chương trình vay — %s", e, exc_info=True)
                    st.error(f"Lỗi khi nhóm theo chương trình vay: {e}")
                    dbc_raw = None

            # Xuất tổng hợp
            if dbc_raw is not None:
                st.divider()
                col_xl, col_pdf1, col_pdf2 = st.columns(3)
                with col_xl:
                    if st.button("📥 Xuất tổng hợp Excel", key="btn_xuat_th", type="primary"):
                        data_excel = xuat_bao_cao(
                            sheets={"Tổng hợp": dbc_raw},
                            tieu_de="Báo cáo tổng hợp",
                            nguoi_xuat=username or "Người dùng",
                        )
                        state.downloads.set("bc_th_excel", data_excel, ten_file_bao_cao("BC_TH"))

                    if state.downloads.has("bc_th_excel"):
                        if st.download_button(
                            "⬇ Tải Excel",
                            data=state.downloads.get_bytes("bc_th_excel"),
                            file_name=state.downloads.get_filename("bc_th_excel") or "BC_TH.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_bc_th",
                        ):
                            state.downloads.clear("bc_th_excel")
                with col_pdf1:
                    if group_col and group_col in df_base.columns:
                        if st.button("📄 Xuất PDF Pivot", key="btn_pdf_pivot", type="primary"):
                            try:
                                with st.spinner("Đang tạo PDF Pivot..."):
                                    pdf_bytes = xuat_pdf_pivot(
                                        df_base, group_col,
                                        "Báo cáo tổng hợp",
                                        username or "unknown",
                                        prefix_file="BC_TH",
                                    )
                                state.downloads.set("bc_th_pdf_pivot", pdf_bytes,
                                    f"BC_TH_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf")
                                db.ghi_audit(username or "unknown", "xuat_pdf_pivot",
                                    f"Tổng hợp theo {group_col}")
                            except Exception as e:
                                state.downloads.clear("bc_th_pdf_pivot")
                                st.error(f"❌ Lỗi tạo PDF: {e}")
                        if state.downloads.has("bc_th_pdf_pivot"):
                            if st.download_button(
                                "⬇ Tải PDF Pivot",
                                data=state.downloads.get_bytes("bc_th_pdf_pivot"),
                                file_name=state.downloads.get_filename("bc_th_pdf_pivot") or "BC_TH.pdf",
                                mime="application/pdf",
                                key="dl_bc_th_pivot",
                            ):
                                state.downloads.clear("bc_th_pdf_pivot")
                with col_pdf2:
                    if group_col and group_col in df_base.columns:
                        if st.button("📄 Xuất PDF theo Nhóm", key="btn_pdf_nhom_th", type="primary"):
                            try:
                                with st.spinner("Đang tạo PDF theo Nhóm..."):
                                    pdf_bytes = xuat_pdf_theo_nhom(
                                        df_base, group_col, COL_CHUNG,
                                        "Báo cáo chi tiết theo nhóm",
                                        username or "unknown",
                                        prefix_file="BC_TH_NHOM",
                                    )
                                state.downloads.set("bc_th_pdf_nhom", pdf_bytes,
                                    f"BC_TH_NHOM_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf")
                                db.ghi_audit(username or "unknown", "xuat_pdf_nhom",
                                    f"Theo nhóm {group_col}")
                            except Exception as e:
                                state.downloads.clear("bc_th_pdf_nhom")
                                st.error(f"❌ Lỗi tạo PDF: {e}")
                        if state.downloads.has("bc_th_pdf_nhom"):
                            if st.download_button(
                                "⬇ Tải PDF Nhóm",
                                data=state.downloads.get_bytes("bc_th_pdf_nhom"),
                                file_name=state.downloads.get_filename("bc_th_pdf_nhom") or "BC_TH_NHOM.pdf",
                                mime="application/pdf",
                                key="dl_bc_th_nhom",
                            ):
                                state.downloads.clear("bc_th_pdf_nhom")

        # ══════════════════════════════
        # MẢNG 2: CHI TIẾT
        # ══════════════════════════════
        else:
            _tab_bc_ct = st.radio(
                "Chế độ xem",
                ["📋 Báo cáo chi tiết", "📑 NQ11"],
                horizontal=True,
                key="bc_ct_tab",
                label_visibility="collapsed",
            )
            st.divider()

            if _tab_bc_ct == "📑 NQ11":
                import importlib; tab_nq11 = importlib.import_module("tabs.tab_nq11"); tab_nq11.render(st.container(), **kwargs)
            else:
                loai_ct = st.radio("Loại chi tiết",
                    ["📋 Danh sách theo tiêu chí lọc",
                     "⏰ Hồ sơ đến hạn / quá hạn",
                     "📌 Theo chương trình vay cụ thể",
                     "🏦 Theo nguồn vốn",
                     "🔴 Danh sách nợ khoanh",
                     "🟠 Danh sách nợ quá hạn"],
                    horizontal=True, key="bc_loai_ct")

                # Bộ lọc chi tiết
                with st.expander("🔧 Bộ lọc nâng cao", expanded=True):
                    d1, d2, d3 = st.columns(3)
                    with d1:
                        _ds_xa_ct = (
                            sorted(df_base[COT_TEN_XA].dropna().unique().tolist())
                            if COT_TEN_XA in df_base.columns
                            else []
                        )
                        _opts_xa_ct = ["Tất cả"] + _ds_xa_ct
                        _desired_xa_ct = state.filter_xa or "Tất cả"
                        if "bc_ct_xa" not in st.session_state:
                            st.session_state["bc_ct_xa"] = _desired_xa_ct if _desired_xa_ct in _opts_xa_ct else "Tất cả"
                        elif st.session_state.get("bc_ct_xa") not in _opts_xa_ct:
                            st.session_state["bc_ct_xa"] = "Tất cả"
                        loc_xa_ct = st.selectbox("Xã", _opts_xa_ct, key="bc_ct_xa")
                        state.filter_xa = None if loc_xa_ct == "Tất cả" else loc_xa_ct
                    with d2:
                        loc_dvut_ct = st.selectbox("Hội đoàn thể",
                            ["Tất cả"]+sorted(df_base[COT_DVUT].dropna().unique().tolist())
                            if COT_DVUT in df_base.columns else ["Tất cả"],
                            key="bc_ct_dvut")
                    with d3:
                        loc_tt_ct = st.selectbox("Tình trạng",
                            ["Tất cả"]+sorted(df_base[COT_TINH_TRANG].dropna().unique().tolist())
                            if COT_TINH_TRANG in df_base.columns else ["Tất cả"],
                            key="bc_ct_tt")

                df_ct = df_base.copy()
                if loc_xa_ct   != "Tất cả" and COT_TEN_XA       in df_ct.columns: df_ct = df_ct[df_ct[COT_TEN_XA]       == loc_xa_ct]
                if loc_dvut_ct != "Tất cả" and COT_DVUT     in df_ct.columns: df_ct = df_ct[df_ct[COT_DVUT]     == loc_dvut_ct]
                if loc_tt_ct   != "Tất cả" and COT_TINH_TRANG in df_ct.columns: df_ct = df_ct[df_ct[COT_TINH_TRANG] == loc_tt_ct]

                m1,m2,m3 = st.columns(3)
                m1.metric("Số hồ sơ", fmt_so(len(df_ct)))
                m2.metric("Tổng dư nợ", _bc_fmt_metric(df_ct[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df_ct.columns else "—")
                m3.metric("Dư nợ QH", _bc_fmt_metric(df_ct[COT_DU_NO_QH].sum()) if COT_DU_NO_QH in df_ct.columns else "—")

                export_df = None

                # ── Danh sách theo tiêu chí ──
                if loai_ct == "📋 Danh sách theo tiêu chí lọc":
                    export_df = df_ct[COL_CHUNG].copy()
                    _hien_thi_bc(
                        _fmt_df(export_df.reset_index(drop=True)),
                        key="baocao_ct_loc",
                        height=420,
                    )

                # ── Đến hạn / quá hạn ──
                elif loai_ct == "⏰ Hồ sơ đến hạn / quá hạn":
                    loai_dh = st.radio("Loại",
                        ["Đến hạn 30 ngày","Đến hạn 60 ngày","Quá hạn"],
                        horizontal=True, key="bc_dh_loai")
                    try:
                        df_tmp = df_ct.copy()
                        df_tmp[COT_NGAY_DH] = pd.to_datetime(df_tmp[COT_NGAY_DH], dayfirst=True, errors="coerce")
                        hn = pd.Timestamp.today()
                        if loai_dh == "Quá hạn":
                            df_tmp = df_tmp[df_tmp[COT_DU_NO_QH] > 0] if COT_DU_NO_QH in df_tmp.columns else df_tmp
                            st.warning(f"⚠️ **{fmt_so(len(df_tmp))}** hồ sơ quá hạn")
                        else:
                            ngay = 30 if "30" in loai_dh else 60
                            df_tmp = df_tmp[(df_tmp[COT_NGAY_DH]>=hn)&(df_tmp[COT_NGAY_DH]<=hn+pd.Timedelta(days=ngay))]
                            st.info(f"📅 **{fmt_so(len(df_tmp))}** hồ sơ đến hạn trong {ngay} ngày tới")
                        export_df = df_tmp[COL_CHUNG].sort_values(COT_NGAY_DH)
                        _hien_thi_bc(
                            _fmt_df(export_df.reset_index(drop=True)),
                            key="baocao_ct_den_han",
                            height=400,
                        )
                    except: st.error("Không thể tính hồ sơ đến hạn.")

                # ── Theo chương trình cụ thể ──
                elif loai_ct == "📌 Theo chương trình vay cụ thể":
                    if COT_TEN_CT in df_ct.columns:
                        ds_ct2 = sorted(df_ct[COT_TEN_CT].dropna().unique().tolist())
                        if ds_ct2:
                            _desired_ct2 = state.filter_chuong_trinh
                            if "bc_ct2_sel" not in st.session_state:
                                st.session_state["bc_ct2_sel"] = _desired_ct2 if _desired_ct2 in ds_ct2 else ds_ct2[0]
                            elif st.session_state.get("bc_ct2_sel") not in ds_ct2:
                                st.session_state["bc_ct2_sel"] = ds_ct2[0]
                        chon_ct2 = st.selectbox("Chọn chương trình", ds_ct2, key="bc_ct2_sel")
                        state.filter_chuong_trinh = chon_ct2
                        df_ct2 = df_ct[df_ct[COT_TEN_CT] == chon_ct2]

                        c1,c2,c3,c4 = st.columns(4)
                        c1.metric("Số hồ sơ", fmt_so(len(df_ct2)))
                        c2.metric("Tổng dư nợ", _bc_fmt_metric(df_ct2[COT_TONG_DU_NO].sum()))
                        c3.metric("Dư nợ QH", _bc_fmt_metric(df_ct2[COT_DU_NO_QH].sum()))
                        c4.metric("Tỷ lệ QH",
                            f"{df_ct2[COT_DU_NO_QH].sum()/df_ct2[COT_TONG_DU_NO].sum()*100:.2f}%"
                            if df_ct2[COT_TONG_DU_NO].sum() > 0 else "—")

                        # Tổng hợp theo xã
                        if COT_TEN_XA in df_ct2.columns:
                            st.markdown("**Tổng hợp theo xã**")
                            t_xa = df_ct2.groupby(COT_TEN_XA).agg(
                                Số_hồ_sơ=(COT_MA_KH, "nunique"),
                                Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
                                Dư_nợ_QH=(COT_DU_NO_QH, "sum"),
                            ).sort_values("Tổng_dư_nợ", ascending=False).reset_index()
                            t_xa["Tỷ_lệ_QH_%"] = (
                                t_xa["Dư_nợ_QH"]
                                / t_xa["Tổng_dư_nợ"].replace(0, float("nan"))
                                * 100
                            ).round(2).fillna(0)
                            _hien_thi_bc(
                                _fmt_df(t_xa),
                                key="baocao_ct_ct2_xa",
                            )

                        export_df = df_ct2[COL_CHUNG].copy()
                        st.markdown("**Danh sách hồ sơ**")
                        _hien_thi_bc(
                            _fmt_df(export_df.reset_index(drop=True)),
                            key="baocao_ct_ct2_ds",
                            height=350,
                        )

                # ── Theo nguồn vốn ──
                elif loai_ct == "🏦 Theo nguồn vốn":
                    if COT_NGUON_VON in df_ct.columns:
                        chon_nv = st.radio(COT_NGUON_VON,
                            ["Tổng hợp cả 2","1 - Trung ương (TW)","2 - Địa phương (ĐP)"],
                            horizontal=True, key="bc_nv_chon")

                        # Tổng hợp so sánh TW vs ĐP
                        st.markdown("**Tổng hợp so sánh nguồn vốn**")
                        t_nv = df_ct.groupby(COT_NGUON_VON).agg(
                            Số_KH          =(COT_MA_KH,"nunique"),
                            Số_món_vay     =(COT_SO_KU,"nunique"),
                            Tổng_dư_nợ     =(COT_TONG_DU_NO,"sum"),
                            Dư_nợ_trong_hạn=(COT_DU_NO_TH,"sum"),
                            Dư_nợ_quá_hạn  =(COT_DU_NO_QH,"sum"),
                        ).reset_index()
                        t_nv[COT_NGUON_VON] = t_nv[COT_NGUON_VON].map({1:"1 - TW",2:"2 - ĐP"}).fillna(t_nv[COT_NGUON_VON].astype(str))
                        t_nv["Tỷ_lệ_QH_%"] = (
                            t_nv["Dư_nợ_quá_hạn"]
                            / t_nv["Tổng_dư_nợ"].replace(0, float("nan"))
                            * 100
                        ).round(2).fillna(0)
                        _hien_thi_bc(
                            _fmt_df(t_nv),
                            key="baocao_ct_nv_tong",
                        )

                        # Lọc và hiển thị chi tiết
                        if chon_nv != "Tổng hợp cả 2":
                            nv_val = 1 if "TW" in chon_nv else 2
                            df_nv = df_ct[df_ct[COT_NGUON_VON] == nv_val]
                            st.divider()

                            # Tổng hợp theo chương trình
                            st.markdown(f"**Theo chương trình — {'TW' if nv_val==1 else 'ĐP'}**")
                            t_ct_nv = df_nv.groupby(COT_TEN_CT).agg(
                                Số_hồ_sơ   =(COT_MA_KH,"count"),
                                Tổng_dư_nợ =(COT_TONG_DU_NO,"sum"),
                                Dư_nợ_QH   =(COT_DU_NO_QH,"sum"),
                            ).sort_values("Tổng_dư_nợ",ascending=False).reset_index() if COT_TEN_CT in df_nv.columns else None
                            if t_ct_nv is not None:
                                t_ct_nv["Tỷ_lệ_QH_%"] = (
                                    t_ct_nv["Dư_nợ_QH"]
                                    / t_ct_nv["Tổng_dư_nợ"].replace(0, float("nan"))
                                    * 100
                                ).round(2).fillna(0)
                                _hien_thi_bc(
                                    _fmt_df(t_ct_nv),
                                    key="baocao_ct_nv_ct",
                                )

                            export_df = df_nv[COL_CHUNG].copy()
                            st.markdown("**Danh sách hồ sơ**")
                            _hien_thi_bc(
                                _fmt_df(export_df.reset_index(drop=True)),
                                key="baocao_ct_nv_ds",
                                height=350,
                            )
                        else:
                            export_df = df_ct[COL_CHUNG].copy()

                # ── Cột dùng chung cho 2 báo cáo DSML ──
                _COL_DSML = [c for c in [
                    COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_TO,
                    COT_MA_KH, COT_TEN_KH, COT_SDT,
                    COT_SO_KU, COT_TEN_CT, COT_NGAY_VAY, COT_NGAY_DH,
                    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_LAI_TON, COT_NGUON_VON,
                ] if c in df_ct.columns]

                # ── Nợ khoanh ──
                if loai_ct == "🔴 Danh sách nợ khoanh":
                    _COT_KHOANH = COT_DU_NO_KHOANH
                    if _COT_KHOANH not in df_ct.columns or df_ct[_COT_KHOANH].sum() == 0:
                        st.info("✅ Không có nợ khoanh trong phạm vi đã lọc.")
                    else:
                        _sort_kh = [c for c in [COT_DVUT, COT_TEN_TO, COT_TEN_KH] if c in df_ct.columns]
                        df_kh_rpt = (
                            df_ct[df_ct[_COT_KHOANH] > 0]
                            .sort_values(_sort_kh).reset_index(drop=True)
                        )
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Số món khoanh", fmt_so(len(df_kh_rpt)))
                        c2.metric("Tổng nợ khoanh", _bc_fmt_metric(df_kh_rpt[_COT_KHOANH].sum()))
                        c3.metric("Tổng lãi tồn",
                            _bc_fmt_metric(df_kh_rpt[COT_LAI_TON].sum())
                            if COT_LAI_TON in df_kh_rpt.columns else "—")

                        if COT_DVUT in df_kh_rpt.columns:
                            st.markdown("**Tổng hợp theo hội đoàn thể**")
                            _agg_kh = {"Số_món": (COT_MA_KH, "count"), "Nợ_khoanh": (_COT_KHOANH, "sum")}
                            if COT_LAI_TON in df_kh_rpt.columns:
                                _agg_kh["Lãi_tồn"] = (COT_LAI_TON, "sum")
                            t_kh = (
                                df_kh_rpt.groupby(COT_DVUT).agg(**_agg_kh)
                                .sort_values("Nợ_khoanh", ascending=False).reset_index()
                            )
                            _hien_thi_bc(_fmt_df(t_kh), key="bc_kh_dvut")

                        export_df = df_kh_rpt[_COL_DSML].copy()
                        st.markdown("**Danh sách chi tiết**")
                        _hien_thi_bc(_fmt_df(export_df), key="bc_dsml_khoanh", height=420)

                # ── Nợ quá hạn ──
                elif loai_ct == "🟠 Danh sách nợ quá hạn":
                    _sort_qh = [c for c in [COT_DVUT, COT_TEN_TO, COT_TEN_KH] if c in df_ct.columns]
                    df_qh_rpt = (
                        df_ct[df_ct[COT_DU_NO_QH] > 0]
                        .sort_values(_sort_qh).reset_index(drop=True)
                    )
                    if df_qh_rpt.empty:
                        st.success("✅ Không có nợ quá hạn trong phạm vi đã lọc.")
                    else:
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Số món QH", fmt_so(len(df_qh_rpt)))
                        c2.metric("Dư nợ QH", _bc_fmt_metric(df_qh_rpt[COT_DU_NO_QH].sum()))
                        _tl_qh = (
                            df_qh_rpt[COT_DU_NO_QH].sum() / df_qh_rpt[COT_TONG_DU_NO].sum() * 100
                            if df_qh_rpt[COT_TONG_DU_NO].sum() > 0 else 0
                        )
                        c3.metric("Tỷ lệ QH", f"{_tl_qh:.2f}%".replace(".", ","))

                        if COT_DVUT in df_qh_rpt.columns:
                            st.markdown("**Tổng hợp theo hội đoàn thể**")
                            t_qh = (
                                df_qh_rpt.groupby(COT_DVUT).agg(
                                    Số_món=(COT_MA_KH, "count"),
                                    Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
                                    Dư_nợ_QH=(COT_DU_NO_QH, "sum"),
                                ).sort_values("Dư_nợ_QH", ascending=False).reset_index()
                            )
                            t_qh["Tỷ_lệ_QH_%"] = (
                                t_qh["Dư_nợ_QH"]
                                / t_qh["Tổng_dư_nợ"].replace(0, float("nan"))
                                * 100
                            ).round(2).fillna(0)
                            _hien_thi_bc(_fmt_df(t_qh), key="bc_qh_dvut")

                        export_df = df_qh_rpt[_COL_DSML].copy()
                        st.markdown("**Danh sách chi tiết**")
                        _hien_thi_bc(_fmt_df(export_df), key="bc_dsml_qh", height=420)

                # Xuất Excel
                if export_df is not None:
                    st.divider()
                    col_xl, col_pdf = st.columns([1, 1])
                    with col_xl:
                        if st.button("📥 Xuất báo cáo chi tiết", type="primary", key="btn_xuat_ct"):
                            sheets = {"Chi tiết": export_df}
                            if la_phan_he_cn(role) and COT_TEN_PGD in df.columns:
                                sheets["Tổng hợp PGD"] = df.groupby(COT_TEN_PGD).agg(
                                    Số_hồ_sơ=(COT_MA_KH, "count"),
                                    Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
                                    Dư_nợ_QH=(COT_DU_NO_QH, "sum"),
                                ).reset_index()

                            tieu_de_xuat = f"Báo cáo chi tiết — {loai_ct[2:].strip()}"
                            ten_file = ten_file_bao_cao(
                                f"BC_CT_{loai_ct[2:12].strip().replace(' ','_')}"
                            )
                            file_bytes = xuat_bao_cao(sheets, tieu_de_xuat, username or "unknown")
                            state.downloads.set("bc_ct_excel", file_bytes, ten_file)
                            db.ghi_audit(username or "unknown", "xuat_excel", f"BC_chi_tiet_{loai_ct[2:12].strip()}")

                        if state.downloads.has("bc_ct_excel"):
                            if st.download_button(
                                "⬇ Tải Excel",
                                data=state.downloads.get_bytes("bc_ct_excel"),
                                file_name=state.downloads.get_filename("bc_ct_excel") or "BC_CT.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_bc_ct",
                            ):
                                state.downloads.clear("bc_ct_excel")
                    with col_pdf:
                        col_pdf_ct, col_pdf_nhom = st.columns(2)
                        with col_pdf_ct:
                            if st.button("📄 PDF Chi tiết", key="btn_pdf_ct", type="primary"):
                                try:
                                    with st.spinner("Đang tạo PDF chi tiết..."):
                                        pdf_bytes = xuat_pdf_chi_tiet(
                                            export_df, COL_CHUNG,
                                            f"Báo cáo — {loai_ct[2:].strip()}",
                                            username or "unknown",
                                            prefix_file="BC_CT",
                                        )
                                    state.downloads.set("bc_ct_pdf", pdf_bytes,
                                        f"BC_CT_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf")
                                    db.ghi_audit(username or "unknown", "xuat_pdf_chi_tiet",
                                        f"Chi tiết {loai_ct[2:12].strip()}")
                                except Exception as e:
                                    state.downloads.clear("bc_ct_pdf")
                                    st.error(f"❌ Lỗi tạo PDF: {e}")
                            if state.downloads.has("bc_ct_pdf"):
                                if st.download_button(
                                    "⬇ Tải PDF",
                                    data=state.downloads.get_bytes("bc_ct_pdf"),
                                    file_name=state.downloads.get_filename("bc_ct_pdf") or "BC_CT.pdf",
                                    mime="application/pdf",
                                    key="dl_bc_ct_pdf",
                                ):
                                    state.downloads.clear("bc_ct_pdf")
                        with col_pdf_nhom:
                            nhom_col = COT_TEN_PGD if COT_TEN_PGD in df_ct.columns else (
                                COT_TEN_XA if COT_TEN_XA in df_ct.columns else None
                            )
                            if nhom_col and nhom_col in df_ct.columns:
                                if st.button("📄 PDF theo Nhóm", key="btn_pdf_nhom_ct", type="primary"):
                                    try:
                                        with st.spinner("Đang tạo PDF theo Nhóm..."):
                                            pdf_bytes = xuat_pdf_theo_nhom(
                                                df_ct, nhom_col, COL_CHUNG,
                                                f"Báo cáo chi tiết — {loai_ct[2:].strip()}",
                                                username or "unknown",
                                                prefix_file="BC_CT_NHOM",
                                            )
                                        state.downloads.set("bc_ct_pdf_nhom", pdf_bytes,
                                            f"BC_CT_NHOM_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf")
                                        db.ghi_audit(username or "unknown", "xuat_pdf_nhom",
                                            f"Chi tiết theo nhóm {nhom_col}")
                                    except Exception as e:
                                        state.downloads.clear("bc_ct_pdf_nhom")
                                        st.error(f"❌ Lỗi tạo PDF: {e}")
                                if state.downloads.has("bc_ct_pdf_nhom"):
                                    if st.download_button(
                                        "⬇ Tải PDF Nhóm",
                                        data=state.downloads.get_bytes("bc_ct_pdf_nhom"),
                                        file_name=state.downloads.get_filename("bc_ct_pdf_nhom") or "BC_CT_NHOM.pdf",
                                        mime="application/pdf",
                                        key="dl_bc_ct_nhom",
                                    ):
                                        state.downloads.clear("bc_ct_pdf_nhom")
