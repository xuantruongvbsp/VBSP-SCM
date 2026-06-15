#!/usr/bin/env python3
"""
nhac_deadline.py — Nhắc các PGD chưa nộp báo cáo + chưa hoàn thành nhập liệu qua Telegram.
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

import re

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


# ── Nhắc deadline nhập liệu (Theo dõi nhập liệu) ─────────────────────────────

_ROMAN_RE = re.compile(r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$')


def _la_pgd_header(stt: str) -> bool:
    if not isinstance(stt, str):
        stt = str(stt)
    return bool(_ROMAN_RE.match(stt.strip().upper()))

def _nhac_theo_doi_nhap_lieu() -> int:
    cfg_notify = db.doc_kv("telegram_notify_config") or {}
    if not cfg_notify.get("nhap_lieu", True):
        return 0
    ds_sheet = db.doc_kv("gsheet_theo_doi_nhap_list")
    if not ds_sheet or not isinstance(ds_sheet, list):
        return 0

    try:
        import gspread
        creds_path = str(_tim_credentials())
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        client = gspread.service_account(filename=creds_path, scopes=scope)
    except Exception as e:
        logger.error("_nhac_theo_doi_nhap_lieu: ket noi GSheet — %s", e)
        return 0

    from services.telegram_service import gui_tin

    today = date.today()
    sent_count = 0

    for i, cfg in enumerate(ds_sheet):
        deadline_str = cfg.get("deadline", "")
        if not deadline_str:
            continue
        try:
            dl_date = pd.to_datetime(deadline_str).date()
        except Exception:
            continue

        days_left = (dl_date - today).days
        if days_left > 3:
            continue

        ten_sheet = cfg.get("ten_hien_thi") or cfg.get("sheet_tab", f"Sheet {i+1}")
        sheet_id = cfg.get("sheet_id", "").strip()
        sheet_tab = cfg.get("sheet_tab", "")
        ds_ct = cfg.get("ds_chuong_trinh", [])
        if not sheet_id or not ds_ct:
            continue

        try:
            sheet = client.open_by_key(sheet_id).worksheet(sheet_tab)
            data = sheet.get_all_values()
            if len(data) <= 1:
                continue
        except Exception as e:
            logger.warning("Doc sheet '%s': %s", ten_sheet, e)
            continue

        loai = cfg.get("loai_cau_truc", "phan_cap_stt")
        header_row = cfg.get("header_row", 10)
        name_col = cfg.get("name_col", 2) - 1
        stt_col = cfg.get("stt_col", 1) - 1
        pgd_col = cfg.get("pgd_col", 1) - 1
        col_indices = [ct["col"] - 1 for ct in ds_ct]

        pgd_progress: dict[str, dict] = {}
        current_pgd = ""

        for row in data[header_row:]:
            if not any(str(c).strip() for c in row):
                continue
            if loai == "phang":
                pgd = str(row[name_col]).strip() if len(row) > name_col else ""
                if pgd:
                    current_pgd = pgd
                    pgd_progress.setdefault(current_pgd, {"total": 0, "filled": 0})
                    for ci in col_indices:
                        if ci < len(row):
                            pgd_progress[current_pgd]["total"] += 1
                            if str(row[ci]).strip():
                                pgd_progress[current_pgd]["filled"] += 1
            elif loai == "cot_pgd":
                pgd = str(row[pgd_col]).strip() if len(row) > pgd_col else ""
                if pgd:
                    current_pgd = pgd
                    pgd_progress.setdefault(current_pgd, {"total": 0, "filled": 0})
                    for ci in col_indices:
                        if ci < len(row):
                            pgd_progress[current_pgd]["total"] += 1
                            if str(row[ci]).strip():
                                pgd_progress[current_pgd]["filled"] += 1
            else:
                stt = str(row[stt_col]).strip() if len(row) > stt_col else ""
                name = str(row[name_col]).strip() if len(row) > name_col else ""
                if stt and _la_pgd_header(stt):
                    current_pgd = name
                elif current_pgd:
                    pgd_progress.setdefault(current_pgd, {"total": 0, "filled": 0})
                    for ci in col_indices:
                        if ci < len(row):
                            pgd_progress[current_pgd]["total"] += 1
                            if str(row[ci]).strip():
                                pgd_progress[current_pgd]["filled"] += 1

        chua_xong: list[str] = []
        for pgd, prog in sorted(pgd_progress.items()):
            if prog["total"] == 0:
                continue
            pct = prog["filled"] / prog["total"] * 100
            if pct < 100:
                chua_xong.append(
                    f"  • {pgd} — {prog['filled']}/{prog['total']} chỉ tiêu ({pct:.0f}%)"
                )

        if not chua_xong:
            logger.info("Nhap lieu '%s': tat ca da hoan thanh", ten_sheet)
            continue

        icon = "🔴" if days_left < 0 else "🟡" if days_left <= 2 else "🟠"
        dl_hien = dl_date.strftime("%d/%m/%Y")
        lines = [
            f"{icon} <b>Nhắc nhập liệu: {ten_sheet}</b>",
            f"📅 Hạn chót: <b>{dl_hien}</b>",
            "",
            f"<b>{len(chua_xong)} PGD chưa hoàn thành:</b>",
        ]
        for line in chua_xong[:15]:
            lines.append(line)
        if len(chua_xong) > 15:
            lines.append(f"  … và {len(chua_xong) - 15} PGD khác")

        ok = gui_tin("\n".join(lines))
        if ok:
            logger.info("Da gui nhac nhap lieu '%s': %d PGD", ten_sheet, len(chua_xong))
            sent_count += 1

    return sent_count


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
                        # Đã nộp (dù trễ) → không nhắc nữa
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

    _nhac_theo_doi_nhap_lieu()


if __name__ == "__main__":
    nhac()
