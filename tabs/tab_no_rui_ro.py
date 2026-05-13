"""Xử lý nợ rủi ro theo QĐ 62/2015/QĐ-TTg — 5 bước: lọc, chọn, nhập, xuất, xem lại."""
from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
import streamlit as st
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from streamlit.delta_generator import DeltaGenerator

import db
from config import (
    COT_DIA_CHI,
    COT_LAI_TON,
    COT_MUC_VAY,
    COT_NGAY_DH,
    COT_NGAY_VAY,
    COT_NGUON_VON,
    COT_TEN_XA,
    COT_TEN_TO,
    COT_TEN_KH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_TEN_PGD,
    NGUYEN_NHAN_RR,
)
from data.pgd import pgd_slug
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from utils import fmt, fmt_bang_ty
from services.template_service import (
    nut_tai_word_va_pdf,
    hien_thi_nut_tai,
)

NGUON_TW = 1
NGUON_DP = 2
LABEL_TW = "Trung ương"
LABEL_DP = "Địa phương"


def _style_doc_xln(doc: Document) -> None:
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)


def _add_header_xln(doc: Document, dia_danh: str, ngay_ky: date) -> None:
    """Header Quốc hiệu + ngày tháng, không có số VB (mẫu đơn cá nhân)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    t = doc.add_table(rows=1, cols=2)
    t.style = "Table Grid"
    for cell in t.rows[0].cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for bn in ["top", "left", "bottom", "right"]:
            b = OxmlElement(f"w:{bn}")
            b.set(qn("w:val"), "none")
            tcBorders.append(b)
        tcPr.append(tcBorders)

    cell_l = t.rows[0].cells[0]
    cell_l.paragraphs[0].add_run("Mẫu số 01/XLN")

    cell_r = t.rows[0].cells[1]
    p3 = cell_r.paragraphs[0]
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.add_run("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM").bold = True
    p4 = cell_r.add_paragraph("Độc lập - Tự do - Hạnh phúc")
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p4.runs[0].bold = True
    p5 = cell_r.add_paragraph(
        f"{dia_danh}, ngày {ngay_ky.day} tháng {ngay_ky.month} năm {ngay_ky.year}"
    )
    p5.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()


def _tao_word_01xln(du_lieu: dict) -> bytes:
    """Mẫu 01/XLN — Đơn đề nghị xử lý nợ (KH tự viết)."""
    doc = Document()
    _style_doc_xln(doc)
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2)

    _add_header_xln(
        doc,
        dia_danh=du_lieu.get("dia_danh", ""),
        ngay_ky=du_lieu.get("ngay_ky", date.today()),
    )

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("ĐƠN ĐỀ NGHỊ XỬ LÝ NỢ")
    r.bold = True
    r.font.size = Pt(14)

    doc.add_paragraph(
        f"Kính gửi: Ngân hàng Chính sách xã hội {du_lieu.get('ten_nhcsxh','')}"
    )
    doc.add_paragraph()

    doc.add_paragraph(
        f"Tên tôi là: {du_lieu.get('ten_kh','')}\n"
        f"Hiện cư trú tại: {du_lieu.get('dia_chi','')}\n"
        f"Là thành viên của Tổ TK&VV: {du_lieu.get('ten_to','')} "
        f"do ông (bà): {du_lieu.get('to_truong','')} làm Tổ trưởng"
    )
    doc.add_paragraph(
        f"1. Theo HĐTD (sổ Vay vốn) số {du_lieu.get('so_ku','')}, "
        f"ngày {du_lieu.get('ngay_vay','')}, tôi có đứng tên vay vốn "
        f"chương trình {du_lieu.get('ten_ct','')} tại NHCSXH "
        f"{du_lieu.get('ten_nhcsxh','')}.\n"
        f"    Số tiền vay: {du_lieu.get('muc_vay','')} đồng; "
        f"Hạn trả nợ: {du_lieu.get('ngay_dh','')}; "
        f"Mục đích vay vốn: {du_lieu.get('muc_dich_vay','')}\n"
        f"    Hiện nay, tôi còn nợ Ngân hàng số tiền: "
        f"{du_lieu.get('tong_du_no','')} đồng\n"
        f"    (Trong đó: Nợ gốc: {du_lieu.get('du_no_goc','')} đồng; "
        f"Nợ lãi: {du_lieu.get('lai_ton','')} đồng)"
    )
    doc.add_paragraph(f"2. Trong thời gian vừa qua do:\n{du_lieu.get('nguyen_nhan','')}")
    doc.add_paragraph(
        "3. Số vốn, tài sản của dự án bị thiệt hại:\n"
        f"    - Số vốn và tài sản bị thiệt hại: {du_lieu.get('so_tien_thiet_hai','')} đồng\n"
        f"    - Tổng số vốn thực hiện dự án: {du_lieu.get('muc_vay','')} đồng\n"
        f"    - Mức độ thiệt hại: {du_lieu.get('muc_do_thiet_hai','')}%"
    )
    doc.add_paragraph(
        "4. Tình hình kinh tế, khả năng trả nợ sau khi gặp rủi ro:\n"
        f"{du_lieu.get('kha_nang_tra_no','')}"
    )
    doc.add_paragraph(
        f"Vậy tôi làm đơn này đề nghị NHCSXH {du_lieu.get('ten_nhcsxh','')} "
        f"xem xét {du_lieu.get('bien_phap','')} số nợ bị rủi ro, cụ thể:\n"
        f"    - Số tiền đề nghị: {du_lieu.get('so_tien_de_nghi','')} đồng\n"
        f"      (Nợ gốc: {du_lieu.get('du_no_goc','')} đồng; "
        f"Nợ lãi: {du_lieu.get('lai_ton','')} đồng)\n"
        f"    - Thời gian đề nghị: {du_lieu.get('so_thang','')} tháng\n"
        f"    - Kế hoạch trả nợ: {du_lieu.get('ke_hoach_tra_no','')}"
    )
    doc.add_paragraph(
        "Tôi xin cam đoan và chịu trách nhiệm trước pháp luật về nội dung "
        "kê khai trên đơn và các hồ sơ giấy tờ chứng minh là đúng."
    )

    doc.add_paragraph()
    p_ky = doc.add_paragraph()
    p_ky.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    d_ky = du_lieu.get("ngay_ky", date.today())
    p_ky.add_run(
        f"Ngày {d_ky.day} tháng {d_ky.month} năm {d_ky.year}\n"
        "Người làm đơn\n(Ký, ghi rõ họ tên)\n\n\n\n"
        f"{du_lieu.get('ten_kh','')}"
    )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _tao_word_02xln(du_lieu: dict) -> bytes:
    """Mẫu 02/XLN — Biên bản đề nghị xử lý nợ bị rủi ro (nhiều bên ký)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()
    _style_doc_xln(doc)
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2)

    _add_header_xln(
        doc, dia_danh=du_lieu.get("dia_danh", ""), ngay_ky=du_lieu.get("ngay_lap", date.today())
    )
    if doc.tables:
        cell = doc.tables[0].rows[0].cells[0]
        if cell.paragraphs and cell.paragraphs[0].runs:
            cell.paragraphs[0].runs[0].text = "Mẫu số 02/XLN"
            for rr in cell.paragraphs[0].runs[1:]:
                rr.text = ""
        else:
            cell.text = "Mẫu số 02/XLN"

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run("BIÊN BẢN\nĐề nghị xử lý nợ bị rủi ro").bold = True
    p_ct = doc.add_paragraph(f"(Chương trình {du_lieu.get('ten_ct','')})")
    p_ct.alignment = WD_ALIGN_PARAGRAPH.CENTER

    ngay_lap = du_lieu.get("ngay_lap", date.today())
    doc.add_paragraph(
        f"Hôm nay, ngày {ngay_lap.day} tháng {ngay_lap.month} "
        f"năm {ngay_lap.year}, tại {du_lieu.get('dia_diem','')}, "
        "chúng tôi gồm có:"
    )

    thanh_phan = du_lieu.get("thanh_phan", [])
    for i, tp in enumerate(thanh_phan, 1):
        doc.add_paragraph(
            f"{i}. Ông (bà) {tp.get('ho_ten','')}   "
            f"Chức vụ: {tp.get('chuc_vu','')}   "
            f"Đại diện: {tp.get('dai_dien','')}"
        )
    for i in range(len(thanh_phan) + 1, 8):
        doc.add_paragraph(
            f"{i}. Ông (bà) ....................................   "
            "Chức vụ: ....................   "
            "Đại diện: ......................"
        )

    doc.add_paragraph(
        "Đã tiến hành thẩm tra và lập biên bản đề nghị xử lý nợ bị rủi ro "
        f"của ông (bà): {du_lieu.get('ten_kh','')}  "
        f"địa chỉ: {du_lieu.get('dia_chi','')}\n"
        "Là đại diện hộ gia đình vay vốn NHCSXH theo HĐTD số "
        f"{du_lieu.get('so_ku','')} ngày {du_lieu.get('ngay_vay','')}, "
        f"có mã món vay: {du_lieu.get('so_ku','')}. Cụ thể như sau:"
    )

    p = doc.add_paragraph("I. Nguyên nhân khách hàng bị rủi ro:")
    p.runs[0].bold = True
    doc.add_paragraph(du_lieu.get("nguyen_nhan", ""))

    p = doc.add_paragraph("II. Xác định mức độ thiệt hại về vốn và tài sản:")
    p.runs[0].bold = True
    doc.add_paragraph(
        "1. Số vốn và tài sản bị thiệt hại: "
        f"{du_lieu.get('so_tien_thiet_hai','')} đồng\n"
        f"2. Tổng số vốn thực hiện dự án: {du_lieu.get('muc_vay','')} đồng\n"
        f"3. Đánh giá mức độ thiệt hại: {du_lieu.get('muc_do_thiet_hai','')}%"
    )

    p = doc.add_paragraph("III. Dư nợ tại NHCSXH đến ngày lập biên bản:")
    p.runs[0].bold = True
    doc.add_paragraph(
        f"Tổng số nợ còn phải trả: {du_lieu.get('tong_du_no','')} đồng\n"
        f"    Trong đó:  + Nợ gốc: {du_lieu.get('du_no_goc','')} đồng\n"
        f"               + Nợ lãi: {du_lieu.get('lai_ton','')} đồng"
    )

    p = doc.add_paragraph("IV. Đánh giá thực trạng dự án, tài sản và khả năng trả nợ:")
    p.runs[0].bold = True
    doc.add_paragraph(
        "1. Đánh giá thực trạng dự án / phương án khôi phục:\n"
        f"{du_lieu.get('thuc_trang_du_an','')}\n\n"
        "2. Tài sản hiện tại của khách hàng:\n"
        f"{du_lieu.get('tai_san_hien_tai','')}\n\n"
        "3. Đánh giá khả năng trả nợ:\n"
        f"{du_lieu.get('kha_nang_tra_no','')}\n\n"
        "4. Về việc áp dụng biện pháp thu hồi nợ:\n"
        f"{du_lieu.get('bien_phap_thu_hoi','')}"
    )

    p = doc.add_paragraph("V. Đề xuất biện pháp xử lý:")
    p.runs[0].bold = True
    doc.add_paragraph(
        f"Chúng tôi nhất trí đề nghị NHCSXH xem xét {du_lieu.get('bien_phap','')} "
        f"cho ông (bà) {du_lieu.get('ten_kh','')} với thời gian "
        f"{du_lieu.get('so_thang','')} tháng, số tiền "
        f"{du_lieu.get('so_tien_de_nghi','')} đồng.\n"
        f"    Trong đó:  + Nợ gốc: {du_lieu.get('du_no_goc','')} đồng\n"
        f"               + Nợ lãi: {du_lieu.get('lai_ton','')} đồng\n"
        "Biên bản này lập thành 02 bản có giá trị pháp lý như nhau."
    )

    doc.add_paragraph()
    ky = doc.add_table(rows=1, cols=3)
    ky.style = "Table Grid"
    for cell in ky.rows[0].cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for bn in ["top", "left", "bottom", "right"]:
            b = OxmlElement(f"w:{bn}")
            b.set(qn("w:val"), "none")
            tcBorders.append(b)
        tcPr.append(tcBorders)

    def _ky(cell, nhan: str, ten: str = ""):
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(f"{nhan}\n(Ký, ghi rõ họ tên)\n\n\n\n{ten}")

    _ky(
        ky.rows[0].cells[0],
        "ĐẠI DIỆN KHÁCH HÀNG\nĐẠI DIỆN UBND CẤP XÃ",
        du_lieu.get("ten_kh", ""),
    )
    _ky(ky.rows[0].cells[1], "TỔ TRƯỞNG TỔ TK&VV\nĐẠI DIỆN HỘI ĐOÀN THỂ")
    _ky(
        ky.rows[0].cells[2],
        "CÁN BỘ TÍN DỤNG\nĐẠI DIỆN NHCSXH",
        du_lieu.get("can_bo_td", ""),
    )

    ky2 = doc.add_table(rows=1, cols=2)
    ky2.style = "Table Grid"
    for cell in ky2.rows[0].cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for bn in ["top", "left", "bottom", "right"]:
            b = OxmlElement(f"w:{bn}")
            b.set(qn("w:val"), "none")
            tcBorders.append(b)
        tcPr.append(tcBorders)
    _ky(ky2.rows[0].cells[0], "ĐẠI DIỆN CƠ QUAN CÔNG AN CẤP XÃ\n(Xác nhận, ký tên, đóng dấu)")
    _ky(ky2.rows[0].cells[1], "ĐẠI DIỆN TỔ CHỨC, CÁ NHÂN LIÊN QUAN (nếu có)")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _set_margins(
    doc: Document,
    left_cm: float = 3.0,
    right_cm: float = 2.0,
    top_cm: float = 2.5,
    bottom_cm: float = 2.5,
) -> None:
    for section in doc.sections:
        section.left_margin = Cm(left_cm)
        section.right_margin = Cm(right_cm)
        section.top_margin = Cm(top_cm)
        section.bottom_margin = Cm(bottom_cm)


