import sys
sys.path.insert(0, '.')
from db import get_conn
from auth import ma_hoa, kiem_tra

conn = get_conn()

# Test 1: Kiểm tra user tồn tại
print("=== Kiểm tra user admin_bien_hoa ===")
user = conn.execute("SELECT username, password_hash, role, pgd FROM users WHERE username=?", 
                    ('admin_bien_hoa',)).fetchone()

if user:
    print(f"✓ User tồn tại: {user[0]}")
    print(f"  Role: {user[2]}")
    print(f"  PGD: {user[3]}")
    
    # Test 2: Kiểm tra password
    test_result = kiem_tra('123456', user[1])
    print(f"  Password '123456' hợp lệ: {test_result}")
else:
    print("✗ Không tìm thấy user admin_bien_hoa")
    print("\nDanh sách users hiện có:")
    all_users = conn.execute("SELECT username, role FROM users").fetchall()
    for u in all_users:
        print(f"  - {u[0]} ({u[1]})")

# Test 3: Tạo lại user nếu cần
print("\n=== Tạo user test ===")
from config import MA_PGD_MAP

for ma, ten in MA_PGD_MAP.items():
    if 'bien_hoa' in ma.lower() or 'biên hòa' in ten.lower():
        print(f"Mã: {ma}, Tên: {ten}")
        
        # Kiểm tra đã tồn tại chưa
        existing = conn.execute("SELECT id FROM users WHERE pgd=? AND role='admin_pgd'", 
                               (ten,)).fetchone()
        if not existing:
            # Tạo user
            username = 'admin_bien_hoa'
            conn.execute("""INSERT INTO users (username, password_hash, role, pgd, ho_ten, active)
                          VALUES (?, ?, ?, ?, ?, 1)""",
                        (username, ma_hoa('123456'), 'admin_pgd', ten, f'Admin {ten}'))
            conn.commit()
            print(f"  → Đã tạo user {username}")
        else:
            print(f"  → User đã tồn tại")
        break
