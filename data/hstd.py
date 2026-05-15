"""Đọc file dữ liệu gốc: HSTD, NQ11, GQVL, Điện báo."""
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from data.core import ts_file, excel_to_parquet
from services.data_quality import kiem_tra_chat_luong
from config import (
    CACHE_HSTD, CACHE_NQ11,
    GQVL_COT_MAP, CACHE_GQVL, CACHE_SK_GQVL,
)


# ── HSTD ─────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def doc_file(fp: str, _ts) -> pd.DataFrame:
    """Đọc file HSTD (BCQUERY sheet, header dòng 4).
    Không chạy kiem_tra_chat_luong ở đây — merge_du_lieu_toan_cn đã chạy DQ rồi.
    """
    def clean(df): return df.iloc[:, 1:].dropna(how="all")
    try:
        return excel_to_parquet(fp, CACHE_HSTD, "BCQUERY", 4, clean)
    except Exception:
        return pd.read_excel(fp, sheet_name="BCQUERY", header=4).iloc[:, 1:].dropna(how="all")


@st.cache_data(show_spinner="Đang tải dữ liệu mốc 31/12...")
def doc_baseline(nam: int, _ts=0) -> pd.DataFrame | None:
    """Đọc HSTD mốc 31/12 theo năm. Trả None nếu chưa có file."""
    from config import baseline_path, baseline_cache
    fp = baseline_path(nam)
    cp = baseline_cache(nam)
    if not os.path.exists(fp):
        return None
    try:
        return excel_to_parquet(fp, cp, "BCQUERY", 4)
    except Exception:
        return pd.read_excel(fp, sheet_name="BCQUERY", header=4).iloc[:, 1:].dropna(how="all")


@st.cache_data(show_spinner=False)
def doc_baseline_pgd(ten_pgd: str, nam: int, _ts=0) -> pd.DataFrame | None:
    """Đọc HSTD mốc 31/12 của một PGD cụ thể."""
    from config import baseline_path_pgd, CACHE_DIR
    from data.pgd import pgd_slug
    fp = baseline_path_pgd(ten_pgd, nam)
    if not os.path.exists(fp):
        return None
    try:
        cp = str(Path(CACHE_DIR) / f"hstd_bl_{pgd_slug(ten_pgd)}_{nam}.parquet")
        return excel_to_parquet(fp, cp, "BCQUERY", 4)
    except Exception:
        return pd.read_excel(fp, sheet_name="BCQUERY", header=4).iloc[:, 1:].dropna(how="all")


@st.cache_data(show_spinner="Đang tổng hợp mốc 31/12...")
def doc_baseline_merged(nam: int, _ts=0) -> pd.DataFrame | None:
    """
    Đọc và merge HSTD mốc 31/12 từ tất cả đơn vị đã upload.
    Ưu tiên baseline_pgd_path; fallback về baseline_path cũ nếu không có đơn vị nào.
    Trả None nếu không có dữ liệu.
    """
    from config import BASELINE_PGD_DIR, baseline_pgd_path, baseline_path
    from config import DS_PGD, DON_VI_CHI_NHANH
    ds = [DON_VI_CHI_NHANH] + DS_PGD
    dfs = []
    for dv in ds:
        fp = baseline_pgd_path(dv, nam)
        if os.path.exists(fp):
            try:
                df = pd.read_excel(fp, sheet_name="BCQUERY", header=4, engine="openpyxl").iloc[:, 1:].dropna(how="all")
                dfs.append(df)
            except Exception:
                pass
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    # fallback: file tổng cũ
    return doc_baseline(nam, _ts)


# ── NQ11 ─────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def doc_file_nq11(fp: str, _ts) -> pd.DataFrame:
    """Đọc file sao kê NQ11 (BCQUERY sheet, header dòng 4)."""
    def clean(df): return df.iloc[:, 1:].dropna(how="all")
    try:
        df = excel_to_parquet(fp, CACHE_NQ11, "BCQUERY", 4, clean)
    except Exception:
        df = pd.read_excel(fp, sheet_name="BCQUERY", header=4).iloc[:, 1:].dropna(how="all")
    return kiem_tra_chat_luong(df, "nq11").df


