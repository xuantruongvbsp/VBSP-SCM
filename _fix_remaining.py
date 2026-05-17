"""Fix remaining hardcoded column names in tab_baocao.py"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

path = r'd:\VBSP-SCM\tabs\tab_baocao.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# Line 675: "Dư nợ khoanh" in _COL_DSML list
old = 'COT_TONG_DU_NO, COT_DU_NO_QH, "Dư nợ khoanh", COT_LAI_TON, COT_NGUON_VON,'
new = 'COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_LAI_TON, COT_NGUON_VON,'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print(f'Fixed remaining "Dư nợ khoanh" in _COL_DSML')
else:
    print('Could not find remaining "Dư nợ khoanh"')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nTotal: {changes} remaining fix(es) applied')
