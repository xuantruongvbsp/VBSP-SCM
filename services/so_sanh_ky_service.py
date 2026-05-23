"""
Các hàm xử lý dữ liệu thuần (không có st.*) cho tab So sánh kỳ.

Extract từ tabs/tab_so_sanh_ky.py để tái sử dụng và kiểm thử độc lập.
"""
from __future__ import annotations

import pandas as pd

from config import (
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_MA_KH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TONG_DU_NO,
    HSTD_DS_CHO_VAY_NAM_ALIASES,
)
from services.hhi_service import danh_gia_hhi, tinh_hhi, tinh_hhi_breakdown
from services.migration_service import migration_matrix
from utils import fmt_so, fmt_ty
import streamlit as st


@st.cache_data(ttl=300, show_spinner=False)
def agg_mot_pgd(df: pd.DataFrame) -> dict[str, float | int]:
    """Tổng hợp các chỉ tiêu chính cho 1 DataFrame (1 PGD hoặc toàn CN)."""
    if df is None or df.empty:
        return {
            "tong_du_no": 0, "du_no_th": 0, "du_no_qh": 0,
            "du_no_khoanh": 0, "so_ho": 0, "so_ku": 0, "gn_nam": 0,
            "tong_lai_ton": 0,
        }
    col_gn = next((c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df.columns), None)
    lai_th = df[COT_LAI_TON].sum()    if COT_LAI_TON    in df.columns else 0
    lai_qh = df[COT_LAI_TON_QH].sum() if COT_LAI_TON_QH in df.columns else 0
    return {
        "tong_du_no":    df[COT_TONG_DU_NO].sum()    if COT_TONG_DU_NO   in df.columns else 0,
        "du_no_th":      df[COT_DU_NO_TH].sum()      if COT_DU_NO_TH     in df.columns else 0,
        "du_no_qh":      df[COT_DU_NO_QH].sum()      if COT_DU_NO_QH     in df.columns else 0,
        "du_no_khoanh":  df[COT_DU_NO_KHOANH].sum()  if COT_DU_NO_KHOANH in df.columns else 0,
        "so_ho":         int(df[COT_MA_KH].nunique()) if COT_MA_KH        in df.columns else 0,
        "so_ku":         int(df[COT_SO_KU].nunique()) if COT_SO_KU        in df.columns else 0,
        "gn_nam":        df[col_gn].sum()             if col_gn                         else 0,
        "tong_lai_ton":  lai_th + lai_qh,
    }


