"""Check the result of _fix_baocao.py replacements"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'd:\VBSP-SCM\tabs\tab_baocao.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('=== Lines 85-100 ===')
for i, line in enumerate(lines[84:100], 85):
    print(f'{i}:{line}', end='')

print('\n=== Lines 308-318 ===')
for i, line in enumerate(lines[307:318], 308):
    print(f'{i}:{line}', end='')

print('\n=== Lines 335-395 (DVUT section) ===')
for i, line in enumerate(lines[334:395], 335):
    print(f'{i}:{line}', end='')

print('\n=== Lines 420-435 ===')
for i, line in enumerate(lines[419:435], 420):
    print(f'{i}:{line}', end='')

print('\n=== Lines 505-535 ===')
for i, line in enumerate(lines[504:535], 505):
    print(f'{i}:{line}', end='')

print('\n=== Lines 580-600 ===')
for i, line in enumerate(lines[579:600], 580):
    print(f'{i}:{line}', end='')

print('\n=== Lines 605-655 ===')
for i, line in enumerate(lines[604:655], 605):
    print(f'{i}:{line}', end='')

print('\n=== Lines 670-740 ===')
for i, line in enumerate(lines[669:740], 670):
    print(f'{i}:{line}', end='')
