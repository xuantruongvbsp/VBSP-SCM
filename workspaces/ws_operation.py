"""

Không gian Tác nghiệp (Operation View)

────────────────────────────────────────

Dành cho CBTD — Tra cứu chi tiết + Document Hub (Trung tâm văn bản tự động).

"""





from logger import get_logger

logger = get_logger(__name__)



import importlib

import socket

import hashlib



import streamlit as st

import pandas as pd

import os

from io import BytesIO

from datetime import date, datetime

import plotly.graph_objects as go





def _df_hash(df: pd.DataFrame) -> str:

    """Tạo hash ngắn cho DataFrame để dùng làm cache key."""

    if df is None or df.empty:

        return "empty"

    try:

        # Hash dựa trên shape và sample dữ liệu

        sample = str(df.shape) + str(df.head(2).to_json()) + str(df.tail(2).to_json())

        return hashlib.md5(sample.encode()).hexdigest()[:12]

    except Exception:

        return "unknown"



import db

from state_manager import SCMStateManager

from config import (

    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_TEN_CT,

    COT_DU_NO_QH, COT_DU_NO_TH, COT_TONG_DU_NO, COT_NGAY_DH, COT_NGAY_VAY,

    COT_TEN_PGD, COT_SDT, COT_DIA_CHI,

    COT_LAI_TON, COT_LAI_THANG, COT_DVUT, COT_TEN_XA,

    COT_LAI_TON_QH,

    TEMPLATES_DIR, TAG_MAP, PGD_XA_MAP,

)

from auth import co_quyen_upload_pgd, is_cn_role, is_pgd_role, get_permissions, get_tab_permissions

from data import (

    danh_dau_khong_hd, danh_dau_khong_hd_cached,

    tong_hop_khong_hd, tong_hop_khong_hd_cached,

    ds_chi_tiet_khong_hd, canh_bao_migration, canh_bao_migration_cached,

)

from data.pgd import pgd_slug

from utils import (

    fmt,

    fmt_ty,

    fmt_so,

    vn,

    auto_fill_document,

    auto_fill_batch,

    auto_fill_klgb,

    quet_templates,

    xuat_excel,

    hien_thi_dataframe_phan_trang,

    get_tab_context,

    lazy_tabs,

)

from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file

from pdf_service import xuat_pdf, kiem_tra_pdf_dependency, render_huong_dan

from components.delta_card import delta_card, kpi_row

from components.filter_bar import filter_bar, apply_filters

from components.loan_drawer import loan_detail_drawer

from components.export_pdf import download_pdf_button, xuat_pdf_co_chart





def _lazy_tab(name: str):

    """Import tab module — dùng sys.modules cache của Python, tự invalidate khi Streamlit hot-reload."""

    return importlib.import_module(f"tabs.{name}")





# ── Helper: tính 4 KPI DeltaCard cho trang chủ PGD ──────────────────────────



@st.cache_data(ttl=300, show_spinner="Đang tính KPI...")

def _kpi_pgd_list_cached(df_hash: str, pgd_user: str, _df_json: str) -> list[dict]:

    """Cached version của _kpi_pgd_list — dùng hash thay vì df trực tiếp."""

    # Parse lại df từ json (chỉ dùng cho cache, không dùng cho tính toán thực)

    df_pgd = pd.read_json(_df_json) if _df_json else pd.DataFrame()

    return _kpi_pgd_list_impl(df_pgd, pgd_user)





def _kpi_pgd_list_impl(df_pgd: pd.DataFrame, pgd_user: str) -> list[dict]:

    """Implementation thực sự của tính KPI."""

    kpi: list[dict] = []

    if df_pgd is None or df_pgd.empty:

        return kpi



    # ── Tính trước để dùng chung ───────────────────────────────────────────

    tong_dn = (

        pd.to_numeric(df_pgd[COT_TONG_DU_NO], errors="coerce").sum()

        if COT_TONG_DU_NO in df_pgd.columns else 0.0

    )

    nqh_dn = (

        pd.to_numeric(df_pgd[COT_DU_NO_QH], errors="coerce").sum()

        if COT_DU_NO_QH in df_pgd.columns else 0.0

    )



    # ── KPI 1: Tổng dư nợ ─────────────────────────────────────────────────

    try:

        pct_nqh = (nqh_dn / tong_dn * 100) if tong_dn > 0 else 0.0

        kpi.append({

            "label":       "Tổng dư nợ",  # noqa: COT

            "value":       fmt_ty(tong_dn),

            "delta":       -pct_nqh,         # ↓ mũi tên xuống, inverse → xanh khi thấp

            "delta_label": "% NQH",

            "icon":        "💰",

            "suffix":      "",

            "precision":   2,

            "help":        "Tổng dư nợ toàn PGD",

            "delta_color": "inverse",

        })

    except Exception as e:

        logger.error("_kpi_pgd_list KPI1: %s", e, exc_info=True)



    # ── KPI 2: Nợ quá hạn ─────────────────────────────────────────────────

    try:

        ty_le_nqh = (nqh_dn / tong_dn * 100) if tong_dn > 0 else 0.0

        kpi.append({

            "label":       "Nợ quá hạn",  # noqa: COT

            "value":       fmt_ty(nqh_dn),

            "delta":       ty_le_nqh,         # ↑ mũi tên lên, inverse → đỏ khi cao

            "delta_label": "% so dư nợ",

            "icon":        "🔴",

            "suffix":      "",

            "precision":   2,

            "help":        "Dư nợ quá hạn toàn PGD",

            "delta_color": "inverse",

        })

    except Exception as e:

        logger.error("_kpi_pgd_list KPI2: %s", e, exc_info=True)



    # ── KPI 3: 3 tháng KHĐ ────────────────────────────────────────────────

    try:

        df_kh   = danh_dau_khong_hd_cached(df_pgd)

        n_khd   = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0

        pct_khd = (n_khd / len(df_pgd) * 100) if len(df_pgd) > 0 else 0.0

        kpi.append({

            "label":       "3 tháng KHĐ",

            "value":       fmt_so(n_khd),

            "delta":       pct_khd,           # ↑ mũi tên lên, inverse → đỏ khi nhiều KHĐ

            "delta_label": "% tổng hồ sơ",

            "icon":        "📅",

            "suffix":      "món",

            "precision":   1,

            "help":        "Khoản hộ vay 3 tháng không hoạt động",

            "delta_color": "inverse",

        })

    except Exception as e:

        logger.error("_kpi_pgd_list KPI3: %s", e, exc_info=True)



    # ── KPI 4: Tiến độ KHTD ───────────────────────────────────────────────

    try:

        # khtd_xa: {ten_xa}|{ma_ct_key} → gia_tri_dong (VND)

        kh_xa  = db.doc_kv("khtd_xa") or {}

        ds_xa  = set(PGD_XA_MAP.get(pgd_user, []))

        tong_kh = sum(

            float(v)

            for k, v in kh_xa.items()

            if "|" in k and k.split("|", 1)[0] in ds_xa

        ) if (kh_xa and ds_xa) else 0.0



        # Tính tiến độ thực hiện so với kế hoạch

        tien_do = min((tong_dn / tong_kh * 100), 999.9) if tong_kh > 0 else 0.0

        kpi.append({

            "label":       "Tiến độ KHTD",

            "value":       f"{tien_do:.1f}%",

            "delta":       fmt_ty(tong_kh),

            "delta_label": "KH năm",

            "icon":        "🎯",

            "suffix":      "",

            "precision":   1,

            "help":        "Tỷ lệ thực hiện kế hoạch tín dụng",

            "delta_color": "normal",

        })

    except Exception as e:

        logger.error("_kpi_pgd_list KPI4: %s", e, exc_info=True)



    return kpi





def _kpi_pgd_list(df_pgd: pd.DataFrame, pgd_user: str) -> list[dict]:

    """

    Tính 4 KPI DeltaCard cho trang chủ / sidebar PGD.

    Wrapper có cache — tự động hash dataframe.



    Returns:

        List dict (kwargs cho delta_card), tối đa 4 phần tử.

    """

    if df_pgd is None or df_pgd.empty:

        return []

    

    df_hash = _df_hash(df_pgd)

    # Convert df thành json string để serialize cho cache

    try:

        _df_json = df_pgd.head(1000).to_json() if len(df_pgd) > 1000 else df_pgd.to_json()

    except Exception:

        _df_json = ""

    

    return _kpi_pgd_list_cached(df_hash, pgd_user, _df_json)





# ═══════════════════════════════════════════════════════════════════════════════

# GAUGE & DASHBOARD NÂNG CAO — Cho PGD (y chang ws_executive nhưng phạm vi PGD)

# ═══════════════════════════════════════════════════════════════════════════════



_NGUONG_AN_TOAN_PGD = 1.0   # % — xanh lá

_NGUONG_CANH_BAO_PGD = 2.0  # % — cam





def _mau_nqh_pgd(tlqh: float) -> tuple[str, str, str]:

    """Trả về (màu_hex, nhãn_trạng_thái, icon) theo mức NQH."""

    if tlqh < _NGUONG_AN_TOAN_PGD:

        return "#2e7d32", "AN TOÀN", "✅"

    if tlqh < _NGUONG_CANH_BAO_PGD:

        return "#f57f17", "CẦN THEO DÕI", "⚠️"

    return "#c62828", "VƯỢT NGƯỠNG", "🚨"





def _gauge_nqh_pgd(tlqh: float, ten_pgd: str = "") -> go.Figure:

    """

    Tạo biểu đồ đồng hồ đo (Gauge + Number) Tỷ lệ NQH cho PGD.

    Vùng màu: xanh [0–1%] | cam [1–2%] | đỏ [2–5%].

    """

    mau, tinh_trang, _ = _mau_nqh_pgd(tlqh)

    gio_han = 5.0  # Trục gauge tối đa 5%

    title_text = f"Tỷ lệ NQH {ten_pgd or 'PGD'}<br><span style='font-size:14px;color:{mau};font-weight:bold'>{tinh_trang}</span>"



    fig = go.Figure(go.Indicator(

        mode="gauge+number+delta",

        value=round(tlqh, 3),

        number={

            "suffix": "%",

            "font": {"size": 40, "color": mau, "family": "Arial"},

            "valueformat": ".3f",

        },

        delta={

            "reference": _NGUONG_AN_TOAN_PGD,

            "increasing": {"color": "#c62828"},

            "decreasing": {"color": "#2e7d32"},

            "suffix": "% so ngưỡng",

            "valueformat": ".3f",

        },

        gauge={

            "axis": {

                "range": [0, gio_han],

                "tickwidth": 1,

                "tickcolor": "#666",

                "ticksuffix": "%",

                "nticks": 6,

            },

            "bar": {"color": mau, "thickness": 0.28},

            "bgcolor": "rgba(0,0,0,0)",

            "borderwidth": 0,

            "steps": [

                {"range": [0, _NGUONG_AN_TOAN_PGD], "color": "rgba(46,125,50,0.12)"},

                {"range": [_NGUONG_AN_TOAN_PGD, _NGUONG_CANH_BAO_PGD], "color": "rgba(245,127,23,0.12)"},

                {"range": [_NGUONG_CANH_BAO_PGD, gio_han], "color": "rgba(198,40,40,0.12)"},

            ],

            "threshold": {

                "line": {"color": "#e65100", "width": 3},

                "thickness": 0.82,

                "value": _NGUONG_AN_TOAN_PGD,

            },

        },

        title={

            "text": title_text,

            "font": {"size": 16},

        },

    ))

    fig.update_layout(

        height=270,

        margin=dict(l=20, r=20, t=50, b=10),

        paper_bgcolor="rgba(0,0,0,0)",

        font_family="Arial",

    )

    return fig







