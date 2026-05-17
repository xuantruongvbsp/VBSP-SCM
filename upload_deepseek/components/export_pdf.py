"""Export PDF nâng cao - hỗ trợ kèm biểu đồ."""

from __future__ import annotations

from io import BytesIO
from datetime import datetime
from pathlib import Path
from typing import Sequence

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

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

try:
    import os
    from pathlib import Path
    candidates = [
        Path("C:/Windows/Fonts/times.ttf"),
        Path("C:/Windows/Fonts/timesbd.ttf"),
    ]
    regular = next((p for p in candidates if p.exists()), None)
    bold = next((p for p in [candidates[1]] if p.exists()), None)
    if regular:
        pdfmetrics.registerFont(TTFont("TNR", str(regular)))
        FONT_NORMAL = "TNR"
    if bold:
        pdfmetrics.registerFont(TTFont("TNR-Bold", str(bold)))
        FONT_BOLD = "TNR-Bold"
except Exception:
    pass

VBSP_GREEN = colors.HexColor("#2E7D32")
VBSP_GREEN_LIGHT = colors.HexColor("#E8F5E9")
ROW_ALT = colors.HexColor("#F5F5F5")
BORDER_COLOR = colors.HexColor("#BDBDBD")

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


def _ve_header(elements: list, tieu_de: str, nguoi_xuat: str, usable_w: float):
    """Vẽ header báo cáo PDF: logo NHCSXH + tiêu đề + meta."""
    from reportlab.platypus import Table as RLTable

    logo_path = _tim_logo()
    style_bank = ParagraphStyle(
        "BankName", fontName=FONT_BOLD, fontSize=11,
        alignment=TA_CENTER, leading=15,
    )
    style_branch = ParagraphStyle(
        "BranchName", fontName=FONT_NORMAL, fontSize=9,
        alignment=TA_CENTER, leading=12, spaceAfter=2,
    )
    style_meta = ParagraphStyle(
        "Meta", fontName=FONT_NORMAL, fontSize=8,
        alignment=TA_CENTER, textColor=colors.gray, spaceAfter=6,
    )
    style_report_title = ParagraphStyle(
        "ReportTitle", fontName=FONT_BOLD, fontSize=13,
        alignment=TA_CENTER, textColor=VBSP_GREEN, spaceAfter=6,
    )

    bank_text = ("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM<br/>"
                 "<font size='9'>Chi nhánh tỉnh Đồng Nai</font>")

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

    elements.append(HRFlowable(
        width="100%", thickness=1.5, color=VBSP_GREEN, spaceAfter=4,
    ))
    elements.append(Paragraph(tieu_de.upper(), style_report_title))
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    elements.append(Paragraph(
        f"Ngày xuất: {now_str}  |  Người xuất: {nguoi_xuat}",
        style_meta,
    ))
    elements.append(Spacer(1, 4))


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

    Returns:
        bytes: Nội dung file PDF
    """
    if not _REPORTLAB_READY:
        st.error("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
        return b""

    from utils import fmt_so

    cols_tien = cols_tien or []
    is_landscape = len(df.columns) >= 8 or prefix_file == "TQPGD"
    page_size = landscape(A4) if is_landscape else A4

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    style_title = ParagraphStyle(
        "Title", fontName=FONT_BOLD, fontSize=16,
        alignment=TA_CENTER, spaceAfter=4, textColor=VBSP_GREEN,
    )
    style_sub = ParagraphStyle(
        "Sub", fontName=FONT_NORMAL, fontSize=9,
        alignment=TA_CENTER, spaceAfter=10, textColor=colors.gray,
    )
    style_header = ParagraphStyle(
        "Header", fontName=FONT_BOLD, fontSize=8,
        alignment=TA_CENTER, textColor=colors.white,
    )
    style_cell = ParagraphStyle(
        "Cell", fontName=FONT_NORMAL, fontSize=7.5,
        alignment=TA_CENTER, leading=10,
    )
    style_cell_left = ParagraphStyle(
        "CellL", fontName=FONT_NORMAL, fontSize=7.5,
        alignment=TA_LEFT, leading=10,
    )
    style_caption = ParagraphStyle(
        "Caption", fontName=FONT_NORMAL, fontSize=8,
        alignment=TA_CENTER, spaceBefore=4, spaceAfter=12, textColor=colors.gray,
    )
    style_footer = ParagraphStyle(
        "Footer", fontName=FONT_NORMAL, fontSize=8,
        alignment=TA_LEFT, textColor=colors.gray,
    )

    elements = []

    # ── Header (Logo NHCSXH + Tiêu đề) ──
    margin = 1.5 * cm
    usable_w = page_size[0] - 2 * margin
    _ve_header(elements, tieu_de, nguoi_xuat, usable_w)

    # ── Biểu đồ ──
    if figs:
        for fig, caption in figs:
            img_bytes = fig_to_bytes(fig)
            if img_bytes:
                img_w = page_size[0] - 3 * cm
                img_h = img_w * 0.45
                img = RLImage(BytesIO(img_bytes), width=img_w, height=img_h)
                elements.append(img)
                if caption:
                    elements.append(Paragraph(caption, style_caption))
                elements.append(Spacer(1, 8))
            else:
                elements.append(Paragraph(f"[Không thể render biểu đồ: {caption}]", style_caption))

    # ── Bảng dữ liệu ──
    if df is not None and not df.empty:
        elements.append(Spacer(1, 6))

        cols = list(df.columns)
        headers = [Paragraph(c, style_header) for c in cols]

        data_rows = []
        for _, row in df.iterrows():
            cells = []
            for i, c in enumerate(cols):
                val = row[c]
                if pd.isna(val):
                    txt = ""
                elif c in cols_tien:
                    try:
                        txt = fmt_so(float(val))
                    except (ValueError, TypeError):
                        txt = str(val)
                else:
                    txt = str(val)
                s = style_cell_left if i == 0 else style_cell
                cells.append(Paragraph(txt, s))
            data_rows.append(cells)

        if them_dong_tong and cols_tien and len(df) > 0:
            tong_row = []
            for c in cols:
                if c in cols_tien:
                    try:
                        tong = pd.to_numeric(df[c], errors="coerce").sum()
                        tong_row.append(Paragraph(fmt_so(tong), style_cell))
                    except Exception:
                        tong_row.append(Paragraph("", style_cell))
                else:
                    tong_row.append(Paragraph("Tổng cộng" if c == cols[0] else "", style_cell))
            data_rows.append(tong_row)

        table_data = [headers] + data_rows
        col_width = (page_size[0] - 3 * cm) / max(len(cols), 1)

        tbl = Table(table_data, colWidths=[col_width] * len(cols))
        tbl_style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, ROW_ALT]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ])

        if them_dong_tong and cols_tien and len(data_rows) > 1:
            last_row = len(data_rows)
            tbl_style.add("BACKGROUND", (0, last_row), (-1, last_row), VBSP_GREEN_LIGHT)
            tbl_style.add("FONTNAME", (0, last_row), (-1, last_row), FONT_BOLD)

        tbl.setStyle(tbl_style)
        elements.append(tbl)

    # ── Footer ──
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", color=BORDER_COLOR))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        f"Nguồn: Hệ thống HSTD · Đơn vị tiền: {don_vi_tien}",
        style_footer,
    ))

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
        width="stretch",
    )
