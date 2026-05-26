"""Tab Quản lý Công văn — ROADMAP §2.4

Tìm kiếm full-text, thêm/sửa/xóa, gắn tag & phân loại, xuất Excel.
"""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from logger import get_logger
from tabs.base_tab import TabContext
from services.cong_van_service import (
    LOAI_CONG_VAN, TRANG_THAI_CV, TAG_GOP_Y,
    them_cv, cap_nhat_cv, xoa_cv, doc_cv, tim_kiem_cv,
    thong_ke_cv_theo_loai, thong_ke_cv_theo_trang_thai,
    xuat_danh_sach_cv, ds_cv_sap_den_han,
)

logger = get_logger(__name__)


def _form_them_cv(username: str) -> None:
    """Form thêm công văn mới."""
    st.markdown("#### ➕ Thêm công văn mới")
    with st.form("cv_form_them", border=True):
        col1, col2 = st.columns(2)
        with col1:
            so_hieu = st.text_input("Số hiệu *", placeholder="VD: 123/QĐ-NHCS", key="cv_f_so")
            ngay_bh = st.date_input("Ngày ban hành *", value=date.today(), format="DD/MM/YYYY", key="cv_f_ngay_bh")
            loai = st.selectbox("Loại *", options=list(LOAI_CONG_VAN.keys()), format_func=lambda x: LOAI_CONG_VAN[x], key="cv_f_loai")
            tag = st.multiselect("Tag", options=TAG_GOP_Y, key="cv_f_tag")
            file_upload = st.file_uploader("File đính kèm", type=["pdf", "docx", "xlsx"], key="cv_f_file")
        with col2:
            trich_yeu = st.text_area("Trích yếu *", placeholder="Nội dung trích yếu...", height=80, key="cv_f_trich_yeu")
            ngay_nhan = st.date_input("Ngày nhận *", value=date.today(), format="DD/MM/YYYY", key="cv_f_ngay_nhan")
            co_quan = st.text_input("Cơ quan ban hành", placeholder="VD: NHCSXH TW", key="cv_f_coquan")
            nguoi_ky = st.text_input("Người ký", key="cv_f_nguoi_ky")
        noi_dung = st.text_area("Nội dung tóm tắt", height=60, key="cv_f_noi_dung")
        trang_thai = st.selectbox("Trạng thái", options=list(TRANG_THAI_CV.keys()), format_func=lambda x: TRANG_THAI_CV[x], key="cv_f_tt")

        if st.form_submit_button("💾 Lưu công văn", type="primary", use_container_width=True):
            if not so_hieu.strip() or not trich_yeu.strip():
                st.error("⚠️ Số hiệu và Trích yếu là bắt buộc.")
                return
            file_path = ""
            if file_upload:
                import os
                upload_dir = os.path.join("cache", "cong_van")
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, f"{so_hieu.replace('/', '_')}_{file_upload.name}")
                with open(file_path, "wb") as f:
                    f.write(file_upload.getvalue())

            them_cv(
                so_hieu=so_hieu.strip(),
                trich_yeu=trich_yeu.strip(),
                ngay_ban_hanh=ngay_bh.isoformat(),
                ngay_nhan=ngay_nhan.isoformat(),
                loai=loai,
                co_quan=co_quan.strip(),
                nguoi_ky=nguoi_ky.strip(),
                tag=", ".join(tag),
                noi_dung=noi_dung.strip(),
                file_path=file_path,
                trang_thai=trang_thai,
                username=username,
            )
            st.toast(f"✅ Đã thêm công văn '{so_hieu}'", icon="📋")
            st.rerun()


