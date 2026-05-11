"""Tab Ủy thác — Theo dõi Hội đoàn thể và các mẫu biểu kiểm tra."""
from __future__ import annotations
import io, pickle
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from streamlit.delta_generator import DeltaGenerator

from config import (
    COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON, COT_LAI_TON_QH,
    COT_SO_DU_TG, COT_NGAY_VAY, COT_TEN_TO, COT_DVUT,
    COT_TEN_XA, COT_TEN_THON, COT_MUC_VAY,
    TEN_CHI_NHANH_HIEN_THI,
)
from utils import fmt, fmt_bang_ty, fmt_so, xuat_excel
from services.template_service import (
    co_template, dien_template, nut_tai_word_va_pdf, docx_bytes_to_pdf,
    TMPL_MAU06, TMPL_MAU06A, TMPL_MAU15, TMPL_MAU16, TMPL_KH_KT
)

# ── Hằng số ──────────────────────────────────────────────────────────────────
DVUT_ORDER = [
    "Hội nông dân",
    "Hội liên hiệp phụ nữ",
    "Hội cựu chiến binh",
    "Đoàn thanh niên",
]


# ══════════════════════════════════════════════════════════════════════════════
# CACHE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=300)
def _tinh_theo_dvut(_df_bytes: bytes) -> bytes:
    df = pickle.loads(_df_bytes)
    if COT_DVUT not in df.columns:
        return pickle.dumps(pd.DataFrame())
    agg = {}
    if COT_TEN_TO      in df.columns: agg["so_to"]   = (COT_TEN_TO,     "nunique")
    if COT_SO_KU       in df.columns: agg["so_kh"]   = (COT_SO_KU,      "nunique")
    if COT_TONG_DU_NO  in df.columns: agg["tong_dn"] = (COT_TONG_DU_NO, "sum")
    if COT_DU_NO_QH    in df.columns: agg["nqh"]     = (COT_DU_NO_QH,   "sum")
    if COT_LAI_TON     in df.columns: agg["lai_ton"] = (COT_LAI_TON,    "sum")
    if not agg:
        return pickle.dumps(pd.DataFrame())
    t = df.groupby(COT_DVUT).agg(**agg).reset_index()
    t["_ord"] = t[COT_DVUT].apply(
        lambda x: DVUT_ORDER.index(x) if x in DVUT_ORDER else 99)
    return pickle.dumps(t.sort_values("_ord").drop(columns="_ord"))


@st.cache_data(show_spinner=False, ttl=300)
def _loc_mau06(_df_bytes: bytes, ngay_tu: str, ngay_den: str) -> bytes:
    df = pickle.loads(_df_bytes)
    if COT_NGAY_VAY not in df.columns:
        return pickle.dumps(pd.DataFrame())
    ngay_vay = pd.to_datetime(df[COT_NGAY_VAY], errors="coerce")
    mask = (ngay_vay >= pd.Timestamp(ngay_tu)) & \
           (ngay_vay <= pd.Timestamp(ngay_den))
    cols = [c for c in [
        COT_TEN_TO, COT_DVUT, COT_TEN_XA, COT_TEN_KH,
        COT_SO_KU, COT_TEN_CT, COT_NGAY_VAY, COT_MUC_VAY,
        COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON,
    ] if c in df.columns]
    result = df.loc[mask, cols].copy()
    return pickle.dumps(result.sort_values(COT_NGAY_VAY, ascending=False))


@st.cache_data(show_spinner=False, ttl=300)
def _loc_mau15(_df_bytes: bytes, ten_to: str) -> bytes:
    df = pickle.loads(_df_bytes)
    if COT_TEN_TO not in df.columns:
        return pickle.dumps(pd.DataFrame())
    df_to = df[df[COT_TEN_TO] == ten_to].copy()
    # Tính nợ lãi = Lãi tồn TH + Lãi tồn QH
    if COT_LAI_TON in df_to.columns and COT_LAI_TON_QH in df_to.columns:
        df_to["Nợ lãi"] = df_to[COT_LAI_TON].fillna(0) + \
                           df_to[COT_LAI_TON_QH].fillna(0)
    elif COT_LAI_TON in df_to.columns:
        df_to["Nợ lãi"] = df_to[COT_LAI_TON].fillna(0)
    else:
        df_to["Nợ lãi"] = 0
    cols = [c for c in [
        COT_TEN_KH, COT_TEN_CT, COT_SO_KU,
        COT_TONG_DU_NO, "Nợ lãi", COT_SO_DU_TG,
    ] if c in df_to.columns or c == "Nợ lãi"]
    return pickle.dumps(df_to[cols].reset_index(drop=True))


# ══════════════════════════════════════════════════════════════════════════════
# WORD EXPORT FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _style_doc(doc: Document) -> None:
    """Thiết lập font mặc định cho toàn bộ document."""
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)