def _loc_theo_nguon(df_rows: list[dict], nguon: int) -> list[dict]:
    """Lọc danh sách hồ sơ theo nguồn vốn (1=TW, 2=ĐP)."""
    return [r for r in df_rows if int(r.get("nguon_von", 0)) == nguon]


def _tong_hop_khoanh_xoa(ds: list[dict]) -> dict:
    """
    Tính tổng gốc/lãi/số hộ từ danh sách hồ sơ.
    Mỗi phần tử ds có keys: ten_ct, du_no_goc (float), lai_ton (float),
    bien_phap ('Khoanh nợ...' hoặc 'Xóa nợ...'), so_thang (int).
    Trả về dict dùng cho _tao_word_13xln / _tao_word_14xln.
    """
    from collections import defaultdict

    nhom: dict[str, dict] = defaultdict(lambda: {"so_ho": 0, "goc": 0.0, "lai": 0.0})
    for r in ds:
        ct = r.get("ten_ct", "Khác")
        nhom[ct]["so_ho"] += 1
        nhom[ct]["goc"] += float(r.get("du_no_goc", 0) or 0)
        nhom[ct]["lai"] += float(r.get("lai_ton", 0) or 0)
    tong_ho = sum(v["so_ho"] for v in nhom.values())
    tong_goc = sum(v["goc"] for v in nhom.values())
    tong_lai = sum(v["lai"] for v in nhom.values())
    return {
        "nhom_ct": dict(nhom),
        "tong_ho": tong_ho,
        "tong_goc": tong_goc,
        "tong_lai": tong_lai,
        "tong_tien": tong_goc + tong_lai,
    }


