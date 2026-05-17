"""Fix remaining "Ngày số liệu" hardcode in tab_so_sanh_ky.py"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

path = r'd:\VBSP-SCM\tabs\tab_so_sanh_ky.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# Line 932: if "Ngày số liệu" in df_ht.columns:
old = 'if "Ngày số liệu" in df_ht.columns:'
new = 'if COT_NGAY_SL in df_ht.columns:'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('Fixed "Ngày số liệu" check')

# Line 933: sl = df_ht["Ngày số liệu"].dropna()
old = 'sl = df_ht["Ngày số liệu"].dropna()'
new = 'sl = df_ht[COT_NGAY_SL].dropna()'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('Fixed "Ngày số liệu" access')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Total: {changes} fix(es) applied')
