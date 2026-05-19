"""Complete patch for tab_no_khoanh.py: insert helpers + replace d_kt blocks."""
TARGET = "d:/VBSP-SCM/tabs/tab_no_khoanh.py"

with open(TARGET, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find insertion point for helpers (before # --- Render ---)
insert_idx = None
for i, line in enumerate(lines):
    if line.strip() == "# ─── Render ───────────────────────────────────────────────────────────────────":
        insert_idx = i
        break
assert insert_idx, "Could not find Render marker"

# Find d_kt markers
dkt1 = dkt2 = dbc = dkt3 = None
for i, line in enumerate(lines):
    s = line.rstrip()
    if s == "        with d_kt:":
        if dkt1 is None: dkt1 = i
        elif dkt2 is None: dkt2 = i
        else: dkt3 = i
    if s == "        with d_bc:":
        dbc = i

assert None not in (dkt1, dbc, dkt3), f"Missing: {dkt1} {dbc} {dkt3}"
print(f"Markers: dkt1={dkt1} dbc={dbc} dkt3={dkt3} insert={insert_idx}")

# Read new d_kt code and helper functions
with open("d:/VBSP-SCM/_new_dkt_code.txt", "r", encoding="utf-8") as f:
    new_dkt = f.read()

with open("d:/VBSP-SCM/_new_helpers.txt", "r", encoding="utf-8") as f:
    new_helpers = f.read()

# Build output
result = []
# 1. Everything before helper insertion point
result.append("".join(lines[:insert_idx]))
# 2. New helper functions
result.append("\n")
result.append(new_helpers)
result.append("\n")
# 3. Render comment line (keep it)
result.append(lines[insert_idx])
# 4. Everything from render() to before dkt1
result.append("".join(lines[insert_idx + 1:dkt1]))
# 5. New d_kt drill-down code
result.append("\n")
result.append(new_dkt)
result.append("\n")
# 6. d_bc block (keep intact)
result.append("".join(lines[dbc:dkt3]))
# Skip dkt3 content

out_str = "".join(result)
if not out_str.endswith("\n"):
    out_str += "\n"

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(out_str)

print(f"Done. {len(out_str)} chars, {len(out_str.splitlines())} lines")
