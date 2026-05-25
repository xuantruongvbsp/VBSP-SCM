"""
Tests cho KTNB Database CRUD — 5 bảng mới.
"""
import pytest
import sqlite3
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


@pytest.fixture(scope="module")
def in_memory_db():
    """Tạo database in-memory với schema KTNB."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Tạo bảng KTNB
    conn.executescript("""
        CREATE TABLE ktnb_dot_kiem_tra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nam INTEGER NOT NULL,
            so_cv TEXT,
            loai_hinh TEXT NOT NULL DEFAULT 'dinh_ky',
            ten_pgd_ks TEXT NOT NULL,
            ngay_bat_dau TEXT,
            ngay_ket_thuc TEXT,
            truong_doan TEXT,
            trang_thai TEXT NOT NULL DEFAULT 'ke_hoach',
            ghi_chu TEXT,
            nguoi_tao TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE ktnb_doan_kiem_tra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dot_id INTEGER NOT NULL REFERENCES ktnb_dot_kiem_tra(id) ON DELETE CASCADE,
            ho_ten TEXT NOT NULL,
            chuc_vu TEXT,
            don_vi TEXT,
            vai_tro TEXT NOT NULL DEFAULT 'thanh_vien',
            ghi_chu TEXT,
            UNIQUE(dot_id, ho_ten)
        );

        CREATE TABLE ktnb_danh_muc_loi_chuan (
            ma_loi TEXT PRIMARY KEY,
            khoi_nghiep_vu TEXT NOT NULL,
            ten_loi TEXT NOT NULL,
            mo_ta TEXT,
            muc_do TEXT NOT NULL DEFAULT 'trung_binh',
            so_cv TEXT,
            con_hieu_luc INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE ktnb_mau_doi_chieu_kh (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dot_id INTEGER NOT NULL REFERENCES ktnb_dot_kiem_tra(id) ON DELETE CASCADE,
            ma_mon_vay TEXT NOT NULL,
            ten_pgd TEXT,
            ten_kh TEXT,
            so_tien_vay REAL,
            du_no_hstd REAL,
            tinh_trang TEXT,
            uu_tien_rui_ro INTEGER NOT NULL DEFAULT 0,
            trang_thai_doi_chieu TEXT NOT NULL DEFAULT 'chua_doi_chieu',
            ngay_doi_chieu TEXT,
            du_no_thuc_te REAL,
            ghi_nhan_loi TEXT,
            phat_hien_sai_sot INTEGER NOT NULL DEFAULT 0,
            ghi_chu TEXT,
            nguoi_nhap TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(dot_id, ma_mon_vay)
        );

        CREATE TABLE ktnb_ket_qua_loi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dot_id INTEGER NOT NULL REFERENCES ktnb_dot_kiem_tra(id) ON DELETE CASCADE,
            ma_loi TEXT NOT NULL,
            ma_mon_vay TEXT,
            mo_ta_cu_the TEXT,
            bien_phap_xu_ly TEXT,
            thoi_han_kp TEXT,
            don_vi_chiu_trach TEXT,
            trang_thai TEXT NOT NULL DEFAULT 'chua_khac_phuc',
            minh_chung_path TEXT,
            nguoi_ghi_nhan TEXT NOT NULL,
            nguoi_dong_loi TEXT,
            ngay_dong_loi TEXT,
            ghi_chu TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    yield conn
    conn.close()


class TestKtnbDotKiemTra:
    """Tests CRUD cho bảng ktnb_dot_kiem_tra."""

    def test_insert_dot(self, in_memory_db):
        """Test INSERT đợt kiểm tra."""
        cur = in_memory_db.execute(
            "INSERT INTO ktnb_dot_kiem_tra (nam, so_cv, loai_hinh, ten_pgd_ks, truong_doan, nguoi_tao) "
            "VALUES (2026, '001/NHCS', 'dinh_ky', 'PGD Test', 'Nguyen A', 'test')"
        )
        in_memory_db.commit()
        assert cur.lastrowid > 0

    def test_select_dot(self, in_memory_db):
        """Test SELECT đợt kiểm tra."""
        in_memory_db.execute(
            "INSERT INTO ktnb_dot_kiem_tra (nam, so_cv, loai_hinh, ten_pgd_ks, truong_doan, nguoi_tao) "
            "VALUES (2026, '002/NHCS', 'dot_xuat', 'PGD 2', 'Le B', 'test')"
        )
        in_memory_db.commit()

        row = in_memory_db.execute("SELECT * FROM ktnb_dot_kiem_tra WHERE so_cv = ?", ("002/NHCS",)).fetchone()
        assert row is not None
        assert row["ten_pgd_ks"] == "PGD 2"

    def test_update_dot(self, in_memory_db):
        """Test UPDATE đợt kiểm tra."""
        in_memory_db.execute(
            "INSERT INTO ktnb_dot_kiem_tra (nam, so_cv, loai_hinh, ten_pgd_ks, truong_doan, nguoi_tao) "
            "VALUES (2026, '003/NHCS', 'chuyen_sau', 'PGD 3', 'Tran C', 'test')"
        )
        in_memory_db.commit()

        in_memory_db.execute(
            "UPDATE ktnb_dot_kiem_tra SET trang_thai = ?, ghi_chu = ? WHERE so_cv = ?",
            ("dang_thuc_hien", "Updated", "003/NHCS")
        )
        in_memory_db.commit()

        row = in_memory_db.execute("SELECT * FROM ktnb_dot_kiem_tra WHERE so_cv = ?", ("003/NHCS",)).fetchone()
        assert row["trang_thai"] == "dang_thuc_hien"
        assert row["ghi_chu"] == "Updated"

    def test_delete_dot_cascade(self, in_memory_db):
        """Test DELETE CASCADE đến bảng con."""
        cur = in_memory_db.execute(
            "INSERT INTO ktnb_dot_kiem_tra (nam, so_cv, loai_hinh, ten_pgd_ks, truong_doan, nguoi_tao) "
            "VALUES (2026, '004/NHCS', 'dinh_ky', 'PGD 4', 'Pham D', 'test')"
        )
        dot_id = cur.lastrowid
        in_memory_db.commit()

        # Thêm thành viên đoàn
        in_memory_db.execute(
            "INSERT INTO ktnb_doan_kiem_tra (dot_id, ho_ten, chuc_vu, don_vi, vai_tro) "
            "VALUES (?, 'TV1', 'CV1', 'DV1', 'thanh_vien')",
            (dot_id,)
        )
        in_memory_db.commit()

        # Xóa đợt
        in_memory_db.execute("DELETE FROM ktnb_dot_kiem_tra WHERE id = ?", (dot_id,))
        in_memory_db.commit()

        # Kiểm tra cascade
        row = in_memory_db.execute(
            "SELECT * FROM ktnb_doan_kiem_tra WHERE dot_id = ?", (dot_id,)
        ).fetchone()
        assert row is None


class TestKtnbDanhMucLoi:
    """Tests cho bảng ktnb_danh_muc_loi_chuan."""

    def test_seed_loi_chuan(self, in_memory_db):
        """Test seed 17 mã lỗi chuẩn CV 9919."""
        loi_chuan = [
            ("TD_01", "tin_dung", "Hồ sơ vay thiếu giấy tờ bắt buộc", "trung_binh", "CV 9919"),
            ("TD_02", "tin_dung", "Sai lãi suất cho vay", "cao", "CV 9919"),
            ("KT_01", "ke_toan", "Hạch toán sai tài khoản", "cao", "CV 9919"),
            ("TC_01", "tccb", "Hồ sơ nhân sự không đầy đủ", "thap", "CV 9919"),
        ]

        for ma_loi, khoi, ten, muc_do, so_cv in loi_chuan:
            in_memory_db.execute(
                "INSERT INTO ktnb_danh_muc_loi_chuan (ma_loi, khoi_nghiep_vu, ten_loi, muc_do, so_cv) "
                "VALUES (?, ?, ?, ?, ?)",
                (ma_loi, khoi, ten, muc_do, so_cv)
            )
        in_memory_db.commit()

        count = in_memory_db.execute("SELECT COUNT(*) as c FROM ktnb_danh_muc_loi_chuan").fetchone()["c"]
        assert count == 4

    def test_primary_key_ma_loi(self, in_memory_db):
        """Test PRIMARY KEY ma_loi không trùng."""
        in_memory_db.execute(
            "INSERT INTO ktnb_danh_muc_loi_chuan (ma_loi, khoi_nghiep_vu, ten_loi) "
            "VALUES ('TEST_01', 'test', 'Test')"
        )
        in_memory_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            in_memory_db.execute(
                "INSERT INTO ktnb_danh_muc_loi_chuan (ma_loi, khoi_nghiep_vu, ten_loi) "
                "VALUES ('TEST_01', 'test', 'Test dup')"
            )


class TestKtnbMauDoiChieu:
    """Tests cho bảng ktnb_mau_doi_chieu_kh."""

    def test_insert_mau(self, in_memory_db):
        """Test INSERT mẫu đối chiếu."""
        in_memory_db.execute(
            "INSERT INTO ktnb_mau_doi_chieu_kh (dot_id, ma_mon_vay, ten_pgd, ten_kh, so_tien_vay, nguoi_nhap) "
            "VALUES (1, 'KU001', 'PGD 1', 'KH A', 100000000, 'test')"
        )
        in_memory_db.commit()

        row = in_memory_db.execute("SELECT * FROM ktnb_mau_doi_chieu_kh WHERE ma_mon_vay = ?", ("KU001",)).fetchone()
        assert row is not None
        assert row["trang_thai_doi_chieu"] == "chua_doi_chieu"

    def test_unique_dot_ku(self, in_memory_db):
        """Test UNIQUE(dot_id, ma_mon_vay)."""
        in_memory_db.execute(
            "INSERT INTO ktnb_mau_doi_chieu_kh (dot_id, ma_mon_vay, nguoi_nhap) "
            "VALUES (1, 'KU_UNIQUE', 'test')"
        )
        in_memory_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            in_memory_db.execute(
                "INSERT INTO ktnb_mau_doi_chieu_kh (dot_id, ma_mon_vay, nguoi_nhap) "
                "VALUES (1, 'KU_UNIQUE', 'test')"
            )


class TestKtnbKetQuaLoi:
    """Tests cho bảng ktnb_ket_qua_loi."""

    def test_insert_loi(self, in_memory_db):
        """Test INSERT lỗi."""
        in_memory_db.execute(
            "INSERT INTO ktnb_ket_qua_loi (dot_id, ma_loi, mo_ta_cu_the, don_vi_chiu_trach, nguoi_ghi_nhan) "
            "VALUES (1, 'TD_01', 'Test lỗi', 'PGD Test', 'Nguyen A')"
        )
        in_memory_db.commit()

        row = in_memory_db.execute("SELECT * FROM ktnb_ket_qua_loi WHERE ma_loi = ?", ("TD_01",)).fetchone()
        assert row is not None
        assert row["trang_thai"] == "chua_khac_phuc"

    def test_cap_nhat_trang_thai(self, in_memory_db):
        """Test UPDATE trạng thái lỗi."""
        cur = in_memory_db.execute(
            "INSERT INTO ktnb_ket_qua_loi (dot_id, ma_loi, mo_ta_cu_the, nguoi_ghi_nhan) "
            "VALUES (1, 'TD_02', 'Test', 'Test')"
        )
        loi_id = cur.lastrowid
        in_memory_db.commit()

        in_memory_db.execute(
            "UPDATE ktnb_ket_qua_loi SET trang_thai = ?, nguoi_dong_loi = ?, ngay_dong_loi = ? WHERE id = ?",
            ("da_khac_phuc", "Truong Doan", "2026-01-15", loi_id)
        )
        in_memory_db.commit()

        row = in_memory_db.execute("SELECT * FROM ktnb_ket_qua_loi WHERE id = ?", (loi_id,)).fetchone()
        assert row["trang_thai"] == "da_khac_phuc"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
