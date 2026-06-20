"""Hàm tiện ích dùng chung cho tất cả module data."""
import os
from typing import Callable

import duckdb
import pandas as pd
import unicodedata

from logger import get_logger

logger = get_logger(__name__)


def ts_file(fp: str) -> float:
    """Timestamp file — 0 nếu không tồn tại."""
    return os.path.getmtime(fp) if os.path.exists(fp) else 0


def _should_force_str(col: str) -> bool:
    s = unicodedata.normalize("NFC", str(col or "")).strip().lower()
    return (
        s.startswith("mã ")
        or s == "mã"
        or " mã " in f" {s} "
        or s in {"mã thôn", "mã xã", "mã kh", "mã khách hàng", "mã chương trình"}
        or s in {"số khế ước", "số ku", "số atm"}
        or "cmnd" in s
        or "cccd" in s
        or s in {"số điện thoại", "điện thoại", "sdt", "sđt"}
        or s.startswith("số ") and ("kh" in s or "account" in s)
    )


def _normalize_code_series(ser: pd.Series) -> pd.Series:
    bad_vals = {"nan", "none", "<na>", "nat"}
    if isinstance(ser.dtype, pd.CategoricalDtype):
        ser = ser.astype(object)
    elif pd.api.types.is_integer_dtype(ser.dtype):
        ser = ser.astype(object)
    elif pd.api.types.is_float_dtype(ser.dtype):
        whole = ser.notna() & (ser % 1 == 0)
        ser = ser.astype(object)
        if whole.any():
            ser = ser.copy()
            ser.loc[whole] = (
                pd.to_numeric(ser.loc[whole], errors="coerce")
                .astype("int64")
                .astype(str)
            )
    if ser.dtype == object:
        num = pd.to_numeric(ser, errors="coerce")
        whole2 = num.notna() & (num % 1 == 0) & ser.notna()
        if whole2.any():
            ser = ser.copy()
            ser.loc[whole2] = num.loc[whole2].astype("int64").astype(str)
    out = ser.fillna("").astype(str).str.strip()
    low = out.str.lower()
    return out.mask(low.isin(bad_vals), "")


