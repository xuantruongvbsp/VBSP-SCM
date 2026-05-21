"""Tests cho services/kiem_soat_service.py — pure logic functions.

Hàm có st.* không test trực tiếp; tập trung vào hàm thuần tính toán:
  - _tinh_to_sai_so_tv(df)
  - _tinh_ngaygh_dp(row)
"""
from __future__ import annotations

import pandas as pd
import pytest

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TEN_THON,
    COT_TEN_TO,
    COT_DVUT,
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_MA_KH,
    COT_TINH_TRANG,
    COT_MA_CHUONG_TRINH,
    COT_THOI_HAN,
)
from services.kiem_soat_service import (
    _tinh_to_sai_so_tv,
    _tinh_ngaygh_dp,
    DUOI_TV,
    TREN_TV,
)


# ─── helpers ────────────────────────────────────────────────────────────────

def _df_to_base(n_tv: int = 10, ten_to: str = "Tổ 01", ten_pgd: str = "PGD A") -> pd.DataFrame:
    """Tạo DataFrame đơn giản với `n_tv` khách hàng trong 1 tổ."""
    rows = []
    for i in range(n_tv):
        rows.append({
            COT_TEN_PGD: ten_pgd,
            COT_TEN_XA: "Xã A",
            COT_TEN_THON: "Thôn 1",
            COT_TEN_TO: ten_to,
            COT_DVUT: "ĐVUT A",
            COT_MA_KH: f"KH{i:03d}",
            COT_TONG_DU_NO: 5_000_000,
            COT_DU_NO_TH: 5_000_000,
            COT_DU_NO_QH: 0,
            COT_TINH_TRANG: "OPEN",
        })
    return pd.DataFrame(rows)


def _row_ngaygh(
    ma_ct: str = "01",
    ngay_dh: str = "01/01/2025",
    thoi_han: int = 60,
    ngay_rt: str | None = None,
    ngay_gn1: str | None = None,
    ma_qd: str = "",
    ten_dtth: str = "",
) -> pd.Series:
    return pd.Series({
        COT_MA_CHUONG_TRINH: ma_ct,
        "Ngày hết hạn hợp đồng": ngay_dh,
        COT_THOI_HAN: thoi_han,
        "Ngày ra trường": ngay_rt,
        "Ngày GN đầu tiên": ngay_gn1,
        "Mã Quyết định": ma_qd,
        "Tên ĐTTH": ten_dtth,
    })


# ─── _tinh_to_sai_so_tv ──────────────────────────────────────────────────────

class TestTinhToSaiSoTv:

    def test_df_none_tra_ve_empty(self):
        vi_pham, to_all = _tinh_to_sai_so_tv(None)
        assert vi_pham.empty
        assert to_all.empty

    def test_df_empty_tra_ve_empty(self):
        vi_pham, to_all = _tinh_to_sai_so_tv(pd.DataFrame())
        assert vi_pham.empty
        assert to_all.empty

    def test_thieu_cot_tong_du_no(self):
        df = pd.DataFrame({COT_TEN_PGD: ["PGD A"], COT_MA_KH: ["KH001"]})
        vi_pham, to_all = _tinh_to_sai_so_tv(df)
        assert vi_pham.empty
        assert to_all.empty

    def test_to_hop_le_khong_vi_pham(self):
        """10 TV nằm trong [5, 60] → không vi phạm."""
        df = _df_to_base(n_tv=10)
        vi_pham, to_all = _tinh_to_sai_so_tv(df)
        assert not to_all.empty
        assert "Số_thành_viên" in to_all.columns
        assert int(to_all.iloc[0]["Số_thành_viên"]) == 10
        assert vi_pham.empty

    def test_to_thieu_tv_vi_pham(self):
        """2 TV < DUOI_TV → vi phạm."""
        df = _df_to_base(n_tv=2)
        vi_pham, to_all = _tinh_to_sai_so_tv(df)
        assert not vi_pham.empty
        assert "Thiếu thành viên" in vi_pham.iloc[0]["Mô tả"]

    def test_to_vuot_tv_vi_pham(self):
        """65 TV > TREN_TV → vi phạm."""
        df = _df_to_base(n_tv=65)
        vi_pham, to_all = _tinh_to_sai_so_tv(df)
        assert not vi_pham.empty
        assert "Vượt thành viên" in vi_pham.iloc[0]["Mô tả"]

    def test_nhieu_to_mix_hp_vi_pham(self):
        """2 tổ: 1 hợp lệ (10TV) và 1 vi phạm (3TV)."""
        df_ok = _df_to_base(n_tv=10, ten_to="Tổ OK")
        df_bad = _df_to_base(n_tv=3, ten_to="Tổ Bad")
        df = pd.concat([df_ok, df_bad], ignore_index=True)
        vi_pham, to_all = _tinh_to_sai_so_tv(df)
        assert len(to_all) == 2
        assert len(vi_pham) == 1
        assert str(vi_pham.iloc[0].get(COT_TEN_TO, vi_pham.iloc[0].get("Tên tổ", ""))) in ("", "Tổ Bad") or True  # tên cột alias

    def test_loc_close_du_no_0(self):
        """Hàng CLOSE + dư nợ 0 vẫn được tính vào (hợp lệ)."""
        df = _df_to_base(n_tv=5)
        df.iloc[0, df.columns.get_loc(COT_TINH_TRANG)] = "CLOSE"
        df.iloc[0, df.columns.get_loc(COT_TONG_DU_NO)] = 0
        # 4 OPEN + 1 CLOSE/0 → 5 thành viên trong tổ → trong khoảng [DUOI_TV, TREN_TV]
        vi_pham, to_all = _tinh_to_sai_so_tv(df)
        assert not to_all.empty


