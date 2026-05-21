"""Unit tests cho services/rui_ro_aggregation.py — Tổng hợp rủi ro."""
from __future__ import annotations

from services.rui_ro_aggregation import _loc_theo_nguon, _tong_hop_no


class TestLocTheoNguon:
    def test_loc_tw(self):
        rows = [
            {"nguon_von": 1, "ten_kh": "A"},
            {"nguon_von": 2, "ten_kh": "B"},
            {"nguon_von": 1, "ten_kh": "C"},
        ]
        ket_qua = _loc_theo_nguon(rows, 1)
        assert len(ket_qua) == 2
        assert ket_qua[0]["ten_kh"] == "A"

    def test_loc_dp(self):
        rows = [
            {"nguon_von": 1, "ten_kh": "A"},
            {"nguon_von": 2, "ten_kh": "B"},
        ]
        ket_qua = _loc_theo_nguon(rows, 2)
        assert len(ket_qua) == 1
        assert ket_qua[0]["ten_kh"] == "B"

    def test_khong_co_nguon_von(self):
        rows = [{"ten_kh": "A"}]
        ket_qua = _loc_theo_nguon(rows, 1)
        assert len(ket_qua) == 0

    def test_danh_sach_rong(self):
        assert _loc_theo_nguon([], 1) == []


class TestTongHopNo:
    def test_tong_hop_co_ban(self):
        ds = [
            {"ten_ct": "CT A", "du_no_goc": 100, "lai_ton": 10},
            {"ten_ct": "CT A", "du_no_goc": 200, "lai_ton": 20},
            {"ten_ct": "CT B", "du_no_goc": 50, "lai_ton": 5},
        ]
        kq = _tong_hop_no(ds)
        assert kq["tong_ho"] == 3
        assert kq["tong_goc"] == 350.0
        assert kq["tong_lai"] == 35.0
        assert kq["tong_tien"] == 385.0
        assert len(kq["nhom_ct"]) == 2
        assert kq["nhom_ct"]["CT A"]["so_ho"] == 2
        assert kq["nhom_ct"]["CT A"]["goc"] == 300.0

    def test_thieu_ten_ct_lay_mac_dinh(self):
        ds = [{"du_no_goc": 100, "lai_ton": 10}]
        kq = _tong_hop_no(ds)
        assert kq["tong_ho"] == 1
        assert "Khác" in kq["nhom_ct"]

    def test_ten_ct_None(self):
        ds = [{"ten_ct": None, "du_no_goc": 100, "lai_ton": 0}]
        kq = _tong_hop_no(ds)
        assert "Khác" in kq["nhom_ct"]

    def test_goc_la_0(self):
        ds = [{"ten_ct": "CT A", "du_no_goc": 0, "lai_ton": 0}]
        kq = _tong_hop_no(ds)
        assert kq["tong_goc"] == 0
        assert kq["tong_tien"] == 0
