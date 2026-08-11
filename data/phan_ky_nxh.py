"""Đọc/ghi dữ liệu phân kỳ Nhà ở Xã hội (NXH) từ file Excel NHCSXH TW."""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import db
from config import CACHE_DIR
from logger import get_logger

logger = get_logger(__name__)

CACHE_NXH = str(Path(CACHE_DIR) / "phan_ky_nxh.parquet")

# Tên cột chuẩn — dùng khi import từ ngoài (nhac_deadline.py, v.v.)
COL_NXH_NGAY = "Ngày đến hạn kỳ con"
COL_NXH_TIEN = "Dư nợ kỳ con đến hạn"
COL_NXH_TGK  = "Tổng TG, TK"
COL_NXH_LAI  = "Lãi tồn"
COL_NXH_PGD  = "Tên PGD"

_REQUIRED_COLS = [COL_NXH_NGAY, COL_NXH_TIEN]
_HEADER_SCAN_ROWS = 12
_TEXT_COL_DTYPES = {
    "Mã PGD": str,
    "Mã xã": str,
    "Mã tổ": str,
    "Mã khách hàng": str,
    "Mã KH": str,
    "Mã chương trình vay": str,
    "Mã nhà đầu tư": str,
    "Số khế ước": str,
    "Số điện thoại": str,
}

# Các tên cột có thể gặp cho "Lãi tồn" tuỳ phiên bản export TW
_LAI_TON_ALIASES = [
    "Lãi tồn",
    "Lãi tồn đến kỳ",
    "Lãi còn lại",
    "Tổng lãi tồn",
    "Lãi tồn đến hạn",
]

# Cột ngày cần convert sang datetime
_DATE_COLS = [
    "Ngày đến hạn kỳ con",
    "Ngày vay",
    "Ngày đến hạn",
]

# Cột tiền cần convert sang numeric
_MONEY_COLS = [
    "Dư nợ kỳ con đến hạn",
    "Tổng TG, TK",
    "Lãi tồn",
    "Dư nợ gốc",
]


def _normalize_col_name(value: Any) -> str:
    """Chuẩn hoá nhãn cột từ Excel/preview."""
    if pd.isna(value):
        return ""
    return str(value).replace("\n", " ").replace("\r", "").strip()


def _normalize_code_value(value: Any, *, phone: bool = False) -> str:
    """Giữ mã định danh dạng text, bỏ `.0` và khôi phục số 0 đầu cho SĐT."""
    if pd.isna(value):
        return ""

    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            value = str(value)

    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
        if text.endswith(".0"):
            stem = text[:-2]
            if stem.isdigit():
                text = stem

    if text in {"nan", "None", "<NA>"}:
        return ""

    if phone:
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) == 9 and not digits.startswith("0"):
            return "0" + digits
        if digits:
            return digits

    return text