def _add_header_quoc_hieu(doc: Document, don_vi: str, so_vb: str,
                           dia_danh: str, ngay_ky: date) -> None:
    """Thêm phần Quốc hiệu, Tiêu ngữ, số VB chuẩn hành chính."""
    t = doc.add_table(rows=1, cols=2)
    t.style = "Table Grid"
    # Bỏ border
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    for cell in t.rows[0].cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for border_name in ["top", "left", "bottom", "right"]:
            border = OxmlElement(f"w:{border_name}")
            border.set(qn("w:val"), "none")
            tcBorders.append(border)
        tcPr.append(tcBorders)

    # Cột trái: Đơn vị + Số VB
    cell_l = t.rows[0].cells[0]
    p = cell_l.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run((don_vi or "").upper())
    run.bold = True
    run.font.size = Pt(12)
    p2 = cell_l.add_paragraph(f"Số: {so_vb}")
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Cột phải: Quốc hiệu
    cell_r = t.rows[0].cells[1]
    p3 = cell_r.paragraphs[0]
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run3 = p3.add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
    run3.bold = True
    run3.font.size = Pt(12)
    p4 = cell_r.add_paragraph("Độc lập - Tự do - Hạnh phúc")
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run4 = p4.runs[0] if p4.runs else p4.add_run("Độc lập - Tự do - Hạnh phúc")
    run4.bold = True

    p5 = cell_r.add_paragraph(
        f"{dia_danh}, ngày {ngay_ky.day} tháng {ngay_ky.month} "
        f"năm {ngay_ky.year}"
    )
    p5.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()


