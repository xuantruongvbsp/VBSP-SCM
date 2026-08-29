"""Export PDF nâng cao - hỗ trợ kèm biểu đồ."""

from __future__ import annotations

from io import BytesIO
from datetime import datetime
from numbers import Number
from pathlib import Path
from typing import Sequence
from xml.sax.saxutils import escape as xml_escape

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from config import TEN_CHI_NHANH_HIEN_THI

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm, mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable, Image as RLImage, PageBreak,
    )
    from reportlab.platypus import Table as RLTable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    import plotly.io as pio
    _REPORTLAB_READY = True
except ImportError:
    _REPORTLAB_READY = False

FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"
FONT_BOLD_ITALIC = "Helvetica-BoldOblique"
_FONT_REGISTERED = False


def _dang_ky_font():
    global FONT_NORMAL, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC, _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    try:
        from pathlib import Path
        candidates_regular = [
            Path(__file__).parent.parent / "assets" / "times.ttf",
            Path("assets/times.ttf"),
            Path("C:/Windows/Fonts/times.ttf"),
        ]
        candidates_bold = [
            Path(__file__).parent.parent / "assets" / "timesbd.ttf",
            Path("assets/timesbd.ttf"),
            Path("C:/Windows/Fonts/timesbd.ttf"),
        ]
        candidates_italic = [
            Path(__file__).parent.parent / "assets" / "timesi.ttf",
            Path("assets/timesi.ttf"),
            Path("C:/Windows/Fonts/timesi.ttf"),
        ]
        candidates_bi = [
            Path(__file__).parent.parent / "assets" / "timesbi.ttf",
            Path("assets/timesbi.ttf"),
            Path("C:/Windows/Fonts/timesbi.ttf"),
        ]
        regular = next((p for p in candidates_regular if p.exists()), None)
        bold = next((p for p in candidates_bold if p.exists()), None)
        italic = next((p for p in candidates_italic if p.exists()), None)
        bolditalic = next((p for p in candidates_bi if p.exists()), None)
        if regular:
            pdfmetrics.registerFont(TTFont("TNR", str(regular)))
            FONT_NORMAL = "TNR"
        if bold:
            pdfmetrics.registerFont(TTFont("TNR-Bold", str(bold)))
            FONT_BOLD = "TNR-Bold"
        if italic:
            pdfmetrics.registerFont(TTFont("TNR-Italic", str(italic)))
            FONT_ITALIC = "TNR-Italic"
        if bolditalic:
            pdfmetrics.registerFont(TTFont("TNR-BoldItalic", str(bolditalic)))
            FONT_BOLD_ITALIC = "TNR-BoldItalic"
    except Exception:
        pass
    _FONT_REGISTERED = True


if _REPORTLAB_READY:
    VBSP_GREEN = colors.HexColor("#1B5E20")
    VBSP_GREEN_LIGHT = colors.HexColor("#C8E6C9")
    VBSP_GREEN_MID = colors.HexColor("#4CAF50")
    ROW_ALT = colors.HexColor("#F8F9FA")
    BORDER_COLOR = colors.HexColor("#90A4AE")
    BORDER_STRONG = colors.HexColor("#455A64")
    TEXT_MUTED = colors.HexColor("#607D8B")
    TEXT_DARK = colors.HexColor("#263238")
else:
    VBSP_GREEN = None
    VBSP_GREEN_LIGHT = None
    VBSP_GREEN_MID = None
    ROW_ALT = None
    BORDER_COLOR = None
    BORDER_STRONG = None
    TEXT_MUTED = None
    TEXT_DARK = None

LOGO_CANDIDATES = [
    Path(__file__).parent.parent / "assets" / "logo.png",
    Path(__file__).parent.parent / "logo.png",
    Path(__file__).parent.parent / "logo-vbsp.jpg",
]


def _tim_logo() -> str | None:
    for p in LOGO_CANDIDATES:
        if p.exists():
            return str(p)
    return None


def _pdf_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).replace("\u2013", "-").replace("\u2014", "-")
    return xml_escape(text)


def _is_number(value: object) -> bool:
    return isinstance(value, Number) and not isinstance(value, bool)


def _format_phan_tram(val: float | int | str) -> str:
    try:
        v = float(val)
        return f"{v:,.2f} %".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(val) if pd.notna(val) else ""


