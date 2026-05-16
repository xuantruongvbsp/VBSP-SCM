"""
VBSP-SCM — Hệ thống Quản trị & Tác nghiệp Tín dụng Nội bộ
Kiến trúc 3 Không gian làm việc: Executive | Management | Operation
"""
import os
import time
from datetime import datetime, date
import streamlit as st

import duckdb
import pandas as pd

from config import (
    FILE_PATH, FILE_PATH_NQ11, FILE_PATH_DB, FILE_PATH_DB_PREV,
    FILE_PATH_SK_GQVL, CACHE_SK_GQVL,
    TEN_FILE, TEN_FILE_NQ11, TEN_FILE_DB, TEN_FILE_DB_PREV,
    COT_TEN_PGD, COT_MA_KH, COT_NGAY_SL, WORKSPACE_MAP,
    CACHE_HSTD, CACHE_NQ11, DON_VI_CHI_NHANH,
    DS_PGD as _DS_PGD_DEFAULT,
    PGD_XA_MAP as _PGD_XA_MAP_DEFAULT,
)
from data import ts_file, doc_file, doc_file_nq11, doc_file_sk_gqvl
from data.pgd import (
    duong_dan_pgd,
    doc_hstd_pgd,
    doc_nq11_pgd,
    doc_hstd_toan_cn_pgd,
    doc_nq11_toan_cn_pgd,
)
from utils import lay_config
import auth
from auth import LOGO_NHCSXH_B64 as LOGO_B64, normalize_role
import workspaces
import db
from widgets.status_widget import render_status_compact
from alert_center import render_alert_sidebar


@st.cache_resource(show_spinner=False, ttl=3600)
def _load_hstd(cache_path: str, _ts: float) -> pd.DataFrame:
    return duckdb.query(f"SELECT * FROM '{cache_path}'").df()


@st.cache_resource(show_spinner=False, ttl=3600)
def _load_nq11(cache_path: str, _ts: float) -> pd.DataFrame:
    return duckdb.query(f"SELECT * FROM '{cache_path}'").df()


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VBSP-SCM | Tín dụng Nội bộ",
    page_icon="🏦", layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS (inject 1 lần) ─────────────────────────────────────────────────
