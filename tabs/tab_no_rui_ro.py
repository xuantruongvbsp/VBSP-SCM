"""Xử lý nợ rủi ro theo QĐ 62/2015/QĐ-TTg — 5 bước: lọc, chọn, nhập, xuất, xem lại."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from config import (
    COT_DIA_CHI,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_LAI_TON,
    COT_MA_KH,
    COT_MUC_VAY,
    COT_NGAY_DH,
    COT_NGAY_VAY,
    COT_NGUON_VON,
    COT_SDT,
    COT_TEN_XA,
    COT_TEN_TO,
    COT_TEN_KH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_TEN_PGD,
    DS_PGD,
    NGUYEN_NHAN_RR,
)
from data.pgd import pgd_slug
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from utils import fmt, fmt_bang_ty, fmt_ngay, hien_thi_dataframe_phan_trang, xuat_excel
from services.template_service import (
    docx_bytes_to_pdf,
    nut_tai_word_va_pdf,
    hien_thi_nut_tai,
)
from services.word_xln_service import (
    _pgd_plain,
    _pgd_line,
    _style_doc_xln,
    _bo_border_cell,
    _set_cell,
    _set_row_font,
    _num,
    _add_header_xln,
    _set_margins,
    _tao_word_01xln,
    _tao_word_02xln,
    _tao_word_xln_bao_cao,
    _tao_word_13xln,
    _tao_word_14xln,
    _tao_word_04xln,
    _tao_word_05xln,
    _tao_word_to_trinh_pgd,
    _tao_word_to_trinh_cn,
)
from services.rui_ro_aggregation import _loc_theo_nguon, _tong_hop_no

NGUON_TW = 1
NGUON_DP = 2
LABEL_TW = "Trung ương"
LABEL_DP = "Địa phương"


def _lay_pgd_tu_user(role: str, pgd_user: str | None, df: pd.DataFrame) -> str | None:
    if pgd_user:
        return pgd_user
    if la_phan_he_cn(role) and df is not None and COT_TEN_PGD in df.columns:
        ds = df[COT_TEN_PGD].dropna().unique().tolist()
        if len(ds) == 1:
            return str(ds[0])
    return None


def _loc_df_theo_pgd(df: pd.DataFrame, role: str, pgd_user: str | None) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if la_phan_he_pgd(role) and pgd_user and COT_TEN_PGD in df.columns:
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


# ── Hàm tách từ render() — Bước 4: xuất 04/05 XLN + Tờ trình ─────────
def _render_04_05_tt(
    ds_khoanh, ds_xoa, ten_don_vi, nguon_label,
    key_prefix, dot_xuat, nam_xuat, la_cn=False,
) -> None:
    ngay_hom_nay = date.today()
    st.markdown(f"**📄 04/XLN — Tổng hợp đề nghị khoanh nợ ({nguon_label})**")
    if st.button(f"📥 Xuất 04/XLN — {nguon_label}", use_container_width=True,
                 key=f"{key_prefix}_04xln"):
        if not ds_khoanh:
            st.warning("⚠️ Không có hồ sơ khoanh nợ.")
        else:
            docx_b = _tao_word_04xln(_tong_hop_no(ds_khoanh), ten_don_vi,
                                      nguon_label, dot_xuat, nam_xuat)
            nut_tai_word_va_pdf(docx_b,
                f"Mau04XLN_{nguon_label[:2]}_{ten_don_vi}_{ngay_hom_nay:%d%m%Y}",
                f"{key_prefix}_04xln")
    hien_thi_nut_tai(f"{key_prefix}_04xln")

    st.markdown(f"**📄 05/XLN — Tổng hợp đề nghị xóa nợ ({nguon_label})**")
    if st.button(f"📥 Xuất 05/XLN — {nguon_label}", use_container_width=True,
                 key=f"{key_prefix}_05xln"):
        if not ds_xoa:
            st.warning("⚠️ Không có hồ sơ xóa nợ.")
        else:
            docx_b = _tao_word_05xln(_tong_hop_no(ds_xoa), ten_don_vi,
                                      nguon_label, dot_xuat, nam_xuat)
            nut_tai_word_va_pdf(docx_b,
                f"Mau05XLN_{nguon_label[:2]}_{ten_don_vi}_{ngay_hom_nay:%d%m%Y}",
                f"{key_prefix}_05xln")
    hien_thi_nut_tai(f"{key_prefix}_05xln")

    ten_tt = "02/TT" if la_cn else "01/TT"
    st.markdown(f"**📄 Tờ trình {ten_tt} ({nguon_label})**")
    if st.button(f"📥 Xuất Tờ trình — {nguon_label}", use_container_width=True,
                 key=f"{key_prefix}_tt"):
        if not ds_khoanh and not ds_xoa:
            st.warning("⚠️ Không có hồ sơ nào.")
        else:
            if la_cn:
                docx_b = _tao_word_to_trinh_cn(
                    _tong_hop_no(ds_khoanh), _tong_hop_no(ds_xoa),
                    ds_khoanh, "Đồng Nai", nguon_label, dot_xuat, nam_xuat,
                )
            else:
                docx_b = _tao_word_to_trinh_pgd(
                    _tong_hop_no(ds_khoanh), _tong_hop_no(ds_xoa),
                    ds_khoanh, ten_don_vi, nguon_label, dot_xuat, nam_xuat,
                )
            nut_tai_word_va_pdf(docx_b,
                f"ToTrinh{ten_tt.replace('/','')}_{nguon_label[:2]}_{ten_don_vi}_{ngay_hom_nay:%d%m%Y}",
                f"{key_prefix}_tt")
    hien_thi_nut_tai(f"{key_prefix}_tt")


# ── Hàm tách từ render() — Bước 1→5 (luồng nhập hồ sơ) ──────────────
def _render_luong_nhap_ho_so(
    df_pgd: pd.DataFrame,
    ten_pgd: str,
    kv_key: str,
    username: str,
    la_cn: bool = False,
    key_prefix: str = "",
) -> None:
    """Luồng nhập hồ sơ rủi ro 5 bước — dùng chung cho PGD và CN.
    key_prefix: thêm vào đầu mọi st.* key để tránh conflict widget.
    la_cn: True → Tờ trình 02/TT + kv key riêng của CN.
    """
    df = df_pgd

    # ── Bước 1: Lọc hộ vay ──────────────────────────────────────────
    with st.expander("🔎 Lọc hộ vay", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df.columns else []
            chon_xa = st.selectbox("Xã/Phường", [""] + ds_xa, key=f"{key_prefix}nrr_xa")
        with c2:
            df_loc = df[df[COT_TEN_XA] == chon_xa] if chon_xa and COT_TEN_XA in df.columns else df
            ds_to = sorted(df_loc[COT_TEN_TO].dropna().unique().tolist()) if COT_TEN_TO in df_loc.columns else []
            chon_to = st.selectbox("Tổ TK&VV", [""] + ds_to, key=f"{key_prefix}nrr_to")
        with c3:
            tim_kh = st.text_input("Tìm tên KH", placeholder="Nhập tên...", key=f"{key_prefix}nrr_tim")

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
        key=f"{key_prefix}nrr_editor",
    )
    ds_chon = edited[edited["Chọn"] == True]
    if ds_chon.empty:
        st.info("👆 Tích chọn ít nhất 1 hộ vay để nhập thông tin rủi ro.")
        return
    st.success(f"✅ Đã chọn **{len(ds_chon)}** hộ vay.")

    # ── Bước 3: Form nhập thông tin rủi ro ──────────────────────────
    st.markdown("#### 📝 Thông tin rủi ro")
    with st.form(f"{key_prefix}form_no_rui_ro"):
        col1, col2 = st.columns(2)
        with col1:
            bien_phap = st.selectbox(
                "Biện pháp xử lý",
                ["Khoanh nợ (QĐ62)", "Xóa nợ (QĐ62)"],
                key=f"{key_prefix}nrr_bien_phap",
            )
            nguyen_nhan = st.selectbox(
                "Nguyên nhân rủi ro",
                NGUYEN_NHAN_RR,
                key=f"{key_prefix}nrr_nguyen_nhan",
            )
        with col2:
            ngay_rr = st.date_input(
                "Ngày xảy ra rủi ro",
                value=date.today(),
                key=f"{key_prefix}nrr_ngay_rr",
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
                    key=f"{key_prefix}nrr_muc_do",
                )
            with mc2:
                goi_y = 60 if "80%" in muc_do else 36
                so_thang = st.number_input(
                    "Số tháng đề nghị khoanh",
                    min_value=0, max_value=120, value=goi_y, step=6,
                    key=f"{key_prefix}nrr_so_thang",
                    help=f"Gợi ý: {goi_y} tháng theo mức độ đã chọn",
                )
        ghi_chu = st.text_area(
            "Ghi chú / Tóm tắt nguyên nhân",
            placeholder="Nhập tối thiểu 20 ký tự...",
            height=100,
            key=f"{key_prefix}nrr_ghi_chu",
        )
        submitted = st.form_submit_button("💾 Lưu hồ sơ", type="primary")

    if submitted:
        if len(ghi_chu.strip()) < 20:
            st.error("⚠️ Ghi chú phải có ít nhất 20 ký tự.")
            st.stop()

        ds_luu = []
        for _, row in ds_chon.iterrows():
            so_ku_r = str(row.get(COT_SO_KU, ""))
            row_full = row
            if so_ku_r and df is not None and not df.empty and COT_SO_KU in df.columns:
                df_tmp = df[df[COT_SO_KU].astype(str) == so_ku_r]
                if not df_tmp.empty:
                    row_full = df_tmp.iloc[0]
            ds_luu.append({
                "ma_kh":   so_ku_r,
                "ten_kh":  str(row_full.get(COT_TEN_KH, "")),
                "so_ku":   so_ku_r,
                "ten_ct":  str(row_full.get(COT_TEN_CT, "")),
                "du_no":   _num(row_full.get(COT_TONG_DU_NO, 0) or 0),
                "dia_chi": str(row_full.get(COT_DIA_CHI, "")),
                "ngay_vay": fmt_ngay(row_full.get(COT_NGAY_VAY, "")),
                "du_no_goc": _num(row_full.get(COT_TONG_DU_NO, 0) or 0),
                "lai_ton": _num(row_full.get(COT_LAI_TON, 0) or 0),
                "nguon_von": int(row_full.get(COT_NGUON_VON, 0) or 0),
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
        st.info("Soạn mẫu 01/02 XLN đã được chuyển sang phần '🧾 Soạn mẫu 01/XLN và 02/XLN' ở phía trên.")

        ds_xuat_full = []
        so_hs_khong_nguon = 0
        for _, row in ds_chon.iterrows():
            so_ku_r = str(row.get(COT_SO_KU, ""))
            row_full = row
            if so_ku_r and df is not None and COT_SO_KU in df.columns:
                df_tmp = df[df[COT_SO_KU].astype(str) == so_ku_r]
                if not df_tmp.empty:
                    row_full = df_tmp.iloc[0]
            try:
                nguon_von_int = int(row_full.get(COT_NGUON_VON, 0) or 0)
            except (ValueError, TypeError):
                nguon_von_int = 0
            if nguon_von_int not in (NGUON_TW, NGUON_DP):
                so_hs_khong_nguon += 1
                nguon_von_int = NGUON_TW
            ds_xuat_full.append({
                "ten_ct":    str(row_full.get(COT_TEN_CT, "")),
                "ten_kh":    str(row_full.get(COT_TEN_KH, "")),
                "dia_chi":   str(row_full.get(COT_DIA_CHI, "")),
                "so_ku":     so_ku_r,
                "ngay_vay":  fmt_ngay(row_full.get(COT_NGAY_VAY, "")),
                "du_no_goc": float(row_full.get(COT_TONG_DU_NO, 0) or 0),
                "lai_ton":   float(row_full.get(COT_LAI_TON, 0) or 0),
                "bien_phap": bien_phap,
                "muc_do":    muc_do,
                "so_thang":  int(so_thang),
                "ghi_chu":   ghi_chu,
                "nguon_von": nguon_von_int,
            })
        if so_hs_khong_nguon:
            st.warning(
                f"Có {so_hs_khong_nguon} hồ sơ không xác định được nguồn vốn "
                f"(cột 'Nguồn vốn' trong HSTD gốc bị trống hoặc sai). "
                f"Mặc định gán về Trung ương. Kiểm tra lại file HSTD gốc nếu cần."
            )

        ds_tw = _loc_theo_nguon(ds_xuat_full, NGUON_TW)
        ds_dp = _loc_theo_nguon(ds_xuat_full, NGUON_DP)
        ds_khoanh_tw = [r for r in ds_tw if "Khoanh" in r.get("bien_phap", "")]
        ds_xoa_tw    = [r for r in ds_tw if "Xóa"    in r.get("bien_phap", "")]
        ds_khoanh_dp = [r for r in ds_dp if "Khoanh" in r.get("bien_phap", "")]
        ds_xoa_dp    = [r for r in ds_dp if "Xóa"    in r.get("bien_phap", "")]

        dot_xuat = 1
        nam_xuat = date.today().year

        st.markdown("#### 📋 Biểu đề nghị xử lý nợ + Tờ trình")

        col_tw, col_dp = st.columns(2)
        with col_tw:
            st.markdown("##### 🔵 Trung ương")
            _render_04_05_tt(ds_khoanh_tw, ds_xoa_tw, ten_pgd, LABEL_TW,
                             f"{key_prefix}tw", dot_xuat, nam_xuat, la_cn)
        with col_dp:
            st.markdown("##### 🟢 Địa phương")
            _render_04_05_tt(ds_khoanh_dp, ds_xoa_dp, ten_pgd, LABEL_DP,
                             f"{key_prefix}dp", dot_xuat, nam_xuat, la_cn)

        st.markdown("---")
        st.markdown("#### 📊 Báo cáo sau hạch toán (13/XLN · 14/XLN)")
        st.caption("Xuất sau khi có Quyết định của Hội đồng quản trị NHCSXH.")

        with st.expander("⚙️ Thông tin Quyết định HĐQT", expanded=False):
            col_qd1, col_qd2, col_qd3, col_qd4 = st.columns(4)
            with col_qd1:
                so_qd = st.text_input("Số QĐ HĐQT", placeholder="vd: 123/QĐ-HĐQT", key=f"{key_prefix}nrr_so_qd")
            with col_qd2:
                ngay_qd = st.date_input("Ngày ký QĐ", value=date.today(), key=f"{key_prefix}nrr_ngay_qd")
            with col_qd3:
                ngay_bd = st.date_input("Từ ngày", value=date.today(), key=f"{key_prefix}nrr_ngay_bd")
            with col_qd4:
                ngay_kt = st.date_input("Đến ngày", value=date.today(), key=f"{key_prefix}nrr_ngay_kt")

        col13_tw, col13_dp, col14_tw, col14_dp = st.columns(4)
        with col13_tw:
            if st.button("📥 13/XLN\nTrung ương", use_container_width=True, key=f"{key_prefix}nrr_13xln_tw"):
                if not ds_khoanh_tw:
                    st.warning("⚠️ Không có hồ sơ khoanh nợ TW.")
                else:
                    docx_b = _tao_word_13xln(
                        _tong_hop_no(ds_khoanh_tw), ten_pgd, LABEL_TW,
                        so_qd, ngay_qd, ngay_bd, ngay_kt,
                    )
                    nut_tai_word_va_pdf(docx_b, f"Mau13XLN_TW_{ten_pgd}_{date.today():%d%m%Y}", f"{key_prefix}nrr_13xln_tw")
            hien_thi_nut_tai(f"{key_prefix}nrr_13xln_tw")
        with col13_dp:
            if st.button("📥 13/XLN\nĐịa phương", use_container_width=True, key=f"{key_prefix}nrr_13xln_dp"):
                if not ds_khoanh_dp:
                    st.warning("⚠️ Không có hồ sơ khoanh nợ ĐP.")
                else:
                    docx_b = _tao_word_13xln(
                        _tong_hop_no(ds_khoanh_dp), ten_pgd, LABEL_DP,
                        so_qd, ngay_qd, ngay_bd, ngay_kt,
                    )
                    nut_tai_word_va_pdf(docx_b, f"Mau13XLN_DP_{ten_pgd}_{date.today():%d%m%Y}", f"{key_prefix}nrr_13xln_dp")
            hien_thi_nut_tai(f"{key_prefix}nrr_13xln_dp")
        with col14_tw:
            if st.button("📥 14/XLN\nTrung ương", use_container_width=True, key=f"{key_prefix}nrr_14xln_tw"):
                if not ds_xoa_tw:
                    st.warning("⚠️ Không có hồ sơ xóa nợ TW.")
                else:
                    docx_b = _tao_word_14xln(
                        _tong_hop_no(ds_xoa_tw), ten_pgd, LABEL_TW,
                        so_qd, ngay_qd, ngay_bd, ngay_kt,
                    )
                    nut_tai_word_va_pdf(docx_b, f"Mau14XLN_TW_{ten_pgd}_{date.today():%d%m%Y}", f"{key_prefix}nrr_14xln_tw")
            hien_thi_nut_tai(f"{key_prefix}nrr_14xln_tw")
        with col14_dp:
            if st.button("📥 14/XLN\nĐịa phương", use_container_width=True, key=f"{key_prefix}nrr_14xln_dp"):
                if not ds_xoa_dp:
                    st.warning("⚠️ Không có hồ sơ xóa nợ ĐP.")
                else:
                    docx_b = _tao_word_14xln(
                        _tong_hop_no(ds_xoa_dp), ten_pgd, LABEL_DP,
                        so_qd, ngay_qd, ngay_bd, ngay_kt,
                    )
                    nut_tai_word_va_pdf(docx_b, f"Mau14XLN_DP_{ten_pgd}_{date.today():%d%m%Y}", f"{key_prefix}nrr_14xln_dp")
            hien_thi_nut_tai(f"{key_prefix}nrr_14xln_dp")

    # ── Bước 5: Xem lại hồ sơ đã lưu ─────────────────────────────────
    st.markdown("---")
    with st.expander("📋 Hồ sơ đã lập kỳ này", expanded=False):
        du_lieu_cu = db.doc_kv(kv_key)
        if du_lieu_cu and "danh_sach" in du_lieu_cu:
            ds_cu = du_lieu_cu["danh_sach"]
            st.caption(f"🕐 {du_lieu_cu.get('ngay_tao', '')} — {len(ds_cu)} hồ sơ")
            _hien_thi_chi_tiet(ds_cu)
            if st.button("🗑️ Xóa bản ghi", key=f"{key_prefix}nrr_btn_xoa", type="secondary"):
                st.session_state[f"{key_prefix}nrr_xac_nhan_xoa"] = True
            if st.session_state.get(f"{key_prefix}nrr_xac_nhan_xoa"):
                st.warning("⚠️ Bạn có chắc chắn muốn xóa toàn bộ hồ sơ kỳ này?")
                c_xc1, c_xc2 = st.columns(2)
                with c_xc1:
                    if st.button("✅ Xác nhận xóa", key=f"{key_prefix}nrr_btn_xac_nhan"):
                        db.ghi_kv(kv_key, {}, username)
                        db.ghi_audit(username, "xoa_no_rui_ro",
                                     f"Xóa {len(ds_cu)} hồ sơ — {ten_pgd or 'unknown'}")
                        st.session_state.pop(f"{key_prefix}nrr_xac_nhan_xoa", None)
                        st.cache_data.clear()
                        st.success("✅ Đã xóa hồ sơ.")
                        st.rerun()
                with c_xc2:
                    if st.button("❌ Hủy", key=f"{key_prefix}nrr_btn_huy"):
                        st.session_state.pop(f"{key_prefix}nrr_xac_nhan_xoa", None)
                        st.rerun()
        else:
            st.info("ℹ️ Chưa có hồ sơ nào trong kỳ này.")


# ── Workspace cho Phòng KH-NV (CN) ─────────────────────────────────
def _render_workspace_cn(tab, **kwargs) -> None:
    df       = kwargs.get("df")
    username = kwargs.get("username", "unknown")

    _tab_ctx = tab if tab is not None else st.container()
    with _tab_ctx:
        t0, t1, t2, t3 = st.tabs([
            "📝 Nhập hồ sơ theo PGD",
            "📊 Tổng quan toàn tỉnh",
            "📋 Biểu đề nghị + Tờ trình CN",
            "📊 13/XLN · 14/XLN",
        ])

        # ── T0: Nhập hồ sơ theo PGD ──────────────────────────────────
        with t0:
            st.caption("Phòng KH-NV nhập thay PGD hoặc nhập hồ sơ Hội sở tỉnh.")

            pgd_chon = st.selectbox(
                "📍 Chọn PGD",
                options=DS_PGD,
                key="cn_nrr_chon_pgd",
            )
            df_pgd = df[df[COT_TEN_PGD] == pgd_chon].copy() \
                     if COT_TEN_PGD in df.columns else pd.DataFrame()

            if df_pgd.empty:
                st.warning(f"⚠️ Không có dữ liệu HSTD cho {pgd_chon}.")
            else:
                now = datetime.now()
                kv_key_cn = f"no_rui_ro_{pgd_slug(pgd_chon)}_{now.year}_{now.month:02d}"
                _render_luong_nhap_ho_so(
                    df_pgd=df_pgd,
                    ten_pgd=pgd_chon,
                    kv_key=kv_key_cn,
                    username=username,
                    la_cn=True,
                    key_prefix="cn_",
                )

        # ── T1: Tổng quan toàn tỉnh ──────────────────────────────────
        with t1:
            col_thang, col_nam = st.columns(2)
            with col_thang:
                thang_xem = st.selectbox("Tháng", list(range(1, 13)),
                    index=datetime.now().month - 1, key="cn_nrr_thang")
            with col_nam:
                nam_xem = st.number_input("Năm", min_value=2020,
                    max_value=2030, value=datetime.now().year, key="cn_nrr_nam")

            ds_all: list[dict] = []
            pgd_co_du_lieu: list[str] = []
            for pgd in DS_PGD:
                key = f"no_rui_ro_{pgd_slug(pgd)}_{nam_xem}_{thang_xem:02d}"
                data = db.doc_kv(key)
                if data and "danh_sach" in data:
                    for item in data["danh_sach"]:
                        item["_pgd"] = pgd
                    ds_all.extend(data["danh_sach"])
                    pgd_co_du_lieu.append(pgd)

            tong_hs    = len(ds_all)
            so_khoanh  = sum(1 for r in ds_all if "Khoanh" in r.get("bien_phap",""))
            so_xoa     = sum(1 for r in ds_all if "Xóa"    in r.get("bien_phap",""))
            tien_khoanh = sum(r.get("du_no", 0) for r in ds_all
                              if "Khoanh" in r.get("bien_phap",""))
            tien_xoa    = sum(r.get("du_no", 0) for r in ds_all
                              if "Xóa"    in r.get("bien_phap",""))

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tổng hồ sơ", tong_hs)
            c2.metric("Khoanh nợ", f"{so_khoanh} món",
                      fmt(tien_khoanh))
            c3.metric("Xóa nợ", f"{so_xoa} món",
                      fmt(tien_xoa))
            c4.metric("PGD có hồ sơ",
                      f"{len(pgd_co_du_lieu)}/{len(DS_PGD)}")

            if not ds_all:
                st.info("ℹ️ Chưa có PGD nào nhập hồ sơ trong kỳ này.")
            else:
                rows_pgd = []
                for pgd in DS_PGD:
                    ds_pgd = [r for r in ds_all if r.get("_pgd") == pgd]
                    if not ds_pgd:
                        continue
                    kh  = [r for r in ds_pgd if "Khoanh" in r.get("bien_phap","")]
                    xoa = [r for r in ds_pgd if "Xóa"    in r.get("bien_phap","")]
                    tw  = [r for r in ds_pgd if r.get("nguon_von") == NGUON_TW]
                    dp  = [r for r in ds_pgd if r.get("nguon_von") == NGUON_DP]
                    rows_pgd.append({
                        "PGD":             pgd,
                        "Khoanh (món)":    len(kh),
                        "Khoanh (triệu)":  sum(r.get("du_no",0) for r in kh) / 1e6,
                        "Xóa (món)":       len(xoa),
                        "Xóa (triệu)":     sum(r.get("du_no",0) for r in xoa) / 1e6,
                        "TW (triệu)":      sum(r.get("du_no",0) for r in tw) / 1e6,
                        "ĐP (triệu)":      sum(r.get("du_no",0) for r in dp) / 1e6,
                        "Tổng (triệu)":    sum(r.get("du_no",0) for r in ds_pgd) / 1e6,
                    })
                df_th = pd.DataFrame(rows_pgd)
                hien_thi_dataframe_phan_trang(df_th, key="cn_nrr_th_pgd")

                if st.button("📥 Xuất Excel tổng hợp", key="cn_nrr_xuat_xl"):
                    df_ct = pd.DataFrame([
                        {k: v for k, v in r.items() if k != "_pgd"}
                        for r in ds_all
                    ])
                    buf = xuat_excel({
                        "Tổng hợp PGD": df_th,
                        "Chi tiết":     df_ct,
                    })
                    st.session_state["_cn_nrr_xl"] = buf
                    db.ghi_audit(username, "xuat_bieu_cn",
                                 f"Excel tổng hợp NRR {thang_xem}/{nam_xem}")
                if st.session_state.get("_cn_nrr_xl"):
                    st.download_button(
                        "⬇ Tải Excel",
                        data=st.session_state["_cn_nrr_xl"],
                        file_name=f"TongHop_NRR_{thang_xem:02d}{nam_xem}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="cn_nrr_dl_xl",
                    )

        # ── T2: Biểu đề nghị + Tờ trình CN ──────────────────────────
        with t2:
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                pgd_t2 = st.selectbox("PGD", ["Tất cả"] + DS_PGD,
                                       key="cn_nrr_t2_pgd")
            with col_f2:
                nv_t2 = st.selectbox("Nguồn vốn",
                    ["Tất cả", "Trung ương", "Địa phương"],
                    key="cn_nrr_t2_nv")
            with col_f3:
                dot_t2 = st.number_input("Đợt", min_value=1, max_value=4,
                                          value=1, key="cn_nrr_t2_dot")
            with col_f4:
                nam_t2 = st.number_input("Năm", min_value=2020, max_value=2030,
                    value=datetime.now().year, key="cn_nrr_t2_nam")

            ds_t2: list[dict] = []
            thang_ht = datetime.now().month
            for pgd in (DS_PGD if pgd_t2 == "Tất cả" else [pgd_t2]):
                key = f"no_rui_ro_{pgd_slug(pgd)}_{nam_t2}_{thang_ht:02d}"
                data = db.doc_kv(key)
                if data and "danh_sach" in data:
                    ds_t2.extend(data["danh_sach"])

            if nv_t2 == "Trung ương":
                ds_t2 = [r for r in ds_t2 if r.get("nguon_von") == NGUON_TW]
            elif nv_t2 == "Địa phương":
                ds_t2 = [r for r in ds_t2 if r.get("nguon_von") == NGUON_DP]

            ds_khoanh_tw = [r for r in ds_t2
                if "Khoanh" in r.get("bien_phap","")
                and r.get("nguon_von") == NGUON_TW]
            ds_xoa_tw    = [r for r in ds_t2
                if "Xóa"    in r.get("bien_phap","")
                and r.get("nguon_von") == NGUON_TW]
            ds_khoanh_dp = [r for r in ds_t2
                if "Khoanh" in r.get("bien_phap","")
                and r.get("nguon_von") == NGUON_DP]
            ds_xoa_dp    = [r for r in ds_t2
                if "Xóa"    in r.get("bien_phap","")
                and r.get("nguon_von") == NGUON_DP]

            ten_don_vi = "Chi nhánh Đồng Nai"
            col_tw, col_dp = st.columns(2)
            with col_tw:
                st.markdown("##### 🔵 Trung ương")
                _render_04_05_tt(
                    ds_khoanh_tw, ds_xoa_tw, ten_don_vi, LABEL_TW,
                    key_prefix="cn_t2_tw",
                    dot_xuat=int(dot_t2), nam_xuat=int(nam_t2),
                    la_cn=True,
                )
            with col_dp:
                st.markdown("##### 🟢 Địa phương")
                _render_04_05_tt(
                    ds_khoanh_dp, ds_xoa_dp, ten_don_vi, LABEL_DP,
                    key_prefix="cn_t2_dp",
                    dot_xuat=int(dot_t2), nam_xuat=int(nam_t2),
                    la_cn=True,
                )

        # ── T3: 13/XLN · 14/XLN ────────────────────────────────────
        with t3:
            st.caption("Xuất sau khi có Quyết định của Hội đồng quản trị NHCSXH.")

            pgd_t3 = st.selectbox("PGD", ["Tất cả"] + DS_PGD,
                                    key="cn_nrr_t3_pgd")

            with st.expander("⚙️ Thông tin Quyết định HĐQT", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    so_qd  = st.text_input("Số QĐ", placeholder="123/QĐ-HĐQT",
                                            key="cn_nrr_so_qd")
                with c2:
                    ngay_qd = st.date_input("Ngày ký", value=date.today(),
                                             format="DD/MM/YYYY", key="cn_nrr_ngay_qd")
                with c3:
                    ngay_bd = st.date_input("Từ ngày", value=date.today(),
                                             format="DD/MM/YYYY", key="cn_nrr_ngay_bd")
                with c4:
                    ngay_kt = st.date_input("Đến ngày", value=date.today(),
                                             format="DD/MM/YYYY", key="cn_nrr_ngay_kt")

            thang_ht = datetime.now().month
            nam_ht   = datetime.now().year
            ds_t3: list[dict] = []
            for pgd in (DS_PGD if pgd_t3 == "Tất cả" else [pgd_t3]):
                key = f"no_rui_ro_{pgd_slug(pgd)}_{nam_ht}_{thang_ht:02d}"
                data = db.doc_kv(key)
                if data and "danh_sach" in data:
                    ds_t3.extend(data["danh_sach"])

            ds_kh_tw = [r for r in ds_t3
                if "Khoanh" in r.get("bien_phap","")
                and r.get("nguon_von") == NGUON_TW]
            ds_kh_dp = [r for r in ds_t3
                if "Khoanh" in r.get("bien_phap","")
                and r.get("nguon_von") == NGUON_DP]
            ds_xo_tw = [r for r in ds_t3
                if "Xóa" in r.get("bien_phap","")
                and r.get("nguon_von") == NGUON_TW]
            ds_xo_dp = [r for r in ds_t3
                if "Xóa" in r.get("bien_phap","")
                and r.get("nguon_von") == NGUON_DP]

            ten_don_vi = "Chi nhánh Đồng Nai"
            ngay_hom_nay = date.today()

            col13_tw, col13_dp, col14_tw, col14_dp = st.columns(4)
            with col13_tw:
                if st.button("📥 13/XLN TW", use_container_width=True,
                              key="cn_nrr_13tw"):
                    if not ds_kh_tw:
                        st.warning("⚠️ Không có hồ sơ khoanh nợ TW.")
                    else:
                        docx_b = _tao_word_13xln(
                            _tong_hop_no(ds_kh_tw), ten_don_vi, LABEL_TW,
                            so_qd, ngay_qd, ngay_bd, ngay_kt,
                        )
                        nut_tai_word_va_pdf(docx_b,
                            f"Mau13XLN_TW_CN_{ngay_hom_nay:%d%m%Y}",
                            "cn_nrr_13tw")
                        db.ghi_audit(username, "xuat_bieu_cn", "13XLN TW")
                hien_thi_nut_tai("cn_nrr_13tw")

            with col13_dp:
                if st.button("📥 13/XLN ĐP", use_container_width=True,
                              key="cn_nrr_13dp"):
                    if not ds_kh_dp:
                        st.warning("⚠️ Không có hồ sơ khoanh nợ ĐP.")
                    else:
                        docx_b = _tao_word_13xln(
                            _tong_hop_no(ds_kh_dp), ten_don_vi, LABEL_DP,
                            so_qd, ngay_qd, ngay_bd, ngay_kt,
                        )
                        nut_tai_word_va_pdf(docx_b,
                            f"Mau13XLN_DP_CN_{ngay_hom_nay:%d%m%Y}",
                            "cn_nrr_13dp")
                        db.ghi_audit(username, "xuat_bieu_cn", "13XLN ĐP")
                hien_thi_nut_tai("cn_nrr_13dp")

            with col14_tw:
                if st.button("📥 14/XLN TW", use_container_width=True,
                              key="cn_nrr_14tw"):
                    if not ds_xo_tw:
                        st.warning("⚠️ Không có hồ sơ xóa nợ TW.")
                    else:
                        docx_b = _tao_word_14xln(
                            _tong_hop_no(ds_xo_tw), ten_don_vi, LABEL_TW,
                            so_qd, ngay_qd, ngay_bd, ngay_kt,
                        )
                        nut_tai_word_va_pdf(docx_b,
                            f"Mau14XLN_TW_CN_{ngay_hom_nay:%d%m%Y}",
                            "cn_nrr_14tw")
                        db.ghi_audit(username, "xuat_bieu_cn", "14XLN TW")
                hien_thi_nut_tai("cn_nrr_14tw")

            with col14_dp:
                if st.button("📥 14/XLN ĐP", use_container_width=True,
                              key="cn_nrr_14dp"):
                    if not ds_xo_dp:
                        st.warning("⚠️ Không có hồ sơ xóa nợ ĐP.")
                    else:
                        docx_b = _tao_word_14xln(
                            _tong_hop_no(ds_xo_dp), ten_don_vi, LABEL_DP,
                            so_qd, ngay_qd, ngay_bd, ngay_kt,
                        )
                        nut_tai_word_va_pdf(docx_b,
                            f"Mau14XLN_DP_CN_{ngay_hom_nay:%d%m%Y}",
                            "cn_nrr_14dp")
                        db.ghi_audit(username, "xuat_bieu_cn", "14XLN ĐP")
                hien_thi_nut_tai("cn_nrr_14dp")


def render(tab: DeltaGenerator, **kwargs) -> None:
    df = kwargs.get("df")
    role_raw = str(kwargs.get("role", "user") or "user")
    role = normalize_role(role_raw)
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
        if la_phan_he_cn(role):
            _render_workspace_cn(tab, df=df, role=role, username=username, **kwargs)
            return


        df = _loc_df_theo_pgd(df, role, pgd_user)
        if df.empty:
            st.warning("⚠️ Không có dữ liệu HSTD cho đơn vị hiện tại.")
            return

        ten_pgd = _lay_pgd_tu_user(role, pgd_user, df)
        kv_key = _tao_kv_key(ten_pgd or "unknown")

        st.markdown("#### 🧾 Soạn mẫu 01/XLN và 02/XLN")
        so_ku_list = []
        if COT_SO_KU in df.columns:
            try:
                so_ku_list = sorted(
                    [str(x).strip() for x in df[COT_SO_KU].dropna().astype(str).unique().tolist()]
                )
            except Exception:
                so_ku_list = []

        if not so_ku_list:
            st.warning("⚠️ Không có món vay nào để soạn mẫu (thiếu Số khế ước hoặc dữ liệu rỗng).")
        else:
            so_ku_chon = st.selectbox(
                "BƯỚC 1 — Chọn món vay (Số khế ước)",
                options=so_ku_list,
                key="xln_so_ku_chon",
            )

            row_hstd = None
            try:
                df_row = df[df[COT_SO_KU].astype(str) == str(so_ku_chon)]
                if not df_row.empty:
                    row_hstd = df_row.iloc[0]
            except Exception:
                row_hstd = None

            if row_hstd is None:
                st.warning("⚠️ Không tìm thấy dữ liệu HSTD tương ứng Số khế ước đã chọn.")
            else:
                ten_kh = str(row_hstd.get(COT_TEN_KH, "") or "")
                dia_chi = str(row_hstd.get(COT_DIA_CHI, "") or "")
                sdt = str(row_hstd.get(COT_SDT, "") or "")

                ngay_vay_str = ""
                try:
                    nv = pd.to_datetime(row_hstd.get(COT_NGAY_VAY, ""), errors="coerce", dayfirst=True)
                    if pd.notna(nv):
                        ngay_vay_str = nv.strftime("%d/%m/%Y")
                    else:
                        ngay_vay_str = str(row_hstd.get(COT_NGAY_VAY, "") or "")
                except Exception:
                    ngay_vay_str = str(row_hstd.get(COT_NGAY_VAY, "") or "")

                ngay_dh_str = ""
                try:
                    ndh = pd.to_datetime(row_hstd.get(COT_NGAY_DH, ""), errors="coerce", dayfirst=True)
                    if pd.notna(ndh):
                        ngay_dh_str = ndh.strftime("%d/%m/%Y")
                    else:
                        ngay_dh_str = str(row_hstd.get(COT_NGAY_DH, "") or "")
                except Exception:
                    ngay_dh_str = str(row_hstd.get(COT_NGAY_DH, "") or "")

                ten_ct = str(row_hstd.get(COT_TEN_CT, "") or "")
                muc_vay_vnd = _num(row_hstd.get(COT_MUC_VAY, 0) or 0)
                du_no_th_vnd = _num(row_hstd.get(COT_DU_NO_TH, 0) or 0)
                du_no_qh_vnd = _num(row_hstd.get(COT_DU_NO_QH, 0) or 0)
                du_no_goc_vnd = du_no_th_vnd + du_no_qh_vnd
                tong_du_no_vnd = _num(row_hstd.get(COT_TONG_DU_NO, 0) or 0)

                co_cot_lai_ton = COT_LAI_TON in df.columns
                lai_ton_vnd = _num(row_hstd.get(COT_LAI_TON, 0) or 0) if co_cot_lai_ton else 0.0

                ten_pgd_row = str(row_hstd.get(COT_TEN_PGD, "") or "")
                ten_nhcsxh = ten_pgd_row or (ten_pgd or "")

                st.info("BƯỚC 2 — Thông tin tự động điền (từ HSTD)")
                a1, a2 = st.columns(2)
                with a1:
                    st.markdown(f"**Tên KH:** {ten_kh or '—'}")
                    st.markdown(f"**Địa chỉ:** {dia_chi or '—'}")
                    st.markdown(f"**Số điện thoại:** {sdt or '—'}")
                    st.markdown(f"**Số khế ước:** {str(so_ku_chon) or '—'}")
                    st.markdown(f"**Ngày vay:** {ngay_vay_str or '—'}")
                    st.markdown(f"**Ngày đến hạn:** {ngay_dh_str or '—'}")
                with a2:
                    st.markdown(f"**Chương trình tín dụng:** {ten_ct or '—'}")
                    st.markdown(f"**Mức vay:** {fmt(muc_vay_vnd) if muc_vay_vnd else '—'}")
                    st.markdown(f"**Dư nợ gốc:** {fmt(du_no_goc_vnd) if du_no_goc_vnd else '—'}")
                    if co_cot_lai_ton:
                        st.markdown(f"**Lãi tồn:** {fmt(lai_ton_vnd) if lai_ton_vnd else '—'}")
                    else:
                        st.markdown("**Lãi tồn:** 0 (không có cột Lãi tồn)")
                    st.markdown(f"**Tổng dư nợ:** {fmt(tong_du_no_vnd) if tong_du_no_vnd else '—'}")
                    st.markdown(f"**NHCSXH/PGD:** {ten_nhcsxh or '—'}")

                with st.form("form_xln_soan", clear_on_submit=False):
                    st.markdown("BƯỚC 3 — Nhập phần tự thuật")
                    c_trai, c_phai = st.columns(2)
                    with c_trai:
                        nguyen_nhan = st.text_area(
                            "Nguyên nhân rủi ro",
                            height=110,
                            key="xln_nguyen_nhan",
                        )
                        thuc_trang = st.text_area(
                            "Thực trạng dự án / tài sản (chỉ dùng cho 02/XLN)",
                            height=90,
                            key="xln_thuc_trang",
                        )
                        kha_nang = st.text_area(
                            "Khả năng trả nợ",
                            height=70,
                            key="xln_kha_nang",
                        )
                    with c_phai:
                        muc_do_pct = st.number_input(
                            "Mức độ thiệt hại %",
                            min_value=0,
                            max_value=100,
                            value=0,
                            step=1,
                            key="xln_muc_do_pct",
                        )
                        so_tien_thiet_hai_trieu = st.number_input(
                            "Số tiền thiệt hại (triệu đồng)",
                            min_value=0.0,
                            value=0.0,
                            step=1.0,
                            key="xln_thiet_hai_trieu",
                        )
                        bien_phap = st.selectbox(
                            "Biện pháp đề nghị",
                            options=["Khoanh nợ", "Xóa nợ"],
                            key="xln_bien_phap",
                        )
                        so_thang = st.number_input(
                            "Số tháng đề nghị",
                            min_value=0,
                            max_value=120,
                            value=36,
                            step=1,
                            key="xln_so_thang",
                        )
                        ke_hoach = st.text_input(
                            "Kế hoạch trả nợ",
                            key="xln_ke_hoach",
                        )
                        ngay_lap = st.date_input(
                            "Ngày lập",
                            value=date.today(),
                            key="xln_ngay_lap",
                        )
                        dia_danh_default = _pgd_plain(ten_pgd_row or ten_pgd or "")
                        dia_danh = st.text_input(
                            "Địa danh",
                            value=dia_danh_default,
                            key="xln_dia_danh",
                        )

                    st.markdown("BƯỚC 4 — Xuất")
                    b1, b2, b3 = st.columns(3)
                    xuat_01 = b1.form_submit_button("📄 Xuất Word 01/XLN", type="primary")
                    xuat_02 = b2.form_submit_button("📋 Xuất Word 02/XLN")
                    xuat_pdf = b3.form_submit_button("📕 Xuất PDF")

                so_tien_thiet_hai_vnd = float(so_tien_thiet_hai_trieu) * 1_000_000.0

                du_lieu_xln = {
                    "ma_kh": str(row_hstd.get(COT_MA_KH, "") or ""),
                    "ten_kh": ten_kh,
                    "dia_chi": dia_chi,
                    "sdt": sdt,
                    "so_ku": str(so_ku_chon),
                    "ten_ct": ten_ct,
                    "muc_vay": fmt(muc_vay_vnd),
                    "tong_du_no": fmt(tong_du_no_vnd),
                    "du_no_goc": fmt(du_no_goc_vnd),
                    "lai_ton": fmt(lai_ton_vnd),
                    "nqh": fmt(du_no_qh_vnd),
                    "ngay_vay": ngay_vay_str,
                    "ngay_dh": ngay_dh_str,
                    "ten_to": str(row_hstd.get(COT_TEN_TO, "") or ""),
                    "dia_danh": str(dia_danh or ""),
                    "ten_nhcsxh": ten_nhcsxh,
                    "nguyen_nhan": str(nguyen_nhan or ""),
                    "bien_phap": str(bien_phap or ""),
                    "so_thang": str(int(so_thang)),
                    "so_tien_de_nghi": fmt(tong_du_no_vnd),
                    "so_tien_thiet_hai": fmt(so_tien_thiet_hai_vnd),
                    "muc_do_thiet_hai": str(int(muc_do_pct)),
                    "kha_nang_tra_no": str(kha_nang or ""),
                    "thuc_trang_du_an": str(thuc_trang or ""),
                    "ke_hoach_tra_no": str(ke_hoach or ""),
                    "dia_diem": ten_nhcsxh,
                    "can_bo_td": st.session_state.get("username", ""),
                    "ngay_ky": ngay_lap,
                    "ngay_lap": ngay_lap,
                    "thanh_phan": [
                        {
                            "stt": 1,
                            "ho_ten": st.session_state.get("username", ""),
                            "chuc_vu": "Cán bộ tín dụng",
                            "dai_dien": ten_nhcsxh,
                        },
                        {
                            "stt": 7,
                            "ho_ten": ten_kh,
                            "chuc_vu": "",
                            "dai_dien": "Khách hàng vay vốn",
                        },
                    ],
                }

                if xuat_01:
                    with st.spinner("Đang tạo 01/XLN..."):
                        docx_b = _tao_word_01xln(du_lieu_xln)
                    ten_file = f"Mau01XLN_{str(so_ku_chon) or 'KH'}_{date.today():%d%m%Y}"
                    nut_tai_word_va_pdf(docx_b, ten_file, "xln_01")
                    st.session_state["_xln_last_docx"] = docx_b
                    st.session_state["_xln_last_name"] = ten_file
                    db.ghi_audit(
                        username,
                        "xuat_01xln",
                        f"so_ku={str(so_ku_chon)} · pgd={ten_nhcsxh} · bien_phap={bien_phap}",
                    )

                if xuat_02:
                    with st.spinner("Đang tạo 02/XLN..."):
                        docx_b = _tao_word_02xln(du_lieu_xln)
                    ten_file = f"Mau02XLN_{str(so_ku_chon) or 'KH'}_{date.today():%d%m%Y}"
                    nut_tai_word_va_pdf(docx_b, ten_file, "xln_02")
                    st.session_state["_xln_last_docx"] = docx_b
                    st.session_state["_xln_last_name"] = ten_file
                    db.ghi_audit(
                        username,
                        "xuat_02xln",
                        f"so_ku={str(so_ku_chon)} · pgd={ten_nhcsxh} · bien_phap={bien_phap}",
                    )

                if xuat_pdf:
                    src_docx = st.session_state.get("_xln_last_docx")
                    ten_file = st.session_state.get("_xln_last_name")
                    if not src_docx:
                        with st.spinner("Đang tạo 02/XLN để xuất PDF..."):
                            src_docx = _tao_word_02xln(du_lieu_xln)
                        ten_file = f"Mau02XLN_{str(so_ku_chon) or 'KH'}_{date.today():%d%m%Y}"
                    pdf_b = docx_bytes_to_pdf(src_docx)
                    st.session_state["_xln_pdf_docx"] = src_docx
                    st.session_state["_xln_pdf_pdf"] = pdf_b
                    st.session_state["_xln_pdf_name"] = ten_file

                pdf_docx = st.session_state.get("_xln_pdf_docx")
                if pdf_docx:
                    ten_pdf = st.session_state.get("_xln_pdf_name", "MauXLN")
                    pdf_bytes = st.session_state.get("_xln_pdf_pdf")
                    d1, d2 = st.columns(2)
                    with d1:
                        st.download_button(
                            "⬇️ Tải Word (.docx)",
                            data=pdf_docx,
                            file_name=f"{ten_pdf}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="xln_pdf_dl_docx",
                        )
                    with d2:
                        if pdf_bytes:
                            st.download_button(
                                "⬇️ Tải PDF",
                                data=pdf_bytes,
                                file_name=f"{ten_pdf}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key="xln_pdf_dl_pdf",
                            )
                        else:
                            st.caption("⚠️ PDF: cần MS Word trên server. Vẫn có thể tải Word.")

                col_dl_01, col_dl_02 = st.columns(2)
                with col_dl_01:
                    hien_thi_nut_tai("xln_01")
                with col_dl_02:
                    hien_thi_nut_tai("xln_02")

        st.divider()

        _render_luong_nhap_ho_so(
            df_pgd=df,
            ten_pgd=ten_pgd or "",
            kv_key=kv_key,
            username=username,
            la_cn=False,
            key_prefix="",
        )
