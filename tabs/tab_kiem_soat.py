"""
Tab Kiểm soát Chi nhánh — chọn nhóm/báo cáo từ registry, gọi render_fn tương ứng.
Mở rộng báo cáo: chỉ sửa services/kiem_soat_service.py (registry + hàm render).
"""
import duckdb
import pandas as pd
import streamlit as st
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role

from config import (
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_MA_CHUONG_TRINH,
    COT_MA_KH,
    COT_MA_NHA_DAU_TU,
    COT_NGAY_SL,
    COT_NGUON_VON,
    COT_TONG_DU_NO,
    COT_SO_KU,
    COT_TEN_KH,
    COT_TEN_CT,
    COT_NGAY_DH,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TINH_TRANG,
)
from data import danh_dau_khong_hd, tong_hop_khong_hd, ds_chi_tiet_khong_hd
from services.kiem_soat_service import BAO_CAO_REGISTRY, NHOM_BAO_CAO, chon_pgd_filter
from utils import fmt_ngay, fmt_so, fmt_ty, get_tab_context, xuat_excel

_COL_PL_NV = "PL NV"


def _norm_series_str(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.strip()
    out = out.str.replace(r"\.0+$", "", regex=True)
    return out


def _render_ra_soat_gqvl_tw_gan_mandt(
    df_full: pd.DataFrame,
    role: str,
    pgd_user: str | None = None,
    df_gqvl: pd.DataFrame | None = None,
) -> None:
    if df_full is None or df_full.empty:
        st.warning("Chưa có dữ liệu HSTD.")
        return

    df_src = df_gqvl if (df_gqvl is not None and not df_gqvl.empty) else df_full

    required_cols = [
        COT_MA_CHUONG_TRINH,
        COT_NGUON_VON,
        COT_MA_NHA_DAU_TU,
        COT_TINH_TRANG,
    ]
    missing_required = [c for c in required_cols if c not in df_src.columns]
    if missing_required:
        st.warning("Thiếu cột trong dữ liệu: " + ", ".join(missing_required))
        return

    if _COL_PL_NV not in df_src.columns:
        st.warning("Dữ liệu chưa có cột PL NV")
        return

    s_ma_ct = _norm_series_str(df_src[COT_MA_CHUONG_TRINH]).str.lstrip("0")
    s_nv = _norm_series_str(df_src[COT_NGUON_VON])
    s_pl = _norm_series_str(df_src[_COL_PL_NV]).str.zfill(2)
    s_tt = _norm_series_str(df_src[COT_TINH_TRANG])
    s_mandt = df_src[COT_MA_NHA_DAU_TU]

    mask = (
        (s_ma_ct == "3")
        & (s_nv == "1")
        & (s_pl == "02")
        & (s_mandt.notna() & (s_mandt.astype(str).str.strip() != ""))
        & (s_tt == "OPEN")
    )
    df_kq = df_src.loc[mask].copy()

    role_norm = normalize_role(role)
    if la_phan_he_pgd(role_norm):
        if not pgd_user:
            user_info = st.session_state.get("user_info") or {}
            pgd_user = user_info.get("pgd")
        if pgd_user and COT_TEN_PGD in df_kq.columns:
            df_kq = df_kq[df_kq[COT_TEN_PGD] == pgd_user].copy()

    if df_kq.empty:
        st.info("Không có món vay GQVL TW gắn MANDT")
        return

    du_no_tong = pd.to_numeric(df_kq.get(COT_TONG_DU_NO), errors="coerce").fillna(0).sum()
    n_kh = df_kq[COT_MA_KH].nunique() if COT_MA_KH in df_kq.columns else 0
    n_pgd = df_kq[COT_TEN_PGD].nunique() if COT_TEN_PGD in df_kq.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số món", fmt_so(len(df_kq)))
    c2.metric("Tổng dư nợ", fmt_ty(du_no_tong))
    c3.metric("Số khách hàng", fmt_so(n_kh))
    c4.metric("Số PGD có phát sinh", fmt_so(n_pgd))

    cols_show = [
        COT_TEN_PGD, COT_TEN_XA, COT_MA_KH, COT_TEN_KH,
        COT_SO_KU, COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO,
        COT_MA_NHA_DAU_TU, _COL_PL_NV,
    ]
    missing = [c for c in cols_show if c not in df_kq.columns]
    if missing:
        st.warning("Thiếu cột trong dữ liệu: " + ", ".join(missing))
    cols_present = [c for c in cols_show if c in df_kq.columns]

    df_view = df_kq[cols_present].copy()

    sort_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_MA_KH] if c in df_view.columns]
    if sort_cols:
        df_view = df_view.sort_values(sort_cols, kind="mergesort")

    for c in [COT_DU_NO_TH, COT_DU_NO_QH, COT_TONG_DU_NO]:
        if c in df_view.columns:
            df_view[c] = pd.to_numeric(df_view[c], errors="coerce").fillna(0).apply(fmt_ty)

    st.dataframe(df_view, use_container_width=True, height=420)

    ngay_sl = ""
    if COT_NGAY_SL in df_src.columns:
        s = df_src[COT_NGAY_SL].dropna()
        if len(s):
            ngay_sl = fmt_ngay(s.iloc[0])
    ngay_sl = (ngay_sl or "").replace("/", "")
    if not ngay_sl:
        ngay_sl = pd.Timestamp.now().strftime("%Y%m%d")

    excel_bytes = xuat_excel({"GQVL_TW_MANDT": df_kq[cols_present]})
    st.download_button(
        "⬇️ Xuất Excel",
        data=excel_bytes,
        file_name=f"GQVL_TW_MANDT_{ngay_sl}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ks_gqvl_tw_mandt_xlsx",
    )


