"""Unit test cho data/core.py — hàm tiện ích xử lý dữ liệu."""
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import pandas as pd


class TestCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from data import core
        cls.core = core

    def test_ts_file_ton_tai_tra_float(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(b"dummy")
            path = f.name
        try:
            ts = self.core.ts_file(path)
            self.assertIsInstance(ts, float)
            self.assertGreater(ts, 0)
        finally:
            os.unlink(path)

    def test_ts_file_khong_ton_tai_tra_0(self) -> None:
        ts = self.core.ts_file("/nonexistent/file.xlsx")
        self.assertEqual(ts, 0.0)

    def test_ts_file_thu_muc_tra_0(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ts = self.core.ts_file(d)
            self.assertEqual(ts, 0.0)

    def test_excel_to_parquet_tao_file_cache(self) -> None:
        df_expected = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fe:
            with pd.ExcelWriter(fe.name, engine="openpyxl") as writer:
                df_expected.to_excel(writer, sheet_name="Sheet1", index=False)
            excel_path = fe.name
        parquet_path = tempfile.mktemp(suffix=".parquet")
        try:
            df_result = self.core.excel_to_parquet(
                excel_path, parquet_path, sheet="Sheet1", header=0
            )
            self.assertIsInstance(df_result, pd.DataFrame)
            self.assertEqual(len(df_result), 2)
            self.assertTrue(os.path.exists(parquet_path))
        finally:
            os.unlink(excel_path)
            if os.path.exists(parquet_path):
                os.unlink(parquet_path)

    def test_excel_to_parquet_post_fn_duoc_goi(self) -> None:
        df_expected = pd.DataFrame({"A": [1, 2, 3]})
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fe:
            with pd.ExcelWriter(fe.name, engine="openpyxl") as writer:
                df_expected.to_excel(writer, sheet_name="Sheet1", index=False)
            excel_path = fe.name
        parquet_path = tempfile.mktemp(suffix=".parquet")
        def post_fn(df):
            return df[df["A"] > 1]
        try:
            df_result = self.core.excel_to_parquet(
                excel_path, parquet_path, sheet="Sheet1", header=0,
                post_fn=post_fn
            )
            self.assertEqual(len(df_result), 2)
        finally:
            os.unlink(excel_path)
            if os.path.exists(parquet_path):
                os.unlink(parquet_path)

    def test_excel_to_parquet_cache_khong_tao_lai(self) -> None:
        df_expected = pd.DataFrame({"A": [1, 2, 3]})
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fe:
            with pd.ExcelWriter(fe.name, engine="openpyxl") as writer:
                df_expected.to_excel(writer, sheet_name="Sheet1", index=False)
            excel_path = fe.name
        parquet_path = tempfile.mktemp(suffix=".parquet")
        try:
            df1 = self.core.excel_to_parquet(
                excel_path, parquet_path, sheet="Sheet1", header=0
            )
            df2 = self.core.excel_to_parquet(
                excel_path, parquet_path, sheet="Sheet1", header=0
            )
            self.assertTrue(df1.equals(df2))
        finally:
            os.unlink(excel_path)
            if os.path.exists(parquet_path):
                os.unlink(parquet_path)

    def test_excel_to_parquet_excel_khong_ton_tai(self) -> None:
        parquet_path = tempfile.mktemp(suffix=".parquet")
        with self.assertRaises(Exception):
            self.core.excel_to_parquet(
                "/nonexistent/file.xlsx", parquet_path, sheet="Sheet1", header=0
            )

    def test_tong_hop_du_no_pgd_parquet_khong_ton_tai_tra_df_rong(self) -> None:
        df = self.core.tong_hop_du_no_pgd("/nonexistent/file.parquet")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    def test_dem_no_qua_han_pgd_parquet_khong_ton_tai_tra_df_rong(self) -> None:
        df = self.core.dem_no_qua_han_pgd("/nonexistent/file.parquet")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    def test_duckdb_query_tra_df(self) -> None:
        df = self.core._duckdb_query("SELECT 1 AS a, 'hello' AS b")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df["a"].iloc[0], 1)
        self.assertEqual(df["b"].iloc[0], "hello")

    def test_duckdb_query_multi_row(self) -> None:
        df = self.core._duckdb_query(
            "SELECT * FROM (VALUES (1,'a'), (2,'b')) AS t(x, y)"
        )
        self.assertEqual(len(df), 2)

    def test_duckdb_query_sql_injection_an_toan(self) -> None:
        df = self.core._duckdb_query(
            "SELECT 1 AS a", params=None
        )
        self.assertIsInstance(df, pd.DataFrame)


if __name__ == "__main__":
    unittest.main()
