"""Xuất báo cáo So sánh kỳ — Excel + PDF, 3 loại PDF.

Loại 1 — PDF Pivot (Tổng hợp): agg theo PGD (Số KH, Số món, DN, TH, QH, %)
Loại 2 — PDF Chi tiết (Danh sách đầy đủ): loan-level, COL_CHUNG
Loại 3 — PDF theo Nhóm (PGD): từng PGD 1 bảng chi tiết + dòng tổng
"""
from __future__ import annotations

from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import db
from utils import xuat_excel, fmt_so
from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON, COT_DVUT, COT_TEN_TO,
    COT_MA_KH, COT_TEN_KH, COT_SDT, COT_DIA_CHI,
    COT_SO_KU, COT_NGAY_VAY, COT_NGAY_DH, COT_THOI_HAN,
    COT_LAI_SUAT, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH,
    COT_TONG_DU_NO, COT_TEN_CT, COT_NGUON_VON,
    COT_TINH_TRANG, COT_LAI_TON,
)

try:
    from pdf_service import xuat_pdf_pivot, xuat_pdf_chi_tiet, xuat_pdf_theo_nhom
    _PDF_SERVICE_READY = True
except ImportError:
    _PDF_SERVICE_READY = False


# ─── EXCEL ────────────────────────────────────────────────────────────────

def xuat_excel_tong_quan(
    rows_data: list[tuple],
    ky1: str,
    ky2: str,
) -> bytes:
    """Dạng 1 Excel: 1 sheet Tổng quan."""
    df = pd.DataFrame(rows_data, columns=[
        "Chỉ tiêu", f"Kỳ {ky1}", f"Kỳ {ky2}", "Chênh lệch", "% thay đổi",
    ])
    return xuat_excel({"Tổng quan": df})


def xuat_excel_da_chieu(
    rows_data: list[tuple],
    ky1: str,
    ky2: str,
    sheets_extra: dict[str, pd.DataFrame] | None = None,
) -> bytes:
    """Dạng 2 Excel: Tổng quan + các sheet bổ sung."""
    df_tq = pd.DataFrame(rows_data, columns=[
        "Chỉ tiêu", f"Kỳ {ky1}", f"Kỳ {ky2}", "Chênh lệch", "% thay đổi",
    ])
    all_sheets = {"Tổng quan": df_tq}
    if sheets_extra:
        all_sheets.update(sheets_extra)
    return xuat_excel(all_sheets)


# ─── PDF (qua reportlab) ─────────────────────────────────────────────────

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable, Image as RLImage, PageBreak,
    )
    from reportlab.lib import colors
    import plotly.io as pio
    _PDF_READY = True
except ImportError:
    _PDF_READY = False


def _build_pdf_styles():
    return {
        "title": ParagraphStyle("title", fontSize=16, spaceAfter=6, alignment=TA_CENTER,
                                leading=20, fontName="Helvetica-Bold"),
        "sub": ParagraphStyle("sub", fontSize=9, spaceAfter=10, alignment=TA_CENTER,
                              leading=12, textColor=colors.grey),
        "h": ParagraphStyle("h", fontSize=11, spaceAfter=6, spaceBefore=10,
                            leading=14, fontName="Helvetica-Bold"),
        "body": ParagraphStyle("body", fontSize=8, leading=10, spaceAfter=4),
        "footer": ParagraphStyle("footer", fontSize=7, textColor=colors.grey,
                                 alignment=TA_CENTER, spaceBefore=12),
    }


def _table_style(header_color: str = "#1e3a5f") -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def _rows_to_table(rows: list[tuple], col_headers: list[str]) -> Table:
    data = [col_headers]
    for r in rows:
        data.append([str(c) for c in r])
    t = Table(data, repeatRows=1)
    t.setStyle(_table_style())
    return t


