import re

with open('tabs/tab_khnv_noi_bo.py', encoding='utf-8') as f:
    content = f.read()

lines_before = len(content.splitlines())

# 1. Update import
old_import = "from services import khnv_noi_bo_service"
new_import = ("from services import khnv_noi_bo_service\n"
              "from services.khnv_noi_bo_service import (\n"
              "    _xuat_bc_phan_cong,\n"
              "    _xuat_bc_tien_do,\n"
              ")")
assert old_import in content, "Import not found"
content = content.replace(old_import, new_import, 1)

# 2. Find the comment block for TAB 4 helpers
# Marker: the separator line before "# TAB 4: 📄 In báo cáo — helpers Word NĐ30/2020"
start_marker = "\n# ──────────────────────────────────────────────\n# TAB 4: 📄 In báo cáo — helpers Word NĐ30/2020\n# ──────────────────────────────────────────────\n"
end_marker = "\n\ndef _render_bao_cao("

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

print(f"start_idx={start_idx}, end_idx={end_idx}")
assert start_idx != -1, "start_marker not found"
assert end_idx != -1, "end_marker not found"
assert start_idx < end_idx, f"start ({start_idx}) must come before end ({end_idx})"

removed_text = content[start_idx:end_idx]
print(f"Removing {len(removed_text.splitlines())} lines")

content = content[:start_idx] + "\n" + content[end_idx:]

lines_after = len(content.splitlines())
print(f"Lines: {lines_before} -> {lines_after}")

with open('tabs/tab_khnv_noi_bo.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
