"""tests/test_giao_ban.py — data/giao_ban.tinh_so_lieu_van_xuoi()

Hàm thuần DataFrame, không cần SQLite hay Streamlit.
"""
from __future__ import annotations

import pandas as pd
import pytest

from data.giao_ban import tinh_so_lieu_van_xuoi


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _df_xa(
    dn: list[float] | None = None,
    qh: list[float] | None = None,
) -> pd.DataFrame:
    """DataFrame 2 hàng tại Xã A."""
    dn = dn or [1_000_000, 2_000_000]
    qh = qh or [0, 500_000]
    return pd.DataFrame({
        "Tên xã":              ["Xã A", "Xã A"],
        "Mã KH":               ["KH001", "KH002"],
        "Tổng dư nợ":          dn,
        "Dư nợ quá hạn":       qh,
        "Dư nợ khoanh":        [0, 0],
        "Số dư tiền gửi 105":  [0, 0],
        "Giải ngân trong tháng": [0, 0],
        "Thu nợ TH tháng":     [0, 0],
        "Thu nợ QH tháng":     [0, 0],
        "Tên tổ":              ["Tổ 1", "Tổ 2"],
    })


# ══════════════════════════════════════════════════════════════════════════════
# tinh_so_lieu_van_xuoi()
# ══════════════════════════════════════════════════════════════════════════════

class TestTinhSoLieuVanXuoi:

    # ── Kiểu trả về ──────────────────────────────────────────────────────────

    def test_tra_ve_dict(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        assert isinstance(result, dict)

    def test_co_cac_tag_bat_buoc(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        for tag in [
            "{{tong_du_no}}", "{{so_kh}}", "{{so_to}}",
            "{{ty_le_nqh}}", "{{du_no_qh}}", "{{nam_moc}}",
            "{{tang_giam_thang}}", "{{tang_giam_dau_nam}}",
        ]:
            assert tag in result, f"Thiếu tag: {tag}"

    # ── Giá trị tính toán ─────────────────────────────────────────────────

    def test_tong_du_no_dung(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        # fmt() chia cho 1_000_000, kết quả "3" cho 3_000_000
        assert result["{{tong_du_no}}"] == "3"

    def test_ty_le_nqh_dung(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        # 500k / 3M ≈ 16.67%
        assert abs(float(result["{{ty_le_nqh}}"]) - 16.67) < 0.5

    def test_so_kh_dem_distinct_ma_kh(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        assert result["{{so_kh}}"] == "2"

    def test_so_to_dem_distinct(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        assert result["{{so_to}}"] == "2"

    def test_nam_moc_duoc_giu(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        assert result["{{nam_moc}}"] == "2025"

    # ── Baseline None ─────────────────────────────────────────────────────

    def test_baseline_none_khong_crash(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        # fmt(0) = '—' (em dash U+2014) — kiểm tra không crash, không rỗng
        assert "{{chenh_lech_dau_nam}}" in result
        assert isinstance(result["{{chenh_lech_dau_nam}}"], str)

    def test_baseline_none_tang_giam_default_tang(self):
        result = tinh_so_lieu_van_xuoi(_df_xa(), None, 2025)
        assert result["{{tang_giam_dau_nam}}"] == "tăng"

    # ── Với baseline ─────────────────────────────────────────────────────

    def test_voi_baseline_tang(self):
        """Hiện tại 3M > baseline 1.5M → tăng."""
        df_bl = _df_xa(dn=[500_000, 1_000_000], qh=[0, 0])
        result = tinh_so_lieu_van_xuoi(_df_xa(), df_bl, 2025)
        assert result["{{tang_giam_dau_nam}}"] == "tăng"

    def test_voi_baseline_giam(self):
        """Hiện tại 1.5M < baseline 3M → giảm."""
        df_bl = _df_xa(dn=[2_000_000, 1_000_000], qh=[0, 0])  # bl = 3M
        df_hien = _df_xa(dn=[500_000, 1_000_000], qh=[0, 0])  # ht = 1.5M
        result = tinh_so_lieu_van_xuoi(df_hien, df_bl, 2025)
        assert result["{{tang_giam_dau_nam}}"] == "giảm"

    # ── Edge cases ────────────────────────────────────────────────────────

    def test_du_no_0_khong_crash(self):
        df = _df_xa(dn=[0, 0], qh=[0, 0])
        result = tinh_so_lieu_van_xuoi(df, None, 2025)
        assert result["{{ty_le_nqh}}"] == "0.00"

    def test_kh_trung_khong_dem_2_lan(self):
        """2 dòng cùng Mã KH → chỉ đếm 1 khách hàng."""
        df = _df_xa()
        df["Mã KH"] = ["KH001", "KH001"]  # cùng mã
        result = tinh_so_lieu_van_xuoi(df, None, 2025)
        assert result["{{so_kh}}"] == "1"
