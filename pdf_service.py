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

try:
    import kaleido
    _KALEIDO_READY = True
except ImportError:
    _KALEIDO_READY = False

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
        Path("assets/timesi.ttf"),
        Path("C:/Windows/Fonts/times.ttf"),
        Path("C:/Windows/Fonts/timesbd.ttf"),
        Path("C:/Windows/Fonts/timesi.ttf"),
    ]
    regular = next((p for p in [candidates[0], candidates[3]] if p.exists()), None)
    bold = next((p for p in [candidates[1], candidates[4]] if p.exists()), None)
    italic = next((p for p in [candidates[2], candidates[5]] if p.exists()), None)

    if regular:
        pdfmetrics.registerFont(TTFont("TNR", str(regular)))
    if bold:
        pdfmetrics.registerFont(TTFont("TNR-Bold", str(bold)))
    if italic:
        pdfmetrics.registerFont(TTFont("TNR-Italic", str(italic)))

    # Fallback nếu không có Times: dùng Helvetica (ASCII only, báo lỗi)
    if not regular:
        warnings.warn("Không tìm thấy times.ttf — tiếng Việt có thể bị lỗi font.")

    _FONT_REGISTERED = True


FONT_NORMAL = "TNR"       # dùng sau khi _dang_ky_font() đã chạy
FONT_BOLD = "TNR-Bold"
FONT_ITALIC = "TNR-Italic"
FONT_FALLBACK = "Helvetica"  # khi font chưa đăng ký được

# ── Lề chuẩn NĐ30/2020/NĐ-CP (Điều 5 & Phụ lục I) ──────────────────────────
_LEFT_MARGIN  = 3.0 * cm if _REPORTLAB_READY else 30   # 30mm — đóng gáy
_RIGHT_MARGIN = 1.5 * cm if _REPORTLAB_READY else 15   # 15mm
_TOP_MARGIN   = 2.0 * cm if _REPORTLAB_READY else 20   # 20mm
_BOT_MARGIN   = 2.0 * cm if _REPORTLAB_READY else 20   # 20mm

def _nd30_header(usable_w: float, fn: str, fb: str, fi: str) -> list:
    """
    Header văn bản chuẩn NĐ30/2020:
    Cột trái (40%): Tên cơ quan + Số văn bản
    Cột phải (60%): Quốc hiệu + Địa danh ngày tháng
    """
    from reportlab.lib.enums import TA_CENTER
    ngay = datetime.now()
    ngay_str = f"Đồng Nai, ngày {ngay.day} tháng {ngay.month} năm {ngay.year}"

    w_l = usable_w * 0.40
    w_r = usable_w * 0.60

    st_coq  = ParagraphStyle("nd30_coq",  fontName=fb, fontSize=11,
                              alignment=TA_CENTER, leading=16)
    st_sovb = ParagraphStyle("nd30_sovb", fontName=fn, fontSize=11,
                              alignment=TA_CENTER, leading=14)
    st_qh   = ParagraphStyle("nd30_qh",   fontName=fb, fontSize=11,
                              alignment=TA_CENTER, leading=15)
    st_td   = ParagraphStyle("nd30_td",   fontName=fb, fontSize=13,
                              alignment=TA_CENTER, leading=16)
    st_ngay = ParagraphStyle("nd30_ngay", fontName=fi, fontSize=11,
                              alignment=TA_CENTER, leading=14, spaceAfter=2)

    tbl_l = Table([
        [Paragraph("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI", st_coq)],
        [Paragraph("CHI NHÁNH TỈNH ĐỒNG NAI", st_coq)],
        [HRFlowable(width=w_l * 0.55, thickness=1, color=colors.black, spaceAfter=2)],
        [Paragraph("Số: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;/BC-SCM", st_sovb)],
    ], colWidths=[w_l])
    tbl_l.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))

    tbl_r = Table([
        [Paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", st_qh)],
        [Paragraph("Độc lập - Tự do - Hạnh phúc", st_td)],
        [HRFlowable(width=w_r * 0.50, thickness=1, color=colors.black, spaceAfter=2)],
        [Paragraph(ngay_str, st_ngay)],
    ], colWidths=[w_r])
    tbl_r.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))

    outer = Table([[tbl_l, tbl_r]], colWidths=[w_l, w_r])
    outer.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    return [outer, Spacer(1, 0.3 * cm)]


