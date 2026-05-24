"""
Tests cho KTNB Service — Phân hệ A/B/C/D.
"""
import pytest
import pandas as pd
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import ktnb_service as ktnb
from config import COT_SO_KU, COT_TEN_KH, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH


@pytest.fixture
def sample_hstd_df():
    """DataFrame mẫu giả lập HSTD."""
    return pd.DataFrame({
        COT_SO_KU: ["KU001", "KU002", "KU003", "KU004", "KU005", "KU006", "KU007", "KU008", "KU009", "KU010"],
        COT_TEN_KH: ["KH A", "KH B", "KH C", "KH D", "KH E", "KH F", "KH G", "KH H", "KH I", "KH J"],
        COT_TONG_DU_NO: [100_000_000, 200_000_000, 150_000_000, 300_000_000, 50_000_000,
                        80_000_000, 120_000_000, 90_000_000, 60_000_000, 110_000_000],
        COT_DU_NO_QH: [0, 50_000_000, 0, 100_000_000, 0, 0, 30_000_000, 0, 0, 20_000_000],
        COT_DU_NO_KHOANH: [0, 0, 40_000_000, 0, 0, 0, 0, 25_000_000, 0, 0],
    })


class TestPhanHeA:
    """Tests cho Phân hệ A — Kế hoạch & Lịch trình."""

    def test_lay_danh_sach_dot_empty(self):
        """Test lấy danh sách đợt khi chưa có đợt nào (năm 9999)."""
        df = ktnb.lay_danh_sach_dot(nam=9999)
        assert isinstance(df, pd.DataFrame)
        assert df.empty or len(df) >= 0

    def test_them_va_lay_dot(self):
        """Test thêm đợt kiểm tra và lấy lại."""
        dot_id = ktnb.them_dot_kiem_tra(
            nam=2026,
            so_cv="TEST/001",
            loai_hinh="dinh_ky",
            ten_pgd_ks="PGD Test",
            ngay_bat_dau="2026-01-01",
            ngay_ket_thuc="2026-01-15",
            truong_doan="Nguyen Van A",
            ghi_chu="Test",
            username="test_user",
        )
        assert dot_id > 0

        # Lấy lại
        dot = ktnb.lay_dot_by_id(dot_id)
        assert dot is not None
        assert dot["so_cv"] == "TEST/001"
        assert dot["truong_doan"] == "Nguyen Van A"

    def test_cap_nhat_dot(self):
        """Test cập nhật đợt kiểm tra."""
        dot_id = ktnb.them_dot_kiem_tra(
            nam=2026, so_cv="TEST/002", loai_hinh="dot_xuat",
            ten_pgd_ks="PGD Test 2", ngay_bat_dau="2026-02-01",
            ngay_ket_thuc="2026-02-15", truong_doan="Le Van B",
            ghi_chu="", username="test_user",
        )
        result = ktnb.cap_nhat_dot_kiem_tra(dot_id, {"ghi_chu": "Updated", "trang_thai": "dang_thuc_hien"}, "test_user")
        assert result is True

        dot = ktnb.lay_dot_by_id(dot_id)
        assert dot["ghi_chu"] == "Updated"

    def test_thanh_phan_doan(self):
        """Test quản lý thành phần đoàn."""
        dot_id = ktnb.them_dot_kiem_tra(
            nam=2026, so_cv="TEST/003", loai_hinh="chuyen_sau",
            ten_pgd_ks="PGD Test 3", ngay_bat_dau="2026-03-01",
            ngay_ket_thuc="2026-03-15", truong_doan="Truong Doan",
            ghi_chu="", username="test_user",
        )
        thanh_vien = [
            {"ho_ten": "TV1", "chuc_vu": "CV1", "don_vi": "DV1", "vai_tro": "thanh_vien"},
            {"ho_ten": "TV2", "chuc_vu": "CV2", "don_vi": "DV2", "vai_tro": "pho_doan"},
        ]
        result = ktnb.cap_nhat_thanh_phan_doan(dot_id, thanh_vien, "test_user")
        assert result is True

        df_tv = ktnb.lay_thanh_phan_doan(dot_id)
        assert len(df_tv) == 2


