import shutil

src_lines = open("tabs/tab_no_khoanh.py", "r", encoding="utf-8").readlines()

pdf_start = None
pdf_end = None
for i, line in enumerate(src_lines):
    if "# ─── PDF helpers (QLNK theo CV 368)" in line:
        pdf_start = i
    if pdf_start is not None and "CV 368:" in line and "Drill-down" in line:
        pdf_end = i
        break

if pdf_start is None or pdf_end is None:
    print(f"ERROR: Could not find PDF block boundaries. start={pdf_start}, end={pdf_end}")
    exit(1)

pdf_body = src_lines[pdf_start:pdf_end]

header = '''"""PDF helpers cho QLNK - reportlab templates.

Tach tu tab_no_khoanh.py de giam kich thuoc file chinh.
"""
from io import BytesIO
from datetime import datetime
from pathlib import Path

_REPORTLAB_READY = False
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable, Image as RLImage,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    _REPORTLAB_READY = True
except ImportError:
    pass

if _REPORTLAB_READY:
    _VBSP_GREEN = colors.HexColor("#2E7D32")
    _VBSP_GREEN_LIGHT = colors.HexColor("#E8F5E9")
    _ROW_ALT = colors.HexColor("#F5F5F5")
    _BORDER_COLOR = colors.HexColor("#BDBDBD")
    _HEADER_BG = colors.HexColor("#D9D9D9")
    _RED = colors.HexColor("#C62828")
else:
    _VBSP_GREEN = _VBSP_GREEN_LIGHT = _ROW_ALT = _BORDER_COLOR = _HEADER_BG = _RED = None

_FN = "TNR"
_FB = "TNR-Bold"

'''

with open("tabs/pdf_no_khoanh.py", "w", encoding="utf-8") as f:
    f.write(header)
    f.writelines(pdf_body)

print(f"Written {len(pdf_body)} lines (from line {pdf_start+1} to {pdf_end})")
print(f"Total file size: {len(header) + sum(len(l) for l in pdf_body)} bytes")
