"""
Tab Nguồn vốn địa phương — Phân hệ Chi nhánh.

Báo cáo Tỷ trọng Vốn ủy thác địa phương trên Tổng nguồn vốn:
  Tỷ lệ % = Nguồn vốn ngân sách địa phương (Tỉnh/Huyện) ủy thác / Tổng nguồn vốn tại địa phương

Phân tích theo 3 chiều: PGD, Xã, Chương trình tín dụng.
Dữ liệu từ cột "Nguồn vốn" (1=TW, 2=ĐP) trong HSTD.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from components.delta_card import kpi_row
from config import (
    COT_MA_CHUONG_TRINH,
    COT_MA_NHA_DAU_TU,
    COT_NGUON_VON,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
    DS_PGD,
)
from logger import get_logger
from data.pgd import pgd_slug
from services.bc_tongquan_service import xuat_pdf_bc
from snapshot_service import (
    danh_sach_ky,
    doc_snapshot_nvdp_range,
    ky_baseline,
)
from tabs.base_tab import TabContext
from utils import fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel, lazy_tabs

logger = get_logger(__name__)

_COLOR_TW = "#42A5F5"
_COLOR_DP = "#EF5350"
_COLOR_DP_TINH = "#26A69A"
_COLOR_DP_XA = "#FFB74D"
_CHART_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
_EXCEL_STATE_PREFIX = "nvdp_excel_buf_"
_PDF_STATE_PREFIX = "nvdp_pdf_buf_"
_EXPORT_SOURCE_ALL = "Tất cả nguồn vốn"
_EXPORT_SOURCE_DP = "Chỉ nguồn Địa phương"
_EXPORT_SOURCE_DP_TINH = "Chỉ ĐP cấp tỉnh"
_EXPORT_SOURCE_DP_XA = "Chỉ ĐP cấp xã/khác"
_EXPORT_SOURCE_TW = "Chỉ nguồn Trung ương"
_EXPORT_SOURCE_OPTIONS = [
    _EXPORT_SOURCE_ALL,
    _EXPORT_SOURCE_DP,
    _EXPORT_SOURCE_DP_TINH,
    _EXPORT_SOURCE_DP_XA,
    _EXPORT_SOURCE_TW,
]
_EXPORT_SHEET_XA_02_CT = "Nguồn xã 02 CT"
_EXPORT_SHEET_PGD = "Theo PGD"
_EXPORT_SHEET_XA = "Theo Xã"
_EXPORT_SHEET_CT = "Theo Chương trình"
_EXPORT_SHEET_OPTIONS = [
    _EXPORT_SHEET_XA_02_CT,
    _EXPORT_SHEET_PGD,
    _EXPORT_SHEET_XA,
    _EXPORT_SHEET_CT,
]


def _text_sach(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "<na>"} else text


def _text_sach_series(values: pd.Series) -> pd.Series:
    text = values.astype("string").fillna("").str.strip()
    return text.mask(text.str.lower().isin(("nan", "none", "<na>", "")), "")


def _ma_ct_series_int(values: pd.Series | None, index: pd.Index) -> pd.Series:
    if values is None:
        return pd.Series(pd.NA, index=index, dtype="Int64")
    numeric = pd.to_numeric(values, errors="coerce")
    result = pd.Series(pd.NA, index=index, dtype="Int64")
    valid = numeric.notna()
    if valid.any():
        result.loc[valid] = numeric.loc[valid].astype(float).astype(int)
    return result


def _map_nguon_von(v) -> str:
    """Phân loại nguồn vốn: 'Trung ương' | 'Địa phương' | 'Khác'."""
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


def _nguon_von_label_series(values: pd.Series) -> pd.Series:
    """Vectorized version of _map_nguon_von for large HSTD frames."""
    if pd.api.types.is_numeric_dtype(values):
        numeric = pd.to_numeric(values, errors="coerce")
        out = pd.Series("Khác", index=values.index, dtype="object")
        out.loc[numeric.eq(1)] = "Trung ương"
        out.loc[numeric.eq(2)] = "Địa phương"
        return out

    text = values.astype("string").fillna("").str.strip().str.upper()
    numeric = pd.to_numeric(text, errors="coerce")

    out = pd.Series("Khác", index=values.index, dtype="object")
    mask_tw = text.isin(("1", "1.0", "TW", "TRUNG ƯƠNG")) | numeric.eq(1)
    mask_dp = text.isin(("2", "2.0", "ĐP", "ĐỊA PHƯƠNG")) | numeric.eq(2)
    out.loc[mask_tw] = "Trung ương"
    out.loc[mask_dp] = "Địa phương"
    return out


def _rule_cap_lookup() -> tuple[dict[tuple[int, str], str], dict[str, str]]:
    """Map rule Mã CT + Mã NĐT sang cấp vốn, đọc kv_store đúng 1 lần mỗi render."""
    exact: dict[tuple[int, str], str] = {}
    fallback: dict[str, str] = {}
    for item in db.doc_ndt_dp_rule_list():
        ma_ndt = _text_sach(item.get("ma", ""))
        if not ma_ndt:
            continue
        cap = "xa" if str(item.get("cap", "tinh")).strip().lower() == "xa" else "tinh"
        ma_ct = item.get("ma_ct")
        if ma_ct is None:
            fallback[ma_ndt] = cap
            continue
        ma_ct_i = _ma_ct_series_int(pd.Series([ma_ct]), pd.Index([0])).iloc[0]
        if pd.isna(ma_ct_i):
            continue
        exact[(int(ma_ct_i), ma_ndt)] = cap
    return exact, fallback


def _rules_cache_key(rules: list[dict]) -> str:
    """Fingerprint rule phân loại Mã NĐT để cache bust khi admin đổi rule."""
    parts = []
    for item in rules:
        ma = _text_sach(item.get("ma", ""))
        if not ma:
            continue
        ma_ct = item.get("ma_ct")
        cap = "xa" if str(item.get("cap", "tinh")).strip().lower() == "xa" else "tinh"
        parts.append(f"{ma_ct or 'ALL'}:{ma}:{cap}")
    return "|".join(sorted(parts))


def _kh_map_cache_key(nhan_dot: str, kh_map: dict[str, float] | None) -> str:
    """Fingerprint KH ĐP để cache Excel đổi khi sửa số trong cùng một đợt."""
    if not kh_map:
        return "no_kh"
    parts = [str(nhan_dot or "")]
    parts.extend(f"{k}:{float(v or 0):.0f}" for k, v in sorted(kh_map.items()))
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _excel_state_key(view_key: str, ts_hstd: float, rules_key: str, kh_key: str = "") -> str:
    digest = hashlib.sha1(f"{rules_key}|{kh_key}".encode("utf-8")).hexdigest()[:12]
    return f"{_EXCEL_STATE_PREFIX}{view_key}_{ts_hstd}_{digest}"


def _clear_old_excel_buffers(active_key: str) -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith(_EXCEL_STATE_PREFIX) and key != active_key:
            st.session_state.pop(key, None)


def _clear_old_pdf_buffers(active_key: str) -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith(_PDF_STATE_PREFIX) and key != active_key:
            st.session_state.pop(key, None)


def _export_sheet_options(is_pgd_view: bool) -> list[str]:
    if is_pgd_view:
        return [s for s in _EXPORT_SHEET_OPTIONS if s != _EXPORT_SHEET_PGD]
    return list(_EXPORT_SHEET_OPTIONS)


def _clean_selected_options(values: list[str] | tuple[str, ...], allowed: list[str]) -> list[str]:
    allowed_set = set(allowed)
    return [str(v) for v in values if str(v) in allowed_set]


def _export_condition_key(
    source_filter: str,
    pgd_values: list[str] | tuple[str, ...],
    xa_values: list[str] | tuple[str, ...],
    ct_values: list[str] | tuple[str, ...],
    sheet_names: list[str] | tuple[str, ...],
) -> str:
    parts = [
        source_filter,
        "|".join(sorted(map(str, pgd_values))),
        "|".join(sorted(map(str, xa_values))),
        "|".join(sorted(map(str, ct_values))),
        "|".join(sorted(map(str, sheet_names))),
    ]
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:12]


def _loc_du_lieu_xuat_theo_dieu_kien(
    df_labeled: pd.DataFrame,
    source_filter: str = _EXPORT_SOURCE_ALL,
    pgd_values: list[str] | tuple[str, ...] = (),
    xa_values: list[str] | tuple[str, ...] = (),
    ct_values: list[str] | tuple[str, ...] = (),
) -> pd.DataFrame:
    """Lọc dữ liệu phục vụ xuất Excel/PDF theo nhiều điều kiện độc lập."""
    if df_labeled is None or df_labeled.empty:
        return pd.DataFrame()
    df_out = df_labeled.copy()
    if "_nv_label" not in df_out.columns or "_nv_cap_label" not in df_out.columns:
        df_out = _phan_nguon_von(df_out)

    if source_filter == _EXPORT_SOURCE_DP:
        df_out = df_out[df_out["_nv_label"].eq("Địa phương")]
    elif source_filter == _EXPORT_SOURCE_DP_TINH:
        df_out = df_out[df_out["_nv_cap_label"].eq("ĐP cấp tỉnh")]
    elif source_filter == _EXPORT_SOURCE_DP_XA:
        df_out = df_out[df_out["_nv_cap_label"].eq("ĐP cấp xã/khác")]
    elif source_filter == _EXPORT_SOURCE_TW:
        df_out = df_out[df_out["_nv_label"].eq("Trung ương")]

    for col, values in (
        (COT_TEN_PGD, pgd_values),
        (COT_TEN_XA, xa_values),
        (COT_TEN_CT, ct_values),
    ):
        selected = {_text_sach(v) for v in values}
        selected.discard("")
        if selected and col in df_out.columns:
            df_out = df_out[df_out[col].map(_text_sach).isin(selected)]

    return df_out


def _export_options_from_col(df: pd.DataFrame, col: str) -> list[str]:
    if df is None or df.empty or col not in df.columns:
        return []
    values = [_text_sach(v) for v in df[col].dropna().tolist()]
    return sorted({v for v in values if v})


def _phan_nguon_von(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm nhãn nguồn vốn tổng và nhãn phân cấp ĐP từ Mã nhà đầu tư (vectorized)."""
    if {"_nv_label", "_nv_cap_label"}.issubset(df.columns):
        return df
    if COT_NGUON_VON not in df.columns:
        df = df.copy()
        df["_nv_label"] = "Không rõ"
        df["_nv_cap_label"] = "Không rõ"
        return df
    df = df.copy()
    if "_nv_label" not in df.columns:
        df["_nv_label"] = _nguon_von_label_series(df[COT_NGUON_VON])
    df["_nv_cap_label"] = df["_nv_label"]
    mask_dp = df["_nv_label"].eq("Địa phương")
    if not mask_dp.any():
        return df

    exact, fallback = _rule_cap_lookup()
    idx_dp = df.index[mask_dp]
    if COT_MA_CHUONG_TRINH in df.columns:
        ma_ct_i = _ma_ct_series_int(df.loc[idx_dp, COT_MA_CHUONG_TRINH], idx_dp)
    else:
        ma_ct_i = _ma_ct_series_int(None, idx_dp)
    if COT_MA_NHA_DAU_TU in df.columns:
        ma_txt = _text_sach_series(df.loc[idx_dp, COT_MA_NHA_DAU_TU])
    else:
        ma_txt = pd.Series([""] * len(idx_dp), index=idx_dp)

    # Ưu tiên rule exact (Mã CT + Mã NĐT) → fallback (Mã NĐT) → mặc định "xa".
    # Trống Mã NĐT → luôn "ĐP cấp xã/khác" (giữ đúng logic per-row cũ).
    exact_str = {f"{ct}|{ma}": cap for (ct, ma), cap in exact.items()}
    cap = (ma_ct_i.astype(str) + "|" + ma_txt).map(exact_str)
    cap = cap.fillna(ma_txt.map(fallback)).fillna("xa").mask(ma_txt.eq(""), "xa")
    df.loc[idx_dp, "_nv_cap_label"] = cap.eq("tinh").map(
        {True: "ĐP cấp tỉnh", False: "ĐP cấp xã/khác"}
    )
    return df


