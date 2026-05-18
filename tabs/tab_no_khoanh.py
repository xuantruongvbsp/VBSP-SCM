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
from utils import fmt_so, fmt_ty, hien_thi_dataframe_phan_trang, xuat_excel
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


# ─── Word helpers (QLNK theo CV 368) ─────────────────────────────────────────

def _qlnk_doc() -> _Document:
    doc = _Document()
    s = doc.sections[0]
    s.top_margin = _Cm(2); s.bottom_margin = _Cm(2)
    s.left_margin = _Cm(3); s.right_margin = _Cm(2)
    doc.styles['Normal'].font.name = 'Times New Roman'
    doc.styles['Normal'].font.size = _Pt(12)
    return doc


def _qlnk_run(p, text: str, bold=False, italic=False, size=12):
    run = p.add_run(str(text))
    run.font.name = 'Times New Roman'
    run.font.size = _Pt(size)
    run.bold = bold
    run.italic = italic
    return run


def _qlnk_par(container, text="", bold=False, italic=False, size=12, align=None):
    p = container.add_paragraph()
    if text:
        _qlnk_run(p, text, bold=bold, italic=italic, size=size)
    if align:
        p.alignment = align
    return p


def _qlnk_cell(cell, text="", bold=False, italic=False, size=11, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    _qlnk_run(p, str(text), bold=bold, italic=italic, size=size)
    if align:
        p.alignment = align


def _qlnk_bg(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = _OxmlElem('w:shd')
    shd.set(_qn('w:val'), 'clear')
    shd.set(_qn('w:color'), 'auto')
    shd.set(_qn('w:fill'), hex_color)
    tcPr.append(shd)


def _qlnk_no_border(tbl):
    tblPr = tbl._tbl.get_or_add_tblPr()
    tblBorders = _OxmlElem('w:tblBorders')
    for nm in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        b = _OxmlElem(f'w:{nm}')
        b.set(_qn('w:val'), 'none')
        b.set(_qn('w:sz'), '0')
        b.set(_qn('w:space'), '0')
        b.set(_qn('w:color'), 'auto')
        tblBorders.append(b)
    tblPr.append(tblBorders)


def _qlnk_header2col(doc, tren: str, duoi: str):
    """Header 2 cột: đơn vị (trái) | quốc hiệu (phải)."""
    tbl = doc.add_table(rows=1, cols=2)
    tbl.style = 'Table Grid'
    _qlnk_no_border(tbl)
    cl, cr = tbl.rows[0].cells

    cl.text = ""
    for line, bold in [(tren, True), (duoi, False), ("─────────────────────", False)]:
        p = cl.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = _Pt(12)
            p.runs[0].bold = bold
        p.alignment = _WD_ALIGN.CENTER

    cr.text = ""
    for line, bold, italic in [
        ("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM", True, False),
        ("Độc lập - Tự do - Hạnh phúc", False, True),
        ("─────────────────────", False, False),
    ]:
        p = cr.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = _Pt(12)
            p.runs[0].bold = bold
            p.runs[0].italic = italic
        p.alignment = _WD_ALIGN.CENTER


def _qlnk_sig(doc, titles: list):
    """Khối chữ ký N cột."""
    tbl = doc.add_table(rows=1, cols=len(titles))
    tbl.style = 'Table Grid'
    _qlnk_no_border(tbl)
    for cell, title in zip(tbl.rows[0].cells, titles):
        cell.text = ""
        p1 = cell.add_paragraph(title)
        if p1.runs:
            p1.runs[0].font.name = 'Times New Roman'
            p1.runs[0].font.size = _Pt(12)
            p1.runs[0].bold = True
        p1.alignment = _WD_ALIGN.CENTER
        for _ in range(4):
            pb = cell.add_paragraph()
            pb.alignment = _WD_ALIGN.CENTER
        p_ky = cell.add_paragraph("(Ký, ghi rõ họ tên)")
        if p_ky.runs:
            p_ky.runs[0].font.name = 'Times New Roman'
            p_ky.runs[0].font.size = _Pt(11)
            p_ky.runs[0].italic = True
        p_ky.alignment = _WD_ALIGN.CENTER


def _qlnk_add_months(dt_str: str, months: int) -> str:
    """Cộng số tháng vào ngày dd/mm/yyyy → dd/mm/yyyy."""
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
    """VND → ngàn đồng (chỉ số, không kèm đơn vị)."""
    try:
        return f"{int(round(float(val) / 1000)):,}"
    except (TypeError, ValueError):
        return "............"


def _qlnk_bytes(doc) -> bytes:
    buf = _io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _tao_word_ke_hoach_kt(ke_hoach: dict, ds_mon_vay: list) -> bytes:
    """Tạo Word Kế hoạch kiểm tra nợ khoanh."""
    doc = _qlnk_doc()
    ten_pgd    = ke_hoach.get("ten_pgd")       or "............"
    ten_xa     = ke_hoach.get("ten_xa")        or "............"
    ngay_kt    = ke_hoach.get("ngay_kiem_tra") or "............"
    thanh_phan = ke_hoach.get("thanh_phan")    or []

    _qlnk_header2col(doc,
                     tren=f"PHÒNG GIAO DỊCH {ten_pgd.upper()}",
                     duoi="TỔ TÍN DỤNG")
    _qlnk_par(doc)
    _qlnk_par(doc, "KẾ HOẠCH KIỂM TRA KHOANH NỢ",
              bold=True, size=14, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc, "(Theo CV 368/NHCS-QLN ngày 17/01/2024)",
              italic=True, size=11, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc)

    p_kg = doc.add_paragraph()
    _qlnk_run(p_kg, "Kính gửi: ", bold=True)
    _qlnk_run(p_kg, f"Giám đốc Phòng giao dịch {ten_pgd}")
    _qlnk_par(doc)

    for cb_text in [
        "Căn cứ Công văn số 368/NHCS-QLN ngày 17/01/2024 của Ngân hàng Chính sách xã hội "
        "về việc hướng dẫn quản lý nợ khoanh;",
        "Căn cứ kết quả rà soát các khoản nợ khoanh tại đơn vị;",
    ]:
        p = doc.add_paragraph(cb_text)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
    _qlnk_par(doc)

    _qlnk_par(doc, "I. NỘI DUNG KIỂM TRA", bold=True)
    p_tg = doc.add_paragraph(f"1. Thời gian kiểm tra: Ngày {ngay_kt} tại {ten_xa}, {ten_pgd}")
    if p_tg.runs:
        p_tg.runs[0].font.name = 'Times New Roman'

    p_tp = doc.add_paragraph("2. Thành phần đoàn kiểm tra:")
    if p_tp.runs:
        p_tp.runs[0].font.name = 'Times New Roman'
    for tp in (thanh_phan or [{"Họ và tên": "............", "Chức vụ/Đơn vị": "............"}]):
        ten  = tp.get("Họ và tên") or tp.get("ten")     or "............"
        chuc = tp.get("Chức vụ/Đơn vị") or tp.get("chuc_vu") or "............"
        pt = doc.add_paragraph(f"    - {ten}, {chuc}")
        if pt.runs:
            pt.runs[0].font.name = 'Times New Roman'

    p_dt = doc.add_paragraph("3. Đối tượng kiểm tra:")
    if p_dt.runs:
        p_dt.runs[0].font.name = 'Times New Roman'

    headers_kh = [
        "STT", "Khách hàng", "Tổ trưởng", "Chương trình vay",
        "Ngày BĐ khoanh", "Thời gian khoanh", "Lý do khoanh nợ",
    ]
    tbl_kh = doc.add_table(rows=1, cols=len(headers_kh))
    tbl_kh.style = 'Table Grid'
    for i, h in enumerate(headers_kh):
        _qlnk_cell(tbl_kh.rows[0].cells[i], h, bold=True, size=10, align=_WD_ALIGN.CENTER)
        _qlnk_bg(tbl_kh.rows[0].cells[i], "D9D9D9")

    for idx, mon in enumerate(ds_mon_vay or [], 1):
        r = tbl_kh.add_row()
        ly_do_ma = mon.get("ly_do_khoanh", "")
        ly_do_hl = LY_DO_KHOANH_LABEL.get(ly_do_ma, ly_do_ma or "............")
        st_val   = mon.get("so_thang_khoanh")
        vals = [
            str(idx),
            mon.get("ten_kh")              or "............",
            mon.get("ten_to_truong")       or "............",
            mon.get("ten_ct")              or "............",
            mon.get("ngay_bat_dau_khoanh") or "............",
            (f"{st_val} tháng" if st_val else "............"),
            ly_do_hl,
        ]
        for i, v in enumerate(vals):
            _qlnk_cell(r.cells[i], v, size=10,
                       align=_WD_ALIGN.CENTER if i == 0 else None)

    _qlnk_par(doc)
    _qlnk_sig(doc, ["Người lập kế hoạch", "Giám Đốc"])
    return _qlnk_bytes(doc)


def _tao_word_01qlnk(ke_hoach: dict, ds_ket_qua: list) -> bytes:
    """Tạo Phiếu kiểm tra nợ khoanh (Mẫu số 01/QLNK)."""
    doc = _qlnk_doc()
    ten_pgd    = ke_hoach.get("ten_pgd")       or "............"
    ten_xa     = ke_hoach.get("ten_xa")        or "............"
    ngay_kt    = ke_hoach.get("ngay_kiem_tra") or "............"
    thanh_phan = ke_hoach.get("thanh_phan")    or []

    hdr = doc.add_table(rows=1, cols=2)
    hdr.style = 'Table Grid'
    _qlnk_no_border(hdr)
    cl, cr = hdr.rows[0].cells

    cl.text = ""
    for line, bold in [
        ("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI TỈNH", True),
        (f"PHÒNG GIAO DỊCH {ten_pgd.upper()}", True),
        ("─────────────────────", False),
    ]:
        p = cl.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = _Pt(12)
            p.runs[0].bold = bold
        p.alignment = _WD_ALIGN.CENTER

    cr.text = ""
    p_ms = cr.add_paragraph("Mẫu số: 01/QLNK")
    if p_ms.runs:
        p_ms.runs[0].font.name = 'Times New Roman'
        p_ms.runs[0].italic = True
    p_ms.alignment = _WD_ALIGN.RIGHT

    _qlnk_par(doc)
    _qlnk_par(doc, "PHIẾU KIỂM TRA NỢ KHOANH",
              bold=True, size=14, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc, "(Đơn vị tính: ngàn đồng)",
              italic=True, size=11, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc)

    cb_list = [
        (tp.get("Họ và tên") or "............",
         tp.get("Chức vụ/Đơn vị") or "............")
        for tp in (thanh_phan or [{}])
    ]
    p_tt = doc.add_paragraph(
        "Tổ trưởng: ............    Tổ chức Chính trị - Xã hội: ............"
    )
    if p_tt.runs:
        p_tt.runs[0].font.name = 'Times New Roman'
    for i, (ten, chuc) in enumerate(cb_list[:2]):
        prefix = "Họ và tên cán bộ kiểm tra: 1." if i == 0 else f"{'':>42}2."
        p_cb = doc.add_paragraph(f"{prefix} {ten}    Chức vụ: {chuc}")
        if p_cb.runs:
            p_cb.runs[0].font.name = 'Times New Roman'
    p_tb = doc.add_paragraph(
        f"Thời điểm kiểm tra: {ngay_kt}    Địa bàn kiểm tra: {ten_xa}"
    )
    if p_tb.runs:
        p_tb.runs[0].font.name = 'Times New Roman'
    _qlnk_par(doc)

    # Bảng 17 cột với 2 dòng header
    N = 17
    tbl = doc.add_table(rows=2, cols=N)
    tbl.style = 'Table Grid'
    hdr0, hdr1 = tbl.rows[0], tbl.rows[1]

    for ci, label in enumerate(["STT", "Họ và tên", "Mã món vay"]):
        hdr0.cells[ci].merge(hdr1.cells[ci])
        _qlnk_cell(hdr0.cells[ci], label, bold=True, size=9, align=_WD_ALIGN.CENTER)
        _qlnk_bg(hdr0.cells[ci], "D9D9D9")

    hdr0.cells[3].merge(hdr0.cells[7])
    _qlnk_cell(hdr0.cells[3], "PHẦN THEO DÕI TẠI NH",
               bold=True, size=9, align=_WD_ALIGN.CENTER)
    _qlnk_bg(hdr0.cells[3], "D9D9D9")

    hdr0.cells[8].merge(hdr0.cells[16])
    _qlnk_cell(hdr0.cells[8], "PHẦN KIỂM TRA THỰC TẾ TẠI KHÁCH HÀNG",
               bold=True, size=9, align=_WD_ALIGN.CENTER)
    _qlnk_bg(hdr0.cells[8], "D9D9D9")

    sub_h = [
        "Dư nợ gốc", "Dư nợ gốc khoanh", "Số tiền lãi còn nợ NH",
        "Ngày BĐ khoanh", "Ngày hết hạn khoanh",
        "Dư nợ gốc", "Dư gốc khoanh", "Số tiền lãi còn nợ NH",
        "Thực trạng DA", "Tình hình KH", "Khả năng TN",
        "KH cam kết TN", "Chênh lệch", "Ký xác nhận KH",
    ]
    for i, h in enumerate(sub_h):
        c = hdr1.cells[i + 3]
        _qlnk_cell(c, h, bold=True, size=9, align=_WD_ALIGN.CENTER)
        _qlnk_bg(c, "D9D9D9")

    for stt, r in enumerate(ds_ket_qua or [], 1):
        bdk      = r.get("ngay_bat_dau_khoanh") or ""
        so_thang = r.get("so_thang_khoanh")
        ngay_hh  = (_qlnk_add_months(bdk, int(so_thang))
                    if (bdk and so_thang) else "............")
        dr = tbl.add_row()
        vals = [
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
        ]
        for i, v in enumerate(vals):
            _qlnk_cell(dr.cells[i], v, size=9,
                       align=_WD_ALIGN.CENTER if i == 0 else None)

    _qlnk_par(doc)
    p_nx = doc.add_paragraph(
        "Kiểm tra thực tế được ..... Khách hàng; Số tiền ............"
    )
    if p_nx.runs:
        p_nx.runs[0].font.name = 'Times New Roman'
    _qlnk_par(doc)
    _qlnk_sig(doc, [
        "ĐẠI DIỆN NHCSXH",
        "BQL TỔ TK&VV",
        "ĐẠI DIỆN CT-XH",
        "TRƯỞNG THÔN",
        "ĐẠI DIỆN UBND",
    ])
    return _qlnk_bytes(doc)


def _tao_word_02qlnk(row: dict) -> bytes:
    """Tạo Cam kết trả nợ (Mẫu số 02/QLNK)."""
    doc = _qlnk_doc()

    hdr = doc.add_table(rows=1, cols=2)
    hdr.style = 'Table Grid'
    _qlnk_no_border(hdr)
    cl, cr = hdr.rows[0].cells

    cl.text = ""
    p_ms = cl.add_paragraph("Mẫu số: 02/QLNK")
    if p_ms.runs:
        p_ms.runs[0].font.name = 'Times New Roman'
        p_ms.runs[0].italic = True

    cr.text = ""
    for line, bold, italic in [
        ("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM", True, False),
        ("Độc lập - Tự do - Hạnh phúc", False, True),
        ("─────────────────────", False, False),
        ("..............., ngày ..... tháng ..... năm .....", False, True),
    ]:
        p = cr.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = _Pt(12)
            p.runs[0].bold = bold
            p.runs[0].italic = italic
        p.alignment = _WD_ALIGN.CENTER

    _qlnk_par(doc)
    _qlnk_par(doc, "CAM KẾT TRẢ NỢ", bold=True, size=14, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc)

    p_kg = doc.add_paragraph()
    _qlnk_run(p_kg, "Kính gửi: ", bold=True)
    _qlnk_run(p_kg, "Ngân hàng Chính sách xã hội")
    _qlnk_par(doc)

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

    for line in [
        f"Tôi tên: {ten_kh}    Năm sinh: ............    SĐT: ............",
        f"Số CCCD/CMND: {so_cccd}    Địa chỉ: {dia_chi}",
        f"Thành viên Tổ TK&VV: {ten_to}",
        f"Theo HĐTD số: {so_ku}",
        f"Hiện còn nợ số tiền: {tong_no:,.0f} đồng "
        f"(gốc: {du_goc_f:,.0f} đồng, lãi: {lai_f:,.0f} đồng)",
        "",
        "Tôi cam kết sẽ trả nợ cho Ngân hàng theo kế hoạch cụ thể:",
        "    - Thời gian: ............",
        "    - Số tiền: ............",
        "    - Địa điểm: ............",
        "",
        "Tôi xin cam kết thực hiện đúng như trên.",
    ]:
        p = doc.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'

    _qlnk_par(doc)
    _qlnk_sig(doc, [
        "Người vay",
        "ĐD BQL Tổ TK&VV",
        "ĐD CT-XH/Trưởng thôn",
        "ĐD NHCSXH",
    ])
    return _qlnk_bytes(doc)


def _tao_word_03qlnk(ten_pgd: str, ten_to: str, ds_het_han: list) -> bytes:
    """Tạo Danh sách món vay hết thời gian khoanh nợ (Mẫu số 03/QLNK)."""
    doc = _qlnk_doc()

    hdr = doc.add_table(rows=1, cols=2)
    hdr.style = 'Table Grid'
    _qlnk_no_border(hdr)
    cl, cr = hdr.rows[0].cells

    cl.text = ""
    for line, bold in [
        ("CHI NHÁNH NHCSXH TỈNH ĐỒNG NAI", True),
        (f"PHÒNG GIAO DỊCH {(ten_pgd or '').upper()}", True),
        ("─────────────────────", False),
    ]:
        p = cl.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = _Pt(12)
            p.runs[0].bold = bold
        p.alignment = _WD_ALIGN.CENTER

    cr.text = ""
    p_ms = cr.add_paragraph("Mẫu số: 03/QLNK")
    if p_ms.runs:
        p_ms.runs[0].font.name = 'Times New Roman'
        p_ms.runs[0].italic = True
    p_ms.alignment = _WD_ALIGN.RIGHT

    _qlnk_par(doc)
    _qlnk_par(doc, "DANH SÁCH MÓN VAY HẾT THỜI GIAN KHOANH NỢ",
              bold=True, size=14, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc, "(Đơn vị tính: đồng)", italic=True, size=11, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc)

    for line in [
        "Từ ngày ............  đến ngày ............",
        f"Tên tổ trưởng: {ten_to or '............'}    Mã tổ: ............",
    ]:
        p = doc.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
    _qlnk_par(doc)

    headers03 = [
        "STT", "Khách hàng", "Mã món vay",
        "Ngày được khoanh nợ", "Ngày hết hạn khoanh",
        "Nợ gốc hết hạn khoanh (đồng)", "Ngày đến hạn trả nợ cuối cùng",
    ]
    tbl = doc.add_table(rows=1, cols=len(headers03))
    tbl.style = 'Table Grid'
    for i, h in enumerate(headers03):
        _qlnk_cell(tbl.rows[0].cells[i], h, bold=True, size=10, align=_WD_ALIGN.CENTER)
        _qlnk_bg(tbl.rows[0].cells[i], "D9D9D9")

    tong_no_goc = 0
    for stt, row in enumerate(ds_het_han or [], 1):
        dr = tbl.add_row()
        du_no = row.get(COT_DU_NO_KHOANH) or row.get("du_no_goc_khoanh") or 0
        try:
            du_no_f = float(du_no)
        except (TypeError, ValueError):
            du_no_f = 0
        tong_no_goc += du_no_f
        bdk   = row.get("ngay_bat_dau_khoanh") or "............"
        so_th = row.get("so_thang_khoanh")
        hh    = (_qlnk_add_months(bdk, int(so_th))
                 if (bdk != "............" and so_th) else "............")
        vals = [
            str(stt),
            row.get(COT_TEN_KH) or row.get("ten_kh") or "............",
            row.get(COT_SO_KU)  or row.get("ma_mon_vay") or "............",
            bdk,
            hh,
            f"{du_no_f:,.0f}",
            row.get(COT_NGAY_DH) or row.get("ngay_den_han") or "............",
        ]
        for i, v in enumerate(vals):
            _qlnk_cell(dr.cells[i], v, size=10,
                       align=_WD_ALIGN.CENTER if i == 0 else None)

    r_cong = tbl.add_row()
    _qlnk_cell(r_cong.cells[0], "Cộng:", bold=True, size=10, align=_WD_ALIGN.CENTER)
    _qlnk_cell(r_cong.cells[5], f"{tong_no_goc:,.0f}", bold=True, size=10)

    _qlnk_par(doc)
    _qlnk_sig(doc, ["Lập biểu", "Kiểm soát", "Giám đốc"])
    return _qlnk_bytes(doc)


def _tao_word_04qlnk(row_hstd: dict, row_bs: dict, ten_pgd: str) -> bytes:
    """Tạo Thông báo nợ hết thời gian khoanh nợ (Mẫu số 04/QLNK)."""
    doc = _qlnk_doc()

    hdr = doc.add_table(rows=1, cols=2)
    hdr.style = 'Table Grid'
    _qlnk_no_border(hdr)
    cl, cr = hdr.rows[0].cells

    cl.text = ""
    for line, bold in [
        ("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI", True),
        (f"CHI NHÁNH / PGD {(ten_pgd or '').upper()}", True),
        ("─────────────────────", False),
    ]:
        p = cl.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = _Pt(12)
            p.runs[0].bold = bold
        p.alignment = _WD_ALIGN.CENTER

    cr.text = ""
    p_ms = cr.add_paragraph("Mẫu số: 04/QLNK")
    if p_ms.runs:
        p_ms.runs[0].font.name = 'Times New Roman'
        p_ms.runs[0].italic = True
    p_ms.alignment = _WD_ALIGN.RIGHT

    _qlnk_par(doc)
    _qlnk_par(doc, "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM",
              bold=True, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc, "Độc lập - Tự do - Hạnh phúc",
              italic=True, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc, "─────────────────────", align=_WD_ALIGN.CENTER)
    _qlnk_par(doc, "..............., ngày ..... tháng ..... năm .....",
              italic=True, align=_WD_ALIGN.RIGHT)
    _qlnk_par(doc)
    _qlnk_par(doc, "THÔNG BÁO NỢ HẾT THỜI GIAN KHOANH NỢ",
              bold=True, size=14, align=_WD_ALIGN.CENTER)
    _qlnk_par(doc)

    ten_kh  = row_hstd.get(COT_TEN_KH) or row_hstd.get("ten_kh") or "............"
    dia_chi = row_hstd.get(COT_TEN_XA) or row_hstd.get("dia_chi") or "............"

    p_kg = doc.add_paragraph()
    _qlnk_run(p_kg, "Kính gửi: ", bold=True)
    _qlnk_run(p_kg, f"Ông/Bà {ten_kh}, địa chỉ: {dia_chi}")
    _qlnk_par(doc)

    so_qd    = row_bs.get("so_quyet_dinh_khoanh") or "............"
    bdk      = row_bs.get("ngay_bat_dau_khoanh")  or "............"
    so_thang = row_bs.get("so_thang_khoanh")
    ngay_hh  = (_qlnk_add_months(bdk, int(so_thang))
                if (bdk != "............" and so_thang) else "............")

    du_goc = row_hstd.get(COT_DU_NO_KHOANH) or row_hstd.get("du_no_goc_khoanh") or 0
    lai    = row_hstd.get("Lãi tồn TH") or row_hstd.get("so_tien_lai_con_no") or 0
    try:
        du_goc_f = float(du_goc)
        lai_f    = float(lai)
        tong_no  = du_goc_f + lai_f
    except (TypeError, ValueError):
        du_goc_f = lai_f = tong_no = 0

    for line in [
        f"Căn cứ Quyết định số {so_qd} của Hội đồng quản trị "
        "Ngân hàng Chính sách xã hội;",
        "",
        f"Ngân hàng Chính sách xã hội thông báo khoản vay có số tiền vay "
        f"được khoanh nợ của Ông/Bà hết thời gian khoanh nợ vào ngày {ngay_hh}.",
        "",
        f"Tổng số dư nợ: {tong_no:,.0f} đồng, trong đó gốc: {du_goc_f:,.0f} đồng, "
        f"lãi: {lai_f:,.0f} đồng.",
        "",
        "Ngân hàng Chính sách xã hội sẽ tiếp tục thực hiện tính lãi của khoản vay "
        "theo thỏa thuận trong Hợp đồng tín dụng kể từ ngày hết thời gian khoanh nợ.",
        "",
        "Ngân hàng Chính sách xã hội thông báo để Ông/Bà biết và chuẩn bị nguồn "
        "trả nợ cho Ngân hàng.",
    ]:
        p = doc.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'

    _qlnk_par(doc)

    sig_tbl = doc.add_table(rows=1, cols=2)
    sig_tbl.style = 'Table Grid'
    _qlnk_no_border(sig_tbl)

    nr_cell = sig_tbl.rows[0].cells[0]
    nr_cell.text = ""
    for line, bold in [("Nơi nhận:", True), ("- Như kính gửi;", False), ("- Lưu.", False)]:
        p = nr_cell.add_paragraph(line)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = _Pt(12)
            p.runs[0].bold = bold

    gd_cell = sig_tbl.rows[0].cells[1]
    gd_cell.text = ""
    for text, bold, italic in [
        ("GIÁM ĐỐC", True, False),
        ("", False, False), ("", False, False), ("", False, False), ("", False, False),
        ("(Ký, đóng dấu, ghi rõ họ tên)", False, True),
    ]:
        p = gd_cell.add_paragraph(text)
        if p.runs:
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = _Pt(12)
            p.runs[0].bold = bold
            p.runs[0].italic = italic
        p.alignment = _WD_ALIGN.CENTER

    return _qlnk_bytes(doc)


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

    ctx = tab if tab is not None else st.container()
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

        # ── KPI tổng quan ─────────────────────────────────────────────────
        tong_du_no = (
            pd.to_numeric(use_df[COT_TONG_DU_NO], errors="coerce").sum()
            if COT_TONG_DU_NO in use_df.columns else 0
        )
        tong_khoanh = (
            pd.to_numeric(use_df[COT_DU_NO_KHOANH], errors="coerce").fillna(0).sum()
        )
        so_mon = (
            df_kh[COT_SO_KU].nunique() if (not df_kh.empty and COT_SO_KU in df_kh.columns)
            else len(df_kh)
        )
        so_ho = (
            df_kh[COT_MA_KH].nunique() if (not df_kh.empty and COT_MA_KH in df_kh.columns)
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

        if df_kh.empty:
            st.success("✅ Hiện không có món vay nào đang khoanh nợ.")
            return

        st.divider()

        # ── Lọc PGD (CN only) ─────────────────────────────────────────────
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

        # ── Heatmap đáo hạn ───────────────────────────────────────────────
        _heatmap_dao_han(df_kh, key=f"{key_prefix}khoanh_hm")

        st.divider()

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
            co_quyen_nhap  = perms.get("upload") or perms.get("nhap_ke_hoach")
            co_quyen_duyet = la_phan_he_cn(role) or co_quyen_upload_pgd(role)
            pgd_filter_kh  = None if la_phan_he_cn(role) else pgd_user

            # ── A: Form lập kế hoạch ──────────────────────────────────────────
            with st.expander("➕ Lập kế hoạch kiểm tra mới", expanded=False):
                if not co_quyen_nhap:
                    st.warning("⚠️ Bạn không có quyền lập kế hoạch kiểm tra.")
                else:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        # Danh sách xã từ df_kh (đã lọc du_no_khoanh > 0)
                        ds_xa = sorted(df_kh[COT_TEN_XA].dropna().unique().tolist()) \
                                if COT_TEN_XA in df_kh.columns else []
                        xa_chon = st.selectbox(
                            "Xã/Phường *",
                            ["— Chọn —"] + ds_xa,
                            key=f"{key_prefix}kh_xa",
                        )
                    with c2:
                        # Lọc tổ TK&VV theo xã đã chọn
                        if xa_chon != "— Chọn —" and COT_TEN_TO in df_kh.columns:
                            ds_to = sorted(
                                df_kh[df_kh[COT_TEN_XA] == xa_chon][COT_TEN_TO]
                                .dropna().unique().tolist()
                            )
                        else:
                            ds_to = []
                        to_chon = st.selectbox(
                            "Tổ TK&VV",
                            ["— Tất cả —"] + ds_to,
                            key=f"{key_prefix}kh_to",
                        )
                    with c3:
                        ngay_kh = st.date_input(
                            "Ngày kiểm tra dự kiến *",
                            key=f"{key_prefix}kh_ngay",
                        )

                    # Thành phần đoàn kiểm tra
                    st.markdown("**Thành phần đoàn kiểm tra**")
                    df_tp_default = pd.DataFrame([
                        {"Họ và tên": username, "Chức vụ/Đơn vị": "CBTD"},
                        {"Họ và tên": "",       "Chức vụ/Đơn vị": ""},
                    ])
                    df_tp = st.data_editor(
                        df_tp_default,
                        num_rows="dynamic",
                        key=f"{key_prefix}kh_thanh_phan",
                        use_container_width=True,
                    )

                    # Chọn món vay đưa vào kế hoạch
                    st.markdown("**Chọn món vay kiểm tra**")
                    df_loc_kh = df_kh.copy()
                    if xa_chon != "— Chọn —" and COT_TEN_XA in df_loc_kh.columns:
                        df_loc_kh = df_loc_kh[df_loc_kh[COT_TEN_XA] == xa_chon]
                    if to_chon != "— Tất cả —" and COT_TEN_TO in df_loc_kh.columns:
                        df_loc_kh = df_loc_kh[df_loc_kh[COT_TEN_TO] == to_chon]

                    if df_loc_kh.empty or COT_SO_KU not in df_loc_kh.columns:
                        st.info("ℹ️ Không có món vay khoanh nào trong phạm vi đã chọn.")
                        ds_chon = []
                    else:
                        # Label: "TênKH — SốKU — LýDoKhoanh"
                        def _label_mon(row):
                            bs = db.doc_bo_sung_mon_vay(str(row.get(COT_SO_KU, "")))
                            ly_do_ma = bs.get("ly_do_khoanh", "") if bs else ""
                            ly_do_str = LY_DO_KHOANH_LABEL.get(ly_do_ma, "Chưa xác định lý do")
                            return (
                                f"{row.get(COT_TEN_KH, '')} — "
                                f"{row.get(COT_SO_KU, '')} — "
                                f"{ly_do_str}"
                            )
                        options_mon = df_loc_kh.apply(_label_mon, axis=1).tolist()
                        ku_list     = df_loc_kh[COT_SO_KU].tolist()
                        label_to_ku = dict(zip(options_mon, ku_list))

                        chon_labels = st.multiselect(
                            f"Chọn món vay ({len(df_loc_kh)} món trong phạm vi)",
                            options=options_mon,
                            key=f"{key_prefix}kh_ds_mon",
                        )
                        ds_chon = [label_to_ku[l] for l in chon_labels]

                    ghi_chu_kh = st.text_area(
                        "Ghi chú",
                        key=f"{key_prefix}kh_ghi_chu",
                        max_chars=500,
                    )

                    col_b1, col_b2, _ = st.columns([1, 1, 4])
                    with col_b1:
                        luu_kh_btn = st.button(
                            "💾 Lưu kế hoạch",
                            key=f"{key_prefix}kh_luu",
                            use_container_width=True,
                        )
                    with col_b2:
                        duyet_kh_btn = st.button(
                            "✅ Duyệt luôn",
                            key=f"{key_prefix}kh_duyet_luon",
                            disabled=not co_quyen_duyet,
                            use_container_width=True,
                        )

                    if luu_kh_btn or duyet_kh_btn:
                        loi_kh = []
                        if xa_chon == "— Chọn —":
                            loi_kh.append("Chưa chọn xã")
                        if not ngay_kh:
                            loi_kh.append("Chưa nhập ngày kiểm tra")
                        if not ds_chon:
                            loi_kh.append("Chưa chọn món vay nào")
                        if loi_kh:
                            for l in loi_kh:
                                st.error(f"❌ {l}")
                        else:
                            thanh_phan_list = df_tp[
                                df_tp["Họ và tên"].str.strip() != ""
                            ].to_dict("records")
                            ten_pgd_kh = (
                                str(df_kh[df_kh[COT_TEN_XA] == xa_chon][COT_TEN_PGD].iloc[0])
                                if (COT_TEN_PGD in df_kh.columns and xa_chon != "— Chọn —"
                                    and not df_kh[df_kh[COT_TEN_XA] == xa_chon].empty)
                                else (pgd_user or "")
                            )
                            data_kh = {
                                "ten_pgd":       ten_pgd_kh,
                                "ten_xa":        xa_chon,
                                "ten_to_tkv":    to_chon if to_chon != "— Tất cả —" else "",
                                "ngay_kiem_tra": str(ngay_kh),
                                "thanh_phan":    thanh_phan_list,
                                "ds_mon_vay":    ds_chon,
                                "ghi_chu":       ghi_chu_kh,
                                "trang_thai":    "cho_duyet",
                            }
                            try:
                                kh_id = db.luu_ke_hoach_kiem_tra(data_kh, username)
                                if duyet_kh_btn:
                                    db.duyet_ke_hoach(kh_id, username)
                                st.cache_data.clear()
                                label_kh = "lưu và duyệt" if duyet_kh_btn else "lưu"
                                st.success(f"✅ Đã {label_kh} kế hoạch kiểm tra.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Lỗi: {e}")

            # ── B: Danh sách kế hoạch đã lập ─────────────────────────────────
            st.markdown("### 📋 Danh sách kế hoạch kiểm tra")

            col_fkh, _ = st.columns([2, 4])
            with col_fkh:
                loc_tt_kh = st.selectbox(
                    "Trạng thái",
                    ["Tất cả", "Chờ duyệt", "Đã duyệt"],
                    key=f"{key_prefix}kh_loc_tt",
                )
            tt_map_kh = {
                "Tất cả":   None,
                "Chờ duyệt": "cho_duyet",
                "Đã duyệt":  "da_duyet",
            }

            rows_kh = db.doc_ke_hoach_kiem_tra(
                ten_pgd=pgd_filter_kh,
                trang_thai=tt_map_kh[loc_tt_kh],
            )

            if not rows_kh:
                st.info("ℹ️ Chưa có kế hoạch nào.")
            else:
                df_kh_list = pd.DataFrame([{
                    "ID":          r["id"],
                    "PGD":         r["ten_pgd"],
                    "Xã":          r["ten_xa"],
                    "Tổ TK&VV":    r.get("ten_to_tkv", ""),
                    "Ngày KT":     r["ngay_kiem_tra"],
                    "Số món":      len(r.get("ds_mon_vay") or []),
                    "Trạng thái":  r["trang_thai"],
                    "Người lập":   r["nguoi_lap"],
                    "Người duyệt": r.get("nguoi_duyet", ""),
                } for r in rows_kh])

                hien_thi_dataframe_phan_trang(
                    df_kh_list,
                    key=f"{key_prefix}kh_list_tbl",
                    height=320,
                )

                if co_quyen_duyet:
                    st.markdown("**Duyệt kế hoạch theo ID:**")
                    kh_id_action = st.number_input(
                        "ID kế hoạch",
                        min_value=1, step=1,
                        key=f"{key_prefix}kh_action_id",
                    )
                    if st.button(
                        "✅ Duyệt kế hoạch này",
                        key=f"{key_prefix}kh_duyet_id",
                        use_container_width=False,
                    ):
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

            with st.expander("📋 M10 — Danh sách chưa nhập kết quả (lưu tạm)"):
                rows_m10 = [
                    r for r in rows_all_kt
                    if r.get("trang_thai") == "luu_tam"
                ]
                df_m10 = pd.DataFrame(rows_m10)
                st.metric("Số bản ghi lưu tạm", fmt_so(len(df_m10)))
                if not df_m10.empty:
                    cols_m10 = [c for c in [
                        "id", "ma_mon_vay", "ten_pgd", "ten_kh",
                        "ngay_kiem_tra", "nguoi_nhap",
                    ] if c in df_m10.columns]
                    hien_thi_dataframe_phan_trang(
                        df_m10[cols_m10],
                        key=f"{key_prefix}bc_m10_tbl",
                        height=300,
                    )
                    if st.button("📥 Xuất M10 Excel", key=f"{key_prefix}bc_m10_xuat"):
                        st.session_state[f"_{key_prefix}m10_buf"] = xuat_excel(
                            {"M10_LuuTam": df_m10[cols_m10]}
                        )
                    if st.session_state.get(f"_{key_prefix}m10_buf"):
                        st.download_button(
                            "⬇️ Tải M10",
                            data=st.session_state[f"_{key_prefix}m10_buf"],
                            file_name="M10_LuuTam.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}bc_m10_dl",
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
                    if st.button("📄 Tạo Word Kế hoạch KT",
                                 key=f"{key_prefix}mb_kh_tao"):
                        try:
                            buf_kh = _tao_word_ke_hoach_kt(kh_sel, ds_mon_detail)
                            ten_file = (
                                f"QLNK_KeHoachKT_"
                                f"{kh_sel.get('ten_xa', '')}_"
                                f"{kh_sel.get('ngay_kiem_tra', '')}"
                            )
                            nut_tai_word_va_pdf(buf_kh, ten_file, f"{key_prefix}mb_kh")
                        except Exception as e_kh:
                            st.error(f"❌ Lỗi tạo Word: {e_kh}")
                    hien_thi_nut_tai(f"{key_prefix}mb_kh")

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
                    if st.button("📄 Tạo Word 01/QLNK",
                                 key=f"{key_prefix}mb_01_tao"):
                        try:
                            buf_01 = _tao_word_01qlnk(kh_01, rows_kq_01)
                            ten_file = (
                                f"QLNK_01_"
                                f"{kh_01.get('ten_xa', '')}_"
                                f"{kh_01.get('ngay_kiem_tra', '')}"
                            )
                            nut_tai_word_va_pdf(buf_01, ten_file, f"{key_prefix}mb_01")
                        except Exception as e_01:
                            st.error(f"❌ Lỗi tạo Word: {e_01}")
                    hien_thi_nut_tai(f"{key_prefix}mb_01")

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
                    if st.button("📄 Tạo Word 02/QLNK",
                                 key=f"{key_prefix}mb_02_tao"):
                        try:
                            row_02_merged = {**rows_hstd_02, **bs_02, **row_02}
                            buf_02 = _tao_word_02qlnk(row_02_merged)
                            ngay_str_02 = str(row_02.get("ngay_kiem_tra", "")).replace("/", "")
                            nut_tai_word_va_pdf(
                                buf_02,
                                f"QLNK_02_{row_02.get('ten_kh', '')}_{ngay_str_02}",
                                f"{key_prefix}mb_02",
                            )
                        except Exception as e_02:
                            st.error(f"❌ Lỗi tạo Word: {e_02}")
                    hien_thi_nut_tai(f"{key_prefix}mb_02")

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
                    st.info(f"{len(df_03)} món trong phạm vi đã chọn.")
                    if st.button("📄 Tạo Word 03/QLNK", key=f"{key_prefix}mb_03_tao"):
                        try:
                            ten_to_03 = to_03 if to_03 != "— Tất cả —" else ""
                            buf_03 = _tao_word_03qlnk(
                                pgd_03 or "", ten_to_03, df_03.to_dict("records")
                            )
                            nut_tai_word_va_pdf(
                                buf_03,
                                f"QLNK_03_{pgd_03}_{ten_to_03}",
                                f"{key_prefix}mb_03",
                            )
                        except Exception as e_03:
                            st.error(f"❌ Lỗi tạo Word: {e_03}")
                    hien_thi_nut_tai(f"{key_prefix}mb_03")

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
                    if st.button("📄 Tạo Word 04/QLNK", key=f"{key_prefix}mb_04_tao"):
                        try:
                            buf_04 = _tao_word_04qlnk(row_04_hstd, bs_04, ten_pgd_04)
                            nut_tai_word_va_pdf(
                                buf_04,
                                f"QLNK_04_{row_04_hstd.get(COT_TEN_KH, '')}_{ku_04}",
                                f"{key_prefix}mb_04",
                            )
                        except Exception as e_04:
                            st.error(f"❌ Lỗi tạo Word: {e_04}")
                    hien_thi_nut_tai(f"{key_prefix}mb_04")
