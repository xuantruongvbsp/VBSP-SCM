"""Unit tests cho services/period_compare.py — So sánh kỳ cấp khế ước."""
from __future__ import annotations

import pandas as pd
import pytest

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGAY_DH_HD,
    COT_NGAY_SL,
    COT_NGAY_VAY,
    COT_SO_KU,
    COT_TONG_DU_NO,
)
from services.period_compare import (
    _derive_status,
    _status_series,
    _loan_key_series,
    join_by_loan,
    roll_cure_rate,
    classify_changes,
    CHANGE_TYPES,
    vintage_nqh,
    par_breakdown,
)

NULL_SEP = "\x00"


class TestDeriveStatus:
    def test_khoanh(self):
        assert _derive_status(100, 0, 50) == "kh"
        assert _derive_status(0, 0, 1) == "kh"

    def test_qua_han(self):
        assert _derive_status(100, 10, 0) == "qh"

    def test_trong_han(self):
        assert _derive_status(100, 0, 0) == "th"

    def test_none(self):
        assert _derive_status(0, 0, 0) == "none"

    def test_uu_tien_khoanh_tren_qh(self):
        assert _derive_status(100, 50, 10) == "kh"


class TestStatusSeries:
    def test_3_trang_thai(self):
        df = pd.DataFrame({
            COT_DU_NO_TH: [100, 0, 0, 0],
            COT_DU_NO_QH: [0, 50, 0, 0],
            "Dư nợ khoanh": [0, 0, 10, 0],
        })
        s = _status_series(df)
        assert s.iloc[0] == "th"
        assert s.iloc[1] == "qh"
        assert s.iloc[2] == "kh"
        assert s.iloc[3] == "none"

    def test_thieu_cot_van_chay(self):
        df = pd.DataFrame({"A": [1]})
        s = _status_series(df)
        assert list(s) == ["none"]


class TestLoanKeySeries:
    def test_binh_thuong(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU001", "KU002"],
            COT_MA_KH: ["KH1", "KH2"],
        })
        s = _loan_key_series(df)
        assert s.iloc[0] == f"KU001{NULL_SEP}KH1"
        assert s.iloc[1] == f"KU002{NULL_SEP}KH2"

    def test_thieu_cot_tra_rong(self):
        df = pd.DataFrame({"A": [1]})
        s = _loan_key_series(df)
        assert s.iloc[0] == f"{NULL_SEP}"


class TestJoinByLoan:
    def test_ca_hai_rong(self):
        df = join_by_loan(pd.DataFrame(), pd.DataFrame())
        assert df.empty

    def test_3_bucket(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU2"],
            COT_MA_KH: ["KH1", "KH2"],
            COT_DU_NO_TH: [100, 200],
            COT_DU_NO_QH: [0, 0],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU2", "KU3"],
            COT_MA_KH: ["KH2", "KH3"],
            COT_DU_NO_TH: [200, 100],
            COT_DU_NO_QH: [0, 0],
        })
        df = join_by_loan(prev, curr)
        assert "_bucket" in df.columns
        assert set(df["_bucket"]) == {"both", "closed", "new"}
        assert len(df) == 3

    def test_trung_key_lay_dong_cuoi(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU1"],
            COT_MA_KH: ["KH1", "KH1"],
            COT_DU_NO_TH: [100, 999],
            COT_DU_NO_QH: [0, 0],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [500],
            COT_DU_NO_QH: [0],
        })
        df = join_by_loan(prev, curr)
        assert len(df) == 1
        assert df[f"{COT_DU_NO_TH}_prev"].iloc[0] == 999


class TestRollCureRate:
    def test_trong(self):
        r = roll_cure_rate(pd.DataFrame())
        assert r["roll_rate"] == 0.0
        assert r["cure_rate"] == 0.0

    def test_roll_50pct(self):
        df = pd.DataFrame({
            "_bucket": ["both", "both"],
            "_status_prev": ["th", "th"],
            f"{COT_DU_NO_TH}_prev": [100.0, 100.0],
            f"{COT_DU_NO_QH}_prev": [0.0, 0.0],
            f"{COT_DU_NO_TH}_curr": [50.0, 0.0],
            f"{COT_DU_NO_QH}_curr": [50.0, 50.0],
        })
        r = roll_cure_rate(df)
        assert r["roll_rate"] == pytest.approx(0.5)
        assert r["roll_count"] == 2

    def test_cure_100pct(self):
        df = pd.DataFrame({
            "_bucket": ["both", "both"],
            "_status_prev": ["qh", "qh"],
            f"{COT_DU_NO_TH}_prev": [0.0, 0.0],
            f"{COT_DU_NO_QH}_prev": [100.0, 100.0],
            f"{COT_DU_NO_TH}_curr": [100.0, 100.0],
            f"{COT_DU_NO_QH}_curr": [0.0, 0.0],
        })
        r = roll_cure_rate(df)
        assert r["cure_rate"] == pytest.approx(1.0)


