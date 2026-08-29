"""PDF generation functions cho module Tiến độ Công việc.

Chứa:
- _xuat_pdf_bao_cao_tien_do: Xuất PDF báo cáo tổng hợp nhiều đầu việc
- _xuat_pdf_tien_do: Xuất PDF tiến độ cho một đầu việc cụ thể
"""
from __future__ import annotations

from datetime import datetime, date
from io import BytesIO

import streamlit as st

from services.task_data_service import _doc_ketqua_task, _PGD_BIEN_HOA
from config import TEN_CHI_NHANH_HIEN_THI
from utils import fmt_ngay

LOAI_TASK = {
    "chung":            "📋 Công việc chung",
    "chi_tieu_khtd":    "🎯 Chỉ tiêu KHTD",
    "ho_so_rui_ro":     "🗂️ Hồ sơ rủi ro",
    "khao_sat_nhu_cau": "📊 Khảo sát nhu cầu vay vốn",
    "bao_cao":          "📄 Báo cáo",
    "tap_huan":         "🎓 Tập huấn",
    "giao_dich_xa":     "📅 Giao dịch xã",
    "uy_thac":          "🤝 Hoạt động ủy thác",
    "nguon_von":        "💰 Nguồn vốn",
    "ban_dai_dien":     "📑 Ban đại diện HĐQT",
    "khac":             "Khác",
}
UU_TIEN = {
    "khan_cap":    "🔴 Khẩn cấp",
    "quan_trong":  "🟡 Quan trọng",
    "binh_thuong": "🟢 Bình thường",
}


