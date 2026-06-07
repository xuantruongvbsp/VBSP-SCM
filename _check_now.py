import pandas as pd
import pyarrow.parquet as pq
from datetime import datetime
import os, time

# 1. Check cache timestamp & size
cache_path = 'd:/VBSP-SCM/cache/hstd.parquet'
size_mb = os.path.getsize(cache_path) / 1024 / 1024
mtime = os.path.getmtime(cache_path)
dt = datetime.fromtimestamp(mtime)
print(f"hstd.parquet: {size_mb:.1f} MB - {dt.strftime('%d/%m/%Y %H:%M:%S')}")

# 2. Check PGD count and schema
s = pq.read_schema(cache_path)
n_cols = len(s)
print(f"Columns: {n_cols}")

pgd_col_found = any(f.name == 'Tên PGD' for f in s)
print(f"'Tên PGD' column: {'YES' if pgd_col_found else 'NO'}")

# 3. Read PGD + TDN
df = pd.read_parquet(cache_path, columns=['Tên PGD', 'Tổng dư nợ', 'Mã KH', 'Số khế ước'])
df['Tổng dư nợ'] = pd.to_numeric(df['Tổng dư nợ'], errors='coerce').fillna(0)
df['Dư nợ quá hạn'] = pd.to_numeric(pd.read_parquet(cache_path, columns=['Dư nợ quá hạn'])['Dư nợ quá hạn'], errors='coerce').fillna(0) if True else 0

# Option B: read all needed cols at once
df2 = pd.read_parquet(cache_path, columns=['Tên PGD', 'Tổng dư nợ', 'Dư nợ quá hạn', 'Dư nợ khoanh', 'Mã KH', 'Số khế ước'])
for c in ['Tổng dư nợ', 'Dư nợ quá hạn', 'Dư nợ khoanh']:
    df2[c] = pd.to_numeric(df2[c], errors='coerce').fillna(0)

active = df2[(df2['Tổng dư nợ'] > 0) | (df2['Dư nợ quá hạn'] > 0) | (df2['Dư nợ khoanh'] > 0)]

pgds = sorted(df['Tên PGD'].unique())
print(f"\nPGD in cache: {len(pgds)}")
for pgd in pgds:
    sub = active[active['Tên PGD'] == pgd]
    tdn = sub['Tổng dư nợ'].sum() / 1e9
    print(f"  {pgd}: {len(sub):,} dòng, {tdn:,.1f} tỷ")

tdn_total = active['Tổng dư nợ'].sum() / 1e9
n_ku = active['Số khế ước'].nunique()
n_kh = active['Mã KH'].nunique()
print(f"\nTổng: {n_ku:,} món, {n_kh:,} KH, {tdn_total:,.1f} tỷ")
