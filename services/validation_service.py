"""
Service validation dữ liệu đa tầng cho hệ thống VBSP-SCM

Mục tiêu:
- Multi-tier validation (Block + Warning + Info)
- Validate PGD → Xã → Thôn → Điểm GD
- Hỗ trợ HSTD, GQVL, NQ11 và các bảng khác
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config import (
    COT_MA_PGD, COT_TEN_PGD,
    COT_MA_XA, COT_TEN_XA,
    COT_MA_THON, COT_TEN_THON,
    COT_MA_DGD, COT_TEN_DGD,
    DGD_DANH_SACH, DGD_MA_MAP,
    PGD_XA_MAP, XA_TO_PGD,
    MA_PGD_MAP, TEN_PGD_TO_MA,
    DS_PGD, DS_XA
)


class ValidationLevel(Enum):
    """Mức độ validation"""
    CRITICAL = "critical"  # Block upload
    WARNING = "warning"    # Show warning
    INFO = "info"          # Show info only


@dataclass
class ValidationError:
    """Lỗi validation"""
    level: ValidationLevel
    column: str
    message: str
    row_count: int = 0
    sample_values: List[str] = None
    
    def __post_init__(self):
        if self.sample_values is None:
            self.sample_values = []


@dataclass
class CrossPgdDuplicateReport:
    """Chẩn đoán khoản vay HSTD bị trùng chéo giữa nhiều PGD."""
    is_valid: bool = True
    reason: str = ""
    key_columns: Tuple[str, ...] = field(default_factory=tuple)
    duplicate_group_count: int = 0
    duplicate_row_count: int = 0
    duplicate_pair_count: int = 0
    total_duplicate_amount: float = 0.0
    estimated_excess_amount: float = 0.0
    blank_name_row_count: int = 0
    top_pairs: List[Dict[str, Any]] = field(default_factory=list)
    top_units: List[Dict[str, Any]] = field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)


class ValidationResult:
    """Kết quả validation"""
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.is_valid: bool = True
        self.critical_count: int = 0
        self.warning_count: int = 0
        self.info_count: int = 0
    
    def add_error(self, error: ValidationError):
        """Thêm lỗi vào kết quả"""
        self.errors.append(error)
        if error.level == ValidationLevel.CRITICAL:
            self.is_valid = False
            self.critical_count += 1
        elif error.level == ValidationLevel.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1
    
    def get_summary(self) -> str:
        """Lấy tóm tắt kết quả"""
        if self.is_valid:
            return "✅ Dữ liệu hợp lệ"
        
        parts = []
        if self.critical_count > 0:
            parts.append(f"🚫 {self.critical_count} lỗi nghiêm trọng")
        if self.warning_count > 0:
            parts.append(f"⚠️ {self.warning_count} cảnh báo")
        if self.info_count > 0:
            parts.append(f"ℹ️ {self.info_count} thông tin")
        
        return " | ".join(parts)


class ValidationService:
    """Service chính cho validation dữ liệu"""
    
    def __init__(self):
        self.pgd_names = set(DS_PGD)
        self.xa_names = set(DS_XA)
        self.dgd_names = {d["ten"] for d in DGD_DANH_SACH}
        self.dgd_ma = {d["ma_dgd"] for d in DGD_DANH_SACH if "ma_dgd" in d}
        self.xa_to_pgd = XA_TO_PGD
        self.pgd_to_xa = PGD_XA_MAP
    
    def validate_dataframe(self, df: pd.DataFrame, table_type: str = "hstd") -> ValidationResult:
        """
        Validate toàn bộ dataframe
        
        Args:
            df: DataFrame cần validate
            table_type: Loại bảng (hstd, gqvl, nq11)
        
        Returns:
            ValidationResult với tất cả lỗi
        """
        result = ValidationResult()
        
        if df.empty:
            result.add_error(ValidationError(
                ValidationLevel.INFO,
                "DataFrame",
                "DataFrame rỗng"
            ))
            return result
        
        # Validate PGD
        self._validate_pgd(df, result)
        
        # Validate Xã
        self._validate_xa(df, result)
        
        # Validate Thôn (nếu có)
        if COT_TEN_THON in df.columns:
            self._validate_thon(df, result)
        
        # Validate Điểm GD (nếu có)
        if COT_TEN_DGD in df.columns or "Tên ĐGD" in df.columns:
            self._validate_dgd(df, result)
        
        # Validate quan hệ PGD-Xã
        self._validate_pgd_xa_relationship(df, result)
        
        # Validate theo loại bảng
        if table_type == "hstd":
            self._validate_hstd_specific(df, result)
        elif table_type == "gqvl":
            self._validate_gqvl_specific(df, result)
        elif table_type == "nq11":
            self._validate_nq11_specific(df, result)
        
        return result
    
    def _validate_pgd(self, df: pd.DataFrame, result: ValidationResult):
        """Validate PGD"""
        pgd_col = self._get_column(df, [COT_TEN_PGD, "Tên PGD", "PGD"])
        if not pgd_col:
            return
        
        invalid_pgd = df[~df[pgd_col].isin(self.pgd_names)][pgd_col].dropna().unique()
        if len(invalid_pgd) > 0:
            result.add_error(ValidationError(
                ValidationLevel.CRITICAL,
                pgd_col,
                f"PGD không tồn tại trong hệ thống: {', '.join(map(str, invalid_pgd[:5]))}",
                row_count=len(df[df[pgd_col].isin(invalid_pgd)]),
                sample_values=list(map(str, invalid_pgd[:5]))
            ))
    
    def _validate_xa(self, df: pd.DataFrame, result: ValidationResult):
        """Validate Xã"""
        xa_col = self._get_column(df, [COT_TEN_XA, "Tên xã", "Xã"])
        if not xa_col:
            return
        
        invalid_xa = df[~df[xa_col].isin(self.xa_names)][xa_col].dropna().unique()
        if len(invalid_xa) > 0:
            result.add_error(ValidationError(
                ValidationLevel.CRITICAL,
                xa_col,
                f"Xã không tồn tại trong hệ thống: {', '.join(map(str, invalid_xa[:5]))}",
                row_count=len(df[df[xa_col].isin(invalid_xa)]),
                sample_values=list(map(str, invalid_xa[:5]))
            ))
    
    def _validate_thon(self, df: pd.DataFrame, result: ValidationResult):
        """Validate Thôn - Warning level vì có thể có thôn mới"""
        thon_col = self._get_column(df, [COT_TEN_THON, "Tên thôn", "Thôn", "Tên ấp", "Ấp"])
        if not thon_col:
            return
        
        # Chỉ warning cho thôn trống
        empty_thon = df[df[thon_col].isna() | (df[thon_col] == "") | (df[thon_col] == " ")]
        if len(empty_thon) > 0:
            result.add_error(ValidationError(
                ValidationLevel.WARNING,
                thon_col,
                f"Thôn/ấp trống: {len(empty_thon)} records",
                row_count=len(empty_thon)
            ))
    
    def _validate_dgd(self, df: pd.DataFrame, result: ValidationResult):
        """Validate Điểm Giao Dịch"""
        dgd_col = self._get_column(df, [COT_TEN_DGD, "Tên ĐGD", "Điểm GD"])
        if not dgd_col:
            return
        
        invalid_dgd = df[~df[dgd_col].isin(self.dgd_names)][dgd_col].dropna().unique()
        if len(invalid_dgd) > 0:
            result.add_error(ValidationError(
                ValidationLevel.WARNING,
                dgd_col,
                f"Điểm GD không tồn tại: {', '.join(map(str, invalid_dgd[:5]))}",
                row_count=len(df[df[dgd_col].isin(invalid_dgd)]),
                sample_values=list(map(str, invalid_dgd[:5]))
            ))
    
    def _validate_pgd_xa_relationship(self, df: pd.DataFrame, result: ValidationResult):
        """Validate quan hệ PGD-Xã"""
        pgd_col = self._get_column(df, [COT_TEN_PGD, "Tên PGD", "PGD"])
        xa_col = self._get_column(df, [COT_TEN_XA, "Tên xã", "Xã"])

        if not pgd_col or not xa_col:
            return

        # Vectorized: lấy distinct cặp (xa, pgd) rồi so với xa_to_pgd map
        pairs = df[[xa_col, pgd_col]].dropna().drop_duplicates()
        pairs = pairs.astype(str)
        pairs["expected_pgd"] = pairs[xa_col].map(self.xa_to_pgd)
        invalid = pairs[
            pairs["expected_pgd"].notna() & (pairs["expected_pgd"] != pairs[pgd_col])
        ]

        if not invalid.empty:
            samples = [
                f"{r[xa_col]} (thuộc {r['expected_pgd']}) nhưng trong dữ liệu là {r[pgd_col]}"
                for _, r in invalid.head(3).iterrows()
            ]
            result.add_error(ValidationError(
                ValidationLevel.CRITICAL,
                f"{pgd_col}-{xa_col}",
                f"Xã không thuộc PGD: {', '.join(samples)}",
                row_count=len(invalid),
                sample_values=samples,
            ))
    
    def _validate_hstd_specific(self, df: pd.DataFrame, result: ValidationResult):
        """Validate riêng cho HSTD — kiểm tra cột bắt buộc, dư nợ âm, trùng khế ước."""
        from config import COT_SO_KU, COT_MA_KH, COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH

        # 1. Cột bắt buộc
        required = [COT_SO_KU, COT_MA_KH, COT_TEN_PGD, COT_TEN_XA, COT_TONG_DU_NO]
        missing_cols = [c for c in required if c not in df.columns]
        if missing_cols:
            result.add_error(ValidationError(
                ValidationLevel.CRITICAL,
                "columns",
                f"Thiếu cột bắt buộc: {', '.join(missing_cols)}",
                row_count=0,
                sample_values=missing_cols,
            ))

        # 2. Dư nợ âm — không thể có dư nợ âm trong HSTD thực tế
        for cot in [COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO]:
            if cot not in df.columns:
                continue
            s = pd.to_numeric(df[cot], errors="coerce")
            so_am = int((s < 0).sum())
            if so_am > 0:
                result.add_error(ValidationError(
                    ValidationLevel.CRITICAL,
                    cot,
                    f"Cột '{cot}' có {so_am} dòng giá trị âm — kiểm tra lại nguồn dữ liệu",
                    row_count=so_am,
                ))

        # 3. Trùng Số Khế ước — cảnh báo để xác nhận (có thể cố ý)
        if COT_SO_KU in df.columns:
            dup_mask = df[COT_SO_KU].astype(str).str.strip().duplicated(keep=False)
            so_trung = int(dup_mask.sum())
            if so_trung > 0:
                samples = df.loc[dup_mask, COT_SO_KU].astype(str).unique()[:5].tolist()
                result.add_error(ValidationError(
                    ValidationLevel.WARNING,
                    COT_SO_KU,
                    f"Trùng Số Khế ước: {so_trung} dòng — {', '.join(samples)}",
                    row_count=so_trung,
                    sample_values=samples,
                ))
    
    def _validate_gqvl_specific(self, df: pd.DataFrame, result: ValidationResult):
        """Validate riêng cho GQVL"""
        # GQVL thường có ít cột hơn, chỉ validate cơ bản
        pass
    
    def _validate_nq11_specific(self, df: pd.DataFrame, result: ValidationResult):
        """Validate riêng cho NQ11"""
        # Có thể thêm các rule riêng cho NQ11 ở đây
        pass
    
    def _get_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """Tìm cột trong dataframe theo tên có thể"""
        for name in possible_names:
            if name in df.columns:
                return name
        return None
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Lấy thống kê về dữ liệu validation"""
        return {
            "total_pgds": len(self.pgd_names),
            "total_xas": len(self.xa_names),
            "total_dgds": len(self.dgd_names),
            "total_dgd_ma": len(self.dgd_ma),
            "pgd_to_xa_mapping": {pgd: len(xas) for pgd, xas in self.pgd_to_xa.items()},
        }


