"""tests/test_hstd.py
──────────────────────────────────────────────────────
Unit test cho data/hstd.py:
  - danh_dau_khong_hd()  — đánh dấu khoản vay 3 tháng không hoạt động (KHĐ)
  - canh_bao_migration() — cảnh báo sớm nguy cơ BT→RR (E → KHĐ)

Không cần SQLite, không cần file upload — test thuần DataFrame.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import pytest

from data.hstd import (
    _dienbao_don_vi_nguon,
    _dienbao_don_vi_trieu,
    canh_bao_migration,
    danh_dau_khong_hd,
    db_lookup,
    doc_dienbao,
    doc_dienbao_matrix,
    liet_ke_sheet_dienbao,
)


class TestDonViDienBao:
    def test_nhan_dien_trieu_dong(self):
        df = pd.DataFrame([["Đơn vị tính: Triệu đồng"]])
        assert _dienbao_don_vi_trieu(df) is True

    def test_nhan_dien_dong(self):
        df = pd.DataFrame([["Đơn vị tính: Đồng"]])
        assert _dienbao_don_vi_trieu(df) is False
        assert _dienbao_don_vi_nguon(df) == "dong"

    def test_nhan_dien_nghin_dong(self):
        df = pd.DataFrame([["Đơn vị tính: Nghìn đồng"]])
        assert _dienbao_don_vi_trieu(df) is False
        assert _dienbao_don_vi_nguon(df) == "nghin"


class TestDocDienBao:
    def test_giu_chi_tieu_nguon_von_can_doi_va_bo_metadata(self, tmp_path):
        fp = tmp_path / "dienbao.xlsx"
        df = pd.DataFrame([
            [None, "NGÂN HÀNG CHÍNH SÁCH XÃ HỘI", None],
            [None, "Đơn vị tính: Triệu đồng", None],
            [None, None, None],
            [None, None, None],
            ["STT", "Chỉ tiêu", "Cộng"],
            [1, "Nguồn vốn cân đối từ TW (KHA)", 123],
            [2, "Tổng dư nợ", 456],
        ])
        df.to_excel(fp, index=False, header=False)

        rows = doc_dienbao(str(fp), ts=1)

        assert "Đơn vị tính: Triệu đồng" not in [r["ten"] for r in rows]
        assert db_lookup(rows, "Nguồn vốn cân đối từ TW (KHA)") == 123

    def test_sheet_ma_tran_co_cot_tong_khong_cong_trung_pgd(self, tmp_path):
        fp = tmp_path / "dienbao_matrix_tong.xlsx"
        df = pd.DataFrame([
            ["NHCSXH", None, None, None, None],
            [None, None, None, None, None],
            ["CÂN ĐỐI NGUỒN VỐN VÀ SỬ DỤNG VỐN", None, None, None, None],
            ["Đơn vị tính: Triệu đồng", None, None, None, None],
            [None, None, None, None, None],
            ["TT", "Chỉ tiêu", "Tổng", "Trong đó", None],
            [None, None, None, "PGD A", "PGD B"],
            ["A", "Tổng dư nợ", 300, 100, 200],
        ])
        df.to_excel(fp, index=False, header=False, sheet_name="TonghopBC")

        sheets = liet_ke_sheet_dienbao(str(fp))
        rows = doc_dienbao(str(fp), ts=1, sheet_name="TonghopBC")
        data = doc_dienbao_matrix(str(fp), ts=1, sheet_name="TonghopBC")

        assert sheets[0]["format"] == "matrix"
        assert sheets[0]["n_don_vi"] == 2
        assert db_lookup(rows, "Tổng dư nợ") == 300
        assert data["units"] == ["PGD A", "PGD B"]
        assert data["matrix"]["Tổng dư nợ"] == {"PGD A": 100, "PGD B": 200}

    def test_liet_ke_sheet_detect_header_o_dong_13_va_tu_bust_cache(self, tmp_path):
        fp = tmp_path / "dienbao_header_dong_13.xlsx"
        df = pd.DataFrame(
            [[None, None, None, None, None] for _ in range(12)]
            + [
                ["TT", "Chỉ tiêu", "Tổng", "Trong đó", None],
                [None, None, None, "PGD A", "PGD B"],
                ["A", "Tổng dư nợ", 300, 100, 200],
            ]
        )
        df.to_excel(fp, index=False, header=False, sheet_name="M")

        sheets = liet_ke_sheet_dienbao(str(fp))
        assert sheets[0]["format"] == "matrix"
        assert sheets[0]["n_don_vi"] == 2

        df.to_excel(fp, index=False, header=False, sheet_name="Y")
        future = time.time() + 10
        os.utime(fp, (future, future))

        sheets_after = liet_ke_sheet_dienbao(str(fp))
        assert [s["sheet"] for s in sheets_after] == ["Y"]

    def test_sheet_ma_tran_khong_cot_tong_tu_cong_cac_pgd(self, tmp_path):
        fp = tmp_path / "dienbao_matrix_khong_tong.xlsx"
        df = pd.DataFrame([
            ["NHCSXH", None, None, None, None],
            [None, None, None, None, None],
            ["CÂN ĐỐI NGUỒN VỐN VÀ SỬ DỤNG VỐN", None, None, None, None],
            ["Đơn vị tính: Triệu đồng", None, None, None, None],
            [None, None, None, None, None],
            ["TT", "Chỉ tiêu", "Mã chỉ tiêu", "Trong đó", None],
            [None, None, None, "PGD A", "PGD B"],
            ["A", "Tổng dư nợ", "TDN", 100, 200],
        ])
        df.to_excel(fp, index=False, header=False, sheet_name="Dulieu")

        rows = doc_dienbao(str(fp), ts=1, sheet_name="Dulieu")
        data = doc_dienbao_matrix(str(fp), ts=1, sheet_name="Dulieu")

        assert db_lookup(rows, "Tổng dư nợ") == 300
        assert data["rows"][0]["val"] == 300
        assert data["units"] == ["PGD A", "PGD B"]


# ══════════════════════════════════════════════════════════════════════════════
# Helpers tạo DataFrame mẫu
# ══════════════════════════════════════════════════════════════════════════════

def _df_p1(
    ngay_gdgn: str,
    ngay_sl: str,
    *,
    dn_th: float = 1_000_000,
    dn_qh: float = 0,
    dn_khoanh: float = 0,
    ma_ct: str | int = "4",
) -> pd.DataFrame:
    """DataFrame cho Priority-1 path: dùng cột ngày GDGN + ngày số liệu."""
    return pd.DataFrame({
        "Số khế ước":               ["KU001"],
        "Ngày giao dịch gần nhất":  [ngay_gdgn],
        "Ngày số liệu":             [ngay_sl],
        "Ngày vay":                 ["01/01/2022"],
        "Dư nợ trong hạn":          [dn_th],
        "Dư nợ quá hạn":            [dn_qh],
        "Dư nợ khoanh":             [dn_khoanh],
        "Mã chương trình":          [ma_ct],
    })


def _df_p2(
    lai_ton: float,
    lai_thang: float,
    *,
    dn_th: float = 1_000_000,
    dn_qh: float = 0,
    dn_khoanh: float = 0,
    ma_ct: str | int = "4",
) -> pd.DataFrame:
    """DataFrame cho Priority-2 path: dùng lãi tồn / lãi tháng, không có cột ngày GDGN."""
    return pd.DataFrame({
        "Số khế ước":             ["KU001"],
        "Lãi tồn TH":             [lai_ton],
        "Lãi DT trong tháng":     [lai_thang],
        "Dư nợ trong hạn":        [dn_th],
        "Dư nợ quá hạn":          [dn_qh],
        "Dư nợ khoanh":           [dn_khoanh],
        "Mã chương trình":        [ma_ct],
    })


def _df_mig(
    phan_loai: str = "E",
    lai_ton: float = 250_000,
    lai_thang: float = 100_000,
    is_3m_inactive: bool = False,
) -> pd.DataFrame:
    """DataFrame tối thiểu cho canh_bao_migration()."""
    return pd.DataFrame({
        "Số khế ước":             ["KU001"],
        "Tên KH":                 ["Nguyễn Văn A"],
        "Tên PGD":                ["PGD Long Thành"],
        "Tên xã":                 ["Xã An Bình"],
        "Tên ĐVUT":               ["Hội Phụ nữ"],
        "Phân loại":              [phan_loai],
        "Lãi tồn TH":             [lai_ton],
        "Lãi DT trong tháng":     [lai_thang],
        "is_3m_inactive":         [is_3m_inactive],
    })


# ══════════════════════════════════════════════════════════════════════════════
# danh_dau_khong_hd()
# ══════════════════════════════════════════════════════════════════════════════

class TestDanhDauKhongHD:

    # ── Output columns ─────────────────────────────────────────────────────

    def test_output_columns_luon_duoc_them(self):
        """Hàm luôn thêm is_3m_inactive và so_thang_khong_hd dù path nào."""
        df = _df_p1("01/01/2026", "15/04/2026")
        result = danh_dau_khong_hd(df)
        assert "is_3m_inactive" in result.columns
        assert "so_thang_khong_hd" in result.columns

    def test_fallback_khong_co_cot_van_them_column(self):
        """Không có cột ngày lẫn lãi → is_3m_inactive = False, không crash."""
        df = pd.DataFrame({
            "Số khế ước":      ["KU001"],
            "Dư nợ trong hạn": [1_000_000],
            "Dư nợ quá hạn":   [0],
        })
        result = danh_dau_khong_hd(df)
        assert "is_3m_inactive" in result.columns
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    # ── Priority-1: ngày GDGN ──────────────────────────────────────────────

    def test_p1_ro_rang_qua_3_thang(self):
        """01/01 → 15/04 ≈ 3.4 tháng → được đánh dấu KHĐ."""
        # 104 ngày / 30.44 ≈ 3.42 tháng
        df = _df_p1("01/01/2026", "15/04/2026")
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is True

    def test_p1_sat_nguong_tren_bi_danh_dau(self):
        """92 ngày / 30.44 ≈ 3.02 tháng — vừa vượt ngưỡng."""
        # 01/01 → 03/04: Jan(31) + Feb(28) + Mar(31) + 2 = 92 ngày
        df = _df_p1("01/01/2026", "03/04/2026")
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is True

    def test_p1_sat_nguong_duoi_khong_danh_dau(self):
        """89 ngày / 30.44 ≈ 2.92 tháng — vừa dưới ngưỡng."""
        # 01/01 → 31/03: Jan(31) + Feb(28) + 30 = 89 ngày
        df = _df_p1("01/01/2026", "31/03/2026")
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    def test_p1_duoi_3_thang_khong_danh_dau(self):
        """Khoảng cách < 1 tháng → không bị đánh dấu."""
        df = _df_p1("15/03/2026", "31/03/2026")
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    def test_p1_so_thang_dung_gia_tri(self):
        """so_thang_khong_hd phản ánh đúng khoảng cách ngày."""
        # 01/01 → 30/04 ≈ 119 ngày / 30.44 ≈ 3.9 tháng
        df = _df_p1("01/01/2026", "30/04/2026")
        result = danh_dau_khong_hd(df)
        so_thang = float(result["so_thang_khong_hd"].iloc[0])
        assert 3.5 <= so_thang <= 4.5

    # ── Exclusion mask ─────────────────────────────────────────────────────

    def test_loai_tru_du_no_bang_0(self):
        """Tổng dư nợ (TH + QH) = 0 → không đánh dấu dù ngày đủ điều kiện."""
        df = _df_p1("01/01/2026", "15/04/2026", dn_th=0, dn_qh=0)
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    def test_loai_tru_du_no_khoanh(self):
        """Có dư nợ khoanh > 0 → loại trừ khỏi đánh dấu KHĐ."""
        df = _df_p1("01/01/2026", "15/04/2026", dn_khoanh=500_000)
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    def test_loai_tru_ma_ct_hssv_string(self):
        """Mã chương trình '2' (HSSV) → không đánh dấu."""
        df = _df_p1("01/01/2026", "15/04/2026", ma_ct="2")
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    def test_loai_tru_ma_ct_hssv_integer(self):
        """Mã chương trình 2 (int) → cũng bị loại trừ."""
        df = _df_p1("01/01/2026", "15/04/2026", ma_ct=2)
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    def test_ma_ct_khac_2_khong_bi_loai(self):
        """Mã chương trình '4' → không bị loại trừ."""
        df = _df_p1("01/01/2026", "15/04/2026", ma_ct="4")
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is True

    # ── Priority-2: lãi tồn ────────────────────────────────────────────────

    def test_p2_lai_ton_lon_hon_3_lan_lai_thang(self):
        """Lãi tồn > 3× lãi tháng AND lãi tháng > 0 → is_3m_inactive = True."""
        df = _df_p2(lai_ton=400_000, lai_thang=100_000)  # 4× > 3
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is True

    def test_p2_lai_ton_duoi_3_lan(self):
        """Lãi tồn ≤ 3× lãi tháng → không đánh dấu."""
        df = _df_p2(lai_ton=200_000, lai_thang=100_000)  # 2× ≤ 3
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    def test_p2_lai_thang_bang_0_khong_danh_dau(self):
        """Lãi tháng = 0 → không đánh dấu (điều kiện lãi tháng > 0)."""
        df = _df_p2(lai_ton=500_000, lai_thang=0)
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    def test_p2_loai_tru_khoanh_van_ap_dung(self):
        """Priority-2 cũng áp dụng exclusion mask: dư nợ khoanh > 0 → loại."""
        df = _df_p2(lai_ton=400_000, lai_thang=100_000, dn_khoanh=500_000)
        result = danh_dau_khong_hd(df)
        assert bool(result["is_3m_inactive"].iloc[0]) is False

    # ── Multi-row ──────────────────────────────────────────────────────────

    def test_nhieu_dong_chi_danh_dau_dung_dieu_kien(self):
        """DataFrame 3 dòng: KU001 đủ điều kiện, KU002 mới, KU003 dư nợ = 0."""
        df = pd.DataFrame({
            "Số khế ước":               ["KU001",       "KU002",       "KU003"],
            "Ngày giao dịch gần nhất":  ["01/01/2026",  "15/03/2026",  "01/01/2026"],
            "Ngày số liệu":             ["30/04/2026",  "30/04/2026",  "30/04/2026"],
            "Ngày vay":                 ["01/01/2022",  "01/01/2022",  "01/01/2022"],
            "Dư nợ trong hạn":          [1_000_000,    1_000_000,     0],
            "Dư nợ quá hạn":            [0,            0,             0],
            "Dư nợ khoanh":             [0,            0,             0],
            "Mã chương trình":          ["4",          "4",           "4"],
        })
        result = danh_dau_khong_hd(df)
        flags = result["is_3m_inactive"].tolist()
        assert flags[0] is True   # KU001: ~119 ngày → đánh dấu
        assert flags[1] is False  # KU002: ~45 ngày → không đánh dấu
        assert flags[2] is False  # KU003: dư nợ = 0 → loại trừ


# ══════════════════════════════════════════════════════════════════════════════
# canh_bao_migration()
# ══════════════════════════════════════════════════════════════════════════════

class TestCanhBaoMigration:

    # ── Output structure ───────────────────────────────────────────────────

    def test_output_co_cac_cot_can_thiet(self):
        """Kết quả phải có muc_canh_bao và so_thang_ton_uoc."""
        df = _df_mig(lai_ton=300_000, lai_thang=100_000)
        result = canh_bao_migration(df)
        assert "muc_canh_bao" in result.columns
        assert "so_thang_ton_uoc" in result.columns

    def test_empty_df_khong_crash(self):
        """DataFrame rỗng → trả về empty DataFrame, không crash."""
        df = pd.DataFrame(columns=[
            "Số khế ước", "Tên KH", "Tên PGD", "Tên xã", "Tên ĐVUT",
            "Phân loại", "Lãi tồn TH", "Lãi DT trong tháng", "is_3m_inactive",
        ])
        result = canh_bao_migration(df)
        assert result.empty

    # ── Mức cảnh báo ──────────────────────────────────────────────────────

    def test_nguy_co_cao_so_thang_qua_2_5(self):
        """3.0 tháng (300k/100k) → mức đỏ 🔴."""
        df = _df_mig(lai_ton=300_000, lai_thang=100_000)
        result = canh_bao_migration(df)
        assert len(result) == 1
        assert "🔴" in result["muc_canh_bao"].iloc[0]

    def test_sap_chuyen_so_thang_2_den_2_4(self):
        """2.2 tháng (220k/100k) → mức vàng ⚠️."""
        df = _df_mig(lai_ton=220_000, lai_thang=100_000)
        result = canh_bao_migration(df)
        assert len(result) == 1
        assert "⚠️" in result["muc_canh_bao"].iloc[0]

    def test_so_thang_ton_uoc_chinh_xac(self):
        """so_thang_ton_uoc = lãi tồn / lãi tháng, làm tròn 1 chữ số thập phân."""
        df = _df_mig(lai_ton=250_000, lai_thang=100_000)  # 2.5 tháng
        result = canh_bao_migration(df)
        assert not result.empty
        assert abs(float(result["so_thang_ton_uoc"].iloc[0]) - 2.5) < 0.15

    # ── Điều kiện loại trừ ─────────────────────────────────────────────────

    def test_duoi_nguong_2_thang_khong_canh_bao(self):
        """1.5 tháng < ngưỡng 2.0 → không xuất hiện trong kết quả."""
        df = _df_mig(lai_ton=150_000, lai_thang=100_000)
        result = canh_bao_migration(df)
        assert result.empty

    def test_phan_loai_khac_E_bi_loai(self):
        """Phân loại != 'E' → không nằm trong kết quả cảnh báo."""
        df = _df_mig(phan_loai="B", lai_ton=300_000, lai_thang=100_000)
        result = canh_bao_migration(df)
        assert result.empty

    def test_da_la_khd_bi_loai(self):
        """Đã is_3m_inactive = True → không cảnh báo migration nữa."""
        df = _df_mig(lai_ton=300_000, lai_thang=100_000, is_3m_inactive=True)
        result = canh_bao_migration(df)
        assert result.empty

    def test_lai_ton_bang_0_khong_canh_bao(self):
        """Lãi tồn = 0 → chưa có dấu hiệu nguy cơ."""
        df = _df_mig(lai_ton=0, lai_thang=100_000)
        result = canh_bao_migration(df)
        assert result.empty

    def test_phan_loai_viet_thuong_va_khoang_trang(self):
        """Phân loại ' e ' (thường + khoảng trắng) vẫn nhận ra sau strip/upper."""
        df = _df_mig(phan_loai=" e ", lai_ton=300_000, lai_thang=100_000)
        result = canh_bao_migration(df)
        assert len(result) == 1

    # ── Multi-row ──────────────────────────────────────────────────────────

    def test_nhieu_dong_mixed_cap_do(self):
        """4 dòng: 1 đỏ, 1 vàng, 1 dưới ngưỡng, 1 không phải E."""
        df = pd.DataFrame({
            "Số khế ước":             ["KU001", "KU002", "KU003", "KU004"],
            "Tên KH":                 ["A",     "B",     "C",     "D"],
            "Tên PGD":                ["PGD"] * 4,
            "Tên xã":                 ["Xã A"] * 4,
            "Tên ĐVUT":               ["HPN"] * 4,
            "Phân loại":              ["E",     "E",     "E",     "B"],
            "Lãi tồn TH":             [300_000, 220_000, 100_000, 300_000],
            "Lãi DT trong tháng":     [100_000, 100_000, 100_000, 100_000],
            "is_3m_inactive":         [False,   False,   False,   False],
        })
        result = canh_bao_migration(df)
        # KU001: 3.0 tháng → đỏ; KU002: 2.2 tháng → vàng
        # KU003: 1.0 tháng → loại; KU004: phân loại B → loại
        assert len(result) == 2
        assert any("🔴" in m for m in result["muc_canh_bao"])
        assert any("⚠️" in m for m in result["muc_canh_bao"])

    def test_is_3m_inactive_auto_computed_khi_thieu(self):
        """is_3m_inactive không có trong input → tự tính, không crash."""
        df = pd.DataFrame({
            "Số khế ước":             ["KU001"],
            "Tên KH":                 ["A"],
            "Tên PGD":                ["PGD LT"],
            "Tên xã":                 ["Xã A"],
            "Tên ĐVUT":               ["HPN"],
            "Phân loại":              ["E"],
            "Lãi tồn TH":             [300_000],
            "Lãi DT trong tháng":     [100_000],
            # is_3m_inactive KHÔNG có — phải tự tính
        })
        result = canh_bao_migration(df)
        assert isinstance(result, pd.DataFrame)
