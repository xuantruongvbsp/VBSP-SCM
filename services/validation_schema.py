"""Schema validation tập trung — single source of truth cho mọi quy tắc kiểm tra dữ liệu.

Thêm loại file mới: khai báo schema ở đây, validation_service tự áp dụng.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_GQVL_DU_NO_KHOANH,
    COT_GQVL_MA_PGD,
    COT_MA_KH,
    COT_NGUON_VON,
    COT_NQ11_DU_NO,
    COT_NQ11_MA_KH,
    COT_NQ11_SO_TIEN,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
)


@dataclass
class ValidationSchema:
    """Quy tắc validation cho 1 loại dữ liệu."""

    required_columns: list[str] = field(default_factory=list)
    numeric_columns: list[str] = field(default_factory=list)
    domain_rules: dict[str, set] = field(default_factory=dict)  # column → allowed values
    unique_columns: list[str] = field(default_factory=list)
    negative_check_columns: list[str] = field(default_factory=list)
    negative_critical_threshold: float = 0.05  # >=5% negative rows = CRITICAL
    check_pgd: bool = True       # validate PGD names
    check_xa: bool = True        # validate Xa names
    check_pgd_xa_link: bool = True  # validate Xa belongs to PGD


SCHEMAS: dict[str, ValidationSchema] = {
    "hstd": ValidationSchema(
        required_columns=[COT_SO_KU, COT_MA_KH, COT_TEN_PGD, COT_TEN_XA, COT_TONG_DU_NO],
        numeric_columns=[COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO, COT_NGUON_VON],
        domain_rules={COT_NGUON_VON: {1, 2, "1", "2", 1.0, 2.0}},
        unique_columns=[COT_SO_KU],
        negative_check_columns=[COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO],
    ),
    "nq11": ValidationSchema(
        required_columns=[COT_NQ11_MA_KH],
        numeric_columns=[COT_NQ11_SO_TIEN, COT_NQ11_DU_NO],
        negative_check_columns=[COT_NQ11_DU_NO],
    ),
    "gqvl": ValidationSchema(
        required_columns=[COT_GQVL_MA_PGD, COT_TEN_XA],
        numeric_columns=[COT_DU_NO_TH, COT_DU_NO_QH, COT_GQVL_DU_NO_KHOANH],
        domain_rules={COT_NGUON_VON: {"TW", "ĐP"}},
        negative_check_columns=[COT_DU_NO_TH, COT_DU_NO_QH, COT_GQVL_DU_NO_KHOANH],
    ),
    "pgd": ValidationSchema(
        required_columns=[COT_SO_KU, COT_TEN_PGD],
        numeric_columns=[COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO],
        unique_columns=[COT_SO_KU],
    ),
    "cdtotkvv": ValidationSchema(
        check_pgd=False,
        check_xa=False,
        check_pgd_xa_link=False,
    ),
}


def get_schema(loai: str) -> ValidationSchema | None:
    """Trả về schema cho loại dữ liệu, hoặc None nếu chưa khai báo."""
    return SCHEMAS.get(loai)
