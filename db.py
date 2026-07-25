import sqlite3
import json
import os
import threading
import atexit
from datetime import datetime
from pathlib import Path
from typing import Any
from config import BASE_DIR
from logger import get_logger

logger = get_logger(__name__)

_local = threading.local()


def _safe_text(value, default: str = "") -> str:
    """Chuẩn hóa giá trị audit/log để None hoặc object lạ không làm hỏng ghi DB."""
    if value is None:
        return default
    try:
        text = str(value).strip()
    except Exception:
        return default
    return text or default


def _safe_username(username) -> str:
    return _safe_text(username, "unknown")


def _safe_action(action) -> str:
    return _safe_text(action, "unknown_action")


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
    conn.execute('PRAGMA foreign_keys=ON;')
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


_KV_SYNC_PATH = Path(__file__).parent / "backups" / "kv_sync.json"

# Bảng được sync qua GitHub — thứ tự: parent trước child (FK)
# Bỏ: audit_log, kv_history (log máy), *_snapshot (lớn, tự tái tạo)
_SYNC_TABLES = [
    "users",
    "kv_store",
    "nhiem_vu",
    "nhiem_vu_ketqua",
    "tien_do_task",
    "tien_do_ketqua",
    "tien_do_template",
    "qlnk_ket_qua",
    "qlnk_bo_sung",
    "qlnk_ke_hoach",
    "mau_bieu_cv368",
]


def export_kv_json() -> str:
    """Xuất tất cả bảng business data thành JSON text (git-friendly).
    Bao gồm: users, kv_store, nhiem_vu, tien_do, qlnk, mau_bieu.
    Bỏ qua: audit_log, kv_history, *_snapshot (log/lớn, tự tái tạo)."""
    result: dict = {
        "exported_at": datetime.now().isoformat(),
        "version": 2,
        "tables": {},
    }
    try:
        with get_conn() as conn:
            for table in _SYNC_TABLES:
                try:
                    rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
                    result["tables"][table] = [dict(r) for r in rows]
                except Exception:
                    result["tables"][table] = []
    except Exception as e:  # conv: skip
        logger.error("export_kv_json thất bại: %s", e, exc_info=True)
        result["error"] = str(e)
    return json.dumps(result, ensure_ascii=False, indent=2)


def import_kv_json(json_str: str, username: str = "sync") -> dict[str, int]:
    """Import (merge) tất cả bảng từ JSON — INSERT OR REPLACE.
    Tương thích ngược với format v1 (chỉ có kv_store).
    Trả về dict {tên_bảng: số_bản_ghi_đã_import}."""
    data = json.loads(json_str)
    # Tương thích format v1 (chỉ có key "kv_store")
    if "tables" in data:
        tables_data: dict = data["tables"]
    else:
        tables_data = {"kv_store": data.get("kv_store", [])}

    counts: dict[str, int] = {}
    try:
        with get_conn() as conn:
            for table in _SYNC_TABLES:
                rows = tables_data.get(table, [])
                if not rows:
                    counts[table] = 0
                    continue
                count = 0
                for row in rows:
                    cols = ", ".join(f'"{c}"' for c in row.keys())
                    placeholders = ", ".join("?" * len(row))
                    try:
                        conn.execute(
                            f'INSERT OR REPLACE INTO "{table}" ({cols}) VALUES ({placeholders})',
                            list(row.values()),
                        )
                        count += 1
                    except Exception:
                        pass
                conn.commit()
                counts[table] = count
    except Exception:
        pass
    return counts


def luu_kv_sync_project() -> dict[str, int]:
    """Xuất tất cả bảng → backups/kv_sync.json (git-tracked).
    Trả về dict {tên_bảng: số_bản_ghi}."""
    _KV_SYNC_PATH.parent.mkdir(parents=True, exist_ok=True)
    json_str = export_kv_json()
    _KV_SYNC_PATH.write_text(json_str, encoding="utf-8")
    data = json.loads(json_str)
    return {t: len(rows) for t, rows in data.get("tables", {}).items()}


def doc_kv_sync_project() -> dict[str, int] | None:
    """Import tất cả bảng từ backups/kv_sync.json (nếu tồn tại).
    Trả về dict {tên_bảng: số_bản_ghi}, hoặc None nếu file chưa có."""
    if not _KV_SYNC_PATH.exists():
        return None
    json_str = _KV_SYNC_PATH.read_text(encoding="utf-8")
    return import_kv_json(json_str)


