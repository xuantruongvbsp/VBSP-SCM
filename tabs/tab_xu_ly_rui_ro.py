"""Tab Xử lý Rủi ro (XLRR) — CN: 6 sub-tabs, PGD: 4 sub-tabs.
Tích hợp: tab_no_rui_ro.py + tab_qd62.py + tab_xlrr_tong_hop.py (đã archive)
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import date, datetime
from typing import Optional

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from config import (
    COT_DIA_CHI,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
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
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,  # Để có đủ 22 đơn vị trong dropdown
    DS_PGD,
    NGUYEN_NHAN_RR,
    TEN_CHI_NHANH_HIEN_THI,
)
from data.pgd import pgd_slug
from services.xlrr_service import (
    HoSoRuiRo,
    LuuTruXLRR,
    TongHopXLRR,
    DotXLRR,
    LuuTruDotXLRR,
    LOAI_HO_SO_HSTD,
    LOAI_HO_SO_QD62,
    NGUON_TW,
    NGUON_DP,
    TRANG_THAI_CHO_DUYET,
    TRANG_THAI_DA_DUYET,
    TRANG_THAI_TU_CHOI,
)
from services.word_xln_service import (
    _tao_word_01xln_v2,
    _tao_word_02xln_v2,
    _tao_word_to_trinh_pgd,
)
from services.xlrr_export_service import tong_hop_theo_bien_phap
from tabs.base_tab import TabContext
from utils import fmt, fmt_ty, hien_thi_dataframe_phan_trang
from logger import get_logger

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────
LABEL_TW = "Trung ương"
LABEL_DP = "Địa phương"

BIEN_PHAP_KHOANH = "khoanh"
BIEN_PHAP_XOA = "xoa"
BIEN_PHAP_KHAC = "khac"

TRANG_THAI_BADGE = {
    TRANG_THAI_CHO_DUYET: "🟡 Chờ duyệt",
    TRANG_THAI_DA_DUYET: "🟢 Đã duyệt",
    TRANG_THAI_TU_CHOI: "🔴 Từ chối",
}


# ── Helpers cập nhật / xóa hồ sơ ─────────────────────────────────────────────

def _cap_nhat_hs(hs_moi: HoSoRuiRo, pgd_slug_val: str, nam: int, thang: int, username: str, la_cn: bool) -> None:
    if la_cn:
        ds = LuuTruXLRR.doc_cn(nam, thang)
        LuuTruXLRR.luu_cn([hs_moi if hs.id == hs_moi.id else hs for hs in ds], nam, thang, username)
        db.ghi_audit(username, "xlrr_cap_nhat_cn", f"ID={hs_moi.id[:8]} KH={hs_moi.ten_kh}")
    else:
        ds = LuuTruXLRR.doc_pgd(pgd_slug_val, nam, thang)
        LuuTruXLRR.luu_pgd([hs_moi if hs.id == hs_moi.id else hs for hs in ds], pgd_slug_val, nam, thang, username)
        db.ghi_audit(username, "xlrr_cap_nhat_pgd", f"ID={hs_moi.id[:8]} KH={hs_moi.ten_kh}")
    st.cache_data.clear()


def _xoa_hs(ho_so_id: str, pgd_slug_val: str, nam: int, thang: int, username: str, la_cn: bool) -> bool:
    if la_cn:
        ds = LuuTruXLRR.doc_cn(nam, thang)
        ds_moi = [hs for hs in ds if hs.id != ho_so_id]
        if len(ds_moi) == len(ds):
            return False
        LuuTruXLRR.luu_cn(ds_moi, nam, thang, username)
        db.ghi_audit(username, "xlrr_xoa_cn", f"ID={ho_so_id[:8]}")
    else:
        ds = LuuTruXLRR.doc_pgd(pgd_slug_val, nam, thang)
        ds_moi = [hs for hs in ds if hs.id != ho_so_id]
        if len(ds_moi) == len(ds):
            return False
        LuuTruXLRR.luu_pgd(ds_moi, pgd_slug_val, nam, thang, username)
        db.ghi_audit(username, "xlrr_xoa_pgd", f"ID={ho_so_id[:8]}")
    st.cache_data.clear()
    return True


def _hs_to_du_lieu_02(hs: HoSoRuiRo) -> dict:
    """Chuyển HoSoRuiRo → dict chuẩn cho _tao_word_02xln_v2."""
    return {
        "ten_nhcsxh": hs.ten_pgd,
        "dia_danh": "TP. Biên Hòa",
        "ngay_lap": hs.ngay_lap_02 or date.today(),
        "dia_diem": hs.dia_diem_02,
        "ten_pgd": hs.ten_pgd_02,
        "chuc_vu_pgd": hs.chuc_vu_pgd_02,
        "ten_ubnd": hs.ten_ubnd_02,
        "chuc_vu_ubnd": hs.chuc_vu_ubnd_02,
        "ten_hoi_nd": hs.ten_hoi_nd_02,
        "chuc_vu_hoi_nd": hs.chuc_vu_hoi_nd_02,
        "ten_cbtd": hs.ten_cbtd_02,
        "ten_to_truong": hs.ten_to_truong_02,
        "ten_kh": hs.ten_kh,
        "dia_chi": getattr(hs, "dia_chi", ""),
        "so_ku": hs.so_ku,
        "ngay_vay": hs.ngay_vay or date.today(),
        "ten_ct": hs.ten_ct,
        "ma_mon_vay": getattr(hs, "ma_mon_vay", ""),
        "muc_vay": f"{getattr(hs, 'muc_vay', 0):,.0f}".replace(",", "."),
        "tong_du_no": f"{hs.tong_du_no:,.0f}".replace(",", ".") if hs.tong_du_no else "0",
        "du_no_goc": f"{hs.du_no_goc:,.0f}".replace(",", "."),
        "lai_ton": f"{hs.lai_ton:,.0f}".replace(",", "."),
        "nguyen_nhan": hs.nguyen_nhan,
        "so_tien_thiet_hai": f"{hs.du_no_goc:,.0f}".replace(",", "."),
        "chi_tiet_thiet_hai": hs.chi_tiet_thiet_hai_02,
        "danh_gia_thiet_hai": hs.danh_gia_thiet_hai_02,
        "danh_gia_du_an": hs.danh_gia_du_an_02,
        "tai_san_hien_tai": hs.tai_san_hien_tai_02,
        "kha_nang_tra_no": hs.kha_nang_tra_no_02,
        "bien_phap_thu_hoi": "",
        "bien_phap": "Khoanh Nợ" if hs.bien_phap == "khoanh" else "Xóa Nợ",
        "so_thang": hs.so_thang,
        "so_tien_de_nghi": f"{hs.tong_du_no:,.0f}".replace(",", ".") if hs.tong_du_no else "0",
    }


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 1: LẬP HỒ SƠ PGD
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_lap_hs_pgd(df: pd.DataFrame, ctx: TabContext) -> None:
    """Sub-tab 1: Lập hồ sơ rủi ro cho PGD (từ HSTD)."""
    st.caption("Lập hồ sơ xử lý nợ rủi ro từ dữ liệu HSTD")
    
    # Lấy thông tin PGD
    role = ctx.role_norm
    username = ctx.username
    
    if la_phan_he_pgd(role):
        ten_pgd = ctx.pgd_user or DON_VI_CHI_NHANH
    else:
        # CN chọn PGD để lập thay — 22 đơn vị (Hội sở CN tỉnh + 21 PGD)
        ten_pgd = st.selectbox(
            "📍 Chọn PGD để lập hồ sơ",
            [DON_VI_CHI_NHANH] + DS_PGD,
            key="xlrr_pgd_chon_pgd",
        )
    
    pgd_slug_val = pgd_slug(ten_pgd)
    df_pgd = df[df[COT_TEN_PGD] == ten_pgd].copy() if COT_TEN_PGD in df.columns else pd.DataFrame()

    _la_cn = la_phan_he_cn(role)

    # ── Chọn đợt XLRR ────────────────────────────────────────────────────────
    _nam_xl = datetime.now().year
    ds_dot = LuuTruDotXLRR.doc_ds(_nam_xl, "cn") if _la_cn else LuuTruDotXLRR.doc_ds(_nam_xl, "pgd", pgd_slug_val)
    dot_key = f"xlrr_dot_{pgd_slug_val}"
    dot_options = {f"{d.ten_dot} ({d.ngay_bat_dau:%d/%m}–{d.ngay_ket_thuc:%d/%m})": d.id for d in ds_dot}
    dot_id = st.session_state.get(dot_key, "")
    if dot_options:
        dot_label = st.selectbox("📅 Chọn đợt XLRR", list(dot_options.keys()), key=dot_key)
        dot_id = dot_options[dot_label]
    else:
        st.warning("⚠️ Chưa có đợt XLRR nào. Vào tab '📅 Quản lý đợt' để tạo đợt trước.")
        dot_id = ""

    # ── Hồ sơ đã lập trong tháng ──────────────────────────────────────────────
    _now = datetime.now()
    _nam, _thang = _now.year, _now.month
    _edit_key = f"xlrr_edit_{pgd_slug_val}"
    _edit_id = st.session_state.get(_edit_key)

    if _la_cn:
        ds_hs = [hs for hs in LuuTruXLRR.doc_cn(_nam, _thang) if hs.ten_pgd == ten_pgd]
    else:
        ds_hs = LuuTruXLRR.doc_pgd(pgd_slug_val, _nam, _thang)

    _hs_sua = next((hs for hs in ds_hs if hs.id == _edit_id), None) if _edit_id else None

    _bp_label = {BIEN_PHAP_KHOANH: "Khoanh nợ", BIEN_PHAP_XOA: "Xóa nợ", BIEN_PHAP_KHAC: "Khác"}
    _exp_title = (
        f"📂 Hồ sơ đã lập tháng {_thang}/{_nam} — {len(ds_hs)} hồ sơ"
        if ds_hs else f"📂 Chưa có hồ sơ tháng {_thang}/{_nam}"
    )
    with st.expander(_exp_title, expanded=bool(_edit_id)):
        if not ds_hs:
            st.info("Chưa có hồ sơ nào được lập trong tháng này.")
        for hs in ds_hs:
            _active = hs.id == _edit_id
            c_info, c_bp, c_tt, c_dn, c_sua, c_xoa = st.columns([3, 1.5, 1.5, 1.5, 0.6, 0.6])
            c_info.markdown(f"**{hs.ten_kh}**  \n`{hs.so_ku}`")
            c_bp.caption(_bp_label.get(hs.bien_phap, hs.bien_phap))
            c_tt.caption(TRANG_THAI_BADGE.get(hs.trang_thai, hs.trang_thai))
            c_dn.caption(f"{fmt_ty(hs.tong_du_no)} tr")
            with c_sua:
                if st.button(
                    "✅" if _active else "✏️",
                    key=f"btn_sua_{hs.id[:8]}",
                    help="Đang sửa — bấm để hủy" if _active else "Sửa hồ sơ này",
                ):
                    if _active:
                        st.session_state.pop(_edit_key, None)
                    else:
                        st.session_state[_edit_key] = hs.id
                    st.rerun()
            with c_xoa:
                with st.popover("🗑️"):
                    st.warning(f"Xóa hồ sơ **{hs.ten_kh}** (`{hs.so_ku}`)? Không thể hoàn tác.")
                    if st.button("⚠️ Xác nhận xóa", key=f"btn_xoa_ok_{hs.id[:8]}", type="primary"):
                        if _xoa_hs(hs.id, pgd_slug_val, _nam, _thang, username, _la_cn):
                            st.session_state.pop(_edit_key, None)
                            st.toast(f"Đã xóa hồ sơ {hs.ten_kh}", icon="🗑️")
                            st.rerun()

    st.divider()

    # ── EDIT MODE: form sửa pre-filled ────────────────────────────────────────
    if _hs_sua:
        st.markdown(f"#### ✏️ Sửa hồ sơ: **{_hs_sua.ten_kh}** — `{_hs_sua.so_ku}`")
        _kp = f"sua_{_hs_sua.id[:8]}_"
        _bp_opts = [("Khoanh nợ (QĐ62)", BIEN_PHAP_KHOANH), ("Xóa nợ (QĐ62)", BIEN_PHAP_XOA)]
        _bp_idx = next((i for i, (_, v) in enumerate(_bp_opts) if v == _hs_sua.bien_phap), 0)
        _nv_opts = [(LABEL_TW, NGUON_TW), (LABEL_DP, NGUON_DP)]
        _nv_idx = next((i for i, (_, v) in enumerate(_nv_opts) if v == _hs_sua.nguon_von), 0)
        _nn_idx = NGUYEN_NHAN_RR.index(_hs_sua.nguyen_nhan) if _hs_sua.nguyen_nhan in NGUYEN_NHAN_RR else 0
        _md_opts = [("Từ 40% đến <80%", "40-80"), ("Từ 80% đến 100%", "80-100"), ("Không áp dụng", "")]
        _md_idx = next((i for i, (_, v) in enumerate(_md_opts) if v == (_hs_sua.muc_do or "")), 2)

        with st.form(f"xlrr_form_sua_{_hs_sua.id[:8]}"):
            col1, col2 = st.columns(2)
            with col1:
                bien_phap_s = st.selectbox(
                    "Biện pháp xử lý *", _bp_opts, index=_bp_idx,
                    format_func=lambda x: x[0], key=f"{_kp}bp",
                )[1]
                nguyen_nhan_s = st.selectbox(
                    "Nguyên nhân rủi ro *", NGUYEN_NHAN_RR,
                    index=_nn_idx, key=f"{_kp}nn",
                )
            with col2:
                ngay_rr_s = st.date_input(
                    "Ngày xảy ra rủi ro *",
                    value=_hs_sua.ngay_rr if isinstance(_hs_sua.ngay_rr, date) else date.today(),
                    format="DD/MM/YYYY", key=f"{_kp}ngay_rr",
                )
                nguon_von_s = st.selectbox(
                    "Nguồn vốn *", _nv_opts, index=_nv_idx,
                    format_func=lambda x: x[0], key=f"{_kp}nv",
                )[1]

            muc_do_s, so_thang_s = "", int(_hs_sua.so_thang or 0)
            if bien_phap_s == BIEN_PHAP_KHOANH:
                st.markdown("**Mức độ thiệt hại (khoanh nợ)**")
                mc1, mc2 = st.columns(2)
                with mc1:
                    muc_do_s = st.radio(
                        "Mức độ", _md_opts, index=_md_idx,
                        format_func=lambda x: x[0], key=f"{_kp}muc_do",
                    )[1]
                with mc2:
                    so_thang_s = st.number_input(
                        "Số tháng đề nghị khoanh *",
                        min_value=0, max_value=120, value=so_thang_s, step=6,
                        key=f"{_kp}so_thang",
                    )

            ghi_chu_s = st.text_area(
                "Ghi chú / Tóm tắt nguyên nhân *",
                value=_hs_sua.ghi_chu or "", height=100, key=f"{_kp}gc",
            )
            st.markdown("**💰 Thông tin dư nợ**")
            st.text_input(
                "Dư nợ gốc (từ HSTD, đồng)", value=fmt(_hs_sua.du_no_goc),
                disabled=True, key=f"{_kp}dng",
            )
            du_no_lai_s = st.number_input(
                "Dư nợ lãi (triệu đồng) *",
                min_value=0.0, step=0.1, format="%.1f",
                value=round((_hs_sua.du_no_lai or 0) / 1_000_000, 1),
                key=f"{_kp}dnl",
            )

            with st.expander("📝 Thông tin mẫu 01/XLN (tùy chọn)"):
                ngay_ky_01_s = st.date_input("Ngày ký đơn:", format="DD/MM/YYYY",
                    value=_hs_sua.ngay_ky_01 if isinstance(_hs_sua.ngay_ky_01, date) else date.today(),
                    key=f"{_kp}01_ngay")
                ma_to_s = st.text_input("Mã Tổ TK&VV:", value=_hs_sua.ma_to or "", key=f"{_kp}01_ma_to")
                ten_to_truong_s = st.text_input("Tổ trưởng:", value=_hs_sua.ten_to_truong or "", key=f"{_kp}01_ttr")
                nguyen_nhan_01_s = st.text_area("Nguyên nhân rủi ro:", value=_hs_sua.nguyen_nhan_01 or "", key=f"{_kp}01_nn")
                so_tien_th_s = st.text_input("Số tiền thiệt hại:", value=_hs_sua.so_tien_thiet_hai_01 or "0", key=f"{_kp}01_stth")
                muc_do_th_s = st.text_input("Mức độ thiệt hại (%):", value=_hs_sua.muc_do_thiet_hai_01 or "0", key=f"{_kp}01_mdth")
                kha_nang_01_s = st.text_area("Khả năng trả nợ:", value=_hs_sua.kha_nang_tra_no_01 or "", key=f"{_kp}01_kn")
                ke_hoach_01_s = st.text_input("Kế hoạch trả nợ:", value=_hs_sua.ke_hoach_tra_no_01 or "", key=f"{_kp}01_kh")

            with st.expander("📋 Thông tin mẫu 02/XLN (tùy chọn)"):
                ngay_lap_02_s = st.date_input("Ngày lập biên bản:", format="DD/MM/YYYY",
                    value=_hs_sua.ngay_lap_02 if isinstance(_hs_sua.ngay_lap_02, date) else date.today(),
                    key=f"{_kp}02_ngay")
                dia_diem_02_s = st.text_input("Địa điểm:", value=_hs_sua.dia_diem_02 or "", key=f"{_kp}02_dd")
                st.markdown("**Thành phần tham dự:**")
                _scv1, _sten1 = st.columns([1, 2])
                with _scv1:
                    chuc_vu_pgd_02_s = st.selectbox("Chức vụ NHCSXH:", ["Phó Giám đốc", "Giám đốc"],
                        index=0 if (_hs_sua.chuc_vu_pgd_02 or "Phó Giám đốc") == "Phó Giám đốc" else 1,
                        key=f"{_kp}02_cv_pgd")
                with _sten1:
                    ten_pgd_02_s = st.text_input("Họ tên đại diện NHCSXH:", value=_hs_sua.ten_pgd_02 or "", key=f"{_kp}02_pgd")
                _scv2, _sten2 = st.columns([1, 2])
                with _scv2:
                    chuc_vu_ubnd_02_s = st.selectbox("Chức vụ UBND xã:", ["Phó Chủ tịch", "Chủ tịch"],
                        index=0 if (_hs_sua.chuc_vu_ubnd_02 or "Phó Chủ tịch") == "Phó Chủ tịch" else 1,
                        key=f"{_kp}02_cv_ubnd")
                with _sten2:
                    ten_ubnd_02_s = st.text_input("Họ tên đại diện UBND:", value=_hs_sua.ten_ubnd_02 or "", key=f"{_kp}02_ubnd")
                _scv3, _sten3 = st.columns([1, 2])
                with _scv3:
                    chuc_vu_hoi_nd_02_s = st.text_input("Chức danh đoàn thể/CA:",
                        value=_hs_sua.chuc_vu_hoi_nd_02 or "Chủ tịch Hội Nông dân xã",
                        key=f"{_kp}02_cv_hnd",
                        help="VD: Chủ tịch Hội ND xã, Trưởng CA xã, Phó CT Hội PN")
                with _sten3:
                    ten_hoi_nd_02_s = st.text_input("Họ tên đại diện đoàn thể/CA:", value=_hs_sua.ten_hoi_nd_02 or "", key=f"{_kp}02_hnd")
                ten_cbtd_02_s = st.text_input("CBTD NHCSXH:", value=_hs_sua.ten_cbtd_02 or "", key=f"{_kp}02_cbtd")
                ten_to_truong_02_s = st.text_input("Tổ trưởng TK&VV:", value=_hs_sua.ten_to_truong_02 or "", key=f"{_kp}02_ttr")
                st.markdown("**Nội dung biên bản:**")
                chi_tiet_02_s = st.text_input("Chi tiết thiệt hại:", value=_hs_sua.chi_tiet_thiet_hai_02 or "", key=f"{_kp}02_ct")
                danh_gia_02_s = st.text_input("Đánh giá thiệt hại:", value=_hs_sua.danh_gia_thiet_hai_02 or "", key=f"{_kp}02_dg")
                du_an_02_s = st.text_area("Đánh giá dự án:", value=_hs_sua.danh_gia_du_an_02 or "", key=f"{_kp}02_da")
                tai_san_02_s = st.text_input("Tài sản hiện tại:", value=_hs_sua.tai_san_hien_tai_02 or "", key=f"{_kp}02_ts")
                kha_nang_02_s = st.text_area("Khả năng trả nợ:", value=_hs_sua.kha_nang_tra_no_02 or "", key=f"{_kp}02_kn")

            c_save, c_cancel = st.columns(2)
            with c_save:
                submitted_sua = st.form_submit_button("💾 Cập nhật hồ sơ", type="primary", use_container_width=True)
            with c_cancel:
                huy_sua = st.form_submit_button("↩️ Hủy", type="secondary", use_container_width=True)

        if huy_sua:
            st.session_state.pop(_edit_key, None)
            st.rerun()

        if submitted_sua:
            if len(ghi_chu_s.strip()) < 20:
                st.error("⚠️ Ghi chú phải có ít nhất 20 ký tự.")
            else:
                hs_moi = dataclasses.replace(
                    _hs_sua,
                    bien_phap=bien_phap_s,
                    nguyen_nhan=nguyen_nhan_s,
                    ngay_rr=ngay_rr_s,
                    nguon_von=nguon_von_s,
                    muc_do=muc_do_s,
                    so_thang=int(so_thang_s),
                    ghi_chu=ghi_chu_s.strip(),
                    du_no_lai=float(du_no_lai_s * 1_000_000),
                    lai_ton=float(du_no_lai_s * 1_000_000),
                    ngay_ky_01=ngay_ky_01_s,
                    ma_to=ma_to_s,
                    ten_to_truong=ten_to_truong_s,
                    nguyen_nhan_01=nguyen_nhan_01_s,
                    so_tien_thiet_hai_01=so_tien_th_s,
                    muc_do_thiet_hai_01=muc_do_th_s,
                    kha_nang_tra_no_01=kha_nang_01_s,
                    ke_hoach_tra_no_01=ke_hoach_01_s,
                    ngay_lap_02=ngay_lap_02_s,
                    dia_diem_02=dia_diem_02_s,
                    ten_pgd_02=ten_pgd_02_s,
                    chuc_vu_pgd_02=chuc_vu_pgd_02_s,
                    ten_ubnd_02=ten_ubnd_02_s,
                    chuc_vu_ubnd_02=chuc_vu_ubnd_02_s,
                    ten_hoi_nd_02=ten_hoi_nd_02_s,
                    chuc_vu_hoi_nd_02=chuc_vu_hoi_nd_02_s,
                    ten_cbtd_02=ten_cbtd_02_s,
                    ten_to_truong_02=ten_to_truong_02_s,
                    chi_tiet_thiet_hai_02=chi_tiet_02_s,
                    danh_gia_thiet_hai_02=danh_gia_02_s,
                    danh_gia_du_an_02=du_an_02_s,
                    tai_san_hien_tai_02=tai_san_02_s,
                    kha_nang_tra_no_02=kha_nang_02_s,
                )
                _cap_nhat_hs(hs_moi, pgd_slug_val, _nam, _thang, username, _la_cn)
                st.session_state.pop(_edit_key, None)
                st.success(f"✅ Đã cập nhật hồ sơ KH **{hs_moi.ten_kh}**")
                st.rerun()
        return

    # ── NEW MODE: lập hồ sơ mới ───────────────────────────────────────────────
    st.markdown("#### ➕ Lập hồ sơ mới")
    if df_pgd.empty:
        st.warning(f"⚠️ Không có dữ liệu HSTD cho {ten_pgd}")
        return

    # Bước 1: Lọc hộ vay (cascade: Xã → Tổ → KH)
    with st.expander("🔎 Bước 1: Lọc hộ vay", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ds_xa = sorted(df_pgd[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df_pgd.columns else []
            chon_xa = st.selectbox(
                "Xã/Phường",
                ["Tất cả"] + ds_xa,
                key="xlrr_pgd_xa",
                help="Gõ để tìm nhanh trong danh sách",
            )
        with c2:
            # Tổ chỉ hiện theo Xã đã chọn
            _df_xa = df_pgd[df_pgd[COT_TEN_XA] == chon_xa] if (chon_xa != "Tất cả" and COT_TEN_XA in df_pgd.columns) else df_pgd
            ds_to = sorted(_df_xa[COT_TEN_TO].dropna().unique().tolist()) if COT_TEN_TO in _df_xa.columns else []
            chon_to = st.selectbox(
                "Tổ TK&VV",
                ["Tất cả"] + ds_to,
                key="xlrr_pgd_to",
                help="Gõ để tìm nhanh trong danh sách",
            )
        with c3:
            # Tên KH: text_input lọc trước → selectbox hiện kết quả đã thu hẹp
            _df_to = _df_xa[_df_xa[COT_TEN_TO] == chon_to] if (chon_to != "Tất cả" and COT_TEN_TO in _df_xa.columns) else _df_xa
            ds_kh_all = sorted(_df_to[COT_TEN_KH].dropna().unique().tolist()) if COT_TEN_KH in _df_to.columns else []
            tim_kh = st.text_input(
                "Tên KH",
                placeholder="Gõ tên để lọc...",
                key="xlrr_pgd_tim_kh",
            )
            ds_kh_filter = [k for k in ds_kh_all if tim_kh.strip().lower() in k.lower()] if tim_kh.strip() else ds_kh_all
            chon_kh = st.selectbox(
                f"Chọn ({len(ds_kh_filter)} KH)",
                ["Tất cả"] + ds_kh_filter,
                key="xlrr_pgd_kh",
                label_visibility="collapsed" if not ds_kh_filter else "visible",
            )

    # Lọc dữ liệu
    df_hien = df_pgd.copy()
    if chon_xa != "Tất cả" and COT_TEN_XA in df_hien.columns:
        df_hien = df_hien[df_hien[COT_TEN_XA] == chon_xa]
    if chon_to != "Tất cả" and COT_TEN_TO in df_hien.columns:
        df_hien = df_hien[df_hien[COT_TEN_TO] == chon_to]
    # Nếu đã chọn tên cụ thể từ dropdown → exact match; ngược lại dùng substring từ text_input
    if chon_kh != "Tất cả" and COT_TEN_KH in df_hien.columns:
        df_hien = df_hien[df_hien[COT_TEN_KH] == chon_kh]
    elif tim_kh.strip() and COT_TEN_KH in df_hien.columns:
        df_hien = df_hien[df_hien[COT_TEN_KH].str.contains(tim_kh.strip(), case=False, na=False)]
    
    if df_hien.empty:
        st.info("ℹ️ Không tìm thấy hộ vay nào phù hợp.")
        return
    
    # Bước 2: Chọn hộ vay
    st.markdown("#### 📋 Bước 2: Chọn hộ vay")
    cot_hien = [c for c in [COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_TONG_DU_NO, COT_DU_NO_QH] if c in df_hien.columns]
    df_editor = df_hien[cot_hien].copy()
    
    # Format số tiền
    for c in [COT_TONG_DU_NO, COT_DU_NO_QH]:
        if c in df_editor.columns:
            df_editor[c] = df_editor[c].apply(lambda x: fmt(x) if pd.notna(x) else "")
    
    df_editor.insert(0, "Chọn", False)
    edited = st.data_editor(
        df_editor,
        use_container_width=True,
        hide_index=True,
        height=300,
        column_config={"Chọn": st.column_config.CheckboxColumn("Chọn")},
        key="xlrr_pgd_editor",
    )
    
    ds_chon = edited[edited["Chọn"] == True]
    if ds_chon.empty:
        st.info("👆 Tích chọn hộ vay ở bảng trên để điền thông tin và lưu hồ sơ bên dưới.")
    else:
        st.success(f"✅ Đã chọn **{len(ds_chon)}** hộ vay.")

    # Tính tổng dư nợ gốc từ HSTD trước khi vào form
    tong_du_no_goc_val = ""
    if COT_TONG_DU_NO in ds_chon.columns:
        # ds_chon còn chứa cột được format (string), cần lấy từ df_pgd gốc
        ds_so_ku_chon = set(ds_chon[COT_SO_KU].astype(str).tolist()) if COT_SO_KU in ds_chon.columns else set()
        if ds_so_ku_chon and COT_SO_KU in df_pgd.columns:
            df_goc = df_pgd[df_pgd[COT_SO_KU].astype(str).isin(ds_so_ku_chon)]
            tong_goc = df_goc[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_goc.columns else 0
            tong_du_no_goc_val = fmt(tong_goc)

    # Bước 3: Nhập thông tin rủi ro
    st.markdown("#### 📝 Bước 3: Thông tin rủi ro")
    with st.form("xlrr_pgd_form_nhap"):
        col1, col2 = st.columns(2)
        with col1:
            bien_phap = st.selectbox(
                "Biện pháp xử lý *",
                [("Khoanh nợ (QĐ62)", BIEN_PHAP_KHOANH), ("Xóa nợ (QĐ62)", BIEN_PHAP_XOA)],
                format_func=lambda x: x[0],
                key="xlrr_pgd_bien_phap",
            )[1]
            nguyen_nhan = st.selectbox("Nguyên nhân rủi ro *", NGUYEN_NHAN_RR, key="xlrr_pgd_nguyen_nhan")
        with col2:
            ngay_rr = st.date_input("Ngày xảy ra rủi ro *", value=date.today(), format="DD/MM/YYYY", key="xlrr_pgd_ngay_rr")
            nguon_von = st.selectbox(
                "Nguồn vốn *",
                [(LABEL_TW, NGUON_TW), (LABEL_DP, NGUON_DP)],
                format_func=lambda x: x[0],
                key="xlrr_pgd_nguon",
            )[1]

        # Mức độ và số tháng (chỉ cho khoanh nợ)
        muc_do = ""
        so_thang = 0
        if bien_phap == BIEN_PHAP_KHOANH:
            st.markdown("**Mức độ thiệt hại (khoanh nợ)**")
            mc1, mc2 = st.columns(2)
            with mc1:
                muc_do_sel = st.radio(
                    "Mức độ",
                    [("Từ 40% đến <80%", "40-80"), ("Từ 80% đến 100%", "80-100"), ("Không áp dụng", "")],
                    format_func=lambda x: x[0],
                    key="xlrr_pgd_muc_do",
                )
                muc_do = muc_do_sel[1]
            with mc2:
                goi_y = 60 if muc_do == "80-100" else 36
                so_thang = st.number_input(
                    "Số tháng đề nghị khoanh *",
                    min_value=0, max_value=120, value=goi_y, step=6,
                    key="xlrr_pgd_so_thang",
                )

        ghi_chu = st.text_area(
            "Ghi chú / Tóm tắt nguyên nhân *",
            placeholder="Nhập tối thiểu 20 ký tự...",
            height=100,
            key="xlrr_pgd_ghi_chu",
        )

        # Thông tin dư nợ: gốc từ HSTD (tính từ ds_chon), lãi nhập tay
        st.markdown("**💰 Thông tin dư nợ**")
        du_no_goc_display = st.text_input(
            "Dư nợ gốc (từ HSTD, đồng)",
            value=tong_du_no_goc_val,
            disabled=True,
            key="xlrr_pgd_du_no_goc_display",
        )
        du_no_lai_input = st.number_input(
            "Dư nợ lãi (nhập tay để khớp số liệu kế toán) *",
            min_value=0.0,
            step=0.1,
            format="%.1f",
            key="xlrr_pgd_du_no_lai",
        )
        
        # Expander: Thông tin mẫu 01/XLN — Đơn đề nghị
        with st.expander("📝 Thông tin mẫu 01/XLN — Đơn đề nghị (tùy chọn)"):
            ngay_ky_01 = st.date_input(
                "Ngày ký đơn:",
                value=date.today(),
                format="DD/MM/YYYY",
                key="xlrr_pgd_01_ngay",
            )
            ma_to = st.text_input("Mã Tổ TK&VV:", key="xlrr_pgd_01_ma_to")
            ten_to_truong = st.text_input("Tổ trưởng:", key="xlrr_pgd_01_to_truong")
            nguyen_nhan_01 = st.text_area("Nguyên nhân rủi ro:", key="xlrr_pgd_01_nguyen_nhan")
            so_tien_thiet_hai_01 = st.text_input("Số tiền thiệt hại:", value="0", key="xlrr_pgd_01_thiet_hai")
            muc_do_thiet_hai_01 = st.text_input("Mức độ thiệt hại (%):", value="0", key="xlrr_pgd_01_muc_do")
            kha_nang_tra_no_01 = st.text_area("Khả năng trả nợ:", key="xlrr_pgd_01_kha_nang")
            ke_hoach_tra_no_01 = st.text_input("Kế hoạch trả nợ:", key="xlrr_pgd_01_ke_hoach")
        
        # Expander: Thông tin mẫu 02/XLN — Biên bản
        with st.expander("📋 Thông tin mẫu 02/XLN — Biên bản (tùy chọn)"):
            ngay_lap_02 = st.date_input(
                "Ngày lập biên bản:",
                value=date.today(),
                format="DD/MM/YYYY",
                key="xlrr_pgd_02_ngay",
            )
            dia_diem_02 = st.text_input("Địa điểm:", key="xlrr_pgd_02_dia_diem")
            st.markdown("**Thành phần tham dự:**")
            _cv1, _ten1 = st.columns([1, 2])
            with _cv1:
                chuc_vu_pgd_02 = st.selectbox("Chức vụ NHCSXH:", ["Phó Giám đốc", "Giám đốc"], key="xlrr_pgd_02_cv_pgd")
            with _ten1:
                ten_pgd_02 = st.text_input("Họ tên đại diện NHCSXH:", key="xlrr_pgd_02_pgd")
            _cv2, _ten2 = st.columns([1, 2])
            with _cv2:
                chuc_vu_ubnd_02 = st.selectbox("Chức vụ UBND xã:", ["Phó Chủ tịch", "Chủ tịch"], key="xlrr_pgd_02_cv_ubnd")
            with _ten2:
                ten_ubnd_02 = st.text_input("Họ tên đại diện UBND:", key="xlrr_pgd_02_ubnd")
            _cv3, _ten3 = st.columns([1, 2])
            with _cv3:
                chuc_vu_hoi_nd_02 = st.text_input(
                    "Chức danh đoàn thể/CA:", value="Chủ tịch Hội Nông dân xã",
                    key="xlrr_pgd_02_cv_hnd",
                    help="VD: Chủ tịch Hội ND xã, Trưởng CA xã, Phó CT Hội PN",
                )
            with _ten3:
                ten_hoi_nd_02 = st.text_input("Họ tên đại diện đoàn thể/CA:", key="xlrr_pgd_02_hoi_nd")
            ten_cbtd_02 = st.text_input("CBTD NHCSXH:", key="xlrr_pgd_02_cbtd")
            ten_to_truong_02 = st.text_input("Tổ trưởng TK&VV:", key="xlrr_pgd_02_to_truong")
            st.markdown("**Nội dung biên bản:**")
            chi_tiet_thiet_hai_02 = st.text_input("Chi tiết thiệt hại:", key="xlrr_pgd_02_chi_tiet")
            danh_gia_thiet_hai_02 = st.text_input("Đánh giá thiệt hại:", key="xlrr_pgd_02_danh_gia")
            danh_gia_du_an_02 = st.text_area("Đánh giá dự án:", key="xlrr_pgd_02_du_an")
            tai_san_hien_tai_02 = st.text_input("Tài sản hiện tại:", key="xlrr_pgd_02_tai_san")
            kha_nang_tra_no_02 = st.text_area("Khả năng trả nợ:", key="xlrr_pgd_02_kha_nang")

        # Expander: Tờ trình PGD gửi CN
        with st.expander("📄 Thông tin Tờ trình gửi CN (tùy chọn — xuất ngay sau khi lưu)"):
            _col_tt1, _col_tt2 = st.columns(2)
            with _col_tt1:
                dot_tt_form = st.number_input(
                    "Đợt xử lý:", min_value=1, max_value=4, value=1,
                    key="xlrr_pgd_tt_dot",
                )
            with _col_tt2:
                nguon_tt_form = st.selectbox(
                    "Nguồn vốn Tờ trình:",
                    ["Trung ương (TW)", "Địa phương (ĐP)"],
                    key="xlrr_pgd_tt_nguon",
                )

        submitted = st.form_submit_button(
            "💾 Lưu hồ sơ",
            type="primary",
            disabled=ds_chon.empty,
            help="Tích chọn ít nhất 1 hộ vay ở Bước 2 trước khi lưu.",
        )
    
    if submitted:
        # Validate
        if len(ghi_chu.strip()) < 20:
            st.error("⚠️ Ghi chú phải có ít nhất 20 ký tự.")
            return
        
        # Tạo danh sách hồ sơ
        now = datetime.now()
        ds_luu: list[HoSoRuiRo] = []
        
        for _, row in ds_chon.iterrows():
            so_ku = str(row.get(COT_SO_KU, ""))
            
            # Tìm dòng đầy đủ trong df_pgd
            row_full = row
            if so_ku and not df_pgd.empty and COT_SO_KU in df_pgd.columns:
                df_tmp = df_pgd[df_pgd[COT_SO_KU].astype(str) == so_ku]
                if not df_tmp.empty:
                    row_full = df_tmp.iloc[0]
            
            # Xác định nguồn vốn từ COT_NGUON_VON nếu có
            nguon_von_val = nguon_von
            if COT_NGUON_VON in row_full:
                try:
                    nv = int(row_full.get(COT_NGUON_VON, 0) or 0)
                    if nv in (NGUON_TW, NGUON_DP):
                        nguon_von_val = nv
                except (ValueError, TypeError):
                    pass
            
            hs = HoSoRuiRo(
                id=str(uuid.uuid4()),
                ma_kh=str(row_full.get(COT_MA_KH, so_ku)),
                ten_kh=str(row_full.get(COT_TEN_KH, "")),
                so_ku=so_ku,
                xa=str(row_full.get(COT_TEN_XA, "")),
                ten_pgd=ten_pgd,
                pgd_slug=pgd_slug_val,
                ten_ct=str(row_full.get(COT_TEN_CT, "")),
                du_no_goc=float(row_full.get(COT_TONG_DU_NO, 0) or 0),
                du_no_lai=float(du_no_lai_input * 1_000_000),
                lai_ton=float(du_no_lai_input * 1_000_000),  # Lãi tồn nhập tay
                ngay_vay=row_full.get(COT_NGAY_VAY),
                ngay_dh=row_full.get(COT_NGAY_DH),
                bien_phap=bien_phap,
                nguyen_nhan=nguyen_nhan,
                muc_do=muc_do,
                so_thang=int(so_thang),
                ngay_rr=ngay_rr,
                ghi_chu=ghi_chu.strip(),
                nguon_von=nguon_von_val,
                loai_ho_so=LOAI_HO_SO_HSTD,
                trang_thai=TRANG_THAI_CHO_DUYET,
                nguoi_tao=username,
                lap_thay_pgd=la_phan_he_cn(role),
                dot_id=dot_id,
                # Thông tin mẫu 01/XLN
                ngay_ky_01=ngay_ky_01,
                ma_to=ma_to,
                ten_to_truong=ten_to_truong,
                so_tien_thiet_hai_01=so_tien_thiet_hai_01,
                muc_do_thiet_hai_01=muc_do_thiet_hai_01,
                kha_nang_tra_no_01=kha_nang_tra_no_01,
                ke_hoach_tra_no_01=ke_hoach_tra_no_01,
                # Thông tin mẫu 02/XLN
                ngay_lap_02=ngay_lap_02,
                dia_diem_02=dia_diem_02,
                ten_pgd_02=ten_pgd_02,
                chuc_vu_pgd_02=chuc_vu_pgd_02,
                ten_ubnd_02=ten_ubnd_02,
                chuc_vu_ubnd_02=chuc_vu_ubnd_02,
                ten_hoi_nd_02=ten_hoi_nd_02,
                chuc_vu_hoi_nd_02=chuc_vu_hoi_nd_02,
                ten_cbtd_02=ten_cbtd_02,
                ten_to_truong_02=ten_to_truong_02,
                chi_tiet_thiet_hai_02=chi_tiet_thiet_hai_02,
                danh_gia_thiet_hai_02=danh_gia_thiet_hai_02,
                danh_gia_du_an_02=danh_gia_du_an_02,
                tai_san_hien_tai_02=tai_san_hien_tai_02,
                kha_nang_tra_no_02=kha_nang_tra_no_02,
            )
            ds_luu.append(hs)
        
        # Lưu
        if la_phan_he_cn(role):
            # CN lập → lưu vào CN registry
            LuuTruXLRR.luu_cn(ds_luu, now.year, now.month, username)
        else:
            # PGD lập → lưu vào PGD registry
            LuuTruXLRR.luu_pgd(ds_luu, pgd_slug_val, now.year, now.month, username)

        st.cache_data.clear()
        st.success(f"✅ Đã lưu **{len(ds_luu)}** hồ sơ xử lý rủi ro.")
        st.balloons()
        # Lưu vào session_state để hiện nút tải ngay sau form
        st.session_state[f"xlrr_saved_{pgd_slug_val}"] = {
            "ds_luu": ds_luu,
            "dot": int(dot_tt_form),
            "nguon": nguon_tt_form,
            "nam": now.year,
            "thang": now.month,
            "ten_pgd": ten_pgd,
        }

    # ── Download section (hiện sau khi lưu thành công) ───────────────
    _saved = st.session_state.get(f"xlrr_saved_{pgd_slug_val}")
    if _saved:
        _ds = _saved["ds_luu"]
        _dot = _saved["dot"]
        _nguon = _saved["nguon"]
        _nam = _saved["nam"]
        _ten_pgd = _saved["ten_pgd"]
        _slug_dl = pgd_slug(_ten_pgd)

        st.markdown("---")
        st.markdown("#### 📥 Tải biểu mẫu vừa lưu")

        # Nút tải từng hồ sơ
        for _i, _hs in enumerate(_ds):
            with st.expander(f"📄 {_hs.ten_kh} — {_hs.so_ku}", expanded=False):
                _c1, _c2 = st.columns(2)
                with _c1:
                    if _hs.ten_to_truong:
                        try:
                            _du_lieu_01 = _hs.to_dict()
                            _bytes_01 = _tao_word_01xln_v2(_du_lieu_01)
                            st.download_button(
                                label="⬇️ Mẫu 01/XLN — Đơn đề nghị",
                                data=_bytes_01,
                                file_name=f"01XLN_{_slug_dl}_{_hs.so_ku[:8]}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key=f"dl_01xln_{pgd_slug_val}_{_i}",
                            )
                        except Exception as e:
                            logger.error("dl_01xln_%s: %s", _hs.id, e, exc_info=True)
                            st.error(f"❌ Lỗi 01/XLN: {e}")
                    else:
                        st.caption("⚠️ Chưa điền Tổ trưởng → không xuất 01/XLN")
                with _c2:
                    if _hs.ten_pgd_02:
                        try:
                            _bytes_02 = _tao_word_02xln_v2(_hs_to_du_lieu_02(_hs))
                            st.download_button(
                                label="⬇️ Mẫu 02/XLN — Biên bản",
                                data=_bytes_02,
                                file_name=f"02XLN_{_slug_dl}_{_hs.so_ku[:8]}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key=f"dl_02xln_{pgd_slug_val}_{_i}",
                            )
                        except Exception as e:
                            logger.error("dl_02xln_%s: %s", _hs.id, e, exc_info=True)
                            st.error(f"❌ Lỗi 02/XLN: {e}")
                    else:
                        st.caption("⚠️ Chưa điền Phó GĐ NHCSXH → không xuất 02/XLN")

        # Tờ trình PGD tổng hợp
        st.markdown("**📝 Tờ trình PGD gửi Chi nhánh**")
        _ds_kh = tong_hop_theo_bien_phap(_ds, "khoanh")
        _ds_xoa = tong_hop_theo_bien_phap(_ds, "xoa")
        _ds_kh_dict = [hs.to_dict() for hs in _ds_kh]
        _ds_xoa_dict = [hs.to_dict() for hs in _ds_xoa]

        def _agg_pgd_inline(ds_list: list) -> dict:
            tong = sum(float(r.get("tong_du_no", 0) or 0) for r in ds_list)
            tw = sum(float(r.get("tong_du_no", 0) or 0) for r in ds_list if r.get("nguon_von") == 1)
            return {"tong": tong, "tw": tw, "dp": tong - tw, "so_ho": len(ds_list)}

        _th_kh = _agg_pgd_inline(_ds_kh_dict)
        _th_xoa = _agg_pgd_inline(_ds_xoa_dict)
        _col_tt, _col_close = st.columns([3, 1])
        with _col_tt:
            try:
                _bytes_tt = _tao_word_to_trinh_pgd(
                    _th_kh, _th_xoa, _ds_kh_dict,
                    _ten_pgd, _nguon, _dot, _nam,
                )
                st.download_button(
                    label="⬇️ Tờ trình PGD gửi CN (.docx)",
                    data=_bytes_tt,
                    file_name=f"ToTrinh_PGD_{_slug_dl}_Dot{_dot}_{_nam}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key=f"dl_tt_pgd_{pgd_slug_val}",
                )
                db.ghi_audit(username, "xuat_to_trinh_pgd",
                             f"{_ten_pgd} — Đợt {_dot} T{_saved['thang']}/{_nam}")
            except Exception as e:
                logger.error("dl_to_trinh_pgd: %s", e, exc_info=True)
                st.error(f"❌ Lỗi Tờ trình PGD: {e}")
        with _col_close:
            if st.button("✕ Đóng", key=f"xlrr_saved_close_{pgd_slug_val}", use_container_width=True):
                del st.session_state[f"xlrr_saved_{pgd_slug_val}"]
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 2: THEO DÕI QĐ62 (cũ là SUB-TAB 3)
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_theo_doi_qd62(ctx: TabContext) -> None:
    """Sub-tab 2: Theo dõi và quản lý trạng thái hồ sơ QĐ62."""
    st.caption("Theo dõi trạng thái hồ sơ QĐ62 toàn Chi nhánh")
    
    role = ctx.role_norm
    username = ctx.username
    
    # Filters
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        pgd_filter = st.multiselect("PGD", ["Tất cả"] + DS_PGD, default=["Tất cả"], key="xlrr_td_pgd")
    with col_f2:
        tt_filter = st.selectbox(
            "Trạng thái",
            ["Tất cả"] + list(TRANG_THAI_BADGE.keys()),
            format_func=lambda x: TRANG_THAI_BADGE.get(x, x) if x != "Tất cả" else "Tất cả",
            key="xlrr_td_tt",
        )
    with col_f3:
        now = datetime.now()
        thang = st.selectbox("Tháng", list(range(1, 13)), index=now.month - 1, key="xlrr_td_thang")
        nam = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_td_nam")
    
    # Load data
    ds_qd62 = LuuTruXLRR.doc_qd62(int(nam), thang)
    
    # Filter
    if pgd_filter and "Tất cả" not in pgd_filter:
        ds_qd62 = [hs for hs in ds_qd62 if hs.ten_pgd in pgd_filter]
    if tt_filter != "Tất cả":
        ds_qd62 = [hs for hs in ds_qd62 if hs.trang_thai == tt_filter]
    
    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Tổng hồ sơ", len(ds_qd62))
    c2.metric("🟡 Chờ duyệt", sum(1 for hs in ds_qd62 if hs.trang_thai == TRANG_THAI_CHO_DUYET))
    c3.metric("🟢 Đã duyệt", sum(1 for hs in ds_qd62 if hs.trang_thai == TRANG_THAI_DA_DUYET))
    c4.metric("💰 Tổng dư nợ", fmt_ty(sum(hs.tong_du_no for hs in ds_qd62)))
    
    # Table
    if not ds_qd62:
        st.info("ℹ️ Chưa có hồ sơ QĐ62 nào.")
    else:
        df_show = pd.DataFrame([{
            "ID": hs.id,
            "PGD": hs.ten_pgd,
            "Họ tên": hs.ten_kh,
            "Xã": hs.xa,
            "CT": hs.ten_ct,
            "Gốc": fmt_ty(hs.du_no_goc),
            "Lãi": fmt_ty(hs.du_no_lai),
            "Lý do": hs.ly_do,
            "Trạng thái": TRANG_THAI_BADGE.get(hs.trang_thai, hs.trang_thai),
            "Ngày lập": hs.ngay_tao.strftime("%d/%m/%Y") if hs.ngay_tao else "",
        } for hs in ds_qd62])
        
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)
        
        # Actions (chỉ cho CN)
        if la_phan_he_cn(role):
            st.markdown("#### ⚡ Thao tác")
            
            ds_cho = [hs for hs in ds_qd62 if hs.trang_thai == TRANG_THAI_CHO_DUYET]
            if ds_cho:
                hs_options = {hs.id: f"{hs.ten_kh} — {hs.ten_pgd}" for hs in ds_cho}
                hs_id = st.selectbox("Chọn hồ sơ", options=list(hs_options.keys()), 
                                    format_func=lambda x: hs_options[x], key="xlrr_td_chon_hs")
                
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if st.button("✅ Duyệt", type="primary", key="xlrr_td_duyet"):
                        # Cập nhật trạng thái
                        for hs in ds_qd62:
                            if hs.id == hs_id:
                                hs.trang_thai = TRANG_THAI_DA_DUYET
                                hs.nguoi_duyet = username
                                hs.ngay_duyet = datetime.now()
                        LuuTruXLRR.luu_qd62(ds_qd62, int(nam), thang, username)
                        db.ghi_audit(username, "xlrr_duyet_qd62", f"ID: {hs_id}")
                        st.success("✅ Đã duyệt hồ sơ.")
                        st.rerun()
                
                with col_act2:
                    if st.button("❌ Từ chối", type="secondary", key="xlrr_td_tuchoi"):
                        for hs in ds_qd62:
                            if hs.id == hs_id:
                                hs.trang_thai = TRANG_THAI_TU_CHOI
                                hs.nguoi_duyet = username
                                hs.ngay_duyet = datetime.now()
                        LuuTruXLRR.luu_qd62(ds_qd62, int(nam), thang, username)
                        db.ghi_audit(username, "xlrr_tuchoi_qd62", f"ID: {hs_id}")
                        st.success("🔴 Đã từ chối hồ sơ.")
                        st.rerun()
            else:
                st.caption("Không có hồ sơ nào đang chờ duyệt.")


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 3 (CN): TỔNG HỢP CN → TW
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_tong_hop_cn(ctx: TabContext) -> None:
    """Tổng hợp toàn Chi nhánh — gửi TW."""
    st.caption("Tổng hợp hồ sơ XLRR toàn Chi nhánh — gom dữ liệu PGD, rà soát và gửi TW")

    from services.xlrr_export_service import (
        nhap_danh_sach_rui_ro_excel,
        tong_hop_theo_bien_phap,
    )
    from collections import defaultdict

    now = datetime.now()
    col_nam, col_thang = st.columns(2)
    with col_nam:
        nam = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_th_nam")
    with col_thang:
        thang_cn = st.selectbox("Tháng lưu CN", list(range(1, 13)), index=now.month - 1, key="xlrr_th_thang")

    # ── Chọn đợt XLRR ────────────────────────────────────────────────────
    ds_dot = LuuTruDotXLRR.doc_ds(nam, "cn")
    if not ds_dot:
        st.warning("⚠️ Chưa có đợt XLRR nào cho năm này. Vào tab '📅 Quản lý đợt' để tạo.")
        return

    dot_labels = {f"{d.ten_dot} ({d.ngay_bat_dau:%d/%m}–{d.ngay_ket_thuc:%d/%m}) [{d.trang_thai_label}]": d for d in ds_dot}
    dot_sel = st.selectbox("📅 Chọn đợt XLRR", list(dot_labels.keys()), key="xlrr_th_dot")
    dot = dot_labels[dot_sel]

    st.markdown("---")
    st.markdown(f"#### 📊 Tổng quan đợt: **{dot.ten_dot}**")
    col_st1, col_st2, col_st3, col_st4 = st.columns(4)
    col_st1.metric("Trạng thái", dot.trang_thai_label)
    col_st2.metric("Ngày BĐ", dot.ngay_bat_dau.strftime("%d/%m/%Y"))
    col_st3.metric("Ngày KT", dot.ngay_ket_thuc.strftime("%d/%m/%Y"))
    col_st4.metric("Đã gửi TW", "✅ Rồi" if dot.da_gui_tw else "⏳ Chưa")

    # ── Bước 1: Tự động gom hồ sơ PGD đã gửi ─────────────────────────────
    st.markdown("---")
    st.markdown("#### 📥 Bước 1: Tự động gom hồ sơ từ PGD")

    all_pgd_hs = []
    pgd_summary = []
    for ten_pgd in DS_PGD:
        slug = pgd_slug(ten_pgd)
        hs_gui_pgd: list = []
        ds = LuuTruXLRR.doc_pgd(slug, nam, thang_cn)
        hs_gui_pgd.extend(hs for hs in ds if hs.da_gui_cn)
        all_pgd_hs.extend(hs_gui_pgd)
        if hs_gui_pgd:
            pgd_summary.append({
                "PGD": ten_pgd,
                "Số HS đã gửi": len(hs_gui_pgd),
                "Khoanh": sum(1 for hs in hs_gui_pgd if hs.is_khoanh),
                "Xóa": sum(1 for hs in hs_gui_pgd if hs.is_xoa),
                "Dư nợ (tr)": fmt_ty(sum(hs.tong_du_no for hs in hs_gui_pgd)),
            })

    if pgd_summary:
        df_sum = pd.DataFrame(pgd_summary)
        st.dataframe(df_sum, use_container_width=True, hide_index=True)
        col_gom, _ = st.columns([1, 3])
        with col_gom:
            if st.button("🔄 GOM vào CN", type="primary", use_container_width=True, key="xlrr_th_gom"):
                LuuTruXLRR.luu_cn(all_pgd_hs, nam, thang_cn, ctx.username)
                st.success(f"✅ Đã gom {len(all_pgd_hs)} hồ sơ từ {len(pgd_summary)} PGD vào CN!")
                db.ghi_audit(ctx.username, "xlrr_gom_cn", f"Đợt {dot.id}: {len(all_pgd_hs)} HS từ {len(pgd_summary)} PGD")
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("Chưa có PGD nào gửi hồ sơ lên CN.")

    # ── Bước 2: Import Excel (fallback) ───────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📂 Bước 2: Import Excel (PGD gửi file thủ công)")

    uploaded_files = st.file_uploader(
        "Chọn file Excel từ PGD (có thể chọn nhiều file)",
        type=['xlsx'],
        accept_multiple_files=True,
        key="xlrr_th_upload",
    )

    if uploaded_files:
        ds_import = []
        errors = []
        for file in uploaded_files:
            try:
                ds_hs = nhap_danh_sach_rui_ro_excel(file.read())
                ds_import.extend(ds_hs)
            except Exception as e:
                logger.error("import_xlrr_excel: %s — %s", file.name, e, exc_info=True)
                errors.append(f"{file.name}: {str(e)}")

        if errors:
            st.error("❌ Lỗi khi đọc file:")
            for err in errors:
                st.write(f"- {err}")

        if ds_import:
            preview_df = pd.DataFrame([{
                "Tên KH": hs.ten_kh,
                "PGD": hs.ten_pgd,
                "Số KU": hs.so_ku,
                "Biện pháp": "Khoanh" if hs.bien_phap == "khoanh" else "Xóa",
                "Dư nợ gốc": fmt_ty(hs.du_no_goc),
            } for hs in ds_import])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

            if st.button("💾 Merge file Excel vào CN", type="primary", use_container_width=True, key="xlrr_th_merge_import"):
                ds_cn = LuuTruXLRR.doc_cn(nam, thang_cn)
                cn_dict = {hs.id: hs for hs in ds_cn}
                for hs in ds_import:
                    cn_dict[hs.id] = hs
                LuuTruXLRR.luu_cn(list(cn_dict.values()), nam, thang_cn, ctx.username)
                st.success(f"✅ Đã merge {len(ds_import)} hồ sơ từ Excel vào CN!")
                db.ghi_audit(ctx.username, "xlrr_import_cn", f"{len(ds_import)} HS từ Excel")
                st.cache_data.clear()
                st.rerun()

    # ── Bước 3: Rà soát danh sách CN ──────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✅ Bước 3: Rà soát danh sách gửi TW")

    ds_cn_all = LuuTruXLRR.doc_cn(nam, thang_cn)

    if not ds_cn_all:
        st.info("Chưa có hồ sơ nào trong CN. Thực hiện Bước 1 hoặc Bước 2 trước.")
    else:
        st.caption(f"Tổng: **{len(ds_cn_all)}** hồ sơ trong CN — Chọn/bỏ chọn để quyết định gửi TW")

        df_check = pd.DataFrame([{
            "Chọn": True,
            "Tên KH": hs.ten_kh,
            "PGD": hs.ten_pgd,
            "Số KU": hs.so_ku,
            "Biện pháp": "Khoanh" if hs.bien_phap == "khoanh" else "Xóa",
            "Dư nợ gốc (tr)": round(hs.du_no_goc / 1_000_000, 1),
            "Nguồn": "TW" if hs.nguon_von == NGUON_TW else "ĐP",
            "ID": hs.id,
        } for hs in ds_cn_all])

        df_edited = st.data_editor(
            df_check,
            column_config={
                "Chọn": st.column_config.CheckboxColumn("Gửi TW", default=True),
                "ID": None,
            },
            disabled=["Tên KH", "PGD", "Số KU", "Biện pháp", "Dư nợ gốc (tr)", "Nguồn"],
            use_container_width=True,
            hide_index=True,
            key="xlrr_th_check",
        )

        ds_chon = [hs for hs in ds_cn_all
                   if hs.id in set(df_edited[df_edited["Chọn"]]["ID"].tolist())]

        st.caption(f"Đã chọn: **{len(ds_chon)}** / {len(ds_cn_all)} hồ sơ")

        # ── Bước 4: Gửi TW ──────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 📤 Bước 4: Gửi lên TW")

        col_gui1, col_gui2 = st.columns([1, 3])
        with col_gui1:
            if st.button("📤 GỬI LÊN TW", type="primary", use_container_width=True, key="xlrr_th_gui_tw", disabled=dot.da_gui_tw or len(ds_chon) == 0):
                dot.da_gui_tw = True
                LuuTruDotXLRR.cap_nhat_dot(dot.id, nam, "cn", "", ctx.username, da_gui_tw=True)
                st.success(f"✅ Đã gửi đợt **{dot.ten_dot}** lên TW ({len(ds_chon)} hồ sơ)!")
                db.ghi_audit(ctx.username, "xlrr_gui_tw", f"Đợt {dot.id}: {len(ds_chon)} HS")
                st.cache_data.clear()
                st.rerun()
        with col_gui2:
            if dot.da_gui_tw:
                st.success("✅ Đợt này đã được gửi lên TW.")

        # ── Xuất mẫu 04/05 (tổng hợp theo biện pháp) ──────────────────
        st.markdown("---")
        st.markdown("#### 📄 Xuất mẫu tổng hợp 04/XLN và 05/XLN")

        ds_khoanh = tong_hop_theo_bien_phap(ds_chon, "khoanh")
        ds_xoa = tong_hop_theo_bien_phap(ds_chon, "xoa")

        col_export = st.columns(2)

        with col_export[0]:
            st.markdown("**Mẫu 04/XLN — Tổng hợp Khoanh nợ**")
            st.caption(f"Có {len(ds_khoanh)} hồ sơ khoanh nợ")
            if ds_khoanh:
                with st.expander("📝 Nhập thông tin để xuất 04/XLN"):
                    ten_pgd_04 = st.text_input("Phó GĐ NHCSXH:", key="xlrr_04_pgd")
                    ten_ubnd_04 = st.text_input("Phó Chủ tịch UBND:", key="xlrr_04_ubnd")
                    ten_hoi_nd_04 = st.text_input("Chủ tịch Hội ND:", key="xlrr_04_hoi_nd")
                    ten_cbtd_04 = st.text_input("CBTD NHCSXH:", key="xlrr_04_cbtd")
                    ngay_lap_04 = st.date_input("Ngày lập:", value=date.today(), format="DD/MM/YYYY", key="xlrr_04_ngay")
                    if st.button("📄 Xuất 04/XLN", type="primary", use_container_width=True, key="btn_04xln"):
                        from services.word_xln_service import _tao_word_04xln_v2
                        thong_tin_04 = {
                            "ten_nhcsxh": TEN_CHI_NHANH_HIEN_THI,
                            "dia_danh": "TP. Biên Hòa",
                            "ngay_lap": ngay_lap_04,
                            "ten_pgd": ten_pgd_04,
                            "ten_ubnd": ten_ubnd_04,
                            "ten_hoi_nd": ten_hoi_nd_04,
                            "ten_cbtd": ten_cbtd_04,
                        }
                        try:
                            file_bytes = _tao_word_04xln_v2(ds_khoanh, thong_tin_04)
                            st.download_button(
                                label="⬇️ Tải 04/XLN (.docx)",
                                data=file_bytes,
                                file_name=f"04XLN_TongHop_Khoanh_Dot{dot.id}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key="dl_04xln"
                            )
                            db.ghi_audit(ctx.username, "xuat_04xln", f"{len(ds_khoanh)} hồ sơ khoanh nợ - {dot.id}")
                            st.success(f"✅ Đã xuất mẫu 04/XLN ({len(ds_khoanh)} hồ sơ)")
                        except Exception as e:
                            logger.error("xuat_04xln: %s", e, exc_info=True)
                            st.error(f"❌ Lỗi xuất 04/XLN: {e}")
            else:
                st.info("ℹ️ Không có hồ sơ khoanh nợ")

        with col_export[1]:
            st.markdown("**Mẫu 05/XLN — Tổng hợp Xóa nợ**")
            st.caption(f"Có {len(ds_xoa)} hồ sơ xóa nợ")
            if ds_xoa:
                with st.expander("📝 Nhập thông tin để xuất 05/XLN"):
                    ten_pgd_05 = st.text_input("Phó GĐ NHCSXH:", key="xlrr_05_pgd")
                    ten_ubnd_05 = st.text_input("Phó Chủ tịch UBND:", key="xlrr_05_ubnd")
                    ten_hoi_nd_05 = st.text_input("Chủ tịch Hội ND:", key="xlrr_05_hoi_nd")
                    ten_cbtd_05 = st.text_input("CBTD NHCSXH:", key="xlrr_05_cbtd")
                    ngay_lap_05 = st.date_input("Ngày lập:", value=date.today(), format="DD/MM/YYYY", key="xlrr_05_ngay")
                    if st.button("📄 Xuất 05/XLN", type="primary", use_container_width=True, key="btn_05xln"):
                        from services.word_xln_service import _tao_word_05xln_v2
                        thong_tin_05 = {
                            "ten_nhcsxh": TEN_CHI_NHANH_HIEN_THI,
                            "dia_danh": "TP. Biên Hòa",
                            "ngay_lap": ngay_lap_05,
                            "ten_pgd": ten_pgd_05,
                            "ten_ubnd": ten_ubnd_05,
                            "ten_hoi_nd": ten_hoi_nd_05,
                            "ten_cbtd": ten_cbtd_05,
                        }
                        try:
                            file_bytes = _tao_word_05xln_v2(ds_xoa, thong_tin_05)
                            st.download_button(
                                label="⬇️ Tải 05/XLN (.docx)",
                                data=file_bytes,
                                file_name=f"05XLN_TongHop_Xoa_Dot{dot.id}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key="dl_05xln"
                            )
                            db.ghi_audit(ctx.username, "xuat_05xln", f"{len(ds_xoa)} hồ sơ xóa nợ - {dot.id}")
                            st.success(f"✅ Đã xuất mẫu 05/XLN ({len(ds_xoa)} hồ sơ)")
                        except Exception as e:
                            logger.error("xuat_05xln: %s", e, exc_info=True)
                            st.error(f"❌ Lỗi xuất 05/XLN: {e}")
            else:
                st.info("ℹ️ Không có hồ sơ xóa nợ")

        # ── Tờ trình CN gửi NHCSXH TW ──────────────────────────────────
        st.markdown("---")
        st.markdown("#### 📝 Tờ trình CN gửi NHCSXH TW")
        with st.expander("Nhập thông tin để xuất Tờ trình CN"):
            col_tt1, col_tt2 = st.columns(2)
            with col_tt1:
                dot_tt_cn = st.number_input("Đợt xử lý:", min_value=1, max_value=4, value=1, key="xlrr_tt_cn_dot")
                nam_tt_cn = st.number_input("Năm:", min_value=2020, max_value=2030, value=int(nam), key="xlrr_tt_cn_nam")
            with col_tt2:
                nguon_tt_cn = st.selectbox("Nguồn vốn:", ["Trung ương (TW)", "Địa phương (ĐP)"], key="xlrr_tt_cn_nguon")
            if st.button("📝 Xuất Tờ trình CN", type="primary", use_container_width=True, key="btn_tt_cn"):
                from services.word_xln_service import _tao_word_to_trinh_cn
                ds_kh_tt = tong_hop_theo_bien_phap(ds_chon, "khoanh")
                ds_xoa_tt = tong_hop_theo_bien_phap(ds_chon, "xoa")
                ds_kh_dict = [hs.to_dict() for hs in ds_kh_tt]
                ds_xoa_dict = [hs.to_dict() for hs in ds_xoa_tt]
                def _agg(ds_list):
                    tong = sum(float(r.get("tong_du_no", 0) or 0) for r in ds_list)
                    tw = sum(float(r.get("tong_du_no", 0) or 0) for r in ds_list if r.get("nguon_von") == 1)
                    dp = tong - tw
                    return {"tong": tong, "tw": tw, "dp": dp, "so_ho": len(ds_list)}
                tong_hop_kh = _agg(ds_kh_dict)
                tong_hop_xoa = _agg(ds_xoa_dict)
                nguon_label = nguon_tt_cn
                try:
                    file_bytes = _tao_word_to_trinh_cn(
                        tong_hop_kh, tong_hop_xoa, ds_kh_dict,
                        TEN_CHI_NHANH_HIEN_THI, nguon_label,
                        int(dot_tt_cn), int(nam_tt_cn),
                    )
                    st.download_button(
                        label="⬇️ Tải Tờ trình CN (.docx)",
                        data=file_bytes,
                        file_name=f"ToTrinh_CN_Dot{int(dot_tt_cn)}_{int(nam_tt_cn)}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key="dl_tt_cn",
                    )
                    db.ghi_audit(ctx.username, "xuat_to_trinh_cn", f"Đợt {int(dot_tt_cn)}/{int(nam_tt_cn)}")
                    st.success("✅ Xuất Tờ trình CN thành công!")
                except Exception as e:
                    logger.error("xuat_to_trinh_cn: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất Tờ trình CN: {e}")

        # ── 13/XLN · 14/XLN — Báo cáo sau hạch toán ────────────────────
        st.markdown("---")
        st.markdown("#### 📊 Báo cáo sau hạch toán (13/XLN · 14/XLN)")
        st.caption("Xuất sau khi có Quyết định của Hội đồng quản trị NHCSXH.")

        ds_kh_tw_13 = [hs for hs in ds_chon if hs.bien_phap == BIEN_PHAP_KHOANH and hs.nguon_von == NGUON_TW]
        ds_kh_dp_13 = [hs for hs in ds_chon if hs.bien_phap == BIEN_PHAP_KHOANH and hs.nguon_von == NGUON_DP]
        ds_xo_tw_13 = [hs for hs in ds_chon if hs.bien_phap == BIEN_PHAP_XOA and hs.nguon_von == NGUON_TW]
        ds_xo_dp_13 = [hs for hs in ds_chon if hs.bien_phap == BIEN_PHAP_XOA and hs.nguon_von == NGUON_DP]

        with st.expander("⚙️ Thông tin Quyết định HĐQT", expanded=False):
            col_qd1, col_qd2, col_qd3, col_qd4 = st.columns(4)
            with col_qd1:
                so_qd_13 = st.text_input("Số QĐ HĐQT", placeholder="123/QĐ-HĐQT", key="xlrr_13_so_qd")
            with col_qd2:
                ngay_qd_13 = st.date_input("Ngày ký QĐ", value=date.today(), format="DD/MM/YYYY", key="xlrr_13_ngay_qd")
            with col_qd3:
                ngay_bd_13 = st.date_input("Từ ngày", value=date.today(), format="DD/MM/YYYY", key="xlrr_13_ngay_bd")
            with col_qd4:
                ngay_kt_13 = st.date_input("Đến ngày", value=date.today(), format="DD/MM/YYYY", key="xlrr_13_ngay_kt")

        from services.rui_ro_aggregation import _tong_hop_no
        from services.word_xln_service import _tao_word_13xln, _tao_word_14xln

        col13_tw, col13_dp, col14_tw, col14_dp = st.columns(4)

        def _to_dict_list(hs_list: list) -> list:
            return [hs.to_dict() for hs in hs_list]

        with col13_tw:
            if st.button("📥 13/XLN\nTW", use_container_width=True, key="xlrr_13_tw_btn"):
                if not ds_kh_tw_13:
                    st.warning("⚠️ Không có hồ sơ khoanh nợ TW.")
                elif not so_qd_13.strip():
                    st.error("⚠️ Vui lòng nhập Số QĐ HĐQT.")
                else:
                    try:
                        tong_hop = _tong_hop_no(_to_dict_list(ds_kh_tw_13))
                        file_bytes = _tao_word_13xln(
                            tong_hop, TEN_CHI_NHANH_HIEN_THI, LABEL_TW,
                            so_qd_13.strip(), ngay_qd_13, ngay_bd_13, ngay_kt_13,
                        )
                        st.download_button(
                            label="⬇️ Tải 13/XLN TW (.docx)",
                            data=file_bytes,
                            file_name=f"13XLN_TW_CN_Dot{dot.id}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="dl_13xln_tw",
                        )
                        db.ghi_audit(ctx.username, "xuat_13xln_tw", f"{len(ds_kh_tw_13)} HS - Đợt {dot.id}")
                        st.success(f"✅ Đã xuất 13/XLN TW ({len(ds_kh_tw_13)} hồ sơ)")
                    except Exception as e:
                        logger.error("xuat_13xln_tw: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất 13/XLN TW: {e}")

        with col13_dp:
            if st.button("📥 13/XLN\nĐP", use_container_width=True, key="xlrr_13_dp_btn"):
                if not ds_kh_dp_13:
                    st.warning("⚠️ Không có hồ sơ khoanh nợ ĐP.")
                elif not so_qd_13.strip():
                    st.error("⚠️ Vui lòng nhập Số QĐ HĐQT.")
                else:
                    try:
                        tong_hop = _tong_hop_no(_to_dict_list(ds_kh_dp_13))
                        file_bytes = _tao_word_13xln(
                            tong_hop, TEN_CHI_NHANH_HIEN_THI, LABEL_DP,
                            so_qd_13.strip(), ngay_qd_13, ngay_bd_13, ngay_kt_13,
                        )
                        st.download_button(
                            label="⬇️ Tải 13/XLN ĐP (.docx)",
                            data=file_bytes,
                            file_name=f"13XLN_DP_CN_Dot{dot.id}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="dl_13xln_dp",
                        )
                        db.ghi_audit(ctx.username, "xuat_13xln_dp", f"{len(ds_kh_dp_13)} HS - Đợt {dot.id}")
                        st.success(f"✅ Đã xuất 13/XLN ĐP ({len(ds_kh_dp_13)} hồ sơ)")
                    except Exception as e:
                        logger.error("xuat_13xln_dp: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất 13/XLN ĐP: {e}")

        with col14_tw:
            if st.button("📥 14/XLN\nTW", use_container_width=True, key="xlrr_14_tw_btn"):
                if not ds_xo_tw_13:
                    st.warning("⚠️ Không có hồ sơ xóa nợ TW.")
                elif not so_qd_13.strip():
                    st.error("⚠️ Vui lòng nhập Số QĐ HĐQT.")
                else:
                    try:
                        tong_hop = _tong_hop_no(_to_dict_list(ds_xo_tw_13))
                        file_bytes = _tao_word_14xln(
                            tong_hop, TEN_CHI_NHANH_HIEN_THI, LABEL_TW,
                            so_qd_13.strip(), ngay_qd_13, ngay_bd_13, ngay_kt_13,
                        )
                        st.download_button(
                            label="⬇️ Tải 14/XLN TW (.docx)",
                            data=file_bytes,
                            file_name=f"14XLN_TW_CN_Dot{dot.id}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="dl_14xln_tw",
                        )
                        db.ghi_audit(ctx.username, "xuat_14xln_tw", f"{len(ds_xo_tw_13)} HS - Đợt {dot.id}")
                        st.success(f"✅ Đã xuất 14/XLN TW ({len(ds_xo_tw_13)} hồ sơ)")
                    except Exception as e:
                        logger.error("xuat_14xln_tw: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất 14/XLN TW: {e}")

        with col14_dp:
            if st.button("📥 14/XLN\nĐP", use_container_width=True, key="xlrr_14_dp_btn"):
                if not ds_xo_dp_13:
                    st.warning("⚠️ Không có hồ sơ xóa nợ ĐP.")
                elif not so_qd_13.strip():
                    st.error("⚠️ Vui lòng nhập Số QĐ HĐQT.")
                else:
                    try:
                        tong_hop = _tong_hop_no(_to_dict_list(ds_xo_dp_13))
                        file_bytes = _tao_word_14xln(
                            tong_hop, TEN_CHI_NHANH_HIEN_THI, LABEL_DP,
                            so_qd_13.strip(), ngay_qd_13, ngay_bd_13, ngay_kt_13,
                        )
                        st.download_button(
                            label="⬇️ Tải 14/XLN ĐP (.docx)",
                            data=file_bytes,
                            file_name=f"14XLN_DP_CN_Dot{dot.id}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="dl_14xln_dp",
                        )
                        db.ghi_audit(ctx.username, "xuat_14xln_dp", f"{len(ds_xo_dp_13)} HS - Đợt {dot.id}")
                        st.success(f"✅ Đã xuất 14/XLN ĐP ({len(ds_xo_dp_13)} hồ sơ)")
                    except Exception as e:
                        logger.error("xuat_14xln_dp: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất 14/XLN ĐP: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 4 (PGD) / SUB-TAB 4 (CN): GỬI CN / XUẤT BIỂU MẪU
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_gui_cn_pgd(df: pd.DataFrame, ctx: TabContext) -> None:
    """Xuất biểu mẫu 01/XLN, 02/XLN; Tờ trình PGD; Gửi Excel lên CN."""
    st.caption("📤 Xuất biểu mẫu và gửi dữ liệu lên CN")

    from services.xlrr_export_service import (
        xuat_danh_sach_rui_ro_excel,
        tong_hop_theo_bien_phap,
    )

    role = ctx.role_norm
    pgd_user = ctx.pgd_user

    # ── Chọn kỳ ──────────────────────────────────────────────────────
    now = datetime.now()
    col_ky1, col_ky2 = st.columns(2)
    with col_ky1:
        thang_xuat = st.selectbox(
            "Tháng",
            list(range(1, 13)),
            index=now.month - 1,
            key="xlrr_pgd_gui_thang",
        )
    with col_ky2:
        nam_xuat = st.number_input(
            "Năm",
            min_value=2020,
            max_value=2030,
            value=now.year,
            step=1,
            key="xlrr_pgd_gui_nam",
        )

    # ── Load hồ sơ ──────────────────────────────────────────────────
    if la_phan_he_cn(role):
        ds_hs = LuuTruXLRR.doc_cn(int(nam_xuat), thang_xuat)
        ds_hs += LuuTruXLRR.doc_qd62(int(nam_xuat), thang_xuat)
    else:
        ds_hs = (
            LuuTruXLRR.doc_pgd(pgd_slug(pgd_user), int(nam_xuat), thang_xuat)
            if pgd_user
            else []
        )

    if not ds_hs:
        st.info(f"ℹ️ Chưa có hồ sơ nào trong kỳ T{thang_xuat}/{int(nam_xuat)}.")
        return

    # ── Xuất Excel gửi CN (chỉ PGD) ──────────────────────────────────
    if la_phan_he_pgd(role):
        st.markdown("---")
        st.markdown("#### 📥 Bước 1: Xuất Excel gửi CN")
        col_excel = st.columns([1, 2])
        with col_excel[0]:
            if st.button("📥 Xuất Excel", use_container_width=True, type="primary", key="xlrr_pgd_gui_btn_excel"):
                try:
                    excel_bytes = xuat_danh_sach_rui_ro_excel(
                        ds_hs, pgd_user or "PGD", int(nam_xuat), thang_xuat
                    )
                    st.download_button(
                        label="⬇️ Tải file Excel",
                        data=excel_bytes,
                        file_name=f"XLRR_{pgd_slug(pgd_user or 'pgd')}_{thang_xuat:02d}_{int(nam_xuat)}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="xlrr_pgd_gui_dl_excel",
                    )
                except Exception as e:
                    logger.error("xuat_excel_xlrr_pgd: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất Excel: {e}")
        with col_excel[1]:
            st.caption("File Excel này chứa dữ liệu rủi ro để gửi CN tổng hợp mẫu 04/05.")

        # ── Tờ trình PGD ─────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 📝 Bước 2: Xuất Tờ trình PGD gửi CN")
        with st.expander("Nhập thông tin để xuất Tờ trình PGD"):
            col_tt1, col_tt2 = st.columns(2)
            with col_tt1:
                dot_tt = st.number_input("Đợt xử lý:", min_value=1, max_value=4, value=1, key="xlrr_tt_pgd_dot")
                nam_tt = st.number_input("Năm:", min_value=2020, max_value=2030, value=int(nam_xuat), key="xlrr_tt_pgd_nam")
            with col_tt2:
                nguon_tt = st.selectbox("Nguồn vốn:", ["Trung ương (TW)", "Địa phương (ĐP)"], key="xlrr_tt_pgd_nguon")

            if st.button("📝 Xuất Tờ trình PGD", type="primary", use_container_width=True, key="xlrr_tt_pgd_btn"):
                from services.word_xln_service import _tao_word_to_trinh_pgd

                ds_kh_pgd = tong_hop_theo_bien_phap(ds_hs, "khoanh")
                ds_xoa_pgd = tong_hop_theo_bien_phap(ds_hs, "xoa")
                ds_kh_dict = [hs.to_dict() for hs in ds_kh_pgd]
                ds_xoa_dict = [hs.to_dict() for hs in ds_xoa_pgd]

                def _agg_pgd(ds_list: list) -> dict:
                    tong = sum(float(r.get("tong_du_no", 0) or 0) for r in ds_list)
                    tw = sum(float(r.get("tong_du_no", 0) or 0) for r in ds_list if r.get("nguon_von") == 1)
                    return {"tong": tong, "tw": tw, "dp": tong - tw, "so_ho": len(ds_list)}

                tong_hop_kh = _agg_pgd(ds_kh_dict)
                tong_hop_xoa = _agg_pgd(ds_xoa_dict)
                try:
                    file_bytes = _tao_word_to_trinh_pgd(
                        tong_hop_kh, tong_hop_xoa, ds_kh_dict,
                        pgd_user or "", nguon_tt, int(dot_tt), int(nam_tt),
                    )
                    st.download_button(
                        label="⬇️ Tải Tờ trình PGD (.docx)",
                        data=file_bytes,
                        file_name=f"ToTrinh_PGD_{pgd_slug(pgd_user or 'pgd')}_Dot{int(dot_tt)}_{int(nam_tt)}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key="xlrr_tt_pgd_dl",
                    )
                    db.ghi_audit(ctx.username, "xuat_to_trinh_pgd",
                                 f"{pgd_user} — Đợt {int(dot_tt)} T{thang_xuat}/{int(nam_tt)}")
                    st.success("✅ Xuất Tờ trình PGD thành công!")
                except Exception as e:
                    logger.error("xuat_to_trinh_pgd: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất Tờ trình PGD: {e}")

        # ── Bước 3: Đánh dấu đã gửi CN ──────────────────────────────
        st.markdown("---")
        st.markdown("#### 📤 Bước 3: Đánh dấu đã gửi CN")
        da_gui = all(hs.da_gui_cn for hs in ds_hs)
        if da_gui:
            st.success("✅ Tất cả hồ sơ kỳ này đã được đánh dấu gửi CN.")
        else:
            so_chua_gui = sum(1 for hs in ds_hs if not hs.da_gui_cn)
            st.info(f"📋 Còn {so_chua_gui}/{len(ds_hs)} hồ sơ chưa đánh dấu gửi CN.")
            if st.button("📤 ĐÁNH DẤU ĐÃ GỬI CN", type="primary", use_container_width=True, key="xlrr_pgd_gui_danh_dau"):
                for hs in ds_hs:
                    hs.da_gui_cn = True
                LuuTruXLRR.luu_pgd(ds_hs, pgd_slug(pgd_user), int(nam_xuat), thang_xuat, ctx.username)
                db.ghi_audit(ctx.username, "xlrr_gui_cn", f"{pgd_user}: {len(ds_hs)} HS T{thang_xuat}/{int(nam_xuat)}")
                st.success(f"✅ Đã đánh dấu {len(ds_hs)} hồ sơ gửi CN!")
                st.cache_data.clear()
                st.rerun()

    # ── Bước 4 (PGD) / Bước 1 (CN): Xuất biểu mẫu từng hồ sơ ───────
    st.markdown("---")
    st.markdown("#### 📄 Xuất biểu mẫu từng hồ sơ (01/XLN, 02/XLN)")
    st.markdown("#### 📋 Chọn hồ sơ xuất biểu mẫu")
    hs_map = {hs.id: hs for hs in ds_hs}
    hs_labels = {
        hs.id: f"{hs.ten_kh} — {hs.ten_pgd} — KU: {hs.so_ku or 'N/A'}"
        for hs in ds_hs
    }
    selected_id = st.selectbox(
        "Chọn hồ sơ:",
        options=list(hs_map.keys()),
        format_func=lambda x: hs_labels.get(x, x),
        key="xlrr_pgd_gui_select_hs",
    )

    if not selected_id:
        return

    hs = hs_map[selected_id]
    
    # Kiểm tra trạng thái nhập liệu
    da_nhap_01 = bool(hs.ngay_ky_01 and hs.ten_to_truong)
    da_nhap_02 = bool(hs.ngay_lap_02 and hs.ten_pgd_02)
    
    if not da_nhap_01 or not da_nhap_02:
        st.warning("⚠️ Hồ sơ chưa nhập đầy đủ thông tin mẫu 01/XLN hoặc 02/XLN. Vui lòng quay lại tab 'Lập hồ sơ PGD' để bổ sung.")
    else:
        st.success("✅ Hồ sơ đã nhập đầy đủ thông tin.")
    
    col1, col2 = st.columns(2)
    
    # ── Xuất 01/XLN ────────────────────────────────────────────────────
    with col1:
        st.markdown("**📝 Mẫu 01/XLN — Đơn đề nghị**")
        
        if st.button("📄 Xuất 01/XLN", use_container_width=True, key="xlrr_pgd_gui_btn_01xln"):
            # Chuẩn bị dữ liệu từ hs đã lưu
            du_lieu_01 = {
                "ten_nhcsxh": hs.ten_pgd,
                "dia_danh": "TP. Biên Hòa",
                "ngay_ky": hs.ngay_ky_01 or date.today(),
                "ten_kh": hs.ten_kh,
                "dia_chi": getattr(hs, 'dia_chi', ''),
                "ma_to": hs.ma_to,
                "ten_to_truong": hs.ten_to_truong,
                "so_ku": hs.so_ku,
                "ngay_vay": hs.ngay_vay or date.today(),
                "ten_ct": hs.ten_ct,
                "muc_vay": f"{getattr(hs, 'muc_vay', 0):,.0f}".replace(",", "."),
                "ngay_dh": getattr(hs, 'ngay_dh', ''),
                "muc_dich_vay": getattr(hs, 'muc_dich_vay', ''),
                "tong_du_no": f"{hs.tong_du_no:,.0f}".replace(",", ".") if hs.tong_du_no else "0",
                "du_no_goc": f"{hs.du_no_goc:,.0f}".replace(",", "."),
                "lai_ton": f"{hs.lai_ton:,.0f}".replace(",", "."),
                "nguyen_nhan": hs.nguyen_nhan,
                "so_tien_thiet_hai": hs.so_tien_thiet_hai_01,
                "muc_do_thiet_hai": hs.muc_do_thiet_hai_01,
                "kha_nang_tra_no": hs.kha_nang_tra_no_01,
                "bien_phap": "Khoanh Nợ" if hs.bien_phap == "khoanh" else "Xóa Nợ",
                "so_tien_de_nghi": f"{hs.tong_du_no:,.0f}".replace(",", ".") if hs.tong_du_no else "0",
                "so_thang": hs.so_thang,
                "ke_hoach_tra_no": hs.ke_hoach_tra_no_01,
            }
            
            try:
                file_bytes = _tao_word_01xln_v2(du_lieu_01)
                st.download_button(
                    label="⬇️ Tải 01/XLN (.docx)",
                    data=file_bytes,
                    file_name=f"01XLN_{hs.ma_kh}_{(hs.ngay_ky_01 or date.today()).strftime('%Y%m%d')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="xlrr_pgd_gui_dl_01xln"
                )
                db.ghi_audit(ctx.username, "xuat_01xln", f"Mã KH: {hs.ma_kh}, Số KU: {hs.so_ku}")
                st.success("✅ Đã xuất 01/XLN thành công!")
            except Exception as e:
                logger.error("xuat_01xln: %s", e, exc_info=True)
                st.error(f"❌ Lỗi xuất 01/XLN: {e}")
    
    # ── Xuất 02/XLN ────────────────────────────────────────────────────
    with col2:
        st.markdown("**📋 Mẫu 02/XLN — Biên bản**")
        
        if st.button("📄 Xuất 02/XLN", use_container_width=True, key="xlrr_pgd_gui_btn_02xln"):
            du_lieu_02 = _hs_to_du_lieu_02(hs)
            
            try:
                file_bytes = _tao_word_02xln_v2(du_lieu_02)
                st.download_button(
                    label="⬇️ Tải 02/XLN (.docx)",
                    data=file_bytes,
                    file_name=f"02XLN_{hs.ma_kh}_{(hs.ngay_lap_02 or date.today()).strftime('%Y%m%d')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="xlrr_pgd_gui_dl_02xln"
                )
                db.ghi_audit(ctx.username, "xuat_02xln", f"Mã KH: {hs.ma_kh}, Số KU: {hs.so_ku}")
                st.success("✅ Đã xuất 02/XLN thành công!")
            except Exception as e:
                logger.error("xuat_02xln: %s", e, exc_info=True)
                st.error(f"❌ Lỗi xuất 02/XLN: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 5 (CN): DASHBOARD GIÁM ĐỐC
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_dashboard_gd(ctx: TabContext) -> None:
    """Dashboard tổng hợp XLRR cho Giám đốc / Ban lãnh đạo."""
    from auth import la_executive, la_admin_cn

    role = ctx.role_norm
    if not (la_executive(role) or la_admin_cn(role) or role in ("manager_cn", "manager")):
        st.warning("⚠️ Chỉ Giám đốc và Ban lãnh đạo Chi nhánh mới có quyền xem mục này.")
        return

    st.caption("📊 Tổng quan tình hình xử lý rủi ro toàn Chi nhánh")

    now = datetime.now()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        thang_dg = st.selectbox("Tháng", list(range(1, 13)), index=now.month - 1, key="xlrr_dg_thang")
    with col_f2:
        nam_dg = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_dg_nam")

    metrics = TongHopXLRR.tong_hop_toan_cn(int(nam_dg), thang_dg)

    st.markdown(f"#### 📊 Tổng quan T{thang_dg}/{int(nam_dg)}")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Tổng hồ sơ", metrics.get("tong_ho_so", 0))
    c2.metric("PGD có hồ sơ", metrics.get("so_pgd_co_hs", 0))
    c3.metric("Khoanh nợ", metrics.get("so_khoanh", 0))
    c4.metric("Xóa nợ", metrics.get("so_xoa", 0))
    c5.metric("TW (triệu đ)", fmt_ty(metrics.get("tw_tien", 0)))
    c6.metric("ĐP (triệu đ)", fmt_ty(metrics.get("dp_tien", 0)))

    st.markdown("#### 🏢 Chi tiết theo PGD")
    df_pgd = TongHopXLRR.tong_hop_theo_pgd(int(nam_dg), thang_dg)
    if df_pgd.empty:
        st.info("ℹ️ Chưa có dữ liệu.")
    else:
        st.dataframe(df_pgd, use_container_width=True, hide_index=True)

    st.markdown("#### 📋 Theo chương trình tín dụng")
    df_ct = TongHopXLRR.tong_hop_theo_chuong_trinh(int(nam_dg), thang_dg)
    if df_ct.empty:
        st.info("ℹ️ Chưa có dữ liệu.")
    else:
        st.dataframe(df_ct, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 6 (CN): NHẬP KẾT QUẢ TỪ NHCSXH TW
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_nhap_ket_qua_cn(ctx: TabContext) -> None:
    """CN nhập kết quả xử lý từ NHCSXH TW và xuất thông báo."""
    from services.xlrr_service import (
        KET_QUA_DA_KHOANH, KET_QUA_DA_XOA,
        KET_QUA_KHONG_DUYET, KET_QUA_CHO_XU_LY, KET_QUA_LABEL,
    )
    from services.word_xln_service import (
        _tao_word_thong_bao_ket_qua_cn,
        _tao_word_thong_bao_ket_qua_pgd,
    )

    st.caption("📬 Nhập kết quả xử lý nợ rủi ro từ NHCSXH TW và xuất thông báo")

    now = datetime.now()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        thang_kq = st.selectbox("Tháng hồ sơ:", list(range(1, 13)), index=now.month - 1, key="xlrr_kq_cn_thang")
    with col_f2:
        nam_kq = st.number_input("Năm:", min_value=2020, max_value=2030, value=now.year, key="xlrr_kq_cn_nam")

    ds_cn = LuuTruXLRR.doc_cn(int(nam_kq), thang_kq)
    if not ds_cn:
        st.info(f"ℹ️ Chưa có hồ sơ CN kỳ T{thang_kq}/{int(nam_kq)}.")
        return

    st.markdown(f"**{len(ds_cn)} hồ sơ cần cập nhật kết quả**")

    # Thông tin QĐ từ TW
    st.markdown("#### 📋 Thông tin Quyết định")
    col_qd1, col_qd2, col_qd3 = st.columns(3)
    with col_qd1:
        so_qd = st.text_input("Số Quyết định:", placeholder="62/QĐ-HĐQT", key="xlrr_kq_cn_so_qd")
    with col_qd2:
        ngay_qd = st.date_input("Ngày QĐ:", value=date.today(), format="DD/MM/YYYY", key="xlrr_kq_cn_ngay_qd")
    with col_qd3:
        dot_kq = st.number_input("Đợt:", min_value=1, max_value=4, value=1, key="xlrr_kq_cn_dot")

    # Bảng nhập kết quả từng hồ sơ
    st.markdown("#### 📝 Cập nhật kết quả từng hồ sơ")
    ket_qua_options = list(KET_QUA_LABEL.values())
    ket_qua_keys = list(KET_QUA_LABEL.keys())

    # Load kết quả đã lưu (nếu có)
    data_cu = LuuTruXLRR.doc_ket_qua(int(nam_kq), thang_kq) or {}
    ds_cu_map = {r["ho_so_id"]: r for r in data_cu.get("ds_ket_qua", [])}

    ds_ket_qua_moi = []
    for hs in ds_cn:
        cu = ds_cu_map.get(hs.id, {})
        kq_idx = ket_qua_keys.index(cu.get("ket_qua", KET_QUA_CHO_XU_LY)) if cu.get("ket_qua") in ket_qua_keys else 3

        with st.expander(f"🔹 {hs.ten_kh} — {hs.ten_pgd} — {hs.so_ku}"):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                kq_sel = st.selectbox(
                    "Kết quả:",
                    ket_qua_options,
                    index=kq_idx,
                    key=f"xlrr_kq_cn_kq_{hs.id}",
                )
                kq_val = ket_qua_keys[ket_qua_options.index(kq_sel)]
            with col_b:
                tien_duyet = st.number_input(
                    "Số tiền duyệt (triệu đ):",
                    min_value=0.0,
                    value=float(cu.get("so_tien_duoc_duyet", hs.tong_du_no or 0)) / 1_000_000,
                    step=0.1,
                    key=f"xlrr_kq_cn_tien_{hs.id}",
                )
            with col_c:
                ghi_chu = st.text_input(
                    "Ghi chú:",
                    value=cu.get("ghi_chu", ""),
                    key=f"xlrr_kq_cn_gc_{hs.id}",
                )

            ds_ket_qua_moi.append({
                "ho_so_id": hs.id,
                "ten_kh": hs.ten_kh,
                "ten_pgd": hs.ten_pgd,
                "so_ku": hs.so_ku,
                "bien_phap": hs.bien_phap,
                "ket_qua": kq_val,
                "so_tien_duoc_duyet": int(tien_duyet * 1_000_000),
                "so_tien_de_nghi": int(hs.tong_du_no or 0),
                "ghi_chu": ghi_chu,
            })

    st.markdown("---")
    col_luu, col_tb_cn, col_tb_pgd = st.columns(3)

    with col_luu:
        if st.button("💾 Lưu kết quả", type="primary", use_container_width=True, key="xlrr_kq_cn_btn_luu"):
            if not so_qd.strip():
                st.error("❌ Vui lòng nhập số Quyết định.")
            else:
                data_luu = {
                    "so_quyet_dinh": so_qd.strip(),
                    "ngay_quyet_dinh": ngay_qd.isoformat(),
                    "dot": int(dot_kq),
                    "nam": int(nam_kq),
                    "thang": thang_kq,
                    "ngay_nhap": datetime.now().isoformat(),
                    "nguoi_nhap": ctx.username,
                    "ds_ket_qua": ds_ket_qua_moi,
                    "ghi_chu_chung": "",
                }
                LuuTruXLRR.luu_ket_qua(data_luu, int(nam_kq), thang_kq, ctx.username)
                st.success(f"✅ Đã lưu kết quả {len(ds_ket_qua_moi)} hồ sơ!")
                st.rerun()

    with col_tb_cn:
        if st.button("📄 Xuất thông báo CN", use_container_width=True, key="xlrr_kq_cn_btn_tb_cn"):
            data_xuat = LuuTruXLRR.doc_ket_qua(int(nam_kq), thang_kq)
            if not data_xuat or not data_xuat.get("ds_ket_qua"):
                st.warning("⚠️ Chưa lưu kết quả. Lưu trước rồi xuất thông báo.")
            else:
                try:
                    file_bytes = _tao_word_thong_bao_ket_qua_cn(
                        data_xuat["ds_ket_qua"],
                        data_xuat.get("so_quyet_dinh", ""),
                        date.fromisoformat(data_xuat.get("ngay_quyet_dinh", date.today().isoformat())),
                        data_xuat.get("dot", 1),
                        int(nam_kq),
                    )
                    st.download_button(
                        label="⬇️ Tải thông báo CN (.docx)",
                        data=file_bytes,
                        file_name=f"ThongBaoKetQua_CN_T{thang_kq:02d}_{int(nam_kq)}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key="xlrr_kq_cn_dl_tb_cn",
                    )
                    db.ghi_audit(ctx.username, "xuat_thong_bao_ket_qua_cn",
                                 f"T{thang_kq}/{int(nam_kq)}")
                    st.success("✅ Xuất thông báo CN thành công!")
                except Exception as e:
                    logger.error("xuat_thong_bao_cn: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất thông báo CN: {e}")

    with col_tb_pgd:
        pgd_list = sorted({r.get("ten_pgd", "") for r in ds_ket_qua_moi if r.get("ten_pgd")})
        if pgd_list:
            ten_pgd_chon = st.selectbox("Chọn PGD xuất thông báo:", pgd_list, key="xlrr_kq_cn_pgd_chon")
            if st.button("📄 Xuất thông báo PGD", use_container_width=True, key="xlrr_kq_cn_btn_tb_pgd"):
                data_xuat = LuuTruXLRR.doc_ket_qua(int(nam_kq), thang_kq)
                if not data_xuat:
                    st.warning("⚠️ Chưa lưu kết quả.")
                else:
                    ds_pgd = [r for r in data_xuat.get("ds_ket_qua", [])
                              if r.get("ten_pgd") == ten_pgd_chon]
                    try:
                        file_bytes = _tao_word_thong_bao_ket_qua_pgd(
                            ds_pgd,
                            ten_pgd_chon,
                            data_xuat.get("so_quyet_dinh", ""),
                            date.fromisoformat(data_xuat.get("ngay_quyet_dinh", date.today().isoformat())),
                            data_xuat.get("dot", 1),
                            int(nam_kq),
                        )
                        st.download_button(
                            label=f"⬇️ Tải thông báo {ten_pgd_chon} (.docx)",
                            data=file_bytes,
                            file_name=f"ThongBaoKetQua_{pgd_slug(ten_pgd_chon)}_T{thang_kq:02d}_{int(nam_kq)}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="xlrr_kq_cn_dl_tb_pgd",
                        )
                        db.ghi_audit(ctx.username, "xuat_thong_bao_ket_qua_pgd",
                                     f"{ten_pgd_chon} T{thang_kq}/{int(nam_kq)}")
                        st.success(f"✅ Xuất thông báo {ten_pgd_chon} thành công!")
                    except Exception as e:
                        logger.error("xuat_thong_bao_pgd: %s", e, exc_info=True)
                        st.error(f"❌ Lỗi xuất thông báo PGD: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 3 (PGD): KẾT QUẢ XLRR
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_ket_qua_pgd(ctx: TabContext) -> None:
    """PGD xem kết quả xử lý nợ rủi ro của PGD mình sau khi CN nhập."""
    from services.xlrr_service import KET_QUA_LABEL
    from services.word_xln_service import _tao_word_thong_bao_ket_qua_pgd

    pgd_user = ctx.pgd_user
    if not pgd_user:
        st.warning("⚠️ Không xác định được PGD của tài khoản.")
        return

    st.caption(f"📬 Kết quả xử lý nợ rủi ro — {pgd_user}")

    now = datetime.now()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        thang_kq = st.selectbox("Tháng:", list(range(1, 13)), index=now.month - 1, key=f"xlrr_kq_pgd_{pgd_slug(pgd_user)}_thang")
    with col_f2:
        nam_kq = st.number_input("Năm:", min_value=2020, max_value=2030, value=now.year, key=f"xlrr_kq_pgd_{pgd_slug(pgd_user)}_nam")

    ds_kq = LuuTruXLRR.doc_ket_qua_pgd(pgd_slug(pgd_user), int(nam_kq), thang_kq)

    if not ds_kq:
        st.info(f"ℹ️ Chưa có kết quả xử lý nào cho {pgd_user} kỳ T{thang_kq}/{int(nam_kq)}.")
        st.caption("CN sẽ cập nhật kết quả sau khi nhận Quyết định từ NHCSXH TW.")
        return

    # Lấy meta QĐ
    data_full = LuuTruXLRR.doc_ket_qua(int(nam_kq), thang_kq) or {}
    so_qd = data_full.get("so_quyet_dinh", "")
    ngay_qd_str = data_full.get("ngay_quyet_dinh", "")
    dot = data_full.get("dot", 1)

    if so_qd:
        st.success(f"✅ Kết quả theo QĐ số **{so_qd}** — Đợt {dot} năm {int(nam_kq)}")

    # Bảng hiển thị kết quả
    rows = []
    for r in ds_kq:
        kq_label = KET_QUA_LABEL.get(r.get("ket_qua", ""), r.get("ket_qua", ""))
        rows.append({
            "Tên KH": r.get("ten_kh", ""),
            "Số KU": r.get("so_ku", ""),
            "Biện pháp": "Khoanh" if r.get("bien_phap") == "khoanh" else "Xóa",
            "Kết quả": kq_label,
            "Tiền duyệt (triệu đ)": fmt_ty(float(r.get("so_tien_duoc_duyet", 0) or 0)),
            "Ghi chú": r.get("ghi_chu", ""),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Nút tải thông báo
    if so_qd and ngay_qd_str:
        st.markdown("---")
        if st.button("📄 Tải Thông báo kết quả (.docx)", use_container_width=True,
                     key=f"xlrr_kq_pgd_{pgd_slug(pgd_user)}_btn_tb"):
            try:
                ngay_qd = date.fromisoformat(ngay_qd_str)
                file_bytes = _tao_word_thong_bao_ket_qua_pgd(
                    ds_kq, pgd_user, so_qd, ngay_qd, dot, int(nam_kq),
                )
                st.download_button(
                    label="⬇️ Tải thông báo (.docx)",
                    data=file_bytes,
                    file_name=f"ThongBaoKetQua_{pgd_slug(pgd_user)}_T{thang_kq:02d}_{int(nam_kq)}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key=f"xlrr_kq_pgd_{pgd_slug(pgd_user)}_dl_tb",
                )
            except Exception as e:
                logger.error("tai_thong_bao_ket_qua: %s", e, exc_info=True)
                st.error(f"❌ Lỗi tải thông báo: {e}")



# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB: QUẢN LÝ ĐỢT XLRR (CN)
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_quan_ly_dot_cn(ctx: TabContext) -> None:
    """CN quản lý đợt XLRR: tạo, sửa, xóa đợt chung toàn Chi nhánh."""
    st.caption("Tạo và quản lý các đợt XLRR chung toàn Chi nhánh")

    now = datetime.now()
    nam = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_dotcn_nam")

    ds_dot = LuuTruDotXLRR.doc_ds(nam, "cn")

    # ── Form tạo đợt mới ──────────────────────────────────────────────────
    with st.expander("➕ Tạo đợt XLRR mới", expanded=len(ds_dot) == 0):
        col1, col2, col3 = st.columns(3)
        with col1:
            ten_dot = st.text_input("Tên đợt", placeholder="VD: Đợt 1/2026", key="xlrr_dotcn_ten")
        with col2:
            ngay_bd = st.date_input("Ngày bắt đầu", value=date.today(), format="DD/MM/YYYY", key="xlrr_dotcn_bd")
        with col3:
            ngay_kt = st.date_input("Ngày kết thúc", value=date.today(), format="DD/MM/YYYY", key="xlrr_dotcn_kt")

        if st.button("✅ Tạo đợt", type="primary", use_container_width=True, key="xlrr_dotcn_tao"):
            if not ten_dot.strip():
                st.error("Vui lòng nhập tên đợt.")
            elif ngay_kt < ngay_bd:
                st.error("Ngày kết thúc phải sau ngày bắt đầu.")
            else:
                dot = LuuTruDotXLRR.tao_dot(
                    ten_dot.strip(), nam, ngay_bd, ngay_kt,
                    ctx.username, "cn",
                )
                st.success(f"Đã tạo đợt: {dot.ten_dot} ({dot.id})")
                st.cache_data.clear()
                st.rerun()

    # ── Danh sách đợt hiện có ─────────────────────────────────────────────
    if not ds_dot:
        st.info("Chưa có đợt XLRR nào trong năm này.")
        return

    st.markdown("---")
    st.markdown("#### 📋 Danh sách đợt XLRR")

    for dot in ds_dot:
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
        with c1:
            st.markdown(f"**{dot.ten_dot}**\n`{dot.id}`")
        with c2:
            st.caption(f"📅 {dot.ngay_bat_dau:%d/%m/%Y} – {dot.ngay_ket_thuc:%d/%m/%Y}")
        with c3:
            st.caption(dot.trang_thai_label)
        with c4:
            if st.button("✏️", key=f"xlrr_dotcn_edit_{dot.id}", help="Sửa đợt này"):
                st.session_state[f"xlrr_dotcn_editing"] = dot.id
                st.rerun()
        with c5:
            with st.popover("🗑️"):
                st.warning(f"Xóa đợt **{dot.ten_dot}**?")
                if st.button("⚠️ Xác nhận xóa", key=f"xlrr_dotcn_del_{dot.id}", type="primary"):
                    if LuuTruDotXLRR.xoa_dot(dot.id, nam, "cn", "", ctx.username):
                        st.toast(f"Đã xóa đợt {dot.ten_dot}", icon="🗑️")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Không thể xóa đợt.")

        # ── Inline edit ──────────────────────────────────────────────────
        edit_id = st.session_state.get("xlrr_dotcn_editing", "")
        if edit_id == dot.id:
            with st.container():
                st.markdown(f"#### ✏️ Sửa đợt: {dot.ten_dot}")
                ec1, ec2, ec3, ec4 = st.columns(4)
                with ec1:
                    ten_moi = st.text_input("Tên đợt", value=dot.ten_dot, key=f"xlrr_dotcn_e_ten_{dot.id}")
                with ec2:
                    bd_moi = st.date_input("Ngày BĐ", value=dot.ngay_bat_dau, format="DD/MM/YYYY", key=f"xlrr_dotcn_e_bd_{dot.id}")
                with ec3:
                    kt_moi = st.date_input("Ngày KT", value=dot.ngay_ket_thuc, format="DD/MM/YYYY", key=f"xlrr_dotcn_e_kt_{dot.id}")
                with ec4:
                    da_gui = st.checkbox("Đã gửi TW", value=dot.da_gui_tw, key=f"xlrr_dotcn_e_gui_{dot.id}")
                bc1, bc2 = st.columns([1, 3])
                with bc1:
                    if st.button("💾 Lưu", type="primary", key=f"xlrr_dotcn_save_{dot.id}"):
                        LuuTruDotXLRR.cap_nhat_dot(
                            dot.id, nam, "cn", "", ctx.username,
                            ten_dot=ten_moi.strip(), ngay_bat_dau=bd_moi,
                            ngay_ket_thuc=kt_moi, da_gui_tw=da_gui,
                        )
                        st.session_state.pop("xlrr_dotcn_editing", None)
                        st.cache_data.clear()
                        st.rerun()
                with bc2:
                    if st.button("Hủy", key=f"xlrr_dotcn_cancel_{dot.id}"):
                        st.session_state.pop("xlrr_dotcn_editing", None)
                        st.rerun()
            st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB: ĐỢT XLRR (PGD)
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_dot_xlrr_pgd(ctx: TabContext) -> None:
    """PGD quản lý đợt XLRR: tạo đợt riêng hoặc copy từ CN."""
    st.caption("Quản lý đợt XLRR của PGD")

    pgd_val = ctx.pgd_user or DON_VI_CHI_NHANH
    slug_val = pgd_slug(pgd_val)
    now = datetime.now()
    nam = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_dotpgd_nam")

    ds_dot_pgd = LuuTruDotXLRR.doc_ds(nam, "pgd", slug_val)
    ds_dot_cn = LuuTruDotXLRR.doc_ds(nam, "cn")

    # ── Tab: Tự tạo hoặc Copy từ CN ───────────────────────────────────────
    t1, t2 = st.tabs(["✏️ Tự tạo đợt", "📋 Copy từ CN"])

    with t1:
        with st.form("xlrr_dotpgd_form_tao"):
            col1, col2, col3 = st.columns(3)
            with col1:
                ten_dot = st.text_input("Tên đợt", placeholder="VD: Đợt 1/2026", key="xlrr_dotpgd_ten")
            with col2:
                ngay_bd = st.date_input("Ngày bắt đầu", value=date.today(), format="DD/MM/YYYY", key="xlrr_dotpgd_bd")
            with col3:
                ngay_kt = st.date_input("Ngày kết thúc", value=date.today(), format="DD/MM/YYYY", key="xlrr_dotpgd_kt")

            if st.form_submit_button("✅ Tạo đợt", type="primary"):
                if not ten_dot.strip():
                    st.error("Vui lòng nhập tên đợt.")
                elif ngay_kt < ngay_bd:
                    st.error("Ngày kết thúc phải sau ngày bắt đầu.")
                else:
                    dot = LuuTruDotXLRR.tao_dot(
                        ten_dot.strip(), nam, ngay_bd, ngay_kt,
                        ctx.username, "pgd", slug_val,
                    )
                    st.success(f"Đã tạo đợt: {dot.ten_dot}")
                    st.cache_data.clear()
                    st.rerun()

    with t2:
        if not ds_dot_cn:
            st.info("CN chưa có đợt nào để copy.")
        else:
            dot_cn_labels = {f"{d.ten_dot} ({d.ngay_bat_dau:%d/%m}–{d.ngay_ket_thuc:%d/%m})": d for d in ds_dot_cn}
            dot_cn_sel = st.selectbox(
                "Chọn đợt của CN để copy", list(dot_cn_labels.keys()),
                key="xlrr_dotpgd_copy_from",
            )
            if st.button("📋 Copy đợt này cho PGD", type="primary", key="xlrr_dotpgd_copy_btn"):
                src = dot_cn_labels[dot_cn_sel]
                dot = LuuTruDotXLRR.tao_dot(
                    f"{src.ten_dot} (copy)", nam,
                    src.ngay_bat_dau, src.ngay_ket_thuc,
                    ctx.username, "pgd", slug_val,
                )
                st.success(f"Đã copy đợt: {dot.ten_dot}")
                st.cache_data.clear()
                st.rerun()

    # ── Danh sách đợt PGD ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📋 Đợt XLRR của PGD")

    if not ds_dot_pgd:
        st.info("PGD chưa có đợt XLRR nào.")
        return

    for dot in ds_dot_pgd:
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1:
            st.markdown(f"**{dot.ten_dot}**\n`{dot.id}`")
        with c2:
            st.caption(f"📅 {dot.ngay_bat_dau:%d/%m/%Y} – {dot.ngay_ket_thuc:%d/%m/%Y}")
        with c3:
            st.caption(dot.trang_thai_label)
        with c4:
            with st.popover("🗑️"):
                st.warning(f"Xóa đợt **{dot.ten_dot}**?")
                if st.button("⚠️ Xác nhận xóa", key=f"xlrr_dotpgd_del_{dot.id}", type="primary"):
                    if LuuTruDotXLRR.xoa_dot(dot.id, nam, "pgd", slug_val, ctx.username):
                        st.toast(f"Đã xóa đợt {dot.ten_dot}", icon="🗑️")
                        st.cache_data.clear()
                        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render(tab=None, **kwargs) -> None:
    """Render tab Xử lý Rủi ro — CN: 5 tabs, PGD: 3 tabs."""
    ctx = TabContext(tab, **kwargs)
    role = ctx.role_norm

    la_cn = la_phan_he_cn(role)
    la_pgd = la_phan_he_pgd(role)

    with ctx:
        st.title("🔴 Xử lý Rủi ro (XLRR)")
        st.caption("Quản lý hồ sơ xử lý nợ rủi ro theo QĐ62/2015/QĐ-TTg")

        if la_cn:
            tab_labels = [
                "📅 Quản lý đợt",
                "🏢 Lập hồ sơ PGD",
                "🔍 Theo dõi QĐ62",
                "🔄 Tổng hợp CN→TW",
                "📊 Dashboard",
                "📬 Thông báo kết quả",
            ]
        elif la_pgd:
            tab_labels = [
                "📅 Đợt XLRR",
                "🏢 Lập hồ sơ",
                "📤 Gửi lên CN",
                "📬 Kết quả XLRR",
            ]
        else:
            st.error("❌ Bạn không có quyền truy cập chức năng này.")
            return

        tabs = st.tabs(tab_labels)
        df = kwargs.get("df", pd.DataFrame())

        if la_cn:
            with tabs[0]:
                _subtab_quan_ly_dot_cn(ctx)
            with tabs[1]:
                _subtab_lap_hs_pgd(df, ctx)
            with tabs[2]:
                _subtab_theo_doi_qd62(ctx)
            with tabs[3]:
                _subtab_tong_hop_cn(ctx)
            with tabs[4]:
                _subtab_dashboard_gd(ctx)
            with tabs[5]:
                _subtab_nhap_ket_qua_cn(ctx)
        elif la_pgd:
            with tabs[0]:
                _subtab_dot_xlrr_pgd(ctx)
            with tabs[1]:
                _subtab_lap_hs_pgd(df, ctx)
            with tabs[2]:
                _subtab_gui_cn_pgd(df, ctx)
            with tabs[3]:
                _subtab_ket_qua_pgd(ctx)


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ══════════════════════════════════════════════════════════════════════════════

__all__ = ["render"]
