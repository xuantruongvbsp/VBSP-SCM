"""Tab Ủy thác — Theo dõi Hội đoàn thể và các mẫu biểu kiểm tra."""


from __future__ import annotations
from logger import get_logger
logger = get_logger(__name__)

import io, os, pickle, uuid
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, normalize_role
from data.core import ts_file
from data.pgd import pgd_slug
from config import (
    COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON, COT_LAI_TON_QH,
    COT_SO_DU_TG, COT_NGAY_VAY, COT_TEN_TO, COT_DVUT,
    COT_TEN_XA, COT_TEN_THON, COT_MUC_VAY,
    TEN_CHI_NHANH_HIEN_THI, DS_PGD, PGD_XA_MAP, CACHE_HSTD,
)
from utils import fmt, fmt_bang_ty, fmt_ngay, fmt_so, xuat_excel
from services.uy_thac_service import (
    build_payload_bc_th,
    build_payload_bb_xac_minh,
    build_payload_ke_hoach,
    build_payload_mau06,
    build_payload_mau15,
    build_payload_mau16,
    cap_nhat_trang_thai_bien_ban,
    co_du_lieu_to,
    doc_bien_ban_theo_nam,
    doc_ds_bien_ban,
    kv_key_bb_ct_cx,
    loc_mau06,
    loc_mau15,
    luu_bien_ban,
    tinh_theo_dvut,
)
from services.template_service import (
    docx_bytes_to_pdf,
    tao_word_uythac_bb_ct_cx,
    tao_word_uythac_bb_xac_minh,
    tao_word_uythac_bc_th,
    tao_word_uythac_ke_hoach,
    tao_word_uythac_mau06,
    tao_word_uythac_mau15,
    tao_word_uythac_mau16,
)

# ── Hằng số ──────────────────────────────────────────────────────────────────
DVUT_ORDER = [
    "Hội nông dân",
    "Hội liên hiệp phụ nữ",
    "Hội cựu chiến binh",
    "Đoàn thanh niên",
]



# ══════════════════════════════════════════════════════════════════════════════
# CACHE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=300)
def _tinh_theo_dvut(_df_bytes: bytes) -> bytes:
    df = pickle.loads(_df_bytes)
    t = tinh_theo_dvut(df, dvut_order=DVUT_ORDER)
    return pickle.dumps(t)


@st.cache_data(show_spinner=False, ttl=300)
def _loc_mau06(_df_bytes: bytes, ngay_tu: str, ngay_den: str) -> bytes:
    df = pickle.loads(_df_bytes)
    result = loc_mau06(df, ngay_tu=ngay_tu, ngay_den=ngay_den)
    return pickle.dumps(result)


@st.cache_data(show_spinner=False, ttl=300)
def _loc_mau15(_df_bytes: bytes, ten_to: str) -> bytes:
    df = pickle.loads(_df_bytes)
    df_to = loc_mau15(df, ten_to=ten_to)
    return pickle.dumps(df_to)


@st.cache_data(show_spinner=False, ttl=300)
def _doc_hstd_cached(_ts: float = 0) -> pd.DataFrame:
    try:
        return pd.read_parquet(CACHE_HSTD)
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _download_word_pdf_pair(docx_bytes: bytes, ten_file: str, key_prefix: str) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Tải Word (.docx)",
            data=docx_bytes,
            file_name=ten_file + ".docx",
            mime="application/vnd.openxmlformats-officedocument"
                 ".wordprocessingml.document",
            key=f"{key_prefix}docx",
        )
    with col2:
        with st.spinner("Đang tạo PDF..."):
            pdf_bytes = docx_bytes_to_pdf(docx_bytes)
        if pdf_bytes:
            st.download_button(
                "⬇️ Tải PDF",
                data=pdf_bytes,
                file_name=ten_file + ".pdf",
                mime="application/pdf",
                key=f"{key_prefix}pdf",
            )
        else:
            st.caption("⚠️ PDF không khả dụng — cần MS Word trên server")


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB RENDERERS
# ══════════════════════════════════════════════════════════════════════════════

def _render_theo_dvut(df: pd.DataFrame) -> None:
    st.markdown("#### 📊 Thống kê theo Hội đoàn thể")
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu."); return
    try:
        t = pickle.loads(_tinh_theo_dvut(pickle.dumps(df)))
    except Exception as e:
        logger.error("_render_theo_dvut: lỗi tính thống kê DVUT — %s", e, exc_info=True)
        st.error("⚠️ Có lỗi khi tính thống kê theo Hội đoàn thể.")
        return
    if t.empty:
        st.info("Không có dữ liệu."); return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hội đoàn thể", len(t))
    c2.metric("Tổng Tổ TK&VV", fmt_so(int(t.get("so_to", pd.Series([0])).sum())))
    c3.metric("Tổng KH", fmt_so(int(t.get("so_kh", pd.Series([0])).sum())))
    c4.metric("Tổng dư nợ (triệu đồng)", fmt(t.get("tong_dn", pd.Series([0])).sum()))
    st.divider()
    hien = t.rename(columns={
        COT_DVUT: "Hội đoàn thể", "so_to": "Số Tổ",
        "so_kh": "Số KH", "tong_dn": "Dư nợ (tỷ)",
        "nqh": "NQH (tỷ)", "lai_ton": "Lãi tồn (tỷ)",
    })
    for col in ["Dư nợ (tỷ)", "NQH (tỷ)", "Lãi tồn (tỷ)"]:
        if col in hien.columns:
            hien[col] = hien[col].apply(fmt_bang_ty)
    st.dataframe(hien, use_container_width=True, hide_index=True)


