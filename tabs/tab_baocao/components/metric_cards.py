"""Component hiển thị metric cards cho báo cáo."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TONG_DU_NO,
    COT_DU_NO_QH,
    COT_SO_KU,
    COT_DNO_NQ11,
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


def _tinh_chi_so_cards(
    df: pd.DataFrame | None,
    df_nq11: pd.DataFrame | None,
) -> dict[str, float | int]:
    """Tính KPI card trên khóa khế ước duy nhất và cột số đã chuẩn hóa."""
    tong_du_no = no_qh = dno_nq11 = 0.0
    so_mon = 0

    if df is not None and not df.empty:
        hstd = df.copy()
        if COT_SO_KU in hstd.columns:
            hstd = hstd.drop_duplicates(subset=[COT_SO_KU], keep="first")
        tong_du_no = (
            float(pd.to_numeric(hstd[COT_TONG_DU_NO], errors="coerce").fillna(0).sum())
            if COT_TONG_DU_NO in hstd.columns else 0.0
        )
        no_qh = (
            float(pd.to_numeric(hstd[COT_DU_NO_QH], errors="coerce").fillna(0).sum())
            if COT_DU_NO_QH in hstd.columns else 0.0
        )
        so_mon = int(
            hstd[COT_SO_KU].nunique() if COT_SO_KU in hstd.columns else len(hstd)
        )

    if df_nq11 is not None and not df_nq11.empty:
        nq11 = df_nq11.copy()
        if COT_SO_KU in nq11.columns:
            nq11 = nq11.drop_duplicates(subset=[COT_SO_KU], keep="first")
        dno_nq11 = (
            float(pd.to_numeric(nq11[COT_DNO_NQ11], errors="coerce").fillna(0).sum())
            if COT_DNO_NQ11 in nq11.columns else 0.0
        )

    return {
        "tong_du_no": tong_du_no,
        "no_qh": no_qh,
        "so_mon": so_mon,
        "tl_no_qh": no_qh / tong_du_no * 100 if tong_du_no > 0 else 0.0,
        "dno_nq11": dno_nq11,
    }


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
    
    chi_so = _tinh_chi_so_cards(df, df_nq11)
    tong_du_no = chi_so["tong_du_no"]
    no_qh = chi_so["no_qh"]
    so_mon = chi_so["so_mon"]
    tl_no_qh = chi_so["tl_no_qh"]
    dno_nq11 = chi_so["dno_nq11"]
    
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
            delta=f"{tl_no_qh:.2f}%" if tl_no_qh > 0 else None,
            delta_color="inverse",
            help="Tỷ lệ nợ quá hạn trên tổng dư nợ"
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
