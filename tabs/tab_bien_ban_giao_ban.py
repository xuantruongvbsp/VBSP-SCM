"""Biên bản họp giao ban xã — xuất Word từ dữ liệu HSTD và baseline."""
from __future__ import annotations

import os
from datetime import date

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from config import (
    COT_TEN_PGD, COT_TEN_XA,
    danh_sach_nam_baseline, baseline_path, TEMPLATES_DIR,
    baseline_pgd_path, danh_sach_nam_baseline_pgd,
    trang_thai_baseline_pgd, DON_VI_CHI_NHANH,
)
from auth import is_pgd_role
from data.hstd import doc_baseline_merged
from data.giao_ban import xuat_bien_ban_giao_ban
from state_manager import SCMStateManager
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user")
    role = kwargs.get("role")

    if df is not None and not df.empty and is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:
        df = df[df[COT_TEN_PGD] == pgd_user].copy()

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📋 Biên bản họp giao ban xã")

        if df is None or df.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return

        # 1. Chọn xã thuộc PGD
        ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())
        chon_xa = st.selectbox("Chọn xã / điểm giao dịch", ds_xa, key="op_gb2_xa")

        # 2. Chọn năm mốc so sánh — dùng doc_baseline_merged() để tổng hợp từ 22 đơn vị
        ds_nam = danh_sach_nam_baseline_pgd()
        if not ds_nam:
            ds_nam = danh_sach_nam_baseline()  # fallback năm cũ
        if not ds_nam:
            st.info("ℹ️ Chưa có dữ liệu mốc 31/12. "
                    "Vẫn xuất được — cột so sánh đầu năm sẽ trống.")
            chon_nam = None
            df_bl = None
        else:
            chon_nam = st.selectbox(
                "So sánh với mốc năm", ds_nam,
                format_func=lambda n: f"31/12/{n}",
                key="op_gb2_nam")
            fp_check = baseline_pgd_path(DON_VI_CHI_NHANH if not pgd_user else pgd_user, chon_nam)
            _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0
            df_bl = doc_baseline_merged(chon_nam, _ts=_ts)

        # 3. Nhập giải ngân (tuỳ chọn)
        with st.expander("✏️ Nhập kế hoạch giải ngân tháng tới (tuỳ chọn)"):
            st.caption("Để trống nếu chưa có kế hoạch.")
            gn_tong = st.number_input(
                "Tổng giải ngân dự kiến (triệu đồng)", min_value=0.0,
                step=1.0, key="op_gb2_gn")

        # 4. Xuất
        template = str(TEMPLATES_DIR / "BB_giao_ban_xa_template.docx")
        if not os.path.exists(template):
            st.error("Chưa có file template BB_giao_ban_xa_template.docx "
                     "trong thư mục templates/")
            return

        if st.button("🖨️ Xuất Biên bản Word", type="primary", key="gb2_xuat"):
            df_xa = df[df[COT_TEN_XA] == chon_xa].copy()
            gn_input = {"__tong__": gn_tong * 1_000_000} if gn_tong > 0 else None
            try:
                state = SCMStateManager()
                data = xuat_bien_ban_giao_ban(
                    df_xa=df_xa,
                    df_baseline=df_bl,
                    nam_moc=chon_nam or date.today().year - 1,
                    template_path=template,
                    giai_ngan_input=gn_input,
                )
                thang = date.today().strftime("%m%Y")
                ten_file = f"BB_GiaoBan_{chon_xa.replace(' ', '_')}_{thang}.docx"
                state.downloads.set("gb2_word", data, ten_file)
                st.success("✅ Đã tạo biên bản! Nhấn nút bên dưới để tải về.")
            except Exception as e:
                logger.error("xuat_bien_ban_giao_ban: %s", e, exc_info=True)
                st.error(f"❌ Lỗi xuất file: {e}")

        state = SCMStateManager()
        if state.downloads.has("gb2_word"):
            if st.download_button(
                "⬇️ Tải về Word",
                data=state.downloads.get_bytes("gb2_word"),
                file_name=state.downloads.get_filename("gb2_word"),
                mime="application/vnd.openxmlformats-officedocument"
                     ".wordprocessingml.document",
                key="gb2_dl_word",
            ):
                state.downloads.clear("gb2_word")
