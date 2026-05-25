"""Component hiển thị metric cards cho báo cáo."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_DU_NO_KHOANH,
    COT_DNO_NQ11,
    COT_NQ11_NO_QH,
)
from utils import fmt_so, vn

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _fmt_ty(x: float) -> str:
    """Format số tiền VND sang tỷ đồng (dùng cho metric card)."""
    try:
        x = float(x)
        if abs(x) > 0:
            return vn(x / 1_000_000_000, 1)
        return "0"
    except Exception:
        return "—"


def render_metric_cards(
    df: pd.DataFrame | None = None,
    df_nq11: pd.DataFrame | None = None,
    df_gqvl: pd.DataFrame | None = None,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị metric cards tổng quan từ các nguồn dữ liệu.
    
    Args:
        df: DataFrame HSTD
        df_nq11: DataFrame NQ11
        df_gqvl: DataFrame GQVL
        container: Streamlit container (optional)
    """
    ctx = container if container is not None else st
    
    # Tính toán metrics từ HSTD
    if df is not None and not df.empty:
        tong_du_no = df[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df.columns else 0
        no_qh = df[COT_DU_NO_QH].sum() if COT_DU_NO_QH in df.columns else 0
        no_khoanh = df[COT_DU_NO_KHOANH].sum() if COT_DU_NO_KHOANH in df.columns else 0
        so_mon = len(df)
        tl_no_xau = (no_qh + no_khoanh) / tong_du_no * 100 if tong_du_no > 0 else 0
    else:
        tong_du_no = no_qh = no_khoanh = so_mon = tl_no_xau = 0
    
    # Tính toán metrics từ NQ11
    if df_nq11 is not None and not df_nq11.empty:
        dno_nq11 = df_nq11[COT_DNO_NQ11].sum() if COT_DNO_NQ11 in df_nq11.columns else 0
        nq11_qh = df_nq11[COT_NQ11_NO_QH].sum() if COT_NQ11_NO_QH in df_nq11.columns else 0
        so_mon_nq11 = len(df_nq11[df_nq11[COT_DNO_NQ11] > 0]) if COT_DNO_NQ11 in df_nq11.columns else 0
    else:
        dno_nq11 = nq11_qh = so_mon_nq11 = 0
    
    # Hiển thị cards
    ctx.markdown("#### 📊 Chỉ số tổng quan")
    
    c1, c2, c3, c4 = ctx.columns(4)
    
    with c1:
        st.metric(
            "Tổng dư nợ",
            f"{_fmt_ty(tong_du_no)} tỷ",
            help="Tổng dư nợ từ dữ liệu HSTD"
        )
    
    with c2:
        st.metric(
            "Nợ quá hạn",
            f"{_fmt_ty(no_qh)} tỷ",
            delta=f"{tl_no_xau:.2f}%" if tl_no_xau > 0 else None,
            delta_color="inverse",
            help="Dư nợ quá hạn + nợ khoanh"
        )
    
    with c3:
        st.metric(
            "Số món vay",
            fmt_so(so_mon),
            help="Tổng số món vay"
        )
    
    with c4:
        st.metric(
            "DNO NQ11",
            f"{_fmt_ty(dno_nq11)} tỷ",
            help="Dư nợ Nghị quyết 11"
        )
    
    ctx.divider()
