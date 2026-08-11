#!/usr/bin/env python3
"""
nhac_deadline.py — Nhắc các PGD chưa nộp báo cáo + chưa hoàn thành nhập liệu qua Telegram.
Chạy độc lập: python scripts/nhac_deadline.py
Có thể gọi từ Task Scheduler: chạy 7h sáng mỗi ngày.
"""
from __future__ import annotations

import os
import sys
import html
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import re

import pandas as pd

import db
from config import DS_PGD, DON_VI_CHI_NHANH
from logger import get_logger
from services.report_submission_service import (
    DS_PGD_ALL,
    COT,
    SHEET_ID,
    _tim_credentials,
    chuan_hoa_ten_pgd,
    doc_du_lieu_gsheet,
    doc_deadline_config,
    doc_manual_log,
    lay_danh_sach_can_nhac,
)
from data.phan_ky_nxh import (
    COL_NXH_NGAY,
    COL_NXH_TIEN,
    COL_NXH_TGK,
    COL_NXH_LAI,
    COL_NXH_PGD,
    lay_ngay_du_lieu_phan_ky_nxh,
)
from services.telegram_delta import diff_deadline, diff_due_loans, diff_progress

logger = get_logger(__name__)


# ── Nhắc deadline nhập liệu (Theo dõi nhập liệu) ─────────────────────────────

