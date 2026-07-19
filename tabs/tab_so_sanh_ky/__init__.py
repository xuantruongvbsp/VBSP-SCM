"""Package So sánh kỳ — tái cấu trúc khoa học từ tab_so_sanh_ky.py + tab_so_sanh_2_ky.py."""
from __future__ import annotations

from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_admin_cn, normalize_role
from logger import get_logger
from tabs.base_tab import TabContext
from tabs.tab_so_sanh_ky.render_moc_nam import render_moc_nam
from tabs.tab_so_sanh_ky.render_2_ky import render_2_ky
from tabs.tab_so_sanh_ky.render_nhieu_ky import render_nhieu_ky
from snapshot_service import (
    danh_sach_ky,
    validate_snapshot,
    xoa_snapshot,
)

import streamlit as st


logger = get_logger(__name__)


_SNAPSHOT_META = {
    "HSTD": ("hstd_snapshot", "ngay_so_lieu"),
    "Ủy thác": ("uy_thac_snapshot", "ngay_so_lieu"),
    "NQ11": ("nq11_snapshot", "ngay_bc"),
    "GQVL": ("gqvl_snapshot", None),
    "CDTOTKVV": ("cdtotkvv_snapshot", None),
}


def _doc_snapshot_inventory() -> list[dict]:
    rows_out: list[dict] = []
    try:
        with db.get_conn() as conn:
            for label, (table, date_col) in _SNAPSHOT_META.items():
                date_expr = f"MAX({date_col})" if date_col else "NULL"
                rows = conn.execute(
                    f"""SELECT ky, COUNT(*) AS so_dong, MAX(created_at) AS ngay_tao,
                               {date_expr} AS ngay_so_lieu
                        FROM {table}
                        GROUP BY ky
                        ORDER BY ky DESC"""
                ).fetchall()
                for row in rows:
                    rows_out.append({
                        "Loại": label,
                        "Kỳ": row["ky"],
                        "Số dòng": row["so_dong"],
                        "Ngày tạo": row["ngay_tao"] or "",
                        "Ngày số liệu": row["ngay_so_lieu"] or "",
                    })
    except Exception as e:
        logger.error("_doc_snapshot_inventory: lỗi đọc danh sách snapshot — %s", e, exc_info=True)
        st.error(f"❌ Lỗi đọc danh sách snapshot: {e}")
    return rows_out


def _render_quan_ly_snapshot(username: str) -> None:
    st.subheader("🧭 Quản lý Snapshot")
    rows = _doc_snapshot_inventory()
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Chưa có snapshot nào.")

    ds_ky = danh_sach_ky()
    if not ds_ky:
        return

    st.divider()
    col_val, col_del = st.columns(2)
    with col_val:
        ky_val = st.selectbox("Kỳ cần kiểm tra", ds_ky, key="ql_snap_validate_ky")
        if st.button("✅ Validate HSTD snapshot", key="ql_snap_validate_btn", use_container_width=True):
            result = validate_snapshot(ky_val)
            if result.get("ok"):
                st.success(f"Snapshot HSTD kỳ {ky_val} hợp lệ.")
            else:
                st.warning("Snapshot cần kiểm tra:")
                for issue in result.get("issues", []):
                    st.write(f"- {issue}")

    with col_del:
        ky_xoa = st.selectbox("Kỳ cần xóa", ds_ky, key="ql_snap_delete_ky")
        confirm = st.checkbox(f"Tôi xác nhận xóa toàn bộ snapshot kỳ {ky_xoa}", key="ql_snap_delete_confirm")
        if st.button("🗑️ Xóa snapshot kỳ này", key="ql_snap_delete_btn", disabled=not confirm, use_container_width=True):
            xoa_snapshot(ky_xoa, username)
            st.success(f"Đã xóa snapshot kỳ {ky_xoa}.")
            st.rerun()


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Entry point: router chọn loại so sánh."""
    ctx = TabContext(tab, **kwargs)
    role = normalize_role(str(kwargs.get("role", "user") or "user"))
    username = kwargs.get("username", "unknown")
    kwargs["role"] = role

    with ctx:
        options = ["📊 So sánh nhiều kỳ", "📅 So sánh mốc năm", "🔄 So sánh 2 kỳ"]
        if la_admin_cn(role):
            options.append("🧭 Quản lý snapshot")
        sub = st.radio(
            "Loại so sánh",
            options,
            horizontal=True,
            key="ss_ky_sub",
            label_visibility="collapsed",
        )
        st.divider()
        if sub == "📅 So sánh mốc năm":
            render_moc_nam(None, **kwargs)
        elif sub == "🔄 So sánh 2 kỳ":
            render_2_ky(None, **kwargs)
        elif sub == "🧭 Quản lý snapshot":
            _render_quan_ly_snapshot(username)
        else:
            render_nhieu_ky(None, **kwargs)
