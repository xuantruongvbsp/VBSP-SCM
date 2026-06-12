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

from config import (
    COT_NGUON_VON,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from tabs.base_tab import TabContext
from utils import fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel, lazy_tabs


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
    """Vẽ biểu đồ cột ngang tỷ trọng ĐP."""
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
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def _render_sub_pgd(df_full: pd.DataFrame) -> None:
    df_pgd = _bang_theo_nv(df_full, COT_TEN_PGD)
    if df_pgd.empty:
        st.warning("Không có dữ liệu PGD.")
        return
    _ve_bieu_do_ngang(df_pgd, COT_TEN_PGD, "Tỷ trọng vốn Địa phương theo PGD", "nvdp_pgd_chart")
    st.markdown("**Bảng chi tiết theo PGD**")
    hien_thi_dataframe_phan_trang(df_pgd, key="nvdp_pgd_table", height=480)


def _render_sub_xa(df_full: pd.DataFrame) -> None:
    df_xa = _bang_theo_nv(df_full, COT_TEN_XA, extra_cols=[COT_TEN_PGD])
    if df_xa.empty:
        st.warning("Không có dữ liệu Xã.")
        return
    df_top = df_xa.copy()
    df_top["_pct"] = df_top["Tỷ trọng ĐP (%)"].str.replace(",", ".").str.rstrip("%").astype(float)
    df_top = df_top.sort_values("_pct", ascending=False).head(20)
    _ve_bieu_do_ngang(df_top, COT_TEN_XA, "Top 20 Xã — Tỷ trọng vốn Địa phương cao nhất", "nvdp_xa_chart")
    st.markdown("**Bảng chi tiết theo Xã**")
    hien_thi_dataframe_phan_trang(df_xa, key="nvdp_xa_table", height=480)


def _render_sub_ct(df_full: pd.DataFrame) -> None:
    df_ct = _bang_theo_nv(df_full, COT_TEN_CT)
    if df_ct.empty:
        st.warning("Không có dữ liệu Chương trình.")
        return
    _ve_bieu_do_ngang(df_ct, COT_TEN_CT, "Tỷ trọng vốn Địa phương theo Chương trình tín dụng", "nvdp_ct_chart")
    st.markdown("**Bảng chi tiết theo Chương trình**")
    hien_thi_dataframe_phan_trang(df_ct, key="nvdp_ct_table", height=480)


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df_full = kwargs.get("df_full")
    pgd_user = kwargs.get("pgd_user", "")  # PGD mode filter

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

        # Filter theo PGD nếu có pgd_user
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

        df = _phan_nguon_von(df_full)

        tong_du_no = pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").sum()
        dn_tw = pd.to_numeric(df[df["_nv_label"] == "Trung ương"][COT_TONG_DU_NO], errors="coerce").sum()
        dn_dp = pd.to_numeric(df[df["_nv_label"] == "Địa phương"][COT_TONG_DU_NO], errors="coerce").sum()
        tl_dp = dn_dp / tong_du_no * 100 if tong_du_no > 0 else 0.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng dư nợ", fmt_ty(tong_du_no) + " tr.đ")
        c2.metric("Dư nợ Trung ương", fmt_ty(dn_tw) + " tr.đ")
        c3.metric("Dư nợ Địa phương", fmt_ty(dn_dp) + " tr.đ")
        delta_color = "inverse" if tl_dp > 50 else "normal"
        c4.metric(
            "Tỷ trọng vốn ĐP",
            f"{tl_dp:.1f}".replace(".", ",") + "%",
            delta="Vốn ĐP chiếm ưu thế" if tl_dp > 50 else "Vốn TW chiếm ưu thế",
            delta_color=delta_color,
        )

        col_pie, col_info = st.columns([1, 2])
        with col_pie:
            fig_pie = go.Figure(go.Pie(
                labels=["Trung ương", "Địa phương"],
                values=[dn_tw, dn_dp],
                marker_colors=["#42A5F5", "#EF5350"],
                hole=0.4,
                textinfo="label+percent",
            ))
            fig_pie.update_layout(
                title="Cơ cấu nguồn vốn",
                height=320,
                margin=dict(l=10, r=10, t=40, b=10),
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

        st.divider()

        # Tabs: ẩn "Theo PGD" nếu ở PGD mode
        if pgd_user:
            lazy_tabs(
                ["🗺️ Theo Xã", "📌 Theo Chương trình"],
                [
                    lambda: (
                        st.warning("Không tìm thấy cột Tên Xã trong dữ liệu.")
                        if COT_TEN_XA not in df_full.columns
                        else _render_sub_xa(df_full)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
                        if COT_TEN_CT not in df_full.columns
                        else _render_sub_ct(df_full)
                    ),
                ],
                key="nvdp_pgd" if pgd_user else "nvdp",
            )
        else:
            lazy_tabs(
                ["🏢 Theo PGD", "🗺️ Theo Xã", "📌 Theo Chương trình"],
                [
                    lambda: (
                        st.warning("Không tìm thấy cột Tên PGD trong dữ liệu.")
                        if COT_TEN_PGD not in df_full.columns
                        else _render_sub_pgd(df_full)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên Xã trong dữ liệu.")
                        if COT_TEN_XA not in df_full.columns
                        else _render_sub_xa(df_full)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
                        if COT_TEN_CT not in df_full.columns
                        else _render_sub_ct(df_full)
                    ),
                ],
                key="nvdp",
            )

        st.divider()

        st.markdown("**📥 Xuất Excel — Báo cáo Nguồn vốn địa phương**")
        today_str = date.today().strftime("%d/%m/%Y")
        today_file = date.today().strftime("%Y%m%d")

        buf = xuat_excel({
            "Theo PGD": _bang_theo_nv(df_full, COT_TEN_PGD),
            "Theo Xã": _bang_theo_nv(df_full, COT_TEN_XA, extra_cols=[COT_TEN_PGD]),
            "Theo Chương trình": _bang_theo_nv(df_full, COT_TEN_CT),
        })
        st.download_button(
            label=f"⬇️ Tải Excel Nguồn vốn ĐP ({today_str})",
            data=buf,
            file_name=f"NguonVonDiaPhuong_{today_file}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="nvdp_xuat_excel",
        )
