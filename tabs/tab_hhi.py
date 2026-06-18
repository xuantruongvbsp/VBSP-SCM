"""
Tab Nguồn vốn địa phương — Phân hệ Chi nhánh.

Báo cáo Tỷ trọng Vốn ủy thác địa phương trên Tổng nguồn vốn:
  Tỷ lệ % = Nguồn vốn ngân sách địa phương (Tỉnh/Huyện) ủy thác / Tổng nguồn vốn tại địa phương

Phân tích theo 3 chiều: PGD, Xã, Chương trình tín dụng.
Dữ liệu từ cột "Nguồn vốn" (1=TW, 2=ĐP) trong HSTD.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from components.delta_card import kpi_row
from config import (
    COT_NGUON_VON,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from snapshot_service import danh_sach_ky, doc_snapshot_nvdp_range
from tabs.base_tab import TabContext
from utils import fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel, lazy_tabs

_COLOR_TW = "#42A5F5"
_COLOR_DP = "#EF5350"
_CHART_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")


def _phan_nguon_von(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm cột _nv_label: 'Trung ương' | 'Địa phương' | 'Khác'."""
    df = df.copy()
    if COT_NGUON_VON not in df.columns:
        df["_nv_label"] = "Không rõ"
        return df

    def _map_nv(v):
        s = str(v).strip().upper()
        if s in ("1", "1.0", "TW", "TRUNG ƯƠNG"):
            return "Trung ương"
        if s in ("2", "2.0", "ĐP", "ĐỊA PHƯƠNG"):
            return "Địa phương"
        try:
            n = int(float(s))
            if n == 1:
                return "Trung ương"
            if n == 2:
                return "Địa phương"
        except (ValueError, TypeError):
            pass
        return "Khác"

    df["_nv_label"] = df[COT_NGUON_VON].map(_map_nv)
    return df


