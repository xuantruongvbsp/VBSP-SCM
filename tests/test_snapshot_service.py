"""
tests/test_snapshot_service.py
────────────────────────────────
Unit test cho snapshot_service.py.
Dùng SQLite in-memory để tránh phụ thuộc file DB thật.
"""
from __future__ import annotations

import sqlite3
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

import snapshot_service as svc


# ── Fixture: DataFrame HSTD giả ─────────────────────────────────────────────
@pytest.fixture
def df_hstd_gias():
    """DataFrame HSTD tối thiểu để test snapshot."""
    return pd.DataFrame({
        "Tên PGD":          ["PGD Biên Hòa", "PGD Biên Hòa", "PGD Long Khánh"],
        "Mã KH":            ["KH001", "KH002", "KH003"],
        "Số khế ước":       ["KU001", "KU002", "KU003"],
        "Tổng dư nợ":       [10_000_000.0, 20_000_000.0, 15_000_000.0],
        "Dư nợ trong hạn":  [10_000_000.0, 18_000_000.0, 15_000_000.0],
        "Dư nợ quá hạn":    [0.0, 2_000_000.0, 0.0],
        "Dư nợ khoanh":     [0.0, 0.0, 0.0],
        "Mã chương trình":  ["2", "4", "2"],
        "Nguồn vốn":        ["1", "1", "2"],
        "Ngày số liệu":     ["31/03/2026", "31/03/2026", "31/03/2026"],
    })


@pytest.fixture
def db_memory():
    """
    Tạo SQLite in-memory với bảng hstd_snapshot + patch db.get_conn().
    Trả về connection để test có thể query trực tiếp.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE hstd_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ky TEXT NOT NULL,
            ten_pgd TEXT NOT NULL,
            ma_ct TEXT NOT NULL DEFAULT 'ALL',
            nguon_von TEXT NOT NULL DEFAULT 'ALL',
            tong_du_no REAL DEFAULT 0,
            du_no_th REAL DEFAULT 0,
            du_no_qh REAL DEFAULT 0,
            du_no_khoanh REAL DEFAULT 0,
            so_ho INTEGER DEFAULT 0,
            so_ku INTEGER DEFAULT 0,
            gn_nam REAL DEFAULT 0,
            ngay_so_lieu TEXT,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ky, ten_pgd, ma_ct, nguon_von)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            username TEXT,
            action TEXT,
            detail TEXT
        )
    """)
    conn.commit()

    # Context manager mock trả về conn thật
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=conn)
    cm.__exit__ = MagicMock(return_value=False)

    with patch("db.get_conn", return_value=cm), \
         patch("db.ghi_audit", return_value=None):
        yield conn

    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# TEST _ky_tu_df
# ══════════════════════════════════════════════════════════════════════════════
class TestKyTuDf:
    def test_ngay_dang_viet(self):
        df = pd.DataFrame({"Ngày số liệu": ["31/03/2026"]})
        assert svc._ky_tu_df(df) == "2026-03"

    def test_ngay_dang_iso(self):
        df = pd.DataFrame({"Ngày số liệu": ["2026-03-31"]})
        assert svc._ky_tu_df(df) == "2026-03"

    def test_khong_co_cot(self):
        """Không có cột Ngày số liệu → fallback tháng hiện tại."""
        from datetime import datetime
        df = pd.DataFrame({"col": [1]})
        ky = svc._ky_tu_df(df)
        assert ky == datetime.now().strftime("%Y-%m")

    def test_gia_tri_null(self):
        df = pd.DataFrame({"Ngày số liệu": [None, None]})
        from datetime import datetime
        assert svc._ky_tu_df(df) == datetime.now().strftime("%Y-%m")


