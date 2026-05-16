"""
Tab Tập trung rủi ro & Chỉ số HHI — Phân hệ Chi nhánh.

Đo mức độ tập trung danh mục cho vay bằng Herfindahl-Hirschman Index (HHI)
theo 3 chiều: Chương trình, Xã, PGD.

HHI = Σ(Si²) × 10.000   (Si = tỷ trọng dư nợ nhóm i / tổng dư nợ)
  < 1.500  → Phân tán tốt
  1.500–2.500 → Tập trung vừa
  > 2.500  → Tập trung cao — cần kiểm soát
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import normalize_role
from config import (
    COT_DU_NO_QH,
    COT_MA_KH,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from data import canh_bao_migration_cached, danh_dau_khong_hd_cached
from utils import fmt_so, fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tinh_hhi(
    df: pd.DataFrame,
    nhom_col: str,
    du_no_col: str = COT_TONG_DU_NO,
) -> float:
    """HHI = Σ(Si²) × 10.000 với Si = dư nợ nhóm / tổng dư nợ."""
    if nhom_col not in df.columns or du_no_col not in df.columns:
        return 0.0
    group = df.groupby(nhom_col)[du_no_col].sum()
    total = group.sum()
    if total == 0:
        return 0.0
    shares = group / total
    return round(float((shares ** 2).sum() * 10_000), 1)


def _nhan_xet_hhi(hhi: float) -> tuple[str, str]:
    """Trả về (nhãn ngưỡng, delta_color cho st.metric)."""
    if hhi < 1_500:
        return "🟢 Phân tán tốt", "normal"
    if hhi < 2_500:
        return "🟡 Tập trung vừa", "off"
    return "🔴 Tập trung cao", "inverse"


def _bang_tap_trung(
    df: pd.DataFrame,
    nhom_col: str,
    du_no_col: str = COT_TONG_DU_NO,
    nqh_col: str = COT_DU_NO_QH,
    extra_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Bảng tổng hợp: nhóm | Dư nợ | Tỷ trọng% | Dư nợ NQH | NQH%.

    Trả về DataFrame đã format (chuỗi) — dùng cho cả hiển thị lẫn xuất Excel.
    """
    if nhom_col not in df.columns or du_no_col not in df.columns:
        return pd.DataFrame()

    has_nqh = nqh_col in df.columns
    agg: dict[str, tuple] = {"_du_no": (du_no_col, "sum")}
    if has_nqh:
        agg["_nqh"] = (nqh_col, "sum")
    if extra_cols:
        for c in extra_cols:
            if c in df.columns:
                agg[c] = (c, "first")

    result = df.groupby(nhom_col, dropna=False).agg(**agg).reset_index()
    total = result["_du_no"].sum()

    result["Dư nợ"] = result["_du_no"].apply(fmt_ty)
    result["Tỷ trọng%"] = result["_du_no"].apply(
        lambda x: f"{x / total * 100:.1f}".replace(".", ",") + "%" if total > 0 else "0,0%"
    )
    if has_nqh:
        result["Dư nợ NQH"] = result["_nqh"].apply(fmt_ty)
        result["NQH%"] = result.apply(
            lambda r: f"{r['_nqh'] / r['_du_no'] * 100:.2f}".replace(".", ",") + "%"
            if r["_du_no"] > 0 else "0,00%",
            axis=1,
        )

    # Sắp xếp giảm dần theo dư nợ rồi bỏ cột tạm
    result = result.sort_values("_du_no", ascending=False).reset_index(drop=True)
    drop_cols = ["_du_no"] + (["_nqh"] if has_nqh else [])
    result = result.drop(columns=drop_cols)
    return result


# ── Sub-tab renderers (module-level để tránh nested function) ──────────────────

