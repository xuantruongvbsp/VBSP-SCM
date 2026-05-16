"""
Module tính ngày đến hạn khoản vay từ hstd.parquet.
KHÔNG import streamlit — dùng pandas + thư viện chuẩn.
"""
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

import pandas as pd
import numpy as np

from config import (
    CACHE_HSTD,
    COT_TEN_PGD, COT_TEN_KH, COT_MA_KH,
    COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH,
    COT_TEN_CT, COT_NGAY_DEN_HAN,
    COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_THOI_HAN,
)

_COT_MA_QD   = "Mã Quyết định"
_COT_TEN_DTTH = "Tên ĐTTH"


def _parse_ngay(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
        return None
    except Exception:
        return None


def _tinh_so_thang_gia_han(row) -> "int | None":
    """Số tháng tối đa được gia hạn nợ theo quy định (làm tròn xuống)."""
    ma_ct    = str(row.get(COT_MA_CHUONG_TRINH, "")).strip()
    ma_qd    = str(row.get(_COT_MA_QD,          "")).strip()
    ten_dtth = str(row.get(_COT_TEN_DTTH,        "")).strip()
    thoi_han = pd.to_numeric(row.get(COT_THOI_HAN, None), errors="coerce")

    if ma_ct == "02":
        return None if pd.isna(thoi_han) else int(thoi_han) // 2

    if ma_ct == "17":
        return 30

    if "29" in ma_qd or "54" in ma_qd:
        if ten_dtth == "Hộ mới thoát nghèo":
            return 0
        if ten_dtth == "Hộ nghèo":
            return 30

    if pd.isna(thoi_han):
        return None
    thoi_han_int = int(thoi_han)
    return 12 if thoi_han_int <= 12 else thoi_han_int // 2


def tinh_den_han_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_ngay_dh"] = df[COT_NGAY_DEN_HAN].apply(_parse_ngay)
    df["Ngày đến hạn"] = df["_ngay_dh"]
    today = date.today()
    df["Tháng đến hạn còn lại"] = df["_ngay_dh"].apply(
        lambda d: (
            relativedelta(d, today).months + relativedelta(d, today).years * 12
            if d is not None else None
        )
    )
    df["Số tháng có thể gia hạn"] = df.apply(_tinh_so_thang_gia_han, axis=1)
    df.drop(columns=["_ngay_dh"], inplace=True)
    return df


def loc_den_han_trong(df, tu_thang=0, den_thang=6) -> pd.DataFrame:
    df_tinh = tinh_den_han_df(df)
    mask = (
        df_tinh["Tháng đến hạn còn lại"].notna()
        & (df_tinh["Tháng đến hạn còn lại"] >= tu_thang)
        & (df_tinh["Tháng đến hạn còn lại"] <= den_thang)
    )
    return df_tinh[mask].copy()


def tong_hop_den_han(df, nhom_theo="pgd") -> pd.DataFrame:
    cot_nhom = COT_TEN_PGD if nhom_theo == "pgd" else COT_TEN_XA
    if cot_nhom not in df.columns:
        return pd.DataFrame()

    df_loc = loc_den_han_trong(df, tu_thang=0, den_thang=6)
    if df_loc.empty:
        return pd.DataFrame()

    ket_qua = df_loc.groupby([cot_nhom, "Tháng đến hạn còn lại"]).agg(
        so_khoan_vay=(COT_MA_KH if COT_MA_KH in df_loc.columns else cot_nhom, "count"),
        tong_du_no=(COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else cot_nhom, "sum"),
    ).reset_index()

    today = date.today()
    ket_qua["Tháng"] = ket_qua["Tháng đến hạn còn lại"].apply(
        lambda n: (today + relativedelta(months=int(n))).strftime("Tháng %m/%Y")
    )
    ket_qua = ket_qua.sort_values([cot_nhom, "Tháng đến hạn còn lại"])
    return ket_qua


def canh_bao_tap_trung(df, nguong_ty_le=0.30) -> list[dict]:
    df_loc = loc_den_han_trong(df, tu_thang=0, den_thang=6)
    if df_loc.empty or COT_TEN_PGD not in df.columns:
        return []

    tong_pgd = df[df[COT_TEN_PGD].isin(df_loc[COT_TEN_PGD])]\
        .groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum()

    canh_bao_list = []
    grouped = df_loc.groupby([COT_TEN_PGD, "Tháng đến hạn còn lại"])

    today = date.today()
    for (ten_pgd, thang_con_lai), grp in grouped:
        tong_den_han = grp[COT_TONG_DU_NO].sum()
        tong_pgd_val = tong_pgd.get(ten_pgd, 0)
        if tong_pgd_val <= 0:
            continue
        ty_le = tong_den_han / tong_pgd_val
        if ty_le >= nguong_ty_le:
            thang_str = (today + relativedelta(months=int(thang_con_lai))).strftime("Tháng %m/%Y")
            canh_bao_list.append({
                "pgd": ten_pgd,
                "thang": thang_str,
                "thang_con_lai": int(thang_con_lai),
                "so_khoan": int(len(grp)),
                "tong_den_han": int(tong_den_han),
                "tong_pgd": int(tong_pgd_val),
                "ty_le": float(ty_le),
                "muc_do": "high" if ty_le >= 0.50 else "medium",
            })

    canh_bao_list.sort(key=lambda x: x["ty_le"], reverse=True)
    return canh_bao_list
