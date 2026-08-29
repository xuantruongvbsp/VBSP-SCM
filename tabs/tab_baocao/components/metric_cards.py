"""Component hiển thị metric cards cho báo cáo."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_DU_NO_KHOANH,
    COT_MA_KH,
    COT_TEN_KH,
    COT_SO_KU,
    COT_DNO_NQ11,
    COT_GIAI_NGAN_TRONG_NAM,
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


def _valid_text_series(series: pd.Series) -> pd.Series:
    """Chuẩn hóa cột mã/tên để đếm unique, bỏ giá trị rỗng giả."""
    out = series.astype("string").str.strip()
    invalid = out.isna() | out.str.lower().isin({"", "nan", "none", "null", "<na>"})
    return out.loc[~invalid]


def _dedupe_theo_khe_uoc(df: pd.DataFrame) -> pd.DataFrame:
    """Giữ một dòng cho mỗi khế ước nếu dữ liệu có cột Số KU."""
    out = df.copy()
    if COT_SO_KU not in out.columns:
        return out
    so_ku = _valid_text_series(out[COT_SO_KU])
    out = out.loc[so_ku.index].copy()
    out["_so_ku_dem"] = so_ku
    return out.drop_duplicates(subset=["_so_ku_dem"], keep="first")


def _sum_numeric(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())


def _count_khach_hang(df: pd.DataFrame, fallback: int) -> int:
    for col in (COT_MA_KH, COT_TEN_KH):
        if col in df.columns:
            values = _valid_text_series(df[col])
            if not values.empty:
                return int(values.nunique())
    return fallback


def _tinh_chi_so_cards(
    df: pd.DataFrame | None,
    df_nq11: pd.DataFrame | None,
    df_gqvl: pd.DataFrame | None = None,
) -> dict[str, float | int]:
    """Tính KPI card trên khóa khế ước duy nhất và cột số đã chuẩn hóa."""
    tong_du_no = no_qh = no_khoanh = dno_nq11 = dno_gqvl = giai_ngan_gqvl = 0.0
    so_mon = so_kh = so_mon_gqvl = 0

    if df is not None and not df.empty:
        hstd = _dedupe_theo_khe_uoc(df)
        tong_du_no = _sum_numeric(hstd, COT_TONG_DU_NO)
        no_qh = _sum_numeric(hstd, COT_DU_NO_QH)
        no_khoanh = _sum_numeric(hstd, COT_DU_NO_KHOANH)
        so_mon = int(
            hstd["_so_ku_dem"].nunique() if "_so_ku_dem" in hstd.columns else len(hstd)
        )
        so_kh = _count_khach_hang(hstd, so_mon)

    if df_nq11 is not None and not df_nq11.empty:
        nq11 = _dedupe_theo_khe_uoc(df_nq11)
        dno_nq11 = _sum_numeric(nq11, COT_DNO_NQ11)

    if df_gqvl is not None and not df_gqvl.empty:
        gqvl = _dedupe_theo_khe_uoc(df_gqvl)
        dno_gqvl = _sum_numeric(gqvl, COT_TONG_DU_NO)
        if dno_gqvl == 0:
            dno_gqvl = sum(
                _sum_numeric(gqvl, col)
                for col in (COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH)
            )
        giai_ngan_gqvl = _sum_numeric(gqvl, COT_GIAI_NGAN_TRONG_NAM)
        so_mon_gqvl = int(
            gqvl["_so_ku_dem"].nunique() if "_so_ku_dem" in gqvl.columns else len(gqvl)
        )

    return {
        "tong_du_no": tong_du_no,
        "no_qh": no_qh,
        "no_khoanh": no_khoanh,
        "no_rui_ro": no_qh + no_khoanh,
        "so_mon": so_mon,
        "so_kh": so_kh,
        "tl_no_qh": no_qh / tong_du_no * 100 if tong_du_no > 0 else 0.0,
        "tl_no_khoanh": no_khoanh / tong_du_no * 100 if tong_du_no > 0 else 0.0,
        "tl_no_rui_ro": (no_qh + no_khoanh) / tong_du_no * 100 if tong_du_no > 0 else 0.0,
        "du_no_bq_mon": tong_du_no / so_mon if so_mon > 0 else 0.0,
        "dno_nq11": dno_nq11,
        "dno_gqvl": dno_gqvl,
        "giai_ngan_gqvl": giai_ngan_gqvl,
        "so_mon_gqvl": so_mon_gqvl,
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
    
    chi_so = _tinh_chi_so_cards(df, df_nq11, df_gqvl)
    tong_du_no = chi_so["tong_du_no"]
    no_qh = chi_so["no_qh"]
    no_khoanh = chi_so["no_khoanh"]
    no_rui_ro = chi_so["no_rui_ro"]
    so_mon = chi_so["so_mon"]
    so_kh = chi_so["so_kh"]
    tl_no_qh = chi_so["tl_no_qh"]
    tl_no_khoanh = chi_so["tl_no_khoanh"]
    tl_no_rui_ro = chi_so["tl_no_rui_ro"]
    du_no_bq_mon = chi_so["du_no_bq_mon"]
    dno_nq11 = chi_so["dno_nq11"]
    dno_gqvl = chi_so["dno_gqvl"]
    giai_ngan_gqvl = chi_so["giai_ngan_gqvl"]
    
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
            "Nợ khoanh",
            f"{_fmt_ty(no_khoanh)} tỷ",
            delta=f"{tl_no_khoanh:.2f}%" if tl_no_khoanh > 0 else None,
            delta_color="inverse",
            help="Tỷ lệ nợ khoanh trên tổng dư nợ"
        )
    
    with c4:
        st.metric(
            "Nợ rủi ro",
            f"{_fmt_ty(no_rui_ro)} tỷ",
            delta=f"{tl_no_rui_ro:.2f}%" if tl_no_rui_ro > 0 else None,
            delta_color="inverse",
            help="Tổng nợ quá hạn và nợ khoanh"
        )

    c5, c6, c7, c8 = ctx.columns(4)

    with c5:
        st.metric(
            "Số khách hàng",
            fmt_so(so_kh),
            help="Số khách hàng duy nhất theo Mã KH; nếu thiếu mã thì dùng Tên KH"
        )

    with c6:
        st.metric(
            "Số món vay",
            fmt_so(so_mon),
            delta=f"{_fmt_ty(du_no_bq_mon)} tỷ/món" if du_no_bq_mon > 0 else None,
            help="Tổng số khế ước duy nhất; delta là dư nợ bình quân mỗi món"
        )

    with c7:
        st.metric(
            "DNO NQ11",
            f"{_fmt_ty(dno_nq11)} tỷ",
            help="Dư nợ Nghị quyết 11"
        )

    with c8:
        st.metric(
            "GQVL năm",
            f"{_fmt_ty(dno_gqvl)} tỷ",
            delta=f"GN {_fmt_ty(giai_ngan_gqvl)} tỷ" if giai_ngan_gqvl > 0 else None,
            help="Dư nợ GQVL; delta là giải ngân GQVL trong năm nếu dữ liệu có cột này"
        )
