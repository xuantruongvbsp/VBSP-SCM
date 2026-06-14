from io import BytesIO
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from state_manager import SCMStateManager
from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_LAI_TON,
    COT_MA_KH,
    COT_SO_KU,
    COT_TONG_DU_NO,
)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable, PageBreak, Image as RLImage
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    _REPORTLAB_READY = True
except ImportError:
    _REPORTLAB_READY = False

_FONT_REGISTERED = False


def _dang_ky_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    import os
    import warnings
    from pathlib import Path

    candidates = [
        Path("assets/times.ttf"),
        Path("assets/timesbd.ttf"),
        Path("C:/Windows/Fonts/times.ttf"),
        Path("C:/Windows/Fonts/timesbd.ttf"),
    ]
    regular = next((p for p in candidates[:2] + [candidates[2]] if p.exists()), None)
    bold = next((p for p in [candidates[1], candidates[3]] if p.exists()), None)

    if regular:
        pdfmetrics.registerFont(TTFont("TNR", str(regular)))
    if bold:
        pdfmetrics.registerFont(TTFont("TNR-Bold", str(bold)))

    if not regular:
        warnings.warn("Không tìm thấy times.ttf — tiếng Việt có thể bị lỗi font.")

    _FONT_REGISTERED = True


FONT_NORMAL = "TNR"
FONT_BOLD = "TNR-Bold"
FONT_FALLBACK = "Helvetica"

if _REPORTLAB_READY:
    VBSP_GREEN = colors.HexColor("#2E7D32")
    VBSP_GREEN_LIGHT = colors.HexColor("#E8F5E9")
    ROW_ALT = colors.HexColor("#F5F5F5")
    BORDER_COLOR = colors.HexColor("#BDBDBD")
else:
    VBSP_GREEN = None
    VBSP_GREEN_LIGHT = None
    ROW_ALT = None
    BORDER_COLOR = None


