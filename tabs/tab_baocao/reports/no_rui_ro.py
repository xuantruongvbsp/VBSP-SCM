"""Báo cáo nợ rủi ro - Nhóm B."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_DVUT,
    COT_MA_KH,
    COT_TEN_KH,
    COT_SO_KU,
    COT_NGAY_DH,
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_DU_NO_KHOANH,
)
from auth import la_phan_he_pgd
from utils import fmt_ty, fmt_so, hien_thi_dataframe_phan_trang, vn
from ..components.export_panel import render_export_panel

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _fmt_df_trieu(df: pd.DataFrame) -> pd.DataFrame:
    """Format cột tiền sang triệu đồng."""
    d = df.copy()
    tien_cols = [COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH]
    for col in tien_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
    return d


def render_no_rui_ro(
    tab: DeltaGenerator | None = None,
    df: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    **kwargs
) -> None:
    """
    Render báo cáo nợ rủi ro.
    
    Args:
        tab: Streamlit container
        df: DataFrame HSTD
        role: Role người dùng
        pgd_user: Tên PGD
        username: Username
    """
    ctx = tab if tab is not None else st
    
    if df is None or df.empty:
        ctx.warning("⚠️ Chưa có dữ liệu HSTD.")
        return
    
    ctx.markdown("### ⚠️ Báo cáo Nợ xấu")
    
    # Chọn loại nợ
    loai_no = ctx.radio(
        "Loại báo cáo",
        ["🔴 Nợ quá hạn", "🟠 Nợ khoanh", "⏰ Đến hạn 30 ngày", "⏰ Đến hạn 60 ngày", "📊 Tỷ lệ nợ xấu"],
        horizontal=True,
        key="no_loai",
    )
    
    # Lọc theo PGD nếu cần
    df_filtered = df.copy()
    if la_phan_he_pgd(role) and pgd_user and COT_TEN_PGD in df_filtered.columns:
        df_filtered = df_filtered[df_filtered[COT_TEN_PGD] == pgd_user]
    
    # Xử lý từng loại
    if loai_no == "🔴 Nợ quá hạn":
        _render_no_qh(ctx, df_filtered, username)
    elif loai_no == "🟠 Nợ khoanh":
        _render_no_khoanh(ctx, df_filtered, username)
    elif loai_no in ["⏰ Đến hạn 30 ngày", "⏰ Đến hạn 60 ngày"]:
        ngay = 30 if "30" in loai_no else 60
        _render_den_han(ctx, df_filtered, ngay, username)
    else:  # Tỷ lệ nợ xấu
        _render_ty_le_no_xau(ctx, df_filtered, username)


def _render_no_qh(ctx, df: pd.DataFrame, username: str) -> None:
    """Render báo cáo nợ quá hạn."""
    if COT_DU_NO_QH not in df.columns:
        ctx.error("❌ Không có cột dư nợ quá hạn.")
        return
    
    df_qh = df[df[COT_DU_NO_QH] > 0].copy()
    
    if df_qh.empty:
        ctx.success("✅ Không có nợ quá hạn!")
        return
    
    # Metrics
    col1, col2, col3 = ctx.columns(3)
    col1.metric("Số món QH", fmt_ty(len(df_qh)))
    col2.metric("Dư nợ QH", f"{df_qh[COT_DU_NO_QH].sum()/1e9:,.1f} tỷ".replace(",", "."))
    tl_qh = df_qh[COT_DU_NO_QH].sum() / df[COT_TONG_DU_NO].sum() * 100 if df[COT_TONG_DU_NO].sum() > 0 else 0
    col3.metric("Tỷ lệ QH", f"{tl_qh:.2f}%".replace(".", ","))
    
    # Cột hiển thị
    cols = [c for c in [
        COT_TEN_PGD, COT_TEN_XA, COT_DVUT,
        COT_MA_KH, COT_TEN_KH, COT_SO_KU,
        COT_TONG_DU_NO, COT_DU_NO_QH
    ] if c in df_qh.columns]
    
    ctx.markdown(f"**📋 Danh sách chi tiết — {fmt_so(len(df_qh))} món**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_qh[cols]), key="qh_chitiet")
    
    ctx.divider()
    render_export_panel(df_qh[cols], "Nợ quá hạn", "Báo cáo nợ quá hạn", username, "BC_QH", ctx, "qh")


def _render_no_khoanh(ctx, df: pd.DataFrame, username: str) -> None:
    """Render báo cáo nợ khoanh."""
    if COT_DU_NO_KHOANH not in df.columns:
        ctx.error("❌ Không có cột dư nợ khoanh.")
        return
    
    df_kh = df[df[COT_DU_NO_KHOANH] > 0].copy()
    
    if df_kh.empty:
        ctx.success("✅ Không có nợ khoanh!")
        return
    
    # Metrics
    col1, col2, col3 = ctx.columns(3)
    col1.metric("Số món khoanh", fmt_ty(len(df_kh)))
    col2.metric("Nợ khoanh", f"{df_kh[COT_DU_NO_KHOANH].sum()/1e9:,.1f} tỷ".replace(",", "."))
    tl_kh = df_kh[COT_DU_NO_KHOANH].sum() / df[COT_TONG_DU_NO].sum() * 100 if df[COT_TONG_DU_NO].sum() > 0 else 0
    col3.metric("Tỷ lệ khoanh", f"{tl_kh:.2f}%".replace(".", ","))
    
    cols = [c for c in [
        COT_TEN_PGD, COT_TEN_XA, COT_DVUT,
        COT_MA_KH, COT_TEN_KH, COT_SO_KU,
        COT_TONG_DU_NO, COT_DU_NO_KHOANH
    ] if c in df_kh.columns]
    
    ctx.markdown(f"**📋 Danh sách chi tiết — {fmt_so(len(df_kh))} món**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_kh[cols]), key="kh_chitiet")
    
    ctx.divider()
    render_export_panel(df_kh[cols], "Nợ khoanh", "Báo cáo nợ khoanh", username, "BC_KHOANH", ctx, "kh")


def _render_den_han(ctx, df: pd.DataFrame, ngay: int, username: str) -> None:
    """Render báo cáo đến hạn."""
    if COT_NGAY_DH not in df.columns:
        ctx.error("❌ Không có cột ngày đến hạn.")
        return
    
    # Parse ngày
    df_tmp = df.copy()
    df_tmp[COT_NGAY_DH] = pd.to_datetime(df_tmp[COT_NGAY_DH], dayfirst=True, errors="coerce")
    
    hn = pd.Timestamp.today()
    df_dh = df_tmp[(df_tmp[COT_NGAY_DH] >= hn) & (df_tmp[COT_NGAY_DH] <= hn + pd.Timedelta(days=ngay))].copy()
    
    if df_dh.empty:
        ctx.info(f"📅 Không có món vay đến hạn trong {ngay} ngày tới.")
        return
    
    ctx.success(f"📅 Có **{fmt_so(len(df_dh))}** món đến hạn trong {ngay} ngày tới.")
    
    cols = [c for c in [
        COT_TEN_PGD, COT_TEN_XA, COT_MA_KH, COT_TEN_KH,
        COT_SO_KU, COT_NGAY_DH, COT_TONG_DU_NO
    ] if c in df_dh.columns]
    
    df_dh = df_dh.sort_values(COT_NGAY_DH)
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_dh[cols]), key=f"dh_{ngay}_chitiet")
    
    ctx.divider()
    render_export_panel(df_dh[cols], f"Đến hạn {ngay} ngày", f"Báo cáo đến hạn {ngay} ngày", username, f"BC_DH{ngay}", ctx, f"dh_{ngay}")


def _render_ty_le_no_xau(ctx, df: pd.DataFrame, username: str) -> None:
    """Render tỷ lệ nợ xấu."""
    if COT_TEN_PGD not in df.columns:
        ctx.error("❌ Không có cột PGD để tổng hợp.")
        return
    
    df_th = df.groupby(COT_TEN_PGD).agg(
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        Nợ_quá_hạn=(COT_DU_NO_QH, "sum"),
        Nợ_khoanh=(COT_DU_NO_KHOANH, "sum"),
    ).reset_index()
    
    df_th["Tổng_nợ_xấu"] = df_th["Nợ_quá_hạn"] + df_th["Nợ_khoanh"]
    df_th["Tỷ_lệ_nợ_xấu_%"] = (df_th["Tổng_nợ_xấu"] / df_th["Tổng_dư_nợ"].replace(0, float("nan")) * 100).round(2).fillna(0)
    
    df_th = df_th.sort_values("Tỷ_lệ_nợ_xấu_%", ascending=False)
    
    ctx.markdown("**📊 Tỷ lệ nợ xấu theo PGD**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_th), key="ty_le_noxau")
    
    ctx.divider()
    render_export_panel(df_th, "Tỷ lệ nợ xấu", "Báo cáo tỷ lệ nợ xấu", username, "BC_NOXAU", ctx, "noxau")