def _read_excel_nxh(raw: io.BytesIO) -> tuple[pd.DataFrame, int | None]:
    """Đọc Excel NXH bằng cách tự dò dòng header trong các dòng đầu."""
    raw.seek(0)
    preview = pd.read_excel(
        raw,
        header=None,
        nrows=_HEADER_SCAN_ROWS,
        engine="openpyxl",
        dtype=str,
    )

    header_row: int | None = None
    for idx, row in preview.iterrows():
        cols = {_normalize_col_name(v) for v in row.tolist()}
        if all(col in cols for col in _REQUIRED_COLS):
            header_row = int(idx)
            break

    candidates = []
    if header_row is not None:
        candidates.append(header_row)
    candidates.extend([4, 3, 0])

    seen: set[int] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)

        raw.seek(0)
        df = pd.read_excel(
            raw,
            header=candidate,
            engine="openpyxl",
            dtype=_TEXT_COL_DTYPES,
        )
        df = _clean(df)
        if all(col in df.columns for col in _REQUIRED_COLS):
            return df, candidate

    raw.seek(0)
    df = pd.read_excel(raw, header=0, engine="openpyxl")
    return _clean(df), None


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hoá DataFrame sau khi đọc Excel."""
    # Chuẩn hoá tên cột — xoá xuống dòng, khoảng trắng thừa
    cols = [_normalize_col_name(c) for c in df.columns]

    # Xoá cột không tên (Unnamed)
    keep = [
        bool(c) and c.lower() != "nan" and not c.startswith("Unnamed")
        for c in cols
    ]
    df = df.loc[:, keep]
    df.columns = [c for c, k in zip(cols, keep) if k]

    # Xoá dòng toàn NaN
    df = df.dropna(how="all").reset_index(drop=True)

    # Chuẩn hoá alias "Lãi tồn"
    for alias in _LAI_TON_ALIASES:
        if alias in df.columns and alias != "Lãi tồn":
            df = df.rename(columns={alias: "Lãi tồn"})
            break

    # Convert cột ngày
    for col in _DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    # Convert cột tiền + lãi sang numeric
    money_cols_actual = _MONEY_COLS + ["Lãi tồn"]
    for col in money_cols_actual:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Cột số thứ tự kỳ trả
    if "Số thứ tự kỳ trả" in df.columns:
        df["Số thứ tự kỳ trả"] = pd.to_numeric(
            df["Số thứ tự kỳ trả"], errors="coerce"
        )

    # Cột chuỗi code — giữ nguyên dạng text
    for col in ["Số khế ước", "Mã KH", "Mã khách hàng", "Mã PGD", "Mã xã", "Mã tổ"]:
        if col in df.columns:
            df[col] = df[col].apply(_normalize_code_value)

    if "Số điện thoại" in df.columns:
        df["Số điện thoại"] = df["Số điện thoại"].apply(
            lambda value: _normalize_code_value(value, phone=True)
        )

    return df


def luu_phan_ky_nxh(file_bytes: bytes, username: str) -> tuple[bool, str]:
    """Đọc Excel NXH, làm sạch, lưu Parquet + meta kv_store.

    Excel từ NHCSXH TW có thể có số dòng tiêu đề thay đổi theo mẫu export.
    Hàm tự dò dòng header trong các dòng đầu rồi fallback các mẫu cũ.

    Returns:
        (True, success_msg) hoặc (False, error_msg)
    ]
    """
    COL_NGAY = "Ngày đến hạn kỳ con"
    COL_TIEN = "Dư nợ kỳ con đến hạn"
    COL_PGD  = "Tên PGD"

    try:
        os.makedirs(os.path.dirname(CACHE_NXH), exist_ok=True)

        raw = io.BytesIO(file_bytes)
        df, header_row = _read_excel_nxh(raw)

        if COL_NGAY not in df.columns or COL_TIEN not in df.columns:
            cols_found = ", ".join(df.columns.tolist()[:10])
            return (
                False,
                f"❌ Không tìm thấy cột '{COL_NGAY}' hoặc '{COL_TIEN}'.\n"
                f"Cột tìm thấy: {cols_found}...\n"
                f"Kiểm tra lại file Excel có đúng mẫu từ NHCSXH TW không.",
            )

        # Xoá dòng không có ngày hoặc dư nợ
        df = df[df[COL_NGAY].notna() | df[COL_TIEN].notna()].reset_index(drop=True)

        if df.empty:
            return False, "❌ File không có dữ liệu hợp lệ sau khi xử lý."

        # Lưu Parquet
        df.to_parquet(CACHE_NXH, index=False, engine="pyarrow", compression="zstd")

        # Lưu metadata
        now = datetime.now()
        so_pgd = df[COL_PGD].nunique() if COL_PGD in df.columns else 0
        meta = {
            "ngay_upload": now.isoformat(),
            "ngay_du_lieu": now.strftime("%d/%m/%Y"),
            "nguoi_upload": username,
            "so_dong": len(df),
            "so_pgd": so_pgd,
            "header_row": header_row + 1 if header_row is not None else None,
        }
        db.ghi_kv("phan_ky_nxh_meta", meta, username)
        db.ghi_audit(username, "upload_phan_ky_nxh",
                     f"Upload NXH: {len(df)} khoản, {so_pgd} PGD")

        return (
            True,
            f"✅ Đã lưu **{len(df):,}** khoản phân kỳ NXH "
            f"từ **{so_pgd}** PGD.",
        )

    except Exception as e:
        logger.error("luu_phan_ky_nxh: %s", e, exc_info=True)
        return False, f"❌ Lỗi xử lý file: {e}"


def doc_phan_ky_nxh() -> pd.DataFrame:
    """Đọc dữ liệu phân kỳ NXH từ Parquet cache.

    Returns:
        DataFrame với cột chuẩn. Trả về DataFrame rỗng nếu chưa có dữ liệu.
    """
    if not os.path.exists(CACHE_NXH):
        return pd.DataFrame()

    try:
        df = pd.read_parquet(CACHE_NXH, engine="pyarrow")

        # Đảm bảo cột ngày đúng kiểu datetime
        COL_NGAY = "Ngày đến hạn kỳ con"
        if COL_NGAY in df.columns:
            df[COL_NGAY] = pd.to_datetime(df[COL_NGAY], errors="coerce")

        return df

    except Exception as e:
        logger.error("doc_phan_ky_nxh: %s", e, exc_info=True)
        return pd.DataFrame()


def lay_ngay_du_lieu_phan_ky_nxh(fallback: object = "") -> str:
    """Lấy ngày dữ liệu của file NXH từ metadata, fallback theo mtime cache."""
    try:
        meta = db.doc_kv("phan_ky_nxh_meta") or {}
        for key in ("ngay_du_lieu", "ngay_upload"):
            raw = str(meta.get(key, "") or "").strip()
            if not raw:
                continue
            try:
                return pd.Timestamp(raw).strftime("%d/%m/%Y")
            except Exception:
                if key == "ngay_du_lieu":
                    return raw
    except Exception as e:
        logger.error("lay_ngay_du_lieu_phan_ky_nxh meta: %s", e, exc_info=True)

    try:
        if os.path.exists(CACHE_NXH):
            return datetime.fromtimestamp(os.path.getmtime(CACHE_NXH)).strftime("%d/%m/%Y")
    except Exception as e:
        logger.error("lay_ngay_du_lieu_phan_ky_nxh mtime: %s", e, exc_info=True)

    try:
        if fallback:
            return pd.Timestamp(fallback).strftime("%d/%m/%Y")
    except Exception:
        return str(fallback or "")
    return str(fallback or "")
