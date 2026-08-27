"""Báo cáo NQ11 - Nhóm C."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_XA,
    COT_TEN_CT,
    COT_DNO_NQ11,
    COT_NQ11_NO_TH,
    COT_NQ11_NO_QH,
    COT_NQ11_MA_KH,
    COT_NQ11_TEN_KH,
    COT_SDT,
    COT_SO_KU,
)
from auth import la_phan_he_pgd
from utils import fmt_so, hien_thi_dataframe_phan_trang, vn
from ..components.export_panel import render_export_panel

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


_NHOM_KHONG_XAC_DINH = "Chưa xác định"


def _chuan_bi_nq11(df: pd.DataFrame | None) -> pd.DataFrame:
    """Chuẩn hóa NQ11 và chỉ giữ một dòng cho mỗi khế ước hợp lệ."""
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    out = df.copy()
    for col in (COT_DNO_NQ11, COT_NQ11_NO_TH, COT_NQ11_NO_QH):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    if COT_SO_KU in out.columns:
        so_ku = out[COT_SO_KU].astype("string").str.strip()
        hop_le = so_ku.notna() & ~so_ku.str.lower().isin(
            {"", "nan", "none", "null", "<na>"}
        )
        out = out.loc[hop_le].copy()
        out[COT_SO_KU] = so_ku.loc[hop_le]
        out = out.drop_duplicates(subset=[COT_SO_KU], keep="first")
    return out.reset_index(drop=True)


def _fmt_df_trieu(df: pd.DataFrame) -> pd.DataFrame:
    """Format cột tiền sang triệu đồng."""
    d = df.copy()
    tien_cols = [
        COT_DNO_NQ11, COT_NQ11_NO_TH, COT_NQ11_NO_QH,
        "DNO_NQ11", "Nợ_trong_hạn", "Nợ_quá_hạn",
    ]
    for col in tien_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
    return d


def render_nq11(
    tab: DeltaGenerator | None = None,
    df_nq11: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    **kwargs
) -> None:
    """
    Render báo cáo NQ11.
    
    Args:
        tab: Streamlit container
        df_nq11: DataFrame NQ11
        role: Role người dùng
        pgd_user: Tên PGD
        username: Username
    """
    ctx = tab if tab is not None else st
    
    if df_nq11 is None or df_nq11.empty:
        ctx.warning("⚠️ Chưa có dữ liệu NQ11.")
        ctx.info("Vui lòng upload file NQ11 qua tab Upload dữ liệu.")
        return
    
    df_nq11 = _chuan_bi_nq11(df_nq11)
    if df_nq11.empty or COT_DNO_NQ11 not in df_nq11.columns:
        ctx.warning("⚠️ Dữ liệu NQ11 không có khế ước/dư nợ hợp lệ.")
        return

    ctx.markdown("### 📑 Báo cáo NQ11")
    
    # Metrics tổng quan
    co_nq11 = df_nq11.loc[df_nq11[COT_DNO_NQ11] > 0].copy()
    tong_mon = co_nq11[COT_SO_KU].nunique() if COT_SO_KU in co_nq11 else len(co_nq11)
    tong_kh = (
        co_nq11[COT_NQ11_MA_KH].astype("string").str.strip().nunique()
        if COT_NQ11_MA_KH in co_nq11 else 0
    )
    
    c1, c2, c3, c4 = ctx.columns(4)
    c1.metric("Số món NQ11", fmt_so(tong_mon))
    c2.metric("Số KH NQ11", fmt_so(tong_kh))
    c3.metric("DNO NQ11", f"{vn(co_nq11[COT_DNO_NQ11].sum()/1e9, 1)} tỷ")
    c4.metric(
        "Nợ quá hạn NQ11",
        f"{vn(co_nq11[COT_NQ11_NO_QH].sum()/1e9, 3)} tỷ"
        if COT_NQ11_NO_QH in co_nq11 else "0 tỷ",
    )
    
    # Chọn loại báo cáo
    loai_bc = ctx.radio(
        "Loại báo cáo",
        ["📊 Tổng hợp theo chương trình", "📋 Chi tiết món NQ11"],
        horizontal=True,
        key="nq11_loai_bc",
    )
    
    ctx.divider()
    
    if loai_bc == "📊 Tổng hợp theo chương trình":
        _render_tong_hop_ct(ctx, co_nq11, username)
    else:
        _render_chi_tiet(ctx, co_nq11, "Chi tiết món NQ11", username)


def _render_tong_hop_ct(ctx, df: pd.DataFrame, username: str) -> None:
    """Render tổng hợp theo chương trình."""
    if COT_TEN_CT not in df.columns:
        ctx.error("❌ Không có cột chương trình.")
        return
    
    df_tmp = df.copy()
    nhom = df_tmp[COT_TEN_CT].astype("string").str.strip()
    df_tmp[COT_TEN_CT] = nhom.mask(nhom.isna() | nhom.eq(""), _NHOM_KHONG_XAC_DINH)
    df_th = df_tmp.groupby(COT_TEN_CT, dropna=False).agg(
        Số_món=(COT_SO_KU, "nunique"),
        DNO_NQ11=(COT_DNO_NQ11, "sum"),
        Nợ_trong_hạn=(COT_NQ11_NO_TH, "sum"),
        Nợ_quá_hạn=(COT_NQ11_NO_QH, "sum"),
    ).reset_index().sort_values("DNO_NQ11", ascending=False)
    
    ctx.markdown(f"**📊 Tổng hợp theo chương trình — {fmt_so(len(df_th))} nhóm**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df_th), key="nq11_th_ct")
    
    ctx.divider()
    render_export_panel(df_th, "Tổng hợp NQ11", "Báo cáo NQ11 tổng hợp", username, "BC_NQ11_TH", ctx, "nq11_th")


def _render_chi_tiet(ctx, df: pd.DataFrame, tieu_de: str, username: str) -> None:
    """Render danh sách chi tiết."""
    if df.empty:
        ctx.info(f"📭 Không có dữ liệu cho {tieu_de}.")
        return
    
    cols = [c for c in [
        COT_TEN_XA, COT_NQ11_MA_KH, COT_NQ11_TEN_KH, COT_SDT,
        COT_SO_KU, COT_TEN_CT, COT_DNO_NQ11, COT_NQ11_NO_TH, COT_NQ11_NO_QH
    ] if c in df.columns]
    
    ctx.markdown(f"**📋 {tieu_de} — {fmt_so(len(df))} món**")
    hien_thi_dataframe_phan_trang(_fmt_df_trieu(df[cols]), key=f"nq11_ct_{tieu_de.replace(' ', '_')}")
    
    ctx.divider()
    render_export_panel(df[cols], tieu_de, f"Báo cáo {tieu_de}", username, f"BC_NQ11_{tieu_de.replace(' ', '_')}", ctx, f"nq11_{tieu_de.replace(' ', '_')}")
