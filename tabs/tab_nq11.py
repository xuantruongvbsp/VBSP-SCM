"""Tab NQ11."""
from __future__ import annotations

from io import BytesIO
from datetime import datetime, date
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import *
from utils import fmt_ty, xuat_excel, ten_file_xuat, hien_thi_dataframe_phan_trang
from data import ts_file

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _tao_column_config_nq11() -> dict[str, st.column_config.Column]:
    """
    Tạo column_config cho bảng NQ11.
    
    Returns:
        Dict cấu hình column cho st.dataframe
    """
    return {
        "Dư_nợ_NQ11": st.column_config.NumberColumn(
            "Dư nợ NQ11\n(triệu đồng)",
            format="%.0f",
            help="Dư nợ Nghị Quyết 11"
        ),
        "Nợ_trong_hạn": st.column_config.NumberColumn(
            "Nợ trong hạn\n(triệu đồng)",
            format="%.0f",
            help="Nợ trong hạn"
        ),
        "Nợ_quá_hạn": st.column_config.NumberColumn(
            "Nợ quá hạn\n(triệu đồng)",
            format="%.0f",
            help="Nợ quá hạn"
        ),
        "Số_món": st.column_config.NumberColumn(
            "Số món",
            format="%d",
            help="Số món vay"
        ),
        "Số tiền giải ngân": st.column_config.NumberColumn(
            "Số tiền giải ngân\n(triệu đồng)",
            format="%.0f",
            help="Số tiền giải ngân"
        ),
        "DNO NQ11": st.column_config.NumberColumn(
            "DNO NQ11\n(triệu đồng)",
            format="%.0f",
            help="Dư nợ NQ11"
        ),
        "Nợ trong hạn": st.column_config.NumberColumn(
            "Nợ trong hạn\n(triệu đồng)",
            format="%.0f",
            help="Nợ trong hạn"
        ),
        "Nợ quá hạn": st.column_config.NumberColumn(
            "Nợ quá hạn\n(triệu đồng)",
            format="%.0f",
            help="Nợ quá hạn"
        ),
    }