def _tao_word_ke_hoach(du_lieu: dict, ds_to: list) -> bytes:
    """Tạo file Word Kế hoạch kiểm tra giám sát ủy thác."""
    doc = Document()
    _style_doc(doc)
    # Lề trang
    for section in doc.sections:
        section.top_margin    = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin   = Cm(3)
        section.right_margin  = Cm(2)

    _add_header_quoc_hieu(
        doc,
        don_vi   = du_lieu.get("don_vi_kt", ""),
        so_vb    = du_lieu.get("so_vb", ""),
        dia_danh = du_lieu.get("dia_danh", ""),
        ngay_ky  = du_lieu.get("ngay_ky", date.today()),
    )

    # Tiêu đề
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = title.add_run(
        f"KẾ HOẠCH\nKiểm tra giám sát hoạt động ủy thác "
        f"năm {du_lieu.get('nam_kh', date.today().year)}"
    )
    run_t.bold = True
    run_t.font.size = Pt(13)
    doc.add_paragraph(
        f"Căn cứ văn bản số 727/HD-NHCS ngày 11/02/2026 của Tổng Giám đốc NHCSXH;"
    )

    # I. Mục đích yêu cầu
    doc.add_paragraph("I. MỤC ĐÍCH, YÊU CẦU").runs[0].bold = True
    doc.add_paragraph(f"1. Mục đích\n{du_lieu.get('muc_dich','')}")
    doc.add_paragraph(f"2. Yêu cầu\n{du_lieu.get('yeu_cau','')}")

    # II. Kế hoạch kiểm tra
    doc.add_paragraph("II. KẾ HOẠCH KIỂM TRA").runs[0].bold = True
    doc.add_paragraph(
        f"1. Nội dung, thời hiệu kiểm tra\n{du_lieu.get('noi_dung_kt','')}"
    )

    # Bảng đối tượng kiểm tra từ hệ thống
    doc.add_paragraph("2. Đối tượng được kiểm tra")
    if ds_to:
        tbl = doc.add_table(rows=1, cols=4)
        tbl.style = "Table Grid"
        hdrs = ["STT", "Hội đoàn thể", "Xã/Phường", "Tên Tổ TK&VV"]
        for i, h in enumerate(hdrs):
            cell = tbl.rows[0].cells[i]
            cell.text = h
            cell.paragraphs[0].runs[0].bold = True
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for idx, to in enumerate(ds_to, 1):
            row = tbl.add_row()
            row.cells[0].text = str(idx)
            row.cells[1].text = str(to.get(COT_DVUT, ""))
            row.cells[2].text = str(to.get(COT_TEN_XA, ""))
            row.cells[3].text = str(to.get(COT_TEN_TO, ""))
        doc.add_paragraph()

    doc.add_paragraph(
        f"3. Thành phần Đoàn kiểm tra\n{du_lieu.get('thanh_phan','')}"
    )

    # III. Kế hoạch giám sát
    doc.add_paragraph("III. KẾ HOẠCH GIÁM SÁT").runs[0].bold = True
    doc.add_paragraph(
        f"1. Nội dung, thời hiệu giám sát\n{du_lieu.get('noi_dung_gs','')}"
    )
    doc.add_paragraph(
        f"2. Phân công cán bộ giám sát\n{du_lieu.get('phan_cong_gs','')}"
    )

    # IV. Tổ chức thực hiện
    doc.add_paragraph("IV. TỔ CHỨC THỰC HIỆN").runs[0].bold = True
    doc.add_paragraph(du_lieu.get("to_chuc", ""))

    # Ký tên
    doc.add_paragraph()
    ky = doc.add_table(rows=1, cols=2)
    ky.style = "Table Grid"
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    for cell in ky.rows[0].cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for border_name in ["top","left","bottom","right"]:
            border = OxmlElement(f"w:{border_name}")
            border.set(qn("w:val"), "none")
            tcBorders.append(border)
        tcPr.append(tcBorders)
    ky.rows[0].cells[0].text = "Nơi nhận:\n- NHCSXH;\n- Lưu: VT."
    p_ky = ky.rows[0].cells[1].paragraphs[0]
    p_ky.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ky.add_run("CHỦ TỊCH\n(Ký, ghi rõ họ tên)\n\n\n\n").bold = True
    p_ky.add_run(du_lieu.get("chu_tich", ""))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _tao_word_mau15(du_lieu: dict, df_to: pd.DataFrame) -> bytes:
    """Tạo file Word Mẫu 15/TD — Danh sách đối chiếu số dư."""
    doc = Document()
    _style_doc(doc)
    for section in doc.sections:
        section.top_margin    = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin   = Cm(2)
        section.right_margin  = Cm(1.5)
        section.page_width    = Cm(29.7)  # A4 ngang
        section.page_height   = Cm(21)

    # Header
    _add_header_quoc_hieu(
        doc,
        don_vi   = du_lieu.get("pgd", ""),
        so_vb    = "15/TD",
        dia_danh = du_lieu.get("ten_xa", ""),
        ngay_ky  = du_lieu.get("ngay_chot", date.today()),
    )

    # Tiêu đề
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = title.add_run("DANH SÁCH ĐỐI CHIẾU SỐ DƯ TIỀN VAY VÀ TIỀN GỬI")
    run_t.bold = True
    run_t.font.size = Pt(13)
    doc.add_paragraph(
        f"Đến ngày {du_lieu.get('ngay_chot', date.today()).strftime('%d/%m/%Y')}"
    ).alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(
        f"Tổ trưởng: {du_lieu.get('to_truong','')}    "
        f"Mã Tổ: {du_lieu.get('ma_to','')}    "
        f"Địa chỉ: {du_lieu.get('dia_chi','')}"
    )
    doc.add_paragraph("Đơn vị tính: đồng")

    # Bảng dữ liệu
    headers = [
        "STT", "Họ và tên KH / Chương trình", "Mã khoản vay",
        "Nợ gốc (NH)", "Nợ lãi (NH)", "Số dư TG (NH)",
        "Nợ gốc (KH)", "Nợ lãi (KH)", "Số dư TG (KH)",
        "CL Nợ gốc", "CL Nợ lãi", "CL Số dư TG",
        "Nguyên nhân CL", "Chữ ký KH",
    ]
    tbl = doc.add_table(rows=2, cols=len(headers))
    tbl.style = "Table Grid"

    # Dòng header số thứ tự cột
    for i, h in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].bold = True
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cell.paragraphs[0].runs[0].font.size = Pt(9)

    stt_row = tbl.rows[1]
    for i in range(len(headers)):
        stt_row.cells[i].text = str(i + 1)
        stt_row.cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        stt_row.cells[i].paragraphs[0].runs[0].font.size = Pt(9)

    # Dữ liệu
    tong_goc = tong_lai = tong_tg = 0
    for idx, row in df_to.iterrows():
        r = tbl.add_row()
        ten_kh = str(row.get(COT_TEN_KH, ""))
        ten_ct = str(row.get(COT_TEN_CT, ""))
        ma_ku  = str(row.get(COT_SO_KU, ""))
        goc    = float(row.get(COT_TONG_DU_NO, 0) or 0)
        lai    = float(row.get("Nợ lãi", 0) or 0)
        tg     = float(row.get(COT_SO_DU_TG, 0) or 0)
        tong_goc += goc
        tong_lai += lai
        tong_tg  += tg

        vals = [
            str(idx + 1),
            f"{ten_kh}\n{ten_ct}",
            ma_ku,
            f"{goc:,.0f}", f"{lai:,.0f}", f"{tg:,.0f}",
            "", "", "",   # cột KH điền tay
            "", "", "",   # cột chênh lệch
            "",           # nguyên nhân
            "",           # chữ ký
        ]
        for i, v in enumerate(vals):
            r.cells[i].text = v
            r.cells[i].paragraphs[0].runs[0].font.size = Pt(9)

    # Dòng tổng cộng
    r_tong = tbl.add_row()
    r_tong.cells[0].merge(r_tong.cells[2])
    r_tong.cells[0].text = "Tổng cộng"
    r_tong.cells[0].paragraphs[0].runs[0].bold = True
    r_tong.cells[3].text = f"{tong_goc:,.0f}"
    r_tong.cells[4].text = f"{tong_lai:,.0f}"
    r_tong.cells[5].text = f"{tong_tg:,.0f}"

    doc.add_paragraph()
    # Ký tên
    p_kt = doc.add_paragraph()
    p_kt.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_kt.add_run(
        "CÁN BỘ ĐỐI CHIẾU\n(Ký, ghi rõ họ tên)\n\n\n\n"
        f"{du_lieu.get('can_bo_kt','')}"
    ).bold = True

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _tao_word_mau06(du_lieu: dict, df_m06: pd.DataFrame,
                    loai: str = "06") -> bytes:
    """Tạo file Word Mẫu 06/TD hoặc 06A/TD."""
    doc = Document()
    _style_doc(doc)
    for section in doc.sections:
        section.top_margin    = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin   = Cm(2)
        section.right_margin  = Cm(1.5)
        section.page_width    = Cm(29.7)
        section.page_height   = Cm(21)

    # Header
    tbl_h = doc.add_table(rows=1, cols=2)
    tbl_h.style = "Table Grid"
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    for cell in tbl_h.rows[0].cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for bn in ["top","left","bottom","right"]:
            b = OxmlElement(f"w:{bn}")
            b.set(qn("w:val"), "none")
            tcBorders.append(b)
        tcPr.append(tcBorders)

    tbl_h.rows[0].cells[0].text = (
        f"Đơn vị kiểm tra: {du_lieu.get('don_vi_kt','')}\n"
        f"{du_lieu.get('ten_xa','')}"
    )
    p_r = tbl_h.rows[0].cells[1].paragraphs[0]
    p_r.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_r.add_run(f"Mẫu số: {loai}/TD\nLập 02 liên:\n"
                "- 01 liên chính lưu NH;\n"
                "- 01 liên phô tô lưu Đ.v k.tra")

    # Tiêu đề
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("PHIẾU KIỂM TRA SỬ DỤNG VỐN VAY").bold = True

    # Thông tin đoàn kiểm tra
    ngay_kt = du_lieu.get("ngay_kt", date.today())
    doc.add_paragraph(
        f"Người kiểm tra: 1. {du_lieu.get('can_bo_1','')}   "
        f"Chức vụ: {du_lieu.get('chuc_vu_1','')}\n"
        f"                        2. {du_lieu.get('can_bo_2','')}   "
        f"Chức vụ: {du_lieu.get('chuc_vu_2','')}"
    )
    doc.add_paragraph(
        f"Thời điểm kiểm tra: ............   "
        f"Địa bàn kiểm tra: {du_lieu.get('dia_ban','')}   "
        f"Tổ TK&VV: {du_lieu.get('ten_to','')}"
    )
    doc.add_paragraph("Đơn vị tính: triệu đồng")

    if loai == "06":
        # Mẫu 06 — bảng nhiều KH
        headers = [
            "STT", "Họ và tên người vay",
            "Mã khoản vay", "Chương trình cho vay",
            "Số tiền giải ngân", "Dư nợ đến ngày KT",
            "Mục đích sử dụng vốn",
            "Tổng tiền thực nhận", "Dư nợ thực tế",
            "Vào việc", "Số tiền đúng MĐ", "Số tiền sai MĐ",
            "Hiệu quả ĐT", "Nợ lãi", "Chữ ký KH",
        ]
        tbl = doc.add_table(rows=1, cols=len(headers))
        tbl.style = "Table Grid"
        for i, h in enumerate(headers):
            c = tbl.rows[0].cells[i]
            c.text = h
            c.paragraphs[0].runs[0].bold = True
            c.paragraphs[0].runs[0].font.size = Pt(8)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        tong_gn = tong_dn = 0
        for idx, row in df_m06.iterrows():
            r = tbl.add_row()
            gn = float(row.get(COT_MUC_VAY, 0) or 0)
            dn = float(row.get(COT_TONG_DU_NO, 0) or 0)
            tong_gn += gn
            tong_dn += dn
            vals = [
                str(idx + 1),
                str(row.get(COT_TEN_KH, "")),
                str(row.get(COT_SO_KU, "")),
                str(row.get(COT_TEN_CT, "")),
                f"{gn:,.0f}", f"{dn:,.0f}",
                str(row.get("Mục đích sử dụng vốn vay", "")),
                "", "", "", "", "", "", "", "",
            ]
            for i, v in enumerate(vals):
                r.cells[i].text = v
                r.cells[i].paragraphs[0].runs[0].font.size = Pt(8)

        # Dòng cộng
        r_c = tbl.add_row()
        r_c.cells[0].merge(r_c.cells[3])
        r_c.cells[0].text = "Cộng"
        r_c.cells[0].paragraphs[0].runs[0].bold = True
        r_c.cells[4].text = f"{tong_gn:,.0f}"
        r_c.cells[5].text = f"{tong_dn:,.0f}"

    else:
        # Mẫu 06A — từng KH riêng lẻ, lấy KH đầu tiên
        if not df_m06.empty:
            row = df_m06.iloc[0]
            doc.add_paragraph(
                f"Họ và tên: {row.get(COT_TEN_KH,'')}\n"
                f"Mã khoản vay: {row.get(COT_SO_KU,'')}\n"
                f"Chương trình: {row.get(COT_TEN_CT,'')}\n"
                f"Số tiền giải ngân: {row.get(COT_MUC_VAY,0):,.0f} đồng\n"
                f"Dư nợ gốc: {row.get(COT_TONG_DU_NO,0):,.0f} đồng\n"
                f"Nợ lãi: {row.get('Nợ lãi',0):,.0f} đồng\n"
                f"Số dư tiền gửi TK: {row.get(COT_SO_DU_TG,0):,.0f} đồng"
            )
            doc.add_paragraph("Mục đích vay vốn: "
                               + str(row.get("Mục đích sử dụng vốn vay","")))
            doc.add_paragraph("Thực tế sử dụng vốn:\n"
                               "- Sử dụng đúng mục đích: ............... đồng\n"
                               "- Sử dụng sai mục đích: ................. đồng")
            doc.add_paragraph("Hiệu quả đầu tư: ................................")
            doc.add_paragraph("Khả năng trả nợ: ................................")

    # Nhận xét
    doc.add_paragraph(
        "\nNhận xét:\n"
        "1. Tình hình thực hiện phương án: ........................................\n"
        "2. Kiểm tra, đối chiếu thực tế được ........ KH, số tiền ........ đồng.\n"
        "Biện pháp xử lý: ............................................................"
    )

    # Ký tên
    doc.add_paragraph()
    ky = doc.add_table(rows=1, cols=2)
    ky.style = "Table Grid"
    for cell in ky.rows[0].cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement("w:tcBorders")
        for bn in ["top","left","bottom","right"]:
            b = OxmlElement(f"w:{bn}")
            b.set(qn("w:val"), "none")
            tcBorders.append(b)
        tcPr.append(tcBorders)
    ky.rows[0].cells[0].text = (
        "CÁN BỘ CHỨNG KIẾN (nếu có)\n(Ký, ghi rõ họ tên)\n\n\n"
    )
    p_r2 = ky.rows[0].cells[1].paragraphs[0]
    p_r2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_r2.add_run(
        f"Ngày {ngay_kt.day} tháng {ngay_kt.month} năm {ngay_kt.year}\n"
        "CÁN BỘ KIỂM TRA\n(Ký, ghi rõ họ tên)\n\n\n"
        f"{du_lieu.get('can_bo_1','')}"
    )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TAB RENDERERS
