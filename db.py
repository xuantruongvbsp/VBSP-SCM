import sqlite3
import json
import os
import threading
import atexit
from datetime import datetime
from pathlib import Path
from typing import Any
from config import BASE_DIR

_local = threading.local()


def get_db_path() -> str:
    return os.getenv("VBSP_SCM_DB_PATH") or str(BASE_DIR / "vbsp_scm.db")


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.Error:
            _close_thread_conn()

    conn = sqlite3.connect(get_db_path(), check_same_thread=False, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    conn.row_factory = sqlite3.Row
    _local.conn = conn
    return conn


def _close_thread_conn() -> None:
    conn = getattr(_local, "conn", None)
    if conn is None:
        return
    try:
        conn.close()
    except sqlite3.Error:
        pass
    finally:
        _local.conn = None


def reset_conn() -> None:
    _close_thread_conn()


atexit.register(_close_thread_conn)


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username   TEXT PRIMARY KEY,
                ho_ten     TEXT NOT NULL,
                password   TEXT NOT NULL,
                role       TEXT NOT NULL DEFAULT 'user',
                pgd        TEXT,
                ngay_tao   TEXT
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
                detail     TEXT
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
        """)
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
        conn.commit()


def ghi_kv(key: str, value: dict, username: str = "system", note: str = None) -> None:
    """Ghi hoặc cập nhật một cặp key-value vào bảng kv_store."""
    try:
        with get_conn() as conn:
            old_row = conn.execute(
                "SELECT value FROM kv_store WHERE key = ?", (key,)
            ).fetchone()
            new_value_str = json.dumps(value, ensure_ascii=False)
            if old_row and old_row["value"] != new_value_str:
                conn.execute(
                    """INSERT INTO kv_history (key, value, changed_by, note)
                       VALUES (?, ?, ?, ?)""",
                    (key, old_row["value"], username, note),
                )
            conn.execute(
                """INSERT OR REPLACE INTO kv_store (key, value, updated_at, updated_by)
                   VALUES (?, ?, ?, ?)""",
                (key, new_value_str,
                 datetime.now().isoformat(), username),
            )
            conn.commit()
    except Exception:
        pass


def doc_kv(key: str, default=None):
    """Đọc giá trị từ kv_store theo key. Trả về default nếu không tìm thấy."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM kv_store WHERE key = ?", (key,)
            ).fetchone()
        if row:
            return json.loads(row["value"])
        return default
    except Exception:
        return default


def list_kv_prefix(prefix: str) -> list[str]:
    """Trả về danh sách key trong kv_store có tiền tố `prefix` (SQL LIKE prefix%)."""
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT key FROM kv_store WHERE key LIKE ?",
                (prefix + "%",),
            ).fetchall()
        return [r["key"] for r in rows]
    except Exception:
        return []


def doc_kv_prefix(prefix: str) -> dict[str, Any]:
    """
    Đọc tất cả các cặp key-value có key bắt đầu bằng prefix từ kv_store.

    Dùng SQL WHERE key LIKE 'prefix%' — tận dụng index idx_kv_key, không
    load toàn bảng về Python. Phù hợp cho các truy vấn như:
        doc_kv_prefix("khtd_pgd_")   → tất cả kế hoạch của 21 PGD
        doc_kv_prefix("khtd_")      → tất cả dữ liệu KHTD/điều chỉnh theo đợt
        doc_kv_prefix("ct_registry_")→ tất cả registry chương trình

    Trả về dict: {key: value_đã_parse_json, ...}
    Nếu không có kết quả, trả về dict rỗng {}.
    """
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT key, value FROM kv_store WHERE key LIKE ?",
                (prefix + "%",),
            ).fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}
    except Exception:
        return {}


