"""Install/update Git hooks for VBSP-SCM project.

Copies hook templates from scripts/hooks/ to .git/hooks/.
Run once after cloning the repo or when hooks are updated.

Usage:
    python scripts/setup_hooks.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

HOOKS = {
    "pre-commit": """#!/bin/sh
# ============================================================
# VBSP-SCM Pre-commit Hook
# Kiem tra nhanh truoc khi commit:
# - py_compile (bat loi syntax)
# - check_hardcode_cols.py (hardcode COT_*)
# - check_conventions.py (role/render/logger/audit, v.v.)
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECK_COLS="$PROJECT_ROOT/scripts/check_hardcode_cols.py"
CHECK_CONV="$PROJECT_ROOT/scripts/check_conventions.py"

staged_py_files() {
    git diff --cached --name-only --diff-filter=ACM | grep -E '\\.py$' || true
}

run_py_compile() {
    files="$(staged_py_files)"
    if [ -z "$files" ]; then
        return 0
    fi
    python - <<'PY'
import os
import py_compile
import subprocess

out = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
    text=True,
    encoding="utf-8",
    errors="replace",
)
files = [f.strip() for f in out.splitlines() if f.strip().endswith(".py")]
for f in files:
    py_compile.compile(f, doraise=True)
print("[pre-commit] py_compile: OK")
PY
}

run_py_compile
exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo ""
    echo "============================================"
    echo "  COMMIT BLOCKED."
    echo "  Python syntax/compile error detected."
    echo "============================================"
    echo ""
    exit $exit_code
fi

if [ -f "$CHECK_COLS" ]; then
    python "$CHECK_COLS" "$@"
    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo "============================================"
        echo "  COMMIT BLOCKED."
        echo "  Hardcoded column names detected."
        echo "  Fix: use COT_* from config.py"
        echo "  Suppress: add  # noqa: COT"
        echo "============================================"
        echo ""
        exit $exit_code
    fi
else
    echo "[pre-commit] WARNING: $CHECK_COLS not found, skipping hardcode check"
fi

if [ -f "$CHECK_CONV" ]; then
    files="$(staged_py_files)"
    if [ -n "$files" ]; then
        python "$CHECK_CONV" $files
        exit_code=$?
        if [ $exit_code -ne 0 ]; then
            echo ""
            echo "============================================"
            echo "  COMMIT BLOCKED."
            echo "  Convention violations detected."
            echo "  Fix: follow VBSP-SCM rules (role/COT/audit/logger/render)."
            echo "  Suppress line: add  # conv: skip  (sparingly)"
            echo "============================================"
            echo ""
            exit $exit_code
        fi
    fi
else
    echo "[pre-commit] WARNING: $CHECK_CONV not found, skipping convention check"
fi

exit 0
""",
}


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    hooks_dir = project_root / ".git" / "hooks"

    if not hooks_dir.is_dir():
        print(f"ERROR: {hooks_dir} not found — is this a git repository?")
        raise SystemExit(1)

    for name, content in HOOKS.items():
        target = hooks_dir / name
        target.write_text(content, encoding="utf-8")
        target.chmod(0o755)
        print(f"  ✅ {name}")

    print()
    print("Git hooks installed successfully.")
    print("Run again after pulling updates to hooks.")


if __name__ == "__main__":
    main()
