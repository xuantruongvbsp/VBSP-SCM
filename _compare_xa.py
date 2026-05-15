import sys, re
sys.stdout.reconfigure(encoding='utf-8')

official_95 = [
    'An Lộc','Biên Hòa','Bình Long','Bình Lộc','Bình Phước',
    'Bảo Vinh','Chơn Thành','Đồng Xoài','Hàng Gòn','Hố Nai',
    'Long Bình','Long Hưng','Long Khánh','Minh Hưng','Phước Bình',
    'Phước Long','Phước Tân','Tam Hiệp','Tam Phước','Trảng Dài',
    'Trấn Biên','Tân Triều','Xuân Lập','An Phước','An Viễn',
    'Bom Bo','Bàu Hàm','Bình An','Bình Minh','Bình Tân',
    'Bù Gia Mập','Bù Đăng','Cẩm Mỹ','Dầu Giây','Đa Kia',
    'Đak Lua','Đak Nhau','Đăk Ơ','Đại Phước','Định Quán',
    'Đồng Phú','Đồng Tâm','Gia Kiệm','Hưng Phước','Hưng Thịnh',
    'La Ngà','Long Hà','Long Phước','Long Thành','Lộc Hưng',
    'Lộc Ninh','Lộc Quang','Lộc Thành','Lộc Thạnh','Lộc Tấn',
    'Minh Đức','Nam Cát Tiên','Nghĩa Trung','Nha Bích','Nhơn Trạch',
    'Phú Hòa','Phú Lâm','Phú Lý','Phú Nghĩa','Phú Riềng',
    'Phú Trung','Phú Vinh','Phước An','Phước Sơn','Phước Thái',
    'Sông Ray','Thanh Sơn','Thiện Hưng','Thuận Lợi','Thọ Sơn',
    'Thống Nhất','Trảng Bom','Trị An','Tà Lài','Tân An',
    'Tân Hưng','Tân Khai','Tân Lợi','Tân Phú','Tân Quan',
    'Tân Tiến','Xuân Bắc','Xuân Hòa','Xuân Lộc','Xuân Phú',
    'Xuân Quế','Xuân Thành','Xuân Đông','Xuân Đường','Xuân Định',
]

with open('config.py', encoding='utf-8') as f:
    src = f.read()

# Split at XA_THON_MAP to separate PGD_XA_MAP section
split_pos = src.find('XA_THON_MAP')
pgd_section = src[:split_pos]
xt_section = src[split_pos:]

# Extract all "Xã X" and "Phường X" from PGD_XA_MAP section
pgd_xa_full = re.findall(r'"((?:Xã|Phường) [^"]+)"', pgd_section)
pgd_xa_names_raw = [x.split(' ', 1)[1] for x in pgd_xa_full]
pgd_xa_names = sorted(set(pgd_xa_names_raw))
# check duplicates
from collections import Counter
dups = [k for k,v in Counter(pgd_xa_names_raw).items() if v > 1]

# Extract XA_THON_MAP keys
xt_full = re.findall(r"'((?:Xã|Phường) [^']+)'\s*:", xt_section)
xt_names = sorted(set(x.split(' ', 1)[1] for x in xt_full))

official_set = set(official_95)

print('=== OFFICIAL 95 — thiếu trong PGD_XA_MAP ===')
missing_pgd = [x for x in official_95 if x not in set(pgd_xa_names)]
for x in missing_pgd:
    print(' -', x)

print()
print('=== PGD_XA_MAP — THỪA so với official 95 ===')
extra_pgd = [x for x in pgd_xa_names if x not in official_set]
for x in extra_pgd:
    print(' +', x)

if dups:
    print()
    print('=== PGD_XA_MAP — TRÙNG LẶP ===')
    for x in dups:
        print(' dup:', x)

print()
print('=== OFFICIAL 95 — thiếu trong XA_THON_MAP ===')
missing_xt = [x for x in official_95 if x not in set(xt_names)]
for x in missing_xt:
    print(' -', x)

print()
print('=== XA_THON_MAP — THỪA so với official 95 ===')
extra_xt = [x for x in xt_names if x not in official_set]
for x in extra_xt:
    print(' +', x)

print()
print(f'PGD_XA_MAP unique xa: {len(pgd_xa_names)}')
print(f'XA_THON_MAP keys: {len(xt_names)}')
