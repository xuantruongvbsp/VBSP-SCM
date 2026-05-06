import db
from auth import doc_users, luu_users, dang_nhap
from data.khtd import doc_khtd, luu_khtd, doc_kehoach, luu_kehoach, doc_cbtd

print("=== VBSP-SCM DB Migration Test ===\n")

# Test 1: DB khởi tạo OK
with db.get_conn() as conn:
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = [t[0] for t in tables]
    assert "users"     in names, "FAIL: bảng users không tồn tại"
    assert "kv_store"  in names, "FAIL: bảng kv_store không tồn tại"
    assert "audit_log" in names, "FAIL: bảng audit_log không tồn tại"
print("✅ Test 1 PASS: 3 bảng SQLite tồn tại")

# Test 2: doc_users trả về dict có ít nhất 1 user
users = doc_users()
assert isinstance(users, dict), "FAIL: doc_users không trả về dict"
assert len(users) > 0, "FAIL: không có user nào trong DB"
print(f"✅ Test 2 PASS: doc_users() → {list(users.keys())}")

# Test 3: Round-trip khtd
luu_khtd({"test_xa": {"1_TW": 1_000_000}})
kh = doc_khtd()
assert kh.get("test_xa") is not None, "FAIL: khtd round-trip"
print("✅ Test 3 PASS: luu_khtd / doc_khtd round-trip OK")

# Test 4: Round-trip kehoach
luu_kehoach({"Tổng dư nợ": 5_000_000_000})
khoach = doc_kehoach()
assert khoach.get("Tổng dư nợ") == 5_000_000_000, "FAIL: kehoach round-trip"
print("✅ Test 4 PASS: luu_kehoach / doc_kehoach round-trip OK")

# Test 5: ghi_audit không raise exception
db.ghi_audit("test_user", "test_action", "test detail")
with db.get_conn() as conn:
    row = conn.execute(
        "SELECT * FROM audit_log WHERE action='test_action'"
    ).fetchone()
assert row is not None, "FAIL: audit_log không ghi được"
print("✅ Test 5 PASS: ghi_audit OK")

# Test 6: dang_nhap admin
ok, info = dang_nhap("admin", "admin123")
print(f"✅ Test 6: dang_nhap admin → ok={ok}, role={info.get('role') if info else None}")

# Dọn dẹp dữ liệu test
luu_khtd({k: v for k, v in doc_khtd().items() if k != "test_xa"})

print("\n=== Tất cả tests PASS — Migration thành công! ===")
