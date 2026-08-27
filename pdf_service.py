from io import BytesIO
from datetime import datetime
from numbers import Number
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
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

    _BASE = Path(__file__).resolve().parent
    candidates_regular = [
        _BASE / "assets" / "times.ttf",
        Path("assets/times.ttf"),
        Path("C:/Windows/Fonts/times.ttf"),
    ]
    candidates_bold = [
        _BASE / "assets" / "timesbd.ttf",
        Path("assets/timesbd.ttf"),
        Path("C:/Windows/Fonts/timesbd.ttf"),
    ]
    candidates_italic = [
        _BASE / "assets" / "timesi.ttf",
        Path("assets/timesi.ttf"),
        Path("C:/Windows/Fonts/timesi.ttf"),
    ]
    candidates_bolditalic = [
        _BASE / "assets" / "timesbi.ttf",
        Path("assets/timesbi.ttf"),
        Path("C:/Windows/Fonts/timesbi.ttf"),
    ]
    regular = next((p for p in candidates_regular if p.exists()), None)
    bold = next((p for p in candidates_bold if p.exists()), None)
    italic = next((p for p in candidates_italic if p.exists()), None)
    bolditalic = next((p for p in candidates_bolditalic if p.exists()), None)

    global FONT_NORMAL, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC

    try:
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
        warnings.warn("Không đăng ký được TNR từ file TTF, sẽ dùng font fallback.")

    if not regular:
        warnings.warn("Không tìm thấy times.ttf — tiếng Việt có thể bị lỗi font.")

    _FONT_REGISTERED = True


FONT_NORMAL = "Times-Roman"
FONT_BOLD = "Times-Bold"
FONT_ITALIC = "Times-Italic"
FONT_BOLD_ITALIC = "Times-BoldItalic"
FONT_FALLBACK = "Times-Roman"
FONT_ITALIC_FALLBACK = "Times-Italic"
FONT_BOLD_ITALIC_FALLBACK = "Times-BoldItalic"

if _REPORTLAB_READY:
    VBSP_GREEN = colors.HexColor("#1B5E20")
    VBSP_GREEN_LIGHT = colors.HexColor("#C8E6C9")
    VBSP_GREEN_MID = colors.HexColor("#4CAF50")
    ROW_ALT = colors.HexColor("#F8F9FA")
    ROW_HEADER_ALT = colors.HexColor("#ECEFF1")
    BORDER_COLOR = colors.HexColor("#90A4AE")
    BORDER_STRONG = colors.HexColor("#455A64")
    TEXT_MUTED = colors.HexColor("#607D8B")
    TEXT_DARK = colors.HexColor("#263238")
else:
    VBSP_GREEN = None
    VBSP_GREEN_LIGHT = None
    VBSP_GREEN_MID = None
    ROW_ALT = None
    ROW_HEADER_ALT = None
    BORDER_COLOR = None
    BORDER_STRONG = None
    TEXT_MUTED = None
    TEXT_DARK = None


def _format_phan_tram(val: float | int | str) -> str:
    try:
        v = float(val)
        return f"{v:,.2f} %".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(val) if pd.notna(val) else ""


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


def _format_number_pdf(value: object, col_name: object = "") -> str:
    from utils import fmt_so

    c = str(col_name).casefold()
    if "tỷ lệ" in c or "%" in c:
        return _format_phan_tram(value).replace(" %", "")
    if _is_number(value):
        return fmt_so(float(value))
    num = float(str(value).strip().replace(".", "").replace(",", "."))
    return fmt_so(num)


def _is_money_col(col_name: object) -> bool:
    c = str(col_name).casefold().replace("_", " ")
    return any(k in c for k in (
        "dư nợ", "dno", "nợ", "lãi", "tiền", "giải ngân", "giai ngan", "gn ",
    ))


def _is_percent_col(col_name: object) -> bool:
    c = str(col_name).casefold().replace("_", " ")
    return any(k in c for k in ("tỷ lệ", "ty le", "tỷ trọng", "ty trong", "%"))


