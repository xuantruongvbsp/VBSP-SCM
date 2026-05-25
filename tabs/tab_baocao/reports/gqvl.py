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
    COT_DU_NO_QH,
    COT_TEN_NHA_DAU_TU,
    COT_GQVL_MA_PGD,
)
from auth import la_phan_he_pgd
from utils import fmt_so, hien_thi_dataframe_phan_trang, vn
from ..components.export_panel import render_export_panel

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _fmt_df_trieu(df: pd.DataFrame) -> pd.DataFrame:
    """Format cột tiền sang triệu đồng."""
    d = df.copy()
    tien_cols = [COT_TONG_DU_NO, COT_DU_NO_QH, COT_GIAI_NGAN_TRONG_NAM]
    for col in tien_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
    return d


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
    
    ctx.markdown("### 💼 Báo cáo GQVL")
    
    # Chọn loại báo cáo
    loai_bc = ctx.radio(
        "Loại báo cáo",
        ["🏛️ Phân tầng TW/ĐP", "🏢 Theo nhà đầu tư", "📊 Tổng hợp giải ngân"],
        horizontal=True,
        key="gqvl_loai_bc",
    )
    
    # Lọc theo PGD nếu cần
    df_filtered = df_gqvl.copy()
    if la_phan_he_pgd(role) and pgd_user:
        # Tìm cột tên PGD trong GQVL
        pgd_col = None
        for col in df_filtered.columns:
            if "pgd" in col.lower() or "đơn vị" in col.lower():
                pgd_col = col
                break
        if pgd_col and pgd_col in df_filtered.columns:
            df_filtered = df_filtered[df_filtered[pgd_col].str.contains(pgd_user, case=False, na=False)]
    
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
    
    # Mapping nguồn vốn
    df_tmp = df.copy()
    df_tmp["Nguồn_vốn_map"] = df_tmp[COT_NGUON_VON].map({
        1: "1 - Trung ương (TW)",
        2: "2 - Địa phương (ĐP)",
        "TW": "1 - Trung ương (TW)",
        "ĐP": "2 - Địa phương (ĐP)",
    }).fillna(df_tmp[COT_NGUON_VON].astype(str))
    
    df_th = df_tmp.groupby("Nguồn_vốn_map").agg(
        Số_món=(COT_GQVL_MA_PGD, "count"),
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        Nợ_quá_hạn=(COT_DU_NO_QH, "sum"),
    ).reset_index()
    
    ctx.markdown("**📊 Phân tầng nguồn vốn GQVL**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_th), key="gqvl_phantang")
    
    ctx.divider()
    render_export_panel(df_th, "Phân tầng GQVL", "Báo cáo GQVL phân tầng", username, "BC_GQVL_PT", ctx, "gqvl_pt")


def _render_nha_dau_tu(ctx, df: pd.DataFrame, username: str) -> None:
    """Render theo nhà đầu tư."""
    ndt_col = COT_TEN_NHA_DAU_TU
    if ndt_col not in df.columns:
        ctx.error("❌ Không có cột mã nhà đầu tư.")
        return
    
    df_th = df.groupby(ndt_col).agg(
        Số_món=(COT_GQVL_MA_PGD, "count"),
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        Nợ_quá_hạn=(COT_DU_NO_QH, "sum"),
    ).reset_index().sort_values("Tổng_dư_nợ", ascending=False).head(20)  # Top 20
    
    ctx.markdown(f"**🏢 Top 20 nhà đầu tư — {fmt_so(len(df_th))} nhà đầu tư**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_th), key="gqvl_ndt")
    
    ctx.divider()
    render_export_panel(df_th, "Nhà đầu tư", "Báo cáo GQVL theo NĐT", username, "BC_GQVL_NDT", ctx, "gqvl_ndt")


def _render_giai_ngan(ctx, df: pd.DataFrame, username: str) -> None:
    """Render tổng hợp giải ngân."""
    if COT_GIAI_NGAN_TRONG_NAM not in df.columns:
        ctx.error("❌ Không có cột giải ngân trong năm.")
        return
    
    df_th = df.groupby(COT_TEN_PGD if COT_TEN_PGD in df.columns else COT_TEN_XA).agg(
        Số_món=(COT_GQVL_MA_PGD, "count"),
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        Giải_ngân_năm=(COT_GIAI_NGAN_TRONG_NAM, "sum"),
    ).reset_index().sort_values("Giải_ngân_năm", ascending=False)
    
    ctx.markdown("**📊 Tổng hợp giải ngân GQVL**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_th), key="gqvl_gn")
    
    ctx.divider()
    render_export_panel(df_th, "Giải ngân", "Báo cáo GQVL giải ngân", username, "BC_GQVL_GN", ctx, "gqvl_gn")
