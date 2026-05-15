from io import BytesIO
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from config import COT_MA_KH, COT_TONG_DU_NO

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable, Image as RLImage
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    _REPORTLAB_READY = True
except ImportError:
    _REPORTLAB_READY = False

_FONT_REGISTERED = False


def _dang_ky_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    # Tìm font theo thứ tự ưu tiên:
    # 1. File .ttf trong thư mục assets/ của project
    # 2. Font hệ thống Windows C:/Windows/Fonts/
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

    # Fallback nếu không có Times: dùng Helvetica (ASCII only, báo lỗi)
    if not regular:
        warnings.warn("Không tìm thấy times.ttf — tiếng Việt có thể bị lỗi font.")

    _FONT_REGISTERED = True


FONT_NORMAL = "TNR"       # dùng sau khi _dang_ky_font() đã chạy
FONT_BOLD = "TNR-Bold"
FONT_FALLBACK = "Helvetica"  # khi font chưa đăng ký được

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
    tieu_de_phu: str = "",
) -> bytes:
    """
    Xuất DataFrame ra PDF chuẩn in A4, hỗ trợ tiếng Việt.
    Tự động landscape nếu số cột >= 8 hoặc prefix_file == "TQPGD".
    Trả về bytes để dùng với st.download_button.
    """
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    _dang_ky_font()
    from utils import vn

    cols_tien = cols_tien or []

    if df is None or df.empty:
        raise ValueError("Không có dữ liệu để xuất PDF.")

    # PERF: Giới hạn số dòng để tránh PDF quá lớn
    MAX_ROWS_PDF = 2000
    if len(df) > MAX_ROWS_PDF:
        df = df.head(MAX_ROWS_PDF)
        st.warning(f"⚠️ PDF chỉ xuất {MAX_ROWS_PDF} dòng đầu (tổng {len(df)} dòng)")

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
    # Landscape nếu nhiều cột hoặc báo cáo TQPGD
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

    # ── 1. Header báo cáo ──────────────────────────────────────────────
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
    # Tiêu đề báo cáo
    title_style = ParagraphStyle(
        "title",
        fontName=fb if _FONT_REGISTERED else FONT_FALLBACK,
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=6,
        textColor=colors.HexColor("#003D7A"),
    )
    sub_style = ParagraphStyle(
        "sub",
        fontName=fn if _FONT_REGISTERED else FONT_FALLBACK,
        fontSize=9,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.grey,
    )
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(tieu_de.upper(), title_style))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {nguoi_xuat}",
        sub_style,
    ))
    if tieu_de_phu:
        story.append(Paragraph(tieu_de_phu, sub_style))
    story.append(Spacer(1, 0.3 * cm))

    # ── 2. Bảng dữ liệu ───────────────────────────────────────────────
    n_cols = len(df.columns)
    
    if n_cols <= 5:
        font_size = 13
    elif n_cols <= 8:
        font_size = 11
    elif n_cols <= 12:
        font_size = 10
    elif n_cols <= 16:
        font_size = 9
    else:
        font_size = 8

    header_font_size = font_size + 2

    # Header row — font nhỏ hơn cho bảng nhiều cột
    h_font = header_font_size if n_cols <= 10 else max(font_size - 1, 7)
    header_cells = [
        Paragraph(
            str(c).replace("_", " ").replace("(triệu đồng)", "\n(triệu đồng)").replace(" %", "\n%"),
            ParagraphStyle("th", fontName=fb, fontSize=h_font,
                           alignment=TA_CENTER, textColor=colors.white,
                           leading=h_font + 2)
        )
        for c in df.columns
    ]
    table_data = [header_cells]

    def _fmt_tien_pdf(val: object) -> str:
        try:
            if isinstance(val, bool):
                raise ValueError
            if isinstance(val, (int, float)):
                num = float(val)
            else:
                num = float(str(val).strip().replace(".", "").replace(",", "."))
            if abs(num) > 0:
                trieu = num / 1_000_000
                return f"{trieu:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return "0"
        except Exception:
            return str(val) if pd.notna(val) else ""

    # Data rows — format số tiền
    # PERF: vectorized thay thế vòng lặp df.iterrows()
    # Pre-build styles một lần ngoài vòng lặp
    style_td = ParagraphStyle("td", fontName=fn, fontSize=font_size, wordWrap="CJK")
    style_td_r = ParagraphStyle("td_r", fontName=fn, fontSize=font_size, alignment=TA_RIGHT)
    cols_list = list(df.columns)
    set_tien = set(cols_tien or [])
    
    # Chuyển df sang list of lists một lần (tránh overhead iterrows)
    arr = df.fillna("").values.tolist()
    
    for row_vals in arr:
        cells = []
        for ci, val in enumerate(row_vals):
            col = cols_list[ci]
            if col in set_tien and val != "":
                try:
                    if isinstance(val, bool):
                        raise ValueError
                    txt = _fmt_tien_pdf(val)
                    cells.append(Paragraph(txt, style_td_r))
                except (ValueError, TypeError):
                    cells.append(Paragraph(str(val), style_td_r))
            else:
                cells.append(Paragraph(str(val) if val != "" else "", style_td))
        table_data.append(cells)

    if dong_tong_cells is not None:
        tong_cells = []
        for col in df.columns:
            val = dong_tong_cells[col]
            if col in cols_tien and isinstance(val, (int, float)):
                txt = _fmt_tien_pdf(val)
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
        col_max_chars = []
        col_widths = []
        for col in df.columns:
            header_len = len(str(col))
            try:
                pd.to_numeric(df[col], errors="raise")
                data_len = 8
            except (ValueError, TypeError):
                data_len = min(df[col].astype(str).str.len().max(), 20) if len(df) > 0 else 0
            col_max_chars.append(max(header_len, data_len, 4))

        total_chars = sum(col_max_chars) or 1
        col_widths = [max((c / total_chars) * usable_w, 1.2 * cm) for c in col_max_chars]
        total_w = sum(col_widths)
        if total_w > usable_w and total_w > 0:
            scale = usable_w / total_w
            col_widths = [w * scale for w in col_widths]
    else:
        col_widths = [usable_w]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Style bảng
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), fb),
        ("FONTSIZE", (0, 0), (-1, 0), header_font_size),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        # Border toàn bảng
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("BOX", (0, 0), (-1, -1), 1, VBSP_GREEN),
    ]
    # Xen kẽ màu dòng
    for r in range(1, len(table_data)):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))

    # Style dòng tổng cộng (dòng cuối)
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

    # ── 3. Phần chữ ký ────────────────────────────────────────────────
    story.append(Spacer(1, 1.5 * cm))

    # Dòng ngày tháng căn phải
    ngay_ky = datetime.now().strftime("Đồng Nai, ngày %d tháng %m năm %Y")
    story.append(Paragraph(
        ngay_ky,
        ParagraphStyle("ngay_ky",
            fontName=fn if _FONT_REGISTERED else FONT_FALLBACK,
            fontSize=10,
            alignment=TA_RIGHT,
            spaceAfter=16,
        )
    ))

    # Bảng 3 cột chữ ký
    ky_style = ParagraphStyle("ky",
        fontName=fb if _FONT_REGISTERED else FONT_FALLBACK,
        fontSize=10,
        alignment=TA_CENTER,
    )
    ky_sub_style = ParagraphStyle("ky_sub",
        fontName=fn if _FONT_REGISTERED else FONT_FALLBACK,
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.grey,
    )
    gap_style = ParagraphStyle("gap",
        fontName=fn if _FONT_REGISTERED else FONT_FALLBACK,
        fontSize=10,
    )

    ky_data = [
        [
            Paragraph("NGƯỜI LẬP BIỂU", ky_style),
            Paragraph("TRƯỞNG PHÒNG KH-NV", ky_style),
            Paragraph("GIÁM ĐỐC", ky_style),
        ],
        [
            Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ky_sub_style),
            Paragraph("<i>(Ký, ghi rõ họ tên)</i>", ky_sub_style),
            Paragraph("<i>(Ký, đóng dấu)</i>", ky_sub_style),
        ],
        [
            Paragraph(" \n\n\n", gap_style),
            Paragraph(" \n\n\n", gap_style),
            Paragraph(" \n\n\n", gap_style),
        ],
    ]

    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ky_tbl)

    # ── 4. Header/Footer mỗi trang (số trang) ─────────────────────────
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


