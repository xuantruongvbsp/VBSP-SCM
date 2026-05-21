"""Unit tests cho services/so_sanh_ky_service.py — So sánh kỳ, tổng hợp, HHI."""
from __future__ import annotations

import pandas as pd
import pytest

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_MA_KH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from services.so_sanh_ky_service import (
    agg_mot_pgd,
    agg_theo_pgd,
    agg_theo_dvut,
    group_bien_dong,
    delta_str,
    tl_nqh,
    fmt_pct_vn,
    phan_loai_khach_hang,
    top_movers,
    phan_tich_hhi_pgd,
)


class TestAggMotPgd:
    def test_df_None(self):
        d = agg_mot_pgd(None)
        assert d["tong_du_no"] == 0
        assert d["so_ho"] == 0

    def test_df_trong(self):
        d = agg_mot_pgd(pd.DataFrame())
        assert d["tong_du_no"] == 0

    def test_agg_du_no(self):
        df = pd.DataFrame({
            COT_TONG_DU_NO: [100, 200, 300],
            COT_DU_NO_TH:   [80,  150, 250],
            COT_DU_NO_QH:   [20,  50,  50],
            COT_MA_KH:      ["KH1", "KH2", "KH1"],
            COT_SO_KU:      ["KU1", "KU2", "KU3"],
        })
        d = agg_mot_pgd(df)
        assert d["tong_du_no"] == 600
        assert d["du_no_th"] == 480
        assert d["du_no_qh"] == 120
        assert d["so_ho"] == 2
        assert d["so_ku"] == 3

    def test_agg_co_khoanh(self):
        df = pd.DataFrame({
            COT_TONG_DU_NO:   [500],
            COT_DU_NO_TH:     [400],
            COT_DU_NO_QH:     [80],
            COT_DU_NO_KHOANH: [20],
            COT_MA_KH:        ["KH1"],
            COT_SO_KU:        ["KU1"],
        })
        d = agg_mot_pgd(df)
        assert d["du_no_khoanh"] == 20

    def test_missing_cot_khong_crash(self):
        df = pd.DataFrame({"A": [1]})
        d = agg_mot_pgd(df)
        assert d["tong_du_no"] == 0


class TestAggTheoPgd:
    def test_df_trong(self):
        df = agg_theo_pgd(pd.DataFrame())
        assert df.empty

    def test_thieu_cot_pgd(self):
        df = pd.DataFrame({COT_TONG_DU_NO: [100]})
        assert agg_theo_pgd(df).empty

    def test_2_pgd_co_tong(self):
        df = pd.DataFrame({
            COT_TEN_PGD:    ["PGD A", "PGD A", "PGD B"],
            COT_TONG_DU_NO: [100,     200,     50],
            COT_DU_NO_TH:   [80,      150,     40],
            COT_DU_NO_QH:   [20,      50,      10],
            COT_MA_KH:      ["KH1",   "KH2",   "KH3"],
            COT_SO_KU:      ["KU1",   "KU2",   "KU3"],
        })
        df_out = agg_theo_pgd(df)
        assert len(df_out) == 3  # 2 PGD + 1 tổng
        tong_row = df_out[df_out[COT_TEN_PGD].str.contains("Tổng", na=False)].iloc[0]
        assert tong_row["tong_du_no"] == 350

    def test_df_chua_khoanh(self):
        df = pd.DataFrame({
            COT_TEN_PGD:      ["PGD A"],
            COT_TONG_DU_NO:    [100],
            COT_DU_NO_TH:      [80],
            COT_DU_NO_QH:      [20],
            COT_DU_NO_KHOANH:  [5],
            COT_MA_KH:         ["KH1"],
            COT_SO_KU:         ["KU1"],
        })
        df_out = agg_theo_pgd(df)
        assert len(df_out) == 2
        assert "du_no_khoanh" in df_out.columns


class TestAggTheoDvut:
    def test_df_trong(self):
        assert agg_theo_dvut(pd.DataFrame()).empty

    def test_thieu_cot_dvut(self):
        assert agg_theo_dvut(pd.DataFrame({COT_TONG_DU_NO: [100]})).empty

    def test_theo_dvut_co_tong(self):
        df = pd.DataFrame({
            COT_DVUT:       ["HND", "HPN", "HND"],
            COT_TONG_DU_NO: [100,   200,   50],
            COT_DU_NO_QH:   [10,    20,    5],
            COT_MA_KH:      ["KH1", "KH2", "KH3"],
            COT_SO_KU:      ["KU1", "KU2", "KU3"],
        })
        df_out = agg_theo_dvut(df)
        assert len(df_out) == 3  # 2 DVUT + 1 tổng
        assert "tong_du_no" in df_out.columns


