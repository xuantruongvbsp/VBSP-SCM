"""
Tab Cảnh báo Khoản vay Đến hạn.
Phân tích dư nợ đến hạn trong N tháng tới dựa trên HSTD hiện tại.
"""
from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

from auth import la_phan_he_pgd
from config import CACHE_HSTD, COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT, COT_TONG_DU_NO, COT_NGAY_DEN_HAN
from data.den_han import (
    tinh_den_han_df,
    loc_den_han_trong,
    tong_hop_den_han,
    canh_bao_tap_trung,
)
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
            buf = BytesIO()
            df_loc[cols_hien_thi].to_excel(buf, index=False)
            st.download_button(
                "📥 Xuất Excel",
                data=buf.getvalue(),
                file_name=f"den_han_{den_thang}thang.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_xuat_den_han",
            )
