"""Check hardcoded column names in staged Python files.

Pre-commit hook script — reads COT_* constants from config.py,
scans staged .py files for hardcoded Vietnamese column name strings
that should use COT_* constants instead.

Usage:
    python scripts/check_hardcode_cols.py [list_of_files...]

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


def check_files(file_paths: list[str], cot_map: dict[str, str]) -> list[str]:
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
            if stripped.startswith('"""'):
                in_docstring = not in_docstring
                if stripped.endswith('"""') and len(stripped) > 6:
                    in_docstring = False
                continue
            if '"""' in stripped:
                in_docstring = not in_docstring
                continue
            if stripped.startswith("'"):
                continue
            if in_docstring:
                continue
            if "COT_" in stripped:
                continue
            if _is_exempt(line):
                continue

            for m in search_re.finditer(stripped):
                col_name = m.group(1)
                cot_name = cot_map.get(col_name, "???")
                if _is_display_context(stripped):
                    continue
                violation = f"  {fp}:{li}: hardcoded \"{col_name}\" — use {cot_name}"
                violations.append(violation)
                break

    return violations


def main() -> int:
    args = sys.argv[1:]
    if args:
        file_paths = [p for p in args if p.endswith(".py")]
    else:
        file_paths = _get_staged_files()

    if not file_paths:
        return 0

    cot_map = _compute_cot_map()
    violations = check_files(file_paths, cot_map)

    if violations:
        print("❌ HARDCODE COLUMN NAMES DETECTED:")
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
