"""Hiển thị bảng Điều chỉnh tăng trưởng — tự động quét từ GSheet."""
from __future__ import annotations

import streamlit as st

from components.delta_card import kpi_row
from utils import xuat_excel
from logger import get_logger

from .data import DCTT_SHEET_ID, doc_dieu_chinh_tu_dong

logger = get_logger(__name__)


def _fmt_dctt(val: float) -> str:
    if val == 0:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:,.0f}".replace(",", ".")


def _bg_dctt(val: float) -> str:
    if val > 0:
        return "background:#d4edda;color:#155724;"
    if val < 0:
        return "background:#f8d7da;color:#721c24;"
    return "color:var(--text-color-secondary,#888);"


def render_dieu_chinh_tang_truong(username: str = "system") -> None:
    col_r, _ = st.columns([1, 8])
    with col_r:
        if st.button("🔄", key="dctt_refresh", help="Làm mới",
                     use_container_width=True):
            doc_dieu_chinh_tu_dong.clear()
            st.rerun()

    try:
        with st.spinner("Đang quét dữ liệu..."):
            df, skipped = doc_dieu_chinh_tu_dong(DCTT_SHEET_ID)
    except Exception as e:
        logger.error("render_dieu_chinh_tang_truong: %s", e, exc_info=True)
        st.error(f"❌ Lỗi đọc sheet: {e}")
        return

    if skipped:
        st.caption(
            "Bỏ qua (không có cột DCTT): " + " · ".join(skipped)
        )

    if df.empty:
        st.warning("⚠️ Không tìm thấy cột 'Điều chỉnh tăng trưởng' trong bất kỳ tab nào.")
        return

    tab_names = [c for c in df.columns if c not in ("Đơn vị", "Tổng")]

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    tong = float(df["Tổng"].sum())
    n_tang = int((df["Tổng"] > 0).sum())
    n_giam = int((df["Tổng"] < 0).sum())
    n_khong = int((df["Tổng"] == 0).sum())

    kpi_row([
        {"label": "Tổng DCTT toàn CN", "value": _fmt_dctt(tong) + " triệu",
         "icon": "📊", "precision": 0,
         "help": "Tổng điều chỉnh tăng trưởng toàn Chi nhánh (triệu đồng)"},
        {"label": "PGD tăng", "value": n_tang,
         "suffix": f"/{len(df)}", "icon": "📈", "precision": 0},
        {"label": "PGD giảm", "value": n_giam,
         "suffix": f"/{len(df)}", "icon": "📉", "precision": 0},
        {"label": "PGD không đổi", "value": n_khong,
         "suffix": f"/{len(df)}", "icon": "➖", "precision": 0},
    ], num_columns=4)

    st.divider()
    st.caption(
        f"Đơn vị: triệu đồng · {len(tab_names)} tab · "
        f"{len(df)} đơn vị · Cache 5 phút"
    )

    # ── Bảng HTML ─────────────────────────────────────────────────────────────
    th = "<th style='padding:6px 8px;font-weight:600;text-align:left;white-space:nowrap;'>Đơn vị</th>"
    for tn in tab_names:
        th += (f"<th style='padding:6px 8px;font-weight:600;text-align:right;"
               f"white-space:nowrap;'>{tn}</th>")
    th += "<th style='padding:6px 8px;font-weight:600;text-align:right;'>Tổng</th>"

    body = ""
    df_sorted = df.sort_values("Tổng", ascending=False)
    for _, r in df_sorted.iterrows():
        row_html = (f"<tr><td style='padding:6px 8px;font-weight:500;"
                    f"white-space:nowrap;'>{r['Đơn vị']}</td>")
        for tn in tab_names:
            v = float(r.get(tn, 0) or 0)
            row_html += (f"<td style='padding:4px 8px;text-align:right;"
                         f"font-size:12px;border-radius:3px;{_bg_dctt(v)}'>"
                         f"{_fmt_dctt(v)}</td>")
        t = float(r.get("Tổng", 0) or 0)
        row_html += (f"<td style='padding:4px 8px;text-align:right;font-weight:700;"
                     f"border-radius:3px;{_bg_dctt(t)}'>{_fmt_dctt(t)}</td></tr>")
        body += row_html

    # Hàng tổng cộng
    foot = ("<tr style='background:var(--secondary-background-color,#f0f2f6);"
            "font-weight:700;border-top:2px solid var(--border-color,#ddd);'>"
            "<td style='padding:6px 8px;'>Tổng cộng</td>")
    for tn in tab_names:
        t = float(df[tn].sum())
        foot += (f"<td style='padding:4px 8px;text-align:right;{_bg_dctt(t)}'>"
                 f"{_fmt_dctt(t)}</td>")
    t_all = float(df["Tổng"].sum())
    foot += (f"<td style='padding:4px 8px;text-align:right;{_bg_dctt(t_all)}'>"
             f"{_fmt_dctt(t_all)}</td></tr>")

    st.html(f"""
    <div style="overflow-x:auto;border-radius:8px;
                border:1px solid var(--border-color,#ddd);margin-bottom:12px;">
      <table style="border-collapse:collapse;width:100%;font-size:12px;">
        <thead><tr style="background:var(--secondary-background-color,#f0f2f6);">{th}</tr></thead>
        <tbody>{body}{foot}</tbody>
      </table>
    </div>
    """)

    # ── Export ─────────────────────────────────────────────────────────────────
    st.divider()
    col_x, _ = st.columns([1, 3])
    with col_x:
        if st.button("📥 Xuất Excel", key="ttdn_dctt_excel", type="primary",
                     use_container_width=True):
            excel_bytes = xuat_excel({"Điều chỉnh tăng trưởng": df_sorted})
            st.download_button(
                "⬇ Tải Excel", data=excel_bytes,
                file_name="dieu_chinh_tang_truong.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="ttdn_dctt_dl", use_container_width=True,
            )
