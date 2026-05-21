"""Unit tests cho services/report_service.py — Xuất báo cáo Excel."""
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import pytest

from services.report_service import ten_file_bao_cao, xuat_bao_cao, xuat_sheet_don


class TestTenFileBaoCao:
    def test_ten_file_xlsx(self):
        ten = ten_file_bao_cao("bao_cao")
        today = datetime.now().strftime("%d%m%Y")
        assert ten == f"bao_cao_{today}.xlsx"

    def test_ten_file_pdf(self):
        ten = ten_file_bao_cao("bieu_mau", ext="pdf")
        today = datetime.now().strftime("%d%m%Y")
        assert ten == f"bieu_mau_{today}.pdf"

    def test_ten_chua_ngay(self):
        ten = ten_file_bao_cao("test")
        assert re.match(r"test_\d{8}\.xlsx", ten)


class TestXuatBaoCao:
    def test_xuat_sheet_don(self):
        df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        pdf_bytes = xuat_sheet_don(df, "Báo cáo test", "tester")
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_xuat_bao_cao_nhieu_sheet(self):
        sheets = {
            "Sheet 1": pd.DataFrame({"A": [1, 2]}),
            "Sheet 2": pd.DataFrame({"B": ["x", "y"]}),
        }
        pdf_bytes = xuat_bao_cao(sheets, "Báo cáo tổng hợp", "tester")
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_xuat_bao_cao_sheet_trong(self):
        sheets = {
            "Sheet 1": pd.DataFrame({"A": [1]}),
            "Sheet 2": pd.DataFrame(),
            "Sheet 3": None,
        }
        pdf_bytes = xuat_bao_cao(sheets, "Test", "tester")
        assert isinstance(pdf_bytes, bytes)

    def test_xuat_bao_cao_df_trong(self):
        sheets = {"Dữ liệu": pd.DataFrame()}
        pdf_bytes = xuat_bao_cao(sheets, "Test", "tester")
        assert isinstance(pdf_bytes, bytes)

    def test_xuat_sheet_don_unicode(self):
        df = pd.DataFrame({"Tên KH": ["Nguyễn Văn A", "Trần Thị B"]})
        pdf_bytes = xuat_sheet_don(df, "Báo cáo tiếng Việt", "người_dùng")
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_xuat_bao_cao_nhieu_dong(self):
        df = pd.DataFrame({"A": range(100), "B": range(100)})
        pdf_bytes = xuat_sheet_don(df, "Báo cáo lớn", "tester")
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 200
