"""
Helpers thuần dữ liệu cho tab Nợ khoanh — không phụ thuộc Streamlit.
Dùng bởi: tabs/tab_no_khoanh.py.
"""
from __future__ import annotations

import pandas as pd

from config import COT_DU_NO_KHOANH, COT_SO_KU
from utils import fmt_ty


def loc_khoanh(df: pd.DataFrame) -> pd.DataFrame:
    """Lọc các món vay đang khoanh nợ (Dư nợ khoanh > 0)."""
    if COT_DU_NO_KHOANH not in df.columns:
        return pd.DataFrame()
    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    return df[du_kh > 0].copy()


def bang_theo_nhom(df: pd.DataFrame, nhom_col: str) -> pd.DataFrame:
    """Bảng tổng hợp: nhóm | Số món | Dư nợ khoanh (triệu đồng) | Tỷ trọng%."""
    if nhom_col not in df.columns or df.empty:
        return pd.DataFrame()

    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df = df.copy()
    df["_du_kh"] = du_kh

    nhom = (
        df.groupby(nhom_col)
        .agg(so_mon=(COT_SO_KU, "nunique"), du_no_khoanh=("_du_kh", "sum"))
        .reset_index()
        .sort_values("du_no_khoanh", ascending=False)
    )

    tong = nhom["du_no_khoanh"].sum()
    nhom["Tỷ trọng%"] = (
        (nhom["du_no_khoanh"] / tong * 100)
        .round(1)
        .apply(lambda x: f"{x:.1f}".replace(".", ",") + "%")
        if tong > 0
        else "0%"
    )
    _COL_DN = "Dư nợ khoanh (triệu đồng)"
    nhom[_COL_DN] = nhom["du_no_khoanh"].apply(fmt_ty)
    nhom = nhom.rename(columns={"so_mon": "Số món"})
    return nhom[[nhom_col, "Số món", _COL_DN, "Tỷ trọng%"]]
