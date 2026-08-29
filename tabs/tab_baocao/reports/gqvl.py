"""Báo cáo GQVL - Nhóm D."""
from __future__ import annotations

import re

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TEN_THON,
    COT_MA_KH,
    COT_TEN_KH,
    COT_NGUON_VON,
    COT_PL_NV,
    COT_GIAI_NGAN_TRONG_NAM,
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_DU_NO_KHOANH,
    COT_SO_KU,
    COT_TEN_NHA_DAU_TU,
    COT_MA_NDT,
)
from auth import la_phan_he_pgd
from utils import fmt_so, vn
from db import doc_ndt_dp_ma_list
from pdf_service import xuat_pdf
from services.data_quality import chuan_hoa_ma_don_vi
from logger import get_logger

from ..components.inline_filter import (
    _chuan_hoa_nguon_von,
    render_inline_filter,
    render_khu_vuc_filter,
    render_nguon_von_filter,
    render_quick_search,
)
from ..components.sticky_table import render_bang_chi_tiet_html
from ..components.quick_export import render_quick_export_buttons
from ..components.tooltip import render_metric_with_tooltip

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


_NHOM_KHONG_XAC_DINH = "Khác/Không xác định"

# Nhãn hiển thị 4 nhóm phân tầng GQVL (khớp GQVL_PHAN_TANG trong config)
_NHAN_PHAN_TANG = {
    "3_TW_NHCSXH": "GQVL TW — NHCSXH huy động",
    "3_TW_NSNN": "GQVL TW — NSNN (Quỹ QG TW)",
    "3_DP_TINH": "GQVL ĐP — Cấp tỉnh",
    "3_DP_XA": "GQVL ĐP — Cấp xã/khác",
}

# Các loại báo cáo GQVL — thứ tự dict = thứ tự hiển thị khi render nhiều mục
_GQVL_REPORT_OPTIONS: dict[str, tuple[str, str]] = {
    "phantang": ("🏛️ Phân tầng 4 nhóm", ""),
    "ndt": ("🏢 Theo nhà đầu tư", COT_MA_NDT),
    "pgd": ("🏢 Theo PGD", COT_TEN_PGD),
    "xa": ("🏘️ Theo Xã", COT_TEN_XA),
    "giaingan": ("📊 Tổng hợp giải ngân", ""),
}


def _phan_tang_4_nhom(df: pd.DataFrame) -> pd.Series:
    """Phân loại từng dòng GQVL vào 4 nhóm chuẩn; trả Series nhãn hiển thị."""
    nv = df[COT_NGUON_VON].map(_chuan_hoa_nguon_von)
    ket_qua = pd.Series(_NHOM_KHONG_XAC_DINH, index=df.index, dtype="string")

    if COT_PL_NV in df.columns:
        pl = pd.to_numeric(df[COT_PL_NV], errors="coerce")
        ket_qua = ket_qua.mask((nv == "1") & (pl == 2), _NHAN_PHAN_TANG["3_TW_NHCSXH"])
        ket_qua = ket_qua.mask((nv == "1") & (pl == 1), _NHAN_PHAN_TANG["3_TW_NSNN"])

    if COT_MA_NDT in df.columns:
        ma = df[COT_MA_NDT].fillna("").astype(str).str.strip()
        ds_tinh = frozenset(doc_ndt_dp_ma_list(3))
        dp = nv == "2"
        ket_qua = ket_qua.mask(dp & ma.isin(ds_tinh), _NHAN_PHAN_TANG["3_DP_TINH"])
        ket_qua = ket_qua.mask(dp & ~ma.isin(ds_tinh), _NHAN_PHAN_TANG["3_DP_XA"])
    else:
        ket_qua = ket_qua.mask(nv == "2", _NHAN_PHAN_TANG["3_DP_XA"])
    return ket_qua



