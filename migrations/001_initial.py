"""Migration 001: Tạo toàn bộ bảng và index ban đầu."""
import sqlite3

VERSION = 1

_SCHEMA_SQL = """
            CREATE TABLE IF NOT EXISTS users (
                username   TEXT PRIMARY KEY,
                ho_ten     TEXT NOT NULL,
                password   TEXT NOT NULL,
                role       TEXT NOT NULL DEFAULT 'user',
                pgd        TEXT,
                ngay_tao   TEXT,
                ngay_doi_mk TEXT
            );
            CREATE TABLE IF NOT EXISTS kv_store (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT,
                updated_by TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_kv_key ON kv_store(key);
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         TEXT NOT NULL,
                username   TEXT NOT NULL DEFAULT 'system',
                action     TEXT NOT NULL,
                detail     TEXT,
                table_name TEXT,
                record_id  TEXT,
                old_value  TEXT,
                new_value  TEXT,
                ip_address TEXT,
                user_agent TEXT
            );
            CREATE TABLE IF NOT EXISTS nhiem_vu (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tieu_de       TEXT NOT NULL,
                mo_ta         TEXT,
                chu_ky        TEXT NOT NULL,
                ky            TEXT NOT NULL,
                pgd           TEXT,
                trang_thai    TEXT NOT NULL DEFAULT 'cho_thuc_hien',
                nguoi_tao     TEXT NOT NULL,
                ngay_tao      TEXT NOT NULL,
                ngay_deadline TEXT,
                ghi_chu_kh    TEXT
            );
            CREATE TABLE IF NOT EXISTS nhiem_vu_ketqua (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                nhiem_vu_id   INTEGER NOT NULL REFERENCES nhiem_vu(id) ON DELETE CASCADE,
                pgd           TEXT NOT NULL,
                noi_dung_th   TEXT,
                so_lieu       TEXT,
                trang_thai    TEXT NOT NULL DEFAULT 'cho_duyet',
                nguoi_nhap    TEXT NOT NULL,
                ngay_nhap     TEXT NOT NULL,
                nguoi_duyet   TEXT,
                ngay_duyet    TEXT,
                y_kien_duyet  TEXT,
                UNIQUE(nhiem_vu_id, pgd)
            );
            CREATE TABLE IF NOT EXISTS kv_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT    NOT NULL,
                value       TEXT,
                changed_by  TEXT,
                changed_at  TEXT DEFAULT (datetime('now','localtime')),
                note        TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_kv_history_key ON kv_history(key);
            CREATE TABLE IF NOT EXISTS tien_do_task (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tieu_de       TEXT NOT NULL,
                mo_ta         TEXT,
                ngay_deadline TEXT NOT NULL,
                ds_pgd        TEXT NOT NULL DEFAULT '[]',
                loai          TEXT NOT NULL DEFAULT 'chung',
                uu_tien       TEXT NOT NULL DEFAULT 'binh_thuong',
                nguoi_tao     TEXT NOT NULL,
                ngay_tao      TEXT NOT NULL,
                trang_thai    TEXT NOT NULL DEFAULT 'dang_theo_doi',
                ghi_chu       TEXT,
                cap_theo_doi  TEXT NOT NULL DEFAULT 'xa',
                ngay_bat_dau  TEXT,
                nguoi_phu_trach TEXT,
                nguoi_thuc_hien_cn TEXT DEFAULT '',
                cbtd_bien_hoa TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_tiendo_deadline ON tien_do_task(ngay_deadline);
            CREATE TABLE IF NOT EXISTS tien_do_ketqua (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         INTEGER NOT NULL REFERENCES tien_do_task(id) ON DELETE CASCADE,
                pgd             TEXT NOT NULL,
                ten_xa          TEXT NOT NULL,
                trang_thai      TEXT NOT NULL DEFAULT 'chua_thuc_hien',
                ngay_hoan_thanh TEXT,
                ghi_chu         TEXT,
                nguoi_nhap      TEXT,
                ngay_nhap       TEXT,
                UNIQUE(task_id, ten_xa)
            );
            CREATE INDEX IF NOT EXISTS idx_tiendo_kq_task ON tien_do_ketqua(task_id);
            CREATE INDEX IF NOT EXISTS idx_tiendo_kq_pgd ON tien_do_ketqua(task_id, pgd);

            CREATE TABLE IF NOT EXISTS tien_do_template (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ten             TEXT NOT NULL,
                mo_ta           TEXT,
                loai            TEXT,
                uu_tien         TEXT DEFAULT 'binh_thuong',
                cap_theo_doi    TEXT DEFAULT 'xa',
                so_ngay_deadline INTEGER DEFAULT 30,
                nguoi_tao       TEXT,
                ngay_tao        TEXT
            );
            CREATE TABLE IF NOT EXISTS tien_do_lich_su (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         INTEGER NOT NULL,
                ten_xa          TEXT NOT NULL,
                pgd             TEXT,
                trang_thai_cu   TEXT,
                trang_thai_moi  TEXT,
                pct_cu          INTEGER,
                pct_moi         INTEGER,
                ghi_chu         TEXT,
                nguoi_nhap      TEXT,
                ngay_nhap       TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tiendo_ls_task ON tien_do_lich_su(task_id);

            CREATE TABLE IF NOT EXISTS hstd_snapshot (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ky           TEXT    NOT NULL,
                ten_pgd      TEXT    NOT NULL,
                ma_ct        TEXT    NOT NULL DEFAULT 'ALL',
                nguon_von    TEXT    NOT NULL DEFAULT 'ALL',
                tong_du_no   REAL    NOT NULL DEFAULT 0,
                du_no_th     REAL    NOT NULL DEFAULT 0,
                du_no_qh     REAL    NOT NULL DEFAULT 0,
                du_no_khoanh REAL    NOT NULL DEFAULT 0,
                so_ho        INTEGER NOT NULL DEFAULT 0,
                so_ku        INTEGER NOT NULL DEFAULT 0,
                gn_nam       REAL    NOT NULL DEFAULT 0,
                ngay_so_lieu TEXT,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                created_by   TEXT    NOT NULL DEFAULT 'system',
                UNIQUE(ky, ten_pgd, ma_ct, nguon_von)
            );
            CREATE INDEX IF NOT EXISTS idx_snapshot_ky     ON hstd_snapshot(ky);
            CREATE INDEX IF NOT EXISTS idx_snapshot_pgd    ON hstd_snapshot(ky, ten_pgd);

            CREATE TABLE IF NOT EXISTS uy_thac_snapshot (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ky           TEXT    NOT NULL,
                cap_tong_hop TEXT    NOT NULL,
                ten_pgd      TEXT    NOT NULL DEFAULT '__ALL__',
                ten_xa       TEXT    NOT NULL DEFAULT '__ALL__',
                dvut         TEXT    NOT NULL DEFAULT '__ALL__',
                ten_to       TEXT    NOT NULL DEFAULT '__ALL__',
                tong_du_no   REAL    NOT NULL DEFAULT 0,
                du_no_qh     REAL    NOT NULL DEFAULT 0,
                lai_ton      REAL    NOT NULL DEFAULT 0,
                so_du_tg     REAL    NOT NULL DEFAULT 0,
                so_kh        INTEGER NOT NULL DEFAULT 0,
                so_ku        INTEGER NOT NULL DEFAULT 0,
                so_to        INTEGER NOT NULL DEFAULT 0,
                ngay_so_lieu TEXT,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                created_by   TEXT    NOT NULL DEFAULT 'system',
                UNIQUE(ky, cap_tong_hop, ten_pgd, ten_xa, dvut, ten_to)
            );
            CREATE INDEX IF NOT EXISTS idx_uy_thac_snap_ky
                ON uy_thac_snapshot(ky, cap_tong_hop);
            CREATE INDEX IF NOT EXISTS idx_uy_thac_snap_pgd
                ON uy_thac_snapshot(ky, ten_pgd);

            CREATE TABLE IF NOT EXISTS nq11_snapshot (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ky           TEXT    NOT NULL,
                ten_pgd      TEXT    NOT NULL DEFAULT '__CN__',
                tong_du_no   REAL    NOT NULL DEFAULT 0,
                no_th        REAL    NOT NULL DEFAULT 0,
                no_qh        REAL    NOT NULL DEFAULT 0,
                so_kh        INTEGER NOT NULL DEFAULT 0,
                gn_nam       REAL    NOT NULL DEFAULT 0,
                ngay_bc      TEXT,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                created_by   TEXT    NOT NULL DEFAULT 'system',
                UNIQUE(ky, ten_pgd)
            );
            CREATE INDEX IF NOT EXISTS idx_nq11_snap_ky  ON nq11_snapshot(ky);
            CREATE INDEX IF NOT EXISTS idx_nq11_snap_pgd ON nq11_snapshot(ky, ten_pgd);

            CREATE TABLE IF NOT EXISTS gqvl_snapshot (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ky           TEXT    NOT NULL,
                ten_pgd      TEXT    NOT NULL DEFAULT '__CN__',
                dn_th        REAL    NOT NULL DEFAULT 0,
                dn_qh        REAL    NOT NULL DEFAULT 0,
                dn_khoanh    REAL    NOT NULL DEFAULT 0,
                so_kh        INTEGER NOT NULL DEFAULT 0,
                gn_nam       REAL    NOT NULL DEFAULT 0,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                created_by   TEXT    NOT NULL DEFAULT 'system',
                UNIQUE(ky, ten_pgd)
            );
            CREATE INDEX IF NOT EXISTS idx_gqvl_snap_ky  ON gqvl_snapshot(ky);
            CREATE INDEX IF NOT EXISTS idx_gqvl_snap_pgd ON gqvl_snapshot(ky, ten_pgd);

            CREATE TABLE IF NOT EXISTS cdtotkvv_snapshot (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ky           TEXT    NOT NULL,
                ten_pgd      TEXT    NOT NULL DEFAULT '__CN__',
                so_to        INTEGER NOT NULL DEFAULT 0,
                so_tot       INTEGER NOT NULL DEFAULT 0,
                so_kha       INTEGER NOT NULL DEFAULT 0,
                so_tb        INTEGER NOT NULL DEFAULT 0,
                so_yeu       INTEGER NOT NULL DEFAULT 0,
                diem_tb      REAL    NOT NULL DEFAULT 0,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                created_by   TEXT    NOT NULL DEFAULT 'system',
                UNIQUE(ky, ten_pgd)
            );
            CREATE INDEX IF NOT EXISTS idx_cdtotkvv_snap_ky  ON cdtotkvv_snapshot(ky);
            CREATE INDEX IF NOT EXISTS idx_cdtotkvv_snap_pgd ON cdtotkvv_snapshot(ky, ten_pgd);

            CREATE TABLE IF NOT EXISTS qlnk_ket_qua (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                ma_mon_vay              TEXT    NOT NULL,
                ten_pgd                 TEXT    NOT NULL,
                ten_xa                  TEXT,
                ten_to_tkv              TEXT,
                ten_kh                  TEXT,
                ngay_bat_dau_khoanh     TEXT,
                so_thang_khoanh         INTEGER,
                so_quyet_dinh_khoanh    TEXT,
                ngay_kiem_tra           TEXT    NOT NULL,
                ngay_het_han_khoanh     TEXT,
                can_bo_kiem_tra         TEXT,
                du_no_goc               REAL    DEFAULT 0,
                du_no_goc_khoanh        REAL    DEFAULT 0,
                so_tien_lai_con_no      REAL    DEFAULT 0,
                du_no_goc_thuc_te       REAL    DEFAULT 0,
                du_no_khoanh_thuc_te    REAL    DEFAULT 0,
                so_tien_lai_thuc_te     REAL    DEFAULT 0,
                chenh_lech              REAL    DEFAULT 0,
                ly_do_chenh_lech        TEXT,
                thuc_trang_du_an        TEXT,
                tinh_hinh_khach_hang    TEXT,
                kha_nang_tra_no         TEXT,
                cam_ket_tra_no          TEXT,
                trang_thai              TEXT    NOT NULL DEFAULT 'luu_tam',
                nguoi_nhap              TEXT    NOT NULL,
                nguoi_phe_duyet         TEXT,
                ngay_phe_duyet          TEXT,
                created_at              TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at              TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_qlnk_kq_ma_mon  ON qlnk_ket_qua(ma_mon_vay);
            CREATE INDEX IF NOT EXISTS idx_qlnk_kq_pgd     ON qlnk_ket_qua(ten_pgd);
            CREATE INDEX IF NOT EXISTS idx_qlnk_kq_ngay_kt ON qlnk_ket_qua(ngay_kiem_tra);
            CREATE INDEX IF NOT EXISTS idx_qlnk_kq_tt      ON qlnk_ket_qua(trang_thai);

            CREATE TABLE IF NOT EXISTS qlnk_bo_sung (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                ma_mon_vay              TEXT    NOT NULL UNIQUE,
                ten_pgd                 TEXT    NOT NULL,
                ngay_bat_dau_khoanh     TEXT,
                so_thang_khoanh         INTEGER,
                so_quyet_dinh_khoanh    TEXT,
                ghi_chu                 TEXT,
                nguoi_cap_nhat          TEXT,
                updated_at              TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_qlnk_bs_ma ON qlnk_bo_sung(ma_mon_vay);

            CREATE TABLE IF NOT EXISTS qlnk_ke_hoach (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                ten_pgd           TEXT NOT NULL,
                nam               INTEGER NOT NULL DEFAULT 0,
                thanh_phan_doan   TEXT NOT NULL DEFAULT '[]',
                ds_phan_cong      TEXT NOT NULL DEFAULT '[]',
                ghi_chu           TEXT,
                ngay_kiem_tra     TEXT,
                trang_thai        TEXT NOT NULL DEFAULT 'luu_tam',
                nguoi_lap         TEXT NOT NULL,
                nguoi_duyet       TEXT,
                ngay_duyet        TEXT,
                created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_qlnk_kh_pgd  ON qlnk_ke_hoach(ten_pgd);
            CREATE INDEX IF NOT EXISTS idx_qlnk_kh_tt   ON qlnk_ke_hoach(trang_thai);

            CREATE TABLE IF NOT EXISTS mau_bieu_cv368 (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                loai_mau    TEXT NOT NULL,
                ten_pgd     TEXT NOT NULL,
                nam         INTEGER NOT NULL,
                dot         INTEGER DEFAULT 1,
                noi_dung    TEXT NOT NULL,
                nguoi_lap   TEXT,
                ngay_lap    TEXT,
                ghi_chu     TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_mbcv368_pgd_loai_nam
                ON mau_bieu_cv368(ten_pgd, loai_mau, nam);

            CREATE TABLE IF NOT EXISTS ktnb_dot_kiem_tra (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                nam             INTEGER NOT NULL,
                so_cv           TEXT,
                loai_hinh       TEXT NOT NULL DEFAULT 'dinh_ky',
                ten_pgd_ks      TEXT NOT NULL,
                ngay_bat_dau    TEXT,
                ngay_ket_thuc   TEXT,
                truong_doan     TEXT,
                trang_thai      TEXT NOT NULL DEFAULT 'ke_hoach',
                ghi_chu         TEXT,
                nguoi_tao       TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_ktnb_dot_nam ON ktnb_dot_kiem_tra(nam);
            CREATE INDEX IF NOT EXISTS idx_ktnb_dot_pgd ON ktnb_dot_kiem_tra(ten_pgd_ks);

            CREATE TABLE IF NOT EXISTS ktnb_doan_kiem_tra (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dot_id          INTEGER NOT NULL REFERENCES ktnb_dot_kiem_tra(id) ON DELETE CASCADE,
                ho_ten          TEXT NOT NULL,
                chuc_vu         TEXT,
                don_vi          TEXT,
                vai_tro         TEXT NOT NULL DEFAULT 'thanh_vien',
                ghi_chu         TEXT,
                UNIQUE(dot_id, ho_ten)
            );
            CREATE INDEX IF NOT EXISTS idx_ktnb_doan_dot ON ktnb_doan_kiem_tra(dot_id);

            CREATE TABLE IF NOT EXISTS ktnb_danh_muc_loi_chuan (
                ma_loi          TEXT PRIMARY KEY,
                khoi_nghiep_vu  TEXT NOT NULL,
                ten_loi         TEXT NOT NULL,
                mo_ta           TEXT,
                muc_do          TEXT NOT NULL DEFAULT 'trung_binh',
                so_cv           TEXT,
                con_hieu_luc    INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS ktnb_mau_doi_chieu_kh (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dot_id          INTEGER NOT NULL REFERENCES ktnb_dot_kiem_tra(id) ON DELETE CASCADE,
                ma_mon_vay      TEXT NOT NULL,
                ten_pgd         TEXT,
                ten_kh          TEXT,
                so_tien_vay     REAL,
                du_no_hstd      REAL,
                tinh_trang      TEXT,
                uu_tien_rui_ro  INTEGER NOT NULL DEFAULT 0,
                trang_thai_doi_chieu TEXT NOT NULL DEFAULT 'chua_doi_chieu',
                ngay_doi_chieu  TEXT,
                du_no_thuc_te   REAL,
                ghi_nhan_loi    TEXT,
                phat_hien_sai_sot INTEGER NOT NULL DEFAULT 0,
                ghi_chu         TEXT,
                nguoi_nhap      TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                UNIQUE(dot_id, ma_mon_vay)
            );
            CREATE INDEX IF NOT EXISTS idx_ktnb_mau_dot ON ktnb_mau_doi_chieu_kh(dot_id);
            CREATE INDEX IF NOT EXISTS idx_ktnb_mau_ma ON ktnb_mau_doi_chieu_kh(ma_mon_vay);

            CREATE TABLE IF NOT EXISTS ktnb_ket_qua_loi (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dot_id          INTEGER NOT NULL REFERENCES ktnb_dot_kiem_tra(id) ON DELETE CASCADE,
                ma_loi          TEXT NOT NULL REFERENCES ktnb_danh_muc_loi_chuan(ma_loi),
                ma_mon_vay      TEXT,
                mo_ta_cu_the    TEXT,
                bien_phap_xu_ly TEXT,
                thoi_han_kp     TEXT,
                don_vi_chiu_trach TEXT,
                trang_thai      TEXT NOT NULL DEFAULT 'chua_khac_phuc',
                minh_chung_path TEXT,
                nguoi_ghi_nhan  TEXT NOT NULL,
                nguoi_dong_loi  TEXT,
                ngay_dong_loi   TEXT,
                ghi_chu         TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_ktnb_loi_dot     ON ktnb_ket_qua_loi(dot_id);
            CREATE INDEX IF NOT EXISTS idx_ktnb_loi_ma      ON ktnb_ket_qua_loi(ma_loi);
            CREATE INDEX IF NOT EXISTS idx_ktnb_loi_trang_thai ON ktnb_ket_qua_loi(trang_thai);

            CREATE TABLE IF NOT EXISTS loan_notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ma_so_ku   TEXT NOT NULL,
                ghi_chu    TEXT NOT NULL,
                username   TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_loan_notes_ku ON loan_notes(ma_so_ku);
"""


def upgrade(conn: sqlite3.Connection) -> None:
    for statement in _SCHEMA_SQL.split(";"):
        sql = statement.strip()
        if not sql:
            continue
        try:
            conn.execute(sql)
        except sqlite3.OperationalError as e:
            is_index = sql.upper().startswith("CREATE INDEX")
            if is_index and "no such column" in str(e).lower():
                continue
            raise
    # Tạo index cho audit_log (sau executescript để tránh lỗi)
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_table_record ON audit_log(table_name, record_id)")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ip ON audit_log(ip_address)")
    except sqlite3.OperationalError:
        pass
