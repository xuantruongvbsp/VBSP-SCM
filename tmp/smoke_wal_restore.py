"""Smoke test: restore trong lúc file -wal đang tồn tại (kịch bản lỗi thực tế)."""
import sys
from pathlib import Path

ROOT = Path(r"D:\VBSP-SCM")
sys.path.insert(0, str(ROOT))

import backup_service  # noqa: E402
import db  # noqa: E402
import auth  # noqa: E402

wal = ROOT / "vbsp_scm.db-wal"

# 1. Đảm bảo -wal đang tồn tại (mô phỏng app đang chạy với WAL mode)
with db.get_conn() as conn:
    conn.execute("SELECT 1")
print("[1] WAL hien co ton tai:", wal.exists(), f"({wal.stat().st_size if wal.exists() else 0} bytes)")

# 2. Tạo backup mới từ DB hiện tại
kq = backup_service.chay_backup()
print("[2] Backup moi:", kq["ky"], "| db_ok:", kq["db_ok"])
assert kq["db_ok"]

# 3. Restore — kịch bản trước đây fail vì WAL cũ replay lên DB mới
zip_bytes = backup_service.zip_ban_backup(kq["ky"])
kq2 = backup_service.phuc_hoi_backup(zip_bytes)
print("[3] Restore:", kq2)
assert kq2["db_ok"], "Restore van that bai!"
assert not any("Loi ghi DB" in loi for loi in kq2["loi"]), "Van con loi ghi DB!"

# 4. Sau restore: đăng nhập + integrity
ok, info = auth.dang_nhap("admin", "123")
import sqlite3  # noqa: E402
ic = sqlite3.connect(str(ROOT / "vbsp_scm.db")).execute("PRAGMA integrity_check").fetchone()[0]
print("[4] Login admin/123:", "OK" if ok else "FAIL", "| integrity:", ic)
assert ok and ic == "ok"

# 5. Zip hỏng vẫn bị từ chối
import io, zipfile  # noqa: E402
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as zf:
    zf.writestr("vbsp_scm.db", b"NOT A SQLITE FILE " * 200)
kq3 = backup_service.phuc_hoi_backup(buf.getvalue())
print("[5] Zip hong bi tu choi:", not kq3["db_ok"], "| loi:", kq3["loi"][0][:60], "...")
assert not kq3["db_ok"]

# 6. DB vẫn lành sau từ chối
ok2, _ = auth.dang_nhap("admin", "123")
print("[6] Login sau tu choi zip hong:", "OK" if ok2 else "FAIL")
assert ok2

print()
print("=== TAT CA TEST PASSED ===")
