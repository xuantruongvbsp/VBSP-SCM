"""Regression tests cho so sánh Telegram với mốc đầu ngày."""
from __future__ import annotations

from services.telegram_delta import diff_deadline, diff_due_loans, diff_progress


def test_diff_deadline_chi_tra_pgd_thay_doi() -> None:
    baseline = {"Báo cáo A": {"missing": ["PGD A", "PGD B"]}}
    current = {"Báo cáo A": {"missing": ["PGD B", "PGD C"]}}

    changes = diff_deadline(baseline, current)

    assert changes == [{
        "name": "Báo cáo A",
        "submitted": ["PGD A"],
        "new_missing": ["PGD C"],
    }]


def test_diff_deadline_khong_doi_tra_rong() -> None:
    snapshot = {"Báo cáo A": {"missing": ["PGD A"]}}

    assert diff_deadline(snapshot, snapshot) == []


def test_diff_progress_nhan_dien_pgd_vua_hoan_thanh() -> None:
    baseline = {"PGD A": {"filled": 8, "total": 10}}
    current = {"PGD A": {"filled": 10, "total": 10}}

    changes = diff_progress(baseline, current)

    assert changes[0]["pgd"] == "PGD A"
    assert changes[0]["old"]["filled"] == 8
    assert changes[0]["new"]["filled"] == 10


def test_diff_due_loans_nhan_dien_khoan_moi_va_khong_con() -> None:
    added, removed, changed = diff_due_loans({"KU01": {}}, {"KU02": {}})

    assert added == ["KU02"]
    assert removed == ["KU01"]
    assert changed == []


def test_diff_due_loans_nhan_dien_du_no_thay_doi() -> None:
    added, removed, changed = diff_due_loans(
        {"KU01": {"du_no": 1_000_000}},
        {"KU01": {"du_no": 900_000}},
    )

    assert added == []
    assert removed == []
    assert changed == ["KU01"]
