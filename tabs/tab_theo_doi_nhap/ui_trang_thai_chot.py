"""Hiển thị trạng thái chốt kế hoạch tín dụng từ Google Sheet."""
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import streamlit as st

from components.delta_card import kpi_row
from logger import get_logger
from utils import xuat_excel

from .data import doc_trang_thai_chot

logger = get_logger(__name__)


def _is_done(val: object) -> bool:
    s = str(val or "").strip().upper()
    return s.startswith("ĐÃ") or s == "HOÀN THÀNH"


def _is_complete(val: object) -> bool:
    s = str(val or "").strip().upper()
    return "HOÀN THÀNH" in s and "CHƯA" not in s


def _status_cols(df: pd.DataFrame) -> list[str]:
    skip = ("stt", "đơn vị", "pgd", "thời gian", "kết quả", "ghi chú")
    cols = []
    for col in df.columns:
        c = str(col).strip().lower()
        if c and not any(k in c for k in skip):
            cols.append(col)
    return cols


def _parse_deadline(text: str) -> datetime | None:
    m = re.search(
        r"(\d{1,2}/\d{1,2}/\d{4})(?:\s+(\d{1,2}:\d{2}(?::\d{2})?))?",
        text or "",
    )
    if not m:
        return None
    raw = m.group(1) + (" " + m.group(2) if m.group(2) else " 23:59:59")
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _render_deadline(deadline_text: str, pct: float) -> None:
    deadline = _parse_deadline(deadline_text)
    if deadline is None:
        if deadline_text:
            st.info(deadline_text)
        return

    now = datetime.now()
    remain = deadline - now
    dl_fmt = deadline.strftime("%d/%m/%Y %H:%M")
    if remain.total_seconds() < 0:
        days = abs(remain.days)
        st.error(f"🔴 Đã quá hạn {days} ngày · hạn chót {dl_fmt} · hoàn thành {pct:.1f}%")
        return

    hours = int(remain.total_seconds() // 3600)
    if hours <= 24:
        st.warning(f"🟡 Còn {hours} giờ · hạn chót {dl_fmt} · hoàn thành {pct:.1f}%")
    else:
        st.info(f"📅 Hạn chót {dl_fmt} · còn {remain.days} ngày · hoàn thành {pct:.1f}%")


def _fmt_status(val: object) -> str:
    s = str(val or "").strip().upper()
    if not s:
        return "—"
    if _is_done(s):
        return "Đã chốt"
    if "CHƯA" in s:
        return "Chưa chốt"
    return str(val).strip()


def _build_export_df(df: pd.DataFrame, status_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in status_cols + ["Kết quả chung"]:
        if col in out.columns:
            out[col] = out[col].map(_fmt_status)
    return out


def render_trang_thai_chot(username: str = "system") -> None:
    col_r, _ = st.columns([1, 8])
    with col_r:
        if st.button("🔄", key="ttc_refresh", help="Làm mới", use_container_width=True):
            doc_trang_thai_chot.clear()
            st.rerun()

    try:
        with st.spinner("Đang đọc trạng thái chốt..."):
            meta, df = doc_trang_thai_chot()
    except Exception as e:
        logger.error("render_trang_thai_chot: %s", e, exc_info=True)
        st.error(f"❌ Lỗi đọc sheet: {e}")
        return

    if df.empty:
        st.warning("⚠️ Chưa đọc được dữ liệu trạng thái chốt.")
        return

    status_cols = _status_cols(df)
    done_mask = df.get(
        "Kết quả chung",
        pd.Series([""] * len(df), index=df.index, dtype=str),
    ).map(_is_complete)
    total = len(df)
    done = int(done_mask.sum()) if len(done_mask) else 0
    pending = total - done
    pct = round(done / total * 100, 1) if total else 0.0

    title = meta.get("title") or "Trạng thái chốt kế hoạch tín dụng"
    st.markdown(f"**{title}**")
    _render_deadline(meta.get("deadline_text", ""), pct)

    kpi_row([
        {"label": "Hoàn thành", "value": done, "suffix": f"/{total} đơn vị", "icon": "🟢"},
        {"label": "Chưa hoàn thành", "value": pending, "suffix": f"/{total} đơn vị", "icon": "🔴"},
        {"label": "Tỷ lệ hoàn thành", "value": pct, "suffix": "%", "icon": "📊", "precision": 1},
        {"label": "Hạng mục chốt", "value": len(status_cols), "suffix": "", "icon": "📋"},
    ], num_columns=4)

    if status_cols:
        st.divider()
        cols = st.columns(len(status_cols))
        for idx, col in enumerate(status_cols):
            da_chot = int(df[col].map(_is_done).sum())
            with cols[idx]:
                st.metric(col, f"{da_chot}/{total}", delta=f"{total - da_chot} chưa chốt")

    st.divider()
    c1, c2 = st.columns([2, 3])
    with c1:
        loc = st.radio(
            "Lọc trạng thái",
            ["Tất cả", "Hoàn thành", "Chưa hoàn thành"],
            horizontal=True,
            key="ttc_filter",
            label_visibility="collapsed",
        )
    with c2:
        if status_cols:
            thieu = st.multiselect(
                "Thiếu hạng mục",
                status_cols,
                key="ttc_missing_cols",
                placeholder="Chọn hạng mục cần lọc",
            )
        else:
            thieu = []

    df_show = df.copy()
    if loc == "Hoàn thành":
        df_show = df_show[done_mask]
    elif loc == "Chưa hoàn thành":
        df_show = df_show[~done_mask]

    for col in thieu:
        df_show = df_show[~df_show[col].map(_is_done)]

    df_view = _build_export_df(df_show, status_cols)
    st.caption(f"Hiển thị {len(df_view)} / {total} đơn vị · Cache 5 phút")
    st.dataframe(df_view, use_container_width=True, hide_index=True)

    if pending:
        chua = df.loc[~done_mask, "Đơn vị/PGD"].dropna().astype(str).tolist()
        st.warning("Chưa hoàn thành: " + " · ".join(chua))

    st.divider()
    col_x, col_dl = st.columns([1, 3])
    with col_x:
        if st.button("📥 Xuất Excel", key="ttc_excel", type="primary", use_container_width=True):
            st.session_state["ttc_excel_bytes"] = xuat_excel({
                "Trang thai chot": _build_export_df(df, status_cols),
                "Dang loc": df_view,
            })
    with col_dl:
        excel_bytes = st.session_state.get("ttc_excel_bytes")
        if excel_bytes:
            st.download_button(
                "⬇ Tải Excel trạng thái chốt",
                data=excel_bytes,
                file_name="trang_thai_chot_khtd.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="ttc_dl_excel",
                use_container_width=True,
            )
