"""Tab CBTD — Quản lý Cán bộ Tín dụng theo ĐGD.

Schema (v3):
    cbtd_data[ma_cb] = {
        "ho_ten":         str,
        "chuc_vu":        str,          # Cán bộ tín dụng / Trưởng nhóm / Phó nhóm / Khác
        "ngay_bo_nhiem":  str,          # định dạng DD/MM/YYYY
        "pgd":            str,          # PGD trực thuộc (không chéo PGD)
        "ds_dgd":         list[str],    # Tên ĐGD phụ trách (2-4 ĐGD)
        "dien_thoai":     str,
        "ghi_chu":        str,
        "ngay_cap":       str,
    }
Thôn/ấp được suy ra động từ dgd_map[pgd][xa][dgd] — không lưu trực tiếp.
"""
from __future__ import annotations

import re
from io import BytesIO
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import streamlit as st
import pandas as pd

import db
from config import (
    COT_HINH_THUC_VAY, COT_MA_KH, COT_SO_KU, COT_TEN_THON, COT_TEN_XA,
    COT_TONG_DU_NO, COT_DU_NO_QH, DS_PGD, DON_VI_CHI_NHANH, lay_dgd_cho_pgd,
    TEN_CHI_NHANH_HIEN_THI,
)
from auth import la_phan_he_cn, la_executive, la_quan_ly_cn, normalize_role
from logger import get_logger
from state_manager import SCMStateManager
from utils import xuat_excel, hien_thi_dataframe_phan_trang, fmt_so, fmt_ty
from data.khtd import doc_cbtd, luu_cbtd, lay_ap_tu_dgd_list, gan_cbtd_vao_df

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

logger = get_logger(__name__)

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

CHUC_VU_OPTS = ["Cán bộ tín dụng", "Trưởng nhóm", "Phó nhóm", "Khác"]
_NGUONG_DGD_QUATAI = 5
_NGUONG_DGD_THIEUTAI = 1
_SDT_REGEX = re.compile(r"^[0-9+\-\s]{8,15}$")
_MA_CB_REGEX = re.compile(r"^CB[A-Z0-9_-]{2,}$")


def _cbtd_add_form_prefix(key_prefix: str, version: int) -> str:
    """Prefix widget key cho form thêm CBTD; tăng version để reset form sau khi lưu."""
    return f"{key_prefix}cbtd_add_v{version}_"


def _validate_dien_thoai(s: Any) -> tuple[bool, str]:
    """Validate SĐT: rỗng = OK (không bắt buộc); không rỗng phải khớp regex."""
    if not s or not str(s).strip():
        return True, ""
    if not _SDT_REGEX.match(str(s).strip()):
        return False, "Số điện thoại chỉ chứa chữ số, +, -, dấu cách; dài 8-15 ký tự"
    return True, ""


def _validate_ma_cb(s: Any, existed: dict) -> tuple[bool, str]:
    """Validate mã CBTD: không trống, đúng format, không trùng."""
    v = (s or "").strip().upper()
    if not v:
        return False, "Mã CBTD không được trống"
    if not _MA_CB_REGEX.match(v):
        return False, "Mã CBTD phải bắt đầu bằng 'CB' theo sau là chữ/số/ _ /-"
    if v in existed:
        return False, f"Mã {v} đã tồn tại, chọn mã khác"
    return True, ""


def _auto_gen_ma_cb(pgd: str, existed: dict) -> str:
    """Tự sinh mã CBTD duy nhất: CB_{slug}_{3 số}."""
    slug = re.sub(r"[^A-Z0-9]+", "_", pgd.upper().strip()).strip("_") or "CN"
    for i in range(1, 999):
        candidate = f"CB_{slug}_{i:03d}"
        if candidate not in existed:
            return candidate
    return f"CB_{slug}_{datetime.now().strftime('%H%M%S')}"


def _workload_label(so_dgd: int) -> tuple[str, str]:
    """(icon, label) — emoji + text workload."""
    if so_dgd >= _NGUONG_DGD_QUATAI:
        return "🔴", "Quá tải"
    if so_dgd <= _NGUONG_DGD_THIEUTAI:
        return "⚠️", "Thiếu tải"
    return "✅", "Cân bằng"


def _pgd_slug_ma(pgd: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", pgd.upper().strip()).strip("_") or "CN"


def _ddmmyyyy_to_date(s: Any) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s).strip(), "%d/%m/%Y").date()
    except Exception:
        return None


