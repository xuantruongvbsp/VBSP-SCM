"""
Profile cold start bottlenecks — đo thời gian thực từng bước.
Chạy: python _profile_cold_start.py
"""
import time
import os
import sys

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def measure(name, fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    print(f"  {name:<50} {elapsed:>8.3f}s")
    return result, elapsed

# ── 1. Import top-level modules ──────────────────────────────────────────
section("1. Top-level imports (Python parse + bytecode)")

t0 = time.perf_counter()
import auth
t_auth = time.perf_counter() - t0
print(f"  {'auth.py:':<50} {t_auth:>8.3f}s  ({os.path.getsize('auth.py')/1024:.0f} KB)")

t0 = time.perf_counter()
from config import COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_MA_KH, CACHE_HSTD, FILE_PATH, TEN_FILE, FILE_PATH_NQ11, TEN_FILE_NQ11, FILE_PATH_DB, TEN_FILE_DB, TEN_FILE_DB_PREV, FILE_PATH_DB_PREV
t_config = time.perf_counter() - t0
print(f"  {'config.py:':<50} {t_config:>8.3f}s  ({os.path.getsize('config.py')/1024:.0f} KB)")

t0 = time.perf_counter()
import db
t_db = time.perf_counter() - t0
print(f"  {'db.py:':<50} {t_db:>8.3f}s  ({os.path.getsize('db.py')/1024:.0f} KB)")

t0 = time.perf_counter()
import workspaces
t_ws = time.perf_counter() - t0
print(f"  {'workspaces:':<50} {t_ws:>8.3f}s")

t0 = time.perf_counter()
import duckdb
t_duckdb = time.perf_counter() - t0
print(f"  {'duckdb:':<50} {t_duckdb:>8.3f}s")

t0 = time.perf_counter()
import pandas as pd
t_pandas = time.perf_counter() - t0
print(f"  {'pandas:':<50} {t_pandas:>8.3f}s")

t0 = time.perf_counter()
import streamlit as st
t_st = time.perf_counter() - t0
print(f"  {'streamlit:':<50} {t_st:>8.3f}s")

total_import = t_auth + t_config + t_db + t_ws + t_duckdb + t_pandas + t_st
print(f"  {'TOTAL imports:':<50} {total_import:>8.3f}s")

# ── 2. Parquet cache files ──────────────────────────────────────────────
section("2. Parquet cache files")

from config import CACHE_HSTD
cache_files = [
    ("cache/hstd.parquet", CACHE_HSTD),
]
import glob as _glob
for f in _glob.glob("cache/*.parquet"):
    cache_files.append((f, f))

for label, path in cache_files:
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / 1024 / 1024
        mtime = time.ctime(os.path.getmtime(path))
        print(f"  {label:<50} {size_mb:>7.1f} MB  ({mtime})")
    else:
        print(f"  {label:<50} NOT FOUND")

# ── 3. DuckDB load from parquet ─────────────────────────────────────────
section("3. DuckDB load from parquet (SELECT *)")

if os.path.exists(CACHE_HSTD):
    t0 = time.perf_counter()
    import duckdb
    arrow_tbl = duckdb.query(f'SELECT * FROM "{CACHE_HSTD}"').to_arrow_table()
    t_query = time.perf_counter() - t0
    nrows = arrow_tbl.num_rows
    ncols = arrow_tbl.num_columns
    mb_arrow = arrow_tbl.nbytes / 1024 / 1024
    print(f"  {'DuckDB query + Arrow table:':<50} {t_query:>8.3f}s  ({nrows:,} rows × {ncols} cols, {mb_arrow:.0f} MB)")

    t0 = time.perf_counter()
    df = arrow_tbl.to_pandas(self_destruct=True)
    t_topd = time.perf_counter() - t0
    mb_pd = df.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"  {'Arrow → pandas (self_destruct):':<50} {t_topd:>8.3f}s  ({mb_pd:.0f} MB pandas)")

    # ── 4. _toi_uu_dtype ────────────────────────────────────────────────
    section("4. _toi_uu_dtype() optimization")

    NGUONG_CATEGORY = 200

    t0 = time.perf_counter()
    cat_count = 0
    for col in df.select_dtypes(include="object").columns:
        try:
            if df[col].nunique(dropna=False) <= NGUONG_CATEGORY:
                if col.lower().startswith("ngày"):
                    continue
                vals = df[col].dropna()
                if len(vals) > 0:
                    numeric_vals = pd.to_numeric(vals, errors="coerce")
                    ty_le_so = numeric_vals.notna().sum() / len(vals)
                    if ty_le_so > 0.8:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                        continue
                df[col] = df[col].astype("category")
                cat_count += 1
        except Exception:
            pass
    t_cat = time.perf_counter() - t0
    print(f"  {'Object → category (step 1):':<50} {t_cat:>8.3f}s  ({cat_count} columns converted)")

    t0 = time.perf_counter()
    f32_count = 0
    for col in df.select_dtypes(include="float64").columns:
        try:
            col_max = df[col].abs().max(skipna=True)
            if pd.isna(col_max) or col_max < 1e9:
                df[col] = df[col].astype("float32")
                f32_count += 1
        except Exception:
            pass
    t_f32 = time.perf_counter() - t0
    print(f"  {'float64 → float32 (step 2):':<50} {t_f32:>8.3f}s  ({f32_count} columns converted)")

    t0 = time.perf_counter()
    i_count = 0
    for col in df.select_dtypes(include="int64").columns:
        try:
            df[col] = pd.to_numeric(df[col], downcast="integer")
            i_count += 1
        except Exception:
            pass
    t_int = time.perf_counter() - t0
    print(f"  {'int64 → downcast (step 3):':<50} {t_int:>8.3f}s  ({i_count} columns converted)")

    total_opt = t_cat + t_f32 + t_int
    mb_after = df.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"  {'TOTAL _toi_uu_dtype():':<50} {total_opt:>8.3f}s  ({mb_pd:.0f} → {mb_after:.0f} MB, saved {mb_pd-mb_after:.0f} MB)")

    # ── Summary ─────────────────────────────────────────────────────────
    section("5. SUMMARY: Full _load_hstd() emulation")
    total_load = t_query + t_topd + total_opt
    print(f"  {'======== COLD START _load_hstd() ========':<50}")
    print(f"  {'DuckDB query:':<50} {t_query:>8.3f}s")
    print(f"  {'Arrow → pandas:':<50} {t_topd:>8.3f}s")
    print(f"  {'_toi_uu_dtype():':<50} {total_opt:>8.3f}s")
    print(f"  {'TOTAL data load:':<50} {total_load:>8.3f}s")
    print()
    print(f"  {'======== COLD START FULL ========':<50}")
    total_all = total_import + total_load
    print(f"  {'Imports:':<50} {total_import:>8.3f}s")
    print(f"  {'Data load:':<50} {total_load:>8.3f}s")
    print(f"  {'TOTAL cold start:':<50} {total_all:>8.3f}s")
    print()
    print(f"  {'Breakdown:':<50}")
    print(f"  {'  - imports:':<50} {total_import/total_all*100:>7.1f}%")
    print(f"  {'  - data load:':<50} {total_load/total_all*100:>7.1f}%")
else:
    print(f"  ⚠️  {CACHE_HSTD} NOT FOUND — cannot profile")

print()
