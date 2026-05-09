"""
Tab Cảnh báo Khoản vay Đến hạn.
Phân tích dư nợ đến hạn trong N tháng tới dựa trên HSTD hiện tại.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

from auth import la_phan_he_pgd
from config import (
    CACHE_HSTD, COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT,
    COT_TONG_DU_NO, COT_NGAY_DEN_HAN, COT_MA_KH, COT_TEN_XA,
    COT_SO_KU,
)
from data.den_han import (
    tinh_den_han_df,
    loc_den_han_trong,
    tong_hop_den_han,
    canh_bao_tap_trung,
)
from pdf_service import xuat_pdf_group_header
from utils import fmt_ty, fmt_so


def render(role: str = None, **kwargs) -> None:
    st.subheader("⏰ Cảnh báo Khoản vay Đến hạn")
    st.caption("Phân tích dư nợ đến hạn trong N tháng tới dựa trên HSTD hiện tại.")

    try:
        df = pd.read_parquet(CACHE_HSTD)
    except FileNotFoundError:
        st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload file trước.")
        return

    pgd_user = kwargs.get("pgd_user")
    if la_phan_he_pgd(role) and pgd_user and COT_TEN_PGD in df.columns:
        df = df[df[COT_TEN_PGD] == pgd_user]

    if COT_NGAY_DEN_HAN not in df.columns:
        st.error(
            f"❌ File HSTD thiếu cột '{COT_NGAY_DEN_HAN}'. "
            f"Kiểm tra lại file upload."
        )
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        den_thang = st.slider(
            "Xem trước (tháng)", min_value=1, max_value=12,
            value=6, key="den_han_slider")
    with col2:
        nhom_theo = st.radio(
            "Nhóm theo", ["PGD", "Xã"],
            horizontal=True, key="den_han_nhom")
    with col3:
        nguong = st.number_input(
            "Ngưỡng tập trung (%)", min_value=10, max_value=80,
            value=30, step=5, key="den_han_nguong") / 100

    df_loc = loc_den_han_trong(df, tu_thang=0, den_thang=den_thang)
    nhom_key = "pgd" if nhom_theo == "PGD" else "xa"

    tong_khoan = len(df_loc)
    tong_tien = df_loc[COT_TONG_DU_NO].sum() if tong_khoan > 0 else 0
    so_pgd = df_loc[COT_TEN_PGD].nunique() if tong_khoan > 0 else 0
    ds_cb = canh_bao_tap_trung(df, nguong_ty_le=nguong)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Số khoản đến hạn", fmt_so(tong_khoan))
    c2.metric("Tổng dư nợ đến hạn", fmt_ty(tong_tien))
    c3.metric("Số PGD liên quan", so_pgd)
    c4.metric("⚠️ Điểm tập trung", len(ds_cb),
              delta_color="inverse" if ds_cb else "off")

    if ds_cb:
        st.divider()
        st.markdown("#### ⚠️ Điểm tập trung rủi ro đến hạn")
        for item in ds_cb:
            icon = "🔴" if item["muc_do"] == "high" else "🟡"
            with st.container(border=True):
                pc1, pc2, pc3, pc4 = st.columns([3, 2, 2, 2])
                pc1.markdown(
                    f"{icon} **{item['pgd']}**  \n"
                    f"Tháng: `{item['thang']}`"
                )
                pc2.metric("Đến hạn", fmt_ty(item["tong_den_han"]))
                pc3.metric("Tổng PGD", fmt_ty(item["tong_pgd"]))
                pc4.metric("Tỷ lệ", f"{item['ty_le']*100:.1f}%")

    st.divider()
    st.markdown("#### 📅 Chi tiết theo tháng")
    df_th = tong_hop_den_han(df, nhom_theo=nhom_key)

    if df_th.empty:
        st.info("Không có khoản vay đến hạn trong khoảng thời gian đã chọn.")
    else:
        try:
            df_pivot = df_th.pivot_table(
                index=df_th.columns[0],
                columns="Tháng",
                values="tong_du_no",
                aggfunc="sum",
                fill_value=0,
            )
            df_display = df_pivot.map(lambda x: fmt_ty(x) if x > 0 else "—")
            st.dataframe(df_display, use_container_width=True)
        except Exception:
            st.dataframe(df_th, use_container_width=True, hide_index=True)

    cols_hien_thi = [
        COT_TEN_PGD, COT_TEN_KH,
        COT_TEN_CT, COT_TONG_DU_NO,
        "Ngày đến hạn", "Tháng đến hạn còn lại",
    ]
    cols_hien_thi = [c for c in cols_hien_thi if c in df_loc.columns]

    with st.expander(f"📋 Danh sách {fmt_so(tong_khoan)} khoản vay đến hạn", expanded=False):
        if df_loc.empty:
            st.info("Không có dữ liệu.")
        else:
            st.dataframe(
                df_loc[cols_hien_thi].sort_values("Tháng đến hạn còn lại"),
                use_container_width=True, hide_index=True,
            )

            # Xác định chế độ xuất: tab này không có bộ lọc PGD/CT/Xã tường minh
            # → luôn xuất chi tiết, nhưng thêm sheet tổng hợp theo nhom_theo
            COLS_CHI_TIET = [
                COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT,
                COT_TONG_DU_NO, "Ngày đến hạn", "Tháng đến hạn còn lại",
            ]
            cols_ok = [c for c in COLS_CHI_TIET if c in df_loc.columns]
            df_chi_tiet = df_loc[cols_ok].sort_values("Tháng đến hạn còn lại").reset_index(drop=True)

            # Sheet tổng hợp theo nhom_theo (pgd hoặc xa)
            nhom_col_dt = COT_TEN_PGD if nhom_theo == "PGD" else "Tên xã"
            if nhom_col_dt in df_loc.columns:
                df_tong_hop = df_loc.groupby(nhom_col_dt).agg(
                    **{"Số khoản": (COT_TONG_DU_NO, "count"),
                       "Dư nợ (VND)": (COT_TONG_DU_NO, "sum")}
                ).reset_index().sort_values("Dư nợ (VND)", ascending=False)
                df_tong_hop["Dư nợ (VND)"] = df_tong_hop["Dư nợ (VND)"].apply(fmt_so)
                sheets_xuat = {
                    f"TH_{nhom_theo}": df_tong_hop,
                    "Chi tiết": df_chi_tiet,
                }
            else:
                sheets_xuat = {"Chi tiết": df_chi_tiet}

            col_ex2, col_pdf2 = st.columns(2)
            with col_ex2:
                excel_bytes = xuat_excel(sheets_xuat)
                st.download_button(
                    "📥 Xuất Excel",
                    data=excel_bytes,
                    file_name=ten_file_xuat(f"DenHan_{den_thang}thang"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="btn_xuat_den_han_excel",
                    use_container_width=True,
                )

            with col_pdf2:
                nut_xuat_pdf(
                    df=df_chi_tiet,
                    tieu_de=f"Hồ sơ đến hạn trong {den_thang} tháng — Chi tiết",
                    username=kwargs.get("username", ""),
                    cols_tien=[COT_TONG_DU_NO],
                    prefix_file=f"DenHan_{den_thang}thang",
                    key="btn_pdf_den_han",
                )

    # ── Xuất PDF Group Header/Footer ─────────────────────────────────────────
    st.divider()
    st.markdown("#### 📄 Xuất PDF Báo cáo Đến hạn")

    col_pdf1, col_pdf2 = st.columns([2, 2])
    with col_pdf1:
        nhom_pdf = st.radio(
            "Nhóm theo (PDF)",
            options=["Chương trình", "PGD", "Xã"],
            horizontal=True,
            key="den_han_nhom_pdf",
        )
    with col_pdf2:
        loc_pgd_pdf = ""
        loc_ct_pdf  = ""
        loc_xa_pdf  = ""
        if not la_phan_he_pgd(role) and COT_TEN_PGD in df_loc.columns:
            ds_pgd = sorted(df_loc[COT_TEN_PGD].dropna().unique().tolist())
            loc_pgd_pdf = st.selectbox(
                "Lọc PGD", [""] + ds_pgd,
                format_func=lambda x: "(Tất cả)" if x == "" else x,
                key="den_han_loc_pgd_pdf",
            )
        if COT_TEN_CT in df_loc.columns:
            ds_ct = sorted(df_loc[COT_TEN_CT].dropna().unique().tolist())
            loc_ct_pdf = st.selectbox(
                "Lọc Chương trình", [""] + ds_ct,
                format_func=lambda x: "(Tất cả)" if x == "" else x,
                key="den_han_loc_ct_pdf",
            )

    # Áp dụng bộ lọc PDF
    df_pdf = df_loc.copy()
    if loc_pgd_pdf and COT_TEN_PGD in df_pdf.columns:
        df_pdf = df_pdf[df_pdf[COT_TEN_PGD] == loc_pgd_pdf]
    if loc_ct_pdf and COT_TEN_CT in df_pdf.columns:
        df_pdf = df_pdf[df_pdf[COT_TEN_CT] == loc_ct_pdf]
    if loc_xa_pdf and COT_TEN_XA in df_pdf.columns:
        df_pdf = df_pdf[df_pdf[COT_TEN_XA] == loc_xa_pdf]

    # Xác định cột nhóm và cột detail cho PDF
    _nhom_col_map = {
        "Chương trình": COT_TEN_CT,
        "PGD":          COT_TEN_PGD,
        "Xã":           COT_TEN_XA,
    }
    nhom_col_pdf = _nhom_col_map[nhom_pdf]

    _detail_pdf_cols = [
        COT_MA_KH, COT_TEN_KH, COT_SO_KU,
        "Ngày đến hạn", "Tháng đến hạn còn lại",
        COT_TONG_DU_NO,
    ]
    _detail_pdf_cols = [c for c in _detail_pdf_cols if c in df_pdf.columns]
    if nhom_col_pdf not in _detail_pdf_cols:
        _detail_pdf_cols = [nhom_col_pdf] + _detail_pdf_cols
    else:
        _detail_pdf_cols = [nhom_col_pdf] + [c for c in _detail_pdf_cols if c != nhom_col_pdf]

    if st.button("📄 Xuất PDF Group Header", key="btn_pdf_den_han_group", type="secondary"):
        if df_pdf.empty:
            st.warning("⚠️ Không có dữ liệu sau khi lọc để xuất PDF.")
        else:
            username = st.session_state.get("username", "VBSP-SCM")
            _tieu_de_phu_parts = []
            if loc_pgd_pdf:
                _tieu_de_phu_parts.append(f"PGD: {loc_pgd_pdf}")
            if loc_ct_pdf:
                _tieu_de_phu_parts.append(f"CT: {loc_ct_pdf}")
            _tieu_de_phu = "  |  ".join(_tieu_de_phu_parts) if _tieu_de_phu_parts else ""
            try:
                with st.spinner("⏳ Đang tạo PDF, vui lòng chờ..."):
                    pdf_bytes = xuat_pdf_group_header(
                        df=df_pdf[_detail_pdf_cols].sort_values(
                            [nhom_col_pdf, "Tháng đến hạn còn lại"]
                            if "Tháng đến hạn còn lại" in df_pdf.columns
                            else [nhom_col_pdf]
                        ),
                        tieu_de=f"Báo cáo Khoản vay Đến hạn trong {den_thang} tháng",
                        nhom_theo=nhom_col_pdf,
                        nguoi_xuat=username,
                        cols_tien=[COT_TONG_DU_NO],
                        tieu_de_phu=_tieu_de_phu,
                        loc_pgd=loc_pgd_pdf,
                        loc_ct=loc_ct_pdf,
                        loc_xa=loc_xa_pdf,
                    )
                st.success("✅ Xuất PDF thành công! Nhấn nút bên dưới để tải.")
                st.download_button(
                    label="⬇ Tải file PDF",
                    data=pdf_bytes,
                    file_name=f"DenHan_{den_thang}thang_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
                    mime="application/pdf",
                    key="btn_pdf_den_han_group_dl",
                )
            except Exception as _e:
                st.error(f"❌ Lỗi tạo PDF: {_e}")
