"""Fix tab_candoi.py imports: lazy plotly, lazy tab_kehoach, explicit config"""
path = "tabs/tab_candoi.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace from config import *
old_cfg = "from config import *"
new_cfg = """from config import (
    DB_HT_CACHE,
    DB_PREV_CACHE,
    FILE_PATH_DB,
    FILE_PATH_DB_PREV,
)"""
content = content.replace(old_cfg, new_cfg)

# 2. Remove top-level plotly imports
content = content.replace("import plotly.express as px\n", "")
content = content.replace("import plotly.graph_objects as go\n", "")

# 3. Remove top-level tab_kehoach import
content = content.replace("from tabs import tab_kehoach\n", "")

# 4. In all functions that use plotly, add lazy import at function body start.
#    Find functions containing px. or go. and add import after docstring/signature.
import re

# Functions to add plotly imports to
# We'll find functions that use px. or go. and add at the top of their body

lines = content.split('\n')
new_lines = []
in_func = False
func_uses_plotly = False
func_body_started = False
func_indent = ""
skip_until_body = False

for i, line in enumerate(lines):
    stripped = line.strip()

    # Detect function start
    if stripped.startswith("def ") and not in_func:
        in_func = True
        func_uses_plotly = False
        func_body_started = False
        skip_until_body = True
        func_indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        continue

    if in_func and skip_until_body:
        new_lines.append(line)
        # Function body starts after the first non-comment, non-docstring, non-empty line
        # after the signature. The signature ends at `:` and may span multiple lines.
        # Simple heuristic: after we see a line that doesn't start with `    ` (indent)
        # or is the start of actual code
        if stripped == "" or stripped.startswith('"""') or stripped.startswith('#') or stripped.endswith(':') or stripped.endswith('),') or stripped.endswith('->'):
            continue
        # This is the first body line
        skip_until_body = False
        func_body_started = True
        continue

    # Check if this function body uses plotly
    if in_func and func_body_started:
        if "px." in stripped or "go." in stripped:
            func_uses_plotly = True

    # If function ends (outdent back to module level)
    if in_func and stripped != "" and not line.startswith(" ") and not line.startswith("\t") and not stripped.startswith('"""'):
        if func_uses_plotly:
            # We need to insert plotly imports. Let's use a regex approach instead.
            pass
        in_func = False
        func_uses_plotly = False

    new_lines.append(line)

# Actually, the above approach is too fragile. Let's use a simpler approach:
# Add a single lazy import wrapper function at the top, and modify callsites.

print("Skipping complex detection. Using simpler approach: add imports at specific lines.")
