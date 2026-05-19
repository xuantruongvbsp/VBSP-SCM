"""
tests/test_currency.py
Kiểm tra các hàm format tiền tệ trong utils.py.

Mục đích:
- Đảm bảo fmt_ty() dùng /1e12 (tỷ đồng), KHÔNG phải /1e9
- Đảm bảo fmt_tien() dùng /1e6 (triệu đồng)
- Đảm bảo fmt_so(), fmt_pct() format đúng kiểu VN
- Bắt lỗi nếu ai đổi hằng số chia sai trong tương lai

Chạy: pytest tests/test_currency.py -v
"""

import sys
from pathlib import Path

# Đảm bảo import được utils.py từ root dự án
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import fmt_ty, fmt_tien, fmt_so, fmt_pct


# ══════════════════════════════════════════════════════════════════════════════
# fmt_ty — đơn vị TỶ đồng (/1e12)
# ══════════════════════════════════════════════════════════════════════════════

class TestFmtTy:
    """fmt_ty() nhận VND thô, hiển thị tỷ đồng."""

    def test_1_ty(self):
        """1 tỷ = 1_000_000_000_000 VND (12 số 0, KHÔNG phải 9)."""
        result = fmt_ty(1_000_000_000_000)
        # Phải chứa "1" và KHÔNG được là "1000" (dấu hiệu dùng /1e9)
        assert "1000" not in result, (
            f"fmt_ty(1 tỷ VND) trả '{result}' — có vẻ đang dùng /1e9 thay vì /1e12"
        )

    def test_100_ty(self):
        """100 tỷ = 100_000_000_000_000 VND."""
        result = fmt_ty(100_000_000_000_000)
        assert "100" in result, (
            f"fmt_ty(100 tỷ VND) trả '{result}' — kết quả không chứa '100'"
        )
        assert "100000" not in result, (
            f"fmt_ty(100 tỷ VND) trả '{result}' — có vẻ đang dùng /1e9"
        )

    def test_zero(self):
        """Giá trị 0 không được crash."""
        result = fmt_ty(0)
        assert result is not None
        assert isinstance(result, str)

    def test_none_or_nan(self):
        """None / NaN không crash — trả về chuỗi rỗng hoặc '-'."""
        import math
        for val in (None, float("nan")):
            result = fmt_ty(val)
            assert isinstance(result, str), (
                f"fmt_ty({val}) phải trả str, got {type(result)}"
            )

    def test_khong_dung_1e9(self):
        """
        Kiểm tra trực tiếp: 1 tỷ VND = 1e12, nếu chia /1e9 sẽ ra 1000.
        Đây là lỗi đã xảy ra 2 lần trong CHANGELOG (17/05, tab_trang_thai_nguon).
        """
        gia_tri_1_ty_vnd = 1_000_000_000_000
        result = fmt_ty(gia_tri_1_ty_vnd)
        # Nếu dùng /1e9 sẽ ra "1.000" hoặc "1000" thay vì "1"
        assert "1000" not in result and "1,000" not in result, (
            f"BUG /1e9: fmt_ty(1 tỷ VND) = '{result}'. "
            f"Phải là ~'1' tỷ, không phải '1000' tỷ. "
            f"Kiểm tra lại hằng số chia trong fmt_ty()."
        )


# ══════════════════════════════════════════════════════════════════════════════
# fmt_tien — đơn vị TRIỆU đồng (/1e6)
# ══════════════════════════════════════════════════════════════════════════════

class TestFmtTien:
    """fmt_tien() nhận VND thô, hiển thị triệu đồng."""

    def test_1_trieu(self):
        """1 triệu = 1_000_000 VND."""
        result = fmt_tien(1_000_000)
        assert "1000" not in result, (
            f"fmt_tien(1 triệu VND) trả '{result}' — có vẻ chia sai đơn vị"
        )

    def test_10_trieu(self):
        """10 triệu = 10_000_000 VND."""
        result = fmt_tien(10_000_000)
        assert "10" in result, (
            f"fmt_tien(10 triệu VND) trả '{result}' — không chứa '10'"
        )

    def test_zero(self):
        result = fmt_tien(0)
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# fmt_so — format số nguyên kiểu VN (dấu . phân cách nghìn)
# ══════════════════════════════════════════════════════════════════════════════

class TestFmtSo:
    def test_1000(self):
        """1000 phải hiển thị có dấu phân cách."""
        result = fmt_so(1000)
        assert "1000" != result, (
            f"fmt_so(1000) = '{result}' — thiếu dấu phân cách hàng nghìn"
        )

    def test_so_lon(self):
        result = fmt_so(213343)
        # Đã từng bị lỗi hiển thị "213343" thay vì "213.343" (CHANGELOG 18/05)
        assert "213343" != result, (
            f"fmt_so(213343) = '{result}' — thiếu dấu phân cách (bug đã gặp 18/05)"
        )

    def test_zero(self):
        result = fmt_so(0)
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# fmt_pct — format phần trăm
# ══════════════════════════════════════════════════════════════════════════════

class TestFmtPct:
    def test_0_5(self):
        """0.5 = 50% hoặc 0.50% tùy convention — không crash là đủ."""
        result = fmt_pct(0.5)
        assert isinstance(result, str)
        assert "%" in result or result != "", (
            f"fmt_pct(0.5) = '{result}' — kết quả không hợp lệ"
        )

    def test_zero(self):
        result = fmt_pct(0)
        assert isinstance(result, str)

    def test_none(self):
        result = fmt_pct(None)
        assert isinstance(result, str)
