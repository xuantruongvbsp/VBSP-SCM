"""Test validation rules - Final version"""
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')
from services.data_quality import kiem_tra_chat_luong

print("=" * 70)
print("KIEM TRA 2 VALIDATION MOI: DU NO AM & GIAI NGAN VUOT HAN MUC")
print("=" * 70)

print("\n[TEST 1] HSTD co du no am -> PHAI BI REJECT")
print("-" * 70)

df_test1 = pd.DataFrame({
    "Số khế ước": ["KU001", "KU002"],
    "Tên PGD": ["PGD Long Thành", "PGD Long Thành"],
    "Tên xã": ["Xã An Phước", "Xã An Phước"],
    "Dư nợ trong hạn": [1000000, -500000],
    "Dư nợ quá hạn": [0, 0],
    "Tổng dư nợ": [1000000, -500000],
    "Nguồn vốn": [1, 1]
})

result1 = kiem_tra_chat_luong(df_test1, "hstd")
print(f"is_valid: {result1.is_valid} (mong doi: False)")
print(f"So loi: {len(result1.errors)}")
for err in result1.errors:
    if "ÂM" in err or "âm" in err.lower():
        print(f"  ✓ {err}")

print("\n[TEST 2] NQ11 co giai ngan > duyet -> PHAI BI REJECT")
print("-" * 70)

df_test2 = pd.DataFrame({
    "Mã khách hàng": ["KH001", "KH002"],
    "Số tiền duyệt": [10000000, 20000000],
    "Số tiền giải ngân": [9000000, 25000000],
    "Dư nợ": [5000000, 10000000]
})

result2 = kiem_tra_chat_luong(df_test2, "nq11")
print(f"is_valid: {result2.is_valid} (mong doi: False)")
print(f"So loi: {len(result2.errors)}")
for err in result2.errors:
    if "giải ngân" in err or "giai ngan" in err.lower():
        print(f"  ✓ {err}")

print("\n[TEST 3] HSTD hop le (khong co du no am) -> PHAI PASS")
print("-" * 70)

df_test3 = pd.DataFrame({
    "Số khế ước": ["KU001", "KU002"],
    "Tên PGD": ["PGD Long Thành", "PGD Long Thành"],
    "Tên xã": ["Xã An Phước", "Xã An Phước"],
    "Dư nợ trong hạn": [1000000, 2000000],
    "Dư nợ quá hạn": [0, 100000],
    "Tổng dư nợ": [1000000, 2100000],
    "Nguồn vốn": [1, 2]
})

result3 = kiem_tra_chat_luong(df_test3, "hstd")
print(f"is_valid: {result3.is_valid} (mong doi: True)")
print(f"So loi: {len(result3.errors)}")
if result3.is_valid:
    print("  ✓ Khong co loi - Du lieu hop le!")
else:
    for err in result3.errors:
        print(f"  - {err}")

print("\n[TEST 4] NQ11 hop le (giai ngan <= duyet) -> PHAI PASS")
print("-" * 70)

df_test4 = pd.DataFrame({
    "Mã khách hàng": ["KH001", "KH002"],
    "Số tiền duyệt": [10000000, 20000000],
    "Số tiền giải ngân": [9000000, 20000000],
    "Dư nợ": [5000000, 10000000]
})

result4 = kiem_tra_chat_luong(df_test4, "nq11")
print(f"is_valid: {result4.is_valid} (mong doi: True)")
print(f"So loi: {len(result4.errors)}")
if result4.is_valid:
    print("  ✓ Khong co loi - Du lieu hop le!")
else:
    for err in result4.errors:
        print(f"  - {err}")

print("\n" + "=" * 70)
print("KET QUA TONG HOP")
print("=" * 70)
test1_pass = not result1.is_valid and any("ÂM" in e for e in result1.errors)
test2_pass = not result2.is_valid and any("giải ngân" in e for e in result2.errors)
test3_pass = result3.is_valid
test4_pass = result4.is_valid

print(f"Test 1 (phat hien du no am):        {'✓ PASS' if test1_pass else '✗ FAIL'}")
print(f"Test 2 (phat hien vuot han muc):    {'✓ PASS' if test2_pass else '✗ FAIL'}")
print(f"Test 3 (chap nhan du lieu hop le):  {'✓ PASS' if test3_pass else '✗ FAIL'}")
print(f"Test 4 (chap nhan NQ11 hop le):     {'✓ PASS' if test4_pass else '✗ FAIL'}")

if all([test1_pass, test2_pass, test3_pass, test4_pass]):
    print("\n✓✓✓ TAT CA CAC TEST DIEU PASS - VALIDATION HOAT DONG CHINH XAC!")
else:
    print("\n✗ CO IT NHAT 1 TEST FAIL - CAN KIEM TRA LAI")
