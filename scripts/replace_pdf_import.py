"""Replace PDF block in tab_no_khoanh.py with import."""
lines = open("tabs/tab_no_khoanh.py", "r", encoding="utf-8").readlines()

# Block 1: reportlab try/except (lines 46-60, 0-indexed 45-59)
# Block 2: PDF helpers (lines 204-1592, 0-indexed 203-1591)
# Also remove BytesIO and Path imports (only used in PDF)

# Build new file
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Skip reportlab try/except block (line 46-60, 0-indexed 45-59)
    if i == 45:
        # Skip until after except block ends
        while i < len(lines) and not lines[i].strip().startswith("_fmt_dong"):
            i += 1
        continue
    # Remove unused imports
    if i == 41 and line.strip() == "from io import BytesIO":
        i += 1
        continue
    if i == 43 and line.strip() == "from pathlib import Path":
        i += 1
        continue
    # Skip PDF block (line 204-1592, 0-indexed 203-1591)
    if i == 203:
        new_lines.append("\n")
        new_lines.append("from tabs.pdf_no_khoanh import (\n")
        new_lines.append("    _REPORTLAB_READY, _VBSP_GREEN, _VBSP_GREEN_LIGHT, _ROW_ALT, _BORDER_COLOR, _HEADER_BG, _RED,\n")
        new_lines.append("    _FN, _FB,\n")
        new_lines.append("    _dang_ky_font_qlnk, _tim_logo_qlnk,\n")
        new_lines.append("    _qlnk_add_months, _qlnk_fmt_k, _qlnk_fmt_dong,\n")
        new_lines.append("    _style_bank_name, _style_bank_branch, _style_doc_title, _style_doc_sub,\n")
        new_lines.append("    _style_body, _style_body_bold, _style_italic,\n")
        new_lines.append("    _style_table_header, _style_table_cell, _style_table_cell_left,\n")
        new_lines.append("    _style_sig_title, _style_sig_sub, _style_date_right, _style_meta_label,\n")
        new_lines.append("    _ve_header_pdf, _ve_footer_pdf, _dong_ten_nd,\n")
        new_lines.append("    _xuat_pdf_mau_kh, _xuat_pdf_mau_01qlnk, _xuat_pdf_mau_02qlnk,\n")
        new_lines.append("    _xuat_pdf_mau_03qlnk, _xuat_pdf_mau_04qlnk,\n")
        new_lines.append("    _xuat_pdf_bb_kt_cv368, _xuat_pdf_qlnk_06,\n")
        new_lines.append("    _xuat_pdf_m10, _xuat_pdf_ke_hoach_kt,\n")
        new_lines.append(")\n")
        new_lines.append("\n")
        # Skip to line 1592 (0-indexed 1591)
        i = 1591
        continue
    new_lines.append(line)
    i += 1

with open("tabs/tab_no_khoanh.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Old: {len(lines)} lines, New: {len(new_lines)} lines")
print(f"Removed: {len(lines) - len(new_lines)} lines")
