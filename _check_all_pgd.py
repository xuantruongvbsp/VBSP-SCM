from pathlib import Path
import os

pgd_data = Path('d:/VBSP-SCM/pgd_data')
dirs = sorted([d for d in pgd_data.iterdir() if d.is_dir()])

print("=== TẤT CẢ THƯ MỤC PGD & FILE HIỆN CÓ ===")
total_with_files = 0
for d in dirs:
    files = list(d.glob('*.xlsx')) + list(d.glob('*.parquet'))
    if files:
        total_with_files += 1
        print(f"\n📁 {d.name}:")
        for f in sorted(files):
            size_kb = f.stat().st_size / 1024
            print(f"   ✅ {f.name} ({size_kb:,.0f} KB)")
    else:
        print(f"\n📁 {d.name}: (trống)")

print(f"\n=== Tổng: {total_with_files}/{len(dirs)} thư mục có file ===")

# Kiểm tra data/ directory
print("\n=== FILE TRONG data/ ===")
data_dir = Path('d:/VBSP-SCM/data')
if data_dir.exists():
    xlsx_files = list(data_dir.glob('*.xlsx'))
    for f in sorted(xlsx_files):
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {f.name} ({size_mb:,.1f} MB)")

# Kiểm tra cache/
print("\n=== FILE TRONG cache/ ===")
cache_dir = Path('d:/VBSP-SCM/cache')
for f in sorted(cache_dir.iterdir()):
    if f.is_file():
        size_mb = f.stat().st_size / 1024 / 1024
        mtime = os.path.getmtime(str(f))
        from datetime import datetime
        dt = datetime.fromtimestamp(mtime)
        print(f"  {f.name} ({size_mb:,.1f} MB) - {dt.strftime('%d/%m/%Y %H:%M')}")
