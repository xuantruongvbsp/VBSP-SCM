"""Unit tests cho services/cdtotkvv_service.py — Chấm điểm Tổ TK&VV."""
from __future__ import annotations

import pandas as pd

from services.cdtotkvv_service import (
    loc_df,
    cdtotkvv_ten_sheet_excel,
    fmt_xuat_to_khong_dat_vn,
)


class TestLocDf:
    def test_df_None(self):
        df = loc_df(None, "cn", "")
        assert df is None

    def test_df_trong(self):
        df = loc_df(pd.DataFrame(), "cn", "")
        assert df.empty

    def test_mode_cn_tra_ve_toan_bo(self):
        df_in = pd.DataFrame({"ten_dv": ["PGD A", "PGD B"]})
        df_out = loc_df(df_in, "cn", "PGD A")
        assert len(df_out) == 2

    def test_mode_pgd_loc_theo_ten(self):
        df_in = pd.DataFrame({"ten_dv": ["PGD A", "PGD B"]})
        df_out = loc_df(df_in, "pgd", "PGD B")
        assert len(df_out) == 1
        assert df_out.iloc[0]["ten_dv"] == "PGD B"

    def test_mode_pgd_khong_khop(self):
        df_in = pd.DataFrame({"ten_dv": ["PGD A"]})
        df_out = loc_df(df_in, "pgd", "PGD X")
        assert df_out.empty

    def test_mode_pgd_loc_theo_ma_khi_khong_co_ten(self):
        df_in = pd.DataFrame({"ma_dv": ["pgd_a", "pgd_b"]})
        df_out = loc_df(df_in, "pgd", "pgd_a")
        assert len(df_out) == 1

    def test_mode_pgd_khong_pgd_user(self):
        df_in = pd.DataFrame({"ten_dv": ["PGD A"]})
        df_out = loc_df(df_in, "pgd", "")
        assert len(df_out) == 1


class TestCdtotkvvTenSheetExcel:
    def test_ten_don_gian(self):
        da_dung = set()
        ten = cdtotkvv_ten_sheet_excel("PGD A - Tổ 1", da_dung)
        assert len(ten) <= 31
        assert ten in da_dung

    def test_ky_tu_cam(self):
        da_dung = set()
        ten = cdtotkvv_ten_sheet_excel("Tổ [1]: A/B\\C", da_dung)
        assert "[" not in ten
        assert ":" not in ten
        assert "/" not in ten
        assert "\\" not in ten

    def test_trung_thi_danh_so(self):
        da_dung = set()
        t1 = cdtotkvv_ten_sheet_excel("PGD A", da_dung)
        t2 = cdtotkvv_ten_sheet_excel("PGD A", da_dung)
        assert t1 != t2
        assert "_1" in t2 or t1.endswith("_")

    def test_ten_dai_cat_bot(self):
        da_dung = set()
        ten = cdtotkvv_ten_sheet_excel("A" * 40, da_dung)
        assert len(ten) <= 31

    def test_ten_toan_ky_tu_cam(self):
        da_dung = set()
        ten = cdtotkvv_ten_sheet_excel("[/:*]", da_dung)
        assert len(ten) > 0
        assert ten not in {"", "/", "\\"}


class TestFmtXuatToKhongDatVn:
    def test_co_du_no_va_diem(self):
        df_in = pd.DataFrame({
            "Dư nợ": [1234567, 0],
            "Số dư TK": [500000, 100000],
            "Điểm đạt được": [85, 90],
            "Điểm tối đa": [100, 100],
            "Tổng điểm": [85, 90],
        })
        df_out = fmt_xuat_to_khong_dat_vn(df_in)
        assert df_out["Dư nợ"].iloc[0] == "1.234.567"
        assert df_out["Điểm đạt được"].iloc[0] == "85"

    def test_cot_ko_co_van_chay(self):
        df_in = pd.DataFrame({"A": [1]})
        df_out = fmt_xuat_to_khong_dat_vn(df_in)
        assert len(df_out) == 1
