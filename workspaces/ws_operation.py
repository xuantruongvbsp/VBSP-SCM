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

    COT_TEN_KH, COT_MA_KH, COT_SO_KU, COT_TEN_CT, COT_MUC_VAY,

    COT_DU_NO_QH, COT_DU_NO_TH, COT_TONG_DU_NO, COT_NGAY_DH, COT_NGAY_VAY,

    COT_TEN_PGD, COT_SDT, COT_DIA_CHI,

    COT_LAI_TON, COT_LAI_THANG, COT_DVUT, COT_TEN_XA, COT_TEN_TO,

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



@st.cache_data(ttl=300, show_spinner=False)

def _kpi_pgd_list_cached(df_hash: str, pgd_user: str, _df: pd.DataFrame) -> list[dict]:

    """Cached version của _kpi_pgd_list — dùng df_hash làm key, _df không bị hash."""

    if _df is None or _df.empty:

        return []

    return _kpi_pgd_list_impl(_df, pgd_user)





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
            "delta":       None,
            "delta_label": "",
            "icon":        "🎯",
            "suffix":      "",
            "precision":   1,
            "help":        f"Tỷ lệ thực hiện kế hoạch tín dụng. KH năm: {fmt_ty(tong_kh)} triệu đồng",
            "delta_color": "normal",
        })

    except Exception as e:

        logger.error("_kpi_pgd_list KPI4: %s", e, exc_info=True)



    # ── KPI 5-8: Dư nợ Bình Quân ───────────────────────────────────────────

    try:

        # Đếm số lượng các nhóm

        so_xa = df_pgd[COT_TEN_XA].dropna().loc[lambda s: (s != "") & (s != "CỘNG")].nunique() if COT_TEN_XA in df_pgd.columns else 0

        so_hoi = df_pgd[COT_DVUT].nunique() if COT_DVUT in df_pgd.columns else 0

        so_to = df_pgd[COT_TEN_TO].nunique() if COT_TEN_TO in df_pgd.columns else 0

        tong_so_khoan = len(df_pgd)



        # KPI 5: Dư nợ BQ xã/phường

        dn_bq_xa = tong_dn / so_xa if so_xa > 0 else 0.0

        kpi.append({

            "label":       "Dư nợ BQ xã",

            "value":       fmt_ty(dn_bq_xa),

            "delta":       None,

            "delta_label": "",

            "icon":        "🏘️",

            "suffix":      "tr.đ",

            "precision":   0,

            "help":        f"Dư nợ bình quân trên mỗi xã/phường. Số xã: {fmt_so(so_xa)}",

            "delta_color": "normal",

        })



        # KPI 6: Dư nợ BQ hộ vay

        dn_bq_ho = tong_dn / tong_so_khoan if tong_so_khoan > 0 else 0.0

        kpi.append({

            "label":       "Dư nợ BQ hộ",

            "value":       fmt_ty(dn_bq_ho),

            "delta":       None,

            "delta_label": "",

            "icon":        "👥",

            "suffix":      "tr.đ",

            "precision":   0,

            "help":        f"Dư nợ bình quân trên mỗi khoản vay. Số khoản: {fmt_so(tong_so_khoan)}",

            "delta_color": "normal",

        })



        # KPI 7: Dư nợ BQ Hội (ĐVUT)

        dn_bq_hoi = tong_dn / so_hoi if so_hoi > 0 else 0.0

        kpi.append({

            "label":       "Dư nợ BQ Hội",

            "value":       fmt_ty(dn_bq_hoi),

            "delta":       None,

            "delta_label": "",

            "icon":        "🏛️",

            "suffix":      "tr.đ",

            "precision":   0,

            "help":        f"Dư nợ bình quân trên mỗi ĐVUT (Hội). Số Hội: {fmt_so(so_hoi)}",

            "delta_color": "normal",

        })



        # KPI 8: Dư nợ BQ tổ

        dn_bq_to = tong_dn / so_to if so_to > 0 else 0.0

        kpi.append({

            "label":       "Dư nợ BQ tổ",

            "value":       fmt_ty(dn_bq_to),

            "delta":       None,

            "delta_label": "",

            "icon":        "📊",

            "suffix":      "tr.đ",

            "precision":   0,

            "help":        f"Dư nợ bình quân trên mỗi tổ. Số tổ: {fmt_so(so_to)}",

            "delta_color": "normal",

        })



    except Exception as e:

        logger.error("_kpi_pgd_list KPI5-8 DNBQ: %s", e, exc_info=True)



    return kpi