def _is_identifier_col(col_name: object) -> bool:
    c = str(col_name).casefold().replace("_", " ")
    return any(k in c for k in (
        "mã ",
        "mã kh",
        "mã tổ",
        "mã xã",
        "mã đv",
        "ma ",
        "ma kh",
        "ma to",
        "ma xa",
        "ma dv",
        "số khế",
        "so khe",
        "số ku",
        "cmnd",
        "cccd",
        "điện thoại",
        "dien thoai",
        "sdt",
        "atm",
    ))


def _is_count_col(col_name: object) -> bool:
    c = str(col_name).casefold().replace("_", " ")
    if _is_identifier_col(c) or _is_percent_col(c):
        return False
    return any(k in c for k in (
        "số kh",
        "số món",
        "số hộ",
        "số tổ",
        "số lượng",
        "món qh",
        "tổ tốt",
    ))


def _infer_pdf_column_roles(columns: list[object]) -> tuple[list[str], list[str], list[str]]:
    cols = [str(col) for col in columns]
    cols_tien = [col for col in cols if _is_money_col(col) and not _is_percent_col(col)]
    cols_dem = [col for col in cols if _is_count_col(col)]
    cols_percent = [col for col in cols if _is_percent_col(col)]
    return cols_tien, cols_dem, cols_percent


def _prepare_pdf_export_frame(
    df: pd.DataFrame,
    cols_hien_thi: list[str] | None = None,
    *,
    cols_tien: list[str] | None = None,
    cols_percent: list[str] | None = None,
    cols_dem: list[str] | None = None,
    scale_money: bool = False,
) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    cols_co = [c for c in (cols_hien_thi or list(df.columns)) if c in df.columns]
    if not cols_co:
        cols_co = list(df.columns)

    df_xuat = df[cols_co].copy()
    infer_tien, infer_dem, infer_percent = _infer_pdf_column_roles(cols_co)
    cols_tien = [c for c in (cols_tien or infer_tien) if c in cols_co]
    cols_dem = [c for c in (cols_dem or infer_dem) if c in cols_co]
    cols_percent = [c for c in (cols_percent or infer_percent) if c in cols_co]

    if scale_money:
        for col in cols_tien:
            df_xuat[col] = pd.to_numeric(df_xuat[col], errors="coerce").div(1_000_000).round(0)

    return df_xuat, cols_tien, cols_dem, cols_percent




def _col_ratio_pdf(col_name: object) -> float:
    c = str(col_name).casefold().replace("_", " ")
    if "31/12" in c or c.startswith("±"):
        return 1.75
    if "bq/kh" in c:
        return 1.15
    if any(k in c for k in ("mã kh", "mã tổ", "số khế", "cmnd", "cccd")):
        return 1.55
    if any(k in c for k in ("tên kh", "khách hàng")):
        return 2.1
    if any(k in c for k in ("tiêu chí", "tieu chi", "chỉ tiêu", "đơn vị", "chi tiêu", "chương trình", "tên xã", "tên pgd")):
        return 2.5
    if any(k in c for k in ("tổ trưởng", "to truong")):
        return 2.0
    if _is_money_col(c):
        return 1.75
    if _is_count_col(c):
        return 0.9
    if _is_percent_col(c):
        return 0.85
    if any(k in c for k in ("còn", "con ")):
        return 1.0
    return 1.2


def _column_widths_pdf(columns: list[object], usable_w: float) -> list[float]:
    ratios = [_col_ratio_pdf(c) for c in columns]
    total_ratio = sum(ratios) or 1
    return [usable_w * r / total_ratio for r in ratios]


