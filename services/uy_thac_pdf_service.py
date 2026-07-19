"""Tạo PDF báo cáo số liệu và báo cáo điều hành Ủy thác bằng ReportLab."""
from __future__ import annotations

from datetime import date, datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Iterable

import pandas as pd
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import TEN_CHI_NHANH_HIEN_THI


_ROOT = Path(__file__).resolve().parent.parent
_GREEN = colors.HexColor("#19733B")
_GREEN_DARK = colors.HexColor("#0F5A2D")
_GREEN_LIGHT = colors.HexColor("#E8F5EC")
_BLUE_LIGHT = colors.HexColor("#EAF2FF")
_ORANGE_LIGHT = colors.HexColor("#FFF1DC")
_RED_LIGHT = colors.HexColor("#FDEBEC")
_GRAY_LIGHT = colors.HexColor("#F4F6F8")
_GRID = colors.HexColor("#B8C0C8")
_TEXT = colors.HexColor("#1F2937")
_MUTED = colors.HexColor("#5F6B76")


def _register_fonts() -> tuple[str, str]:
    regular_candidates = [
        Path("C:/Windows/Fonts/times.ttf"),
        _ROOT / "assets" / "times.ttf",
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/timesbd.ttf"),
        _ROOT / "assets" / "timesbd.ttf",
    ]
    regular = next((p for p in regular_candidates if p.exists()), None)
    bold = next((p for p in bold_candidates if p.exists()), None)
    if regular and bold:
        try:
            pdfmetrics.registerFont(TTFont("UT-Times", str(regular)))
            pdfmetrics.registerFont(TTFont("UT-Times-Bold", str(bold)))
            pdfmetrics.registerFontFamily(
                "UT-Times",
                normal="UT-Times",
                bold="UT-Times-Bold",
                italic="UT-Times",
                boldItalic="UT-Times-Bold",
            )
            return "UT-Times", "UT-Times-Bold"
        except Exception:
            pass
    return "Helvetica", "Helvetica-Bold"


FONT_NORMAL, FONT_BOLD = _register_fonts()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "UTTitle", parent=base["Title"], fontName=FONT_BOLD,
            fontSize=17, leading=22, alignment=TA_CENTER,
            textColor=_GREEN_DARK, spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "UTSubtitle", fontName=FONT_NORMAL, fontSize=9,
            leading=12, alignment=TA_CENTER, textColor=_MUTED,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "UTSection", fontName=FONT_BOLD, fontSize=12,
            leading=15, textColor=_GREEN_DARK, spaceBefore=6, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "UTBody", fontName=FONT_NORMAL, fontSize=9,
            leading=13, textColor=_TEXT, spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "UTSmall", fontName=FONT_NORMAL, fontSize=7.5,
            leading=9.5, textColor=_MUTED,
        ),
        "table_header": ParagraphStyle(
            "UTTableHeader", fontName=FONT_BOLD, fontSize=7,
            leading=8.5, alignment=TA_CENTER, textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "UTTableCell", fontName=FONT_NORMAL, fontSize=6.8,
            leading=8.4, alignment=TA_CENTER, textColor=_TEXT,
        ),
        "table_cell_left": ParagraphStyle(
            "UTTableCellLeft", fontName=FONT_NORMAL, fontSize=6.8,
            leading=8.4, alignment=TA_LEFT, textColor=_TEXT,
        ),
        "table_cell_right": ParagraphStyle(
            "UTTableCellRight", fontName=FONT_NORMAL, fontSize=6.8,
            leading=8.4, alignment=TA_RIGHT, textColor=_TEXT,
        ),
        "kpi": ParagraphStyle(
            "UTKpi", fontName=FONT_NORMAL, fontSize=8,
            leading=11, alignment=TA_CENTER, textColor=_TEXT,
        ),
        "note": ParagraphStyle(
            "UTNote", fontName=FONT_NORMAL, fontSize=8,
            leading=11, textColor=_MUTED, leftIndent=6,
        ),
    }