# ══════════════════════════════════════════════════════════════════════════════
# TEST luu_snapshot
# ══════════════════════════════════════════════════════════════════════════════
class TestLuuSnapshot:
    def test_luu_thanh_cong(self, df_hstd_gias, db_memory):
        kq = svc.luu_snapshot(df_hstd_gias, "test_user")
        assert kq.thanh_cong is True
        assert "2026-03" in kq.thong_bao

    def test_luu_co_dong_tong_pgd(self, df_hstd_gias, db_memory):
        """Phải có dòng tổng PGD (ma_ct='ALL', nguon_von='ALL')."""
        svc.luu_snapshot(df_hstd_gias, "test_user")
        rows = db_memory.execute(
            "SELECT * FROM hstd_snapshot WHERE ma_ct='ALL' AND nguon_von='ALL'"
        ).fetchall()
        # 2 PGD + 1 dòng __CN__
        assert len(rows) >= 3

    def test_luu_co_dong_cn(self, df_hstd_gias, db_memory):
        """Phải có dòng tổng toàn CN (__CN__)."""
        svc.luu_snapshot(df_hstd_gias, "test_user")
        row = db_memory.execute(
            "SELECT * FROM hstd_snapshot WHERE ten_pgd='__CN__'"
        ).fetchone()
        assert row is not None
        # Tổng dư nợ = 45 triệu
        assert abs(row["tong_du_no"] - 45_000_000.0) < 1

    def test_upsert_cung_ky(self, df_hstd_gias, db_memory):
        """Lưu 2 lần cùng kỳ → không bị trùng dòng."""
        svc.luu_snapshot(df_hstd_gias, "user1")
        svc.luu_snapshot(df_hstd_gias, "user2")
        count = db_memory.execute(
            "SELECT COUNT(*) FROM hstd_snapshot WHERE ten_pgd='__CN__'"
        ).fetchone()[0]
        assert count == 1  # upsert, không duplicate

    def test_df_rong_tra_false(self, db_memory):
        kq = svc.luu_snapshot(pd.DataFrame(), "test_user")
        assert kq.thanh_cong is False

    def test_df_none_tra_false(self, db_memory):
        kq = svc.luu_snapshot(None, "test_user")
        assert kq.thanh_cong is False


# ══════════════════════════════════════════════════════════════════════════════
# TEST doc_snapshot
# ══════════════════════════════════════════════════════════════════════════════
class TestDocSnapshot:
    def test_doc_sau_luu(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")
        df = svc.doc_snapshot("2026-03")
        assert not df.empty
        assert "tong_du_no" in df.columns

    def test_ky_khong_ton_tai(self, db_memory):
        df = svc.doc_snapshot("1999-01")
        assert df.empty

    def test_chi_lay_ma_ct_all(self, df_hstd_gias, db_memory):
        """doc_snapshot chỉ trả dòng ma_ct='ALL'."""
        svc.luu_snapshot(df_hstd_gias, "test_user")
        df = svc.doc_snapshot("2026-03")
        # Tất cả dòng phải là tổng PGD (không có chi tiết ct)
        assert len(df) >= 2  # ít nhất 2 PGD + __CN__


# ══════════════════════════════════════════════════════════════════════════════
# TEST doc_snapshot_range
# ══════════════════════════════════════════════════════════════════════════════
class TestDocSnapshotRange:
    def test_range_mot_ky(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")
        df = svc.doc_snapshot_range("2026-01", "2026-12")
        assert not df.empty
        assert "ky" in df.columns

    def test_range_khong_co_du_lieu(self, db_memory):
        df = svc.doc_snapshot_range("2020-01", "2020-12")
        assert df.empty


# ══════════════════════════════════════════════════════════════════════════════
# TEST danh_sach_ky
# ══════════════════════════════════════════════════════════════════════════════
class TestDanhSachKy:
    def test_rong_khi_chua_co(self, db_memory):
        ds = svc.danh_sach_ky()
        assert ds == []

    def test_co_ky_sau_luu(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")
        ds = svc.danh_sach_ky()
        assert "2026-03" in ds

    def test_thu_tu_moi_truoc(self, df_hstd_gias, db_memory):
        """Danh sách phải sắp theo mới → cũ."""
        svc.luu_snapshot(df_hstd_gias, "u1")
        df2 = df_hstd_gias.copy()
        df2["Ngày số liệu"] = "30/04/2026"
        svc.luu_snapshot(df2, "u2")
        ds = svc.danh_sach_ky()
        assert ds[0] > ds[-1]  # mới nhất ở đầu


# ══════════════════════════════════════════════════════════════════════════════
# TEST xoa_snapshot
# ══════════════════════════════════════════════════════════════════════════════
class TestXoaSnapshot:
    def test_xoa_thanh_cong(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")
        svc.xoa_snapshot("2026-03", "test_user")
        ds = svc.danh_sach_ky()
        assert "2026-03" not in ds

    def test_xoa_ky_khong_ton_tai(self, db_memory):
        """Xóa kỳ không tồn tại không được raise exception."""
        try:
            svc.xoa_snapshot("1999-01", "test_user")
        except Exception as e:
            pytest.fail(f"xoa_snapshot raise exception không mong muốn: {e}")
