"""Regression tests cho rule-based Telegram scheduler."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import os
from zoneinfo import ZoneInfo

import pytest

from services import telegram_schedule_service as svc
from services.telegram_jobs import TelegramJobResult


TZ = ZoneInfo("Asia/Bangkok")


@pytest.fixture
def kv_store(monkeypatch):
    values: dict = {}
    audits: list[tuple] = []

    monkeypatch.setattr(svc.db, "doc_kv", lambda key, default=None: deepcopy(values.get(key, default)))

    def _ghi_kv(key, value, username="system", note=None):
        values[key] = deepcopy(value)

    monkeypatch.setattr(svc.db, "ghi_kv", _ghi_kv)
    monkeypatch.setattr(svc.db, "ghi_audit", lambda *args: audits.append(args))
    return values, audits


def _rule(**overrides):
    raw = {
        "id": "tg_rule_deadline_01",
        "name": "Nhắc deadline",
        "notify_key": "deadline_bc",
        "enabled": True,
        "mode": "daily",
        "times": ["08:00"],
        "weekdays": [],
        "timezone": "Asia/Bangkok",
        "grace_minutes": 10,
        "max_runs_per_day": 1,
        "max_attempts_per_slot": 1,
        "cooldown_minutes": 15,
    }
    raw.update(overrides)
    return svc.normalize_rule(raw)


def test_validate_reject_notify_key_khong_whitelist() -> None:
    with pytest.raises(ValueError, match="whitelist"):
        _rule(notify_key="os.system")


def test_validate_mvp_reject_interval() -> None:
    with pytest.raises(ValueError, match="daily/weekly"):
        _rule(mode="interval")


def test_validate_reject_delivery_mode_khong_ho_tro() -> None:
    with pytest.raises(ValueError, match="delivery_mode"):
        _rule(delivery_mode="delta_only")


def test_due_slot_daily_trong_grace_window() -> None:
    rule = _rule(times=["08:00", "14:00"], max_runs_per_day=2)

    slots = svc.due_slots(rule, datetime(2026, 7, 14, 8, 7, tzinfo=TZ))

    assert [slot["slot_id"] for slot in slots] == ["tg_rule_deadline_01:20260714:0800"]
    assert svc.due_slots(rule, datetime(2026, 7, 14, 8, 10, tzinfo=TZ)) == []


def test_due_slot_weekly_chi_dung_thu() -> None:
    rule = _rule(mode="weekly", weekdays=[0], times=["08:00"])

    assert svc.due_slots(rule, datetime(2026, 7, 13, 8, 5, tzinfo=TZ))
    assert svc.due_slots(rule, datetime(2026, 7, 14, 8, 5, tzinfo=TZ)) == []


def test_run_due_rules_claim_truoc_va_khong_gui_trung(monkeypatch, kv_store) -> None:
    values, audits = kv_store
    values[svc.RULES_KEY] = {
        "schema_version": 1,
        "enabled": True,
        "rules": [_rule()],
    }
    calls: list[str] = []
    monkeypatch.setattr(
        svc,
        "run_telegram_job",
        lambda key: calls.append(key) or TelegramJobResult(True, "OK", sent=1),
    )
    now = datetime(2026, 7, 14, 8, 5, tzinfo=TZ)

    first = svc.run_due_rules(now)
    second = svc.run_due_rules(now)

    assert len(first) == 1
    assert second == []
    assert calls == ["deadline_bc"]
    entry = values["telegram_schedule_runlog_20260714"]["tg_rule_deadline_01:20260714:0800"]
    assert entry["status"] == "success"
    assert entry["attempts"] == 1
    assert [item[1] for item in audits] == ["telegram_schedule_claim", "telegram_schedule_finish"]


def test_failed_slot_retry_sau_cooldown(monkeypatch, kv_store) -> None:
    values, _audits = kv_store
    rule = _rule(
        grace_minutes=20,
        max_attempts_per_slot=2,
        cooldown_minutes=5,
    )
    values[svc.RULES_KEY] = {"schema_version": 1, "enabled": True, "rules": [rule]}
    results = iter([
        TelegramJobResult(False, error="HTTP 500", failed=1),
        TelegramJobResult(True, "OK", sent=1),
    ])
    monkeypatch.setattr(svc, "run_telegram_job", lambda _key: next(results))

    assert svc.run_due_rules(datetime(2026, 7, 14, 8, 1, tzinfo=TZ))[0]["ok"] is False
    assert svc.run_due_rules(datetime(2026, 7, 14, 8, 4, tzinfo=TZ)) == []
    assert svc.run_due_rules(datetime(2026, 7, 14, 8, 6, tzinfo=TZ))[0]["ok"] is True
    entry = values["telegram_schedule_runlog_20260714"]["tg_rule_deadline_01:20260714:0800"]
    assert entry["status"] == "success"
    assert entry["attempts"] == 2


def test_scheduler_managed_chi_khi_global_va_rule_cung_bat(kv_store) -> None:
    values, _audits = kv_store
    values[svc.RULES_KEY] = {"schema_version": 1, "enabled": False, "rules": [_rule()]}
    assert svc.is_scheduler_managed("deadline_bc") is False

    values[svc.RULES_KEY]["enabled"] = True
    assert svc.is_scheduler_managed("deadline_bc") is True
    assert svc.is_scheduler_managed("nhap_lieu") is False


def test_toggle_notify_tat_thi_scheduler_khong_claim(monkeypatch, kv_store) -> None:
    values, _audits = kv_store
    values[svc.RULES_KEY] = {"schema_version": 1, "enabled": True, "rules": [_rule()]}
    values["telegram_notify_config"] = {"deadline_bc": False}
    runner = pytest.fail
    monkeypatch.setattr(svc, "run_telegram_job", runner)

    outcomes = svc.run_due_rules(datetime(2026, 7, 14, 8, 5, tzinfo=TZ))

    assert outcomes == []
    assert "telegram_schedule_runlog_20260714" not in values


def test_next_scheduled_run_bo_qua_rule_tat_va_chon_moc_gan_nhat(kv_store) -> None:
    values, _audits = kv_store
    values[svc.RULES_KEY] = {
        "schema_version": 1,
        "enabled": True,
        "rules": [
            _rule(id="tg_rule_disabled", enabled=False, times=["08:01"]),
            _rule(id="tg_rule_daily_02", times=["14:00"]),
            _rule(id="tg_rule_weekly_03", mode="weekly", weekdays=[0], times=["08:00"]),
        ],
    }

    next_run = svc.next_scheduled_run(now=datetime(2026, 7, 14, 8, 5, tzinfo=TZ))

    assert next_run == datetime(2026, 7, 14, 14, 0, tzinfo=TZ)


def test_run_rule_now_khong_claim_runlog(monkeypatch, kv_store) -> None:
    values, audits = kv_store
    values[svc.RULES_KEY] = {
        "schema_version": 1,
        "enabled": False,
        "rules": [_rule(enabled=False)],
    }
    monkeypatch.setattr(
        svc,
        "run_telegram_job",
        lambda key: TelegramJobResult(True, f"Đã chạy {key}", sent=2),
    )

    result = svc.run_rule_now("tg_rule_deadline_01", "admin_test")

    assert result.ok is True
    assert result.sent == 2
    assert "telegram_schedule_runlog_20260714" not in values
    assert audits[0][0:2] == ("admin_test", "telegram_schedule_test")


def test_scheduler_health_bao_ok_va_lay_lan_gui_thanh_cong(monkeypatch, kv_store, tmp_path) -> None:
    values, _audits = kv_store
    values[svc.RULES_KEY] = {
        "schema_version": 1,
        "enabled": True,
        "rules": [_rule(times=["14:00"])],
    }
    values["telegram_schedule_runlog_20260714"] = {
        "tg_rule_deadline_01:20260714:0800": {
            "status": "success",
            "updated_at": "2026-07-14T08:03:00+07:00",
        },
    }
    heartbeat_path = tmp_path / "telegram_scheduler.lock"
    heartbeat_path.touch()
    heartbeat_at = datetime(2026, 7, 14, 8, 1, tzinfo=TZ)
    os.utime(heartbeat_path, (heartbeat_at.timestamp(), heartbeat_at.timestamp()))
    monkeypatch.setattr(svc, "SCHEDULER_HEARTBEAT_PATH", heartbeat_path)

    health = svc.scheduler_health(datetime(2026, 7, 14, 8, 5, tzinfo=TZ))

    assert health["status"] == "ok"
    assert health["age_minutes"] == pytest.approx(4)
    assert health["last_success"] == datetime(2026, 7, 14, 8, 3, tzinfo=TZ)
    assert health["next_run"] == datetime(2026, 7, 14, 14, 0, tzinfo=TZ)


def test_scheduler_health_canh_bao_heartbeat_cu(monkeypatch, kv_store, tmp_path) -> None:
    values, _audits = kv_store
    values[svc.RULES_KEY] = {
        "schema_version": 1,
        "enabled": True,
        "rules": [_rule()],
    }
    heartbeat_path = tmp_path / "telegram_scheduler.lock"
    heartbeat_path.touch()
    heartbeat_at = datetime(2026, 7, 14, 7, 30, tzinfo=TZ)
    os.utime(heartbeat_path, (heartbeat_at.timestamp(), heartbeat_at.timestamp()))
    monkeypatch.setattr(svc, "SCHEDULER_HEARTBEAT_PATH", heartbeat_path)

    health = svc.scheduler_health(
        datetime(2026, 7, 14, 8, 0, tzinfo=TZ),
        stale_minutes=15,
    )

    assert health["status"] == "stale"
    assert health["age_minutes"] == pytest.approx(30)


def test_full_then_delta_dung_moc_trong_ngay_va_reset_ngay_moi(monkeypatch, kv_store) -> None:
    values, audits = kv_store
    rule = _rule(
        delivery_mode="full_then_delta",
        times=["08:00", "14:00"],
        max_runs_per_day=2,
    )
    values[svc.RULES_KEY] = {"schema_version": 1, "enabled": True, "rules": [rule]}
    baselines: list[dict | None] = []

    def _runner(_key, baseline=None):
        baselines.append(deepcopy(baseline))
        return TelegramJobResult(
            True,
            "OK",
            sent=1 if baseline is None else 0,
            snapshot={"PGD A": {"missing": True}},
        )

    monkeypatch.setattr(svc, "run_telegram_job", _runner)

    svc.run_due_rules(datetime(2026, 7, 14, 8, 5, tzinfo=TZ))
    svc.run_due_rules(datetime(2026, 7, 14, 14, 5, tzinfo=TZ))
    svc.run_due_rules(datetime(2026, 7, 15, 8, 5, tzinfo=TZ))

    assert baselines == [None, {"PGD A": {"missing": True}}, None]
    baseline_entry = values[f"telegram_schedule_baseline_{rule['id']}"]
    assert baseline_entry["snapshot"] == {"PGD A": {"missing": True}}
    assert baseline_entry["date_key"] == "20260715"
    assert [item[1] for item in audits].count("telegram_schedule_baseline") == 2
