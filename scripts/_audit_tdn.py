"""Audit tổng dư nợ HSTD — chạy tạm, không commit."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
import pandas as pd

from config import (
    CACHE_HSTD,
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_MA_KH,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
)
from services.validation_service import validate_hstd_cross_pgd_duplicates
from services.tongquan_service import tinh_kpi_tongquan

path = CACHE_HSTD.replace("\\", "/")

print("=== 1. TONG HOP PARQUET ===")
r_full = duckdb.query(f"""
SELECT COUNT(*) AS rows,
       SUM(TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE)) AS tdn
FROM '{path}'
""").df().iloc[0]
r_act = duckdb.query(f"""
SELECT COUNT(*) AS rows,
       SUM(TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE)) AS tdn
FROM '{path}'
WHERE TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE) > 0
   OR TRY_CAST("{COT_DU_NO_QH}" AS DOUBLE) > 0
   OR TRY_CAST("{COT_DU_NO_KHOANH}" AS DOUBLE) > 0
""").df().iloc[0]
print(f"  Full:  {int(r_full['rows']):,} rows, TDN {r_full['tdn']/1e9:.3f} ty")
print(f"  Active:{int(r_act['rows']):,} rows, TDN {r_act['tdn']/1e9:.3f} ty")

df = pd.read_parquet(CACHE_HSTD)
for c in [COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
mask = (df[COT_TONG_DU_NO] > 0) | (df[COT_DU_NO_QH] > 0) | (df[COT_DU_NO_KHOANH] > 0)
da = df[mask]

kpi = tinh_kpi_tongquan(
    da, COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_SO_KU, COT_MA_KH
)
print(f"  KPI tab (active): TDN {kpi['tdn']/1e9:.3f} ty")
print(f"  Can doi TH+QH+Khoanh: {(kpi['dth']+kpi['dqh']+kpi['dnk'])/1e9:.3f} ty")

print("\n=== 2. TRUNG CHEO PGD (E15) ===")
rep = validate_hstd_cross_pgd_duplicates(df)
print(f"  is_valid: {rep.is_valid}")
if not rep.is_valid:
    print(f"  duplicate groups: {rep.duplicate_group_count}")
    print(f"  duplicate rows: {rep.duplicate_row_count}")
    print(f"  total dup amount ty: {rep.total_duplicate_amount/1e9:.3f}")
    print(f"  estimated EXCESS ty: {rep.estimated_excess_amount/1e9:.3f}")
    if rep.top_pairs:
        print("  top pairs:")
        for p in rep.top_pairs[:5]:
            print(f"    {p}")

# Dedupe: keep max du_no per (ma_kh, so_ku) — conservative
if COT_MA_KH in da.columns and COT_SO_KU in da.columns:
    dedup = (
        da.sort_values(COT_TONG_DU_NO, ascending=False)
        .drop_duplicates(subset=[COT_MA_KH, COT_SO_KU], keep="first")
    )
    print(f"\n=== 3. NEU BO TRUNG (KH+KU, giu dong DN lon nhat) ===")
    print(f"  rows: {len(da):,} -> {len(dedup):,}")
    print(f"  TDN ty: {da[COT_TONG_DU_NO].sum()/1e9:.3f} -> {dedup[COT_TONG_DU_NO].sum()/1e9:.3f}")
    print(f"  giam ty: {(da[COT_TONG_DU_NO].sum()-dedup[COT_TONG_DU_NO].sum())/1e9:.3f}")

print("\n=== 4. THEO PGD (active TDN ty) ===")
pgd = da.groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum().sort_values(ascending=False)
for p, v in pgd.items():
    print(f"  {v/1e9:7.3f}  {p}")

print("\n=== 5. SUM FILE PGD GOC (neu co) ===")
from config import PGD_DATA_DIR

frames = []
for d in sorted(Path(PGD_DATA_DIR).iterdir()):
    if not d.is_dir():
        continue
    for name in ("hstd_latest.xlsx", "hstd.xlsx"):
        p = d / name
        if p.exists():
            try:
                x = pd.read_excel(p, engine="openpyxl")
                if COT_TONG_DU_NO in x.columns:
                    t = pd.to_numeric(x[COT_TONG_DU_NO], errors="coerce").fillna(0).sum()
                    frames.append((d.name, t, len(x)))
            except Exception as e:
                print(f"  skip {p}: {e}")
            break
if frames:
    s = sum(t for _, t, _ in frames)
    print(f"  {len(frames)} file, tong TDN ty: {s/1e9:.3f} (chua loc active)")
else:
    print("  Khong co pgd_data local")
