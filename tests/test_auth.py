"""Test RBAC — phân quyền 9 role và normalize_role."""
import pytest
from auth import (
    normalize_role, is_cn_role, is_pgd_role,
    la_phan_he_cn, la_phan_he_pgd,
    co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd,
    co_quyen_giao_nhiem_vu, la_chuyen_vien_cn,
    get_permissions, get_tab_permissions, ROLE_MAP, ROLES_CN, ROLES_PGD,
)


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_role
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeRole:
    """Test normalize_role: role cũ → role mới."""

    @pytest.mark.parametrize("input_role,expected", [
        ("admin",         "admin_cn"),
        ("manager",       "manager_cn"),
        ("user",          "user_pgd"),
        ("admin_cn",      "admin_cn"),
        ("executive",     "executive"),
        ("user_pgd",      "user_pgd"),
        ("manager_cn",    "manager_cn"),
        ("chuyenvien_cn", "chuyenvien_cn"),
        ("admin_pgd",     "admin_pgd"),
        ("manager_pgd",   "manager_pgd"),
    ])
    def test_normalize_role_map(self, input_role, expected):
        """normalize_role({input_role}) → {expected}"""
        assert normalize_role(input_role) == expected

    def test_normalize_role_unknown(self):
        """Role lạ không có trong map → trả nguyên gốc, không crash"""
        assert normalize_role("unknown_role") == "unknown_role"


# ═══════════════════════════════════════════════════════════════════════════════
# is_cn_role / la_phan_he_cn (alias)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsCnRole:
    """Test is_cn_role: kiểm tra role thuộc phân hệ Chi nhánh."""

    @pytest.mark.parametrize("role,expected", [
        ("executive",     True),
        ("admin_cn",      True),
        ("manager_cn",    True),
        ("chuyenvien_cn", True),
        ("admin",         True),     # role cũ → admin_cn
        ("manager",       True),     # role cũ → manager_cn
        ("user_pgd",      False),
        ("admin_pgd",     False),
        ("manager_pgd",   False),
        ("user",          False),    # user → user_pgd
    ])
    def test_is_cn_role(self, role, expected):
        """is_cn_role('{role}') → {expected}"""
        assert is_cn_role(role) == expected

    def test_la_phan_he_cn_alias(self):
        """la_phan_he_cn là alias của is_cn_role (cùng hàm hoặc cùng kết quả)"""
        assert la_phan_he_cn is is_cn_role
        # Đảm bảo cho cùng kết quả
        for r in ["executive", "admin_cn", "user_pgd", "user"]:
            assert la_phan_he_cn(r) == is_cn_role(r)


# ═══════════════════════════════════════════════════════════════════════════════
# is_pgd_role / la_phan_he_pgd (alias)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsPgdRole:
    """Test is_pgd_role: kiểm tra role thuộc phân hệ PGD."""

    @pytest.mark.parametrize("role,expected", [
        ("user_pgd",    True),
        ("admin_pgd",   True),
        ("manager_pgd", True),
        ("user",        True),       # user → user_pgd
        ("executive",   False),
        ("admin_cn",    False),
        ("manager_cn",  False),
        ("admin",       False),      # admin → admin_cn
    ])
    def test_is_pgd_role(self, role, expected):
        """is_pgd_role('{role}') → {expected}"""
        assert is_pgd_role(role) == expected

    def test_la_phan_he_pgd_alias(self):
        """la_phan_he_pgd là alias của is_pgd_role"""
        assert la_phan_he_pgd is is_pgd_role


# ═══════════════════════════════════════════════════════════════════════════════
# co_quyen_upload_pgd
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoQuyenUploadPgd:
    """Test co_quyen_upload_pgd: quyền upload dữ liệu PGD."""

    @pytest.mark.parametrize("role,expected", [
        ("admin_pgd",   True),
        ("manager_pgd", True),
        ("user_pgd",    False),
        ("admin_cn",    False),    # CN không upload qua hàm PGD
        ("executive",   False),
        ("admin",       False),    # admin → admin_cn
        ("user",        False),    # user → user_pgd (user_pgd không có quyền)
    ])
    def test_co_quyen_upload_pgd(self, role, expected):
        """co_quyen_upload_pgd('{role}') → {expected}"""
        assert co_quyen_upload_pgd(role) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# co_quyen_quan_ly_user_pgd
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoQuyenQuanLyUserPgd:
    """Test co_quyen_quan_ly_user_pgd: quyền quản lý user PGD."""

    @pytest.mark.parametrize("role,expected", [
        ("admin_pgd",   True),
        ("manager_pgd", False),
        ("user_pgd",    False),
        ("admin_cn",    False),
    ])
    def test_co_quyen_quan_ly_user_pgd(self, role, expected):
        """co_quyen_quan_ly_user_pgd('{role}') → {expected}"""
        assert co_quyen_quan_ly_user_pgd(role) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# co_quyen_giao_nhiem_vu
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoQuyenGiaoNhiemVu:
    """Test co_quyen_giao_nhiem_vu: quyền giao nhiệm vụ cho PGD."""

    @pytest.mark.parametrize("role,expected", [
        ("admin_pgd",     True),
        ("manager_pgd",   True),
        ("admin_cn",      True),
        ("manager_cn",    True),
        ("chuyenvien_cn", True),
        ("user_pgd",      False),
        ("executive",     False),
        ("user",          False),
    ])
    def test_co_quyen_giao_nhiem_vu(self, role, expected):
        """co_quyen_giao_nhiem_vu('{role}') → {expected}"""
        assert co_quyen_giao_nhiem_vu(role) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# la_chuyen_vien_cn
