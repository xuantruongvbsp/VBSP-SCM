"""
Trung tâm Upload (Upload Center) — Tab Quản trị hệ thống
──────────────────────────────────────────────────────────────────────────────
Module này quản lý upload file hệ thống (HSTD gốc, NQ11 gốc, Điện báo)
qua tab Quản trị. Upload theo PGD nằm ở tab_upload_khnv / tab_upload_pgd.

Hàm công khai:
  render_panel_upload(role, prefix)  — giao diện upload file hệ thống + Điện báo
  lay_trang_thai()                   — dict trạng thái file hiện tại
  hien_thi_trang_thai_nho()          — banner trạng thái mini cho tab không upload
"""
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

import db
from config import (
    FILE_PATH, FILE_PATH_NQ11, FILE_PATH_DB, FILE_PATH_DB_PREV,
    TEN_FILE, TEN_FILE_NQ11, TEN_FILE_DB, TEN_FILE_DB_PREV,
    DB_HT_CACHE, DB_PREV_CACHE, CACHE_DIR,
    PGD_DATA_DIR, UPLOAD_CANH_BAO_NGAY, DON_VI_CHI_NHANH, DS_PGD,
)
from services.upload_service import (
    FILES_HE_THONG,
    kiem_tra_file_he_thong,
    luu_file_he_thong,
    luu_dienbao,
)

# ── Khóa session state dùng chung toàn ứng dụng ─────────────────────────────
KHOA_TRANG_THAI = "upload_center_trang_thai"

# Ánh xạ tên file → nhãn hiển thị và đường dẫn thực tế
_DS_FILE_THAM_CHIEU: dict[str, tuple[str, str]] = {
    TEN_FILE:         ("📊 HSTD",             FILE_PATH),
    TEN_FILE_NQ11:    ("📑 Sao kê NQ11",       FILE_PATH_NQ11),
    TEN_FILE_DB:      ("⚖️ Điện báo HT",       FILE_PATH_DB),
    TEN_FILE_DB_PREV: ("⚖️ Điện báo 31/12",    FILE_PATH_DB_PREV),
}


# ── Ghi trạng thái upload vào session state ───────────────────────────────────

def _cap_nhat_session(ten_file: str, duong_dan: str) -> None:
    """Ghi thông tin upload vào session state để các tab khác tham chiếu."""
    if KHOA_TRANG_THAI not in st.session_state:
        st.session_state[KHOA_TRANG_THAI] = {}
    st.session_state[KHOA_TRANG_THAI][ten_file] = {
        "duong_dan":    duong_dan,
        "thoi_gian":    datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "nguoi_upload": st.session_state.get("username", "—"),
    }


# ── Tra cứu trạng thái ────────────────────────────────────────────────────────

def lay_trang_thai() -> dict:
    """
    Trả về dict trạng thái upload trong phiên làm việc hiện tại.
    Các tab khác gọi hàm này để biết file nào đã được upload.
    """
    return st.session_state.get(KHOA_TRANG_THAI, {})


def duong_dan_hien_tai(loai: str) -> str | None:
    """
    Trả về đường dẫn đang hoạt động cho từng loại file.
    loai: "hstd" | "nq11" | "db_ht" | "db_prev"
    """
    anh_xa = {
        "hstd":    (None,          FILE_PATH),
        "nq11":    (None,          FILE_PATH_NQ11),
        "db_ht":   (DB_HT_CACHE,   FILE_PATH_DB),
        "db_prev": (DB_PREV_CACHE, FILE_PATH_DB_PREV),
    }
    if loai not in anh_xa:
        return None
    cache_path, goc_path = anh_xa[loai]
    if cache_path and os.path.exists(cache_path):
        return cache_path
    if os.path.exists(goc_path):
        return goc_path
    return None


# ── Banner trạng thái mini ────────────────────────────────────────────────────

