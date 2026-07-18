"""Regression tests cho routing thông báo Telegram theo PGD + allowlist auto-clean."""
from __future__ import annotations

import sys
from datetime import datetime
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
import pandas as pd

from services import telegram_service as tg
from services.telegram_service import (
    gui_thong_bao_upload_pgd as _gui_upload_pgd_goc,
    doc_deadline_bc_allowlist,
    luu_deadline_bc_allowlist,
)
from config import COT_DU_NO_QH, COT_TEN_PGD


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


# ── Standard notification structure tests ─────────────────────────────────────

class TestChuanHoaThongBao:
    def test_hstd_uu_tien_ngay_so_lieu_merge_meta(self, monkeypatch) -> None:
        monkeypatch.setattr(
            tg.db,
            "doc_kv",
            lambda key: {"ngay_sl": "2026-06-30 00:00:00"}
            if key == "merge_meta_hstd" else None,
        )

        result = tg._chuan_hoa_thong_bao(
            "📊 <b>Báo cáo sáng 16/07/2026</b>\n\n💰 Dư nợ: <b>25.000 tỷ</b>",
            "bao_cao_sang",
        )

        assert "<b>Báo cáo tổng hợp sáng — Toàn Chi nhánh</b>" in result
        assert "<b>Ngày số liệu:</b> 30/06/2026" in result
        assert "<b>Tóm tắt:</b> 📊 Báo cáo sáng 16/07/2026" in result
        assert "💰 Dư nợ: <b>25.000 tỷ</b>" in result
        assert "<b>Nguồn dữ liệu:</b> HSTD" in result
        assert "<b>Cập nhật lúc:</b>" in result

    def test_gsheet_khong_nham_deadline_la_ngay_so_lieu(self, monkeypatch) -> None:
        monkeypatch.setattr(tg.db, "doc_kv", lambda _key: None)
        result = tg._chuan_hoa_thong_bao(
            "⚠️ <b>Nhắc nộp báo cáo</b>\n📅 Deadline: <b>31/12/2026</b>",
            "deadline_bc",
        )

        assert f"<b>Ngày số liệu:</b> {datetime.now():%d/%m/%Y}" in result
        assert "<b>Nguồn dữ liệu:</b> Google Sheets" in result

    def test_chuan_hoa_idempotent(self, monkeypatch) -> None:
        monkeypatch.setattr(tg.db, "doc_kv", lambda _key: None)
        once = tg._chuan_hoa_thong_bao("Tiêu đề\nChi tiết", "health_check")
        twice = tg._chuan_hoa_thong_bao(once, "health_check")
        assert twice == once

    def test_du_19_notify_key(self) -> None:
        assert len(tg._NOTIFY_PRESENTATION) == 19
        assert len(set(tg._NOTIFY_PRESENTATION)) == 19


class TestBaoCaoNqhTuan:
    def test_hien_thi_tang_giam_tong_va_tung_pgd(self, monkeypatch) -> None:
        sender = Mock(return_value=True)
        monkeypatch.setattr(tg, "_la_bat", lambda _key: True)
        monkeypatch.setattr(tg, "_gui_tin_for", sender)
        monkeypatch.setattr(
            tg,
            "_lay_moc_nqh_nam",
            lambda _ngay: ({"PGD A": 100_000_000.0, "PGD B": 50_000_000.0}, "31/12/2025"),
        )

        ok = tg.gui_bao_cao_nqh_tuan(
            [
                {"ten_pgd": "PGD A", "du_no": 12_883_400_000_000.0, "nqh": 120_000_000.0, "ty_le_nqh": 1.2},
                {"ten_pgd": "PGD B", "du_no": 20_000_000_000.0, "nqh": 40_000_000.0, "ty_le_nqh": 0.2},
            ],
            "18/07/2026",
        )

        assert ok is True
        text_gui = sender.call_args.args[0]
        assert "Tổng dư nợ CN: <b>12.903,4 tỷ</b>" in text_gui
        assert "Tổng NQH: <b>160 tr</b>" in text_gui
        assert "Tăng/giảm trong kỳ" in text_gui
        assert "🔺 +10 tr" in text_gui
        assert "PGD A: 120 tr (1,20%) · 🔺 +20 tr" in text_gui
        assert "PGD B: 40 tr (0,20%) · 🔻 -10 tr" in text_gui

    def test_lay_moc_baseline_3112_nam_truoc(self, monkeypatch) -> None:
        import data.hstd as hstd_data

        monkeypatch.setattr(hstd_data, "ts_baseline_merged", lambda _nam: 123.0)
        monkeypatch.setattr(
            hstd_data,
            "doc_baseline_merged",
            lambda nam, ts=0.0: pd.DataFrame([
                {COT_TEN_PGD: "PGD A", COT_DU_NO_QH: 10_000_000.0},
                {COT_TEN_PGD: "PGD A", COT_DU_NO_QH: 2_000_000.0},
                {COT_TEN_PGD: "PGD B", COT_DU_NO_QH: 5_000_000.0},
            ]) if nam == 2025 and ts == 123.0 else pd.DataFrame(),
        )

        nqh_moc, ngay_moc = tg._lay_moc_nqh_nam("18/07/2026")

        assert nqh_moc == {"PGD A": 12_000_000.0, "PGD B": 5_000_000.0}
        assert ngay_moc == "31/12/2025"


