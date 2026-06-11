"""Tab Chất lượng Dữ liệu — phân tích toàn diện HSTD/NQ11/GQVL sau merge."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime

import db
from auth import normalize_role, la_phan_he_cn
from config import (
    COT_TEN_PGD, COT_SO_KU, COT_TONG_DU_NO,
    COT_DU_NO_QH, COT_DU_NO_TH, COT_DU_NO_KHOANH,
    COT_TEN_XA, COT_TEN_CT, COT_MA_KH,
    DS_PGD, DON_VI_CHI_NHANH,
)
from tabs.base_tab import TabContext
from utils import fmt_so, fmt_ty
from logger import get_logger

logger = get_logger(__name__)

_LOAI_LABELS = {"hstd": "HSTD", "nq11": "NQ11 / GQVL"}
_COT_KEY = [COT_SO_KU, COT_MA_KH, COT_TEN_PGD, COT_TEN_XA,
            COT_TEN_CT, COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _badge(ok: bool) -> str:
    return "✅" if ok else "❌"


def _doc_meta(loai: str) -> dict | None:
    return db.doc_kv(f"merge_meta_{loai}")


def _doc_quality_meta(loai: str) -> dict | None:
    return db.doc_kv(f"data_quality_meta_{loai}")


def _fmt_ts(ts_str: str | None) -> str:
    if not ts_str:
        return "—"
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(ts_str)


# ── Phân tích df trực tiếp ─────────────────────────────────────────────────────

def _phan_tich_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Tỷ lệ null của từng cột quan trọng."""
    rows = []
    for cot in _COT_KEY:
        if cot not in df.columns:
            rows.append({"Cột": cot, "Tổng dòng": len(df), "Null": len(df), "Tỷ lệ null (%)": 100.0, "Trạng thái": "❌ Thiếu cột"})
            continue
        null_count = int(df[cot].isna().sum() + (df[cot].astype(str).str.strip() == "").sum())
        pct = round(null_count / max(len(df), 1) * 100, 2)
        status = "✅ Tốt" if pct < 1 else ("⚠️ Chú ý" if pct < 5 else "❌ Xấu")
        rows.append({"Cột": cot, "Tổng dòng": len(df), "Null": null_count, "Tỷ lệ null (%)": pct, "Trạng thái": status})
    return pd.DataFrame(rows)


def _phan_tich_trung_lap(df: pd.DataFrame) -> dict:
    """Phát hiện trùng lặp theo Số khế ước."""
    result = {"dup_sku": 0, "dup_makh": 0}
    if COT_SO_KU in df.columns:
        result["dup_sku"] = int(df[COT_SO_KU].astype(str).str.strip().duplicated(keep=False).sum())
    if COT_MA_KH in df.columns:
        result["dup_makh_pgd"] = (
            df.groupby([COT_TEN_PGD, COT_MA_KH]).size().gt(1).sum()
            if COT_TEN_PGD in df.columns else 0
        )
    return result


def _phan_tich_du_no_am(df: pd.DataFrame) -> dict:
    result = {}
    for cot in [COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO]:
        if cot in df.columns:
            s = pd.to_numeric(df[cot], errors="coerce")
            result[cot] = int((s < 0).sum())
    return result


