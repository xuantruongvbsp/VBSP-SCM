"""Test cho services/period_compare.py — so sánh 2 kỳ, roll rate, vintage NQH."""
from __future__ import annotations

import pandas as pd
import pytest

from services.period_compare import (
    CHANGE_LABELS,
    CHANGE_TYPES,
    classify_changes,
    join_by_loan,
    par_breakdown,
    roll_cure_rate,
    vintage_nqh,
)
from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGAY_SL,
    COT_NGAY_VAY,
    COT_SO_KU,
    COT_TONG_DU_NO,
)


class TestJoinByLoan:
    def test_join_on_key(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU2", "KU3"],
            COT_MA_KH: ["KH1", "KH2", "KH3"],
            COT_TONG_DU_NO: [100, 200, 300],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU1", "KU2", "KU4"],
            COT_MA_KH: ["KH1", "KH2", "KH4"],
            COT_TONG_DU_NO: [150, 250, 400],
        })
        joined = join_by_loan(prev, curr)
        assert len(joined) == 4
        bucket_map = dict(zip(joined["_key"], joined["_bucket"]))
        assert bucket_map["KU1\x00KH1"] == "both"
        assert bucket_map["KU2\x00KH2"] == "both"
        assert bucket_map["KU3\x00KH3"] == "closed"
        assert bucket_map["KU4\x00KH4"] == "new"
        assert f"{COT_TONG_DU_NO}_prev" in joined.columns
        assert f"{COT_TONG_DU_NO}_curr" in joined.columns
        assert joined.loc[joined["_key"] == "KU1\x00KH1", f"{COT_TONG_DU_NO}_prev"].iloc[0] == 100
        assert joined.loc[joined["_key"] == "KU1\x00KH1", f"{COT_TONG_DU_NO}_curr"].iloc[0] == 150

    def test_join_with_extra_columns(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1"], COT_MA_KH: ["KH1"], "extra_prev": ["abc"],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU1"], COT_MA_KH: ["KH1"], "extra_curr": ["xyz"],
        })
        joined = join_by_loan(prev, curr)
        assert joined["extra_prev"].iloc[0] == "abc"
        assert joined["extra_curr"].iloc[0] == "xyz"

    def test_both_empty(self):
        assert join_by_loan(pd.DataFrame(), pd.DataFrame()).empty

    def test_status_columns_added(self):
        prev = pd.DataFrame({
            COT_SO_KU: ["KU1"], COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [100], COT_DU_NO_QH: [0],
        })
        curr = pd.DataFrame({
            COT_SO_KU: ["KU1"], COT_MA_KH: ["KH1"],
            COT_DU_NO_TH: [0], COT_DU_NO_QH: [50],
        })
        joined = join_by_loan(prev, curr)
        assert "_status_prev" in joined.columns
        assert "_status_curr" in joined.columns
        assert joined["_status_prev"].iloc[0] == "th"
        assert joined["_status_curr"].iloc[0] == "qh"


class TestClassifyChanges:
    def _mk(self, bucket, sp, sc, dn_p=0, dn_c=0, dh_p=None, dh_c=None):
        data = {
            "_key": ["KU1"], "_bucket": [bucket],
            "_status_prev": [sp], "_status_curr": [sc],
            f"{COT_TONG_DU_NO}_prev": [dn_p], f"{COT_TONG_DU_NO}_curr": [dn_c],
        }
        if dh_p is not None:
            data[f"{COT_NGAY_DH}_prev"] = [dh_p]
        if dh_c is not None:
            data[f"{COT_NGAY_DH}_curr"] = [dh_c]
        return pd.DataFrame(data)

    def test_classify_new_loan(self):
        r = classify_changes(self._mk("new", "none", "th", dn_c=100))
        assert r["_change_type"].iloc[0] == "new"

    def test_classify_closed(self):
        r = classify_changes(self._mk("closed", "th", "none", dn_p=100))
        assert r["_change_type"].iloc[0] == "closed"

    def test_classify_worsened(self):
        r = classify_changes(self._mk("both", "th", "qh", dn_p=100, dn_c=100))
        assert r["_change_type"].iloc[0] == "worsened"

    def test_classify_improved(self):
        r = classify_changes(self._mk("both", "qh", "th", dn_p=100, dn_c=100))
        assert r["_change_type"].iloc[0] == "improved"

    def test_classify_extended(self):
        r = classify_changes(self._mk("both", "th", "th", dn_p=100, dn_c=100,
                                       dh_p="2025-01-01", dh_c="2025-06-01"))
        assert r["_change_type"].iloc[0] == "extended"

    def test_classify_increased(self):
        r = classify_changes(self._mk("both", "th", "th", dn_p=100, dn_c=150))
        assert r["_change_type"].iloc[0] == "increased"

    def test_classify_decreased(self):
        r = classify_changes(self._mk("both", "th", "th", dn_p=200, dn_c=150))
        assert r["_change_type"].iloc[0] == "decreased"

    def test_classify_unchanged(self):
        r = classify_changes(self._mk("both", "th", "th", dn_p=100, dn_c=100))
        assert r["_change_type"].iloc[0] == "unchanged"

    def test_extra_columns(self):
        r = classify_changes(self._mk("both", "th", "qh", dn_p=100, dn_c=150))
        assert "_change_label" in r.columns
        assert "_du_no_delta" in r.columns
        assert "_status_rank_delta" in r.columns
        assert r["_du_no_delta"].iloc[0] == 50.0
        assert r["_status_rank_delta"].iloc[0] == 1

    def test_empty_input(self):
        assert classify_changes(pd.DataFrame()).empty