# ══════════════════════════════════════════════════════════════════════════════

def _render_theo_dvut(df: pd.DataFrame) -> None:
    st.markdown("#### 📊 Thống kê theo Hội đoàn thể")
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu."); return
    try:
        t = pickle.loads(_tinh_theo_dvut(pickle.dumps(df)))
    except Exception as e:
        st.error(f"Lỗi: {e}"); return
    if t.empty:
        st.info("Không có dữ liệu."); return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hội đoàn thể", len(t))
    c2.metric("Tổng Tổ TK&VV", fmt_so(int(t.get("so_to", pd.Series([0])).sum())))
    c3.metric("Tổng KH", fmt_so(int(t.get("so_kh", pd.Series([0])).sum())))
    c4.metric("Tổng dư nợ (tr.đ)", fmt(t.get("tong_dn", pd.Series([0])).sum()))
    st.divider()
    hien = t.rename(columns={
        COT_DVUT: "Hội đoàn thể", "so_to": "Số Tổ",
        "so_kh": "Số KH", "tong_dn": "Dư nợ (tr.đ)",
        "nqh": "NQH (tr.đ)", "lai_ton": "Lãi tồn (tr.đ)",
    })
    for col in ["Dư nợ (tr.đ)", "NQH (tr.đ)", "Lãi tồn (tr.đ)"]:
        if col in hien.columns:
            hien[col] = hien[col].apply(fmt)
    st.dataframe(hien, use_container_width=True, hide_index=True)


