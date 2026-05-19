"""Phân tích Nợ khoanh — danh mục khoản vay đang trong giai đoạn khoanh nợ QĐ 62.

Port từ VSPPRO Khoanh.tsx.
KPI cards + breakdown theo Chương trình / Xã / ĐVUT + danh sách chi tiết.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role, get_permissions, co_quyen_upload_pgd
from config import (
    COT_DU_NO_QH,
    COT_DVUT,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    DS_PGD,
    LY_DO_KHOANH_QD62,
    LY_DO_KHOANH_LABEL,
)
from utils import fmt_so, fmt_ty, get_tab_context, hien_thi_dataframe_phan_trang, xuat_excel
import db
from io import BytesIO
from datetime import datetime
from pathlib import Path

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
    _REPORTLAB_READY = False

COT_DU_NO_KHOANH = "Dư nợ khoanh"
COT_NGAY_HH_KHOANH = "Ngày hết hạn Khoanh"
COT_TEN_TO = "Tên tổ"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _loc_khoanh(df: pd.DataFrame) -> pd.DataFrame:
    """Lọc các món vay đang khoanh nợ (Dư nợ khoanh > 0)."""
    if COT_DU_NO_KHOANH not in df.columns:
        return pd.DataFrame()
    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    return df[du_kh > 0].copy()


def _bang_theo_nhom(df: pd.DataFrame, nhom_col: str) -> pd.DataFrame:
    """Bảng tổng hợp: nhóm | Số món | Dư nợ khoanh | Tỷ trọng%."""
    if nhom_col not in df.columns or df.empty:
        return pd.DataFrame()

    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df = df.copy()
    df["_du_kh"] = du_kh

    nhom = (
        df.groupby(nhom_col)
        .agg(so_mon=(COT_SO_KU, "nunique"), du_no_khoanh=("_du_kh", "sum"))
        .reset_index()
        .sort_values("du_no_khoanh", ascending=False)
    )

    tong = nhom["du_no_khoanh"].sum()
    nhom["Tỷ trọng%"] = (nhom["du_no_khoanh"] / tong * 100).round(1).apply(
        lambda x: f"{x:.1f}".replace(".", ",") + "%"
    ) if tong > 0 else "0%"
    nhom[COT_DU_NO_KHOANH] = nhom["du_no_khoanh"].apply(fmt_ty)
    nhom = nhom.rename(columns={"so_mon": "Số món"})
    return nhom[[nhom_col, "Số món", COT_DU_NO_KHOANH, "Tỷ trọng%"]]


def _chart_nhom(df: pd.DataFrame, nhom_col: str, key: str) -> None:
    """Horizontal bar chart: top 15 nhóm theo dư nợ khoanh."""
    try:
        import plotly.express as px
    except ImportError:
        return

    if df.empty or nhom_col not in df.columns:
        return

    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df = df.copy()
    df["_du_kh"] = du_kh

    nhom = df.groupby(nhom_col)["_du_kh"].sum().reset_index()
    nhom.columns = [nhom_col, "_val"]
    nhom = nhom[nhom["_val"] > 0].sort_values("_val", ascending=True).tail(15)
    if nhom.empty:
        return

    nhom["Label"] = nhom["_val"].apply(fmt_ty)

    fig = px.bar(
        nhom, y=nhom_col, x="_val",
        orientation="h",
        text="Label",
        color="_val",
        color_continuous_scale=["#fff3e0", "#e65100"],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=max(260, len(nhom) * 28 + 80),
        margin=dict(t=10, b=20, l=10, r=70),
        coloraxis_showscale=False,
        xaxis_title="Dư nợ khoanh (VND)",
        yaxis_title="",
    )
    st.plotly_chart(fig, width='stretch', key=key)


def _heatmap_dao_han(df: pd.DataFrame, key: str) -> None:
    """Bar chart phân bổ khoanh theo tháng đáo hạn."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    if COT_NGAY_DH not in df.columns or df.empty:
        return

    ngay_dh = pd.to_datetime(df[COT_NGAY_DH], errors="coerce", dayfirst=True)
    df = df.copy()
    df["_du_kh"] = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
    df["_ym"] = ngay_dh.dt.to_period("Y").astype(str)  # nhóm theo năm

    nhom = (
        df.groupby("_ym")
        .agg(so_mon=("_ym", "count"), du_no=("_du_kh", "sum"))
        .reset_index()
        .sort_values("_ym")
    )
    nhom = nhom[nhom["_ym"].str.match(r"\d{4}")]  # loại NaT

    if nhom.empty:
        return

    fig = go.Figure(go.Bar(
        x=nhom["_ym"],
        y=nhom["so_mon"],
        name="Số món",
        marker_color="#e64a19",
        text=nhom["so_mon"].astype(str),
        textposition="outside",
        hovertext=nhom["du_no"].apply(fmt_ty),
        hoverinfo="x+text",
    ))
    fig.update_layout(
        xaxis_title="Năm đáo hạn",
        yaxis_title="Số khoản khoanh",
        height=260,
        margin=dict(t=10, b=30, l=40, r=20),
    )
    st.markdown("**📅 Phân bổ theo năm đáo hạn**")
    st.plotly_chart(fig, width='stretch', key=key)


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
    bank_html = ("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM<br/>"
                 "<font size='10'>Chi nhánh tỉnh Đồng Nai</font>")

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
    dia_chi = row.get("ten_xa") or row.get(COT_TEN_XA) or row.get("dia_chi") or "............"
    so_cccd = row.get("so_cmnd") or row.get("so_cccd") or "............"
    ten_to  = row.get("ten_to_tkv") or row.get(COT_TEN_TO) or "............"
    so_ku   = row.get("ma_mon_vay") or row.get(COT_SO_KU) or "............"
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

    _ve_header_pdf(elements, usable_w,
                   tieu_de="CAM KẾT TRẢ NỢ",
                   don_vi_tren="",
                   don_vi_duoi="")

    elements.append(Paragraph(
        "<font size='8'><i>Mẫu số: 02/QLNK</i></font>",
        ParagraphStyle("MS", fontName=_FN, fontSize=8,
                       alignment=TA_RIGHT, leading=10)))
    elements.append(Paragraph(
        "<i>..............., ngày ..... tháng ..... năm .....</i>",
        ParagraphStyle("DateBl", fontName=_FN, fontSize=10,
                       alignment=TA_RIGHT, leading=13, spaceAfter=8)))

    elements.append(Paragraph(
        "<b>Kính gửi:</b> Ngân hàng Chính sách xã hội", _style_body()))

    for line in [
        f"Tôi tên: {ten_kh}    Năm sinh: ............    SĐT: ............",
        f"Số CCCD/CMND: {so_cccd}    Địa chỉ: {dia_chi}",
        f"Thành viên Tổ TK&amp;VV: {ten_to}",
        f"Theo HĐTD số: {so_ku}",
        f"Hiện còn nợ số tiền: {tong_no:,.0f} đồng "
        f"(gốc: {du_goc_f:,.0f} đồng, lãi: {lai_f:,.0f} đồng)",
    ]:
        elements.append(Paragraph(line, _style_body()))

    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "Tôi cam kết sẽ trả nợ cho Ngân hàng theo kế hoạch cụ thể:",
        _style_body()))

    tho = thoi_han or "............"
    tien = so_tien_cam_ket or "............"
    pt = phuong_thuc or "............"
    for l in [
        f"    - Thời gian: {tho}",
        f"    - Số tiền: {tien}",
        f"    - Địa điểm: {pt}",
    ]:
        elements.append(Paragraph(l, _style_body()))

    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "Tôi xin cam kết thực hiện đúng như trên.", _style_body()))

    _ve_footer_pdf(elements, usable_w, signatures=[
        "Người vay", "ĐD BQL Tổ TK&amp;VV",
        "ĐD CT-XH/Trưởng thôn", "ĐD NHCSXH",
    ])

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _xuat_pdf_mau_03qlnk(ten_pgd: str, ten_to: str, ds_het_han: list,
                         tu_ngay: str = "", den_ngay: str = "",
                         ma_to: str = "", don_vi_uy_thac: str = "") -> bytes:
    _dang_ky_font_qlnk()
    buf    = BytesIO()
    margin = 1.5 * cm
    doc    = SimpleDocTemplate(buf, pagesize=landscape(A4),
                               leftMargin=margin, rightMargin=margin,
                               topMargin=1.2 * cm, bottomMargin=2 * cm)
    usable_w = landscape(A4)[0] - 2 * margin
    elements = []

    # ── Header: 2 cột (đơn vị | mẫu số) ─────────────────────────────────────
    _sB = ParagraphStyle("hB", fontName=_FB, fontSize=10, leading=14)
    _sN = ParagraphStyle("hN", fontName=_FN, fontSize=10, leading=14)
    _sR = ParagraphStyle("hR", fontName=_FN, fontSize=9,  leading=13, alignment=TA_RIGHT)
    hdr_tbl = Table(
        [[
            Paragraph(
                f"CHI NHÁNH TỈNH ĐỒNG NAI<br/>"
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
                   don_vi_tren="CHI NHÁNH NHCSXH TỈNH ĐỒNG NAI",
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
                   don_vi_tren="CHI NHÁNH NHCSXH TỈNH ĐỒNG NAI",
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


# ─── Render ───────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """
    Render tab Phân tích Nợ khoanh.

    Dùng được ở cả phân hệ CN (truyền df_full) và PGD.
    """
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username", "unknown")

    ctx = get_tab_context(tab)
    with ctx:
        st.subheader("🔒 Phân tích Nợ khoanh")
        st.caption(
            "Khoản vay đang trong giai đoạn khoanh nợ theo QĐ 62/2015/QĐ-TTg. "
            "Phân tích theo Chương trình / Xã / Hội đoàn thể."
        )

        use_df = df_full if la_phan_he_cn(role) else df
        if use_df is None or use_df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD.")
            return

        if COT_DU_NO_KHOANH not in use_df.columns:
            st.info(
                f"ℹ️ Dữ liệu không có cột '{COT_DU_NO_KHOANH}'. "
                "Cần upload HSTD có cột Dư nợ khoanh."
            )
            return

        df_kh = _loc_khoanh(use_df)

        if df_kh.empty:
            st.success("✅ Hiện không có món vay nào đang khoanh nợ.")
            return

        st.divider()

        # ── Lọc PGD (CN only) — thực hiện TRƯỚC khi tính KPI ─────────────
        key_prefix = "cn_"
        if la_phan_he_cn(role):
            col_f, _ = st.columns([2, 4])
            with col_f:
                pgd_chon = st.selectbox(
                    "🔍 Lọc PGD",
                    ["Tất cả"] + DS_PGD,
                    key="khoanh_pgd_loc",
                )
            if pgd_chon != "Tất cả" and COT_TEN_PGD in df_kh.columns:
                df_kh = df_kh[df_kh[COT_TEN_PGD] == pgd_chon]
        else:
            from data.pgd import pgd_slug
            key_prefix = f"pgd_{pgd_slug(pgd_user)}_" if pgd_user else "pgd_"

        # ── KPI tổng quan — tính từ df_kh (đã qua filter PGD) ─────────────
        # tong_du_no: toàn bộ dư nợ cùng scope — lọc use_df theo PGD đã chọn
        _pgd_filter_kpi = (
            st.session_state.get("khoanh_pgd_loc")
            if la_phan_he_cn(role) else pgd_user
        )
        if _pgd_filter_kpi and _pgd_filter_kpi != "Tất cả" and COT_TEN_PGD in use_df.columns:
            use_df_scope = use_df[use_df[COT_TEN_PGD] == _pgd_filter_kpi]
        else:
            use_df_scope = use_df

        tong_du_no = (
            pd.to_numeric(use_df_scope[COT_TONG_DU_NO], errors="coerce").sum()
            if COT_TONG_DU_NO in use_df_scope.columns else 0
        )
        tong_khoanh = (
            pd.to_numeric(df_kh[COT_DU_NO_KHOANH], errors="coerce").fillna(0).sum()
        )
        so_mon = (
            df_kh[COT_SO_KU].nunique() if COT_SO_KU in df_kh.columns
            else len(df_kh)
        )
        so_ho = (
            df_kh[COT_MA_KH].nunique() if COT_MA_KH in df_kh.columns
            else 0
        )
        tl_khoanh = tong_khoanh / tong_du_no * 100 if tong_du_no > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🔒 Số món khoanh", fmt_so(so_mon))
        k2.metric("👤 Số hộ", fmt_so(so_ho))
        k3.metric("💰 Tổng dư nợ khoanh", fmt_ty(tong_khoanh))
        k4.metric(
            "📊 Tỷ lệ khoanh / tổng DN",
            f"{tl_khoanh:.2f}".replace(".", ",") + "%",
            delta=f"{tl_khoanh:.2f}".replace(".", ",") + "%" if tl_khoanh > 0 else None,
            delta_color="inverse" if tl_khoanh > 2 else "off",
        )

        # ── Heatmap đáo hạn ───────────────────────────────────────────────
        _heatmap_dao_han(df_kh, key=f"{key_prefix}khoanh_hm")

        st.divider()

        # ── Lọc món sắp hết hạn khoanh (từ sidebar badge) ────────────────
        _qlnk_filter = st.session_state.pop('_qlnk_filter', None)
        if _qlnk_filter == 'sap_het_han':
            from alert_center import canh_bao_no_khoanh_sap_het_han
            data_hh = canh_bao_no_khoanh_sap_het_han(df_kh)
            ds_hh = data_hh['chi_tiet_khan'] + data_hh['chi_tiet_canh_bao']
            if ds_hh:
                st.markdown("#### 🔍 Sắp hết hạn khoanh (M03)")
                st.caption(
                    f"🔴 {data_hh['so_khan']} món hết hạn ≤30 ngày · "
                    f"🟠 {data_hh['so_canh_bao']} món sắp hết hạn ≤180 ngày"
                )
                df_show = pd.DataFrame(ds_hh)
                if 'con_lai' in df_show.columns:
                    df_show = df_show.sort_values('con_lai')
                    df_show['Hạn còn (ngày)'] = df_show['con_lai']
                    df_show = df_show.drop(columns=['con_lai'], errors='ignore')
                st.dataframe(
                    df_show, width='stretch', hide_index=True,
                    use_container_width=True,
                )
            else:
                st.success("✅ Không có món nào sắp hết hạn khoanh.")

        # ── Sub-tabs ──────────────────────────────────────────────────────
        d1, d2, d3, d4, d5, d6, d7 = st.tabs([
            "📋 Theo Chương trình",
            "🏘️ Theo Xã",
            "🤝 Theo Hội đoàn thể",
            "📄 Danh sách chi tiết",
            "📅 Kế hoạch",
            "✏️ Kiểm tra",
            "📊 Báo cáo",
        ])

        for dtab, nhom_col, tag, label in [
            (d1, COT_TEN_CT,  "ct",   "Chương trình"),
            (d2, COT_TEN_XA,  "xa",   "Xã"),
            (d3, COT_DVUT,    "dvut", "Hội đoàn thể"),
        ]:
            with dtab:
                if nhom_col not in df_kh.columns:
                    st.info(f"Không có cột {label} trong dữ liệu.")
                    continue
                c_chart, c_table = st.columns([3, 2])
                with c_chart:
                    _chart_nhom(df_kh, nhom_col, key=f"{key_prefix}khoanh_{tag}_chart")
                with c_table:
                    bng = _bang_theo_nhom(df_kh, nhom_col)
                    if not bng.empty:
                        hien_thi_dataframe_phan_trang(
                            bng, key=f"{key_prefix}khoanh_{tag}_tbl", height=320
                        )

        with d4:
            cols_hien = [c for c in [
                COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_KH, COT_SO_KU,
                COT_TEN_CT, COT_DU_NO_KHOANH, COT_DU_NO_QH, COT_NGAY_DH,
            ] if c in df_kh.columns]

            df_hien = df_kh[cols_hien].copy()
            if COT_DU_NO_KHOANH in df_hien.columns:
                df_hien[COT_DU_NO_KHOANH] = (
                    pd.to_numeric(df_hien[COT_DU_NO_KHOANH], errors="coerce")
                    .apply(fmt_ty)
                )
            if COT_DU_NO_QH in df_hien.columns:
                df_hien[COT_DU_NO_QH] = (
                    pd.to_numeric(df_hien[COT_DU_NO_QH], errors="coerce")
                    .apply(fmt_ty)
                )

            hien_thi_dataframe_phan_trang(
                df_hien, key=f"{key_prefix}khoanh_chitiet", height=420
            )

            if st.button(
                f"📥 Xuất Excel ({len(df_kh)} món)",
                key=f"{key_prefix}khoanh_xuat",
            ):
                st.session_state[f"_{key_prefix}khoanh_buf"] = xuat_excel(
                    {"Nợ khoanh": df_hien}
                )
            if st.session_state.get(f"_{key_prefix}khoanh_buf"):
                st.download_button(
                    "⬇️ Tải về Excel",
                    data=st.session_state[f"_{key_prefix}khoanh_buf"],
                    file_name="NoKhoanh.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"{key_prefix}khoanh_dl",
                )

        with d5:
            perms = get_permissions(role)
            co_quyen_nhap  = perms.get("can_upload") or perms.get("upload")
            co_quyen_duyet = la_phan_he_cn(role) or co_quyen_upload_pgd(role)
            pgd_filter_kh  = None if la_phan_he_cn(role) else pgd_user

            # ── A: Form lập kế hoạch cả năm ──────────────────────────────────
            with st.expander("➕ Lập / cập nhật kế hoạch kiểm tra cả năm", expanded=False):
                if not co_quyen_nhap:
                    st.warning("⚠️ Bạn không có quyền lập kế hoạch kiểm tra.")
                else:
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        nam_kh = st.number_input(
                            "Năm kế hoạch *",
                            min_value=2020, max_value=2035,
                            value=datetime.now().year, step=1,
                            key=f"{key_prefix}kh_nam",
                        )
                    with c2:
                        if la_phan_he_cn(role):
                            pgd_kh = st.selectbox(
                                "PGD *", ["— Chọn —"] + DS_PGD,
                                key=f"{key_prefix}kh_pgd",
                            )
                        else:
                            pgd_kh = pgd_user or ""
                            st.info(f"PGD: **{pgd_kh}**")

                    # Lọc toàn bộ món khoanh hết hạn trong năm đã chọn
                    df_kh_form = df_kh.copy()
                    if la_phan_he_cn(role) and pgd_kh != "— Chọn —":
                        if COT_TEN_PGD in df_kh_form.columns:
                            df_kh_form = df_kh_form[df_kh_form[COT_TEN_PGD] == pgd_kh]
                    elif not la_phan_he_cn(role) and pgd_user:
                        if COT_TEN_PGD in df_kh_form.columns:
                            df_kh_form = df_kh_form[df_kh_form[COT_TEN_PGD] == pgd_user]

                    if COT_NGAY_HH_KHOANH in df_kh_form.columns:
                        _hh_s = pd.to_datetime(
                            df_kh_form[COT_NGAY_HH_KHOANH], dayfirst=True, errors="coerce"
                        )
                        df_kh_form = df_kh_form[_hh_s.dt.year == int(nam_kh)].copy()

                    if df_kh_form.empty:
                        _pgd_s = f" của {pgd_kh}" if (la_phan_he_cn(role) and pgd_kh != "— Chọn —") else ""
                        st.info(f"ℹ️ Không có món vay khoanh nào hết hạn trong năm {int(nam_kh)}{_pgd_s}.")
                    else:
                        st.info(
                            f"📋 **{len(df_kh_form)} món vay** hết hạn khoanh trong năm {int(nam_kh)}. "
                            "Điền **Ngày KT dự kiến** cho từng món "
                            "(bắt buộc trong vòng **120 ngày** trước ngày hết hạn khoanh)."
                        )

                        # Bảng phân công — data_editor (chỉ 2 cột được chỉnh)
                        _cols_co_dinh = [c for c in [
                            COT_TEN_XA, COT_TEN_TO, COT_TEN_KH,
                            COT_SO_KU, COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH,
                        ] if c in df_kh_form.columns]

                        df_edit = df_kh_form[_cols_co_dinh].copy().reset_index(drop=True)
                        df_edit[COT_DU_NO_KHOANH] = (
                            pd.to_numeric(df_edit[COT_DU_NO_KHOANH], errors="coerce")
                            .fillna(0).apply(fmt_ty)
                        )
                        df_edit["Ngày KT dự kiến"] = ""
                        df_edit["Ghi chú"]         = ""

                        df_edited = st.data_editor(
                            df_edit,
                            key=f"{key_prefix}kh_phan_cong",
                            use_container_width=True,
                            height=min(45 + len(df_edit) * 35, 520),
                            disabled=_cols_co_dinh,
                            column_config={
                                "Ngày KT dự kiến": st.column_config.TextColumn(
                                    "Ngày KT dự kiến",
                                    help="Nhập dạng dd/mm/yyyy. Phải ≤ 120 ngày trước HH khoanh.",
                                    max_chars=12,
                                ),
                            },
                        )

                        # Thành phần đoàn
                        st.markdown("**Thành phần đoàn kiểm tra**")
                        df_tp = st.data_editor(
                            pd.DataFrame([
                                {"Họ và tên": username, "Chức vụ": "CBTD"},
                                {"Họ và tên": "",       "Chức vụ": ""},
                            ]),
                            num_rows="dynamic",
                            key=f"{key_prefix}kh_tp_doan",
                            use_container_width=True,
                        )

                        ghi_chu_kh = st.text_area(
                            "Ghi chú chung", key=f"{key_prefix}kh_ghi_chu", max_chars=500,
                        )

                        col_b1, col_b2, _ = st.columns([1, 1, 4])
                        with col_b1:
                            luu_kh_btn = st.button(
                                "💾 Lưu kế hoạch", key=f"{key_prefix}kh_luu",
                                use_container_width=True,
                            )
                        with col_b2:
                            duyet_kh_btn = st.button(
                                "✅ Duyệt luôn", key=f"{key_prefix}kh_duyet_luon",
                                disabled=not co_quyen_duyet, use_container_width=True,
                            )

                        if luu_kh_btn or duyet_kh_btn:
                            loi_kh = []
                            if la_phan_he_cn(role) and pgd_kh == "— Chọn —":
                                loi_kh.append("Chưa chọn PGD")

                            # Build ds_phan_cong
                            ku_hh_map = {}
                            if COT_SO_KU in df_kh_form.columns and COT_NGAY_HH_KHOANH in df_kh_form.columns:
                                ku_hh_map = {
                                    str(r[COT_SO_KU] or ""): str(r[COT_NGAY_HH_KHOANH] or "")
                                    for _, r in df_kh_form.iterrows()
                                }
                            ds_phan_cong = []
                            for _, row_e in df_edited.iterrows():
                                so_ku     = str(row_e.get(COT_SO_KU, "") or "")
                                ngay_kt_s = str(row_e.get("Ngày KT dự kiến", "") or "").strip()
                                hh_raw    = ku_hh_map.get(so_ku, "")
                                ds_phan_cong.append({
                                    "so_ku":           so_ku,
                                    "ten_kh":          str(row_e.get(COT_TEN_KH, "") or ""),
                                    "ten_xa":          str(row_e.get(COT_TEN_XA, "") or ""),
                                    "ten_to":          str(row_e.get(COT_TEN_TO, "") or ""),
                                    "ngay_hh_khoanh":  hh_raw,
                                    "du_no_khoanh":    str(row_e.get(COT_DU_NO_KHOANH, "") or ""),
                                    "ngay_kt_du_kien": ngay_kt_s,
                                    "ghi_chu":         str(row_e.get("Ghi chú", "") or ""),
                                })

                            if loi_kh:
                                for _l in loi_kh:
                                    st.error(f"❌ {_l}")
                            else:
                                tp_list    = df_tp[df_tp["Họ và tên"].str.strip() != ""].to_dict("records")
                                ten_pgd_kh = pgd_kh if la_phan_he_cn(role) else (pgd_user or "")
                                data_kh = {
                                    "ten_pgd":         ten_pgd_kh,
                                    "nam":             int(nam_kh),
                                    "thanh_phan_doan": tp_list,
                                    "ds_phan_cong":    ds_phan_cong,
                                    "ghi_chu":         ghi_chu_kh,
                                }
                                try:
                                    kh_id = db.luu_ke_hoach_kiem_tra(data_kh, username)
                                    if duyet_kh_btn:
                                        db.duyet_ke_hoach(kh_id, username)
                                    label_kh = "lưu và duyệt" if duyet_kh_btn else "lưu"
                                    st.success(f"✅ Đã {label_kh} kế hoạch kiểm tra năm {int(nam_kh)}.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Lỗi: {e}")

            # ── B: Danh sách kế hoạch đã lập ─────────────────────────────────
            st.markdown("### 📋 Danh sách kế hoạch đã lập")

            cf1, cf2, _ = st.columns([1, 2, 3])
            with cf1:
                nam_loc = st.number_input(
                    "Năm", min_value=2020, max_value=2035,
                    value=datetime.now().year, step=1,
                    key=f"{key_prefix}kh_loc_nam",
                )
            with cf2:
                loc_tt_kh = st.selectbox(
                    "Trạng thái",
                    ["Tất cả", "Chờ duyệt", "Đã duyệt"],
                    key=f"{key_prefix}kh_loc_tt",
                )
            tt_map_kh = {"Tất cả": None, "Chờ duyệt": "luu_tam", "Đã duyệt": "da_duyet"}

            rows_kh = db.doc_ke_hoach_kiem_tra(
                ten_pgd=pgd_filter_kh,
                trang_thai=tt_map_kh[loc_tt_kh],
                nam=int(nam_loc),
            )

            if not rows_kh:
                st.info("ℹ️ Chưa có kế hoạch nào.")
            else:
                df_kh_list = pd.DataFrame([{
                    "ID":            r["id"],
                    "PGD":           r["ten_pgd"],
                    "Năm":           r.get("nam", ""),
                    "Tổng món":      len(r.get("ds_phan_cong") or []),
                    "Đã điền ngày":  sum(
                        1 for x in (r.get("ds_phan_cong") or [])
                        if x.get("ngay_kt_du_kien", "").strip()
                    ),
                    "Trạng thái":    r["trang_thai"],
                    "Người lập":     r["nguoi_lap"],
                    "Người duyệt":   r.get("nguoi_duyet", ""),
                    "Ngày duyệt":    r.get("ngay_duyet", ""),
                } for r in rows_kh])

                hien_thi_dataframe_phan_trang(
                    df_kh_list, key=f"{key_prefix}kh_list_tbl", height=320,
                )

                if co_quyen_duyet:
                    st.markdown("**Duyệt kế hoạch theo ID:**")
                    kh_id_action = st.number_input(
                        "ID kế hoạch", min_value=1, step=1,
                        key=f"{key_prefix}kh_action_id",
                    )
                    if st.button("✅ Duyệt kế hoạch này", key=f"{key_prefix}kh_duyet_id"):
                        ok = db.duyet_ke_hoach(int(kh_id_action), username)
                        st.success("Đã duyệt.") if ok else st.error("Không thể duyệt.")
                        st.rerun()

        with d6:
            perms = get_permissions(role)
            co_quyen_nhap = perms.get("can_upload")
            co_quyen_duyet = la_phan_he_cn(role) or co_quyen_upload_pgd(role)

            with st.expander("➕ Nhập kết quả kiểm tra mới", expanded=False):
                if not co_quyen_nhap:
                    st.warning("⚠️ Bạn không có quyền nhập kết quả kiểm tra.")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        if not df_kh.empty and COT_SO_KU in df_kh.columns:
                            options_ku = sorted(df_kh[COT_SO_KU].dropna().unique().tolist())
                            chon_ku = st.selectbox(
                                "Số khế ước *",
                                ["— Chọn —"] + options_ku,
                                key=f"{key_prefix}kt_ku",
                            )
                            row_chon = (
                                df_kh[df_kh[COT_SO_KU] == chon_ku].iloc[0]
                                if chon_ku != "— Chọn —" else None
                            )
                        else:
                            chon_ku = st.text_input(
                                "Số khế ước *", key=f"{key_prefix}kt_ku_txt"
                            )
                            row_chon = None

                        ten_kh_hien = (
                            str(row_chon.get(COT_TEN_KH, "")) if row_chon is not None else ""
                        )
                        st.text_input(
                            "Tên khách hàng",
                            value=ten_kh_hien,
                            disabled=True,
                            key=f"{key_prefix}kt_ten_kh",
                        )

                    with c2:
                        ngay_kt = st.date_input(
                            "Ngày kiểm tra *", key=f"{key_prefix}kt_ngay"
                        )
                        can_bo = st.text_input(
                            "Cán bộ kiểm tra",
                            value=username,
                            key=f"{key_prefix}kt_canbo",
                        )

                    st.markdown("**Thông tin khoanh** *(bổ sung 1 lần nếu chưa có)*")
                    bs_data = (
                        db.doc_bo_sung_mon_vay(chon_ku)
                        if chon_ku and chon_ku != "— Chọn —" else None
                    )
                    c3, c4, c5 = st.columns(3)
                    with c3:
                        ngay_bdk = st.text_input(
                            "Ngày bắt đầu khoanh (dd/mm/yyyy)",
                            value=bs_data.get("ngay_bat_dau_khoanh", "") if bs_data else "",
                            key=f"{key_prefix}kt_bdk",
                        )
                    with c4:
                        so_thang_kh = st.number_input(
                            "Số tháng khoanh",
                            min_value=0, max_value=120, step=1,
                            value=int(bs_data.get("so_thang_khoanh") or 0) if bs_data else 0,
                            key=f"{key_prefix}kt_sothang",
                        )
                    with c5:
                        so_qd = st.text_input(
                            "Số QĐ khoanh",
                            value=bs_data.get("so_quyet_dinh_khoanh", "") if bs_data else "",
                            key=f"{key_prefix}kt_soqd",
                        )

                    st.markdown("**Theo dõi tại ngân hàng** *(prefill từ HSTD, có thể sửa)*")
                    c6, c7, c8 = st.columns(3)
                    with c6:
                        du_no_goc = st.number_input(
                            "Dư nợ gốc (đồng)",
                            min_value=0.0, step=1_000_000.0, format="%.0f",
                            value=float(pd.to_numeric(
                                row_chon.get(COT_TONG_DU_NO, 0), errors="coerce"
                            ) or 0) if row_chon is not None else 0.0,
                            key=f"{key_prefix}kt_no_goc",
                        )
                    with c7:
                        du_no_goc_kh = st.number_input(
                            "Dư nợ gốc khoanh (đồng)",
                            min_value=0.0, step=1_000_000.0, format="%.0f",
                            value=float(pd.to_numeric(
                                row_chon.get(COT_DU_NO_KHOANH, 0), errors="coerce"
                            ) or 0) if row_chon is not None else 0.0,
                            key=f"{key_prefix}kt_no_goc_kh",
                        )
                    with c8:
                        lai_con_no = st.number_input(
                            "Lãi còn nợ NH (đồng)",
                            min_value=0.0, step=100_000.0, format="%.0f",
                            key=f"{key_prefix}kt_lai_con",
                        )

                    st.markdown("**Kiểm tra thực tế tại khách hàng**")
                    c9, c10, c11 = st.columns(3)
                    with c9:
                        du_no_goc_tt = st.number_input(
                            "Dư nợ gốc (thực tế)",
                            min_value=0.0, step=1_000_000.0, format="%.0f",
                            key=f"{key_prefix}kt_tt_goc",
                        )
                    with c10:
                        du_no_kh_tt = st.number_input(
                            "Dư nợ khoanh (thực tế)",
                            min_value=0.0, step=1_000_000.0, format="%.0f",
                            key=f"{key_prefix}kt_tt_kh",
                        )
                    with c11:
                        lai_tt = st.number_input(
                            "Lãi (thực tế)",
                            min_value=0.0, step=100_000.0, format="%.0f",
                            key=f"{key_prefix}kt_tt_lai",
                        )

                    chenh_lech = du_no_goc_kh - du_no_kh_tt
                    ly_do_cl = ""
                    if chenh_lech != 0:
                        st.info(
                            f"⚠️ Chênh lệch dư nợ khoanh: "
                            f"**{fmt_so(abs(chenh_lech))} đồng**"
                        )
                        ly_do_cl = st.text_area(
                            "Lý do chênh lệch *",
                            max_chars=250,
                            key=f"{key_prefix}kt_lydo_cl",
                        )

                    st.markdown("**Đánh giá (Mẫu 01/QLNK)**")
                    thuc_trang = st.text_area(
                        "Thực trạng dự án/phương án vay vốn (cột 12)",
                        max_chars=250,
                        help="Tối thiểu 5 ký tự. Chương trình NS&VSMTNT, HSSV, Nhà ở không bắt buộc.",
                        key=f"{key_prefix}kt_thuc_trang",
                    )
                    tinh_hinh_kh = st.text_area(
                        "Tình hình thực tế của khách hàng (cột 13)",
                        max_chars=250,
                        key=f"{key_prefix}kt_tinh_hinh",
                    )
                    kha_nang = st.radio(
                        "Khả năng trả nợ (cột 14)",
                        options=["co", "chua_co", "khong_co"],
                        format_func=lambda x: {
                            "co": "Có khả năng trả nợ",
                            "chua_co": "Chưa có khả năng trả nợ",
                            "khong_co": "Không có khả năng trả nợ",
                        }[x],
                        horizontal=True,
                        key=f"{key_prefix}kt_kha_nang",
                    )
                    cam_ket = None
                    if kha_nang == "co":
                        cam_ket = st.radio(
                            "Cam kết trả nợ (cột 15)",
                            options=["co_cam_ket", "khong_cam_ket", "khong_thuc_hien"],
                            format_func=lambda x: {
                                "co_cam_ket": "Có cam kết",
                                "khong_cam_ket": "Không cam kết",
                                "khong_thuc_hien": "Không thực hiện cam kết",
                            }[x],
                            horizontal=True,
                            key=f"{key_prefix}kt_cam_ket",
                        )

                    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                    with col_btn1:
                        luu_tam_btn = st.button(
                            "💾 Lưu tạm",
                            key=f"{key_prefix}kt_luu_tam",
                            use_container_width=True,
                        )
                    with col_btn2:
                        phe_duyet_btn = st.button(
                            "✅ Phê duyệt",
                            key=f"{key_prefix}kt_phe_duyet",
                            disabled=not co_quyen_duyet,
                            use_container_width=True,
                        )

                    if luu_tam_btn or phe_duyet_btn:
                        loi = []
                        if not chon_ku or chon_ku == "— Chọn —":
                            loi.append("Chưa chọn số khế ước")
                        if not ngay_kt:
                            loi.append("Chưa nhập ngày kiểm tra")
                        if chenh_lech != 0 and not ly_do_cl.strip():
                            loi.append("Có chênh lệch nhưng chưa nhập lý do")

                        if loi:
                            for l in loi:
                                st.error(f"❌ {l}")
                        else:
                            trang_thai_luu = "da_phe_duyet" if phe_duyet_btn else "luu_tam"
                            ten_pgd_v = (
                                str(row_chon.get(COT_TEN_PGD, pgd_user or ""))
                                if row_chon is not None else (pgd_user or "")
                            )
                            data_dict = {
                                "ma_mon_vay": chon_ku if chon_ku != "— Chọn —" else "",
                                "ten_pgd": ten_pgd_v,
                                "ten_xa": str(row_chon.get(COT_TEN_XA, ""))
                                          if row_chon is not None else "",
                                "ten_to_tkv": str(row_chon.get(COT_TEN_TO, ""))
                                              if row_chon is not None else "",
                                "ten_kh": ten_kh_hien,
                                "ngay_bat_dau_khoanh": ngay_bdk,
                                "so_thang_khoanh": so_thang_kh or None,
                                "so_quyet_dinh_khoanh": so_qd,
                                "ngay_kiem_tra": str(ngay_kt),
                                "ngay_het_han_khoanh": (
                                    str(row_chon.get(COT_NGAY_HH_KHOANH, "") or "")
                                    if row_chon is not None else ""
                                ),
                                "can_bo_kiem_tra": can_bo,
                                "du_no_goc": du_no_goc,
                                "du_no_goc_khoanh": du_no_goc_kh,
                                "so_tien_lai_con_no": lai_con_no,
                                "du_no_goc_thuc_te": du_no_goc_tt,
                                "du_no_khoanh_thuc_te": du_no_kh_tt,
                                "so_tien_lai_thuc_te": lai_tt,
                                "chenh_lech": chenh_lech,
                                "ly_do_chenh_lech": ly_do_cl,
                                "thuc_trang_du_an": thuc_trang,
                                "tinh_hinh_khach_hang": tinh_hinh_kh,
                                "kha_nang_tra_no": kha_nang,
                                "cam_ket_tra_no": cam_ket,
                                "trang_thai": trang_thai_luu,
                            }
                            try:
                                db.luu_ket_qua_kiem_tra(data_dict, username)
                                if ngay_bdk or so_qd:
                                    db.luu_bo_sung_mon_vay(
                                        data_dict["ma_mon_vay"],
                                        ten_pgd_v,
                                        {
                                            "ngay_bat_dau_khoanh": ngay_bdk,
                                            "so_thang_khoanh": so_thang_kh,
                                            "so_quyet_dinh_khoanh": so_qd,
                                        },
                                        username,
                                    )
                                st.cache_data.clear()
                                label = "phê duyệt" if phe_duyet_btn else "lưu tạm"
                                st.success(f"✅ Đã {label} kết quả kiểm tra.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Lỗi khi lưu: {e}")

            st.markdown("### 📋 Kết quả kiểm tra đã lưu")

            col_f1, col_f2, _ = st.columns([2, 2, 4])
            with col_f1:
                loc_tt = st.selectbox(
                    "Trạng thái",
                    ["Tất cả", "Lưu tạm", "Đã phê duyệt", "Mở phê duyệt"],
                    key=f"{key_prefix}kt_loc_tt",
                )
            tt_map = {
                "Tất cả": None,
                "Lưu tạm": "luu_tam",
                "Đã phê duyệt": "da_phe_duyet",
                "Mở phê duyệt": "mo_phe_duyet",
            }
            pgd_filter = None if la_phan_he_cn(role) else pgd_user

            rows_kt = db.doc_ket_qua_kiem_tra(
                ten_pgd=pgd_filter,
                trang_thai=tt_map[loc_tt],
            )

            if not rows_kt:
                st.info("ℹ️ Chưa có kết quả kiểm tra nào được lưu.")
            else:
                df_kt = pd.DataFrame(rows_kt)
                col_rename = {
                    "id": "ID",
                    "ma_mon_vay": "Số KU",
                    "ten_pgd": "PGD",
                    "ten_kh": "Khách hàng",
                    "ngay_kiem_tra": "Ngày KT",
                    "kha_nang_tra_no": "Khả năng TN",
                    "cam_ket_tra_no": "Cam kết",
                    "trang_thai": "Trạng thái",
                    "nguoi_nhap": "Người nhập",
                }
                df_hien_kt = df_kt.rename(columns=col_rename)
                cols_show = [c for c in col_rename.values() if c in df_hien_kt.columns]
                hien_thi_dataframe_phan_trang(
                    df_hien_kt[cols_show],
                    key=f"{key_prefix}kt_list_tbl",
                    height=360,
                )

                if co_quyen_duyet:
                    st.markdown("**Thao tác theo ID:**")
                    chon_id = st.number_input(
                        "ID bản ghi",
                        min_value=1, step=1,
                        key=f"{key_prefix}kt_action_id",
                    )
                    ca1, ca2, _ = st.columns([1, 1, 4])
                    with ca1:
                        if st.button(
                            "✅ Phê duyệt",
                            key=f"{key_prefix}kt_phe_duyet_id",
                            use_container_width=True,
                        ):
                            ok = db.phe_duyet_ket_qua(int(chon_id), username)
                            (st.success("Đã phê duyệt.") if ok
                             else st.error("Không thể phê duyệt."))
                            st.rerun()
                    with ca2:
                        if st.button(
                            "🔓 Mở phê duyệt",
                            key=f"{key_prefix}kt_mo_pd_id",
                            use_container_width=True,
                        ):
                            ok = db.mo_phe_duyet(int(chon_id), username)
                            (st.success("Đã mở phê duyệt.") if ok
                             else st.error("Không thể mở."))
                            st.rerun()

        with d7:
            st.markdown("### 📊 Báo cáo Quản lý Nợ khoanh")

            pgd_filter_bc = None if la_phan_he_cn(role) else pgd_user
            rows_all_kt = db.doc_ket_qua_kiem_tra(ten_pgd=pgd_filter_bc)
            da_kiem_tra_set = {r["ma_mon_vay"] for r in rows_all_kt}

            with st.expander(
                "📋 M08 — Danh sách món vay chưa kiểm tra", expanded=True
            ):
                if COT_SO_KU in df_kh.columns:
                    df_chua_kt = df_kh[~df_kh[COT_SO_KU].isin(da_kiem_tra_set)].copy()
                else:
                    df_chua_kt = df_kh.copy()

                st.metric("Số món chưa kiểm tra", fmt_so(len(df_chua_kt)))

                if not df_chua_kt.empty:
                    cols_m08 = [c for c in [
                        COT_TEN_PGD, COT_TEN_XA, COT_TEN_KH, COT_SO_KU,
                        COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH,
                    ] if c in df_chua_kt.columns]
                    hien_thi_dataframe_phan_trang(
                        df_chua_kt[cols_m08],
                        key=f"{key_prefix}bc_m08_tbl",
                        height=320,
                    )
                    if st.button("📥 Xuất M08 Excel", key=f"{key_prefix}bc_m08_xuat"):
                        st.session_state[f"_{key_prefix}m08_buf"] = xuat_excel(
                            {"M08_ChuaKiemTra": df_chua_kt[cols_m08]}
                        )
                    if st.session_state.get(f"_{key_prefix}m08_buf"):
                        st.download_button(
                            "⬇️ Tải M08",
                            data=st.session_state[f"_{key_prefix}m08_buf"],
                            file_name="M08_ChuaKiemTra.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_m08_dl",
                        )

            with st.expander("📋 M09 — Danh sách món vay có khả năng trả nợ"):
                rows_m09 = [
                    r for r in rows_all_kt
                    if r.get("trang_thai") == "da_phe_duyet"
                    and r.get("kha_nang_tra_no") == "co"
                ]
                df_m09 = pd.DataFrame(rows_m09)
                st.metric("Số món có KN trả nợ", fmt_so(len(df_m09)))
                if not df_m09.empty:
                    cols_m09 = [c for c in [
                        "ma_mon_vay", "ten_pgd", "ten_kh",
                        "ngay_kiem_tra", "cam_ket_tra_no", "nguoi_nhap",
                    ] if c in df_m09.columns]
                    hien_thi_dataframe_phan_trang(
                        df_m09[cols_m09],
                        key=f"{key_prefix}bc_m09_tbl",
                        height=300,
                    )
                    if st.button("📥 Xuất M09 Excel", key=f"{key_prefix}bc_m09_xuat"):
                        st.session_state[f"_{key_prefix}m09_buf"] = xuat_excel(
                            {"M09_CoKNTraNo": df_m09[cols_m09]}
                        )
                    if st.session_state.get(f"_{key_prefix}m09_buf"):
                        st.download_button(
                            "⬇️ Tải M09",
                            data=st.session_state[f"_{key_prefix}m09_buf"],
                            file_name="M09_CoKNTraNo.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_m09_dl",
                        )

            with st.expander("📊 QLNK_06 — Báo cáo kết quả kiểm tra nợ khoanh", expanded=False):
                st.markdown("**Bộ lọc**")
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    pgd_f06 = st.selectbox(
                        "PGD",
                        options=["— Tất cả —"] + (
                            sorted([r.get("ten_pgd", "") for r in rows_all_kt
                                    if r.get("ten_pgd")]) if rows_all_kt else []
                        ),
                        key=f"{key_prefix}bc_06_pgd",
                    )
                with col_f2:
                    ngay_tu_06 = st.text_input(
                        "Từ ngày (dd/mm/yyyy)",
                        key=f"{key_prefix}bc_06_tu",
                    )
                with col_f3:
                    ngay_den_06 = st.text_input(
                        "Đến ngày (dd/mm/yyyy)",
                        key=f"{key_prefix}bc_06_den",
                    )

                # Lọc dữ liệu
                df_06 = pd.DataFrame(rows_all_kt) if rows_all_kt else pd.DataFrame()
                if not df_06.empty:
                    if pgd_f06 != "— Tất cả —":
                        df_06 = df_06[df_06["ten_pgd"] == pgd_f06]

                    # Lọc ngày nếu có
                    if ngay_tu_06 or ngay_den_06:
                        from datetime import datetime as dt
                        try:
                            if ngay_tu_06:
                                tu_dt = dt.strptime(ngay_tu_06.strip(), "%d/%m/%Y").date()
                                df_06 = df_06[
                                    (df_06["ngay_kiem_tra"] >= str(tu_dt)) |
                                    (df_06["ngay_kiem_tra"].isna())
                                ]
                            if ngay_den_06:
                                den_dt = dt.strptime(ngay_den_06.strip(), "%d/%m/%Y").date()
                                df_06 = df_06[
                                    (df_06["ngay_kiem_tra"] <= str(den_dt)) |
                                    (df_06["ngay_kiem_tra"].isna())
                                ]
                        except ValueError:
                            st.warning("⚠️ Định dạng ngày không hợp lệ (dd/mm/yyyy)")

                if df_06.empty:
                    st.info("ℹ️ Không có dữ liệu kiểm tra phù hợp.")
                else:
                    st.metric("Số bản ghi", fmt_so(len(df_06)))

                    cols_06 = [c for c in [
                        "ma_mon_vay", "ten_pgd", "ten_kh", "ten_ct",
                        "du_no_goc", "du_no_goc_khoanh", "du_no_goc_thuc_te",
                        "du_no_khoanh_thuc_te", "chenh_lech",
                        "thuc_trang_du_an", "tinh_hinh_khach_hang",
                        "kha_nang_tra_no", "cam_ket_tra_no",
                        "trang_thai", "ngay_kiem_tra", "can_bo_kiem_tra",
                        "nguoi_nhap", "nguoi_phe_duyet",
                    ] if c in df_06.columns]

                    df_06_display = df_06[cols_06].copy()
                    # Format tiền
                    for col in ["du_no_goc", "du_no_goc_khoanh", "du_no_goc_thuc_te",
                                "du_no_khoanh_thuc_te", "chenh_lech"]:
                        if col in df_06_display.columns:
                            df_06_display[col] = (
                                df_06_display[col]
                                .apply(lambda x: fmt_ty(float(x) or 0) if x else "0")
                            )

                    hien_thi_dataframe_phan_trang(
                        df_06_display,
                        key=f"{key_prefix}bc_06_tbl",
                        height=350,
                    )

                    col_06_1, col_06_2 = st.columns(2)
                    with col_06_1:
                        if st.button("📥 Xuất QLNK_06 Excel", key=f"{key_prefix}bc_06_xuat"):
                            st.session_state[f"_{key_prefix}qlnk06_buf"] = xuat_excel(
                                {"QLNK_06": df_06[cols_06]}
                            )
                    with col_06_2:
                        if st.button("📄 Xuất QLNK_06 PDF", key=f"{key_prefix}bc_06_pdf"):
                            try:
                                pgd_pdf_06 = (pgd_f06 if pgd_f06 != "— Tất cả —" else "")
                                pdf_06 = _xuat_pdf_qlnk_06(
                                    df_06.to_dict("records"),
                                    ten_pgd=pgd_pdf_06,
                                    ngay_tu=ngay_tu_06,
                                    ngay_den=ngay_den_06
                                )
                                st.session_state[f"_{key_prefix}qlnk06_pdf"] = pdf_06
                            except Exception as e:
                                st.error(f"❌ Lỗi xuất PDF: {e}")

                    if st.session_state.get(f"_{key_prefix}qlnk06_buf"):
                        st.download_button(
                            "⬇️ Tải QLNK_06 Excel",
                            data=st.session_state[f"_{key_prefix}qlnk06_buf"],
                            file_name="QLNK_06.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_06_dl",
                        )
                    if st.session_state.get(f"_{key_prefix}qlnk06_pdf"):
                        st.download_button(
                            "⬇️ Tải QLNK_06 PDF",
                            data=st.session_state[f"_{key_prefix}qlnk06_pdf"],
                            file_name="QLNK_06.pdf",
                            mime="application/pdf",
                            key=f"{key_prefix}bc_06_pdf_dl",
                        )

            with st.expander("📋 M10_QLNK — Danh sách món vay chưa nhập kết quả kiểm tra"):
                rows_m10 = [
                    r for r in rows_all_kt
                    if r.get("trang_thai") == "luu_tam"
                ]
                df_m10 = pd.DataFrame(rows_m10) if rows_m10 else pd.DataFrame()
                st.metric("Số bản ghi lưu tạm", fmt_so(len(df_m10)))
                if not df_m10.empty:
                    # Chỉ show các cột quan trọng, format tiền và ngày
                    cols_m10 = [c for c in [
                        "ma_mon_vay", "ten_pgd", "ten_kh", "so_ku",
                        "du_no_goc_khoanh", "ngay_kiem_tra", "nguoi_nhap",
                    ] if c in df_m10.columns]

                    df_m10_display = df_m10[cols_m10].copy()
                    # Format cột tiền từ đồng → triệu đồng
                    if "du_no_goc_khoanh" in df_m10_display.columns:
                        df_m10_display["du_no_goc_khoanh"] = (
                            df_m10_display["du_no_goc_khoanh"]
                            .apply(lambda x: fmt_ty(float(x) or 0) if x else "0")
                        )

                    hien_thi_dataframe_phan_trang(
                        df_m10_display,
                        key=f"{key_prefix}bc_m10_tbl",
                        height=300,
                    )

                    col_ex1, col_ex2 = st.columns(2)
                    with col_ex1:
                        if st.button("📥 Xuất M10 Excel", key=f"{key_prefix}bc_m10_xuat"):
                            st.session_state[f"_{key_prefix}m10_buf"] = xuat_excel(
                                {"M10_LuuTam": df_m10[cols_m10]}
                            )
                    with col_ex2:
                        if st.button("📄 Xuất M10 PDF", key=f"{key_prefix}bc_m10_pdf"):
                            pgd_pdf = pgd_filter_bc or ""
                            try:
                                pdf_m10 = _xuat_pdf_m10(
                                    df_m10.to_dict("records"), ten_pgd=pgd_pdf
                                )
                                st.session_state[f"_{key_prefix}m10_pdf"] = pdf_m10
                            except Exception as e:
                                st.error(f"❌ Lỗi xuất PDF: {e}")

                    if st.session_state.get(f"_{key_prefix}m10_buf"):
                        st.download_button(
                            "⬇️ Tải M10 Excel",
                            data=st.session_state[f"_{key_prefix}m10_buf"],
                            file_name="M10_LuuTam.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_m10_dl",
                        )
                    if st.session_state.get(f"_{key_prefix}m10_pdf"):
                        st.download_button(
                            "⬇️ Tải M10 PDF",
                            data=st.session_state[f"_{key_prefix}m10_pdf"],
                            file_name="M10_LuuTam.pdf",
                            mime="application/pdf",
                            key=f"{key_prefix}bc_m10_pdf_dl",
                        )

            with st.expander("📊 Tiến độ kiểm tra theo PGD"):
                if not rows_all_kt:
                    st.info("ℹ️ Chưa có dữ liệu kiểm tra.")
                else:
                    df_td = pd.DataFrame(rows_all_kt)

                    if COT_TEN_PGD in df_kh.columns and COT_SO_KU in df_kh.columns:
                        tong_kh_pgd = (
                            df_kh.groupby(COT_TEN_PGD)[COT_SO_KU]
                            .nunique()
                            .rename("Tổng món KH")
                        )
                    else:
                        tong_kh_pgd = pd.Series(dtype=int, name="Tổng món KH")

                    da_pd = df_td[df_td["trang_thai"] == "da_phe_duyet"]
                    da_kt_pgd = (
                        da_pd.groupby("ten_pgd")["ma_mon_vay"]
                        .nunique()
                        .rename("Đã KT (PD)")
                    )

                    df_td_pgd = pd.concat([tong_kh_pgd, da_kt_pgd], axis=1).fillna(0)
                    df_td_pgd = df_td_pgd.astype(int)
                    df_td_pgd["Tỷ lệ%"] = df_td_pgd.apply(
                        lambda r: (
                            f"{r['Đã KT (PD)'] / r['Tổng món KH'] * 100:.1f}%".replace(".", ",")
                            if r["Tổng món KH"] > 0 else "—"
                        ),
                        axis=1,
                    )
                    df_td_pgd = df_td_pgd.reset_index().rename(
                        columns={"index": "PGD", "ten_pgd": "PGD"}
                    )

                    hien_thi_dataframe_phan_trang(
                        df_td_pgd,
                        key=f"{key_prefix}bc_td_pgd_tbl",
                        height=340,
                    )
                    if st.button(
                        "📥 Xuất tiến độ Excel",
                        key=f"{key_prefix}bc_td_xuat",
                    ):
                        st.session_state[f"_{key_prefix}td_buf"] = xuat_excel(
                            {"TienDoKiemTra": df_td_pgd}
                        )
                    if st.session_state.get(f"_{key_prefix}td_buf"):
                        st.download_button(
                            "⬇️ Tải tiến độ",
                            data=st.session_state[f"_{key_prefix}td_buf"],
                            file_name="TienDoKiemTraNK.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_td_dl",
                        )

            # ── Xuất mẫu biểu ────────────────────────────────────────────────
            st.divider()
            st.markdown("### 📄 Xuất mẫu biểu theo CV 368")

            pgd_f = pgd_filter_bc

            with st.expander("📝 Kế hoạch kiểm tra nợ khoanh", expanded=False):
                rows_kh_mb = db.doc_ke_hoach_kiem_tra(ten_pgd=pgd_f)
                if not rows_kh_mb:
                    st.info("ℹ️ Chưa có kế hoạch nào. Vào tab 📅 Kế hoạch để lập.")
                else:
                    options_kh_mb = {
                        f"ID {r['id']} — {r['ten_xa']} — {r['ngay_kiem_tra']} "
                        f"({r['trang_thai']})": r
                        for r in rows_kh_mb
                    }
                    chon_kh_mb = st.selectbox(
                        "Chọn kế hoạch",
                        list(options_kh_mb.keys()),
                        key=f"{key_prefix}mb_kh_sel",
                    )
                    kh_sel = options_kh_mb[chon_kh_mb]
                    ds_mon_kh = kh_sel.get("ds_mon_vay") or []
                    ds_mon_detail = []
                    for ku in ds_mon_kh:
                        rows_hstd_ku = (
                            df_kh[df_kh[COT_SO_KU] == ku]
                            if COT_SO_KU in df_kh.columns else pd.DataFrame()
                        )
                        bs_ku = db.doc_bo_sung_mon_vay(str(ku)) or {}
                        if not rows_hstd_ku.empty:
                            r_ku = rows_hstd_ku.iloc[0]
                            ds_mon_detail.append({
                                "ten_kh":              str(r_ku.get(COT_TEN_KH, "")),
                                "ten_to_truong":       str(r_ku.get(COT_TEN_TO, "")),
                                "ten_ct":              str(r_ku.get(COT_TEN_CT, "")),
                                "ngay_bat_dau_khoanh": bs_ku.get("ngay_bat_dau_khoanh", ""),
                                "so_thang_khoanh":     bs_ku.get("so_thang_khoanh", ""),
                                "ly_do_khoanh":        bs_ku.get("ly_do_khoanh", ""),
                            })
                    c_kh1, c_kh2 = st.columns(2)
                    with c_kh1:
                        can_bo_kt_kh = st.text_input(
                            "Cán bộ kiểm tra", username,
                            key=f"{key_prefix}mb_kh_cb",
                        )
                    with c_kh2:
                        noi_dung_kh = st.text_area(
                            "Nội dung bổ sung", max_chars=300,
                            key=f"{key_prefix}mb_kh_nd",
                        )
                    st.caption(
                        f"� {len(ds_mon_detail)} món vay trong kế hoạch "
                        f"tại {kh_sel.get('ten_xa', '')}"
                    )
                    if st.button("📥 Xuất PDF Kế hoạch KT",
                                 key=f"{key_prefix}mb_kh_tao", type="primary"):
                        try:
                            pdf_kh = _xuat_pdf_mau_kh(
                                kh_sel, ds_mon_detail,
                                can_bo_kt=can_bo_kt_kh, noi_dung=noi_dung_kh,
                            )
                            st.session_state[f"{key_prefix}mb_kh_pdf"] = pdf_kh
                            st.session_state[f"{key_prefix}mb_kh_fn"] = (
                                f"QLNK_KH_{kh_sel.get('ten_xa', '')}_"
                                f"{kh_sel.get('ngay_kiem_tra', '')}.pdf"
                            )
                        except Exception as e_kh:
                            st.error(f"❌ Lỗi tạo PDF: {e_kh}")
                    pdf_kh_data = st.session_state.get(f"{key_prefix}mb_kh_pdf")
                    if pdf_kh_data:
                        st.download_button(
                            "⬇️ Tải PDF",
                            data=pdf_kh_data,
                            file_name=st.session_state.get(f"{key_prefix}mb_kh_fn",
                                                           "QLNK_KH.pdf"),
                            mime="application/pdf",
                            key=f"{key_prefix}mb_kh_dl",
                        )

            with st.expander("📝 Mẫu 01/QLNK — Phiếu kiểm tra nợ khoanh", expanded=False):
                rows_kh_01 = db.doc_ke_hoach_kiem_tra(ten_pgd=pgd_f, trang_thai="da_duyet")
                if not rows_kh_01:
                    st.info("ℹ️ Chưa có kế hoạch đã duyệt.")
                else:
                    options_kh_01 = {
                        f"ID {r['id']} — {r['ten_xa']} — {r['ngay_kiem_tra']}": r
                        for r in rows_kh_01
                    }
                    chon_kh_01 = st.selectbox(
                        "Chọn kế hoạch",
                        list(options_kh_01.keys()),
                        key=f"{key_prefix}mb_01_sel",
                    )
                    kh_01    = options_kh_01[chon_kh_01]
                    ds_ku_01 = kh_01.get("ds_mon_vay") or []
                    rows_kq_01 = [
                        r for r in db.doc_ket_qua_kiem_tra(
                            ten_pgd=pgd_f, trang_thai="da_phe_duyet"
                        )
                        if r.get("ma_mon_vay") in ds_ku_01
                    ]
                    st.info(f"Số món đã có kết quả KT: {len(rows_kq_01)}/{len(ds_ku_01)}")
                    ket_luan_01 = st.text_area(
                        "Kết luận bổ sung", max_chars=500,
                        key=f"{key_prefix}mb_01_kl",
                    )
                    if st.button("� Xuất PDF Mẫu 01/QLNK",
                                 key=f"{key_prefix}mb_01_tao", type="primary"):
                        try:
                            pdf_01 = _xuat_pdf_mau_01qlnk(kh_01, rows_kq_01,
                                                           ket_luan=ket_luan_01)
                            st.session_state[f"{key_prefix}mb_01_pdf"] = pdf_01
                            st.session_state[f"{key_prefix}mb_01_fn"] = (
                                f"QLNK_01_{kh_01.get('ten_xa', '')}_"
                                f"{kh_01.get('ngay_kiem_tra', '')}.pdf"
                            )
                        except Exception as e_01:
                            st.error(f"❌ Lỗi tạo PDF: {e_01}")
                    pdf_01_data = st.session_state.get(f"{key_prefix}mb_01_pdf")
                    if pdf_01_data:
                        st.download_button(
                            "⬇️ Tải PDF",
                            data=pdf_01_data,
                            file_name=st.session_state.get(f"{key_prefix}mb_01_fn",
                                                           "QLNK_01.pdf"),
                            mime="application/pdf",
                            key=f"{key_prefix}mb_01_dl",
                        )

            with st.expander("📝 Mẫu 02/QLNK — Cam kết trả nợ", expanded=False):
                rows_co_kn = [
                    r for r in db.doc_ket_qua_kiem_tra(
                        ten_pgd=pgd_f, trang_thai="da_phe_duyet"
                    )
                    if r.get("kha_nang_tra_no") == "co"
                ]
                if not rows_co_kn:
                    st.info("ℹ️ Chưa có khách hàng nào được xác nhận có khả năng trả nợ.")
                else:
                    options_02 = {
                        f"{r.get('ten_kh', '')} — {r.get('ma_mon_vay', '')} "
                        f"— {r.get('ngay_kiem_tra', '')}": r
                        for r in rows_co_kn
                    }
                    chon_02 = st.selectbox(
                        "Chọn khách hàng",
                        list(options_02.keys()),
                        key=f"{key_prefix}mb_02_sel",
                    )
                    row_02 = options_02[chon_02]
                    bs_02  = db.doc_bo_sung_mon_vay(row_02.get("ma_mon_vay", "")) or {}
                    ku_02  = row_02.get("ma_mon_vay", "")
                    rows_hstd_02 = (
                        df_kh[df_kh[COT_SO_KU] == ku_02].iloc[0].to_dict()
                        if (COT_SO_KU in df_kh.columns
                            and not df_kh[df_kh[COT_SO_KU] == ku_02].empty)
                        else {}
                    )
                    row_02_merged = {**rows_hstd_02, **bs_02, **row_02}
                    c02a, c02b, c02c = st.columns(3)
                    with c02a:
                        tien_ck = st.text_input(
                            "Số tiền cam kết", key=f"{key_prefix}mb_02_tien",
                        )
                    with c02b:
                        han_ck = st.text_input(
                            "Thời hạn", key=f"{key_prefix}mb_02_han",
                        )
                    with c02c:
                        pt_ck = st.selectbox(
                            "Phương thức",
                            ["Trả 1 lần", "Trả góp", "Khác"],
                            key=f"{key_prefix}mb_02_pt",
                        )
                    if st.button("📥 Xuất PDF Mẫu 02/QLNK",
                                 key=f"{key_prefix}mb_02_tao", type="primary"):
                        try:
                            pdf_02 = _xuat_pdf_mau_02qlnk(
                                row_02_merged,
                                so_tien_cam_ket=tien_ck,
                                thoi_han=han_ck,
                                phuong_thuc=pt_ck,
                            )
                            ngay_str_02 = str(row_02.get("ngay_kiem_tra", "")).replace("/", "")
                            st.session_state[f"{key_prefix}mb_02_pdf"] = pdf_02
                            st.session_state[f"{key_prefix}mb_02_fn"] = (
                                f"QLNK_02_{row_02.get('ten_kh', '')}_{ngay_str_02}.pdf"
                            )
                        except Exception as e_02:
                            st.error(f"❌ Lỗi tạo PDF: {e_02}")
                    pdf_02_data = st.session_state.get(f"{key_prefix}mb_02_pdf")
                    if pdf_02_data:
                        st.download_button(
                            "⬇️ Tải PDF",
                            data=pdf_02_data,
                            file_name=st.session_state.get(f"{key_prefix}mb_02_fn",
                                                           "QLNK_02.pdf"),
                            mime="application/pdf",
                            key=f"{key_prefix}mb_02_dl",
                        )

            with st.expander(
                "📝 Mẫu 03/QLNK — Danh sách hết thời gian khoanh nợ", expanded=False
            ):
                if df_kh.empty:
                    st.info("ℹ️ Không có dữ liệu nợ khoanh.")
                else:
                    col_p03, col_t03 = st.columns(2)
                    with col_p03:
                        ds_pgd_03 = (
                            sorted(df_kh[COT_TEN_PGD].dropna().unique().tolist())
                            if (la_phan_he_cn(role) and COT_TEN_PGD in df_kh.columns)
                            else [pgd_user or ""]
                        )
                        pgd_03 = (
                            st.selectbox("PGD", ds_pgd_03, key=f"{key_prefix}mb_03_pgd")
                            if len(ds_pgd_03) > 1 else ds_pgd_03[0]
                        )
                    with col_t03:
                        df_03 = (
                            df_kh[df_kh[COT_TEN_PGD] == pgd_03]
                            if (COT_TEN_PGD in df_kh.columns and pgd_03)
                            else df_kh
                        )
                        ds_to_03 = (
                            sorted(df_03[COT_TEN_TO].dropna().unique().tolist())
                            if COT_TEN_TO in df_03.columns else []
                        )
                        to_03 = st.selectbox(
                            "Tổ TK&VV",
                            ["— Tất cả —"] + ds_to_03,
                            key=f"{key_prefix}mb_03_to",
                        )
                    if to_03 != "— Tất cả —" and COT_TEN_TO in df_03.columns:
                        df_03 = df_03[df_03[COT_TEN_TO] == to_03]

                    # Lọc < 120 ngày trước hết hạn
                    col_nd03, col_ck03 = st.columns([2, 3])
                    with col_nd03:
                        ngay_tinh_03 = st.date_input(
                            "Ngày tính",
                            value=datetime.now().date(),
                            key=f"{key_prefix}mb_03_ngay",
                        )
                    with col_ck03:
                        loc_120 = st.checkbox(
                            "Chỉ lấy món hết hạn trong vòng 120 ngày",
                            value=True,
                            key=f"{key_prefix}mb_03_loc120",
                        )
                    if loc_120 and COT_NGAY_HH_KHOANH in df_03.columns:
                        _ref = pd.Timestamp(ngay_tinh_03)
                        _hh  = pd.to_datetime(df_03[COT_NGAY_HH_KHOANH], dayfirst=True, errors="coerce")
                        df_03 = df_03[(_hh - _ref).dt.days < 120].copy()

                    st.info(f"**{len(df_03)} món** trong phạm vi đã chọn.")

                    # Thông tin bổ sung cho mẫu
                    c03a, c03b = st.columns(2)
                    with c03a:
                        tu_ngay_03  = st.text_input("Từ ngày", placeholder="dd/mm/yyyy",
                                                    key=f"{key_prefix}mb_03_tu")
                        ma_to_03    = st.text_input("Mã tổ", key=f"{key_prefix}mb_03_ma_to")
                    with c03b:
                        den_ngay_03 = st.text_input("Đến ngày", placeholder="dd/mm/yyyy",
                                                    key=f"{key_prefix}mb_03_den")
                        dvut_03     = st.text_input("Đơn vị ủy thác",
                                                    key=f"{key_prefix}mb_03_dvut")

                    if st.button("📄 Xuất PDF Mẫu 03/QLNK",
                                 key=f"{key_prefix}mb_03_tao", type="primary"):
                        try:
                            ten_to_03 = to_03 if to_03 != "— Tất cả —" else ""
                            pdf_03 = _xuat_pdf_mau_03qlnk(
                                pgd_03 or "", ten_to_03,
                                df_03.to_dict("records"),
                                tu_ngay=tu_ngay_03,
                                den_ngay=den_ngay_03,
                                ma_to=ma_to_03,
                                don_vi_uy_thac=dvut_03,
                            )
                            st.session_state[f"{key_prefix}mb_03_pdf"] = pdf_03
                            st.session_state[f"{key_prefix}mb_03_fn"] = (
                                f"QLNK_03_{pgd_03}_{ten_to_03}.pdf"
                            )
                        except Exception as e_03:
                            st.error(f"❌ Lỗi tạo PDF: {e_03}")
                    pdf_03_data = st.session_state.get(f"{key_prefix}mb_03_pdf")
                    if pdf_03_data:
                        st.download_button(
                            "⬇️ Tải PDF",
                            data=pdf_03_data,
                            file_name=st.session_state.get(f"{key_prefix}mb_03_fn",
                                                           "QLNK_03.pdf"),
                            mime="application/pdf",
                            key=f"{key_prefix}mb_03_dl",
                        )

            with st.expander(
                "📝 Mẫu 04/QLNK — Thông báo hết thời gian khoanh nợ", expanded=False
            ):
                if df_kh.empty or COT_SO_KU not in df_kh.columns:
                    st.info("ℹ️ Không có dữ liệu nợ khoanh.")
                else:
                    options_04 = {
                        f"{r.get(COT_TEN_KH, '')} — {r.get(COT_SO_KU, '')}": r.to_dict()
                        for _, r in df_kh.iterrows()
                        if r.get(COT_SO_KU)
                    }
                    chon_04 = st.selectbox(
                        "Chọn khách hàng",
                        list(options_04.keys()),
                        key=f"{key_prefix}mb_04_sel",
                    )
                    row_04_hstd = options_04[chon_04]
                    ku_04 = str(row_04_hstd.get(COT_SO_KU, ""))
                    bs_04 = db.doc_bo_sung_mon_vay(ku_04) or {}
                    ten_pgd_04 = (
                        str(row_04_hstd.get(COT_TEN_PGD, pgd_user or ""))
                        if COT_TEN_PGD in row_04_hstd else (pgd_user or "")
                    )
                    noi_dung_04 = st.text_area(
                        "Nội dung thông báo bổ sung", max_chars=500,
                        key=f"{key_prefix}mb_04_nd",
                    )
                    han_cuoi_04 = st.text_input(
                        "Hạn cuối trả nợ",
                        key=f"{key_prefix}mb_04_hc",
                    )
                    if st.button("� Xuất PDF Mẫu 04/QLNK",
                                 key=f"{key_prefix}mb_04_tao", type="primary"):
                        try:
                            pdf_04 = _xuat_pdf_mau_04qlnk(
                                row_04_hstd, bs_04, ten_pgd_04,
                                noi_dung=noi_dung_04, han_cuoi=han_cuoi_04,
                            )
                            st.session_state[f"{key_prefix}mb_04_pdf"] = pdf_04
                            st.session_state[f"{key_prefix}mb_04_fn"] = (
                                f"QLNK_04_{row_04_hstd.get(COT_TEN_KH, '')}_{ku_04}.pdf"
                            )
                        except Exception as e_04:
                            st.error(f"❌ Lỗi tạo PDF: {e_04}")
                    pdf_04_data = st.session_state.get(f"{key_prefix}mb_04_pdf")
                    if pdf_04_data:
                        st.download_button(
                            "⬇️ Tải PDF",
                            data=pdf_04_data,
                            file_name=st.session_state.get(f"{key_prefix}mb_04_fn",
                                                           "QLNK_04.pdf"),
                            mime="application/pdf",
                            key=f"{key_prefix}mb_04_dl",
                        )
