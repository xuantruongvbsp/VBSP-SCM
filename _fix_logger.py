"""
Fix LOGGER convention across all tab/workspace/widget files.
Adds `from logger import get_logger` and `logger.error(..., exc_info=True)`
to all `except Exception` blocks.
"""
import re
import ast
from pathlib import Path

ROOT = Path(__file__).parent

# Files to scan (from check_conventions.py output showing violations)
FILES = [
    "tabs/tab_candoi.py",
    "tabs/tab_cdtotkvv.py",
    "tabs/tab_cdtotkvv_pgd.py",
    "tabs/tab_diem_gd_pgd.py",
    "tabs/tab_gqvl.py",
    "tabs/tab_kehoach.py",
    "tabs/tab_khtd.py",
    "tabs/tab_khtd_giao_dc.py",
    "tabs/tab_khtd_mau07.py",
    "tabs/tab_khtd_nhap.py",
    "tabs/tab_khtd_pgd.py",
    "tabs/tab_khtd_xuat.py",
    "tabs/tab_nhiem_vu.py",
    "tabs/tab_no_khoanh.py",
    "tabs/tab_qd62.py",
    "tabs/tab_quan_ly_dgd.py",
    "tabs/tab_tien_do.py",
    "tabs/tab_tien_do_nop.py",
    "tabs/tab_tongquan.py",
    "tabs/tab_trang_thai_nguon.py",
    "tabs/tab_upload_khnv.py",
    "tabs/tab_upload_pgd.py",
    "tabs/tab_uy_thac.py",
    "tabs/tab_audit_log.py",
    "tabs/tab_ban_dai_dien.py",
    "widgets/data_source_status.py",
    "workspaces/ws_executive.py",
    "workspaces/ws_management.py",
    "workspaces/ws_operation.py",
]


def has_logger_import(content: str) -> bool:
    return bool(re.search(r'from\s+logger\s+import', content)) or bool(re.search(r'get_logger\s*\(', content))


def add_logger_import(content: str) -> str:
    """Add `from logger import get_logger` and `logger = get_logger(__name__)` after last import."""
    lines = content.splitlines(keepends=True)
    last_import_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(('import ', 'from ')):
            last_import_idx = i
    
    if last_import_idx >= 0:
        # Find the end of import block (might have blank lines after)
        insert_idx = last_import_idx + 1
        while insert_idx < len(lines) and lines[insert_idx].strip() == '':
            insert_idx += 1
        
        indent = ''
        lines.insert(insert_idx, f'from logger import get_logger\n')
        lines.insert(insert_idx + 1, f'logger = get_logger(__name__)\n')
        lines.insert(insert_idx + 2, '\n')
    
    return ''.join(lines)


def fix_except_block(content: str) -> tuple[str, int]:
    """Fix `except Exception as e:` blocks by adding logger.error(... , exc_info=True)."""
    lines = content.splitlines(keepends=True)
    fixed_count = 0
    
    EXCEPT_PATTERN = re.compile(r'^(?P<indent>\s*)except\s+Exception(\s+as\s+(?P<var>\w+))?\s*:')
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('except Exception'):
            m = EXCEPT_PATTERN.match(line)
            if m and '# conv: skip' not in line:
                indent = m.group('indent')
                var_name = m.group('var') or 'e'
                
                # Check if already has logger.error in the following block
                has_logger = False
                j = i + 1
                next_indent = None
                while j < len(lines):
                    next_line = lines[j]
                    if next_line.strip() == '':
                        j += 1
                        continue
                    if next_indent is None:
                        next_indent = len(next_line) - len(next_line.lstrip())
                        next_indent_chars = next_line[:next_indent]
                    else:
                        curr_indent = len(next_line) - len(next_line.lstrip())
                        if curr_indent <= indent.count(' ') and next_line.strip():
                            break
                    
                    if 'logger.error' in next_line:
                        has_logger = True
                        break
                    j += 1
                
                if not has_logger:
                    # Add logger.error line after except
                    msg = f"Lỗi trong khối except: %s"
                    log_line = f"{indent}    logger.error(\"{msg}\", {var_name}, exc_info=True)\n"
                    lines.insert(i + 1, log_line)
                    fixed_count += 1
    
    return ''.join(lines), fixed_count


def process_file(filepath: Path) -> int:
    """Process a single file, return number of fixes."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  ❌ Cannot read: {e}")
        return 0
    
    original = content
    
    # Step 1: Add logger import if missing
    if not has_logger_import(content):
        content = add_logger_import(content)
    
    # Step 2: Fix except blocks
    content, fixed = fix_except_block(content)
    
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        print(f"  ✅ Fixed {fixed} except blocks + added import")
    else:
        print(f"  ⏭️  No changes needed")
    
    return fixed


def main():
    total_fixed = 0
    for rel_path in FILES:
        filepath = ROOT / rel_path
        if not filepath.exists():
            print(f"  ❌ Not found: {rel_path}")
            continue
        print(f"📄 {rel_path}")
        fixed = process_file(filepath)
        total_fixed += fixed
    
    print(f"\n{'='*50}")
    print(f"Total: {total_fixed} except blocks fixed across {len(FILES)} files")


if __name__ == '__main__':
    main()