_BAD_TEXT_VALUES = {"", "nan", "none", "<na>", "nat"}


def _normalize_text_series(series: pd.Series) -> pd.Series:
    """Chuẩn hóa cột định danh để so khớp khóa khoản vay ổn định."""
    ser = series.copy()
    if isinstance(ser.dtype, pd.CategoricalDtype):
        ser = ser.astype(object)
    elif pd.api.types.is_integer_dtype(ser.dtype):
        ser = ser.astype(object)
    elif pd.api.types.is_float_dtype(ser.dtype):
        so = pd.to_numeric(ser, errors="coerce")
        nguyen = so.notna() & (so % 1 == 0)
        ser = ser.astype(object)
        if nguyen.any():
            ser = ser.copy()
            ser.loc[nguyen] = so.loc[nguyen].astype("int64").astype(str)

    if ser.dtype == object:
        mau = pd.to_numeric(ser.iloc[:200], errors="coerce")
        if mau.notna().any():
            so = pd.to_numeric(ser, errors="coerce")
            nguyen = so.notna() & (so % 1 == 0) & ser.notna()
            if nguyen.any():
                ser = ser.copy()
                ser.loc[nguyen] = so.loc[nguyen].astype("int64").astype(str)

    out = ser.fillna("").astype(str).str.strip()
    lower = out.str.lower()
    return out.where(~lower.isin(_BAD_TEXT_VALUES), "")