def _nd30_chu_ky(usable_w: float, fn: str, fb: str, fi: str,
                 noi_nhan: list[str] | None = None) -> list:
    """
    Phần ký chuẩn NĐ30: Nơi nhận (trái 40%) + Giám đốc (phải 60%).
    """
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    noi_nhan = noi_nhan or [
        "- Giám đốc Chi nhánh;",
        "- Phòng KH-NV;",
        "- Lưu: VT.",
    ]
    st_nn_title = ParagraphStyle("nn_title", fontName=fb,  fontSize=11,
                                  alignment=TA_LEFT,   leading=15)
    st_nn_item  = ParagraphStyle("nn_item",  fontName=fi,  fontSize=10,
                                  alignment=TA_LEFT,   leading=14)
    st_ky_title = ParagraphStyle("ky_title", fontName=fb,  fontSize=12,
                                  alignment=TA_CENTER, leading=16)
    st_ky_sub   = ParagraphStyle("ky_sub",   fontName=fi,  fontSize=10,
                                  alignment=TA_CENTER, leading=13)

    nn_cells = [[Paragraph("<b>Nơi nhận:</b>", st_nn_title)]]
    for item in noi_nhan:
        nn_cells.append([Paragraph(item, st_nn_item)])

    ky_cells = [
        [Paragraph("GIÁM ĐỐC", st_ky_title)],
        [Paragraph("<i>(Ký, đóng dấu)</i>", st_ky_sub)],
        [Spacer(1, 1.8 * cm)],
    ]

    w_l = usable_w * 0.40
    w_r = usable_w * 0.60

    tbl_nn = Table(nn_cells, colWidths=[w_l])
    tbl_nn.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    tbl_ky = Table(ky_cells, colWidths=[w_r])
    tbl_ky.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    outer = Table([[tbl_nn, tbl_ky]], colWidths=[w_l, w_r])
    outer.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    return [outer]


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


