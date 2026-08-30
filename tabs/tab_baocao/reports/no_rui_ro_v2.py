"""Báo cáo nợ rủi ro v2 - UX nâng cao."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_DVUT,
    COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_NGAY_DH,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH,
)
from auth import la_phan_he_pgd
from utils import fmt_so, vn
from pdf_service import xuat_pdf, xuat_pdf_chi_tiet

from ..components.inline_filter import (
    chuan_bi_du_lieu_bao_cao,
    render_combined_filter_search,
    render_inline_filter,
    render_nguon_von_filter,
)
from ..components.sticky_table import render_sticky_table
from ..components.quick_export import render_quick_export_buttons
from ..components.tooltip import render_metric_with_tooltip
from ..components.alert_suggestion import check_alerts, get_suggestions, render_alert_card

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


def _loc_den_han(
    df: pd.DataFrame,
    ngay: int,
    hom_nay: pd.Timestamp | str | None = None,
) -> pd.DataFrame:
    """Lọc món đến hạn từ đầu ngày hiện tại đến hết ngày cuối kỳ."""
    if COT_NGAY_DH not in df.columns:
        return df.iloc[0:0].copy()
    out = df.copy()
    out[COT_NGAY_DH] = pd.to_datetime(
        out[COT_NGAY_DH], dayfirst=True, errors="coerce"
    ).dt.normalize()
    moc_dau = pd.Timestamp.today().normalize() if hom_nay is None else pd.Timestamp(hom_nay).normalize()
    moc_cuoi = moc_dau + pd.Timedelta(days=ngay)
    return out.loc[out[COT_NGAY_DH].between(moc_dau, moc_cuoi)].copy()


def _tao_ty_le_no_xau_theo_pgd(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp QH + khoanh theo PGD mà không làm rơi dòng thiếu tên nhóm."""
    if COT_TEN_PGD not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    nhom = out[COT_TEN_PGD].astype("string").str.strip()
    out[COT_TEN_PGD] = nhom.mask(nhom.isna() | nhom.eq(""), "Chưa xác định")
    df_th = out.groupby(COT_TEN_PGD, dropna=False).agg(
        Tổng_dư_nợ=(COT_TONG_DU_NO, "sum"),
        Nợ_quá_hạn=(COT_DU_NO_QH, "sum"),
        Nợ_khoanh=(COT_DU_NO_KHOANH, "sum"),
    ).reset_index()
    df_th["Tổng_nợ_xấu"] = df_th["Nợ_quá_hạn"] + df_th["Nợ_khoanh"]
    df_th["Tỷ_lệ_nợ_xấu_%"] = (
        df_th["Tổng_nợ_xấu"]
        / df_th["Tổng_dư_nợ"].replace(0, float("nan"))
        * 100
    ).round(2).fillna(0)
    return df_th


def _xuat_pdf_chi_tiet_no_rui_ro(
    df: pd.DataFrame,
    tieu_de: str,
    username: str,
    prefix_file: str,
) -> bytes:
    """Xuất PDF chi tiết và chuẩn hóa ngày đến hạn về dd/mm/yyyy."""
    df_xuat = df.copy()
    if COT_NGAY_DH in df_xuat.columns:
        ngay = pd.to_datetime(df_xuat[COT_NGAY_DH], dayfirst=True, errors="coerce")
        df_xuat[COT_NGAY_DH] = ngay.dt.strftime("%d/%m/%Y").where(ngay.notna(), "")
    return xuat_pdf_chi_tiet(
        df_xuat,
        list(df_xuat.columns),
        tieu_de,
        username,
        prefix_file,
    )


