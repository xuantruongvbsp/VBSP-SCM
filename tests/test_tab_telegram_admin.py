"""Regression tests cho tabs/tab_telegram_admin.py."""
from __future__ import annotations

import pandas as pd

from tabs.tab_telegram_admin import (
    _TELEGRAM_LOG_FAIL_STYLE,
    _TELEGRAM_LOG_OK_STYLE,
    _highlight_log_result,
)


def test_highlight_log_result_khong_can_cot_ok() -> None:
    row = pd.Series({
        "Thời gian": "2026-08-03 08:00:00",
        "Loại": "deadline_bc",
        "Nội dung": "Nhắc báo cáo",
        "Kết quả": "✅ OK",
    })

    styles = _highlight_log_result(row)

    assert len(styles) == len(row)
    assert styles == ["", "", "", _TELEGRAM_LOG_OK_STYLE]


def test_highlight_log_result_to_mau_loi_theo_cot_ket_qua() -> None:
    row = pd.Series({
        "Thời gian": "2026-08-03 08:05:00",
        "Loại": "deadline_bc",
        "Nội dung": "Nhắc báo cáo",
        "Kết quả": "❌ timeout",
    })

    styles = _highlight_log_result(row)

    assert len(styles) == len(row)
    assert styles == ["", "", "", _TELEGRAM_LOG_FAIL_STYLE]