@st.cache_data(ttl=300, show_spinner=False)
def agg_theo_pgd(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp chỉ tiêu theo từng PGD, thêm hàng tổng."""
    if df is None or df.empty or COT_TEN_PGD not in df.columns:
        return pd.DataFrame()
    
    agg_spec: dict[str, tuple[str, str]] = {
        "tong_du_no": (COT_TONG_DU_NO, "sum"),
        "du_no_th":   (COT_DU_NO_TH, "sum"),
        "du_no_qh":   (COT_DU_NO_QH, "sum"),
        "so_ho":      (COT_MA_KH, "nunique"),
        "so_ku":      (COT_SO_KU, "nunique"),
    }
    if COT_DU_NO_KHOANH in df.columns:
        agg_spec["du_no_khoanh"] = (COT_DU_NO_KHOANH, "sum")
    col_gn = next((c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df.columns), None)
    if col_gn:
        agg_spec["gn_nam"] = (col_gn, "sum")

    try:
        result = df.groupby(COT_TEN_PGD).agg(**agg_spec).reset_index()
    except Exception:
        return pd.DataFrame()

    tong = {COT_TEN_PGD: "⬛ Tổng Chi nhánh"}
    for col in result.columns:
        if col != COT_TEN_PGD:
            tong[col] = result[col].sum()
    result = pd.concat([result, pd.DataFrame([tong])], ignore_index=True)
    return result


def agg_theo_dvut(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp chỉ tiêu theo Hội đoàn thể (ĐVUT), thêm hàng tổng."""
    if df is None or df.empty or COT_DVUT not in df.columns:
        return pd.DataFrame()

    agg_spec: dict[str, tuple[str, str]] = {
        "tong_du_no": (COT_TONG_DU_NO, "sum"),
        "du_no_qh":   (COT_DU_NO_QH, "sum"),
        "so_ho":      (COT_MA_KH, "nunique"),
        "so_ku":      (COT_SO_KU, "nunique"),
    }
    if COT_DU_NO_KHOANH in df.columns:
        agg_spec["du_no_khoanh"] = (COT_DU_NO_KHOANH, "sum")

    try:
        result = df.groupby(COT_DVUT).agg(**agg_spec).reset_index()
    except Exception:
        return pd.DataFrame()

    tong = {COT_DVUT: "⬛ Tổng"}
    for col in result.columns:
        if col != COT_DVUT:
            tong[col] = result[col].sum()
    return pd.concat([result, pd.DataFrame([tong])], ignore_index=True)


def group_bien_dong(df: pd.DataFrame, dim: str) -> pd.DataFrame:
    """Tổng hợp df theo dim: du_no, du_no_qh, so_ku, nqh_pct."""
    if dim not in df.columns:
        return pd.DataFrame(columns=[dim, "du_no", "du_no_qh", "so_ku", "nqh_pct"])
    cols: dict = {"du_no_qh": (COT_DU_NO_QH, "sum"), "so_ku": (COT_SO_KU, "nunique")}
    if COT_TONG_DU_NO in df.columns:
        cols["du_no"] = (COT_TONG_DU_NO, "sum")
    g = df.groupby(dim, dropna=False).agg(**cols).reset_index()
    if "du_no" not in g.columns:
        g["du_no"] = 0
    g["nqh_pct"] = (g["du_no_qh"] / g["du_no"].replace(0, float("nan")) * 100).fillna(0)
    return g


def delta_str(val: float, baseline: float, unit: str = "ty") -> str:
    """Chuỗi ±delta ngắn gọn."""
    delta = val - baseline
    sign = "+" if delta >= 0 else ""
    if unit == "ty":
        return f"{sign}{fmt_ty(delta)}"
    return f"{sign}{fmt_so(int(delta))}"


def tl_nqh(du_no_qh: float, tong_du_no: float) -> float:
    """Tỷ lệ nợ quá hạn (%)."""
    return (du_no_qh / tong_du_no * 100) if tong_du_no > 0 else 0.0


def fmt_pct_vn(x: float) -> str:
    """Format phần trăm kiểu Việt Nam."""
    return f"{x:.2f}".replace(".", ",") + "%"


def ma_tran_chuyen_nhuong(ky_truoc: str, ky_sau: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lấy ma trận chuyển nhóm nợ từ snapshot."""
    matrix, chi_tiet = migration_matrix(ky_truoc, ky_sau)
    return matrix, chi_tiet


def phan_loai_khach_hang(df_truoc: pd.DataFrame, df_sau: pd.DataFrame) -> pd.DataFrame:
    """Phân loại khách hàng: Retained, Churned, New."""
    if df_truoc.empty or df_sau.empty or COT_MA_KH not in df_truoc.columns:
        return pd.DataFrame()

    ma_kh_truoc = set(df_truoc[COT_MA_KH].astype(str).str.strip())
    ma_kh_sau = set(df_sau[COT_MA_KH].astype(str).str.strip())

    retained = len(ma_kh_truoc & ma_kh_sau)
    churned = len(ma_kh_truoc - ma_kh_sau)
    new = len(ma_kh_sau - ma_kh_truoc)

    return pd.DataFrame([{
        "Loại": "Tồn tại trước đó",
        "Số hộ": fmt_so(retained),
        "% KH trước": fmt_pct_vn((retained / len(ma_kh_truoc) * 100) if ma_kh_truoc else 0),
    }, {
        "Loại": "Rời khỏi",
        "Số hộ": fmt_so(churned),
        "% KH trước": fmt_pct_vn((churned / len(ma_kh_truoc) * 100) if ma_kh_truoc else 0),
    }, {
        "Loại": "Mới",
        "Số hộ": fmt_so(new),
        "% KH sau": fmt_pct_vn((new / len(ma_kh_sau) * 100) if ma_kh_sau else 0),
    }])


def top_movers(
    df_ht: pd.DataFrame,
    df_bl: pd.DataFrame,
    nhom_by: str = COT_TEN_PGD,
    n: int = 5,
) -> pd.DataFrame:
    """Top N đơn vị với thay đổi lớn nhất về dư nợ và NQH."""
    if df_ht.empty or df_bl.empty:
        return pd.DataFrame()

    if nhom_by not in df_ht.columns or nhom_by not in df_bl.columns:
        return pd.DataFrame()

    agg_ht = df_ht.groupby(nhom_by).agg({
        COT_TONG_DU_NO: "sum",
        COT_DU_NO_QH: "sum",
    }).reset_index()
    agg_ht["nqh_pct"] = (agg_ht[COT_DU_NO_QH] / agg_ht[COT_TONG_DU_NO] * 100).fillna(0)

    agg_bl = df_bl.groupby(nhom_by).agg({
        COT_TONG_DU_NO: "sum",
        COT_DU_NO_QH: "sum",
    }).reset_index()
    agg_bl["nqh_pct"] = (agg_bl[COT_DU_NO_QH] / agg_bl[COT_TONG_DU_NO] * 100).fillna(0)

    merged = agg_ht.merge(
        agg_bl,
        on=nhom_by,
        how="outer",
        suffixes=("_ht", "_bl"),
    ).fillna(0)

    merged["delta_dn"] = merged[f"{COT_TONG_DU_NO}_ht"] - merged[f"{COT_TONG_DU_NO}_bl"]
    merged["delta_nqh"] = merged["nqh_pct_ht"] - merged["nqh_pct_bl"]
    merged["pct_change"] = (
        merged["delta_dn"] / merged[f"{COT_TONG_DU_NO}_bl"]
        * 100
    ).where(merged[f"{COT_TONG_DU_NO}_bl"] != 0, 0)

    top = merged.nlargest(n, "delta_dn")

    result = pd.DataFrame()
    result[nhom_by] = top[nhom_by]
    result["DN mốc"] = top[f"{COT_TONG_DU_NO}_bl"].apply(fmt_ty)
    result["DN HT"] = top[f"{COT_TONG_DU_NO}_ht"].apply(fmt_ty)
    result["Δ DN"] = top["delta_dn"].apply(lambda x: ("+" if x >= 0 else "") + fmt_ty(x))
    result["% Thay đổi"] = top["pct_change"].apply(fmt_pct_vn)
    result["NQH mốc"] = top["nqh_pct_bl"].apply(fmt_pct_vn)
    result["NQH HT"] = top["nqh_pct_ht"].apply(fmt_pct_vn)

    return result


def phan_tich_hhi_pgd(df: pd.DataFrame) -> tuple[float, pd.DataFrame, str, str, str]:
    """Tính HHI theo PGD — nồng độ rủi ro."""
    if df.empty or COT_TEN_PGD not in df.columns or COT_TONG_DU_NO not in df.columns:
        return 0.0, pd.DataFrame(), "N/A", "", ""

    hhi = tinh_hhi(df, COT_TEN_PGD, COT_TONG_DU_NO)
    breakdown = tinh_hhi_breakdown(df, COT_TEN_PGD, COT_TONG_DU_NO)

    muc_do, icon, mau = danh_gia_hhi(hhi)

    return hhi, breakdown, muc_do, icon, mau
