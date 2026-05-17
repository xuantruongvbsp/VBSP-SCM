"""Fix Unicode arrows in _fix_baocao.py print statements"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

path = r'd:\VBSP-SCM\_fix_baocao.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all → with -> in print statements
content = content.replace('\u2192', '->')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed all Unicode arrows in _fix_baocao.py')
