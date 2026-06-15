#!/usr/bin/env python3
"""
health_check.py — Kiểm tra sức khỏe hệ thống VBSP-SCM.
Chạy độc lập: python health_check.py
Không phụ thuộc Streamlit hay bất kỳ module app nào.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

# Đảm bảo stdout/stderr dùng UTF-8 trên Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Đường dẫn hệ thống (mirror config.py, không import config) ───────────────
BASE_DIR     = Path(__file__).parent.resolve()
DB_PATH      = os.getenv("VBSP_SCM_DB_PATH") or str(BASE_DIR / "vbsp_scm.db")
CACHE_DIR    = BASE_DIR / "cache"
PGD_DATA_DIR = BASE_DIR / "pgd_data"

CACHE_HSTD = CACHE_DIR / "hstd.parquet"
CACHE_NQ11 = CACHE_DIR / "nq11.parquet"
CACHE_GQVL = CACHE_DIR / "gqvl.parquet"

DON_VI_CHI_NHANH = "Hội sở Chi nhánh tỉnh"
DS_PGD = [
    "PGD Long Thành",  "PGD Trảng Bom",   "PGD Long Khánh",  "PGD Xuân Lộc",
    "PGD Định Quán",   "PGD Vĩnh Cửu",    "PGD Tân Phú",     "PGD Thống Nhất",
    "PGD Cẩm Mỹ",     "PGD Nhơn Trạch",  "PGD Bình Long",   "PGD Lộc Ninh",
    "PGD Bình Phước",  "PGD Phước Long",  "PGD Bù Đăng",     "PGD Đồng Phú",
    "PGD Chơn Thành",  "PGD Bù Đốp",     "PGD Bù Gia Mập",  "PGD Phú Riềng",
    "PGD Hớn Quản",
]
DS_DON_VI = [DON_VI_CHI_NHANH] + DS_PGD  # 22 đơn vị


# ── Helpers ───────────────────────────────────────────────────────────────────
def pgd_slug(ten_pgd: str) -> str:
    """Mirror data/pgd.py — chạy không cần import streamlit."""
    s = ten_pgd.strip().lower().replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def hstd_path(ten_pgd: str) -> Path:
    return PGD_DATA_DIR / pgd_slug(ten_pgd) / "hstd_latest.xlsx"


def _con() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)  # conv: skip — health_check chạy độc lập, không qua app context
    conn.row_factory = sqlite3.Row
    return conn


# ── Màu sắc terminal (tắt khi không phải TTY) ─────────────────────────────────
_COLOR = sys.stdout.isatty()

def _g(s: str) -> str: return f"\033[32m{s}\033[0m" if _COLOR else s   # green
def _r(s: str) -> str: return f"\033[31m{s}\033[0m" if _COLOR else s   # red
def _y(s: str) -> str: return f"\033[33m{s}\033[0m" if _COLOR else s   # yellow
def _b(s: str) -> str: return f"\033[1m{s}\033[0m"  if _COLOR else s   # bold


# ── Bộ ghi kết quả ────────────────────────────────────────────────────────────
_results: list[tuple[bool, str]] = []


def check(label: str, passed: bool, detail: str = "") -> bool:
    icon = "✅" if passed else "❌"
    suffix = f"  →  {detail}" if detail else ""
    print(f"  {icon} {label}{suffix}")
    _results.append((passed, label))
    return passed


def section(title: str) -> None:
    print(f"\n{_b(title)}")
    print("  " + "─" * (len(title) + 2))


# ══════════════════════════════════════════════════════════════════════════════
# 1. CƠ SỞ DỮ LIỆU SQLITE
# ══════════════════════════════════════════════════════════════════════════════
def check_database() -> None:
    section("1. Cơ sở dữ liệu SQLite")

    if not check("File vbsp_scm.db tồn tại", Path(DB_PATH).exists(), DB_PATH):
        check("Kết nối SQLite", False, "Bỏ qua — file không tồn tại")
        return

    try:
        conn = _con(); conn.execute("SELECT 1"); conn.close()
        check("Kết nối SQLite", True)
    except Exception as e:  # conv: skip
        check("Kết nối SQLite", False, str(e))
        return

    try:
        conn = _con()
        existing = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        for tbl in ("kv_store", "users", "audit_log"):
            check(f"Bảng '{tbl}' tồn tại", tbl in existing)
    except Exception as e:  # conv: skip
        check("Kiểm tra bảng", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# 2. KV_STORE — toàn vẹn và dữ liệu nghiệp vụ
# ══════════════════════════════════════════════════════════════════════════════
def check_kv_store() -> None:
    section("2. kv_store — toàn vẹn & dữ liệu nghiệp vụ")

    try:
        conn = _con()
        rows = conn.execute("SELECT key, value FROM kv_store").fetchall()
        conn.close()
    except Exception as e:  # conv: skip
        check("Đọc kv_store", False, str(e))
        return

    # 2-a. Không có row JSON corrupt
    corrupt = [r["key"] for r in rows if not _valid_json(r["value"])]
    check(
        "Không có key kv_store bị corrupt",
        not corrupt,
        f"{len(corrupt)} key lỗi: {corrupt[:5]}" if corrupt
        else f"{len(rows)} key, tất cả hợp lệ",
    )

    kv = {r["key"]: _parse_kv(r["value"]) for r in rows}

    # 2-b. khtd_cn tồn tại và không rỗng
    khtd = kv.get("khtd_cn")
    check(
        "khtd_cn tồn tại",
        bool(khtd),
        f"{len(khtd)} chương trình" if isinstance(khtd, dict) else
        ("Tồn tại" if khtd else "Chưa nhập KHTD Chi nhánh"),
    )

    # 2-c. merge_meta_hstd — chứng nhận merge đã chạy
    meta = kv.get("merge_meta_hstd")
    if meta:
        ts  = meta.get("thoi_gian") or meta.get("ts") or "?"
        npg = meta.get("so_pgd", "?")
        check("merge HSTD đã chạy", True, f"Lần cuối: {ts} | {npg} PGD")
    else:
        check("merge HSTD đã chạy", False, "merge_meta_hstd chưa tồn tại trong kv_store")

    print(f"  ℹ  Tổng số key trong kv_store: {len(rows)}")


def _valid_json(s: str) -> bool:
    try:
        json.loads(s); return True
    except Exception:
        return False


def _parse_kv(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 3. PARQUET CACHE
# ══════════════════════════════════════════════════════════════════════════════
def check_parquet() -> None:
    section("3. Parquet cache")

    for name, path in [
        ("hstd.parquet", CACHE_HSTD),
        ("nq11.parquet", CACHE_NQ11),
        ("gqvl.parquet", CACHE_GQVL),
    ]:
        if path.exists():
            size_mb = path.stat().st_size / 1_048_576
            mtime   = datetime.fromtimestamp(path.stat().st_mtime)
            age_h   = (datetime.now() - mtime).total_seconds() / 3600
            detail  = f"{size_mb:.1f} MB | cập nhật {mtime.strftime('%d/%m %H:%M')} ({age_h:.0f}h trước)"
            check(f"{name} tồn tại", True, detail)
        else:
            check(f"{name} tồn tại", False, "Chưa có — cần chạy merge")


# ══════════════════════════════════════════════════════════════════════════════
# 4. UPLOAD FILE PGD (hstd_latest.xlsx)
# ══════════════════════════════════════════════════════════════════════════════
def check_pgd_uploads() -> None:
    section("4. Upload file PGD — hstd_latest.xlsx")

    missing: list[str] = []
    stale:   list[str] = []

    for ten in DS_DON_VI:
        p = hstd_path(ten)
        if not p.exists():
            missing.append(ten)
        else:
            age = (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)).days
            if age > 3:
                stale.append(f"{ten} ({age}d)")

    uploaded = len(DS_DON_VI) - len(missing)
    check(
        f"Tất cả {len(DS_DON_VI)} đơn vị đã upload HSTD",
        not missing,
        f"{uploaded}/{len(DS_DON_VI)} đã có file",
    )

    for m in missing:
        print(f"    {_r('✗')} Chưa upload: {m}")
    for s in stale:
        print(f"    {_y('⚠')}  File cũ > 3 ngày: {s}")

    if not missing and not stale:
        print(f"    Tất cả {len(DS_DON_VI)} đơn vị OK")


# ══════════════════════════════════════════════════════════════════════════════
# 5. AUDIT LOG 24H
# ══════════════════════════════════════════════════════════════════════════════
def check_audit_log() -> None:
    section("5. Audit log 24h gần nhất")

    try:
        conn = _con()
        cutoff   = (datetime.now() - timedelta(hours=24)).isoformat()
        cnt_24h  = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_log WHERE ts >= ?", (cutoff,)
        ).fetchone()["c"]
        cnt_total = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_log"
        ).fetchone()["c"]
        recent = conn.execute(
            "SELECT ts, username, action, detail FROM audit_log ORDER BY id DESC LIMIT 5"
        ).fetchall()
        conn.close()
    except Exception as e:  # conv: skip
        check("Đọc audit_log", False, str(e))
        return

    check(
        "Có hoạt động trong 24h",
        cnt_24h > 0,
        f"{cnt_24h} log trong 24h | tổng cộng {cnt_total}",
    )

    if recent:
        print()
        print(f"  {'Thời gian':<22} {'User':<16} {'Action':<24} Detail")
        print("  " + "─" * 88)
        for r in recent:
            ts_s  = (r["ts"] or "-")[:19]
            usr_s = (r["username"] or "-")[:14]
            act_s = (r["action"]   or "-")[:22]
            det_s = (r["detail"]   or "")[:44]
            print(f"  {ts_s:<22} {usr_s:<16} {act_s:<24} {det_s}")


# ══════════════════════════════════════════════════════════════════════════════
# TỔNG KẾT
# ══════════════════════════════════════════════════════════════════════════════
def summary() -> int:
    passed = sum(1 for ok, _ in _results if ok)
    failed = len(_results) - passed

    print("\n" + "═" * 56)
    print(_b("TỔNG KẾT"))
    print("═" * 56)
    print(f"  Tổng checks : {len(_results)}")
    print(f"  {_g(f'Đạt        : {passed}')}")
    if failed:
        print(f"  {_r(f'Lỗi        : {failed}')}")
        print()
        for ok, lbl in _results:
            if not ok:
                print(f"    {_r('✗')} {lbl}")
    print("═" * 56)
    return 0 if failed == 0 else 1


# ══════════════════════════════════════════════════════════════════════════════
# GHI KẾT QUẢ VÀO KV_STORE (để app đọc và hiện cảnh báo sidebar)
# ══════════════════════════════════════════════════════════════════════════════
def _ghi_ket_qua_kv(exit_code: int) -> None:
    """Lưu kết quả health check vào kv_store với key 'health_check_result'."""
    passed = sum(1 for ok, _ in _results if ok)
    failed = len(_results) - passed
    failed_labels = [lbl for ok, lbl in _results if not ok]

    payload = json.dumps({
        "ts":           datetime.now().isoformat(),
        "total":        len(_results),
        "passed":       passed,
        "failed":       failed,
        "failed_labels": failed_labels,
        "exit_code":    exit_code,
    }, ensure_ascii=False)

    try:
        conn = _con()
        conn.execute(
            """INSERT OR REPLACE INTO kv_store (key, value, updated_at, updated_by)
               VALUES (?, ?, ?, ?)""",
            ("health_check_result", payload, datetime.now().isoformat(), "health_check"),
        )
        conn.commit()
        conn.close()
        print(f"\n  ℹ  Đã ghi kết quả vào kv_store → key: health_check_result")
    except Exception as e:  # conv: skip — health_check chạy độc lập
        print(f"\n  ⚠  Không ghi được vào kv_store: {e}", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(_b(f"\nVBSP-SCM Health Check  —  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"))
    print(f"DB   : {DB_PATH}")
    print(f"Root : {BASE_DIR}")

    check_database()
    check_kv_store()
    check_parquet()
    check_pgd_uploads()
    check_audit_log()

    exit_code = summary()
    _ghi_ket_qua_kv(exit_code)

    # Gửi kết quả health check qua Telegram
    try:
        from services.telegram_service import gui_ket_qua_health_check
        _passed = sum(1 for ok, _ in _results if ok)
        _failed = len(_results) - _passed
        _chi_tiet = "\n".join(f"✗ {lbl}" for ok, lbl in _results if not ok)
        gui_ket_qua_health_check(
            ok_count=_passed,
            warn_count=0,
            err_count=_failed,
            ngay=datetime.now().strftime("%d/%m/%Y %H:%M"),
            chi_tiet=_chi_tiet,
        )
        print("  ℹ  Đã gửi kết quả health check qua Telegram")
    except Exception as _tg_err:
        print(f"  ⚠  Telegram health check: {_tg_err}", file=sys.stderr)

    # Tự động tạo báo cáo sáng nếu chưa có hôm nay
    try:
        from services.daily_report_service import lay_bao_cao_sang_hom_nay, tao_bao_cao_sang
        if lay_bao_cao_sang_hom_nay() is None:
            path = tao_bao_cao_sang("health_check")
            print(f"\n  ✅  Báo cáo sáng: đã tạo {path.name} ({path.stat().st_size // 1024} KB)")
        else:
            print(f"\n  ℹ   Báo cáo sáng: đã có hôm nay — bỏ qua")
    except Exception as _bc_err:
        print(f"\n  ⚠   Báo cáo sáng: không tạo được — {_bc_err}", file=sys.stderr)

    sys.exit(exit_code)
