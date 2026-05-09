"""
VBSP-SCM — Hệ thống Quản trị & Tác nghiệp Tín dụng Nội bộ
Kiến trúc 3 Không gian làm việc: Executive | Management | Operation
"""
import os
import time
from datetime import datetime, date
import streamlit as st

from logo_b64_snippet import LOGO_NHCSXH_B64
import duckdb
import pandas as pd

from config import (
    FILE_PATH, FILE_PATH_NQ11, FILE_PATH_DB, FILE_PATH_DB_PREV,
    FILE_PATH_SK_GQVL,
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
from workspaces import ws_executive, ws_management, ws_operation
import db
from widgets.status_widget import render_status_compact
from alert_center import render_alert_sidebar


@st.cache_data(show_spinner=False, ttl=3600)  # tự xóa sau 1 giờ
def _load_hstd(cache_path: str, _ts: float) -> pd.DataFrame:
    return duckdb.query(f"SELECT * FROM '{cache_path}'").df()


@st.cache_data(show_spinner=False, ttl=3600)  # tự xóa sau 1 giờ
def _load_nq11(cache_path: str, _ts: float) -> pd.DataFrame:
    return duckdb.query(f"SELECT * FROM '{cache_path}'").df()


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VBSP-SCM | Tín dụng Nội bộ",
    page_icon="🏦", layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ───────────────────────────────────────────────────────────────
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

/* ── 3. SIDEBAR ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a1628 0%, #0d2137 60%, #1a3a5c 100%) !important;
    border-right: none !important;
    box-shadow: 4px 0 20px rgba(0,0,0,0.25) !important;
}
[data-testid="stSidebar"] * { color: #e8edf2 !important; }

/* Tên người dùng */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #e8edf2 !important;
    font-size: 0.93rem !important;
}

/* Caption PGD */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #94a3b8 !important;
    font-size: 0.80rem !important;
}

/* Label "Không gian làm việc" */
[data-testid="stSidebar"] strong {
    color: #94a3b8 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
}

/* Tất cả nút trong sidebar */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.06) !important;
    color: #cbd5e1 !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 10px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 9px 14px !important;
    text-align: left !important;
    white-space: normal !important;
    word-break: break-word !important;
    line-height: 1.4 !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.13) !important;
    border-color: rgba(255,255,255,0.25) !important;
    color: #ffffff !important;
    transform: translateX(2px) !important;
}

/* Nút workspace đang active (type="primary") */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, rgba(21,101,192,0.75), rgba(25,118,210,0.65)) !important;
    border: 1px solid rgba(100,160,255,0.4) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 12px rgba(21,101,192,0.35) !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, rgba(21,101,192,0.90), rgba(25,118,210,0.80)) !important;
    box-shadow: 0 4px 16px rgba(21,101,192,0.50) !important;
    transform: translateX(2px) !important;
}

/* Divider trong sidebar */
[data-testid="stSidebar"] hr {
    border-top: 1px solid rgba(255,255,255,0.10) !important;
    margin: 0.6rem 0 !important;
}

/* ── 4. TABS ── */
[data-testid="stTabs"] { background: white !important; border-radius: 12px !important;
    padding: 0 8px !important; box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important; }
