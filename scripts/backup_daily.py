#!/usr/bin/env python3
"""
backup_daily.py — Sao lưu tự động hàng ngày.

Gọi bởi:
  - Windows Task Scheduler (06:30 mỗi ngày)
  - Docker Compose profile=backup
  - Thủ công: python scripts/backup_daily.py

Kết quả:
  - Lưu vào backups/YYYYMMDD_HHMMSS/
  - Giữ tối đa 7 bản gần nhất
  - Ghi log vào logs/backup.log
  - Exit 0 nếu thành công, 1 nếu lỗi
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path
from datetime import datetime

# ── Thêm root vào sys.path để import backup_service ──────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── Logging ra file + stdout ──────────────────────────────────────
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "backup.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("backup_daily")


def main() -> int:
    log.info("=" * 60)
    log.info("VBSP-SCM — Backup tự động bắt đầu")
    log.info("=" * 60)

    try:
        from backup_service import chay_backup, don_backup
    except ImportError as e:
        log.error("Không import được backup_service: %s", e)
        return 1

    # ── Chạy backup ──────────────────────────────────────────────
    try:
        ket_qua = chay_backup()
        ky = ket_qua.get("ky", "unknown")
        db_ok = ket_qua.get("db_ok", False)
        n_parquet = ket_qua.get("parquet", 0)
        n_pgd = ket_qua.get("pgd_xlsx", 0)
        out_dir = ket_qua.get("out_dir", "")

        if db_ok:
            log.info("✅ DB backup OK")
        else:
            log.error("❌ DB backup THẤT BẠI")

        log.info("📦 Parquet cache: %d file", n_parquet)
        log.info("📁 PGD Excel:     %d file", n_pgd)
        log.info("📂 Thư mục:       %s", out_dir)

    except Exception as e:
        log.error("Lỗi khi chạy backup: %s", e, exc_info=True)
        return 1

    # ── Dọn bản cũ ───────────────────────────────────────────────
    try:
        don_backup()
        log.info("🧹 Dọn bản backup cũ xong")
    except Exception as e:
        log.warning("Không dọn được bản cũ: %s", e)

    if not db_ok:
        log.error("Backup hoàn thành nhưng DB gặp lỗi")
        return 1

    log.info("✅ Backup kỳ %s hoàn thành thành công", ky)
    return 0


if __name__ == "__main__":
    sys.exit(main())
