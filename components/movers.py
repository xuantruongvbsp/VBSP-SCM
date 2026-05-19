"""Movers Analysis - Phân tích biến động theo nhóm.

So sánh các chỉ tiêu giữa kỳ trước và kỳ hiện tại theo từng
dimension (PGD, Xã, Chương trình, Tổ, ĐVUT), hiển thị Top N
cải thiện và Top N giảm sút.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import pandas as pd
import streamlit as st

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TEN_CT,
    COT_TEN_TO,
    COT_DVUT,
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
)
from utils import fmt_tien, fmt_ty, fmt_so

DIMENSION_OPTIONS: list[dict[str, Any]] = [
    {"key": "pgd",      "label": "PGD",           "col": COT_TEN_PGD},
    {"key": "xa",       "label": "Xã",            "col": COT_TEN_XA},
    {"key": "chuongtrinh", "label": "Chương trình","col": COT_TEN_CT},
    {"key": "to",       "label": "Tổ TK&VV",      "col": COT_TEN_TO},
    {"key": "dvut",     "label": "ĐVUT",          "col": COT_DVUT},
]

METRIC_OPTIONS: list[dict[str, Any]] = [
    {"key": "tong_du_no", "label": "Tổng dư nợ",  "unit": "tien"},  # noqa: COT
    {"key": "ty_le_nqh",  "label": "Tỷ lệ NQH",   "unit": "ty_le"},
    {"key": "roll_rate",  "label": "Roll rate",    "unit": "ty_le"},
]


def _pick_dim_col(dim_key: str) -> str | None:
    for d in DIMENSION_OPTIONS:
        if d["key"] == dim_key:
            return d["col"]
    return None


def _compute_movers(
    df_curr: pd.DataFrame,
    df_prev: pd.DataFrame | None,
    dim_col: str,
    metric: str,
) -> list[dict[str, Any]]:
    if df_curr is None or df_curr.empty:
        return []

    if dim_col not in df_curr.columns:
        return []

    grp_curr = df_curr.groupby(dim_col, dropna=False).agg(
        tong_du_no=(COT_TONG_DU_NO, "sum"),
        du_no_qh=(COT_DU_NO_QH, "sum"),
        du_no_th=(COT_DU_NO_TH, "sum"),
    ).reset_index()

    if df_prev is not None and not df_prev.empty and dim_col in df_prev.columns:
        grp_prev = df_prev.groupby(dim_col, dropna=False).agg(
            tong_du_no=(COT_TONG_DU_NO, "sum"),
            du_no_qh=(COT_DU_NO_QH, "sum"),
            du_no_th=(COT_DU_NO_TH, "sum"),
        ).reset_index()
    else:
        grp_prev = None

    merged = grp_curr.copy()
    merged.columns = [dim_col, "curr_tong_du_no", "curr_qh", "curr_th"]

    if grp_prev is not None:
        prev_renamed = grp_prev.rename(columns={
            "tong_du_no": "prev_tong_du_no",
            "du_no_qh": "prev_qh",
            "du_no_th": "prev_th",
        })
        merged = merged.merge(prev_renamed, on=dim_col, how="left")
    else:
        merged["prev_tong_du_no"] = 0.0
        merged["prev_qh"] = 0.0
        merged["prev_th"] = 0.0

    merged = merged.fillna(0.0)

    results: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        prev_value = 0.0
        curr_value = 0.0

        if metric == "tong_du_no":
            prev_value = row["prev_tong_du_no"]
            curr_value = row["curr_tong_du_no"]
        elif metric == "ty_le_nqh":
            prev_value = (row["prev_qh"] / row["prev_tong_du_no"]) if row["prev_tong_du_no"] > 0 else 0.0
            curr_value = (row["curr_qh"] / row["curr_tong_du_no"]) if row["curr_tong_du_no"] > 0 else 0.0
        elif metric == "roll_rate":
            prev_value = 0.0
            curr_value = (row["curr_qh"] / row["prev_th"]) if row["prev_th"] > 0 else 0.0

        delta = curr_value - prev_value
        pct_delta = (delta / prev_value) if prev_value != 0 else None

        results.append({
            "key": row[dim_col],
            "prev_value": prev_value,
            "curr_value": curr_value,
            "delta": delta,
            "pct_delta": pct_delta,
            "prev_tong_du_no": row["prev_tong_du_no"],
            "curr_tong_du_no": row["curr_tong_du_no"],
        })

    return results


def _format_value(value: float, unit: str) -> str:
    if unit == "tien":
        return fmt_tien(value)
    elif unit == "ty_le":
        return fmt_ty(value)
    return fmt_so(value)


def _render_mover_item(
    item: dict[str, Any],
    rank: int,
    unit: str,
    is_improved: bool,
    key: str,
):
    delta = item["delta"]
    pct = item["pct_delta"]
    abs_delta = abs(delta)

    arrow = "▲" if is_improved else "▼"
    color_class = "improved" if is_improved else "declined"
    bg = "#0D2818" if is_improved else "#2D0D14"

    delta_str = _format_value(abs_delta, unit)
    if pct is not None:
        delta_str += f" ({pct:+.1%})"

    metric_str = _format_value(item["curr_value"], unit)
    prev_str = _format_value(item["prev_value"], unit)

    st.markdown(f"""
    <div style="padding:8px 12px;margin:4px 0;border-radius:8px;background:{bg};
                border-left:4px solid {'#66BB6A' if is_improved else '#EF5350'};">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <strong>#{rank}</strong>
            <strong>{item["key"]}</strong>
            <span style="font-size:1.1em;font-weight:600;">{metric_str}</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.85em;color:#94A3B8;margin-top:4px;">
            <span>Kỳ trước: {prev_str}</span>
            <span style="color:{'#81C784' if is_improved else '#EF9A9A'};">
                {arrow} {delta_str}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_kpi_box(label: str, value: float, unit: str, color: str):
    val_str = _format_value(value, unit)
    st.markdown(f"""
    <div style="text-align:center;padding:10px;background:#1E2130;
                border-radius:10px;border:1px solid #2A2D3E;">
        <div style="font-size:0.8em;color:#94A3B8;">{label}</div>
        <div style="font-size:1.3em;font-weight:700;color:{color};">{val_str}</div>
    </div>
    """, unsafe_allow_html=True)


