"""Dashboard mini: KPI Điểm Giao Dịch & Tổ TK&VV trong phạm vi 1 PGD."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from utils import fmt_so
from logger import get_logger

logger = get_logger(__name__)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """Tổng quan ĐGD & Tổ TK&VV — KPI và cảnh báo nhanh."""
    from components.delta_card import kpi_row as _kpi_row
    from services.cbtd_dia_ban_service import tom_tat_kpi as _tom_kpi, canh_bao_cbtd_dia_ban as _canh_bao
    from services.cdtotkvv_service import tong_hop_tu_pgd_data as _tong_hop_cdto, loc_df as _loc_df
    from data.khtd import doc_cbtd as _dc

    pgd_user = kwargs.get("pgd_user", "")
    df       = kwargs.get("df")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("📊 Tổng quan ĐGD & Tổ TK&VV")
        st.caption(f"Phạm vi: {pgd_user or 'PGD của bạn'}")

        dgd_map   = db.doc_dgd_map() or {}
        cbtd_data = {}
        try:
            cbtd_all = _dc()
            if pgd_user:
                cbtd_data = {
                    k: v for k, v in cbtd_all.items()
                    if str(v.get("pgd", "")).strip().lower() == pgd_user.strip().lower()
                }
            else:
                cbtd_data = cbtd_all
        except Exception:
            pass

        dgd_pgd: dict = {}
        if pgd_user:
            for pgd_k, xa_block in dgd_map.items():
                if str(pgd_k).strip().lower() == pgd_user.strip().lower():
                    dgd_pgd = {pgd_k: xa_block}
                    break
        else:
            dgd_pgd = dgd_map

        df_cdto_all = None
        try:
            df_cdto_all = _tong_hop_cdto()
            if df_cdto_all is not None and not df_cdto_all.empty:
                df_cdto_all = _loc_df(df_cdto_all, "pgd", pgd_user)
        except Exception:
            pass

        kpi = _tom_kpi(cbtd_data, dgd_pgd, df_cdto_all)

        _kpi_row(
            cols=[
                {"label": "CBTD của PGD", "value": fmt_so(kpi["so_cbtd"]),     "icon": "👔"},
                {"label": "Tổng ĐGD",     "value": fmt_so(kpi["so_dgd_tong"]), "icon": "📍"},
                {"label": "Tổng Tổ",      "value": fmt_so(kpi["so_to_tong"]),  "icon": "🏘️"},
                {"label": "Điểm TB",       "value": f"{kpi['diem_tb']:.1f}" if kpi["so_to_tong"] else "—",    "icon": "⭐"},
                {"label": "% Tổ đạt",     "value": f"{kpi['pct_to_dat']:.1f}%" if kpi["so_to_tong"] else "—", "icon": "✅"},
                {"label": "Tổ TB/Yếu",    "value": fmt_so(kpi["so_to_tb_yeu"]), "icon": "🔴" if kpi["so_to_tb_yeu"] else "🟢"},
            ],
            num_columns=6,
        )

        try:
            cbs = _canh_bao(cbtd_data, dgd_pgd, df, df_cdto_all)
            if cbs:
                with st.expander(f"🔔 Cảnh báo ({len(cbs)})", expanded=True):
                    for cb in cbs:
                        if cb["muc_do"] == "🔴":
                            st.error(cb["noi_dung"])
                        else:
                            st.warning(cb["noi_dung"])
            else:
                st.success("✅ Không có cảnh báo nào cho PGD này.")
        except Exception:
            pass
