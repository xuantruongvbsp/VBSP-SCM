"""Dịch vụ xuất báo cáo giao ban tháng tổng hợp toàn Chi nhánh — PDF A4 landscape.

Bố cục 2 trang:
  Trang 1: Header NHCSXH + KPI tổng quan + Bảng xếp hạng 22 PGD
  Trang 2: Nhận xét / vấn đề nổi cộm + Chữ ký
"""
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from pathlib import Path
from typing import Sequence

import pandas as pd
import streamlit as st

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable, Image as RLImage, PageBreak,
    )
    from reportlab.platypus import Table as RLTable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    _REPORTLAB_READY = True
except ImportError:
    _REPORTLAB_READY = False

from config import (
    COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH,
    COT_MA_KH, COT_LAI_TON, COT_TEN_CT,
    DON_VI_CHI_NHANH, DS_PGD,
)
from utils import fmt, fmt_so, vn
from logger import get_logger

logger = get_logger(__name__)

FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

try:
    import os
    candidates = [
        Path("C:/Windows/Fonts/times.ttf"),
        Path("C:/Windows/Fonts/timesbd.ttf"),
        Path("assets/times.ttf"),
        Path("assets/timesbd.ttf"),
    ]
    regular = next((p for p in candidates if p.exists()), None)
    bold = next((p for p in [candidates[1], candidates[3]] if p.exists()), None)
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
RED_TEXT = colors.HexColor("#C62828")
ORANGE_TEXT = colors.HexColor("#E65100")


def _tim_logo() -> str | None:
    for p in [
        Path("assets/logo.png"),
        Path("logo.png"),
    ]:
        if p.exists():
            return str(p)
    return None


def tao_bao_cao_giao_ban_thang(
    df: pd.DataFrame,
    thang: int,
    nam: int,
    username: str = "unknown",
    df_prev: pd.DataFrame | None = None,
) -> bytes:
    """Tạo báo cáo giao ban tháng tổng hợp toàn Chi nhánh — PDF A4 landscape.

    Args:
        df: HSTD toàn Chi nhánh (đã lọc kỳ hiện tại)
        thang: Tháng báo cáo (1-12)
        nam: Năm báo cáo
        username: Người xuất báo cáo
        df_prev: HSTD kỳ trước để so sánh (None = không so sánh)

    Returns:
        bytes: Nội dung file PDF
    """
    if not _REPORTLAB_READY:
        st.error("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
        return b""
    if df is None or df.empty:
        st.warning("Không có dữ liệu để tạo báo cáo giao ban.")
        return b""

    _dang_ky_font()

    page_size = landscape(A4)
    margin = 1.5 * cm
    usable_w = page_size[0] - 2 * margin

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=f"Giao ban tháng {thang}/{nam}",
        author="VBSP-SCM",
    )

    story: list = []

    _ve_header(story, thang, nam, username, usable_w)

    df_copy = df.copy()
    for c in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_LAI_TON]:
        if c in df_copy.columns:
            df_copy[c] = pd.to_numeric(df_copy[c], errors="coerce").fillna(0)

    _ve_kpi_section(story, df_copy, df_prev, thang, nam, usable_w)

    story.append(PageBreak())

    _ve_header(story, thang, nam, username, usable_w)

    _ve_bang_xep_hang_pgd(story, df_copy, df_prev, usable_w)

    _ve_nhan_xet(story, df_copy, thang, nam, usable_w)

    try:
        doc.build(story)
    except Exception as e:
        logger.error("tao_bao_cao_giao_ban_thang: Lỗi build PDF — %s", e, exc_info=True)
        st.error(f"Lỗi tạo PDF: {e}")
        return b""

    buf.seek(0)
    return buf.getvalue()


