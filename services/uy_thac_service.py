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
    COT_TEN_PGD,
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

    df_src = df.copy()
    for col in [COT_DVUT, COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO, COT_SO_KU]:
        if col in df_src.columns:
            try:
                s = df_src[col].astype("string").str.strip()
                df_src[col] = s.replace("", pd.NA)
            except Exception:
                df_src[col] = df_src[col]

    for col in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON]:
        if col in df_src.columns:
            df_src[col] = pd.to_numeric(df_src[col], errors="coerce").fillna(0)

    out_parts: list[pd.Series] = []

    if COT_TEN_TO in df_src.columns:
        if COT_TEN_PGD in df_src.columns and COT_TEN_XA in df_src.columns:
            dims = [COT_DVUT, COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO]
        elif COT_TEN_PGD in df_src.columns:
            dims = [COT_DVUT, COT_TEN_PGD, COT_TEN_TO]
        elif COT_TEN_XA in df_src.columns:
            dims = [COT_DVUT, COT_TEN_XA, COT_TEN_TO]
        else:
            dims = [COT_DVUT, COT_TEN_TO]
        so_to = (
            df_src[dims]
            .dropna(subset=[COT_DVUT, COT_TEN_TO])
            .drop_duplicates()
            .groupby(COT_DVUT)
            .size()
            .rename("so_to")
        )
        out_parts.append(so_to)

    if COT_SO_KU in df_src.columns:
        out_parts.append(df_src.groupby(COT_DVUT)[COT_SO_KU].nunique().rename("so_kh"))

    if COT_TONG_DU_NO in df_src.columns:
        out_parts.append(df_src.groupby(COT_DVUT)[COT_TONG_DU_NO].sum().rename("tong_dn"))
    if COT_DU_NO_QH in df_src.columns:
        out_parts.append(df_src.groupby(COT_DVUT)[COT_DU_NO_QH].sum().rename("nqh"))
    if COT_LAI_TON in df_src.columns:
        out_parts.append(df_src.groupby(COT_DVUT)[COT_LAI_TON].sum().rename("lai_ton"))

    if not out_parts:
        return pd.DataFrame()

    t = pd.concat(out_parts, axis=1).reset_index()
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
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
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


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER PAYLOAD FUNCTIONS — Thuần, không đụng UI
# ══════════════════════════════════════════════════════════════════════════════

def build_payload_ke_hoach(
    don_vi_kt: str, so_vb: str, dia_danh: str,
    nam_kh: int, ngay_ky: date, chu_tich: str,
    muc_dich: str, yeu_cau: str, noi_dung_kt: str,
    thanh_phan: str, noi_dung_gs: str, phan_cong_gs: str,
    to_chuc: str, ds_to: list,
) -> tuple[dict, str]:
    context = {
        "don_vi_kt": don_vi_kt, "so_vb": so_vb,
        "dia_danh": dia_danh, "nam_kh": nam_kh,
        "ngay_ky": ngay_ky.strftime("%d/%m/%Y"),
        "ngay": ngay_ky.day, "thang": ngay_ky.month, "nam": ngay_ky.year,
        "muc_dich": muc_dich, "yeu_cau": yeu_cau,
        "noi_dung_kt": noi_dung_kt, "thanh_phan": thanh_phan,
        "noi_dung_gs": noi_dung_gs, "phan_cong_gs": phan_cong_gs,
        "to_chuc": to_chuc, "chu_tich": chu_tich,
        "so_to": len(ds_to), "ds_to": ds_to,
        "ngay_ky": ngay_ky,
    }
    ten_file = (
        f"KH_KiemTra_UyThac_{nam_kh}_"
        f"{don_vi_kt[:20].replace(' ','_')}"
    )
    return context, ten_file


def build_payload_mau06(
    don_vi_kt: str, ten_xa: str, ten_to: str,
    can_bo_1: str, chuc_vu_1: str, can_bo_2: str, chuc_vu_2: str,
    dia_ban: str, ngay_kt: date,
    nhan_xet_chung: str,
    so_kh_dung: str, so_tien_dung: str, ty_trong_dung: str,
    so_kh_sai: str, so_tien_sai: str, ty_trong_sai: str,
    bien_phap: str,
    df_m06: pd.DataFrame, pgd_scope: str,
) -> tuple[dict, pd.DataFrame, str]:
    df_xuat = df_m06.copy()
    if ten_to and COT_TEN_TO in df_xuat.columns:
        df_xuat = df_xuat[df_xuat[COT_TEN_TO] == ten_to]
    if COT_LAI_TON in df_xuat.columns and COT_LAI_TON_QH in df_xuat.columns:
        df_xuat["Nợ lãi"] = df_xuat[COT_LAI_TON].fillna(0) + df_xuat[COT_LAI_TON_QH].fillna(0)
    du_lieu_word = {
        "don_vi_kt": don_vi_kt,
        "ten_xa": ten_xa, "ten_to": ten_to,
        "can_bo_1": can_bo_1, "chuc_vu_1": chuc_vu_1,
        "can_bo_2": can_bo_2, "chuc_vu_2": chuc_vu_2,
        "dia_ban": dia_ban, "ngay_kt": ngay_kt,
        "nhan_xet_chung": nhan_xet_chung,
        "so_kh_dung": so_kh_dung, "so_tien_dung": so_tien_dung,
        "ty_trong_dung": ty_trong_dung,
        "so_kh_sai": so_kh_sai, "so_tien_sai": so_tien_sai,
        "ty_trong_sai": ty_trong_sai,
        "bien_phap": bien_phap,
    }
    slug = pgd_slug(pgd_scope) if pgd_scope else "cn"
    ten_file = f"Mau06TD_{slug}_{ngay_kt.strftime('%d%m%Y')}"
    return du_lieu_word, df_xuat, ten_file