def _render_trang_chu(tab, df_pgd: pd.DataFrame, role: str, pgd_user: str, kwargs: dict):

    """

    Trang chủ dashboard PGD — tổng quan KPI, shortcut, cảnh báo, nhiệm vụ.

    """

    ctx = tab if tab is not None else st.container()

    with ctx:

        state = SCMStateManager()

        st.subheader("🏠 Trang Chủ")



        # ── Vùng A: Header ──────────────────────────────────────────────────

        try:

            col_info, col_btn = st.columns([3, 1])

            with col_info:

                ten_pgd = pgd_user or "Chi nhánh"

                so_ho_so = len(df_pgd) if df_pgd is not None and not df_pgd.empty else 0

                st.markdown(f"**{ten_pgd}** · {fmt_so(so_ho_so)} hồ sơ")

            with col_btn:

                if st.button("🔄 Làm mới", use_container_width=True, key="trang_chu_refresh"):

                    st.rerun()

        except Exception as e:  # conv: skip

            logger.error("Lỗi trong khối except: %s", e, exc_info=True)

            st.error(f"❌ Lỗi header: {e}")



        # ── Vùng B: 4 KPI cards ────────────────────────────────────────────

        try:

            if df_pgd is None or df_pgd.empty:

                st.warning("⚠️ Chưa có dữ liệu. Vui lòng upload file HSTD.")

            else:

                kpi_data = _kpi_pgd_list(df_pgd, pgd_user or "")

                if kpi_data:

                    kpi_row(kpi_data, num_columns=4)

        except Exception as e:  # conv: skip

            logger.error("Lỗi trong khối except: %s", e, exc_info=True)

            st.error(f"❌ Lỗi KPI: {e}")



        st.divider()



        # ── Vùng C: 2 cột ngang ────────────────────────────────────────────

        col_left, col_right = st.columns([1, 1])



        # Cột trái: Truy cập nhanh

        with col_left:

            st.markdown("**🚀 Truy cập nhanh**")

            try:

                shortcuts = [

                    ("🔍", "Tra cứu hồ sơ", "Tìm kiếm chi tiết", "nghiep_vu_pgd", 2),

                    ("📈", "Báo cáo chi tiết", "Xem báo cáo", "bao_cao_giao_ban", 0),

                    ("⏰", "Đến hạn", "Khoản đến hạn", "nghiep_vu_pgd", 4),

                    ("📝", "Giao ban xã", "Biên bản giao ban", "bao_cao_giao_ban", 2),

                    ("🎯", "KHTD PGD", "Kế hoạch tín dụng", "ke_hoach_pgd", 0),

                    ("🔔", "Đôn đốc KHĐ", "Khoản 3m KHĐ", "kiem_soat_rr", 0),

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

            except Exception as e:  # conv: skip

                logger.error("Lỗi trong khối except: %s", e, exc_info=True)

                st.error(f"❌ Lỗi shortcut: {e}")



        # Cột phải: Cảnh báo + Nhiệm vụ

        with col_right:

            # Phần cảnh báo

            st.markdown("**⚠️ Cảnh báo**")

            try:

                if df_pgd is None or df_pgd.empty:

                    st.info("Không có dữ liệu để hiển thị cảnh báo.")

                else:

                    alerts = []



                    # Cảnh báo NQH

                    try:

                        nqh_count = (pd.to_numeric(df_pgd[COT_DU_NO_QH], errors="coerce") > 0).sum()

                        if nqh_count > 0:

                            alerts.append(("🔴", f"NQH > 0: {fmt_so(nqh_count)} khoản", "danger", "bao_cao_giao_ban", 1))

                    except Exception as e:

                        logger.error("_render_trang_chu canh_bao_nqh: %s", e, exc_info=True)



                    # Cảnh báo 3m KHĐ

                    try:

                        df_kh = danh_dau_khong_hd_cached(df_pgd)

                        khd_count = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0

                        if khd_count > 0:

                            alerts.append(("📅", f"3m KHĐ: {fmt_so(khd_count)} khoản", "danger", "kiem_soat_rr", 0))

                    except Exception as e:

                        logger.error("_render_trang_chu canh_bao_khd: %s", e, exc_info=True)



                    if alerts:

                        for icon, text, color, nhom, tab_idx in alerts:

                            if st.button(f"{icon} {text}", use_container_width=True, key=f"alert_{text}"):

                                state.nav_ws_op_nhom = nhom

                                state.nav_ws_op_jump_tab = tab_idx

                                st.rerun()

                    else:

                        st.success("✅ Không có cảnh báo nào")

            except Exception as e:  # conv: skip

                logger.error("Lỗi trong khối except: %s", e, exc_info=True)

                st.error(f"❌ Lỗi cảnh báo: {e}")



            # Phần nhiệm vụ — query trực tiếp từ bảng nhiem_vu

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

            except Exception as e:  # conv: skip

                logger.error("Lỗi tải nhiệm vụ sidebar: %s", e, exc_info=True)

                st.warning(f"⚠️ Không thể tải danh sách nhiệm vụ: {e}")





def _render_don_doc(df: pd.DataFrame, pgd_user: str, role: str):

    """

    Widget 3 tháng không hoạt động — dành cho CBTD địa bàn.

    Hiển thị bảng theo ĐVUT + xuất danh sách đôn đốc.

    """

    st.subheader("🔴 Món vay 3 tháng không hoạt động")

    st.caption("Lãi tồn > 3 tháng lãi dự thu — cần đôn đốc thu hồi trước khi phát sinh NQH")



    if df is None or df.empty:

        st.warning("Chưa có dữ liệu."); return



    # Đánh dấu 3 tháng không hoạt động

    df_kh = danh_dau_khong_hd_cached(df)

    n_khd = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0

    n_tong = len(df_kh)



    # KPI

    k1, k2, k3 = st.columns(3)

    k1.metric("Tổng món vay", fmt_so(n_tong))

    k2.metric("Cần đôn đốc 🔴", fmt_so(n_khd),

              delta=f"{n_khd/n_tong*100:.1f}% tổng món" if n_tong > 0 else "0%",

              delta_color="inverse" if n_khd > 0 else "off")

    tong_lai = (df_kh[df_kh.get("is_3m_inactive", False)][COT_LAI_TON].sum()
                if COT_LAI_TON in df_kh.columns else 0)
    k3.metric("Lãi tồn cần thu (đồng)", fmt(tong_lai))



    if n_khd == 0:

        st.success("✅ Không có món vay nào quá 3 tháng không hoạt động!")

        return



    st.divider()



    # ── Bảng tổng hợp theo ĐVUT ───────────────────────────────────────────

    st.markdown("**Tổng hợp theo Hội đoàn thể (ĐVUT)**")

    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_DVUT)

    if not nhom_dvut.empty:

        hien_thi_dataframe_phan_trang(

            nhom_dvut,

            key="op_khd_nhom_dvut",

            height=220,

        )



    # Bảng theo Xã

    st.markdown("**Tổng hợp theo Xã/Phường**")

    nhom_xa = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_XA)

    if not nhom_xa.empty:

        hien_thi_dataframe_phan_trang(

            nhom_xa,

            key="op_khd_nhom_xa",

            height=220,

        )



    st.divider()



    # ── Danh sách chi tiết + xuất Excel ──────────────────────────────────

    st.markdown("**📋 Danh sách hộ cần đôn đốc**")

    col_loc, col_xuat = st.columns([2, 1])



    with col_loc:

        ds_dvut = ["Tất cả"]

        if COT_DVUT in df_kh.columns:

            ds_dvut += sorted(df_kh[COT_DVUT].dropna().unique().tolist())

        chon_dvut = st.selectbox("Lọc Hội đoàn thể", ds_dvut, key="op_khd_dvut")



    gia_tri = None if chon_dvut == "Tất cả" else chon_dvut

    df_dondoc = ds_chi_tiet_khong_hd(df_kh, nhom_theo=COT_DVUT,

                                      gia_tri_nhom=gia_tri)



    with col_xuat:

        st.markdown("<br>", unsafe_allow_html=True)

        if not df_dondoc.empty:

            from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file

            kpi_don_doc = [

                ("Số hộ KHĐ", fmt_so(len(df_dondoc)), f"Lọc: {chon_dvut}"),

            ]

            if COT_LAI_TON in df_dondoc.columns:

                kpi_don_doc.append(("Lãi tồn", fmt_ty(df_dondoc[COT_LAI_TON].sum()), "triệu đồng"))

            st.download_button(

                label=f"⬇️ Xuất Excel chuyên nghiệp ({len(df_dondoc)} hộ)",

                type="primary",

                data=xuat_excel_chuyen_nghiep(

                    df=df_dondoc,

                    title="Danh sách Đôn đốc 3 tháng KHĐ",

                    subtitle=f"PGD: {pgd_user} - {chon_dvut}",

                    nguoi_xuat=st.session_state.get("txt_username", ""),

                    kpi_items=kpi_don_doc,

                ),

                file_name=excel_ten_file("DonDoc_3m_KHD"),

                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

                key="op_xuat_khd_pro",

            )



    if not df_dondoc.empty:

        hien_thi_dataframe_phan_trang(

            df_dondoc,

            key="op_khd_dondoc",

            height=360,

        )

        tong_lai_ds = (df_dondoc[COT_LAI_TON].sum()
                       if COT_LAI_TON in df_dondoc.columns else 0)
        st.caption(

            f"**{fmt_so(len(df_dondoc))}** món · "

            f"Lãi tồn: **{fmt(tong_lai_ds)}** triệu đồng"

        )



        # ── LoanDetailDrawer ───────────────────────────────────────────

        st.divider()

        st.markdown("**🔍 Tra cứu chi tiết khoản vay**")

        cols_chon = [c for c in [COT_SO_KU, COT_TEN_KH, COT_MA_KH] if c in df_dondoc.columns]

        if cols_chon:

            df_chon = df_dondoc.copy()

            df_chon["_hien_thi"] = df_chon[cols_chon[0]].astype(str)

            if len(cols_chon) > 1:

                for c in cols_chon[1:]:

                    df_chon["_hien_thi"] += " | " + df_chon[c].astype(str)

            options = dict(zip(df_chon["_hien_thi"], df_dondoc.index))

            selected_label = st.selectbox(

                "Chọn khoản vay để xem chi tiết",

                options=list(options.keys()),

                key="op_khd_chon_drawer",

            )

            if selected_label:

                row_idx = options[selected_label]

                row_data = df_dondoc.loc[row_idx]

                loan_detail_drawer(row_data)

    else:

        st.info("Không có hộ nào thỏa điều kiện.")





def _render_canh_bao_som_pgd(tab, **kwargs) -> None:

    """Nợ đến hạn có nguy cơ cho phân hệ PGD."""

    _lazy_tab("tab_canh_bao_som").render(tab, **kwargs)





# ═══════════════════════════════════════════════════════════════════════════════

# CẢNH BÁO SỚM ĐẦY ĐỦ — Giống ws_management._render_canh_bao() nhưng cho PGD

# ═══════════════════════════════════════════════════════════════════════════════



def _render_canh_bao_som_pgd_full(df: pd.DataFrame, pgd_user: str, role: str, username: str):

    """

    Tab Cảnh báo sớm đầy đủ cho PGD — Migration & 3 tháng không hoạt động.

    Giống y chang _render_canh_bao() trong ws_management nhưng:

    - Top Xã thay vì Top PGD

    - Phạm vi chỉ 1 PGD

    """

    st.subheader("🚨 Cảnh báo sớm — Phân loại nợ & 3 tháng không HĐ")



    if df is None or df.empty:

        st.warning("Chưa có dữ liệu HSTD.")

        return



    # Đánh dấu 3 tháng không hoạt động

    df_kh = danh_dau_khong_hd_cached(df)



    # ── KPI nhanh ──────────────────────────────────────────────────────────

    tong_mon = len(df_kh)

    khd_tong = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0

    df_amber = canh_bao_migration_cached(df_kh)

    amber_tong = len(df_amber)

    tl_khd = khd_tong / tong_mon * 100 if tong_mon > 0 else 0

    tong_lai_khd = 0.0

    if not df_kh.empty and "is_3m_inactive" in df_kh.columns:

        df_khd_only = df_kh[df_kh["is_3m_inactive"]]

        for col in (COT_LAI_TON, COT_LAI_TON_QH):

            if col in df_kh.columns:

                tong_lai_khd += pd.to_numeric(df_khd_only[col], errors="coerce").fillna(0).sum()



    kpi_row([

        {"label": "Tổng món vay", "value": tong_mon, "icon": "📊", "suffix": "", "precision": 0,

         "help": f"Tổng số món vay {pgd_user or 'PGD'}"},

        {"label": "3 tháng KHĐ", "value": khd_tong, "icon": "🔴", "suffix": "", "precision": 0,

         "delta": tl_khd, "delta_label": "% tổng món", "delta_color": "inverse" if tl_khd > 2 else "off",

         "help": "Số món 3 tháng không hoạt động"},

        {"label": "Sắp chuyển KHĐ", "value": amber_tong, "icon": "⚠️", "suffix": "", "precision": 0,

         "delta_color": "off", "help": "Lãi tồn 2-3 tháng, cần đôn đốc ngay"},

        {"label": "Lãi tồn KHĐ", "value": tong_lai_khd, "icon": "💰", "suffix": "đồng", "precision": 0,

         "help": "Tổng lãi tồn các món 3 tháng KHĐ"},

    ], num_columns=4)



    st.divider()



    # ── Bảng Top đơn vị cần chấn chỉnh — theo XÃ thay vì PGD ─────────────────

    if COT_TEN_XA in df_kh.columns:

        st.markdown("**📋 Tổng hợp theo Xã/Phường**")

        nhom_xa = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_XA)

        if not nhom_xa.empty:

            hien_thi_dataframe_phan_trang(

                nhom_xa,

                key="pgd_khd_nhom_xa",

                height=300,

            )



    st.markdown("**📋 Tổng hợp theo Hội đoàn thể (ĐVUT)**")

    nhom_dvut = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_DVUT)

    if not nhom_dvut.empty:

        hien_thi_dataframe_phan_trang(

            nhom_dvut,

            key="pgd_khd_nhom_dvut",

            height=220,

        )



    st.divider()



    # ── Vùng Amber — cảnh báo sớm migration ──────────────────────────────

    st.markdown("**⚠️ Danh sách sắp chuyển 03 tháng không hoạt động — Đang tồn lãi 2–3 tháng (cần đôn đốc ngay)**")

    if not df_amber.empty:

        col_amber_loc, col_amber_xuat = st.columns([2, 1])

        with col_amber_loc:

            if COT_TEN_XA in df_amber.columns:

                ds_xa = ["Tất cả"] + sorted(df_amber[COT_TEN_XA].dropna().unique().tolist())

                loc_xa_a = st.selectbox("Lọc Xã", ds_xa, key="pgd_amber_xa")

            else:

                loc_xa_a = "Tất cả"

        with col_amber_xuat:

            st.markdown("<br>", unsafe_allow_html=True)

            if COT_TEN_XA in df_amber.columns and loc_xa_a != "Tất cả":

                df_amber_loc = df_amber[df_amber[COT_TEN_XA] == loc_xa_a]

            else:

                df_amber_loc = df_amber

            buf_a = xuat_excel({"SapChuyen3mKHD": df_amber_loc})

            st.download_button(

                f"⬇️ Xuất Excel Amber ({len(df_amber_loc)} món)",

                data=buf_a,

                file_name=f"SapChuyen3mKHD_{pgd_user or 'PGD'}_{datetime.now().strftime('%Y%m%d')}.xlsx",

                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

                key="pgd_cb_xuat_amber",

            )

        cols_hien = [c for c in [

            COT_TEN_XA, COT_DVUT, COT_TEN_KH,

            COT_SO_KU, COT_TEN_CT, COT_LAI_TON, COT_LAI_THANG,

            "so_thang_ton_uoc", "muc_canh_bao",

        ] if c in df_amber_loc.columns]

        hien_thi_dataframe_phan_trang(

            df_amber_loc[cols_hien] if cols_hien else df_amber_loc,

            key="pgd_amber_ds",

            height=320,

        )

    else:

        st.success("✅ Không có món vay nào sắp chuyển 03 tháng không hoạt động.")



    st.divider()



    # ── Xuất KL giao ban tự động ──────────────────────────────────────────

    st.markdown("**📄 Xuất Thông báo KL Giao ban (Bảng II tự động điền)**")

    templates = quet_templates(TEMPLATES_DIR)

    mau_klgb = [(t, p) for t, p in templates

                if "giao" in t.lower() or "kl" in t.lower() or "thong bao" in t.lower()]



    if not mau_klgb:

        st.info("⚠️ Chưa có mẫu KL giao ban trong thư mục `templates/`. "

                "Đặt file `.docx` vào thư mục đó và reload.")

    else:

        col_xa_kl, col_mau_kl = st.columns(2)

        with col_xa_kl:

            if COT_TEN_XA in df_kh.columns:

                ds_xa_kl = sorted(df_kh[COT_TEN_XA].dropna().unique().tolist())

                xa_kl = st.selectbox("Chọn Xã", ["Toàn PGD"] + ds_xa_kl, key="pgd_kl_xa")

            else:

                xa_kl = "Toàn PGD"

        with col_mau_kl:

            ten_mau_kl = st.selectbox(

                "Mẫu biểu", [t[0] for t in mau_klgb], key="pgd_kl_mau")



        if st.button("🖨️ Tạo KL giao ban", type="primary", key="pgd_kl_btn"):

            try:

                if COT_TEN_XA in df_kh.columns and xa_kl != "Toàn PGD":

                    df_kl = df_kh[df_kh[COT_TEN_XA] == xa_kl]

                else:

                    df_kl = df_kh

                idx_mau = [t[0] for t in mau_klgb].index(ten_mau_kl)

                path_mau = mau_klgb[idx_mau][1]

                data = auto_fill_klgb(df_kl, str(path_mau), pgd_user or "")

                fname = f"KL_GiaoBan_{pgd_user or 'PGD'}_{xa_kl.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y')}.docx"

                state = SCMStateManager()

                state.downloads.set("pgd_kl_giao_ban_docx", data, fname)

                st.success("✅ Đã tạo xong — nhấn nút bên dưới để tải về.")

            except Exception as e:

                logger.error("Lỗi tạo KL giao ban PGD: %s", e, exc_info=True)

                st.error(f"Lỗi tạo KL giao ban: {e}")



        state = SCMStateManager()

        if state.downloads.has("pgd_kl_giao_ban_docx"):

            fname = state.downloads.get_filename("pgd_kl_giao_ban_docx") or "KL_GiaoBan.docx"

            if st.download_button(

                f"⬇️ Tải KL giao ban — {fname}",

                data=state.downloads.get_bytes("pgd_kl_giao_ban_docx"),

                file_name=fname,

                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",

                key="pgd_kl_dl",

            ):

                state.downloads.clear("pgd_kl_giao_ban_docx")





def _render_canh_bao_nqh_pgd(tab, **kwargs) -> None:

    """Cảnh báo Tín dụng cho phân hệ PGD."""

    _lazy_tab("tab_canh_bao_nqh").render(tab, **kwargs)





def _banner_canh_bao_khd(df_pgd: pd.DataFrame, role: str) -> None:

    if df_pgd is None or df_pgd.empty:

        return

    df_kh = danh_dau_khong_hd_cached(df_pgd)

    n_khd = int(df_kh["is_3m_inactive"].sum()) if "is_3m_inactive" in df_kh.columns else 0

    if n_khd == 0:

        return

    du_no_khd = 0.0

    if COT_TONG_DU_NO in df_kh.columns and "is_3m_inactive" in df_kh.columns:

        du_no_khd = pd.to_numeric(

            df_kh.loc[df_kh["is_3m_inactive"], COT_TONG_DU_NO], errors="coerce"

        ).sum() / 1e6

    st.warning(

        f"⚠️ **{fmt_so(n_khd)} món vay 3 tháng không hoạt động** · "

        f"Dư nợ: **{du_no_khd:,.0f} triệu đồng** · "

        f"Vào nhóm **🔍 Kiểm soát & Rủi ro → Tab Đôn đốc KHĐ** để xem chi tiết.",

        icon="🔴",

    )





# ═══════════════════════════════════════════════════════════════════════════════

# KIỂM SOÁT NỘI BỘ PGD — Checklist 7 điểm tự kiểm tra trước khi báo cáo CN

# ═══════════════════════════════════════════════════════════════════════════════