def doc_kv_nhieu(keys: list[str]) -> dict[str, Any]:
    """
    Đọc nhiều key cùng lúc bằng một câu lệnh SQL duy nhất (IN clause).

    Hiệu quả hơn nhiều lần gọi doc_kv() riêng lẻ khi cần đọc
    dữ liệu của nhiều PGD trong một lần.

    Trả về dict: {key: value_đã_parse, ...} — chỉ các key tồn tại.
    """
    if not keys:
        return {}
    try:
        placeholders = ",".join("?" * len(keys))
        with get_conn() as conn:
            rows = conn.execute(
                f"SELECT key, value FROM kv_store WHERE key IN ({placeholders})",
                keys,
            ).fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}
    except Exception:
        return {}


def doc_kv_history(key: str, limit: int = 10) -> list[dict]:
    """
    Đọc lịch sử thay đổi của một key từ bảng kv_history.

    Trả về list[dict] với các khóa: id, value, changed_by, changed_at, note.
    Nếu không có lịch sử → trả về [].
    """
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT id, value, changed_by, changed_at, note
                   FROM kv_history WHERE key = ?
                   ORDER BY id DESC LIMIT ?""",
                (key, limit),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


def khoi_phuc_kv(key: str, history_id: int, username: str) -> bool:
    """
    Khôi phục giá trị của một key từ lịch sử theo history_id.

    Trả về True nếu thành công, False nếu không tìm thấy id.
    """
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM kv_history WHERE id = ? AND key = ?",
                (history_id, key),
            ).fetchone()
        if not row:
            return False
        value_cu = json.loads(row["value"])
        ghi_kv(key, value_cu, username, note=f"Khôi phục từ phiên bản #{history_id}")
        ghi_audit(username, "khoi_phuc_kv", f"key={key}, history_id={history_id}")
        return True
    except Exception:
        return False


def ghi_audit(username: str, action: str, detail: str = "") -> None:
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (ts, username, action, detail) VALUES (?,?,?,?)",
                (datetime.now().isoformat(), username, action, detail)
            )
            conn.commit()
    except Exception:
        pass


def seed_dynamic_configs() -> None:
    """
    Khởi tạo các cấu hình động từ config.py vào kv_store nếu chưa tồn tại.
    Chạy an toàn nhiều lần — chỉ INSERT khi key chưa có, không ghi đè dữ liệu
    đã được Admin chỉnh sửa qua giao diện.
    """
    from config import DS_PGD, MA_PGD_MAP, PGD_XA_MAP, CHUONG_TRINH_KHTD

    # CHUONG_TRINH_KHTD là list of tuples → chuyển sang list of lists để JSON thuần
    ct_as_list = [list(row) for row in CHUONG_TRINH_KHTD]

    configs_mac_dinh: dict = {
        "ds_pgd":             DS_PGD,
        "ma_pgd_map":         MA_PGD_MAP,
        "pgd_xa_map":         PGD_XA_MAP,
        "chuong_trinh_khtd":  ct_as_list,
    }

    try:
        with get_conn() as conn:
            for key, value in configs_mac_dinh.items():
                exists = conn.execute(
                    "SELECT 1 FROM kv_store WHERE key = ?", (key,)
                ).fetchone()
                if not exists:
                    conn.execute(
                        """INSERT INTO kv_store (key, value, updated_at, updated_by)
                           VALUES (?, ?, ?, ?)""",
                        (key, json.dumps(value, ensure_ascii=False),
                         datetime.now().isoformat(), "system"),
                    )
            conn.commit()
        ghi_audit("system", "seed_configs", "seeded dynamic configs vào kv_store")
    except Exception as e:
        ghi_audit("system", "seed_configs_error", str(e))


def doc_dgd_map() -> dict:
    """
    Đọc cấu hình mapping Điểm giao dịch từ kv_store.
    Trả về dict có cấu trúc: {"PGD": {"Xã": {"Điểm GD": ["Ấp 1", "Ấp 2"]}}}
    """
    return doc_kv("dgd_map", {})


def luu_dgd_map(data: dict, username: str) -> None:
    """
    Lưu cấu hình mapping Điểm giao dịch vào kv_store và ghi audit log.
    
    Args:
        data: Dict mapping điểm giao dịch với cấu trúc PGD -> Xã -> Điểm GD -> [Thôn/Ấp]
        username: Tên người dùng thực hiện cập nhật
    """
    try:
        ghi_kv("dgd_map", data, username)
        ghi_audit(username, "cap_nhat_dgd_map", f"Cập nhật mapping điểm giao dịch - Số PGD: {len(data)}")
    except Exception as e:
        ghi_audit(username, "loi_dgd_map", f"Lỗi cập nhật mapping điểm giao dịch: {str(e)}")
        raise


def migrate_from_json():
    """
    Migrate dữ liệu từ các file JSON cũ vào SQLite.
    Chạy an toàn nhiều lần (INSERT OR IGNORE).
    Sau khi migrate xong đổi tên file .json → .json.bak (không xóa).
    """
    with get_conn() as conn:
        # ── Migrate users.json ──────────────────────────────────────
        users_path = str(BASE_DIR / "users.json")
        if os.path.exists(users_path):
            try:
                with open(users_path, "r", encoding="utf-8") as f:
                    users = json.load(f)
                for username, info in users.items():
                    conn.execute(
                        """INSERT OR IGNORE INTO users
                           (username, ho_ten, password, role, pgd, ngay_tao)
                           VALUES (?,?,?,?,?,?)""",
                        (
                            username,
                            info.get("ho_ten", ""),
                            info.get("password", ""),
                            info.get("role", "user"),
                            info.get("pgd"),
                            info.get("ngay_tao", ""),
                        )
                    )
                conn.commit()
                os.rename(users_path, users_path + ".bak")
                ghi_audit("system", "migrate_json", "migrated users.json")
            except Exception as e:
                ghi_audit("system", "migrate_error", f"users.json: {e}")

        # ── Migrate các file JSON kv_store ──────────────────────────
        kv_files = {
            "khtd":    str(BASE_DIR / "khtd.json"),
            "kehoach": str(BASE_DIR / "kehoach.json"),
            "cbtd":    str(BASE_DIR / "cbtd.json"),
        }
        for key, path in kv_files.items():
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    conn.execute(
                        """INSERT OR REPLACE INTO kv_store
                           (key, value, updated_at, updated_by)
                           VALUES (?,?,?,?)""",
                        (key, json.dumps(data, ensure_ascii=False),
                         datetime.now().isoformat(), "system")
                    )
                    conn.commit()
                    os.rename(path, path + ".bak")
                    ghi_audit("system", "migrate_json", f"migrated {key}.json")
                except Exception as e:
                    ghi_audit("system", "migrate_error", f"{key}.json: {e}")


def migrate_pgd_bien_hoa() -> None:
    """
    Migration: Tách slot dữ liệu PGD Biên Hòa khỏi slot merge toàn CN.
    Cập nhật pgd_user cho CBTD Biên Hòa từ 'Hội sở Chi nhánh tỉnh' sang 'PGD Biên Hòa'.
    Chỉ áp dụng cho user có role='user' (CBTD địa bàn), không áp dụng cho admin/manager.
    """
    try:
        with get_conn() as conn:
            # Cập nhật user có pgd='Hội sở Chi nhánh tỉnh' và role='user'
            # sang pgd='PGD Biên Hòa'
            cursor = conn.execute(
                """UPDATE users
                   SET pgd = ?
                   WHERE pgd = ?
                   AND role = ?""",
                ("PGD Biên Hòa", "Hội sở Chi nhánh tỉnh", "user")
            )
            conn.commit()
            so_dong_cap_nhat = cursor.rowcount
            if so_dong_cap_nhat > 0:
                ghi_audit(
                    "system",
                    "migrate_pgd_bien_hoa",
                    f"Đã cập nhật {so_dong_cap_nhat} user từ 'Hội sở Chi nhánh tỉnh' sang 'PGD Biên Hòa'"
                )
    except Exception as e:
        ghi_audit("system", "migrate_pgd_bien_hoa_error", str(e))


def doc_ndt_dp_list() -> list[dict]:
    """
    Đọc danh sách Mã NĐT địa phương từ kv_store.
    Mỗi phần tử: {"ma": "INV...", "ghi_chu": "...", "cap": "tinh"|"xa"}
    Fallback về seed data nếu chưa có.
    """
    val = doc_kv("ndt_dp_list")
    if val and isinstance(val, list) and len(val) > 0:
        # Đảm bảo backward compat: bổ sung "cap" nếu phần tử cũ chưa có
        for item in val:
            item.setdefault("cap", "tinh")
        return val
    # Seed mặc định
    return [
        {"ma": "INV0802140002662", "ghi_chu": "UBND tỉnh Đồng Nai",              "cap": "tinh"},
        {"ma": "INV0603170027393", "ghi_chu": "Nguồn vốn cho vay đào tạo nghề",  "cap": "tinh"},
    ]


def doc_ndt_dp_ma_list() -> list[str]:
    """Trả về list mã Cấp Tỉnh (str) để dùng trong phân tầng GQVL."""
    return [item["ma"] for item in doc_ndt_dp_list() if item.get("cap", "tinh") == "tinh"]


# ══════════════════════════════════════════════════════════════════════════════
# QLNK — Quản lý nợ khoanh
# ══════════════════════════════════════════════════════════════════════════════

_QLNK_KQ_COLS = [
    "id", "ma_mon_vay", "ten_pgd", "ten_xa", "ten_to_tkv", "ten_kh",
    "ngay_bat_dau_khoanh", "so_thang_khoanh", "so_quyet_dinh_khoanh",
    "ngay_kiem_tra", "ngay_het_han_khoanh", "can_bo_kiem_tra",
    "du_no_goc", "du_no_goc_khoanh", "so_tien_lai_con_no",
    "du_no_goc_thuc_te", "du_no_khoanh_thuc_te", "so_tien_lai_thuc_te",
    "chenh_lech", "ly_do_chenh_lech",
    "thuc_trang_du_an", "tinh_hinh_khach_hang", "kha_nang_tra_no", "cam_ket_tra_no",
    "trang_thai", "nguoi_nhap", "nguoi_phe_duyet", "ngay_phe_duyet",
    "created_at", "updated_at",
]


def luu_ket_qua_kiem_tra(data: dict, username: str) -> int:
    """
    Insert hoặc update kết quả kiểm tra nợ khoanh.
    - Nếu data có "id" và id tồn tại, trang_thai != 'da_phe_duyet' → UPDATE.
    - Ngược lại → INSERT mới.
    - Tự tính chenh_lech = du_no_goc_khoanh - du_no_khoanh_thuc_te
      khi data không truyền chenh_lech (hoặc = 0) mà 2 giá trị kia khác 0.
    - Ghi audit_log sau khi ghi thành công.
    - Trả về id (int) của record vừa insert/update.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Tự tính chenh_lech nếu cần
    khoanh = float(data.get("du_no_goc_khoanh") or 0)
    thuc_te = float(data.get("du_no_khoanh_thuc_te") or 0)
    chenh_lech = float(data.get("chenh_lech") or 0)
    if chenh_lech == 0 and (khoanh != 0 or thuc_te != 0):
        chenh_lech = round(khoanh - thuc_te, 2)

    try:
        with get_conn() as conn:
            record_id = data.get("id")
            existing = None
            if record_id:
                existing = conn.execute(
                    "SELECT id, trang_thai FROM qlnk_ket_qua WHERE id = ?",
                    (record_id,),
                ).fetchone()

            if existing and existing["trang_thai"] != "da_phe_duyet":
                # UPDATE
                conn.execute(
                    """UPDATE qlnk_ket_qua SET
                        ma_mon_vay=?, ten_pgd=?, ten_xa=?, ten_to_tkv=?, ten_kh=?,
                        ngay_bat_dau_khoanh=?, so_thang_khoanh=?, so_quyet_dinh_khoanh=?,
                        ngay_kiem_tra=?, ngay_het_han_khoanh=?, can_bo_kiem_tra=?,
                        du_no_goc=?, du_no_goc_khoanh=?, so_tien_lai_con_no=?,
                        du_no_goc_thuc_te=?, du_no_khoanh_thuc_te=?, so_tien_lai_thuc_te=?,
                        chenh_lech=?, ly_do_chenh_lech=?,
                        thuc_trang_du_an=?, tinh_hinh_khach_hang=?,
                        kha_nang_tra_no=?, cam_ket_tra_no=?,
                        trang_thai=?, nguoi_nhap=?, updated_at=?
                    WHERE id=?""",
                    (
                        data.get("ma_mon_vay"), data.get("ten_pgd"),
                        data.get("ten_xa"), data.get("ten_to_tkv"), data.get("ten_kh"),
                        data.get("ngay_bat_dau_khoanh"), data.get("so_thang_khoanh"),
                        data.get("so_quyet_dinh_khoanh"),
                        data.get("ngay_kiem_tra"), data.get("ngay_het_han_khoanh"),
                        data.get("can_bo_kiem_tra"),
                        float(data.get("du_no_goc") or 0),
                        khoanh,
                        float(data.get("so_tien_lai_con_no") or 0),
                        float(data.get("du_no_goc_thuc_te") or 0),
                        thuc_te,
                        float(data.get("so_tien_lai_thuc_te") or 0),
                        chenh_lech, data.get("ly_do_chenh_lech"),
                        data.get("thuc_trang_du_an"), data.get("tinh_hinh_khach_hang"),
                        data.get("kha_nang_tra_no"), data.get("cam_ket_tra_no"),
                        data.get("trang_thai", "luu_tam"), username, now,
                        record_id,
                    ),
                )
                conn.commit()
                result_id = record_id
            else:
                # INSERT
                cur = conn.execute(
                    """INSERT INTO qlnk_ket_qua (
                        ma_mon_vay, ten_pgd, ten_xa, ten_to_tkv, ten_kh,
                        ngay_bat_dau_khoanh, so_thang_khoanh, so_quyet_dinh_khoanh,
                        ngay_kiem_tra, ngay_het_han_khoanh, can_bo_kiem_tra,
                        du_no_goc, du_no_goc_khoanh, so_tien_lai_con_no,
                        du_no_goc_thuc_te, du_no_khoanh_thuc_te, so_tien_lai_thuc_te,
                        chenh_lech, ly_do_chenh_lech,
                        thuc_trang_du_an, tinh_hinh_khach_hang,
                        kha_nang_tra_no, cam_ket_tra_no,
                        trang_thai, nguoi_nhap, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        data.get("ma_mon_vay"), data.get("ten_pgd"),
                        data.get("ten_xa"), data.get("ten_to_tkv"), data.get("ten_kh"),
                        data.get("ngay_bat_dau_khoanh"), data.get("so_thang_khoanh"),
                        data.get("so_quyet_dinh_khoanh"),
                        data.get("ngay_kiem_tra"), data.get("ngay_het_han_khoanh"),
                        data.get("can_bo_kiem_tra"),
                        float(data.get("du_no_goc") or 0),
                        khoanh,
                        float(data.get("so_tien_lai_con_no") or 0),
                        float(data.get("du_no_goc_thuc_te") or 0),
                        thuc_te,
                        float(data.get("so_tien_lai_thuc_te") or 0),
                        chenh_lech, data.get("ly_do_chenh_lech"),
                        data.get("thuc_trang_du_an"), data.get("tinh_hinh_khach_hang"),
                        data.get("kha_nang_tra_no"), data.get("cam_ket_tra_no"),
                        data.get("trang_thai", "luu_tam"), username, now,
                    ),
                )
                conn.commit()
                result_id = cur.lastrowid

        ghi_audit(
            username, "luu_ket_qua_kiem_tra",
            f"ma_mon_vay={data.get('ma_mon_vay')}, trang_thai={data.get('trang_thai', 'luu_tam')}",
        )
        return result_id
    except Exception:
        raise


def phe_duyet_ket_qua(record_id: int, username: str) -> bool:
    """
    Chuyển trang_thai → 'da_phe_duyet'.
    Chỉ hợp lệ khi trang_thai hiện tại là 'luu_tam' hoặc 'mo_phe_duyet'.
    Trả về True nếu thành công, False nếu không tìm thấy hoặc không hợp lệ.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT trang_thai FROM qlnk_ket_qua WHERE id = ?", (record_id,)
            ).fetchone()
            if not row or row["trang_thai"] not in ("luu_tam", "mo_phe_duyet"):
                return False
            conn.execute(
                """UPDATE qlnk_ket_qua
                   SET trang_thai='da_phe_duyet', nguoi_phe_duyet=?,
                       ngay_phe_duyet=?, updated_at=?
                   WHERE id=?""",
                (username, now, now, record_id),
            )
            conn.commit()
        ghi_audit(username, "phe_duyet_ket_qua", f"id={record_id}")
        return True
    except Exception:
        return False