def _dang_ky_font():
    if FONT_NORMAL == "TNR":
        return
    try:
        candidates = [
            Path("C:/Windows/Fonts/times.ttf"),
            Path("C:/Windows/Fonts/timesbd.ttf"),
            Path("assets/times.ttf"),
            Path("assets/timesbd.ttf"),
        ]
        regular = next((p for p in candidates if p.exists()), None)
        bold = next((p for p in [candidates[1], candidates[3]] if p.exists()), None)
        if regular:
            pdfmetrics.registerFont(TTFont("TNR", str(regular)))
        if bold:
            pdfmetrics.registerFont(TTFont("TNR-Bold", str(bold)))
    except Exception:
        pass


def _ve_header(story: list, thang: int, nam: int, username: str, usable_w: float):
    logo_path = _tim_logo()

    style_bank = ParagraphStyle(
        "GB_BankName", fontName=FONT_BOLD, fontSize=12,
        alignment=TA_CENTER, leading=16,
    )
    style_title = ParagraphStyle(
        "GB_Title", fontName=FONT_BOLD, fontSize=16,
        alignment=TA_CENTER, textColor=VBSP_GREEN, spaceBefore=4, spaceAfter=4,
    )
    style_meta = ParagraphStyle(
        "GB_Meta", fontName=FONT_NORMAL, fontSize=8,
        alignment=TA_CENTER, textColor=colors.gray,
    )
    style_slogan = ParagraphStyle(
        "GB_Slogan", fontName=FONT_BOLD, fontSize=10,
        alignment=TA_CENTER, textColor=VBSP_GREEN, spaceAfter=6,
    )

    bank_text = (
        "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI<br/>"
        "CHI NHÁNH TỈNH ĐỒNG NAI"
    )
    if logo_path:
        try:
            logo = RLImage(logo_path, width=2.2 * cm, height=2.2 * cm)
            header_tbl = RLTable(
                [[logo, Paragraph(bank_text, style_bank)]],
                colWidths=[2.6 * cm, usable_w - 2.6 * cm],
            )
            header_tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(header_tbl)
        except Exception:
            story.append(Paragraph(bank_text, style_bank))
    else:
        story.append(Paragraph(bank_text, style_bank))

    story.append(HRFlowable(
        width="100%", thickness=1.5, color=VBSP_GREEN, spaceAfter=4,
    ))

    story.append(Paragraph(
        f"BÁO CÁO GIAO BAN THÁNG {thang}/{nam}",
        style_title,
    ))
    story.append(Paragraph("— Toàn Chi nhánh —", style_slogan))

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(
        f"Ngày xuất: {now_str}  |  Người xuất: {username}",
        style_meta,
    ))
    story.append(Spacer(1, 6))


