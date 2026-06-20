"""Báo cáo Giao ban PGD — tổng hợp dư nợ, cho vay, thu nợ theo ĐVUT và Xã."""
from __future__ import annotations

import db
from datetime import datetime

import plotly.express as px
import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_MA_KH,
    COT_TONG_DU_NO, COT_DU_NO_QH,
)
from auth import is_pgd_role, is_cn_role
from data import danh_dau_khong_hd_cached
from utils import fmt_ty, fmt_so, hien_thi_dataframe_phan_trang
from services.excel_service import xuat_excel_chuyen_nghiep
from pdf_service import kiem_tra_pdf_dependency
from components.export_pdf import download_pdf_button, xuat_pdf_co_chart
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:

    """

    Render tab Báo cáo Giao ban - tạo báo cáo tổng hợp theo xã với bảng tóm tắt theo ĐVUT.

    """

    ctx = tab if tab is not None else st.container()

    with ctx:

        st.subheader("📝 Báo cáo Giao ban")

        st.caption("Tổng hợp tình hình dư nợ, cho vay, thu nợ theo ĐVUT và Xã")

        

        df = kwargs.get("df")

        pgd_user = kwargs.get("pgd_user")

        role = kwargs.get("role")

        

        if df is None or df.empty:

            st.warning("Chưa có dữ liệu HSTD.")

            return

        

        # ① Bộ lọc

        st.markdown("**① Bộ lọc dữ liệu**")

        

        # Lọc theo PGD

        df_filtered = df.copy()

        if is_pgd_role(role) and pgd_user:

            if COT_TEN_PGD in df.columns:

                df_filtered = df[df[COT_TEN_PGD] == pgd_user].copy()

            st.info(f"Dữ liệu đã lọc theo PGD: **{pgd_user}**")

        elif is_cn_role(role):

            if COT_TEN_PGD in df.columns:

                ds_pgd = sorted(df[COT_TEN_PGD].dropna().unique().tolist())

                if ds_pgd:

                    chon_pgd = st.selectbox("Chọn Phòng Giao dịch", ds_pgd, key="op_gb_pgd")

                    df_filtered = df[df[COT_TEN_PGD] == chon_pgd].copy()

        

        # Chọn Xã

        if COT_TEN_XA in df_filtered.columns:

            ds_xa = sorted(df_filtered[COT_TEN_XA].dropna().unique().tolist())

            if not ds_xa:

                st.warning("Không có dữ liệu xã nào trong PGD được chọn.")

                return

            chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="op_gb_xa")

            df_xa = df_filtered[df_filtered[COT_TEN_XA] == chon_xa].copy()

        else:

            st.warning("Không tìm thấy cột 'Tên xã' trong dữ liệu.")

            return

        

        if df_xa.empty:

            st.warning(f"Không có dữ liệu cho xã **{chon_xa}**")

            return



        # Chọn điểm giao dịch


        dgd_map = db.doc_dgd_map()

        

        # Lấy PGD hiện tại

        current_pgd = pgd_user if is_pgd_role(role) else (

            chon_pgd if 'chon_pgd' in locals() else pgd_user

        )

        

        ds_dgd = []

        chon_dgd = None

        ds_thon_dgd = None

        ten_dgd = None

        

        if current_pgd and current_pgd in dgd_map and chon_xa in dgd_map[current_pgd]:

            ds_dgd = list(dgd_map[current_pgd][chon_xa].keys())

        

        if not ds_dgd:

            st.info(

                "⚠️ Xã này chưa cấu hình điểm giao dịch. "

                "Vào tab **📍 Điểm GD của tôi** để thêm/cập nhật."

            )

            # Vẫn cho phép tiếp tục - lọc theo toàn xã

            chon_dgd = None

            ds_thon_dgd = None

            df_dgd = df_xa.copy()

            ten_dgd = chon_xa

        else:

            chon_dgd = st.selectbox("📍 Điểm giao dịch", ds_dgd, key="op_gb_dgd")

            ds_thon_dgd = dgd_map[current_pgd][chon_xa][chon_dgd]

            ten_dgd = chon_dgd

            st.caption(f"Quản lý: {', '.join(ds_thon_dgd)}")

            

            # Lọc df theo thôn/ấp của điểm giao dịch

            if "Tên thôn" in df_xa.columns:

                df_dgd = df_xa[df_xa["Tên thôn"].isin(ds_thon_dgd)].copy()

            else:

                df_dgd = df_xa.copy()

                st.warning("Không tìm thấy cột 'Tên thôn' để lọc theo điểm giao dịch.")

        

        if df_dgd.empty:

            st.warning(f"Không có dữ liệu cho điểm giao dịch **{chon_dgd or chon_xa}**")

            return

        

        st.divider()

        

        # ② Bảng tổng hợp theo ĐVUT

        st.markdown("**② Tổng hợp theo ĐVUT**")

        

        # Đánh dấu khách hàng 3 tháng không hoạt động

        df_dgd_marked = danh_dau_khong_hd_cached(df_dgd)

        

        # Groupby theo Tên ĐVUT

        if COT_DVUT not in df_dgd.columns:

            st.warning("Không tìm thấy cột 'Tên ĐVUT' trong dữ liệu.")

            return

        

        # Tính toán các cột

        agg_dict = {

            "Số Tổ": ("Tên tổ", lambda x: x.nunique() if "Tên tổ" in df_dgd.columns else 0),

            "Số KH": (COT_MA_KH, lambda x: x.nunique()),

            "Tổng dư nợ": (COT_TONG_DU_NO, lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),

            "Nợ quá hạn": (COT_DU_NO_QH, lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),

        }

        

        # Thêm các cột có điều kiện

        if "Giải ngân trong tháng" in df_dgd.columns:

            agg_dict["Doanh số cho vay tháng"] = ("Giải ngân trong tháng", 

                lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())

        

        # Tính doanh số thu nợ (cộng 3 cột nếu có)

        thu_no_cols = ["Thu nợ TH tháng", "Thu nợ QH tháng", "Thu nợ khoanh tháng"]

        existing_thu_no_cols = [col for col in thu_no_cols if col in df_dgd.columns]

        if existing_thu_no_cols:

            for col in existing_thu_no_cols:

                df_dgd[col] = pd.to_numeric(df_dgd[col], errors="coerce").fillna(0)

            df_dgd["Tổng thu nợ tháng"] = df_dgd[existing_thu_no_cols].sum(axis=1)

            agg_dict["Doanh số thu nợ tháng"] = ("Tổng thu nợ tháng", "sum")

        

        if "Dư nợ khoanh" in df_dgd.columns:

            agg_dict["Nợ khoanh"] = ("Dư nợ khoanh", 

                lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())

        

        # Số khoản 3m KHĐ

        if "is_3m_inactive" in df_dgd_marked.columns:

            df_dgd["is_3m_inactive"] = df_dgd_marked["is_3m_inactive"]

            agg_dict["Số khoản 3m KHĐ"] = ("is_3m_inactive", "sum")

        

        # Tạo bảng tổng hợp - chỉ sử dụng những cột thực sự tồn tại

        valid_agg_dict = {}

        for col_name, (data_col, agg_func) in agg_dict.items():

            if data_col in df_dgd.columns:

                valid_agg_dict[data_col] = agg_func

        

        if valid_agg_dict and COT_DVUT in df_dgd.columns:

            df_bang = df_dgd.groupby(COT_DVUT).agg(valid_agg_dict).reset_index()

            

            # Đổi tên cột về tên hiển thị

            rename_dict = {}

            for col_name, (data_col, agg_func) in agg_dict.items():

                if data_col in df_dgd.columns and data_col in df_bang.columns:

                    rename_dict[data_col] = col_name

            df_bang = df_bang.rename(columns=rename_dict)

        else:

            # Tạo DataFrame rỗng với cấu trúc cơ bản

            df_bang = pd.DataFrame({COT_DVUT: []})

        

        # Tính tỷ trọng %

        if "Tổng dư nợ" in df_bang.columns and df_bang["Tổng dư nợ"].sum() > 0:

            df_bang["Tỷ trọng %"] = (df_bang["Tổng dư nợ"] / df_bang["Tổng dư nợ"].sum() * 100).round(1)

        

        # Thêm dòng Cộng

        dong_cong = {COT_DVUT: "CỘNG"}

        for col in df_bang.columns:

            if col != COT_DVUT:

                if col == "Tỷ trọng %":

                    dong_cong[col] = 100.0

                else:

                    dong_cong[col] = df_bang[col].sum()

        

        df_bang = pd.concat([df_bang, pd.DataFrame([dong_cong])], ignore_index=True)

        

        # Định dạng hiển thị (chia triệu đồng cho các cột tiền)

        df_display = df_bang.copy()

        tien_cols = ["Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh", "Doanh số cho vay tháng", "Doanh số thu nợ tháng"]

        for col in tien_cols:

            if col in df_display.columns:

                df_display[col] = (df_display[col] / 1e6).round(1)

        

        hien_thi_dataframe_phan_trang(df_display, key="op_bao_cao_dvut_bang")

        

        # Ghi chú đơn vị

        st.caption("*Đơn vị tiền: triệu đồng*")

        

        st.divider()

        

        # ③ Đoạn tóm tắt văn bản

        st.markdown("**③ Tóm tắt báo cáo**")

        

        # Lấy các số liệu từ dòng Cộng

        dong_cong_data = df_bang[df_bang[COT_DVUT] == "CỘNG"].iloc[0]

        

        tong_dn = dong_cong_data.get("Tổng dư nợ", 0) / 1e6

        so_kh = int(dong_cong_data.get("Số KH", 0))

        so_to = int(dong_cong_data.get("Số Tổ", 0))

        nqh = dong_cong_data.get("Nợ quá hạn", 0) / 1e6

        nkh = dong_cong_data.get("Nợ khoanh", 0) / 1e6

        ds_cv = dong_cong_data.get("Doanh số cho vay tháng", 0) / 1e6

        ds_thu = dong_cong_data.get("Doanh số thu nợ tháng", 0) / 1e6

        

        tl_nqh = (nqh / tong_dn * 100) if tong_dn > 0 else 0

        

        # Thông tin khu vực

        khu_vuc_text = f"{ten_dgd}"

        if ds_thon_dgd:

            khu_vuc_text += f" (gồm: {', '.join(ds_thon_dgd)})"

        

        tom_tat = f"""Khu vực {khu_vuc_text}, xã {chon_xa}: Tổng dư nợ đạt {tong_dn:,.0f} triệu đồng, với {fmt_so(so_kh)} khách hàng còn dư nợ, thông qua {so_to} Tổ TK&VV. Trong đó, nợ quá hạn {nqh:,.0f} triệu đồng, tỷ lệ {tl_nqh:.2f}%; nợ khoanh {nkh:,.0f} triệu đồng.

Doanh số cho vay trong tháng: {ds_cv:,.0f} triệu đồng; doanh số thu nợ trong tháng: {ds_thu:,.0f} triệu đồng."""

        

        st.text_area("📋 Đoạn tóm tắt (copy vào báo cáo)",

                     value=tom_tat,

                     height=150,

                     key="op_gb_tom_tat")

        

        st.divider()

        

        # ④ Xuất báo cáo

        st.markdown("**④ Xuất báo cáo**")

        

        _pdf_dep = kiem_tra_pdf_dependency()

        if not _pdf_dep["reportlab"]:

            for msg in _pdf_dep["messages"]:

                st.warning(msg)

        

        cols_xuat = [c for c in df_bang.columns if c != "Tỷ trọng %"] or list(df_bang.columns)

        

        col_excel, col_pdf = st.columns([1, 1])

        with col_excel:

            if st.button("⬇️ Tạo Excel chuyên nghiệp", type="primary",
                         key="gb_btn_gen_excel", use_container_width=True):
                try:
                    st.session_state["_xls_giao_ban"] = xuat_excel_chuyen_nghiep(
                        df=df_bang,
                        title="Báo cáo Giao ban",
                        subtitle=f"Xã {chon_xa} · {ten_dgd or ''} · {datetime.now().strftime('%d/%m/%Y')}",
                        nguoi_xuat=st.session_state.get("txt_username", ""),
                        columns=cols_xuat,
                        kpi_items=[
                            ("Điểm GD", ten_dgd or chon_xa, ""),
                            ("Tổng dư nợ", fmt_ty(tong_dn * 1e6) if tong_dn > 0 else "—", "triệu đồng"),
                            ("Số khách hàng", fmt_so(so_kh) if so_kh > 0 else "—", ""),
                            ("Nợ quá hạn", fmt_ty(nqh * 1e6) if nqh > 0 else "—", "triệu đồng"),
                            ("Tỷ lệ NQH", f"{tl_nqh:.2f}%" if tl_nqh > 0 else "0%", ""),
                            ("Doanh số cho vay", fmt_ty(ds_cv * 1e6) if ds_cv > 0 else "—", "triệu đồng"),
                            ("Doanh số thu nợ", fmt_ty(ds_thu * 1e6) if ds_thu > 0 else "—", "triệu đồng"),
                        ],
                    )
                    st.session_state["_xls_giao_ban_fname"] = f"GiaoBan_{chon_xa}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                except Exception as e:
                    logger.error("ws_operation giao_ban xuat_excel_chuyen_nghiep: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi xuất Excel: {e}")
            if st.session_state.get("_xls_giao_ban"):
                st.download_button(
                    label="📥 Tải Excel chuyên nghiệp",
                    data=st.session_state["_xls_giao_ban"],
                    file_name=st.session_state.get("_xls_giao_ban_fname", "GiaoBan.xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="gb_download",
                    use_container_width=True,
                )

        with col_pdf:

            cols_tien_gb = [c for c in ["Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh", "Doanh số cho vay tháng", "Doanh số thu nợ tháng"] if c in df_bang.columns]


            df_chart = df_bang[df_bang[COT_DVUT] != "CỘNG"].copy()

            fig_list = []

            if not df_chart.empty and "Tổng dư nợ" in df_chart.columns:

                fig_dn = px.bar(

                    df_chart, x=COT_DVUT, y="Tổng dư nợ",

                    title="Tổng dư nợ theo ĐVUT",

                    text_auto=".1s", color_discrete_sequence=["#2E7D32"],

                )

                fig_dn.update_layout(xaxis_title="", yaxis_title="Triệu đồng")

                fig_list.append((fig_dn, "Tổng dư nợ theo ĐVUT"))

            if "Nợ quá hạn" in df_chart.columns:

                fig_nqh = px.bar(

                    df_chart, x=COT_DVUT, y="Nợ quá hạn",

                    title="Nợ quá hạn theo ĐVUT",

                    text_auto=".1s", color_discrete_sequence=["#E53935"],

                )

                fig_nqh.update_layout(xaxis_title="", yaxis_title="Triệu đồng")

                fig_list.append((fig_nqh, "Nợ quá hạn theo ĐVUT"))



            download_pdf_button(

                pdf_bytes=xuat_pdf_co_chart(

                    df=df_bang,

                    tieu_de=f"Báo cáo Giao ban - {chon_xa}",

                    nguoi_xuat=st.session_state.get("txt_username", ""),

                    figs=fig_list if fig_list else None,

                    cols_tien=cols_tien_gb,

                    prefix_file="GiaoBan",

                    them_dong_tong=False,

                ),

                filename=f"GiaoBan_{chon_xa}_{datetime.now().strftime('%Y%m%d')}.pdf",

                label=f"📥 Tải PDF ({len(df_bang)} dòng)",

                key="gb_pdf_download_v2",

            )

