"""Migration 003: Thêm snapshot chỉ tiêu theo địa bàn thôn."""
import sqlite3

VERSION = 3

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS thon_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ky              TEXT    NOT NULL,
    ten_pgd         TEXT    NOT NULL,
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
);
CREATE INDEX IF NOT EXISTS idx_thon_snap_ky ON thon_snapshot(ky);
CREATE INDEX IF NOT EXISTS idx_thon_snap_pgd_xa
    ON thon_snapshot(ky, ten_pgd, ten_xa);
"""


def upgrade(conn: sqlite3.Connection) -> None:
    for statement in _SCHEMA_SQL.split(";"):
        sql = statement.strip()
        if sql:
            conn.execute(sql)