def _ve_kpi_section(
    story: list,
    df: pd.DataFrame,
    df_prev: pd.DataFrame | None,
    thang: int,
    nam: int,
    usable_w: float,
):
    style_section = ParagraphStyle(
        "GB_Section", fontName=FONT_BOLD, fontSize=12,
        textColor=VBSP_GREEN, spaceBefore=6, spaceAfter=6,
    )
    story.append(Paragraph("I. CHỈ TIÊU TỔNG QUAN TOÀN CHI NHÁNH", style_section))

    dn = float(df[COT_TONG_DU_NO].sum())
    qh = float(df[COT_DU_NO_QH].sum())
    kh = float(df.get(COT_DU_NO_KHOANH, pd.Series([0])).sum())
    lt = float(df.get(COT_LAI_TON, pd.Series([0])).sum())
    n_mon = int(len(df))
    n_kh = int(df[COT_MA_KH].nunique())
    n_pgd = int(df[COT_TEN_PGD].nunique())
    tl_qh = qh / dn * 100 if dn > 0 else 0.0
    tl_kh = kh / dn * 100 if dn > 0 else 0.0
    nx = dn - qh - kh

    kpi_data = [
        ("Dư nợ toàn CN", fmt(dn), "triệu đồng"),
        ("Dư nợ trong hạn", fmt(nx), "triệu đồng"),
        ("Dư nợ quá hạn", fmt(qh), "triệu đồng"),
        ("Tỷ lệ quá hạn", f"{vn(tl_qh, 2)}%", ""),
        ("Dư nợ khoanh", fmt(kh), "triệu đồng"),
        ("Tỷ lệ khoanh", f"{vn(tl_kh, 2)}%", ""),
        ("Lãi tồn", fmt(lt), "triệu đồng"),
        ("Số món vay", fmt_so(n_mon), "món"),
        ("Số khách hàng", fmt_so(n_kh), "KH"),
        ("Số PGD có dữ liệu", str(n_pgd), f"/{len(DS_PGD)} PGD"),
    ]

    style_kpi_label = ParagraphStyle(
        "GB_KPI_Label", fontName=FONT_NORMAL, fontSize=8.5,
        alignment=TA_LEFT, leading=12,
    )
    style_kpi_val = ParagraphStyle(
        "GB_KPI_Val", fontName=FONT_BOLD, fontSize=10,
        alignment=TA_RIGHT, textColor=VBSP_GREEN, leading=12,
    )
    style_kpi_unit = ParagraphStyle(
        "GB_KPI_Unit", fontName=FONT_NORMAL, fontSize=7,
        alignment=TA_LEFT, textColor=colors.gray, leading=12,
    )

    rows_per_col = 5
    col1_items = kpi_data[:rows_per_col]
    col2_items = kpi_data[rows_per_col:]

    kpi_table_data: list[list] = []
    for i in range(rows_per_col):
        row: list = []
        for items in [col1_items, col2_items]:
            if i < len(items):
                label, val, unit = items[i]
                row.append(Paragraph(label, style_kpi_label))
                row.append(Paragraph(val, style_kpi_val))
                row.append(Paragraph(unit, style_kpi_unit))
            else:
                row.append(Paragraph("", style_kpi_label))
                row.append(Paragraph("", style_kpi_val))
                row.append(Paragraph("", style_kpi_unit))
        kpi_table_data.append(row)

    col_widths = [
        usable_w * 0.22, usable_w * 0.14, usable_w * 0.14,
        usable_w * 0.22, usable_w * 0.14, usable_w * 0.14,
    ]
    kpi_tbl = Table(kpi_table_data, colWidths=col_widths)
    kpi_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, VBSP_GREEN_LIGHT),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
    ]))
    story.append(kpi_tbl)

    # So sánh kỳ trước nếu có
    if df_prev is not None and not df_prev.empty:
        for c in [COT_TONG_DU_NO, COT_DU_NO_QH]:
            if c in df_prev.columns:
                df_prev[c] = pd.to_numeric(df_prev[c], errors="coerce").fillna(0)
        dn_prev = float(df_prev[COT_TONG_DU_NO].sum())
        qh_prev = float(df_prev.get(COT_DU_NO_QH, pd.Series([0])).sum())
        delta_dn = dn - dn_prev
        delta_qh = qh - qh_prev
        pct_dn = delta_dn / dn_prev * 100 if dn_prev > 0 else 0.0
        pct_qh = delta_qh / qh_prev * 100 if qh_prev > 0 else 0.0

        story.append(Spacer(1, 4))
        style_delta = ParagraphStyle(
            "GB_Delta", fontName=FONT_NORMAL, fontSize=8,
            alignment=TA_CENTER, textColor=colors.gray, leading=11,
        )
        arrow_dn = "▲" if delta_dn >= 0 else "▼"
        arrow_qh = "▲" if delta_qh >= 0 else "▼"
        color_dn = VBSP_GREEN if delta_dn >= 0 else RED_TEXT
        color_qh = RED_TEXT if delta_qh >= 0 else VBSP_GREEN
        story.append(Paragraph(
            f'So kỳ trước: Dư nợ <font color="{_hex(color_dn)}">{arrow_dn} {fmt(abs(int(delta_dn)))} trđ ({vn(abs(pct_dn), 1)}%)</font>'
            f'  |  Quá hạn <font color="{_hex(color_qh)}">{arrow_qh} {fmt(abs(int(delta_qh)))} trđ ({vn(abs(pct_qh), 1)}%)</font>',
            style_delta,
        ))

    story.append(Spacer(1, 4))


