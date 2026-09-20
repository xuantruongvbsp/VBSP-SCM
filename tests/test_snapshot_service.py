"""
tests/test_snapshot_service.py
────────────────────────────────
Unit test cho snapshot_service.py.
Dùng SQLite in-memory để tránh phụ thuộc file DB thật.
"""
from __future__ import annotations

import sqlite3
import importlib
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
        "Tên ĐVUT":         ["Hội A", "Hội A", "Hội B"],
        "Tên xã":           ["Xã 1", "Xã 1", "Xã 2"],
        "Tên tổ":           ["Tổ 1", "Tổ 2", "Tổ 3"],
        "Lãi tồn TH":       [100_000.0, 200_000.0, 50_000.0],
        "Lãi tồn QH":       [0.0, 20_000.0, 0.0],
        "Số dư tiền gửi 105": [10_000.0, 20_000.0, 15_000.0],
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
        CREATE TABLE uy_thac_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ky TEXT NOT NULL,
            cap_tong_hop TEXT NOT NULL,
            ten_pgd TEXT NOT NULL DEFAULT '__ALL__',
            ten_xa TEXT NOT NULL DEFAULT '__ALL__',
            dvut TEXT NOT NULL DEFAULT '__ALL__',
            ten_to TEXT NOT NULL DEFAULT '__ALL__',
            tong_du_no REAL DEFAULT 0,
            du_no_qh REAL DEFAULT 0,
            lai_ton REAL DEFAULT 0,
            so_du_tg REAL DEFAULT 0,
            so_kh INTEGER DEFAULT 0,
            so_ku INTEGER DEFAULT 0,
            so_to INTEGER DEFAULT 0,
            ngay_so_lieu TEXT,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ky, cap_tong_hop, ten_pgd, ten_xa, dvut, ten_to)
        )
    """)
    conn.execute("""
        CREATE TABLE nq11_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ky TEXT NOT NULL,
            ten_pgd TEXT NOT NULL DEFAULT '__CN__',
            tong_du_no REAL DEFAULT 0,
            no_th REAL DEFAULT 0,
            no_qh REAL DEFAULT 0,
            so_kh INTEGER DEFAULT 0,
            gn_nam REAL DEFAULT 0,
            ngay_bc TEXT,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ky, ten_pgd)
        )
    """)
    conn.execute("""
        CREATE TABLE gqvl_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ky TEXT NOT NULL,
            ten_pgd TEXT NOT NULL DEFAULT '__CN__',
            dn_th REAL DEFAULT 0,
            dn_qh REAL DEFAULT 0,
            dn_khoanh REAL DEFAULT 0,
            so_kh INTEGER DEFAULT 0,
            gn_nam REAL DEFAULT 0,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ky, ten_pgd)
        )
    """)
    conn.execute("""
        CREATE TABLE cdtotkvv_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ky TEXT NOT NULL,
            ten_pgd TEXT NOT NULL DEFAULT '__CN__',
            so_to INTEGER DEFAULT 0,
            so_tot INTEGER DEFAULT 0,
            so_kha INTEGER DEFAULT 0,
            so_tb INTEGER DEFAULT 0,
            so_yeu INTEGER DEFAULT 0,
            diem_tb REAL DEFAULT 0,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ky, ten_pgd)
        )
    """)
    conn.execute("""
        CREATE TABLE thon_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ky TEXT NOT NULL,
            ten_pgd TEXT NOT NULL DEFAULT '',
            ma_thon TEXT NOT NULL DEFAULT '',
            ten_xa TEXT NOT NULL,
            ten_thon TEXT NOT NULL,
            tong_du_no REAL NOT NULL DEFAULT 0,
            du_no_th REAL NOT NULL DEFAULT 0,
            du_no_qh REAL NOT NULL DEFAULT 0,
            cho_vay_thang REAL NOT NULL DEFAULT 0,
            thu_no_thang REAL NOT NULL DEFAULT 0,
            cho_vay_nam REAL NOT NULL DEFAULT 0,
            thu_no_nam REAL NOT NULL DEFAULT 0,
            no_den_han_mon INTEGER NOT NULL DEFAULT 0,
            no_den_han_goc REAL NOT NULL DEFAULT 0,
            so_mon_3m_khd INTEGER NOT NULL DEFAULT 0,
            so_mon_rui_ro INTEGER NOT NULL DEFAULT 0,
            ngay_so_lieu TEXT,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ky, ten_pgd, ma_thon, ten_xa, ten_thon)
        )
    """)
    conn.execute("""
        CREATE TABLE cbtd_to_tkvv_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ky TEXT NOT NULL,
            ma_cb TEXT NOT NULL,
            ho_ten TEXT NOT NULL DEFAULT '',
            pgd TEXT NOT NULL DEFAULT '',
            so_to INTEGER NOT NULL DEFAULT 0,
            so_tot INTEGER NOT NULL DEFAULT 0,
            so_kha INTEGER NOT NULL DEFAULT 0,
            so_tb INTEGER NOT NULL DEFAULT 0,
            so_yeu INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_by TEXT NOT NULL DEFAULT 'system',
            UNIQUE(ky, ma_cb)
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
        df = pd.DataFrame({"Ngày số liệu": ["2026-07-01"]})
        assert svc._ky_tu_df(df) == "2026-07"
        assert svc._ngay_so_lieu_max(df) == "01/07/2026"

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

    def test_nhieu_ngay_lay_ngay_lon_nhat(self):
        df = pd.DataFrame({"Ngày số liệu": ["31/03/2026", "30/04/2026"]})
        assert svc._ky_tu_df(df) == "2026-04"
        assert svc._ngay_so_lieu_max(df) == "30/04/2026"


