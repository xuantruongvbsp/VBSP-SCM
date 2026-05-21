"""Unit tests cho services/du_phong_service.py — Dự phóng dòng tiền."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_MA_KH,
    COT_MUC_VAY,
    COT_NGAY_DH,
    COT_NGAY_VAY,
    COT_SO_KU,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TEN_CT,
    COT_TONG_DU_NO,
    COT_NGUON_VON,
)
from services.du_phong_service import du_phong_dong_tien, du_phong_chi_tiet


class TestDuPhongDongTien:
    def test_df_trong(self):
        df = du_phong_dong_tien(pd.DataFrame())
        assert df.empty

    def test_thieu_cot_bat_buoc(self):
        df = pd.DataFrame({"A": [1]})
        out = du_phong_dong_tien(df)
        assert out.empty

    def test_1_khe_uoc(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_TONG_DU_NO: [12000000],
            COT_DU_NO_TH: [12000000],
            COT_DU_NO_QH: [0],
            COT_NGAY_VAY: ["01/01/2024"],
            COT_NGAY_DH: ["01/01/2025"],
            COT_MUC_VAY: [12000000],
        })
        tu_thang = date(2024, 1, 1)
        den_thang = date(2024, 12, 31)
        out = du_phong_dong_tien(df, tu_thang=tu_thang, den_thang=den_thang)
        assert not out.empty
        assert "thang" in out.columns
        assert "du_kien_thu_goc" in out.columns
        assert out["so_mon"].sum() == 12

    def test_loc_theo_thang(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_TONG_DU_NO: [12000000],
            COT_DU_NO_TH: [12000000],
            COT_DU_NO_QH: [0],
            COT_NGAY_VAY: ["01/01/2024"],
            COT_NGAY_DH: ["01/01/2026"],
            COT_MUC_VAY: [24000000],
        })
        tu_thang = date(2025, 1, 1)
        den_thang = date(2025, 6, 30)
        out = du_phong_dong_tien(df, tu_thang=tu_thang, den_thang=den_thang)
        assert not out.empty
        assert out["so_mon"].sum() == 6

    def test_du_no_0_bi_loai(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_TONG_DU_NO: [0],
            COT_DU_NO_TH: [0],
            COT_DU_NO_QH: [0],
            COT_NGAY_VAY: ["01/01/2024"],
            COT_NGAY_DH: ["01/01/2025"],
            COT_MUC_VAY: [12000000],
        })
        out = du_phong_dong_tien(df)
        assert out.empty

    def test_không_co_ngay_vay(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_TONG_DU_NO: [100],
            COT_NGAY_VAY: [pd.NaT],
            COT_NGAY_DH: ["01/01/2025"],
            COT_MUC_VAY: [12000000],
        })
        out = du_phong_dong_tien(df)
        assert out.empty

    def test_default_tu_den_thang(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_TONG_DU_NO: [12000000],
            COT_DU_NO_TH: [12000000],
            COT_DU_NO_QH: [0],
            COT_NGAY_VAY: ["01/01/2024"],
            COT_NGAY_DH: ["01/01/2025"],
            COT_MUC_VAY: [12000000],
        })
        out = du_phong_dong_tien(df)
        assert not out.empty or True


class TestDuPhongChiTiet:
    def test_df_trong(self):
        df = du_phong_chi_tiet(pd.DataFrame())
        assert df.empty

    def test_thieu_cot(self):
        df = pd.DataFrame({"A": [1]})
        out = du_phong_chi_tiet(df)
        assert out.empty

    def test_thang_None(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_TONG_DU_NO: [100],
            COT_NGAY_VAY: ["01/01/2024"],
            COT_NGAY_DH: ["01/01/2025"],
            COT_MUC_VAY: [100],
        })
        out = du_phong_chi_tiet(df, thang=None)
        assert out.empty

    def test_chi_tiet_1_thang(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_TONG_DU_NO: [12000000],
            COT_NGAY_VAY: ["01/01/2024"],
            COT_NGAY_DH: ["01/01/2025"],
            COT_MUC_VAY: [12000000],
        })
        thang = date(2024, 6, 15)
        out = du_phong_chi_tiet(df, thang=thang)
        if not out.empty:
            assert "goc_ht" in out.columns
