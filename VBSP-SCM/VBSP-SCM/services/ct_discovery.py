"""
Quét 3 file hàng ngày → cập nhật registry chương trình theo PGD.
──────────────────────────────────────────────────────────────────
Hàm công khai:
  quet_va_ghi_chuong_trinh(username) — quét HSTD + GQVL + NQ11,
      ghi kv_store, trả về tóm tắt kết quả.
  doc_ct_registry(pgd)               — đọc registry từ kv_store.
  ghi_ct_registry(pgd, data, user)   — ghi/merge registry vào kv_store.
"""
import json
import os
from datetime import datetime
from typing import Any

import pandas as pd

import db
from config import (
    FILE_PATH, FILE_PATH_NQ11, FILE_PATH_GQVL,
    COT_TEN_PGD, COT_MA_CHUONG_TRINH, COT_TEN_CT, COT_NGUON_VON,
    COT_TONG_DU_NO, COT_DU_NO_TH, COT_SO_KU,
    COT_PL_NV, COT_MA_NDT,
    MA_NDT_CAP_TINH,
    CHUONG_TRINH_KHTD, TEN_CHINH_THUC_CT,
    DON_VI_CHI_NHANH, KV_KEY_CT_REGISTRY_ALL,
    GQVL_COT_MAP,
)

# ── Tiền tố key kv_store cho từng PGD ────────────────────────────────────────
_KV_PREFIX = "ct_registry_"

# ── Bảng tên hiển thị 2 nhóm GQVL ───────────────────────────────────────────
_GQVL_TEN_MAP: dict[str, str] = {
    "3_TW": "Cho vay giải quyết việc làm",
    "3_DP": "Cho vay giải quyết việc làm (ĐP)",
}
_GQVL_NV_INT: dict[str, int] = {
    "3_TW": 1, "3_DP": 2,
}

# ── Lookup nhanh: (ma_ct, nguon_von_int) → ma_key ────────────────────────────
# Xây từ CHUONG_TRINH_KHTD — bao gồm cả GQVL (ma_ct=3, xử lý chung)
_MA_KEY_LOOKUP: dict[tuple[int, int], str] = {}
for _mk, _mct, _ten, _nv, _match in CHUONG_TRINH_KHTD:
    _nv_int = 1 if _nv == "TW" else 2
    # Giữ mục đầu tiên nếu trùng (ma_ct, nguon_von)
    if (_mct, _nv_int) not in _MA_KEY_LOOKUP:
        _MA_KEY_LOOKUP[(_mct, _nv_int)] = _mk


# ── Slug helper (tái sử dụng logic từ data.pgd) ───────────────────────────────
def _slug(ten_pgd: str) -> str:
    """'PGD Long Thành' → 'pgd_long_thanh'."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFD", ten_pgd.strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 3 — Helper đọc/ghi kv_store
# ─────────────────────────────────────────────────────────────────────────────

def doc_ct_registry(pgd: str | None = None) -> dict:
    """
    Đọc registry chương trình từ kv_store.

    pgd=None  → đọc "ct_registry_all" (toàn hệ thống).
    pgd="PGD Long Thành" → đọc "ct_registry_{slug}".
    Trả về dict rỗng nếu chưa có dữ liệu.
    """
    key = KV_KEY_CT_REGISTRY_ALL if pgd is None else f"{_KV_PREFIX}{_slug(pgd)}"
    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM kv_store WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row["value"]) if row else {}
    except Exception:
        return {}


def ghi_ct_registry(pgd: str | None, data: dict, username: str) -> None:
    """
    Ghi registry chương trình vào kv_store, merge với dữ liệu cũ (không xóa).

    pgd=None → ghi vào "ct_registry_all".
    pgd="PGD Long Thành" → ghi vào "ct_registry_{slug}".
    Merge: dùng dict.update() — chương trình cũ không bị xóa khi upload lại.
    """
    key = KV_KEY_CT_REGISTRY_ALL if pgd is None else f"{_KV_PREFIX}{_slug(pgd)}"
    cu = doc_ct_registry(pgd)
    cu.update(data)
    try:
        with db.get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO kv_store
                   (key, value, updated_at, updated_by)
                   VALUES (?,?,?,?)""",
                (
                    key,
                    json.dumps(cu, ensure_ascii=False),
                    datetime.now().isoformat(),
                    username,
                ),
            )
            conn.commit()
    except Exception as e:
        raise RuntimeError(f"Không thể ghi ct_registry '{key}': {e}") from e


