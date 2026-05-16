"""Tab "🔍 Trạng thái hệ thống" — hiển thị tổng quan trạng thái quy trình, audit log và trạng thái PGD."""
from __future__ import annotations
import os
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

import db
from config import CACHE_HSTD, CACHE_NQ11
from auth import la_phan_he_cn, normalize_role
from tabs import tab_audit_log as _tab_audit_log


def render(tab=None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    username = str(kwargs.get("username", "unknown") or "unknown")
    role = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🔍 Trạng thái hệ thống")

        la_cn = la_phan_he_cn(role)
        if la_cn:
            if pgd_user:
                tab_tq, tab_audit, tab_pgd = st.tabs(["📊 Tổng quan", "📋 Lịch sử giao dịch", "🏢 Trạng thái PGD"])
            else:
                tab_tq, tab_audit = st.tabs(["📊 Tổng quan", "📋 Lịch sử giao dịch"])
            with tab_tq:
                _render_tong_quan()
            with tab_audit:
                _tab_audit_log.render(None, mode="compact", force_allow=True)
        else:
            tab_pgd = st.tabs(["🏢 Trạng thái PGD"])[0]

        if not la_cn or pgd_user:
            with tab_pgd if la_cn else tab_pgd:
                _render_trang_thai_pgd(pgd_user, username)


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

    st.dataframe(df, width='stretch', hide_index=True)

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
# Sub-tab 2: Lịch sử giao dịch — dùng tab_audit_log (compact mode)
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-tab 3: Trạng thái PGD — kiểm tra file upload của một PGD
# ═══════════════════════════════════════════════════════════════════════════════

def _render_trang_thai_pgd(pgd_user: str | None, username: str) -> None:
    """Hiển thị trạng thái upload file của PGD."""
    pgd_user = pgd_user or username
    st.markdown(f"**Trạng thái upload — {pgd_user}**")

    from data.pgd import duong_dan_pgd

    ds_file = [
        ("HSTD", "hstd"),
        ("NQ11", "nq11"),
        ("GQVL", "gqvl"),
    ]

    rows = []
    for ten, loai in ds_file:
        try:
            path = duong_dan_pgd(pgd_user, loai)
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                lan_cuoi = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                tuoi = datetime.now() - datetime.fromtimestamp(mtime)
                if tuoi < timedelta(days=7):
                    tt = "✅"
                else:
                    tt = "⚠️"
                rows.append({"Loại file": ten, "Trạng thái": tt, "Cập nhật lần cuối": lan_cuoi})
            else:
                rows.append({"Loại file": ten, "Trạng thái": "❌", "Cập nhật lần cuối": "Chưa upload"})
        except Exception as e:
            rows.append({"Loại file": ten, "Trạng thái": "❌", "Cập nhật lần cuối": f"Lỗi: {e}"})

    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    st.markdown("**📋 Hoạt động gần đây**")
    _tab_audit_log.render(None, mode="compact", force_allow=True, username_filter=pgd_user)
