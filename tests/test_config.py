"""Test các hàm và hằng số trong config.py."""
import pytest
from config import (
    tim_ten_xa_trong_hstd, XA_NAME_MAP,
    DS_PGD, MA_PGD_MAP, DON_VI_CHI_NHANH,
    DGD_DANH_SACH, DGD_MA_MAP, TEN_PGD_TO_MA,
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


class TestDgdMaMap:
    """Test mapping mã Điểm Giao Dịch."""

    def test_dgd_ma_map_hoi_so_theo_nguon_master(self):
        """Ba Điểm GD Hội sở dễ lệch mã phải khớp nguồn master BCQUERY."""
        hoi_so = DGD_MA_MAP["4601"]
        assert hoi_so["TXN0460414"] == "Bửu Hòa"
        assert hoi_so["TXN0462402"] == "Hố Nai 3"
        assert hoi_so["TXN0465804"] == "Tân Hiệp 3"
        assert "Bửa Hòa" not in hoi_so.values()

    def test_dgd_danh_sach_ma_dgd_deu_nam_trong_dgd_ma_map(self):
        """Mọi dòng lịch Điểm GD có mã hợp lệ trong DGD_MA_MAP cùng PGD."""
        loi = []
        for row in DGD_DANH_SACH:
            ma_pgd = str(TEN_PGD_TO_MA.get(row.get("pgd", "")) or "").lstrip("0")
            ma_dgd = row.get("ma_dgd")
            if not ma_dgd or ma_dgd not in DGD_MA_MAP.get(ma_pgd, {}):
                loi.append((row.get("stt"), row.get("pgd"), row.get("ten"), ma_dgd))
        assert loi == []

    def test_dgd_danh_sach_khong_trung_ma_dgd(self):
        """Danh sách lịch không được dùng cùng một mã cho hai Điểm GD."""
        da_gap = {}
        trung = []
        for row in DGD_DANH_SACH:
            ma_dgd = row.get("ma_dgd")
            if not ma_dgd:
                continue
            if ma_dgd in da_gap:
                trung.append((ma_dgd, da_gap[ma_dgd], row.get("stt")))
            else:
                da_gap[ma_dgd] = row.get("stt")
        assert trung == []

    def test_dgd_danh_sach_cac_dong_lech_ten_da_duoc_chuan_hoa(self):
        """Các dòng từng lệch tên theo nguồn master phải giữ đúng mã."""
        theo_stt = {row["stt"]: row for row in DGD_DANH_SACH}
        assert theo_stt[76]["ten"] == "Xuân Hưng"
        assert theo_stt[76]["ma_dgd"] == "TXN0467901"
        assert theo_stt[81]["ten"] == "Xuân Hòa"
        assert theo_stt[81]["ma_dgd"] == "TXN0467903"
        assert theo_stt[122]["ten"] == "Dak Lua"
        assert theo_stt[122]["ma_dgd"] == "TXN0461801"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
