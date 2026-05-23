"""tests/test_migration_service.py — services/migration_service.py

Kiểm tra:
  - _nhan_nhom_no()    — chuẩn hoá phân loại về 4 nhóm
  - danh_sach_ky()     — liệt kê kỳ từ file parquet
  - doc_snapshot()     — đọc parquet kỳ
  - migration_matrix() — ma trận 4×4 chuyển dịch nhóm nợ

Không cần SQLite — monkeypatch _SNAPSHOT_DIR → tmp_path.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import services.migration_service as mm
from services.migration_service import _nhan_nhom_no

# Tên cột khớp config.py
COT_SO_KU   = "Số khế ước"
COT_MA_KH   = "Mã KH"
COT_PHAN_LOAI = "Phân loại"
COT_TONG_DU_NO = "Tổng dư nợ"
COT_TEN_PGD = "Tên PGD"
COT_TEN_CT  = "Tên chương trình"
COT_DU_NO_QH = "Dư nợ quá hạn"


# ── Helper ────────────────────────────────────────────────────────────────────

def _df_snap(ku_list, pl_list, pgd="PGD A") -> pd.DataFrame:
    n = len(ku_list)
    return pd.DataFrame({
        COT_SO_KU:    ku_list,
        COT_MA_KH:    [f"KH{i+1}" for i in range(n)],
        COT_PHAN_LOAI: pl_list,
        COT_TONG_DU_NO: [1_000_000] * n,
        COT_DU_NO_QH:   [0] * n,
        COT_TEN_PGD:    [pgd] * n,
        COT_TEN_CT:     ["CT A"] * n,
    })


# ══════════════════════════════════════════════════════════════════════════════
# _nhan_nhom_no()
# ══════════════════════════════════════════════════════════════════════════════

class TestNhanNhomNo:

    def _nhom_truoc(self, phanloai: str) -> str:
        result = _nhan_nhom_no(pd.Series([phanloai]), pd.Series([phanloai]))
        return result["nhom_truoc"].iloc[0]

    def test_e_la_trong_han(self):
        assert self._nhom_truoc("E") == "Trong hạn"

    def test_d_la_qua_han(self):
        assert self._nhom_truoc("D") == "Quá hạn"

    def test_c_la_khoanh(self):
        assert self._nhom_truoc("C") == "Khoanh"

    def test_b_la_khoanh(self):
        assert self._nhom_truoc("B") == "Khoanh"

    def test_a_la_khoanh(self):
        assert self._nhom_truoc("A") == "Khoanh"

    def test_rong_la_tat_toan(self):
        assert self._nhom_truoc("") == "Tất toán"

    def test_nan_string_la_tat_toan(self):
        assert self._nhom_truoc("nan") == "Tất toán"

    def test_viet_thuong_duoc_chuan_hoa(self):
        assert self._nhom_truoc("e") == "Trong hạn"

    def test_khoang_trang_duoc_strip(self):
        assert self._nhom_truoc(" E ") == "Trong hạn"

    def test_output_co_2_cot(self):
        result = _nhan_nhom_no(pd.Series(["E", "D"]), pd.Series(["D", "C"]))
        assert set(result.columns) == {"nhom_truoc", "nhom_sau"}
        assert result["nhom_truoc"].iloc[0] == "Trong hạn"
        assert result["nhom_sau"].iloc[0] == "Quá hạn"


# ══════════════════════════════════════════════════════════════════════════════
# danh_sach_ky() + doc_snapshot() — với monkeypatch _SNAPSHOT_DIR
# ══════════════════════════════════════════════════════════════════════════════

class TestDanhSachKy:

    def test_thu_muc_rong_tra_ve_list_rong(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        assert mm.danh_sach_ky() == []

    def test_liet_ke_ky_dung_dinh_dang(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        (tmp_path / "snapshot_2025-01.parquet").touch()
        (tmp_path / "snapshot_2024-12.parquet").touch()
        ky = mm.danh_sach_ky()
        assert "2025-01" in ky
        assert "2024-12" in ky

    def test_sap_xep_moi_truoc(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        (tmp_path / "snapshot_2024-12.parquet").touch()
        (tmp_path / "snapshot_2025-01.parquet").touch()
        ky = mm.danh_sach_ky()
        assert ky[0] > ky[-1]

    def test_bo_qua_file_sai_dinh_dang(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        (tmp_path / "snapshot_bad.parquet").touch()
        (tmp_path / "some_other_file.txt").touch()
        ky = mm.danh_sach_ky()
        assert ky == []


class TestDocSnapshot:

    def test_ky_khong_ton_tai_tra_ve_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        result = mm.doc_snapshot("2025-01")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_doc_dung_parquet(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        df = _df_snap(["KU001"], ["E"])
        df.to_parquet(tmp_path / "snapshot_2025-01.parquet", index=False)

        result = mm.doc_snapshot("2025-01")
        assert not result.empty
        assert COT_SO_KU in result.columns


# ══════════════════════════════════════════════════════════════════════════════
# migration_matrix()
# ══════════════════════════════════════════════════════════════════════════════

class TestMigrationMatrix:

    def _write_snap(self, tmp_path: Path, ky: str, df: pd.DataFrame):
        df.to_parquet(tmp_path / f"snapshot_{ky}.parquet", index=False)

    def test_ky_khong_ton_tai_tra_ve_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        matrix, detail = mm.migration_matrix("2024-12", "2025-01")
        assert matrix.empty
        assert detail.empty

    def test_matrix_co_4x4_rows(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        df1 = _df_snap(["KU001", "KU002", "KU003"], ["E", "D", "E"])
        df2 = _df_snap(["KU001", "KU002", "KU003"], ["E", "E", "D"])
        self._write_snap(tmp_path, "2024-12", df1)
        self._write_snap(tmp_path, "2025-01", df2)

        matrix, _ = mm.migration_matrix("2024-12", "2025-01")
        assert not matrix.empty
        # Ma trận reindex về 4 nhóm chuẩn
        for nhom in ["Trong hạn", "Quá hạn", "Khoanh"]:
            assert nhom in matrix.index

    def test_chi_tiet_co_cot_nhom_no(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        df1 = _df_snap(["KU001"], ["E"])
        df2 = _df_snap(["KU001"], ["D"])
        self._write_snap(tmp_path, "2024-12", df1)
        self._write_snap(tmp_path, "2025-01", df2)

        _, detail = mm.migration_matrix("2024-12", "2025-01")
        assert "Nhóm nợ kỳ trước" in detail.columns
        assert "Nhóm nợ kỳ sau" in detail.columns

    def test_mon_vay_chuyen_nhom_duoc_ghi_nhan(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mm, "_SNAPSHOT_DIR", tmp_path)
        # KU001: E → D (chuyển nhóm)
        # KU002: E → E (không đổi)
        df1 = _df_snap(["KU001", "KU002"], ["E", "E"])
        df2 = _df_snap(["KU001", "KU002"], ["D", "E"])
        self._write_snap(tmp_path, "2024-12", df1)
        self._write_snap(tmp_path, "2025-01", df2)

        matrix, detail = mm.migration_matrix("2024-12", "2025-01")
        # Trong hạn → Quá hạn phải có 1 món
        th_qh = int(matrix.loc["Trong hạn", "Quá hạn"])
        assert th_qh == 1
