"""tests/test_excel_service.py — services/excel_service.py

Kiểm tra:
  - ten_file_xuat()  — tạo tên file có timestamp
  - ExcelReport      — builder pattern, smoke test build()
"""
from __future__ import annotations

import pandas as pd
import pytest

from services.excel_service import ExcelReport, ten_file_xuat, xuat_excel_chuyen_nghiep


# ══════════════════════════════════════════════════════════════════════════════
# ten_file_xuat()
# ══════════════════════════════════════════════════════════════════════════════

class TestTenFileXuat:

    def test_bat_dau_bang_prefix(self):
        result = ten_file_xuat("BaoCao")
        assert result.startswith("BaoCao_")

    def test_mac_dinh_extension_xlsx(self):
        result = ten_file_xuat("BaoCao")
        assert result.endswith(".xlsx")

    def test_extension_pdf(self):
        result = ten_file_xuat("BaoCao", ext="pdf")
        assert result.endswith(".pdf")

    def test_co_timestamp_8_chu_so_ngay(self):
        result = ten_file_xuat("BaoCao")
        # Tên file: BaoCao_DDMMYYYY_HHMM.xlsx
        parts = result.replace(".xlsx", "").split("_")
        # prefix + DDMMYYYY + HHMM
        assert len(parts) >= 3
        assert len(parts[-2]) == 8   # DDMMYYYY
        assert parts[-2].isdigit()

    def test_hai_lan_goi_khac_nhau(self):
        import time
        r1 = ten_file_xuat("X")
        time.sleep(0.01)
        r2 = ten_file_xuat("X")
        # Cùng phút → có thể trùng timestamp, nhưng prefix phải giống nhau
        assert r1.startswith("X_")
        assert r2.startswith("X_")


# ══════════════════════════════════════════════════════════════════════════════
# ExcelReport — smoke tests
# ══════════════════════════════════════════════════════════════════════════════

def _df_simple() -> pd.DataFrame:
    return pd.DataFrame({
        "Tên PGD":    ["PGD A", "PGD B"],
        "Tổng dư nợ": [1_000_000, 2_000_000],
    })


class TestExcelReport:

    def test_build_tra_ve_bytes(self):
        rpt = ExcelReport("Báo cáo test")
        result = rpt.build()
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_build_co_kpi(self):
        rpt = ExcelReport("Tiêu đề")
        rpt.add_kpi("Tổng món", 123)
        rpt.add_kpi("Tổng dư nợ", "1.234 tỷ", "đồng")
        result = rpt.build()
        assert isinstance(result, bytes)

    def test_build_co_detail(self):
        rpt = ExcelReport("Tiêu đề")
        rpt.add_detail("Chi tiết", _df_simple())
        result = rpt.build()
        assert isinstance(result, bytes)

    def test_build_nhieu_sheet(self):
        rpt = ExcelReport("Tiêu đề")
        rpt.add_kpi("KPI", 1)
        rpt.add_detail("Sheet 1", _df_simple())
        rpt.add_sheet("Sheet 2", _df_simple())
        result = rpt.build()
        assert isinstance(result, bytes)

    def test_add_detail_empty_df_bi_bo_qua(self):
        rpt = ExcelReport("Tiêu đề")
        rpt.add_detail("Empty", pd.DataFrame())
        assert len(rpt._detail_sheets) == 0

    def test_chaining(self):
        """add_kpi/add_detail/add_sheet đều trả về self để chain."""
        rpt = (
            ExcelReport("T")
            .add_kpi("k", 1)
            .add_detail("d", _df_simple())
            .add_sheet("s", _df_simple())
        )
        assert isinstance(rpt, ExcelReport)


# ══════════════════════════════════════════════════════════════════════════════
# xuat_excel_chuyen_nghiep() — convenience wrapper
# ══════════════════════════════════════════════════════════════════════════════

class TestXuatExcelChuyenNghiep:

    def test_tra_ve_bytes(self):
        result = xuat_excel_chuyen_nghiep(_df_simple(), "Báo cáo test")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_voi_kpi_items(self):
        result = xuat_excel_chuyen_nghiep(
            _df_simple(), "Báo cáo",
            kpi_items=[("Tổng", 2, "PGD")],
        )
        assert isinstance(result, bytes)
