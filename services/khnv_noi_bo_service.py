from __future__ import annotations

import db


def doc_ds(key: str) -> list:
    val = db.doc_kv(key)
    return val if isinstance(val, list) else []


def ghi_ds(key: str, ds: list, username: str, action: str, mo_ta: str) -> None:
    db.ghi_kv(key, ds, username)
    db.ghi_audit(username, action, mo_ta)


# ── Word export — NĐ30/2020 ──────────────────────────────────────────────────

def _xuat_bc_phan_cong(ds: list, thang: int, nam: int, ten_truong_phong: str = "") -> bytes:
    """Tạo Word 'DANH SÁCH PHÂN CÔNG VÀ GIAO VIỆC' chuẩn NĐ30/2020."""
    import io
    from datetime import date as _date
    from docx import Document
    from docx.shared import Cm, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    def _set_font(run, bold: bool = False, size: int = 13) -> None:
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)
        run.font.bold = bold
        try:
            rPr = run._r.get_or_add_rPr()
            rFonts = rPr.get_or_add_rFonts()
            rFonts.set(qn("w:eastAsia"), "Times New Roman")
        except Exception:
            pass

    def _remove_borders(table) -> None:
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

    def _shade_cell(cell, fill: str = "BDD7EE") -> None:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), fill)
        tcPr.append(shd)

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

    today = _date.today()

    hdr = doc.add_table(rows=1, cols=2)
    _remove_borders(hdr)
    cell_l = hdr.rows[0].cells[0]
    for i, (txt, bold) in enumerate([
        ("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI", True),
        ("Chi nhánh tỉnh Đồng Nai", False),
        ("Phòng KH-NV", False),
        ("──────────────", False),
        ("Số:      /BC-KHNV", False),
    ]):
        p = cell_l.paragraphs[0] if i == 0 else cell_l.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(p.add_run(txt), bold=bold, size=12 if i == 0 else 11)

    cell_r = hdr.rows[0].cells[1]
    for i, (txt, bold) in enumerate([
        ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", True),
        ("Độc lập - Tự do - Hạnh phúc", True),
        ("──────────────────────────", False),
        (f"Đồng Nai, ngày {today.day} tháng {today.month} năm {today.year}", False),
    ]):
        p = cell_r.paragraphs[0] if i == 0 else cell_r.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(p.add_run(txt), bold=bold, size=11)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_font(p.add_run("DANH SÁCH PHÂN CÔNG VÀ GIAO VIỆC"), bold=True, size=14)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_font(p.add_run(f"Tháng {thang} năm {nam}"), size=13)
    doc.add_paragraph()

    _uu = {"khan_cap": "Khẩn cấp", "quan_trong": "Quan trọng", "binh_thuong": "Bình thường"}
    _cv = {"vp1": "Phó Phòng VT1", "vp2": "Phó Phòng VT2", "cbtd": "Cán bộ TD"}
    headers = ["STT", "Nhóm việc", "Đầu việc", "Người thực hiện",
               "Chức vụ", "Mức độ", "Ngày giao", "Thời gian\nhoàn thành"]
    widths_cm = [0.8, 2.5, 4.0, 2.5, 1.8, 1.6, 1.7, 1.7]

    tbl = doc.add_table(rows=1, cols=8)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, w in enumerate(widths_cm):
        for cell in tbl.columns[i].cells:
            cell.width = Cm(w)

    hdr_row = tbl.rows[0]
    for i, h in enumerate(headers):
        cell = hdr_row.cells[i]
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(p.add_run(h), bold=True, size=11)
        _shade_cell(cell)

    for stt, item in enumerate(ds, 1):
        row = tbl.add_row()
        cv_code = item.get("chuc_vu", "")
        vals = [
            str(stt),
            item.get("nhom", ""),
            item.get("tieu_de", ""),
            item.get("nguoi_thuc_hien", ""),
            _cv.get(cv_code, cv_code),
            _uu.get(item.get("uu_tien", ""), ""),
            item.get("ngay_giao", ""),
            item.get("ngay_deadline", ""),
        ]
        CENTER_COLS = {0, 5, 6, 7}
        for i, val in enumerate(vals):
            p = row.cells[i].paragraphs[0]
            p.alignment = (WD_ALIGN_PARAGRAPH.CENTER if i in CENTER_COLS
                           else WD_ALIGN_PARAGRAPH.LEFT)
            _set_font(p.add_run(val), size=11)

    doc.add_paragraph()
    foot = doc.add_table(rows=3, cols=2)
    _remove_borders(foot)
    foot_data = [
        ("Người lập",          "TRƯỞNG PHÒNG KH-NV"),
        ("(Ký, ghi rõ họ tên)", "(Ký, ghi rõ họ tên)"),
        ("",                   ten_truong_phong),
    ]
    foot_bold = [(False, True), (False, False), (False, True)]
    for i, ((txt_l, txt_r), (bl, br)) in enumerate(zip(foot_data, foot_bold)):
        pl = foot.rows[i].cells[0].paragraphs[0]
        pl.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(pl.add_run(txt_l), bold=bl, size=12)
        pr = foot.rows[i].cells[1].paragraphs[0]
        pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(pr.add_run(txt_r), bold=br, size=12)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _xuat_bc_tien_do(ds: list, thang: int, nam: int, ten_truong_phong: str = "") -> bytes:
    """Tạo Word 'BÁO CÁO TIẾN ĐỘ THỰC HIỆN CÔNG VIỆC' chuẩn NĐ30/2020."""
    import io
    from datetime import date as _date
    from docx import Document
    from docx.shared import Cm, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    def _set_font(run, bold: bool = False, size: int = 13) -> None:
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)
        run.font.bold = bold
        try:
            rPr = run._r.get_or_add_rPr()
            rFonts = rPr.get_or_add_rFonts()
            rFonts.set(qn("w:eastAsia"), "Times New Roman")
        except Exception:
            pass

    def _remove_borders(table) -> None:
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

    def _shade_cell(cell, fill: str = "BDD7EE") -> None:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), fill)
        tcPr.append(shd)

    _tt_map = {"chua_lam": "Chưa làm", "dang_lam": "Đang làm",
               "hoan_thanh": "Hoàn thành", "tre_han": "Trễ hạn"}
    _uu_map = {"khan_cap": "Khẩn cấp", "quan_trong": "Quan trọng", "binh_thuong": "Bình thường"}

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

    today = _date.today()

    hdr = doc.add_table(rows=1, cols=2)
    _remove_borders(hdr)
    cell_l = hdr.rows[0].cells[0]
    for i, (txt, bold) in enumerate([
        ("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI", True),
        ("Chi nhánh tỉnh Đồng Nai", False),
        ("Phòng KH-NV", False),
        ("──────────────", False),
        ("Số:      /BC-KHNV", False),
    ]):
        p = cell_l.paragraphs[0] if i == 0 else cell_l.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(p.add_run(txt), bold=bold, size=12 if i == 0 else 11)

    cell_r = hdr.rows[0].cells[1]
    for i, (txt, bold) in enumerate([
        ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", True),
        ("Độc lập - Tự do - Hạnh phúc", True),
        ("──────────────────────────", False),
        (f"Đồng Nai, ngày {today.day} tháng {today.month} năm {today.year}", False),
    ]):
        p = cell_r.paragraphs[0] if i == 0 else cell_r.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(p.add_run(txt), bold=bold, size=11)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_font(p.add_run("BÁO CÁO TIẾN ĐỘ THỰC HIỆN CÔNG VIỆC"), bold=True, size=14)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_font(p.add_run(f"Tháng {thang} năm {nam}"), size=13)
    doc.add_paragraph()

    p = doc.add_paragraph()
    _set_font(p.add_run("I. TỔNG QUAN"), bold=True, size=13)

    tong = len(ds)
    ht   = sum(1 for x in ds if x.get("trang_thai") == "hoan_thanh")
    dang = sum(1 for x in ds if x.get("trang_thai") == "dang_lam")
    chua = sum(1 for x in ds if x.get("trang_thai") == "chua_lam")
    tre  = sum(1 for x in ds if x.get("trang_thai") == "tre_han")
    pct  = f"{ht / tong * 100:.0f}" if tong > 0 else "0"

    p = doc.add_paragraph()
    _set_font(p.add_run(
        f"Tổng số đầu việc: {tong}  |  Đã hoàn thành: {ht} ({pct}%)  |  "
        f"Đang thực hiện: {dang}  |  Chưa làm: {chua}  |  Trễ hạn: {tre}"
    ), size=13)
    doc.add_paragraph()

    p = doc.add_paragraph()
    _set_font(p.add_run("II. CHI TIẾT"), bold=True, size=13)

    headers = ["STT", "Đầu việc", "Người thực hiện", "Mức độ",
               "Ngày giao", "Thời gian\nhoàn thành", "Trạng thái", "Ghi chú"]
    widths_cm = [0.8, 3.6, 2.5, 1.8, 1.8, 2.0, 1.8, 2.3]

    tbl = doc.add_table(rows=1, cols=8)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, w in enumerate(widths_cm):
        for cell in tbl.columns[i].cells:
            cell.width = Cm(w)

    hdr_row = tbl.rows[0]
    for i, h in enumerate(headers):
        cell = hdr_row.cells[i]
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(p.add_run(h), bold=True, size=11)
        _shade_cell(cell)

    for stt, item in enumerate(ds, 1):
        row = tbl.add_row()
        vals = [
            str(stt),
            item.get("tieu_de", ""),
            item.get("nguoi_thuc_hien", ""),
            _uu_map.get(item.get("uu_tien", ""), ""),
            item.get("ngay_giao", ""),
            item.get("ngay_deadline", ""),
            _tt_map.get(item.get("trang_thai", ""), ""),
            item.get("ghi_chu_ket_qua", ""),
        ]
        CENTER_COLS = {0, 3, 4, 5, 6}
        for i, val in enumerate(vals):
            p = row.cells[i].paragraphs[0]
            p.alignment = (WD_ALIGN_PARAGRAPH.CENTER if i in CENTER_COLS
                           else WD_ALIGN_PARAGRAPH.LEFT)
            _set_font(p.add_run(val), size=11)

    doc.add_paragraph()
    foot = doc.add_table(rows=3, cols=2)
    _remove_borders(foot)
    foot_data = [
        ("Người lập",           "TRƯỞNG PHÒNG KH-NV"),
        ("(Ký, ghi rõ họ tên)", "(Ký, ghi rõ họ tên)"),
        ("",                    ten_truong_phong),
    ]
    foot_bold = [(False, True), (False, False), (False, True)]
    for i, ((txt_l, txt_r), (bl, br)) in enumerate(zip(foot_data, foot_bold)):
        pl = foot.rows[i].cells[0].paragraphs[0]
        pl.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(pl.add_run(txt_l), bold=bl, size=12)
        pr = foot.rows[i].cells[1].paragraphs[0]
        pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(pr.add_run(txt_r), bold=br, size=12)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

