"""Tab Xử lý Rủi ro (XLRR) — 5 sub-tabs: Lập hồ sơ PGD, Lập hồ sơ CN, Theo dõi QĐ62, Tổng hợp CN, Báo cáo.
Tích hợp: tab_no_rui_ro.py + tab_qd62.py + tab_xlrr_tong_hop.py
"""
from __future__ import annotations

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
    DS_PGD,
    NGUYEN_NHAN_RR,
)
from data.pgd import pgd_slug
from services.xlrr_service import (
    HoSoRuiRo,
    LuuTruXLRR,
    TongHopXLRR,
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
)
from tabs.base_tab import TabContext
from utils import fmt, fmt_ty, hien_thi_dataframe_phan_trang

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
        ten_pgd = ctx.pgd_user or DS_PGD[0]
    else:
        # CN chọn PGD để lập thay
        ten_pgd = st.selectbox("📍 Chọn PGD để lập hồ sơ", DS_PGD, key="xlrr_pgd_chon_pgd")
    
    pgd_slug_val = pgd_slug(ten_pgd)
    df_pgd = df[df[COT_TEN_PGD] == ten_pgd].copy() if COT_TEN_PGD in df.columns else pd.DataFrame()
    
    if df_pgd.empty:
        st.warning(f"⚠️ Không có dữ liệu HSTD cho {ten_pgd}")
        return
    
    # Bước 1: Lọc hộ vay
    with st.expander("🔎 Bước 1: Lọc hộ vay", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ds_xa = sorted(df_pgd[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df_pgd.columns else []
            chon_xa = st.selectbox("Xã/Phường", [""] + ds_xa, key="xlrr_pgd_xa")
        with c2:
            df_loc = df_pgd[df_pgd[COT_TEN_XA] == chon_xa] if chon_xa and COT_TEN_XA in df_pgd.columns else df_pgd
            ds_to = sorted(df_loc[COT_TEN_TO].dropna().unique().tolist()) if COT_TEN_TO in df_loc.columns else []
            chon_to = st.selectbox("Tổ TK&VV", [""] + ds_to, key="xlrr_pgd_to")
        with c3:
            tim_kh = st.text_input("Tìm tên KH", placeholder="Nhập tên...", key="xlrr_pgd_tim")
    
    # Lọc dữ liệu
    df_hien = df_pgd.copy()
    if chon_xa and COT_TEN_XA in df_hien.columns:
        df_hien = df_hien[df_hien[COT_TEN_XA] == chon_xa]
    if chon_to and COT_TEN_TO in df_hien.columns:
        df_hien = df_hien[df_hien[COT_TEN_TO] == chon_to]
    if tim_kh and COT_TEN_KH in df_hien.columns:
        df_hien = df_hien[df_hien[COT_TEN_KH].str.contains(tim_kh, case=False, na=False)]
    
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
        st.info("👆 Tích chọn ít nhất 1 hộ vay để tiếp tục.")
        return
    
    st.success(f"✅ Đã chọn **{len(ds_chon)}** hộ vay.")
    
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
        
        submitted = st.form_submit_button("💾 Lưu hồ sơ", type="primary")
    
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
                du_no_lai=float(row_full.get(COT_LAI_TON, 0) or 0),
                lai_ton=float(row_full.get(COT_LAI_TON, 0) or 0),
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


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 2: LẬP HỒ SƠ CN (QĐ62)
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_lap_hs_cn(df: pd.DataFrame, ctx: TabContext) -> None:
    """Sub-tab 2: Lập hồ sơ CN (QĐ62 trực tiếp hoặc lập thay PGD)."""
    st.caption("Lập hồ sơ QĐ62 trực tiếp hoặc lập thay cho PGD")
    
    role = ctx.role_norm
    username = ctx.username
    
    # Chọn mode
    mode = st.radio(
        "Chế độ lập hồ sơ",
        ["🏢 Lập QĐ62 trực tiếp (Hội sở/CN)", "🔄 Lập thay cho PGD"],
        horizontal=True,
        key="xlrr_cn_mode",
    )
    
    if mode == "🔄 Lập thay cho PGD":
        # Chuyển sang sub-tab 1 với context CN
        st.info("Chuyển sang tab 'Lập hồ sơ PGD' và chọn PGD từ dropdown.")
        return
    
    # Mode QĐ62 trực tiếp
    st.markdown("#### ➕ Thêm hồ sơ QĐ62 mới")
    
    with st.form("xlrr_cn_form_qd62"):
        col_a, col_b = st.columns(2)
        with col_a:
            ho_ten = st.text_input("Họ tên khách hàng *", placeholder="Nguyễn Văn A", key="xlrr_cn_ho_ten")
            so_cccd = st.text_input("Số CCCD/CMND *", placeholder="0790xxxxxx", key="xlrr_cn_cccd")
            ten_pgd = st.selectbox("Phòng giao dịch *", DS_PGD, key="xlrr_cn_pgd")
        with col_b:
            xa = st.text_input("Xã/Phường *", key="xlrr_cn_xa")
            ten_ct = st.text_input("Chương trình tín dụng", key="xlrr_cn_ct")
            du_no_goc = st.number_input("Dư nợ gốc (triệu đồng) *", min_value=0.0, step=0.1, format="%.1f", key="xlrr_cn_goc")
            du_no_lai = st.number_input("Dư nợ lãi (triệu đồng)", min_value=0.0, step=0.1, format="%.1f", key="xlrr_cn_lai")
        
        ly_do = st.selectbox("Lý do rủi ro *", NGUYEN_NHAN_RR, key="xlrr_cn_ly_do")
        ghi_chu = st.text_area("Ghi chú", height=80, key="xlrr_cn_ghi_chu")
        
        submitted = st.form_submit_button("💾 Lưu hồ sơ QĐ62", type="primary")
    
    if submitted:
        # Validate
        errs = []
        if not ho_ten.strip():
            errs.append("Họ tên")
        if not so_cccd.strip():
            errs.append("Số CCCD")
        if not xa.strip():
            errs.append("Xã/Phường")
        if du_no_goc <= 0:
            errs.append("Dư nợ gốc phải > 0")
        
        if errs:
            st.error(f"⚠️ Vui lòng nhập: {', '.join(errs)}")
            return
        
        # Tạo hồ sơ
        now = datetime.now()
        hs = HoSoRuiRo(
            id=str(uuid.uuid4()),
            ma_kh=so_cccd,
            ten_kh=ho_ten.strip(),
            so_ku="",
            xa=xa.strip(),
            ten_pgd=ten_pgd,
            pgd_slug=pgd_slug(ten_pgd),
            ten_ct=ten_ct or "QĐ62",
            du_no_goc=int(du_no_goc * 1_000_000),
            du_no_lai=int(du_no_lai * 1_000_000),
            nguyen_nhan=ly_do,
            ghi_chu=ghi_chu.strip(),
            loai_ho_so=LOAI_HO_SO_QD62,
            trang_thai=TRANG_THAI_CHO_DUYET,
            so_cccd=so_cccd.strip(),
            ly_do=ly_do,
            nguoi_tao=username,
            ngay_tao=now,
        )
        
        # Lưu
        LuuTruXLRR.luu_qd62([hs], now.year, now.month, username)
        
        st.cache_data.clear()
        st.success(f"✅ Đã thêm hồ sơ QĐ62: {ho_ten.strip()}")
        st.rerun()
    
    # Hiển thị danh sách QĐ62 đã lập
    st.markdown("#### 📋 Hồ sơ QĐ62 đã lập trong kỳ")
    now = datetime.now()
    ds_qd62 = LuuTruXLRR.doc_qd62(now.year, now.month)
    
    if not ds_qd62:
        st.info("ℹ️ Chưa có hồ sơ QĐ62 nào trong kỳ này.")
    else:
        df_qd62 = pd.DataFrame([{
            "Họ tên": hs.ten_kh,
            "Xã": hs.xa,
            "PGD": hs.ten_pgd,
            "Dư nợ gốc": fmt_ty(hs.du_no_goc),
            "Lý do": hs.ly_do,
            "Trạng thái": TRANG_THAI_BADGE.get(hs.trang_thai, hs.trang_thai),
        } for hs in ds_qd62])
        
        st.dataframe(df_qd62, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 3: THEO DÕI QĐ62
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_theo_doi_qd62(ctx: TabContext) -> None:
    """Sub-tab 3: Theo dõi và quản lý trạng thái hồ sơ QĐ62."""
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
# SUB-TAB 4: TỔNG HỢP TOÀN CN
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_tong_hop_cn(ctx: TabContext) -> None:
    """Sub-tab 4: Tổng hợp toàn Chi nhánh."""
    st.caption("Tổng hợp hồ sơ xử lý rủi ro toàn Chi nhánh Đồng Nai")
    
    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        now = datetime.now()
        thang = st.selectbox("Tháng", list(range(1, 13)), index=now.month - 1, key="xlrr_th_thang")
    with col_f2:
        nam = st.number_input("Năm", min_value=2020, max_value=2030, value=now.year, key="xlrr_th_nam")
    
    # Metrics
    metrics = TongHopXLRR.tong_hop_toan_cn(int(nam), thang)
    
    st.markdown("#### 📊 Tổng quan")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Tổng hồ sơ", metrics["tong_ho_so"])
    c2.metric("PGD có hồ sơ", metrics["so_pgd_co_hs"])
    c3.metric("Khoanh nợ", metrics["so_khoanh"])
    c4.metric("Xóa nợ", metrics["so_xoa"])
    c5.metric("TW", fmt_ty(metrics["tw_tien"]))
    c6.metric("ĐP", fmt_ty(metrics["dp_tien"]))
    
    # Bảng tổng hợp theo PGD
    st.markdown("#### 🏢 Chi tiết theo PGD")
    df_pgd = TongHopXLRR.tong_hop_theo_pgd(int(nam), thang)
    if df_pgd.empty:
        st.info("ℹ️ Chưa có dữ liệu.")
    else:
        st.dataframe(df_pgd, use_container_width=True, hide_index=True)
    
    # Bảng tổng hợp theo chương trình
    st.markdown("#### 📋 Theo chương trình tín dụng")
    df_ct = TongHopXLRR.tong_hop_theo_chuong_trinh(int(nam), thang)
    if df_ct.empty:
        st.info("ℹ️ Chưa có dữ liệu.")
    else:
        st.dataframe(df_ct, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB 5: BÁO CÁO & IN ẤN
# ══════════════════════════════════════════════════════════════════════════════

def _subtab_bao_cao(df: pd.DataFrame, ctx: TabContext) -> None:
    """Sub-tab 5: Xuất biểu mẫu 01/XLN và 02/XLN."""
    st.caption("📄 Xuất biểu mẫu Đơn đề nghị (01/XLN) và Biên bản (02/XLN)")

    # Lấy dữ liệu hồ sơ
    role = ctx.role_norm
    pgd_user = ctx.pgd_user

    # ── Chọn kỳ xuất biểu ─────────────────────────────────────────────
    now = datetime.now()
    col_ky1, col_ky2 = st.columns(2)
    with col_ky1:
        thang_xuat = st.selectbox(
            "Tháng",
            list(range(1, 13)),
            index=now.month - 1,
            key="xlrr_bc_thang",
        )
    with col_ky2:
        nam_xuat = st.number_input(
            "Năm",
            min_value=2020,
            max_value=2030,
            value=now.year,
            step=1,
            key="xlrr_bc_nam",
        )

    # ── Load hồ sơ từ kv_store theo kỳ đã chọn ────────────────────────
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
        st.info(
            f"ℹ️ Chưa có hồ sơ nào trong kỳ T{thang_xuat}/{int(nam_xuat)} để xuất biểu mẫu."
        )
        return

    # ── Chọn hồ sơ (dùng id làm key để tránh trùng label) ────────────
    st.markdown("**📋 Chọn hồ sơ xuất biểu mẫu**")
    hs_map = {hs.id: hs for hs in ds_hs}
    hs_labels = {
        hs.id: f"{hs.ten_kh} — {hs.ten_pgd} — KU: {hs.so_ku or 'N/A'}"
        for hs in ds_hs
    }
    selected_id = st.selectbox(
        "Chọn hồ sơ:",
        options=list(hs_map.keys()),
        format_func=lambda x: hs_labels.get(x, x),
        key="xlrr_bc_select_hs",
    )

    if not selected_id:
        return

    hs = hs_map[selected_id]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📝 Mẫu 01/XLN — Đơn đề nghị**")
        
        # Form nhập thông tin bổ sung cho 01
        with st.form("form_01xln"):
            ngay_ky = st.date_input("Ngày ký đơn:", value=date.today(), format="DD/MM/YYYY", key="xlrr_01_ngay")
            ma_to = st.text_input("Mã Tổ TK&VV:", value=getattr(hs, 'ma_to', ''), key="xlrr_01_ma_to")
            ten_to_truong = st.text_input("Tổ trưởng:", value=getattr(hs, 'ten_to_truong', ''), key="xlrr_01_to_truong")
            nguyen_nhan = st.text_area("Nguyên nhân rủi ro:", value=getattr(hs, 'nguyen_nhan', ''), key="xlrr_01_nguyen_nhan")
            so_tien_thiet_hai = st.text_input("Số tiền thiệt hại:", value="0", key="xlrr_01_thiet_hai")
            muc_do_thiet_hai = st.text_input("Mức độ thiệt hại (%):", value="0", key="xlrr_01_muc_do")
            kha_nang_tra_no = st.text_area("Khả năng trả nợ:", value=getattr(hs, 'kha_nang_tra_no', ''), key="xlrr_01_kha_nang")
            bien_phap = st.selectbox("Biện pháp:", ["khoanh nợ", "xóa nợ"], key="xlrr_01_bien_phap")
            so_thang = st.number_input("Số tháng đề nghị:", min_value=0, value=getattr(hs, 'so_thang', 36), key="xlrr_01_thang")
            ke_hoach_tra_no = st.text_input("Kế hoạch trả nợ:", value="", key="xlrr_01_ke_hoach")
            
            submit_01 = st.form_submit_button("📄 Xuất 01/XLN", use_container_width=True)
        
        if submit_01:
            # Chuẩn bị dữ liệu
            du_lieu_01 = {
                "ten_nhcsxh": getattr(hs, 'ten_pgd', ''),
                "dia_danh": "TP. Biên Hòa",
                "ngay_ky": ngay_ky,
                "ten_kh": hs.ten_kh,
                "dia_chi": getattr(hs, 'dia_chi', ''),
                "ma_to": ma_to,
                "ten_to_truong": ten_to_truong,
                "so_ku": hs.so_ku,
                "ngay_vay": getattr(hs, 'ngay_vay', date.today()),
                "ten_ct": getattr(hs, 'ten_ct', ''),
                "muc_vay": f"{getattr(hs, 'muc_vay', 0):,.0f}".replace(",", "."),
                "ngay_dh": getattr(hs, 'ngay_dh', ''),
                "muc_dich_vay": getattr(hs, 'muc_dich_vay', ''),
                "tong_du_no": f"{hs.tong_du_no:,.0f}".replace(",", ".") if hs.tong_du_no else "0",
                "du_no_goc": f"{getattr(hs, 'du_no_goc', 0):,.0f}".replace(",", "."),
                "lai_ton": f"{getattr(hs, 'lai_ton', 0):,.0f}".replace(",", "."),
                "nguyen_nhan": nguyen_nhan,
                "so_tien_thiet_hai": so_tien_thiet_hai,
                "muc_do_thiet_hai": muc_do_thiet_hai,
                "kha_nang_tra_no": kha_nang_tra_no,
                "bien_phap": bien_phap,
                "so_tien_de_nghi": f"{hs.tong_du_no:,.0f}".replace(",", ".") if hs.tong_du_no else "0",
                "so_thang": int(so_thang),
                "ke_hoach_tra_no": ke_hoach_tra_no,
            }
            
            try:
                file_bytes = _tao_word_01xln_v2(du_lieu_01)
                st.download_button(
                    label="⬇️ Tải 01/XLN (.docx)",
                    data=file_bytes,
                    file_name=f"01XLN_{hs.ma_kh}_{ngay_ky.strftime('%Y%m%d')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
                db.ghi_audit(ctx.username, "xuat_01xln", f"Mã KH: {hs.ma_kh}, Số KU: {hs.so_ku}")
                st.success("✅ Đã xuất 01/XLN thành công!")
            except Exception as e:
                st.error(f"❌ Lỗi xuất 01/XLN: {e}")
    
    with col2:
        st.markdown("**📋 Mẫu 02/XLN — Biên bản**")
        
        # Form nhập thông tin bổ sung cho 02
        with st.form("form_02xln"):
            ngay_lap = st.date_input("Ngày lập biên bản:", value=date.today(), format="DD/MM/YYYY", key="xlrr_02_ngay")
            dia_diem = st.text_input("Địa điểm:", value="", key="xlrr_02_dia_diem")
            
            st.markdown("**Thành phần tham dự:**")
            ten_pgd = st.text_input("Phó GĐ NHCSXH:", key="xlrr_02_pgd")
            ten_ubnd = st.text_input("Phó Chủ tịch UBND:", key="xlrr_02_ubnd")
            ten_hoi_nd = st.text_input("Chủ tịch Hội ND:", key="xlrr_02_hoi_nd")
            ten_cbtd = st.text_input("CBTD NHCSXH:", key="xlrr_02_cbtd")
            ten_to_truong_02 = st.text_input("Tổ trưởng TK&VV:", value=getattr(hs, 'ten_to_truong', ''), key="xlrr_02_to_truong")
            
            st.markdown("**Nội dung biên bản:**")
            nguyen_nhan_02 = st.text_area("Nguyên nhân rủi ro:", value=getattr(hs, 'nguyen_nhan', ''), key="xlrr_02_nguyen_nhan")
            chi_tiet_thiet_hai = st.text_input("Chi tiết thiệt hại:", value="", key="xlrr_02_chi_tiet_th")
            danh_gia_thiet_hai = st.text_input("Đánh giá thiệt hại:", value="", key="xlrr_02_dg_th")
            danh_gia_du_an = st.text_area("Đánh giá dự án:", value="", key="xlrr_02_dg_du_an")
            tai_san_hien_tai = st.text_input("Tài sản hiện tại:", value="", key="xlrr_02_ts")
            kha_nang_tra_no_02 = st.text_area("Khả năng trả nợ:", value=getattr(hs, 'kha_nang_tra_no', ''), key="xlrr_02_kha_nang")
            bien_phap_02 = st.selectbox("Biện pháp đề nghị:", ["khoanh nợ", "xóa nợ"], key="xlrr_02_bien_phap")
            so_thang_02 = st.number_input("Số tháng:", min_value=0, value=getattr(hs, 'so_thang', 36), key="xlrr_02_thang")
            
            submit_02 = st.form_submit_button("📄 Xuất 02/XLN", use_container_width=True)
        
        if submit_02:
            # Chuẩn bị dữ liệu
            du_lieu_02 = {
                "ten_nhcsxh": getattr(hs, 'ten_pgd', ''),
                "dia_danh": "TP. Biên Hòa",
                "ngay_lap": ngay_lap,
                "dia_diem": dia_diem,
                "ten_pgd": ten_pgd,
                "ten_ubnd": ten_ubnd,
                "ten_hoi_nd": ten_hoi_nd,
                "ten_cbtd": ten_cbtd,
                "ten_to_truong": ten_to_truong_02,
                "ten_kh": hs.ten_kh,
                "dia_chi": getattr(hs, 'dia_chi', ''),
                "so_ku": hs.so_ku,
                "ngay_vay": getattr(hs, 'ngay_vay', date.today()),
                "ten_ct": getattr(hs, 'ten_ct', ''),
                "ma_mon_vay": getattr(hs, 'ma_mon_vay', ''),
                "muc_vay": f"{getattr(hs, 'muc_vay', 0):,.0f}".replace(",", "."),
                "tong_du_no": f"{hs.tong_du_no:,.0f}".replace(",", ".") if hs.tong_du_no else "0",
                "du_no_goc": f"{getattr(hs, 'du_no_goc', 0):,.0f}".replace(",", "."),
                "lai_ton": f"{getattr(hs, 'lai_ton', 0):,.0f}".replace(",", "."),
                "nguyen_nhan": nguyen_nhan_02,
                "so_tien_thiet_hai": f"{getattr(hs, 'so_tien_thiet_hai', 0):,.0f}".replace(",", "."),
                "chi_tiet_thiet_hai": chi_tiet_thiet_hai,
                "danh_gia_thiet_hai": danh_gia_thiet_hai,
                "danh_gia_du_an": danh_gia_du_an,
                "tai_san_hien_tai": tai_san_hien_tai,
                "kha_nang_tra_no": kha_nang_tra_no_02,
                "bien_phap_thu_hoi": "",
                "bien_phap": bien_phap_02,
                "so_thang": int(so_thang_02),
                "so_tien_de_nghi": f"{hs.tong_du_no:,.0f}".replace(",", ".") if hs.tong_du_no else "0",
            }
            
            try:
                file_bytes = _tao_word_02xln_v2(du_lieu_02)
                st.download_button(
                    label="⬇️ Tải 02/XLN (.docx)",
                    data=file_bytes,
                    file_name=f"02XLN_{hs.ma_kh}_{ngay_lap.strftime('%Y%m%d')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
                db.ghi_audit(ctx.username, "xuat_02xln", f"Mã KH: {hs.ma_kh}, Số KU: {hs.so_ku}")
                st.success("✅ Đã xuất 02/XLN thành công!")
            except Exception as e:
                st.error(f"❌ Lỗi xuất 02/XLN: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render(tab=None, **kwargs) -> None:
    """Render tab Xử lý Rủi ro với 5 sub-tabs."""
    ctx = TabContext(tab, **kwargs)
    role = ctx.role_norm
    
    # Xác định quyền truy cập
    la_cn = la_phan_he_cn(role)
    la_pgd = la_phan_he_pgd(role)
    
    with ctx:
        st.title("🔴 Xử lý Rủi ro (XLRR)")
        st.caption("Quản lý hồ sơ xử lý nợ rủi ro theo QĐ62/2015/QĐ-TTg")
        
        # Xác định sub-tabs hiển thị dựa trên quyền
        if la_cn:
            tab_labels = [
                "📝 Lập hồ sơ PGD",
                "🏢 Lập hồ sơ CN",
                "📋 Theo dõi QĐ62",
                "📊 Tổng hợp CN",
                "📄 Báo cáo",
            ]
        elif la_pgd:
            tab_labels = [
                "📝 Lập hồ sơ PGD",
                "📄 Báo cáo",
            ]
        else:
            st.error("❌ Bạn không có quyền truy cập chức năng này.")
            return
        
        # Render tabs
        tabs = st.tabs(tab_labels)
        
        # Lấy DataFrame từ context
        df = kwargs.get("df", pd.DataFrame())
        
        if la_cn:
            with tabs[0]:
                _subtab_lap_hs_pgd(df, ctx)
            with tabs[1]:
                _subtab_lap_hs_cn(df, ctx)
            with tabs[2]:
                _subtab_theo_doi_qd62(ctx)
            with tabs[3]:
                _subtab_tong_hop_cn(ctx)
            with tabs[4]:
                _subtab_bao_cao(df, ctx)
        elif la_pgd:
            with tabs[0]:
                _subtab_lap_hs_pgd(df, ctx)
            with tabs[1]:
                _subtab_bao_cao(df, ctx)


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ══════════════════════════════════════════════════════════════════════════════

__all__ = ["render"]