def mo_phe_duyet(record_id: int, username: str) -> bool:
    """
    Chuyển trang_thai từ 'da_phe_duyet' → 'mo_phe_duyet'.
    Xóa nguoi_phe_duyet và ngay_phe_duyet (NULL).
    Trả về True/False, không raise exception.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT trang_thai FROM qlnk_ket_qua WHERE id = ?", (record_id,)
            ).fetchone()
            if not row or row["trang_thai"] != "da_phe_duyet":
                return False
            conn.execute(
                """UPDATE qlnk_ket_qua
                   SET trang_thai='mo_phe_duyet', nguoi_phe_duyet=NULL,
                       ngay_phe_duyet=NULL, updated_at=?
                   WHERE id=?""",
                (now, record_id),
            )
            conn.commit()
        ghi_audit(username, "mo_phe_duyet_ket_qua", f"id={record_id}")
        return True
    except Exception:
        return False


def doc_ket_qua_kiem_tra(
    ten_pgd: str = None,
    ma_mon_vay: str = None,
    trang_thai: str = None,
) -> list[dict]:
    """
    Đọc danh sách kết quả kiểm tra nợ khoanh.
    Lọc AND theo ten_pgd / ma_mon_vay / trang_thai nếu được truyền (None = bỏ qua).
    Trả về list[dict] ORDER BY ngay_kiem_tra DESC, id DESC.
    """
    try:
        clauses, params = [], []
        if ten_pgd is not None:
            clauses.append("ten_pgd = ?")
            params.append(ten_pgd)
        if ma_mon_vay is not None:
            clauses.append("ma_mon_vay = ?")
            params.append(ma_mon_vay)
        if trang_thai is not None:
            clauses.append("trang_thai = ?")
            params.append(trang_thai)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""SELECT {', '.join(_QLNK_KQ_COLS)}
                  FROM qlnk_ket_qua {where}
                  ORDER BY ngay_kiem_tra DESC, id DESC"""
        with get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def luu_bo_sung_mon_vay(
    ma_mon_vay: str,
    ten_pgd: str,
    data: dict,
    username: str,
) -> None:
    """
    Upsert thông tin bổ sung cho 1 món vay vào qlnk_bo_sung.
    Mỗi ma_mon_vay có đúng 1 dòng (UNIQUE).
    Không raise exception — lỗi chỉ ghi audit.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO qlnk_bo_sung
                   (ma_mon_vay, ten_pgd,
                    ngay_bat_dau_khoanh, so_thang_khoanh, so_quyet_dinh_khoanh,
                    ghi_chu, nguoi_cap_nhat, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    ma_mon_vay, ten_pgd,
                    data.get("ngay_bat_dau_khoanh"),
                    data.get("so_thang_khoanh"),
                    data.get("so_quyet_dinh_khoanh"),
                    data.get("ghi_chu"),
                    username, now,
                ),
            )
            conn.commit()
        ghi_audit(username, "luu_bo_sung_mon_vay", f"ma_mon_vay={ma_mon_vay}")
    except Exception as e:
        ghi_audit(username, "loi_luu_bo_sung_mon_vay", f"ma_mon_vay={ma_mon_vay}, err={e}")


def doc_bo_sung_mon_vay(ma_mon_vay: str) -> dict | None:
    """
    Đọc thông tin bổ sung của 1 món vay từ qlnk_bo_sung.
    Trả về dict hoặc None nếu chưa có / lỗi.
    """
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM qlnk_bo_sung WHERE ma_mon_vay = ?", (ma_mon_vay,)
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def doc_ke_hoach_kiem_tra(ten_pgd: str = None, trang_thai: str = None,
                          nam: int = None) -> list[dict]:
    """Đọc kế hoạch kiểm tra năm từ qlnk_ke_hoach."""
    conds, params = [], []
    if ten_pgd:
        conds.append("ten_pgd = ?"); params.append(ten_pgd)
    if trang_thai:
        conds.append("trang_thai = ?"); params.append(trang_thai)
    if nam:
        conds.append("nam = ?"); params.append(nam)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    try:
        with get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM qlnk_ke_hoach {where} ORDER BY nam DESC, id DESC",
                params,
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for _fld in ("ds_phan_cong", "thanh_phan_doan"):
                try:
                    d[_fld] = json.loads(d.get(_fld) or "[]")
                except Exception:
                    d[_fld] = []
            result.append(d)
        return result
    except Exception:
        return []


def luu_ke_hoach_kiem_tra(data: dict, username: str = "system") -> int:
    """Upsert kế hoạch kiểm tra năm vào qlnk_ke_hoach. Trả về id bản ghi."""
    now        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ds_pc      = json.dumps(data.get("ds_phan_cong") or [], ensure_ascii=False)
    tp_doan    = json.dumps(data.get("thanh_phan_doan") or [], ensure_ascii=False)
    rec_id     = data.get("id")
    ten_pgd    = data.get("ten_pgd", "")
    nam        = int(data.get("nam") or 0)
    try:
        with get_conn() as conn:
            if rec_id:
                conn.execute(
                    """UPDATE qlnk_ke_hoach
                       SET ten_pgd=?, nam=?, ds_phan_cong=?, thanh_phan_doan=?,
                           ghi_chu=?, updated_at=?
                       WHERE id=? AND trang_thai != 'da_duyet'""",
                    (ten_pgd, nam, ds_pc, tp_doan, data.get("ghi_chu"), now, rec_id),
                )
            else:
                cur = conn.execute(
                    """INSERT INTO qlnk_ke_hoach
                       (ten_pgd, nam, ds_phan_cong, thanh_phan_doan,
                        ghi_chu, trang_thai, nguoi_lap, updated_at)
                       VALUES (?,?,?,?,?, 'luu_tam', ?,?)""",
                    (ten_pgd, nam, ds_pc, tp_doan,
                     data.get("ghi_chu"), username, now),
                )
                rec_id = cur.lastrowid
            conn.commit()
        ghi_audit(username, "luu_ke_hoach_kiem_tra", f"id={rec_id} pgd={ten_pgd} nam={nam}")
        return rec_id or 0
    except Exception as e:
        ghi_audit(username, "loi_luu_ke_hoach_kiem_tra", str(e))
        return 0


def duyet_ke_hoach(kehoach_id: int, username: str = "system") -> bool:
    """Duyệt kế hoạch kiểm tra (luu_tam → da_duyet)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """UPDATE qlnk_ke_hoach
                   SET trang_thai='da_duyet', nguoi_duyet=?, ngay_duyet=?, updated_at=?
                   WHERE id=? AND trang_thai IN ('luu_tam', 'mo_phe_duyet')""",
                (username, now, now, kehoach_id),
            )
            conn.commit()
            ok = cur.rowcount > 0
        ghi_audit(username, "duyet_ke_hoach", f"id={kehoach_id} ok={ok}")
        return ok
    except Exception as e:
        ghi_audit(username, "loi_duyet_ke_hoach", str(e))
        return False


# Khởi tạo DB, migrate dữ liệu cũ, sau đó seed cấu hình động
init_db()
migrate_from_json()
seed_dynamic_configs()
migrate_pgd_bien_hoa()