def xuat_pdf(
    df: pd.DataFrame,
    tieu_de: str,
    nguoi_xuat: str,
    cols_tien: list[str] | None = None,
    don_vi_tien: str = "đồng",
    prefix_file: str = "",
    them_dong_tong: bool = True,
    cols_right: list[str] | None = None,
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    if df is None or df.empty or len(df.columns) == 0:
        raise ValueError("Không có dữ liệu để xuất PDF")
    _dang_ky_font()
    from utils import fmt_so

    cols_tien = cols_tien or []
    cols_right = cols_right or []

    dong_tong_cells = None
    if them_dong_tong and cols_tien and len(df) > 0:
        tong_row = {}
        for col in df.columns:
            if col in cols_tien:
                try:
                    tong_row[col] = pd.to_numeric(df[col], errors="coerce").sum()
                except Exception:
                    tong_row[col] = ""
            else:
                tong_row[col] = "TỔNG CỘNG" if list(df.columns).index(col) == 0 else ""
        dong_tong_cells = tong_row

    buf = BytesIO()
    use_landscape = len(df.columns) >= 8 or prefix_file == "TQPGD"
    page_size = landscape(A4) if use_landscape else A4
    margin = 1.0 * cm

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=2 * cm,
        title=tieu_de,
        author="VBSP-SCM",
    )

    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD if _FONT_REGISTERED else FONT_FALLBACK

    story = []
    usable_w = page_size[0] - 2 * margin

    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        logo = RLImage(str(logo_path), width=2.2 * cm, height=2.2 * cm)
        from reportlab.platypus import Table as RLTable
        header_tbl = RLTable(
            [[logo, Paragraph(
                "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM<br/>"
                "<font size='10'>Chi nhánh tỉnh Đồng Nai</font>",
                ParagraphStyle("hdr_txt", fontName=fb, fontSize=12,
                               alignment=TA_CENTER, leading=16)
            )]],
            colWidths=[2.5 * cm, usable_w - 2.5 * cm]
        )
        header_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_tbl)
    else:
        story.append(Paragraph(
            "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM",
            ParagraphStyle("bank", fontName=fb, fontSize=12,
                           alignment=TA_CENTER, spaceAfter=2)
        ))
        story.append(Paragraph(
            "CHI NHÁNH TỈNH ĐỒNG NAI",
            ParagraphStyle("branch", fontName=fn, fontSize=11,
                           alignment=TA_CENTER, spaceAfter=6)
        ))

    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=VBSP_GREEN, spaceAfter=6))
    story.append(Paragraph(
        tieu_de.upper(),
        ParagraphStyle("title", fontName=fb, fontSize=13, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=4)
    ))
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {nguoi_xuat}",
        ParagraphStyle("meta", fontName=fn, fontSize=9, alignment=TA_CENTER,
                       textColor=colors.grey, spaceAfter=12)
    ))

    n_cols = len(df.columns)

    if n_cols <= 6:
        font_size = 11
    elif n_cols <= 10:
        font_size = 10
    elif n_cols <= 14:
        font_size = 9
    else:
        font_size = 8

    header_font_size = font_size + 2

    header_cells = [
        Paragraph(str(c).replace("_", " "), ParagraphStyle("th", fontName=fb,
                  fontSize=header_font_size, alignment=TA_CENTER,
                  textColor=colors.white))
        for c in df.columns
    ]
    table_data = [header_cells]

    for _, row in df.iterrows():
        cells = []
        for col in df.columns:
            val = row[col]
            if col in cols_tien and pd.notna(val):
                try:
                    if isinstance(val, bool):
                        raise ValueError
                    if isinstance(val, (int, float)):
                        txt = fmt_so(float(val))
                    else:
                        num = float(
                            str(val).strip().replace(".", "").replace(",", ".")
                        )
                        txt = fmt_so(num)
                    p = Paragraph(txt, ParagraphStyle("td_r", fontName=fn,
                                                      fontSize=font_size, alignment=TA_RIGHT))
                except (ValueError, TypeError):
                    p = Paragraph(
                        str(val) if pd.notna(val) else "",
                        ParagraphStyle("td_r", fontName=fn,
                                       fontSize=font_size, alignment=TA_RIGHT),
                    )
            elif col in cols_right:
                p = Paragraph(str(val) if pd.notna(val) else "",
                              ParagraphStyle("td_r2", fontName=fn, fontSize=font_size,
                                             alignment=TA_RIGHT))
            else:
                p = Paragraph(str(val) if pd.notna(val) else "",
                              ParagraphStyle("td", fontName=fn, fontSize=font_size,
                                             wordWrap="CJK"))
            cells.append(p)
        table_data.append(cells)

    if dong_tong_cells is not None:
        tong_cells = []
        for col in df.columns:
            val = dong_tong_cells[col]
            if col in cols_tien and isinstance(val, (int, float)):
                txt = fmt_so(float(val))
                p = Paragraph(
                    f"<b>{txt}</b>",
                    ParagraphStyle("tong_r", fontName=fb,
                                   fontSize=font_size, alignment=TA_RIGHT)
                )
            elif val == "TỔNG CỘNG":
                p = Paragraph(
                    "<b>TỔNG CỘNG</b>",
                    ParagraphStyle("tong_lbl", fontName=fb,
                                   fontSize=font_size, alignment=TA_CENTER)
                )
            else:
                p = Paragraph(
                    str(val) if val else "",
                    ParagraphStyle("tong_empty", fontName=fn, fontSize=font_size)
                )
            tong_cells.append(p)
        table_data.append(tong_cells)

    if n_cols > 0:
        cols_list = list(df.columns)

        def _col_ratio(col_name: str) -> float:
            c = str(col_name).lower()
            if c in ("stt",):
                return 0.5
            if any(k in c for k in ("tiêu chí", "tieu chi")):
                return 2.5
            if any(k in c for k in ("tổ trưởng", "to truong")):
                return 2.0
            if any(k in c for k in ("xếp loại", "xep loai")):
                return 1.2
            if any(k in c for k in ("mã tổ", "ma to")):
                return 1.0
            if any(k in c for k in ("chỉ tiêu", "đơn vị", "chi tiêu", "chương trình", "ten")):
                return 3.0
            if any(k in c for k in ("tỷ lệ", "tl ", "%")):
                return 0.8
            if any(k in c for k in ("còn", "con ")):
                return 1.0
            return 1.2

        ratios = [_col_ratio(c) for c in cols_list]
        total_ratio = sum(ratios)
        col_widths = [usable_w * r / total_ratio for r in ratios]
    else:
        col_widths = [usable_w]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), fb),
        ("FONTSIZE", (0, 0), (-1, 0), header_font_size),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("BOX", (0, 0), (-1, -1), 1, VBSP_GREEN),
    ]
    for r in range(1, len(table_data)):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))

    if dong_tong_cells is not None:
        last_row = len(table_data) - 1
        style_cmds.extend([
            ("BACKGROUND", (0, last_row), (-1, last_row), VBSP_GREEN_LIGHT),
            ("FONTNAME",   (0, last_row), (-1, last_row), fb),
            ("LINEABOVE",  (0, last_row), (-1, last_row), 1.5, VBSP_GREEN),
        ])

    tbl.setStyle(TableStyle(style_cmds))
    for ci, col in enumerate(df.columns):
        c = str(col).lower()
        if c not in ("stt", "chỉ tiêu", "đơn vị", "chi tiêu", "chương trình"):
            tbl.setStyle(TableStyle([
                ("ALIGN", (ci, 1), (ci, -1), "RIGHT")
            ]))
    story.append(tbl)

    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        f"Đồng Nai, ngày {datetime.now().strftime('%d')} "
        f"tháng {datetime.now().strftime('%m')} "
        f"năm {datetime.now().strftime('%Y')}",
        ParagraphStyle("date_sign", fontName=fn, fontSize=10,
                       alignment=TA_RIGHT, spaceAfter=6)
    ))

    ky_data = [[
        Paragraph("NGƯỜI LẬP BIỂU", ParagraphStyle("ky", fontName=fb, fontSize=10, alignment=TA_CENTER)),
        Paragraph("KIỂM SOÁT", ParagraphStyle("ky", fontName=fb, fontSize=10, alignment=TA_CENTER)),
        Paragraph("GIÁM ĐỐC", ParagraphStyle("ky", fontName=fb, fontSize=10, alignment=TA_CENTER)),
    ], [
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky2", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky2", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky2", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
    ], [
        Paragraph(" \n\n\n", ParagraphStyle("gap", fontSize=10)),
        Paragraph(" \n\n\n", ParagraphStyle("gap", fontSize=10)),
        Paragraph(" \n\n\n", ParagraphStyle("gap", fontSize=10)),
    ]]
    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ky_tbl)

    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn if _FONT_REGISTERED else FONT_FALLBACK, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            page_size[0] - margin,
            0.8 * cm,
            f"Trang {_doc.page}  |  VBSP-SCM  |  {ngay_str}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.getvalue()


