"""Gửi thông báo Telegram 1 chiều cho VBSP-SCM (push notification)."""
from __future__ import annotations

import html as _html
import json
import os
import re
import time
from datetime import datetime

import requests

import db
from logger import get_logger

logger = get_logger(__name__)

_DEFAULT_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_DEFAULT_CHAT_ID = "-5339155216"
_API_TIMEOUT     = 10  # giây

# Metadata dùng để chuẩn hóa cấu trúc mọi tin gửi theo notify_key.
_NOTIFY_PRESENTATION = {
    "bao_cao_sang":      ("Báo cáo tổng hợp sáng", "Toàn Chi nhánh", "HSTD"),
    "khoang_den_han":    ("Nhắc khoản đến hạn", "Toàn Chi nhánh", "HSTD"),
    "phan_ky_nxh":       ("Nhắc phân kỳ nhà ở xã hội", "Theo PGD", "File phân kỳ NXH/Tiền gửi"),
    "khtd_tien_do":     ("Tiến độ KHTD", "Toàn Chi nhánh", "HSTD/KHTD"),
    "qh_moi":            ("Cảnh báo NQH tăng", "Toàn Chi nhánh", "HSTD/Snapshot"),
    "rui_ro_tin_dung":   ("Cảnh báo rủi ro tín dụng", "Toàn Chi nhánh", "HSTD/Snapshot"),
    "deadline_bc":       ("Nhắc nộp báo cáo", "Toàn Chi nhánh", "Google Sheets"),
    "nhap_lieu":         ("Nhắc nhập liệu", "Toàn Chi nhánh", "Google Sheets"),
    "health_check":      ("Kết quả Health Check", "Hệ thống VBSP-SCM", "Health Check"),
    "merge_thanh_cong": ("Merge dữ liệu thành công", "Toàn Chi nhánh", "Hệ thống merge"),
    "upload_pgd":        ("PGD upload dữ liệu", "Theo PGD", "File upload"),
    "he_thong":          ("Cảnh báo hệ thống", "Hệ thống VBSP-SCM", "Hệ thống"),
    "nop_moi_gsheet":   ("PGD nộp báo cáo mới", "Toàn Chi nhánh", "Google Sheets"),
    "den_han_phan_tang": ("Nhắc đến hạn T-7/T-3/T-1", "Toàn Chi nhánh", "HSTD"),
    "lich_cong_tac":     ("Lịch công tác", "Phòng KH-NV", "Kế hoạch công tác"),
    "giai_ngan_tuan":   ("Báo cáo giải ngân tuần", "Toàn Chi nhánh", "HSTD"),
    "khoanh_tang":       ("Cảnh báo nợ khoanh tăng", "Toàn Chi nhánh", "HSTD/Snapshot"),
    "nqh_tuan":          ("Báo cáo NQH tuần", "Toàn Chi nhánh", "HSTD/Baseline"),
    "khtd_ct":           ("KHTD theo chương trình", "Toàn Chi nhánh", "HSTD/KHTD"),
    "tong_ket_thang":   ("Tổng kết tháng", "Toàn Chi nhánh", "HSTD/KHTD"),
}

_NOTIFY_GROUP_BY_KEY = {
    "bao_cao_sang": "bao_cao_dinh_ky",
    "khtd_tien_do": "bao_cao_dinh_ky",
    "giai_ngan_tuan": "bao_cao_dinh_ky",
    "nqh_tuan": "bao_cao_dinh_ky",
    "khtd_ct": "bao_cao_dinh_ky",
    "tong_ket_thang": "bao_cao_dinh_ky",
    "khoang_den_han": "nhac_nghiep_vu",
    "phan_ky_nxh": "nhac_nghiep_vu",
    "deadline_bc": "nhac_nghiep_vu",
    "nhap_lieu": "nhac_nghiep_vu",
    "nop_moi_gsheet": "nhac_nghiep_vu",
    "den_han_phan_tang": "nhac_nghiep_vu",
    "lich_cong_tac": "nhac_nghiep_vu",
    "qh_moi": "canh_bao_rui_ro",
    "khoanh_tang": "canh_bao_rui_ro",
    "rui_ro_tin_dung": "canh_bao_rui_ro",
    "upload_pgd": "su_kien_he_thong",
    "merge_thanh_cong": "su_kien_he_thong",
    "health_check": "su_kien_he_thong",
    "he_thong": "su_kien_he_thong",
}