def _kpi_pgd_list(df_pgd: pd.DataFrame, pgd_user: str) -> list[dict]:

    """

    Tính 8 KPI DeltaCard cho trang chủ / sidebar PGD.

    Wrapper có cache — tự động hash dataframe.



    Returns:

        List dict (kwargs cho delta_card), tối đa 8 phần tử.

    """

    if df_pgd is None or df_pgd.empty:

        return []

    

    df_hash = _df_hash(df_pgd)

    return _kpi_pgd_list_cached(df_hash, pgd_user, df_pgd)





# ═══════════════════════════════════════════════════════════════════════════════
_WS_OP_MENU_ITEMS = [
    # ── Tổng quan ──
    {"group": "Tổng quan", "label": "🏠 Trang Chủ"},
    {"group": "Tổng quan", "label": "📊 Dashboard Sức khỏe"},
    {"group": "Tổng quan", "label": "📍 Tổng quan ĐGD & Tổ TK&VV"},
    # ── Tác nghiệp ──
    {"group": "Tác nghiệp", "label": "📊 Thông tin chung"},
    {"group": "Tác nghiệp", "label": "📈 Tiến độ công việc"},
    {"group": "Tác nghiệp", "label": "🔍 Tra cứu hồ sơ"},
    {"group": "Tác nghiệp", "label": "📋 Danh sách & Lọc"},
    {"group": "Tác nghiệp", "label": "⏰ Đến hạn"},
    {"group": "Tác nghiệp", "label": "💵 Dự phóng Dòng tiền"},
    {"group": "Tác nghiệp", "label": "🔥 Heatmap Đáo hạn"},
    {"group": "Tác nghiệp", "label": "📉 Histogram Dư nợ"},
    {"group": "Tác nghiệp", "label": "🍩 Cơ cấu CT"},
    {"group": "Tác nghiệp", "label": "🔄 So sánh kỳ"},
    {"group": "Tác nghiệp", "label": "🏷️ Phân loại KH"},
    {"group": "Tác nghiệp", "label": "📄 Quản lý Template"},
    # ── Báo cáo ──
    {
        "group": "Báo cáo",
        "label": "📋 Báo cáo tín dụng",
        "children": [
            {"label": "📊 Báo cáo tín dụng"},
            {"label": "📅 Báo cáo định kỳ"},
            {"label": "📡 Điện báo"},
            {"label": "📝 Báo cáo Giao ban"},
            {"label": "📄 Trung tâm mẫu biểu"},
            {"label": "📋 Biên bản giao ban"},
            {"label": "📢 Thông báo kết luận"},
            {"label": "📋 Theo dõi nhập liệu"},
            {"label": "📥 Tiến độ nộp BC"},
            {"label": "✅ Checklist BC"},
        ],
    },
    # ── Kế hoạch ──
    {
        "group": "Kế hoạch",
        "label": "🎯 Kế hoạch tín dụng",
        "children": [
            {"label": "🎯 KHTD"},
            {"label": "⚖️ Kế hoạch/Cân đối"},
            {"label": "📋 Giao & ĐC KHTD"},
            {"label": "📋 Mẫu 07 Giao KH"},
            {"label": "🔭 Xây dựng KHTD TL"},
            {"label": "📋 NQ11"},
            {"label": "📊 Dashboard GQVL"},
            {"label": "📊 Xuất báo cáo KHTD"},
        ],
    },
    # ── Kiểm soát ──
    {
        "group": "Kiểm soát",
        "label": "🛡️ Kiểm soát chất lượng",
        "children": [
            {"label": "🚨 Cảnh báo Tín dụng"},
            {"label": "🔔 Đôn đốc KHĐ"},
            {"label": "⚡ Nợ đến hạn có nguy cơ"},
            {"label": "🚨 Cảnh báo sớm (Full)"},
            {"label": "✅ Checklist Nội bộ PGD"},
            {"label": "🔍 Kiểm soát Dữ liệu"},
            {"label": "👔 CBTD & Địa bàn"},
            {"label": "💳 Xử lý Rủi ro"},
            {"label": "📈 Phân tích NQH"},
            {"label": "📍 Điểm Giao Dịch"},
            {"label": "🏛️ Ban Đại Diện"},
            {"label": "🤝 Ủy thác"},
            {"label": "🏘️ Tổ TK&VV"},
            {"label": "📊 Tổng quan Nợ Khoanh"},
            {"label": "🔒 Quản lý Nợ Khoanh CV 368"},
        ],
    },
    # ── Công cụ ──
    {
        "group": "Công cụ",
        "label": "⚙️ Công cụ & Hệ thống",
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

    # ── Tra cứu nhanh — chỉ hợp lý ở phân hệ địa bàn ────────────────────
    st.markdown(
        "<p style='font-size:14px;font-weight:700;"
        "color:#94A3B8;margin-bottom:6px'>TRA CỨU NHANH</p>",
        unsafe_allow_html=True,
    )
    q = st.text_input(
        "🔍 Tìm khách hàng", placeholder="Tên / CMND / Khế ước...",
        key="ws_op_search_q", label_visibility="collapsed",
    )
    if q and len(q) >= 2:
        _df_s = df_pgd
        if _df_s is not None and not _df_s.empty:
            from config import COT_TEN_KH, COT_CMND, COT_SO_KU, COT_TEN_XA, COT_TONG_DU_NO
            _mask = pd.Series(False, index=_df_s.index)
            for _c in [COT_TEN_KH, COT_CMND, COT_SO_KU]:
                if _c in _df_s.columns:
                    _mask |= _df_s[_c].astype(str).str.contains(q, case=False, na=False)
            _hits = _df_s.loc[_mask, [c for c in [COT_TEN_KH, COT_CMND, COT_SO_KU, COT_TEN_XA, COT_TONG_DU_NO] if c in _df_s.columns]].head(30)
            if not _hits.empty:
                with st.expander(f"Tìm thấy {min(len(_hits), 30)}/{_mask.sum()} kết quả", expanded=True):
                    st.dataframe(_hits, use_container_width=True, height=min(300, len(_hits) * 40 + 50))
            else:
                st.caption("Không tìm thấy kết quả.")
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






















    # ── Định nghĩa nhóm tab ─────────────────────────────────────────────

    CAC_NHOM = {

        "trang_chu": {

            "label": "🏠 Trang Chủ",

            "tabs": [

                ("🏠 Trang Chủ", lambda tab: _lazy_tab("tab_trang_chu_pgd").render(tab, df=df_pgd, role=role, pgd_user=pgd_user)),
                ("📊 Dashboard Sức khỏe", lambda tab: _lazy_tab("tab_dashboard_suc_khoe_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role)),
                ("📍 Tổng quan ĐGD & Tổ TK&VV", lambda tab: _lazy_tab("tab_dashboard_dgd_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role, username=username)),
            ],
        },

        "nghiep_vu_pgd": {

            "label": "📋 Nghiệp vụ hàng ngày",

            "tabs": [

                ("📊 Thông tin chung", lambda tab: _lazy_tab("tab_tongquan").render(tab, **_pgd_df_kwargs)),

                ("📈 Tiến độ công việc", lambda tab: _lazy_tab("tab_tien_do").render(tab, **kwargs)),

                ("🔍 Tra cứu hồ sơ", lambda tab: _lazy_tab("tab_tracuu_v2").render(tab, **_pgd_df_kwargs)),

                ("📋 Danh sách & Lọc", lambda tab: _lazy_tab("tab_danhsach").render(tab, **kwargs)),

                ("⏰ Đến hạn", lambda tab: _lazy_tab("tab_den_han").render(tab, role=role, pgd_user=pgd_user)),

                ("📈 Dự phóng Dòng tiền", lambda tab: _lazy_tab("tab_du_phong_dong_tien_pgd").render(tab, **_pgd_df_kwargs)),

                ("🔥 Heatmap Đáo hạn", lambda tab: _lazy_tab("tab_heatmap_dao_han_pgd").render(tab, **_pgd_df_kwargs)),

                ("📊 Histogram Dư nợ", lambda tab: _lazy_tab("tab_histogram_du_no_pgd").render(tab, **_pgd_df_kwargs)),

                ("🍩 Cơ cấu CT", lambda tab: _lazy_tab("tab_donut_co_cau_pgd").render(tab, **_pgd_df_kwargs)),

                ("📊 So sánh kỳ", lambda tab: _lazy_tab("tab_so_sanh_ky").render(

                    tab, df=df_pgd, df_full=df_pgd, role=role, username=username,

                    pgd_user=pgd_user, pgd_mode=True,

                )),

                ("📄 Quản lý Template", lambda tab: _lazy_tab("tab_template_pgd").render(tab, **kwargs)),

                ("🏷️ Phân loại KH", lambda tab: _lazy_tab("tab_phan_loai_kh").render(tab, **_pgd_df_kwargs)),

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

                ("📝 Báo cáo Giao ban", lambda tab: _lazy_tab("tab_bao_cao_giao_ban_pgd").render(tab, **kwargs)),

                ("📄 Trung tâm mẫu biểu",       lambda tab: _lazy_tab("tab_doc_hub").render(tab, df=df, df_nq11=df_nq11, role=role, pgd_user=pgd_user)),

                ("📋 Biên bản giao ban",         lambda tab: _lazy_tab("tab_bien_ban_giao_ban").render(tab, **kwargs)),

                ("📢 Thông báo kết luận",        lambda tab: _lazy_tab("tab_thong_bao_ket_luan").render(tab, **kwargs)),

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
                ("📊 Xuất báo cáo KHTD", lambda tab: _lazy_tab("tab_khtd_xuat").render_xuat_baocao(role=role, username=username, df_full=df_pgd)),
            ],
        },
        "kiem_soat_rr": {

            "label": "🔍 Kiểm soát & Rủi ro",

            "tabs": [

                ("🚨 Cảnh báo Tín dụng", lambda tab: _lazy_tab("tab_canh_bao_nqh").render(tab, **_pgd_df_kwargs)),

                ("🔔 Đôn đốc KHĐ", lambda tab: _lazy_tab("tab_don_doc_khd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role)),

                ("⚡ Nợ đến hạn có nguy cơ", lambda tab: _lazy_tab("tab_canh_bao_som").render(tab, **kwargs)),

                ("🚨 Cảnh báo sớm (Full)", lambda tab: _lazy_tab("tab_canh_bao_som_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role, username=username)),

                ("✅ Checklist Nội bộ PGD", lambda tab: _lazy_tab("tab_kiem_soat_noi_bo_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role)),

                ("🔍 Kiểm soát Dữ liệu", lambda tab: _lazy_tab("tab_kiem_soat_du_lieu_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "", role=role, username=username)),

                ("👔 CBTD & Địa bàn", lambda tab: _lazy_tab("tab_cbtd").render(

                    tab, df=df_pgd, role=role, username=username, pgd_user=pgd_user or pgd_filter or ""

                )),

                ("💳 Xử lý Rủi ro", lambda tab: _lazy_tab("tab_xu_ly_rui_ro").render(
                    tab, df=df_pgd, role=role, username=username, pgd_user=pgd_user or pgd_filter
                )),
                ("📈 Phân tích NQH", lambda tab: _lazy_tab("tab_phan_tich_nqh_pgd").render(tab, df=df_pgd, pgd_user=pgd_user or pgd_filter or "")),
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