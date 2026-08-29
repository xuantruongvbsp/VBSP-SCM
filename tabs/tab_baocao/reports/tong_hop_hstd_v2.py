"""Báo cáo tổng hợp từ HSTD v2 - UX nâng cao."""
from __future__ import annotations

import re
import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING

from config import (
    COT_TEN_PGD, COT_TEN_XA, COT_TEN_THON, COT_TEN_CT,
    COT_NGUON_VON, COT_DVUT, COT_TEN_TO,
    COT_MA_KH, COT_SO_KU, COT_TEN_PNKT51, COT_TONG_DU_NO,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH,
)
from auth import la_phan_he_pgd
from utils import fmt_so
from pdf_service import xuat_pdf
from data.hstd import doc_baseline_merged, ts_baseline_merged

from ..components.inline_filter import (
    chuan_bi_du_lieu_bao_cao,
    _chuan_hoa_nguon_von,
    chuan_hoa_nhom_nguon_von,
    loc_khu_vuc,
    phan_loai_khu_vuc_df,
    render_combined_filter_search,
    render_inline_filter,
    render_khu_vuc_filter,
    render_nguon_von_filter,
)
from ..components.sticky_table import render_bang_chi_tiet_html, render_sticky_table
from ..components.quick_export import render_quick_export_buttons
from ..components.tooltip import render_header_with_tooltip, render_formula_reference
from ..components.alert_suggestion import render_combined_alerts_suggestions
from logger import get_logger

logger = get_logger(__name__)

_NHOM_KHONG_XAC_DINH = "Chưa xác định"
_COT_SO_SANH_KHU_VUC = "_khu_vuc_so_sanh"
_NHAN_KHU_VUC = {
    "thanh_thi": "Thành thị",
    "nong_thon": "Nông thôn",
    "": _NHOM_KHONG_XAC_DINH,
}

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


_NGUONG_CANH_BAO_MD_PHAN_TRAM = 5.0


def _thong_diep_muc_dich_chua_xac_dinh(
    df_th: pd.DataFrame,
    group_col: str,
    df_group: pd.DataFrame,
    nguong_phan_tram: float = _NGUONG_CANH_BAO_MD_PHAN_TRAM,
) -> str | None:
    """Trả thông điệp cảnh báo khi nhóm Chưa xác định chiếm >= ngưỡng dư nợ, ngược lại None."""
    required_cols = {group_col, "Tỷ_trọng_%", "Tổng_dư_nợ"}
    if df_th is None or df_th.empty or not required_cols.issubset(df_th.columns):
        return None
    dong_cxd = df_th[df_th[group_col].eq(_NHOM_KHONG_XAC_DINH)]
    if dong_cxd.empty:
        return None
    ty_trong = float(dong_cxd["Tỷ_trọng_%"].sum())
    if ty_trong < nguong_phan_tram:
        return None
    dn_cxd = float(dong_cxd["Tổng_dư_nợ"].sum())
    msg = (
        f"⚠️ Nhóm \"{_NHOM_KHONG_XAC_DINH}\" chiếm {ty_trong:.1f}% dư nợ "
        f"(≈ {dn_cxd / 1e9:.1f} tỷ) — dữ liệu thiếu mục đích sử dụng vốn "
        "(Tên PNKT51), số liệu theo mục đích vốn ở phạm vi này chưa đầy đủ."
    ).replace(".", ",")
    required_group_cols = {COT_TEN_PGD, group_col, COT_TONG_DU_NO}
    if df_group is not None and required_group_cols.issubset(df_group.columns):
        cxd = df_group[df_group[group_col].eq(_NHOM_KHONG_XAC_DINH)]
        if not cxd.empty:
            cxd = cxd.copy()
            cxd[COT_TONG_DU_NO] = pd.to_numeric(cxd[COT_TONG_DU_NO], errors="coerce").fillna(0)
            top_pgd = (
                cxd.groupby(COT_TEN_PGD)[COT_TONG_DU_NO]
                .sum()
                .sort_values(ascending=False)
                .head(3)
            )
            ds = ", ".join(
                f"{pgd} ({gia_tri / 1e9:.1f} tỷ)".replace(".", ",")
                for pgd, gia_tri in top_pgd.items()
                if gia_tri > 0
            )
            if ds:
                msg += f" Thiếu nhiều nhất: {ds}."
    return msg