def _render_ke_hoach(df: pd.DataFrame, pgd_user: str) -> None:
    st.markdown("#### 📋 Kế hoạch kiểm tra giám sát ủy thác")
    st.caption("Hội đoàn thể cấp xã lập (PGD) hoặc cấp tỉnh lập (CN). "
               "Danh sách Tổ TK&VV tự động lấy từ hệ thống.")

    # Lấy danh sách Tổ từ df
    ds_to = []
    if df is not None and not df.empty:
        grp = [c for c in [COT_DVUT, COT_TEN_XA, COT_TEN_TO] if c in df.columns]
        if grp:
            ds_to = (df[grp].drop_duplicates()
                     .sort_values(grp).to_dict("records"))

    with st.form("form_ke_hoach_kt"):
        c1, c2 = st.columns(2)
        don_vi_kt = c1.selectbox(
            "Hội đoàn thể kiểm tra",
            options=DVUT_ORDER,
            key="kh_don_vi_kt"
        )
        so_vb      = c1.text_input("Số văn bản", placeholder="VD: 12/KH-HND")
        ds_xa_kh = sorted(df[COT_TEN_XA].dropna().unique().tolist()) \
                   if df is not None and COT_TEN_XA in df.columns else []
        dia_danh = c1.selectbox(
            "Địa danh (xã/phường)",
            options=ds_xa_kh,
            key="kh_dia_danh",
            help="Xã/phường nơi Hội đóng trụ sở — dùng làm địa danh ký văn bản"
        )
        nam_kh     = c2.number_input("Năm kế hoạch",
                                      value=date.today().year,
                                      min_value=2020, max_value=2035, step=1)
        ngay_ky    = c2.date_input("Ngày ký", value=date.today())
        chu_tich   = c2.text_input("Chủ tịch ký",
                                    placeholder="Họ và tên Chủ tịch Hội")

        st.markdown("**I. Mục đích, yêu cầu**")
        muc_dich   = st.text_area("Mục đích", height=70)
        yeu_cau    = st.text_area("Yêu cầu", height=70)

        st.markdown("**II. Kế hoạch kiểm tra**")
        noi_dung_kt = st.text_area("Nội dung, thời hiệu kiểm tra", height=70)
        thanh_phan  = st.text_area("Thành phần Đoàn kiểm tra", height=60)
        st.info(f"📋 Hệ thống tìm thấy **{len(ds_to)}** Tổ TK&VV "
                f"— sẽ tự động điền vào bảng Đối tượng kiểm tra.")

        st.markdown("**III. Kế hoạch giám sát**")
        noi_dung_gs  = st.text_area("Nội dung, thời hiệu giám sát", height=70)
        phan_cong_gs = st.text_area("Phân công cán bộ giám sát", height=60)

        st.markdown("**IV. Tổ chức thực hiện**")
        to_chuc = st.text_area("Tổ chức thực hiện", height=60)

        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        # Build context cho template Kế hoạch kiểm tra
        context = {
            "don_vi_kt":   don_vi_kt,
            "so_vb":       so_vb,
            "dia_danh":    dia_danh,
            "nam_kh":      int(nam_kh),
            "ngay_ky":     ngay_ky.strftime("%d/%m/%Y"),
            "ngay":        ngay_ky.day,
            "thang":       ngay_ky.month,
            "nam":         ngay_ky.year,
            "muc_dich":    muc_dich,
            "yeu_cau":     yeu_cau,
            "noi_dung_kt": noi_dung_kt,
            "thanh_phan":  thanh_phan,
            "noi_dung_gs": noi_dung_gs,
            "phan_cong_gs": phan_cong_gs,
            "to_chuc":     to_chuc,
            "chu_tich":    chu_tich,
            "so_to":       len(ds_to),
            "ds_to":       ds_to,
        }

        if co_template(TMPL_KH_KT):
            with st.spinner("Đang tạo file..."):
                docx_bytes = dien_template(TMPL_KH_KT, context)
            ten_file = f"KH_KiemTra_UyThac_{int(nam_kh)}_{don_vi_kt[:20].replace(' ','_')}"
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "⬇️ Tải Word (.docx)",
                    data=docx_bytes,
                    file_name=ten_file + ".docx",
                    mime="application/vnd.openxmlformats-officedocument"
                         ".wordprocessingml.document",
                    key="kh_docx",
                )
            with col2:
                with st.spinner("Đang tạo PDF..."):
                    pdf_bytes = docx_bytes_to_pdf(docx_bytes)
                if pdf_bytes:
                    st.download_button(
                        "⬇️ Tải PDF",
                        data=pdf_bytes,
                        file_name=ten_file + ".pdf",
                        mime="application/pdf",
                        key="kh_pdf",
                    )
                else:
                    st.caption("⚠️ PDF không khả dụng — cần MS Word trên server")
        else:
            st.warning(
                f"⚠️ Chưa có template '{TMPL_KH_KT}' trong thư mục templates/. "
                f"Vui lòng upload file Word mẫu chuẩn vào thư mục này."
            )


