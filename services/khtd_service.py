"""
Dịch vụ KHTD — Giao KHTD & Điều chỉnh KHTD: Google Sheet, kv_store, duyệt, lũy kế đợt.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

import pandas as pd

import db
from logger import get_logger
from config import (
    CHUONG_TRINH_KHTD,
    DCGIAM_CRED_FILE,
    DCGIAM_SHEET_ID,
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_TONG_DU_NO,
    COT_TEN_PGD,
    DS_PGD,
    DON_VI_CHI_NHANH,
    GQVL_MA_KEY_GIAO,
    PGD_XA_MAP,
)
from data.pgd import pgd_slug as _pgd_slug
from services.upload_service import KetQuaUpload

logger = get_logger(__name__)

LOAI_GIAO = "giao"
LOAI_DIEU_CHINH = "dieu_chinh"

_LOOKUP_MA_KEY: dict[tuple[int, int], str] = {}
for _mk, _mct, _ten, _nv, _match in CHUONG_TRINH_KHTD:
    _nv_int = 1 if _nv == "TW" else 2
    if (_mct, _nv_int) not in _LOOKUP_MA_KEY:
        _LOOKUP_MA_KEY[(_mct, _nv_int)] = _mk


def ghi_kv_va_audit(
    key: str,
    value,
    *,
    username: str,
    action: str,
    mo_ta: str,
) -> None:
    db.ghi_kv(key, value, username)
    db.ghi_audit(username, action, mo_ta)


def _action_luu_khtd_from_key(key: str) -> str:
    if key == "khtd_cn":
        return "luu_khtd_cn"
    if key == "khtd_xa":
        return "luu_khtd_cn"
    if key.startswith("khtd_ap_"):
        return "luu_khtd_mau07"
    return "luu_kv"


def luu_khtd_dict(key: str, data: dict, username: str) -> None:
    action = _action_luu_khtd_from_key(key)
    ghi_kv_va_audit(
        key,
        data,
        username=username,
        action=action,
        mo_ta=f"key={key}, {len(data)} items",
    )


def _slug_text(text: str) -> str:
    s = unicodedata.normalize("NFD", str(text or "").strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def kv_key_mau07(pgd: str, xa: str) -> tuple[str, str]:
    pgd_s = _slug_text(pgd)
    xa_s = _slug_text(xa)
    return f"khtd_ap_{pgd_s}_{xa_s}", f"khtd_ap_lich_su_{pgd_s}_{xa_s}"


def _sync_khtd_xa_from_ap(xa: str, data_ap: dict, username: str) -> None:
    kv_xa = db.doc_kv("khtd_xa")
    kv_xa = kv_xa if isinstance(kv_xa, dict) else {}
    tong: dict[str, float] = {}
    for composite, gia_tri in data_ap.items():
        parts = str(composite).split("|", 1)
        if len(parts) != 2:
            continue
        mk = parts[1]
        k = f"{xa}|{mk}"
        tong[k] = round(tong.get(k, 0.0) + float(gia_tri), 1)
    kv_xa.update(tong)
    ghi_kv_va_audit(
        "khtd_xa",
        kv_xa,
        username=username,
        action="luu_khtd_mau07",
        mo_ta=f"sync khtd_xa — Xã: {xa} ({len(tong)} items)",
    )


def luu_khtd_mau07(
    *,
    pgd: str,
    xa: str,
    data_nhap: dict,
    lich_su_moi: list,
    username: str,
    loai_van_ban: str,
    lan_moi: int,
) -> None:
    kv_key_ht, kv_key_ls = kv_key_mau07(pgd, xa)
    ghi_kv_va_audit(
        kv_key_ht,
        data_nhap,
        username=username,
        action="luu_khtd_mau07",
        mo_ta=f"{loai_van_ban} lần {lan_moi} — {xa} ({pgd}) — data",
    )
    ghi_kv_va_audit(
        kv_key_ls,
        lich_su_moi,
        username=username,
        action="luu_khtd_mau07",
        mo_ta=f"{loai_van_ban} lần {lan_moi} — {xa} ({pgd}) — lịch sử",
    )
    _sync_khtd_xa_from_ap(xa, data_nhap, username)


def _get_sheet_client() -> Any:
    import gspread

    return gspread.service_account(filename=DCGIAM_CRED_FILE)


def _so_trieu_tu_oa(x: Any) -> float:
    if x is None:
        return 0.0
    s = str(x).strip().replace(",", "").replace(" ", "")
    if not s or s.lower() == "nan":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _kv_key(pgd_slug: str, nam: str | int, thang: str | int, dot: str | int) -> str:
    th = str(thang).strip().zfill(2)
    return f"khtd_{pgd_slug}_{nam}_{th}_{dot}"


def kv_key_dot(
    pgd_slug_s: str, nam: str | int, thang: str | int, dot: str | int
) -> str:
    """Khóa kv_store cho một đợt KHTD (dùng từ tab)."""
    return _kv_key(pgd_slug_s, nam, thang, dot)


def _parse_key_suffix(rest: str) -> tuple[int, str, str] | None:
    m = re.match(r"^(\d{4})_(\d{2})_(.+)$", rest.strip())
    if not m:
        return None
    return int(m.group(1)), m.group(2), m.group(3)


def _dot_sort_key(dot: str) -> tuple[int | str, ...]:
    s = str(dot).strip()
    m = re.match(r"(?i)dot\s*(\d+)$", s)
    if m:
        return (0, int(m.group(1)))
    return (1, s.lower())


def ds_slug() -> list[str]:
    return ["hoi_so"] + [_pgd_slug(ten) for ten in DS_PGD]


def lay_dot_truoc(
    pgd_slug: str,
    nam: str | int,
    thang: str | int,
    dot: str | int,
) -> dict | None:
    prefix = f"khtd_{pgd_slug}_"
    all_kv = db.doc_kv_prefix(prefix)
    cur_tuple = (
        int(str(nam)),
        str(thang).strip().zfill(2),
        _dot_sort_key(str(dot)),
    )
    parsed: list[tuple[tuple[Any, ...], str]] = []
    for k in all_kv:
        if not k.startswith(prefix):
            continue
        suf = k[len(prefix) :]
        p = _parse_key_suffix(suf)
        if not p:
            continue
        na_k, th_k, dot_k = p
        sort_t = (na_k, th_k, _dot_sort_key(dot_k))
        parsed.append((sort_t, k))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    candidates = [t for t in parsed if t[0] < cur_tuple]
    if not candidates:
        return None
    _, best_key = max(candidates, key=lambda x: x[0])
    raw = all_kv.get(best_key)
    if raw is None:
        raw = db.doc_kv(best_key)
    return raw if isinstance(raw, dict) else None


def lay_kh_dot_truoc(
    pgd_slug: str,
    nam: str | int,
    thang: str | int,
    dot: str | int,
) -> dict[str, dict[str, float]]:
    raw = lay_dot_truoc(pgd_slug, nam, thang, dot)
    if raw is None:
        return {}
    out: dict[str, dict[str, float]] = {}
    for item in raw.get("du_lieu", []):
        if not isinstance(item, dict):
            continue
        ma_key = str(item.get("ma_key", "") or "")
        if not ma_key:
            continue
        out[ma_key] = {
            "kh_moi_tw": float(item.get("kh_moi_tw") or 0),
            "kh_moi_dp": float(item.get("kh_moi_dp") or 0),
        }

    if not out.get("3_TW_NHCSXH") and out.get("3_TW"):
        val = float(out["3_TW"].get("kh_moi_tw", 0)) / 2
        out.setdefault("3_TW_NHCSXH", {"kh_moi_tw": val, "kh_moi_dp": 0.0})
        out.setdefault("3_TW_NSNN", {"kh_moi_tw": val, "kh_moi_dp": 0.0})
    if not out.get("3_DP_TINH") and out.get("3_DP"):
        val = float(out["3_DP"].get("kh_moi_dp", 0))
        out.setdefault("3_DP_TINH", {"kh_moi_tw": 0.0, "kh_moi_dp": val})

    return out


def tinh_kh_dau_nam(
    df_hstd: pd.DataFrame | None = None,
    *,
    parquet_path: str | None = None,
    ten_pgd: str | None = None,
) -> dict[str, dict[str, float]]:
    """
    Tổng dư nợ HSTD theo ma_key (VND). Thiếu cột → {}.

    Ưu tiên parquet_path: DuckDB đọc thẳng từ file, lọc PGD ngay trong SQL.
    Fallback df_hstd: DuckDB query trên in-memory DataFrame.
    """
    import duckdb

    try:
        if parquet_path:
            where_parts = [
                f'"{COT_MA_CHUONG_TRINH}" IS NOT NULL',
                f'"{COT_NGUON_VON}" IS NOT NULL',
            ]
            params: list = []
            if ten_pgd:
                where_parts.append(f'"{COT_TEN_PGD}" = ?')
                params.append(ten_pgd)
            sql = f"""
                SELECT
                    TRY_CAST("{COT_MA_CHUONG_TRINH}" AS INTEGER) AS ma_ct,
                    TRY_CAST("{COT_NGUON_VON}"        AS INTEGER) AS nv,
                    SUM(COALESCE(TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE), 0)) AS tong_vnd
                FROM read_parquet('{parquet_path}')
                WHERE {" AND ".join(where_parts)}
                GROUP BY ma_ct, nv
            """
            rows = duckdb.execute(sql, params).fetchall()
        else:
            if df_hstd is None or df_hstd.empty:
                return {}
            missing = {COT_MA_CHUONG_TRINH, COT_NGUON_VON, COT_TONG_DU_NO} - set(df_hstd.columns)
            if missing:
                return {}
            con = duckdb.connect()
            con.register("t", df_hstd)
            sql = f"""
                SELECT
                    TRY_CAST("{COT_MA_CHUONG_TRINH}" AS INTEGER) AS ma_ct,
                    TRY_CAST("{COT_NGUON_VON}"        AS INTEGER) AS nv,
                    SUM(COALESCE(TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE), 0)) AS tong_vnd
                FROM t
                WHERE "{COT_MA_CHUONG_TRINH}" IS NOT NULL
                  AND "{COT_NGUON_VON}" IS NOT NULL
                GROUP BY ma_ct, nv
            """
            rows = con.execute(sql).fetchall()

        out: dict[str, dict[str, float]] = {}
        for ma_ct, nv, tong_vnd in rows:
            if ma_ct is None or nv is None:
                continue
            mk = _LOOKUP_MA_KEY.get((int(ma_ct), int(nv)))
            if not mk:
                continue
            if mk not in out:
                out[mk] = {"kh_moi_tw": 0.0, "kh_moi_dp": 0.0}
            if int(nv) == 1:
                out[mk]["kh_moi_tw"] += float(tong_vnd or 0.0)
            elif int(nv) == 2:
                out[mk]["kh_moi_dp"] += float(tong_vnd or 0.0)
        return out
    except Exception as exc:
        logger.error("tinh_kh_dau_nam: lỗi tổng hợp dư nợ HSTD — %s", exc, exc_info=True)
        return {}


def doc_tu_sheet(pgd_slug: str) -> tuple[list[dict], list[str]]:
    """
    Đọc tab Google Sheet trùng tên pgd_slug; dữ liệu từ hàng 3 (bỏ 2 hàng header).
    Validate: dc_tw/dc_dp ≠ 0 phải có ly_do.
    """
    du_lieu_hop_le: list[dict] = []
    danh_sach_loi: list[str] = []

    try:
        client = _get_sheet_client()
        sh = client.open_by_key(DCGIAM_SHEET_ID)
        ws = sh.worksheet(pgd_slug)
        rows = ws.get_values()
    except Exception as e:
        err = f"[{pgd_slug}] Không đọc được Sheet: {e}"
        return [], [err]

    for i, row in enumerate(rows[2:], start=3):

        def _c(idx: int) -> str:
            return str(row[idx]).strip() if len(row) > idx and row[idx] is not None else ""

        xa = _c(1)
        ma_key = _c(2)
        if not ma_key:
            continue

        ten_ct = _c(3)
        nguon = _c(4)
        kh_tw = _so_trieu_tu_oa(_c(5) if len(row) > 5 else "")
        dc_tw = _so_trieu_tu_oa(_c(6) if len(row) > 6 else "")
        kh_moi_tw = _so_trieu_tu_oa(_c(7) if len(row) > 7 else "")
        kh_dp = _so_trieu_tu_oa(_c(8) if len(row) > 8 else "")
        dc_dp = _so_trieu_tu_oa(_c(9) if len(row) > 9 else "")
        kh_moi_dp = _so_trieu_tu_oa(_c(10) if len(row) > 10 else "")
        ly_do = _c(11)

        if (dc_tw != 0 or dc_dp != 0) and not ly_do:
            danh_sach_loi.append(
                f"Hàng {i} · ma_key={ma_key}: có điều chỉnh (dc_tw/dc_dp) "
                f"nhưng thiếu lý do."
            )
            continue

        du_lieu_hop_le.append(
            {
                "xa": xa,
                "ma_key": ma_key,
                "ten_ct": ten_ct,
                "nguon": nguon,
                "kh_tw": kh_tw,
                "dc_tw": dc_tw,
                "kh_moi_tw": kh_moi_tw,
                "kh_dp": kh_dp,
                "dc_dp": dc_dp,
                "kh_moi_dp": kh_moi_dp,
                "ly_do": ly_do,
            }
        )

    return du_lieu_hop_le, danh_sach_loi


def _du_lieu_chuyen_trieu_sang_vnd(_loai: str, du_lieu: list[dict]) -> list[dict]:
    """
    Quy đổi triệu → VND (kh_tw, kh_dp, dc_tw, dc_dp), rồi
    kh_moi_tw = kh_tw + dc_tw, kh_moi_dp = kh_dp + dc_dp (đơn vị VND).
    """
    out: list[dict] = []
    for r in du_lieu:
        d = dict(r)
        ktw = float(d.get("kh_tw") or 0)
        kdp = float(d.get("kh_dp") or 0)
        dtw = float(d.get("dc_tw") or 0)
        ddp = float(d.get("dc_dp") or 0)
        ktw_v = ktw * 1_000_000
        kdp_v = kdp * 1_000_000
        dtw_v = dtw * 1_000_000
        ddp_v = ddp * 1_000_000
        d["kh_tw"] = ktw_v
        d["kh_dp"] = kdp_v
        d["dc_tw"] = dtw_v
        d["dc_dp"] = ddp_v
        d["kh_moi_tw"] = ktw_v + dtw_v
        d["kh_moi_dp"] = kdp_v + ddp_v
        out.append(d)
    return out


def luu_dot(
    pgd_slug: str,
    nam: str | int,
    thang: str | int,
    dot: str | int,
    loai: str,
    du_lieu: list[dict],
    username: str,
) -> KetQuaUpload:
    key = _kv_key(pgd_slug, nam, thang, dot)
    try:
        du_lieu_vnd = _du_lieu_chuyen_trieu_sang_vnd(loai, du_lieu)
        payload = {
            "loai": loai,
            "du_lieu": du_lieu_vnd,
            "timestamp": datetime.now().isoformat(),
            "trang_thai": "cho_duyet",
        }
        db.ghi_kv(key, payload, username)
        db.ghi_audit(
            username,
            "luu_dot_khtd",
            f"PGD: {pgd_slug} · {nam}/{thang}/{dot} · loai={loai} · {len(du_lieu)} dòng",
        )
        return KetQuaUpload(
            True,
            f"✅ Đã lưu KHTD — {pgd_slug} · năm {nam} · tháng {thang} · đợt {dot} · "
            f"{len(du_lieu)} dòng (chờ duyệt).",
            key,
        )
    except Exception as e:
        msg = f"❌ Lưu KHTD thất bại: {e}"
        db.ghi_audit(username, "luu_dot_khtd_error", f"{key} · {e}")
        return KetQuaUpload(False, msg, "")


def push_kh_len_sheet(
    pgd_slug: str,
    nam: str | int,
    thang: str | int,
    dot: str | int,
    username: str,
) -> KetQuaUpload:
    kh_truoc = lay_kh_dot_truoc(pgd_slug, nam, thang, dot)
    try:
        client = _get_sheet_client()
        sh = client.open_by_key(DCGIAM_SHEET_ID)
        ws = sh.worksheet(pgd_slug)
        rows = ws.get_values()
    except Exception as e:
        msg = f"❌ Không mở được Sheet: {e}"
        db.ghi_audit(username, "push_khtd_sheet_loi", f"{pgd_slug} · {e}")
        return KetQuaUpload(False, msg, "")

    data_rows = rows[4:] if len(rows) > 4 else []
    updates: list[Any] = []
    for ri, row in enumerate(data_rows, start=5):

        def _gc(idx: int) -> str:
            return (
                str(row[idx]).strip()
                if len(row) > idx and row[idx] is not None
                else ""
            )

        ma_key = _gc(2)
        if not ma_key:
            continue
        if ma_key.startswith("3_") and ma_key not in GQVL_MA_KEY_GIAO:
            continue
        nguon = _gc(4).strip().upper()
        kh_prev = kh_truoc.get(ma_key, {})
        if nguon == "TW":
            val = float(kh_prev.get("kh_moi_tw", 0) or 0) / 1_000_000
            col_letter = "F"
        elif nguon == "DP":
            val = float(kh_prev.get("kh_moi_dp", 0) or 0) / 1_000_000
            col_letter = "I"
        else:
            continue
        updates.append({"range": f"{col_letter}{ri}", "values": [[val if val != 0 else ""]]})

    try:
        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
        db.ghi_audit(
            username,
            "push_khtd_kh_giao",
            f"{pgd_slug} · {nam}/{thang}/{dot} · {len(updates)} ô",
        )
        return KetQuaUpload(
            True,
            f"✅ Đã đẩy KH giao (F/I) — {pgd_slug} · {len(updates)} ô.",
            pgd_slug,
        )
    except Exception as e:
        msg = f"❌ Ghi Sheet thất bại: {e}"
        db.ghi_audit(username, "push_khtd_sheet_error", str(e))
        return KetQuaUpload(False, msg, "")


def _slug_to_ten_dv(slug: str) -> str:
    if slug == "hoi_so":
        return DON_VI_CHI_NHANH
    for ten in DS_PGD:
        if _pgd_slug(ten) == slug:
            return ten
    return slug


def _tai_va_luu_pgd_co_loi(
    pgd_slug: str,
    nam: str | int,
    thang: str | int,
    dot: str | int,
    username: str,
) -> tuple[KetQuaUpload, list[str]]:
    du_lieu, loi_sheet = doc_tu_sheet(pgd_slug)
    if (
        not du_lieu
        and len(loi_sheet) == 1
        and "Không đọc được Sheet" in loi_sheet[0]
    ):
        kq = KetQuaUpload(False, loi_sheet[0], "")
        db.ghi_audit(username, "tai_khtd_doc_loi", f"{pgd_slug} · {loi_sheet[0][:200]}")
        return kq, loi_sheet

    kq = luu_dot(
        pgd_slug,
        nam,
        thang,
        dot,
        LOAI_DIEU_CHINH,
        du_lieu,
        username,
    )
    if loi_sheet:
        loi_txt = "\n".join(loi_sheet)
        thong_bao = (
            f"{kq.thong_bao}\n\n⚠️ **Lỗi validate ({len(loi_sheet)}):**\n{loi_txt}"
        )
        kq = KetQuaUpload(kq.thanh_cong, thong_bao, kq.duong_dan)
    return kq, loi_sheet


def tai_va_luu_pgd(
    pgd_slug: str,
    nam: str | int,
    thang: str | int,
    dot: str | int,
    username: str,
) -> KetQuaUpload:
    kq, _ = _tai_va_luu_pgd_co_loi(pgd_slug, nam, thang, dot, username)
    return kq


def tai_tat_ca(
    nam: str | int,
    thang: str | int,
    dot: str | int,
    username: str,
) -> dict[str, str]:
    ket_qua: dict[str, str] = {}
    for slug in ds_slug():
        try:
            kq, loi_sheet = _tai_va_luu_pgd_co_loi(slug, nam, thang, dot, username)
            if loi_sheet:
                ket_qua[slug] = f"{len(loi_sheet)} lỗi"
            elif kq.thanh_cong:
                ket_qua[slug] = "ok"
            else:
                ket_qua[slug] = (kq.thong_bao or "")[:200] if kq.thong_bao else "lỗi"
        except Exception as e:
            ket_qua[slug] = str(e)[:200]
            db.ghi_audit(username, "tai_khtd_pgd_error", f"{slug} · {e}")

    try:
        import streamlit as st

        st.cache_data.clear()
    except ImportError:
        pass

    db.ghi_audit(username, "tai_khtd_tat_ca", f"{nam}/{thang}/{dot}")
    return ket_qua


def tong_hop(nam: str | int, thang: str | int, dot: str | int) -> pd.DataFrame:
    cols = [
        "pgd_slug",
        "xa",
        "ma_key",
        "ten_ct",
        "nguon",
        "loai",
        "kh_tw",
        "dc_tw",
        "kh_moi_tw",
        "kh_dp",
        "dc_dp",
        "kh_moi_dp",
        "ly_do",
    ]
    rows: list[dict] = []
    for pgd_s in ds_slug():
        key = _kv_key(pgd_s, nam, thang, dot)
        raw = db.doc_kv(key)
        if not raw or not isinstance(raw, dict):
            continue
        loai = raw.get("loai") or ""
        for item in raw.get("du_lieu") or []:
            if not isinstance(item, dict):
                continue
            row = {"pgd_slug": pgd_s, "loai": loai}
            for c in (
                "xa",
                "ma_key",
                "ten_ct",
                "nguon",
                "kh_tw",
                "dc_tw",
                "kh_moi_tw",
                "kh_dp",
                "dc_dp",
                "kh_moi_dp",
                "ly_do",
            ):
                row[c] = item.get(c)
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def kiem_tra_can_bang(nam: str | int, thang: str | int, dot: str | int) -> dict:
    df = tong_hop(nam, thang, dot)
    if df.empty:
        return {}
    df = df[df["loai"] == LOAI_DIEU_CHINH]
    if df.empty:
        return {}

    out: dict = {}
    for ma_key, g in df.groupby("ma_key"):
        mk = str(ma_key)
        tong_dc_tw = float(g["dc_tw"].fillna(0).sum())
        tong_dc_dp = float(g["dc_dp"].fillna(0).sum())
        out[mk] = {
            "tong_dc_tw": tong_dc_tw,
            "tong_dc_dp": tong_dc_dp,
            "can_bang": abs(tong_dc_tw) <= 1_000_000
            and abs(tong_dc_dp) <= 1_000_000,
        }
    return out


def duyet(
    pgd_slug: str,
    nam: str | int,
    thang: str | int,
    dot: str | int,
    trang_thai: str,
    y_kien: str,
    username: str,
) -> None:
    if trang_thai not in ("da_duyet", "tu_choi"):
        db.ghi_audit(
            username,
            "duyet_khtd_invalid",
            f"trang_thai={trang_thai!r} · {pgd_slug} · {nam}/{thang}/{dot}",
        )
        return

    key = _kv_key(pgd_slug, nam, thang, dot)
    hien_tai = db.doc_kv(key)
    if not hien_tai or not isinstance(hien_tai, dict):
        db.ghi_audit(username, "duyet_khtd_missing", f"Không có dữ liệu · {key}")
        return

    cap_nhat = dict(hien_tai)
    cap_nhat["trang_thai"] = trang_thai
    cap_nhat["y_kien_duyet"] = y_kien
    cap_nhat["nguoi_duyet"] = username
    cap_nhat["thoi_gian_duyet"] = datetime.now().isoformat()

    db.ghi_kv(key, cap_nhat, username)
    db.ghi_audit(
        username,
        "duyet_khtd",
        f"{pgd_slug} · {nam}/{thang}/{dot} · {trang_thai} · {y_kien[:120]}",
    )


def tao_dot_giao_dau_nam(
    nam: int,
    username: str,
    df_hstd: pd.DataFrame | None = None,
    *,
    parquet_path: str | None = None,
) -> dict[str, KetQuaUpload]:
    kh_base = tinh_kh_dau_nam(df_hstd, parquet_path=parquet_path)
    loi_chung = KetQuaUpload(
        False,
        "❌ Không tính được KH đầu năm từ HSTD (thiếu cột hoặc không có dữ liệu).",
        "",
    )
    if not kh_base:
        out = {slug: loi_chung for slug in ds_slug()}
        try:
            import streamlit as st

            st.cache_data.clear()
        except ImportError:
            pass
        return out

    ket_qua: dict[str, KetQuaUpload] = {}
    for slug in ds_slug():
        ten_pgd = _slug_to_ten_dv(slug)
        ds_xa = PGD_XA_MAP.get(ten_pgd, [])
        du_lieu: list[dict] = []
        for xa in ds_xa:
            for ma_key, _ma_ct, ten_ct, nguon, _ten_match in CHUONG_TRINH_KHTD:
                if ma_key.startswith("3_") and ma_key not in GQVL_MA_KEY_GIAO:
                    continue
                kh_prev = kh_base.get(ma_key, {})
                tw_vnd = float(kh_prev.get("kh_moi_tw") or 0)
                dp_vnd = float(kh_prev.get("kh_moi_dp") or 0)
                tw_trieu = tw_vnd / 1_000_000
                dp_trieu = dp_vnd / 1_000_000
                du_lieu.append(
                    {
                        "xa": xa,
                        "ma_key": ma_key,
                        "ten_ct": ten_ct,
                        "nguon": nguon,
                        "kh_tw": tw_trieu,
                        "dc_tw": 0.0,
                        "kh_moi_tw": tw_trieu,
                        "kh_dp": dp_trieu,
                        "dc_dp": 0.0,
                        "kh_moi_dp": dp_trieu,
                        "ly_do": "",
                    }
                )
        ket_qua[slug] = luu_dot(
            slug,
            nam,
            "01",
            "Dot1",
            LOAI_GIAO,
            du_lieu,
            username,
        )

    try:
        import streamlit as st

        st.cache_data.clear()
    except ImportError:
        pass
    return ket_qua
