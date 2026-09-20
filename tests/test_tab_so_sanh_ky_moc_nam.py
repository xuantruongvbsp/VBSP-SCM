"""Regression tests cho lựa chọn mốc năm trong tab So sánh kỳ."""
from __future__ import annotations

import importlib

import pandas as pd


render_moc_nam = importlib.import_module("tabs.tab_so_sanh_ky.render_moc_nam")


def test_nq11_chi_nhan_moc_co_ngay_bao_cao_dung_3112(monkeypatch) -> None:
    snapshots = {
        "2025-12": pd.DataFrame({"ngay_bc": ["31/12/2025"]}),
        "2026-12": pd.DataFrame({"ngay_bc": ["12/05/2026"]}),
    }
    monkeypatch.setattr(
        render_moc_nam,
        "doc_nq11_snapshot",
        lambda ky: snapshots[ky],
    )

    assert render_moc_nam._la_moc_nq11_cuoi_nam("2025-12") is True
    assert render_moc_nam._la_moc_nq11_cuoi_nam("2026-12") is False
    assert render_moc_nam._la_moc_nq11_cuoi_nam("2026-05") is False
