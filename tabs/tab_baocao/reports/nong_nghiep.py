"""Báo cáo Nông nghiệp — thống kê dư nợ theo mục đích sử dụng vốn (LV2).

Level 2 nâng cấp (2026-08-30):
- Fix bug KeyError Khoanh trong _dong_tong_hien_thi()
- Convention widget key_prefix _kp (cn_ / pgd_{slug}_)
- @st.cache_data(ttl=300) cho các hàm tổng hợp nặng
- Thêm BẢNG THEO PGD (level trên Xã) cho cả 2 khu vực
- 4 biểu đồ PLOTLY (Treemap, Top/Bottom Xã TLQH, PGD TLQH, Top10 mục đích)
- 4 Cảnh báo sớm (🔴 Xã QH≥5%, 🟠 Mục đích≥3%, 🟡 PGD chênh cao, ℹ️ Lĩnh vực bị lọc)
- Excel 6 sheet (Tổng quan / XaNT / PhườngTT / PGD / Top10DN / Canh bao)
- Highlight dòng TỔNG CỘNG nền #C8E6C9 + chữ đậm qua pandas Styler → HTML table (≥8 cột rule)

Phạm vi nghiệp vụ:
- Xã nông thôn: TẤT CẢ mục đích sử dụng vốn (Tên PNKT51).
- Phường (thành thị): Trồng trọt + Chăn nuôi.
"""
from __future__ import annotations

import io
import unicodedata
from typing import TYPE_CHECKING

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_PNKT51, COT_TONG_DU_NO,
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
from data.pgd import pgd_slug
from ..components.inline_filter import chuan_bi_du_lieu_bao_cao, phan_loai_khu_vuc_df
from logger import get_logger

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

logger = get_logger(__name__)

_COT_LINH_VUC = "_linh_vuc_nn"
_NHOM_CHUA_XAC_DINH = "Chưa xác định"

_LINH_VUC_THANH_THI = [
    NN_LINH_VUC_TRONG_TROT,
    NN_LINH_VUC_CHAN_NUOI,
]

_COT_TIEN = ("Tổng dư nợ", "Trong hạn", "Quá hạn", "Khoanh", "BQ/KH")
_COT_DEM = ("Số KH", "Số món")
_COT_PHAN_TRAM = ("Tỷ trọng %", "Tỷ lệ QH %")
_NHAN_NHOM_GOP = "Mục đích / Lĩnh vực"

_VBSP_GREEN = "#1B5E20"
_VBSP_GREEN_LIGHT = "#C8E6C9"
_VBSP_ACCENT = "#4CAF50"
_VBSP_RED = "#C62828"
_VBSP_ORANGE = "#EF6C00"
_VBSP_AMBER = "#FFB300"

_NGUONG_XA_QH_DO = 5.0
_NGUONG_MD_QH_VANG = 3.0


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


def _loc_pham_vi_bao_cao(df_phan_loai: pd.DataFrame) -> pd.DataFrame:
    """Lọc phạm vi báo cáo: nông thôn lấy TẤT CẢ mục đích, phường lấy 2 lĩnh vực."""
    if df_phan_loai.empty:
        return df_phan_loai.copy()

    kv = phan_loai_khu_vuc_df(df_phan_loai)
    mask_nong_thon = kv.eq("nong_thon")
    mask_thanh_thi = kv.eq("thanh_thi") & df_phan_loai[_COT_LINH_VUC].isin(
        _LINH_VUC_THANH_THI
    )
    return df_phan_loai.loc[mask_nong_thon | mask_thanh_thi].copy()


@st.cache_data(ttl=300, show_spinner=False)
def _tong_hop_linh_vuc_cached(df_bytes: bytes, chi_linh_vuc: tuple[str, ...]) -> pd.DataFrame:
    """Cache-aware wrapper cho _tong_hop_linh_vuc."""
    df = pd.read_pickle(io.BytesIO(df_bytes)) if df_bytes else pd.DataFrame()
    return _tong_hop_linh_vuc_raw(df, list(chi_linh_vuc))


def _tong_hop_linh_vuc_raw(df: pd.DataFrame, chi_linh_vuc: list[str]) -> pd.DataFrame:
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


def _tong_hop_linh_vuc(df: pd.DataFrame, chi_linh_vuc: list[str]) -> pd.DataFrame:
    """Backward-compat wrapper — không cache (dùng raw)."""
    return _tong_hop_linh_vuc_raw(df, chi_linh_vuc)


@st.cache_data(ttl=300, show_spinner=False)
def _tong_hop_theo_cot_cached(df_bytes: bytes, cot_nhom: str) -> pd.DataFrame:
    df = pd.read_pickle(io.BytesIO(df_bytes)) if df_bytes else pd.DataFrame()
    return _tong_hop_theo_cot_raw(df, cot_nhom)


def _tong_hop_theo_cot_raw(df: pd.DataFrame, cot_nhom: str) -> pd.DataFrame:
    """Tổng hợp dư nợ theo một cột nhóm (Tên PNKT51 / Tên xã / Tên PGD) — lấy TẤT CẢ giá trị."""
    df = df.copy()
    if df.empty or cot_nhom not in df.columns:
        return pd.DataFrame()

    nhom = df[cot_nhom].astype("string").str.strip()
    df[cot_nhom] = nhom.mask(
        nhom.isna() | nhom.str.lower().isin({"", "nan", "none", "null", "<na>"}),
        _NHOM_CHUA_XAC_DINH,
    )

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

    df_th = df.groupby(cot_nhom, dropna=False).agg(**agg_kwargs).reset_index()

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

    return df_th.sort_values("Tổng_dư_nợ", ascending=False).reset_index(drop=True)


def _tong_hop_theo_cot(df: pd.DataFrame, cot_nhom: str) -> pd.DataFrame:
    """Backward-compat wrapper."""
    return _tong_hop_theo_cot_raw(df, cot_nhom)


