"""Thông báo Kết luận giao ban (NĐ30) — xuất Word/PDF tự động."""
from __future__ import annotations

import os
import tempfile
from datetime import date

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator
from dateutil.relativedelta import relativedelta

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TONG_DU_NO, COT_DU_NO_QH,
    COT_LAI_TON, COT_LAI_TON_QH, COT_SO_DU_TG, COT_TEN_TO,
    COT_NGAY_DH, COT_TEN_CT, COT_DVUT,
    danh_sach_nam_baseline, danh_sach_nam_baseline_pgd,
    baseline_pgd_path, DON_VI_CHI_NHANH,
)
from auth import is_pgd_role
from data.hstd import doc_baseline_merged
from data.giao_ban import xuat_thong_bao_ket_luan_giao_ban
from utils import fmt
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Xuất Thông báo kết luận họp giao ban tháng tại điểm giao dịch — chuẩn thể thức NĐ30."""
    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user")
    role = kwargs.get("role")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📢 Thông báo Kết luận Giao ban")
        st.caption(
            "Xuất Thông báo kết luận họp giao ban tháng "
            "tại điểm giao dịch — chuẩn thể thức NĐ30/2020"
        )

        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        if is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:
            df = df[df[COT_TEN_PGD] == pgd_user].copy()

        ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())
        if not ds_xa:
            st.warning("Không có cột Tên xã.")
            return

        default_xa = st.session_state.get("gb2_xa", ds_xa[0] if ds_xa else None)
        if default_xa not in ds_xa:
            default_xa = ds_xa[0] if ds_xa else None
        chon_xa = st.selectbox(
            "Chọn xã / điểm giao dịch",
            ds_xa,
            index=ds_xa.index(default_xa) if default_xa in ds_xa else 0,
            key="op_tb_chon_xa",
        )
        st.session_state["gb2_xa"] = chon_xa

        ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()
        chon_nam = st.session_state.get("gb2_nam")
        if ds_nam and chon_nam not in ds_nam:
            chon_nam = ds_nam[0]
        df_bl = None
        if ds_nam and chon_nam is not None:
            fp_check = baseline_pgd_path(
                DON_VI_CHI_NHANH if not pgd_user else pgd_user, chon_nam
            )
            _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0
            df_bl = doc_baseline_merged(chon_nam, _ts=_ts)

        col_a, col_b = st.columns(2)
        with col_a:
            tb_dgd = st.text_input(
                "Tên điểm giao dịch",
                value=chon_xa,
                key="op_tb_ten_dgd",
                help="Mặc định là tên xã, chỉnh lại nếu khác",
            )
            tb_ngay = st.date_input("Ngày họp", value=date.today(), format="DD/MM/YYYY", key="op_tb_ngay_hop")
        with col_b:
            tb_so_vb = st.text_input(
                "Số văn bản",
                placeholder="VD: 05",
                key="op_tb_so_van_ban",
                help="Phần số trong 'Số: .../TB-KLGB'",
            )
            tb_ten_ky = st.text_input(
                "Tên người ký",
                placeholder="VD: Nguyễn Văn A",
                key="op_tb_ten_nguoi_ky",
                help="Tên Phó Giám đốc ký văn bản",
            )

        # Preview số liệu tự động
        df_xa_preview = df[df[COT_TEN_XA] == chon_xa].copy()
        if not df_xa_preview.empty:
            dn_prev = pd.to_numeric(df_xa_preview[COT_TONG_DU_NO], errors="coerce").sum() / 1e6
            nqh_prev = pd.to_numeric(df_xa_preview[COT_DU_NO_QH], errors="coerce").sum() / 1e6
            lai_prev = (
                pd.to_numeric(df_xa_preview.get(COT_LAI_TON, 0), errors="coerce").sum()
                + pd.to_numeric(df_xa_preview.get(COT_LAI_TON_QH, 0), errors="coerce").sum()
            ) / 1e6
            tg_prev = pd.to_numeric(df_xa_preview.get(COT_SO_DU_TG, 0), errors="coerce").sum() / 1e6
            st.info(
                f"📊 **Số liệu tự động — {chon_xa}**\n\n"
                f"Dư nợ: **{fmt(dn_prev * 1e6)}** triệu · "
                f"NQH: **{fmt(nqh_prev * 1e6)}** triệu · "
                f"Lãi tồn: **{fmt(lai_prev * 1e6)}** triệu · "
                f"Tiền gửi TK: **{fmt(tg_prev * 1e6)}** triệu"
            )

        # Giải ngân kế hoạch tháng tới
        thang_toi = date.today() + relativedelta(months=1)
        ngay_dh_col = "Ngày ĐH theo Gia hạn" if "Ngày ĐH theo Gia hạn" in df_xa_preview.columns else COT_NGAY_DH
        mask_dh = (
            pd.to_datetime(df_xa_preview[ngay_dh_col], errors="coerce").dt.month == thang_toi.month
        ) & (
            pd.to_datetime(df_xa_preview[ngay_dh_col], errors="coerce").dt.year == thang_toi.year
        )
        df_dh_prev = df_xa_preview[mask_dh].copy()
        giai_ngan_input = {}
        with st.expander("💰 Nhập số giải ngân dự kiến tháng tới (tùy chọn)"):
            st.caption("Để trống nếu chưa xác định. Nhập theo đơn vị triệu đồng.")
            if not df_dh_prev.empty and COT_TEN_TO in df_dh_prev.columns:
                for (dvut, to, ct), grp in df_dh_prev.groupby([COT_DVUT, COT_TEN_TO, COT_TEN_CT]):
                    val = st.number_input(
                        f"{to} — {ct}",
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                        format="%.0f",
                        key=f"op_gn_{dvut}_{to}_{ct}",
                        help="Triệu đồng",
                    )
                    if val > 0:
                        giai_ngan_input[(dvut, to, ct)] = val * 1e6
            else:
                st.caption("Không có món đến hạn tháng tới hoặc chưa có dữ liệu.")
                giai_ngan_input = None

        tb_cs = st.text_area(
            "I. Chính sách mới trong tháng",
            placeholder="Để trống nếu không có chính sách mới...",
            height=100,
            key="op_tb_chinh_sach",
        )
        tb_tt = st.text_area(
            "II.2 Tồn tại, hạn chế",
            placeholder="Nêu cụ thể tồn tại của Hội, Tổ, khách hàng...",
            height=120,
            key="op_tb_ton_tai",
        )
        tb_nv = st.text_area(
            "III. Nhiệm vụ tháng tiếp theo",
            placeholder="Kế hoạch kiểm tra, xử lý nợ xấu, nội dung khác...",
            height=120,
            key="op_tb_nhiem_vu",
        )

        if st.button("🖨️ Xuất Thông báo Kết luận Word", type="primary", key="tb_xuat"):
            df_xa_tb = df[df[COT_TEN_XA] == chon_xa].copy() if COT_TEN_XA in df.columns else pd.DataFrame()
            if df_xa_tb.empty:
                st.warning(f"⚠️ Không có dữ liệu cho xã **{chon_xa}**.")
            else:
                try:
                    data = xuat_thong_bao_ket_luan_giao_ban(
                        df_xa=df_xa_tb,
                        ten_pgd=pgd_user or "",
                        ten_xa=chon_xa,
                        ten_dgd=tb_dgd or chon_xa,
                        thang_bao_cao=tb_ngay.month,
                        nam_bao_cao=tb_ngay.year,
                        ngay_hop=tb_ngay.strftime("%d/%m/%Y"),
                        chinh_sach_moi=tb_cs,
                        ton_tai_han_che=tb_tt,
                        nhiem_vu_tiep=tb_nv,
                        so_van_ban=tb_so_vb,
                        ten_nguoi_ky=tb_ten_ky,
                        giai_ngan_input=giai_ngan_input,
                        df_baseline=df_bl,
                        nam_moc=chon_nam or date.today().year - 1,
                    )
                    ten_file = (
                        f"TB_KetLuan_{chon_xa.replace(' ', '_')}"
                        f"_{date.today().strftime('%m%Y')}.docx"
                    )
                    st.session_state["tb_data"] = data
                    st.session_state["tb_ten_file"] = ten_file
                    st.success("✅ Đã tạo Thông báo Kết luận! Nhấn nút bên dưới để tải về.")
                except Exception as e:
                    logger.error("xuat_thong_bao_ket_luan_giao_ban: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi tạo file: {e}")

        if st.session_state.get("tb_data"):
            st.download_button(
                "⬇️ Tải về Word",
                data=st.session_state["tb_data"],
                file_name=st.session_state["tb_ten_file"],
                mime="application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document",
                key="tb_dl_word",
            )

        if st.session_state.get("tb_data") and st.button("📄 Xuất PDF", type="primary", key="tb_xuat_pdf"):
            try:
                from docx2pdf import convert
                data_pdf = st.session_state["tb_data"]
                ten_file_pdf = st.session_state["tb_ten_file"]
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    tmp.write(data_pdf)
                    tmp_path = tmp.name
                pdf_path = tmp_path.replace(".docx", ".pdf")
                convert(tmp_path, pdf_path)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                os.unlink(tmp_path)
                os.unlink(pdf_path)
                ten_pdf = ten_file_pdf.replace(".docx", ".pdf")
                st.session_state["_tb_pdf_bytes"] = pdf_bytes
                st.session_state["_tb_pdf_file"] = ten_pdf
            except ImportError:
                st.warning("⚠️ Chưa cài docx2pdf. Chạy: pip install docx2pdf")
                st.info("💡 Mở file Word rồi chọn **Save As → PDF** thủ công.")
                st.session_state["_tb_pdf_bytes"] = None
            except Exception as _e_pdf:
                logger.error("xuat_pdf_tb_ket_luan: %s", _e_pdf, exc_info=True)
                st.error(f"❌ Lỗi chuyển PDF: {_e_pdf}")
                st.session_state["_tb_pdf_bytes"] = None

        if st.session_state.get("_tb_pdf_bytes"):
            st.download_button(
                "⬇️ Tải về PDF",
                data=st.session_state["_tb_pdf_bytes"],
                file_name=st.session_state.get("_tb_pdf_file", "output.pdf"),
                mime="application/pdf",
                key="tb_dl_pdf",
            )
