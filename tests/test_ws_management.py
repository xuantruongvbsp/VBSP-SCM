from __future__ import annotations

import sqlite3
from unittest.mock import patch

from workspaces.ws_management import _doc_nqh_delta_snapshot


def test_nqh_delta_snapshot_chi_doc_lop_tong_pgd() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE hstd_snapshot (
            ky TEXT, ten_pgd TEXT, ma_ct TEXT, nguon_von TEXT,
            du_no_qh REAL, tong_du_no REAL
        )"""
    )
    conn.executemany(
        "INSERT INTO hstd_snapshot VALUES (?,?,?,?,?,?)",
        [
            ("2026-08", "PGD A", "ALL", "ALL", 10.0, 100.0),
            ("2026-08", "PGD A", "1", "1", 10.0, 100.0),
            ("2025-12", "PGD A", "ALL", "ALL", 3.0, 50.0),
            ("2025-12", "PGD A", "1", "1", 3.0, 50.0),
        ],
    )
    conn.commit()

    with patch("db.get_conn", return_value=conn):
        result = _doc_nqh_delta_snapshot()
    conn.close()

    assert result.iloc[0]["qh_curr"] == 10.0
    assert result.iloc[0]["qh_prev"] == 3.0
    assert result.iloc[0]["dn_curr"] == 100.0
    assert result.iloc[0]["dn_prev"] == 50.0
    assert result.iloc[0]["delta_qh"] == 7.0