# ── Allowlist auto-clean tests ────────────────────────────────────────────────

class TestDocDeadlineBcAllowlist:
    def test_tra_ve_none_khi_chua_co_allowlist(self, monkeypatch):
        monkeypatch.setattr(tg.db, "doc_kv", lambda _key: None)
        assert doc_deadline_bc_allowlist() is None

    def test_tra_ve_none_khi_list_rong(self, monkeypatch):
        monkeypatch.setattr(tg.db, "doc_kv", lambda _key: [])
        assert doc_deadline_bc_allowlist() is None

    def test_loc_stale_khi_deadline_da_xoa(self, monkeypatch):
        monkeypatch.setattr(tg.db, "doc_kv", _make_stale_doc_kv({
            "telegram_deadline_bc_allowlist": ["BC A", "BC B", "BC C"],
            "bao_cao_deadline_config": {"BC A": "2026-07-15"},
        }))
        result = doc_deadline_bc_allowlist()
        assert result == ["BC A"]

    def test_loc_toan_bo_stale_tra_none(self, monkeypatch):
        monkeypatch.setattr(tg.db, "doc_kv", _make_stale_doc_kv({
            "telegram_deadline_bc_allowlist": ["BC X", "BC Y"],
            "bao_cao_deadline_config": {"BC A": "2026-07-15"},
        }))
        result = doc_deadline_bc_allowlist()
        assert result is None

    def test_khong_co_deadline_config_thi_giu_nguyen(self, monkeypatch):
        monkeypatch.setattr(tg.db, "doc_kv", _make_stale_doc_kv({
            "telegram_deadline_bc_allowlist": ["BC A", "BC B"],
            "bao_cao_deadline_config": {},
        }))
        result = doc_deadline_bc_allowlist()
        assert result == ["BC A", "BC B"]

    def test_allowlist_none_thi_khong_loc_stale(self, monkeypatch):
        monkeypatch.setattr(tg.db, "doc_kv", _make_stale_doc_kv({
            "telegram_deadline_bc_allowlist": None,
            "bao_cao_deadline_config": {"BC A": "2026-07-15"},
        }))
        assert doc_deadline_bc_allowlist() is None


class TestLuuDeadlineBcAllowlist:
    def test_luu_allowlist_bt_thuong(self, monkeypatch):
        store = _make_stale_store({"bao_cao_deadline_config": {"BC A": "2026-07-15", "BC B": "2026-08-01"}})
        monkeypatch.setattr(tg.db, "doc_kv", store.__getitem__)
        monkeypatch.setattr(tg.db, "ghi_kv", _ghi_store(store))
        monkeypatch.setattr(tg.db, "ghi_audit", Mock())

        luu_deadline_bc_allowlist(["BC A", "BC B"], "test_user")
        assert store["telegram_deadline_bc_allowlist"] == ["BC A", "BC B"]

    def test_luu_allowlist_tu_loc_stale(self, monkeypatch):
        store = _make_stale_store({"bao_cao_deadline_config": {"BC A": "2026-07-15"}})
        monkeypatch.setattr(tg.db, "doc_kv", store.__getitem__)
        monkeypatch.setattr(tg.db, "ghi_kv", _ghi_store(store))
        monkeypatch.setattr(tg.db, "ghi_audit", Mock())

        luu_deadline_bc_allowlist(["BC A", "BC Stale"], "test_user")
        assert store["telegram_deadline_bc_allowlist"] == ["BC A"]

    def test_luu_allowlist_rong_tra_ve_none(self, monkeypatch):
        monkeypatch.setattr(tg.db, "doc_kv", lambda _key: {})
        monkeypatch.setattr(tg.db, "ghi_kv", Mock())
        monkeypatch.setattr(tg.db, "ghi_audit", Mock())

        luu_deadline_bc_allowlist(None, "test_user")
        ghi_kv_args = tg.db.ghi_kv.call_args.args
        assert ghi_kv_args[1] is None

    def test_luu_allowlist_toan_bo_stale_thanh_none(self, monkeypatch):
        store = _make_stale_store({"bao_cao_deadline_config": {"BC A": "2026-07-15"}})
        monkeypatch.setattr(tg.db, "doc_kv", store.__getitem__)
        monkeypatch.setattr(tg.db, "ghi_kv", _ghi_store(store))
        monkeypatch.setattr(tg.db, "ghi_audit", Mock())

        luu_deadline_bc_allowlist(["BC Stale 1", "BC Stale 2"], "test_user")
        # Tất cả stale → trả về None
        assert store["telegram_deadline_bc_allowlist"] is None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_stale_doc_kv(values: dict):
    """Mock doc_kv trả về giá trị từ dict."""
    return lambda key: values.get(key)


def _make_stale_store(values: dict) -> dict:
    """Tạo dict store với ghi_kv ghi thật vào dict."""
    return dict(values)


def _ghi_store(store: dict):
    """Hàm ghi_kv mock: ghi trực tiếp vào store dict."""
    def _ghi(key, value, username):
        store[key] = value
    return _ghi
