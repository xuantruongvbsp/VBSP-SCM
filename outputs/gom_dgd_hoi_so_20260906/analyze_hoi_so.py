# -*- coding: utf-8 -*-
"""Phân tích đối chiếu HSTD Hội sở (31/07/2026) với báo cáo PDF theo Xã - Điểm GD.

Mục tiêu:
  1. Xác định định nghĩa chỉ tiêu khớp PDF (dư nợ / số tổ / KH vay).
  2. Kiểm tra độ lệch theo từng xã.
Chạy: venv\\Scripts\\python.exe outputs\\gom_dgd_hoi_so_20260906\\analyze_hoi_so.py
"""
from __future__ import annotations

import pandas as pd

PARQUET = r"pgd_data\hoi_so_chi_nhanh_tinh\hstd_khnv.parquet"

# Số liệu PDF 4601_RPT_DNO_XA_DIEMGD_31072026 (đơn vị: triệu đồng)
# xa: (so_to, kh_vay, tong_du_no)
PDF_XA = {
    "Biên Hòa":   (24, 1076, 61682.13),
    "Hố Nai":     (23,  933, 52737.07),
    "Long Bình":  (33, 1573, 107193.79),
    "Long Hưng":  (17,  784, 47666.40),
    "Phước Tân":  (23, 1086, 67972.51),
    "Tam Hiệp":   (31, 1381, 105451.60),
    "Tam Phước":  (17,  732, 45587.40),
    "Trảng Dài":  (16,  815, 64709.23),
    "Trấn Biên":  (50, 1829, 128417.44),
}
PDF_TONG = (234, 10209, 681418.0)


def chuan_hoa_ma(s: pd.Series) -> pd.Series:
    return s.astype("string").fillna("").str.replace(r"\.0$", "", regex=True).str.strip()


def nap_du_lieu() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["_xa"] = df["Tên xã"].astype("string").fillna("").str.strip()
    df["_mt"] = chuan_hoa_ma(df["Mã thôn"])
    df["_ms"] = chuan_hoa_ma(df["Mã xã"])
    df["_to"] = chuan_hoa_ma(df["Mã tổ"])
    df["_kh"] = chuan_hoa_ma(df["Mã KH"])
    df["_htv"] = pd.to_numeric(df["Hình thức vay"], errors="coerce")
    df["_ngay"] = pd.to_numeric(df["Ngày GDXA"], errors="coerce")
    df["_dn"] = pd.to_numeric(df["Tổng dư nợ"], errors="coerce").fillna(0)
    df["_qh"] = pd.to_numeric(df["Dư nợ quá hạn"], errors="coerce").fillna(0)
    df["_th"] = pd.to_numeric(df["Dư nợ trong hạn"], errors="coerce").fillna(0)
    df["_kh_val"] = pd.to_numeric(df["Dư nợ khoanh"], errors="coerce").fillna(0)
    return df


def main() -> None:
    df = nap_du_lieu()
    print(f"Tổng số dòng: {len(df):,} | Tổng dư nợ: {df['_dn'].sum()/1e6:,.1f} triệu")
    print("Giá trị 'Hình thức vay':", sorted(set(df["_htv"].dropna().tolist())))
    print("Dư nợ theo Hình thức vay (triệu):")
    print((df.groupby("_htv")["_dn"].sum() / 1e6).round(1).to_string())
    print("\nTình trạng món vay (triệu):")
    print((df.groupby("Tình trạng món vay")["_dn"].sum() / 1e6).round(1).to_string())

    print("\n=== Đối chiếu theo xã ===")
    hdr = f"{'Xã':<11}{'HSTD_all':>12}{'HTV!=1':>12}{'PDF':>12}{'d(all)':>10}{'d(!=1)':>10}"
    print(hdr)
    t_all = t_f = 0.0
    for xa, (_to, _kh, dn_pdf) in PDF_XA.items():
        g = df[df["_xa"] == xa]
        a = g["_dn"].sum() / 1e6
        f = g[g["_htv"] != 1]["_dn"].sum() / 1e6
        t_all += a
        t_f += f
        print(f"{xa:<11}{a:>12,.1f}{f:>12,.1f}{dn_pdf:>12,.1f}{a-dn_pdf:>10,.1f}{f-dn_pdf:>10,.1f}")
    print(f"{'TỔNG 9 xã':<11}{t_all:>12,.1f}{t_f:>12,.1f}{PDF_TONG[2]:>12,.1f}"
          f"{t_all-PDF_TONG[2]:>10,.1f}{t_f-PDF_TONG[2]:>10,.1f}")

    print("\nCác 'Tên xã' khác ngoài 9 xã của PDF:")
    khac = df[~df["_xa"].isin(PDF_XA)]
    if khac.empty:
        print("  (không có)")
    else:
        print(khac.groupby("_xa")["_dn"].agg(["count", "sum"]).assign(trieu=lambda x: (x["sum"]/1e6).round(1)).to_string())

    print("\n=== Đối chiếu số tổ / KH vay (xã, HTV!=1) ===")
    print(f"{'Xã':<11}{'to_HSTD':>9}{'to_PDF':>8}{'kh_HSTD':>9}{'kh_PDF':>8}{'mon_HSTD':>10}")
    for xa, (to_pdf, kh_pdf, _dn) in PDF_XA.items():
        g = df[(df["_xa"] == xa) & (df["_htv"] != 1)]
        print(f"{xa:<11}{g['_to'].nunique():>9}{to_pdf:>8}{g['_kh'].nunique():>9}{kh_pdf:>8}"
              f"{g['_dn'].gt(0).sum():>10}")


if __name__ == "__main__":
    main()
