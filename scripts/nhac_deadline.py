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


# ── Phát hiện submission mới từ GSheet ───────────────────────────────────────

def _thong_bao_nop_moi_gsheet() -> int:
    """Phát hiện submission mới từ GSheet kể từ lần chạy trước, gửi Telegram.

    Lưu timestamp lần kiểm tra vào kv_store key 'tg_last_gsheet_check_ts'.
    Lần đầu chạy: chỉ lưu timestamp, không gửi (tránh spam toàn bộ lịch sử).
    """
    from services.telegram_service import gui_thong_bao_nop_moi_gsheet

    try:
        df = _doc_du_lieu()
        now = datetime.now()

        if df.empty:
            db.ghi_kv("tg_last_gsheet_check_ts", now.isoformat(), "system")
            return 0

        last_ts_str = db.doc_kv("tg_last_gsheet_check_ts")
        db.ghi_kv("tg_last_gsheet_check_ts", now.isoformat(), "system")

        if not last_ts_str:
            logger.info("_thong_bao_nop_moi_gsheet: lần đầu chạy — chỉ lưu timestamp")
            return 0

        try:
            last_ts = pd.to_datetime(last_ts_str)
        except Exception:
            return 0

        df_moi = df[df["thoi_gian"] > last_ts].copy()
        if df_moi.empty:
            return 0

        ds = []
        for _, r in df_moi.iterrows():
            ts_str = ""
            try:
                if pd.notna(r.get("thoi_gian")):
                    ts_str = pd.Timestamp(r["thoi_gian"]).strftime("%d/%m %H:%M")
            except Exception:
                pass
            ds.append({
                "ten_pgd":      str(r.get("ten_pgd", "") or ""),
                "loai_bao_cao": str(r.get("loai_bao_cao", "") or ""),
                "thoi_gian":    ts_str,
                "ho_ten":       str(r.get("ho_ten", "") or ""),
            })

        ok = gui_thong_bao_nop_moi_gsheet(ds)
        if ok:
            logger.info("_thong_bao_nop_moi_gsheet: đã gửi %d submission mới", len(ds))
        return len(ds) if ok else 0
    except Exception as e:
        logger.error("_thong_bao_nop_moi_gsheet: %s", e, exc_info=True)
        return 0


# ── Nhắc đến hạn phân tầng T-7 / T-3 / T-1 ──────────────────────────────────

def _nhac_den_han_phan_tang() -> int:
    """Tìm khoản đến hạn trong 1/3/7 ngày tới, gửi cảnh báo phân tầng."""
    from services.telegram_service import gui_nhac_den_han_phan_tang
    cfg_notify = db.doc_kv("telegram_notify_config") or {}
    if not cfg_notify.get("den_han_phan_tang", True):
        return 0
    try:
        from pathlib import Path
        from config import (
            CACHE_HSTD, COT_NGAY_DH, COT_TONG_DU_NO,
            COT_TEN_KH, COT_SO_KU, COT_TEN_PGD,
        )
        if not Path(CACHE_HSTD).exists():
            return 0
        df = pd.read_parquet(CACHE_HSTD)
        if COT_NGAY_DH not in df.columns:
            return 0
        today_ts = pd.Timestamp.today().normalize()
        buckets: dict[str, list[dict]] = {"T-1": [], "T-3": [], "T-7": []}
        tier_map = {1: "T-1", 3: "T-3", 7: "T-7"}
        for days in (1, 3, 7):
            target = today_ts + pd.Timedelta(days=days)
            mask = df[COT_NGAY_DH].notna() & (df[COT_NGAY_DH].dt.normalize() == target)
            for _, r in df[mask].iterrows():
                buckets[tier_map[days]].append({
                    "ten_kh":  str(r.get(COT_TEN_KH, "") or ""),
                    "so_ku":   str(r.get(COT_SO_KU, "") or ""),
                    "ngay_dh": target.strftime("%d/%m/%Y"),
                    "du_no":   float(r.get(COT_TONG_DU_NO, 0) or 0),
                    "ten_pgd": str(r.get(COT_TEN_PGD, "") or ""),
                })
        if not any(v for v in buckets.values()):
            return 0
        ok = gui_nhac_den_han_phan_tang(buckets)
        return 1 if ok else 0
    except Exception as e:
        logger.error("_nhac_den_han_phan_tang: %s", e, exc_info=True)
        return 0


# ── Nhắc lịch công tác ngày mai ───────────────────────────────────────────────

def _nhac_lich_cong_tac() -> int:
    """Đọc khnv_lich_list, tìm sự kiện ngày mai, gửi nhắc Telegram."""
    from services.telegram_service import gui_nhac_lich_cong_tac
    cfg_notify = db.doc_kv("telegram_notify_config") or {}
    if not cfg_notify.get("lich_cong_tac", True):
        return 0
    try:
        ds_lich = db.doc_kv("khnv_lich_list")
        if not ds_lich or not isinstance(ds_lich, list):
            return 0
        tomorrow = (date.today() + __import__("datetime").timedelta(days=1))
        ngay_mai_str = tomorrow.strftime("%d/%m/%Y")
        tomorrow_dt  = pd.Timestamp(tomorrow)
        ds_sv = []
        for entry in ds_lich:
            if not isinstance(entry, dict):
                continue
            ngay_raw = entry.get("ngay") or entry.get("date") or ""
            try:
                ngay_entry = pd.to_datetime(ngay_raw, dayfirst=True).normalize()
            except Exception:
                continue
            if ngay_entry != tomorrow_dt:
                continue
            ds_sv.append({
                "gio":              str(entry.get("gio", "") or entry.get("time", "") or ""),
                "noi_dung":         str(entry.get("noi_dung", "") or entry.get("content", "") or ""),
                "nguoi_phu_trach":  str(entry.get("nguoi_phu_trach", "") or entry.get("assignee", "") or ""),
                "dia_diem":         str(entry.get("dia_diem", "") or entry.get("location", "") or ""),
            })
        if not ds_sv:
            return 0
        # Sắp xếp theo giờ
        ds_sv.sort(key=lambda x: x["gio"] or "99:99")
        ok = gui_nhac_lich_cong_tac(ds_sv, ngay_mai_str)
        return 1 if ok else 0
    except Exception as e:
        logger.error("_nhac_lich_cong_tac: %s", e, exc_info=True)
        return 0


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
    _thong_bao_nop_moi_gsheet()

    # Nhắc khoản đến hạn phân tầng T-7/T-3/T-1
    try:
        _nhac_den_han_phan_tang()
    except Exception as e:
        logger.error("_nhac_den_han_phan_tang: %s", e)

    # Nhắc lịch công tác ngày mai (chỉ chạy buổi chiều — lúc 14:00)
    if datetime.now().hour >= 13:
        try:
            _nhac_lich_cong_tac()
        except Exception as e:
            logger.error("_nhac_lich_cong_tac: %s", e)


if __name__ == "__main__":
    nhac()
