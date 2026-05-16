"""FilterBar - Thanh lọc dữ liệu nâng cao."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st


def filter_bar(
    df: pd.DataFrame,
    filters: list[dict],
    key_prefix: str = "fb",
    on_change: Callable | None = None,
) -> dict[str, Any]:
    """Thanh lọc dữ liệu động.

    Args:
        df: DataFrame gốc
        filters: Danh sách filter config, mỗi filter là dict:
            - field: tên cột
            - label: nhãn hiển thị
            - type: "select" | "multiselect" | "text" | "range"
            - default: giá trị mặc định (optional)
            - options: list options (nếu type="select"|"multiselect", optional)
            - placeholder: text placeholder (optional)
        key_prefix: prefix cho session state keys
        on_change: callback khi filter thay đổi

    Returns:
        dict[field -> value] chứa giá trị filter hiện tại
    """
    result = {}

    if not filters:
        return result

    expanded = st.session_state.get(f"{key_prefix}_expanded", False)

    col_toggle, col_clear = st.columns([6, 1])
    with col_toggle:
        if st.button(
            "🔍 Bộ lọc" if not expanded else "🔍 Ẩn bộ lọc",
            use_container_width=True,
            key=f"{key_prefix}_toggle",
        ):
            st.session_state[f"{key_prefix}_expanded"] = not expanded
            st.rerun()

    with col_clear:
        if st.button("🔄 Xóa", use_container_width=True, key=f"{key_prefix}_clear"):
            for f in filters:
                key = f"{key_prefix}_{f['field']}"
                st.session_state.pop(key, None)
            st.rerun()

    if not expanded:
        return result

    n_cols = min(len(filters), 4)
    cols = st.columns(n_cols)

    for i, f in enumerate(filters):
        field = f["field"]
        label = f.get("label", field)
        ftype = f.get("type", "select")
        placeholder = f.get("placeholder", f"Chọn {label.lower()}...")

        session_key = f"{key_prefix}_{field}"
        default = f.get("default")

        with cols[i % n_cols]:
            if ftype == "select":
                options = f.get("options")
                if options is None and field in df.columns:
                    options = sorted(df[field].dropna().unique().tolist())
                options = ["Tất cả"] + (options or [])
                val = st.selectbox(
                    label,
                    options=options,
                    index=0 if default is None else options.index(default) if default in options else 0,
                    key=session_key,
                    placeholder=placeholder,
                )
                result[field] = None if val == "Tất cả" else val

            elif ftype == "multiselect":
                options = f.get("options")
                if options is None and field in df.columns:
                    options = sorted(df[field].dropna().unique().tolist())
                val = st.multiselect(
                    label,
                    options=options or [],
                    default=default or [],
                    key=session_key,
                    placeholder=placeholder,
                )
                result[field] = val if val else None

            elif ftype == "text":
                val = st.text_input(
                    label,
                    value=default or "",
                    key=session_key,
                    placeholder=placeholder,
                )
                result[field] = val.strip() if val.strip() else None

            elif ftype == "range":
                if field in df.columns:
                    numeric_col = pd.to_numeric(df[field], errors="coerce")
                    min_v = float(numeric_col.min()) if not numeric_col.isna().all() else 0.0
                    max_v = float(numeric_col.max()) if not numeric_col.isna().all() else 0.0
                else:
                    min_v, max_v = 0.0, 0.0

                range_val = st.slider(
                    label,
                    min_value=min_v,
                    max_value=max_v,
                    value=(min_v, max_v),
                    key=session_key,
                )
                result[field] = range_val

    st.divider()

    if on_change:
        on_change()

    return result


def apply_filters(df: pd.DataFrame, filter_values: dict) -> pd.DataFrame:
    """Áp dụng filter values vào DataFrame.

    Args:
        df: DataFrame gốc
        filter_values: Dict từ filter_bar()

    Returns:
        DataFrame đã được filter
    """
    if not filter_values or df.empty:
        return df

    result = df.copy()

    for field, val in filter_values.items():
        if val is None:
            continue
        if field not in result.columns:
            continue

        if isinstance(val, tuple) and len(val) == 2:
            numeric_col = pd.to_numeric(result[field], errors="coerce")
            result = result[(numeric_col >= val[0]) & (numeric_col <= val[1])]
        elif isinstance(val, list):
            if val:
                result = result[result[field].isin(val)]
        else:
            result = result[result[field].astype(str).str.contains(str(val), case=False, na=False)]

    return result