def _render_ke_hoach(df: pd.DataFrame, pgd_user: str, role: str) -> None:
    st.markdown("#### 📋 Kế hoạch kiểm tra giám sát ủy thác")
    st.caption("Hội đoàn thể cấp xã lập (PGD) hoặc cấp tỉnh lập (CN). "
               "Danh sách Tổ TK&VV tự động lấy từ hệ thống.")

    if df is None or df.empty:
        st.warning("Chưa có dữ liệu.")
        return

    if (not la_phan_he_cn(role)) and not pgd_user:
        st.error("Không xác định được PGD.")
        return

    key_prefix_base = f"uyt_kh_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"

    if pgd_user and not la_phan_he_cn(role):
        st.info(f"PGD: **{pgd_user}**")
        pgd_chon = pgd_user
    else:
        if COT_TEN_PGD in df.columns:
            ds_pgd = sorted(df[COT_TEN_PGD].dropna().unique().tolist())
        else:
            ds_pgd = DS_PGD
        pgd_opt = st.selectbox(
            "Chọn PGD",
            options=["(Tất cả)"] + ds_pgd,
            key=f"{key_prefix_base}pgd",
        )
        pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt

    key_prefix = (
        f"{key_prefix_base}{pgd_slug(pgd_chon) if pgd_chon else 'all'}_"
    )

    df_src = df
    if pgd_chon and COT_TEN_PGD in df.columns:
        df_src = df[df[COT_TEN_PGD] == pgd_chon].copy()

    # Lấy danh sách Tổ từ df đã lọc
    ds_to = []
    grp = [c for c in [COT_DVUT, COT_TEN_XA, COT_TEN_TO] if c in df_src.columns]
    if grp:
        ds_to = (
            df_src[grp]
            .drop_duplicates()
            .sort_values(grp)
            .to_dict("records")
        )

    with st.form(f"{key_prefix}form"):
        c1, c2 = st.columns(2)
        don_vi_kt = c1.selectbox(
            "Hội đoàn thể kiểm tra",
            options=DVUT_ORDER,
            key=f"{key_prefix}don_vi_kt",
        )
        so_vb = c1.text_input(
            "Số văn bản",
            placeholder="VD: 12/KH-HND",
            key=f"{key_prefix}so_vb",
        )
        ds_xa_df = (
            sorted(df_src[COT_TEN_XA].dropna().unique().tolist())
            if COT_TEN_XA in df_src.columns
            else []
        )
        ds_xa_map = (
            list(PGD_XA_MAP.get(pgd_chon, []))
            if pgd_chon
            else [xa for ds in PGD_XA_MAP.values() for xa in ds]
        )
        ds_xa_kh = sorted(set(ds_xa_df) | set(ds_xa_map))
        if ds_xa_kh:
            dia_danh = c1.selectbox(
                "Địa danh (xã/phường)",
                options=ds_xa_kh,
                key=f"{key_prefix}dia_danh",
                help="Xã/phường nơi Hội đóng trụ sở — dùng làm địa danh ký văn bản",
            )
        else:
            dia_danh = c1.text_input(
                "Địa danh (xã/phường)",
                placeholder="Nhập xã/phường...",
                key=f"{key_prefix}dia_danh_txt",
            )
        nam_kh     = c2.number_input("Năm kế hoạch",
                                      value=date.today().year,
                                      min_value=2020, max_value=2035, step=1,
                                      key=f"{key_prefix}nam_kh")
        ngay_ky = c2.date_input("Ngày ký", value=date.today(), key=f"{key_prefix}ngay_ky")
        chu_tich = c2.text_input(
            "Chủ tịch ký",
            placeholder="Họ và tên Chủ tịch Hội",
            key=f"{key_prefix}chu_tich",
        )

        st.markdown("**I. Mục đích, yêu cầu**")
        muc_dich   = st.text_area("Mục đích", height=70, key=f"{key_prefix}muc_dich")
        yeu_cau    = st.text_area("Yêu cầu", height=70, key=f"{key_prefix}yeu_cau")

        st.markdown("**II. Kế hoạch kiểm tra**")
        noi_dung_kt = st.text_area(
            "Nội dung, thời hiệu kiểm tra",
            height=70,
            key=f"{key_prefix}noi_dung_kt",
        )
        thanh_phan  = st.text_area(
            "Thành phần Đoàn kiểm tra",
            height=60,
            key=f"{key_prefix}thanh_phan",
        )
        st.info(f"📋 Hệ thống tìm thấy **{len(ds_to)}** Tổ TK&VV "
                f"— sẽ tự động điền vào bảng Đối tượng kiểm tra.")

        st.markdown("**III. Kế hoạch giám sát**")
        noi_dung_gs  = st.text_area(
            "Nội dung, thời hiệu giám sát",
            height=70,
            key=f"{key_prefix}noi_dung_gs",
        )
        phan_cong_gs = st.text_area(
            "Phân công cán bộ giám sát",
            height=60,
            key=f"{key_prefix}phan_cong_gs",
        )

        st.markdown("**IV. Tổ chức thực hiện**")
        to_chuc = st.text_area("Tổ chức thực hiện", height=60, key=f"{key_prefix}to_chuc")

        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        context, ten_file = build_payload_ke_hoach(
            don_vi_kt=don_vi_kt, so_vb=so_vb, dia_danh=dia_danh,
            nam_kh=int(nam_kh), ngay_ky=ngay_ky, chu_tich=chu_tich,
            muc_dich=muc_dich, yeu_cau=yeu_cau,
            noi_dung_kt=noi_dung_kt, thanh_phan=thanh_phan,
            noi_dung_gs=noi_dung_gs, phan_cong_gs=phan_cong_gs,
            to_chuc=to_chuc, ds_to=ds_to,
        )
        with st.spinner("Đang tạo file..."):
            docx_bytes = tao_word_uythac_ke_hoach(context, ds_to)
        _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}kh_")


