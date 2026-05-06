#!/usr/bin/env python3
"""Script to insert 9-role system into auth.py"""
import os

BASE_DIR = r"c:\VBSP-SCM"
auth_path = os.path.join(BASE_DIR, "auth.py")

# Read the file
with open(auth_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# New role system code to insert after line 18
new_code = '''

# ═══════════════════════════════════════════════════════════════════════════════
# HỆ THỐNG 9 ROLE MỚI (backward-compatible)
# ═══════════════════════════════════════════════════════════════════════════════

# 9 role: executive, admin_cn, manager_cn, admin_pgd, manager_pgd, user_pgd
# + 4 role cũ vẫn hoạt động: executive, admin, manager, user
ALL_ROLES = [
    "executive",
    "admin_cn", "manager_cn",           # Phân hệ Chi nhánh
    "admin_pgd", "manager_pgd", "user_pgd",  # Phân hệ PGD
    "admin", "manager", "user",          # Role cũ (tương thích ngược)
]

# Mapping role cũ → role mới tương đương
ROLE_MAP = {
    # Role cũ → Role mới
    "admin": "admin_cn",
    "manager": "manager_cn",
    "user": "user_pgd",
    # Role mới giữ nguyên
    "executive": "executive",
    "admin_cn": "admin_cn",
    "manager_cn": "manager_cn",
    "admin_pgd": "admin_pgd",
    "manager_pgd": "manager_pgd",
    "user_pgd": "user_pgd",
}

# Phân hệ Chi nhánh (CN)
ROLES_CN = ["executive", "admin_cn", "manager_cn", "admin", "manager"]

# Phân hệ PGD
ROLES_PGD = ["admin_pgd", "manager_pgd", "user_pgd", "user"]

# Quyền cụ thể
ROLES_CAN_UPLOAD = ["admin_cn", "manager_cn", "admin", "manager", "admin_pgd", "manager_pgd"]
ROLES_CAN_MANAGE_USERS = ["admin_cn", "admin", "admin_pgd"]
ROLES_CAN_VIEW_ALL_PGD = ["executive", "admin_cn", "manager_cn", "admin", "manager"]
ROLES_CAN_EDIT_KHTD = ["admin_cn", "manager_cn", "admin", "manager", "admin_pgd", "manager_pgd"]


def normalize_role(role: str) -> str:
    """Chuẩn hóa role về dạng mới (admin → admin_cn, user → user_pgd)."""
    return ROLE_MAP.get(role, role)


def is_cn_role(role: str) -> bool:
    """Kiểm tra role thuộc phân hệ Chi nhánh.
    
    Args:
        role: Role cần kiểm tra (hỗ trợ cả role cũ và mới)
    
    Returns:
        True nếu role thuộc phân hệ CN
    """
    normalized = normalize_role(role)
    return normalized in ["executive", "admin_cn", "manager_cn"]


def is_pgd_role(role: str) -> bool:
    """Kiểm tra role thuộc phân hệ PGD.
    
    Args:
        role: Role cần kiểm tra (hỗ trợ cả role cũ và mới)
    
    Returns:
        True nếu role thuộc phân hệ PGD
    """
    normalized = normalize_role(role)
    return normalized in ["admin_pgd", "manager_pgd", "user_pgd"]


def get_permissions(role: str) -> dict:
    """Lấy danh sách quyền của role.
    
    Args:
        role: Role cần lấy quyền (hỗ trợ cả role cũ và mới)
    
    Returns:
        Dict với các keys:
        - can_upload: Có quyền upload file
        - can_manage_users: Có quyền quản lý người dùng
        - can_view_all_pgd: Có quyền xem tất cả PGD
        - can_edit_khtd: Có quyền chỉnh sửa KHTD
    """
    normalized = normalize_role(role)
    return {
        "can_upload": normalized in ["admin_cn", "manager_cn", "admin_pgd", "manager_pgd"],
        "can_manage_users": normalized in ["admin_cn", "admin_pgd"],
        "can_view_all_pgd": normalized in ["executive", "admin_cn", "manager_cn"],
        "can_edit_khtd": normalized in ["admin_cn", "manager_cn", "admin_pgd", "manager_pgd"],
    }


# Giữ lại các hàm cũ để tương thích ngược (alias)
la_phan_he_cn = is_cn_role
la_phan_he_pgd = is_pgd_role


def co_quyen_upload_pgd(role: str) -> bool:
    """Kiểm tra quyền upload dữ liệu PGD."""
    normalized = normalize_role(role)
    return normalized in ["admin_pgd", "manager_pgd"]


def co_quyen_quan_ly_user_pgd(role: str) -> bool:
    """Kiểm tra quyền quản lý user PGD."""
    normalized = normalize_role(role)
    return normalized == "admin_pgd"


def co_quyen_giao_nhiem_vu(role: str) -> bool:
    """Kiểm tra quyền giao nhiệm vụ cho PGD."""
    normalized = normalize_role(role)
    return normalized in ["admin_pgd", "manager_pgd", "admin_cn", "manager_cn"]

'''

# Insert after line 18 (0-indexed: 17, so we insert at position 18)
new_lines = lines[:18] + [new_code] + lines[18:]

# Write back
with open(auth_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Successfully added 9-role system to auth.py')
