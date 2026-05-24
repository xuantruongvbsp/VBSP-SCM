"""So sánh số liệu giữa 2 kỳ — router chọn loại so sánh.

Tái cấu trúc: code logic nằm trong package tabs/tab_so_sanh_ky/.
File này giữ vai trò tương thích ngược cho các workspace gọi cũ.
"""
from __future__ import annotations

from streamlit.delta_generator import DeltaGenerator

from tabs.tab_so_sanh_ky import render as _package_render


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Entry point — delegate to package router."""
    _package_render(tab, **kwargs)
