"""Quản lý Kế hoạch Tín dụng: SQLite kv_store + đọc file phụ lục QĐ UBND tỉnh."""
import os
import re
import json
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
from datetime import datetime as _dt

import pandas as pd

from config import FILE_KHTD
from .pgd import pgd_slug
from .dgd_helpers import ds_ma_thon_cua_entry


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
    seen = set()
    xa_block = (dgd_map or {}).get(pgd, {})
    for ten_xa, dgd_block in xa_block.items():
        if not isinstance(dgd_block, dict):
            continue
        for dgd_name, ap_list in dgd_block.items():
            if dgd_name in ds_dgd:
                # Schema moi: ap_list co the la dict {"thon": [...]} hoac list cu
                if isinstance(ap_list, dict):
                    thon_items = ap_list.get("thon", [])
                elif isinstance(ap_list, list):
                    thon_items = ap_list
                else:
                    thon_items = []
                for ap in thon_items:
                    # Gom khoảng trắng liên tiếp: dgd_map có thể lưu cùng một ấp
                    # với 2 biến thể ("Khu phố  Tân Hạnh 1" / "Khu phố Tân Hạnh 1").
                    ap_s = "" if ap is None else re.sub(r"\s+", " ", str(ap).strip())
                    if not ap_s or ap_s.lower() in {"nan", "none", "<na>"}:
                        continue
                    key = (_normalize_cbtd_join_text(ten_xa), _normalize_cbtd_join_text(ap_s))
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append((ten_xa, ap_s))
    return result


def lay_thong_tin_dgd_theo_ten(pgd: str, ds_dgd: list, dgd_map: dict) -> dict[str, dict]:
    """Trả về dict[dgd_name] → {"xa": ten_xa, "thon": [list ten_thon_clean]} cho UI hiển thị.

    Giữ nguyên ĐGD trong ``ds_dgd`` ngay cả khi không tìm thấy trong
    ``dgd_map`` (trả về xa="" / thon=[]) để bảng phân công không mất dòng
    (user thấy rõ ĐGD nào chưa được cấu hình thôn/ấp).

    Args:
        pgd: Tên PGD
        ds_dgd: List tên ĐGD cần lấy metadata (thứ tự được bảo toàn theo key set)
        dgd_map: Dict {pgd: {xa: {dgd_name: entry}}}  (entry là list hoặc dict {"thon":...})

    Returns:
        dict[str, dict] — key là tên ĐGD, value có keys "xa" và "thon".
    """
    out: dict[str, dict] = {d: {"xa": "", "thon": []} for d in (ds_dgd or [])}
    xa_block = (dgd_map or {}).get(pgd, {})
    for ten_xa, dgd_block in xa_block.items():
        if not isinstance(dgd_block, dict):
            continue
        for dgd_name, entry in dgd_block.items():
            if dgd_name not in out:
                continue
            if isinstance(entry, dict):
                thon_items = entry.get("thon", []) or []
            elif isinstance(entry, list):
                thon_items = entry
            else:
                thon_items = []
            clean = []
            for ap in thon_items:
                ap_s = "" if ap is None else str(ap).strip()
                if ap_s and ap_s.lower() not in {"nan", "none", "<na>"}:
                    clean.append(ap_s)
            out[dgd_name]["xa"] = ten_xa
            out[dgd_name]["thon"] = clean
    return out


