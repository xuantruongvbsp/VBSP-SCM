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
from auth import la_phan_he_cn, la_phan_he_pgd, la_executive, la_quan_ly_cn, normalize_role
from logger import get_logger
from state_manager import SCMStateManager
from utils import xuat_excel, hien_thi_dataframe_phan_trang, fmt, fmt_so, fmt_ty, lazy_tabs
from components.delta_card import delta_card, kpi_row
from services.cbtd_dia_ban_service import (
    lay_kpi_cbtd_theo_thang, tong_hop_hstd_theo_cbtd,
    top_3_viec_uu_tien, cham_diem_cbtd_thang,
)
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

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("👔 Quản lý Cán bộ Tín dụng (CBTD)")
        if pgd_user:
            st.caption(f"📍 **Địa bàn mode:** Chỉ xem CBTD thuộc PGD **{pgd_user}** (không chéo đơn vị).")
        else:
            st.caption("🏛️ **Chi nhánh mode:** Toàn bộ 22 đơn vị — có thể thêm/sửa/xóa CBTD toàn hệ thống.")

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

        def _label_dgd_day_du(pgd: str, xa: str, dgd_name: str) -> str:
            so_ap = len(_ap_cua_dgd(pgd, dgd_name))
            suffix = f"{so_ap} thôn/ấp" if so_ap else "chưa gom thôn"
            return f"{_label_dgd(xa, dgd_name)} · {suffix}"

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
        # 6 NHÓM NGHIỆP VỤ LEVEL-2 LAZY TABS MỚI
        # Thứ tự: Đầu tháng → Giữa tháng → Cuối tháng
        # ════════════════════════════════════════════════════════════════════
        labels_lv2 = [
            "📊 Trang chủ cá nhân",
            "👥 Quản lý hồ sơ CBTD",
            "📋 KHTD & Giao chỉ tiêu",
            "💰 Tác nghiệp & Đôn đốc",
            "📈 Xếp hạng & Báo cáo",
            "🛠️ Công cụ bổ trợ",
        ]

        # ── Nhóm 1: Trang chủ cá nhân CBTD ─────────────────────────────────
        def _render_g1(_c):
            with _c:
                _kp_g1 = f"{_kp}lv2_1_"
                if not cbtd_data:
                    st.warning("⚠️ Chưa có danh sách CBTD — qua **Nhóm 2** để thêm CBTD.")
                    return

                # 1) Scope guard: build danh sách CBTD cho phép
                if la_phan_he_cn(role):
                    _ds_cbtd_scope = list(cbtd_data.items())
                else:
                    _pgd_scope = pgd_user or ""
                    _ds_cbtd_scope = [
                        (m, i) for m, i in cbtd_data.items()
                        if (i.get("pgd") or "").strip() == (_pgd_scope or "").strip()
                    ]
                if not _ds_cbtd_scope:
                    st.warning("⚠️ Không có CBTD nào thuộc phạm vi được xem.")
                    return
                _ds_ma_cb = [m for m, _ in _ds_cbtd_scope]
                _label_by_ma_cb = {
                    m: f"{info.get('ho_ten', m)} — {info.get('pgd','')} [{m}]"
                    for m, info in _ds_cbtd_scope
                }
                _ma_cb = st.selectbox(
                    "Chọn Cán bộ tín dụng",
                    _ds_ma_cb, index=0,
                    format_func=lambda m: _label_by_ma_cb.get(m, str(m)),
                    key=f"{_kp_g1}chon_cb",
                )
                _info_cb = cbtd_data[_ma_cb]

                # 2) Chọn kỳ (tháng / năm) + hôm nay
                _kc1, _kc2, _kc3 = st.columns([1, 1, 2])
                with _kc1:
                    _nam = st.number_input(
                        "Năm", value=max(2024, date.today().year),
                        min_value=2023, max_value=2100, step=1,
                        key=f"{_kp_g1}nam",
                    )
                with _kc2:
                    _thang = st.number_input(
                        "Tháng", value=max(1, date.today().month),
                        min_value=1, max_value=12, step=1,
                        key=f"{_kp_g1}thang",
                    )
                with _kc3:
                    _today = st.date_input(
                        "Ngày hôm nay", value=date.today(),
                        format="DD/MM/YYYY",
                        key=f"{_kp_g1}today",
                    )
                st.divider()

                # 3) Tính KPI tháng N via service
                _kpi_mon = lay_kpi_cbtd_theo_thang(
                    _ma_cb, int(_nam), int(_thang),
                    cbtd_data=cbtd_data, dgd_map=dgd_map, df_hstd=df,
                    scope_pgd=pgd_user if la_phan_he_pgd(role) else None,
                ) or {}
                _score = cham_diem_cbtd_thang(
                    _ma_cb, int(_nam), int(_thang),
                    cbtd_data=cbtd_data, dgd_map=dgd_map, df_hstd=df,
                    scope_pgd=pgd_user if la_phan_he_pgd(role) else None,
                ) or {}
                _top3 = top_3_viec_uu_tien(
                    _ma_cb, _today,
                    cbtd_data=cbtd_data, dgd_map=dgd_map, df_hstd=df,
                    scope_pgd=pgd_user if la_phan_he_pgd(role) else None,
                ) or []
                _df_sl_cbtd = tong_hop_hstd_theo_cbtd(
                    cbtd_data, dgd_map, df,
                    yyyy=int(_nam), mm=int(_thang),
                    scope_pgd=pgd_user if la_phan_he_pgd(role) else None,
                )

                if not _kpi_mon.get("so_kh") and not _top3:
                    st.info(
                        f"ℹ️ Chưa tính được KPI cho **{_info_cb.get('ho_ten', _ma_cb)}** — "
                        "có thể chưa gán ĐGD hoặc file HSTD chưa được upload/tải lên."
                    )
                    _meta_warn = (_score or {}).get("meta", {}).get("warning")
                    if _meta_warn:
                        st.caption(f"Ghi chú: {_meta_warn}")

                # 4) 5 KPI card công việc hôm nay
                st.subheader("🏷️ Công việc hôm nay")
                _so_den_han = 0
                _so_nqh = 0
                for _v in _top3:
                    if _v.get("loai") == "den_han_hom_nay":
                        _so_den_han = int((_v.get("chi_tiet") or {}).get("so_hd", 0) or 0)
                    elif _v.get("loai") == "nqh_cao":
                        _so_nqh = int((_v.get("chi_tiet") or {}).get("so_mon", 0) or 0)
                _so_dgd = len(_info_cb.get("ds_dgd") or [])
                _so_ap = int(_score.get("so_ap", 0) or 0)
                _diem = float(_score.get("diem_tong", 0.0) or 0.0)
                _cols1: list[dict] = [
                    {"label": "🔴 HĐ đến hạn hôm nay", "value": fmt(_so_den_han),
                     "icon": "📅", "suffix": "hợp đồng",
                     "help": "Số hợp đồng có ngày đến hạn trả nợ = ngày hôm nay"},
                    {"label": "⚠️ HĐ NQH", "value": fmt(_so_nqh),
                     "icon": "🚨", "suffix": "hợp đồng",
                     "help": "Số hợp đồng có dư nợ nhóm 2-5 (quá hạn hoặc khả năng mất vốn)"},
                    {"label": "🗺️ Điểm GD phụ trách", "value": fmt(_so_dgd),
                     "icon": "📍", "suffix": "ĐGD",
                     "help": "Số điểm giao dịch đã phân công cho CBTD này"},
                    {"label": "🏘️ Ấp/Xã phụ trách", "value": fmt(_so_ap),
                     "icon": "🏡", "suffix": "ấp/xã",
                     "help": "Số ấp/xã suy ra từ danh sách ĐGD (gộp theo tên xã + thôn/ấp)"},
                    {"label": "⭐ Điểm tháng", "value": f"{_diem:,.1f}",
                     "icon": "🏆", "suffix": f"/100 → {_score.get('xep_loai', 'Yếu')}",
                     "help": "Điểm tổng hợp CBTD (scorecard 0-100, clamp BUGMAP C49)"},
                ]
                kpi_row(_cols1, num_columns=5)

                # 4b) Số liệu HSTD theo từng CBTD trong phạm vi đang xem
                st.subheader("📊 Số liệu theo từng CBTD")
                if _df_sl_cbtd is None or _df_sl_cbtd.empty:
                    st.info("Chưa có số liệu HSTD khớp theo CBTD trong phạm vi đang xem.")
                else:
                    _view_mode = st.radio(
                        "Phạm vi bảng",
                        ["Tất cả CBTD", "CBTD đang chọn"],
                        horizontal=True,
                        key=f"{_kp_g1}scope_bang_cbtd",
                    )
                    _df_sl_show = _df_sl_cbtd.copy()
                    if _view_mode == "CBTD đang chọn":
                        _df_sl_show = _df_sl_show[_df_sl_show["Ma_CBTD"] == _ma_cb]

                    _df_sl_view = _df_sl_show.rename(columns={
                        "Ma_CBTD": "Mã CBTD",
                        "Ho_ten": "Họ tên",
                        "So_DGD": "Số ĐGD",
                        "So_ap": "Số ấp",
                        "So_KH": "Số KH",
                        "So_mon_vay": "Số món vay",
                        "Tong_du_no": "Tổng dư nợ (tr)",
                        "Du_no_trong_han": "Dư nợ TH (tr)",
                        "Du_no_qh": "Dư nợ QH (tr)",
                        "TL_QH_pct": "TL QH %",
                        "So_CT": "Số CT",
                        "CT_du_no_lon_nhat": "CT dư nợ lớn nhất",
                        "Du_no_ct_lon_nhat": "Dư nợ CT lớn nhất (tr)",
                        "So_KH_moi_thang": "KH mới tháng",
                        "So_giai_ngan_thang": "GN tháng",
                        "Canh_bao": "Cảnh báo",
                    })
                    for _col in ["Tổng dư nợ (tr)", "Dư nợ TH (tr)", "Dư nợ QH (tr)", "Dư nợ CT lớn nhất (tr)"]:
                        if _col in _df_sl_view.columns:
                            _df_sl_view[_col] = _df_sl_view[_col].map(_fmt_tien)
                    if "TL QH %" in _df_sl_view.columns:
                        _df_sl_view["TL QH %"] = _df_sl_view["TL QH %"].map(
                            lambda x: f"{float(x or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        )
                    _cols_view = [
                        "Mã CBTD", "Họ tên", "PGD", "Số ĐGD", "Số ấp", "Số KH", "Số món vay",
                        "Tổng dư nợ (tr)", "Dư nợ TH (tr)", "Dư nợ QH (tr)", "TL QH %",
                        "Số CT", "CT dư nợ lớn nhất", "Dư nợ CT lớn nhất (tr)",
                        "KH mới tháng", "GN tháng", "Cảnh báo",
                    ]
                    _cols_view = [c for c in _cols_view if c in _df_sl_view.columns]
                    hien_thi_dataframe_phan_trang(
                        _df_sl_view[_cols_view],
                        key=f"{_kp_g1}bang_so_lieu_cbtd",
                        height=360,
                    )
                    st.download_button(
                        "⬇ Tải Excel số liệu CBTD",
                        data=xuat_excel({"So_lieu_CBTD": _df_sl_show}),
                        file_name=f"So_lieu_CBTD_{int(_thang):02d}_{int(_nam)}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"{_kp_g1}dl_so_lieu_cbtd",
                    )

                # 5) 5 Đèn giao dịch tháng (ngưỡng xanh/vàng/đỏ VBSP)
                st.subheader("💡 Đèn giao dịch tháng")
                _tl_qh = float(_kpi_mon.get("tl_qh_pct", 0.0) or 0.0)
                _so_kh_moi = int(_kpi_mon.get("so_kh_moi_thang", 0) or 0)
                _so_gn_mon = int(_kpi_mon.get("so_giai_ngan_mon", 0) or 0)
                _dn_ty = float(_kpi_mon.get("tong_du_no_ty", 0.0) or 0.0)
                _pct_to_dat = float(_score.get("pct_to_dat", 0.0) or 0.0)
                def _mau_pct_thuan(pct: float) -> str:
                    if pct >= 85: return "🟢"
                    if pct >= 70: return "🟡"
                    return "🔴"
                def _mau_pct_nguoc(pct: float) -> str:
                    if pct < 10: return "🟢"
                    if pct < 15: return "🟡"
                    return "🔴"
                _den1 = _mau_pct_thuan(_pct_to_dat if _pct_to_dat else (100 if _tl_qh <= 3 else 75))
                _den2 = _mau_pct_nguoc(_tl_qh)
                _den3 = _mau_pct_thuan(100 if _dn_ty > 0 else 0)
                _den4 = _mau_pct_thuan(100 if _so_gn_mon >= 3 else (60 if _so_gn_mon >= 1 else 30))
                _den5 = _mau_pct_thuan(100 if _so_kh_moi >= 5 else (60 if _so_kh_moi >= 1 else 20))
                _cols2 = st.columns(5)
                _labels_den = [
                    ("% Tổ đạt CHXH",  _den1, f"{_pct_to_dat if _pct_to_dat else '—'}",  "%", "Đèn xanh ≥ 85% / Vàng 70-85 / Đỏ <70"),
                    ("NQH %",          _den2, f"{_tl_qh:,.1f}", "%", "Đèn xanh <10% / Vàng 10-15 / Đỏ >15"),
                    ("Dư nợ tháng",    _den3, f"{_dn_ty:,.1f}", "tỷ", "Dư nợ CBTD quản lý (tỷ đồng)"),
                    ("HĐ giải ngân",   _den4, fmt(_so_gn_mon),   "hợp đồng", "Số hợp đồng giải ngân trong tháng N"),
                    ("KH mới tháng",   _den5, fmt(_so_kh_moi),   "KH", "Số khách hàng mới có ngày vay trong tháng N"),
                ]
                for i, (_lb, _mau, _val, _suf, _hp) in enumerate(_labels_den):
                    with _cols2[i]:
                        delta_card(_lb, f"{_mau}  {_val}",
                                   icon="", suffix=_suf, help=_hp,
                                   key=f"{_kp_g1}den_{i}")
                st.caption(
                    "💡 Đèn giao dịch: 🟢 xanh = đạt mục tiêu · 🟡 vàng = cần theo dõi · 🔴 đỏ = phải hành động ngay"
                )

                # 6) Top 3 việc ưu tiên hôm nay
                st.subheader("🎯 Top 3 việc ưu tiên hôm nay")
                if not _top3:
                    st.info("🎉 Không có việc ưu tiên đặc biệt hôm nay — chúc CBTD làm việc hiệu quả!")
                else:
                    _stt_pri = {1: "🔝 Ưu tiên 1", 2: "⏰ Ưu tiên 2", 3: "📌 Ưu tiên 3", 99: "⚠️ Lỗi", 5: "ℹ️ Gợi ý"}
                    for idx, v in enumerate(_top3):
                        with st.container(border=True):
                            _pri = int(v.get("priority", 99))
                            lab = _stt_pri.get(_pri, f"Ưu tiên {_pri}")
                            st.markdown(f"**{lab}** — {v.get('noi_dung', '')}")
                            ct = v.get("chi_tiet") or {}
                            if ct:
                                bits = []
                                if ct.get("so_hd"): bits.append(f"{ct['so_hd']} hợp đồng")
                                if ct.get("so_mon"): bits.append(f"{ct['so_mon']} món")
                                if ct.get("ty_le_pct") is not None: bits.append(f"TL {ct['ty_le_pct']:,.1f}%")
                                if ct.get("so_tien_qh_ty"): bits.append(f"Số tiền QH {ct['so_tien_qh_ty']:,.1f} tỷ")
                                if ct.get("ma_kh_mau"): bits.append(f"KH mẫu: {ct['ma_kh_mau']}")
                                if ct.get("ngay"): bits.append(f"Ngày: {ct['ngay']}")
                                if ct.get("so_to"): bits.append(f"{ct['so_to']} tổ")
                                if bits:
                                    st.caption("  ·  ".join(bits))

                # 7) Thông tin phân công ĐGD hôm nay
                st.subheader("👥 Phân công ĐGD phụ trách")
                _ds_dgd = _info_cb.get("ds_dgd") or []
                if not _ds_dgd:
                    st.caption("⚠️ CBTD này chưa được phân công ĐGD nào — vào **Nhóm 2** để phân công.")
                else:
                    _ap_info = lay_ap_tu_dgd_list(_info_cb.get("pgd", ""), _ds_dgd, dgd_map)
                    _rows_pc = []
                    for j, _dgd in enumerate(_ds_dgd):
                        info_d = (_ap_info or {}).get(_dgd, {})
                        _rows_pc.append({
                            "STT": j + 1,
                            "Điểm giao dịch": _dgd,
                            "Xã/phường": info_d.get("xa", ""),
                            "Thôn/ấp": ", ".join(info_d.get("thon", []) or []),
                        })
                    hien_thi_dataframe_phan_trang(
                        pd.DataFrame(_rows_pc),
                        key=f"{_kp_g1}pc_dgd", height=250,
                    )

                # 8) Warning nếu có schema / fallback
                _warn_list: list[str] = []
                if _kpi_mon.get("meta", {}).get("warning"):
                    _warn_list.append(str(_kpi_mon["meta"]["warning"]))
                if _kpi_mon.get("meta", {}).get("fallback_all_time"):
                    _warn_list.append("⚠️ KPI tháng đang hiển thị toàn thời gian (thiếu cột ngày trong HSTD).")
                if _score.get("meta", {}).get("source"):
                    _warn_list.append(f"🔗 Điểm tính từ nguồn: {_score['meta']['source']}.")
                if _warn_list:
                    with st.expander("🔧 Thông tin kỹ thuật / Ghi chú", expanded=False):
                        for w in _warn_list:
                            st.markdown(f"- {w}")

        # ── Nhóm 2: Quản lý hồ sơ CBTD (toàn bộ nội dung cũ) ────────────────
        def _render_g2(_c):
            with _c:
                _kp_g2 = f"{_kp}lv2_2_"

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
                            search_q = fc1.text_input("🔍 Tìm (Họ tên / SĐT / Mã CB)", "",
                                                      key=f"{_kp_g2}cbtd_search")
                            pgd_opts = ["Tất cả"] + DS_PGD_ALL
                            pgd_sel = fc2.selectbox("PGD trực thuộc", pgd_opts,
                                                    index=0, key=f"{_kp_g2}cbtd_pgd")
                            wl_opts = ["Tất cả", "✅ Cân bằng (2-4 ĐGD)", "🔴 Quá tải (≥5)", "⚠️ Thiếu tải (≤1)"]
                            wl_sel = fc3.selectbox("Workload", wl_opts, index=0,
                                                   key=f"{_kp_g2}cbtd_wl")
                            ap_opts = ["Tất cả", "≥20 ấp", "10-19 ấp", "<10 ấp"]
                            ap_sel = fc4.selectbox("Quy mô ấp", ap_opts, index=0,
                                                   key=f"{_kp_g2}cbtd_ap")

                        rows = []
                        for ma, info in cbtd_data.items():
                            ho_ten = info.get("ho_ten", "")
                            so_dgd = len(info.get("ds_dgd", []))
                            so_ap  = _so_ap_cbtd(info)
                            wl_icon, wl_label = _workload_label(so_dgd)
                            if search_q:
                                q = search_q.strip().lower()
                                haystack = " ".join([
                                    str(ma).lower(),
                                    ho_ten.lower(),
                                    str(info.get("dien_thoai", "")).lower(),
                                    str(info.get("ghi_chu", "")).lower(),
                                ])
                                if q not in haystack:
                                    continue
                            if pgd_sel != "Tất cả":
                                if info.get("pgd", "") != pgd_sel:
                                    continue
                            if wl_sel == "✅ Cân bằng (2-4 ĐGD)" and not (2 <= so_dgd <= 4):
                                continue
                            if wl_sel == "🔴 Quá tải (≥5)" and so_dgd < 5:
                                continue
                            if wl_sel == "⚠️ Thiếu tải (≤1)" and not (0 < so_dgd <= 1):
                                continue
                            if ap_sel == "≥20 ấp" and so_ap < 20:
                                continue
                            if ap_sel == "10-19 ấp" and not (10 <= so_ap <= 19):
                                continue
                            if ap_sel == "<10 ấp" and so_ap >= 10:
                                continue
                            rows.append({
                                "Mã CBTD": ma,
                                "Họ và tên": ho_ten,
                                "Chức vụ": info.get("chuc_vu", "") or "Cán bộ tín dụng",
                                "PGD": info.get("pgd", ""),
                                "Số ĐGD": so_dgd,
                                "Workload": f"{wl_icon} {wl_label}",
                                "Số ấp": so_ap,
                                "SĐT": info.get("dien_thoai", ""),
                                "Ngày bổ nhiệm": info.get("ngay_bo_nhiem", ""),
                                "Ghi chú": info.get("ghi_chu", ""),
                            })
                        if not rows:
                            st.caption("🔍 Không có CBTD phù hợp bộ lọc.")
                        else:
                            df_hien = pd.DataFrame(rows)
                            st.caption(f"📋 Tổng **{len(df_hien)}** CBTD phù hợp điều kiện.")
                            hien_thi_dataframe_phan_trang(df_hien, key=f"{_kp_g2}cbtd_ds", height=460)

                # ── SUB-TAB 2: Bản đồ ĐGD → CBTD ────────────────────────────────────
                with xem2:
                    st.caption("🗺️ **Bản đồ phân công:** Mỗi ĐGD trong HSTD thuộc đúng 1 CBTD. "
                               "ĐGD màu xám = chưa gán CBTD.")
                    pgd_opts_bd = ["Tất cả"] + DS_PGD_ALL
                    pgd_sel_bd = st.selectbox("Lọc PGD", pgd_opts_bd, index=0,
                                              key=f"{_kp_g2}cbtd_pgd_bd")
                    only_chua = st.checkbox("🔴 Chỉ xem ĐGD CHƯA gán CBTD",
                                            key=f"{_kp_g2}cbtd_only_chua")
                    rows_bd = []
                    for pgd_bd, xa_block in dgd_map.items():
                        if not isinstance(xa_block, dict):
                            continue
                        if pgd_sel_bd != "Tất cả" and pgd_bd != pgd_sel_bd:
                            continue
                        for xa_bd, dgd_block in xa_block.items():
                            if not isinstance(dgd_block, dict):
                                continue
                            for dgd_name_bd in dgd_block:
                                ap_bd = len(_ap_cua_dgd(pgd_bd, dgd_name_bd))
                                found = dgd_da_phan.get((pgd_bd, dgd_name_bd))
                                if only_chua and found:
                                    continue
                                if found:
                                    ma_cb, ten_cb = found
                                else:
                                    ma_cb, ten_cb = "", ""
                                rows_bd.append({
                                    "PGD": pgd_bd,
                                    "Xã": xa_bd,
                                    "ĐGD": dgd_name_bd,
                                    "Số ấp": ap_bd,
                                    "Mã CBTD": ma_cb,
                                    "CBTD": ten_cb,
                                    "Trạng thái": "✅ Đã gán" if ma_cb else "⚠️ CHƯA gán",
                                })
                    if not rows_bd:
                        st.info("Không có ĐGD phù hợp.")
                    else:
                        df_bd = pd.DataFrame(rows_bd)
                        _tong_dgd_phan = sum(len(i.get('ds_dgd', [])) for i in cbtd_data.values())
                        st.caption(f"🗺️ Hiển thị **{len(df_bd)}** ĐGD / **{_tong_dgd_phan}** đã gán CBTD.")
                        hien_thi_dataframe_phan_trang(df_bd, key=f"{_kp_g2}cbtd_bd_dgd", height=420)

                # ── SUB-TAB 3: Chi tiết CBTD ─────────────────────────────────────────
                with xem3:
                    if not cbtd_data:
                        st.info("Chưa có CBTD nào.")
                    else:
                        chon = st.selectbox(
                            "Chọn CBTD để xem chi tiết",
                            list(cbtd_data.keys()),
                            format_func=lambda k: f"{k} — {cbtd_data[k].get('ho_ten','')} "
                                                  f"({cbtd_data[k].get('pgd','')})",
                            key=f"{_kp_g2}cbtd_chon_xem")
                        info = cbtd_data[chon]
                        ten_cb = info.get("ho_ten", "")
                        pgd_cb = info.get("pgd", "")
                        ds_dgd_cb = info.get("ds_dgd", []) or []

                        # Header 6 cột info
                        ic1, ic2, ic3, ic4, ic5, ic6 = st.columns(6)
                        ic1.metric("Chức vụ", info.get("chuc_vu", "") or "Cán bộ tín dụng")
                        ic2.metric("Số ĐGD", len(ds_dgd_cb))
                        tong_ap_ct = _so_ap_cbtd(info)
                        ic3.metric("Số ấp/phường", tong_ap_ct)
                        so_kl_cb = len(ds_dgd_cb)
                        wl_i, wl_l = _workload_label(so_kl_cb)
                        ic4.metric(f"{wl_i} Workload", wl_l)
                        ic5.metric("Ngày bổ nhiệm", info.get("ngay_bo_nhiem", "") or "—")
                        ic6.metric("SĐT", info.get("dien_thoai", "") or "—")
                        st.divider()

                        # PDF export
                        st.markdown("**📄 Hồ sơ năng lực CBTD** — Xuất PDF 1 trang (A4) gồm: "
                                    "Thông tin cá nhân · Địa bàn phụ trách · KPI HSTD · Tổ TK&VV · Khối ký tên.")

                        # Tính KPI HSTD cho CBTD này
                        kpi_hstd = None
                        tos_info = None
                        if df is not None and not df.empty and ds_dgd_cb:
                            try:
                                from services.cbtd_dia_ban_service import lay_to_theo_cbtd
                                joined = gan_cbtd_vao_df(df, {chon: info}, dgd_map)
                                if COT_HINH_THUC_VAY in joined.columns:
                                    joined = joined[joined[COT_HINH_THUC_VAY] != 1]
                                df_cb = joined[joined["CBTD"] == chon]
                                if not df_cb.empty:
                                    so_kh = int(pd.to_numeric(df_cb[COT_MA_KH],
                                                              errors="coerce").dropna().nunique() or 0)
                                    so_mon = int(pd.to_numeric(df_cb[COT_SO_KU],
                                                               errors="coerce").dropna().nunique() or 0)
                                    tdn = float(pd.to_numeric(df_cb[COT_TONG_DU_NO],
                                                              errors="coerce").fillna(0).sum() or 0)
                                    dqh = float(pd.to_numeric(df_cb[COT_DU_NO_QH],
                                                              errors="coerce").fillna(0).sum() or 0)
                                    kpi_hstd = {
                                        "so_kh": so_kh,
                                        "so_mon_vay": so_mon,
                                        "du_no_ty": tdn / 1_000_000_000,
                                        "du_no_qh_ty": dqh / 1_000_000_000,
                                        "tl_qh_pct": (dqh / tdn * 100) if tdn > 0 else 0,
                                    }
                                    # Lấy list Tổ
                                    try:
                                        # Không có df_cdtotkvv truyền vào → None (tạm chấp nhận)
                                        to_dict = lay_to_theo_cbtd({chon: info}, dgd_map, None) or {}
                                        tos_info = to_dict.get(chon) or []
                                    except Exception:
                                        tos_info = []
                            except Exception as e:
                                logger.warning("Chi tiết CBTD KPI HSTD %s: %s", chon, e, exc_info=True)

                        col1_pdf, col2_pdf = st.columns([3, 1])
                        with col1_pdf:
                            st.caption("Tùy chọn nội dung PDF (có thể bỏ bớt nếu in ngắn gọn):")
                            co1, co2, co3, co4 = st.columns(4)
                            ck_tt = co1.checkbox("Thông tin cá nhân", True,
                                                 key=f"{_kp_g2}cbtd_ck_tt_{chon}")
                            ck_db = co2.checkbox("Địa bàn + ĐGD", True,
                                                 key=f"{_kp_g2}cbtd_ck_db_{chon}")
                            ck_kp = co3.checkbox("KPI HSTD", True,
                                                 key=f"{_kp_g2}cbtd_ck_kp_{chon}")
                            ck_to = co4.checkbox("Danh sách Tổ TK&VV", True,
                                                 key=f"{_kp_g2}cbtd_ck_to_{chon}")
                        with col2_pdf:
                            pdf_bytes = _build_profile_pdf(chon, info,
                                                           kpi_hstd if ck_kp else None,
                                                           tos_info if ck_to else None,
                                                           pgd_user_override=pgd_user or None)
                            if pdf_bytes:
                                if st.download_button(
                                    "⬇️ Tải PDF hồ sơ",
                                    data=pdf_bytes,
                                    file_name=f"CBTD_{chon}_{ten_cb}_HoSoNangLuc.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"{_kp_g2}btn_export_pdf_{chon}",
                                ):
                                    db.ghi_audit(username, "xuat_pdf_cbtd",
                                                 f"Xuất PDF hồ sơ năng lực {chon} — {ten_cb}")
                            else:
                                st.button("⬇️ Tải PDF hồ sơ", disabled=True,
                                          use_container_width=True,
                                          key=f"{_kp_g2}btn_export_pdf_{chon}")
                                st.caption("⚠️ Lỗi tạo PDF — xem log.")
                        st.divider()

                        st.markdown("**1️⃣ Thông tin cá nhân & Kinh nghiệm**")
                        with st.container(border=True):
                            i1, i2 = st.columns(2)
                            i1.write(f"**Họ và tên:** {ten_cb}")
                            i1.write(f"**Chức vụ:** {info.get('chuc_vu', '') or 'Cán bộ tín dụng'}")
                            i1.write(f"**Ngày bổ nhiệm:** {info.get('ngay_bo_nhiem', '') or '—'}")
                            i1.write(f"**Số điện thoại:** {info.get('dien_thoai', '') or '—'}")
                            i2.write(f"**Đơn vị PGD trực thuộc:** {pgd_cb}")
                            i2.write(f"**Mã CBTD:** {chon}")
                            i2.write(f"**Ghi chú:** {info.get('ghi_chu', '') or '—'}")
                            i2.write(f"**Ngày cập nhật gần nhất:** {info.get('ngay_cap', '') or '—'}")

                        st.divider()
                        st.markdown("**2️⃣ Địa bàn phụ trách (Điểm Giao Dịch & Thôn/ấp)**")
                        with st.container(border=True):
                            if not ds_dgd_cb:
                                st.info("⚠️ CBTD này chưa được gán ĐGD nào. Sử dụng **Chỉnh sửa** để cập nhật.")
                            else:
                                rows_ct = []
                                for idx, dgd_name in enumerate(ds_dgd_cb, 1):
                                    ap_list = _ap_cua_dgd(pgd_cb, dgd_name)
                                    xa_name = "—"
                                    for xa_k, dgd_block in dgd_map.get(pgd_cb, {}).items():
                                        if isinstance(dgd_block, dict) and dgd_name in dgd_block:
                                            xa_name = xa_k
                                            break
                                    rows_ct.append({
                                        "STT": idx,
                                        "Xã/Phường": xa_name,
                                        "Điểm Giao Dịch": dgd_name,
                                        "Số ấp/thôn": len(ap_list),
                                        "Danh sách ấp/thôn": ", ".join(ap_list) or "—",
                                    })
                                hien_thi_dataframe_phan_trang(pd.DataFrame(rows_ct),
                                                              key=f"{_kp_g2}cbtd_ct_ap")

                        st.divider()
                        st.markdown("**3️⃣ KPI tổng hợp từ HSTD**")
                        with st.container(border=True):
                            if not kpi_hstd:
                                st.info("Chưa có dữ liệu HSTD cho CBTD này.")
                            else:
                                k1, k2, k3, k4, k5 = st.columns(5)
                                k1.metric("Số KH vay", fmt_so(kpi_hstd["so_kh"]))
                                k2.metric("Số món vay", fmt_so(kpi_hstd["so_mon_vay"]))
                                k3.metric("Tổng dư nợ (tỷ)", f"{kpi_hstd['du_no_ty']:,.2f}")
                                k4.metric("Dư nợ QH (tỷ)", f"{kpi_hstd['du_no_qh_ty']:,.2f}")
                                k5.metric("Tỷ lệ QH", f"{kpi_hstd['tl_qh_pct']:,.2f} %")
                                if kpi_hstd["tl_qh_pct"] >= 2:
                                    st.warning("⚠️ Tỷ lệ QH ≥ 2% — cần rà soát và kiểm soát.")
                                elif kpi_hstd["tl_qh_pct"] > 0:
                                    st.caption(f"ℹ️ Có {kpi_hstd['du_no_qh_ty']:,.2f} tỷ dư nợ chất vấn — đang theo dõi.")
                                else:
                                    st.success("✅ Không có dư nợ chất vấn — chất lượng tài sản tốt.")

                        st.divider()
                        st.markdown("**4️⃣ Cross-link: Tổ TK&VV thuộc địa bàn CBTD này**")
                        with st.container(border=True):
                            if not tos_info:
                                st.caption("ℹ️ Chưa load dữ liệu Tổ TK&VV (chỉ render ở Tab CDTO TKVV). "
                                           "Click vào Tab Tổ để xem chi tiết từng tổ.")
                            else:
                                st.caption(f"🏘️ Tổng **{len(tos_info)}** Tổ TK&VV thuộc địa bàn CBTD này.")
                                hien_thi_dataframe_phan_trang(pd.DataFrame(tos_info),
                                                              key=f"{_kp_g2}cbtd_ct_to_tkvv")

                st.divider()

                # ════════════════════════════════════════════════════════════════════
                # CRUD (admin + manager CN)
                # ════════════════════════════════════════════════════════════════════
                if not la_quan_ly_cn(role):
                    st.caption("🔒 Chỉ **Quản lý Chi nhánh** (admin/manager_cn) mới được thêm/sửa/xóa CBTD. "
                               "PGD/CBTD địa bàn vui lòng liên hệ phòng KH-NV.")
                else:
                    che_do = st.radio(
                        "Thao tác",
                        ["➕ Thêm mới", "✏️ Chỉnh sửa", "🗑️ Xóa"],
                        horizontal=True, key=f"{_kp_g2}cbtd_mode")

                    # ── THÊM MỚI ─────────────────────────────────────────────────────
                    if che_do == "➕ Thêm mới":
                        add_ver_key = f"{_kp_g2}cbtd_add_ver"
                        add_ver = int(st.session_state.get(add_ver_key, 0) or 0)
                        add_kp = _cbtd_add_form_prefix(_kp_g2, add_ver)
                        st.markdown("**➕ Thêm CBTD mới**")
                        c1, c2 = st.columns(2)
                        with c1:
                            ma_default = _auto_gen_ma_cb(DS_PGD_ALL[0] if not cbtd_data
                                                         else list(cbtd_data.values())[-1].get("pgd", DS_PGD_ALL[0]),
                                                         cbtd_data)
                            ma_new = st.text_input(
                                "Mã CBTD * (để trống = tự sinh)",
                                value=ma_default,
                                key=f"{add_kp}cbtd_ma_new",
                                help="Format: CB_<PGD>_<số thứ tự>, vd: CB_BIEN_HOA_001")
                            ten_new = st.text_input(
                                "Họ và tên *",
                                key=f"{add_kp}cbtd_ten_new",
                                placeholder="vd: Nguyễn Văn A")
                            chuc_vu_new = st.selectbox(
                                "Chức vụ *",
                                CHUC_VU_OPTS, index=0,
                                key=f"{add_kp}cbtd_chuc_vu_new")
                            ngay_bn_new = st.date_input(
                                "Ngày bổ nhiệm",
                                format="DD/MM/YYYY",
                                value=date.today(),
                                key=f"{add_kp}cbtd_ngay_bn_new")
                            dt_new = st.text_input(
                                "Số điện thoại",
                                placeholder="vd: 0912345678",
                                key=f"{add_kp}cbtd_dt_new")
                            gc_new = st.text_input(
                                "Ghi chú",
                                placeholder="(không bắt buộc)",
                                key=f"{add_kp}cbtd_gc_new")
                        with c2:
                            pgd_new = st.selectbox(
                                "PGD trực thuộc *",
                                DS_PGD_ALL, index=0,
                                key=f"{add_kp}cbtd_pgd_new")
                            dgd_opts_new = _ds_dgd_cua_pgd(pgd_new)
                            if not dgd_opts_new:
                                st.warning(f"PGD **{pgd_new}** chưa cấu hình ĐGD.")
                                dgd_sel_new = []
                            else:
                                labels_new = [_label_dgd_day_du(pgd_new, xa, d) for xa, d in dgd_opts_new]
                                label_to_dgd_new = {
                                    _label_dgd_day_du(pgd_new, xa, d): d
                                    for xa, d in dgd_opts_new
                                }
                                sel_labels = st.multiselect(
                                    "ĐGD phụ trách * (chọn nhiều cùng lúc)",
                                    labels_new,
                                    help="1 CBTD phụ trách 2–4 ĐGD trong cùng PGD — chọn hết rồi mới LƯU 1 lần",
                                    key=f"{add_kp}cbtd_dgd_new")
                                dgd_sel_new = [label_to_dgd_new[lbl] for lbl in sel_labels if lbl in label_to_dgd_new]

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

                        if st.button("💾 LƯU CBTD MỚI", type="primary", key=f"{_kp_g2}btn_them_cbtd"):
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
                                key=f"{_kp_g2}cbtd_chon_sua")
                            info_cu = cbtd_data[chon_sua]
                            # Khởi tạo giá trị mặc định cho trường mới (nếu chưa có từ schema cũ)
                            chuc_vu_cu = info_cu.get("chuc_vu", "") or "Cán bộ tín dụng"
                            ngay_bn_cu = _ddmmyyyy_to_date(info_cu.get("ngay_bo_nhiem", "")) or date.today()

                            c1, c2 = st.columns(2)
                            with c1:
                                ten_sua = st.text_input("Họ và tên *",
                                    value=info_cu.get("ho_ten",""), key=f"{_kp_g2}cbtd_ten_sua")
                                # Chức vụ (NEW v3)
                                cv_idx_sua = CHUC_VU_OPTS.index(chuc_vu_cu) if chuc_vu_cu in CHUC_VU_OPTS else 0
                                chuc_vu_sua = st.selectbox("Chức vụ *", CHUC_VU_OPTS, index=cv_idx_sua,
                                                           key=f"{_kp_g2}cbtd_chuc_vu_sua")
                                # Ngày bổ nhiệm (NEW v3)
                                ngay_bn_sua = st.date_input("Ngày bổ nhiệm", format="DD/MM/YYYY",
                                                            value=ngay_bn_cu,
                                                            key=f"{_kp_g2}cbtd_ngay_bn_sua")
                                dt_sua  = st.text_input("Số điện thoại",
                                    value=info_cu.get("dien_thoai",""), key=f"{_kp_g2}cbtd_dt_sua",
                                    placeholder="vd: 0912345678")
                                gc_sua  = st.text_input("Ghi chú",
                                    value=info_cu.get("ghi_chu",""), key=f"{_kp_g2}cbtd_gc_sua")
                                pgd_idx = DS_PGD_ALL.index(info_cu["pgd"]) if info_cu.get("pgd") in DS_PGD_ALL else 0
                                pgd_sua = st.selectbox("PGD trực thuộc *",
                                    DS_PGD_ALL, index=pgd_idx, key=f"{_kp_g2}cbtd_pgd_sua")

                            with c2:
                                dgd_opts_sua = _ds_dgd_cua_pgd(pgd_sua)
                                if not dgd_opts_sua:
                                    st.warning(f"PGD **{pgd_sua}** chưa cấu hình ĐGD.")
                                    dgd_sel_sua = []
                                else:
                                    labels_sua = [_label_dgd_day_du(pgd_sua, xa, d) for xa, d in dgd_opts_sua]
                                    label_to_dgd_sua = {
                                        _label_dgd_day_du(pgd_sua, xa, d): d
                                        for xa, d in dgd_opts_sua
                                    }
                                    ds_dgd_cu  = info_cu.get("ds_dgd", []) if pgd_sua == info_cu.get("pgd") else []
                                    default_labels = [_label_dgd_day_du(pgd_sua, xa, d) for xa, d in dgd_opts_sua
                                                      if d in ds_dgd_cu]
                                    sel_labels_sua = st.multiselect(
                                        "ĐGD phụ trách * (chọn nhiều rồi Lưu 1 lần)",
                                        labels_sua,
                                        default=default_labels,
                                        help="Chọn nhiều ĐGD cùng lúc → 1 nút Lưu cuối cùng",
                                        key=f"{_kp_g2}cbtd_dgd_sua")
                                    dgd_sel_sua = [label_to_dgd_sua[lbl] for lbl in sel_labels_sua if lbl in label_to_dgd_sua]

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

                            if st.button("💾 Lưu thay đổi", type="primary", key=f"{_kp_g2}btn_luu_sua"):
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
                                key=f"{_kp_g2}cbtd_chon_xoa")
                            info_xoa = cbtd_data[chon_xoa]
                            st.warning(
                                f"⚠️ Sắp xóa: **{chon_xoa}** — {info_xoa['ho_ten']}\n\n"
                                f"PGD: {info_xoa.get('pgd','?')} | "
                                f"ĐGD: {', '.join(info_xoa.get('ds_dgd',[]))}"
                            )
                            xn = st.checkbox("Xác nhận xóa", key=f"{_kp_g2}cbtd_xn_xoa")
                            if st.button("🗑️ Xóa", type="primary",
                                         disabled=not xn, key=f"{_kp_g2}btn_xoa_cbtd"):
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

                hien_thi_dataframe_phan_trang(pd.DataFrame(rows_bc), key=f"{_kp_g2}cbtd_bc_tong_hop")

                if st.button("📥 Xuất báo cáo CBTD", key=f"{_kp_g2}btn_xuat_cbtd"):
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
                        key=f"{_kp_g2}dl_cbtd",
                    ):
                        state.downloads.clear("cbtd_excel")

        # ── Nhóm 3: KHTD & Giao chỉ tiêu ────────────────────────────────────
        def _render_g3(_c):
            with _c:
                st.info(
                    "📝 **[Nhóm 3 / Đầu tháng] KHTD & Giao chỉ tiêu theo từng CBTD** — Sẽ cập nhật sau Step 4:\n\n"
                    "• Giao chỉ tiêu tháng mới (Dư nợ / Giải ngân / KH mới / NQH / Tổ mới) cho từng CBTD\n"
                    "• Xem lịch sử TH/CT tháng N-1 so sánh tháng N\n"
                    "• Điều chỉnh giữa kỳ (phân bổ lại chỉ tiêu nếu CBTD nghỉ / luân chuyển)\n"
                    "• Xuất quyết định giao chỉ tiêu (Word PDF)"
                )

        # ── Nhóm 4: Tác nghiệp & Đôn đốc hàng ngày ──────────────────────────
        def _render_g4(_c):
            with _c:
                st.info(
                    "📝 **[Nhóm 4 / Giữa tháng] Tác nghiệp & Đôn đốc hàng ngày** — Sẽ cập nhật sau Step 3 helper:\n\n"
                    "• ① Hợp đồng đến hạn trả nợ hôm nay / trong 7 ngày tới\n"
                    "• ② Kiểm soát NQH 30/60/90 ngày (theo từng CBTD địa bàn)\n"
                    "• ③ Đôn đốc Giải ngân (đơn chờ duyệt > 3 ngày)\n"
                    "• ④ KH mới tháng này (theo dõi tiến độ)\n"
                    "• ⑤ Đôn đốc 3 tháng KHD (không hoạt động) — reuse logic tab_don_doc_khd\n"
                    "• ⑥ Phiếu đến hạn (export Word - Phiếu 01/02/03)\n"
                    "• Export Excel danh sách NQH chi tiết theo CBTD"
                )

        # ── Nhóm 5: Xếp hạng & Báo cáo cuối tháng ──────────────────────────
        def _render_g5(_c):
            with _c:
                st.info(
                    "📝 **[Nhóm 5 / Cuối tháng] Xếp hạng & Báo cáo** — Dùng service `xep_hang_cbtd()` đã có (cbtd_dia_ban_service.py L568):\n\n"
                    "• Chấm điểm tháng N tự động theo scorecard (0-100 clamp) — reuse `xep_hang_cbtd()`\n"
                    "• BXH toàn chi nhánh (Xuất sắc 85+ / Tốt 70-85 / Khá 55-70 / TB 40-55 / Yếu <40)\n"
                    "• Soạn nội dung giao ban ngày 01 tháng tự động từ BXH + Top 3 CBTD xuất sắc\n"
                    "• Xuất báo cáo cuối tháng (Word + PDF) — reuse template Word\n"
                    "• Download BXH Excel (có format màu theo xếp loại)"
                )

        # ── Nhóm 6: Công cụ bổ trợ ──────────────────────────────────────────
        def _render_g6(_c):
            with _c:
                st.info(
                    "📝 **[Nhóm 6 / Công cụ] Mapping & Mẫu biểu VBSP** — Sẽ cập nhật sau Step 4:\n\n"
                    "• ① Mapping ĐGD view theo từng CBTD (1 CBTD = bao nhiêu ĐGD = bao nhiêu ấp)\n"
                    "• ② Mapping Tổ TK&VV → CBTD (từ ĐGD auto-infer, có override manual) — persist kv_store\n"
                    "• ③ Xuất 10 mẫu biểu VBSP (Phiếu 01 → 10) theo khối Word\n"
                    "• ④ Tìm kiếm nâng cao Hợp đồng (tên KH / SĐT / CCCD / số tiền / ngày đến hạn)"
                )

        labels_final = list(labels_lv2)
        renderers_final = [
            _render_g1, _render_g2, _render_g3, _render_g4, _render_g5, _render_g6,
        ]
        _scope_slug = pgd_user.replace(" ", "_").lower() if pgd_user else "cn"
        lazy_tabs(labels_final, renderers_final, key=f"cbtd_lv2_{_scope_slug}")
