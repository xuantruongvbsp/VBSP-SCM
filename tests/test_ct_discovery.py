"""Test services/ct_discovery.py — quét chương trình tín dụng."""

import pandas as pd
import pytest

from services.ct_discovery import (
    _slug,
    _phan_tang_gqvl,
    _MA_KEY_LOOKUP,
)


class TestSlug:
    def test_pgd_long_thanh(self):
        assert _slug("PGD Long Thành") == "pgd_long_thanh"

    def test_chu_d(self):
        # _slug trong ct_discovery.py không xử lý "đ" riêng → "đ" bị regex [^a-z0-9] loại bỏ → pgd_inh_quan
        assert _slug("PGD Định Quán") == "pgd_inh_quan"

    def test_hoi_so(self):
        slug = _slug("Hội sở Chi nhánh tỉnh")
        assert "hoi_so" in slug


class TestMaKeyLookup:
    def test_co_ct_1_tw(self):
        assert (1, 1) in _MA_KEY_LOOKUP

    def test_lookup_tra_ma_key(self):
        # Phải có ít nhất 1 entry với ma_ct=1, nguon_von=1 (TW)
        result = _MA_KEY_LOOKUP.get((1, 1))
        assert result is not None


class TestPhanTangGqvl:
    """_phan_tang_gqvl() phân tầng GQVL thành 4 nhóm."""

    @pytest.fixture
    def ndt_dp_list(self):
        return ["DP001", "DT_DP_01"]

    def test_tw_nhcsxh(self, ndt_dp_list):
        row = pd.Series({
            "Nguồn vốn": "TW",
            "Phân loại NV": 2,
        })
        mk = _phan_tang_gqvl(row, ndt_dp_list=ndt_dp_list)
        assert mk == "3_TW_NHCSXH"

    def test_tw_nsnn(self, ndt_dp_list):
        row = pd.Series({
            "Nguồn vốn": "TW",
            "Phân loại NV": 1,
        })
        mk = _phan_tang_gqvl(row, ndt_dp_list=ndt_dp_list)
        assert mk == "3_TW_NSNN"

    def test_dp_tinh(self, ndt_dp_list):
        row = pd.Series({
            "Nguồn vốn": "ĐP",
            "Mã nhà đầu tư": "DP001",
        })
        mk = _phan_tang_gqvl(row, ndt_dp_list=ndt_dp_list)
        assert mk == "3_DP_TINH"

    def test_dp_xa_khong_co_trong_danh_sach(self, ndt_dp_list):
        row = pd.Series({
            "Nguồn vốn": "ĐP",
            "Mã nhà đầu tư": "UNKNOWN_XYZ",
        })
        mk = _phan_tang_gqvl(row, ndt_dp_list=ndt_dp_list)
        assert mk == "3_DP_XA"

    def test_tw_khong_xac_dinh_plnv_tra_none(self, ndt_dp_list):
        row = pd.Series({
            "Nguồn vốn": "TW",
            "Phân loại NV": 999,
        })
        mk = _phan_tang_gqvl(row, ndt_dp_list=ndt_dp_list)
        assert mk is None

    def test_nguon_von_khac_tra_none(self, ndt_dp_list):
        row = pd.Series({
            "Nguồn vốn": "KHAC",
        })
        mk = _phan_tang_gqvl(row, ndt_dp_list=ndt_dp_list)
        assert mk is None
