"""Báo cáo CDTOTKVV - Nhóm E."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import COT_TEN_XA, COT_TEN_TO
from auth import la_phan_he_pgd
from utils import fmt_so, hien_thi_dataframe_phan_trang
from data.cdtotkvv import chuan_hoa_cdtotkvv_phan_tich
from services.tongquan_cdto_service import compute_totkvv_kpi
from services.cdtotkvv_service import loc_df
from ..components.export_panel import render_export_panel

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _chuan_bi_cdto(df: pd.DataFrame | None) -> pd.DataFrame:
    """Chuẩn hóa và giữ một dòng cho mỗi khóa đơn vị + Tổ."""
    out = chuan_hoa_cdtotkvv_phan_tich(df)
    if out.empty:
        return out
    if {"ma_dv", "ma_to"}.issubset(out.columns):
        ma_dv = out["ma_dv"].astype("string").str.strip()
        ma_to = out["ma_to"].astype("string").str.strip()
        day_du = ma_dv.notna() & ma_to.notna() & ma_dv.ne("") & ma_to.ne("")
        trung = pd.DataFrame(
            {"ma_dv": ma_dv, "ma_to": ma_to}, index=out.index
        ).duplicated(keep="last")
        out = out.loc[~(day_du & trung)].copy()
    return out.reset_index(drop=True)


def _cac_cot_diem_co_du_lieu(
    df: pd.DataFrame,
    cols: list[str],
) -> list[str]:
    """Chỉ lấy cột điểm có ít nhất một giá trị số thực sự."""
    return [
        col for col in cols
        if col in df.columns
        and pd.to_numeric(df[col], errors="coerce").notna().any()
    ]


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
    
    if la_phan_he_pgd(role) and pgd_user:
        df_cdtotkvv = loc_df(df_cdtotkvv, "pgd", pgd_user)
    df_cdtotkvv = _chuan_bi_cdto(df_cdtotkvv)
    if df_cdtotkvv.empty:
        ctx.warning("⚠️ Không có Tổ còn dư nợ để lập báo cáo.")
        return

    ctx.markdown("### ⭐ Báo cáo Chấm điểm Tổ TK&VV")
    
    # Các cột điểm chuẩn CDTOTKVV
    diem_cols = _cac_cot_diem_co_du_lieu(df_cdtotkvv, [
        "diem_gdtx", "diem_nqh", "diem_thu_no", "diem_thu_lai",
        "diem_tv_tiengui", "diem_ds_tg", "tong_diem"
    ])
    
    if not diem_cols:
        ctx.error("❌ Không tìm thấy các cột điểm trong dữ liệu CDTOTKVV.")
        ctx.json({"columns": list(df_cdtotkvv.columns)})
        return
    
    # Metrics tổng quan
    kpi = compute_totkvv_kpi(df_cdtotkvv)
    tong_to = kpi["tong_to"]
    avg_diem = kpi["diem_tb"]
    
    c1, c2, c3 = ctx.columns(3)
    c1.metric("Tổng số tổ", fmt_so(tong_to))
    c2.metric("Điểm trung bình", f"{avg_diem:.1f}")
    
    c3.metric("Tổ tốt", fmt_so(kpi["to_tot"]))
    
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
        "ma_dv", "ten_dv", "ten_xa", "ma_to", "ten_to_truong",
        "tong_diem", "xep_loai", "tinh_trang"
    ] if c in df.columns]
    
    ctx.markdown(f"**🏆 Bảng xếp hạng Tổ TK&VV — {fmt_so(len(df_sorted))} tổ**")
    hien_thi_dataframe_phan_trang(df_sorted[display_cols], key="cdto_xephang")
    
    ctx.divider()
    render_export_panel(df_sorted[display_cols], "Xếp hạng", "Báo cáo xếp hạng CDTOTKVV", username, "BC_CDTO_XH", ctx, "cdto_xh")


def _render_phan_tich_diem(ctx, df: pd.DataFrame, username: str) -> None:
    """Render phân tích điểm thành phần."""
    # Tính trung bình các điểm thành phần
    diem_cols = _cac_cot_diem_co_du_lieu(df, [
        "diem_gdtx", "diem_nqh", "diem_thu_no", "diem_thu_lai",
        "diem_tv_tiengui", "diem_ds_tg"
    ])
    analysis_cols = diem_cols.copy()
    if _cac_cot_diem_co_du_lieu(df, ["tong_diem"]):
        analysis_cols.append("tong_diem")
    
    if not analysis_cols:
        ctx.error("❌ Không có dữ liệu điểm để phân tích.")
        return
    
    # Tổng hợp theo xã
    group_col = "ten_xa" if "ten_xa" in df.columns else (
        COT_TEN_XA if COT_TEN_XA in df.columns else (
            "ma_to" if "ma_to" in df.columns else (
                COT_TEN_TO if COT_TEN_TO in df.columns else None
            )
        )
    )
    
    if group_col:
        df_tmp = df.copy()
        nhom = df_tmp[group_col].astype("string").str.strip()
        df_tmp[group_col] = nhom.mask(nhom.isna() | nhom.eq(""), "Chưa xác định")
        agg_dict = {col: "mean" for col in analysis_cols}
        
        df_th = df_tmp.groupby(group_col, dropna=False).agg(agg_dict).reset_index()
        df_th = df_th.sort_values(
            "tong_diem" if "tong_diem" in df_th.columns else analysis_cols[0],
            ascending=False,
        )
        
        ctx.markdown(f"**📊 Điểm trung bình theo {group_col}**")
        
        # Format số
        for col in analysis_cols:
            if col in df_th.columns:
                df_th[col] = df_th[col].round(1)
        
        hien_thi_dataframe_phan_trang(df_th, key="cdto_diem_th")
        
        ctx.divider()
        render_export_panel(df_th, "Điểm thành phần", "Phân tích điểm CDTOTKVV", username, "BC_CDTO_DIEM", ctx, "cdto_diem")
    else:
        ctx.error("❌ Không có cột nhóm địa bàn.")


def _render_theo_dia_ban(ctx, df: pd.DataFrame, username: str) -> None:
    """Render theo địa bàn xã/thôn."""
    group_col = "ten_xa" if "ten_xa" in df.columns else (
        COT_TEN_XA if COT_TEN_XA in df.columns else None
    )
    
    if not group_col:
        ctx.error("❌ Không có cột xã trong dữ liệu.")
        return
    
    df_tmp = df.copy()
    nhom = df_tmp[group_col].astype("string").str.strip()
    df_tmp[group_col] = nhom.mask(nhom.isna() | nhom.eq(""), "Chưa xác định")
    df_tmp["_is_tot"] = df_tmp.get("xep_loai", pd.Series(index=df_tmp.index)).eq("Tốt")
    agg_kwargs = {"Số_tổ": ("ma_to", "nunique")}
    if "tong_diem" in df_tmp.columns:
        agg_kwargs["tong_diem"] = ("tong_diem", "mean")
    if "xep_loai" in df_tmp.columns:
        agg_kwargs["Tổ_tốt"] = ("_is_tot", "sum")

    df_th = df_tmp.groupby(group_col, dropna=False).agg(**agg_kwargs).reset_index()
    df_th = df_th.sort_values("Số_tổ", ascending=False)
    
    # Format
    if "tong_diem" in df_th.columns:
        df_th["tong_diem"] = df_th["tong_diem"].round(1)
    
    ctx.markdown(f"**🏘️ Phân bổ theo {group_col} — {fmt_so(len(df_th))} đơn vị**")
    hien_thi_dataframe_phan_trang(df_th, key="cdto_diaban")
    
    ctx.divider()
    render_export_panel(df_th, "Theo địa bàn", "Báo cáo CDTOTKVV theo địa bàn", username, "BC_CDTO_DB", ctx, "cdto_db")
