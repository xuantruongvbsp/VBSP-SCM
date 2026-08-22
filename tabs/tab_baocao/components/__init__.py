"""Components cho tab_baocao."""
from __future__ import annotations

# Components cơ bản
from .metric_cards import render_metric_cards
from .data_source_indicator import render_data_source_status
from .export_panel import render_export_panel

# Components UX nâng cao
from .skeleton_loader import render_skeleton_metrics, render_skeleton_table, render_skeleton_card
from .sticky_table import render_sticky_table, render_sortable_table, render_bang_chi_tiet_html
from .inline_filter import render_inline_filter, render_quick_search, render_combined_filter_search
from .quick_export import render_quick_export_buttons, render_bulk_export
from .tooltip import render_tooltip, render_header_with_tooltip, render_metric_with_tooltip, render_formula_reference
from .alert_suggestion import (
    check_alerts, get_suggestions, render_alert_card,
    render_alerts_panel, render_suggestions_panel, render_combined_alerts_suggestions
)

__all__ = [
    # Cơ bản
    "render_metric_cards",
    "render_data_source_status",
    "render_export_panel",
    # UX nâng cao
    "render_skeleton_metrics",
    "render_skeleton_table",
    "render_skeleton_card",
    "render_sticky_table",
    "render_sortable_table",
    "render_bang_chi_tiet_html",
    "render_inline_filter",
    "render_quick_search",
    "render_combined_filter_search",
    "render_quick_export_buttons",
    "render_bulk_export",
    "render_tooltip",
    "render_header_with_tooltip",
    "render_metric_with_tooltip",
    "render_formula_reference",
    "check_alerts",
    "get_suggestions",
    "render_alert_card",
    "render_alerts_panel",
    "render_suggestions_panel",
    "render_combined_alerts_suggestions",
]