def _date_to_ddmmyyyy(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _build_profile_pdf(ma_cb: str, info: dict, kpi_hstd: dict | None,
                       tos_info: list[dict] | None,
                       pgd_user_override: str | None = None) -> bytes | None:
    """Tạo PDF hồ sơ năng lực CBTD (A4). Trả về bytes hoặc None nếu lỗi.

    Khối: Header đơn vị + Thông tin cá nhân + Địa bàn phụ trách + KPI HSTD
          + Bảng Tổ TK&VV + Khối ký tên (3 vị trí).
    """
    try:
        from services.pdf_service import (
            _register_vbsp_fonts, _VBSP_GREEN, _VBSP_GREEN_LIGHT, _VBSP_ACCENT,
            _set_col_ratio, _PAGE_WIDTH, _PAGE_HEIGHT, _MARGIN,
        )
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm, cm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )
        from reportlab.pdfbase.pdfmetrics import stringWidth

        _register_vbsp_fonts()
        buf = BytesIO()
        page_w, page_h = A4

        ngay_str = datetime.today().strftime("%d/%m/%Y")
        ho_ten = info.get("ho_ten", "")
        pgd = info.get("pgd", "") or (pgd_user_override or "")
        chuc_vu = info.get("chuc_vu", "") or "Cán bộ tín dụng"
        ngay_bn = info.get("ngay_bo_nhiem", "") or "—"
        dien_thoai = info.get("dien_thoai", "") or "—"
        ghi_chu = info.get("ghi_chu", "") or "—"
        ds_dgd = info.get("ds_dgd", []) or []

        def _on_page(canvas, doc):
            canvas.saveState()
            # Header kẻ xanh
            canvas.setStrokeColor(_VBSP_GREEN)
            canvas.setLineWidth(1.4)
            canvas.line(_MARGIN, page_h - _MARGIN + 4, page_w - _MARGIN, page_h - _MARGIN + 4)
            canvas.setFont("Times-Bold", 9)
            canvas.setFillColor(_VBSP_GREEN)
            canvas.drawString(_MARGIN, page_h - _MARGIN + 10,
                              TEN_CHI_NHANH_HIEN_THI or "Ngân hàng Chính sách Xã hội - Chi nhánh Đồng Nai")
            canvas.setFont("Times-Roman", 8)
            canvas.setFillColor(colors.black)
            canvas.drawRightString(page_w - _MARGIN, page_h - _MARGIN + 10,
                                   f"Ngày in: {ngay_str}")
            # Footer
            canvas.setStrokeColor(_VBSP_ACCENT)
            canvas.setLineWidth(0.6)
            canvas.line(_MARGIN, _MARGIN - 10, page_w - _MARGIN, _MARGIN - 10)
            canvas.setFont("Times-Roman", 7.5)
            canvas.setFillColor(colors.black)
            canvas.drawString(_MARGIN, _MARGIN - 22,
                              "Hồ sơ năng lực CBTD — Hệ thống Quản trị Tín dụng Nội bộ")
            canvas.drawRightString(page_w - _MARGIN, _MARGIN - 22,
                                   f"Trang {doc.page}    |    In lúc {datetime.today().strftime('%d/%m/%Y %H:%M')}")
            canvas.restoreState()

        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=_MARGIN, rightMargin=_MARGIN,
            topMargin=_MARGIN + 14, bottomMargin=_MARGIN + 6,
            title=f"Hồ sơ năng lực CBTD - {ma_cb} - {ho_ten}",
            author="VBSP ĐN SCM",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("T", parent=styles["Title"], fontName="Times-Bold",
                                     fontSize=16, textColor=_VBSP_GREEN,
                                     alignment=TA_CENTER, spaceAfter=2)
        sub_style = ParagraphStyle("S", parent=styles["Normal"], fontName="Times-Italic",
                                   fontSize=10, alignment=TA_CENTER, textColor=colors.grey,
                                   spaceAfter=8)
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Times-Bold",
                            fontSize=12, textColor=_VBSP_GREEN, spaceBefore=6, spaceAfter=3)
        info_key = ParagraphStyle("IK", parent=styles["Normal"], fontName="Times-Bold",
                                  fontSize=10.5, leading=15)
        info_val = ParagraphStyle("IV", parent=styles["Normal"], fontName="Times-Roman",
                                  fontSize=10.5, leading=15)
        th_style = ParagraphStyle("TH", parent=styles["Normal"], fontName="Times-Bold",
                                  fontSize=9.5, textColor=colors.whiter, alignment=TA_CENTER,
                                  leading=13)
        td_style = ParagraphStyle("TD", parent=styles["Normal"], fontName="Times-Roman",
                                  fontSize=9.5, alignment=TA_CENTER, leading=13)
        td_left = ParagraphStyle("TL", parent=td_style, alignment=TA_LEFT)
        td_right = ParagraphStyle("TR", parent=td_style, alignment=TA_RIGHT)

        story = []
        # Header tiêu đề
        story.append(Paragraph("HỒ SƠ NĂNG LỰC CÁN BỘ TÍN DỤNG", title_style))
        story.append(Paragraph(f"Mã CBTD: {ma_cb} &nbsp;&nbsp;|&nbsp;&nbsp; "
                               f"PGD: {pgd} &nbsp;&nbsp;|&nbsp;&nbsp; In ngày {ngay_str}", sub_style))
        story.append(HRFlowable(width="100%", thickness=1.2, color=_VBSP_GREEN,
                                spaceBefore=0, spaceAfter=6))

        # --- Khối 1: Thông tin cá nhân ---
        story.append(Paragraph("1. Thông tin cá nhân", h2))
        info_rows = [
            ["Họ và tên:", ho_ten, "Chức vụ:", chuc_vu],
            ["Đơn vị PGD:", pgd, "Ngày bổ nhiệm:", ngay_bn],
            ["Điện thoại:", dien_thoai, "Số ĐGD phụ trách:", f"{len(ds_dgd)} ĐGD"],
            ["Ghi chú:", ghi_chu, "Mã CBTD:", ma_cb],
        ]
        tbl_info_data = []
        for r in info_rows:
            tbl_info_data.append([
                Paragraph(r[0], info_key), Paragraph(r[1], info_val),
                Paragraph(r[2], info_key), Paragraph(r[3], info_val),
            ])
        tbl_info = Table(tbl_info_data,
                         colWidths=[3*cm, 7.2*cm, 3.3*cm, 6.5*cm],
                         hAlign="LEFT")
        tbl_info.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(tbl_info)
        story.append(Spacer(1, 4))

        # --- Khối 2: Địa bàn phụ trách ---
        story.append(Paragraph("2. Địa bàn phụ trách (Điểm Giao Dịch / Thôn ấp)", h2))
        dgd_rows: list[list] = [[
            Paragraph("STT", th_style), Paragraph("Điểm Giao Dịch", th_style),
            Paragraph("Số ấp/thôn phụ trách", th_style), Paragraph("Danh sách ấp/thôn", th_style),
        ]]
        # Load dgd_map mới để đếm ấp
        dgd_map_pdf = db.doc_dgd_map() or {}
        tong_ap = 0
        for idx, dgd_name in enumerate(ds_dgd, 1):
            ap_list_pdf: list[str] = []
            for _, dgd_block in dgd_map_pdf.get(pgd, {}).items():
                if isinstance(dgd_block, dict) and dgd_name in dgd_block:
                    entry = dgd_block[dgd_name]
                    raw = entry.get("thon", []) if isinstance(entry, dict) else (entry or [])
                    ap_list_pdf = [str(a).strip() for a in raw if str(a).strip()]
                    break
            tong_ap += len(ap_list_pdf)
            dgd_rows.append([
                Paragraph(str(idx), td_style),
                Paragraph(dgd_name, td_left),
                Paragraph(str(len(ap_list_pdf)), td_style),
                Paragraph(", ".join(ap_list_pdf) or "—", td_left),
            ])
        # Tổng cộng
        dgd_rows.append([
            Paragraph("", td_style),
            Paragraph("<b>Tổng cộng</b>", td_left),
            Paragraph(f"<b>{len(ds_dgd)} ĐGD / {tong_ap} ấp</b>", td_style),
            Paragraph("", td_style),
        ])
        tbl_dgd = Table(dgd_rows, colWidths=[1.2*cm, 4.5*cm, 3.5*cm, 10.8*cm], hAlign="LEFT")
        tstyle_dgd = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-2, -2), [colors.white, _VBSP_GREEN_LIGHT]),
        ])
        # Highlight dòng tổng
        tstyle_dgd.add("BACKGROUND", (0, -1), (-1, -1), _VBSP_GREEN_LIGHT)
        tstyle_dgd.add("FONTNAME", (0, -1), (-1, -1), "Times-Bold")
        tbl_dgd.setStyle(tstyle_dgd)
        story.append(tbl_dgd)
        story.append(Spacer(1, 6))

        # --- Khối 3: KPI HSTD ---
        story.append(Paragraph("3. Kết quả HSTD (từ dữ liệu mới nhất)", h2))
        if kpi_hstd:
            kpi_rows = [[
                Paragraph("Số KH", th_style), Paragraph("Số món vay", th_style),
                Paragraph("Tổng dư nợ (tỷ đồng)", th_style),
                Paragraph("Dư nợ QH (tỷ đồng)", th_style), Paragraph("Tỷ lệ QH", th_style),
            ]]
            so_kh_v = str(kpi_hstd.get("so_kh", "—"))
            so_mon_v = str(kpi_hstd.get("so_mon_vay", "—"))
            dn_v = f"{float(kpi_hstd.get('du_no_ty', 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            qh_v = f"{float(kpi_hstd.get('du_no_qh_ty', 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            tl_v = f"{float(kpi_hstd.get('tl_qh_pct', 0)):,.2f} %".replace(",", "X").replace(".", ",").replace("X", ".")
            kpi_rows.append([
                Paragraph(so_kh_v, td_style), Paragraph(so_mon_v, td_style),
                Paragraph(dn_v, td_right), Paragraph(qh_v, td_right),
                Paragraph(tl_v, td_right),
            ])
            tbl_kpi = Table(kpi_rows, colWidths=[3.5*cm, 3.5*cm, 4.5*cm, 4.5*cm, 4*cm], hAlign="LEFT")
            tbl_kpi.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tbl_kpi)
        else:
            story.append(Paragraph("(Chưa có dữ liệu HSTD cho địa bàn CBTD này)",
                                   ParagraphStyle("NN", parent=styles["Normal"],
                                                  fontName="Times-Italic", textColor=colors.grey)))
        story.append(Spacer(1, 6))

        # --- Khối 4: Tổ TK&VV ---
        story.append(Paragraph("4. Danh sách Tổ TK&VV thuộc địa bàn", h2))
        if tos_info:
            to_rows = [[
                Paragraph("STT", th_style), Paragraph("Xã", th_style),
                Paragraph("ĐGD", th_style), Paragraph("Mã Tổ", th_style),
                Paragraph("Tổ trưởng", th_style),
                Paragraph("Xếp loại", th_style), Paragraph("Điểm", th_style),
            ]]
            for i, t in enumerate(tos_info, 1):
                to_rows.append([
                    Paragraph(str(i), td_style),
                    Paragraph(str(t.get("ten_xa", "—")), td_left),
                    Paragraph(str(t.get("dgd", "—")), td_left),
                    Paragraph(str(t.get("ma_to", "—")), td_style),
                    Paragraph(str(t.get("ten_to_truong", "—")), td_left),
                    Paragraph(str(t.get("xep_loai", "—")), td_style),
                    Paragraph(str(t.get("tong_diem", "—")), td_right),
                ])
            tbl_to = Table(to_rows,
                           colWidths=[1*cm, 3*cm, 2.8*cm, 2.5*cm, 4.2*cm, 2.5*cm, 2*cm],
                           hAlign="LEFT", repeatRows=1)
            tbl_to.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _VBSP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _VBSP_GREEN_LIGHT]),
            ]))
            story.append(tbl_to)
        else:
            story.append(Paragraph("(Chưa có dữ liệu Tổ TK&VV)",
                                   ParagraphStyle("NN2", parent=styles["Normal"],
                                                  fontName="Times-Italic", textColor=colors.grey)))

        story.append(Spacer(1, 18))

        # --- Khối 5: Ký tên 3 vị trí ---
        s_k1 = ParagraphStyle("k1", parent=styles["Normal"], fontName="Times-Bold",
                              fontSize=10.5, alignment=TA_CENTER)
        s_k2 = ParagraphStyle("k2", parent=styles["Normal"], fontName="Times-Italic",
                              fontSize=9.5, alignment=TA_CENTER, textColor=colors.grey,
                              leading=13)
        ky_row = [[
            Paragraph("Người lập", s_k1),
            Paragraph("Phòng Tổ chức Cán bộ", s_k1),
            Paragraph("Giám đốc Chi nhánh", s_k1),
        ]]
        ky_spacer = [[
            Paragraph("&nbsp;<br/>&nbsp;<br/>&nbsp;<br/>&nbsp;", s_k2),
            Paragraph("&nbsp;<br/>&nbsp;<br/>&nbsp;<br/>&nbsp;", s_k2),
            Paragraph("&nbsp;<br/>&nbsp;<br/>&nbsp;<br/>&nbsp;", s_k2),
        ]]
        ky_note = [[
            Paragraph("(Ký, ghi rõ họ tên)", s_k2),
            Paragraph("(Ký, họ tên, đóng dấu)", s_k2),
            Paragraph("(Ký, họ tên, đóng dấu)", s_k2),
        ]]
        combined = [ky_row[0], ky_spacer[0], ky_note[0]]
        tbl_ky = Table(combined, colWidths=[(page_w-2*_MARGIN)/3]*3, hAlign="CENTER")
        tbl_ky.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(tbl_ky)

        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        return buf.getvalue()
    except Exception as e:
        logger.error("_build_profile_pdf(%s) — %s", ma_cb, e, exc_info=True)
        return None


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")  # PGD mode filter
    state = SCMStateManager()
    _kp = f"pgd_{pgd_user.strip().lower().replace(' ', '_')}_" if pgd_user else "cn_"

    import streamlit as _st
    ctx = tab if tab is not None else _st.container()

    with ctx:
        st.subheader("👔 Quản lý Cán bộ Tín dụng (CBTD)")
        if pgd_user:
            st.caption(f"1 CBTD phụ trách 2–4 Điểm giao dịch (ĐGD) trong PGD **{pgd_user}**. "
                       "Thôn/ấp được suy ra tự động từ cấu hình ĐGD.")
        else:
            st.caption("1 CBTD phụ trách 2–4 Điểm giao dịch (ĐGD) trong cùng PGD. "
                       "Thôn/ấp được suy ra tự động từ cấu hình ĐGD.")

        cbtd_data_raw: dict = doc_cbtd()
        # Filter theo PGD nếu có pgd_user
        if pgd_user:
            cbtd_data = {
                k: v for k, v in cbtd_data_raw.items()
                if str(v.get("pgd", "")).strip().lower() == pgd_user.strip().lower()
            }
        else:
            cbtd_data = cbtd_data_raw

        dgd_map: dict = db.doc_dgd_map() or {}

        if not dgd_map:
            st.warning("⚠️ Chưa cấu hình Điểm giao dịch. "
                       "Vào tab **📍 Điểm GD** để cấu hình trước.")

        # ── Dữ liệu tính toán chung ──────────────────────────────────────────
        # Dict (pgd, dgd_name) → (ma_cb, ten_cb) — phát hiện trùng ĐGD
        dgd_da_phan: dict[tuple[str, str], tuple[str, str]] = {}
        for ma_cb, info in cbtd_data.items():
            pgd_cb = info.get("pgd", "")
            for dgd in info.get("ds_dgd", []):
                dgd_da_phan[(pgd_cb, dgd)] = (ma_cb, info.get("ho_ten", ""))

        # ── Helpers ──────────────────────────────────────────────────────────
        def _ds_dgd_cua_pgd(pgd: str) -> list[tuple[str, str]]:
            """[(xa, dgd_name)] — toàn bộ ĐGD trong PGD (từ DGD_DANH_SACH)."""
            dgd_list = lay_dgd_cho_pgd(pgd)
            return [(d["xa"], d["ten"]) for d in dgd_list]

        def _label_dgd(xa: str, dgd_name: str) -> str:
            return f"{xa} — {dgd_name}"

        def _ap_cua_dgd(pgd: str, dgd_name: str) -> list[str]:
            """List ấp của một ĐGD từ dgd_map (schema mới: dict với key 'thon')."""
            for xa, dgd_block in dgd_map.get(pgd, {}).items():
                if isinstance(dgd_block, dict) and dgd_name in dgd_block:
                    entry = dgd_block[dgd_name]
                    if isinstance(entry, dict):
                        thon_list = entry.get("thon", [])
                    elif isinstance(entry, list):
                        thon_list = entry
                    else:
                        thon_list = []
                    return [str(a).strip() for a in thon_list if str(a).strip()]
            return []

        def _so_ap_cbtd(info: dict) -> int:
            pgd = info.get("pgd", "")
            ds_dgd = info.get("ds_dgd", [])
            return len(lay_ap_tu_dgd_list(pgd, ds_dgd, dgd_map))

        def _kiem_tra_trung_dgd(pgd: str, ds_dgd: list[str], bo_qua_ma: str | None = None) -> dict[str, str]:
            """Trả về {dgd_name: 'ma_cb — ten_cb'} cho ĐGD đã bị chiếm."""
            trung = {}
            for dgd_name in ds_dgd:
                found = dgd_da_phan.get((pgd, dgd_name))
                if found and found[0] != bo_qua_ma:
                    trung[dgd_name] = f"{found[0]} — {found[1]}"
            return trung

        def _fmt_tien(x: float) -> str:
            try:
                x = float(x)
                if abs(x) > 0:
                    return f"{x/1_000_000:,.0f}".replace(",","X").replace(".",",").replace("X",".")
                return "—"
            except Exception:
                return "—"

        # ════════════════════════════════════════════════════════════════════
        # 3 SUB-TAB XEM
        # ════════════════════════════════════════════════════════════════════
        xem1, xem2, xem3 = st.tabs([
            "📋 Danh sách CBTD",
            "🗺️ Bản đồ ĐGD → CBTD",
            "🔎 Chi tiết CBTD",
        ])

        # ── SUB-TAB 1: Danh sách ─────────────────────────────────────────────
        with xem1:
            if not cbtd_data:
                st.info("Chưa có CBTD nào. Thêm mới bên dưới.")
            else:
                tong_dgd = sum(len(i.get("ds_dgd", [])) for i in cbtd_data.values())
                tong_ap  = sum(_so_ap_cbtd(i) for i in cbtd_data.values())
                so_quatai = sum(1 for i in cbtd_data.values()
                                if len(i.get("ds_dgd", [])) >= _NGUONG_DGD_QUATAI)
                so_thieutai = sum(1 for i in cbtd_data.values()
                                  if 0 < len(i.get("ds_dgd", [])) <= _NGUONG_DGD_THIEUTAI)
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Số CBTD", len(cbtd_data))
                c2.metric("Tổng ĐGD đã phân", tong_dgd)
                c3.metric("Tổng ấp phụ trách", tong_ap)
                c4.metric("🔴 Quá tải (≥5 ĐGD)", so_quatai, delta=None, delta_color="inverse")
                c5.metric("⚠️ Thiếu tải (≤1 ĐGD)", so_thieutai, delta=None, delta_color="off")

                # Bộ lọc mạnh
                with st.container(border=True):
                    fc1, fc2, fc3, fc4 = st.columns(4)
                    pgd_all_opt = ["Tất cả"] + sorted(
                        {str(v.get("pgd", "")).strip() for v in cbtd_data.values() if v.get("pgd")})
                    loc_pgd = fc1.selectbox("Lọc PGD", pgd_all_opt, key=f"{_kp}ds_loc_pgd")
                    loc_wl  = fc2.selectbox("Workload",
                        ["Tất cả", "🔴 Quá tải", "✅ Cân bằng", "⚠️ Thiếu tải"],
                        key=f"{_kp}ds_loc_wl")
                    loc_min_dgd = fc3.number_input("Số ĐGD ≥", min_value=0, max_value=20,
                                                   value=0, step=1, key=f"{_kp}ds_loc_min")
                    loc_max_dgd = fc4.number_input("Số ĐGD ≤", min_value=0, max_value=50,
                                                   value=20, step=1, key=f"{_kp}ds_loc_max")
                    fcc1, fcc2 = st.columns([3, 1])
                    loc_search = fcc1.text_input(
                        "🔎 Tìm (Mã / Họ tên / ĐT / Ghi chú)",
                        key=f"{_kp}ds_loc_search",
                        placeholder="vd: CB, Nguyễn Văn, 091...")
                    loc_sort = fcc2.selectbox("Sắp xếp theo",
                        ["Cập nhật mới nhất", "Số ĐGD (giam)", "Số ấp (giam)",
                         "PGD → Mã CBTD", "Họ tên"],
                        key=f"{_kp}ds_loc_sort")

                rows = []
                for ma, info in cbtd_data.items():
                    pgd_cb = info.get("pgd", "—") or "—"
                    ds_dgd = info.get("ds_dgd", []) or []
                    so_dgd = len(ds_dgd)
                    so_ap  = _so_ap_cbtd(info)
                    wl_icon, wl_txt = _workload_label(so_dgd)
                    # Bộ lọc
                    if loc_pgd != "Tất cả" and pgd_cb != loc_pgd:
                        continue
                    if loc_wl != "Tất cả":
                        if loc_wl == "🔴 Quá tải" and wl_icon != "🔴": continue
                        if loc_wl == "✅ Cân bằng" and wl_icon != "✅": continue
                        if loc_wl == "⚠️ Thiếu tải" and wl_icon != "⚠️": continue
                    if so_dgd < loc_min_dgd or so_dgd > loc_max_dgd:
                        continue
                    if loc_search.strip():
                        needle = loc_search.strip().lower()
                        haystack = " ".join([
                            ma.lower(),
                            str(info.get("ho_ten", "")).lower(),
                            str(info.get("dien_thoai", "")).lower(),
                            str(info.get("ghi_chu", "")).lower(),
                            str(info.get("chuc_vu", "")).lower(),
                        ])
                        if needle not in haystack:
                            continue
                    dgd_tom_tat = " | ".join(ds_dgd[:4]) + ("…" if len(ds_dgd) > 4 else "")
                    status = "✅ Đầy đủ" if ds_dgd and pgd_cb != "—" else "⚠️ Cần cập nhật"
                    cv = info.get("chuc_vu", "") or "—"
                    nbn = info.get("ngay_bo_nhiem", "") or "—"
                    rows.append({
                        "Mã CBTD":    ma,
                        "Họ tên":     info.get("ho_ten", ""),
                        "Chức vụ":    cv,
                        "Ngày bổ nhiệm": nbn,
                        "PGD":        pgd_cb,
                        "Điện thoại": info.get("dien_thoai", "") or "—",
                        "Số ĐGD":    so_dgd,
                        "Số ấp":     so_ap,
                        "Workload":  f"{wl_icon} {wl_txt}",
                        "ĐGD phụ trách": dgd_tom_tat or "—",
                        "Trạng thái": status,
                        "Cập nhật":  info.get("ngay_cap", ""),
                        "__sort_time": info.get("ngay_cap", ""),
                        "__pgd_sort": (pgd_cb, ma),
                        "__ten_sort": str(info.get("ho_ten", "")).lower(),
                    })

                # Sort
                if rows:
                    if loc_sort == "Cập nhật mới nhất":
                        rows.sort(key=lambda r: r["__sort_time"], reverse=True)
                    elif loc_sort == "Số ĐGD (giam)":
                        rows.sort(key=lambda r: r["Số ĐGD"], reverse=True)
                    elif loc_sort == "Số ấp (giam)":
                        rows.sort(key=lambda r: r["Số ấp"], reverse=True)
                    elif loc_sort == "PGD → Mã CBTD":
                        rows.sort(key=lambda r: r["__pgd_sort"])
                    else:
                        rows.sort(key=lambda r: r["__ten_sort"])
                    df_hien = pd.DataFrame([{k:v for k,v in r.items() if not k.startswith("__")}
                                            for r in rows])
                    st.caption(f"✅ Hiển thị **{len(df_hien)} / {len(cbtd_data)}** CBTD.")
                    hien_thi_dataframe_phan_trang(df_hien, key=f"{_kp}cbtd_ds", height=460)
                else:
                    st.info("🗂️ Không có CBTD nào khớp bộ lọc.")

                # ĐGD chưa có CBTD
                tong_dgd_cfg = sum(
                    len(dgd_block)
                    for xa_block in dgd_map.values()
                    for dgd_block in xa_block.values()
                    if isinstance(dgd_block, dict)
                )
                so_chua = tong_dgd_cfg - len(dgd_da_phan)
                if so_chua > 0:
                    with st.expander(f"⚠️ {so_chua} ĐGD chưa có CBTD phụ trách"):
                        for pgd_k, xa_block in dgd_map.items():
                            for xa_k, dgd_block in xa_block.items():
                                if not isinstance(dgd_block, dict):
                                    continue
                                chua = [d for d in dgd_block if (pgd_k, d) not in dgd_da_phan]
                                if chua:
                                    st.caption(f"**{pgd_k} / {xa_k}:** {', '.join(chua)}")

        # ── SUB-TAB 2: Bản đồ ĐGD → CBTD ────────────────────────────────────
        with xem2:
            st.caption("Toàn bộ ĐGD và CBTD phụ trách. Dễ kiểm tra trùng, thiếu.")
            if not dgd_map:
                st.warning("Chưa có cấu hình ĐGD.")
            else:
                pgd_opts = ["Tất cả"] + [p for p in dgd_map if dgd_map[p]]
                loc_pgd = st.selectbox("Lọc theo PGD", pgd_opts, key=f"{_kp}bd_pgd")
                loc_tt  = st.selectbox("Tình trạng",
                    ["Tất cả", "✅ Đã phân", "⚠️ Chưa phân"], key=f"{_kp}bd_tt")

                rows_bd = []
                for pgd_k, xa_block in dgd_map.items():
                    if loc_pgd != "Tất cả" and pgd_k != loc_pgd:
                        continue
                    for xa_k, dgd_block in xa_block.items():
                        if not isinstance(dgd_block, dict):
                            continue
                        for dgd_name, ap_list in dgd_block.items():
                            assigned = dgd_da_phan.get((pgd_k, dgd_name))
                            tt = "✅ Đã phân" if assigned else "⚠️ Chưa phân"
                            if loc_tt != "Tất cả" and tt != loc_tt:
                                continue
                            rows_bd.append({
                                "PGD":       pgd_k,
                                "Xã":        xa_k,
                                "ĐGD":       dgd_name,
                                "Mã CBTD":   assigned[0] if assigned else "—",
                                "Tên CBTD":  assigned[1] if assigned else "—",
                                "Số ấp":     len(ap_list or []),
                                "Tình trạng": tt,
                            })

                if rows_bd:
                    df_bd = pd.DataFrame(rows_bd)
                    m1, m2 = st.columns(2)
                    m1.metric("Tổng ĐGD", len(df_bd))
                    m2.metric("Chưa phân CBTD", len(df_bd[df_bd["Tình trạng"]=="⚠️ Chưa phân"]))
                    hien_thi_dataframe_phan_trang(df_bd, key=f"{_kp}cbtd_bd_dgd", height=420)
                else:
                    st.info("Không có ĐGD nào phù hợp bộ lọc.")

        # ── SUB-TAB 3: Chi tiết từng CBTD ────────────────────────────────────
        with xem3:
            if not cbtd_data:
                st.info("Chưa có CBTD nào.")
            else:
                opts_xem = {
                    ma: f"{ma} — {info['ho_ten']} / {info.get('pgd','?')} "
                        f"({len(info.get('ds_dgd',[]))} ĐGD)"
                    for ma, info in cbtd_data.items()
                }
                chon = st.selectbox("Chọn CBTD", list(opts_xem.keys()),
                                    format_func=lambda k: opts_xem[k],
                                    key=f"{_kp}cbtd_chon_xem")
                info_xem = cbtd_data[chon]
                pgd_xem  = info_xem.get("pgd", "")
                ds_dgd_xem = info_xem.get("ds_dgd", []) or []
                chuc_vu_xem = info_xem.get("chuc_vu", "") or "Cán bộ tín dụng"
                ngay_bn_xem = info_xem.get("ngay_bo_nhiem", "") or "—"
                so_dgd_xem = len(ds_dgd_xem)
                wl_icon_xem, wl_txt_xem = _workload_label(so_dgd_xem)

                # --- Header info block 6 cột ---
                xv1, xv2, xv3, xv4, xv5, xv6 = st.columns(6)
                xv1.markdown(f"👤 **{info_xem['ho_ten']}**")
                xv2.markdown(f"🏢 {pgd_xem or '—'}")
                xv3.markdown(f"📞 {info_xem.get('dien_thoai','') or '—'}")
                xv4.markdown(f"🎖️ {chuc_vu_xem}")
                xv5.markdown(f"📅 Bổ nhiệm: {ngay_bn_xem}")
                xv6.markdown(f"{wl_icon_xem} WL: {wl_txt_xem} ({so_dgd_xem} ĐGD)")

                # Nút actions: Export PDF + Copy Mã
                xa1, xa2, xa3 = st.columns([1, 1, 4])
                with xa1:
                    if st.button("📄 Xuất Hồ sơ (PDF)", type="secondary",
                                 key=f"{_kp}btn_export_pdf_{chon}",
                                 help="Xuất file PDF A4 hồ sơ năng lực CBTD"):
                        with st.spinner(f"Đang tạo PDF hồ sơ {chon}…"):
                            # Tính KPI HSTD
                            kpi_hstd_dict: dict | None = None
                            tos_cbtd_list: list[dict] | None = None
                            if df is not None and not df.empty and ds_dgd_xem and pgd_xem:
                                try:
                                    df_cb_xem_ct = gan_cbtd_vao_df(df, {chon: info_xem}, dgd_map)
                                    df_cb_xem_ct = df_cb_xem_ct[df_cb_xem_ct["CBTD"] == chon].copy()
                                    if COT_HINH_THUC_VAY in df_cb_xem_ct.columns:
                                        df_cb_xem_ct = df_cb_xem_ct[
                                            df_cb_xem_ct[COT_HINH_THUC_VAY] != 1
                                        ]
                                    tdn_ct = (pd.to_numeric(df_cb_xem_ct[COT_TONG_DU_NO],
                                                            errors="coerce").sum()
                                              if COT_TONG_DU_NO in df_cb_xem_ct.columns else 0)
                                    dqh_ct = (pd.to_numeric(df_cb_xem_ct[COT_DU_NO_QH],
                                                            errors="coerce").sum()
                                              if COT_DU_NO_QH in df_cb_xem_ct.columns else 0)
                                    tlqh_ct = (dqh_ct / tdn_ct * 100) if tdn_ct > 0 else 0
                                    so_kh_ct = (df_cb_xem_ct[COT_MA_KH].nunique()
                                                if COT_MA_KH in df_cb_xem_ct.columns else 0)
                                    so_ku_ct = (df_cb_xem_ct[COT_SO_KU].nunique()
                                                if COT_SO_KU in df_cb_xem_ct.columns else 0)
                                    kpi_hstd_dict = {
                                        "so_kh": int(so_kh_ct),
                                        "so_mon_vay": int(so_ku_ct),
                                        "du_no_ty": round(float(tdn_ct) / 1_000_000_000, 2),
                                        "du_no_qh_ty": round(float(dqh_ct) / 1_000_000_000, 2),
                                        "tl_qh_pct": round(float(tlqh_ct), 2),
                                    }
                                except Exception as e_pdf:
                                    logger.error("tab_cbtd export_pdf KPI — %s", e_pdf,
                                                 exc_info=True)
                            # Lấy list Tổ TK&VV
                            try:
                                from services.cbtd_dia_ban_service import lay_to_theo_cbtd
                                from services.cdtotkvv_service import tong_hop_tu_pgd_data
                                df_cdto_pdf = tong_hop_tu_pgd_data()
                                to_map_pdf = lay_to_theo_cbtd(
                                    {chon: info_xem}, dgd_map, df_cdto_pdf)
                                tos_cbtd_list = to_map_pdf.get(chon, []) or None
                            except Exception as e_pdf2:
                                logger.error("tab_cbtd export_pdf ToTKVV — %s", e_pdf2,
                                             exc_info=True)
                            pdf_bytes = _build_profile_pdf(
                                chon, info_xem, kpi_hstd_dict, tos_cbtd_list,
                                pgd_user_override=pgd_user or None,
                            )
                            if pdf_bytes:
                                from components.export_pdf import download_pdf_button
                                ten_file = f"HS_NL_CBTD_{chon}_{_pgd_slug_ma(pgd_xem or 'CN')}_{datetime.today().strftime('%d%m%Y')}.pdf"
                                download_pdf_button(pdf_bytes=pdf_bytes, ten_file_mau=ten_file,
                                                    label_tai="📥 Tải hồ sơ PDF",
                                                    nut_bam_key=f"{_kp}dl_pdf_{chon}",
                                                    container=st)
                                st.success("✅ Đã tạo PDF hồ sơ năng lực.")
                                db.ghi_audit(username, "xuat_pdf_profile_cbtd",
                                             f"{chon} — {info_xem.get('ho_ten','')}")
                            else:
                                st.error("❌ Lỗi tạo PDF (xem log).")
                with xa2:
                    st.code(chon, language=None)

                st.divider()

                if ds_dgd_xem and pgd_xem:
                    with st.expander(f"📍 {len(ds_dgd_xem)} ĐGD phụ trách", expanded=True):
                        for dgd_name in ds_dgd_xem:
                            ap_list = _ap_cua_dgd(pgd_xem, dgd_name)
                            st.caption(
                                f"**{dgd_name}** ({len(ap_list)} ấp)"
                                + (f": {', '.join(ap_list)}" if ap_list else "")
                            )
                else:
                    st.warning("⚠️ CBTD này chưa được gán ĐGD (dữ liệu cũ). "
                               "Dùng **Chỉnh sửa** để cập nhật.")

                # Dữ liệu hồ sơ từ HSTD
                if df is not None and not df.empty and ds_dgd_xem and pgd_xem:
                    df_cb_xem = gan_cbtd_vao_df(df, {chon: info_xem}, dgd_map)
                    df_cb_xem = df_cb_xem[df_cb_xem["CBTD"] == chon].copy()
                    if COT_HINH_THUC_VAY in df_cb_xem.columns:
                        df_cb_xem = df_cb_xem[df_cb_xem[COT_HINH_THUC_VAY] != 1]

                    tdn = pd.to_numeric(df_cb_xem[COT_TONG_DU_NO], errors="coerce").sum() if COT_TONG_DU_NO in df_cb_xem.columns else 0
                    dqh = pd.to_numeric(df_cb_xem[COT_DU_NO_QH], errors="coerce").sum()   if COT_DU_NO_QH   in df_cb_xem.columns else 0
                    tlqh = (dqh/tdn*100) if tdn > 0 else 0

                    mx1, mx2, mx3, mx4 = st.columns(4)
                    mx1.metric("Số KH",      fmt_so(df_cb_xem[COT_MA_KH].nunique()) if COT_MA_KH in df_cb_xem.columns else "—")
                    mx2.metric("Số món vay", fmt_so(df_cb_xem[COT_SO_KU].nunique()) if COT_SO_KU in df_cb_xem.columns else "—")
                    mx3.metric("Tổng dư nợ (tr.đ)", _fmt_tien(tdn))
                    mx4.metric("Tỷ lệ QH", f"{tlqh:.2f}%",
                               delta="⚠" if tlqh >= 2 else None, delta_color="inverse")

                    if COT_TEN_THON in df_cb_xem.columns and COT_TEN_XA in df_cb_xem.columns:
                        st.markdown("**Tổng hợp theo ấp**")
                        th_ap = df_cb_xem.groupby([COT_TEN_XA, COT_TEN_THON]).agg(
                            Số_KH       =(COT_MA_KH, "nunique"),
                            Tổng_dư_nợ =(COT_TONG_DU_NO, "sum"),
                            Dư_nợ_QH   =(COT_DU_NO_QH, "sum"),
                        ).reset_index().sort_values("Tổng_dư_nợ", ascending=False)
                        th_ap["Tổng dư nợ (tr.đ)"] = th_ap["Tổng_dư_nợ"].apply(_fmt_tien)
                        th_ap["Dư nợ QH (tr.đ)"]   = th_ap["Dư_nợ_QH"].apply(_fmt_tien)
                        th_ap["QH %"] = (th_ap["Dư_nợ_QH"]/th_ap["Tổng_dư_nợ"]*100).fillna(0).round(2)
                        hien_thi_dataframe_phan_trang(
                            th_ap[[COT_TEN_XA, COT_TEN_THON, "Số_KH", "Tổng dư nợ (tr.đ)", "Dư nợ QH (tr.đ)", "QH %"]],
                            key=f"{_kp}cbtd_ct_ap",
                        )

                # ── Cross-link: Tổ TK&VV thuộc địa bàn CBTD ─────────────────
                st.markdown("**🏘️ Tổ TK&VV phụ trách**")
                try:
                    from services.cbtd_dia_ban_service import lay_to_theo_cbtd
                    from services.cdtotkvv_service import tong_hop_tu_pgd_data
                    df_cdto_xem = tong_hop_tu_pgd_data()
                    to_map = lay_to_theo_cbtd({chon: info_xem}, dgd_map, df_cdto_xem)
                    tos_cbtd = to_map.get(chon, [])
                    if not tos_cbtd:
                        st.caption("Chưa có dữ liệu Tổ TK&VV khớp với địa bàn CBTD này.")
                    else:
                        df_tos = pd.DataFrame(tos_cbtd)
                        col_hien = [c for c in ["dgd", "ten_xa", "ma_to", "ten_to_truong",
                                                "xep_loai", "tong_diem", "tinh_trang"]
                                    if c in df_tos.columns]
                        rename_tos = {
                            "dgd": "ĐGD", "ten_xa": "Xã", "ma_to": "Mã Tổ",
                            "ten_to_truong": "Tổ trưởng", "xep_loai": "Xếp loại",
                            "tong_diem": "Điểm", "tinh_trang": "Tình trạng",
                        }
                        hien_thi_dataframe_phan_trang(
                            df_tos[col_hien].rename(columns=rename_tos),
                            key=f"{_kp}cbtd_ct_to_tkvv",
                        )
                except Exception as e:
                    logger.error("tab_cbtd: cross-link To TK&VV — %s", e, exc_info=True)
                    st.caption("Chưa có dữ liệu Tổ TK&VV.")

        st.divider()

        # ════════════════════════════════════════════════════════════════════
        # CRUD (admin + manager CN)
        # ════════════════════════════════════════════════════════════════════
        if not la_quan_ly_cn(role):
            st.caption("Chỉ Quản lý Chi nhánh (admin/manager) mới được thêm/sửa/xóa CBTD.")
        else:
            che_do = st.radio("Thao tác",
                ["➕ Thêm mới", "✏️ Chỉnh sửa", "🗑️ Xóa"],
                horizontal=True, key=f"{_kp}cbtd_mode")
            st.divider()

            # ── THÊM MỚI ─────────────────────────────────────────────────────
            if che_do == "➕ Thêm mới":
                add_ver_key = f"{_kp}cbtd_add_ver"
                add_ver = int(st.session_state.get(add_ver_key, 0) or 0)
                add_kp = _cbtd_add_form_prefix(_kp, add_ver)
                st.markdown("**➕ Thêm CBTD mới**")
                c1, c2 = st.columns(2)

                with c1:
                    # Auto-gen mã CBTD (nút) + input
                    mcc1, mcc2 = st.columns([4, 1])
                    with mcc1:
                        ma_new  = st.text_input("Mã CBTD *", placeholder="vd: CB_PGD_BP_001",
                                                key=f"{add_kp}cbtd_ma_new",
                                                help="Nhập tay hoặc bấm nút bên phải để tự sinh")
                    with mcc2:
                        if st.button("🔢 Tự sinh", key=f"{add_kp}btn_auto_ma",
                                     help="Tự sinh mã CBTD theo PGD"):
                            gen = _auto_gen_ma_cb(DS_PGD_ALL[0] if not st.session_state.get(f"{add_kp}cbtd_pgd_new")
                                                  else st.session_state.get(f"{add_kp}cbtd_pgd_new"),
                                                  cbtd_data)
                            st.session_state[f"{add_kp}cbtd_ma_new"] = gen
                            st.rerun()
                    ten_new = st.text_input("Họ và tên *", key=f"{add_kp}cbtd_ten_new")
                    # Chức vụ (NEW v3)
                    cv_default_idx = 0
                    chuc_vu_new = st.selectbox("Chức vụ *", CHUC_VU_OPTS, index=cv_default_idx,
                                               key=f"{add_kp}cbtd_chuc_vu_new")
                    # Ngày bổ nhiệm (NEW v3)
                    ngay_bn_new = st.date_input("Ngày bổ nhiệm", format="DD/MM/YYYY",
                                                value=date.today(),
                                                key=f"{add_kp}cbtd_ngay_bn_new")
                    dt_new  = st.text_input("Số điện thoại", key=f"{add_kp}cbtd_dt_new",
                                            placeholder="vd: 0912345678 hoặc +84 91 234 5678")
                    gc_new  = st.text_input("Ghi chú", key=f"{add_kp}cbtd_gc_new")
                    pgd_new = st.selectbox("PGD trực thuộc *", DS_PGD_ALL, key=f"{add_kp}cbtd_pgd_new")

                with c2:
                    st.caption("🛡️ **Validation** — hiển thị ngay dưới widget")
                    dgd_opts_new = _ds_dgd_cua_pgd(pgd_new)
                    if not dgd_opts_new:
                        st.warning(f"PGD **{pgd_new}** chưa cấu hình ĐGD.")
                        dgd_sel_new = []
                    else:
                        labels_new = [_label_dgd(xa, d) for xa, d in dgd_opts_new]
                        sel_labels = st.multiselect(
                            "ĐGD phụ trách * (chọn nhiều cùng lúc)",
                            labels_new,
                            help="1 CBTD phụ trách 2–4 ĐGD trong cùng PGD — chọn hết rồi mới LƯU 1 lần",
                            key=f"{add_kp}cbtd_dgd_new")
                        dgd_sel_new = [d for xa, d in dgd_opts_new
                                       if _label_dgd(xa, d) in sel_labels]

                        if dgd_sel_new:
                            trung = _kiem_tra_trung_dgd(pgd_new, dgd_sel_new)
                            if trung:
                                for d, cb in trung.items():
                                    st.error(f"⛔ **{d}** đã thuộc CBTD **{cb}**")
                            else:
                                # Preview ấp
                                tong_ap_new = lay_ap_tu_dgd_list(pgd_new, dgd_sel_new, dgd_map)
                                wl_i, wl_t = _workload_label(len(dgd_sel_new))
                                st.success(f"✅ {len(dgd_sel_new)} ĐGD hợp lệ — Workload: {wl_i} {wl_t} — "
                                           f"{len(tong_ap_new)} ấp/thôn phụ trách")
                                with st.expander("Xem danh sách ấp"):
                                    for xa_p, ap_p in sorted(tong_ap_new):
                                        st.caption(f"• {xa_p} / {ap_p}")
                        else:
                            st.caption("👆 Chọn ít nhất 1 ĐGD (bấm chọn nhiều ĐGD cùng lúc rồi lưu 1 lần)")

                if st.button("💾 LƯU CBTD MỚI", type="primary", key=f"{_kp}btn_them_cbtd"):
                    err = []
                    # Mã CBTD
                    ma_val = (ma_new or "").strip().upper()
                    ok_ma, msg_ma = _validate_ma_cb(ma_val if ma_val else None, cbtd_data)
                    if not ok_ma:
                        err.append(msg_ma)
                    # Họ tên
                    if not ten_new.strip():
                        err.append("Thiếu Họ tên (không được trống)")
                    if len(ten_new.strip()) < 3:
                        err.append("Họ tên quá ngắn (≥3 ký tự)")
                    # Điện thoại
                    ok_dt, msg_dt = _validate_dien_thoai(dt_new)
                    if not ok_dt:
                        err.append(msg_dt)
                    # ĐGD
                    if not dgd_sel_new:
                        err.append("Chọn ít nhất 1 ĐGD")
                    # Trùng ĐGD
                    trung_luu = _kiem_tra_trung_dgd(pgd_new, dgd_sel_new)
                    if trung_luu:
                        for d, cb in trung_luu.items():
                            err.append(f"ĐGD **{d}** đã thuộc CBTD **{cb}**")
                    # Show errors or save
                    if err:
                        for e in err:
                            st.error(f"❌ {e}")
                    else:
                        ma_key = ma_val
                        cbtd_data[ma_key] = {
                            "ho_ten":         ten_new.strip(),
                            "chuc_vu":        chuc_vu_new,
                            "ngay_bo_nhiem":  _date_to_ddmmyyyy(ngay_bn_new),
                            "pgd":            pgd_new,
                            "ds_dgd":         dgd_sel_new,
                            "dien_thoai":     dt_new.strip(),
                            "ghi_chu":        gc_new.strip(),
                            "ngay_cap":       datetime.today().strftime("%d/%m/%Y %H:%M"),
                        }
                        luu_cbtd(cbtd_data)
                        db.ghi_audit(username, "luu_cbtd",
                                     f"Thêm {ma_key} — {ten_new.strip()} / {chuc_vu_new} "
                                     f"({pgd_new}, {len(dgd_sel_new)} ĐGD)")
                        st.cache_data.clear()
                        st.session_state[add_ver_key] = add_ver + 1
                        st.success(f"✅ Đã thêm **{ma_key}** — {ten_new.strip()} ({chuc_vu_new})")
                        st.rerun()

            # ── CHỈNH SỬA ────────────────────────────────────────────────────
            elif che_do == "✏️ Chỉnh sửa":
                st.markdown("**✏️ Chỉnh sửa CBTD**")
                if not cbtd_data:
                    st.info("Chưa có CBTD nào.")
                else:
                    chon_sua = st.selectbox(
                        "Chọn CBTD",
                        list(cbtd_data.keys()),
                        format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} "
                                              f"/ {cbtd_data[k].get('pgd','?')} "
                                              f"({len(cbtd_data[k].get('ds_dgd',[]))} ĐGD)",
                        key=f"{_kp}cbtd_chon_sua")
                    info_cu = cbtd_data[chon_sua]
                    # Khởi tạo giá trị mặc định cho trường mới (nếu chưa có từ schema cũ)
                    chuc_vu_cu = info_cu.get("chuc_vu", "") or "Cán bộ tín dụng"
                    ngay_bn_cu = _ddmmyyyy_to_date(info_cu.get("ngay_bo_nhiem", "")) or date.today()

                    c1, c2 = st.columns(2)
                    with c1:
                        ten_sua = st.text_input("Họ và tên *",
                            value=info_cu.get("ho_ten",""), key=f"{_kp}cbtd_ten_sua")
                        # Chức vụ (NEW v3)
                        cv_idx_sua = CHUC_VU_OPTS.index(chuc_vu_cu) if chuc_vu_cu in CHUC_VU_OPTS else 0
                        chuc_vu_sua = st.selectbox("Chức vụ *", CHUC_VU_OPTS, index=cv_idx_sua,
                                                   key=f"{_kp}cbtd_chuc_vu_sua")
                        # Ngày bổ nhiệm (NEW v3)
                        ngay_bn_sua = st.date_input("Ngày bổ nhiệm", format="DD/MM/YYYY",
                                                    value=ngay_bn_cu,
                                                    key=f"{_kp}cbtd_ngay_bn_sua")
                        dt_sua  = st.text_input("Số điện thoại",
                            value=info_cu.get("dien_thoai",""), key=f"{_kp}cbtd_dt_sua",
                            placeholder="vd: 0912345678")
                        gc_sua  = st.text_input("Ghi chú",
                            value=info_cu.get("ghi_chu",""), key=f"{_kp}cbtd_gc_sua")
                        pgd_idx = DS_PGD_ALL.index(info_cu["pgd"]) if info_cu.get("pgd") in DS_PGD_ALL else 0
                        pgd_sua = st.selectbox("PGD trực thuộc *",
                            DS_PGD_ALL, index=pgd_idx, key=f"{_kp}cbtd_pgd_sua")

                    with c2:
                        dgd_opts_sua = _ds_dgd_cua_pgd(pgd_sua)
                        if not dgd_opts_sua:
                            st.warning(f"PGD **{pgd_sua}** chưa cấu hình ĐGD.")
                            dgd_sel_sua = []
                        else:
                            labels_sua = [_label_dgd(xa, d) for xa, d in dgd_opts_sua]
                            ds_dgd_cu  = info_cu.get("ds_dgd", []) if pgd_sua == info_cu.get("pgd") else []
                            default_labels = [_label_dgd(xa, d) for xa, d in dgd_opts_sua
                                              if d in ds_dgd_cu]
                            sel_labels_sua = st.multiselect(
                                "ĐGD phụ trách * (chọn nhiều rồi Lưu 1 lần)",
                                labels_sua,
                                default=default_labels,
                                help="Chọn nhiều ĐGD cùng lúc → 1 nút Lưu cuối cùng",
                                key=f"{_kp}cbtd_dgd_sua")
                            dgd_sel_sua = [d for xa, d in dgd_opts_sua
                                           if _label_dgd(xa, d) in sel_labels_sua]

                            if dgd_sel_sua:
                                trung_sua = _kiem_tra_trung_dgd(pgd_sua, dgd_sel_sua, bo_qua_ma=chon_sua)
                                if trung_sua:
                                    for d, cb in trung_sua.items():
                                        st.error(f"⛔ **{d}** đang thuộc CBTD **{cb}**")
                                else:
                                    tong_ap_sua = lay_ap_tu_dgd_list(pgd_sua, dgd_sel_sua, dgd_map)
                                    wl_i_s, wl_t_s = _workload_label(len(dgd_sel_sua))
                                    st.info(f"✅ {len(dgd_sel_sua)} ĐGD — WL: {wl_i_s} {wl_t_s} — "
                                            f"{len(tong_ap_sua)} ấp/thôn")
                            else:
                                st.caption("👆 Chọn ít nhất 1 ĐGD")

                    if st.button("💾 Lưu thay đổi", type="primary", key=f"{_kp}btn_luu_sua"):
                        err_sua = []
                        if not ten_sua.strip():
                            err_sua.append("Họ tên không được để trống")
                        if len(ten_sua.strip()) < 3 and ten_sua.strip():
                            err_sua.append("Họ tên quá ngắn (≥3 ký tự)")
                        ok_dt_s, msg_dt_s = _validate_dien_thoai(dt_sua)
                        if not ok_dt_s:
                            err_sua.append(msg_dt_s)
                        if not dgd_sel_sua:
                            err_sua.append("Chọn ít nhất 1 ĐGD")
                        trung_luu_sua = _kiem_tra_trung_dgd(pgd_sua, dgd_sel_sua, bo_qua_ma=chon_sua)
                        if trung_luu_sua:
                            for d, cb in trung_luu_sua.items():
                                err_sua.append(f"ĐGD **{d}** đang thuộc CBTD **{cb}**")
                        if err_sua:
                            for e in err_sua:
                                st.error(f"❌ {e}")
                        else:
                            # Giữ nguyên ngày_cap cũ nếu không thay đổi fields (chỉ cập nhật khi có thay đổi)
                            ngay_cap_cu = info_cu.get("ngay_cap", "")
                            cbtd_data[chon_sua] = {
                                "ho_ten":         ten_sua.strip(),
                                "chuc_vu":        chuc_vu_sua,
                                "ngay_bo_nhiem":  _date_to_ddmmyyyy(ngay_bn_sua),
                                "pgd":            pgd_sua,
                                "ds_dgd":         dgd_sel_sua,
                                "dien_thoai":     dt_sua.strip(),
                                "ghi_chu":        gc_sua.strip(),
                                "ngay_cap":       ngay_cap_cu or datetime.today().strftime("%d/%m/%Y %H:%M"),
                            }
                            luu_cbtd(cbtd_data)
                            db.ghi_audit(username, "luu_cbtd",
                                         f"Sửa {chon_sua} — {pgd_sua}, {chuc_vu_sua}, "
                                         f"{len(dgd_sel_sua)} ĐGD")
                            st.cache_data.clear()
                            st.success(f"✅ Đã cập nhật **{chon_sua}**")
                            st.rerun()

            # ── XÓA ─────────────────────────────────────────────────────────
            elif che_do == "🗑️ Xóa":
                st.markdown("**🗑️ Xóa CBTD**")
                if not cbtd_data:
                    st.info("Chưa có CBTD nào.")
                else:
                    chon_xoa = st.selectbox(
                        "Chọn CBTD",
                        list(cbtd_data.keys()),
                        format_func=lambda k: f"{k} — {cbtd_data[k]['ho_ten']} "
                                              f"/ {cbtd_data[k].get('pgd','?')}",
                        key=f"{_kp}cbtd_chon_xoa")
                    info_xoa = cbtd_data[chon_xoa]
                    st.warning(
                        f"⚠️ Sắp xóa: **{chon_xoa}** — {info_xoa['ho_ten']}\n\n"
                        f"PGD: {info_xoa.get('pgd','?')} | "
                        f"ĐGD: {', '.join(info_xoa.get('ds_dgd',[]))}"
                    )
                    xn = st.checkbox("Xác nhận xóa", key=f"{_kp}cbtd_xn_xoa")
                    if st.button("🗑️ Xóa", type="primary",
                                 disabled=not xn, key=f"{_kp}btn_xoa_cbtd"):
                        del cbtd_data[chon_xoa]
                        luu_cbtd(cbtd_data)
                        db.ghi_audit(username, "luu_cbtd", f"Xóa {chon_xoa}")
                        st.cache_data.clear()
                        st.success(f"✅ Đã xóa **{chon_xoa}**")
                        st.rerun()

        st.divider()

        # ════════════════════════════════════════════════════════════════════
        # BÁO CÁO DƯ NỢ THEO CBTD
        # ════════════════════════════════════════════════════════════════════
        cbtd_co_dgd = {ma: info for ma, info in cbtd_data.items()
                       if info.get("pgd") and info.get("ds_dgd")}
        if not cbtd_co_dgd:
            if cbtd_data:
                st.info("ℹ️ Chưa có CBTD nào được gán ĐGD. "
                        "Dùng **Chỉnh sửa** để cập nhật.")
            return

        st.markdown("**📊 Tổng hợp dư nợ theo CBTD**")

        if df is None or df.empty:
            st.warning("Chưa có dữ liệu HSTD.")
            return

        # Join toàn bộ df với cbtd
        df_joined = gan_cbtd_vao_df(df, cbtd_co_dgd, dgd_map)
        if COT_HINH_THUC_VAY in df_joined.columns:
            df_joined = df_joined[df_joined[COT_HINH_THUC_VAY] != 1]

        rows_bc = []
        for ma, info in cbtd_co_dgd.items():
            df_cb = df_joined[df_joined["CBTD"] == ma]
            if df_cb.empty:
                continue
            tdn = pd.to_numeric(df_cb[COT_TONG_DU_NO], errors="coerce").sum() if COT_TONG_DU_NO in df_cb.columns else 0
            dqh = pd.to_numeric(df_cb[COT_DU_NO_QH], errors="coerce").sum()   if COT_DU_NO_QH   in df_cb.columns else 0
            rows_bc.append({
                "Mã CBTD":       ma,
                "Họ tên":        info["ho_ten"],
                "PGD":           info.get("pgd",""),
                "SĐT":           info.get("dien_thoai",""),
                "Số KH":         fmt_so(df_cb[COT_MA_KH].nunique()) if COT_MA_KH in df_cb.columns else "—",
                "Số món vay":    fmt_so(df_cb[COT_SO_KU].nunique()) if COT_SO_KU in df_cb.columns else "—",
                "Tổng dư nợ":   _fmt_tien(tdn),
                "Dư nợ QH":     _fmt_tien(dqh),
                "Tỷ lệ QH %":   round(dqh/tdn*100, 2) if tdn else 0,
                "Số ĐGD":       len(info.get("ds_dgd",[])),
                "Số ấp":        _so_ap_cbtd(info),
            })

        if not rows_bc:
            st.info("Không có dữ liệu dư nợ cho CBTD nào (kiểm tra lại tên thôn trong ĐGD).")
            return

        hien_thi_dataframe_phan_trang(pd.DataFrame(rows_bc), key=f"{_kp}cbtd_bc_tong_hop")

        if st.button("📥 Xuất báo cáo CBTD", key=f"{_kp}btn_xuat_cbtd"):
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                pd.DataFrame(rows_bc).to_excel(w, index=False, sheet_name="Tổng hợp CBTD")
                for ma, info in cbtd_co_dgd.items():
                    df_cb2 = df_joined[df_joined["CBTD"] == ma].copy()
                    if not df_cb2.empty:
                        df_cb2.drop(columns=["CBTD","Tên CBTD"], errors="ignore", inplace=True)
                        df_cb2.to_excel(w, index=False, sheet_name=f"CB_{ma}"[:31])
            state.downloads.set(
                "cbtd_excel",
                buf.getvalue(),
                f"BC_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
            )

        if state.downloads.has("cbtd_excel"):
            if st.download_button(
                "⬇ Tải Excel",
                data=state.downloads.get_bytes("cbtd_excel"),
                file_name=state.downloads.get_filename("cbtd_excel") or f"BC_CBTD_{datetime.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{_kp}dl_cbtd",
            ):
                state.downloads.clear("cbtd_excel")