if "_css_injected" not in st.session_state:
    st.markdown("""<style>
/* ── 1. TYPOGRAPHY ── */
html, body, [class*="css"] {
    font-size: 15px !important;
    font-family: "Inter", "Segoe UI", system-ui, sans-serif !important;
    line-height: 1.65 !important;
    color: #1e2a3a !important;
}
h1 { font-size: 1.55rem !important; font-weight: 700 !important; color: #0d2137 !important; letter-spacing: -0.3px !important; }
h2 { font-size: 1.3rem  !important; font-weight: 700 !important; color: #0d2137 !important; }
h3 { font-size: 1.1rem  !important; font-weight: 600 !important; color: #1a3a5c !important; }
[data-testid="stMarkdownContainer"] p  { font-size: 0.97rem !important; color: #2c3e50 !important; }
[data-testid="stCaptionContainer"]  p  { font-size: 0.84rem !important; color: #6b7a8d !important; }

/* ── 2. NỀN TỔNG THỂ ── */
[data-testid="stAppViewContainer"] > .main { background: #f0f4f8 !important; }
.block-container { padding: 1.5rem 2rem 2rem !important; max-width: 1400px !important; }

/* ── 3. SIDEBAR — Dark Green NHCSXH ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1B5E20 0%, #2E7D32 55%, #388E3C 100%) !important;
    border-right: none !important;
    box-shadow: 4px 0 16px rgba(0,0,0,0.18) !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #FFFFFF !important;
    font-weight: 700;
}

[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown p {
    color: rgba(255,255,255,0.85) !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: rgba(255,255,255,0.8) !important;
}

[data-testid="stSidebar"] .stButton > button {
    background-color: #1565C0 !important;
    color: #FFFFFF !important;
    border: 1.5px solid #0D47A1 !important;
    border-radius: 10px;
    width: 100%;
    text-align: left;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 4px;
    transition: all 0.2s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #1976D2 !important;
    border-color: #1565C0 !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    transform: translateX(2px);
}

[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #E65100 !important;
    color: #FFFFFF !important;
    border-color: #E65100 !important;
    box-shadow: 0 3px 10px rgba(230,81,0,0.3);
    font-weight: 600;
}

[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.2);
    margin: 12px 0;
}

[data-testid="stSidebar"] .stAlert {
    background-color: rgba(0,0,0,0.15);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 8px;
    font-size: 12px;
}

/* ── 4. Main area ── */
.main .block-container {
    background-color: #FAFAFA;
    padding-top: 1.5rem;
}

header[data-testid="stHeader"] {
    background-color: #FFFFFF;
    border-bottom: 2px solid #C8E6C9;
}

/* ── 5. TABS ── */
[data-testid="stTabs"] { background: white !important; border-radius: 12px !important;
    padding: 0 8px !important; box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important; }
[data-testid="stTabs"] button[role="tab"] {
    font-size: 0.88rem !important; font-weight: 600 !important;
    padding: 10px 16px !important; color: #5a6a7a !important;
    border-radius: 0 !important; transition: color 0.2s !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #2E7D32 !important;
    border-bottom: 3px solid #2E7D32 !important;
    background: transparent !important;
}
[data-testid="stTabs"] button[role="tab"]:hover { color: #2E7D32 !important; }

/* ── 6. EXPANDER (card-style) ── */
[data-testid="stExpander"] {
    background: white !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    margin-bottom: 12px !important;
}
[data-testid="stExpander"] summary {
    font-size: 0.95rem !important; font-weight: 600 !important;
    color: #1a3a5c !important; padding: 12px 16px !important;
}

/* ── 7. METRIC (KPI card) ── */
[data-testid="stMetric"] {
    background: white !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05) !important;
}
[data-testid="stMetric"] label {
    font-size: 0.8rem !important; color: #6b7a8d !important;
    font-weight: 500 !important; text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important; font-weight: 700 !important;
    color: #0d2137 !important;
}

/* ── 8. DATAFRAME ── */
[data-testid="stDataFrame"] {
    border-radius: 10px !important; overflow: hidden !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
[data-testid="stDataFrame"] th {
    background: #2E7D32 !important; color: white !important;
    font-size: 0.85rem !important; font-weight: 600 !important;
    padding: 10px 12px !important; letter-spacing: 0.3px !important;
}
[data-testid="stDataFrame"] td {
    font-size: 0.9rem !important; padding: 8px 12px !important;
    border-bottom: 1px solid #f1f5f9 !important;
}

/* ── 9. INPUT / SELECTBOX / NUMBER INPUT ── */
[data-testid="stSelectbox"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextInput"]  label,
[data-testid="stFileUploader"] label {
    font-size: 0.88rem !important; font-weight: 600 !important;
    color: #3d5166 !important; margin-bottom: 4px !important;
}
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"]   input {
    border: 1.5px solid #d0d9e4 !important;
    border-radius: 8px !important;
    font-size: 0.95rem !important;
    padding: 8px 12px !important;
    background: #fafcff !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextInput"]   input:focus {
    border-color: #2E7D32 !important;
    box-shadow: 0 0 0 3px rgba(46,125,50,0.12) !important;
    outline: none !important;
    background: white !important;
}

/* ── 10. BUTTON ── */
.stButton > button {
    font-size: 0.9rem !important; font-weight: 600 !important;
    padding: 8px 20px !important; border-radius: 8px !important;
    border: 1.5px solid #d0d9e4 !important;
    background: white !important; color: #2c3e50 !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    border-color: #2E7D32 !important; color: #2E7D32 !important;
    box-shadow: 0 2px 8px rgba(46,125,50,0.15) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2E7D32, #43A047) !important;
    color: white !important; border: none !important;
    box-shadow: 0 3px 10px rgba(46,125,50,0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1B5E20, #2E7D32) !important;
    box-shadow: 0 4px 14px rgba(46,125,50,0.4) !important;
}

/* ── 11. ALERT / INFO / WARNING / SUCCESS ── */
[data-testid="stAlert"] {
    border-radius: 10px !important; font-size: 0.92rem !important;
    border: none !important; padding: 12px 16px !important;
}

/* ── 12. ROLE BADGES ── */
.role-executive { background:#ede7f6; color:#4527a0; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:700; }
.role-admin     { background:#e8f5e9; color:#1b5e20; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }
.role-manager   { background:#fff8e1; color:#e65100; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }
.role-user      { background:#e3f2fd; color:#0d47a1; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }

/* ── 13. DIVIDER ── */
hr { border: none !important; border-top: 1px solid #e2e8f0 !important; margin: 1rem 0 !important; }

/* ── 14. FORM ── */
[data-testid="stForm"] {
    background: white !important; border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    padding: 20px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
}
</style>""", unsafe_allow_html=True)
    st.session_state["_css_injected"] = True

