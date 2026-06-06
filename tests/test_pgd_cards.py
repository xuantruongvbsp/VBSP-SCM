"""Test helpers trong tab_pgd_cards.py — không phụ thuộc Streamlit."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from config import PGD_DATA_DIR


# ── Import helpers từ tab_pgd_cards ──────────────────────────────────────────

@pytest.fixture
def mock_pgd_dir():
    """Tạo thư mục pgd_data tạm, dọn sau test."""
    with tempfile.TemporaryDirectory() as tmp:
        pgd_dir = Path(tmp) / "pgd_data"
        slug_dir = pgd_dir / "pgd_long_thanh"
        slug_dir.mkdir(parents=True)
        yield pgd_dir, slug_dir


class TestNqhColor:
    """_nqh_color() phân loại mức NQH."""

    def test_duoi_1_tra_xanh(self):
        from tabs.tab_pgd_cards import _nqh_color
        assert _nqh_color(0.5) == "green"
        assert _nqh_color(0.99) == "green"
        assert _nqh_color(0.0) == "green"

    def test_tu_1_den_duoi_3_tra_amber(self):
        from tabs.tab_pgd_cards import _nqh_color
        assert _nqh_color(1.0) == "amber"
        assert _nqh_color(2.5) == "amber"
        assert _nqh_color(2.99) == "amber"

    def test_tu_3_tro_len_tra_red(self):
        from tabs.tab_pgd_cards import _nqh_color
        assert _nqh_color(3.0) == "red"
        assert _nqh_color(10.0) == "red"
        assert _nqh_color(100.0) == "red"


class TestFmtBqHo:
    """_fmt_bq_ho() hiển thị dư nợ bình quân hộ."""

    def test_tren_100_trieu(self):
        from tabs.tab_pgd_cards import _fmt_bq_ho
        assert "tr" in _fmt_bq_ho(150_000_000)
        assert "150" in _fmt_bq_ho(150_000_000) or "150.0" in _fmt_bq_ho(150_000_000)

    def test_duoi_100_trieu(self):
        from tabs.tab_pgd_cards import _fmt_bq_ho
        assert "tr" in _fmt_bq_ho(45_500_000)
        # Làm tròn 1 số lẻ nếu < 100
        result = _fmt_bq_ho(45_500_000)
        assert "45.5" in result


class TestRenderCardHtml:
    """_render_card_html() tạo HTML card."""

    def test_co_day_du_thong_tin(self):
        from tabs.tab_pgd_cards import _render_card_html
        row = {
            "ten_pgd": "PGD Long Thành",
            "du_no": 50_000_000_000,
            "ty_le_nqh": 1.25,
            "no_den_han_thang": 500_000_000,
            "so_kh": 1200,
            "dn_binh_quan_ho": 41_000_000,
            "so_mon": 1250,
        }
        html = _render_card_html(row, True, "05/06 14:30", 3)
        assert "PGD Long Thành" in html
        assert "✅" in html
        assert "#3" in html

    def test_khong_co_file(self):
        from tabs.tab_pgd_cards import _render_card_html
        row = {
            "ten_pgd": "PGD Long Thành",
            "du_no": 0,
            "ty_le_nqh": 0,
            "no_den_han_thang": 0,
            "so_kh": 0,
            "dn_binh_quan_ho": 0,
            "so_mon": 0,
        }
        html = _render_card_html(row, False, "—", 0)
        assert "❌" in html

    def test_nqh_red_cho_vuot_nguong(self):
        from tabs.tab_pgd_cards import _render_card_html
        row = {
            "ten_pgd": "PGD Test",
            "du_no": 10_000_000_000,
            "ty_le_nqh": 4.5,
            "no_den_han_thang": 0,
            "so_kh": 100,
            "dn_binh_quan_ho": 100_000_000,
            "so_mon": 100,
        }
        html = _render_card_html(row, True, "06/06 07:00", 1)
        assert "red" in html  # badge màu đỏ


class TestPgdFilePath:
    """_pgd_file_path / _pgd_khnv_path trả về Path đúng."""

    def test_pgd_file_path_dung_loai_hstd(self):
        from tabs.tab_pgd_cards import _pgd_file_path
        p = _pgd_file_path("PGD Long Thành")
        assert isinstance(p, Path)
        assert p.name == "hstd_latest.xlsx"

    def test_pgd_khnv_path_dung_loai_hstd_khnv(self):
        from tabs.tab_pgd_cards import _pgd_khnv_path
        p = _pgd_khnv_path("PGD Long Thành")
        assert isinstance(p, Path)
        assert p.name == "hstd_khnv.xlsx"


class TestUploadInfo:
    """_upload_info() kiểm tra cả 2 loại file."""

    def test_khong_co_file_nao(self, mock_pgd_dir):
        pgd_dir, slug_dir = mock_pgd_dir
        # Mock trực tiếp 2 hàm trả về Path
        with patch("tabs.tab_pgd_cards._pgd_file_path", return_value=slug_dir / "hstd_latest.xlsx"), \
             patch("tabs.tab_pgd_cards._pgd_khnv_path", return_value=slug_dir / "hstd_khnv.xlsx"):
            from tabs.tab_pgd_cards import _upload_info
            ok, ts = _upload_info("PGD Long Thành")
            assert ok is False
            assert ts == "—"

    def test_chi_co_hstd_latest(self, mock_pgd_dir):
        pgd_dir, slug_dir = mock_pgd_dir
        (slug_dir / "hstd_latest.xlsx").write_text("fake")
        with patch("tabs.tab_pgd_cards._pgd_file_path", return_value=slug_dir / "hstd_latest.xlsx"), \
             patch("tabs.tab_pgd_cards._pgd_khnv_path", return_value=slug_dir / "hstd_khnv.xlsx"):
            from tabs.tab_pgd_cards import _upload_info
            ok, ts = _upload_info("PGD Long Thành")
            assert ok is True
            assert ts != "—"
            assert "/" in ts  # format dd/mm HH:MM

    def test_chi_co_hstd_khnv(self, mock_pgd_dir):
        pgd_dir, slug_dir = mock_pgd_dir
        (slug_dir / "hstd_khnv.xlsx").write_text("fake")
        with patch("tabs.tab_pgd_cards._pgd_file_path", return_value=slug_dir / "hstd_latest.xlsx"), \
             patch("tabs.tab_pgd_cards._pgd_khnv_path", return_value=slug_dir / "hstd_khnv.xlsx"):
            from tabs.tab_pgd_cards import _upload_info
            ok, ts = _upload_info("PGD Long Thành")
            assert ok is True
            assert ts != "—"

    def test_co_ca_2_file_lay_moi_nhat(self, mock_pgd_dir):
        pgd_dir, slug_dir = mock_pgd_dir
        f1 = slug_dir / "hstd_latest.xlsx"
        f2 = slug_dir / "hstd_khnv.xlsx"
        f1.write_text("old")
        f2.write_text("new")
        os.utime(str(f1), (1000000000, 1000000000))
        os.utime(str(f2), (2000000000, 2000000000))
        with patch("tabs.tab_pgd_cards._pgd_file_path", return_value=f1), \
             patch("tabs.tab_pgd_cards._pgd_khnv_path", return_value=f2):
            from tabs.tab_pgd_cards import _upload_info
            ok, ts = _upload_info("PGD Long Thành")
            assert ok is True
            expected = datetime.fromtimestamp(2000000000).strftime("%d/%m %H:%M")
            assert ts == expected
