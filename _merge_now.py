"""
Standalone merge: read ALL 22 PGD HSTD XLSX files + concat → cache/hstd.parquet
Mimics merge_du_lieu_toan_cn("hstd") without Streamlit imports.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import unicodedata, re, os, warnings, time
warnings.filterwarnings('ignore')

# ── Constants ──
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

# Money columns to force numeric
COLS_SO = [
    'Dư nợ trong hạn','Dư nợ quá hạn','Dư nợ khoanh',
    'Tổng dư nợ','Lãi tồn TH','Lãi tồn QH',
    'Lãi DT trong tháng','Gốc đã trả','Mức vay',
    'Thời hạn vay',
]

def slug(s):
    s = s.strip().lower().replace("đ","d").replace("Đ","D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")

pgd_data = Path('d:/VBSP-SCM/pgd_data')
cache_path = Path('d:/VBSP-SCM/cache/hstd.parquet')

# Backup existing cache
if cache_path.exists():
    backup = cache_path.with_suffix('.parquet.bak')
    import shutil
    shutil.copy2(cache_path, backup)
    print(f"Backup: {backup.name}")

tat_ca = [DON_VI_CHI_NHANH] + DS_PGD
frames = []
ok = 0
fail = 0

t0 = time.time()
for ten_pgd in tat_ca:
    s = slug(ten_pgd)
    dir_path = pgd_data / s
    
    # Priority: hstd_khnv.xlsx (KH-NV upload) → hstd_latest.xlsx (PGD upload)
    path = None
    for fname in ['hstd_khnv.xlsx', 'hstd_latest.xlsx']:
        p = dir_path / fname
        if p.exists():
            path = p
            break
    
    if not path:
        print(f"  SKIP {ten_pgd}: no file in {s}/")
        fail += 1
        continue
    
    try:
        # Read like merge: header=4, drop col 0, drop all-nan rows
        df = pd.read_excel(str(path), sheet_name='BCQUERY', header=4)
        df = df.iloc[:, 1:].dropna(how='all')
        df[COT_TEN_PGD] = ten_pgd
        frames.append(df)
        ok += 1
        print(f"  OK {ten_pgd}: {len(df):,} rows ({path.stat().st_size/1024/1024:.0f} MB)")
    except Exception as e:
        print(f"  FAIL {ten_pgd}: {e}")
        fail += 1

print(f"\nRead: {ok} OK, {fail} fail / {len(tat_ca)}")

if not frames:
    print("No frames to merge!")
    exit(1)

# Unify schema
all_cols = []
for df in frames:
    for col in df.columns:
        if col not in all_cols:
            all_cols.append(col)
print(f"Total columns: {len(all_cols)}")

# Reindex
frames2 = []
for df in frames:
    frames2.append(df.reindex(columns=all_cols))

df_merged = pd.concat(frames2, ignore_index=True)
print(f"Merged: {len(df_merged):,} rows")

# Force numeric
for col in COLS_SO:
    if col in df_merged.columns:
        df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce')

# Clean string cols
BAD_VALS = {"nan", "None", "<NA>", "NaT"}
str_cols = [c for c in df_merged.columns if c not in COLS_SO]
for col in str_cols:
    ser = df_merged[col]
    if hasattr(ser.dtype, 'categories'):  # Categorical
        ser = ser.astype(object)
    df_merged[col] = ser.astype(str).replace(BAD_VALS, "").replace("nan", "").replace("None", "")

# Write parquet
os.makedirs(cache_path.parent, exist_ok=True)
df_merged.to_parquet(cache_path, engine='pyarrow', index=False)

elapsed = time.time() - t0
size_mb = cache_path.stat().st_size / 1024 / 1024

# Verify
tdn = df_merged['Tổng dư nợ'].sum() / 1e9
n_ku = df_merged['Số khế ước'].nunique() if 'Số khế ước' in df_merged.columns else 'N/A'
n_kh = df_merged['Mã KH'].nunique() if 'Mã KH' in df_merged.columns else 'N/A'
n_pgd = df_merged[COT_TEN_PGD].nunique()

print(f"\n=== MERGE COMPLETE ===")
print(f"File: {cache_path} ({size_mb:.1f} MB)")
print(f"Time: {elapsed:.1f}s")
print(f"PGDs: {n_pgd}")
print(f"Rows: {len(df_merged):,}")
print(f"TDN: {tdn:,.1f} ty")
print(f"KU: {n_ku}")
print(f"KH: {n_kh}")

# Per-PGD breakdown
for pgd in sorted(df_merged[COT_TEN_PGD].unique()):
    sub = df_merged[df_merged[COT_TEN_PGD] == pgd]
    tdn_p = sub['Tổng dư nợ'].sum() / 1e9
    print(f"  {pgd}: {len(sub):,} rows, {tdn_p:,.1f} ty")
