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

# 2. (Đã xóa) Rule /1e9 bị loại bỏ vì sai về toán:
_TIEN_SAI = re.compile(r'(?!x)x')  # pattern không bao giờ khớp

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

# 6. render() signature — thiếu tab=None default
# Cấm: def render(tab: DeltaGenerator, **kwargs)
# Cho phép: def render(tab=None, **kwargs) hoặc tab: DeltaGenerator | None = None
_RENDER_NO_NONE = re.compile(
    r'def render\(tab\s*:\s*DeltaGenerator(?!\s*\|\s*None)(?!\s*=\s*None)'
)

# 7. render() — tham số đầu tiên không phải tab
# Cấm: def render(role: str = None, ...
# Cấm: def render(mode: str, ...
_RENDER_FIRST_PARAM = re.compile(
    r'def render\((?:role|mode|cap)\s*:'
)

# 8. except Exception mà không có exc_info=True NGAY TRONG except block
# Kiểm tra dòng except và 3 dòng tiếp theo có exc_info=True không
_EXCEPT_EXC = re.compile(r'except\s+Exception\s+as\s+e\s*:')
_EXC_INFO   = re.compile(r'exc_info\s*=\s*True')

# 9. Thiếu logger import — file tabs/ có except Exception nhưng không import logger
_GET_LOGGER  = re.compile(r'get_logger\s*\(')
_FROM_LOGGER = re.compile(r'from\s+logger\s+import')

# 10. Hardcode màu nguy hiểm cho dark mode trong HTML/CSS inline (rule 8.16 + BUGMAP B15)
#   - Chữ TỐI cố định mà KHÔNG đặt nền cùng dòng  → chìm trên nền tối
#   - Nền SÁNG cố định mà KHÔNG đặt màu chữ cùng dòng → chữ theo theme sáng → chìm
# Dùng luminance để phân loại; cặp "nền sáng + chữ tối" (B15) được coi là HỢP LỆ.
_CSS_COLOR     = re.compile(r'(?<!-)\bcolor\s*:\s*([#a-zA-Z0-9]+)')
_CSS_BG        = re.compile(r'\bbackground(?:-color)?\s*:\s*([#a-zA-Z0-9]+)')
_NAMED_LUM     = {"black": 0.0, "white": 1.0}


def _luminance(token: str) -> float | None:
    """Độ sáng cảm nhận 0..1 của 1 màu CSS (#rgb/#rrggbb/black/white). None nếu không xác định."""
    t = token.strip().lower()
    if t in _NAMED_LUM:
        return _NAMED_LUM[t]
    if not t.startswith("#"):
        return None  # rgb()/rgba()/var()/biến f-string → bỏ qua (an toàn)
    hex_part = t[1:]
    if len(hex_part) == 3:
        hex_part = "".join(c * 2 for c in hex_part)
    if len(hex_part) != 6:
        return None
    try:
        r, g, b = (int(hex_part[k:k + 2], 16) for k in (0, 2, 4))
    except ValueError:
        return None
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _check_darkmode(line: str, neighborhood: str = "") -> str | None:
    """Trả về mô tả vi phạm dark mode nếu có, ngược lại None.

    `line`: dòng chứa literal màu (để báo đúng số dòng).
    `neighborhood`: vài dòng lân cận ghép lại — nhận diện cặp màu/nền bị tách
    qua nhiều dòng f-string (CSS Streamlit thường viết kiểu này).
    """
    ctx = neighborhood or line
    m_color = _CSS_COLOR.search(line)
    m_bg = _CSS_BG.search(line)
    co_bg_quanh = "background" in ctx              # nền có thể ở dòng f-string kề
    co_color_quanh = _CSS_COLOR.search(ctx) is not None

    if m_color:
        lum = _luminance(m_color.group(1))
        # Chữ tối cố định mà KHÔNG có khai báo nền nào quanh đó → chìm trên dark
        if lum is not None and lum < 0.45 and not co_bg_quanh:
            return ("chữ tối cố định không kèm nền — sẽ chìm trên dark mode; "
                    "dùng color:var(--text-color)")
    if m_bg:
        lum_bg = _luminance(m_bg.group(1))
        # Nền sáng cố định mà KHÔNG có khai báo màu chữ quanh đó → chữ theo theme sáng
        if lum_bg is not None and lum_bg > 0.75 and not co_color_quanh:
            return ("nền sáng cố định thiếu color chữ kèm theo — "
                    "thêm color tối cố định (cặp khóa, BUGMAP B15)")
    return None

