"""
scripts/validate_data.py
─────────────────────────
Kiểm tra toàn vẹn dữ liệu nhanh — chạy độc lập, không phụ thuộc Streamlit.

Kiểm tra:
1. File parquet tồn tại + có schema hợp lệ
2. Tổng dư nợ các PGD = dư nợ toàn CN (± sai số làm tròn)
3. Không có giá trị âm bất thường
4. Số lượng KH / món vay nhất quán giữa các cấp tổng hợp

Exit 0 = pass, 1 = có cảnh báo.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Thêm thư mục gốc vào path để import config
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import config as cfg
import pandas as pd
import pyarrow.parquet as pq
from config import (
    CACHE_HSTD, CACHE_NQ11, CACHE_GQVL,
    COT_TEN_PGD, COT_TEN_KH, COT_MA_KH, COT_SO_KU,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_DU_NO_TH,
    COT_TEN_CT, COT_NGUON_VON, COT_NGAY_SL, COT_NGAY_VAY,
    COT_TEN_XA, COT_TEN_TO, COT_DVUT,
    COT_TINH_TRANG, COT_DIA_CHI, COT_SDT,
    COT_MA_NDT, COT_TEN_NHA_DAU_TU as COT_TEN_NDT,
    COT_PL_NV, COT_GIAI_NGAN_TRONG_NAM,
    COT_NGAY_DH, COT_NGAY_DH_HD, COT_THOI_HAN, COT_LAI_SUAT,
    COT_MUC_VAY, COT_GOC_TRA, COT_LAI_DA_TRA, COT_CMND,
    COT_NGAY_SINH, COT_NGAY_CAP_CMND, COT_NOI_CAP_CMND,
    COT_NGAY_HH_KHOANH, COT_TEN_HSSV, COT_TEN_VC, COT_HINH_THUC_VAY,
    COT_LAI_TON, COT_LAI_TON_QH, COT_LAI_THANG,
    COT_MA_PGD, COT_MA_XA, COT_MA_TO, COT_TEN_TO_TRUONG, COT_MA_CHUONG_TRINH,
    COT_NGAY_DEN_HAN,
    DS_PGD, DON_VI_CHI_NHANH,
)

# ── Cột bắt buộc phải có trong HSTD ──────────────────────────────────────────
_HSTD_REQUIRED_COLS = [
    COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU,
    COT_NGAY_VAY, COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH,
    COT_TEN_CT, COT_NGUON_VON, COT_NGAY_SL,
]

_HSTD_NICE_COLS = [
    COT_DU_NO_KHOANH, COT_TEN_XA, COT_TEN_TO, COT_DVUT,
    COT_TINH_TRANG, COT_DIA_CHI, COT_SDT,
]

_HSTD_CODE_COLS = [COT_MA_PGD, COT_MA_XA, COT_MA_TO]
_EXPECTED_UNITS = [DON_VI_CHI_NHANH] + list(DS_PGD)


def _parquet_cols(path: str) -> set[str]:
    """Đọc tên cột từ parquet schema — không load toàn bộ dữ liệu."""
    schema = pq.read_schema(path)
    return {f.name for f in schema}


def _fmt_ds(values: list[str], limit: int = 8) -> str:
    if not values:
        return "[]"
    head = values[:limit]
    suffix = "" if len(values) <= limit else f", ... (+{len(values) - limit})"
    return "[" + ", ".join(map(str, head)) + suffix + "]"


def check_parquet_files() -> int:
    """Kiểm tra file parquet tồn tại và có schema cơ bản."""
    errors = 0
    checks = [
        (CACHE_HSTD, "HSTD", _HSTD_REQUIRED_COLS, _HSTD_NICE_COLS),
        (CACHE_NQ11, "NQ11", [COT_TEN_PGD, "DNO NQ11"], []),
        (CACHE_GQVL, "GQVL", [COT_TEN_PGD], []),
    ]
    for path, label, required, nice_cols in checks:
        if not os.path.exists(path):
            print(f"  ⚠️  [{label}] File chưa tồn tại: {path}")
            errors += 1
            continue
        try:
            cols = _parquet_cols(path)
        except Exception as e:
            print(f"  ❌ [{label}] Không đọc được schema: {e}")
            errors += 1
            continue

        missing = [c for c in required if c not in cols]
        if missing:
            print(f"  ⚠️  [{label}] Thiếu cột: {missing}")
            errors += 1
        else:
            nice_missing = [c for c in nice_cols if c not in cols]
            if nice_missing:
                print(f"  ✅ [{label}] Schema OK ({len(cols)} cột, thiếu {nice_missing})")
            else:
                print(f"  ✅ [{label}] Schema OK ({len(cols)} cột)")
    return errors


def _safe_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)


def _blank_mask(s: pd.Series) -> pd.Series:
    return s.isna() | s.astype(str).str.strip().isin(["", "nan", "None", "<NA>"])


def _clean_values(s: pd.Series) -> set[str]:
    return {
        str(v).strip()
        for v in s.dropna().tolist()
        if str(v).strip() and str(v).strip().lower() not in {"nan", "none", "<na>"}
    }


def _known_config_columns() -> set[str]:
    cols: set[str] = set()
    for name in dir(cfg):
        if not name.startswith("COT_"):
            continue
        value = getattr(cfg, name, None)
        if isinstance(value, str) and value.strip():
            cols.add(value)
    return cols


def _check_units(df: pd.DataFrame, *, label: str, require_full: bool) -> int:
    """Kiểm tra danh mục đơn vị có hợp lệ theo danh sách cấu hình."""
    if COT_TEN_PGD not in df.columns:
        return 0

    errors = 0
    actual = _clean_values(df[COT_TEN_PGD])
    expected = set(_EXPECTED_UNITS)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)

    print(f"  ✅ [{label}] Đơn vị có dữ liệu = {len(actual & expected)}/{len(expected)}")
    if missing:
        if require_full:
            print(f"  ⚠️  [{label}] Thiếu đơn vị trong danh mục: {_fmt_ds(missing)}")
            errors += 1
        else:
            print(f"  ℹ️  [{label}] Chưa phát sinh dữ liệu tại {len(missing)} đơn vị: {_fmt_ds(missing)}")
    if unknown:
        print(f"  ⚠️  [{label}] Tên đơn vị ngoài danh mục: {_fmt_ds(unknown)}")
        errors += 1

    blank_units = int(_blank_mask(df[COT_TEN_PGD]).sum())
    if blank_units:
        print(f"  ⚠️  [{label}] Có {blank_units} dòng trống {COT_TEN_PGD}")
        errors += 1
    return errors


def _check_required_values(df: pd.DataFrame) -> int:
    """Kiểm tra các khóa nghiệp vụ bắt buộc không rỗng trên dòng còn dư nợ."""
    errors = 0
    if COT_TONG_DU_NO in df.columns:
        active = _safe_num(df[COT_TONG_DU_NO]) > 0
    else:
        active = pd.Series([True] * len(df), index=df.index)

    for col in [COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_NGAY_VAY]:
        if col not in df.columns:
            continue
        n_blank = int((_blank_mask(df[col]) & active).sum())
        if n_blank:
            print(f"  ⚠️  [{col}] Có {n_blank} dòng dư nợ dương nhưng trống")
            errors += 1

    for col in _HSTD_CODE_COLS:
        if col not in df.columns:
            continue
        n_blank = int((_blank_mask(df[col]) & active).sum())
        if n_blank:
            print(f"  ⚠️  [{col}] Có {n_blank} dòng dư nợ dương nhưng trống mã")
            errors += 1
    return errors


def _check_duplicate_loans(df: pd.DataFrame) -> int:
    """Mỗi khế ước trong một đơn vị chỉ nên xuất hiện một dòng HSTD active."""
    required = [COT_TEN_PGD, COT_SO_KU]
    if any(c not in df.columns for c in required):
        return 0

    work = df[required].copy()
    mask = ~_blank_mask(work[COT_TEN_PGD]) & ~_blank_mask(work[COT_SO_KU])
    if COT_TONG_DU_NO in df.columns:
        mask &= _safe_num(df[COT_TONG_DU_NO]) > 0
    duplicated = work[mask].duplicated(required, keep=False)
    n_dup_rows = int(duplicated.sum())
    if n_dup_rows:
        sample = work[mask][duplicated].head(5).to_dict("records")
        print(f"  ⚠️  Có {n_dup_rows} dòng trùng khóa ({COT_TEN_PGD}, {COT_SO_KU}); mẫu={sample}")
        return 1

    print("  ✅ Không trùng khóa PGD + Số khế ước")
    return 0


def check_hstd_consistency() -> int:
    """Kiểm tra tính nhất quán của dữ liệu HSTD."""
    errors = 0
    if not os.path.exists(CACHE_HSTD):
        print("  ⏭️  HSTD chưa có — bỏ qua kiểm tra nhất quán")
        return errors

    try:
        df = pd.read_parquet(CACHE_HSTD)
    except Exception as e:
        print(f"  ❌ Không đọc được HSTD: {e}")
        return 1

    n_rows = len(df)
    print(f"  📊 {n_rows:,} dòng")

    errors += _check_units(df, label="HSTD", require_full=True)
    errors += _check_required_values(df)

    # 1. Kiểm tra giá trị âm
    for col in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_DU_NO_TH]:
        if col not in df.columns:
            continue
        neg = (_safe_num(df[col]) < 0).sum()
        if neg > 0:
            print(f"  ⚠️  [{col}] Có {neg} dòng giá trị âm")
            errors += 1

    # 2. Tổng dư nợ >= dư nợ trong hạn + quá hạn + khoanh
    tdn = _safe_num(df[COT_TONG_DU_NO]).sum() if COT_TONG_DU_NO in df.columns else 0
    dth = _safe_num(df[COT_DU_NO_TH]).sum() if COT_DU_NO_TH in df.columns else 0
    dqh = _safe_num(df[COT_DU_NO_QH]).sum() if COT_DU_NO_QH in df.columns else 0
    dnk = _safe_num(df[COT_DU_NO_KHOANH]).sum() if COT_DU_NO_KHOANH in df.columns else 0
    tong_thanh_phan = dth + dqh + dnk

    if tdn > 0:
        for label, value in [
            (COT_DU_NO_TH, dth),
            (COT_DU_NO_QH, dqh),
            (COT_DU_NO_KHOANH, dnk),
        ]:
            if value > tdn * 1.001:
                print(f"  ⚠️  Tổng {label} ({value:,.0f}) lớn hơn Tổng dư nợ ({tdn:,.0f})")
                errors += 1

    if tdn > 0 and abs(tdn - tong_thanh_phan) > max(tdn, tong_thanh_phan) * 0.01:
        print(f"  ⚠️  Tổng dư nợ ({tdn:,.0f}) ≠ DTH+QH+KN ({tong_thanh_phan:,.0f}) — chênh {(tdn - tong_thanh_phan):,.0f}")
        errors += 1
    else:
        print(f"  ✅ Tổng dư nợ     = {tdn:,.0f} VND")

    # 3. Tổng dư nợ filter theo PGD (dùng groupby)
    if COT_TEN_PGD in df.columns and COT_TONG_DU_NO in df.columns:
        df_num = df[[COT_TEN_PGD, COT_TONG_DU_NO]].copy()
        df_num[COT_TONG_DU_NO] = _safe_num(df_num[COT_TONG_DU_NO])
        by_pgd = df_num.groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum()
        n_pgd_co_dn = int((by_pgd > 0).sum())
        print(f"  ✅ PGD có dư nợ   = {n_pgd_co_dn}/{len(by_pgd)}")

        # So sánh tổng groupby với tdn
        sum_by_pgd = by_pgd.sum()
        if tdn > 0 and abs(tdn - sum_by_pgd) > max(tdn, sum_by_pgd) * 0.001:
            print(f"  ⚠️  Tổng groupby PGD ({sum_by_pgd:,.0f}) ≠ Tổng toàn CN ({tdn:,.0f})")
            errors += 1

    # 4. Thống kê cơ bản
    for col_label, col_name in [("KH", COT_MA_KH), ("Món vay", COT_SO_KU)]:
        if col_name in df.columns:
            n_unique = df[col_name].nunique()
            print(f"  ✅ Số {col_label} unique = {n_unique:,}")
    errors += _check_duplicate_loans(df)

    # 5. Ngày số liệu
    if COT_NGAY_SL in df.columns:
        ngay_raw = df[COT_NGAY_SL].dropna()
        ngay_values = ngay_raw.unique()
        ngay_parsed = pd.to_datetime(ngay_raw, errors="coerce", dayfirst=True)
        n_invalid = int(ngay_parsed.isna().sum())
        if n_invalid:
            print(f"  ⚠️  Ngày số liệu có {n_invalid} dòng không parse được")
            errors += 1
        if len(ngay_values) <= 3:
            print(f"  ✅ Ngày số liệu    = {sorted(map(str, ngay_values))}")
        else:
            print(f"  ⚠️  Ngày số liệu phân tán — {len(ngay_values)} giá trị khác nhau")
            errors += 1

    # 6. Phát hiện cột lạ (không có hằng số COT_* tương ứng trong config)
    known_cols = _known_config_columns()
    actual_cols = set(df.columns)
    unknown = sorted(actual_cols - known_cols)
    if unknown:
        print(
            "  ℹ️  Có "
            f"{len(unknown)} cột HSTD chưa map qua COT_* trong config; mẫu={_fmt_ds(unknown, limit=12)}"
        )

    return errors


def check_nq11_consistency() -> int:
    """Kiểm tra nhất quán dữ liệu NQ11."""
    errors = 0
    if not os.path.exists(CACHE_NQ11):
        print("  ⏭️  NQ11 chưa có — bỏ qua")
        return errors

    try:
        df = pd.read_parquet(CACHE_NQ11)
    except Exception as e:
        print(f"  ❌ Không đọc được NQ11: {e}")
        return 1

    n_rows = len(df)
    print(f"  📊 {n_rows:,} dòng")
    errors += _check_units(df, label="NQ11", require_full=False)

    # Check giá trị âm
    for col in ["DNO NQ11", "Nợ trong hạn", "Nợ quá hạn", "Nợ khoanh"]:
        if col not in df.columns:
            continue
        neg = (_safe_num(df[col]) < 0).sum()
        if neg > 0:
            print(f"  ⚠️  [NQ11/{col}] Có {neg} dòng giá trị âm")
            errors += 1

    # Nợ TH + QH + KN ≈ DNO (có thể khác do DNO NQ11 là tổng riêng)
    if "DNO NQ11" in df.columns:
        dno = _safe_num(df["DNO NQ11"]).sum()
        print(f"  ✅ [NQ11] DNO = {dno:,.0f} VND")

    return errors


def check_gqvl_consistency() -> int:
    """Kiểm tra nhất quán dữ liệu GQVL."""
    errors = 0
    if not os.path.exists(CACHE_GQVL):
        print("  ⏭️  GQVL chưa có — bỏ qua")
        return errors

    try:
        df = pd.read_parquet(CACHE_GQVL)
    except Exception as e:
        print(f"  ❌ Không đọc được GQVL: {e}")
        return 1

    n_rows = len(df)
    print(f"  📊 {n_rows:,} dòng")
    errors += _check_units(df, label="GQVL", require_full=True)

    return errors


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("  VBSP-SCM — Data Validation")
    print("=" * 60)

    print("\n📁 [1/4] Kiểm tra file Parquet...")
    errors = check_parquet_files()

    print("\n🔍 [2/4] Kiểm tra nhất quán HSTD...")
    errors += check_hstd_consistency()

    print("\n📋 [3/4] Kiểm tra nhất quán NQ11...")
    errors += check_nq11_consistency()

    print("\n📋 [4/4] Kiểm tra nhất quán GQVL...")
    errors += check_gqvl_consistency()

    print("\n" + "=" * 60)
    if errors == 0:
        print("  ✅ Tất cả kiểm tra đều OK")
        return 0
    else:
        print(f"  ⚠️  {errors} cảnh báo cần xem xét")
        return 1


if __name__ == "__main__":
    sys.exit(main())