def xuat_pdf_pivot(
    df: pd.DataFrame,
    group_col: str,
    tieu_de: str,
    nguoi_xuat: str,
    prefix_file: str = "BC_PIVOT",
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    if df is None or df.empty:
        raise ValueError("Không có dữ liệu để xuất PDF")
    if group_col not in df.columns:
        raise ValueError(f"Cột nhóm '{group_col}' không tồn tại trong dữ liệu")

    _dang_ky_font()

    _DN_SO_KH = "Số KH"
    _DN_SO_MON = "Số món"
    _DN_TONG_DU_NO = "Tổng dư nợ"
    _DN_DU_NO_TH = "Dư nợ TH"
    _DN_DU_NO_QH = "Dư nợ QH"
    _DN_TL_QH = "Tỷ lệ QH%"

    agg_dict = {
        _DN_SO_KH: (COT_MA_KH, "nunique"),
        _DN_SO_MON: (COT_SO_KU, "nunique"),
        _DN_TONG_DU_NO: (COT_TONG_DU_NO, "sum"),
        _DN_DU_NO_TH: (COT_DU_NO_TH, "sum"),
        _DN_DU_NO_QH: (COT_DU_NO_QH, "sum"),
    }
    if COT_LAI_TON in df.columns:
        _DN_LAI_TON = "Lãi tồn"
        agg_dict[_DN_LAI_TON] = (COT_LAI_TON, "sum")

    df_pivot = (
        df.groupby(group_col)
        .agg(**agg_dict)
        .sort_values(_DN_TONG_DU_NO, ascending=False)
        .reset_index()
    )

    df_pivot[_DN_TL_QH] = (
        df_pivot[_DN_DU_NO_QH]
        / df_pivot[_DN_TONG_DU_NO].replace(0, float("nan"))
        * 100
    ).round(2).fillna(0)

    cols_tien = [_DN_TONG_DU_NO, _DN_DU_NO_TH, _DN_DU_NO_QH]
    if COT_LAI_TON in df.columns:
        cols_tien.append(_DN_LAI_TON)

    return xuat_pdf(
        df_pivot,
        tieu_de,
        nguoi_xuat,
        cols_tien=cols_tien,
        prefix_file=prefix_file,
        them_dong_tong=True,
    )


def xuat_pdf_chi_tiet(
    df: pd.DataFrame,
    cols_hien_thi: list[str],
    tieu_de: str,
    nguoi_xuat: str,
    prefix_file: str = "BC_CT",
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    if df is None or df.empty:
        raise ValueError("Không có dữ liệu để xuất PDF")

    _dang_ky_font()

    cols_co = [c for c in cols_hien_thi if c in df.columns]
    if not cols_co:
        cols_co = list(df.columns)

    df_xuat = df[cols_co].copy()

    _MONEY_PATTERNS = {
        COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO,
        COT_LAI_TON, COT_DU_NO_KHOANH,
        "Tổng dư nợ", "Dư nợ TH", "Dư nợ QH", "Dư nợ trong hạn",
        "Dư nợ quá hạn", "Lãi tồn", "Dư nợ khoanh", "Nợ khoanh",
        "Tổng_dư_nợ", "Dư_nợ_trong_hạn", "Dư_nợ_quá_hạn",
        "Lãi_tồn_KHĐ", "Nợ_khoanh",
        "Số_KH", "Số_món_vay", "Số món",
        "Dư_nợ_TH", "Dư_nợ_QH",
    }
    cols_tien = [c for c in cols_co if c in _MONEY_PATTERNS]

    return xuat_pdf(
        df_xuat,
        tieu_de,
        nguoi_xuat,
        cols_tien=cols_tien,
        prefix_file=prefix_file,
        them_dong_tong=True,
    )


def xuat_pdf_theo_nhom(
    df: pd.DataFrame,
    group_col: str,
    cols_chi_tiet: list[str],
    tieu_de: str,
    nguoi_xuat: str,
    prefix_file: str = "BC_NHOM",
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    if df is None or df.empty:
        raise ValueError("Không có dữ liệu để xuất PDF")
    if group_col not in df.columns:
        raise ValueError(f"Cột nhóm '{group_col}' không tồn tại trong dữ liệu")

    _dang_ky_font()
    from utils import fmt_so

    cols_co = [c for c in cols_chi_tiet if c in df.columns]
    if not cols_co:
        cols_co = list(df.columns)

    _MONEY_PATTERNS = {
        COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO,
        COT_LAI_TON, COT_DU_NO_KHOANH,
        "Tổng dư nợ", "Dư nợ TH", "Dư nợ QH", "Dư nợ trong hạn",
        "Dư nợ quá hạn", "Lãi tồn", "Dư nợ khoanh", "Nợ khoanh",
        "Tổng_dư_nợ", "Dư_nợ_trong_hạn", "Dư_nợ_quá_hạn",
        "Lãi_tồn_KHĐ", "Nợ_khoanh",
        "Số_KH", "Số_món_vay", "Số món",
        "Dư_nợ_TH", "Dư_nợ_QH",
    }
    cols_tien = [c for c in cols_co if c in _MONEY_PATTERNS]

    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD if _FONT_REGISTERED else FONT_FALLBACK

    buf = BytesIO()
    page_size = landscape(A4)
    margin = 1.0 * cm

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=2 * cm,
        title=tieu_de,
        author="VBSP-SCM",
    )

    story = []
    usable_w = page_size[0] - 2 * margin
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        logo = RLImage(str(logo_path), width=2.0 * cm, height=2.0 * cm)
        from reportlab.platypus import Table as RLTable
        header_tbl = RLTable(
            [[logo, Paragraph(
                "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM<br/>"
                "<font size='9'>Chi nhánh tỉnh Đồng Nai</font>",
                ParagraphStyle("hdr_nhom", fontName=fb, fontSize=11,
                               alignment=TA_CENTER, leading=15)
            )]],
            colWidths=[2.3 * cm, usable_w - 2.3 * cm]
        )
        header_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_tbl)
    else:
        story.append(Paragraph(
            "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM",
            ParagraphStyle("bank_nhom", fontName=fb, fontSize=11,
                           alignment=TA_CENTER, spaceAfter=2)
        ))
        story.append(Paragraph(
            "CHI NHÁNH TỈNH ĐỒNG NAI",
            ParagraphStyle("branch_nhom", fontName=fn, fontSize=10,
                           alignment=TA_CENTER, spaceAfter=6)
        ))

    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=VBSP_GREEN, spaceAfter=6))
    story.append(Paragraph(
        tieu_de.upper(),
        ParagraphStyle("title_nhom", fontName=fb, fontSize=12, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=4)
    ))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {nguoi_xuat}",
        ParagraphStyle("meta_nhom", fontName=fn, fontSize=8, alignment=TA_CENTER,
                       textColor=colors.grey, spaceAfter=10)
    ))

    groups = list(df.groupby(group_col, sort=False))
    n_cols = len(cols_co)

    if n_cols <= 6:
        font_size = 10
    elif n_cols <= 10:
        font_size = 9
    elif n_cols <= 14:
        font_size = 8
    else:
        font_size = 7

    hdr_font_size = font_size + 1

    for gi, (nhom_val, nhom_df) in enumerate(groups):
        nhom_label = str(nhom_val) if pd.notna(nhom_val) else "(Không xác định)"
        n_ho_so = len(nhom_df)
        tong_du_no = nhom_df[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in nhom_df.columns else 0
        tong_str = f"{fmt_so(tong_du_no)}"

        if gi > 0:
            story.append(PageBreak())

        story.append(Spacer(1, 0.3 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=VBSP_GREEN, spaceAfter=4))
        story.append(Paragraph(
            f"<b>{nhom_label}</b> — {n_ho_so} hồ sơ — Tổng dư nợ: {tong_str}",
            ParagraphStyle("section_nhom", fontName=fb, fontSize=10,
                           textColor=VBSP_GREEN, spaceAfter=6)
        ))

        nhom_display = nhom_df[cols_co].copy()

        header_cells = [
            Paragraph(str(c).replace("_", " "), ParagraphStyle("th_nhom", fontName=fb,
                      fontSize=hdr_font_size, alignment=TA_CENTER, textColor=colors.white))
            for c in cols_co
        ]
        table_data = [header_cells]

        for _, row in nhom_display.iterrows():
            cells = []
            for col in cols_co:
                val = row[col]
                if col in cols_tien and pd.notna(val):
                    try:
                        if isinstance(val, bool):
                            raise ValueError
                        if isinstance(val, (int, float)):
                            txt = fmt_so(float(val))
                        else:
                            num = float(
                                str(val).strip().replace(".", "").replace(",", ".")
                            )
                            txt = fmt_so(num)
                        p = Paragraph(txt, ParagraphStyle("td_r_nhom", fontName=fn,
                                          fontSize=font_size, alignment=TA_RIGHT))
                    except (ValueError, TypeError):
                        p = Paragraph(
                            str(val) if pd.notna(val) else "",
                            ParagraphStyle("td_r_nhom2", fontName=fn,
                                           fontSize=font_size, alignment=TA_RIGHT),
                        )
                else:
                    p = Paragraph(str(val) if pd.notna(val) else "",
                                  ParagraphStyle("td_nhom", fontName=fn, fontSize=font_size,
                                                 wordWrap="CJK"))
                cells.append(p)
            table_data.append(cells)

        cong_cells = []
        for ci, col in enumerate(cols_co):
            if col in cols_tien:
                try:
                    tong = pd.to_numeric(nhom_display[col], errors="coerce").sum()
                    cong_cells.append(Paragraph(
                        f"<b>{fmt_so(tong)}</b>",
                        ParagraphStyle("cong_r_nhom", fontName=fb, fontSize=font_size,
                                       alignment=TA_RIGHT),
                    ))
                except Exception:
                    cong_cells.append(Paragraph("", ParagraphStyle("cong_nhom", fontName=fb, fontSize=font_size)))
            elif ci == 0:
                cong_cells.append(Paragraph(
                    "<b>Cộng</b>",
                    ParagraphStyle("cong_lbl_nhom", fontName=fb, fontSize=font_size,
                                   alignment=TA_LEFT),
                ))
            else:
                cong_cells.append(Paragraph("", ParagraphStyle("cong_nhom", fontName=fb, fontSize=font_size)))
        table_data.append(cong_cells)

        col_widths = [usable_w / n_cols] * n_cols if n_cols else [usable_w]
        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        last_r = len(table_data) - 1
        style_cmds = [
            ("BACKGROUND", (0, 0),       (-1, 0),       VBSP_GREEN),
            ("TEXTCOLOR",  (0, 0),       (-1, 0),       colors.white),
            ("FONTNAME",   (0, 0),       (-1, 0),       fb),
            ("FONTSIZE",   (0, 0),       (-1, 0),       hdr_font_size),
            ("ALIGN",      (0, 0),       (-1, 0),       "CENTER"),
            ("VALIGN",     (0, 0),       (-1, -1),      "MIDDLE"),
            ("GRID",       (0, 0),       (-1, -1),      0.5, BORDER_COLOR),
            ("BACKGROUND", (0, last_r),  (-1, last_r),  VBSP_GREEN_LIGHT),
            ("FONTNAME",   (0, last_r),  (-1, last_r),  fb),
            ("LINEABOVE",  (0, last_r),  (-1, last_r),  1.5, VBSP_GREEN),
        ]
        for r in range(1, last_r):
            if r % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))
        tbl.setStyle(TableStyle(style_cmds))
        story.append(tbl)

    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        f"Đồng Nai, ngày {datetime.now().strftime('%d')} "
        f"tháng {datetime.now().strftime('%m')} "
        f"năm {datetime.now().strftime('%Y')}",
        ParagraphStyle("date_sign_nhom", fontName=fn, fontSize=10,
                       alignment=TA_RIGHT, spaceAfter=6)
    ))

    ky_data = [[
        Paragraph("NGƯỜI LẬP BIỂU", ParagraphStyle("ky_nhom_a", fontName=fb, fontSize=10, alignment=TA_CENTER)),
        Paragraph("KIỂM SOÁT",       ParagraphStyle("ky_nhom_b", fontName=fb, fontSize=10, alignment=TA_CENTER)),
        Paragraph("GIÁM ĐỐC",        ParagraphStyle("ky_nhom_c", fontName=fb, fontSize=10, alignment=TA_CENTER)),
    ], [
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky_nhom_d", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky_nhom_e", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky_nhom_f", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
    ], [
        Paragraph(" \n\n\n", ParagraphStyle("gap_nhom_a", fontSize=10)),
        Paragraph(" \n\n\n", ParagraphStyle("gap_nhom_b", fontSize=10)),
        Paragraph(" \n\n\n", ParagraphStyle("gap_nhom_c", fontSize=10)),
    ]]
    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ky_tbl)

    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn if _FONT_REGISTERED else FONT_FALLBACK, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            page_size[0] - margin, 0.8 * cm,
            f"Trang {_doc.page}  |  VBSP-SCM  |  {ngay_str}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.getvalue()


