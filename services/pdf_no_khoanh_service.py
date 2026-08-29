"""PDF helpers cho QLNK - reportlab templates.

Tach tu tab_no_khoanh.py de giam kich thuoc file chinh.
"""
from io import BytesIO
from datetime import datetime
from pathlib import Path

from config import (
    COT_CMND,
    COT_DIA_CHI,
    COT_DU_NO_KHOANH,
    COT_DVUT,
    COT_NGAY_CAP_CMND,
    COT_NGAY_DH,
    COT_NGAY_HH_KHOANH,
    COT_NGAY_SINH,
    COT_NOI_CAP_CMND,
    COT_SDT,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_TO,
    COT_TEN_XA,
    LY_DO_KHOANH_LABEL,
    TEN_CHI_NHANH_HIEN_THI,
)

from utils import fmt_so

_fmt_dong = lambda x: fmt_so(float(x)) + " đồng" if x not in (None, "", float("nan")) else "0 đồng"

_REPORTLAB_READY = False
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable, Image as RLImage,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    _REPORTLAB_READY = True
except ImportError:
    pass

if _REPORTLAB_READY:
    _VBSP_GREEN = colors.HexColor("#2E7D32")
    _VBSP_GREEN_LIGHT = colors.HexColor("#E8F5E9")
    _ROW_ALT = colors.HexColor("#F5F5F5")
    _BORDER_COLOR = colors.HexColor("#BDBDBD")
    _HEADER_BG = colors.HexColor("#D9D9D9")
    _RED = colors.HexColor("#C62828")
else:
    _VBSP_GREEN = _VBSP_GREEN_LIGHT = _ROW_ALT = _BORDER_COLOR = _HEADER_BG = _RED = None

_FN = "TNR"
_FB = "TNR-Bold"

# ─── PDF helpers (QLNK theo CV 368) ──────────────────────────────────────────

_FONT_QLNK = False

def _dang_ky_font_qlnk():
    global _FONT_QLNK
    if _FONT_QLNK or not _REPORTLAB_READY:
        return
    candidates = [
        Path("C:/Windows/Fonts/times.ttf"),
        Path("C:/Windows/Fonts/timesbd.ttf"),
    ]
    regular = next((p for p in [candidates[0]] if p.exists()), None)
    bold = next((p for p in [candidates[1]] if p.exists()), None)
    if regular:
        pdfmetrics.registerFont(TTFont("TNR", str(regular)))
    if bold:
        pdfmetrics.registerFont(TTFont("TNR-Bold", str(bold)))
    _FONT_QLNK = True

if _REPORTLAB_READY:
    _VBSP_GREEN = colors.HexColor("#2E7D32")
    _VBSP_GREEN_LIGHT = colors.HexColor("#E8F5E9")
    _ROW_ALT = colors.HexColor("#F5F5F5")
    _BORDER_COLOR = colors.HexColor("#BDBDBD")
    _HEADER_BG = colors.HexColor("#D9D9D9")
    _RED = colors.HexColor("#C62828")
else:
    _VBSP_GREEN = _VBSP_GREEN_LIGHT = _ROW_ALT = _BORDER_COLOR = _HEADER_BG = _RED = None

_FN = "TNR"
_FB = "TNR-Bold"


def _tim_logo_qlnk() -> str | None:
    for p in [
        Path(__file__).parent.parent / "assets" / "logo.png",
        Path(__file__).parent.parent / "logo-vbsp.jpg",
        Path(__file__).parent.parent / "logo.png",
    ]:
        if p.exists():
            return str(p)
    return None


def _qlnk_add_months(dt_str: str, months: int) -> str:
    try:
        import calendar as _cal
        from datetime import date as _date
        parts = str(dt_str).strip().split("/")
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        m2 = m - 1 + int(months)
        y2 = y + m2 // 12
        m2 = m2 % 12 + 1
        d2 = min(d, _cal.monthrange(y2, m2)[1])
        return _date(y2, m2, d2).strftime("%d/%m/%Y")
    except Exception:
        return "............"


def _qlnk_fmt_k(val) -> str:
    try:
        return f"{int(round(float(val) / 1000)):,}"
    except (TypeError, ValueError):
        return "............"


def _qlnk_fmt_dong(val) -> str:
    try:
        return f"{int(round(float(val))):,}"
    except (TypeError, ValueError):
        return "............"


# ── Common PDF styles ──

def _style_bank_name() -> ParagraphStyle:
    return ParagraphStyle("BankName", fontName=_FB, fontSize=12,
                          alignment=TA_CENTER, leading=16)

def _style_bank_branch() -> ParagraphStyle:
    return ParagraphStyle("BranchName", fontName=_FN, fontSize=10,
                          alignment=TA_CENTER, leading=13, spaceAfter=2)

def _style_doc_title() -> ParagraphStyle:
    return ParagraphStyle("DocTitle", fontName=_FB, fontSize=15,
                          alignment=TA_CENTER, textColor=_VBSP_GREEN,
                          spaceBefore=4, spaceAfter=4, leading=18)

def _style_doc_sub() -> ParagraphStyle:
    return ParagraphStyle("DocSub", fontName=_FN, fontSize=10,
                          alignment=TA_CENTER, spaceAfter=6, leading=13)

def _style_body() -> ParagraphStyle:
    return ParagraphStyle("Body", fontName=_FN, fontSize=12,
                          alignment=TA_LEFT, leading=20, spaceAfter=2)

def _style_body_bold() -> ParagraphStyle:
    return ParagraphStyle("BodyBold", fontName=_FB, fontSize=12,
                          alignment=TA_LEFT, leading=20, spaceAfter=2)

def _style_italic() -> ParagraphStyle:
    return ParagraphStyle("Italic", fontName=_FN, fontSize=10,
                          alignment=TA_CENTER, leading=13)

def _style_table_header(font_size=9) -> ParagraphStyle:
    return ParagraphStyle("TH", fontName=_FB, fontSize=font_size,
                          alignment=TA_CENTER, textColor=colors.white, leading=12)

def _style_table_cell(font_size=9, align=TA_CENTER) -> ParagraphStyle:
    return ParagraphStyle("TC", fontName=_FN, fontSize=font_size,
                          alignment=align, leading=12, wordWrap="CJK")

def _style_table_cell_left(font_size=9) -> ParagraphStyle:
    return _style_table_cell(font_size, TA_LEFT)

def _style_sig_title() -> ParagraphStyle:
    return ParagraphStyle("SigTitle", fontName=_FB, fontSize=11,
                          alignment=TA_CENTER, leading=14)

def _style_sig_sub() -> ParagraphStyle:
    return ParagraphStyle("SigSub", fontName=_FN, fontSize=9,
                          alignment=TA_CENTER, leading=12, textColor=colors.grey)

def _style_date_right() -> ParagraphStyle:
    return ParagraphStyle("DateRight", fontName=_FN, fontSize=11,
                          alignment=TA_RIGHT, leading=14, spaceAfter=4)

def _style_meta_label() -> ParagraphStyle:
    return ParagraphStyle("MetaLabel", fontName=_FB, fontSize=10,
                          alignment=TA_LEFT, leading=13, spaceAfter=2)


# ── PDF layout helpers ──

