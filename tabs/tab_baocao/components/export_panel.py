"""Component xuất báo cáo Excel/PDF."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from typing import TYPE_CHECKING

from utils import xuat_excel, ten_file_xuat
from services import xuat_bao_cao, ten_file_bao_cao
from pdf_service import xuat_pdf_chi_tiet
from state_manager import SCMStateManager
from db import ghi_audit
from logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def render_export_panel(
    df_export: pd.DataFrame | None = None,
    sheet_name: str = "Báo cáo",
    tieu_de: str = "Báo cáo",
    username: str = "unknown",
    prefix_file: str = "BC",
    container: DeltaGenerator | None = None,
    key_suffix: str = "",
) -> None:
    """
    Hiển thị panel xuất báo cáo.
    
    Args:
        df_export: DataFrame cần xuất
        sheet_name: Tên sheet trong Excel
        tieu_de: Tiêu đề báo cáo
        username: Tên người dùng
        prefix_file: Prefix cho tên file
        container: Streamlit container
        key_suffix: Hậu tố cho streamlit keys
    """
    ctx = container if container is not None else st
    state = SCMStateManager()
    
    if df_export is None or df_export.empty:
        ctx.info("Không có dữ liệu để xuất.")
        return
    
    ctx.markdown("#### 📥 Xuất báo cáo")
    
    col1, col2 = ctx.columns(2)
    
    with col1:
        if st.button("📊 Xuất Excel", type="primary", key=f"btn_xl_{key_suffix}"):
            try:
                buf = xuat_excel({sheet_name: df_export})
                state.downloads.set(
                    f"bc_excel_{key_suffix}",
                    buf,
                    ten_file_bao_cao(prefix_file),
                )
                ghi_audit(username, "xuat_excel", f"{tieu_de} - Excel")
                st.success("✅ Đã tạo file Excel!")
            except Exception as e:
                logger.error("export_panel: lỗi tạo Excel — %s", e, exc_info=True)
                st.error(f"❌ Lỗi tạo Excel: {e}")
        
        if state.downloads.has(f"bc_excel_{key_suffix}"):
            st.download_button(
                "⬇️ Tải Excel",
                data=state.downloads.get_bytes(f"bc_excel_{key_suffix}"),
                file_name=state.downloads.get_filename(f"bc_excel_{key_suffix}") or f"{prefix_file}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_xl_{key_suffix}",
            )
    
    with col2:
        if st.button("📄 Xuất PDF", type="primary", key=f"btn_pdf_{key_suffix}"):
            try:
                with st.spinner("Đang tạo PDF..."):
                    cols = [c for c in df_export.columns[:15]]  # Giới hạn 15 cột
                    pdf_bytes = xuat_pdf_chi_tiet(
                        df_export, cols, tieu_de, username, prefix_file
                    )
                state.downloads.set(
                    f"bc_pdf_{key_suffix}",
                    pdf_bytes,
                    f"{prefix_file}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
                )
                ghi_audit(username, "xuat_pdf", f"{tieu_de} - PDF")
                st.success("✅ Đã tạo file PDF!")
            except Exception as e:
                logger.error("export_panel: lỗi tạo PDF — %s", e, exc_info=True)
                st.error(f"❌ Lỗi tạo PDF: {e}")
        
        if state.downloads.has(f"bc_pdf_{key_suffix}"):
            st.download_button(
                "⬇️ Tải PDF",
                data=state.downloads.get_bytes(f"bc_pdf_{key_suffix}"),
                file_name=state.downloads.get_filename(f"bc_pdf_{key_suffix}") or f"{prefix_file}.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{key_suffix}",
            )