def _ds_nam_baseline_hstd() -> list[int]:
    """Các năm đã có baseline HSTD 31/12 (giảm dần), quét data/baseline_pgd."""
    from config import BASELINE_PGD_DIR

    if not BASELINE_PGD_DIR.exists():
        return []
    nam = set()
    for f in BASELINE_PGD_DIR.rglob("HSTD_3112_*.XLSX"):
        try:
            nam.add(int(f.stem.split("_")[-1]))
        except ValueError:
            continue
    return sorted(nam, reverse=True)


def _loc_nguon_von_baseline(df: pd.DataFrame, chon: str) -> pd.DataFrame:
    """Lọc nghiêm baseline theo nguồn vốn đang chọn; không trả ngược toàn bảng khi không khớp."""
    if df is None or df.empty or COT_NGUON_VON not in df.columns or chon == "all":
        return df
    if chon not in {"1", "2"}:
        return df
    return df.loc[df[COT_NGUON_VON].map(_chuan_hoa_nguon_von).eq(chon)].copy()


def _doc_baseline_cung_pham_vi(
    selected_report: str,
    group_col: str,
    role: str,
    pgd_user: str,
    hien_loc_pgd: bool,
    filter_cols: list[str],
) -> tuple[pd.DataFrame | None, int | None]:
    """Đọc baseline 31/12 năm gần nhất và thu hẹp ĐÚNG phạm vi các bộ lọc hiện tại.

    Tái áp dụng trạng thái widget (PGD, Xã/Chương trình, Nguồn vốn, Khu vực,
    tìm kiếm) lên baseline để cột so sánh cùng khẩu vị với dữ liệu hiện tại.
    Trả (df_baseline hoặc None, năm baseline hoặc None).
    """
    ds_nam = _ds_nam_baseline_hstd()
    if not ds_nam:
        return None, None
    nam_bl = max(ds_nam)
    try:
        df_bl = doc_baseline_merged(nam_bl, ts=ts_baseline_merged(nam_bl))
    except Exception as e:
        logger.error(
            "_doc_baseline_cung_pham_vi: lỗi đọc baseline 31/12/%s — %s",
            nam_bl, e, exc_info=True,
        )
        return None, None
    if df_bl is None or df_bl.empty:
        return None, None
    df_bl = df_bl.copy()

    # Phạm vi PGD theo role (user PGD chỉ thấy đơn vị mình)
    if la_phan_he_pgd(role) and pgd_user and COT_TEN_PGD in df_bl.columns:
        df_bl = df_bl[df_bl[COT_TEN_PGD] == pgd_user]

    # Tái áp dụng các selectbox chỉ khi widget tương ứng đang hiển thị
    trang_thai: list[tuple[str, str]] = []
    if hien_loc_pgd:
        trang_thai.append(
            (f"filter_th_{selected_report}_pgd_{COT_TEN_PGD}", COT_TEN_PGD)
        )
    for cot in filter_cols:
        trang_thai.append((f"filter_th_{selected_report}_filter_{cot}", cot))
    for khoa, cot in trang_thai:
        gia_tri = st.session_state.get(khoa)
        if gia_tri and gia_tri != "Tất cả" and cot in df_bl.columns:
            df_bl = df_bl[df_bl[cot] == gia_tri]

    df_bl = _loc_nguon_von_baseline(
        df_bl,
        st.session_state.get(f"nv_filter_th_{selected_report}", "all"),
    )
    df_bl = loc_khu_vuc(df_bl, st.session_state.get(f"kv_filter_th_{selected_report}", "all"))

    # Tái áp dụng tìm kiếm nhanh (PGD / Xã / Mục đích vốn / Mã KH)
    tu_khoa = str(st.session_state.get(f"quick_search_th_{selected_report}_search", "") or "").strip()
    if tu_khoa:
        mask = pd.Series(False, index=df_bl.index)
        for cot in (COT_TEN_PGD, COT_TEN_XA, COT_TEN_PNKT51, COT_MA_KH):
            if cot in df_bl.columns:
                mask |= df_bl[cot].astype(str).str.lower().str.contains(
                    tu_khoa.lower(), na=False
                )
        df_bl = df_bl[mask]

    df_bl = chuan_bi_du_lieu_bao_cao(df_bl)
    if df_bl is None:
        return None, nam_bl
    return df_bl, nam_bl