def _xuat_pdf_ty_le_no_xau(
    df: pd.DataFrame,
    tieu_de: str,
    username: str,
    prefix_file: str = "BC_NOXAU",
) -> bytes:
    """Xuất PDF nợ xấu với đủ cột tiền, tổng tỷ lệ đúng và không dùng emoji."""
    cot_tien_nguon = ["Tổng_dư_nợ", "Nợ_quá_hạn", "Nợ_khoanh", "Tổng_nợ_xấu"]
    thieu_cot = [c for c in [COT_TEN_PGD, *cot_tien_nguon] if c not in df.columns]
    if thieu_cot:
        raise ValueError(f"Thiếu cột để xuất PDF tỷ lệ nợ xấu: {', '.join(thieu_cot)}")

    so_tien = {
        col: pd.to_numeric(df[col], errors="coerce").fillna(0)
        for col in cot_tien_nguon
    }
    df_xuat = pd.DataFrame({
        "PGD": df[COT_TEN_PGD].astype("string").fillna(""),
        "Tổng dư nợ": (so_tien["Tổng_dư_nợ"] / 1_000_000).round(0),
        "Nợ quá hạn": (so_tien["Nợ_quá_hạn"] / 1_000_000).round(0),
        "Nợ khoanh": (so_tien["Nợ_khoanh"] / 1_000_000).round(0),
        "Tổng nợ xấu": (so_tien["Tổng_nợ_xấu"] / 1_000_000).round(0),
    })
    tong_dn = float(so_tien["Tổng_dư_nợ"].sum())
    tong_qh = float(so_tien["Nợ_quá_hạn"].sum())
    tong_khoanh = float(so_tien["Nợ_khoanh"].sum())
    tong_xau = float(so_tien["Tổng_nợ_xấu"].sum())
    df_xuat["Tỷ lệ nợ xấu %"] = (
        so_tien["Tổng_nợ_xấu"]
        / so_tien["Tổng_dư_nợ"].replace(0, float("nan"))
        * 100
    ).round(2).fillna(0)

    dong_tong = {
        "PGD": "TỔNG CỘNG",
        "Tổng dư nợ": round(tong_dn / 1_000_000),
        "Nợ quá hạn": round(tong_qh / 1_000_000),
        "Nợ khoanh": round(tong_khoanh / 1_000_000),
        "Tổng nợ xấu": round(tong_xau / 1_000_000),
        "Tỷ lệ nợ xấu %": round(tong_xau / tong_dn * 100, 2) if tong_dn > 0 else 0.0,
    }
    return xuat_pdf(
        df_xuat,
        f"{tieu_de} (triệu đồng)",
        username,
        cols_tien=["Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh", "Tổng nợ xấu"],
        don_vi_tien="triệu đồng",
        prefix_file=prefix_file,
        them_dong_tong=True,
        cols_right=["Tỷ lệ nợ xấu %"],
        dong_tong=dong_tong,
        cols_percent=["Tỷ lệ nợ xấu %"],
    )


def render_no_rui_ro_v2(
    tab: DeltaGenerator | None = None,
    df: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    specific_report: str | None = None,
    **kwargs
) -> None:
    """
    Render báo cáo nợ rủi ro với UX nâng cao.
    
    Args:
        tab: Streamlit container
        df: DataFrame HSTD
        role: Role người dùng
        pgd_user: Tên PGD
        username: Username
        specific_report: qh, khoanh, dh30, dh60, noxau
    """
    ctx = tab if tab is not None else st
    
    if df is None or df.empty:
        ctx.warning("⚠️ Chưa có dữ liệu HSTD.")
        return
    
    # Options
    report_options = {
        "qh": ("🔴 Nợ quá hạn", "no_qh"),
        "khoanh": ("🟠 Nợ khoanh", "no_khoanh"),
        "dh30": ("⏰ Đến hạn 30 ngày", "den_han_30"),
        "dh60": ("⏰ Đến hạn 60 ngày", "den_han_60"),
        "noxau": ("📊 Tỷ lệ nợ xấu", "ty_le_no_xau"),
    }
    
    if specific_report is None or specific_report not in report_options:
        selected_report = ctx.radio(
            "Loại báo cáo",
            list(report_options.keys()),
            format_func=lambda k: report_options[k][0],
            horizontal=True,
            key="nr_loai_v2",
        )
    else:
        selected_report = specific_report
    
    report_label, _ = report_options[selected_report]
    
    # Lọc theo PGD
    df_filtered = df.copy()
    if la_phan_he_pgd(role) and pgd_user and COT_TEN_PGD in df_filtered.columns:
        df_filtered = df_filtered[df_filtered[COT_TEN_PGD] == pgd_user]
    elif COT_TEN_PGD in df_filtered.columns:
        ctx.markdown("**🏢 Bộ lọc PGD**")
        df_filtered = render_inline_filter(
            df_filtered,
            [COT_TEN_PGD],
            key="nr_v2_pgd",
            container=ctx,
        )

    # Bộ lọc nguồn vốn TW (1) / Địa phương (2)
    df_filtered = render_nguon_von_filter(df_filtered, key="nr_v2", container=ctx)

    # Chuẩn bị dữ liệu: loại dòng không có khế ước và gộp dòng lặp cùng khoản vay.
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

    # Cảnh báo phải phản ánh đúng PGD và nguồn vốn đang xem.
    alerts = check_alerts(df_filtered)
    if alerts:
        ctx.markdown("#### 🔔 Cảnh báo nợ xấu")
        for alert in alerts:
            if alert["type"] in ["ty_le_qh", "ty_le_no_xau"]:
                render_alert_card(alert, container=ctx)
        ctx.divider()

    ctx.markdown(f"### {report_label}")
    
    # Render theo loại
    if selected_report == "qh":
        _render_no_qh_v2(ctx, df_filtered, username)
    elif selected_report == "khoanh":
        _render_no_khoanh_v2(ctx, df_filtered, username)
    elif selected_report in ["dh30", "dh60"]:
        ngay = 30 if selected_report == "dh30" else 60
        _render_den_han_v2(ctx, df_filtered, ngay, username)
    else:
        _render_ty_le_no_xau_v2(ctx, df_filtered, username)