def _phan_tich_theo_pgd(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp chất lượng theo PGD."""
    if df.empty or COT_TEN_PGD not in df.columns:
        return pd.DataFrame()
    all_pgd = [DON_VI_CHI_NHANH] + DS_PGD
    rows = []
    for pgd in all_pgd:
        sub = df[df[COT_TEN_PGD] == pgd]
        if sub.empty:
            rows.append({"PGD": pgd, "Số dòng": 0, "Tổng dư nợ (triệu)": "—",
                         "Có NQH": "—", "Trạng thái": "❌ Không có dữ liệu"})
            continue
        so_dong = len(sub)
        tong_dn = sub[COT_TONG_DU_NO].pipe(pd.to_numeric, errors="coerce").sum() if COT_TONG_DU_NO in sub.columns else 0
        co_nqh = "Có" if (pd.to_numeric(sub[COT_DU_NO_QH], errors="coerce").sum() > 0 if COT_DU_NO_QH in sub.columns else False) else "Không"
        rows.append({
            "PGD": pgd,
            "Số dòng": so_dong,
            "Tổng dư nợ (triệu)": fmt_ty(tong_dn),
            "Có NQH": co_nqh,
            "Trạng thái": "✅ OK",
        })
    return pd.DataFrame(rows)


# ── Sub-sections ───────────────────────────────────────────────────────────────

def _render_tong_quan_merge() -> None:
    """Card tổng quan trạng thái merge 3 loại."""
    st.subheader("📦 Trạng thái Merge")
    cols = st.columns(3)
    for i, loai in enumerate(["hstd", "nq11", "gqvl"]):
        meta = _doc_meta(loai)
        with cols[i]:
            if meta:
                so_pgd = meta.get("so_pgd", 0)
                so_dong = meta.get("so_dong", 0)
                ts = _fmt_ts(meta.get("thoi_gian"))
                pgd_cu = meta.get("pgd_cu", [])
                st.markdown(
                    f"<div style='border:1px solid #e5e7eb;border-radius:10px;padding:14px'>"
                    f"<b style='font-size:1.1rem'>{loai.upper()}</b><br>"
                    f"✅ {fmt_so(so_dong)} dòng · {so_pgd} PGD<br>"
                    f"<span style='font-size:0.8rem;color:var(--text-sub,#6b7280)'>🕐 {ts}</span>"
                    + (f"<br><span style='color:#f59e0b;font-size:0.8rem'>⚠️ {len(pgd_cu)} PGD dữ liệu cũ</span>" if pgd_cu else "")
                    + "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='border:1px solid #fecaca;border-radius:10px;padding:14px'>"
                    f"<b style='font-size:1.1rem'>{loai.upper()}</b><br>"
                    f"❌ Chưa có dữ liệu merge</div>",
                    unsafe_allow_html=True,
                )


def _render_quality_report() -> None:
    """Báo cáo chất lượng từ kv_store (ghi lúc merge)."""
    st.subheader("📊 Báo cáo Chất lượng từ Merge")
    meta = _doc_quality_meta("hstd")
    if not meta:
        st.info("ℹ️ Chưa có báo cáo chất lượng. Thực hiện merge HSTD để tạo báo cáo.")
        return

    ts = _fmt_ts(meta.get("thoi_gian"))
    tong_loi = meta.get("tong_so_loi", 0)
    bao_cao = meta.get("bao_cao", [])

    col1, col2, col3 = st.columns(3)
    col1.metric("🕐 Thời điểm kiểm tra", ts)
    col2.metric("🔢 Tổng dòng", fmt_so(meta.get("tong_dong", 0)))
    col3.metric("⚠️ Tổng lỗi phát hiện", str(tong_loi),
                delta="OK" if tong_loi == 0 else f"{tong_loi} lỗi",
                delta_color="normal" if tong_loi == 0 else "inverse")

    if bao_cao:
        df_bc = pd.DataFrame(bao_cao)
        cols_show = [c for c in ["don_vi", "loai", "tong_dong", "so_loi",
                                  "duplicate_rows", "null_required_cells",
                                  "invalid_domain_rows", "ti_le_dat_chuan"] if c in df_bc.columns]
        labels = {
            "don_vi": "Đơn vị", "loai": "Loại", "tong_dong": "Dòng",
            "so_loi": "Lỗi", "duplicate_rows": "Trùng lặp",
            "null_required_cells": "Null bắt buộc", "invalid_domain_rows": "Ngoài domain",
            "ti_le_dat_chuan": "% Đạt chuẩn",
        }
        df_show = df_bc[cols_show].rename(columns=labels) if cols_show else df_bc
        st.dataframe(df_show, use_container_width=True, height=300)


def _render_phan_tich_truc_tiep(df: pd.DataFrame) -> None:
    """Phân tích live từ df hiện tại."""
    st.subheader("🔍 Phân tích Dữ liệu Hiện tại")
    if df is None or df.empty:
        st.warning("⚠️ Không có dữ liệu để phân tích.")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Null / Missing", "🔄 Trùng lặp", "⛔ Dư nợ âm", "📍 Theo PGD"])

    with tab1:
        df_missing = _phan_tich_missing(df)
        st.caption(f"Phân tích {fmt_so(len(df))} dòng · {len(df.columns)} cột")
        so_loi = (df_missing["Tỷ lệ null (%)"] >= 5).sum()
        if so_loi > 0:
            st.warning(f"⚠️ {so_loi} cột có tỷ lệ null ≥ 5%")
        else:
            st.success("✅ Tất cả cột quan trọng đều ổn")
        st.dataframe(df_missing, use_container_width=True, height=320)

    with tab2:
        dup = _phan_tich_trung_lap(df)
        dup_sku = dup.get("dup_sku", 0)
        dup_makh = dup.get("dup_makh_pgd", 0)
        c1, c2 = st.columns(2)
        c1.metric("Trùng Số Khế ước", fmt_so(dup_sku),
                  delta="OK" if dup_sku == 0 else f"{fmt_so(dup_sku)} dòng",
                  delta_color="normal" if dup_sku == 0 else "inverse")
        c2.metric("Trùng Mã KH trong PGD", fmt_so(dup_makh),
                  delta="OK" if dup_makh == 0 else f"{fmt_so(dup_makh)} bộ",
                  delta_color="normal" if dup_makh == 0 else "off")
        if dup_sku > 0 and COT_SO_KU in df.columns:
            with st.expander("👁️ Xem dòng trùng Số Khế ước"):
                mask_dup = df[COT_SO_KU].astype(str).str.strip().duplicated(keep=False)
                cols_show = [c for c in [COT_TEN_PGD, COT_SO_KU, COT_MA_KH, COT_TONG_DU_NO] if c in df.columns]
                st.dataframe(df.loc[mask_dup, cols_show].head(200), use_container_width=True)

    with tab3:
        am_result = _phan_tich_du_no_am(df)
        tong_am = sum(am_result.values())
        if tong_am == 0:
            st.success("✅ Không có dư nợ âm")
        else:
            st.error(f"❌ Phát hiện {fmt_so(tong_am)} dòng dư nợ âm")
        cols = st.columns(3)
        for i, (cot, so) in enumerate(am_result.items()):
            cols[i % 3].metric(cot, fmt_so(so),
                               delta="OK" if so == 0 else f"⛔ {fmt_so(so)}",
                               delta_color="normal" if so == 0 else "inverse")

    with tab4:
        df_pgd = _phan_tich_theo_pgd(df)
        if df_pgd.empty:
            st.warning("⚠️ Không có cột Tên PGD để phân tích.")
        else:
            so_thieu = (df_pgd["Số dòng"] == 0).sum()
            if so_thieu:
                st.warning(f"⚠️ {so_thieu} đơn vị không có dữ liệu")
            else:
                st.success("✅ Đủ 22 đơn vị")
            st.dataframe(df_pgd, use_container_width=True, height=500)


# ── Entry point ────────────────────────────────────────────────────────────────

def render(tab=None, **kwargs) -> None:
    """Render tab Chất lượng Dữ liệu."""
    ctx = TabContext(tab, **kwargs)
    role = ctx.role_norm
    _df_full = ctx.df_full
    df: pd.DataFrame | None = _df_full if _df_full is not None else kwargs.get("df")

    with ctx:
        st.subheader("🛡️ Chất lượng Dữ liệu")

        if not la_phan_he_cn(role):
            st.info("ℹ️ Chức năng này chỉ dành cho Phòng KH-NV / Ban Giám đốc.")
            return

        try:
            _render_tong_quan_merge()
            st.divider()
            _render_quality_report()
            st.divider()
            _render_phan_tich_truc_tiep(df)
        except Exception as e:
            logger.error("tab_data_quality.render: %s", e, exc_info=True)
            st.error(f"❌ Lỗi render tab Chất lượng Dữ liệu: {e}")