def xuat_pdf_tong_quan(
    rows_data: list[tuple],
    ky1: str,
    ky2: str,
    username: str,
    col_headers: list[str] | None = None,
) -> bytes:
    """Dạng 1 PDF: 1 trang A4 — KPI + bảng chính."""
    if not _PDF_READY:
        return b""

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = _build_pdf_styles()
    elems = []

    elems.append(Paragraph("BÁO CÁO SO SÁNH KỲ", styles["title"]))
    elems.append(Paragraph(f"{ky1} → {ky2}", styles["sub"]))
    elems.append(Paragraph(f"Ngày xuất: {datetime.now():%d/%m/%Y} | Người xuất: {username}",
                           styles["sub"]))
    elems.append(Spacer(1, 4*mm))

    if col_headers is None:
        col_headers = ["Chỉ tiêu", f"Kỳ {ky1}", f"Kỳ {ky2}", "Chênh lệch", "% thay đổi"]
    elems.append(_rows_to_table(rows_data, col_headers))
    elems.append(Spacer(1, 4*mm))

    # Footer
    elems.append(HRFlowable(width="100%", color=colors.HexColor("#d1d5db")))
    elems.append(Paragraph(
        f"VBSP-SCM · Chi nhánh NHCSXH tỉnh Đồng Nai · Trang 1/1",
        styles["footer"],
    ))

    doc.build(elems)
    return buf.getvalue()


def xuat_pdf_da_chieu(
    rows_data: list[tuple],
    ky1: str,
    ky2: str,
    username: str,
    extra_tables: list[tuple[str, list[tuple], list[str]]] | None = None,
    figs: list[tuple[go.Figure, str]] | None = None,
) -> bytes:
    """Dạng 2 PDF: Cover + từng chiều 1 trang + chart."""
    if not _PDF_READY:
        return b""

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = _build_pdf_styles()
    elems = []

    # Cover page
    elems.append(Spacer(1, 6*cm))
    elems.append(Paragraph("BÁO CÁO SO SÁNH KỲ", styles["title"]))
    elems.append(Paragraph(f"{ky1} → {ky2}", styles["sub"]))
    elems.append(Spacer(1, 2*cm))
    elems.append(Paragraph(f"Ngày xuất: {datetime.now():%d/%m/%Y}", styles["sub"]))
    elems.append(Paragraph(f"Người xuất: {username}", styles["sub"]))
    elems.append(Paragraph(f"Đơn vị: Chi nhánh NHCSXH tỉnh Đồng Nai", styles["sub"]))
    elems.append(PageBreak())

    # Tổng quan
    elems.append(Paragraph("1. Tổng quan", styles["h"]))
    col_headers = ["Chỉ tiêu", f"Kỳ {ky1}", f"Kỳ {ky2}", "Chênh lệch", "% thay đổi"]
    elems.append(_rows_to_table(rows_data, col_headers))

    # Extra tables (each on new page)
    if extra_tables:
        for title, extra_rows, extra_cols in extra_tables:
            elems.append(PageBreak())
            elems.append(Paragraph(f"2. {title}", styles["h"]))
            elems.append(_rows_to_table(extra_rows, extra_cols))

    # Charts
    if figs:
        for fig, fig_title in figs:
            try:
                img_bytes = pio.to_image(fig, format="png", width=700, height=380, scale=1.5)
                img = RLImage(BytesIO(img_bytes), width=16*cm, height=8*cm)
                elems.append(Spacer(1, 4*mm))
                elems.append(Paragraph(f"Biểu đồ: {fig_title}", styles["h"]))
                elems.append(img)
            except Exception:
                pass
            elems.append(PageBreak())

    # Footer
    elems.append(HRFlowable(width="100%", color=colors.HexColor("#d1d5db")))
    elems.append(Paragraph(
        "VBSP-SCM · Chi nhánh NHCSXH tỉnh Đồng Nai · Trang cuối",
        styles["footer"],
    ))

    doc.build(elems)
    return buf.getvalue()


def build_excel_sheets_pgd(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    ky1: str,
    ky2: str,
    ten_pgd_col: str = "ten_pgd",
) -> dict[str, pd.DataFrame]:
    """Tạo sheet 'Theo PGD' cho Excel dạng 2."""
    m1 = df1[[ten_pgd_col, "tong_du_no", "du_no_qh", "so_ho"]].copy()
    m2 = df2[[ten_pgd_col, "tong_du_no", "du_no_qh", "so_ho"]].copy()
    m1.columns = ["Đơn vị", f"DN {ky1}", f"NQH {ky1}", f"Hộ {ky1}"]
    m2.columns = ["Đơn vị", f"DN {ky2}", f"NQH {ky2}", f"Hộ {ky2}"]
    merged = pd.merge(m1, m2, on="Đơn vị", how="outer").fillna(0)
    merged["Δ Dư nợ"] = merged[f"DN {ky2}"] - merged[f"DN {ky1}"]
    return {"Theo PGD": merged}


