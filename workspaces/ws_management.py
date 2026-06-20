"""
Không gian Điều hành (Management View)
───────────────────────────────────────
Dành cho Lãnh đạo phòng KH-NV — Giám sát NQH theo địa bàn,
quản lý chỉ tiêu, cân đối nguồn vốn.
"""


from logger import get_logger
logger = get_logger(__name__)

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import db

from state_manager import SCMStateManager
from config import (
    COT_TEN_PGD, COT_MA_KH, COT_SO_KU, COT_TEN_KH,
    COT_DU_NO_QH, COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT,
    COT_NGAY_DH, COT_TINH_TRANG, COT_SDT,
    COT_LAI_TON, COT_LAI_TON_QH, COT_LAI_THANG, COT_DVUT, COT_MUC_VAY,
    COT_NGAY_VAY, COT_THOI_HAN, COT_LAI_SUAT,
    TEMPLATES_DIR, TAG_MAP,
)
from auth import is_cn_role, is_pgd_role, get_permissions, normalize_role, la_phan_he_cn
from data import (
    danh_dau_khong_hd, danh_dau_khong_hd_cached,
    tong_hop_khong_hd, tong_hop_khong_hd_cached,
    ds_chi_tiet_khong_hd, canh_bao_migration, canh_bao_migration_cached,
)
from utils import (
    fmt,
    fmt_so,
    fmt_ty,
    vn,
    xuat_excel,
    quet_templates,
    auto_fill_klgb,
    auto_fill_document,
    hien_thi_dataframe_phan_trang,
    lazy_tabs,
)
from services.excel_service import xuat_excel_chuyen_nghiep, ten_file_xuat as excel_ten_file
from pdf_service import render_huong_dan, xuat_pdf_group_header
from components.delta_card import delta_card, kpi_row
from components.loan_drawer import loan_detail_drawer
from components.filter_bar import filter_bar, apply_filters
from components.export_pdf import download_pdf_button, xuat_pdf_co_chart


@st.cache_resource
def _get_tab(name: str):
    """Import tab module — dùng sys.modules cache của Python, tự invalidate khi Streamlit hot-reload."""
    import importlib
    try:
        return importlib.import_module(f"tabs.{name}")
    except ModuleNotFoundError:
        import tabs
        return getattr(tabs, name)








def _render_cbtd_dia_ban(tab_parent=None, **kw):
    """Nhóm CBTD & Địa bàn — 4 sub-tab: Dashboard · CBTD · ĐGD · Tổ TK&VV."""
    if tab_parent is not None:
        ctx = tab_parent
    else:
        ctx = st.container()
    with ctx:
        lazy_tabs(
            ["📊 Dashboard", "👔 Cán bộ tín dụng", "📍 Điểm Giao Dịch", "🏘️ Tổ TK&VV"],
            [
                lambda c: _get_tab("tab_cbtd_dashboard").render(c, **kw),
                lambda c: _get_tab("tab_cbtd").render(c, **kw),
                lambda c: _get_tab("tab_quan_ly_dgd").render(c, **kw),
                lambda c: _get_tab("tab_cdtotkvv").render(c, **dict(kw, cdto_mode="cn")),
            ],
            key="mgmt_cbtd",
        )






def _banner_hstd_cu(threshold_days: int = 7) -> None:
    """Banner cảnh báo dữ liệu HSTD tổng hợp (do Phòng KH-NV upload) chưa cập nhật."""
    from services.upload_service import lay_meta_merge
    meta = lay_meta_merge("hstd")
    if not meta:
        st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload file tại tab **Upload dữ liệu**.")
        return
    try:
        last_update = datetime.fromisoformat(meta["thoi_gian"])
        age_days = (datetime.now() - last_update).days
    except Exception:
        return
    if age_days >= threshold_days:
        st.warning(
            f"⚠️ Dữ liệu HSTD đã **{age_days} ngày** chưa cập nhật "
            f"(lần cuối: {last_update.strftime('%d/%m/%Y %H:%M')}). "
            "Vui lòng upload file mới tại tab **Upload dữ liệu**."
        )


