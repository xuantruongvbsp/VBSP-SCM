"""Rule engine cho Telegram scheduler, lưu cấu hình và runlog bằng kv_store."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import db
from logger import get_logger
from services.telegram_jobs import run_telegram_job, telegram_job_keys

logger = get_logger(__name__)

RULES_KEY = "telegram_schedule_rules"
RUNLOG_PREFIX = "telegram_schedule_runlog_"
BASELINE_PREFIX = "telegram_schedule_baseline_"
SCHEMA_VERSION = 1
DEFAULT_TIMEZONE = "Asia/Bangkok"
SCHEDULER_HEARTBEAT_PATH = Path(__file__).resolve().parent.parent / "cache" / "telegram_scheduler.lock"
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_RULE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")


def default_schedule_config() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "enabled": False, "rules": []}


def doc_schedule_config() -> dict[str, Any]:
    raw = db.doc_kv(RULES_KEY)
    if not isinstance(raw, dict):
        return default_schedule_config()
    try:
        return validate_schedule_config(raw)
    except ValueError as e:
        logger.error("telegram_schedule_rules không hợp lệ: %s", e)
        return default_schedule_config()


def _new_rule_id() -> str:
    return f"tg_{uuid.uuid4().hex[:16]}"


def normalize_rule(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Mỗi rule phải là object.")
    rule_id = str(raw.get("id") or _new_rule_id()).strip()
    if not _RULE_ID_RE.fullmatch(rule_id):
        raise ValueError(f"Rule ID không hợp lệ: {rule_id}")
    notify_key = str(raw.get("notify_key") or "").strip()
    if notify_key not in telegram_job_keys():
        raise ValueError(f"notify_key chưa được whitelist: {notify_key}")
    mode = str(raw.get("mode") or "daily").strip().lower()
    if mode not in {"daily", "weekly"}:
        raise ValueError("MVP chỉ hỗ trợ mode daily/weekly.")
    delivery_mode = str(raw.get("delivery_mode") or "full_each_time").strip().lower()
    if delivery_mode not in {"full_each_time", "full_then_delta"}:
        raise ValueError("delivery_mode phải là full_each_time/full_then_delta.")
    times = sorted({str(x).strip() for x in raw.get("times", []) if str(x).strip()})
    if not times or any(not _TIME_RE.fullmatch(x) for x in times):
        raise ValueError(f"Rule {rule_id} phải có giờ HH:MM hợp lệ.")
    weekdays = sorted({int(x) for x in raw.get("weekdays", [])})
    if any(x < 0 or x > 6 for x in weekdays):
        raise ValueError(f"Rule {rule_id} có weekday ngoài 0..6.")
    if mode == "weekly" and not weekdays:
        raise ValueError(f"Rule weekly {rule_id} phải chọn ít nhất một thứ.")
    timezone = str(raw.get("timezone") or DEFAULT_TIMEZONE).strip()
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as e:
        raise ValueError(f"Timezone không hợp lệ: {timezone}") from e

    def _bounded(name: str, default: int, minimum: int, maximum: int) -> int:
        value = int(raw.get(name, default))
        if value < minimum or value > maximum:
            raise ValueError(f"{name} phải trong khoảng {minimum}..{maximum}.")
        return value

    return {
        "id": rule_id,
        "name": str(raw.get("name") or notify_key).strip()[:100],
        "notify_key": notify_key,
        "enabled": bool(raw.get("enabled", True)),
        "mode": mode,
        "delivery_mode": delivery_mode,
        "times": times,
        "weekdays": weekdays,
        "timezone": timezone,
        "grace_minutes": _bounded("grace_minutes", 10, 1, 60),
        "max_runs_per_day": _bounded("max_runs_per_day", len(times), 1, 20),
        "max_attempts_per_slot": _bounded("max_attempts_per_slot", 1, 1, 3),
        "cooldown_minutes": _bounded("cooldown_minutes", 15, 0, 1440),
    }


def validate_schedule_config(raw: dict[str, Any]) -> dict[str, Any]:
    if int(raw.get("schema_version", SCHEMA_VERSION)) != SCHEMA_VERSION:
        raise ValueError("schema_version Telegram scheduler chưa được hỗ trợ.")
    rules_raw = raw.get("rules", [])
    if not isinstance(rules_raw, list) or len(rules_raw) > 50:
        raise ValueError("rules phải là list tối đa 50 phần tử.")
    rules = [normalize_rule(item) for item in rules_raw]
    ids = [item["id"] for item in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("Rule ID bị trùng.")
    return {"schema_version": SCHEMA_VERSION, "enabled": bool(raw.get("enabled", False)), "rules": rules}


def luu_schedule_config(raw: dict[str, Any], username: str) -> dict[str, Any]:
    cfg = validate_schedule_config(raw)
    db.ghi_kv(RULES_KEY, cfg, username)
    if db.doc_kv(RULES_KEY) != cfg:
        raise RuntimeError("Không xác nhận được dữ liệu telegram_schedule_rules sau khi lưu.")
    db.ghi_audit(username, "telegram_schedule_rules", f"Lưu {len(cfg['rules'])} rule; enabled={cfg['enabled']}")
    return cfg


def is_scheduler_managed(notify_key: str) -> bool:
    cfg = doc_schedule_config()
    return bool(cfg["enabled"] and any(
        rule["enabled"] and rule["notify_key"] == notify_key for rule in cfg["rules"]
    ))


def run_rule_now(rule_id: str, username: str):
    """Chạy thử một rule, không claim slot và không tính giới hạn lịch."""
    cfg = doc_schedule_config()
    rule = next((item for item in cfg["rules"] if item["id"] == rule_id), None)
    if rule is None:
        raise ValueError("Không tìm thấy rule Telegram.")
    if not _notify_enabled(rule["notify_key"]):
        raise ValueError("Loại thông báo này đang tắt ở tab Thông báo.")
    result = run_telegram_job(rule["notify_key"])
    db.ghi_audit(
        username,
        "telegram_schedule_test",
        f"rule={rule_id}; key={rule['notify_key']}; ok={result.ok}; sent={result.sent}",
    )
    return result


def _notify_enabled(notify_key: str) -> bool:
    cfg = db.doc_kv("telegram_notify_config") or {}
    return bool(cfg.get(notify_key, True))


def _local_now(rule: dict[str, Any], now: datetime | None) -> datetime:
    tz = ZoneInfo(rule["timezone"])
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def next_scheduled_run(
    cfg: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """Tính lần chạy kế tiếp của các rule đang bật, tối đa 8 ngày tới."""
    config = cfg or doc_schedule_config()
    if not config["enabled"]:
        return None
    current = now or datetime.now(ZoneInfo(DEFAULT_TIMEZONE))
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
    candidates: list[datetime] = []
    for rule in config["rules"]:
        if not rule["enabled"] or not _notify_enabled(rule["notify_key"]):
            continue
        local_now = current.astimezone(ZoneInfo(rule["timezone"]))
        for day_offset in range(8):
            target_day = local_now + timedelta(days=day_offset)
            if rule["mode"] == "weekly" and target_day.weekday() not in rule["weekdays"]:
                continue
            for hhmm in rule["times"]:
                hour, minute = map(int, hhmm.split(":"))
                candidate = target_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate > local_now:
                    candidates.append(candidate.astimezone(ZoneInfo(DEFAULT_TIMEZONE)))
    return min(candidates) if candidates else None


def scheduler_health(now: datetime | None = None, stale_minutes: int = 15) -> dict[str, Any]:
    """Trạng thái heartbeat, lần gửi thành công và lần chạy kế tiếp."""
    current = now or datetime.now(ZoneInfo(DEFAULT_TIMEZONE))
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
    cfg = doc_schedule_config()
    heartbeat: datetime | None = None
    if SCHEDULER_HEARTBEAT_PATH.exists():
        heartbeat = datetime.fromtimestamp(
            SCHEDULER_HEARTBEAT_PATH.stat().st_mtime,
            tz=ZoneInfo(DEFAULT_TIMEZONE),
        )
    age_minutes = None if heartbeat is None else max(0.0, (current - heartbeat).total_seconds() / 60)
    if not cfg["enabled"]:
        status = "disabled"
    elif heartbeat is None:
        status = "never"
    elif age_minutes is not None and age_minutes > stale_minutes:
        status = "stale"
    else:
        status = "ok"

    last_success: datetime | None = None
    for offset in range(14):
        date_key = (current - timedelta(days=offset)).strftime("%Y%m%d")
        for entry in _doc_runlog(date_key).values():
            if entry.get("status") != "success":
                continue
            try:
                updated = datetime.fromisoformat(str(entry.get("updated_at")))
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
                if last_success is None or updated > last_success:
                    last_success = updated
            except (TypeError, ValueError):
                continue
    return {
        "status": status,
        "heartbeat": heartbeat,
        "age_minutes": age_minutes,
        "last_success": last_success,
        "next_run": next_scheduled_run(cfg, current),
    }


def due_slots(rule: dict[str, Any], now: datetime | None = None) -> list[dict[str, Any]]:
    """Trả các slot đến hạn trong grace window; slot_id ổn định theo ngày+giờ."""
    current = _local_now(rule, now)
    if not rule["enabled"]:
        return []
    if rule["mode"] == "weekly" and current.weekday() not in rule["weekdays"]:
        return []
    slots: list[dict[str, Any]] = []
    for hhmm in rule["times"]:
        hour, minute = map(int, hhmm.split(":"))
        scheduled_at = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_at <= current < scheduled_at + timedelta(minutes=rule["grace_minutes"]):
            slots.append({
                "slot_id": f"{rule['id']}:{current:%Y%m%d}:{hour:02d}{minute:02d}",
                "scheduled_at": scheduled_at.isoformat(),
                "date_key": current.strftime("%Y%m%d"),
            })
    return slots


def _runlog_key(date_key: str) -> str:
    return f"{RUNLOG_PREFIX}{date_key}"


def _doc_runlog(date_key: str) -> dict[str, Any]:
    raw = db.doc_kv(_runlog_key(date_key)) or {}
    return raw if isinstance(raw, dict) else {}


def _ghi_runlog(date_key: str, log: dict[str, Any], action: str, detail: str) -> None:
    key = _runlog_key(date_key)
    db.ghi_kv(key, log, "telegram_scheduler")
    if db.doc_kv(key) != log:
        raise RuntimeError(f"Không xác nhận được runlog {key} sau khi lưu.")
    db.ghi_audit("telegram_scheduler", action, detail)


def _can_claim(rule: dict[str, Any], slot: dict[str, Any], now: datetime) -> bool:
    log = _doc_runlog(slot["date_key"])
    same_rule = [x for x in log.values() if x.get("rule_id") == rule["id"]]
    unique_runs = {x.get("slot_id") for x in same_rule if x.get("status") in {"running", "success", "failed"}}
    entry = log.get(slot["slot_id"])
    if entry is None:
        return len(unique_runs) < rule["max_runs_per_day"]
    if entry.get("status") in {"running", "success"}:
        return False
    attempts = int(entry.get("attempts", 0))
    if attempts >= rule["max_attempts_per_slot"]:
        return False
    try:
        last_at = datetime.fromisoformat(str(entry.get("updated_at")))
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=now.tzinfo)
        if now < last_at + timedelta(minutes=rule["cooldown_minutes"]):
            return False
    except Exception:
        pass
    return True


def _claim(rule: dict[str, Any], slot: dict[str, Any], now: datetime) -> int:
    log = _doc_runlog(slot["date_key"])
    old = log.get(slot["slot_id"], {})
    attempts = int(old.get("attempts", 0)) + 1
    log[slot["slot_id"]] = {
        "slot_id": slot["slot_id"],
        "rule_id": rule["id"],
        "notify_key": rule["notify_key"],
        "scheduled_at": slot["scheduled_at"],
        "status": "running",
        "attempts": attempts,
        "updated_at": now.isoformat(),
    }
    _ghi_runlog(slot["date_key"], log, "telegram_schedule_claim", slot["slot_id"])
    return attempts


def _finish(rule: dict[str, Any], slot: dict[str, Any], now: datetime, attempts: int, result) -> None:
    log = _doc_runlog(slot["date_key"])
    log[slot["slot_id"]] = {
        "slot_id": slot["slot_id"],
        "rule_id": rule["id"],
        "notify_key": rule["notify_key"],
        "delivery_mode": rule["delivery_mode"],
        "scheduled_at": slot["scheduled_at"],
        "status": "success" if result.ok else "failed",
        "attempts": attempts,
        "sent": result.sent,
        "failed": result.failed,
        "info": result.info,
        "error": result.error,
        "updated_at": now.isoformat(),
    }
    _ghi_runlog(
        slot["date_key"], log, "telegram_schedule_finish",
        f"{slot['slot_id']} status={log[slot['slot_id']]['status']} sent={result.sent}",
    )


def _run_scheduled_job(rule: dict[str, Any], slot: dict[str, Any], now: datetime):
    """Chạy full hoặc delta; baseline luôn là bản đầu tiên thành công trong ngày."""
    if rule["delivery_mode"] != "full_then_delta":
        return run_telegram_job(rule["notify_key"])

    baseline_key = f"{BASELINE_PREFIX}{rule['id']}"
    baseline_entry = db.doc_kv(baseline_key) or {}
    baseline_matches = (
        isinstance(baseline_entry, dict)
        and baseline_entry.get("date_key") == slot["date_key"]
        and baseline_entry.get("notify_key") == rule["notify_key"]
        and isinstance(baseline_entry.get("snapshot"), dict)
    )
    if baseline_matches:
        return run_telegram_job(rule["notify_key"], baseline=baseline_entry["snapshot"])

    result = run_telegram_job(rule["notify_key"])
    if result.ok and isinstance(result.snapshot, dict):
        baseline_entry = {
            "rule_id": rule["id"],
            "notify_key": rule["notify_key"],
            "date_key": slot["date_key"],
            "created_at": now.isoformat(),
            "snapshot": result.snapshot,
        }
        db.ghi_kv(baseline_key, baseline_entry, "telegram_scheduler")
        if db.doc_kv(baseline_key) != baseline_entry:
            raise RuntimeError("Không xác nhận được baseline Telegram scheduler sau khi lưu.")
        db.ghi_audit(
            "telegram_scheduler",
            "telegram_schedule_baseline",
            f"rule={rule['id']}; date={slot['date_key']}",
        )
    return result


def run_due_rules(now: datetime | None = None) -> list[dict[str, Any]]:
    """Chạy các slot đến hạn. Caller phải bảo đảm chỉ một scheduler process giữ lock."""
    cfg = doc_schedule_config()
    if not cfg["enabled"]:
        return []
    outcomes: list[dict[str, Any]] = []
    for rule in cfg["rules"]:
        if not _notify_enabled(rule["notify_key"]):
            continue
        for slot in due_slots(rule, now):
            current = _local_now(rule, now)
            if not _can_claim(rule, slot, current):
                continue
            attempts = _claim(rule, slot, current)
            result = _run_scheduled_job(rule, slot, current)
            _finish(rule, slot, current, attempts, result)
            outcomes.append({
                "slot_id": slot["slot_id"], "notify_key": rule["notify_key"],
                "ok": result.ok, "sent": result.sent, "error": result.error,
            })
    return outcomes