def _get_ks_cache(df: pd.DataFrame) -> dict:
    cache_key = (len(df), tuple(df.columns.tolist()))
    ks = st.session_state.get("ks_cache", {})
    if ks.get("_key") == cache_key:
        return ks

    with st.spinner("Đang phân tích dữ liệu..."):
        df_kh = danh_dau_khong_hd(df)

        df_khd_pgd = tong_hop_khong_hd(df_kh, nhom_theo=COT_TEN_PGD)
        df_khd_chi = ds_chi_tiet_khong_hd(df_kh)

        if COT_DU_NO_QH in df_kh.columns and COT_TEN_PGD in df_kh.columns:
            _ku_col = COT_SO_KU if COT_SO_KU in df_kh.columns else COT_TEN_KH
            df_nqh_pgd = duckdb.query(f"""
                SELECT
                    "{COT_TEN_PGD}",
                    COUNT(DISTINCT "{_ku_col}")                          AS "Số_hồ_sơ_NQH",
                    SUM(TRY_CAST("{COT_DU_NO_QH}"  AS DOUBLE))          AS "Tổng_dư_nợ_QH",
                    SUM(TRY_CAST("{COT_TONG_DU_NO}" AS DOUBLE))         AS "Tổng_dư_nợ"
                FROM df_kh
                WHERE TRY_CAST("{COT_DU_NO_QH}" AS DOUBLE) > 0
                GROUP BY "{COT_TEN_PGD}"
            """).df()
            if not df_nqh_pgd.empty:
                tdn = df_nqh_pgd["Tổng_dư_nợ"].replace(0, pd.NA)
                df_nqh_pgd["Tỷ_lệ_QH_%"] = (
                    df_nqh_pgd["Tổng_dư_nợ_QH"] / tdn * 100
                ).round(1).fillna(0)

            _chi_cols = ", ".join(
                f'"{c}"' for c in [
                    COT_TEN_PGD, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
                    COT_DU_NO_QH, COT_TONG_DU_NO, COT_NGAY_DH,
                ] if c in df_kh.columns
            )
            df_nqh_chi = duckdb.query(f"""
                SELECT {_chi_cols}
                FROM df_kh
                WHERE TRY_CAST("{COT_DU_NO_QH}" AS DOUBLE) > 0
            """).df()
        else:
            df_nqh_pgd = pd.DataFrame()
            df_nqh_chi = pd.DataFrame()

    result = {
        "_key": cache_key,
        "df_kh": df_kh,
        "df_khd_pgd": df_khd_pgd,
        "df_khd_chi": df_khd_chi,
        "df_nqh_pgd": df_nqh_pgd,
        "df_nqh_chi": df_nqh_chi,
    }
    st.session_state["ks_cache"] = result
    return result


def render_tab(df, role: str, username: str, **kwargs) -> None:
    if df is None or df.empty:
        st.warning("Chưa có dữ liệu HSTD toàn CN.")
        return

    cache = _get_ks_cache(df)

    readonly = normalize_role(role) == "executive"
    nhom_keys = list(NHOM_BAO_CAO.keys())

    tab_main_ks, tab_main_gsnb = st.tabs(["🧩 Kiểm soát", "📋 Báo cáo giám sát nội bộ"])

    with get_tab_context(tab_main_ks):
        col_a, col_b, col_c = st.columns([1, 1, 2])
        with col_a:
            st.selectbox(
                "Nhóm báo cáo",
                options=nhom_keys,
                format_func=lambda k: NHOM_BAO_CAO[k],
                key="ks_nhom",
            )
        nhom = st.session_state["ks_nhom"]

        ds_ma = [ma for ma, meta in BAO_CAO_REGISTRY.items() if meta.nhom == nhom]
        if not ds_ma:
            st.info("Nhóm này chưa có báo cáo.")
            return

        if st.session_state.get("ks_bao_cao") not in ds_ma:
            st.session_state["ks_bao_cao"] = ds_ma[0]

        with col_b:
            st.selectbox(
                "Báo cáo",
                options=ds_ma,
                format_func=lambda k: BAO_CAO_REGISTRY[k].ten,
                key="ks_bao_cao",
            )
        with col_c:
            pgd_chon = chon_pgd_filter(df, "main")

        meta = BAO_CAO_REGISTRY[st.session_state["ks_bao_cao"]]
        st.caption(meta.mo_ta)
        meta.render_fn(cache, pgd_chon, username, readonly)

    with get_tab_context(tab_main_gsnb):
        sub_gqvl, = st.tabs(["🧾 Rà soát GQVL TW – Gắn MANDT"])
        with sub_gqvl:
            _render_ra_soat_gqvl_tw_gan_mandt(
                df_full=df,
                role=role,
                pgd_user=kwargs.get("pgd_user"),
                df_gqvl=kwargs.get("df_gqvl"),
            )
