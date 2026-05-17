"""Fix the problematic multiline replacement 10h in _fix_baocao.py"""
path = r'd:\VBSP-SCM\_fix_baocao.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''# Lines 731-734
old = 'if "Tên ĐVUT" in df_qh_rpt.columns:\\n                                df_qh_rpt.groupby("Tên ĐVUT").agg('
new = 'if COT_DVUT in df_qh_rpt.columns:\\n                                df_qh_rpt.groupby(COT_DVUT).agg('
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10h. Fixed Tên ĐVUT qh groupby')'''

new_block = '''# Lines 731-734: separate replacements
old = 'if "Tên ĐVUT" in df_qh_rpt.columns:'
new = 'if COT_DVUT in df_qh_rpt.columns:'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10h. Fixed Tên ĐVUT qh if')

old = 'df_qh_rpt.groupby("Tên ĐVUT").agg('
new = 'df_qh_rpt.groupby(COT_DVUT).agg('
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10i. Fixed Tên ĐVUT qh groupby')'''

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    print('SUCCESS: Fixed replacement 10h')
else:
    print('FAIL: Could not find old_block')
    # Debug: find relevant lines
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if '10h' in line or 'df_qh_rpt' in line:
            print(f'  Line {i+1}: {line}')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