def _xuat_pdf_bao_cao_tien_do(ds_task, username):
    try:
        from pdf_service import _dang_ky_font, VBSP_GREEN, ROW_ALT, BORDER_COLOR, _REPORTLAB_READY
        if not _REPORTLAB_READY:
            st.error("Chưa cài thư viện reportlab. Chạy: pip install reportlab")
            return None
        _dang_ky_font()

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, HRFlowable, PageBreak,
        )
        from io import BytesIO
        from datetime import date, datetime
        import json

        FONT_NORMAL = "TNR"
        FONT_BOLD = "TNR-Bold"
        FONT_FALLBACK = "Helvetica"

        fn = FONT_NORMAL if FONT_NORMAL else FONT_FALLBACK
        fb = FONT_BOLD if FONT_BOLD else FONT_FALLBACK

        hom_nay = date.today().isoformat()
        ngay_str = datetime.now().strftime("%d/%m/%Y")
        buf = BytesIO()
        margin = 1.5 * cm
        page_size = A4
        usable_w = page_size[0] - 2 * margin

        doc = SimpleDocTemplate(
            buf, pagesize=page_size,
            leftMargin=margin, rightMargin=margin,
            topMargin=margin, bottomMargin=1.5 * cm,
            title=f"Báo cáo tiến độ công việc {ngay_str}",
            author="VBSP-SCM",
        )

        story = []

        # ── Header ─────────────────────────────────────────────────────
        story.append(Paragraph(
            "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM",
            ParagraphStyle("bank", fontName=fb, fontSize=13,
                           alignment=TA_CENTER, spaceAfter=2)
        ))
        story.append(Paragraph(
            TEN_CHI_NHANH_HIEN_THI.upper(),
            ParagraphStyle("branch", fontName=fn, fontSize=11,
                           alignment=TA_CENTER, spaceAfter=4)
        ))
        story.append(HRFlowable(width="100%", thickness=1.5,
                                color=colors.HexColor("#2E7D32"), spaceAfter=6))
        story.append(Paragraph(
            f"BÁO CÁO TIẾN ĐỘ CÔNG VIỆC — {ngay_str}",
            ParagraphStyle("title", fontName=fb, fontSize=14,
                           alignment=TA_CENTER, spaceAfter=4,
                           textColor=colors.HexColor("#003D7A"))
        ))
        story.append(Paragraph(
            f"Người xuất: {username}  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle("meta", fontName=fn, fontSize=9,
                           alignment=TA_CENTER, spaceAfter=10,
                           textColor=colors.grey)
        ))

        # ── Phần 1: Tiến độ theo đầu việc ─────────────────────────────
        story.append(Paragraph(
            "PHẦN 1: TIẾN ĐỘ THEO ĐẦU VIỆC",
            ParagraphStyle("p1_title", fontName=fb, fontSize=11,
                           alignment=TA_LEFT, spaceBefore=4, spaceAfter=6,
                           textColor=colors.HexColor("#2E7D32"))
        ))

        task_header_s = ParagraphStyle("task_h", fontName=fb, fontSize=13,
                                       leading=17, spaceBefore=10, spaceAfter=3,
                                       textColor=colors.HexColor("#003D7A"))
        task_meta_s = ParagraphStyle("task_m", fontName=fn, fontSize=11,
                                     leading=15, spaceAfter=4, textColor=colors.grey)
        pgd_group_s = ParagraphStyle("pgd_g", fontName=fb, fontSize=10,
                                     leading=14, spaceBefore=4, spaceAfter=1,
                                     textColor=colors.HexColor("#2E7D32"))
        xa_line_s = ParagraphStyle("xa_l", fontName=fn, fontSize=9,
                                   leading=12, leftIndent=12)
        th_s = ParagraphStyle("th", fontName=fb, fontSize=11,
                              alignment=TA_CENTER, textColor=colors.white,
                              leading=14)
        td_s = ParagraphStyle("td", fontName=fn, fontSize=11,
                              leading=14, wordWrap="CJK")
        td_c = ParagraphStyle("td_c", fontName=fn, fontSize=11,
                              alignment=TA_CENTER, leading=14)
        td_green = ParagraphStyle("td_green", fontName=fn, fontSize=11,
                                  alignment=TA_CENTER, leading=14,
                                  textColor=colors.HexColor("#2E7D32"))
        td_red = ParagraphStyle("td_red", fontName=fn, fontSize=11,
                                alignment=TA_CENTER, leading=14,
                                textColor=colors.HexColor("#C62828"))
        td_r = ParagraphStyle("td_r", fontName=fn, fontSize=11,
                              alignment=TA_RIGHT, leading=14)

        for i, t in enumerate(ds_task, 1):
            kq = _doc_ketqua_task(t["id"])
            cbtd_bien_hoa = str(t.get("cbtd_bien_hoa") or "").strip()
            if cbtd_bien_hoa and not any(r.get("ten_xa") == _PGD_BIEN_HOA for r in kq):
                kq = list(kq or [])
                kq.append({
                    "pgd": _PGD_BIEN_HOA,
                    "ten_xa": _PGD_BIEN_HOA,
                    "trang_thai": "chua_thuc_hien",
                    "ngay_hoan_thanh": None,
                    "ghi_chu": "",
                })
            xong = sum(1 for r in kq if r["trang_thai"] == "da_hoan_thanh")
            tong = len(kq)
            pct = round(xong / tong * 100) if tong else 0

            loai_label = LOAI_TASK.get(t["loai"], t["loai"])
            nguoi_pt = t.get("nguoi_phu_trach") or "—"
            cap = t.get("cap_theo_doi", "xa")

            tag_cap = "🏢 Theo dõi chung PGD" if cap == "pgd" else "📍 Theo dõi chi tiết xã"

            if pct == 100:
                css_cls = "✅ Hoàn thành"
            elif t["ngay_deadline"] < hom_nay:
                css_cls = "🔴 Trễ hạn"
            else:
                css_cls = "⏳ Đang thực hiện"

            story.append(Paragraph(
                f"{i}. {t['tieu_de']}",
                task_header_s
            ))
            story.append(Paragraph(
                f"Thời hạn cuối cùng: {fmt_ngay(t['ngay_deadline'])} | Tiến độ hoàn thành: {pct}% | "
                f"{css_cls} | Loại: {loai_label} | {tag_cap} | "
                f"Người PT: {nguoi_pt}",
                task_meta_s
            ))

            if cap == "pgd":
                pgd_order = sorted(set(r["pgd"] for r in kq), key=lambda x: (x == _PGD_BIEN_HOA, x))
                tbl_data = [[
                    Paragraph("STT", th_s),
                    Paragraph("PGD", th_s),
                    Paragraph("Trạng thái", th_s),
                    Paragraph("Ghi chú", th_s),
                ]]
                for j, pgd in enumerate(pgd_order, 1):
                    r_pgd = next((r for r in kq if r["pgd"] == pgd), {})
                    tt = r_pgd.get("trang_thai", "chua_thuc_hien")
                    if tt == "da_hoan_thanh":
                        tt_txt = "✅ Hoàn thành"
                        stt_style = td_green
                    elif tt == "khong_ap_dung":
                        tt_txt = "➖ N/A"
                        stt_style = td_c
                    else:
                        tt_txt = "⬜ Chưa thực hiện"
                        stt_style = td_red
                    gc = (r_pgd.get("ghi_chu") or "").strip()
                    tbl_data.append([
                        Paragraph(str(j), td_c),
                        Paragraph(pgd, td_s),
                        Paragraph(tt_txt, stt_style),
                        Paragraph(gc, td_s),
                    ])
                cw = [1.5 * cm, 7.0 * cm, 3.5 * cm, 6.0 * cm]
                tbl = Table(tbl_data, colWidths=cw, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDBDBD")),
                ]))
                for r_idx in range(1, len(tbl_data)):
                    if r_idx % 2 == 0:
                        tbl.setStyle(TableStyle([
                            ("BACKGROUND", (0, r_idx), (-1, r_idx),
                             colors.HexColor("#F5F5F5"))
                        ]))
                story.append(tbl)
            else:
                tbl_data = [[
                    Paragraph("STT", th_s),
                    Paragraph("PGD", th_s),
                    Paragraph("Xã / Phường", th_s),
                    Paragraph("Trạng thái", th_s),
                    Paragraph("Ghi chú", th_s),
                ]]
                for j, r in enumerate(
                    sorted(kq, key=lambda x: (x["pgd"], x["ten_xa"])), 1
                ):
                    tt = r["trang_thai"]
                    if tt == "da_hoan_thanh":
                        tt_txt = "✅ Hoàn thành"
                        stt_style = td_green
                        ngay_ht = r.get("ngay_hoan_thanh") or ""
                        try:
                            ngay_ht = datetime.strptime(
                                ngay_ht[:10], "%Y-%m-%d"
                            ).strftime("%d/%m/%Y")
                        except Exception:
                            pass
                        gc = ngay_ht
                    elif tt == "khong_ap_dung":
                        tt_txt = "➖ N/A"
                        stt_style = td_c
                        gc = ""
                    else:
                        tt_txt = "⬜ Chưa thực hiện"
                        stt_style = td_red
                        gc = ""
                    tbl_data.append([
                        Paragraph(str(j), td_c),
                        Paragraph(r["pgd"], td_s),
                        Paragraph(r["ten_xa"] or "", td_s),
                        Paragraph(tt_txt, stt_style),
                        Paragraph(gc, td_s),
                    ])
                cw = [1.2 * cm, 5.2 * cm, 4.3 * cm, 3.3 * cm, 4.0 * cm]
                tbl = Table(tbl_data, colWidths=cw, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDBDBD")),
                ]))
                for r_idx in range(1, len(tbl_data)):
                    if r_idx % 2 == 0:
                        tbl.setStyle(TableStyle([
                            ("BACKGROUND", (0, r_idx), (-1, r_idx),
                             colors.HexColor("#F5F5F5"))
                        ]))
                story.append(tbl)

            story.append(Spacer(1, 0.3 * cm))
            story.append(HRFlowable(width="60%", thickness=0.3,
                                    color=colors.HexColor("#E0E0E0"),
                                    spaceAfter=2))

        # ── Page break → Phần 2 ───────────────────────────────────────
        story.append(PageBreak())

        story.append(Paragraph(
            "PHẦN 2: BÁO CÁO TRỄ HẠN",
            ParagraphStyle("p2_title", fontName=fb, fontSize=11,
                           alignment=TA_LEFT, spaceBefore=4, spaceAfter=6,
                           textColor=colors.HexColor("#C62828"))
        ))

        p2_th = ParagraphStyle("p2_th", fontName=fb, fontSize=11,
                                alignment=TA_CENTER, textColor=colors.white,
                                leading=14)
        p2_td = ParagraphStyle("p2_td", fontName=fn, fontSize=11,
                               leading=14, wordWrap="CJK")
        p2_td_c = ParagraphStyle("p2_td_c", fontName=fn, fontSize=11,
                                 alignment=TA_CENTER, leading=14)
        p2_td_r = ParagraphStyle("p2_td_r", fontName=fb, fontSize=11,
                                 alignment=TA_CENTER, leading=14,
                                 textColor=colors.HexColor("#C62828"))

        p2_count = 0
        for t in ds_task:
            if t["ngay_deadline"] >= hom_nay:
                continue
            kq = _doc_ketqua_task(t["id"])
            tre_list = [r for r in kq if r["trang_thai"] == "chua_thuc_hien"]
            if not tre_list:
                continue

            so_ngay_tre = (date.today() -
                           date.fromisoformat(t["ngay_deadline"])).days
            cap = t.get("cap_theo_doi", "xa")

            story.append(Paragraph(
                f"▪ {t['tieu_de']} — Trễ {so_ngay_tre} ngày (thời hạn: {fmt_ngay(t['ngay_deadline'])})",
                ParagraphStyle("p2_task", fontName=fb, fontSize=11,
                               leading=15, spaceBefore=8, spaceAfter=3,
                               textColor=colors.HexColor("#C62828"))
            ))

            if cap == "pgd":
                cols = ["STT", "PGD", "Số ngày trễ"]
                tbl_data = [[Paragraph(c, p2_th) for c in cols]]
                for j, r in enumerate(tre_list, 1):
                    p2_count += 1
                    tbl_data.append([
                        Paragraph(str(j), p2_td_c),
                        Paragraph(r["pgd"], p2_td),
                        Paragraph(f"{so_ngay_tre} ngày", p2_td_r),
                    ])
                cw2 = [1.5 * cm, 10.0 * cm, 6.5 * cm]
                tbl2 = Table(tbl_data, colWidths=cw2, repeatRows=1)
                tbl2.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C62828")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDBDBD")),
                ]))
                for r_idx in range(1, len(tbl_data)):
                    if r_idx % 2 == 0:
                        tbl2.setStyle(TableStyle([
                            ("BACKGROUND", (0, r_idx), (-1, r_idx),
                             colors.HexColor("#FFEBEE"))
                        ]))
                story.append(tbl2)
            else:
                cols = ["STT", "PGD", "Xã / Phường", "Số ngày trễ"]
                tbl_data = [[Paragraph(c, p2_th) for c in cols]]
                idx2 = 0
                kq_by_pgd = {}
                for r in tre_list:
                    kq_by_pgd.setdefault(r["pgd"], []).append(r)
                for pgd, items in sorted(kq_by_pgd.items()):
                    for r in items:
                        idx2 += 1
                        p2_count += 1
                        tbl_data.append([
                            Paragraph(str(idx2), p2_td_c),
                            Paragraph(pgd, p2_td),
                            Paragraph(r["ten_xa"], p2_td),
                            Paragraph(f"{so_ngay_tre} ngày", p2_td_r),
                        ])
                cw2 = [1.2 * cm, 5.5 * cm, 6.5 * cm, 4.8 * cm]
                tbl2 = Table(tbl_data, colWidths=cw2, repeatRows=1)
                tbl2.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C62828")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDBDBD")),
                ]))
                for r_idx in range(1, len(tbl_data)):
                    if r_idx % 2 == 0:
                        tbl2.setStyle(TableStyle([
                            ("BACKGROUND", (0, r_idx), (-1, r_idx),
                             colors.HexColor("#FFEBEE"))
                        ]))
                story.append(tbl2)

        if p2_count > 0:
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph(
                f"Tổng số: {p2_count} đơn vị trễ hạn",
                ParagraphStyle("sum", fontName=fb, fontSize=10,
                               alignment=TA_CENTER, spaceBefore=8,
                               textColor=colors.HexColor("#C62828"))
            ))
        else:
            story.append(Paragraph(
                "✅ Không có đơn vị nào trễ hạn.",
                ParagraphStyle("ok", fontName=fn, fontSize=10,
                               alignment=TA_CENTER, spaceAfter=6,
                               textColor=colors.HexColor("#2E7D32"))
            ))

        # ── Chữ ký ───────────────────────────────────────────────────
        story.append(Spacer(1, 0.6 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor("#BDBDBD"), spaceAfter=4))
        sig_style = ParagraphStyle("sig", fontName=fn, fontSize=11,
                                   alignment=TA_CENTER, leading=15)
        sig_bold = ParagraphStyle("sig_b", fontName=fb, fontSize=12,
                                  alignment=TA_CENTER, leading=17)
        sig_data = [[
            Paragraph("Người lập", sig_bold),
            Paragraph("Kiểm soát", sig_bold),
            Paragraph("Giám đốc", sig_bold),
        ], [
            Paragraph("(Ký, ghi rõ họ tên)", sig_style),
            Paragraph("(Ký, ghi rõ họ tên)", sig_style),
            Paragraph("(Ký, ghi rõ họ tên, đóng dấu)", sig_style),
        ]]
        sig_tbl = Table(sig_data, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
        sig_tbl.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(sig_tbl)

        # ── Footer ────────────────────────────────────────────────────
        def _on_page(canvas, _doc):
            canvas.saveState()
            canvas.setFont(fn if FONT_NORMAL else FONT_FALLBACK, 8)
            canvas.setFillColor(colors.grey)
            canvas.drawRightString(
                page_size[0] - margin,
                0.6 * cm,
                f"Trang {_doc.page}  |  VBSP-SCM  |  {ngay_str}"
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        buf.seek(0)
        return buf

    except Exception as e:  # conv: skip
        st.error(f"Lỗi tạo PDF báo cáo tiến độ: {e}")
        return None


def _xuat_pdf_tien_do(task, ds_kq, username):
    try:
        from itertools import groupby
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import os

        FONT_NORMAL = "Helvetica"
        FONT_BOLD = "Helvetica-Bold"

        arial_path = "C:/Windows/Fonts/arial.ttf"
        arialbd_path = "C:/Windows/Fonts/arialbd.ttf"
        if os.path.exists(arial_path):
            pdfmetrics.registerFont(TTFont("ArialUni", arial_path))
            FONT_NORMAL = "ArialUni"
        if os.path.exists(arialbd_path):
            pdfmetrics.registerFont(TTFont("ArialUni-Bold", arialbd_path))
            FONT_BOLD = "ArialUni-Bold"

        ds_kq = list(ds_kq or [])
        cbtd_bien_hoa = str(task.get("cbtd_bien_hoa") or "").strip()
        if cbtd_bien_hoa and not any(r.get("ten_xa") == _PGD_BIEN_HOA for r in ds_kq):
            ds_kq.append({
                "pgd": _PGD_BIEN_HOA,
                "ten_xa": _PGD_BIEN_HOA,
                "trang_thai": "chua_thuc_hien",
                "ngay_hoan_thanh": None,
                "ghi_chu": "",
            })

        kq_theo_pgd = {}
        for r in sorted(ds_kq, key=lambda x: x["pgd"]):
            kq_theo_pgd.setdefault(r["pgd"], []).append(r)

        pgd_order = sorted(kq_theo_pgd.keys(), key=lambda x: (x == _PGD_BIEN_HOA, x))

        TS_LABEL = {
            "chua_thuc_hien": "○",
            "da_hoan_thanh": "✓",
            "khong_ap_dung": "—",
        }

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=28, rightMargin=28,
            topMargin=20, bottomMargin=20,
        )

        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "Title_VN", parent=styles["Title"],
            fontName=FONT_BOLD, fontSize=14,
            alignment=TA_CENTER, spaceAfter=2, leading=18,
        )
        subtitle_style = ParagraphStyle(
            "Sub_VN", parent=styles["Normal"],
            fontName=FONT_BOLD, fontSize=12,
            alignment=TA_CENTER, spaceAfter=4, leading=16,
        )
        header_style = ParagraphStyle(
            "Header_VN", parent=styles["Normal"],
            fontName=FONT_BOLD, fontSize=11,
            alignment=TA_CENTER, spaceAfter=6, leading=15,
        )
        normal_style = ParagraphStyle(
            "Normal_VN", parent=styles["Normal"],
            fontName=FONT_NORMAL, fontSize=9, leading=13,
        )
        pgd_header_style = ParagraphStyle(
            "PGDHeader", parent=styles["Normal"],
            fontName=FONT_BOLD, fontSize=10, leading=14,
            spaceBefore=6, spaceAfter=2,
        )
        xa_style = ParagraphStyle(
            "XaStyle", parent=styles["Normal"],
            fontName=FONT_NORMAL, fontSize=9, leading=12, leftIndent=12,
        )
        summary_style = ParagraphStyle(
            "Summary", parent=styles["Normal"],
            fontName=FONT_BOLD, fontSize=10, leading=14,
            spaceBefore=8, spaceAfter=4,
        )

        story.append(Paragraph(
            "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM", title_style))
        story.append(Paragraph(TEN_CHI_NHANH_HIEN_THI.upper(), subtitle_style))
        story.append(Spacer(1, 6))
        story.append(Paragraph("BÁO CÁO TIẾN ĐỘ CÔNG VIỆC", header_style))
        story.append(Paragraph(task.get("tieu_de", ""), header_style))
        story.append(Spacer(1, 4))

        loai = LOAI_TASK.get(task.get("loai", ""), task.get("loai", ""))
        uu_tien = UU_TIEN.get(task.get("uu_tien", ""), task.get("uu_tien", ""))
        deadline = task.get("ngay_deadline", "")
        now = datetime.now()
        ngay_xuat = now.strftime("%d/%m/%Y %H:%M")

        story.append(Paragraph(
            f"Loại: {loai} | Ưu tiên: {uu_tien} | "
            f"Người phụ trách: {task.get('nguoi_phu_trach') or '—'} | "
            f"Từ ngày: {fmt_ngay(task.get('ngay_bat_dau')) or '—'} → Thời hạn: {fmt_ngay(deadline)}",
            normal_style,
        ))
        story.append(Paragraph(
            f"Ngày xuất: {ngay_xuat} | Người xuất: {username}",
            normal_style,
        ))

        story.append(HRFlowable(
            width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 4))

        tong_dv = 0
        tong_dv_ht = 0
        tong_xa_all = 0
        tong_xa_xong_all = 0

        for pgd in pgd_order:
            items = kq_theo_pgd[pgd]
            tong = len(items)
            xong = sum(1 for r in items if r["trang_thai"] == "da_hoan_thanh")
            tong_xa_all += tong
            tong_xa_xong_all += xong
            pct = round(xong / tong * 100) if tong > 0 else 0

            story.append(Paragraph(
                f"<b>{pgd}</b>  ({xong}/{tong} xã — {pct}%)",
                pgd_header_style,
            ))

            for r in items:
                symbol = TS_LABEL.get(r["trang_thai"], "?")
                ten_xa = r["ten_xa"]
                ngay_ht = r.get("ngay_hoan_thanh") or ""

                if r["trang_thai"] == "da_hoan_thanh":
                    try:
                        ngay_ht = datetime.strptime(
                            ngay_ht[:10], "%Y-%m-%d"
                        ).strftime("%d/%m/%Y")
                    except Exception:
                        pass
                    status_text = ngay_ht
                elif r["trang_thai"] == "khong_ap_dung":
                    status_text = "N/A"
                else:
                    status_text = "Chưa thực hiện"

                dots = "." * max(2, 45 - len(ten_xa) - len(status_text))
                line = f"{symbol} {ten_xa} {dots} {status_text}"
                story.append(Paragraph(line, xa_style))

            story.append(Spacer(1, 2))

            tong_dv += 1
            if xong == tong and tong > 0:
                tong_dv_ht += 1

        story.append(HRFlowable(
            width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 6))

        tong_pct = (
            round(tong_xa_xong_all / tong_xa_all * 100)
            if tong_xa_all > 0 else 0
        )
        story.append(Paragraph(
            f"TỔNG KẾT: {tong_dv_ht}/{tong_dv} đơn vị hoàn thành"
            f" | {tong_pct}% toàn Chi nhánh",
            summary_style,
        ))

        doc.build(story)
        buf.seek(0)
        return buf

    except Exception as e:  # conv: skip
        st.error(f"Lỗi tạo PDF: {e}")
        return None