# ─── STREAMLIT UI ────────────────────────────────────────────────────────

def render_export_ui(
    rows_data: list[tuple],
    ky1: str,
    ky2: str,
    username: str,
    sheets_extra: dict[str, pd.DataFrame] | None = None,
    extra_tables: list[tuple[str, list[tuple], list[str]]] | None = None,
    figs: list[tuple[go.Figure, str]] | None = None,
    pgd_mode: bool = False,
    action: str = "xuat_bieu_cn",
    key_prefix: str = "ssk",
) -> None:
    """Section xuất báo cáo: radio chọn dạng + nút download trực tiếp.

    key_prefix phải unique mỗi lần gọi để tránh DuplicateElementKey khi
    render_export_ui xuất hiện nhiều lần trong cùng một Streamlit page.

    Dùng st.session_state để cache bytes, tránh antipattern
    st.button → st.download_button lồng nhau (bytes biến mất sau rerun).
    """
    st.markdown("**📤 Xuất báo cáo**")

    # Chọn dạng Excel và PDF
    col_ex_label, col_ex_opt = st.columns([0.2, 0.8])
    with col_ex_label:
        st.write("📊 Excel:")
    with col_ex_opt:
        ex_type = st.radio(
            "Dạng Excel", ["Tổng quan", "Đa chiều"],
            horizontal=True, key=f"{key_prefix}_ex_type", label_visibility="collapsed",
        )

    col_pdf_label, col_pdf_opt = st.columns([0.2, 0.8])
    with col_pdf_label:
        st.write("📄 PDF:")
    with col_pdf_opt:
        pdf_type = st.radio(
            "Dạng PDF", ["Tổng quan", "Đầy đủ"],
            horizontal=True, key=f"{key_prefix}_pdf_type", label_visibility="collapsed",
        )

    # ── Cache Excel bytes trong session_state theo (prefix, ky1, ky2, dạng) ──
    xl_key = f"_{key_prefix}_xl_{ky1}_{ky2}_{ex_type}"
    if xl_key not in st.session_state:
        if ex_type == "Tổng quan":
            st.session_state[xl_key] = xuat_excel_tong_quan(rows_data, ky1, ky2)
        else:
            st.session_state[xl_key] = xuat_excel_da_chieu(rows_data, ky1, ky2, sheets_extra)

    # ── Cache PDF bytes trong session_state ──
    pdf_key = f"_{key_prefix}_pdf_{ky1}_{ky2}_{pdf_type}"
    if pdf_key not in st.session_state:
        if not _PDF_READY:
            st.session_state[pdf_key] = b""
        elif pdf_type == "Tổng quan":
            st.session_state[pdf_key] = xuat_pdf_tong_quan(rows_data, ky1, ky2, username)
        else:
            st.session_state[pdf_key] = xuat_pdf_da_chieu(
                rows_data, ky1, ky2, username, extra_tables, figs,
            )

    col_ex, col_pdf = st.columns(2)

    with col_ex:
        if st.download_button(
            "📥 Xuất Excel",
            data=st.session_state[xl_key],
            file_name=f"so_sanh_ky_{ky1}_vs_{ky2}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_dl_excel",
            use_container_width=True,
        ):
            db.ghi_audit(username, action,
                         f"Xuất Excel so sánh kỳ: {ky1} vs {ky2} ({ex_type})")

    with col_pdf:
        pdf_bytes = st.session_state[pdf_key]
        if not pdf_bytes:
            st.error(
                "🚨 **Không thể xuất PDF**\n\n"
                "Thư viện **reportlab** chưa được cài đặt. Chạy lệnh:\n\n"
                "`pip install reportlab`"
            )
        else:
            if st.download_button(
                "📄 Xuất PDF",
                data=pdf_bytes,
                file_name=f"so_sanh_ky_{ky1}_vs_{ky2}.pdf",
                mime="application/pdf",
                key=f"{key_prefix}_dl_pdf",
                use_container_width=True,
            ):
                db.ghi_audit(username, action,
                             f"Xuất PDF so sánh kỳ: {ky1} vs {ky2} ({pdf_type})")

    st.caption(f"File: so_sanh_ky_{ky1}_vs_{ky2}.xlsx / .pdf")


