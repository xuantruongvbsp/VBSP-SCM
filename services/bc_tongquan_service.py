"""Dịch vụ xuất báo cáo Quản lý Công việc & Nhiệm vụ."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
import io

import pandas as pd
import numpy as np

from logger import get_logger
from services import xuat_bao_cao

logger = get_logger(__name__)


def tao_bc_tongquan(
    df_tien_do: pd.DataFrame,
    df_nhiem_vu: pd.DataFrame,
    filter_nam: int,
    filter_quy: Optional[int] = None,
    filter_thang: Optional[int] = None,
    filter_trang_thai: Optional[list[str]] = None,
    filter_uu_tien: Optional[list[str]] = None,
    filter_pgd: Optional[list[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Tạo báo cáo tổng hợp Quản lý Công việc & Nhiệm vụ.

    Params
    ------
    df_tien_do    : DataFrame - Dữ liệu Tiến độ Công việc
    df_nhiem_vu   : DataFrame - Dữ liệu Nhiệm vụ định kỳ
    filter_nam    : int - Năm báo cáo
    filter_quy    : int | None - Quý (1-4)
    filter_thang  : int | None - Tháng (1-12)
    filter_trang_thai: list[str] | None - ["Đang thực hiện", "Hoàn thành", "Trễ hạn"]
    filter_uu_tien: list[str] | None - ["Khẩn cấp", "Quan trọng", "Bình thường"]
    filter_pgd    : list[str] | None - [slug1, slug2, ...]

    Returns
    -------
    Dict[str, DataFrame] - {
        "Bìa": df_bia,
        "Tổng hợp": df_tong_hop,
        "Chi tiết TV": df_chi_tiet_tv,
        "Chi tiết NV": df_chi_tiet_nv,
    }
    """
    try:
        # Xử lý dữ liệu rỗng
        df_tv = df_tien_do.copy() if df_tien_do is not None and not df_tien_do.empty else pd.DataFrame()
        df_nv = df_nhiem_vu.copy() if df_nhiem_vu is not None and not df_nhiem_vu.empty else pd.DataFrame()

        # Lọc dữ liệu
        df_tv = loc_du_lieu_tien_do(df_tv, filter_nam, filter_quy, filter_thang, filter_trang_thai, filter_pgd)
        df_nv = loc_du_lieu_nhiem_vu(df_nv, filter_nam, filter_quy, filter_thang, filter_trang_thai, filter_uu_tien, filter_pgd)

        # Tính KPI
        kpi = tinh_kpi(df_tv, df_nv)

        # Tạo ma trận
        df_ma_tran = tao_ma_tran(df_tv, df_nv)

        # Tạo sheet Bìa
        df_bia = _tao_sheet_bia(filter_nam, filter_quy, filter_thang, kpi)

        # Tạo sheet Tổng hợp (KPI + ma trận)
        df_tong_hop = _tao_sheet_tong_hop(kpi, df_ma_tran)

        # Chuẩn bị chi tiết
        df_chi_tiet_tv = _chuan_bi_chi_tiet_tv(df_tv)
        df_chi_tiet_nv = _chuan_bi_chi_tiet_nv(df_nv)

        return {
            "Bìa": df_bia,
            "Tổng hợp": df_tong_hop,
            "Chi tiết TV": df_chi_tiet_tv,
            "Chi tiết NV": df_chi_tiet_nv,
        }

    except Exception as e:
        logger.error("tao_bc_tongquan: %s", e, exc_info=True)
        return {
            "Bìa": pd.DataFrame(),
            "Tổng hợp": pd.DataFrame(),
            "Chi tiết TV": pd.DataFrame(),
            "Chi tiết NV": pd.DataFrame(),
        }


