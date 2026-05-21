"""Unit tests cho services/hhi_service.py — Chỉ số tập trung Herfindahl-Hirschman."""
from __future__ import annotations

import pandas as pd
import pytest

from config import COT_TONG_DU_NO
from services.hhi_service import tinh_hhi, tinh_hhi_breakdown, danh_gia_hhi


class TestTinhHhi:
    def test_df_trong_tra_ve_0(self):
        assert tinh_hhi(pd.DataFrame(), "nhom") == 0.0

    def test_dong_deu_hoan_toan(self):
        df = pd.DataFrame({"nhom": ["A", "B", "C", "D"], COT_TONG_DU_NO: [25, 25, 25, 25]})
        hhi = tinh_hhi(df, "nhom")
        assert hhi == pytest.approx(0.25)

    def test_tap_trung_hoan_toan(self):
        df = pd.DataFrame({"nhom": ["A"], COT_TONG_DU_NO: [100]})
        hhi = tinh_hhi(df, "nhom")
        assert hhi == pytest.approx(1.0)

    def test_3_nhom_khong_deu(self):
        df = pd.DataFrame({
            "nhom": ["A", "B", "C"],
            COT_TONG_DU_NO: [70, 20, 10],
        })
        hhi = tinh_hhi(df, "nhom")
        expected = 0.7**2 + 0.2**2 + 0.1**2
        assert hhi == pytest.approx(expected)

    def test_tong_bang_0(self):
        df = pd.DataFrame({"nhom": ["A", "B"], COT_TONG_DU_NO: [0.0, 0.0]})
        assert tinh_hhi(df, "nhom") == 0.0

    def test_thieu_cot_tien_tu_dong_tim(self):
        df = pd.DataFrame({"nhom": ["A", "B"], "Dư nợ": [30, 20]})
        hhi = tinh_hhi(df, "nhom")
        assert hhi == pytest.approx((0.6**2 + 0.4**2))

    def test_cot_tien_khong_ton_tai(self):
        df = pd.DataFrame({"nhom": ["A"]})
        assert tinh_hhi(df, "nhom") == 0.0

    def test_truyen_cot_tien_tuong_minh(self):
        df = pd.DataFrame({"xa": ["X", "Y"], "ty_trong": [60, 40]})
        hhi = tinh_hhi(df, "xa", cot_tien="ty_trong")
        assert hhi == pytest.approx(0.6**2 + 0.4**2)


class TestTinhHhiBreakdown:
    def test_df_trong(self):
        df = tinh_hhi_breakdown(pd.DataFrame(), "nhom")
        assert df.empty

    def test_breakdown_2_nhom(self):
        df_in = pd.DataFrame({"pgd": ["PGD A", "PGD B"], COT_TONG_DU_NO: [30, 70]})
        df = tinh_hhi_breakdown(df_in, "pgd")
        assert len(df) == 2
        assert df.iloc[0]["pgd"] == "PGD B"
        assert df.iloc[0]["ty_trong_pct"] == 70.0
        assert df.iloc[1]["pgd"] == "PGD A"
        assert df.iloc[1]["ty_trong_pct"] == 30.0
        assert "dong_gop_hhi" in df.columns

    def test_cot_khong_ton_tai(self):
        df_in = pd.DataFrame({"pgd": ["A"]})
        df = tinh_hhi_breakdown(df_in, "pgd")
        assert df.empty

    def test_tong_0(self):
        df_in = pd.DataFrame({"pgd": ["A", "B"], COT_TONG_DU_NO: [0.0, 0.0]})
        df = tinh_hhi_breakdown(df_in, "pgd")
        assert df.empty


class TestDanhGiaHhi:
    def test_da_dang_hoa_tot(self):
        muc_do, icon, mau = danh_gia_hhi(0.05)
        assert "Đa dạng" in muc_do
        assert icon == "✅"

    def test_tap_trung_vua_phai_can_duoi(self):
        muc_do, icon, mau = danh_gia_hhi(0.10)
        assert "vừa" in muc_do
        assert icon == "⚠️"

    def test_tap_trung_vua_phai_can_tren(self):
        muc_do, icon, mau = danh_gia_hhi(0.24)
        assert "vừa" in muc_do
        assert icon == "⚠️"

    def test_tap_trung_cao(self):
        muc_do, icon, mau = danh_gia_hhi(0.30)
        assert "Cảnh báo" in muc_do
        assert icon == "🚨"

    def test_tap_trung_cao_cuc_dai(self):
        muc_do, icon, mau = danh_gia_hhi(1.0)
        assert "Cảnh báo" in muc_do
        assert icon == "🚨"
