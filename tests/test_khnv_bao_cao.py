"""Test services/khnv_bao_cao_service.py — tổng hợp số liệu tháng."""

import pandas as pd
import pytest

from services.khnv_bao_cao_service import tong_hop_so_lieu_thang
from config import (
    COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH,
    COT_DU_NO_KHOANH, COT_TEN_KH, COT_TEN_CT, COT_NGUON_VON,
    COT_DVUT, COT_GIAI_NGAN_TRONG_THANG,
)


def _df_mau():
    return pd.DataFrame({
        COT_TEN_PGD: ["PGD Long Thành", "PGD Trảng Bom"],
        COT_TONG_DU_NO: [50000000, 30000000],
        COT_DU_NO_TH: [49000000, 29500000],
        COT_DU_NO_QH: [1000000, 500000],
        COT_DU_NO_KHOANH: [0, 0],
        COT_TEN_KH: ["Nguyễn Văn A", "Trần Thị B"],
        COT_TEN_CT: ["NN giải quyết việc làm", "HSSV"],
        COT_NGUON_VON: ["1", "2"],
        COT_DVUT: ["Hội ND", "Hội PN"],
        COT_GIAI_NGAN_TRONG_THANG: [5000000, 3000000],
    })


class TestTongHopSoLieuThang:
    def test_df_empty_tra_dict_rong(self):
        result = tong_hop_so_lieu_thang(pd.DataFrame())
        assert result == {}

    def test_df_none_tra_dict_rong(self):
        result = tong_hop_so_lieu_thang(None)
        assert result == {}

    def test_co_du_lieu_tra_day_du_metric(self):
        df = _df_mau()
        result = tong_hop_so_lieu_thang(df)
        assert result["tong_du_no"] == 80000000
        assert result["du_no_trong_han"] == 78500000
        assert result["du_no_qua_han"] == 1500000
        assert result["so_khach_hang"] == 2
        assert result["so_mon_vay"] == 2
        assert result["ty_le_no_qua_han"] == pytest.approx(1.875, rel=0.01)
        assert result["giai_ngan_trong_thang"] == 8000000

    def test_nguon_von_tach_duoc_tw_dp(self):
        df = _df_mau()
        result = tong_hop_so_lieu_thang(df)
        assert result["nguon_von_tw"] == 50000000
        assert result["nguon_von_dp"] == 30000000

    def test_chia_0_khong_crash(self):
        df = pd.DataFrame({
            COT_TEN_PGD: ["PGD X"],
            COT_TONG_DU_NO: [0],
            COT_DU_NO_TH: [0],
            COT_DU_NO_QH: [0],
            COT_TEN_KH: ["KH"],
            COT_TEN_CT: ["CT"],
        })
        result = tong_hop_so_lieu_thang(df)
        assert result["ty_le_no_qua_han"] == 0

    def test_thieu_cot_giai_ngan_khong_crash(self):
        df = _df_mau().drop(columns=[COT_GIAI_NGAN_TRONG_THANG])
        result = tong_hop_so_lieu_thang(df)
        assert result["giai_ngan_trong_thang"] == 0

    def test_thieu_cot_nguon_von_khong_crash(self):
        df = _df_mau().drop(columns=[COT_NGUON_VON])
        result = tong_hop_so_lieu_thang(df)
        assert result["nguon_von_tw"] == 0
        assert result["nguon_von_dp"] == 0