def movers_analysis(
    df_curr: pd.DataFrame,
    df_prev: pd.DataFrame | None = None,
    top_n: int = 10,
    key_prefix: str = "mover",
    on_select_dimension: Callable | None = None,
    on_select_metric: Callable | None = None,
    show_title: bool = True,
):
    """Phân tích biến động - Top cải thiện và giảm sút.

    Args:
        df_curr: DataFrame kỳ hiện tại (có COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_TH)
        df_prev: DataFrame kỳ trước (None nếu không có so sánh)
        top_n: Số lượng hiển thị mỗi bên
        key_prefix: Prefix cho Streamlit keys
        on_select_dimension: Callback khi chọn dimension
        on_select_metric: Callback khi chọn metric
        show_title: Hiển thị tiêu đề component
    """
    if df_curr is None or df_curr.empty:
        if show_title:
            st.subheader("📊 Phân tích biến động (Movers)")
        st.info("Chưa có dữ liệu kỳ hiện tại.")
        return

    if show_title:
        st.subheader("📊 Phân tích biến động (Movers)")

    # ── Dimension & Metric selectors ─────────────────────────────────────
    col_dim, col_metric = st.columns([1, 1])

    with col_dim:
        dim_options = {d["label"]: d["key"] for d in DIMENSION_OPTIONS}
        valid_dims = {}
        for d in DIMENSION_OPTIONS:
            if d["col"] in df_curr.columns:
                valid_dims[d["label"]] = d["key"]
        if not valid_dims:
            st.warning("Không có cột phân loại phù hợp trong dữ liệu.")
            return

        selected_dim_label = st.segmented_control(
            "Phân tích theo",
            options=list(valid_dims.keys()),
            key=f"{key_prefix}_dim",
            default=list(valid_dims.keys())[0],
            label_visibility="collapsed",
        )
        selected_dim_key = valid_dims.get(selected_dim_label, list(valid_dims.values())[0])

        if on_select_dimension:
            on_select_dimension(selected_dim_key)

    with col_metric:
        metric_options = {m["label"]: m["key"] for m in METRIC_OPTIONS}
        selected_metric_label = st.segmented_control(
            "Chỉ tiêu",
            options=list(metric_options.keys()),
            key=f"{key_prefix}_metric",
            default=list(metric_options.keys())[0],
            label_visibility="collapsed",
        )
        selected_metric_key = metric_options.get(selected_metric_label, list(metric_options.values())[0])
        selected_unit = next((m["unit"] for m in METRIC_OPTIONS if m["key"] == selected_metric_key), "tien")

        if on_select_metric:
            on_select_metric(selected_metric_key)

    # ── Compute movers ────────────────────────────────────────────────────
    dim_col = _pick_dim_col(selected_dim_key)
    if dim_col is None:
        st.error(f"Dimension '{selected_dim_key}' không hợp lệ.")
        return

    results = _compute_movers(df_curr, df_prev, dim_col, selected_metric_key)

    if not results:
        st.info("Không đủ dữ liệu để phân tích.")
        return

    sorted_improved = sorted(results, key=lambda x: x["delta"])
    sorted_declined = sorted(results, key=lambda x: x["delta"], reverse=True)

    if selected_metric_key in ("ty_le_nqh", "roll_rate"):
        top_improved = [r for r in sorted_improved if r["delta"] <= 0][:top_n]
        top_declined = [r for r in sorted_declined if r["delta"] > 0][:top_n]
    else:
        top_improved = [r for r in sorted_improved if r["delta"] <= 0][:top_n]
        top_declined = [r for r in sorted_declined if r["delta"] > 0][:top_n]

    # ── KPI summary row ──────────────────────────────────────────────────
    st.markdown("---")
    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        _render_kpi_box("Tổng số nhóm", len(results), "so", "#1976d2")
    with kpi_cols[1]:
        _render_kpi_box("Cải thiện", len(top_improved), "so", "#2e7d32")
    with kpi_cols[2]:
        _render_kpi_box("Giảm sút", len(top_declined), "so", "#c62828")
    with kpi_cols[3]:
        total_curr = sum(r["curr_value"] for r in results)
        _render_kpi_box("Tổng giá trị", total_curr, selected_unit, "#1976d2")

    st.markdown("---")

    # ── Two-column layout ────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(f"##### ✅ Top {min(len(top_improved), top_n)} Cải thiện nhiều nhất")
        st.caption("Nhóm có delta thấp/âm nhất (tốt lên)")
        if not top_improved:
            st.info("Không có nhóm nào cải thiện.")
        else:
            for i, item in enumerate(top_improved[:top_n]):
                _render_mover_item(item, i + 1, selected_unit, True, f"{key_prefix}_imp_{i}")

    with col_right:
        st.markdown(f"##### ❌ Top {min(len(top_declined), top_n)} Giảm sút nhiều nhất")
        st.caption("Nhóm có delta cao/dương nhất (xấu đi)")
        if not top_declined:
            st.info("Không có nhóm nào giảm sút.")
        else:
            for i, item in enumerate(top_declined[:top_n]):
                _render_mover_item(item, i + 1, selected_unit, False, f"{key_prefix}_dec_{i}")

    # ── Raw data expander ────────────────────────────────────────────────
    with st.expander("📋 Xem bảng dữ liệu đầy đủ", expanded=False):
        rows = []
        for r in results:
            rows.append({
                selected_dim_label: r["key"],
                "Giá trị kỳ trước": r["prev_value"],
                "Giá trị kỳ này": r["curr_value"],
                "Delta": r["delta"],
                "% Delta": r["pct_delta"],
                "Dư nợ kỳ trước": r["prev_tong_du_no"],
                "Dư nợ kỳ này": r["curr_tong_du_no"],
            })
        df_show = pd.DataFrame(rows)
        st.dataframe(df_show, width="stretch", hide_index=True)

    return results
