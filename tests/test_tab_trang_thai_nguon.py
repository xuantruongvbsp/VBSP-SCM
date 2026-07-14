"""Hồi quy query trạng thái snapshot HSTD."""
from __future__ import annotations

import sqlite3
from unittest.mock import patch

from tabs.tab_trang_thai_nguon import _doc_snapshot_status


def test_snapshot_status_chi_cong_lop_tong_pgd():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE hstd_snapshot (
            ky TEXT, ten_pgd TEXT, ma_ct TEXT, nguon_von TEXT,
            tong_du_no REAL, created_at TEXT
        )"""
    )
    conn.executemany(
        "INSERT INTO hstd_snapshot VALUES (?,?,?,?,?,?)",
        [
            ("2026-03", "PGD A", "ALL", "ALL", 100.0, "2026-03-31"),
            ("2026-03", "PGD B", "ALL", "ALL", 200.0, "2026-03-31"),
            ("2026-03", "__CN__", "ALL", "ALL", 300.0, "2026-03-31"),
            ("2026-03", "PGD A", "2", "1", 100.0, "2026-03-31"),
        ],
    )
    with patch("tabs.tab_trang_thai_nguon.db.get_conn", return_value=conn):
        result = _doc_snapshot_status()
    conn.close()

    assert result.iloc[0]["Số đơn vị"] == 2
    assert result.iloc[0]["Tổng dư nợ (VND)"] == 300.0