def _discover_migrations():
    """Tìm tất cả migration files trong migrations/, sort theo VERSION."""
    import importlib
    import pkgutil
    import migrations as mig_pkg
    result = []
    for importer, modname, ispkg in pkgutil.iter_modules(mig_pkg.__path__):
        if modname[0].isdigit():
            mod = importlib.import_module(f"migrations.{modname}")
            result.append(mod)
    result.sort(key=lambda m: m.VERSION)
    return result


def init_db():
    with get_conn() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for mig in _discover_migrations():
            if mig.VERSION > version:
                mig.upgrade(conn)
                conn.execute(f"PRAGMA user_version = {mig.VERSION}")
        conn.commit()


def luu_ghi_chu_kv(ma_so_ku: str, ghi_chu: str, username: str) -> bool:
    """Lưu hoặc cập nhật ghi chú cho 1 khoản vay (UPSERT theo ma_so_ku)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM loan_notes WHERE ma_so_ku = ?", (ma_so_ku,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE loan_notes SET ghi_chu=?, username=?, updated_at=? WHERE ma_so_ku=?",
                    (ghi_chu, username, now, ma_so_ku),
                )
            else:
                conn.execute(
                    "INSERT INTO loan_notes (ma_so_ku, ghi_chu, username, created_at, updated_at) VALUES (?,?,?,?,?)",
                    (ma_so_ku, ghi_chu, username, now, now),
                )
            conn.commit()
        ghi_audit(username, "luu_ghi_chu_kv", f"ma_so_ku={ma_so_ku}")
        return True
    except Exception as e:
        logger.error("luu_ghi_chu_kv thất bại ma_so_ku=%s: %s", ma_so_ku, e, exc_info=True)
        return False


def doc_ghi_chu_kv(ma_so_ku: str) -> dict | None:
    """Đọc ghi chú mới nhất cho 1 khoản vay.
    Trả về {"ghi_chu", "username", "updated_at"} hoặc None nếu chưa có."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT ghi_chu, username, updated_at FROM loan_notes WHERE ma_so_ku = ?",
                (ma_so_ku,),
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        logger.error("doc_ghi_chu_kv thất bại ma_so_ku=%s", ma_so_ku, exc_info=True)
        return None


def doc_ghi_chu_nhieu(ds_ma: list[str]) -> dict[str, dict]:
    """Đọc ghi chú cho nhiều khoản vay cùng lúc.
    Trả về {ma_so_ku: {"ghi_chu", "username", "updated_at"}}."""
    if not ds_ma:
        return {}
    try:
        placeholders = ",".join("?" * len(ds_ma))
        with get_conn() as conn:
            rows = conn.execute(
                f"SELECT ma_so_ku, ghi_chu, username, updated_at FROM loan_notes WHERE ma_so_ku IN ({placeholders})",
                list(ds_ma),
            ).fetchall()
        return {r["ma_so_ku"]: {"ghi_chu": r["ghi_chu"], "username": r["username"], "updated_at": r["updated_at"]} for r in rows}
    except Exception:
        logger.error("doc_ghi_chu_nhieu thất bại so_ma=%s", len(ds_ma), exc_info=True)
        return {}


