"""Base tab context — TabContext class dùng chung cho mọi tab render."""
from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from auth import normalize_role
from config import ROLES_PHAN_HE_CN


class TabContext:
    """Base context for all tab renders.

    Centralizes common kwargs extraction (role, username, pgd_user, df_full),
    role normalization, and tab container setup.

    Usage:
        def render(tab, **kwargs):
            ctx = TabContext(tab, **kwargs)
            with ctx:
                if ctx.is_exec: ...
                if ctx.is_pgd: ...
                if ctx.is_cn: ...
    """

    def __init__(self, tab, **kwargs):
        self.tab = tab
        self.role = kwargs.get("role", "")
        self.username = kwargs.get("username", "")
        self.pgd_user = kwargs.get("pgd_user", "")
        self.df_full = kwargs.get("df_full")

        self._role_n: Optional[str] = None
        self._container: Any = None

    @property
    def container(self):
        if self._container is None:
            self._container = self.tab if self.tab is not None else st.container()
        return self._container

    def __enter__(self):
        return self.container.__enter__()

    def __exit__(self, *args):
        return self.container.__exit__(*args)

    @property
    def role_norm(self) -> str:
        if self._role_n is None:
            self._role_n = normalize_role(str(self.role or "user"))
        return self._role_n

    @property
    def is_cn(self) -> bool:
        return self.role_norm in ROLES_PHAN_HE_CN and self.role_norm != "executive"

    @property
    def is_exec(self) -> bool:
        return self.role_norm == "executive"

    @property
    def is_pgd(self) -> bool:
        return self.role_norm not in ROLES_PHAN_HE_CN and bool(self.pgd_user)
