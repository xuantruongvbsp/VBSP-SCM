"""So sánh số liệu giữa 2 kỳ — router chọn loại so sánh.

Tái cấu trúc: code logic nằm trong package tabs/tab_so_sanh_ky/.
File này giữ vai trò tương thích ngược cho các workspace gọi cũ.
"""
from __future__ import annotations

from streamlit.delta_generator import DeltaGenerator

from auth import normalize_role
from utils import get_tab_context

# Delegate to package
from tabs.tab_so_sanh_ky import render as _package_render
from tabs.tab_so_sanh_ky.render_moc_nam import render_moc_nam


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Entry point — delegate to package router."""
    _package_render(tab, **kwargs)