def kiem_tra_pdf_dependency() -> dict:
    """
    Kiểm tra trạng thái các thư viện cần cho PDF.
    Trả về dict: { "reportlab": bool, "kaleido": bool, "font_ok": bool, "messages": list[str] }
    Dùng để hiển thị banner hướng dẫn trong UI.
    """
    msgs = []
    if not _REPORTLAB_READY:
        msgs.append("Thiếu **reportlab** → chạy: `pip install reportlab`")
    font_file = next((p for p in [Path("assets/times.ttf"), Path("C:/Windows/Fonts/times.ttf")] if p.exists()), None)
    font_ok = font_file is not None
    if not font_ok:
        msgs.append("⚠️ Không tìm thấy font **Times New Roman** — tiếng Việt trong PDF có thể bị lỗi. Cần file `times.ttf` trong thư mục `assets/`")
    if not _KALEIDO_READY:
        msgs.append("Thiếu **kaleido** (nhúng biểu đồ vào PDF) → chạy: `pip install kaleido`")
    return {
        "reportlab": _REPORTLAB_READY,
        "kaleido": _KALEIDO_READY,
        "font": font_ok,
        "messages": msgs,
        "ready": _REPORTLAB_READY and font_ok,
    }


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
    use_landscape = len(df.columns) >= 8 or prefix_file == "TQPGD"
    page_size = landscape(A4) if use_landscape else A4

    # Lề chuẩn NĐ30 — landscape dùng lề đối xứng hơn
    if use_landscape:
        l_margin, r_margin = 2.0 * cm, 1.5 * cm
    else:
        l_margin, r_margin = _LEFT_MARGIN, _RIGHT_MARGIN
    t_margin, b_margin = _TOP_MARGIN, _BOT_MARGIN

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=l_margin, rightMargin=r_margin,
        topMargin=t_margin,  bottomMargin=b_margin,
        title=tieu_de,
        author="VBSP-SCM",
    )

    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD   if _FONT_REGISTERED else FONT_FALLBACK
    fi = FONT_ITALIC if _FONT_REGISTERED else FONT_FALLBACK

    story = []
    usable_w = page_size[0] - l_margin - r_margin

    # ── 1. Header chuẩn NĐ30 ───────────────────────────────────────────
    story.extend(_nd30_header(usable_w, fn, fb, fi))
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

    # ── 3. Phần chữ ký chuẩn NĐ30 ────────────────────────────────────
    story.append(Spacer(1, 1.0 * cm))
    story.extend(_nd30_chu_ky(usable_w, fn, fb, fi))

    # ── 4. Footer số trang mỗi trang ──────────────────────────────────
    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn if _FONT_REGISTERED else FONT_FALLBACK, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            page_size[0] - r_margin,
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
    fb = FONT_BOLD   if _FONT_REGISTERED else FONT_FALLBACK
    fi = FONT_ITALIC if _FONT_REGISTERED else FONT_FALLBACK

    buf = BytesIO()
    page_size = A4
    usable_w = page_size[0] - _LEFT_MARGIN - _RIGHT_MARGIN

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=_LEFT_MARGIN, rightMargin=_RIGHT_MARGIN,
        topMargin=_TOP_MARGIN,   bottomMargin=_BOT_MARGIN,
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

    # ── Report Header chuẩn NĐ30 ────────────────────────────────────────────
    story.extend(_nd30_header(usable_w, fn, fb, fi))
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

    # ── Chữ ký chuẩn NĐ30 ────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0 * cm))
    story.extend(_nd30_chu_ky(usable_w, fn, fb, fi))

    # ── Số trang footer mỗi trang ────────────────────────────────────────────
    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn if _FONT_REGISTERED else FONT_FALLBACK, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            page_size[0] - _RIGHT_MARGIN, 0.7 * cm,
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

    if st.button("📄 Xuất PDF", key=key, type="primary"):
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


# ═══════════════════════════════════════════════════════════════════════════════
# TÍNH NĂNG NÂNG CAO TỪ VSPPRO — KPI Cards + Chart embedding
# ═══════════════════════════════════════════════════════════════════════════════

def _build_kpi_cards(
    story: list,
    kpi_items: list[tuple[str, str, str]],
    usable_w: float,
    fn: str,
    fb: str,
) -> None:
    """
    Tạo grid KPI cards với viền trái màu sắc (giống VSPPRO export-pdf.ts).
    
    kpi_items: list of (label, value, accent_or_note)
        - Nếu value bắt đầu bằng '⚠️' hoặc '🔴' → accent = True (viền đỏ)
        - accent_or_note == "accent" → viền đỏ, ngược lại là note/text phụ
    """
    if not kpi_items:
        return

    CARD_W = (usable_w - 3 * 6) / 4  # 4 cột, gap 6pt

    rows = []
    for i in range(0, len(kpi_items), 4):
        batch = kpi_items[i:i + 4]
        row_cells = []
        for label, value, accent in batch:
            is_accent = (
                accent == "accent"
                or str(value).startswith("⚠️")
                or str(value).startswith("🔴")
            )
            border_color = "#e11d48" if is_accent else "#0f766e"
            val_color = "#be123c" if is_accent else "#0f172a"

            card = Table([
                [Paragraph(
                    f"<font size='8' color='#64748b'>{label.upper()}</font>",
                    ParagraphStyle("kpi_lbl", fontName=fn, fontSize=8, leading=10)
                )],
                [Paragraph(
                    f"<font size='11' color='{val_color}'><b>{value}</b></font>",
                    ParagraphStyle("kpi_val", fontName=fb, fontSize=11, leading=14)
                )],
            ], colWidths=[CARD_W - 16])

            card.setStyle(TableStyle([
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ]))

            # Viền trái màu
            card.setStyle(TableStyle([
                ("LINEBEFORE", (0, 0), (0, -1), 4, colors.HexColor(border_color)),
            ]))

            outer = Table([[card]], colWidths=[CARD_W])
            outer.setStyle(TableStyle([
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ]))
            row_cells.append(outer)

        # Đệm thêm ô trống nếu < 4
        while len(row_cells) < 4:
            row_cells.append(Table([[""]], colWidths=[CARD_W]))

        row_tbl = Table([row_cells], colWidths=[CARD_W] * 4)
        row_tbl.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        rows.append(row_tbl)

    kpi_container = Table([[r] for r in rows], colWidths=[usable_w])
    kpi_container.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    story.append(Spacer(1, 4))
    story.append(kpi_container)
    story.append(Spacer(1, 4))


