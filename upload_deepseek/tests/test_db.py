"""Test KV store, audit log với SQLite tạm."""
import os
import json
import pytest
import db as db_module


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Fixture: tạo DB SQLite tạm, không ảnh hưởng DB thật."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("VBSP_SCM_DB_PATH", db_file)
    # Reset thread-local connection để lấy connection mới theo env var
    db_module.reset_conn()
    db_module.init_db()
    yield db_module
    # Dọn dẹp
    db_module.reset_conn()
    if os.path.exists(db_file):
        os.unlink(db_file)


# ═══════════════════════════════════════════════════════════════════════════════
# ghi_kv / doc_kv roundtrip
# ═══════════════════════════════════════════════════════════════════════════════

class TestKvRoundtrip:
    """Test ghi và đọc KV store."""

    def test_ghi_doc_kv_dict(self, test_db):
        """Ghi dict JSON, đọc lại phải giống dict gốc."""
        data = {"khtd_tw": 5_000_000_000, "khtd_dp": 2_000_000_000}
        test_db.ghi_kv("khtd_cn", data, username="test_user")
        result = test_db.doc_kv("khtd_cn")
        assert result == data

    def test_ghi_doc_kv_khong_doi_kieu_so(self, test_db):
        """Số nguyên 5_000_000_000 không bị đổi thành float (5.0) khi lưu JSON."""
        test_db.ghi_kv("test_so_tien", {"so_tien": 1_000_000}, username="test")
        result = test_db.doc_kv("test_so_tien")
        assert result["so_tien"] == 1_000_000
        assert isinstance(result["so_tien"], int), (
            f"Kiểu dữ liệu bị thay đổi: {type(result['so_tien'])} thay vì int"
        )

    def test_doc_kv_key_khong_ton_tai(self, test_db):
        """doc_kv key không tồn tại → None."""
        result = test_db.doc_kv("key_khong_ton_tai")
        assert result is None

    def test_doc_kv_key_khong_ton_tai_default(self, test_db):
        """doc_kv key không tồn tại với default → trả default."""
        result = test_db.doc_kv("key_khong_ton_tai", default="ABC")
        assert result == "ABC"


# ═══════════════════════════════════════════════════════════════════════════════
# ghi_kv ghi đè
# ═══════════════════════════════════════════════════════════════════════════════

class TestKvOverwrite:
    """Test ghi đè giá trị KV store."""

    def test_ghi_kv_overwrite(self, test_db):
        """Ghi key 2 lần, đọc lại phải lấy giá trị lần 2."""
        test_db.ghi_kv("test_key", {"a": 1}, username="user1")
        test_db.ghi_kv("test_key", {"a": 2}, username="user2")
        result = test_db.doc_kv("test_key")
        assert result == {"a": 2}


# ═══════════════════════════════════════════════════════════════════════════════
# ghi_audit
# ═══════════════════════════════════════════════════════════════════════════════

class TestAudit:
    """Test ghi audit log."""

    def test_ghi_audit_khong_crash(self, test_db):
        """ghi_audit không raise exception."""
        test_db.ghi_audit("admin", "test_action", "detail test")

    def test_ghi_audit_co_record(self, test_db):
        """Sau khi ghi audit, có thể query và thấy record."""
        test_db.ghi_audit("test_user", "insert", "test_detail")
        conn = test_db.get_conn()
        rows = conn.execute(
            "SELECT username, action, detail FROM audit_log WHERE username = ?",
            ("test_user",),
        ).fetchall()
        assert len(rows) >= 1
        row = rows[0]
        assert row["username"] == "test_user"
        assert row["action"] == "insert"
        assert row["detail"] == "test_detail"


# ═══════════════════════════════════════════════════════════════════════════════
# list_kv_prefix
# ═══════════════════════════════════════════════════════════════════════════════

class TestListKvPrefix:
    """Test liệt kê key theo prefix."""

    def test_list_kv_prefix(self, test_db):
        """Ghi 3 key, list prefix 'khtd_pgd_' trả về đúng 2 key."""
        test_db.ghi_kv("khtd_pgd_bien-hoa",   {"a": 1}, username="test")
        test_db.ghi_kv("khtd_pgd_long-khanh", {"b": 2}, username="test")
        test_db.ghi_kv("khac_key",            {"c": 3}, username="test")

        keys = test_db.list_kv_prefix("khtd_pgd_")
        assert len(keys) == 2
        assert "khtd_pgd_bien-hoa" in keys
        assert "khtd_pgd_long-khanh" in keys
        assert "khac_key" not in keys

    def test_list_kv_prefix_no_match(self, test_db):
        """Prefix không khớp key nào → list rỗng."""
        keys = test_db.list_kv_prefix("not_exist_")
        assert keys == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