def _danh_sach_tieu_chi_so_sanh(df: pd.DataFrame) -> list[tuple[str, str]]:
    tieu_chi = [("Khu vực", _COT_SO_SANH_KHU_VUC)]
    for label, col in [
        ("PGD", COT_TEN_PGD),
        ("Xã/phường", COT_TEN_XA),
        ("Chương trình", COT_TEN_CT),
        ("Mục đích vốn", COT_TEN_PNKT51),
        ("Nguồn vốn", COT_NGUON_VON),
        ("ĐVUT", COT_DVUT),
        ("CBTD/Tổ", COT_TEN_TO),
    ]:
        if col in df.columns:
            tieu_chi.append((label, col))
    return tieu_chi


def _tao_so_sanh_du_no_theo_tieu_chi(
    df_filtered: pd.DataFrame,
    tieu_chi_chon: list[str] | None = None,
    top_n: int | None = 10,
) -> pd.DataFrame:
    """Tạo bảng so sánh dư nợ theo nhiều tiêu chí, giữ cùng quy tắc đếm của Tổng hợp HSTD."""
    if df_filtered is None or df_filtered.empty:
        return pd.DataFrame()

    ds_tieu_chi = _danh_sach_tieu_chi_so_sanh(df_filtered)
    if tieu_chi_chon is not None and not tieu_chi_chon:
        return pd.DataFrame()
    if tieu_chi_chon is not None:
        ds_tieu_chi = [(label, col) for label, col in ds_tieu_chi if label in tieu_chi_chon]

    rows: list[pd.DataFrame] = []
    for label, group_col in ds_tieu_chi:
        df_scope = df_filtered.copy()
        selected_report = ""
        if label == "Khu vực":
            df_scope[_COT_SO_SANH_KHU_VUC] = (
                phan_loai_khu_vuc_df(df_scope).map(_NHAN_KHU_VUC).fillna(_NHOM_KHONG_XAC_DINH)
            )
        elif group_col == COT_NGUON_VON:
            selected_report = "nv"

        df_th, _, _ = _tao_tong_hop_theo_nhom(df_scope, selected_report, group_col)
        if df_th.empty:
            continue

        df_top = df_th.head(top_n).copy() if top_n and top_n > 0 else df_th.copy()
        tong_tieu_chi = float(df_th["Tổng_dư_nợ"].sum())
        out = pd.DataFrame({
            "Tiêu chí": label,
            "Nhóm": df_top[group_col].astype(str),
            "Xếp hạng": range(1, len(df_top) + 1),
            "Tổng dư nợ": df_top["Tổng_dư_nợ"],
            "Tỷ trọng trong tiêu chí %": (
                df_top["Tổng_dư_nợ"] / tong_tieu_chi * 100 if tong_tieu_chi > 0 else 0.0
            ),
            "Số KH": df_top["Số_KH"].astype(int),
            "Số món": df_top["Số_món"].astype(int),
            "BQ/KH": df_top["BQ_dư_nợ_KH"],
        })
        rows.append(out)

    if not rows:
        return pd.DataFrame()

    result = pd.concat(rows, ignore_index=True)
    result["Tỷ trọng trong tiêu chí %"] = result["Tỷ trọng trong tiêu chí %"].round(2)
    return result


def _fmt_so_sanh_du_no_hien_thi(df_so_sanh: pd.DataFrame) -> pd.DataFrame:
    df_show = df_so_sanh.copy()
    for col in ("Tổng dư nợ", "BQ/KH"):
        df_show[col] = (pd.to_numeric(df_show[col], errors="coerce") / 1_000_000).round(0)
    return df_show


def _xuat_pdf_so_sanh_du_no(
    df_so_sanh: pd.DataFrame,
    tieu_de: str,
    username: str,
) -> bytes:
    df_xuat = _fmt_so_sanh_du_no_hien_thi(df_so_sanh)
    return xuat_pdf(
        df_xuat,
        f"{tieu_de} (triệu đồng)",
        username,
        cols_tien=["Tổng dư nợ", "BQ/KH"],
        don_vi_tien="triệu đồng",
        prefix_file="BC_SS_DU_NO",
        them_dong_tong=False,
        cols_right=["Xếp hạng", "Tỷ trọng trong tiêu chí %", "Số KH", "Số món"],
        cols_percent=["Tỷ trọng trong tiêu chí %"],
        cols_dem=["Xếp hạng", "Số KH", "Số món"],
    )