def xuat_pdf(
    df: pd.DataFrame,
    tieu_de: str,
    nguoi_xuat: str,
    cols_tien: list[str] | None = None,
    don_vi_tien: str = "đồng",
    prefix_file: str = "",
    them_dong_tong: bool = True,
    cols_right: list[str] | None = None,
    dong_tong: dict[str, object] | None = None,
    cols_percent: list[str] | None = None,
    cols_dem: list[str] | None = None,
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    if df is None or df.empty or len(df.columns) == 0:
        raise ValueError("Không có dữ liệu để xuất PDF")
    _dang_ky_font()
    from utils import fmt_so

    cols_tien = cols_tien or []
    cols_right = cols_right or []
    cols_percent = cols_percent or []
    cols_dem = cols_dem or []

    dong_tong_cells = None
    if them_dong_tong and dong_tong is not None:
        dong_tong_cells = {col: dong_tong.get(col, "") for col in df.columns}
    elif them_dong_tong and (cols_tien or cols_dem) and len(df) > 0:
        tong_row = {}
        for col in df.columns:
            if col in cols_tien or col in cols_dem:
                try:
                    tong_row[col] = pd.to_numeric(df[col], errors="coerce").sum()
                except Exception:
                    tong_row[col] = ""
            else:
                tong_row[col] = "TỔNG CỘNG" if list(df.columns).index(col) == 0 else ""
        dong_tong_cells = tong_row

    buf = BytesIO()
    use_landscape = len(df.columns) >= 6 or prefix_file == "TQPGD"
    page_size = landscape(A4) if use_landscape else A4
    margin = 1.2 * cm

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=2 * cm,
        title=tieu_de,
        author="VBSP-SCM - NHCSXH Đồng Nai",
        subject=f"Báo cáo: {tieu_de}",
    )

    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD if _FONT_REGISTERED else FONT_FALLBACK
    fi = FONT_ITALIC if _FONT_REGISTERED else FONT_ITALIC_FALLBACK

    story = []
    usable_w = page_size[0] - 2 * margin
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        try:
            logo = RLImage(str(logo_path), width=2.0 * cm, height=2.0 * cm)
            from reportlab.platypus import Table as RLTable
            header_tbl = RLTable(
                [[logo, Paragraph(
                    "<b>NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM</b><br/>"
                    "<font size='10'>Chi nhánh tỉnh Đồng Nai</font>",
                    ParagraphStyle("hdr_txt", fontName=fb, fontSize=12,
                                   alignment=TA_CENTER, leading=15, spaceAfter=0)
                )]],
                colWidths=[2.4 * cm, usable_w - 2.4 * cm]
            )
            header_tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(header_tbl)
        except Exception:
            story.append(Paragraph(
                "<b>NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM</b>",
                ParagraphStyle("bank", fontName=fb, fontSize=12,
                               alignment=TA_CENTER, spaceAfter=1)
            ))
            story.append(Paragraph(
                "Chi nhánh tỉnh Đồng Nai",
                ParagraphStyle("branch", fontName=fn, fontSize=10,
                               alignment=TA_CENTER, spaceAfter=4)
            ))
    else:
        story.append(Paragraph(
            "<b>NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM</b>",
            ParagraphStyle("bank", fontName=fb, fontSize=12,
                           alignment=TA_CENTER, spaceAfter=1)
        ))
        story.append(Paragraph(
            "Chi nhánh tỉnh Đồng Nai",
            ParagraphStyle("branch", fontName=fn, fontSize=10,
                           alignment=TA_CENTER, spaceAfter=4)
        ))

    story.append(Spacer(1, 0.15 * cm))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=VBSP_GREEN, spaceAfter=0.2 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=VBSP_GREEN_MID, spaceAfter=0.4 * cm))
    story.append(Paragraph(
        _pdf_text(tieu_de.upper()),
        ParagraphStyle("title", fontName=fb, fontSize=14, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=0.15 * cm, leading=18)
    ))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  ·  Người xuất: {_pdf_text(nguoi_xuat)}  ·  Nguồn: Hệ thống HSTD VBSP-SCM",
        ParagraphStyle("meta", fontName=fn, fontSize=9, alignment=TA_CENTER,
                       textColor=TEXT_MUTED, spaceAfter=0.6 * cm)
    ))

    n_cols = len(df.columns)

    if n_cols <= 5:
        font_size = 11
    elif n_cols <= 8:
        font_size = 10
    elif n_cols <= 12:
        font_size = 9.5
    elif n_cols <= 16:
        font_size = 8.5
    else:
        font_size = 7.5

    header_font_size = font_size + 1.5

    cols_list = list(df.columns)

    def _col_ratio(col_name: str) -> float:
        c = str(col_name).strip().lower()
        if c in ("stt",):
            return 0.45
        if any(k in c for k in ("tiêu chí", "tieu chi", "chỉ tiêu", "chi tiêu",
                                 "đơn vị")):
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
        if any(k in c for k in ("tên kh", "ten kh", "khách hàng", "khach hang")):
            return 2.15
        if any(k in c for k in ("mã kh", "ma kh", "số ku", "so ku", "số khế", "so khe", "cmnd", "cccd")):
            return 1.6
        if any(k in c for k in ("tỷ lệ", "tl ", "%", "tỷ trọng", "ty trong")):
            return 0.9
        if any(k in c for k in ("số kh", "so kh", "số món", "so mon",
                                 "món qh", "mon qh")):
            return 0.9
        if "bq/kh" in c:
            return 1.15
        if "31/12" in c or c.startswith("±"):
            # Cột mốc 31/12 và tăng/giảm so mốc: rộng ngang cột tiền
            return 1.75
        if any(k in c for k in ("dư nợ", "du no", "trong hạn", "qua hạn",
                                 "quá hạn", "khoanh", "lãi", "tiền")):
            return 1.75
        return 1.3

    ratios = [_col_ratio(c) for c in cols_list]
    total_ratio = sum(ratios)
    col_widths = [usable_w * r / total_ratio for r in ratios]

    header_style = ParagraphStyle("th", fontName=fb, fontSize=header_font_size,
                                  alignment=TA_CENTER, textColor=colors.white,
                                  leading=header_font_size + 4)
    header_cells = [
        Paragraph(_pdf_text(str(c).replace("_", " ")), header_style)
        for c in cols_list
    ]
    table_data = [header_cells]

    cell_right_style = ParagraphStyle(
        "td_r", fontName=fn, fontSize=font_size, alignment=TA_RIGHT,
        leading=font_size + 3
    )
    cell_left_style = ParagraphStyle(
        "td_l", fontName=fn, fontSize=font_size, alignment=TA_LEFT,
        leading=font_size + 3, wordWrap="CJK"
    )
    cell_center_style = ParagraphStyle(
        "td_c", fontName=fn, fontSize=font_size, alignment=TA_CENTER,
        leading=font_size + 3, wordWrap="CJK"
    )

    def _is_left_align(col_name: str) -> bool:
        c = str(col_name).lower()
        left_keywords = ("chỉ tiêu", "chi tiêu", "đơn vị", "tiêu chí", "tieu chi",
                         "tên ", "ten ", "họ ", "ho ", "chương trình", "chuong trinh",
                         "xã", "xa", "huyện", "tỉnh", "thôn", "thon")
        return any(k in c for k in left_keywords) or c == cols_list[0].lower()

    def _is_center_align(col_name: str) -> bool:
        c = str(col_name).lower()
        return c in ("stt",) or any(k in c for k in ("xếp loại", "xep loai"))

    for _, row in df.iterrows():
        cells = []
        for ci, col in enumerate(cols_list):
            val = row[col]
            if pd.isna(val):
                p = Paragraph(
                    "",
                    cell_left_style if _is_left_align(col) else cell_right_style,
                )
            elif col in cols_percent:
                txt = _format_phan_tram(val)
                p = Paragraph(txt, cell_right_style)
            elif col in cols_tien and pd.notna(val):
                try:
                    txt = _format_number_pdf(val, col)
                    p = Paragraph(txt, cell_right_style)
                except (ValueError, TypeError):
                    p = Paragraph(_pdf_text(val), cell_right_style)
            elif col in cols_dem and pd.notna(val):
                try:
                    txt = _format_number_pdf(val, col)
                except (ValueError, TypeError):
                    txt = _pdf_text(val)
                p = Paragraph(txt, cell_right_style)
            elif col in cols_right:
                try:
                    txt = _format_number_pdf(val, col) if _is_number(val) else _pdf_text(val)
                except (ValueError, TypeError):
                    txt = _pdf_text(val)
                p = Paragraph(txt, cell_right_style)
            elif _is_left_align(col):
                p = Paragraph(_pdf_text(val), cell_left_style)
            elif _is_center_align(col):
                p = Paragraph(_pdf_text(val), cell_center_style)
            else:
                p = Paragraph(_pdf_text(val), cell_left_style)
            cells.append(p)
        table_data.append(cells)

    tong_right_style = ParagraphStyle(
        "tong_r", fontName=fb, fontSize=font_size, alignment=TA_RIGHT,
        leading=font_size + 3, textColor=VBSP_GREEN
    )
    tong_left_style = ParagraphStyle(
        "tong_l", fontName=fb, fontSize=font_size, alignment=TA_LEFT,
        leading=font_size + 3, textColor=VBSP_GREEN
    )
    tong_center_style = ParagraphStyle(
        "tong_c", fontName=fb, fontSize=font_size, alignment=TA_CENTER,
        leading=font_size + 3, textColor=VBSP_GREEN
    )

    if dong_tong_cells is not None:
        tong_cells = []
        for ci, col in enumerate(cols_list):
            val = dong_tong_cells.get(col, "")
            if pd.isna(val):
                val = ""
            txt = _pdf_text(val) if val else ""
            if col in cols_percent and val != "":
                try:
                    txt = f"<b>{_pdf_text(_format_phan_tram(val))}</b>"
                except Exception:
                    txt = f"<b>{txt}</b>"
                p = Paragraph(txt, tong_right_style)
            elif col in cols_tien and val != "":
                try:
                    txt = f"<b>{_pdf_text(_format_number_pdf(val, col))}</b>"
                except (ValueError, TypeError):
                    txt = f"<b>{txt}</b>"
                p = Paragraph(txt, tong_right_style)
            elif col in cols_dem and val != "":
                try:
                    txt = f"<b>{_pdf_text(_format_number_pdf(val, col))}</b>"
                except (ValueError, TypeError):
                    txt = f"<b>{txt}</b>"
                p = Paragraph(txt, tong_right_style)
            elif val == "TỔNG CỘNG":
                p = Paragraph("<b>TỔNG CỘNG</b>", tong_center_style)
            elif col in cols_right and val != "":
                try:
                    txt = _pdf_text(_format_number_pdf(val, col)) if _is_number(val) else txt
                except (ValueError, TypeError):
                    pass
                p = Paragraph(f"<b>{txt}</b>", tong_right_style)
            else:
                p = Paragraph(f"<b>{txt}</b>" if txt else "",
                              tong_left_style if _is_left_align(col) else tong_center_style)
            tong_cells.append(p)
        table_data.append(tong_cells)

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

    n_data_rows = len(table_data) - (1 if dong_tong_cells is not None else 0)
    for r in range(1, n_data_rows):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))

    if dong_tong_cells is not None:
        last_row = len(table_data) - 1
        style_cmds.extend([
            ("BACKGROUND", (0, last_row), (-1, last_row), VBSP_GREEN_LIGHT),
            ("FONTNAME",   (0, last_row), (-1, last_row), fb),
            ("LINEABOVE",  (0, last_row), (-1, last_row), 2.0, VBSP_GREEN),
            ("LINEBELOW",  (0, last_row), (-1, last_row), 1.2, VBSP_GREEN),
            ("TOPPADDING", (0, last_row), (-1, last_row), 7),
            ("BOTTOMPADDING", (0, last_row), (-1, last_row), 7),
        ])

    tbl.setStyle(TableStyle(style_cmds))

    for ci, col in enumerate(cols_list):
        c = str(col).lower()
        is_left = _is_left_align(col)
        is_center = _is_center_align(col)
        if not is_left and not is_center:
            tbl.setStyle(TableStyle([
                ("ALIGN", (ci, 1), (ci, -1), "RIGHT")
            ]))

    story.append(tbl)

    story.append(Spacer(1, 0.2 * cm))
    don_vi_hien = f"({don_vi_tien})" if don_vi_tien and don_vi_tien != "đồng" else ""
    if don_vi_hien or cols_percent or cols_tien:
        ghi_chu_parts = []
        if don_vi_hien:
            ghi_chu_parts.append(f"Đơn vị tiền: {don_vi_hien}")
        if cols_percent:
            ghi_chu_parts.append("Đơn vị %: phần trăm (%)")
        if cols_tien and not don_vi_hien:
            ghi_chu_parts.append("Đơn vị tiền: VND")
        if ghi_chu_parts:
            story.append(Paragraph(
                "  ·  ".join(ghi_chu_parts),
                ParagraphStyle("ghi_chu", fontName=fi, fontSize=8.5,
                               alignment=TA_LEFT, textColor=TEXT_MUTED,
                               spaceAfter=0.8 * cm, spaceBefore=0.2 * cm)
            ))

    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(
        f"Đồng Nai, ngày {datetime.now().strftime('%d')} "
        f"tháng {datetime.now().strftime('%m')} "
        f"năm {datetime.now().strftime('%Y')}",
        ParagraphStyle("date_sign", fontName=fn, fontSize=10,
                       alignment=TA_RIGHT, spaceAfter=0.6 * cm)
    ))

    fi_ky = fi if _FONT_REGISTERED else FONT_ITALIC_FALLBACK
    ky_data = [[
        Paragraph("<b>NGƯỜI LẬP BIỂU</b>", ParagraphStyle("ky_t", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
        Paragraph("<b>PHÒNG CHUYÊN MÔN</b>" if len(cols_list) >= 8 else "<b>KIỂM SOÁT</b>",
                  ParagraphStyle("ky_t2", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
        Paragraph("<b>GIÁM ĐỐC</b>", ParagraphStyle("ky_t3", fontName=fb, fontSize=10, alignment=TA_CENTER, spaceAfter=2)),
    ], [
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky_d", fontName=fi_ky, fontSize=9,
                                                               alignment=TA_CENTER, textColor=TEXT_MUTED)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky_d2", fontName=fi_ky, fontSize=9,
                                                               alignment=TA_CENTER, textColor=TEXT_MUTED)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ParagraphStyle("ky_d3", fontName=fi_ky, fontSize=9,
                                                               alignment=TA_CENTER, textColor=TEXT_MUTED)),
    ], [
        Paragraph(" ", ParagraphStyle("gap", fontSize=12, leading=28)),
        Paragraph(" ", ParagraphStyle("gap2", fontSize=12, leading=28)),
        Paragraph(" ", ParagraphStyle("gap3", fontSize=12, leading=28)),
    ]]
    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ky_tbl)

    def _on_page(canvas, _doc):
        canvas.saveState()
        fn_pg = fn if _FONT_REGISTERED else FONT_FALLBACK
        canvas.setFont(fn_pg, 8)
        canvas.setFillColor(TEXT_MUTED)
        canvas.drawRightString(
            page_size[0] - margin,
            0.8 * cm,
            f"Trang {_doc.page}  ·  VBSP-SCM  ·  {ngay_str}"
        )
        canvas.drawString(
            margin,
            0.8 * cm,
            "NHCSXH Đồng Nai  ·  Báo cáo nội bộ"
        )
        canvas.setStrokeColor(VBSP_GREEN_MID)
        canvas.setLineWidth(0.8)
        canvas.line(margin, 1.1 * cm, page_size[0] - margin, 1.1 * cm)
        canvas.restoreState()

    try:
        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    except Exception:
        doc.build(story)
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
    cols_dem = [_DN_SO_KH, _DN_SO_MON]
    cols_percent = [_DN_TL_QH]
    df_xuat, cols_tien, cols_dem, cols_percent = _prepare_pdf_export_frame(
        df_pivot,
        list(df_pivot.columns),
        cols_tien=cols_tien,
        cols_dem=cols_dem,
        cols_percent=cols_percent,
        scale_money=True,
    )

    return xuat_pdf(
        df_xuat,
        f"{tieu_de} (triệu đồng)",
        nguoi_xuat,
        cols_tien=cols_tien,
        don_vi_tien="triệu đồng",
        prefix_file=prefix_file,
        them_dong_tong=True,
        cols_right=cols_dem + cols_percent,
        cols_percent=cols_percent,
        cols_dem=cols_dem,
    )