def build_payload_mau15(
    pgd: str, ten_xa: str, ten_to: str, to_truong: str,
    ma_to: str, dia_chi: str, can_bo_kt: str,
    ngay_chot: date, pgd_scope: str,
) -> tuple[dict, str]:
    du_lieu_word = {
        "pgd": pgd, "ten_xa": ten_xa, "ten_to": ten_to,
        "to_truong": to_truong, "ma_to": ma_to,
        "dia_chi": dia_chi, "can_bo_kt": can_bo_kt,
        "ngay_chot": ngay_chot,
    }
    ten_file = (
        f"Mau15TD_{ten_to.replace(' ','_')}_"
        f"{ngay_chot.strftime('%d%m%Y')}"
    )
    return du_lieu_word, ten_file


def build_payload_mau16(
    don_vi_kt: str, ten_xa: str, ten_thon: str, ten_to: str,
    hoi_doan_the: str, to_truong: str, to_pho: str,
    can_bo_1: str, chuc_vu_1: str, can_bo_2: str, chuc_vu_2: str,
    ngay_kt: date,
    ty_le_nqh: str, xep_loai_to: str, so_kh_kt_thuc_te: str,
    uu_diem: str, ton_tai: str, kien_nghi: str, so_phieu_kem_theo: str,
    df_src: pd.DataFrame,
) -> tuple[dict, pd.DataFrame, str]:
    df_xuat = df_src.copy()
    if ten_xa and COT_TEN_XA in df_xuat.columns:
        df_xuat = df_xuat[df_xuat[COT_TEN_XA] == ten_xa]
    if ten_to and COT_TEN_TO in df_xuat.columns:
        df_xuat = df_xuat[df_xuat[COT_TEN_TO] == ten_to]
    du_lieu = {
        "don_vi_kt": don_vi_kt,
        "ten_xa": ten_xa, "ten_thon": ten_thon,
        "ten_to": ten_to, "hoi_doan_the": hoi_doan_the,
        "to_truong": to_truong, "to_pho": to_pho,
        "can_bo_1": can_bo_1, "chuc_vu_1": chuc_vu_1,
        "can_bo_2": can_bo_2, "chuc_vu_2": chuc_vu_2,
        "ngay_kt": ngay_kt,
        "ty_le_nqh": ty_le_nqh, "xep_loai_to": xep_loai_to,
        "so_kh_kt_thuc_te": so_kh_kt_thuc_te,
        "uu_diem": uu_diem, "ton_tai": ton_tai,
        "kien_nghi": kien_nghi,
        "so_phieu_kem_theo": so_phieu_kem_theo,
    }
    to_slug = (ten_to or "TatCa").replace(" ", "_")
    ten_file = f"Mau16TD_{to_slug}_{ngay_kt.strftime('%d%m%Y')}"
    return du_lieu, df_xuat, ten_file


def build_payload_bb_xac_minh(
    ten_kh: str, so_ku: str, so_tien: float,
    ly_do: str, bien_phap: str, can_bo_lap: str,
    ngay_lap: date, pgd_scope: str,
) -> tuple[dict, str]:
    du_lieu = {
        "ten_kh": ten_kh, "so_ku": so_ku,
        "so_tien": f"{so_tien:,.1f}",
        "ly_do": ly_do, "bien_phap": bien_phap,
        "can_bo_lap": can_bo_lap,
        "ngay_lap": ngay_lap,
        "ngay": ngay_lap.day, "thang": ngay_lap.month, "nam": ngay_lap.year,
    }
    slug = pgd_slug(pgd_scope) if pgd_scope else "cn"
    ten_file = (
        f"BBXacMinh_{so_ku}_{slug}_"
        f"{ngay_lap.strftime('%d%m%Y')}"
    )
    return du_lieu, ten_file


def build_payload_bc_th(
    don_vi_kt: str, truong_doan: str, cap_uy: str,
    dia_danh: str, ngay_bc: date, noi_dung_kt: str,
    nx_ctxh: str, nx_to: str, nx_to_vien: str,
    kn_ctxh: str, kn_nhcs: str, kn_cap_tren: str,
    nam_td: int,
) -> tuple[dict, str]:
    du_lieu_bc = {
        "don_vi_kt": don_vi_kt, "truong_doan": truong_doan,
        "dia_danh": dia_danh, "ngay_bc": ngay_bc, "cap_uy": cap_uy,
        "noi_dung_kt": noi_dung_kt,
        "nx_ctxh": nx_ctxh, "nx_to": nx_to, "nx_to_vien": nx_to_vien,
        "kn_ctxh": kn_ctxh, "kn_nhcs": kn_nhcs, "kn_cap_tren": kn_cap_tren,
    }
    ten_file = f"BaoCaoTH_UyThac_{nam_td}"
    return du_lieu_bc, ten_file

