"""
Tab Quản lý Bảo mật — IP Whitelist, 2FA, Session Management
Tuân thủ NHCSXH — Thông tư 09/2019/TT-NHNN về An ninh thông tin
"""

from __future__ import annotations

import streamlit as st
import db
from auth import la_admin_cn, normalize_role
from tabs.base_tab import TabContext
from security import (
    get_ip_whitelist,
    add_ip_to_whitelist,
    remove_ip_from_whitelist,
    is_2fa_enabled,
    enable_2fa,
    disable_2fa,
    setup_2fa,
    verify_totp,
    get_totp_uri,
    SESSION_TIMEOUT_MINUTES,
)
from logger import get_logger

logger = get_logger(__name__)


def render(tab=None, **kwargs) -> None:
    """Render tab quản lý bảo mật."""
    role = kwargs.get("role", "")
    username = kwargs.get("username", "")

    if not la_admin_cn(role):
        st.warning("⛔ Chỉ Admin CN mới có quyền truy cập trang này.")
        return

    _tab_ctx = TabContext(tab, **kwargs)
    with _tab_ctx:
        st.subheader("🔐 Quản lý Bảo mật NHCSXH")
        st.caption(f"Tuân thủ Thông tư 09/2019/TT-NHNN | Session timeout: {SESSION_TIMEOUT_MINUTES} phút")

        tab1, tab2, tab3 = st.tabs(["🌐 IP Whitelist", "🔢 2FA/TOTP", "📋 Audit Trail"])

        with tab1:
            _render_ip_whitelist(username)

        with tab2:
            _render_2fa_manager(username)

        with tab3:
            _render_audit_settings(username)