def _render_kiem_soat_noi_bo_pgd(df_pgd: pd.DataFrame, pgd_user: str, role: str) -> None:

    """

    Checklist 7 điểm kiểm soát nội bộ cho CBTD địa bàn PGD.

    Mỗi điểm: Pass/Fail + số liệu thực tế + nút nhảy tới tab xử lý.

    """

    st.subheader("✅ Kiểm soát Nội bộ PGD")

    st.caption(

        f"CBTD tự kiểm tra trước khi báo cáo — "

        f"**{pgd_user or 'PGD'}** · {date.today().strftime('%d/%m/%Y')}"

    )



    if df_pgd is None or df_pgd.empty:

        st.warning("⚠️ Chưa có dữ liệu HSTD.")

        return



    # ── Tính các chỉ số ──────────────────────────────────────────────────────

    tdn = (pd.to_numeric(df_pgd[COT_TONG_DU_NO], errors="coerce").sum()
           if COT_TONG_DU_NO in df_pgd.columns else 0.0)

    dqh = (pd.to_numeric(df_pgd[COT_DU_NO_QH], errors="coerce").sum()
           if COT_DU_NO_QH in df_pgd.columns else 0.0)

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



    from dateutil.relativedelta import relativedelta

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



    # ── Danh sách điểm kiểm soát ─────────────────────────────────────────────

    # (id, tiêu_đề, pass_bool, mô_tả, nhóm_nav, tab_idx)

    items = [

        (

            "nqh",

            "Tỷ lệ NQH < 1%",

            tlqh < _NGUONG_AN_TOAN_PGD,

            f"NQH hiện tại: **{tlqh:.3f}%**",

            "kiem_soat_rr", 0,

        ),

        (

            "khd",

            "3 tháng KHĐ < 5% tổng hồ sơ",

            tl_khd < 5.0,

            f"3m KHĐ: **{n_khd} món** ({tl_khd:.1f}%)",

            "kiem_soat_rr", 1,

        ),

        (

            "amber",

            "Không có khoản sắp chuyển 3m KHĐ",

            n_amber == 0,

            f"Sắp chuyển: **{n_amber} món** (lãi tồn 2–3 tháng)",

            "kiem_soat_rr", 3,

        ),

        (

            "lai",

            "Không có lãi tồn",

            n_co_lai_ton == 0,

            f"Lãi tồn > 0: **{n_co_lai_ton} hồ sơ**",

            "kiem_soat_rr", 0,

        ),

        (

            "sdt",

            "Hồ sơ đủ số điện thoại",

            n_thieu_sdt == 0,

            f"Thiếu SĐT: **{n_thieu_sdt} hồ sơ**",

            "nghiep_vu_pgd", 2,

        ),

        (

            "daohantoi",

            f"Đã nắm hồ sơ đến hạn tháng {thang_toi.month}/{thang_toi.year}",

            n_dh_thang_toi > 0,

            f"Đến hạn tháng tới: **{n_dh_thang_toi} món**",

            "nghiep_vu_pgd", 4,

        ),

        (

            "khtd",

            "Tiến độ KHTD ≥ 95%",

            (pct_khtd or 0) >= 95,

            f"KHTD: **{pct_khtd:.1f}%**" if pct_khtd is not None else "KHTD: **Chưa có kế hoạch**",

            "ke_hoach_pgd", 0,

        ),

    ]



    n_pass = sum(1 for _, _, ok, _, _, _ in items if ok)

    n_fail = len(items) - n_pass



    # ── Header tổng kết ───────────────────────────────────────────────────────

    c_ok, c_fail, c_pct = st.columns(3)

    c_ok.metric("✅ Đạt", n_pass, help="Số tiêu chí đạt yêu cầu")

    c_fail.metric("🔴 Cần xử lý", n_fail, help="Số tiêu chí cần hành động")

    c_pct.metric(

        "Điểm kiểm soát",

        f"{n_pass}/{len(items)}",

        delta=f"{n_pass/len(items)*100:.0f}%",

        delta_color="normal" if n_fail == 0 else "inverse",

    )



    if n_fail == 0:

        st.success("🎉 Tất cả tiêu chí đạt — sẵn sàng báo cáo lên Chi nhánh!")

    else:

        st.warning(f"⚠️ Còn **{n_fail} tiêu chí** cần xử lý trước khi báo cáo.")



    st.divider()



    # ── Bảng checklist ────────────────────────────────────────────────────────

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

            if not ok:

                st.markdown("<br>", unsafe_allow_html=True)

                if st.button("→ Xử lý", key=f"ksnb_{item_id}_btn", use_container_width=True):

                    _st = SCMStateManager()

                    _st.nav_ws_op_nhom = nhom_nav

                    _st.nav_ws_op_jump_tab = tab_idx

                    st.rerun()



    st.divider()



    # ── Xuất báo cáo kiểm soát ────────────────────────────────────────────────

    with st.expander("📄 Xuất Phiếu Kiểm soát Nội bộ (Excel)"):

        rows = []

        for _, tieu_de, ok, mo_ta, _, _ in items:

            rows.append({

                "Tiêu chí": tieu_de,

                "Kết quả": "✅ Đạt" if ok else "🔴 Cần xử lý",

                "Chi tiết": mo_ta.replace("**", ""),

                "Ngày kiểm tra": date.today().strftime("%d/%m/%Y"),

                "PGD": pgd_user or "",

            })

        df_ks = pd.DataFrame(rows)

        buf = xuat_excel({"KiemSoatNoiBo": df_ks})

        st.download_button(

            f"⬇️ Tải Phiếu Kiểm soát ({date.today().strftime('%d/%m/%Y')})",

            data=buf,

            file_name=f"KiemSoat_{pgd_user or 'PGD'}_{date.today().strftime('%Y%m%d')}.xlsx",

            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

            key=f"ksnb_{pgd_user or 'cn'}_xuat_excel",

        )





# ═══════════════════════════════════════════════════════════════════════════════

# HEATMAP RỦI RO THEO XÃ — Cho PGD (y chang ws_executive nhưng thay PGD bằng Xã)

# ═══════════════════════════════════════════════════════════════════════════════



def _heatmap_rui_ro_xa(df_pgd: pd.DataFrame, pgd_user: str) -> None:

    """

    Bảng HTML 7 cột: Xã | Dư nợ | NQH% | 3T KHĐ | Migration | Tăng trưởng | Điểm RR.

    Giống _heatmap_rui_ro_pgd() trong ws_executive nhưng so sánh các Xã thay vì PGD.

    """

    if df_pgd is None or df_pgd.empty:

        return

    if COT_TEN_XA not in df_pgd.columns:

        st.info("Không có cột Tên xã để hiển thị heatmap rủi ro.")

        return



    g = df_pgd.groupby(COT_TEN_XA)

    t = g.agg(

        du_no=(COT_TONG_DU_NO, "sum"),

        dqh=(COT_DU_NO_QH, "sum"),

        nkh=(COT_MA_KH, "nunique"),

    ).reset_index()

    t["tl_nqh"] = (t["dqh"] / t["du_no"].replace(0, float("nan")) * 100).round(3).fillna(0)



    df_k = danh_dau_khong_hd_cached(df_pgd)

    khd = df_k[df_k["is_3m_inactive"]].groupby(COT_TEN_XA).size().reset_index(name="khd")

    t = t.merge(khd, on=COT_TEN_XA, how="left")

    t["khd"] = t["khd"].fillna(0).astype(int)



    df_mg = canh_bao_migration_cached(df_pgd)

    mg = (

        df_mg.groupby(COT_TEN_XA).size().reset_index(name="mg")

        if not df_mg.empty

        else pd.DataFrame(columns=[COT_TEN_XA, "mg"])

    )

    t = t.merge(mg, on=COT_TEN_XA, how="left")

    t["mg"] = t["mg"].fillna(0).astype(int)



    # Tăng trưởng: so sánh với snapshot (nếu có)

    t["tt"] = None

    try:

        from snapshot_service import doc_snapshot, danh_sach_ky

        ds_ky = danh_sach_ky()

        if len(ds_ky) >= 2:

            _df_prev = doc_snapshot(ds_ky[1])

            if _df_prev is not None and not _df_prev.empty:

                # Lọc snapshot theo PGD hiện tại

                if pgd_user and COT_TEN_PGD in _df_prev.columns:

                    _df_prev = _df_prev[_df_prev[COT_TEN_PGD] == pgd_user]

                prev_map = _df_prev.set_index("ten_xa")["tong_du_no"].to_dict() if "ten_xa" in _df_prev.columns else {}

                if prev_map:

                    t["tt"] = t.apply(

                        lambda r: (r["du_no"] - prev_map.get(r[COT_TEN_XA], r["du_no"])) / 1e6,

                        axis=1,

                    )

    except Exception as e:

        logger.error("_heatmap_rui_ro_xa snapshot: %s", e, exc_info=True)



    t["rr"] = (

        t["tl_nqh"] * 3

        + t["khd"] / t["nkh"].replace(0, 1) * 100

        + t["mg"] / t["nkh"].replace(0, 1) * 100

    ).round(1)

    t = t.sort_values("rr", ascending=False).reset_index(drop=True)



    BD = "#2A2D3E"; H = "#1B5E20"; W = "#1E2130"; A = "#161922"; TX = "#E0E6ED"

    R = "#EF9A9A"; AM = "#FFCC80"; G = "#A5D6A7"; GR = "#94A3B8"



    def td(v, al="right", c="", bg="", fw=""):

        s = f"text-align:{al};padding:5px 8px;border:1px solid {BD};font-size:0.8rem;white-space:nowrap;color:{TX}"

        if c:

            s += f";color:{c}"

        if bg:

            s += f";background:{bg}"

        if fw:

            s += f";font-weight:{fw}"

        return f"<td style='{s}'>{v}</td>"



    def nc(tl): return R if tl >= 2 else (AM if tl >= 0.5 else G)



    hdrs = ["#", "Xã/Phường", "Dư nợ (triệu đồng)", "NQH%", "3T KHĐ", "Migration", "Tăng trưởng", "Điểm RR"]

    thead = "".join(

        f'<th style="background:{H};color:#fff;text-align:{"center" if i==0 else "left" if i==1 else "right"};padding:6px 8px;border:1px solid {BD};font-size:0.8rem">{h}</th>'

        for i, h in enumerate(hdrs)

    )

    rows_h = []

    for i, row in t.iterrows():

        bg = W if i % 2 == 0 else A

        tl = row["tl_nqh"]

        tt_s = "—"

        if row["tt"] is not None:

            col = G if row["tt"] >= 0 else R

            tt_vn = f"{abs(row['tt']):,.0f}".replace(",","X").replace(".",",").replace("X",".")

            tt_s = f'<span style="color:{col}">{"+" if row["tt"] >= 0 else "-"}{tt_vn}</span>'

        rows_h.append(

            "<tr>" + "".join(

                [

                    td(str(i + 1), "center", "", bg),

                    td(row[COT_TEN_XA], "left", "", bg),

                    td(fmt_ty(row["du_no"]), bg=bg),

                    td(f"{tl:.3f}%", c=nc(tl), bg=bg, fw="bold" if tl >= 0.5 else ""),

                    td(str(row["khd"]), c=R if row["khd"] > 0 else GR, bg=bg),

                    td(str(row["mg"]), c=AM if row["mg"] > 0 else GR, bg=bg),

                    td(tt_s, bg=bg),

                    td(f"{row['rr']:.1f}", c=R if row["rr"] >= 5 else (AM if row["rr"] >= 2 else G), bg=bg, fw="bold"),

                ]

            ) + "</tr>"

        )



    st.markdown(

        f"""

<div style="overflow-x:auto;margin:8px 0">

<table style="border-collapse:collapse;width:100%;font-family:'Inter','Segoe UI',sans-serif">

  <thead><tr>{thead}</tr></thead>

  <tbody>{"" .join(rows_h)}</tbody>

</table>

<p style="font-size:0.75rem;color:#94A3B8;margin:4px 0 0">

NQH%: <span style="color:{G}">■</span>&lt;0.5% &nbsp;

<span style="color:{AM}">■</span>0.5–2% &nbsp;

<span style="color:{R}">■</span>≥2% &nbsp;·&nbsp;

Điểm RR = NQH%×3 + KHĐ/KH% + Mg/KH%

</p></div>""",

        unsafe_allow_html=True,

    )





