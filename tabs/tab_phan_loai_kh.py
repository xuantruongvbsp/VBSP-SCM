"""Tab Phan loai Khach hang theo muc do rui ro (A/B/C/D)."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from config import (
    COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU, COT_TEN_CT,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, DON_VI_CHI_NHANH,
)
from services.phan_loai_service import (
    phan_loai_khach_hang, thong_ke_phan_loai, tom_tat_cn, PHAN_LOAI_LABELS,
)
from tabs.base_tab import TabContext
from utils import fmt_ty, fmt_so
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    role     = ctx.role_norm
    username = ctx.username or "unknown"
    pgd_user = ctx.pgd_user
    df_full  = ctx.df_full if ctx.df_full is not None else kwargs.get("df")

    with ctx:
        st.subheader("Phan loai Khach hang")

        if df_full is None or (hasattr(df_full, "empty") and df_full.empty):
            st.warning("Chua co du lieu.")
            return

        # ── Lọc theo PGD ─────────────────────────────────────────────────────
        df = df_full.copy()

        if la_phan_he_pgd(role) and pgd_user:
            if COT_TEN_PGD in df.columns:
                df = df[df[COT_TEN_PGD] == pgd_user]
        elif la_phan_he_cn(role):
            if COT_TEN_PGD in df.columns:
                pgd_options = ["Tat ca"] + [
                    p for p in sorted(df[COT_TEN_PGD].dropna().unique())
                    if p != DON_VI_CHI_NHANH
                ]
                sel_pgd = st.selectbox(
                    "Loc PGD", pgd_options, key="plkh_pgd_filter"
                )
                if sel_pgd != "Tat ca":
                    df = df[df[COT_TEN_PGD] == sel_pgd]

        # ── Phân loại ────────────────────────────────────────────────────────
        try:
            df_cl = phan_loai_khach_hang(df)
        except Exception as e:
            logger.error("tab_phan_loai_kh render phan_loai: %s", e, exc_info=True)
            st.error(f"Loi phan loai: {e}")
            return

        # ── KPI cards ────────────────────────────────────────────────────────
        tom_tat = tom_tat_cn(df_cl)
        c1, c2, c3, c4 = st.columns(4)
        for col_widget, key in zip([c1, c2, c3, c4], ["A", "B", "C", "D"]):
            label, _color, desc = PHAN_LOAI_LABELS[key]
            col_widget.metric(label, fmt_so(tom_tat.get(key, 0)), help=desc)

        st.divider()

        # ── 2 tabs chi tiết ──────────────────────────────────────────────────
        t1, t2 = st.tabs(["Tong hop theo PGD", "Danh sach chi tiet"])

        with t1:
            try:
                df_tt = thong_ke_phan_loai(df_cl)
                if not df_tt.empty:
                    df_tt["Du no (ty)"] = (df_tt["Du no (VND)"] / 1e9).round(3)
                    df_show = (
                        df_tt[["PGD", "Phan loai", "So KH", "Du no (ty)"]]
                        .sort_values(["PGD", "Phan loai"])
                    )
                    st.dataframe(
                        df_show,
                        use_container_width=True,
                        height=400,
                        hide_index=True,
                    )
                else:
                    st.info("Khong co du lieu de tong hop.")
            except Exception as e:
                logger.error("tab_phan_loai_kh t1: %s", e, exc_info=True)
                st.error(f"Loi tong hop: {e}")

        with t2:
            # Lọc theo phân loại
            pl_options = ["Tat ca"] + list(PHAN_LOAI_LABELS.keys())
            sel_pl = st.selectbox(
                "Phan loai", pl_options, key="plkh_filter_pl"
            )
            df_detail = (
                df_cl if sel_pl == "Tat ca"
                else df_cl[df_cl["__phan_loai"] == sel_pl]
            )

            cols_show = [
                c for c in [
                    COT_TEN_PGD, COT_MA_KH, COT_TEN_KH, COT_SO_KU,
                    COT_TEN_CT, COT_TONG_DU_NO, COT_DU_NO_QH,
                    COT_DU_NO_KHOANH, "__phan_loai",
                ]
                if c in df_detail.columns
            ]
            rename_map = {
                COT_TONG_DU_NO:   "Du no (trieu)",
                COT_DU_NO_QH:     "NQH (trieu)",
                COT_DU_NO_KHOANH: "Khoanh (trieu)",
                "__phan_loai":    "Loai",
            }
            df_out = df_detail[cols_show].copy()
            for money_col in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH]:
                if money_col in df_out.columns:
                    df_out[money_col] = df_out[money_col].apply(fmt_ty)
            df_out = df_out.rename(columns=rename_map)
            st.caption(f"{fmt_so(len(df_out))} khoan vay")
            st.dataframe(
                df_out,
                use_container_width=True,
                height=500,
                hide_index=True,
            )
