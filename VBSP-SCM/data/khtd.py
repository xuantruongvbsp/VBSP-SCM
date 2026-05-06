"""Quản lý Kế hoạch Tín dụng: SQLite kv_store + đọc file phụ lục QĐ UBND tỉnh."""
import os
import json
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
from datetime import datetime as _dt

import pandas as pd

from config import FILE_KHTD
from .pgd import pgd_slug


# ── Trợ giúp nội bộ: đọc/ghi kv_store ───────────────────────────────────────
def _kv_get(key: str) -> dict:
    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM kv_store WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row["value"]) if row else {}
    except Exception:
        return {}


def _kv_set(key: str, data: dict):
    try:
        with db.get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO kv_store
                   (key, value, updated_at, updated_by)
                   VALUES (?,?,?,?)""",
                (key, json.dumps(data, ensure_ascii=False),
                 _dt.now().isoformat(), "system")
            )
            conn.commit()
    except Exception:
        pass


# ── KH SQLite ─────────────────────────────────────────────────────────────────
def doc_khtd() -> dict:
    """Đọc kế hoạch tín dụng từ kv_store."""
    return _kv_get("khtd")


def luu_khtd(data: dict):
    """Lưu kế hoạch tín dụng vào kv_store."""
    _kv_set("khtd", data)


# ── Kế hoạch Điện báo (dùng cho tab_kehoach) ─────────────────────────────────
def doc_kehoach(ten_pgd: str | None = None) -> dict:
    """Đọc kế hoạch Điện báo từ kv_store. CN: key ``kehoach``; PGD: ``kehoach_pgd_{slug}``."""
    key = f"kehoach_pgd_{pgd_slug(ten_pgd)}" if ten_pgd else "kehoach"
    return _kv_get(key)


def luu_kehoach(kh: dict, ten_pgd: str | None = None):
    key = f"kehoach_pgd_{pgd_slug(ten_pgd)}" if ten_pgd else "kehoach"
    _kv_set(key, kh)


# ── CBTD SQLite ───────────────────────────────────────────────────────────────
def doc_cbtd() -> dict:
    return _kv_get("cbtd")


def luu_cbtd(data: dict):
    _kv_set("cbtd", data)


# ── Đọc file phụ lục QĐ UBND tỉnh ────────────────────────────────────────────
_LA_MA = {
    'I','II','III','IV','V','VI','VII','VIII','IX','X',
    'XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX',
    'XX','XXI','XXII','XXIII',
}

_SHEET_MAP = {
    'CTR ngheo':     'TW',
    'CTR ngheo (2)': 'DP',
}

# Cột → mã CT key (dùng mã nội bộ, không đổi khi đổi tên hiển thị)
_CT_TW_MAP = {4:"1_TW", 7:"19_TW", 10:"9_TW",  13:"99_TW"}
_CT_DP_MAP = {4:"1_DP", 7:"19_DP", 10:"9_DP",  13:"3_DP"}

from config import BASE_DIR
FILE_KH_QD = str(BASE_DIR / "khtd_qd.xlsx")


def doc_phu_luc_qd(filepath_or_bytes) -> dict:
    """
    Đọc file phụ lục QĐ UBND tỉnh → dict khtd_data.
    Hỗ trợ đường dẫn file hoặc bytes từ st.file_uploader.

    Cấu trúc file:
      Sheet 'CTR ngheo'    → TW (Hộ nghèo, Cận nghèo, Thoát nghèo, SXKD VKK)
      Sheet 'CTR ngheo (2)'→ ĐP (Hộ nghèo, Cận nghèo, Thoát nghèo, GQVL ĐP)

    Trả về dict {xa|ma_ct_key: gia_tri_dong}
    """
    src = BytesIO(filepath_or_bytes) if isinstance(filepath_or_bytes, bytes) \
          else filepath_or_bytes
    xl   = pd.ExcelFile(src)
    khtd = {}

    for sheet, nv in _SHEET_MAP.items():
        if sheet not in xl.sheet_names:
            continue
        df_s   = pd.read_excel(xl, sheet_name=sheet, header=None)
        ct_map = _CT_TW_MAP if nv == "TW" else _CT_DP_MAP

        for _, row in df_s.iloc[10:].iterrows():
            ten = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
            stt = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if ten in ("", "nan", "Tổng cộng") or stt in _LA_MA:
                continue
            for col_idx, ma_key in ct_map.items():
                try:
                    v   = row.iloc[col_idx]
                    val = float(v) * 1e6 if pd.notna(v) and str(v) != "nan" else 0.0
                except:
                    val = 0.0
                if val > 0:
                    khtd[f"{ten}|{ma_key}"] = val

    return khtd


def luu_phu_luc_qd(file_bytes: bytes) -> dict:
    """Lưu file phụ lục QĐ gốc + load KH vào khtd.json."""
    os.makedirs(os.path.dirname(FILE_KH_QD), exist_ok=True)
    with open(FILE_KH_QD, "wb") as f:
        f.write(file_bytes)
    khtd = doc_phu_luc_qd(file_bytes)
    luu_khtd(khtd)
    return khtd
