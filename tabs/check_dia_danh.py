"""Script kiểm tra nhất quán tên địa danh trong HSTD vs config."""
import pandas as pd
from config import PGD_XA_MAP
import unicodedata
import re

def chuan_hoa(s):
    """Chuẩn hóa để so sánh."""
    s = unicodedata.normalize('NFD', str(s).strip().lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\b(xa|phuong|thi tran|tt)\b', '', s)
    return re.sub(r'\s+', ' ', s).strip()

# Đọc HSTD
print("Đang đọc HSTD...")
try:
    df = pd.read_excel('HSTD_Du_lieu_tho.XLSX', sheet_name='BCQUERY', header=4)
    df = df.iloc[:, 1:].dropna(how='all')
except FileNotFoundError:
    print("❌ Không tìm thấy file HSTD_Du_lieu_tho.XLSX")
    print("Đảm bảo file nằm cùng thư mục với script này.")
    exit(1)
except Exception as e:
    print(f"❌ Lỗi đọc file: {e}")
    exit(1)

print("\n" + "="*80)
print("KIỂM TRA NHẤT QUÁN TÊN ĐỊA DANH")
print("="*80)

# 1. XÃ
print("\n📍 1. TÊN XÃ:")
print("-"*80)

xa_config = set()
for pgd, ds in PGD_XA_MAP.items():
    xa_config.update(ds)

xa_hstd = set(df["Tên xã"].dropna().unique())

print(f"Config (PGD_XA_MAP): {len(xa_config)} xã")
print(f"HSTD (file data):    {len(xa_hstd)} xã")

# Tìm xã không khớp
mapping_can_sua = {}
xa_config_khong_co_hstd = []

for xa_cfg in sorted(xa_config):
    found = False
    if xa_cfg in xa_hstd:
        found = True
    else:
        # Fuzzy match
        cfg_norm = chuan_hoa(xa_cfg)
        for xa_h in xa_hstd:
            if chuan_hoa(xa_h) == cfg_norm:
                mapping_can_sua[xa_cfg] = xa_h
                found = True
                break
    
    if not found:
        xa_config_khong_co_hstd.append(xa_cfg)

if xa_config_khong_co_hstd:
    print(f"\n⚠️ Config có {len(xa_config_khong_co_hstd)} xã CHƯA CÓ trong HSTD (có thể chưa upload):")
    for xa in xa_config_khong_co_hstd[:10]:  # Show 10 đầu
        print(f"  - {xa}")
    if len(xa_config_khong_co_hstd) > 10:
        print(f"  ... và {len(xa_config_khong_co_hstd) - 10} xã khác")

if mapping_can_sua:
    print(f"\n⚠️ CẦN SỬA {len(mapping_can_sua)} XÃ (tên không khớp chính xác):")
    print()
    for cfg, hstd in sorted(mapping_can_sua.items()):
        print(f"  Config:  '{cfg}'")
        print(f"  HSTD:    '{hstd}'")
        print(f"  Chuẩn hóa: '{chuan_hoa(cfg)}' == '{chuan_hoa(hstd)}'")
        print()

# 2. THÔN/ẤP
print("\n📍 2. TÊN THÔN/ẤP:")
print("-"*80)

thon_list = df["Tên thôn"].dropna().unique()
print(f"Tổng: {len(thon_list)} thôn/ấp")

# Phân loại
ap = sum(1 for t in thon_list if 'Ấp' in str(t))
thon = sum(1 for t in thon_list if 'Thôn' in str(t))
kp = sum(1 for t in thon_list if any(x in str(t) for x in ['KP', 'Khu phố']))
khac = len(thon_list) - ap - thon - kp

print(f"  Ấp:      {ap}")
print(f"  Thôn:    {thon}")
print(f"  KP:      {kp}")
print(f"  Khác:    {khac}")

if khac > 0:
    print("\n  Các tên không theo pattern chuẩn:")
    other_list = [t for t in sorted(thon_list) 
                  if not any(x in str(t) for x in ['Ấp', 'Thôn', 'KP', 'Khu phố'])]
    for t in other_list[:20]:  # Show 20 đầu
        print(f"    - {t}")
    if len(other_list) > 20:
        print(f"    ... và {len(other_list) - 20} thôn/ấp khác")

# 3. SAMPLE
print("\n📍 3. SAMPLE DỮ LIỆU (3 PGD đầu có data):")
print("-"*80)

pgd_list = df["Tên PGD"].dropna().unique()
for pgd in sorted(pgd_list)[:3]:
    print(f"\n{pgd}:")
    df_pgd = df[df["Tên PGD"] == pgd]
    xa_list = df_pgd["Tên xã"].unique()
    for xa in sorted(xa_list)[:2]:  # 2 xã đầu
        thon_xa = df_pgd[df_pgd["Tên xã"] == xa]["Tén thôn"].unique()
        print(f"  {xa}: {len(thon_xa)} thôn/ấp")
        for t in sorted(thon_xa)[:3]:  # 3 thôn đầu
            print(f"    → {t}")

# 4. EXPORT MAPPING
print("\n" + "="*80)
print("✅ KIỂM TRA XONG!")
print("="*80)

if mapping_can_sua:
    print("\n🔧 COPY DICT SAU ĐÂY VÀO config.py:")
    print("\n# Mapping tên xã: HSTD → Config")
    print("XA_NAME_MAP = {")
    for hstd, cfg in sorted(mapping_can_sua.items()):
        print(f'    "{hstd}": "{cfg}",  # {hstd} (HSTD) → {cfg} (Config)')
    print("}")
    
    print("\n📝 SAU KHI THÊM VÀO config.py, dùng hàm này để map:")
    print("""
def tim_ten_xa_trong_hstd(ten_xa_config: str, df: pd.DataFrame) -> str:
    '''Tìm tên xã trong HSTD khớp với tên trong config.'''
    # Thử exact match trước
    if ten_xa_config in df["Tên xã"].values:
        return ten_xa_config
    
    # Dùng mapping
    for hstd_name, cfg_name in XA_NAME_MAP.items():
        if cfg_name == ten_xa_config:
            return hstd_name
    
    # Không tìm thấy
    return None
""")
else:
    print("\n✅ Không có xã nào cần sửa mapping!")

print("\n" + "="*80)
