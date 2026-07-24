"""
scripts/gen_code_index.py
──────────────────────────
Tự sinh CODE_INDEX.md từ code thực tế.
Chạy: venv/Scripts/python.exe scripts/gen_code_index.py

Quét tabs/, services/, data/, components/, workspaces/ và root files
để extract hàm public → sinh bảng map chức năng → file → hàm.
"""
from __future__ import annotations

import ast
import re
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Nhóm file ──────────────────────────────────────────────────────────────
GROUPS = [
    ("Core (luôn cần đọc trước)", [
        "app.py", "auth.py", "config.py", "db.py", "utils.py",
        "snapshot_service.py",
    ]),
    ("Workspaces", ["workspaces/ws_executive.py", "workspaces/ws_management.py",
                     "workspaces/ws_operation.py"]),
    ("Data Layer", ["data/core.py", "data/hstd.py", "data/pgd.py",
                     "data/khtd.py", "data/cdotkvv.py", "data/den_han.py",
                     "data/giao_ban.py", "data/phan_ky_nxh.py"]),
    ("Components", ["components/delta_card.py", "components/export_pdf.py",
                     "components/filter_bar.py", "components/loan_drawer.py",
                     "components/movers.py"]),
]

# Thư mục quét tự động
SCAN_DIRS = ["services", "tabs"]

# File bỏ qua
SKIP = {"__init__.py", "__pycache__", "base_tab.py"}


def _parse_module(filepath: Path) -> ast.Module | None:
    """Parse module để sinh index; bỏ qua warning escape cũ trong docstring file được quét."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return ast.parse(source, filename=str(filepath))
    except Exception:
        return None


def extract_public_funcs(filepath: Path) -> list[str]:
    """Extract tên hàm public (không bắt đầu _) từ file Python."""
    tree = _parse_module(filepath)
    if tree is None:
        return []
    funcs = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                funcs.append(node.name)
    return funcs[:5]  # giới hạn 5 hàm/file cho gọn


def extract_docstring_header(filepath: Path) -> str:
    """Lấy dòng đầu của module docstring (nếu có)."""
    tree = _parse_module(filepath)
    if tree is None:
        return ""
    ds = ast.get_docstring(tree)
    if ds:
        first_line = ds.strip().split("\n")[0].strip()
        return first_line[:80]
    return ""


def scan_dir(dirname: str) -> list[tuple[str, str, list[str]]]:
    """Quét thư mục, trả về list (rel_path, docstring, [funcs])."""
    results = []
    d = ROOT / dirname
    if not d.is_dir():
        return results
    for f in sorted(d.glob("*.py")):
        if f.name in SKIP:
            continue
        funcs = extract_public_funcs(f)
        if funcs:
            ds = extract_docstring_header(f)
            results.append((f"{dirname}/{f.name}", ds, funcs))
    # Sub-packages
    for sub in sorted(d.iterdir()):
        if sub.is_dir() and not sub.name.startswith("_"):
            init = sub / "__init__.py"
            if init.exists():
                funcs = extract_public_funcs(init)
                ds = extract_docstring_header(init)
                if funcs:
                    results.append((f"{dirname}/{sub.name}/", ds, funcs))
    return results


def gen_section(title: str, files: list[str]) -> str:
    """Sinh section từ danh sách file cụ thể."""
    lines = [f"## {title}\n", "| File | Hàm chính |", "|---|---|"]
    for rel in files:
        fp = ROOT / rel
        if not fp.exists():
            continue
        funcs = extract_public_funcs(fp)
        if funcs:
            lines.append(f"| `{rel}` | {', '.join('`' + f + '()`' for f in funcs)} |")
    return "\n".join(lines) + "\n"


def gen_scan_section(title: str, dirname: str) -> str:
    """Sinh section từ quét thư mục."""
    items = scan_dir(dirname)
    if not items:
        return ""
    lines = [f"## {title}\n", "| File | Mô tả | Hàm chính |", "|---|---|---|"]
    for rel, ds, funcs in items:
        desc = ds if ds else "—"
        lines.append(f"| `{rel}` | {desc} | {', '.join('`' + f + '()`' for f in funcs)} |")
    return "\n".join(lines) + "\n"


def main():
    out = [
        "# CODE_INDEX — Tra nhanh file cần sửa",
        "",
        "> **TỰ SINH** bởi `scripts/gen_code_index.py`. Chạy lại sau khi thêm file mới.",
        "> Dành cho agent. Chỉ map chức năng → file → hàm.",
        "",
        "---",
        "",
    ]

    for title, files in GROUPS:
        out.append(gen_section(title, files))
        out.append("---\n")

    out.append(gen_scan_section("Services", "services"))
    out.append("---\n")
    out.append(gen_scan_section("Tabs", "tabs"))
    out.append("---\n")

    # Scripts
    scripts = scan_dir("scripts")
    if scripts:
        out.append("## Scripts\n")
        out.append("| File | Mô tả |")
        out.append("|---|---|")
        for rel, ds, _ in scripts:
            out.append(f"| `{rel}` | {ds or '—'} |")
        out.append("")

    content = "\n".join(out)
    target = ROOT / "CODE_INDEX.md"
    target.write_text(content, encoding="utf-8")
    print(f"✅ CODE_INDEX.md đã sinh ({len(content)} ký tự, {content.count(chr(10))} dòng)")


if __name__ == "__main__":
    main()