def xuat_pdf_chi_tiet(
    df: pd.DataFrame,
    cols_hien_thi: list[str],
    tieu_de: str,
    nguoi_xuat: str,
    prefix_file: str = "BC_CT",
    cols_tien: list[str] | None = None,
    cols_percent: list[str] | None = None,
    cols_dem: list[str] | None = None,
    don_vi_tien: str = "đồng",
    scale_money: bool = False,
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    if df is None or df.empty:
        raise ValueError("Không có dữ liệu để xuất PDF")

    _dang_ky_font()

    df_xuat, cols_tien, cols_dem, cols_percent = _prepare_pdf_export_frame(
        df,
        cols_hien_thi,
        cols_tien=cols_tien,
        cols_dem=cols_dem,
        cols_percent=cols_percent,
        scale_money=scale_money,
    )

    return xuat_pdf(
        df_xuat,
        tieu_de,
        nguoi_xuat,
        cols_tien=cols_tien,
        don_vi_tien=don_vi_tien,
        prefix_file=prefix_file,
        them_dong_tong=True,
        cols_right=cols_dem + cols_percent,
        cols_percent=cols_percent,
        cols_dem=cols_dem,
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
        _pdf_text(tieu_de.upper()),
        ParagraphStyle("title_nhom", fontName=fb, fontSize=12, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=4)
    ))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {_pdf_text(nguoi_xuat)}",
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
            f"<b>{_pdf_text(nhom_label)}</b> - {n_ho_so} hồ sơ - Tổng dư nợ: {tong_str}",
            ParagraphStyle("section_nhom", fontName=fb, fontSize=10,
                           textColor=VBSP_GREEN, spaceAfter=6)
        ))

        nhom_display = nhom_df[cols_co].copy()

        header_cells = [
            Paragraph(_pdf_text(str(c).replace("_", " ")), ParagraphStyle("th_nhom", fontName=fb,
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
                        txt = _format_number_pdf(val, col)
                        p = Paragraph(txt, ParagraphStyle("td_r_nhom", fontName=fn,
                                          fontSize=font_size, alignment=TA_RIGHT))
                    except (ValueError, TypeError):
                        p = Paragraph(
                            _pdf_text(val),
                            ParagraphStyle("td_r_nhom2", fontName=fn,
                                           fontSize=font_size, alignment=TA_RIGHT),
                        )
                else:
                    p = Paragraph(_pdf_text(val),
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

        col_widths = _column_widths_pdf(cols_co, usable_w) if n_cols else [usable_w]
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
        tieu_de_day_du = f"{tieu_de} - {tieu_de_phu}"
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
        _pdf_text(day_du_tieu_de.upper()),
        ParagraphStyle("title2", fontName=fb, fontSize=12, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=4)
    ))
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {_pdf_text(nguoi_xuat)}",
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
                f"<b>{_pdf_text(label)}</b><br/>{_pdf_text(val)}{_pdf_text(delta_str)}",
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
            Paragraph(_pdf_text(str(c).replace("_", " ")), ParagraphStyle("th2", fontName=fb,
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
                        p = Paragraph(_pdf_text(val),
                                      ParagraphStyle("td2", fontName=fn,
                                        fontSize=font_size, wordWrap="CJK"))
                else:
                    p = Paragraph(_pdf_text(val),
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
        co_quan_html += f"<br/><font size='9'>{_pdf_text(so_hieu)}</font>"

    co_quan_left = Paragraph(
        co_quan_html,
        ParagraphStyle("co_quan", fontName=fb, fontSize=10,
                       alignment=TA_LEFT, leading=14),
    )
    quoc_hieu_right = Paragraph(
        "<b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b><br/>"
        "<b>Độc lập - Tự do - Hạnh phúc</b><br/>"
        "<font size='9'>-------------------</font>",
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
            _pdf_text(loai_van_ban.upper()),
            ParagraphStyle("loai_vb", fontName=fb, fontSize=10,
                           alignment=TA_CENTER, spaceAfter=2),
        ))
    story.append(Paragraph(
        _pdf_text(day_du_tieu_de.upper()),
        ParagraphStyle("title3", fontName=fb, fontSize=11, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=2),
    ))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {_pdf_text(nguoi_xuat or 'VBSP-SCM')}",
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
                f"<b>{_pdf_text(nhom_theo)}: {_pdf_text(nhom_label)}</b>",
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
                Paragraph(_pdf_text(str(c).replace("_", " ")), ParagraphStyle("th3", fontName=fb,
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
                            txt = _format_number_pdf(val, col)
                            p = Paragraph(txt, ParagraphStyle("td_r3", fontName=fn,
                                              fontSize=font_size, alignment=TA_RIGHT))
                        except (ValueError, TypeError):
                            p = Paragraph(_pdf_text(val),
                                          ParagraphStyle("td3", fontName=fn,
                                            fontSize=font_size, wordWrap="CJK"))
                    else:
                        p = Paragraph(_pdf_text(val),
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

            col_widths = _column_widths_pdf(list(nhom_df.columns), usable_w) if n_cols else [usable_w]
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
