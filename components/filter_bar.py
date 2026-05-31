"""FilterBar - Thanh lọc dữ liệu nâng cao + Lưu cấu hình bộ lọc."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

import db
from logger import get_logger

logger = get_logger(__name__)


def _get_filter_preset_key(username: str) -> str:
    return f"filter_preset_{username}"


def load_filter_presets(username: str) -> dict[str, dict[str, Any]]:
    """Đọc tất cả bộ lọc đã lưu của user. Trả về {preset_name: {field: value}}."""
    if not username:
        return {}
    data = db.doc_kv(_get_filter_preset_key(username))
    if isinstance(data, dict) and "presets" in data:
        return data["presets"]
    return {}


def save_filter_presets(username: str, presets: dict[str, dict[str, Any]]) -> None:
    """Lưu toàn bộ bộ lọc của user vào kv_store.
    Giữ nguyên trường 'last_used' hiện có (không ghi đè).
    """
    if not username:
        return
    existing = db.doc_kv(_get_filter_preset_key(username)) or {}
    payload = {"presets": presets}
    if "last_used" in existing:
        payload["last_used"] = existing["last_used"]
    db.ghi_kv(_get_filter_preset_key(username), payload, username)
    db.ghi_audit(username, "luu_filter_preset", f"{len(presets)} presets")
    st.cache_data.clear()


def get_last_filter_preset_name(username: str) -> str | None:
    """Lấy tên preset đã dùng lần cuối."""
    data = db.doc_kv(_get_filter_preset_key(username))
    if isinstance(data, dict):
        return data.get("last_used")
    return None


def set_last_filter_preset_name(username: str, name: str) -> None:
    """Ghi nhận preset vừa được chọn."""
    if not username:
        return
    data = db.doc_kv(_get_filter_preset_key(username)) or {}
    data["last_used"] = name
    db.ghi_kv(_get_filter_preset_key(username), data, username)


def filter_bar(
    df: pd.DataFrame,
    filters: list[dict],
    key_prefix: str = "fb",
    on_change: Callable | None = None,
    username: str = "",
) -> dict[str, Any]:
    """Thanh lọc dữ liệu động + lưu/tải cấu hình bộ lọc.

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
        username: nếu có → hiện nút Lưu/Tải bộ lọc từ kv_store

    Returns:
        dict[field -> value] chứa giá trị filter hiện tại
    """
    result = {}

    if not filters:
        return result

    expanded = st.session_state.get(f"{key_prefix}_expanded", False)

    # ── Auto-load last used preset ──────────────────────────────────
    _auto_key = f"{key_prefix}_auto_loaded"
    if username and not st.session_state.get(_auto_key):
        last_name = get_last_filter_preset_name(username)
        if last_name:
            presets = load_filter_presets(username)
            if last_name in presets:
                _apply_preset_to_session(presets[last_name], filters, key_prefix)
        st.session_state[_auto_key] = True

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

    # ── Save / Load presets ─────────────────────────────────────────
    if username and result:
        _show_filter_presets_ui(result, key_prefix, username)

    st.divider()

    if on_change:
        on_change()

    return result


def _apply_preset_to_session(
    preset_values: dict[str, Any],
    filters: list[dict],
    key_prefix: str,
) -> None:
    """Áp dụng giá trị preset vào session_state keys."""
    if filters:
        for f in filters:
            field = f["field"]
            session_key = f"{key_prefix}_{field}"
            if field in preset_values:
                st.session_state[session_key] = preset_values[field]
    else:
        for field, val in preset_values.items():
            session_key = f"{key_prefix}_{field}"
            st.session_state[session_key] = val


def _show_filter_presets_ui(
    current_values: dict[str, Any],
    key_prefix: str,
    username: str,
) -> None:
    """Hiển thị row Lưu/Tải/Xóa bộ lọc."""
    presets = load_filter_presets(username)
    preset_names = sorted(presets.keys())

    st.caption("💾 **Lưu / Tải cấu hình bộ lọc**")
    col_save, col_load, col_del = st.columns([2, 2, 1])

    with col_save:
        save_name = st.text_input(
            "Tên bộ lọc",
            placeholder="VD: Phòng KH-NV, TW...",
            key=f"{key_prefix}_preset_name",
            label_visibility="collapsed",
        )
        if st.button("💾 Lưu", use_container_width=True, key=f"{key_prefix}_save_preset"):
            name = save_name.strip()
            if not name:
                st.toast("⚠️ Nhập tên bộ lọc trước khi lưu", icon="⚠️")
            else:
                presets[name] = dict(current_values)
                save_filter_presets(username, presets)
                set_last_filter_preset_name(username, name)
                st.toast(f"✅ Đã lưu bộ lọc '{name}'", icon="💾")
                st.rerun()

    with col_load:
        if preset_names:
            selected = st.selectbox(
                "Tải bộ lọc",
                options=[""] + preset_names,
                format_func=lambda x: "Chọn bộ lọc đã lưu..." if x == "" else x,
                key=f"{key_prefix}_load_preset",
                label_visibility="collapsed",
            )
            if selected and st.button("📂 Tải", use_container_width=True, key=f"{key_prefix}_load_btn"):
                _apply_preset_to_session(presets[selected], [], key_prefix)
                set_last_filter_preset_name(username, selected)
                st.toast(f"✅ Đã tải bộ lọc '{selected}'", icon="📂")
                st.rerun()
        else:
            st.caption("Chưa có bộ lọc nào được lưu")

    with col_del:
        if preset_names:
            del_name = st.selectbox(
                "Xóa",
                options=[""] + preset_names,
                format_func=lambda x: "🗑️" if x == "" else x,
                key=f"{key_prefix}_del_preset",
                label_visibility="collapsed",
            )
            if del_name and st.button("🗑️", use_container_width=True, key=f"{key_prefix}_del_btn"):
                presets.pop(del_name, None)
                save_filter_presets(username, presets)
                st.toast(f"🗑️ Đã xóa bộ lọc '{del_name}'", icon="🗑️")
                st.rerun()


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
