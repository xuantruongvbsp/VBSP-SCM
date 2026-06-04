"""Dịch vụ xuất Lịch làm việc tuần KH-NV ra file Word.

Dùng mẫu MAU_LICH LAM VIEC TUAN KH-NV.md.
- Nhập tuần (từ ngày → đến ngày)
- Nhập nội dung cho từng mục
- Sinh file .docx hoàn chỉnh
"""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

from logger import get_logger

logger = get_logger(__name__)

SECTION_LABELS: list[tuple[str, str]] = [
    ("cong_tac_td", "1. Công tác tín dụng chi nhánh tỉnh"),
    ("dia_ban_hs", "2. Địa bàn 09 phường do Hội sở tỉnh kiêm nhiệm"),
    ("noi_dung_khac", "3. Nội dung công việc khác"),
]

MAU_NOI_DUNG_MAC_DINH = {
    "cong_tac_td": (
        "- Tham mưu Ban Giám đốc chi nhánh các nội dung theo chỉ đạo.\n"
        "- Đôn đốc các PGD:\n"
        "  + Làm việc với UBND các xã, phường để sớm được chuyển vốn ủy thác.\n"
        "  + Huy động tiền gửi; tổ chức giải ngân kịp thời.\n"
        "  + Kiểm soát, xử lý nợ đến hạn phân kỳ.\n"
        "  + Phân tích nguyên nhân, có giải pháp xử lý NQH, nợ khoanh, hộ KHĐ.\n"
        "  + Đôn đốc CT-XH nâng cao chất lượng ủy thác, bình xét, kiểm tra.\n"
        "- Chủ động rà soát, chỉnh sửa tồn tại theo kết luận kiểm tra.\n"
        "- Các nội dung công việc khác theo chỉ đạo của BGĐ CN tỉnh."
    ),
    "dia_ban_hs": (
        "- Làm việc với UBND các phường để sớm được chuyển vốn ủy thác.\n"
        "- Huy động tiền gửi; giải ngân các chỉ tiêu kế hoạch dư nợ.\n"
        "- Xử lý nợ đến hạn; đôn đốc thu hồi NQH, nợ khoanh.\n"
        "- Đôn đốc CT-XH cấp xã nâng cao chất lượng hoạt động ủy thác.\n"
        "- Các nội dung công việc khác theo chỉ đạo của BGĐ CN tỉnh."
    ),
    "noi_dung_khac": "- Các nội dung công việc khác theo chỉ đạo của BGĐ CN tỉnh.",
}


def lay_tuan_tiep_theo() -> tuple[date, date]:
    """Ngày thứ 2 và thứ 6 của tuần sau."""
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    next_friday = next_monday + timedelta(days=4)
    return next_monday, next_friday


def xuat_lich_lam_viec_tuan(
    tu_ngay: date,
    den_ngay: date,
    noi_dung: dict[str, str] | None = None,
    ten_truong_phong: str = "",
    ngay_ky: date | None = None,
) -> bytes:
    """Tạo file Word Lịch công tác tuần."""
    from docx import Document
    from docx.shared import Cm, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(3)
    sec.right_margin = Cm(2)
    sec.top_margin = Cm(2)
    sec.bottom_margin = Cm(2)
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(13)

    nd = noi_dung or {}
    ngay_ky = ngay_ky or (tu_ngay - timedelta(days=3))

    def fmt_date(d: date) -> str:
        return f"ngày {d.day} tháng {d.month} năm {d.year}"

    def _set(run, bold=False, size=13):
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)
        run.font.bold = bold
        try:
            rPr = run._r.get_or_add_rPr()
            rFonts = rPr.get_or_add_rFonts()
            rFonts.set(qn("w:eastAsia"), "Times New Roman")
        except Exception:
            pass

    def _no_border(table):
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                for old in tcPr.findall(qn("w:tcBorders")):
                    tcPr.remove(old)
                tcBorders = OxmlElement("w:tcBorders")
                for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
                    el = OxmlElement(f"w:{side}")
                    el.set(qn("w:val"), "nil")
                    tcBorders.append(el)
                tcPr.append(tcBorders)

    # ── Header ──
    hdr = doc.add_table(rows=1, cols=2)
    _no_border(hdr)
    cell_l = hdr.rows[0].cells[0]
    for txt, bold in [("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI", True),
                       ("CHI NHÁNH TỈNH ĐỒNG NAI", True),
                       ("Phòng KHNVTD", False),
                       ("──────────────", False)]:
        p = cell_l.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _set(p.add_run(txt), bold=bold, size=12 if bold else 11)
    p0 = cell_l.paragraphs[0]
    p0._element.getparent().remove(p0._element)

    cell_r = hdr.rows[0].cells[1]
    for txt, bold in [("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", True),
                       ("Độc lập - Tự do - Hạnh phúc", True),
                       ("──────────────────────────", False),
                       (f"Đồng Nai, {fmt_date(ngay_ky)}", False)]:
        p = cell_r.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set(p.add_run(txt), bold=bold, size=12 if bold else 11)
    p0r = cell_r.paragraphs[0]
    p0r._element.getparent().remove(p0r._element)

    doc.add_paragraph("")

    # ── Title ──
    p_t = doc.add_paragraph()
    p_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set(p_t.add_run("LỊCH CÔNG TÁC"), bold=True, size=16)

    p_s = doc.add_paragraph()
    p_s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set(p_s.add_run(f"Từ {fmt_date(tu_ngay)} đến {fmt_date(den_ngay)}"), bold=True, size=13)

    doc.add_paragraph("")

    # ── NỘI DUNG ──
    p_h = doc.add_paragraph()
    _set(p_h.add_run("NỘI DUNG CÔNG VIỆC:"), bold=True, size=13)

    for key, label in SECTION_LABELS:
        doc.add_paragraph("")
        p_sec = doc.add_paragraph()
        _set(p_sec.add_run(label), bold=True, size=13)
        text = nd.get(key, MAU_NOI_DUNG_MAC_DINH.get(key, ""))
        for line in text.strip().split("\n"):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            _set(p.add_run(line), bold=False, size=13)

    doc.add_paragraph("")
    doc.add_paragraph("")

    # ── Ký tên ──
    sig = doc.add_table(rows=1, cols=2)
    _no_border(sig)
    sl = sig.rows[0].cells[0]
    sp = sl.add_paragraph()
    sp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _set(sp.add_run("Nơi nhận:\n- Phòng HC-TC;\n- Các cán bộ phòng TD (biết, thực hiện);\n- Lưu TD."), bold=False, size=11)
    p0sl = sl.paragraphs[0]
    p0sl._element.getparent().remove(p0sl._element)

    sr = sig.rows[0].cells[1]
    for _ in range(4):
        sr.add_paragraph("")
    sp2 = sr.add_paragraph()
    sp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set(sp2.add_run("TRƯỞNG PHÒNG"), bold=True, size=13)
    if ten_truong_phong:
        for _ in range(3):
            sr.add_paragraph("")
        sp3 = sr.add_paragraph()
        sp3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set(sp3.add_run(ten_truong_phong), bold=True, size=13)
    p0sr = sr.paragraphs[0]
    p0sr._element.getparent().remove(p0sr._element)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