# ── GQVL ─────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def doc_file_gqvl(fp: str, _ts) -> pd.DataFrame:
    """Đọc file sao kê GQVL, chuẩn hoá tên cột."""
    try:
        os.makedirs(os.path.dirname(CACHE_GQVL), exist_ok=True)
        if ts_file(CACHE_GQVL) < ts_file(fp):
            df = pd.read_excel(fp, sheet_name="Sheet1", header=7)
            df = df.iloc[:, 1:].dropna(how="all").iloc[1:]
            df = df.rename(columns=GQVL_COT_MAP).reset_index(drop=True)
            df = kiem_tra_chat_luong(df, "gqvl").df
            df.to_parquet(CACHE_GQVL, index=False)
        return pd.read_parquet(CACHE_GQVL)
    except Exception:
        df = pd.read_excel(fp, sheet_name="Sheet1", header=7)
        df = df.iloc[:, 1:].dropna(how="all").iloc[1:]
        df = df.rename(columns=GQVL_COT_MAP).reset_index(drop=True)
        return kiem_tra_chat_luong(df, "gqvl").df


# ── SK GQVL (tra NQ11 cho món vay dư nợ = 0) ─────────────────────────────────
@st.cache_data(show_spinner=False)
def doc_file_sk_gqvl(fp: str, _ts) -> pd.DataFrame:
    """
    Đọc file sao kê GQVL chi tiết (SK_GQVL_du_lieu_tho.xlsx).
    Header ở dòng 7, bỏ dòng đầu tiên sau header (dòng tổng cộng).
    Chuẩn hoá tên cột theo GQVL_COT_MAP — kết quả có cột 'Số khế ước' và 'NQ11'.
    """
    def _doc(path: str) -> pd.DataFrame:
        df = pd.read_excel(path, sheet_name="Sheet1", header=7)
        df = df.iloc[:, 1:].dropna(how="all").iloc[1:].reset_index(drop=True)
        return df.rename(columns=GQVL_COT_MAP)

    try:
        os.makedirs(os.path.dirname(CACHE_SK_GQVL), exist_ok=True)
        if ts_file(CACHE_SK_GQVL) < ts_file(fp):
            _doc(fp).to_parquet(CACHE_SK_GQVL, index=False)
        return pd.read_parquet(CACHE_SK_GQVL)
    except Exception:
        return _doc(fp)


# ── ĐIỆN BÁO ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def doc_dienbao(fp: str, _ts) -> list:
    """
    Đọc file Điện báo 2 cột (Chỉ tiêu / Giá trị).
    Trả về list[dict]: {ten, val, la_nqh_con, cha}
    """
    df_raw = pd.read_excel(fp, header=None)
    rows, ten_cha = [], None
    for _, row in df_raw.iterrows():
        ten = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        if ten in ("", "nan", "Chỉ tiêu", "Điện báo ngày"):
            continue
        try:
            val = float(row.iloc[2]) if pd.notna(row.iloc[2]) else 0.0
        except:
            val = 0.0
        if ten.startswith("Trđ:"):
            rows.append({"ten": f"  NQH: {ten_cha}", "val": val,
                         "la_nqh_con": True, "cha": ten_cha})
        else:
            rows.append({"ten": ten, "val": val,
                         "la_nqh_con": False, "cha": None})
            ten_cha = ten
    return rows


def db_lookup(rows: list, ten_search: str) -> float:
    """Tìm giá trị theo tên chỉ tiêu (chính xác → gần đúng)."""
    if not rows:
        return 0.0
    ten_l = ten_search.lower()
    for r in rows:
        if not r["la_nqh_con"] and r["ten"].strip() == ten_search.strip():
            return r["val"]
    for r in rows:
        if not r["la_nqh_con"] and ten_l in r["ten"].lower():
            return r["val"]
    return 0.0


def db_nqh_con(rows: list, ten_cha: str) -> float:
    """Lấy giá trị NQH dòng con ngay sau ten_cha."""
    for r in rows:
        if r["la_nqh_con"] and r["cha"] == ten_cha:
            return r["val"]
    return 0.0


# ── Phân tích rủi ro: 3 tháng không hoạt động ────────────────────────────────

