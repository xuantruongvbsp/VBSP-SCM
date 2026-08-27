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
import pdfplumber
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

    def test_format_phan_tram_giu_dung_dau_hang_nghin(self):
        from pdf_service import _format_phan_tram

        assert _format_phan_tram(1234.56) == "1.234,56 %"

    def test_is_money_col_nhan_dien_nq11_giaingan(self):
        """Cột tiền NQ11/GQVL (DNO NQ11, Giải ngân) phải được nhận diện là cột tiền."""
        from pdf_service import _is_money_col

        assert _is_money_col("DNO NQ11") is True
        assert _is_money_col("DNO_NQ11") is True
        assert _is_money_col("Giải ngân trong năm") is True
        assert _is_money_col("Giải_ngân_năm") is True

    def test_xuat_pdf_chi_tiet_scale_trieu_va_don_vi(self):
        """xuat_pdf_chi_tiet với scale_money=True → đơn vị triệu đồng và tiền chia 1e6."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf_chi_tiet

        df = pd.DataFrame({
            "Chương trình": ["A", "B"],
            "DNO_NQ11": [1_500_000_000, 2_500_000_000],
            "Số_món": [10, 20],
        })
        pdf_bytes = xuat_pdf_chi_tiet(
            df, list(df.columns), "Test NQ11", "admin",
            don_vi_tien="triệu đồng", scale_money=True,
        )
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        assert "triệu đồng" in text
        assert "1.500" in text
        assert "2.500" in text

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

    def test_xuat_pdf_nhan_dong_tong_tuy_chinh(self):
        """Dòng tổng tùy chỉnh render được cả số tiền và cột đếm/tỷ lệ."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf

        result = xuat_pdf(
            df_test,
            "Test tổng tùy chỉnh",
            "admin",
            cols_tien=["Dư nợ"],
            cols_right=["Số hộ"],
            dong_tong={"Tên PGD": "TỔNG CỘNG", "Dư nợ": 15_000_000, "Số hộ": 150},
        )

        assert isinstance(result, bytes)
        assert result.startswith(b"%PDF")

    def test_xuat_pdf_dong_tong_format_duoc_numpy_number(self):
        """Dòng tổng từ pandas/numpy phải có phân cách hàng nghìn trong PDF."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf

        df = pd.DataFrame({
            "Chương trình": ["A", "B"],
            "Tổng dư nợ": [1_000_000_000, 2_500_000_000],
            "Dư nợ QH": [10_000_000, 20_000_000],
        })
        pdf_bytes = xuat_pdf(
            df,
            "Test tổng số lớn",
            "tester",
            cols_tien=["Tổng dư nợ", "Dư nợ QH"],
        )

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        assert "3.500.000.000" in text
        assert "3500000000" not in text

    def test_xuat_pdf_sau_cot_dung_kho_ngang(self):
        """Bảng 6 cột số nhiều cần khổ ngang để tránh cột tiền bị bẻ dòng xấu."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf

        df = pd.DataFrame({
            "Chương trình": ["A"],
            "Số KH": [1],
            "Số món": [1],
            "Tổng dư nợ": [1_000_000_000],
            "Dư nợ QH": [0],
            "Tỷ lệ QH %": [0],
        })
        pdf_bytes = xuat_pdf(
            df,
            "Test sáu cột",
            "tester",
            cols_tien=["Tổng dư nợ", "Dư nợ QH"],
            cols_right=["Số KH", "Số món", "Tỷ lệ QH %"],
        )

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[0]

        assert page.width > page.height

    def test_col_ratio_pdf_uu_tien_cot_moc_3112_va_bq_kh(self):
        """Cột mốc 31/12 và BQ/KH không được rơi về ratio mặc định quá hẹp."""
        from pdf_service import _col_ratio_pdf

        assert _col_ratio_pdf("31/12/2025") == 1.75
        assert _col_ratio_pdf("± 31/12") == 1.75
        assert _col_ratio_pdf("BQ/KH") == 1.15

    def test_xuat_pdf_group_header_khong_dung_glyph_la(self):
        """Nhãn nhóm trong PDF group header phải render bằng chữ thường, không dùng ký tự dễ lỗi font."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf_group_header

        df = pd.DataFrame({
            "Tên PGD": ["PGD A"],
            "Tên KH": ["Nguyễn Văn A"],
            "Tổng dư nợ": [1_000_000],
        })
        pdf_bytes = xuat_pdf_group_header(
            df,
            "Test group",
            "Tên PGD",
            "tester",
            cols_tien=["Tổng dư nợ"],
        )

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        assert "▸" not in text
        assert "Tên PGD: PGD A" in text

    def test_xuat_pdf_bao_cao_escape_text_dac_biet(self):
        """Đường xuất PDF báo cáo phụ không được crash khi tiêu đề/KPI/cell có &, <, >."""
        pytest.importorskip("reportlab", reason="Chưa cài thư viện reportlab")
        from pdf_service import xuat_pdf_bao_cao

        df = pd.DataFrame({
            "Tên KH": ["Nguyễn & Co <test>"],
            "Tổng dư nợ": [1_000_000],
        })
        pdf_bytes = xuat_pdf_bao_cao(
            df,
            "Báo cáo A & B <C>",
            "tester & admin",
            kpi_items=[{"label": "Số KH & món", "value": "1 < 2", "delta": 1.2}],
            cols_tien=["Tổng dư nợ"],
        )

        assert pdf_bytes.startswith(b"%PDF")
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        assert "Nguyễn & Co" in text
        assert "1.000.000" in text

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