class TestKyThangTruoc:
    def test_thang_lien_truoc_chinh_xac(self):
        ds = ["2026-05", "2026-04", "2026-03", "2025-12"]
        assert svc.ky_thang_truoc(ds, "2026-05") == "2026-04"

    def test_thang_truoc_khi_qua_nam(self):
        ds = ["2026-01", "2025-12", "2025-11"]
        assert svc.ky_thang_truoc(ds, "2026-01") == "2025-12"

    def test_thieu_thang_lien_truoc_tra_none(self):
        ds = ["2026-05", "2026-02", "2026-01"]
        assert svc.ky_thang_truoc(ds, "2026-05") is None

    def test_danh_sach_rong(self):
        assert svc.ky_thang_truoc([], "2026-05") is None

    def test_ky_khong_hop_le(self):
        assert svc.ky_thang_truoc(["2026-05"], "abc") is None
        assert svc.ky_thang_truoc(["2025-12"], "2026-00") is None
        assert svc.ky_thang_truoc(["2026-02"], "2026-03-extra") is None

    def test_khong_co_ky_truoc_tra_none(self):
        assert svc.ky_thang_truoc(["2026-05"], "2026-05") is None


class TestKyBaseline:
    def test_chi_nhan_dung_thang_12_nam_truoc(self):
        ds = ["2026-08", "2025-12", "2025-11"]
        assert svc.ky_baseline(ds, "2026-08") == "2025-12"

    def test_thieu_thang_12_khong_fallback_sang_ky_khac(self):
        ds = ["2026-08", "2026-07", "2026-04"]
        assert svc.ky_baseline(ds, "2026-08") is None

    def test_ky_hien_tai_khong_hop_le_tra_none(self):
        assert svc.ky_baseline(["2025-12"], "abc") is None


