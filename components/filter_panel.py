"""Filter Panel component for advanced search and filtering."""

from __future__ import annotations

import re
import unicodedata

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING, Callable
from datetime import date, datetime

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON,
    COT_TEN_CT, COT_NGUON_VON, COT_NGAY_VAY, COT_NGAY_DH,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_KHOANH,
    COT_TINH_TRANG, NGUON_VON_LABEL,
    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_CMND, COT_SDT,
)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


@st.cache_data(show_spinner=False)
def _get_unique_values(_df: pd.DataFrame, col: str, ts: float = 0.0) -> list:
    """Get sorted unique values from column, handling missing values."""
    _ = ts
    if col not in _df.columns:
        return []
    values = _df[col].dropna().unique().tolist()
    return sorted([str(v) for v in values if v != ""])


@st.cache_data(show_spinner=False)
def _pre_compute_max_du_no(_df: pd.DataFrame, col: str, ts: float = 0.0) -> float:
    """Cache max dư nợ — tránh full column scan mỗi rerun."""
    _ = ts
    if col not in _df.columns:
        return 1_000_000_000.0
    try:
        ser = pd.to_numeric(_df[col], errors="coerce")
        m = float(ser.max()) if not ser.empty and pd.notna(ser.max()) else 0.0
        return max(m, 1_000_000.0)
    except Exception:
        return 1_000_000_000.0


@st.cache_data(show_spinner=False)
def _pre_convert_dates(_df: pd.DataFrame, cols: tuple[str, ...], ts: float = 0.0) -> dict[str, "pd.Series"]:
    """Cache pre-converted datetime series — tránh pd.to_datetime() mỗi rerun."""
    _ = ts
    result: dict[str, pd.Series] = {}
    for col in cols:
        if col in _df.columns:
            result[col] = pd.to_datetime(_df[col], errors="coerce")
    return result


@st.cache_data(show_spinner=False)
def _get_options_filtered(
    _df: pd.DataFrame, filter_col: str, filter_vals: tuple, target_col: str, ts: float = 0.0
) -> list:
    """Unique target_col values filtered by filter_col — cached by (filter_vals, ts)."""
    _ = ts
    if not filter_vals or filter_col not in _df.columns or target_col not in _df.columns:
        return _get_unique_values(_df, target_col, ts)
    mask = _df[filter_col].isin(filter_vals)
    return sorted(_df.loc[mask, target_col].dropna().unique().tolist())


@st.cache_data(show_spinner=False)
def _pre_compute_search_text(_df: pd.DataFrame, search_cols: tuple[str, ...], ts: float = 0.0) -> "pd.Series":
    """Cache chuỗi tìm kiếm đã chuẩn hóa — ghép các cột, normalize 1 lần duy nhất."""
    _ = ts
    parts: list[pd.Series] = []
    for col in search_cols:
        if col in _df.columns:
            s = _df[col].fillna("").astype(str)
            s = s.str.lower().str.replace("đ", "d", regex=False)
            s = s.map(lambda x: unicodedata.normalize("NFD", str(x)) if x else "")
            s = s.map(lambda x: "".join(ch for ch in x if unicodedata.category(ch) != "Mn") if x else "")
            s = s.str.replace(r"\s+", " ", regex=True).str.strip()
            parts.append(s)
    if parts:
        return pd.concat(parts, axis=0).groupby(level=0).agg(" | ".join)
    return pd.Series("", index=_df.index)


def _normalize_nguon_von_code(value) -> str:
    s = str(value).strip()
    if s in {"1", "01", "1.0", "01.0", "TW", "tw"}:
        return "1"
    if s in {"2", "02", "2.0", "02.0", "DP", "dp", "ĐP", "đp"}:
        return "2"
    return s