def xuat_pdf_bang(
    df: pd.DataFrame,
    tieu_de: str,
    tieu_de_phu: str = "",
    *,
    nguoi_xuat: str = "",
    cols_tien: list[str] | None = None,
    prefix_file: str = "",
) -> bytes:
    if tieu_de_phu:
        tieu_de_day_du = f"{tieu_de} — {tieu_de_phu}"
    else:
        tieu_de_day_du = tieu_de
    return xuat_pdf(
        df,
        tieu_de_day_du,
        nguoi_xuat or "VBSP-SCM",
        cols_tien=cols_tien,
        prefix_file=prefix_file,
    )


def nut_xuat_pdf(
    df: pd.DataFrame,
    tieu_de: str,
    username: str,
    cols_tien: list[str] | None = None,
    prefix_file: str = "BC",
    key: str = "btn_pdf",
) -> None:
    state = SCMStateManager()
    downloads_key = f"pdf_{key}"

    if st.button("📄 Xuất PDF", key=key, type="primary"):
        try:
            with st.spinner("Đang tạo PDF..."):
                pdf_bytes = xuat_pdf(df, tieu_de, username, cols_tien, prefix_file=prefix_file)
            state.downloads.set(
                downloads_key,
                pdf_bytes,
                f"{prefix_file}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
            )
        except Exception as e:  # conv: skip
            state.downloads.clear(downloads_key)
            st.error(f"❌ Lỗi tạo PDF: {e}")

    if state.downloads.has(downloads_key):
        if st.download_button(
            label="⬇ Tải file PDF",
            data=state.downloads.get_bytes(downloads_key),
            file_name=state.downloads.get_filename(downloads_key) or f"{prefix_file}.pdf",
            mime="application/pdf",
            key=f"dl_{key}",
        ):
            state.downloads.clear(downloads_key)


