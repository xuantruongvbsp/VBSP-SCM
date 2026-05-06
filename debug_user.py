import sys
sys.path.insert(0, '.')
from db import get_conn
from auth import ma_hoa, kiem_tra

conn = get_conn()

# 1. Liệt kê tất cả users
print("=== Tất cả users ===")
cursor = conn.execute("SELECT username, role, pgd FROM users")
for row in cursor.fetchall():
    print(f"  {row[0]:25} | {row[1]:12} | {row[2]}")

# 2. Tìm user admin_bien_hoa
print("\n=== Tìm admin_bien_hoa ===")
user = conn.execute("SELECT * FROM users WHERE username=?", ('admin_bien_hoa',)).fetchone()
print(f"Tìm thấy: {user is not None}")

if user:
    print(f"ID: {user[0]}, Username: {user[1]}")
    print(f"Role: {user[3]}, PGD: {user[4]}")
    # Test password
    result = kiem_tra('123456', user[2])
    print(f"Password '123456' hợp lệ: {result}")
else:
    # 3. Tạo user thủ công nếu chưa có
    print("\n=== Tạo user admin_bien_hoa ===")
    from config import DON_VI_CHI_NHANH
    try:
        conn.execute("""INSERT INTO users (username, password_hash, role, pgd, ho_ten, active)
                      VALUES (?, ?, ?, ?, ?, 1)""",
                    ('admin_bien_hoa', ma_hoa('123456'), 'admin_pgd', DON_VI_CHI_NHANH, 'Admin Biên Hòa'))
        conn.commit()
        print("✅ Đã tạo admin_bien_hoa")
    except Exception as e:
        print(f"❌ Lỗi: {e}")

print("\nXong! Thử đăng nhập với admin_bien_hoa / 123456")