def _normalize_search_text(value) -> str:
    """Chuẩn hóa chữ để tìm kiếm tiếng Việt không phân biệt dấu/hoa thường."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    text = str(value).strip().casefold().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text)


def _keyword_search_mask(
    df: pd.DataFrame,
    keyword: str,
    search_cols: list[str],
    search_text: "pd.Series | None" = None,
) -> pd.Series:
    """Tạo mask tìm kiếm nhanh, hỗ trợ nhập tên có dấu hoặc không dấu.

    Args:
        search_text: Pre-computed normalized search text (để tránh normalize lại mỗi lần).
                     Nếu có, chỉ scan 1 cột này thay vì normalize từng cột.
    """
    kw_raw = str(keyword or "").strip()
    if not kw_raw:
        return pd.Series(True, index=df.index)

    kw_lower = kw_raw.lower()
    kw_norm = _normalize_search_text(kw_raw)

    # Fast path: dùng pre-computed search text column
    if search_text is not None and len(search_text) == len(df):
        mask = search_text.str.contains(kw_norm, regex=False, na=False)
        if kw_lower != kw_norm:
            mask |= search_text.str.lower().str.contains(kw_lower, regex=False, na=False)
        return mask

    # Slow path: scan từng cột
    mask = pd.Series(False, index=df.index)
    for col in search_cols:
        if col not in df.columns:
            continue
        s = df[col].fillna("").astype(str)
        mask |= s.str.lower().str.contains(kw_lower, regex=False, na=False)
        if kw_norm:
            mask |= s.map(_normalize_search_text).str.contains(kw_norm, regex=False, na=False)
    return mask


def render_filter_panel(
    df: pd.DataFrame,
    df_nq11: pd.DataFrame | None,
    df_gqvl: pd.DataFrame | None,
    pgd_user: str | None,
    on_filter_change: Callable[[pd.DataFrame], None] | None = None,
    ts_hstd: float = 0.0,
) -> pd.DataFrame:
    """
    Render advanced filter panel and return filtered DataFrame.
    
    Args:
        df: Source DataFrame
        df_nq11: NQ11 data for filtering (optional)
        df_gqvl: GQVL data for filtering (optional)
        pgd_user: PGD filter for user scope (None = all)
        on_filter_change: Callback when filter changes
    
    Returns:
        Filtered DataFrame
    """
    
    # Pre-compute cached values
    _max_du_no = _pre_compute_max_du_no(df, COT_TONG_DU_NO, ts_hstd)
    _date_series = _pre_convert_dates(df, (COT_NGAY_VAY, COT_NGAY_DH), ts_hstd)

    # Initialize filter state
    if "tracuu_filters" not in st.session_state:
        st.session_state.tracuu_filters = {
            "search_keyword": "",
            "selected_pgd": [] if pgd_user is None else [pgd_user],
            "selected_xa": [],
            "selected_thon": [],
            "selected_ct": [],
            "selected_nv": [],
            "du_no_range": (0.0, _max_du_no),
            "ngay_vay_from": None,
            "ngay_vay_to": None,
            "ngay_dh_from": None,
            "ngay_dh_to": None,
            "filter_qua_han": False,
            "filter_nq11": False,
            "filter_gqvl": False,
            "filter_khoanh": False,
            "filter_active": True,
        }
    
    # Quick search bar
    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        search_kw = st.text_input(
            "🔍 Tìm kiếm nhanh",
            value=st.session_state.tracuu_filters["search_keyword"],
            placeholder="Tên KH, CMND/CCCD, Số khế ước, SĐT...",
            key="tc_search_kw",
        )
    with col2:
        st.write("")
        st.write("")
        search_clicked = st.button("🔍 Tìm", use_container_width=True, type="primary")
    with col3:
        st.write("")
        st.write("")
        _has_any_filter = bool(
            st.session_state.tracuu_filters.get("search_keyword")
            or st.session_state.tracuu_filters.get("selected_pgd")
            or st.session_state.tracuu_filters.get("selected_xa")
            or st.session_state.tracuu_filters.get("selected_thon")
            or st.session_state.tracuu_filters.get("selected_ct")
            or st.session_state.tracuu_filters.get("selected_nv")
            or st.session_state.tracuu_filters.get("ngay_vay_from")
            or st.session_state.tracuu_filters.get("ngay_vay_to")
            or st.session_state.tracuu_filters.get("ngay_dh_from")
            or st.session_state.tracuu_filters.get("ngay_dh_to")
            or st.session_state.tracuu_filters.get("filter_qua_han")
            or st.session_state.tracuu_filters.get("filter_nq11")
            or st.session_state.tracuu_filters.get("filter_gqvl")
            or st.session_state.tracuu_filters.get("filter_khoanh")
        )
        if st.button(
            "🔄 Reset",
            use_container_width=True,
            key="tc_reset_top",
            disabled=not _has_any_filter,
        ):
            st.session_state.tracuu_filters = {
                "search_keyword": "",
                "selected_pgd": [] if pgd_user is None else [pgd_user],
                "selected_xa": [],
                "selected_thon": [],
                "selected_ct": [],
                "selected_nv": [],
                "du_no_range": (0.0, _max_du_no),
                "ngay_vay_from": None,
                "ngay_vay_to": None,
                "ngay_dh_from": None,
                "ngay_dh_to": None,
                "filter_qua_han": False,
                "filter_nq11": False,
                "filter_gqvl": False,
                "filter_khoanh": False,
                "filter_active": True,
            }
            st.rerun()
    
    # Advanced filters expander
    with st.expander("📋 Bộ lọc nâng cao", expanded=False):
        
        # Row 1: Địa bàn
        st.markdown("**📍 Địa bàn**")
        col_pgd, col_xa, col_thon = st.columns(3)
        
        with col_pgd:
            ds_pgd = _get_unique_values(df, COT_TEN_PGD, ts_hstd)
            if pgd_user:
                # User PGD chỉ thấy PGD của mình
                selected_pgd = [pgd_user]
                st.multiselect(
                    "Phòng Giao Dịch",
                    options=ds_pgd,
                    default=selected_pgd,
                    disabled=True,
                    key="tc_pgd_disabled",
                )
            else:
                selected_pgd = st.multiselect(
                    "Phòng Giao Dịch",
                    options=ds_pgd,
                    default=st.session_state.tracuu_filters["selected_pgd"],
                    placeholder="Tất cả PGD",
                    key="tc_pgd",
                )
        
        with col_xa:
            ds_xa = _get_options_filtered(df, COT_TEN_PGD, tuple(selected_pgd), COT_TEN_XA, ts_hstd)
            selected_xa = st.multiselect(
                "Xã/Phường",
                options=ds_xa,
                default=[x for x in st.session_state.tracuu_filters["selected_xa"] if x in ds_xa],
                placeholder="Tất cả xã",
                key="tc_xa",
            )
        
        with col_thon:
            ds_thon = _get_options_filtered(df, COT_TEN_XA, tuple(selected_xa), COT_TEN_THON, ts_hstd)
            selected_thon = st.multiselect(
                "Thôn/Tổ dân phố",
                options=ds_thon,
                default=[x for x in st.session_state.tracuu_filters["selected_thon"] if x in ds_thon],
                placeholder="Tất cả thôn",
                key="tc_thon",
            )
        
        st.divider()
        
        # Row 2: Chương trình & Nguồn vốn
        st.markdown("**📑 Chương trình & Nguồn vốn**")
        col_ct, col_nv = st.columns(2)
        
        with col_ct:
            ds_ct = _get_unique_values(df, COT_TEN_CT, ts_hstd)
            selected_ct = st.multiselect(
                "Chương trình tín dụng",
                options=ds_ct,
                default=st.session_state.tracuu_filters["selected_ct"],
                placeholder="Tất cả chương trình",
                key="tc_ct",
            )
        
        with col_nv:
            ds_nv = _get_unique_values(df, COT_NGUON_VON, ts_hstd)
            ds_nv_norm = sorted({v for v in (_normalize_nguon_von_code(x) for x in ds_nv) if v != ""})
            nv_options = []
            for nv in ds_nv_norm:
                label = NGUON_VON_LABEL.get(nv, NGUON_VON_LABEL.get(str(nv), nv))
                nv_options.append((nv, f"{nv} - {label}"))
            selected_nv_labels = st.multiselect(
                "Nguồn vốn",
                options=[opt[1] for opt in nv_options],
                default=[
                    f"{nv} - {NGUON_VON_LABEL.get(nv, NGUON_VON_LABEL.get(str(nv), nv))}"
                    for nv in st.session_state.tracuu_filters["selected_nv"]
                    if any(opt[0] == nv for opt in nv_options)
                ],
                placeholder="Tất cả nguồn vốn",
                key="tc_nv",
            )
            # Map back to values
            selected_nv = [opt[0] for opt in nv_options if opt[1] in selected_nv_labels]
        
        st.divider()
        
        # Row 3: Dư nợ & Ngày
        st.markdown("**💰 Dư nợ & Ngày tháng**")
        
        # Dư nợ range
        if COT_TONG_DU_NO in df.columns:
            raw_range = st.session_state.tracuu_filters["du_no_range"]
            safe_value = (
                float(raw_range[0]),
                min(float(raw_range[1]), _max_du_no),
            )
            du_no_range = st.slider(
                "Khoảng dư nợ (VNĐ)",
                min_value=0.0,
                max_value=_max_du_no,
                value=safe_value,
                step=1_000_000.0,
                format="%,.0f",
                key="tc_du_no",
            )
        else:
            du_no_range = (0.0, float('inf'))
        
        col_date1, col_date2 = st.columns(2)
        
        with col_date1:
            st.markdown("**📅 Ngày vay**")
            col_from, col_to = st.columns(2)
            with col_from:
                ngay_vay_from = st.date_input(
                    "Từ ngày",
                    value=st.session_state.tracuu_filters["ngay_vay_from"],
                    key="tc_ngay_vay_from",
                    format="DD/MM/YYYY",
                )
            with col_to:
                ngay_vay_to = st.date_input(
                    "Đến ngày",
                    value=st.session_state.tracuu_filters["ngay_vay_to"],
                    key="tc_ngay_vay_to",
                    format="DD/MM/YYYY",
                )
        
        with col_date2:
            st.markdown("**📅 Ngày đến hạn**")
            col_from, col_to = st.columns(2)
            with col_from:
                ngay_dh_from = st.date_input(
                    "Từ ngày",
                    value=st.session_state.tracuu_filters["ngay_dh_from"],
                    key="tc_ngay_dh_from",
                    format="DD/MM/YYYY",
                )
            with col_to:
                ngay_dh_to = st.date_input(
                    "Đến ngày",
                    value=st.session_state.tracuu_filters["ngay_dh_to"],
                    key="tc_ngay_dh_to",
                    format="DD/MM/YYYY",
                )
        
        st.divider()
        
        # Row 4: Trạng thái & Tình trạng
        st.markdown("**⚠️ Trạng thái đặc biệt**")
        col_status1, col_status2 = st.columns(2)
        
        with col_status1:
            filter_qua_han = st.toggle(
                "🔴 Chỉ hồ sơ quá hạn",
                value=st.session_state.tracuu_filters["filter_qua_han"],
                key="tc_qua_han",
            )
            filter_nq11 = st.toggle(
                "✨ Chỉ hồ sơ NQ11",
                value=st.session_state.tracuu_filters["filter_nq11"],
                key="tc_nq11",
            )
        
        with col_status2:
            filter_gqvl = st.toggle(
                "📋 Chỉ hồ sơ GQVL",
                value=st.session_state.tracuu_filters["filter_gqvl"],
                key="tc_gqvl",
            )
            filter_khoanh = st.toggle(
                "🔒 Chỉ hồ sơ khoanh nợ",
                value=st.session_state.tracuu_filters["filter_khoanh"],
                key="tc_khoanh",
            )
        
        # Filter actions
        st.divider()
        col_reset, col_save, col_spacer = st.columns([1, 1, 3])
        with col_reset:
            if st.button("🔄 Đặt lại", use_container_width=True, key="tc_reset"):
                st.session_state.tracuu_filters = {
                    "search_keyword": "",
                    "selected_pgd": [] if pgd_user is None else [pgd_user],
                    "selected_xa": [],
                    "selected_thon": [],
                    "selected_ct": [],
                    "selected_nv": [],
                    "du_no_range": (0.0, _max_du_no),
                    "ngay_vay_from": None,
                    "ngay_vay_to": None,
                    "ngay_dh_from": None,
                    "ngay_dh_to": None,
                    "filter_qua_han": False,
                    "filter_nq11": False,
                    "filter_gqvl": False,
                    "filter_khoanh": False,
                    "filter_active": True,
                }
                st.rerun()
        with col_save:
            st.button("💾 Lưu bộ lọc", use_container_width=True, disabled=True, key="tc_save_filter")
    
    # ── Xây dựng composite mask (1 Series bool duy nhất, không copy) ──
    mask = pd.Series(True, index=df.index)

    # -- Pre-compute search text (cached, chỉ tính 1 lần) --
    _search_cols = (COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_CMND, COT_SDT)
    _search_text = _pre_compute_search_text(df, _search_cols, ts_hstd)

    # 1. Keyword search
    if search_kw:
        mask &= _keyword_search_mask(df, search_kw, list(_search_cols), _search_text)

    # 2. Địa bàn filters
    if selected_pgd and COT_TEN_PGD in df.columns:
        mask &= df[COT_TEN_PGD].astype(str).str.strip().isin({str(v).strip() for v in selected_pgd})

    if selected_xa and COT_TEN_XA in df.columns:
        mask &= df[COT_TEN_XA].astype(str).str.strip().isin({str(v).strip() for v in selected_xa})

    if selected_thon and COT_TEN_THON in df.columns:
        mask &= df[COT_TEN_THON].astype(str).str.strip().isin({str(v).strip() for v in selected_thon})

    # 3. Chương trình & Nguồn vốn
    if selected_ct and COT_TEN_CT in df.columns:
        mask &= df[COT_TEN_CT].astype(str).str.strip().isin({str(v).strip() for v in selected_ct})

    if selected_nv and COT_NGUON_VON in df.columns:
        _nv_norm = df[COT_NGUON_VON].map(_normalize_nguon_von_code)
        mask &= _nv_norm.astype(str).str.strip().isin({str(v).strip() for v in selected_nv})

    # 4. Dư nợ range
    if COT_TONG_DU_NO in df.columns:
        _dn = pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0)
        mask &= (_dn >= float(du_no_range[0])) & (_dn <= float(du_no_range[1]))

    # 5. Date filters
    if (ngay_vay_from or ngay_vay_to) and COT_NGAY_VAY in df.columns:
        _ts_vay = _date_series.get(COT_NGAY_VAY)
        if _ts_vay is None:
            _ts_vay = pd.to_datetime(df[COT_NGAY_VAY], errors="coerce")
        if ngay_vay_from:
            mask &= _ts_vay >= pd.Timestamp(ngay_vay_from)
        if ngay_vay_to:
            mask &= _ts_vay <= pd.Timestamp(ngay_vay_to)

    if (ngay_dh_from or ngay_dh_to) and COT_NGAY_DH in df.columns:
        _ts_dh = _date_series.get(COT_NGAY_DH)
        if _ts_dh is None:
            _ts_dh = pd.to_datetime(df[COT_NGAY_DH], errors="coerce")
        if ngay_dh_from:
            mask &= _ts_dh >= pd.Timestamp(ngay_dh_from)
        if ngay_dh_to:
            mask &= _ts_dh <= pd.Timestamp(ngay_dh_to)

    # 6. Special status filters
    if filter_qua_han and COT_DU_NO_QH in df.columns:
        _qh = pd.to_numeric(df[COT_DU_NO_QH], errors="coerce").fillna(0)
        mask &= _qh > 0

    if filter_nq11:
        if "__is_nq11" in df.columns:
            mask &= df["__is_nq11"]
        elif df_nq11 is not None and not df_nq11.empty and COT_SO_KU in df.columns:
            _nq_ku_col = "Số khế ước" if "Số khế ước" in df_nq11.columns else COT_SO_KU
            if _nq_ku_col in df_nq11.columns:
                _set_nq = set(df_nq11[_nq_ku_col].dropna().astype(str).str.strip())
                mask &= df[COT_SO_KU].astype(str).str.strip().isin(_set_nq)

    if filter_gqvl:
        if "__is_gqvl" in df.columns:
            mask &= df["__is_gqvl"]
        elif df_gqvl is not None and not df_gqvl.empty and COT_SO_KU in df.columns:
            _gq_ku_col = "Số khế ước" if "Số khế ước" in df_gqvl.columns else COT_SO_KU
            if _gq_ku_col in df_gqvl.columns:
                _set_gq = set(df_gqvl[_gq_ku_col].dropna().astype(str).str.strip())
                mask &= df[COT_SO_KU].astype(str).str.strip().isin(_set_gq)

    if filter_khoanh and COT_DU_NO_KHOANH in df.columns:
        _kn = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
        mask &= _kn > 0

    # ── Copy 1 lần duy nhất tại đây ──
    df_filtered = df.loc[mask].copy()
    
    # Update session state
    st.session_state.tracuu_filters.update({
        "search_keyword": search_kw,
        "selected_pgd": selected_pgd,
        "selected_xa": selected_xa,
        "selected_thon": selected_thon,
        "selected_ct": selected_ct,
        "selected_nv": selected_nv,
        "du_no_range": du_no_range,
        "ngay_vay_from": ngay_vay_from,
        "ngay_vay_to": ngay_vay_to,
        "ngay_dh_from": ngay_dh_from,
        "ngay_dh_to": ngay_dh_to,
        "filter_qua_han": filter_qua_han,
        "filter_nq11": filter_nq11,
        "filter_gqvl": filter_gqvl,
        "filter_khoanh": filter_khoanh,
    })
    
    # Callback
    if on_filter_change:
        on_filter_change(df_filtered)
    
    if st.session_state.get("_debug_tracuu_filters", False):
        with st.expander("🧪 Debug bộ lọc", expanded=False):
            st.write({"rows_before": int(len(df)), "rows_after": int(len(df_filtered))})
            st.write(
                {
                    "keyword": search_kw,
                    "selected_pgd": selected_pgd,
                    "selected_xa": selected_xa,
                    "selected_thon": selected_thon,
                    "selected_ct": selected_ct,
                    "selected_nv": selected_nv,
                    "du_no_range": du_no_range,
                    "ngay_vay_from": ngay_vay_from,
                    "ngay_vay_to": ngay_vay_to,
                    "ngay_dh_from": ngay_dh_from,
                    "ngay_dh_to": ngay_dh_to,
                    "filter_qua_han": filter_qua_han,
                    "filter_nq11": filter_nq11,
                    "filter_gqvl": filter_gqvl,
                    "filter_khoanh": filter_khoanh,
                }
            )
            _cols = [
                COT_TONG_DU_NO,
                COT_DU_NO_QH,
                COT_DU_NO_KHOANH,
                COT_NGUON_VON,
                COT_TEN_PGD,
                COT_TEN_CT,
            ]
            _present = [c for c in _cols if c in df.columns]
            if _present:
                st.write({c: str(df[c].dtype) for c in _present})

    return df_filtered
