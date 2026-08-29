"""Quick export component cho báo cáo - xuất nhanh không cần chuyển tab."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import TYPE_CHECKING

from utils import xuat_excel
from services import xuat_bao_cao, ten_file_bao_cao
from db import ghi_audit
from logger import get_logger
from state_manager import SCMStateManager

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def render_quick_export_buttons(
    df: pd.DataFrame,
    sheet_name: str,
    tieu_de: str,
    username: str,
    prefix_file: str,
    key: str,
    container: DeltaGenerator | None = None,
    show_excel: bool = True,
    show_pdf: bool = True,
    pdf_func = None,
    df_excel: pd.DataFrame | None = None,
) -> None:
    """
    Hiển thị nút xuất nhanh ngay trên bảng.
    
    Args:
        df: DataFrame dùng cho PDF (thô, tự format trong pdf_func)
        sheet_name: Tên sheet
        tieu_de: Tiêu đề báo cáo
        username: Username
        prefix_file: Prefix file name
        key: Streamlit unique key
        container: Streamlit container
        show_excel: Hiển thị nút Excel
        show_pdf: Hiển thị nút PDF
        pdf_func: Hàm tạo PDF (optional)
        df_excel: DataFrame riêng cho Excel (đã format), mặc định dùng df
    """
    ctx = container if container is not None else st
    state = SCMStateManager()
    
    if df.empty:
        ctx.caption("📭 Không có dữ liệu để xuất")
        return
    
    df_export = df_excel if df_excel is not None else df
    
    # Row chứa các nút export
    cols = ctx.columns([1, 1, 3])  # Excel, PDF, spacer
    
    # Excel button
    if show_excel:
        with cols[0]:
            if st.button("📊 Excel", key=f"qexp_xl_{key}", type="secondary", use_container_width=True):
                xl_bytes = xuat_excel({sheet_name: df_export})
                state_key = f"qexp_xl_{key}_data"
                state.downloads.set(
                    state_key,
                    xl_bytes,
                    ten_file_bao_cao(prefix_file),
                )
                ghi_audit(username, "quick_export_excel", tieu_de)
                st.success("✅ Đã tạo Excel!")
            
            # Download button
            state_key = f"qexp_xl_{key}_data"
            if state.downloads.has(state_key):
                st.download_button(
                    "⬇️ Tải",
                    data=state.downloads.get_bytes(state_key),
                    file_name=state.downloads.get_filename(state_key) or f"{prefix_file}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"qexp_xl_dl_{key}",
                    use_container_width=True,
                )
    
    # PDF button
    if show_pdf:
        with cols[1]:
            if pdf_func and st.button("📄 PDF", key=f"qexp_pdf_{key}", type="secondary", use_container_width=True):
                try:
                    with st.spinner("Đang tạo PDF..."):
                        pdf_bytes = pdf_func(df, tieu_de, username)
                    
                    state_key = f"qexp_pdf_{key}_data"
                    state.downloads.set(
                        state_key,
                        pdf_bytes,
                        f"{prefix_file}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
                    )
                    ghi_audit(username, "quick_export_pdf", tieu_de)
                    st.success("✅ Đã tạo PDF!")
                except Exception as e:
                    logger.error("quick_export: lỗi tạo PDF — %s", e, exc_info=True)
                    st.error(f"❌ Lỗi: {e}")
            
            # Download PDF button
            state_key = f"qexp_pdf_{key}_data"
            if pdf_func and state.downloads.has(state_key):
                st.download_button(
                    "⬇️ Tải",
                    data=state.downloads.get_bytes(state_key),
                    file_name=state.downloads.get_filename(state_key) or f"{prefix_file}.pdf",
                    mime="application/pdf",
                    key=f"qexp_pdf_dl_{key}",
                    use_container_width=True,
                )
    
    # Hiển thị thông tin
    with cols[2]:
        ctx.caption(f"📋 {len(df):,} dòng • Cập nhật: {datetime.now().strftime('%H:%M')}".replace(",", "."))


def render_bulk_export(
    dfs: dict[str, pd.DataFrame],
    tieu_de: str,
    username: str,
    prefix_file: str,
    key: str,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Xuất nhiều sheets một lúc.
    
    Args:
        dfs: Dict {sheet_name: DataFrame}
        tieu_de: Tiêu đề
        username: Username
        prefix_file: Prefix
        key: Streamlit key
        container: Streamlit container
    """
    ctx = container if container is not None else st
    state = SCMStateManager()
    
    total_rows = sum(len(df) for df in dfs.values())
    
    col1, col2 = ctx.columns([1, 3])
    
    with col1:
        if st.button("📦 Xuất tất cả", key=f"bulk_exp_{key}", type="primary"):
            # Chỉ xuất các sheet không rỗng
            valid_sheets = {k: v for k, v in dfs.items() if not v.empty}
            
            if valid_sheets:
                xl_bytes = xuat_excel(valid_sheets)
                state_key = f"bulk_exp_{key}_data"
                state.downloads.set(
                    state_key,
                    xl_bytes,
                    ten_file_bao_cao(f"{prefix_file}_FULL"),
                )
                ghi_audit(username, "bulk_export", f"{tieu_de} - {len(valid_sheets)} sheets")
                st.success(f"✅ Đã tạo file với {len(valid_sheets)} sheets!")
            else:
                st.warning("📭 Không có dữ liệu để xuất")
    
    with col2:
        ctx.caption(f"📊 Tổng cộng: {total_rows:,} dòng trong {len(dfs)} báo cáo".replace(",", "."))
    
    # Download button
    state_key = f"bulk_exp_{key}_data"
    if state.downloads.has(state_key):
        st.download_button(
            "⬇️ Tải file tổng hợp",
            data=state.downloads.get_bytes(state_key),
            file_name=state.downloads.get_filename(state_key) or f"{prefix_file}_FULL.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"bulk_exp_dl_{key}",
            type="primary",
        )
