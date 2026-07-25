"""tests/test_luu_pgd_file.py — Test mở rộng cho luu_pgd_file()."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pytest

from services.upload_service import KetQuaUpload, kiem_tra_file, luu_pgd_file
from tests.fixtures import tao_file_hstd_hop_le


# ── Helpers ──────────────────────────────────────────────────────────────────


def _tao_excel_bytes(sheet_name="BCQUERY", rows=2, header_row=4):
    """Tạo file Excel bytes với header tại header_row (0-indexed, dùng startrow)."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "BoQua": ["x"] * rows,
            "Số khế ước": [f"KU{i:03d}" for i in range(rows)],
            "Mã KH": [f"KH{i:03d}" for i in range(rows)],
            "Tên PGD": ["PGD Long Thành"] * rows,
            "Tên xã": ["Phước Thái"] * rows,
            "Dư nợ trong hạn": [1000 * (i + 1) for i in range(rows)],
            "Dư nợ quá hạn": [0] * rows,
            "Tổng dư nợ": [1000 * (i + 1) for i in range(rows)],
            "Nguồn vốn": [1] * rows,
        }
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, startrow=header_row, index=False)
    return buf.getvalue()


def _tao_excel_gqvl_bytes(rows=2):
    """Tạo file Excel GQVL — sheet 'Sheet1', header tại dòng 7 (0-indexed)."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "BoQua": ["x"] * rows,
            "Số khế ước": [f"KU{i:03d}" for i in range(rows)],
            "Mã KH": [f"KH{i:03d}" for i in range(rows)],
            "Tên PGD": ["PGD Long Thành"] * rows,
            "Tổng dư nợ": [5000 * (i + 1) for i in range(rows)],
        }
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sheet1", startrow=7, index=False)
    return buf.getvalue()


def _tao_excel_cdtotkvv_bytes(thang="06", nam="2026"):
    """Tạo file Excel CDTOTKVV có chứa ngày/tháng để doc_thang_nam_tu_file parse được."""
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append([f"BẢNG CHẤM ĐIỂM TỔ TK&VV tháng {thang}/{nam}"])
    ws.append(["STT", "Tên Tổ", "Điểm"])
    ws.append([1, "Tổ 1", 90])
    ws.append([2, "Tổ 2", 85])
    wb.save(buf)
    return buf.getvalue()


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_pgd_dir():
    """Tạo thư mục tạm cho PGD_DATA_DIR."""
    with tempfile.TemporaryDirectory() as tmp:
        pgd_dir = Path(tmp) / "pgd_data"
        pgd_dir.mkdir()
        yield pgd_dir


# ── Tests ────────────────────────────────────────────────────────────────────


class TestLuuPgdFileMoRong:
    """Test mở rộng cho luu_pgd_file() — không trùng với test_upload_supplement.py."""

    def test_luu_nq11_thanh_cong(self, mock_pgd_dir):
        """Upload NQ11 → nq11_latest.xlsx được tạo."""
        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)):
            from data.pgd import pgd_slug

            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True, exist_ok=True)

            fake_excel = _tao_excel_bytes(sheet_name="BCQUERY", header_row=4)
            result = luu_pgd_file("PGD Long Thành", "nq11", fake_excel)

            assert result.thanh_cong is True
            assert (slug_dir / "nq11_latest.xlsx").exists()

    def test_luu_gqvl_thanh_cong(self, mock_pgd_dir):
        """Upload GQVL → gqvl_latest.xlsx được tạo."""
        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)):
            from data.pgd import pgd_slug

            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True, exist_ok=True)

            fake_excel = _tao_excel_gqvl_bytes()
            result = luu_pgd_file("PGD Long Thành", "gqvl", fake_excel)

            assert result.thanh_cong is True
            assert (slug_dir / "gqvl_latest.xlsx").exists()

    def test_file_sai_dinh_dang_pdf(self):
        """File .pdf → kiem_tra_file trả về False."""
        fake_bytes = b"%PDF-1.4 fake content" * 100  # > 1KB
        ok, msg = kiem_tra_file("test.pdf", fake_bytes)
        assert ok is False
        assert "không được hỗ trợ" in msg

    def test_file_qua_nho(self, mock_pgd_dir):
        """File < 1KB → thanh_cong=False."""
        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)):
            small_bytes = b"tiny"  # 4 bytes < 1000
            result = luu_pgd_file("PGD Long Thành", "hstd", small_bytes)
            assert result.thanh_cong is False
            assert "quá nhỏ" in result.thong_bao

    def test_xoa_parquet_cache_sau_upload(self, mock_pgd_dir):
        """Sau upload, file .parquet cùng tên bị xóa."""
        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)):
            from data.pgd import pgd_slug

            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True, exist_ok=True)

            # Tạo file parquet giả
            fake_parquet = slug_dir / "hstd_latest.parquet"
            fake_parquet.write_bytes(b"fake parquet data")
            assert fake_parquet.exists()

            fake_excel = tao_file_hstd_hop_le()
            result = luu_pgd_file("PGD Long Thành", "hstd", fake_excel)

            assert result.thanh_cong is True
            assert not fake_parquet.exists()

    def test_audit_log_ghi_sau_upload(self, mock_pgd_dir):
        """Sau upload thành công, db.ghi_audit được gọi với 'upload_pgd'."""
        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)), \
             patch("services.upload_service.db.ghi_audit") as mock_audit:
            from data.pgd import pgd_slug

            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True, exist_ok=True)

            fake_excel = tao_file_hstd_hop_le()
            result = luu_pgd_file("PGD Long Thành", "hstd", fake_excel)

            assert result.thanh_cong is True
            mock_audit.assert_called_once()
            args = mock_audit.call_args[0]
            assert args[1] == "upload_pgd"
            assert "HSTD" in args[2]

    def test_validation_critical_block(self, mock_pgd_dir):
        """Validation trả về lỗi critical → upload bị block."""
        from services.validation_service import ValidationError, ValidationLevel, ValidationResult

        mock_result = ValidationResult()
        mock_result.add_error(
            ValidationError(
                ValidationLevel.CRITICAL,
                "Mã KH",
                "Thiếu cột bắt buộc",
            )
        )

        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)), \
             patch("services.validation_service.validate_dataframe", return_value=mock_result):
            from data.pgd import pgd_slug

            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True, exist_ok=True)

            fake_excel = tao_file_hstd_hop_le()
            result = luu_pgd_file("PGD Long Thành", "hstd", fake_excel)

            assert result.thanh_cong is False
            assert "không hợp lệ" in result.thong_bao

    def test_validation_warning_khong_block(self, mock_pgd_dir):
        """Validation chỉ có warning → upload vẫn thành công."""
        from services.validation_service import ValidationError, ValidationLevel, ValidationResult

        mock_result = ValidationResult()
        mock_result.add_error(
            ValidationError(
                ValidationLevel.WARNING,
                "Tên xã",
                "Xã không nằm trong danh sách",
            )
        )

        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)), \
             patch("services.validation_service.validate_dataframe", return_value=mock_result):
            from data.pgd import pgd_slug

            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True, exist_ok=True)

            fake_excel = tao_file_hstd_hop_le()
            result = luu_pgd_file("PGD Long Thành", "hstd", fake_excel)

            assert result.thanh_cong is True
            assert (slug_dir / "hstd_latest.xlsx").exists()

    def test_cdtotkvv_luu_lich_su(self, mock_pgd_dir):
        """Upload CDTOTKVV → file lịch sử cdtotkvv_{suffix}.xlsx được tạo."""
        with patch("data.pgd.PGD_DATA_DIR", str(mock_pgd_dir)), \
             patch("data.cdtotkvv.doc_thang_nam_tu_file", return_value="06/2026"):
            from data.pgd import pgd_slug

            slug_dir = mock_pgd_dir / pgd_slug("PGD Long Thành")
            slug_dir.mkdir(parents=True, exist_ok=True)

            fake_excel = _tao_excel_cdtotkvv_bytes()
            result = luu_pgd_file("PGD Long Thành", "cdtotkvv", fake_excel)

            assert result.thanh_cong is True
            assert (slug_dir / "cdtotkvv_latest.xlsx").exists()
            # File lịch sử: suffix từ "06/2026" → "06_2026" hoặc "2026_06"
            lich_su_files = list(slug_dir.glob("cdtotkvv_*.xlsx"))
            # Loại bỏ cdtotkvv_latest.xlsx
            lich_su_files = [f for f in lich_su_files if "latest" not in f.name]
            assert len(lich_su_files) >= 1