_ROMAN_RE = re.compile(r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$')


def _la_pgd_header(stt: str) -> bool:
    if not isinstance(stt, str):
        stt = str(stt)
    return bool(_ROMAN_RE.match(stt.strip().upper()))

def run_nhap_lieu(
    baseline_snapshot: dict | None = None,
) -> tuple[int, int, str, dict]:
    """Gửi nhắc nhập liệu đầy đủ hoặc phần thay đổi so với baseline đầu ngày."""
    cfg_notify = db.doc_kv("telegram_notify_config") or {}
    if not cfg_notify.get("nhap_lieu", True):
        return 0, 0, "", {}
    ds_sheet = db.doc_kv("gsheet_theo_doi_nhap_list")
    if not ds_sheet or not isinstance(ds_sheet, list):
        return 0, 0, "", {}

    try:
        import gspread
        creds_path = str(_tim_credentials())
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        client = gspread.service_account(filename=creds_path, scopes=scope)
    except Exception as e:
        logger.error("_nhac_theo_doi_nhap_lieu: ket noi GSheet — %s", e)
        return 0, 0, str(e), {}

    from services.telegram_service import gui_tin_theo_notify_chi_tiet

    today = date.today()
    sent_count = 0
    pending_count = 0
    first_err = ""
    snapshot: dict[str, dict] = {}

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

        progress_snapshot = {
            str(pgd): {"filled": int(prog["filled"]), "total": int(prog["total"])}
            for pgd, prog in sorted(pgd_progress.items())
            if prog["total"] > 0
        }
        dl_hien = dl_date.strftime("%d/%m/%Y")
        snapshot[str(ten_sheet)] = {
            "deadline": dl_hien,
            "progress": progress_snapshot,
        }

        if baseline_snapshot is not None:
            old_progress = (
                baseline_snapshot.get(str(ten_sheet), {}).get("progress", {})
                if isinstance(baseline_snapshot, dict) else {}
            )
            changed: list[str] = []
            for change in diff_progress(old_progress, progress_snapshot):
                pgd = change["pgd"]
                old = change["old"]
                new = change["new"]
                old_text = f"{old.get('filled', 0)}/{old.get('total', 0)}"
                new_text = f"{new.get('filled', 0)}/{new.get('total', 0)}"
                icon = "✅" if new.get("total", 0) and new.get("filled", 0) >= new.get("total", 0) else "🔄"
                changed.append(f"  {icon} {pgd}: {old_text} → {new_text}")
            if not changed:
                continue
            pending_count += 1
            lines = [
                f"🔄 <b>Cập nhật nhập liệu: {ten_sheet}</b>",
                "So với bản đầu tiên trong ngày:",
                "",
                *changed[:20],
            ]
            if len(changed) > 20:
                lines.append(f"  … và {len(changed) - 20} PGD khác")
        else:
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

            pending_count += 1
            icon = "🔴" if days_left < 0 else "🟡" if days_left <= 2 else "🟠"
            lines = [
                f"{icon} <b>Nhắc nhập liệu: {ten_sheet}</b>",
                f"📅 Hạn chót: <b>{dl_hien}</b>",
                "",
                f"<b>{len(chua_xong)} PGD chưa hoàn thành:</b>",
                *chua_xong[:15],
            ]
            if len(chua_xong) > 15:
                lines.append(f"  … và {len(chua_xong) - 15} PGD khác")

        ok, err = gui_tin_theo_notify_chi_tiet("\n".join(lines), "nhap_lieu")
        if ok:
            logger.info("Da gui nhac nhap lieu '%s'", ten_sheet)
            sent_count += 1
        else:
            logger.error("Nhac nhap lieu '%s' that bai: %s", ten_sheet, err)
            if not first_err:
                first_err = err

    return sent_count, pending_count, first_err, snapshot


def _nhac_theo_doi_nhap_lieu() -> tuple[int, int, str]:
    """Wrapper tương thích ngược cho task nhắc deadline cũ."""
    sent, pending, error, _snapshot = run_nhap_lieu()
    return sent, pending, error


# ── Phát hiện submission mới từ GSheet ───────────────────────────────────────

def _thong_bao_nop_moi_gsheet() -> int:
    """Phát hiện submission mới từ GSheet kể từ lần chạy trước, gửi Telegram.

    Lưu timestamp lần kiểm tra vào kv_store key 'tg_last_gsheet_check_ts'.
    Lần đầu chạy: chỉ lưu timestamp, không gửi (tránh spam toàn bộ lịch sử).
    """
    from services.telegram_service import gui_thong_bao_nop_moi_gsheet

    try:
        df = doc_du_lieu_gsheet()
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

def run_den_han_phan_tang_with_snapshot(
    baseline_snapshot: dict | None = None,
) -> tuple[bool, int, int, str, dict]:
    """Gửi nhắc đến hạn đầy đủ hoặc thay đổi, kèm snapshot đầu ngày."""
    from services.telegram_service import (
        gui_nhac_den_han_phan_tang,
        gui_tin_theo_notify_chi_tiet,
    )
    cfg_notify = db.doc_kv("telegram_notify_config") or {}
    if not cfg_notify.get("den_han_phan_tang", True):
        return True, 0, 0, "", {}
    try:
        from pathlib import Path
        from config import (
            CACHE_HSTD, COT_NGAY_DH, COT_TONG_DU_NO,
            COT_TEN_KH, COT_SO_KU, COT_TEN_PGD,
        )
        if not Path(CACHE_HSTD).exists():
            return False, 0, 0, f"Chưa có dữ liệu HSTD: {CACHE_HSTD}", {}
        df = pd.read_parquet(CACHE_HSTD)
        if COT_NGAY_DH not in df.columns:
            return False, 0, 0, f"Thiếu cột {COT_NGAY_DH}.", {}
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
        snapshot = {}
        for tier, items in buckets.items():
            for item in items:
                item_id = "|".join([
                    tier,
                    item["ten_pgd"],
                    item["so_ku"] or item["ten_kh"],
                    item["ngay_dh"],
                ])
                snapshot[item_id] = {**item, "tier": tier}

        if baseline_snapshot is not None:
            added_ids, removed_ids, changed_ids = diff_due_loans(baseline_snapshot, snapshot)
            if not added_ids and not removed_ids and not changed_ids:
                return True, 0, 0, "", snapshot
            lines = [
                "🔄 <b>Cập nhật khoản đến hạn</b>",
                "So với bản đầu tiên trong ngày:",
                "",
            ]
            for item_id in added_ids[:15]:
                item = snapshot[item_id]
                lines.append(
                    f"  ⚠️ Mới: {html.escape(item['ten_kh'])} "
                    f"({html.escape(item['ten_pgd'])}) — {item['tier']}"
                )
            for item_id in removed_ids[:15]:
                item = baseline_snapshot[item_id]
                lines.append(
                    f"  ✅ Không còn: {html.escape(str(item.get('ten_kh', '')))} "
                    f"({html.escape(str(item.get('ten_pgd', '')))}) — {item.get('tier', '')}"
                )
            for item_id in changed_ids[:15]:
                item = snapshot[item_id]
                lines.append(
                    f"  🔄 Cập nhật: {html.escape(item['ten_kh'])} "
                    f"({html.escape(item['ten_pgd'])}) — {item['tier']}"
                )
            hidden = sum(max(len(items) - 15, 0) for items in (added_ids, removed_ids, changed_ids))
            if hidden > 0:
                lines.append(f"  … và {hidden} thay đổi khác")
            ok, err = gui_tin_theo_notify_chi_tiet(
                "\n".join(lines),
                "den_han_phan_tang",
            )
            total_changes = len(added_ids) + len(removed_ids) + len(changed_ids)
            return ok, 1 if ok else 0, total_changes, err, snapshot

        if not any(v for v in buckets.values()):
            return True, 0, 0, "", snapshot
        total = sum(len(v) for v in buckets.values())
        ok = gui_nhac_den_han_phan_tang(buckets)
        if ok:
            return True, 1, total, "", snapshot
        from services.telegram_service import lay_loi_gui_gan_nhat
        return False, 0, total, lay_loi_gui_gan_nhat("den_han_phan_tang"), snapshot
    except Exception as e:
        logger.error("run_den_han_phan_tang: %s", e, exc_info=True)
        return False, 0, 0, str(e), {}


def run_den_han_phan_tang() -> tuple[bool, int, int, str]:
    """Wrapper tương thích ngược, gửi bản đến hạn đầy đủ."""
    ok, sent, total, error, _snapshot = run_den_han_phan_tang_with_snapshot()
    return ok, sent, total, error


def _nhac_den_han_phan_tang() -> int:
    """Wrapper tương thích ngược, trả số tin đã gửi."""
    _ok, sent, _total, _error = run_den_han_phan_tang()
    return sent


# ── Nhắc phân kỳ NXH ─────────────────────────────────────────────────────────

def _nhac_phan_ky_nxh() -> int:
    """Gửi danh sách phân kỳ NXH toàn tháng vào ngày 1–3 đầu tháng (1 lần/tháng).

    - Chỉ chạy khi today là ngày 1, 2, hoặc 3 (backup nếu ngày 1 lỡ).
    - Dùng kv_store key 'nxh_nhac_thang_da_gui' để chống gửi trùng trong tháng.
    - Lấy toàn bộ khoản đến hạn trong tháng (ngày 1 → cuối tháng).
    """
    from services.telegram_service import gui_nhac_phan_ky_nxh, _la_bat
    if not _la_bat("phan_ky_nxh"):
        return 0

    today = date.today()
    if today.day > 3:
        return 0

    # Chống gửi trùng trong cùng tháng
    ky_thang = today.strftime("%Y-%m")
    da_gui = db.doc_kv("nxh_nhac_thang_da_gui")
    if da_gui == ky_thang:
        logger.info("_nhac_phan_ky_nxh: tháng %s đã gửi, bỏ qua", ky_thang)
        return 0

    try:
        from data.phan_ky_nxh import doc_phan_ky_nxh
        df = doc_phan_ky_nxh()
        if df.empty:
            logger.warning("_nhac_phan_ky_nxh: chưa có dữ liệu parquet NXH")
            return 0

        if COL_NXH_NGAY not in df.columns or COL_NXH_PGD not in df.columns:
            logger.warning("_nhac_phan_ky_nxh: thiếu cột %s hoặc %s", COL_NXH_NGAY, COL_NXH_PGD)
            return 0

        # Toàn bộ khoản trong tháng hiện tại (ngày 1 → cuối tháng)
        today_ts  = pd.Timestamp(today).normalize()
        first_day = today_ts.replace(day=1)
        last_day  = first_day + pd.offsets.MonthEnd(0)
        ngay_du_lieu = lay_ngay_du_lieu_phan_ky_nxh(first_day.strftime("%d/%m/%Y"))

        mask = (
            df[COL_NXH_NGAY].notna()
            & (df[COL_NXH_NGAY] >= first_day)
            & (df[COL_NXH_NGAY] <= last_day)
        )
        df_thang = df[mask].sort_values(["Tên xã", COL_NXH_NGAY])
        if df_thang.empty:
            logger.info(
                "_nhac_phan_ky_nxh: không có khoản nào tháng %s — đánh dấu đã gửi", ky_thang
            )
            db.ghi_kv("nxh_nhac_thang_da_gui", ky_thang, "system")
            return 0

        sent = 0
        for ten_pgd, grp in df_thang.groupby(COL_NXH_PGD):
            ds = []
            for _, row in grp.iterrows():
                ngay_dh = ""
                try:
                    if pd.notna(row[COL_NXH_NGAY]):
                        ngay_dh = pd.Timestamp(row[COL_NXH_NGAY]).strftime("%d/%m/%Y")
                except Exception:
                    pass
                ds.append({
                    "ten_kh":        str(row.get("Tên khách hàng") or ""),
                    "so_ku":         str(row.get("Số khế ước") or ""),
                    "ngay_dh":       ngay_dh,
                    "du_no":         float(row.get(COL_NXH_TIEN) or 0),
                    "lai_ton":       float(row.get(COL_NXH_LAI) or 0) if COL_NXH_LAI in grp.columns else 0.0,
                    "tong_tgk":      float(row.get(COL_NXH_TGK) or 0) if COL_NXH_TGK in grp.columns else 0.0,
                    "sdt":           str(row.get("Số điện thoại") or ""),
                    "ten_xa":        str(row.get("Tên xã") or ""),
                    "ten_to_truong": str(row.get("Tên tổ trưởng") or ""),
                    "ghi_chu":       str(row.get("Ghi chú") or ""),
                })
            ok = gui_nhac_phan_ky_nxh(str(ten_pgd), ds, ngay_du_lieu=ngay_du_lieu)
            if ok:
                sent += 1

        # Đánh dấu đã gửi tháng này
        db.ghi_kv("nxh_nhac_thang_da_gui", ky_thang, "system")
        logger.info(
            "_nhac_phan_ky_nxh: tháng %s — đã gửi %d/%d PGD, %d khoản",
            ky_thang, sent, df_thang[COL_NXH_PGD].nunique(), len(df_thang),
        )
        return sent
    except Exception as e:
        logger.error("_nhac_phan_ky_nxh: %s", e, exc_info=True)
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
        tomorrow = date.today() + timedelta(days=1)
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


def run_deadline_bc_with_snapshot(
    baseline_snapshot: dict | None = None,
) -> tuple[int, int, int, str, dict]:
    """Gửi deadline đầy đủ hoặc thay đổi, kèm snapshot để scheduler lưu mốc."""
    from services.telegram_service import gui_canh_bao_deadline
    from services.telegram_service import (
        doc_deadline_bc_allowlist,
        gui_tin_theo_notify_chi_tiet,
        lay_loi_gui_gan_nhat,
    )

    allowlist_set = doc_deadline_bc_allowlist()
    ds_can_nhac = lay_danh_sach_can_nhac(allowlist=allowlist_set)
    snapshot = {
        str(item["loai"]): {
            "deadline": item["deadline_date"].strftime("%d/%m/%Y"),
            "missing": sorted(str(pgd) for pgd in item["ds_chua_nop"]),
        }
        for item in ds_can_nhac
    }
    sent_count = 0
    failed_count = 0
    first_error = ""

    if baseline_snapshot is not None:
        lines = ["🔄 <b>Cập nhật nộp báo cáo</b>", "So với bản đầu tiên trong ngày:", ""]
        changed_count = 0
        for change in diff_deadline(baseline_snapshot, snapshot):
            loai = change["name"]
            da_nop = change["submitted"]
            moi_thieu = change["new_missing"]
            changed_count += 1
            lines.append(f"<b>{html.escape(loai)}</b>")
            if da_nop:
                lines.append(f"  ✅ Đã nộp thêm: {html.escape(', '.join(da_nop))}")
            if moi_thieu:
                lines.append(f"  ⚠️ Mới phát sinh chưa nộp: {html.escape(', '.join(moi_thieu))}")
        if changed_count == 0:
            return 0, 0, 0, "", snapshot
        ok, err = gui_tin_theo_notify_chi_tiet("\n".join(lines), "deadline_bc")
        if ok:
            return 1, changed_count, 0, "", snapshot
        return 0, changed_count, 1, err, snapshot

    for item in ds_can_nhac:
        loai = item["loai"]
        dl_hien = item["deadline_date"].strftime("%d/%m/%Y")
        chua_nop = item["ds_chua_nop"]
        ok = gui_canh_bao_deadline(loai, dl_hien, chua_nop)
        if ok:
            logger.info("Đã gửi nhắc '%s': %d PGD chưa nộp", loai, len(chua_nop))
            sent_count += 1
        else:
            failed_count += 1
            if not first_error:
                first_error = lay_loi_gui_gan_nhat("deadline_bc")
            logger.error("Gửi nhắc '%s' thất bại: %s", loai, first_error)
    return sent_count, len(ds_can_nhac), failed_count, first_error, snapshot


def run_deadline_bc() -> tuple[int, int, int, str]:
    """Wrapper tương thích ngược, gửi bản deadline đầy đủ."""
    sent, pending, failed, error, _snapshot = run_deadline_bc_with_snapshot()
    return sent, pending, failed, error

def nhac() -> None:
    """Duyệt deadline, tìm PGD chưa nộp, gửi Telegram."""
    from services.telegram_schedule_service import is_scheduler_managed

    if not is_scheduler_managed("deadline_bc"):
        sent_count, pending_count, _failed, _error = run_deadline_bc()
        if pending_count == 0:
            logger.info("Không có deadline nào cần nhắc hôm nay.")
        else:
            logger.info("Hoàn tất deadline: đã gửi %d/%d nhắc nhở.", sent_count, pending_count)
    else:
        logger.info("deadline_bc do Telegram scheduler quản lý; legacy task bỏ qua.")

    if not is_scheduler_managed("nhap_lieu"):
        _nhac_theo_doi_nhap_lieu()
    else:
        logger.info("nhap_lieu do Telegram scheduler quản lý; legacy task bỏ qua.")
    _thong_bao_nop_moi_gsheet()

    # Nhắc phân kỳ NXH — khoản đến hạn tháng này
    _nhac_phan_ky_nxh()

    # Nhắc khoản đến hạn phân tầng T-7/T-3/T-1
    if not is_scheduler_managed("den_han_phan_tang"):
        _nhac_den_han_phan_tang()
    else:
        logger.info("den_han_phan_tang do Telegram scheduler quản lý; legacy task bỏ qua.")

    # Nhắc lịch công tác ngày mai (chỉ chạy buổi chiều — lúc 14:00)
    if datetime.now().hour >= 13:
        _nhac_lich_cong_tac()


if __name__ == "__main__":
    nhac()
