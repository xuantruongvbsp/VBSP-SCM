"""Unit tests cho services/no_khoanh_service.py — Lọc & thống kê nợ khoanh."""
from __future__ import annotations

import pandas as pd
import pytest

from config import COT_DU_NO_KHOANH, COT_SO_KU, COT_TEN_PGD
from services.no_khoanh_service import loc_khoanh, bang_theo_nhom


class TestLocKhoanh:
    def test_df_trong(self):
        df = loc_khoanh(pd.DataFrame())
        assert df.empty

    def test_khong_co_cot_khoanh(self):
        df = loc_khoanh(pd.DataFrame({COT_SO_KU: ["KU1"]}))
        assert df.empty

    def test_loc_dung_mon_khoanh(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU2", "KU3"],
            COT_DU_NO_KHOANH: [100, 0, 50],
        })
        ket_qua = loc_khoanh(df)
        assert len(ket_qua) == 2
        assert set(ket_qua[COT_SO_KU]) == {"KU1", "KU3"}

    def test_du_no_khoanh_am_khong_loc(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_DU_NO_KHOANH: [-100],
        })
        ket_qua = loc_khoanh(df)
        assert ket_qua.empty

    def test_du_no_khoanh_str_duoc_ep_so(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU2"],
            COT_DU_NO_KHOANH: ["500", "0"],
        })
        ket_qua = loc_khoanh(df)
        assert len(ket_qua) == 1
        assert ket_qua.iloc[0][COT_SO_KU] == "KU1"


class TestBangTheoNhom:
    def test_df_trong(self):
        df = bang_theo_nhom(pd.DataFrame(), COT_TEN_PGD)
        assert df.empty

    def test_thieu_cot_nhom(self):
        df = bang_theo_nhom(pd.DataFrame({COT_SO_KU: ["KU1"]}), "missing_col")
        assert df.empty

    def test_bang_theo_pgd(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU2", "KU3"],
            COT_DU_NO_KHOANH: [100, 200, 100],
            COT_TEN_PGD: ["PGD A", "PGD A", "PGD B"],
        })
        df_out = bang_theo_nhom(df, COT_TEN_PGD)
        assert len(df_out) == 2
        assert df_out.iloc[0][COT_TEN_PGD] == "PGD A"
        assert "Số món" in df_out.columns
        assert "Tỷ trọng%" in df_out.columns

    def test_tong_0_khong_loi(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_DU_NO_KHOANH: [0],
            COT_TEN_PGD: ["PGD A"],
        })
        df_out = bang_theo_nhom(df, COT_TEN_PGD)
        assert len(df_out) == 1
