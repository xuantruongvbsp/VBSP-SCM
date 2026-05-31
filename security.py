"""
Bảo mật & Tuân thủ NHCSXH
- Session timeout 30 phút
- IP whitelist nội bộ
- 2FA cho admin
"""

import os
import re
import time
import json
import hmac
import hashlib
import base64
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from functools import wraps

import streamlit as st
import db
from logger import get_logger

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. SESSION TIMEOUT (30 phút)
# ═══════════════════════════════════════════════════════════════════════════════

SESSION_TIMEOUT_MINUTES = 30


def init_session_security():
    """Khởi tạo session state cho bảo mật."""
    if "_last_activity" not in st.session_state:
        st.session_state._last_activity = time.time()
    if "_login_time" not in st.session_state:
        st.session_state._login_time = time.time()
    if "_ip_address" not in st.session_state:
        st.session_state._ip_address = _get_client_ip()
    if "_user_agent" not in st.session_state:
        st.session_state._user_agent = _get_user_agent()


def _get_client_ip() -> str:
    """Lấy IP address của client từ request."""
    try:
        # Streamlit cloud/localhost
        if hasattr(st, "experimental_get_query_params"):
            # Thử lấy từ headers nếu có
            headers = st.context.headers if hasattr(st, "context") and hasattr(st.context, "headers") else {}
            if headers:
                ip = headers.get("X-Forwarded-For", headers.get("X-Real-IP", "127.0.0.1"))
                return ip.split(",")[0].strip()
    except Exception:
        pass
    return "127.0.0.1"


def _get_user_agent() -> str:
    """Lấy user agent từ request."""
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            return st.context.headers.get("User-Agent", "")
    except Exception:
        pass
    return ""


def update_last_activity():
    """Cập nhật thời gian hoạt động cuối."""
    st.session_state._last_activity = time.time()


def check_session_timeout() -> Tuple[bool, str]:
    """
    Kiểm tra session timeout.
    
    Returns:
        (is_valid, message): True nếu session còn hợp lệ
    """
    if "_last_activity" not in st.session_state:
        return True, ""
    
    last_activity = st.session_state._last_activity
    timeout_seconds = SESSION_TIMEOUT_MINUTES * 60
    
    if time.time() - last_activity > timeout_seconds:
        username = st.session_state.get("username", "unknown")
        db.ghi_audit(username, "session_timeout", f"Timeout sau {SESSION_TIMEOUT_MINUTES} phút không hoạt động")
        return False, f"Phiên làm việc đã hết hạn sau {SESSION_TIMEOUT_MINUTES} phút không hoạt động"
    
    return True, ""


def check_and_handle_timeout():
    """Kiểm tra timeout và xử lý logout nếu cần."""
    is_valid, message = check_session_timeout()
    if not is_valid:
        # Clear session
        username = st.session_state.get("username", "unknown")
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state._logout_reason = message
        st.session_state._logout_time = datetime.now().isoformat()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. IP WHITELIST
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_IP_RANGES = [
    "127.0.0.1",           # localhost
    "10.0.0.0/8",          # Private network (NHCSXH internal)
    "172.16.0.0/12",       # Private network
    "192.168.0.0/16",      # Private network
]


def _ip_to_int(ip: str) -> int:
    """Chuyển IP string sang integer."""
    parts = ip.split(".")
    return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])


def _is_ip_in_range(ip: str, ip_range: str) -> bool:
    """Kiểm tra IP có nằm trong range không."""
    if "/" not in ip_range:
        return ip == ip_range
    
    # CIDR notation
    network, prefix = ip_range.split("/")
    prefix = int(prefix)
    
    ip_int = _ip_to_int(ip)
    network_int = _ip_to_int(network)
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    
    return (ip_int & mask) == (network_int & mask)


def get_ip_whitelist() -> list[str]:
    """Lấy danh sách IP whitelist từ kv_store."""
    whitelist = db.doc_kv("ip_whitelist")
    if whitelist is None:
        # Lưu default vào kv_store
        db.ghi_kv("ip_whitelist", DEFAULT_IP_RANGES, "system", "Init default IP whitelist")
        return DEFAULT_IP_RANGES
    return whitelist