_KTNB_LOI_CHUAN = [
    ("TD_01", "tin_dung", "Hồ sơ vay thiếu giấy tờ bắt buộc", "Thiếu CMND/CCCD, giấy đề nghị vay vốn, biên bản họp tổ", "trung_binh", "CV 9919/NHCS-KTNB"),
    ("TD_02", "tin_dung", "Sai lãi suất cho vay", "Lãi suất áp dụng không đúng quyết định hiện hành", "cao", "CV 9919/NHCS-KTNB"),
    ("TD_03", "tin_dung", "Mức vay vượt quy định chương trình", "Số tiền cho vay vượt mức tối đa chương trình tín dụng", "cao", "CV 9919/NHCS-KTNB"),
    ("TD_04", "tin_dung", "Sai đối tượng thụ hưởng", "Người vay không thuộc đối tượng chương trình tín dụng", "cao", "CV 9919/NHCS-KTNB"),
    ("TD_05", "tin_dung", "Gia hạn nợ không đúng quy trình", "Thiếu biên bản xét duyệt gia hạn hoặc gia hạn sai thẩm quyền", "trung_binh", "CV 9919/NHCS-KTNB"),
    ("TD_06", "tin_dung", "Dư nợ thực tế không khớp sổ sách", "Chênh lệch giữa dư nợ đối chiếu thực tế và dư nợ trên hệ thống", "cao", "CV 10499/NHCS-KTNB"),
    ("TD_07", "tin_dung", "Không lập/lưu biên bản kiểm tra sau vay", "Thiếu biên bản kiểm tra sử dụng vốn định kỳ theo quy định", "thap", "CV 9919/NHCS-KTNB"),
    ("TD_08", "tin_dung", "Tổ TK&VV hoạt động không đúng quy định", "Danh sách tổ viên, biên bản họp tổ không đầy đủ/lưu trữ không đúng", "thap", "CV 9919/NHCS-KTNB"),
    ("KT_01", "ke_toan", "Hạch toán sai tài khoản", "Bút toán không đúng hệ thống tài khoản NHCSXH", "cao", "CV 9919/NHCS-KTNB"),
    ("KT_02", "ke_toan", "Chứng từ kế toán không hợp lệ", "Chứng từ thiếu chữ ký, dấu, hoặc số tiền bằng chữ/số không khớp", "trung_binh", "CV 9919/NHCS-KTNB"),
    ("KT_03", "ke_toan", "Tồn quỹ tiền mặt vượt định mức", "Số dư tiền mặt cuối ngày vượt định mức cho phép", "trung_binh", "CV 9919/NHCS-KTNB"),
    ("KT_04", "ke_toan", "Bảo quản kho quỹ không đúng quy định", "Phòng kho quỹ không đạt tiêu chuẩn an toàn theo quy định", "trung_binh", "CV 9919/NHCS-KTNB"),
    ("KT_05", "ke_toan", "Báo cáo tài chính nộp trễ hạn", "Báo cáo định kỳ nộp sau ngày quy định", "thap", "CV 9919/NHCS-KTNB"),
    ("TC_01", "tccb", "Hồ sơ nhân sự không đầy đủ", "Thiếu quyết định bổ nhiệm, hợp đồng lao động, bằng cấp chứng chỉ", "thap", "CV 9919/NHCS-KTNB"),
    ("TC_02", "tccb", "Vi phạm quy chế chi tiêu nội bộ", "Chi tiêu vượt định mức hoặc không có chứng từ hợp lệ", "trung_binh", "CV 9919/NHCS-KTNB"),
    ("TC_03", "tccb", "Ban đại diện HĐQT chưa giám sát theo quy định", "Thiếu biên bản giám sát định kỳ hoặc giám sát không đúng nội dung", "thap", "CV 9919/NHCS-KTNB"),
    ("TC_04", "tccb", "Công tác lưu trữ văn bản không đúng quy định", "Văn bản không được phân loại, đóng dấu mật hoặc lưu trữ đúng niên hạn", "thap", "CV 9919/NHCS-KTNB"),
]


def seed_ktnb_danh_muc_loi() -> int:
    """Seed danh mục lỗi chuẩn theo CV 9919/NHCS-KTNB. Chạy an toàn nhiều lần.
    Trả về số bản ghi đã insert (0 nếu đã có hết)."""
    count = 0
    try:
        with get_conn() as conn:
            for row in _KTNB_LOI_CHUAN:
                ma_loi, khoi, ten, mo_ta, muc_do, so_cv = row
                exists = conn.execute(
                    "SELECT 1 FROM ktnb_danh_muc_loi_chuan WHERE ma_loi = ?", (ma_loi,)
                ).fetchone()
                if not exists:
                    conn.execute(
                        """INSERT INTO ktnb_danh_muc_loi_chuan
                           (ma_loi, khoi_nghiep_vu, ten_loi, mo_ta, muc_do, so_cv)
                           VALUES (?,?,?,?,?,?)""",
                        (ma_loi, khoi, ten, mo_ta, muc_do, so_cv),
                    )
                    count += 1
            conn.commit()
    except Exception as e:
        logger.error("seed_ktnb_danh_muc_loi thất bại: %s", e, exc_info=True)
    return count


