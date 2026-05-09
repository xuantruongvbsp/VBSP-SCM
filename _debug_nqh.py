"""Debug: check Unicode normalization of column names"""
import unicodedata, pandas as pd, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'c:\VBSP-SCM')

path = r'c:\VBSP-SCM\cache\hstd.parquet'
df = pd.read_parquet(path)

# Find NQH-related columns
target = "Dư nợ quá hạn"
col = [c for c in df.columns if target.lower() in c.lower()]
if col:
    c = col[0]
    print(f"Found column: {repr(c)}")
    print(f"  is NFC: {unicodedata.is_normalized('NFC', c)}")
    print(f"  is NFD: {unicodedata.is_normalized('NFD', c)}")
    print(f"  normalize NFC: {repr(unicodedata.normalize('NFC', c))}")
else:
    print(f"Column '{target}' not found via fuzzy match!")
    print(f"Similar cols: {[c for c in df.columns if 'du' in c.lower()]}")

import config
cc = config.COT_DU_NO_QH
print(f"\nConfig COT_DU_NO_QH: {repr(cc)}")
print(f"  is NFC: {unicodedata.is_normalized('NFC', cc)}")
print(f"  is NFD: {unicodedata.is_normalized('NFD', cc)}")

if col:
    print(f"\nExact match: {col[0] == cc}")
    print(f"NFC match: {unicodedata.normalize('NFC', col[0]) == unicodedata.normalize('NFC', cc)}")

# Check CQH columns
cqh_cols = ["Chuyển QH trong tháng", "CQH trong Quý", "CQH Năm"]
for cqh in cqh_cols:
    found = [c for c in df.columns if cqh.lower() in c.lower()]
    if found:
        print(f"\n'{cqh}' -> {repr(found[0])}")
        print(f"  Exact match: {found[0] == cqh}")
    else:
        print(f"\n'{cqh}' NOT found!")

print(f"\nTotal rows: {len(df)}")
s = pd.to_numeric(df["Dư nợ quá hạn"], errors="coerce").fillna(0)
print(f"NQH > 0: {(s > 0).sum()}")

# Check CQH thang values
cqh_col = "Chuyển QH trong tháng"
if cqh_col in df.columns:
    cqh_s = pd.to_numeric(df[cqh_col], errors="coerce").fillna(0)
    print(f"\n'{cqh_col}' > 0: {(cqh_s > 0).sum()}")