def _render_dashboard_nang_cao_pgd(tab_parent, df_pgd: pd.DataFrame, pgd_user: str, role: str):

    """

    Dashboard nâng cao cho PGD — Giống ws_executive._the_suc_khoe() nhưng cho 1 PGD:

    - Gauge NQH

    - Heatmap rủi ro theo Xã

    """

    with tab_parent:

        st.subheader("📊 Dashboard Sức Khỏe Tín Dụng")

        st.caption(f"Phạm vi: **{pgd_user or 'PGD'}** — Đánh giá rủi ro theo các xã/phường")



        if df_pgd is None or df_pgd.empty:

            st.warning("⚠️ Chưa có dữ liệu HSTD để hiển thị dashboard.")

            return



        # Tính chỉ số

        tdn = df_pgd[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_pgd.columns else 0

        dth = pd.to_numeric(df_pgd[COT_DU_NO_TH], errors="coerce").sum() if COT_DU_NO_TH in df_pgd.columns else 0

        dqh = df_pgd[COT_DU_NO_QH].sum() if COT_DU_NO_QH in df_pgd.columns else 0

        tlqh = dqh / tdn * 100 if tdn > 0 else 0.0

        n_hs = len(df_pgd)

        n_kh = df_pgd[COT_MA_KH].nunique() if COT_MA_KH in df_pgd.columns else 0



        mau, tinh_trang, icon = _mau_nqh_pgd(tlqh)



        col_gauge, col_kpi = st.columns([2, 3], gap="large")



        with col_gauge:

            st.plotly_chart(_gauge_nqh_pgd(tlqh, pgd_user or "PGD"), use_container_width=True)



        with col_kpi:

            st.markdown(f"### {icon} Chỉ số Tín dụng {pgd_user or 'PGD'}")

            kpi_row([

                {"label": "Tổng dư nợ", "value": fmt_ty(tdn), "icon": "💰", "suffix": "triệu đ", "precision": 0,

                 "help": f"Tổng dư nợ {pgd_user or 'PGD'}"},

                {"label": "Dư nợ trong hạn", "value": fmt_ty(dth), "icon": "✅", "suffix": "triệu đ", "precision": 0,

                 "help": "Dư nợ chưa đến hạn thanh toán"},

                {"label": "Nợ quá hạn", "value": fmt_ty(dqh), "icon": "⚠️", "suffix": "triệu đ", "precision": 0,

                 "delta": tlqh, "delta_label": "% NQH", "delta_color": "inverse" if tlqh >= 1 else "normal",

                 "help": f"{tinh_trang}" if dqh > 0 else "✅ Không có NQH"},

                {"label": "Số khách hàng", "value": fmt_so(n_kh), "icon": "👥", "suffix": "", "precision": 0,

                 "help": f"Tổng {fmt_so(n_hs)} hồ sơ"},

            ], num_columns=4)



            st.markdown("---")

            pct_th = dth / tdn * 100 if tdn > 0 else 100

            st.markdown(

                f"**Tỷ lệ Dư nợ trong hạn:** "

                f"<span style='color:#90CAF9;font-weight:bold'>{pct_th:.1f}%</span> "

                f"&nbsp;|&nbsp; **NQH:** "

                f"<span style='color:{mau};font-weight:bold'>{tlqh:.3f}%</span>",

                unsafe_allow_html=True,

            )

            st.progress(

                min(pct_th / 100, 1.0),

                text=f"Sức khỏe: {pct_th:.1f}% dư nợ đang trong hạn",

            )



        st.divider()



        # Heatmap rủi ro theo Xã

        st.markdown("### 🔥 Heatmap Rủi ro theo Xã/Phường")

        st.caption("Điểm RR (Risk Rating) = NQH%×3 + KHĐ/KH% + Mg/KH% · Cao = Rủi ro lớn")

        _heatmap_rui_ro_xa(df_pgd, pgd_user)





# ═══════════════════════════════════════════════════════════════════════════════

# KIỂM SOÁT NỘI BỘ — Phiên bản rút gọn cho PGD (chỉ xem, không chỉnh sửa)

# ═══════════════════════════════════════════════════════════════════════════════



def _render_kiem_soat_pgd(tab_parent, df_pgd: pd.DataFrame, pgd_user: str, role: str, username: str):

    """

    Kiểm soát nội bộ cho PGD — Phiên bản rút gọn chỉ xem dữ liệu 1 PGD.

    Giống tab_kiem_soat.render_tab() nhưng không có filter PGD và chỉ đọc.

    """

    with tab_parent:

        st.subheader("🔍 Kiểm soát Nội bộ PGD")

        st.caption(f"Phạm vi: **{pgd_user or 'PGD'}** — Chế độ chỉ xem")



        if df_pgd is None or df_pgd.empty:

            st.warning("Chưa có dữ liệu HSTD.")

            return



        # Cache key cho PGD

        cache_key = (pgd_user or "", len(df_pgd))

        ks_pgd_key = f"ks_pgd_cache_{pgd_user or 'all'}"

        ks = st.session_state.get(ks_pgd_key, {})



        if ks.get("_key") != cache_key:

            with st.spinner("Đang phân tích dữ liệu PGD..."):

                df_kh = danh_dau_khong_hd_cached(df_pgd)



                # Tổng hợp 3 tháng KHĐ theo Xã

                df_khd_xa = tong_hop_khong_hd_cached(df_kh, nhom_theo=COT_TEN_XA) if COT_TEN_XA in df_kh.columns else pd.DataFrame()



                # Chi tiết 3 tháng KHĐ

                df_khd_chi = ds_chi_tiet_khong_hd(df_kh)



                # NQH theo Xã

                if COT_DU_NO_QH in df_kh.columns and COT_TEN_XA in df_kh.columns:

                    df_nqh_xa = df_kh[df_kh[COT_DU_NO_QH] > 0].groupby(COT_TEN_XA).agg({

                        COT_SO_KU: "count",

                        COT_DU_NO_QH: "sum",

                        COT_TONG_DU_NO: "sum"

                    }).reset_index()

                    if not df_nqh_xa.empty:

                        df_nqh_xa["Tỷ_lệ_QH_%"] = (df_nqh_xa[COT_DU_NO_QH] / df_nqh_xa[COT_TONG_DU_NO].replace(0, pd.NA) * 100).round(1).fillna(0)

                else:

                    df_nqh_xa = pd.DataFrame()



                # Chi tiết NQH

                mask_nqh = df_kh[COT_DU_NO_QH] > 0 if COT_DU_NO_QH in df_kh.columns else pd.Series([False] * len(df_kh))

                cols_nqh = [c for c in [COT_TEN_XA, COT_TEN_KH, COT_SO_KU, COT_TEN_CT, COT_DU_NO_QH, COT_TONG_DU_NO, COT_NGAY_DH] if c in df_kh.columns]

                df_nqh_chi = df_kh[mask_nqh][cols_nqh] if cols_nqh else pd.DataFrame()



                ks = {

                    "_key": cache_key,

                    "df_kh": df_kh,

                    "df_khd_xa": df_khd_xa,

                    "df_khd_chi": df_khd_chi,

                    "df_nqh_xa": df_nqh_xa,

                    "df_nqh_chi": df_nqh_chi,

                }

                st.session_state[ks_pgd_key] = ks



        # Hiển thị theo tab

        tab_3mkhd, tab_nqh = st.tabs(["📋 3 tháng KHĐ", "⚠️ Nợ Quá Hạn"])



        with tab_3mkhd:

            st.markdown("**📊 Tổng hợp theo Xã**")

            if not ks["df_khd_xa"].empty:

                hien_thi_dataframe_phan_trang(ks["df_khd_xa"], key="pgd_ks_khd_xa", height=280)

            else:

                st.info("Không có dữ liệu 3 tháng KHĐ theo xã.")



            st.divider()

            st.markdown("**📋 Chi tiết**")

            if not ks["df_khd_chi"].empty:

                hien_thi_dataframe_phan_trang(ks["df_khd_chi"], key="pgd_ks_khd_chi", height=320)

            else:

                st.success("✅ Không có món vay 3 tháng không hoạt động.")



        with tab_nqh:

            st.markdown("**📊 Tổng hợp theo Xã**")

            if not ks["df_nqh_xa"].empty:

                hien_thi_dataframe_phan_trang(ks["df_nqh_xa"], key="pgd_ks_nqh_xa", height=280)

            else:

                st.info("Không có dữ liệu NQH theo xã.")



            st.divider()

            st.markdown("**📋 Chi tiết**")

            if not ks["df_nqh_chi"].empty:

                hien_thi_dataframe_phan_trang(ks["df_nqh_chi"], key="pgd_ks_nqh_chi", height=320)

            else:

                st.success("✅ Không có nợ quá hạn.")



        # Xuất Excel tổng hợp

        st.divider()

        col_x1, col_x2 = st.columns(2)

        with col_x1:

            if not ks["df_khd_xa"].empty:

                buf_khd = xuat_excel({"3m_KHD_theo_Xa": ks["df_khd_xa"], "Chi_tiet_3m_KHD": ks["df_khd_chi"]})

                st.download_button(

                    "⬇️ Xuất Excel 3 tháng KHĐ",

                    data=buf_khd,

                    file_name=f"KiemSoat_3mKHD_{pgd_user or 'PGD'}_{datetime.now().strftime('%Y%m%d')}.xlsx",

                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

                    key="pgd_ks_xuat_khd",

                )

        with col_x2:

            if not ks["df_nqh_xa"].empty:

                buf_nqh = xuat_excel({"NQH_theo_Xa": ks["df_nqh_xa"], "Chi_tiet_NQH": ks["df_nqh_chi"]})

                st.download_button(

                    "⬇️ Xuất Excel NQH",

                    data=buf_nqh,

                    file_name=f"KiemSoat_NQH_{pgd_user or 'PGD'}_{datetime.now().strftime('%Y%m%d')}.xlsx",

                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

                    key="pgd_ks_xuat_nqh",

                )





def _render_doc_hub(df: pd.DataFrame, df_nq11, role: str):

    """Module Trung tâm Tự động hóa Văn bản."""

    st.subheader("📄 Trung tâm Tự động hóa Văn bản")

    st.caption("Chọn hồ sơ → Chọn mẫu biểu → Tải về bản hoàn thiện tự động")



    templates = quet_templates(TEMPLATES_DIR)

    if not templates:

        st.warning(f"⚠️ Chưa có file mẫu nào trong thư mục `templates/`")

        st.info(

            "**Cách thêm mẫu biểu:**\n"

            f"1. Tạo file Word `.docx` với các tag như `{{{{ten_kh}}}}`, `{{{{so_ku}}}}` ...\n"

            f"2. Copy vào thư mục: `{TEMPLATES_DIR}`\n"

            "3. Reload trang là xuất hiện trong danh sách\n\n"

            "**Các tag hỗ trợ sẵn:**\n"

            + "\n".join(f"- `{tag}` → cột *{col}*" for tag, col in TAG_MAP.items())

        )

        return



    st.success(f"✅ Có **{len(templates)}** mẫu biểu sẵn sàng")



    st.markdown("**① Chọn đối tượng**")

    doi_tuong = st.radio(

        "Chọn đối tượng xuất văn bản",

        ["Từng hồ sơ khách hàng", "Theo Xã/Phường (xuất hàng loạt)"],

        horizontal=True, key="op_dh_doi_tuong", label_visibility="collapsed",

    )



    df_chon = None



    if doi_tuong == "Từng hồ sơ khách hàng":

        kw = st.text_input("🔍 Tìm khách hàng",

                           placeholder="Tên KH hoặc Số khế ước...", key="op_dh_kw")

        if kw:

            mask = (df[[c for c in [COT_TEN_KH, COT_SO_KU, COT_MA_KH] if c in df.columns]]
                    .astype(str).apply(lambda c: c.str.contains(kw, case=False, na=False)).any(axis=1))

            df_tim = df[mask]

            if df_tim.empty:

                st.warning("Không tìm thấy.")

            else:

                opts = ((df_tim[COT_TEN_KH].astype(str) + "  —  " +
                         df_tim[COT_SO_KU].astype(str)) if COT_SO_KU in df_tim.columns
                        else df_tim[COT_TEN_KH].astype(str))

                chon = st.multiselect("Chọn hồ sơ (có thể chọn nhiều)",

                                      opts.tolist(), key="op_dh_hs_sel")

                if chon:

                    idx_list = [opts.tolist().index(c) for c in chon]

                    df_chon  = df_tim.iloc[idx_list].reset_index(drop=True)

                    st.info(f"Đã chọn **{len(df_chon)}** hồ sơ")

    else:

        COT_XA = COT_TEN_XA

        if COT_XA in df.columns:

            ds_xa   = sorted(df[COT_XA].dropna().unique().tolist())

            chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="op_dh_xa")

            df_chon = df[df[COT_XA] == chon_xa].copy()

            st.info(f"Xã **{chon_xa}**: **{len(df_chon)}** hồ sơ")

        else:

            st.warning("Không tìm thấy cột Tên xã trong dữ liệu.")



    if df_chon is None or len(df_chon) == 0:

        st.info("👆 Chọn hồ sơ hoặc xã/phường để tiếp tục.")

        return



    st.markdown("**② Chọn mẫu biểu**")

    ten_mau_list  = [t[0] for t in templates]

    path_mau_list = [t[1] for t in templates]

    chon_mau_list = st.multiselect("Chọn 1 hoặc nhiều mẫu biểu",

                                   ten_mau_list, key="op_dh_mau_sel")



    with st.expander("📋 Xem tất cả mẫu biểu & tag hỗ trợ"):

        for ten, path in templates:

            st.markdown(f"**📄 {ten}**  `{path.name}`")

        st.markdown(

            "**📋 Biên bản giao ban xã** — `BB_giao_ban_xa_template.docx` "

            "(xuất Word tại sub-tab **📋 Biên bản giao ban**)."

        )

        st.divider()

        st.markdown("**Tag hỗ trợ trong file Word:**")

        for tag, col in TAG_MAP.items():

            st.caption(f"`{tag}` → {col}")



    if not chon_mau_list:

        st.info("👆 Chọn ít nhất 1 mẫu biểu.")

        return



    st.markdown("**③ Xuất văn bản**")

    che_do_xuat = st.radio(

        "Chế độ xuất",

        ["Mỗi hồ sơ 1 file riêng", "Gộp tất cả vào 1 file (hàng loạt)"],

        horizontal=True, key="op_dh_xuat_mode",

    ) if len(df_chon) > 1 else "Mỗi hồ sơ 1 file riêng"



    dh_ss_key = "_dh_docx_hub"

    if st.button("🖨️ Tạo văn bản", type="primary", key="dh_btn_xuat"):

        results = []

        for ten_mau in chon_mau_list:

            idx_mau  = ten_mau_list.index(ten_mau)

            path_mau = path_mau_list[idx_mau]

            if not path_mau.exists():

                st.error(f"Không tìm thấy file: {path_mau}"); continue

            try:

                if che_do_xuat == "Mỗi hồ sơ 1 file riêng":

                    for i, (_, row) in enumerate(df_chon.iterrows()):

                        ten_kh = str(row.get(COT_TEN_KH, f"hs_{i+1}"))

                        fname  = f"{path_mau.stem}_{ten_kh}_{datetime.today().strftime('%d%m%Y')}.docx"

                        data   = auto_fill_document(row, str(path_mau), TAG_MAP)

                        results.append((f"{ten_mau} — {ten_kh}", data, fname, f"dl_{ten_mau}_{i}"))

                else:

                    fname = f"{path_mau.stem}_batch_{datetime.today().strftime('%d%m%Y')}.docx"

                    data  = auto_fill_batch(df_chon, str(path_mau), TAG_MAP)

                    results.append((f"⬇ {ten_mau} — {len(df_chon)} hồ sơ (gộp)", data, fname, f"dl_batch_{ten_mau}"))

                st.success(f"✅ Đã tạo: **{ten_mau}**")

            except Exception as e:  # conv: skip

                logger.error("Lỗi trong khối except: %s", e, exc_info=True)

                st.error(f"Lỗi tạo {ten_mau}: {e}")

        st.session_state[dh_ss_key] = results



    if st.session_state.get(dh_ss_key):

        for label, data, fname, key in st.session_state[dh_ss_key]:

            st.download_button(

                f"⬇ {label}", data=data, file_name=fname,

                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",

                key=key,

            )





def _init_gb2_session_for_doc_hub(kwargs: dict) -> None:

    """

    Khởi tạo st.session_state gb2_xa / gb2_nam để tab Thông báo KL

    dùng chung lựa chọn với tab Biên bản (cùng key widget).

    """

    from config import (

        danh_sach_nam_baseline,

        danh_sach_nam_baseline_pgd,

    )



    df = kwargs.get("df")

    role = kwargs.get("role")

    pgd_user = kwargs.get("pgd_user")

    if df is None or df.empty:

        return

    if is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:

        df = df[df[COT_TEN_PGD] == pgd_user].copy()

    if COT_TEN_XA not in df.columns:

        return

    ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())

    if not ds_xa:

        return

    if "gb2_xa" not in st.session_state or st.session_state.gb2_xa not in ds_xa:

        st.session_state.gb2_xa = ds_xa[0]

    ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()

    if ds_nam and (

        "gb2_nam" not in st.session_state or st.session_state.gb2_nam not in ds_nam

    ):

        st.session_state.gb2_nam = ds_nam[0]





