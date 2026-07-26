"""Validate that direct requirements and the complete lockfile stay in sync."""
from __future__ import annotations

import re
import sys
from pathlib import Path


_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s;]+)$")


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _read_exact_pins(path: Path) -> tuple[dict[str, str], list[str]]:
    pins: dict[str, str] = {}
    errors: list[str] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PIN_RE.fullmatch(line)
        if match is None:
            errors.append(f"{path.name}:{line_number}: pin must use package==version")
            continue
        name, version = match.groups()
        normalized = _normalized_name(name)
        if normalized in pins:
            errors.append(f"{path.name}:{line_number}: duplicate package {name}")
            continue
        pins[normalized] = version
    return pins, errors


def validate_lock(direct_path: Path, lock_path: Path) -> list[str]:
    """Return validation errors; an empty list means the lock is consistent."""
    errors: list[str] = []
    for path in (direct_path, lock_path):
        if not path.is_file():
            errors.append(f"missing dependency file: {path}")
    if errors:
        return errors

    direct, direct_errors = _read_exact_pins(direct_path)
    locked, lock_errors = _read_exact_pins(lock_path)
    errors.extend(direct_errors)
    errors.extend(lock_errors)

    for name, version in direct.items():
        locked_version = locked.get(name)
        if locked_version is None:
            errors.append(f"{name}=={version} is missing from {lock_path.name}")
        elif locked_version != version:
            errors.append(
                f"{name} version mismatch: direct={version}, lock={locked_version}"
            )
    if len(locked) <= len(direct):
        errors.append("lockfile does not contain a transitive dependency closure")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: validate_dependency_lock.py DIRECT_REQUIREMENTS LOCKFILE")
        return 2

    errors = validate_lock(Path(args[0]), Path(args[1]))
    if errors:
        print("Dependency lock is invalid:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Dependency lock is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