def _hien_thi_bang_cv(ds: list[dict], username: str) -> None:
    """Hiển thị bảng danh sách công văn với nút sửa/xóa."""
    if not ds:
        st.info("ℹ️ Không tìm thấy công văn nào.")
        return

    for cv in ds:
        with st.container():
            c1, c2, c3, c4 = st.columns([5, 1.5, 0.6, 0.6])
            loai_icon = LOAI_CONG_VAN.get(cv.get("loai", ""), "📋")
            with c1:
                tag_html = ""
                if cv.get("tag"):
                    tags = [t.strip() for t in cv.get("tag", "").split(",") if t.strip()]
                    tag_spans = " ".join(
                        f'<span style="background:#E8F5E9;color:#2E7D32;padding:1px 6px;border-radius:4px;font-size:11px;margin-right:4px">{t}</span>'
                        for t in tags[:5]
                    )
                    tag_html = f'<div style="margin-top:2px">{tag_spans}</div>'
                st.markdown(
                    f"**{loai_icon} {cv.get('so_hieu', '')}**"
                    f" — {cv.get('trich_yeu', '')[:80]}"
                    f"{tag_html}",
                    unsafe_allow_html=True,
                )
            with c2:
                ngay_bh = (cv.get("ngay_ban_hanh", "") or "")[:10]
                st.caption(f"📅 BH: {ngay_bh}")
                tt_label = TRANG_THAI_CV.get(cv.get("trang_thai", ""), cv.get("trang_thai", ""))
                st.caption(tt_label)
            with c3:
                if st.button("✏️", key=f"cv_edit_{cv['id']}", help="Sửa"):
                    st.session_state["cv_edit_id"] = cv["id"]
                    st.rerun()
            with c4:
                with st.popover("🗑️"):
                    st.warning(f"Xóa công văn **{cv.get('so_hieu', '')}**?")
                    if st.button("⚠️ Xác nhận xóa", key=f"cv_del_ok_{cv['id']}", type="primary"):
                        xoa_cv(cv["id"], username)
                        st.toast(f"🗑️ Đã xóa công văn {cv.get('so_hieu', '')}", icon="🗑️")
                        st.rerun()


def _form_sua_cv(username: str) -> None:
    """Form sửa công văn."""
    edit_id = st.session_state.get("cv_edit_id")
    if not edit_id:
        return
    cv = doc_cv(edit_id)
    if not cv:
        st.session_state.pop("cv_edit_id", None)
        return

    st.markdown(f"#### ✏️ Sửa công văn: **{cv.get('so_hieu', '')}**")
    with st.form(f"cv_form_sua_{edit_id}", border=True):
        col1, col2 = st.columns(2)
        with col1:
            so_hieu = st.text_input("Số hiệu *", value=cv.get("so_hieu", ""), key=f"cv_s_so_{edit_id}")
            ngay_bh_raw = cv.get("ngay_ban_hanh", "")
            try:
                ngay_bh_def = date.fromisoformat(ngay_bh_raw[:10])
            except Exception:
                ngay_bh_def = date.today()
            ngay_bh = st.date_input("Ngày ban hành *", value=ngay_bh_def, format="DD/MM/YYYY", key=f"cv_s_ngay_bh_{edit_id}")
            loai_idx = list(LOAI_CONG_VAN.keys()).index(cv.get("loai", "cong_van"))
            loai = st.selectbox("Loại *", options=list(LOAI_CONG_VAN.keys()), format_func=lambda x: LOAI_CONG_VAN[x], index=loai_idx, key=f"cv_s_loai_{edit_id}")
            tag_cur = [t.strip() for t in cv.get("tag", "").split(",") if t.strip()]
            tag = st.multiselect("Tag", options=TAG_GOP_Y, default=tag_cur, key=f"cv_s_tag_{edit_id}")
        with col2:
            trich_yeu = st.text_area("Trích yếu *", value=cv.get("trich_yeu", ""), height=80, key=f"cv_s_ty_{edit_id}")
            ngay_nhan_raw = cv.get("ngay_nhan", "")
            try:
                ngay_nhan_def = date.fromisoformat(ngay_nhan_raw[:10])
            except Exception:
                ngay_nhan_def = date.today()
            ngay_nhan = st.date_input("Ngày nhận *", value=ngay_nhan_def, format="DD/MM/YYYY", key=f"cv_s_nn_{edit_id}")
            co_quan = st.text_input("Cơ quan ban hành", value=cv.get("co_quan_ban_hanh", ""), key=f"cv_s_cq_{edit_id}")
            nguoi_ky = st.text_input("Người ký", value=cv.get("nguoi_ky", ""), key=f"cv_s_nk_{edit_id}")
        noi_dung = st.text_area("Nội dung tóm tắt", value=cv.get("noi_dung_tom_tat", ""), height=60, key=f"cv_s_nd_{edit_id}")
        tt_idx = list(TRANG_THAI_CV.keys()).index(cv.get("trang_thai", "chua_xu_ly"))
        trang_thai = st.selectbox("Trạng thái", options=list(TRANG_THAI_CV.keys()), format_func=lambda x: TRANG_THAI_CV[x], index=tt_idx, key=f"cv_s_tt_{edit_id}")

        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.form_submit_button("💾 Cập nhật", type="primary", use_container_width=True):
                cap_nhat_cv(
                    edit_id, so_hieu=so_hieu.strip(), trich_yeu=trich_yeu.strip(),
                    ngay_ban_hanh=ngay_bh.isoformat(), ngay_nhan=ngay_nhan.isoformat(),
                    loai=loai, co_quan=co_quan.strip(), nguoi_ky=nguoi_ky.strip(),
                    tag=", ".join(tag), noi_dung=noi_dung.strip(), trang_thai=trang_thai,
                    username=username,
                )
                st.session_state.pop("cv_edit_id", None)
                st.toast(f"✅ Đã cập nhật công văn", icon="✏️")
                st.rerun()
        with col_cancel:
            if st.form_submit_button("↩️ Hủy", type="secondary", use_container_width=True):
                st.session_state.pop("cv_edit_id", None)
                st.rerun()


