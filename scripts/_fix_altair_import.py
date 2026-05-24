"""Temporary script: lazy import altair in tab_so_sanh_ky.py"""
import re

path = "tabs/tab_so_sanh_ky.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove top-level import altair
content = content.replace('import altair as alt\n', '')

# 2. Add lazy import inside 5 functions that use altair
funcs = [
    '_chart_tang_truong',
    '_render_co_cau_nguon_von',
    '_render_thoi_han_vay',
    '_render_lai_ton_chi_tiet',
    '_render_aging_analysis',
]
for fn in funcs:
    pattern = rf'(def {fn}\([^)]*\)\s*->\s*None:\s*\n\s*"""[^"]*""")'
    replacement = rf'\1\n    import altair as alt'
    content = re.sub(pattern, replacement, content)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("OK")