def ghi_kv(key: str, value: dict, username: str = "system", note: str = None) -> None:
    """Ghi hoặc cập nhật một cặp key-value vào bảng kv_store."""
    key_safe = _safe_text(key)
    username_safe = _safe_username(username)
    note_safe = None if note is None else _safe_text(note)
    try:
        if not key_safe:
            raise ValueError("kv_store key không được rỗng")
        with get_conn() as conn:
            old_row = conn.execute(
                "SELECT value FROM kv_store WHERE key = ?", (key_safe,)
            ).fetchone()
            new_value_str = json.dumps(value, ensure_ascii=False)
            if old_row and old_row["value"] != new_value_str:
                conn.execute(
                    """INSERT INTO kv_history (key, value, changed_by, note)
                       VALUES (?, ?, ?, ?)""",
                    (key_safe, old_row["value"], username_safe, note_safe),
                )
            conn.execute(
                """INSERT OR REPLACE INTO kv_store (key, value, updated_at, updated_by)
                   VALUES (?, ?, ?, ?)""",
                (key_safe, new_value_str,
                 datetime.now().isoformat(), username_safe),
            )
            conn.commit()
    except Exception:
        logger.error("ghi_kv thất bại key=%s", key_safe or "<empty>", exc_info=True)


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
        logger.error("doc_kv thất bại key=%s", key, exc_info=True)
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
        logger.error("list_kv_prefix thất bại prefix=%s", prefix, exc_info=True)
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
        logger.error("doc_kv_prefix thất bại prefix=%s", prefix, exc_info=True)
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
        logger.error("doc_kv_nhieu thất bại so_key=%s", len(keys), exc_info=True)
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
        logger.error("doc_kv_history thất bại key=%s", key, exc_info=True)
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
    """Ghi audit log cơ bản (backward compatible)."""
    username_safe = _safe_username(username)
    action_safe = _safe_action(action)
    detail_safe = "" if detail is None else _safe_text(detail)
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (ts, username, action, detail) VALUES (?,?,?,?)",
                (datetime.now().isoformat(), username_safe, action_safe, detail_safe)
            )
            conn.commit()
    except Exception:
        logger.error("ghi_audit thất bại username=%s action=%s", username_safe, action_safe, exc_info=True)


def ghi_audit_full(
    username: str,
    action: str,
    detail: str = "",
    table_name: str = None,
    record_id: str = None,
    old_value: dict = None,
    new_value: dict = None,
    ip_address: str = None,
    user_agent: str = None,
) -> None:
    """
    Ghi audit log đầy đủ cho compliance NHCSXH.
    
    Args:
        username: Tên user thực hiện
        action: Loại hành động (insert, update, delete, login, logout...)
        detail: Mô tả chi tiết
        table_name: Tên bảng bị tác động
        record_id: ID của record bị tác động
        old_value: Giá trị cũ (dict)
        new_value: Giá trị mới (dict)
        ip_address: IP address của client
        user_agent: User agent string
    """
    username_safe = _safe_username(username)
    action_safe = _safe_action(action)
    detail_safe = "" if detail is None else _safe_text(detail)
    try:
        import json
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO audit_log
                   (ts, username, action, detail, table_name, record_id,
                    old_value, new_value, ip_address, user_agent)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now().isoformat(),
                    username_safe,
                    action_safe,
                    detail_safe,
                    table_name,
                    str(record_id) if record_id is not None else None,
                    json.dumps(old_value, ensure_ascii=False) if old_value else None,
                    json.dumps(new_value, ensure_ascii=False) if new_value else None,
                    ip_address,
                    user_agent,
                ),
            )
            conn.commit()
    except Exception:
        logger.error("ghi_audit_full thất bại username=%s action=%s", username_safe, action_safe, exc_info=True)


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
    except Exception as e:  # conv: skip
        logger.error("seed_configs thất bại: %s", e, exc_info=True)
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
    except Exception as e:  # conv: skip
        logger.error("luu_dgd_map thất bại: %s", e, exc_info=True)
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
            except Exception as e:  # conv: skip
                logger.error("migrate users.json thất bại: %s", e, exc_info=True)
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
                except Exception as e:  # conv: skip
                    logger.error("migrate %s.json thất bại: %s", key, e, exc_info=True)
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
    except Exception as e:  # conv: skip
        logger.error("migrate_pgd_bien_hoa thất bại: %s", e, exc_info=True)
        ghi_audit("system", "migrate_pgd_bien_hoa_error", str(e))


