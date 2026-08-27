"""Regression tests for the shared PDF report exporter."""
from __future__ import annotations

from io import BytesIO

import pandas as pd
import pdfplumber

from services.bc_tongquan_service import xuat_pdf_bc


def test_xuat_pdf_bc_render_tat_ca_sheet_khong_rong():
    pdf_bytes = xuat_pdf_bc(
        {
            "Tổng hợp chỉ tiêu": pd.DataFrame([
                {"Chỉ tiêu": "Tổng dư nợ", "Hiện tại (VND)": 12_000_000},
            ]),
            "Theo chương trình": pd.DataFrame([
                {"Chương trình": "Hộ nghèo", "Dư nợ (VND)": 5_000_000},
            ]),
        },
        "So sánh Cân đối",
        "tester",
    )

    assert pdf_bytes.startswith(b"%PDF")
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        extracted = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "Tổng hợp chỉ tiêu" in extracted
    assert "Theo chương trình" in extracted
    assert "Tổng dư nợ" in extracted
    assert "Hộ nghèo" in extracted
    assert "tester" in extracted


def test_xuat_pdf_bc_khong_tao_trang_trang_chi_co_footer():
    rows = [
        {
            "Chương trình": f"Chương trình {index:02d}",
            "DN kỳ trước (triệu đồng)": index * 10,
            "DN hiện tại (triệu đồng)": index * 11,
            "Chênh lệch (triệu đồng)": index,
            "Tỷ lệ %": 10.0,
            "NQH kỳ trước (triệu đồng)": 0,
            "NQH hiện tại (triệu đồng)": 0,
        }
        for index in range(40)
    ]
    pdf_bytes = xuat_pdf_bc(
        {
            "Tổng hợp chỉ tiêu": pd.DataFrame([{"Chỉ tiêu": "Tổng dư nợ", "Giá trị": 1}]),
            "Theo chương trình": pd.DataFrame(rows),
        },
        "So sánh Cân đối",
        "tester",
    )

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        last_page_text = pdf.pages[-1].extract_text() or ""

    assert "Chương trình" in last_page_text
    assert "Tài liệu được tạo tự động" in last_page_text


def test_xuat_pdf_bc_giu_nguyen_cot_ma_dinh_danh():
    pdf_bytes = xuat_pdf_bc(
        {
            "Chi tiết": pd.DataFrame([
                {"Mã KH": 75000001, "Số khế ước": "KU202600001", "Tổng dư nợ": 1_000_000},
            ]),
        },
        "Báo cáo mã định danh",
        "tester",
    )

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        extracted = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "75000001" in extracted
    assert "75.000.001" not in extracted
