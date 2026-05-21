from __future__ import annotations

from datetime import date, datetime

import pandas as pd

import db
from data.pgd import pgd_slug
from logger import get_logger
from config import (
    COT_DU_NO_QH,
    COT_DVUT,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_NGAY_VAY,
    COT_SO_DU_TG,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    COT_MUC_VAY,
)

logger = get_logger(__name__)


def tinh_theo_dvut(df: pd.DataFrame, dvut_order: list[str] | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if COT_DVUT not in df.columns:
        return pd.DataFrame()

    agg: dict[str, tuple[str, str]] = {}
    if COT_TEN_TO in df.columns:
        agg["so_to"] = (COT_TEN_TO, "nunique")
    if COT_SO_KU in df.columns:
        agg["so_kh"] = (COT_SO_KU, "nunique")
    if COT_TONG_DU_NO in df.columns:
        agg["tong_dn"] = (COT_TONG_DU_NO, "sum")
    if COT_DU_NO_QH in df.columns:
        agg["nqh"] = (COT_DU_NO_QH, "sum")
    if COT_LAI_TON in df.columns:
        agg["lai_ton"] = (COT_LAI_TON, "sum")
    if not agg:
        return pd.DataFrame()

    t = df.groupby(COT_DVUT).agg(**agg).reset_index()
    if dvut_order:
        t["_ord"] = t[COT_DVUT].apply(lambda x: dvut_order.index(x) if x in dvut_order else 99)
        return t.sort_values("_ord").drop(columns="_ord")
    return t


def loc_mau06(df: pd.DataFrame, ngay_tu: str, ngay_den: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if COT_NGAY_VAY not in df.columns:
        return pd.DataFrame()

    ngay_vay = pd.to_datetime(df[COT_NGAY_VAY], errors="coerce")
    mask = (ngay_vay >= pd.Timestamp(ngay_tu)) & (ngay_vay <= pd.Timestamp(ngay_den))
    cols = [
        c
        for c in [
            COT_TEN_TO,
            COT_DVUT,
            COT_TEN_XA,
            COT_TEN_KH,
            COT_SO_KU,
            COT_TEN_CT,
            COT_NGAY_VAY,
            COT_MUC_VAY,
            COT_TONG_DU_NO,
            COT_DU_NO_QH,
            COT_LAI_TON,
        ]
        if c in df.columns
    ]
    result = df.loc[mask, cols].copy()
    if COT_NGAY_VAY in result.columns:
        return result.sort_values(COT_NGAY_VAY, ascending=False)
    return result


def loc_mau15(df: pd.DataFrame, ten_to: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if COT_TEN_TO not in df.columns:
        return pd.DataFrame()

    df_to = df[df[COT_TEN_TO] == ten_to].copy()
    if COT_LAI_TON in df_to.columns and COT_LAI_TON_QH in df_to.columns:
        df_to["Nợ lãi"] = df_to[COT_LAI_TON].fillna(0) + df_to[COT_LAI_TON_QH].fillna(0)
    elif COT_LAI_TON in df_to.columns:
        df_to["Nợ lãi"] = df_to[COT_LAI_TON].fillna(0)
    else:
        df_to["Nợ lãi"] = 0

    cols = [c for c in [COT_TEN_KH, COT_TEN_CT, COT_SO_KU, COT_TONG_DU_NO, "Nợ lãi", COT_SO_DU_TG] if c in df_to.columns or c == "Nợ lãi"]
    return df_to[cols].reset_index(drop=True)


def co_du_lieu_to(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    if COT_TEN_TO not in df.columns:
        return False
    s = df[COT_TEN_TO]
    if s is None:
        return False
    try:
        return s.dropna().astype(str).str.strip().replace("", pd.NA).dropna().size > 0
    except Exception as e:
        logger.error("co_du_lieu_to: lỗi kiểm tra cột Tổ — %s", e, exc_info=True)
        return False


def kv_key_bb_ct_cx(cap: str, scope: str | None, nam: int) -> str:
    kv_prefix = "ut_bbct" if cap == "tinh" else "ut_bbcx"
    slug = pgd_slug(scope) if scope else "cn"
    return f"{kv_prefix}_{slug}_{int(nam)}"


def doc_ds_bien_ban(kv_key: str) -> list[dict]:
    ds = db.doc_kv(kv_key) or []
    return ds if isinstance(ds, list) else []


def luu_bien_ban(kv_key: str, ds_hien_tai: list, record: dict, username: str) -> None:
    if not isinstance(ds_hien_tai, list):
        ds_hien_tai = []
    db.ghi_kv(kv_key, ds_hien_tai + [record], username)

    cap = record.get("loai_cap") or ("tinh" if record.get("loai") == "CT" else "xa")
    ten_don_vi = record.get("ten_don_vi", "")
    ngay_kt_raw = record.get("ngay_kt", "")
    ngay_kt_hien_thi = str(ngay_kt_raw or "")
    try:
        if isinstance(ngay_kt_raw, date):
            ngay_kt_hien_thi = ngay_kt_raw.strftime("%d/%m/%Y")
        elif isinstance(ngay_kt_raw, str) and ngay_kt_raw:
            ngay_kt_hien_thi = datetime.fromisoformat(ngay_kt_raw).strftime("%d/%m/%Y")
    except Exception:
        ngay_kt_hien_thi = str(ngay_kt_raw or "")
    loai_str = "bb_ct" if cap == "tinh" else "bb_cx"
    mau = "02/BB-CT" if cap == "tinh" else "03/BB-CX"
    db.ghi_audit(username, f"luu_{loai_str}", f"Mẫu {mau} — {ten_don_vi} ngày {ngay_kt_hien_thi}")


def doc_bien_ban_theo_nam(nam: int, pgd_user: str | None = None) -> list[dict]:
    nam_int = int(nam)
    all_records: list[dict] = []
    if pgd_user:
        slug = pgd_slug(pgd_user)
        for pref in ["ut_bbct", "ut_bbcx"]:
            recs = db.doc_kv(f"{pref}_{slug}_{nam_int}") or []
            if isinstance(recs, list):
                all_records.extend(recs)
        return all_records

    for pref in ["ut_bbct", "ut_bbcx"]:
        all_kv: dict = db.doc_kv_prefix(f"{pref}_") or {}
        for key, recs in all_kv.items():
            if key.endswith(f"_{nam_int}") and isinstance(recs, list):
                all_records.extend(recs)
    return all_records


def cap_nhat_trang_thai_bien_ban(
    kv_key: str,
    rec_id: str,
    ket_qua_xu_ly: str,
    username: str,
    ten_don_vi: str = "",
    ngay_cap_nhat: date | None = None,
) -> bool:
    ds_cur = db.doc_kv(kv_key) or []
    if not isinstance(ds_cur, list) or not rec_id:
        return False

    found = False
    ngay_cap_nhat = ngay_cap_nhat or date.today()
    updated: list[dict] = []
    for rec in ds_cur:
        if isinstance(rec, dict) and rec.get("id") == rec_id:
            found = True
            updated.append(
                {
                    **rec,
                    "trang_thai": "da_xu_ly",
                    "ket_qua_xu_ly": ket_qua_xu_ly,
                    "ngay_cap_nhat": ngay_cap_nhat.strftime("%Y-%m-%d"),
                    "nguoi_cap_nhat": username,
                }
            )
        else:
            updated.append(rec)

    if not found:
        return False

    db.ghi_kv(kv_key, updated, username)
    if ten_don_vi:
        db.ghi_audit(username, "cap_nhat_trang_thai_bb", f"ID {rec_id} — {ten_don_vi} → Đã xử lý")
    else:
        db.ghi_audit(username, "cap_nhat_trang_thai_bb", f"ID {rec_id} → Đã xử lý")
    return True