def _render_sub_ct(df_full: pd.DataFrame) -> None:
    """Sub-tab: biểu đồ cột ngang top 15 + bảng theo Chương trình."""
    # Tổng hợp dư nợ theo chương trình
    agg_ct = (
        df_full.groupby(COT_TEN_CT, dropna=False)[COT_TONG_DU_NO]
        .sum()
        .reset_index(name="tong_du_no")
    )
    total_ct = agg_ct["tong_du_no"].sum()
    agg_ct["ty_trong"] = (
        agg_ct["tong_du_no"] / total_ct * 100 if total_ct > 0 else 0.0
    )
    agg_ct = agg_ct.sort_values("tong_du_no", ascending=False)
    top15 = agg_ct.head(15).copy()

    top15["color"] = top15["ty_trong"].apply(
        lambda x: "#E53935" if x >= 25 else ("#FFA000" if x >= 10 else "#43A047")
    )

    fig = go.Figure(
        go.Bar(
            y=top15[COT_TEN_CT].astype(str),
            x=top15["ty_trong"],
            orientation="h",
            marker_color=top15["color"],
            text=top15["ty_trong"].apply(
                lambda x: f"{x:.1f}%".replace(".", ",")
            ),
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Top 15 Chương trình theo tỷ trọng dư nợ",
        xaxis_title="Tỷ trọng (%)",
        yaxis=dict(autorange="reversed"),
        height=max(400, len(top15) * 34 + 100),
        margin=dict(l=20, r=90, t=50, b=30),
    )
    st.plotly_chart(fig, use_container_width=True, key="hhi_ct_chart")

    st.markdown("**Bảng tổng hợp Chương trình**")
    df_ct = _bang_tap_trung(df_full, COT_TEN_CT)
    if not df_ct.empty:
        hien_thi_dataframe_phan_trang(df_ct, key="hhi_ct_table", height=350)


def _render_sub_xa(df_full: pd.DataFrame) -> None:
    """Sub-tab: treemap theo Xã × PGD + bảng chi tiết."""
    agg_xa = (
        df_full.groupby([COT_TEN_PGD, COT_TEN_XA], dropna=False)[COT_TONG_DU_NO]
        .sum()
        .reset_index(name="tong_du_no")
    )

    if COT_DU_NO_QH in df_full.columns:
        nqh_xa = (
            df_full.groupby([COT_TEN_PGD, COT_TEN_XA], dropna=False)[COT_DU_NO_QH]
            .sum()
            .reset_index(name="tong_nqh")
        )
        agg_xa = agg_xa.merge(nqh_xa, on=[COT_TEN_PGD, COT_TEN_XA], how="left")
        agg_xa["tl_nqh_pct"] = agg_xa.apply(
            lambda r: r["tong_nqh"] / r["tong_du_no"] * 100
            if r["tong_du_no"] > 0 else 0.0,
            axis=1,
        )
    else:
        agg_xa["tl_nqh_pct"] = 0.0

    # Bỏ dòng dư nợ = 0 (treemap không hỗ trợ value=0)
    agg_xa = agg_xa[agg_xa["tong_du_no"] > 0].copy()
    agg_xa["tong_du_no_ty"] = agg_xa["tong_du_no"] / 1e9

    if not agg_xa.empty:
        midpoint = float(agg_xa["tl_nqh_pct"].median())
        fig_xa = px.treemap(
            agg_xa,
            path=[px.Constant("Chi nhánh"), COT_TEN_PGD, COT_TEN_XA],
            values="tong_du_no_ty",
            color="tl_nqh_pct",
            color_continuous_scale=["#43A047", "#FFA000", "#E53935"],
            color_continuous_midpoint=midpoint,
            title="Dư nợ theo Xã — màu nền = tỷ lệ NQH%",
            labels={
                "tong_du_no_ty": "Dư nợ (tỷ đồng)",
                "tl_nqh_pct": "NQH%",
            },
        )
        fig_xa.update_traces(
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Dư nợ: %{value:.3f} tỷ<br>"
                "NQH: %{color:.2f}%"
                "<extra></extra>"
            )
        )
        fig_xa.update_layout(height=520)
        st.plotly_chart(fig_xa, use_container_width=True, key="hhi_xa_treemap")

    st.markdown("**Bảng tổng hợp Xã**")
    df_xa = _bang_tap_trung(df_full, COT_TEN_XA, extra_cols=[COT_TEN_PGD])
    if not df_xa.empty:
        # Đưa COT_TEN_PGD lên ngay sau COT_TEN_XA
        col_first = [COT_TEN_XA] + (
            [COT_TEN_PGD] if COT_TEN_PGD in df_xa.columns else []
        )
        col_rest = [c for c in df_xa.columns if c not in col_first]
        hien_thi_dataframe_phan_trang(
            df_xa[col_first + col_rest],
            key="hhi_xa_table",
            height=350,
        )


def _render_sub_pgd(df_full: pd.DataFrame) -> None:
    """Sub-tab: bảng PGD tổng hợp với 3m KHĐ và Migration."""
    df_pgd = _bang_tap_trung(df_full, COT_TEN_PGD)
    if df_pgd.empty:
        st.warning("Không có dữ liệu PGD.")
        return

    # Số món vay
    if COT_MA_KH in df_full.columns:
        so_mon = (
            df_full.groupby(COT_TEN_PGD)[COT_MA_KH]
            .count()
            .reset_index(name="Số món")
        )
    else:
        so_mon = (
            df_full.groupby(COT_TEN_PGD)
            .size()
            .reset_index(name="Số món")
        )
    df_pgd = df_pgd.merge(so_mon, on=COT_TEN_PGD, how="left")
    df_pgd["Số món"] = df_pgd["Số món"].fillna(0).apply(lambda x: fmt_so(int(x)))

    # 3m KHĐ + Migration
    try:
        df_kh = danh_dau_khong_hd_cached(df_full)

        if "is_3m_inactive" in df_kh.columns:
            khd_pgd = (
                df_kh[df_kh["is_3m_inactive"]]
                .groupby(COT_TEN_PGD)
                .size()
                .reset_index(name="3m KHĐ")
            )
            df_pgd = df_pgd.merge(khd_pgd, on=COT_TEN_PGD, how="left")
            df_pgd["3m KHĐ"] = df_pgd["3m KHĐ"].fillna(0).astype(int)

        df_amber = canh_bao_migration_cached(df_kh)
        if not df_amber.empty and COT_TEN_PGD in df_amber.columns:
            mig_pgd = (
                df_amber.groupby(COT_TEN_PGD)
                .size()
                .reset_index(name="Migration ⚠️")
            )
            df_pgd = df_pgd.merge(mig_pgd, on=COT_TEN_PGD, how="left")
            df_pgd["Migration ⚠️"] = df_pgd["Migration ⚠️"].fillna(0).astype(int)
    except Exception:
        pass

    cols_order = [COT_TEN_PGD, "Số món", "Dư nợ", "Tỷ trọng%", "Dư nợ NQH", "NQH%"]
    if "3m KHĐ" in df_pgd.columns:
        cols_order.append("3m KHĐ")
    if "Migration ⚠️" in df_pgd.columns:
        cols_order.append("Migration ⚠️")

    st.markdown("**Bảng tổng hợp PGD**")
    hien_thi_dataframe_phan_trang(
        df_pgd[[c for c in cols_order if c in df_pgd.columns]],
        key="hhi_pgd_table",
        height=480,
    )