class TestGroupBienDong:
    def test_thieu_cot_dim(self):
        df = group_bien_dong(pd.DataFrame(), "missing")
        assert df.empty

    def test_group_theo_pgd(self):
        df = pd.DataFrame({
            COT_TEN_PGD:    ["PGD A", "PGD A", "PGD B"],
            COT_TONG_DU_NO: [100,     200,     300],
            COT_DU_NO_QH:   [10,      20,      15],
            COT_SO_KU:      ["KU1",   "KU2",   "KU3"],
        })
        df_out = group_bien_dong(df, COT_TEN_PGD)
        assert len(df_out) == 2
        assert "nqh_pct" in df_out.columns


class TestDeltaStr:
    def test_tang(self):
        assert delta_str(150_000_000_000, 100_000_000_000) == "+50.000"

    def test_giam(self):
        assert delta_str(80_000_000_000, 100_000_000_000) == "-20.000"

    def test_so(self):
        s = delta_str(10, 5, unit="so")
        assert s == "+5"


class TestTlNqh:
    def test_0(self):
        assert tl_nqh(0, 100) == 0.0

    def test_10_pct(self):
        assert tl_nqh(10, 200) == 5.0

    def test_du_no_0(self):
        assert tl_nqh(10, 0) == 0.0


class TestFmtPctVn:
    def test_5(self):
        assert fmt_pct_vn(5.25) == "5,25%"

    def test_int(self):
        assert fmt_pct_vn(100) == "100,00%"


class TestPhanLoaiKhachHang:
    def test_df_trong(self):
        assert phan_loai_khach_hang(pd.DataFrame(), pd.DataFrame()).empty

    def test_thieu_cot_ma_kh(self):
        df = pd.DataFrame({"x": [1]})
        assert phan_loai_khach_hang(df, pd.DataFrame({COT_MA_KH: ["KH1"]})).empty

    def test_3_loai(self):
        df_truoc = pd.DataFrame({COT_MA_KH: ["KH1", "KH2", "KH3"]})
        df_sau   = pd.DataFrame({COT_MA_KH: ["KH1", "KH4", "KH5"]})
        df_out = phan_loai_khach_hang(df_truoc, df_sau)
        assert len(df_out) == 3
        assert df_out.iloc[0]["Loại"] == "Tồn tại trước đó"


class TestTopMovers:
    def test_df_trong(self):
        assert top_movers(pd.DataFrame(), pd.DataFrame()).empty

    def test_thieu_cot_nhom(self):
        df = pd.DataFrame({COT_TONG_DU_NO: [100]})
        assert top_movers(df, df, nhom_by="missing").empty

    def test_2_pgd_2_movers(self):
        df_ht = pd.DataFrame({
            COT_TEN_PGD:    ["PGD A", "PGD B"],
            COT_TONG_DU_NO: [150,     100],
            COT_DU_NO_QH:   [15,      10],
        })
        df_bl = pd.DataFrame({
            COT_TEN_PGD:    ["PGD A", "PGD B"],
            COT_TONG_DU_NO: [100,     100],
            COT_DU_NO_QH:   [10,      10],
        })
        df_out = top_movers(df_ht, df_bl, n=2)
        assert len(df_out) == 2
        assert "DN mốc" in df_out.columns
        assert "Δ DN" in df_out.columns


class TestPhanTichHhiPgd:
    def test_df_trong(self):
        hhi, bd, muc_do, icon, mau = phan_tich_hhi_pgd(pd.DataFrame())
        assert hhi == 0.0

    def test_thieu_cot(self):
        hhi, bd, muc_do, icon, mau = phan_tich_hhi_pgd(pd.DataFrame({"A": [1]}))
        assert hhi == 0.0

    def test_hoat_dong_binh_thuong(self):
        df = pd.DataFrame({
            COT_TEN_PGD:     ["PGD A", "PGD B", "PGD C", "PGD D", "PGD E"],
            COT_TONG_DU_NO:  [100,     200,     100,     300,     300],
        })
        hhi, bd, muc_do, icon, mau = phan_tich_hhi_pgd(df)
        assert hhi > 0.2
        assert len(bd) == 5
        assert icon in ("⚠️", "✅")
