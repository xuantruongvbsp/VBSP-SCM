from config import DON_VI_CHI_NHANH
from upload_service import thu_muc_pgd
import os

thu_muc = thu_muc_pgd(DON_VI_CHI_NHANH)
print(f"Thu muc: {thu_muc}")
print(f"Ton tai: {os.path.exists(thu_muc)}")

if os.path.exists(thu_muc):
    files = os.listdir(thu_muc)
    print(f"So file: {len(files)}")
    for f in files:
        fpath = os.path.join(thu_muc, f)
        size = os.path.getsize(fpath)
        print(f"  {f} ({size:,} bytes)")
else:
    print("Thu muc khong ton tai")