def _render_mau06(df: pd.DataFrame, pgd_user: str | None) -> None:
    st.markdown("#### 📋 Mẫu 06/TD & 06A/TD — Phiếu kiểm tra sử dụng vốn")
    st.caption("Quy định: kiểm tra 100% món vay trong 30 ngày sau giải ngân. "
               "Thời điểm kiểm tra cụ thể do CBTD nhập khi đi thực địa.")
    key_prefix_base = f"uyt_m06_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return
    if len(df.columns) < 15:
        st.error(
            f"⚠️ Dữ liệu HSTD chưa đầy đủ (chỉ {len(df.columns)} cột) — không thể lập Mẫu 06/TD.\n\n"
            "Cần upload/merge lại file HSTD đúng để tạo cache đầy đủ."
        )
        return
    if COT_NGAY_VAY not in df.columns:
        st.warning(f"Thiếu cột '{COT_NGAY_VAY}' trong dữ liệu HSTD — không thể lọc giải ngân để lập Mẫu 06/TD.")
        return

    if pgd_user:
        st.info(f"PGD: **{pgd_user}**")
        pgd_chon = pgd_user
    else:
        ds_pgd = (
            sorted(df[COT_TEN_PGD].dropna().unique().tolist())
            if COT_TEN_PGD in df.columns
            else DS_PGD
        )
        pgd_opt = st.selectbox(
            "Chọn PGD",
            options=["(Tất cả)"] + ds_pgd,
            key=f"{key_prefix_base}pgd",
        )
        pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt

    key_prefix = (
        f"{key_prefix_base}{pgd_slug(pgd_chon) if pgd_chon else 'all'}_"
    )

    df_src = df
    if pgd_chon and COT_TEN_PGD in df.columns:
        df_src = df[df[COT_TEN_PGD] == pgd_chon].copy()

    c1, c2 = st.columns(2)
    loai_mau = c1.radio("Loại mẫu", ["06/TD (bảng nhiều KH)",
                                       "06A/TD (từng KH riêng)"],
                        key=f"{key_prefix}loai")
    so_ngay  = c2.slider("Giải ngân trong N ngày qua", 7, 30, 30,
                         key=f"{key_prefix}ngay")
    st.caption("Ngày kiểm tra thực tế do Cán bộ hội đi kiểm tra ghi vào mẫu.")

    ngay_den = date.today()
    ngay_tu  = date.today() - timedelta(days=so_ngay)
    st.caption(f"📅 {ngay_tu.strftime('%d/%m/%Y')} → {ngay_den.strftime('%d/%m/%Y')}")

    try:
        raw    = _loc_mau06(pickle.dumps(df_src), str(ngay_tu), str(ngay_den))
        df_m06 = pickle.loads(raw)
    except Exception as e:
        logger.error("_render_mau06: lỗi lọc dữ liệu Mẫu 06 — %s", e, exc_info=True)
        st.error("⚠️ Có lỗi khi lọc dữ liệu Mẫu 06/TD.")
        return

    if df_m06.empty:
        st.success("✅ Không có món vay nào cần kiểm tra."); return

    tong_dn = df_m06[COT_TONG_DU_NO].sum() \
              if COT_TONG_DU_NO in df_m06.columns else 0
    ca, cb  = st.columns(2)
    ca.metric("Số món cần KT", fmt_so(len(df_m06)))
    cb.metric("Tổng dư nợ (triệu đồng)", fmt(tong_dn))
    st.dataframe(df_m06, use_container_width=True,
                 hide_index=True, height=300)

    # Form thông tin người kiểm tra
    with st.form(f"{key_prefix}form"):
        st.markdown("**Thông tin xuất mẫu:**")
        f1, f2 = st.columns(2)
        don_vi_kt = f1.selectbox(
            "Hội đoàn thể kiểm tra",
            options=DVUT_ORDER,
            key=f"{key_prefix}don_vi_kt"
        )
        ds_xa_m06 = [""] + sorted(df_m06[COT_TEN_XA].dropna().unique().tolist()) \
                    if COT_TEN_XA in df_m06.columns else [""]
        ten_xa = f1.selectbox(
            "Xã/Phường",
            options=ds_xa_m06,
            key=f"{key_prefix}ten_xa"
        )
        # Lọc Tổ theo Xã đã chọn (dùng session_state vì trong form)
        ten_xa_filter = st.session_state.get(f"{key_prefix}ten_xa", "")
        df_to_filter = df_m06[df_m06[COT_TEN_XA] == ten_xa_filter] \
                       if ten_xa_filter and COT_TEN_XA in df_m06.columns else df_m06
        ds_to_m06 = [""] + sorted(df_to_filter[COT_TEN_TO].dropna().unique().tolist()) \
                    if COT_TEN_TO in df_to_filter.columns else [""]
        ten_to = f1.selectbox(
            "Tổ TK&VV",
            options=ds_to_m06,
            key=f"{key_prefix}chon_to"
        )
        dia_ban = f1.text_input("Địa bàn kiểm tra",
                                placeholder="Ấp..., xã...",
                                key=f"{key_prefix}dia_ban")
        ngay_kt = f1.date_input("Ngày kiểm tra",
                                value=date.today(), key=f"{key_prefix}ngay_kt")

        can_bo_1  = f2.text_input("Cán bộ kiểm tra 1", key=f"{key_prefix}can_bo_1")
        chuc_vu_1 = f2.text_input("Chức vụ 1", key=f"{key_prefix}chuc_vu_1")
        can_bo_2  = f2.text_input("Cán bộ kiểm tra 2 (nếu có)", key=f"{key_prefix}can_bo_2")
        chuc_vu_2 = f2.text_input("Chức vụ 2 (nếu có)", key=f"{key_prefix}chuc_vu_2")

        st.markdown("**Nội dung nhận xét:**")
        nx1, nx2 = st.columns(2)
        nhan_xet_chung = nx1.text_area(
            "1. Tình hình thực hiện phương án vay vốn",
            key=f"{key_prefix}nx_chung", height=80,
        )
        so_kh_dung    = nx2.text_input("Số KH đúng mục đích", key=f"{key_prefix}so_kh_dung")
        so_tien_dung  = nx2.text_input("Số tiền đúng MĐ (triệu đ)", key=f"{key_prefix}tien_dung")
        ty_trong_dung = nx2.text_input("Tỷ trọng đúng MĐ (%)", key=f"{key_prefix}ty_dung")
        so_kh_sai     = nx2.text_input("Số KH sai mục đích", key=f"{key_prefix}so_kh_sai")
        so_tien_sai   = nx2.text_input("Số tiền sai MĐ (triệu đ)", key=f"{key_prefix}tien_sai")
        ty_trong_sai  = nx2.text_input("Tỷ trọng sai MĐ (%)", key=f"{key_prefix}ty_sai")
        bien_phap     = st.text_area("Biện pháp xử lý", key=f"{key_prefix}bien_phap", height=60)

        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        loai_word = "06" if "06/TD" in loai_mau else "06A"
        du_lieu_word, df_xuat, ten_file = build_payload_mau06(
            don_vi_kt=don_vi_kt, ten_xa=ten_xa, ten_to=ten_to,
            can_bo_1=can_bo_1, chuc_vu_1=chuc_vu_1,
            can_bo_2=can_bo_2, chuc_vu_2=chuc_vu_2,
            dia_ban=dia_ban, ngay_kt=ngay_kt,
            nhan_xet_chung=nhan_xet_chung,
            so_kh_dung=so_kh_dung, so_tien_dung=so_tien_dung,
            ty_trong_dung=ty_trong_dung,
            so_kh_sai=so_kh_sai, so_tien_sai=so_tien_sai,
            ty_trong_sai=ty_trong_sai,
            bien_phap=bien_phap,
            df_m06=df_m06,
            pgd_scope=pgd_chon or pgd_user or "ToanCN",
        )
        with st.spinner("Đang tạo file..."):
            docx_bytes = tao_word_uythac_mau06(du_lieu_word, df_xuat, loai=loai_word)
        _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}06_")


