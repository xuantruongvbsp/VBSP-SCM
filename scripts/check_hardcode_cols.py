"""Check hardcoded column names in staged/changed Python files.

Pre-commit hook script — reads COT_* constants from config.py,
scans added/changed lines in staged .py files for hardcoded
Vietnamese column name strings that should use COT_* constants.

Usage:
    python scripts/check_hardcode_cols.py [--full] [list_of_files...]

    Default: checks only DIFF lines (git diff --cached).
    --full  : checks entire files (for manual audit).
    If no files given, reads from ``git diff --cached --name-only``.

Exit code 0 = clean, 1 = violations found.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_LINE_CONTEXT_EXEMPTIONS = (
    "noqa: COT",
    "ignore-cot",
)

_DISPLAY_KEYWORDS = (
    "st.metric",
    "st.selectbox",
    "st.radio",
    "st.multiselect",
    "st.text_input",
    "st.number_input",
    "st.slider",
    "st.button",
    "st.markdown",
    "st.write",
    "st.info",
    "st.success",
    "st.warning",
    "st.error",
    "st.caption",
    "st.header",
    "st.subheader",
    "st.title",
    "st.dataframe",
    "st.table",
    "st.expander",
    "st.sidebar",
    "st.columns",
    "st.container",
    "st.empty",
    "st.form_submit_button",
    "st.camera_input",
    "st.file_uploader",
    "st.checkbox",
    "st.toggle",
    "st.chat_input",
    "st.chat_message",
    "st.status",
    "st.toast",
    "st.balloons",
    "st.snow",
    "st.spinner",
    "help=",
    "label=",
    "placeholder=",
    "format_func=",
    "caption=",
    "body=",
    "icon=",
    "_ks_html_metric_card",
    "_ks_html_metric",
)


def _compute_cot_map() -> dict[str, str]:
    sys.path.insert(0, str(PROJECT_ROOT))
    import config
    sys.path.pop(0)
    cot_map: dict[str, str] = {}
    for name in dir(config):
        if name.startswith("COT_") and name.isupper():
            val = getattr(config, name)
            if isinstance(val, str) and len(val) > 2:
                if val not in cot_map:
                    cot_map[val] = name
    return cot_map


def _get_staged_files() -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=str(PROJECT_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [f.strip() for f in out.splitlines() if f.strip().endswith(".py")]


def _build_search_pattern(cot_map: dict[str, str]) -> re.Pattern:
    values = sorted(cot_map.keys(), key=len, reverse=True)
    escaped = [re.escape(v) for v in values]
    pattern = r'"(' + "|".join(escaped) + r')"'
    return re.compile(pattern)


def _is_exempt(line: str) -> bool:
    for marker in _LINE_CONTEXT_EXEMPTIONS:
        if marker in line:
            return True
    return False


def _is_display_context(line: str) -> bool:
    for kw in _DISPLAY_KEYWORDS:
        if kw in line:
            return True
    return False


def _parse_diff_added_lines(file_path: str) -> dict[int, str]:
    """Get {line_number: content} for lines added in staged diff."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "-U0", "--", file_path],
            cwd=str(PROJECT_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}

    added: dict[int, str] = {}
    current_new = 0

    for line in out.splitlines():
        if line.startswith("@@"):
            parts = line.split(" ")
            new_part = parts[2] if len(parts) >= 3 else ""
            if new_part.startswith("+"):
                num = new_part[1:].split(",")[0]
                current_new = int(num)
            continue

        if line.startswith("+") and not line.startswith("+++"):
            added[current_new] = line[1:]
            current_new += 1
        elif line.startswith("-"):
            pass
        elif line.startswith("\\"):
            pass
        else:
            current_new += 1

    return added


def _is_docstring_line(stripped: str) -> bool:
    return (
        stripped.startswith('"""')
        or stripped.endswith('"""')
        or '"""' in stripped
        or stripped.startswith("'")
    )


def _should_skip_line(stripped: str, line: str) -> bool:
    if not stripped:
        return True
    if stripped.startswith("#"):
        return True
    if stripped.startswith("import ") or stripped.startswith("from "):
        return True
    if "COT_" in stripped:
        return True
    if _is_exempt(line):
        return True
    if _is_docstring_line(stripped):
        return True
    if _is_display_context(stripped):
        return True
    return False


def check_diff(cot_map: dict[str, str]) -> list[str]:
    file_paths = _get_staged_files()
    if not file_paths:
        return []

    search_re = _build_search_pattern(cot_map)
    violations: list[str] = []

    for fp in file_paths:
        added_lines = _parse_diff_added_lines(fp)
        if not added_lines:
            continue

        for li, line_text in added_lines.items():
            stripped = line_text.strip()
            if _should_skip_line(stripped, line_text):
                continue

            for m in search_re.finditer(stripped):
                col_name = m.group(1)
                cot_name = cot_map.get(col_name, "???")
                violation = f"  {fp}:{li}: hardcoded \"{col_name}\" — use {cot_name}"
                violations.append(violation)
                break

    return violations


def check_full(file_paths: list[str], cot_map: dict[str, str]) -> list[str]:
    search_re = _build_search_pattern(cot_map)
    violations: list[str] = []

    for fp in file_paths:
        full_path = PROJECT_ROOT / fp
        if not full_path.is_file():
            continue
        try:
            lines = full_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        in_docstring = False
        for li, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("import ") or stripped.startswith("from "):
                continue
            if '"""' in stripped:
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if "COT_" in stripped:
                continue
            if _is_exempt(line):
                continue
            if _is_display_context(stripped):
                continue

            for m in search_re.finditer(stripped):
                col_name = m.group(1)
                cot_name = cot_map.get(col_name, "???")
                violation = f"  {fp}:{li}: hardcoded \"{col_name}\" — use {cot_name}"
                violations.append(violation)
                break

    return violations


def main() -> int:
    args = sys.argv[1:]
    use_full = "--full" in args
    file_args = [a for a in args if a != "--full" and a.endswith(".py")]

    if file_args:
        file_paths = file_args
    else:
        file_paths = _get_staged_files()

    if not file_paths:
        return 0

    cot_map = _compute_cot_map()

    if use_full:
        violations = check_full(file_paths, cot_map)
    else:
        violations = check_diff(cot_map)

    if violations:
        print("[HARDCODE VIOLATIONS]")
        print("-" * 62)
        for v in violations:
            print(v)
        print("-" * 62)
        print(f"  Found {len(violations)} violation(s).")
        print()
        print("  Fix: Replace the string with the COT_* constant from config.py.")
        print("  If this is intentional (display label), add  # noqa: COT")
        print()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