def _hien_thi_trang_thai_file_he_thong(ten_file_can: str | None = None) -> None:
    """
    Hiển thị trạng thái 4 file hệ thống (HSTD/NQ11/Điện báo) dưới dạng card.
    Dùng nội bộ trong render_panel_upload — không gọi từ các tab phân tích.
    ten_file_can: chỉ kiểm tra file này (None = hiển thị tất cả 4 file).
    """
    trang_thai_ss = lay_trang_thai()

    ds_kiem_tra: dict[str, tuple[str, str]] = {
        ten: (mo_ta, (
            (DB_HT_CACHE   if os.path.exists(DB_HT_CACHE)   else FILE_PATH_DB)
            if ten == TEN_FILE_DB else
            (DB_PREV_CACHE if os.path.exists(DB_PREV_CACHE) else FILE_PATH_DB_PREV)
            if ten == TEN_FILE_DB_PREV else path
        ))
        for ten, (mo_ta, path) in _DS_FILE_THAM_CHIEU.items()
    }

    if ten_file_can and ten_file_can in ds_kiem_tra:
        ds_kiem_tra = {ten_file_can: ds_kiem_tra[ten_file_can]}

    cols = st.columns(len(ds_kiem_tra))
    for col, (ten, (mo_ta, path)) in zip(cols, ds_kiem_tra.items()):
        if os.path.exists(path):
            ts  = datetime.fromtimestamp(os.path.getmtime(path))
            mb  = os.path.getsize(path) / 1024 / 1024
            age = (datetime.now() - ts).days
            if ten in trang_thai_ss:
                info = trang_thai_ss[ten]
                col.success(
                    f"**{mo_ta}**\n\n"
                    f"✅ {ts.strftime('%d/%m %H:%M')} · {mb:.1f} MB\n\n"
                    f"👤 {info['nguoi_upload']}"
                )
            else:
                icon = "✅" if age == 0 else ("⚠️" if age <= 3 else "🔴")
                col.info(
                    f"**{mo_ta}**\n\n"
                    f"{icon} {ts.strftime('%d/%m/%Y')} · {mb:.1f} MB"
                )
        else:
            col.warning(
                f"**{mo_ta}**\n\n"
                f"❌ Chưa có file\n\n"
                f"Upload tại **⚙️ Quản lý HT**"
            )


def hien_thi_trang_thai_nho() -> None:
    """
    Banner cảnh báo toàn cục — hiển thị đầu mỗi tab phân tích.

    Scan toàn bộ pgd_data/ theo từng loại file. Nếu có bất kỳ đơn vị nào
    có file cũ hơn ngưỡng UPLOAD_CANH_BAO_NGAY → hiện st.warning một lần.
    Nếu tất cả đều trong ngưỡng (hoặc chưa có file nào) → không hiện gì
    để tránh làm rối giao diện.
    """
    pgd_data = Path(PGD_DATA_DIR)
    if not pgd_data.exists():
        return

    tat_ca_dv = [DON_VI_CHI_NHANH] + DS_PGD
    co_don_vi_qua_nguong = False

    for loai, nguong in UPLOAD_CANH_BAO_NGAY.items():
        for ten_dv in tat_ca_dv:
            # Import lazy để tránh circular
            from data.pgd import duong_dan_pgd
            path = Path(duong_dan_pgd(ten_dv, loai))
            if not path.exists():
                continue
            so_ngay_cu = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))).days
            if so_ngay_cu > nguong:
                co_don_vi_qua_nguong = True
                break
        if co_don_vi_qua_nguong:
            break

    if co_don_vi_qua_nguong:
        st.warning(
            "⚠️ Một số đơn vị chưa cập nhật số liệu mới nhất. "
            "Dữ liệu đang hiển thị có thể chưa phản ánh tình hình thực tế. "
            "Xem chi tiết tại tab **📤 Upload Dữ liệu**."
        )


# ── Giao diện upload tập trung — Entry Point chính ───────────────────────────

def render_panel_upload(role: str, prefix: str = "uc") -> None:
    """
    Giao diện upload file hệ thống (HSTD gốc, NQ11 gốc, Điện báo).
    Dùng cho tab Quản trị hệ thống.
    Upload theo PGD → dùng tab_upload_khnv / tab_upload_pgd.
    """
    if role not in ["admin", "manager"]:
        st.warning("🔒 Chỉ Phòng KH-NV (manager/admin) mới có quyền upload file hệ thống.")
        st.divider()
        _hien_thi_trang_thai_file_he_thong()
        return

    st.info("ℹ️ Upload dữ liệu qua tab **📤 Upload KH-NV → Import từ Thư mục**")

    # ── Trạng thái file hiện tại ──────────────────────────────────────────────
    st.markdown("**📋 Trạng thái file dữ liệu**")
    _hien_thi_trang_thai_file_he_thong()

    st.divider()

    # ── Xóa cache thủ công ────────────────────────────────────────────────────
    st.markdown("**🗑️ Xóa cache thủ công**")
    st.caption("Dùng khi cần làm mới dữ liệu mà không upload file mới")
    if st.button("🔄 Xóa toàn bộ cache", key=f"{prefix}_xoa_cache"):
        st.cache_data.clear()
        for f in Path(str(CACHE_DIR)).glob("*.parquet"):
            f.unlink(missing_ok=True)
        st.success("✅ Đã xóa cache — tất cả user sẽ thấy dữ liệu mới nhất.")
