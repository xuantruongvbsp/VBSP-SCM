"""
Quản lý State tập trung cho VBSP-SCM.
────────────────────────────────────
Thay thế st.session_state rải rác bằng accessor chuẩn:
  state = SCMStateManager()
  state.filter_pgd = "PGD A"    # tự động reset filter_xa
  state.downloads.set("bc_ct", data, "BC.xlsx")
  state.temp.get("my_key")
"""

import copy
from typing import Any, Optional

import streamlit as st


# ── Singleton ───────────────────────────────────────────────────────
_instance: Optional["SCMStateManager"] = None


def get_instance() -> "SCMStateManager":
    """Trả về instance duy nhất trong phiên làm việc."""
    global _instance
    if _instance is None:
        _instance = SCMStateManager()
    return _instance


# ── Namespace proxies (stateless — an toàn với hot-reload) ────────────────

class _DownloadNamespace:
    """Quản lý bytes + filename cho download buttons.

    state.downloads.set("bc_ct", pdf_bytes, "BC_2026.pdf")
    if state.downloads.has("bc_ct"):
        st.download_button(..., data=state.downloads.get_bytes("bc_ct"), ...)
    """
    _NS = "_scm_downloads"

    def set(self, key: str, data: bytes, filename: str) -> None:
        if self._NS not in st.session_state:
            st.session_state[self._NS] = {}
        st.session_state[self._NS][key] = {"bytes": data, "filename": filename}

    def has(self, key: str) -> bool:
        store = st.session_state.get(self._NS, {})
        item = store.get(key)
        return item is not None and item.get("bytes") is not None

    def get_bytes(self, key: str) -> Optional[bytes]:
        item = st.session_state.get(self._NS, {}).get(key)
        return item["bytes"] if item else None

    def get_filename(self, key: str) -> Optional[str]:
        item = st.session_state.get(self._NS, {}).get(key)
        return item["filename"] if item else None

    def clear(self, key: str) -> None:
        store = st.session_state.get(self._NS, {})
        store.pop(key, None)

    def clear_all(self) -> None:
        st.session_state[self._NS] = {}


class _TempNamespace:
    """Vùng nhớ tạm — lưu state tạm giữa các component.

    state.temp.set("edit_mode", True)
    mode = state.temp.get("edit_mode", False)
    old = state.temp.pop("temp_key")
    """
    _NS = "_scm_temp"

    def get(self, key: str, default: Any = None) -> Any:
        return st.session_state.get(self._NS, {}).get(key, default)

    def set(self, key: str, value: Any) -> None:
        if self._NS not in st.session_state:
            st.session_state[self._NS] = {}
        st.session_state[self._NS][key] = value

    def pop(self, key: str, default: Any = None) -> Any:
        return st.session_state.get(self._NS, {}).pop(key, default)

    def clear_all(self) -> None:
        st.session_state[self._NS] = {}


class _CacheNamespace:
    """Cache dữ liệu tính toán nặng (không dùng st.cache_data được).

    state.cache.set("top_10_pgd", df_result)
    df_result = state.cache.get("top_10_pgd")
    """
    _NS = "_scm_cache"

    def get(self, key: str, default: Any = None) -> Any:
        return st.session_state.get(self._NS, {}).get(key, default)

    def set(self, key: str, value: Any) -> None:
        if self._NS not in st.session_state:
            st.session_state[self._NS] = {}
        st.session_state[self._NS][key] = value

    def clear(self, key: str) -> None:
        store = st.session_state.get(self._NS, {})
        store.pop(key, None)

    def clear_all(self) -> None:
        st.session_state[self._NS] = {}


# ── Main State Manager ───────────────────────────────────────────────────────

