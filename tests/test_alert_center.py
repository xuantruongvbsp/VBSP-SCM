"""tests/test_alert_center.py — alert_center.canh_bao_no_khoanh_sap_het_han()

Hàm này thuần DataFrame — không cần Streamlit, không cần SQLite.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from alert_center import canh_bao_no_khoanh_sap_het_han


# ── Helper ────────────────────────────────────────────────────────────────────

def _ngay(days_from_today: int) -> str:
    return (date.today() + timedelta(days=days_from_today)).strftime("%d/%m/%Y")


def _df(*ngay_het_list: str) -> pd.DataFrame:
    n = len(ngay_het_list)
    return pd.DataFrame({
        "Số khế ước":        [f"KU{i+1}" for i in range(n)],
        "Tên PGD":           ["PGD A"] * n,
        "Tên xã":            ["Xã A"] * n,
        "Tên KH":            [f"KH {i+1}" for i in range(n)],
        "Ngày hết hạn Khoanh": list(ngay_het_list),
    })


# ══════════════════════════════════════════════════════════════════════════════
# canh_bao_no_khoanh_sap_het_han()
# ══════════════════════════════════════════════════════════════════════════════

class TestCanhBaoNoKhoanh:

    # ── Guard conditions ─────────────────────────────────────────────────────

    def test_empty_df_tra_ve_zeros(self):
        result = canh_bao_no_khoanh_sap_het_han(pd.DataFrame())
        assert result == {
            "so_khan": 0, "so_canh_bao": 0,
            "chi_tiet_khan": [], "chi_tiet_canh_bao": [],
        }

    def test_thieu_cot_ngay_tra_ve_zeros(self):
        df = pd.DataFrame({"Tên KH": ["A"], "Tên PGD": ["PGD A"]})
        result = canh_bao_no_khoanh_sap_het_han(df)
        assert result["so_khan"] == 0
        assert result["so_canh_bao"] == 0

    # ── Phân loại theo con_lai ─────────────────────────────────────────────

    def test_le_30_ngay_la_khan(self):
        result = canh_bao_no_khoanh_sap_het_han(_df(_ngay(10)))
        assert result["so_khan"] == 1
        assert result["so_canh_bao"] == 0

    def test_dung_30_ngay_la_khan(self):
        result = canh_bao_no_khoanh_sap_het_han(_df(_ngay(30)))
        assert result["so_khan"] == 1

    def test_31_den_180_la_canh_bao(self):
        result = canh_bao_no_khoanh_sap_het_han(_df(_ngay(60)))
        assert result["so_khan"] == 0
        assert result["so_canh_bao"] == 1

    def test_dung_180_la_canh_bao(self):
        result = canh_bao_no_khoanh_sap_het_han(_df(_ngay(180)))
        assert result["so_canh_bao"] == 1

    def test_qua_180_bi_bo_qua(self):
        result = canh_bao_no_khoanh_sap_het_han(_df(_ngay(200)))
        assert result["so_khan"] == 0
        assert result["so_canh_bao"] == 0

    # ── Nhiều khoản, kết hợp ──────────────────────────────────────────────

    def test_hon_hop_3_truong_hop(self):
        df = _df(_ngay(10), _ngay(60), _ngay(200))
        result = canh_bao_no_khoanh_sap_het_han(df)
        assert result["so_khan"] == 1
        assert result["so_canh_bao"] == 1

    # ── Chi tiết ─────────────────────────────────────────────────────────

    def test_chi_tiet_khan_la_list_dict(self):
        result = canh_bao_no_khoanh_sap_het_han(_df(_ngay(10)))
        assert isinstance(result["chi_tiet_khan"], list)
        assert len(result["chi_tiet_khan"]) == 1
        assert isinstance(result["chi_tiet_khan"][0], dict)

    def test_chi_tiet_canh_bao_la_list_dict(self):
        result = canh_bao_no_khoanh_sap_het_han(_df(_ngay(60)))
        assert isinstance(result["chi_tiet_canh_bao"], list)
        assert len(result["chi_tiet_canh_bao"]) == 1

    # ── Ngày không hợp lệ ────────────────────────────────────────────────

    def test_ngay_khong_phan_tich_duoc_bi_bo_qua(self):
        df = pd.DataFrame({"Ngày hết hạn Khoanh": ["không phải ngày", "ABC"]})
        result = canh_bao_no_khoanh_sap_het_han(df)
        assert result["so_khan"] == 0
        assert result["so_canh_bao"] == 0
