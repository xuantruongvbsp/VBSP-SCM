"""
Tab Cảnh báo Khoản vay Đến hạn.
Phân tích dư nợ đến hạn trong N tháng tới dựa trên HSTD hiện tại.
"""
from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

from auth import la_phan_he_pgd
from config import (
    CACHE_HSTD, COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT,
    COT_TONG_DU_NO, COT_NGAY_DEN_HAN, COT_MA_KH, COT_TEN_XA,
    COT_SO_KU, COT_DVUT,
)
from data.den_han import tinh_den_han_df
from pdf_service import xuat_pdf_group_header, nut_xuat_pdf
from utils import fmt_ty, fmt_so, xuat_excel, ten_file_xuat


@st.cache_data(show_spinner=False)
def _doc_va_tinh_den_han(pgd_user: str | None, mtime: float) -> pd.DataFrame:
    """Đọc parquet + tính toán den_han; cache theo (pgd_user, mtime file)."""
    try:
        df = pd.read_parquet(CACHE_HSTD)
    except Exception:
        return pd.DataFrame()
    if pgd_user and COT_TEN_PGD in df.columns:
        df = df[df[COT_TEN_PGD] == pgd_user]
    return tinh_den_han_df(df)


def _loc_thang(df_tinh: pd.DataFrame, tu_thang: int, den_thang: int) -> pd.DataFrame:
    col = "Tháng đến hạn còn lại"
    mask = (
        df_tinh[col].notna()
        & (df_tinh[col] >= tu_thang)
        & (df_tinh[col] <= den_thang)
    )
    return df_tinh[mask].copy()