def _render_thong_bao_ket_luan(tab, **kwargs):

    """Tab xuất Thông báo Kết luận giao ban (NĐ30) — dùng gb2_xa / gb2_nam từ tab Biên bản."""

    from config import (

        danh_sach_nam_baseline,

        danh_sach_nam_baseline_pgd,

        baseline_pgd_path,

        DON_VI_CHI_NHANH,

    )

    from data.hstd import doc_baseline_merged

    from data.giao_ban import xuat_thong_bao_ket_luan_giao_ban



    ctx = tab if tab is not None else st

    df = kwargs.get("df")

    pgd_user = kwargs.get("pgd_user")

    role = kwargs.get("role")



    with ctx:

        st.subheader("📢 Thông báo Kết luận Giao ban")

        st.caption(

            "Xuất Thông báo kết luận họp giao ban tháng "

            "tại điểm giao dịch — chuẩn thể thức NĐ30/2020"

        )



        if df is None or df.empty:

            st.warning("⚠️ Chưa có dữ liệu HSTD.")

            return

        if is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:

            df = df[df[COT_TEN_PGD] == pgd_user].copy()



        ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())

        if not ds_xa:

            st.warning("Không có cột Tên xã.")

            return



        default_xa = st.session_state.get("gb2_xa", ds_xa[0] if ds_xa else None)

        if default_xa not in ds_xa:

            default_xa = ds_xa[0] if ds_xa else None

        chon_xa = st.selectbox(

            "Chọn xã / điểm giao dịch",

            ds_xa,

            index=ds_xa.index(default_xa) if default_xa in ds_xa else 0,

            key="op_tb_chon_xa",

        )

        st.session_state["gb2_xa"] = chon_xa



        ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()

        chon_nam = st.session_state.get("gb2_nam")

        if ds_nam and chon_nam not in ds_nam:

            chon_nam = ds_nam[0]

        df_bl = None

        if ds_nam and chon_nam is not None:

            fp_check = baseline_pgd_path(

                DON_VI_CHI_NHANH if not pgd_user else pgd_user, chon_nam

            )

            _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0

            df_bl = doc_baseline_merged(chon_nam, _ts=_ts)



        col_a, col_b = st.columns(2)

        with col_a:

            tb_dgd = st.text_input(

                "Tên điểm giao dịch",

                value=chon_xa,

                key="op_tb_ten_dgd",

                help="Mặc định là tên xã, chỉnh lại nếu khác",

            )

            tb_ngay = st.date_input("Ngày họp", value=date.today(), format="DD/MM/YYYY", key="op_tb_ngay_hop")

        with col_b:

            tb_so_vb = st.text_input(

                "Số văn bản",

                placeholder="VD: 05",

                key="op_tb_so_van_ban",

                help="Phần số trong 'Số: .../TB-KLGB'",

            )

            tb_ten_ky = st.text_input(

                "Tên người ký",

                placeholder="VD: Nguyễn Văn A",

                key="op_tb_ten_nguoi_ky",

                help="Tên Phó Giám đốc ký văn bản",

            )



        # Preview số liệu tự động

        from config import COT_LAI_TON_QH, COT_SO_DU_TG

        df_xa_preview = df[df[COT_TEN_XA] == chon_xa].copy()

        if not df_xa_preview.empty:

            dn_prev = pd.to_numeric(df_xa_preview[COT_TONG_DU_NO], errors="coerce").sum() / 1e6

            nqh_prev = pd.to_numeric(df_xa_preview[COT_DU_NO_QH], errors="coerce").sum() / 1e6

            lai_prev = (

                pd.to_numeric(df_xa_preview.get(COT_LAI_TON, 0), errors="coerce").sum()

                + pd.to_numeric(df_xa_preview.get(COT_LAI_TON_QH, 0), errors="coerce").sum()

            ) / 1e6

            tg_prev = pd.to_numeric(df_xa_preview.get(COT_SO_DU_TG, 0), errors="coerce").sum() / 1e6

            st.info(

                f"📊 **Số liệu tự động — {chon_xa}**\n\n"

                f"Dư nợ: **{fmt(dn_prev * 1e6)}** triệu · "

                f"NQH: **{fmt(nqh_prev * 1e6)}** triệu · "

                f"Lãi tồn: **{fmt(lai_prev * 1e6)}** triệu · "

                f"Tiền gửi TK: **{fmt(tg_prev * 1e6)}** triệu"

            )



        # Giải ngân kế hoạch tháng tới

        from dateutil.relativedelta import relativedelta

        from config import COT_TEN_TO

        thang_toi = date.today() + relativedelta(months=1)

        ngay_dh_col = "Ngày ĐH theo Gia hạn" if "Ngày ĐH theo Gia hạn" in df_xa_preview.columns else COT_NGAY_DH

        mask_dh = (

            pd.to_datetime(df_xa_preview[ngay_dh_col], errors="coerce").dt.month == thang_toi.month

        ) & (

            pd.to_datetime(df_xa_preview[ngay_dh_col], errors="coerce").dt.year == thang_toi.year

        )

        df_dh_prev = df_xa_preview[mask_dh].copy()

        giai_ngan_input = {}

        with st.expander("💰 Nhập số giải ngân dự kiến tháng tới (tùy chọn)"):

            st.caption("Để trống nếu chưa xác định. Nhập theo đơn vị triệu đồng.")

            if not df_dh_prev.empty and COT_TEN_TO in df_dh_prev.columns:

                for (dvut, to, ct), grp in df_dh_prev.groupby([COT_DVUT, COT_TEN_TO, COT_TEN_CT]):

                    val = st.number_input(

                        f"{to} — {ct}",

                        min_value=0.0,

                        value=0.0,

                        step=1.0,

                        format="%.0f",

                        key=f"op_gn_{dvut}_{to}_{ct}",

                        help="Triệu đồng",

                    )

                    if val > 0:

                        giai_ngan_input[(dvut, to, ct)] = val * 1e6

            else:

                st.caption("Không có món đến hạn tháng tới hoặc chưa có dữ liệu.")

                giai_ngan_input = None



        tb_cs = st.text_area(

            "I. Chính sách mới trong tháng",

            placeholder="Để trống nếu không có chính sách mới...",

            height=100,

            key="op_tb_chinh_sach",

        )

        tb_tt = st.text_area(

            "II.2 Tồn tại, hạn chế",

            placeholder="Nêu cụ thể tồn tại của Hội, Tổ, khách hàng...",

            height=120,

            key="op_tb_ton_tai",

        )

        tb_nv = st.text_area(

            "III. Nhiệm vụ tháng tiếp theo",

            placeholder="Kế hoạch kiểm tra, xử lý nợ xấu, nội dung khác...",

            height=120,

            key="op_tb_nhiem_vu",

        )



        if st.button("🖨️ Xuất Thông báo Kết luận Word", type="primary", key="tb_xuat"):

            df_xa_tb = df[df[COT_TEN_XA] == chon_xa].copy()

            try:

                data = xuat_thong_bao_ket_luan_giao_ban(

                    df_xa=df_xa_tb,

                    ten_pgd=pgd_user or "",

                    ten_xa=chon_xa,

                    ten_dgd=tb_dgd or chon_xa,

                    thang_bao_cao=date.today().month,

                    nam_bao_cao=date.today().year,

                    ngay_hop=tb_ngay.strftime("%d/%m/%Y"),

                    chinh_sach_moi=tb_cs,

                    ton_tai_han_che=tb_tt,

                    nhiem_vu_tiep=tb_nv,

                    so_van_ban=tb_so_vb,

                    ten_nguoi_ky=tb_ten_ky,

                    giai_ngan_input=giai_ngan_input,

                    df_baseline=df_bl,

                    nam_moc=chon_nam or date.today().year - 1,

                )

                ten_file = (

                    f"TB_KetLuan_{chon_xa.replace(' ', '_')}"

                    f"_{date.today().strftime('%m%Y')}.docx"

                )

                st.session_state["tb_data"] = data

                st.session_state["tb_ten_file"] = ten_file

                st.success("✅ Đã tạo Thông báo Kết luận! Nhấn nút bên dưới để tải về.")



            except Exception as e:  # conv: skip

                logger.error("Lỗi trong khối except: %s", e, exc_info=True)

                st.error(f"❌ Lỗi tạo file: {e}")



        if st.session_state.get("tb_data"):

            st.download_button(

                "⬇️ Tải về Word",

                data=st.session_state["tb_data"],

                file_name=st.session_state["tb_ten_file"],

                mime="application/vnd.openxmlformats-officedocument"

                ".wordprocessingml.document",

                key="tb_dl_word",

            )



        if st.session_state.get("tb_data") and st.button("📄 Xuất PDF", type="primary", key="tb_xuat_pdf"):

            try:

                import tempfile, os

                from docx2pdf import convert

                data_pdf = st.session_state["tb_data"]

                ten_file_pdf = st.session_state["tb_ten_file"]

                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:

                    tmp.write(data_pdf)

                    tmp_path = tmp.name

                pdf_path = tmp_path.replace(".docx", ".pdf")

                convert(tmp_path, pdf_path)

                with open(pdf_path, "rb") as f:

                    pdf_bytes = f.read()

                os.unlink(tmp_path)

                os.unlink(pdf_path)

                ten_pdf = ten_file_pdf.replace(".docx", ".pdf")

                st.session_state["_tb_pdf_bytes"] = pdf_bytes

                st.session_state["_tb_pdf_file"] = ten_pdf

            except ImportError:

                st.warning("⚠️ Chưa cài docx2pdf. Chạy: pip install docx2pdf")

                st.info("💡 Mở file Word rồi chọn **Save As → PDF** thủ công.")

                st.session_state["_tb_pdf_bytes"] = None

            except Exception as _e_pdf:

                logger.error("Lỗi trong khối except: %s", _e_pdf, exc_info=True)

                st.error(f"❌ Lỗi chuyển PDF: {_e_pdf}")

                st.session_state["_tb_pdf_bytes"] = None



        if st.session_state.get("_tb_pdf_bytes"):

            st.download_button(

                "⬇️ Tải về PDF",

                data=st.session_state["_tb_pdf_bytes"],

                file_name=st.session_state.get("_tb_pdf_file", "output.pdf"),

                mime="application/pdf",

                key="tb_dl_pdf",

            )





def _render_bien_ban_giao_ban(tab, **kwargs):

    ctx = tab if tab is not None else st

    from config import (danh_sach_nam_baseline, baseline_path, TEMPLATES_DIR,

                        baseline_pgd_path, danh_sach_nam_baseline_pgd,

                        trang_thai_baseline_pgd, DON_VI_CHI_NHANH)

    from data.hstd import doc_baseline_merged

    from data.giao_ban import xuat_bien_ban_giao_ban

    from datetime import date



    df = kwargs.get("df")

    pgd_user = kwargs.get("pgd_user")

    role = kwargs.get("role")



    if df is not None and not df.empty and is_pgd_role(role) and pgd_user and COT_TEN_PGD in df.columns:

        df = df[df[COT_TEN_PGD] == pgd_user].copy()



    with ctx:

        st.subheader("📋 Biên bản họp giao ban xã")



        if df is None or df.empty:

            st.warning("Chưa có dữ liệu HSTD.")

            return



        # 1. Chọn xã thuộc PGD

        ds_xa = sorted(df[COT_TEN_XA].dropna().unique().tolist())

        chon_xa = st.selectbox("Chọn xã / điểm giao dịch", ds_xa,

                               key="op_gb2_xa")



        # 2. Chọn năm mốc so sánh — dùng doc_baseline_merged() để tổng hợp từ 22 đơn vị

        ds_nam = danh_sach_nam_baseline_pgd()

        if not ds_nam:

            ds_nam = danh_sach_nam_baseline()  # fallback năm cũ

        if not ds_nam:

            st.info("ℹ️ Chưa có dữ liệu mốc 31/12. "

                    "Vẫn xuất được — cột so sánh đầu năm sẽ trống.")

            chon_nam = None

            df_bl = None

        else:

            chon_nam = st.selectbox(

                "So sánh với mốc năm", ds_nam,

                format_func=lambda n: f"31/12/{n}",

                key="op_gb2_nam")

            # Đọc dữ liệu đã merge từ tất cả đơn vị

            fp_check = baseline_pgd_path(DON_VI_CHI_NHANH if not pgd_user else pgd_user, chon_nam)

            _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0

            df_bl = doc_baseline_merged(chon_nam, _ts=_ts)



        # 3. Nhập giải ngân (tuỳ chọn)

        with st.expander("✏️ Nhập kế hoạch giải ngân tháng tới (tuỳ chọn)"):

            st.caption("Để trống nếu chưa có kế hoạch.")

            gn_tong = st.number_input(

                "Tổng giải ngân dự kiến (triệu đồng)", min_value=0.0,

                step=1.0, key="op_gb2_gn")

            # Đơn giản: nhập 1 số tổng — code điền vào dòng Cộng

            # Nếu sau này cần chi tiết theo Tổ thì mở rộng thêm



        # 4. Xuất

        template = str(TEMPLATES_DIR / "BB_giao_ban_xa_template.docx")

        if not os.path.exists(template):

            st.error("Chưa có file template BB_giao_ban_xa_template.docx "

                     "trong thư mục templates/")

            return



        if st.button("🖨️ Xuất Biên bản Word", type="primary", key="gb2_xuat"):

            df_xa = df[df[COT_TEN_XA] == chon_xa].copy()

            gn_input = {"__tong__": gn_tong * 1_000_000} if gn_tong > 0 else None

            try:

                state = SCMStateManager()

                data = xuat_bien_ban_giao_ban(

                    df_xa=df_xa,

                    df_baseline=df_bl,

                    nam_moc=chon_nam or date.today().year - 1,

                    template_path=template,

                    giai_ngan_input=gn_input,

                )

                thang = date.today().strftime("%m%Y")

                ten_file = f"BB_GiaoBan_{chon_xa.replace(' ','_')}_{thang}.docx"

                state.downloads.set("gb2_word", data, ten_file)

                st.success("✅ Đã tạo biên bản! Nhấn nút bên dưới để tải về.")

            except Exception as e:  # conv: skip

                logger.error("Lỗi trong khối except: %s", e, exc_info=True)

                st.error(f"❌ Lỗi xuất file: {e}")

                st.exception(e)



        state = SCMStateManager()

        if state.downloads.has("gb2_word"):

            if st.download_button(

                "⬇️ Tải về Word",

                data=state.downloads.get_bytes("gb2_word"),

                file_name=state.downloads.get_filename("gb2_word"),

                mime="application/vnd.openxmlformats-officedocument"

                     ".wordprocessingml.document",

                key="gb2_dl_word",

            ):

                state.downloads.clear("gb2_word")





