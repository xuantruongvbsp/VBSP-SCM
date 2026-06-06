"""Test services/data_priority_service.py — widget trạng thái upload."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from services.data_priority_service import (
    NguonDuLieu,
    kiem_tra_nguon_uu_tien,
    thong_ke_su_dung_nguon,
)


class TestNguonDuLieu:
    def test_cac_hang_so(self):
        assert NguonDuLieu.PGD_UPLOAD == "pgd_upload"
        assert NguonDuLieu.CHUA_UPLOAD == "chua_upload"
        assert NguonDuLieu.KHONG_CO == "khong_co"


class TestKiemTraNguonUuTien:
    """kiem_tra_nguon_uu_tien() — kiểm tra trạng thái file của 1 đơn vị."""

    def test_co_file_tra_pgd_upload(self):
        mock_info = {"co_file": True, "canh_bao": "ok", "so_ngay_cu": 0}
        with patch(
            "data.pgd.doc_trang_thai_file",
            return_value=mock_info,
        ), patch("data.pgd.duong_dan_pgd", return_value="/fake/path.xlsx"):
            result = kiem_tra_nguon_uu_tien("PGD Long Thành", "hstd")
            assert result["nguon_uu_tien"] == NguonDuLieu.PGD_UPLOAD
            assert "✅" in result["ly_do"]
            assert result["duong_dan"] == "/fake/path.xlsx"

    def test_khong_co_file_tra_chua_upload(self):
        mock_info = {"co_file": False, "canh_bao": "", "so_ngay_cu": 0}
        with patch(
            "data.pgd.doc_trang_thai_file",
            return_value=mock_info,
        ):
            result = kiem_tra_nguon_uu_tien("PGD Long Thành", "hstd")
            assert result["nguon_uu_tien"] == NguonDuLieu.CHUA_UPLOAD
            assert "📤" in result["ly_do"]
            assert len(result["canh_bao"]) >= 1

    def test_file_cu_co_canh_bao(self):
        mock_info = {"co_file": True, "canh_bao": "cu", "so_ngay_cu": 7}
        with patch(
            "data.pgd.doc_trang_thai_file",
            return_value=mock_info,
        ), patch("data.pgd.duong_dan_pgd", return_value="/fake/path.xlsx"):
            result = kiem_tra_nguon_uu_tien("PGD Long Thành", "hstd")
            assert len(result["canh_bao"]) >= 1
            assert "cũ" in result["canh_bao"][0].lower() or "7" in result["canh_bao"][0]


class TestThongKeSuDungNguon:
    """thong_ke_su_dung_nguon() — thống kê upload toàn CN."""

    def test_tat_ca_da_upload(self):
        mock_info = {"co_file": True, "canh_bao": "ok", "so_ngay_cu": 0}
        with patch(
            "services.data_priority_service.kiem_tra_nguon_uu_tien",
            return_value={"nguon_uu_tien": NguonDuLieu.PGD_UPLOAD},
        ):
            stats = thong_ke_su_dung_nguon()
            assert stats["pgd_upload"] == len(stats["chi_tiet"])
            assert stats["chua_upload"] == 0

    def test_tat_ca_chua_upload(self):
        with patch(
            "services.data_priority_service.kiem_tra_nguon_uu_tien",
            return_value={"nguon_uu_tien": NguonDuLieu.CHUA_UPLOAD},
        ):
            stats = thong_ke_su_dung_nguon()
            assert stats["pgd_upload"] == 0
            assert stats["chua_upload"] == len(stats["chi_tiet"])

    def test_co_ca_pgd_va_chua_upload(self):
        call_count = [0]

        def _mock(ten_dv, loai):
            call_count[0] += 1
            # PGD đầu tiên đã upload, các PGD còn lại chưa
            if call_count[0] <= 1:
                return {"nguon_uu_tien": NguonDuLieu.PGD_UPLOAD}
            return {"nguon_uu_tien": NguonDuLieu.CHUA_UPLOAD}

        with patch("services.data_priority_service.kiem_tra_nguon_uu_tien", side_effect=_mock):
            stats = thong_ke_su_dung_nguon()
            assert stats["pgd_upload"] == 1
            assert stats["chua_upload"] == len(stats["chi_tiet"]) - 1
