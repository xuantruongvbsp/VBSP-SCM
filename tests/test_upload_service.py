"""
tests/test_upload_service.py
─────────────────────────────
Unit test cho services/upload_service.py.
Dùng pytest + unittest.mock — không cần DB thật, không cần file thật.
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── Import module cần test ──────────────────────────────────────────────────
try:
    from services.upload_service import (
        KetQuaUpload,
        kiem_tra_file,
        kiem_tra_file_he_thong,
    )
except ImportError:
    from upload_service import (
        KetQuaUpload,
        kiem_tra_file,
        kiem_tra_file_he_thong,
    )


# ── Helpers tạo file bytes giả ──────────────────────────────────────────────
def _excel_bytes_nho() -> bytes:
    """Trả về bytes Excel giả < 1KB (file quá nhỏ)."""
    return b"PK\x03\x04" + b"\x00" * 100  # magic bytes xlsx nhưng < 1KB


def _excel_bytes_hop_le() -> bytes:
    """Tạo file Excel thật bằng openpyxl (> 1KB)."""
    import openpyxl
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tên PGD", "Mã KH", "Tổng dư nợ"])
    ws.append(["PGD Biên Hòa", "KH001", 10_000_000])
    wb.save(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# TEST KetQuaUpload
# ══════════════════════════════════════════════════════════════════════════════
class TestKetQuaUpload:
    def test_thanh_cong_true(self):
        kq = KetQuaUpload(True, "OK", "/path/file.xlsx")
        assert kq.thanh_cong is True
        assert kq.thong_bao == "OK"
        assert kq.duong_dan == "/path/file.xlsx"

    def test_that_bai(self):
        kq = KetQuaUpload(False, "Lỗi upload")
        assert kq.thanh_cong is False
        assert kq.duong_dan == ""

    def test_hien_thi_thanh_cong(self):
        """hien_thi() gọi st.success khi thanh_cong=True."""
        kq = KetQuaUpload(True, "Upload OK")
        with patch("streamlit.success") as mock_success:
            kq.hien_thi()
            mock_success.assert_called_once_with("Upload OK")

    def test_hien_thi_that_bai(self):
        """hien_thi() gọi st.error khi thanh_cong=False."""
        kq = KetQuaUpload(False, "Upload lỗi")
        with patch("streamlit.error") as mock_error:
            kq.hien_thi()
            mock_error.assert_called_once_with("Upload lỗi")


# ══════════════════════════════════════════════════════════════════════════════
# TEST kiem_tra_file
# ══════════════════════════════════════════════════════════════════════════════
class TestKiemTraFile:
    def test_file_hop_le(self):
        ok, msg = kiem_tra_file("HSTD_BienHoa.xlsx", _excel_bytes_hop_le())
        assert ok is True
        assert msg == "OK"

    def test_dinh_dang_sai(self):
        ok, msg = kiem_tra_file("bao_cao.pdf", b"\x00" * 5000)
        assert ok is False
        assert "không được hỗ trợ" in msg.lower() or "pdf" in msg.lower()

    def test_file_qua_nho(self):
        ok, msg = kiem_tra_file("HSTD.xlsx", b"\x00" * 100)
        assert ok is False
        assert "nhỏ" in msg.lower() or "kb" in msg.lower()

    def test_extension_xls_hop_le(self):
        ok, msg = kiem_tra_file("data.xls", _excel_bytes_hop_le())
        assert ok is True

    def test_ten_file_khong_co_extension(self):
        ok, msg = kiem_tra_file("HSTD", _excel_bytes_hop_le())
        assert ok is False

    def test_custom_exts_chophep(self):
        """Cho phép .csv nếu truyền exts_chophep tùy chỉnh."""
        ok, msg = kiem_tra_file(
            "data.csv",
            b"col1,col2\n" + b"a,b\n" * 250,
            exts_chophep={".csv"},
        )
        assert ok is True


# ══════════════════════════════════════════════════════════════════════════════
# TEST kiem_tra_file_he_thong
# ══════════════════════════════════════════════════════════════════════════════
class TestKiemTraFileHeThong:
    """
    FILES_HE_THONG là dict tên file → config trong upload_service.
    Test dùng patch để không phụ thuộc giá trị thực tế.
    """

    def _patch_files(self, ten_file_hop_le: str):
        try:
            import services.upload_service as svc
        except ImportError:
            import upload_service as svc
        return patch.object(
            svc, "FILES_HE_THONG", {ten_file_hop_le: {}}
        )

    def test_ten_file_hop_le(self):
        ten = "HSTD_CN.xlsx"
        with self._patch_files(ten):
            ok, msg = kiem_tra_file_he_thong(ten, _excel_bytes_hop_le())
        assert ok is True

    def test_ten_file_sai(self):
        with self._patch_files("HSTD_DUNG.xlsx"):
            ok, msg = kiem_tra_file_he_thong(
                "file_sai_ten.xlsx", _excel_bytes_hop_le()
            )
        assert ok is False
        assert "không hợp lệ" in msg.lower() or "tên" in msg.lower()

    def test_dinh_dang_sai_uu_tien_truoc(self):
        """Lỗi định dạng phải được trả về trước lỗi tên file."""
        with self._patch_files("HSTD_CN.xlsx"):
            ok, msg = kiem_tra_file_he_thong("wrong.pdf", b"\x00" * 5000)
        assert ok is False
        assert "pdf" in msg.lower() or "không được hỗ trợ" in msg.lower()
