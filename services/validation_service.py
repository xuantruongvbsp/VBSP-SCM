"""
Service validation dữ liệu đa tầng cho hệ thống VBSP-SCM

Mục tiêu:
- Multi-tier validation (Block + Warning + Info)
- Validate PGD → Xã → Thôn → Điểm GD
- Hỗ trợ HSTD, GQVL, NQ11 và các bảng khác
"""

from __future__ import annotations

from dataclasses import dataclass
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
        
        # Kiểm tra xã có thuộc PGD không
        invalid_relationships = []
        for _, row in df.iterrows():
            pgd = row[pgd_col]
            xa = row[xa_col]
            
            if pd.isna(pgd) or pd.isna(xa):
                continue
            
            # Kiểm tra qua XA_TO_PGD
            expected_pgd = self.xa_to_pgd.get(xa)
            if expected_pgd and expected_pgd != pgd:
                invalid_relationships.append(f"{xa} (thuộc {expected_pgd}) nhưng trong dữ liệu là {pgd}")
        
        if len(invalid_relationships) > 0:
            result.add_error(ValidationError(
                ValidationLevel.CRITICAL,
                f"{pgd_col}-{xa_col}",
                f"Xã không thuộc PGD: {', '.join(invalid_relationships[:3])}",
                row_count=len(invalid_relationships),
                sample_values=invalid_relationships[:3]
            ))
    
    def _validate_hstd_specific(self, df: pd.DataFrame, result: ValidationResult):
        """Validate riêng cho HSTD"""
        # Có thể thêm các rule riêng cho HSTD ở đây
        pass
    
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