# ─────────────────────────────────────────────────────────────────────────────
# Helper đọc file trực tiếp (không qua @st.cache_data để tránh phụ thuộc context)
# ─────────────────────────────────────────────────────────────────────────────

def _doc_hstd_raw(fp: str) -> pd.DataFrame:
    """Đọc HSTD: sheet BCQUERY, header dòng 4, bỏ cột đầu + dòng NaN."""
    df = pd.read_excel(fp, sheet_name="BCQUERY", header=4, engine="openpyxl")
    return df.iloc[:, 1:].dropna(how="all").reset_index(drop=True)


def _doc_nq11_raw(fp: str) -> pd.DataFrame:
    """Đọc NQ11: sheet BCQUERY, header dòng 4, bỏ cột đầu + dòng NaN."""
    df = pd.read_excel(fp, sheet_name="BCQUERY", header=4, engine="openpyxl")
    return df.iloc[:, 1:].dropna(how="all").reset_index(drop=True)


def _doc_gqvl_raw(fp: str) -> pd.DataFrame:
    """Đọc GQVL: sheet Sheet1, header dòng 7, bỏ cột đầu + dòng đầu tiên sau header."""
    df = pd.read_excel(fp, sheet_name="Sheet1", header=7, engine="openpyxl")
    df = df.iloc[:, 1:].dropna(how="all").iloc[1:].reset_index(drop=True)
    return df.rename(columns=GQVL_COT_MAP)


# ─────────────────────────────────────────────────────────────────────────────
# Logic quét HSTD
# ─────────────────────────────────────────────────────────────────────────────

