"""Profile: _toi_uu_dtype() riêng"""
import time, pandas as pd

# Load dùng cache nếu mới chạy _prof2_ trước đó
from config import CACHE_HSTD
import duckdb
print("Loading parquet...")
arrow_tbl = duckdb.query(f'SELECT * FROM "{CACHE_HSTD}"').to_arrow_table()
df = arrow_tbl.to_pandas(self_destruct=True)
mb_before = df.memory_usage(deep=True).sum() / 1024 / 1024
print(f"Loaded: {df.shape[0]:,} rows × {df.shape[1]} cols, {mb_before:.0f} MB")

NGUONG = 200

t0 = time.perf_counter()
cat_count = 0
for col in df.select_dtypes(include="object").columns:
    try:
        if df[col].nunique(dropna=False) <= NGUONG:
            if col.lower().startswith("ngày"): continue
            vals = df[col].dropna()
            if len(vals) > 0:
                nv = pd.to_numeric(vals, errors="coerce")
                if nv.notna().sum() / len(vals) > 0.8:
                    df[col] = pd.to_numeric(df[col], errors="coerce"); continue
            df[col] = df[col].astype("category")
            cat_count += 1
    except: pass
t_cat = time.perf_counter() - t0
print(f"Object→category: {t_cat:.3f}s ({cat_count} cols)")

t0 = time.perf_counter()
f32 = 0
for col in df.select_dtypes(include="float64").columns:
    try:
        cm = df[col].abs().max(skipna=True)
        if pd.isna(cm) or cm < 1e9:
            df[col] = df[col].astype("float32"); f32 += 1
    except: pass
t_f32 = time.perf_counter() - t0
print(f"float64→float32: {t_f32:.3f}s ({f32} cols)")

t0 = time.perf_counter()
i = 0
for col in df.select_dtypes(include="int64").columns:
    try: df[col] = pd.to_numeric(df[col], downcast="integer"); i += 1
    except: pass
t_int = time.perf_counter() - t0
print(f"int→downcast: {t_int:.3f}s ({i} cols)")

mb_after = df.memory_usage(deep=True).sum() / 1024 / 1024
print(f"TOTAL optimize: {t_cat+t_f32+t_int:.3f}s  ({mb_before:.0f}→{mb_after:.0f} MB)")
