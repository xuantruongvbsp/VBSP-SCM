"""Unit tests cho services/data_quality.py — Chất lượng dữ liệu."""
from __future__ import annotations

import pandas as pd
import pytest

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_GQVL_DU_NO_KHOANH,
    COT_GQVL_MA_PGD,
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_NQ11_DU_NO,
    COT_NQ11_MA_KH,
    COT_NQ11_SO_TIEN,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from services.data_quality import (
    _safe_series,
    chuan_hoa_ten_cot,
    kiem_tra_du_no_am,
    kiem_tra_so_tien_giai_ngan,
    kiem_tra_ma_don_vi_hop_le,
    chuan_hoa_ma_don_vi,
    kiem_tra_chat_luong,
    tong_hop_bao_cao_chat_luong,
    DataQualityResult,
)


class TestSafeSeries:
    def test_co_cot(self):
        df = pd.DataFrame({"A": [1, 2, 3]})
        s = _safe_series(df, "A")
        assert len(s) == 3

    def test_thieu_cot(self):
        df = pd.DataFrame({"A": [1]})
        s = _safe_series(df, "B")
        assert len(s) == 0


class TestChuanHoaTenCot:
    def test_khong_co_rename_map(self):
        df = pd.DataFrame({"A": [1]})
        df_out = chuan_hoa_ten_cot(df, "unknown_type")
        pd.testing.assert_frame_equal(df_out, df)

    def test_hstd_rename(self):
        """hstd rename_map rỗng → giữ nguyên"""
        df = pd.DataFrame({"A": [1]})
        df_out = chuan_hoa_ten_cot(df, "hstd")
        pd.testing.assert_frame_equal(df_out, df)


class TestKiemTraDuNoAm:
    def test_hstd_khong_am(self):
        df = pd.DataFrame({
            COT_DU_NO_TH: [100, 200],
            COT_DU_NO_QH: [10, 20],
            COT_TONG_DU_NO: [110, 220],
        })
        errors = kiem_tra_du_no_am(df, "hstd")
        assert len(errors) == 0

    def test_hstd_co_am(self):
        df = pd.DataFrame({
            COT_DU_NO_TH: [-100, 200],
            COT_DU_NO_QH: [10, 20],
            COT_TONG_DU_NO: [110, 220],
        })
        errors = kiem_tra_du_no_am(df, "hstd")
        assert len(errors) >= 1
        assert "ÂM" in errors[0]

    def test_nq11_co_am(self):
        df = pd.DataFrame({COT_NQ11_DU_NO: [-500]})
        errors = kiem_tra_du_no_am(df, "nq11")
        assert len(errors) >= 1

    def test_gqvl_co_am(self):
        df = pd.DataFrame({COT_GQVL_DU_NO_KHOANH: [-100]})
        errors = kiem_tra_du_no_am(df, "gqvl")
        assert len(errors) >= 1

    def test_thieu_cot_khong_crash(self):
        df = pd.DataFrame({"A": [1]})
        errors = kiem_tra_du_no_am(df, "hstd")
        assert len(errors) == 0

    def test_loai_khong_xac_dinh(self):
        df = pd.DataFrame({COT_DU_NO_TH: [-1]})
        errors = kiem_tra_du_no_am(df, "unknown")
        assert errors == []

    def test_du_no_str(self):
        df = pd.DataFrame({COT_DU_NO_TH: ["-100", "0"]})
        errors = kiem_tra_du_no_am(df, "hstd")
        assert len(errors) >= 1


class TestKiemTraSoTienGiaiNgan:
    def test_khong_phai_nq11(self):
        df = pd.DataFrame({"A": [1]})
        errors = kiem_tra_so_tien_giai_ngan(df, "hstd")
        assert errors == []

    def test_nq11_khong_vuot(self):
        df = pd.DataFrame({
            "Số tiền giải ngân": [100],
            "Số tiền duyệt": [200],
        })
        errors = kiem_tra_so_tien_giai_ngan(df, "nq11")
        assert errors == []

    def test_nq11_co_vuot(self):
        df = pd.DataFrame({
            "Số tiền giải ngân": [300],
            "Số tiền duyệt": [200],
        })
        errors = kiem_tra_so_tien_giai_ngan(df, "nq11")
        assert len(errors) >= 1
        assert "giải ngân" in errors[0].lower()

    def test_nq11_thieu_cot_khong_crash(self):
        df = pd.DataFrame({"A": [1]})
        errors = kiem_tra_so_tien_giai_ngan(df, "nq11")
        assert errors == []