def _p(value: object, style: ParagraphStyle) -> Paragraph:
    text = "" if value is None or (not isinstance(value, str) and pd.isna(value)) else str(value)
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _fmt_vn(value: object, precision: int = 0, signed: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    sign_fmt = "+" if signed and number > 0 else ""
    raw = f"{abs(number):,.{precision}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if number < 0:
        return f"-{raw}"
    return f"{sign_fmt}{raw}"


def _fmt_date(value: object) -> str:
    if value in (None, ""):
        return "Chưa xác định"
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.strftime("%d/%m/%Y")
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return parsed.strftime("%d/%m/%Y") if pd.notna(parsed) else str(value)


def _is_money_col(col: str) -> bool:
    lower = col.lower()
    return "(triệu đồng)" in lower or "(trieu dong)" in lower


def _is_percent_col(col: str) -> bool:
    lower = col.lower()
    return "%" in col or "tỷ lệ" in lower or "tỷ trọng" in lower


def _is_count_col(col: str) -> bool:
    lower = col.lower()
    return lower.startswith("số ") or col == "Xếp hạng"


def _format_cell(col: str, value: object) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    if _is_money_col(col):
        try:
            return _fmt_vn(float(value) / 1_000_000, signed=col.startswith("Δ"))
        except (TypeError, ValueError):
            return str(value)
    if _is_percent_col(col):
        try:
            return _fmt_vn(value, precision=2) + "%"
        except (TypeError, ValueError):
            return str(value)
    if _is_count_col(col):
        try:
            return _fmt_vn(value, signed=col.startswith("Δ"))
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _fmt_vn(value, precision=1 if not float(value).is_integer() else 0)
    return str(value)


def _logo_path() -> Path | None:
    for path in [_ROOT / "assets" / "logo.png", _ROOT / "logo.png"]:
        if path.exists():
            return path
    return None


def _header(story: list, title: str, subtitle: str, styles: dict[str, ParagraphStyle], usable_w: float) -> None:
    logo_path = _logo_path()
    bank_style = ParagraphStyle(
        "UTBank", fontName=FONT_BOLD, fontSize=10.5,
        leading=13, alignment=TA_CENTER, textColor=_TEXT,
    )
    bank = Paragraph(
        "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM<br/>"
        f"<font size='9'>{escape(TEN_CHI_NHANH_HIEN_THI)}</font>",
        bank_style,
    )
    if logo_path:
        logo = Image(str(logo_path), width=17 * mm, height=17 * mm)
        header = Table([[logo, bank]], colWidths=[22 * mm, usable_w - 22 * mm])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header)
    else:
        story.append(bank)
    story.append(HRFlowable(width="100%", thickness=1.3, color=_GREEN, spaceBefore=3, spaceAfter=7))
    story.append(Paragraph(escape(title.upper()), styles["title"]))
    story.append(Paragraph(escape(subtitle), styles["subtitle"]))


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(_GRID)
    canvas.setLineWidth(0.4)
    canvas.line(doc.leftMargin, 11 * mm, doc.pagesize[0] - doc.rightMargin, 11 * mm)
    canvas.setFillColor(_MUTED)
    canvas.setFont(FONT_NORMAL, 7)
    canvas.drawString(doc.leftMargin, 7 * mm, "Nguồn: HSTD - Hệ thống Quản trị Tín dụng Nội bộ")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 7 * mm, f"Trang {doc.page}")
    canvas.restoreState()


