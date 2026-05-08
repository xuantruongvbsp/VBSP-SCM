"""Tab Trạng thái Nguồn dữ liệu — hiển thị trạng thái upload cho admin/manager.

Sử dụng widget có sẵn từ:
  - widgets/data_source_status.py  → render_widget_compact, render_detailed_status
  - widgets/status_widget.py       → render_status_compact, render_priority_info
  - data/pgd.py                    → doc_trang_thai_file, lay_trang_thai_upload_pgd
"""
import streamlit as st
import pandas as pd

from config import DS_PGD, DON_VI_CHI_NHANH
from data.pgd import lay_trang_thai_upload_pgd, doc_trang_thai_file
from utils import format_df_vn
from widgets.data_source_status import render_widget_compact, render_detailed_status
from widgets.status_widget import render_priority_info


def render_tab(role: str, username: str = "unknown") -> None:
    """Entry point — hiển thị tab trạng thái nguồn dữ liệu.

    Args:
        role: Vai trò người dùng (executive/admin_cn/manager_cn/admin/manager/...)
        username: Tên đăng nhập (dùng để audit nếu cần)
    """
    st.subheader("📊 Trạng thái nguồn dữ liệu")
    st.caption("Kiểm tra tình trạng upload file của tất cả đơn vị")

    tab_tong_quan, tab_chi_tiet = st.tabs(["📋 Tổng quan", "🔍 Chi tiết theo PGD"])

    with tab_tong_quan:
        _render_tong_quan(role)

    with tab_chi_tiet:
        _render_chi_tiet_pgd()


def _render_tong_quan(role: str) -> None:
    """Hiển thị tổng quan trạng thái nguồn dữ liệu."""
    st.markdown("### Tổng quan toàn Chi nhánh")

    ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
    df_trang_thai = lay_trang_thai_upload_pgd(ds_don_vi)

    if df_trang_thai.empty:
        st.info("Chưa có dữ liệu upload từ任何 đơn vị.")
        return

    thong_ke = _tinh_thong_ke(df_trang_thai)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏢 Tổng đơn vị", thong_ke["tong_don_vi"])
    with col2:
        st.metric("✅ Đã upload HSTD", thong_ke["da_upload_hstd"],
                  delta=f"{thong_ke['ty_le_hstd']:.0f}%")
    with col3:
        st.metric("✅ Đã upload NQ11", thong_ke["da_upload_nq11"],
                  delta=f"{thong_ke['ty_le_nq11']:.0f}%")
    with col4:
        st.metric("✅ Đã upload GQVL", thong_ke["da_upload_gqvl"],
                  delta=f"{thong_ke['ty_le_gqvl']:.0f}%")

    st.markdown("### Chi tiết trạng thái từng đơn vị")
    st.dataframe(
        df_trang_thai,
        use_container_width=True,
        hide_index=True,
        height=min(60 + len(df_trang_thai) * 38, 600),
    )

    st.markdown("### Ghi chú")
    st.markdown("""
    - ✅ **dd/mm**: File đã upload, số liệu mới
    - ⚠️ **dd/mm (N ngày)**: File đã upload nhưng **N ngày chưa cập nhật** — cần kiểm tra
    - ❌ **Chưa có**: Chưa upload file — cần upload gấp
    """)


def _render_chi_tiet_pgd() -> None:
    """Hiển thị chi tiết trạng thái theo từng PGD."""
    st.markdown("### Trạng thái chi tiết theo PGD")

    danh_sach = [DON_VI_CHI_NHANH] + DS_PGD
    pgd_chon = st.selectbox(
        "Chọn đơn vị để xem chi tiết:",
        danh_sach,
        key="ttn_pgd_chon",
    )

    if not pgd_chon:
        st.info("Vui lòng chọn đơn vị.")
        return

    st.markdown(f"#### {pgd_chon}")

    cols = st.columns(3)
    loai_labels = [
        ("hstd", "📊 HSTD — Hồ sơ tín dụng"),
        ("nq11", "📑 NQ11 — Sao kê Nghị quyết 11"),
        ("gqvl", "📋 GQVL — Giải quyết việc làm"),
    ]

    for i, (loai, label) in enumerate(loai_labels):
        with cols[i]:
            tt = doc_trang_thai_file(pgd_chon, loai)
            _hien_thi_trang_thai_card(loai, label, tt)

    st.markdown("---")

    if st.button("🔄 Làm mới trạng thái", key="ttn_refresh"):
        st.cache_data.clear()
        st.rerun()


def _hien_thi_trang_thai_card(loai: str, label: str, tt: dict) -> None:
    """Hiển thị card trạng thái cho một loại file."""
    st.markdown(f"**{label}**")

    if not tt.get("co_file"):
        st.error("❌ Chưa upload")
        st.caption(f"File: `{loai}_latest.xlsx` chưa có trong thư mục PGD")
        return

    trang_thai = tt.get("canh_bao", "")
    ngay_upload = tt.get("ngay_upload")
    ngay_so_lieu = tt.get("ngay_so_lieu")
    so_ngay_cu = tt.get("so_ngay_cu", 0)

    if trang_thai == "ok":
        st.success("🟢 Dữ liệu mới")
    else:
        st.warning(f"🟡 Dữ liệu cũ ({so_ngay_cu} ngày chưa cập nhật)")

    if ngay_upload:
        st.caption(f"📅 Upload: {ngay_upload.strftime('%d/%m/%Y %H:%M')}")

    if ngay_so_lieu:
        st.caption(f"📆 Số liệu: {ngay_so_lieu.strftime('%d/%m/%Y')}")
    else:
        st.caption("📆 Số liệu: Không xác định")


def _tinh_thong_ke(df: pd.DataFrame) -> dict:
    """Tính thống kê từ DataFrame trạng thái upload."""
    tong = len(df)
    if tong == 0:
        return {
            "tong_don_vi": 0,
            "da_upload_hstd": 0, "ty_le_hstd": 0,
            "da_upload_nq11": 0, "ty_le_nq11": 0,
            "da_upload_gqvl": 0, "ty_le_gqvl": 0,
        }

    def dem_co_file(col: str) -> int:
        return int(df[col].apply(lambda x: "✅" in str(x) or "⚠️" in str(x)).sum())

    da_hstd = dem_co_file("HSTD")
    da_nq11 = dem_co_file("NQ11")
    da_gqvl = dem_co_file("GQVL")

    return {
        "tong_don_vi": tong,
        "da_upload_hstd": da_hstd, "ty_le_hstd": da_hstd / tong * 100,
        "da_upload_nq11": da_nq11, "ty_le_nq11": da_nq11 / tong * 100,
        "da_upload_gqvl": da_gqvl, "ty_le_gqvl": da_gqvl / tong * 100,
    }