def _bang_theo_nv(
    df: pd.DataFrame,
    nhom_col: str,
    extra_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Bảng tổng hợp theo nhóm: TW dư nợ | ĐP dư nợ | Tỷ trọng ĐP%."""
    if nhom_col not in df.columns or COT_TONG_DU_NO not in df.columns:
        return pd.DataFrame()

    df = _phan_nguon_von(df)

    pivot = df.pivot_table(
        index=[nhom_col] + (extra_cols if extra_cols else []),
        columns="_nv_label",
        values=COT_TONG_DU_NO,
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    for nv_col in ["Trung ương", "Địa phương"]:
        if nv_col not in pivot.columns:
            pivot[nv_col] = 0.0

    pivot["Tổng dư nợ"] = pivot["Trung ương"] + pivot["Địa phương"]
    if "Khác" in pivot.columns:
        pivot["Tổng dư nợ"] += pivot["Khác"]
    pivot["Tỷ trọng ĐP (%)"] = pivot.apply(
        lambda r: r["Địa phương"] / r["Tổng dư nợ"] * 100
        if r["Tổng dư nợ"] > 0 else 0.0,
        axis=1,
    )

    result = pivot.sort_values("Tổng dư nợ", ascending=False).reset_index(drop=True)

    result["TW (triệu đồng)"] = result["Trung ương"].apply(fmt_ty)
    result["ĐP (triệu đồng)"] = result["Địa phương"].apply(fmt_ty)
    result["Tổng (triệu đồng)"] = result["Tổng dư nợ"].apply(fmt_ty)
    result["Tỷ trọng ĐP (%)"] = result["Tỷ trọng ĐP (%)"].apply(
        lambda x: f"{x:.1f}".replace(".", ",") + "%"
    )

    display_cols = [nhom_col]
    if extra_cols:
        display_cols += [c for c in extra_cols if c in result.columns]
    display_cols += ["TW (triệu đồng)", "ĐP (triệu đồng)", "Tổng (triệu đồng)", "Tỷ trọng ĐP (%)"]
    return result[[c for c in display_cols if c in result.columns]]


def _ve_bieu_do_ngang(df_table: pd.DataFrame, label_col: str, tieu_de: str, key: str) -> None:
    """Vẽ biểu đồ cột ngang tỷ trọng ĐP — dark-mode compatible."""
    df_chart = df_table.copy()
    pct_col = "Tỷ trọng ĐP (%)"
    df_chart["_pct"] = df_chart[pct_col].str.replace(",", ".").str.rstrip("%").astype(float)
    df_chart = df_chart.sort_values("_pct", ascending=True)

    colors = ["#E53935" if v > 50 else ("#FFA000" if v > 30 else "#43A047") for v in df_chart["_pct"]]

    fig = go.Figure(go.Bar(
        y=df_chart[label_col],
        x=df_chart["_pct"],
        orientation="h",
        marker_color=colors,
        text=df_chart[pct_col],
        textposition="outside",
    ))
    fig.update_layout(
        title=tieu_de,
        xaxis_title="Tỷ trọng ĐP (%)",
        yaxis=dict(autorange="reversed"),
        height=max(400, len(df_chart) * 30 + 100),
        margin=dict(l=20, r=80, t=50, b=30),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def _render_sub_pgd(df: pd.DataFrame) -> None:
    df_pgd = _bang_theo_nv(df, COT_TEN_PGD)
    if df_pgd.empty:
        st.warning("Không có dữ liệu PGD.")
        return
    _ve_bieu_do_ngang(df_pgd, COT_TEN_PGD, "Tỷ trọng vốn Địa phương theo PGD", "nvdp_pgd_chart")
    st.markdown("**Bảng chi tiết theo PGD**")
    hien_thi_dataframe_phan_trang(df_pgd, key="nvdp_pgd_table", height=480)


def _render_sub_xa(df: pd.DataFrame, kp: str = "") -> None:
    df_xa = _bang_theo_nv(df, COT_TEN_XA, extra_cols=[COT_TEN_PGD])
    if df_xa.empty:
        st.warning("Không có dữ liệu Xã.")
        return
    df_top = df_xa.copy()
    df_top["_pct"] = df_top["Tỷ trọng ĐP (%)"].str.replace(",", ".").str.rstrip("%").astype(float)
    df_top = df_top.sort_values("_pct", ascending=False).head(20)
    _ve_bieu_do_ngang(df_top, COT_TEN_XA, "Top 20 Xã — Tỷ trọng vốn Địa phương cao nhất", f"{kp}nvdp_xa_chart")
    st.markdown("**Bảng chi tiết theo Xã**")
    hien_thi_dataframe_phan_trang(df_xa, key=f"{kp}nvdp_xa_table", height=480)


def _render_sub_ct(df: pd.DataFrame, kp: str = "") -> None:
    df_ct = _bang_theo_nv(df, COT_TEN_CT)
    if df_ct.empty:
        st.warning("Không có dữ liệu Chương trình.")
        return
    _ve_bieu_do_ngang(df_ct, COT_TEN_CT, "Tỷ trọng vốn Địa phương theo Chương trình tín dụng", f"{kp}nvdp_ct_chart")
    st.markdown("**Bảng chi tiết theo Chương trình**")
    hien_thi_dataframe_phan_trang(df_ct, key=f"{kp}nvdp_ct_table", height=480)


def _render_trend(ky_list: list[str]) -> None:
    """Biểu đồ xu hướng TW vs ĐP qua các kỳ snapshot."""
    if len(ky_list) < 2:
        return
    df_trend = doc_snapshot_nvdp_range(ky_list[-1], ky_list[0])
    if df_trend.empty:
        return

    df_tw = df_trend[df_trend["nguon_von"] == "1"].set_index("ky")["tong_du_no"]
    df_dp = df_trend[df_trend["nguon_von"] == "2"].set_index("ky")["tong_du_no"]
    ky_vals = sorted(df_trend["ky"].unique())

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ky_vals,
        y=[df_tw.get(k, 0) / 1e9 for k in ky_vals],
        name="Trung ương",
        marker_color=_COLOR_TW,
    ))
    fig.add_trace(go.Bar(
        x=ky_vals,
        y=[df_dp.get(k, 0) / 1e9 for k in ky_vals],
        name="Địa phương",
        marker_color=_COLOR_DP,
    ))
    fig.update_layout(
        barmode="stack",
        title="Xu hướng dư nợ TW vs ĐP theo kỳ",
        yaxis_title="Tỷ đồng",
        height=350,
        margin=dict(l=20, r=20, t=50, b=30),
        legend=dict(orientation="h", y=1.08),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, key="nvdp_trend_chart")


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df_full = kwargs.get("df_full")
    pgd_user = kwargs.get("pgd_user", "")

    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.subheader("🏦 Nguồn vốn địa phương")
        if pgd_user:
            st.caption(
                f"Báo cáo Tỷ trọng Vốn ủy thác địa phương tại **{pgd_user}** — "
                "phân tích theo Xã và Chương trình tín dụng."
            )
        else:
            st.caption(
                "Báo cáo Tỷ trọng Vốn ủy thác địa phương trên Tổng nguồn vốn "
                "— phân tích theo PGD, Xã và Chương trình tín dụng."
            )

        if df_full is None or df_full.empty:
            st.warning("⚠️ Chưa có dữ liệu. Vui lòng upload và merge HSTD.")
            return

        # Filter theo PGD nếu PGD mode
        if pgd_user and COT_TEN_PGD in df_full.columns:
            df_full = df_full[df_full[COT_TEN_PGD] == pgd_user].copy()
            if df_full.empty:
                st.warning(f"⚠️ Không có dữ liệu cho PGD **{pgd_user}**.")
                return

        if COT_NGUON_VON not in df_full.columns:
            st.warning(
                "⚠️ Dữ liệu HSTD không có cột 'Nguồn vốn'. "
                "Vui lòng kiểm tra lại file HSTD gốc."
            )
            return

        # CN mode: filter PGD drill-down
        selected_pgd = None
        if not pgd_user and COT_TEN_PGD in df_full.columns:
            pgds = sorted(df_full[COT_TEN_PGD].dropna().unique().tolist())
            sel = st.selectbox(
                "🔍 Lọc theo PGD (tùy chọn)",
                ["Tất cả"] + pgds,
                key="nvdp_filter_pgd",
            )
            if sel != "Tất cả":
                selected_pgd = sel
                df_display = df_full[df_full[COT_TEN_PGD] == sel].copy()
            else:
                df_display = df_full
        else:
            df_display = df_full

        # ── KPI metrics ───────────────────────────────────────────────────────
        df_labeled = _phan_nguon_von(df_display)
        tong_du_no = pd.to_numeric(df_labeled[COT_TONG_DU_NO], errors="coerce").sum()
        dn_tw = pd.to_numeric(
            df_labeled[df_labeled["_nv_label"] == "Trung ương"][COT_TONG_DU_NO], errors="coerce"
        ).sum()
        dn_dp = pd.to_numeric(
            df_labeled[df_labeled["_nv_label"] == "Địa phương"][COT_TONG_DU_NO], errors="coerce"
        ).sum()
        tl_dp = dn_dp / tong_du_no * 100 if tong_du_no > 0 else 0.0

        # Delta từ snapshot — chỉ khi xem toàn CN (không filter PGD)
        delta_tong = delta_tw = delta_dp = delta_tl = None
        prev_label = "so với kỳ trước"
        ky_list: list[str] = []

        if not pgd_user and selected_pgd is None:
            ky_list = danh_sach_ky()
            if ky_list:
                prev_ky = ky_list[0]
                ky_parts = prev_ky.split("-")
                prev_label = f"so với T{ky_parts[1]}/{ky_parts[0]}"
                df_prev = doc_snapshot_nvdp_range(prev_ky, prev_ky)
                if not df_prev.empty:
                    p_tw = float(df_prev[df_prev["nguon_von"] == "1"]["tong_du_no"].sum())
                    p_dp = float(df_prev[df_prev["nguon_von"] == "2"]["tong_du_no"].sum())
                    p_tong = p_tw + p_dp
                    p_tl = p_dp / p_tong * 100 if p_tong > 0 else 0.0
                    delta_tong = (tong_du_no - p_tong) / p_tong * 100 if p_tong > 0 else None
                    delta_tw = (dn_tw - p_tw) / p_tw * 100 if p_tw > 0 else None
                    delta_dp = (dn_dp - p_dp) / p_dp * 100 if p_dp > 0 else None
                    delta_tl = tl_dp - p_tl

        kpi_row(
            [
                {
                    "label": "Tổng dư nợ",
                    "value": fmt_ty(tong_du_no),
                    "suffix": "tr.đ",
                    "delta": delta_tong,
                    "delta_label": prev_label,
                    "icon": "💰",
                    "precision": 1,
                },
                {
                    "label": "Dư nợ Trung ương",
                    "value": fmt_ty(dn_tw),
                    "suffix": "tr.đ",
                    "delta": delta_tw,
                    "delta_label": prev_label,
                    "icon": "🏛️",
                    "precision": 1,
                },
                {
                    "label": "Dư nợ Địa phương",
                    "value": fmt_ty(dn_dp),
                    "suffix": "tr.đ",
                    "delta": delta_dp,
                    "delta_label": prev_label,
                    "icon": "🏘️",
                    "precision": 1,
                },
                {
                    "label": "Tỷ trọng vốn ĐP",
                    "value": f"{tl_dp:.1f}".replace(".", ",") + "%",
                    "delta": delta_tl,
                    "delta_label": prev_label,
                    "delta_color": "inverse" if tl_dp > 50 else "normal",
                    "icon": "📊",
                    "precision": 1,
                },
            ],
            num_columns=4,
        )

        # ── Pie + công thức ───────────────────────────────────────────────────
        col_pie, col_info = st.columns([1, 2])
        with col_pie:
            fig_pie = go.Figure(go.Pie(
                labels=["Trung ương", "Địa phương"],
                values=[dn_tw, dn_dp],
                marker_colors=[_COLOR_TW, _COLOR_DP],
                hole=0.4,
                textinfo="label+percent",
            ))
            fig_pie.update_layout(
                title="Cơ cấu nguồn vốn",
                height=320,
                margin=dict(l=10, r=10, t=40, b=10),
                **_CHART_LAYOUT,
            )
            st.plotly_chart(fig_pie, use_container_width=True, key="nvdp_pie")

        with col_info:
            st.markdown("##### 📐 Cách đo lường")
            st.latex(
                r"\text{Tỷ lệ \%} = "
                r"\frac{\text{Nguồn vốn ngân sách địa phương (Tỉnh/Huyện) ủy thác}}"
                r"{\text{Tổng nguồn vốn tại địa phương}}"
            )
            st.info(
                "Nguồn vốn được xác định từ cột **Nguồn vốn** trong HSTD: "
                "**1 = Trung ương**, **2 = Địa phương**."
            )

        # ── Trend chart (chỉ khi xem toàn CN, có ít nhất 2 kỳ) ──────────────
        if len(ky_list) >= 2:
            st.divider()
            st.markdown("**📈 Xu hướng theo kỳ snapshot**")
            _render_trend(ky_list)

        st.divider()

        # ── Sub-tabs phân tích ────────────────────────────────────────────────
        # Khi filter PGD hoặc PGD mode: ẩn tab "Theo PGD"
        is_pgd_view = bool(pgd_user or selected_pgd)
        kp = f"pgd_" if is_pgd_view else ""

        if is_pgd_view:
            lazy_tabs(
                ["🗺️ Theo Xã", "📌 Theo Chương trình"],
                [
                    lambda: (
                        st.warning("Không tìm thấy cột Tên Xã trong dữ liệu.")
                        if COT_TEN_XA not in df_display.columns
                        else _render_sub_xa(df_display, kp)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
                        if COT_TEN_CT not in df_display.columns
                        else _render_sub_ct(df_display, kp)
                    ),
                ],
                key="nvdp_sub_pgd",
            )
        else:
            lazy_tabs(
                ["🏢 Theo PGD", "🗺️ Theo Xã", "📌 Theo Chương trình"],
                [
                    lambda: (
                        st.warning("Không tìm thấy cột Tên PGD trong dữ liệu.")
                        if COT_TEN_PGD not in df_display.columns
                        else _render_sub_pgd(df_display)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên Xã trong dữ liệu.")
                        if COT_TEN_XA not in df_display.columns
                        else _render_sub_xa(df_display, kp)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
                        if COT_TEN_CT not in df_display.columns
                        else _render_sub_ct(df_display, kp)
                    ),
                ],
                key="nvdp_sub_cn",
            )

        # ── Xuất Excel ────────────────────────────────────────────────────────
        st.divider()
        st.markdown("**📥 Xuất Excel — Báo cáo Nguồn vốn địa phương**")
        today_str = date.today().strftime("%d/%m/%Y")
        today_file = date.today().strftime("%Y%m%d")

        sheets: dict[str, pd.DataFrame] = {
            "Theo Chương trình": _bang_theo_nv(df_display, COT_TEN_CT),
            "Theo Xã": _bang_theo_nv(df_display, COT_TEN_XA, extra_cols=[COT_TEN_PGD]),
        }
        if not is_pgd_view:
            sheets["Theo PGD"] = _bang_theo_nv(df_display, COT_TEN_PGD)

        buf = xuat_excel(sheets)
        st.download_button(
            label=f"⬇️ Tải Excel Nguồn vốn ĐP ({today_str})",
            data=buf,
            file_name=f"NguonVonDiaPhuong_{today_file}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="nvdp_xuat_excel",
        )