def _render_so_sanh_du_no(
    ctx: DeltaGenerator,
    df_filtered: pd.DataFrame,
    username: str,
    key: str,
) -> None:
    ctx.markdown("### ⚖️ So sánh dư nợ theo tiêu chí")
    ds_tieu_chi = _danh_sach_tieu_chi_so_sanh(df_filtered)
    labels = [label for label, _ in ds_tieu_chi]
    default_labels = labels[:5]

    col1, col2 = ctx.columns([3, 1])
    with col1:
        tieu_chi_chon = st.multiselect(
            "Tiêu chí",
            labels,
            default=default_labels,
            key=f"{key}_tieu_chi",
        )
    with col2:
        top_n = st.number_input(
            "Top nhóm",
            min_value=3,
            max_value=100,
            value=10,
            step=1,
            key=f"{key}_top_n",
        )

    df_so_sanh = _tao_so_sanh_du_no_theo_tieu_chi(
        df_filtered,
        tieu_chi_chon=tieu_chi_chon,
        top_n=int(top_n),
    )
    if df_so_sanh.empty:
        ctx.warning("⚠️ Không có dữ liệu phù hợp để so sánh.")
        return

    tong_du_no = pd.to_numeric(df_filtered[COT_TONG_DU_NO], errors="coerce").fillna(0).sum()
    col_a, col_b, col_c = ctx.columns(3)
    col_a.metric("Tổng dư nợ phạm vi", f"{tong_du_no/1e9:.1f} tỷ".replace(".", ","))
    col_b.metric("Tiêu chí", fmt_so(df_so_sanh["Tiêu chí"].nunique()))
    col_c.metric("Nhóm hiển thị", fmt_so(len(df_so_sanh)))

    render_quick_export_buttons(
        df_so_sanh,
        "SoSanhDuNo",
        "So sánh dư nợ theo tiêu chí",
        username,
        "BC_SS_DU_NO",
        key=key,
        container=ctx,
        pdf_func=lambda d, t, u: _xuat_pdf_so_sanh_du_no(d, t, u),
    )

    df_show = _fmt_so_sanh_du_no_hien_thi(df_so_sanh)
    render_sticky_table(df_show, key=f"{key}_bang", height=560, container=ctx)