# ── Các thư mục/file bỏ qua ─────────────────────────────────────────────────
_SKIP_DIRS  = {"_archive", ".git", "__pycache__", "node_modules",
               "khtd-targets-app", "tests", "scripts", "backups",
               "venv", ".venv", ".ruff_cache"}
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

        if _ROLE_HARDCODE.search(line) and "# conv: skip" not in line:
            loi.append(
                f"  Dòng {i:4d}: [ROLE] Hardcode role string — "
                f"dùng normalize_role() + la_phan_he_cn/pgd()\n"
                f"           → {stripped[:100]}"
            )

        if _COT_HARDCODE.search(line) and "# conv: skip" not in line:
            loi.append(
                f"  Dòng {i:4d}: [COT]  Hardcode tên cột — "
                f"dùng COT_* từ config.py\n"
                f"           → {stripped[:100]}"
            )

        if _SQLITE_DIRECT.search(line) and "db.py" not in str(path) and "# conv: skip" not in line:
            loi.append(
                f"  Dòng {i:4d}: [DB]   sqlite3.connect() trực tiếp — "
                f"dùng db.get_conn()\n"
                f"           → {stripped[:100]}"
            )

        if _RENDER_NO_NONE.search(line) and "# conv: skip" not in line:
            loi.append(
                f"  Dòng {i:4d}: [RENDER] render(tab: DeltaGenerator) thiếu = None — "
                f"thêm | None = None\n"
                f"           → {stripped[:100]}"
            )

        if _RENDER_FIRST_PARAM.search(line) and "# conv: skip" not in line:
            loi.append(
                f"  Dòng {i:4d}: [RENDER] Tham số đầu tiên của render() phải là tab — "
                f"dùng render(tab=None, **kwargs)\n"
                f"           → {stripped[:100]}"
            )

        if _EXCEPT_EXC.search(line) and "# conv: skip" not in line:
            # Kiểm tra 3 dòng tiếp theo có exc_info=True không
            co_exc_info = any(
                _EXC_INFO.search(lines[j - 1]) if j <= len(lines) else False
                for j in range(i + 1, min(i + 4, len(lines) + 1))
            )
            if not co_exc_info:
                loi.append(
                    f"  Dòng {i:4d}: [LOGGER] except Exception as e: — "
                    f"dùng logger.error(... , exc_info=True)\n"
                    f"           → {stripped[:100]}"
                )

        if "# conv: skip" not in line:
            _window = "\n".join(lines[max(0, i - 4): i + 3])
            _dm = _check_darkmode(line, _window)
            if _dm:
                loi.append(
                    f"  Dòng {i:4d}: [DARKMODE] {_dm}\n"
                    f"           → {stripped[:100]}"
                )

    # Kiểm tra ghi_kv không có ghi_audit (warn nhẹ)
    if _GHI_KV.search(content) and not _GHI_AUDIT.search(content):
        loi.append(
            f"  [AUDIT] File có ghi_kv() nhưng không có ghi_audit() — "
            f"kiểm tra lại audit log"
        )

    # Kiểm tra except Exception nhưng không có exc_info=True trong file
    is_tab_file = "tabs" in path.parts
    if is_tab_file and _EXCEPT_EXC.search(content) and not _EXC_INFO.search(content):
        loi.append(
            f"  [LOGGER] File có except Exception nhưng không có exc_info=True — "
            f"thêm logger.error(..., exc_info=True) để truy vết stacktrace"
        )

    # Kiểm tra except Exception nhưng thiếu import logger
    if is_tab_file and _EXCEPT_EXC.search(content):
        if not _GET_LOGGER.search(content) and not _FROM_LOGGER.search(content):
            loi.append(
                f"  [LOGGER] File có except Exception nhưng thiếu `from logger import get_logger` — "
                f"thêm import và dùng logger.error()"
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