def _ve_header_pdf(elements, usable_w: float, tieu_de: str,
                   don_vi_tren: str = "", don_vi_duoi: str = "",
                   co_quoc_hieu: bool = True):
    logo_path = _tim_logo_qlnk()
    bank_html = (
        "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM<br/>"
        f"<font size='10'>{TEN_CHI_NHANH_HIEN_THI}</font>"
    )

    left_html = ""
    if don_vi_tren:
        left_html += f"<b>{don_vi_tren}</b>"
    if don_vi_duoi:
        left_html += f"<br/>{don_vi_duoi}"
    left_html += "<br/>─────────────────────" if left_html else ""

    right_html = ""
    if co_quoc_hieu:
        right_html = (
            "<b>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</b><br/>"
            "<i>Độc lập - Tự do - Hạnh phúc</i><br/>"
            "─────────────────────"
        )

    if logo_path and left_html and right_html:
        try:
            logo = RLImage(logo_path, width=2.0 * cm, height=2.0 * cm)
            mid_w = usable_w - 2.4 * cm
            left_w = mid_w * 0.55
            right_w = mid_w * 0.45
            inner = Table(
                [[Paragraph(left_html, _style_body()),
                  Paragraph(right_html, _style_body())]],
                colWidths=[left_w, right_w],
            )
            inner.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            header_tbl = Table(
                [[logo, inner]],
                colWidths=[2.4 * cm, mid_w],
            )
            header_tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            elements.append(header_tbl)
        except Exception:
            elements.append(Paragraph(bank_html, _style_bank_name()))
            if left_html:
                elements.append(Paragraph(left_html, _style_bank_branch()))
    else:
        elements.append(Paragraph(bank_html, _style_bank_name()))
        if left_html:
            elements.append(Paragraph(left_html, _style_bank_branch()))

    elements.append(HRFlowable(width="100%", thickness=1.5,
                               color=_VBSP_GREEN, spaceAfter=4))
    elements.append(Paragraph(tieu_de.upper(), _style_doc_title()))
    elements.append(Spacer(1, 4))


def _ve_footer_pdf(elements, usable_w: float, signatures: list[str],
                   ngay_str: str = None):
    if ngay_str:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(ngay_str, _style_date_right()))
    elements.append(Spacer(1, 8))

    n = len(signatures)
    cols_w = [usable_w / n] * n

    sig_data = []
    sig_data.append([Paragraph(s, _style_sig_title()) for s in signatures])
    sig_data.append([Paragraph("<i>(Ký, ghi rõ họ tên)</i>", _style_sig_sub())
                     for _ in signatures])
    sig_data.append([Paragraph("<br/><br/><br/>", _style_body())
                     for _ in signatures])

    sig_tbl = Table(sig_data, colWidths=cols_w)
    sig_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(sig_tbl)


def _dong_ten_nd(nd: str = "") -> str:
    try:
        from datetime import date
        today = date.today()
        return f"Đồng Nai, ngày {today.day} tháng {today.month} năm {today.year}"
    except Exception:
        return nd or "Đồng Nai, ngày ... tháng ... năm ..."


# ═══════════════════════════════════════════════════════════════════════════════
#  5 hàm xuất PDF — thay thế _tao_word_* cũ
# ═══════════════════════════════════════════════════════════════════════════════

