# -*- coding: utf-8 -*-
"""Bước 3b: soi chi tiết xã Tam Hiệp — mã thôn nào có dư nợ ở 2 ngày GDXA."""
from __future__ import annotations

import pandas as pd

from analyze_hoi_so import nap_du_lieu

pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 300)


def main() -> None:
    df = nap_du_lieu()
    d = df[(df["_htv"] != 1) & (df["_xa"] == "Tam Hiệp")].copy()
    g = d.groupby(["_mt", "_ngay"], dropna=False).agg(
        so_dong=("_dn", "size"),
        du_no_trieu=("_dn", lambda s: round(s.sum() / 1e6, 2)),
        so_to=("_to", lambda s: s[s != ""].nunique()),
        so_kh=("_kh", lambda s: s.nunique()),
        ten_thon=("Tên thôn", lambda s: sorted({str(x).strip() for x in s.dropna()
                                                if str(x).strip() and str(x).strip().lower() != "<na>"})),
    ).reset_index()
    print("=== Xã Tam Hiệp: (Mã thôn, Ngày GDXA) ===")
    print(g.to_string(index=False))

    print("\n=== Mã thôn có dư nợ > 0 ở nhiều ngày ===")
    dn = g[g["du_no_trieu"] > 0]
    for mt, gg in dn.groupby("_mt"):
        if gg["_ngay"].nunique() > 1:
            print(f"  {mt}: " + " | ".join(
                f"ngày {r._ngay}: {r.du_no_trieu:,.2f}tr, {r.so_to} tổ" for r in gg.itertuples()))

    print("\n=== Tổng theo ngày (chỉ dòng dư nợ > 0) ===")
    d2 = d[d["_dn"] > 0]
    print(d2.groupby("_ngay", dropna=False).apply(
        lambda x: pd.Series({
            "du_no_trieu": round(x["_dn"].sum() / 1e6, 2),
            "so_to": x.loc[x["_to"] != "", "_to"].nunique(),
            "so_kh": x["_kh"].nunique(),
            "so_ma_thon": x["_mt"].nunique(),
        }), include_groups=False).to_string())

    print("\n=== Loại 46005812 khỏi ngày 13 thì Tân Mai còn bao nhiêu? ===")
    for loai in [None, "46005812"]:
        x = d2[(d2["_ngay"] == 13)]
        if loai:
            x = x[x["_mt"] != loai]
        print(f"  loại={loai}: dư nợ {x['_dn'].sum()/1e6:,.2f} | tổ {x.loc[x['_to']!='','_to'].nunique()}"
              f" | KH {x['_kh'].nunique()} | mã thôn {sorted(x['_mt'].unique())}")
    print("  PDF Tân Mai: tổ 8 | KH 306 | dư nợ 27,875.11")

    print("\n=== Ngày 22: chi tiết từng mã thôn (so với Bình Đa 30,087.74 / Tam Hiệp 17,355.69) ===")
    x22 = d2[d2["_ngay"] == 22]
    print(x22.groupby("_mt").apply(lambda x: pd.Series({
        "du_no_trieu": round(x["_dn"].sum() / 1e6, 2),
        "so_to": x.loc[x["_to"] != "", "_to"].nunique(),
        "so_kh": x["_kh"].nunique(),
        "ten_thon": ", ".join(sorted({str(v).strip() for v in x["Tên thôn"].dropna()
                                      if str(v).strip() and str(v).strip().lower() != "<na>"})),
    }), include_groups=False).to_string())


if __name__ == "__main__":
    main()
