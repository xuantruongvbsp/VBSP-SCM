"""Bổ sung test upload_service.py — upload HSTD lưu hstd_khnv.xlsx."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from services.upload_service import luu_pgd_file, KetQuaUpload
from tests.fixtures import tao_file_hstd_hop_le


# Block Telegram HTTP calls — tránh gửi tin nhắn thật khi chạy test
@pytest.fixture(autouse=True)
def _mock_telegram_upload_pgd():
    with patch("services.telegram_service.gui_thong_bao_upload_pgd", return_value=True):
        yield


class TestLuuPgdFileHstdKhnv:
    """luu_pgd_file() — upload HSTD lưu vào đúng loại file."""

    @pytest.fixture
    def mock_pgd_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pgd_dir = Path(tmp) / "pgd_data"
            yield pgd_dir

    def test_luu_hstd_thanh_cong(self, mock_pgd_dir):
        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)):
            from data.pgd import pgd_slug
            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True)

            fake_excel = tao_file_hstd_hop_le()
            result = luu_pgd_file("PGD Long Thành", "hstd", fake_excel)
            assert result.thanh_cong is True
            assert (slug_dir / "hstd_latest.xlsx").exists()

    def test_luu_hstd_khong_ghi_de_khnv(self, mock_pgd_dir):
        """Upload HSTD PGD không được ghi vào hstd_khnv.xlsx."""
        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)):
            from data.pgd import pgd_slug
            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True)
            (slug_dir / "hstd_khnv.xlsx").write_text("KHNV data")
            original = (slug_dir / "hstd_khnv.xlsx").read_text()

            fake_excel = tao_file_hstd_hop_le()
            result = luu_pgd_file("PGD Long Thành", "hstd", fake_excel)
            assert result.thanh_cong is True
            assert (slug_dir / "hstd_khnv.xlsx").read_text() == original


class TestKetQuaUpload:
    def test_thanh_cong(self):
        kq = KetQuaUpload(True, "✅ OK", "/path/to/file.xlsx")
        assert kq.thanh_cong is True
        assert "✅" in kq.thong_bao

    def test_that_bai(self):
        kq = KetQuaUpload(False, "❌ Lỗi")
        assert not kq.thanh_cong
        assert "❌" in kq.thong_bao
