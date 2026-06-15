"""Gửi thông báo Telegram 1 chiều cho VBSP-SCM (push notification)."""
from __future__ import annotations

import html as _html
import os
import time
from datetime import datetime

import requests

import db
from logger import get_logger

logger = get_logger(__name__)

_DEFAULT_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_DEFAULT_CHAT_ID = "-5339155216"
_API_TIMEOUT     = 10  # giây


# ── Config ─────────────────────────────────────────────────────────────────────

def _get_config() -> tuple[str, str]:
    """Đọc token/chat_id từ kv_store, fallback về default."""
    cfg = db.doc_kv("telegram_config") or {}
    return (
        cfg.get("token",   _DEFAULT_TOKEN),
        cfg.get("chat_id", _DEFAULT_CHAT_ID),
    )


def luu_config(token: str, chat_id: str, username: str = "system") -> None:
    """Cập nhật token/chat_id — gọi từ tab Cài đặt bot."""
    db.ghi_kv("telegram_config", {"token": token, "chat_id": chat_id}, username)
    db.ghi_audit(username, "telegram_config", f"Cập nhật telegram config (chat_id={chat_id})")


def _la_bat(key: str) -> bool:
    """Kiểm tra loại thông báo có được bật không (mặc định BẬT)."""
    cfg = db.doc_kv("telegram_notify_config") or {}
    return bool(cfg.get(key, True))


def _ghi_log(func: str, preview: str, ok: bool, error: str = "") -> None:
    """Ghi log gửi tin vào kv_store (max 100 entries, FIFO)."""
    try:
        log = db.doc_kv("telegram_send_log") or []
        log.insert(0, {
            "ts":      datetime.now().isoformat(),
            "func":    func,
            "preview": preview[:80],
            "ok":      ok,
            "error":   error,
        })
        db.ghi_kv("telegram_send_log", log[:100], "system")
    except Exception as e:
        logger.warning("_ghi_log: %s", e)


# ── Core ───────────────────────────────────────────────────────────────────────

def gui_tin(text: str, parse_mode: str = "HTML") -> bool:
    """Gửi tin nhắn văn bản. Retry tối đa 2 lần khi lỗi mạng. Trả về True nếu thành công."""
    token, chat_id = _get_config()
    last_err = ""
    for attempt in range(3):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
                timeout=_API_TIMEOUT,
            )
            if r.ok:
                _ghi_log("gui_tin", text, True)
                return True
            last_err = f"HTTP {r.status_code}: {r.text[:100]}"
            logger.warning("telegram gui_tin attempt %d: %s", attempt + 1, last_err)
            break  # HTTP error → không retry (lỗi config/nội dung)
        except Exception as e:
            last_err = str(e)
            logger.warning("telegram gui_tin attempt %d: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2)
    _ghi_log("gui_tin", text, False, last_err)
    return False


# ── Thông báo nghiệp vụ ────────────────────────────────────────────────────────

def gui_canh_bao_deadline(ten_loai: str, deadline: str, chua_nop: list[str]) -> bool:
    """Nhắc các PGD chưa nộp báo cáo trước deadline."""
    if not _la_bat("deadline_bc"):
        return True
    if not chua_nop:
        return True
    ds = "\n".join(f"  • {_html.escape(pgd)}" for pgd in chua_nop)
    text = (
        f"⚠️ <b>Nhắc nộp {_html.escape(ten_loai)}</b>\n"
        f"📅 Deadline: <b>{_html.escape(deadline)}</b>\n\n"
        f"<b>{len(chua_nop)} đơn vị chưa nộp:</b>\n{ds}"
    )
    return gui_tin(text)


def gui_ket_qua_health_check(
    ok_count: int,
    warn_count: int,
    err_count: int,
    ngay: str = "",
    chi_tiet: str = "",
) -> bool:
    """Kết quả health check buổi sáng."""
    if not _la_bat("health_check"):
        return True
    icon = "🔴" if err_count > 0 else "🟡" if warn_count > 0 else "🟢"
    parts = [f"{icon} <b>Health Check VBSP-SCM</b>"]
    if ngay:
        parts.append(f"📅 {_html.escape(ngay)}")
    parts.append(f"✅ OK: {ok_count}   ⚠️ Cảnh báo: {warn_count}   ❌ Lỗi: {err_count}")
    if chi_tiet:
        parts.append("")
        parts.append(_html.escape(chi_tiet))
    return gui_tin("\n".join(parts))


def gui_thong_bao_merge(loai: str, so_pgd: int, username: str) -> bool:
    """Thông báo sau khi merge dữ liệu toàn CN thành công."""
    if not _la_bat("merge_thanh_cong"):
        return True
    text = (
        f"✅ <b>Merge {_html.escape(loai.upper())} thành công</b>\n"
        f"👤 {_html.escape(username)} vừa gộp dữ liệu <b>{so_pgd} PGD</b>"
    )
    return gui_tin(text)


def gui_nhac_khoang_den_han(ds_khoang: list[dict]) -> bool:
    """Nhắc khoản vay đến hạn trong tháng.

    Mỗi item: {"ten_kh": str, "so_ku": str, "ngay_dh": str, "du_no": str, "ten_pgd": str}
    """
    if not _la_bat("khoang_den_han"):
        return True
    if not ds_khoang:
        return True
    lines = [f"⏰ <b>Khoản đến hạn trong tháng ({len(ds_khoang)} khoản)</b>", ""]
    for k in ds_khoang[:20]:
        lines.append(
            f"  • {_html.escape(k.get('ten_kh',''))} — {_html.escape(k.get('so_ku',''))} — "
            f"{_html.escape(k.get('ngay_dh',''))} — {_html.escape(k.get('du_no',''))} "
            f"({_html.escape(k.get('ten_pgd',''))})"
        )
    if len(ds_khoang) > 20:
        lines.append(f"  … và {len(ds_khoang) - 20} khoản khác")
    return gui_tin("\n".join(lines))


def gui_bao_cao_sang(
    ngay: str,
    tong_du_no: str,
    tong_qh: str,
    ty_le_qh: str,
    so_pgd_da_upload: int,
    tong_pgd: int,
) -> bool:
    """Tóm tắt số liệu buổi sáng — gọi từ scripts/daily_report.py."""
    if not _la_bat("bao_cao_sang"):
        return True
    pgd_status = "✅" if so_pgd_da_upload >= tong_pgd else "⚠️"
    text = (
        f"📊 <b>Báo cáo sáng {_html.escape(ngay)}</b>\n\n"
        f"💰 Tổng dư nợ: <b>{_html.escape(tong_du_no)}</b>\n"
        f"🔴 Dư nợ quá hạn: <b>{_html.escape(tong_qh)}</b> ({_html.escape(ty_le_qh)})\n"
        f"{pgd_status} PGD đã upload: <b>{so_pgd_da_upload}/{tong_pgd}</b>"
    )
    return gui_tin(text)