# ── Logo VBSP ────────────────────────────────────────────────────────────────

def show_logo(width=80):
    st.markdown(
        f'''<div style="text-align:center;padding:8px 0">
        <img src="data:image/png;base64,{LOGO_B64}" width="{width}" style="border-radius:8px">
        </div>''',
        unsafe_allow_html=True
    )


def main():
    # Splash screen — tạm tắt để debug
    st.session_state["_splash_done"] = True

    # ── Session state ─────────────────────────────────────────────────────────
    for k, v in [("logged_in",False),("user_info",None),("username",""),("workspace",None)]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Login ─────────────────────────────────────────────────────────────────
    # DEV MODE: tự động đăng nhập admin (xóa block này khi deploy)
    if not st.session_state.logged_in:
        st.session_state.logged_in = True
        st.session_state.username  = "admin"
        st.session_state.user_info = {
            "username": "admin",
            "ho_ten": "Admin Dev",
            "role":   "admin_cn",
            "pgd":    None,
        }
        st.session_state["role"] = "admin_cn"
        st.session_state["username"] = "admin"
    # END DEV MODE
    if not st.session_state.logged_in:
        auth.hien_thi_login()
        st.stop()

    user_info = st.session_state.get("user_info")
    if user_info is None:
        # Chế độ test hoặc chưa đăng nhập
        st.warning("⚠️ Chưa đăng nhập hoặc session hết hạn.")
        st.stop()

    ho_ten    = user_info["ho_ten"]
    role      = user_info["role"]
    pgd_user  = user_info.get("pgd")
    username  = st.session_state.username

    # Chuẩn hóa role về dạng mới (backward-compatible)
    role = normalize_role(role)

    # Workspace mặc định theo role
    WS_DEFAULT = {
        "executive":   "executive",
        "admin":       "management",
        "manager":     "management",
        "user":        "operation",
        "admin_cn":    "management",
        "manager_cn":  "management",
        "chuyenvien_cn":"management",
        "admin_pgd":   "operation",
        "manager_pgd": "operation",
        "user_pgd":    "operation",
    }
    if st.session_state.workspace is None:
        st.session_state.workspace = WS_DEFAULT.get(role, "operation")

    # Workspace được phép dùng
    WS_ALLOWED = {
        "executive":   ["executive"],
        "admin":       ["executive","management","operation"],
        "manager":     ["management","operation"],
        "user":        ["operation"],
        "admin_cn":    ["executive","management","operation"],
        "manager_cn":  ["management","operation"],
        "chuyenvien_cn":["management","operation"],
        "admin_pgd":   ["operation"],
        "manager_pgd": ["operation"],
        "user_pgd":    ["operation"],
    }
    allowed = WS_ALLOWED.get(role, ["operation"])

    WS_LABELS = {
        "executive": "📊 Tổng Quan Chi Nhánh",
        "management":"📋 Phòng KH-NV",
        "operation": "🗺️ Hỗ Trợ Địa Bàn PGD/Biên Hòa",
    }

    # ── Sidebar ───────────────────────────────────────────────────────────────────
    with st.sidebar:
        show_logo(width=90)
        st.markdown("<div style='text-align:center;font-weight:700;font-size:1rem;margin-top:4px'>VBSP-SCM</div>", unsafe_allow_html=True)
        st.divider()
        badge_map = {
            "executive":   '<span class="role-executive">👑 Ban Giám đốc</span>',
            "admin":       '<span class="role-admin">⭐ Quản trị viên</span>',
            "manager":     '<span class="role-manager">🔑 Lãnh đạo KH-NV</span>',
            "user":        '<span class="role-user">👤 CBTD</span>',
            "admin_cn":    '<span class="role-admin">⭐ Quản trị CN</span>',
            "manager_cn":  '<span class="role-manager">🔑 Lãnh đạo CN</span>',
            "chuyenvien_cn": '<span class="role-manager">🧩 Chuyên viên CN</span>',
            "admin_pgd":   '<span class="role-admin">⭐ Quản trị PGD</span>',
            "manager_pgd": '<span class="role-manager">🔑 Lãnh đạo PGD</span>',
            "user_pgd":    '<span class="role-user">👤 CBTD</span>',
        }
        st.markdown(f"**{ho_ten}**")
        st.markdown(badge_map.get(role,""), unsafe_allow_html=True)
        if pgd_user: st.caption(f"📍 {pgd_user}")

        st.divider()
        st.markdown("**Không gian làm việc**")
        for ws_key in allowed:
            is_active = st.session_state.workspace == ws_key
            if st.button(
                f"{'▶ ' if is_active else '   '}{WS_LABELS.get(ws_key, ws_key)}",
                key=f"ws_{ws_key}", use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.workspace = ws_key
                st.rerun()

        # ── Menu điều hành (chỉ hiện khi workspace = management) ──
        if st.session_state.get("workspace") == "management":
            from workspaces.ws_management import render_sidebar_menu
            can_upload = locals().get("can_upload")
            if can_upload is None:
                can_upload = role in ("admin", "admin_cn", "manager", "manager_cn", "chuyenvien_cn")
            render_sidebar_menu(
                role=role,
                username=username,
                df=locals().get("df"),
                df_full=locals().get("df_full"),
                ds_pgd_all=locals().get("ds_pgd_all", []),
                can_upload=can_upload,
            )

        st.divider()
        # Widget trạng thái nguồn dữ liệu ưu tiên PGD
        try:
            render_status_compact(pgd_user if role == "user" else None)
        except Exception as e:
            # Fallback về hiển thị file cũ nếu có lỗi
            st.caption("📊 Trạng thái file hệ thống:")
            for fp, ten in [(FILE_PATH,TEN_FILE),(FILE_PATH_NQ11,TEN_FILE_NQ11),
                            (FILE_PATH_DB,TEN_FILE_DB),(FILE_PATH_DB_PREV,TEN_FILE_DB_PREV)]:
                if not os.path.exists(fp):
                    st.warning(f"⚠️ Thiếu `{ten}`")
                else:
                    ngay = datetime.fromtimestamp(ts_file(fp))
                    mb   = os.path.getsize(fp)/1024/1024
                    icon = "✅" if ngay.date() >= date.today() else "⚠️"
                    st.caption(f"{icon} `{ten}` {mb:.1f}MB")

        render_alert_sidebar(
            df_full=st.session_state.get("df_full"),
            role=role,
            pgd_user=pgd_user,
        )

        from auth import la_phan_he_cn, la_phan_he_pgd

        if role in ["admin","manager","executive"] or la_phan_he_cn(role) or la_phan_he_pgd(role):
            st.divider()
            if st.button("🔄 Làm mới cache", use_container_width=True):
                st.cache_data.clear()
                for k in ["_ctx", "_ctx_cache_key", "_pgd_map_cache_ts", "_pgd_xa_map_cached", "_ds_pgd_all_cached", "df_full"]:
                    st.session_state.pop(k, None)
                st.rerun()

        if role in ["admin", "admin_cn", "admin_pgd"]:
            st.divider()
            if st.button("👥 Quản lý Users", use_container_width=True):
                st.session_state.workspace = "admin_users"; st.rerun()

        st.divider()
        if st.button("🚪 Đăng xuất", use_container_width=True):
            for k in ["logged_in","user_info","username","workspace"]:
                st.session_state[k] = False if k=="logged_in" else None
            st.session_state.username = ""
            db.ghi_audit(username, "logout", "")
            st.rerun()

    # ── Load dữ liệu (ưu tiên Upload PGD cho workspace Operation) ────────────────
    ws_hien_tai = st.session_state.workspace

    _hstd_ts = ts_file(CACHE_HSTD) if os.path.exists(CACHE_HSTD) else 0.0
    _nq11_ts = ts_file(CACHE_NQ11) if os.path.exists(CACHE_NQ11) else 0.0
    _gqvl_ts = ts_file(FILE_PATH_SK_GQVL) if os.path.exists(FILE_PATH_SK_GQVL) else 0.0
    _data_version = f"{ws_hien_tai}|{role}|{pgd_user}|{_hstd_ts}|{_nq11_ts}|{_gqvl_ts}"

    if st.session_state.get("_ctx_cache_key") != _data_version:
        with st.spinner("⏳ Đang tải dữ liệu, vui lòng chờ..."):
            if not os.path.exists(CACHE_HSTD):
                if os.path.exists(FILE_PATH):
                    doc_file(FILE_PATH, ts_file(FILE_PATH))
                else:
                    st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload qua tab Upload.")
                    st.stop()

            from auth import la_phan_he_cn
            if la_phan_he_cn(role) or not pgd_user:
                df_full = _load_hstd(CACHE_HSTD, _hstd_ts)
                df = df_full
            else:
                _hstd_cols = duckdb.query(f"DESCRIBE SELECT * FROM '{CACHE_HSTD}'").df()["column_name"].tolist()
                if COT_TEN_PGD not in _hstd_cols:
                    st.error("Lỗi dữ liệu: Không tìm thấy cột 'Tên PGD' trong file gốc để phân quyền. Vui lòng liên hệ Admin.")
                    st.stop()
                df = duckdb.query(
                    f"SELECT * FROM '{CACHE_HSTD}' WHERE \"{COT_TEN_PGD}\" = '{pgd_user}'"
                ).df()
                if df.empty:
                    st.warning(f"Không có dữ liệu PGD: {pgd_user}"); st.stop()
                df_full = df

            if ws_hien_tai == "operation":
                if role == "user" and pgd_user:
                    path_hstd_pgd = duong_dan_pgd(pgd_user, "hstd")
                    if os.path.exists(path_hstd_pgd):
                        df_pgd = doc_hstd_pgd(pgd_user, ts_file(path_hstd_pgd))
                        if df_pgd is not None and not df_pgd.empty:
                            df = df_pgd
                        else:
                            st.warning(f"⚠️ File Upload HSTD của `{pgd_user}` rỗng, "
                                       f"tạm dùng dữ liệu Phòng KH-NV.")
                    else:
                        st.info(f"ℹ️ `{pgd_user}` chưa upload HSTD — "
                                f"tạm dùng dữ liệu từ Phòng KH-NV.")
                elif role in ("admin", "manager"):
                    from pathlib import Path
                    from config import PGD_DATA_DIR
                    _pgd_hstd_mtime = max(
                        (ts_file(str(d / "hstd_latest.xlsx"))
                         for d in Path(PGD_DATA_DIR).iterdir()
                         if d.is_dir() and (d / "hstd_latest.xlsx").exists()),
                        default=0.0,
                    )
                    df_op = doc_hstd_toan_cn_pgd(_pgd_hstd_mtime)
                    if df_op is not None and not df_op.empty:
                        df = df_op
            else:
                df = df_full

            df_nq11 = None
            if ws_hien_tai == "operation":
                if role == "user" and pgd_user:
                    path_nq11_pgd = duong_dan_pgd(pgd_user, "nq11")
                    if os.path.exists(path_nq11_pgd):
                        df_nq11 = doc_nq11_pgd(pgd_user, ts_file(path_nq11_pgd))
                else:
                    df_nq11 = doc_nq11_toan_cn_pgd()

            if df_nq11 is None and os.path.exists(FILE_PATH_NQ11):
                if not os.path.exists(CACHE_NQ11):
                    doc_file_nq11(FILE_PATH_NQ11, ts_file(FILE_PATH_NQ11))
                if role == "user" and pgd_user:
                    _nq11_cache = st.session_state.get("nq11_pgd_cache")
                    _nq11_ts = ts_file(CACHE_NQ11)
                    if (
                        _nq11_cache
                        and _nq11_cache.get("ts_nq11") == _nq11_ts
                        and _nq11_cache.get("pgd_user") == pgd_user
                    ):
                        df_nq11 = _nq11_cache["data"]
                    else:
                        makh_df = df[[COT_MA_KH]].dropna().astype(str).drop_duplicates()
                        if not makh_df.empty:
                            df_nq11 = duckdb.query(
                                f"SELECT n.* FROM '{CACHE_NQ11}' n "
                                f"JOIN makh_df m ON CAST(n.\"Mã khách hàng\" AS VARCHAR) = m[\"{COT_MA_KH}\"]"
                            ).df()
                        else:
                            df_nq11 = pd.DataFrame()
                        st.session_state["nq11_pgd_cache"] = {
                            "data": df_nq11,
                            "ts_nq11": _nq11_ts,
                            "pgd_user": pgd_user,
                        }
                else:
                    df_nq11 = _load_nq11(CACHE_NQ11, _nq11_ts)

            df_sk_gqvl = None
            if os.path.exists(FILE_PATH_SK_GQVL):
                df_sk_gqvl = doc_file_sk_gqvl(FILE_PATH_SK_GQVL, _gqvl_ts)

            _map_cache_ts = _hstd_ts
            if st.session_state.get("_pgd_map_cache_ts") != _map_cache_ts:
                if role == "user" and os.path.exists(CACHE_HSTD):
                    _df_ref = duckdb.query(
                        f"SELECT DISTINCT \"{COT_TEN_PGD}\", \"Tên xã\" FROM '{CACHE_HSTD}'"
                    ).df()
                else:
                    _df_ref = df_full

                _pgd_xa_map = {}
                if COT_TEN_PGD in _df_ref.columns and "Tên xã" in _df_ref.columns:
                    for pgd, xa in _df_ref[[COT_TEN_PGD, "Tên xã"]].dropna().drop_duplicates().values:
                        _pgd_xa_map[str(xa).strip()] = str(pgd).strip()
                _ds_pgd_all = sorted(_df_ref[COT_TEN_PGD].dropna().unique().tolist()) \
                              if COT_TEN_PGD in _df_ref.columns else []

                _kv_ds_pgd = lay_config("ds_pgd",    _DS_PGD_DEFAULT)
                _kv_pgd_xa = lay_config("pgd_xa_map", _PGD_XA_MAP_DEFAULT)

                if _kv_ds_pgd:
                    _ds_pgd_all = sorted(set(_ds_pgd_all) | set(_kv_ds_pgd))

                if isinstance(_kv_pgd_xa, dict):
                    for _pgd, _ds_xa in _kv_pgd_xa.items():
                        for _xa in (_ds_xa or []):
                            _xa = str(_xa).strip()
                            if _xa and _xa not in _pgd_xa_map:
                                _pgd_xa_map[_xa] = str(_pgd).strip()

                st.session_state["_pgd_map_cache_ts"]  = _map_cache_ts
                st.session_state["_pgd_xa_map_cached"] = _pgd_xa_map
                st.session_state["_ds_pgd_all_cached"] = _ds_pgd_all
            else:
                _pgd_xa_map = st.session_state["_pgd_xa_map_cached"]
                _ds_pgd_all = st.session_state["_ds_pgd_all_cached"]

            ctx = dict(
                df=df,
                df_full=df_full,
                role=role,
                pgd_user=pgd_user,
                username=username,
                df_nq11=df_nq11,
                df_sk_gqvl=df_sk_gqvl,
                pgd_xa_map=_pgd_xa_map,
                ds_pgd_all=_ds_pgd_all,
                ts_hstd=ts_file(CACHE_HSTD) if os.path.exists(CACHE_HSTD) else 0.0,
            )
            st.session_state["_ctx"] = ctx
            st.session_state["_ctx_cache_key"] = _data_version
            st.session_state["df_full"] = df_full
    else:
        ctx = st.session_state["_ctx"]
        df_full = ctx["df_full"]

    _pgd_xa_map = ctx["pgd_xa_map"]
    _ds_pgd_all = ctx["ds_pgd_all"]

    # ── Render workspace ──────────────────────────────────────────────────────────
    ws = st.session_state.workspace

    if ws == "executive":
        workspaces.ws_executive.render(**ctx)
    elif ws == "management":
        workspaces.ws_management.render(**ctx)
    elif ws == "operation":
        workspaces.ws_operation.render(**ctx)
    elif ws == "admin_users" and role == "admin":
        st.title("👥 Quản lý người dùng")
        class _FakeTab:
            def __enter__(self): return self
            def __exit__(self,*a): pass
        auth.render(_FakeTab(), df_full=df_full, role=role, username=username)
    else:
        workspaces.ws_operation.render(**ctx)


main()