@st.cache_data(show_spinner=False)
def _nhan_nv_numeric(_df: pd.DataFrame, cache_key: str) -> tuple[pd.DataFrame, "pd.Series"]:
    """Pre-label + pre-convert dư nợ → (df_labeled, dn_series). Cache theo cache_key."""
    df_labeled = _phan_nguon_von(_df)
    dn = pd.to_numeric(df_labeled[COT_TONG_DU_NO], errors="coerce").fillna(0.0)
    return df_labeled, dn


def _bang_theo_nv(
    df: pd.DataFrame,
    nhom_col: str,
    extra_cols: list[str] | None = None,
    df_labeled: pd.DataFrame | None = None,
    them_dong_tong: bool = False,
) -> pd.DataFrame:
    """Bảng tổng hợp theo nhóm: TW dư nợ | ĐP dư nợ | Tỷ trọng ĐP%.

    Args:
        df_labeled: Pre-labeled df (tránh gọi lại _phan_nguon_von).
    """
    if nhom_col not in df.columns or COT_TONG_DU_NO not in df.columns:
        return pd.DataFrame()

    if df_labeled is not None and "_nv_label" in df_labeled.columns:
        df_work = df_labeled
    else:
        df_work = _phan_nguon_von(df)

    idx_cols = [nhom_col] + [c for c in (extra_cols or []) if c in df_work.columns]

    # Vectorized: group by nhom + cap_label, sum dư nợ, unstack cap_label thành cột
    df_agg = df_work[idx_cols + ["_nv_cap_label"]].copy()
    df_agg["_dn"] = pd.to_numeric(df_work[COT_TONG_DU_NO], errors="coerce").fillna(0.0).values

    pivot = (
        df_agg.groupby(idx_cols + ["_nv_cap_label"])["_dn"]
        .sum()
        .unstack("_nv_cap_label")
        .fillna(0.0)
        .reset_index()
    )
    pivot.columns.name = None

    for col in ("Trung ương", "ĐP cấp tỉnh", "ĐP cấp xã/khác"):
        if col not in pivot.columns:
            pivot[col] = 0.0

    pivot["Địa phương"] = pivot["ĐP cấp tỉnh"] + pivot["ĐP cấp xã/khác"]
    pivot["_tong"] = pivot["Trung ương"] + pivot["Địa phương"]

    result = pivot.sort_values("_tong", ascending=False).reset_index(drop=True)
    if result.empty:
        return result

    result["Tỷ trọng ĐP (%)"] = result.apply(
        lambda r: r["Địa phương"] / r["_tong"] * 100
        if r["_tong"] > 0 else 0.0,
        axis=1,
    )

    result = result.sort_values("_tong", ascending=False).reset_index(drop=True)
    if them_dong_tong:
        tong_row = {col: "" for col in idx_cols}
        tong_row[idx_cols[0]] = "Tổng cộng"
        for col in ["Trung ương", "ĐP cấp tỉnh", "ĐP cấp xã/khác", "Địa phương", "_tong"]:
            tong_row[col] = result[col].sum()
        tong_row["Tỷ trọng ĐP (%)"] = (
            tong_row["Địa phương"] / tong_row["_tong"] * 100
            if tong_row["_tong"] > 0 else 0.0
        )
        result = pd.concat([result, pd.DataFrame([tong_row])], ignore_index=True)

    result["TW (triệu đồng)"] = result["Trung ương"].apply(fmt_ty)
    result["ĐP cấp tỉnh (triệu đồng)"] = result["ĐP cấp tỉnh"].apply(fmt_ty)
    result["ĐP cấp xã/khác (triệu đồng)"] = result["ĐP cấp xã/khác"].apply(fmt_ty)
    result["Tổng dư nợ ĐP (triệu đồng)"] = result["Địa phương"].apply(fmt_ty)
    result["Tổng (triệu đồng)"] = result["_tong"].apply(fmt_ty)
    result["Tỷ trọng ĐP (%)"] = result["Tỷ trọng ĐP (%)"].apply(
        lambda x: f"{x:.1f}".replace(".", ",") + "%"
    )

    display_cols = idx_cols + [
        "TW (triệu đồng)",
        "ĐP cấp tỉnh (triệu đồng)", "ĐP cấp xã/khác (triệu đồng)",
        "Tổng dư nợ ĐP (triệu đồng)",
    ]
    display_cols += ["Tổng (triệu đồng)", "Tỷ trọng ĐP (%)"]
    return result[[c for c in display_cols if c in result.columns]]


