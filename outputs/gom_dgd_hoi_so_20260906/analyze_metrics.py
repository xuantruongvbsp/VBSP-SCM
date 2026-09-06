# -*- coding: utf-8 -*-
"""Bước 2: xác định định nghĩa chỉ tiêu khớp PDF (số tổ, KH vay) và khảo sát
cấu trúc (Xã, Ngày GDXA, Mã thôn) của phần dư nợ thuộc Điểm GD (Hình thức vay != 1).

Chạy: venv\\Scripts\\python.exe outputs\\gom_dgd_hoi_so_20260906\\analyze_metrics.py
"""
from __future__ import annotations

import pandas as pd

from analyze_hoi_so import PDF_XA, chuan_hoa_ma, nap_du_lieu

# PDF theo Điểm GD: xa -> [(ten_dgd, so_to, kh_vay, tong_du_no_trieu)]
PDF_DGD = {
    "Biên Hòa": [
        ("Bửu Hòa", 7, 319, 17635.04),
        ("Biên Hòa", 5, 229, 17422.40),
        ("Tân Hạnh", 8, 343, 17317.34),
        ("Tân Vạn", 4, 185, 9307.35),
    ],
    "Hố Nai": [
        ("Hố Nai", 9, 347, 23299.18),
        ("Hố Nai 3", 14, 586, 29437.89),
    ],
    "Long Bình": [
        ("Hố Nai 2", 9, 459, 29610.37),
        ("Tân Biên", 11, 526, 35090.82),
        ("Long Bình", 13, 588, 42492.60),
    ],
    "Long Hưng": [
        ("Long Bình Tân", 7, 313, 22456.39),
        ("An Hòa", 8, 367, 21799.82),
        ("Long Hưng", 2, 104, 3410.20),
    ],
    "Phước Tân": [
        ("Phước Tân", 23, 1086, 67972.51),
    ],
    "Tam Hiệp": [
        ("Bình Đa", 8, 427, 30087.74),
        ("Tam Hiệp", 6, 252, 17355.69),
        ("Tân Mai", 8, 306, 27875.11),
        ("Tân Hiệp 3", 9, 396, 30133.06),
    ],
    "Trảng Dài": [
        ("Thiện Tân", 8, 383, 23010.36),
        ("Trảng Dài", 8, 432, 41698.87),
    ],
    "Tam Phước": [
        ("Tam Phước", 17, 732, 45587.40),
    ],
    "Trấn Biên": [
        ("An Bình", 4, 192, 14098.70),
        ("Hiệp Hòa", 6, 211, 8841.78),
        ("Trấn Biên", 11, 364, 28837.90),
        ("Bửu Long", 9, 345, 21002.85),
        ("Thống Nhất 2", 4, 140, 11292.93),
        ("Trung Dũng", 16, 577, 44343.27),
    ],
}


def main() -> None:
    df = nap_du_lieu()
    d = df[df["_htv"] != 1].copy()
    print(f"Dòng HTV!=1: {len(d):,} | dư nợ {d['_dn'].sum()/1e6:,.1f} triệu")
    print("Ngày GDXA rỗng trong HTV!=1:", int(d["_ngay"].isna().sum()))
    print("Mã thôn rỗng trong HTV!=1:", int((d["_mt"] == "").sum()))
    print("Mã tổ rỗng trong HTV!=1:", int((d["_to"] == "").sum()))

    print("\n=== Thử các định nghĩa 'số tổ' / 'KH vay' ===")
    print(f"{'Xã':<11}{'to_raw':>8}{'to_loai_rong':>14}{'PDF_to':>8}"
          f"{'kh_all':>8}{'kh_dn>0':>9}{'PDF_kh':>8}")
    for xa, (to_pdf, kh_pdf, _dn) in PDF_XA.items():
        g = d[d["_xa"] == xa]
        to_raw = g["_to"].nunique()
        to_lr = g.loc[g["_to"] != "", "_to"].nunique()
        kh_all = g["_kh"].nunique()
        kh_dn = g.loc[g["_dn"] > 0, "_kh"].nunique()
        print(f"{xa:<11}{to_raw:>8}{to_lr:>14}{to_pdf:>8}{kh_all:>8}{kh_dn:>9}{kh_pdf:>8}")

    print("\n=== Cấu trúc (Xã, Ngày GDXA) — số mã thôn & dư nợ ===")
    for xa in PDF_XA:
        g = d[d["_xa"] == xa]
        print(f"\n--- {xa} | ĐGD PDF: {[x[0] for x in PDF_DGD[xa]]}")
        for ngay, gg in g.groupby("_ngay", dropna=False):
            ma_thons = sorted(gg["_mt"].unique())
            ten_thons = sorted({t for t in gg["Tên thôn"].astype("string").fillna("")
                                .str.strip() if t and t.lower() not in {"nan", "<na>"}})
            print(f"  ngày={ngay} | mã thôn ({len(ma_thons)}): {ma_thons}")
            print(f"          dư nợ={gg['_dn'].sum()/1e6:,.2f} triệu | số tổ={gg.loc[gg['_to']!='','_to'].nunique()}"
                  f" | KH(dư nợ>0)={gg.loc[gg['_dn']>0,'_kh'].nunique()} | tên thôn: {ten_thons}")


if __name__ == "__main__":
    main()