class TestNgayCuoiThang:
    def test_thang_31_ngay(self):
        assert svc.ngay_cuoi_thang("2026-03") == "31/03/2026"

    def test_thang_30_ngay(self):
        assert svc.ngay_cuoi_thang("2026-04") == "30/04/2026"

    def test_thang_2_nam_nhuan(self):
        assert svc.ngay_cuoi_thang("2024-02") == "29/02/2024"

    def test_ky_khong_hop_le(self):
        assert svc.ngay_cuoi_thang("abc") is None

    def test_ky_thua_thanh_phan_khong_hop_le(self):
        assert svc.ngay_cuoi_thang("2026-03-15") is None

    def test_luu_snapshot_giu_ngay_so_lieu_thuc_te(self, db_memory):
        df = pd.DataFrame({
            "Tên PGD": ["PGD Biên Hòa"],
            "Mã KH": ["KH001"],
            "Số khế ước": ["KU001"],
            "Tổng dư nợ": [10_000_000.0],
            "Dư nợ trong hạn": [10_000_000.0],
            "Dư nợ quá hạn": [0.0],
            "Dư nợ khoanh": [0.0],
            "Mã chương trình": ["2"],
            "Nguồn vốn": ["1"],
            "Ngày số liệu": ["15/03/2026"],
        })
        svc.luu_snapshot(df, "tester")
        row = db_memory.execute(
            "SELECT ngay_so_lieu FROM hstd_snapshot WHERE ten_pgd='__CN__'"
        ).fetchone()
        assert row["ngay_so_lieu"] == "15/03/2026"

    def test_snapshot_la_cuoi_thang(self):
        df_ok = pd.DataFrame({"ngay_so_lieu": ["30/04/2026", "30/04/2026"]})
        df_sai = pd.DataFrame({"ngay_so_lieu": ["29/04/2026"]})
        assert svc.snapshot_la_cuoi_thang(df_ok, "2026-04") is True
        assert svc.snapshot_la_cuoi_thang(df_sai, "2026-04") is False

    def test_snapshot_la_cuoi_thang_ho_tro_cot_ngay_nq11(self):
        df_ok = pd.DataFrame({"ngay_bc": ["31/12/2025", "31/12/2025"]})
        df_sai = pd.DataFrame({"ngay_bc": ["12/05/2026"]})
        assert svc.snapshot_la_cuoi_thang(df_ok, "2025-12", cot_ngay="ngay_bc") is True
        assert svc.snapshot_la_cuoi_thang(df_sai, "2026-12", cot_ngay="ngay_bc") is False


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

    def test_luu_lai_cung_ky_xoa_dong_chi_tiet_khong_con(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "user1")
        df_moi = df_hstd_gias.iloc[[0]].copy()

        kq = svc.luu_snapshot(df_moi, "user2")

        assert kq.thanh_cong is True
        rows = db_memory.execute(
            "SELECT ten_pgd, ma_ct, nguon_von FROM hstd_snapshot WHERE ky='2026-03'"
        ).fetchall()
        assert {(r["ten_pgd"], r["ma_ct"], r["nguon_von"]) for r in rows} == {
            ("PGD Biên Hòa", "2", "1"),
            ("PGD Biên Hòa", "ALL", "ALL"),
            ("__CN__", "ALL", "ALL"),
        }

    def test_luu_ngay_so_lieu_theo_tung_pgd_de_phat_hien_file_giua_thang(
        self, df_hstd_gias, db_memory
    ):
        df = df_hstd_gias.iloc[[0, 2]].copy()
        df.loc[df["Tên PGD"].eq("PGD Biên Hòa"), "Ngày số liệu"] = "31/03/2026"
        df.loc[df["Tên PGD"].eq("PGD Long Khánh"), "Ngày số liệu"] = "23/03/2026"

        svc.luu_snapshot(df, "user1")
        snap = svc.doc_snapshot("2026-03")

        ngay_theo_pgd = snap.set_index("ten_pgd")["ngay_so_lieu"].to_dict()
        assert ngay_theo_pgd["PGD Biên Hòa"] == "31/03/2026"
        assert ngay_theo_pgd["PGD Long Khánh"] == "23/03/2026"
        assert svc.snapshot_la_cuoi_thang(snap, "2026-03") is False

    def test_luu_lai_cung_ky_rollback_neu_insert_loi(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "user1")
        count_truoc = db_memory.execute(
            "SELECT COUNT(*) FROM hstd_snapshot WHERE ky='2026-03'"
        ).fetchone()[0]
        db_memory.execute("""
            CREATE TRIGGER fail_hstd_insert
            BEFORE INSERT ON hstd_snapshot
            WHEN NEW.ma_ct = '4'
            BEGIN
                SELECT RAISE(ABORT, 'forced insert failure');
            END
        """)
        db_memory.commit()

        kq = svc.luu_snapshot(df_hstd_gias, "user2")

        assert kq.thanh_cong is False
        count_sau = db_memory.execute(
            "SELECT COUNT(*) FROM hstd_snapshot WHERE ky='2026-03'"
        ).fetchone()[0]
        assert count_sau == count_truoc

    def test_cho_phep_truyen_ky_tuong_minh(self, df_hstd_gias, db_memory):
        df_baseline = df_hstd_gias.copy()
        df_baseline["Ngày số liệu"] = "31/12/2025"
        kq = svc.luu_snapshot(df_baseline, "user1", ky="2025-12")
        assert kq.thanh_cong is True
        assert db_memory.execute(
            "SELECT COUNT(*) FROM hstd_snapshot WHERE ky='2025-12'"
        ).fetchone()[0] > 0

    def test_df_rong_tra_false(self, db_memory):
        kq = svc.luu_snapshot(pd.DataFrame(), "test_user")
        assert kq.thanh_cong is False

    def test_df_none_tra_false(self, db_memory):
        kq = svc.luu_snapshot(None, "test_user")
        assert kq.thanh_cong is False

    def test_luu_clear_cache(self, df_hstd_gias, db_memory):
        with patch.object(svc, "_clear_snapshot_cache") as clear_mock:
            svc.luu_snapshot(df_hstd_gias, "test_user")
        clear_mock.assert_called_once()


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

    def test_doc_theo_ct_cong_tu_dong_chi_tiet_pgd(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")
        df = svc.doc_snapshot_theo_ct("2026-03")
        assert not df.empty
        row_ct2 = df[df["ma_ct"] == "2"].iloc[0]
        assert row_ct2["tong_du_no"] == 25_000_000.0


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


class TestUyThacSnapshot:
    def test_luu_va_doc_chuoi_cn(self, df_hstd_gias, db_memory):
        kq = svc.luu_uy_thac_snapshot(df_hstd_gias, "tester")
        assert kq.thanh_cong is True
        df = svc.doc_uy_thac_snapshot_multi(("2026-03",))
        assert len(df) == 1
        assert df.iloc[0]["tong_du_no"] == 45_000_000.0
        assert df.iloc[0]["lai_ton"] == 370_000.0
        assert df.iloc[0]["so_to"] == 3

    def test_upsert_cung_ky_khong_trung(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "u1")
        svc.luu_uy_thac_snapshot(df_hstd_gias, "u2")
        count = db_memory.execute(
            "SELECT COUNT(*) FROM uy_thac_snapshot WHERE ky='2026-03' AND cap_tong_hop='CN'"
        ).fetchone()[0]
        assert count == 1

    def test_luu_lai_cung_ky_xoa_dong_uy_thac_khong_con(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "u1")
        df_moi = df_hstd_gias[df_hstd_gias["Tên PGD"] == "PGD Biên Hòa"].copy()

        kq = svc.luu_uy_thac_snapshot(df_moi, "u2")

        assert kq.thanh_cong is True
        count_long_khanh = db_memory.execute(
            "SELECT COUNT(*) FROM uy_thac_snapshot WHERE ky='2026-03' AND ten_pgd='PGD Long Khánh'"
        ).fetchone()[0]
        assert count_long_khanh == 0

    def test_luu_uy_thac_suy_ra_ten_hoi_va_to_tu_ma_to(self, df_hstd_gias, db_memory):
        df = df_hstd_gias.iloc[[0]].copy()
        df["Tên ĐVUT"] = pd.NA
        df["Tên tổ"] = pd.NA
        df["Mã PGD"] = "004601"
        df["Mã tổ"] = "000123"

        with patch(
            "data.cdtotkvv.ban_do_ma_to_dvut",
            return_value={"4601|123": "11", "123": "14"},
        ):
            kq = svc.luu_uy_thac_snapshot(df, "tester")

        assert kq.thanh_cong is True
        row_hoi = db_memory.execute(
            """SELECT dvut FROM uy_thac_snapshot
                WHERE ky='2026-03' AND cap_tong_hop='HOI' AND ten_pgd='PGD Biên Hòa'"""
        ).fetchone()
        row_to = db_memory.execute(
            """SELECT dvut, ten_to FROM uy_thac_snapshot
                WHERE ky='2026-03' AND cap_tong_hop='TO'"""
        ).fetchone()
        assert row_hoi["dvut"] == "Hội nông dân"
        assert row_to["dvut"] == "Hội nông dân"
        assert row_to["ten_to"] == "Tổ 123"

    def test_doc_theo_pgd(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "tester")
        df = svc.doc_uy_thac_snapshot_multi(("2026-03",), ten_pgd="PGD Biên Hòa")
        assert len(df) == 1
        assert df.iloc[0]["tong_du_no"] == 30_000_000.0

    def test_doc_theo_hoi(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "tester")
        df = svc.doc_uy_thac_snapshot_multi(("2026-03",), cap_tong_hop="HOI", dvut="Hội A")
        assert len(df) == 1
        assert df.iloc[0]["ten_pgd"] == "__ALL__"
        assert df.iloc[0]["dvut"] == "Hội A"
        assert df.iloc[0]["tong_du_no"] == 30_000_000.0
        assert df.iloc[0]["so_to"] == 2

    def test_doc_theo_hoi_trong_tung_pgd(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "tester")
        df = svc.doc_uy_thac_snapshot_multi(
            ("2026-03",),
            ten_pgd="PGD Biên Hòa",
            cap_tong_hop="HOI",
            dvut="Hội A",
        )
        assert len(df) == 1
        assert df.iloc[0]["ten_pgd"] == "PGD Biên Hòa"
        assert df.iloc[0]["dvut"] == "Hội A"
        assert df.iloc[0]["tong_du_no"] == 30_000_000.0
        assert df.iloc[0]["so_to"] == 2

    def test_api_hoi_cn_chi_doc_grain_toan_chi_nhanh(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "tester")
        df = svc.doc_uy_thac_snapshot_hoi_cn(("2026-03",), "Hội A")

        assert len(df) == 1
        assert df.iloc[0]["ten_pgd"] == "__ALL__"
        assert df.iloc[0]["tong_du_no"] == 30_000_000.0

    def test_api_hoi_pgd_chi_doc_grain_pgd(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "tester")
        df = svc.doc_uy_thac_snapshot_hoi_pgd(
            ("2026-03",), "PGD Biên Hòa", "Hội A"
        )

        assert len(df) == 1
        assert df.iloc[0]["ten_pgd"] == "PGD Biên Hòa"
        assert df.iloc[0]["tong_du_no"] == 30_000_000.0

    def test_api_hoi_pgd_khong_truy_van_khi_thieu_pham_vi(self, db_memory):
        df = svc.doc_uy_thac_snapshot_hoi_pgd(("2026-03",), "", "Hội A")
        assert df.empty

    def test_doc_theo_hoi_khong_lan_cn_va_pgd_khi_cung_hoi_o_nhieu_pgd(self, db_memory):
        df = pd.DataFrame({
            "Tên PGD": ["PGD Biên Hòa", "PGD Long Khánh"],
            "Mã KH": ["KH001", "KH002"],
            "Số khế ước": ["KU001", "KU002"],
            "Tổng dư nợ": [10_000_000.0, 15_000_000.0],
            "Dư nợ trong hạn": [10_000_000.0, 15_000_000.0],
            "Dư nợ quá hạn": [0.0, 0.0],
            "Dư nợ khoanh": [0.0, 0.0],
            "Mã chương trình": ["2", "2"],
            "Nguồn vốn": ["1", "1"],
            "Ngày số liệu": ["31/03/2026", "31/03/2026"],
            "Tên ĐVUT": ["Hội A", "Hội A"],
            "Tên xã": ["Xã 1", "Xã 2"],
            "Tên tổ": ["Tổ 1", "Tổ 2"],
            "Lãi tồn TH": [100_000.0, 50_000.0],
            "Lãi tồn QH": [0.0, 0.0],
            "Số dư tiền gửi 105": [10_000.0, 15_000.0],
        })
        svc.luu_uy_thac_snapshot(df, "tester")

        df_cn = svc.doc_uy_thac_snapshot_multi(("2026-03",), cap_tong_hop="HOI", dvut="Hội A")
        assert len(df_cn) == 1
        assert df_cn.iloc[0]["ten_pgd"] == "__ALL__"
        assert df_cn.iloc[0]["tong_du_no"] == 25_000_000.0

        df_pgd = svc.doc_uy_thac_snapshot_multi(
            ("2026-03",),
            ten_pgd="PGD Biên Hòa",
            cap_tong_hop="HOI",
            dvut="Hội A",
        )
        assert len(df_pgd) == 1
        assert df_pgd.iloc[0]["ten_pgd"] == "PGD Biên Hòa"
        assert df_pgd.iloc[0]["tong_du_no"] == 10_000_000.0

    def test_doc_theo_hoi_suy_luan_dung_backward_compatible_khi_truyen_dvut_va_ten_pgd(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "tester")
        df = svc.doc_uy_thac_snapshot_multi(
            ("2026-03",),
            ten_pgd="PGD Biên Hòa",
            dvut="Hội A",
        )
        assert len(df) == 1
        assert df.iloc[0]["cap_tong_hop"] == "HOI"
        assert df.iloc[0]["ten_pgd"] == "PGD Biên Hòa"

    def test_doc_theo_xa(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "tester")
        df = svc.doc_uy_thac_snapshot_multi(
            ("2026-03",),
            ten_pgd="PGD Biên Hòa",
            cap_tong_hop="XA",
            ten_xa="Xã 1",
        )
        assert len(df) == 1
        assert df.iloc[0]["ten_pgd"] == "PGD Biên Hòa"
        assert df.iloc[0]["ten_xa"] == "Xã 1"
        assert df.iloc[0]["tong_du_no"] == 30_000_000.0

    def test_luu_uy_thac_cho_phep_override_ky_backfill(self, df_hstd_gias, db_memory):
        svc.luu_uy_thac_snapshot(df_hstd_gias, "tester", ky="2025-12")
        df = svc.doc_uy_thac_snapshot_multi(("2025-12",), ten_pgd="PGD Biên Hòa")

        assert len(df) == 1
        assert df.iloc[0]["ky"] == "2025-12"
        assert df.iloc[0]["tong_du_no"] == 30_000_000.0


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


class TestThonSnapshot:
    @staticmethod
    def _tong_hop(*rows: dict) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_luu_doc_giu_dinh_danh_va_ngay_tung_thon(self, db_memory):
        raw = pd.DataFrame({"Ngày số liệu": ["31/03/2026"]})
        tong_hop = self._tong_hop({
            "Ten_pgd": "PGD A", "Ma_thon": "101", "Ten_xa": "Xã A", "Ten_thon": "Thôn 1",
            "Tong_du_no": 10_000_000, "Du_no_th": 9_000_000, "Du_no_qh": float("nan"),
            "Cho_vay_thang": 2_000_000, "Thu_no_thang": 1_000_000,
            "Cho_vay_nam": 4_000_000, "Thu_no_nam": 3_000_000,
            "No_den_han_mon": 1, "No_den_han_goc": 3_000_000,
            "So_mon_3m_khd": 0, "So_mon_rui_ro": 1, "Ngay_so_lieu": "31/03/2026",
        })
        with patch(
            "services.cbtd_dia_ban_service.tong_hop_hstd_theo_thon",
            return_value=tong_hop,
        ):
            result = svc.luu_thon_snapshot(raw, "tester", ky="2026-03")

        assert result.thanh_cong is True
        doc = svc.doc_thon_snapshot("2026-03")
        assert doc.loc[0, "ten_pgd"] == "PGD A"
        assert doc.loc[0, "ma_thon"] == "101"
        assert doc.loc[0, "du_no_th"] == 9_000_000
        assert doc.loc[0, "du_no_qh"] == 0
        assert doc.loc[0, "cho_vay_nam"] == 4_000_000
        assert doc.loc[0, "thu_no_nam"] == 3_000_000
        assert doc.loc[0, "ngay_so_lieu"] == "31/03/2026"

    def test_luu_lai_cung_ky_xoa_thon_khong_con(self, db_memory):
        raw = pd.DataFrame({"Ngày số liệu": ["31/03/2026"]})
        base = {
            "Ten_pgd": "PGD A", "Ma_thon": "101", "Ten_xa": "Xã A", "Ten_thon": "Thôn 1",
            "Tong_du_no": 1, "Du_no_qh": 0, "Cho_vay_thang": 0, "Thu_no_thang": 0,
            "No_den_han_mon": 0, "No_den_han_goc": 0, "So_mon_3m_khd": 0,
            "So_mon_rui_ro": 0, "Ngay_so_lieu": "31/03/2026",
        }
        first = self._tong_hop(base, {**base, "Ma_thon": "102", "Ten_thon": "Thôn 2"})
        second = self._tong_hop(base)
        with patch(
            "services.cbtd_dia_ban_service.tong_hop_hstd_theo_thon",
            side_effect=[first, second],
        ):
            assert svc.luu_thon_snapshot(raw, "u1", ky="2026-03").thanh_cong
            assert svc.luu_thon_snapshot(raw, "u2", ky="2026-03").thanh_cong

        rows = db_memory.execute(
            "SELECT ma_thon FROM thon_snapshot WHERE ky='2026-03'"
        ).fetchall()
        assert [r["ma_thon"] for r in rows] == ["101"]

    def test_luu_lai_rollback_neu_insert_loi(self, db_memory):
        raw = pd.DataFrame({"Ngày số liệu": ["31/03/2026"]})
        good = self._tong_hop({
            "Ten_pgd": "PGD A", "Ma_thon": "101", "Ten_xa": "Xã A", "Ten_thon": "Thôn 1",
            "Tong_du_no": 1, "Ngay_so_lieu": "31/03/2026",
        })
        bad = self._tong_hop({
            "Ten_pgd": "PGD A", "Ma_thon": "999", "Ten_xa": "Xã A", "Ten_thon": "FAIL",
            "Tong_du_no": 2, "Ngay_so_lieu": "31/03/2026",
        })
        with patch(
            "services.cbtd_dia_ban_service.tong_hop_hstd_theo_thon",
            return_value=good,
        ):
            assert svc.luu_thon_snapshot(raw, "u1", ky="2026-03").thanh_cong
        db_memory.execute("""
            CREATE TRIGGER fail_thon_insert BEFORE INSERT ON thon_snapshot
            WHEN NEW.ten_thon = 'FAIL'
            BEGIN SELECT RAISE(ABORT, 'forced insert failure'); END
        """)
        db_memory.commit()

        with patch(
            "services.cbtd_dia_ban_service.tong_hop_hstd_theo_thon",
            return_value=bad,
        ):
            result = svc.luu_thon_snapshot(raw, "u2", ky="2026-03")

        assert result.thanh_cong is False
        row = db_memory.execute(
            "SELECT ma_thon, tong_du_no FROM thon_snapshot WHERE ky='2026-03'"
        ).fetchone()
        assert (row["ma_thon"], row["tong_du_no"]) == ("101", 1)

    def test_export_thon_snapshot(self, db_memory):
        db_memory.execute(
            """INSERT INTO thon_snapshot
               (ky, ten_pgd, ma_thon, ten_xa, ten_thon, ngay_so_lieu)
               VALUES ('2026-03', 'PGD A', '101', 'Xã A', 'Thôn 1', '31/03/2026')"""
        )
        db_memory.commit()
        assert svc.export_snapshot_excel(["2026-03"], "thon")[:2] == b"PK"


class TestThonSnapshotMigration:
    def test_nang_schema_bao_toan_du_lieu_va_khong_xoa_cbtd_cu(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE thon_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ky TEXT NOT NULL,
                ten_xa TEXT NOT NULL, ten_thon TEXT NOT NULL,
                tong_du_no REAL NOT NULL DEFAULT 0, du_no_qh REAL NOT NULL DEFAULT 0,
                cho_vay_thang REAL NOT NULL DEFAULT 0, thu_no_thang REAL NOT NULL DEFAULT 0,
                no_den_han_mon INTEGER NOT NULL DEFAULT 0, no_den_han_goc REAL NOT NULL DEFAULT 0,
                so_mon_3m_khd INTEGER NOT NULL DEFAULT 0, so_mon_rui_ro INTEGER NOT NULL DEFAULT 0,
                ngay_so_lieu TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')),
                created_by TEXT NOT NULL DEFAULT 'system', UNIQUE(ky, ten_xa, ten_thon)
            )
        """)
        conn.execute("CREATE TABLE cbtd_snapshot (id INTEGER PRIMARY KEY, ky TEXT)")
        conn.execute(
            "INSERT INTO thon_snapshot (ky, ten_xa, ten_thon, tong_du_no) VALUES ('2026-03','Xã A','Thôn 1',123)"
        )
        conn.commit()

        importlib.import_module("migrations.004_ensure_thon_snapshot").upgrade(conn)
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cbtd_snapshot'"
        ).fetchone()
        importlib.import_module("migrations.005_thon_snapshot_identity").upgrade(conn)

        columns = {r[1] for r in conn.execute("PRAGMA table_info(thon_snapshot)")}
        row = conn.execute(
            "SELECT ten_pgd, ma_thon, ten_xa, ten_thon, tong_du_no FROM thon_snapshot"
        ).fetchone()
        assert {"ten_pgd", "ma_thon"}.issubset(columns)
        assert row[0] in {"", "__UNKNOWN__"}
        assert row[1:] == ("", "Xã A", "Thôn 1", 123)
        conn.close()

    def test_migration_006_them_chi_tieu_va_bang_cbtd_to_tkvv_idempotent(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE thon_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ky TEXT NOT NULL,
                ten_pgd TEXT NOT NULL DEFAULT '',
                ma_thon TEXT NOT NULL DEFAULT '',
                ten_xa TEXT NOT NULL,
                ten_thon TEXT NOT NULL,
                tong_du_no REAL NOT NULL DEFAULT 0,
                du_no_qh REAL NOT NULL DEFAULT 0
            )
        """)
        migration = importlib.import_module("migrations.006_cbtd_comparison")

        migration.upgrade(conn)
        migration.upgrade(conn)

        columns = {r[1] for r in conn.execute("PRAGMA table_info(thon_snapshot)")}
        assert {"du_no_th", "cho_vay_nam", "thu_no_nam"}.issubset(columns)
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cbtd_to_tkvv_snapshot'"
        ).fetchone()
        conn.close()


