import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'd:\VBSP-SCM\tabs\tab_no_rui_ro.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Edit 1: Find the second 'df is None or df.empty:' occurrence (first is in _loc_df_theo_pgd)
count = 0
edit1_line = -1
for i, line in enumerate(lines):
    if 'df is None or df.empty:' in line:
        count += 1
        if count == 2:
            edit1_line = i
            break

print(f'Edit 1: Found 2nd occurrence at line {edit1_line+1}')

# Insert 4 lines after the blank line (edit1_line + 3)
insert_at = edit1_line + 3
new_lines = [
    '        if la_phan_he_cn(role):\n',
    '            _render_workspace_cn(tab, df=df, role=role, username=username, **kwargs)\n',
    '            return\n',
    '\n',
]
lines = lines[:insert_at] + new_lines + lines[insert_at:]
print(f'Edit 1: Inserted CN branch at line {insert_at+1}')

# Edit 2: Find st.divider() followed by Bước 1 (the old 5-step flow)
edit2_start = -1
for i, line in enumerate(lines):
    if 'st.divider()' in line and i > edit1_line:
        for j in range(i+1, min(i+5, len(lines))):
            if lines[j].strip() and 'Bước 1' in lines[j]:
                edit2_start = i
                break
        if edit2_start >= 0:
            break

print(f'Edit 2: Found divider for old flow at line {edit2_start+1}')

new_section = [
    '        st.divider()\n',
    '\n',
    '        _render_luong_nhap_ho_so(\n',
    '            df_pgd=df,\n',
    '            ten_pgd=ten_pgd or "",\n',
    '            kv_key=kv_key,\n',
    '            username=username,\n',
    '            la_cn=False,\n',
    '            key_prefix="",\n',
    '        )\n',
]
lines = lines[:edit2_start] + new_section

print(f'Edit 2: Replaced Bước 1-5 with _render_luong_nhap_ho_so() call')
print(f'Total lines: {len(lines)}')

with open(r'd:\VBSP-SCM\tabs\tab_no_rui_ro.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('File written successfully')
