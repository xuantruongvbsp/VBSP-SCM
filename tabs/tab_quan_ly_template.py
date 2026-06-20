"""Quản lý Template Word — upload, xem danh sách, xóa và test mẫu biểu .docx."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from config import (
    TEMPLATES_DIR, TAG_MAP,
    COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_MUC_VAY,
    COT_TONG_DU_NO, COT_NGAY_VAY, COT_THOI_HAN, COT_LAI_SUAT,
)
from utils import fmt, fmt_so, quet_templates, auto_fill_document, hien_thi_dataframe_phan_trang
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Upload, quản lý và test các mẫu biểu .docx cho báo cáo tự động."""
    df = kwargs.get("df") or kwargs.get("df_full")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📁 Quản lý Template Word")
        st.caption("Upload, quản lý và test các mẫu biểu .docx cho báo cáo tự động")

        templates_path = Path(TEMPLATES_DIR)
        templates_path.mkdir(exist_ok=True)

        tab_upload, tab_danh_sach, tab_test = st.tabs([
            "📤 Upload mẫu mới", "📋 Danh sách Template", "🧪 Test Template",
        ])

        with tab_upload:
            st.markdown("**📤 Upload file template Word (.docx)**")
            uploaded_file = st.file_uploader(
                "Chọn file .docx", type=["docx"],
                help="Chỉ chấp nhận file .docx. Tên file nên mô tả rõ ràng mục đích sử dụng.",
                key="template_uploader",
            )
            if uploaded_file is not None:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.info(f"📄 **{uploaded_file.name}**")
                    st.text(f"Kích thước: {fmt_so(len(uploaded_file.getvalue()))} bytes")
                    ten_file_moi = st.text_input(
                        "Tên file (để trống = giữ tên gốc)",
                        value="",
                        help="VD: 'Mau_To_trinh_cho_vay_NOXH' (không cần .docx)",
                        key="template_new_name",
                    )
                with col2:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.button("💾 Lưu Template", type="primary", key="save_template"):
                        try:
                            ten_file = (ten_file_moi.strip().replace(".docx", "") + ".docx"
                                        if ten_file_moi.strip() else uploaded_file.name)
                            if not ten_file.lower().endswith(".docx"):
                                ten_file += ".docx"
                            file_path = templates_path / ten_file
                            if file_path.exists():
                                st.warning(f"⚠️ File **{ten_file}** đã tồn tại!")
                                if not st.checkbox("✅ Ghi đè file cũ", key="overwrite_template"):
                                    st.stop()
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getvalue())
                            st.success(f"✅ Đã lưu template: **{ten_file}**")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            logger.error("tab_quan_ly_template save: %s", e, exc_info=True)
                            st.error(f"❌ Lỗi lưu file: {e}")

        with tab_danh_sach:
            st.markdown("**📋 Danh sách Template hiện có**")
            templates = quet_templates(TEMPLATES_DIR)
            if not templates:
                st.info("📭 Chưa có template nào. Hãy upload file .docx ở tab bên trái.")
            else:
                template_data = []
                for ten_hienthi, file_path in templates:
                    file_stat = file_path.stat()
                    template_data.append({
                        "Tên hiển thị": ten_hienthi,
                        "Tên file":     file_path.name,
                        "Kích thước (KB)": f"{file_stat.st_size / 1024:.1f}",
                        "Ngày tạo": datetime.fromtimestamp(file_stat.st_ctime).strftime("%d/%m/%Y %H:%M"),
                        "Ngày sửa": datetime.fromtimestamp(file_stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                        "Đường dẫn": str(file_path),
                    })
                df_templates = pd.DataFrame(template_data)
                hien_thi_dataframe_phan_trang(
                    df_templates.drop(columns=["Đường dẫn"]),
                    key="mgmt_template_danh_sach",
                )
                st.divider()
                st.markdown("**🗑️ Xóa Template**")
                col_chon, col_xoa = st.columns([3, 1])
                label_list = [f"{row['Tên hiển thị']} ({row['Tên file']})" for _, row in df_templates.iterrows()]
                with col_chon:
                    chon_xoa = st.selectbox("Chọn template để xóa", options=label_list, key="template_delete_select")
                with col_xoa:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ Xóa", type="secondary", key="delete_template"):
                        idx = label_list.index(chon_xoa)
                        file_to_delete = Path(df_templates.iloc[idx]["Đường dẫn"])
                        try:
                            file_to_delete.unlink()
                            st.success(f"✅ Đã xóa: {file_to_delete.name}")
                            st.rerun()
                        except Exception as e:
                            logger.error("tab_quan_ly_template delete: %s", e, exc_info=True)
                            st.error(f"❌ Không thể xóa file: {e}")

        with tab_test:
            st.markdown("**🧪 Test Template với dữ liệu mẫu**")
            if df is None or df.empty:
                st.warning("⚠️ Không có dữ liệu HSTD để test. Hãy upload dữ liệu trước.")
                return
            templates = quet_templates(TEMPLATES_DIR)
            if not templates:
                st.info("📭 Không có template để test.")
                return
            col_template, col_hoso = st.columns(2)
            with col_template:
                chon_template = st.selectbox("Chọn Template", options=[t[0] for t in templates],
                                             key="test_template_select")
            with col_hoso:
                df_sample = df.head(10) if len(df) >= 10 else df
                ds_khach_hang = [
                    f"{row.get(COT_MA_KH, 'N/A')} - {row.get(COT_TEN_KH, 'Không tên')[:20]}"
                    for _, row in df_sample.iterrows()
                ]
                chon_hoso = st.selectbox("Chọn hồ sơ test", options=ds_khach_hang, key="test_hoso_select")

            idx_hoso = ds_khach_hang.index(chon_hoso)
            row_test = df_sample.iloc[idx_hoso]

            with st.expander("📄 Thông tin hồ sơ test", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Mã KH:** {row_test.get(COT_MA_KH, 'N/A')}")
                    st.write(f"**Tên KH:** {row_test.get(COT_TEN_KH, 'N/A')}")
                    st.write(f"**Số khoản vay:** {row_test.get(COT_SO_KU, 'N/A')}")
                    st.write(f"**Mức vay:** {fmt(row_test.get(COT_MUC_VAY, 0))} đồng")
                with col2:
                    st.write(f"**Dư nợ:** {fmt(row_test.get(COT_TONG_DU_NO, 0))} đồng")
                    st.write(f"**Ngày vay:** {row_test.get(COT_NGAY_VAY, 'N/A')}")
                    st.write(f"**Thời hạn:** {row_test.get(COT_THOI_HAN, 'N/A')} tháng")
                    st.write(f"**Lãi suất:** {row_test.get(COT_LAI_SUAT, 'N/A')}%")

            if st.button("🚀 Test Template", type="primary", key="test_template_btn"):
                try:
                    template_path = next((p for t, p in templates if t == chon_template), None)
                    if template_path is None:
                        st.error("❌ Không tìm thấy template!")
                        return
                    extra_data = {
                        "{{nguoi_ky}}": "Nguyễn Văn Test Manager",
                        "{{chuc_vu}}": "Phó Giám đốc Chi nhánh",
                        "{{so_quyet_dinh}}": "001/QĐ-CN",
                    }
                    doc_bytes = auto_fill_document(
                        data_row=row_test,
                        template_path=str(template_path),
                        tag_map=TAG_MAP,
                        extra=extra_data,
                    )
                    file_name = f"Test_{chon_template.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y_%H%M')}.docx"
                    st.download_button(
                        label="⬇️ Tải file Word đã test",
                        data=doc_bytes,
                        file_name=file_name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="download_test_doc",
                    )
                    st.success("✅ Test thành công! Nhấn nút trên để tải file Word.")
                except Exception as e:
                    logger.error("tab_quan_ly_template test: %s", e, exc_info=True)
                    st.error(f"❌ Lỗi test template: {e}")
                    st.exception(e)
