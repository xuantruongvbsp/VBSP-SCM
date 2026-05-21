"""Unit tests cho services/kiem_soat_service.py — Kiểm soát Chi nhánh."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_MA_CHUONG_TRINH,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGAY_DH_HD,
    COT_NGUON_VON,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TEN_THON,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_THOI_HAN,
    COT_TINH_TRANG,
    COT_TONG_DU_NO,
)
from services.kiem_soat_service import (
    _tinh_ngaygh_dp,
    _fmt_so_cell,
    _ks_html_metric_card,
    _tong_hop_vp_theo_pgd,
    _tong_hop_ghv_theo_pgd,
)


class TestTinhNgayGhDp:
    def test_thieu_ngay_dh(self):
        row = pd.Series({COT_MA_CHUONG_TRINH: "01", COT_THOI_HAN: 12})
        assert pd.isna(_tinh_ngaygh_dp(row))

    def test_ct_17_30_thang(self):
        row = pd.Series({
            COT_MA_CHUONG_TRINH: "17",
            "Ngày ĐH theo hợp đồng": "01/01/2024",
        })
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        assert kq.year == 2026 and kq.month == 7

    def test_thoi_han_ngan_toi_da_12_thang(self):
        row = pd.Series({
            COT_MA_CHUONG_TRINH: "01",
            "Ngày ĐH theo hợp đồng": "01/01/2024",
            COT_THOI_HAN: 6,
        })
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        assert kq.year == 2025 and kq.month == 1

    def test_thoi_han_dai_nua_thoi_han(self):
        row = pd.Series({
            COT_MA_CHUONG_TRINH: "01",
            "Ngày ĐH theo hợp đồng": "01/01/2024",
            COT_THOI_HAN: 36,
        })
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        assert kq.year == 2025 and kq.month == 7

    def test_thieu_thoi_han(self):
        row = pd.Series({
            COT_MA_CHUONG_TRINH: "01",
            "Ngày ĐH theo hợp đồng": "01/01/2024",
        })
        assert pd.isna(_tinh_ngaygh_dp(row))

    def test_ct_02_co_ra_truong_va_gn1(self):
        row = pd.Series({
            COT_MA_CHUONG_TRINH: "02",
            "Ngày ĐH theo hợp đồng": "01/01/2024",
            "Ngày ra trường": "01/01/2026",
            "Ngày GN đầu tiên": "01/01/2022",
        })
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        assert kq.year == 2026 and kq.month == 1

    def test_ct_02_thieu_ra_truong(self):
        row = pd.Series({
            COT_MA_CHUONG_TRINH: "02",
            "Ngày ĐH theo hợp đồng": "01/01/2024",
            "Ngày GN đầu tiên": "01/01/2022",
        })
        assert pd.isna(_tinh_ngaygh_dp(row))

    def test_qd29_ho_ngheo(self):
        row = pd.Series({
            COT_MA_CHUONG_TRINH: "01",
            "Ngày ĐH theo hợp đồng": "01/01/2024",
            COT_THOI_HAN: 24,
            "Mã Quyết định": "29/QĐ-TTg",
            "Tên ĐTTH": "Hộ nghèo",
        })
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        assert kq.year == 2026 and kq.month == 7

    def test_qd29_ho_moi_thoat_ngheo(self):
        row = pd.Series({
            COT_MA_CHUONG_TRINH: "01",
            "Ngày ĐH theo hợp đồng": "01/01/2024",
            "Tên ĐTTH": "Hộ mới thoát nghèo",
            "Mã Quyết định": "29/QĐ-TTg",
            COT_THOI_HAN: 24,
        })
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        assert kq == pd.Timestamp("2024-01-01")


class TestFmtSoCell:
    def test_so_nguyen(self):
        assert _fmt_so_cell(1234.0) == "1.234"

    def test_nan(self):
        assert _fmt_so_cell(float("nan")) == "—"

    def test_None(self):
        assert _fmt_so_cell(None) == "—"

    def test_khong(self):
        assert _fmt_so_cell(0) == "0"


class TestKsHtmlMetricCard:
    def test_basic(self):
        html = _ks_html_metric_card(
            title="Tổng dư nợ",
            value="1.234 tỷ",
            subtitle="so với kỳ trước",
            bg="#fff",
            border="#4caf50",
            value_color="#333",
        )
        assert "Tổng dư nợ" in html
        assert "1.234 tỷ" in html
        assert "so với kỳ trước" in html
        assert "background" in html


class TestTongHopVpTheoPgd:
    def test_df_trong(self):
        df = _tong_hop_vp_theo_pgd(pd.DataFrame())
        assert df.empty

    def test_thieu_cot_pgd(self):
        df_vp = pd.DataFrame({"Số_thành_viên": [3, 4], "Tổng_dư_nợ": [100, 200]})
        df = _tong_hop_vp_theo_pgd(df_vp)
        assert df.empty

    def test_1_pgd_co_to(self):
        df_vp = pd.DataFrame({
            COT_TEN_PGD: ["PGD A", "PGD A"],
            COT_TEN_TO: ["Tổ 1", "Tổ 2"],
            "Số_thành_viên": [3, 70],
            "Tổng_dư_nợ": [100, 500],
        })
        df = _tong_hop_vp_theo_pgd(df_vp)
        assert len(df) == 1
        assert df.iloc[0][COT_TEN_PGD] == "PGD A"
        assert df.iloc[0]["Tổ_thiếu_TV"] == 1
        assert df.iloc[0]["Tổ_vượt_TV"] == 1


class TestTongHopGhvTheoPgd:
    def test_df_trong(self):
        df = _tong_hop_ghv_theo_pgd(pd.DataFrame())
        assert df.empty

    def test_thieu_cot(self):
        df_gv = pd.DataFrame({"A": [1]})
        df = _tong_hop_ghv_theo_pgd(df_gv)
        assert df.empty

    def test_1_pgd(self):
        df_gv = pd.DataFrame({
            COT_TEN_PGD: ["PGD A", "PGD A"],
            "Vượt (tháng)": [3.0, 1.5],
            COT_DU_NO_TH: [100, 200],
        })
        df = _tong_hop_ghv_theo_pgd(df_gv)
        assert len(df) == 1
        assert df.iloc[0]["Số_món"] == 2
        assert df.iloc[0]["Vượt_max"] == 3.0
