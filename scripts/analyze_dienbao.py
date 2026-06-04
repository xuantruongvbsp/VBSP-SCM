"""Phân tích cấu trúc file DIEN BAO NGAY CN.xlsx"""
import pandas as pd
from pathlib import Path

FP = Path(r"D:\VBSP-SCM\docs\MAU BAO CAO KHNV\DIEN BAO NGAY CN.xlsx")

if not FP.exists():
    print(f"KHÔNG TÌM THẤY FILE: {FP}")
    exit(1)

xls = pd.ExcelFile(FP)
print(f"📑 Số sheet: {len(xls.sheet_names)}")
print(f"📑 Tên sheets: {xls.sheet_names}\n")

for sheet in xls.sheet_names:
    df = pd.read_excel(FP, sheet_name=sheet, header=None)
    print(f"\n{'='*80}")
    print(f"📋 Sheet: '{sheet}' — shape: {df.shape}")
    print(f"{'='*80}")
    
    n_rows = min(120, len(df))
    for i in range(n_rows):
        row_vals = []
        for j in range(min(12, len(df.columns))):
            v = df.iloc[i, j]
            if pd.isna(v):
                row_vals.append("NaN")
            else:
                s = str(v).strip()[:50]
                row_vals.append(s)
        line = " | ".join(row_vals)
        if any(x != "NaN" for x in row_vals):
            print(f"  [{i:3d}] {line}")

print("\n\n=== PHÂN TÍCH CHI TIẾT ===")

for sheet in xls.sheet_names:
    df = pd.read_excel(FP, sheet_name=sheet, header=None)
    
    # Đếm dòng không trống
    non_empty = 0
    for i in range(len(df)):
        if any(pd.notna(df.iloc[i, j]) for j in range(min(5, len(df.columns)))):
            non_empty += 1
    
    print(f"\nSheet '{sheet}': {non_empty}/{len(df)} dòng có dữ liệu")
    
    # Liệt kê các giá trị có thể là chỉ tiêu (cột 1 - index 1)
    if len(df.columns) >= 2:
        chi_tieu = []
        for i in range(len(df)):
            v = df.iloc[i, 1]
            if pd.notna(v):
                s = str(v).strip()
                if s and s not in ("nan", "Chỉ tiêu", "Điện báo ngày", ""):
                    chi_tieu.append((i, s))
        print(f"  Số chỉ tiêu: {len(chi_tieu)}")
        for idx, name in chi_tieu[:50]:
            print(f"    [{idx:3d}] {name[:80]}")
        if len(chi_tieu) > 50:
            print(f"    ... và {len(chi_tieu)-50} chỉ tiêu khác")