# ── Extra functions chỉ có ở root pdf_service.py ──────────────────────────

def kiem_tra_pdf_dependency() -> dict:
    ready = True
    messages = []

    try:
        import reportlab
    except ImportError:
        ready = False
        messages.append("❌ Thiếu thư viện `reportlab`. Chạy: `pip install reportlab`")

    try:
        from PIL import Image
    except ImportError:
        ready = False
        messages.append("❌ Thiếu thư viện `Pillow`. Chạy: `pip install Pillow`")

    if not _REPORTLAB_READY:
        ready = False
        messages.append("❌ reportlab import lỗi — không thể xuất PDF")

    return {
        "ready": ready,
        "reportlab": _REPORTLAB_READY,
        "messages": messages,
    }


def render_huong_dan():
    st.markdown("""
    ## 📖 Hướng dẫn sử dụng VBSP-SCM

    ### 🔍 Tra cứu hồ sơ
    - Nhập **Mã KH**, **Số CMND**, **Số khế ước** hoặc **Tên KH** để tra cứu
    - Hỗ trợ tra cứu tổng hợp từ nhiều tiêu chí cùng lúc

    ### 📊 Báo cáo
    - Sử dụng bộ lọc theo PGD, Xã, Chương trình
    - Xuất báo cáo PDF / Excel với định dạng chuẩn

    ### 📤 Upload dữ liệu
    - Upload file Excel HSTD, NQ11 hoặc GQVL
    - Hệ thống tự động chuyển đổi sang Parquet để tối ưu tốc độ

    ### ⚙️ Yêu cầu hệ thống
    - Python ≥ 3.10
    - Tất cả thư viện trong `requirements.txt`
    - Font Times New Roman để xuất PDF tiếng Việt

    ### 📞 Hỗ trợ
    Liên hệ bộ phận CNTT Chi nhánh NHCSXH tỉnh Đồng Nai
    """)


