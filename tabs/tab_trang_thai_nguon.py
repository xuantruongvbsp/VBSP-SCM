"""Tab "🔍 Trạng thái hệ thống" — hiển thị tổng quan trạng thái quy trình và audit log gần nhất.

Chỉ dành cho phân hệ Chi nhánh (la_phan_he_cn).
"""
from __future__ import annotations
import os

import streamlit as st
import pandas as pd

import db
from config import CACHE_HSTD, CACHE_NQ11
from auth import la_phan_he_cn, normalize_role
from utils import format_df_vn


def render(tab=None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    username = str(kwargs.get("username", "unknown") or "unknown")
    role = normalize_role(role_raw)

    if not la_phan_he_cn(role):
        st.warning("⛔ Chỉ tài khoản Chi nhánh mới xem được Trạng thái hệ thống.")
        return

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("� Trạng thái hệ thống")

        tab_tq, tab_audit = st.tabs(["� Tổng quan", "� Audit Log"])

        with tab_tq:
            _render_tong_quan()

        with tab_audit:
            _render_audit_log()


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-tab 1: Tổng quan trạng thái quy trình
# ═══════════════════════════════════════════════════════════════════════════════

def _render_tong_quan() -> None:
    ds_quy_trinh = [
        _lay_tt_khtd_cn(),
        _lay_tt_merge_hstd(),
        _lay_tt_merge_nq11(),
        _lay_tt_merge_gqvl(),
        _lay_tt_file_hstd(),
        _lay_tt_file_nq11(),
    ]

    tong = len(ds_quy_trinh)
    dang_ok = sum(1 for _, tt, _, _ in ds_quy_trinh if tt == "✅")
    can_xu_ly = tong - dang_ok

    m1, m2, m3 = st.columns(3)
    m1.metric("📌 Tổng check", tong)
    m2.metric("✅ Đang OK", tong if dang_ok == tong else dang_ok)
    m3.metric("⚠️ Cần xử lý", can_xu_ly)

    st.divider()

    df = pd.DataFrame(
        [
            {"Quy trình": ten, "Trạng thái": tt, "Cập nhật lần cuối": lan_cuoi, "Ghi chú": ghi_chu}
            for ten, tt, lan_cuoi, ghi_chu in ds_quy_trinh
        ]
    )

    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("🔄 Làm mới", key="tttq_refresh"):
        st.rerun()


def _lay_tt_khtd_cn() -> tuple:
    """Kiểm tra KHTD Chi nhánh — key 'khtd_cn'."""
    try:
        val = db.doc_kv("khtd_cn")
        if val is None:
            return "KHTD Chi nhánh", "❌", "—", "Chưa có dữ liệu kế hoạch"
        updated = val.get("updated_at", "—") if isinstance(val, dict) else "—"
        return "KHTD Chi nhánh", "✅", str(updated), "Đã có kế hoạch"
    except Exception as e:
        return "KHTD Chi nhánh", "❌", "—", f"Lỗi đọc: {e}"


def _lay_tt_merge(ten: str, key: str) -> tuple:
    """Kiểm tra trạng thái merge HSTD/NQ11/GQVL."""
    try:
        val = db.doc_kv(key)
        if val is None or not isinstance(val, dict):
            return ten, "❌", "—", "Chưa merge"
        so_pgd = val.get("so_pgd", 0)
        updated = val.get("updated_at", "—")
        return ten, "✅", str(updated), f"Đã merge {so_pgd} PGD"
    except Exception as e:
        return ten, "❌", "—", f"Lỗi đọc: {e}"


def _lay_tt_merge_hstd() -> tuple:
    return _lay_tt_merge("Merge HSTD", "merge_meta_hstd")


def _lay_tt_merge_nq11() -> tuple:
    return _lay_tt_merge("Merge NQ11", "merge_meta_nq11")


def _lay_tt_merge_gqvl() -> tuple:
    return _lay_tt_merge("Merge GQVL", "merge_meta_gqvl")


def _lay_tt_file_hstd() -> tuple:
    """Kiểm tra file hstd.parquet."""
    try:
        if os.path.exists(CACHE_HSTD):
            mtime = os.path.getmtime(CACHE_HSTD)
            from datetime import datetime
            return "File hstd.parquet", "✅", datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"), "Tồn tại"
        return "File hstd.parquet", "❌", "—", "Chưa có file cache"
    except Exception as e:
        return "File hstd.parquet", "❌", "—", f"Lỗi: {e}"


def _lay_tt_file_nq11() -> tuple:
    """Kiểm tra file nq11.parquet."""
    try:
        if os.path.exists(CACHE_NQ11):
            mtime = os.path.getmtime(CACHE_NQ11)
            from datetime import datetime
            return "File nq11.parquet", "✅", datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"), "Tồn tại"
        return "File nq11.parquet", "❌", "—", "Chưa có file cache"
    except Exception as e:
        return "File nq11.parquet", "❌", "—", f"Lỗi: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-tab 2: Audit Log — 20 dòng gần nhất
# ═══════════════════════════════════════════════════════════════════════════════

def _render_audit_log() -> None:
    """Hiển thị 20 dòng audit gần nhất, có bộ lọc action."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT action FROM audit_log ORDER BY action"
            ).fetchall()
        ds_action = ["Tất cả"] + [r["action"] for r in rows]
    except Exception as e:
        st.error(f"Không thể đọc danh sách action: {e}")
        ds_action = ["Tất cả"]

    action_chon = st.selectbox(
        "Lọc theo hành động",
        ds_action,
        key="tttq_audit_action",
    )

    try:
        sql = "SELECT ts, username, action, detail FROM audit_log"
        params = []
        if action_chon and action_chon != "Tất cả":
            sql += " WHERE action = ?"
            params.append(action_chon)
        sql += " ORDER BY ts DESC LIMIT 20"

        with db.get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            st.info("Không có bản ghi audit log nào.")
            return

        df = pd.DataFrame(
            rows,
            columns=["Thời gian", "User", "Hành động", "Chi tiết"],
        )
        df = format_df_vn(df)

        st.caption(f"Hiển thị {len(df)} bản ghi gần nhất")
        st.dataframe(df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Lỗi đọc audit log: {e}")
