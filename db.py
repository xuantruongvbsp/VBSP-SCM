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
        """)
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
    Đọc danh sách Mã NĐT cấp tỉnh từ kv_store.
    Mỗi phần tử: {"ma": "INV0802140002662", "ghi_chu": "UBND tỉnh Đồng Nai"}
    Fallback về seed data nếu chưa có.
    """
    val = doc_kv("ndt_dp_list")
    if val and isinstance(val, list) and len(val) > 0:
        return val
    # Seed mặc định
    return [
        {"ma": "INV0802140002662", "ghi_chu": "UBND tỉnh Đồng Nai"},
        {"ma": "INV0603170027393", "ghi_chu": "Nguồn vốn cho vay đào tạo nghề"},
    ]


def doc_ndt_dp_ma_list() -> list[str]:
    """Trả về chỉ list mã (str) để dùng trong phân tầng."""
    return [item["ma"] for item in doc_ndt_dp_list()]


# Khởi tạo DB, migrate dữ liệu cũ, sau đó seed cấu hình động
init_db()
migrate_from_json()
seed_dynamic_configs()
migrate_pgd_bien_hoa()
