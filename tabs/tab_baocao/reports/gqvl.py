"""Báo cáo GQVL - Nhóm D."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_NGUON_VON,
    COT_GIAI_NGAN_TRONG_NAM,
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_DU_NO_KHOANH,
    COT_SO_KU,
    COT_TEN_NHA_DAU_TU,
    COT_MA_NDT,
)
from auth import la_phan_he_pgd
from utils import fmt_so, hien_thi_dataframe_phan_trang, vn
from services.data_quality import chuan_hoa_ma_don_vi
from ..components.inline_filter import _chuan_hoa_nguon_von
from ..components.export_panel import render_export_panel

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


_NHOM_KHONG_XAC_DINH = "Khác/Không xác định"


def _chuan_bi_gqvl(df: pd.DataFrame | None) -> pd.DataFrame:
    """Chuẩn hóa GQVL để mọi KPI/bảng cùng đếm một lần mỗi khế ước."""
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    out = chuan_hoa_ma_don_vi(df)
    for col in (
        COT_DU_NO_TH,
        COT_DU_NO_QH,
        COT_DU_NO_KHOANH,
        COT_TONG_DU_NO,
        COT_GIAI_NGAN_TRONG_NAM,
    ):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    thanh_phan_du_no = [
        col for col in (COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH)
        if col in out.columns
    ]
    if COT_TONG_DU_NO not in out.columns and thanh_phan_du_no:
        out[COT_TONG_DU_NO] = out[thanh_phan_du_no].sum(axis=1)

    if COT_SO_KU in out.columns:
        so_ku = out[COT_SO_KU].astype("string").str.strip()
        hop_le = so_ku.notna() & ~so_ku.str.lower().isin(
            {"", "nan", "none", "null", "<na>"}
        )
        out = out.loc[hop_le].copy()
        out["_so_ku_dem"] = so_ku.loc[hop_le]
        out = out.drop_duplicates(subset=["_so_ku_dem"], keep="first")
    else:
        out["_so_ku_dem"] = out.index.astype(str)

    return out.reset_index(drop=True)


def _fmt_df_trieu(df: pd.DataFrame) -> pd.DataFrame:
    """Format cột tiền sang triệu đồng."""
    d = df.copy()
    tien_cols = [
        COT_TONG_DU_NO, COT_DU_NO_QH, COT_GIAI_NGAN_TRONG_NAM,
        "Tổng_dư_nợ", "Nợ_quá_hạn", "Giải_ngân_năm",
    ]
    for col in tien_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
    return d


def _tong_hop_theo_nha_dau_tu(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, str | None]:
    """Tổng hợp đủ mọi nhà đầu tư; không cắt top làm hụt số liệu xuất báo cáo."""
    ndt_col = next(
        (col for col in (COT_TEN_NHA_DAU_TU, COT_MA_NDT) if col in df.columns),
        None,
    )
    if ndt_col is None:
        return pd.DataFrame(), None
    df_tmp = df.copy()
    nhom_ndt = df_tmp[ndt_col].astype("string").str.strip()
    df_tmp[ndt_col] = nhom_ndt.mask(
        nhom_ndt.isna() | nhom_ndt.eq(""), _NHOM_KHONG_XAC_DINH
    )
    df_th = df_tmp.groupby(ndt_col, dropna=False).agg(
        Số_món=("_so_ku_dem", "nunique"),
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        Nợ_quá_hạn=(COT_DU_NO_QH, "sum"),
    ).reset_index().sort_values("Tổng_dư_nợ", ascending=False)
    return df_th, ndt_col


def render_gqvl(
    tab: DeltaGenerator | None = None,
    df_gqvl: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    **kwargs
) -> None:
    """
    Render báo cáo GQVL.
    
    Args:
        tab: Streamlit container
        df_gqvl: DataFrame GQVL
        role: Role người dùng
        pgd_user: Tên PGD
        username: Username
    """
    ctx = tab if tab is not None else st
    
    if df_gqvl is None or df_gqvl.empty:
        ctx.warning("⚠️ Chưa có dữ liệu GQVL.")
        return
    
    df_filtered = _chuan_bi_gqvl(df_gqvl)
    if df_filtered.empty:
        ctx.warning("⚠️ Dữ liệu GQVL không có khế ước hợp lệ.")
        return
    if COT_TONG_DU_NO not in df_filtered.columns:
        ctx.error("❌ Dữ liệu GQVL không có cột dư nợ hoặc các cột thành phần dư nợ.")
        return

    # Lọc chính xác theo tên PGD đã chuẩn hóa; không dò mơ hồ trên cột mã.
    if (
        la_phan_he_pgd(role)
        and pgd_user
        and COT_TEN_PGD in df_filtered.columns
    ):
        df_filtered = df_filtered.loc[df_filtered[COT_TEN_PGD].eq(pgd_user)].copy()
        if df_filtered.empty:
            ctx.warning(f"⚠️ Không có dữ liệu GQVL của {pgd_user}.")
            return

    ctx.markdown("### 💼 Báo cáo GQVL")

    tong_du_no = df_filtered[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_filtered else 0
    no_qh = df_filtered[COT_DU_NO_QH].sum() if COT_DU_NO_QH in df_filtered else 0
    giai_ngan = (
        df_filtered[COT_GIAI_NGAN_TRONG_NAM].sum()
        if COT_GIAI_NGAN_TRONG_NAM in df_filtered else 0
    )
    c1, c2, c3, c4 = ctx.columns(4)
    c1.metric("Số món GQVL", fmt_so(df_filtered["_so_ku_dem"].nunique()))
    c2.metric("Tổng dư nợ", f"{vn(tong_du_no / 1e9, 1)} tỷ")
    c3.metric("Nợ quá hạn", f"{vn(no_qh / 1e9, 1)} tỷ")
    c4.metric("Giải ngân năm", f"{vn(giai_ngan / 1e9, 1)} tỷ")
    
    # Chọn loại báo cáo
    loai_bc = ctx.radio(
        "Loại báo cáo",
        ["🏛️ Phân tầng TW/ĐP", "🏢 Theo nhà đầu tư", "📊 Tổng hợp giải ngân"],
        horizontal=True,
        key="gqvl_loai_bc",
    )
    
    ctx.divider()
    
    if loai_bc == "🏛️ Phân tầng TW/ĐP":
        _render_phan_tang(ctx, df_filtered, username)
    elif loai_bc == "🏢 Theo nhà đầu tư":
        _render_nha_dau_tu(ctx, df_filtered, username)
    else:
        _render_giai_ngan(ctx, df_filtered, username)


def _render_phan_tang(ctx, df: pd.DataFrame, username: str) -> None:
    """Render phân tầng TW/ĐP."""
    if COT_NGUON_VON not in df.columns:
        ctx.error("❌ Không có cột nguồn vốn.")
        return
    
    df_tmp = df.copy()
    nv_chuan = df_tmp[COT_NGUON_VON].map(_chuan_hoa_nguon_von)
    df_tmp["Nguồn_vốn_map"] = nv_chuan.map({
        "1": "1 - Trung ương (TW)",
        "2": "2 - Địa phương (ĐP)",
    }).fillna(_NHOM_KHONG_XAC_DINH)
    
    df_th = df_tmp.groupby("Nguồn_vốn_map").agg(
        Số_món=("_so_ku_dem", "nunique"),
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        Nợ_quá_hạn=(COT_DU_NO_QH, "sum"),
    ).reset_index()
    
    ctx.markdown("**📊 Phân tầng nguồn vốn GQVL**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_th), key="gqvl_phantang")
    
    ctx.divider()
    render_export_panel(df_th, "Phân tầng GQVL", "Báo cáo GQVL phân tầng", username, "BC_GQVL_PT", ctx, "gqvl_pt")


def _render_nha_dau_tu(ctx, df: pd.DataFrame, username: str) -> None:
    """Render theo nhà đầu tư."""
    df_th, ndt_col = _tong_hop_theo_nha_dau_tu(df)
    if ndt_col is None:
        ctx.error("❌ Không có cột nhà đầu tư.")
        return
    
    ctx.markdown(f"**🏢 Theo nhà đầu tư — {fmt_so(len(df_th))} nhà đầu tư**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_th), key="gqvl_ndt")
    
    ctx.divider()
    render_export_panel(df_th, "Nhà đầu tư", "Báo cáo GQVL theo NĐT", username, "BC_GQVL_NDT", ctx, "gqvl_ndt")


def _render_giai_ngan(ctx, df: pd.DataFrame, username: str) -> None:
    """Render tổng hợp giải ngân."""
    if COT_GIAI_NGAN_TRONG_NAM not in df.columns:
        ctx.error("❌ Không có cột giải ngân trong năm.")
        return
    
    group_col = next(
        (col for col in (COT_TEN_PGD, COT_TEN_XA) if col in df.columns),
        None,
    )
    if group_col is None:
        ctx.error("❌ Không có cột đơn vị/xã để tổng hợp giải ngân.")
        return
    df_tmp = df.copy()
    nhom = df_tmp[group_col].astype("string").str.strip()
    df_tmp[group_col] = nhom.mask(nhom.isna() | nhom.eq(""), _NHOM_KHONG_XAC_DINH)
    df_th = df_tmp.groupby(group_col, dropna=False).agg(
        Số_món=("_so_ku_dem", "nunique"),
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        Giải_ngân_năm=(COT_GIAI_NGAN_TRONG_NAM, "sum"),
    ).reset_index().sort_values("Giải_ngân_năm", ascending=False)
    
    ctx.markdown("**📊 Tổng hợp giải ngân GQVL**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_th), key="gqvl_gn")
    
    ctx.divider()
    render_export_panel(df_th, "Giải ngân", "Báo cáo GQVL giải ngân", username, "BC_GQVL_GN", ctx, "gqvl_gn")
