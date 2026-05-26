"""So sánh đến hạn cùng kỳ — ROADMAP §2.3

Phát hiện PGD có số khoản đến hạn tăng đột biến so với cùng kỳ năm trước.
"""
from __future__ import annotations

from datetime import datetime, date
import os

import pandas as pd
import pyarrow.parquet as pq

from data.core import _duckdb_query
from logger import get_logger

logger = get_logger(__name__)
from config import (
    CACHE_HSTD,
    COT_TEN_PGD, COT_SO_KU, COT_MA_KH, COT_TONG_DU_NO,
    COT_NGAY_DH, COT_TEN_CT,
)
from data.hstd import doc_baseline_merged


def so_sanh_den_han_cung_ky(
    parquet_path: str | None = None,
    nam_hien_tai: int | None = None,
    months_ahead: int = 3,
) -> pd.DataFrame | None:
    """
    So sánh khoản vay đến hạn giữa năm hiện tại và năm trước.

    Args:
        parquet_path: đường dẫn parquet HSTD hiện tại
        nam_hien_tai: năm hiện tại (mặc định: năm nay)
        months_ahead: số tháng nhìn tới (mặc định 3 tháng)

    Returns:
        DataFrame: [PGD, Số món năm nay, Dư nợ năm nay,
                     Số món năm trước, Dư nợ năm trước, Tăng/Giảm món, Tăng/Giảm dư nợ]
        hoặc None nếu không đủ dữ liệu
    """
    now = datetime.now()
    nam_ht = nam_hien_tai or now.year
    nam_truoc = nam_ht - 1
    parquet_path = parquet_path or str(CACHE_HSTD)

    if not os.path.exists(parquet_path):
        return None

    cutoff_ht = date(nam_ht, now.month, 1)
    for _ in range(months_ahead):
        if cutoff_ht.month == 12:
            cutoff_ht = date(cutoff_ht.year + 1, 1, 1)
        else:
            cutoff_ht = date(cutoff_ht.year, cutoff_ht.month + 1, 1)

    # Đọc schema nhẹ (không load data) — pq.read_schema() chỉ đọc metadata
    try:
        schema_fields = [f.name for f in pq.read_schema(parquet_path)]
    except Exception as e:
        logger.error("so_sanh_den_han_cung_ky: đọc schema parquet lỗi — %s", e, exc_info=True)
        return None
    if COT_NGAY_DH not in schema_fields:
        return None

    sql_ht = f"""
        SELECT
            "{COT_TEN_PGD}"          AS "PGD",
            COUNT("{COT_SO_KU}")     AS "Số món {nam_ht}",
            SUM("{COT_TONG_DU_NO}")  AS "Dư nợ {nam_ht}"
        FROM read_parquet(?)
        WHERE "{COT_NGAY_DH}" IS NOT NULL
          AND "{COT_TONG_DU_NO}" > 0
          AND TRY_CAST("{COT_NGAY_DH}" AS DATE) >= CURRENT_DATE
          AND TRY_CAST("{COT_NGAY_DH}" AS DATE) < '{cutoff_ht.isoformat()}'
        GROUP BY "{COT_TEN_PGD}"
    """
    try:
        df_ht = _duckdb_query(sql_ht, [str(parquet_path)])
    except Exception as e:
        logger.error("so_sanh_den_han_cung_ky: DuckDB query lỗi — %s", e, exc_info=True)
        return None

    df_bl = doc_baseline_merged(nam_truoc)
    if df_bl is None or df_bl.empty:
        return None

    if COT_NGAY_DH not in df_bl.columns:
        return None

    df_bl[COT_TONG_DU_NO] = pd.to_numeric(df_bl[COT_TONG_DU_NO], errors="coerce").fillna(0)
    df_bl["_ngay_dh"] = pd.to_datetime(df_bl[COT_NGAY_DH], errors="coerce", dayfirst=True)
    cutoff_bl = date(nam_truoc, now.month, 1)
    for _ in range(months_ahead):
        if cutoff_bl.month == 12:
            cutoff_bl = date(cutoff_bl.year + 1, 1, 1)
        else:
            cutoff_bl = date(cutoff_bl.year, cutoff_bl.month + 1, 1)

    mask = (
        df_bl["_ngay_dh"].notna()
        & (df_bl["_ngay_dh"] >= pd.Timestamp(nam_truoc, now.month, 1))
        & (df_bl["_ngay_dh"] < pd.Timestamp(cutoff_bl))
        & (df_bl[COT_TONG_DU_NO] > 0)
    )
    df_bl_loc = df_bl[mask]

    if df_bl_loc.empty:
        return None

    bl_grouped = df_bl_loc.groupby(COT_TEN_PGD).agg(
        so_mon_bl=(COT_SO_KU, "count"),
        du_no_bl=(COT_TONG_DU_NO, "sum"),
    ).reset_index()
    bl_grouped.columns = ["PGD", f"Số món {nam_truoc}", f"Dư nợ {nam_truoc}"]

    result = df_ht.merge(bl_grouped, on="PGD", how="outer").fillna(0)

    mon_ht = f"Số món {nam_ht}"
    mon_bl = f"Số món {nam_truoc}"
    dn_ht = f"Dư nợ {nam_ht}"
    dn_bl = f"Dư nợ {nam_truoc}"

    result["± Món"] = result[mon_ht] - result[mon_bl]
    result["± Dư nợ"] = result[dn_ht] - result[dn_bl]
    result["± Dư nợ %"] = (
        (result["± Dư nợ"] / result[dn_bl].replace(0, pd.NA) * 100)
    ).round(1).fillna(0)

    result = result.sort_values("± Dư nợ", ascending=False)

    for c in [dn_ht, dn_bl, "± Dư nợ"]:
        result[c] = result[c].round(0).astype(int)
    for c in [mon_ht, mon_bl, "± Món"]:
        result[c] = result[c].astype(int)

    return result


def phan_tich_den_han_dot_bien(
    df_result: pd.DataFrame,
    threshold_pct: float = 30.0,
) -> list[dict]:
    """Từ kết quả so sánh, lọc ra PGD tăng đột biến."""
    alerts = []
    for _, row in df_result.iterrows():
        pct = row.get("± Dư nợ %", 0) or 0
        if abs(pct) >= threshold_pct:
            direction = "🔥 TĂNG" if pct > 0 else "❄️ GIẢM"
            alerts.append({
                "PGD": row.get("PGD", ""),
                "direction": direction,
                "pct_change": pct,
                "delta_du_no": row.get("± Dư nợ", 0),
            })
    return sorted(alerts, key=lambda x: abs(x["pct_change"]), reverse=True)