def _chuan_bi_gqvl(df: pd.DataFrame | None) -> pd.DataFrame:
    """Chuẩn hóa GQVL để mọi KPI/bảng cùng đếm một lần mỗi khế ước."""
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    out = chuan_hoa_ma_don_vi(df)
    for col in (
        COT_DU_NO_TH,
        COT_DU_NO_QH,
        COT_DU_NO_KHOANH,
        COT_TONG_DU_NO,
        COT_GIAI_NGAN_TRONG_NAM,
    ):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    thanh_phan_du_no = [
        col for col in (COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH)
        if col in out.columns
    ]
    if COT_TONG_DU_NO not in out.columns and thanh_phan_du_no:
        out[COT_TONG_DU_NO] = out[thanh_phan_du_no].sum(axis=1)

    if COT_SO_KU in out.columns:
        so_ku = out[COT_SO_KU].astype("string").str.strip()
        hop_le = so_ku.notna() & ~so_ku.str.lower().isin(
            {"", "nan", "none", "null", "<na>"}
        )
        out = out.loc[hop_le].copy()
        out["_so_ku_dem"] = so_ku.loc[hop_le]
        out = out.drop_duplicates(subset=["_so_ku_dem"], keep="first")
    else:
        out["_so_ku_dem"] = out.index.astype(str)

    return out.reset_index(drop=True)


def _fmt_df_trieu(df: pd.DataFrame) -> pd.DataFrame:
    """Format cột tiền sang triệu đồng."""
    d = df.copy()
    tien_cols = [
        COT_TONG_DU_NO, COT_DU_NO_QH, COT_GIAI_NGAN_TRONG_NAM,
        "Tổng_dư_nợ", "Nợ_quá_hạn", "Giải_ngân_năm",
    ]
    for col in tien_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").apply(
                lambda x: vn(x / 1_000_000, 0) if pd.notna(x) else "—"
            )
    return d


def _tong_hop_theo_nhom(
    df: pd.DataFrame,
    group_col: str,
    co_giai_ngan: bool = False,
) -> pd.DataFrame:
    """Tổng hợp GQVL theo cột nhóm; đếm món/KH đúng một lần, kèm tỷ lệ QH/tỷ trọng."""
    out = df.copy()
    nhom = out[group_col].astype("string").str.strip()
    out[group_col] = nhom.mask(nhom.isna() | nhom.eq(""), _NHOM_KHONG_XAC_DINH)

    for cot in (COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_GIAI_NGAN_TRONG_NAM):
        if cot in out.columns:
            out[cot] = pd.to_numeric(out[cot], errors="coerce").fillna(0)

    agg_kwargs = {
        "Số_món": ("_so_ku_dem", "nunique"),
        "Tổng_dư_nợ": (COT_TONG_DU_NO, "sum"),
    }
    if "_ma_kh_dem" in out.columns:
        agg_kwargs["Số_KH"] = ("_ma_kh_dem", "nunique")
    if COT_DU_NO_TH in out.columns:
        agg_kwargs["Dư_nợ_trong_hạn"] = (COT_DU_NO_TH, "sum")
    if COT_DU_NO_QH in out.columns:
        agg_kwargs["Dư_nợ_quá_hạn"] = (COT_DU_NO_QH, "sum")
    if COT_DU_NO_KHOANH in out.columns:
        agg_kwargs["Dư_nợ_khoanh"] = (COT_DU_NO_KHOANH, "sum")
    if co_giai_ngan and COT_GIAI_NGAN_TRONG_NAM in out.columns:
        agg_kwargs["Giải_ngân_năm"] = (COT_GIAI_NGAN_TRONG_NAM, "sum")

    df_th = out.groupby(group_col, dropna=False).agg(**agg_kwargs).reset_index()
    if df_th.empty:
        return df_th

    tong_dn = float(df_th["Tổng_dư_nợ"].sum())
    if "Dư_nợ_quá_hạn" in df_th.columns:
        df_th["Tỷ_lệ_QH_%"] = (
            df_th["Dư_nợ_quá_hạn"] / df_th["Tổng_dư_nợ"].replace(0, float("nan")) * 100
        ).round(2).fillna(0)
    else:
        df_th["Tỷ_lệ_QH_%"] = 0.0
    df_th["Tỷ_trọng_%"] = (
        df_th["Tổng_dư_nợ"] / tong_dn * 100
    ).round(2) if tong_dn > 0 else 0.0
    if "Số_KH" in df_th.columns:
        df_th["BQ_dư_nợ_KH"] = df_th["Tổng_dư_nợ"] / df_th["Số_KH"].replace(0, float("nan"))
    return df_th.sort_values("Tổng_dư_nợ", ascending=False)


