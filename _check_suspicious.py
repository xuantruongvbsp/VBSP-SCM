"""Check suspicious remaining hardcoded column names"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

path = r'd:\VBSP-SCM\tabs\tab_baocao.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('=== tab_baocao.py lines 198-260 ===')
for i, line in enumerate(lines[197:260], 198):
    print(f'{i}:{line}', end='')

print('\n=== tab_danhsach.py line 105 ===')
path2 = r'd:\VBSP-SCM\tabs\tab_danhsach.py'
with open(path2, 'r', encoding='utf-8') as f:
    lines2 = f.readlines()
for i, line in enumerate(lines2[100:115], 101):
    print(f'{i}:{line}', end='')

print('\n=== tab_so_sanh_ky.py lines 928-990 ===')
path3 = r'd:\VBSP-SCM\tabs\tab_so_sanh_ky.py'
with open(path3, 'r', encoding='utf-8') as f:
    lines3 = f.readlines()
for i, line in enumerate(lines3[927:990], 928):
    print(f'{i}:{line}', end='')
