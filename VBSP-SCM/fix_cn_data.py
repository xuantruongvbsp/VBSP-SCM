import sys
sys.path.insert(0, r'c:\VBSP-SCM')

from config import DON_VI_CHI_NHANH
from upload_service import thu_muc_pgd
import os

thu_muc = thu_muc_pgd(DON_VI_CHI_NHANH)

# Step 1: Check files
result = []
result.append(f"Thu muc: {thu_muc}")
if os.path.exists(thu_muc):
    files = os.listdir(thu_muc)
    result.append(f"So file: {len(files)}")
    for f in files:
        fpath = os.path.join(thu_muc, f)
        size = os.path.getsize(fpath)
        result.append(f"  {f} ({size:,} bytes)")
    
    # Step 2: Delete wrong files
    loai_xoa = ['hstd', 'nq11', 'gqvl', 'cdtotkvv']
    deleted = []
    for f in files:
        ten = f.lower()
        if any(ten.startswith(l) for l in loai_xoa):
            fpath = os.path.join(thu_muc, f)
            os.remove(fpath)
            deleted.append(f)
            result.append(f"[XOA] {f}")
    
    if not deleted:
        result.append("Khong co file can xoa")
else:
    result.append("Thu muc khong ton tai")

# Step 3: Merge
from upload_service import merge_du_lieu_toan_cn
from config import DS_PGD

for loai in ['hstd', 'nq11', 'gqvl']:
    kq = merge_du_lieu_toan_cn(loai, ds_pgd=DS_PGD)
    result.append(f"Merge {loai}: {kq.thong_bao}")

# Write output
with open('c:/VBSP-SCM/fix_cn_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(result))

print('\n'.join(result))
