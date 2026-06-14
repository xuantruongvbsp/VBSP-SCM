#!/usr/bin/env python3
"""
nhac_deadline.py — Nhắc các PGD chưa nộp báo cáo trước deadline qua Telegram.
Chạy độc lập: python scripts/nhac_deadline.py
Có thể gọi từ Task Scheduler: chạy 7h sáng mỗi ngày.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd

import db
from config import DS_PGD, DON_VI_CHI_NHANH
from logger import get_logger

logger = get_logger(__name__)

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

# ── Kết nối Google Sheets ─────────────────────────────────────────────────────

SHEET_ID = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
SHEET_TAB = "TIENDO_BAOCAO"
COT = ["thoi_gian", "email", "ten_pgd", "loai_bao_cao",
       "ky_bao_cao", "noi_dung", "file_dinh_kem", "ho_ten"]


def _tim_credentials() -> Path:
    candidates = [
        BASE_DIR / "credentials.json",
        BASE_DIR.parent / "credentials.json",
        Path.cwd() / "credentials.json",
        Path("credentials.json"),
    ]
    for cand in candidates:
        if cand.exists():
            return cand.resolve()
    raise FileNotFoundError(f"Không tìm thấy credentials.json. Đã thử: {[str(c) for c in candidates]}")


def _chuan_hoa_ten_pgd(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return raw
    s = raw.strip()
    for prefix in ("Phòng giao dịch ", "Phong giao dich ", "PGD ", "pgd "):
        if s.lower().startswith(prefix.lower()):
            return "PGD " + s[len(prefix):].strip()
    return s


def _doc_du_lieu() -> pd.DataFrame:
    try:
        import gspread
    except ImportError:
        logger.error("Thiếu thư viện gspread. Cài: pip install gspread google-auth")
        return pd.DataFrame(columns=COT)

    try:
        creds_path = str(_tim_credentials())
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        client = gspread.service_account(filename=creds_path, scopes=scope)
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        data = sheet.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame(columns=COT)
        df = pd.DataFrame([r[:len(COT)] for r in data[1:]], columns=COT)
        df["ten_pgd"] = df["ten_pgd"].apply(_chuan_hoa_ten_pgd)
        df["thoi_gian"] = pd.to_datetime(df["thoi_gian"], dayfirst=True, errors="coerce")
        return df
    except Exception as e:
        logger.error("_doc_du_lieu GSheet: %s", e, exc_info=True)
        return pd.DataFrame(columns=COT)


# ── Deadline logic ────────────────────────────────────────────────────────────

def _doc_deadline_config() -> dict[str, str]:
    """Đọc cấu hình deadline: {loai_bao_cao: 'YYYY-MM-DD'}."""
    raw = db.doc_kv("bao_cao_deadline_config") or {}
    normalized: dict[str, str] = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            vals = [v for v in val.values() if isinstance(v, str)]
            if vals:
                normalized[key] = vals[0]
        elif isinstance(val, str):
            normalized[key] = val
    return normalized


def _doc_manual_log() -> dict:
    """Đọc danh sách đánh dấu thủ công: {(pgd, loai): entry_dict}."""
    raw = db.doc_kv("manual_nop_tdn")
    if not isinstance(raw, list):
        return {}
    result = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        pgd = entry.get("pgd")
        loai = entry.get("loai")
        if pgd and loai:
            result[(pgd, loai)] = entry
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def nhac() -> None:
    """Duyệt deadline, tìm PGD chưa nộp, gửi Telegram."""
    deadline_cfg = _doc_deadline_config()
    if not deadline_cfg:
        logger.info("Không có deadline nào được cài đặt, bỏ qua.")
        return

    df = _doc_du_lieu()
    if df.empty:
        logger.warning("Không lấy được dữ liệu từ Google Sheets, bỏ qua.")
        return

    manual_map = _doc_manual_log()
    today = date.today()

    from services.telegram_service import gui_canh_bao_deadline

    sent_count = 0
    for loai, deadline_str in sorted(deadline_cfg.items()):
        # Parse deadline date
        try:
            dl_date = pd.to_datetime(deadline_str).date()
        except Exception:
            logger.warning("Bỏ qua deadline '%s': không parse được ngày '%s'", loai, deadline_str)
            continue

        # Chỉ nhắc nếu deadline đã qua hoặc trong 3 ngày tới
        days_left = (dl_date - today).days
        if days_left > 3:
            continue

        dl_hien = dl_date.strftime("%d/%m/%Y")

        # Tìm PGD chưa nộp
        chua_nop: list[str] = []
        for pgd in DS_PGD_ALL:
            # Kiểm tra manual override (ghi đè thủ công)
            manual_entry = manual_map.get((pgd, loai))
            if manual_entry and manual_entry.get("ghi_de", False):
                ngay = pd.to_datetime(manual_entry.get("ngay_nop"))
                try:
                    nop_date = ngay.date() if hasattr(ngay, "date") else pd.to_datetime(ngay).date()
                    if nop_date <= dl_date:
                        continue  # Đã nộp đúng hạn qua manual
                except Exception:
                    pass

            # Kiểm tra GSheet
            match = df[(df["ten_pgd"] == pgd) & (df["loai_bao_cao"] == loai)]
            if match.empty:
                chua_nop.append(pgd)
            else:
                last = match.sort_values("thoi_gian").iloc[-1]
                ngay_nop = last["thoi_gian"]
                if ngay_nop is None or (hasattr(ngay_nop, "__class__") and pd.isna(ngay_nop)):
                    chua_nop.append(pgd)
                else:
                    try:
                        nop_date = ngay_nop.date() if hasattr(ngay_nop, "date") else pd.to_datetime(ngay_nop).date()
                        if nop_date > dl_date:
                            chua_nop.append(pgd)
                    except Exception:
                        chua_nop.append(pgd)

        if not chua_nop:
            logger.info("Loại '%s' (deadline %s): tất cả đã nộp", loai, dl_hien)
            continue

        # Gửi Telegram
        label = f"{loai} (hạn {dl_hien})"
        ok = gui_canh_bao_deadline(loai, dl_hien, chua_nop)
        if ok:
            logger.info("Đã gửi nhắc '%s': %d PGD chưa nộp", loai, len(chua_nop))
            sent_count += 1
        else:
            logger.error("Gửi nhắc '%s' thất bại", loai)

    if sent_count == 0:
        logger.info("Không có deadline nào cần nhắc hôm nay.")
    else:
        logger.info("Hoàn tất: đã gửi %d nhắc nhở.", sent_count)


if __name__ == "__main__":
    nhac()