class TestKiemTraMaDonViHopLe:
    def test_pgd_hop_le(self):
        df = pd.DataFrame({COT_TEN_PGD: ["Phòng giao dịch Biên Hòa"]})
        errors = kiem_tra_ma_don_vi_hop_le(df)
        assert len(errors) == 0

    def test_pgd_khong_hop_le(self):
        df = pd.DataFrame({COT_TEN_PGD: ["Đơn vị không tồn tại XYZ"]})
        errors = kiem_tra_ma_don_vi_hop_le(df)
        assert len(errors) >= 1
        assert COT_TEN_PGD in errors[0]

    def test_khong_co_cot_pgd_xa(self):
        df = pd.DataFrame({"A": [1]})
        errors = kiem_tra_ma_don_vi_hop_le(df)
        assert errors == []


class TestChuanHoaMaDonVi:
    def test_giu_nguyen_pgd_hop_le(self):
        from config import DS_PGD
        pgd = DS_PGD[0] if DS_PGD else "PGD Test"
        df = pd.DataFrame({COT_TEN_PGD: [pgd]})
        out = chuan_hoa_ma_don_vi(df)
        assert out[COT_TEN_PGD].iloc[0] == pgd

    def test_chuan_hoa_ma_ct(self):
        df = pd.DataFrame({
            COT_MA_CHUONG_TRINH: ["1.0", "2"],
            COT_TEN_CT: ["CT A", "CT B"],
        })
        out = chuan_hoa_ma_don_vi(df)
        assert out[COT_MA_CHUONG_TRINH].iloc[0] == 1

    def test_df_trong(self):
        out = chuan_hoa_ma_don_vi(pd.DataFrame())
        assert out.empty


class TestKiemTraChatLuong:
    def test_hstd_hop_le(self):
        from config import DS_PGD
        pgd = DS_PGD[0] if DS_PGD else "PGD Test"
        df = pd.DataFrame({
            COT_TEN_PGD: [pgd, pgd],
            COT_TEN_XA: ["Xã Trảng Dài", "Xã Trảng Dài"],
            COT_DU_NO_TH: [100, 200],
            COT_DU_NO_QH: [0, 10],
            COT_TONG_DU_NO: [100, 210],
            COT_NGUON_VON: [1, 2],
        })
        ket_qua = kiem_tra_chat_luong(df, "hstd")
        assert isinstance(ket_qua, DataQualityResult)
        assert "loai" in ket_qua.report

    def test_nq11(self):
        df = pd.DataFrame({
            COT_NQ11_MA_KH: ["KH1", "KH2"],
            COT_NQ11_SO_TIEN: [100, 200],
            COT_NQ11_DU_NO: [50, 100],
        })
        ket_qua = kiem_tra_chat_luong(df, "nq11")
        assert isinstance(ket_qua, DataQualityResult)

    def test_thieu_cot_bat_buoc(self):
        df = pd.DataFrame({"A": [1]})
        ket_qua = kiem_tra_chat_luong(df, "hstd")
        assert len(ket_qua.errors) > 0


class TestTongHopBaoCaoChatLuong:
    def test_danh_sach_rong(self):
        df = tong_hop_bao_cao_chat_luong([])
        assert "Loại" in df.columns
        assert df.empty

    def test_2_report(self):
        reports = [
            {"loai": "hstd", "tong_dong": 100, "so_loi": 0, "ti_le_dat_chuan": 100.0},
            {"loai": "nq11", "tong_dong": 50, "so_loi": 2, "ti_le_dat_chuan": 75.0},
        ]
        df = tong_hop_bao_cao_chat_luong(reports)
        assert len(df) == 2
        assert df.iloc[0]["Loại"] == "HSTD"
        assert df.iloc[0]["Tỷ lệ đạt chuẩn"] == "100.0%"
