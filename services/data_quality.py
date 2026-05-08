"""
Lớp chuẩn hóa và kiểm soát chất lượng dữ liệu tập trung.

Mục tiêu:
- Chuẩn hóa tên cột theo schema thống nhất.
- Chuẩn hóa mã/tên PGD, xã và chương trình tín dụng.
- Kiểm tra chất lượng dữ liệu (cột bắt buộc, null-rate, unique, domain).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from config import (
    COT_MA_CHUONG_TRINH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    DON_VI_CHI_NHANH,
    DS_PGD,
    MA_PGD_MAP,
    TEN_PGD_TO_MA,
    XA_TO_PGD,
)


SchemaRule = dict[str, Any]


CANONICAL_SCHEMA: dict[str, SchemaRule] = {
    "hstd": {
        "required_columns": [COT_TEN_PGD, COT_TEN_XA],
        "numeric_columns": ["Dư nợ trong hạn", "Dư nợ quá hạn", "Tổng dư nợ", "Nguồn vốn"],
        "unique_columns": [],  # Số khế ước hợp lệ khi trùng: 1 KH vay nhiều CT
        "domain_columns": {"Nguồn vốn": {1, 2, "1", "2", 1.0, 2.0}},
        "rename_map": {},
    },
    "nq11": {
        "required_columns": ["Mã khách hàng"],
        "numeric_columns": ["Số tiền", "Dư nợ"],
        "unique_columns": [],
        "domain_columns": {},
        "rename_map": {},
    },
    "gqvl": {
        "required_columns": ["Mã PGD", COT_TEN_XA],
        "numeric_columns": ["Dư nợ trong hạn", "Dư nợ quá hạn", "Dư nợ khoanh"],
        "unique_columns": [],  # Số khế ước hợp lệ khi trùng
        "domain_columns": {"Nguồn vốn": {"TW", "ĐP"}},  # Giá trị thực tế trong file
        "rename_map": {},
    },
    "pgd": {
        "required_columns": [COT_SO_KU, COT_TEN_PGD],
        "numeric_columns": ["Dư nợ trong hạn", "Dư nợ quá hạn", "Tổng dư nợ"],
        "unique_columns": [COT_SO_KU],
        "domain_columns": {},
        "rename_map": {},
    },
}


@dataclass
class DataQualityResult:
    """Kết quả xử lý chất lượng dữ liệu."""

    df: pd.DataFrame
    report: dict[str, Any]
    errors: list[str]
    is_valid: bool = True


def _safe_series(df: pd.DataFrame, col: str) -> pd.Series:
    """Trả về Series an toàn; nếu thiếu cột thì trả Series rỗng."""
    if col not in df.columns:
        return pd.Series(dtype="object")
    return df[col]


def chuan_hoa_ten_cot(df: pd.DataFrame, loai: str) -> pd.DataFrame:
    """Đổi tên cột theo schema canonical cho từng loại dữ liệu."""
    schema = CANONICAL_SCHEMA.get(loai, {})
    rename_map = schema.get("rename_map", {}) or {}
    if not rename_map:
        return df
    return df.rename(columns=rename_map)


def kiem_tra_du_no_am(df: pd.DataFrame, loai: str) -> list[str]:
    """
    Phát hiện dư nợ âm trong HSTD/NQ11/GQVL.
    
    Args:
        df: DataFrame cần kiểm tra
        loai: "hstd" | "nq11" | "gqvl"
    
    Returns:
        Danh sách lỗi (rỗng nếu không có lỗi)
    """
    errors = []
    
    if loai == "hstd":
        cot_can_kiem_tra = ["Dư nợ trong hạn", "Dư nợ quá hạn", "Tổng dư nợ"]
    elif loai == "nq11":
        cot_can_kiem_tra = ["Dư nợ"]
    elif loai == "gqvl":
        cot_can_kiem_tra = ["Dư nợ trong hạn", "Dư nợ quá hạn", "Dư nợ khoanh"]
    else:
        return []
    
    for cot in cot_can_kiem_tra:
        if cot not in df.columns:
            continue
        
        s = pd.to_numeric(df[cot], errors='coerce')
        
        so_dong_am = int((s < 0).sum())
        
        if so_dong_am > 0:
            errors.append(
                f"⛔ Cột '{cot}' có {so_dong_am} dòng dư nợ ÂM — "
                f"Không được phép trong nghiệp vụ tín dụng!"
            )
    
    return errors


def kiem_tra_so_tien_giai_ngan(df: pd.DataFrame, loai: str) -> list[str]:
    """
    Kiểm tra NQ11: Số tiền giải ngân không được vượt Số tiền duyệt.
    
    Chỉ áp dụng cho loại = "nq11".
    """
    errors = []
    
    if loai != "nq11":
        return []
    
    cot_giai_ngan = None
    cot_duyet = None
    
    for c in df.columns:
        c_lower = c.lower()
        if "giải ngân" in c_lower or "giai ngan" in c_lower:
            cot_giai_ngan = c
        if "duyệt" in c_lower or "duyet" in c_lower:
            cot_duyet = c
    
    if not cot_giai_ngan or not cot_duyet:
        return []
    
    giai_ngan = pd.to_numeric(df[cot_giai_ngan], errors='coerce')
    duyet = pd.to_numeric(df[cot_duyet], errors='coerce')
    
    vuot_han_muc = int((giai_ngan > duyet).sum())
    
    if vuot_han_muc > 0:
        errors.append(
            f"⛔ Có {vuot_han_muc} dòng 'Số tiền giải ngân' > 'Số tiền duyệt' — "
            f"Vi phạm hạn mức tín dụng!"
        )
    
    return errors


def kiem_tra_ma_don_vi_hop_le(df: pd.DataFrame) -> list[str]:
    """
    Kiểm tra Tên PGD và Tên xã phải tồn tại trong config.

    Lưu ý: XA_TO_PGD dùng tiền tố "Xã/Phường/Thị trấn" nhưng file thực tế
    không có tiền tố → strip trước khi so sánh.
    Trả về danh sách lỗi chi tiết.
    """
    _TIEN_TO = ("Xã ", "Phường ", "Thị trấn ", "Thị xã ")
    _GIA_TRI_DAC_BIET = {"Vay trực tiếp", "nan", ""}

    def _strip_prefix(s: str) -> str:
        for p in _TIEN_TO:
            if s.startswith(p):
                return s[len(p):]
        return s

    errors = []
    ds_pgd_hop_le = set(DS_PGD + [DON_VI_CHI_NHANH])
    xa_hop_le = {_strip_prefix(k) for k in XA_TO_PGD.keys()}

    if COT_TEN_PGD in df.columns:
        pgd_vals = df[COT_TEN_PGD].astype(str).str.strip()
        pgd_invalid = pgd_vals[~pgd_vals.isin(ds_pgd_hop_le) & pgd_vals.notna() & ~pgd_vals.isin({"nan", ""})]
        if len(pgd_invalid) > 0:
            ds_sai = pgd_invalid.unique()[:5]
            errors.append(
                f"⛔ Cột '{COT_TEN_PGD}' có {len(pgd_invalid)} dòng không hợp lệ. "
                f"VD: {', '.join(ds_sai)}"
            )

    if COT_TEN_XA in df.columns:
        xa_vals = df[COT_TEN_XA].astype(str).str.strip()
        xa_vals_stripped = xa_vals
        for p in _TIEN_TO:
            xa_vals_stripped = xa_vals_stripped.str.replace(p, "", regex=False)
        xa_invalid = xa_vals[
            ~xa_vals_stripped.isin(xa_hop_le)
            & ~xa_vals_stripped.isin(_GIA_TRI_DAC_BIET)
            & xa_vals.notna()
        ]
        if len(xa_invalid) > 0:
            ds_sai = xa_invalid.unique()[:5]
            errors.append(
                f"⛔ Cột '{COT_TEN_XA}' có {len(xa_invalid)} dòng không tồn tại trong danh mục. "
                f"VD: {', '.join(ds_sai)}"
            )

    return errors


def chuan_hoa_ma_don_vi(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa tên PGD từ mã PGD và chuẩn hóa xã về đúng PGD."""
    out = df.copy()

    if "Mã PGD" in out.columns and COT_TEN_PGD not in out.columns:
        out[COT_TEN_PGD] = (
            out["Mã PGD"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.zfill(6)
            .map(MA_PGD_MAP)
        )

    if COT_TEN_PGD in out.columns:
        out[COT_TEN_PGD] = out[COT_TEN_PGD].astype(str).str.strip()
        mask_unknown = ~out[COT_TEN_PGD].isin(TEN_PGD_TO_MA.keys())
        out.loc[mask_unknown, COT_TEN_PGD] = out.loc[mask_unknown, COT_TEN_PGD]

    if COT_TEN_XA in out.columns and COT_TEN_PGD in out.columns:
        xa_to_pgd = out[COT_TEN_XA].astype(str).str.strip().map(XA_TO_PGD)
        out[COT_TEN_PGD] = out[COT_TEN_PGD].where(xa_to_pgd.isna(), xa_to_pgd)

    if COT_MA_CHUONG_TRINH in out.columns:
        out[COT_MA_CHUONG_TRINH] = (
            pd.to_numeric(out[COT_MA_CHUONG_TRINH], errors="coerce")
            .round(0)
            .astype("Int64")
        )
    if COT_TEN_CT in out.columns:
        out[COT_TEN_CT] = out[COT_TEN_CT].astype(str).str.strip()
    return out


def kiem_tra_chat_luong(df: pd.DataFrame, loai: str) -> DataQualityResult:
    """Kiểm tra chất lượng dữ liệu theo schema và trả báo cáo tổng hợp."""
    schema = CANONICAL_SCHEMA.get(loai, CANONICAL_SCHEMA["pgd"])
    out = chuan_hoa_ma_don_vi(chuan_hoa_ten_cot(df, loai))
    errors: list[str] = []

    errors.extend(kiem_tra_du_no_am(out, loai))
    errors.extend(kiem_tra_so_tien_giai_ngan(out, loai))
    errors.extend(kiem_tra_ma_don_vi_hop_le(out))

    missing_required = [c for c in schema["required_columns"] if c not in out.columns]
    if missing_required:
        errors.append(f"Thiếu cột bắt buộc: {', '.join(missing_required)}")

    duplicate_rows = 0
    for c in schema["unique_columns"]:
        if c in out.columns:
            dup = int(out[c].astype(str).duplicated().sum())
            duplicate_rows += dup
            if dup > 0:
                errors.append(f"Cột '{c}' có {dup} dòng trùng.")

    invalid_domain = 0
    for c, domain in schema["domain_columns"].items():
        if c not in out.columns:
            continue
        s = _safe_series(out, c)
        invalid_domain += int((~s.isin(domain) & s.notna()).sum())
    if invalid_domain > 0:
        errors.append(f"Có {invalid_domain} giá trị ngoài miền cho cột domain.")

    for c in schema["numeric_columns"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    null_required = 0
    for c in schema["required_columns"]:
        if c in out.columns:
            null_required += int(_safe_series(out, c).isna().sum())
    if null_required > 0:
        errors.append(f"Các cột bắt buộc có {null_required} ô trống.")

    is_valid = len(errors) == 0

    report = {
        "loai": loai,
        "tong_dong": int(len(out)),
        "so_loi": int(len(errors)),
        "missing_required_columns": missing_required,
        "duplicate_rows": int(duplicate_rows),
        "invalid_domain_rows": int(invalid_domain),
        "null_required_cells": int(null_required),
        "ti_le_dat_chuan": round(
            max(0.0, 100.0 - (len(errors) * 12.5)),
            1,
        ),
    }
    return DataQualityResult(df=out, report=report, errors=errors, is_valid=is_valid)


def tong_hop_bao_cao_chat_luong(reports: list[dict[str, Any]]) -> pd.DataFrame:
    """Chuyển danh sách report thành DataFrame phục vụ UI."""
    if not reports:
        return pd.DataFrame(columns=["Loại", "Tổng dòng", "Số lỗi", "Tỷ lệ đạt chuẩn"])
    rows = [
        {
            "Loại": r.get("loai", "").upper(),
            "Tổng dòng": r.get("tong_dong", 0),
            "Số lỗi": r.get("so_loi", 0),
            "Tỷ lệ đạt chuẩn": f"{r.get('ti_le_dat_chuan', 0)}%",
        }
        for r in reports
    ]
    return pd.DataFrame(rows)
