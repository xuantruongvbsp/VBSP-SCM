"""Regression tests cho fallback BQ Hội khi HSTD thiếu Tên ĐVUT."""
from __future__ import annotations

import pandas as pd

from config import (
    COT_DVUT,
    COT_MA_PGD,
    COT_MA_TO,
    COT_TEN_PGD,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)
from data import cdtotkvv
from tabs import tab_tongquan


def test_ban_do_ma_to_dvut_bo_key_don_khi_ma_to_mo_ho(monkeypatch):
    df_cdto = pd.DataFrame({
        "ma_dv": ["004601", "004602"],
        "ma_to": ["000123", "123"],
        "dvut": ["11", "12"],
    })
    monkeypatch.setattr(cdtotkvv, "doc_cdtotkvv_toan_cn_pgd", lambda: df_cdto)

    result = cdtotkvv.ban_do_ma_to_dvut()

    assert result["4601|123"] == "11"
    assert result["4602|123"] == "12"
    assert "123" not in result


def test_cache_bq_counts_uu_tien_key_kep_ma_pgd_ma_to(monkeypatch):
    df_hstd = pd.DataFrame({
        COT_TEN_PGD: ["Hội sở Chi nhánh tỉnh"] * 3,
        COT_MA_PGD: ["004601"] * 3,
        COT_MA_TO: ["000123", "000124", "000125"],
        COT_TEN_TO: ["", "", ""],
        COT_TEN_XA: ["Biên Hòa"] * 3,
        COT_DVUT: [None, None, None],
        COT_TONG_DU_NO: [10_000_000, 20_000_000, 30_000_000],
    })
    monkeypatch.setattr(
        tab_tongquan,
        "ban_do_ma_to_dvut",
        lambda: {
            "4601|123": "11",
            "4601|124": "11",
            "4601|125": "11",
            "123": "14",
        },
    )

    _n_pgd, _n_to, _n_xa, n_hoi = tab_tongquan._cache_bq_counts(
        df_hstd,
        ts=1.0,
        pgd_filter="",
    )

    assert n_hoi == 1