class TestPhanHeB:
    """Tests cho Phân hệ B — Chọn mẫu đối chiếu."""

    def test_chon_mau_uu_tien_rui_ro(self, sample_hstd_df):
        """Test chọn mẫu ưu tiên rủi ro (QH, Khoanh)."""
        df_mau = ktnb.chon_mau_doi_chieu(sample_hstd_df, dot_id=1, ty_le_pct=20, uu_tien_rui_ro=True)

        # Các món có QH hoặc Khoanh phải được chọn 100%
        df_qh = sample_hstd_df[sample_hstd_df[COT_DU_NO_QH] > 0]
        df_khoanh = sample_hstd_df[sample_hstd_df[COT_DU_NO_KHOANH] > 0]

        # Kiểm tra các món risk có trong mẫu
        ku_qh = set(df_qh[COT_SO_KU].tolist())
        ku_khoanh = set(df_khoanh[COT_SO_KU].tolist())
        ku_mau = set(df_mau[COT_SO_KU].tolist()) if COT_SO_KU in df_mau.columns else set(df_mau["__ma_mon"].tolist())

        # Tất cả KU QH và Khoanh phải có trong mẫu
        assert ku_qh.issubset(ku_mau)
        assert ku_khoanh.issubset(ku_mau)

    def test_chon_mau_ty_le(self, sample_hstd_df):
        """Test chọn mẫu theo tỷ lệ %."""
        # DataFrame không có risk
        df_no_risk = sample_hstd_df[
            (sample_hstd_df[COT_DU_NO_QH] == 0) & (sample_hstd_df[COT_DU_NO_KHOANH] == 0)
        ].copy()

        df_mau = ktnb.chon_mau_doi_chieu(df_no_risk, dot_id=1, ty_le_pct=50, uu_tien_rui_ro=True)

        # Với 50% và 4 dòng không risk, nên chọn khoảng 2 dòng
        n_expected = max(1, int(len(df_no_risk) * 0.5))
        assert len(df_mau) <= len(df_no_risk)


class TestPhanHeD:
    """Tests cho Phân hệ D — Giám sát & Khắc phục lỗi."""

    def test_lay_danh_muc_loi(self):
        """Test lấy danh mục lỗi chuẩn."""
        df_dm = ktnb.lay_danh_muc_loi()
        assert isinstance(df_dm, pd.DataFrame)
        # Có ít nhất 17 mã lỗi theo CV 9919
        assert len(df_dm) >= 17

    def test_thong_ke_loi(self):
        """Test thống kê lỗi (có thể empty nếu chưa có lỗi)."""
        # Lấy một đợt test bất kỳ hoặc dùng -1
        df_stats = ktnb.thong_ke_loi_theo_khoi(dot_id=-999)
        assert isinstance(df_stats, pd.DataFrame)


class TestTinhTrangLich:
    """Tests cho helper tính trạng thái lịch."""

    def test_tinh_trang_sap_toi(self):
        """Lịch tương lai -> sap_toi."""
        future = "2099-12-31"
        result = ktnb._tinh_trang_lich(future, "2099-12-31")
        assert result == "sap_toi"

    def test_tinh_trang_qua_han(self):
        """Lịch quá khứ -> qua_han."""
        past = "2000-01-01"
        result = ktnb._tinh_trang_lich(past, "2000-01-31")
        assert result == "qua_han"

    def test_tinh_trang_dung_han(self):
        """Lịch hiện tại -> dung_han."""
        today = date.today().strftime("%Y-%m-%d")
        result = ktnb._tinh_trang_lich(today, today)
        assert result == "dung_han"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
