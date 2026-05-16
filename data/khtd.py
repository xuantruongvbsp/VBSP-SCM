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


# ── CBTD ↔ ĐGD helpers ───────────────────────────────────────────────────────

def lay_ap_tu_dgd_list(pgd: str, ds_dgd: list, dgd_map: dict) -> list[tuple[str, str]]:
    """Trả về list (ten_xa, ten_ap) từ ds_dgd trong dgd_map của một PGD.

    Args:
        pgd: Tên PGD (key trong dgd_map)
        ds_dgd: Danh sách tên ĐGD mà CBTD phụ trách
        dgd_map: Dict {pgd: {xa: {dgd_name: [ap_list]}}}
    Returns:
        List (ten_xa, ten_ap) — dùng để join với HSTD qua cột Tên xã + Tên thôn
    """
    result = []
    xa_block = (dgd_map or {}).get(pgd, {})
    for ten_xa, dgd_block in xa_block.items():
        if not isinstance(dgd_block, dict):
            continue
        for dgd_name, ap_list in dgd_block.items():
            if dgd_name in ds_dgd:
                for ap in (ap_list or []):
                    ap_s = str(ap).strip()
                    if ap_s:
                        result.append((ten_xa, ap_s))
    return result


def xay_ap_to_cbtd_map(cbtd_data: dict, dgd_map: dict) -> dict:
    """Xây dict (xa_lower, ap_lower) → (ma_cb, ten_cb) để join với HSTD.

    1 ĐGD = 1 CBTD nên không có trùng. Key đầu tiên thắng nếu có xung đột.
    """
    result: dict[tuple[str, str], tuple[str, str]] = {}
    for ma_cb, info in (cbtd_data or {}).items():
        pgd = info.get("pgd", "")
        ds_dgd = info.get("ds_dgd", [])
        if not pgd or not ds_dgd:
            continue
        for ten_xa, ten_ap in lay_ap_tu_dgd_list(pgd, ds_dgd, dgd_map):
            key = (ten_xa.lower().strip(), ten_ap.lower().strip())
            if key not in result:
                result[key] = (ma_cb, info.get("ho_ten", ""))
    return result


def gan_cbtd_vao_df(
    df,
    cbtd_data: dict,
    dgd_map: dict,
    col_xa: str = "Tên xã",
    col_thon: str = "Tên thôn",
):
    """Thêm cột 'CBTD' (mã) và 'Tên CBTD' vào df. Join qua (Tên xã, Tên thôn).

    Nếu không tìm được khớp, giá trị là None.
    """
    df = df.copy()
    ap_map = xay_ap_to_cbtd_map(cbtd_data, dgd_map)
    if not ap_map or col_xa not in df.columns or col_thon not in df.columns:
        df["CBTD"] = None
        df["Tên CBTD"] = None
        return df
    xa_s = df[col_xa].fillna("").astype(str).str.strip().str.lower()
    thon_s = df[col_thon].fillna("").astype(str).str.strip().str.lower()
    keys = list(zip(xa_s, thon_s))
    df["CBTD"]     = [ap_map.get(k, (None, None))[0] for k in keys]
    df["Tên CBTD"] = [ap_map.get(k, (None, None))[1] for k in keys]
    return df


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
