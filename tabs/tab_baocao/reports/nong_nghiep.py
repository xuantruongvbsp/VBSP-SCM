"""Báo cáo Nông nghiệp — thống kê dư nợ theo lĩnh vực nông nghiệp.

Phạm vi:
- Xã nông thôn: toàn bộ lĩnh vực nông nghiệp
  (Trồng trọt, Chăn nuôi, Nuôi trồng thủy sản, Lâm nghiệp).
- Phường (thành thị): Trồng trọt + Chăn nuôi.

Phân loại lĩnh vực từ cột "Tên PNKT51" (Mục đích sử dụng vốn) theo từ khóa
không dấu, khai báo trong config.py (NN_TU_KHOA_*).
"""
from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd

from config import (
    COT_TEN_PGD, COT_TEN_PNKT51, COT_TONG_DU_NO,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH,
    COT_MA_KH, COT_TEN_KH, COT_SO_KU,
    NN_LINH_VUC_TRONG_TROT, NN_LINH_VUC_CHAN_NUOI, NN_LINH_VUC_THUY_SAN,
    NN_LINH_VUC_LAM_NGHIEP, NN_LINH_VUC_KHAC,
    NN_TU_KHOA_TRONG_TROT, NN_TU_KHOA_CHAN_NUOI, NN_TU_KHOA_THUY_SAN,
    NN_TU_KHOA_LAM_NGHIEP,
)
from auth import la_phan_he_pgd
from utils import xuat_excel
from pdf_service import xuat_pdf
from components.delta_card import kpi_row
from ..components.inline_filter import chuan_bi_du_lieu_bao_cao, phan_loai_khu_vuc_df

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

_COT_LINH_VUC = "_linh_vuc_nn"

_LINH_VUC_NONG_THON = [
    NN_LINH_VUC_TRONG_TROT,
    NN_LINH_VUC_CHAN_NUOI,
    NN_LINH_VUC_THUY_SAN,
    NN_LINH_VUC_LAM_NGHIEP,
]
_LINH_VUC_THANH_THI = [
    NN_LINH_VUC_TRONG_TROT,
    NN_LINH_VUC_CHAN_NUOI,
]

_COT_TIEN = ("Tổng dư nợ", "Trong hạn", "Quá hạn", "Khoanh", "BQ/KH")
_COT_DEM = ("Số KH", "Số món")
_COT_PHAN_TRAM = ("Tỷ trọng %", "Tỷ lệ QH %")


def _bo_dau(s) -> str:
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").casefold().strip()


def phan_loai_linh_vuc_nong_nghiep(ten_pnkt51) -> str:
    """Phân loại một giá trị 'Tên PNKT51' → lĩnh vực nông nghiệp chuẩn."""
    txt = _bo_dau(ten_pnkt51)
    if not txt or txt in {"nan", "none", "null", "<na>"}:
        return NN_LINH_VUC_KHAC
    if any(k in txt for k in NN_TU_KHOA_LAM_NGHIEP):
        return NN_LINH_VUC_LAM_NGHIEP
    if any(k in txt for k in NN_TU_KHOA_THUY_SAN):
        return NN_LINH_VUC_THUY_SAN
    if any(k in txt for k in NN_TU_KHOA_CHAN_NUOI):
        return NN_LINH_VUC_CHAN_NUOI
    if any(k in txt for k in NN_TU_KHOA_TRONG_TROT):
        return NN_LINH_VUC_TRONG_TROT
    return NN_LINH_VUC_KHAC