def xuat_pdf_bang(
    df: pd.DataFrame,
    tieu_de: str,
    tieu_de_phu: str = "",
    *,
    nguoi_xuat: str = "",
    cols_tien: list[str] | None = None,
    prefix_file: str = "",
) -> bytes:
    """
    Xuất một bảng DataFrame ra PDF (wrapper gọi `xuat_pdf`).
    Ghép phụ đề vào tiêu đề khi có `tieu_de_phu`.
    """
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
        tieu_de_phu=tieu_de_phu,
    )


def xuat_pdf_group_header(
    df: pd.DataFrame,
    tieu_de: str,
    nhom_theo: str,
    *,
    nguoi_xuat: str = "",
    cols_tien: list[str] | None = None,
    tieu_de_phu: str = "",
    loc_pgd: str = "",
    loc_ct: str = "",
    loc_xa: str = "",
) -> bytes:
    """
    Xuất PDF dạng Group Header/Group Footer — cấu trúc giống Access Report.

    Cấu trúc:
    - Report Header : tiêu đề, ngày xuất, thông tin bộ lọc
    - Group Header  : tên nhóm (nền xanh nhạt, in đậm)
    - Detail rows   : danh sách hồ sơ thuộc nhóm
    - Group Footer  : tổng món vay / tổng KH / tổng dư nợ của nhóm (in đậm)
    - Report Footer : tổng toàn báo cáo

    Tham số:
        df          : DataFrame chi tiết (đã lọc theo điều kiện bộ lọc bên ngoài)
        tieu_de     : Tiêu đề báo cáo
        nhom_theo   : Tên cột dùng để nhóm (ví dụ COT_TEN_CT / COT_TEN_PGD / COT_TEN_XA)
        nguoi_xuat  : Tên người xuất
        cols_tien   : Danh sách cột tiền (sẽ format số, tính tổng)
        tieu_de_phu : Phụ đề / thông tin bổ sung hiển thị dưới tiêu đề
        loc_pgd     : Giá trị bộ lọc PGD (chỉ để hiển thị info)
        loc_ct      : Giá trị bộ lọc chương trình (chỉ để hiển thị info)
        loc_xa      : Giá trị bộ lọc xã (chỉ để hiển thị info)
    """
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    _dang_ky_font()
    from utils import fmt_so

    cols_tien = cols_tien or []

    if df is None or df.empty:
        raise ValueError("Không có dữ liệu để xuất PDF.")
    if nhom_theo not in df.columns:
        raise ValueError(f"Cột nhóm '{nhom_theo}' không tồn tại trong DataFrame.")

    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD if _FONT_REGISTERED else FONT_FALLBACK

    buf = BytesIO()
    page_size = A4
    margin = 1.0 * cm
    usable_w = page_size[0] - 2 * margin

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=2 * cm,
        title=tieu_de,
        author="VBSP-SCM",
    )

    # ── Style chung ──────────────────────────────────────────────────────────
    _st_normal = ParagraphStyle("gh_normal", fontName=fn, fontSize=9, leading=12)
    _st_bold   = ParagraphStyle("gh_bold",   fontName=fb, fontSize=9, leading=12)
    _st_right  = ParagraphStyle("gh_right",  fontName=fn, fontSize=9, leading=12,
                                alignment=TA_RIGHT)
    _st_bold_r = ParagraphStyle("gh_bold_r", fontName=fb, fontSize=9, leading=12,
                                alignment=TA_RIGHT)
    _st_center = ParagraphStyle("gh_center", fontName=fn, fontSize=9, leading=12,
                                alignment=TA_CENTER)
    _st_h3 = ParagraphStyle("gh_h3", fontName=fb, fontSize=10, leading=14,
                            textColor=VBSP_GREEN)

    story: list = []

    # ── Report Header ────────────────────────────────────────────────────────
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        logo = RLImage(str(logo_path), width=2.0 * cm, height=2.0 * cm)
        from reportlab.platypus import Table as RLTable
        hdr_tbl = RLTable(
            [[logo, Paragraph(
                "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM<br/>"
                "<font size='9'>Chi nhánh tỉnh Đồng Nai</font>",
                ParagraphStyle("rh_txt", fontName=fb, fontSize=11,
                               alignment=TA_CENTER, leading=15)
            )]],
            colWidths=[2.3 * cm, usable_w - 2.3 * cm]
        )
        hdr_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(hdr_tbl)
    else:
        story.append(Paragraph(
            "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM — Chi nhánh tỉnh Đồng Nai",
            ParagraphStyle("rh_txt2", fontName=fb, fontSize=11,
                           alignment=TA_CENTER, spaceAfter=4)
        ))

    story.append(HRFlowable(width="100%", thickness=1.5, color=VBSP_GREEN, spaceAfter=4))
    story.append(Paragraph(
        tieu_de.upper(),
        ParagraphStyle("rh_title", fontName=fb, fontSize=13, alignment=TA_CENTER,
                       textColor=VBSP_GREEN, spaceAfter=3)
    ))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {nguoi_xuat or 'VBSP-SCM'}",
        ParagraphStyle("rh_meta", fontName=fn, fontSize=8, alignment=TA_CENTER,
                       textColor=colors.grey, spaceAfter=3)
    ))

    # Hiển thị thông tin bộ lọc đang áp dụng
    loc_parts: list[str] = []
    if loc_pgd:
        loc_parts.append(f"PGD: <b>{loc_pgd}</b>")
    if loc_ct:
        loc_parts.append(f"Chương trình: <b>{loc_ct}</b>")
    if loc_xa:
        loc_parts.append(f"Xã: <b>{loc_xa}</b>")
    if tieu_de_phu:
        loc_parts.insert(0, tieu_de_phu)

    if loc_parts:
        story.append(Paragraph(
            "  |  ".join(loc_parts),
            ParagraphStyle("rh_filter", fontName=fn, fontSize=8, alignment=TA_CENTER,
                           textColor=colors.HexColor("#1B5E20"), spaceAfter=6)
        ))
    else:
        story.append(Spacer(1, 0.3 * cm))

    # ── Xác định các cột hiển thị detail ────────────────────────────────────
    detail_cols = [c for c in df.columns if c != nhom_theo]

    # Tính tỷ lệ độ rộng cột detail
    def _detail_ratio(col_name: str) -> float:
        c = str(col_name).lower()
        if any(k in c for k in ("tên kh", "ten kh")):
            return 2.8
        if any(k in c for k in ("tên chương trình", "ten chuong trinh", "chương trình")):
            return 2.5
        if any(k in c for k in ("số khế ước", "so khe uoc", "khế ước")):
            return 1.8
        if any(k in c for k in ("ngày đến hạn", "ngay den han")):
            return 1.5
        if any(k in c for k in ("tháng đến hạn", "thang den han", "tháng còn")):
            return 1.2
        if any(k in c for k in ("dư nợ", "du no", "tổng dư")):
            return 1.4
        if any(k in c for k in ("mã kh", "ma kh")):
            return 1.2
        return 1.0

    det_ratios = [_detail_ratio(c) for c in detail_cols]
    det_total  = sum(det_ratios)
    det_widths = [usable_w * r / det_total for r in det_ratios]

    # ── Màu sắc group ────────────────────────────────────────────────────────
    GH_BG  = colors.HexColor("#DCEEFB")   # Group Header nền xanh nhạt
    GF_BG  = VBSP_GREEN_LIGHT              # Group Footer nền xanh lá nhạt
    RF_BG  = colors.HexColor("#E8F5E9")   # Report Footer

    # ── Tổng toàn báo cáo ────────────────────────────────────────────────────
    report_so_mon:  int   = 0
    report_so_kh:   int   = 0
    report_tong_dn: float = 0.0

    # ── Lặp qua từng nhóm ────────────────────────────────────────────────────
    cot_ma_kh = None
    if COT_MA_KH in df.columns:
        cot_ma_kh = COT_MA_KH
    cot_du_no = COT_TONG_DU_NO if COT_TONG_DU_NO in df.columns else None

    groups = df.groupby(nhom_theo, sort=True)

    for ten_nhom, grp in groups:
        # ── Group Header ─────────────────────────────────────────────────────
        story.append(Spacer(1, 0.2 * cm))
        gh_tbl = Table(
            [[Paragraph(str(ten_nhom), ParagraphStyle(
                "gh_lbl", fontName=fb, fontSize=10, leading=14,
                textColor=colors.HexColor("#1A237E")
            ))]],
            colWidths=[usable_w],
        )
        gh_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GH_BG),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#1565C0")),
        ]))
        story.append(gh_tbl)

        # ── Header row của bảng detail ────────────────────────────────────────
        det_header = [
            Paragraph(
                str(c).replace("_", " "),
                ParagraphStyle("det_th", fontName=fb, fontSize=8,
                               alignment=TA_CENTER, textColor=colors.white, leading=10)
            )
            for c in detail_cols
        ]
        detail_data = [det_header]

        # ── Detail rows ───────────────────────────────────────────────────────
        for _, row in grp.iterrows():
            cells = []
            for col in detail_cols:
                val = row[col]
                if col in cols_tien and pd.notna(val):
                    try:
                        txt = fmt_so(float(val))
                        cells.append(Paragraph(txt, _st_right))
                    except (ValueError, TypeError):
                        cells.append(Paragraph(str(val) if pd.notna(val) else "", _st_right))
                else:
                    cells.append(Paragraph(str(val) if pd.notna(val) else "", _st_normal))
            detail_data.append(cells)

        det_tbl = Table(detail_data, colWidths=det_widths, repeatRows=1)
        det_style = [
            ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), fb),
            ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER_COLOR),
        ]
        # Xen kẽ màu dòng detail
        for r in range(1, len(detail_data)):
            if r % 2 == 0:
                det_style.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))
        det_tbl.setStyle(TableStyle(det_style))
        story.append(det_tbl)

        # ── Group Footer ──────────────────────────────────────────────────────
        so_mon_nhom  = len(grp)
        so_kh_nhom   = grp[cot_ma_kh].nunique() if cot_ma_kh else so_mon_nhom
        tong_dn_nhom = grp[cot_du_no].sum() if cot_du_no else 0.0

        report_so_mon  += so_mon_nhom
        report_so_kh   += so_kh_nhom
        report_tong_dn += tong_dn_nhom

        gf_cells = [
            Paragraph(
                f"<b>Tổng nhóm: {so_mon_nhom} món vay"
                f" | {so_kh_nhom} KH"
                f" | Dư nợ: {fmt_so(tong_dn_nhom)}</b>",
                ParagraphStyle("gf_lbl", fontName=fb, fontSize=8,
                               alignment=TA_RIGHT, leading=11,
                               textColor=colors.HexColor("#1B5E20"))
            )
        ]
        gf_tbl = Table([gf_cells], colWidths=[usable_w])
        gf_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), GF_BG),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("LINEABOVE", (0, 0), (-1, 0), 0.8, VBSP_GREEN),
        ]))
        story.append(gf_tbl)

    # ── Report Footer ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=VBSP_GREEN, spaceAfter=4))
    rf_cells = [
        Paragraph(
            f"<b>TỔNG TOÀN BÁO CÁO: {report_so_mon} món vay"
            f" | {report_so_kh} khách hàng"
            f" | Tổng dư nợ: {fmt_so(report_tong_dn)}</b>",
            ParagraphStyle("rf_lbl", fontName=fb, fontSize=10,
                           alignment=TA_RIGHT, leading=14,
                           textColor=VBSP_GREEN)
        )
    ]
    rf_tbl = Table([rf_cells], colWidths=[usable_w])
    rf_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), RF_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 1, VBSP_GREEN),
    ]))
    story.append(rf_tbl)

    # ── Chữ ký ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(
        f"Đồng Nai, ngày {datetime.now().strftime('%d')} "
        f"tháng {datetime.now().strftime('%m')} "
        f"năm {datetime.now().strftime('%Y')}",
        ParagraphStyle("rf_date", fontName=fn, fontSize=9,
                       alignment=TA_RIGHT, spaceAfter=4)
    ))
    ky_data = [[
        Paragraph("NGƯỜI LẬP BIỂU",
                  ParagraphStyle("ky", fontName=fb, fontSize=9, alignment=TA_CENTER)),
        Paragraph("KIỂM SOÁT",
                  ParagraphStyle("ky", fontName=fb, fontSize=9, alignment=TA_CENTER)),
        Paragraph("GIÁM ĐỐC",
                  ParagraphStyle("ky", fontName=fb, fontSize=9, alignment=TA_CENTER)),
    ], [
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>",
                  ParagraphStyle("ky2", fontName=fn, fontSize=8,
                                 alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>",
                  ParagraphStyle("ky2", fontName=fn, fontSize=8,
                                 alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("<i>(Ký, ghi rõ họ tên)</i>",
                  ParagraphStyle("ky2", fontName=fn, fontSize=8,
                                 alignment=TA_CENTER, textColor=colors.grey)),
    ], [
        Paragraph("&nbsp;", ParagraphStyle("gap", fontName=fn, fontSize=24)),
        Paragraph("&nbsp;", ParagraphStyle("gap", fontName=fn, fontSize=24)),
        Paragraph("&nbsp;", ParagraphStyle("gap", fontName=fn, fontSize=24)),
    ]]
    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(ky_tbl)

    # ── Số trang footer mỗi trang ────────────────────────────────────────────
    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn if _FONT_REGISTERED else FONT_FALLBACK, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            page_size[0] - margin, 0.7 * cm,
            f"Trang {_doc.page}  |  VBSP-SCM  |  {ngay_str}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.getvalue()


def nut_xuat_pdf(
    df: pd.DataFrame,
    tieu_de: str,
    username: str,
    cols_tien: list[str] | None = None,
    prefix_file: str = "BC",
    key: str = "btn_pdf",
    tieu_de_phu: str = "",
) -> None:
    """
    Render nút 'Xuất PDF' + download_button inline trong Streamlit tab.
    Gọi: nut_xuat_pdf(export_df, "Báo cáo dư nợ", username,
                      cols_tien=[COT_TONG_DU_NO, COT_DU_NO_QH])
    """
    ss_key = f"_pdf_bytes_{key}"

    if st.button("📄 Xuất PDF", key=key):
        try:
            with st.spinner("⏳ Đang tạo PDF..."):
                pdf_bytes = xuat_pdf(df, tieu_de, username, cols_tien, prefix_file=prefix_file, tieu_de_phu=tieu_de_phu)
            st.session_state[ss_key] = {"data": pdf_bytes, "filename": f"{prefix_file}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf"}
        except Exception as e:
            import traceback
            st.session_state[ss_key] = None
            st.error(f"❌ Lỗi tạo PDF: {e}")
            st.code(traceback.format_exc())

    if ss_key in st.session_state and st.session_state[ss_key]:
        pdf_info = st.session_state[ss_key]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.download_button(
                label="⬇ Tải file PDF đã tạo",
                data=pdf_info["data"],
                file_name=pdf_info["filename"],
                mime="application/pdf",
                key=f"{key}_dl",
            )
        with col2:
            if st.button("✕", key=f"{key}_clear", help="Tạo lại"):
                del st.session_state[ss_key]
                st.rerun()
