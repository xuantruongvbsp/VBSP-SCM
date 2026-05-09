"""
alert_center.py
Tổng hợp và hiển thị cảnh báo tự động trong sidebar.
Mỗi lần gọi render_alert_sidebar() sẽ đọc dữ liệu thực
từ kv_store + parquet, không cache để luôn mới nhất.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st
import db
from config import CACHE_GQVL

NGUONG_NGAY_UPLOAD_CU = 3   # cảnh báo nếu file chưa merge quá 3 ngày


def _kiem_tra_upload_tre() -> list[str]:
    """Trả về danh sách loại file chưa được merge trong NGUONG_NGAY_UPLOAD_CU ngày."""
    canh_bao = []
    now = datetime.now()
    for loai in ["hstd", "nq11", "gqvl"]:
        meta = db.doc_kv(f"merge_meta_{loai}")
        if not meta:
            canh_bao.append(f"Chưa có dữ liệu **{loai.upper()}**")
            continue
        try:
            thoi_gian = datetime.fromisoformat(meta["thoi_gian"])
            delta = (now - thoi_gian).days
            if delta >= NGUONG_NGAY_UPLOAD_CU:
                canh_bao.append(
                    f"**{loai.upper()}** chưa cập nhật ({delta} ngày trước)"
                )
        except Exception:
            pass
    return canh_bao


def _kiem_tra_khong_hoat_dong(df_full, pgd_filter: str | None = None) -> list[str]:
    """
    Trả về danh sách cảnh báo hộ 3 tháng không hoạt động.
    Dùng hàm tong_hop_khong_hd() từ hstd.py.
    """
    if df_full is None or df_full.empty:
        return []
    try:
        from hstd import tong_hop_khong_hd
        from config import COT_TEN_PGD
        df_loc = df_full
        if pgd_filter and COT_TEN_PGD in df_full.columns:
            df_loc = df_full[df_full[COT_TEN_PGD] == pgd_filter]
        tong_hop = tong_hop_khong_hd(df_loc, nhom_theo=COT_TEN_PGD)
        if tong_hop.empty:
            return []
        tong_mon = int(tong_hop["Món_3m_KHĐ"].sum())
        if tong_mon > 0:
            return [f"**{tong_mon} món vay** ≥ 3 tháng không hoạt động"]
        return []
    except Exception:
        return []


def render_alert_sidebar(
    df_full=None,
    role: str = "user",
    pgd_user: str | None = None,
) -> None:
    """
    Hiển thị cảnh báo trong sidebar.
    Gọi sau render_status_compact() trong app.py.

    Chỉ hiển thị nếu có ít nhất 1 cảnh báo.
    """
    canh_bao: list[str] = []

    # Cảnh báo upload trễ — chỉ admin/manager mới thấy
    from auth import is_cn_role, is_pgd_role
    if is_cn_role(role) or role in ["admin", "manager"]:
        canh_bao += _kiem_tra_upload_tre()

    # Cảnh báo 3 tháng không hoạt động
    pgd_filter = pgd_user if is_pgd_role(role) else None
    canh_bao += _kiem_tra_khong_hoat_dong(df_full, pgd_filter)

    if not canh_bao:
        return

    st.divider()
    st.markdown("🔔 **Cảnh báo**")
    for msg in canh_bao:
        st.warning(msg, icon="⚠️")