def migrate_legacy_user_roles() -> None:
    """
    Chuẩn hóa role người dùng cũ sang hệ role mới.
    admin -> admin_cn, manager -> manager_cn, user -> user_pgd.
    Đồng thời bỏ PGD khỏi các role cấp Chi nhánh để tránh lẫn phân hệ.
    """
    try:
        with get_conn() as conn:
            tong_cap_nhat = 0
            for role_cu, role_moi in (
                ("admin", "admin_cn"),
                ("manager", "manager_cn"),
                ("user", "user_pgd"),
            ):
                cur = conn.execute(
                    "UPDATE users SET role = ? WHERE role = ?",
                    (role_moi, role_cu),
                )
                tong_cap_nhat += max(cur.rowcount, 0)

            cur_cn = conn.execute(
                """UPDATE users
                   SET pgd = NULL
                   WHERE role IN ('executive', 'admin_cn', 'manager_cn', 'chuyenvien_cn')
                   AND pgd IS NOT NULL"""
            )
            tong_cap_nhat += max(cur_cn.rowcount, 0)

            conn.commit()

            if tong_cap_nhat > 0:
                ghi_audit(
                    "system",
                    "migrate_legacy_user_roles",
                    f"Đã chuẩn hóa {tong_cap_nhat} bản ghi users sang role mới",
                )
    except Exception as e:  # conv: skip
        logger.error("migrate_legacy_user_roles thất bại: %s", e, exc_info=True)
        ghi_audit("system", "migrate_legacy_user_roles_error", str(e))


def _seed_ndt_dp_rules() -> list[dict]:
    return [
        {"ma_ct": 3, "ma": "INV0802140002662", "ghi_chu": "UBND tỉnh Đồng Nai", "cap": "tinh"},
        {"ma_ct": 3, "ma": "INV0603170027393", "ghi_chu": "Nguồn vốn cho vay đào tạo nghề", "cap": "tinh"},
        {"ma_ct": 6, "ma": "INV1907190050748", "ghi_chu": "(chưa xác nhận nghiệp vụ — mặc định cấp tỉnh)", "cap": "tinh"},
        {"ma_ct": 6, "ma": "INV0802140002661", "ghi_chu": "(chưa xác nhận nghiệp vụ — mặc định cấp tỉnh)", "cap": "tinh"},
    ]


def _normalize_ndt_dp_rule(item: dict, default_ma_ct: int | None = None) -> dict | None:
    if not isinstance(item, dict):
        return None
    ma = str(item.get("ma", "") or "").strip()
    if not ma:
        return None
    ma_ct_raw = item.get("ma_ct", default_ma_ct)
    try:
        ma_ct = int(ma_ct_raw) if ma_ct_raw not in (None, "", "ALL") else None
    except Exception:
        ma_ct = default_ma_ct
    return {
        "ma_ct": ma_ct,
        "ma": ma,
        "ghi_chu": str(item.get("ghi_chu", "") or "").strip(),
        "cap": "xa" if str(item.get("cap", "tinh")).strip().lower() == "xa" else "tinh",
    }


