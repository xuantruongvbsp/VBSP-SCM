import time, sys
sys.stdout.reconfigure(encoding='utf-8')

t0 = time.perf_counter()
import duckdb
t1 = time.perf_counter()
print(f"duckdb import: {t1-t0:.3f}s")

path = r"D:\VBSP-SCM\cache\hstd.parquet"
t0 = time.perf_counter()
r = duckdb.query(f'SELECT count(*) FROM "{path}"').fetchone()
t1 = time.perf_counter()
print(f"count(*) query: {t1-t0:.3f}s, rows={r[0]:,}")

t0 = time.perf_counter()
arrow_tbl = duckdb.query(f'SELECT * FROM "{path}"').to_arrow_table()
t1 = time.perf_counter()
print(f"SELECT * to Arrow: {t1-t0:.3f}s, {arrow_tbl.num_rows:,} rows x {arrow_tbl.num_columns} cols, {arrow_tbl.nbytes/1024/1024:.0f} MB")

import pandas as pd
t0 = time.perf_counter()
df = arrow_tbl.to_pandas(self_destruct=True)
t1 = time.perf_counter()
mb = df.memory_usage(deep=True).sum() / 1024 / 1024
print(f"Arrow to pandas: {t1-t0:.3f}s, {mb:.0f} MB")