def _gan_linh_vuc(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[_COT_LINH_VUC] = df[COT_TEN_PNKT51].map(phan_loai_linh_vuc_nong_nghiep)
    return df


def _loc_pham_vi_nong_nghiep(df_phan_loai: pd.DataFrame) -> pd.DataFrame:
    """Lọc đúng phạm vi báo cáo: nông thôn lấy 4 lĩnh vực, phường lấy 2 lĩnh vực."""
    if df_phan_loai.empty:
        return df_phan_loai.copy()

    kv = phan_loai_khu_vuc_df(df_phan_loai)
    mask_nong_thon = kv.eq("nong_thon") & df_phan_loai[_COT_LINH_VUC].isin(
        _LINH_VUC_NONG_THON
    )
    mask_thanh_thi = kv.eq("thanh_thi") & df_phan_loai[_COT_LINH_VUC].isin(
        _LINH_VUC_THANH_THI
    )
    return df_phan_loai.loc[mask_nong_thon | mask_thanh_thi].copy()


def _tong_hop_linh_vuc(df: pd.DataFrame, chi_linh_vuc: list[str]) -> pd.DataFrame:
    """Tổng hợp dư nợ theo lĩnh vực, chỉ giữ các lĩnh vực trong `chi_linh_vuc`."""
    df = _gan_linh_vuc(df)
    df = df[df[_COT_LINH_VUC].isin(chi_linh_vuc)].copy()
    if df.empty:
        return pd.DataFrame()

    for cot in (COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH):
        if cot in df.columns:
            df[cot] = pd.to_numeric(df[cot], errors="coerce").fillna(0)
        else:
            df[cot] = 0.0

    cot_kh = _chon_cot_dem_hop_le(df, [COT_MA_KH, COT_TEN_KH])
    cot_ku = _chon_cot_dem_hop_le(df, [COT_SO_KU])
    df["_kh_dem_nn"] = _series_dem_hop_le(df, cot_kh) if cot_kh else df.index.astype(str)
    df["_ku_dem_nn"] = _series_dem_hop_le(df, cot_ku) if cot_ku else df.index.astype(str)

    agg_kwargs = {
        "Tổng_dư_nợ": (COT_TONG_DU_NO, "sum"),
        "Dư_nợ_trong_hạn": (COT_DU_NO_TH, "sum"),
        "Dư_nợ_quá_hạn": (COT_DU_NO_QH, "sum"),
        "Số_KH": ("_kh_dem_nn", "nunique"),
        "Số_món": ("_ku_dem_nn", "nunique"),
        "Dư_nợ_khoanh": (COT_DU_NO_KHOANH, "sum"),
    }

    df_th = df.groupby(_COT_LINH_VUC, dropna=False).agg(**agg_kwargs).reset_index()

    tong_dn = float(df_th["Tổng_dư_nợ"].sum())
    df_th["Tỷ_trọng_%"] = (
        (df_th["Tổng_dư_nợ"] / tong_dn * 100).round(2) if tong_dn > 0 else 0.0
    )
    df_th["Tỷ_lệ_QH_%"] = (
        df_th["Dư_nợ_quá_hạn"]
        / df_th["Tổng_dư_nợ"].replace(0, float("nan"))
        * 100
    ).round(2).fillna(0)
    df_th["BQ_KH"] = df_th["Tổng_dư_nợ"] / df_th["Số_KH"].replace(0, float("nan"))

    thu_tu = {lv: i for i, lv in enumerate(chi_linh_vuc)}
    df_th["_tt"] = df_th[_COT_LINH_VUC].map(thu_tu).fillna(99)
    df_th = df_th.sort_values("_tt").drop(columns="_tt").reset_index(drop=True)
    return df_th


def _df_hien_thi(df_th: pd.DataFrame) -> pd.DataFrame:
    """Chuyển về bảng hiển thị (triệu đồng)."""
    if df_th.empty:
        return pd.DataFrame()
    co_khoanh = "Dư_nợ_khoanh" in df_th.columns
    df = pd.DataFrame({
        "Lĩnh vực": df_th[_COT_LINH_VUC].astype(str),
        "Số KH": df_th["Số_KH"].astype(int),
        "Số món": df_th["Số_món"].astype(int),
        "Tổng dư nợ": (df_th["Tổng_dư_nợ"] / 1_000_000).round(0),
        "Trong hạn": (df_th["Dư_nợ_trong_hạn"] / 1_000_000).round(0),
        "Quá hạn": (df_th["Dư_nợ_quá_hạn"] / 1_000_000).round(0),
    })
    if co_khoanh:
        df["Khoanh"] = (df_th["Dư_nợ_khoanh"] / 1_000_000).round(0)
    df["Tỷ trọng %"] = df_th["Tỷ_trọng_%"]
    df["Tỷ lệ QH %"] = df_th["Tỷ_lệ_QH_%"]
    df["BQ/KH"] = (df_th["BQ_KH"] / 1_000_000).round(0)
    return df


def _df_tong_hop_hai_khu_vuc(df_phan_loai: pd.DataFrame, kv: pd.Series) -> pd.DataFrame:
    """Gộp bảng nông thôn + thành thị thành một bảng có cột 'Khu vực'."""
    parts = []
    for khu_vuc, ds_lv, ten in (
        ("nong_thon", _LINH_VUC_NONG_THON, "Xã nông thôn"),
        ("thanh_thi", _LINH_VUC_THANH_THI, "Phường (thành thị)"),
    ):
        df_th = _tong_hop_linh_vuc(df_phan_loai[kv.eq(khu_vuc)], ds_lv)
        if df_th.empty:
            continue
        df_h = _df_hien_thi(df_th)
        df_h.insert(0, "Khu vực", ten)
        parts.append(df_h)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _dong_tong_nn(df_phan_loai: pd.DataFrame) -> dict | None:
    """Dòng TỔNG CỘNG cho PDF — đếm KH/món theo nunique, không cộng trùng."""
    df = df_phan_loai[df_phan_loai[_COT_LINH_VUC].isin(_LINH_VUC_NONG_THON)].copy()
    if df.empty:
        return None

    def _sum(cot):
        if cot in df.columns:
            return round(pd.to_numeric(df[cot], errors="coerce").fillna(0).sum() / 1_000_000)
        return ""

    cot_kh = COT_MA_KH if COT_MA_KH in df.columns else (
        COT_TEN_KH if COT_TEN_KH in df.columns else None
    )
    cot_ku = COT_SO_KU if COT_SO_KU in df.columns else None

    tong_dn = pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0).sum()
    tong_qh = pd.to_numeric(df[COT_DU_NO_QH], errors="coerce").fillna(0).sum()
    so_kh = int(df[cot_kh].nunique()) if cot_kh else len(df)

    dong = {
        "Khu vực": "TỔNG CỘNG",
        "Lĩnh vực": "",
        "Số KH": so_kh,
        "Số món": int(df[cot_ku].nunique()) if cot_ku else len(df),
        "Tổng dư nợ": round(tong_dn / 1_000_000),
        "Trong hạn": _sum(COT_DU_NO_TH),
        "Quá hạn": round(tong_qh / 1_000_000),
    }
    if COT_DU_NO_KHOANH in df.columns:
        dong["Khoanh"] = _sum(COT_DU_NO_KHOANH)
    dong["Tỷ trọng %"] = 100.0
    dong["Tỷ lệ QH %"] = round(tong_qh / tong_dn * 100, 2) if tong_dn > 0 else 0.0
    dong["BQ/KH"] = round(tong_dn / so_kh / 1_000_000) if so_kh > 0 else ""
    return dong


