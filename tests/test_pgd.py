"""Unit test cho data/pgd.py — quản lý file dữ liệu riêng từng PGD."""
import os
import tempfile
import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd


class TestPgdSlug(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import pgd
        cls.pgd = pgd

    def test_slug_pgd_long_thanh(self) -> None:
        self.assertEqual(self.pgd.pgd_slug("PGD Long Thành"), "pgd_long_thanh")

    def test_slug_pgd_bien_hoa(self) -> None:
        self.assertEqual(self.pgd.pgd_slug("PGD Biên Hòa"), "pgd_bien_hoa")

    def test_slug_pgd_dinh_quan(self) -> None:
        self.assertEqual(self.pgd.pgd_slug("PGD Định Quán"), "pgd_dinh_quan")

    def test_slug_pgd_1(self) -> None:
        self.assertEqual(self.pgd.pgd_slug("PGD 1"), "pgd_1")

    def test_slug_chi_chua_ky_tu_hop_le(self) -> None:
        result = self.pgd.pgd_slug("PGD Xuân Lộc")
        self.assertRegex(result, r"^[a-z0-9_]+$")

    def test_slug_khong_dau_cach_thua(self) -> None:
        result = self.pgd.pgd_slug("  PGD Long Khánh  ")
        self.assertNotEqual(result[0], "_")
        self.assertNotEqual(result[-1], "_")

    def test_slug_hoi_so(self) -> None:
        self.assertEqual(self.pgd.pgd_slug("Hội sở Chi nhánh tỉnh"), "hoi_so_chi_nhanh_tinh")


class TestPgdDuongDan(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import pgd
        cls.pgd = pgd

    def test_thu_muc_pgd_tra_path(self) -> None:
        path = self.pgd.thu_muc_pgd("PGD Long Thành")
        self.assertIsInstance(path, Path)
        self.assertTrue(str(path).endswith("pgd_long_thanh"))
        self.assertTrue(path.exists())

    def test_thu_muc_pgd_tao_thu_muc(self) -> None:
        path = self.pgd.thu_muc_pgd("PGD Tạm Thời")
        try:
            self.assertTrue(path.exists())
            self.assertTrue(path.is_dir())
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_duong_dan_pgd_hstd(self) -> None:
        path = self.pgd.duong_dan_pgd("PGD Long Thành", "hstd")
        self.assertTrue(path.endswith("hstd_latest.xlsx"))
        self.assertIn("pgd_long_thanh", path)

    def test_duong_dan_pgd_nq11(self) -> None:
        path = self.pgd.duong_dan_pgd("PGD Long Thành", "nq11")
        self.assertTrue(path.endswith("nq11_latest.xlsx"))

    def test_duong_dan_pgd_gqvl(self) -> None:
        path = self.pgd.duong_dan_pgd("PGD Long Thành", "gqvl")
        self.assertTrue(path.endswith("gqvl_latest.xlsx"))

    def test_duong_dan_pgd_cdtotkvv(self) -> None:
        path = self.pgd.duong_dan_pgd("PGD Long Thành", "cdtotkvv")
        self.assertTrue(path.endswith("cdtotkvv_latest.xlsx"))

    def test_duong_dan_pgd_dienbao_ht(self) -> None:
        path = self.pgd.duong_dan_pgd("PGD Long Thành", "dienbao_ht")
        self.assertTrue(path.endswith("dienbao_ht.xlsx"))

    def test_duong_dan_pgd_dienbao_prev(self) -> None:
        path = self.pgd.duong_dan_pgd("PGD Long Thành", "dienbao_prev")
        self.assertTrue(path.endswith("dienbao_prev.xlsx"))

    def test_duong_dan_gqvl_pgd_chua_slug(self) -> None:
        path = self.pgd.duong_dan_gqvl_pgd("PGD Long Thành")
        self.assertIn("gqvl_pgd", path)
        self.assertTrue(path.endswith(".xlsx"))

    def test_kiem_tra_file_ton_tai_chua_co(self) -> None:
        result = self.pgd.kiem_tra_file_ton_tai_pgd("PGD Không Tồn Tại", "hstd")
        self.assertFalse(result)


class TestPgdLuuFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import pgd
        cls.pgd = pgd

    def test_luu_file_pgd_tao_file(self) -> None:
        ten_pgd = "PGD Test Lưu"
        loai = "hstd"
        file_bytes = b"dummy content"
        try:
            path = self.pgd.luu_file_pgd(ten_pgd, loai, file_bytes)
            self.assertTrue(os.path.exists(path))
            with open(path, "rb") as f:
                self.assertEqual(f.read(), file_bytes)
        finally:
            import shutil
            shutil.rmtree(
                Path(self.pgd.duong_dan_pgd(ten_pgd, loai)).parent,
                ignore_errors=True,
            )

    def test_luu_file_pgd_ghi_de(self) -> None:
        ten_pgd = "PGD Test Ghi Đè"
        loai = "hstd"
        try:
            path1 = self.pgd.luu_file_pgd(ten_pgd, loai, b"content1")
            path2 = self.pgd.luu_file_pgd(ten_pgd, loai, b"content2")
            self.assertEqual(path1, path2)
            with open(path2, "rb") as f:
                self.assertEqual(f.read(), b"content2")
        finally:
            import shutil
            shutil.rmtree(
                Path(self.pgd.duong_dan_pgd(ten_pgd, loai)).parent,
                ignore_errors=True,
            )

    def test_luu_file_pgd_voi_lich_su_tao_ca_hai(self) -> None:
        ten_pgd = "PGD Test Lịch Sử"
        loai = "hstd"
        try:
            path = self.pgd.luu_file_pgd_voi_lich_su(
                ten_pgd, loai, b"content", "06/2026"
            )
            thu_muc = Path(path).parent
            self.assertTrue((thu_muc / "hstd_latest.xlsx").exists())
            self.assertTrue((thu_muc / "hstd_2026_06.xlsx").exists())
        finally:
            import shutil
            shutil.rmtree(
                Path(self.pgd.duong_dan_pgd(ten_pgd, loai)).parent,
                ignore_errors=True,
            )

    def test_luu_file_pgd_voi_lich_su_khong_ghi_de_file_cu(self) -> None:
        ten_pgd = "PGD Test Lịch Sử 2"
        loai = "hstd"
        try:
            self.pgd.luu_file_pgd_voi_lich_su(
                ten_pgd, loai, b"content_v1", "06/2026"
            )
            self.pgd.luu_file_pgd_voi_lich_su(
                ten_pgd, loai, b"content_v2", "06/2026"
            )
            thu_muc = Path(self.pgd.duong_dan_pgd(ten_pgd, loai)).parent
            ver_path = thu_muc / "hstd_2026_06.xlsx"
            with open(ver_path, "rb") as f:
                self.assertEqual(f.read(), b"content_v1")
        finally:
            import shutil
            shutil.rmtree(
                Path(self.pgd.duong_dan_pgd(ten_pgd, loai)).parent,
                ignore_errors=True,
            )

    def test_luu_gqvl_pgd(self) -> None:
        ten_pgd = "PGD Test GQVL"
        try:
            path = self.pgd.luu_gqvl_pgd(ten_pgd, b"gqvl_content")
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith("gqvl_latest.xlsx"))
        finally:
            import shutil
            shutil.rmtree(
                Path(self.pgd.duong_dan_pgd(ten_pgd, "gqvl")).parent,
                ignore_errors=True,
            )


class TestPgdXlsxValToDatetime(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import pgd
        cls.pgd = pgd

    def test_xlsx_val_none(self) -> None:
        result = self.pgd._xlsx_val_to_datetime(None)
        self.assertIsNone(result)

    def test_xlsx_val_datetime(self) -> None:
        dt = datetime(2026, 5, 8, 10, 30)
        result = self.pgd._xlsx_val_to_datetime(dt)
        self.assertEqual(result, dt)

    def test_xlsx_val_date(self) -> None:
        from datetime import date
        d = date(2026, 5, 8)
        result = self.pgd._xlsx_val_to_datetime(d)
        self.assertEqual(result, datetime(2026, 5, 8, 0, 0))

    def test_xlsx_val_serial_number(self) -> None:
        result = self.pgd._xlsx_val_to_datetime(45000.0)
        self.assertIsInstance(result, datetime)

    def test_xlsx_val_str_dd_mm_yyyy(self) -> None:
        result = self.pgd._xlsx_val_to_datetime("08/05/2026")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 5)

    def test_xlsx_val_str_yyyy_mm_dd(self) -> None:
        result = self.pgd._xlsx_val_to_datetime("2026-05-08")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)

    def test_xlsx_val_str_invalid(self) -> None:
        result = self.pgd._xlsx_val_to_datetime("")
        self.assertIsNone(result)

    def test_xlsx_val_int(self) -> None:
        result = self.pgd._xlsx_val_to_datetime(45000)
        self.assertIsInstance(result, datetime)


