"""Tab Xử lý Rủi ro (XLRR) — CN: 6 sub-tabs, PGD: 4 sub-tabs.
Tích hợp: tab_no_rui_ro.py + tab_qd62.py + tab_xlrr_tong_hop.py (đã archive)
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

import db
from auth import la_phan_he_cn, la_phan_he_pgd
from config import (
    DON_VI_CHI_NHANH,  # Để có đủ 22 đơn vị trong dropdown
    DS_PGD,
)
from data.pgd import pgd_slug
from services.xlrr_service import (
    LuuTruXLRR,
    TongHopXLRR,
    LuuTruDotXLRR,
    TRANG_THAI_CHO_DUYET,
    TRANG_THAI_DA_DUYET,
    TRANG_THAI_TU_CHOI,
)
from services.xlrr_subtabs import (
    TRANG_THAI_BADGE,
    _subtab_gui_cn_pgd,
    _subtab_lap_hs_pgd,
    _subtab_tong_hop_cn,
)
from tabs.base_tab import TabContext
from utils import fmt_ty
from logger import get_logger

logger = get_logger(__name__)


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
