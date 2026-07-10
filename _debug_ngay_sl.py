"""Debug: kiểm tra Ngày số liệu HSTD từ merged parquet và từng file PGD."""
import sys, os
sys.path.insert(0, 'd:/VBSP-SCM')

import pyarrow.parquet as pq
import pandas as pd
from datetime import datetime
import db

# ── 1. Kiểm tra merged parquet ──────────────────────────────────────
print("=" * 60)
print("1. MERGED PARQUET: cache/hstd.parquet")
print("=" * 60)
schema = pq.read_schema('d:/VBSP-SCM/cache/hstd.parquet')
cols = [f.name for f in schema]
print(f"Số cột: {len(cols)}")
print(f"Có cột 'Ngày số liệu': {'Ngày số liệu' in cols}")

# Tìm cột liên quan ngày
for c in cols:
    if 'ngày' in c.lower() or 'số liệu' in c.lower() or 'date' in c.lower():
        print(f"  Cột liên quan: '{c}'")

# Đọc thử 3 dòng
df = pq.read_table('d:/VBSP-SCM/cache/hstd.parquet').to_pandas()
print(f"Số dòng: {len(df)}")

if 'Ngày số liệu' in cols:
    vals = df['Ngày số liệu'].dropna().unique()
    print(f"Giá trị 'Ngày số liệu' unique (first 10): {list(vals[:10])}")
    # Parse thử
    parsed = pd.to_datetime(df['Ngày số liệu'], dayfirst=True, errors='coerce')
    print(f"  Số dòng parse được: {parsed.notna().sum()}")
    if parsed.notna().sum() > 0:
        print(f"  Min: {parsed.min()}, Max: {parsed.max()}")

# ── 2. Kiểm tra merge_meta_hstd ─────────────────────────────────────
print("\n" + "=" * 60)
print("2. merge_meta_hstd trong kv_store")
print("=" * 60)
meta = db.doc_kv("merge_meta_hstd")
if meta:
    for k, v in meta.items():
        print(f"  {k}: {v}")
else:
    print("  → Không tồn tại")

# ── 3. Thử đọc Ngày số liệu từ file Excel gốc của 1-2 PGD ──────────
print("\n" + "=" * 60)
print("3. Kiểm tra _doc_ngay_so_lieu() từ data.pgd")
print("=" * 60)
from data.pgd import duong_dan_pgd

# Test với 1-2 PGD có file
for ten_pgd in ["PGD Biên Hòa", "PGD Long Khánh", "PGD Trảng Bom", "PGD Vĩnh Cửu", "PGD Nhơn Trạch"]:
    path = duong_dan_pgd(ten_pgd, "hstd")
    if path and os.path.exists(path):
        print(f"\n--- {ten_pgd}: {path} ---")
        # Đọc cell FS6 trực tiếp
        try:
            df_cell = pd.read_excel(path, sheet_name='BCQUERY', header=None, engine='openpyxl')
            print(f"  Sheet BCQUERY shape: {df_cell.shape}")
            # FS = column index 187 (F=6, S=19 → 6*26+19-1 = 174... let me calculate)
            # F=6th letter, S=19th letter → col = 6*26 + 18 = 174 (0-indexed)
            # Actually: A=1, Z=26, AA=27, ... FS:
            # F=6, S=19 → col = 6*26 + 19 = 175 (1-indexed) → 174 (0-indexed)
            # Row 6 (1-indexed) → row 5 (0-indexed)
            fs_col = 6*26 + 19 - 1  # 0-indexed
            print(f"  FS column index (0-based): {fs_col}")
            val = df_cell.iloc[5, fs_col] if df_cell.shape[1] > fs_col else "N/A"
            print(f"  Cell FS6 value: {repr(val)}")
            # Row 5 is 0-indexed = row 6 in Excel
            # Also check row 5 (0-indexed)
            val2 = df_cell.iloc[5, fs_col] if df_cell.shape[1] > fs_col else "N/A"
            print(f"  Cell at [5, {fs_col}]: {repr(val2)}")
        except Exception as e:
            print(f"  LỖI đọc Excel: {e}")
    else:
        print(f"\n--- {ten_pgd}: KHÔNG có file ---")

print("\n✅ Done")
