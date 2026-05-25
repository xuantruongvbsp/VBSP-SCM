"""Báo cáo CDTOTKVV - Nhóm E."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TEN_TO,
)
from auth import la_phan_he_pgd
from utils import fmt_so, hien_thi_dataframe_phan_trang
from ..components.export_panel import render_export_panel

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def render_cdtotkvv(
    tab: DeltaGenerator | None = None,
    df_cdtotkvv: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    **kwargs
) -> None:
    """
    Render báo cáo CDTOTKVV.
    
    Args:
        tab: Streamlit container
        df_cdtotkvv: DataFrame CDTOTKVV
        role: Role người dùng
        pgd_user: Tên PGD
        username: Username
    """
    ctx = tab if tab is not None else st
    
    if df_cdtotkvv is None or df_cdtotkvv.empty:
        ctx.warning("⚠️ Chưa có dữ liệu CDTOTKVV.")
        return
    
    ctx.markdown("### ⭐ Báo cáo Chấm điểm Tổ TK&VV")
    
    # Các cột điểm chuẩn CDTOTKVV
    diem_cols = [c for c in [
        "diem_gdtx", "diem_nqh", "diem_thu_no", "diem_thu_lai",
        "diem_tv_tiengui", "diem_ds_tg", "tong_diem"
    ] if c in df_cdtotkvv.columns]
    
    if not diem_cols:
        ctx.error("❌ Không tìm thấy các cột điểm trong dữ liệu CDTOTKVV.")
        ctx.json({"columns": list(df_cdtotkvv.columns)})
        return
    
    # Metrics tổng quan
    tong_to = len(df_cdtotkvv)
    avg_diem = df_cdtotkvv["tong_diem"].mean() if "tong_diem" in df_cdtotkvv.columns else 0
    
    c1, c2, c3 = ctx.columns(3)
    c1.metric("Tổng số tổ", fmt_so(tong_to))
    c2.metric("Điểm trung bình", f"{avg_diem:.1f}")
    
    if "xep_loai" in df_cdtotkvv.columns:
        xl_counts = df_cdtotkvv["xep_loai"].value_counts()
        c3.metric("Tổ xuất sắc", fmt_so(xl_counts.get("Xuất sắc", 0)))
    
    # Chọn loại báo cáo
    loai_bc = ctx.radio(
        "Loại báo cáo",
        ["🏆 Xếp hạng tổng hợp", "📊 Phân tích điểm thành phần", "🏘️ Theo địa bàn"],
        horizontal=True,
        key="cdto_loai_bc",
    )
    
    ctx.divider()
    
    if loai_bc == "🏆 Xếp hạng tổng hợp":
        _render_xep_hang(ctx, df_cdtotkvv, username)
    elif loai_bc == "📊 Phân tích điểm thành phần":
        _render_phan_tich_diem(ctx, df_cdtotkvv, username)
    else:
        _render_theo_dia_ban(ctx, df_cdtotkvv, username)


def _render_xep_hang(ctx, df: pd.DataFrame, username: str) -> None:
    """Render bảng xếp hạng."""
    # Sắp xếp theo tổng điểm giảm dần
    sort_col = "tong_diem" if "tong_diem" in df.columns else "diem_gdtx"
    df_sorted = df.sort_values(sort_col, ascending=False)
    
    # Chọn cột hiển thị
    display_cols = [c for c in [
        "ma_dv", "ten_dv", "ten_xa", "ten_to_truong",
        "tong_diem", "xep_loai", "tinh_trang"
    ] if c in df.columns]
    
    ctx.markdown(f"**🏆 Bảng xếp hạng Tổ TK&VV — {fmt_so(len(df_sorted))} tổ**")
    hien_thi_dataframe_phan_trang(df_sorted[display_cols], key="cdto_xephang")
    
    ctx.divider()
    render_export_panel(df_sorted[display_cols], "Xếp hạng", "Báo cáo xếp hạng CDTOTKVV", username, "BC_CDTO_XH", ctx, "cdto_xh")


def _render_phan_tich_diem(ctx, df: pd.DataFrame, username: str) -> None:
    """Render phân tích điểm thành phần."""
    # Tính trung bình các điểm thành phần
    diem_cols = [c for c in [
        "diem_gdtx", "diem_nqh", "diem_thu_no", "diem_thu_lai",
        "diem_tv_tiengui", "diem_ds_tg"
    ] if c in df.columns]
    
    if not diem_cols:
        ctx.error("❌ Không có dữ liệu điểm thành phần.")
        return
    
    # Tổng hợp theo xã
    group_col = COT_TEN_XA if COT_TEN_XA in df.columns else (
        COT_TEN_TO if COT_TEN_TO in df.columns else None
    )
    
    if group_col:
        agg_dict = {col: "mean" for col in diem_cols}
        if "tong_diem" in df.columns:
            agg_dict["tong_diem"] = "mean"
        
        df_th = df.groupby(group_col).agg(agg_dict).reset_index()
        df_th = df_th.sort_values("tong_diem" if "tong_diem" in df_th.columns else diem_cols[0], ascending=False)
        
        ctx.markdown(f"**📊 Điểm trung bình theo {group_col}**")
        
        # Format số
        for col in diem_cols + (["tong_diem"] if "tong_diem" in df_th.columns else []):
            if col in df_th.columns:
                df_th[col] = df_th[col].round(1)
        
        hien_thi_dataframe_phan_trang(df_th, key="cdto_diem_th")
        
        ctx.divider()
        render_export_panel(df_th, "Điểm thành phần", "Phân tích điểm CDTOTKVV", username, "BC_CDTO_DIEM", ctx, "cdto_diem")
    else:
        ctx.error("❌ Không có cột nhóm địa bàn.")


def _render_theo_dia_ban(ctx, df: pd.DataFrame, username: str) -> None:
    """Render theo địa bàn xã/thôn."""
    group_col = COT_TEN_XA if COT_TEN_XA in df.columns else None
    
    if not group_col:
        ctx.error("❌ Không có cột xã trong dữ liệu.")
        return
    
    # Tổng hợp theo xã
    agg_dict = {
        "ma_to": "count",
    }
    if "tong_diem" in df.columns:
        agg_dict["tong_diem"] = "mean"
    if "xep_loai" in df.columns:
        # Đếm số tổ xuất sắc
        df["is_xuatsac"] = df["xep_loai"].str.contains("xuất sắc", case=False, na=False)
        agg_dict["Tổ_xuất_sắc"] = ("is_xuatsac", "sum")
    
    df_th = df.groupby(group_col).agg(agg_dict).reset_index()
    df_th = df_th.rename(columns={"ma_to": "Số_tổ"})
    df_th = df_th.sort_values("Số_tổ", ascending=False)
    
    # Format
    if "tong_diem" in df_th.columns:
        df_th["tong_diem"] = df_th["tong_diem"].round(1)
    
    ctx.markdown(f"**🏘️ Phân bổ theo {group_col} — {fmt_so(len(df_th))} đơn vị**")
    hien_thi_dataframe_phan_trang(df_th, key="cdto_diaban")
    
    ctx.divider()
    render_export_panel(df_th, "Theo địa bàn", "Báo cáo CDTOTKVV theo địa bàn", username, "BC_CDTO_DB", ctx, "cdto_db")
