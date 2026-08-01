"""Regression tests for DeltaCard layout and kwargs forwarding."""
from __future__ import annotations

from unittest.mock import MagicMock

from components import delta_card as delta_card_module


def _context_mock() -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__.return_value = ctx
    ctx.__exit__.return_value = False
    return ctx


def test_delta_card_giu_sub_trong_cung_container(monkeypatch):
    col_metric = _context_mock()
    col_help = _context_mock()
    card = _context_mock()
    metric = MagicMock()
    caption = MagicMock()

    monkeypatch.setattr(delta_card_module.st, "columns", lambda _spec: [col_metric, col_help])
    monkeypatch.setattr(delta_card_module.st, "container", MagicMock(return_value=card))
    monkeypatch.setattr(delta_card_module.st, "metric", metric)
    monkeypatch.setattr(delta_card_module.st, "caption", caption)

    delta_card_module.delta_card("Tổng dư nợ", 12.3, sub="Kỳ trước: 11,8 tỷ")

    delta_card_module.st.container.assert_called_once_with(border=True)
    assert metric.call_args.kwargs["border"] is False
    caption.assert_called_once_with("Kỳ trước: 11,8 tỷ")


def test_kpi_row_truyen_sub_qua_kwargs(monkeypatch):
    columns = [_context_mock(), _context_mock()]
    render_card = MagicMock()
    monkeypatch.setattr(delta_card_module.st, "columns", lambda _count: columns)
    monkeypatch.setattr(delta_card_module, "delta_card", render_card)

    delta_card_module.kpi_row(
        [{"label": "A", "value": 1, "sub": "Chi tiết"}],
        num_columns=2,
    )

    render_card.assert_called_once_with(label="A", value=1, sub="Chi tiết")