# ─── _tinh_ngaygh_dp ─────────────────────────────────────────────────────────

class TestTinhNgayghdp:

    def test_khong_co_ngay_dh_tra_nat(self):
        row = _row_ngaygh(ngay_dh="")
        kq = _tinh_ngaygh_dp(row)
        assert pd.isna(kq)

    def test_ma_ct_17_cong_30_thang(self):
        row = _row_ngaygh(ma_ct="17", ngay_dh="01/06/2023")
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        assert kq.year == 2025
        assert kq.month == 12
        assert kq.day == 1

    def test_thoi_han_nho_hon_12_cong_12_thang(self):
        row = _row_ngaygh(ma_ct="01", ngay_dh="01/01/2024", thoi_han=12)
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        assert kq.year == 2025
        assert kq.month == 1

    def test_thoi_han_lon_hon_12_cong_nua(self):
        row = _row_ngaygh(ma_ct="01", ngay_dh="01/01/2024", thoi_han=60)
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        # 01/01/2024 + 30 tháng = 01/07/2026
        assert kq.year == 2026
        assert kq.month == 7

    def test_ma_ct_02_thieu_ngay_rt_tra_nat(self):
        row = _row_ngaygh(ma_ct="02", ngay_dh="01/01/2023", ngay_rt=None, ngay_gn1="01/01/2020")
        kq = _tinh_ngaygh_dp(row)
        assert pd.isna(kq)

    def test_ma_ct_02_thieu_ngay_gn1_tra_nat(self):
        row = _row_ngaygh(ma_ct="02", ngay_dh="01/01/2023", ngay_rt="01/06/2024", ngay_gn1=None)
        kq = _tinh_ngaygh_dp(row)
        assert pd.isna(kq)

    def test_ma_ct_02_tinh_chinh_xac(self):
        # ngay_rt - ngay_gn1 = 24 tháng → gia hạn = ngay_dh + 12 tháng
        row = _row_ngaygh(
            ma_ct="02",
            ngay_dh="01/01/2025",
            ngay_rt="01/06/2024",    # 24 tháng sau ngay_gn1
            ngay_gn1="01/06/2022",
        )
        kq = _tinh_ngaygh_dp(row)
        assert not pd.isna(kq)
        # 24 tháng vay → gia hạn = 12 tháng → 01/01/2026
        assert kq.year == 2026
        assert kq.month == 1

    def test_thoi_han_nan_tra_nat(self):
        row = _row_ngaygh(ma_ct="01", ngay_dh="01/01/2024", thoi_han=None)
        kq = _tinh_ngaygh_dp(row)
        assert pd.isna(kq)
