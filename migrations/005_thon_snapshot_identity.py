"""Migration 005: Bổ sung định danh PGD/mã thôn, bảo toàn snapshot đã có."""
from __future__ import annotations

import sqlite3

VERSION = 5


_CREATE_V2_SQL = """
CREATE TABLE thon_snapshot_v2 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ky              TEXT    NOT NULL,
    ten_pgd         TEXT    NOT NULL DEFAULT '',
    ma_thon         TEXT    NOT NULL DEFAULT '',
    ten_xa          TEXT    NOT NULL,
    ten_thon        TEXT    NOT NULL,
    tong_du_no      REAL    NOT NULL DEFAULT 0,
    du_no_qh        REAL    NOT NULL DEFAULT 0,
    cho_vay_thang   REAL    NOT NULL DEFAULT 0,
    thu_no_thang    REAL    NOT NULL DEFAULT 0,
    no_den_han_mon  INTEGER NOT NULL DEFAULT 0,
    no_den_han_goc  REAL    NOT NULL DEFAULT 0,
    so_mon_3m_khd   INTEGER NOT NULL DEFAULT 0,
    so_mon_rui_ro   INTEGER NOT NULL DEFAULT 0,
    ngay_so_lieu    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    created_by      TEXT    NOT NULL DEFAULT 'system',
    UNIQUE(ky, ten_pgd, ma_thon, ten_xa, ten_thon)
)
"""


def _create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_thon_snap_ky ON thon_snapshot(ky)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_thon_snap_pgd ON thon_snapshot(ky, ten_pgd)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_thon_snap_ma ON thon_snapshot(ky, ten_pgd, ma_thon)")


def upgrade(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='thon_snapshot'"
    ).fetchone()
    if not exists:
        conn.execute(_CREATE_V2_SQL.replace("thon_snapshot_v2", "thon_snapshot", 1))
        _create_indexes(conn)
        return

    columns = {row[1] for row in conn.execute("PRAGMA table_info(thon_snapshot)")}
    if {"ten_pgd", "ma_thon"}.issubset(columns):
        _create_indexes(conn)
        return

    # SAVEPOINT hoạt động an toàn cả khi init_db đang ở trong một transaction.
    conn.execute("SAVEPOINT migrate_thon_snapshot_v2")
    try:
        conn.execute("DROP TABLE IF EXISTS thon_snapshot_v2")
        conn.execute(_CREATE_V2_SQL)
        conn.execute(
            """INSERT INTO thon_snapshot_v2
               (id, ky, ten_pgd, ma_thon, ten_xa, ten_thon,
                tong_du_no, du_no_qh, cho_vay_thang, thu_no_thang,
                no_den_han_mon, no_den_han_goc, so_mon_3m_khd, so_mon_rui_ro,
                ngay_so_lieu, created_at, created_by)
               SELECT id, ky, '__UNKNOWN__', '', ten_xa, ten_thon,
                      tong_du_no, du_no_qh, cho_vay_thang, thu_no_thang,
                      no_den_han_mon, no_den_han_goc, so_mon_3m_khd, so_mon_rui_ro,
                      ngay_so_lieu, created_at, created_by
               FROM thon_snapshot"""
        )
        conn.execute("DROP TABLE thon_snapshot")
        conn.execute("ALTER TABLE thon_snapshot_v2 RENAME TO thon_snapshot")
        _create_indexes(conn)
        conn.execute("RELEASE SAVEPOINT migrate_thon_snapshot_v2")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT migrate_thon_snapshot_v2")
        conn.execute("RELEASE SAVEPOINT migrate_thon_snapshot_v2")
        raise
