import re

path = r'd:\VBSP-SCM\tabs\tab_tongquan.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the fmt_so application for Số món vay and Số KH - remove fmt_so to keep numeric values
old = 'df_hien["Số món vay"]         = df_hien["so_mon"].apply(fmt_so)\n            df_hien["Số KH"]              = df_hien["so_kh"].apply(fmt_so)'
new = 'df_hien["Số món vay"]         = df_hien["so_mon"]\n            df_hien["Số KH"]              = df_hien["so_kh"]'

count = content.count(old)
print(f"Found {count} occurrence(s) at line 610-611")

if count > 0:
    content = content.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replacement done!")
else:
    print("Pattern not found, trying exact match...")
    lines = content.split('\n')
    for i, line in enumerate(lines[608:615], start=609):
        print(f"  Line {i}: {repr(line)}")