class TestCbtdToTkvvSnapshot:
    def test_luu_doc_khu_trung_to_va_dem_xep_loai(self, db_memory):
        df_cdtot = pd.DataFrame([
            {"ten_dv": "PGD A", "ten_xa": "Xã A", "ma_to": "T01", "xep_loai": "Tốt"},
            {"ten_dv": "PGD A", "ten_xa": "Xã A", "ma_to": "T01", "xep_loai": "Tốt"},
            {"ten_dv": "PGD A", "ten_xa": "Xã A", "ma_to": "T02", "xep_loai": "Khá"},
        ])
        cbtd_data = {
            "CB01": {"ho_ten": "Nguyễn Văn A", "pgd": "PGD A", "ds_dgd": ["ĐGD A"]},
        }
        dgd_map = {
            "PGD A": {"Xã A": {"ĐGD A": {"thon": ["Thôn 1"]}}},
        }

        result = svc.luu_cbtd_to_tkvv_snapshot(
            df_cdtot, cbtd_data, dgd_map, "2026-03", "tester"
        )
        doc = svc.doc_cbtd_to_tkvv_snapshot("2026-03")

        assert result.thanh_cong is True
        assert len(doc) == 1
        assert doc.loc[0, "ma_cb"] == "CB01"
        assert doc.loc[0, "so_to"] == 2
        assert doc.loc[0, "so_tot"] == 1
        assert doc.loc[0, "so_kha"] == 1

    def test_xoa_cdtotkvv_snapshot_ky_khong_dung_bang_hstd(self, db_memory):
        db_memory.execute(
            "INSERT INTO cdtotkvv_snapshot (ky, ten_pgd) VALUES (?, ?)",
            ("2026-09", "__CN__"),
        )
        db_memory.execute(
            "INSERT INTO cbtd_to_tkvv_snapshot (ky, ma_cb) VALUES (?, ?)",
            ("2026-09", "CB01"),
        )
        db_memory.execute(
            "INSERT INTO hstd_snapshot (ky, ten_pgd, ma_ct, nguon_von) VALUES (?, ?, ?, ?)",
            ("2026-09", "__CN__", "ALL", "ALL"),
        )
        db_memory.commit()

        result = svc.xoa_cdtotkvv_snapshot_ky("2026-09", "tester")

        assert result.thanh_cong is True
        assert db_memory.execute(
            "SELECT COUNT(*) FROM cdtotkvv_snapshot WHERE ky='2026-09'"
        ).fetchone()[0] == 0
        assert db_memory.execute(
            "SELECT COUNT(*) FROM cbtd_to_tkvv_snapshot WHERE ky='2026-09'"
        ).fetchone()[0] == 0
        assert db_memory.execute(
            "SELECT COUNT(*) FROM hstd_snapshot WHERE ky='2026-09'"
        ).fetchone()[0] == 1