def _meta_table(
    pham_vi: str,
    ngay_so_lieu: object,
    nguoi_xuat: str,
    bo_loc: Iterable[str] | None,
    styles: dict[str, ParagraphStyle],
    usable_w: float,
) -> Table:
    filters = "; ".join(str(v) for v in (bo_loc or []) if str(v).strip()) or "Không áp dụng bộ lọc bổ sung"
    rows = [
        [_p("Phạm vi", styles["body"]), _p(pham_vi, styles["body"]),
         _p("Ngày số liệu", styles["body"]), _p(_fmt_date(ngay_so_lieu), styles["body"])],
        [_p("Người xuất", styles["body"]), _p(nguoi_xuat or "unknown", styles["body"]),
         _p("Ngày xuất", styles["body"]), _p(datetime.now().strftime("%d/%m/%Y %H:%M"), styles["body"])],
        [_p("Bộ lọc", styles["body"]), _p(filters, styles["body"]), "", ""],
    ]
    table = Table(rows, colWidths=[25 * mm, usable_w * 0.43, 27 * mm, usable_w * 0.29])
    table.setStyle(TableStyle([
        ("SPAN", (1, 2), (3, 2)),
        ("BACKGROUND", (0, 0), (0, -1), _GREEN_LIGHT),
        ("BACKGROUND", (2, 0), (2, 1), _GREEN_LIGHT),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
        ("FONTNAME", (2, 0), (2, 1), FONT_BOLD),
        ("GRID", (0, 0), (-1, -1), 0.45, _GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _kpi_table(tong_quan: dict[str, object], styles: dict[str, ParagraphStyle], usable_w: float) -> Table:
    kpis = [
        ("Tổ TK&VV", _fmt_vn(tong_quan.get("so_to", 0)), _GREEN_LIGHT),
        ("Khách hàng", _fmt_vn(tong_quan.get("so_kh", 0)), _BLUE_LIGHT),
        ("Dư nợ", _fmt_vn(float(tong_quan.get("tong_dn", 0) or 0) / 1e9, 3) + " tỷ", _GREEN_LIGHT),
        ("Tỷ lệ NQH", _fmt_vn(tong_quan.get("ty_le_nqh", 0), 2) + "%", _RED_LIGHT),
        ("Tổ có NQH", _fmt_vn(tong_quan.get("so_to_nqh", 0)), _RED_LIGHT),
        ("Tổ có lãi tồn", _fmt_vn(tong_quan.get("so_to_lai_ton", 0)), _ORANGE_LIGHT),
        ("Lãi tồn", _fmt_vn(float(tong_quan.get("lai_ton", 0) or 0) / 1e6) + " triệu", _ORANGE_LIGHT),
        ("Tiền gửi", _fmt_vn(float(tong_quan.get("so_du_tg", 0) or 0) / 1e9, 3) + " tỷ", _BLUE_LIGHT),
    ]
    cells = []
    for label, value, _ in kpis:
        cells.append(Paragraph(f"<b>{escape(label)}</b><br/><font size='13'>{escape(value)}</font>", styles["kpi"]))
    table = Table([cells[:4], cells[4:]], colWidths=[usable_w / 4] * 4, rowHeights=[18 * mm, 18 * mm])
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for idx, (_, _, bg) in enumerate(kpis):
        commands.append(("BACKGROUND", (idx % 4, idx // 4), (idx % 4, idx // 4), bg))
    table.setStyle(TableStyle(commands))
    return table


def _column_widths(df: pd.DataFrame, usable_w: float) -> list[float]:
    weights: list[float] = []
    for col in df.columns:
        sample = [str(col)] + [str(v) for v in df[col].head(25).fillna("").tolist()]
        max_len = max((len(v) for v in sample), default=8)
        weights.append(min(max(max_len, 8), 32))
    total = sum(weights) or 1
    return [usable_w * w / total for w in weights]


def _data_table(df: pd.DataFrame, styles: dict[str, ParagraphStyle], usable_w: float) -> Table:
    show = df.copy().reset_index(drop=True)
    headers = [_p(col, styles["table_header"]) for col in show.columns]
    rows: list[list[Paragraph]] = []
    for _, row in show.iterrows():
        cells = []
        for col in show.columns:
            text = _format_cell(str(col), row[col])
            if _is_money_col(str(col)) or _is_percent_col(str(col)) or _is_count_col(str(col)):
                style = styles["table_cell_right"]
            elif col == show.columns[0] or show[col].dtype == "object":
                style = styles["table_cell_left"]
            else:
                style = styles["table_cell"]
            cells.append(_p(text, style))
        rows.append(cells)
    table = Table(
        [headers] + rows,
        colWidths=_column_widths(show, usable_w),
        repeatRows=1,
        splitByRow=1,
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _GREEN_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, _GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _GRAY_LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _append_dataframe(
    story: list,
    df: pd.DataFrame,
    styles: dict[str, ParagraphStyle],
    usable_w: float,
    max_rows: int | None = None,
) -> None:
    if df is None or df.empty:
        story.append(Paragraph("Không có dữ liệu phù hợp.", styles["note"]))
        return
    show = df.head(max_rows).copy() if max_rows else df.copy()
    columns = list(show.columns)
    if len(columns) <= 9:
        story.append(_data_table(show, styles, usable_w))
    else:
        anchor_candidates = {
            "PGD", "Xã/Phường", "Hội đoàn thể", "Tổ TK&VV", "Kỳ", "Đối tượng",
            "Mức độ", "Nhóm cảnh báo", "Đơn vị/Đối tượng",
        }
        anchors = [c for c in columns if c in anchor_candidates][:2]
        if not anchors:
            anchors = columns[:1]
        metrics = [c for c in columns if c not in anchors]
        chunks = [metrics[i:i + (9 - len(anchors))] for i in range(0, len(metrics), 9 - len(anchors))]
        for idx, chunk in enumerate(chunks, start=1):
            story.append(Paragraph(f"Nhóm cột {idx}/{len(chunks)}", styles["small"]))
            story.append(_data_table(show[anchors + chunk], styles, usable_w))
            if idx < len(chunks):
                story.append(Spacer(1, 6))
    if max_rows and len(df) > max_rows:
        story.append(Paragraph(
            f"PDF hiển thị {max_rows}/{len(df)} dòng. Xem đầy đủ trong bộ báo cáo Excel.",
            styles["note"],
        ))


def _bar_chart(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
    usable_w: float,
    top_n: int = 10,
    scale: float = 1e9,
) -> Drawing | None:
    if df is None or df.empty or label_col not in df.columns or value_col not in df.columns:
        return None
    data = df[[label_col, value_col]].copy()
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce").fillna(0)
    data = data.sort_values(value_col, ascending=False).head(top_n)
    if data.empty or float(data[value_col].max()) <= 0:
        return None
    width = min(usable_w, 245 * mm)
    drawing = Drawing(width, 92 * mm)
    chart = VerticalBarChart()
    chart.x = 16 * mm
    chart.y = 18 * mm
    chart.width = width - 25 * mm
    chart.height = 58 * mm
    chart.data = [[float(v) / scale for v in data[value_col]]]
    chart.categoryAxis.categoryNames = [str(v)[:20] for v in data[label_col]]
    chart.categoryAxis.labels.fontName = FONT_NORMAL
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.dy = -4
    chart.valueAxis.labels.fontName = FONT_NORMAL
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labelTextFormat = "%0.1f"
    chart.bars[0].fillColor = _GREEN
    chart.bars[0].strokeColor = _GREEN_DARK
    drawing.add(chart)
    drawing.add(String(width / 2, 84 * mm, title, fontName=FONT_BOLD, fontSize=10, textAnchor="middle", fillColor=_GREEN_DARK))
    drawing.add(String(width - 2 * mm, 3 * mm, "Đơn vị: tỷ đồng", fontName=FONT_NORMAL, fontSize=7, textAnchor="end", fillColor=_MUTED))
    return drawing


def _trend_chart(df: pd.DataFrame, usable_w: float) -> Drawing | None:
    required = {"Kỳ", "Tổng dư nợ (triệu đồng)"}
    if df is None or df.empty or not required.issubset(df.columns):
        return None
    show = df.copy().tail(12)
    values = pd.to_numeric(show["Tổng dư nợ (triệu đồng)"], errors="coerce").fillna(0) / 1e9
    if values.empty or float(values.max()) <= 0:
        return None
    width = min(usable_w, 245 * mm)
    drawing = Drawing(width, 86 * mm)
    chart = HorizontalLineChart()
    chart.x = 18 * mm
    chart.y = 17 * mm
    chart.width = width - 28 * mm
    chart.height = 53 * mm
    chart.data = [list(values.astype(float))]
    chart.categoryAxis.categoryNames = [str(v) for v in show["Kỳ"]]
    chart.categoryAxis.labels.fontName = FONT_NORMAL
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontName = FONT_NORMAL
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = max(0, float(values.min()) * 0.95)
    chart.valueAxis.labelTextFormat = "%0.1f"
    chart.lines[0].strokeColor = _GREEN
    chart.lines[0].strokeWidth = 2
    chart.lines[0].symbol = None
    drawing.add(chart)
    drawing.add(String(width / 2, 79 * mm, "Xu hướng tổng dư nợ ủy thác", fontName=FONT_BOLD, fontSize=10, textAnchor="middle", fillColor=_GREEN_DARK))
    drawing.add(String(width - 2 * mm, 3 * mm, "Đơn vị: tỷ đồng", fontName=FONT_NORMAL, fontSize=7, textAnchor="end", fillColor=_MUTED))
    return drawing


def _insights(
    tong_quan: dict[str, object],
    theo_hoi: pd.DataFrame,
    dieu_hanh_pgd: pd.DataFrame,
    diem_nong_xa: pd.DataFrame,
    diem_nong_to: pd.DataFrame,
    to_da_hoi: pd.DataFrame,
    bien_dong: pd.DataFrame,
) -> list[str]:
    result = [
        f"Tỷ lệ nợ quá hạn trong phạm vi báo cáo là {_fmt_vn(tong_quan.get('ty_le_nqh', 0), 2)}%.",
        f"Có {_fmt_vn(tong_quan.get('so_to_nqh', 0))} Tổ phát sinh NQH và "
        f"{_fmt_vn(tong_quan.get('so_to_lai_ton', 0))} Tổ phát sinh lãi tồn.",
    ]
    if theo_hoi is not None and not theo_hoi.empty and "Hội đoàn thể" in theo_hoi.columns and "Dư nợ (triệu đồng)" in theo_hoi.columns:
        top = theo_hoi.sort_values("Dư nợ (triệu đồng)", ascending=False).iloc[0]
        result.append(
            f"Hội có quy mô dư nợ lớn nhất là {top['Hội đoàn thể']} với "
            f"{_fmt_vn(float(top['Dư nợ (triệu đồng)']) / 1e9, 3)} tỷ đồng."
        )
    if dieu_hanh_pgd is not None and not dieu_hanh_pgd.empty and "PGD" in dieu_hanh_pgd.columns and "NQH (triệu đồng)" in dieu_hanh_pgd.columns:
        top = dieu_hanh_pgd.sort_values("NQH (triệu đồng)", ascending=False).iloc[0]
        result.append(
            f"PGD có NQH cao nhất trong phạm vi là {top['PGD']} với "
            f"{_fmt_vn(float(top['NQH (triệu đồng)']) / 1e6)} triệu đồng."
        )
    result.append(
        f"Danh sách ưu tiên gồm {len(diem_nong_xa) if diem_nong_xa is not None else 0} xã/phường, "
        f"{len(diem_nong_to) if diem_nong_to is not None else 0} Tổ điểm nóng và "
        f"{len(to_da_hoi) if to_da_hoi is not None else 0} Tổ xuất hiện ở nhiều Hội."
    )
    if bien_dong is not None and len(bien_dong) >= 2 and "Tổng dư nợ (triệu đồng)" in bien_dong.columns:
        _col = pd.to_numeric(bien_dong["Tổng dư nợ (triệu đồng)"], errors="coerce").fillna(0)
        latest = float(_col.iloc[-1])    # kỳ mới nhất
        previous = float(_col.iloc[0])  # kỳ gốc / baseline (đầu DataFrame = cũ nhất)
        result.append(
            f"So với kỳ gốc, tổng dư nợ thay đổi {_fmt_vn((latest - previous) / 1e6, signed=True)} triệu đồng."
        )
    return result


def _prepare_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Định dạng cột giá trị cảnh báo hỗn hợp theo đúng đơn vị nghiệp vụ."""
    if df is None or df.empty or "Giá trị" not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    result = df.copy()

    def _format_alert_value(row: pd.Series) -> str:
        group = str(row.get("Nhóm cảnh báo", "") or "").lower()
        value = row.get("Giá trị", 0)
        if "nợ quá hạn" in group or "lãi tồn" in group:
            return _fmt_vn(float(value or 0) / 1e6) + " triệu đồng"
        if "tổ đa hội" in group:
            return _fmt_vn(value) + " Hội"
        if "kiến nghị quá hạn" in group:
            return _fmt_vn(value) + " ngày"
        return _fmt_vn(value) if isinstance(value, (int, float)) else str(value)

    result["Giá trị cảnh báo"] = result.apply(_format_alert_value, axis=1)
    return result.drop(columns=["Giá trị"])


def _build_pdf(story: list, buffer: BytesIO) -> bytes:
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=13 * mm,
        rightMargin=13 * mm,
        topMargin=11 * mm,
        bottomMargin=16 * mm,
        title="Báo cáo Ủy thác",
        author=TEN_CHI_NHANH_HIEN_THI,
    )
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    result = buffer.getvalue()
    buffer.close()
    return result


def tao_pdf_bao_cao_dang_xem(
    df: pd.DataFrame,
    ten_bao_cao: str,
    tong_quan: dict[str, object],
    pham_vi: str,
    ngay_so_lieu: object,
    nguoi_xuat: str,
    bo_loc: Iterable[str] | None = None,
) -> bytes:
    """Tạo PDF đúng báo cáo/bộ lọc người dùng đang xem."""
    styles = _styles()
    page_size = landscape(A4)
    usable_w = page_size[0] - 26 * mm
    story: list = []
    _header(
        story,
        f"Báo cáo Ủy thác - {ten_bao_cao}",
        "Báo cáo theo đúng phạm vi và bộ lọc đang hiển thị trên hệ thống",
        styles,
        usable_w,
    )
    story.append(_meta_table(pham_vi, ngay_so_lieu, nguoi_xuat, bo_loc, styles, usable_w))
    story.append(Spacer(1, 7))
    story.append(_kpi_table(tong_quan, styles, usable_w))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Chi tiết báo cáo", styles["section"]))
    _append_dataframe(story, df, styles, usable_w, max_rows=250)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Đơn vị tiền trong các cột ghi '(triệu đồng)' đã được quy đổi từ VND sang triệu đồng khi tạo PDF.",
        styles["note"],
    ))
    return _build_pdf(story, BytesIO())


def tao_pdf_dieu_hanh_uy_thac(
    *,
    tong_quan: dict[str, object],
    pham_vi: str,
    ngay_so_lieu: object,
    nguoi_xuat: str,
    bo_loc: Iterable[str] | None,
    theo_hoi: pd.DataFrame,
    dieu_hanh_pgd: pd.DataFrame,
    diem_nong_xa: pd.DataFrame,
    diem_nong_to: pd.DataFrame,
    canh_bao: pd.DataFrame,
    to_da_hoi: pd.DataFrame,
    bien_dong: pd.DataFrame,
) -> bytes:
    """Tạo bộ PDF điều hành Ủy thác nhiều phần, không phụ thuộc Microsoft Word."""
    styles = _styles()
    canh_bao = _prepare_alerts(canh_bao)
    page_size = landscape(A4)
    usable_w = page_size[0] - 26 * mm
    story: list = []
    _header(
        story,
        "Báo cáo điều hành hoạt động Ủy thác",
        "Quy mô - chất lượng - cảnh báo - điểm nóng - biến động nhiều kỳ",
        styles,
        usable_w,
    )
    story.append(_meta_table(pham_vi, ngay_so_lieu, nguoi_xuat, bo_loc, styles, usable_w))
    story.append(Spacer(1, 7))
    story.append(_kpi_table(tong_quan, styles, usable_w))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Nhận định điều hành", styles["section"]))
    for line in _insights(tong_quan, theo_hoi, dieu_hanh_pgd, diem_nong_xa, diem_nong_to, to_da_hoi, bien_dong):
        story.append(Paragraph(f"- {escape(line)}", styles["body"]))

    chart_hoi = _bar_chart(
        theo_hoi, "Hội đoàn thể", "Dư nợ (triệu đồng)",
        "Cơ cấu dư nợ theo Hội đoàn thể", usable_w / 2 - 3 * mm, top_n=6,
    )
    chart_pgd = _bar_chart(
        dieu_hanh_pgd, "PGD", "NQH (triệu đồng)",
        "Các PGD có nợ quá hạn cao", usable_w / 2 - 3 * mm, top_n=6,
    )
    if chart_hoi is not None or chart_pgd is not None:
        story.append(PageBreak())
        story.append(Paragraph("Biểu đồ cơ cấu và chất lượng", styles["section"]))
        chart_row = Table(
            [[chart_hoi or "", chart_pgd or ""]],
            colWidths=[usable_w / 2, usable_w / 2],
        )
        chart_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(chart_row)

    chart_trend = _trend_chart(bien_dong, usable_w)
    if chart_trend is not None:
        story.append(PageBreak())
        story.append(Paragraph("Biểu đồ biến động nhiều kỳ", styles["section"]))
        story.append(chart_trend)

    sections = [
        ("1. Cơ cấu và chất lượng theo Hội đoàn thể", theo_hoi, 20),
        ("2. Điều hành theo PGD", dieu_hanh_pgd, 30),
        ("3. Cảnh báo trọng điểm", canh_bao, 40),
        ("4. Điểm nóng xã/phường", diem_nong_xa, 35),
        ("5. Điểm nóng Tổ TK&VV", diem_nong_to, 40),
        ("6. Tổ xuất hiện ở nhiều Hội", to_da_hoi, 50),
        ("7. Biến động nhiều kỳ", bien_dong, 24),
    ]
    for title, data, max_rows in sections:
        story.append(PageBreak())
        story.append(Paragraph(title, styles["section"]))
        _append_dataframe(story, data, styles, usable_w, max_rows=max_rows)

    story.append(PageBreak())
    story.append(Paragraph("8. Hành động đề xuất", styles["section"]))
    actions = [
        "Ưu tiên rà soát các PGD, xã/phường và Tổ có NQH hoặc lãi tồn cao trong danh sách điểm nóng.",
        "Đối chiếu lại Hội nhận ủy thác đối với các Tổ xuất hiện ở nhiều Hội trong HSTD.",
        "Giao thời hạn xử lý cụ thể cho từng cảnh báo trọng điểm và cập nhật kết quả tại mục Theo dõi kiến nghị.",
        "Theo dõi biến động tối thiểu 6 kỳ để phân biệt phát sinh nhất thời với xu hướng chất lượng kéo dài.",
    ]
    for action in actions:
        story.append(Paragraph(f"- {escape(action)}", styles["body"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Lưu ý: Điểm rủi ro và danh sách điểm nóng là chỉ báo điều hành nội bộ, không thay thế kết luận kiểm tra nghiệp vụ.",
        styles["note"],
    ))
    return _build_pdf(story, BytesIO())
