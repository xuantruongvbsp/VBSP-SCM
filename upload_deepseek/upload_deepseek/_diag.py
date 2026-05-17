import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import duckdb, os
os.chdir("D:/VBSP-SCM")
cache = "cache/hstd.parquet"
conn = duckdb.connect(":memory:")

# Số PGD có dữ liệu
r = conn.execute(f"""
    SELECT "Tên PGD", COUNT(*) as so_hang, COUNT(DISTINCT "Mã KH") as so_kh,
           SUM("Tổng dư nợ") as tong_du_no
    FROM read_parquet('{cache}')
    WHERE "Tổng dư nợ" > 0
    GROUP BY "Tên PGD"
    ORDER BY tong_du_no DESC
""").fetchdf()
print(f"Số PGD có dữ liệu: {len(r)}")
print(r.to_string())

# Số KH bị duplicate (cùng Mã KH, cùng Số khế ước)
dup = conn.execute(f"""
    SELECT COUNT(*) FROM (
        SELECT "Mã KH", "Số khế ước", COUNT(*) as cnt
        FROM read_parquet('{cache}')
        WHERE "Tổng dư nợ" > 0
        GROUP BY "Mã KH", "Số khế ước"
        HAVING COUNT(*) > 1
    )
""").fetchone()[0]
print(f"\nSố cặp (Mã KH, Số khế ước) bị duplicate: {dup:,}")
conn.close()
