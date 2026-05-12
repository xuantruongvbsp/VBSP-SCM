"""Xử lý nợ rủi ro theo QĐ 62/2015/QĐ-TTg — 5 bước: lọc, chọn, nhập, xuất, xem lại."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from config import (
    COT_TEN_XA,
    COT_TEN_TO,
    COT_TEN_KH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_TEN_PGD,
    NGUYEN_NHAN_RR,
)
from data.pgd import pgd_slug
from utils import fmt, fmt_bang_ty
from services.template_service import (
    co_template,
    dien_template,
    nut_tai_word_va_pdf,
    hien_thi_nut_tai,
    TMPL_13XLN,
    TMPL_14XLN,
    TMPL_TT_KHOANH,
    TMPL_TT_XOA,
)


def _lay_pgd_tu_user(role: str, pgd_user: str | None, df: pd.DataFrame) -> str | None:
    if pgd_user:
        return pgd_user
    if role in ("admin", "manager", "admin_cn", "manager_cn", "executive") and df is not None and COT_TEN_PGD in df.columns:
        ds = df[COT_TEN_PGD].dropna().unique().tolist()
        if len(ds) == 1:
            return str(ds[0])
    return None


def _loc_df_theo_pgd(df: pd.DataFrame, role: str, pgd_user: str | None) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if role in ("user_pgd", "admin_pgd", "manager_pgd", "user") and pgd_user and COT_TEN_PGD in df.columns:
        return df[df[COT_TEN_PGD] == pgd_user].copy()
    return df


def _tao_kv_key(ten_pgd: str) -> str:
    now = datetime.now()
    return f"no_rui_ro_{pgd_slug(ten_pgd)}_{now.year}_{now.month:02d}"


def _hien_thi_chi_tiet(ds: list[dict]) -> None:
    if not ds:
        st.info("ℹ️ Chưa có hồ sơ nào.")
        return
    df_xem = pd.DataFrame(ds)
    cols_xem = [c for c in [
        "ten_kh", "so_ku", "ten_ct", "du_no", "bien_phap",
        "nguyen_nhan", "muc_do", "so_thang", "ngay_rr", "ghi_chu",
    ] if c in df_xem.columns]
    if "du_no" in df_xem.columns:
        df_xem["du_no"] = df_xem["du_no"].apply(lambda x: fmt(x) if pd.notna(x) else "")
    st.dataframe(df_xem[cols_xem], use_container_width=True, hide_index=True)


def render(tab: DeltaGenerator, **kwargs) -> None:
    df = kwargs.get("df")
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("💳 Xử lý nợ rủi ro — QĐ 62/2015/QĐ-TTg")
        st.caption(
            "Khoanh nợ / Xóa nợ cho hộ vay gặp rủi ro theo Quyết định 62. "
            "Dữ liệu được lưu theo kỳ (tháng hiện tại)."
        )

        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        df = _loc_df_theo_pgd(df, role, pgd_user)
        if df.empty:
            st.warning("⚠️ Không có dữ liệu HSTD cho đơn vị hiện tại.")
            return

        ten_pgd = _lay_pgd_tu_user(role, pgd_user, df)
        kv_key = _tao_kv_key(ten_pgd or "unknown")

        # ── Bước 1: Lọc hộ vay ──────────────────────────────────────────
        with st.expander("🔎 Lọc hộ vay", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df.columns else []
                chon_xa = st.selectbox("Xã/Phường", [""] + ds_xa, key="nrr_xa")
            with c2:
                df_loc = df[df[COT_TEN_XA] == chon_xa] if chon_xa and COT_TEN_XA in df.columns else df
                ds_to = sorted(df_loc[COT_TEN_TO].dropna().unique().tolist()) if COT_TEN_TO in df_loc.columns else []
                chon_to = st.selectbox("Tổ TK&VV", [""] + ds_to, key="nrr_to")
            with c3:
                tim_kh = st.text_input("Tìm tên KH", placeholder="Nhập tên...", key="nrr_tim")

        df_hien = df.copy()
        if chon_xa and COT_TEN_XA in df_hien.columns:
            df_hien = df_hien[df_hien[COT_TEN_XA] == chon_xa]
        if chon_to and COT_TEN_TO in df_hien.columns:
            df_hien = df_hien[df_hien[COT_TEN_TO] == chon_to]
        if tim_kh and COT_TEN_KH in df_hien.columns:
            df_hien = df_hien[df_hien[COT_TEN_KH].str.contains(tim_kh, case=False, na=False)]

        if df_hien.empty:
            st.info("ℹ️ Không tìm thấy hộ vay nào phù hợp.")
            return

        # ── Bước 2: Bảng chọn hộ vay ────────────────────────────────────
        st.markdown("#### 📋 Danh sách hộ vay")
        cot_hien = [c for c in [COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_TONG_DU_NO, COT_DU_NO_QH] if c in df_hien.columns]
        df_editor = df_hien[cot_hien].copy()
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
            key="nrr_editor",
        )
        ds_chon = edited[edited["Chọn"] == True]
        if ds_chon.empty:
            st.info("👆 Tích chọn ít nhất 1 hộ vay để nhập thông tin rủi ro.")
            return
        st.success(f"✅ Đã chọn **{len(ds_chon)}** hộ vay.")

        # ── Bước 3: Form nhập thông tin rủi ro ──────────────────────────
        st.markdown("#### 📝 Thông tin rủi ro")
        with st.form("form_no_rui_ro"):
            col1, col2 = st.columns(2)
            with col1:
                bien_phap = st.selectbox(
                    "Biện pháp xử lý",
                    ["Khoanh nợ (QĐ62)", "Xóa nợ (QĐ62)"],
                    key="nrr_bien_phap",
                )
                nguyen_nhan = st.selectbox(
                    "Nguyên nhân rủi ro",
                    NGUYEN_NHAN_RR,
                    key="nrr_nguyen_nhan",
                )
            with col2:
                ngay_rr = st.date_input(
                    "Ngày xảy ra rủi ro",
                    value=date.today(),
                    key="nrr_ngay_rr",
                )
            muc_do = ""
            so_thang = 0
            if "Khoanh nợ" in bien_phap:
                st.markdown("**Mức độ thiệt hại (khoanh nợ)**")
                mc1, mc2 = st.columns(2)
                with mc1:
                    muc_do = st.radio(
                        "Mức độ thiệt hại",
                        ["Từ 40% đến <80%", "Từ 80% đến 100%", "Không áp dụng"],
                        key="nrr_muc_do",
                    )
                with mc2:
                    goi_y = 60 if "80%" in muc_do else 36
                    so_thang = st.number_input(
                        "Số tháng đề nghị khoanh",
                        min_value=0, max_value=120, value=goi_y, step=6,
                        key="nrr_so_thang",
                        help=f"Gợi ý: {goi_y} tháng theo mức độ đã chọn",
                    )
            ghi_chu = st.text_area(
                "Ghi chú / Tóm tắt nguyên nhân",
                placeholder="Nhập tối thiểu 20 ký tự...",
                height=100,
                key="nrr_ghi_chu",
            )
            submitted = st.form_submit_button("💾 Lưu hồ sơ", type="primary")

        if submitted:
            if len(ghi_chu.strip()) < 20:
                st.error("⚠️ Ghi chú phải có ít nhất 20 ký tự.")
                st.stop()
            ds_luu = []
            for _, row in ds_chon.iterrows():
                ds_luu.append({
                    "ma_kh":       str(row.get(COT_SO_KU, "")),
                    "ten_kh":      str(row.get(COT_TEN_KH, "")),
                    "so_ku":       str(row.get(COT_SO_KU, "")),
                    "ten_ct":      str(row.get(COT_TEN_CT, "")),
                    "du_no":       float(row.get(COT_TONG_DU_NO, 0) or 0),
                    "bien_phap":   bien_phap,
                    "nguyen_nhan": nguyen_nhan,
                    "muc_do":      muc_do,
                    "so_thang":    int(so_thang),
                    "ngay_rr":     ngay_rr.isoformat(),
                    "ghi_chu":     ghi_chu.strip(),
                })
            db.ghi_kv(kv_key, {"danh_sach": ds_luu, "ngay_tao": datetime.now().isoformat()}, username)
            db.ghi_audit(username, "luu_no_rui_ro", f"{len(ds_luu)} hồ sơ — {ten_pgd or 'unknown'}")
            st.cache_data.clear()
            st.success(f"✅ Đã lưu **{len(ds_luu)}** hồ sơ xử lý nợ rủi ro.")
            st.balloons()

        # ── Bước 4: Xuất biểu mẫu ───────────────────────────────────────
        if ds_chon is not None and not ds_chon.empty:
            st.markdown("#### 📄 Xuất biểu mẫu")
            cols_btn = st.columns(3)

            ds_xuat = []
            for _, row in ds_chon.iterrows():
                ds_xuat.append({
                    "ten_kh": str(row.get(COT_TEN_KH, "")),
                    "so_ku":  str(row.get(COT_SO_KU, "")),
                    "ten_ct": str(row.get(COT_TEN_CT, "")),
                    "du_no":  fmt(row.get(COT_TONG_DU_NO, 0)),
                    "nqh":    fmt(row.get(COT_DU_NO_QH, 0)),
                })
            context_mau = {
                "pgd":       ten_pgd or "",
                "ngay_lap":  date.today().strftime("%d/%m/%Y"),
                "ngay":      date.today().day,
                "thang":     date.today().month,
                "nam":       date.today().year,
                "bien_phap": bien_phap if "bien_phap" in dir() else "",
                "nguyen_nhan": nguyen_nhan if "nguyen_nhan" in dir() else "",
                "so_kh":     len(ds_xuat),
                "ds_kh":     ds_xuat,
            }
            if "Khoanh nợ" in (bien_phap if "bien_phap" in dir() else ""):
                context_mau["muc_do"] = muc_do
                context_mau["so_thang"] = so_thang
                context_mau["ngay_rr"] = ngay_rr.isoformat() if "ngay_rr" in dir() else ""

            with cols_btn[0]:
                if st.button("📄 Xuất 13/XLN (Khoanh nợ)", use_container_width=True, key="nrr_btn_13"):
                    if co_template(TMPL_13XLN):
                        with st.spinner("Đang tạo 13/XLN..."):
                            docx_bytes = dien_template(TMPL_13XLN, context_mau)
                        ten_file = f"Mau13XLN_{ten_pgd or 'unknown'}_{date.today().strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_bytes, ten_file, "nrr_13xln")
                    else:
                        st.warning("⚠️ Chưa có template 13/XLN — liên hệ admin để upload mẫu.")
                hien_thi_nut_tai("nrr_13xln")
            with cols_btn[1]:
                if st.button("📄 Xuất 14/XLN (Xóa nợ)", use_container_width=True, key="nrr_btn_14"):
                    if co_template(TMPL_14XLN):
                        with st.spinner("Đang tạo 14/XLN..."):
                            docx_bytes = dien_template(TMPL_14XLN, context_mau)
                        ten_file = f"Mau14XLN_{ten_pgd or 'unknown'}_{date.today().strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_bytes, ten_file, "nrr_14xln")
                    else:
                        st.warning("⚠️ Chưa có template 14/XLN — liên hệ admin để upload mẫu.")
                hien_thi_nut_tai("nrr_14xln")
            with cols_btn[2]:
                bp = bien_phap if "bien_phap" in dir() else ""
                tmpl_tt = TMPL_TT_KHOANH if "Khoanh nợ" in bp else TMPL_TT_XOA
                ten_tt = "Tờ trình khoanh nợ" if "Khoanh nợ" in bp else "Tờ trình xóa nợ"
                if st.button(f"📄 Xuất {ten_tt}", use_container_width=True, key="nrr_btn_tt"):
                    if co_template(tmpl_tt):
                        with st.spinner(f"Đang tạo {ten_tt}..."):
                            docx_bytes = dien_template(tmpl_tt, context_mau)
                        ten_file = f"ToTrinh_{ten_pgd or 'unknown'}_{date.today().strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_bytes, ten_file, "nrr_tt")
                    else:
                        st.warning(f"⚠️ Chưa có template '{tmpl_tt}' — liên hệ admin để upload mẫu.")
                hien_thi_nut_tai("nrr_tt")

        # ── Bước 5: Xem lại hồ sơ đã lưu ─────────────────────────────────
        st.markdown("---")
        with st.expander("📋 Hồ sơ đã lập kỳ này", expanded=False):
            du_lieu_cu = db.doc_kv(kv_key)
            if du_lieu_cu and "danh_sach" in du_lieu_cu:
                ds_cu = du_lieu_cu["danh_sach"]
                st.caption(f"🕐 {du_lieu_cu.get('ngay_tao', '')} — {len(ds_cu)} hồ sơ")
                _hien_thi_chi_tiet(ds_cu)
                if st.button("🗑️ Xóa bản ghi", key="nrr_btn_xoa", type="secondary"):
                    st.session_state["nrr_xac_nhan_xoa"] = True
                if st.session_state.get("nrr_xac_nhan_xoa"):
                    st.warning("⚠️ Bạn có chắc chắn muốn xóa toàn bộ hồ sơ kỳ này?")
                    c_xc1, c_xc2 = st.columns(2)
                    with c_xc1:
                        if st.button("✅ Xác nhận xóa", key="nrr_btn_xac_nhan"):
                            db.ghi_kv(kv_key, {}, username)
                            db.ghi_audit(username, "xoa_no_rui_ro",
                                         f"Xóa {len(ds_cu)} hồ sơ — {ten_pgd or 'unknown'}")
                            st.session_state.pop("nrr_xac_nhan_xoa", None)
                            st.cache_data.clear()
                            st.success("✅ Đã xóa hồ sơ.")
                            st.rerun()
                    with c_xc2:
                        if st.button("❌ Hủy", key="nrr_btn_huy"):
                            st.session_state.pop("nrr_xac_nhan_xoa", None)
                            st.rerun()
            else:
                st.info("ℹ️ Chưa có hồ sơ nào trong kỳ này.")
