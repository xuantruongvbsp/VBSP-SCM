"""
Test module bảo mật — Security & NHCSXH Compliance Tests
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Test IP Whitelist
from security import (
    _ip_to_int,
    _is_ip_in_range,
    is_ip_allowed,
    get_ip_whitelist,
    add_ip_to_whitelist,
    remove_ip_from_whitelist,
    SESSION_TIMEOUT_MINUTES,
    check_session_timeout,
    generate_totp_secret,
    verify_totp,
    _hotp,
)


class TestIPWhitelist:
    """Test IP whitelist functionality."""

    def test_ip_to_int(self):
        """Test chuyển đổi IP string sang integer."""
        assert _ip_to_int("192.168.1.1") == 3232235777
        assert _ip_to_int("10.0.0.1") == 167772161
        assert _ip_to_int("127.0.0.1") == 2130706433

    def test_is_ip_in_range_single_ip(self):
        """Test kiểm tra single IP."""
        assert _is_ip_in_range("192.168.1.1", "192.168.1.1") is True
        assert _is_ip_in_range("192.168.1.1", "192.168.1.2") is False

    def test_is_ip_in_range_cidr(self):
        """Test kiểm tra CIDR range."""
        assert _is_ip_in_range("192.168.1.1", "192.168.1.0/24") is True
        assert _is_ip_in_range("192.168.1.100", "192.168.1.0/24") is True
        assert _is_ip_in_range("192.168.2.1", "192.168.1.0/24") is False
        assert _is_ip_in_range("10.0.0.50", "10.0.0.0/8") is True

    def test_is_ip_in_range_private_networks(self):
        """Test các private network ranges."""
        assert _is_ip_in_range("10.50.100.200", "10.0.0.0/8") is True
        assert _is_ip_in_range("172.20.50.100", "172.16.0.0/12") is True
        assert _is_ip_in_range("192.168.50.100", "192.168.0.0/16") is True

    def test_add_ip_validation(self):
        """Test validation khi thêm IP."""
        with patch('security.db') as mock_db:
            # Valid IP
            ok, msg = add_ip_to_whitelist("192.168.1.0/24", "admin")
            assert ok is True
            assert "Đã thêm" in msg

            # Invalid CIDR prefix
            ok, msg = add_ip_to_whitelist("192.168.1.0/33", "admin")
            assert ok is False
            assert "Prefix" in msg

            # Invalid IP format
            ok, msg = add_ip_to_whitelist("192.168.1", "admin")
            assert ok is False
            assert "Định dạng" in msg

            # Duplicate IP
            mock_db.doc_kv.return_value = ["192.168.1.0/24"]
            ok, msg = add_ip_to_whitelist("192.168.1.0/24", "admin")
            assert ok is False
            assert "đã tồn tại" in msg

    def test_remove_ip_validation(self):
        """Test validation khi xóa IP."""
        with patch('security.db') as mock_db:
            mock_db.doc_kv.return_value = ["192.168.1.0/24", "127.0.0.1"]

            # Cannot remove localhost
            ok, msg = remove_ip_from_whitelist("127.0.0.1", "admin")
            assert ok is False
            assert "không thể xóa localhost" in msg.lower()

            # IP not in whitelist
            ok, msg = remove_ip_from_whitelist("10.0.0.0/8", "admin")
            assert ok is False
            assert "không tồn tại" in msg


class TestTOTP2FA:
    """Test TOTP/2FA functionality."""

    def test_generate_totp_secret(self):
        """Test tạo secret key."""
        secret = generate_totp_secret()
        # Base32 encoded, length should be 32 chars
        assert len(secret) == 32
        # Should only contain valid base32 chars
        import base64
        decoded = base64.b32decode(secret)
        assert len(decoded) == 20  # 160 bits

    def test_hotp_generation(self):
        """Test HOTP value generation."""
        secret = "JBSWY3DPEHPK3PXP"  # Known test secret
        counter = 0
        code = _hotp(secret, counter)
        assert len(code) == 6
        assert code.isdigit()

    def test_verify_totp_valid_code(self):
        """Test xác thực mã TOTP hợp lệ."""
        secret = generate_totp_secret()
        # Generate current code
        counter = int(time.time()) // 30
        code = _hotp(secret, counter)

        # Should verify
        assert verify_totp(secret, code) is True

    def test_verify_totp_invalid_code(self):
        """Test xác thực mã TOTP không hợp lệ."""
        secret = generate_totp_secret()
        assert verify_totp(secret, "000000") is False
        assert verify_totp(secret, "999999") is False
        assert verify_totp(secret, "invalid") is False

    def test_verify_totp_window(self):
        """Test time window tolerance (±1 window)."""
        secret = generate_totp_secret()
        current_counter = int(time.time()) // 30

        # Previous window code should work
        prev_code = _hotp(secret, current_counter - 1)
        assert verify_totp(secret, prev_code) is True

        # Next window code should work
        next_code = _hotp(secret, current_counter + 1)
        assert verify_totp(secret, next_code) is True


class TestSessionTimeout:
    """Test session timeout functionality."""

    def test_session_timeout_minutes(self):
        """Test default session timeout value."""
        assert SESSION_TIMEOUT_MINUTES == 30

    def test_check_session_timeout_valid(self):
        """Test session còn hợp lệ."""
        from unittest.mock import MagicMock
        with patch('security.st') as mock_st:
            # Mock session_state hỗ trợ cả `in` và attribute access
            state = MagicMock()
            state.__contains__ = MagicMock(return_value=True)
            state._last_activity = time.time()
            mock_st.session_state = state
            is_valid, msg = check_session_timeout()
            assert is_valid is True
            assert msg == ""

    def test_check_session_timeout_expired(self):
        """Test session đã hết hạn."""
        from unittest.mock import MagicMock
        with patch('security.st') as mock_st, patch('security.db') as mock_db:
            # Mock session_state hỗ trợ cả `in` và attribute access
            state = MagicMock()
            state.__contains__ = MagicMock(return_value=True)
            state._last_activity = time.time() - (31 * 60)
            state.username = "testuser"
            mock_st.session_state = state
            is_valid, msg = check_session_timeout()
            assert is_valid is False
            assert "hết hạn" in msg.lower()
            assert "30" in msg


class TestAuditTrailFull:
    """Test audit trail đầy đủ với IP, UA, table_name."""

    def test_ghi_audit_full_basic(self):
        """Test ghi audit log đầy đủ."""
        # Patch db trong module db (nơi hàm ghi_audit_full được định nghĩa)
        with patch('db.get_conn') as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

            from db import ghi_audit_full
            ghi_audit_full(
                username="testuser",
                action="update",
                detail="Test update",
                table_name="users",
                record_id="123",
                old_value={"name": "Old"},
                new_value={"name": "New"},
                ip_address="192.168.1.1",
                user_agent="TestAgent/1.0",
            )

            # Verify connection was used
            mock_get_conn.assert_called()


@pytest.fixture
def security_context():
    """Fixture cung cấp security context cho test."""
    return {
        "ip_whitelist": ["127.0.0.1", "10.0.0.0/8", "192.168.0.0/16"],
        "test_secret": generate_totp_secret(),
    }


def test_integration_security_flow(security_context):
    """Test integration: flow bảo mật đầy đủ."""
    # 1. Kiểm tra IP
    assert is_ip_allowed("127.0.0.1") is True
    assert is_ip_allowed("192.168.1.100") is True
    assert is_ip_allowed("10.50.100.1") is True

    # 2. Kiểm tra 2FA
    secret = security_context["test_secret"]
    counter = int(time.time()) // 30
    valid_code = _hotp(secret, counter)
    assert verify_totp(secret, valid_code) is True

    # 3. Session timeout
    assert SESSION_TIMEOUT_MINUTES == 30
