"""Unit test cho data/hstd.py — đọc dữ liệu HSTD, Điện báo, phân tích rủi ro."""
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import pandas as pd


class TestDienBao(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import hstd
        cls.hstd = hstd

    def _tao_file_dienbao(self, data: list[list]) -> bytes:
        df = pd.DataFrame(data)
        bio = BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            df.to_excel(writer, header=False, index=False)
        return bio.getvalue()

    def test_doc_dienbao_rong(self) -> None:
        fp = tempfile.mktemp(suffix=".xlsx")
        try:
            df_empty = pd.DataFrame()
            df_empty.to_excel(fp, header=False, index=False)
            rows = self.hstd.doc_dienbao(fp, 0)
            self.assertIsInstance(rows, list)
        finally:
            if os.path.exists(fp):
                os.unlink(fp)

    def test_doc_dienbao_co_du_lieu(self) -> None:
        data = [
            ["", "Chỉ tiêu", None],
            ["", "Tổng dư nợ", 500_000_000_000],
            ["", "Dư nợ quá hạn", 10_000_000_000],
            ["", "Trđ:", 5_000_000_000],
        ]
        fp = tempfile.mktemp(suffix=".xlsx")
        try:
            df = pd.DataFrame(data)
            df.to_excel(fp, header=False, index=False)
            rows = self.hstd.doc_dienbao(fp, 0)
            self.assertGreater(len(rows), 0)
            self.assertTrue(any("Tổng dư nợ" in r["ten"] for r in rows))
        finally:
            if os.path.exists(fp):
                os.unlink(fp)

    def test_db_lookup_tim_thay_chinh_xac(self) -> None:
        rows = [
            {"ten": "Tổng dư nợ", "val": 500.0, "la_nqh_con": False, "cha": None},
            {"ten": "Dư nợ quá hạn", "val": 10.0, "la_nqh_con": False, "cha": None},
        ]
        val = self.hstd.db_lookup(rows, "Tổng dư nợ")
        self.assertEqual(val, 500.0)

    def test_db_lookup_tim_thay_gan_dung(self) -> None:
        rows = [
            {"ten": "Tổng dư nợ", "val": 500.0, "la_nqh_con": False, "cha": None},
        ]
        val = self.hstd.db_lookup(rows, "Tổng dư nợ ")
        self.assertEqual(val, 500.0)

    def test_db_lookup_khong_tim_thay(self) -> None:
        rows = [
            {"ten": "Tổng dư nợ", "val": 500.0, "la_nqh_con": False, "cha": None},
        ]
        val = self.hstd.db_lookup(rows, "Không tồn tại")
        self.assertEqual(val, 0.0)

    def test_db_lookup_rows_rong(self) -> None:
        val = self.hstd.db_lookup([], "Tổng dư nợ")
        self.assertEqual(val, 0.0)

    def test_db_nqh_con_tim_thay(self) -> None:
        rows = [
            {"ten": "Tổng dư nợ", "val": 500.0, "la_nqh_con": False, "cha": None},
            {"ten": "  NQH: Tổng dư nợ", "val": 3.0, "la_nqh_con": True, "cha": "Tổng dư nợ"},
        ]
        val = self.hstd.db_nqh_con(rows, "Tổng dư nợ")
        self.assertEqual(val, 3.0)

    def test_db_nqh_con_khong_tim_thay(self) -> None:
        rows = [
            {"ten": "Tổng dư nợ", "val": 500.0, "la_nqh_con": False, "cha": None},
        ]
        val = self.hstd.db_nqh_con(rows, "Tổng dư nợ")
        self.assertEqual(val, 0.0)

    def test_db_nqh_con_rows_rong(self) -> None:
        val = self.hstd.db_nqh_con([], "Tổng dư nợ")
        self.assertEqual(val, 0.0)


class TestKhongHoatDong(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import hstd
        cls.hstd = hstd

    def _df_co_ngay(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Số khế ước": ["KU001", "KU002", "KU003"],
            "Mã chương trình": [1, 2, 3],
            "Dư nợ TH": [10_000_000, 5_000_000, 0],
            "Dư nợ quá hạn": [0, 0, 0],
            "Dư nợ khoanh": [0, 0, 0],
            "Ngày số liệu": pd.to_datetime(["2026-05-08", "2026-05-08", "2026-05-08"]),
            "Ngày giao dịch gần nhất": pd.to_datetime([
                "2025-01-01", "2026-04-01", "2026-05-01"
            ]),
            "Ngày vay": pd.to_datetime(["2025-01-01", "2026-04-01", "2026-05-01"]),
            "Lãi tồn": [1_000_000, 0, 0],
            "Lãi DT tháng": [100_000, 100_000, 100_000],
        })

    def _df_khong_ngay(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Số khế ước": ["KU001", "KU002"],
            "Mã chương trình": [1, 3],
            "Dư nợ TH": [10_000_000, 5_000_000],
            "Dư nợ quá hạn": [0, 0],
            "Dư nợ khoanh": [0, 0],
            "Lãi tồn": [5_000_000, 0],
            "Lãi DT tháng": [100_000, 100_000],
        })

    def test_danh_dau_khong_hd_co_ngay(self) -> None:
        df = self._df_co_ngay()
        result = self.hstd.danh_dau_khong_hd(df)
        self.assertIn("is_3m_inactive", result.columns)
        self.assertIn("so_thang_khong_hd", result.columns)
        self.assertTrue(result.loc[0, "is_3m_inactive"])
        self.assertFalse(result.loc[1, "is_3m_inactive"])
        self.assertFalse(result.loc[2, "is_3m_inactive"])

    def test_danh_dau_khong_hd_loai_tru_du_no_0(self) -> None:
        df = self._df_co_ngay()
        df.loc[2, "Dư nợ TH"] = 0
        df.loc[2, "Dư nợ quá hạn"] = 0
        result = self.hstd.danh_dau_khong_hd(df)
        self.assertFalse(result.loc[2, "is_3m_inactive"])

    def test_danh_dau_khong_hd_loai_tru_khoanh(self) -> None:
        df = self._df_co_ngay()
        df.loc[0, "Dư nợ khoanh"] = 5_000_000
        result = self.hstd.danh_dau_khong_hd(df)
        self.assertFalse(result.loc[0, "is_3m_inactive"])

    def test_danh_dau_khong_hd_loai_tru_hssv(self) -> None:
        df = self._df_co_ngay()
        result = self.hstd.danh_dau_khong_hd(df)
        self.assertFalse(result.loc[1, "is_3m_inactive"])

    def test_danh_dau_khong_hd_khong_co_ngay(self) -> None:
        df = self._df_khong_ngay()
        result = self.hstd.danh_dau_khong_hd(df)
        self.assertIn("is_3m_inactive", result.columns)
        self.assertTrue(result.loc[0, "is_3m_inactive"])
        self.assertFalse(result.loc[1, "is_3m_inactive"])

    def test_danh_dau_khong_hd_thieu_cot_lai(self) -> None:
        df = pd.DataFrame({"Số khế ước": ["KU001"]})
        result = self.hstd.danh_dau_khong_hd(df)
        self.assertIn("is_3m_inactive", result.columns)
        self.assertFalse(result.loc[0, "is_3m_inactive"])

    def test_danh_dau_khong_hd_df_rong(self) -> None:
        df = pd.DataFrame()
        result = self.hstd.danh_dau_khong_hd(df)
        self.assertIn("is_3m_inactive", result.columns)

    def test_tong_hop_khong_hd_theo_dvut(self) -> None:
        df = self._df_co_ngay()
        df["Tên ĐVUT"] = ["ĐVUT A", "ĐVUT A", "ĐVUT B"]
        result = self.hstd.tong_hop_khong_hd(df, nhom_theo="Tên ĐVUT")
        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn("Tổng_món", result.columns)
        self.assertIn("Món_3m_KHĐ", result.columns)
        self.assertIn("Tỷ_lệ_KHĐ_%", result.columns)

    def test_tong_hop_khong_hd_chua_danh_dau(self) -> None:
        df = self._df_co_ngay()
        df["Tên ĐVUT"] = ["ĐVUT A"] * 3
        if "is_3m_inactive" in df.columns:
            df = df.drop(columns=["is_3m_inactive"])
        result = self.hstd.tong_hop_khong_hd(df, nhom_theo="Tên ĐVUT")
        self.assertIn("Món_3m_KHĐ", result.columns)

    def test_tong_hop_khong_hd_nhom_khong_ton_tai(self) -> None:
        df = self._df_co_ngay()
        result = self.hstd.tong_hop_khong_hd(df, nhom_theo="Cột Không Tồn Tại")
        self.assertTrue(result.empty)

    def test_ds_chi_tiet_khong_hd(self) -> None:
        df = self._df_co_ngay()
        df["Tên ĐVUT"] = ["ĐVUT A", "ĐVUT A", "ĐVUT B"]
        result = self.hstd.ds_chi_tiet_khong_hd(df, nhom_theo="Tên ĐVUT")
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)

    def test_ds_chi_tiet_khong_hd_loc_theo_nhom(self) -> None:
        df = self._df_co_ngay()
        df["Tên ĐVUT"] = ["ĐVUT A", "ĐVUT A", "ĐVUT B"]
        result = self.hstd.ds_chi_tiet_khong_hd(
            df, nhom_theo="Tên ĐVUT", gia_tri_nhom="ĐVUT A"
        )
        self.assertGreater(len(result), 0)
        self.assertTrue(all(result["Tên ĐVUT"] == "ĐVUT A"))


class TestCanhBaoMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import hstd
        cls.hstd = hstd

    def test_canh_bao_migration_phat_hien_amber(self) -> None:
        df = pd.DataFrame({
            "Số khế ước": ["KU001", "KU002"],
            "Phân loại": ["E", "E"],
            "Dư nợ TH": [10_000_000, 10_000_000],
            "Dư nợ quá hạn": [0, 0],
            "Dư nợ khoanh": [0, 0],
            "Mã chương trình": [1, 1],
            "Lãi tồn": [300_000, 50_000],
            "Lãi DT tháng": [100_000, 100_000],
            "Ngày số liệu": pd.to_datetime(["2026-05-08", "2026-05-08"]),
            "Ngày giao dịch gần nhất": pd.to_datetime(["2026-01-01", "2026-04-01"]),
            "Ngày vay": pd.to_datetime(["2026-01-01", "2026-04-01"]),
        })
        result = self.hstd.canh_bao_migration(df)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn("so_thang_ton_uoc", result.columns)
        self.assertIn("muc_canh_bao", result.columns)

    def test_canh_bao_migration_khong_co_phan_loai(self) -> None:
        df = pd.DataFrame({
            "Số khế ước": ["KU001"],
            "Dư nợ TH": [10_000_000],
            "Dư nợ quá hạn": [0],
            "Dư nợ khoanh": [0],
            "Mã chương trình": [1],
            "Lãi tồn": [300_000],
            "Lãi DT tháng": [100_000],
            "Ngày số liệu": pd.to_datetime(["2026-05-08"]),
            "Ngày giao dịch gần nhất": pd.to_datetime(["2026-01-01"]),
            "Ngày vay": pd.to_datetime(["2026-01-01"]),
        })
        result = self.hstd.canh_bao_migration(df)
        self.assertIsInstance(result, pd.DataFrame)


if __name__ == "__main__":
    unittest.main()