def _render_mau15(df: pd.DataFrame, pgd_user: str | None) -> None:
    st.markdown("#### 📋 Mẫu 15/TD — Danh sách đối chiếu số dư")
    st.caption("Đối chiếu nợ gốc, nợ lãi, số dư tiền gửi TK từng tổ viên.")
    key_prefix_base = f"uyt_m15_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return
    if len(df.columns) < 15:
        st.error(
            f"⚠️ Dữ liệu HSTD cache chưa đầy đủ (chỉ {len(df.columns)} cột) — "
            "không thể lập Mẫu 15/TD.\n\n"
            "Cần upload/merge lại file HSTD đúng để tạo cache đầy đủ."
        )
        return
    if COT_TEN_TO not in df.columns:
        st.warning(f"Thiếu cột '{COT_TEN_TO}' trong dữ liệu HSTD — không thể lập Mẫu 15/TD.")
        return

    if pgd_user:
        st.info(f"PGD: **{pgd_user}**")
        pgd_chon = pgd_user
    else:
        ds_pgd = (
            sorted(df[COT_TEN_PGD].dropna().unique().tolist())
            if COT_TEN_PGD in df.columns
            else DS_PGD
        )
        pgd_opt = st.selectbox(
            "Chọn PGD",
            options=["(Tất cả)"] + ds_pgd,
            key=f"{key_prefix_base}pgd",
        )
        pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt

    key_prefix = (
        f"{key_prefix_base}{pgd_slug(pgd_chon) if pgd_chon else 'all'}_"
    )

    df_src = df
    if pgd_chon and COT_TEN_PGD in df.columns:
        df_src = df[df[COT_TEN_PGD] == pgd_chon].copy()

    # Chọn Tổ TK&VV
    if not co_du_lieu_to(df_src):
        st.warning(f"Không có dữ liệu '{COT_TEN_TO}' trong phạm vi đã chọn.")
        return
    ds_to = (
        sorted(
            df_src[COT_TEN_TO]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .unique()
            .tolist()
        )
        if COT_TEN_TO in df_src.columns
        else []
    )
    if not ds_to:
        st.warning("Không có dữ liệu Tổ TK&VV."); return

    c1, c2 = st.columns(2)
    chon_dvut = c1.selectbox("Hội đoàn thể", ["Tất cả"] + DVUT_ORDER,
                              key=f"{key_prefix}dvut")
    # Lọc Tổ theo DVUT
    df_filter = df_src.copy()
    if chon_dvut != "Tất cả" and COT_DVUT in df_filter.columns:
        df_filter = df_filter[df_filter[COT_DVUT] == chon_dvut]
    ds_to_filter = sorted(df_filter[COT_TEN_TO].dropna().unique().tolist()) \
                   if COT_TEN_TO in df_filter.columns else []
    chon_to = c2.selectbox("Tổ TK&VV", ds_to_filter, key=f"{key_prefix}to")

    if not chon_to:
        st.info("Chọn Tổ TK&VV để xem dữ liệu."); return

    try:
        df_to = pickle.loads(_loc_mau15(pickle.dumps(df_src), chon_to))
    except Exception as e:
        logger.error("_render_mau15: lỗi lọc dữ liệu Mẫu 15 — %s", e, exc_info=True)
        st.error("⚠️ Có lỗi khi lọc dữ liệu Mẫu 15/TD.")
        return

    if df_to.empty:
        st.info(f"Không có dữ liệu cho Tổ **{chon_to}**."); return

    # KPI
    tong_goc = df_to[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_to.columns else 0
    tong_lai = df_to["Nợ lãi"].sum() if "Nợ lãi" in df_to.columns else 0
    tong_tg  = df_to[COT_SO_DU_TG].sum() if COT_SO_DU_TG in df_to.columns else 0
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Số KH", fmt_so(len(df_to)))
    k2.metric("Tổng nợ gốc (triệu đồng)", fmt(tong_goc))
    k3.metric("Tổng nợ lãi (triệu đồng)", fmt(tong_lai))
    k4.metric("Tổng TG TK (triệu đồng)", fmt(tong_tg))
    st.dataframe(df_to, use_container_width=True, hide_index=True, height=350)

    # Tự động lấy xã và tổ trưởng từ Tổ đang chọn
    xa_cua_to = ""
    ten_to_truong = ""
    if chon_to:
        if COT_TEN_XA in df_src.columns and COT_TEN_TO in df_src.columns:
            s_xa = df_src[df_src[COT_TEN_TO] == chon_to][COT_TEN_XA].dropna()
            xa_cua_to = s_xa.iloc[0] if not s_xa.empty else ""
        for cot in ["Tên Tổ trưởng", "Tổ trưởng", "Họ tên Tổ trưởng"]:
            if cot in df_src.columns:
                s_tt = df_src[df_src[COT_TEN_TO] == chon_to][cot].dropna()
                ten_to_truong = str(s_tt.iloc[0]) if not s_tt.empty else ""
                break

    # Form xuất Word
    with st.form(f"{key_prefix}form"):
        st.markdown("**Thông tin xuất mẫu:**")
        f1, f2 = st.columns(2)
        pgd = f1.text_input(
            "PGD",
            value=pgd_chon or pgd_user or "",
            disabled=True,
            key=f"{key_prefix}pgd"
        )
        ten_xa = f1.text_input(
            "Xã/Phường",
            value=xa_cua_to,
            disabled=True,
            help="Tự động lấy theo Tổ TK&VV đã chọn",
            key=f"{key_prefix}ten_xa"
        )
        to_truong = f1.text_input(
            "Tổ trưởng",
            value=ten_to_truong,
            help="Tự động lấy từ HSTD, có thể sửa lại nếu cần",
            key=f"{key_prefix}to_truong"
        )
        ma_to     = f1.text_input("Mã Tổ")
        dia_chi   = f2.text_input("Địa chỉ Tổ")
        can_bo_kt = f2.text_input("Cán bộ đối chiếu")
        ngay_chot = f2.date_input("Ngày chốt số liệu", value=date.today(),
                                  key=f"{key_prefix}ngay_chot")
        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        with st.spinner("Đang tạo file..."):
            du_lieu_word, ten_file = build_payload_mau15(
                pgd=pgd, ten_xa=ten_xa, ten_to=chon_to,
                to_truong=to_truong, ma_to=ma_to,
                dia_chi=dia_chi, can_bo_kt=can_bo_kt,
                ngay_chot=ngay_chot, pgd_scope=pgd_chon or pgd_user or "",
            )
            docx_bytes = tao_word_uythac_mau15(du_lieu_word, df_to)
        _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}15_")