def is_ip_allowed(ip: str) -> bool:
    """Kiểm tra IP có được phép truy cập không."""
    whitelist = get_ip_whitelist()
    for ip_range in whitelist:
        if _is_ip_in_range(ip, ip_range):
            return True
    return False


def add_ip_to_whitelist(ip_range: str, username: str) -> Tuple[bool, str]:
    """Thêm IP range vào whitelist."""
    # Validate IP range format
    if "/" in ip_range:
        try:
            network, prefix = ip_range.split("/")
            prefix = int(prefix)
            if not (0 <= prefix <= 32):
                return False, "Prefix phải từ 0-32"
            # Validate IP format
            parts = network.split(".")
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                return False, "Định dạng IP không hợp lệ"
        except Exception:
            return False, "Định dạng IP range không hợp lệ (VD: 192.168.1.0/24)"
    else:
        # Single IP
        parts = ip_range.split(".")
        if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return False, "Định dạng IP không hợp lệ"
    
    whitelist = get_ip_whitelist()
    if ip_range in whitelist:
        return False, "IP range đã tồn tại trong whitelist"
    
    whitelist.append(ip_range)
    db.ghi_kv("ip_whitelist", whitelist, username, f"Thêm IP: {ip_range}")
    db.ghi_audit(username, "add_ip_whitelist", f"Thêm IP range: {ip_range}")
    return True, "Đã thêm IP range vào whitelist"


def remove_ip_from_whitelist(ip_range: str, username: str) -> Tuple[bool, str]:
    """Xóa IP range khỏi whitelist."""
    whitelist = get_ip_whitelist()
    if ip_range not in whitelist:
        return False, "IP range không tồn tại trong whitelist"
    
    # Không cho xóa localhost
    if ip_range == "127.0.0.1":
        return False, "Không thể xóa localhost (127.0.0.1)"
    
    whitelist.remove(ip_range)
    db.ghi_kv("ip_whitelist", whitelist, username, f"Xóa IP: {ip_range}")
    db.ghi_audit(username, "remove_ip_whitelist", f"Xóa IP range: {ip_range}")
    return True, "Đã xóa IP range khỏi whitelist"


def check_ip_and_handle():
    """Kiểm tra IP và xử lý nếu không được phép."""
    ip = _get_client_ip()
    if not is_ip_allowed(ip):
        username = st.session_state.get("username", "unknown")
        db.ghi_audit(username, "ip_blocked", f"Truy cập từ IP không cho phép: {ip}")
        st.error(f"⛔ IP {ip} không được phép truy cập hệ thống.")
        st.info("Vui lòng liên hệ quản trị viên để được hỗ trợ.")
        st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 2FA (TOTP) cho Admin
# ═══════════════════════════════════════════════════════════════════════════════


def generate_totp_secret() -> str:
    """Tạo secret key cho TOTP."""
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8")


def get_totp_uri(secret: str, username: str, issuer: str = "VBSP-SCM") -> str:
    """Tạo TOTP URI cho QR code."""
    return f"otpauth://totp/{issuer}:{username}?secret={secret}&issuer={issuer}"


def verify_totp(secret: str, code: str) -> bool:
    """Xác thực mã TOTP."""
    try:
        counter = int(time.time()) // 30
        
        # Thử 3 window: hiện tại, trước 1, sau 1
        for offset in [-1, 0, 1]:
            expected = _hotp(secret, counter + offset)
            if hmac.compare_digest(expected, code.zfill(6)):
                return True
        return False
    except Exception:
        return False


def _hotp(secret: str, counter: int, digits: int = 6) -> str:
    """Tính HOTP value."""
    key = base64.b32decode(secret.upper())
    counter_bytes = counter.to_bytes(8, byteorder="big")
    
    mac = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    
    code = ((mac[offset] & 0x7F) << 24 |
            (mac[offset + 1] & 0xFF) << 16 |
            (mac[offset + 2] & 0xFF) << 8 |
            (mac[offset + 3] & 0xFF))
    
    return str(code % (10 ** digits)).zfill(digits)


def is_2fa_enabled(username: str) -> bool:
    """Kiểm tra user có bật 2FA không."""
    user_2fa = db.doc_kv(f"2fa_user_{username}")
    return user_2fa is not None and user_2fa.get("enabled", False)