class TestPgdDocTrangThai(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import pgd
        cls.pgd = pgd

    def test_doc_trang_thai_file_chua_co(self) -> None:
        tt = self.pgd.doc_trang_thai_file("PGD Không Tồn Tại", "hstd")
        self.assertFalse(tt["co_file"])
        self.assertEqual(tt["canh_bao"], "khong_co")
        self.assertIsNone(tt["ngay_upload"])
        self.assertIsNone(tt["so_ngay_cu"])
        self.assertIsNone(tt["ngay_so_lieu"])

    def test_doc_trang_thai_file_vua_tao(self) -> None:
        ten_pgd = "PGD Test Trạng Thái"
        loai = "hstd"
        try:
            self.pgd.luu_file_pgd(ten_pgd, loai, b"dummy")
            tt = self.pgd.doc_trang_thai_file(ten_pgd, loai)
            self.assertTrue(tt["co_file"])
            self.assertIn(tt["canh_bao"], ("ok", "cu"))
            self.assertIsNotNone(tt["ngay_upload"])
        finally:
            import shutil
            shutil.rmtree(
                Path(self.pgd.duong_dan_pgd(ten_pgd, loai)).parent,
                ignore_errors=True,
            )

    def test_format_badge_khong_co(self) -> None:
        tt = {"co_file": False}
        badge = self.pgd._format_badge(tt)
        self.assertIn("Chưa có", badge)

    def test_format_badge_co_file(self) -> None:
        tt = {
            "co_file": True,
            "ngay_upload": datetime(2026, 5, 8),
            "ngay_so_lieu": datetime(2026, 5, 7),
            "canh_bao": "ok",
            "so_ngay_cu": 1,
        }
        badge = self.pgd._format_badge(tt)
        self.assertIn("✅", badge)
        self.assertIn("07/05", badge)

    def test_format_badge_canh_bao_cu(self) -> None:
        tt = {
            "co_file": True,
            "ngay_upload": datetime(2026, 1, 1),
            "ngay_so_lieu": None,
            "canh_bao": "cu",
            "so_ngay_cu": 127,
        }
        badge = self.pgd._format_badge(tt)
        self.assertIn("⚠️", badge)
        self.assertIn("127 ngày", badge)


class TestPgdDsPgdCoFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import pgd
        cls.pgd = pgd

    def test_ds_pgd_co_file_chua_co(self) -> None:
        result = self.pgd.ds_pgd_co_file("xyz_invalid")
        self.assertIsInstance(result, list)

    def test_ds_pgd_co_gqvl_chua_co_tra_list(self) -> None:
        result = self.pgd.ds_pgd_co_gqvl()
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