def _tinh_tong_cong(df_th: pd.DataFrame, df: pd.DataFrame) -> dict:
    """Dòng tổng: KH/món đếm nunique toàn cục để không trùng giữa các nhóm."""
    tong_dn = float(df_th["Tổng_dư_nợ"].sum()) if not df_th.empty else 0.0
    tong_th = float(df_th["Dư_nợ_trong_hạn"].sum()) if "Dư_nợ_trong_hạn" in df_th.columns else 0.0
    tong_qh = float(df_th["Dư_nợ_quá_hạn"].sum()) if "Dư_nợ_quá_hạn" in df_th.columns else 0.0
    tong_khoanh = float(df_th["Dư_nợ_khoanh"].sum()) if "Dư_nợ_khoanh" in df_th.columns else 0.0
    tong_gn = float(df_th["Giải_ngân_năm"].sum()) if "Giải_ngân_năm" in df_th.columns else 0.0
    so_kh = int(df["_ma_kh_dem"].nunique()) if "_ma_kh_dem" in df.columns else 0
    so_mon = int(df["_so_ku_dem"].nunique()) if "_so_ku_dem" in df.columns else 0
    return {
        "tong_dn": tong_dn, "tong_th": tong_th, "tong_qh": tong_qh,
        "tong_khoanh": tong_khoanh, "tong_gn": tong_gn,
        "so_kh": so_kh, "so_mon": so_mon,
        "bq_kh": tong_dn / so_kh if so_kh > 0 else float("nan"),
    }


def _tong_hop_theo_nha_dau_tu(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, str | None]:
    """Tổng hợp đủ mọi nhà đầu tư; không cắt top làm hụt số liệu xuất báo cáo."""
    ndt_col = next(
        (col for col in (COT_TEN_NHA_DAU_TU, COT_MA_NDT) if col in df.columns),
        None,
    )
    if ndt_col is None:
        return pd.DataFrame(), None
    return _tong_hop_theo_nhom(df, ndt_col), ndt_col


def _tao_df_hien_thi(df_th: pd.DataFrame, group_col: str, ten_nhom: str) -> pd.DataFrame:
    """Chuyển bảng tổng hợp nội bộ sang cột hiển thị; tiền sang triệu đồng."""
    df_h = pd.DataFrame({ten_nhom: df_th[group_col].astype(str)})
    if "Số_KH" in df_th.columns:
        df_h["Số KH"] = df_th["Số_KH"].astype(int)
    df_h["Số món"] = df_th["Số_món"].astype(int)
    df_h["Tổng dư nợ"] = df_th["Tổng_dư_nợ"] / 1_000_000
    if "Dư_nợ_trong_hạn" in df_th.columns:
        df_h["Trong hạn"] = df_th["Dư_nợ_trong_hạn"] / 1_000_000
    if "Dư_nợ_quá_hạn" in df_th.columns:
        df_h["Quá hạn"] = df_th["Dư_nợ_quá_hạn"] / 1_000_000
    if "Dư_nợ_khoanh" in df_th.columns:
        df_h["Khoanh"] = df_th["Dư_nợ_khoanh"] / 1_000_000
    if "Giải_ngân_năm" in df_th.columns:
        df_h["Giải ngân năm"] = df_th["Giải_ngân_năm"] / 1_000_000
    if "BQ_dư_nợ_KH" in df_th.columns:
        df_h["BQ/KH"] = df_th["BQ_dư_nợ_KH"] / 1_000_000
    df_h["Tỷ trọng %"] = df_th["Tỷ_trọng_%"]
    df_h["Tỷ lệ QH %"] = df_th["Tỷ_lệ_QH_%"]
    if "Tỷ_trọng_GN_%" in df_th.columns:
        df_h["Tỷ trọng GN %"] = df_th["Tỷ_trọng_GN_%"]
    return df_h


