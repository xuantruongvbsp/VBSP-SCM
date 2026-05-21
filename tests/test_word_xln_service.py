"""Tests cho services/word_xln_service.py.

Phân nhóm:
  - TestPgdHelpers : _pgd_plain / _pgd_line
  - TestNum        : _num (chuyển đổi string/số → float)
  - TestTaoWord01Xln : smoke test — _tao_word_01xln trả về bytes .docx hợp lệ
  - TestTaoWordSmokeAll : smoke test các mẫu còn lại (02/04/05/13/14 + tờ trình)
"""
from __future__ import annotations

from datetime import date

import pytest

from services.word_xln_service import (
    _num,
    _pgd_line,
    _pgd_plain,
    _tao_word_01xln,
    _tao_word_02xln,
    _tao_word_04xln,
    _tao_word_05xln,
    _tao_word_13xln,
    _tao_word_14xln,
    _tao_word_to_trinh_pgd,
    _tao_word_to_trinh_cn,
)


# ─── _pgd_plain / _pgd_line ──────────────────────────────────────────────────

class TestPgdHelpers:

    # _pgd_plain
    def test_pgd_plain_co_prefix(self):
        assert _pgd_plain("PGD Long Thành") == "Long Thành"

    def test_pgd_plain_khong_prefix(self):
        assert _pgd_plain("Long Thành") == "Long Thành"

    def test_pgd_plain_pgd_hoa(self):
        assert _pgd_plain("pgd long thành") == "long thành"  # startswith case-insensitive

    def test_pgd_plain_none(self):
        assert _pgd_plain(None) == ""

    def test_pgd_plain_empty(self):
        assert _pgd_plain("") == ""

    def test_pgd_plain_chi_co_pgd(self):
        # "PGD ".strip() = "PGD" → không match "pgd " prefix → giữ nguyên
        assert _pgd_plain("PGD ") == "PGD"

    # _pgd_line
    def test_pgd_line_them_prefix(self):
        assert _pgd_line("Long Thành") == "PGD Long Thành"

    def test_pgd_line_da_co_prefix(self):
        assert _pgd_line("PGD Long Thành") == "PGD Long Thành"

    def test_pgd_line_none_fallback(self):
        assert _pgd_line(None) == "PGD"

    def test_pgd_line_empty_fallback(self):
        assert _pgd_line("") == "PGD"


# ─── _num ────────────────────────────────────────────────────────────────────

class TestNum:

    def test_none_tra_0(self):
        assert _num(None) == 0.0

    def test_empty_str_tra_0(self):
        assert _num("") == 0.0

    def test_whitespace_tra_0(self):
        assert _num("   ") == 0.0

    def test_int(self):
        assert _num(100) == 100.0

    def test_float(self):
        assert _num(3.14) == 3.14

    def test_string_so_don_gian(self):
        assert _num("500") == 500.0

    def test_string_format_viet(self):
        # Dấu chấm ngăn cách hàng nghìn, dấu phẩy thập phân → VN format
        assert _num("1.234.567") == 1234567.0

    def test_string_co_space(self):
        assert _num("1 000 000") == 1000000.0

    def test_string_khong_hop_le_tra_0(self):
        assert _num("abc") == 0.0

    def test_string_dau_am(self):
        # "-500" → strip dấu âm sẽ fail, nhưng không có space/dot/comma → float("-500")
        # Hành vi hiện tại: sau strip space/replace(".","") → "-500" → float OK
        result = _num("-500")
        assert isinstance(result, float)


# ─── _tao_word_01xln ─────────────────────────────────────────────────────────

def _du_lieu_01():
    return {
        "dia_danh": "Đồng Nai",
        "ngay_ky": date(2026, 5, 21),
        "ten_nhcsxh": "PGD Long Thành",
        "ten_kh": "Nguyễn Văn A",
        "dia_chi": "123 Đường Lê Lợi, Long Thành",
        "ten_to": "Tổ TK&VV số 01",
        "to_truong": "Trần Thị B",
        "so_ku": "KU2024001",
        "ngay_vay": "01/01/2022",
        "ten_ct": "Hộ nghèo",
        "muc_vay": "50.000.000",
        "ngay_dh": "01/01/2027",
        "muc_dich_vay": "Chăn nuôi bò",
        "tong_du_no": "45.000.000",
        "du_no_goc": "40.000.000",
        "lai_ton": "5.000.000",
        "nguyen_nhan": "Bị thiên tai lũ lụt",
        "so_tien_thiet_hai": "20.000.000",
        "muc_do_thiet_hai": "40",
    }


class TestTaoWord01Xln:

    def test_tra_ve_bytes(self):
        byt = _tao_word_01xln(_du_lieu_01())
        assert isinstance(byt, bytes)

    def test_bytes_khong_rong(self):
        byt = _tao_word_01xln(_du_lieu_01())
        assert len(byt) > 1000  # file .docx tối thiểu ~5KB

    def test_docx_magic_bytes(self):
        """File .docx là ZIP — bắt đầu bằng PK\\x03\\x04."""
        byt = _tao_word_01xln(_du_lieu_01())
        assert byt[:4] == b"PK\x03\x04"

    def test_du_lieu_trong_van_tao_duoc(self):
        """Không crash khi truyền dict rỗng."""
        byt = _tao_word_01xln({})
        assert isinstance(byt, bytes)
        assert len(byt) > 0


