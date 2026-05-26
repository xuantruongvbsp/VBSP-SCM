"""Fix syntax errors in tab_xu_ly_rui_ro.py"""

SRC = r"d:\VBSP-SCM\tabs\tab_xu_ly_rui_ro.py"
with open(SRC, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: f-string with literal newline
content = content.replace(
    'st.markdown(f"**{dot.ten_dot}**\n`{dot.id}`")',
    'st.markdown(f"**{dot.ten_dot}**  \\\n`{dot.id}`")'
)

# Fix 2: typo "nàày"
content = content.replace('"nàày"', '"này"')

# Fix 3: Also check in _subtab_dot_xlrr_pgd - there's a similar pattern
# Check for the PGD version
content = content.replace(
    'st.markdown(f"**{dot.ten_dot}**\n`{dot.id}`")',
    'st.markdown(f"**{dot.ten_dot}**  \\\n`{dot.id}`")'
)

# Also check if there's the same pattern with slightly different whitespace
import re
# Pattern: st.markdown(f"**{...}**\n`{...}`")  where \n is literal
pattern = r'st\.markdown\(f"\*\*\{dot\.ten_dot\}\*\*\n`\{dot\.id\}`"\)'
if re.search(pattern, content):
    print("Found more instances of the broken f-string")

with open(SRC, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixes applied")