def _bo_the_html(value: str) -> str:
    """Rút text thuần từ một dòng HTML ngắn để dùng làm tóm tắt."""
    return _html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def _dinh_dang_ngay_so_lieu(value: object) -> str:
    """Chuẩn hóa ngày về DD/MM/YYYY; trả chuỗi gốc nếu không parse được."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if match:
        day, month, year = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if match:
        year, month, day = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return raw


def _lay_ngay_so_lieu_thong_bao(notify_key: str, text: str, nguon: str) -> str:
    """Lấy ngày nghiệp vụ; nguồn HSTD ưu tiên metadata merge thay vì ngày gửi."""
    if notify_key == "phan_ky_nxh":
        ngay_trong_tin = _dinh_dang_ngay_so_lieu(text)
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", ngay_trong_tin):
            return ngay_trong_tin

    if "HSTD" in nguon:
        try:
            meta = db.doc_kv("merge_meta_hstd") or {}
            ngay_meta = _dinh_dang_ngay_so_lieu(meta.get("ngay_sl"))
            if ngay_meta:
                return ngay_meta
        except Exception as e:
            logger.error("lay ngay so lieu Telegram (%s): %s", notify_key, e, exc_info=True)

    # Các tin Health Check/lịch công tác thường đã mang ngày nghiệp vụ trong nội dung.
    if notify_key not in {"deadline_bc", "nhap_lieu"}:
        ngay_trong_tin = _dinh_dang_ngay_so_lieu(text)
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", ngay_trong_tin):
            return ngay_trong_tin

    # GSheet và sự kiện hệ thống phản ánh trạng thái tại lần quét hiện tại.
    return datetime.now().strftime("%d/%m/%Y")


def _chuan_hoa_thong_bao(text: str, notify_key: str) -> str:
    """Bọc tin nghiệp vụ theo một khung thống nhất, idempotent."""
    if notify_key not in _NOTIFY_PRESENTATION or "<b>Ngày số liệu:</b>" in text:
        return text

    tieu_de, pham_vi, nguon = _NOTIFY_PRESENTATION[notify_key]
    raw_lines = text.splitlines()
    first_index = next((i for i, line in enumerate(raw_lines) if line.strip()), None)
    if first_index is None:
        tom_tat = "Không có nội dung tóm tắt"
        chi_tiet = "—"
    else:
        tom_tat = _bo_the_html(raw_lines[first_index]) or tieu_de
        detail_lines = raw_lines[first_index + 1:]
        while detail_lines and not detail_lines[0].strip():
            detail_lines.pop(0)
        chi_tiet = "\n".join(detail_lines).strip() or "—"

    ngay_so_lieu = _lay_ngay_so_lieu_thong_bao(notify_key, text, nguon)
    cap_nhat_luc = datetime.now().strftime("%H:%M %d/%m/%Y")
    return (
        f"📌 <b>{_html.escape(tieu_de)} — {_html.escape(pham_vi)}</b>\n"
        f"📅 <b>Ngày số liệu:</b> {_html.escape(ngay_so_lieu or '—')}\n"
        f"🧾 <b>Tóm tắt:</b> {_html.escape(tom_tat)}\n"
        f"🔎 <b>Chi tiết / top cảnh báo:</b>\n{chi_tiet}\n"
        f"🗂 <b>Nguồn dữ liệu:</b> {_html.escape(nguon)}\n"
        f"🕒 <b>Cập nhật lúc:</b> {cap_nhat_luc}"
    )


# ── Config ─────────────────────────────────────────────────────────────────────

def _get_config() -> tuple[str, str]:
    """Đọc token/chat_id từ kv_store, fallback về default."""
    cfg = db.doc_kv("telegram_config") or {}
    return (
        cfg.get("token",   _DEFAULT_TOKEN),
        cfg.get("chat_id", _DEFAULT_CHAT_ID),
    )


def luu_config(token: str, chat_id: str, username: str = "system") -> None:
    """Cập nhật token/chat_id — giữ nguyên extra_chats đã cấu hình."""
    cfg = db.doc_kv("telegram_config") or {}
    cfg["token"]   = token
    cfg["chat_id"] = chat_id
    db.ghi_kv("telegram_config", cfg, username)
    db.ghi_audit(username, "telegram_config", f"Cập nhật telegram config (chat_id={chat_id})")


def luu_extra_chat(notify_key: str, chat_id: str, username: str = "system") -> None:
    """Lưu hoặc xóa chat_id phụ cho 1 loại thông báo."""
    cfg   = db.doc_kv("telegram_config") or {}
    extra = cfg.get("extra_chats", {})
    if chat_id.strip():
        extra[notify_key] = chat_id.strip()
    else:
        extra.pop(notify_key, None)
    cfg["extra_chats"] = extra
    db.ghi_kv("telegram_config", cfg, username)
    db.ghi_audit(username, "telegram_extra_chat",
                 f"Chat ID phụ: {notify_key} = {chat_id.strip() or '(đã xóa)'}")


def luu_group_chat(group_key: str, chat_id: str, username: str = "system") -> None:
    """Lưu hoặc xóa chat_id cho cả một nhóm thông báo Telegram."""
    group_key = str(group_key or "").strip()
    if not group_key:
        raise ValueError("group_key Telegram không được trống")
    cfg = db.doc_kv("telegram_config") or {}
    group_chats = cfg.get("group_chats", {})
    if chat_id.strip():
        group_chats[group_key] = chat_id.strip()
    else:
        group_chats.pop(group_key, None)
    cfg["group_chats"] = group_chats
    db.ghi_kv("telegram_config", cfg, username)
    db.ghi_audit(username, "telegram_group_chat",
                 f"Chat ID nhóm: {group_key} = {chat_id.strip() or '(đã xóa)'}")


def _chat_id_theo_notify(cfg: dict, notify_key: str, main_chat: str) -> str:
    """Resolve Chat ID theo thứ tự: loại thông báo -> nhóm thông báo -> chat chính."""
    key = str(notify_key or "").strip()
    group_key = _NOTIFY_GROUP_BY_KEY.get(key, "")
    return (
        cfg.get("extra_chats", {}).get(key)
        or (cfg.get("group_chats", {}).get(group_key) if group_key else None)
        or main_chat
    )


def doc_deadline_bc_allowlist() -> list[str] | None:
    """Danh sách loại báo cáo được phép gửi nhắc deadline (None = tất cả).

    Tự động lọc stale entries (loại BC không còn trong deadline config).
    Ghi log cảnh báo để admin biết nếu có stale.
    """
    val = db.doc_kv("telegram_deadline_bc_allowlist")
    if not val:
        return None
    if not isinstance(val, list):
        return None
    ds_raw = [str(x) for x in val if str(x).strip()]
    if not ds_raw:
        return None

    # Lọc stale: loại BC không còn trong deadline config hiện tại
    try:
        from services.report_submission_service import doc_deadline_config
        ds_hop_le = {str(k).strip() for k in doc_deadline_config() if str(k).strip()}
    except Exception:
        ds_hop_le = set()

    ds_loc = [loai for loai in ds_raw if loai in ds_hop_le] if ds_hop_le else ds_raw
    stale_count = len(ds_raw) - len(ds_loc)
    if stale_count > 0:
        stale_items = [loai for loai in ds_raw if loai not in ds_hop_le]
        logger.warning(
            "doc_deadline_bc_allowlist: %d stale entries đã bị lọc — %s",
            stale_count,
            ", ".join(stale_items[:5]),
        )
        # Tự động lưu bản đã lọc để tránh stale tích lũy
        if ds_loc:
            db.ghi_kv("telegram_deadline_bc_allowlist", ds_loc, "system")
        else:
            db.ghi_kv("telegram_deadline_bc_allowlist", None, "system")
            return None
    return ds_loc


def luu_deadline_bc_allowlist(ds_loai: list[str] | None, username: str = "system") -> None:
    """Lưu allowlist loại báo cáo cho nhắc deadline (None/[] = gửi tất cả).

    Tự động lọc stale entries (loại BC không còn trong deadline config).
    """
    if ds_loai:
        ds = sorted({str(x).strip() for x in ds_loai if str(x).strip()})

        # Lọc stale trước khi lưu
        try:
            from services.report_submission_service import doc_deadline_config
            ds_hop_le = {str(k).strip() for k in doc_deadline_config() if str(k).strip()}
        except Exception:
            ds_hop_le = set()

        if ds_hop_le:
            ds_raw = ds
            ds = [loai for loai in ds_raw if loai in ds_hop_le]
            stale = len(ds_raw) - len(ds)
            if stale > 0:
                logger.warning(
                    "luu_deadline_bc_allowlist: %d stale entries đã bị lọc khi lưu",
                    stale,
                )

        if not ds:
            db.ghi_kv("telegram_deadline_bc_allowlist", None, username)
            db.ghi_audit(username, "telegram_deadline_bc_allowlist", "Allowlist rỗng sau lọc → ALL (None)")
            return

        db.ghi_kv("telegram_deadline_bc_allowlist", ds, username)
        db.ghi_audit(username, "telegram_deadline_bc_allowlist", f"Allowlist {len(ds)} loại báo cáo")
    else:
        db.ghi_kv("telegram_deadline_bc_allowlist", None, username)
        db.ghi_audit(username, "telegram_deadline_bc_allowlist", "Allowlist: ALL (None)")


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
        logger.error("_ghi_log: %s", e, exc_info=True)


def lay_loi_gui_gan_nhat(func: str) -> str:
    """Lấy lỗi gửi gần nhất theo func/log key."""
    try:
        log = db.doc_kv("telegram_send_log") or []
    except Exception as e:
        logger.error("lay_loi_gui_gan_nhat(%s): %s", func, e, exc_info=True)
        return ""
    for entry in log:
        if str(entry.get("func", "")) == func and not bool(entry.get("ok", False)):
            return str(entry.get("error", "") or "")
    return ""


def _rut_gon_loi_telegram(resp: requests.Response) -> str:
    """Rút gọn lỗi Telegram từ JSON/raw text để UI hiển thị dễ hiểu hơn."""
    try:
        data = resp.json()
        mo_ta = str(data.get("description") or "").strip()
        if mo_ta:
            return f"HTTP {resp.status_code}: {mo_ta}"
    except (ValueError, json.JSONDecodeError, AttributeError):
        pass
    text = (resp.text or "").strip()
    return f"HTTP {resp.status_code}: {text[:300]}"


def _gui_tin_core(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> tuple[bool, str]:
    """Core sender cho chat bất kỳ, trả về (ok, chi_tiet_loi)."""
    last_err = ""
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    for attempt in range(3):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=_API_TIMEOUT,
            )
            if r.ok:
                return True, ""
            last_err = _rut_gon_loi_telegram(r)
            logger.warning("telegram send attempt %d: %s", attempt + 1, last_err)
            break  # HTTP error → không retry (lỗi config/nội dung)
        except Exception as e:
            last_err = str(e)
            logger.error("telegram send attempt %d: %s", attempt + 1, e, exc_info=True)
            if attempt < 2:
                time.sleep(2)
    return False, last_err


# ── Core ───────────────────────────────────────────────────────────────────────

def gui_tin(text: str, parse_mode: str = "HTML") -> bool:
    """Gửi tin nhắn văn bản đến chat chính. Retry tối đa 2 lần khi lỗi mạng."""
    token, chat_id = _get_config()
    ok, last_err = _gui_tin_core(token, chat_id, text, parse_mode=parse_mode)
    if ok:
        _ghi_log("gui_tin", text, True)
        return True
    _ghi_log("gui_tin", text, False, last_err)
    return False


def gui_tin_chi_tiet(text: str, parse_mode: str = "HTML") -> tuple[bool, str]:
    """Gửi tin tới chat chính, trả về chi tiết lỗi để UI hiển thị."""
    token, chat_id = _get_config()
    ok, err = _gui_tin_core(token, chat_id, text, parse_mode=parse_mode)
    _ghi_log("gui_tin", text, ok, err)
    return ok, err


def gui_tin_chi_tiet_voi_config(
    token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    log_func: str | None = "gui_tin_test",
) -> tuple[bool, str]:
    """Gửi tin với token/chat_id truyền vào, không phụ thuộc config đã lưu."""
    token = (token or "").strip()
    chat_id = str(chat_id or "").strip()
    if not token:
        err = "Token Telegram đang trống."
        if log_func:
            _ghi_log(log_func, text, False, err)
        return False, err
    if not chat_id:
        err = "Chat ID Telegram đang trống."
        if log_func:
            _ghi_log(log_func, text, False, err)
        return False, err
    ok, err = _gui_tin_core(token, chat_id, text, parse_mode=parse_mode)
    if log_func:
        _ghi_log(log_func, text, ok, err)
    return ok, err


def gui_tin_theo_notify_chi_tiet(
    text: str,
    notify_key: str,
    parse_mode: str = "HTML",
) -> tuple[bool, str]:
    """Gửi tin theo notify_key, trả về chi tiết lỗi để caller xử lý."""
    if parse_mode == "HTML":
        text = _chuan_hoa_thong_bao(text, notify_key)
    token, main_chat = _get_config()
    cfg = db.doc_kv("telegram_config") or {}
    chat_id = _chat_id_theo_notify(cfg, notify_key, main_chat)
    ok, err = _gui_tin_core(token, chat_id, text, parse_mode=parse_mode)
    _ghi_log(notify_key, text, ok, err)
    return ok, err


def _gui_tin_for(text: str, notify_key: str, parse_mode: str = "HTML") -> bool:
    """Gửi tin nhắn đến chat_id phụ của notify_key nếu có, fallback chat chính."""
    ok, _err = gui_tin_theo_notify_chi_tiet(text, notify_key, parse_mode=parse_mode)
    return ok


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
    return _gui_tin_for(text, "deadline_bc")


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
    return _gui_tin_for("\n".join(parts), "health_check")


def gui_thong_bao_merge(loai: str, so_pgd: int, username: str) -> bool:
    """Thông báo sau khi merge dữ liệu toàn CN thành công."""
    if not _la_bat("merge_thanh_cong"):
        return True
    text = (
        f"✅ <b>Merge {_html.escape(loai.upper())} thành công</b>\n"
        f"👤 {_html.escape(username)} vừa gộp dữ liệu <b>{so_pgd} PGD</b>"
    )
    return _gui_tin_for(text, "merge_thanh_cong")


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
    return _gui_tin_for("\n".join(lines), "khoang_den_han")


def gui_nhac_phan_ky_nxh(
    ten_pgd: str,
    ds_khoan: list[dict],
    ngay_du_lieu: str = "",
) -> bool:
    """Gửi danh sách phân kỳ NXH cho 1 PGD, chia 2 nhóm đủ/không đủ số dư.
    Tự chia nhiều tin nếu dài (ngưỡng ~3300 ký tự/chunk, chừa chỗ cho khung chuẩn).

    Mỗi item: {"ten_kh", "so_ku", "ngay_dh", "du_no", "tong_tgk",
               "sdt", "ten_xa", "ten_to_truong", "ghi_chu"}
    """
    if not _la_bat("phan_ky_nxh"):
        return True
    if not ds_khoan:
        return True
    from datetime import date
    thang      = date.today().strftime("%m/%Y")
    ngay_ref   = ngay_du_lieu or date.today().strftime("%d/%m/%Y")
    tong_tien  = sum(float(k.get("du_no", 0) or 0) for k in ds_khoan)
    tong_tien_hien = f"{tong_tien / 1e6:,.0f}".replace(",", ".") + " triệu"

    # ── Chia 2 nhóm: đủ số dư (TK >= dư nợ + lãi tồn) vs không đủ ─────────────
    def _phai_tra(k: dict) -> float:
        return float(k.get("du_no", 0) or 0) + float(k.get("lai_ton", 0) or 0)

    du_so_du = [k for k in ds_khoan if float(k.get("tong_tgk", 0) or 0) >= _phai_tra(k)]
    khong_du  = [k for k in ds_khoan if float(k.get("tong_tgk", 0) or 0) < _phai_tra(k)]

    def _fmt_sdt(raw: str) -> str:
        """Chuẩn hoá SĐT → 10 chữ số bắt đầu 0, bọc thẻ tel: để nhấn gọi."""
        s = re.sub(r"[\s\-\.\(\)]", "", raw.strip())
        if s.startswith("+84"):
            s = "0" + s[3:]
        elif re.match(r"^84\d{9}$", s):
            s = "0" + s[2:]
        if not re.match(r"^0\d{9}$", s):
            return _html.escape(raw)       # không nhận dạng được → hiện nguyên
        return f'<a href="tel:{s}">{s}</a>'

    def _fmt_tr(v: float) -> str:
        """Triệu đồng, nguyên triệu, phân cách VN: 1.234 tr."""
        return f"{v / 1e6:,.0f}".replace(",", ".") + " tr"

    def _dong_kh(k: dict, show_tgk: bool = False) -> list[str]:
        """Một khách hàng = 2 dòng (nhóm đủ) hoặc 3 dòng (nhóm thiếu).

        Dòng 1: tên KH (đậm) + số khế ước — dễ quét mắt.
        Dòng 2: hạn trả · dư nợ · lãi tồn · TK.
        Dòng 3 (chỉ nhóm thiếu): số tiền còn thiếu (đậm) + SĐT.
        """
        ten_kh      = _html.escape(str(k.get("ten_kh", "")))
        so_ku       = _html.escape(str(k.get("so_ku", "")))
        ngay        = _html.escape(str(k.get("ngay_dh", "")))
        du_no_val   = float(k.get("du_no", 0) or 0)
        lai_ton_val = float(k.get("lai_ton", 0) or 0)
        sdt_raw     = str(k.get("sdt", "") or "")
        co_canh_bao = bool(str(k.get("ghi_chu", "")).strip())
        marker      = "⚠️" if co_canh_bao else "▪️"

        rows = [f"{marker} <b>{ten_kh}</b> · {so_ku}"]

        sdt_str  = _fmt_sdt(sdt_raw) if sdt_raw else ""
        chi_tiet = [f"Hạn {ngay}", f"Nợ {_fmt_tr(du_no_val)}"]
        if lai_ton_val > 0:
            chi_tiet.append(f"Lãi tồn {_fmt_tr(lai_ton_val)}")

        if show_tgk:
            tgk       = float(k.get("tong_tgk", 0) or 0)
            con_thieu = du_no_val + lai_ton_val - tgk
            chi_tiet.append(f"TK {_fmt_tr(tgk)}")
            rows.append("    ⏰ " + " · ".join(chi_tiet))
            dong_thieu = f"👉 Thiếu <b>{_fmt_tr(con_thieu)}</b> và lãi phát sinh tháng"
            if sdt_str:
                dong_thieu += f" · 📞 {sdt_str}"
            rows.append("    " + dong_thieu)
        else:
            if sdt_str:
                chi_tiet.append(f"📞 {sdt_str}")
            rows.append("    ⏰ " + " · ".join(chi_tiet))
        return rows

    # ── Đọc mapping xã → cán bộ ───────────────────────────────────────────────
    can_bo_map: dict[str, str] = {}
    try:
        can_bo_map = db.doc_kv("nxh_can_bo_xa") or {}
    except Exception as e:
        logger.error("doc nxh_can_bo_xa cho Telegram NXH: %s", e, exc_info=True)

    def _build_xa_groups(ds: list[dict], show_tgk: bool) -> list[str]:
        """Nhóm KH theo xã, mỗi nhóm có header tên xã + cán bộ phụ trách."""
        lines: list[str] = []
        # Giữ thứ tự xã theo ds (đã sort xã+ngày từ daily_report)
        seen: dict[str, list[dict]] = {}
        for k in ds:
            xa = str(k.get("ten_xa", "") or "")
            seen.setdefault(xa, []).append(k)
        for xa, items in seen.items():
            xa_hien_thi = xa or "Chưa rõ xã"
            can_bo = can_bo_map.get(xa, "")
            cb_str = f" · CB: <b>{_html.escape(can_bo)}</b>" if can_bo else ""
            lines.append(f"\n📍 <b>{_html.escape(xa_hien_thi)}</b>{cb_str} · {len(items)} khoản")
            for k in items:
                lines.extend(_dong_kh(k, show_tgk=show_tgk))
        return lines

    so_canh_bao = sum(1 for k in ds_khoan if str(k.get("ghi_chu", "")).strip())
    canh_bao_str = f" · ⚠️ <b>{so_canh_bao} cảnh báo</b>" if so_canh_bao else ""
    pgd_esc = _html.escape(ten_pgd)

    def _gui_nhom(loai_lines: list[str], loai_header: str) -> bool:
        """Gửi 1 nhóm (đủ hoặc không đủ) — tự chia chunk nếu dài."""
        # Chừa dung lượng cho khung chuẩn (ngày SL, nguồn, thời điểm cập nhật).
        _MAX = 3300
        chunks: list[list[str]] = []
        cur: list[str] = []
        cur_len = 0
        for line in loai_lines:
            need = len(line) + 1
            if cur_len + need > _MAX and cur:
                chunks.append(cur)
                cur, cur_len = [], 0
            cur.append(line)
            cur_len += need
        if cur:
            chunks.append(cur)

        n = len(chunks)
        result = True
        for i, chunk in enumerate(chunks):
            page_tag = f" ({i + 1}/{n})" if n > 1 else ""
            if i == 0:
                msg_header = (
                    f"🏠 <b>{pgd_esc} — Phân kỳ NXH tháng {thang}</b>{page_tag}\n"
                    f"📆 <b>Ngày dữ liệu NXH:</b> {_html.escape(str(ngay_ref))}\n"
                    f"📋 <b>{len(ds_khoan)} khoản</b> · 💰 <b>{tong_tien_hien}</b>"
                    f" · ✅ Đủ số dư: {len(du_so_du)} · ❌ Chưa đủ: {len(khong_du)}"
                    f"{canh_bao_str}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{loai_header}\n"
                )
            else:
                msg_header = (
                    f"🏠 <b>{pgd_esc} — Phân kỳ NXH tháng {thang}</b>"
                    f" — tiếp theo{page_tag}\n"
                    f"📆 <b>Ngày dữ liệu NXH:</b> {_html.escape(str(ngay_ref))}\n"
                )
            if not _gui_tin_for(msg_header + "\n".join(chunk), "phan_ky_nxh"):
                result = False
        return result

    # ── Tin 1: ĐỦ SỐ DƯ ──────────────────────────────────────────────────────
    ok = True
    if du_so_du:
        lines_du = _build_xa_groups(du_so_du, show_tgk=False)
        lines_du.append("\n<i>(*) Lãi phát sinh theo dư nợ</i>")
        if not _gui_nhom(lines_du, f"✅ <b>ĐỦ SỐ DƯ THANH TOÁN ({len(du_so_du)} khoản)</b>"):
            ok = False

    # ── Tin 2: CHƯA ĐỦ SỐ DƯ ────────────────────────────────────────────────
    if khong_du:
        lines_khong = _build_xa_groups(khong_du, show_tgk=True)
        lines_khong.append("\n<i>(*) Lãi phát sinh theo dư nợ</i>")
        loai_header_khong = (
            f"❌ <b>CHƯA ĐỦ SỐ DƯ ({len(khong_du)} khoản)</b>\n"
            f"<i>Tính đến ngày {_html.escape(ngay_ref)}, các khách hàng dưới đây"
            f" chưa đủ số dư trong tài khoản để thanh toán nợ:</i>"
        )
        if not _gui_nhom(lines_khong, loai_header_khong):
            ok = False

    return ok


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
    return _gui_tin_for(text, "bao_cao_sang")


def gui_thong_bao_upload_pgd(ten_pgd: str, loai: str, username: str) -> bool:
    """Thông báo khi PGD upload file thành công."""
    if not _la_bat("upload_pgd"):
        return True
    now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
    text = (
        f"📤 <b>{_html.escape(ten_pgd)}</b> vừa upload <b>{_html.escape(loai.upper())}</b>\n"
        f"👤 {_html.escape(username)}   ⏰ {now_str}"
    )
    return gui_tin_pgd(text, ten_pgd, notify_key="upload_pgd")


def gui_khtd_tien_do(ds_pgd: list[dict]) -> bool:
    """Gửi tóm tắt tiến độ KHTD.

    Mỗi item: {ten_pgd, ke_hoach, thuc_hien, pct}
    """
    if not _la_bat("khtd_tien_do"):
        return True
    if not ds_pgd:
        return True
    from datetime import date as _date
    lines = [f"📈 <b>Tiến độ KHTD — {_date.today().strftime('%d/%m/%Y')}</b>", ""]
    for p in ds_pgd:
        pct  = float(p.get("pct", 0))
        icon = "⚠️" if pct < 70 else "✅"
        kh   = float(p.get("ke_hoach", 0)) / 1e9
        th   = float(p.get("thuc_hien", 0)) / 1e9
        pct_str = f"{pct:.0f}".replace(".", ",")
        kh_str  = f"{kh:.1f}".replace(".", ",")
        th_str  = f"{th:.1f}".replace(".", ",")
        lines.append(
            f"{icon} {_html.escape(str(p.get('ten_pgd', '')))} — "
            f"{th_str}/{kh_str} tỷ ({pct_str}%)"
        )
    return _gui_tin_for("\n".join(lines), "khtd_tien_do")


def gui_canh_bao_qh_moi(ds_tang: list[dict]) -> bool:
    """Cảnh báo khi tỷ lệ NQH tăng bất thường.

    Mỗi item: {ten_pgd, ty_le_cu, ty_le_moi, tang}
    """
    if not _la_bat("qh_moi"):
        return True
    if not ds_tang:
        return True
    lines = [f"⚠️ <b>Nợ quá hạn tăng bất thường — {len(ds_tang)} đơn vị</b>", ""]
    for p in ds_tang:
        tang = float(p.get("tang", 0))
        cu   = float(p.get("ty_le_cu", 0))
        moi  = float(p.get("ty_le_moi", 0))
        lines.append(
            f"  🔴 {_html.escape(str(p.get('ten_pgd', '')))} — "
            f"{cu:.2f}% → {moi:.2f}% (+{tang:.2f}%)"
        )
    return _gui_tin_for("\n".join(lines), "qh_moi")


def gui_thong_bao_nop_moi_gsheet(ds_nop: list[dict]) -> bool:
    """Thông báo khi phát hiện submission mới từ Google Form (GSheet).

    Mỗi item: {ten_pgd, loai_bao_cao, thoi_gian, ho_ten}
    """
    if not _la_bat("nop_moi_gsheet"):
        return True
    if not ds_nop:
        return True
    now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
    lines = [f"📋 <b>Nhận báo cáo mới — {len(ds_nop)} nộp</b>   ⏰ {now_str}", ""]
    for item in ds_nop[:20]:
        pgd   = _html.escape(str(item.get("ten_pgd", "")))
        loai  = _html.escape(str(item.get("loai_bao_cao", "")))
        ts    = _html.escape(str(item.get("thoi_gian", "")))
        ho_ten = _html.escape(str(item.get("ho_ten", "") or ""))
        lines.append(f"  ✅ <b>{pgd}</b> — {loai} ({ts})")
        if ho_ten:
            lines.append(f"    <i>Người nộp: {ho_ten}</i>")
    if len(ds_nop) > 20:
        lines.append(f"  … và {len(ds_nop) - 20} nộp khác")
    return _gui_tin_for("\n".join(lines), "nop_moi_gsheet")


def _lay_moc_nqh_nam(ngay_sl: str) -> tuple[dict[str, float], str]:
    """Đọc NQH từng PGD tại baseline 31/12 của năm trước."""
    try:
        from config import COT_DU_NO_QH, COT_TEN_PGD
        from data.hstd import doc_baseline_merged, ts_baseline_merged

        ngay_chuan = _dinh_dang_ngay_so_lieu(ngay_sl)
        match = re.fullmatch(r"\d{2}/(\d{2})/(\d{4})", ngay_chuan)
        nam_hien_tai = int(match.group(2)) if match else datetime.now().year
        nam_moc = nam_hien_tai - 1
        if nam_moc <= 0:
            return {}, ""

        df_moc = doc_baseline_merged(nam_moc, ts=ts_baseline_merged(nam_moc))
        if df_moc is None or df_moc.empty:
            return {}, ""

        nqh_moc: dict[str, float] = {}
        for row in df_moc.to_dict("records"):
            ten_pgd = str(row.get(COT_TEN_PGD, "") or "").strip()
            if not ten_pgd:
                continue
            nqh_moc[ten_pgd] = nqh_moc.get(ten_pgd, 0.0) + float(row.get(COT_DU_NO_QH, 0) or 0)

        return nqh_moc, f"31/12/{nam_moc}"
    except Exception as e:
        logger.error("_lay_moc_nqh_nam: %s", e, exc_info=True)
        return {}, ""


def gui_bao_cao_nqh_tuan(ds_pgd: list[dict], ngay_sl: str = "") -> bool:
    """Báo cáo NQH tuần — từng đơn vị, top 3 và biến động so baseline 31/12 năm trước.

    Mỗi item: {ten_pgd, du_no, nqh, ty_le_nqh}
    """
    if not _la_bat("nqh_tuan"):
        return True
    if not ds_pgd:
        return True
    from datetime import date as _d
    today = _d.today()
    ngay_ref = ngay_sl or today.strftime("%d/%m/%Y")
    tong_dn = sum(float(p.get("du_no", 0) or 0) for p in ds_pgd)
    tong_qh = sum(float(p.get("nqh", 0) or 0) for p in ds_pgd)
    tl_cn = tong_qh / tong_dn * 100 if tong_dn else 0.0

    def _icon(tl: float) -> str:
        if tl >= 3:
            return "🔴"
        if tl >= 1:
            return "🟡"
        if tl > 0:
            return "🟠"
        return "🟢"

    def _fmt_so_vn(value: float, decimals: int = 0) -> str:
        raw = f"{value:,.{decimals}f}"
        return raw.replace(",", "_").replace(".", ",").replace("_", ".")

    def _fmt(vnd: float, decimals: int = 0) -> str:
        return _fmt_so_vn(vnd / 1e6, decimals) + " tr"

    def _fmt_delta(vnd: float) -> str:
        decimals = 1 if 0 < abs(vnd) < 1_000_000 else 0
        if vnd > 0:
            return f"🔺 +{_fmt(vnd, decimals)}"
        if vnd < 0:
            return f"🔻 -{_fmt(abs(vnd), decimals)}"
        return "➖ 0 tr"

    nqh_moc, ngay_moc = _lay_moc_nqh_nam(ngay_ref)
    ten_pgd_hien_tai = [str(p.get("ten_pgd", "") or "").strip() for p in ds_pgd]
    du_moc_tong = bool(nqh_moc) and all(ten in nqh_moc for ten in ten_pgd_hien_tai)
    tong_qh_moc = sum(nqh_moc[ten] for ten in ten_pgd_hien_tai) if du_moc_tong else 0.0
    tl_cn_s = f"{tl_cn:.2f}".replace(".", ",")

    lines = [
        f"📊 <b>Báo cáo NQH tuần</b>   📅 {_html.escape(ngay_ref)}",
        "",
        f"💰 Tổng dư nợ CN: <b>{_fmt_so_vn(tong_dn / 1e9, 1)} tỷ</b>",
        f"🔴 Tổng NQH: <b>{_fmt(tong_qh)}</b>  ({tl_cn_s}%)",
    ]
    if du_moc_tong and ngay_moc:
        lines.append(
            f"📈 Tăng/giảm trong kỳ: <b>{_fmt_delta(tong_qh - tong_qh_moc)}</b> "
            f"so mốc {_html.escape(ngay_moc)}"
        )
    elif ngay_moc:
        lines.append(f"ℹ️ Chưa đủ dữ liệu PGD để tính tổng so mốc {_html.escape(ngay_moc)}")
    else:
        lines.append("ℹ️ Chưa có baseline 31/12 năm trước để tính tăng/giảm")
    lines.extend(["", "<b>Từng đơn vị:</b>"])

    ds_sorted = sorted(ds_pgd, key=lambda p: float(p.get("ty_le_nqh", 0) or 0), reverse=True)
    for p in ds_sorted:
        ten_pgd = str(p.get("ten_pgd", "") or "").strip()
        pgd = _html.escape(ten_pgd)
        nqh = float(p.get("nqh", 0) or 0)
        tl  = float(p.get("ty_le_nqh", 0) or 0)
        delta_s = f" · {_fmt_delta(nqh - nqh_moc[ten_pgd])}" if ten_pgd in nqh_moc else ""
        if nqh == 0:
            lines.append(f"  {_icon(0)} {pgd}: —{delta_s}")
        else:
            tl_s = f"{tl:.2f}%".replace(".", ",")
            lines.append(f"  {_icon(tl)} {pgd}: {_fmt(nqh)} ({tl_s}){delta_s}")

    # Top 3 nếu nhiều PGD
    top3 = [p for p in ds_sorted if float(p.get("nqh", 0) or 0) > 0][:3]
    if top3:
        lines.append("")
        lines.append("⚠️ <b>Cần chú ý:</b>")
        for i, p in enumerate(top3, 1):
            pgd = _html.escape(str(p.get("ten_pgd", "")))
            tl  = float(p.get("ty_le_nqh", 0) or 0)
            tl_s = f"{tl:.2f}%".replace(".", ",")
            lines.append(f"  {i}. {pgd} — {tl_s}")

    return _gui_tin_for("\n".join(lines), "nqh_tuan")


def gui_khtd_theo_chuong_trinh(ds_ct: list[dict], ngay: str = "") -> bool:
    """Báo cáo tiến độ KHTD phân tích theo từng chương trình tín dụng.

    Mỗi item: {ten_ct, nguon_von, ke_hoach, thuc_hien, pct}
    nguon_von: 'TW' | 'ĐP'
    """
    if not _la_bat("khtd_ct"):
        return True
    if not ds_ct:
        return True
    from datetime import date as _d
    ngay_ref = ngay or _d.today().strftime("%d/%m/%Y")

    def _icon(pct: float) -> str:
        if pct >= 100:
            return "✅"
        if pct >= 80:
            return "🟡"
        return "🔴"

    def _fty(vnd: float) -> str:
        return f"{vnd / 1e9:,.1f}".replace(",", ".") + " tỷ"

    tong_kh = sum(float(c.get("ke_hoach", 0) or 0) for c in ds_ct)
    tong_th = sum(float(c.get("thuc_hien", 0) or 0) for c in ds_ct)
    pct_cn  = tong_th / tong_kh * 100 if tong_kh > 0 else 0.0

    lines = [f"🎯 <b>KHTD theo Chương trình</b>   📅 {_html.escape(ngay_ref)}", ""]

    for nv_label in ("TW", "ĐP"):
        nhom = [c for c in ds_ct if c.get("nguon_von") == nv_label]
        if not nhom:
            continue
        header = "NGUỒN VỐN TRUNG ƯƠNG" if nv_label == "TW" else "NGUỒN VỐN ĐỊA PHƯƠNG"
        lines.append(f"<b>{header}</b>")
        for c in nhom:
            ten  = _html.escape(str(c.get("ten_ct", "")))
            kh   = float(c.get("ke_hoach", 0) or 0)
            th   = float(c.get("thuc_hien", 0) or 0)
            pct  = float(c.get("pct", 0) or 0)
            if kh == 0 and th == 0:
                continue
            pct_s = f"{pct:.1f}%".replace(".", ",")
            if kh > 0:
                lines.append(f"  {_icon(pct)} {ten}: {_fty(th)}/{_fty(kh)} ({pct_s})")
            else:
                lines.append(f"  ℹ️ {ten}: {_fty(th)} (KH chưa giao)")
        lines.append("")

    pct_cn_s = f"{pct_cn:.1f}%".replace(".", ",")
    lines.append(f"🏆 <b>Tổng CN: {_fty(tong_th)}/{_fty(tong_kh)} ({pct_cn_s})</b>")
    return _gui_tin_for("\n".join(lines), "khtd_ct")


def gui_tong_ket_thang(
    thang: int,
    nam: int,
    du_no: float,
    ke_hoach: float,
    nqh: float,
    so_khoang_den_han: int,
    du_no_den_han: float,
    ds_pgd_top: list[dict],
    ds_pgd_bot: list[dict],
) -> bool:
    """Tổng kết tháng — gửi ngày 25–31 hàng tháng.

    ds_pgd_top/bot: [{ten_pgd, pct_kh}] — top hoàn thành / cần cải thiện
    """
    if not _la_bat("tong_ket_thang"):
        return True
    pct_kh = du_no / ke_hoach * 100 if ke_hoach > 0 else 0.0
    tl_nqh = nqh / du_no * 100 if du_no > 0 else 0.0

    def _fty(vnd: float) -> str:
        return f"{vnd / 1e9:,.1f}".replace(",", ".") + " tỷ"

    def _fmt_m(vnd: float) -> str:
        return f"{vnd / 1e6:,.0f}".replace(",", ".") + " triệu"

    icon_kh = "✅" if pct_kh >= 100 else "🟡" if pct_kh >= 80 else "🔴"
    icon_nqh = "🔴" if tl_nqh >= 3 else "🟡" if tl_nqh >= 1 else "🟢"

    pct_kh_s  = f"{pct_kh:.1f}%".replace(".", ",")
    tl_nqh_s  = f"{tl_nqh:.2f}%".replace(".", ",")

    lines = [
        f"📅 <b>Tổng kết tháng {thang:02d}/{nam}</b>",
        "",
        f"{icon_kh} Dư nợ: <b>{_fty(du_no)}</b>  |  KH: {_fty(ke_hoach)}  |  Đạt <b>{pct_kh_s}</b>",
        f"{icon_nqh} NQH: <b>{_fmt_m(nqh)}</b>  ({tl_nqh_s})",
    ]
    if so_khoang_den_han > 0:
        lines.append(
            f"⏰ Đến hạn tháng sau: <b>{so_khoang_den_han}</b> khoản "
            f"({_fty(du_no_den_han)})"
        )

    if ds_pgd_top:
        lines.append("")
        lines.append("🏆 <b>Hoàn thành KH tốt nhất:</b>")
        for p in ds_pgd_top[:5]:
            pgd = _html.escape(str(p.get("ten_pgd", "")))
            pct = float(p.get("pct_kh", 0) or 0)
            pct_s = f"{pct:.1f}%".replace(".", ",")
            lines.append(f"  ✅ {pgd} — {pct_s}")

    if ds_pgd_bot:
        lines.append("")
        lines.append("⚠️ <b>Cần cải thiện:</b>")
        for p in ds_pgd_bot[:5]:
            pgd = _html.escape(str(p.get("ten_pgd", "")))
            pct = float(p.get("pct_kh", 0) or 0)
            pct_s = f"{pct:.1f}%".replace(".", ",")
            lines.append(f"  🔴 {pgd} — {pct_s}")

    return _gui_tin_for("\n".join(lines), "tong_ket_thang")


def luu_pgd_chat(ten_pgd: str, chat_id: str, username: str = "system") -> None:
    """Lưu hoặc xóa chat_id riêng cho từng PGD."""
    from data.pgd import pgd_slug
    slug = pgd_slug(ten_pgd)
    cfg  = db.doc_kv("telegram_config") or {}
    pgd_chats = cfg.get("pgd_chats", {})
    if chat_id.strip():
        pgd_chats[slug] = chat_id.strip()
    else:
        pgd_chats.pop(slug, None)
    cfg["pgd_chats"] = pgd_chats
    db.ghi_kv("telegram_config", cfg, username)
    db.ghi_audit(username, "telegram_pgd_chat",
                 f"Chat ID PGD: {ten_pgd} ({slug}) = {chat_id.strip() or '(đã xóa)'}")


def gui_tin_pgd(text: str, ten_pgd: str, notify_key: str = "", parse_mode: str = "HTML") -> bool:
    """Gửi tin đến chat PGD → chat loại TB → chat nhóm TB → chat chính."""
    from data.pgd import pgd_slug
    if notify_key and parse_mode == "HTML":
        text = _chuan_hoa_thong_bao(text, notify_key)
    token, main_chat = _get_config()
    cfg  = db.doc_kv("telegram_config") or {}
    slug = pgd_slug(ten_pgd)
    chat_id = cfg.get("pgd_chats", {}).get(slug) or _chat_id_theo_notify(cfg, notify_key, main_chat)
    ok, last_err = _gui_tin_core(token, chat_id, text, parse_mode=parse_mode)
    if ok:
        _ghi_log(notify_key or f"pgd:{slug}", text, True)
        return True
    _ghi_log(notify_key or f"pgd:{slug}", text, False, last_err)
    return False


def gui_nhac_den_han_phan_tang(buckets: dict[str, list[dict]]) -> bool:
    """Nhắc khoản đến hạn phân tầng T-1 / T-3 / T-7.

    buckets = {"T-1": [...], "T-3": [...], "T-7": [...]}
    Mỗi item: {ten_kh, so_ku, ngay_dh, du_no (VND), ten_pgd}
    """
    if not _la_bat("den_han_phan_tang"):
        return True
    if not any(v for v in buckets.values()):
        return True

    tiers = [
        ("T-1", "🔴", "Đến hạn NGÀY MAI"),
        ("T-3", "🟠", "Đến hạn trong 3 ngày"),
        ("T-7", "🟡", "Đến hạn trong 7 ngày"),
    ]
    lines = ["⏰ <b>Nhắc khoản đến hạn sắp tới</b>", ""]
    any_tier = False
    for tier_key, icon, label in tiers:
        ds = buckets.get(tier_key, [])
        if not ds:
            continue
        any_tier = True
        tong_vnd = sum(float(k.get("du_no", 0) or 0) for k in ds)
        tong_s   = f"{tong_vnd / 1e6:,.0f}".replace(",", ".") + " triệu"
        lines.append(f"{icon} <b>{label} ({len(ds)} khoản — {tong_s}):</b>")
        for k in ds[:10]:
            kh   = _html.escape(str(k.get("ten_kh", "")))
            pgd  = _html.escape(str(k.get("ten_pgd", "")))
            ngay = _html.escape(str(k.get("ngay_dh", "")))
            dn_s = f"{float(k.get('du_no', 0) or 0) / 1e6:,.0f}".replace(",", ".") + " tr"
            lines.append(f"  • {kh} ({pgd}) — {ngay} — {dn_s}")
        if len(ds) > 10:
            lines.append(f"  … và {len(ds) - 10} khoản khác")
        lines.append("")
    if not any_tier:
        return True
    return _gui_tin_for("\n".join(lines), "den_han_phan_tang")


def gui_nhac_lich_cong_tac(ds_su_kien: list[dict], ngay_mai: str) -> bool:
    """Nhắc lịch công tác Phòng KH-NV ngày mai (gửi chiều hôm trước).

    Mỗi item: {gio, noi_dung, nguoi_phu_trach, dia_diem}
    """
    if not _la_bat("lich_cong_tac"):
        return True
    if not ds_su_kien:
        return True
    lines = [f"📅 <b>Lịch công tác ngày mai — {_html.escape(ngay_mai)}</b>", ""]
    for sv in ds_su_kien:
        gio = _html.escape(str(sv.get("gio", "") or "")).strip()
        nd  = _html.escape(str(sv.get("noi_dung", "") or "")).strip()
        pt  = _html.escape(str(sv.get("nguoi_phu_trach", "") or "")).strip()
        dd  = _html.escape(str(sv.get("dia_diem", "") or "")).strip()
        line = f"  🕒 <b>{gio}</b>  {nd}" if gio else f"  📌 {nd}"
        if pt:
            line += f"  · {pt}"
        if dd:
            line += f"  📍 {dd}"
        lines.append(line)
    return _gui_tin_for("\n".join(lines), "lich_cong_tac")


def gui_giai_ngan_tuan(ds_pgd: list[dict], tuan_str: str = "") -> bool:
    """Báo cáo giải ngân (khoản vay mới) 7 ngày qua theo PGD.

    Mỗi item: {ten_pgd, so_khoan, giai_ngan (VND)}
    """
    if not _la_bat("giai_ngan_tuan"):
        return True
    ds_pgd = [p for p in ds_pgd if float(p.get("giai_ngan", 0) or 0) > 0]
    if not ds_pgd:
        return True
    tong_vnd = sum(float(p.get("giai_ngan", 0) or 0) for p in ds_pgd)
    tong_n   = sum(int(p.get("so_khoan", 0) or 0) for p in ds_pgd)
    tong_s   = f"{tong_vnd / 1e9:,.2f}".replace(",", ".") + " tỷ"
    lines = [
        f"💸 <b>Giải ngân tuần {_html.escape(tuan_str)}</b>",
        f"📊 Tổng: <b>{tong_s}</b>  ({tong_n} khoản mới)",
        "",
    ]
    for p in sorted(ds_pgd, key=lambda x: float(x.get("giai_ngan", 0) or 0), reverse=True):
        pgd = _html.escape(str(p.get("ten_pgd", "")))
        gn  = float(p.get("giai_ngan", 0) or 0)
        n   = int(p.get("so_khoan", 0) or 0)
        gn_s = f"{gn / 1e6:,.0f}".replace(",", ".") + " tr"
        lines.append(f"  • {pgd}: {gn_s} ({n} khoản)")
    return _gui_tin_for("\n".join(lines), "giai_ngan_tuan")


def gui_canh_bao_khoanh_tang(ds_tang: list[dict]) -> bool:
    """Cảnh báo đơn vị có nợ khoanh tăng bất thường (≥ 5% so kỳ trước).

    Mỗi item: {ten_pgd, khoanh_cu (VND), khoanh_moi (VND), tang_pct}
    """
    if not _la_bat("khoanh_tang"):
        return True
    if not ds_tang:
        return True
    lines = [f"⚠️ <b>Cảnh báo nợ khoanh tăng</b>  ({len(ds_tang)} đơn vị)", ""]
    for p in sorted(ds_tang, key=lambda x: float(x.get("tang_pct", 0) or 0), reverse=True):
        pgd   = _html.escape(str(p.get("ten_pgd", "")))
        cu    = float(p.get("khoanh_cu", 0) or 0)
        moi   = float(p.get("khoanh_moi", 0) or 0)
        tang  = float(p.get("tang_pct", 0) or 0)
        cu_s  = f"{cu / 1e6:,.0f}".replace(",", ".") + " tr"
        moi_s = f"{moi / 1e6:,.0f}".replace(",", ".") + " tr"
        tang_s = f"+{tang:.1f}%".replace(".", ",")
        lines.append(f"  🔴 {pgd}: {cu_s} → {moi_s} ({tang_s})")
    return _gui_tin_for("\n".join(lines), "khoanh_tang")


def gui_canh_bao_tong_hop_rui_ro(
    ds_qh: list[dict],
    ds_khoanh: list[dict],
    ngay_moc: str = "",
) -> bool:
    """Gộp cảnh báo NQH tăng + nợ khoanh tăng vào 1 tin, hiển thị rõ mốc baseline.

    ds_qh:     [{ten_pgd, ty_le_cu, ty_le_moi, tang}]
    ds_khoanh: [{ten_pgd, khoanh_cu, khoanh_moi, tang_pct}]
    ngay_moc:  "31/12/2025"
    """
    if not _la_bat("rui_ro_tin_dung"):
        return True
    has_qh      = bool(ds_qh)
    has_khoanh  = bool(ds_khoanh)
    if not has_qh and not has_khoanh:
        return True

    moc_str = f" — so với mốc {_html.escape(ngay_moc)}" if ngay_moc else ""
    lines = [f"⚠️ <b>Cảnh báo rủi ro tín dụng{moc_str}</b>", ""]

    # ── Phần 1: Nợ quá hạn tăng ──────────────────────────────────────────
    if has_qh:
        lines.append(f"🔴 <b>NỢ QUÁ HẠN TĂNG ({len(ds_qh)} đơn vị):</b>")
        for p in ds_qh:
            tang = float(p.get("tang", 0))
            cu   = float(p.get("ty_le_cu", 0))
            moi  = float(p.get("ty_le_moi", 0))
            cu_s  = f"{cu:.2f}%".replace(".", ",")
            moi_s = f"{moi:.2f}%".replace(".", ",")
            tang_s = f"+{tang:.2f}%".replace(".", ",")
            lines.append(
                f"  🔴 {_html.escape(str(p.get('ten_pgd', '')))} — "
                f"{cu_s} → {moi_s} ({tang_s})"
            )
        lines.append("")

    # ── Phần 2: Nợ khoanh tăng ──────────────────────────────────────────
    if has_khoanh:
        lines.append(f"⚠️ <b>NỢ KHOANH TĂNG ({len(ds_khoanh)} đơn vị):</b>")
        for p in sorted(ds_khoanh, key=lambda x: float(x.get("tang_pct", 0) or 0), reverse=True):
            pgd   = _html.escape(str(p.get("ten_pgd", "")))
            cu    = float(p.get("khoanh_cu", 0) or 0)
            moi   = float(p.get("khoanh_moi", 0) or 0)
            tang  = float(p.get("tang_pct", 0) or 0)
            cu_s  = f"{cu / 1e6:,.0f}".replace(",", ".") + " tr"
            moi_s = f"{moi / 1e6:,.0f}".replace(",", ".") + " tr"
            tang_s = f"+{tang:.1f}%".replace(".", ",")
            lines.append(f"  🔴 {pgd}: {cu_s} → {moi_s} ({tang_s})")

    return _gui_tin_for("\n".join(lines), "rui_ro_tin_dung")


def gui_canh_bao_he_thong(loai: str, mo_ta: str) -> bool:
    """Cảnh báo sự kiện hệ thống (đăng nhập bất thường, lỗi...).

    loai: 'login' | 'loi' | 'canh_bao'
    """
    if not _la_bat("he_thong"):
        return True
    icon_map = {"login": "🔐", "loi": "❌", "canh_bao": "⚠️"}
    icon    = icon_map.get(loai, "ℹ️")
    now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
    text = (
        f"{icon} <b>Cảnh báo hệ thống</b>\n"
        f"⏰ {now_str}\n\n"
        f"{_html.escape(mo_ta)}"
    )
    return _gui_tin_for(text, "he_thong")