def _format_number_pdf(value: object, col_name: object = "") -> str:
    from utils import fmt_so

    c = str(col_name).casefold()
    if "tỷ lệ" in c or "%" in c:
        return _format_phan_tram(value).replace(" %", "")
    if _is_number(value):
        return fmt_so(float(value))
    num = float(str(value).strip().replace(".", "").replace(",", "."))
    return fmt_so(num)


def _ve_header(elements: list, tieu_de: str, nguoi_xuat: str, usable_w: float) -> str:
    """Vẽ header báo cáo PDF: logo NHCSXH + tiêu đề + meta. Trả về ngay_str."""
    from reportlab.platypus import Table as RLTable

    logo_path = _tim_logo()
    style_bank = ParagraphStyle(
        "BankName", fontName=FONT_BOLD, fontSize=12,
        alignment=TA_CENTER, leading=15, spaceAfter=0,
    )
    style_meta = ParagraphStyle(
        "Meta", fontName=FONT_NORMAL, fontSize=9,
        alignment=TA_CENTER, textColor=TEXT_MUTED, spaceAfter=6,
    )
    style_report_title = ParagraphStyle(
        "ReportTitle", fontName=FONT_BOLD, fontSize=14,
        alignment=TA_CENTER, textColor=VBSP_GREEN, spaceAfter=4, leading=18,
    )

    bank_text = (
        "<b>NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM</b><br/>"
        f"<font size='10'>{xml_escape(TEN_CHI_NHANH_HIEN_THI)}</font>"
    )

    if logo_path:
        try:
            logo = RLImage(logo_path, width=2.0 * cm, height=2.0 * cm)
            header_tbl = RLTable(
                [[logo, Paragraph(bank_text, style_bank)]],
                colWidths=[2.4 * cm, usable_w - 2.4 * cm],
            )
            header_tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            elements.append(header_tbl)
        except Exception:
            elements.append(Paragraph(bank_text, style_bank))
    else:
        elements.append(Paragraph(bank_text, style_bank))

    elements.append(Spacer(1, 0.15 * cm))
    elements.append(HRFlowable(
        width="100%", thickness=2, color=VBSP_GREEN, spaceAfter=0.2 * cm,
    ))
    elements.append(HRFlowable(
        width="100%", thickness=0.5, color=VBSP_GREEN_MID, spaceAfter=0.4 * cm,
    ))
    elements.append(Paragraph(_pdf_text(tieu_de.upper()), style_report_title))
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    elements.append(Paragraph(
        f"Ngày xuất: {now_str}  ·  Người xuất: {_pdf_text(nguoi_xuat)}  ·  Nguồn: Hệ thống HSTD VBSP-SCM",
        style_meta,
    ))
    elements.append(Spacer(1, 0.3 * cm))
    return now_str


def fig_to_bytes(fig: go.Figure, width: int = 800, height: int = 400) -> bytes | None:
    """Chuyển Plotly figure thành PNG bytes để nhúng vào PDF."""
    try:
        return pio.to_image(fig, format="png", width=width, height=height, scale=2)
    except Exception:
        return None