# ── Entry point ────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Render tab Tập trung rủi ro & HHI.

    Nhận df_full (toàn CN) từ kwargs — không dùng df (PGD-filtered).
    """
    df_full = kwargs.get("df_full")
    normalize_role(str(kwargs.get("role", "user") or "user"))  # validate only

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📊 Tập trung rủi ro & Chỉ số HHI")
        st.caption(
            "Đo mức độ tập trung danh mục cho vay theo Chương trình, Xã và PGD "
            "bằng chỉ số Herfindahl-Hirschman Index (HHI)."
        )

        if df_full is None or df_full.empty:
            st.warning("⚠️ Chưa có dữ liệu toàn Chi nhánh. Vui lòng upload và merge HSTD.")
            return

        # ── SECTION 1: 3 KPI cards ─────────────────────────────────────────
        hhi_ct  = _tinh_hhi(df_full, COT_TEN_CT)
        hhi_xa  = _tinh_hhi(df_full, COT_TEN_XA)
        hhi_pgd = _tinh_hhi(df_full, COT_TEN_PGD)

        c1, c2, c3 = st.columns(3)
        for col, hhi, label in [
            (c1, hhi_ct,  "HHI theo Chương trình"),
            (c2, hhi_xa,  "HHI theo Xã"),
            (c3, hhi_pgd, "HHI theo PGD"),
        ]:
            nhan, delta_color = _nhan_xet_hhi(hhi)
            col.metric(
                label=label,
                value=f"{int(hhi):,}".replace(",", ".") + " điểm",
                delta=nhan,
                delta_color=delta_color,
            )

        # ── SECTION 2: Thang giải thích ───────────────────────────────────
        st.info(
            "**Thang HHI:**   "
            "🟢 **< 1.500** — Phân tán tốt   |   "
            "🟡 **1.500 – 2.500** — Tập trung vừa   |   "
            "🔴 **> 2.500** — Tập trung cao, cần kiểm soát"
        )

        st.divider()

        # ── SECTION 3: Sub-tabs chi tiết ──────────────────────────────────
        sub1, sub2, sub3 = st.tabs([
            "📊 Theo Chương trình",
            "🗺️ Theo Xã",
            "🏢 Theo PGD",
        ])

        with sub1:
            if COT_TEN_CT not in df_full.columns:
                st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
            else:
                _render_sub_ct(df_full)

        with sub2:
            missing = [c for c in [COT_TEN_XA, COT_TEN_PGD] if c not in df_full.columns]
            if missing:
                st.warning(f"Thiếu cột: {', '.join(missing)}")
            else:
                _render_sub_xa(df_full)

        with sub3:
            if COT_TEN_PGD not in df_full.columns:
                st.warning("Không tìm thấy cột Tên PGD trong dữ liệu.")
            else:
                _render_sub_pgd(df_full)

        st.divider()

        # ── SECTION 4: Xuất Excel ──────────────────────────────────────────
        st.markdown("**📥 Xuất Excel — 3 chiều phân tích**")
        today_str = date.today().strftime("%d/%m/%Y")
        today_file = date.today().strftime("%Y%m%d")

        buf = xuat_excel({
            "Chương trình": _bang_tap_trung(df_full, COT_TEN_CT),
            "Xã": _bang_tap_trung(df_full, COT_TEN_XA, extra_cols=[COT_TEN_PGD]),
            "PGD": _bang_tap_trung(df_full, COT_TEN_PGD),
        })
        st.download_button(
            label=f"⬇️ Tải Excel HHI ({today_str})",
            data=buf,
            file_name=f"HHI_TapTrungRuiRo_{today_file}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="hhi_xuat_excel",
        )