def _quet_hstd(
    df: pd.DataFrame,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """
    Quét HSTD: mỗi hàng dư nợ > 0 → entry registry.
    Bỏ qua ma_ct=6 (GQVL xử lý riêng).

    Trả về:
        registry_all    : { ma_key: entry }
        pgd_registries  : { ten_pgd: { ma_key: entry } }
    """
    registry_all: dict[str, Any] = {}
    pgd_registries: dict[str, dict[str, Any]] = {}

    # Ưu tiên cột tổng dư nợ, fallback sang dư nợ trong hạn
    col_du_no = COT_TONG_DU_NO if COT_TONG_DU_NO in df.columns else COT_DU_NO_TH

    for _, row in df.iterrows():
        du_no = pd.to_numeric(row.get(col_du_no, 0), errors="coerce")
        if not du_no or du_no <= 0:
            continue

        try:
            ma_ct = int(float(row.get(COT_MA_CHUONG_TRINH, None)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        try:
            nv_int = int(float(row.get(COT_NGUON_VON, None)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue

        ten_ct  = str(row.get(COT_TEN_CT, "")).strip()
        ten_pgd = str(row.get(COT_TEN_PGD, DON_VI_CHI_NHANH)).strip() or DON_VI_CHI_NHANH

        ma_key = _MA_KEY_LOOKUP.get((ma_ct, nv_int), f"{ma_ct}|{nv_int}")
        ten_chinh_thuc = TEN_CHINH_THUC_CT.get(ma_key, ten_ct)

        entry: dict[str, Any] = {
            "ma_ct":    ma_ct,
            "ten_ct":   ten_chinh_thuc,
            "nguon_von": nv_int,
            "pgd":      ten_pgd,
            "ma_key":   ma_key,
        }

        registry_all[ma_key] = entry
        pgd_registries.setdefault(ten_pgd, {})[ma_key] = entry

    return registry_all, pgd_registries


# ─────────────────────────────────────────────────────────────────────────────
# Logic phân tầng GQVL
# ─────────────────────────────────────────────────────────────────────────────

def _phan_tang_gqvl(row: pd.Series) -> str | None:
    """
    Xác định ma_key cho 1 dòng GQVL: 3_TW (Trung ương) hoặc 3_DP (Địa phương).

    Quy tắc:
        Nguồn vốn=1 (TW) → 3_TW
        Nguồn vốn=2 (ĐP) → 3_DP
    Trả về None nếu không xác định được nguồn vốn.
    """
    try:
        nv = int(float(row.get("Nguồn vốn", 0)))
    except (TypeError, ValueError):
        return None

    if nv == 1:
        return "3_TW"
    if nv == 2:
        return "3_DP"
    return None


def _quet_gqvl(
    df_gqvl: pd.DataFrame,
    df_hstd: pd.DataFrame,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, int]]:
    """
    Quét GQVL, join với HSTD để lấy Tên PGD, xác định 3_TW hoặc 3_DP.

    Trả về:
        registry_all    : { ma_key: entry }
        pgd_registries  : { ten_pgd: { ma_key: entry } }
        phan_tang_count : { "3_TW": N, "3_DP": N }
    """
    registry_all: dict[str, Any] = {}
    pgd_registries: dict[str, dict[str, Any]] = {}
    phan_tang_count: dict[str, int] = {"3_TW": 0, "3_DP": 0}

    # Tạo map Số khế ước → Tên PGD từ HSTD để join
    ku_col = "Số khế ước"
    if COT_TEN_PGD in df_hstd.columns and ku_col in df_hstd.columns:
        pgd_map: dict[Any, str] = (
            df_hstd[[ku_col, COT_TEN_PGD]]
            .drop_duplicates(subset=ku_col)
            .set_index(ku_col)[COT_TEN_PGD]
            .to_dict()
        )
    else:
        pgd_map = {}

    for _, row in df_gqvl.iterrows():
        mk = _phan_tang_gqvl(row)
        if mk is None:
            continue

        phan_tang_count[mk] = phan_tang_count.get(mk, 0) + 1

        so_ku   = row.get(ku_col, None)
        ten_pgd = str(pgd_map.get(so_ku, DON_VI_CHI_NHANH)).strip() or DON_VI_CHI_NHANH
        nv_int  = _GQVL_NV_INT[mk]

        entry: dict[str, Any] = {
            "ma_ct":    3,
            "ten_ct":   _GQVL_TEN_MAP[mk],
            "nguon_von": nv_int,
            "pgd":      ten_pgd,
            "ma_key":   mk,
        }

        registry_all[mk] = entry
        pgd_registries.setdefault(ten_pgd, {})[mk] = entry

    return registry_all, pgd_registries, phan_tang_count


# ─────────────────────────────────────────────────────────────────────────────
# Logic quét NQ11
# ─────────────────────────────────────────────────────────────────────────────

def _quet_nq11(
    df_nq11: pd.DataFrame,
    registry_all: dict[str, Any],
) -> dict[str, Any]:
    """
    Quét NQ11, bổ sung vào registry những chương trình chưa có từ HSTD/GQVL.
    Trả về dict các entry bổ sung mới.
    """
    bo_sung: dict[str, Any] = {}

    for _, row in df_nq11.iterrows():
        try:
            ma_ct = int(float(row.get(COT_MA_CHUONG_TRINH, None)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        try:
            nv_int = int(float(row.get(COT_NGUON_VON, None)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue

        ten_ct  = str(row.get(COT_TEN_CT, "")).strip()
        ten_pgd = str(row.get(COT_TEN_PGD, DON_VI_CHI_NHANH)).strip() or DON_VI_CHI_NHANH
        ma_key  = _MA_KEY_LOOKUP.get((ma_ct, nv_int), f"{ma_ct}|{nv_int}")

        if ma_key not in registry_all:
            bo_sung[ma_key] = {
                "ma_ct":    ma_ct,
                "ten_ct":   TEN_CHINH_THUC_CT.get(ma_key, ten_ct),
                "nguon_von": nv_int,
                "pgd":      ten_pgd,
                "ma_key":   ma_key,
                "nguon":    "NQ11",
            }

    return bo_sung


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 2 — Hàm chính
# ─────────────────────────────────────────────────────────────────────────────

def quet_va_ghi_chuong_trinh(username: str) -> dict:
    """
    Quét 3 file (HSTD, GQVL, NQ11) → ghi registry chương trình vào kv_store.
    Gọi ngay sau khi luu_3file_phong_khnv() lưu file xong.

    Xử lý lỗi độc lập: lỗi 1 file không ngăn xử lý 2 file còn lại.

    Trả về:
        {
            "tong_ct"       : int   — số chương trình unique trong registry_all,
            "pgd_stats"     : dict  — { ten_pgd: so_ct } số CT per PGD,
            "gqvl_phan_tang": dict  — { "6a_TW": N, "6b_TW": N, ... },
            "loi"           : list  — danh sách thông báo lỗi (nếu có),
        }
    """
    ket_qua: dict = {
        "tong_ct":        0,
        "pgd_stats":      {},
        "gqvl_phan_tang": {"6a_TW": 0, "6b_TW": 0, "6c_DP": 0, "6d_DP": 0},
        "loi":            [],
    }

    # ── 1. Đọc HSTD (bắt buộc — là cơ sở join cho GQVL) ─────────────────────
    df_hstd: pd.DataFrame | None = None
    try:
        if os.path.exists(FILE_PATH):
            df_hstd = _doc_hstd_raw(FILE_PATH)
    except Exception as e:
        ket_qua["loi"].append(f"Đọc HSTD lỗi: {e}")

    if df_hstd is None or df_hstd.empty:
        ket_qua["loi"].append("HSTD: không đọc được hoặc rỗng — dừng quét.")
        return ket_qua

    # ── 2. Quét HSTD ─────────────────────────────────────────────────────────
    registry_all, pgd_regs_hstd = _quet_hstd(df_hstd)

    # ── 3. Quét GQVL ─────────────────────────────────────────────────────────
    pgd_regs_gqvl: dict[str, dict] = {}
    try:
        if os.path.exists(FILE_PATH_GQVL):
            df_gqvl = _doc_gqvl_raw(FILE_PATH_GQVL)
            gqvl_all, pgd_regs_gqvl, phan_tang = _quet_gqvl(df_gqvl, df_hstd)
            registry_all.update(gqvl_all)
            ket_qua["gqvl_phan_tang"] = phan_tang
        else:
            ket_qua["loi"].append("GQVL: file chưa có — bỏ qua phân tầng GQVL.")
    except Exception as e:
        ket_qua["loi"].append(f"Quét GQVL lỗi: {e}")

    # ── 4. Quét NQ11 (bổ sung — không ghi đè registry đã có) ────────────────
    try:
        if os.path.exists(FILE_PATH_NQ11):
            df_nq11 = _doc_nq11_raw(FILE_PATH_NQ11)
            bo_sung = _quet_nq11(df_nq11, registry_all)
            registry_all.update(bo_sung)
        else:
            ket_qua["loi"].append("NQ11: file chưa có — bỏ qua bổ sung từ NQ11.")
    except Exception as e:
        ket_qua["loi"].append(f"Quét NQ11 lỗi: {e}")

    # ── 5. Gộp per-PGD registry (HSTD ← GQVL) ───────────────────────────────
    all_pgd_regs: dict[str, dict] = {}
    for ten_pgd, reg in pgd_regs_hstd.items():
        all_pgd_regs.setdefault(ten_pgd, {}).update(reg)
    for ten_pgd, reg in pgd_regs_gqvl.items():
        all_pgd_regs.setdefault(ten_pgd, {}).update(reg)

    # ── 6. Ghi kv_store từng PGD ─────────────────────────────────────────────
    for ten_pgd, reg in all_pgd_regs.items():
        try:
            ghi_ct_registry(ten_pgd, reg, username)
            ket_qua["pgd_stats"][ten_pgd] = len(reg)
        except Exception as e:
            ket_qua["loi"].append(f"Ghi PGD '{ten_pgd}' lỗi: {e}")

    # ── 7. Ghi ct_registry_all (toàn hệ thống) ───────────────────────────────
    try:
        ghi_ct_registry(None, registry_all, username)
    except Exception as e:
        ket_qua["loi"].append(f"Ghi registry_all lỗi: {e}")

    ket_qua["tong_ct"] = len(registry_all)

    # ── 8. Lưu tóm tắt kết quả vào kv_store (để UI đọc lại mà không cần quét lại) ──
    try:
        with db.get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO kv_store
                   (key, value, updated_at, updated_by)
                   VALUES (?,?,?,?)""",
                (
                    "ct_discovery_last_result",
                    json.dumps(ket_qua, ensure_ascii=False),
                    datetime.now().isoformat(),
                    username,
                ),
            )
            conn.commit()
    except Exception:
        pass

    # ── 9. Audit ──────────────────────────────────────────────────────────────
    db.ghi_audit(
        username,
        "quet_va_ghi_chuong_trinh",
        (
            f"tong_ct={ket_qua['tong_ct']}, "
            f"so_pgd={len(all_pgd_regs)}, "
            f"gqvl={ket_qua['gqvl_phan_tang']}, "
            f"loi={len(ket_qua['loi'])}"
        ),
    )

    return ket_qua


def doc_ket_qua_quet_cuoi() -> dict:
    """
    Đọc kết quả lần quét gần nhất từ kv_store.
    Dùng trong UI để hiển thị kết quả mà không cần quét lại.
    Trả về dict rỗng nếu chưa từng quét.
    """
    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM kv_store WHERE key='ct_discovery_last_result'"
            ).fetchone()
        return json.loads(row["value"]) if row else {}
    except Exception:
        return {}