# ─── HSTD EXPORT UI (3 loại PDF) ───────────────────────────────────────

def _build_col_chung(df: pd.DataFrame) -> list[str]:
    return [c for c in [
        COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON, COT_DVUT, COT_TEN_TO,
        COT_MA_KH, COT_TEN_KH, COT_SDT, COT_DIA_CHI,
        COT_SO_KU, COT_NGAY_VAY, COT_NGAY_DH, COT_THOI_HAN,
        COT_LAI_SUAT, COT_DU_NO_TH, COT_DU_NO_QH,
        COT_TONG_DU_NO, COT_TEN_CT, COT_NGUON_VON,
        COT_TINH_TRANG,
    ] if c in df.columns]


def render_export_hstd_ui(
    df_ht: pd.DataFrame,
    df_bl: pd.DataFrame,
    label_ht: str,
    label_bl: str,
    rows_data: list[tuple],
    username: str,
    sheets_extra: dict[str, pd.DataFrame] | None = None,
    action: str = "xuat_bieu_cn",
    key_prefix: str = "ssk",
) -> None:
    """Section xuất báo cáo HSTD: 2 mảng (Tổng hợp / Chi tiết) x 3 loại PDF.

    Mảng "📊 Tổng hợp":
      - Excel (tổng quan, có sẵn)
      - PDF Pivot (Loại 1): agg theo PGD
      - PDF theo Nhóm (Loại 3): từng PGD + bảng chi tiết COL_CHUNG

    Mảng "Chi tiết":
      - Excel (tổng quan, có sẵn)
      - PDF Chi tiết (Loại 2): danh sách đầy đủ COL_CHUNG
      - PDF theo Nhóm (Loại 3): từng PGD + bảng chi tiết COL_CHUNG
    """
    st.markdown("**📤 Xuất báo cáo HSTD**")

    # ── Chọn kỳ dữ liệu xuất ──
    mang = st.radio(
        "Loại xuất",
        ["📊 Tổng hợp", "Chi tiết"],
        horizontal=True,
        key=f"{key_prefix}_hstd_mang",
    )

    col_k, col_x = st.columns([0.45, 0.55])
    with col_k:
        ky_xuat = st.selectbox(
            "Kỳ dữ liệu xuất",
            [label_ht, label_bl],
            key=f"{key_prefix}_hstd_ky_xuat",
        )
    df_xuat = df_ht if ky_xuat == label_ht else df_bl

    if df_xuat is None or df_xuat.empty:
        st.warning("⚠️ Không có dữ liệu HSTD cho kỳ đã chọn.")
        return

    col_chung = _build_col_chung(df_xuat)
    if not col_chung:
        st.warning("⚠️ Không có cột dữ liệu phù hợp để xuất.")
        return

    if COT_TONG_DU_NO in df_xuat.columns:
        df_xuat = df_xuat[df_xuat[COT_TONG_DU_NO] > 0].copy()

    tien_de_pdf = f"So sánh mốc năm — {ky_xuat}"

    if mang == "📊 Tổng hợp":
        _render_export_tong_hop(
            df_xuat, col_chung, rows_data, label_ht, label_bl,
            ky_xuat, tien_de_pdf, username, sheets_extra, action, key_prefix,
        )
    else:
        _render_export_chi_tiet(
            df_xuat, col_chung, rows_data, label_ht, label_bl,
            ky_xuat, tien_de_pdf, username, sheets_extra, action, key_prefix,
        )