class TestClassifyChanges:
    def test_new_closed_both(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU2"],
            COT_MA_KH: ["KH1", "KH2"],
            COT_DU_NO_TH: [100, 200],
            COT_DU_NO_QH: [0, 0],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU2", "KU3"],
            COT_MA_KH: ["KH2", "KH3"],
            COT_DU_NO_TH: [200, 100],
            COT_DU_NO_QH: [0, 0],
        })
        joined = join_by_loan(prev, curr)
        classified = classify_changes(joined)
        buckets = classified["_bucket"]
        changes = classified["_change_type"]
        assert changes[buckets == "new"].iloc[0] == "new"
        assert changes[buckets == "closed"].iloc[0] == "closed"
        assert changes[buckets == "both"].iloc[0] == "unchanged"

    def test_worsened(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [100],
            COT_DU_NO_QH: [0],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [0],
            COT_DU_NO_QH: [100],
        })
        joined = join_by_loan(prev, curr)
        classified = classify_changes(joined)
        assert classified["_change_type"].iloc[0] == "worsened"

    def test_trong(self):
        df = classify_changes(pd.DataFrame())
        assert df.empty

    def test_co_cot_label(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [50],
            COT_DU_NO_QH: [0],
            COT_TONG_DU_NO: [50],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [150],
            COT_DU_NO_QH: [0],
            COT_TONG_DU_NO: [150],
        })
        joined = join_by_loan(prev, curr)
        classified = classify_changes(joined)
        assert classified["_change_type"].iloc[0] == "increased"
        assert "_change_label" in classified.columns
        assert "Tăng DN" in classified["_change_label"].iloc[0]

    def test_decreased(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [150],
            COT_DU_NO_QH: [0],
            COT_TONG_DU_NO: [150],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [50],
            COT_DU_NO_QH: [0],
            COT_TONG_DU_NO: [50],
        })
        joined = join_by_loan(prev, curr)
        classified = classify_changes(joined)
        assert classified["_change_type"].iloc[0] == "decreased"


class TestVintageNqh:
    def test_trong(self):
        df = vintage_nqh(pd.DataFrame())
        assert df.empty

    def test_thieu_cot_ngay_vay(self):
        df = pd.DataFrame({COT_SO_KU: ["KU1"]})
        assert vintage_nqh(df).empty

    def test_2_nam(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU2", "KU3"],
            COT_NGAY_VAY: ["01/01/2023", "15/06/2024", "01/01/2023"],
            COT_TONG_DU_NO: [100, 200, 300],
            COT_DU_NO_QH: [10, 0, 20],
        })
        df_out = vintage_nqh(df)
        assert len(df_out) == 2
        assert "Tỷ lệ NQH" in df_out.columns

    def test_ngay_khong_parse_duoc(self):
        df = pd.DataFrame({
            COT_SO_KU: ["KU1"],
            COT_NGAY_VAY: ["invalid"],
            COT_TONG_DU_NO: [100],
            COT_DU_NO_QH: [0],
        })
        df_out = vintage_nqh(df)
        assert not df_out.empty
        assert "N/A" in df_out["Năm vay"].values


class TestParBreakdown:
    def test_trong(self):
        r = par_breakdown(pd.DataFrame())
        assert r["tong_du_no"] == 0

    def test_khong_qua_han(self):
        df = pd.DataFrame({
            COT_NGAY_SL: ["01/01/2024"],
            COT_NGAY_DH: ["01/01/2025"],
            COT_TONG_DU_NO: [200],
            COT_DU_NO_QH: [0],
        })
        r = par_breakdown(df)
        assert r["par30"] == 0

    def test_qua_han_60_ngay(self):
        df = pd.DataFrame({
            COT_NGAY_SL: ["01/03/2024"],
            COT_NGAY_DH: ["01/01/2024"],
            COT_TONG_DU_NO: [100],
            COT_DU_NO_QH: [0],
        })
        r = par_breakdown(df)
        assert r["par30"] == 100
        assert r["par90"] == 0

    def test_qua_han_120_ngay(self):
        df = pd.DataFrame({
            COT_NGAY_SL: ["01/05/2024"],
            COT_NGAY_DH: ["01/01/2024"],
            COT_TONG_DU_NO: [300],
            COT_DU_NO_QH: [0],
        })
        r = par_breakdown(df)
        assert r["par30"] == 300
        assert r["par90"] == 300
        assert r["par180"] == 0

    def test_fallback_dung_qh(self):
        df = pd.DataFrame({
            COT_NGAY_SL: ["01/02/2024", "01/02/2024"],
            COT_TONG_DU_NO: [100, 50],
            COT_DU_NO_QH: [100, 0],
        })
        r = par_breakdown(df)
        assert r["par30"] == 100
