"""
Widget hiển thị trạng thái dữ liệu compact cho sidebar.
──────────────────────────────────────────────────────────────────────
Hai luồng dữ liệu độc lập:
  ws_operation (role=user/admin/manager):
    → hiển thị trạng thái file pgd_data/ của PGD
  ws_management / ws_executive (role=admin/manager):
    → hiển thị trạng thái CACHE_HSTD (do KH-NV tạo)

Không dùng ngôn ngữ "ưu tiên / fallback" — hai luồng hoàn toàn tách biệt.
"""
import streamlit as st
from typing import Optional
from datetime import datetime

from config import DS_PGD, CACHE_HSTD
from utils import format_df_vn
try:
    from services.data_priority_service import (
        lay_thong_tin_nguon_hien_tai,
        thong_ke_su_dung_nguon
    )
    from data.pgd import doc_trang_thai_file
    DATA_PRIORITY_AVAILABLE = True
except ImportError:
    DATA_PRIORITY_AVAILABLE = False


def render_widget_compact(pgd_user: Optional[str] = None, role: str = "user",
                          ws_hien_tai: str = "operation") -> None:
    """
    Widget compact hiển thị trạng thái dữ liệu trong sidebar.

    Args:
        pgd_user: Tên PGD của user hiện tại (nếu có)
        role: Vai trò của user
        ws_hien_tai: Workspace đang dùng ("operation" / "management" / "executive")
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 📊 Dữ liệu")

    if ws_hien_tai in ("management", "executive"):
        _render_cache_status()
        return

    # ws_operation — hiển thị trạng thái pgd_data/
    if not DATA_PRIORITY_AVAILABLE:
        st.sidebar.markdown("---")
        if pgd_user:
            st.sidebar.info(f"🏢 **{pgd_user}**\n\n📤 Chưa kiểm tra file")
        else:
            st.sidebar.info("📤 Dữ liệu địa bàn")
        return

    if role == "user" and pgd_user:
        _render_pgd_status(pgd_user)
    elif role in ["admin", "manager"]:
        _render_admin_overview()
    else:
        st.sidebar.info("📤 Dữ liệu địa bàn")


def _render_cache_status() -> None:
    """Hiển thị trạng thái CACHE_HSTD cho ws_management/executive."""
    import os
    try:
        if os.path.exists(CACHE_HSTD):
            mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_HSTD))
            st.sidebar.success(f"✅ CACHE KH-NV\n\n📅 {mtime.strftime('%d/%m %H:%M')}")
        else:
            st.sidebar.warning("⚠️ Chưa có CACHE KH-NV\n\nVui lòng upload tại tab KH-NV")
    except Exception:
        st.sidebar.info("🔄 CACHE KH-NV")


def _render_pgd_status(pgd_user: str) -> None:
    """Hiển thị trạng thái file pgd_data/ cho PGD cụ thể."""
    try:
        thong_tin = lay_thong_tin_nguon_hien_tai(pgd_user)
        hstd_info = thong_tin.get("hstd", {})

        nguon = hstd_info.get("nguon", "chua_upload")
        tt = hstd_info.get("trang_thai", {})

        st.sidebar.markdown(f"🏢 **{pgd_user}**")

        if nguon == "pgd_upload" and tt.get("co_file", False):
            if tt.get("canh_bao") == "ok":
                mo_ta = f"✅ Đã upload\n({tt['ngay_upload'].strftime('%d/%m') if tt.get('ngay_upload') else ''})"
                st.sidebar.success(mo_ta)
            else:
                mo_ta = f"⚠️ Đã upload\n({tt['so_ngay_cu']} ngày chưa cập nhật)"
                st.sidebar.warning(mo_ta)
        else:
            st.sidebar.warning("📤 Chưa upload dữ liệu địa bàn")

        with st.sidebar.expander("📋 Chi tiết các file"):
            for loai in ["nq11", "gqvl", "cdtotkvv"]:
                info = thong_tin.get(loai, {})
                nguon_file = info.get("nguon", "chua_upload")
                tt_file = info.get("trang_thai", {})

                if nguon_file == "pgd_upload" and tt_file.get("co_file", False):
                    if tt_file.get("canh_bao") == "ok":
                        st.markdown(f"**{loai.upper()}**: ✅ Đã upload")
                    else:
                        st.markdown(f"**{loai.upper()}**: ⚠️ Cần cập nhật")
                else:
                    st.markdown(f"**{loai.upper()}**: 📤 Chưa upload")

    except Exception as e:
        st.sidebar.error(f"Lỗi hiển thị: {str(e)[:50]}...")


def _render_admin_overview() -> None:
    """Hiển thị tổng quan trạng thái upload cho admin/manager."""
    try:
        thong_ke = thong_ke_su_dung_nguon()
        tong_pgd = len(DS_PGD)

        pgd_upload = thong_ke.get("pgd_upload", 0)
        ty_le = (pgd_upload / tong_pgd * 100) if tong_pgd > 0 else 0

        st.sidebar.markdown("**📊 Upload địa bàn**")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("PGD", tong_pgd)
        with col2:
            st.metric("Đã upload", pgd_upload)

        st.sidebar.progress(ty_le / 100, text=f"{ty_le:.0f}% đã upload")

        if ty_le < 70:
            st.sidebar.warning("💡 Một số PGD chưa upload dữ liệu địa bàn")
        else:
            st.sidebar.success("✅ Tỷ lệ upload tốt")

    except Exception:
        st.sidebar.info("📊 Dữ liệu địa bàn")


def render_detailed_status(pgd_user: Optional[str] = None,
                           show_all_pgd: bool = False) -> None:
    """
    Widget chi tiết hiển thị trạng thái dữ liệu trong main content.
    """
    if not DATA_PRIORITY_AVAILABLE:
        st.info("📤 Dữ liệu địa bàn chưa được kiểm tra")
        return

    st.subheader("📊 Trạng thái dữ liệu địa bàn")

    try:
        from services.data_priority_service import (
            bao_cao_trang_thai_nguon,
            hien_thi_tong_quan_nguon
        )

        if show_all_pgd:
            hien_thi_tong_quan_nguon()

            st.markdown("### 📋 Chi tiết từng PGD")
            df_bao_cao = bao_cao_trang_thai_nguon()
            st.dataframe(
                format_df_vn(df_bao_cao),
                use_container_width=True,
                hide_index=True,
                height=400,
            )
        elif pgd_user:
            from services.data_priority_service import hien_thi_trang_thai_nguon_widget
            hien_thi_trang_thai_nguon_widget(pgd_user)
        else:
            st.info("Chọn PGD để xem chi tiết trạng thái dữ liệu địa bàn")

    except Exception as e:
        st.error(f"Lỗi hiển thị chi tiết: {e}")


# Alias cho tương thích ngược
def render_compact_widget(*args, **kwargs):
    """Alias cho render_widget_compact."""
    return render_widget_compact(*args, **kwargs)