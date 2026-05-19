"""
Tab Kiểm soát Chi nhánh — chọn nhóm/báo cáo từ registry, gọi render_fn tương ứng.
Mở rộng báo cáo: chỉ sửa services/kiem_soat_service.py (registry + hàm render).
"""
import duckdb
import pandas as pd
import streamlit as st
from auth import normalize_role

from config import (
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_TONG_DU_NO,
    COT_SO_KU,
    COT_TEN_KH,
    COT_TEN_CT,
    COT_NGAY_DH,
    COT_TEN_PGD,
)
from data import danh_dau_khong_hd, tong_hop_khong_hd, ds_chi_tiet_khong_hd
from services.kiem_soat_service import BAO_CAO_REGISTRY, NHOM_BAO_CAO, chon_pgd_filter


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