def _render_bao_cao_giao_ban(tab, **kwargs):

    """

    Render tab Báo cáo Giao ban - tạo báo cáo tổng hợp theo xã với bảng tóm tắt theo ĐVUT.

    """

    ctx = tab if tab is not None else st

    with ctx:

        st.subheader("📝 Báo cáo Giao ban")

        st.caption("Tổng hợp tình hình dư nợ, cho vay, thu nợ theo ĐVUT và Xã")

        

        df = kwargs.get("df")

        pgd_user = kwargs.get("pgd_user")

        role = kwargs.get("role")

        

        if df is None or df.empty:

            st.warning("Chưa có dữ liệu HSTD.")

            return

        

        # ① Bộ lọc

        st.markdown("**① Bộ lọc dữ liệu**")

        

        # Lọc theo PGD

        df_filtered = df.copy()

        if is_pgd_role(role) and pgd_user:

            if COT_TEN_PGD in df.columns:

                df_filtered = df[df[COT_TEN_PGD] == pgd_user].copy()

            st.info(f"Dữ liệu đã lọc theo PGD: **{pgd_user}**")

        elif is_cn_role(role):

            if COT_TEN_PGD in df.columns:

                ds_pgd = sorted(df[COT_TEN_PGD].dropna().unique().tolist())

                if ds_pgd:

                    chon_pgd = st.selectbox("Chọn Phòng Giao dịch", ds_pgd, key="op_gb_pgd")

                    df_filtered = df[df[COT_TEN_PGD] == chon_pgd].copy()

        

        # Chọn Xã

        if COT_TEN_XA in df_filtered.columns:

            ds_xa = sorted(df_filtered[COT_TEN_XA].dropna().unique().tolist())

            if not ds_xa:

                st.warning("Không có dữ liệu xã nào trong PGD được chọn.")

                return

            chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa, key="op_gb_xa")

            df_xa = df_filtered[df_filtered[COT_TEN_XA] == chon_xa].copy()

        else:

            st.warning("Không tìm thấy cột 'Tên xã' trong dữ liệu.")

            return

        

        if df_xa.empty:

            st.warning(f"Không có dữ liệu cho xã **{chon_xa}**")

            return



        # Chọn điểm giao dịch

        import db

        dgd_map = db.doc_dgd_map()

        

        # Lấy PGD hiện tại

        current_pgd = pgd_user if is_pgd_role(role) else (

            chon_pgd if 'chon_pgd' in locals() else pgd_user

        )

        

        ds_dgd = []

        chon_dgd = None

        ds_thon_dgd = None

        ten_dgd = None

        

        if current_pgd and current_pgd in dgd_map and chon_xa in dgd_map[current_pgd]:

            ds_dgd = list(dgd_map[current_pgd][chon_xa].keys())

        

        if not ds_dgd:

            st.info(

                "⚠️ Xã này chưa cấu hình điểm giao dịch. "

                "Vào tab **📍 Điểm GD của tôi** để thêm/cập nhật."

            )

            # Vẫn cho phép tiếp tục - lọc theo toàn xã

            chon_dgd = None

            ds_thon_dgd = None

            df_dgd = df_xa.copy()

            ten_dgd = chon_xa

        else:

            chon_dgd = st.selectbox("📍 Điểm giao dịch", ds_dgd, key="op_gb_dgd")

            ds_thon_dgd = dgd_map[current_pgd][chon_xa][chon_dgd]

            ten_dgd = chon_dgd

            st.caption(f"Quản lý: {', '.join(ds_thon_dgd)}")

            

            # Lọc df theo thôn/ấp của điểm giao dịch

            if "Tên thôn" in df_xa.columns:

                df_dgd = df_xa[df_xa["Tên thôn"].isin(ds_thon_dgd)].copy()

            else:

                df_dgd = df_xa.copy()

                st.warning("Không tìm thấy cột 'Tên thôn' để lọc theo điểm giao dịch.")

        

        if df_dgd.empty:

            st.warning(f"Không có dữ liệu cho điểm giao dịch **{chon_dgd or chon_xa}**")

            return

        

        st.divider()

        

        # ② Bảng tổng hợp theo ĐVUT

        st.markdown("**② Tổng hợp theo ĐVUT**")

        

        # Đánh dấu khách hàng 3 tháng không hoạt động

        df_dgd_marked = danh_dau_khong_hd_cached(df_dgd)

        

        # Groupby theo Tên ĐVUT

        if COT_DVUT not in df_dgd.columns:

            st.warning("Không tìm thấy cột 'Tên ĐVUT' trong dữ liệu.")

            return

        

        # Tính toán các cột

        agg_dict = {

            "Số Tổ": ("Tên tổ", lambda x: x.nunique() if "Tên tổ" in df_dgd.columns else 0),

            "Số KH": (COT_MA_KH, lambda x: x.nunique()),

            "Tổng dư nợ": (COT_TONG_DU_NO, lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),

            "Nợ quá hạn": (COT_DU_NO_QH, lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),

        }

        

        # Thêm các cột có điều kiện

        if "Giải ngân trong tháng" in df_dgd.columns:

            agg_dict["Doanh số cho vay tháng"] = ("Giải ngân trong tháng", 

                lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())

        

        # Tính doanh số thu nợ (cộng 3 cột nếu có)

        thu_no_cols = ["Thu nợ TH tháng", "Thu nợ QH tháng", "Thu nợ khoanh tháng"]

        existing_thu_no_cols = [col for col in thu_no_cols if col in df_dgd.columns]

        if existing_thu_no_cols:

            for col in existing_thu_no_cols:

                df_dgd[col] = pd.to_numeric(df_dgd[col], errors="coerce").fillna(0)

            df_dgd["Tổng thu nợ tháng"] = df_dgd[existing_thu_no_cols].sum(axis=1)

            agg_dict["Doanh số thu nợ tháng"] = ("Tổng thu nợ tháng", "sum")

        

        if "Dư nợ khoanh" in df_dgd.columns:

            agg_dict["Nợ khoanh"] = ("Dư nợ khoanh", 

                lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())

        

        # Số khoản 3m KHĐ

        if "is_3m_inactive" in df_dgd_marked.columns:

            df_dgd["is_3m_inactive"] = df_dgd_marked["is_3m_inactive"]

            agg_dict["Số khoản 3m KHĐ"] = ("is_3m_inactive", "sum")

        

        # Tạo bảng tổng hợp - chỉ sử dụng những cột thực sự tồn tại

        valid_agg_dict = {}

        for col_name, (data_col, agg_func) in agg_dict.items():

            if data_col in df_dgd.columns:

                valid_agg_dict[data_col] = agg_func

        

        if valid_agg_dict and COT_DVUT in df_dgd.columns:

            df_bang = df_dgd.groupby(COT_DVUT).agg(valid_agg_dict).reset_index()

            

            # Đổi tên cột về tên hiển thị

            rename_dict = {}

            for col_name, (data_col, agg_func) in agg_dict.items():

                if data_col in df_dgd.columns and data_col in df_bang.columns:

                    rename_dict[data_col] = col_name

            df_bang = df_bang.rename(columns=rename_dict)

        else:

            # Tạo DataFrame rỗng với cấu trúc cơ bản

            df_bang = pd.DataFrame({COT_DVUT: []})

        

        # Tính tỷ trọng %

        if "Tổng dư nợ" in df_bang.columns and df_bang["Tổng dư nợ"].sum() > 0:

            df_bang["Tỷ trọng %"] = (df_bang["Tổng dư nợ"] / df_bang["Tổng dư nợ"].sum() * 100).round(1)

        

        # Thêm dòng Cộng

        dong_cong = {COT_DVUT: "CỘNG"}

        for col in df_bang.columns:

            if col != COT_DVUT:

                if col == "Tỷ trọng %":

                    dong_cong[col] = 100.0

                else:

                    dong_cong[col] = df_bang[col].sum()

        

        df_bang = pd.concat([df_bang, pd.DataFrame([dong_cong])], ignore_index=True)

        

        # Định dạng hiển thị (chia triệu đồng cho các cột tiền)

        df_display = df_bang.copy()

        tien_cols = ["Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh", "Doanh số cho vay tháng", "Doanh số thu nợ tháng"]

        for col in tien_cols:

            if col in df_display.columns:

                df_display[col] = (df_display[col] / 1e6).round(1)

        

        hien_thi_dataframe_phan_trang(df_display, key="op_bao_cao_dvut_bang")

        

        # Ghi chú đơn vị

        st.caption("*Đơn vị tiền: triệu đồng*")

        

        st.divider()

        

        # ③ Đoạn tóm tắt văn bản

        st.markdown("**③ Tóm tắt báo cáo**")

        

        # Lấy các số liệu từ dòng Cộng

        dong_cong_data = df_bang[df_bang[COT_DVUT] == "CỘNG"].iloc[0]

        

        tong_dn = dong_cong_data.get("Tổng dư nợ", 0) / 1e6

        so_kh = int(dong_cong_data.get("Số KH", 0))

        so_to = int(dong_cong_data.get("Số Tổ", 0))

        nqh = dong_cong_data.get("Nợ quá hạn", 0) / 1e6

        nkh = dong_cong_data.get("Nợ khoanh", 0) / 1e6

        ds_cv = dong_cong_data.get("Doanh số cho vay tháng", 0) / 1e6

        ds_thu = dong_cong_data.get("Doanh số thu nợ tháng", 0) / 1e6

        

        tl_nqh = (nqh / tong_dn * 100) if tong_dn > 0 else 0

        

        # Thông tin khu vực

        khu_vuc_text = f"{ten_dgd}"

        if ds_thon_dgd:

            khu_vuc_text += f" (gồm: {', '.join(ds_thon_dgd)})"

        

        tom_tat = f"""Khu vực {khu_vuc_text}, xã {chon_xa}: Tổng dư nợ đạt {tong_dn:,.0f} triệu đồng, với {fmt_so(so_kh)} khách hàng còn dư nợ, thông qua {so_to} Tổ TK&VV. Trong đó, nợ quá hạn {nqh:,.0f} triệu đồng, tỷ lệ {tl_nqh:.2f}%; nợ khoanh {nkh:,.0f} triệu đồng.

Doanh số cho vay trong tháng: {ds_cv:,.0f} triệu đồng; doanh số thu nợ trong tháng: {ds_thu:,.0f} triệu đồng."""

        

        st.text_area("📋 Đoạn tóm tắt (copy vào báo cáo)",

                     value=tom_tat,

                     height=150,

                     key="op_gb_tom_tat")

        

        st.divider()

        

        # ④ Xuất báo cáo

        st.markdown("**④ Xuất báo cáo**")

        

        _pdf_dep = kiem_tra_pdf_dependency()

        if not _pdf_dep["reportlab"]:

            for msg in _pdf_dep["messages"]:

                st.warning(msg)

        

        cols_xuat = [c for c in df_bang.columns if c != "Tỷ trọng %"] or list(df_bang.columns)

        

        col_excel, col_pdf = st.columns([1, 1])

        with col_excel:

            st.download_button(

                label="⬇️ Xuất Excel chuyên nghiệp",

                type="primary",

                data=xuat_excel_chuyen_nghiep(

                    df=df_bang,

                    title="Báo cáo Giao ban",

                    subtitle=f"Xã {chon_xa} · {ten_dgd or ''} · {datetime.now().strftime('%d/%m/%Y')}",

                    nguoi_xuat=st.session_state.get("txt_username", ""),

                    columns=cols_xuat,

                    kpi_items=[

                        ("Điểm GD", ten_dgd or chon_xa, ""),

                        ("Tổng dư nợ", fmt_ty(tong_dn * 1e6) if tong_dn > 0 else "—", "triệu đồng"),

                        ("Số khách hàng", fmt_so(so_kh) if so_kh > 0 else "—", ""),

                        ("Nợ quá hạn", fmt_ty(nqh * 1e6) if nqh > 0 else "—", "triệu đồng"),

                        ("Tỷ lệ NQH", f"{tl_nqh:.2f}%" if tl_nqh > 0 else "0%", ""),

                        ("Doanh số cho vay", fmt_ty(ds_cv * 1e6) if ds_cv > 0 else "—", "triệu đồng"),

                        ("Doanh số thu nợ", fmt_ty(ds_thu * 1e6) if ds_thu > 0 else "—", "triệu đồng"),

                    ],

                ),

                file_name=f"GiaoBan_{chon_xa}_{datetime.now().strftime('%Y%m%d')}.xlsx",

                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

                key="gb_download",

                use_container_width=True,

            )

        with col_pdf:

            cols_tien_gb = [c for c in ["Tổng dư nợ", "Nợ quá hạn", "Nợ khoanh", "Doanh số cho vay tháng", "Doanh số thu nợ tháng"] if c in df_bang.columns]

            import plotly.express as px

            df_chart = df_bang[df_bang[COT_DVUT] != "CỘNG"].copy()

            fig_list = []

            if not df_chart.empty and "Tổng dư nợ" in df_chart.columns:

                fig_dn = px.bar(

                    df_chart, x=COT_DVUT, y="Tổng dư nợ",

                    title="Tổng dư nợ theo ĐVUT",

                    text_auto=".1s", color_discrete_sequence=["#2E7D32"],

                )

                fig_dn.update_layout(xaxis_title="", yaxis_title="Triệu đồng")

                fig_list.append((fig_dn, "Tổng dư nợ theo ĐVUT"))

            if "Nợ quá hạn" in df_chart.columns:

                fig_nqh = px.bar(

                    df_chart, x=COT_DVUT, y="Nợ quá hạn",

                    title="Nợ quá hạn theo ĐVUT",

                    text_auto=".1s", color_discrete_sequence=["#E53935"],

                )

                fig_nqh.update_layout(xaxis_title="", yaxis_title="Triệu đồng")

                fig_list.append((fig_nqh, "Nợ quá hạn theo ĐVUT"))



            download_pdf_button(

                pdf_bytes=xuat_pdf_co_chart(

                    df=df_bang,

                    tieu_de=f"Báo cáo Giao ban - {chon_xa}",

                    nguoi_xuat=st.session_state.get("txt_username", ""),

                    figs=fig_list if fig_list else None,

                    cols_tien=cols_tien_gb,

                    prefix_file="GiaoBan",

                    them_dong_tong=False,

                ),

                filename=f"GiaoBan_{chon_xa}_{datetime.now().strftime('%Y%m%d')}.pdf",

                label=f"📥 Tải PDF ({len(df_bang)} dòng)",

                key="gb_pdf_download_v2",

            )



_WS_OP_MENU_ITEMS = [
    # ── Tổng quan ──
    {"group": "Tổng quan", "label": "🏠 Trang Chủ"},
    {"group": "Tổng quan", "label": "📊 Dashboard Sức khỏe"},
    # ── Tác nghiệp ──
    {"group": "Tác nghiệp", "label": "📊 Thông tin chung"},
    {"group": "Tác nghiệp", "label": "📈 Tiến độ công việc"},
    {"group": "Tác nghiệp", "label": "🔍 Tra cứu hồ sơ"},
    {"group": "Tác nghiệp", "label": "📋 Danh sách & Lọc"},
    {"group": "Tác nghiệp", "label": "⏰ Đến hạn"},
    {"group": "Tác nghiệp", "label": "📈 Dự phóng Dòng tiền"},
    {"group": "Tác nghiệp", "label": "🔥 Heatmap Đáo hạn"},
    {"group": "Tác nghiệp", "label": "📊 Histogram Dư nợ"},
    {"group": "Tác nghiệp", "label": "🍩 Cơ cấu CT"},
    {"group": "Tác nghiệp", "label": "📊 So sánh kỳ"},
    {"group": "Tác nghiệp", "label": "📄 Quản lý Template"},
    # ── Báo cáo ──
    {
        "group": "Báo cáo",
        "label": "Báo cáo tín dụng",
        "children": [
            {"label": "📊 Báo cáo tín dụng"},
            {"label": "📅 Báo cáo định kỳ"},
            {"label": "📡 Điện báo"},
            {"label": "📝 Báo cáo Giao ban"},
        ],
    },
    # ── Kế hoạch ──
    {
        "group": "Kế hoạch",
        "label": "Kế hoạch tín dụng",
        "children": [
            {"label": "🎯 KHTD"},
            {"label": "⚖️ Kế hoạch/Cân đối"},
            {"label": "📋 Giao & ĐC KHTD"},
            {"label": "📋 Mẫu 07 Giao KH"},
            {"label": "🔭 Xây dựng KHTD TL"},
            {"label": "📋 NQ11"},
            {"label": "📊 Dashboard GQVL"},
        ],
    },
    # ── Kiểm soát ──
    {
        "group": "Kiểm soát",
        "label": "Kiểm soát chất lượng",
        "children": [
            {"label": "🚨 Cảnh báo Tín dụng"},
            {"label": "🔔 Đôn đốc KHĐ"},
            {"label": "⚡ Nợ đến hạn có nguy cơ"},
            {"label": "🚨 Cảnh báo sớm (Full)"},
            {"label": "✅ Checklist Nội bộ PGD"},
            {"label": "🔍 Kiểm soát Dữ liệu"},
            {"label": "👔 CBTD & Địa bàn"},
            {"label": "💳 Xử lý Rủi ro"},
            {"label": "📍 Điểm Giao Dịch"},
            {"label": "🏛️ Ban Đại Diện"},
            {"label": "🤝 Ủy thác"},
            {"label": "📊 Tổng quan Nợ Khoanh"},
            {"label": "🔒 Quản lý Nợ Khoanh CV 368"},
        ],
    },
    # ── Công cụ ──
    {
        "group": "Công cụ",
        "label": "Công cụ & Hệ thống",
        "children": [
            {"label": "✅ Nhiệm vụ"},
            {"label": "📤 Upload Dữ liệu"},
            {"label": "📤 Upload HSTD"},
            {"label": "🏦 Nguồn vốn ĐP"},
            {"label": "🏦 Mã NĐT địa phương"},
            {"label": "📋 Nhật ký hoạt động"},
            {"label": "📈 Phân tích xu hướng"},
            {"label": "🔍 Trạng thái hệ thống"},
            {"label": "📖 Hướng dẫn"},
        ],
    },
]

_GROUP_COLORS = {
    "Tổng quan":  {"bg": "#0D2137", "border": "#64B5F6", "text": "#90CAF9"},
    "Tác nghiệp": {"bg": "#0D2818", "border": "#A5D6A7", "text": "#A5D6A7"},
    "Báo cáo":    {"bg": "#2D1F0D", "border": "#FFCC80", "text": "#FFD54F"},
    "Kế hoạch":   {"bg": "#0D2818", "border": "#80CBC4", "text": "#80CBC4"},
    "Kiểm soát":  {"bg": "#2D0D14", "border": "#EF9A9A", "text": "#F48FB1"},
    "Công cụ":    {"bg": "#1E2130", "border": "#94A3B8", "text": "#B0BEC5"},
}

_GROUP_KEY_MAP = {
    "Tổng quan": "nghiep_vu_pgd",
    "Tác nghiệp": "nghiep_vu_pgd",
    "Báo cáo": "bao_cao_giao_ban",
    "Kế hoạch": "ke_hoach_pgd",
    "Kiểm soát": "kiem_soat_rr",
    "Công cụ": "quan_tri_pgd",
}