@st.cache_data(show_spinner=False, ttl=300)
def _doc_nqh_delta_snapshot() -> pd.DataFrame:
    """Lấy delta NQH giữa 2 kỳ gần nhất từ hstd_snapshot."""
    import sqlite3
    from db import get_conn
    with get_conn() as conn:
        ky_list = [r[0] for r in conn.execute(
            "SELECT DISTINCT ky FROM hstd_snapshot ORDER BY ky DESC LIMIT 2"
        ).fetchall()]
    if len(ky_list) < 2:
        return pd.DataFrame()
    ky_curr, ky_prev = ky_list[0], ky_list[1]
    with get_conn() as conn:
        df_curr = pd.read_sql_query(
            "SELECT ten_pgd, SUM(du_no_qh) as qh_curr, SUM(tong_du_no) as dn_curr "
            "FROM hstd_snapshot WHERE ky=? GROUP BY ten_pgd",
            conn, params=(ky_curr,),
        )
        df_prev = pd.read_sql_query(
            "SELECT ten_pgd, SUM(du_no_qh) as qh_prev, SUM(tong_du_no) as dn_prev "
            "FROM hstd_snapshot WHERE ky=? GROUP BY ten_pgd",
            conn, params=(ky_prev,),
        )
    df = df_curr.merge(df_prev, on="ten_pgd", how="left").fillna(0)
    df["delta_qh"] = df["qh_curr"] - df["qh_prev"]
    df["pct_qh"] = df["delta_qh"] / df["qh_prev"].replace(0, float("nan")) * 100
    df["ky_curr"] = ky_curr
    df["ky_prev"] = ky_prev
    return df


def _render_nqh_tang_dot_bien(key_prefix: str = "nqh_db_") -> None:
    """Hiển thị bảng NQH tăng đột biến dựa trên hstd_snapshot."""
    from utils import fmt_ty as _fmt_ty, fmt_so as _fmt_so

    df = _doc_nqh_delta_snapshot()
    if df.empty:
        st.info("ℹ️ Chưa đủ 2 kỳ snapshot để so sánh. Hãy merge HSTD ít nhất 2 lần.")
        return

    ky_curr = df["ky_curr"].iloc[0]
    ky_prev = df["ky_prev"].iloc[0]
    st.caption(f"So sánh kỳ **{ky_curr}** vs **{ky_prev}**")

    df_show = df[df["ten_pgd"] != "Hội sở Chi nhánh tỉnh"].copy() if len(df) > 1 else df.copy()
    df_show = df_show.sort_values("delta_qh", ascending=False)

    tang = df_show[df_show["delta_qh"] > 0]
    giam = df_show[df_show["delta_qh"] < 0]

    c1, c2 = st.columns(2)
    c1.metric("PGD có NQH tăng", len(tang), delta=f"{len(tang)} đơn vị", delta_color="inverse" if len(tang) else "off")
    c2.metric("PGD có NQH giảm", len(giam), delta=f"{len(giam)} đơn vị", delta_color="normal" if len(giam) else "off")

    cols_display = {
        "ten_pgd": "PGD",
        "qh_prev": f"NQH kỳ {ky_prev} (triệu)",
        "qh_curr": f"NQH kỳ {ky_curr} (triệu)",
        "delta_qh": "Tăng/Giảm (triệu)",
        "pct_qh": "% thay đổi",
    }
    df_out = df_show[list(cols_display.keys())].rename(columns=cols_display).copy()
    for col in [f"NQH kỳ {ky_prev} (triệu)", f"NQH kỳ {ky_curr} (triệu)", "Tăng/Giảm (triệu)"]:
        if col in df_out.columns:
            df_out[col] = df_out[col].apply(_fmt_ty)
    df_out["% thay đổi"] = df_out["% thay đổi"].apply(
        lambda x: f"+{x:.1f}".replace(".", ",") + "%" if x > 0 else (f"{x:.1f}".replace(".", ",") + "%" if not pd.isna(x) else "—")
    )
    st.dataframe(df_out, use_container_width=True, height=500)