def _render_mau06(df: pd.DataFrame, pgd_user: str) -> None:
    st.markdown("#### 📋 Mẫu 06/TD & 06A/TD — Phiếu kiểm tra sử dụng vốn")
    st.caption("Quy định: kiểm tra 100% món vay trong 30 ngày sau giải ngân. "
               "Thời điểm kiểm tra cụ thể do CBTD nhập khi đi thực địa.")
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return
    if COT_NGAY_VAY not in df.columns:
        st.warning(f"Không tìm thấy cột '{COT_NGAY_VAY}'."); return

    c1, c2 = st.columns(2)
    loai_mau = c1.radio("Loại mẫu", ["06/TD (bảng nhiều KH)",
                                       "06A/TD (từng KH riêng)"],
                         key="m06_loai")
    so_ngay  = c2.slider("Giải ngân trong N ngày qua", 7, 30, 30,
                          key="m06_ngay")
    st.caption("Ngày kiểm tra thực tế do Cán bộ hội đi kiểm tra ghi vào mẫu.")

    ngay_den = date.today()
    ngay_tu  = date.today() - timedelta(days=so_ngay)
    st.caption(f"📅 {ngay_tu.strftime('%d/%m/%Y')} → {ngay_den.strftime('%d/%m/%Y')}")

    try:
        raw    = _loc_mau06(pickle.dumps(df), str(ngay_tu), str(ngay_den))
        df_m06 = pickle.loads(raw)
    except Exception as e:
        st.error(f"Lỗi: {e}"); return

    if df_m06.empty:
        st.success("✅ Không có món vay nào cần kiểm tra."); return

    tong_dn = df_m06[COT_TONG_DU_NO].sum() \
              if COT_TONG_DU_NO in df_m06.columns else 0
    ca, cb  = st.columns(2)
    ca.metric("Số món cần KT", fmt_so(len(df_m06)))
    cb.metric("Tổng dư nợ (tr.đ)", fmt(tong_dn))
    st.dataframe(df_m06, use_container_width=True,
                 hide_index=True, height=300)

    # Form thông tin người kiểm tra
    with st.form("form_xuat_m06"):
        st.markdown("**Thông tin xuất mẫu:**")
        f1, f2 = st.columns(2)
        don_vi_kt = f1.selectbox(
            "Hội đoàn thể kiểm tra",
            options=DVUT_ORDER,
            key="m06_don_vi_kt"
        )
        ds_xa_m06 = [""] + sorted(df_m06[COT_TEN_XA].dropna().unique().tolist()) \
                    if COT_TEN_XA in df_m06.columns else [""]
        ten_xa = f1.selectbox(
            "Xã/Phường",
            options=ds_xa_m06,
            key="m06_ten_xa"
        )
        # Lọc Tổ theo Xã đã chọn (dùng session_state vì trong form)
        ten_xa_filter = st.session_state.get("m06_ten_xa", "")
        df_to_filter = df_m06[df_m06[COT_TEN_XA] == ten_xa_filter] \
                       if ten_xa_filter and COT_TEN_XA in df_m06.columns else df_m06
        ds_to_m06 = [""] + sorted(df_to_filter[COT_TEN_TO].dropna().unique().tolist()) \
                    if COT_TEN_TO in df_to_filter.columns else [""]
        ten_to = f1.selectbox(
            "Tổ TK&VV",
            options=ds_to_m06,
            key="m06_chon_to"
        )
        can_bo_1  = f2.text_input("Cán bộ kiểm tra 1")
        chuc_vu_1 = f2.text_input("Chức vụ 1")
        can_bo_2  = f2.text_input("Cán bộ kiểm tra 2 (nếu có)")
        dia_ban   = f2.text_input("Địa bàn kiểm tra",
                                   placeholder="Ấp..., xã...")
        ngay_kt   = f2.date_input("Ngày kiểm tra",
                                   value=date.today(), key="m06_ngay_kt")
        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        df_xuat = df_m06.copy()
        if ten_to:
            df_xuat = df_xuat[df_xuat[COT_TEN_TO] == ten_to] \
                      if COT_TEN_TO in df_xuat.columns else df_xuat
        # Tính Nợ lãi
        if COT_LAI_TON in df_xuat.columns and COT_LAI_TON_QH in df_xuat.columns:
            df_xuat["Nợ lãi"] = (df_xuat[COT_LAI_TON].fillna(0) +
                                  df_xuat[COT_LAI_TON_QH].fillna(0))
        # Build context cho template
        ds_kh = []
        for i, (_, row) in enumerate(df_xuat.iterrows(), 1):
            ds_kh.append({
                "stt":      i,
                "ten_kh":  str(row.get(COT_TEN_KH, "")),
                "so_ku":   str(row.get(COT_SO_KU, "")),
                "ten_ct":  str(row.get(COT_TEN_CT, "")),
                "muc_vay": fmt(row.get(COT_MUC_VAY, 0)),
                "du_no":   fmt(row.get(COT_TONG_DU_NO, 0)),
                "muc_dich": str(row.get("Mục đích sử dụng vốn vay", "")),
                "no_lai":  fmt(row.get("Nợ lãi", 0)),
            })
        context = {
            "don_vi_kt":   don_vi_kt,
            "ten_xa":      ten_xa,
            "ten_to":      ten_to,
            "can_bo_1":    can_bo_1,
            "chuc_vu_1":   chuc_vu_1,
            "can_bo_2":    can_bo_2,
            "dia_ban":     dia_ban,
            "ngay_kt":     ngay_kt.strftime("%d/%m/%Y"),
            "ngay":        ngay_kt.day,
            "thang":       ngay_kt.month,
            "nam":         ngay_kt.year,
            "so_kh_kt":    len(df_xuat),
            "ds_kh":       ds_kh,
            "tong_muc_vay": fmt(df_xuat[COT_MUC_VAY].sum()
                               if COT_MUC_VAY in df_xuat.columns else 0),
            "tong_du_no":  fmt(df_xuat[COT_TONG_DU_NO].sum()
                               if COT_TONG_DU_NO in df_xuat.columns else 0),
        }
        tmpl = TMPL_MAU06 if "06/TD" in loai_mau else TMPL_MAU06A

        if co_template(tmpl):
            with st.spinner("Đang tạo file..."):
                docx_bytes = dien_template(tmpl, context)
            ten_file = f"Mau06TD_{pgd_user}_{ngay_kt.strftime('%d%m%Y')}"
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "⬇️ Tải Word (.docx)",
                    data=docx_bytes,
                    file_name=ten_file + ".docx",
                    mime="application/vnd.openxmlformats-officedocument"
                         ".wordprocessingml.document",
                    key="m06_docx",
                )
            with col2:
                with st.spinner("Đang tạo PDF..."):
                    pdf_bytes = docx_bytes_to_pdf(docx_bytes)
                if pdf_bytes:
                    st.download_button(
                        "⬇️ Tải PDF",
                        data=pdf_bytes,
                        file_name=ten_file + ".pdf",
                        mime="application/pdf",
                        key="m06_pdf",
                    )
                else:
                    st.caption("⚠️ PDF không khả dụng — cần MS Word trên server")
        else:
            st.warning(
                f"⚠️ Chưa có template '{tmpl}' trong thư mục templates/. "
                f"Vui lòng upload file Word mẫu chuẩn vào thư mục này."
            )


