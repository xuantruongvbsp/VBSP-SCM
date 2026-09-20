"""
tests/test_bom_snapshot_ky_cu.py
────────────────────────────────
Test 3 hàm snapshot mới trong services/upload_service.py:
  • bom_snapshot_ky_cu()              — bơm HSTD/Thôn/Ủy thác kỳ cũ
  • bom_snapshot_cdtotkvv_ky_cu()     — bơm CDTOTKVV/CBTD–Tổ kỳ cũ
  • chay_lai_snapshot_ky_hien_tai()   — chạy lại toàn bộ snapshot kỳ hiện tại

Chiến lược: mock các phụ thuộc nặng (đọc Excel/parquet, hàm ghi snapshot, db,
streamlit) rồi kiểm tra LUỒNG ĐIỀU PHỐI:
  - đúng kỳ được truyền xuống hàm snapshot
  - đúng bảng được ghi / bỏ qua theo điều kiện
  - KetQuaUpload.thanh_cong đúng
  - audit được ghi
  - KHÔNG ghi đè cache/hstd.parquet (chỉ đọc)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import services.upload_service as upload_service
from services.upload_service import (
    KetQuaUpload,
    bom_snapshot_ky_cu,
    bom_snapshot_cdtotkvv_ky_cu,
    chay_lai_snapshot_ky_hien_tai,
    tao_snapshot_cdtotkvv_theo_thang,
)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _df_nho() -> pd.DataFrame:
    return pd.DataFrame({
        "Ma_KH": ["KH1"],
        "Tong_du_no": [1_000],
        "Ngày số liệu": ["31/07/2026"],
    })


def _kq(ok: bool = True, msg: str = "ok") -> KetQuaUpload:
    return KetQuaUpload(ok, msg)


def _patch_cache_dir(tmp_path):
    """Trỏ CACHE_DIR về tmp để file tạm không lẫn vào cache thật."""
    return patch.object(upload_service, "CACHE_DIR", str(tmp_path))


# ══════════════════════════════════════════════════════════════════════════════
# bom_snapshot_ky_cu  (HSTD)
# ══════════════════════════════════════════════════════════════════════════════
class TestBomSnapshotKyCu:
    @pytest.fixture(autouse=True)
    def _mot_don_vi_bat_buoc(self, monkeypatch):
        monkeypatch.setattr(upload_service, "DON_VI_CHI_NHANH", "PGD A")
        monkeypatch.setattr(upload_service, "DS_PGD", [])

    def test_ky_sai_tra_ve_that_bai(self):
        with patch("snapshot_service.luu_snapshot") as m_snap:
            kq = bom_snapshot_ky_cu("2026-13", {"PGD A": "/x.xlsx"})
        assert kq.thanh_cong is False
        assert "không hợp lệ" in kq.thong_bao.lower()
        m_snap.assert_not_called()

    def test_loai_khong_hstd_bi_tu_choi(self):
        kq = bom_snapshot_ky_cu("2026-07", {"PGD A": "/x.xlsx"}, loai="nq11")
        assert kq.thanh_cong is False
        assert "chỉ hỗ trợ HSTD" in kq.thong_bao

    def test_files_rong_tra_ve_that_bai(self):
        kq = bom_snapshot_ky_cu("2026-07", {})
        assert kq.thanh_cong is False
        assert "Chưa có file" in kq.thong_bao

    def test_bom_thanh_cong_tu_duong_dan(self, tmp_path):
        """File dạng đường dẫn (str) → đọc → ghi snapshot đúng kỳ → audit."""
        src = tmp_path / "f.xlsx"
        src.write_bytes(b"dummy")  # hàm thật copyfile nguồn → tmp trước khi đọc
        with (
            _patch_cache_dir(tmp_path),
            patch.object(upload_service, "_doc_excel_pgd_thanh_df", return_value=_df_nho()) as m_doc,
            patch.object(upload_service, "_normalize_merge_dataframe_for_parquet", side_effect=lambda d: d),
            patch("snapshot_service.luu_snapshot", return_value=_kq()) as m_hstd,
            patch("snapshot_service.luu_thon_snapshot", return_value=_kq()) as m_thon,
            patch("snapshot_service.luu_uy_thac_snapshot", return_value=_kq()) as m_ut,
            patch("snapshot_service.doc_thon_snapshot", return_value=_df_nho()),
            patch("snapshot_service.snapshot_la_cuoi_thang", return_value=True),
            patch.object(upload_service.db, "ghi_audit") as m_audit,
            patch("services.upload_service.st.cache_data.clear"),
        ):
            kq = bom_snapshot_ky_cu("2026-07", {"PGD A": str(src)}, "tester")

        assert kq.thanh_cong is True
        m_doc.assert_called_once()
        # đúng kỳ được truyền xuống cả 3 hàm snapshot
        assert m_hstd.call_args.kwargs["ky"] == "2026-07"
        assert m_thon.call_args.kwargs["ky"] == "2026-07"
        assert m_ut.call_args.kwargs["ky"] == "2026-07"
        # audit ghi đúng action
        assert m_audit.call_args.args[1] == "bom_snapshot_ky_cu"
        assert "Đã bơm snapshot kỳ" in kq.thong_bao
        assert "HSTD ✅" in kq.thong_bao

    def test_bom_tu_bytes_ghi_va_don_file_tam(self, tmp_path):
        """File dạng bytes → ghi tạm → đọc → dọn file tạm trong finally."""
        with (
            _patch_cache_dir(tmp_path),
            patch.object(upload_service, "_doc_excel_pgd_thanh_df", return_value=_df_nho()),
            patch.object(upload_service, "_normalize_merge_dataframe_for_parquet", side_effect=lambda d: d),
            patch("snapshot_service.luu_snapshot", return_value=_kq()),
            patch("snapshot_service.luu_thon_snapshot", return_value=_kq()),
            patch("snapshot_service.luu_uy_thac_snapshot", return_value=_kq()),
            patch("snapshot_service.doc_thon_snapshot", return_value=_df_nho()),
            patch("snapshot_service.snapshot_la_cuoi_thang", return_value=True),
            patch.object(upload_service.db, "ghi_audit"),
            patch("services.upload_service.st.cache_data.clear"),
        ):
            kq = bom_snapshot_ky_cu("2026-07", {"PGD A": b"PK\x03\x04dummy"}, "tester")

        assert kq.thanh_cong is True
        # thư mục tạm được dọn sạch
        tmp_bom = Path(upload_service.CACHE_DIR) / "tmp_bom_ky_cu"
        assert not any(tmp_bom.glob("*")) if tmp_bom.exists() else True

    def test_snapshot_lan_danh_duoc_ghi_nhan(self, tmp_path):
        """Một loại snapshot fail → ket_qua.thanh_cong False nhưng audit vẫn ghi."""
        src = tmp_path / "f.xlsx"
        src.write_bytes(b"dummy")
        with (
            _patch_cache_dir(tmp_path),
            patch.object(upload_service, "_doc_excel_pgd_thanh_df", return_value=_df_nho()),
            patch.object(upload_service, "_normalize_merge_dataframe_for_parquet", side_effect=lambda d: d),
            patch("snapshot_service.luu_snapshot", return_value=_kq(False, "lỗi HSTD")),
            patch("snapshot_service.luu_thon_snapshot", return_value=_kq()),
            patch("snapshot_service.luu_uy_thac_snapshot", return_value=_kq()),
            patch("snapshot_service.doc_thon_snapshot", return_value=_df_nho()),
            patch("snapshot_service.snapshot_la_cuoi_thang", return_value=True),
            patch.object(upload_service.db, "ghi_audit") as m_audit,
            patch("services.upload_service.st.cache_data.clear"),
        ):
            kq = bom_snapshot_ky_cu("2026-07", {"PGD A": str(src)}, "tester")

        assert kq.thanh_cong is False
        assert "HSTD ❌" in kq.thong_bao
        m_audit.assert_called_once()

    def test_khong_doc_duoc_file_nao(self, tmp_path):
        src = tmp_path / "f.xlsx"
        src.write_bytes(b"dummy")
        with (
            _patch_cache_dir(tmp_path),
            patch.object(upload_service, "_doc_excel_pgd_thanh_df", side_effect=ValueError("sai mẫu")),
            patch.object(upload_service.db, "ghi_audit"),
            patch("services.upload_service.st.cache_data.clear"),
        ):
            kq = bom_snapshot_ky_cu("2026-07", {"PGD A": str(src)}, "tester")
        assert kq.thanh_cong is False
        assert "Chưa ghi snapshot" in kq.thong_bao

    def test_thieu_don_vi_bi_chan_truoc_khi_doc_va_ghi(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_service, "DS_PGD", ["PGD B"])
        src = tmp_path / "f.xlsx"
        src.write_bytes(b"dummy")
        with (
            _patch_cache_dir(tmp_path),
            patch.object(upload_service, "_doc_excel_pgd_thanh_df") as m_doc,
            patch("snapshot_service.luu_snapshot") as m_hstd,
        ):
            kq = bom_snapshot_ky_cu("2026-07", {"PGD A": str(src)}, "tester")

        assert kq.thanh_cong is False
        assert "thiếu 1 đơn vị: PGD B" in kq.thong_bao
        m_doc.assert_not_called()
        m_hstd.assert_not_called()

    def test_sai_ngay_so_lieu_bi_chan_truoc_khi_ghi(self, tmp_path):
        src = tmp_path / "f.xlsx"
        src.write_bytes(b"dummy")
        df_sai_ngay = _df_nho().assign(**{"Ngày số liệu": "30/07/2026"})
        with (
            _patch_cache_dir(tmp_path),
            patch.object(upload_service, "_doc_excel_pgd_thanh_df", return_value=df_sai_ngay),
            patch("snapshot_service.luu_snapshot") as m_hstd,
            patch.object(upload_service.db, "ghi_audit"),
        ):
            kq = bom_snapshot_ky_cu("2026-07", {"PGD A": str(src)}, "tester")

        assert kq.thanh_cong is False
        assert "yêu cầu 31/07/2026" in kq.thong_bao
        m_hstd.assert_not_called()

    def test_uy_thac_loi_thi_toan_bo_ket_qua_bao_that_bai(self, tmp_path):
        src = tmp_path / "f.xlsx"
        src.write_bytes(b"dummy")
        with (
            _patch_cache_dir(tmp_path),
            patch.object(upload_service, "_doc_excel_pgd_thanh_df", return_value=_df_nho()),
            patch.object(upload_service, "_normalize_merge_dataframe_for_parquet", side_effect=lambda d: d),
            patch("snapshot_service.luu_snapshot", return_value=_kq()),
            patch("snapshot_service.luu_thon_snapshot", return_value=_kq()),
            patch("snapshot_service.luu_uy_thac_snapshot", return_value=_kq(False, "lỗi ủy thác")),
            patch("snapshot_service.doc_thon_snapshot", return_value=_df_nho()),
            patch("snapshot_service.snapshot_la_cuoi_thang", return_value=True),
            patch.object(upload_service.db, "ghi_audit"),
        ):
            kq = bom_snapshot_ky_cu("2026-07", {"PGD A": str(src)}, "tester")

        assert kq.thanh_cong is False
        assert "Ủy thác ❌" in kq.thong_bao


# ══════════════════════════════════════════════════════════════════════════════
# bom_snapshot_cdtotkvv_ky_cu  (Tổ TK&VV)
# ══════════════════════════════════════════════════════════════════════════════
class TestBomSnapshotCdtotkvvKyCu:
    def test_ky_sai_tra_ve_that_bai(self):
        with patch("snapshot_service.luu_cdtotkvv_snapshot") as m:
            kq = bom_snapshot_cdtotkvv_ky_cu("abc", [b"x"])
        assert kq.thanh_cong is False
        m.assert_not_called()

    def test_files_rong_tra_ve_that_bai(self):
        kq = bom_snapshot_cdtotkvv_ky_cu("2026-07", [])
        assert kq.thanh_cong is False
        assert "Chưa có file" in kq.thong_bao

    def test_file_toan_cn_tach_duoc_ghi_ca_hai_bang(self, tmp_path):
        """File toàn CN → tach → đọc → ghi CDTOTKVV + CBTD–Tổ (có CBTD)."""
        with (
            _patch_cache_dir(tmp_path),
            patch("data.cdtotkvv.tach_file_cdto_toan_cn", return_value={"PGD A": b"sub"}),
            patch("data.cdtotkvv.doc_cdtotkvv_path", return_value=_df_nho()),
            patch("data.core.ts_file", return_value=0),
            patch("data.khtd.doc_cbtd", return_value={"CB1": {"ten_cbtd": "X"}}),
            patch.object(upload_service.db, "doc_dgd_map", return_value={}),
            patch("snapshot_service.luu_cdtotkvv_snapshot", return_value=_kq()) as m_cdto,
            patch("snapshot_service.luu_cbtd_to_tkvv_snapshot", return_value=_kq()) as m_tot,
            patch.object(upload_service.db, "ghi_audit") as m_audit,
        ):
            kq = bom_snapshot_cdtotkvv_ky_cu("2026-07", {"toan_cn.xlsx": b"PK\x03\x04"}, "tester")

        assert kq.thanh_cong is True
        m_cdto.assert_called_once()
        # CBTD–Tổ được ghi vì có hồ sơ CBTD
        m_tot.assert_called_once()
        assert m_audit.call_args.args[1] == "bom_snapshot_cdtotkvv_ky_cu"

    def test_file_per_unit_fallback_khi_tach_loi(self, tmp_path):
        """tach_file_cdto_toan_cn raise → fallback đọc trực tiếp file per-unit."""
        with (
            _patch_cache_dir(tmp_path),
            patch("data.cdtotkvv.tach_file_cdto_toan_cn", side_effect=ValueError("không phải toàn CN")),
            patch("data.cdtotkvv.doc_cdtotkvv_path", return_value=_df_nho()) as m_doc,
            patch("data.core.ts_file", return_value=0),
            patch("data.khtd.doc_cbtd", return_value={"CB1": {}}),
            patch.object(upload_service.db, "doc_dgd_map", return_value={}),
            patch("snapshot_service.luu_cdtotkvv_snapshot", return_value=_kq()),
            patch("snapshot_service.luu_cbtd_to_tkvv_snapshot", return_value=_kq()),
            patch.object(upload_service.db, "ghi_audit"),
        ):
            kq = bom_snapshot_cdtotkvv_ky_cu("2026-07", {"dv.xlsx": b"PK\x03\x04"}, "tester")

        assert kq.thanh_cong is True
        m_doc.assert_called_once()  # đọc trực tiếp bytes đã ghi tạm

    def test_chua_co_cbtd_bo_qua_snapshot_to(self, tmp_path):
        """doc_cbtd rỗng → KHÔNG ghi CBTD–Tổ, msg cảnh báo."""
        with (
            _patch_cache_dir(tmp_path),
            patch("data.cdtotkvv.tach_file_cdto_toan_cn", return_value={"PGD A": b"sub"}),
            patch("data.cdtotkvv.doc_cdtotkvv_path", return_value=_df_nho()),
            patch("data.core.ts_file", return_value=0),
            patch("data.khtd.doc_cbtd", return_value={}),
            patch.object(upload_service.db, "doc_dgd_map", return_value={}),
            patch("snapshot_service.luu_cdtotkvv_snapshot", return_value=_kq()),
            patch("snapshot_service.luu_cbtd_to_tkvv_snapshot") as m_tot,
            patch.object(upload_service.db, "ghi_audit"),
        ):
            kq = bom_snapshot_cdtotkvv_ky_cu("2026-07", {"f.xlsx": b"PK\x03\x04"}, "tester")

        assert kq.thanh_cong is True  # CDTOTKVV vẫn thành công
        m_tot.assert_not_called()
        assert "Chưa có hồ sơ CBTD" in kq.thong_bao

    def test_khong_doc_duoc_du_lieu(self, tmp_path):
        with (
            _patch_cache_dir(tmp_path),
            patch("data.cdtotkvv.tach_file_cdto_toan_cn", side_effect=ValueError("x")),
            patch("data.cdtotkvv.doc_cdtotkvv_path", side_effect=ValueError("sai mẫu")),
            patch("data.core.ts_file", return_value=0),
            patch.object(upload_service.db, "ghi_audit"),
        ):
            kq = bom_snapshot_cdtotkvv_ky_cu("2026-07", {"f.xlsx": b"PK\x03\x04"}, "tester")
        assert kq.thanh_cong is False
        assert "Không đọc được dữ liệu CDTOTKVV" in kq.thong_bao


# ══════════════════════════════════════════════════════════════════════════════
# tao_snapshot_cdtotkvv_theo_thang
# ══════════════════════════════════════════════════════════════════════════════
class TestTaoSnapshotCdtotkvvTheoThang:
    def test_chi_ghi_khi_du_don_vi_va_dung_ky_cdto(self):
        df = pd.DataFrame({"ten_dv": ["Hội sở", "PGD A"]})
        with (
            patch.object(upload_service, "DON_VI_CHI_NHANH", "Hội sở"),
            patch.object(upload_service, "DS_PGD", ["PGD A"]),
            patch("data.cdtotkvv.doc_cdtotkvv", return_value=df) as m_doc,
            patch("services.file_detection_service.ten_doc_ve_don_vi_chuan", side_effect=lambda x: x),
            patch("data.khtd.doc_cbtd", return_value={"CB01": {}}),
            patch.object(upload_service.db, "doc_dgd_map", return_value={}),
            patch("snapshot_service.luu_cdtotkvv_snapshot", return_value=_kq()) as m_cdto,
            patch("snapshot_service.luu_cbtd_to_tkvv_snapshot", return_value=_kq()) as m_cbtd,
        ):
            result = tao_snapshot_cdtotkvv_theo_thang("08/2026", "tester")

        assert result.thanh_cong is True
        m_doc.clear.assert_called_once_with()
        assert m_cdto.call_args.args[1:] == ("2026-08", "tester")
        assert m_cbtd.call_args.args[3:] == ("2026-08", "tester")

    def test_thieu_don_vi_khong_ghi_de_snapshot_cu(self):
        df = pd.DataFrame({"ten_dv": ["Hội sở"]})
        with (
            patch.object(upload_service, "DON_VI_CHI_NHANH", "Hội sở"),
            patch.object(upload_service, "DS_PGD", ["PGD A"]),
            patch("data.cdtotkvv.doc_cdtotkvv", return_value=df),
            patch("services.file_detection_service.ten_doc_ve_don_vi_chuan", side_effect=lambda x: x),
            patch("snapshot_service.luu_cdtotkvv_snapshot") as m_cdto,
        ):
            result = tao_snapshot_cdtotkvv_theo_thang("08/2026", "tester")

        assert result.thanh_cong is False
        assert "thiếu 1/22 đơn vị" in result.thong_bao
        m_cdto.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# chay_lai_snapshot_ky_hien_tai
# ══════════════════════════════════════════════════════════════════════════════
class TestChayLaiSnapshotKyHienTai:
    def test_cache_khong_ton_tai(self, tmp_path):
        with patch.object(upload_service, "CACHE_HSTD", str(tmp_path / "khong_ton_tai.parquet")):
            kq = chay_lai_snapshot_ky_hien_tai("tester")
        assert kq.thanh_cong is False
        assert "Chưa có cache HSTD" in kq.thong_bao

    def test_cache_rong(self, tmp_path):
        cache = tmp_path / "hstd.parquet"
        cache.write_bytes(b"dummy")
        with (
            patch.object(upload_service, "CACHE_HSTD", str(cache)),
            patch.object(upload_service.pd, "read_parquet", return_value=pd.DataFrame()),
        ):
            kq = chay_lai_snapshot_ky_hien_tai("tester")
        assert kq.thanh_cong is False
        assert "rỗng" in kq.thong_bao

    def test_chay_thanh_cong_dung_ky_tu_cache(self, tmp_path):
        cache = tmp_path / "hstd.parquet"
        cache.write_bytes(b"dummy")
        with (
            patch.object(upload_service, "CACHE_HSTD", str(cache)),
            patch.object(upload_service.pd, "read_parquet", return_value=_df_nho()),
            patch("snapshot_service._ky_tu_df", return_value="2026-08"),
            patch("snapshot_service.luu_snapshot", return_value=_kq()) as m_hstd,
            patch("snapshot_service.luu_thon_snapshot", return_value=_kq()) as m_thon,
            patch("snapshot_service.luu_uy_thac_snapshot", return_value=_kq()) as m_ut,
            patch("data.cdtotkvv.doc_cdtotkvv_toan_cn_pgd", return_value=pd.DataFrame()),
            patch.object(upload_service.db, "ghi_audit") as m_audit,
            patch("services.upload_service.st.cache_data.clear"),
        ):
            progress = MagicMock()
            kq = chay_lai_snapshot_ky_hien_tai("tester", progress_cb=progress)

        assert kq.thanh_cong is True
        assert m_hstd.call_args.kwargs["ky"] == "2026-08"
        assert m_thon.call_args.kwargs["ky"] == "2026-08"
        assert m_ut.call_args.kwargs["ky"] == "2026-08"
        assert m_audit.call_args.args[1] == "chay_lai_snapshot_ky_hien_tai"
        progress.assert_called()  # có cập nhật tiến độ

    def test_snapshot_loi_tra_ve_false_va_audit(self, tmp_path):
        cache = tmp_path / "hstd.parquet"
        cache.write_bytes(b"dummy")
        with (
            patch.object(upload_service, "CACHE_HSTD", str(cache)),
            patch.object(upload_service.pd, "read_parquet", return_value=_df_nho()),
            patch("snapshot_service._ky_tu_df", return_value="2026-08"),
            patch("snapshot_service.luu_snapshot", side_effect=RuntimeError("lỗi DB")),
            patch.object(upload_service.db, "ghi_audit") as m_audit,
            patch("services.upload_service.st.cache_data.clear"),
        ):
            kq = chay_lai_snapshot_ky_hien_tai("tester")

        assert kq.thanh_cong is False
        assert "Lỗi chạy lại snapshot" in kq.thong_bao
        assert m_audit.call_args.args[1] == "chay_lai_snapshot_loi"