def _ten_don_vi_ngan(value) -> str:
    text = _text_sach(value)
    if text == DON_VI_CHI_NHANH:
        return "Hội sở tỉnh"
    if text.startswith("PGD "):
        return text[4:].strip()
    return text


def _ordered_units(values: pd.Series) -> list[str]:
    existing = [_text_sach(v) for v in values.dropna().tolist()]
    existing_set = {v for v in existing if v}
    preferred = [DON_VI_CHI_NHANH] + list(DS_PGD)
    ordered = [v for v in preferred if v in existing_set]
    ordered.extend(sorted(existing_set - set(ordered)))
    return ordered


def _bang_nguon_von_xa_02_ct(
    df: pd.DataFrame,
    df_labeled: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Bảng đối chiếu GQVL/NSVSMT dùng nguồn ngân sách cấp xã nhận ủy thác."""
    required = {COT_TEN_PGD, COT_MA_CHUONG_TRINH, COT_TONG_DU_NO}
    if df is None or df.empty or not required.issubset(df.columns):
        return pd.DataFrame()

    if df_labeled is not None and {"_nv_label", "_nv_cap_label"}.issubset(df_labeled.columns):
        df_work = df_labeled
    else:
        df_work = _phan_nguon_von(df)

    ma_ct = _ma_ct_series_int(df_work[COT_MA_CHUONG_TRINH], df_work.index)
    dn = pd.to_numeric(df_work[COT_TONG_DU_NO], errors="coerce").fillna(0.0)
    mask = (
        df_work["_nv_label"].eq("Địa phương")
        & df_work["_nv_cap_label"].eq("ĐP cấp xã/khác")
        & ma_ct.isin([3, 6])
    )

    rows = df_work.loc[mask, [COT_TEN_PGD]].copy()
    rows["_ma_ct"] = ma_ct.loc[mask].astype(int)
    rows["_dn"] = dn.loc[mask].values

    units = _ordered_units(df_work[COT_TEN_PGD])
    if not units:
        return pd.DataFrame()

    if rows.empty:
        pivot = pd.DataFrame(0.0, index=units, columns=[3, 6])
    else:
        pivot = (
            rows.groupby([COT_TEN_PGD, "_ma_ct"])["_dn"]
            .sum()
            .unstack("_ma_ct")
            .reindex(units)
            .fillna(0.0)
        )
        for col in (3, 6):
            if col not in pivot.columns:
                pivot[col] = 0.0
        pivot = pivot[[3, 6]]

    out = pd.DataFrame(
        {
            "STT": range(1, len(pivot) + 1),
            "Đơn vị": [_ten_don_vi_ngan(v) for v in pivot.index],
            "GQVL nguồn vốn xã": pivot[3].astype(float).values,
            "NS&VSMTNT nguồn vốn xã": pivot[6].astype(float).values,
        }
    )
    out["Tổng cộng"] = out["GQVL nguồn vốn xã"] + out["NS&VSMTNT nguồn vốn xã"]

    total = {
        "STT": "",
        "Đơn vị": "Tổng cộng",
        "GQVL nguồn vốn xã": out["GQVL nguồn vốn xã"].sum(),
        "NS&VSMTNT nguồn vốn xã": out["NS&VSMTNT nguồn vốn xã"].sum(),
        "Tổng cộng": out["Tổng cộng"].sum(),
    }
    out = pd.concat([out, pd.DataFrame([total])], ignore_index=True)

    for col in ["GQVL nguồn vốn xã", "NS&VSMTNT nguồn vốn xã", "Tổng cộng"]:
        out[col] = out[col].apply(fmt_ty)
    return out


def _bang_ma_ndt_cho_phan_loai(
    df_labeled: pd.DataFrame,
    dn: pd.Series,
) -> pd.DataFrame:
    """Mã NĐT nguồn ĐP chưa có rule phân cấp (đang mặc định tính vào cấp xã/khác)."""
    required_cols = {COT_MA_NHA_DAU_TU, "_nv_label"}
    if df_labeled is None or df_labeled.empty or not required_cols.issubset(df_labeled.columns):
        return pd.DataFrame()
    mask_dp = df_labeled["_nv_label"].eq("Địa phương")
    if not mask_dp.any():
        return pd.DataFrame()

    rules = db.doc_ndt_dp_rule_list() or []
    rule_mas = {
        _text_sach(r.get("ma", ""))
        for r in rules
        if isinstance(r, dict)
    }
    rule_mas.discard("")

    sub = df_labeled.loc[mask_dp].copy()
    sub["_dn"] = pd.to_numeric(dn.reindex(sub.index), errors="coerce").fillna(0.0).to_numpy()
    sub["_ma_ndt"] = sub[COT_MA_NHA_DAU_TU].map(_text_sach)
    sub = sub[(sub["_ma_ndt"] != "") & (~sub["_ma_ndt"].isin(rule_mas))]
    if sub.empty:
        return pd.DataFrame()

    rows = []
    for ma, g in sub.groupby("_ma_ndt"):
        ct_chinh = ""
        if COT_TEN_CT in g.columns and not g.empty:
            ct_chinh = _text_sach(g.loc[g["_dn"].idxmax(), COT_TEN_CT])
        rows.append(
            {
                "Mã NĐT": ma,
                "Dư nợ (triệu đồng)": fmt_ty(g["_dn"].sum()),
                "Số PGD": g[COT_TEN_PGD].nunique() if COT_TEN_PGD in g.columns else 0,
                "Số xã": g[COT_TEN_XA].nunique() if COT_TEN_XA in g.columns else 0,
                "Chương trình chính": ct_chinh,
                "_dn_sort": float(g["_dn"].sum()),
            }
        )
    out = pd.DataFrame(rows).sort_values("_dn_sort", ascending=False).reset_index(drop=True)
    out.insert(0, "STT", range(1, len(out) + 1))
    return out.drop(columns=["_dn_sort"])


def _dem_nguon_von_nan_co_ma_ndt(df: pd.DataFrame) -> int:
    """Đếm dòng trống cột 'Nguồn vốn' nhưng mang Mã NĐT dạng INV — nghi vốn ĐP thiếu nhãn."""
    if df is None or df.empty:
        return 0
    if COT_NGUON_VON not in df.columns or COT_MA_NHA_DAU_TU not in df.columns:
        return 0
    nv_nan = _text_sach_series(df[COT_NGUON_VON]).eq("")
    ma_inv = _text_sach_series(df[COT_MA_NHA_DAU_TU]).str.upper().str.startswith("INV")
    return int((nv_nan & ma_inv).sum())


@st.cache_data(show_spinner=False)
def _cached_bang_ma_ndt_cho_phan_loai(
    _df_labeled: pd.DataFrame,
    _dn: pd.Series,
    cache_key: str,
) -> pd.DataFrame:
    """Cache bảng Mã NĐT chờ phân loại; bảng này chỉ đổi khi HSTD/rules/filter đổi."""
    _ = cache_key
    return _bang_ma_ndt_cho_phan_loai(_df_labeled, _dn)


@st.cache_data(show_spinner=False)
def _cached_dem_nguon_von_nan_co_ma_ndt(
    _df: pd.DataFrame,
    cache_key: str,
) -> int:
    """Cache kiểm tra INV thiếu nguồn vốn; phụ thuộc HSTD/filter hiện tại."""
    _ = cache_key
    return _dem_nguon_von_nan_co_ma_ndt(_df)


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


def _render_sub_pgd(
    df: pd.DataFrame,
    df_labeled: pd.DataFrame | None = None,
) -> None:
    df_pgd_hien = _bang_theo_nv(
        df, COT_TEN_PGD, df_labeled=df_labeled, them_dong_tong=True
    )
    if df_pgd_hien.empty:
        st.warning("Không có dữ liệu PGD.")
        return
    df_pgd = df_pgd_hien.iloc[:-1]  # exclude "Tổng cộng" row for chart
    _ve_bieu_do_ngang(df_pgd, COT_TEN_PGD, "Tỷ trọng vốn Địa phương theo PGD", "nvdp_pgd_chart")
    st.markdown("**Bảng chi tiết theo PGD**")
    hien_thi_dataframe_phan_trang(df_pgd_hien, key="nvdp_pgd_table", height=480)


def _render_sub_xa(df: pd.DataFrame, kp: str = "", df_labeled: pd.DataFrame | None = None) -> None:
    df_xa = _bang_theo_nv(df, COT_TEN_XA, extra_cols=[COT_TEN_PGD], df_labeled=df_labeled)
    if df_xa.empty:
        st.warning("Không có dữ liệu Xã.")
        return
    df_top = df_xa.copy()
    df_top["_pct"] = df_top["Tỷ trọng ĐP (%)"].str.replace(",", ".").str.rstrip("%").astype(float)
    df_top = df_top.sort_values("_pct", ascending=False).head(20)
    _ve_bieu_do_ngang(df_top, COT_TEN_XA, "Top 20 Xã — Tỷ trọng vốn Địa phương cao nhất", f"{kp}nvdp_xa_chart")
    st.markdown("**Bảng chi tiết theo Xã**")
    hien_thi_dataframe_phan_trang(df_xa, key=f"{kp}nvdp_xa_table", height=480)


def _render_sub_ct(df: pd.DataFrame, kp: str = "", df_labeled: pd.DataFrame | None = None) -> None:
    df_ct = _bang_theo_nv(df, COT_TEN_CT, df_labeled=df_labeled)
    if df_ct.empty:
        st.warning("Không có dữ liệu Chương trình.")
        return
    _ve_bieu_do_ngang(df_ct, COT_TEN_CT, "Tỷ trọng vốn Địa phương theo Chương trình tín dụng", f"{kp}nvdp_ct_chart")
    st.markdown("**Bảng chi tiết theo Chương trình**")
    hien_thi_dataframe_phan_trang(df_ct, key=f"{kp}nvdp_ct_table", height=480)


# ── Cache snapshot context ────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=600)
def _load_snapshot_context(cache_key: str) -> dict:
    """Cache snapshot context: ky_list, df_prev, prev_label. TTL 10 phút."""
    ky_list = danh_sach_ky()
    ctx: dict = {"ky_list": ky_list, "df_prev": pd.DataFrame(), "prev_label": "so với kỳ trước"}

    if not ky_list:
        return ctx

    prev_ky = ky_baseline(ky_list, ky_list[0]) or (ky_list[1] if len(ky_list) > 1 else None)
    if prev_ky and prev_ky != ky_list[0]:
        ky_parts = prev_ky.split("-")
        ctx["prev_label"] = f"so baseline T{ky_parts[1]}/{ky_parts[0]}"
        ctx["df_prev"] = doc_snapshot_nvdp_range(prev_ky, prev_ky)

    return ctx


# ── KH tín dụng ĐP theo PGD (Nhóm A: KH vs Thực tế) ──────────────────────────

def _kh_dp_cua_pgd(ten_pgd: str, kh_map: dict[str, float]) -> float:
    """Tra KH ĐP (VND) theo tên PGD; slug Hội sở trong KHTD là 'hoi_so'."""
    slug = pgd_slug(ten_pgd)
    kh = kh_map.get(slug)
    if kh is None and slug.startswith("hoi_so"):
        kh = kh_map.get("hoi_so")
    return float(kh or 0.0)


def _khtd_dot_sort_key(dot: str) -> tuple[int | str, ...]:
    s = str(dot).strip()
    m = re.match(r"(?i)dot\s*(\d+)$", s)
    if m:
        return (0, int(m.group(1)))
    return (1, s.lower())


def _is_khtd_timestamp_dot(dot: str) -> bool:
    return bool(re.search(r"_\d{8}T\d{6}$", str(dot or "").strip()))


def _parse_khtd_period_key(key: str, slugs: list[str]) -> tuple[int, str, str] | None:
    """Parse khtd_{slug}_{YYYY}_{MM}_{dot}; slug/dot đều có thể chứa underscore."""
    text = str(key or "")
    if not text.startswith("khtd_"):
        return None
    for slug in sorted(slugs, key=len, reverse=True):
        prefix = f"khtd_{slug}_"
        if not text.startswith(prefix):
            continue
        suffix = text[len(prefix):].strip()
        m = re.match(r"^(\d{4})_(\d{2})_(.+)$", suffix)
        if not m:
            return None
        return int(m.group(1)), m.group(2), m.group(3).strip()
    return None


@st.cache_data(show_spinner=False, ttl=300)
def _doc_kh_dp_theo_pgd() -> tuple[str, dict]:
    """KH ĐP mới nhất theo PGD từ các đợt KHTD đã giao (kv_store).

    Trả về (nhãn đợt, {pgd_slug: kh_moi_dp_vnd}); ("", {}) nếu chưa có đợt nào.
    """
    try:
        from services import khtd_service

        # Quét khóa khtd_{slug}_{năm}_{tháng}_{đợt}; slug và đợt có thể chứa underscore.
        slugs = (
            khtd_service.ds_slug()
            if hasattr(khtd_service, "ds_slug")
            else ["hoi_so"] + [pgd_slug(ten) for ten in DS_PGD]
        )
        periods: dict[tuple, int] = {}
        for k in db.list_kv_prefix("khtd_"):
            p = _parse_khtd_period_key(k, slugs)
            if p is None:
                continue
            if _is_khtd_timestamp_dot(p[2]):
                continue
            periods[p] = periods.get(p, 0) + 1
        if not periods:
            return "", {}
        nam, th, dot = max(
            periods, key=lambda p: (p[0], p[1], _khtd_dot_sort_key(p[2]))
        )
        df = khtd_service.tong_hop(nam, th, dot)
        if df is None or df.empty:
            return "", {}
        df = df[df["ma_key"].astype(str).str.contains("_DP", na=False)].copy()
        if df.empty:
            return "", {}
        df["kh_moi_dp"] = pd.to_numeric(df["kh_moi_dp"], errors="coerce").fillna(0.0)
        kh = df.groupby("pgd_slug")["kh_moi_dp"].sum()
        kh = kh[kh > 0]
        if kh.empty:
            return "", {}
        return f"đợt {dot}, {th}/{nam}", kh.to_dict()
    except Exception as e:
        logger.error("_doc_kh_dp_theo_pgd: %s", e, exc_info=True)
    return "", {}


# ── Cache Excel export ────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cached_bao_cao_sheets(
    _df_labeled: pd.DataFrame,
    is_pgd_view: bool,
    extra_cols: tuple[str, ...],
    sheet_names: tuple[str, ...] = (),
    view_key: str = "cn",
    ts: float = 0.0,
    rules_key: str = "",
    nhan_dot: str = "",
    kh_sig: str = "",
) -> dict[str, pd.DataFrame]:
    """Cache các bảng báo cáo — dùng chung cho xuất Excel và PDF."""
    _ = (view_key, ts, rules_key, nhan_dot, kh_sig)
    wanted = set(sheet_names)
    sheets: dict[str, pd.DataFrame] = {
        _EXPORT_SHEET_XA_02_CT: _bang_nguon_von_xa_02_ct(_df_labeled, df_labeled=_df_labeled),
        _EXPORT_SHEET_CT: _bang_theo_nv(_df_labeled, COT_TEN_CT, df_labeled=_df_labeled),
        _EXPORT_SHEET_XA: _bang_theo_nv(_df_labeled, COT_TEN_XA, extra_cols=list(extra_cols), df_labeled=_df_labeled),
    }
    if not is_pgd_view:
        sheets[_EXPORT_SHEET_PGD] = _bang_theo_nv(
            _df_labeled, COT_TEN_PGD, df_labeled=_df_labeled,
            them_dong_tong=True,
        )
    if wanted:
        sheets = {name: data for name, data in sheets.items() if name in wanted}
    return {name: data for name, data in sheets.items() if isinstance(data, pd.DataFrame) and not data.empty}


@st.cache_data(show_spinner=False)
def _cached_excel_sheets(
    _df_labeled: pd.DataFrame,
    is_pgd_view: bool,
    extra_cols: tuple[str, ...],
    sheet_names: tuple[str, ...] = (),
    view_key: str = "cn",
    ts: float = 0.0,
    rules_key: str = "",
    nhan_dot: str = "",
    kh_sig: str = "",
) -> bytes:
    """Cache Excel export — tránh tính lại bảng mỗi lần tải."""
    sheets = _cached_bao_cao_sheets(
        _df_labeled, is_pgd_view, extra_cols, sheet_names, view_key, ts, rules_key, nhan_dot, kh_sig
    )
    if not sheets:
        raise RuntimeError("Không có bảng dữ liệu phù hợp điều kiện xuất.")
    return xuat_excel(sheets)


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df_full = kwargs.get("df_full")
    pgd_user = kwargs.get("pgd_user", "")
    ts_hstd = float(kwargs.get("ts_hstd", 0.0))

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

        # ── PRE-COMPUTE (1 lần duy nhất cho toàn bộ render) ──────────────────
        rules_key = _rules_cache_key(db.doc_ndt_dp_rule_list())
        nv_cache_key = f"{'pgd' if pgd_user else 'cn'}_{selected_pgd or 'all'}_{ts_hstd}_{rules_key}"
        df_labeled, dn_series = _nhan_nv_numeric(df_display, nv_cache_key)
        mask_tw = df_labeled["_nv_label"] == "Trung ương"
        mask_dp = df_labeled["_nv_label"] == "Địa phương"
        mask_dp_tinh = df_labeled["_nv_cap_label"] == "ĐP cấp tỉnh"
        mask_dp_xa = df_labeled["_nv_cap_label"] == "ĐP cấp xã/khác"
        tong_du_no = float(dn_series.sum())
        dn_tw = float(dn_series[mask_tw].sum())
        dn_dp = float(dn_series[mask_dp].sum())
        dn_dp_tinh = float(dn_series[mask_dp_tinh].sum())
        dn_dp_xa = float(dn_series[mask_dp_xa].sum())
        tl_dp = dn_dp / tong_du_no * 100 if tong_du_no > 0 else 0.0

        # KH ĐP theo đợt KHTD gần nhất (Nhóm A: KH vs Thực tế)
        nhan_dot_kh, kh_map = _doc_kh_dp_theo_pgd()
        if kh_map:
            if pgd_user or selected_pgd:
                kh_dp_view = _kh_dp_cua_pgd(str(pgd_user or selected_pgd), kh_map)
            else:
                kh_dp_view = float(sum(kh_map.values()))
            dat_kh = dn_dp / kh_dp_view * 100 if kh_dp_view > 0 else None
        else:
            dat_kh = None

        # Delta từ snapshot — chỉ khi xem toàn CN (không filter PGD)
        delta_tong = delta_tw = delta_dp = delta_tl = None
        prev_label = "so với kỳ trước"

        if not pgd_user and selected_pgd is None:
            snap_ctx = _load_snapshot_context(f"nvdp_{ts_hstd}")
            prev_label = snap_ctx["prev_label"]
            df_prev = snap_ctx["df_prev"]
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
                    "label": "ĐP cấp tỉnh",
                    "value": fmt_ty(dn_dp_tinh),
                    "suffix": "tr.đ",
                    "help": "Dư nợ nguồn ĐP có Mã nhà đầu tư được rule phân loại cấp tỉnh.",
                    "icon": "🏛️",
                },
                {
                    "label": "ĐP cấp xã/khác",
                    "value": fmt_ty(dn_dp_xa),
                    "suffix": "tr.đ",
                    "help": "Dư nợ nguồn ĐP có Mã nhà đầu tư thuộc cấp xã/khác hoặc chưa có rule cấp tỉnh.",
                    "icon": "🏘️",
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
            num_columns=3,
        )
        if dat_kh is not None:
            kpi_row(
                [
                    {
                        "label": f"Đạt KH ĐP — {nhan_dot_kh}",
                        "value": f"{dat_kh:.1f}".replace(".", ",") + "%",
                        "help": (
                            "Dư nợ Địa phương thực tế / KH ĐP được giao "
                            f"theo {nhan_dot_kh} (KHTD phần vốn Địa phương)."
                        ),
                        "icon": "🎯",
                        "precision": 1,
                    },
                ],
                num_columns=3,
            )

        st.divider()

        is_pgd_view = bool(pgd_user or selected_pgd)
        view_key = selected_pgd or pgd_user or "cn"
        kp = f"pgd_" if is_pgd_view else ""
        extra_cols_tuple = (COT_TEN_PGD,) if COT_TEN_PGD in df_display.columns else ()

        if st.toggle(
            "Hiện kiểm tra Mã NĐT & chất lượng dữ liệu",
            value=False,
            key=f"{kp}nvdp_show_data_quality",
        ):
            df_cho_pl = _cached_bang_ma_ndt_cho_phan_loai(df_labeled, dn_series, nv_cache_key)
            n_nan_inv = _cached_dem_nguon_von_nan_co_ma_ndt(df_display, nv_cache_key)
            st.markdown(f"**🔎 Mã NĐT chờ phân loại & kiểm tra chất lượng dữ liệu ({len(df_cho_pl)} mã)**")
            if not df_cho_pl.empty:
                st.caption(
                    "Các Mã NĐT dưới đây thuộc nguồn Địa phương nhưng **chưa có rule phân cấp**, "
                    "đang được tính mặc định vào **ĐP cấp xã/khác**."
                )
                hien_thi_dataframe_phan_trang(
                    df_cho_pl, key=f"{kp}nvdp_ma_ndt_cho_pl", height=360
                )
                st.info(
                    "Nếu mã nào là vốn **cấp tỉnh** ủy thác, hãy thêm rule tương ứng trong tab "
                    "**Mã NĐT địa phương** để số liệu ĐP cấp tỉnh/xã chính xác."
                )
            if n_nan_inv > 0:
                st.warning(
                    f"⚠️ Có **{n_nan_inv}** dòng trống cột 'Nguồn vốn' nhưng mang Mã NĐT dạng INV — "
                    "có thể là vốn Địa phương bị thiếu nhãn. Vui lòng kiểm tra lại file HSTD gốc."
                )
            if df_cho_pl.empty and n_nan_inv == 0:
                st.success("Không phát hiện Mã NĐT chờ phân loại hoặc dòng INV thiếu nguồn vốn.")
            st.divider()

        # ── Sub-tabs phân tích ────────────────────────────────────────────────
        if is_pgd_view:
            lazy_tabs(
                ["🗺️ Theo Xã", "📌 Theo Chương trình"],
                [
                    lambda: (
                        st.warning("Không tìm thấy cột Tên Xã trong dữ liệu.")
                        if COT_TEN_XA not in df_display.columns
                        else _render_sub_xa(df_display, kp, df_labeled=df_labeled)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
                        if COT_TEN_CT not in df_display.columns
                        else _render_sub_ct(df_display, kp, df_labeled=df_labeled)
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
                        else _render_sub_pgd(
                            df_display, df_labeled=df_labeled,
                        )
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên Xã trong dữ liệu.")
                        if COT_TEN_XA not in df_display.columns
                        else _render_sub_xa(df_display, kp, df_labeled=df_labeled)
                    ),
                    lambda: (
                        st.warning("Không tìm thấy cột Tên chương trình trong dữ liệu.")
                        if COT_TEN_CT not in df_display.columns
                        else _render_sub_ct(df_display, kp, df_labeled=df_labeled)
                    ),
                ],
                key="nvdp_sub_cn",
            )

        # ── Xuất báo cáo (on-demand — chỉ tính khi bấm nút, tránh eager) ────
        st.divider()
        st.markdown("**📥 Xuất báo cáo — Nguồn vốn địa phương**")

        sheet_options = _export_sheet_options(is_pgd_view)
        sheet_key = f"{kp}nvdp_export_sheets"
        if sheet_key in st.session_state:
            st.session_state[sheet_key] = _clean_selected_options(st.session_state[sheet_key], sheet_options)

        with st.expander("Điều kiện xuất báo cáo", expanded=True):
            c_filter_1, c_filter_2 = st.columns(2)
            with c_filter_1:
                source_filter = st.selectbox(
                    "Nguồn vốn",
                    _EXPORT_SOURCE_OPTIONS,
                    key=f"{kp}nvdp_export_source",
                )
            with c_filter_2:
                selected_sheet_names = st.multiselect(
                    "Bảng đưa vào file",
                    sheet_options,
                    default=sheet_options,
                    key=sheet_key,
                    help="Có thể chọn một hoặc nhiều bảng. Bỏ hết lựa chọn thì chưa tạo file.",
                )

            c_filter_3, c_filter_4, c_filter_5 = st.columns(3)
            with c_filter_3:
                pgd_export = []
                if not is_pgd_view:
                    pgd_export = st.multiselect(
                        "PGD",
                        _export_options_from_col(df_labeled, COT_TEN_PGD),
                        key=f"{kp}nvdp_export_pgd",
                        help="Để trống là xuất tất cả PGD trong phạm vi đang xem.",
                    )
            with c_filter_4:
                xa_export = st.multiselect(
                    "Xã/Phường",
                    _export_options_from_col(df_labeled, COT_TEN_XA),
                    key=f"{kp}nvdp_export_xa",
                    help="Để trống là xuất tất cả xã/phường trong phạm vi đang xem.",
                )
            with c_filter_5:
                ct_export = st.multiselect(
                    "Chương trình",
                    _export_options_from_col(df_labeled, COT_TEN_CT),
                    key=f"{kp}nvdp_export_ct",
                    help="Để trống là xuất tất cả chương trình trong phạm vi đang xem.",
                )

        df_export = _loc_du_lieu_xuat_theo_dieu_kien(
            df_labeled,
            source_filter=source_filter,
            pgd_values=pgd_export,
            xa_values=xa_export,
            ct_values=ct_export,
        )
        if not selected_sheet_names:
            st.warning("Chọn ít nhất một bảng để tạo file báo cáo.")
        elif df_export.empty:
            st.warning("Không có dữ liệu phù hợp với điều kiện xuất đã chọn.")
        else:
            st.caption(
                f"Dữ liệu xuất: {len(df_export):,} dòng · "
                f"{len(selected_sheet_names)} bảng · {source_filter}"
            )

        today_str = date.today().strftime("%d/%m/%Y")
        today_file = date.today().strftime("%Y%m%d")
        kh_sig = _kh_map_cache_key(nhan_dot_kh, kh_map)
        sheet_names_tuple = tuple(selected_sheet_names)
        condition_sig = _export_condition_key(
            source_filter,
            pgd_export,
            xa_export,
            ct_export,
            sheet_names_tuple,
        )
        export_sig = f"{kh_sig}|{condition_sig}"
        excel_state_key = _excel_state_key(view_key, ts_hstd, rules_key, export_sig)
        pdf_state_key = f"{_PDF_STATE_PREFIX}{view_key}_{ts_hstd}_{condition_sig}"

        tieu_de_pdf = "BÁO CÁO TỶ TRỌNG VỐN ỦY THÁC ĐỊA PHƯƠNG"
        tieu_de_pdf += f" — {view_key}" if is_pgd_view else " — TOÀN CHI NHÁNH"

        col_excel, col_pdf = st.columns(2)

        with col_excel:
            if st.button(
                "📊 Tạo báo cáo Excel",
                key="nvdp_tao_excel",
                disabled=not selected_sheet_names or df_export.empty,
            ):
                with st.spinner("Đang tạo báo cáo Excel..."):
                    try:
                        _clear_old_excel_buffers(excel_state_key)
                        st.session_state[excel_state_key] = _cached_excel_sheets(
                            df_export, is_pgd_view, extra_cols_tuple, sheet_names_tuple, view_key, ts_hstd, rules_key,
                            nhan_dot_kh, kh_sig,
                        )
                    except Exception as e:
                        logger.error("tab_hhi export excel: %s", e, exc_info=True)
                        st.warning(f"Không thể tạo đầy đủ file Excel nguồn vốn địa phương: {e}")
                        _clear_old_excel_buffers(excel_state_key)
                        st.session_state[excel_state_key] = xuat_excel(
                            {"Lỗi xuất file": pd.DataFrame({"Lỗi": [str(e)]})}
                        )
            if excel_state_key in st.session_state:
                st.download_button(
                    label=f"⬇️ Tải Excel Nguồn vốn ĐP ({today_str})",
                    data=st.session_state[excel_state_key],
                    file_name=f"NguonVonDiaPhuong_{today_file}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="nvdp_xuat_excel",
                )

        with col_pdf:
            if st.button(
                "📄 Tạo báo cáo PDF",
                key="nvdp_tao_pdf",
                disabled=not selected_sheet_names or df_export.empty,
            ):
                with st.spinner("Đang tạo báo cáo PDF..."):
                    try:
                        _clear_old_pdf_buffers(pdf_state_key)
                        sheets = _cached_bao_cao_sheets(
                            df_export, is_pgd_view, extra_cols_tuple, sheet_names_tuple, view_key, ts_hstd,
                            rules_key, nhan_dot_kh, kh_sig,
                        )
                        if not sheets:
                            raise RuntimeError("Không có bảng dữ liệu phù hợp điều kiện xuất.")
                        pdf_bytes = xuat_pdf_bc(sheets, tieu_de_pdf, ctx.username)
                        if not pdf_bytes:
                            raise RuntimeError("Dịch vụ PDF không trả về dữ liệu.")
                        st.session_state[pdf_state_key] = pdf_bytes
                    except Exception as e:
                        logger.error("tab_hhi export pdf: %s", e, exc_info=True)
                        _clear_old_pdf_buffers(pdf_state_key)
                        st.warning(f"Không thể tạo PDF nguồn vốn địa phương: {e}")
            if pdf_state_key in st.session_state:
                st.download_button(
                    label=f"⬇️ Tải PDF Nguồn vốn ĐP ({today_str})",
                    data=st.session_state[pdf_state_key],
                    file_name=f"NguonVonDiaPhuong_{today_file}.pdf",
                    mime="application/pdf",
                    key="nvdp_xuat_pdf",
                )