def xuat_pdf_bao_cao(
    df: pd.DataFrame,
    tieu_de: str,
    nguoi_xuat: str,
    kpi_items: list | None = None,
    cols_tien: list[str] | None = None,
    tieu_de_phu: str = "",
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    _dang_ky_font()
    from utils import fmt_so, fmt_tien

    cols_tien = cols_tien or []
    kpi_items = kpi_items or []

    day_du_tieu_de = tieu_de
    if tieu_de_phu:
        day_du_tieu_de = f"{tieu_de}\n{tieu_de_phu}"

    buf = BytesIO()
    page_size = A4
    margin = 1.5 * cm

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=2 * cm,
        title=tieu_de,
        author="VBSP-SCM",
    )

    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD if _FONT_REGISTERED else FONT_FALLBACK

    story = []
    usable_w = page_size[0] - 2 * margin

    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        logo = RLImage(str(logo_path), width=1.8 * cm, height=1.8 * cm)
        from reportlab.platypus import Table as RLTable
        header_tbl = RLTable(
            [[logo, Paragraph(
                "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM<br/>"
                "<font size='9'>Chi nhánh tỉnh Đồng Nai</font>",
                ParagraphStyle("hdr_txt2", fontName=fb, fontSize=11,
                               alignment=TA_CENTER, leading=14)
            )]],
            colWidths=[2.0 * cm, usable_w - 2.0 * cm]
        )
        header_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_tbl)
    else:
        story.append(Paragraph(
            "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM",
            ParagraphStyle("bank2", fontName=fb, fontSize=11,
                           alignment=TA_CENTER, spaceAfter=2)
        ))

    story.append(HRFlowable(width="100%", thickness=1, color=VBSP_GREEN, spaceAfter=6))
    story.append(Paragraph(
        day_du_tieu_de.upper(),
        ParagraphStyle("title2", fontName=fb, fontSize=12, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=4)
    ))
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {nguoi_xuat}",
        ParagraphStyle("meta2", fontName=fn, fontSize=8, alignment=TA_CENTER,
                       textColor=colors.grey, spaceAfter=10)
    ))

    if kpi_items:
        story.append(Paragraph(
            "<b>TỔNG QUAN CHỈ SỐ</b>",
            ParagraphStyle("kpi_label", fontName=fb, fontSize=10,
                           alignment=TA_CENTER, spaceAfter=6, textColor=VBSP_GREEN)
        ))
        row_items = []
        for item in kpi_items:
            label = item.get("label", "")
            val = item.get("value", "")
            delta = item.get("delta")
            delta_str = f" ({delta:+.1f}%)" if delta is not None else ""
            row_items.append(Paragraph(
                f"<b>{label}</b><br/>{val}{delta_str}",
                ParagraphStyle("kpi_cell", fontName=fn, fontSize=9,
                               alignment=TA_CENTER, leading=12)
            ))
        n_kpi = len(kpi_items)
        if n_kpi > 0:
            kpi_tbl = Table([row_items], colWidths=[usable_w / n_kpi] * n_kpi)
            kpi_tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, VBSP_GREEN),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(kpi_tbl)
            story.append(Spacer(1, 0.5 * cm))

    if df is not None and not df.empty:
        story.append(Paragraph(
            "<b>CHI TIẾT DỮ LIỆU</b>",
            ParagraphStyle("detail_label", fontName=fb, fontSize=10,
                           alignment=TA_CENTER, spaceAfter=6, textColor=VBSP_GREEN)
        ))

        font_size = 9 if len(df.columns) <= 8 else 8
        hdr_font_size = font_size + 1

        header_cells = [
            Paragraph(str(c).replace("_", " "), ParagraphStyle("th2", fontName=fb,
                      fontSize=hdr_font_size, alignment=TA_CENTER, textColor=colors.white))
            for c in df.columns
        ]
        table_data = [header_cells]

        for _, row in df.iterrows():
            cells = []
            for col in df.columns:
                val = row[col]
                if col in cols_tien and pd.notna(val):
                    try:
                        num = float(val) if not isinstance(val, (int, float)) else float(val)
                        txt = fmt_so(num)
                        p = Paragraph(txt, ParagraphStyle("td_r2", fontName=fn,
                                          fontSize=font_size, alignment=TA_RIGHT))
                    except (ValueError, TypeError):
                        p = Paragraph(str(val) if pd.notna(val) else "",
                                      ParagraphStyle("td2", fontName=fn,
                                        fontSize=font_size, wordWrap="CJK"))
                else:
                    p = Paragraph(str(val) if pd.notna(val) else "",
                                  ParagraphStyle("td2", fontName=fn,
                                    fontSize=font_size, wordWrap="CJK"))
                cells.append(p)
            table_data.append(cells)

        if n_cols := len(df.columns):
            col_widths = [usable_w / n_cols] * n_cols
        else:
            col_widths = [usable_w]

        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), fb),
            ("FONTSIZE", (0, 0), (-1, 0), hdr_font_size),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ]
        for r in range(1, len(table_data)):
            if r % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))
        tbl.setStyle(TableStyle(style_cmds))
        story.append(tbl)

    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        f"Đồng Nai, ngày {datetime.now().strftime('%d')} "
        f"tháng {datetime.now().strftime('%m')} năm {datetime.now().strftime('%Y')}",
        ParagraphStyle("date_sign2", fontName=fn, fontSize=9,
                       alignment=TA_RIGHT, spaceAfter=4)
    ))

    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn if _FONT_REGISTERED else FONT_FALLBACK, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            page_size[0] - margin, 0.8 * cm,
            f"Trang {_doc.page}  |  VBSP-SCM  |  {ngay_str}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.getvalue()