def xuat_pdf_co_chart(
    df: pd.DataFrame,
    tieu_de: str,
    nguoi_xuat: str,
    figs: Sequence[tuple[go.Figure, str]] | None = None,
    cols_tien: list[str] | None = None,
    don_vi_tien: str = "đồng",
    prefix_file: str = "",
    them_dong_tong: bool = True,
    them_ngay_xuat: bool = True,
    cols_percent: list[str] | None = None,
    cols_dem: list[str] | None = None,
) -> bytes:
    """Xuất PDF kèm biểu đồ.

    Args:
        df: DataFrame dữ liệu
        tieu_de: Tiêu đề báo cáo
        nguoi_xuat: Người xuất
        figs: List các tuple (figure, caption)
        cols_tien: Danh sách cột tiền để format
        don_vi_tien: Đơn vị tiền tệ
        prefix_file: Tiền tố tên file
        them_dong_tong: Thêm dòng tổng cộng
        them_ngay_xuat: Thêm ngày xuất
        cols_percent: Danh sách cột phần trăm
        cols_dem: Danh sách cột số đếm (số KH, số món...)

    Returns:
        bytes: Nội dung file PDF
    """
    if not _REPORTLAB_READY:
        st.error("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
        return b""

    _dang_ky_font()

    cols_tien = cols_tien or []
    cols_percent = cols_percent or []
    cols_dem = cols_dem or []
    if df is None:
        df = pd.DataFrame()
    cols = list(df.columns) if not df.empty else []
    n_cols = len(cols)
    is_landscape = n_cols >= 6 or prefix_file == "TQPGD"
    page_size = landscape(A4) if is_landscape else A4
    margin = 1.2 * cm

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=2 * cm,
        title=tieu_de,
        author=f"VBSP-SCM - {TEN_CHI_NHANH_HIEN_THI}",
    )

    fn = FONT_NORMAL
    fb = FONT_BOLD
    fi = FONT_ITALIC

    if n_cols <= 5:
        font_size = 10
    elif n_cols <= 8:
        font_size = 9.5
    elif n_cols <= 12:
        font_size = 9
    elif n_cols <= 16:
        font_size = 8
    else:
        font_size = 7.5
    header_font_size = font_size + 1.5

    style_caption = ParagraphStyle(
        "Caption", fontName=fi, fontSize=9,
        alignment=TA_CENTER, spaceBefore=4, spaceAfter=10, textColor=TEXT_MUTED,
    )
    style_footer = ParagraphStyle(
        "Footer", fontName=fi, fontSize=8.5,
        alignment=TA_LEFT, textColor=TEXT_MUTED,
    )

    elements = []

    # ── Header (Logo NHCSXH + Tiêu đề) ──
    usable_w = page_size[0] - 2 * margin
    ngay_str = _ve_header(elements, tieu_de, nguoi_xuat, usable_w)

    def _is_left_align(col_name: str) -> bool:
        c = str(col_name).lower()
        left_keywords = ("chỉ tiêu", "chi tiêu", "đơn vị", "tiêu chí", "tieu chi",
                         "tên ", "ten ", "họ ", "ho ", "chương trình", "chuong trinh",
                         "xã", "xa", "huyện", "tỉnh", "thôn", "thon")
        return (any(k in c for k in left_keywords) or c == str(cols[0]).lower()) if cols else False

    def _is_center_align(col_name: str) -> bool:
        c = str(col_name).lower()
        return c in ("stt",) or any(k in c for k in ("xếp loại", "xep loai"))

    def _col_ratio(col_name: str) -> float:
        c = str(col_name).strip().lower()
        if c in ("stt",):
            return 0.45
        if any(k in c for k in ("tiêu chí", "tieu chi", "chỉ tiêu", "chi tiêu", "đơn vị")):
            return 2.8
        if any(k in c for k in ("tổ trưởng", "to truong", "họ tên", "ho ten")):
            return 2.2
        if any(k in c for k in ("xếp loại", "xep loai")):
            return 1.3
        if any(k in c for k in ("mã tổ", "ma to", "mã pgd", "ma pgd")):
            return 1.15
        if any(k in c for k in ("chương trình", "chuong trinh", "tên ct", "ten ct")):
            return 2.5
        if any(k in c for k in ("tên xã", "ten xa", "tên pgd", "ten pgd",
                                 "tên thôn", "ten thon", "huyện", "tỉnh")):
            return 2.0
        if any(k in c for k in ("mã kh", "ma kh", "số ku", "so ku", "số khế", "so khe", "cmnd", "cccd")):
            return 1.6
        if any(k in c for k in ("tên kh", "ten kh", "khách hàng", "khach hang")):
            return 2.15
        if any(k in c for k in ("tỷ lệ", "tl ", "%", "tỷ trọng", "ty trong")):
            return 0.9
        if any(k in c for k in ("bq/kh", "số kh", "so kh", "số món", "so mon",
                                 "món qh", "mon qh")):
            return 0.9
        if any(k in c for k in ("dư nợ", "du no", "trong hạn", "qua hạn",
                                 "quá hạn", "khoanh", "lãi", "tiền")):
            return 1.75
        return 1.3

    # ── Biểu đồ ──
    if figs:
        for fig, caption in figs:
            img_bytes = fig_to_bytes(fig)
            if img_bytes:
                img_w = usable_w
                img_h = img_w * 0.42
                img = RLImage(BytesIO(img_bytes), width=img_w, height=img_h)
                elements.append(img)
                if caption:
                    elements.append(Paragraph(caption, style_caption))
                elements.append(Spacer(1, 0.4 * cm))
            else:
                elements.append(Paragraph(f"[Không thể render biểu đồ: {caption}]", style_caption))

    # ── Bảng dữ liệu ──
    if cols:
        elements.append(Spacer(1, 0.2 * cm))

        header_style = ParagraphStyle(
            "Header2", fontName=fb, fontSize=header_font_size,
            alignment=TA_CENTER, textColor=colors.white, leading=header_font_size + 4,
        )
        headers = [Paragraph(_pdf_text(str(c).replace("_", " ")), header_style) for c in cols]

        cell_right_style = ParagraphStyle(
            "CellR", fontName=fn, fontSize=font_size,
            alignment=TA_RIGHT, leading=font_size + 3,
        )
        cell_left_style = ParagraphStyle(
            "CellL", fontName=fn, fontSize=font_size,
            alignment=TA_LEFT, leading=font_size + 3, wordWrap="CJK",
        )
        cell_center_style = ParagraphStyle(
            "CellC", fontName=fn, fontSize=font_size,
            alignment=TA_CENTER, leading=font_size + 3, wordWrap="CJK",
        )

        data_rows = []
        for _, row in df.iterrows():
            cells = []
            for i, c in enumerate(cols):
                val = row[c]
                if pd.isna(val):
                    p = Paragraph(
                        "",
                        cell_left_style if _is_left_align(c) else cell_right_style,
                    )
                elif c in cols_percent:
                    txt = _pdf_text(_format_phan_tram(val))
                    p = Paragraph(txt, cell_right_style)
                elif c in cols_tien:
                    try:
                        txt = _format_number_pdf(val, c)
                    except (ValueError, TypeError):
                        txt = _pdf_text(val)
                    p = Paragraph(txt, cell_right_style)
                elif c in cols_dem:
                    try:
                        txt = _format_number_pdf(val, c)
                    except (ValueError, TypeError):
                        txt = _pdf_text(val)
                    p = Paragraph(txt, cell_right_style)
                else:
                    txt = _pdf_text(val)
                    if _is_left_align(c):
                        p = Paragraph(txt, cell_left_style)
                    elif _is_center_align(c):
                        p = Paragraph(txt, cell_center_style)
                    else:
                        p = Paragraph(txt, cell_left_style)
                cells.append(p)
            data_rows.append(cells)

        has_tong = them_dong_tong and cols_tien and len(df) > 0
        if has_tong:
            tong_row_cells = []
            tong_right_style = ParagraphStyle(
                "TongR", fontName=fb, fontSize=font_size,
                alignment=TA_RIGHT, leading=font_size + 3, textColor=VBSP_GREEN,
            )
            tong_center_style = ParagraphStyle(
                "TongC", fontName=fb, fontSize=font_size,
                alignment=TA_CENTER, leading=font_size + 3, textColor=VBSP_GREEN,
            )
            tong_left_style = ParagraphStyle(
                "TongL", fontName=fb, fontSize=font_size,
                alignment=TA_LEFT, leading=font_size + 3, textColor=VBSP_GREEN,
            )
            for i, c in enumerate(cols):
                if c in cols_percent:
                    try:
                        tong = pd.to_numeric(df[c], errors="coerce").mean()
                        txt = f"<b>{_pdf_text(_format_phan_tram(tong))}</b>"
                    except Exception:
                        txt = ""
                    tong_row_cells.append(Paragraph(txt, tong_right_style))
                elif c in cols_tien:
                    try:
                        tong = pd.to_numeric(df[c], errors="coerce").sum()
                        txt = f"<b>{_pdf_text(_format_number_pdf(tong, c))}</b>"
                    except Exception:
                        txt = ""
                    tong_row_cells.append(Paragraph(txt, tong_right_style))
                elif c in cols_dem:
                    try:
                        tong = pd.to_numeric(df[c], errors="coerce").sum()
                        txt = f"<b>{_pdf_text(_format_number_pdf(tong, c))}</b>"
                    except Exception:
                        txt = ""
                    tong_row_cells.append(Paragraph(txt, tong_right_style))
                elif i == 0:
                    tong_row_cells.append(Paragraph("<b>TỔNG CỘNG</b>", tong_center_style))
                else:
                    tong_row_cells.append(Paragraph("", tong_left_style))
            data_rows.append(tong_row_cells)

        table_data = [headers] + data_rows

        ratios = [_col_ratio(c) for c in cols]
        total_ratio = sum(ratios)
        col_widths = [usable_w * r / total_ratio for r in ratios]

        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), fb),
            ("FONTSIZE", (0, 0), (-1, 0), header_font_size),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, 0), 0.5, BORDER_STRONG),
            ("GRID", (0, 1), (-1, -1), 0.3, BORDER_COLOR),
            ("BOX", (0, 0), (-1, -1), 1.2, VBSP_GREEN),
            ("LINEBELOW", (0, 0), (-1, 0), 1.0, VBSP_GREEN_MID),
        ]

        n_data_rows = len(data_rows) - (1 if has_tong else 0)
        for r in range(1, n_data_rows + 1):
            if r % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))

        if has_tong and len(data_rows) > 0:
            last_row = len(data_rows)
            style_cmds.extend([
                ("BACKGROUND", (0, last_row), (-1, last_row), VBSP_GREEN_LIGHT),
                ("FONTNAME",   (0, last_row), (-1, last_row), fb),
                ("LINEABOVE",  (0, last_row), (-1, last_row), 2.0, VBSP_GREEN),
                ("LINEBELOW",  (0, last_row), (-1, last_row), 1.2, VBSP_GREEN),
                ("TOPPADDING", (0, last_row), (-1, last_row), 7),
                ("BOTTOMPADDING", (0, last_row), (-1, last_row), 7),
            ])

        tbl.setStyle(TableStyle(style_cmds))

        for ci, col in enumerate(cols):
            is_left = _is_left_align(col)
            is_center = _is_center_align(col)
            if not is_left and not is_center:
                tbl.setStyle(TableStyle([
                    ("ALIGN", (ci, 1), (ci, -1), "RIGHT")
                ]))

        elements.append(tbl)

    # ── Ghi chú đơn vị ──
    ghi_chu_parts = []
    don_vi_hien = f"({don_vi_tien})" if don_vi_tien and don_vi_tien != "đồng" else ""
    if don_vi_hien:
        ghi_chu_parts.append(f"Đơn vị tiền: {don_vi_hien}")
    elif cols_tien:
        ghi_chu_parts.append("Đơn vị tiền: VND")
    if cols_percent:
        ghi_chu_parts.append("Đơn vị %: phần trăm (%)")
    if ghi_chu_parts:
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(Paragraph(
            _pdf_text("  ·  ".join(ghi_chu_parts)),
            style_footer,
        ))

    # ── Chữ ký ──
    elements.append(Spacer(1, 1.0 * cm))
    elements.append(Paragraph(
        f"Đồng Nai, ngày {datetime.now().strftime('%d')} "
        f"tháng {datetime.now().strftime('%m')} "
        f"năm {datetime.now().strftime('%Y')}",
        ParagraphStyle("DS", fontName=fn, fontSize=10,
                       alignment=TA_RIGHT, spaceAfter=0.6 * cm)
    ))

    fi_ky = fi
    ky_data = [[
        Paragraph("<b>NGƯỜI LẬP BIỂU</b>", ParagraphStyle("K1", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
        Paragraph("<b>KIỂM SOÁT</b>", ParagraphStyle("K2", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
        Paragraph("<b>GIÁM ĐỐC</b>", ParagraphStyle("K3", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
    ], [
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("Kd1", fontName=fi_ky, fontSize=9,
                                                               alignment=TA_CENTER, textColor=TEXT_MUTED)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("Kd2", fontName=fi_ky, fontSize=9,
                                                               alignment=TA_CENTER, textColor=TEXT_MUTED)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("Kd3", fontName=fi_ky, fontSize=9,
                                                               alignment=TA_CENTER, textColor=TEXT_MUTED)),
    ], [
        Paragraph(" ", ParagraphStyle("Kg1", fontSize=12, leading=28)),
        Paragraph(" ", ParagraphStyle("Kg2", fontSize=12, leading=28)),
        Paragraph(" ", ParagraphStyle("Kg3", fontSize=12, leading=28)),
    ]]
    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(ky_tbl)

    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn, 8)
        canvas.setFillColor(TEXT_MUTED)
        canvas.drawRightString(
            page_size[0] - margin,
            0.8 * cm,
            f"Trang {_doc.page}  ·  VBSP-SCM  ·  {ngay_str}"
        )
        canvas.drawString(
            margin,
            0.8 * cm,
            f"{TEN_CHI_NHANH_HIEN_THI}  ·  Báo cáo nội bộ"
        )
        canvas.setStrokeColor(VBSP_GREEN_MID)
        canvas.setLineWidth(0.8)
        canvas.line(margin, 1.1 * cm, page_size[0] - margin, 1.1 * cm)
        canvas.restoreState()

    try:
        doc.build(elements, onFirstPage=_on_page, onLaterPages=_on_page)
    except Exception:
        doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


def download_pdf_button(
    pdf_bytes: bytes,
    filename: str = "bao_cao.pdf",
    label: str = "📥 Tải PDF",
    key: str | None = None,
):
    """Nút tải PDF trong Streamlit."""
    st.download_button(
        label=label,
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        key=key,
        use_container_width=True,
    )
