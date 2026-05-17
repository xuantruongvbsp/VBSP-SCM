"""Final scan: check for remaining hardcoded column names in Priority 1 files"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from config import *

# Get all COT_ values from config
cot_values = {v for k, v in globals().items() if k.startswith('COT_') and isinstance(v, str)}

priority1 = [
    r'd:\VBSP-SCM\tabs\tab_baocao.py',
    r'd:\VBSP-SCM\tabs\tab_danhsach.py',
    r'd:\VBSP-SCM\tabs\tab_khtd_mau07.py',
    r'd:\VBSP-SCM\tabs\tab_so_sanh_ky.py',
]

total_issues = 0
for filepath in priority1:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    issues = []
    for i, line in lines:
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('import') or stripped.startswith('from'):
            continue
        if 'COT_' in stripped:
            continue
        for val in cot_values:
            if f'"{val}"' in stripped:
                # Check if it's in a display context (st.metric, st.selectbox, etc.)
                # or a docstring
                pass
    
    print(f'{filepath}: {len(issues)} potential issues')

# Actually let me just grep for the specific patterns that matter
import subprocess
print('\n=== Checking remaining hardcoded strings in Priority 1 ===')
for filepath in priority1:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    found = []
    for val in sorted(cot_values, key=len, reverse=True):
        # Only count quoted occurrences not preceded by COT_
        import re
        pattern = re.escape(val)
        matches = re.findall(pattern, content)
        if matches:
            # Check context - skip if in comment or import
            for m in re.finditer(pattern, content):
                start = max(0, m.start() - 20)
                context = content[start:m.end()+20]
                # Count this
                found.append((val, m.start()))
    
    if found:
        print(f'\n{filepath}:')
        for val, pos in found[:20]:
            print(f'  pos {pos}: "{val}"')
        if len(found) > 20:
            print(f'  ... and {len(found)-20} more')
    else:
        print(f'{filepath}: CLEAN')
