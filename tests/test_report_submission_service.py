"""Unit test cho services/report_submission_service.py — đổi tên loại BC."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from services import report_submission_service as svc


@pytest.fixture
def mock_kv():
    store: dict = {}

    def _doc(key, default=None):
        return store.get(key, default)

    def _ghi(key, value, username):
        store[key] = value

    with patch.object(svc.db, "doc_kv", side_effect=_doc), patch.object(
        svc.db, "ghi_kv", side_effect=_ghi
    ), patch.object(svc.db, "ghi_audit"):
        yield store


class TestPhatHienTenLechTen:
    def test_khop_exact_khong_bao(self, mock_kv):
        cfg = {"BC tháng 6": "2026-06-30"}
        gsheet = ["BC tháng 6"]
        assert svc.phat_hien_ten_lech_ten(cfg, gsheet) == []

    def test_khac_giai_doan_nam(self, mock_kv):
        cfg = {"RÀ SOÁT XÂY DỰNG KHTD 2023-2026": "2026-07-15"}
        gsheet = ["RÀ SOÁT XÂY DỰNG KHTD 2027-2030"]
        ds = svc.phat_hien_ten_lech_ten(cfg, gsheet)
        assert len(ds) == 1
        assert ds[0]["ten_theo_doi"] == "RÀ SOÁT XÂY DỰNG KHTD 2023-2026"
        assert ds[0]["ten_form"] == "RÀ SOÁT XÂY DỰNG KHTD 2027-2030"
        assert ds[0]["ly_do"] == "khac_giai_doan_nam"

    def test_khong_co_tren_form(self, mock_kv):
        cfg = {"BC nội bộ": "2026-06-30"}
        gsheet = ["BC khác"]
        ds = svc.phat_hien_ten_lech_ten(cfg, gsheet)
        assert len(ds) == 1
        assert ds[0]["ten_form"] == ""

    def test_goi_y_khi_ten_form_chen_them_cum_tu(self, mock_kv):
        cfg = {"RÀ SOÁT XÂY DỰNG KHTD 2023-2026": "2026-07-15"}
        gsheet = ["RÀ SOÁT XÂY DỰNG KHTD GIAI ĐOẠN 2027-2030"]
        ds = svc.phat_hien_ten_lech_ten(cfg, gsheet)
        assert len(ds) == 1
        assert ds[0]["ten_form"] == "RÀ SOÁT XÂY DỰNG KHTD GIAI ĐOẠN 2027-2030"
        assert ds[0]["ly_do"] == "gan_dung_ten_goc"


class TestDanhMucTheoDoi:
    def test_uu_tien_hien_ten_tren_form_khi_khac_giai_doan_nam(self, mock_kv):
        cfg = {"RÀ SOÁT XÂY DỰNG KHTD 2023-2026": "2026-07-15"}
        gsheet = ["RÀ SOÁT XÂY DỰNG KHTD 2027-2030", "BC khác"]

        dm = svc.xay_dung_danh_muc_theo_doi(cfg, gsheet)

        assert dm["tracked_to_display"]["RÀ SOÁT XÂY DỰNG KHTD 2023-2026"] == "RÀ SOÁT XÂY DỰNG KHTD 2027-2030"
        assert dm["display_to_tracked"]["RÀ SOÁT XÂY DỰNG KHTD 2027-2030"] == "RÀ SOÁT XÂY DỰNG KHTD 2023-2026"
        assert "RÀ SOÁT XÂY DỰNG KHTD 2027-2030" not in dm["ds_loai_chua_cai"]

    def test_gan_trang_thai_van_match_dung_ten_form(self, mock_kv):
        cfg = {"RÀ SOÁT XÂY DỰNG KHTD 2023-2026": "2026-07-15"}
        df = pd.DataFrame(
            [
                {
                    "thoi_gian": pd.Timestamp("2026-07-10"),
                    "ten_pgd": "PGD A",
                    "loai_bao_cao": "RÀ SOÁT XÂY DỰNG KHTD 2027-2030",
                    "file_dinh_kem": "https://example.com",
                }
            ]
        )

        out, _ = svc.gan_trang_thai(df, cfg)

        assert out.iloc[0]["_loai_theo_doi"] == "RÀ SOÁT XÂY DỰNG KHTD 2023-2026"
        assert out.iloc[0]["_loai_hien_thi"] == "RÀ SOÁT XÂY DỰNG KHTD 2027-2030"
        assert out.iloc[0]["tt"] == "dung_han"

    def test_hien_ten_form_khi_ten_moi_chen_them_cum_tu(self, mock_kv):
        cfg = {"RÀ SOÁT XÂY DỰNG KHTD 2023-2026": "2026-07-15"}
        gsheet = ["RÀ SOÁT XÂY DỰNG KHTD GIAI ĐOẠN 2027-2030"]

        dm = svc.xay_dung_danh_muc_theo_doi(cfg, gsheet)

        assert (
            dm["tracked_to_display"]["RÀ SOÁT XÂY DỰNG KHTD 2023-2026"]
            == "RÀ SOÁT XÂY DỰNG KHTD GIAI ĐOẠN 2027-2030"
        )
        assert (
            dm["display_to_tracked"]["RÀ SOÁT XÂY DỰNG KHTD GIAI ĐOẠN 2027-2030"]
            == "RÀ SOÁT XÂY DỰNG KHTD 2023-2026"
        )


class TestDoiTenLoaiTheoDoi:
    def test_doi_ten_thanh_cong(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {
            "RÀ SOÁT XÂY DỰNG KHTD 2023-2026": "2026-07-15",
            "BC khác": "2026-08-01",
        }
        mock_kv[svc.KV_MANUAL] = [
            {"pgd": "PGD A", "loai": "RÀ SOÁT XÂY DỰNG KHTD 2023-2026", "ghi_de": True},
        ]
        mock_kv[svc.KV_ALLOWLIST] = [
            "RÀ SOÁT XÂY DỰNG KHTD 2023-2026",
            "BC khác",
        ]

        kq = svc.doi_ten_loai_theo_doi(
            "RÀ SOÁT XÂY DỰNG KHTD 2023-2026",
            "RÀ SOÁT XÂY DỰNG KHTD 2027-2030",
            "admin_test",
        )

        assert kq["ok"] is True
        assert kq["so_manual_cap_nhat"] == 1
        assert kq["allowlist_cap_nhat"] is True

        cfg = mock_kv[svc.KV_DEADLINE]
        assert "RÀ SOÁT XÂY DỰNG KHTD 2023-2026" not in cfg
        assert cfg["RÀ SOÁT XÂY DỰNG KHTD 2027-2030"] == "2026-07-15"
        assert cfg["BC khác"] == "2026-08-01"

        manual = mock_kv[svc.KV_MANUAL][0]
        assert manual["loai"] == "RÀ SOÁT XÂY DỰNG KHTD 2027-2030"

        allow = mock_kv[svc.KV_ALLOWLIST]
        assert "RÀ SOÁT XÂY DỰNG KHTD 2027-2030" in allow
        assert "RÀ SOÁT XÂY DỰNG KHTD 2023-2026" not in allow

    def test_ten_moi_da_ton_tai(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {
            "Tên cũ": "2026-07-01",
            "Tên mới": "2026-08-01",
        }
        kq = svc.doi_ten_loai_theo_doi("Tên cũ", "Tên mới", "u")
        assert kq["ok"] is False
        assert "đã tồn tại" in kq["msg"].lower()

    def test_ten_cu_khong_ton_tai(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {"BC A": "2026-07-01"}
        kq = svc.doi_ten_loai_theo_doi("BC B", "BC C", "u")
        assert kq["ok"] is False

    def test_dong_bo_tat_ca_ten_theo_form(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {
            "RÀ SOÁT XÂY DỰNG KHTD 2023-2026": "2026-07-15",
            "BÁO CÁO KẾ HOẠCH 2024-2025": "2026-07-20",
        }

        kq = svc.dong_bo_tat_ca_ten_theo_form(
            mock_kv[svc.KV_DEADLINE],
            [
                "RÀ SOÁT XÂY DỰNG KHTD 2027-2030",
                "BÁO CÁO KẾ HOẠCH 2026-2027",
            ],
            "admin_test",
        )

        assert kq["so_doi"] == 2
        cfg = mock_kv[svc.KV_DEADLINE]
        assert "RÀ SOÁT XÂY DỰNG KHTD 2027-2030" in cfg
        assert "BÁO CÁO KẾ HOẠCH 2026-2027" in cfg


class TestBaoCaoDieuHanh:
    def test_lap_bang_nghia_vu_tinh_ca_don_vi_chua_co_dong_nop(self, mock_kv):
        cfg = {"BC tuần": "2026-07-15"}
        df = pd.DataFrame(
            [
                {
                    "thoi_gian": pd.Timestamp("2026-07-10"),
                    "ten_pgd": "PGD A",
                    "loai_bao_cao": "BC tuần",
                    "ky_bao_cao": "Tuần 28",
                    "file_dinh_kem": "https://example.com/a",
                }
            ]
        )

        df_nghia_vu, extra = svc.lap_bang_nghia_vu_bao_cao(
            df,
            cfg,
            ds_pgd_scope=["PGD A", "PGD B"],
        )

        assert len(df_nghia_vu) == 2
        assert extra["metrics"]["tong_nghia_vu"] == 2

        row_a = df_nghia_vu[df_nghia_vu["Đơn vị"] == "PGD A"].iloc[0]
        row_b = df_nghia_vu[df_nghia_vu["Đơn vị"] == "PGD B"].iloc[0]

        assert row_a["Mã trạng thái"] == "dung_han"
        assert bool(row_a["Hoàn thành"]) is True
        assert row_b["Mã trạng thái"] == "chua_nop"
        assert bool(row_b["Cần xử lý"]) is True

    def test_tong_hop_bao_cao_dieu_hanh_tach_thieu_file_khoi_da_hoan_thanh(self, mock_kv):
        cfg = {"BC tháng": "2026-07-15"}
        df = pd.DataFrame(
            [
                {
                    "thoi_gian": pd.Timestamp("2026-07-10"),
                    "ten_pgd": "PGD A",
                    "loai_bao_cao": "BC tháng",
                    "ky_bao_cao": "06/2026",
                    "file_dinh_kem": "",
                }
            ]
        )

        bao_cao = svc.tong_hop_bao_cao_dieu_hanh(
            df,
            cfg,
            ds_pgd_scope=["PGD A"],
        )

        assert len(bao_cao["df_chua_hoan_thanh"]) == 1
        assert bao_cao["metrics"]["so_thieu_file"] == 1
        assert bao_cao["metrics"]["da_hoan_thanh"] == 0
        assert bao_cao["df_chua_hoan_thanh"].iloc[0]["Mã trạng thái"] == "thieu_file"


class TestLuuTruBaoCao:
    def test_luu_tru_giu_du_lieu_gsheet_va_go_deadline(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {"BC tháng 6": "2026-07-15"}
        df = pd.DataFrame(
            [
                {
                    "thoi_gian": pd.Timestamp("2026-07-10"),
                    "ten_pgd": "PGD A",
                    "loai_bao_cao": "BC tháng 6",
                    "file_dinh_kem": "https://example.com/a",
                }
            ]
        )

        meta = svc.luu_tru_loai_bao_cao("BC tháng 6", "admin_test")

        assert meta["deadline_cu"] == "2026-07-15"
        assert mock_kv[svc.KV_DEADLINE] == {}
        assert "BC tháng 6" in mock_kv[svc.KV_ARCHIVE]
        assert svc.loc_du_lieu_luu_tru(df, archived=False).empty
        assert len(svc.loc_du_lieu_luu_tru(df, archived=True)) == 1

    def test_khoi_phuc_khong_tu_bat_lai_deadline_cu(self, mock_kv):
        mock_kv[svc.KV_ARCHIVE] = {
            "BC tháng 6": {
                "ten_hien_thi": "BC tháng 6",
                "ten_theo_doi": "BC tháng 6",
                "deadline_cu": "2026-07-15",
            }
        }
        mock_kv[svc.KV_DEADLINE] = {}

        assert svc.khoi_phuc_loai_bao_cao("BC tháng 6", "admin_test") is True
        assert mock_kv[svc.KV_ARCHIVE] == {}
        assert mock_kv[svc.KV_DEADLINE] == {}

    def test_telegram_bo_qua_deadline_luu_tru_con_sot(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {"BC tháng 6": "2026-07-15"}
        mock_kv[svc.KV_ARCHIVE] = {
            "BC tháng 6": {
                "ten_hien_thi": "BC tháng 6",
                "ten_theo_doi": "BC tháng 6",
            }
        }
        df = pd.DataFrame(
            [
                {
                    "thoi_gian": pd.Timestamp("2026-07-10"),
                    "ten_pgd": "PGD A",
                    "loai_bao_cao": "BC tháng 6",
                    "file_dinh_kem": "https://example.com/a",
                }
            ]
        )

        assert svc.lay_danh_sach_can_nhac(df=df) == []


class TestLayDanhSachCanNhacAllowlist:
    def test_allowlist_loc_dung_loai_bc(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {"BC A": "2026-07-15", "BC B": "2026-07-16"}
        df = pd.DataFrame([
            {"thoi_gian": pd.Timestamp("2026-07-10"), "ten_pgd": "PGD A", "loai_bao_cao": "BC A", "file_dinh_kem": "https://x.com"},
        ])

        ds = svc.lay_danh_sach_can_nhac(df=df, allowlist={"BC A"})
        assert len(ds) == 1
        assert ds[0]["loai"] == "BC A"

    def test_allowlist_loai_bo_bc_khong_trong_danh_sach(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {"BC A": "2026-07-15", "BC B": "2026-07-16"}
        df = pd.DataFrame([
            {"thoi_gian": pd.Timestamp("2026-07-10"), "ten_pgd": "PGD A", "loai_bao_cao": "BC A", "file_dinh_kem": "https://x.com"},
            {"thoi_gian": pd.Timestamp("2026-07-10"), "ten_pgd": "PGD B", "loai_bao_cao": "BC B", "file_dinh_kem": "https://x.com"},
        ])

        ds = svc.lay_danh_sach_can_nhac(df=df, allowlist={"BC A"})
        assert len(ds) == 1
        assert ds[0]["loai"] == "BC A"

    def test_allowlist_none_la_tat_ca(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {"BC A": "2026-07-15", "BC B": "2026-07-16"}
        df = pd.DataFrame([
            {"thoi_gian": pd.Timestamp("2026-07-10"), "ten_pgd": "PGD A", "loai_bao_cao": "BC A", "file_dinh_kem": "https://x.com"},
        ])

        ds = svc.lay_danh_sach_can_nhac(df=df, allowlist=None)
        assert len(ds) == 2  # Cả 2 loại đều cần nhắc

    def test_allowlist_rong_tra_rong(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {"BC A": "2026-07-15"}
        df = pd.DataFrame([
            {"thoi_gian": pd.Timestamp("2026-07-10"), "ten_pgd": "PGD A", "loai_bao_cao": "BC A", "file_dinh_kem": "https://x.com"},
        ])

        ds = svc.lay_danh_sach_can_nhac(df=df, allowlist=set())
        assert ds == []

    def test_allowlist_khong_anh_huong_loc_deadline_qua_han(self, mock_kv):
        mock_kv[svc.KV_DEADLINE] = {"BC A": "2026-07-15", "BC B": "2026-08-01"}
        df = pd.DataFrame([
            {"thoi_gian": pd.Timestamp("2026-07-10"), "ten_pgd": "PGD A", "loai_bao_cao": "BC A", "file_dinh_kem": "https://x.com"},
        ])

        ds = svc.lay_danh_sach_can_nhac(df=df, allowlist={"BC A", "BC B"})
        # BC B có deadline > 3 ngày, không cần nhắc
        assert len(ds) == 1
        assert ds[0]["loai"] == "BC A"
