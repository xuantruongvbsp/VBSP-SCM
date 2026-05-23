"""Dự phóng Doanh số Thu nợ & Kế hoạch Dòng tiền — PGD / Xã."""
from __future__ import annotations

from datetime import datetime, date

import duckdb
import pandas as pd
from dateutil.relativedelta import relativedelta

from config import (
    COT_SO_KU, COT_MA_KH, COT_TEN_KH, COT_TEN_PGD, COT_TEN_XA,
    COT_TEN_CT, COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH,
    COT_NGAY_VAY, COT_NGAY_DH, COT_MUC_VAY, COT_NGUON_VON,
)
try:
    from logger import get_logger
    logger = get_logger(__name__)
except Exception as e:
    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
    import logging
    logger = logging.getLogger(__name__)


def du_phong_dong_tien(
    df: pd.DataFrame | None = None,
    tu_thang: date | None = None,
    den_thang: date | None = None,
    *,
    parquet_path: str | None = None,
    ten_pgd: str | None = None,
) -> pd.DataFrame:
    """
    Tính dòng tiền dự kiến thu nợ gốc theo tiến độ hợp đồng cho từng tháng.

    Nguyên lý: Với mỗi khế ước còn dư nợ, lấy Tổng mức vay (Mức vay),
    phân bổ đều theo số tháng từ Ngày vay → Ngày ĐH theo Gia hạn.
    Chỉ tính các tháng nằm trong khoảng tu_thang → den_thang.

    Ưu tiên parquet_path: DuckDB đọc thẳng từ Parquet, lọc PGD, mở rộng
    tháng bằng UNNEST(RANGE()) — không load toàn bộ dữ liệu vào RAM.
    Fallback df: DuckDB query trên in-memory DataFrame.

    Returns:
        DataFrame với cột: thang, so_mon, tong_du_no, du_kien_thu_goc,
                           du_kien_thu_goc_trieu, tong_du_no_trieu, thang_label
    """
    hom_nay = datetime.now().date()
    if tu_thang is None:
        tu_thang = date(hom_nay.year, hom_nay.month, 1)
    if den_thang is None:
        den_thang = tu_thang + relativedelta(months=12)

    # ── Xây dựng nguồn dữ liệu cho DuckDB ──────────────────────────────
    if parquet_path:
        where_pgd = f'AND "{COT_TEN_PGD}" = \'{ten_pgd}\'' if ten_pgd else ""
        src_clause = f"read_parquet('{parquet_path}')"
        src_filter = f"{where_pgd}"
        date_expr_vay = (
            f"COALESCE("
            f"TRY_CAST(\"{COT_NGAY_VAY}\" AS DATE),"
            f"TRY_STRPTIME(CAST(\"{COT_NGAY_VAY}\" AS VARCHAR), '%d/%m/%Y')"
            f")"
        )
        date_expr_dh = (
            f"COALESCE("
            f"TRY_CAST(\"{COT_NGAY_DH}\" AS DATE),"
            f"TRY_STRPTIME(CAST(\"{COT_NGAY_DH}\" AS VARCHAR), '%d/%m/%Y')"
            f")"
        )
    else:
        if df is None or df.empty:
            return pd.DataFrame()
        need_cols = [COT_NGAY_VAY, COT_NGAY_DH, COT_MUC_VAY, COT_TONG_DU_NO]
        if any(c not in df.columns for c in need_cols):
            return pd.DataFrame()
        # Chuẩn hoá ngày trước — DuckDB không parse dayfirst
        df = df.copy()
        df[COT_NGAY_VAY] = pd.to_datetime(df[COT_NGAY_VAY], dayfirst=True, errors="coerce")
        df[COT_NGAY_DH]  = pd.to_datetime(df[COT_NGAY_DH],  dayfirst=True, errors="coerce")
        con = duckdb.connect()
        con.register("src_df", df)
        src_clause  = "src_df"
        src_filter  = ""
        date_expr_vay = f"TRY_CAST(\"{COT_NGAY_VAY}\" AS DATE)"
        date_expr_dh  = f"TRY_CAST(\"{COT_NGAY_DH}\"  AS DATE)"

    sql = f"""
        WITH base AS (
            SELECT
                COALESCE(CAST("{COT_SO_KU}"      AS VARCHAR), '') AS so_ku,
                TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE)            AS tong_du_no,
                {date_expr_vay}                                    AS ngay_vay,
                {date_expr_dh}                                     AS ngay_dh,
                TRY_CAST("{COT_MUC_VAY}"    AS DOUBLE)            AS muc_vay
            FROM {src_clause}
            WHERE TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE) > 0
              {src_filter}
        ),
        calc AS (
            SELECT *,
                GREATEST(1, DATEDIFF('month', ngay_vay, ngay_dh)) AS so_thang,
                muc_vay / GREATEST(1, DATEDIFF('month', ngay_vay, ngay_dh)) AS goc_ht
            FROM base
            WHERE ngay_vay IS NOT NULL AND ngay_dh IS NOT NULL
        ),
        expanded AS (
            SELECT
                DATE_TRUNC('month', ngay_vay + (i * INTERVAL '1 month'))::DATE AS thang,
                so_ku, tong_du_no, goc_ht
            FROM (SELECT *, UNNEST(RANGE(so_thang)) AS i FROM calc)
        )
        SELECT
            thang,
            COUNT(*)            AS so_mon,
            SUM(tong_du_no)     AS tong_du_no,
            SUM(goc_ht)         AS du_kien_thu_goc
        FROM expanded
        WHERE thang BETWEEN ? AND ?
        GROUP BY thang
        ORDER BY thang
    """

    try:
        if parquet_path:
            tong_hop = duckdb.execute(sql, [tu_thang, den_thang]).df()
        else:
            tong_hop = con.execute(sql, [tu_thang, den_thang]).df()
    except Exception as e:
        logger.error("du_phong_dong_tien: lỗi query — %s", e, exc_info=True)
        return pd.DataFrame()

    if tong_hop.empty:
        return pd.DataFrame()

    tong_hop["du_kien_thu_goc_trieu"] = (tong_hop["du_kien_thu_goc"] / 1e6).round(1)
    tong_hop["tong_du_no_trieu"]       = (tong_hop["tong_du_no"]      / 1e6).round(1)
    tong_hop["thang_label"]            = tong_hop["thang"].apply(lambda d: d.strftime("%m/%Y"))
    return tong_hop


