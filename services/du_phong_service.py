"""Dự phóng Doanh số Thu nợ & Kế hoạch Dòng tiền — PGD / Xã."""
from __future__ import annotations

from datetime import datetime, date

import pandas as pd
from dateutil.relativedelta import relativedelta

from config import (
    COT_SO_KU, COT_MA_KH, COT_TEN_KH, COT_TEN_PGD, COT_TEN_XA,
    COT_TEN_CT, COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH,
    COT_NGAY_VAY, COT_NGAY_DH, COT_MUC_VAY, COT_NGUON_VON,
)


def du_phong_dong_tien(
    df: pd.DataFrame,
    tu_thang: date | None = None,
    den_thang: date | None = None,
) -> pd.DataFrame:
    """
    Tính dòng tiền dự kiến thu nợ gốc theo tiến độ hợp đồng cho từng tháng.

    Nguyên lý: Với mỗi khế ước còn dư nợ, lấy Tổng mức vay (Mức vay),
    phân bổ đều theo số tháng từ Ngày vay → Ngày ĐH theo Gia hạn.
    Chỉ tính các tháng nằm trong khoảng tu_thang → den_thang.

    Returns:
        DataFrame với cột: thang, so_mon, tong_du_no, du_kien_thu_goc, du_no_th, du_no_qh
    """
    if df.empty:
        return pd.DataFrame()

    need_cols = [COT_NGAY_VAY, COT_NGAY_DH, COT_MUC_VAY, COT_TONG_DU_NO]
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        return pd.DataFrame()

    df = df[df[COT_TONG_DU_NO] > 0].copy()
    if len(df) == 0:
        return pd.DataFrame()

    df[COT_NGAY_VAY] = pd.to_datetime(df[COT_NGAY_VAY], dayfirst=True, errors="coerce")
    df[COT_NGAY_DH] = pd.to_datetime(df[COT_NGAY_DH], dayfirst=True, errors="coerce")

    df = df.dropna(subset=[COT_NGAY_VAY, COT_NGAY_DH])
    df["_so_thang"] = (
        (df[COT_NGAY_DH].dt.year - df[COT_NGAY_VAY].dt.year) * 12
        + (df[COT_NGAY_DH].dt.month - df[COT_NGAY_VAY].dt.month)
    ).clip(lower=1)

    df["_goc_hang_thang"] = df[COT_MUC_VAY] / df["_so_thang"]

    hom_nay = datetime.now().date()
    if tu_thang is None:
        tu_thang = date(hom_nay.year, hom_nay.month, 1)
    if den_thang is None:
        den_thang = tu_thang + relativedelta(months=12)

    thang_hien_tai = date(hom_nay.year, hom_nay.month, 1)

    records = []
    for _, row in df.iterrows():
        ngay_vay = row[COT_NGAY_VAY].date()
        ngay_dh = row[COT_NGAY_DH].date()
        goc_ht = row["_goc_hang_thang"]
        du_no = row[COT_TONG_DU_NO]

        for i in range(int(row["_so_thang"])):
            thang_moc = ngay_vay + relativedelta(months=i)
            thang_key = date(thang_moc.year, thang_moc.month, 1)

            if thang_key < tu_thang or thang_key > den_thang:
                continue

            da_qua = thang_key <= thang_hien_tai

            records.append({
                "thang": thang_key,
                "so_ku": row.get(COT_SO_KU, ""),
                "ma_kh": row.get(COT_MA_KH, ""),
                "ten_kh": row.get(COT_TEN_KH, ""),
                "du_no_hien_tai": du_no,
                "du_kien_thu_goc": goc_ht,
                "da_qua": da_qua,
            })

    if not records:
        return pd.DataFrame()

    df_thang = pd.DataFrame(records)

    tong_hop = df_thang.groupby("thang").agg(
        so_mon=("so_ku", "count"),
        tong_du_no=("du_no_hien_tai", "sum"),
        du_kien_thu_goc=("du_kien_thu_goc", "sum"),
    ).reset_index()

    tong_hop["du_kien_thu_goc_trieu"] = (tong_hop["du_kien_thu_goc"] / 1e6).round(1)
    tong_hop["tong_du_no_trieu"] = (tong_hop["tong_du_no"] / 1e6).round(1)
    tong_hop["thang_label"] = tong_hop["thang"].apply(lambda d: d.strftime("%m/%Y"))

    return tong_hop


def du_phong_chi_tiet(
    df: pd.DataFrame,
    thang: date,
) -> pd.DataFrame:
    """Danh sách chi tiết các khế ước đến hạn thu gốc trong tháng cụ thể."""
    if df.empty:
        return pd.DataFrame()

    need_cols = [COT_NGAY_VAY, COT_NGAY_DH, COT_MUC_VAY, COT_TONG_DU_NO]
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        return pd.DataFrame()

    df = df[df[COT_TONG_DU_NO] > 0].copy()
    df[COT_NGAY_VAY] = pd.to_datetime(df[COT_NGAY_VAY], dayfirst=True, errors="coerce")
    df[COT_NGAY_DH] = pd.to_datetime(df[COT_NGAY_DH], dayfirst=True, errors="coerce")
    df = df.dropna(subset=[COT_NGAY_VAY, COT_NGAY_DH])

    results = []
    for _, row in df.iterrows():
        ngay_vay = row[COT_NGAY_VAY].date()
        ngay_dh = row[COT_NGAY_DH].date()
        so_thang = max(1, (ngay_dh.year - ngay_vay.year) * 12 + (ngay_dh.month - ngay_vay.month))
        goc_ht = row[COT_MUC_VAY] / so_thang

        for i in range(so_thang):
            thang_moc = ngay_vay + relativedelta(months=i)
            thang_key = date(thang_moc.year, thang_moc.month, 1)
            if thang_key == thang:
                results.append({
                    "so_ku": row.get(COT_SO_KU, ""),
                    "ma_kh": row.get(COT_MA_KH, ""),
                    "ten_kh": row.get(COT_TEN_KH, ""),
                    "ten_pgd": row.get(COT_TEN_PGD, ""),
                    "ten_xa": row.get(COT_TEN_XA, ""),
                    "ten_ct": row.get(COT_TEN_CT, ""),
                    "du_no": row[COT_TONG_DU_NO],
                    "goc_hang_thang": goc_ht,
                    "ngay_vay": ngay_vay.strftime("%d/%m/%Y"),
                    "ngay_dh": ngay_dh.strftime("%d/%m/%Y"),
                })
                break

    if not results:
        return pd.DataFrame()

    df_ct = pd.DataFrame(results)
    df_ct["du_no_trieu"] = (df_ct["du_no"] / 1e6).round(1)
    df_ct["goc_ht_trieu"] = (df_ct["goc_hang_thang"] / 1e6).round(1)
    return df_ct
