"""Migration 002: Thêm cột mới cho các bảng (backward compatibility với DB cũ)."""
import sqlite3

VERSION = 2


def upgrade(conn: sqlite3.Connection) -> None:
    try:
        conn.execute(
            "ALTER TABLE tien_do_task ADD COLUMN cap_theo_doi TEXT NOT NULL DEFAULT 'xa'"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE tien_do_ketqua ADD COLUMN loai_noi_dung TEXT"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE tien_do_task ADD COLUMN ngay_bat_dau TEXT"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE tien_do_task ADD COLUMN nguoi_phu_trach TEXT"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE tien_do_task ADD COLUMN nguoi_thuc_hien_cn TEXT DEFAULT ''"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE tien_do_task ADD COLUMN cbtd_bien_hoa TEXT DEFAULT ''"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE qlnk_ket_qua ADD COLUMN ngay_het_han_khoanh TEXT"
        )
    except sqlite3.OperationalError:
        pass
    for _col, _typ in [
        ("nguoi_duyet",   "TEXT"),
        ("ngay_duyet",    "TEXT"),
        ("ghi_chu",       "TEXT"),
        ("nam",           "INTEGER NOT NULL DEFAULT 0"),
        ("ds_phan_cong",  "TEXT NOT NULL DEFAULT '[]'"),
        ("thanh_phan_doan", "TEXT NOT NULL DEFAULT '[]'"),
        ("ngay_kiem_tra", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE qlnk_ke_hoach ADD COLUMN {_col} {_typ}")
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_qlnk_kh_ngay ON qlnk_ke_hoach(ngay_kiem_tra)"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE users ADD COLUMN ngay_doi_mk TEXT"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE tien_do_ketqua ADD COLUMN pct_hoan_thanh INTEGER DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE nhiem_vu ADD COLUMN uu_tien TEXT DEFAULT 'binh_thuong'"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE nhiem_vu ADD COLUMN loai TEXT DEFAULT 'chung'"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE nhiem_vu_ketqua ADD COLUMN file_path TEXT"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE nhiem_vu_ketqua ADD COLUMN file_name TEXT"
        )
    except sqlite3.OperationalError:
        pass

    # Migration: Mở rộng audit_log cho NHCSXH compliance
    for col, typ in [
        ("table_name", "TEXT"),
        ("record_id", "TEXT"),
        ("old_value", "TEXT"),
        ("new_value", "TEXT"),
        ("ip_address", "TEXT"),
        ("user_agent", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE audit_log ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
