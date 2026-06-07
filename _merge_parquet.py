"""Merge using cached parquet files (hstd_khnv.parquet in each pgd dir) - MUCH faster."""
import pandas as pd
import numpy as np
from pathlib import Path
import unicodedata, re, os, time, shutil, warnings
warnings.filterwarnings('ignore')

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

COLS_SO = [
    'Dư nợ trong hạn','Dư nợ quá hạn','Dư nợ khoanh',
    'Tổng dư nợ','Lãi tồn TH','Lãi tồn QH',
    'Lãi DT trong tháng','Gốc đã trả','Mức vay',
    'Thời hạn vay',
]

pgd_data = Path('d:/VBSP-SCM/pgd_data')
cache_path = Path('d:/VBSP-SCM/cache/hstd.parquet')
log_path = Path('d:/VBSP-SCM/_merge_log.txt')

with open(log_path, 'w', encoding='utf-8') as log:
    t0 = time.time()
    
    # Backup
    if cache_path.exists():
        backup = cache_path.with_suffix('.parquet.bak')
        shutil.copy2(cache_path, backup)
        log.write(f"Backup: {backup.name}\n")
    
    tat_ca = [DON_VI_CHI_NHANH] + DS_PGD
    frames = []
    ok = 0
    
    for ten_pgd in tat_ca:
        s = slug(ten_pgd)
        dir_path = pgd_data / s
        
        # Try parquet first (fast), then Excel
        path = None
        for fname in ['hstd_khnv.parquet', 'hstd_khnv.xlsx', 'hstd_latest.xlsx']:
            p = dir_path / fname
            if p.exists():
                path = p
                break
        
        if not path:
            log.write(f"SKIP {ten_pgd}: no file\n")
            continue
        
        try:
            if path.suffix == '.parquet':
                df = pd.read_parquet(str(path))
            else:
                df = pd.read_excel(str(path), sheet_name='BCQUERY', header=4)
                df = df.iloc[:, 1:].dropna(how='all')
            
            # Ensure 'Tên PGD' column
            if COT_TEN_PGD in df.columns:
                df[COT_TEN_PGD] = ten_pgd
            else:
                df[COT_TEN_PGD] = ten_pgd
            
            frames.append(df)
            ok += 1
            log.write(f"OK {ten_pgd}: {len(df):,} rows\n")
        except Exception as e:
            log.write(f"FAIL {ten_pgd}: {e}\n")
    
    log.write(f"\nRead: {ok}/{len(tat_ca)} OK\n")
    log.flush()
    
    if not frames:
        log.write("NO FRAMES!\n")
        exit(1)
    
    # Unify schema
    all_cols = []
    for df in frames:
        for col in df.columns:
            if col not in all_cols:
                all_cols.append(col)
    log.write(f"Cols: {len(all_cols)}\n")
    
    frames2 = [df.reindex(columns=all_cols) for df in frames]
    df_merged = pd.concat(frames2, ignore_index=True)
    
    # Force numeric
    for col in COLS_SO:
        if col in df_merged.columns:
            df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce')
    
    # Clean strings
    BAD_VALS = {"nan", "None", "<NA>", "NaT", "NaN"}
    for col in df_merged.columns:
        if col not in COLS_SO:
            ser = df_merged[col]
            if hasattr(ser, 'cat'):
                ser = ser.astype(object)
            df_merged[col] = ser.fillna("").astype(str).replace(BAD_VALS, "").replace("nan","")
    
    # Write
    df_merged.to_parquet(cache_path, engine='pyarrow', index=False)
    
    elapsed = time.time() - t0
    size_mb = cache_path.stat().st_size / 1024 / 1024
    tdn = df_merged['Tổng dư nợ'].sum() / 1e9
    
    log.write(f"\n=== DONE ===\n")
    log.write(f"Time: {elapsed:.0f}s | Size: {size_mb:.1f} MB\n")
    log.write(f"PGDs: {df_merged[COT_TEN_PGD].nunique()} | Rows: {len(df_merged):,} | TDN: {tdn:,.1f} ty\n")
    
    for pgd in sorted(df_merged[COT_TEN_PGD].unique()):
        sub = df_merged[df_merged[COT_TEN_PGD] == pgd]
        tdn_p = sub['Tổng dư nợ'].sum() / 1e9
        log.write(f"  {pgd}: {len(sub):,} rows, {tdn_p:,.1f} ty\n")
    
    log.write("SUCCESS\n")
