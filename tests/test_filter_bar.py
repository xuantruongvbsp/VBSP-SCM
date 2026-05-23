"""tests/test_filter_bar.py — components/filter_bar.apply_filters()

apply_filters() là hàm thuần pandas — không có st.* calls.
"""
from __future__ import annotations

import pandas as pd
import pytest

from components.filter_bar import apply_filters


# ── Fixture ──────────────────────────────────────────────────────────────────

def _df() -> pd.DataFrame:
    return pd.DataFrame({
        "Tên PGD":    ["PGD Long Thành", "PGD Nhơn Trạch", "PGD Long Thành"],
        "Tổng dư nợ": [1_000_000,         2_000_000,         500_000],
        "Trạng thái": ["active",           "inactive",        "active"],
    })


# ══════════════════════════════════════════════════════════════════════════════
# apply_filters()
# ══════════════════════════════════════════════════════════════════════════════

class TestApplyFilters:

    # ── Guard conditions ─────────────────────────────────────────────────────

    def test_filter_rong_tra_ve_nguyen_vien(self):
        result = apply_filters(_df(), {})
        assert len(result) == 3

    def test_empty_df_tra_ve_empty(self):
        result = apply_filters(pd.DataFrame(), {"Tên PGD": "A"})
        assert result.empty

    def test_none_value_bi_bo_qua(self):
        result = apply_filters(_df(), {"Tên PGD": None})
        assert len(result) == 3

    def test_col_khong_ton_tai_bi_bo_qua(self):
        result = apply_filters(_df(), {"Cot Khong Co": "x"})
        assert len(result) == 3

    # ── Scalar filter (str.contains, case-insensitive) ───────────────────────

    def test_scalar_loc_theo_chuoi_con(self):
        result = apply_filters(_df(), {"Tên PGD": "Long Thành"})
        assert len(result) == 2
        assert all("Long Thành" in v for v in result["Tên PGD"])

    def test_scalar_case_insensitive(self):
        # "INACTIVE" chỉ khớp "inactive", không khớp "active" (không có "inactive" trong "active")
        result = apply_filters(_df(), {"Trạng thái": "INACTIVE"})
        assert len(result) == 1
        assert result["Trạng thái"].iloc[0] == "inactive"

    def test_scalar_partial_match(self):
        result = apply_filters(_df(), {"Tên PGD": "Nhơn"})
        assert len(result) == 1

    # ── List filter (isin) ───────────────────────────────────────────────────

    def test_list_isin(self):
        result = apply_filters(_df(), {"Tên PGD": ["PGD Nhơn Trạch"]})
        assert len(result) == 1
        assert result["Tên PGD"].iloc[0] == "PGD Nhơn Trạch"

    def test_list_nhieu_gia_tri(self):
        result = apply_filters(_df(), {"Tên PGD": ["PGD Long Thành", "PGD Nhơn Trạch"]})
        assert len(result) == 3

    def test_list_rong_khong_loc(self):
        result = apply_filters(_df(), {"Tên PGD": []})
        assert len(result) == 3

    # ── Range filter (tuple) ─────────────────────────────────────────────────

    def test_range_loc_dung(self):
        result = apply_filters(_df(), {"Tổng dư nợ": (600_000, 2_500_000)})
        assert len(result) == 2
        assert all(result["Tổng dư nợ"] >= 600_000)
        assert all(result["Tổng dư nợ"] <= 2_500_000)

    def test_range_bao_gom_bien(self):
        result = apply_filters(_df(), {"Tổng dư nợ": (500_000, 1_000_000)})
        assert len(result) == 2

    def test_range_loai_tat_ca(self):
        result = apply_filters(_df(), {"Tổng dư nợ": (5_000_000, 10_000_000)})
        assert result.empty

    # ── Nhiều filter kết hợp ─────────────────────────────────────────────────

    def test_nhieu_filter_and(self):
        result = apply_filters(_df(), {
            "Tên PGD": "Long Thành",
            "Tổng dư nợ": (600_000, 2_000_000),
        })
        assert len(result) == 1
        assert result["Tổng dư nợ"].iloc[0] == 1_000_000
