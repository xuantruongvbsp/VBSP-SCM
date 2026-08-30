"""Inline filter component cho báo cáo."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING, List, Dict, Any, Callable

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_MA_KH,
    COT_NGUON_VON,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_XA_THANH_THI,
    DS_XA_THANH_THI_THEO_PGD,
)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


# Nhãn hiển thị cho filter nguồn vốn: 1=TW, 2=ĐP
_NV_LABELS = {
    "all": "🌐 Tất cả nguồn vốn",
    "1": "1 — Trung ương",
    "2": "2 — Địa phương",
}

_NV_GROUP_LABELS = {
    "1": "1 — Trung ương",
    "2": "2 — Địa phương",
}


def _chuan_hoa_nguon_von(value) -> str:
    """Chuẩn hóa giá trị cột Nguồn vốn về '1' (TW) / '2' (ĐP), khác → ''."""
    s = str(value).strip()
    if s in {"1", "01", "1.0", "01.0", "TW", "tw"}:
        return "1"
    if s in {"2", "02", "2.0", "02.0", "DP", "dp", "ĐP", "đp"}:
        return "2"
    return ""


def chuan_bi_du_lieu_bao_cao(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn bị dữ liệu trước khi tổng hợp báo cáo tín dụng.

    Loại các dạng dòng gây sai số liệu trong phạm vi báo cáo tín dụng:
    1. Dòng không còn dư nợ/quá hạn/khoanh — nếu giữ lại sẽ đội "Số KH"
       và "Số món vay" bởi các khoản đã tất toán.
    2. Dòng KHÔNG có Số khế ước (KH đã sạch nợ, dư nợ=0, vô chương trình) —
       nếu giữ lại sẽ gộp chung thành 1 "món" rỗng.
    3. Nhiều dòng cùng khoản vay theo (Mã KH, Số khế ước) — giữ dòng đầu,
       tránh double-count dư nợ. Dữ liệu nguồn không bị thay đổi.

    Trả DataFrame đã làm sạch (bản copy).
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    cot_du_no = [
        col for col in (COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH)
        if col in out.columns
    ]
    if cot_du_no:
        mask_con_du_no = pd.Series(False, index=out.index)
        for col in cot_du_no:
            mask_con_du_no |= pd.to_numeric(out[col], errors="coerce").fillna(0) > 0
        out = out.loc[mask_con_du_no].copy()
    if COT_SO_KU in out.columns:
        ku = out[COT_SO_KU].astype("string").str.strip()
        ku_rong = ku.isna() | ku.str.lower().isin({"", "nan", "none", "null", "<na>"})
        out = out.loc[~ku_rong].copy()
    if COT_MA_KH in out.columns and COT_SO_KU in out.columns:
        ma_kh = out[COT_MA_KH].astype("string").str.strip()
        so_ku = out[COT_SO_KU].astype("string").str.strip()
        ma_kh_hop_le = ma_kh.notna() & ~ma_kh.str.lower().isin(
            {"", "nan", "none", "null", "<na>"}
        )
        # Chỉ gộp khi có đủ hai thành phần khóa. Chuẩn hóa khoảng trắng để
        # "KU1" và " KU1 " không bị coi là hai khoản vay khác nhau.
        trung_khoa = pd.DataFrame(
            {"_ma_kh": ma_kh, "_so_ku": so_ku},
            index=out.index,
        ).duplicated(keep="first")
        out = out.loc[~(ma_kh_hop_le & trung_khoa)].copy()
    return out


def loc_nguon_von(df: pd.DataFrame, chon: str) -> pd.DataFrame:
    """Lọc DataFrame theo mã nguồn vốn đã chuẩn hóa; lựa chọn không hợp lệ giữ nguyên df."""
    if df is None or df.empty or COT_NGUON_VON not in df.columns or chon == "all":
        return df

    nv_chuan = df[COT_NGUON_VON].map(_chuan_hoa_nguon_von)
    if chon not in {"1", "2"} or not nv_chuan.eq(chon).any():
        return df
    return df.loc[nv_chuan.eq(chon)].copy()


def chuan_hoa_nhom_nguon_von(df: pd.DataFrame) -> pd.DataFrame:
    """Gộp các biến thể 1/01/TW và 2/02/ĐP thành hai nhãn nguồn vốn chuẩn."""
    if df is None or df.empty or COT_NGUON_VON not in df.columns:
        return df

    result = df.copy()
    nv_chuan = result[COT_NGUON_VON].map(_chuan_hoa_nguon_von)
    result[COT_NGUON_VON] = nv_chuan.map(_NV_GROUP_LABELS).fillna("Khác/Không xác định")
    return result


def render_nguon_von_filter(
    df: pd.DataFrame,
    key: str,
    container: DeltaGenerator | None = None,
) -> pd.DataFrame:
    """
    Filter dữ liệu theo nguồn vốn: Trung ương (1) / Địa phương (2).

    Trả df nguyên vẹn khi thiếu cột Nguồn vốn, chọn "Tất cả" hoặc cột
    không có giá trị 1/2 hợp lệ.
    """
    ctx = container if container is not None else st

    if df is None or df.empty or COT_NGUON_VON not in df.columns:
        return df

    nv_chuan = df[COT_NGUON_VON].map(_chuan_hoa_nguon_von)
    hien_co = [m for m in ("1", "2") if (nv_chuan == m).any()]
    if not hien_co:
        return df

    chon = ctx.radio(
        "💰 Nguồn vốn",
        ["all"] + hien_co,
        format_func=lambda m: _NV_LABELS[m],
        horizontal=True,
        key=f"nv_filter_{key}",
    )
    if chon == "all":
        return df

    df_loc = loc_nguon_von(df, chon)
    ctx.caption(
        f"🏦 Đang lọc: **{_NV_LABELS[chon]}** — {len(df_loc):,} dòng".replace(",", ".")
    )
    return df_loc


# ── Bộ lọc khu vực nông thôn / thành thị ────────────────────────────────────
_KV_LABELS = {
    "all": "🌐 Tất cả khu vực",
    "thanh_thi": "🏙️ Thành thị",
    "nong_thon": "🌾 Nông thôn",
}

_XA_THANH_THI_LC = frozenset(x.casefold() for x in DS_XA_THANH_THI)
_XA_THANH_THI_THEO_PGD_LC = frozenset(
    (ten_pgd.casefold(), ten_xa.casefold())
    for ten_pgd, ten_xa in DS_XA_THANH_THI_THEO_PGD
)


def _phan_loai_khu_vuc(value) -> str:
    """Phân loại một giá trị 'Tên xã' → 'thanh_thi' / 'nong_thon'."""
    s = str(value).strip()
    if not s or s.casefold() in {"nan", "none", "null", "<na>"}:
        return "nong_thon"
    return "thanh_thi" if s.casefold() in _XA_THANH_THI_LC else "nong_thon"


def _chuan_hoa_text_series(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.casefold().fillna("")


def phan_loai_khu_vuc_df(df: pd.DataFrame) -> pd.Series:
    """Phân loại khu vực cho từng dòng; hỗ trợ ngoại lệ theo cặp PGD + Tên xã."""
    kv = df[COT_TEN_XA].map(_phan_loai_khu_vuc)
    if COT_TEN_PGD not in df.columns or not _XA_THANH_THI_THEO_PGD_LC:
        return kv

    ten_pgd = _chuan_hoa_text_series(df[COT_TEN_PGD])
    ten_xa = _chuan_hoa_text_series(df[COT_TEN_XA])
    mask_dac_biet = pd.Series(False, index=df.index)
    for pgd_key, xa_key in _XA_THANH_THI_THEO_PGD_LC:
        mask_dac_biet |= ten_pgd.eq(pgd_key) & ten_xa.eq(xa_key)
    return kv.mask(mask_dac_biet, "thanh_thi")


def loc_khu_vuc(df: pd.DataFrame, chon: str) -> pd.DataFrame:
    """Lọc DataFrame theo khu vực nông thôn/thành thị; lựa chọn không hợp lệ giữ nguyên df."""
    if df is None or df.empty or COT_TEN_XA not in df.columns or chon == "all":
        return df
    if chon not in {"thanh_thi", "nong_thon"}:
        return df
    kv = phan_loai_khu_vuc_df(df)
    return df.loc[kv.eq(chon)].copy()


def render_khu_vuc_filter(
    df: pd.DataFrame,
    key: str,
    container: DeltaGenerator | None = None,
) -> pd.DataFrame:
    """
    Filter dữ liệu theo khu vực: Thành thị (phường) / Nông thôn (xã).

    Trả df nguyên vẹn khi thiếu cột Tên xã, chọn "Tất cả", hoặc cột
    không có giá trị.
    """
    ctx = container if container is not None else st

    if df is None or df.empty or COT_TEN_XA not in df.columns:
        return df

    kv = phan_loai_khu_vuc_df(df)
    hien_co = [m for m in ("thanh_thi", "nong_thon") if (kv == m).any()]
    if not hien_co:
        return df

    chon = ctx.radio(
        "🏙️ Khu vực",
        ["all"] + hien_co,
        format_func=lambda m: _KV_LABELS[m],
        horizontal=True,
        key=f"kv_filter_{key}",
    )
    if chon == "all":
        return df

    df_loc = loc_khu_vuc(df, chon)
    ctx.caption(
        f"🏙️ Đang lọc: **{_KV_LABELS[chon]}** — {len(df_loc):,} dòng".replace(",", ".")
    )
    return df_loc


def render_inline_filter(
    df: pd.DataFrame,
    filter_columns: List[str],
    key: str,
    container: DeltaGenerator | None = None,
    on_filter_change: Callable | None = None,
) -> pd.DataFrame:
    """
    Hiển thị inline filter ngay trên đầu bảng.
    
    Args:
        df: DataFrame gốc
        filter_columns: Các cột cần filter
        key: Streamlit key
        container: Streamlit container
        on_filter_change: Callback khi filter thay đổi
    
    Returns:
        DataFrame đã filter
    """
    ctx = container if container is not None else st
    
    df_filtered = df.copy()
    
    # Tạo row cho filters
    n_cols = len(filter_columns)
    cols = ctx.columns(min(n_cols, 4))  # Tối đa 4 filter trên 1 row
    
    for idx, col_name in enumerate(filter_columns):
        if idx < len(cols) and col_name in df.columns:
            with cols[idx]:
                # Danh sách của filter sau phụ thuộc kết quả filter trước để
                # không cho phép chọn một tổ hợp Xã/Chương trình không tồn tại.
                unique_vals = ["Tất cả"] + sorted(
                    df_filtered[col_name].dropna().unique().tolist(),
                    key=lambda value: str(value).casefold(),
                )
                widget_key = f"filter_{key}_{col_name}"
                if (
                    widget_key in st.session_state
                    and st.session_state[widget_key] not in unique_vals
                ):
                    st.session_state[widget_key] = "Tất cả"
                
                # Selectbox cho mỗi cột
                selected = st.selectbox(
                    f"🔍 {col_name}",
                    unique_vals,
                    key=widget_key,
                    label_visibility="visible",
                )
                
                # Apply filter
                if selected != "Tất cả":
                    df_filtered = df_filtered[df_filtered[col_name] == selected]
    
    # Hiển thị số lượng kết quả
    ctx.caption(f"📊 Hiển thị **{len(df_filtered):,}** / **{len(df):,}** dòng".replace(",", "."))
    
    # Callback nếu có
    if on_filter_change:
        on_filter_change(df_filtered)
    
    return df_filtered


def render_quick_search(
    df: pd.DataFrame,
    search_columns: List[str],
    key: str,
    placeholder: str = "🔍 Tìm kiếm nhanh...",
    container: DeltaGenerator | None = None,
) -> pd.DataFrame:
    """
    Tìm kiếm nhanh across multiple columns.
    
    Args:
        df: DataFrame gốc
        search_columns: Các cột để tìm kiếm
        key: Streamlit key
        placeholder: Placeholder text
        container: Streamlit container
    
    Returns:
        DataFrame đã filter
    """
    ctx = container if container is not None else st
    
    # Search input
    search_term = ctx.text_input(
        "Tìm kiếm nhanh",
        placeholder=placeholder,
        key=f"quick_search_{key}",
        label_visibility="collapsed",
    )
    
    df_filtered = df.copy()
    
    if search_term:
        # Tìm kiếm substring trong các cột
        mask = pd.Series([False] * len(df), index=df.index)
        
        for col in search_columns:
            if col in df.columns:
                # Chuyển về string và tìm kiếm không phân biệt case
                col_values = df[col].astype(str).str.lower()
                mask |= col_values.str.contains(search_term.lower(), na=False)
        
        df_filtered = df[mask]
        
        ctx.caption(f"🔎 Tìm thấy **{len(df_filtered):,}** kết quả cho \"{search_term}\"".replace(",", "."))
    
    return df_filtered


def render_combined_filter_search(
    df: pd.DataFrame,
    filter_columns: List[str],
    search_columns: List[str],
    key: str,
    container: DeltaGenerator | None = None,
) -> pd.DataFrame:
    """
    Kết hợp filter và search.
    
    Returns:
        DataFrame đã filter và search
    """
    ctx = container if container is not None else st
    
    # Filter section
    ctx.markdown("**🔧 Bộ lọc**")
    df_filtered = render_inline_filter(
        df, filter_columns, f"{key}_filter", container=ctx
    )
    
    ctx.divider()
    
    # Search section
    ctx.markdown("**🔍 Tìm kiếm**")
    df_searched = render_quick_search(
        df_filtered, search_columns, f"{key}_search", container=ctx
    )
    
    return df_searched
