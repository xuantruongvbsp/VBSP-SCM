"""Phân loại khách hàng theo mức độ rủi ro dựa trên dư nợ và lịch sử."""
from __future__ import annotations
import pandas as pd
from config import (
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH,
    COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
)

PHAN_LOAI_LABELS = {
    "A": ("Loai A - Tot",      "#10b981", "NQH = 0, khong co no khoanh"),
    "B": ("Loai B - Binh thuong", "#f59e0b", "NQH < 3% hoac no khoanh < 10%"),
    "C": ("Loai C - Chu y",     "#f97316", "NQH 3-15% hoac no khoanh 10-30%"),
    "D": ("Loai D - Rui ro",    "#ef4444", "NQH > 15% hoac no khoanh > 30%"),
}


def phan_loai_khach_hang(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm cột __phan_loai (A/B/C/D) vào DataFrame HSTD."""
    df = df.copy()
    dn = pd.to_numeric(df.get(COT_TONG_DU_NO, 0), errors="coerce").fillna(0)
    qh = pd.to_numeric(df.get(COT_DU_NO_QH, 0), errors="coerce").fillna(0)
    kh = pd.to_numeric(df.get(COT_DU_NO_KHOANH, 0), errors="coerce").fillna(0)

    tl_nqh    = qh / dn.replace(0, float("nan")) * 100
    tl_khoanh = kh / dn.replace(0, float("nan")) * 100

    def _xep_loai(row_idx: int) -> str:
        nqh_val = tl_nqh.iloc[row_idx]
        khoanhp_val = tl_khoanh.iloc[row_idx]
        nqh     = nqh_val     if not pd.isna(nqh_val)     else 0.0
        khoanhp = khoanhp_val if not pd.isna(khoanhp_val) else 0.0
        if nqh == 0 and khoanhp == 0:
            return "A"
        if nqh < 3 and khoanhp < 10:
            return "B"
        if nqh <= 15 and khoanhp <= 30:
            return "C"
        return "D"

    df["__phan_loai"] = [_xep_loai(i) for i in range(len(df))]
    return df


def thong_ke_phan_loai(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp phân loại theo PGD."""
    if "__phan_loai" not in df.columns:
        df = phan_loai_khach_hang(df)
    if COT_TEN_PGD not in df.columns:
        return pd.DataFrame()

    agg_kw: dict
    if COT_MA_KH in df.columns:
        agg_kw = {
            "so_kh":   (COT_MA_KH, "nunique"),
            "tong_dn": (COT_TONG_DU_NO, "sum"),
        }
    else:
        agg_kw = {
            "so_kh":   (COT_SO_KU, "count"),
            "tong_dn": (COT_TONG_DU_NO, "sum"),
        }

    result = (
        df.groupby([COT_TEN_PGD, "__phan_loai"])
        .agg(**agg_kw)
        .reset_index()
        .rename(columns={
            "__phan_loai": "Phan loai",
            COT_TEN_PGD:   "PGD",
            "so_kh":        "So KH",
            "tong_dn":      "Du no (VND)",
        })
    )
    return result


def tom_tat_cn(df: pd.DataFrame) -> dict:
    """Trả về dict tóm tắt toàn CN: {A: n, B: n, C: n, D: n}."""
    if "__phan_loai" not in df.columns:
        df = phan_loai_khach_hang(df)
    counts = df["__phan_loai"].value_counts().to_dict()
    return {k: counts.get(k, 0) for k in ["A", "B", "C", "D"]}