def enable_2fa(username: str, code: str) -> Tuple[bool, str]:
    """Bật 2FA cho user."""
    # Kiểm tra xem có secret đang chờ xác nhận không
    pending = db.doc_kv(f"2fa_pending_{username}")
    if not pending:
        return False, "Không tìm thấy yêu cầu kích hoạt 2FA. Vui lòng bắt đầu lại quy trình."
    
    secret = pending.get("secret")
    if not verify_totp(secret, code):
        return False, "Mã xác thực không đúng. Vui lòng thử lại."
    
    # Lưu 2FA setting
    db.ghi_kv(f"2fa_user_{username}", {
        "enabled": True,
        "secret": secret,
        "enabled_at": datetime.now().isoformat(),
    }, username, "Kích hoạt 2FA")
    
    # Xóa pending
    db.ghi_kv(f"2fa_pending_{username}", None, username, "")
    
    db.ghi_audit(username, "2fa_enabled", "Kích hoạt xác thực 2 yếu tố")
    return True, "Đã kích hoạt 2FA thành công"


def disable_2fa(username: str, password: str, verify_func) -> Tuple[bool, str]:
    """Tắt 2FA cho user (cần xác thực password)."""
    if not verify_func(password):
        return False, "Mật khẩu không đúng"
    
    if not is_2fa_enabled(username):
        return False, "2FA chưa được kích hoạt cho tài khoản này"
    
    db.ghi_kv(f"2fa_user_{username}", None, username, "Vô hiệu hóa 2FA")
    db.ghi_audit(username, "2fa_disabled", "Vô hiệu hóa xác thực 2 yếu tố")
    return True, "Đã tắt 2FA"


def setup_2fa(username: str) -> Tuple[bool, str, str]:
    """Bắt đầu thiết lập 2FA, trả về (success, message, secret)."""
    if is_2fa_enabled(username):
        return False, "2FA đã được kích hoạt", ""
    
    secret = generate_totp_secret()
    
    # Lưu pending để xác nhận sau
    db.ghi_kv(f"2fa_pending_{username}", {
        "secret": secret,
        "created_at": datetime.now().isoformat(),
    }, username, "Bắt đầu thiết lập 2FA")
    
    return True, "", secret


def verify_2fa_login(username: str, code: str) -> bool:
    """Xác thực 2FA trong quá trình đăng nhập."""
    if not is_2fa_enabled(username):
        return True  # 2FA chưa bật, cho phép đăng nhập
    
    user_2fa = db.doc_kv(f"2fa_user_{username}")
    secret = user_2fa.get("secret")
    
    if not secret:
        return False
    
    if verify_totp(secret, code):
        db.ghi_audit(username, "2fa_login_success", "Đăng nhập thành công với 2FA")
        return True
    else:
        db.ghi_audit(username, "2fa_login_failed", "Mã 2FA không đúng")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DECORATOR cho các hàm cần bảo mật
# ═══════════════════════════════════════════════════════════════════════════════

def require_security_check(func):
    """Decorator kiểm tra session timeout và IP whitelist."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Kiểm tra timeout
        is_valid, message = check_session_timeout()
        if not is_valid:
            st.error(f"⛔ {message}")
            st.session_state.clear()
            st.rerun()
        
        # Kiểm tra IP
        if not is_ip_allowed(_get_client_ip()):
            st.error("⛔ IP không được phép truy cập")
            st.stop()
        
        # Cập nhật last activity
        update_last_activity()
        
        return func(*args, **kwargs)
    return wrapper


def audit_trail(table_name: str, action: str, get_record_id=None):
    """
    Decorator ghi audit log đầy đủ khi thao tác dữ liệu.
    
    Args:
        table_name: Tên bảng
        action: Loại hành động (insert, update, delete)
        get_record_id: Hàm lấy record_id từ args/kwargs
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            username = st.session_state.get("username", "system")
            ip = _get_client_ip()
            ua = _get_user_agent()
            
            record_id = None
            if get_record_id:
                try:
                    record_id = get_record_id(*args, **kwargs)
                except Exception:
                    pass
            
            old_value = None
            new_value = None
            
            result = func(*args, **kwargs)
            
            # Ghi audit
            db.ghi_audit_full(
                username=username,
                action=action,
                detail=f"{action} trên {table_name}",
                table_name=table_name,
                record_id=record_id,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip,
                user_agent=ua,
            )
            
            return result
        return wrapper
    return decorator