def _ve_bang_xep_hang_pgd(
    story: list,
    df: pd.DataFrame,
    df_prev: pd.DataFrame | None,
    usable_w: float,
):
    style_section = ParagraphStyle(
        "GB_Section", fontName=FONT_BOLD, fontSize=12,
        textColor=VBSP_GREEN, spaceBefore=6, spaceAfter=6,
    )
    story.append(Paragraph("II. XẾP HẠNG CÁC PGD THEO DƯ NỢ", style_section))

    pgd_stats = df.groupby(COT_TEN_PGD).agg(
        so_mon=(COT_MA_KH, "count"),
        so_kh=(COT_MA_KH, "nunique"),
        du_no=(COT_TONG_DU_NO, "sum"),
        qh=(COT_DU_NO_QH, "sum"),
        khoanh=(COT_DU_NO_KHOANH, "sum") if COT_DU_NO_KHOANH in df.columns else (COT_MA_KH, lambda x: 0),
        lai_ton=(COT_LAI_TON, "sum") if COT_LAI_TON in df.columns else (COT_MA_KH, lambda x: 0),
    ).reset_index()

    pgd_stats["tl_qh"] = pgd_stats.apply(
        lambda r: r["qh"] / r["du_no"] * 100 if r["du_no"] > 0 else 0, axis=1
    )
    pgd_stats["tl_khoanh"] = pgd_stats.apply(
        lambda r: r["khoanh"] / r["du_no"] * 100 if r["du_no"] > 0 else 0, axis=1
    )
    pgd_stats = pgd_stats.sort_values("du_no", ascending=False).reset_index(drop=True)
    pgd_stats["rank"] = range(1, len(pgd_stats) + 1)

    if df_prev is not None and not df_prev.empty:
        for c in [COT_TONG_DU_NO, COT_DU_NO_QH]:
            if c in df_prev.columns:
                df_prev[c] = pd.to_numeric(df_prev[c], errors="coerce").fillna(0)
        pgd_prev = df_prev.groupby(COT_TEN_PGD).agg(
            du_no_prev=(COT_TONG_DU_NO, "sum"),
        ).reset_index()
        pgd_stats = pgd_stats.merge(pgd_prev, on=COT_TEN_PGD, how="left")
        pgd_stats["du_no_prev"] = pgd_stats["du_no_prev"].fillna(0)
        pgd_stats["delta_dn"] = pgd_stats["du_no"] - pgd_stats["du_no_prev"]
    else:
        pgd_stats["delta_dn"] = 0

    headers = ["#", "PGD", "Số món", "Số KH", "Dư nợ (trđ)", "QH (trđ)", "QH%", "Khoanh (trđ)", "Lãi tồn (trđ)", "±DN"]
    style_h = ParagraphStyle(
        "GB_TH", fontName=FONT_BOLD, fontSize=7,
        alignment=TA_CENTER, textColor=colors.white, leading=9,
    )
    style_c = ParagraphStyle(
        "GB_TC", fontName=FONT_NORMAL, fontSize=7,
        alignment=TA_CENTER, leading=9,
    )
    style_cl = ParagraphStyle(
        "GB_TCL", fontName=FONT_NORMAL, fontSize=7,
        alignment=TA_LEFT, leading=9,
    )

    table_data = [[Paragraph(h, style_h) for h in headers]]

    for _, row in pgd_stats.iterrows():
        delta_str = ""
        if row["delta_dn"] != 0:
            arrow = "▲" if row["delta_dn"] > 0 else "▼"
            delta_str = f"{arrow} {fmt(abs(int(row['delta_dn'])))}"

        tl_qh_str = f"{vn(row['tl_qh'], 1)}%"
        qh_color = RED_TEXT if row["tl_qh"] > 5 else (ORANGE_TEXT if row["tl_qh"] > 3 else colors.black)

        cells = [
            Paragraph(str(row["rank"]), style_c),
            Paragraph(str(row[COT_TEN_PGD]), style_cl),
            Paragraph(fmt_so(int(row["so_mon"])), style_c),
            Paragraph(fmt_so(int(row["so_kh"])), style_c),
            Paragraph(fmt(int(row["du_no"])), style_c),
            Paragraph(fmt(int(row["qh"])), style_c),
            Paragraph(f'<font color="{_hex(qh_color)}">{tl_qh_str}</font>', style_c),
            Paragraph(fmt(int(row["khoanh"])), style_c),
            Paragraph(fmt(int(row["lai_ton"])), style_c),
            Paragraph(delta_str, style_c),
        ]
        table_data.append(cells)

    # Dòng tổng
    cong_cells = [
        Paragraph("", style_c),
        Paragraph("TOÀN CN", style_cl),
        Paragraph(fmt_so(int(pgd_stats["so_mon"].sum())), style_c),
        Paragraph(fmt_so(int(pgd_stats["so_kh"].sum())), style_c),
        Paragraph(fmt(int(pgd_stats["du_no"].sum())), style_c),
        Paragraph(fmt(int(pgd_stats["qh"].sum())), style_c),
        Paragraph("", style_c),
        Paragraph(fmt(int(pgd_stats["khoanh"].sum())), style_c),
        Paragraph(fmt(int(pgd_stats["lai_ton"].sum())), style_c),
        Paragraph("", style_c),
    ]
    table_data.append(cong_cells)

    n_cols = len(headers)
    col_w = [usable_w * p for p in [0.04, 0.18, 0.08, 0.08, 0.12, 0.10, 0.07, 0.10, 0.10, 0.13]]

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    tbl_style_cmds: list = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("BACKGROUND", (0, 0), (-1, 0), VBSP_GREEN),
        ("LINEBELOW", (0, 0), (-1, 0), 1, VBSP_GREEN),
        ("BACKGROUND", (0, -1), (-1, -1), VBSP_GREEN_LIGHT),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            tbl_style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))

    tbl.setStyle(TableStyle(tbl_style_cmds))
    story.append(tbl)

    # Highlight top 3 PGD
    story.append(Spacer(1, 6))
    top3 = pgd_stats.head(3)
    bottom3 = pgd_stats.tail(3)
    style_highlight = ParagraphStyle(
        "GB_Highlight", fontName=FONT_NORMAL, fontSize=8,
        alignment=TA_LEFT, leading=11, textColor=colors.gray,
    )
    top_names = ", ".join(top3[COT_TEN_PGD].tolist())
    bottom_names = ", ".join(bottom3[COT_TEN_PGD].tolist())
    story.append(Paragraph(
        f'<b>Top 3 dư nợ cao nhất:</b> {top_names}  |  '
        f'<b>3 PGD dư nợ thấp nhất:</b> {bottom_names}',
        style_highlight,
    ))

    # PGD có QH% cao nhất
    pgd_sorted_qh = pgd_stats.sort_values("tl_qh", ascending=False)
    top_qh = pgd_sorted_qh.head(3)
    qh_names = ", ".join([
        f'{r[COT_TEN_PGD]} ({vn(r["tl_qh"], 1)}%)'
        for _, r in top_qh.iterrows()
    ])
    story.append(Paragraph(
        f'<font color="{_hex(RED_TEXT)}"><b>⚠ PGD có tỷ lệ quá hạn cao nhất:</b></font> {qh_names}',
        style_highlight,
    ))