# ══════════════════════════════════════════════════════════════════════════════
# TEST xoa_snapshot
# ══════════════════════════════════════════════════════════════════════════════
class TestXoaSnapshot:
    def test_xoa_thanh_cong(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")
        svc.xoa_snapshot("2026-03", "test_user")
        ds = svc.danh_sach_ky()
        assert "2026-03" not in ds

    def test_xoa_dong_bo_tat_ca_bang(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")
        db_memory.execute(
            "INSERT INTO uy_thac_snapshot (ky, cap_tong_hop, ten_pgd) VALUES (?, ?, ?)",
            ("2026-03", "CN", "__ALL__"),
        )
        for table in ("nq11_snapshot", "gqvl_snapshot", "cdtotkvv_snapshot"):
            db_memory.execute(f"INSERT INTO {table} (ky, ten_pgd) VALUES (?, ?)", ("2026-03", "__CN__"))
        db_memory.execute(
            """INSERT INTO thon_snapshot
               (ky, ten_pgd, ma_thon, ten_xa, ten_thon) VALUES (?, ?, ?, ?, ?)""",
            ("2026-03", "PGD A", "101", "Xã A", "Thôn 1"),
        )
        db_memory.execute(
            "INSERT INTO cbtd_to_tkvv_snapshot (ky, ma_cb) VALUES (?, ?)",
            ("2026-03", "CB01"),
        )
        db_memory.commit()

        svc.xoa_snapshot("2026-03", "test_user")

        for table in (
            "hstd_snapshot",
            "uy_thac_snapshot",
            "nq11_snapshot",
            "gqvl_snapshot",
            "cdtotkvv_snapshot",
            "cbtd_to_tkvv_snapshot",
            "thon_snapshot",
        ):
            count = db_memory.execute(f"SELECT COUNT(*) FROM {table} WHERE ky='2026-03'").fetchone()[0]
            assert count == 0

    def test_xoa_ky_khong_ton_tai(self, db_memory):
        """Xóa kỳ không tồn tại không được raise exception."""
        try:
            svc.xoa_snapshot("1999-01", "test_user")
        except Exception as e:
            pytest.fail(f"xoa_snapshot raise exception không mong muốn: {e}")

    def test_xoa_clear_cache(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")
        with patch.object(svc, "_clear_snapshot_cache") as clear_mock:
            svc.xoa_snapshot("2026-03", "test_user")
        clear_mock.assert_called_once()


class TestSnapshotServiceHelpers:
    def test_compare_snapshot_2_ky_co_delta(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "u1")
        df2 = df_hstd_gias.copy()
        df2["Ngày số liệu"] = "30/04/2026"
        df2.loc[df2["Tên PGD"] == "PGD Biên Hòa", "Tổng dư nợ"] += 5_000_000.0
        df2["Dư nợ trong hạn"] = df2["Tổng dư nợ"] - df2["Dư nợ quá hạn"]
        svc.luu_snapshot(df2, "u2")

        df_cmp = svc.compare_snapshot_2_ky("2026-03", "2026-04")

        row = df_cmp[df_cmp["ten_pgd"] == "PGD Biên Hòa"].iloc[0]
        assert row["tong_du_no_delta"] == 10_000_000.0
        assert "tong_du_no_pct" in df_cmp.columns

    def test_validate_snapshot_bat_thieu_pgd(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")

        result = svc.validate_snapshot("2026-03")

        assert result["ok"] is False
        assert any("Thiếu dữ liệu" in issue for issue in result["issues"])

    def test_export_snapshot_excel_tra_bytes_xlsx(self, df_hstd_gias, db_memory):
        svc.luu_snapshot(df_hstd_gias, "test_user")

        data = svc.export_snapshot_excel(["2026-03"], "hstd")

        assert data[:2] == b"PK"
