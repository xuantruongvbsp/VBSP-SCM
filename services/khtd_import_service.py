"""Import Biểu 01C / Biểu 02C từ TTBC; lưu/đọc Thuyết minh và KH dư nợ tương lai.

Namespace kv_store: khtd_xd_{loai}_*
  loai = "1n" (1 năm) | "3n" (3 năm) | "5n" (5 năm 2026–2030)
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd

from logger import get_logger

logger = get_logger(__name__)

import db
from config import (
    BIEU_01C_XD_MA_KEY,
    BIEU_02C_THUYET_MINH_XD,
    CHUONG_TRINH_KHTD,
    DS_PGD,
    PGD_XA_MAP,
)
from data.pgd import pgd_slug as _slug
from services.upload_service import KetQuaUpload


# ── Biểu 01C: đọc file TTBC ──────────────────────────────────────────────────

def doc_bieu_01c(file_bytes: bytes) -> dict[str, dict[str, dict[str, float]]]:
    """Đọc KHNV_01C.XLSX → {ten_xa: {ten_ap: {ma_key: trieu_dong}}}.

    Cấu trúc file TTBC:
    - Dòng 1–10: tiêu đề / header
    - Dòng 11 (index 10): hàng mã XD-code (cột 4+)
    - Dòng 12+: data — xã header (tên dạng "Năm 20XX") rồi ấp
    """
    df_raw = pd.read_excel(BytesIO(file_bytes), sheet_name=0, header=None, dtype=str)
    if len(df_raw) <= 10:
        return {}

    # Dòng index 10: XD codes
    xd_row = df_raw.iloc[10]
    col_to_makey: dict[int, str] = {}
    seen_makeys: set[str] = set()
    for col_idx, xd_val in enumerate(xd_row):
        xd_str = str(xd_val).strip() if pd.notna(xd_val) else ""
        if xd_str in BIEU_01C_XD_MA_KEY:
            mk = BIEU_01C_XD_MA_KEY[xd_str]
            if mk not in seen_makeys:
                col_to_makey[col_idx] = mk
                seen_makeys.add(mk)

    result: dict[str, dict[str, dict[str, float]]] = {}
    ten_xa_hien_tai = ""

    for row_idx in range(11, len(df_raw)):
        row = df_raw.iloc[row_idx]
        ma = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        ten = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

        if not ma or ma in ("nan", "None"):
            continue

        if not _la_ma_don_vi(ma):
            ten_xa_hien_tai = ten
            if ten_xa_hien_tai and ten_xa_hien_tai not in result:
                result[ten_xa_hien_tai] = {}
            continue

        if ten.startswith("Năm ") or ten.startswith("năm "):
            if ten_xa_hien_tai and ten_xa_hien_tai not in result:
                result[ten_xa_hien_tai] = {}
            continue

        if ten_xa_hien_tai and ten and ten not in ("nan", "None"):
            _them_ap(result, ten_xa_hien_tai, ten, row, col_to_makey)

    return result


def _la_ma_don_vi(ma: str) -> bool:
    return ma.isdigit() and 5 <= len(ma) <= 10


def _them_ap(
    result: dict,
    ten_xa: str,
    ten_ap: str,
    row: "pd.Series",
    col_to_makey: dict[int, str],
) -> None:
    ap_data: dict[str, float] = {}
    for col_idx, ma_key in col_to_makey.items():
        try:
            val = row.iloc[col_idx]
            if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
                continue
            fval = float(str(val).replace(",", "."))
            if fval > 0:
                ap_data[ma_key] = ap_data.get(ma_key, 0.0) + fval
        except (ValueError, IndexError):
            continue
    if ap_data:
        if ten_xa not in result:
            result[ten_xa] = {}
        result[ten_xa][ten_ap] = ap_data


# ── Biểu 01C: lưu vào kv_store ───────────────────────────────────────────────

def luu_bieu_01c(
    file_bytes: bytes,
    pgd_ten: str,
    nam: int,
    username: str,
    loai: str = "1n",
) -> KetQuaUpload:
    """Parse KHNV_01C.XLSX → ghi vào khtd_xd_{loai}_01c_{pgd_slug}_{xa_slug}_{nam}."""
    try:
        data_by_xa = doc_bieu_01c(file_bytes)
    except Exception as e:  # conv: skip
        logger.error("Lỗi đọc file Biểu 01C: %s", e, exc_info=True)
        return KetQuaUpload(False, f"❌ Không đọc được file Biểu 01C: {e}")

    if not data_by_xa:
        return KetQuaUpload(False, "⚠️ File không có dữ liệu ấp/thôn hợp lệ.")

    pgd_slug_str = _slug(pgd_ten)
    ds_xa_pgd = {xa.strip() for xa in PGD_XA_MAP.get(pgd_ten, [])}

    so_xa_luu = 0
    so_ap_tong = 0
    canh_bao: list[str] = []

    for ten_xa, ap_dict in data_by_xa.items():
        if not ap_dict:
            continue
        xa_slug_str = _tim_xa_slug(ten_xa, ds_xa_pgd)
        if xa_slug_str is None:
            canh_bao.append(f"'{ten_xa}'")
            continue

        kv_key = f"khtd_xd_{loai}_01c_{pgd_slug_str}_{xa_slug_str}_{nam}"
        du_lieu_cu: dict[str, float] = db.doc_kv(kv_key) or {}
        for ten_ap, ma_key_dict in ap_dict.items():
            for ma_key, val_trieu in ma_key_dict.items():
                du_lieu_cu[f"{ten_ap}|{ma_key}"] = val_trieu
        db.ghi_kv(kv_key, du_lieu_cu, username)
        so_xa_luu += 1
        so_ap_tong += len(ap_dict)

    if so_xa_luu == 0:
        msg = f"⚠️ Không khớp xã nào với PGD **{pgd_ten}**."
        if canh_bao:
            msg += " Xã trong file: " + ", ".join(canh_bao[:5])
        return KetQuaUpload(False, msg)

    db.ghi_audit(
        username, "import_bieu_01c",
        f"PGD: {pgd_ten} — Năm: {nam} — Loại: {loai} — {so_xa_luu} xã, {so_ap_tong} ấp/thôn",
    )

    thong_bao = (
        f"✅ Đã import Biểu 01C ({loai}) năm **{nam}**: "
        f"**{so_ap_tong} ấp/thôn** thuộc **{so_xa_luu} xã** của {pgd_ten}."
    )
    if canh_bao:
        thong_bao += f"\n⚠️ {len(canh_bao)} xã bỏ qua: " + "; ".join(canh_bao[:4])
    return KetQuaUpload(True, thong_bao)


def doc_bieu_01c_xd(pgd_ten: str, xa_ten: str, nam: int, loai: str = "1n") -> dict[str, float]:
    """Đọc dữ liệu Biểu 01C đã lưu cho 1 xã / 1 năm / 1 loại KH."""
    key = f"khtd_xd_{loai}_01c_{_slug(pgd_ten)}_{_slug(xa_ten)}_{nam}"
    return db.doc_kv(key) or {}


def _tim_xa_slug(ten_xa_file: str, ds_xa_pgd: set[str]) -> str | None:
    ten_norm = ten_xa_file.strip()
    if ten_norm in ds_xa_pgd:
        return _slug(ten_norm)
    for prefix in ("Xã ", "Phường ", "Thị trấn ", "xã ", "phường ", "thị trấn "):
        if ten_norm.startswith(prefix):
            ten_no_prefix = ten_norm[len(prefix):].strip()
            for xa in ds_xa_pgd:
                xa_no_prefix = xa
                for p in ("Xã ", "Phường ", "Thị trấn "):
                    if xa.startswith(p):
                        xa_no_prefix = xa[len(p):]
                        break
                if ten_no_prefix.lower() == xa_no_prefix.lower():
                    return _slug(xa)
    slug_file = _slug(ten_norm)
    for xa in ds_xa_pgd:
        if _slug(xa) == slug_file:
            return slug_file
    return None


# ── Biểu 02C: KH dư nợ theo chương trình ────────────────────────────────────

def luu_bieu_02c(
    pgd_ten: str,
    nam: int,
    du_lieu: dict,
    username: str,
    loai: str = "1n",
) -> bool:
    """Lưu KH dư nợ Biểu 02C cho 1 PGD / 1 năm / 1 loại KH."""
    key = f"khtd_xd_{loai}_02c_{_slug(pgd_ten)}_{nam}"
    payload = dict(du_lieu)
    payload["updated_at"] = datetime.now().isoformat()
    payload["updated_by"] = username
    db.ghi_kv(key, payload, username)
    db.ghi_audit(
        username, "luu_bieu_02c_xd",
        f"PGD: {pgd_ten} — Năm: {nam} — Loại: {loai}",
    )
    return True


def doc_bieu_02c(pgd_ten: str, nam: int, loai: str = "1n") -> dict:
    """Đọc KH dư nợ Biểu 02C của 1 PGD / 1 năm / 1 loại KH."""
    key = f"khtd_xd_{loai}_02c_{_slug(pgd_ten)}_{nam}"
    return db.doc_kv(key) or {}


def tong_hop_bieu_02c_cn(nam: int, loai: str = "1n") -> pd.DataFrame:
    """Tổng hợp dư nợ KH từ tất cả PGD cho 1 năm / 1 loại KH → DataFrame.

    Columns: PGD | ma_key | du_no_vnd | ten_ct | nguon_von
    """
    suffix = f"_{nam}"
    prefix = f"khtd_xd_{loai}_02c_"
    all_kv = db.doc_kv_prefix(prefix)

    rows = []
    ma_key_info = {mk: (ten, nv) for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD}

    for key, payload in all_kv.items():
        if not key.endswith(suffix):
            continue
        pgd_slug_part = key[len(prefix):-len(suffix)]
        pgd_ten = next(
            (p for p in DS_PGD if _slug(p) == pgd_slug_part),
            pgd_slug_part,
        )
        du_no_dict = payload.get("du_no", {})
        for mk, vnd in du_no_dict.items():
            ten_ct, nv = ma_key_info.get(mk, (mk, ""))
            rows.append({
                "PGD": pgd_ten,
                "ma_key": mk,
                "ten_ct": ten_ct,
                "nguon_von": nv,
                "du_no_vnd": float(vnd),
            })

    if not rows:
        return pd.DataFrame(columns=["PGD", "ma_key", "ten_ct", "nguon_von", "du_no_vnd"])
    return pd.DataFrame(rows)


def trang_thai_xd_pgd(nam: int, loai: str = "1n") -> dict[str, dict[str, bool]]:
    """Trả về {pgd_ten: {co_01c, co_02c, co_tm}} — 3 batch queries thay vì N×3."""
    suffix = f"_{nam}"
    all_01c = set(db.doc_kv_prefix(f"khtd_xd_{loai}_01c_").keys())
    all_02c = set(db.doc_kv_prefix(f"khtd_xd_{loai}_02c_").keys())
    all_tm  = set(db.doc_kv_prefix(f"khtd_xd_{loai}_tm_").keys())

    ket_qua: dict[str, dict[str, bool]] = {}
    for pgd_ten in DS_PGD:
        slug = _slug(pgd_ten)
        prefix_01c = f"khtd_xd_{loai}_01c_{slug}_"
        has_01c = any(k.startswith(prefix_01c) and k.endswith(suffix) for k in all_01c)
        has_02c = f"khtd_xd_{loai}_02c_{slug}{suffix}" in all_02c
        has_tm  = f"khtd_xd_{loai}_tm_{slug}{suffix}" in all_tm
        ket_qua[pgd_ten] = {"co_01c": has_01c, "co_02c": has_02c, "co_tm": has_tm}
    return ket_qua


# ── Thuyết minh chỉ tiêu ─────────────────────────────────────────────────────

def luu_thuyet_minh(
    pgd_ten: str,
    nam: int,
    du_lieu: dict[str, float],
    username: str,
    loai: str = "1n",
) -> bool:
    key = f"khtd_xd_{loai}_tm_{_slug(pgd_ten)}_{nam}"
    db.ghi_kv(key, du_lieu, username)
    db.ghi_audit(
        username, "luu_thuyet_minh_khtd",
        f"PGD: {pgd_ten} — Năm: {nam} — Loại: {loai} — {len(du_lieu)} chỉ tiêu",
    )
    return True


def doc_thuyet_minh(pgd_ten: str, nam: int, loai: str = "1n") -> dict[str, float]:
    key = f"khtd_xd_{loai}_tm_{_slug(pgd_ten)}_{nam}"
    return db.doc_kv(key) or {}


# ── Tổng hợp Biểu 01C toàn CN ────────────────────────────────────────────────

def tong_hop_bieu_01c_cn(nam: int, loai: str = "1n") -> pd.DataFrame:
    """Tổng hợp nhu cầu vay Biểu 01C từ tất cả PGD cho 1 năm / 1 loại KH.

    Columns: PGD | xa | ma_key | ten_ct | nhu_cau_trieu
    """
    prefix = f"khtd_xd_{loai}_01c_"
    all_kv = db.doc_kv_prefix(prefix)
    suffix = f"_{nam}"
    ma_key_info = {mk: ten for mk, _, ten, _, _ in CHUONG_TRINH_KHTD}

    rows = []
    for key, flat_data in all_kv.items():
        if not key.endswith(suffix):
            continue
        rest = key[len(prefix):]  # {pgd_slug}_{xa_slug}_{nam}
        for pgd_ten in DS_PGD:
            pgd_s = _slug(pgd_ten)
            if rest.startswith(pgd_s + "_"):
                xa_slug = rest[len(pgd_s) + 1 : -len(suffix)]
                for flat_key, val in flat_data.items():
                    mk = flat_key.split("|", 1)[1] if "|" in flat_key else flat_key
                    ten_ct = ma_key_info.get(mk, mk)
                    rows.append({
                        "PGD": pgd_ten,
                        "xa": xa_slug,
                        "ma_key": mk,
                        "ten_ct": ten_ct,
                        "nhu_cau_trieu": float(val),
                    })
                break

    if not rows:
        return pd.DataFrame(columns=["PGD", "xa", "ma_key", "ten_ct", "nhu_cau_trieu"])
    return pd.DataFrame(rows)


# ── Approval workflow ─────────────────────────────────────────────────────────

_DEFAULT_APPROVAL: dict = {
    "trang_thai": "nhap_lieu",
    "ngay_nop": None,
    "nguoi_nop": "",
    "ngay_duyet": None,
    "nguoi_duyet": "",
    "y_kien": "",
    "lan_nop": 0,
}


def doc_trang_thai_approval(pgd_ten: str, ds_nam: list[int], loai: str) -> dict:
    """Đọc trạng thái approval cho 1 PGD / giai đoạn."""
    key = f"khtd_xd_{loai}_status_{_slug(pgd_ten)}_{ds_nam[0]}"
    return db.doc_kv(key) or dict(_DEFAULT_APPROVAL)


def nop_ke_hoach(pgd_ten: str, ds_nam: list[int], loai: str, username: str) -> bool:
    """PGD nộp kế hoạch. Điều kiện: tất cả năm đều có đủ 3 biểu."""
    slug = _slug(pgd_ten)
    # Check conditions
    all_01c = set(db.doc_kv_prefix(f"khtd_xd_{loai}_01c_{slug}_").keys())
    for nam in ds_nam:
        suf = f"_{nam}"
        has_01c = any(k.endswith(suf) for k in all_01c)
        has_02c = bool(db.doc_kv(f"khtd_xd_{loai}_02c_{slug}_{nam}"))
        has_tm  = bool(db.doc_kv(f"khtd_xd_{loai}_tm_{slug}_{nam}"))
        if not (has_01c and has_02c and has_tm):
            return False

    key = f"khtd_xd_{loai}_status_{slug}_{ds_nam[0]}"
    cu = doc_trang_thai_approval(pgd_ten, ds_nam, loai)
    cu["trang_thai"] = "da_nop"
    cu["ngay_nop"] = datetime.now().isoformat()
    cu["nguoi_nop"] = username
    cu["lan_nop"] = cu.get("lan_nop", 0) + 1
    db.ghi_kv(key, cu, username)
    db.ghi_audit(
        username, "nop_ke_hoach_xd",
        f"PGD: {pgd_ten} — {loai} {ds_nam[0]}–{ds_nam[-1]} — Lần {cu['lan_nop']}",
    )
    return True


def duyet_ke_hoach_xd(
    pgd_ten: str,
    ds_nam: list[int],
    loai: str,
    trang_thai_moi: str,
    y_kien: str,
    username: str,
) -> bool:
    """CN duyệt (da_duyet) hoặc trả lại (tu_choi) kế hoạch PGD."""
    key = f"khtd_xd_{loai}_status_{_slug(pgd_ten)}_{ds_nam[0]}"
    cu = doc_trang_thai_approval(pgd_ten, ds_nam, loai)
    cu["trang_thai"] = trang_thai_moi
    cu["ngay_duyet"] = datetime.now().isoformat()
    cu["nguoi_duyet"] = username
    cu["y_kien"] = y_kien
    db.ghi_kv(key, cu, username)
    db.ghi_audit(
        username, f"khtd_xd_{trang_thai_moi}",
        f"PGD: {pgd_ten} — {loai} — {y_kien[:80] if y_kien else 'Không có ý kiến'}",
    )
    return True


def mo_lai_ke_hoach(pgd_ten: str, ds_nam: list[int], loai: str, username: str) -> bool:
    """admin_cn mở lại kế hoạch đã duyệt → nhap_lieu."""
    key = f"khtd_xd_{loai}_status_{_slug(pgd_ten)}_{ds_nam[0]}"
    cu = doc_trang_thai_approval(pgd_ten, ds_nam, loai)
    cu["trang_thai"] = "nhap_lieu"
    cu["ngay_duyet"] = None
    cu["nguoi_duyet"] = ""
    db.ghi_kv(key, cu, username)
    db.ghi_audit(username, "mo_lai_ke_hoach_xd", f"PGD: {pgd_ten} — {loai}")
    return True


def trang_thai_approval_cn(ds_nam: list[int], loai: str) -> dict[str, dict]:
    """Trả về {pgd_ten: approval_dict} cho tất cả PGD."""
    nam_dau = ds_nam[0]
    prefix = f"khtd_xd_{loai}_status_"
    all_kv = db.doc_kv_prefix(prefix)
    result: dict[str, dict] = {}
    for pgd_ten in DS_PGD:
        key = f"{prefix}{_slug(pgd_ten)}_{nam_dau}"
        result[pgd_ten] = all_kv.get(key, dict(_DEFAULT_APPROVAL))
    return result


def is_khoa(pgd_ten: str, ds_nam: list[int], loai: str) -> bool:
    """Trả về True nếu kế hoạch đã được CN duyệt (da_duyet) — hard lock, không cho sửa.

    Chỉ admin_cn mới có thể mở lại qua `mo_lai_ke_hoach()`.
    """
    tt = doc_trang_thai_approval(pgd_ten, ds_nam, loai)
    return tt.get("trang_thai") == "da_duyet"


# ── Đọc Thuyết minh từ Biểu 02C (import) ─────────────────────────────────────

def doc_thuyet_minh_tu_bieu_02c(file_bytes: bytes) -> dict[str, float]:
    """Đọc phần C (XD00057–XD00074) từ KHNV_02C.XLSX → dict {key_noi_bo: float}."""
    df_raw = pd.read_excel(BytesIO(file_bytes), sheet_name=0, header=None, dtype=str)
    result: dict[str, float] = {}
    for _, row in df_raw.iterrows():
        ma = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        if ma not in BIEU_02C_THUYET_MINH_XD:
            continue
        key_noi_bo = BIEU_02C_THUYET_MINH_XD[ma]
        for col_idx in (3, 4, 5):
            try:
                val = row.iloc[col_idx]
                if pd.notna(val) and str(val).strip() not in ("", "nan", "None"):
                    fval = float(str(val).replace(",", "."))
                    if fval > 0:
                        result[key_noi_bo] = fval
                        break
            except (ValueError, IndexError):
                continue
    return result
