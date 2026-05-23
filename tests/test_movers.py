"""tests/test_movers.py — components/movers._compute_movers()

_compute_movers() là hàm thuần pandas — không có st.* calls.
"""
from __future__ import annotations

import pandas as pd
import pytest

from components.movers import _compute_movers

COT_TEN_PGD    = "Tên PGD"
COT_TONG_DU_NO = "Tổng dư nợ"
COT_DU_NO_QH   = "Dư nợ quá hạn"
COT_DU_NO_TH   = "Dư nợ trong hạn"


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _df_curr() -> pd.DataFrame:
    return pd.DataFrame({
        COT_TEN_PGD:    ["PGD A", "PGD B"],
        COT_TONG_DU_NO: [1_000_000, 2_000_000],
        COT_DU_NO_QH:   [0, 200_000],
        COT_DU_NO_TH:   [1_000_000, 1_800_000],
    })


def _df_prev() -> pd.DataFrame:
    return pd.DataFrame({
        COT_TEN_PGD:    ["PGD A", "PGD B"],
        COT_TONG_DU_NO: [900_000, 2_200_000],
        COT_DU_NO_QH:   [100_000, 100_000],
        COT_DU_NO_TH:   [800_000, 2_100_000],
    })


# ══════════════════════════════════════════════════════════════════════════════
# _compute_movers()
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeMovers:

    # ── Kiểu trả về ──────────────────────────────────────────────────────────

    def test_tra_ve_list(self):
        result = _compute_movers(_df_curr(), None, COT_TEN_PGD, "tong_du_no")
        assert isinstance(result, list)

    def test_so_phan_tu_khop_so_pgd(self):
        result = _compute_movers(_df_curr(), None, COT_TEN_PGD, "tong_du_no")
        assert len(result) == 2

    def test_moi_phan_tu_co_cac_key_bat_buoc(self):
        result = _compute_movers(_df_curr(), None, COT_TEN_PGD, "tong_du_no")
        required = {"key", "curr_value", "prev_value", "delta", "pct_delta",
                    "prev_tong_du_no", "curr_tong_du_no"}
        for item in result:
            assert required <= set(item.keys())

    # ── Guard conditions ─────────────────────────────────────────────────────

    def test_empty_curr_tra_ve_list_rong(self):
        assert _compute_movers(pd.DataFrame(), None, COT_TEN_PGD, "tong_du_no") == []

    def test_col_khong_ton_tai_tra_ve_list_rong(self):
        assert _compute_movers(_df_curr(), None, "Cot Khong Co", "tong_du_no") == []

    # ── metric = tong_du_no ──────────────────────────────────────────────────

    def test_tong_du_no_curr_dung(self):
        result = _compute_movers(_df_curr(), None, COT_TEN_PGD, "tong_du_no")
        curr_map = {r["key"]: r["curr_value"] for r in result}
        assert curr_map["PGD A"] == 1_000_000
        assert curr_map["PGD B"] == 2_000_000

    def test_prev_none_cho_prev_value_la_0(self):
        result = _compute_movers(_df_curr(), None, COT_TEN_PGD, "tong_du_no")
        for r in result:
            assert r["prev_value"] == 0.0

    def test_delta_voi_prev(self):
        result = _compute_movers(_df_curr(), _df_prev(), COT_TEN_PGD, "tong_du_no")
        m = {r["key"]: r for r in result}
        # PGD A: 1M - 0.9M = +0.1M
        assert abs(m["PGD A"]["delta"] - 100_000) < 1
        # PGD B: 2M - 2.2M = -0.2M
        assert abs(m["PGD B"]["delta"] + 200_000) < 1

    def test_pct_delta_dung(self):
        result = _compute_movers(_df_curr(), _df_prev(), COT_TEN_PGD, "tong_du_no")
        m = {r["key"]: r for r in result}
        # PGD A: delta=100k, prev=900k → pct ≈ 0.111
        assert m["PGD A"]["pct_delta"] is not None
        assert abs(m["PGD A"]["pct_delta"] - 100_000 / 900_000) < 0.001

    # ── metric = ty_le_nqh ───────────────────────────────────────────────────

    def test_ty_le_nqh_no_prev(self):
        result = _compute_movers(_df_curr(), None, COT_TEN_PGD, "ty_le_nqh")
        m = {r["key"]: r for r in result}
        # PGD A: 0/1M = 0
        assert m["PGD A"]["curr_value"] == 0.0
        # PGD B: 200k/2M = 0.1
        assert abs(m["PGD B"]["curr_value"] - 0.1) < 0.001

    def test_ty_le_nqh_dn_0_khong_crash(self):
        df = pd.DataFrame({
            COT_TEN_PGD:    ["PGD C"],
            COT_TONG_DU_NO: [0],
            COT_DU_NO_QH:   [0],
            COT_DU_NO_TH:   [0],
        })
        result = _compute_movers(df, None, COT_TEN_PGD, "ty_le_nqh")
        assert result[0]["curr_value"] == 0.0

    # ── metric = roll_rate ───────────────────────────────────────────────────

    def test_roll_rate_voi_prev(self):
        result = _compute_movers(_df_curr(), _df_prev(), COT_TEN_PGD, "roll_rate")
        m = {r["key"]: r for r in result}
        # PGD A: curr_qh=0 / prev_th=800k = 0
        assert m["PGD A"]["curr_value"] == 0.0
        # PGD B: curr_qh=200k / prev_th=2_100k ≈ 0.095
        assert abs(m["PGD B"]["curr_value"] - 200_000 / 2_100_000) < 0.001
