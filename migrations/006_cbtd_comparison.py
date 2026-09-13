"""Migration 006: Mở rộng thon_snapshot + thêm bảng snapshot Tổ TK&VV theo CBTD."""
import sqlite3

VERSION = 6

_THON_NEW_COLS = [
    ("du_no_th", "REAL NOT NULL DEFAULT 0"),
    ("cho_vay_nam", "REAL NOT NULL DEFAULT 0"),
    ("thu_no_nam", "REAL NOT NULL DEFAULT 0"),
]

_CBTD_TO_TKVV_SQL = """
CREATE TABLE IF NOT EXISTS cbtd_to_tkvv_snapshot (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ky          TEXT NOT NULL,
    ma_cb       TEXT NOT NULL,
    ho_ten      TEXT NOT NULL DEFAULT '',
    pgd         TEXT NOT NULL DEFAULT '',
    so_to       INTEGER NOT NULL DEFAULT 0,
    so_tot      INTEGER NOT NULL DEFAULT 0,
    so_kha      INTEGER NOT NULL DEFAULT 0,
    so_tb       INTEGER NOT NULL DEFAULT 0,
    so_yeu      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    created_by  TEXT NOT NULL DEFAULT 'system',
    UNIQUE(ky, ma_cb)
);
CREATE INDEX IF NOT EXISTS idx_cbtd_to_snap_ky ON cbtd_to_tkvv_snapshot(ky);
"""


def upgrade(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(thon_snapshot)")}
    for col, typ in _THON_NEW_COLS:
        if col not in columns:
            conn.execute(f"ALTER TABLE thon_snapshot ADD COLUMN {col} {typ}")

    for statement in _CBTD_TO_TKVV_SQL.split(";"):
        sql = statement.strip()
        if sql:
            conn.execute(sql)
