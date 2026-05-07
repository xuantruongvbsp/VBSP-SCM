#!/usr/bin/env python3
"""
codebase_for_ai.py
──────────────────
Quét toàn bộ dự án → gộp code vào file Markdown duy nhất
dùng chung cho nhiều AI (DeepSeek, Claude, Gemini, Cursor, Windsurf, Trae).

Cách dùng:
    python codebase_for_ai.py
    python codebase_for_ai.py --dir /duong/dan/khac
"""

import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# ── Cấu hình ──────────────────────────────────────────────────────────────────

EXTENSIONS = {".py", ".js", ".html", ".css", ".json", ".yaml", ".yml", ".toml",
              ".txt", ".md"}

IGNORE_DIRS = {"venv", "env", "__pycache__", ".git", ".idea", "node_modules",
               "streamlit_cache", ".pytest_cache", "dist", "build",
               ".mypy_cache", ".ruff_cache", ".vscode", ".trae", ".vs"}

IGNORE_FILES = {"codebase_for_ai.md", "merged_codebase.txt", ".env", ".gitignore"}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB – bỏ qua file lớn hơn

LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".txt": "text",
}


def detect_language(ext: str) -> str:
    """Trả về tên ngôn ngữ cho markdown code block."""
    return LANG_MAP.get(ext, "text")


def should_ignore_dir(dir_name: str) -> bool:
    """Kiểm tra có nên bỏ qua thư mục không."""
    return dir_name in IGNORE_DIRS or dir_name.startswith(".")


def collect_files(root_dir: str) -> list[Path]:
    """Thu thập tất cả file hợp lệ theo cấu hình."""
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Lọc bỏ thư mục không cần thiết – thao tác trực tiếp trên list
        dirnames[:] = [d for d in dirnames if not should_ignore_dir(d)]
        # Sắp xếp cho nhất quán
        dirnames.sort()

        for fname in sorted(filenames):
            if fname in IGNORE_FILES:
                continue
            fp = Path(dirpath) / fname
            ext = fp.suffix.lower()
            if ext not in EXTENSIONS:
                continue
            if fp.stat().st_size > MAX_FILE_SIZE:
                print(f"  ⚠️  Bỏ qua (quá lớn): {fp}")
                continue
            files.append(fp)
    return files


def build_tree(root_dir: str, prefix: str = "") -> list[str]:
    """Tạo cây thư mục dạng tree (dùng iterdir đệ quy)."""
    lines: list[str] = []
    root = Path(root_dir).resolve()
    entries: list[Path] = sorted(
        [p for p in root.iterdir() if not p.name.startswith(".")],
        key=lambda x: (not x.is_dir(), x.name.lower()),
    )
    # Lọc bỏ thư mục không cần
    entries = [p for p in entries if not (p.is_dir() and should_ignore_dir(p.name))]

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if is_last else "│   "
            sub_tree = build_tree(str(entry), prefix + extension)
            lines.extend(sub_tree)
    return lines


def read_file_safe(filepath: Path) -> str:
    """Đọc file với fallback encoding."""
    try:
        return filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return filepath.read_text(encoding="latin-1")
        except Exception:
            return f"[Không thể đọc file: {filepath.name}]"


def generate_codebase(root_dir: str, output_file: str = "codebase_for_ai.md") -> str:
    """
    Quét thư mục root_dir, gộp code vào file Markdown.
    Trả về đường dẫn file output.
    """
    root = Path(root_dir).resolve()
    print(f"\n{'='*60}")
    print(f"  📁 Codebase: {root.name}")
    print(f"  📍 Thư mục: {root}")
    print(f"{'='*60}\n")

    # Bước 1: Thu thập file
    print("🔍 Đang quét file...")
    files = collect_files(str(root))
    print(f"  ✅ Tìm thấy {len(files)} file hợp lệ.\n")

    # Bước 2: Tạo cây thư mục
    print("🌳 Đang tạo cây thư mục...")
    tree_lines = build_tree(str(root))

    # Bước 3: Ghi file output
    print(f"  📝 Đang ghi {output_file}...")
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_size = 0

    with open(output_file, "w", encoding="utf-8") as out:
        # Header
        out.write(f"# 📁 Codebase: {root.name}\n\n")
        out.write(f"**Generated:** {generated_time}\n\n")
        out.write("---\n\n")
        out.write("## 📑 Cấu trúc dự án\n\n")
        out.write("```\n")
        out.write(f"{root.name}/\n")
        for line in tree_lines:
            out.write(line + "\n")
        out.write("```\n\n")
        out.write("---\n\n")
        out.write("## 📄 Nội dung chi tiết\n\n")

        # Nội dung từng file
        for idx, fp in enumerate(files, 1):
            try:
                content = read_file_safe(fp)
                rel_path = fp.relative_to(root).as_posix()
                ext = fp.suffix.lower()
                lang = detect_language(ext)

                out.write(f"### 📄 `{rel_path}`\n\n")
                out.write(f"```{lang}\n")
                out.write(content.rstrip("\n") + "\n")
                out.write("```\n\n")
                out.write("---\n\n")

                total_size += len(content.encode("utf-8"))
                if idx % 50 == 0:
                    print(f"  ⏳ Đã xử lý {idx}/{len(files)} file...")

            except Exception as e:
                print(f"  ❌ Lỗi xử lý {fp.name}: {e}")

    # Bước 4: In tổng kết
    size_mb = total_size / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"  ✅ HOÀN TẤT!")
    print(f"  📄 File:        {output_file}")
    print(f"  📦 Số file:      {len(files)}")
    print(f"  💾 Dung lượng:   {size_mb:.2f} MB")
    print(f"{'='*60}\n")

    print("─" * 60)
    print("  📋 HƯỚNG DẪN SỬ DỤNG")
    print("─" * 60)
    print()
    print(f"  Copy toàn bộ nội dung file {output_file}")
    print("  và paste trực tiếp vào prompt của AI:")
    print()
    print(f"    DeepSeek / Claude / Gemini / ChatGPT")
    print(f"    Cursor  / Windsurf / Trae")
    print()
    print(f"  Hoặc dùng lệnh (trên macOS/Linux):")
    print(f"    cat {output_file} | pbcopy")
    print()
    print(f"  Trên Windows (PowerShell):")
    print(f"    Get-Content {output_file} | Set-Clipboard")
    print()
    print("─" * 60)

    return str(Path(output_file).resolve())


def main():
    parser = argparse.ArgumentParser(
        description="Gộp toàn bộ codebase vào file Markdown cho AI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ví dụ:\n"
            "  python codebase_for_ai.py\n"
            "  python codebase_for_ai.py --dir /path/to/project\n"
            "  python codebase_for_ai.py --output my_codebase.md\n"
        ),
    )
    parser.add_argument(
        "--dir", "-d",
        default=".",
        help="Thư mục dự án (mặc định: thư mục hiện tại)",
    )
    parser.add_argument(
        "--output", "-o",
        default="codebase_for_ai.md",
        help="Tên file output (mặc định: codebase_for_ai.md)",
    )
    args = parser.parse_args()

    start = time.time()
    generate_codebase(args.dir, args.output)
    elapsed = time.time() - start
    print(f"\n  ⏱  Thời gian: {elapsed:.2f}s\n")


if __name__ == "__main__":
    main()