def excel_to_parquet(
    excel_path: str,
    parquet_path: str,
    sheet: str | int,
    header: int,
    post_fn: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Chuyển Excel → Parquet cache với PyArrow backend.
    Chỉ chuyển lại khi Excel mới hơn cache → đọc nhanh hơn ~200x.
    RAM giảm 50-70% nhờ PyArrow zero-copy; cache nhỏ hơn ~30% nhờ zstd.
    """
    os.makedirs(os.path.dirname(parquet_path), exist_ok=True)
    df_fresh: pd.DataFrame | None = None
    if ts_file(parquet_path) < ts_file(excel_path):
        try:
            df_fresh = pd.read_excel(
                excel_path, sheet_name=sheet, header=header,
                engine="calamine",
            )
            if post_fn:
                df_fresh = post_fn(df_fresh)
            # Normalize tên cột: xóa ký tự xuống dòng trong header cell Excel
            # (VD: "Thời hạn\nvay" → "Thời hạn vay")
            df_fresh.columns = [
                c.replace('\n', ' ').replace('\r', '').strip()
                if isinstance(c, str) else c
                for c in df_fresh.columns
            ]
            for col in list(df_fresh.columns):
                if _should_force_str(col):
                    df_fresh[col] = _normalize_code_series(df_fresh[col])
            # Sanitize object columns: bytes → str để tránh PyArrow
            # "Expected bytes, got a 'float' object" khi gặp NaN trong cột binary
            for col in list(df_fresh.columns):
                if df_fresh[col].dtype == object:
                    try:
                        _non_null = df_fresh[col].dropna()
                        if len(_non_null) > 0 and any(
                            isinstance(v, bytes) for v in _non_null.iloc[:100]
                        ):
                            df_fresh[col] = df_fresh[col].apply(
                                lambda x: x.decode("utf-8", errors="replace") if isinstance(x, bytes) else x
                            )
                    except Exception:
                        pass
            df_fresh.to_parquet(parquet_path, index=False, engine='pyarrow', compression='zstd', compression_level=3)
        except Exception as e:
            logger.error("excel_to_parquet: lỗi xử lý file %s → %s — %s", excel_path, parquet_path, e, exc_info=True)
            try:
                if os.path.exists(parquet_path):
                    os.remove(parquet_path)
            except Exception as e2:
                logger.error("excel_to_parquet: không thể xóa cache parquet lỗi — %s", e2, exc_info=True)
            raise
        # Vừa ghi xong — df_fresh đã normalize, trả thẳng, không đọc lại parquet
        return df_fresh

    # Cache hit — đọc từ parquet, xử lý cache cũ có dtype sai (int64/float64)
    result = pd.read_parquet(parquet_path, engine='pyarrow')
    result.columns = [
        c.replace('\n', ' ').replace('\r', '').strip()
        if isinstance(c, str) else c
        for c in result.columns
    ]
    for col in list(result.columns):
        if _should_force_str(col):
            _s = result[col]
            if pd.api.types.is_integer_dtype(_s) or pd.api.types.is_float_dtype(_s):
                result[col] = _normalize_code_series(_s)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DUCKDB AGGREGATES — Truy vấn nhanh trực tiếp trên Parquet, không nạp vào RAM
# ══════════════════════════════════════════════════════════════════════════════


def _duckdb_query(sql: str, params: list | None = None) -> pd.DataFrame:
    """
    Chạy câu lệnh SQL trên DuckDB (in-process, không cần server).
    Trả về DataFrame. Mỗi lần gọi tạo connection mới và đóng ngay sau đó
    để tránh conflict với SQLite threading.local.

    Nội bộ — gọi qua các hàm aggregate bên dưới.
    """
    conn = duckdb.connect(database=":memory:", read_only=False)
    try:
        if params:
            result = conn.execute(sql, params).df()
        else:
            result = conn.execute(sql).df()
        return result
    finally:
        conn.close()


def tong_hop_du_no_pgd(parquet_path: str) -> pd.DataFrame:
    """
    Tổng hợp dư nợ theo PGD từ file Parquet toàn chi nhánh.

    Chỉ đọc các cột cần thiết từ Parquet (lazy scan).
    Trả về DataFrame với cột:
        [ten_pgd, ma_ct, tong_du_no, so_ho]

    Phù hợp cho: Tab Giao ban, Tab Tổng quan, Báo cáo điện báo.
    """
    from config import COT_TEN_PGD, COT_MA_CHUONG_TRINH, COT_TONG_DU_NO, COT_MA_KH

    if not os.path.exists(parquet_path):
        return pd.DataFrame()

    sql = f"""
        SELECT
            "{COT_TEN_PGD}"          AS ten_pgd,
            "{COT_MA_CHUONG_TRINH}"  AS ma_ct,
            SUM("{COT_TONG_DU_NO}")  AS tong_du_no,
            COUNT("{COT_MA_KH}")     AS so_ho
        FROM read_parquet(?)
        WHERE "{COT_TONG_DU_NO}" IS NOT NULL
          AND "{COT_TONG_DU_NO}" > 0
        GROUP BY "{COT_TEN_PGD}", "{COT_MA_CHUONG_TRINH}"
        ORDER BY "{COT_TEN_PGD}", "{COT_MA_CHUONG_TRINH}"
    """
    try:
        return _duckdb_query(sql, [parquet_path])
    except Exception:
        return pd.DataFrame()


def dem_no_qua_han_pgd(parquet_path: str) -> pd.DataFrame:
    """
    Đếm số món và tổng dư nợ quá hạn theo PGD.

    Trả về DataFrame với cột: [ten_pgd, so_mon_qh, tong_no_qh]
    Dùng cho: Widget cảnh báo NQH trên Tab Tổng quan.
    """
    from config import COT_TEN_PGD, COT_DU_NO_QH, COT_MA_KH

    if not os.path.exists(parquet_path):
        return pd.DataFrame()

    sql = f"""
        SELECT
            "{COT_TEN_PGD}"       AS ten_pgd,
            COUNT("{COT_MA_KH}")  AS so_mon_qh,
            SUM("{COT_DU_NO_QH}") AS tong_no_qh
        FROM read_parquet(?)
        WHERE "{COT_DU_NO_QH}" IS NOT NULL
          AND "{COT_DU_NO_QH}" > 0
        GROUP BY "{COT_TEN_PGD}"
        ORDER BY tong_no_qh DESC
    """
    try:
        return _duckdb_query(sql, [parquet_path])
    except Exception:
        return pd.DataFrame()


def tong_hop_theo_xa(parquet_path: str, ten_pgd: str) -> pd.DataFrame:
    """
    Tổng hợp dư nợ theo xã cho một PGD cụ thể.

    Chỉ lọc đúng PGD cần thiết ngay tại DuckDB (không load cả bảng).
    Trả về DataFrame với cột: [ten_xa, ma_ct, tong_du_no, so_ho]
    """
    from config import (
        COT_TEN_PGD,
        COT_MA_CHUONG_TRINH,
        COT_TONG_DU_NO,
        COT_MA_KH,
        COT_TEN_XA,
    )

    if not os.path.exists(parquet_path):
        return pd.DataFrame()

    sql = f"""
        SELECT
            "{COT_TEN_XA}"           AS ten_xa,
            "{COT_MA_CHUONG_TRINH}"  AS ma_ct,
            SUM("{COT_TONG_DU_NO}")  AS tong_du_no,
            COUNT("{COT_MA_KH}")     AS so_ho
        FROM read_parquet(?)
        WHERE "{COT_TEN_PGD}" = ?
          AND "{COT_TONG_DU_NO}" IS NOT NULL
        GROUP BY "{COT_TEN_XA}", "{COT_MA_CHUONG_TRINH}"
        ORDER BY "{COT_TEN_XA}", "{COT_MA_CHUONG_TRINH}"
    """
    try:
        return _duckdb_query(sql, [parquet_path, ten_pgd])
    except Exception:
        return pd.DataFrame()


def tong_hop_tq_pgd(parquet_path: str, nam_ht: int) -> pd.DataFrame:
    """
    Tổng hợp toàn PGD cho dashboard Tổng quan — 1 query thay 4 pandas groupby.

    Trả về DataFrame: [ten_pgd, du_no, so_kh, so_mon, nqh, du_no_khoanh,
                         lai_ton, ds_cho_vay, no_dh_nam, ds_thu_no]
    Tất cả giá trị là VND thô (chưa chia triệu).
    """
    from config import (
        COT_TEN_PGD, COT_MA_KH, COT_SO_KU,
        COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH,
        COT_LAI_TON, COT_NGAY_DH,
    )

    if not os.path.exists(parquet_path):
        return pd.DataFrame()

    schema = pd.read_parquet(parquet_path, engine='pyarrow').columns.tolist()

    has_khoanh = COT_DU_NO_KHOANH in schema
    has_lai_ton = COT_LAI_TON in schema
    has_ngay_dh = COT_NGAY_DH in schema

    select_cols = f"""
        "{COT_TEN_PGD}"          AS ten_pgd,
        SUM("{COT_TONG_DU_NO}")  AS du_no,
        COUNT(DISTINCT "{COT_MA_KH}") AS so_kh,
        COUNT("{COT_SO_KU}")     AS so_mon,
        SUM("{COT_DU_NO_QH}")    AS nqh
    """
    extra_cols = ""
    if has_khoanh:
        extra_cols += f""",
        SUM("{COT_DU_NO_KHOANH}") AS du_no_khoanh"""
    else:
        extra_cols += """,
        0 AS du_no_khoanh"""
    if has_lai_ton:
        extra_cols += f""",
        SUM("{COT_LAI_TON}") AS lai_ton"""
    else:
        extra_cols += """,
        0 AS lai_ton"""
    extra_cols += """,
        0 AS ds_cho_vay"""

    no_dh = ""
    if has_ngay_dh:
        no_dh = f""",
        SUM(CASE WHEN "{COT_NGAY_DH}" IS NOT NULL
            AND EXTRACT(YEAR FROM "{COT_NGAY_DH}") = {int(nam_ht)}
            THEN "{COT_TONG_DU_NO}" ELSE 0 END) AS no_dh_nam"""
    else:
        no_dh = """,
        0 AS no_dh_nam"""

    sql = f"""
        SELECT {select_cols}{extra_cols}{no_dh},
            0 AS ds_thu_no
        FROM read_parquet(?)
        WHERE "{COT_TONG_DU_NO}" IS NOT NULL
        GROUP BY "{COT_TEN_PGD}"
        ORDER BY "{COT_TEN_PGD}"
    """
    try:
        return _duckdb_query(sql, [parquet_path])
    except Exception:
        return pd.DataFrame()


def tong_hop_tq_co_cau_ct(parquet_path: str, pgd_filter: str = "") -> pd.DataFrame:
    """
    Tổng hợp cơ cấu dư nợ theo chương trình tín dụng + nguồn vốn.
    1 query thay thế 6+ pandas groupby trong tinh_co_cau_ct.

    Trả về DataFrame: [ten_ct, nguon_von, tong_du_no, so_kh, so_mon, nqh, khoanh, ...]
    """
    from config import (
        COT_TEN_CT, COT_MA_KH, COT_SO_KU,
        COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH,
        COT_NGUON_VON, COT_TEN_PGD,
    )

    if not os.path.exists(parquet_path):
        return pd.DataFrame()

    schema = pd.read_parquet(parquet_path, engine='pyarrow').columns.tolist()
    has_khoanh = COT_DU_NO_KHOANH in schema
    has_nv = COT_NGUON_VON in schema

    khoanh_col = f'SUM("{COT_DU_NO_KHOANH}")' if has_khoanh else '0'
    nv_group = f', "{COT_NGUON_VON}"' if has_nv else ''

    where_clause = f'WHERE "{COT_TONG_DU_NO}" IS NOT NULL'
    if pgd_filter and pgd_filter != "Tất cả":
        where_clause += f' AND "{COT_TEN_PGD}" = \'{pgd_filter}\''

    sql = f"""
        SELECT
            "{COT_TEN_CT}"          AS ten_ct,
            SUM("{COT_TONG_DU_NO}") AS tong_du_no,
            COUNT(DISTINCT "{COT_MA_KH}") AS so_kh,
            COUNT("{COT_SO_KU}")    AS so_mon,
            SUM("{COT_DU_NO_QH}")   AS nqh,
            {khoanh_col}            AS khoanh
            {nv_group}
        FROM read_parquet(?)
        {where_clause}
        GROUP BY "{COT_TEN_CT}"{nv_group}
        ORDER BY tong_du_no DESC
    """
    try:
        return _duckdb_query(sql, [parquet_path])
    except Exception:
        return pd.DataFrame()


def tong_hop_tq_kpi(parquet_path: str, pgd_filter: str = "") -> pd.DataFrame:
    """
    KPI tổng quan: tổng dư nợ, NQH, khoanh, số KH, số món.
    1 query thay thế pandas groupby trong tinh_kpi_tongquan.

    Trả về 1 dòng DataFrame: [tong_du_no, so_kh, so_mon, nqh, khoanh, lai_ton]
    """
    from config import (
        COT_TEN_PGD, COT_MA_KH, COT_SO_KU,
        COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH,
        COT_LAI_TON,
    )

    if not os.path.exists(parquet_path):
        return pd.DataFrame()

    schema = pd.read_parquet(parquet_path, engine='pyarrow').columns.tolist()
    has_khoanh = COT_DU_NO_KHOANH in schema
    has_lai_ton = COT_LAI_TON in schema
    khoanh_col = f'SUM("{COT_DU_NO_KHOANH}")' if has_khoanh else '0'
    lai_col = f'SUM("{COT_LAI_TON}")' if has_lai_ton else '0'

    where_clause = f'WHERE "{COT_TONG_DU_NO}" IS NOT NULL'
    if pgd_filter and pgd_filter != "Tất cả":
        where_clause += f' AND "{COT_TEN_PGD}" = \'{pgd_filter}\''

    sql = f"""
        SELECT
            SUM("{COT_TONG_DU_NO}")          AS tong_du_no,
            COUNT(DISTINCT "{COT_MA_KH}")     AS so_kh,
            COUNT("{COT_SO_KU}")              AS so_mon,
            SUM("{COT_DU_NO_QH}")             AS nqh,
            {khoanh_col}                      AS khoanh,
            {lai_col}                         AS lai_ton
        FROM read_parquet(?)
        {where_clause}
    """
    try:
        return _duckdb_query(sql, [parquet_path])
    except Exception:
        return pd.DataFrame()


def tong_hop_tq_pgd_full(parquet_path: str, nam_ht: int, pgd_filter: str = "") -> pd.DataFrame:
    """
    Tổng hợp PGD đầy đủ — thay thế tinh_tqpgd_extended + merge.
    1 query DuckDB trả tất cả chỉ số cho dashboard PGD.

    Columns: ten_pgd, du_no, so_kh, so_mon, nqh, du_no_khoanh,
             lai_ton, ds_cho_vay, no_dh_nam, ds_thu_no
    """
    from config import (
        COT_TEN_PGD, COT_MA_KH, COT_SO_KU,
        COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH,
        COT_LAI_TON, COT_NGAY_DH,
    )

    if not os.path.exists(parquet_path):
        return pd.DataFrame()

    schema = pd.read_parquet(parquet_path, engine='pyarrow').columns.tolist()

    has_khoanh = COT_DU_NO_KHOANH in schema
    has_lai_ton = COT_LAI_TON in schema
    has_ngay_dh = COT_NGAY_DH in schema

    khoanh_col = f'SUM("{COT_DU_NO_KHOANH}")' if has_khoanh else '0'
    lai_col = f'SUM("{COT_LAI_TON}")' if has_lai_ton else '0'

    no_dh = ""
    if has_ngay_dh:
        no_dh = f""",
        SUM(CASE WHEN "{COT_NGAY_DH}" IS NOT NULL
            AND EXTRACT(YEAR FROM "{COT_NGAY_DH}") = {int(nam_ht)}
            THEN "{COT_TONG_DU_NO}" ELSE 0 END)"""
    else:
        no_dh = """,
        0"""

    where_clause = f'WHERE "{COT_TONG_DU_NO}" IS NOT NULL'
    if pgd_filter and pgd_filter != "Tất cả":
        where_clause += f' AND "{COT_TEN_PGD}" = \'{pgd_filter}\''

    sql = f"""
        SELECT
            "{COT_TEN_PGD}"          AS ten_pgd,
            SUM("{COT_TONG_DU_NO}")  AS du_no,
            COUNT(DISTINCT "{COT_MA_KH}") AS so_kh,
            COUNT("{COT_SO_KU}")     AS so_mon,
            SUM("{COT_DU_NO_QH}")    AS nqh,
            {khoanh_col}             AS du_no_khoanh,
            {lai_col}                AS lai_ton,
            0                        AS ds_cho_vay
            {no_dh}                  AS no_dh_nam,
            0                        AS ds_thu_no
        FROM read_parquet(?)
        {where_clause}
        GROUP BY "{COT_TEN_PGD}"
        ORDER BY "{COT_TEN_PGD}"
    """
    try:
        return _duckdb_query(sql, [parquet_path])
    except Exception:
        return pd.DataFrame()
