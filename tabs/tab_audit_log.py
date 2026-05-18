"""Tab Lịch sử giao dịch — hiển thị audit log (full mode cho Admin, compact cho mọi user)."""
from __future__ import annotations
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import db
from auth import normalize_role
from utils import format_df_vn

ACTION_NHOM = {
    "Upload":    ["upload", "merge", "luu_pgd", "luu_file"],
    "KHTD":      ["luu_khtd", "luu_kh", "giao_khtd", "dieu_chinh"],
    "User":      ["create_user", "delete_user", "reset_password"],
    "Export":    ["export", "xuat_pdf", "xuat_excel", "export_kv"],
    "Khác":      [],   # fallback
}


def _doc_audit(ngay_tu: str, ngay_den: str,
               username_loc: str, action_loc: str,
               username_filter: str | None = None) -> pd.DataFrame:
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
    if username_filter:
        sql += " AND username LIKE ?"
        params.append(f"%{username_filter}%")
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


def render(tab=None, **kwargs) -> None:
    mode = kwargs.pop("mode", "full")
    force_allow = kwargs.pop("force_allow", False)
    username_filter = kwargs.pop("username_filter", None)

    role_raw = str(kwargs.get("role", "user") or "user")
    role = normalize_role(role_raw)

    if not force_allow and role != "admin_cn":
        st.warning("⛔ Chỉ Admin mới có quyền xem Lịch sử giao dịch.")
        return

    _tab_ctx = tab if tab is not None else st.container()
    with _tab_ctx:
        st.subheader("📋 Lịch sử giao dịch")

        if mode == "compact":
            _render_compact(username_filter)
        else:
            _render_full(role, username_filter)


def _render_compact(username_filter: str | None = None) -> None:
    """Chế độ compact — chỉ action filter + 20 dòng, không date/user/metrics/export."""
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
        wheres = []
        if action_chon and action_chon != "Tất cả":
            wheres.append("action = ?")
            params.append(action_chon)
        if username_filter:
            wheres.append("username LIKE ?")
            params.append(f"%{username_filter}%")
        if wheres:
            sql += " WHERE " + " AND ".join(wheres)
        sql += " ORDER BY ts DESC LIMIT 20"

        with db.get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            st.info("Không có bản ghi nào.")
            return

        df = pd.DataFrame(
            rows,
            columns=["Thời gian", "User", "Hành động", "Chi tiết"],
        )
        df = format_df_vn(df)

        st.caption(f"Hiển thị {len(df)} bản ghi gần nhất")
        st.dataframe(df, width='stretch', hide_index=True)

    except Exception as e:
        st.error(f"Lỗi đọc: {e}")


def _render_full(role: str, username_filter: str | None = None) -> None:
    """Chế độ full — đầy đủ bộ lọc, metrics, export (dành cho Admin)."""
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.5, 1.5])
    with c1:
        ngay_tu = st.date_input(
            "Từ ngày",
            value=datetime.today() - timedelta(days=7),
            format="DD/MM/YYYY",
            key="audit_tu",
        ).strftime("%Y-%m-%d")
    with c2:
        ngay_den = st.date_input(
            "Đến ngày",
            value=datetime.today(),
            format="DD/MM/YYYY",
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

    df = _doc_audit(ngay_tu, ngay_den, user_chon, action_chon, username_filter)

    st.caption(f"Tìm thấy **{len(df)}** bản ghi (tối đa 500)")

    if df.empty:
        st.info("Không có bản ghi nào trong khoảng thời gian này.")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Tổng thao tác", len(df))
    m2.metric("Số user", df["User"].nunique())
    m3.metric("Hành động phổ biến nhất",
              df["Hành động"].value_counts().index[0] if not df.empty else "—")

    st.divider()
    st.dataframe(
        df.drop(columns=["ID"]),
        width='stretch',
        hide_index=True,
        column_config={
            "Thời gian": st.column_config.TextColumn(width="medium"),
            "User":      st.column_config.TextColumn(width="small"),
            "Hành động": st.column_config.TextColumn(width="medium"),
            "Chi tiết":  st.column_config.TextColumn(width="large"),
        },
    )

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 Tải xuống CSV",
        data=csv,
        file_name=f"audit_log_{ngay_tu}_{ngay_den}.csv",
        mime="text/csv",
    )
