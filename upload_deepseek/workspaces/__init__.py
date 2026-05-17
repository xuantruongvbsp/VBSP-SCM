from __future__ import annotations

import importlib
from typing import Any

__all__ = ["ws_executive", "ws_management", "ws_operation"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        mod = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = mod
        return mod
    raise AttributeError(name)
