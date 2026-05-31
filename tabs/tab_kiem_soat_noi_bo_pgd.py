"""Kiểm soát Nội bộ PGD — Checklist 7 điểm tự kiểm tra trước khi báo cáo CN."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

import db
from config import (
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_TH,
    COT_LAI_TON, COT_SDT, COT_NGAY_DH, COT_MA_KH,
    PGD_XA_MAP,
)
from data import danh_dau_khong_hd_cached, canh_bao_migration_cached
from utils import fmt_so
from components.delta_card import kpi_row
from state_manager import SCMStateManager
from logger import get_logger

logger = get_logger(__name__)

_NGUONG_AN_TOAN_PGD = 1.0


def render(tab=None, **kwargs) -> None:
    df_pgd = kwargs.get("df")
    pgd_user = kwargs.get("pgd_user", "")
    role = kwargs.get("role", "user")

    st.subheader("✅ Kiểm soát Nội bộ PGD")
    st.caption(
        f"CBTD tự kiểm tra trước khi báo cáo — "
        f"**{pgd_user or 'PGD'}** · {date.today().strftime('%d/%m/%Y')}"
    )

    if df_pgd is None or df_pgd.empty:
        st.warning("⚠️ Chưa có dữ liệu HSTD.")
        return

    tdn = pd.to_numeric(df_pgd[COT_TONG_DU_NO], errors="coerce").sum() \
        if COT_TONG_DU_NO in df_pgd.columns else 0.0
    dqh = pd.to_numeric(df_pgd[COT_DU_NO_QH], errors="coerce").sum() \
        if COT_DU_NO_QH in df_pgd.columns else 0.0
    tlqh = dqh / tdn * 100 if tdn > 0 else 0.0

    df_kh = danh_dau_khong_hd_cached(df_pgd)
    n_khd = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0
    n_tong = len(df_pgd)
    tl_khd = n_khd / n_tong * 100 if n_tong > 0 else 0.0

    df_amber = canh_bao_migration_cached(df_pgd)
    n_amber = len(df_amber)

    n_co_lai_ton = 0
    if COT_LAI_TON in df_pgd.columns:
        n_co_lai_ton = int(
            (pd.to_numeric(df_pgd[COT_LAI_TON], errors="coerce").fillna(0) > 0).sum()
        )

    n_thieu_sdt = 0
    if COT_SDT in df_pgd.columns:
        n_thieu_sdt = int(
            df_pgd[COT_SDT].isna().sum()
            + (df_pgd[COT_SDT].astype(str).str.strip() == "").sum()
        )

    thang_toi = date.today() + relativedelta(months=1)
    n_dh_thang_toi = 0
    if COT_NGAY_DH in df_pgd.columns:
        _ngay_dh = pd.to_datetime(df_pgd[COT_NGAY_DH], errors="coerce")
        n_dh_thang_toi = int(
            ((_ngay_dh.dt.month == thang_toi.month) & (_ngay_dh.dt.year == thang_toi.year)).sum()
        )

    kh_xa = db.doc_kv("khtd_xa") or {}
    ds_xa_pgd = set(PGD_XA_MAP.get(pgd_user or "", []))
    tong_kh_pgd = sum(
        float(v) for k, v in kh_xa.items()
        if "|" in k and k.split("|", 1)[0] in ds_xa_pgd
    ) if (kh_xa and ds_xa_pgd) else 0.0
    pct_khtd = tdn / tong_kh_pgd * 100 if tong_kh_pgd > 0 else None

    items = [
        ("nqh", "Tỷ lệ NQH < 1%", tlqh < _NGUONG_AN_TOAN_PGD,
         f"NQH hiện tại: **{tlqh:.3f}%**", "kiem_soat_rr", 0),
        ("khd", "3 tháng KHĐ < 5% tổng hồ sơ", tl_khd < 5.0,
         f"3m KHĐ: **{n_khd} món** ({tl_khd:.1f}%)", "kiem_soat_rr", 1),
        ("amber", "Không có khoản sắp chuyển 3m KHĐ", n_amber == 0,
         f"Sắp chuyển: **{n_amber} món** (lãi tồn 2–3 tháng)", "kiem_soat_rr", 3),
        ("lai", "Không có lãi tồn", n_co_lai_ton == 0,
         f"Lãi tồn > 0: **{n_co_lai_ton} hồ sơ**", "kiem_soat_rr", 0),
        ("sdt", "Hồ sơ đủ số điện thoại", n_thieu_sdt == 0,
         f"Thiếu SĐT: **{n_thieu_sdt} hồ sơ**", "nghiep_vu_pgd", 2),
        ("daohantoi", f"Đã nắm hồ sơ đến hạn tháng {thang_toi.month}/{thang_toi.year}",
         n_dh_thang_toi > 0, f"Đến hạn tháng tới: **{n_dh_thang_toi} món**", "nghiep_vu_pgd", 4),
        ("khtd", "Tiến độ KHTD ≥ 95%", (pct_khtd or 0) >= 95,
         f"KHTD: **{pct_khtd:.1f}%**" if pct_khtd is not None else "KHTD: **Chưa có kế hoạch**",
         "ke_hoach_pgd", 0),
    ]

    n_pass = sum(1 for _, _, ok, _, _, _ in items if ok)
    n_fail = len(items) - n_pass

    c_ok, c_fail, c_pct = st.columns(3)
    c_ok.metric("✅ Đạt", n_pass, help="Số tiêu chí đạt yêu cầu")
    c_fail.metric("🔴 Cần xử lý", n_fail, help="Số tiêu chí cần hành động")
    c_pct.metric(
        "Điểm kiểm soát", f"{n_pass}/{len(items)}",
        delta=f"{n_pass / len(items) * 100:.0f}%",
        delta_color="normal" if n_fail == 0 else "inverse",
    )

    if n_fail == 0:
        st.success("🎉 Tất cả tiêu chí đạt — sẵn sàng báo cáo lên Chi nhánh!")
    else:
        st.warning(f"⚠️ Còn **{n_fail} tiêu chí** cần xử lý trước khi báo cáo.")

    st.divider()

    state = SCMStateManager()
    for idx, (item_id, tieu_de, ok, mo_ta, nhom_nav, tab_idx) in enumerate(items):
        icon = "✅" if ok else "🔴"
        bg = "rgba(46,125,50,0.08)" if ok else "rgba(198,40,40,0.08)"
        border = "#2e7d32" if ok else "#c62828"
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"""<div style="padding:8px 12px;margin:4px 0;border-left:3px solid {border};
                    background:{bg};border-radius:4px">
                    <span style="font-size:1.1em">{icon}</span>&nbsp;
                    <b>{tieu_de}</b><br>
                    <span style="font-size:0.85em;color:#94A3B8">{mo_ta}</span>
                </div>""",
                unsafe_allow_html=True,
            )
        with col_btn:
            if not ok and st.button("🔗 Xử lý", key=f"ks_nb_{item_id}",
                                     use_container_width=True):
                state.nav_ws_op_nhom = nhom_nav
                state.nav_ws_op_jump_tab = tab_idx
                st.rerun()
