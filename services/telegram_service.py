"""Gửi thông báo Telegram 1 chiều cho VBSP-SCM (push notification)."""
from __future__ import annotations

import requests

import db
from logger import get_logger

logger = get_logger(__name__)

_DEFAULT_TOKEN   = "8907687363:AAHNyQlwks9jA5x4TpuMeqbPIP2RXy2VNEg"
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
    """Cập nhật token/chat_id — gọi từ trang Cài đặt nếu muốn đổi bot."""
    db.ghi_kv("telegram_config", {"token": token, "chat_id": chat_id}, username)
    db.ghi_audit(username, "telegram_config", f"Cập nhật telegram config (chat_id={chat_id})")


# ── Core ───────────────────────────────────────────────────────────────────────

def gui_tin(text: str, parse_mode: str = "HTML") -> bool:
    """Gửi tin nhắn văn bản. Trả về True nếu thành công."""
    token, chat_id = _get_config()
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=_API_TIMEOUT,
        )
        if not r.ok:
            logger.warning("telegram gui_tin: HTTP %s — %s", r.status_code, r.text[:200])
        return r.ok
    except Exception as e:
        logger.error("telegram gui_tin: %s", e)
        return False


# ── Thông báo nghiệp vụ ────────────────────────────────────────────────────────

def gui_canh_bao_deadline(ten_loai: str, deadline: str, chua_nop: list[str]) -> bool:
    """Nhắc các PGD chưa nộp báo cáo trước deadline."""
    if not chua_nop:
        return True
    ds = "\n".join(f"  • {pgd}" for pgd in chua_nop)
    text = (
        f"⚠️ <b>Nhắc nộp {ten_loai}</b>\n"
        f"📅 Deadline: <b>{deadline}</b>\n\n"
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
    if err_count > 0:
        icon = "🔴"
    elif warn_count > 0:
        icon = "🟡"
    else:
        icon = "🟢"
    parts = [
        f"{icon} <b>Health Check VBSP-SCM</b>",
    ]
    if ngay:
        parts.append(f"📅 {ngay}")
    parts.append(
        f"✅ OK: {ok_count}   ⚠️ Cảnh báo: {warn_count}   ❌ Lỗi: {err_count}"
    )
    if chi_tiet:
        parts.append("")
        parts.append(chi_tiet)
    return gui_tin("\n".join(parts))


def gui_thong_bao_merge(loai: str, so_pgd: int, username: str) -> bool:
    """Thông báo sau khi merge dữ liệu toàn CN thành công."""
    label = loai.upper()
    text = (
        f"✅ <b>Merge {label} thành công</b>\n"
        f"👤 {username} vừa gộp dữ liệu <b>{so_pgd} PGD</b>"
    )
    return gui_tin(text)


def gui_nhac_khoang_den_han(ds_khoang: list[dict]) -> bool:
    """Nhắc khoản vay đến hạn trong 7 ngày tới.

    Mỗi item: {"ten_kh": str, "so_ku": str, "ngay_dh": str, "du_no": str, "ten_pgd": str}
    """
    if not ds_khoang:
        return True
    lines = [f"⏰ <b>Khoản đến hạn trong 7 ngày ({len(ds_khoang)} khoản)</b>", ""]
    for k in ds_khoang[:20]:  # tối đa 20 dòng để tránh message quá dài
        lines.append(
            f"  • {k.get('ten_kh','')} — {k.get('so_ku','')} — "
            f"{k.get('ngay_dh','')} — {k.get('du_no','')} "
            f"({k.get('ten_pgd','')})"
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
    pgd_status = "✅" if so_pgd_da_upload >= tong_pgd else "⚠️"
    text = (
        f"📊 <b>Báo cáo sáng {ngay}</b>\n\n"
        f"💰 Tổng dư nợ: <b>{tong_du_no}</b>\n"
        f"🔴 Dư nợ quá hạn: <b>{tong_qh}</b> ({ty_le_qh})\n"
        f"{pgd_status} PGD đã upload: <b>{so_pgd_da_upload}/{tong_pgd}</b>"
    )
    return gui_tin(text)