def du_phong_chi_tiet(
    df: pd.DataFrame | None = None,
    thang: date | None = None,
    *,
    parquet_path: str | None = None,
    ten_pgd: str | None = None,
) -> pd.DataFrame:
    """
    Danh sách chi tiết các khế ước đến hạn thu gốc trong tháng cụ thể.

    Ưu tiên parquet_path: DuckDB đọc thẳng từ Parquet với lọc PGD.
    Fallback df: DuckDB query trên in-memory DataFrame.
    """
    if thang is None:
        return pd.DataFrame()

    thang_dau = date(thang.year, thang.month, 1)

    # ── Xây dựng nguồn dữ liệu cho DuckDB ──────────────────────────────
    if parquet_path:
        where_pgd = f'AND "{COT_TEN_PGD}" = \'{ten_pgd}\'' if ten_pgd else ""
        src_clause = f"read_parquet('{parquet_path}')"
        src_filter = where_pgd
        date_expr_vay = (
            f"COALESCE("
            f"TRY_CAST(\"{COT_NGAY_VAY}\" AS DATE),"
            f"TRY_STRPTIME(CAST(\"{COT_NGAY_VAY}\" AS VARCHAR), '%d/%m/%Y')"
            f")"
        )
        date_expr_dh = (
            f"COALESCE("
            f"TRY_CAST(\"{COT_NGAY_DH}\" AS DATE),"
            f"TRY_STRPTIME(CAST(\"{COT_NGAY_DH}\" AS VARCHAR), '%d/%m/%Y')"
            f")"
        )
    else:
        if df is None or df.empty:
            return pd.DataFrame()
        need_cols = [COT_NGAY_VAY, COT_NGAY_DH, COT_MUC_VAY, COT_TONG_DU_NO]
        if any(c not in df.columns for c in need_cols):
            return pd.DataFrame()
        df = df.copy()
        df[COT_NGAY_VAY] = pd.to_datetime(df[COT_NGAY_VAY], dayfirst=True, errors="coerce")
        df[COT_NGAY_DH]  = pd.to_datetime(df[COT_NGAY_DH],  dayfirst=True, errors="coerce")
        con = duckdb.connect()
        con.register("src_df", df)
        src_clause  = "src_df"
        src_filter  = ""
        date_expr_vay = f"TRY_CAST(\"{COT_NGAY_VAY}\" AS DATE)"
        date_expr_dh  = f"TRY_CAST(\"{COT_NGAY_DH}\"  AS DATE)"

    # Các cột tuỳ chọn — chỉ select khi có trong nguồn
    opt_cols = {
        "ma_kh":   COT_MA_KH,
        "ten_kh":  COT_TEN_KH,
        "ten_pgd": COT_TEN_PGD,
        "ten_xa":  COT_TEN_XA,
        "ten_ct":  COT_TEN_CT,
    }
    # Luôn include tất cả — nếu cột không tồn tại DuckDB trả NULL
    opt_select = "\n".join(
        f"            COALESCE(CAST(\"{col}\" AS VARCHAR), '') AS {alias},"
        for alias, col in opt_cols.items()
    )

    sql = f"""
        WITH base AS (
            SELECT
                COALESCE(CAST("{COT_SO_KU}"      AS VARCHAR), '') AS so_ku,
                {opt_select}
                TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE)            AS tong_du_no,
                {date_expr_vay}                                    AS ngay_vay,
                {date_expr_dh}                                     AS ngay_dh,
                TRY_CAST("{COT_MUC_VAY}"    AS DOUBLE)            AS muc_vay
            FROM {src_clause}
            WHERE TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE) > 0
              {src_filter}
        ),
        calc AS (
            SELECT *,
                GREATEST(1, DATEDIFF('month', ngay_vay, ngay_dh)) AS so_thang,
                muc_vay / GREATEST(1, DATEDIFF('month', ngay_vay, ngay_dh)) AS goc_ht
            FROM base
            WHERE ngay_vay IS NOT NULL AND ngay_dh IS NOT NULL
        ),
        expanded AS (
            SELECT
                DATE_TRUNC('month', ngay_vay + (i * INTERVAL '1 month'))::DATE AS thang_exp,
                so_ku, ma_kh, ten_kh, ten_pgd, ten_xa, ten_ct,
                tong_du_no, goc_ht, ngay_vay, ngay_dh
            FROM (SELECT *, UNNEST(RANGE(so_thang)) AS i FROM calc)
        )
        SELECT
            so_ku, ma_kh, ten_kh, ten_pgd, ten_xa, ten_ct,
            tong_du_no                                    AS du_no,
            goc_ht                                        AS goc_hang_thang,
            strftime(ngay_vay, '%d/%m/%Y')                AS ngay_vay,
            strftime(ngay_dh,  '%d/%m/%Y')                AS ngay_dh
        FROM expanded
        WHERE thang_exp = ?
        ORDER BY so_ku
    """

    try:
        if parquet_path:
            df_ct = duckdb.execute(sql, [thang_dau]).df()
        else:
            df_ct = con.execute(sql, [thang_dau]).df()
    except Exception as e:
        logger.error("du_phong_chi_tiet: lỗi query — %s", e, exc_info=True)
        return pd.DataFrame()

    if df_ct.empty:
        return pd.DataFrame()

    df_ct["du_no_trieu"]  = (df_ct["du_no"]          / 1e6).round(1)
    df_ct["goc_ht_trieu"] = (df_ct["goc_hang_thang"] / 1e6).round(1)
    return df_ct
