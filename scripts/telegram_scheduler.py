#!/usr/bin/env python3
"""Chạy Telegram rule engine; được Windows Task Scheduler gọi mỗi 5 phút."""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from logger import get_logger
from services.telegram_schedule_service import SCHEDULER_HEARTBEAT_PATH, run_due_rules

logger = get_logger(__name__)
LOCK_PATH = SCHEDULER_HEARTBEAT_PATH


@contextmanager
def _single_instance_lock():
    """Khóa liên tiến trình trên Windows; lock file chỉ là coordination, không chứa dữ liệu."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_PATH, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.tell() == 0 and handle.read(1) == b"":
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                yield False
                return
        yield True
    finally:
        if os.name == "nt":
            try:
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        handle.close()


def main() -> int:
    with _single_instance_lock() as acquired:
        if not acquired:
            logger.info("Telegram scheduler đang chạy ở process khác; bỏ qua lượt này.")
            return 0
        os.utime(LOCK_PATH, None)
        outcomes = run_due_rules()
        for item in outcomes:
            logger.info(
                "Telegram slot=%s key=%s ok=%s sent=%s error=%s",
                item["slot_id"], item["notify_key"], item["ok"], item["sent"], item["error"],
            )
        return 0 if all(item["ok"] for item in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
