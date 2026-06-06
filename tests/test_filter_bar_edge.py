"""Bổ sung edge cases cho test_filter_bar.py — apply_filters."""

import pandas as pd
import pytest

from components.filter_bar import apply_filters
from config import COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_TEN_XA


def _df_mau():
    return pd.DataFrame({
        COT_TEN_PGD: ["PGD A", "PGD B", "PGD C"],
        COT_TONG_DU_NO: [10000, 20000, 30000],
        COT_DU_NO_QH: [100, 200, 300],
        COT_TEN_XA: ["Xã 1", "Xã 2", "Xã 3"],
    })


class TestApplyFiltersEdgeCases:
    """Edge cases cho apply_filters()."""

    def test_filter_empty_tra_df_goc(self):
        df = _df_mau()
        result = apply_filters(df, {})
        assert len(result) == 3

    def test_filter_none_value_bi_bo_qua(self):
        df = _df_mau()
        result = apply_filters(df, {COT_TEN_PGD: None})
        assert len(result) == 3

    def test_select_chinh_xac_1_pgd(self):
        df = _df_mau()
        result = apply_filters(df, {COT_TEN_PGD: ["PGD A"]})
        assert len(result) == 1
        assert result.iloc[0][COT_TEN_PGD] == "PGD A"

    def test_select_nhieu_pgd(self):
        df = _df_mau()
        result = apply_filters(df, {COT_TEN_PGD: ["PGD A", "PGD C"]})
        assert len(result) == 2

    def test_select_list_empty_tra_df_goc(self):
        df = _df_mau()
        result = apply_filters(df, {COT_TEN_PGD: []})
        assert len(result) == 3  # list rỗng → không filter

    def test_range_filter_dung_khoang(self):
        df = _df_mau()
        result = apply_filters(df, {COT_TONG_DU_NO: (15000, 25000)})
        assert len(result) == 1
        assert result.iloc[0][COT_TEN_PGD] == "PGD B"

    def test_text_filter_tim_gan_dung(self):
        df = _df_mau()
        result = apply_filters(df, {COT_TEN_PGD: "PGD"})
        assert len(result) == 3  # tất cả đều chứa "PGD"

    def test_text_filter_chinh_xac(self):
        df = _df_mau()
        result = apply_filters(df, {COT_TEN_PGD: "PGD A"})
        assert len(result) == 1

    def test_filter_cot_khong_ton_tai_bo_qua(self):
        df = _df_mau()
        result = apply_filters(df, {"Cot_Khong_Ton_Tai": "xxx"})
        assert len(result) == 3  # cột không tồn tại → bỏ qua

    def test_ket_hop_nhieu_filter(self):
        df = _df_mau()
        filters = {
            COT_TEN_PGD: ["PGD A", "PGD B"],
            COT_TONG_DU_NO: (15000, 30000),
        }
        result = apply_filters(df, filters)
        assert len(result) == 1  # PGD B (20000 nằm trong khoảng)
        assert result.iloc[0][COT_TEN_PGD] == "PGD B"

    def test_df_empty_tra_df_rong(self):
        df = pd.DataFrame(columns=[COT_TEN_PGD, COT_TONG_DU_NO])
        result = apply_filters(df, {COT_TEN_PGD: ["PGD A"]})
        assert result.empty
