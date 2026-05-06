"""Test validation rules"""
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')
from services.data_quality import kiem_tra_chat_luong

print("=" * 70)
print("TEST 1: HSTD co du no am -> PHAI BI REJECT")
print("=" * 70)

df_test1 = pd.DataFrame({
    "Số KU": ["KU001", "KU002"],
    "Tên PGD": ["PGD Long Thành", "PGD Long Thành"],
    "Tên xã": ["Xã An Phước", "Xã An Phước"],
    "Dư nợ trong hạn": [1000000, -500000],
    "Dư nợ quá hạn": [0, 0],
    "Tổng dư nợ": [1000000, -500000],
    "Nguồn vốn": [1, 1]
})

result1 = kiem_tra_chat_luong(df_test1, "hstd")
print(f"is_valid: {result1.is_valid}")
print(f"So loi: {len(result1.errors)}")
for err in result1.errors:
    print(f"  {err}")

print("\n" + "=" * 70)
print("TEST 2: NQ11 co giai ngan > duyet -> PHAI BI REJECT")
print("=" * 70)

df_test2 = pd.DataFrame({
    "Mã khách hàng": ["KH001", "KH002"],
    "Số tiền duyệt": [10000000, 20000000],
    "Số tiền giải ngân": [9000000, 25000000],
    "Dư nợ": [5000000, 10000000]
})

result2 = kiem_tra_chat_luong(df_test2, "nq11")
print(f"is_valid: {result2.is_valid}")
print(f"So loi: {len(result2.errors)}")
for err in result2.errors:
    print(f"  {err}")

print("\n" + "=" * 70)
print("TEST 3: Du lieu hop le -> PHAI PASS")
print("=" * 70)

df_test3 = pd.DataFrame({
    "Số KU": ["KU001", "KU002"],
    "Tên PGD": ["PGD Long Thành", "PGD Long Thành"],
    "Tên xã": ["Xã An Phước", "Xã An Phước"],
    "Dư nợ trong hạn": [1000000, 2000000],
    "Dư nợ quá hạn": [0, 100000],
    "Tổng dư nợ": [1000000, 2100000],
    "Nguồn vốn": [1, 2]
})

result3 = kiem_tra_chat_luong(df_test3, "hstd")
print(f"is_valid: {result3.is_valid}")
print(f"So loi: {len(result3.errors)}")
if not result3.errors:
    print("  Khong co loi!")

print("\n" + "=" * 70)
print("KET LUAN")
print("=" * 70)
print(f"Test 1 (du no am): {'PASS' if not result1.is_valid else 'FAIL'}")
print(f"Test 2 (vuot han muc): {'PASS' if not result2.is_valid else 'FAIL'}")
print(f"Test 3 (hop le): {'PASS' if result3.is_valid else 'FAIL'}")