def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    username = ctx.username

    with ctx:
        st.title("📋 Quản lý Công văn")
        st.caption("Tìm kiếm full-text, thêm/sửa/xóa, gắn tag & phân loại công văn đến/đi")

        # ── KPI row ──
        df_loai = thong_ke_cv_theo_loai()
        df_tt = thong_ke_cv_theo_trang_thai()
        tong_cv = df_loai["so_luong"].sum() if not df_loai.empty else 0
        chua_xl = int(df_tt[df_tt["trang_thai"] == "chua_xu_ly"]["so_luong"].sum()) if not df_tt.empty else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("📋 Tổng công văn", tong_cv)
        c2.metric("⏳ Chưa xử lý", chua_xl)

        ds_tre = ds_cv_sap_den_han()
        c3.metric("⚠️ Quá hạn 7 ngày", len(ds_tre))

        # ── Sub-tabs ──
        t1, t2, t3 = st.tabs(["🔍 Tìm kiếm & Danh sách", "➕ Thêm mới", "📤 Xuất Excel"])

        with t1:
            st.markdown("#### 🔍 Tìm kiếm công văn")
            col_kw, col_loai, col_tag, col_tt = st.columns(4)
            with col_kw:
                keyword = st.text_input("Từ khóa (số hiệu, trích yếu, nội dung...)", key="cv_kw")
            with col_loai:
                loai_filter = st.selectbox("Loại", ["Tất cả"] + list(LOAI_CONG_VAN.keys()),
                                           format_func=lambda x: "Tất cả" if x == "Tất cả" else LOAI_CONG_VAN.get(x, x), key="cv_f_loai_filter")
            with col_tag:
                tag_filter = st.selectbox("Tag", ["Tất cả"] + TAG_GOP_Y, key="cv_f_tag_filter")
            with col_tt:
                tt_filter = st.selectbox("Trạng thái", ["Tất cả"] + list(TRANG_THAI_CV.keys()),
                                         format_func=lambda x: "Tất cả" if x == "Tất cả" else TRANG_THAI_CV.get(x, x), key="cv_f_tt_filter")

            ds = tim_kiem_cv(
                keyword=keyword,
                loai=None if loai_filter == "Tất cả" else loai_filter,
                tag=None if tag_filter == "Tất cả" else tag_filter,
                trang_thai=None if tt_filter == "Tất cả" else tt_filter,
            )

            # Sửa inline
            if st.session_state.get("cv_edit_id"):
                _form_sua_cv(username)
                st.divider()

            st.caption(f"Tìm thấy **{len(ds)}** công văn")
            _hien_thi_bang_cv(ds, username)

        with t2:
            _form_them_cv(username)

        with t3:
            st.markdown("#### 📤 Xuất danh sách công văn")
            st.caption("Xuất Excel với bộ lọc hiện tại")
            if st.button("📥 Xuất Excel", type="primary", use_container_width=True, key="cv_xuat_excel"):
                try:
                    data = xuat_danh_sach_cv(
                        keyword=keyword if 'keyword' in dir() else "",
                        loai=None if loai_filter == "Tất cả" else loai_filter if 'loai_filter' in dir() else None,
                        tag=None if tag_filter == "Tất cả" else tag_filter if 'tag_filter' in dir() else None,
                        trang_thai=None if tt_filter == "Tất cả" else tt_filter if 'tt_filter' in dir() else None,
                    )
                    st.download_button(
                        "⬇️ Tải Excel",
                        data=data,
                        file_name=f"DanhSach_CongVan_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="cv_dl_excel",
                    )
                except Exception as e:
                    logger.error("xuat_excel_cv: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất Excel: {e}")


__all__ = ["render"]
