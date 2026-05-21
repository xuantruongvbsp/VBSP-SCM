"""Data aggregation helpers cho module Nợ Rủi Ro."""
from __future__ import annotations

from collections import defaultdict


def _loc_theo_nguon(df_rows: list[dict], nguon: int) -> list[dict]:
    """Lọc danh sách hồ sơ theo nguồn vốn (1=TW, 2=ĐP)."""
    return [r for r in df_rows if int(r.get("nguon_von", 0)) == nguon]


def _tong_hop_no(ds: list[dict]) -> dict:
    """Tổng hợp số liệu theo nhóm chương trình."""
    nhom = defaultdict(lambda: {"so_ho": 0, "goc": 0.0, "lai": 0.0, "ds": []})
    for r in ds:
        ct = r.get("ten_ct", "Khác") or "Khác"
        nhom[ct]["so_ho"] += 1
        nhom[ct]["goc"] += float(r.get("du_no_goc", 0) or 0)
        nhom[ct]["lai"] += float(r.get("lai_ton", 0) or 0)
        nhom[ct]["ds"].append(r)
    tong_goc = sum(v["goc"] for v in nhom.values())
    tong_lai = sum(v["lai"] for v in nhom.values())
    return {
        "nhom_ct": dict(nhom),
        "tong_ho": sum(v["so_ho"] for v in nhom.values()),
        "tong_goc": tong_goc,
        "tong_lai": tong_lai,
        "tong_tien": tong_goc + tong_lai,
    }
