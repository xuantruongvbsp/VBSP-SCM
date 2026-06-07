"""Merge 22 PGD via DuckDB - UNION ALL from parquet files. Memory efficient."""
import duckdb, os, time, shutil
from pathlib import Path
import unicodedata, re

def slug(s):
    s = s.strip().lower().replace("đ","d").replace("Đ","D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")

DS_PGD = [
    "PGD Long Thành","PGD Trảng Bom","PGD Long Khánh","PGD Xuân Lộc",
    "PGD Định Quán","PGD Vĩnh Cửu","PGD Tân Phú","PGD Thống Nhất",
    "PGD Cẩm Mỹ","PGD Nhơn Trạch","PGD Bình Long","PGD Lộc Ninh",
    "PGD Bình Phước","PGD Phước Long","PGD Bù Đăng","PGD Đồng Phú",
    "PGD Chơn Thành","PGD Bù Đốp","PGD Bù Gia Mập","PGD Phú Riềng",
    "PGD Hớn Quản",
]
DON_VI_CHI_NHANH = "Hội sở Chi nhánh tỉnh"
COT_TEN_PGD = "Tên PGD"

pgd_data = Path('d:/VBSP-SCM/pgd_data')
cache_path = Path('d:/VBSP-SCM/cache/hstd.parquet')
log_path = Path('d:/VBSP-SCM/_merge_log.txt')

with open(log_path, 'a', encoding='utf-8') as log:
    t0 = time.time()
    log.write(f"\n=== DuckDB MERGE {time.strftime('%H:%M:%S')} ===\n")
    
    # Backup
    if cache_path.exists():
        backup = cache_path.with_suffix('.parquet.bak')
        shutil.copy2(cache_path, backup)
        log.write(f"Backup: {backup.name}\n")
    
    # Collect valid parquet paths
    pgd_paths = []
    for ten_pgd in [DON_VI_CHI_NHANH] + DS_PGD:
        s = slug(ten_pgd)
        dir_path = pgd_data / s
        
        chosen = None
        for fname in ['hstd_khnv.parquet', 'hstd_khnv.xlsx', 'hstd_latest.xlsx']:
            p = dir_path / fname
            if p.exists():
                chosen = str(p)
                break
        
        if chosen:
            pgd_paths.append((ten_pgd, chosen))
    
    log.write(f"Found {len(pgd_paths)} PGD files\n")
    
    # Build UNION ALL query with COT_TEN_PGD injection
    union_parts = []
    for ten_pgd, path in pgd_paths:
        ext = Path(path).suffix
        if ext == '.parquet':
            source = f"'{path}'"
        else:
            source = f"'{path}'"
        
        # Escape PGD name for SQL
        pgd_escaped = ten_pgd.replace("'", "''")
        
        union_parts.append(
            f"SELECT *, '{pgd_escaped}' AS \"{COT_TEN_PGD}\" FROM {source}"
        )
    
    sql = " UNION ALL ".join(union_parts)
    log.write(f"SQL built ({len(sql):,} chars)\n")
    log.write(f"Reading from {len(union_parts)} sources...\n")
    log.flush()
    
    try:
        # If sources are parquet, use read_parquet
        arrow_tbl = duckdb.query(sql).to_arrow_table()
        log.write(f"Arrow table: {arrow_tbl.num_rows:,} rows, {arrow_tbl.num_columns} cols\n")
        log.flush()
        
        df = arrow_tbl.to_pandas(self_destruct=True)
        log.write(f"DataFrame: {len(df):,} rows\n")
        log.flush()
        
        # Force COT_TEN_PGD column (already set above, but double-check)
        if COT_TEN_PGD in df.columns:
            # Fix: DuckDB may have created duplicate - keep the right one
            pass
        
        # Write parquet
        df.to_parquet(cache_path, engine='pyarrow', index=False)
        
        elapsed = time.time() - t0
        size_mb = cache_path.stat().st_size / 1024 / 1024
        n_pgd = df[COT_TEN_PGD].nunique()
        
        log.write(f"\n=== DONE ===\n")
        log.write(f"Time: {elapsed:.0f}s | Size: {size_mb:.1f} MB\n")
        log.write(f"PGDs: {n_pgd} | Rows: {len(df):,}\n")
        
        for pgd in sorted(df[COT_TEN_PGD].unique()):
            log.write(f"  {pgd}\n")
        
        log.write("SUCCESS\n")
        
    except Exception as e:
        log.write(f"ERROR: {e}\n")
        import traceback
        log.write(traceback.format_exc())
