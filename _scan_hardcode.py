"""Scan tabs/ for hardcoded Vietnamese column names that should use COT_* constants."""
import re, os, glob

cot_map = {}
with open('d:\\VBSP-SCM\\config.py', 'r', encoding='utf-8') as f:
    for line in f:
        m = re.match(r'^COT_([A-Z_]+)\s*=\s*"(.+)"', line)
        if m:
            cot_map[m.group(1)] = m.group(2)

with open('d:\\VBSP-SCM\\config.py', 'r', encoding='utf-8') as f:
    for line in f:
        m = re.match(r'^COT_([A-Z_]+)\s*=\s*COT_([A-Z_]+)', line)
        if m:
            cot_map[m.group(1)] = cot_map.get(m.group(2), m.group(2))

cot_values = sorted(set(cot_map.values()), key=len, reverse=True)

files = glob.glob('d:\\VBSP-SCM\\tabs\\tab_*.py')
files.sort()

results = {}
for fp in files:
    fname = os.path.basename(fp)
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')

    hits = []
    for val in cot_values:
        if len(val) < 4:
            continue
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#') or 'import' in stripped or 'COT_' in stripped:
                continue
            if '"' + val + '"' in line or "'" + val + "'" in line:
                if not re.search(r'COT_\w+\s*=\s*"' + re.escape(val) + '"', line):
                    hits.append((i, line.strip()[:80], val))

    if hits:
        results[fname] = hits

# Write to UTF-8 file for Vietnamese support
output_path = 'd:\\VBSP-SCM\\_scan_result.txt'
with open(output_path, 'w', encoding='utf-8') as out:
    out.write(f'=== SCAN RESULT: {len(results)} files with potential hardcoded column names ===\n\n')
    for fname, hits in sorted(results.items()):
        out.write(f'--- {fname} --- ({len(hits)} hits)\n')
        for line_no, line_text, val in hits[:50]:
            out.write(f'  L{line_no:>4}: {line_text}\n')
            out.write(f'         (hardcode: "{val}")\n')
        if len(hits) > 50:
            out.write(f'  ... and {len(hits)-50} more\n')
        out.write('\n')

print(f'Done. Results written to {output_path}')
print(f'{len(results)} files with {sum(len(h) for h in results.values())} total hits')