def _xuat_pdf_mau_kh(ke_hoach: dict, ds_mon_vay: list,
                     can_bo_kt: str = "", noi_dung: str = "") -> bytes:
    _dang_ky_font_qlnk()
    ten_pgd    = ke_hoach.get("ten_pgd")       or "............"
    ten_xa     = ke_hoach.get("ten_xa")        or "............"
    ngay_kt    = ke_hoach.get("ngay_kiem_tra") or "............"
    thanh_phan = ke_hoach.get("thanh_phan")    or []

    buf = BytesIO()
    margin = 2.0 * cm
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=2 * cm)
    usable_w = A4[0] - 2 * margin
    elements = []

    _ve_header_pdf(elements, usable_w,
                   tieu_de="KẾ HOẠCH KIỂM TRA KHOANH NỢ",
                   don_vi_tren=f"PHÒNG GIAO DỊCH {ten_pgd.upper()}",
                   don_vi_duoi="TỔ TÍN DỤNG")
    elements.append(Paragraph("(Theo CV 368/NHCS-QLN ngày 17/01/2024)",
                              _style_italic()))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"<b>Kính gửi:</b> Giám đốc Phòng giao dịch {ten_pgd}",
        _style_body()))
    elements.append(Paragraph(
        "Căn cứ Công văn số 368/NHCS-QLN ngày 17/01/2024 của Ngân hàng Chính sách xã hội "
        "về việc hướng dẫn quản lý nợ khoanh;",
        _style_body()))
    elements.append(Paragraph(
        "Căn cứ kết quả rà soát các khoản nợ khoanh tại đơn vị;",
        _style_body()))
    elements.append(Spacer(1, 4))

    elements.append(Paragraph("<b>I. NỘI DUNG KIỂM TRA</b>", _style_body_bold()))
    elements.append(Paragraph(
        f"1. Thời gian kiểm tra: Ngày {ngay_kt} tại {ten_xa}, {ten_pgd}",
        _style_body()))
    elements.append(Paragraph("2. Thành phần đoàn kiểm tra:", _style_body()))
    for tp in (thanh_phan or [{"Họ và tên": "............", "Chức vụ/Đơn vị": "............"}]):
        ten = tp.get("Họ và tên") or tp.get("ten") or "............"
        chuc = tp.get("Chức vụ/Đơn vị") or tp.get("chuc_vu") or "............"
        elements.append(Paragraph(f"    - {ten}, {chuc}", _style_body()))
    elements.append(Paragraph("3. Đối tượng kiểm tra:", _style_body()))
    if noi_dung:
        elements.append(Paragraph(f"    {noi_dung}", _style_body()))

    headers = ["STT", "Khách hàng", "Tổ trưởng", "Chương trình vay",
               "Ngày BĐ khoanh", "Thời gian khoanh", "Lý do khoanh nợ"]
    ncols = len(headers)
    col_widths = [0.8 * cm, 3.8 * cm, 3.0 * cm, 3.0 * cm, 2.5 * cm, 2.2 * cm, 3.5 * cm]

    table_data = [[Paragraph(h, _style_table_header(9)) for h in headers]]
    for idx, mon in enumerate(ds_mon_vay or [], 1):
        ly_do_ma = mon.get("ly_do_khoanh", "")
        ly_do_hl = LY_DO_KHOANH_LABEL.get(ly_do_ma, ly_do_ma or "............")
        st_val = mon.get("so_thang_khoanh")
        vals = [
            str(idx),
            mon.get("ten_kh")              or "............",
            mon.get("ten_to_truong")       or "............",
            mon.get("ten_ct")              or "............",
            mon.get("ngay_bat_dau_khoanh") or "............",
            (f"{st_val} tháng" if st_val else "............"),
            ly_do_hl,
        ]
        table_data.append([Paragraph(v, _style_table_cell(9)) for v in vals])

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER_COLOR),
        ("BOX", (0, 0), (-1, -1), 1, _VBSP_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for r in range(1, len(table_data)):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), _ROW_ALT))

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)

    _ve_footer_pdf(elements, usable_w,
                   signatures=["Người lập kế hoạch", "Giám Đốc"],
                   ngay_str=_dong_ten_nd())

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_mau_01qlnk(ke_hoach: dict, ds_ket_qua: list,
                         ket_luan: str = "") -> bytes:
    _dang_ky_font_qlnk()
    ten_pgd    = ke_hoach.get("ten_pgd")       or "............"
    ten_xa     = ke_hoach.get("ten_xa")        or "............"
    ngay_kt    = ke_hoach.get("ngay_kiem_tra") or "............"
    thanh_phan = ke_hoach.get("thanh_phan")    or []

    buf = BytesIO()
    margin = 1.5 * cm
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=1.5 * cm)
    usable_w = landscape(A4)[0] - 2 * margin
    elements = []

    _ve_header_pdf(elements, usable_w,
                   tieu_de="PHIẾU KIỂM TRA NỢ KHOANH",
                   don_vi_tren="NGÂN HÀNG CHÍNH SÁCH XÃ HỘI TỈNH",
                   don_vi_duoi=f"PHÒNG GIAO DỊCH {ten_pgd.upper()}")
    elements.append(Paragraph(
        "<font size='8'><i>Mẫu số: 01/QLNK</i></font>",
        ParagraphStyle("MS", fontName=_FN, fontSize=8,
                       alignment=TA_RIGHT, leading=10)))
    elements.append(Paragraph("(Đơn vị tính: ngàn đồng)", _style_italic()))

    cb_list = [
        (tp.get("Họ và tên") or "............",
         tp.get("Chức vụ/Đơn vị") or "............")
        for tp in (thanh_phan or [{}])
    ]
    elements.append(Paragraph(
        "Tổ trưởng: ............    Tổ chức Chính trị - Xã hội: ............",
        _style_body()))
    for i, (ten, chuc) in enumerate(cb_list[:2]):
        prefix = "Họ và tên cán bộ kiểm tra: 1." if i == 0 else (
            "                                 2.")
        elements.append(Paragraph(
            f"{prefix} {ten}    Chức vụ: {chuc}", _style_body()))
    elements.append(Paragraph(
        f"Thời điểm kiểm tra: {ngay_kt}    Địa bàn kiểm tra: {ten_xa}",
        _style_body()))
    elements.append(Spacer(1, 6))

    N = 17
    col_w = [
        1.0 * cm, 2.8 * cm, 2.0 * cm,
        1.5 * cm, 1.5 * cm, 1.5 * cm, 1.8 * cm, 1.8 * cm,
        1.5 * cm, 1.5 * cm, 1.5 * cm,
        2.0 * cm, 2.0 * cm, 1.6 * cm,
        1.5 * cm, 1.5 * cm, 1.5 * cm,
    ]

    fs = 7
    th = _style_table_header(fs)
    tc = _style_table_cell(fs)

    row0 = [Paragraph("STT", th), Paragraph("Họ và tên", th),
            Paragraph("Mã món vay", th)]
    row0 += [Paragraph("PHẦN THEO DÕI TẠI NH", th)]
    row0 += [Paragraph("", th)] * 4
    row0 += [Paragraph("PHẦN KIỂM TRA THỰC TẾ TẠI KHÁCH HÀNG", th)]
    row0 += [Paragraph("", th)] * 8

    sub_h = [
        "Dư nợ gốc", "Dư nợ gốc khoanh", "Số tiền lãi còn nợ NH",
        "Ngày BĐ khoanh", "Ngày hết hạn khoanh",
        "Dư nợ gốc", "Dư gốc khoanh", "Số tiền lãi còn nợ NH",
        "Thực trạng DA", "Tình hình KH", "Khả năng TN",
        "KH cam kết TN", "Chênh lệch", "Ký xác nhận KH",
    ]

    header_data = [
        [row0[0], row0[1], row0[2]] + [row0[3]] * 5 + [row0[8]] * 9,
        [Paragraph("", th), Paragraph("", th), Paragraph("", th)]
        + [Paragraph(h, th) for h in sub_h],
    ]

    style_cmds = []
    for ci in range(N):
        style_cmds.append(("BACKGROUND", (ci, 0), (ci, 0), _HEADER_BG))
        style_cmds.append(("BACKGROUND", (ci, 1), (ci, 1), _HEADER_BG))
        style_cmds.append(("TEXTCOLOR", (ci, 0), (ci, 1), colors.black))
    style_cmds.append(("SPAN", (3, 0), (7, 0)))
    style_cmds.append(("SPAN", (8, 0), (16, 0)))
    style_cmds.append(("GRID", (0, 0), (-1, -1), 0.5, _BORDER_COLOR))
    style_cmds.append(("BOX", (0, 0), (-1, -1), 1, _VBSP_GREEN))
    style_cmds.append(("VALIGN", (0, 0), (-1, -1), "MIDDLE"))
    style_cmds.append(("TOPPADDING", (0, 0), (-1, -1), 2))
    style_cmds.append(("BOTTOMPADDING", (0, 0), (-1, -1), 2))

    for stt, r in enumerate(ds_ket_qua or [], 1):
        bdk = r.get("ngay_bat_dau_khoanh") or ""
        so_thang = r.get("so_thang_khoanh")
        ngay_hh = (_qlnk_add_months(bdk, int(so_thang))
                   if (bdk and so_thang) else "............")
        row = [Paragraph(v, tc) for v in [
            str(stt),
            r.get("ten_kh")               or "............",
            r.get("ma_mon_vay")           or "............",
            _qlnk_fmt_k(r.get("du_no_goc")),
            _qlnk_fmt_k(r.get("du_no_goc_khoanh")),
            _qlnk_fmt_k(r.get("so_tien_lai_con_no")),
            bdk                           or "............",
            ngay_hh,
            _qlnk_fmt_k(r.get("du_no_goc_thuc_te")),
            _qlnk_fmt_k(r.get("du_no_khoanh_thuc_te")),
            _qlnk_fmt_k(r.get("so_tien_lai_thuc_te")),
            r.get("thuc_trang_du_an")     or "............",
            r.get("tinh_hinh_khach_hang") or "............",
            r.get("kha_nang_tra_no")      or "............",
            r.get("cam_ket_tra_no")       or "............",
            _qlnk_fmt_k(r.get("chenh_lech")),
            "",
        ]]
        header_data.append(row)

    for r in range(2, len(header_data)):
        if r % 2 == 0:
            for ci in range(N):
                style_cmds.append(("BACKGROUND", (ci, r), (ci, r), _ROW_ALT))

    tbl = Table(header_data, colWidths=col_w, repeatRows=2)
    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"<b>Nhận xét:</b> Kiểm tra thực tế được ..... Khách hàng; "
        f"Số tiền ............",
        _style_body()))
    if ket_luan:
        elements.append(Paragraph(f"<b>Kết luận:</b> {ket_luan}", _style_body()))

    _ve_footer_pdf(elements, usable_w, signatures=[
        "ĐẠI DIỆN NHCSXH", "BQL TỔ TK&VV",
        "ĐẠI DIỆN CT-XH", "TRƯỞNG THÔN", "ĐẠI DIỆN UBND",
    ], ngay_str=_dong_ten_nd())

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_mau_02qlnk(row: dict,
                         so_tien_cam_ket: str = "",
                         thoi_han: str = "",
                         phuong_thuc: str = "") -> bytes:
    _dang_ky_font_qlnk()
    ten_kh  = row.get("ten_kh") or row.get(COT_TEN_KH) or "............"
    dia_chi = (
        row.get(COT_DIA_CHI)
        or row.get("dia_chi")
        or row.get(COT_TEN_XA)
        or row.get("ten_xa")
        or "............"
    )
    sdt = row.get(COT_SDT) or row.get("sdt") or row.get("so_dien_thoai") or "............"
    so_cccd = row.get(COT_CMND) or row.get("so_cmnd") or row.get("so_cccd") or "............"
    ngay_sinh_raw = row.get(COT_NGAY_SINH)
    try:
        ngay_sinh_dt = pd.to_datetime(ngay_sinh_raw, dayfirst=True, errors="coerce")
        nam_sinh = str(int(ngay_sinh_dt.year)) if pd.notna(ngay_sinh_dt) else "............"
    except Exception:
        nam_sinh = "............"
    ngay_cap_cmnd = row.get(COT_NGAY_CAP_CMND) or "....../....../......"
    noi_cap_cmnd  = row.get(COT_NOI_CAP_CMND)  or "...................."
    ten_to  = row.get(COT_TEN_TO) or row.get("ten_to_tkv") or row.get("ten_to") or "............"
    dvut = row.get(COT_DVUT) or row.get("dvut") or "............"
    ten_pgd = row.get("ten_pgd") or row.get(COT_TEN_PGD) or "............"
    so_ku   = row.get("ma_mon_vay") or row.get(COT_SO_KU) or "............"
    ten_ct = row.get(COT_TEN_CT) or "......................................................"
    du_goc  = row.get("du_no_goc_khoanh") or row.get(COT_DU_NO_KHOANH) or 0
    lai     = row.get("so_tien_lai_con_no") or 0
    try:
        du_goc_f = float(du_goc)
        lai_f    = float(lai)
        tong_no  = du_goc_f + lai_f
    except (TypeError, ValueError):
        du_goc_f = lai_f = tong_no = 0

    buf = BytesIO()
    margin = 2.5 * cm
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=margin, rightMargin=margin,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    usable_w = A4[0] - 2 * margin
    elements = []

    s_right_8 = ParagraphStyle("r8", fontName=_FN, fontSize=9, leading=12, alignment=TA_RIGHT)
    s_center = ParagraphStyle("c", fontName=_FN, fontSize=11, leading=14, alignment=TA_CENTER)
    s_center_b = ParagraphStyle("cb", fontName=_FB, fontSize=11, leading=14, alignment=TA_CENTER)
    s_title = ParagraphStyle("t", fontName=_FB, fontSize=13, leading=18, alignment=TA_CENTER, spaceAfter=10)

    elements.append(Paragraph("<i>Mẫu số 02/QLNK</i>", s_right_8))
    elements.append(Paragraph(
        "<b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b><br/>"
        "<i>Độc lập - Tự do - Hạnh phúc</i><br/>"
        "────────────────────────────",
        s_center_b,
    ))
    elements.append(Paragraph("..............., ngày ..... tháng ..... năm 20.....", s_right_8))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("CAM KẾT TRẢ NỢ", s_title))

    elements.append(Paragraph(
        "<b>Kính gửi:</b> Ngân hàng Chính sách xã hội ....................................",
        _style_body(),
    ))

    lines = [
        f"Tôi tên là: {ten_kh}..........................................................    Năm sinh: {nam_sinh}",
        f"Số điện thoại liên hệ: {sdt}.........................................................",
        f"Số CCCD: {so_cccd}.............., ngày cấp {ngay_cap_cmnd}, nơi cấp {noi_cap_cmnd}",
        f"Địa chỉ cư trú: {dia_chi}.................................................................",
        f"Là thành viên của Tổ TK&VV {ten_to} do ông (bà) .............................. làm tổ trưởng,",
        f"thuộc tổ chức Hội {dvut}........................................................ quản lý.",
        f"Theo Hợp đồng tín dụng (Sổ Vay vốn) số {so_ku}.............., ngày....../....../...... tôi có",
        f"dư nợ vay vốn chương trình {ten_ct} tại",
        f"Phòng giao dịch NHCSXH {ten_pgd}.............., tỉnh: ..............",
        f"Đến ngày ....../....../......, tôi còn nợ Ngân hàng Chính sách xã hội (NHCSXH) số tiền "
        f"{_fmt_dong(tong_no)}, trong đó: Số tiền gốc: {_fmt_dong(du_goc_f)}; "
        f"Số tiền lãi: {_fmt_dong(lai_f)}.",
        "Tôi cam kết trả nợ số tiền còn nợ NHCSXH theo kế hoạch cụ thể sau:",
    ]
    for line in lines:
        elements.append(Paragraph(line, _style_body()))

    elements.append(Spacer(1, 2))
    if so_tien_cam_ket or thoi_han or phuong_thuc:
        if thoi_han:
            elements.append(Paragraph(f"{thoi_han}", _style_body()))
        if so_tien_cam_ket:
            elements.append(Paragraph(f"{so_tien_cam_ket}", _style_body()))
        if phuong_thuc:
            elements.append(Paragraph(f"{phuong_thuc}", _style_body()))
    else:
        for _ in range(4):
            elements.append(Paragraph("....................................................................................", _style_body()))

    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "Nếu tôi không thực hiện đúng như cam kết này, tôi xin hoàn toàn chịu trách nhiệm "
        "trước NHCSXH, trước pháp luật./",
        _style_body(),
    ))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Ngày ..... tháng ...... năm ......", _style_date_right()))
    sig_borrow = Table(
        [[Paragraph("<b>Người vay</b><br/><i>(Ký ghi rõ họ tên, hoặc điểm chỉ)</i>", s_center)]],
        colWidths=[usable_w],
    )
    sig_borrow.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_borrow)
    elements.append(Spacer(1, 28))

    sig_tbl = Table(
        [[
            Paragraph("<b>Đại diện Ban quản lý<br/>Tổ TK&VV</b>", s_center),
            Paragraph("<b>Đại diện Tổ chức CT-<br/>XH/Trưởng thôn</b>", s_center),
            Paragraph("<b>Đại diện NHCSXH</b>", s_center),
        ], [
            Paragraph("<i>(Ký, ghi rõ họ tên)</i>", s_center),
            Paragraph("<i>(Ký, ghi rõ họ tên, đóng dấu<br/>(nếu có))</i>", s_center),
            Paragraph("<i>(Ký, ghi rõ họ tên, đóng dấu<br/>(nếu có))</i>", s_center),
        ], [
            Paragraph("<br/><br/><br/>", _style_body()),
            Paragraph("<br/><br/><br/>", _style_body()),
            Paragraph("<br/><br/><br/>", _style_body()),
        ]],
        colWidths=[usable_w / 3] * 3,
    )
    sig_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(sig_tbl)

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_bb_kt_cv368(noi_dung: dict) -> bytes:
    _dang_ky_font_qlnk()
    pgd = str(noi_dung.get("ten_pgd") or "")
    try:
        nam = int(noi_dung.get("nam") or datetime.now().year)
    except Exception:
        nam = datetime.now().year
    dot = noi_dung.get("dot")
    ngay_kt = str(noi_dung.get("ngay_kiem_tra") or "")[:10]
    ds_mon = noi_dung.get("ds_mon") or []

    buf = BytesIO()
    margin = 1.5 * cm
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=1.2 * cm,
        bottomMargin=2 * cm,
    )
    usable_w = landscape(A4)[0] - 2 * margin
    elements = []

    _sN = ParagraphStyle("bbN", fontName=_FN, fontSize=10, leading=14)
    _sR = ParagraphStyle("bbR", fontName=_FN, fontSize=10, leading=14, alignment=TA_RIGHT)
    left_html = (
        "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI<br/>"
        f"{TEN_CHI_NHANH_HIEN_THI}<br/>"
        f"<b>Phòng giao dịch {pgd}</b><br/>"
        "─────────────────────"
    )
    right_html = (
        "<b>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</b><br/>"
        "<i>Độc lập - Tự do - Hạnh phúc</i><br/>"
        "─────────────────────<br/>"
        f"{_dong_ten_nd()}"
    )
    hdr_tbl = Table(
        [[Paragraph(left_html, _sN), Paragraph(right_html, _sR)]],
        colWidths=[usable_w * 0.55, usable_w * 0.45],
    )
    hdr_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(hdr_tbl)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        "BIÊN BẢN KIỂM TRA NỢ KHOANH",
        ParagraphStyle("BBTitle", fontName=_FB, fontSize=14, leading=18, alignment=TA_CENTER, textColor=_VBSP_GREEN),
    ))
    elements.append(Spacer(1, 6))
    if dot:
        elements.append(Paragraph(f"<b>Đợt:</b> {dot} &nbsp;&nbsp; <b>Năm:</b> {nam}", _style_body()))
    else:
        elements.append(Paragraph(f"<b>Năm:</b> {nam}", _style_body()))
    if ngay_kt:
        elements.append(Paragraph(f"<b>Ngày kiểm tra:</b> {ngay_kt}", _style_body()))
    elements.append(Paragraph(
        "<i>Căn cứ: Công văn số 368/NHCS-QLN ngày 17/01/2024 của NHCSXH</i>",
        _style_body(),
    ))
    elements.append(Spacer(1, 8))

    th = _style_table_header(8)
    tc = _style_table_cell(8)
    tcL = _style_table_cell_left(8)
    col_hdrs = [
        "STT", "Tên tổ TK&VV", "Tên KH", "Số KU", "Dư nợ (đồng)",
        "Ngày HH khoanh", "Kết quả KT", "Khả năng TN", "Cam kết TN", "Ghi chú",
    ]
    col_w = [
        0.8 * cm, 3.2 * cm, 3.8 * cm, 2.4 * cm, 2.8 * cm,
        2.2 * cm, 2.5 * cm, 2.2 * cm, 3.0 * cm, 3.0 * cm,
    ]
    table_data = [[Paragraph(h, th) for h in col_hdrs]]
    tbl_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER_COLOR),
        ("BOX", (0, 0), (-1, -1), 1.0, _VBSP_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    for idx, item in enumerate(ds_mon, 1):
        du_no_raw = item.get("du_no_khoanh", 0)
        try:
            du_no_v = float(str(du_no_raw).replace(" đồng", "").replace(".", "").replace(",", "").strip())
        except Exception:
            du_no_v = 0.0
        table_data.append([
            Paragraph(str(idx), tc),
            Paragraph(str(item.get("ten_to") or ""), tcL),
            Paragraph(str(item.get("ten_kh") or ""), tcL),
            Paragraph(str(item.get("so_ku") or ""), tc),
            Paragraph(_qlnk_fmt_dong(du_no_v), tc),
            Paragraph(str(item.get("ngay_hh_khoanh") or ""), tc),
            Paragraph(str(item.get("ket_qua_kt") or ""), tcL),
            Paragraph(str(item.get("kha_nang_tn") or ""), tc),
            Paragraph(str(item.get("cam_ket_tn") or ""), tcL),
            Paragraph(str(item.get("ghi_chu") or ""), tcL),
        ])
        if idx % 2 == 0:
            tbl_cmds.append(("BACKGROUND", (0, idx), (-1, idx), _ROW_ALT))

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(tbl_cmds))
    elements.append(tbl)
    elements.append(Spacer(1, 10))

    _ve_footer_pdf(elements, usable_w, signatures=["NGƯỜI LẬP", "GIÁM ĐỐC"], ngay_str=_dong_ten_nd())
    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_mau_03qlnk(
    ten_pgd: str | dict,
    ten_to: str = "",
    ds_het_han: list | None = None,
    tu_ngay: str = "",
    den_ngay: str = "",
    ma_to: str = "",
    don_vi_uy_thac: str = "",
) -> bytes:
    if isinstance(ten_pgd, dict) and ds_het_han is None:
        return _xuat_pdf_bb_kt_cv368(ten_pgd)
    _dang_ky_font_qlnk()
    buf    = BytesIO()
    margin = 1.5 * cm
    doc    = SimpleDocTemplate(buf, pagesize=landscape(A4),
                               leftMargin=margin, rightMargin=margin,
                               topMargin=1.2 * cm, bottomMargin=2 * cm)
    usable_w = landscape(A4)[0] - 2 * margin
    elements = []

    ds_het_han = ds_het_han or []
    _sB = ParagraphStyle("hB", fontName=_FB, fontSize=10, leading=14)
    _sN = ParagraphStyle("hN", fontName=_FN, fontSize=10, leading=14)
    _sR = ParagraphStyle("hR", fontName=_FN, fontSize=9,  leading=13, alignment=TA_RIGHT)
    hdr_tbl = Table(
        [[
            Paragraph(
                f"{TEN_CHI_NHANH_HIEN_THI.upper()}<br/>"
                f"PHÒNG GIAO DỊCH {(ten_pgd or '').upper()}",
                _sB,
            ),
            Paragraph("Mẫu số 03/QLNK", _sR),
        ]],
        colWidths=[usable_w * 0.7, usable_w * 0.3],
    )
    hdr_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(hdr_tbl)
    elements.append(Spacer(1, 8))

    # ── Tiêu đề ───────────────────────────────────────────────────────────────
    _sTitle = ParagraphStyle("T", fontName=_FB, fontSize=13, alignment=TA_CENTER, leading=18)
    _sSub   = ParagraphStyle("S", fontName=_FN, fontSize=10, alignment=TA_CENTER, leading=14)
    elements.append(Paragraph("DANH SÁCH MÓN VAY HẾT THỜI GIAN KHOANH NỢ", _sTitle))
    tu_str  = tu_ngay  or "....... tháng ....... năm ......."
    den_str = den_ngay or "....... tháng ....... năm ......."
    elements.append(Paragraph(f"Từ ngày {tu_str} đến ngày {den_str}", _sSub))
    elements.append(Spacer(1, 6))

    # ── Thông tin tổ ─────────────────────────────────────────────────────────
    ten_to_str = ten_to or "................................"
    ma_to_str  = ma_to  or ".................."
    dvut_str   = don_vi_uy_thac or ""
    elements.append(Paragraph(
        f"Tên tổ trưởng: <b>{ten_to_str}</b>&nbsp;&nbsp;&nbsp;&nbsp;Mã tổ: <b>{ma_to_str}</b>",
        _sN,
    ))
    elements.append(Paragraph(f"Đơn vị ủy thác: <b>{dvut_str}</b>", _sN))

    # ── Đơn vị tính ──────────────────────────────────────────────────────────
    elements.append(Paragraph(
        "Đơn vị tính: đồng",
        ParagraphStyle("DVT", fontName=_FN, fontSize=9, alignment=TA_RIGHT, leading=12),
    ))
    elements.append(Spacer(1, 4))

    # ── Bảng dữ liệu (gộp theo khách hàng) ──────────────────────────────────
    headers03 = [
        "STT", "Khách hàng", "Mã món vay",
        "Ngày được khoanh nợ", "Ngày hết hạn khoanh",
        "Nợ gốc hết hạn khoanh (đồng)", "Ngày đến hạn trả nợ cuối cùng",
    ]
    col_w03 = [1.0*cm, 5.5*cm, 3.2*cm, 3.5*cm, 3.5*cm, 4.5*cm, 4.0*cm]
    th03 = _style_table_header(9)
    tc03 = _style_table_cell(9)
    tcL  = _style_table_cell_left(9)

    table_data   = [[Paragraph(h, th03) for h in headers03]]
    merge_cmds   = []   # SPAN commands cho gộp dòng KH
    tong_no_goc  = 0.0

    # Gộp theo tên khách hàng
    from collections import OrderedDict
    nhom_kh: dict = OrderedDict()
    for row in (ds_het_han or []):
        kh = row.get(COT_TEN_KH) or row.get("ten_kh") or "............"
        nhom_kh.setdefault(kh, []).append(row)

    stt        = 0
    data_row_i = 1  # index dòng trong table_data (bỏ header)
    for kh_name, loans in nhom_kh.items():
        stt += 1
        for loan_i, row in enumerate(loans):
            du_no = row.get(COT_DU_NO_KHOANH) or row.get("du_no_goc_khoanh") or 0
            try:
                du_no_f = float(du_no)
            except (TypeError, ValueError):
                du_no_f = 0.0
            tong_no_goc += du_no_f

            hh_raw = row.get(COT_NGAY_HH_KHOANH) or row.get("ngay_het_han_khoanh") or ""
            bdk    = row.get("ngay_bat_dau_khoanh") or ""
            so_th  = row.get("so_thang_khoanh")
            # Ưu tiên dùng cột HH trực tiếp; fallback tính từ BĐK + số tháng
            if not hh_raw and bdk and so_th:
                hh_raw = _qlnk_add_months(bdk, int(so_th))
            hh_str  = hh_raw  or "............"
            bdk_str = bdk     or "............"
            dh_str  = row.get(COT_NGAY_DH) or row.get("ngay_den_han") or "............"

            table_data.append([
                Paragraph(str(stt) if loan_i == 0 else "", tc03),
                Paragraph(kh_name  if loan_i == 0 else "", tcL),
                Paragraph(str(row.get(COT_SO_KU) or row.get("ma_mon_vay") or "............"), tc03),
                Paragraph(bdk_str, tc03),
                Paragraph(hh_str,  tc03),
                Paragraph(_qlnk_fmt_dong(du_no_f), tc03),
                Paragraph(dh_str,  tc03),
            ])

            # SPAN dọc cho cột STT và Khách hàng nếu KH có nhiều món
            if loan_i == 0 and len(loans) > 1:
                r_start = data_row_i
                r_end   = data_row_i + len(loans) - 1
                merge_cmds += [
                    ("SPAN", (0, r_start), (0, r_end)),
                    ("SPAN", (1, r_start), (1, r_end)),
                ]
            data_row_i += 1

    # Dòng Cộng
    last_row = len(table_data)
    table_data.append([
        Paragraph("", tc03),
        Paragraph("<b>Cộng:</b>",
                  ParagraphStyle("CB", fontName=_FB, fontSize=9, alignment=TA_LEFT, leading=12)),
        Paragraph("", tc03), Paragraph("", tc03), Paragraph("", tc03),
        Paragraph(f"<b>{_qlnk_fmt_dong(tong_no_goc)}</b>",
                  ParagraphStyle("CB2", fontName=_FB, fontSize=9, alignment=TA_CENTER, leading=12)),
        Paragraph("", tc03),
    ])

    style_cmds03 = [
        ("BACKGROUND",    (0, 0),  (-1, 0),        _HEADER_BG),
        ("GRID",          (0, 0),  (-1, -1),        0.5, _BORDER_COLOR),
        ("BOX",           (0, 0),  (-1, -1),        1,   colors.black),
        ("VALIGN",        (0, 0),  (-1, -1),        "MIDDLE"),
        ("TOPPADDING",    (0, 0),  (-1, -1),        3),
        ("BOTTOMPADDING", (0, 0),  (-1, -1),        3),
        ("BACKGROUND",    (0, last_row), (-1, last_row), _VBSP_GREEN_LIGHT),
        ("LINEABOVE",     (0, last_row), (-1, last_row), 1, colors.black),
    ] + merge_cmds

    tbl = Table(table_data, colWidths=col_w03, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds03))
    elements.append(tbl)
    elements.append(Spacer(1, 10))

    # ── Chữ ký ───────────────────────────────────────────────────────────────
    _ve_footer_pdf(
        elements, usable_w,
        signatures=["Lập biểu", "KIỂM SOÁT", "GIÁM ĐỐC"],
        ngay_str=_dong_ten_nd(),
    )

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_mau_04qlnk(row_hstd: dict, row_bs: dict, ten_pgd: str,
                         noi_dung: str = "", han_cuoi: str = "") -> bytes:
    _dang_ky_font_qlnk()
    ten_kh  = row_hstd.get(COT_TEN_KH) or row_hstd.get("ten_kh") or "............"
    dia_chi = row_hstd.get(COT_TEN_XA) or row_hstd.get("dia_chi") or "............"
    so_qd   = row_bs.get("so_quyet_dinh_khoanh") or "............"
    bdk     = row_bs.get("ngay_bat_dau_khoanh")  or "............"
    so_thang = row_bs.get("so_thang_khoanh")
    ngay_hh = (_qlnk_add_months(bdk, int(so_thang))
               if (bdk != "............" and so_thang) else "............")
    du_goc = row_hstd.get(COT_DU_NO_KHOANH) or row_hstd.get("du_no_goc_khoanh") or 0
    lai = row_hstd.get("Lãi tồn TH") or row_hstd.get("so_tien_lai_con_no") or 0
    try:
        du_goc_f = float(du_goc)
        lai_f = float(lai)
        tong_no = du_goc_f + lai_f
    except (TypeError, ValueError):
        du_goc_f = lai_f = tong_no = 0

    buf = BytesIO()
    margin = 2.5 * cm
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=margin, rightMargin=margin,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    usable_w = A4[0] - 2 * margin
    elements = []

    _ve_header_pdf(elements, usable_w,
                   tieu_de="THÔNG BÁO NỢ HẾT THỜI GIAN KHOANH NỢ",
                   don_vi_tren="NGÂN HÀNG CHÍNH SÁCH XÃ HỘI",
                   don_vi_duoi=f"CHI NHÁNH / PGD {(ten_pgd or '').upper()}")

    elements.append(Paragraph(
        "<font size='8'><i>Mẫu số: 04/QLNK</i></font>",
        ParagraphStyle("MS", fontName=_FN, fontSize=8,
                       alignment=TA_RIGHT, leading=10)))
    elements.append(Paragraph(
        "<i>..............., ngày ..... tháng ..... năm .....</i>",
        ParagraphStyle("DateBl", fontName=_FN, fontSize=10,
                       alignment=TA_RIGHT, leading=13, spaceAfter=8)))

    elements.append(Paragraph(
        f"<b>Kính gửi:</b> Ông/Bà {ten_kh}, địa chỉ: {dia_chi}",
        _style_body()))

    for line in [
        f"Căn cứ Quyết định số {so_qd} của Hội đồng quản trị "
        "Ngân hàng Chính sách xã hội;",
        f"Ngân hàng Chính sách xã hội thông báo khoản vay có số tiền vay "
        f"được khoanh nợ của Ông/Bà hết thời gian khoanh nợ vào ngày "
        f"{han_cuoi or ngay_hh}.",
        f"Tổng số dư nợ: {tong_no:,.0f} đồng, trong đó gốc: {du_goc_f:,.0f} đồng, "
        f"lãi: {lai_f:,.0f} đồng.",
        "Ngân hàng Chính sách xã hội sẽ tiếp tục thực hiện tính lãi của khoản vay "
        "theo thỏa thuận trong Hợp đồng tín dụng kể từ ngày hết thời gian khoanh nợ.",
        "Ngân hàng Chính sách xã hội thông báo để Ông/Bà biết và chuẩn bị nguồn "
        "trả nợ cho Ngân hàng.",
    ]:
        elements.append(Paragraph(line, _style_body()))

    elements.append(Spacer(1, 12))

    nr_data = [
        [Paragraph("<b>Nơi nhận:</b><br/>- Như kính gửi;<br/>- Lưu.",
                   ParagraphStyle("NR", fontName=_FN, fontSize=11,
                                  alignment=TA_LEFT, leading=16)),
         Paragraph("<b>GIÁM ĐỐC</b><br/><br/><br/><br/>"
                   "<i>(Ký, đóng dấu, ghi rõ họ tên)</i>",
                   ParagraphStyle("GD", fontName=_FN, fontSize=11,
                                  alignment=TA_CENTER, leading=16))],
    ]
    nr_tbl = Table(nr_data, colWidths=[usable_w * 0.5, usable_w * 0.5])
    nr_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    if noi_dung:
        elements.append(Paragraph(
            f"<i>Ghi chú: {noi_dung}</i>",
            ParagraphStyle("Note", fontName=_FN, fontSize=10,
                           alignment=TA_LEFT, leading=14,
                           textColor=colors.grey, spaceAfter=4)))
    elements.append(nr_tbl)

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_qlnk_06(ds_ket_qua: list, ten_pgd: str = "",
                      ngay_tu: str = "", ngay_den: str = "") -> bytes:
    """Báo cáo kết quả kiểm tra nợ khoanh — QLNK_06"""
    _dang_ky_font_qlnk()
    buf = BytesIO()
    margin = 1.0 * cm
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=1.5 * cm)
    usable_w = A4[0] - 2 * margin
    elements = []

    _ve_header_pdf(elements, usable_w,
                   tieu_de="BÁO CÁO KẾT QUẢ KIỂM TRA NỢ KHOANH",
                   don_vi_tren=TEN_CHI_NHANH_HIEN_THI.upper(),
                   don_vi_duoi=f"PHÒNG GIAO DỊCH {(ten_pgd or '').upper()}")
    elements.append(Paragraph(
        "<font size='7'><i>QLNK_06</i></font>",
        ParagraphStyle("MS", fontName=_FN, fontSize=7,
                       alignment=TA_RIGHT, leading=8)))

    if ngay_tu or ngay_den:
        elements.append(Paragraph(
            f"Từ ngày {ngay_tu or '..........'}  đến ngày {ngay_den or '..........'}",
            _style_body()))
    elements.append(Spacer(1, 3))

    headers = [
        "STT", "Mã KH", "Tên KH", "Tên PGD", "Tên CT",
        "Số KU", "Ngày BĐ KH", "Thời gian", "Ngày HH KH",
        "Dư nợ gốc", "Dư nợ gốc KH", "Chênh lệch",
        "TT dự án", "TH KH", "KN TN", "CK TN",
        "Trang thái", "Kiểm tra", "Lưu",
    ]
    ncols = len(headers)
    col_widths = [0.4*cm] * 19  # Tương đối bằng nhau, scaled down

    th = _style_table_header(6)
    tc = _style_table_cell(6)

    table_data = [[Paragraph(h, th) for h in headers]]
    for stt, row in enumerate(ds_ket_qua or [], 1):
        try:
            du_no_goc = float(row.get("du_no_goc") or 0)
            du_no_kh = float(row.get("du_no_goc_khoanh") or 0)
            chenh = float(row.get("chenh_lech") or 0)
        except (TypeError, ValueError):
            du_no_goc = du_no_kh = chenh = 0

        so_thang = row.get("so_thang_khoanh") or ""
        bdk = row.get("ngay_bat_dau_khoanh") or ""
        ngay_hh = (_qlnk_add_months(bdk, int(so_thang)) if bdk and so_thang else "")

        table_data.append([Paragraph(v, tc) for v in [
            str(stt),
            row.get("ma_mon_vay", "")[:8] or "",
            (row.get("ten_kh", "") or "")[:15],
            (row.get("ten_pgd", "") or "")[:12],
            (row.get("ten_ct", "") or "")[:10] if row.get("ten_ct") else "",
            row.get("so_ku", "")[:6] or "",
            bdk,
            f"{so_thang} tháng" if so_thang else "",
            ngay_hh,
            f"{int(du_no_goc/1e6)}" if du_no_goc else "",
            f"{int(du_no_kh/1e6)}" if du_no_kh else "",
            f"{int(chenh/1e6)}" if chenh else "",
            ("Bình thường" if not row.get("thuc_trang_du_an") else
             row.get("thuc_trang_du_an", "")[:10]),
            ("Bình thường" if not row.get("tinh_hinh_khach_hang") else
             row.get("tinh_hinh_khach_hang", "")[:10]),
            ("Có" if row.get("kha_nang_tra_no") == "co" else "Không"),
            ("Có" if row.get("cam_ket_tra_no") == "co" else "Không"),
            ("✓ PD" if row.get("trang_thai") == "da_phe_duyet" else
             ("○ TT" if row.get("trang_thai") == "luu_tam" else "")),
            (row.get("can_bo_kiem_tra", "") or "")[:10],
            (row.get("nguoi_nhap", "") or "")[:10],
        ]])

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER_COLOR),
        ("BOX", (0, 0), (-1, -1), 1, _VBSP_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for r in range(1, len(table_data)):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), _ROW_ALT))

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)

    _ve_footer_pdf(elements, usable_w,
                   signatures=["Lập biểu", "Kiểm soát", "Giám đốc"],
                   ngay_str=_dong_ten_nd())

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_m10(ds_luu_tam: list, ten_pgd: str = "") -> bytes:
    """M10 — Danh sách món vay chưa nhập kết quả kiểm tra"""
    _dang_ky_font_qlnk()
    buf = BytesIO()
    margin = 1.2 * cm
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=1.8 * cm)
    usable_w = A4[0] - 2 * margin
    elements = []

    _ve_header_pdf(elements, usable_w,
                   tieu_de="DANH SÁCH MÓN VAY CHƯA NHẬP KẾT QUẢ KIỂM TRA",
                   don_vi_tren=TEN_CHI_NHANH_HIEN_THI.upper(),
                   don_vi_duoi=f"PHÒNG GIAO DỊCH {(ten_pgd or '').upper()}")
    elements.append(Paragraph(
        "<font size='8'><i>M10_QLNK</i></font>",
        ParagraphStyle("MS", fontName=_FN, fontSize=8,
                       alignment=TA_RIGHT, leading=10)))
    elements.append(Paragraph("(Đơn vị tính: đồng)", _style_italic()))
    elements.append(Spacer(1, 4))

    headers_m10 = [
        "STT", "Mã KH", "Tên KH", "Tên PGD", "Số KU",
        "Dư nợ khoanh", "Ngày lưu", "Người nhập",
    ]
    col_w_m10 = [0.6*cm, 1.5*cm, 3.0*cm, 3.5*cm, 1.8*cm,
                 2.2*cm, 1.8*cm, 2.5*cm]

    th_m10 = _style_table_header(8)
    tc_m10 = _style_table_cell(8)

    table_data = [[Paragraph(h, th_m10) for h in headers_m10]]
    tong_no = 0
    for stt, row in enumerate(ds_luu_tam or [], 1):
        try:
            du_no = float(row.get("du_no_goc_khoanh") or 0)
        except (TypeError, ValueError):
            du_no = 0
        tong_no += du_no

        table_data.append([Paragraph(v, tc_m10) for v in [
            str(stt),
            row.get("ma_mon_vay", "")[:10] or "",
            (row.get("ten_kh", "") or "")[:25],
            (row.get("ten_pgd", "") or "")[:20],
            row.get("so_ku", "")[:8] or "",
            _qlnk_fmt_dong(du_no),
            row.get("ngay_kiem_tra", "") or "............",
            (row.get("nguoi_nhap", "") or "")[:15],
        ]])

    # Dòng cộng
    table_data.append([
        Paragraph("<b>Cộng:</b>",
                  ParagraphStyle("THB", fontName=_FB, fontSize=8, alignment=TA_CENTER)),
        Paragraph("", tc_m10), Paragraph("", tc_m10), Paragraph("", tc_m10),
        Paragraph("", tc_m10),
        Paragraph(f"<b>{_qlnk_fmt_dong(tong_no)}</b>",
                  ParagraphStyle("THB", fontName=_FB, fontSize=8, alignment=TA_CENTER)),
        Paragraph("", tc_m10), Paragraph("", tc_m10),
    ])

    style_m10 = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER_COLOR),
        ("BOX", (0, 0), (-1, -1), 1, _VBSP_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for r in range(1, len(table_data) - 1):
        if r % 2 == 0:
            style_m10.append(("BACKGROUND", (0, r), (-1, r), _ROW_ALT))
    last_row = len(table_data) - 1
    style_m10.append(("BACKGROUND", (0, last_row), (-1, last_row), _VBSP_GREEN_LIGHT))
    style_m10.append(("FONTNAME", (0, last_row), (-1, last_row), _FB))
    style_m10.append(("LINEABOVE", (0, last_row), (-1, last_row), 1.5, _VBSP_GREEN))

    tbl_m10 = Table(table_data, colWidths=col_w_m10, repeatRows=1)
    tbl_m10.setStyle(TableStyle(style_m10))
    elements.append(tbl_m10)

    _ve_footer_pdf(elements, usable_w,
                   signatures=["Lập biểu", "Kiểm soát", "Giám đốc"],
                   ngay_str=_dong_ten_nd())

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_ke_hoach_kt(
    noi_dung_or_data_kh: dict,
    ds_phan_cong: list | None = None,
    thanh_phan: dict | None = None,
    ten_pgd: str | None = None,
    nam: int | None = None,
) -> bytes:
    """Xuất PDF Kế hoạch kiểm tra nợ khoanh theo NĐ 30/2020."""
    from itertools import groupby as _groupby
    if ds_phan_cong is None and thanh_phan is None and ten_pgd is None and nam is None:
        nd = noi_dung_or_data_kh or {}
        ten_pgd = str(nd.get("ten_pgd") or "")
        try:
            nam = int(nd.get("nam") or datetime.now().year)
        except Exception:
            nam = datetime.now().year
        thanh_phan = nd.get("thanh_phan") or nd.get("thanh_phan_tham_gia") or {}
        ds_phan_cong = nd.get("ds_mon") or nd.get("ds_phan_cong") or []
    else:
        ds_phan_cong = ds_phan_cong or []
        thanh_phan = thanh_phan or {}
        ten_pgd = ten_pgd or ""
        try:
            nam = int(nam or datetime.now().year)
        except Exception:
            nam = datetime.now().year
    _dang_ky_font_qlnk()
    buf    = BytesIO()
    margin = 1.8 * cm
    use_ls = len(ds_phan_cong) > 20
    psz    = landscape(A4) if use_ls else A4
    doc    = SimpleDocTemplate(buf, pagesize=psz,
                               leftMargin=margin, rightMargin=margin,
                               topMargin=1.5 * cm, bottomMargin=2 * cm)
    usable_w = psz[0] - 2 * margin
    elements = []

    # ── Header 2 cột ─────────────────────────────────────────────────────────
    _sN  = ParagraphStyle("khN",  fontName=_FN, fontSize=10, leading=14)
    _sR  = ParagraphStyle("khR",  fontName=_FN, fontSize=10, leading=14, alignment=TA_RIGHT)
    left_html = (
        f"NGÂN HÀNG CHÍNH SÁCH XÃ HỘI<br/>"
        f"{TEN_CHI_NHANH_HIEN_THI}<br/>"
        f"<b>Phòng giao dịch {ten_pgd}</b><br/>"
        f"─────────────────────<br/>"
        f"Số: ......./KH-PGD"
    )
    right_html = (
        f"<b>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</b><br/>"
        f"<i>Độc lập - Tự do - Hạnh phúc</i><br/>"
        f"─────────────────────<br/>"
        f"{_dong_ten_nd()}"
    )
    hdr_tbl = Table(
        [[Paragraph(left_html, _sN), Paragraph(right_html, _sR)]],
        colWidths=[usable_w * 0.55, usable_w * 0.45],
    )
    hdr_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(hdr_tbl)
    elements.append(Spacer(1, 10))

    # ── Tiêu đề ───────────────────────────────────────────────────────────────
    elements.append(Paragraph(
        f"KẾ HOẠCH KIỂM TRA NỢ KHOANH NĂM {nam}",
        ParagraphStyle("KHTitle", fontName=_FB, fontSize=14, leading=18,
                       alignment=TA_CENTER, textColor=_VBSP_GREEN),
    ))
    elements.append(Spacer(1, 6))

    # ── Thông tin chung ───────────────────────────────────────────────────────
    elements.append(Paragraph(
        "<i>Căn cứ: Công văn số 368/NHCS-QLN ngày 17/01/2024 của NHCSXH</i>",
        _style_body(),
    ))
    elements.append(Paragraph(
        f"<b>PGD:</b> {ten_pgd} &nbsp;&nbsp; <b>Năm:</b> {nam}",
        _style_body(),
    ))
    elements.append(Spacer(1, 8))

    # ── Bảng kế hoạch ─────────────────────────────────────────────────────────
    col_hdrs = [
        "STT", "Tên tổ TK&VV", "Tên khách hàng", "Số khế ước",
        "Dư nợ khoanh (đồng)", "Ngày HH khoanh", "Ngày KT dự kiến", "Ghi chú",
    ]
    th  = _style_table_header(8)
    tc  = _style_table_cell(8)
    tcL = _style_table_cell_left(8)
    if use_ls:
        col_w = [0.8*cm, 3.5*cm, 4.5*cm, 2.8*cm, 3.2*cm, 2.5*cm, 2.5*cm, 3.0*cm]
    else:
        col_w = [0.7*cm, 3.0*cm, 3.8*cm, 2.5*cm, 2.8*cm, 2.2*cm, 2.2*cm, 2.3*cm]

    table_data = [[Paragraph(h, th) for h in col_hdrs]]
    tbl_cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0), _VBSP_GREEN),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("GRID",          (0, 0), (-1, -1), 0.5, _BORDER_COLOR),
        ("BOX",           (0, 0), (-1, -1), 1.0, _VBSP_GREEN),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    def _parse_dn(raw) -> float:
        try:
            return float(str(raw).replace(" đồng", "").replace(".", "").replace(",", "").strip())
        except (ValueError, TypeError):
            return 0.0

    stt        = 0
    tong_dn    = 0.0
    row_idx    = 1
    sorted_pc  = sorted(ds_phan_cong,
                        key=lambda x: (x.get("ten_to") or "", x.get("ten_xa") or ""))
    for to_name, group_items in _groupby(sorted_pc, key=lambda x: x.get("ten_to") or ""):
        items = list(group_items)
        span_start = row_idx
        for i, item in enumerate(items):
            stt  += 1
            dn_v  = _parse_dn(item.get("du_no_khoanh", 0))
            tong_dn += dn_v
            table_data.append([
                Paragraph(str(stt), tc),
                Paragraph(to_name if i == 0 else "", tcL),
                Paragraph(item.get("ten_kh") or "", tcL),
                Paragraph(item.get("so_ku") or "", tc),
                Paragraph(_qlnk_fmt_dong(dn_v), tc),
                Paragraph(item.get("ngay_hh_khoanh") or "", tc),
                Paragraph(item.get("ngay_kt_du_kien") or "", tc),
                Paragraph(item.get("ghi_chu") or "", tcL),
            ])
            row_idx += 1
        if len(items) > 1:
            tbl_cmds.append(("SPAN",   (1, span_start), (1, row_idx - 1)))
            tbl_cmds.append(("VALIGN", (1, span_start), (1, row_idx - 1), "MIDDLE"))
        for ri in range(span_start, row_idx):
            if (ri - 1) % 2 == 0:
                tbl_cmds.append(("BACKGROUND", (0, ri), (-1, ri), _ROW_ALT))

    _sTB = ParagraphStyle("sTB", fontName=_FB, fontSize=8, alignment=TA_CENTER, leading=11)
    table_data.append([
        Paragraph("", tc),
        Paragraph("<b>TỔNG CỘNG</b>", _sTB),
        Paragraph("", tc),
        Paragraph(f"<b>{stt} món</b>", _sTB),
        Paragraph(f"<b>{_qlnk_fmt_dong(tong_dn)}</b>", _sTB),
        Paragraph("", tc), Paragraph("", tc), Paragraph("", tc),
    ])
    last = len(table_data) - 1
    tbl_cmds += [
        ("BACKGROUND", (0, last), (-1, last), _VBSP_GREEN_LIGHT),
        ("FONTNAME",   (0, last), (-1, last), _FB),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, _VBSP_GREEN),
    ]

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(tbl_cmds))
    elements.append(tbl)
    elements.append(Spacer(1, 10))

    # ── Thành phần tham gia kiểm tra ─────────────────────────────────────────
    elements.append(Paragraph("<b>Thành phần tham gia kiểm tra:</b>", _style_body_bold()))
    for idx, (label, val) in enumerate([
        ("Đại diện NHCSXH",                   thanh_phan.get("dai_dien_nhcsxh", "")),
        ("Đại diện Ban quản lý Tổ TK&VV",     f"Ông/Bà {thanh_phan.get('to_tkv', '')}"),
        ("Đại diện tổ chức CT-XH",            thanh_phan.get("ct_xh", "")),
        ("Trưởng thôn",                        thanh_phan.get("truong_thon", "")),
        ("Đại diện UBND xã",                   thanh_phan.get("ubnd_xa", "")),
    ], 1):
        elements.append(Paragraph(
            f"{idx}. {label}: {val or '............'}",
            _style_body(),
        ))
    elements.append(Spacer(1, 10))

    # ── Footer ký duyệt ───────────────────────────────────────────────────────
    _ve_footer_pdf(elements, usable_w,
                   signatures=["NGƯỜI LẬP KẾ HOẠCH", "GIÁM ĐỐC"],
                   ngay_str=_dong_ten_nd())
    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