def _tao_word_xln_bao_cao(
    tong_hop: dict,
    ten_pgd: str,
    nguon_label: str,
    ngay_bat_dau: date,
    ngay_ket_thuc: date,
    mau_so: str,
    tieu_de: str,
) -> bytes:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def _bo_border_cell(cell) -> None:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for bn in ["top", "left", "bottom", "right"]:
            b = OxmlElement(f"w:{bn}")
            b.set(qn("w:val"), "none")
            tcBorders.append(b)
        tcPr.append(tcBorders)

    def _set_cell(
        cell,
        text: str,
        *,
        bold: bool = False,
        italic: bool = False,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        v_align=WD_ALIGN_VERTICAL.CENTER,
        font_size: int = 10,
    ) -> None:
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = align
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.name = "Times New Roman"
        run.font.size = Pt(font_size)
        cell.vertical_alignment = v_align

    def _set_row_font(row, font_size: int = 10) -> None:
        for cell in row.cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(font_size)

    doc = Document()
    _style_doc_xln(doc)
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width = Cm(27.9)
    sec.page_height = Cm(19.0)
    _set_margins(doc, left_cm=1.5, right_cm=1.5, top_cm=1.5, bottom_cm=1.5)

    p_ms = doc.add_paragraph(f"Mẫu số: {mau_so}")
    p_ms.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    p = doc.add_paragraph("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI")
    if p.runs:
        p.runs[0].bold = True
    if ten_pgd:
        p2 = doc.add_paragraph(f"PGD {ten_pgd}")
        if p2.runs:
            p2.runs[0].bold = True
    else:
        doc.add_paragraph("PGD")

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run(tieu_de)
    r.bold = True

    t2 = doc.add_paragraph(
        "(theo Quyết định số .../QĐ-HĐQT ngày ... tháng ... năm ... của Chủ tịch Hội đồng quản trị NHCSXH)"
    )
    t2.alignment = WD_ALIGN_PARAGRAPH.CENTER

    tu_ngay = ngay_bat_dau.strftime("%d/%m/%Y")
    den_ngay = ngay_ket_thuc.strftime("%d/%m/%Y")
    t3 = doc.add_paragraph(f"Từ ngày {tu_ngay} đến ngày {den_ngay}")
    t3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Nguồn vốn: {nguon_label}")
    doc.add_paragraph("Đơn vị tính: hộ, đồng")

    tbl = doc.add_table(rows=3, cols=15)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdr0 = tbl.rows[0].cells
    hdr1 = tbl.rows[1].cells
    hdr2 = tbl.rows[2].cells

    hdr0[0].merge(hdr2[0])
    hdr0[1].merge(hdr2[1])
    hdr0[14].merge(hdr2[14])

    hdr0[2].merge(hdr0[5])
    hdr0[6].merge(hdr0[9])
    hdr0[10].merge(hdr0[13])

    hdr1[2].merge(hdr2[2])
    hdr1[6].merge(hdr2[6])
    hdr1[10].merge(hdr2[10])

    hdr1[3].merge(hdr1[5])
    hdr1[7].merge(hdr1[9])
    hdr1[11].merge(hdr1[13])

    _set_cell(hdr0[0], "STT", bold=True)
    _set_cell(hdr0[1], "Chi nhánh tỉnh, thành phố", bold=True)
    _set_cell(hdr0[2], "Số được thông báo", bold=True)
    _set_cell(hdr0[6], "Số hạch toán thực tế", bold=True)
    _set_cell(hdr0[10], "Chênh lệch", bold=True)
    _set_cell(hdr0[14], "Nguyên nhân chênh lệch", bold=True)

    _set_cell(hdr1[2], "Số hộ", bold=True)
    _set_cell(hdr1[3], "Số tiền", bold=True)
    _set_cell(hdr1[6], "Số hộ", bold=True)
    _set_cell(hdr1[7], "Số tiền", bold=True)
    _set_cell(hdr1[10], "Số hộ", bold=True)
    _set_cell(hdr1[11], "Số tiền", bold=True)

    _set_cell(hdr2[3], "Tổng", bold=True)
    _set_cell(hdr2[4], "Gốc", bold=True)
    _set_cell(hdr2[5], "Lãi", bold=True)
    _set_cell(hdr2[7], "Tổng", bold=True)
    _set_cell(hdr2[8], "Gốc", bold=True)
    _set_cell(hdr2[9], "Lãi", bold=True)
    _set_cell(hdr2[11], "Tổng", bold=True)
    _set_cell(hdr2[12], "Gốc", bold=True)
    _set_cell(hdr2[13], "Lãi", bold=True)

    _set_row_font(tbl.rows[0], 10)
    _set_row_font(tbl.rows[1], 10)
    _set_row_font(tbl.rows[2], 10)

    stt = 0
    nhom_ct = tong_hop.get("nhom_ct", {}) or {}
    for ten_ct, v in nhom_ct.items():
        row_nhom = tbl.add_row()
        cell_nhom = row_nhom.cells[0].merge(row_nhom.cells[-1])
        _set_cell(
            cell_nhom,
            str(ten_ct),
            bold=True,
            italic=True,
            align=WD_ALIGN_PARAGRAPH.LEFT,
        )

        stt += 1
        so_ho = int(v.get("so_ho", 0) or 0)
        goc = float(v.get("goc", 0) or 0)
        lai = float(v.get("lai", 0) or 0)
        tong = goc + lai

        row = tbl.add_row()
        _set_row_font(row, 10)
        _set_cell(row.cells[0], str(stt), align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell(row.cells[1], ten_pgd or "", align=WD_ALIGN_PARAGRAPH.LEFT)

        _set_cell(row.cells[2], str(so_ho), align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell(row.cells[3], fmt(tong), align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell(row.cells[4], fmt(goc), align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell(row.cells[5], fmt(lai), align=WD_ALIGN_PARAGRAPH.RIGHT)

        _set_cell(row.cells[6], str(so_ho), align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell(row.cells[7], fmt(tong), align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell(row.cells[8], fmt(goc), align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell(row.cells[9], fmt(lai), align=WD_ALIGN_PARAGRAPH.RIGHT)

        _set_cell(row.cells[10], "0", align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell(row.cells[11], "0", align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell(row.cells[12], "0", align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell(row.cells[13], "0", align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell(row.cells[14], "", align=WD_ALIGN_PARAGRAPH.LEFT)

    row_tong = tbl.add_row()
    _set_row_font(row_tong, 10)
    _set_cell(row_tong.cells[0], "", bold=True)
    _set_cell(row_tong.cells[1], "Tổng cộng:", bold=True, align=WD_ALIGN_PARAGRAPH.LEFT)

    tong_ho = int(tong_hop.get("tong_ho", 0) or 0)
    tong_goc = float(tong_hop.get("tong_goc", 0) or 0)
    tong_lai = float(tong_hop.get("tong_lai", 0) or 0)
    tong_tien = tong_goc + tong_lai

    _set_cell(row_tong.cells[2], str(tong_ho), bold=True)
    _set_cell(row_tong.cells[3], fmt(tong_tien), bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    _set_cell(row_tong.cells[4], fmt(tong_goc), bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    _set_cell(row_tong.cells[5], fmt(tong_lai), bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)

    _set_cell(row_tong.cells[6], str(tong_ho), bold=True)
    _set_cell(row_tong.cells[7], fmt(tong_tien), bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    _set_cell(row_tong.cells[8], fmt(tong_goc), bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    _set_cell(row_tong.cells[9], fmt(tong_lai), bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)

    _set_cell(row_tong.cells[10], "0", bold=True)
    _set_cell(row_tong.cells[11], "0", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    _set_cell(row_tong.cells[12], "0", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    _set_cell(row_tong.cells[13], "0", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    _set_cell(row_tong.cells[14], "", bold=True)

    doc.add_paragraph()
    ky = doc.add_table(rows=1, cols=3)
    ky.style = "Table Grid"
    for cell in ky.rows[0].cells:
        _bo_border_cell(cell)
        _set_cell(cell, "", font_size=11)

    _set_cell(ky.rows[0].cells[0], "LẬP BIỂU\n\n\n\n", bold=True, font_size=11)
    _set_cell(ky.rows[0].cells[1], "KIỂM SOÁT\n\n\n\n", bold=True, font_size=11)
    _set_cell(ky.rows[0].cells[2], "GIÁM ĐỐC\n\n\n\n", bold=True, font_size=11)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _tao_word_13xln(
    tong_hop: dict,
    ten_pgd: str,
    nguon_label: str,
    ngay_bat_dau: date,
    ngay_ket_thuc: date,
) -> bytes:
    return _tao_word_xln_bao_cao(
        tong_hop=tong_hop,
        ten_pgd=ten_pgd,
        nguon_label=nguon_label,
        ngay_bat_dau=ngay_bat_dau,
        ngay_ket_thuc=ngay_ket_thuc,
        mau_so="13/XLN",
        tieu_de="BÁO CÁO CÁC KHOẢN NỢ SAU KHI THỰC HIỆN HẠCH TOÁN KHOANH NỢ",
    )


def _tao_word_14xln(
    tong_hop: dict,
    ten_pgd: str,
    nguon_label: str,
    ngay_bat_dau: date,
    ngay_ket_thuc: date,
) -> bytes:
    return _tao_word_xln_bao_cao(
        tong_hop=tong_hop,
        ten_pgd=ten_pgd,
        nguon_label=nguon_label,
        ngay_bat_dau=ngay_bat_dau,
        ngay_ket_thuc=ngay_ket_thuc,
        mau_so="14/XLN",
        tieu_de="BÁO CÁO CÁC KHOẢN NỢ SAU KHI THỰC HIỆN HẠCH TOÁN XÓA NỢ",
    )


def _tao_word_to_trinh(
    tong_hop_khoanh: dict,
    tong_hop_xoa: dict,
    ten_pgd: str,
    nguon_label: str,
    dot: int,
    nam: int,
) -> bytes:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def _bo_border_cell(cell) -> None:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for bn in ["top", "left", "bottom", "right"]:
            b = OxmlElement(f"w:{bn}")
            b.set(qn("w:val"), "none")
            tcBorders.append(b)
        tcPr.append(tcBorders)

    def _p(doc_or_cell, text: str, *, bold: bool = False, align=None) -> None:
        if hasattr(doc_or_cell, "add_paragraph"):
            p = doc_or_cell.add_paragraph(text)
        else:
            p = doc_or_cell.paragraphs[0]
            p.text = text
        if align is not None:
            p.alignment = align
        for run in p.runs:
            run.bold = bold
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)

    doc = Document()
    _style_doc_xln(doc)
    sec = doc.sections[0]
    sec.page_height = Cm(29.7)
    sec.page_width = Cm(21.0)
    _set_margins(doc, left_cm=3.0, right_cm=2.0, top_cm=2.5, bottom_cm=2.5)

    ngay_hn = date.today()
    dia_danh = ten_pgd or "Đồng Nai"

    hdr = doc.add_table(rows=1, cols=2)
    hdr.style = "Table Grid"
    for cell in hdr.rows[0].cells:
        _bo_border_cell(cell)

    cell_l = hdr.rows[0].cells[0]
    cell_r = hdr.rows[0].cells[1]

    p_l = cell_l.paragraphs[0]
    p_l.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_l = p_l.add_run("CHI NHÁNH NHCSXH TỈNH ĐỒNG NAI")
    run_l.bold = True
    run_l.font.name = "Times New Roman"
    run_l.font.size = Pt(12)
    p_l2 = cell_l.add_paragraph(f"PGD {ten_pgd}".strip())
    p_l2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if p_l2.runs:
        p_l2.runs[0].bold = True

    p_r = cell_r.paragraphs[0]
    p_r.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_r = p_r.add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
    run_r.bold = True
    run_r.font.name = "Times New Roman"
    run_r.font.size = Pt(12)
    p_r2 = cell_r.add_paragraph("Độc lập - Tự do - Hạnh phúc")
    p_r2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if p_r2.runs:
        p_r2.runs[0].bold = True

    hdr2 = doc.add_table(rows=1, cols=2)
    hdr2.style = "Table Grid"
    for cell in hdr2.rows[0].cells:
        _bo_border_cell(cell)

    cell2_l = hdr2.rows[0].cells[0]
    cell2_r = hdr2.rows[0].cells[1]
    p2_l = cell2_l.paragraphs[0]
    p2_l.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2_l.add_run("Số: .../TTr-NHCSXH")

    p2_r = cell2_r.paragraphs[0]
    p2_r.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2_r.add_run(
        f"{dia_danh}, ngày {ngay_hn.day} tháng {ngay_hn.month} năm {ngay_hn.year}"
    )

    doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rt = t.add_run("TỜ TRÌNH")
    rt.bold = True
    rt.font.size = Pt(14)
    doc.add_paragraph(
        f"Về việc đề nghị xử lý nợ bị rủi ro đợt {dot} năm {nam}",
    ).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Nguồn vốn: {nguon_label}").alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    doc.add_paragraph(
        "Kính gửi: Giám đốc Chi nhánh Ngân hàng Chính sách xã hội tỉnh Đồng Nai"
    )

    doc.add_paragraph(
        "Căn cứ Quyết định số 62/2015/QĐ-TTg ngày 04/12/2015 của Thủ tướng Chính phủ "
        "về việc xử lý nợ bị rủi ro tại Ngân hàng Chính sách xã hội;"
    )
    doc.add_paragraph(
        "Căn cứ quy định hiện hành của Ngân hàng Chính sách xã hội về xử lý nợ bị rủi ro;"
    )
    doc.add_paragraph(
        f"Phòng giao dịch NHCSXH {ten_pgd} kính trình Giám đốc Chi nhánh NHCSXH tỉnh Đồng Nai "
        f"xem xét, quyết định xử lý nợ bị rủi ro đợt {dot} năm {nam} như sau:"
    )

    so_mon_khoanh = int(tong_hop_khoanh.get("tong_ho", 0) or 0)
    so_mon_xoa = int(tong_hop_xoa.get("tong_ho", 0) or 0)
    so_mon_tong = so_mon_khoanh + so_mon_xoa

    goc_khoanh = float(tong_hop_khoanh.get("tong_goc", 0) or 0)
    lai_khoanh = float(tong_hop_khoanh.get("tong_lai", 0) or 0)
    tien_khoanh = goc_khoanh + lai_khoanh

    goc_xoa = float(tong_hop_xoa.get("tong_goc", 0) or 0)
    lai_xoa = float(tong_hop_xoa.get("tong_lai", 0) or 0)
    tien_xoa = goc_xoa + lai_xoa

    goc_tong = goc_khoanh + goc_xoa
    lai_tong = lai_khoanh + lai_xoa
    tien_tong = goc_tong + lai_tong

    k3 = tong_hop_khoanh.get("khoanh_3y", {}) or {}
    k5 = tong_hop_khoanh.get("khoanh_5y", {}) or {}
    so_mon_k3 = int(k3.get("so_mon", 0) or 0)
    so_mon_k5 = int(k5.get("so_mon", 0) or 0)
    tien_k3 = float(k3.get("tong_tien", 0) or 0)
    tien_k5 = float(k5.get("tong_tien", 0) or 0)

    doc.add_paragraph(
        f"1. Tổng số đề nghị xử lý rủi ro đợt {dot} năm {nam}: {so_mon_tong} món vay, "
        f"số tiền {fmt(tien_tong)} đồng (gốc {fmt(goc_tong)} đồng, lãi {fmt(lai_tong)} đồng). Cụ thể:"
    )
    doc.add_paragraph(
        f"a) Khoanh nợ: {so_mon_khoanh} món vay, số tiền {fmt(tien_khoanh)} đồng, "
        f"gốc {fmt(goc_khoanh)} đồng, lãi {fmt(lai_khoanh)} đồng. Trong đó:"
    )
    doc.add_paragraph(
        f"+ Khoanh nợ tối đa 3 năm: {so_mon_k3} món vay, {fmt(tien_k3)} đồng."
    )
    doc.add_paragraph(
        f"+ Khoanh nợ tối đa 5 năm: {so_mon_k5} món vay, {fmt(tien_k5)} đồng."
    )
    doc.add_paragraph(
        f"b) Xóa nợ: {so_mon_xoa} món vay, số tiền {fmt(tien_xoa)} đồng, "
        f"gốc {fmt(goc_xoa)} đồng, lãi {fmt(lai_xoa)} đồng."
    )
    doc.add_paragraph("(Biểu tổng hợp đề nghị xử lý nợ mẫu số 03, 04, 05/XLN đính kèm)")

    doc.add_paragraph(
        "2. Các khoản nợ bị rủi ro đề nghị xử lý nêu trên đã được Phòng giao dịch rà soát, "
        "đối chiếu hồ sơ, xác định đúng đối tượng và đảm bảo đầy đủ điều kiện theo quy định."
    )
    doc.add_paragraph(
        "3. Phòng giao dịch chịu trách nhiệm trước pháp luật và trước NHCSXH về tính chính xác "
        "của các thông tin, hồ sơ và số liệu báo cáo; đồng thời phối hợp các đơn vị liên quan "
        "tổ chức thực hiện sau khi được cấp có thẩm quyền phê duyệt."
    )

    doc.add_paragraph()
    doc.add_paragraph(f"Phòng giao dịch NHCSXH {ten_pgd} kính trình.").alignment = (
        WD_ALIGN_PARAGRAPH.LEFT
    )

    doc.add_paragraph()
    ky = doc.add_table(rows=1, cols=2)
    ky.style = "Table Grid"
    for cell in ky.rows[0].cells:
        _bo_border_cell(cell)

    ky_l = ky.rows[0].cells[0]
    ky_r = ky.rows[0].cells[1]

    ky_l.text = "Nơi nhận:\n- Như kính gửi;\n- Lưu VT."
    for p in ky_l.paragraphs:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)

    pr = ky_r.paragraphs[0]
    pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = pr.add_run("GIÁM ĐỐC\n(Ký tên, đóng dấu)")
    rr.bold = True
    rr.font.name = "Times New Roman"
    rr.font.size = Pt(12)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _lay_pgd_tu_user(role: str, pgd_user: str | None, df: pd.DataFrame) -> str | None:
    if pgd_user:
        return pgd_user
    if la_phan_he_cn(role) and df is not None and COT_TEN_PGD in df.columns:
        ds = df[COT_TEN_PGD].dropna().unique().tolist()
        if len(ds) == 1:
            return str(ds[0])
    return None


def _loc_df_theo_pgd(df: pd.DataFrame, role: str, pgd_user: str | None) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if la_phan_he_pgd(role) and pgd_user and COT_TEN_PGD in df.columns:
        return df[df[COT_TEN_PGD] == pgd_user].copy()
    return df


def _tao_kv_key(ten_pgd: str) -> str:
    now = datetime.now()
    return f"no_rui_ro_{pgd_slug(ten_pgd)}_{now.year}_{now.month:02d}"


def _hien_thi_chi_tiet(ds: list[dict]) -> None:
    if not ds:
        st.info("ℹ️ Chưa có hồ sơ nào.")
        return
    df_xem = pd.DataFrame(ds)
    cols_xem = [c for c in [
        "ten_kh", "so_ku", "ten_ct", "du_no", "bien_phap",
        "nguyen_nhan", "muc_do", "so_thang", "ngay_rr", "ghi_chu",
    ] if c in df_xem.columns]
    if "du_no" in df_xem.columns:
        df_xem["du_no"] = df_xem["du_no"].apply(lambda x: fmt(x) if pd.notna(x) else "")
    st.dataframe(df_xem[cols_xem], use_container_width=True, hide_index=True)


def render(tab: DeltaGenerator, **kwargs) -> None:
    df = kwargs.get("df")
    role_raw = str(kwargs.get("role", "user") or "user")
    role = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("💳 Xử lý nợ rủi ro — QĐ 62/2015/QĐ-TTg")
        st.caption(
            "Khoanh nợ / Xóa nợ cho hộ vay gặp rủi ro theo Quyết định 62. "
            "Dữ liệu được lưu theo kỳ (tháng hiện tại)."
        )

        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        df = _loc_df_theo_pgd(df, role, pgd_user)
        if df.empty:
            st.warning("⚠️ Không có dữ liệu HSTD cho đơn vị hiện tại.")
            return

        ten_pgd = _lay_pgd_tu_user(role, pgd_user, df)
        kv_key = _tao_kv_key(ten_pgd or "unknown")

        # ── Bước 1: Lọc hộ vay ──────────────────────────────────────────
        with st.expander("🔎 Lọc hộ vay", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df.columns else []
                chon_xa = st.selectbox("Xã/Phường", [""] + ds_xa, key="nrr_xa")
            with c2:
                df_loc = df[df[COT_TEN_XA] == chon_xa] if chon_xa and COT_TEN_XA in df.columns else df
                ds_to = sorted(df_loc[COT_TEN_TO].dropna().unique().tolist()) if COT_TEN_TO in df_loc.columns else []
                chon_to = st.selectbox("Tổ TK&VV", [""] + ds_to, key="nrr_to")
            with c3:
                tim_kh = st.text_input("Tìm tên KH", placeholder="Nhập tên...", key="nrr_tim")

        df_hien = df.copy()
        if chon_xa and COT_TEN_XA in df_hien.columns:
            df_hien = df_hien[df_hien[COT_TEN_XA] == chon_xa]
        if chon_to and COT_TEN_TO in df_hien.columns:
            df_hien = df_hien[df_hien[COT_TEN_TO] == chon_to]
        if tim_kh and COT_TEN_KH in df_hien.columns:
            df_hien = df_hien[df_hien[COT_TEN_KH].str.contains(tim_kh, case=False, na=False)]

        if df_hien.empty:
            st.info("ℹ️ Không tìm thấy hộ vay nào phù hợp.")
            return

        # ── Bước 2: Bảng chọn hộ vay ────────────────────────────────────
        st.markdown("#### 📋 Danh sách hộ vay")
        cot_hien = [c for c in [COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_TONG_DU_NO, COT_DU_NO_QH] if c in df_hien.columns]
        df_editor = df_hien[cot_hien].copy()
        for c in [COT_TONG_DU_NO, COT_DU_NO_QH]:
            if c in df_editor.columns:
                df_editor[c] = df_editor[c].apply(lambda x: fmt(x) if pd.notna(x) else "")
        df_editor.insert(0, "Chọn", False)
        edited = st.data_editor(
            df_editor,
            use_container_width=True,
            hide_index=True,
            height=300,
            column_config={"Chọn": st.column_config.CheckboxColumn("Chọn")},
            key="nrr_editor",
        )
        ds_chon = edited[edited["Chọn"] == True]
        if ds_chon.empty:
            st.info("👆 Tích chọn ít nhất 1 hộ vay để nhập thông tin rủi ro.")
            return
        st.success(f"✅ Đã chọn **{len(ds_chon)}** hộ vay.")

        # ── Bước 3: Form nhập thông tin rủi ro ──────────────────────────
        st.markdown("#### 📝 Thông tin rủi ro")
        with st.form("form_no_rui_ro"):
            col1, col2 = st.columns(2)
            with col1:
                bien_phap = st.selectbox(
                    "Biện pháp xử lý",
                    ["Khoanh nợ (QĐ62)", "Xóa nợ (QĐ62)"],
                    key="nrr_bien_phap",
                )
                nguyen_nhan = st.selectbox(
                    "Nguyên nhân rủi ro",
                    NGUYEN_NHAN_RR,
                    key="nrr_nguyen_nhan",
                )
            with col2:
                ngay_rr = st.date_input(
                    "Ngày xảy ra rủi ro",
                    value=date.today(),
                    key="nrr_ngay_rr",
                )
            muc_do = ""
            so_thang = 0
            if "Khoanh nợ" in bien_phap:
                st.markdown("**Mức độ thiệt hại (khoanh nợ)**")
                mc1, mc2 = st.columns(2)
                with mc1:
                    muc_do = st.radio(
                        "Mức độ thiệt hại",
                        ["Từ 40% đến <80%", "Từ 80% đến 100%", "Không áp dụng"],
                        key="nrr_muc_do",
                    )
                with mc2:
                    goi_y = 60 if "80%" in muc_do else 36
                    so_thang = st.number_input(
                        "Số tháng đề nghị khoanh",
                        min_value=0, max_value=120, value=goi_y, step=6,
                        key="nrr_so_thang",
                        help=f"Gợi ý: {goi_y} tháng theo mức độ đã chọn",
                    )
            ghi_chu = st.text_area(
                "Ghi chú / Tóm tắt nguyên nhân",
                placeholder="Nhập tối thiểu 20 ký tự...",
                height=100,
                key="nrr_ghi_chu",
            )
            submitted = st.form_submit_button("💾 Lưu hồ sơ", type="primary")

        if submitted:
            if len(ghi_chu.strip()) < 20:
                st.error("⚠️ Ghi chú phải có ít nhất 20 ký tự.")
                st.stop()
            ds_luu = []
            for _, row in ds_chon.iterrows():
                ds_luu.append({
                    "ma_kh":       str(row.get(COT_SO_KU, "")),
                    "ten_kh":      str(row.get(COT_TEN_KH, "")),
                    "so_ku":       str(row.get(COT_SO_KU, "")),
                    "ten_ct":      str(row.get(COT_TEN_CT, "")),
                    "du_no":       float(row.get(COT_TONG_DU_NO, 0) or 0),
                    "bien_phap":   bien_phap,
                    "nguyen_nhan": nguyen_nhan,
                    "muc_do":      muc_do,
                    "so_thang":    int(so_thang),
                    "ngay_rr":     ngay_rr.isoformat(),
                    "ghi_chu":     ghi_chu.strip(),
                })
            db.ghi_kv(kv_key, {"danh_sach": ds_luu, "ngay_tao": datetime.now().isoformat()}, username)
            db.ghi_audit(username, "luu_no_rui_ro", f"{len(ds_luu)} hồ sơ — {ten_pgd or 'unknown'}")
            st.cache_data.clear()
            st.success(f"✅ Đã lưu **{len(ds_luu)}** hồ sơ xử lý nợ rủi ro.")
            st.balloons()

        # ── Bước 4: Xuất biểu mẫu ───────────────────────────────────────
        if ds_chon is not None and not ds_chon.empty:
            st.markdown("#### 📄 Xuất biểu mẫu")
            cols_xln = st.columns(2)

            row0 = ds_chon.iloc[0] if not ds_chon.empty else pd.Series()
            so_ku0 = str(row0.get(COT_SO_KU, "")) if hasattr(row0, "get") else ""
            row_src = None
            try:
                if so_ku0 and df is not None and not df.empty and COT_SO_KU in df.columns:
                    df_src = df[df[COT_SO_KU].astype(str) == so_ku0]
                    if not df_src.empty:
                        row_src = df_src.iloc[0]
            except Exception:
                row_src = None
            if row_src is None:
                row_src = row0

            def _num(v) -> float:
                if v is None:
                    return 0.0
                if isinstance(v, (int, float)):
                    return float(v)
                s = str(v).strip()
                if not s:
                    return 0.0
                s = s.replace(" ", "").replace(".", "").replace(",", ".")
                try:
                    return float(s)
                except Exception:
                    return 0.0

            ngay_vay_str = ""
            try:
                nv = pd.to_datetime(row_src.get(COT_NGAY_VAY, ""), errors="coerce", dayfirst=True)
                if pd.notna(nv):
                    ngay_vay_str = nv.strftime("%d/%m/%Y")
            except Exception:
                pass

            ngay_dh_str = ""
            try:
                ndh = pd.to_datetime(row_src.get(COT_NGAY_DH, ""), errors="coerce", dayfirst=True)
                if pd.notna(ndh):
                    ngay_dh_str = ndh.strftime("%d/%m/%Y")
                else:
                    ngay_dh_str = str(row_src.get(COT_NGAY_DH, "") or "")
            except Exception:
                ngay_dh_str = str(row_src.get(COT_NGAY_DH, "") or "")

            du_no_raw = _num(row_src.get(COT_TONG_DU_NO, 0))
            lai_ton_raw = _num(row_src.get(COT_LAI_TON, 0))
            muc_vay_raw = row_src.get(COT_MUC_VAY, du_no_raw) if COT_MUC_VAY in getattr(row_src, "index", []) else du_no_raw
            muc_vay_num = _num(muc_vay_raw)

            du_lieu_xln = {
                "ten_kh": str(row_src.get(COT_TEN_KH, "")),
                "so_ku": so_ku0,
                "ten_ct": str(row_src.get(COT_TEN_CT, "")),
                "muc_vay": fmt(muc_vay_num),
                "tong_du_no": fmt(du_no_raw),
                "du_no_goc": fmt(du_no_raw),
                "lai_ton": fmt(lai_ton_raw),
                "nqh": fmt(_num(row_src.get(COT_DU_NO_QH, 0))),
                "ngay_vay": ngay_vay_str,
                "ngay_dh": ngay_dh_str,
                "ten_to": str(row_src.get(COT_TEN_TO, "")),
                "dia_chi": str(row_src.get(COT_DIA_CHI, "")) if COT_DIA_CHI in getattr(row_src, "index", []) else "",
                "dia_danh": ten_pgd or "",
                "ten_nhcsxh": ten_pgd or "",
                "nguyen_nhan": nguyen_nhan if "nguyen_nhan" in locals() else "",
                "bien_phap": bien_phap if "bien_phap" in locals() else "",
                "so_thang": str(so_thang) if "so_thang" in locals() else "",
                "so_tien_de_nghi": fmt(du_no_raw),
                "so_tien_thiet_hai": fmt(du_no_raw),
                "muc_do_thiet_hai": "",
                "muc_dich_vay": "",
                "kha_nang_tra_no": "",
                "thuc_trang_du_an": "",
                "tai_san_hien_tai": "",
                "bien_phap_thu_hoi": "",
                "ke_hoach_tra_no": "",
                "to_truong": "",
                "dia_diem": ten_pgd or "",
                "can_bo_td": st.session_state.get("username", ""),
                "ngay_ky": date.today(),
                "ngay_lap": date.today(),
                "thanh_phan": [
                    {
                        "stt": 1,
                        "ho_ten": st.session_state.get("username", ""),
                        "chuc_vu": "Cán bộ tín dụng",
                        "dai_dien": ten_pgd or "",
                    },
                    {
                        "stt": 7,
                        "ho_ten": str(row_src.get(COT_TEN_KH, "")),
                        "chuc_vu": "",
                        "dai_dien": "Khách hàng vay vốn",
                    },
                ],
            }

            with cols_xln[0]:
                if st.button(
                    "📄 Xuất 01/XLN (Đơn KH)",
                    use_container_width=True,
                    key="nrr_btn_01xln",
                ):
                    with st.spinner("Đang tạo 01/XLN..."):
                        docx_bytes_01 = _tao_word_01xln(du_lieu_xln)
                    ten_file_01 = f"Mau01XLN_{so_ku0 or 'KH'}_{date.today().strftime('%d%m%Y')}"
                    nut_tai_word_va_pdf(docx_bytes_01, ten_file_01, "nrr_01xln")
                hien_thi_nut_tai("nrr_01xln")

            with cols_xln[1]:
                if st.button(
                    "📄 Xuất 02/XLN (Biên bản)",
                    use_container_width=True,
                    key="nrr_btn_02xln",
                ):
                    with st.spinner("Đang tạo 02/XLN..."):
                        docx_bytes_02 = _tao_word_02xln(du_lieu_xln)
                    ten_file_02 = f"Mau02XLN_{so_ku0 or 'KH'}_{date.today().strftime('%d%m%Y')}"
                    nut_tai_word_va_pdf(docx_bytes_02, ten_file_02, "nrr_02xln")
                hien_thi_nut_tai("nrr_02xln")

            st.markdown("#### 📊 Xuất biểu tổng hợp (13/XLN · 14/XLN · Tờ trình)")

            ds_xuat_full = []
            for _, row in ds_chon.iterrows():
                so_ku_r = str(row.get(COT_SO_KU, ""))
                row_full = row
                if so_ku_r and df is not None and COT_SO_KU in df.columns:
                    df_tmp = df[df[COT_SO_KU].astype(str) == so_ku_r]
                    if not df_tmp.empty:
                        row_full = df_tmp.iloc[0]

                nguon_von_val = row_full.get(COT_NGUON_VON, 0)
                try:
                    nguon_von_int = int(nguon_von_val)
                except (ValueError, TypeError):
                    nguon_von_int = 0

                du_no_goc_r = float(row_full.get(COT_TONG_DU_NO, 0) or 0)
                lai_ton_r = float(row_full.get(COT_LAI_TON, 0) or 0)

                ds_xuat_full.append(
                    {
                        "ten_kh": str(row_full.get(COT_TEN_KH, "")),
                        "so_ku": so_ku_r,
                        "ten_ct": str(row_full.get(COT_TEN_CT, "")),
                        "du_no_goc": du_no_goc_r,
                        "lai_ton": lai_ton_r,
                        "bien_phap": bien_phap if "bien_phap" in locals() else "",
                        "so_thang": int(so_thang) if "so_thang" in locals() else 0,
                        "nguon_von": nguon_von_int,
                    }
                )

            ds_tw = _loc_theo_nguon(ds_xuat_full, NGUON_TW)
            ds_dp = _loc_theo_nguon(ds_xuat_full, NGUON_DP)

            ds_khoanh_tw = [r for r in ds_tw if "Khoanh" in r.get("bien_phap", "")]
            ds_xoa_tw = [r for r in ds_tw if "Xóa" in r.get("bien_phap", "")]
            ds_khoanh_dp = [r for r in ds_dp if "Khoanh" in r.get("bien_phap", "")]
            ds_xoa_dp = [r for r in ds_dp if "Xóa" in r.get("bien_phap", "")]

            def _tinh_khoanh_3y_5y(ds_khoanh: list[dict]) -> tuple[dict, dict]:
                so_mon_3y = 0
                goc_3y = 0.0
                lai_3y = 0.0
                so_mon_5y = 0
                goc_5y = 0.0
                lai_5y = 0.0
                for r in ds_khoanh:
                    so_thang_r = int(r.get("so_thang", 0) or 0)
                    goc_r = float(r.get("du_no_goc", 0) or 0)
                    lai_r = float(r.get("lai_ton", 0) or 0)
                    if so_thang_r <= 36:
                        so_mon_3y += 1
                        goc_3y += goc_r
                        lai_3y += lai_r
                    else:
                        so_mon_5y += 1
                        goc_5y += goc_r
                        lai_5y += lai_r
                return (
                    {"so_mon": so_mon_3y, "tong_tien": goc_3y + lai_3y},
                    {"so_mon": so_mon_5y, "tong_tien": goc_5y + lai_5y},
                )

            ngay_hom_nay = date.today()
            dot_xuat = 1
            nam_xuat = ngay_hom_nay.year

            st.markdown("**📄 13/XLN — Báo cáo khoanh nợ**")
            col13_tw, col13_dp = st.columns(2)
            with col13_tw:
                if st.button(
                    "📥 13/XLN — Trung ương",
                    use_container_width=True,
                    key="nrr_13xln_tw",
                ):
                    if not ds_khoanh_tw:
                        st.warning("⚠️ Không có hồ sơ khoanh nợ nguồn Trung ương.")
                    else:
                        th = _tong_hop_khoanh_xoa(ds_khoanh_tw)
                        k3, k5 = _tinh_khoanh_3y_5y(ds_khoanh_tw)
                        th["khoanh_3y"] = k3
                        th["khoanh_5y"] = k5
                        docx_b = _tao_word_13xln(
                            th, ten_pgd or "", LABEL_TW, ngay_hom_nay, ngay_hom_nay
                        )
                        ten_f = f"Mau13XLN_TW_{ten_pgd or 'PGD'}_{ngay_hom_nay.strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_b, ten_f, "nrr_13xln_tw")
                hien_thi_nut_tai("nrr_13xln_tw")
            with col13_dp:
                if st.button(
                    "📥 13/XLN — Địa phương",
                    use_container_width=True,
                    key="nrr_13xln_dp",
                ):
                    if not ds_khoanh_dp:
                        st.warning("⚠️ Không có hồ sơ khoanh nợ nguồn Địa phương.")
                    else:
                        th = _tong_hop_khoanh_xoa(ds_khoanh_dp)
                        k3, k5 = _tinh_khoanh_3y_5y(ds_khoanh_dp)
                        th["khoanh_3y"] = k3
                        th["khoanh_5y"] = k5
                        docx_b = _tao_word_13xln(
                            th, ten_pgd or "", LABEL_DP, ngay_hom_nay, ngay_hom_nay
                        )
                        ten_f = f"Mau13XLN_DP_{ten_pgd or 'PGD'}_{ngay_hom_nay.strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_b, ten_f, "nrr_13xln_dp")
                hien_thi_nut_tai("nrr_13xln_dp")

            st.markdown("**📄 14/XLN — Báo cáo xóa nợ**")
            col14_tw, col14_dp = st.columns(2)
            with col14_tw:
                if st.button(
                    "📥 14/XLN — Trung ương",
                    use_container_width=True,
                    key="nrr_14xln_tw",
                ):
                    if not ds_xoa_tw:
                        st.warning("⚠️ Không có hồ sơ xóa nợ nguồn Trung ương.")
                    else:
                        th = _tong_hop_khoanh_xoa(ds_xoa_tw)
                        docx_b = _tao_word_14xln(
                            th, ten_pgd or "", LABEL_TW, ngay_hom_nay, ngay_hom_nay
                        )
                        ten_f = f"Mau14XLN_TW_{ten_pgd or 'PGD'}_{ngay_hom_nay.strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_b, ten_f, "nrr_14xln_tw")
                hien_thi_nut_tai("nrr_14xln_tw")
            with col14_dp:
                if st.button(
                    "📥 14/XLN — Địa phương",
                    use_container_width=True,
                    key="nrr_14xln_dp",
                ):
                    if not ds_xoa_dp:
                        st.warning("⚠️ Không có hồ sơ xóa nợ nguồn Địa phương.")
                    else:
                        th = _tong_hop_khoanh_xoa(ds_xoa_dp)
                        docx_b = _tao_word_14xln(
                            th, ten_pgd or "", LABEL_DP, ngay_hom_nay, ngay_hom_nay
                        )
                        ten_f = f"Mau14XLN_DP_{ten_pgd or 'PGD'}_{ngay_hom_nay.strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_b, ten_f, "nrr_14xln_dp")
                hien_thi_nut_tai("nrr_14xln_dp")

            st.markdown("**📄 Tờ trình đề nghị xử lý nợ rủi ro**")
            coltt_tw, coltt_dp = st.columns(2)
            with coltt_tw:
                if st.button(
                    "📥 Tờ trình — Trung ương",
                    use_container_width=True,
                    key="nrr_tt_tw",
                ):
                    if not ds_tw:
                        st.warning("⚠️ Không có hồ sơ nguồn Trung ương.")
                    else:
                        th_k = _tong_hop_khoanh_xoa(ds_khoanh_tw)
                        th_x = _tong_hop_khoanh_xoa(ds_xoa_tw)
                        k3, k5 = _tinh_khoanh_3y_5y(ds_khoanh_tw)
                        th_k["khoanh_3y"] = k3
                        th_k["khoanh_5y"] = k5
                        docx_b = _tao_word_to_trinh(
                            th_k, th_x, ten_pgd or "", LABEL_TW, dot_xuat, nam_xuat
                        )
                        ten_f = f"ToTrinh_TW_{ten_pgd or 'PGD'}_{ngay_hom_nay.strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_b, ten_f, "nrr_tt_tw")
                hien_thi_nut_tai("nrr_tt_tw")
            with coltt_dp:
                if st.button(
                    "📥 Tờ trình — Địa phương",
                    use_container_width=True,
                    key="nrr_tt_dp",
                ):
                    if not ds_dp:
                        st.warning("⚠️ Không có hồ sơ nguồn Địa phương.")
                    else:
                        th_k = _tong_hop_khoanh_xoa(ds_khoanh_dp)
                        th_x = _tong_hop_khoanh_xoa(ds_xoa_dp)
                        k3, k5 = _tinh_khoanh_3y_5y(ds_khoanh_dp)
                        th_k["khoanh_3y"] = k3
                        th_k["khoanh_5y"] = k5
                        docx_b = _tao_word_to_trinh(
                            th_k, th_x, ten_pgd or "", LABEL_DP, dot_xuat, nam_xuat
                        )
                        ten_f = f"ToTrinh_DP_{ten_pgd or 'PGD'}_{ngay_hom_nay.strftime('%d%m%Y')}"
                        nut_tai_word_va_pdf(docx_b, ten_f, "nrr_tt_dp")
                hien_thi_nut_tai("nrr_tt_dp")

        # ── Bước 5: Xem lại hồ sơ đã lưu ─────────────────────────────────
        st.markdown("---")
        with st.expander("📋 Hồ sơ đã lập kỳ này", expanded=False):
            du_lieu_cu = db.doc_kv(kv_key)
            if du_lieu_cu and "danh_sach" in du_lieu_cu:
                ds_cu = du_lieu_cu["danh_sach"]
                st.caption(f"🕐 {du_lieu_cu.get('ngay_tao', '')} — {len(ds_cu)} hồ sơ")
                _hien_thi_chi_tiet(ds_cu)
                if st.button("🗑️ Xóa bản ghi", key="nrr_btn_xoa", type="secondary"):
                    st.session_state["nrr_xac_nhan_xoa"] = True
                if st.session_state.get("nrr_xac_nhan_xoa"):
                    st.warning("⚠️ Bạn có chắc chắn muốn xóa toàn bộ hồ sơ kỳ này?")
                    c_xc1, c_xc2 = st.columns(2)
                    with c_xc1:
                        if st.button("✅ Xác nhận xóa", key="nrr_btn_xac_nhan"):
                            db.ghi_kv(kv_key, {}, username)
                            db.ghi_audit(username, "xoa_no_rui_ro",
                                         f"Xóa {len(ds_cu)} hồ sơ — {ten_pgd or 'unknown'}")
                            st.session_state.pop("nrr_xac_nhan_xoa", None)
                            st.cache_data.clear()
                            st.success("✅ Đã xóa hồ sơ.")
                            st.rerun()
                    with c_xc2:
                        if st.button("❌ Hủy", key="nrr_btn_huy"):
                            st.session_state.pop("nrr_xac_nhan_xoa", None)
                            st.rerun()
            else:
                st.info("ℹ️ Chưa có hồ sơ nào trong kỳ này.")