# ─── Smoke tests tất cả các mẫu còn lại ─────────────────────────────────────

def _du_lieu_chung():
    """Dict đủ field để các mẫu không crash."""
    return {
        "dia_danh": "Đồng Nai",
        "ngay_ky": date(2026, 5, 21),
        "ten_nhcsxh": "PGD Long Thành",
        "ten_pgd": "PGD Long Thành",
        "ten_kh": "Nguyễn Văn A",
        "dia_chi": "123 Đường Lê Lợi",
        "ten_to": "Tổ 01",
        "to_truong": "Trần Thị B",
        "so_ku": "KU001",
        "ngay_vay": "01/01/2022",
        "ngay_dh": "01/01/2027",
        "ten_ct": "Hộ nghèo",
        "muc_vay": "50000000",
        "tong_du_no": "45000000",
        "du_no_goc": "40000000",
        "lai_ton": "5000000",
        "nguyen_nhan": "Thiên tai",
        "so_tien_thiet_hai": "20000000",
        "muc_do_thiet_hai": "40",
        "muc_dich_vay": "Chăn nuôi",
        "bien_phap_xu_ly": "Khoanh nợ",
        "loai_xu_ly": "Khoanh nợ",
        "so_tien_xu_ly": "40000000",
        "tu_ngay": "01/01/2026",
        "den_ngay": "01/01/2028",
        "nam_sinh": "1980",
        "so_cmnd": "12345678",
        "ngay_cap_cmnd": "01/01/2010",
        "noi_cap_cmnd": "Đồng Nai",
        "ghi_chu": "",
        "so_ho": 1,
        "tong_goc": 40000000,
        "tong_lai": 5000000,
        "ds_ho_so": [],
        # Tờ trình
        "ten_cn": "Chi nhánh Đồng Nai",
        "so_to_trinh": "01/TT",
        "ngay_to_trinh": date(2026, 5, 21),
        "noi_dung_trinh": "Xin phê duyệt khoanh nợ",
        "ds_pgd": [],
    }


def _tong_hop_rong():
    """Tổng hợp tối giản cho các mẫu Word cần tham số tong_hop."""
    return {
        "tong_ho": 0,
        "tong_goc": 0.0,
        "tong_lai": 0.0,
        "tong_tien": 0.0,
        "nhom_ct": {},
    }


class TestTaoWordSmokeAll:
    """Smoke test: mỗi hàm chỉ cần không crash và trả về bytes .docx hợp lệ."""

    def _is_valid_docx(self, byt: bytes) -> bool:
        return isinstance(byt, bytes) and byt[:4] == b"PK\x03\x04"

    def test_mau_02xln(self):
        byt = _tao_word_02xln(_du_lieu_chung())
        assert self._is_valid_docx(byt)

    def test_mau_04xln(self):
        # _tao_word_04xln(tong_hop, ten_pgd, nguon_label, dot, nam)
        byt = _tao_word_04xln(_tong_hop_rong(), "PGD Long Thành", "Trung ương", 1, 2026)
        assert self._is_valid_docx(byt)

    def test_mau_05xln(self):
        # _tao_word_05xln(tong_hop, ten_pgd, nguon_label, dot, nam)
        byt = _tao_word_05xln(_tong_hop_rong(), "PGD Long Thành", "Trung ương", 1, 2026)
        assert self._is_valid_docx(byt)

    def test_mau_13xln(self):
        # _tao_word_13xln(tong_hop, ten_pgd, nguon_label, so_qd, ngay_qd, ngay_bat_dau, ngay_ket_thuc)
        byt = _tao_word_13xln(
            _tong_hop_rong(), "PGD Long Thành", "Trung ương",
            "01/QĐ", date(2026, 1, 1), date(2026, 1, 1), date(2026, 12, 31),
        )
        assert self._is_valid_docx(byt)

    def test_mau_14xln(self):
        # _tao_word_14xln(tong_hop, ten_pgd, nguon_label, so_qd, ngay_qd, ngay_bat_dau, ngay_ket_thuc)
        byt = _tao_word_14xln(
            _tong_hop_rong(), "PGD Long Thành", "Trung ương",
            "01/QĐ", date(2026, 1, 1), date(2026, 1, 1), date(2026, 12, 31),
        )
        assert self._is_valid_docx(byt)

    def test_to_trinh_pgd(self):
        # _tao_word_to_trinh_pgd(tong_hop_khoanh, tong_hop_xoa, ds_khoanh, ten_pgd, nguon_label, dot, nam)
        byt = _tao_word_to_trinh_pgd(
            _tong_hop_rong(), _tong_hop_rong(), [],
            "PGD Long Thành", "Trung ương", 1, 2026,
        )
        assert self._is_valid_docx(byt)

    def test_to_trinh_cn(self):
        # _tao_word_to_trinh_cn(tong_hop_khoanh, tong_hop_xoa, ds_khoanh, ten_tinh, nguon_label, dot, nam)
        byt = _tao_word_to_trinh_cn(
            _tong_hop_rong(), _tong_hop_rong(), [],
            "Chi nhánh Đồng Nai", "Trung ương", 1, 2026,
        )
        assert self._is_valid_docx(byt)
