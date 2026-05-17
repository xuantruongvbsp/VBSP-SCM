"""
scripts/check_conventions.py
─────────────────────────────
Kiểm tra convention VBSP-SCM trên các file .py được staged.
Chạy tự động qua pre-commit hook.

Exit code 0 = pass, 1 = có vi phạm.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ── Các pattern cần kiểm tra ────────────────────────────────────────────────

# 1. Hardcode role string trực tiếp
# Cho phép: normalize_role(...), la_phan_he_cn(...), v.v.
# Cấm: role == "admin", role == "manager", role in ["admin", "user"]
_ROLE_HARDCODE = re.compile(
    r'\brole\s*[=!]=\s*["\'](?:admin|manager|user|admin_cn|manager_cn'
    r'|admin_pgd|manager_pgd|user_pgd|executive|chuyenvien_cn)["\']'
    r'|\brole\s+in\s+\[',
)

# 2. Chia tiền tệ sai đơn vị /1e9
# Cho phép: /1e6 (triệu), /1e12 (tỷ qua fmt_ty)
# Cấm: /1e9, / 1e9, /1_000_000_000
_TIEN_SAI = re.compile(
    r'/\s*1e9\b|/\s*1_000_000_000\b'
)

# 3. Hardcode tên cột tiếng Việt thay vì dùng COT_*
# Cấm: df["Tổng dư nợ"], df['Dư nợ quá hạn'], v.v.
_COT_HARDCODE = re.compile(
    r'(?:df|row|data)\s*\[\s*["\']'
    r'(?:Tổng dư nợ|Dư nợ quá hạn|Dư nợ trong hạn'
    r'|Mã KH|Số khế ước|Tên PGD|Tên chương trình'
    r'|Ngày số liệu|Ngày vay|Ngày ĐH theo Gia hạn'
    r'|Tình trạng món vay)["\']'
)

# 4. Ghi kv_store không có audit log trong cùng hàm/block
# Heuristic: ghi_kv có trong file nhưng không có ghi_audit
# (chỉ warn, không fail cứng)
_GHI_KV    = re.compile(r'\bghi_kv\s*\(')
_GHI_AUDIT = re.compile(r'\bghi_audit\s*\(')

# 5. Dùng sqlite3.connect trực tiếp thay vì db.get_conn()
_SQLITE_DIRECT = re.compile(
    r'sqlite3\.connect\s*\('
)

# ── Các thư mục/file bỏ qua ─────────────────────────────────────────────────
_SKIP_DIRS  = {"_archive", ".git", "__pycache__", "node_modules",
               "khtd-targets-app", "tests", "scripts"}
_SKIP_FILES = {"check_conventions.py", "backup_service.py"}


def _nen_kiem_tra(path: Path) -> bool:
    parts = set(path.parts)
    if parts & _SKIP_DIRS:
        return False
    if path.name in _SKIP_FILES:
        return False
    return path.suffix == ".py"


def kiem_tra_file(path: Path) -> list[str]:
    """Trả về danh sách lỗi tìm thấy trong file."""
    loi: list[str] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return [f"Không đọc được file: {e}"]

    lines = content.splitlines()

    for i, line in enumerate(lines, start=1):
        # Bỏ qua dòng comment
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        if _ROLE_HARDCODE.search(line):
            loi.append(
                f"  Dòng {i:4d}: [ROLE] Hardcode role string — "
                f"dùng normalize_role() + la_phan_he_cn/pgd()\n"
                f"           → {stripped[:100]}"
            )

        if _TIEN_SAI.search(line):
            loi.append(
                f"  Dòng {i:4d}: [TIEN] Dùng /1e9 cho tiền tệ — "
                f"phải dùng /1e12 qua fmt_ty()\n"
                f"           → {stripped[:100]}"
            )

        if _COT_HARDCODE.search(line):
            loi.append(
                f"  Dòng {i:4d}: [COT]  Hardcode tên cột — "
                f"dùng COT_* từ config.py\n"
                f"           → {stripped[:100]}"
            )

        if _SQLITE_DIRECT.search(line) and "db.py" not in str(path):
            loi.append(
                f"  Dòng {i:4d}: [DB]   sqlite3.connect() trực tiếp — "
                f"dùng db.get_conn()\n"
                f"           → {stripped[:100]}"
            )

    # Kiểm tra ghi_kv không có ghi_audit (warn nhẹ)
    if _GHI_KV.search(content) and not _GHI_AUDIT.search(content):
        loi.append(
            f"  [AUDIT] File có ghi_kv() nhưng không có ghi_audit() — "
            f"kiểm tra lại audit log"
        )

    return loi


def main(files: list[str] | None = None) -> int:
    """
    Kiểm tra danh sách file truyền vào (từ pre-commit)
    hoặc toàn bộ *.py trong project nếu chạy tay.
    """
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if files:
        paths = [Path(f) for f in files if Path(f).suffix == ".py"]
    else:
        # Chạy tay: quét toàn project
        root = Path(__file__).parent.parent
        paths = [p for p in root.rglob("*.py") if _nen_kiem_tra(p)]

    tong_loi = 0
    for path in sorted(paths):
        if not _nen_kiem_tra(path):
            continue
        loi = kiem_tra_file(path)
        if loi:
            print(f"\n❌ {path}")
            for msg in loi:
                print(msg)
            tong_loi += len(loi)

    if tong_loi == 0:
        print("✅ Tất cả convention OK")
        return 0
    else:
        print(f"\n{'─'*60}")
        print(f"❌ Tổng cộng {tong_loi} vi phạm convention")
        print(f"{'─'*60}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] if len(sys.argv) > 1 else None))
