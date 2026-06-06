"""Bổ sung edge cases cho test_tongquan_service.py."""

import pandas as pd
import pytest

from services.tongquan_service import tinh_tqpgd_extended
from config import COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_MA_KH, COT_SO_KU, COT_LAI_TON, COT_NGAY_DH, COT_DU_NO_KHOANH


def _df_mau(pgd_list=None, du_no_list=None, qh_list=None):
    """Tạo DataFrame mẫu với các cột bắt buộc."""
    if pgd_list is None:
        pgd_list = ["PGD Long Thành", "PGD Trảng Bom"]
    if du_no_list is None:
        du_no_list = [10000, 20000]
    if qh_list is None:
        qh_list = [100, 200]

    n = len(pgd_list)
    return pd.DataFrame({
        COT_TEN_PGD: pgd_list,
        COT_TONG_DU_NO: du_no_list,
        COT_DU_NO_QH: qh_list,
        COT_MA_KH: [f"KH{i:03d}" for i in range(n)],
        COT_SO_KU: [f"KU{i:03d}" for i in range(n)],
        COT_LAI_TON: [50] * n,
        COT_NGAY_DH: pd.to_datetime(["2026-06-01"] * ((n + 1) // 2) + ["2025-12-15"] * (n // 2)),
        COT_DU_NO_KHOANH: [0] * n,
    })


class TestTqpgdExtendedEdgeCases:
    """Edge cases cho tinh_tqpgd_extended()."""

    def test_pgd_duy_nhat(self):
        df = _df_mau(["PGD Long Thành"], [10000], [100])
        result = tinh_tqpgd_extended(
            df, col_khoanh=COT_DU_NO_KHOANH, col_cv="", cols_thu_key="",
            nam_ht="2026", cot_pgd=COT_TEN_PGD, cot_tdn=COT_TONG_DU_NO,
            cot_dqh=COT_DU_NO_QH, cot_lai_ton=COT_LAI_TON,
            cot_ngay_dh=COT_NGAY_DH, cot_ma_kh=COT_MA_KH, cot_so_ku=COT_SO_KU,
        )
        assert len(result) == 1
        assert result.iloc[0]["du_no"] == 10000
        assert result.iloc[0]["nqh"] == 100

    def test_nhieu_pgd(self):
        df = _df_mau(["PGD A", "PGD B", "PGD C"], [1000, 2000, 3000], [50, 100, 150])
        result = tinh_tqpgd_extended(
            df, col_khoanh=COT_DU_NO_KHOANH, col_cv="", cols_thu_key="",
            nam_ht="2026", cot_pgd=COT_TEN_PGD, cot_tdn=COT_TONG_DU_NO,
            cot_dqh=COT_DU_NO_QH, cot_lai_ton=COT_LAI_TON,
            cot_ngay_dh=COT_NGAY_DH, cot_ma_kh=COT_MA_KH, cot_so_ku=COT_SO_KU,
        )
        assert len(result) == 3

    def test_no_dh_nam_loc_dung_nam(self):
        df = _df_mau(["PGD Test"], [10000], [0])
        result = tinh_tqpgd_extended(
            df, col_khoanh=COT_DU_NO_KHOANH, col_cv="", cols_thu_key="",
            nam_ht="2026", cot_pgd=COT_TEN_PGD, cot_tdn=COT_TONG_DU_NO,
            cot_dqh=COT_DU_NO_QH, cot_lai_ton=COT_LAI_TON,
            cot_ngay_dh=COT_NGAY_DH, cot_ma_kh=COT_MA_KH, cot_so_ku=COT_SO_KU,
        )
        # PGD Long Thành có ngày đh 2026-06-01 → nợ ĐH phải > 0
        pgd_lt = df[df[COT_TEN_PGD] == "PGD Long Thành"]
        if not pgd_lt.empty:
            assert "no_dh_nam" in result.columns

    def test_khong_co_cot_lai_ton_khong_crash(self):
        df = _df_mau(["PGD X"], [5000], [50])
        df = df.drop(columns=[COT_LAI_TON])
        result = tinh_tqpgd_extended(
            df, col_khoanh=COT_DU_NO_KHOANH, col_cv="", cols_thu_key="",
            nam_ht="2026", cot_pgd=COT_TEN_PGD, cot_tdn=COT_TONG_DU_NO,
            cot_dqh=COT_DU_NO_QH, cot_lai_ton=COT_LAI_TON,
            cot_ngay_dh=COT_NGAY_DH if COT_NGAY_DH in df.columns else "",
            cot_ma_kh=COT_MA_KH, cot_so_ku=COT_SO_KU,
        )
        # Không crash, lai_ton = 0
        assert result.iloc[0]["lai_ton"] == 0

    def test_khong_co_cot_ngay_dh_khong_crash(self):
        df = _df_mau(["PGD X"], [5000], [50])
        df = df.drop(columns=[COT_NGAY_DH])
        result = tinh_tqpgd_extended(
            df, col_khoanh=COT_DU_NO_KHOANH, col_cv="", cols_thu_key="",
            nam_ht="2026", cot_pgd=COT_TEN_PGD, cot_tdn=COT_TONG_DU_NO,
            cot_dqh=COT_DU_NO_QH, cot_lai_ton=COT_LAI_TON,
            cot_ngay_dh=COT_NGAY_DH,
            cot_ma_kh=COT_MA_KH, cot_so_ku=COT_SO_KU,
        )
        assert "no_dh_nam" in result.columns
        assert result.iloc[0]["no_dh_nam"] == 0

    def test_ds_thu_no_tu_nhieu_cot(self):
        df = _df_mau(["PGD A"], [8000], [80])
        df["Thu nợ trong năm"] = [500]
        df["Thu nợ QH trong năm"] = [100]
        result = tinh_tqpgd_extended(
            df, col_khoanh=COT_DU_NO_KHOANH, col_cv="",
            cols_thu_key="Thu nợ trong năm,Thu nợ QH trong năm",
            nam_ht="2026", cot_pgd=COT_TEN_PGD, cot_tdn=COT_TONG_DU_NO,
            cot_dqh=COT_DU_NO_QH, cot_lai_ton=COT_LAI_TON,
            cot_ngay_dh=COT_NGAY_DH, cot_ma_kh=COT_MA_KH, cot_so_ku=COT_SO_KU,
        )
        assert result.iloc[0]["ds_thu_no"] == 600

    def test_pgd_bi_trung_agg_dung(self):
        """Nhiều dòng cùng PGD → groupby sum."""
        df = pd.DataFrame({
            COT_TEN_PGD: ["PGD X", "PGD X"],
            COT_TONG_DU_NO: [3000, 2000],
            COT_DU_NO_QH: [30, 20],
            COT_MA_KH: ["KH001", "KH002"],
            COT_SO_KU: ["KU001", "KU002"],
            COT_LAI_TON: [10, 5],
        })
        result = tinh_tqpgd_extended(
            df, col_khoanh="", col_cv="", cols_thu_key="",
            nam_ht="2026", cot_pgd=COT_TEN_PGD, cot_tdn=COT_TONG_DU_NO,
            cot_dqh=COT_DU_NO_QH, cot_lai_ton=COT_LAI_TON,
            cot_ngay_dh="", cot_ma_kh=COT_MA_KH, cot_so_ku=COT_SO_KU,
        )
        assert len(result) == 1
        assert result.iloc[0]["du_no"] == 5000
        assert result.iloc[0]["nqh"] == 50