def xuat_pdf_group_header(
    df: pd.DataFrame,
    tieu_de: str,
    nhom_theo: str,
    nguoi_xuat: str = "",
    cols_tien: list[str] | None = None,
    tieu_de_phu: str = "",
    loc_pgd: str | None = None,
    loc_ct: str | None = None,
    loc_xa: str | None = None,
    so_hieu: str = "",        # "Số: 123/NHCS-KHNV" — để trống = không hiện
    loai_van_ban: str = "",   # "BÁO CÁO" / "DANH SÁCH" / "BIÊN BẢN"... — hiện trên tiêu đề
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    _dang_ky_font()
    from utils import fmt_so

    cols_tien = cols_tien or []

    day_du_tieu_de = tieu_de
    phu_parts = []
    if tieu_de_phu:
        phu_parts.append(tieu_de_phu)
    if loc_pgd:
        phu_parts.append(f"PGD: {loc_pgd}")
    if loc_ct:
        phu_parts.append(f"CT: {loc_ct}")
    if loc_xa:
        phu_parts.append(f"Xã: {loc_xa}")
    if phu_parts:
        day_du_tieu_de = f"{tieu_de}  |  {' - '.join(phu_parts)}"

    buf = BytesIO()
    page_size = landscape(A4)
    margin = 1.0 * cm

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=2 * cm,
        title=tieu_de,
        author="VBSP-SCM",
    )

    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD if _FONT_REGISTERED else FONT_FALLBACK

    story = []
    usable_w = page_size[0] - 2 * margin
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ── Header NĐ 30 ─────────────────────────────────────────────────────────
    from reportlab.platypus import Table as RLTable
    col_w = usable_w / 2

    co_quan_html = (
        "<b>NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM</b><br/>"
        "<b>Chi nhánh tỉnh Đồng Nai</b>"
    )
    if so_hieu:
        co_quan_html += f"<br/><font size='9'>{so_hieu}</font>"

    co_quan_left = Paragraph(
        co_quan_html,
        ParagraphStyle("co_quan", fontName=fb, fontSize=10,
                       alignment=TA_LEFT, leading=14),
    )
    quoc_hieu_right = Paragraph(
        "<b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b><br/>"
        "<b>Độc lập - Tự do - Hạnh phúc</b><br/>"
        "<font size='9'>───────────────────</font>",
        ParagraphStyle("quoc_hieu", fontName=fb, fontSize=10,
                       alignment=TA_CENTER, leading=14),
    )
    nd30_hdr = RLTable([[co_quan_left, quoc_hieu_right]],
                       colWidths=[col_w, col_w])
    nd30_hdr.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(nd30_hdr)
    story.append(Spacer(1, 0.3 * cm))

    if loai_van_ban:
        story.append(Paragraph(
            loai_van_ban.upper(),
            ParagraphStyle("loai_vb", fontName=fb, fontSize=10,
                           alignment=TA_CENTER, spaceAfter=2),
        ))
    story.append(Paragraph(
        day_du_tieu_de.upper(),
        ParagraphStyle("title3", fontName=fb, fontSize=11, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=2),
    ))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {nguoi_xuat or 'VBSP-SCM'}",
        ParagraphStyle("meta3", fontName=fn, fontSize=8, alignment=TA_CENTER,
                       textColor=colors.grey, spaceAfter=8),
    ))

    if df.empty:
        story.append(Paragraph("Không có dữ liệu.", ParagraphStyle("empty", fontName=fn, fontSize=10)))
    else:
        groups = df.groupby(nhom_theo, sort=False) if nhom_theo in df.columns else [("", df)]
        for nhom_val, nhom_df in groups:
            nhom_label = str(nhom_val) if pd.notna(nhom_val) else "(Không xác định)"
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph(
                f"<b>▸ {nhom_label}</b>",
                ParagraphStyle("nhom", fontName=fb, fontSize=10,
                               textColor=VBSP_GREEN, spaceAfter=4)
            ))

            nhom_df = nhom_df.drop(columns=[nhom_theo], errors="ignore")
            if nhom_df.empty:
                continue

            n_cols = len(nhom_df.columns)
            font_size = 8 if n_cols > 8 else 9
            hdr_font_size = font_size + 1

            header_cells = [
                Paragraph(str(c).replace("_", " "), ParagraphStyle("th3", fontName=fb,
                          fontSize=hdr_font_size, alignment=TA_CENTER, textColor=colors.white))
                for c in nhom_df.columns
            ]
            table_data = [header_cells]

            for _, row in nhom_df.iterrows():
                cells = []
                for col in nhom_df.columns:
                    val = row[col]
                    if col in cols_tien and pd.notna(val):
                        try:
                            num = float(val) if not isinstance(val, (int, float)) else float(val)
                            txt = fmt_so(num)
                            p = Paragraph(txt, ParagraphStyle("td_r3", fontName=fn,
                                              fontSize=font_size, alignment=TA_RIGHT))
                        except (ValueError, TypeError):
                            p = Paragraph(str(val) if pd.notna(val) else "",
                                          ParagraphStyle("td3", fontName=fn,
                                            fontSize=font_size, wordWrap="CJK"))
                    else:
                        p = Paragraph(str(val) if pd.notna(val) else "",
                                      ParagraphStyle("td3", fontName=fn,
                                        fontSize=font_size, wordWrap="CJK"))
                    cells.append(p)
                table_data.append(cells)

            # Dòng Cộng
            cong_cells = []
            for ci, col in enumerate(nhom_df.columns):
                if col in cols_tien:
                    try:
                        tong = pd.to_numeric(nhom_df[col], errors="coerce").sum()
                        cong_cells.append(Paragraph(
                            fmt_so(tong),
                            ParagraphStyle("cong_r", fontName=fb, fontSize=font_size,
                                           alignment=TA_RIGHT),
                        ))
                    except Exception:
                        cong_cells.append(Paragraph("", ParagraphStyle("cong", fontName=fb, fontSize=font_size)))
                elif ci == 0:
                    cong_cells.append(Paragraph(
                        "Cộng",
                        ParagraphStyle("cong_lbl", fontName=fb, fontSize=font_size,
                                       alignment=TA_LEFT),
                    ))
                else:
                    cong_cells.append(Paragraph("", ParagraphStyle("cong", fontName=fb, fontSize=font_size)))
            table_data.append(cong_cells)

            col_widths = [usable_w / n_cols] * n_cols if n_cols else [usable_w]
            tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
            last_r = len(table_data) - 1
            style_cmds = [
                ("BACKGROUND", (0, 0),       (-1, 0),       VBSP_GREEN),
                ("TEXTCOLOR",  (0, 0),       (-1, 0),       colors.white),
                ("FONTNAME",   (0, 0),       (-1, 0),       fb),
                ("FONTSIZE",   (0, 0),       (-1, 0),       hdr_font_size),
                ("ALIGN",      (0, 0),       (-1, 0),       "CENTER"),
                ("VALIGN",     (0, 0),       (-1, -1),      "MIDDLE"),
                ("GRID",       (0, 0),       (-1, -1),      0.5, BORDER_COLOR),
                # Dòng Cộng
                ("BACKGROUND", (0, last_r),  (-1, last_r),  VBSP_GREEN_LIGHT),
                ("FONTNAME",   (0, last_r),  (-1, last_r),  fb),
                ("LINEABOVE",  (0, last_r),  (-1, last_r),  1.5, VBSP_GREEN),
            ]
            for r in range(1, last_r):
                if r % 2 == 0:
                    style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))
            tbl.setStyle(TableStyle(style_cmds))
            story.append(tbl)

    # ── Chữ ký ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(
        f"Đồng Nai, ngày {datetime.now().strftime('%d')} "
        f"tháng {datetime.now().strftime('%m')} "
        f"năm {datetime.now().strftime('%Y')}",
        ParagraphStyle("date_sign3", fontName=fn, fontSize=10,
                       alignment=TA_RIGHT, spaceAfter=6),
    ))
    ky_data = [
        [
            Paragraph("NGƯỜI LẬP BIỂU", ParagraphStyle("ky3a", fontName=fb, fontSize=10, alignment=TA_CENTER)),
            Paragraph("KIỂM SOÁT",       ParagraphStyle("ky3b", fontName=fb, fontSize=10, alignment=TA_CENTER)),
            Paragraph("GIÁM ĐỐC",        ParagraphStyle("ky3c", fontName=fb, fontSize=10, alignment=TA_CENTER)),
        ],
        [
            Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky3d", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
            Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky3e", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
            Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky3f", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
        ],
        [
            Paragraph(" \n\n\n", ParagraphStyle("gap3a", fontSize=10)),
            Paragraph(" \n\n\n", ParagraphStyle("gap3b", fontSize=10)),
            Paragraph(" \n\n\n", ParagraphStyle("gap3c", fontSize=10)),
        ],
    ]
    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ky_tbl)

    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn if _FONT_REGISTERED else FONT_FALLBACK, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            page_size[0] - margin, 0.8 * cm,
            f"Trang {_doc.page}  |  VBSP-SCM  |  {ngay_str}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.getvalue()
