"""Regression tests cho visibility module tích hợp trong Theo dõi nhập liệu."""
from __future__ import annotations

import pytest

from tabs.tab_theo_doi_nhap import (
    _selection_needs_reset,
    _visible_sheet_entries,
)
from tabs.tab_theo_doi_nhap.constants import BUILTIN_MODULES, KV_BUILTIN_VIS
from tabs.tab_theo_doi_nhap.data import (
    doc_builtin_visibility,
    luu_builtin_visibility,
)
from tabs.tab_theo_doi_nhap.ui_settings import (
    _BUILTIN_VIS_STATE_KEY,
    _can_manage_builtin,
    _sync_builtin_visibility_state,
)


def _all_visible() -> dict[str, bool]:
    return {module["id"]: True for module in BUILTIN_MODULES}


def test_doc_builtin_visibility_defaults_all_modules_to_true(monkeypatch) -> None:
    monkeypatch.setattr(
        "tabs.tab_theo_doi_nhap.data.db.doc_kv",
        lambda key: None,
    )

    assert doc_builtin_visibility() == _all_visible()


def test_luu_builtin_visibility_writes_kv_then_audit(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        "tabs.tab_theo_doi_nhap.data.db.ghi_kv",
        lambda *args: calls.append(("kv", *args)),
    )
    monkeypatch.setattr(
        "tabs.tab_theo_doi_nhap.data.db.ghi_audit",
        lambda *args: calls.append(("audit", *args)),
    )
    cfg = {**_all_visible(), "khao_sat": False}

    luu_builtin_visibility(cfg, "admin_test")

    assert calls == [
        ("kv", KV_BUILTIN_VIS, cfg, "admin_test"),
        ("audit", "admin_test", KV_BUILTIN_VIS, str(cfg)),
    ]


@pytest.mark.parametrize(
    ("selected", "previous_ids", "current_ids", "expected"),
    [
        (1, ("builtin:khao_sat", "sheet:0"), ("builtin:khao_sat", "sheet:0"), False),
        ("1", ("builtin:khao_sat", "sheet:0"), ("builtin:khao_sat", "sheet:0"), True),
        (-1, ("builtin:khao_sat", "sheet:0"), ("builtin:khao_sat", "sheet:0"), True),
        (2, ("builtin:khao_sat", "sheet:0"), ("builtin:khao_sat", "sheet:0"), True),
        (1, None, ("builtin:khao_sat", "sheet:0"), True),
        (1, ("builtin:khao_sat", "sheet:0"), ("builtin:dctt", "sheet:0"), True),
    ],
)
def test_selection_reset_tracks_option_identity(
    selected: object,
    previous_ids: object,
    current_ids: tuple[str, ...],
    expected: bool,
) -> None:
    assert _selection_needs_reset(selected, previous_ids, current_ids) is expected


def test_visibility_state_syncs_after_external_untrack() -> None:
    old_vis = _all_visible()
    state: dict[str, object] = {}
    _sync_builtin_visibility_state(old_vis, state)
    assert state["tdn_vis_khao_sat"] is True

    new_vis = {**old_vis, "khao_sat": False}
    _sync_builtin_visibility_state(new_vis, state)

    assert state["tdn_vis_khao_sat"] is False
    assert state[_BUILTIN_VIS_STATE_KEY] == tuple(
        (module["id"], new_vis[module["id"]])
        for module in BUILTIN_MODULES
    )


def test_visibility_state_preserves_unsaved_checkbox_change() -> None:
    persisted = _all_visible()
    state: dict[str, object] = {}
    _sync_builtin_visibility_state(persisted, state)
    state["tdn_vis_khao_sat"] = False

    _sync_builtin_visibility_state(persisted, state)

    assert state["tdn_vis_khao_sat"] is False


def test_visible_sheet_entries_default_to_enabled() -> None:
    sheets = [
        {"sheet_tab": "A"},
        {"sheet_tab": "B", "enabled": True},
    ]

    assert _visible_sheet_entries(sheets) == [
        (0, sheets[0]),
        (1, sheets[1]),
    ]


def test_visible_sheet_entries_exclude_disabled_and_keep_original_index() -> None:
    sheets = [
        {"sheet_tab": "Ẩn", "enabled": False},
        {"sheet_tab": "Hiện", "enabled": True},
    ]

    assert _visible_sheet_entries(sheets) == [(1, sheets[1])]


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin_cn", True),
        ("admin", True),
        ("manager_cn", False),
        ("manager", False),
        ("chuyenvien_cn", False),
        ("executive", False),
    ],
)
def test_only_admin_can_manage_builtin(role: str, expected: bool) -> None:
    assert _can_manage_builtin(role) is expected