def _render_ip_whitelist(username: str) -> None:
    """Render phần quản lý IP Whitelist."""
    st.markdown("#### 🌐 Quản lý IP Whitelist")
    st.info(
        "Giới hạn truy cập theo IP nội bộ NHCSXH. "
        "Mặc định cho phép: localhost, 10.x.x.x, 172.16-31.x.x, 192.168.x.x"
    )

    whitelist = get_ip_whitelist()

    # Hiển thị danh sách hiện tại
    st.markdown("**Danh sách IP được phép:**")
    cols = st.columns([3, 1])
    for ip_range in whitelist:
        with cols[0]:
            st.markdown(f"- `{ip_range}`")
        with cols[1]:
            if ip_range != "127.0.0.1":  # Không cho xóa localhost
                if st.button(f"🗑️ Xóa", key=f"del_ip_{ip_range}"):
                    ok, msg = remove_ip_from_whitelist(ip_range, username)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # Thêm IP mới
    st.divider()
    st.markdown("**Thêm IP range mới:**")
    col1, col2 = st.columns([3, 1])
    with col1:
        new_ip = st.text_input(
            "IP/Range",
            placeholder="VD: 192.168.1.0/24 hoặc 10.0.0.50",
            key="new_ip_range",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Thêm", use_container_width=True, key="security_add_ip"):
            if new_ip.strip():
                ok, msg = add_ip_to_whitelist(new_ip.strip(), username)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("Vui lòng nhập IP range")

    # Hướng dẫn
    with st.expander("ℹ️ Hướng dẫn định dạng IP"):
        st.markdown("""
        - **Single IP**: `192.168.1.100` — cho phép 1 IP cụ thể
        - **CIDR Range**: `192.168.1.0/24` — cho phép toàn bộ subnet 192.168.1.x
        - **Private networks**: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
        """)


def _render_2fa_manager(username: str) -> None:
    """Render phần quản lý 2FA."""
    st.markdown("#### 🔢 Xác thực 2 yếu tố (2FA/TOTP)")
    st.info(
        "Bảo vệ tài khoản Admin bằng Google Authenticator hoặc các app TOTP tương thích."
    )

    is_enabled = is_2fa_enabled(username)

    if is_enabled:
        st.success("✅ 2FA đã được kích hoạt cho tài khoản này")

        # Form tắt 2FA
        with st.expander("⚠️ Vô hiệu hóa 2FA", expanded=False):
            st.warning("Vô hiệu hóa 2FA sẽ làm giảm bảo mật tài khoản.")
            pw = st.text_input("Nhập mật khẩu để xác nhận", type="password", key="2fa_disable_pw")
            if st.button("🔓 Vô hiệu hóa 2FA", type="secondary", key="security_disable_2fa"):
                # Cần hàm kiểm tra password — giả định dùng từ auth
                from auth import kiem_tra, doc_users
                users = doc_users()
                user_data = users.get(username, {})
                if kiem_tra(pw, user_data.get("password", "")):
                    db.ghi_kv(f"2fa_user_{username}", None, username, "Vô hiệu hóa 2FA")
                    db.ghi_audit(username, "2fa_disabled", "Vô hiệu hóa xác thực 2 yếu tố")
                    st.success("Đã vô hiệu hóa 2FA")
                    st.rerun()
                else:
                    st.error("Mật khẩu không đúng")
    else:
        st.warning("⚠️ 2FA chưa được kích hoạt")

        # Quy trình bật 2FA
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("**Bước 1: Tạo mã QR**")
            if st.button("🔄 Tạo mã QR mới", key="gen_2fa"):
                ok, msg, secret = setup_2fa(username)
                if ok:
                    st.session_state["_2fa_secret"] = secret
                    st.session_state["_2fa_step"] = 1
                    st.rerun()
                else:
                    st.error(msg)

            if st.session_state.get("_2fa_step") == 1:
                secret = st.session_state.get("_2fa_secret", "")
                if secret:
                    # Hiển thị QR code (giả lập bằng text vì không có PIL)
                    uri = get_totp_uri(secret, username)
                    st.markdown("**Mã QR (quét bằng Google Authenticator):**")
                    st.code(uri)

                    # Hiển thị secret để nhập thủ công
                    st.markdown("**Hoặc nhập thủ công:**")
                    st.code(secret)

        with col2:
            st.markdown("**Bước 2: Xác nhận mã**")
            if st.session_state.get("_2fa_step") == 1:
                code = st.text_input("Nhập mã 6 số từ app", key="2fa_code", max_chars=6)
                if st.button("✅ Xác nhận", key="verify_2fa"):
                    ok, msg = enable_2fa(username, code)
                    if ok:
                        st.success(msg)
                        st.session_state.pop("_2fa_step", None)
                        st.session_state.pop("_2fa_secret", None)
                        st.rerun()
                    else:
                        st.error(msg)

        # Hướng dẫn
        with st.expander("ℹ️ Hướng dẫn thiết lập 2FA"):
            st.markdown("""
            1. **Tải Google Authenticator** trên điện thoại
            2. **Bấm "Tạo mã QR mới"** ở trên
            3. **Quét mã QR** bằng app hoặc nhập secret thủ công
            4. **Nhập mã 6 số** từ app để xác nhận
            5. **Lưu backup codes** — dùng khi mất điện thoại
            """)


def _render_audit_settings(username: str) -> None:
    """Render phần cài đặt audit trail."""
    st.markdown("#### 📋 Cài đặt Audit Trail")

    # Thống kê audit log
    try:
        with db.get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            today = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE ts >= date('now')"
            ).fetchone()[0]
            has_full_audit = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE ip_address IS NOT NULL"
            ).fetchone()[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng bản ghi", f"{total:,}")
        col2.metric("Hôm nay", f"{today:,}")
        col3.metric("Có IP/UA", f"{has_full_audit:,}")
    except Exception as e:
        logger.error("tab_security: doc_thong_ke_audit — %s", e, exc_info=True)
        st.error(f"Không thể đọc thống kê audit: {e}")

    st.divider()

    # Cài đặt session timeout
    st.markdown("**Cài đặt Session Timeout:**")
    st.info(f"Hiện tại: **{SESSION_TIMEOUT_MINUTES} phút** (mặc định theo Thông tư 09/2019)")

    st.markdown("**Xóa audit log cũ:**")
    days_to_keep = st.slider(
        "Giữ lại bản ghi trong",
        min_value=30,
        max_value=365,
        value=90,
        step=30,
        key="audit_retention",
    )

    if st.button("🗑️ Xóa bản ghi cũ", type="secondary", key="sec_btn_xoa_audit"):
        try:
            with db.get_conn() as conn:
                deleted = conn.execute(
                    "DELETE FROM audit_log WHERE ts < date('now', '-{} days')".format(days_to_keep)
                ).rowcount
                conn.commit()
            db.ghi_audit(username, "audit_cleanup", f"Xóa {deleted} bản ghi cũ hơn {days_to_keep} ngày")
            st.success(f"Đã xóa {deleted} bản ghi cũ")
        except Exception as e:
            logger.error("tab_security: audit_cleanup — %s", e, exc_info=True)
            st.error(f"Lỗi: {e}")
