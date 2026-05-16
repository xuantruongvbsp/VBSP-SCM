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
    # TÃ¬m font theo thá»© tá»± Æ°u tiÃªn:
    # 1. File .ttf trong thÆ° má»¥c assets/ cá»§a project
    # 2. Font há»‡ thá»‘ng Windows C:/Windows/Fonts/
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

    # Fallback náº¿u khÃ´ng cÃ³ Times: dÃ¹ng Helvetica (ASCII only, bÃ¡o lá»—i)
    if not regular:
        warnings.warn("KhÃ´ng tÃ¬m tháº¥y times.ttf â€” tiáº¿ng Viá»‡t cÃ³ thá»ƒ bá»‹ lá»—i font.")

    _FONT_REGISTERED = True


FONT_NORMAL = "TNR"       # dÃ¹ng sau khi _dang_ky_font() Ä‘Ã£ cháº¡y
FONT_BOLD = "TNR-Bold"
FONT_FALLBACK = "Helvetica"  # khi font chÆ°a Ä‘Äƒng kÃ½ Ä‘Æ°á»£c

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
    don_vi_tien: str = "Ä‘á»“ng",
    prefix_file: str = "",
    them_dong_tong: bool = True,
) -> bytes:
    if not _REPORTLAB_READY:
        raise ImportError("ChÆ°a cÃ i thÆ° viá»‡n reportlab. Cháº¡y: pip install reportlab")
    """
    Xuáº¥t DataFrame ra PDF chuáº©n in A4, há»— trá»£ tiáº¿ng Viá»‡t.
    Tá»± Ä‘á»™ng landscape náº¿u sá»‘ cá»™t >= 8 hoáº·c prefix_file == "TQPGD".
    Tráº£ vá» bytes Ä‘á»ƒ dÃ¹ng vá»›i st.download_button.
    """
    _dang_ky_font()
    from utils import fmt_so

    cols_tien = cols_tien or []

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
                tong_row[col] = "Tá»”NG Cá»˜NG" if list(df.columns).index(col) == 0 else ""
        dong_tong_cells = tong_row

    buf = BytesIO()
    # Landscape náº¿u nhiá»u cá»™t hoáº·c bÃ¡o cÃ¡o TQPGD
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

    # â”€â”€ 1. Header bÃ¡o cÃ¡o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        logo = RLImage(str(logo_path), width=2.2 * cm, height=2.2 * cm)
        from reportlab.platypus import Table as RLTable
        header_tbl = RLTable(
            [[logo, Paragraph(
                "NGÃ‚N HÃ€NG CHÃNH SÃCH XÃƒ Há»˜I VIá»†T NAM<br/>"
                "<font size='10'>Chi nhÃ¡nh tá»‰nh Äá»“ng Nai</font>",
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
            "NGÃ‚N HÃ€NG CHÃNH SÃCH XÃƒ Há»˜I VIá»†T NAM",
            ParagraphStyle("bank", fontName=fb, fontSize=12,
                           alignment=TA_CENTER, spaceAfter=2)
        ))
        story.append(Paragraph(
            "CHI NHÃNH Tá»ˆNH Äá»’NG NAI",
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
        f"NgÃ y xuáº¥t: {ngay_str}  |  NgÆ°á»i xuáº¥t: {nguoi_xuat}",
        ParagraphStyle("meta", fontName=fn, fontSize=9, alignment=TA_CENTER,
                       textColor=colors.grey, spaceAfter=12)
    ))

    # â”€â”€ 2. Báº£ng dá»¯ liá»‡u â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    n_cols = len(df.columns)
    
    # Tá»± Ä‘á»™ng co font size theo sá»‘ cá»™t
    if n_cols <= 6:
        font_size = 11
    elif n_cols <= 10:
        font_size = 10
    elif n_cols <= 14:
        font_size = 9
    else:
        font_size = 8

    header_font_size = font_size + 2

    # Header row
    header_cells = [
        Paragraph(str(c).replace("_", " "), ParagraphStyle("th", fontName=fb,
                  fontSize=header_font_size, alignment=TA_CENTER,
                  textColor=colors.white))
        for c in df.columns
    ]
    table_data = [header_cells]

    # Data rows â€” format sá»‘ tiá»n
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
            elif val == "Tá»”NG Cá»˜NG":
                p = Paragraph(
                    "<b>Tá»”NG Cá»˜NG</b>",
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
            if any(k in c for k in ("tiÃªu chÃ­", "tieu chi")):
                return 2.5
            if any(k in c for k in ("tá»• trÆ°á»Ÿng", "to truong")):
                return 2.0
            if any(k in c for k in ("xáº¿p loáº¡i", "xep loai")):
                return 1.2
            if any(k in c for k in ("mÃ£ tá»•", "ma to")):
                return 1.0
            if any(k in c for k in ("chá»‰ tiÃªu", "Ä‘Æ¡n vá»‹", "chi tiÃªu", "chÆ°Æ¡ng trÃ¬nh", "ten")):
                return 3.0
            if any(k in c for k in ("tá»· lá»‡", "tl ", "%")):
                return 0.8
            if any(k in c for k in ("cÃ²n", "con ")):
                return 1.0
            return 1.2

        ratios = [_col_ratio(c) for c in cols_list]
        total_ratio = sum(ratios)
        col_widths = [usable_w * r / total_ratio for r in ratios]
    else:
        col_widths = [usable_w]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Style báº£ng
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), fb),
        ("FONTSIZE", (0, 0), (-1, 0), header_font_size),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        # Border toÃ n báº£ng
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("BOX", (0, 0), (-1, -1), 1, VBSP_GREEN),
    ]
    # Xen káº½ mÃ u dÃ²ng
    for r in range(1, len(table_data)):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))

    # Style dÃ²ng tá»•ng cá»™ng (dÃ²ng cuá»‘i)
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
        if c not in ("stt", "chá»‰ tiÃªu", "Ä‘Æ¡n vá»‹", "chi tiÃªu", "chÆ°Æ¡ng trÃ¬nh"):
            tbl.setStyle(TableStyle([
                ("ALIGN", (ci, 1), (ci, -1), "RIGHT")
            ]))
    story.append(tbl)

    # â”€â”€ 3. Pháº§n chá»¯ kÃ½ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        f"Äá»“ng Nai, ngÃ y {datetime.now().strftime('%d')} "
        f"thÃ¡ng {datetime.now().strftime('%m')} "
        f"nÄƒm {datetime.now().strftime('%Y')}",
        ParagraphStyle("date_sign", fontName=fn, fontSize=10,
                       alignment=TA_RIGHT, spaceAfter=6)
    ))

    ky_data = [[
        Paragraph("NGÆ¯á»œI Láº¬P BIá»‚U", ParagraphStyle("ky", fontName=fb, fontSize=10, alignment=TA_CENTER)),
        Paragraph("KIá»‚M SOÃT", ParagraphStyle("ky", fontName=fb, fontSize=10, alignment=TA_CENTER)),
        Paragraph("GIÃM Äá»C", ParagraphStyle("ky", fontName=fb, fontSize=10, alignment=TA_CENTER)),
    ], [
        Paragraph("<i>(KÃ½, ghi rÃµ há» tÃªn)</i>", ParagraphStyle("ky2", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("<i>(KÃ½, ghi rÃµ há» tÃªn)</i>", ParagraphStyle("ky2", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("<i>(KÃ½, ghi rÃµ há» tÃªn)</i>", ParagraphStyle("ky2", fontName=fn, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)),
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

    # â”€â”€ 4. Header/Footer má»—i trang (sá»‘ trang) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    Xuáº¥t má»™t báº£ng DataFrame ra PDF (wrapper gá»i `xuat_pdf`).
    GhÃ©p phá»¥ Ä‘á» vÃ o tiÃªu Ä‘á» khi cÃ³ `tieu_de_phu`.
    """
    if tieu_de_phu:
        tieu_de_day_du = f"{tieu_de} â€” {tieu_de_phu}"
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
    Render nÃºt 'Xuáº¥t PDF' + download_button inline trong Streamlit tab.
    DÃ¹ng session_state Ä‘á»ƒ trÃ¡nh lá»—i data=None khi nhiá»u instance cÃ¹ng render.
    Gá»i: nut_xuat_pdf(export_df, "BÃ¡o cÃ¡o dÆ° ná»£", username,
                      cols_tien=[COT_TONG_DU_NO, COT_DU_NO_QH])
    """
    ss_key      = f"_pdf_bytes_{key}"
    ss_file_key = f"_pdf_file_{key}"

    if st.button("ðŸ“„ Xuáº¥t PDF", key=key, type="primary"):
        try:
            with st.spinner("Äang táº¡o PDF..."):
                pdf_bytes = xuat_pdf(df, tieu_de, username, cols_tien, prefix_file=prefix_file)
            st.session_state[ss_key]      = pdf_bytes
            st.session_state[ss_file_key] = f"{prefix_file}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf"
        except Exception as e:
            st.session_state[ss_key] = None
            st.error(f"âŒ Lá»—i táº¡o PDF: {e}")

    pdf_data = st.session_state.get(ss_key)
    if pdf_data is not None:
        st.download_button(
            label="â¬‡ Táº£i file PDF",
            data=pdf_data,
            file_name=st.session_state.get(ss_file_key, f"{prefix_file}.pdf"),
            mime="application/pdf",
            key=f"{key}_dl",
        )
