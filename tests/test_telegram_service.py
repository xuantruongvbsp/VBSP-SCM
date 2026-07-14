"""Regression tests cho routing thông báo Telegram theo PGD."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from services import telegram_service as tg
from services.telegram_service import gui_thong_bao_upload_pgd as _gui_upload_pgd_goc


TEN_PGD = "PGD Long Thành"
SLUG_PGD = "pgd-long-thanh"


def _mock_config(monkeypatch, telegram_config: dict) -> None:
    """Mock config Telegram/notify mà không đụng SQLite thật."""
    data_pkg = ModuleType("data")
    data_pkg.__path__ = []
    pgd_module = ModuleType("data.pgd")
    pgd_module.pgd_slug = lambda _ten_pgd: SLUG_PGD
    monkeypatch.setitem(sys.modules, "data", data_pkg)
    monkeypatch.setitem(sys.modules, "data.pgd", pgd_module)

    def _doc_kv(key: str):
        if key == "telegram_config":
            return telegram_config
        if key == "telegram_notify_config":
            return {"upload_pgd": True}
        return None

    monkeypatch.setattr(tg.db, "doc_kv", _doc_kv)


@pytest.mark.parametrize(
    ("pgd_chats", "extra_chats", "expected_chat"),
    [
        ({SLUG_PGD: "CHAT_PGD"}, {"upload_pgd": "CHAT_EXTRA"}, "CHAT_PGD"),
        ({}, {"upload_pgd": "CHAT_EXTRA"}, "CHAT_EXTRA"),
        ({}, {}, "CHAT_MAIN"),
    ],
    ids=["uu_tien_chat_pgd", "fallback_chat_phu", "fallback_chat_chinh"],
)
def test_upload_pgd_routing_dung_thu_tu(
    monkeypatch,
    pgd_chats: dict,
    extra_chats: dict,
    expected_chat: str,
) -> None:
    """Upload PGD phải route: chat PGD → chat phụ upload_pgd → chat chính."""
    _mock_config(monkeypatch, {
        "token": "TOKEN_TEST",
        "chat_id": "CHAT_MAIN",
        "pgd_chats": pgd_chats,
        "extra_chats": extra_chats,
    })
    sender = Mock(return_value=(True, ""))
    ghi_log = Mock()
    monkeypatch.setattr(tg, "_gui_tin_core", sender)
    monkeypatch.setattr(tg, "_ghi_log", ghi_log)

    assert _gui_upload_pgd_goc(TEN_PGD, "hstd", "tester") is True

    assert sender.call_args.args[0:2] == ("TOKEN_TEST", expected_chat)
    assert sender.call_args.kwargs == {"parse_mode": "HTML"}
    assert ghi_log.call_args.args[0] == "upload_pgd"
    assert ghi_log.call_args.args[2] is True


def test_upload_pgd_gui_loi_ghi_dung_log_key(monkeypatch) -> None:
    """Lỗi gửi chat PGD phải còn tra được bằng notify_key upload_pgd ở tab Admin."""
    _mock_config(monkeypatch, {
        "token": "TOKEN_TEST",
        "chat_id": "CHAT_MAIN",
        "pgd_chats": {SLUG_PGD: "CHAT_PGD"},
        "extra_chats": {"upload_pgd": "CHAT_EXTRA"},
    })
    sender = Mock(return_value=(False, "HTTP 400: chat not found"))
    ghi_log = Mock()
    monkeypatch.setattr(tg, "_gui_tin_core", sender)
    monkeypatch.setattr(tg, "_ghi_log", ghi_log)

    assert _gui_upload_pgd_goc(TEN_PGD, "hstd", "tester") is False

    assert sender.call_args.args[1] == "CHAT_PGD"
    assert ghi_log.call_args.args[0] == "upload_pgd"
    assert ghi_log.call_args.args[2:] == (False, "HTTP 400: chat not found")
