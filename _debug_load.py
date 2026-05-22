import sys, duckdb, pandas as pd
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from config import CACHE_HSTD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH

cache = CACHE_HSTD.replace('\\', '/')
print('Cache path:', cache)

# 1) Total rows
try:
    r1 = duckdb.query(f'SELECT COUNT(*) as n FROM "{cache}"').df()
    print('Total rows:', r1['n'].iloc[0])
except Exception as e:  # conv: skip
    print('QUERY FULL ERROR:', e)

# 2) active_only query
sql = (f'SELECT COUNT(*) as n FROM "{cache}" WHERE '
       f'("{COT_TONG_DU_NO}" > 0 OR "{COT_DU_NO_QH}" > 0 OR "{COT_DU_NO_KHOANH}" > 0)')
try:
    r2 = duckdb.query(sql).df()
    print('Active rows (du_no > 0):', r2['n'].iloc[0])
except Exception as e:  # conv: skip
    print('QUERY ACTIVE_ONLY ERROR:', e)
    df_s = pd.read_parquet(cache, columns=[COT_TONG_DU_NO])
    print('  dtype:', df_s[COT_TONG_DU_NO].dtype)
    print('  sample:', df_s[COT_TONG_DU_NO].head(3).tolist())
