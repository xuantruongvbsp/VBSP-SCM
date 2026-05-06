import sys, re
sys.path.insert(0, '.')
from db import get_conn
from auth import ma_hoa
from config import MA_PGD_MAP

conn = get_conn()

# Dùng MA_PGD_MAP để lấy mã PGD thay vì tạo slug từ tên tiếng Việt
for ma_pgd, ten_pgd in MA_PGD_MAP.items():
    # Tạo slug từ mã PGD: 004601 → bien_hoa, 004602 → long_thanh
    slug = ma_pgd.replace("0046", "")  # Bỏ prefix 0046
    slug_map = {
        "01": "bien_hoa",
        "02": "long_thanh", 
        "03": "trang_bom",
        "04": "tan_phu",
        "05": "vinh_cuu",
        "06": "dinh_quan",
        "07": "xuan_loc",
        "08": "long_khanh",
        "09": "cam_my",
        "10": "thong_nhat",
        "11": "nhon_trach",
        "12": "binh_long",
        "13": "loc_ninh",
        "14": "binh_phuoc",
        "15": "phuoc_long",
        "16": "bu_dang",
        "17": "dong_phu",
        "18": "chon_thanh",
        "19": "bu_dop",
        "20": "bu_gia_map",
        "21": "phu_rieng",
        "22": "hon_quan",
    }
    slug = slug_map.get(slug, f"pgd_{slug}")
    username = f"admin_{slug}"
    
    existing = conn.execute(
        "SELECT username FROM users WHERE username=?", (username,)
    ).fetchone()
    
    # Xóa user cũ nếu tồn tại (để cập nhật password mới)
    if existing:
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        print(f"🗑️  Xóa user cũ: {username}")
    
    conn.execute(
        """INSERT INTO users 
           (username, password, role, pgd, ho_ten)
           VALUES (?, ?, ?, ?, ?)""",
        (
            username,
            ma_hoa("123456"),
            "admin_pgd",
            ten_pgd,
            f"Admin {ten_pgd}",
        )
    )
    print(f"✅ Tạo: {username} | pgd={ten_pgd}")

conn.commit()
print("\n🎉 Xong! Mật khẩu mặc định: 123456")