def loc_du_lieu_tien_do(
    df: pd.DataFrame,
    filter_nam: int,
    filter_quy: Optional[int] = None,
    filter_thang: Optional[int] = None,
    filter_trang_thai: Optional[list[str]] = None,
    filter_pgd: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Lọc dữ liệu Tiến độ Công việc."""
    if df.empty:
        return df

    result = df.copy()

    # Lọc năm
    if "năm" in result.columns:
        result = result[pd.to_numeric(result["năm"], errors="coerce") == filter_nam]

    # Lọc quý
    if filter_quy and "quý" in result.columns:
        result = result[pd.to_numeric(result["quý"], errors="coerce") == filter_quy]

    # Lọc tháng
    if filter_thang and "tháng" in result.columns:
        result = result[pd.to_numeric(result["tháng"], errors="coerce") == filter_thang]

    # Lọc trạng thái
    if filter_trang_thai and "trạng_thái" in result.columns:
        result = result[result["trạng_thái"].isin(filter_trang_thai)]

    # Lọc PGD
    if filter_pgd and "pgd_slug" in result.columns:
        result = result[result["pgd_slug"].isin(filter_pgd)]

    return result


def loc_du_lieu_nhiem_vu(
    df: pd.DataFrame,
    filter_nam: int,
    filter_quy: Optional[int] = None,
    filter_thang: Optional[int] = None,
    filter_trang_thai: Optional[list[str]] = None,
    filter_uu_tien: Optional[list[str]] = None,
    filter_pgd: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Lọc dữ liệu Nhiệm vụ định kỳ."""
    if df.empty:
        return df

    result = df.copy()

    # Lọc năm
    if "năm" in result.columns:
        result = result[pd.to_numeric(result["năm"], errors="coerce") == filter_nam]

    # Lọc quý
    if filter_quy and "quý" in result.columns:
        result = result[pd.to_numeric(result["quý"], errors="coerce") == filter_quy]

    # Lọc tháng
    if filter_thang and "tháng" in result.columns:
        result = result[pd.to_numeric(result["tháng"], errors="coerce") == filter_thang]

    # Lọc trạng thái
    if filter_trang_thai and "trạng_thái" in result.columns:
        result = result[result["trạng_thái"].isin(filter_trang_thai)]

    # Lọc ưu tiên
    if filter_uu_tien and "ưu_tiên" in result.columns:
        result = result[result["ưu_tiên"].isin(filter_uu_tien)]

    # Lọc PGD
    if filter_pgd and "pgd_slug" in result.columns:
        result = result[result["pgd_slug"].isin(filter_pgd)]

    return result


def tinh_kpi(df_tv: pd.DataFrame, df_nv: pd.DataFrame) -> dict:
    """
    Tính 4 KPI chính:
    - Tổng công việc & nhiệm vụ
    - % Hoàn thành
    - % Trễ hạn
    - Chờ duyệt (Nhiệm vụ)

    Returns
    -------
    dict - {
        "tong_cv": int,
        "tong_nv": int,
        "pct_ht": float (0-100),
        "pct_tre": float (0-100),
        "so_cho_duyet": int,
    }
    """
    try:
        kpi = {
            "tong_cv": len(df_tv) if not df_tv.empty else 0,
            "tong_nv": len(df_nv) if not df_nv.empty else 0,
            "pct_ht": 0.0,
            "pct_tre": 0.0,
            "so_cho_duyet": 0,
        }

        # % Hoàn thành công việc
        if not df_tv.empty and "trạng_thái" in df_tv.columns:
            so_ht = len(df_tv[df_tv["trạng_thái"] == "Hoàn thành"])
            kpi["pct_ht"] = (so_ht / len(df_tv) * 100) if len(df_tv) > 0 else 0.0

        # % Trễ hạn công việc
        if not df_tv.empty and "trạng_thái" in df_tv.columns:
            so_tre = len(df_tv[df_tv["trạng_thái"] == "Trễ hạn"])
            kpi["pct_tre"] = (so_tre / len(df_tv) * 100) if len(df_tv) > 0 else 0.0

        # Chờ duyệt (Nhiệm vụ)
        if not df_nv.empty and "trạng_thái" in df_nv.columns:
            kpi["so_cho_duyet"] = len(df_nv[df_nv["trạng_thái"] == "Chờ duyệt"])

        return kpi

    except Exception as e:
        logger.error("tinh_kpi: %s", e, exc_info=True)
        return {
            "tong_cv": 0,
            "tong_nv": 0,
            "pct_ht": 0.0,
            "pct_tre": 0.0,
            "so_cho_duyet": 0,
        }


def tao_ma_tran(df_tv: pd.DataFrame, df_nv: pd.DataFrame) -> pd.DataFrame:
    """
    Tạo ma trận PGD × Công việc/Nhiệm vụ (trạng thái tóm tắt).

    Returns
    -------
    DataFrame - Ma trận với cột PGD, Tổng CV, Hoàn thành, Trễ hạn, Tổng NV, Chờ duyệt
    """
    try:
        pgds = set()

        if not df_tv.empty and "pgd" in df_tv.columns:
            pgds.update(df_tv["pgd"].dropna().unique())

        if not df_nv.empty and "pgd" in df_nv.columns:
            pgds.update(df_nv["pgd"].dropna().unique())

        if not pgds:
            return pd.DataFrame()

        ma_tran = []

        for pgd in sorted(pgds):
            row = {"PGD": pgd}

            # Tính chỉ số công việc
            df_tv_pgd = df_tv[df_tv["pgd"] == pgd] if not df_tv.empty else pd.DataFrame()
            row["Tổng CV"] = len(df_tv_pgd)
            row["CV Hoàn thành"] = len(df_tv_pgd[df_tv_pgd["trạng_thái"] == "Hoàn thành"]) if "trạng_thái" in df_tv_pgd.columns else 0
            row["CV Trễ hạn"] = len(df_tv_pgd[df_tv_pgd["trạng_thái"] == "Trễ hạn"]) if "trạng_thái" in df_tv_pgd.columns else 0

            # Tính chỉ số nhiệm vụ
            df_nv_pgd = df_nv[df_nv["pgd"] == pgd] if not df_nv.empty else pd.DataFrame()
            row["Tổng NV"] = len(df_nv_pgd)
            row["NV Chờ duyệt"] = len(df_nv_pgd[df_nv_pgd["trạng_thái"] == "Chờ duyệt"]) if "trạng_thái" in df_nv_pgd.columns else 0

            ma_tran.append(row)

        return pd.DataFrame(ma_tran)

    except Exception as e:
        logger.error("tao_ma_tran: %s", e, exc_info=True)
        return pd.DataFrame()


def _tao_sheet_bia(filter_nam: int, filter_quy: Optional[int], filter_thang: Optional[int], kpi: dict) -> pd.DataFrame:
    """Tạo dữ liệu sheet Bìa (thực chất là thông tin top-level cho PDF/Excel)."""
    data = {
        "Thông tin báo cáo": [
            f"Năm: {filter_nam}",
            f"Quý/Tháng: {filter_quy or filter_thang or 'Cả năm'}",
            f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y')}",
            "",
            "KPI Tóm tắt:",
            f"Tổng công việc: {kpi['tong_cv']}",
            f"% Hoàn thành: {kpi['pct_ht']:.1f}%",
            f"% Trễ hạn: {kpi['pct_tre']:.1f}%",
            f"Nhiệm vụ chờ duyệt: {kpi['so_cho_duyet']}",
        ]
    }
    return pd.DataFrame(data)


def _tao_sheet_tong_hop(kpi: dict, df_ma_tran: pd.DataFrame) -> pd.DataFrame:
    """Tạo sheet Tổng hợp (KPI + ma trận)."""
    try:
        # Thêm dòng KPI tóm tắt vào đầu ma trận
        rows = []
        rows.append({
            "PGD": "=== TỔNG ===",
            "Tổng CV": kpi["tong_cv"],
            "CV Hoàn thành": f"{kpi['pct_ht']:.1f}%",
            "CV Trễ hạn": f"{kpi['pct_tre']:.1f}%",
            "Tổng NV": kpi["tong_nv"],
            "NV Chờ duyệt": kpi["so_cho_duyet"],
        })

        if not df_ma_tran.empty:
            rows.extend(df_ma_tran.to_dict(orient="records"))

        return pd.DataFrame(rows)

    except Exception as e:
        logger.error("_tao_sheet_tong_hop: %s", e, exc_info=True)
        return pd.DataFrame()


def _chuan_bi_chi_tiet_tv(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn bị dữ liệu chi tiết Công việc để xuất."""
    if df.empty:
        return df

    # Giữ lại các cột quan trọng: tiêu đề, PGD, trạng thái, ngày deadline, % hoàn thành
    cols_keep = [c for c in ["tiêu_đề", "pgd", "trạng_thái", "ngày_deadline", "phan_tram_hoan_thanh", "ghi_chu"] if c in df.columns]

    if not cols_keep:
        cols_keep = df.columns.tolist()[:8]  # Fallback: 8 cột đầu

    return df[cols_keep].reset_index(drop=True)


def _chuan_bi_chi_tiet_nv(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn bị dữ liệu chi tiết Nhiệm vụ để xuất."""
    if df.empty:
        return df

    # Giữ lại các cột quan trọng: tiêu đề, PGD, ưu tiên, trạng thái, deadline
    cols_keep = [c for c in ["tiêu_đề", "pgd", "ưu_tiên", "trạng_thái", "ngày_deadline", "ghi_chu"] if c in df.columns]

    if not cols_keep:
        cols_keep = df.columns.tolist()[:8]  # Fallback: 8 cột đầu

    return df[cols_keep].reset_index(drop=True)


def xuat_excel_bc(sheets: Dict[str, pd.DataFrame], prefix: str, nguoi_xuat: str) -> bytes:
    """
    Xuất báo cáo dưới dạng Excel.

    Params
    ------
    sheets      : Dict[str, DataFrame] - {sheet_name: dataframe}
    prefix      : str - Tiền tố tên file
    nguoi_xuat  : str - Người xuất báo cáo

    Returns
    -------
    bytes - Nội dung file Excel
    """
    try:
        tieu_de = f"Báo cáo Quản lý Công việc & Nhiệm vụ — {prefix}"
        return xuat_bao_cao(sheets, tieu_de, nguoi_xuat)

    except Exception as e:
        logger.error("xuat_excel_bc: %s", e, exc_info=True)
        return b""


def xuat_pdf_bc(sheets: Dict[str, pd.DataFrame], tieu_de: str, nguoi_xuat: str) -> bytes:
    """
    Xuất báo cáo dưới dạng PDF.

    Params
    ------
    sheets      : Dict[str, DataFrame]
    tieu_de     : str - Tiêu đề báo cáo
    nguoi_xuat  : str - Người xuất báo cáo

    Returns
    -------
    bytes - Nội dung file PDF
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak
        )
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import os

        buf = io.BytesIO()

        # Cố gắng dùng font TimesVN
        font_dir = "C:/Windows/Fonts"
        try:
            pdfmetrics.registerFont(TTFont("TimesVN", os.path.join(font_dir, "times.ttf")))
            pdfmetrics.registerFont(TTFont("TimesVN-Bold", os.path.join(font_dir, "timesbd.ttf")))
            base_font = "TimesVN"
            base_font_bold = "TimesVN-Bold"
        except Exception:  # conv: skip
            base_font = "Helvetica"
            base_font_bold = "Helvetica-Bold"

        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=2.5*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        # Styles
        s_co_quan = ParagraphStyle("co_quan", fontName=base_font, fontSize=10, leading=14, alignment=1)
        s_tieu_de = ParagraphStyle("tieu_de", fontName=base_font_bold, fontSize=13, leading=18, alignment=1, spaceBefore=10, spaceAfter=4)
        s_phu_de = ParagraphStyle("phu_de", fontName=base_font, fontSize=10, leading=14, alignment=1, spaceAfter=10, textColor=colors.HexColor("#444444"))
        s_normal = ParagraphStyle("normal", fontName=base_font, fontSize=9, leading=12)
        s_footer = ParagraphStyle("footer", fontName=base_font, fontSize=8, leading=11, textColor=colors.grey)

        story = []
        story.append(Paragraph("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM", s_co_quan))
        story.append(Paragraph("Chi nhánh tỉnh Đồng Nai", s_co_quan))
        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#185FA5")))
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(tieu_de.upper(), s_tieu_de))
        story.append(Paragraph(f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M')}", s_phu_de))
        story.append(Spacer(1, 0.4*cm))

        # Thêm bảng Tổng hợp (sheet 2)
        if "Tổng hợp" in sheets and not sheets["Tổng hợp"].empty:
            df_tong_hop = sheets["Tổng hợp"]
            header = [Paragraph(f"<b>{col}</b>", s_normal) for col in df_tong_hop.columns]
            data = [header]

            for _, row in df_tong_hop.iterrows():
                data.append([Paragraph(str(val), s_normal) for val in row.values])

            tbl = Table(data, colWidths=[2*cm]*len(df_tong_hop.columns), repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#185FA5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1EFE8")]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#AAAAAA")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 0.6*cm))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            "Tài liệu được tạo tự động từ Hệ thống Quản trị Tín dụng Nội bộ VBSP-SCM",
            s_footer,
        ))

        doc.build(story)
        return buf.getvalue()

    except Exception as e:
        logger.error("xuat_pdf_bc: %s", e, exc_info=True)
        return b""
