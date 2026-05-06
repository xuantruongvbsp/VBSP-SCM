"""
Test thủ công cho 3 validation mới trong data_quality.py
"""
import pandas as pd
from services.data_quality import kiem_tra_chat_luong

print("=" * 80)
print("TEST 1: Kiểm tra dư nợ âm trong HSTD")
print("=" * 80)

df_hstd_am = pd.DataFrame({
    "Số KU": ["KU001", "KU002", "KU003"],
    "Tên PGD": ["PGD Long Thành", "PGD Long Thành", "PGD Long Thành"],
    "Tên xã": ["Xã An Phước", "Xã An Phước", "Xã An Phước"],
    "Dư nợ trong hạn": [1000000, -500000, 2000000],
    "Dư nợ quá hạn": [0, 100000, -300000],
    "Tổng dư nợ": [1000000, -400000, 1700000],
    "Nguồn vốn": [1, 1, 2]
})

result = kiem_tra_chat_luong(df_hstd_am, "hstd")
print(f"Số lỗi: {len(result.errors)}")
print(f"is_valid: {result.is_valid}")
for err in result.errors:
    print(f"  - {err}")

print("\n" + "=" * 80)
print("TEST 2: Kiểm tra số tiền giải ngân > duyệt trong NQ11")
print("=" * 80)

df_nq11_vuot = pd.DataFrame({
    "Mã khách hàng": ["KH001", "KH002", "KH003"],
    "Số tiền duyệt": [10000000, 20000000, 15000000],
    "Số tiền giải ngân": [9000000, 25000000, 15000000],
    "Dư nợ": [5000000, 10000000, 8000000]
})

result = kiem_tra_chat_luong(df_nq11_vuot, "nq11")
print(f"Số lỗi: {len(result.errors)}")
print(f"is_valid: {result.is_valid}")
for err in result.errors:
    print(f"  - {err}")

print("\n" + "=" * 80)
print("TEST 3: Kiểm tra mã đơn vị không hợp lệ")
print("=" * 80)

df_don_vi_sai = pd.DataFrame({
    "Số KU": ["KU001", "KU002", "KU003"],
    "Tên PGD": ["PGD Long Thành", "PGD Không Tồn Tại", "PGD ABC"],
    "Tên xã": ["Xã An Phước", "Xã Không Có", "Xã XYZ"],
    "Dư nợ trong hạn": [1000000, 2000000, 3000000],
    "Dư nợ quá hạn": [0, 0, 0],
    "Tổng dư nợ": [1000000, 2000000, 3000000],
    "Nguồn vốn": [1, 1, 2]
})

result = kiem_tra_chat_luong(df_don_vi_sai, "hstd")
print(f"Số lỗi: {len(result.errors)}")
print(f"is_valid: {result.is_valid}")
for err in result.errors:
    print(f"  - {err}")

print("\n" + "=" * 80)
print("TEST 4: Dữ liệu hợp lệ (không có lỗi)")
print("=" * 80)

df_hop_le = pd.DataFrame({
    "Số KU": ["KU001", "KU002", "KU003"],
    "Tên PGD": ["PGD Long Thành", "PGD Long Thành", "PGD Long Thành"],
    "Tên xã": ["Xã An Phước", "Xã An Phước", "Xã An Phước"],
    "Dư nợ trong hạn": [1000000, 2000000, 3000000],
    "Dư nợ quá hạn": [0, 100000, 50000],
    "Tổng dư nợ": [1000000, 2100000, 3050000],
    "Nguồn vốn": [1, 1, 2]
})

result = kiem_tra_chat_luong(df_hop_le, "hstd")
print(f"Số lỗi: {len(result.errors)}")
print(f"is_valid: {result.is_valid}")
if result.errors:
    for err in result.errors:
        print(f"  - {err}")
else:
    print("  ✓ Không có lỗi - Dữ liệu hợp lệ!")

print("\n" + "=" * 80)
print("HOÀN THÀNH TẤT CẢ CÁC TEST")
print("=" * 80)