def _xuat_pdf_nong_nghiep(df_phan_loai: pd.DataFrame, kv: pd.Series, username: str) -> bytes | None:
    df = _df_tong_hop_hai_khu_vuc(df_phan_loai, kv)
    if df.empty:
        return None
    dong = _dong_tong_nn(df_phan_loai)
    tien_cols = [c for c in ("Tổng dư nợ", "Trong hạn", "Quá hạn", "Khoanh", "BQ/KH") if c in df.columns]
    dem_cols = ["Số KH", "Số món"]
    percent_cols = ["Tỷ trọng %", "Tỷ lệ QH %"]
    return xuat_pdf(
        df,
        "BÁO CÁO NÔNG NGHIỆP (triệu đồng)",
        username,
        cols_tien=tien_cols,
        don_vi_tien="triệu đồng",
        prefix_file="BC_NONG_NGHIEP",
        them_dong_tong=True,
        cols_right=dem_cols + percent_cols,
        dong_tong=dong,
        cols_percent=percent_cols,
        cols_dem=dem_cols,
    )


def _column_config() -> dict:
    cfg = {}
    for cot in _COT_DEM:
        cfg[cot] = st.column_config.NumberColumn(cot, format="%d")
    for cot in _COT_TIEN:
        cfg[cot] = st.column_config.NumberColumn(cot, format="%,.0f")
    for cot in _COT_PHAN_TRAM:
        cfg[cot] = st.column_config.NumberColumn(cot, format="%.2f")
    return cfg