def _render_mau15(df: pd.DataFrame, pgd_user: str) -> None:
    st.markdown("#### 📋 Mẫu 15/TD — Danh sách đối chiếu số dư")
    st.caption("Đối chiếu nợ gốc, nợ lãi, số dư tiền gửi TK từng tổ viên.")
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD."); return

    # Chọn Tổ TK&VV
    ds_to = sorted(df[COT_TEN_TO].dropna().unique().tolist()) \
            if COT_TEN_TO in df.columns else []
    if not ds_to:
        st.warning("Không có dữ liệu Tổ TK&VV."); return

    c1, c2 = st.columns(2)
    chon_dvut = c1.selectbox("Hội đoàn thể", ["Tất cả"] + DVUT_ORDER,
                               key="m15_dvut")
    # Lọc Tổ theo DVUT
    df_filter = df.copy()
    if chon_dvut != "Tất cả" and COT_DVUT in df_filter.columns:
        df_filter = df_filter[df_filter[COT_DVUT] == chon_dvut]
    ds_to_filter = sorted(df_filter[COT_TEN_TO].dropna().unique().tolist()) \
                   if COT_TEN_TO in df_filter.columns else []
    chon_to = c2.selectbox("Tổ TK&VV", ds_to_filter, key="m15_to")

    if not chon_to:
        st.info("Chọn Tổ TK&VV để xem dữ liệu."); return

    try:
        df_to = pickle.loads(_loc_mau15(pickle.dumps(df), chon_to))
    except Exception as e:
        st.error(f"Lỗi: {e}"); return

    if df_to.empty:
        st.info(f"Không có dữ liệu cho Tổ **{chon_to}**."); return

    # KPI
    tong_goc = df_to[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_to.columns else 0
    tong_lai = df_to["Nợ lãi"].sum() if "Nợ lãi" in df_to.columns else 0
    tong_tg  = df_to[COT_SO_DU_TG].sum() if COT_SO_DU_TG in df_to.columns else 0
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Số KH", fmt_so(len(df_to)))
    k2.metric("Tổng nợ gốc (tr.đ)", fmt(tong_goc))
    k3.metric("Tổng nợ lãi (tr.đ)", fmt(tong_lai))
    k4.metric("Tổng TG TK (tr.đ)", fmt(tong_tg))
    st.dataframe(df_to, use_container_width=True, hide_index=True, height=350)

    # Tự động lấy xã và tổ trưởng từ Tổ đang chọn
    xa_cua_to = ""
    ten_to_truong = ""
    if chon_to:
        if COT_TEN_XA in df.columns and COT_TEN_TO in df.columns:
            s_xa = df[df[COT_TEN_TO] == chon_to][COT_TEN_XA].dropna()
            xa_cua_to = s_xa.iloc[0] if not s_xa.empty else ""
        for cot in ["Tên Tổ trưởng", "Tổ trưởng", "Họ tên Tổ trưởng"]:
            if cot in df.columns:
                s_tt = df[df[COT_TEN_TO] == chon_to][cot].dropna()
                ten_to_truong = str(s_tt.iloc[0]) if not s_tt.empty else ""
                break

    # Form xuất Word
    with st.form("form_xuat_m15"):
        st.markdown("**Thông tin xuất mẫu:**")
        f1, f2 = st.columns(2)
        pgd = f1.text_input(
            "PGD",
            value=pgd_user,
            disabled=True,
            key="m15_pgd"
        )
        ten_xa = f1.text_input(
            "Xã/Phường",
            value=xa_cua_to,
            disabled=True,
            help="Tự động lấy theo Tổ TK&VV đã chọn",
            key="m15_ten_xa"
        )
        to_truong = f1.text_input(
            "Tổ trưởng",
            value=ten_to_truong,
            help="Tự động lấy từ HSTD, có thể sửa lại nếu cần",
            key="m15_to_truong"
        )
        ma_to     = f1.text_input("Mã Tổ")
        dia_chi   = f2.text_input("Địa chỉ Tổ")
        can_bo_kt = f2.text_input("Cán bộ đối chiếu")
        ngay_chot = f2.date_input("Ngày chốt số liệu", value=date.today(),
                                   key="m15_ngay_chot")
        submitted = st.form_submit_button("📄 Tạo Word")

    if submitted:
        # Build context cho template Mẫu 15/TD
        context = {
            "pgd":         pgd,
            "ten_xa":      ten_xa,
            "ten_to":      chon_to,
            "to_truong":   to_truong,
            "ma_to":       ma_to,
            "dia_chi":     dia_chi,
            "can_bo_kt":   can_bo_kt,
            "ngay_chot":   ngay_chot.strftime("%d/%m/%Y"),
            "ngay":        ngay_chot.day,
            "thang":       ngay_chot.month,
            "nam":         ngay_chot.year,
            "tong_du_no":  fmt(tong_goc),
            "tong_lai":    fmt(tong_lai),
            "tong_tg":     fmt(tong_tg),
            "so_kh":       len(df_to),
            "ds_kh": [
                {
                    "stt":    i,
                    "ten_kh": str(row.get(COT_TEN_KH, "")),
                    "ten_ct": str(row.get(COT_TEN_CT, "")),
                    "so_ku":  str(row.get(COT_SO_KU, "")),
                    "du_no":  fmt(row.get(COT_TONG_DU_NO, 0)),
                    "lai":    fmt(row.get("Nợ lãi", 0)),
                    "tg":     fmt(row.get(COT_SO_DU_TG, 0)),
                }
                for i, (_, row) in enumerate(df_to.iterrows(), 1)
            ],
        }

        if co_template(TMPL_MAU15):
            with st.spinner("Đang tạo file..."):
                docx_bytes = dien_template(TMPL_MAU15, context)
            ten_file = f"Mau15TD_{chon_to.replace(' ','_')}_{ngay_chot.strftime('%d%m%Y')}"
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "⬇️ Tải Word (.docx)",
                    data=docx_bytes,
                    file_name=ten_file + ".docx",
                    mime="application/vnd.openxmlformats-officedocument"
                         ".wordprocessingml.document",
                    key="m15_docx",
                )
            with col2:
                with st.spinner("Đang tạo PDF..."):
                    pdf_bytes = docx_bytes_to_pdf(docx_bytes)
                if pdf_bytes:
                    st.download_button(
                        "⬇️ Tải PDF",
                        data=pdf_bytes,
                        file_name=ten_file + ".pdf",
                        mime="application/pdf",
                        key="m15_pdf",
                    )
                else:
                    st.caption("⚠️ PDF không khả dụng — cần MS Word trên server")
        else:
            st.warning(
                f"⚠️ Chưa có template '{TMPL_MAU15}' trong thư mục templates/. "
                f"Vui lòng upload file Word mẫu chuẩn vào thư mục này."
            )


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def render(tab: DeltaGenerator, **kwargs) -> None:
    """Entry point — dùng chung cho ws_operation và ws_management."""
    df       = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")

    with tab:
        st.subheader("🤝 Ủy thác — Hội đoàn thể")
        st.caption(
            "Theo dõi hoạt động ủy thác và các mẫu biểu kiểm tra "
            "theo văn bản 727/HD-NHCS."
        )
        sub1, sub2, sub3, sub4, sub5 = st.tabs([
            "📊 Theo Hội đoàn thể",
            "📋 Kế hoạch kiểm tra",
            "📋 Mẫu 06/TD & 06A/TD",
            "📋 Mẫu 15/TD",
            "📋 Biên bản & Báo cáo",
        ])
        with sub1: _render_theo_dvut(df)
        with sub2: _render_ke_hoach(df, pgd_user)
        with sub3: _render_mau06(df, pgd_user)
        with sub4: _render_mau15(df, pgd_user)
        with sub5:
            st.info("🚧 Đang phát triển — Biên bản kiểm tra CT-XH cấp tỉnh, "
                    "cấp xã, Tổ TK&VV, Biên bản xác minh nợ chiếm dụng "
                    "và Báo cáo tổng hợp.")