[data-testid="stTabs"] button[role="tab"] {
    font-size: 0.88rem !important; font-weight: 600 !important;
    padding: 10px 16px !important; color: #5a6a7a !important;
    border-radius: 0 !important; transition: color 0.2s !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #1565c0 !important;
    border-bottom: 3px solid #1565c0 !important;
    background: transparent !important;
}
[data-testid="stTabs"] button[role="tab"]:hover { color: #1565c0 !important; }

/* ── 5. EXPANDER (card-style) ── */
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

/* ── 6. METRIC (KPI card) ── */
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

/* ── 7. DATAFRAME ── */
[data-testid="stDataFrame"] {
    border-radius: 10px !important; overflow: hidden !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
[data-testid="stDataFrame"] th {
    background: #1a3a5c !important; color: white !important;
    font-size: 0.85rem !important; font-weight: 600 !important;
    padding: 10px 12px !important; letter-spacing: 0.3px !important;
}
[data-testid="stDataFrame"] td {
    font-size: 0.9rem !important; padding: 8px 12px !important;
    border-bottom: 1px solid #f1f5f9 !important;
}

/* ── 8. INPUT / SELECTBOX / NUMBER INPUT ── */
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
    border-color: #1565c0 !important;
    box-shadow: 0 0 0 3px rgba(21,101,192,0.12) !important;
    outline: none !important;
    background: white !important;
}

/* ── 9. BUTTON ── */
.stButton > button {
    font-size: 0.9rem !important; font-weight: 600 !important;
    padding: 8px 20px !important; border-radius: 8px !important;
    border: 1.5px solid #d0d9e4 !important;
    background: white !important; color: #2c3e50 !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    border-color: #1565c0 !important; color: #1565c0 !important;
    box-shadow: 0 2px 8px rgba(21,101,192,0.15) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1565c0, #1976d2) !important;
    color: white !important; border: none !important;
    box-shadow: 0 3px 10px rgba(21,101,192,0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #0d47a1, #1565c0) !important;
    box-shadow: 0 4px 14px rgba(21,101,192,0.4) !important;
}

/* ── 10. ALERT / INFO / WARNING / SUCCESS ── */
[data-testid="stAlert"] {
    border-radius: 10px !important; font-size: 0.92rem !important;
    border: none !important; padding: 12px 16px !important;
}

/* ── 11. ROLE BADGES ── */
.role-executive { background:#ede7f6; color:#4527a0; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:700; }
.role-admin     { background:#e8f5e9; color:#1b5e20; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }
.role-manager   { background:#fff8e1; color:#e65100; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }
.role-user      { background:#e3f2fd; color:#0d47a1; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }

/* ── 12. DIVIDER ── */
hr { border: none !important; border-top: 1px solid #e2e8f0 !important; margin: 1rem 0 !important; }

/* ── 13. FORM ── */
[data-testid="stForm"] {
    background: white !important; border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    padding: 20px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
}
</style>""", unsafe_allow_html=True)

# ── Logo VBSP ────────────────────────────────────────────────────────────────

def show_logo(width=80):
    st.markdown(
        f'''<div style="text-align:center;padding:8px 0">
        <img src="data:image/png;base64,{LOGO_B64}" width="{width}" style="border-radius:8px">
        </div>''',
        unsafe_allow_html=True
    )


def main():
    # Splash screen chỉ hiện khi chưa đăng nhập
    if not st.session_state.get("_splash_done") and not st.session_state.get("logged_in"):
        placeholder = st.empty()
        placeholder.markdown(
            f"""<div style="position:fixed;top:0;left:0;width:100vw;height:100vh;
  background:linear-gradient(145deg,#1a1a6e 0%,#003087 50%,#0055b3 100%);
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  z-index:9999;font-family:'Times New Roman',Georgia,serif;">

  <img src="data:image/jpeg;base64,{LOGO_NHCSXH_B64}"
       style="width:100px;margin-bottom:28px;">

  <div style="color:white;font-size:1.8rem;font-weight:700;
    text-align:center;margin-bottom:10px;letter-spacing:0.5px;">
    NGÂN HÀNG CHÍNH SÁCH XÃ HỘI
  </div>
  <div style="color:rgba(255,255,255,0.97);font-size:1.45rem;font-weight:600;
    text-align:center;margin-bottom:6px;">
    Chi nhánh tỉnh Đồng Nai
  </div>
  <div style="color:rgba(255,255,255,0.85);font-size:1.25rem;font-weight:500;
    text-align:center;margin-bottom:44px;font-style:italic;">
    Phòng Kế hoạch - Nghiệp vụ Tín dụng
  </div>

  <div style="width:280px;height:3px;background:rgba(255,255,255,0.25);
    border-radius:4px;overflow:hidden;">
    <div style="height:100%;background:white;border-radius:4px;
      animation:load 1.8s ease-in-out forwards;"></div>
  </div>
  <div style="color:rgba(255,255,255,0.55);font-size:0.8rem;margin-top:12px;">
    Đang tải hệ thống...
  </div>

  <div style="position:absolute;bottom:24px;color:rgba(255,255,255,0.3);
    font-size:0.72rem;">
    Hệ thống Quản trị Tín dụng Nội bộ · VBSP-SCM
  </div>
</div>

<style>
@keyframes load {{
  from {{ width:0%; }}
  to   {{ width:100%; }}
}}
</style>""",
            unsafe_allow_html=True,
        )
        time.sleep(1.8)
        placeholder.empty()
        st.session_state["_splash_done"] = True
        st.rerun()

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
            "ho_ten": "Admin Dev",
            "role":   "admin",
            "pgd":    None,
        }
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
                st.cache_data.clear(); st.rerun()

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

    # ── Load dữ liệu — skip nếu đã có ctx và file chưa thay đổi ─────────────────
    _ts_hien_tai = ts_file(CACHE_HSTD) if os.path.exists(CACHE_HSTD) else 0.0
    _ctx_cu = st.session_state.get("_ctx_cache")
    _ws_hien_tai = st.session_state.workspace

    if (
        _ctx_cu is not None
        and _ctx_cu.get("ts_hstd") == _ts_hien_tai
        and _ctx_cu.get("_ws") == _ws_hien_tai
        and _ws_hien_tai != "operation"   # operation luôn load mới vì PGD tự upload
    ):
        ctx = _ctx_cu
    else:
      with st.spinner("⏳ Đang tải dữ liệu, vui lòng chờ..."):
        ws_hien_tai = _ws_hien_tai

        # Ưu tiên CACHE_HSTD (merge từ 22 PGD upload).
        if not os.path.exists(CACHE_HSTD):
            if os.path.exists(FILE_PATH):
                doc_file(FILE_PATH, ts_file(FILE_PATH))
            else:
                st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload qua tab Upload.")
                st.stop()

        # Load dữ liệu: phân hệ CN thấy toàn bộ, phân hệ PGD chỉ thấy của mình
        from auth import la_phan_he_cn
        if la_phan_he_cn(role) or not pgd_user:
            df_full = _load_hstd(CACHE_HSTD, ts_file(CACHE_HSTD))
            df = df_full
        else:
            _hstd_cols = duckdb.query(f"DESCRIBE SELECT * FROM '{CACHE_HSTD}'").df()["column_name"].tolist()
            if COT_TEN_PGD not in _hstd_cols:
                st.error("Lỗi dữ liệu: Không tìm thấy cột 'Tên PGD' trong file gốc để phân quyền. Vui lòng liên hệ Admin.")
                st.stop()
            # user role: chỉ lấy đúng dữ liệu PGD của mình — tránh load cả file vào RAM
            df = duckdb.query(
                f"SELECT * FROM '{CACHE_HSTD}' WHERE \"{COT_TEN_PGD}\" = '{pgd_user}'"
            ).df()
            if df.empty:
                st.warning(f"Không có dữ liệu PGD: {pgd_user}"); st.stop()
            # df_full cho user = chính df đã lọc (user không có quyền xem dữ liệu PGD khác)
            df_full = df

        # ── Workspace Operation: dùng pgd_data/ riêng — KHÔNG ghi đè df_full toàn CN ──
        # Theo kiến trúc 2 luồng (HUONG_DAN_NGUON_DU_LIEU.md):
        #   df_full  = CACHE_HSTD (22 PGD — do KH-NV quản lý, KHÔNG thay đổi)
        #   df       = pgd_data/{slug}/ (do PGD upload — chỉ dùng trong ws_operation)
        if ws_hien_tai == "operation":
            if role == "user" and pgd_user:
                path_hstd_pgd = duong_dan_pgd(pgd_user, "hstd")
                if os.path.exists(path_hstd_pgd):
                    df_pgd = doc_hstd_pgd(pgd_user, ts_file(path_hstd_pgd))
                    if df_pgd is not None and not df_pgd.empty:
                        df = df_pgd
                        # df_full GIỮ NGUYÊN — không ghi đè bằng pgd_data
                    else:
                        st.warning(f"⚠️ File Upload HSTD của `{pgd_user}` rỗng, "
                                   f"tạm dùng dữ liệu Phòng KH-NV.")
                else:
                    st.info(f"ℹ️ `{pgd_user}` chưa upload HSTD — "
                            f"tạm dùng dữ liệu từ Phòng KH-NV.")
            elif role in ("admin", "manager"):
                # admin/manager vào operation → xem tổng hợp pgd_data/
                df_op = doc_hstd_toan_cn_pgd()
                if df_op is not None and not df_op.empty:
                    df = df_op
                    # df_full GIỮ NGUYÊN — ws_management/executive vẫn dùng CACHE_HSTD
                # Nếu pgd_data/ chưa có → df giữ nguyên CACHE_HSTD, không warning
        else:
            df = df_full  # reset về toàn chi nhánh khi không phải workspace operation
            # KHÔNG clear cache ở đây — cache chỉ xóa khi upload file mới

        # ── NQ11 ─────────────────────────────────────────────────────────────────────
        df_nq11 = None
        if ws_hien_tai == "operation":
            if role == "user" and pgd_user:
                path_nq11_pgd = duong_dan_pgd(pgd_user, "nq11")
                if os.path.exists(path_nq11_pgd):
                    df_nq11 = doc_nq11_pgd(pgd_user, ts_file(path_nq11_pgd))
            else:
                df_nq11 = doc_nq11_toan_cn_pgd()

        if df_nq11 is None and os.path.exists(FILE_PATH_NQ11):
            # Đảm bảo parquet NQ11 tồn tại
            if not os.path.exists(CACHE_NQ11):
                doc_file_nq11(FILE_PATH_NQ11, ts_file(FILE_PATH_NQ11))

            if role == "user" and pgd_user:
                # Chỉ lấy các dòng NQ11 thuộc mã KH trong PGD của user
                makh_list = df[COT_MA_KH].dropna().astype(str).unique().tolist()
                if makh_list:
                    _makh_sql = ", ".join(f"'{m}'" for m in makh_list)
                    _sql = f"SELECT * FROM '{CACHE_NQ11}' WHERE \"{COT_MA_KH}\" IN ({_makh_sql})"
                    try:
                        df_nq11 = duckdb.query(_sql).df()
                    except Exception:
                        df_nq11 = _load_nq11(CACHE_NQ11, ts_file(CACHE_NQ11))
                else:
                    df_nq11 = pd.DataFrame()
            else:
                df_nq11 = _load_nq11(CACHE_NQ11, ts_file(CACHE_NQ11))

        # Sao kê GQVL chi tiết — dùng để xác định nhãn NQ11 cho món vay dư nợ = 0
        df_sk_gqvl = None
        if os.path.exists(FILE_PATH_SK_GQVL):
            if not os.path.exists(CACHE_SK_GQVL):
                doc_file_sk_gqvl(FILE_PATH_SK_GQVL, ts_file(FILE_PATH_SK_GQVL))
            if os.path.exists(CACHE_SK_GQVL):
                df_sk_gqvl = _load_nq11(CACHE_SK_GQVL, ts_file(CACHE_SK_GQVL))

        # ── Xây dựng mapping Xã → PGD ───────────────────────────────────────────────
        # Ưu tiên: 1) kv_store (admin config), 2) dữ liệu thực tế từ HSTD
        # KHÔNG dùng DS_PGD / PGD_XA_MAP hardcode nữa
        if df_full is not None and not df_full.empty:
            _df_ref = df_full
        else:
            _df_ref = df

        # --- Build từ HSTD (nguồn thực tế) ---
        _pgd_xa_map = {}
        if COT_TEN_PGD in _df_ref.columns and "Tên xã" in _df_ref.columns:
            for pgd, xa in _df_ref[[COT_TEN_PGD, "Tên xã"]].dropna().drop_duplicates().values:
                _pgd_xa_map[str(xa).strip()] = str(pgd).strip()

        # --- Bổ sung / ghi đè từ kv_store nếu Admin đã cấu hình ---
        _kv_ds_pgd    = lay_config("ds_pgd",    _DS_PGD_DEFAULT)
        _kv_pgd_xa    = lay_config("pgd_xa_map", _PGD_XA_MAP_DEFAULT)

        # ds_pgd_all: dùng danh sách kv_store làm chuẩn (Admin có thể thêm/bớt PGD)
        if _kv_ds_pgd:
            _ds_pgd_all = sorted(set(_ds_pgd_all) | set(_kv_ds_pgd))

        # pgd_xa_map (inverse): bổ sung các xã từ PGD_XA_MAP kv_store chưa có trong HSTD
        if isinstance(_kv_pgd_xa, dict):
            for _pgd, _ds_xa in _kv_pgd_xa.items():
                for _xa in (_ds_xa or []):
                    _xa = str(_xa).strip()
                    if _xa and _xa not in _pgd_xa_map:
                        _pgd_xa_map[_xa] = str(_pgd).strip()

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
        ctx["_ws"] = ws_hien_tai
        st.session_state["_ctx_cache"] = ctx

    # ── Render workspace ──────────────────────────────────────────────────────────
    ws = st.session_state.workspace

    if ws == "executive":
        ws_executive.render(**ctx)
    elif ws == "management":
        ws_management.render(**ctx)
    elif ws == "operation":
        ws_operation.render(**ctx)
    elif ws == "admin_users" and role == "admin":
        st.title("👥 Quản lý người dùng")
        class _FakeTab:
            def __enter__(self): return self
            def __exit__(self,*a): pass
        auth.render(_FakeTab(), df_full=df_full, role=role, username=username)
    else:
        ws_operation.render(**ctx)


main()
