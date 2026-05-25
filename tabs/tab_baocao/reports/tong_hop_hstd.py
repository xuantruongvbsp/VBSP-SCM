"""Báo cáo tổng hợp từ HSTD - Nhóm A."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TEN_THON,
    COT_TEN_CT,
    COT_NGUON_VON,
    COT_DVUT,
    COT_TEN_TO,
    COT_MA_KH,
    COT_SO_KU,
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
)
from auth import la_phan_he_pgd, la_phan_he_cn
from utils import fmt_ty, fmt_so, hien_thi_dataframe_phan_trang, vn
from ..components.export_panel import render_export_panel
from state_manager import SCMStateManager
from logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _fmt_df_trieu(df: pd.DataFrame) -> pd.DataFrame:
    """Format cột tiền sang triệu đồng."""
    d = df.copy()
    tien_cols = ["Tổng_dư_nợ", "Dư_nợ_trong_hạn", "Dư_nợ_quá_hạn"]
    for col in tien_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
    return d


def render_tong_hop_hstd(
    tab: DeltaGenerator | None = None,
    df: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    **kwargs
) -> None:
    """
    Render báo cáo tổng hợp từ HSTD.
    
    Args:
        tab: Streamlit container
        df: DataFrame HSTD
        role: Role người dùng
        pgd_user: Tên PGD (nếu là role PGD)
        username: Username
    """
    ctx = tab if tab is not None else st
    state = SCMStateManager()
    
    if df is None or df.empty:
        ctx.warning("⚠️ Chưa có dữ liệu HSTD.")
        return
    
    ctx.markdown("### 📁 Báo cáo Tổng hợp từ HSTD")
    
    # Chọn loại tổng hợp
    loai_th = ctx.radio(
        "Tổng hợp theo",
        ["🏢 Theo PGD", "🏘️ Theo Xã", "🏡 Theo Thôn/ấp", "📌 Theo Chương trình", 
         "🏦 Theo Nguồn vốn", "🤝 Theo ĐVUT", "👤 Theo CBTD/Tổ"],
        horizontal=True,
        key="th_loai_hstd",
    )
    
    # Xác định cột nhóm
    group_col = {
        "🏢 Theo PGD": COT_TEN_PGD,
        "🏘️ Theo Xã": COT_TEN_XA,
        "🏡 Theo Thôn/ấp": COT_TEN_THON,
        "📌 Theo Chương trình": COT_TEN_CT,
        "🏦 Theo Nguồn vốn": COT_NGUON_VON,
        "🤝 Theo ĐVUT": COT_DVUT,
        "👤 Theo CBTD/Tổ": COT_TEN_TO,
    }.get(loai_th, COT_TEN_PGD)
    
    # Kiểm tra cột tồn tại
    if group_col not in df.columns:
        ctx.error(f"❌ Không có cột {group_col} trong dữ liệu.")
        return
    
    # Bộ lọc cho PGD
    df_filtered = df.copy()
    if la_phan_he_pgd(role) and pgd_user:
        if COT_TEN_PGD in df_filtered.columns:
            df_filtered = df_filtered[df_filtered[COT_TEN_PGD] == pgd_user]
            ctx.info(f"📍 Đang xem báo cáo của PGD: **{pgd_user}**")
    
    # Tạo báo cáo tổng hợp
    try:
        df_th = df_filtered.groupby(group_col).agg(
            Số_KH=(COT_MA_KH, "nunique"),
            Số_món=(COT_SO_KU, "nunique"),
            Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
            Dư_nợ_trong_hạn=(COT_DU_NO_TH, "sum"),
            Dư_nợ_quá_hạn=(COT_DU_NO_QH, "sum"),
        ).reset_index()
        
        # Tính tỷ lệ QH
        df_th["Tỷ_lệ_QH_%"] = (
            df_th["Dư_nợ_quá_hạn"] / df_th["Tổng_dư_nợ"].replace(0, float("nan")) * 100
        ).round(2).fillna(0)
        
        # Sắp xếp
        df_th = df_th.sort_values("Tổng_dư_nợ", ascending=False)
        
        # Hiển thị
        ctx.markdown(f"**📊 Tổng hợp theo {group_col} — {fmt_so(len(df_th))} nhóm**")
        
        hien_thi_dataframe_phan_trang(
            _fmt_df_trieu(df_th),
            key="th_hstd_table",
        )
        
        # Export
        ctx.divider()
        render_export_panel(
            df_export=df_th,
            sheet_name="Tổng hợp HSTD",
            tieu_de=f"Báo cáo tổng hợp theo {group_col}",
            username=username,
            prefix_file=f"BC_TH_{group_col.replace(' ', '_')}",
            container=ctx,
            key_suffix="th_hstd",
        )
        
    except Exception as e:
        logger.error("tong_hop_hstd: lỗi tạo báo cáo — %s", e, exc_info=True)
        ctx.error(f"❌ Lỗi tạo báo cáo: {e}")
