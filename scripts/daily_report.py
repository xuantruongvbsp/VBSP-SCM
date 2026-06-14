#!/usr/bin/env python3
"""
daily_report.py — Tạo báo cáo Excel tóm tắt định kỳ hằng ngày.
Chạy độc lập: python scripts/daily_report.py
Có thể gọi từ Task Scheduler hoặc chạy thủ công.
"""
from __future__ import annotations

import os
import sys
import json
from datetime import datetime, date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from data.core import _duckdb_query
from config import (
    CACHE_HSTD,
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT, COT_TEN_KH,
    COT_SO_KU, COT_MA_KH, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_TH,
    COT_DU_NO_KHOANH, COT_LAI_TON, COT_NGAY_DH, COT_NGUON_VON,
    DS_PGD, COT_TEN_TO,
)
from data.pgd import pgd_slug
from utils import fmt_ty, fmt_so

REPORT_DIR = BASE_DIR / "cache" / "reports"
HEADER_FILL = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
BOLD_FONT = Font(bold=True, size=11)
NORMAL_FONT = Font(size=10)
BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)
RED_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
AMBER_FILL = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")


def _style_header(ws, ncols: int):
    for col in range(1, ncols + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER


def _style_data(ws, nrows: int, ncols: int, tien_cols: list[int] | None = None):
    tien_cols = tien_cols or []
    for row in range(2, nrows + 1):
        for col in range(1, ncols + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = BORDER
            cell.font = NORMAL_FONT
            if col in tien_cols:
                cell.number_format = '#,##0'
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="left")
        if row == nrows:
            for col in range(1, ncols + 1):
                cell = ws.cell(row=row, column=col)
                cell.font = BOLD_FONT


def _auto_width(ws, ncols: int):
    for col in range(1, ncols + 1):
        max_len = 0
        for row in range(1, ws.max_row + 1):
            val = ws.cell(row=row, column=col).value or ""
            max_len = max(max_len, len(str(val)))
        ws.column_dimensions[get_column_letter(col)].width = min(max_len + 4, 40)


def _build_tong_quan_sheet(wb: Workbook, parquet_path: str):
    """Sheet 1: Tổng quan dư nợ theo PGD."""
    ws = wb.active
    ws.title = "Tổng quan PGD"

    if not os.path.exists(parquet_path):
        ws.cell(row=1, column=1, value="⚠️ Chưa có dữ liệu parquet").font = Font(bold=True, color="FF0000")
        return

    sql = f"""
        SELECT
            "{COT_TEN_PGD}"          AS "PGD",
            COUNT(DISTINCT "{COT_MA_KH}") AS "Số KH",
            COUNT("{COT_SO_KU}")      AS "Số món",
            SUM("{COT_TONG_DU_NO}")   AS "Dư nợ",
            SUM("{COT_DU_NO_QH}")     AS "Nợ QH",
            SUM("{COT_DU_NO_TH}")     AS "Nợ TH"
        FROM read_parquet(?)
        WHERE "{COT_TONG_DU_NO}" IS NOT NULL
        GROUP BY "{COT_TEN_PGD}"
        ORDER BY "Dư nợ" DESC
    """
    try:
        df = _duckdb_query(sql, [parquet_path])
    except Exception:
        ws.cell(row=1, column=1, value="⚠️ Lỗi truy vấn dữ liệu").font = Font(bold=True, color="FF0000")
        return

    total = pd.DataFrame([{
        "PGD": "TOÀN CHI NHÁNH",
        "Số KH": df["Số KH"].sum(),
        "Số món": df["Số món"].sum(),
        "Dư nợ": df["Dư nợ"].sum(),
        "Nợ QH": df["Nợ QH"].sum(),
        "Nợ TH": df["Nợ TH"].sum(),
    }])
    df["Tỷ lệ NQH"] = (df["Nợ QH"] / df["Dư nợ"].replace(0, pd.NA) * 100).round(2)
    total["Tỷ lệ NQH"] = round(total["Nợ QH"].iloc[0] / total["Dư nợ"].iloc[0] * 100, 2) if total["Dư nợ"].iloc[0] > 0 else 0
    df_out = pd.concat([df, total], ignore_index=True)

    for c in ["Dư nợ", "Nợ QH", "Nợ TH"]:
        df_out[c] = df_out[c].astype(int)

    cols = list(df_out.columns)
    for i, col in enumerate(cols, 1):
        ws.cell(row=1, column=i, value=col)

    for r, (_, row) in enumerate(df_out.iterrows(), 2):
        for c, col in enumerate(cols, 1):
            ws.cell(row=r, column=c, value=row[col])

    ncols = len(cols)
    _style_header(ws, ncols)
    tien_cols = [i + 1 for i, c in enumerate(cols) if c in ("Dư nợ", "Nợ QH", "Nợ TH")]
    _style_data(ws, len(df_out) + 1, ncols, tien_cols)

    for r in range(2, len(df_out) + 2):
        tl = ws.cell(row=r, column=ncols).value
        if isinstance(tl, (int, float)):
            if tl > 2:
                ws.cell(row=r, column=ncols).fill = RED_FILL
            elif tl > 1:
                ws.cell(row=r, column=ncols).fill = AMBER_FILL

    _auto_width(ws, ncols)


def _build_nqh_top_sheet(wb: Workbook, parquet_path: str):
    """Sheet 2: Top khoản vay NQH cao nhất."""
    ws = wb.create_sheet("Top NQH")

    if not os.path.exists(parquet_path):
        ws.cell(row=1, column=1, value="⚠️ Chưa có dữ liệu")
        return

    sql = f"""
        SELECT
            "{COT_TEN_PGD}"   AS "PGD",
            "{COT_TEN_KH}"    AS "Tên KH",
            "{COT_SO_KU}"     AS "Số KU",
            "{COT_TEN_CT}"    AS "CT",
            "{COT_TONG_DU_NO}" AS "Dư nợ",
            "{COT_DU_NO_QH}"  AS "Nợ QH",
            "{COT_LAI_TON}"   AS "Lãi tồn"
        FROM read_parquet(?)
        WHERE "{COT_DU_NO_QH}" > 0
        ORDER BY "{COT_DU_NO_QH}" DESC
        LIMIT 50
    """
    try:
        df = _duckdb_query(sql, [parquet_path])
    except Exception:
        ws.cell(row=1, column=1, value="⚠️ Lỗi truy vấn")
        return

    cols = list(df.columns)
    for i, col in enumerate(cols, 1):
        ws.cell(row=1, column=i, value=col)
    for r, (_, row) in enumerate(df.iterrows(), 2):
        for c, col in enumerate(cols, 1):
            ws.cell(row=r, column=c, value=row[col])

    ncols = len(cols)
    _style_header(ws, ncols)
    tien_cols = [i + 1 for i, c in enumerate(cols) if c in ("Dư nợ", "Nợ QH", "Lãi tồn")]
    _style_data(ws, len(df) + 1, ncols, tien_cols)
    _auto_width(ws, ncols)


def _build_den_han_sheet(wb: Workbook, parquet_path: str):
    """Sheet 3: Khoản vay đến hạn trong 30 ngày."""
    ws = wb.create_sheet("Đến hạn 30 ngày")

    if not os.path.exists(parquet_path):
        ws.cell(row=1, column=1, value="⚠️ Chưa có dữ liệu")
        return

    cutoff = (date.today() + timedelta(days=30)).isoformat()

    sql = f"""
        SELECT
            "{COT_TEN_PGD}"   AS "PGD",
            "{COT_TEN_KH}"    AS "Tên KH",
            "{COT_SO_KU}"     AS "Số KU",
            "{COT_NGAY_DH}"   AS "Ngày đến hạn",
            "{COT_TEN_CT}"    AS "CT",
            "{COT_TONG_DU_NO}" AS "Dư nợ",
            "{COT_TEN_TO}"    AS "Tổ TK&VV"
        FROM read_parquet(?)
        WHERE "{COT_NGAY_DH}" IS NOT NULL
          AND "{COT_NGAY_DH}" <= '{cutoff}'
          AND "{COT_NGAY_DH}" >= CURRENT_DATE
          AND "{COT_TONG_DU_NO}" > 0
        ORDER BY "{COT_NGAY_DH}", "{COT_TONG_DU_NO}" DESC
    """
    try:
        df = _duckdb_query(sql, [parquet_path])
    except Exception:
        ws.cell(row=1, column=1, value="⚠️ Lỗi truy vấn")
        return

    cols = list(df.columns)
    for i, col in enumerate(cols, 1):
        ws.cell(row=1, column=i, value=col)
    for r, (_, row) in enumerate(df.iterrows(), 2):
        for c, col in enumerate(cols, 1):
            ws.cell(row=r, column=c, value=row[col])

    ncols = len(cols)
    _style_header(ws, ncols)
    tien_cols = [i + 1 for i, c in enumerate(cols) if c in ("Dư nợ",)]
    _style_data(ws, len(df) + 1, ncols, tien_cols)
    _auto_width(ws, ncols)


def _build_khtd_sheet(wb: Workbook):
    """Sheet 4: KHTD tiến độ."""
    ws = wb.create_sheet("KHTD tiến độ")

    import db
    data = db.doc_kv("khtd_cn")
    if not data:
        ws.cell(row=1, column=1, value="⚠️ Chưa nhập KHTD Chi nhánh")
        return

    rows = []
    for ct, targets in sorted(data.items()):
        if not isinstance(targets, dict):
            continue
        for ten_pgd, val in targets.items():
            if isinstance(val, (int, float)):
                rows.append({"CT": ct, "PGD": ten_pgd, "KHTD (triệu đ)": round(val / 1_000_000, 1)})

    if not rows:
        ws.cell(row=1, column=1, value="⚠️ Chưa có dữ liệu KHTD")
        return

    df = pd.DataFrame(rows)
    cols = list(df.columns)
    for i, col in enumerate(cols, 1):
        ws.cell(row=1, column=i, value=col)
    for r, (_, row) in enumerate(df.iterrows(), 2):
        for c, col in enumerate(cols, 1):
            ws.cell(row=r, column=c, value=row[col])

    ncols = len(cols)
    _style_header(ws, ncols)
    tien_cols = [i + 1 for i, c in enumerate(cols) if "KHTD" in c]
    _style_data(ws, len(df) + 1, ncols, tien_cols)
    _auto_width(ws, ncols)


def _build_bia_sheet(wb: Workbook):
    """Sheet Bìa: thông tin báo cáo."""
    ws = wb.create_sheet("Bìa", 0)
    ws.merge_cells("A1:E1")
    title_cell = ws.cell(row=1, column=1, value="BÁO CÁO TÓM TẮT ĐỊNH KỲ")
    title_cell.font = Font(bold=True, size=16, color="2E7D32")
    title_cell.alignment = Alignment(horizontal="center")

    now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
    ws.merge_cells("A3:E3")
    ws.cell(row=3, column=1, value=f"Thời gian xuất: {now_str}").font = Font(size=11)
    ws.cell(row=3, column=1).alignment = Alignment(horizontal="center")

    ws.merge_cells("A5:E5")
    ws.cell(row=5, column=1, value="NHCSXH Chi nhánh Đồng Nai").font = Font(bold=True, size=12)
    ws.cell(row=5, column=1).alignment = Alignment(horizontal="center")

    ws.merge_cells("A7:E7")
    ws.cell(row=7, column=1, value="Hệ thống Quản trị Tín dụng Nội bộ — VBSP-SCM").font = Font(size=10, italic=True)
    ws.cell(row=7, column=1).alignment = Alignment(horizontal="center")

    ws.column_dimensions["A"].width = 15
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 15


def generate_daily_report() -> str | None:
    """Tạo báo cáo Excel hằng ngày. Trả về đường dẫn file hoặc None nếu lỗi."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    parquet_path = str(CACHE_HSTD)
    if not os.path.exists(parquet_path):
        print(f"❌ Không tìm thấy {CACHE_HSTD}")
        return None

    wb = Workbook()
    _build_bia_sheet(wb)
    _build_tong_quan_sheet(wb, parquet_path)
    _build_nqh_top_sheet(wb, parquet_path)
    _build_den_han_sheet(wb, parquet_path)
    _build_khtd_sheet(wb)

    now = datetime.now()
    filename = f"BaoCao_Ngay_{now.strftime('%Y%m%d_%H%M')}.xlsx"
    filepath = REPORT_DIR / filename

    wb.save(str(filepath))

    info = {
        "ts": now.isoformat(),
        "file": filename,
        "size": filepath.stat().st_size,
    }
    meta_path = REPORT_DIR / "latest.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)

    print(f"✅ Đã tạo báo cáo: {filepath} ({info['size'] / 1024:.1f} KB)")

    # Gửi tóm tắt qua Telegram
    try:
        from services.telegram_service import gui_bao_cao_sang
        from config import COT_TONG_DU_NO, COT_DU_NO_QH

        if os.path.exists(parquet_path):
            sql_sum = f"""
                SELECT
                    SUM("{COT_TONG_DU_NO}") AS tong_dn,
                    SUM("{COT_DU_NO_QH}")   AS tong_qh
                FROM read_parquet(?)
                WHERE "{COT_TONG_DU_NO}" IS NOT NULL
            """
            df_sum = _duckdb_query(sql_sum, [parquet_path])
            tong_dn = int(df_sum["tong_dn"].iloc[0] or 0)
            tong_qh = int(df_sum["tong_qh"].iloc[0] or 0)
            ty_le_qh = f"{tong_qh / tong_dn * 100:.2f}%" if tong_dn > 0 else "—"

            merge_meta = db.doc_kv("merge_meta_hstd") or {}
            so_pgd = merge_meta.get("so_pgd", 0)

            from config import DS_PGD
            gui_bao_cao_sang(
                ngay=now.strftime("%d/%m/%Y"),
                tong_du_no=f"{tong_dn / 1e9:,.1f} tỷ".replace(",", "."),
                tong_qh=f"{tong_qh / 1e6:,.0f} triệu".replace(",", "."),
                ty_le_qh=ty_le_qh,
                so_pgd_da_upload=so_pgd,
                tong_pgd=len(DS_PGD),
            )
    except Exception as e:
        print(f"⚠️ Telegram: {e}")

    return str(filepath)


def _cleanup_old(n_days: int = 30):
    """Xóa báo cáo cũ hơn N ngày."""
    if not REPORT_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=n_days)
    deleted = 0
    for f in REPORT_DIR.glob("BaoCao_Ngay_*.xlsx"):
        try:
            ts = datetime.fromtimestamp(f.stat().st_mtime)
            if ts < cutoff:
                f.unlink()
                deleted += 1
        except Exception:
            pass
    if deleted:
        print(f"🗑️ Đã xóa {deleted} báo cáo cũ (> {n_days} ngày)")


def list_reports() -> list[dict]:
    """Liệt kê tất cả báo cáo đã tạo."""
    if not REPORT_DIR.exists():
        return []
    reports = []
    for f in sorted(REPORT_DIR.glob("BaoCao_Ngay_*.xlsx"), reverse=True):
        ts = datetime.fromtimestamp(f.stat().st_mtime)
        reports.append({
            "file": f.name,
            "ts": ts.strftime("%d/%m/%Y %H:%M"),
            "size_kb": round(f.stat().st_size / 1024, 1),
            "path": str(f),
        })
    return reports


def get_latest_report() -> str | None:
    """Lấy đường dẫn báo cáo mới nhất."""
    meta_path = REPORT_DIR / "latest.json"
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                info = json.load(f)
            fp = REPORT_DIR / info["file"]
            if fp.exists():
                return str(fp)
        except Exception:
            pass
    reports = list_reports()
    return reports[0]["path"] if reports else None


if __name__ == "__main__":
    print(f"VBSP-SCM Daily Report Generator — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    result = generate_daily_report()
    _cleanup_old(30)
    if not result:
        sys.exit(1)
