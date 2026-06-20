"""Trang chủ dashboard PGD — KPI cards, truy cập nhanh, cảnh báo, nhiệm vụ."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

import db
from config import (
    COT_TONG_DU_NO, COT_MA_KH, COT_TEN_TO, COT_TEN_PGD,
    COT_TEN_XA, COT_DVUT, COT_DU_NO_QH,
)
from data import danh_dau_khong_hd_cached
from state_manager import SCMStateManager
from utils import fmt_so, vn
from components.delta_card import kpi_row
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Trang chủ dashboard PGD — tổng quan KPI, shortcut, cảnh báo, nhiệm vụ."""
    df_pgd   = kwargs.get("df")
    role     = kwargs.get("role")
    pgd_user = kwargs.get("pgd_user", "")

    ctx = tab if tab is not None else st.container()
    with ctx:
        state = SCMStateManager()
        st.subheader("🏠 Trang Chủ")

        # ── Header ──────────────────────────────────────────────────────────
        try:
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                ten_pgd = pgd_user or "Toàn địa bàn"
                so_ho_so = len(df_pgd) if df_pgd is not None and not df_pgd.empty else 0
                st.markdown(f"**{ten_pgd}** · {fmt_so(so_ho_so)} hồ sơ")
            with col_btn:
                if st.button("🔄 Làm mới", use_container_width=True, key="trang_chu_refresh"):
                    st.rerun()
        except Exception as e:
            logger.error("_render_trang_chu header: %s", e, exc_info=True)
            st.error(f"❌ Lỗi header: {e}")

        # ── KPI cards ───────────────────────────────────────────────────────
        try:
            from workspaces.ws_operation import _kpi_pgd_list  # lazy: avoids circular import
            if df_pgd is None or df_pgd.empty:
                st.warning("⚠️ Chưa có dữ liệu. Vui lòng upload file HSTD.")
            else:
                kpi_data = _kpi_pgd_list(df_pgd, pgd_user or "")
                if kpi_data:
                    kpi_row(kpi_data, num_columns=4)
        except Exception as e:
            logger.error("_render_trang_chu kpi: %s", e, exc_info=True)
            st.error(f"❌ Lỗi KPI: {e}")

        # ── KPI BQ ──────────────────────────────────────────────────────────
        try:
            if df_pgd is not None and not df_pgd.empty and COT_TONG_DU_NO in df_pgd.columns:
                df_bq = df_pgd.copy()
                df_bq[COT_TONG_DU_NO] = pd.to_numeric(df_bq[COT_TONG_DU_NO], errors="coerce").fillna(0)
                tdn = df_bq[COT_TONG_DU_NO].sum()

                n_kh  = int(df_bq[COT_MA_KH].nunique()) if COT_MA_KH in df_bq.columns else 0
                bq_kh = tdn / n_kh if n_kh > 0 else 0

                n_to  = int(df_bq.groupby([COT_TEN_PGD, COT_TEN_TO]).ngroups) if COT_TEN_TO in df_bq.columns else 0
                bq_to = tdn / n_to if n_to > 0 else 0

                n_xa  = int(df_bq[COT_TEN_XA].dropna().loc[lambda s: (s != "") & (s != "CỘNG")].nunique()) if COT_TEN_XA in df_bq.columns else 0
                bq_xa = tdn / n_xa if n_xa > 0 else 0

                n_hoi = int(df_bq[COT_DVUT].dropna().loc[lambda s: (s != "") & (s != "CỘNG")].nunique()) if COT_DVUT in df_bq.columns else 0
                bq_hoi = tdn / n_hoi if n_hoi > 0 else 0

                kpi_row([
                    {"label": "Dư nợ BQ hộ vay",   "value": f"{vn(bq_kh/1_000_000,1)} tr" if n_kh > 0 else "—",
                     "icon": "👤",  "help": f"{fmt_so(n_kh)} khách hàng có dư nợ"},
                    {"label": "Dư nợ BQ tổ TKVV",  "value": f"{vn(bq_to/1_000_000,1)} tr" if n_to > 0 else "—",
                     "icon": "🏘️", "help": f"{fmt_so(n_to)} tổ TK&VV"},
                    {"label": "Dư nợ BQ xã",        "value": f"{vn(bq_xa/1_000_000,1)} tr" if n_xa > 0 else "—",
                     "icon": "📍",  "help": f"{fmt_so(n_xa)} xã"},
                    {"label": "Dư nợ BQ Hội",       "value": f"{vn(bq_hoi/1_000_000,1)} tr" if n_hoi > 0 else "—",
                     "icon": "🤝",  "help": f"{fmt_so(n_hoi)} hội đoàn thể"},
                ], num_columns=4)
        except Exception as e:
            logger.error("_render_trang_chu kpi_bq: %s", e, exc_info=True)
            st.error(f"❌ Lỗi KPI BQ: {e}")

        st.divider()

        # ── 2 cột: Truy cập nhanh | Cảnh báo + Nhiệm vụ ────────────────────
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("**🚀 Truy cập nhanh**")
            try:
                shortcuts = [
                    ("🔍", "Tra cứu hồ sơ",  "Tìm kiếm chi tiết",   "nghiep_vu_pgd",    2),
                    ("📈", "Báo cáo chi tiết","Xem báo cáo",          "bao_cao_giao_ban", 0),
                    ("⏰", "Đến hạn",          "Khoản đến hạn",        "nghiep_vu_pgd",    4),
                    ("📝", "Giao ban xã",      "Biên bản giao ban",    "bao_cao_giao_ban", 2),
                    ("🎯", "KHTD PGD",         "Kế hoạch tín dụng",   "ke_hoach_pgd",     0),
                    ("🔔", "Đôn đốc KHĐ",     "Khoản 3m KHĐ",        "kiem_soat_rr",     0),
                ]
                for i in range(0, len(shortcuts), 2):
                    s1, s2 = st.columns(2)
                    if i < len(shortcuts):
                        icon, title, desc, nhom, tab_idx = shortcuts[i]
                        with s1:
                            if st.button(f"{icon} {title}\n_{desc}_", use_container_width=True,
                                         key=f"sc_1_{i}"):
                                state.nav_ws_op_nhom = nhom
                                state.nav_ws_op_jump_tab = tab_idx
                                st.rerun()
                    if i + 1 < len(shortcuts):
                        icon, title, desc, nhom, tab_idx = shortcuts[i + 1]
                        with s2:
                            if st.button(f"{icon} {title}\n_{desc}_", use_container_width=True,
                                         key=f"sc_1_{i+1}"):
                                state.nav_ws_op_nhom = nhom
                                state.nav_ws_op_jump_tab = tab_idx
                                st.rerun()
            except Exception as e:
                logger.error("_render_trang_chu shortcut: %s", e, exc_info=True)
                st.error(f"❌ Lỗi shortcut: {e}")

        with col_right:
            st.markdown("**⚠️ Cảnh báo**")
            try:
                if df_pgd is None or df_pgd.empty:
                    st.info("Không có dữ liệu để hiển thị cảnh báo.")
                else:
                    alerts = []
                    try:
                        nqh_count = (pd.to_numeric(df_pgd[COT_DU_NO_QH], errors="coerce") > 0).sum()
                        if nqh_count > 0:
                            alerts.append(("🔴", f"NQH > 0: {fmt_so(nqh_count)} khoản", "danger", "bao_cao_giao_ban", 1))
                    except Exception as e:
                        logger.error("trang_chu_pgd canh_bao_nqh: %s", e, exc_info=True)
                    try:
                        df_kh = danh_dau_khong_hd_cached(df_pgd)
                        khd_count = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
                        if khd_count > 0:
                            alerts.append(("📅", f"3m KHĐ: {fmt_so(khd_count)} khoản", "danger", "kiem_soat_rr", 0))
                    except Exception as e:
                        logger.error("trang_chu_pgd canh_bao_khd: %s", e, exc_info=True)
                    if alerts:
                        for icon, text, color, nhom, tab_idx in alerts:
                            if st.button(f"{icon} {text}", use_container_width=True, key=f"alert_{text}"):
                                state.nav_ws_op_nhom = nhom
                                state.nav_ws_op_jump_tab = tab_idx
                                st.rerun()
                    else:
                        st.success("✅ Không có cảnh báo nào")
            except Exception as e:
                logger.error("trang_chu_pgd canh_bao: %s", e, exc_info=True)
                st.error(f"❌ Lỗi cảnh báo: {e}")

            st.markdown("**✅ Nhiệm vụ đang chờ**")
            try:
                with db.get_conn() as conn:
                    rows = conn.execute(
                        """SELECT id, tieu_de, ngay_deadline, trang_thai
                           FROM nhiem_vu
                           WHERE (pgd = ? OR pgd IS NULL)
                             AND trang_thai NOT IN ('da_hoan_thanh', 'tam_dung')
                           ORDER BY ngay_deadline ASC
                           LIMIT 5""",
                        (pgd_user,),
                    ).fetchall()
                nv_pgd = [dict(r) for r in rows]
                if not nv_pgd:
                    st.success("Không có nhiệm vụ nào đang chờ")
                else:
                    for nv in nv_pgd:
                        dl = nv.get("ngay_deadline", "")
                        st.caption(f"📌 {nv.get('tieu_de', '—')}")
                        st.caption(f"Hạn: {dl or '—'}")
            except Exception as e:
                logger.error("trang_chu_pgd nhiem_vu: %s", e, exc_info=True)
                st.warning(f"⚠️ Không thể tải danh sách nhiệm vụ: {e}")