def render(tab: DeltaGenerator, **kwargs: dict) -> None:
    """
    Render tab NQ11.
    
    Args:
        tab: Streamlit DeltaGenerator cho tab này
        **kwargs: Chứa df, df_full, role, pgd_user, username, df_nq11
    """
    df = kwargs.get("df")
    df_full = kwargs.get("df_full", df)
    role = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username")
    df_nq11 = kwargs.get("df_nq11")

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
            st.subheader("📑 Dữ liệu Nghị Quyết 11 (NQ11)")

            def fmt_vn_tien(x: float) -> str:
                """Format số tiền cho metric display (triệu đồng, 0 dp)."""
                try:
                    x = float(x)
                    if abs(x) > 0:
                        trieu = x / 1_000_000
                        return f"{trieu:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    return "—"
                except Exception:
                    return "—"

            if df_nq11 is None:
                st.warning("⚠️ Chưa có file dữ liệu NQ11.")
                st.info(f"Vui lòng đặt file vào: {FILE_PATH_NQ11} rồi bấm Làm mới dữ liệu.")
            else:
                # ── Chỉ số tổng quan ──
                tong_mon     = len(df_nq11)
                co_nq11      = df_nq11[df_nq11["DNO NQ11"] > 0]
                khong_nq11   = df_nq11[df_nq11["DNO NQ11"] == 0]
                tong_dno_nq11= co_nq11["DNO NQ11"].sum()
                tong_no_th   = df_nq11["Nợ trong hạn"].sum()  if "Nợ trong hạn"  in df_nq11.columns else 0
                tong_no_qh   = df_nq11["Nợ quá hạn"].sum()   if "Nợ quá hạn"    in df_nq11.columns else 0

                c1,c2,c3,c4,c5 = st.columns(5)
                c1.metric("Tổng số món",       f"{tong_mon:,}".replace(",","."))
                c2.metric("Món có NQ11",        f"{len(co_nq11):,}".replace(",","."))
                c3.metric("Dư nợ NQ11",         fmt_vn_tien(tong_dno_nq11))
                c4.metric("Tổng nợ trong hạn",  fmt_vn_tien(tong_no_th))
                c5.metric("Tổng nợ quá hạn",    fmt_vn_tien(tong_no_qh))

                st.divider()

                # ── Bộ lọc ──
                with st.expander("🔧 Bộ lọc", expanded=True):
                    lf1, lf2, lf3 = st.columns(3)
                    with lf1:
                        loai_loc = st.selectbox("Lọc theo NQ11",
                            ["Tất cả", "Chỉ món có NQ11", "Chỉ món không có NQ11"], key="nq11_loai")
                    with lf2:
                        if "Tên chương trình" in df_nq11.columns:
                            ds_ct_nq = ["Tất cả"] + sorted(df_nq11["Tên chương trình"].dropna().unique().tolist())
                            loc_ct   = st.selectbox("Chương trình", ds_ct_nq, key="nq11_ct")
                        else: loc_ct = "Tất cả"
                    with lf3:
                        if "Tên xã" in df_nq11.columns:
                            ds_xa = ["Tất cả"] + sorted(df_nq11["Tên xã"].dropna().unique().tolist())
                            loc_xa = st.selectbox("Xã", ds_xa, key="nq11_xa")
                        else: loc_xa = "Tất cả"

                # Áp dụng lọc
                df_loc_nq = df_nq11.copy()
                if loai_loc == "Chỉ món có NQ11":      df_loc_nq = df_loc_nq[df_loc_nq["DNO NQ11"] > 0]
                elif loai_loc == "Chỉ món không có NQ11": df_loc_nq = df_loc_nq[df_loc_nq["DNO NQ11"] == 0]
                if loc_ct != "Tất cả" and "Tên chương trình" in df_loc_nq.columns:
                    df_loc_nq = df_loc_nq[df_loc_nq["Tên chương trình"] == loc_ct]
                if loc_xa != "Tất cả" and "Tên xã" in df_loc_nq.columns:
                    df_loc_nq = df_loc_nq[df_loc_nq["Tên xã"] == loc_xa]

                # Tóm tắt sau lọc
                m1,m2,m3 = st.columns(3)
                m1.metric("Số món hiển thị",  f"{len(df_loc_nq):,}".replace(",","."))
                m2.metric("Dư nợ NQ11",       fmt_vn_tien(df_loc_nq["DNO NQ11"].sum()))
                m3.metric("Nợ trong hạn",     fmt_vn_tien(df_loc_nq["Nợ trong hạn"].sum() if "Nợ trong hạn" in df_loc_nq.columns else 0))

                # ── Bảng tổng hợp theo chương trình ──
                st.divider()
                st.markdown("**📊 Tổng hợp theo chương trình**")
                if "Tên chương trình" in df_loc_nq.columns:
                    th_ct = df_loc_nq.groupby("Tên chương trình").agg(
                        Số_món        = ("Mã khách hàng", "count"),
                        Dư_nợ_NQ11    = ("DNO NQ11",      "sum"),
                        Nợ_trong_hạn  = ("Nợ trong hạn",  "sum"),
                        Nợ_quá_hạn    = ("Nợ quá hạn",    "sum"),
                    ).sort_values("Dư_nợ_NQ11", ascending=False).reset_index()
                    # Dùng column_config thay vì apply format
                    hien_thi_dataframe_phan_trang(
                        th_ct,
                        key="nq11_th_ct",
                        column_config=_tao_column_config_nq11(),
                    )

                # ── Danh sách chi tiết ──
                st.divider()
                st.markdown("**📋 Danh sách chi tiết**")
                cot_hien_nq = [c for c in [
                    "Tên xã","Tên thôn","Mã khách hàng","Tên khách hàng",
                    "Số điện thoại","Số khế ước","Tên chương trình",
                    "Số tiền giải ngân","Nợ trong hạn","Nợ quá hạn","DNO NQ11",
                    "Đến hạn sau cùng","Ngày báo cáo"
                ] if c in df_loc_nq.columns]

                # Hiển thị với column_config thay vì apply format
                df_hien_nq = df_loc_nq[cot_hien_nq].copy()
                hien_thi_dataframe_phan_trang(
                    df_hien_nq.reset_index(drop=True),
                    key="nq11_ds_chi_tiet",
                    column_config=_tao_column_config_nq11(),
                    height=350,
                )

                # ── Xuất Excel ──
                st.divider()
                if st.button("📥 Xuất dữ liệu NQ11 ra Excel", type="primary", key="btn_nq11_xuat"):
                    buf = BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as w:
                        # Sheet 1: Tổng hợp chương trình (số gốc)
                        th_ct.to_excel(w, index=False, sheet_name="Tổng hợp CT")
                        # Sheet 2: Danh sách chi tiết (số gốc)
                        df_loc_nq[cot_hien_nq].to_excel(w, index=False, sheet_name="Chi tiết")
                        # Sheet 3: Chỉ món NQ11
                        if loai_loc != "Chỉ món không có NQ11":
                            df_loc_nq[df_loc_nq["DNO NQ11"]>0][cot_hien_nq].to_excel(
                                w, index=False, sheet_name="Chỉ món NQ11")
                    st.session_state["_bytes_nq11"] = buf.getvalue()
                    st.session_state["_file_nq11"] = f"NQ11_{datetime.today().strftime('%d%m%Y')}.xlsx"

                if st.session_state.get("_bytes_nq11"):
                    st.download_button(
                        "⬇ Tải file Excel",
                        data=st.session_state["_bytes_nq11"],
                        file_name=st.session_state["_file_nq11"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_nq11",
                    )

        # =============================================
        # TAB CÂN ĐỐI NGUỒN VỐN  (dữ liệu Điện báo — toàn chi nhánh)
        # =============================================
