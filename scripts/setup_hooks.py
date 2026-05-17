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
# Kiem tra hardcoded column names truoc khi commit.
# Goi scripts/check_hardcode_cols.py de quet staged files.
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECKER="$PROJECT_ROOT/scripts/check_hardcode_cols.py"

if [ ! -f "$CHECKER" ]; then
    echo "[pre-commit] WARNING: $CHECKER not found, skipping hardcode check"
    exit 0
fi

python "$CHECKER" "$@"
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
fi

exit $exit_code
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
