"""Quản trị Telegram Bot — cấu hình token, bật/tắt thông báo, xem lịch sử gửi."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, normalize_role


_NOTIFY_ITEMS = [
    ("bao_cao_sang",      "📊 Báo cáo tổng hợp sáng",       "Số liệu dư nợ, NQH gửi mỗi sáng"),
    ("khoang_den_han",    "⏰ Nhắc khoản đến hạn",           "Danh sách khoản vay đáo hạn trong tháng"),
    ("deadline_bc",       "⚠️ Nhắc nộp báo cáo",             "PGD chưa nộp khi gần deadline"),
    ("nhap_lieu",         "📝 Nhắc nhập liệu GSheet",        "PGD chưa hoàn thành nhập liệu theo dõi"),
    ("health_check",      "🔍 Kết quả Health Check",         "Trạng thái hệ thống mỗi buổi sáng"),
    ("merge_thanh_cong",  "✅ Thông báo merge dữ liệu",      "Khi Phòng KH-NV gộp xong 22 PGD"),
]


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")

    ctx = tab if tab is not None else st.container()
    with ctx:
        if not la_phan_he_cn(role):
            st.warning("⚠️ Chức năng dành riêng cho cán bộ Chi nhánh.")
            return

        st.subheader("🤖 Quản trị Telegram Bot")

        # ── Expander 1: Cấu hình bot ───────────────────────────────────────────
        with st.expander("⚙️ Cấu hình Bot (Token & Chat ID)", expanded=True):
            cfg = db.doc_kv("telegram_config") or {}
            cur_token   = cfg.get("token", "")
            cur_chat_id = cfg.get("chat_id", "-5339155216")

            col1, col2 = st.columns(2)
            with col1:
                new_token = st.text_input(
                    "Bot Token",
                    value=cur_token,
                    type="password",
                    placeholder="110xxxxxxx:AAF...",
                    key="tg_token",
                )
            with col2:
                new_chat_id = st.text_input(
                    "Chat ID",
                    value=cur_chat_id,
                    placeholder="-100xxxxxxxxxx",
                    key="tg_chat_id",
                )

            c_luu, c_test, _ = st.columns([1, 1, 3])
            with c_luu:
                if st.button("💾 Lưu", key="tg_btn_luu", use_container_width=True):
                    if not new_token.strip():
                        st.error("❌ Token không được để trống.")
                    elif not new_chat_id.strip():
                        st.error("❌ Chat ID không được để trống.")
                    else:
                        from services.telegram_service import luu_config
                        luu_config(new_token.strip(), new_chat_id.strip(), username)
                        st.success("✅ Đã lưu cấu hình bot.")

            with c_test:
                if st.button("🧪 Test", key="tg_btn_test", use_container_width=True):
                    from services.telegram_service import gui_tin
                    ok = gui_tin("✅ <b>VBSP-SCM</b> kết nối Telegram thành công!")
                    if ok:
                        st.success("✅ Gửi thành công — kiểm tra group Telegram.")
                    else:
                        st.error("❌ Gửi thất bại — kiểm tra Token và Chat ID.")

            if cur_token:
                st.caption(f"Token hiện tại: `...{cur_token[-8:]}`   |   Chat ID: `{cur_chat_id}`")
            else:
                st.caption("⚠️ Chưa cấu hình token — đang dùng giá trị mặc định từ biến môi trường.")

        # ── Expander 2: Bật/tắt thông báo ─────────────────────────────────────
        with st.expander("🔔 Bật / Tắt thông báo", expanded=False):
            notify_cfg = db.doc_kv("telegram_notify_config") or {}
            new_cfg: dict[str, bool] = {}
            changed = False

            for key, label, mo_ta in _NOTIFY_ITEMS:
                cur_val = bool(notify_cfg.get(key, True))
                new_val = st.checkbox(label, value=cur_val, key=f"tg_notify_{key}", help=mo_ta)
                new_cfg[key] = new_val
                if new_val != cur_val:
                    changed = True

            if changed:
                if st.button("💾 Lưu cài đặt thông báo", key="tg_notify_save", type="primary"):
                    db.ghi_kv("telegram_notify_config", new_cfg, username)
                    db.ghi_audit(username, "telegram_notify_config", "Cập nhật bật/tắt thông báo Telegram")
                    st.success("✅ Đã lưu.")
                    st.rerun()
            else:
                st.caption("Thay đổi giá trị để hiện nút Lưu.")

        # ── Expander 3: Lịch sử gửi ────────────────────────────────────────────
        with st.expander("📋 Lịch sử gửi", expanded=False):
            log = db.doc_kv("telegram_send_log") or []
            if not log:
                st.caption("Chưa có lịch sử gửi.")
            else:
                rows = []
                for entry in log[:50]:
                    ts       = (entry.get("ts") or "")[:19].replace("T", " ")
                    func     = entry.get("func", "")
                    preview  = entry.get("preview", "")
                    ok       = entry.get("ok", False)
                    err      = entry.get("error", "")
                    ket_qua  = "✅" if ok else f"❌ {err[:60]}"
                    rows.append({"Thời gian": ts, "Loại": func, "Nội dung": preview, "Kết quả": ket_qua})

                import pandas as pd
                df_log = pd.DataFrame(rows)

                # Highlight dòng lỗi
                def _color(row):
                    if row["Kết quả"].startswith("❌"):
                        return ["background-color: #ffeaea"] * len(row)
                    return [""] * len(row)

                st.dataframe(
                    df_log.style.apply(_color, axis=1),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(f"Hiển thị {min(50, len(log))}/{len(log)} bản ghi gần nhất.")
