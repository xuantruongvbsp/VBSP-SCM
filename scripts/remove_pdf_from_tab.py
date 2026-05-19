"""Remove PDF block from tab_no_khoanh.py and add import."""
lines = open("tabs/tab_no_khoanh.py", "r", encoding="utf-8").readlines()

# --- Find reportlab import block ---
try_start = None
except_end = None
for i, line in enumerate(lines):
    if try_start is None and i < 70 and line.strip() == "try:" and "from reportlab" in (lines[i-1].strip() if i > 0 else ""):
        try_start = i - 1  # include the 'from reportlab' line
    if try_start is not None and except_end is None and "_REPORTLAB_READY = False" in line:
        # Find end of except block
        for j in range(i + 1, min(i + 6, len(lines))):
            if lines[j].strip() == "":
                except_end = j
                break
        if except_end is None:
            except_end = i + 2
        try_start = try_start - 1  # include blank line before
        break

print(f"reportlab block: lines {try_start+1}-{except_end+1}")

# --- Find PDF helpers block ---
pdf_start = None
pdf_end = None
for i, line in enumerate(lines):
    if "PDF helpers (QLNK theo CV 368)" in line:
        pdf_start = i
    if pdf_start is not None and "CV 368:" in line and "Drill-down" in line:
        pdf_end = i
        break

# Include the blank line before and separator comment
if pdf_start is not None:
    while pdf_start > 0 and lines[pdf_start - 1].strip() == "":
        pdf_start -= 1

print(f"PDF block: lines {pdf_start+1}-{pdf_end+1}")

if try_start is None or pdf_start is None:
    print("ERROR: Could not find blocks")
    exit(1)

# --- Build new file ---
new_lines = []
# Keep everything before reportlab import
new_lines.extend(lines[:try_start])
# Add import
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
# Add _fmt_dong (keep it)
# Keep from after except_end to before pdf_start
new_lines.extend(lines[except_end + 1:pdf_start])
# Keep everything after pdf_end
new_lines.extend(lines[pdf_end:])

with open("tabs/tab_no_khoanh.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Old size: {len(lines)} lines, New size: {len(new_lines)} lines")
