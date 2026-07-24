"""UI lưu trữ báo cáo cho tab Tiến độ nộp báo cáo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.report_submission_service import (
    khoi_phuc_loai_bao_cao,
    loc_du_lieu_luu_tru,
)
from utils import xuat_excel


def render_archive(
    df: pd.DataFrame,
    archive_cfg: dict[str, dict],
    username: str,
    can_config: bool,
) -> None:
    """Hiển thị lịch sử báo cáo đã lưu trữ và cho phép khôi phục."""
    st.subheader("🗃️ Báo cáo đã lưu trữ")
    st.caption(
        "Dữ liệu vẫn nằm trong Google Sheet và được tách khỏi deadline, Tổng quan đang hoạt động "
        "và Telegram."
    )
    if not archive_cfg:
        st.info("Chưa có loại báo cáo nào được lưu trữ.")
        return

    options = sorted(archive_cfg)

    def _archive_label(key: str) -> str:
        return str(archive_cfg.get(key, {}).get("ten_hien_thi") or key)

    selected = st.selectbox(
        "Loại báo cáo lưu trữ",
        options=options,
        format_func=_archive_label,
        key="tdn_archive_view_type",
    )
    selected_cfg = {selected: archive_cfg[selected]}
    df_luu = loc_du_lieu_luu_tru(df, selected_cfg, archived=True)
    meta = archive_cfg[selected]

    archived_at = meta.get("luu_tru_luc", "")
    try:
        archived_at_text = pd.to_datetime(archived_at).strftime("%H:%M %d/%m/%Y")
    except Exception:
        archived_at_text = "—"
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Loại lưu trữ", "1")
    m2.metric("Lượt nộp", len(df_luu))
    m3.metric("Đơn vị đã nộp", df_luu["ten_pgd"].nunique() if not df_luu.empty else 0)
    m4.metric("Lưu trữ lúc", archived_at_text)
    st.caption(
        f"Người lưu trữ: **{meta.get('luu_tru_boi', '—')}** · "
        f"Deadline cũ: **{meta.get('deadline_cu') or '—'}**"
    )

    if df_luu.empty:
        st.warning("Loại này đã được đánh dấu lưu trữ nhưng chưa có lượt nộp trong phạm vi bạn được xem.")
    else:
        df_hien = df_luu[
            [
                "thoi_gian",
                "ten_pgd",
                "loai_bao_cao",
                "ky_bao_cao",
                "ho_ten",
                "noi_dung",
                "file_dinh_kem",
            ]
        ].copy()
        df_hien["thoi_gian"] = pd.to_datetime(df_hien["thoi_gian"], errors="coerce").dt.strftime(
            "%d/%m/%Y %H:%M"
        )
        df_hien = df_hien.rename(
            columns={
                "thoi_gian": "Thời gian",
                "ten_pgd": "Đơn vị",
                "loai_bao_cao": "Loại báo cáo",
                "ky_bao_cao": "Kỳ báo cáo",
                "ho_ten": "Người nộp",
                "noi_dung": "Nội dung",
                "file_dinh_kem": "File",
            }
        )
        st.dataframe(
            df_hien,
            hide_index=True,
            use_container_width=True,
            column_config={"File": st.column_config.LinkColumn("File", display_text="📎 Xem")},
        )
        excel_bytes = xuat_excel({"Báo cáo đã lưu trữ": df_hien})
        st.download_button(
            "📥 Xuất Excel lịch sử",
            data=excel_bytes,
            file_name="bao_cao_da_luu_tru.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="tdn_archive_excel",
        )

    if can_config:
        st.divider()
        st.markdown("#### Khôi phục loại báo cáo")
        st.caption(
            "Sau khi khôi phục, báo cáo trở lại nhóm Cần cài deadline. Deadline cũ không tự bật lại."
        )
        confirm_restore = st.checkbox(
            "Tôi xác nhận muốn khôi phục loại báo cáo này",
            key="tdn_archive_restore_confirm",
        )
        if st.button(
            "↩️ Khôi phục",
            key="tdn_archive_restore",
            disabled=not confirm_restore,
        ):
            if khoi_phuc_loai_bao_cao(selected, username):
                st.cache_data.clear()
                st.success(f"✅ Đã khôi phục: **{_archive_label(selected)}**")
                st.rerun()
            else:
                st.warning("Loại báo cáo này không còn trong danh mục lưu trữ.")