def _tong_hop_theo_muc_dich(df: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible wrapper cho các test/import cũ."""
    return _tong_hop_theo_cot_raw(df, COT_TEN_PNKT51)


def _df_hien_thi(df_th: pd.DataFrame, cot_nhom: str = _COT_LINH_VUC, nhan_nhom: str = "Lĩnh vực") -> pd.DataFrame:
    """Chuyển về bảng hiển thị (triệu đồng)."""
    if df_th.empty:
        return pd.DataFrame()
    co_khoanh = "Dư_nợ_khoanh" in df_th.columns
    df = pd.DataFrame({
        nhan_nhom: df_th[cot_nhom].astype(str),
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
    df_th_nt = _tong_hop_theo_cot_raw(df_phan_loai[kv.eq("nong_thon")], COT_TEN_PNKT51)
    if not df_th_nt.empty:
        df_h = _df_hien_thi(df_th_nt, COT_TEN_PNKT51, _NHAN_NHOM_GOP)
        df_h.insert(0, "Khu vực", "Xã nông thôn")
        parts.append(df_h)
    df_th_tt = _tong_hop_linh_vuc_raw(df_phan_loai[kv.eq("thanh_thi")], _LINH_VUC_THANH_THI)
    if not df_th_tt.empty:
        df_h = _df_hien_thi(df_th_tt, _COT_LINH_VUC, _NHAN_NHOM_GOP)
        df_h.insert(0, "Khu vực", "Phường (thành thị)")
        parts.append(df_h)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _dong_tong_nn(df_phan_loai: pd.DataFrame) -> dict | None:
    """Dòng TỔNG CỘNG cho PDF — đếm KH/món theo nunique, không cộng trùng."""
    df = _loc_pham_vi_bao_cao(df_phan_loai)
    if df.empty:
        return None

    def _sum(cot):
        if cot in df.columns:
            return round(pd.to_numeric(df[cot], errors="coerce").fillna(0).sum() / 1_000_000)
        return ""

    tong_dn = pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0).sum()
    tong_qh = pd.to_numeric(df[COT_DU_NO_QH], errors="coerce").fillna(0).sum()
    so_kh = _dem_khach_hang(df)

    dong = {
        "Khu vực": "TỔNG CỘNG",
        _NHAN_NHOM_GOP: "",
        "Số KH": so_kh,
        "Số món": _dem_unique_hop_le(df, COT_SO_KU),
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


def _styler_html_table(df_hien: pd.DataFrame, highlight_last: bool = True) -> str:
    """Trả về HTML table style chuẩn cho bảng ≥8 cột (rule 6.15). highlight_last=True: dòng cuối nền xanh đậm."""
    if df_hien is None or df_hien.empty:
        return ""

    def _fmt_tien(v):
        try:
            if pd.isna(v):
                return ""
            fv = float(v)
            return f"{fv:,.0f}".replace(",", ".")
        except Exception:
            return str(v) if v is not None else ""

    def _fmt_pt(v):
        try:
            if pd.isna(v):
                return ""
            return f"{float(v):.2f}"
        except Exception:
            return str(v) if v is not None else ""

    cols = list(df_hien.columns)

    def _style_attr(base_style: str, extra_style: str = "") -> str:
        prefix = 'style="'
        style_inner = (
            base_style[len(prefix):-1]
            if base_style.startswith(prefix) and base_style.endswith('"')
            else "text-align:left;padding:4px 8px;"
        )
        return f'style="{style_inner}{extra_style}"'

    col_is_tien = {}
    col_is_pt = {}
    col_is_dem = {}
    for c in cols:
        if c in _COT_TIEN:
            col_is_tien[c] = True
        elif c in _COT_PHAN_TRAM:
            col_is_pt[c] = True
        elif c in _COT_DEM:
            col_is_dem[c] = True

    rows_html = []
    n_rows = len(df_hien)
    for i, (_, row) in enumerate(df_hien.iterrows()):
        is_total_row = highlight_last and i == n_rows - 1
        row_style = ""
        cells = []
        for c in cols:
            val = row[c]
            if col_is_tien.get(c):
                txt = _fmt_tien(val)
                align = 'style="text-align:right;padding:4px 8px;"'
            elif col_is_pt.get(c):
                txt = _fmt_pt(val)
                align = 'style="text-align:right;padding:4px 8px;"'
            elif col_is_dem.get(c):
                try:
                    txt = f"{int(val):,}".replace(",", ".") if pd.notna(val) else ""
                except Exception:
                    txt = str(val) if val is not None else ""
                align = 'style="text-align:right;padding:4px 8px;"'
            else:
                txt = str(val) if val is not None else ""
                align = 'style="text-align:left;padding:4px 8px;"'
            if is_total_row:
                style = _style_attr(
                    align,
                    f"background:{_VBSP_GREEN_LIGHT};font-weight:700;border:1px solid #bdbdbd;",
                )
                cell = f"<th {style}>{txt}</th>"
            else:
                zebra = 'background:#f9fafb;color:#111827;' if i % 2 == 0 else 'color:inherit;'
                style = _style_attr(align, f"{zebra}border:1px solid #e0e0e0;")
                cell = f"<td {style}>{txt}</td>"
            cells.append(cell)
        tr_tag = "tr" if not is_total_row else 'tr style="font-weight:700;"'
        rows_html.append(f"<{tr_tag}>{''.join(cells)}</tr>")

    headers_html = "".join(
        f'<th style="background:{_VBSP_GREEN};color:#fff;text-align:center;padding:6px 8px;border:1px solid {_VBSP_GREEN};font-weight:700;">{c}</th>'
        for c in cols
    )
    html = f"""
    <div style="overflow-x:auto;width:100%;">
      <table style="border-collapse:collapse;width:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:13px;">
        <thead><tr>{headers_html}</tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    """
    return html


def _thong_tin_khac(df_phan_loai: pd.DataFrame, khu_vuc: str) -> str | None:
    """Đếm phần 'Khác nông nghiệp' bị loại khỏi báo cáo để cảnh báo minh bạch."""
    if (
        df_phan_loai is None
        or df_phan_loai.empty
        or COT_TEN_XA not in df_phan_loai.columns
        or _COT_LINH_VUC not in df_phan_loai.columns
    ):
        return None
    mask_kv = phan_loai_khu_vuc_df(df_phan_loai).eq(khu_vuc)
    df_kv = df_phan_loai[mask_kv]
    if df_kv.empty:
        return None
    so_khac = int(df_kv[_COT_LINH_VUC].eq(NN_LINH_VUC_KHAC).sum())
    tong = len(df_kv)
    if so_khac == 0:
        return None
    return f"ℹ️ {so_khac}/{tong} món thuộc \"{NN_LINH_VUC_KHAC}\" đã được loại khỏi thống kê nông nghiệp."


def _thong_tin_bi_loc_linh_vuc(df_phan_loai: pd.DataFrame) -> str | None:
    """Đếm lĩnh vực thuỷ sản / lâm nghiệp ở khu vực thành thị (bị lọc ra khỏi báo cáo phường)."""
    if (
        df_phan_loai is None
        or df_phan_loai.empty
        or COT_TEN_XA not in df_phan_loai.columns
        or _COT_LINH_VUC not in df_phan_loai.columns
    ):
        return None
    kv = phan_loai_khu_vuc_df(df_phan_loai)
    df_tt = df_phan_loai[kv.eq("thanh_thi")]
    if df_tt.empty:
        return None
    mask_loctru = df_tt[_COT_LINH_VUC].isin([NN_LINH_VUC_THUY_SAN, NN_LINH_VUC_LAM_NGHIEP])
    so = int(mask_loctru.sum())
    if so == 0:
        return None
    tong_dn_loctru = (
        pd.to_numeric(df_tt.loc[mask_loctru, COT_TONG_DU_NO], errors="coerce").fillna(0).sum()
        if COT_TONG_DU_NO in df_tt.columns
        else 0
    )
    return (
        f"ℹ️ {so} món Thuỷ sản/Lâm nghiệp ở khu vực phường (tổng DN "
        f"{round(tong_dn_loctru / 1_000_000):,.0f} triệu) đã bị loại khỏi báo cáo thành thị theo quy định "
        f"(chỉ giữ Trồng trọt + Chăn nuôi)."
    ).replace(",", ".")


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


def _dong_tong_hien_thi(df_raw: pd.DataFrame, nhan_nhom: str) -> dict:
    """Dòng TỔNG CỘNG cho bảng hiển thị (triệu đồng). FIX L2_1: guard COT_DU_NO_KHOANH tồn tại trước khi .sum()."""
    dong: dict = {}
    if df_raw is None or df_raw.empty:
        return dong
    df = df_raw.copy()
    for cot in (COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH):
        if cot in df.columns:
            df[cot] = pd.to_numeric(df[cot], errors="coerce").fillna(0)
        else:
            df[cot] = 0.0

    tong_dn = float(df[COT_TONG_DU_NO].sum())
    tong_th = float(df[COT_DU_NO_TH].sum())
    tong_qh = float(df[COT_DU_NO_QH].sum())
    so_kh = _dem_khach_hang(df)
    so_mon = _dem_unique_hop_le(df, COT_SO_KU)

    tong_khoanh = 0.0
    if COT_DU_NO_KHOANH in df.columns:
        df[COT_DU_NO_KHOANH] = pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
        tong_khoanh = float(df[COT_DU_NO_KHOANH].sum())

    dong = {
        nhan_nhom: "TỔNG CỘNG",
        "Số KH": so_kh,
        "Số món": so_mon,
        "Tổng dư nợ": round(tong_dn / 1_000_000),
        "Trong hạn": round(tong_th / 1_000_000),
        "Quá hạn": round(tong_qh / 1_000_000),
        "Khoanh": round(tong_khoanh / 1_000_000),
    }
    dong["Tỷ trọng %"] = 100.0
    dong["Tỷ lệ QH %"] = round(tong_qh / tong_dn * 100, 2) if tong_dn > 0 else 0.0
    dong["BQ/KH"] = round(tong_dn / so_kh / 1_000_000) if so_kh > 0 else 0
    return dong


def _df_to_bytes(df: pd.DataFrame) -> bytes:
    """Chuyển DataFrame → bytes cho @st.cache_data pickle (tránh hash mutable warning)."""
    buf = io.BytesIO()
    pd.to_pickle(df, buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 4 BIỂU ĐỒ PLOTLY (L2_3)
# ---------------------------------------------------------------------------

def _fig_treemap_linh_vuc(df_phan_loai: pd.DataFrame) -> go.Figure | None:
    """Treemap Tỷ trọng Tổng DN theo Lĩnh vực nông nghiệp (toàn CN phạm vi báo cáo)."""
    df_loc = _loc_pham_vi_bao_cao(df_phan_loai)
    if df_loc.empty:
        return None
    df_loc = df_loc.copy()
    df_loc[COT_TONG_DU_NO] = pd.to_numeric(df_loc[COT_TONG_DU_NO], errors="coerce").fillna(0)
    grp = df_loc.groupby(_COT_LINH_VUC, dropna=False)[COT_TONG_DU_NO].sum().reset_index()
    grp.columns = ["Lĩnh vực", "Tổng dư nợ (tỷ)"]
    grp["Tổng dư nợ (tỷ)"] = (grp["Tổng dư nợ (tỷ)"] / 1e9).round(2)
    grp = grp[grp["Tổng dư nợ (tỷ)"] > 0]
    if grp.empty:
        return None
    fig = px.treemap(
        grp, path=[px.Constant("Nông nghiệp"), "Lĩnh vực"], values="Tổng dư nợ (tỷ)",
        color="Tổng dư nợ (tỷ)",
        color_continuous_scale="Greens",
        title="🗺️ Tỷ trọng Dư nợ theo Lĩnh vực Nông nghiệp (tỷ đồng)",
        hover_data={"Tổng dư nợ (tỷ)": ":,.2f"},
    )
    fig.update_layout(height=360, margin=dict(t=50, l=10, r=10, b=10), title_x=0.02)
    return fig


def _fig_top_bottom_xa_tlqh(df_th_xa: pd.DataFrame, nhan_xa: str = "Xã", top_n: int = 15) -> go.Figure | None:
    """Bar chart Top 15 Xã TL QH CAO NHẤT (đỏ) + Thấp NHẤT (xanh)."""
    if df_th_xa is None or df_th_xa.empty:
        return None
    tmp = df_th_xa[df_th_xa[nhan_xa] != "TỔNG CỘNG"].copy() if nhan_xa in df_th_xa.columns else df_th_xa.copy()
    if tmp.empty:
        return None
    col_nhom = nhan_xa
    col_qh = "Tỷ lệ QH %"
    if col_qh not in tmp.columns:
        return None
    tmp = tmp.sort_values(col_qh, ascending=False).reset_index(drop=True)
    top_high = tmp.head(top_n).copy()
    top_high["_loai"] = "🔴 TL QH CAO"
    low_source = tmp.sort_values(col_qh, ascending=True).copy()
    if len(tmp) > top_n:
        high_names = set(top_high[col_nhom].astype(str))
        low_source = low_source[~low_source[col_nhom].astype(str).isin(high_names)]
    top_low = low_source.head(top_n).copy()
    top_low["_loai"] = "🟢 TL QH THẤP"
    comb = pd.concat([top_high, top_low], ignore_index=True)
    comb = comb[comb[col_qh].notna()]
    if comb.empty:
        return None
    fig = px.bar(
        comb, x=col_qh, y=col_nhom, color="_loai", orientation="h",
        color_discrete_map={"🔴 TL QH CAO": _VBSP_RED, "🟢 TL QH THẤP": _VBSP_ACCENT},
        title=f"⚠️ Top {top_n} xã TL QH CAO / THẤP nhất",
        hover_data={col_qh: ":,.2f", nhan_xa: True, "_loai": False},
    )
    fig.add_vline(x=_NGUONG_MD_QH_VANG, line_width=2, line_dash="dash", line_color=_VBSP_AMBER, annotation_text=f"Ngưỡng {_NGUONG_MD_QH_VANG:.0f}%")
    fig.add_vline(x=_NGUONG_XA_QH_DO, line_width=2, line_dash="dash", line_color=_VBSP_RED, annotation_text=f"Ngưỡng {_NGUONG_XA_QH_DO:.0f}%")
    fig.update_layout(height=max(420, 28 * len(comb)), margin=dict(t=50, l=260, r=10, b=40), title_x=0.02, yaxis_title="", xaxis_title="Tỷ lệ QH (%)")
    return fig


def _fig_pgd_tlqh(df_th_pgd: pd.DataFrame) -> go.Figure | None:
    """Bar chart Tỷ lệ QH theo PGD (để role CN theo dõi 21 PGD)."""
    if df_th_pgd is None or df_th_pgd.empty:
        return None
    tmp = df_th_pgd.copy()
    col_pgd = [c for c in ("PGD", COT_TEN_PGD) if c in tmp.columns]
    if not col_pgd:
        return None
    col_pgd = col_pgd[0]
    col_qh = "Tỷ lệ QH %"
    if col_qh not in tmp.columns:
        return None
    tmp = tmp[tmp[col_pgd] != "TỔNG CỘNG"] if col_pgd in tmp.columns else tmp
    tmp = tmp.sort_values(col_qh, ascending=False)
    if tmp.empty:
        return None
    def _mau(tl):
        if tl >= _NGUONG_XA_QH_DO:
            return _VBSP_RED
        elif tl >= _NGUONG_MD_QH_VANG:
            return _VBSP_ORANGE
        elif tl >= 1.5:
            return _VBSP_AMBER
        return _VBSP_ACCENT
    colors = [_mau(x) for x in tmp[col_qh].fillna(0).tolist()]
    fig = go.Figure(go.Bar(
        x=tmp[col_pgd].astype(str), y=tmp[col_qh], marker_color=colors,
        text=[f"{v:.1f}%" if pd.notna(v) else "" for v in tmp[col_qh]], textposition="outside",
    ))
    fig.add_hline(y=_NGUONG_MD_QH_VANG, line_dash="dash", line_color=_VBSP_AMBER, annotation_text=f"Ngưỡng {_NGUONG_MD_QH_VANG:.0f}%")
    fig.add_hline(y=_NGUONG_XA_QH_DO, line_dash="dash", line_color=_VBSP_RED, annotation_text=f"Ngưỡng {_NGUONG_XA_QH_DO:.0f}%")
    fig.update_layout(
        title=f"📍 Tỷ lệ QH theo Đơn vị (PGD) — {len(tmp)} đơn vị",
        height=400, margin=dict(t=50, l=10, r=10, b=160),
        xaxis_title="", yaxis_title="Tỷ lệ QH (%)",
        title_x=0.02, showlegend=False,
    )
    fig.update_xaxes(tickangle=-45)
    return fig


def _fig_top10_muc_dich(df_th_md: pd.DataFrame, nhan_md: str = "Mục đích") -> go.Figure | None:
    """Horizontal bar Top 10 Mục đích / Lĩnh vực có Tổng DN lớn nhất."""
    if df_th_md is None or df_th_md.empty:
        return None
    tmp = df_th_md.copy()
    if nhan_md not in tmp.columns or "Tổng dư nợ" not in tmp.columns:
        return None
    tmp = tmp[tmp[nhan_md] != "TỔNG CỘNG"]
    tmp = tmp.sort_values("Tổng dư nợ", ascending=False).head(10)
    if tmp.empty:
        return None
    fig = px.bar(
        tmp, x="Tổng dư nợ", y=nhan_md, orientation="h",
        color_discrete_sequence=[_VBSP_GREEN],
        title="📈 Top 10 Mục đích sử dụng vốn có Tổng dư nợ lớn nhất (triệu đồng)",
        hover_data={"Tổng dư nợ": ":,.0f"},
    )
    fig.update_layout(height=max(420, 32 * len(tmp)), margin=dict(t=50, l=320, r=10, b=40), title_x=0.02, yaxis_title="", xaxis_title="Tổng dư nợ (triệu đồng)")
    fig.update_yaxes(autorange="reversed")
    return fig


# ---------------------------------------------------------------------------
# 4 CẢNH BÁO SỚM (L2_4)
# ---------------------------------------------------------------------------

def _tao_canh_bao(
    df_th_xa_nt: pd.DataFrame,
    df_th_md_nt: pd.DataFrame,
    df_th_pgd_all: pd.DataFrame,
    df_phan_loai: pd.DataFrame,
) -> pd.DataFrame:
    """Trả về DataFrame các cảnh báo sớm để hiển thị + export Excel."""
    rows = []
    # 1. Xã có TL QH ≥ 5% (đỏ)
    if not df_th_xa_nt.empty and "Tỷ lệ QH %" in df_th_xa_nt.columns:
        tmp = df_th_xa_nt[df_th_xa_nt["Xã"] != "TỔNG CỘNG"] if "Xã" in df_th_xa_nt.columns else df_th_xa_nt.copy()
        for _, r in tmp[tmp["Tỷ lệ QH %"] >= _NGUONG_XA_QH_DO].iterrows():
            rows.append({
                "Mức": "🔴 Nghiêm trọng",
                "Loại": "Xã TL QH ≥ 5%",
                "Đối tượng": str(r.get("Xã", "")),
                "Giá trị": f"{float(r.get('Tỷ lệ QH %', 0)):.2f}%",
                "Tổng DN (triệu)": f"{float(r.get('Tổng dư nợ', 0)):,.0f}".replace(",", "."),
                "Gợi ý": "Rà soát hồ sơ, tổ chức bám thu, báo cáo lãnh đạo",
            })

    # 2. Mục đích có TL QH ≥ 3% (vàng)
    if not df_th_md_nt.empty and "Tỷ lệ QH %" in df_th_md_nt.columns:
        fallback_cols = [
            c for c in df_th_md_nt.columns
            if c not in {
                "Số KH", "Số món", "Tổng dư nợ", "Trong hạn", "Quá hạn",
                "Khoanh", "Tỷ trọng %", "Tỷ lệ QH %", "BQ/KH",
            }
        ]
        col_nhom = "Mục đích" if "Mục đích" in df_th_md_nt.columns else next(iter(fallback_cols), None)
        if col_nhom is not None:
            tmp = df_th_md_nt[df_th_md_nt[col_nhom] != "TỔNG CỘNG"].copy()
            for _, r in tmp[tmp["Tỷ lệ QH %"] >= _NGUONG_MD_QH_VANG].iterrows():
                rows.append({
                    "Mức": "🟠 Cảnh báo",
                    "Loại": "Mục đích TL QH ≥ 3%",
                    "Đối tượng": str(r.get(col_nhom, "")),
                    "Giá trị": f"{float(r.get('Tỷ lệ QH %', 0)):.2f}%",
                    "Tổng DN (triệu)": f"{float(r.get('Tổng dư nợ', 0)):,.0f}".replace(",", "."),
                    "Gợi ý": "Phân tích nguyên nhân QH ở nhóm mục đích này, tăng cường giám sát",
                })

    # 3. PGD chênh lệch cao (TL QH > trung bình + 2 std)
    if not df_th_pgd_all.empty and "Tỷ lệ QH %" in df_th_pgd_all.columns:
        col_pgd = "PGD" if "PGD" in df_th_pgd_all.columns else (COT_TEN_PGD if COT_TEN_PGD in df_th_pgd_all.columns else None)
        if col_pgd is not None:
            tmp = df_th_pgd_all[df_th_pgd_all[col_pgd] != "TỔNG CỘNG"].copy()
            vals = pd.to_numeric(tmp["Tỷ lệ QH %"], errors="coerce").fillna(0)
            if len(vals) >= 3:
                mean = float(vals.mean())
                std = float(vals.std())
                nguong_cao = mean + 2 * std
                for _, r in tmp[vals >= nguong_cao].iterrows():
                    rows.append({
                        "Mức": "🟡 Chú ý",
                        "Loại": "PGD TL QH chênh cao (>mean+2σ)",
                        "Đối tượng": str(r.get(col_pgd, "")),
                        "Giá trị": f"{float(r.get('Tỷ lệ QH %', 0)):.2f}% (mean={mean:.2f}%)",
                        "Tổng DN (triệu)": f"{float(r.get('Tổng dư nợ', 0)):,.0f}".replace(",", "."),
                        "Gợi ý": "Chia sẻ kinh nghiệm từ PGD TL QH thấp; kiểm tra quy trình thu hồi",
                    })

    # 4. Phường có Thuỷ sản / Lâm nghiệp bị lọc
    note_extra = _thong_tin_bi_loc_linh_vuc(df_phan_loai)
    if note_extra:
        rows.append({
            "Mức": "ℹ️ Thông tin",
            "Loại": "Lĩnh vực bị loại khỏi báo cáo phường",
            "Đối tượng": "Thuỷ sản / Lâm nghiệp (phường)",
            "Giá trị": "→ xem chi tiết bên dưới",
            "Tổng DN (triệu)": "—",
            "Gợi ý": "Nếu cần bao gồm, điều chỉnh _LINH_VUC_THANH_THI (hiện chỉ Trồng trọt + Chăn nuôi)",
        })

    if not rows:
        rows.append({
            "Mức": "✅ An toàn",
            "Loại": "Không có cảnh báo vượt ngưỡng",
            "Đối tượng": "Toàn bộ chỉ số",
            "Giá trị": "—",
            "Tổng DN (triệu)": "—",
            "Gợi ý": "Tiếp tục duy trì công tác giám sát định kỳ",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# RENDER CHÍNH
# ---------------------------------------------------------------------------

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

    # --- L2_1: convention widget key_prefix
    slug = pgd_slug(pgd_user) if pgd_user else ""
    _kp = f"pgd_{slug}_" if slug else "cn_"

    ctx.subheader("🌾 Báo cáo Nông nghiệp")

    df_scope = df.copy()

    if la_phan_he_pgd(role) and pgd_user:
        if COT_TEN_PGD in df_scope.columns:
            df_scope = df_scope[df_scope[COT_TEN_PGD] == pgd_user]
        ctx.info(f"📍 Đang xem báo cáo của PGD: **{pgd_user}**")
    elif COT_TEN_PGD in df_scope.columns:
        ds_pgd = ["Tất cả"] + sorted(df_scope[COT_TEN_PGD].dropna().unique().tolist())
        pgd_chon = ctx.selectbox("📍 PGD", ds_pgd, key=f"{_kp}nn_pgd")
        if pgd_chon != "Tất cả":
            df_scope = df_scope[df_scope[COT_TEN_PGD] == pgd_chon]

    with ctx.spinner("⏳ Đang chuẩn bị dữ liệu báo cáo nông nghiệp..."):
        df_scope = chuan_bi_du_lieu_bao_cao(df_scope)
        if df_scope is None or df_scope.empty:
            ctx.warning("⚠️ Không có khoản vay phù hợp.")
            return

        df_phan_loai = _gan_linh_vuc(df_scope)
        kv = phan_loai_khu_vuc_df(df_phan_loai)

        df_nn = _loc_pham_vi_bao_cao(df_phan_loai)
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
            {"label": "Tổng dư nợ", "value": tong_dn / 1e9, "icon": "🌾", "suffix": "tỷ", "precision": 3},
            {"label": "Số KH", "value": so_kh, "icon": "👥", "precision": 0},
            {"label": "Số món", "value": so_mon, "icon": "📄", "precision": 0},
            {"label": "Tỷ lệ QH", "value": round(tong_qh / tong_dn * 100, 2) if tong_dn > 0 else 0.0, "icon": "⚠️", "suffix": "%", "precision": 2, "delta_color": "inverse"},
        ], num_columns=4)

        ctx.divider()

        # --- L2_3: 4 biểu đồ plotly (2 rows x 2 cols) ---
        ctx.markdown("##### 📊 Trực quan tổng quan")
        with ctx.spinner("⏳ Đang vẽ biểu đồ..."):
            df_bytes_nn = _df_to_bytes(df_nn)
            c1, c2 = ctx.columns(2)
            with c1:
                fig_a = _fig_treemap_linh_vuc(df_phan_loai)
                if fig_a is not None:
                    st.plotly_chart(fig_a, use_container_width=True, key=f"{_kp}nn_fig_a")

            # Tổng hợp mục đích (nông thôn) cho fig d:
            df_raw_nt = df_phan_loai[kv.eq("nong_thon")]
            df_bytes_nt = _df_to_bytes(df_raw_nt)
            df_th_md_nt_raw = _tong_hop_theo_cot_cached(df_bytes_nt, COT_TEN_PNKT51)
            df_th_md_nt = _df_hien_thi(df_th_md_nt_raw, COT_TEN_PNKT51, "Mục đích") if not df_th_md_nt_raw.empty else pd.DataFrame()

            with c2:
                fig_d = _fig_top10_muc_dich(df_th_md_nt, nhan_md="Mục đích")
                if fig_d is not None:
                    st.plotly_chart(fig_d, use_container_width=True, key=f"{_kp}nn_fig_d")

            # Tổng hợp PGD (toàn phạm vi báo cáo) cho fig c + cảnh báo:
            df_th_pgd_raw = _tong_hop_theo_cot_cached(df_bytes_nn, COT_TEN_PGD)
            df_th_pgd = _df_hien_thi(df_th_pgd_raw, COT_TEN_PGD, "PGD") if not df_th_pgd_raw.empty else pd.DataFrame()
            if not df_th_pgd.empty:
                _dong = _dong_tong_hien_thi(df_th_pgd_raw, "PGD")
                if _dong:
                    df_th_pgd.loc[len(df_th_pgd)] = _dong

            # Tổng hợp Xã NT cho fig b + cảnh báo:
            df_th_xa_raw = _tong_hop_theo_cot_cached(df_bytes_nt, COT_TEN_XA)
            df_th_xa_nt = _df_hien_thi(df_th_xa_raw, COT_TEN_XA, "Xã") if not df_th_xa_raw.empty else pd.DataFrame()

            c3, c4 = ctx.columns(2)
            with c3:
                fig_c = _fig_pgd_tlqh(df_th_pgd)
                if fig_c is not None:
                    st.plotly_chart(fig_c, use_container_width=True, key=f"{_kp}nn_fig_c")
            with c4:
                fig_b = _fig_top_bottom_xa_tlqh(df_th_xa_nt, nhan_xa="Xã", top_n=15)
                if fig_b is not None:
                    st.plotly_chart(fig_b, use_container_width=True, key=f"{_kp}nn_fig_b")

        ctx.divider()

        # --- L2_4: Block cảnh báo sớm expander ---
        df_cb = _tao_canh_bao(df_th_xa_nt, df_th_md_nt, df_th_pgd, df_phan_loai)
        with ctx.expander("🚨 Cảnh báo sớm (4 loại)", expanded=True):
            if df_cb is None or df_cb.empty:
                st.caption("Không có cảnh báo nào.")
            else:
                # Mức màu
                def _tag_muc(m):
                    if isinstance(m, str) and "Nghiêm trọng" in m:
                        return f"<span style='background:#ffebee;color:#C62828;padding:2px 10px;border-radius:999px;font-weight:600;'>{m}</span>"
                    if isinstance(m, str) and "Cảnh báo" in m:
                        return f"<span style='background:#fff3e0;color:#EF6C00;padding:2px 10px;border-radius:999px;font-weight:600;'>{m}</span>"
                    if isinstance(m, str) and "Chú ý" in m:
                        return f"<span style='background:#fff8e1;color:#E65100;padding:2px 10px;border-radius:999px;font-weight:600;'>{m}</span>"
                    if isinstance(m, str) and "An toàn" in m:
                        return f"<span style='background:#e8f5e9;color:#1B5E20;padding:2px 10px;border-radius:999px;font-weight:600;'>{m}</span>"
                    return f"<span style='background:#e3f2fd;color:#0d47a1;padding:2px 10px;border-radius:999px;font-weight:600;'>{m}</span>"
                df_cb_show = df_cb.copy()
                df_cb_show["Mức"] = df_cb_show["Mức"].map(_tag_muc)
                styler = df_cb_show.style.set_properties(**{
                    "text-align": "left", "padding": "6px 8px", "border": "1px solid #e0e0e0", "font-size": "13px",
                }).hide(axis="index")
                st.markdown(styler.set_table_styles([
                    dict(selector="th", props=[("background", _VBSP_GREEN), ("color", "#fff"), ("padding", "6px 8px"), ("font-weight", "700")]),
                ]).to_html(escape=False), unsafe_allow_html=True)
                note_extra = _thong_tin_bi_loc_linh_vuc(df_phan_loai)
                if note_extra:
                    st.caption(note_extra)

        ctx.divider()

        # --- L2_1: column config + 2 khu vực tabs ---
        cfg = {}
        for cot in _COT_DEM:
            cfg[cot] = st.column_config.NumberColumn(cot, format="%d")
        for cot in _COT_TIEN:
            cfg[cot] = st.column_config.NumberColumn(cot, format="%,.0f")
        for cot in _COT_PHAN_TRAM:
            cfg[cot] = st.column_config.NumberColumn(cot, format="%.2f")

        t1, t2 = ctx.tabs(["🌾 Xã nông thôn", "🏙️ Phường (thành thị)"])

        with t1:
            if df_raw_nt.empty:
                st.info("Không có dữ liệu ở khu vực nông thôn.")
            else:
                # -- Theo Mục đích --
                df_th_nt = df_th_md_nt_raw
                if df_th_nt.empty:
                    st.info("Không có dữ liệu theo mục đích.")
                else:
                    st.markdown("###### 🎯 Theo Mục đích sử dụng vốn")
                    df_hien_nt = _df_hien_thi(df_th_nt, COT_TEN_PNKT51, "Mục đích")
                    dong_nt = _dong_tong_hien_thi(df_raw_nt, "Mục đích")
                    if dong_nt:
                        df_hien_nt.loc[len(df_hien_nt)] = dong_nt
                    # L2_6: highlight tổng qua HTML (bảng 9 cột >=8 rule)
                    html_nt = _styler_html_table(df_hien_nt, highlight_last=True)
                    if html_nt:
                        st.markdown(html_nt, unsafe_allow_html=True)
                    else:
                        st.dataframe(df_hien_nt, use_container_width=True, hide_index=True, column_config=cfg)

                # -- L2_2: Bảng THEO PGD --
                st.markdown("###### 📍 Theo Đơn vị (PGD)")
                if COT_TEN_PGD not in df_raw_nt.columns:
                    st.caption("⚠️ Dữ liệu không có cột PGD.")
                else:
                    df_th_pgd_nt_raw = _tong_hop_theo_cot_cached(df_bytes_nt, COT_TEN_PGD)
                    if df_th_pgd_nt_raw.empty:
                        st.info("Không có dữ liệu.")
                    else:
                        df_hien_pgd_nt = _df_hien_thi(df_th_pgd_nt_raw, COT_TEN_PGD, "PGD")
                        dong_pgd_nt = _dong_tong_hien_thi(df_raw_nt, "PGD")
                        if dong_pgd_nt:
                            df_hien_pgd_nt.loc[len(df_hien_pgd_nt)] = dong_pgd_nt
                        html_pgd = _styler_html_table(df_hien_pgd_nt, highlight_last=True)
                        if html_pgd:
                            st.markdown(html_pgd, unsafe_allow_html=True)
                        else:
                            st.dataframe(df_hien_pgd_nt, use_container_width=True, hide_index=True, column_config=cfg)

                # -- Theo Xã --
                st.markdown("#### 🏘️ Theo Xã")
                if not df_th_xa_raw.empty:
                    df_hien_xa = _df_hien_thi(df_th_xa_raw, COT_TEN_XA, "Xã")
                    dong_xa = _dong_tong_hien_thi(df_raw_nt, "Xã")
                    if dong_xa:
                        df_hien_xa.loc[len(df_hien_xa)] = dong_xa
                    html_xa = _styler_html_table(df_hien_xa, highlight_last=True)
                    if html_xa:
                        st.markdown(html_xa, unsafe_allow_html=True)
                    else:
                        st.dataframe(df_hien_xa, use_container_width=True, hide_index=True, column_config=cfg)
                else:
                    st.info("Không có dữ liệu.")

        with t2:
            df_raw_tt = df_phan_loai[kv.eq("thanh_thi")]
            df_raw_tt_scoped = df_raw_tt[df_raw_tt[_COT_LINH_VUC].isin(_LINH_VUC_THANH_THI)]
            df_bytes_tt = _df_to_bytes(df_raw_tt)
            df_bytes_tt_scoped = _df_to_bytes(df_raw_tt_scoped)
            df_th_tt = _tong_hop_linh_vuc_cached(df_bytes_tt, tuple(_LINH_VUC_THANH_THI))
            if df_th_tt.empty:
                st.info("Không có dữ liệu trồng trọt/chăn nuôi ở khu vực phường.")
            else:
                note = _thong_tin_khac(df_phan_loai, "thanh_thi")
                if note:
                    st.caption(note)
                st.markdown("###### 🌱 Theo Lĩnh vực")
                df_hien_tt = _df_hien_thi(df_th_tt, _COT_LINH_VUC, "Lĩnh vực")
                dong_tt = _dong_tong_hien_thi(df_raw_tt_scoped, "Lĩnh vực")
                if dong_tt:
                    df_hien_tt.loc[len(df_hien_tt)] = dong_tt
                html_tt = _styler_html_table(df_hien_tt, highlight_last=True)
                if html_tt:
                    st.markdown(html_tt, unsafe_allow_html=True)
                else:
                    st.dataframe(df_hien_tt, use_container_width=True, hide_index=True, column_config=cfg)

                # -- L2_2: Bảng THEO PGD khu vực thành thị --
                st.markdown("###### 📍 Theo Đơn vị (PGD)")
                if COT_TEN_PGD not in df_raw_tt_scoped.columns:
                    st.caption("⚠️ Dữ liệu không có cột PGD.")
                else:
                    df_th_pgd_tt_raw = _tong_hop_theo_cot_cached(df_bytes_tt_scoped, COT_TEN_PGD)
                    if df_th_pgd_tt_raw.empty:
                        st.info("Không có dữ liệu.")
                    else:
                        df_hien_pgd_tt = _df_hien_thi(df_th_pgd_tt_raw, COT_TEN_PGD, "PGD")
                        dong_pgd_tt = _dong_tong_hien_thi(df_raw_tt_scoped, "PGD")
                        if dong_pgd_tt:
                            df_hien_pgd_tt.loc[len(df_hien_pgd_tt)] = dong_pgd_tt
                        html_pgd_tt = _styler_html_table(df_hien_pgd_tt, highlight_last=True)
                        if html_pgd_tt:
                            st.markdown(html_pgd_tt, unsafe_allow_html=True)
                        else:
                            st.dataframe(df_hien_pgd_tt, use_container_width=True, hide_index=True, column_config=cfg)

                st.markdown("#### 🏘️ Theo Phường")
                df_th_ph_raw = _tong_hop_theo_cot_cached(df_bytes_tt_scoped, COT_TEN_XA)
                if df_th_ph_raw.empty:
                    st.info("Không có dữ liệu.")
                else:
                    df_hien_ph = _df_hien_thi(df_th_ph_raw, COT_TEN_XA, "Phường")
                    dong_ph = _dong_tong_hien_thi(df_raw_tt_scoped, "Phường")
                    if dong_ph:
                        df_hien_ph.loc[len(df_hien_ph)] = dong_ph
                    html_ph = _styler_html_table(df_hien_ph, highlight_last=True)
                    if html_ph:
                        st.markdown(html_ph, unsafe_allow_html=True)
                    else:
                        st.dataframe(df_hien_ph, use_container_width=True, hide_index=True, column_config=cfg)

        # --- L2_5: EXCEL 6 SHEET ---
        with ctx.spinner("⏳ Đang chuẩn bị file xuất..."):
            sheets: dict[str, pd.DataFrame] = {}

            # 1. Tổng quan KPI
            kpi_row_xl = pd.DataFrame([{
                "Chỉ tiêu": "Tổng dư nợ (tỷ đồng)",
                "Giá trị": round(tong_dn / 1e9, 3),
                "Đơn vị": "tỷ đồng",
            }, {
                "Chỉ tiêu": "Số khách hàng",
                "Giá trị": so_kh,
                "Đơn vị": "người",
            }, {
                "Chỉ tiêu": "Số món vay",
                "Giá trị": so_mon,
                "Đơn vị": "món",
            }, {
                "Chỉ tiêu": "Tỷ lệ quá hạn",
                "Giá trị": round(tong_qh / tong_dn * 100, 2) if tong_dn > 0 else 0.0,
                "Đơn vị": "%",
            }])
            sheets["01_Tong_quan_KPI"] = kpi_row_xl

            # 2. Xã nông thôn (theo mục đích)
            if not df_th_md_nt.empty:
                df_nt_xuat = df_th_md_nt.copy()
                if "TỔNG CỘNG" not in df_nt_xuat.get("Mục đích", pd.Series(dtype="string")).astype(str).values:
                    dong_nt_xuat = _dong_tong_hien_thi(df_raw_nt, "Mục đích")
                    if dong_nt_xuat:
                        df_nt_xuat.loc[len(df_nt_xuat)] = dong_nt_xuat
                sheets["02_Xa_nong_thon"] = df_nt_xuat

            # 3. Phường thành thị (theo lĩnh vực)
            if not df_th_tt.empty:
                df_tt_xuat = _df_hien_thi(df_th_tt, _COT_LINH_VUC, "Lĩnh vực")
                if dong_tt:
                    df_tt_xuat.loc[len(df_tt_xuat)] = dong_tt
                sheets["03_Phuong_thanh_thi"] = df_tt_xuat

            # 4. Theo PGD (toàn phạm vi báo cáo)
            if not df_th_pgd.empty:
                sheets["04_Theo_PGD"] = df_th_pgd

            # 5. Top 10 Tổng dư nợ theo xã (toàn CN)
            if not df_th_xa_nt.empty and "Tổng dư nợ" in df_th_xa_nt.columns:
                tmp = df_th_xa_nt[df_th_xa_nt["Xã"] != "TỔNG CỘNG"] if "Xã" in df_th_xa_nt.columns else df_th_xa_nt.copy()
                tmp = tmp.sort_values("Tổng dư nợ", ascending=False).head(10)
                sheets["05_Top10_Xa_DN_max"] = tmp.reset_index(drop=True)

            # 6. Cảnh báo sớm
            if df_cb is not None and not df_cb.empty:
                df_cb_xl = df_cb.copy()
                df_cb_xl.columns = [c.replace("<", "").replace(">", "") for c in df_cb_xl.columns]
                sheets["06_Canh_bao_som"] = df_cb_xl

        col_xl, col_pdf = ctx.columns(2)
        if sheets:
            with col_xl:
                buf = xuat_excel(sheets)
                st.download_button(
                    "⬇️ Tải Excel (.xlsx) - 6 sheet",
                    data=buf,
                    file_name="BaoCao_NongNghiep.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"{_kp}nn_dl_xl",
                    use_container_width=True,
                )

        try:
            pdf_bytes = _xuat_pdf_nong_nghiep(df_phan_loai, kv, username)
        except Exception as e:
            logger.error("nong_nghiep: lỗi tạo PDF — %s", e, exc_info=True)
            ctx.caption(f"⚠️ Không tạo được PDF: {e}")
            pdf_bytes = None
        if pdf_bytes:
            with col_pdf:
                st.download_button(
                    "⬇️ Tải PDF (.pdf)",
                    data=pdf_bytes,
                    file_name="BaoCao_NongNghiep.pdf",
                    mime="application/pdf",
                    key=f"{_kp}nn_dl_pdf",
                    use_container_width=True,
                )
