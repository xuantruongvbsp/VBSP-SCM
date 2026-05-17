"""
Unit test cho pdf_service.py — VBSP-SCM.

Kiểm tra các hàm xuất PDF:
- xuat_pdf()
- xuat_pdf_bang()

Dùng pytest, mock reportlab để test trường hợp chưa cài thư viện.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest

# ── DataFrame mẫu dùng chung cho các test ──────────────────────────────
df_test = pd.DataFrame({
    "Tên PGD": ["PGD A", "PGD B", "PGD C", "PGD D", "PGD E"],
    "Dư nợ": [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000],
    "Số hộ": [10, 20, 30, 40, 50],
})

df_rong = pd.DataFrame()


# ── Test: xuat_pdf trả về bytes đúng định dạng PDF ─────────────────────
class TestXuatPdf:

    def test_xuat_pdf_tra_ve_bytes(self):
        """Gọi xuat_pdf với DataFrame hợp lệ → trả về bytes, bắt đầu bằng %PDF."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf

        result = xuat_pdf(df_test, "Test báo cáo", "admin")
        assert isinstance(result, bytes), "Kết quả phải là bytes"
        assert len(result) > 0, "Bytes không được rỗng"
        assert result.startswith(b"%PDF"), "Phải bắt đầu bằng %PDF (đúng định dạng PDF)"

    def test_xuat_pdf_co_cot_tien(self):
        """Gọi xuat_pdf với cols_tien → không raise exception, trả về bytes."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf

        # Không raise bất kỳ exception nào
        result = xuat_pdf(df_test, "Test", "admin", cols_tien=["Dư nợ"])
        assert isinstance(result, bytes), "Kết quả phải là bytes"
        assert len(result) > 0, "Bytes không được rỗng"

    def test_xuat_pdf_df_rong(self):
        """Gọi xuat_pdf với DataFrame rỗng → raise ValueError rõ ràng (Table cần ít nhất 1 dòng & 1 cột)."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf

        # DataFrame rỗng → pdf_service tự raise ValueError trước
        with pytest.raises(ValueError, match="Không có dữ liệu để xuất PDF"):
            xuat_pdf(df_rong, "Test rỗng", "admin")

    def test_xuat_pdf_bang_tra_ve_bytes(self):
        """Gọi xuat_pdf_bang → trả về bytes, len > 0."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf_bang

        result = xuat_pdf_bang(df_test, "Test bảng", "admin")
        assert isinstance(result, bytes), "Kết quả phải là bytes"
        assert len(result) > 0, "Bytes không được rỗng"
        assert result.startswith(b"%PDF"), "Phải bắt đầu bằng %PDF"

    def test_reportlab_chua_cai(self):
        """Khi _REPORTLAB_READY = False → raise ImportError với message phù hợp."""
        with patch("pdf_service._REPORTLAB_READY", False):
            from pdf_service import xuat_pdf

            with pytest.raises(ImportError) as exc_info:
                xuat_pdf(df_test, "Test", "admin")
            assert "reportlab" in str(exc_info.value).lower(), (
                "Message lỗi phải đề cập đến reportlab"
            )