def _render_no_qh_v2(ctx, df: pd.DataFrame, username: str) -> None:
    """Render nợ quá hạn với UX nâng cao."""
    if COT_DU_NO_QH not in df.columns:
        ctx.error("❌ Không có cột dư nợ quá hạn.")
        return
    
    filter_cols = [c for c in [COT_TEN_XA, COT_DVUT] if c in df.columns]
    search_cols = [c for c in [COT_TEN_KH, COT_MA_KH, COT_SO_KU] if c in df.columns]
    df_scope = render_combined_filter_search(
        df,
        filter_cols,
        search_cols,
        key="qh_v2",
        container=ctx,
    )
    df_qh = df_scope[df_scope[COT_DU_NO_QH] > 0].copy()
    
    if df_qh.empty:
        ctx.success("✅ Không có nợ quá hạn!")
        return
    
    # Metrics với tooltip
    col1, col2, col3, col4 = ctx.columns(4)
    
    render_metric_with_tooltip(
        "Số món QH",
        fmt_so(len(df_qh)),
        "Số món vay đã quá hạn thanh toán",
        container=col1,
    )
    
    render_metric_with_tooltip(
        "Dư nợ QH",
        f"{df_qh[COT_DU_NO_QH].sum()/1e9:.1f} tỷ".replace(".", ","),
        "Tổng dư nợ quá hạn",
        container=col2,
    )
    
    tong_du_no_scope = df_scope[COT_TONG_DU_NO].sum()
    tl_qh = (
        df_qh[COT_DU_NO_QH].sum() / tong_du_no_scope * 100
        if tong_du_no_scope > 0 else 0
    )
    render_metric_with_tooltip(
        "Tỷ lệ QH",
        f"{tl_qh:.2f}%".replace(".", ","),
        "Nợ quá hạn / Tổng dư nợ × 100%",
        delta=f"Ngưỡng: 10%",
        delta_color="inverse" if tl_qh > 10 else "normal",
        container=col3,
    )
    
    # Gợi ý hành động
    suggestions = get_suggestions([{"type": "ty_le_qh"}])
    with col4:
        ctx.markdown("**💡 Gợi ý:**")
        for sugg in suggestions[:2]:
            ctx.caption(f"{sugg['icon']} {sugg['title']}")
    
    ctx.divider()
    
    # Bảng chi tiết dùng đúng cùng phạm vi với KPI.
    cols_display = [c for c in [
        COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_MA_KH, COT_TEN_KH,
        COT_SO_KU, COT_TONG_DU_NO, COT_DU_NO_QH
    ] if c in df_qh.columns]
    df_display = df_qh[cols_display]
    
    # Quick export
    render_quick_export_buttons(
        df_display,
        "NoQuaHan",
        "Báo cáo nợ quá hạn",
        username,
        "BC_QH",
        key="qh_v2",
        container=ctx,
        pdf_func=lambda d, t, u: _xuat_pdf_chi_tiet_no_rui_ro(d, t, u, "BC_QH"),
    )
    
    # Sticky table
    render_sticky_table(
        _fmt_df_trieu(df_display),
        key="qh_table_v2",
        height=400,
        container=ctx,
    )