def _thong_tin_khac(df_phan_loai: pd.DataFrame, khu_vuc: str) -> str | None:
    """Đếm phần 'Khác nông nghiệp' bị loại khỏi báo cáo để cảnh báo minh bạch."""
    mask_kv = phan_loai_khu_vuc_df(df_phan_loai).eq(khu_vuc)
    df_kv = df_phan_loai[mask_kv]
    if df_kv.empty:
        return None
    so_khac = int(df_kv[_COT_LINH_VUC].eq(NN_LINH_VUC_KHAC).sum())
    tong = len(df_kv)
    if so_khac == 0:
        return None
    return f"ℹ️ {so_khac}/{tong} món thuộc \"{NN_LINH_VUC_KHAC}\" đã được loại khỏi thống kê nông nghiệp."


def _dem_unique_hop_le(df: pd.DataFrame, cot: str) -> int:
    if cot not in df.columns:
        return len(df)
    values = _series_dem_hop_le(df, cot).dropna()
    return int(values.nunique())


def _series_dem_hop_le(df: pd.DataFrame, cot: str) -> pd.Series:
    values = df[cot].astype("string").str.strip()
    invalid = values.isna() | values.str.lower().isin({"", "nan", "none", "null", "<na>"})
    return values.mask(invalid, pd.NA)


def _chon_cot_dem_hop_le(df: pd.DataFrame, ds_cot: list[str]) -> str | None:
    for cot in ds_cot:
        if cot in df.columns and _series_dem_hop_le(df, cot).notna().any():
            return cot
    return None


def _dem_khach_hang(df: pd.DataFrame) -> int:
    cot_kh = _chon_cot_dem_hop_le(df, [COT_MA_KH, COT_TEN_KH])
    return _dem_unique_hop_le(df, cot_kh) if cot_kh else len(df)


