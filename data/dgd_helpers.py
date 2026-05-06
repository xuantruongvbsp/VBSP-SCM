"""Helper dùng chung cho cấu hình ĐGD / dgd_map (Excel, pool thôn, trạng thái map)."""
from __future__ import annotations

import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from config import COT_TEN_PGD, COT_TEN_THON, COT_TEN_XA, PGD_XA_MAP
from data.pgd import duong_dan_pgd
from utils import pick_hstd_column

_COT_TEN_DGD_HSTD = "Tên điểm GD"


def _norm_col_header(s: str) -> str:
    """Giống utils.norm_col_header — NBSP/thin-space → space, strip."""
    return str(s).replace("\u00a0", " ").replace("\u202f", " ").strip()


def dgd_dang_dung_trong_hstd(
    df: pd.DataFrame, ten_pgd: str, ten_xa: str, ten_dgd: str
) -> bool:
    if df is None or df.empty or _COT_TEN_DGD_HSTD not in df.columns:
        return False
    d = df.copy()
    if COT_TEN_PGD in d.columns:
        d = d[d[COT_TEN_PGD] == ten_pgd]
    if "Tên xã" in d.columns:
        d = d[d["Tên xã"] == ten_xa]
    if d.empty:
        return False
    col = d[_COT_TEN_DGD_HSTD].astype(str).str.strip()
    return (col == str(ten_dgd).strip()).any()