class TestRollCureRate:
    def test_basic(self):
        joined = pd.DataFrame({
            "_key": ["KU1", "KU2", "KU3", "KU4"],
            "_bucket": ["both", "both", "both", "both"],
            "_status_prev": ["th", "th", "qh", "qh"],
            "_status_curr": ["qh", "th", "th", "qh"],
            f"{COT_DU_NO_TH}_prev": [100.0, 200.0, 0.0, 0.0],
            f"{COT_DU_NO_TH}_curr": [0.0, 200.0, 150.0, 0.0],
            f"{COT_DU_NO_QH}_prev": [0.0, 0.0, 300.0, 400.0],
            f"{COT_DU_NO_QH}_curr": [50.0, 0.0, 0.0, 400.0],
        })
        r = roll_cure_rate(joined)
        assert r["base_th_prev"] == 300.0
        assert r["roll_count"] == 1
        assert abs(r["roll_rate"] - 50.0 / 300.0) < 1e-9
        assert r["base_qh_prev"] == 700.0
        assert r["cure_count"] == 1
        assert abs(r["cure_rate"] - 150.0 / 700.0) < 1e-9

    def test_empty_input(self):
        r = roll_cure_rate(pd.DataFrame())
        assert r["roll_rate"] == 0.0
        assert r["cure_rate"] == 0.0
        assert r["roll_count"] == 0

    def test_new_closed_ignored(self):
        joined = pd.DataFrame({
            "_key": ["KU1", "KU2"],
            "_bucket": ["new", "closed"],
            "_status_prev": ["none", "th"],
            "_status_curr": ["th", "none"],
            f"{COT_DU_NO_TH}_prev": [0.0, 100.0],
            f"{COT_DU_NO_TH}_curr": [100.0, 0.0],
            f"{COT_DU_NO_QH}_prev": [0.0, 0.0],
            f"{COT_DU_NO_QH}_curr": [0.0, 0.0],
        })
        r = roll_cure_rate(joined)
        assert r["base_th_prev"] == 0.0
        assert r["base_qh_prev"] == 0.0
        assert r["roll_rate"] == 0.0


class TestVintageNQH:
    def test_basic(self):
        df = pd.DataFrame({
            COT_NGAY_VAY: ["2023-01-15", "2023-01-20", "2024-05-10"],
            COT_SO_KU: ["KU1", "KU2", "KU3"],
            COT_TONG_DU_NO: [500.0, 1000.0, 2000.0],
            COT_DU_NO_QH: [0.0, 100.0, 50.0],
        })
        df[COT_NGAY_VAY] = pd.to_datetime(df[COT_NGAY_VAY])
        v = vintage_nqh(df)
        assert not v.empty
        assert list(v.columns) == ["Năm vay", "so_ku", "tong_du_no", "du_no_qh", "Tỷ lệ NQH"]
        row_2023 = v[v["Năm vay"] == "2023"].iloc[0]
        assert row_2023["so_ku"] == 2
        assert row_2023["du_no_qh"] == 100.0
        assert row_2023["tong_du_no"] == 1500.0
        assert row_2023["Tỷ lệ NQH"] == 100.0 / 1500.0

    def test_empty_input(self):
        assert vintage_nqh(pd.DataFrame()).empty

    def test_missing_ngay_vay(self):
        assert vintage_nqh(pd.DataFrame({COT_TONG_DU_NO: [100]})).empty


class TestParBreakdown:
    def test_basic(self):
        df = pd.DataFrame({
            COT_NGAY_DH: ["2025-05-01", "2025-03-15", "2024-12-31"],
            COT_TONG_DU_NO: [100.0, 200.0, 300.0],
            COT_NGAY_SL: "2025-06-10",
        })
        df[COT_NGAY_DH] = pd.to_datetime(df[COT_NGAY_DH])
        df[COT_NGAY_SL] = pd.to_datetime(df[COT_NGAY_SL])
        par = par_breakdown(df)
        assert par["par30"] == 600.0
        assert par["par90"] == 300.0
        assert par["par180"] == 0.0
        assert par["tong_du_no"] == 600.0
        assert abs(par["par30_pct"] - 1.0) < 1e-9
        assert abs(par["par90_pct"] - 0.5) < 1e-9

    def test_empty_input(self):
        par = par_breakdown(pd.DataFrame())
        assert par["par30"] == 0
        assert par["par90"] == 0
        assert par["par180"] == 0
        assert par["tong_du_no"] == 0

    def test_no_ngay_sl(self):
        df = pd.DataFrame({
            COT_NGAY_DH: ["2025-06-01"],
            COT_TONG_DU_NO: [100.0],
        })
        par = par_breakdown(df)
        assert par["par30"] == 0
        assert par["tong_du_no"] == 100.0
