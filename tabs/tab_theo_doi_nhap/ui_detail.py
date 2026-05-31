"""Chi tiết tiến độ nhập liệu — Drill-down xã/phường, Sort, Inline progress, Export."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import xuat_excel
from logger import get_logger

from .data import emoji_pct, da_nhap

logger = get_logger(__name__)


def _render_inline_progress(pct: float) -> str:
    if pct >= 100:
        bar_color = "#28a745"
    elif pct >= 60:
        bar_color = "#ffc107"
    elif pct > 0:
        bar_color = "#fd7e14"
    else:
        bar_color = "#dc3545"

    return (
        f'<div style="display:flex;align-items:center;gap:4px;">'
        f'<div style="flex:1;height:6px;background:var(--secondary-background-color,#e9ecef);'
        f'border-radius:3px;overflow:hidden;">'
        f'<div style="width:{pct}%;height:100%;background:{bar_color};'
        f'border-radius:3px;"></div>'
        f'</div>'
        f'<span>{emoji_pct(pct)} {pct:.0f}%</span>'
        f'</div>'
    )


def _render_bang_chi_tiet_html(
    df_show: pd.DataFrame, ds_ct: list[dict], ct_chon: str
) -> pd.DataFrame:
    """Tạo bảng chi tiết với inline progress bar qua HTML."""
    ct_names = [ct["ten"] for ct in ds_ct]

    headers = "<th>Đơn vị</th><th>Số xã</th>"
    for ct_name in ct_names:
        if ct_chon in ("Tất cả", ct_name):
            headers += f"<th>{ct_name}</th>"
    headers += "<th>Tổng</th>"

    rows_html = ""
    df_xuat_rows = []
    for _, r in df_show.iterrows():
        don_vi = r["Đơn vị"]
        so_xa = int(r.get("_total", 0))
        xuat_row = {"Đơn vị": don_vi, "Số xã": so_xa}

        row_html = (
            f"<tr>"
            f"<td style='padding:6px 8px;font-weight:500;'>{don_vi}</td>"
            f"<td style='padding:6px 8px;text-align:center;'>{so_xa}</td>"
        )
        for ct_name in ct_names:
            if ct_chon not in ("Tất cả", ct_name):
                continue
            pct = r.get(f"{ct_name}_pct", 0)
            fil = int(r.get(f"{ct_name}_filled", 0))
            tot = int(r.get(f"{ct_name}_total", 0))
            row_html += (
                f"<td style='padding:4px 8px;min-width:140px;'>"
                f"{_render_inline_progress(pct)}"
                f"<small style='color:var(--text-color-secondary,#888);'>({fil}/{tot})</small>"
                f"</td>"
            )
            xuat_row[f"{ct_name}"] = f"{fil}/{tot} ({pct:.0f}%)"

        tong_pct = r.get("Tổng_pct", 0)
        row_html += (
            f"<td style='padding:4px 8px;'>"
            f"{_render_inline_progress(tong_pct)}"
            f"</td>"
        )
        row_html += "</tr>"
        xuat_row["Tổng"] = f"{tong_pct:.0f}%"
        rows_html += row_html
        df_xuat_rows.append(xuat_row)

    html = f"""
    <div style="overflow-x:auto;border-radius:8px;border:1px solid var(--border-color,#ddd);">
      <table style="border-collapse:collapse;width:100%;font-size:12px;">
        <thead>
          <tr style="background:var(--secondary-background-color,#f0f2f6);">
            {headers}
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
    """
    st.html(html)

    df_xuat = pd.DataFrame(df_xuat_rows) if df_xuat_rows else pd.DataFrame()
    return df_xuat


def _render_drilldown_xa(
    pgd_groups: dict[str, list[list]],
    ds_ct: list[dict],
    ten_pgd: str,
) -> None:
    """Hiển thị chi tiết từng xã/phường của một PGD."""
    sub_rows = pgd_groups.get(ten_pgd, [])
    if not sub_rows:
        st.info(f"Không có dữ liệu xã/phường cho {ten_pgd}.")
        return

    total = len(sub_rows)
    ct_names = [ct["ten"] for ct in ds_ct]

    # Tính tiến độ cho PGD này
    pcts = {}
    for ct in ds_ct:
        ci = ct["col"] - 1
        ten = ct["ten"]
        filled = sum(1 for r in sub_rows if len(r) > ci and da_nhap(r[ci]))
        pcts[ten] = (filled, total, (filled / total * 100) if total > 0 else 0)

    overall_filled = sum(
        1 for r in sub_rows
        if all(
            len(r) > ct["col"] - 1 and da_nhap(r[ct["col"] - 1])
            for ct in ds_ct
        )
    )
    overall_pct = (overall_filled / total * 100) if total > 0 else 0

    st.markdown(
        f"**{ten_pgd}** — {overall_filled}/{total} xã hoàn thành "
        f"({overall_pct:.0f}%)"
    )

    # Bảng drill-down HTML
    headers = "<th>Xã/phường</th>"
    for ct_name in ct_names:
        headers += f"<th>{ct_name}</th>"
    headers += "<th>Tổng</th>"

    rows_html = ""
    for row in sub_rows:
        name = str(row[1]).strip() if len(row) > 1 else "?"
        row_html = f"<tr><td style='padding:6px 8px;'>{name}</td>"

        row_filled = 0
        for ct in ds_ct:
            ci = ct["col"] - 1
            filled = len(row) > ci and da_nhap(row[ci])
            if filled:
                row_filled += 1
            bg = "#d4edda" if filled else "#f8d7da"
            icon = "✅" if filled else "❌"
            row_html += (
                f"<td style='padding:4px 6px;text-align:center;"
                f"background:{bg};border-radius:2px;'>{icon}</td>"
            )

        row_total_pct = (row_filled / len(ds_ct) * 100) if ds_ct else 0
        bg_total = "#d4edda" if row_total_pct >= 100 else (
            "#fff3cd" if row_total_pct > 0 else "#f8d7da"
        )
        row_html += (
            f"<td style='padding:4px 6px;text-align:center;"
            f"background:{bg_total};border-radius:2px;font-weight:600;'>"
            f"{row_filled}/{len(ds_ct)}</td>"
        )
        row_html += "</tr>"
        rows_html += row_html

    html = f"""
    <div style="overflow-x:auto;border-radius:6px;border:1px solid var(--border-color,#ddd);
         margin:8px 0;font-size:11px;">
      <table style="border-collapse:collapse;width:100%;">
        <thead>
          <tr style="background:var(--secondary-background-color,#f0f2f6);">
            {headers}
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """
    st.html(html)


def render_chi_tiet(
    df_td: pd.DataFrame,
    ds_ct: list[dict],
    username: str,
    pgd_groups: dict[str, list[list]] | None = None,
) -> None:
    if df_td.empty:
        st.info("Chưa có dữ liệu.")
        return

    # ── Quick filter chips ─────────────────────────────────────────────────
    st.markdown("**Lọc nhanh:**")
    cf1, cf2, cf3, cf4 = st.columns(4)
    with cf1:
        show_all = st.checkbox("Tất cả", value=True, key="ttdn_chip_all")
    with cf2:
        show_full = st.checkbox("🟢 Hoàn thành", value=False, key="ttdn_chip_full")
    with cf3:
        show_partial = st.checkbox("🟡 Đang điền", value=False, key="ttdn_chip_partial")
    with cf4:
        show_empty = st.checkbox("🔴 Chưa điền", value=False, key="ttdn_chip_empty")

    # Chỉ 1 chip được chọn
    if show_full:
        show_all = False
        show_partial = False
        show_empty = False
    if show_partial:
        show_all = False
        show_full = False
        show_empty = False
    if show_empty:
        show_all = False
        show_full = False
        show_partial = False

    # ── Advanced filters ───────────────────────────────────────────────────
    st.divider()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        ct_chon = st.selectbox(
            "Lọc chương trình",
            ["Tất cả"] + [ct["ten"] for ct in ds_ct],
            key="ttdn_ct_filter",
        )
    with col_f2:
        sort_by = st.selectbox(
            "Sắp xếp theo",
            ["Tổng % ↓", "Tổng % ↑", "Tên A→Z", "Số xã ↓"],
            key="ttdn_sort_by",
        )

    # ── Apply filters ──────────────────────────────────────────────────────
    df_show = df_td.copy()
    if not show_all:
        if show_full:
            df_show = df_show[df_show["Tổng_pct"] >= 100]
        elif show_partial:
            df_show = df_show[
                (df_show["Tổng_pct"] > 0) & (df_show["Tổng_pct"] < 100)
            ]
        elif show_empty:
            df_show = df_show[df_show["Tổng_pct"] == 0]

    # Sort
    if sort_by == "Tổng % ↓":
        df_show = df_show.sort_values("Tổng_pct", ascending=False)
    elif sort_by == "Tổng % ↑":
        df_show = df_show.sort_values("Tổng_pct", ascending=True)
    elif sort_by == "Tên A→Z":
        df_show = df_show.sort_values("Đơn vị", ascending=True)
    elif sort_by == "Số xã ↓":
        df_show = df_show.sort_values("_total", ascending=False)

    st.caption(
        f"Hiển thị {len(df_show)} / {len(df_td)} đơn vị"
        + (f" — Sắp xếp: {sort_by}" if sort_by != "Tổng % ↓" else "")
    )

    # ── Render bảng chi tiết ───────────────────────────────────────────────
    df_xuat = _render_bang_chi_tiet_html(df_show, ds_ct, ct_chon)

    # ── Drill-down vào xã/phường ───────────────────────────────────────────
    if pgd_groups:
        st.divider()
        st.markdown("**🔍 Xem chi tiết xã/phường của một PGD:**")
        pgd_list = sorted(df_show["Đơn vị"].tolist())
        pgd_chon = st.selectbox(
            "Chọn PGD",
            pgd_list,
            key="ttdn_drill_pgd",
            label_visibility="collapsed",
        )
        if pgd_chon:
            _render_drilldown_xa(pgd_groups, ds_ct, pgd_chon)

    # ── Export ──────────────────────────────────────────────────────────────
    st.divider()
    col_x1, col_x2 = st.columns([1, 3])
    with col_x1:
        if st.button("📥 Xuất Excel", key="ttdn_btn_excel", type="primary",
                     use_container_width=True):
            excel_bytes = xuat_excel({"Theo dõi nhập liệu": df_xuat})
            st.session_state["ttdn_excel_bytes"] = excel_bytes
            st.session_state["ttdn_show_dl"] = True

    if st.session_state.get("ttdn_show_dl"):
        excel_bytes = st.session_state.get("ttdn_excel_bytes")
        if excel_bytes:
            with col_x2:
                st.download_button(
                    "⬇ Tải Excel",
                    data=excel_bytes,
                    file_name="theo_doi_nhap_lieu.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="ttdn_dl_excel",
                    use_container_width=True,
                )
