"""Result Card component for displaying search results."""

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON,
    COT_TEN_CT, COT_TONG_DU_NO, COT_DU_NO_QH, COT_NGUON_VON, NGUON_VON_LABEL,
    COT_TINH_TRANG, COT_NGAY_VAY, COT_THOI_HAN, COT_LAI_SUAT,
    COT_NGAY_DH_GDXA, COT_NGAY_GN_DAU_TIEN,
)
from utils import fmt_tien, fmt_ty, vn

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _get_badge_styles(du_no_qh: float, is_nq11: bool, is_gqvl: bool) -> tuple[str, str]:
    """Get badge HTML and border color based on status."""
    badges = []
    border_color = "#42A5F5"  # Default blue
    
    if du_no_qh > 0:
        badges.append(
            '<span style="background:#2D0D14;color:#EF9A9A;border:1px solid #C62828;'
            'border-radius:10px;padding:2px 8px;font-size:.7rem;font-weight:700;margin-left:4px">'
            '⚠️ Quá hạn</span>'
        )
        border_color = "#EF5350"  # Red for quá hạn
    
    if is_nq11:
        badges.append(
            '<span style="background:#1B5E20;color:#81C784;border:1px solid #2E7D32;'
            'border-radius:10px;padding:2px 8px;font-size:.7rem;font-weight:700;margin-left:4px">'
            '✨ NQ11</span>'
        )
    
    if is_gqvl:
        badges.append(
            '<span style="background:#0D47A1;color:#90CAF9;border:1px solid #1565C0;'
            'border-radius:10px;padding:2px 8px;font-size:.7rem;font-weight:700;margin-left:4px">'
            '📋 GQVL</span>'
        )
    
    return "".join(badges), border_color


def _format_du_no(value: float) -> str:
    """Format dư nợ with color coding."""
    if pd.isna(value) or value == 0:
        return "<span style='color:#9E9E9E'>—</span>"
    formatted = fmt_tien(value)
    return f"<span style='font-weight:600;color:#4CAF50'>{formatted} tr</span>"


def render_result_card(
    hs: pd.Series,
    is_nq11: bool = False,
    is_gqvl: bool = False,
    on_detail_click: str = None,
    container: "DeltaGenerator" = None,
) -> None:
    """
    Render a single result card for a hồ sơ.
    
    Args:
        hs: Series containing hồ sơ data
        is_nq11: Whether this hồ sơ is in NQ11
        is_gqvl: Whether this hồ sơ is in GQVL
        on_detail_click: Session state key to store selected Số KU
        container: Optional container to render in (defaults to st)
    """
    ctx = container if container is not None else st
    
    # Get values
    ten_kh = str(hs.get(COT_TEN_KH, "—"))
    ma_kh = str(hs.get(COT_MA_KH, "—"))
    so_ku = str(hs.get(COT_SO_KU, "—"))
    ten_pgd = str(hs.get(COT_TEN_PGD, "—"))
    ten_xa = str(hs.get(COT_TEN_XA, "—"))
    ten_thon = str(hs.get(COT_TEN_THON, "—"))
    ten_ct = str(hs.get(COT_TEN_CT, "—"))
    tong_du_no = float(hs.get(COT_TONG_DU_NO, 0) or 0)
    du_no_qh = float(hs.get(COT_DU_NO_QH, 0) or 0)
    nguon_von = str(hs.get(COT_NGUON_VON, "—"))
    def _s(val, default="—") -> str:
        if val is None:
            return default
        try:
            if pd.isna(val):
                return default
        except (TypeError, ValueError):
            pass
        return str(val)

    ngay_vay = _s(hs.get(COT_NGAY_VAY))
    thoi_han = _s(hs.get(COT_THOI_HAN))
    # Format thời hạn: "60.0" → "60", giữ nguyên nếu không phải số
    if thoi_han != "—":
        try:
            _th = float(thoi_han)
            thoi_han = str(int(_th)) if _th == int(_th) else thoi_han
        except (ValueError, TypeError):
            pass
    else:
        # Fallback: Ngày ĐH theo GDXA − Ngày GN đầu tiên (tháng)
        _ngay_gn = pd.to_datetime(hs.get(COT_NGAY_GN_DAU_TIEN), dayfirst=True, errors="coerce")
        _ngay_dh = pd.to_datetime(hs.get(COT_NGAY_DH_GDXA), dayfirst=True, errors="coerce")
        if pd.notna(_ngay_gn) and pd.notna(_ngay_dh):
            _months = (_ngay_dh.year - _ngay_gn.year) * 12 + (_ngay_dh.month - _ngay_gn.month)
            if _months > 0:
                thoi_han = str(_months)
    _lai_suat_raw = hs.get(COT_LAI_SUAT)
    try:
        lai_suat = f"{float(_lai_suat_raw):.3f}".rstrip("0").rstrip(".").replace(".", ",")
    except (ValueError, TypeError):
        lai_suat = _s(_lai_suat_raw)
    thoi_han_str = f"{thoi_han} tháng" if thoi_han != "—" else "—"
    
    # Build badges
    badges, border_color = _get_badge_styles(du_no_qh, is_nq11, is_gqvl)
    
    # Format nguon von
    nv_label = NGUON_VON_LABEL.get(nguon_von, nguon_von)
    
    # Card HTML
    card_html = f'''
    <div style="
        background: linear-gradient(145deg, #1E2130 0%, #252a3d 100%);
        border-radius: 12px;
        border-left: 4px solid {border_color};
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    ">
        <!-- Header -->
        <div style="margin-bottom: 12px;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #E0E0E0; display: flex; align-items: center;">
                👤 {ten_kh}
                {badges}
            </div>
            <div style="font-size: 0.85rem; color: #9E9E9E; margin-top: 4px;">
                {ma_kh} · Số KU: {so_ku}
            </div>
        </div>
        
        <!-- Info Grid -->
        <div style="
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.9rem;
            margin-bottom: 12px;
        ">
            <div>
                <span style="color: #9E9E9E;">📍</span>
                <span style="color: #BDBDBD;">{ten_pgd}</span>
                {f'<br><span style="color: #757575; font-size: 0.8rem; margin-left: 20px;">→ {ten_xa}</span>' if ten_xa != "—" else ""}
                {f'<br><span style="color: #757575; font-size: 0.8rem; margin-left: 20px;">→ {ten_thon}</span>' if ten_thon != "—" else ""}
            </div>
            <div>
                <span style="color: #9E9E9E;">📑</span>
                <span style="color: #BDBDBD;">{ten_ct[:35]}{'...' if len(ten_ct) > 35 else ''}</span>
            </div>
            <div>
                <span style="color: #9E9E9E;">💰</span>
                {_format_du_no(tong_du_no)}
                {f'<br><span style="color: #EF5350; font-size: 0.8rem; margin-left: 20px;">QH: {fmt_tien(du_no_qh)}</span>' if du_no_qh > 0 else ""}
            </div>
            <div>
                <span style="color: #9E9E9E;">🏦</span>
                <span style="color: #BDBDBD;">{nguon_von} - {nv_label}</span>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 12px;
            border-top: 1px solid #37474F;
            font-size: 0.8rem;
            color: #9E9E9E;
        ">
            <span>📅 {ngay_vay} · ⏱️ {thoi_han_str} · 📊 {lai_suat}%</span>
        </div>
    </div>
    '''
    
    ctx.markdown(card_html, unsafe_allow_html=True)
    
    # Detail button
    btn_key = f"tc_detail_{so_ku}_{hash(ten_kh) % 10000}"
    if ctx.button("🔍 Xem chi tiết", key=btn_key, use_container_width=True):
        if on_detail_click:
            st.session_state[on_detail_click] = so_ku
        st.rerun()