def _render_export_tong_hop(
    df_xuat: pd.DataFrame,
    col_chung: list[str],
    rows_data: list[tuple],
    label_ht: str,
    label_bl: str,
    ky_xuat: str,
    tieu_de_pdf: str,
    username: str,
    sheets_extra: dict[str, pd.DataFrame] | None,
    action: str,
    key_prefix: str,
) -> None:
    col_xl, col_pdf1, col_pdf2 = st.columns(3)

    # ── Excel ──
    with col_xl:
        xl_key = f"_{key_prefix}_hstd_xl_{ky_xuat}"
        if xl_key not in st.session_state:
            if sheets_extra:
                st.session_state[xl_key] = xuat_excel_da_chieu(
                    rows_data, label_ht, label_bl, sheets_extra,
                )
            else:
                st.session_state[xl_key] = xuat_excel_tong_quan(
                    rows_data, label_ht, label_bl,
                )

        st.download_button(
            "📥 Xuất Excel",
            data=st.session_state[xl_key],
            file_name=f"so_sanh_moc_nam_{ky_xuat.replace('/', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_hstd_dl_excel",
            use_container_width=True,
        )

    # ── PDF Pivot (Loại 1) ──
    with col_pdf1:
        pdf1_key = f"_{key_prefix}_hstd_pdf1_{ky_xuat}"
        if pdf1_key not in st.session_state:
            if _PDF_SERVICE_READY:
                try:
                    st.session_state[pdf1_key] = xuat_pdf_pivot(
                        df_xuat, COT_TEN_PGD,
                        tieu_de_pdf, username,
                        prefix_file="SSK_PIVOT",
                    )
                except Exception:
                    st.session_state[pdf1_key] = b""
            else:
                st.session_state[pdf1_key] = b""

        _download_pdf_btn(
            pdf1_key, st.session_state[pdf1_key],
            f"SSK_Pivot_{ky_xuat.replace('/', '_')}.pdf",
            "📄 PDF Pivot (Loại 1)",
            f"{key_prefix}_hstd_dl_pdf1",
            username, action, f"PDF Pivot: {ky_xuat}",
        )

    # ── PDF theo Nhóm (Loại 3) ──
    with col_pdf2:
        pdf3_key = f"_{key_prefix}_hstd_pdf3_{ky_xuat}"
        if pdf3_key not in st.session_state:
            if _PDF_SERVICE_READY and COT_TEN_PGD in df_xuat.columns:
                try:
                    st.session_state[pdf3_key] = xuat_pdf_theo_nhom(
                        df_xuat, COT_TEN_PGD, col_chung,
                        tieu_de_pdf, username,
                        prefix_file="SSK_NHOM",
                    )
                except Exception:
                    st.session_state[pdf3_key] = b""
            else:
                st.session_state[pdf3_key] = b""

        _download_pdf_btn(
            pdf3_key, st.session_state[pdf3_key],
            f"SSK_Nhom_{ky_xuat.replace('/', '_')}.pdf",
            "📄 PDF theo Nhóm (Loại 3)",
            f"{key_prefix}_hstd_dl_pdf3",
            username, action, f"PDF Nhóm: {ky_xuat}",
        )

    st.caption(f"File: SSK_Pivot_{ky_xuat.replace('/', '_')}.pdf · SSK_Nhom_{ky_xuat.replace('/', '_')}.pdf")