def doc_ndt_dp_rule_list() -> list[dict]:
    """
    Danh mục rule Mã NĐT ĐP chuẩn:
    {"ma_ct": 3|6|None, "ma": "INV...", "ghi_chu": "...", "cap": "tinh"|"xa"}
    Ưu tiên key mới `ndt_dp_rule_list`, fallback dữ liệu cũ theo từng chương trình.
    """
    val = doc_kv("ndt_dp_rule_list")
    raw_rules: list[dict] = val if isinstance(val, list) and val else []
    if not raw_rules:
        raw_gqvl = doc_kv("ndt_dp_list")
        raw_nsvsmt = doc_kv("ndt_dp_nsvsmt_list")
        if isinstance(raw_gqvl, list):
            raw_rules.extend(_normalize_ndt_dp_rule(x, 3) for x in raw_gqvl)
        if isinstance(raw_nsvsmt, list):
            raw_rules.extend(_normalize_ndt_dp_rule(x, 6) for x in raw_nsvsmt)
        raw_rules = [x for x in raw_rules if x]
    if not raw_rules:
        raw_rules = _seed_ndt_dp_rules()

    out: list[dict] = []
    seen: set[tuple[int | None, str]] = set()
    for item in raw_rules:
        norm = item if isinstance(item, dict) and "ma_ct" in item else _normalize_ndt_dp_rule(item)
        norm = _normalize_ndt_dp_rule(norm or {})
        if not norm:
            continue
        key = (norm.get("ma_ct"), norm["ma"])
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def _loc_ndt_dp_rule_theo_ct(ma_ct: int) -> list[dict]:
    ma_ct_i = int(ma_ct)
    return [x for x in doc_ndt_dp_rule_list() if x.get("ma_ct") == ma_ct_i]


def luu_ndt_dp_rule_list(ds: list[dict], username: str) -> None:
    """Lưu danh mục rule Mã NĐT ĐP chuẩn vào kv_store."""
    norm = []
    for item in ds:
        item_n = _normalize_ndt_dp_rule(item)
        if item_n:
            norm.append(item_n)
    ghi_kv("ndt_dp_rule_list", norm, username)


def doc_ndt_dp_list() -> list[dict]:
    """
    Danh sách Mã NĐT ĐP áp dụng cho GQVL (ma_ct=3).
    Mỗi phần tử: {"ma_ct": 3, "ma": "INV...", "ghi_chu": "...", "cap": "tinh"|"xa"}
    """
    return _loc_ndt_dp_rule_theo_ct(3)


def luu_ndt_dp_list(ds: list[dict], username: str) -> None:
    """Ghi đè rule Mã NĐT áp dụng cho GQVL (ma_ct=3), giữ nguyên rule CT khác."""
    ds_khac = [x for x in doc_ndt_dp_rule_list() if x.get("ma_ct") != 3]
    ds_gqvl = []
    for item in ds:
        item2 = dict(item)
        item2["ma_ct"] = 3
        item_n = _normalize_ndt_dp_rule(item2, 3)
        if item_n:
            ds_gqvl.append(item_n)
    luu_ndt_dp_rule_list(ds_khac + ds_gqvl, username)


def doc_ndt_dp_ma_list(ma_ct: int = 3) -> list[str]:
    """Trả về list mã Cấp Tỉnh cho chương trình ĐP tương ứng (mặc định GQVL=3)."""
    return [item["ma"] for item in _loc_ndt_dp_rule_theo_ct(ma_ct) if item.get("cap", "tinh") == "tinh"]


def phan_loai_ndt_dp_cap(ma_ct: int, ma_ndt: str) -> str:
    """
    Phân loại cấp theo ưu tiên:
    1. match exact cặp (ma_ct, ma_ndt)
    2. fallback rule chung (ma_ct=None, ma_ndt)
    3. mặc định `xa`
    """
    ma = str(ma_ndt or "").strip()
    if not ma:
        return "xa"
    rules = doc_ndt_dp_rule_list()
    ma_ct_i = int(ma_ct)
    for item in rules:
        if item.get("ma_ct") == ma_ct_i and item.get("ma") == ma:
            return item.get("cap", "tinh")
    for item in rules:
        if item.get("ma_ct") is None and item.get("ma") == ma:
            return item.get("cap", "tinh")
    return "xa"


def doc_ndt_dp_nsvsmt_list() -> list[dict]:
    """
    Mã NĐT cho NSVSMT (ma_ct=6) ĐP.
    Mỗi phần tử: {"ma_ct": 6, "ma": "INV...", "ghi_chu": "...", "cap": "tinh"|"xa"}
    """
    return _loc_ndt_dp_rule_theo_ct(6)


def doc_ndt_dp_nsvsmt_ma_list() -> list[str]:
    """Trả về list mã Cấp Tỉnh cho NSVSMT ĐP để dùng trong phân tầng 6_DP."""
    return doc_ndt_dp_ma_list(6)


