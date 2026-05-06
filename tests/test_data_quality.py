import unittest

import pandas as pd

from services.data_quality import chuan_hoa_ma_don_vi, kiem_tra_chat_luong


class TestDataQuality(unittest.TestCase):
    def test_chuan_hoa_pgd_tu_ma(self) -> None:
        df = pd.DataFrame(
            {
                "Mã PGD": ["004602"],
                "Số khế ước": ["KU001"],
                "Tên xã": ["Xã Long Thành"],
            }
        )
        out = chuan_hoa_ma_don_vi(df)
        self.assertIn("Tên PGD", out.columns)
        self.assertEqual(out.loc[0, "Tên PGD"], "PGD Long Thành")

    def test_kiem_tra_chat_luong_hstd(self) -> None:
        df = pd.DataFrame(
            {
                "Số khế ước": ["KU001", "KU001"],
                "Tên PGD": ["PGD Long Thành", "PGD Long Thành"],
                "Tên xã": ["Xã Long Thành", "Xã Long Thành"],
                "Nguồn vốn": [1, 3],
                "Dư nợ trong hạn": ["1000", "2000"],
                "Dư nợ quá hạn": ["0", "100"],
                "Tổng dư nợ": ["1000", "2100"],
            }
        )
        result = kiem_tra_chat_luong(df, "hstd")
        self.assertGreaterEqual(result.report["so_loi"], 1)
        self.assertIn("Cột 'Số khế ước' có 1 dòng trùng.", result.errors)

    def test_kiem_tra_chat_luong_bat_loi_null_bat_buoc(self) -> None:
        df = pd.DataFrame(
            {
                "Số khế ước": ["KU001"],
                "Tên PGD": ["PGD Long Thành"],
                "Tên xã": [None],
                "Nguồn vốn": [1],
                "Dư nợ trong hạn": ["1000"],
                "Dư nợ quá hạn": ["0"],
                "Tổng dư nợ": ["1000"],
            }
        )
        result = kiem_tra_chat_luong(df, "hstd")
        self.assertIn("Các cột bắt buộc có 1 ô trống.", result.errors)


if __name__ == "__main__":
    unittest.main()
