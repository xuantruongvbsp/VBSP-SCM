"""Tests cho services/rui_ro_aggregation.py — pure functions, không cần DB."""
from __future__ import annotations

import pytest

from services.rui_ro_aggregation import _loc_theo_nguon, _tong_hop_no


# ─── _loc_theo_nguon ────────────────────────────────────────────────────────

class TestLocTheoNguon:
    def _ds(self):
        return [
            {"so_ku": "KU1", "nguon_von": 1, "du_no_goc": 1_000_000},
            {"so_ku": "KU2", "nguon_von": 2, "du_no_goc": 2_000_000},
            {"so_ku": "KU3", "nguon_von": 1, "du_no_goc": 3_000_000},
            {"so_ku": "KU4", "nguon_von": "2", "du_no_goc": 500_000},  # string int
        ]

    def test_loc_tw(self):
        kq = _loc_theo_nguon(self._ds(), nguon=1)
        assert len(kq) == 2
        assert all(int(r["nguon_von"]) == 1 for r in kq)

    def test_loc_dp(self):
        kq = _loc_theo_nguon(self._ds(), nguon=2)
        assert len(kq) == 2
        assert all(int(r["nguon_von"]) == 2 for r in kq)

    def test_nguon_khong_ton_tai(self):
        kq = _loc_theo_nguon(self._ds(), nguon=99)
        assert kq == []

    def test_danh_sach_trong(self):
        kq = _loc_theo_nguon([], nguon=1)
        assert kq == []

    def test_khong_co_field_nguon_von(self):
        ds = [{"so_ku": "KU1"}, {"so_ku": "KU2"}]
        kq = _loc_theo_nguon(ds, nguon=1)
        # nguon_von mặc định 0 → không khớp 1
        assert kq == []


# ─── _tong_hop_no ────────────────────────────────────────────────────────────

class TestTongHopNo:
    def _ds_simple(self):
        return [
            {"ten_ct": "Hộ nghèo", "du_no_goc": 1_000_000, "lai_ton": 50_000},
            {"ten_ct": "Hộ nghèo", "du_no_goc": 2_000_000, "lai_ton": 100_000},
            {"ten_ct": "GQVL", "du_no_goc": 5_000_000, "lai_ton": 0},
        ]

    def test_so_ho(self):
        kq = _tong_hop_no(self._ds_simple())
        assert kq["tong_ho"] == 3
        assert kq["nhom_ct"]["Hộ nghèo"]["so_ho"] == 2
        assert kq["nhom_ct"]["GQVL"]["so_ho"] == 1

    def test_tong_tien(self):
        kq = _tong_hop_no(self._ds_simple())
        assert kq["tong_goc"] == 8_000_000
        assert kq["tong_lai"] == 150_000
        assert kq["tong_tien"] == 8_150_000

    def test_ten_ct_none_ve_khac(self):
        ds = [{"ten_ct": None, "du_no_goc": 1_000_000, "lai_ton": 0}]
        kq = _tong_hop_no(ds)
        assert "Khác" in kq["nhom_ct"]
        assert kq["nhom_ct"]["Khác"]["so_ho"] == 1

    def test_ten_ct_empty_ve_khac(self):
        ds = [{"ten_ct": "", "du_no_goc": 500_000, "lai_ton": 0}]
        kq = _tong_hop_no(ds)
        assert "Khác" in kq["nhom_ct"]

    def test_danh_sach_trong(self):
        kq = _tong_hop_no([])
        assert kq["tong_ho"] == 0
        assert kq["tong_goc"] == 0.0
        assert kq["tong_tien"] == 0.0

    def test_ds_field_luu_trong_nhom(self):
        ds = [{"ten_ct": "Hộ nghèo", "du_no_goc": 1_000_000, "lai_ton": 0, "so_ku": "K1"}]
        kq = _tong_hop_no(ds)
        assert kq["nhom_ct"]["Hộ nghèo"]["ds"][0]["so_ku"] == "K1"

    def test_gia_tri_thieu_ve_0(self):
        ds = [{"ten_ct": "Hộ nghèo"}]  # thiếu du_no_goc, lai_ton
        kq = _tong_hop_no(ds)
        assert kq["tong_goc"] == 0.0
        assert kq["tong_lai"] == 0.0
