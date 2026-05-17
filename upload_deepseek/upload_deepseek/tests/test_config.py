"""Test các hàm và hằng số trong config.py."""
import pytest
from config import (
    tim_ten_xa_trong_hstd, XA_NAME_MAP,
    DS_PGD, MA_PGD_MAP, DON_VI_CHI_NHANH,
)


# ═══════════════════════════════════════════════════════════════════════════════
# tim_ten_xa_trong_hstd
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimTenXaTrongHstd:
    """Test map tên xã từ config sang tên trong HSTD."""

    @pytest.mark.parametrize("input_xa,expected", [
        # Exact match trong XA_NAME_MAP
        ("Xã La Ngà",  "La Ngà"),
        ("Xã Phú Hòa", "Phú Hòa"),
        # Bỏ prefix "Xã "
        ("Xã Bình Minh", "Bình Minh"),
        # Bỏ prefix "Phường "
        ("Phường Trung Dũng", "Trung Dũng"),
        # Bỏ prefix "Thị trấn "
        ("Thị trấn Vĩnh An", "Vĩnh An"),
        # Bỏ prefix "TT "
        ("TT Gia Ray", "Gia Ray"),
        # Không có prefix → trả nguyên gốc
        ("Không có prefix", "Không có prefix"),
    ])
    def test_tim_ten_xa_trong_hstd(self, input_xa, expected):
        """tim_ten_xa_trong_hstd('{input_xa}') → '{expected}'"""
        assert tim_ten_xa_trong_hstd(input_xa) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# DS_PGD
# ═══════════════════════════════════════════════════════════════════════════════

class TestDsPgd:
    """Test danh sách PGD."""

    def test_ds_pgd_length(self):
        """DS_PGD có ít nhất 21 phòng giao dịch"""
        assert len(DS_PGD) >= 21, f"DS_PGD chỉ có {len(DS_PGD)} phần tử"

    def test_ds_pgd_khong_chua_ho_so_cn(self):
        """'Hội sở Chi nhánh tỉnh' (DON_VI_CHI_NHANH) không nằm trong DS_PGD"""
        assert DON_VI_CHI_NHANH not in DS_PGD, (
            f"'{DON_VI_CHI_NHANH}' là DON_VI_CHI_NHANH, không thuộc DS_PGD"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MA_PGD_MAP
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaPgdMap:
    """Test mapping mã PGD."""

    def test_ma_pgd_map_is_dict(self):
        """MA_PGD_MAP là dict"""
        assert isinstance(MA_PGD_MAP, dict)

    def test_ma_pgd_map_values_are_strings(self):
        """Mỗi value trong MA_PGD_MAP là string (tên đơn vị)"""
        for key, val in MA_PGD_MAP.items():
            assert isinstance(val, str), f"Value của key '{key}' không phải string: {type(val)}"

    def test_ma_pgd_map_has_ho_so_cn(self):
        """MA_PGD_MAP có 'Hội sở Chi nhánh tỉnh' (mã 004601)"""
        assert "Hội sở Chi nhánh tỉnh" in MA_PGD_MAP.values()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
