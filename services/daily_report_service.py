"""Báo cáo định kỳ — tự tạo Excel tóm tắt mỗi sáng, lưu vào cache/reports/."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

import db
from config import BASE_DIR, CACHE_HSTD
from logger import get_logger
from services.report_service import xuat_bao_cao

logger = get_logger(__name__)

# ── Thư mục lưu báo cáo (tuyệt đối, không phụ thuộc CWD) ───────────────────
REPORTS_DIR: Path = BASE_DIR / "cache" / "reports"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def ten_file_ngay(d: Optional[date] = None) -> str:
    """Tên file báo cáo theo ngày: bao_cao_sang_DDMMYYYY.xlsx."""
    d = d or date.today()
    return f"bao_cao_sang_{d.strftime('%d%m%Y')}.xlsx"


# ── API công khai ─────────────────────────────────────────────────────────────

def lay_bao_cao_sang_hom_nay() -> Optional[Path]:
    """Trả về Path nếu báo cáo hôm nay đã có, ngược lại trả None."""
    path = REPORTS_DIR / ten_file_ngay()
    return path if path.exists() else None


def lay_ds_bao_cao(n_ngay: int = 7) -> list[dict]:
    """Danh sách báo cáo trong N ngày gần nhất, mới nhất trước.

    Mỗi item: {ngay, path, ten_file, size_kb, hom_nay}
    """
    _ensure_dir()
    result = []
    today = date.today()
    for i in range(n_ngay):
        d = today - timedelta(days=i)
        path = REPORTS_DIR / ten_file_ngay(d)
        if path.exists():
            result.append({
                "ngay":     d,
                "path":     path,
                "ten_file": path.name,
                "size_kb":  path.stat().st_size // 1024,
                "hom_nay":  i == 0,
            })
    return result


def tao_bao_cao_sang(nguoi_tao: str = "system") -> Path:
    """Tạo Excel tổng hợp sáng và lưu vào cache/reports/.

    Returns:
        Path file vừa tạo (tuyệt đối).

    Raises:
        FileNotFoundError: Chưa có cache HSTD.
        ValueError:        Không build được sheet nào.
    """
    _ensure_dir()
    now = datetime.now()
    out_path = REPORTS_DIR / ten_file_ngay()

    sheets = _build_sheets(now)

    excel_bytes = xuat_bao_cao(
        sheets,
        tieu_de=f"BÁO CÁO TỔNG HỢP SÁNG {now.strftime('%d/%m/%Y')}",
        nguoi_xuat=nguoi_tao,
    )
    out_path.write_bytes(excel_bytes)

    db.ghi_audit(nguoi_tao, "tao_bao_cao_sang", f"Lưu {out_path.name} ({len(excel_bytes)//1024} KB)")
    logger.info("tao_bao_cao_sang: ✅ %s (%d KB)", out_path.name, len(excel_bytes) // 1024)
    return out_path


# ── Build sheets ─────────────────────────────────────────────────────────────

def _build_sheets(now: datetime) -> dict[str, pd.DataFrame]:
    """Build 4 DataFrame sheets từ cache HSTD.

    Sheets:
        1. Tổng quan       — KPI 1 dòng (dư nợ, NQH, khoanh, số KH, số món)
        2. Dư nợ theo PGD  — Toàn bộ chỉ số theo 22 PGD
        3. NQH theo PGD    — Số món + tổng NQH theo PGD
        4. Đến hạn tháng này — Tổng hợp đến hạn theo PGD trong tháng hiện tại
    """
    if not Path(CACHE_HSTD).exists():
        raise FileNotFoundError(f"Chưa có cache HSTD: {CACHE_HSTD}")

    from data.core import dem_no_qua_han_pgd, tong_hop_tq_kpi, tong_hop_tq_pgd_full

    sheets: dict[str, pd.DataFrame] = {}

    # Sheet 1: KPI tổng quan
    try:
        df = tong_hop_tq_kpi(CACHE_HSTD)
        if df is not None and not df.empty:
            sheets["Tổng quan"] = df
    except Exception as e:
        logger.warning("_build_sheets Tổng quan: %s", e)

    # Sheet 2: Dư nợ theo PGD (tất cả chỉ số)
    try:
        df = tong_hop_tq_pgd_full(CACHE_HSTD, now.year)
        if df is not None and not df.empty:
            sheets["Dư nợ theo PGD"] = df
    except Exception as e:
        logger.warning("_build_sheets Dư nợ PGD: %s", e)

    # Sheet 3: NQH theo PGD
    try:
        df = dem_no_qua_han_pgd(CACHE_HSTD)
        if df is not None and not df.empty:
            sheets["NQH theo PGD"] = df
    except Exception as e:
        logger.warning("_build_sheets NQH PGD: %s", e)

    # Sheet 4: Đến hạn tháng này
    try:
        df = _lay_den_han_thang_nay(now)
        if df is not None and not df.empty:
            sheets["Đến hạn tháng này"] = df
    except Exception as e:
        logger.warning("_build_sheets Đến hạn: %s", e)

    if not sheets:
        raise ValueError("Không build được sheet nào — parquet có thể chưa có dữ liệu")

    return sheets


def _lay_den_han_thang_nay(now: datetime) -> Optional[pd.DataFrame]:
    """Tổng hợp khoản đến hạn trong tháng hiện tại, group theo PGD."""
    from config import COT_NGAY_DH, COT_TEN_PGD, COT_MA_KH, COT_TONG_DU_NO

    needed = [c for c in [COT_TEN_PGD, COT_MA_KH, COT_NGAY_DH, COT_TONG_DU_NO] if c]

    try:
        df = pd.read_parquet(CACHE_HSTD, columns=needed)
    except Exception:
        # fallback: đọc toàn bộ rồi lọc cột
        df = pd.read_parquet(CACHE_HSTD)
        df = df[[c for c in needed if c in df.columns]]

    # Kiểm tra cột bắt buộc
    if COT_NGAY_DH not in df.columns or COT_TEN_PGD not in df.columns:
        logger.warning("_lay_den_han_thang_nay: thiếu cột %s hoặc %s", COT_NGAY_DH, COT_TEN_PGD)
        return None

    df[COT_NGAY_DH] = pd.to_datetime(df[COT_NGAY_DH], errors="coerce", format="mixed", dayfirst=True)
    mask = (
        (df[COT_NGAY_DH].dt.year == now.year)
        & (df[COT_NGAY_DH].dt.month == now.month)
    )
    df_m = df[mask].copy()
    if df_m.empty:
        return None

    agg_dict: dict = {}
    if COT_MA_KH in df_m.columns:
        agg_dict["Số món đến hạn"] = (COT_MA_KH, "count")
    if COT_TONG_DU_NO in df_m.columns:
        agg_dict["Tổng dư nợ (VNĐ)"] = (COT_TONG_DU_NO, "sum")

    if not agg_dict:
        return None

    result = (
        df_m.groupby(COT_TEN_PGD)
        .agg(**agg_dict)
        .reset_index()
        .rename(columns={COT_TEN_PGD: "Tên PGD"})
        .sort_values("Tổng dư nợ (VNĐ)" if "Tổng dư nợ (VNĐ)" in agg_dict else "Số món đến hạn",
                     ascending=False)
    )
    return result
