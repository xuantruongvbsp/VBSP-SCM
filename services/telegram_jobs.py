"""Registry các job Telegram có thể chạy thủ công hoặc theo lịch."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TelegramJobResult:
    ok: bool
    info: str = ""
    sent: int = 0
    failed: int = 0
    error: str = ""
    snapshot: dict[str, Any] | None = None


def _run_deadline_bc(baseline: dict | None = None) -> TelegramJobResult:
    from scripts.nhac_deadline import run_deadline_bc_with_snapshot

    sent, pending, failed, error, snapshot = run_deadline_bc_with_snapshot(baseline)
    if failed:
        return TelegramJobResult(
            False,
            f"Đã gửi {sent}/{pending} loại báo cáo",
            sent,
            failed,
            error or "Gửi nhắc deadline thất bại.",
            snapshot,
        )
    empty_info = "Không có báo cáo cần nhắc" if baseline is None else "Không có thay đổi cần gửi"
    info = f"Đã gửi {sent} loại báo cáo" if sent else empty_info
    return TelegramJobResult(True, info, sent, 0, "", snapshot)


def _run_nhap_lieu(baseline: dict | None = None) -> TelegramJobResult:
    from scripts.nhac_deadline import run_nhap_lieu

    sent, pending, error, snapshot = run_nhap_lieu(baseline)
    if error and pending == 0:
        return TelegramJobResult(False, failed=1, error=error, snapshot=snapshot)
    failed = max(pending - sent, 0)
    if failed:
        return TelegramJobResult(
            False,
            f"Đã gửi {sent}/{pending} nhắc nhập liệu",
            sent,
            failed,
            error or "Gửi nhắc nhập liệu thất bại.",
            snapshot,
        )
    empty_info = "Không có sheet nhập liệu cần nhắc" if baseline is None else "Không có thay đổi cần gửi"
    info = f"Đã gửi {sent} nhắc nhập liệu" if sent else empty_info
    return TelegramJobResult(True, info, sent, 0, "", snapshot)


def _run_den_han_phan_tang(baseline: dict | None = None) -> TelegramJobResult:
    from scripts.nhac_deadline import run_den_han_phan_tang_with_snapshot

    ok, sent, total, error, snapshot = run_den_han_phan_tang_with_snapshot(baseline)
    if not ok:
        return TelegramJobResult(False, f"{total} khoản cần nhắc", sent, 1, error, snapshot)
    if sent:
        label = "thay đổi" if baseline is not None else "khoản"
        info = f"Đã gửi {total} {label} T-1/T-3/T-7"
    else:
        info = "Không có khoản đến hạn cần nhắc" if baseline is None else "Không có thay đổi cần gửi"
    return TelegramJobResult(True, info, sent, 0, "", snapshot)


_JOB_REGISTRY: dict[str, Callable[[dict | None], TelegramJobResult]] = {
    "deadline_bc": _run_deadline_bc,
    "nhap_lieu": _run_nhap_lieu,
    "den_han_phan_tang": _run_den_han_phan_tang,
}


def telegram_job_keys() -> tuple[str, ...]:
    return tuple(_JOB_REGISTRY)


def run_telegram_job(notify_key: str, baseline: dict | None = None) -> TelegramJobResult:
    """Chạy job từ whitelist; không nhận module/function tùy ý từ rule."""
    runner = _JOB_REGISTRY.get(str(notify_key or "").strip())
    if runner is None:
        return TelegramJobResult(False, error=f"Job Telegram không được hỗ trợ: {notify_key}")
    try:
        return runner(baseline)
    except Exception as e:
        logger.error("run_telegram_job(%s): %s", notify_key, e, exc_info=True)
        return TelegramJobResult(False, error=str(e))