def _split_ap_cell(val: Any) -> list[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    s = str(val).strip()
    if not s:
        return []
    parts = re.split(r"\s*,\s*", s)
    return [p.strip() for p in parts if p.strip()]


def parse_excel_import(uploaded: bytes, ten_pgd: str) -> dict[str, dict[str, list[str]]]:
    """Trả về {ten_xa: {ten_dgd: [ap,...]}} cho một PGD."""
    _ = ten_pgd  # PGD do selectbox — cấu trúc dict theo xã
    raw = pd.read_excel(BytesIO(uploaded), header=None)
    if raw.shape[1] < 4:
        raise ValueError("File phải có ít nhất 4 cột (A–D).")
    start = 0
    if raw.shape[0] > 0:
        c0 = str(raw.iloc[0, 0]).strip().lower()
        c1 = str(raw.iloc[0, 1]).strip().lower() if raw.shape[1] > 1 else ""
        if c0 in ("stt", "số tt", "so tt") or "xã" in c1 or "phường" in c1:
            start = 1
    body = raw.iloc[start:, :4].copy()
    body.columns = ["stt", "xa", "dgd", "ap"]

    out: dict[str, dict[str, list[str]]] = {}
    for _, row in body.iterrows():
        ten_xa = str(row["xa"]).strip() if pd.notna(row["xa"]) else ""
        ten_dgd = str(row["dgd"]).strip() if pd.notna(row["dgd"]) else ""
        if not ten_xa or not ten_dgd:
            continue
        ds_ap = _split_ap_cell(row["ap"])
        if ten_xa not in out:
            out[ten_xa] = {}
        if ten_dgd not in out[ten_xa]:
            out[ten_xa][ten_dgd] = []
        seen = set(out[ten_xa][ten_dgd])
        for ap in ds_ap:
            if ap not in seen:
                out[ten_xa][ten_dgd].append(ap)
                seen.add(ap)
    return out


def dem_thong_ke(parsed: dict[str, dict[str, list[str]]]) -> tuple[int, int, int, int]:
    so_xa = len(parsed)
    so_dgd = sum(len(v) for v in parsed.values())
    so_ap = 0
    for xa_d in parsed.values():
        for ds in xa_d.values():
            so_ap += len(ds)
    return 1, so_xa, so_dgd, so_ap


def _collapse_ws(s: str) -> str:
    """Thu gọn khoảng trắng (PGD / địa danh từ Excel)."""
    return re.sub(r"\s+", " ", str(s).strip())


def _norm_pgd_so_sanh(s: str) -> str:
    return _collapse_ws(s).lower()


_XA_PREFIX_RANK = (
    "thị trấn ",
    "thị xã ",
    "phường ",
    "xã ",
)


def _norm_xa_so_sanh(s: str) -> str:
    """
    Chuẩn hóa tên xã để khớp PGD_XA_MAP ('Xã Phước Thái')
    với HSTD ('Phước Thái', 'xã Phước Thái', …).
    """
    t = _collapse_ws(s).lower()
    for prefix in _XA_PREFIX_RANK:
        if t.startswith(prefix):
            t = t[len(prefix) :].strip()
            break
    return _collapse_ws(t)


def _pick_ten_pgd_column(df: pd.DataFrame) -> str | None:
    col = pick_hstd_column(df, COT_TEN_PGD, "Tên PGD")
    if col:
        return col
    for c in df.columns:
        cl = _norm_col_header(str(c)).lower()
        if "tên" in cl and "pgd" in cl:
            return c
    return None


def _pick_ten_xa_column(df: pd.DataFrame) -> str | None:
    col = pick_hstd_column(df, COT_TEN_XA, "Tên xã", "Tên Xã")
    if col:
        return col
    for c in df.columns:
        cl = _norm_col_header(str(c)).lower()
        if "tên" in cl and ("xã" in cl or "phường" in cl):
            return c
    return None


def _pick_ten_thon_column(df: pd.DataFrame) -> str | None:
    col = pick_hstd_column(df, COT_TEN_THON, "Tên Thôn", "Tên thôn")
    if col:
        return col
    for c in df.columns:
        cl = _norm_col_header(str(c)).lower()
        if "tên" in cl and "thôn" in cl:
            return c
    return None


def _gop_thon_tu_bang(
    df: pd.DataFrame,
    ten_pgd: str,
    ten_xa: str,
) -> set[str]:
    """
    Lọc df theo PGD + Xã (strip, case-insensitive) và trả về set tên thôn.
    Tự động tìm cột thôn: "Tên Thôn", "Tên thôn", COT_TEN_THON.
    """
    if df is None or df.empty:
        return set()

    col_pgd = _pick_ten_pgd_column(df)
    col_xa = _pick_ten_xa_column(df)
    col_thon = _pick_ten_thon_column(df)

    if not col_thon:
        return set()

    pgd_sel = _norm_pgd_so_sanh(ten_pgd)
    xa_sel = _norm_xa_so_sanh(ten_xa)

    mask = pd.Series([True] * len(df), index=df.index)
    ser_pgd = (
        df[col_pgd].map(lambda x: _norm_pgd_so_sanh(x) if pd.notna(x) else "")
        if col_pgd
        else None
    )
    ser_xa = (
        df[col_xa].map(lambda x: _norm_xa_so_sanh(x) if pd.notna(x) else "")
        if col_xa
        else None
    )

    if ser_xa is not None:
        mask &= ser_xa == xa_sel
    if ser_pgd is not None:
        mask &= ser_pgd == pgd_sel

    def _tap_thon(m: pd.Series) -> set[str]:
        if not m.any():
            return set()
        ts = df.loc[m, col_thon].dropna().astype(str).str.strip()
        return {t for t in ts if t and t.lower() != "nan"}

    out = _tap_thon(mask)
    # PGD_XA_MAP thường có tiền tố "Xã …" trong khi HSTD chỉ có tên cốt — đã chuẩn hóa;
    # nếu vẫn rỗng (sai khác mã PGD trên một phần dòng), thử chỉ lọc theo xã.
    if not out and ser_xa is not None:
        out = _tap_thon(ser_xa == xa_sel)

    return out


def pool_thon_cho_xa(
    df: pd.DataFrame,
    ten_pgd: str,
    ten_xa: str,
    dgd_map: dict[str, Any],
) -> list[str]:
    """
    Gộp danh sách thôn/ấp từ 3 nguồn:
      1. Thôn đã gán trong dgd_map (PGD → Xã → ĐGD → [Thôn])
      2. DataFrame df truyền vào (có thể rỗng)
      3. File HSTD riêng PGD (parquet hoặc Excel) — luôn chạy để bổ sung
    """
    pool: set[str] = set()

    xa_map = (dgd_map or {}).get(ten_pgd, {}).get(ten_xa, {})
    if not isinstance(xa_map, dict):
        xa_map = {}
    for thon_list in xa_map.values():
        for t in thon_list or []:
            s = str(t).strip()
            if s and s.lower() != "nan":
                pool.add(s)

    pool |= _gop_thon_tu_bang(df, ten_pgd, ten_xa)

    try:
        path_excel = Path(duong_dan_pgd(ten_pgd, "hstd"))
        path_parquet = path_excel.with_suffix(".parquet")
        if path_parquet.exists():
            df_pgd = pd.read_parquet(path_parquet, engine="pyarrow")
            pool |= _gop_thon_tu_bang(df_pgd, ten_pgd, ten_xa)
        elif path_excel.exists():
            df_pgd = pd.read_excel(
                path_excel,
                sheet_name="BCQUERY",
                header=4,
                engine="openpyxl",
            ).iloc[:, 1:].dropna(how="all")
            pool |= _gop_thon_tu_bang(df_pgd, ten_pgd, ten_xa)
    except Exception as e:
        # Không fatal — fallback pool không gồm file PGD; log để debug đọc file.
        logging.warning(
            "[pool_thon] Không đọc được file HSTD PGD %s: %s",
            ten_pgd,
            e,
        )

    return sorted(pool)


def trang_thai_pgd_vs_map(
    ten_pgd: str, dgd_map: dict[str, Any]
) -> tuple[str, str]:
    ds_xa_cfg = PGD_XA_MAP.get(ten_pgd, [])
    if not ds_xa_cfg:
        return "—", "⚠️ Không có trong PGD_XA_MAP"
    block = dgd_map.get(ten_pgd, {})
    if not isinstance(block, dict) or not block:
        return "⚠️ Chưa cấu hình", "Chưa có dgd_map"
    thieu = [xa for xa in ds_xa_cfg if xa not in block]
    if thieu:
        return "⚠️ Chưa cấu hình", f"Thiếu xã: {', '.join(thieu[:5])}" + (
            "…" if len(thieu) > 5 else ""
        )
    for xa in ds_xa_cfg:
        dct = block.get(xa, {})
        if not isinstance(dct, dict) or not dct:
            return "⚠️ Chưa cấu hình", f"Xã {xa} chưa có ĐGD"
    return "✅ Đầy đủ", ""