class SCMStateManager:
    """
    Proxy trung tâm quản lý State cho VBSP-SCM.

    - Khởi tạo nhẹ (không check/ghi session_state trong __init__)
    - Gọi ``SCMStateManager.ensure_initialized()`` một lần ở app.py
    - Typed property cho domain quan trọng: filters, navigation, workspace
    - Generic namespace cho pattern phổ biến: downloads, temp, cache
    - An toàn với hot-reload (lưu dict thuần, không lưu class instance)

    Usage::

        state = SCMStateManager()

        # Filters (auto-reset xã khi đổi PGD)
        state.filter_pgd = "PGD Long Thành"
        xa = state.filter_xa

        # Navigation (one-shot jump)
        state.nav_ws_mgmt_jump = "Chi tiết dư nợ"

        # Generic downloads
        state.downloads.set("bc_ct", pdf_bytes, "BC_2026.pdf")
        if state.downloads.has("bc_ct"):
            st.download_button(..., data=state.downloads.get_bytes("bc_ct"), ...)

        # Generic temp
        state.temp.set("edit_mode", True)
        mode = state.temp.get("edit_mode")
    """

    # ── Sub-namespace objects ──────────────────────────────────────
    downloads: _DownloadNamespace
    temp: _TempNamespace
    cache: _CacheNamespace

    def __init__(self):
        """Lightweight — chỉ gán namespace proxy. Không đụng session_state."""
        self.downloads = _DownloadNamespace()
        self.temp = _TempNamespace()
        self.cache = _CacheNamespace()

    # ── Static: Lazy Initialization ─────────────────────────────────

    @staticmethod
    def ensure_initialized() -> None:
        """
        Khởi tạo tất cả namespace một lần duy nhất.
        Gọi ở đầu ``app.py::main()`` trước khi làm bất kỳ việc gì.
        """
        _DEFAULTS: dict[str, dict] = {
            "_scm_filters": {
                "pgd": None,
                "xa": None,
                "chuong_trinh": None,
            },
            "_scm_navigation": {
                "ws_mgmt_menu": "",
                "ws_mgmt_jump": None,
                "ws_op_nhom": "",
                "ws_op_jump_tab": None,
            },
            "_scm_downloads": {},
            "_scm_temp": {},
            "_scm_cache": {},
        }
        for ns, default in _DEFAULTS.items():
            if ns not in st.session_state:
                st.session_state[ns] = copy.deepcopy(default)

    def _filters_ns(self) -> dict:
        return st.session_state.setdefault(
            "_scm_filters",
            {"pgd": None, "xa": None, "chuong_trinh": None},
        )

    def _nav_ns(self) -> dict:
        return st.session_state.setdefault(
            "_scm_navigation",
            {"ws_mgmt_menu": "", "ws_mgmt_jump": None, "ws_op_nhom": "", "ws_op_jump_tab": None},
        )

    # ── Domain: Filters (typed properties) ────────────────────────────

    @property
    def filter_pgd(self) -> Optional[str]:
        return self._filters_ns().get("pgd")

    @filter_pgd.setter
    def filter_pgd(self, value: Optional[str]) -> None:
        ns = self._filters_ns()
        if ns.get("pgd") != value:
            ns["pgd"] = value
            ns["xa"] = None

    @property
    def filter_xa(self) -> Optional[str]:
        return self._filters_ns().get("xa")

    @filter_xa.setter
    def filter_xa(self, value: Optional[str]) -> None:
        self._filters_ns()["xa"] = value

    @property
    def filter_chuong_trinh(self) -> Optional[str]:
        return self._filters_ns().get("chuong_trinh")

    @filter_chuong_trinh.setter
    def filter_chuong_trinh(self, value: Optional[str]) -> None:
        self._filters_ns()["chuong_trinh"] = value

    # ── Domain: Navigation (typed properties) ────────────────────────

    @property
    def nav_ws_mgmt_menu(self) -> str:
        return self._nav_ns().get("ws_mgmt_menu", "")

    @nav_ws_mgmt_menu.setter
    def nav_ws_mgmt_menu(self, value: str) -> None:
        self._nav_ns()["ws_mgmt_menu"] = value

    @property
    def nav_ws_mgmt_jump(self) -> Optional[str]:
        """One-shot jump — pop sau khi đọc, tránh lặp khi rerun."""
        return self._nav_ns().pop("ws_mgmt_jump", None)

    @nav_ws_mgmt_jump.setter
    def nav_ws_mgmt_jump(self, value: Optional[str]) -> None:
        self._nav_ns()["ws_mgmt_jump"] = value

    @property
    def nav_ws_op_nhom(self) -> str:
        return self._nav_ns().get("ws_op_nhom", "")

    @nav_ws_op_nhom.setter
    def nav_ws_op_nhom(self, value: str) -> None:
        self._nav_ns()["ws_op_nhom"] = value

    @property
    def nav_ws_op_jump_tab(self) -> Optional[int]:
        """One-shot jump tab — pop sau khi đọc."""
        return self._nav_ns().pop("ws_op_jump_tab", None)

    @nav_ws_op_jump_tab.setter
    def nav_ws_op_jump_tab(self, value: Optional[int]) -> None:
        self._nav_ns()["ws_op_jump_tab"] = value

    @property
    def nav_ws_op_menu(self) -> str:
        return self._nav_ns().get("ws_op_menu", "")

    @nav_ws_op_menu.setter
    def nav_ws_op_menu(self, value: str) -> None:
        self._nav_ns()["ws_op_menu"] = value

    # ── Domain: Workspace ────────────────────────────────────────
    # Giữ nguyên attribute style của Streamlit để backward-compatible

    @property
    def workspace(self) -> Optional[str]:
        return st.session_state.get("workspace")

    @workspace.setter
    def workspace(self, value: str) -> None:
        st.session_state.workspace = value

    # ── Domain: Auth (read-only convenience) ────────────────────────

    @property
    def username(self) -> str:
        return st.session_state.get("username", "")

    @property
    def role(self) -> str:
        return st.session_state.get("role", "user")

    # ── Debug & Maintenance ────────────────────────────────────

    @staticmethod
    def debug_dump() -> dict:
        """Trả về toàn bộ state VBSP-SCM dưới dạng dict sạch (debug)."""
        result = {}
        for k, v in st.session_state.items():
            if k.startswith("_scm_"):
                try:
                    result[k] = copy.deepcopy(v)
                except Exception:
                    result[k] = f"<{type(v).__name__}>"
        return result

    @staticmethod
    def clear_temp() -> None:
        """Xoá toàn bộ temp state — gọi khi chuyển workspace."""
        st.session_state["_scm_temp"] = {}