def _render_bien_ban(df: pd.DataFrame, pgd_user: str | None) -> None:
    st.markdown("#### 📋 Biên bản & Báo cáo tổng hợp")
    key_prefix_base = f"uyt_bb_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    loai = st.radio(
        "Loại biên bản",
        [
            "📋 Mẫu 16/TD — Kiểm tra CT-XH Tổ TK&VV",
            "📄 Biên bản xác minh nợ chiếm dụng",
            "📊 Báo cáo tổng hợp ủy thác (Excel)",
        ],
        horizontal=True,
        key=f"{key_prefix_base}loai",
    )

    if pgd_user:
        st.info(f"PGD: **{pgd_user}**")
        pgd_chon = pgd_user
    else:
        if df is not None and (not df.empty) and COT_TEN_PGD in df.columns:
            ds_pgd = sorted(df[COT_TEN_PGD].dropna().unique().tolist())
        else:
            ds_pgd = DS_PGD
        pgd_opt = st.selectbox(
            "Chọn PGD",
            options=["(Tất cả)"] + ds_pgd,
            key=f"{key_prefix_base}pgd",
        )
        pgd_chon = None if pgd_opt == "(Tất cả)" else pgd_opt

    key_prefix = f"{key_prefix_base}{pgd_slug(pgd_chon) if pgd_chon else 'all'}_"

    if loai.startswith("📄"):
        df_src = pd.DataFrame()
    else:
        if df is None or df.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return
        df_src = df
        if pgd_chon and COT_TEN_PGD in df.columns:
            df_src = df[df[COT_TEN_PGD] == pgd_chon].copy()

    if loai.startswith("📋"):
        with st.form(f"{key_prefix}form_m16"):
            c1, c2 = st.columns(2)
            don_vi_kt = c1.selectbox("Hội đoàn thể kiểm tra", DVUT_ORDER, key=f"{key_prefix}dvkt")
            ds_xa_bb = (
                sorted(df_src[COT_TEN_XA].dropna().unique().tolist())
                if COT_TEN_XA in df_src.columns else []
            )
            ten_xa = c1.selectbox("Xã/Phường", [""] + ds_xa_bb, key=f"{key_prefix}xa")
            ten_xa_cur = st.session_state.get(f"{key_prefix}xa", "")
            df_to_filter = (
                df_src[df_src[COT_TEN_XA] == ten_xa_cur]
                if ten_xa_cur and COT_TEN_XA in df_src.columns else df_src
            )
            ds_to_bb = (
                sorted(df_to_filter[COT_TEN_TO].dropna().unique().tolist())
                if COT_TEN_TO in df_to_filter.columns else []
            )
            ten_to = c1.selectbox("Tổ TK&VV", [""] + ds_to_bb, key=f"{key_prefix}to")
            ten_thon = c1.text_input(
                "Thôn/tổ dân phố",
                help="Địa chỉ thôn của Tổ TK&VV",
                key=f"{key_prefix}thon",
            )

            # Auto-detect tổ trưởng và hội đoàn thể từ df
            _to_truong_auto = ""
            _hoi_auto = ""
            if ten_to and COT_TEN_TO in df_src.columns:
                s_tt = df_src[df_src[COT_TEN_TO] == ten_to]
                for cot_tt in ["Tên Tổ trưởng", "Tổ trưởng", "Họ tên Tổ trưởng"]:
                    if cot_tt in df_src.columns:
                        v = s_tt[cot_tt].dropna()
                        if not v.empty:
                            _to_truong_auto = str(v.iloc[0])
                            break
                if COT_DVUT in df_src.columns:
                    v = s_tt[COT_DVUT].dropna()
                    if not v.empty:
                        _hoi_auto = str(v.iloc[0])

            hoi_doan_the = c1.text_input(
                "Tổ thuộc Hội", value=_hoi_auto, key=f"{key_prefix}hoi",
                help="Hội quản lý tổ (tự điền từ dữ liệu, có thể sửa)",
            )
            to_truong = c2.text_input(
                "Tổ trưởng Tổ TK&VV", value=_to_truong_auto, key=f"{key_prefix}totruong",
            )
            to_pho = c2.text_input("Tổ phó (nếu có)", key=f"{key_prefix}topho")
            can_bo_1 = c2.text_input("Cán bộ kiểm tra 1", key=f"{key_prefix}cb1")
            chuc_vu_1 = c2.text_input("Chức vụ 1", key=f"{key_prefix}cv1")
            can_bo_2 = c2.text_input("Cán bộ kiểm tra 2 (nếu có)", key=f"{key_prefix}cb2")
            chuc_vu_2 = c2.text_input("Chức vụ 2", key=f"{key_prefix}cv2")
            ngay_kt = c2.date_input("Ngày kiểm tra", value=date.today(), key=f"{key_prefix}ngay")

            st.markdown("**Phần I — Tình hình chung (để trống = lấy từ HSTD)**")
            pi1, pi2 = st.columns(2)
            ty_le_nqh = pi1.text_input(
                "Tỷ lệ NQH (%)", placeholder="VD: 0,0 (để trống = tự tính)",
                key=f"{key_prefix}tylnqh",
            )
            xep_loai_to = pi2.text_input(
                "Kết quả xếp loại Tổ", placeholder="VD: Loại Tốt", key=f"{key_prefix}xeploai",
            )

            st.markdown("**Phần III — Đánh giá, nhận xét**")
            so_kh_kt = st.text_input(
                "Số KH kiểm tra thực tế", placeholder="VD: 05", key=f"{key_prefix}sokh",
            )
            t1, t2 = st.columns(2)
            uu_diem  = t1.text_area("1. Ưu điểm", height=80, key=f"{key_prefix}uudiem")
            ton_tai  = t2.text_area("2. Tồn tại", height=80, key=f"{key_prefix}tontai")
            kien_nghi = st.text_area("3. Kiến nghị (nếu có)", height=70, key=f"{key_prefix}kiennghi")
            so_phieu = st.text_input(
                "Số phiếu kiểm tra kèm theo", placeholder="VD: 05", key=f"{key_prefix}sophieu",
            )
            submitted_m16 = st.form_submit_button("📄 Tạo Word", type="primary")

        if submitted_m16:
            du_lieu, df_xuat, ten_file = build_payload_mau16(
                don_vi_kt=don_vi_kt, ten_xa=ten_xa, ten_thon=ten_thon,
                ten_to=ten_to, hoi_doan_the=hoi_doan_the,
                to_truong=to_truong, to_pho=to_pho,
                can_bo_1=can_bo_1, chuc_vu_1=chuc_vu_1,
                can_bo_2=can_bo_2, chuc_vu_2=chuc_vu_2,
                ngay_kt=ngay_kt,
                ty_le_nqh=ty_le_nqh, xep_loai_to=xep_loai_to,
                so_kh_kt_thuc_te=so_kh_kt,
                uu_diem=uu_diem, ton_tai=ton_tai,
                kien_nghi=kien_nghi, so_phieu_kem_theo=so_phieu,
                df_src=df_src,
            )
            with st.spinner("Đang tạo file..."):
                docx_bytes = tao_word_uythac_mau16(du_lieu, df_xuat)
            _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}m16_")

        return

    if loai.startswith("📄"):
        with st.form(f"{key_prefix}form_xm"):
            c1, c2 = st.columns(2)
            ten_kh = c1.text_input("Họ tên khách hàng", key=f"{key_prefix}xm_kh")
            so_ku = c1.text_input("Số khế ước", key=f"{key_prefix}xm_sku")
            so_tien = c1.number_input(
                "Số tiền chiếm dụng (triệu đồng)",
                min_value=0.0,
                step=0.1,
                key=f"{key_prefix}xm_sotien",
            )
            can_bo_lap = c2.text_input("Cán bộ lập biên bản", key=f"{key_prefix}xm_cb")
            ngay_lap = c2.date_input("Ngày lập", value=date.today(), key=f"{key_prefix}xm_ngay")
            ly_do = st.text_area("Lý do / Hoàn cảnh", height=80, key=f"{key_prefix}xm_lydo")
            bien_phap = st.text_area("Biện pháp xử lý", height=80, key=f"{key_prefix}xm_bien_phap")
            submitted_xm = st.form_submit_button("📄 Tạo Word", type="primary")

        if submitted_xm:
            du_lieu, ten_file = build_payload_bb_xac_minh(
                ten_kh=ten_kh, so_ku=so_ku, so_tien=so_tien,
                ly_do=ly_do, bien_phap=bien_phap,
                can_bo_lap=can_bo_lap, ngay_lap=ngay_lap,
                pgd_scope=pgd_chon or pgd_user or "ToanCN",
            )
            with st.spinner("Đang tạo file..."):
                docx_bytes = tao_word_uythac_bb_xac_minh(du_lieu)
            _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}xm_")
        return

    try:
        df_th = pickle.loads(_tinh_theo_dvut(pickle.dumps(df_src)))
    except Exception as e:
        logger.error("_render_bien_ban: lỗi tính tổng hợp DVUT — %s", e, exc_info=True)
        st.error("⚠️ Có lỗi khi tính tổng hợp theo Hội đoàn thể.")
        df_th = pd.DataFrame()

    if df_th.empty:
        st.info("Không có dữ liệu.")
        return

    hien = df_th.rename(
        columns={
            COT_DVUT: "Hội đoàn thể",
            "so_to": "Số Tổ TK&VV",
            "so_kh": "Số hộ vay",
            "tong_dn": "Dư nợ (triệu đồng)",
            "nqh": "NQH (triệu đồng)",
            "lai_ton": "Lãi tồn (triệu đồng)",
        }
    )
    for col in ["Dư nợ (triệu đồng)", "NQH (triệu đồng)", "Lãi tồn (triệu đồng)"]:
        if col in hien.columns:
            hien[col] = hien[col].apply(fmt)
    st.dataframe(hien, use_container_width=True, hide_index=True)

    pgd_scope = pgd_chon or pgd_user or "ToanCN"
    ten_file = f"TongHopUyThac_{pgd_slug(pgd_scope)}_{date.today().strftime('%d%m%Y')}.xlsx"
    _xls_key = f"_xls_{key_prefix}uy_thac_th"
    if st.button("⬇️ Tạo Excel", key=f"{key_prefix}th_gen", use_container_width=False):
        try:
            st.session_state[_xls_key] = xuat_excel({"Tổng hợp ủy thác": hien})
        except Exception as e:
            logger.error("tab_uy_thac xuat_excel: %s", e, exc_info=True)
            st.error(f"❌ Lỗi xuất Excel: {e}")
    if st.session_state.get(_xls_key):
        if st.download_button(
            "📥 Tải Excel",
            data=st.session_state[_xls_key],
            file_name=ten_file,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}th_dl",
        ):
            db.ghi_audit(
                st.session_state.get("username", "unknown"),
                "xuat_bieu_cn",
                f"Tổng hợp ủy thác — {pgd_chon or pgd_user or '(Tất cả)'}",
            )


