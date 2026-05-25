"""Các module báo cáo chi tiết."""
from __future__ import annotations

# v1 - Báo cáo cơ bản
from .tong_hop_hstd import render_tong_hop_hstd
from .no_rui_ro import render_no_rui_ro
from .nq11 import render_nq11
from .gqvl import render_gqvl
from .cdtotkvv import render_cdtotkvv

# v2 - UX nâng cao
from .tong_hop_hstd_v2 import render_tong_hop_hstd_v2
from .no_rui_ro_v2 import render_no_rui_ro_v2

__all__ = [
    # v1
    "render_tong_hop_hstd",
    "render_no_rui_ro",
    "render_nq11",
    "render_gqvl",
    "render_cdtotkvv",
    # v2
    "render_tong_hop_hstd_v2",
    "render_no_rui_ro_v2",
]
