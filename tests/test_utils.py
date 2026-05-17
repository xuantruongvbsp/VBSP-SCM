"""Test các hàm format tiền tệ, số, tỷ lệ trong utils.py."""
import math
import pytest
from utils import (
    fmt, fmt_ty, fmt_bang_ty, fmt_tien, fmt_pct, fmt_so, fmt_cl, fmt_tl,
    vn, norm_col_header,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Nhóm fmt / fmt_ty — VND → triệu đồng (chia 1_000_000)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFmtTy:
    """Test hàm fmt_ty: đồng → triệu đồng."""

    def test_fmt_ty_1_trieu(self):
        """1.000.000 VND → '1' (1 triệu đồng)"""
        assert fmt_ty(1_000_000) == "1"

    def test_fmt_ty_1_ty(self):
        """1.000.000.000 VND → '1.000' (1 tỷ = 1.000 triệu)"""
        assert fmt_ty(1_000_000_000) == "1.000"

    # Bug guard: /1e6 not /1e9
    def test_fmt_ty_1_nghin_ty(self):
        """1.000.000.000.000 VND → '1.000.000' (1 nghìn tỷ = 1.000.000 triệu).
        Nếu ra '1.000' là đang chia 1e9 thay vì 1e6 — bug nghiêm trọng."""
        assert fmt_ty(1_000_000_000_000) == "1.000.000"

    def test_fmt_ty_so_0(self):
        """0 → '—'"""
        assert fmt_ty(0) == "—"

    def test_fmt_ty_so_am(self):
        """-500.000.000 → '-500' (dư âm 500 triệu)"""
        assert fmt_ty(-500_000_000) == "-500"

    def test_fmt_ty_none(self):
        """None → '—'"""
        assert fmt_ty(None) == "—"

    def test_fmt_ty_nan(self):
        """NaN → '—'"""
        assert fmt_ty(float("nan")) == "—"

    def test_fmt_ty_inf(self):
        """inf → '—'"""
        assert fmt_ty(float("inf")) == "—"

    def test_fmt_ty_chuoi_abc(self):
        """'abc' → '—'"""
        assert fmt_ty("abc") == "—"


class TestFmt:
    """Test hàm fmt (generic format, giống fmt_ty)."""

    def test_fmt_1_trieu(self):
        """fmt(1.000.000) → '1'"""
        assert fmt(1_000_000) == "1"

    def test_fmt_0(self):
        """fmt(0) → '—'"""
        assert fmt(0) == "—"

    def test_fmt_so_am(self):
        """fmt(-500_000_000) → '-500'"""
        assert fmt(-500_000_000) == "-500"


class TestFmtBangTy:
    """Test hàm fmt_bang_ty: đồng → triệu đồng (cố định đơn vị triệu)."""

    def test_fmt_bang_ty_1_ty(self):
        """1 tỷ → '1.000' (triệu)"""
        assert fmt_bang_ty(1_000_000_000) == "1.000"

    def test_fmt_bang_ty_0(self):
        """0 → '—'"""
        assert fmt_bang_ty(0) == "—"

    def test_fmt_bang_ty_so_le(self):
        """fmt_bang_ty(1_500_000, so_le=1) → '1,5' (1.5 triệu, 1 số lẻ)"""
        assert fmt_bang_ty(1_500_000, so_le=1) == "1,5"

    def test_fmt_bang_ty_abc(self):
        """'abc' → '—'"""
        assert fmt_bang_ty("abc") == "—"


class TestFmtTien:
    """Test hàm fmt_tien: đồng → triệu đồng."""

    def test_fmt_tien_1_trieu(self):
        """1 triệu → '1'"""
        assert fmt_tien(1_000_000) == "1"

    def test_fmt_tien_0(self):
        """0 → '—'"""
        assert fmt_tien(0) == "—"

    def test_fmt_tien_abc(self):
        """'abc' → '—'"""
        assert fmt_tien("abc") == "—"


# ═══════════════════════════════════════════════════════════════════════════════
# Nhóm fmt_so — số nguyên, dấu . nghìn
# ═══════════════════════════════════════════════════════════════════════════════

class TestFmtSo:
    """Test hàm fmt_so: số nguyên với dấu . phân cách hàng nghìn."""

    def test_fmt_so_binh_thuong(self):
        """1.234.567 → '1.234.567'"""
        assert fmt_so(1_234_567) == "1.234.567"

    def test_fmt_so_0(self):
        """0 → '0' (hàm không có check abs > 0, trả về '0')"""
        assert fmt_so(0) == "0"

    def test_fmt_so_abc(self):
        """'abc' → '—'"""
        assert fmt_so("abc") == "—"


# ═══════════════════════════════════════════════════════════════════════════════
# Nhóm fmt_pct — tỷ lệ phần trăm có dấu
# ═══════════════════════════════════════════════════════════════════════════════

class TestFmtPct:
    """Test hàm fmt_pct: tỷ lệ % có dấu +/-."""

    def test_fmt_pct_duong(self):
        """87.5 → '+87,5%' (dương có dấu +)"""
        assert fmt_pct(87.5) == "+87,5%"

    def test_fmt_pct_am(self):
        """-10.0 → '-10%' (âm có dấu -; vn() rstrip số 0 ở cuối)"""
        assert fmt_pct(-10.0) == "-10%"

    def test_fmt_pct_0(self):
        """0 → '0%' (trường hợp đặc biệt)"""
        assert fmt_pct(0) == "0%"

    def test_fmt_pct_abc(self):
        """'abc' → '—'"""
        assert fmt_pct("abc") == "—"


# ═══════════════════════════════════════════════════════════════════════════════
# Nhóm vn — số thực → chuỗi VN (dấu . nghìn, dấu , thập phân)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVn:
    """Test hàm vn: format số kiểu Việt Nam."""

    def test_vn_co_thap_phan(self):
        """vn(1234567.5, d=1) → '1.234.567,5'"""
        assert vn(1_234_567.5, d=1) == "1.234.567,5"

    def test_vn_so_nguyen(self):
        """vn(-500, d=0) → '-500'"""
        assert vn(-500, d=0) == "-500"

    def test_vn_abc(self):
        """vn('abc') → '—'"""
        assert vn("abc") == "—"


# ═══════════════════════════════════════════════════════════════════════════════
# Nhóm norm_col_header — chuẩn hóa tên cột
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormColHeader:
    """Test hàm norm_col_header: strip NBSP, thin-space, whitespace."""

    def test_norm_col_header_nbsp(self):
        """Chuỗi có NBSP (\\u00a0) → được strip"""
        result = norm_col_header("\u00a0Tên\u00a0KH\u00a0")
        assert result == "Tên KH"

    def test_norm_col_header_thin_space(self):
        """Chuỗi có thin-space (\\u202f) → được strip"""
        result = norm_col_header("\u202fTên\u202fKH\u202f")
        assert result == "Tên KH"

    def test_norm_col_header_trim(self):
        """'  Tên KH  ' → 'Tên KH'"""
        assert norm_col_header("  Tên KH  ") == "Tên KH"


# ═══════════════════════════════════════════════════════════════════════════════
# Nhóm fmt_cl — chênh lệch triệu đồng có dấu
# ═══════════════════════════════════════════════════════════════════════════════

class TestFmtCl:
    """Test hàm fmt_cl: chênh lệch triệu đồng có dấu +/-."""

    def test_fmt_cl_duong(self):
        """Giá trị dương → có dấu +"""
        assert fmt_cl(1_000_000) == "+1"

    def test_fmt_cl_am(self):
        """Giá trị âm → có dấu -"""
        assert fmt_cl(-500_000_000) == "-500"

    def test_fmt_cl_0(self):
        """0 → '—'"""
        assert fmt_cl(0) == "—"

    def test_fmt_cl_abc(self):
        """'abc' → '—'"""
        assert fmt_cl("abc") == "—"


# ═══════════════════════════════════════════════════════════════════════════════
# Nhóm fmt_tl — tỷ lệ thực hiện / kế hoạch
# ═══════════════════════════════════════════════════════════════════════════════

class TestFmtTl:
    """Test hàm fmt_tl: tỷ lệ thực hiện/kế hoạch."""

    def test_fmt_tl_binh_thuong(self):
        """fmt_tl(87, 100) → '87,0%'"""
        assert fmt_tl(87, 100) == "87,0%"

    def test_fmt_tl_ca_hai_bang_0(self):
        """fmt_tl(0, 0) → '—' (chia cho 0)"""
        assert fmt_tl(0, 0) == "—"

    def test_fmt_tl_mau_so_0(self):
        """fmt_tl(50, 0) → '—' (kế hoạch = 0)"""
        assert fmt_tl(50, 0) == "—"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
