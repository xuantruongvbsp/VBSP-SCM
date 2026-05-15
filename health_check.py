"""
health_check.py — Kiểm tra nhanh các quy trình nghiệp vụ quan trọng
Chạy: python health_check.py
Mục đích: chạy tay mỗi sáng để phát hiện quy trình nào đang bị lỗi.
"""
import json
import os
import sqlite3
from pathlib import Path

from config import CACHE_HSTD, CACHE_NQ11, DS_PGD
from data.pgd import duong_dan_pgd, pgd_slug
from db import doc_kv, get_conn

CHECKS = []


def check(name):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


@check("kv_store: khtd_cn tồn tại")
def _():
    data = doc_kv("khtd_cn")
    assert data and isinstance(data, dict), "Chưa nhập KHTD cấp chi nhánh (khtd_cn rỗng hoặc None)"


@check("Merge HSTD đã chạy")
def _():
    meta = doc_kv("merge_meta_hstd")
    assert meta and meta.get("so_pgd", 0) > 0, (
        f"Chưa merge HSTD hoặc merge_meta_hstd không hợp lệ: {meta}"
    )


@check("File hstd.parquet tồn tại trên disk")
def _():
    path = Path(CACHE_HSTD)
    assert path.exists(), f"Thiếu file: {path}"


@check("File nq11.parquet tồn tại trên disk")
def _():
    path = Path(CACHE_NQ11)
    assert path.exists(), f"Thiếu file: {path}"


@check("Tất cả PGD đã upload HSTD")
def _():
    thieu = []
    for pgd in DS_PGD:
        duong_dan = duong_dan_pgd(pgd, "hstd")
        if not os.path.exists(duong_dan):
            thieu.append(pgd)
    assert not thieu, f"PGD chưa upload HSTD ({len(thieu)}): {thieu}"


@check("Không có key kv_store bị corrupt")
def _():
    loi = []
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM kv_store").fetchall()
    for row in rows:
        try:
            json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            loi.append(row["key"])
    assert not loi, f"Key bị corrupt ({len(loi)}): {loi}"


@check("Audit log có ghi nhận trong 24h qua")
def _():
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE ts > datetime('now', '-1 day')"
        ).fetchone()[0]
    # Cảnh báo nếu không có activity — app có thể chưa chạy
    assert count > 0, f"Không có audit log trong 24h qua (app chưa chạy hoặc chưa có thao tác)"


if __name__ == "__main__":
    ok, fail = 0, 0
    print("=" * 50)
    print("HEALTH CHECK — VBSP-SCM")
    print("=" * 50)
    for name, fn in CHECKS:
        try:
            fn()
            print(f"  ✅ {name}")
            ok += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            fail += 1
    print(f"\n{'=' * 50}")
    print(f"Kết quả: {ok} OK / {fail} LỖI")
    print("=" * 50)
