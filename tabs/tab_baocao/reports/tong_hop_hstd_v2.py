"""Báo cáo tổng hợp từ HSTD v2 - UX nâng cao."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON, COT_TEN_CT,
    COT_NGUON_VON, COT_DVUT, COT_TEN_TO,
    COT_MA_KH, COT_SO_KU, COT_TONG_DU_NO,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH,
)
from auth import la_phan_he_pgd
from utils import fmt_so

from ..components.inline_filter import (
    chuan_bi_du_lieu_bao_cao,
    chuan_hoa_nhom_nguon_von,
    render_combined_filter_search,
    render_inline_filter,
    render_nguon_von_filter,
)
from ..components.sticky_table import render_bang_chi_tiet_html
from ..components.quick_export import render_quick_export_buttons
from ..components.tooltip import render_header_with_tooltip, render_formula_reference
from ..components.alert_suggestion import render_combined_alerts_suggestions
from logger import get_logger

logger = get_logger(__name__)

_NHOM_KHONG_XAC_DINH = "Chưa xác định"

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _tao_tong_hop_theo_nhom(
    df_filtered: pd.DataFrame,
    selected_report: str,
    group_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Chuẩn hóa và tổng hợp HSTD; không làm rơi dòng thiếu tên nhóm."""
    df_group = (
        chuan_hoa_nhom_nguon_von(df_filtered)
        if selected_report == "nv"
        else df_filtered
    ).copy()

    nhom = df_group[group_col].astype("string").str.strip()
    df_group[group_col] = nhom.mask(nhom.isna() | nhom.eq(""), _NHOM_KHONG_XAC_DINH)

    for cot in (COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH):
        if cot in df_group.columns:
            df_group[cot] = pd.to_numeric(df_group[cot], errors="coerce").fillna(0)

    ma_kh = df_group[COT_MA_KH].astype("string").str.strip()
    so_ku = df_group[COT_SO_KU].astype("string").str.strip()
    df_group["_ma_kh_dem"] = ma_kh.mask(ma_kh.isna() | ma_kh.eq(""))
    df_group["_so_ku_dem"] = so_ku.mask(so_ku.isna() | so_ku.eq(""))
    qh_mask = df_group[COT_DU_NO_QH] > 0
    df_group["_so_ku_qh"] = df_group["_so_ku_dem"].where(qh_mask)

    agg_kwargs = {
        "Số_KH": ("_ma_kh_dem", "nunique"),
        "Số_món": ("_so_ku_dem", "nunique"),
        "Số_món_QH": ("_so_ku_qh", "nunique"),
        "Tổng_dư_nợ": (COT_TONG_DU_NO, "sum"),
        "Dư_nợ_trong_hạn": (COT_DU_NO_TH, "sum"),
        "Dư_nợ_quá_hạn": (COT_DU_NO_QH, "sum"),
    }
    co_khoanh = COT_DU_NO_KHOANH in df_group.columns
    if co_khoanh:
        agg_kwargs["Dư_nợ_khoanh"] = (COT_DU_NO_KHOANH, "sum")

    df_th = df_group.groupby(group_col, dropna=False).agg(**agg_kwargs).reset_index()
    if df_th.empty:
        return df_th, df_group, co_khoanh

    tong_dn = float(df_th["Tổng_dư_nợ"].sum())
    df_th["Tỷ_lệ_QH_%"] = (
        df_th["Dư_nợ_quá_hạn"]
        / df_th["Tổng_dư_nợ"].replace(0, float("nan"))
        * 100
    ).round(2).fillna(0)
    df_th["Tỷ_trọng_%"] = (
        (df_th["Tổng_dư_nợ"] / tong_dn * 100).round(2) if tong_dn > 0 else 0.0
    )
    df_th["BQ_dư_nợ_KH"] = (
        df_th["Tổng_dư_nợ"] / df_th["Số_KH"].replace(0, float("nan"))
    )
    return df_th.sort_values("Tổng_dư_nợ", ascending=False), df_group, co_khoanh


def _tinh_tong_cong(
    df_th: pd.DataFrame,
    df_group: pd.DataFrame,
) -> dict[str, float | int]:
    """Tính dòng tổng trên dữ liệu gốc để KH/món không bị đếm trùng giữa nhóm."""
    tong_dn = float(df_th["Tổng_dư_nợ"].sum()) if not df_th.empty else 0.0
    tong_qh = float(df_th["Dư_nợ_quá_hạn"].sum()) if not df_th.empty else 0.0
    tong_kh = int(df_group["_ma_kh_dem"].nunique()) if "_ma_kh_dem" in df_group else 0
    tong_mon = int(df_group["_so_ku_dem"].nunique()) if "_so_ku_dem" in df_group else 0
    tong_mon_qh = int(df_group["_so_ku_qh"].nunique()) if "_so_ku_qh" in df_group else 0
    return {
        "tong_dn": tong_dn,
        "tong_th": float(df_th["Dư_nợ_trong_hạn"].sum()) if not df_th.empty else 0.0,
        "tong_qh": tong_qh,
        "tong_khoanh": (
            float(df_th["Dư_nợ_khoanh"].sum())
            if "Dư_nợ_khoanh" in df_th.columns else 0.0
        ),
        "tong_kh": tong_kh,
        "tong_mon": tong_mon,
        "tong_mon_qh": tong_mon_qh,
        "ty_le_qh": tong_qh / tong_dn * 100 if tong_dn > 0 else 0.0,
        "ty_trong": 100.0 if tong_dn > 0 and not df_th.empty else 0.0,
        "bq_kh": tong_dn / tong_kh if tong_kh > 0 else float("nan"),
    }