def _render_bb_ct_cx(df: pd.DataFrame, pgd_user: str | None,
                     username: str, role: str) -> None:
    """Sub-tab 3 — Nhập + lưu Mẫu 02/BB-CT và 03/BB-CX với theo dõi tiến độ."""
    st.markdown("#### 📝 Biên bản kiểm tra tổ chức CT-XH (Mẫu 02/BB-CT & 03/BB-CX)")
    st.caption(
        "Nhập kết quả kiểm tra và lưu vào hệ thống để theo dõi tiến độ xử lý kiến nghị. "
        "Xuất Word/PDF trực tiếp từ dữ liệu đã lưu."
    )

    key_prefix_base = f"uyt_bbctx_{pgd_slug(pgd_user) if pgd_user else 'cn'}_"
    loai_sel = st.radio(
        "Loại biên bản",
        ["02/BB-CT — Tổ chức CT-XH cấp tỉnh", "03/BB-CX — Tổ chức CT-XH cấp xã"],
        horizontal=True, key=f"{key_prefix_base}loai",
    )
    cap = "tinh" if "CT" in loai_sel else "xa"

    c_nam, c_pgd = st.columns(2)
    nam = int(c_nam.number_input(
        "Năm", value=date.today().year,
        min_value=2020, max_value=2035, step=1, key=f"{key_prefix_base}nam",
    ))

    if pgd_user:
        scope = pgd_user
        c_pgd.info(f"Đơn vị: **{pgd_user}**")
    else:
        scope = c_pgd.selectbox(
            "PGD / Đơn vị quản lý hồ sơ",
            options=DS_PGD, key=f"{key_prefix_base}pgd_sel",
        )

    key_prefix = f"{key_prefix_base}{pgd_slug(scope) if scope else 'cn'}_"
    kv_key = kv_key_bb_ct_cx(cap=cap, scope=scope, nam=nam)

    ds_luu: list = doc_ds_bien_ban(kv_key)

    # ── Danh sách biên bản đã lưu ──────────────────────────────────────────
    if ds_luu:
        so_hieu_mau = "02/BB-CT" if cap == "tinh" else "03/BB-CX"
        st.markdown(f"##### Biên bản {so_hieu_mau} đã lưu — {scope} ({nam})")
        for bb in reversed(ds_luu):
            tt = bb.get("trang_thai", "cho_xu_ly")
            tt_label = {
                "cho_xu_ly": "🔴 Chờ xử lý",
                "da_xu_ly": "✅ Đã xử lý",
                "khong_ton_tai": "🟢 Không tồn tại",
            }.get(tt, tt)
            ngay_str = bb.get("ngay_kt", "")
            ngay_hien_thi = fmt_ngay(ngay_str)
            ten_dv = bb.get("ten_don_vi", "")
            with st.expander(
                f"[{so_hieu_mau}] {ngay_hien_thi} — {ten_dv} | {tt_label}"
            ):
                col_i1, col_i2 = st.columns(2)
                col_i1.markdown(f"**Đơn vị KT:** {bb.get('don_vi_kt', '')}")
                col_i1.markdown(f"**Trưởng đoàn:** {bb.get('truong_doan', '')}")
                col_i2.markdown(f"**Đại diện được KT:** {bb.get('dai_dien_dc', '')}")
                col_i2.markdown(f"**Hạn hoàn thành:** {fmt_ngay(bb.get('han_hoan_thanh', ''))}")
                if bb.get("kien_nghi"):
                    st.markdown(f"**Kiến nghị:** {bb['kien_nghi']}")
                if bb.get("ket_qua_xu_ly"):
                    st.markdown(f"**Kết quả xử lý:** {bb['ket_qua_xu_ly']}")

                rec_id = bb.get("id", "")
                ten_file = (
                    f"{'BB_CT' if cap == 'tinh' else 'BB_CX'}"
                    f"_{ten_dv[:20].replace(' ', '_')}"
                    f"_{ngay_str.replace('-', '')}"
                )
                ss_key = f"bbct_bytes_{rec_id}"
                if st.button("📄 Tạo Word / PDF", key=f"{key_prefix}gen_{rec_id}"):
                    st.session_state[ss_key] = tao_word_uythac_bb_ct_cx(
                        bb, cap=bb.get("loai_cap", cap)
                    )
                if ss_key in st.session_state:
                    docx_b = st.session_state[ss_key]
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        st.download_button(
                            "⬇️ Tải Word",
                            data=docx_b,
                            file_name=ten_file + ".docx",
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".wordprocessingml.document",
                            key=f"{key_prefix}dl_{rec_id}",
                        )
                    with col_e2:
                        with st.spinner("Đang tạo PDF..."):
                            pdf_b = docx_bytes_to_pdf(docx_b)
                        if pdf_b:
                            st.download_button(
                                "⬇️ Tải PDF",
                                data=pdf_b,
                                file_name=ten_file + ".pdf",
                                mime="application/pdf",
                                key=f"{key_prefix}pdf_{rec_id}",
                            )
                        else:
                            st.caption("⚠️ PDF không khả dụng — cần MS Word trên server")
        st.divider()

    # ── Form nhập biên bản mới ─────────────────────────────────────────────
    so_hieu_label = "02/BB-CT" if cap == "tinh" else "03/BB-CX"
    st.markdown(f"##### Nhập biên bản {so_hieu_label} mới")

    with st.form(f"{key_prefix}form_{cap}_moi", clear_on_submit=True):
        st.markdown("**Thông tin chung**")
        fc1, fc2 = st.columns(2)
        dvut      = fc1.selectbox("Hội đoàn thể kiểm tra", DVUT_ORDER,  key=f"{key_prefix}dvut_{cap}")
        don_vi_kt = fc1.text_input("Tên đơn vị kiểm tra (đầy đủ)",      key=f"{key_prefix}dvkt_{cap}")
        ten_don_vi = fc1.text_input("Đơn vị được kiểm tra",              key=f"{key_prefix}dvdc_{cap}",
                                    placeholder="Hội ... xã/tỉnh ...")
        ngay_kt    = fc2.date_input("Ngày kiểm tra", value=date.today(), key=f"{key_prefix}ngay_{cap}")
        truong_doan = fc2.text_input("Trưởng đoàn kiểm tra",             key=f"{key_prefix}td_{cap}")
        can_bo_2   = fc2.text_input("Cán bộ kiểm tra 2 (nếu có)",       key=f"{key_prefix}cb2_{cap}")
        dai_dien_dc = fc2.text_input("Đại diện đơn vị được kiểm tra",   key=f"{key_prefix}dddc_{cap}")
        chuc_vu_dc = fc2.text_input("Chức vụ đại diện",                  key=f"{key_prefix}cvdc_{cap}")

        st.markdown("**II. Kết quả thực hiện (theo Phụ lục I VB 727)**")
        muc_list = [
            ("tuyen_truyen",    "1. Công tác tuyên truyền, vận động"),
            ("kiem_tra_giam_sat", "2. Công tác kiểm tra, giám sát"),
            ("tap_huan",        "3. Công tác tập huấn"),
            ("phoi_hop_nhcs",   "4. Hoạt động phối hợp với NHCSXH"),
        ]
        if cap == "tinh":
            muc_list.append(("trach_nhiem", "5. Trách nhiệm của tổ chức CT-XH cấp tỉnh"))

        nd_results: dict[str, dict] = {}
        for field_key, ten_muc in muc_list:
            st.markdown(f"*{ten_muc}*")
            mc1, mc2 = st.columns(2)
            kq = mc1.text_area("a) Kết quả", height=60, key=f"{key_prefix}{field_key}_kq_{cap}")
            tt_nd = mc2.text_area("b) Tồn tại", height=60, key=f"{key_prefix}{field_key}_tt_{cap}")
            nd_results[field_key] = {"ket_qua": kq, "ton_tai": tt_nd}

        st.markdown("**III. Đánh giá, Nhận xét & Kiến nghị**")
        ek1, ek2 = st.columns(2)
        uu_diem     = ek1.text_area("Ưu điểm",        height=80, key=f"{key_prefix}uu_{cap}")
        ton_tai_ch  = ek2.text_area("Tồn tại chung",  height=80, key=f"{key_prefix}tt_{cap}")
        kien_nghi   = st.text_area("Kiến nghị",       height=80, key=f"{key_prefix}kn_{cap}")

        hk1, hk2 = st.columns(2)
        han_ht = hk1.date_input("Hạn hoàn thành kiến nghị",
                                  value=date.today(), key=f"{key_prefix}han_{cap}")
        tt_sel = hk2.selectbox(
            "Trạng thái tồn tại",
            options=["cho_xu_ly", "khong_ton_tai"],
            format_func=lambda x: {
                "cho_xu_ly": "🔴 Có tồn tại — chờ xử lý",
                "khong_ton_tai": "🟢 Không có tồn tại",
            }.get(x, x),
            key=f"{key_prefix}tt_select_{cap}",
        )
        y_kien = st.text_area("IV. Ý kiến đơn vị được kiểm tra", height=60,
                               key=f"{key_prefix}ykien_{cap}")
        submitted = st.form_submit_button("💾 Lưu biên bản", type="primary")

    if submitted:
        new_id = uuid.uuid4().hex[:8]
        record = {
            "id":           new_id,
            "kv_key":       kv_key,
            "loai":         "CT" if cap == "tinh" else "CX",
            "loai_cap":     cap,
            "ngay_kt":      ngay_kt.strftime("%Y-%m-%d"),
            "dvut":         dvut,
            "don_vi_kt":    don_vi_kt,
            "ten_don_vi":   ten_don_vi,
            "truong_doan":  truong_doan,
            "can_bo_2":     can_bo_2,
            "dai_dien_dc":  dai_dien_dc,
            "chuc_vu_dc":   chuc_vu_dc,
            "dia_danh":     scope,
            **nd_results,
            "uu_diem":       uu_diem,
            "ton_tai_chung": ton_tai_ch,
            "kien_nghi":     kien_nghi,
            "han_hoan_thanh": han_ht.strftime("%Y-%m-%d"),
            "trang_thai":    tt_sel,
            "y_kien_don_vi_dc": y_kien,
            "ket_qua_xu_ly": "",
            "ngay_cap_nhat": date.today().strftime("%Y-%m-%d"),
            "nguoi_cap_nhat": username,
        }
        luu_bien_ban(kv_key=kv_key, ds_hien_tai=ds_luu, record=record, username=username)
        st.success(
            f"✅ Đã lưu biên bản {'02/BB-CT' if cap == 'tinh' else '03/BB-CX'} — {ten_don_vi}"
        )
        st.rerun()