def _xuat_pdf_tong_hop(
    df_th: pd.DataFrame,
    tong_cong: dict,
    group_col: str,
    ten_nhom: str,
    co_khoanh: bool,
    tieu_de: str,
    username: str,
    prefix_file: str,
    nam_bl: int | None = None,
) -> bytes:
    """Xuất PDF bảng tổng hợp; dòng TỔNG CỘNG dùng nunique toàn cục (không cộng theo nhóm)."""
    bq_tong = tong_cong["bq_kh"]
    co_moc = nam_bl is not None and "DN_moc_3112" in df_th.columns
    cot_moc = f"31/12/{nam_bl}" if nam_bl is not None else None
    cot_tang = "± 31/12"

    df_xuat = pd.DataFrame({
        ten_nhom: df_th[group_col].astype(str),
        "Số KH": df_th["Số_KH"].astype(int),
        "Số món": df_th["Số_món"].astype(int),
        "Món QH": df_th["Số_món_QH"].astype(int),
        "Tổng dư nợ": (df_th["Tổng_dư_nợ"] / 1_000_000).round(0),
    })
    if co_moc:
        df_xuat[cot_moc] = (df_th["DN_moc_3112"] / 1_000_000).round(0)
        df_xuat[cot_tang] = (
            (df_th["Tổng_dư_nợ"] - df_th["DN_moc_3112"]) / 1_000_000
        ).round(0)
    df_xuat["Trong hạn"] = (df_th["Dư_nợ_trong_hạn"] / 1_000_000).round(0)
    df_xuat["Quá hạn"] = (df_th["Dư_nợ_quá_hạn"] / 1_000_000).round(0)
    if co_khoanh:
        df_xuat["Khoanh"] = (df_th["Dư_nợ_khoanh"] / 1_000_000).round(0)
    df_xuat["Tỷ trọng %"] = df_th["Tỷ_trọng_%"].round(2)
    df_xuat["Tỷ lệ QH %"] = df_th["Tỷ_lệ_QH_%"].round(2)
    df_xuat["BQ/KH"] = (df_th["BQ_dư_nợ_KH"] / 1_000_000).round(0)

    tong_dn_moc = float(df_th["DN_moc_3112"].sum()) if co_moc else 0.0
    dong_tong = {
        ten_nhom: "TỔNG CỘNG",
        "Số KH": int(tong_cong["tong_kh"]),
        "Số món": int(tong_cong["tong_mon"]),
        "Món QH": int(tong_cong["tong_mon_qh"]),
        "Tổng dư nợ": round(float(tong_cong["tong_dn"]) / 1_000_000),
    }
    if co_moc:
        dong_tong[cot_moc] = round(tong_dn_moc / 1_000_000)
        dong_tong[cot_tang] = round((float(tong_cong["tong_dn"]) - tong_dn_moc) / 1_000_000)
    dong_tong["Trong hạn"] = round(float(tong_cong["tong_th"]) / 1_000_000)
    dong_tong["Quá hạn"] = round(float(tong_cong["tong_qh"]) / 1_000_000)
    dong_tong["Tỷ trọng %"] = float(tong_cong["ty_trong"])
    dong_tong["Tỷ lệ QH %"] = round(float(tong_cong["ty_le_qh"]), 2)
    dong_tong["BQ/KH"] = "" if pd.isna(bq_tong) else round(float(bq_tong) / 1_000_000)
    if co_khoanh:
        dong_tong["Khoanh"] = round(float(tong_cong["tong_khoanh"]) / 1_000_000)

    tien_cols = [
        c for c in ["Tổng dư nợ", cot_moc, cot_tang, "Trong hạn", "Quá hạn", "Khoanh", "BQ/KH"]
        if c and c in df_xuat.columns
    ]
    dem_cols = ["Số KH", "Số món", "Món QH"]
    phan_tram_cols = ["Tỷ trọng %", "Tỷ lệ QH %"]
    # Tiêu đề PDF: bỏ emoji/ký tự đặc biệt ở MỌI vị trí (font TNR không có glyph emoji)
    nhan = re.sub(r"\W+", " ", str(tieu_de), flags=re.UNICODE).strip()
    nhan = re.sub(
        r"^Báo cáo tổng hợp\s+", "", nhan, flags=re.IGNORECASE
    ).strip() or str(tieu_de)
    return xuat_pdf(
        df_xuat,
        f"BÁO CÁO TỔNG HỢP HSTD — {nhan} (triệu đồng)",
        username,
        cols_tien=tien_cols,
        don_vi_tien="triệu đồng",
        prefix_file=prefix_file,
        them_dong_tong=True,
        cols_right=dem_cols + phan_tram_cols,
        dong_tong=dong_tong,
        cols_percent=phan_tram_cols,
        cols_dem=dem_cols,
    )


# Các loại tổng hợp HSTD — thứ tự dict = thứ tự hiển thị khi render nhiều mục
_REPORT_OPTIONS: dict[str, tuple[str, str]] = {
    "pgd": ("🏢 Theo PGD", COT_TEN_PGD),
    "xa": ("🏘️ Theo Xã", COT_TEN_XA),
    "thon": ("🏡 Theo Thôn/ấp", COT_TEN_THON),
    "ct": ("📌 Theo Chương trình", COT_TEN_CT),
    "md": ("🎯 Theo Mục đích sử dụng vốn", COT_TEN_PNKT51),
    "nv": ("🏦 Theo Nguồn vốn", COT_NGUON_VON),
    "dvut": ("🤝 Theo ĐVUT", COT_DVUT),
    "cbtd": ("👤 Theo CBTD/Tổ", COT_TEN_TO),
    "sosanh": ("⚖️ So sánh dư nợ", COT_TEN_PGD),
}


