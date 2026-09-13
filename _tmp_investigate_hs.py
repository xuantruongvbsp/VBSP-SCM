import duckdb

P = "cache/hstd.parquet"
HS = "Hội sở Chi nhánh tỉnh"

def run(label, sql):
    print("===", label, "===")
    print(duckdb.query(sql).df().to_string(index=False))

run("HS_TOTAL", f'SELECT SUM(TRY_CAST("Tổng dư nợ" AS DOUBLE))/1e9 AS ty FROM read_parquet(\'{P}\') WHERE "Tên PGD" = \'{HS}\'')
run("HS_BY_HTV", f'SELECT "Hình thức vay" AS htv, SUM(TRY_CAST("Tổng dư nợ" AS DOUBLE))/1e9 AS ty, COUNT(*) AS dong FROM read_parquet(\'{P}\') WHERE "Tên PGD" = \'{HS}\' GROUP BY 1 ORDER BY 2 DESC')
run("HS_THON_EMPTY", f'SELECT SUM(TRY_CAST("Tổng dư nợ" AS DOUBLE))/1e9 AS thon_empty_ty FROM read_parquet(\'{P}\') WHERE "Tên PGD" = \'{HS}\' AND (("Tên thôn" IS NULL) OR (TRIM(CAST("Tên thôn" AS VARCHAR)) = \'\'))')
run("HS_THON_NONEMPTY", f'SELECT SUM(TRY_CAST("Tổng dư nợ" AS DOUBLE))/1e9 AS thon_nonempty_ty FROM read_parquet(\'{P}\') WHERE "Tên PGD" = \'{HS}\' AND (("Tên thôn" IS NOT NULL) AND (TRIM(CAST("Tên thôn" AS VARCHAR)) <> \'\'))')