def _tao_dong_tong(tong_cong: dict, ten_nhom: str, df_th: pd.DataFrame) -> dict:
    """Dòng TỔNG CỘNG khớp cột của bảng hiển thị."""
    dong = {ten_nhom: "TỔNG CỘNG"}
    if "Số_KH" in df_th.columns:
        dong["Số KH"] = int(tong_cong["so_kh"])
    dong["Số món"] = int(tong_cong["so_mon"])
    dong["Tổng dư nợ"] = tong_cong["tong_dn"] / 1_000_000
    if "Dư_nợ_trong_hạn" in df_th.columns:
        dong["Trong hạn"] = tong_cong["tong_th"] / 1_000_000
    if "Dư_nợ_quá_hạn" in df_th.columns:
        dong["Quá hạn"] = tong_cong["tong_qh"] / 1_000_000
    if "Dư_nợ_khoanh" in df_th.columns:
        dong["Khoanh"] = tong_cong["tong_khoanh"] / 1_000_000
    if "Giải_ngân_năm" in df_th.columns:
        dong["Giải ngân năm"] = tong_cong["tong_gn"] / 1_000_000
    if "BQ_dư_nợ_KH" in df_th.columns:
        dong["BQ/KH"] = "" if pd.isna(tong_cong["bq_kh"]) else tong_cong["bq_kh"] / 1_000_000
    dong["Tỷ trọng %"] = 100.0 if tong_cong["tong_dn"] > 0 else 0.0
    dong["Tỷ lệ QH %"] = (
        tong_cong["tong_qh"] / tong_cong["tong_dn"] * 100 if tong_cong["tong_dn"] > 0 else 0.0
    )
    if "Tỷ_trọng_GN_%" in df_th.columns:
        dong["Tỷ trọng GN %"] = 100.0 if tong_cong["tong_gn"] > 0 else 0.0
    return dong


def _xuat_pdf_gqvl(
    df_th: pd.DataFrame,
    tong_cong: dict,
    group_col: str,
    ten_nhom: str,
    tieu_de: str,
    username: str,
    prefix_file: str,
) -> bytes:
    """Xuất PDF bảng tổng hợp GQVL với dòng tổng và cột tiền/tỷ lệ chuẩn."""
    df_xuat = _tao_df_hien_thi(df_th, group_col, ten_nhom)
    dong_tong = _tao_dong_tong(tong_cong, ten_nhom, df_th)
    cot_dem = ["Số món"] + (["Số KH"] if "Số_KH" in df_th.columns else [])
    cot_tien = [
        c for c in ("Tổng dư nợ", "Trong hạn", "Quá hạn", "Khoanh", "Giải ngân năm", "BQ/KH")
        if c in df_xuat.columns
    ]
    cot_pt = [c for c in ("Tỷ trọng %", "Tỷ lệ QH %", "Tỷ trọng GN %") if c in df_xuat.columns]
    nhan = re.sub(r"\W+", " ", str(tieu_de), flags=re.UNICODE).strip() or str(tieu_de)
    return xuat_pdf(
        df_xuat,
        f"BÁO CÁO GQVL — {nhan} (triệu đồng)",
        username,
        cols_tien=cot_tien,
        don_vi_tien="triệu đồng",
        prefix_file=prefix_file,
        them_dong_tong=True,
        cols_right=cot_dem + cot_pt,
        dong_tong=dong_tong,
        cols_percent=cot_pt,
        cols_dem=cot_dem,
    )