def _chuan_hoa_trang_thai_chon_nhieu() -> None:
    """Đảm bảo session state của multiselect là list key hợp lệ.

    Phiên cũ dùng radio lưu chuỗi đơn (vd "pgd"); nếu còn trong session_state
    thì chuyển sang list để multiselect không crash vì sai kiểu dữ liệu.
    """
    gia_tri = st.session_state.get("th_loai_hstd_v2")
    if gia_tri is None:
        return
    if isinstance(gia_tri, str):
        gia_tri = [gia_tri]
    if not isinstance(gia_tri, (list, tuple)):
        st.session_state.pop("th_loai_hstd_v2", None)
        return
    hop_le = [k for k in gia_tri if k in _REPORT_OPTIONS]
    st.session_state["th_loai_hstd_v2"] = hop_le or ["pgd"]


def _render_mot_loai_tong_hop(
    ctx: DeltaGenerator,
    df: pd.DataFrame,
    selected_report: str,
    role: str,
    pgd_user: str,
    username: str,
    kem_formula: bool = False,
) -> None:
    """Render trọn vẹn MỘT loại tổng hợp HSTD: bộ lọc, cảnh báo, bảng, nút xuất.

    Mỗi loại dùng bộ widget key riêng (th_{selected_report}_*) nên có thể
    render nhiều loại liên tiếp trong cùng một lần chạy mà không trùng key.
    """
    report_label, group_col = _REPORT_OPTIONS[selected_report]

    df_filtered = df.copy()

    # ── Bảng điều khiển lọc: khối phẳng có viền, gom mọi bộ lọc một chỗ ─────
    with ctx.container(border=True):
        # Kiểm tra cột tồn tại
        if group_col not in df_filtered.columns:
            ctx.error(f"❌ Không có cột {group_col} trong dữ liệu.")
            return

        # Bộ lọc PGD (rộng toàn phần)
        if la_phan_he_pgd(role) and pgd_user:
            if COT_TEN_PGD in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[COT_TEN_PGD] == pgd_user]
                ctx.info(f"📍 Đang xem báo cáo của PGD: **{pgd_user}**")
        elif COT_TEN_PGD in df_filtered.columns and group_col != COT_TEN_PGD:
            df_filtered = render_inline_filter(
                df_filtered,
                [COT_TEN_PGD],
                key=f"th_{selected_report}_pgd",
                container=ctx,
            )

        # Nguồn vốn + Khu vực đặt song song; tham khảo công thức bên phải
        if kem_formula:
            col_nv, col_kv, col_ref = ctx.columns([1.3, 1.3, 1])
            df_filtered = render_nguon_von_filter(
                df_filtered, key=f"th_{selected_report}", container=col_nv
            )
            df_filtered = render_khu_vuc_filter(
                df_filtered, key=f"th_{selected_report}", container=col_kv
            )
            render_formula_reference(col_ref)
        else:
            col_nv, col_kv = ctx.columns(2)
            df_filtered = render_nguon_von_filter(
                df_filtered, key=f"th_{selected_report}", container=col_nv
            )
            df_filtered = render_khu_vuc_filter(
                df_filtered, key=f"th_{selected_report}", container=col_kv
            )

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
    search_cols = [
        c for c in [COT_TEN_PGD, COT_TEN_XA, COT_TEN_PNKT51, COT_MA_KH]
        if c in df_filtered.columns
    ]
    
    df_filtered = render_combined_filter_search(
        df_filtered,
        filter_cols[:2],  # Tối đa 2 filter
        search_cols,
        key=f"th_{selected_report}",
        container=ctx,
    )

    if selected_report == "sosanh":
        _render_so_sanh_du_no(ctx, df_filtered, username, key="th_sosanh")
        return

    # ── Baseline 31/12 năm trước — thu hẹp đúng phạm vi các bộ lọc ──────────
    df_bl_3112: pd.DataFrame | None = None
    nam_bl: int | None = None
    hien_loc_pgd = (
        not (la_phan_he_pgd(role) and pgd_user)
        and COT_TEN_PGD in df_filtered.columns
        and group_col != COT_TEN_PGD
    )
    df_bl_3112, nam_bl = _doc_baseline_cung_pham_vi(
        selected_report, group_col, role, pgd_user, hien_loc_pgd, filter_cols,
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

        if selected_report == "md":
            canh_bao_md = _thong_diep_muc_dich_chua_xac_dinh(
                df_th, group_col, df_group
            )
            if canh_bao_md:
                ctx.warning(canh_bao_md)

        # Ghép dư nợ mốc 31/12 năm trước theo nhóm (cùng phạm vi bộ lọc)
        co_moc = False
        cot_moc = cot_tang = None
        tong_dn_moc = 0.0
        if df_bl_3112 is not None and nam_bl is not None and group_col in df_bl_3112.columns:
            df_bl_num = df_bl_3112.copy()
            df_bl_num[COT_TONG_DU_NO] = pd.to_numeric(
                df_bl_num[COT_TONG_DU_NO], errors="coerce"
            ).fillna(0)
            if selected_report == "nv":
                df_bl_num = chuan_hoa_nhom_nguon_von(df_bl_num)
            nhom_bl = df_bl_num[group_col].astype("string").str.strip()
            df_bl_num[group_col] = nhom_bl.mask(
                nhom_bl.isna() | nhom_bl.eq(""), _NHOM_KHONG_XAC_DINH
            )
            bl_dn = df_bl_num.groupby(group_col, dropna=False)[COT_TONG_DU_NO].sum()
            df_th["DN_moc_3112"] = df_th[group_col].map(bl_dn).fillna(0.0)
            df_th["DN_tang_3112"] = df_th["Tổng_dư_nợ"] - df_th["DN_moc_3112"]
            tong_dn_moc = float(df_th["DN_moc_3112"].sum())
            co_moc = True
            cot_moc = f"31/12/{nam_bl}"
            cot_tang = "± 31/12"
        elif df_bl_3112 is not None and nam_bl is not None:
            ctx.caption(
                f"ℹ️ Baseline 31/12/{nam_bl} không có cột \"{group_col}\" — "
                "bỏ qua cột so sánh mốc năm cho loại tổng hợp này."
            )

        # Metrics
        if co_moc:
            col1, col2, col3, col4, col5 = ctx.columns(5)
        else:
            col1, col2, col3, col4 = ctx.columns(4)
        col1.metric("Số nhóm", fmt_so(len(df_th)))
        col2.metric("Tổng dư nợ", f"{tong_cong['tong_dn']/1e9:.1f} tỷ".replace(".", ","))
        col3.metric("Tổng KH", fmt_so(tong_cong["tong_kh"]))
        
        ty_le_qh_tb = float(tong_cong["ty_le_qh"])
        col4.metric("Tỷ lệ QH TB", f"{ty_le_qh_tb:.2f}%".replace(".", ","))

        if co_moc:
            delta_moc = float(tong_cong["tong_dn"]) - tong_dn_moc
            pct_moc = delta_moc / tong_dn_moc * 100 if tong_dn_moc else 0.0
            col5.metric(
                f"So mốc 31/12/{nam_bl}",
                f"{delta_moc/1e9:+.1f} tỷ".replace(".", ","),
                f"{pct_moc:+.2f}%".replace(".", ","),
            )
        
        ctx.divider()

        ten_nhom = (
            report_label.split("Theo ")[-1].strip()
            if "Theo " in report_label else report_label
        )

        # Dựng bảng hiển thị + dòng tổng (triệu đồng) dùng chung cho HTML, Excel, PDF
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

        if co_moc:
            df_hien[cot_moc] = df_th["DN_moc_3112"] / 1_000_000
            df_hien[cot_tang] = df_th["DN_tang_3112"] / 1_000_000
            # Đặt hai cột mốc ngay sau cột "Tổng dư nợ"
            thu_tu = [c for c in df_hien.columns if c not in (cot_moc, cot_tang)]
            vi_tri = thu_tu.index("Tổng dư nợ") + 1
            thu_tu[vi_tri:vi_tri] = [cot_moc, cot_tang]
            df_hien = df_hien[thu_tu]

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
        if co_moc:
            dong_tong[cot_moc] = tong_dn_moc / 1_000_000
            dong_tong[cot_tang] = (float(tong_cong["tong_dn"]) - tong_dn_moc) / 1_000_000

        cot_tien_list = [
            c for c in (
                "Tổng dư nợ", cot_moc, cot_tang,
                "Trong hạn", "Quá hạn", "Khoanh", "BQ/KH",
            )
            if c and c in df_hien.columns
        ]
        df_xuat_excel = _df_xuat_excel_tong_hop(df_hien, dong_tong, cot_tien_list)

        # Quick export
        render_quick_export_buttons(
            df_th,
            f"TongHop_{selected_report}",
            f"Báo cáo tổng hợp {report_label}",
            username,
            f"BC_TH_{selected_report.upper()}",
            key=f"th_{selected_report}",
            container=ctx,
            pdf_func=lambda d, t, u: _xuat_pdf_tong_hop(
                d, tong_cong, group_col, ten_nhom, co_khoanh, t, u,
                f"BC_TH_{selected_report.upper()}", nam_bl=nam_bl if co_moc else None,
            ),
            df_excel=df_xuat_excel,
        )

        # Bảng chi tiết — HTML theo bảng màu chuẩn UI_GUIDELINES
        render_header_with_tooltip(
            "📊 Chi tiết",
            tooltip_key="Tổng dư nợ",
            container=ctx,
        )

        render_bang_chi_tiet_html(
            df_hien,
            key=f"th_chi_tiet_{selected_report}",
            cot_ten=ten_nhom,
            cot_dem=["Số KH", "Số món", "Món QH"],
            cot_tien=cot_tien_list,
            cot_bar="Tỷ trọng %",
            cot_badge="Tỷ lệ QH %",
            nhom_header=[
                ("", 1),
                ("QUY MÔ", 3),
                ("DƯ NỢ", (4 if co_khoanh else 3) + (2 if co_moc else 0)),
                ("CƠ CẤU & CHẤT LƯỢNG", 3),
            ],
            dong_tong=dong_tong,
            height=520,
            container=ctx,
        )
        
    except Exception as e:
        logger.error("tong_hop_hstd_v2: lỗi tạo báo cáo — %s", e, exc_info=True)
        ctx.error(f"❌ Lỗi tạo báo cáo: {e}")


def _df_xuat_excel_tong_hop(
    df_hien: pd.DataFrame,
    dong_tong: dict,
    cot_tien: list[str],
) -> pd.DataFrame:
    """Dựng bảng Excel đồng nhất với bảng hiển thị: triệu đồng, cột sạch, kèm dòng TỔNG CỘNG."""
    df = df_hien.copy()
    for cot in cot_tien:
        if cot in df.columns:
            df[cot] = pd.to_numeric(df[cot], errors="coerce").round(0)
    dong = {c: dong_tong.get(c) for c in df.columns}
    for cot in cot_tien:
        if cot in dong and pd.notna(dong.get(cot)):
            dong[cot] = round(float(dong[cot]))
    df.loc[len(df)] = dong
    return df


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

    Cho phép tick chọn NHIỀU loại tổng hợp cùng lúc (multiselect); mỗi loại
    được chọn render thành một khối bảng xếp chồng liên tiếp từ trên xuống.

    Args:
        tab: Streamlit container
        df: DataFrame HSTD
        role: Role người dùng
        pgd_user: Tên PGD
        username: Username
        specific_report: Key của báo cáo cụ thể (pgd, xa, thon, ct, nv, dvut,
            cbtd, sosanh) — nếu truyền vào chỉ render báo cáo đó, ẩn multiselect
    """
    ctx = tab if tab is not None else st

    if df is None or df.empty:
        ctx.warning("⚠️ Chưa có dữ liệu HSTD.")
        return

    # Deep-link từ nơi khác: render duy nhất loại được chỉ định
    if specific_report is not None and specific_report in _REPORT_OPTIONS:
        _render_mot_loai_tong_hop(ctx, df, specific_report, role, pgd_user, username)
        return

    _chuan_hoa_trang_thai_chon_nhieu()
    ds_chon = ctx.multiselect(
        "🧭 Tổng hợp theo — tick chọn nhiều mục để xem cùng lúc",
        list(_REPORT_OPTIONS.keys()),
        default=["pgd"],
        format_func=lambda k: _REPORT_OPTIONS[k][0],
        key="th_loai_hstd_v2",
    )
    if not ds_chon:
        ctx.info("👆 Vui lòng tick chọn ít nhất một loại tổng hợp để hiển thị báo cáo.")
        return

    # Giữ thứ tự chuẩn của _REPORT_OPTIONS bất kể thứ tự tick của user
    ds_chon = [k for k in _REPORT_OPTIONS if k in ds_chon]
    for vi_tri, selected_report in enumerate(ds_chon):
        if vi_tri > 0:
            ctx.divider()
        _render_mot_loai_tong_hop(
            ctx, df, selected_report, role, pgd_user, username,
            kem_formula=(vi_tri == 0),
        )
