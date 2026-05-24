"""Profile: parquet cache size + DuckDB load time"""
import time, os
from config import CACHE_HSTD

print(f"Parquet file: {CACHE_HSTD}")
if os.path.exists(CACHE_HSTD):
    sz = os.path.getsize(CACHE_HSTD) / 1024 / 1024
    print(f"Size: {sz:.1f} MB")
    
    import duckdb
    t0 = time.perf_counter()
    arrow_tbl = duckdb.query(f'SELECT * FROM "{CACHE_HSTD}"').to_arrow_table()
    t1 = time.perf_counter() - t0
    print(f"DuckDB query → Arrow: {t1:.3f}s  ({arrow_tbl.num_rows:,} rows × {arrow_tbl.num_columns} cols, {arrow_tbl.nbytes/1024/1024:.0f} MB)")

    import pandas as pd
    t0 = time.perf_counter()
    df = arrow_tbl.to_pandas(self_destruct=True)
    t2 = time.perf_counter() - t0
    mb = df.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"Arrow → pandas: {t2:.3f}s  ({mb:.0f} MB)")
    print(f"TOTAL load: {t1+t2:.3f}s")
else:
    print("NOT FOUND")