def _chart_to_image(fig) -> bytes | None:
    """
    Chuyển Plotly figure thành ảnh PNG bytes để nhúng vào PDF.
    Yêu cầu: pip install kaleido
    Trả về None nếu không có kaleido.
    """
    try:
        return fig.to_image(format="png", width=800, height=400, scale=2)
    except Exception:
        return None


def xuat_pdf_bao_cao(
    df: pd.DataFrame,
    tieu_de: str,
    nguoi_xuat: str,
    *,
    kpi_items: list[tuple[str, str, str]] | None = None,
    charts: list[object] | None = None,
    cols_tien: list[str] | None = None,
    them_dong_tong: bool = True,
    tieu_de_phu: str = "",
) -> bytes:
    """
    Xuất PDF báo cáo đầy đủ với 3 phần giống VSPPRO export-pdf.ts:
      1. Header (logo NHCSXH + tiêu đề)
      2. KPI Cards (grid 4 cột với viền trái màu)
      3. Biểu đồ (Plotly → PNG)
      4. Bảng chi tiết (format số tiền, tổng cộng)

    Tham số:
        df          : DataFrame dữ liệu
        tieu_de     : Tiêu đề báo cáo
        nguoi_xuat  : Tên người xuất
        kpi_items   : List (label, value, accent_or_note) — giống VSPPRO kpiItems()
        charts      : List Plotly Figure để nhúng vào PDF
        cols_tien   : Danh sách cột tiền (format số, tính tổng)
        them_dong_tong: Thêm dòng tổng cộng
        tieu_de_phu : Phụ đề
    """
    if not _REPORTLAB_READY:
        raise ImportError("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
    _dang_ky_font()
    from utils import fmt_so

    cols_tien = cols_tien or []

    if df is None or df.empty:
        raise ValueError("Không có dữ liệu để xuất PDF.")

    MAX_ROWS_PDF = 2000
    if len(df) > MAX_ROWS_PDF:
        df = df.head(MAX_ROWS_PDF)

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
    use_landscape = len(df.columns) >= 8
    page_size = landscape(A4) if use_landscape else A4

    if use_landscape:
        l_margin, r_margin = 2.0 * cm, 1.5 * cm
    else:
        l_margin, r_margin = _LEFT_MARGIN, _RIGHT_MARGIN
    t_margin, b_margin = _TOP_MARGIN, _BOT_MARGIN

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=l_margin, rightMargin=r_margin,
        topMargin=t_margin, bottomMargin=b_margin,
        title=tieu_de, author="VBSP-SCM",
    )

    fn = FONT_NORMAL if _FONT_REGISTERED else FONT_FALLBACK
    fb = FONT_BOLD   if _FONT_REGISTERED else FONT_FALLBACK
    fi = FONT_ITALIC if _FONT_REGISTERED else FONT_FALLBACK

    story = []
    usable_w = page_size[0] - l_margin - r_margin
    ngay_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ── 1. Header ───────────────────────────────────────────────────────────
    story.extend(_nd30_header(usable_w, fn, fb, fi))
    story.append(HRFlowable(width="100%", thickness=1.5, color=VBSP_GREEN, spaceAfter=6))
    title_style = ParagraphStyle(
        "title", fontName=fb, fontSize=14, alignment=TA_CENTER,
        spaceAfter=4, textColor=colors.HexColor("#003D7A"),
    )
    sub_style = ParagraphStyle(
        "sub", fontName=fn, fontSize=9, alignment=TA_CENTER,
        spaceAfter=8, textColor=colors.grey,
    )
    story.append(Paragraph(tieu_de.upper(), title_style))
    story.append(Paragraph(
        f"Ngày xuất: {ngay_str}  |  Người xuất: {nguoi_xuat}",
        sub_style,
    ))
    if tieu_de_phu:
        story.append(Paragraph(tieu_de_phu, sub_style))

    # ── 2. KPI Cards ────────────────────────────────────────────────────────
    if kpi_items:
        _build_kpi_cards(story, kpi_items, usable_w, fn, fb)
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=8))

    # ── 3. Biểu đồ (Plotly → PNG) ───────────────────────────────────────────
    if charts:
        story.append(Paragraph(
            "BIỂU ĐỒ PHÂN TÍCH",
            ParagraphStyle("chart_title", fontName=fb, fontSize=11, alignment=TA_CENTER,
                           textColor=VBSP_GREEN, spaceAfter=6)
        ))
        for fig in charts:
            img_bytes = _chart_to_image(fig)
            if img_bytes:
                try:
                    img = RLImage(BytesIO(img_bytes), width=usable_w, height=usable_w * 0.45)
                    story.append(img)
                    story.append(Spacer(1, 6))
                except Exception:
                    story.append(Paragraph(
                        "[Không thể hiển thị biểu đồ]",
                        ParagraphStyle("chart_err", fontName=fi, fontSize=9, textColor=colors.grey, alignment=TA_CENTER)
                    ))
            else:
                story.append(Paragraph(
                    "⚠️ Cần cài kaleido để hiển thị biểu đồ: pip install kaleido",
                    ParagraphStyle("chart_miss", fontName=fi, fontSize=9, textColor=colors.grey, alignment=TA_CENTER)
                ))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=8))

    # ── 4. Bảng chi tiết ────────────────────────────────────────────────────
    n_cols = len(df.columns)

    if n_cols <= 5:
        font_size = 12
    elif n_cols <= 8:
        font_size = 10
    elif n_cols <= 12:
        font_size = 9
    elif n_cols <= 16:
        font_size = 8
    else:
        font_size = 7

    h_font = min(font_size + 2, 12)
    header_cells = [
        Paragraph(
            str(c).replace("_", " ").replace("(triệu đồng)", "\n(triệu đồng)").replace(" %", "\n%"),
            ParagraphStyle("th", fontName=fb, fontSize=h_font,
                           alignment=TA_CENTER, textColor=colors.white, leading=h_font + 2)
        )
        for c in df.columns
    ]
    table_data = [header_cells]

    style_td   = ParagraphStyle("td",   fontName=fn, fontSize=font_size, wordWrap="CJK")
    style_td_r = ParagraphStyle("td_r", fontName=fn, fontSize=font_size, alignment=TA_RIGHT)
    cols_list  = list(df.columns)
    set_tien   = set(cols_tien)

    arr = df.fillna("").values.tolist()
    for row_vals in arr:
        cells = []
        for ci, val in enumerate(row_vals):
            col = cols_list[ci]
            if col in set_tien and val != "":
                try:
                    if isinstance(val, bool):
                        raise ValueError
                    num = float(val) if isinstance(val, (int, float)) else float(str(val).strip().replace(".", "").replace(",", "."))
                    trieu = num / 1_000_000
                    txt = f"{trieu:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
                trieu = val / 1_000_000
                txt = f"{trieu:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
                tong_cells.append(Paragraph(f"<b>{txt}</b>",
                    ParagraphStyle("tong_r", fontName=fb, fontSize=font_size, alignment=TA_RIGHT)))
            elif val == "TỔNG CỘNG":
                tong_cells.append(Paragraph("<b>TỔNG CỘNG</b>",
                    ParagraphStyle("tong_lbl", fontName=fb, fontSize=font_size, alignment=TA_CENTER)))
            else:
                tong_cells.append(Paragraph(str(val) if val else "",
                    ParagraphStyle("td", fontName=fn, fontSize=font_size)))
        table_data.append(tong_cells)

    if n_cols > 0:
        col_max_chars = []
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
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), fb),
        ("FONTSIZE",   (0, 0), (-1, 0), h_font),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("BOX",  (0, 0), (-1, -1), 1, VBSP_GREEN),
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
    story.append(tbl)

    # ── 5. Chữ ký NĐ30 ──────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0 * cm))
    story.extend(_nd30_chu_ky(usable_w, fn, fb, fi))

    # ── 6. Footer số trang ──────────────────────────────────────────────────
    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(fn if _FONT_REGISTERED else FONT_FALLBACK, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            page_size[0] - r_margin, 0.8 * cm,
            f"Trang {_doc.page}  |  VBSP-SCM  |  {ngay_str}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.getvalue()


def nut_xuat_pdf_bao_cao(
    df: pd.DataFrame,
    tieu_de: str,
    username: str,
    *,
    kpi_items: list[tuple[str, str, str]] | None = None,
    charts: list | None = None,
    cols_tien: list[str] | None = None,
    tieu_de_phu: str = "",
    prefix_file: str = "BC",
    key: str = "btn_pdf_full",
) -> None:
    """
    Render nút '📄 Báo cáo PDF đầy đủ' trong Streamlit — dùng xuat_pdf_bao_cao().
    """
    ss_key = f"_pdf_full_bytes_{key}"

    if st.button("📄 Báo cáo PDF đầy đủ", key=key, type="primary"):
        try:
            with st.spinner("⏳ Đang tạo PDF với biểu đồ..."):
                pdf_bytes = xuat_pdf_bao_cao(
                    df=df, tieu_de=tieu_de, nguoi_xuat=username,
                    kpi_items=kpi_items, charts=charts,
                    cols_tien=cols_tien, tieu_de_phu=tieu_de_phu,
                )
            st.session_state[ss_key] = {
                "data": pdf_bytes,
                "filename": f"{prefix_file}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
            }
        except Exception as e:
            import traceback
            st.session_state[ss_key] = None
            st.error(f"❌ Lỗi tạo PDF: {e}")
            st.code(traceback.format_exc())

    if ss_key in st.session_state and st.session_state[ss_key]:
        pdf_info = st.session_state[ss_key]
        st.download_button(
            label="⬇ Tải PDF đã tạo",
            data=pdf_info["data"],
            file_name=pdf_info["filename"],
            mime="application/pdf",
            key=f"{key}_dl",
            use_container_width=True,
        )


def render_huong_dan() -> None:
    """
    Hướng dẫn cài đặt & cấu hình hệ thống — dùng chung cho CN và PGD.
    """
    _pdf_dep = kiem_tra_pdf_dependency()

    st.subheader("Hướng dẫn cài đặt & Cấu hình")
    st.caption("Áp dụng cho cả phân hệ Chi nhánh (CN) và Phòng Giao dịch (PGD)")

    with st.expander("1. Cài đặt môi trường Python", expanded=True):
        st.markdown("""
        **Yêu cầu:** Python 3.10 trở lên

        ```bash
        # Kiểm tra phiên bản Python
        python --version

        # Tạo môi trường ảo (khuyến nghị)
        python -m venv .venv

        # Kích hoạt môi trường ảo
        # Windows:
        .venv\\Scripts\\activate
        # Linux/Mac:
        source .venv/bin/activate
        ```
        """)

    with st.expander("2. Cài đặt thư viện", expanded=True):
        st.markdown("""
        ```bash
        pip install -r requirements.txt
        ```

        **Thư viện PDF** (cài riêng nếu cần xuất PDF):

        ```bash
        pip install reportlab kaleido
        ```
        """)
        if _pdf_dep["reportlab"]:
            st.success(" reportlab: đã cài")
        else:
            st.error(" reportlab: chưa cài")
        if _pdf_dep["kaleido"]:
            st.success(" kaleido: đã cài")
        else:
            st.warning(" kaleido: chưa cài (chỉ cần nếu muốn nhúng biểu đồ vào PDF)")

    with st.expander("3. Font chữ tiếng Việt cho PDF"):
        st.markdown("""
        Để xuất PDF có hỗ trợ tiếng Việt, cần file font **Times New Roman**:

        - **Cách 1 (tự động):** Hệ thống tự tìm trong `C:/Windows/Fonts/times.ttf`
        - **Cách 2 (thủ công):** Copy file `times.ttf` + `timesbd.ttf` vào thư mục `assets/` của dự án

        ```bash
        # Tạo thư mục assets nếu chưa có
        mkdir assets
        # Copy font từ Windows
        copy C:\\Windows\\Fonts\\times.ttf assets\\
        copy C:\\Windows\\Fonts\\timesbd.ttf assets\\
        ```
        """)
        if _pdf_dep["font"]:
            st.success(" Font Times New Roman: đã tìm thấy")
        else:
            st.warning(" Font Times New Roman: chưa tìm thấy — tiếng Việt trong PDF có thể bị lỗi")

    with st.expander("4. Cấu hình dữ liệu ban đầu"):
        st.markdown("""
        **Dành cho CN:**
        - File HSTD gốc đặt tại đường dẫn cấu hình trong `config.py` (biến `FILE_PATH`)
        - Hoặc upload qua giao diện: tab **Upload dữ liệu**

        **Dành cho PGD:**
        - Upload file HSTD qua giao diện: tab **Quản trị PGD → Upload HSTD**
        - Hệ thống tự động lưu vào thư mục `pgd_data/{slug}/`

        **Dữ liệu mẫu:**
        - File HSTD là file Excel (.xlsx) với các cột: Mã KH, Tên KH, Số KU, Tên CT, Dư nợ TH, Dư nợ QH, Tổng dư nợ, Ngày vay, Ngày ĐH,...
        - File NQ11 là file Excel phục vụ báo cáo NQ11
        """)

    with st.expander("5. Chạy ứng dụng"):
        st.markdown("""
        ```bash
        streamlit run app.py
        ```

        Ứng dụng sẽ mở tại: **http://localhost:8501**

        **Phân quyền mặc định:**
        - `executive` → Ban Giám đốc (dashboard vĩ mô)
        - `admin_cn` / `manager_cn` → Phòng KH-NV Chi nhánh
        - `admin_pgd` / `user_pgd` → Phòng Giao dịch
        """)

    with st.expander("6. Xử lý sự cố thường gặp"):
        st.markdown("""
        | Vấn đề | Nguyên nhân | Giải pháp |
        |--------|-------------|-----------|
        | `ModuleNotFoundError: No module named 'reportlab'` | Chưa cài reportlab | `pip install reportlab` |
        | `ModuleNotFoundError: No module named 'kaleido'` | Chưa cài kaleido | `pip install kaleido` |
        | PDF bị lỗi font, không dấu | Thiếu times.ttf | Copy font vào `assets/` |
        | `StreamlitApp: No data` | Chưa upload HSTD | Upload file HSTD qua tab Quản trị |
        | Lỗi `Permission denied` khi upload | Quyền thư mục | Chạy lại với quyền Admin |
        """)

    st.divider()
    st.caption(
        "Mọi thắc mắc vui lòng liên hệ Phòng KH-NV NHCSXH Chi nhánh Đồng Nai. "
        f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
