"""Unit tests cho services/kiem_soat_service.py — _tinh_to_sai_so_tv (DuckDB)."""
from __future__ import annotations

import pandas as pd

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_MA_KH,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TEN_THON,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TINH_TRANG,
    COT_TONG_DU_NO,
)
from services.kiem_soat_service import _tinh_to_sai_so_tv, DUOI_TV, TREN_TV


class TestTinhToSaiSoTv:
    def test_df_None(self):
        df_vp, df_to = _tinh_to_sai_so_tv(None)
        assert df_vp.empty and df_to.empty

    def test_df_trong(self):
        df_vp, df_to = _tinh_to_sai_so_tv(pd.DataFrame())
        assert df_vp.empty and df_to.empty

    def test_thieu_cot_du_no(self):
        df = pd.DataFrame({"A": [1]})
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert df_vp.empty and df_to.empty

    def test_1_to_thieu_tv(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1", "Tổ 1"],
            COT_TONG_DU_NO: [100, 200],
            COT_MA_KH: ["KH1", "KH2"],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert not df_vp.empty
        assert df_vp.iloc[0]["Số_thành_viên"] == 2
        assert "Thiếu thành viên" in df_vp.iloc[0]["Mô tả"]

    def test_1_to_vuot_tv(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1"] * (TREN_TV + 5),
            COT_TONG_DU_NO: [100] * (TREN_TV + 5),
            COT_MA_KH: [f"KH{i}" for i in range(TREN_TV + 5)],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert not df_vp.empty
        assert "Vượt thành viên" in df_vp.iloc[0]["Mô tả"]

    def test_khong_vi_pham(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1"] * 10,
            COT_TONG_DU_NO: [100] * 10,
            COT_MA_KH: [f"KH{i}" for i in range(10)],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert df_vp.empty

    def test_loc_theo_tinh_trang_close(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1", "Tổ 1", "Tổ 2"],
            COT_TONG_DU_NO: [100, 0, 100],
            COT_TINH_TRANG: ["ACTIVE", "CLOSE", "ACTIVE"],
            COT_MA_KH: ["KH1", "KH2", "KH3"],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert not df_to.empty
        assert "Tổ 2" in df_to[COT_TEN_TO].values

    def test_loai_bo_vay_truc_tiep_khong_co_to(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1", "", ""],
            COT_TONG_DU_NO: [100, 200, 300],
            COT_MA_KH: ["KH1", "KH2", "KH3"],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert not df_to.empty
        assert len(df_to) == 1

    def test_co_dvut_thay_cho_to(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["", ""],
            COT_DVUT: ["HPN", "HPN"],
            COT_TONG_DU_NO: [100, 200],
            COT_MA_KH: ["KH1", "KH2"],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert not df_to.empty
        assert "HPN" in df_to[COT_DVUT].values

    def test_du_no_bang_0_bi_loai(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1", "Tổ 1"],
            COT_TONG_DU_NO: [100, 0],
            COT_MA_KH: ["KH1", "KH2"],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert len(df_to) == 1
        assert df_to.iloc[0]["Số_thành_viên"] == 1

    def test_khong_co_ma_kh_ma_co_so_ku(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1", "Tổ 1"],
            COT_TONG_DU_NO: [100, 200],
            COT_SO_KU: ["KU1", "KU2"],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert not df_to.empty

    def test_khong_co_ma_kh_khong_co_so_ku(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1"],
            COT_TONG_DU_NO: [100],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert df_vp.empty and df_to.empty

    def test_co_du_no_th_qh(self):
        df = pd.DataFrame({
            COT_TEN_TO: ["Tổ 1", "Tổ 1"],
            COT_TONG_DU_NO: [100, 200],
            COT_DU_NO_TH: [80, 150],
            COT_DU_NO_QH: [20, 50],
            COT_MA_KH: ["KH1", "KH2"],
        })
        df_vp, df_to = _tinh_to_sai_so_tv(df)
        assert "Dư_nợ_TH" in df_to.columns
        assert "Dư_nợ_QH" in df_to.columns
