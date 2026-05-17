"""Simple check for remaining hardcoded column names in Priority 1 files"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Column names that should use COT_ constants (sorted longest first for greedy matching)
COLUMN_NAMES = [
    "Tổng dư nợ", "Dư nợ trong hạn", "Dư nợ quá hạn", "Tên chương trình",
    "Tên ĐVUT", "Tên tổ", "Tên xã", "Tên thôn",
    "Số điện thoại", "Địa chỉ", "Nguồn vốn",
    "Mã KH", "Tên KH", "Số khế ước",
    "Ngày vay", "Ngày ĐH", "Thời hạn vay", "Lãi suất",
    "Mức vay", "Tình trạng món vay",
    "Dư nợ khoanh", "Lãi tồn TH", "Lãi tồn QH",
    "Ngày số liệu", "Gốc đã trả",
    "Số CMND", "Phân loại",
    "Ngày giao dịch gần nhất",
]

files = [
    r'd:\VBSP-SCM\tabs\tab_baocao.py',
    r'd:\VBSP-SCM\tabs\tab_danhsach.py',
    r'd:\VBSP-SCM\tabs\tab_khtd_mau07.py',
    r'd:\VBSP-SCM\tabs\tab_so_sanh_ky.py',
]

total = 0
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f'\n=== {filepath.split(chr(92))[-1]} ===')
    found = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments and imports
        if stripped.startswith('#') or stripped.startswith('import') or stripped.startswith('from'):
            continue
        # Skip lines that already use COT_ (likely already fixed)
        if 'COT_' in stripped:
            continue
        for col in COLUMN_NAMES:
            if f'"{col}"' in stripped:
                # Show context
                context = line.strip()[:120]
                print(f'  L{i}: ...{context}...')
                found += 1
                total += 1
                break
    
    if found == 0:
        print('  CLEAN - no hardcoded column names')

print(f'\n{"="*50}')
print(f'TOTAL remaining hardcoded column names: {total}')