def _join_unique_values(values: pd.Series) -> str:
    vals = sorted({str(v).strip() for v in values if str(v).strip()})
    return " | ".join(vals)


def validate_hstd_cross_pgd_duplicates(df: pd.DataFrame) -> CrossPgdDuplicateReport:
    """
    Phát hiện khoản vay HSTD trùng chéo giữa nhiều PGD theo khóa:
    (Mã KH, Số khế ước).

    Trả về report chi tiết để caller quyết định block publish/cache.
    """
    from config import (
        COT_MA_KH,
        COT_NGAY_VAY,
        COT_SO_KU,
        COT_TEN_KH,
        COT_TEN_PGD,
        COT_TONG_DU_NO,
    )

    report = CrossPgdDuplicateReport(key_columns=(COT_MA_KH, COT_SO_KU))
    required = [COT_MA_KH, COT_SO_KU, COT_TEN_PGD]
    missing = [col for col in required if col not in df.columns]
    if missing:
        report.reason = f"Thiếu cột để kiểm tra trùng chéo: {', '.join(missing)}"
        return report

    du_no_series = (
        pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0)
        if COT_TONG_DU_NO in df.columns
        else pd.Series(0, index=df.index, dtype="float64")
    )
    ten_kh_series = (
        _normalize_text_series(df[COT_TEN_KH])
        if COT_TEN_KH in df.columns
        else pd.Series("", index=df.index, dtype="object")
    )
    ngay_vay_series = (
        _normalize_text_series(df[COT_NGAY_VAY])
        if COT_NGAY_VAY in df.columns
        else pd.Series("", index=df.index, dtype="object")
    )

    work = pd.DataFrame(
        {
            "ma_kh": _normalize_text_series(df[COT_MA_KH]),
            "so_ku": _normalize_text_series(df[COT_SO_KU]),
            "ten_pgd": _normalize_text_series(df[COT_TEN_PGD]),
            "ten_kh": ten_kh_series,
            "ngay_vay": ngay_vay_series,
            "tong_du_no": du_no_series,
        }
    )
    work = work[
        (work["ma_kh"] != "")
        & (work["so_ku"] != "")
        & (work["ten_pgd"] != "")
    ].copy()
    if work.empty:
        report.reason = "Không có dòng nào đủ khóa Mã KH + Số khế ước để đối chiếu."
        return report

    work["loan_key"] = work["ma_kh"] + "|" + work["so_ku"]
    work["ten_kh_trong"] = work["ten_kh"] == ""

    per_key = (
        work.groupby(["ma_kh", "so_ku"], sort=False)
        .agg(
            so_dong=("ten_pgd", "size"),
            so_pgd=("ten_pgd", "nunique"),
            tong_du_no=("tong_du_no", "sum"),
            du_no_lon_nhat=("tong_du_no", "max"),
        )
        .reset_index()
    )
    cross_keys = per_key[per_key["so_pgd"] > 1].copy()
    if cross_keys.empty:
        return report

    report.is_valid = False
    cross_keys["uoc_du_no_thua"] = (
        cross_keys["tong_du_no"] - cross_keys["du_no_lon_nhat"]
    ).clip(lower=0)

    cross_rows = cross_keys[["ma_kh", "so_ku"]].merge(
        work,
        on=["ma_kh", "so_ku"],
        how="left",
    )
    pair_map = (
        cross_rows[["ma_kh", "so_ku", "ten_pgd"]]
        .drop_duplicates()
        .groupby(["ma_kh", "so_ku"], sort=False)["ten_pgd"]
        .agg(_join_unique_values)
        .reset_index(name="cap_pgd")
    )
    cross_keys = cross_keys.merge(pair_map, on=["ma_kh", "so_ku"], how="left")
    cross_rows = cross_rows.merge(pair_map, on=["ma_kh", "so_ku"], how="left")

    report.duplicate_group_count = int(len(cross_keys))
    report.duplicate_row_count = int(len(cross_rows))
    report.duplicate_pair_count = int(cross_keys["cap_pgd"].nunique())
    report.total_duplicate_amount = float(cross_keys["tong_du_no"].sum())
    report.estimated_excess_amount = float(cross_keys["uoc_du_no_thua"].sum())
    report.blank_name_row_count = int(cross_rows["ten_kh_trong"].sum())

    top_pairs = (
        cross_keys.groupby("cap_pgd", as_index=False)
        .agg(
            so_mon_trung=("ma_kh", "size"),
            tong_du_no_trung=("tong_du_no", "sum"),
            uoc_du_no_thua=("uoc_du_no_thua", "sum"),
        )
        .sort_values(
            by=["tong_du_no_trung", "so_mon_trung"],
            ascending=[False, False],
        )
    )
    report.top_pairs = top_pairs.head(10).to_dict("records")

    top_units = (
        cross_rows.groupby("ten_pgd", as_index=False)
        .agg(
            so_dong_trung=("loan_key", "size"),
            so_mon_trung=("loan_key", "nunique"),
            tong_du_no_trung=("tong_du_no", "sum"),
            so_dong_ten_trong=("ten_kh_trong", "sum"),
        )
        .sort_values(
            by=["tong_du_no_trung", "so_mon_trung"],
            ascending=[False, False],
        )
    )
    report.top_units = top_units.head(10).to_dict("records")

    sample_rows = (
        cross_rows[
            [
                "cap_pgd",
                "ten_pgd",
                "ma_kh",
                "so_ku",
                "ten_kh",
                "ngay_vay",
                "tong_du_no",
                "ten_kh_trong",
            ]
        ]
        .sort_values(
            by=["cap_pgd", "ma_kh", "so_ku", "ten_pgd"],
            ascending=[True, True, True, True],
        )
        .head(20)
        .rename(
            columns={
                "cap_pgd": "cap_pgd",
                "ten_pgd": "ten_pgd",
                "ma_kh": COT_MA_KH,
                "so_ku": COT_SO_KU,
                "ten_kh": COT_TEN_KH,
                "ngay_vay": COT_NGAY_VAY,
                "tong_du_no": COT_TONG_DU_NO,
                "ten_kh_trong": "ten_kh_trong",
            }
        )
    )
    report.sample_rows = sample_rows.to_dict("records")
    return report


# Singleton instance
validation_service = ValidationService()


def validate_dataframe(df: pd.DataFrame, table_type: str = "hstd") -> ValidationResult:
    """
    Convenience function để validate dataframe
    
    Args:
        df: DataFrame cần validate
        table_type: Loại bảng (hstd, gqvl, nq11)
    
    Returns:
        ValidationResult với tất cả lỗi
    """
    return validation_service.validate_dataframe(df, table_type)


def get_validation_summary(df: pd.DataFrame, table_type: str = "hstd") -> str:
    """
    Lấy summary validation result
    
    Args:
        df: DataFrame cần validate
        table_type: Loại bảng
    
    Returns:
        String summary
    """
    result = validate_dataframe(df, table_type)
    return result.get_summary()
