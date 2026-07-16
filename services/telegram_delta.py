"""So sánh snapshot Telegram đầu ngày với dữ liệu hiện tại, không có I/O."""
from __future__ import annotations


def diff_deadline(baseline: dict, current: dict) -> list[dict]:
    """Các PGD đã nộp thêm hoặc mới phát sinh chưa nộp theo từng báo cáo."""
    changes = []
    for loai in sorted(set(baseline) | set(current)):
        old_missing = set(baseline.get(loai, {}).get("missing", []))
        new_missing = set(current.get(loai, {}).get("missing", []))
        submitted = sorted(old_missing - new_missing)
        new_missing_items = sorted(new_missing - old_missing)
        if submitted or new_missing_items:
            changes.append({
                "name": loai,
                "submitted": submitted,
                "new_missing": new_missing_items,
            })
    return changes


def diff_progress(baseline: dict, current: dict) -> list[dict]:
    """Các PGD có số chỉ tiêu đã nhập thay đổi so với đầu ngày."""
    changes = []
    for pgd in sorted(set(baseline) | set(current)):
        old = baseline.get(pgd, {"filled": 0, "total": 0})
        new = current.get(pgd, {"filled": 0, "total": 0})
        if old != new:
            changes.append({"pgd": pgd, "old": old, "new": new})
    return changes


def diff_due_loans(baseline: dict, current: dict) -> tuple[list[str], list[str], list[str]]:
    """ID khoản mới, không còn và có nội dung thay đổi so với đầu ngày."""
    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    changed = sorted(
        item_id for item_id in set(baseline) & set(current)
        if baseline[item_id] != current[item_id]
    )
    return added, removed, changed