def render_sidebar_menu(role, username, **kwargs):
    """Render menu HỖ TRỢ ĐỊA BÀN — gọi từ app.py bên trong with st.sidebar.
    Pattern giống hệt render_sidebar_menu của ws_management: flat button + accordion children."""

    state = SCMStateManager()

    df_pgd = kwargs.get("df_pgd")
    pgd_user_op = kwargs.get("pgd_user")
    tab_perm = kwargs.get("tab_perm", {})
    nhom_duoc_phep = tab_perm.get("nhom_duoc_phep", [])

    _ten_hien_thi = pgd_user_op or "Toàn địa bàn"

    # ── Filter to allowed groups ──────────────────────────────────────
    allowed_items = []
    for item in _WS_OP_MENU_ITEMS:
        grp_key = _GROUP_KEY_MAP.get(item["group"], "")
        if nhom_duoc_phep and grp_key not in nhom_duoc_phep:
            continue
        allowed_items.append(item)

    if not allowed_items:
        return

    # ── Build valid labels ────────────────────────────────────────────
    valid_labels = [x["label"] for x in allowed_items] + [
        c["label"] for x in allowed_items for c in x.get("children", [])
    ]

    default_label = allowed_items[0]["label"]
    active_label = state.nav_ws_op_menu
    if active_label not in valid_labels:
        state.nav_ws_op_menu = default_label
        active_label = default_label

    st.markdown(f"### 🏦 {_ten_hien_thi}")
    so_ho_so = len(df_pgd) if df_pgd is not None and not df_pgd.empty else 0
    st.caption(f"{fmt_so(so_ho_so)} hồ sơ")
    st.divider()

    st.markdown(
        "<p style='font-size:14px;font-weight:700;"
        "color:#94A3B8;margin-bottom:6px'>MENU HỖ TRỢ ĐỊA BÀN</p>",
        unsafe_allow_html=True,
    )

    # ── Group items by group name ──────────────────────────────────────
    groups = []
    current_grp = None
    cur_flat = []
    cur_acc = []
    for item in allowed_items:
        g = item["group"]
        if g != current_grp:
            if cur_flat or cur_acc:
                groups.append((current_grp, cur_flat, cur_acc))
            current_grp = g
            cur_flat = []
            cur_acc = []
        if item.get("children"):
            cur_acc.append(item)
        else:
            cur_flat.append(item)
    if cur_flat or cur_acc:
        groups.append((current_grp, cur_flat, cur_acc))

    # ── Render each group ─────────────────────────────────────────────
    for grp_name, flat_items, acc_items in groups:
        clr = _GROUP_COLORS.get(grp_name, {"bg": "#F1EFE8", "border": "#888", "text": "#444"})

        st.markdown(
            f"<p style='font-size:11px;font-weight:700;"
            f"color:{clr['text']};text-transform:uppercase;"
            f"letter-spacing:0.06em;padding:12px 4px 4px;margin:0'>"
            f"{grp_name}</p>",
            unsafe_allow_html=True,
        )

        # ── Flat items ─────────────────────────────────────────────────
        for item in flat_items:
            is_active = item["label"] == active_label
            if is_active:
                st.markdown(
                    f"<div style='"
                    f"background:#E65100;"
                    f"border-left:3px solid #BF360C;"
                    f"color:#FFFFFF;"
                    f"font-size:14px;font-weight:700;"
                    f"padding:10px 12px 10px 14px;"
                    f"border-radius:0 6px 6px 0;"
                    f"margin-bottom:4px'>"
                    f"{item['label']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                if st.button(
                    item["label"],
                    key=f"ws_op_m_{item['label']}",
                    use_container_width=True,
                ):
                    state.nav_ws_op_menu = item["label"]
                    st.rerun()

        # ── Accordion items ────────────────────────────────────────────
        for item in acc_items:
            children = item.get("children", [])
            child_labels = [c["label"] for c in children]
            is_child_active = active_label in child_labels
            open_key = f"ws_op_acc_{item['label']}"

            if is_child_active and not st.session_state.get(open_key):
                st.session_state[open_key] = True

            is_open = st.session_state.get(open_key, False)

            # Parent button / active bar
            if is_child_active:
                st.markdown(
                    f"<div style='"
                    f"background:#E65100;"
                    f"border-left:3px solid #BF360C;"
                    f"color:#FFFFFF;"
                    f"font-size:14px;font-weight:700;"
                    f"padding:10px 12px 10px 14px;"
                    f"border-radius:0 6px 6px 0;"
                    f"margin-bottom:4px'>"
                    f"\u25be {item['label']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                arrow = "\u25be" if is_open else "\u25b8"
                if st.button(
                    f"{arrow} {item['label']}",
                    key=f"ws_op_acc_btn_{item['label']}",
                    use_container_width=True,
                ):
                    st.session_state[open_key] = not is_open
                    st.rerun()

            # Children (only when open OR when a child is active)
            if is_open or is_child_active:
                for child in children:
                    is_child_sel = active_label == child["label"]
                    if is_child_sel:
                        st.markdown(
                            f"<div style='background:#E65100;"
                            f"border-left:4px solid #BF360C;"
                            f"color:#FFFFFF;font-size:13px;font-weight:700;"
                            f"padding:8px 10px 8px 22px;"
                            f"border-radius:0 6px 6px 0;margin-bottom:3px'>"
                            f"\u25cf {child['label']}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        _, col = st.columns([0.06, 0.94])
                        with col:
                            if st.button(
                                f"\u21b3 {child['label']}",
                                key=f"ws_op_m_{child['label']}",
                                use_container_width=True,
                            ):
                                state.nav_ws_op_menu = child["label"]
                                st.rerun()


def render(**kwargs):

    _wl = st.session_state.pop("_data_load_warning", None)

    if _wl:

        st.warning(_wl)



    df = kwargs.get("df")

    df_nq11 = kwargs.get("df_nq11")

    role = kwargs.get("role")

    pgd_user = kwargs.get("pgd_user")

    username = kwargs.get("username", "unknown")

    state = SCMStateManager()

    if is_pgd_role(role) and pgd_user and df is not None and COT_TEN_PGD in df.columns:
        state.filter_pgd = pgd_user
        df_pgd = df[df[COT_TEN_PGD] == pgd_user].copy()
    else:
        df_pgd = df

    pgd_filter = pgd_user
    tab_perm = get_tab_permissions(role)
    nhom_duoc_phep = tab_perm["nhom_duoc_phep"]

    _pgd_df_kwargs = {**kwargs, "df": df_pgd, "df_full": df_pgd, "pgd_filter": pgd_filter}

    # ── Helpers render ──────────────────────────────────────────────────

    def _render_diem_gd_va_to_tkvv(tab_parent, **kw):

        with get_tab_context(tab_parent):

            _sub0, _sub1, _sub2 = st.tabs(["📊 Tổng quan", "📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"])

            _render_dashboard_pgd_dgd(_sub0, **kw)

            _lazy_tab("tab_diem_gd_pgd").render(_sub1, **kw)

            _lazy_tab("tab_cdtotkvv_pgd").render(_sub2, **kw)



    def _render_dashboard_pgd_dgd(tab_parent, **kw):

        """Dashboard mini: KPI ĐGD & Tổ TK&VV trong phạm vi 1 PGD."""

        with get_tab_context(tab_parent):

            from components.delta_card import kpi_row as _kpi_row

            from services.cbtd_dia_ban_service import tom_tat_kpi as _tom_kpi, canh_bao_cbtd_dia_ban as _canh_bao

            from services.cdtotkvv_service import tong_hop_tu_pgd_data as _tong_hop_cdto, loc_df as _loc_df



            _pgd_user = kw.get("pgd_user", "")

            _df       = kw.get("df")

            _role_kw  = kw.get("role", "user")

            _username = kw.get("username", "unknown")



            st.subheader("📊 Tổng quan ĐGD & Tổ TK&VV")

            st.caption(f"Phạm vi: {_pgd_user or 'PGD của bạn'}")



            _dgd_map   = db.doc_dgd_map() or {}

            _cbtd_data = {}



            try:

                from data.khtd import doc_cbtd as _dc

                _cbtd_all = _dc()

                if _pgd_user:

                    _cbtd_data = {

                        k: v for k, v in _cbtd_all.items()

                        if str(v.get("pgd", "")).strip().lower() == _pgd_user.strip().lower()

                    }

                else:

                    _cbtd_data = _cbtd_all

            except Exception:

                pass



            # Lọc dgd_map theo PGD

            _dgd_pgd: dict = {}

            if _pgd_user:

                for pgd_k, xa_block in _dgd_map.items():

                    if str(pgd_k).strip().lower() == _pgd_user.strip().lower():

                        _dgd_pgd = {pgd_k: xa_block}

                        break

            else:

                _dgd_pgd = _dgd_map



            # Tổ TK&VV

            _df_cdto_all = None

            try:

                _df_cdto_all = _tong_hop_cdto()

                if _df_cdto_all is not None and not _df_cdto_all.empty:

                    _df_cdto_all = _loc_df(_df_cdto_all, "pgd", _pgd_user)

            except Exception:

                pass



            _kpi = _tom_kpi(_cbtd_data, _dgd_pgd, _df_cdto_all)



            _kpi_row(

                cols=[

                    {"label": "CBTD của PGD", "value": fmt_so(_kpi["so_cbtd"]),        "icon": "👔"},

                    {"label": "Tổng ĐGD",     "value": fmt_so(_kpi["so_dgd_tong"]),    "icon": "📍"},

                    {"label": "Tổng Tổ",      "value": fmt_so(_kpi["so_to_tong"]),     "icon": "🏘️"},

                    {"label": "Điểm TB",       "value": f"{_kpi['diem_tb']:.1f}" if _kpi["so_to_tong"] else "—", "icon": "⭐"},

                    {"label": "% Tổ đạt",     "value": f"{_kpi['pct_to_dat']:.1f}%" if _kpi["so_to_tong"] else "—", "icon": "✅"},

                    {"label": "Tổ TB/Yếu",    "value": fmt_so(_kpi["so_to_tb_yeu"]),  "icon": "🔴" if _kpi["so_to_tb_yeu"] else "🟢"},

                ],

                num_columns=6,

            )



            # Cảnh báo nhanh

            try:

                _cbs = _canh_bao(_cbtd_data, _dgd_pgd, _df, _df_cdto_all)

                if _cbs:

                    with st.expander(f"🔔 Cảnh báo ({len(_cbs)})", expanded=True):

                        for _cb in _cbs:

                            if _cb["muc_do"] == "🔴":

                                st.error(_cb["noi_dung"])

                            else:

                                st.warning(_cb["noi_dung"])

                else:

                    st.success("✅ Không có cảnh báo nào cho PGD này.")

            except Exception:

                pass



    def _render_du_phong_dong_tien(tab_parent, **kw) -> None:

        with get_tab_context(tab_parent):

            from services.du_phong_service import du_phong_dong_tien, du_phong_chi_tiet

            from dateutil.relativedelta import relativedelta



            df_loc = kw.get("df")

            pgd = kw.get("pgd_user") or kw.get("pgd_filter") or ""



            st.subheader("📈 Dự phóng Doanh số & Kế hoạch Dòng tiền")



            if df_loc is None or df_loc.empty:

                st.info("Chưa có dữ liệu HSTD.")

                return



            if pgd:

                st.caption(f"📍 Địa bàn: **{pgd}**")



            hom_nay = datetime.now().date()

            thang_ht = date(hom_nay.year, hom_nay.month, 1)



            col_xa, col_ct = st.columns(2)

            with col_xa:

                ds_xa = ["Tất cả"] + sorted(df_loc[COT_TEN_XA].dropna().unique().tolist()) if COT_TEN_XA in df_loc.columns else ["Tất cả"]

                loc_xa = st.selectbox("🏘️ Xã", ds_xa, key="op_dp_xa")

            with col_ct:

                ds_ct = ["Tất cả"] + sorted(df_loc[COT_TEN_CT].dropna().unique().tolist()) if COT_TEN_CT in df_loc.columns else ["Tất cả"]

                loc_ct = st.selectbox("📌 Chương trình", ds_ct, key="op_dp_ct")



            df_work = df_loc.copy()

            if loc_xa != "Tất cả" and COT_TEN_XA in df_work.columns:

                df_work = df_work[df_work[COT_TEN_XA] == loc_xa]

            if loc_ct != "Tất cả" and COT_TEN_CT in df_work.columns:

                df_work = df_work[df_work[COT_TEN_CT] == loc_ct]



            if df_work.empty:

                st.info("Không có dữ liệu phù hợp với bộ lọc.")

                return



            df_dp = du_phong_dong_tien(df_work)



            if df_dp.empty:

                st.warning("⚠️ Không đủ dữ liệu Ngày vay / Ngày ĐH để dự phóng.")

                return



            # Chia 2 phần: tháng đã qua và tháng tương lai

            df_qua = df_dp[df_dp["thang"] < thang_ht].copy()

            df_lai = df_dp[df_dp["thang"] >= thang_ht].copy()



            tong_goc_qua = df_qua["du_kien_thu_goc"].sum() if not df_qua.empty else 0

            tong_goc_lai = df_lai["du_kien_thu_goc"].sum() if not df_lai.empty else 0



            c1, c2, c3 = st.columns(3)

            c1.metric("📊 Số tháng dự phóng", f"{len(df_dp)} tháng")

            c2.metric("✅ Đã qua (dự kiến)", fmt_ty(tong_goc_qua))

            c3.metric("🔮 Tương lai (dự kiến)", fmt_ty(tong_goc_lai))



            st.divider()



            # Biểu đồ cột

            st.markdown("**📊 Biểu đồ Dự phóng Dòng tiền theo tháng**")



            import plotly.graph_objects as go



            fig = go.Figure()



            if not df_qua.empty:

                fig.add_trace(go.Bar(

                    x=df_qua["thang_label"],

                    y=df_qua["du_kien_thu_goc_trieu"],

                    name="Đã qua (dự kiến)",

                    marker_color="#9e9e9e",

                    hovertemplate="%{y:,.0f} triệu<extra></extra>",

                ))



            if not df_lai.empty:

                fig.add_trace(go.Bar(

                    x=df_lai["thang_label"],

                    y=df_lai["du_kien_thu_goc_trieu"],

                    name="Tương lai (dự kiến)",

                    marker_color="#1565c0",

                    hovertemplate="%{y:,.0f} triệu<extra></extra>",

                ))



            fig.update_layout(

                barmode="stack",

                height=350,

                margin=dict(l=0, r=20, t=10, b=10),

                plot_bgcolor="rgba(0,0,0,0)",

                paper_bgcolor="rgba(0,0,0,0)",

                font_family="Arial",

                xaxis=dict(title=""),

                yaxis=dict(title="Triệu đồng", tickformat=",.0f"),

                legend=dict(orientation="h", y=1.08),

            )

            st.plotly_chart(fig, use_container_width=True)



            # Bảng dữ liệu

            with st.expander("📋 Xem bảng số liệu chi tiết", expanded=False):

                df_show = df_dp[["thang_label", "so_mon", "tong_du_no_trieu", "du_kien_thu_goc_trieu"]].copy()

                df_show.columns = ["Tháng", "Số món", "Tổng dư nợ (tr.đ)", "Dự kiến thu gốc (tr.đ)"]

                st.dataframe(df_show, hide_index=True, use_container_width=True)



            # Chọn tháng xem chi tiết

            st.markdown("**🔍 Xem chi tiết tháng cụ thể**")

            thang_xem = st.selectbox(

                "Chọn tháng",

                df_dp["thang_label"].tolist(),

                key="op_dp_thang_xem",

            )

            thang_date = df_dp[df_dp["thang_label"] == thang_xem]["thang"].iloc[0]



            df_ct_detail = du_phong_chi_tiet(df_work, thang_date)

            if not df_ct_detail.empty:

                st.caption(f"**{len(df_ct_detail)}** khế ước có gốc đến hạn trong tháng {thang_xem}")

                cols_show = [c for c in ["ten_kh", "ten_xa", "ten_ct", "du_no_trieu", "goc_ht_trieu", "ngay_vay", "ngay_dh"]

                             if c in df_ct_detail.columns]

                df_ct_show = df_ct_detail[cols_show].copy()

                col_map = {"ten_kh": "Khách hàng", "ten_xa": "Xã", "ten_ct": "Chương trình",

                           "du_no_trieu": "Dư nợ (tr.đ)", "goc_ht_trieu": "Gốc/tháng (tr.đ)",

                           "ngay_vay": "Ngày vay", "ngay_dh": "Ngày ĐH"}

                df_ct_show = df_ct_show.rename(columns={k: v for k, v in col_map.items() if k in df_ct_show.columns})

                st.dataframe(df_ct_show, hide_index=True, use_container_width=True, height=300)

            else:

                st.info("Không có khế ước nào đến hạn thu gốc trong tháng này.")



    def _render_heatmap_dao_han(tab_parent, **kw) -> None:

        with get_tab_context(tab_parent):

            import plotly.express as px

            from dateutil.relativedelta import relativedelta



            df_loc = kw.get("df")

            st.subheader("🔥 Heatmap Đáo hạn — Dư nợ đến hạn theo Tháng × Chương trình")



            if df_loc is None or df_loc.empty:

                st.info("Chưa có dữ liệu HSTD.")

                return



            hom_nay = datetime.now().date()

            thang_ht = date(hom_nay.year, hom_nay.month, 1)



            cot_ngay_vay = COT_NGAY_VAY if COT_NGAY_VAY in df_loc.columns else (COT_NGAY_DH if COT_NGAY_DH in df_loc.columns else None)

            if cot_ngay_vay is None:

                st.warning("Không tìm thấy cột ngày vay/ngày ĐH để tính đáo hạn.")

                return



            cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else COT_DU_NO_TH

            if cot_tien not in df_loc.columns:

                st.warning("Không tìm thấy cột dư nợ để tính.")

                return



            df_hm = df_loc.copy()

            df_hm[cot_ngay_vay] = pd.to_datetime(df_hm[cot_ngay_vay], errors="coerce")

            df_hm = df_hm.dropna(subset=[cot_ngay_vay])



            df_hm["thang_dh"] = df_hm[cot_ngay_vay].dt.to_period("M").astype(str)

            df_hm["nam"] = df_hm[cot_ngay_vay].dt.year.astype(int)



            nam_min = max(df_hm["nam"].min(), hom_nay.year - 1)

            nam_max = min(df_hm["nam"].max(), hom_nay.year + 2)



            df_loc_hm = df_hm[(df_hm["nam"] >= nam_min) & (df_hm["nam"] <= nam_max)].copy()



            if df_loc_hm.empty:

                st.info("Không có dữ liệu trong khoảng thời gian này.")

                return



            nhom_ct = COT_TEN_CT if COT_TEN_CT in df_loc_hm.columns else None



            if nhom_ct:

                pivot = df_loc_hm.pivot_table(

                    index="thang_dh", columns=nhom_ct, values=cot_tien, aggfunc="sum"

                ).fillna(0)

            else:

                pivot = df_loc_hm.groupby("thang_dh")[cot_tien].sum().to_frame("Tổng")



            fig = px.imshow(

                pivot if nhom_ct else pivot.T,

                text_auto=".0f",

                aspect="auto",

                color_continuous_scale="YlOrRd",

                labels=dict(x="Chương trình" if nhom_ct else "", y="Tháng", color="Dư nợ (triệu)"),

                title="Dư nợ đến hạn theo Tháng × Chương trình",

            )

            fig.update_layout(

                height=max(350, len(pivot) * 40),

                margin=dict(l=0, r=0, t=40, b=0),

                font_family="Arial",

            )

            if nhom_ct:

                fig.update_xaxes(tickangle=45)

            st.plotly_chart(fig, use_container_width=True)



            with st.expander("📋 Bảng số liệu", expanded=False):

                df_show = pivot.reset_index() if nhom_ct else pivot.reset_index()

                st.dataframe(df_show, hide_index=True, use_container_width=True)



            if not nhom_ct:

                st.caption("💡 Thêm dữ liệu cột Chương trình để xem heatmap chi tiết theo từng CT.")



            st.divider()

            col1, col2 = st.columns([1, 1])

            with col1:

                st.download_button(

                    label="⬇️ Xuất Excel (chuyên nghiệp)",

                    type="primary",

                    data=xuat_excel_chuyen_nghiep(

                        df=df_show,

                        title="Heatmap Đáo hạn",

                        subtitle=f"Kỳ: {nam_min}-{nam_max}",

                        nguoi_xuat=st.session_state.get("txt_username", ""),

                        kpi_items=[

                            ("Tổng số tháng", fmt_so(len(pivot)), ""),

                            ("Dư nợ b/q tháng", fmt_ty(pivot.values.mean()), "triệu đồng"),

                        ],

                    ),

                    file_name=excel_ten_file("Heatmap_DaoHan"),

                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

                    use_container_width=True,

                )



    def _render_histogram_du_no(tab_parent, **kw) -> None:

        with get_tab_context(tab_parent):

            import plotly.express as px



            df_loc = kw.get("df")

            st.subheader("📊 Histogram — Phân bố Dư nợ theo Khoản vay")



            if df_loc is None or df_loc.empty:

                st.info("Chưa có dữ liệu HSTD.")

                return



            cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else (COT_DU_NO_TH if COT_DU_NO_TH in df_loc.columns else None)

            if cot_tien is None:

                st.warning("Không tìm thấy cột dư nợ.")

                return



            df_hist = df_loc.copy()

            df_hist[cot_tien] = pd.to_numeric(df_hist[cot_tien], errors="coerce").fillna(0)

            df_hist = df_hist[df_hist[cot_tien] > 0]



            if df_hist.empty:

                st.info("Không có dữ liệu dư nợ dương.")

                return



            max_val = df_hist[cot_tien].max()

            bins = st.slider("Số khoảng (bins)", min_value=5, max_value=50, value=20, key="op_hist_bins")



            fig = px.histogram(

                df_hist,

                x=cot_tien,

                nbins=bins,

                labels={cot_tien: "Dư nợ (đồng)"},

                title="Phân bố dư nợ",

                color_discrete_sequence=["#2E7D32"],

            )

            fig.update_layout(

                height=400,

                margin=dict(l=0, r=20, t=40, b=0),

                font_family="Arial",

                xaxis=dict(tickformat=",.0f"),

                yaxis=dict(title="Số khoản vay"),

                bargap=0.05,

            )

            fig.add_vline(x=df_hist[cot_tien].median(), line_dash="dash", line_color="#C62828",

                          annotation_text=f"Trung vị: {df_hist[cot_tien].median():,.0f}")

            st.plotly_chart(fig, use_container_width=True)



            col_s1, col_s2, col_s3 = st.columns(3)

            with col_s1:

                st.metric("Trung bình", fmt_ty(df_hist[cot_tien].mean()), help="Dư nợ bình quân/khoản")

            with col_s2:

                st.metric("Trung vị", fmt_ty(df_hist[cot_tien].median()), help="Dư nợ trung vị")

            with col_s3:

                st.metric("Tổng số khoản", fmt_so(len(df_hist)), help="Số khoản vay có dư nợ")



    def _render_donut_co_cau(tab_parent, **kw) -> None:

        with get_tab_context(tab_parent):

            import plotly.graph_objects as go





            df_loc = kw.get("df")

            st.subheader("🍩 Donut — Cơ cấu Dư nợ theo Chương trình")



            if df_loc is None or df_loc.empty:

                st.info("Chưa có dữ liệu HSTD.")

                return



            nhom_ct = COT_TEN_CT if COT_TEN_CT in df_loc.columns else None

            if nhom_ct is None:

                st.warning("Không tìm thấy cột Chương trình.")

                return



            cot_tien = COT_TONG_DU_NO if COT_TONG_DU_NO in df_loc.columns else (COT_DU_NO_TH if COT_DU_NO_TH in df_loc.columns else None)

            if cot_tien is None:

                st.warning("Không tìm thấy cột dư nợ.")

                return



            df_donut = df_loc.copy()

            df_donut[cot_tien] = pd.to_numeric(df_donut[cot_tien], errors="coerce").fillna(0)

            df_donut = df_donut[df_donut[cot_tien] > 0]



            if df_donut.empty:

                st.info("Không có dữ liệu dư nợ dương.")

                return



            ct_group = df_donut.groupby(nhom_ct)[cot_tien].sum().sort_values(ascending=False)



            top_n = st.slider("Hiển thị Top N chương trình", min_value=3, max_value=10, value=5, key="op_donut_top")

            ct_show = ct_group.head(top_n)

            ct_others = ct_group.iloc[top_n:].sum() if len(ct_group) > top_n else 0



            labels = list(ct_show.index)

            values = [v / 1e6 for v in ct_show.values]

            if ct_others > 0:

                labels.append("Khác")

                values.append(ct_others / 1e6)



            colors = ["#2E7D32", "#1565C0", "#F9A825", "#C62828", "#6A1B9A",

                      "#00838F", "#E65100", "#4E342E", "#37474F", "#827717"]



            fig = go.Figure(data=[go.Pie(

                labels=labels,

                values=values,

                hole=0.4,

                marker=dict(colors=colors[:len(labels)]),

                textinfo="label+percent",

                texttemplate="%{label}<br>%{percent:.1f}%",

                hovertemplate="<b>%{label}</b><br>Dư nợ: %{value:,.0f} tr.đ<br>Tỷ trọng: %{percent:.1f}%<extra></extra>",

            )])

            fig.update_layout(

                height=450,

                margin=dict(l=0, r=0, t=10, b=0),

                font_family="Arial",

                legend=dict(orientation="h", y=-0.1),

            )

            st.plotly_chart(fig, use_container_width=True)



            with st.expander("📋 Bảng số liệu", expanded=False):

                df_ct = ct_group.reset_index()

                df_ct.columns = ["Chương trình", "Dư nợ (đồng)"]

                df_ct["Dư nợ (triệu)"] = (df_ct["Dư nợ (đồng)"] / 1e6).round(1)

                df_ct["Tỷ trọng %"] = (df_ct["Dư nợ (đồng)"] / df_ct["Dư nợ (đồng)"].sum() * 100).round(1)

                st.dataframe(df_ct, hide_index=True, use_container_width=True)



    def _render_doc_hub_tab(tab_parent) -> None:

        with get_tab_context(tab_parent):

            _init_gb2_session_for_doc_hub(kwargs)

            _render_doc_hub(df, df_nq11, role)



    # ── Định nghĩa nhóm tab ─────────────────────────────────────────────

    CAC_NHOM = {

        "trang_chu": {

            "label": "🏠 Trang Chủ",

            "tabs": [

                ("🏠 Trang Chủ", lambda tab: _render_trang_chu(tab, df_pgd, role, pgd_user, kwargs)),

                ("📊 Dashboard Sức khỏe", lambda tab: _lazy_tab("tab_dashboard_suc_khoe_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role)),

            ],

        },

        "nghiep_vu_pgd": {

            "label": "📋 Nghiệp vụ hàng ngày",

            "tabs": [

                ("📊 Thông tin chung", lambda tab: _lazy_tab("tab_tongquan").render(tab, **_pgd_df_kwargs)),

                ("📈 Tiến độ công việc", lambda tab: _lazy_tab("tab_tien_do").render(tab, **kwargs)),

                ("🔍 Tra cứu hồ sơ", lambda tab: _lazy_tab("tab_tracuu_v2").render(tab, **kwargs)),

                ("📋 Danh sách & Lọc", lambda tab: _lazy_tab("tab_danhsach").render(tab, **kwargs)),

                ("⏰ Đến hạn", lambda tab: _lazy_tab("tab_den_han").render(tab, role=role, pgd_user=pgd_user)),

                ("📈 Dự phóng Dòng tiền", lambda tab: _render_du_phong_dong_tien(tab, **_pgd_df_kwargs)),

                ("🔥 Heatmap Đáo hạn", lambda tab: _render_heatmap_dao_han(tab, **_pgd_df_kwargs)),

                ("📊 Histogram Dư nợ", lambda tab: _render_histogram_du_no(tab, **_pgd_df_kwargs)),

                ("🍩 Cơ cấu CT", lambda tab: _render_donut_co_cau(tab, **_pgd_df_kwargs)),

                ("📊 So sánh kỳ", lambda tab: _lazy_tab("tab_so_sanh_ky").render(

                    tab, df=df_pgd, df_full=df_pgd, role=role, username=username,

                    pgd_user=pgd_user, pgd_mode=True,

                )),

                ("📄 Quản lý Template", lambda tab: _lazy_tab("tab_template_pgd").render(tab, **kwargs)),

            ],

        },

        "bao_cao_giao_ban": {

            "label": "📈 Báo cáo & Giao ban",

            "tabs": [

                ("📊 Báo cáo tín dụng", lambda tab: _lazy_tab("tab_baocao").render(tab, **_pgd_df_kwargs)),

                ("📅 Báo cáo định kỳ", lambda tab: _lazy_tab("tab_bao_cao_dinh_ky").render(tab, **kwargs)),

                ("📡 Điện báo", lambda tab: _lazy_tab("tab_candoi").render(

                    tab, **{**kwargs, "pgd_mode": True, "df": df, "df_full": df}

                )),

                ("📝 Báo cáo Giao ban", lambda tab: _render_bao_cao_giao_ban(tab, **kwargs)),

                ("📄 Trung tâm mẫu biểu",       lambda tab: _render_doc_hub_tab(tab)),

                ("📋 Biên bản giao ban",         lambda tab: _render_bien_ban_giao_ban(tab, **kwargs)),

                ("📢 Thông báo kết luận",        lambda tab: _render_thong_bao_ket_luan(tab, **kwargs)),

                ("📋 Theo dõi nhập liệu",         lambda tab: _lazy_tab("tab_theo_doi_nhap").render(tab, **kwargs)),

                ("📥 Tiến độ nộp BC",             lambda tab: _lazy_tab("tab_tien_do_nop").render(tab, **kwargs)),

                ("✅ Checklist BC",               lambda tab: _lazy_tab("tab_checklist_bc").render(tab, **kwargs)),

            ],

        },

        "ke_hoach_pgd": {

            "label": "🎯 Kế hoạch PGD",

            "tabs": [

                ("🎯 KHTD", lambda tab: _lazy_tab("tab_khtd_pgd").render(tab, **kwargs)),

                ("⚖️ Kế hoạch/Cân đối", lambda tab: _lazy_tab("tab_kehoach").render(

                    tab, df=df_pgd, role=role, username=username,

                    pgd_mode=True, pgd_user=pgd_user or pgd_filter or ""

                )),

                ("📋 Giao & ĐC KHTD", lambda tab: _lazy_tab("tab_khtd_giao_dc").render(tab, **kwargs)),

                ("📋 Mẫu 07 Giao KH", lambda tab: _lazy_tab("tab_khtd_mau07").render(tab, **kwargs)),

                ("🔭 Xây dựng KHTD TL", lambda tab: _lazy_tab("tab_xay_dung_khtd").render(tab, **kwargs)),

                ("📋 NQ11", lambda tab: _lazy_tab("tab_nq11").render(tab, **_pgd_df_kwargs)),

                ("📊 Dashboard GQVL", lambda tab: _lazy_tab("tab_gqvl_pgd").render(tab, **kwargs)),

            ],

        },

        "kiem_soat_rr": {

            "label": "🔍 Kiểm soát & Rủi ro",

            "tabs": [

                ("🚨 Cảnh báo Tín dụng", lambda tab: _render_canh_bao_nqh_pgd(tab, **_pgd_df_kwargs)),

                ("🔔 Đôn đốc KHĐ", lambda tab: _lazy_tab("tab_don_doc_khd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role)),

                ("⚡ Nợ đến hạn có nguy cơ", lambda tab: _render_canh_bao_som_pgd(tab, **kwargs)),

                ("🚨 Cảnh báo sớm (Full)", lambda tab: _lazy_tab("tab_canh_bao_som_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role, username=username)),

                ("✅ Checklist Nội bộ PGD", lambda tab: _lazy_tab("tab_kiem_soat_noi_bo_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role)),

                ("🔍 Kiểm soát Dữ liệu", lambda tab: _render_kiem_soat_pgd(tab, df_pgd, pgd_user or pgd_filter or "", role, username)),

                ("👔 CBTD & Địa bàn", lambda tab: _lazy_tab("tab_cbtd").render(

                    tab, df=df_pgd, role=role, username=username, pgd_user=pgd_user or pgd_filter or ""

                )),

                ("💳 Xử lý Rủi ro", lambda tab: _lazy_tab("tab_xu_ly_rui_ro").render(

                    tab, df=df_pgd, role=role, username=username, pgd_user=pgd_user or pgd_filter

                )),

                ("📍 Điểm Giao Dịch", lambda tab: _lazy_tab("tab_diem_gd_pgd").render(tab, **kwargs)),

                ("🏘️ Tổ TK&VV",       lambda tab: _lazy_tab("tab_cdtotkvv_pgd").render(tab, **kwargs)),

                ("🏛️ Ban Đại Diện", lambda tab: _lazy_tab("tab_ban_dai_dien").render(tab, cap="xa", **kwargs)),

                ("🤝 Ủy thác", lambda tab: _lazy_tab("tab_uy_thac").render(tab, **kwargs)),

                ("📊 Tổng quan Nợ Khoanh", lambda tab: _lazy_tab("tab_no_khoanh").render(

                    tab,

                    df=df_pgd,

                    df_full=None,

                    role=role,

                    username=username,

                    pgd_user=pgd_user,

                    nhom="tongquan",

                )),

                ("🔒 Quản lý Nợ Khoanh CV 368", lambda tab: _lazy_tab("tab_no_khoanh").render(

                    tab,

                    df=df_pgd,

                    df_full=None,

                    role=role,

                    username=username,

                    pgd_user=pgd_user,

                    nhom="cv368",

                )),

            ],

        },

        "quan_tri_pgd": {

            "label": "⚙️ Quản trị PGD",

            "tabs": [

                ("✅ Nhiệm vụ", lambda tab: _lazy_tab("tab_nhiem_vu").render(tab, **kwargs)),

                ("📤 Upload Dữ liệu", lambda tab: _lazy_tab("tab_upload_pgd").render(tab, **kwargs)),

                ("📤 Upload HSTD", lambda tab: _lazy_tab("tab_upload_pgd").render(tab, **kwargs)),

                ("🏦 Nguồn vốn ĐP", lambda tab: _lazy_tab("tab_hhi").render(

                    tab, df_full=df_pgd, pgd_user=pgd_user or pgd_filter or ""

                )),

                ("🏦 Mã NĐT địa phương", lambda tab: _lazy_tab("tab_ndt_dp").render(

                    tab, df=df_pgd, role=role, username=username,

                    pgd_user=pgd_user or pgd_filter or ""

                )),

                ("📋 Nhật ký hoạt động", lambda tab: _lazy_tab("tab_audit_log").render(

                    tab, role=role, username=username,

                    pgd_user=pgd_user or pgd_filter or ""

                )),

                ("📈 Phân tích xu hướng", lambda tab: _lazy_tab("tab_xu_huong_pgd").render(tab, **kwargs)),

                ("🔍 Trạng thái hệ thống", lambda tab: _lazy_tab("tab_trang_thai_nguon").render(tab, **kwargs)),

                ("📖 Hướng dẫn", lambda tab: render_huong_dan()),

            ],

        },

    }

    _tab_label_fns = {}
    for _key, _info in CAC_NHOM.items():
        if _key not in nhom_duoc_phep and _key != "trang_chu":
            continue
        _tabs = _info["tabs"]
        if _key == "quan_tri_pgd" and not tab_perm["co_quyen_upload_hstd"]:
            _tabs = [t for t in _tabs if "Upload HSTD" not in t[0]]
        for _label, _fn in _tabs:
            _tab_label_fns[_label] = _fn

    _all_labels = list(_tab_label_fns.keys())
    if not _all_labels:
        return

    active_label = state.nav_ws_op_menu
    if not active_label or active_label not in _tab_label_fns:
        active_label = _all_labels[0]
        state.nav_ws_op_menu = active_label

    active_fn = _tab_label_fns.get(active_label)
    if active_fn:
        try:
            active_fn(None)
        except Exception as e:
            logger.error("render_op: lỗi render %s — %s", active_label, e, exc_info=True)
            st.error(f"❌ Lỗi render **{active_label}**: {e}")
            import traceback
            st.code(traceback.format_exc())
    else:
        st.info(f"Tính năng **{active_label}** đang được phát triển.")