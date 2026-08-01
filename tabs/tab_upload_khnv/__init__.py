"""
Tab Upload KH-NV — Phòng Kế hoạch Nghiệp vụ.
────────────────────────────────────────────
Quyền: role in ("admin", "manager", "admin_cn", "manager_cn")

Cấu trúc 6 sub-tabs:
  📊 Tổng quan & Merge  — bảng trạng thái + pending queue + nút Merge thủ công
  📤 Upload đơn vị      — form upload 4 file cho 1 đơn vị
  📦 Import hàng loạt   — multi-file bulk import
  🏢 Toàn Chi nhánh     — CDTOTKVV / NQ11 / GQVL toàn CN
  📅 Mốc 31/12          — upload file baseline
  🗑️ Xóa dữ liệu        — xóa file + rebuild cache

Flow batch merge:
  Upload đơn vị → lưu vào pgd_data/ → thêm vào pending queue
  Import hàng loạt → lưu vào pgd_data/ → tự merge toàn CN → cache clear
"""
from __future__ import annotations

import streamlit as st

from auth import la_phan_he_cn, normalize_role
from tabs.base_tab import TabContext
from utils import lazy_tabs

from . import _status_board, _merge_panel, _baseline, _delete
from ._upload_don_vi import render_upload_don_vi, render_import_hang_loat
from ._upload_toan_cn import render_cdto_toan_cn, render_nq11_toan_cn, render_gqvl_toan_cn
from ._state import xoa_cache_trang_thai


def render(tab=None, **kwargs) -> None:
    """Entry point — nhận tab (st.tab object) hoặc render trong context hiện tại."""
    role     = kwargs.get("role", "")
    username = kwargs.get("username", "unknown")
    df_full  = kwargs.get("df_full")

    _ctx = TabContext(tab, **kwargs)
    with _ctx:
        if not la_phan_he_cn(role) or normalize_role(role) == "executive":
            st.error("🔒 Chức năng này chỉ dành cho Phòng KH-NV (admin/manager).")
            return

        # Header
        col_title, col_badge = st.columns([6, 1])
        with col_title:
            st.markdown("## 📤 Upload Dữ liệu — Phòng KH-NV")
        with col_badge:
            st.markdown(
                "<div style='text-align:right;padding-top:14px'>"
                "<span style='background:#0d6efd;color:white;padding:4px 12px;"
                "border-radius:12px;font-size:12px;font-weight:600'>KH-NV</span>"
                "</div>",
                unsafe_allow_html=True,
            )

        st.info(
            "💡 Upload file Điện báo thực hiện tại tab **📡 Điện Báo**, không phải tab này."
        )

        def _render_tong_quan(_tab=None) -> None:
            col_tt, col_rf = st.columns([5, 1])
            with col_tt:
                st.markdown("#### 📋 Trạng thái Upload — 22 Đơn vị")
            with col_rf:
                if st.button("🔄 Làm mới", key="btn_refresh_trang_thai", use_container_width=True):
                    xoa_cache_trang_thai()
                    st.cache_data.clear()
                    st.rerun()

            with st.container(key="khnv_bang_trang_thai_upload"):
                _status_board.render_bang_trang_thai()

            st.divider()
            st.markdown("#### 🔄 Merge & Rebuild Cache")
            _merge_panel.render(username)

        def _render_upload_don_vi(_tab=None) -> None:
            st.markdown("#### 📤 Upload file cho từng đơn vị")
            st.caption(
                "Upload 1–4 file cho một đơn vị. "
                "File được lưu vào hàng chờ — "
                "chuyển sang tab **📊 Tổng quan** để merge khi xong."
            )
            render_upload_don_vi(username)

        def _render_import_hang_loat(_tab=None) -> None:
            st.markdown("#### 📦 Import hàng loạt")
            st.caption(
                "Chọn nhiều file cùng lúc — hệ thống tự nhận diện loại và PGD. "
                "File được lưu vào hàng chờ — chuyển sang **📊 Tổng quan** để merge."
            )
            render_import_hang_loat(role, username)

        def _render_toan_chi_nhanh(_tab=None) -> None:
            st.markdown("#### 🏢 Upload dữ liệu Toàn Chi nhánh")
            lazy_tabs(
                ["🏆 CDTOTKVV toàn CN", "📑 Danh sách mã KU NQ11", "📋 GQVL toàn CN"],
                [
                    lambda c: render_cdto_toan_cn(username),
                    lambda c: render_nq11_toan_cn(username),
                    lambda c: render_gqvl_toan_cn(username, df_full),
                ],
                key="khnv_upload_toan_cn",
            )

        def _render_baseline(_tab=None) -> None:
            _baseline.render(username)

        def _render_xoa_du_lieu(_tab=None) -> None:
            st.markdown("#### 🗑️ Xóa dữ liệu PGD")
            _delete.render(role=role, username=username)

        lazy_tabs(
            [
                "📊 Tổng quan",
                "📤 Upload đơn vị",
                "📦 Import hàng loạt",
                "🏢 Toàn Chi nhánh",
                "📅 Mốc 31/12",
                "🗑️ Xóa dữ liệu",
            ],
            [
                _render_tong_quan,
                _render_upload_don_vi,
                _render_import_hang_loat,
                _render_toan_chi_nhanh,
                _render_baseline,
                _render_xoa_du_lieu,
            ],
            key="khnv_upload",
        )