# ═══════════════════════════════════════════════════════════════════════════════

class TestLaChuyenVienCn:
    """Test la_chuyen_vien_cn: kiểm tra role là chuyên viên CN."""

    @pytest.mark.parametrize("role,expected", [
        ("chuyenvien_cn", True),
        ("admin_cn",  False),
        ("manager_cn", False),
        ("user_pgd", False),
    ])
    def test_la_chuyen_vien_cn(self, role, expected):
        """la_chuyen_vien_cn('{role}') → {expected}"""
        assert la_chuyen_vien_cn(role) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# get_permissions
# ═══════════════════════════════════════════════════════════════════════════════

EXPECTED_PERMISSIONS = {
    "executive": {
        "can_upload": False,
        "can_manage_users": False,
        "can_view_all_pgd": True,
        "can_edit_khtd": False,
    },
    "admin_cn": {
        "can_upload": True,
        "can_manage_users": True,
        "can_view_all_pgd": True,
        "can_edit_khtd": True,
    },
    "user_pgd": {
        "can_upload": False,
        "can_manage_users": False,
        "can_view_all_pgd": False,
        "can_edit_khtd": False,
    },
    "admin_pgd": {
        "can_upload": True,
        "can_manage_users": True,
        "can_view_all_pgd": False,
        "can_edit_khtd": True,
    },
    "manager_pgd": {
        "can_upload": True,
        "can_manage_users": False,
        "can_view_all_pgd": False,
        "can_edit_khtd": True,
    },
}


class TestGetPermissions:
    """Test get_permissions: dict quyền của từng role."""

    @pytest.mark.parametrize("role,expected", list(EXPECTED_PERMISSIONS.items()))
    def test_get_permissions(self, role, expected):
        """get_permissions('{role}') == {expected}"""
        perms = get_permissions(role)
        for key, val in expected.items():
            assert perms[key] == val, (
                f"get_permissions('{role}')['{key}'] phải là {val}, "
                f"nhưng được {perms[key]}"
            )


class TestGetTabPermissions:
    """Test phân quyền nhóm tab của workspace Operation."""

    def test_user_pgd_chi_duoc_nghiep_vu_va_bao_cao(self):
        perms = get_tab_permissions("user_pgd")
        assert perms["nhom_duoc_phep"] == ["nghiep_vu_pgd", "bao_cao_giao_ban"]
        assert perms["co_quyen_khtd"] is False
        assert perms["co_quyen_kiem_soat"] is False
        assert perms["co_quyen_quan_tri"] is False
        assert perms["co_quyen_upload_hstd"] is False

    def test_manager_pgd_duoc_day_du_nhom(self):
        perms = get_tab_permissions("manager_pgd")
        assert perms["nhom_duoc_phep"] == [
            "nghiep_vu_pgd", "bao_cao_giao_ban", "ke_hoach_pgd", "kiem_soat_rr", "quan_tri_pgd"
        ]
        assert perms["co_quyen_khtd"] is True
        assert perms["co_quyen_kiem_soat"] is True
        assert perms["co_quyen_quan_tri"] is True
        assert perms["co_quyen_upload_hstd"] is True

    def test_role_la_fallback_chi_lay_quyen_toi_thieu(self):
        perms = get_tab_permissions("role_la")
        assert perms["nhom_duoc_phep"] == ["nghiep_vu_pgd", "bao_cao_giao_ban"]
        assert perms["co_quyen_khtd"] is False
        assert perms["co_quyen_kiem_soat"] is False
        assert perms["co_quyen_quan_tri"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# ROLE_MAP — constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoleMap:
    """Test hằng số ROLE_MAP có đủ các role cũ và mới."""

    def test_role_map_has_all_old_roles(self):
        """ROLE_MAP chứa 'admin', 'manager', 'user'"""
        for old_role in ("admin", "manager", "user"):
            assert old_role in ROLE_MAP

    def test_role_map_preserves_new_roles(self):
        """ROLE_MAP chứa và giữ nguyên các role mới"""
        for new_role in ("executive", "admin_cn", "manager_cn",
                         "chuyenvien_cn", "admin_pgd", "manager_pgd", "user_pgd"):
            assert new_role in ROLE_MAP
            assert ROLE_MAP[new_role] == new_role


# ═══════════════════════════════════════════════════════════════════════════════
# ROLES_CN / ROLES_PGD — constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestRolesCnPgd:
    """Test hằng số danh sách role."""

    def test_roles_cn_contains_expected(self):
        """ROLES_CN chứa executive, admin_cn, manager_cn, chuyenvien_cn, admin, manager"""
        expected = {"executive", "admin_cn", "manager_cn", "chuyenvien_cn", "admin", "manager"}
        assert set(ROLES_CN) == expected

    def test_roles_pgd_contains_expected(self):
        """ROLES_PGD chứa admin_pgd, manager_pgd, user_pgd, user"""
        expected = {"admin_pgd", "manager_pgd", "user_pgd", "user"}
        assert set(ROLES_PGD) == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
