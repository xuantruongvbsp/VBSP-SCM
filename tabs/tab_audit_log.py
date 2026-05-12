"""Tab Audit Log — Lịch sử thao tác hệ thống (chỉ Admin)."""
from __future__ import annotations
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import db

ACTION_NHOM = {
    "Upload":    ["upload", "merge", "luu_pgd", "luu_file"],
    "KHTD":      ["luu_khtd", "luu_kh", "giao_khtd", "dieu_chinh"],
    "User":      ["create_user", "delete_user", "reset_password"],
    "Export":    ["export", "xuat_pdf", "xuat_excel", "export_kv"],
    "Khác":      [],   # fallback
}


def _doc_audit(ngay_tu: str, ngay_den: str,
               username_loc: str, action_loc: str) -> pd.DataFrame:
    sql = """
        SELECT id, ts, username, action, detail
        FROM audit_log
        WHERE ts >= ? AND ts <= ?
    """
    params = [ngay_tu + "T00:00:00", ngay_den + "T23:59:59"]
    if username_loc and username_loc != "Tất cả":
        sql += " AND username = ?"
        params.append(username_loc)
    if action_loc and action_loc != "Tất cả":
        sql += " AND action LIKE ?"
        params.append(f"%{action_loc}%")
    sql += " ORDER BY ts DESC LIMIT 500"
    with db.get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    if not rows:
        return pd.DataFrame(columns=["id","ts","username","action","detail"])
    return pd.DataFrame(rows, columns=["ID","Thời gian","User","Hành động","Chi tiết"])


def _doc_ds_user() -> list[str]:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT username FROM audit_log ORDER BY username"
        ).fetchall()
    return ["Tất cả"] + [r[0] for r in rows]


from utils import get_tab_context

def render(tab, **kwargs) -> None:
    role = kwargs.get("role", "user")
    if role not in ("admin", "admin_cn"):
        st.warning("⛔ Chỉ Admin mới có quyền xem Audit Log.")
        return

    with get_tab_context(tab):
        st.subheader("📋 Lịch sử thao tác hệ thống")

        # ── Bộ lọc ───────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.5, 1.5])
        with c1:
            ngay_tu = st.date_input(
                "Từ ngày",
                value=datetime.today() - timedelta(days=7),
                key="audit_tu",
            ).strftime("%Y-%m-%d")
        with c2:
            ngay_den = st.date_input(
                "Đến ngày",
                value=datetime.today(),
                key="audit_den",
            ).strftime("%Y-%m-%d")
        with c3:
            ds_user = _doc_ds_user()
            user_chon = st.selectbox("User", ds_user, key="audit_user")
        with c4:
            action_chon = st.text_input(
                "Hành động (chứa...)",
                placeholder="vd: upload, khtd, export",
                key="audit_action",
            )

        # ── Load & hiển thị ───────────────────────────────────────────────
        df = _doc_audit(ngay_tu, ngay_den, user_chon, action_chon)

        st.caption(f"Tìm thấy **{len(df)}** bản ghi (tối đa 500)")

        if df.empty:
            st.info("Không có bản ghi nào trong khoảng thời gian này.")
            return

        # Metrics nhanh
        m1, m2, m3 = st.columns(3)
        m1.metric("Tổng thao tác", len(df))
        m2.metric("Số user", df["User"].nunique())
        m3.metric("Hành động phổ biến nhất",
                  df["Hành động"].value_counts().index[0] if not df.empty else "—")

        st.divider()
        st.dataframe(
            df.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Thời gian": st.column_config.TextColumn(width="medium"),
                "User":      st.column_config.TextColumn(width="small"),
                "Hành động": st.column_config.TextColumn(width="medium"),
                "Chi tiết":  st.column_config.TextColumn(width="large"),
            },
        )

        # Export
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Tải xuống CSV",
            data=csv,
            file_name=f"audit_log_{ngay_tu}_{ngay_den}.csv",
            mime="text/csv",
        )