def render(role: str = None, **kwargs) -> None:
    st.subheader("⏰ Cảnh báo Khoản vay Đến hạn")
    st.caption("Phân tích dư nợ đến hạn trong N tháng tới dựa trên HSTD hiện tại.")

    pgd_user = kwargs.get("pgd_user")
    _pgd_filter = pgd_user if la_phan_he_pgd(role) else None

    try:
        _mtime = os.path.getmtime(CACHE_HSTD)
    except FileNotFoundError:
        st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload file trước.")
        return

    df_tinh = _doc_va_tinh_den_han(_pgd_filter, _mtime)
    if df_tinh.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD.")
        return
    if COT_NGAY_DEN_HAN not in df_tinh.columns:
        st.error(f"❌ File HSTD thiếu cột '{COT_NGAY_DEN_HAN}'. Kiểm tra lại file upload.")
        return

    col1, col2 = st.columns(2)
    with col1:
        den_thang = st.slider(
            "Xem trước (tháng)", min_value=1, max_value=12,
            value=6, key="den_han_slider")
    with col2:
        nhom_theo = st.radio(
            "Nhóm theo", ["PGD", "Xã", "Hội đoàn thể"],
            horizontal=True, key="den_han_nhom")

    df_loc = _loc_thang(df_tinh, 0, den_thang)
    df_loc = df_loc[pd.to_numeric(df_loc[COT_TONG_DU_NO], errors="coerce").fillna(0) > 0]
    nhom_key = "pgd" if nhom_theo == "PGD" else ("dvut" if nhom_theo == "Hội đoàn thể" else "xa")

    tong_khoan = len(df_loc)
    tong_tien = df_loc[COT_TONG_DU_NO].sum() if tong_khoan > 0 else 0
    so_pgd = df_loc[COT_TEN_PGD].nunique() if tong_khoan > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Số khoản đến hạn", fmt_so(tong_khoan))
    c2.metric("Tổng dư nợ đến hạn", fmt_ty(tong_tien))
    c3.metric("Số PGD liên quan", so_pgd)

    # ── Bảng thống kê + đồ thị theo tháng (toàn năm) ────────────────────────
    st.divider()
    st.markdown("#### 📊 Thống kê theo tháng — Dư nợ đến hạn trong năm")

    df_nam = _loc_thang(df_tinh, 0, 12)

    if df_nam.empty:
        st.info("Không có khoản vay đến hạn trong 12 tháng tới.")
    else:
        df_nam = df_nam.copy()
        # Dùng "Ngày đến hạn" (đã parse đúng dayfirst=True) thay vì re-parse cột gốc
        df_nam["_ngay_dh"] = pd.to_datetime(df_nam["Ngày đến hạn"], errors="coerce")
        df_nam["_thang_label"] = df_nam["_ngay_dh"].dt.strftime("%m/%Y")
        df_nam["_sort_key"] = df_nam["_ngay_dh"].dt.to_period("M")

        df_th_stats = (
            df_nam.dropna(subset=["_thang_label"])
            .groupby(["_sort_key", "_thang_label"], sort=True)
            .agg(
                so_khoan=(COT_TONG_DU_NO, "count"),
                du_no=(COT_TONG_DU_NO, "sum"),
            )
            .reset_index()
            .sort_values("_sort_key")
        )

        if not df_th_stats.empty:
            tong_du_no_nam = df_th_stats["du_no"].sum()
            df_th_stats["pct"] = (
                df_th_stats["du_no"] / tong_du_no_nam * 100
                if tong_du_no_nam > 0 else 0
            ).round(1)

            # Bảng thống kê
            df_bang = df_th_stats[["_thang_label", "so_khoan", "du_no", "pct"]].copy()
            df_bang.columns = ["Tháng", "Số khoản", "Dư nợ (triệu đồng)", "Tỷ trọng %"]
            df_bang["Số khoản"] = df_bang["Số khoản"].apply(fmt_so)
            df_bang["Dư nợ (triệu đồng)"] = (
                df_th_stats["du_no"] / 1e6
            ).round(0).apply(lambda x: f"{x:,.0f}".replace(",", "."))
            df_bang["Tỷ trọng %"] = df_th_stats["pct"].apply(
                lambda x: f"{x:.1f}".replace(".", ",") + "%"
            )
            st.dataframe(df_bang, use_container_width=True, hide_index=True)

            # Đồ thị cột
            try:
                import plotly.graph_objects as go
                du_no_trieu = (df_th_stats["du_no"] / 1e6).round(0)
                fig = go.Figure(go.Bar(
                    x=df_th_stats["_thang_label"],
                    y=du_no_trieu,
                    text=du_no_trieu.apply(
                        lambda x: f"{x:,.0f}".replace(",", ".")
                    ),
                    textposition="outside",
                    marker_color="#3B82F6",
                    hovertemplate="<b>%{x}</b><br>Dư nợ: %{y:,.0f} triệu<extra></extra>",
                ))
                fig.update_layout(
                    xaxis_title="Tháng đến hạn",
                    yaxis_title="Dư nợ (triệu đồng)",
                    height=350,
                    margin=dict(t=20, b=40),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as _e:
                st.warning(f"Không thể vẽ đồ thị: {_e}")

    # ── Tổng hợp đến hạn theo PGD/Xã/Hội đoàn thể ───────────────────────────
    st.divider()
    NHOM_COT_MAP = {"PGD": COT_TEN_PGD, "Xã": COT_TEN_XA, "Hội đoàn thể": COT_DVUT}
    tieu_de_nhom = nhom_theo
    cot_nhom_th  = NHOM_COT_MAP[nhom_theo]
    st.markdown(f"#### 📋 Tổng hợp theo {tieu_de_nhom} — {den_thang} tháng tới")

    if df_loc.empty or cot_nhom_th not in df_loc.columns:
        st.info("Không có dữ liệu trong khoảng thời gian đã chọn.")
    else:
        _th_agg = (
            df_loc.groupby(cot_nhom_th, sort=False)
            .agg(
                **{
                    "Số khoản": (COT_MA_KH if COT_MA_KH in df_loc.columns else cot_nhom_th, "count"),
                    "_du_no": (COT_TONG_DU_NO, "sum"),
                }
            )
            .reset_index()
            .sort_values("_du_no", ascending=False)
            .rename(columns={cot_nhom_th: tieu_de_nhom})
        )
        _th_agg["Số khoản"] = _th_agg["Số khoản"].apply(fmt_so)
        _th_agg["Dư nợ (triệu đồng)"] = (
            _th_agg["_du_no"] / 1e6
        ).round(0).apply(lambda x: f"{x:,.0f}".replace(",", "."))

        st.dataframe(
            _th_agg[[tieu_de_nhom, "Số khoản", "Dư nợ (triệu đồng)"]],
            use_container_width=True, hide_index=True,
        )

        # Biểu đồ bar ngang có màu gradient
        try:
            import plotly.express as _px
            _top = _th_agg.nlargest(min(20, len(_th_agg)), "_du_no").sort_values("_du_no")
            _fig = _px.bar(
                _top,
                x="_du_no",
                y=tieu_de_nhom,
                orientation="h",
                color="_du_no",
                color_continuous_scale=[[0.0, "#C8E6C9"], [0.5, "#43A047"], [1.0, "#1B5E20"]],
                text="Dư nợ (triệu đồng)",
                labels={"_du_no": "Dư nợ", tieu_de_nhom: tieu_de_nhom},
                height=max(300, len(_top) * 36),
            )
            _fig.update_traces(textposition="outside",
                               hovertemplate="<b>%{y}</b><br>Dư nợ: %{text}<extra></extra>")
            _fig.update_layout(
                coloraxis_showscale=False,
                xaxis=dict(showticklabels=False, title=""),
                yaxis_title="",
                margin=dict(l=10, r=130, t=20, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(_fig, use_container_width=True, key=f"bar_nhom_{nhom_key}")
        except Exception as _e:
            st.caption(f"Không thể vẽ biểu đồ: {_e}")

    cols_hien_thi = [
        COT_TEN_PGD, COT_TEN_KH,
        COT_TEN_CT, COT_TONG_DU_NO,
        "Ngày đến hạn", "Số tháng có thể gia hạn",
    ]
    cols_hien_thi = [c for c in cols_hien_thi if c in df_loc.columns]

    with st.expander(f"📋 Danh sách {fmt_so(tong_khoan)} khoản vay đến hạn", expanded=False):
        if df_loc.empty:
            st.info("Không có dữ liệu.")
        else:
            # Convert ngày sang dd/mm/yyyy để hiển thị
            df_hien = df_loc[cols_hien_thi].sort_values("Ngày đến hạn").copy()
            if "Ngày đến hạn" in df_hien.columns:
                df_hien["Ngày đến hạn"] = pd.to_datetime(
                    df_hien["Ngày đến hạn"], errors="coerce"
                ).dt.strftime("%d/%m/%Y").fillna("")
            st.dataframe(df_hien, use_container_width=True, hide_index=True)

            COLS_CHI_TIET = [
                COT_TEN_PGD, COT_TEN_KH, COT_TEN_CT,
                COT_TONG_DU_NO, "Ngày đến hạn", "Số tháng có thể gia hạn",
            ]
            cols_ok = [c for c in COLS_CHI_TIET if c in df_loc.columns]
            df_chi_tiet = df_loc[cols_ok].sort_values("Ngày đến hạn").reset_index(drop=True)
            # Convert ngày trong file xuất
            if "Ngày đến hạn" in df_chi_tiet.columns:
                df_chi_tiet["Ngày đến hạn"] = pd.to_datetime(
                    df_chi_tiet["Ngày đến hạn"], errors="coerce"
                ).dt.strftime("%d/%m/%Y").fillna("")

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
    if "Ngày đến hạn" in df_pdf.columns:
        df_pdf["Ngày đến hạn"] = pd.to_datetime(
            df_pdf["Ngày đến hạn"], errors="coerce"
        ).dt.strftime("%d/%m/%Y").fillna("")
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
        "Ngày đến hạn", "Số tháng có thể gia hạn",
        COT_TONG_DU_NO,
    ]
    _detail_pdf_cols = [c for c in _detail_pdf_cols if c in df_pdf.columns]
    if nhom_col_pdf not in _detail_pdf_cols:
        _detail_pdf_cols = [nhom_col_pdf] + _detail_pdf_cols
    else:
        _detail_pdf_cols = [nhom_col_pdf] + [c for c in _detail_pdf_cols if c != nhom_col_pdf]

    if st.button("📄 Xuất PDF Group Header", key="btn_pdf_den_han_group", type="primary"):
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
                            [nhom_col_pdf, "Ngày đến hạn"]
                            if "Ngày đến hạn" in df_pdf.columns
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
                st.session_state["_pdf_bytes_den_han_group"] = pdf_bytes
            except Exception as _e:
                st.session_state["_pdf_bytes_den_han_group"] = None
                st.error(f"❌ Lỗi tạo PDF: {_e}")

    if st.session_state.get("_pdf_bytes_den_han_group"):
        st.download_button(
            label="⬇ Tải file PDF",
            data=st.session_state["_pdf_bytes_den_han_group"],
            file_name=f"DenHan_{den_thang}thang_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
            mime="application/pdf",
            key="btn_pdf_den_han_group_dl",
        )