def _render_no_khoanh_v2(ctx, df: pd.DataFrame, username: str) -> None:
    """Render nợ khoanh với UX nâng cao."""
    if COT_DU_NO_KHOANH not in df.columns:
        ctx.error("❌ Không có cột dư nợ khoanh.")
        return
    
    filter_cols = [c for c in [COT_TEN_XA] if c in df.columns]
    search_cols = [c for c in [COT_TEN_KH, COT_MA_KH] if c in df.columns]
    df_scope = render_combined_filter_search(
        df,
        filter_cols,
        search_cols,
        key="kh_v2",
        container=ctx,
    )
    df_kh = df_scope[df_scope[COT_DU_NO_KHOANH] > 0].copy()
    
    if df_kh.empty:
        ctx.success("✅ Không có nợ khoanh!")
        return
    
    # Metrics
    col1, col2, col3 = ctx.columns(3)
    col1.metric("Số món khoanh", fmt_so(len(df_kh)))
    col2.metric("Nợ khoanh", f"{df_kh[COT_DU_NO_KHOANH].sum()/1e9:.1f} tỷ".replace(".", ","))
    
    tong_du_no_scope = df_scope[COT_TONG_DU_NO].sum()
    tl_kh = (
        df_kh[COT_DU_NO_KHOANH].sum() / tong_du_no_scope * 100
        if tong_du_no_scope > 0 else 0
    )
    col3.metric("Tỷ lệ khoanh", f"{tl_kh:.2f}%".replace(".", ","))
    
    ctx.divider()
    
    cols_display = [c for c in [
        COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_MA_KH, COT_TEN_KH,
        COT_SO_KU, COT_TONG_DU_NO, COT_DU_NO_KHOANH
    ] if c in df_kh.columns]
    
    df_display = df_kh[cols_display]
    
    render_quick_export_buttons(
        df_display, "NoKhoanh", "Báo cáo nợ khoanh", username, "BC_KHOANH",
        key="kh_v2", container=ctx,
        pdf_func=lambda d, t, u: _xuat_pdf_chi_tiet_no_rui_ro(d, t, u, "BC_KHOANH"),
    )
    
    render_sticky_table(_fmt_df_trieu(df_display), key="kh_table_v2", height=400, container=ctx)


def _render_den_han_v2(ctx, df: pd.DataFrame, ngay: int, username: str) -> None:
    """Render đến hạn với UX nâng cao."""
    if COT_NGAY_DH not in df.columns:
        ctx.error("❌ Không có cột ngày đến hạn.")
        return
    
    filter_cols = [c for c in [COT_TEN_XA] if c in df.columns]
    search_cols = [c for c in [COT_TEN_KH, COT_MA_KH] if c in df.columns]
    df_scope = render_combined_filter_search(
        df,
        filter_cols,
        search_cols,
        key=f"dh{ngay}_v2",
        container=ctx,
    )
    df_dh = _loc_den_han(df_scope, ngay)
    
    if df_dh.empty:
        ctx.info(f"📅 Không có món vay đến hạn trong {ngay} ngày tới.")
        return
    
    col1, col2 = ctx.columns(2)
    col1.metric("Số món đến hạn", fmt_so(len(df_dh)))
    col2.metric("Dư nợ đến hạn", f"{df_dh[COT_TONG_DU_NO].sum()/1e9:.1f} tỷ".replace(".", ","))
    
    ctx.divider()
    
    cols_display = [c for c in [
        COT_TEN_PGD, COT_TEN_XA, COT_MA_KH, COT_TEN_KH,
        COT_SO_KU, COT_NGAY_DH, COT_TONG_DU_NO
    ] if c in df_dh.columns]
    
    df_dh = df_dh.sort_values(COT_NGAY_DH)
    
    df_display = df_dh[cols_display]
    
    render_quick_export_buttons(
        df_display, f"DenHan{ngay}", f"Báo cáo đến hạn {ngay} ngày",
        username, f"BC_DH{ngay}", key=f"dh{ngay}_v2", container=ctx,
        pdf_func=lambda d, t, u: _xuat_pdf_chi_tiet_no_rui_ro(d, t, u, f"BC_DH{ngay}"),
    )
    
    render_sticky_table(_fmt_df_trieu(df_display), key=f"dh{ngay}_table_v2", height=400, container=ctx)


def _render_ty_le_no_xau_v2(ctx, df: pd.DataFrame, username: str) -> None:
    """Render tỷ lệ nợ xấu với UX nâng cao."""
    if COT_TEN_PGD not in df.columns:
        ctx.error("❌ Không có cột PGD.")
        return
    
    df_th = _tao_ty_le_no_xau_theo_pgd(df)
    
    # Highlight cảnh báo
    df_th["⚠️"] = df_th["Tỷ_lệ_nợ_xấu_%"].apply(lambda x: "🚨" if x > 15 else ("⚠️" if x > 10 else "✅"))
    
    df_th = df_th.sort_values("Tỷ_lệ_nợ_xấu_%", ascending=False)
    
    col1, col2 = ctx.columns(2)
    col1.metric("PGD có nợ xấu cao", len(df_th[df_th["Tỷ_lệ_nợ_xấu_%"] > 10]))
    col2.metric("PGD an toàn", len(df_th[df_th["Tỷ_lệ_nợ_xấu_%"] <= 5]))
    
    ctx.divider()
    
    render_quick_export_buttons(
        df_th, "TyLeNoXau", "Báo cáo tỷ lệ nợ xấu",
        username, "BC_NOXAU", key="noxau_v2", container=ctx,
        pdf_func=lambda d, t, u: _xuat_pdf_ty_le_no_xau(d, t, u),
    )
    
    render_sticky_table(_fmt_df_trieu(df_th), key="noxau_table_v2", height=400, container=ctx)
