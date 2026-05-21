"""Smoke tests: import all UI modules + call render() without crashing.

Depends on conftest.py which mocks `streamlit` as MagicMock.
Mỗi tab/service được test độc lập trong subTest để không fail toàn bộ.
"""
from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Danh sách các module UI cần smoke test
# ---------------------------------------------------------------------------

TAB_MODULES: list[str] = [
    "tabs.tab_audit_log",
    "tabs.tab_ban_dai_dien",
    "tabs.tab_baocao",
    "tabs.tab_candoi",
    "tabs.tab_canh_bao_som",
    "tabs.tab_cbtd",
    "tabs.tab_cdtotkvv",
    "tabs.tab_cdtotkvv_pgd",
    "tabs.tab_checklist_bc",
    "tabs.tab_danhsach",
    "tabs.tab_den_han",
    "tabs.tab_diem_gd_pgd",
    "tabs.tab_gqvl",
    "tabs.tab_hhi",
    "tabs.tab_kehoach",
    "tabs.tab_kh_gqvl",
    "tabs.tab_khnv_noi_bo",
    "tabs.tab_khtd",
    "tabs.tab_khtd_giao_dc",
    "tabs.tab_khtd_mau07",
    "tabs.tab_khtd_nhap",
    "tabs.tab_khtd_pgd",
    "tabs.tab_khtd_xuat",
    "tabs.tab_kiem_soat",
    "tabs.tab_nhiem_vu",
    "tabs.tab_no_khoanh",
    "tabs.tab_no_rui_ro",
    "tabs.tab_nq11",
    "tabs.tab_phoi_hop_pgd",
    "tabs.tab_qd62",
    "tabs.tab_qlnk_dashboard",
    "tabs.tab_quan_ly_bc",
    "tabs.tab_quan_ly_cv",
    "tabs.tab_quan_ly_dgd",
    "tabs.tab_so_sanh_2_ky",
    "tabs.tab_so_sanh_ky",
    "tabs.tab_tien_do",
    "tabs.tab_tien_do_nop",
    "tabs.tab_tongquan",
    "tabs.tab_tracuu",
    "tabs.tab_trang_thai_nguon",
    "tabs.tab_upload_khnv",
    "tabs.tab_upload_pgd",
    "tabs.tab_uy_thac",
    "tabs.tab_xlrr_tong_hop",
]

WIDGET_MODULES: list[str] = [
    "widgets.data_source_status",
    "widgets.status_widget",
]

WORKSPACE_MODULES: list[str] = [
    "workspaces.ws_executive",
    "workspaces.ws_management",
    "workspaces.ws_operation",
]

SERVICE_MODULES: list[str] = [
    "services.upload_service",
    "services.uy_thac_service",
    "services.tien_do_service",
    "services.tongquan_service",
    "services.report_service",
]

RENDER_MODULES: list[str] = [
    *TAB_MODULES,
    *WIDGET_MODULES,
    *WORKSPACE_MODULES,
]

ALL_MODULES = [*RENDER_MODULES, *SERVICE_MODULES]

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, force=True)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import(module_name: str) -> object:
    """Import a module, return None on failure."""
    try:
        return importlib.import_module(module_name)
    except Exception as e:
        raise ImportError(f"Không import được {module_name}: {e}")


def _module_has(mod: object, name: str) -> bool:
    return hasattr(mod, name) and callable(getattr(mod, name))


def _try_render(mod: object, module_name: str, monkeypatch: pytest.MonkeyPatch, render_kwargs: dict[str, Any]) -> str | None:
    """Call render() and return error message or None."""
    # Monkeypatch các hàm db/pandas có thể fail
    monkeypatch.setattr("db.doc_kv", lambda key, default=None: default)
    monkeypatch.setattr("db.doc_kv_prefix", lambda prefix: {})
    monkeypatch.setattr("db.ghi_kv", lambda key, value, username: None)
    monkeypatch.setattr("db.ghi_audit", lambda username, action, desc: None)

    import streamlit as st
    st.session_state = {"username": "tester", "role": "admin_cn"}
    st.cache_data = type("Cache", (), {"clear": lambda: None})()

    try:
        render_kwargs.setdefault("role", "admin_cn")
        render_kwargs.setdefault("username", "tester")
        render_kwargs.setdefault("pgd_user", "PGD A")
        render_kwargs.setdefault("df", pd.DataFrame())
        render_kwargs.setdefault("df_full", pd.DataFrame())

        if _module_has(mod, "render"):
            import inspect
            sig = inspect.signature(mod.render)
            params = list(sig.parameters.keys())

            args: list = []
            call_kwargs: dict = {}

            if params and params[0] == "tab":
                param = sig.parameters["tab"]
                if param.default is inspect.Parameter.empty:
                    args.append(st.container())
                else:
                    args.append(None)

            # Check second param
            if len(params) > 1:
                second = params[1]
                param = sig.parameters[second]
                if second in ("role", "mode", "cap") and param.default is inspect.Parameter.empty:
                    if second == "cap":
                        args.append("xa")
                    elif second == "mode":
                        args.append("cn")
                    elif second == "role":
                        args.append("admin_cn")

            # Remaining kwargs
            for key, val in render_kwargs.items():
                if key in params:
                    call_kwargs[key] = val

            mod.render(*args, **call_kwargs)
            return None

        # Special: render_nhap_cn / render_nhap_pgd
        if _module_has(mod, "render_nhap_cn"):
            mod.render_nhap_cn(role="admin_cn", username="tester", df_full=pd.DataFrame(), df_gqvl=pd.DataFrame())

        if _module_has(mod, "render_nhap_pgd"):
            mod.render_nhap_pgd(role="user_pgd", username="tester", df_full=pd.DataFrame())

        return None

    except Exception as e:
        logger.debug("Lỗi render %s: %s", module_name, e, exc_info=True)
        return f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSmokeImports:
    """Import tất cả module UI, không crash."""

    @pytest.mark.parametrize("module_name", ALL_MODULES)
    def test_import(self, module_name: str) -> None:
        _import(module_name)


class TestSmokeRender:
    """Gọi render() / render_nhap_*() cho tất cả tab, không crash."""

    @pytest.mark.parametrize("module_name", RENDER_MODULES)
    def test_render(self, module_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _import(module_name)
        err = _try_render(mod, module_name, monkeypatch, {})
        if err:
            pytest.fail(f"{module_name}.render() thất bại: {err}")