def render_nong_nghiep(
    tab: DeltaGenerator | None = None,
    df: pd.DataFrame | None = None,
    role: str = "",
    pgd_user: str = "",
    username: str = "",
    **kwargs,
) -> None:
    ctx = tab if tab is not None else st

    if df is None or df.empty:
        ctx.warning("⚠️ Chưa có dữ liệu HSTD.")
        return
    if COT_TEN_PNKT51 not in df.columns:
        ctx.warning("⚠️ Dữ liệu HSTD thiếu cột \"Tên PNKT51\" (Mục đích sử dụng vốn) — chưa thể thống kê nông nghiệp.")
        return

    ctx.subheader("🌾 Báo cáo Nông nghiệp")

    df_scope = df.copy()

    if la_phan_he_pgd(role) and pgd_user:
        if COT_TEN_PGD in df_scope.columns:
            df_scope = df_scope[df_scope[COT_TEN_PGD] == pgd_user]
        ctx.info(f"📍 Đang xem báo cáo của PGD: **{pgd_user}**")
    elif COT_TEN_PGD in df_scope.columns:
        ds_pgd = ["Tất cả"] + sorted(df_scope[COT_TEN_PGD].dropna().unique().tolist())
        pgd_chon = ctx.selectbox("📍 PGD", ds_pgd, key="nn_pgd")
        if pgd_chon != "Tất cả":
            df_scope = df_scope[df_scope[COT_TEN_PGD] == pgd_chon]

    df_scope = chuan_bi_du_lieu_bao_cao(df_scope)
    if df_scope is None or df_scope.empty:
        ctx.warning("⚠️ Không có khoản vay phù hợp.")
        return

    df_phan_loai = _gan_linh_vuc(df_scope)
    kv = phan_loai_khu_vuc_df(df_phan_loai)

    df_nn = _loc_pham_vi_nong_nghiep(df_phan_loai)
    if not df_nn.empty:
        if COT_TONG_DU_NO in df_nn.columns:
            df_nn[COT_TONG_DU_NO] = pd.to_numeric(df_nn[COT_TONG_DU_NO], errors="coerce").fillna(0)
        if COT_DU_NO_QH in df_nn.columns:
            df_nn[COT_DU_NO_QH] = pd.to_numeric(df_nn[COT_DU_NO_QH], errors="coerce").fillna(0)
    tong_dn = float(df_nn[COT_TONG_DU_NO].sum()) if not df_nn.empty and COT_TONG_DU_NO in df_nn.columns else 0.0
    tong_qh = float(df_nn[COT_DU_NO_QH].sum()) if not df_nn.empty and COT_DU_NO_QH in df_nn.columns else 0.0
    so_kh = _dem_khach_hang(df_nn)
    so_mon = _dem_unique_hop_le(df_nn, COT_SO_KU)

    kpi_row([
        {"label": "Tổng dư nợ NN", "value": tong_dn / 1e9, "icon": "🌾", "suffix": "tỷ", "precision": 3},
        {"label": "Số KH", "value": so_kh, "icon": "👥", "precision": 0},
        {"label": "Số món", "value": so_mon, "icon": "📄", "precision": 0},
        {"label": "Tỷ lệ QH", "value": round(tong_qh / tong_dn * 100, 2) if tong_dn > 0 else 0.0, "icon": "⚠️", "suffix": "%", "precision": 2, "delta_color": "inverse"},
    ], num_columns=4)

    ctx.divider()

    cfg = _column_config()
    t1, t2 = ctx.tabs(["🌾 Xã nông thôn", "🏙️ Phường (thành thị)"])

    with t1:
        df_th_nt = _tong_hop_linh_vuc(df_phan_loai[kv.eq("nong_thon")], _LINH_VUC_NONG_THON)
        if df_th_nt.empty:
            st.info("Không có dữ liệu nông nghiệp ở khu vực nông thôn.")
        else:
            note = _thong_tin_khac(df_phan_loai, "nong_thon")
            if note:
                st.caption(note)
            st.dataframe(_df_hien_thi(df_th_nt), use_container_width=True, hide_index=True, column_config=cfg)

    with t2:
        df_th_tt = _tong_hop_linh_vuc(df_phan_loai[kv.eq("thanh_thi")], _LINH_VUC_THANH_THI)
        if df_th_tt.empty:
            st.info("Không có dữ liệu trồng trọt/chăn nuôi ở khu vực phường.")
        else:
            note = _thong_tin_khac(df_phan_loai, "thanh_thi")
            if note:
                st.caption(note)
            st.dataframe(_df_hien_thi(df_th_tt), use_container_width=True, hide_index=True, column_config=cfg)

    sheets = {}
    df_nt_xuat = _df_hien_thi(_tong_hop_linh_vuc(df_phan_loai[kv.eq("nong_thon")], _LINH_VUC_NONG_THON))
    df_tt_xuat = _df_hien_thi(_tong_hop_linh_vuc(df_phan_loai[kv.eq("thanh_thi")], _LINH_VUC_THANH_THI))
    if not df_nt_xuat.empty:
        sheets["Xa nong thon"] = df_nt_xuat
    if not df_tt_xuat.empty:
        sheets["Phuong thanh thi"] = df_tt_xuat

    col_xl, col_pdf = ctx.columns(2)
    if sheets:
        with col_xl:
            buf = xuat_excel(sheets)
            ctx.download_button(
                "⬇️ Tải Excel (.xlsx)",
                data=buf,
                file_name="BaoCao_NongNghiep.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="nn_dl_xl",
                use_container_width=True,
            )

    try:
        pdf_bytes = _xuat_pdf_nong_nghiep(df_phan_loai, kv, username)
    except Exception as e:
        ctx.caption(f"⚠️ Không tạo được PDF: {e}")
        pdf_bytes = None
    if pdf_bytes:
        with col_pdf:
            ctx.download_button(
                "⬇️ Tải PDF (.pdf)",
                data=pdf_bytes,
                file_name="BaoCao_NongNghiep.pdf",
                mime="application/pdf",
                key="nn_dl_pdf",
                use_container_width=True,
            )