def render_gqvl(
    tab: DeltaGenerator | None = None,
    df_gqvl: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    specific_report: str | None = None,
    **kwargs
) -> None:
    """Render báo cáo GQVL (v2 UX nâng cao): tick chọn nhiều loại báo cáo."""
    ctx = tab if tab is not None else st

    if df_gqvl is None or df_gqvl.empty:
        ctx.warning("⚠️ Chưa có dữ liệu GQVL.")
        return

    df_goc = _chuan_bi_gqvl(df_gqvl)
    if df_goc.empty:
        ctx.warning("⚠️ Dữ liệu GQVL không có khế ước hợp lệ.")
        return
    if COT_TONG_DU_NO not in df_goc.columns:
        ctx.error("❌ Dữ liệu GQVL không có cột dư nợ hoặc các cột thành phần dư nợ.")
        return

    if specific_report is not None and specific_report in _GQVL_REPORT_OPTIONS:
        _render_mot_loai_gqvl(ctx, df_goc, specific_report, role, pgd_user, username)
        return

    ctx.markdown("### 💼 Báo cáo GQVL")
    ds_chon = ctx.multiselect(
        "🧭 Loại báo cáo — tick chọn nhiều mục để xem cùng lúc",
        list(_GQVL_REPORT_OPTIONS.keys()),
        default=["phantang"],
        format_func=lambda k: _GQVL_REPORT_OPTIONS[k][0],
        key="gqvl_loai_bc_v2",
    )
    if not ds_chon:
        ctx.info("👆 Vui lòng tick chọn ít nhất một loại báo cáo để hiển thị.")
        return

    ds_chon = [k for k in _GQVL_REPORT_OPTIONS if k in ds_chon]
    for vi_tri, r in enumerate(ds_chon):
        if vi_tri > 0:
            ctx.divider()
        _render_mot_loai_gqvl(ctx, df_goc, r, role, pgd_user, username)


