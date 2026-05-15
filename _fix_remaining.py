"""Fix remaining formatting issues in tabs."""
import os, re, sys

sys.stdout.reconfigure(encoding='utf-8')

# 3. Fix tab_tracuu.py - update NumberColumn format strings
path = r'd:\VBSP-SCM\tabs\tab_tracuu.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace format="%.0f \u20ab" with format="%.0f" (₫ symbol)
content = content.replace('%.0f \u20ab', '%.0f')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('tab_tracuu.py done')

print('All done!')
