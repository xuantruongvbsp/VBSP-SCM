from io import BytesIO
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st

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
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    """
    Xuất DataFrame ra PDF chuẩn in A4, hỗ trợ tiếng Việt.
    Tự động landscape nếu số cột >= 8 hoặc prefix_file == "TQPGD".
    Trả về bytes để dùng với st.download_button.
    """
    _dang_ky_font()
    from utils import fmt_so

    cols_tien = cols_tien or []

    if df is None or df.empty:
        raise ValueError("Không có dữ liệu để xuất PDF.")

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

    # ── 2. Bảng dữ liệu ───────────────────────────────────────────────
    n_cols = len(df.columns)
    
    # Tự động co font size theo số cột
    if n_cols <= 6:
        font_size = 11
    elif n_cols <= 10:
        font_size = 10
    elif n_cols <= 14:
        font_size = 9
    else:
        font_size = 8

    header_font_size = font_size + 2

    # Header row — font nhỏ hơn cho bảng nhiều cột
    h_font = header_font_size if n_cols <= 10 else max(font_size - 1, 7)
    header_cells = [
        Paragraph(
            str(c).replace("_", " ").replace(" (tỷ)", "\n(tỷ)").replace(" %", "\n%"),
            ParagraphStyle("th", fontName=fb, fontSize=h_font,
                           alignment=TA_CENTER, textColor=colors.white,
                           leading=h_font + 2)
        )
        for c in df.columns
    ]
    table_data = [header_cells]

    # Data rows — format số tiền
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

            # Cột tên đơn vị — rộng nhất
            if any(k in c for k in ("đơn vị", "don vi", "tên pgd", "ten pgd")):
                return 3.5

            # Cột số lượng nguyên (KH, Tổ)
            if any(k in c for k in ("số kh", "so kh", "tổng tổ", "tong to",
                                     "tốt", "tot", "khá", "kha", " tb", "yếu", "yeu")):
                return 0.7

            # Cột tiền tỷ
            if any(k in c for k in ("dư nợ", "du no", "qh (", "khoanh", "lãi tồn",
                                     "nợ xấu", "no xau", "nợ đh", "no dh",
                                     "ds cho", "ds thu")):
                return 1.1

            # Cột tỷ lệ %
            if any(k in c for k in ("tl qh", "tl kh", "tl npl", "% ", "tỷ lệ")):
                return 0.8

            return 1.2

        ratios = [_col_ratio(c) for c in cols_list]
        total_ratio = sum(ratios)
        col_widths = [usable_w * r / total_ratio for r in ratios]
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
    )


def nut_xuat_pdf(
    df: pd.DataFrame,
    tieu_de: str,
    username: str,
    cols_tien: list[str] | None = None,
    prefix_file: str = "BC",
    key: str = "btn_pdf",
) -> None:
    """
    Render nút 'Xuất PDF' + download_button inline trong Streamlit tab.
    Gọi: nut_xuat_pdf(export_df, "Báo cáo dư nợ", username,
                      cols_tien=[COT_TONG_DU_NO, COT_DU_NO_QH])
    """
    if st.button("📄 Xuất PDF", key=key, type="secondary"):
        try:
            with st.spinner("Đang tạo PDF..."):
                pdf_bytes = xuat_pdf(df, tieu_de, username, cols_tien, prefix_file=prefix_file)
            ten_file = f"{prefix_file}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf"
            st.download_button(
                label="⬇ Tải file PDF",
                data=pdf_bytes,
                file_name=ten_file,
                mime="application/pdf",
                key=f"{key}_dl",
            )
            st.success("✅ PDF đã tạo xong")
        except Exception as e:
            st.error(f"❌ Lỗi tạo PDF: {e}")
