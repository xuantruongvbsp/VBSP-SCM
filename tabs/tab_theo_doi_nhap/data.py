"""Đọc dữ liệu Google Sheet, phân nhóm PGD, tính toán tiến độ nhập liệu."""
from __future__ import annotations

from datetime import date as _date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from logger import get_logger

from .constants import (
    KV_LIST_KEY,
    KV_LEGACY_KEY,
    KV_SNAPSHOT_PREFIX,
    DEFAULT_CT,
    CACHE_TTL,
)

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def tim_credentials() -> Path:
    candidates = [
        PROJECT_ROOT / "credentials.json",
        PROJECT_ROOT.parent / "credentials.json",
        Path.cwd() / "credentials.json",
        Path("credentials.json"),
    ]
    from config import BASE_DIR as _bd
    candidates.append(_bd / "credentials.json")
    for cand in candidates:
        if cand.exists():
            return cand.resolve()
    raise FileNotFoundError(
        f"Không tìm thấy credentials.json. Đã thử: {[str(c) for c in candidates]}"
    )


def ket_noi_gsheet():
    _p = tim_credentials()
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        import gspread
        return gspread.service_account(filename=str(_p), scopes=scope)
    except Exception as e:
        logger.error("ket_noi_gsheet: %s", e, exc_info=True)
        try:
            from oauth2client.service_account import ServiceAccountCredentials
            import gspread
            creds = ServiceAccountCredentials.from_json_keyfile_name(str(_p), scope)
            return gspread.authorize(creds)
        except ImportError:
            raise RuntimeError("Không thể kết nối GSheet.")


@st.cache_data(ttl=CACHE_TTL)
def doc_sheet(sheet_id: str, sheet_tab: str, header_row: int) -> list[list]:
    try:
        client = ket_noi_gsheet()
        ws = client.open_by_key(sheet_id).worksheet(sheet_tab)
        all_rows = ws.get_all_values()
        return all_rows[header_row:]
    except Exception as e:
        logger.error("doc_sheet: %s", e, exc_info=True)
        raise


def la_pgd_header(stt) -> bool:
    if stt is None:
        return False
    s = str(stt).strip()
    if not s:
        return False
    try:
        float(s)
        return False
    except (ValueError, TypeError):
        return True


def la_dong_tong_cong(name: str) -> bool:
    s = name.strip().lower()
    return any(kw in s for kw in ["tổng cộng", "tổng số", "cộng", "ghi chú"])


def da_nhap(val) -> bool:
    return val is not None and str(val).strip() != ""


def phan_nhom_pgd(
    rows: list[list],
    stt_idx: int,
    name_idx: int,
    loai: str = "phan_cap_stt",
    pgd_col_idx: int = 0,
) -> dict[str, list[list]]:
    """Phân nhóm rows theo PGD dựa theo loại cấu trúc."""

    if loai == "phang":
        groups: dict[str, list[list]] = {}
        for row in rows:
            if not any(str(c).strip() for c in row):
                continue
            name = str(row[name_idx]).strip() if len(row) > name_idx else ""
            if name and not la_dong_tong_cong(name):
                groups[name] = [row]
        return groups

    if loai == "cot_pgd":
        groups = {}
        for row in rows:
            if not any(str(c).strip() for c in row):
                continue
            pgd = str(row[pgd_col_idx]).strip() if len(row) > pgd_col_idx else ""
            name = str(row[name_idx]).strip() if len(row) > name_idx else ""
            if pgd and not la_dong_tong_cong(name):
                groups.setdefault(pgd, []).append(row)
        return groups

    groups = {}
    current: str | None = None
    for row in rows:
        if not any(str(c).strip() for c in row):
            continue
        stt = row[stt_idx] if len(row) > stt_idx else ""
        name = row[name_idx] if len(row) > name_idx else ""
        if la_pgd_header(stt):
            current = str(name).strip()
            if current and current not in groups:
                groups[current] = []
        elif current is not None and not la_dong_tong_cong(str(name)):
            groups[current].append(row)
    return groups


