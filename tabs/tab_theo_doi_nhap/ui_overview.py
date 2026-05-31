"""Tổng quan tiến độ nhập liệu — Heatmap, Progress bars, KPI mở rộng, So sánh kỳ."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.delta_card import kpi_row
from logger import get_logger

from .constants import EMOJI_PCT, LOAI_LABEL
from .data import emoji_pct, doc_snapshot_truoc, luu_snapshot

logger = get_logger(__name__)


def _heatmap_color(pct: float) -> str:
    if pct >= 100:
        return "var(--green-100, #d4edda)"
    if pct >= 80:
        return "var(--green-50, #a8e6cf)"
    if pct >= 60:
        return "var(--yellow-50, #ffd3b6)"
    if pct >= 40:
        return "var(--orange-50, #ffaaa5)"
    if pct > 0:
        return "var(--red-50, #ff8c94)"
    return "var(--red-100, #f8d7da)"


def _heatmap_text_color(pct: float) -> str:
    if pct >= 100:
        return "#155724"
    if pct >= 40:
        return "#333"
    return "#721c24"


def _render_heatmap(df_td: pd.DataFrame, ds_ct: list[dict], ten_sheet: str) -> None:
    """Ma trận tiến độ dạng HTML Heatmap với màu gradient."""
    if df_td.empty:
        return

    df_sorted = df_td.sort_values("Tổng_pct", ascending=False)

    ct_names = [ct["ten"] for ct in ds_ct]
    headers_html = "<th style='padding:6px 8px;text-align:center;font-weight:600;white-space:nowrap;'>Đơn vị</th>"
    headers_html += "<th style='padding:6px 8px;text-align:center;font-weight:600;'>Số xã</th>"
    for ct_name in ct_names:
        headers_html += f"<th style='padding:6px 8px;text-align:center;font-weight:600;'>{ct_name}</th>"
    headers_html += "<th style='padding:6px 8px;text-align:center;font-weight:600;'>Tổng</th>"

    rows_html = ""
    for _, r in df_sorted.iterrows():
        don_vi = r["Đơn vị"]
        so_xa = int(r.get("_total", 0))
        tong_pct = r.get("Tổng_pct", 0)

        row_html = f"<tr>"
        row_html += f"<td style='padding:6px 8px;font-weight:500;white-space:nowrap;text-align:left;'>{don_vi}</td>"
        row_html += f"<td style='padding:6px 8px;text-align:center;'>{so_xa}</td>"

        for ct_name in ct_names:
            pct = r.get(f"{ct_name}_pct", 0)
            fil = int(r.get(f"{ct_name}_filled", 0))
            tot = int(r.get(f"{ct_name}_total", 0))
            bg = _heatmap_color(pct)
            tc = _heatmap_text_color(pct)
            display = f"{fil}/{tot}<br><small>({pct:.0f}%)</small>"
            row_html += (
                f"<td style='padding:4px 6px;text-align:center;"
                f"background:{bg};color:{tc};border-radius:4px;"
                f"font-size:12px;white-space:nowrap;'>{display}</td>"
            )

        bg_total = _heatmap_color(tong_pct)
        tc_total = _heatmap_text_color(tong_pct)
        row_html += (
            f"<td style='padding:4px 6px;text-align:center;"
            f"background:{bg_total};color:{tc_total};border-radius:4px;"
            f"font-weight:700;font-size:13px;'>{tong_pct:.0f}%</td>"
        )
        row_html += "</tr>"
        rows_html += row_html

    html = f"""
    <div style="overflow-x:auto;border-radius:8px;border:1px solid var(--border-color,#ddd);margin-bottom:12px;">
      <table style="border-collapse:collapse;width:100%;font-size:12px;">
        <thead>
          <tr style="background:var(--secondary-background-color,#f0f2f6);">
            {headers_html}
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
    """
    st.html(html)


def _render_progress_bars(df_td: pd.DataFrame) -> None:
    """Thanh tiến trình ngang cho từng PGD."""
    if df_td.empty:
        return

    df_sorted = df_td.sort_values("Tổng_pct", ascending=False)
    html_parts = [
        '<div style="margin:8px 0;font-size:12px;">'
    ]
    for _, r in df_sorted.iterrows():
        don_vi = r["Đơn vị"]
        pct = r.get("Tổng_pct", 0)
        em = emoji_pct(pct)

        if pct >= 100:
            bar_color = "#28a745"
        elif pct >= 60:
            bar_color = "#ffc107"
        elif pct > 0:
            bar_color = "#fd7e14"
        else:
            bar_color = "#dc3545"

        html_parts.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;">'
            f'<span style="width:160px;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" '
            f'title="{don_vi}">{em} {don_vi}</span>'
            f'<div style="flex:1;height:18px;background:var(--secondary-background-color,#e9ecef);'
            f'border-radius:9px;overflow:hidden;">'
            f'<div style="width:{pct}%;height:100%;background:{bar_color};'
            f'border-radius:9px;transition:width 0.5s ease;"></div>'
            f'</div>'
            f'<span style="width:42px;text-align:left;font-weight:600;">{pct:.0f}%</span>'
            f'</div>'
        )
    html_parts.append('</div>')
    st.html("".join(html_parts))


def _render_so_sanh_ky(
    df_td: pd.DataFrame,
    sheet_id: str,
    sheet_tab: str,
    username: str,
) -> None:
    """So sánh tiến độ với kỳ snapshot trước đó."""
    if df_td.empty:
        return

    prev = doc_snapshot_truoc(sheet_id, sheet_tab)
    if prev is None:
        return

    prev_pct = prev.get("tong_pct", 0)
    prev_full = prev.get("so_pgd_full", 0)
    prev_empty = prev.get("so_pgd_empty", 0)
    prev_total = prev.get("total_pgd", 0)
    prev_ngay = prev.get("ngay", "?")

    curr_pct = round(float(df_td["Tổng_pct"].mean()), 1)
    curr_full = int((df_td["Tổng_pct"] >= 100).sum())
    curr_empty = int((df_td["Tổng_pct"] == 0).sum())

    delta_pct = curr_pct - prev_pct
    delta_full = curr_full - prev_full
    delta_empty = curr_empty - prev_empty

    st.divider()
    st.markdown(f"**📊 So sánh với lần trước ({prev_ngay})**")

    cols = st.columns(4)
    with cols[0]:
        arrow = "📈" if delta_pct >= 0 else "📉"
        st.metric(
            f"{arrow} % Trung bình",
            f"{curr_pct:.1f}%",
            delta=f"{delta_pct:+.1f}%",
            delta_color="normal" if delta_pct >= 0 else "inverse",
        )
    with cols[1]:
        st.metric(
            "🟢 Hoàn thành",
            f"{curr_full}/{len(df_td)}",
            delta=f"{delta_full:+d}" if delta_full != 0 else None,
        )
    with cols[2]:
        st.metric(
            "🔴 Chưa điền",
            f"{curr_empty}/{len(df_td)}",
            delta=f"{delta_empty:+d}" if delta_empty != 0 else None,
            delta_color="inverse",
        )
    with cols[3]:
        ngay_cu = prev.get("ngay", "?")
        st.caption(f"So với ngày {ngay_cu}")

    # Chi tiết PGD thay đổi
    if "chi_tiet" in prev:
        prev_map = {r["Đơn vị"]: r for r in prev["chi_tiet"]}
        tang = []
        giam = []
        for _, r in df_td.iterrows():
            don_vi = r["Đơn vị"]
            curr_p = r.get("Tổng_pct", 0)
            prev_p = prev_map.get(don_vi, {}).get("Tổng_pct", 0) if don_vi in prev_map else curr_p
            diff = curr_p - prev_p
            if diff > 0.5:
                tang.append((don_vi, diff))
            elif diff < -0.5:
                giam.append((don_vi, diff))

        if tang or giam:
            msg_parts = []
            if tang:
                tang.sort(key=lambda x: -x[1])
                msg_parts.append(
                    "🟢 **Tăng:** " + " · ".join(
                        f"{d} (+{v:.0f}%)" for d, v in tang[:5]
                    )
                )
            if giam:
                giam.sort(key=lambda x: x[1])
                msg_parts.append(
                    "🔴 **Giảm:** " + " · ".join(
                        f"{d} ({v:.0f}%)" for d, v in giam[:5]
                    )
                )
            st.caption(" · ".join(msg_parts))


def render_tong_quan(
    df_td: pd.DataFrame,
    ds_ct: list[dict],
    ten_sheet: str,
    pgd_groups: dict[str, list[list]] | None = None,
    name_idx: int = 1,
    sheet_id: str = "",
    sheet_tab: str = "",
    username: str = "system",
) -> None:
    if df_td.empty:
        st.info("Chưa có dữ liệu. Kiểm tra lại Sheet ID hoặc cấu hình cột.")
        return

    total_pgd = len(df_td)
    pgd_full = int((df_td["Tổng_pct"] >= 100).sum())
    pgd_empty = int((df_td["Tổng_pct"] == 0).sum())
    pgd_partial = total_pgd - pgd_full - pgd_empty
    pct_avg = round(float(df_td["Tổng_pct"].mean()), 1)
    tong_xa = int(df_td["_total"].sum()) if "_total" in df_td.columns else 0

    # Lưu snapshot nếu có sheet_id
    if sheet_id and sheet_tab:
        try:
            luu_snapshot(sheet_id, sheet_tab, df_td, username)
        except Exception:
            pass

    # ── KPI Row mở rộng (6 cards) ─────────────────────────────────────────
    kpi_row([
        {"label": "Hoàn thành", "value": pgd_full, "suffix": f"/{total_pgd} PGD",
         "icon": "🟢", "precision": 0,
         "help": "Đơn vị đã điền đầy đủ tất cả chỉ tiêu"},
        {"label": "Đang điền", "value": pgd_partial, "suffix": f"/{total_pgd} PGD",
         "icon": "🟡", "precision": 0,
         "help": "Đã có dữ liệu nhưng chưa đầy đủ"},
        {"label": "Chưa điền", "value": pgd_empty, "suffix": f"/{total_pgd} PGD",
         "icon": "🔴", "precision": 0,
         "help": "Chưa có bất kỳ dữ liệu nào"},
        {"label": "% TB toàn CN", "value": pct_avg, "suffix": "%",
         "icon": "📊", "precision": 1,
         "help": "Tỷ lệ hoàn thành trung bình toàn chi nhánh"},
        {"label": "Tổng xã/phường", "value": tong_xa, "suffix": "",
         "icon": "🏘️", "precision": 0,
         "help": "Tổng số xã/phường đang theo dõi"},
        {"label": "Chỉ tiêu", "value": len(ds_ct), "suffix": "",
         "icon": "📋", "precision": 0,
         "help": "Số lượng chỉ tiêu đang theo dõi"},
    ], num_columns=6)

    st.divider()

    # ── So sánh với kỳ trước ──────────────────────────────────────────────
    if sheet_id and sheet_tab:
        _render_so_sanh_ky(df_td, sheet_id, sheet_tab, username)

    # ── Progress Bars ─────────────────────────────────────────────────────
    st.divider()
    st.markdown(f"**📊 Tiến độ từng đơn vị — {ten_sheet}**")
    _render_progress_bars(df_td)

    # ── Kiểm tra sai lệch PGD_XA_MAP ──────────────────────────────────────
    try:
        from config import PGD_XA_MAP
        sai_lech = []
        for _, r in df_td.iterrows():
            don_vi = r["Đơn vị"]
            so_trong_sheet = int(r.get("_total", 0))
            so_trong_config = len(PGD_XA_MAP.get(don_vi, []))
            if so_trong_config > 0 and so_trong_sheet != so_trong_config:
                ten_trong_sheet = []
                if pgd_groups and don_vi in pgd_groups:
                    ten_trong_sheet = [
                        str(row[name_idx]).strip() for row in pgd_groups[don_vi]
                        if len(row) > name_idx and str(row[name_idx]).strip()
                    ]
                msg = (
                    f"**{don_vi}**: Sheet={so_trong_sheet}, Config={so_trong_config} "
                    f"({'thừa' if so_trong_sheet > so_trong_config else 'thiếu'} "
                    f"{abs(so_trong_sheet - so_trong_config)} xã)"
                )
                if ten_trong_sheet:
                    msg += f"\n  → Sheet có: {', '.join(ten_trong_sheet)}"
                sai_lech.append(msg)
        if sai_lech:
            st.warning(
                "⚠️ **Sai lệch số xã/phường so với cấu hình:**\n"
                + "\n".join(f"- {s}" for s in sai_lech)
            )
    except Exception as e_load:
        logger.warning(
            "render_tong_quan: không so sánh được PGD_XA_MAP — %s",
            e_load, exc_info=True,
        )

    # ── Heatmap ────────────────────────────────────────────────────────────
    st.divider()
    st.markdown(f"**🗺️ Ma trận tiến độ — {ten_sheet}**")
    st.caption("🟢 100% · 🟡 đang điền · 🔴 chưa điền  — Di chuột để xem chi tiết")
    _render_heatmap(df_td, ds_ct, ten_sheet)

    # ── Danh sách chưa điền ────────────────────────────────────────────────
    df_chua = df_td[df_td["Tổng_pct"] == 0]
    if not df_chua.empty:
        st.warning(
            f"⚠️ **{len(df_chua)} đơn vị chưa điền:** "
            + " · ".join(df_chua["Đơn vị"].tolist())
        )
