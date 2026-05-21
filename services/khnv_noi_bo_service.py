from __future__ import annotations

import db


def doc_ds(key: str) -> list:
    val = db.doc_kv(key)
    return val if isinstance(val, list) else []


def ghi_ds(key: str, ds: list, username: str, action: str, mo_ta: str) -> None:
    db.ghi_kv(key, ds, username)
    db.ghi_audit(username, action, mo_ta)