def render_result_grid(
    df: pd.DataFrame,
    df_nq11: pd.DataFrame | None = None,
    df_gqvl: pd.DataFrame | None = None,
    columns: int = 3,
    on_detail_click: str = "tc_selected_ku",
    container: "DeltaGenerator" = None,
) -> None:
    """
    Render a grid of result cards.
    
    Args:
        df: DataFrame with filtered results
        df_nq11: NQ11 data for badges
        df_gqvl: GQVL data for badges
        columns: Number of columns in grid (1-4)
        on_detail_click: Session state key for detail click
        container: Optional container
    """
    ctx = container if container is not None else st
    
    if df.empty:
        ctx.info("ℹ️ Không có kết quả phù hợp với bộ lọc.")
        return
    
    # Dùng cột __is_nq11/__is_gqvl nếu đã được enrich (ưu tiên)
    _use_enriched = "__is_nq11" in df.columns and "__is_gqvl" in df.columns
    # Fallback: build set nếu chưa enrich
    nq11_set: set[str] = set()
    gqvl_set: set[str] = set()
    if not _use_enriched:
        if df_nq11 is not None and "Số khế ước" in df_nq11.columns:
            nq11_set = set(df_nq11["Số khế ước"].astype(str).str.strip())
        if df_gqvl is not None and "Số khế ước" in df_gqvl.columns:
            gqvl_set = set(df_gqvl["Số khế ước"].astype(str).str.strip())
    
    # Render cards
    so_ku_col = COT_SO_KU if COT_SO_KU in df.columns else None
    
    # Use columns layout
    cols = ctx.columns(columns)
    
    for idx, (_, row) in enumerate(df.iterrows()):
        col_idx = idx % columns
        so_ku = str(row.get(so_ku_col, "")).strip() if so_ku_col else ""
        
        if _use_enriched:
            is_nq11 = bool(row.get("__is_nq11", False))
            is_gqvl = bool(row.get("__is_gqvl", False))
        else:
            is_nq11 = so_ku in nq11_set if so_ku else False
            is_gqvl = so_ku in gqvl_set if so_ku else False
        
        with cols[col_idx]:
            render_result_card(
                hs=row,
                is_nq11=is_nq11,
                is_gqvl=is_gqvl,
                on_detail_click=on_detail_click,
            )