def _build_all_items(role: str, username: str, **kwargs) -> list:
    """Xây danh sách ALL_ITEMS — dùng chung cho sidebar và render."""
    # Đảm bảo mọi lambda dùng **kwargs đều có đủ role và username
    kwargs.setdefault("role", role)
    kwargs.setdefault("username", username)
    df_full = kwargs.get("df_full")
    ds_pgd_all = kwargs.get("ds_pgd_all", [])
    can_upload = kwargs.get("can_upload", False)
    role_n = normalize_role(str(role or "user"))

    ALL_ITEMS = [
        # ── Tổng quan ──────────────────────────────────────────────────────────
        {"group": "Tổng quan", "label": "📊 Thông tin chung",      "icon": "info-circle",  "fn": lambda: _get_tab("tab_tongquan").render(None, **kwargs)},
        {"group": "Tổng quan", "label": "🏢 Toàn cảnh 22 PGD",    "icon": "grid",         "fn": lambda: _get_tab("tab_pgd_cards").render(None, **kwargs)},
        {"group": "Tổng quan", "label": "🔍 Tra cứu Khách hàng",  "icon": "search",       "fn": lambda: _get_tab("tab_tracuu_v2").render(None, **kwargs)},

        # ── Nội bộ Phòng KH-NV ─────────────────────────────────────────────────
        {"group": "Nội bộ Phòng", "label": "🗂️ Nội bộ Phòng KH-NV",             "icon": "users",    "fn": lambda: _get_tab("tab_khnv_noi_bo").render(None, **kwargs)},
        {"group": "Nội bộ Phòng", "label": "📋 Quản lý Công văn",                "icon": "file-text","fn": lambda: _get_tab("tab_quan_ly_cong_van").render(None, **kwargs)},
        {"group": "Nội bộ Phòng", "label": "📝 Quản lý Công việc & Nhiệm vụ",   "icon": "layout",   "fn": lambda: _get_tab("tab_quan_ly_cv").render(None, **kwargs)},

        # ── Giám sát ───────────────────────────────────────────────────────────
        {"group": "Giám sát", "label": "⚠️ Cảnh báo Tín dụng",    "icon": "alert-triangle","fn": lambda: _get_tab("tab_canh_bao_nqh").render(None, role=role, username=username, df_full=df_full, ds_pgd_all=ds_pgd_all)},
        {"group": "Giám sát", "label": "📊 So sánh kỳ",            "icon": "chart-line",    "fn": lambda: _get_tab("tab_so_sanh_ky").render(None, **kwargs)},
        {"group": "Giám sát", "label": "🔴 NQH tăng đột biến",     "icon": "trending-up",   "fn": lambda: _render_nqh_tang_dot_bien()},
        {"group": "Giám sát", "label": "🛡️ Chất lượng Dữ liệu",   "icon": "shield-check",  "fn": lambda: _get_tab("tab_data_quality").render(None, **kwargs)},
        {"group": "Giám sát", "label": "🏠 Phân kỳ NXH",           "icon": "home",          "fn": lambda: _get_tab("tab_phan_ky_nxh").render(None, **kwargs)},
        {"group": "Giám sát", "label": "🏷️ Phân loại Khách hàng", "icon": "tag",           "fn": lambda: _get_tab("tab_phan_loai_kh").render(None, **kwargs)},
        {"group": "Giám sát", "label": "🧪 Stress Test Danh mục", "icon": "flask",         "fn": lambda: _get_tab("tab_stress_test").render(None, **kwargs)},

        # ── Kiểm soát ──────────────────────────────────────────────────────────
        {"group": "Kiểm soát", "label": "🔎 Kiểm soát nội bộ",         "icon": "search",       "fn": lambda: _get_tab("tab_kiem_soat").render_tab(df_full, role, kwargs.get("username", "unknown"))},
        {"group": "Kiểm soát", "label": "🔍 Kiểm toán Nội bộ (KTNB)", "icon": "file-search",  "fn": lambda: _get_tab("tab_ktnb").render(None, **kwargs)},
        {"group": "Kiểm soát", "label": "⚡ Xử lý Rủi ro",             "icon": "alert-circle", "fn": lambda: _get_tab("tab_xu_ly_rui_ro").render(None, **kwargs)},
        {
            "group": "Kiểm soát",
            "label": "🔒 Nợ Khoanh",
            "icon": "lock",
            "children": [
                {"label": "📊 Tổng quan Nợ Khoanh",           "fn": lambda: _get_tab("tab_no_khoanh").render(None, **{**kwargs, "nhom": "tongquan"})},
                {"label": "🔒 Quản lý Nợ Khoanh theo CV 368", "fn": lambda: _get_tab("tab_no_khoanh").render(None, **{**kwargs, "nhom": "cv368"})},
            ],
        },

        # ── Kế hoạch Tín dụng ──────────────────────────────────────────────────
        {"group": "Kế hoạch Tín dụng", "label": "📈 Kế hoạch tín dụng",       "icon": "file-text",   "fn": lambda: _get_tab("tab_khtd").render(None, **dict(kwargs, khtd_mode="cn"))},
        {"group": "Kế hoạch Tín dụng", "label": "📋 Giao & ĐC KHTD",          "icon": "upload",       "fn": lambda: _get_tab("tab_khtd_giao_dc").render(None, **kwargs)},
        {"group": "Kế hoạch Tín dụng", "label": "🔭 Xây dựng KHTD 1-3-5 năm","icon": "calendar-plus","fn": lambda: _get_tab("tab_xay_dung_khtd").render(None, **kwargs)},
        {"group": "Kế hoạch Tín dụng", "label": "📡 Điện báo & KH vs TH",     "icon": "antenna",      "fn": lambda: _get_tab("tab_candoi").render(None, **kwargs)},
        {"group": "Kế hoạch Tín dụng", "label": "📤 Xuất báo cáo KHTD",       "icon": "file-export",  "fn": lambda: _get_tab("tab_khtd_xuat").render_xuat_baocao(role=kwargs.get("role", ""), username=kwargs.get("username", ""), df_full=kwargs.get("df"))},
        {"group": "Kế hoạch Tín dụng", "label": "🏦 Nguồn vốn địa phương",    "icon": "bank",         "fn": lambda: _get_tab("tab_hhi").render(None, **kwargs)},

        # ── Báo cáo ────────────────────────────────────────────────────────────
        {"group": "Báo cáo", "label": "📊 Báo cáo tín dụng",    "icon": "file",          "fn": lambda: _get_tab("tab_baocao").render(None, **kwargs)},
        {"group": "Báo cáo", "label": "⏰ Nợ Đến Hạn",           "icon": "clock",         "fn": lambda: _get_tab("tab_canh_bao_nqh").render(None, role=role, username=username, df_full=df_full, ds_pgd_all=ds_pgd_all)},
        {"group": "Báo cáo", "label": "📅 Báo cáo định kỳ",      "icon": "calendar",      "fn": lambda: _get_tab("tab_bao_cao_dinh_ky").render(None, **kwargs)},
        {"group": "Báo cáo", "label": "📄 Báo cáo KHNV",         "icon": "file-report",   "fn": lambda: _get_tab("tab_khnv_bao_cao").render(None, **kwargs)},
        {"group": "Báo cáo", "label": "📥 Tiến độ nộp BC",       "icon": "inbox",         "fn": lambda: _get_tab("tab_tien_do_nop").render(None, **kwargs)},

        # ── Ủy Thác ────────────────────────────────────────────────────────────
        {"group": "Ủy Thác", "label": "🏛️ Ban Đại Diện",  "icon": "building",  "fn": lambda: _get_tab("tab_ban_dai_dien").render(None, cap="tinh", **kwargs)},
        {"group": "Ủy Thác", "label": "🤝 Ủy thác",        "icon": "handshake", "fn": lambda: _get_tab("tab_uy_thac").render(None, **kwargs)},
        {"group": "Ủy Thác", "label": "👔 CBTD & Địa bàn", "icon": "user",      "fn": lambda: _render_cbtd_dia_ban(None, **kwargs)},
    ]

    if can_upload:
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Template văn bản", "icon": "template", "fn": lambda: _get_tab("tab_quan_ly_template").render(None, df=df_full)})
    if role_n in ("admin_cn", "manager_cn"):
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Mã NĐT địa phương", "icon": "building-bank", "fn": lambda: _get_tab("tab_quan_ly_ndt_dp").render(None, role=role_n, username=kwargs.get("username", "unknown"))})
    if role_n == "admin_cn":
        ALL_ITEMS.append({"group": "Hệ thống", "label": "Nhật ký hệ thống", "icon": "list", "fn": lambda: _get_tab("tab_audit_log").render(None, **kwargs)})
        ALL_ITEMS.append({"group": "Hệ thống", "label": "🔐 Quản lý bảo mật", "icon": "shield", "fn": lambda: _get_tab("tab_security").render(None, **kwargs)})
        ALL_ITEMS.append({"group": "Hệ thống", "label": "🤖 Bot Telegram", "icon": "message", "fn": lambda: _get_tab("tab_telegram_admin").render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "🔍 Trạng thái hệ thống", "icon": "pulse", "fn": lambda: _get_tab("tab_trang_thai_nguon").render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "Upload dữ liệu", "icon": "upload", "fn": lambda: _get_tab("tab_upload_khnv").render(None, **kwargs)})
    ALL_ITEMS.append({"group": "Hệ thống", "label": "📖 Hướng dẫn", "icon": "book", "fn": lambda: render_huong_dan()})

    return ALL_ITEMS