def _render_theo_doi_bc_th(pgd_user: str | None,
                            username: str, role: str) -> None:
    """Sub-tab 7 — Theo dõi tiến độ xử lý kiến nghị + xuất Mẫu 04/BC-TH."""
    st.markdown("#### 📊 Theo dõi tiến độ & Báo cáo tổng hợp (Mẫu 04/BC-TH)")
    slug = pgd_slug(pgd_user) if pgd_user else "cn"
    key_prefix = f"uyt_td_{slug}_"

    # ── Section 1: Theo dõi ────────────────────────────────────────────────
    st.markdown("##### I. Theo dõi tiến độ xử lý kiến nghị")

    tc1, tc2, tc3 = st.columns(3)
    nam_td = int(tc1.number_input(
        "Năm", value=date.today().year,
        min_value=2020, max_value=2035, step=1, key=f"{key_prefix}nam",
    ))
    loai_td = tc2.selectbox(
        "Loại", ["Tất cả", "BB-CT (cấp tỉnh)", "BB-CX (cấp xã)"], key=f"{key_prefix}loai"
    )
    tt_td = tc3.selectbox(
        "Trạng thái",
        ["Tất cả", "Chờ xử lý", "Đã xử lý", "Không tồn tại"],
        key=f"{key_prefix}tt",
    )

    # Load records
    all_records: list[dict] = doc_bien_ban_theo_nam(nam=nam_td, pgd_user=pgd_user)

    # Filter theo loại
    if "BB-CT" in loai_td:
        all_records = [r for r in all_records if r.get("loai") == "CT"]
    elif "BB-CX" in loai_td:
        all_records = [r for r in all_records if r.get("loai") == "CX"]

    # Filter theo trạng thái
    tt_map = {"Chờ xử lý": "cho_xu_ly", "Đã xử lý": "da_xu_ly",
              "Không tồn tại": "khong_ton_tai"}
    if tt_td != "Tất cả":
        all_records = [r for r in all_records if r.get("trang_thai") == tt_map.get(tt_td)]

    if not all_records:
        st.info("Chưa có biên bản nào trong kỳ này.")
    else:
        rows = []
        for r in sorted(all_records, key=lambda x: x.get("ngay_kt", ""), reverse=True):
            tt = r.get("trang_thai", "cho_xu_ly")
            tt_label = {
                "cho_xu_ly": "🔴 Chờ xử lý",
                "da_xu_ly": "✅ Đã xử lý",
                "khong_ton_tai": "🟢 Không tồn tại",
            }.get(tt, tt)
            mau_so = "02/BB-CT" if r.get("loai") == "CT" else "03/BB-CX"
            kn_text = r.get("kien_nghi") or ""
            rows.append({
                "ID": r.get("id", ""),
                "Mẫu số": mau_so,
                "Ngày KT": fmt_ngay(r.get("ngay_kt", "")),
                "Đơn vị được KT": r.get("ten_don_vi", ""),
                "Kiến nghị": kn_text[:80] + "..." if len(kn_text) > 80 else kn_text,
                "Hạn hoàn thành": fmt_ngay(r.get("han_hoan_thanh", "")),
                "Trạng thái": tt_label,
                "Kết quả xử lý": r.get("ket_qua_xu_ly", ""),
            })
        df_td = pd.DataFrame(rows)
        st.dataframe(
            df_td.drop(columns=["ID"]),
            use_container_width=True, hide_index=True,
        )

        # Cập nhật trạng thái (chỉ CN role)
        if la_phan_he_cn(role):
            st.markdown("**Cập nhật trạng thái xử lý:**")
            cho_xu_ly = [r for r in all_records if r.get("trang_thai") == "cho_xu_ly"]
            if not cho_xu_ly:
                st.success("✅ Tất cả kiến nghị đã được xử lý.")
            else:
                opt_map = {
                    f"{fmt_ngay(r.get('ngay_kt',''))} — {r.get('ten_don_vi','')} [{r.get('id','')}]": r
                    for r in cho_xu_ly
                }
                chon_label = st.selectbox(
                    "Chọn biên bản cần cập nhật",
                    options=[""] + list(opt_map.keys()),
                    key=f"{key_prefix}chon_label",
                )
                if chon_label:
                    target = opt_map[chon_label]
                    ket_qua_xl = st.text_area(
                        "Kết quả xử lý", height=60, key=f"{key_prefix}kq_xl"
                    )
                    if st.button("✅ Đánh dấu đã xử lý", key=f"{key_prefix}btn_xl"):
                        kv_key_t = target.get("kv_key", "")
                        if kv_key_t:
                            ok = cap_nhat_trang_thai_bien_ban(
                                kv_key=kv_key_t,
                                rec_id=str(target.get("id", "")),
                                ket_qua_xu_ly=ket_qua_xl,
                                username=username,
                                ten_don_vi=str(target.get("ten_don_vi", "") or ""),
                            )
                            if ok:
                                st.success("✅ Đã cập nhật trạng thái!")
                                st.rerun()
                            else:
                                st.error("⚠️ Không tìm thấy biên bản để cập nhật (dữ liệu có thể đã thay đổi).")

    st.divider()

    # ── Section 2: Xuất BC-TH ──────────────────────────────────────────────
    st.markdown("##### II. Xuất Báo cáo tổng hợp (Mẫu 04/BC-TH)")

    all_for_bc: list[dict] = []
    all_for_bc = doc_bien_ban_theo_nam(nam=nam_td, pgd_user=pgd_user)

    if not all_for_bc:
        st.info("Không có biên bản nào để lập báo cáo tổng hợp.")
        return

    opt_bc = {
        f"[{'02/BB-CT' if r.get('loai')=='CT' else '03/BB-CX'}] "
        f"{fmt_ngay(r.get('ngay_kt',''))} — {r.get('ten_don_vi','')}": r
        for r in all_for_bc
    }
    chon_bc = st.multiselect(
        "Chọn biên bản đưa vào báo cáo tổng hợp",
        options=list(opt_bc.keys()), key=f"{key_prefix}bcth_chon",
    )
    if not chon_bc:
        st.info("Chọn ít nhất 1 biên bản để tạo báo cáo.")
        return

    ds_chon = [opt_bc[k] for k in chon_bc]

    with st.form(f"{key_prefix}form_bc_th"):
        st.markdown("**Thông tin báo cáo:**")
        bc1, bc2 = st.columns(2)
        don_vi_kt_bc  = bc1.text_input("Đơn vị kiểm tra", key=f"{key_prefix}bcth_dvkt")
        truong_doan_bc = bc1.text_input("Trưởng đoàn kiểm tra", key=f"{key_prefix}bcth_td")
        cap_uy        = bc1.text_input("Cấp ủy, chính quyền tham dự (nếu có)", key=f"{key_prefix}bcth_capuy")
        dia_danh_bc   = bc2.text_input("Địa danh ký", placeholder="Biên Hòa", key=f"{key_prefix}bcth_dd")
        ngay_bc       = bc2.date_input("Ngày báo cáo", value=date.today(), key=f"{key_prefix}bcth_ngay")
        noi_dung_kt   = st.text_area(
            "III. Nội dung kiểm tra",
            value="Theo Phụ lục I văn bản số 727/HD-NHCS ngày 11/02/2026.",
            height=60, key=f"{key_prefix}bcth_ndkt",
        )
        st.markdown("**IV. Đánh giá & Kiến nghị:**")
        r1, r2 = st.columns(2)
        nx_ctxh    = r1.text_area("Nhận xét đối với CT-XH",       height=60, key=f"{key_prefix}bcth_nx_ctxh")
        nx_to      = r2.text_area("Nhận xét đối với Tổ TK&VV",    height=60, key=f"{key_prefix}bcth_nx_to")
        nx_to_vien = r1.text_area("Nhận xét đối với tổ viên",     height=60, key=f"{key_prefix}bcth_nx_tov")
        kn_ctxh    = r2.text_area("Kiến nghị với CT-XH",          height=60, key=f"{key_prefix}bcth_kn_ctxh")
        kn_nhcs    = r1.text_area("Kiến nghị với NHCSXH",         height=60, key=f"{key_prefix}bcth_kn_nhcs")
        kn_cap_tren = r2.text_area("Kiến nghị với CT-XH cấp trên", height=60, key=f"{key_prefix}bcth_kn_ct")
        submitted_bc = st.form_submit_button("📄 Tạo Báo cáo tổng hợp Word", type="primary")

    if submitted_bc:
        du_lieu_bc, ten_file = build_payload_bc_th(
            don_vi_kt=don_vi_kt_bc, truong_doan=truong_doan_bc,
            cap_uy=cap_uy, dia_danh=dia_danh_bc, ngay_bc=ngay_bc,
            noi_dung_kt=noi_dung_kt,
            nx_ctxh=nx_ctxh, nx_to=nx_to, nx_to_vien=nx_to_vien,
            kn_ctxh=kn_ctxh, kn_nhcs=kn_nhcs, kn_cap_tren=kn_cap_tren,
            nam_td=nam_td,
        )
        with st.spinner("Đang tạo file..."):
            docx_bytes = tao_word_uythac_bc_th(du_lieu_bc, ds_chon)
        _download_word_pdf_pair(docx_bytes, ten_file, f"{key_prefix}bcth_")
        db.ghi_audit(username, "xuat_bc_th",
                      f"Báo cáo tổng hợp năm {nam_td} — {len(ds_chon)} biên bản")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