def _ve_nhan_xet(
    story: list,
    df: pd.DataFrame,
    thang: int,
    nam: int,
    usable_w: float,
):
    style_section = ParagraphStyle(
        "GB_Section", fontName=FONT_BOLD, fontSize=12,
        textColor=VBSP_GREEN, spaceBefore=12, spaceAfter=6,
    )
    story.append(Paragraph("III. NHẬN XÉT &amp; ĐỀ XUẤT", style_section))

    dn = float(df[COT_TONG_DU_NO].sum())
    qh = float(df[COT_DU_NO_QH].sum())
    tl_qh = qh / dn * 100 if dn > 0 else 0.0
    kh = float(df.get(COT_DU_NO_KHOANH, pd.Series([0])).sum())
    lt = float(df.get(COT_LAI_TON, pd.Series([0])).sum())
    n_kh = int(df[COT_MA_KH].nunique())

    diem_nhan_xet: list[str] = []

    diem_nhan_xet.append(
        f"Tính đến hết tháng {thang}/{nam}, toàn Chi nhánh quản lý "
        f"{fmt_so(n_kh)} khách hàng với tổng dư nợ {fmt(int(dn))} triệu đồng."
    )

    if tl_qh <= 1:
        diem_nhan_xet.append(
            f"Tỷ lệ quá hạn ở mức {vn(tl_qh, 2)}%, dưới ngưỡng 1% — chất lượng tín dụng tốt."
        )
    elif tl_qh <= 3:
        diem_nhan_xet.append(
            f"Tỷ lệ quá hạn ở mức {vn(tl_qh, 2)}%, trong ngưỡng kiểm soát — cần tiếp tục theo dõi."
        )
    else:
        diem_nhan_xet.append(
            f"Tỷ lệ quá hạn ở mức {vn(tl_qh, 2)}%, trên ngưỡng 3% — cần có biện pháp xử lý quyết liệt."
        )

    if kh > 0:
        diem_nhan_xet.append(
            f"Dư nợ khoanh hiện tại {fmt(int(kh))} triệu đồng, cần rà soát các món đến hạn khoanh."
        )
    if lt > 0:
        diem_nhan_xet.append(
            f"Lãi tồn toàn CN {fmt(int(lt))} triệu đồng — đề nghị các PGD tăng cường thu lãi."
        )

    style_nx = ParagraphStyle(
        "GB_NX", fontName=FONT_NORMAL, fontSize=9,
        alignment=TA_LEFT, leading=15, spaceAfter=4,
    )

    for nx in diem_nhan_xet:
        story.append(Paragraph(f"• {nx}", style_nx))

    story.append(Spacer(1, 12))

    # Chữ ký
    style_ky_label = ParagraphStyle(
        "GB_KyLabel", fontName=FONT_BOLD, fontSize=10,
        alignment=TA_CENTER, leading=14,
    )
    style_ky_sub = ParagraphStyle(
        "GB_KySub", fontName=FONT_NORMAL, fontSize=8,
        alignment=TA_CENTER, textColor=colors.gray, leading=11,
    )

    ky_data = [
        [
            Paragraph("NGƯỜI LẬP BIỂU", style_ky_label),
            Paragraph("KIỂM SOÁT", style_ky_label),
            Paragraph("GIÁM ĐỐC", style_ky_label),
        ],
        [
            Paragraph("(Ký, ghi rõ họ tên)", style_ky_sub),
            Paragraph("(Ký, ghi rõ họ tên)", style_ky_sub),
            Paragraph("(Ký, ghi rõ họ tên)", style_ky_sub),
        ],
    ]
    ky_tbl = Table(ky_data, colWidths=[usable_w / 3] * 3)
    ky_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ky_tbl)


def _hex(c) -> str:
    try:
        return c.hexval()
    except AttributeError:
        pass
    try:
        r = int(c.red * 255) if hasattr(c, 'red') else 0
        g = int(c.green * 255) if hasattr(c, 'green') else 0
        b = int(c.blue * 255) if hasattr(c, 'blue') else 0
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#000000"