def _render_export_chi_tiet(
    df_xuat: pd.DataFrame,
    col_chung: list[str],
    rows_data: list[tuple],
    label_ht: str,
    label_bl: str,
    ky_xuat: str,
    tieu_de_pdf: str,
    username: str,
    sheets_extra: dict[str, pd.DataFrame] | None,
    action: str,
    key_prefix: str,
) -> None:
    col_xl, col_pdf2, col_pdf3 = st.columns(3)

    # ── Excel ──
    with col_xl:
        xl_key = f"_{key_prefix}_hstd_xl_ct_{ky_xuat}"
        if xl_key not in st.session_state:
            df_xl = df_xuat[col_chung].copy()
            sheets = {"Chi tiết": df_xl}
            tong_hop_sheets = _build_tong_hop_sheets(df_xuat)
            sheets.update(tong_hop_sheets)
            st.session_state[xl_key] = xuat_excel(sheets)

        st.download_button(
            "📥 Xuất Excel",
            data=st.session_state[xl_key],
            file_name=f"so_sanh_ct_moc_nam_{ky_xuat.replace('/', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_hstd_dl_excel_ct",
            use_container_width=True,
        )

    # ── PDF Chi tiết (Loại 2) ──
    with col_pdf2:
        pdf2_key = f"_{key_prefix}_hstd_pdf2_{ky_xuat}"
        if pdf2_key not in st.session_state:
            if _PDF_SERVICE_READY:
                try:
                    st.session_state[pdf2_key] = xuat_pdf_chi_tiet(
                        df_xuat, col_chung,
                        tieu_de_pdf, username,
                        prefix_file="SSK_CT",
                    )
                except Exception:
                    st.session_state[pdf2_key] = b""
            else:
                st.session_state[pdf2_key] = b""

        _download_pdf_btn(
            pdf2_key, st.session_state[pdf2_key],
            f"SSK_ChiTiet_{ky_xuat.replace('/', '_')}.pdf",
            "📄 PDF Chi tiết (Loại 2)",
            f"{key_prefix}_hstd_dl_pdf2",
            username, action, f"PDF Chi tiết: {ky_xuat}",
        )

    # ── PDF theo Nhóm (Loại 3) ──
    with col_pdf3:
        pdf3_key = f"_{key_prefix}_hstd_pdf3_ct_{ky_xuat}"
        if pdf3_key not in st.session_state:
            if _PDF_SERVICE_READY and COT_TEN_PGD in df_xuat.columns:
                try:
                    st.session_state[pdf3_key] = xuat_pdf_theo_nhom(
                        df_xuat, COT_TEN_PGD, col_chung,
                        tieu_de_pdf, username,
                        prefix_file="SSK_CT_NHOM",
                    )
                except Exception:
                    st.session_state[pdf3_key] = b""
            else:
                st.session_state[pdf3_key] = b""

        _download_pdf_btn(
            pdf3_key, st.session_state[pdf3_key],
            f"SSK_CT_Nhom_{ky_xuat.replace('/', '_')}.pdf",
            "📄 PDF theo Nhóm (Loại 3)",
            f"{key_prefix}_hstd_dl_pdf3_ct",
            username, action, f"PDF Nhóm (CT): {ky_xuat}",
        )

    st.caption(f"File: SSK_ChiTiet_{ky_xuat.replace('/', '_')}.pdf · SSK_CT_Nhom_{ky_xuat.replace('/', '_')}.pdf")


def _build_tong_hop_sheets(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sheets = {}
    if COT_TEN_PGD in df.columns:
        agg_pgd = df.groupby(COT_TEN_PGD).agg(
            **{
                "Số KH": (COT_MA_KH, "nunique") if COT_MA_KH in df.columns else (COT_SO_KU, "nunique"),
                "Số món": (COT_SO_KU, "nunique"),
                "Tổng dư nợ": (COT_TONG_DU_NO, "sum"),
                "Dư nợ TH": (COT_DU_NO_TH, "sum") if COT_DU_NO_TH in df.columns else (COT_TONG_DU_NO, "sum"),
                "Dư nợ QH": (COT_DU_NO_QH, "sum") if COT_DU_NO_QH in df.columns else (COT_TONG_DU_NO, "sum"),
            }
        ).reset_index()
        sheets["Tổng hợp PGD"] = agg_pgd

    if COT_TEN_XA in df.columns:
        agg_xa = df.groupby(COT_TEN_XA).agg(
            **{
                "Số KH": (COT_MA_KH, "nunique") if COT_MA_KH in df.columns else (COT_SO_KU, "nunique"),
                "Số món": (COT_SO_KU, "nunique"),
                "Tổng dư nợ": (COT_TONG_DU_NO, "sum"),
            }
        ).reset_index()
        sheets["Tổng hợp Xã"] = agg_xa

    if COT_TEN_CT in df.columns:
        agg_ct = df.groupby(COT_TEN_CT).agg(
            **{
                "Số KH": (COT_MA_KH, "nunique") if COT_MA_KH in df.columns else (COT_SO_KU, "nunique"),
                "Số món": (COT_SO_KU, "nunique"),
                "Tổng dư nợ": (COT_TONG_DU_NO, "sum"),
            }
        ).reset_index()
        sheets["Tổng hợp CT"] = agg_ct

    return sheets


def _download_pdf_btn(
    cache_key: str,
    pdf_bytes: bytes,
    filename: str,
    label: str,
    widget_key: str,
    username: str,
    action: str,
    audit_detail: str,
) -> None:
    if not pdf_bytes:
        st.warning("⚠️ Không thể tạo PDF. Kiểm tra cài đặt reportlab.")
    else:
        if st.download_button(
            label,
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            key=widget_key,
            use_container_width=True,
        ):
            db.ghi_audit(username, action, audit_detail)