def _normalize_cbtd_join_text(value) -> str:
    """Normalize key xã/thôn đồng nhất ở cả lookup và DataFrame side."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        text = re.sub(r"\s+", " ", str(value).strip()).lower()
    except Exception:
        return ""
    return "" if text in {"nan", "none", "<na>"} else text


def _normalize_cbtd_join_series(values: pd.Series) -> pd.Series:
    text = (
        values.astype("string").fillna("").str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.lower()
    )
    return text.mask(text.isin(("nan", "none", "<na>")), "")


def _normalize_ma_text(value) -> str:
    """Chuẩn hóa mã thôn/mã tổ: bỏ '.0' đuôi số thực, khoảng trắng, viết thường."""
    base = _normalize_cbtd_join_text(value)
    if not base:
        return ""
    return re.sub(r"\.0+$", "", base)


def _normalize_ma_series(values: pd.Series) -> pd.Series:
    text = _normalize_cbtd_join_series(values).str.replace(r"\.0+$", "", regex=True)
    return text.mask(text.isin(("nan", "none", "<na>")), "")


def xay_ap_to_cbtd_map(cbtd_data: dict, dgd_map: dict) -> dict:
    """Xây dict (pgd_lower, xa_lower, ap_lower) → (ma_cb, ten_cb).

    Phải có chiều PGD vì tên xã/thôn có thể trùng giữa các đơn vị. Một ĐGD
    thuộc đúng một CBTD nên key đầu tiên thắng nếu cấu hình vẫn còn xung đột.
    """
    result: dict[tuple[str, str, str], tuple[str, str]] = {}
    for ma_cb, info in (cbtd_data or {}).items():
        pgd = info.get("pgd", "")
        ds_dgd = info.get("ds_dgd", [])
        if not pgd or not ds_dgd:
            continue
        for ten_xa, ten_ap in lay_ap_tu_dgd_list(pgd, ds_dgd, dgd_map):
            key = (
                _normalize_cbtd_join_text(pgd),
                _normalize_cbtd_join_text(ten_xa),
                _normalize_cbtd_join_text(ten_ap),
            )
            if key not in result:
                result[key] = (ma_cb, info.get("ho_ten", ""))
    return result


def lay_ma_thon_tu_dgd_list(pgd: str, ds_dgd: list, dgd_map: dict) -> list[str]:
    """Trả về danh sách MÃ thôn của các Điểm GD trong ds_dgd thuộc một PGD.

    Mã thôn là khóa CHÍNH để gắn HSTD → Điểm GD → CBTD: tên thôn có thể trống,
    trùng hoặc đổi cách viết giữa các kỳ, còn mã thôn thì ổn định.
    """
    result: list[str] = []
    xa_block = (dgd_map or {}).get(pgd, {})
    for ten_xa, dgd_block in xa_block.items():
        if not isinstance(dgd_block, dict):
            continue
        for dgd_name, entry in dgd_block.items():
            if dgd_name in ds_dgd:
                for mt in ds_ma_thon_cua_entry(entry):
                    if mt not in result:
                        result.append(mt)
    return result


def xay_ma_thon_to_cbtd_map(cbtd_data: dict, dgd_map: dict) -> dict:
    """Xây dict (pgd_lower, ma_thon_lower) → (ma_cb, ten_cb).

    Mã thôn chỉ ổn định trong phạm vi PGD, không bảo đảm duy nhất toàn Chi
    nhánh. Ghép thêm PGD để không gán nhầm hồ sơ giữa hai đơn vị có cùng mã.
    """
    result: dict[tuple[str, str], tuple[str, str]] = {}
    for ma_cb, info in (cbtd_data or {}).items():
        pgd = info.get("pgd", "")
        ds_dgd = info.get("ds_dgd", [])
        if not pgd or not ds_dgd:
            continue
        for mt in lay_ma_thon_tu_dgd_list(pgd, ds_dgd, dgd_map):
            key = (_normalize_cbtd_join_text(pgd), _normalize_ma_text(mt))
            if key[1] and key not in result:
                result[key] = (ma_cb, info.get("ho_ten", ""))
    return result


def danh_sach_dgd_chua_co_cbtd(dgd_map: dict, cbtd_data: dict, pgd_filter: str | None = None) -> list[dict]:
    """Quét dgd_map → list các ĐGD CHƯA được gắn vào trường ds_dgd của bất kỳ CBTD nào.

    Mỗi entry trả về: ``{"pgd": str, "xa": str, "ten_dgd": str,
    "so_ma_thon": int, "so_thon": int, "ngay_gdxa": int|None}``.
    Dùng làm input cho nút "Tạo nhanh CBTD cho các ĐGD còn thiếu".
    """
    # Build set {(pgd, ten_dgd): ma_cb} từ cbtd_data để O(1) check
    dgd_to_cb: dict[tuple[str, str], str] = {}
    for ma_cb, info in (cbtd_data or {}).items():
        pgd = info.get("pgd", "")
        for dgd_n in info.get("ds_dgd", []) or []:
            if pgd and dgd_n:
                dgd_to_cb[(pgd, dgd_n)] = ma_cb

    rows: list[dict] = []
    for pgd, xa_dict in (dgd_map or {}).items():
        if pgd_filter and str(pgd_filter).strip() and str(pgd_filter).strip() != str(pgd).strip():
            continue
        if not isinstance(xa_dict, dict):
            continue
        for xa, dgd_dict in xa_dict.items():
            if not isinstance(dgd_dict, dict):
                continue
            for ten_dgd, entry in dgd_dict.items():
                ma_s = ds_ma_thon_cua_entry(entry)
                thon_s = []
                if isinstance(entry, dict):
                    if not ma_s:
                        # backward-compat lấy thôn từ key "thon"
                        raw_thon = entry.get("thon", [])
                        if isinstance(raw_thon, list):
                            thon_s = [str(t).strip() for t in raw_thon if str(t).strip() and str(t).strip().lower() != "nan"]
                    ngay = entry.get("ngay_gdxa")
                elif isinstance(entry, list):
                    thon_s = [str(t).strip() for t in entry if str(t).strip() and str(t).strip().lower() != "nan"]
                    ngay = None
                else:
                    ngay = None
                # ĐGD "thực" được định nghĩa là: có ma_thôn HOẶC có thôn (ít nhất 1 mã/thôn)
                if not ma_s and not thon_s:
                    continue
                if (pgd, ten_dgd) in dgd_to_cb:
                    continue
                rows.append({
                    "pgd": pgd,
                    "xa": xa,
                    "ten_dgd": ten_dgd,
                    "so_ma_thon": len(ma_s),
                    "so_thon": len(thon_s),
                    "ngay_gdxa": (int(ngay) if isinstance(ngay, (int, float)) and not pd.isna(ngay) else None),
                })
    return rows


def tao_cbtd_tu_dgd(dgd_map: dict, cbtd_data: dict | None = None,
                    pgd_filter: str | None = None,
                    username: str = "system_auto",
                    overwrite: bool = False) -> tuple[dict, list[dict]]:
    """Tự tạo CBTD tạm cho từng ĐGD còn thiếu.

    Rule (chính user chốt): **1 Điểm GD = đúng 1 CBTD phụ trách.**
    - Mã CBTD tự sinh: ``"CB_" + pgd_slug(ten_dgd)``  (trùng tên ĐGD để sau này rename dễ)
    - Tên CBTD (ho_ten): mặc định = ``ten_dgd``, ghi chú "Tự tạo từ ĐGD"
    - ``ds_dgd = [ten_dgd]`` (1-1), ``pgd`` lấy từ dgd_map key, ``ngay_cap`` hiện tại.

    Args:
        dgd_map: Cấu hình Điểm GD (kv_store dgd_map)
        cbtd_data: cbtd cũ để merge (không làm thay đổi ĐÃ CÓ CBTD)
        pgd_filter: Chỉ tạo cho PGD này (None = tất cả)
        username: Ghi vào trường ``created_by`` tạm cho audit
        overwrite: False (an toàn mặc định) = chỉ tạo cho ĐGD chưa có CBTD
                   True = override DS_DGD của mọi CBTD cũ theo rule 1-1 NGUY HIỂM.

    Returns:
        ``(cbtd_data_moi, ds_cbtd_vua_tao)`` — ds_cbtd_vua_tao chứa các dict
        info CBTD mới tạo (không có trong input).
    """
    from data.pgd import pgd_slug as _slug_dgd

    existing = dict(cbtd_data or {})
    ds_con_thieu = danh_sach_dgd_chua_co_cbtd(dgd_map, existing, pgd_filter)

    created: list[dict] = []
    used_ma: set[str] = set(existing.keys())
    ts = _dt.now().strftime("%d/%m/%Y %H:%M")
    for item in ds_con_thieu:
        pgd = item["pgd"]
        ten_dgd = item["ten_dgd"]
        base_ma = "CB_" + _slug_dgd(ten_dgd)
        # Xung đột: 2 ĐGD cùng tên ở 2 PGD? → nối thêm slug_pgd
        ma_cb = base_ma
        if ma_cb in used_ma:
            ma_cb = base_ma + "_" + _slug_dgd(str(pgd))
            k = 2
            while ma_cb in used_ma:
                ma_cb = f"{base_ma}_{_slug_dgd(str(pgd))}_{k}"
                k += 1
        info_moi = {
            "ho_ten": ten_dgd,
            "chuc_vu": "Cán bộ tín dụng",
            "pgd": pgd,
            "xa_phu_trach": [item["xa"]] if item["xa"] else [],
            "ds_dgd": [ten_dgd],
            "ngay_cap": ts,
            "ghi_chu": "Tự tạo từ Điểm GD (chưa nhập tên thật)",
            "created_by": username,
            "auto_generated": True,
        }
        existing[ma_cb] = info_moi
        used_ma.add(ma_cb)
        created.append({"ma_cb": ma_cb, **info_moi})

    if overwrite:
        # Mode này KHÔNG recommended, chỉ cho phép test đơn vị
        # Giữ nguyên existing nhưng tách lại DS_DGD theo rule 1-1 cho mọi item
        # (bỏ qua — giữ overwrite= chỉ tạo đủ, không đụng tới CBTD đã có thật)
        pass

    return existing, created


def gan_cbtd_vao_df(
    df,
    cbtd_data: dict,
    dgd_map: dict,
    col_xa: str = "Tên xã",
    col_thon: str = "Tên thôn",
    col_ma_thon: str = "Mã thôn",
    col_pgd: str = "Tên PGD",
    fallback_xa_dgd: bool = False,
):
    """Thêm cột 'CBTD' (mã) và 'Tên CBTD' vào df.

    Join ưu tiên theo (PGD, MÃ THÔN), phần còn lại fallback về
    (PGD, Tên xã, Tên thôn). Nếu DataFrame cũ thiếu cột PGD thì chỉ dùng key
    không bị trùng giữa các PGD. Vectorised bằng Series.map.
    """
    df = df.copy()
    df["CBTD"] = None
    df["Tên CBTD"] = None

    ma_map = xay_ma_thon_to_cbtd_map(cbtd_data, dgd_map)
    if ma_map and col_ma_thon in df.columns:
        ma_s = _normalize_ma_series(df[col_ma_thon])
        if col_pgd in df.columns:
            pgd_s = _normalize_cbtd_join_series(df[col_pgd])
            join_key = pgd_s + "\x1f" + ma_s
            df["CBTD"] = join_key.map({f"{kp}\x1f{km}": v[0] for (kp, km), v in ma_map.items()})
            df["Tên CBTD"] = join_key.map({f"{kp}\x1f{km}": v[1] for (kp, km), v in ma_map.items()})
        else:
            # Tương thích file cũ thiếu PGD: chỉ dùng mã xuất hiện ở đúng 1 PGD.
            by_ma: dict[str, list[tuple[str, str]]] = {}
            for (_, km), value in ma_map.items():
                by_ma.setdefault(km, []).append(value)
            unique_ma = {km: vals[0] for km, vals in by_ma.items() if len(vals) == 1}
            df["CBTD"] = ma_s.map({k: v[0] for k, v in unique_ma.items()})
            df["Tên CBTD"] = ma_s.map({k: v[1] for k, v in unique_ma.items()})

    ap_map = xay_ap_to_cbtd_map(cbtd_data, dgd_map)
    if ap_map and col_xa in df.columns and col_thon in df.columns:
        xa_s = _normalize_cbtd_join_series(df[col_xa])
        thon_s = _normalize_cbtd_join_series(df[col_thon])
        str_map_cb: dict[str, str | None] = {}
        str_map_ten: dict[str, str | None] = {}
        if col_pgd in df.columns:
            join_key = _normalize_cbtd_join_series(df[col_pgd]) + "\x1f" + xa_s + "\x1f" + thon_s
            for (kp, kx, kt), (v_cb, v_ten) in ap_map.items():
                str_map_cb[f"{kp}\x1f{kx}\x1f{kt}"] = v_cb
                str_map_ten[f"{kp}\x1f{kx}\x1f{kt}"] = v_ten
        else:
            join_key = xa_s + "\x1f" + thon_s
            by_ap: dict[tuple[str, str], list[tuple[str, str]]] = {}
            for (_, kx, kt), value in ap_map.items():
                by_ap.setdefault((kx, kt), []).append(value)
            for (kx, kt), values in by_ap.items():
                if len(values) == 1:
                    str_map_cb[f"{kx}\x1f{kt}"] = values[0][0]
                    str_map_ten[f"{kx}\x1f{kt}"] = values[0][1]
        con_thieu = df["CBTD"].isna()
        df.loc[con_thieu, "CBTD"] = join_key[con_thieu].map(str_map_cb)
        df.loc[con_thieu, "Tên CBTD"] = join_key[con_thieu].map(str_map_ten)

    # Fallback riêng cho snapshot lịch sử trước/sau sáp nhập: nhiều dòng kỳ cũ
    # còn mã thôn cũ hoặc tên thôn trống, nhưng tên xã cũ trùng chính xác tên ĐGD.
    if fallback_xa_dgd and col_pgd in df.columns and col_xa in df.columns:
        con_thieu = df["CBTD"].isna()
        if con_thieu.any():
            owner_by_dgd: dict[tuple[str, str], tuple[str, str] | None] = {}
            for ma_cb, info in (cbtd_data or {}).items():
                pgd_key = _normalize_cbtd_join_text((info or {}).get("pgd", ""))
                ten_cb = (info or {}).get("ho_ten", "")
                if not pgd_key:
                    continue
                for dgd_name in (info or {}).get("ds_dgd", []) or []:
                    dgd_key = _normalize_cbtd_join_text(dgd_name)
                    if not dgd_key:
                        continue
                    key = (pgd_key, dgd_key)
                    value = (ma_cb, ten_cb)
                    if key in owner_by_dgd and owner_by_dgd[key] != value:
                        owner_by_dgd[key] = None
                    else:
                        owner_by_dgd[key] = value

            xa_fallback_cb: dict[str, str] = {}
            xa_fallback_ten: dict[str, str] = {}
            for pgd_k, xa_block in (dgd_map or {}).items():
                pgd_key = _normalize_cbtd_join_text(pgd_k)
                if not pgd_key or not isinstance(xa_block, dict):
                    continue
                for xa_name, dgd_block in xa_block.items():
                    xa_key = _normalize_cbtd_join_text(xa_name)
                    if not xa_key or not isinstance(dgd_block, dict):
                        continue
                    owner = owner_by_dgd.get((pgd_key, xa_key))
                    if owner is None:
                        continue
                    if owner and xa_key in {_normalize_cbtd_join_text(x) for x in dgd_block.keys()}:
                        join = f"{pgd_key}\x1f{xa_key}"
                        xa_fallback_cb[join] = owner[0]
                        xa_fallback_ten[join] = owner[1]

            if xa_fallback_cb:
                join_key = _normalize_cbtd_join_series(df[col_pgd]) + "\x1f" + _normalize_cbtd_join_series(df[col_xa])
                df.loc[con_thieu, "CBTD"] = join_key[con_thieu].map(xa_fallback_cb)
                df.loc[con_thieu, "Tên CBTD"] = join_key[con_thieu].map(xa_fallback_ten)
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
                except (ValueError, TypeError, IndexError):
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