from tabs.base_tab import TabContext


def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    """Entry point — dùng chung cho ws_operation và ws_management."""
    ctx = TabContext(tab, **kwargs)
    _df_full = kwargs.get("df_full")
    df_full = _df_full if isinstance(_df_full, pd.DataFrame) else None
    df = kwargs.get("df")
    if (df is None or getattr(df, "empty", True)) and df_full is not None and not df_full.empty:
        df = df_full
    if (df is None or getattr(df, "empty", True)) and os.path.exists(CACHE_HSTD):
        df_cache = _doc_hstd_cached(ts_file(CACHE_HSTD))
        df = df_cache
    pgd_user = ctx.pgd_user
    username = kwargs.get("username", "unknown")
    role     = normalize_role(str(kwargs.get("role", "user") or "user"))

    with ctx:
        st.subheader("🤝 Ủy thác — Hội đoàn thể")
        st.caption(
            "Theo dõi hoạt động ủy thác và các mẫu biểu kiểm tra "
            "theo văn bản 727/HD-NHCS."
        )
        if df is None or df.empty:
            if os.path.exists(CACHE_HSTD):
                df_cache2 = _doc_hstd_cached(ts_file(CACHE_HSTD))
                if df_cache2 is not None and not df_cache2.empty and len(df_cache2.columns) < 15:
                    st.error(
                        f"⚠️ Dữ liệu HSTD cache chưa đầy đủ (chỉ {len(df_cache2.columns)} cột) — "
                        "cần upload/merge HSTD lại để dùng các chức năng Ủy thác."
                    )
        sub1, sub2, sub3, sub4, sub5, sub6, sub7 = st.tabs([
            "📊 Theo Hội đoàn thể",
            "📋 Kế hoạch (01/KH)",
            "📝 Biên bản CT-XH",
            "📋 Mẫu 06/TD & 06A/TD",
            "📋 Mẫu 15/TD",
            "📋 Biên bản & Báo cáo",
            "📊 Theo dõi & BC-TH",
        ])
        with sub1: _render_theo_dvut(df)
        with sub2: _render_ke_hoach(df, pgd_user, role)
        with sub3: _render_bb_ct_cx(df, pgd_user, username, role)
        with sub4: _render_mau06(df, pgd_user)
        with sub5: _render_mau15(df, pgd_user)
        with sub6: _render_bien_ban(df, pgd_user)
        with sub7: _render_theo_doi_bc_th(pgd_user, username, role)
