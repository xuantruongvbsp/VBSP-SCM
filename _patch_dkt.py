"""Patch: Replace all d_kt blocks with new drill-down code, keep d_bc intact."""
TARGET = "d:/VBSP-SCM/tabs/tab_no_khoanh.py"
NEW_CODE_FILE = "d:/VBSP-SCM/_new_dkt_code.txt"

with open(TARGET, "r", encoding="utf-8") as f:
    lines = f.readlines()

dkt1 = dkt2 = dbc = dkt3 = None
for i, line in enumerate(lines):
    s = line.rstrip()
    if s == "        with d_kt:":
        if dkt1 is None: dkt1 = i
        elif dkt2 is None: dkt2 = i
        else: dkt3 = i
    if s == "        with d_bc:":
        dbc = i

assert None not in (dkt1, dbc, dkt3), f"Missing markers: {dkt1} {dbc} {dkt3}"

with open(NEW_CODE_FILE, "r", encoding="utf-8") as f:
    new_dkt = f.read()

# Output: before[:dkt1] + new_dkt + "\n" + lines[dbc:dkt3] (d_bc) + function close
# Need to find proper function close after the d_bc block
# The render function closes after dkt3. We need to copy the dedent lines
# that follow dkt3. These are at the original indentation level.

# After dkt3, the render() function might have more code at outer level.
# Let me find what comes after the third d_kt block closes.

# The file is essentially:
# def render(...):
#     ...
#     if d_kt is not None:
#         with d_kt: ...  # dkt1
#         with d_kt: ...  # dkt2  
#         with d_bc: ...  # dbc
#         with d_kt: ...  # dkt3
#     # possibly more code at render() level

# Actually, let me check: the original structure has the if-block containing all 3 d_kt + d_bc.
# The if-block starts before dkt1. I need to find the line before dkt1 that opens the if.
# And close the if properly.

# Look at the indentation level of dkt1
dkt1_indent = len(lines[dkt1]) - len(lines[dkt1].lstrip())
print(f"dkt1 indent: {dkt1_indent} spaces, line: {lines[dkt1].rstrip()}")

# Find the if/for statement that opens this block
for j in range(dkt1 - 1, max(0, dkt1 - 20), -1):
    stripped = lines[j].rstrip()
    indent = len(lines[j]) - len(lines[j].lstrip())
    if indent < dkt1_indent and stripped.endswith(":"):
        print(f"  Parent block L{j}: indent={indent}: {stripped}")
        break

# Build output
result = []
result.append("".join(lines[:dkt1]))
result.append("\n")
result.append(new_dkt)
result.append("\n")
result.append("".join(lines[dbc:dkt3]))
# Don't include dkt3 content - the new drill-down replaces it

out_str = "".join(result)
# Ensure proper newline at end
if not out_str.endswith("\n"):
    out_str += "\n"

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(out_str)

print(f"Patched {TARGET}")
print(f"New size: {len(out_str)} chars, {len(out_str.splitlines())} lines")
