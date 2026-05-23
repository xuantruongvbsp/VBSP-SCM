"""tests/test_khtd_nhap_service.py — services/khtd_nhap_service.py

Kiểm tra các hàm thuần:
  - clean_sheet_name()
  - format_kich_thuoc()
  - doc_excel_khtd_cn_upload()
  - doc_excel_khtd_xa_upload()
  - luu_pdf_khtd_xa()
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import pytest

from services.khtd_nhap_service import (
    clean_sheet_name,
    doc_excel_khtd_cn_upload,
    doc_excel_khtd_xa_upload,
    format_kich_thuoc,
    luu_pdf_khtd_xa,
)


def _excel(rows: list[dict]) -> bytes:
    buf = BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# clean_sheet_name()
# ══════════════════════════════════════════════════════════════════════════════

class TestCleanSheetName:

    def test_gioi_han_31_ky_tu(self):
        assert len(clean_sheet_name("A" * 40)) == 31

    def test_giua_nguyen_ten_ngan(self):
        assert clean_sheet_name("Sheet1") == "Sheet1"

    def test_strip_khoang_trang(self):
        assert clean_sheet_name("  Sheet  ") == "Sheet"

    def test_xoa_backslash(self):
        assert "\\" not in clean_sheet_name("A\\B")

    def test_xoa_slash(self):
        assert "/" not in clean_sheet_name("A/B")

    def test_xoa_dau_hoi(self):
        assert "?" not in clean_sheet_name("A?B")

    def test_xoa_dau_ngoac_vuong(self):
        result = clean_sheet_name("A[B]C")
        assert "[" not in result and "]" not in result

    def test_xoa_dau_hai_cham(self):
        assert ":" not in clean_sheet_name("A:B")


# ══════════════════════════════════════════════════════════════════════════════
# format_kich_thuoc()
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatKichThuoc:

    def test_duoi_1mb_hien_thi_kb(self):
        assert "KB" in format_kich_thuoc(500 * 1024)

    def test_tren_1mb_hien_thi_mb(self):
        assert "MB" in format_kich_thuoc(2 * 1024 * 1024)

    def test_dung_ranh_gioi_1mb(self):
        assert "MB" in format_kich_thuoc(1_048_576)

    def test_co_so_thap_phan(self):
        result = format_kich_thuoc(1_500_000)
        assert "." in result


# ══════════════════════════════════════════════════════════════════════════════
# doc_excel_khtd_cn_upload()
# ══════════════════════════════════════════════════════════════════════════════

class TestDocExcelKhtdCnUpload:

    MA_KEYS = {"1_TW", "2_TW", "3_DP"}

    def test_hop_le_tra_ve_dict_vnd(self):
        data = _excel([{"Mã CT": "1_TW", "KH (triệu đồng)": 100.0}])
        patch, _, _ = doc_excel_khtd_cn_upload(data, self.MA_KEYS)
        assert patch["1_TW"] == 100_000_000

    def test_chuyen_trieu_sang_vnd(self):
        data = _excel([{"Mã CT": "1_TW", "KH (triệu đồng)": 5.5}])
        patch, _, _ = doc_excel_khtd_cn_upload(data, self.MA_KEYS)
        assert patch["1_TW"] == 5_500_000

    def test_nhieu_dong_hop_le(self):
        data = _excel([
            {"Mã CT": "1_TW", "KH (triệu đồng)": 100},
            {"Mã CT": "2_TW", "KH (triệu đồng)": 200},
        ])
        patch, so_dong, _ = doc_excel_khtd_cn_upload(data, self.MA_KEYS)
        assert so_dong == 2
        assert patch["2_TW"] == 200_000_000

    def test_thieu_cot_ma_ct_raise_valueerror(self):
        data = _excel([{"Tên CT": "A", "KH (triệu đồng)": 100}])
        with pytest.raises(ValueError, match="Mã CT"):
            doc_excel_khtd_cn_upload(data, self.MA_KEYS)

    def test_thieu_cot_kh_raise_valueerror(self):
        data = _excel([{"Mã CT": "1_TW", "Giá trị": 100}])
        with pytest.raises(ValueError):
            doc_excel_khtd_cn_upload(data, self.MA_KEYS)

    def test_ma_key_khong_hop_le_vao_bo_qua(self):
        data = _excel([{"Mã CT": "UNKNOWN", "KH (triệu đồng)": 100}])
        _, so_dong, bo_qua = doc_excel_khtd_cn_upload(data, self.MA_KEYS)
        assert "UNKNOWN" in bo_qua
        assert so_dong == 0

    def test_gia_tri_0_bi_bo_qua(self):
        data = _excel([{"Mã CT": "1_TW", "KH (triệu đồng)": 0}])
        patch, so_dong, _ = doc_excel_khtd_cn_upload(data, self.MA_KEYS)
        assert so_dong == 0
        assert "1_TW" not in patch

    def test_gia_tri_na_bi_bo_qua(self):
        data = _excel([{"Mã CT": "1_TW", "KH (triệu đồng)": float("nan")}])
        _, so_dong, _ = doc_excel_khtd_cn_upload(data, self.MA_KEYS)
        assert so_dong == 0


# ══════════════════════════════════════════════════════════════════════════════
# doc_excel_khtd_xa_upload()
# ══════════════════════════════════════════════════════════════════════════════

class TestDocExcelKhtdXaUpload:

    MA_KEYS = {"1_TW", "2_TW"}
    DS_XA = {"Xã An Bình", "Xã Phú Hữu"}

    def _xa_excel(self, rows: list[list]) -> bytes:
        buf = BytesIO()
        pd.DataFrame(rows).to_excel(buf, index=False, header=False)
        return buf.getvalue()

    def test_hop_le_tra_ve_updates(self):
        data = self._xa_excel([["Xã An Bình", "1_TW", 50.0]])
        updates, dem, _ = doc_excel_khtd_xa_upload(data, self.DS_XA, self.MA_KEYS)
        assert "Xã An Bình|1_TW" in updates
        assert updates["Xã An Bình|1_TW"] == 50_000_000

    def test_chuyen_trieu_sang_vnd(self):
        data = self._xa_excel([["Xã An Bình", "1_TW", 3.5]])
        updates, _, _ = doc_excel_khtd_xa_upload(data, self.DS_XA, self.MA_KEYS)
        assert updates["Xã An Bình|1_TW"] == 3_500_000

    def test_xa_khong_thuoc_pgd_tao_canh_bao(self):
        data = self._xa_excel([["Xã Không Có", "1_TW", 50.0]])
        _, _, canh_bao = doc_excel_khtd_xa_upload(data, self.DS_XA, self.MA_KEYS)
        assert any("Xã Không Có" in c for c in canh_bao)

    def test_ma_ct_khong_hop_le_tao_canh_bao(self):
        data = self._xa_excel([["Xã An Bình", "UNKNOWN_CT", 50.0]])
        _, _, canh_bao = doc_excel_khtd_xa_upload(data, self.DS_XA, self.MA_KEYS)
        assert any("UNKNOWN_CT" in c for c in canh_bao)

    def test_gia_tri_le_0_bi_bo_qua(self):
        data = self._xa_excel([["Xã An Bình", "1_TW", 0.0]])
        _, dem, _ = doc_excel_khtd_xa_upload(data, self.DS_XA, self.MA_KEYS)
        assert dem == 0

    def test_ds_xa_rong_cho_phep_tat_ca(self):
        """ds_xa_hop_le rỗng → không check xã, chấp nhận bất kỳ."""
        data = self._xa_excel([["Xã Bất Kỳ", "1_TW", 10.0]])
        updates, dem, _ = doc_excel_khtd_xa_upload(data, set(), self.MA_KEYS)
        assert dem == 1


# ══════════════════════════════════════════════════════════════════════════════
# luu_pdf_khtd_xa()
# ══════════════════════════════════════════════════════════════════════════════

class TestLuuPdfKhtdXa:

    def test_pdf_rong_raise(self, tmp_path):
        with pytest.raises(ValueError, match="PDF"):
            luu_pdf_khtd_xa(b"", str(tmp_path), pgd="PGD A", xa="Xã A")

    def test_thu_muc_rong_raise(self, tmp_path):
        with pytest.raises(ValueError):
            luu_pdf_khtd_xa(b"PDF", "", pgd="PGD A", xa="Xã A")

    def test_thu_muc_khong_ton_tai_raise(self):
        with pytest.raises(ValueError):
            luu_pdf_khtd_xa(b"PDF", "/khong/ton/tai/xyz", pgd="PGD A", xa="Xã A")

    def test_luu_thanh_cong_tra_ve_path(self, tmp_path):
        result = luu_pdf_khtd_xa(
            b"PDF content", str(tmp_path),
            pgd="PGD Long Thành", xa="Xã An Bình",
            now=datetime(2026, 5, 23, 10, 30),
        )
        assert result.exists()
        assert result.suffix == ".pdf"

    def test_ten_file_bat_dau_khtd(self, tmp_path):
        result = luu_pdf_khtd_xa(
            b"PDF", str(tmp_path),
            pgd="PGD A", xa="Xã A",
            now=datetime(2026, 5, 23, 10, 30),
        )
        assert result.name.startswith("KHTD_")

    def test_ten_file_co_timestamp(self, tmp_path):
        result = luu_pdf_khtd_xa(
            b"PDF", str(tmp_path),
            pgd="PGD A", xa="Xã A",
            now=datetime(2026, 5, 23, 10, 30),
        )
        assert "20260523" in result.name

    def test_ky_tu_dac_biet_trong_ten_bi_thay_the(self, tmp_path):
        result = luu_pdf_khtd_xa(
            b"PDF", str(tmp_path),
            pgd="PGD A/B:C", xa="Xã A",
            now=datetime(2026, 5, 23, 10, 30),
        )
        assert result.exists()
        assert "/" not in result.name
        assert ":" not in result.name