def tinh_tien_do(pgd_groups: dict, ds_ct: list[dict]) -> pd.DataFrame:
    rows_out = []
    for pgd, sub_rows in pgd_groups.items():
        total = len(sub_rows)
        row: dict = {"Đơn vị": pgd, "_total": total}
        sum_pct = 0.0
        ap_dung_count = 0
        for ct in ds_ct:
            ten = ct["ten"]
            pgd_list = ct.get("pgd_list") or []
            ap_dung = (not pgd_list) or (pgd in pgd_list)
            if not ap_dung:
                row[f"{ten}_filled"] = None
                row[f"{ten}_total"] = None
                row[f"{ten}_pct"] = None
                continue
            ci = ct["col"] - 1
            filled = sum(1 for r in sub_rows if len(r) > ci and da_nhap(r[ci]))
            pct = (filled / total * 100) if total > 0 else 0.0
            row[f"{ten}_filled"] = filled
            row[f"{ten}_total"] = total
            row[f"{ten}_pct"] = round(pct, 1)
            sum_pct += pct
            ap_dung_count += 1
        row["Tổng_pct"] = round(sum_pct / ap_dung_count, 1) if ap_dung_count else 0.0
        rows_out.append(row)
    return pd.DataFrame(rows_out) if rows_out else pd.DataFrame()


def emoji_pct(pct: float | None) -> str:
    from .constants import EMOJI_PCT
    if pct is None:
        return "—"
    if pct >= 100:
        return EMOJI_PCT["full"]
    if pct > 0:
        return EMOJI_PCT["partial"]
    return EMOJI_PCT["empty"]


# ── Config persistence ────────────────────────────────────────────────────────

def doc_ds_sheet() -> list[dict]:
    saved = db.doc_kv(KV_LIST_KEY)
    if saved and isinstance(saved, list):
        return saved

    legacy = db.doc_kv(KV_LEGACY_KEY)
    if legacy and isinstance(legacy, dict) and legacy.get("sheet_id"):
        migrated = [{
            "ten_hien_thi": legacy.get("sheet_tab", "Sheet cũ")[:40],
            **legacy,
        }]
        db.ghi_kv(KV_LIST_KEY, migrated, "system")
        return migrated
    return []


def luu_ds_sheet(ds: list[dict], username: str) -> None:
    db.ghi_kv(KV_LIST_KEY, ds, username)
    db.ghi_audit(username, "luu_theo_doi_nhap_config", f"{len(ds)} sheet(s)")


def sheet_moi() -> dict:
    return {
        "ten_hien_thi": "",
        "sheet_id": "",
        "sheet_tab": "",
        "header_row": 10,
        "stt_col": 1,
        "name_col": 2,
        "ds_chuong_trinh": list(DEFAULT_CT),
    }


# ── Snapshot history (⭐ MỚI) ──────────────────────────────────────────────────

def luu_snapshot(
    sheet_id: str,
    sheet_tab: str,
    df_td: pd.DataFrame,
    username: str,
) -> None:
    """Lưu snapshot tiến độ 1 lần/ngày để so sánh."""
    if df_td.empty:
        return

    today = _date.today().isoformat()
    key = f"{KV_SNAPSHOT_PREFIX}{sheet_id}_{sheet_tab}_{today}"

    existing = db.doc_kv(key)
    if existing is not None:
        return

    data = {
        "ngay": today,
        "sheet_id": sheet_id,
        "sheet_tab": sheet_tab,
        "tong_pct": round(float(df_td["Tổng_pct"].mean()), 1),
        "so_pgd_full": int((df_td["Tổng_pct"] >= 100).sum()),
        "so_pgd_empty": int((df_td["Tổng_pct"] == 0).sum()),
        "total_pgd": len(df_td),
        "chi_tiet": df_td.to_dict(orient="records"),
    }
    db.ghi_kv(key, data, username)


def doc_snapshot_truoc(
    sheet_id: str,
    sheet_tab: str,
    ngay_hien_tai: str | None = None,
) -> dict | None:
    """Đọc snapshot gần nhất trước ngày hiện tại."""
    if ngay_hien_tai is None:
        ngay_hien_tai = _date.today().isoformat()

    all_snapshots = db.doc_kv_prefix(KV_SNAPSHOT_PREFIX)
    candidates = []
    for key, val in all_snapshots.items():
        if not isinstance(val, dict):
            continue
        if val.get("sheet_id") != sheet_id:
            continue
        if val.get("sheet_tab") != sheet_tab:
            continue
        ngay = val.get("ngay", "")
        if ngay and ngay < ngay_hien_tai:
            candidates.append((ngay, val))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def cleanup_snapshots_cu(so_ngay_giu: int = 90) -> int:
    """Xóa snapshot cũ hơn N ngày. Trả về số đã xóa."""
    from datetime import timedelta

    cutoff = (_date.today() - timedelta(days=so_ngay_giu)).isoformat()
    all_snapshots = db.doc_kv_prefix(KV_SNAPSHOT_PREFIX)
    deleted = 0
    for key, val in all_snapshots.items():
        if isinstance(val, dict) and val.get("ngay", "") < cutoff:
            db.ghi_kv(key, None, "system")
            deleted += 1
    return deleted