def render_sidebar_menu(role: str, username: str, **kwargs):
    """Render menu ĐIỀU HÀNH — gọi từ app.py bên trong with st.sidebar.
    Tối ưu: dùng st.radio() theo nhóm thay cho ~25 st.button() riêng lẻ."""

    state = SCMStateManager()
    GROUP_COLORS = {
        "Tổng quan":         {"bg": "#0D2137", "border": "#90CAF9", "text": "#90CAF9"},
        "Nội bộ Phòng":      {"bg": "#0D2818", "border": "#80CBC4", "text": "#80CBC4"},
        "Giám sát":          {"bg": "#0D2137", "border": "#64B5F6", "text": "#90CAF9"},
        "Kiểm soát":         {"bg": "#2D0D14", "border": "#EF9A9A", "text": "#F48FB1"},
        "Kế hoạch Tín dụng": {"bg": "#0D2818", "border": "#A5D6A7", "text": "#A5D6A7"},
        "Báo cáo":           {"bg": "#2D1F0D", "border": "#FFCC80", "text": "#FFD54F"},
        "Ủy Thác":           {"bg": "#1A1040", "border": "#CE93D8", "text": "#CE93D8"},
        "Hệ thống":          {"bg": "#1E2130", "border": "#94A3B8", "text": "#B0BEC5"},
    }

    all_items = _build_all_items(role, username, **kwargs)
    if not all_items:
        return

    valid_labels = [x["label"] for x in all_items] + [
        c["label"] for x in all_items for c in x.get("children", [])
    ]

    default_label = all_items[0]["label"]
    active_label = state.nav_ws_mgmt_menu
    if active_label not in valid_labels:
        state.nav_ws_mgmt_menu = default_label
        active_label = default_label

    st.divider()

    st.markdown(
        "<p style='font-size:14px;font-weight:700;"
        "color:#94A3B8;margin-bottom:6px'>MENU ĐIỀU HÀNH</p>",
        unsafe_allow_html=True
    )

    groups = []
    current_grp = None
    cur_flat = []
    cur_acc = []
    for item in all_items:
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

    for grp_name, flat_items, acc_items in groups:
        clr = GROUP_COLORS.get(grp_name, {"bg": "#F1EFE8", "border": "#888", "text": "#444"})

        st.markdown(
            f"<p style='font-size:11px;font-weight:700;"
            f"color:{clr['text']};text-transform:uppercase;"
            f"letter-spacing:0.06em;padding:12px 4px 4px;margin:0'>"
            f"{grp_name}</p>",
            unsafe_allow_html=True,
        )

        for item in flat_items:
            lbl = item["label"]
            if lbl == active_label:
                st.markdown(
                    f"<div style='"
                    f"background:linear-gradient(135deg,#1565C0,#1976D2);"
                    f"border-left:4px solid #0D47A1;"
                    f"color:#FFFFFF;font-size:14px;font-weight:700;"
                    f"padding:10px 12px;border-radius:0 8px 8px 0;margin-bottom:4px;"
                    f"box-shadow:0 2px 8px rgba(21,101,192,0.35)'>"
                    f"\u25b6 {lbl}</div>",
                    unsafe_allow_html=True,
                )
            else:
                if st.button(lbl, key=f"menu_btn_{lbl}", use_container_width=True):
                    state.nav_ws_mgmt_menu = lbl
                    st.rerun()

        for item in acc_items:
            children = item.get("children", [])
            child_labels = [c["label"] for c in children]
            is_child_active = active_label in child_labels
            open_key = f"ws_mgmt_acc_{item['label']}"

            if is_child_active and not st.session_state.get(open_key):
                st.session_state[open_key] = True

            is_open = st.session_state.get(open_key, False)

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
                    key=f"menu_acc_{item['label']}",
                    use_container_width=True,
                ):
                    st.session_state[open_key] = not is_open
                    st.rerun()

            if is_open:
                for child in children:
                    clbl = child["label"]
                    if clbl == active_label:
                        st.markdown(
                            f"<div style='"
                            f"background:linear-gradient(135deg,#1565C0,#1976D2);"
                            f"border-left:4px solid #0D47A1;"
                            f"color:#FFFFFF;font-size:13px;font-weight:700;"
                            f"padding:8px 12px 8px 20px;border-radius:0 8px 8px 0;margin-bottom:3px'>"
                            f"\u25b6 {clbl}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        if st.button(clbl, key=f"menu_btn_{clbl}", use_container_width=True):
                            state.nav_ws_mgmt_menu = clbl
                            st.rerun()

def render(**kwargs):
    _wl = st.session_state.pop("_data_load_warning", None)
    if _wl:
        st.warning(_wl)

    def _tab_so_sanh_ky_fn(**kw):
        _get_tab("tab_so_sanh_ky").render(None, **kw)

    role       = kwargs.get("role")
    username   = kwargs.get("username", "unknown")
    df         = kwargs.get("df")
    df_full    = kwargs.get("df_full", df)
    ds_pgd_all = kwargs.get("ds_pgd_all", [])
    role_n = normalize_role(str(role or "user"))
    can_upload = get_permissions(role_n)["can_upload"]
    can_manage_users = get_permissions(role_n)["can_manage_users"]

    st.title("📋 Phòng KH-NV")
    st.caption("Giám sát chỉ tiêu · Cân đối vốn · Quản lý NQH · GQVL · Quản lý CBTD")

    _banner_hstd_cu()

    filtered_kw = {k: v for k, v in kwargs.items()
                   if k not in ("role", "username", "df", "df_full", "ds_pgd_all")}
    _data_id = id(df_full)
    if "_mgmt_all_items_cache" not in st.session_state or st.session_state.get("_mgmt_all_items_data_id") != _data_id:
        ALL_ITEMS = _build_all_items(
            role, username,
            df=df, df_full=df_full, ds_pgd_all=ds_pgd_all,
            can_upload=can_upload, **filtered_kw
        )
        st.session_state["_mgmt_all_items_cache"] = ALL_ITEMS
        st.session_state["_mgmt_all_items_data_id"] = _data_id
    else:
        ALL_ITEMS = st.session_state["_mgmt_all_items_cache"]

    # ── Navigation: điều hướng hoàn toàn qua sidebar (render_sidebar_menu) ──
    valid_labels = [x["label"] for x in ALL_ITEMS] + [
        c["label"] for x in ALL_ITEMS for c in x.get("children", [])
    ]

    # Handle jump từ shortcut / nút điều hướng ngoài ws_management
    state = SCMStateManager()
    jump_label = state.nav_ws_mgmt_jump
    if jump_label and jump_label in valid_labels:
        state.nav_ws_mgmt_menu = jump_label
        st.toast(f"✨ Đã chuyển tới: {jump_label}", icon="👆")

    # Khởi tạo / validate ws_mgmt_menu — khôi phục từ kv_store nếu session mới
    active_label = state.nav_ws_mgmt_menu
    _mem_key = f"nav_ws_mgmt_{username}"
    if not active_label or active_label not in valid_labels:
        _saved = db.doc_kv(_mem_key)
        if _saved and _saved in valid_labels:
            active_label = _saved
        else:
            active_label = ALL_ITEMS[0]["label"]
        state.nav_ws_mgmt_menu = active_label
    else:
        _prev_saved = db.doc_kv(_mem_key)
        if _prev_saved != active_label:
            db.ghi_kv(_mem_key, active_label, username)

    # ── Render DUY NHẤT mục đang chọn ────────────────────────────────────
    active_item = next((x for x in ALL_ITEMS if x["label"] == active_label), None)
    if active_item and active_item.get("fn"):
        try:
            active_item["fn"]()
        except Exception as e:  # conv: skip
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            import traceback
            st.error(f"❌ Lỗi render **{active_label}**: {e}")
            st.code(traceback.format_exc())
    else:
        # Tìm trong children (accordion)
        found_child = False
        for parent in ALL_ITEMS:
            for child in parent.get("children", []):
                if child["label"] == active_label:
                    try:
                        child["fn"]()
                    except Exception as e:  # conv: skip
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        import traceback

                        st.error(f"❌ Lỗi render **{active_label}**: {e}")
                        st.code(traceback.format_exc())
                    found_child = True
                    break
            if found_child:
                break
        if not found_child:
            st.info(f"Tính năng **{active_label}** đang được phát triển.")