def render_tong_hop_hstd_v2(
    tab: DeltaGenerator | None = None,
    df: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    specific_report: str | None = None,
    **kwargs
) -> None:
    """
    Render báo cáo tổng hợp từ HSTD với UX nâng cao.
    
    Args:
        tab: Streamlit container
        df: DataFrame HSTD
        role: Role người dùng
        pgd_user: Tên PGD
        username: Username
        specific_report: Key của báo cáo cụ thể (pgd, xa, thon, ct, nv, dvut, cbtd)
    """
    ctx = tab if tab is not None else st
    
    if df is None or df.empty:
        ctx.warning("⚠️ Chưa có dữ liệu HSTD.")
        return
    
    # Xác định báo cáo cần render
    report_options = {
        "pgd": ("🏢 Theo PGD", COT_TEN_PGD),
        "xa": ("🏘️ Theo Xã", COT_TEN_XA),
        "thon": ("🏡 Theo Thôn/ấp", COT_TEN_THON),
        "ct": ("📌 Theo Chương trình", COT_TEN_CT),
        "nv": ("🏦 Theo Nguồn vốn", COT_NGUON_VON),
        "dvut": ("🤝 Theo ĐVUT", COT_DVUT),
        "cbtd": ("👤 Theo CBTD/Tổ", COT_TEN_TO),
    }
    
    # Nếu không chỉ định, cho phép chọn
    if specific_report is None or specific_report not in report_options:
        col1, col2 = ctx.columns([2, 1])
        with col1:
            selected_report = ctx.radio(
                "Tổng hợp theo",
                list(report_options.keys()),
                format_func=lambda k: report_options[k][0],
                horizontal=True,
                key="th_loai_hstd_v2",
            )
        with col2:
            render_formula_reference(ctx)
    else:
        selected_report = specific_report
    
    report_label, group_col = report_options[selected_report]
    
    # Kiểm tra cột tồn tại
    if group_col not in df.columns:
        ctx.error(f"❌ Không có cột {group_col} trong dữ liệu.")
        return
    
    # Bộ lọc PGD
    df_filtered = df.copy()
    if la_phan_he_pgd(role) and pgd_user:
        if COT_TEN_PGD in df_filtered.columns:
            df_filtered = df_filtered[df_filtered[COT_TEN_PGD] == pgd_user]
            ctx.info(f"📍 Đang xem báo cáo của PGD: **{pgd_user}**")
    elif COT_TEN_PGD in df_filtered.columns and group_col != COT_TEN_PGD:
        ctx.markdown("**🏢 Bộ lọc PGD**")
        df_filtered = render_inline_filter(
            df_filtered,
            [COT_TEN_PGD],
            key=f"th_{selected_report}_pgd",
            container=ctx,
        )

    # Bộ lọc nguồn vốn TW (1) / Địa phương (2)
    df_filtered = render_nguon_von_filter(df_filtered, key=f"th_{selected_report}", container=ctx)

    # Chỉ giữ các khoản vay có khế ước và gộp dòng lặp cùng khoản vay.
    # Làm sạch tại report-level để không làm mất dữ liệu tiền gửi 105 ở nguồn HSTD.
    so_dong_truoc = len(df_filtered)
    df_filtered = chuan_bi_du_lieu_bao_cao(df_filtered)
    so_dong_loai = so_dong_truoc - len(df_filtered)
    if so_dong_loai:
        ctx.caption(
            f"🧹 Đã loại **{fmt_so(so_dong_loai)}** dòng không có khế ước hoặc "
            "lặp cùng khoản vay khỏi phạm vi báo cáo."
        )
    if df_filtered.empty:
        ctx.warning("⚠️ Không có khoản vay phù hợp với bộ lọc hiện tại.")
        return

    # Cảnh báo và gợi ý phải dùng cùng phạm vi PGD/nguồn vốn với báo cáo.
    render_combined_alerts_suggestions(df_filtered, container=ctx)
    ctx.divider()

    # Inline filter và search
    ctx.markdown(f"### {report_label}")
    
    # Xác định cột filter
    filter_cols = [
        c for c in [COT_TEN_XA, COT_TEN_CT]
        if c in df_filtered.columns and c != group_col
    ]
    search_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_MA_KH] if c in df_filtered.columns]
    
    df_filtered = render_combined_filter_search(
        df_filtered,
        filter_cols[:2],  # Tối đa 2 filter
        search_cols,
        key=f"th_{selected_report}",
        container=ctx,
    )
    
    # Tạo báo cáo tổng hợp
    try:
        df_th, df_group, co_khoanh = _tao_tong_hop_theo_nhom(
            df_filtered,
            selected_report,
            group_col,
        )
        if df_th.empty:
            ctx.warning("⚠️ Không có dữ liệu phù hợp với bộ lọc hiện tại.")
            return
        tong_cong = _tinh_tong_cong(df_th, df_group)
        
        # Metrics
        col1, col2, col3, col4 = ctx.columns(4)
        col1.metric("Số nhóm", fmt_so(len(df_th)))
        col2.metric("Tổng dư nợ", f"{tong_cong['tong_dn']/1e9:.1f} tỷ".replace(".", ","))
        col3.metric("Tổng KH", fmt_so(tong_cong["tong_kh"]))
        
        ty_le_qh_tb = float(tong_cong["ty_le_qh"])
        col4.metric("Tỷ lệ QH TB", f"{ty_le_qh_tb:.2f}%".replace(".", ","))
        
        ctx.divider()
        
        # Quick export
        render_quick_export_buttons(
            df_th,
            f"TongHop_{selected_report}",
            f"Báo cáo tổng hợp {report_label}",
            username,
            f"BC_TH_{selected_report.upper()}",
            key=f"th_{selected_report}",
            container=ctx,
        )
        
        # Bảng chi tiết — HTML theo bảng màu chuẩn UI_GUIDELINES
        render_header_with_tooltip(
            "📊 Chi tiết",
            tooltip_key="Tổng dư nợ",
            container=ctx,
        )

        ten_nhom = (
            report_label.split("Theo ")[-1].strip()
            if "Theo " in report_label else report_label
        )
        df_hien = pd.DataFrame({
            ten_nhom: df_th[group_col].astype(str),
            "Số KH": df_th["Số_KH"].astype(int),
            "Số món": df_th["Số_món"].astype(int),
            "Món QH": df_th["Số_món_QH"].astype(int),
            "Tổng dư nợ": df_th["Tổng_dư_nợ"] / 1_000_000,
            "Trong hạn": df_th["Dư_nợ_trong_hạn"] / 1_000_000,
            "Quá hạn": df_th["Dư_nợ_quá_hạn"] / 1_000_000,
        })
        if co_khoanh:
            df_hien["Khoanh"] = df_th["Dư_nợ_khoanh"] / 1_000_000
        df_hien["Tỷ trọng %"] = df_th["Tỷ_trọng_%"]
        df_hien["Tỷ lệ QH %"] = df_th["Tỷ_lệ_QH_%"]
        df_hien["BQ/KH"] = df_th["BQ_dư_nợ_KH"] / 1_000_000

        dong_tong = {
            ten_nhom: "TỔNG CỘNG",
            "Số KH": int(tong_cong["tong_kh"]),
            "Số món": int(tong_cong["tong_mon"]),
            "Món QH": int(tong_cong["tong_mon_qh"]),
            "Tổng dư nợ": float(tong_cong["tong_dn"]) / 1_000_000,
            "Trong hạn": float(tong_cong["tong_th"]) / 1_000_000,
            "Quá hạn": float(tong_cong["tong_qh"]) / 1_000_000,
            "Tỷ trọng %": float(tong_cong["ty_trong"]),
            "Tỷ lệ QH %": ty_le_qh_tb,
            "BQ/KH": float(tong_cong["bq_kh"]) / 1_000_000,
        }
        if co_khoanh:
            dong_tong["Khoanh"] = float(tong_cong["tong_khoanh"]) / 1_000_000

        render_bang_chi_tiet_html(
            df_hien,
            key=f"th_chi_tiet_{selected_report}",
            cot_ten=ten_nhom,
            cot_dem=["Số KH", "Số món", "Món QH"],
            cot_tien=[
                c for c in ("Tổng dư nợ", "Trong hạn", "Quá hạn", "Khoanh", "BQ/KH")
                if c in df_hien.columns
            ],
            cot_bar="Tỷ trọng %",
            cot_badge="Tỷ lệ QH %",
            nhom_header=[
                ("", 1),
                ("QUY MÔ", 3),
                ("DƯ NỢ", 4 if co_khoanh else 3),
                ("CƠ CẤU & CHẤT LƯỢNG", 3),
            ],
            dong_tong=dong_tong,
            height=520,
            container=ctx,
        )
        
    except Exception as e:
        logger.error("tong_hop_hstd_v2: lỗi tạo báo cáo — %s", e, exc_info=True)
        ctx.error(f"❌ Lỗi tạo báo cáo: {e}")