def _render_mot_loai_gqvl(
    ctx: DeltaGenerator,
    df: pd.DataFrame,
    selected_report: str,
    role: str,
    pgd_user: str,
    username: str,
) -> None:
    """Render trọn vẹn MỘT loại báo cáo GQVL: bộ lọc, bảng, xuất."""
    label, group_col = _GQVL_REPORT_OPTIONS[selected_report]
    df_filtered = df.copy()

    with ctx.container(border=True):
        kem_loc_pgd = selected_report not in ("pgd", "giaingan")
        if la_phan_he_pgd(role) and pgd_user:
            if COT_TEN_PGD in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[COT_TEN_PGD].eq(pgd_user)].copy()
                ctx.info(f"📍 Đang xem báo cáo của PGD: **{pgd_user}**")
        elif kem_loc_pgd and COT_TEN_PGD in df_filtered.columns:
            df_filtered = render_inline_filter(
                df_filtered,
                [COT_TEN_PGD],
                key=f"gqvl_{selected_report}_pgd",
                container=ctx,
            )

        col_nv, col_kv = ctx.columns(2)
        df_filtered = render_nguon_von_filter(
            df_filtered, key=f"gqvl_{selected_report}", container=col_nv,
        )
        df_filtered = render_khu_vuc_filter(
            df_filtered, key=f"gqvl_{selected_report}", container=col_kv,
        )

    if df_filtered.empty:
        ctx.warning("⚠️ Không có khoản vay phù hợp với bộ lọc hiện tại.")
        return

    if selected_report == "phantang":
        df_filtered["_phan_tang"] = _phan_tang_4_nhom(df_filtered)
        group_col = "_phan_tang"
        ten_nhom = "Phân tầng"
    elif selected_report == "giaingan":
        if COT_GIAI_NGAN_TRONG_NAM not in df_filtered.columns:
            ctx.error("❌ Không có cột giải ngân trong năm.")
            return
        group_col = next(
            (c for c in (COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON) if c in df_filtered.columns),
            None,
        )
        if group_col is None:
            ctx.error("❌ Không có cột đơn vị để tổng hợp giải ngân.")
            return
        ten_nhom = "Đơn vị"
    elif selected_report == "ndt":
        group_col = next(
            (c for c in (COT_TEN_NHA_DAU_TU, COT_MA_NDT) if c in df_filtered.columns),
            None,
        )
        if group_col is None:
            ctx.error("❌ Không có cột nhà đầu tư.")
            return
        ten_nhom = "Nhà đầu tư"
    else:
        if group_col not in df_filtered.columns:
            ctx.error(f"❌ Không có cột {group_col} trong dữ liệu.")
            return
        ten_nhom = "PGD" if selected_report == "pgd" else "Xã/phường"

    if COT_MA_KH in df_filtered.columns:
        ma_kh = df_filtered[COT_MA_KH].astype("string").str.strip()
        df_filtered["_ma_kh_dem"] = ma_kh.mask(ma_kh.isna() | ma_kh.eq(""))

    search_cols = [c for c in (COT_TEN_KH, COT_MA_KH, COT_SO_KU) if c in df_filtered.columns]
    df_filtered = render_quick_search(
        df_filtered,
        search_cols,
        key=f"gqvl_{selected_report}",
        container=ctx,
    )
    if df_filtered.empty:
        ctx.warning("⚠️ Không có dữ liệu phù hợp.")
        return

    co_giai_ngan = selected_report == "giaingan"
    df_th = _tong_hop_theo_nhom(df_filtered, group_col, co_giai_ngan=co_giai_ngan)
    if df_th.empty:
        ctx.warning("⚠️ Không có dữ liệu phù hợp với bộ lọc hiện tại.")
        return
    if co_giai_ngan and "Giải_ngân_năm" in df_th.columns:
        tong_gn = float(df_th["Giải_ngân_năm"].sum())
        df_th["Tỷ_trọng_GN_%"] = (
            df_th["Giải_ngân_năm"] / tong_gn * 100
        ).round(2) if tong_gn > 0 else 0.0
        df_th = df_th.sort_values("Giải_ngân_năm", ascending=False)

    tong_cong = _tinh_tong_cong(df_th, df_filtered)

    ctx.markdown(f"### {label}")
    c1, c2, c3, c4 = ctx.columns(4)
    render_metric_with_tooltip("Số nhóm", fmt_so(len(df_th)), container=c1)
    render_metric_with_tooltip(
        "Tổng dư nợ", f"{vn(tong_cong['tong_dn'] / 1e9, 1)} tỷ", container=c2,
    )
    nhan_kh = "Tổng KH" if "Số_KH" in df_th.columns else "Số món"
    gia_tri_kh = (
        fmt_so(tong_cong["so_kh"]) if "Số_KH" in df_th.columns else fmt_so(tong_cong["so_mon"])
    )
    render_metric_with_tooltip(nhan_kh, gia_tri_kh, container=c3)
    ty_le_qh = (
        tong_cong["tong_qh"] / tong_cong["tong_dn"] * 100 if tong_cong["tong_dn"] > 0 else 0.0
    )
    render_metric_with_tooltip(
        "Tỷ lệ QH TB",
        f"{ty_le_qh:.2f}%".replace(".", ","),
        container=c4,
        delta_color="inverse" if ty_le_qh > 0 else "off",
    )

    df_hien = _tao_df_hien_thi(df_th, group_col, ten_nhom)
    dong_tong = _tao_dong_tong(tong_cong, ten_nhom, df_th)

    render_quick_export_buttons(
        df_hien,
        f"GQVL_{selected_report}",
        f"Báo cáo GQVL {label}",
        username,
        f"BC_GQVL_{selected_report.upper()}",
        key=f"gqvl_{selected_report}",
        container=ctx,
        pdf_func=lambda d, t, u: _xuat_pdf_gqvl(
            df_th, tong_cong, group_col, ten_nhom, t, u,
            f"BC_GQVL_{selected_report.upper()}",
        ),
    )

    cot_dem = ["Số món"] + (["Số KH"] if "Số_KH" in df_th.columns else [])
    cot_tien = [
        c for c in ("Tổng dư nợ", "Trong hạn", "Quá hạn", "Khoanh", "Giải ngân năm", "BQ/KH")
        if c in df_hien.columns
    ]
    render_bang_chi_tiet_html(
        df_hien,
        key=f"gqvl_chi_tiet_{selected_report}",
        cot_ten=ten_nhom,
        cot_dem=cot_dem,
        cot_tien=cot_tien,
        cot_bar="Tỷ trọng GN %" if (co_giai_ngan and "Tỷ_trọng_GN_%" in df_th.columns) else "Tỷ trọng %",
        cot_badge="Tỷ lệ QH %",
        dong_tong=dong_tong,
        height=520,
        container=ctx,
    )