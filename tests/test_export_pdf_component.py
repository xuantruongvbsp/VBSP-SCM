from __future__ import annotations

from io import BytesIO

import pandas as pd
import pdfplumber
import pytest

from components.export_pdf import _format_phan_tram, xuat_pdf_co_chart


def test_format_phan_tram_giu_dung_dau_hang_nghin():
    assert _format_phan_tram(1234.56) == "1.234,56 %"


def test_xuat_pdf_co_chart_o_rong_va_text_dac_biet_khong_crash():
    pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")

    df = pd.DataFrame({
        "Tên PGD": ["PGD A", None],
        "Tên KH": ["Nguyễn & Co <test>", "Trần Thị B"],
        "Mã KH": [75000001, 75000002],
        "Số khế ước": ["KU202600001", "KU202600002"],
        "Tổng dư nợ": [1_000_000, 2_000_000],
        "Tỷ lệ QH %": [0.12, 0.0],
    })
    pdf_bytes = xuat_pdf_co_chart(
        df,
        "Báo cáo test PDF kèm biểu đồ",
        "tester",
        cols_tien=["Tổng dư nợ"],
        cols_percent=["Tỷ lệ QH %"],
        don_vi_tien="triệu đồng",
    )

    assert pdf_bytes.startswith(b"%PDF")
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[0]
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    assert page.width > page.height
    assert "KU202600001" in text
    assert "Nguyễn & Co" in text
    assert "3.000.000" in text
