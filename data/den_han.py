"""
Module tính ngày đến hạn khoản vay từ hstd.parquet.
KHÔNG import streamlit — dùng pandas + thư viện chuẩn.
"""
from datetime import date
from dateutil.relativedelta import relativedelta

import pandas as pd
import numpy as np

from config import (
    CACHE_HSTD,
    COT_TEN_PGD, COT_TEN_KH, COT_MA_KH,
    COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH,
    COT_TEN_CT, COT_NGAY_DEN_HAN,
    COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_THOI_HAN,
    COT_NGAY_VAY, COT_NGAY_DH_HD,
)

_COT_MA_QD   = "Mã Quyết định"
_COT_TEN_DTTH = "Tên ĐTTH"


def _normalize_ma(s: pd.Series) -> pd.Series:
    """Chuẩn hóa '2.0' → '2', '17.0' → '17'; chuỗi không phải số giữ nguyên."""
    numeric = pd.to_numeric(s, errors="coerce")
    normalized = numeric.dropna().astype(int).astype(str)
    result = s.copy()
    result[numeric.notna()] = normalized
    return result


def _tinh_thoi_han_tu_ngay(df: pd.DataFrame) -> pd.Series:
    """Tính thời hạn vay (tháng) từ Ngày vay → Ngày ĐH theo hợp đồng khi cột Thời hạn vay trống."""
    thoi_han = pd.to_numeric(
        df[COT_THOI_HAN] if COT_THOI_HAN in df.columns else pd.Series(np.nan, index=df.index),
        errors="coerce",
    )
    # Nếu đã có dữ liệu thì dùng luôn
    if thoi_han.notna().any():
        return thoi_han
    # Tính từ ngày vay và ngày đến hạn theo hợp đồng
    if COT_NGAY_VAY not in df.columns or COT_NGAY_DH_HD not in df.columns:
        return thoi_han
    ngay_vay = pd.to_datetime(df[COT_NGAY_VAY], dayfirst=True, errors="coerce")
    ngay_dh  = pd.to_datetime(df[COT_NGAY_DH_HD], dayfirst=True, errors="coerce")
    computed = (ngay_dh.dt.year - ngay_vay.dt.year) * 12 + (ngay_dh.dt.month - ngay_vay.dt.month)
    return computed.where(ngay_vay.notna() & ngay_dh.notna())


def _tinh_so_thang_gia_han_vec(df: pd.DataFrame) -> pd.Series:
    """Vectorized: số tháng tối đa được gia hạn theo quy định NHCSXH."""
    idx = df.index

    def _str_col(name: str) -> pd.Series:
        return (df[name].astype(str).str.strip()
                if name in df.columns else pd.Series("", index=idx))

    ma_ct    = _normalize_ma(_str_col(COT_MA_CHUONG_TRINH))
    ma_qd    = _normalize_ma(_str_col(_COT_MA_QD))
    ten_dtth = _str_col(_COT_TEN_DTTH)
    thoi_han = _tinh_thoi_han_tu_ngay(df)
    th_half  = thoi_han.fillna(0) // 2
    m_qd = ma_qd.str.contains("29", na=False) | ma_qd.str.contains("54", na=False)

    # np.select: first matching condition wins (highest priority first)
    conditions = [
        (ma_ct == "2") & thoi_han.notna(),
        ma_ct == "17",
        m_qd & (ten_dtth == "Hộ mới thoát nghèo"),
        m_qd & (ten_dtth == "Hộ nghèo"),
        thoi_han.notna() & (thoi_han <= 12),
        thoi_han.notna() & (thoi_han > 12),
    ]
    choices = [th_half, 30, 0, 30, 12, th_half]
    return pd.Series(np.select(conditions, choices, default=np.nan), index=idx).astype("Int64")


def tinh_den_han_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    ngay_ts = pd.to_datetime(df[COT_NGAY_DEN_HAN], dayfirst=True, errors="coerce")
    df["Ngày đến hạn"] = ngay_ts.dt.date.where(ngay_ts.notna())
    today = date.today()
    months_diff = (ngay_ts.dt.year - today.year) * 12 + (ngay_ts.dt.month - today.month)
    df["Tháng đến hạn còn lại"] = months_diff.where(ngay_ts.notna()).astype("Int64")
    df["Số tháng có thể gia hạn"] = _tinh_so_thang_gia_han_vec(df)
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

    df_loc = loc_den_han_trong(df, tu_thang=0, den_thang=den_thang)
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


def canh_bao_tap_trung(df, nguong_ty_le=0.30, den_thang: int = 6) -> list[dict]:
    df_loc = loc_den_han_trong(df, tu_thang=0, den_thang=den_thang)
    if df_loc.empty or COT_TEN_PGD not in df.columns:
        return []

    tong_pgd = df[df[COT_TEN_PGD].isin(df_loc[COT_TEN_PGD])]\
        .groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum()

    canh_bao_list = []
    grouped = df_loc.groupby(COT_TEN_PGD)

    today = date.today()
    thang_str = f"trong {den_thang} tháng tới"
    for ten_pgd, grp in grouped:
        tong_den_han = grp[COT_TONG_DU_NO].sum()
        tong_pgd_val = tong_pgd.get(ten_pgd, 0)
        if tong_pgd_val <= 0:
            continue
        ty_le = tong_den_han / tong_pgd_val
        if ty_le >= nguong_ty_le:
            canh_bao_list.append({
                "pgd": ten_pgd,
                "thang": thang_str,
                "thang_con_lai": den_thang,
                "so_khoan": int(len(grp)),
                "tong_den_han": int(tong_den_han),
                "tong_pgd": int(tong_pgd_val),
                "ty_le": float(ty_le),
                "muc_do": "high" if ty_le >= 0.50 else "medium",
            })

    canh_bao_list.sort(key=lambda x: x["ty_le"], reverse=True)
    return canh_bao_list