def luu_ndt_dp_nsvsmt_list(ds: list[dict], username: str) -> None:
    """Ghi đè rule Mã NĐT áp dụng cho NSVSMT (ma_ct=6), giữ nguyên rule CT khác."""
    ds_khac = [x for x in doc_ndt_dp_rule_list() if x.get("ma_ct") != 6]
    ds_ns = []
    for item in ds:
        item2 = dict(item)
        item2["ma_ct"] = 6
        item_n = _normalize_ndt_dp_rule(item2, 6)
        if item_n:
            ds_ns.append(item_n)
    luu_ndt_dp_rule_list(ds_khac + ds_ns, username)


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
    except Exception as e:  # conv: skip
        logger.error("luu_bo_sung_mon_vay thất bại ma_mon_vay=%s: %s", ma_mon_vay, e, exc_info=True)
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


def doc_bo_sung_nhieu_mon_vay(ds_ma: list[str]) -> dict[str, dict]:
    """Đọc qlnk_bo_sung cho nhiều món vay cùng lúc — tránh N+1 query."""
    if not ds_ma:
        return {}
    try:
        placeholders = ",".join("?" * len(ds_ma))
        with get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM qlnk_bo_sung WHERE ma_mon_vay IN ({placeholders})",
                list(ds_ma),
            ).fetchall()
        return {r["ma_mon_vay"]: dict(r) for r in rows}
    except Exception:
        return {}


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
    except Exception as e:  # conv: skip
        logger.error("duyet_ke_hoach thất bại id=%s: %s", kehoach_id, e, exc_info=True)
        ghi_audit(username, "loi_duyet_ke_hoach", str(e))
        return False


def luu_mau_bieu_cv368(loai_mau, ten_pgd, nam, dot, noi_dung_dict,
                       nguoi_lap, ghi_chu="") -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nd_json = json.dumps(noi_dung_dict, ensure_ascii=False)
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO mau_bieu_cv368
                   (loai_mau, ten_pgd, nam, dot, noi_dung, nguoi_lap, ngay_lap, ghi_chu, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (loai_mau, ten_pgd, int(nam), int(dot), nd_json, nguoi_lap, now, ghi_chu, now),
            )
            conn.commit()
            rec_id = cur.lastrowid
        ghi_audit(nguoi_lap, "luu_mau_bieu_cv368",
                  f"{loai_mau} PGD={ten_pgd} nam={nam} dot={dot}")
        return rec_id or 0
    except Exception as e:  # conv: skip
        logger.error("luu_mau_bieu_cv368 thất bại %s/%s: %s", loai_mau, ten_pgd, e, exc_info=True)
        ghi_audit(nguoi_lap, "loi_luu_mau_bieu_cv368", str(e))
        return 0


def doc_mau_bieu_cv368(ten_pgd=None, loai_mau=None, nam=None) -> list[dict]:
    conds, params = [], []
    if ten_pgd:
        conds.append("ten_pgd = ?"); params.append(ten_pgd)
    if loai_mau:
        conds.append("loai_mau = ?"); params.append(loai_mau)
    if nam:
        conds.append("nam = ?"); params.append(int(nam))
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    try:
        with get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM mau_bieu_cv368 {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["noi_dung"] = json.loads(d.get("noi_dung") or "{}")
            except Exception:
                d["noi_dung"] = {}
            result.append(d)
        return result
    except Exception:
        return []


def doc_mau_bieu_cv368_by_id(mb_id: int) -> dict | None:
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM mau_bieu_cv368 WHERE id = ?", (int(mb_id),)
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["noi_dung"] = json.loads(d.get("noi_dung") or "{}")
        except Exception:
            d["noi_dung"] = {}
        return d
    except Exception:
        return None


def xoa_audit_cu(ngay_giu_lai: int = 90) -> int:
    """Xóa audit_log cũ hơn ngay_giu_lai ngày. Trả về số dòng đã xóa."""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM audit_log WHERE ts < datetime('now', ?)",
                (f"-{ngay_giu_lai} days",),
            )
            conn.commit()
            return cur.rowcount
    except Exception:
        return 0


# Khởi tạo DB, migrate dữ liệu cũ, sau đó seed cấu hình động
init_db()
migrate_from_json()
seed_dynamic_configs()
migrate_pgd_bien_hoa()
migrate_legacy_user_roles()
_ = seed_ktnb_danh_muc_loi()