def danh_dau_khong_hd(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Đánh dấu món vay 3 tháng không hoạt động (KHĐ) theo Mẫu 08/KTNB.

    Ưu tiên 1 — có cột \"Ngày giao dịch gần nhất\": khoảng cách tháng từ
    (Ngày số liệu − ngày GD gần nhất, fallback Ngày vay nếu GDGN null) / 30.44.

    Ưu tiên 2 — không có cột GDGN (HSTD cũ): giữ logic lãi tồn
    (Lãi tồn TH > N × Lãi DT tháng và Lãi DT > 0).

    Ngoại lệ không đánh dấu KHĐ: (Dư nợ TH + Dư nợ QH) ≤ 0; Dư nợ khoanh > 0;
    Mã chương trình 02 (HSSV).

    Thêm cột: is_3m_inactive (bool), so_thang_khong_hd (float, làm tròn 1 chữ số
    theo nhánh đang dùng).
    """
    from config import (
        COT_LAI_TON,
        COT_LAI_THANG,
        NGUONG_KHONG_HĐ_THANG,
        COT_NGAY_GDGN,
        COT_NGAY_VAY,
        COT_NGAY_SL,
        COT_DU_NO_TH,
        COT_DU_NO_QH,
        COT_MA_CHUONG_TRINH,
    )

    COT_DU_NO_KHOANH = "Dư nợ khoanh"
    df = df.copy()

    du_th = pd.to_numeric(df[COT_DU_NO_TH], errors="coerce").fillna(0) if COT_DU_NO_TH in df.columns else pd.Series(0.0, index=df.index)
    du_qh = pd.to_numeric(df[COT_DU_NO_QH], errors="coerce").fillna(0) if COT_DU_NO_QH in df.columns else pd.Series(0.0, index=df.index)
    du_kh = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0) if COT_DU_NO_KHOANH in df.columns else pd.Series(0.0, index=df.index)

    mask_loai_tru = (du_th + du_qh) <= 0
    mask_loai_tru = mask_loai_tru | (du_kh > 0)
    if COT_MA_CHUONG_TRINH in df.columns:
        ma_raw = df[COT_MA_CHUONG_TRINH]
        ma_num = pd.to_numeric(ma_raw, errors="coerce")
        ma_str = ma_raw.astype(str).str.strip()
        mask_hssv = (ma_num == 2) | (ma_str == "02") | (ma_str == "2")
        mask_loai_tru = mask_loai_tru | mask_hssv

    co_the_dung_ngay = (
        COT_NGAY_GDGN in df.columns
        and COT_NGAY_SL in df.columns
    )

    if co_the_dung_ngay:
        ngay_sl = pd.to_datetime(df[COT_NGAY_SL], errors="coerce")
        ngay_gdgn = pd.to_datetime(df[COT_NGAY_GDGN], errors="coerce")
        ngay_vay = pd.to_datetime(df[COT_NGAY_VAY], errors="coerce") if COT_NGAY_VAY in df.columns else pd.Series(pd.NaT, index=df.index)
        ref = ngay_gdgn.where(ngay_gdgn.notna(), ngay_vay)
        days = (ngay_sl - ref).dt.days
        so_thang = days.astype(float) / 30.44
        df["so_thang_khong_hd"] = so_thang.round(1)
        mask_khd = (so_thang >= float(NGUONG_KHONG_HĐ_THANG)) & so_thang.notna()
        df["is_3m_inactive"] = mask_khd & (~mask_loai_tru)
        return df

    if COT_LAI_TON not in df.columns or COT_LAI_THANG not in df.columns:
        df["is_3m_inactive"] = False
        df["so_thang_khong_hd"] = float("nan")
        return df

    lai_ton = pd.to_numeric(df[COT_LAI_TON], errors="coerce").fillna(0)
    lai_thang = pd.to_numeric(df[COT_LAI_THANG], errors="coerce").fillna(0)
    so_uoc = lai_ton / lai_thang.clip(lower=1e-9)
    df["so_thang_khong_hd"] = so_uoc.round(1)
    mask_khd = (lai_ton > NGUONG_KHONG_HĐ_THANG * lai_thang) & (lai_thang > 0)
    df["is_3m_inactive"] = mask_khd & (~mask_loai_tru)
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def danh_dau_khong_hd_cached(df: "pd.DataFrame") -> "pd.DataFrame":
    """Cache wrapper cho danh_dau_khong_hd — dùng thay thế khi gọi nhiều lần trong cùng rerun."""
    return danh_dau_khong_hd(df)


@st.cache_data(show_spinner=False, ttl=3600)
def tong_hop_khong_hd_cached(df: "pd.DataFrame", nhom_theo: str = "Tên ĐVUT") -> "pd.DataFrame":
    return tong_hop_khong_hd(df, nhom_theo=nhom_theo)


@st.cache_data(show_spinner=False, ttl=3600)
def canh_bao_migration_cached(df: "pd.DataFrame") -> "pd.DataFrame":
    return canh_bao_migration(df)


def tong_hop_khong_hd(df: "pd.DataFrame",
                      nhom_theo: str = "Tên ĐVUT") -> "pd.DataFrame":
    """
    Tổng hợp số món 'không hoạt động 3 tháng' theo nhóm.

    Tham số:
        df        : DataFrame đã qua danh_dau_khong_hd()
        nhom_theo : Cột để group — "Tên ĐVUT", "Tên xã", "Tên PGD", "Tên thôn"

    Trả về DataFrame gồm:
        nhom_theo | Tổng_món | Món_3m_KHĐ | Tỷ_lệ_KHĐ_%
        | Lãi_tồn_KHĐ | Dư_nợ_KHĐ
    """
    from config import (COT_SO_KU, COT_TONG_DU_NO, COT_LAI_TON,
                        COT_DU_NO_TH, COT_DU_NO_QH)

    if "is_3m_inactive" not in df.columns:
        df = danh_dau_khong_hd(df)

    if nhom_theo not in df.columns:
        return pd.DataFrame()

    df_inactive = df[df["is_3m_inactive"]]

    # Tổng toàn bộ theo nhóm
    tong = df.groupby(nhom_theo).agg(
        Tổng_món=(COT_SO_KU, "nunique"),
    ).reset_index()

    # Tổng món không hoạt động theo nhóm
    khd = df_inactive.groupby(nhom_theo).agg(
        Món_3m_KHĐ   =(COT_SO_KU,       "nunique"),
        Lãi_tồn_KHĐ  =(COT_LAI_TON,     "sum"),
        Dư_nợ_KHĐ    =(COT_TONG_DU_NO,  "sum"),
    ).reset_index()

    result = tong.merge(khd, on=nhom_theo, how="left").fillna(0)
    result["Món_3m_KHĐ"]  = result["Món_3m_KHĐ"].astype(int)
    result["Tỷ_lệ_KHĐ_%"] = (
        result["Món_3m_KHĐ"] / result["Tổng_món"] * 100
    ).round(1).fillna(0)

    return result.sort_values("Món_3m_KHĐ", ascending=False).reset_index(drop=True)


def ds_chi_tiet_khong_hd(df: "pd.DataFrame",
                          nhom_theo: str = "Tên ĐVUT",
                          gia_tri_nhom: str = None) -> "pd.DataFrame":
    """
    Danh sách chi tiết các hộ cần đôn đốc (3 tháng không hoạt động).
    Dùng để xuất Excel giao CBTD đi đôn đốc.

    Tham số:
        df            : DataFrame đã qua danh_dau_khong_hd()
        nhom_theo     : Cột lọc (mặc định "Tên ĐVUT")
        gia_tri_nhom  : Giá trị nhóm cần lấy (None = tất cả)
    """
    import logging

    from config import (
        COT_TEN_PGD,
        COT_TEN_XA,
        COT_MA_KH,
        COT_TEN_KH,
        COT_SO_KU,
        COT_NGAY_GDGN,
        COT_TEN_CT,
        COT_TONG_DU_NO,
        COT_LAI_TON,
        COT_DVUT,
        COT_NGAY_DH,
    )

    if "is_3m_inactive" not in df.columns:
        df = danh_dau_khong_hd(df)

    ds = df[df["is_3m_inactive"]].copy()

    if gia_tri_nhom and nhom_theo in ds.columns:
        ds = ds[ds[nhom_theo] == gia_tri_nhom]

    logging.debug(
        "Cột ngày hạn: %s",
        [c for c in ds.columns if "hạn" in c.lower()],
    )
    logging.debug(
        "Cột lãi tồn: %s",
        [c for c in ds.columns if "lãi" in c.lower() and "tồn" in c.lower()],
    )

    cot_lai_ton_qh = None
    for alias in ("Lãi tồn QH", "Lãi quá hạn tồn", "Lãi tồn quá hạn"):
        if alias in ds.columns:
            cot_lai_ton_qh = alias
            break

    if COT_LAI_TON in ds.columns:
        lai_th = pd.to_numeric(ds[COT_LAI_TON], errors="coerce").fillna(0)
    else:
        lai_th = pd.Series(0.0, index=ds.index, dtype="float64")

    if cot_lai_ton_qh is not None:
        lai_qh = pd.to_numeric(ds[cot_lai_ton_qh], errors="coerce").fillna(0)
    else:
        lai_qh = pd.Series(0.0, index=ds.index, dtype="float64")

    ds["Lãi tồn"] = lai_th + lai_qh

    cot_ngay_han = None
    for alias in (
        "Ngày đến hạn cuối",
        "Ngày đến hạn (sau GH)",
        "Ngày đến hạn GH",
        "Ngày ĐH cuối",
        COT_NGAY_DH,
    ):
        if alias in ds.columns:
            cot_ngay_han = alias
            break
    if cot_ngay_han is not None:
        ds["Ngày đến hạn cuối"] = ds[cot_ngay_han]

    cols_xuat = [
        c
        for c in [
            COT_TEN_PGD,
            COT_TEN_XA,
            COT_DVUT,
            "Tên tổ",
            COT_MA_KH,
            COT_TEN_KH,
            COT_SO_KU,
            COT_TEN_CT,
            "Ngày đến hạn cuối",
            COT_TONG_DU_NO,
            "Lãi tồn",
            COT_NGAY_GDGN,
        ]
        if c in ds.columns
    ]

    return ds[cols_xuat].reset_index(drop=True)


def canh_bao_migration(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Phát hiện món vay 'Đủ tiêu chuẩn' (Phân loại=E) có dấu hiệu
    sắp chuyển sang '3 tháng không lãi' — cảnh báo sớm trước NQH.

    Điều kiện:
        - Phân loại = E (Đủ tiêu chuẩn — chưa quá hạn)
        - Lãi tồn TH > 0  (đã bắt đầu tồn lãi)
        - Lãi tồn TH > 1 tháng lãi dự thu (cảnh báo từ tháng thứ 2)
        - Chưa đủ 3 tháng (is_3m_inactive = False)
        → Vùng "amber": cần chú ý, chưa vi phạm nhưng có rủi ro cao

    Trả về DataFrame chỉ gồm các món ở vùng cảnh báo, có thêm cột:
        'so_thang_ton_uoc' — số tháng lãi tồn ước tính
        'muc_canh_bao'     — "⚠️ Cảnh báo" hoặc "🔴 Khẩn cấp"
    """
    from config import (COT_LAI_TON, COT_LAI_THANG, COT_PHAN_LOAI,
                        COT_SO_KU, COT_TEN_KH, COT_TEN_PGD,
                        COT_TEN_XA, COT_DVUT)

    if "is_3m_inactive" not in df.columns:
        df = danh_dau_khong_hd(df)

    lai_ton   = pd.to_numeric(df[COT_LAI_TON],   errors="coerce").fillna(0)
    lai_thang = pd.to_numeric(df[COT_LAI_THANG], errors="coerce").fillna(1)

    mask_e = df[COT_PHAN_LOAI].astype(str).str.strip().str.upper() == "E" \
             if COT_PHAN_LOAI in df.columns else pd.Series(True, index=df.index)
    so_thang = lai_ton / lai_thang.clip(lower=1)
    mask_amber = (
        mask_e &
        (so_thang >= 2.0) &           # từ 2 tháng trở lên
        (~df["is_3m_inactive"])        # chưa đủ 3 tháng (chưa bị đánh dấu)
    )

    result = df[mask_amber].copy()
    result["so_thang_ton_uoc"] = so_thang[mask_amber].round(1)
    result["muc_canh_bao"] = result["so_thang_ton_uoc"].apply(
        lambda x: "🔴 Nguy cơ cao (2.5–3 tháng)" if x >= 2.5 else "⚠️ Sắp chuyển 3 tháng KHĐ (2–2.4 tháng)"
    )
    return result.reset_index(drop=True)
