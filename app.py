"""
VBSP-SCM — Hệ thống Quản trị & Tác nghiệp Tín dụng Nội bộ
Kiến trúc 3 Không gian làm việc: Executive | Management | Operation
"""
import logging
import os
import time
import warnings
from datetime import datetime, date
import streamlit as st

# Khởi tạo logging ngay khi app.py được import — đảm bảo logs/app.log tồn tại
# trước khi bất kỳ module nào khác gọi get_logger()
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
try:
    from logger import get_logger as _get_logger  # noqa: F401 — kích hoạt file handler
    _get_logger(__name__)
except Exception:
    pass

# Suppress harmless openpyxl warning for Excel files without default style
warnings.filterwarnings(
    "ignore",
    message="Workbook contains no default style",
    category=UserWarning,
    module="openpyxl",
)

import duckdb
import pandas as pd

from config import (
    COT_DU_NO_KHOANH,
    FILE_PATH, FILE_PATH_NQ11, FILE_PATH_DB, FILE_PATH_DB_PREV,
    FILE_PATH_SK_GQVL, CACHE_SK_GQVL,
    TEN_FILE, TEN_FILE_NQ11, TEN_FILE_DB, TEN_FILE_DB_PREV,
    COT_TEN_PGD, COT_MA_KH, COT_NGAY_SL, COT_SO_KU, WORKSPACE_MAP,
    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_TH,
    CACHE_HSTD, CACHE_NQ11, DON_VI_CHI_NHANH,
    DS_PGD as _DS_PGD_DEFAULT,
    PGD_XA_MAP as _PGD_XA_MAP_DEFAULT,
)
from data import ts_file, doc_file, doc_file_nq11, doc_file_sk_gqvl
from data.pgd import (
    duong_dan_pgd,
    duong_dan_hstd_hien_hanh,
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
from utils_theme import init_theme, get_theme_css
from state_manager import SCMStateManager
from security import (
    init_session_security,
    check_and_handle_timeout,
    update_last_activity,
    is_ip_allowed,
    _get_client_ip,
)


def _toi_uu_dtype(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce DataFrame memory after load:
      - float64 -> float32 for numeric columns              (~50% smaller)
      - int64   -> int32/int16 if values fit                (~50% smaller)
    Keep float64 for large monetary columns (>1e9) to avoid overflow.
    No category conversion for object columns: nunique() on 163 cols x 349K rows
    costs ~6s and causes "category type does not support sum operations" bugs.
    """
    for col in df.select_dtypes(include="float64").columns:
        try:
            col_max = df[col].abs().max(skipna=True)
            if pd.isna(col_max) or col_max < 1e9:
                df[col] = df[col].astype("float32")
        except Exception:
            pass

    for col in df.select_dtypes(include="int64").columns:
        try:
            df[col] = pd.to_numeric(df[col], downcast="integer")
        except Exception:
            pass

    return df


@st.cache_resource(show_spinner=False, ttl=3600)
def _load_hstd(
    cache_path: str,
    _ts: float,
    ten_pgd: str | None = None,
    active_only: bool = False,
) -> pd.DataFrame:
    """
    Load HSTD từ Parquet bằng DuckDB — đọc TẤT CẢ cột + filter rows.
    (PyArrow filters chỉ đọc cột được reference → bỏ sót cột khác).

    Cache key = (cache_path, _ts, ten_pgd, active_only) → mỗi tổ hợp dùng chung
    1 bản trong @st.cache_resource (không nhân bản theo session).

    - ten_pgd=None,  active_only=False → toàn bộ
    - ten_pgd=None,  active_only=True  → CN role: chỉ hồ sơ còn dư nợ
    - ten_pgd=<str>, active_only=False → PGD role: lọc theo PGD
    - ten_pgd=<str>, active_only=True  → PGD role + active filter
    """

    sql = f'SELECT * FROM "{cache_path}"'
    where_clauses = []

    if ten_pgd:
        where_clauses.append(f'"{COT_TEN_PGD}" = \'{ten_pgd}\'')

    if active_only:
        where_clauses.append(f'("{COT_TONG_DU_NO}" > 0 OR "{COT_DU_NO_QH}" > 0 OR "{COT_DU_NO_KHOANH}" > 0)')

    if where_clauses:
        sql += ' WHERE ' + ' AND '.join(where_clauses)

    try:
        if where_clauses:
            import duckdb
            arrow_tbl = duckdb.query(sql).to_arrow_table()
            df = arrow_tbl.to_pandas(self_destruct=True)
        else:
            df = pd.read_parquet(cache_path, engine='pyarrow')
        return _toi_uu_dtype(df)
    except Exception:
        return pd.DataFrame()


@st.cache_resource(show_spinner=False, ttl=3600)
def _load_nq11(cache_path: str, _ts: float) -> pd.DataFrame:
    return duckdb.query(f"SELECT * FROM '{cache_path}'").df()


def _enrich_hstd(
    df: pd.DataFrame,
    df_nq11: pd.DataFrame | None,
    df_gqvl: pd.DataFrame | None,
) -> pd.DataFrame:
    """Gắn cột __is_nq11, __is_gqvl (và cột dư nợ bổ sung) vào HSTD.

    Thực hiện một lần duy nhất tại app.py trước khi truyền ctx vào tabs.
    Tất cả tabs dùng df["__is_nq11"] thay vì tự build set riêng.
    """
    if df is None or df.empty:
        return df
    if COT_SO_KU not in df.columns:
        df = df.copy()
        df["__is_nq11"] = False
        df["__is_gqvl"] = False
        return df

    df = df.copy()
    df[COT_SO_KU] = df[COT_SO_KU].astype(str).str.strip()
    _ku = df[COT_SO_KU]

    # ── NQ11 ──
    # Ưu tiên kv_store (upload 1 lần); fallback sang df_nq11 nếu kv_store trống
    from data.hstd import doc_so_khe_uoc_nq11 as _doc_nq11_ids
    _nq11_ids = _doc_nq11_ids()
    if _nq11_ids:
        df["__is_nq11"] = _ku.isin(_nq11_ids)
    elif df_nq11 is not None and not df_nq11.empty:
        _ku_col = next(
            (c for c in ["Số khế ước", COT_SO_KU] if c in df_nq11.columns), None
        )
        if _ku_col:
            # Chỉ lấy KU có DNO NQ11 > 0 — tránh đánh badge nhầm khoản đã tất toán
            _dno_col = next(
                (c for c in df_nq11.columns if "dno nq11" in str(c).lower()), None
            )
            _df_nq = df_nq11
            if _dno_col:
                _dno = pd.to_numeric(df_nq11[_dno_col], errors="coerce").fillna(0)
                _df_nq = df_nq11[_dno > 0]
            _set_nq = set(_df_nq[_ku_col].dropna().astype(str).str.strip())
            df["__is_nq11"] = _ku.isin(_set_nq)
        else:
            df["__is_nq11"] = False
    else:
        df["__is_nq11"] = False

    # Tính __dn_nq11 / __qh_nq11 từ cột HSTD (không cần join từ file NQ11 nữa)
    if df["__is_nq11"].any():
        _tong_col = next((c for c in [COT_TONG_DU_NO, "Tổng dư nợ"] if c in df.columns), None)
        _qh_col   = next((c for c in [COT_DU_NO_QH,   "Dư nợ quá hạn"] if c in df.columns), None)
        if _tong_col:
            df["__dn_nq11"] = pd.to_numeric(df[_tong_col], errors="coerce").fillna(0).where(df["__is_nq11"], 0)
        elif COT_DU_NO_TH in df.columns and _qh_col:
            df["__dn_nq11"] = (
                pd.to_numeric(df[COT_DU_NO_TH], errors="coerce").fillna(0)
                + pd.to_numeric(df[_qh_col],    errors="coerce").fillna(0)
            ).where(df["__is_nq11"], 0)
        if _qh_col:
            df["__qh_nq11"] = pd.to_numeric(df[_qh_col], errors="coerce").fillna(0).where(df["__is_nq11"], 0)

    # ── GQVL ──
    # Dùng df[COT_SO_KU] thay vì _ku để tránh index mismatch sau NQ11 merge
    if df_gqvl is not None and not df_gqvl.empty:
        _ku_col_g = next(
            (c for c in ["Số khế ước", COT_SO_KU] if c in df_gqvl.columns), None
        )
        if _ku_col_g:
            _set_gq = set(df_gqvl[_ku_col_g].dropna().astype(str).str.strip())
            df["__is_gqvl"] = df[COT_SO_KU].isin(_set_gq)
            # Join thêm tên nhà đầu tư
            _ndt_col = next(
                (c for c in df_gqvl.columns
                 if "nhà đầu tư" in c.lower() or c.lower() in ("ten_ndt", "ndt")),
                None,
            )
            if _ndt_col:
                _slim_g = (
                    df_gqvl[[_ku_col_g, _ndt_col]]
                    .drop_duplicates(subset=[_ku_col_g])
                    .rename(columns={_ku_col_g: COT_SO_KU, _ndt_col: "__ndt_gqvl"})
                )
                _slim_g[COT_SO_KU] = _slim_g[COT_SO_KU].astype(str).str.strip()
                df = df.merge(_slim_g, on=COT_SO_KU, how="left")
        else:
            df["__is_gqvl"] = False
    else:
        df["__is_gqvl"] = False

    return df


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VBSP-SCM | Tín dụng Nội bộ",
    page_icon="🏦", layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme init + CSS ────────────────────────────────────────────────────────────
init_theme()
st.markdown(get_theme_css(), unsafe_allow_html=True)

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

    # ── Dọn audit_log cũ — 1 lần/ngày ───────────────────────────────────────
    from datetime import date as _date
    _today = _date.today().isoformat()
    if db.doc_kv("_last_audit_cleanup") != _today:
        try:
            db.xoa_audit_cu(90)
            db.ghi_kv("_last_audit_cleanup", _today, "system")
        except Exception:
            pass

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

    # ── Bảo mật & Tuân thủ NHCSXH ─────────────────────────────────────────────
    # Khởi tạo session security
    init_session_security()

    # Kiểm tra session timeout
    check_and_handle_timeout()

    # Kiểm tra IP whitelist (chỉ khi không phải localhost/dev)
    client_ip = _get_client_ip()
    if client_ip != "127.0.0.1" and not is_ip_allowed(client_ip):
        st.error(f"⛔ IP {client_ip} không được phép truy cập hệ thống.")
        db.ghi_audit(st.session_state.get("username", "unknown"), "ip_blocked", f"IP: {client_ip}")
        st.info("Vui lòng liên hệ quản trị viên để được hỗ trợ.")
        st.stop()

    # Cập nhật last activity
    update_last_activity()
    # ─────────────────────────────────────────────────────────────────────────

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
            label = WS_LABELS.get(ws_key, ws_key)
            if is_active:
                st.markdown(
                    f"<div style='"
                    f"background:linear-gradient(135deg,#1565C0,#1976D2);"
                    f"border-left:4px solid #0D47A1;"
                    f"color:#FFFFFF;font-size:15px;font-weight:700;"
                    f"padding:12px 18px;border-radius:0 10px 10px 0;margin-bottom:6px;"
                    f"box-shadow:0 3px 10px rgba(21,101,192,0.4);"
                    f"letter-spacing:0.3px'>"
                    f"▶ {label}</div>",
                    unsafe_allow_html=True,
                )
            else:
                if st.button(label, key=f"ws_{ws_key}", use_container_width=True):
                    st.session_state.workspace = ws_key
                    st.rerun()

        # ── Menu điều hành (chỉ hiện khi workspace = management) ──
        if st.session_state.get("workspace") == "management":
            from workspaces.ws_management import render_sidebar_menu
            from auth import la_phan_he_cn, la_executive
            can_upload = la_phan_he_cn(role) and not la_executive(role)
            _ctx_sb = st.session_state.get("_ctx") or {}
            render_sidebar_menu(
                role=role,
                username=username,
                df=_ctx_sb.get("df"),
                df_full=_ctx_sb.get("df_full"),
                ds_pgd_all=_ctx_sb.get("ds_pgd_all", []),
                can_upload=can_upload,
            )

        # ── Menu Hỗ trợ địa bàn (chỉ hiện khi workspace = operation) ──
        if st.session_state.get("workspace") == "operation":
            from workspaces.ws_operation import render_sidebar_menu
            from auth import get_tab_permissions, is_pgd_role
            _tab_perm = get_tab_permissions(role)
            _ctx_sb = st.session_state.get("_ctx") or {}
            _df_op = _ctx_sb.get("df")
            _pgd_user_op = pgd_user
            _df_pgd_op = None
            if _df_op is not None and not _df_op.empty and is_pgd_role(role) and _pgd_user_op and COT_TEN_PGD in _df_op.columns:
                _df_pgd_op = _df_op[_df_op[COT_TEN_PGD] == _pgd_user_op].copy()
            elif _df_op is not None and not _df_op.empty:
                _df_pgd_op = _df_op
            render_sidebar_menu(
                role=role,
                username=username,
                df_pgd=_df_pgd_op,
                pgd_user=_pgd_user_op,
                tab_perm=_tab_perm,
            )

        st.divider()
        # Widget trạng thái nguồn dữ liệu ưu tiên PGD
        try:
            from widgets.status_widget import render_status_compact
            from auth import la_phan_he_pgd
            render_status_compact(pgd_user if la_phan_he_pgd(role) else None)
        except Exception as e:  # conv: skip
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

        _mp = db.doc_kv("_merge_progress")
        if _mp:
            _loai_upper = str(_mp.get("loai", "")).upper()
            if _mp.get("running"):
                _done = _mp.get("done", 0)
                _total = _mp.get("total", 22)
                st.divider()
                st.warning(
                    f"🔄 Đang merge {_loai_upper}: **{_done}/{_total} PGD**\n\n"
                    "_Chuyển tab bình thường — merge chạy nền._"
                )
            else:
                _end_str = _mp.get("end")
                if _end_str:
                    try:
                        _age = (datetime.now() - datetime.fromisoformat(_end_str)).total_seconds()
                        if _age < 300:
                            st.divider()
                            st.success(f"✅ Merge {_loai_upper} xong · {_mp.get('done', 0)} PGD")
                    except Exception:
                        pass

        from alert_center import render_alert_sidebar
        render_alert_sidebar(
            df_full=st.session_state.get("df_full"),
            role=role,
            pgd_user=pgd_user,
        )

        from auth import la_phan_he_cn, la_phan_he_pgd

        if la_phan_he_cn(role) or la_phan_he_pgd(role):
            st.divider()
            if st.button("🔄 Làm mới cache", use_container_width=True):
                st.cache_data.clear()
                for k in ["_ctx", "_ctx_cache_key", "_pgd_map_cache_ts", "_pgd_xa_map_cached", "_ds_pgd_all_cached", "df_full"]:
                    st.session_state.pop(k, None)
                st.rerun()

        if normalize_role(role) in ("admin_cn", "admin_pgd"):
            st.divider()
            if st.button("👥 Quản lý Users", use_container_width=True):
                st.session_state.workspace = "admin_users"; st.rerun()

        if normalize_role(role) in ("admin_cn", "admin"):
            st.divider()
            st.caption("💾 Sao lưu & phục hồi → tab **🔍 Trạng thái** › Hệ thống")

        if normalize_role(role) in ("admin_cn", "admin"):
            st.divider()
            with st.expander("🧪 Debug state", expanded=False):
                try:
                    dump = SCMStateManager.debug_dump()
                    downloads = dump.get("_scm_downloads", {}) if isinstance(dump, dict) else {}
                    st.caption(f"downloads keys: {len(downloads) if isinstance(downloads, dict) else 0}")
                    if st.button("🧹 Clear downloads", use_container_width=True, key="dbg_clear_downloads"):
                        SCMStateManager().downloads.clear_all()
                        st.rerun()
                    st.json(dump)
                except Exception as e:  # conv: skip
                    st.error(f"Debug dump lỗi: {e}")

        st.divider()
        if st.button("🚪 Đăng xuất", use_container_width=True):
            for k in ["logged_in","user_info","username","workspace"]:
                st.session_state[k] = False if k=="logged_in" else None
            st.session_state.username = ""
            for k in list(st.session_state.keys()):
                if str(k).startswith("_scm_"):
                    st.session_state.pop(k, None)
            db.ghi_audit(username, "logout", "")
            st.rerun()

    # ── Load dữ liệu (ưu tiên Upload PGD cho workspace Operation) ────────────────
    ws_hien_tai = st.session_state.workspace

    _hstd_ts = ts_file(CACHE_HSTD) if os.path.exists(CACHE_HSTD) else 0.0
    _nq11_ts = ts_file(CACHE_NQ11) if os.path.exists(CACHE_NQ11) else 0.0
    _gqvl_ts = ts_file(FILE_PATH_SK_GQVL) if os.path.exists(FILE_PATH_SK_GQVL) else 0.0

    # PGD upload mtime — đưa vào _data_version để tự động reload khi PGD upload file mới
    # mà chưa có merge hệ thống (trường hợp này _hstd_ts không đổi → không detect được).
    # PGD role: check 1 file → rẻ, không cần cache.
    # CN role / operation: quét 22 thư mục → cache 30s trong session_state.
    from auth import la_phan_he_cn as _la_cn_ver, la_phan_he_pgd as _la_pgd_ver
    _pgd_op_ts = 0.0
    if ws_hien_tai == "operation":
        if _la_pgd_ver(role) and pgd_user:
            _p = duong_dan_hstd_hien_hanh(pgd_user)
            _pgd_op_ts = ts_file(_p) if os.path.exists(_p) else 0.0
        elif _la_cn_ver(role):
            _pgd_scan_ss = st.session_state.get("_pgd_op_mtime_ss")
            _now_t = time.time()
            if _pgd_scan_ss is None or (_now_t - _pgd_scan_ss["ts"]) > 30:
                from pathlib import Path
                from config import PGD_DATA_DIR
                _pgd_op_ts = max(
                    (
                        max(
                            ts_file(str(d / "hstd_latest.xlsx")) if (d / "hstd_latest.xlsx").exists() else 0.0,
                            ts_file(str(d / "hstd_khnv.xlsx")) if (d / "hstd_khnv.xlsx").exists() else 0.0,
                        )
                        for d in Path(PGD_DATA_DIR).iterdir()
                        if d.is_dir()
                    ),
                    default=0.0,
                )
                st.session_state["_pgd_op_mtime_ss"] = {"mtime": _pgd_op_ts, "ts": _now_t}
            else:
                _pgd_op_ts = _pgd_scan_ss["mtime"]

    _data_version = f"{ws_hien_tai}|{role}|{pgd_user}|{_hstd_ts}|{_nq11_ts}|{_gqvl_ts}|{_pgd_op_ts}"

    if st.session_state.get("_ctx_cache_key") != _data_version:
        with st.spinner("⏳ Đang tải dữ liệu, vui lòng chờ..."):
            if not os.path.exists(CACHE_HSTD):
                if os.path.exists(FILE_PATH):
                    doc_file(FILE_PATH, ts_file(FILE_PATH))
                else:
                    st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng upload qua tab Upload.")
                    st.stop()

            from auth import la_phan_he_cn
            import tracemalloc as _tm
            _tm.start()
            if la_phan_he_cn(role) or not pgd_user:
                df_full = _load_hstd(CACHE_HSTD, _hstd_ts, active_only=True)
                df = df_full
                # Kiểm tra schema — parquet từ file template chỉ có ~6 cột
                # (xảy ra khi cache bị xóa và app fallback đọc raw Excel)
                _MIN_COLS = 15
                if not df_full.empty and len(df_full.columns) < _MIN_COLS:
                    st.error(
                        f"⚠️ **Dữ liệu HSTD không đầy đủ** — cache chỉ có {len(df_full.columns)} cột "
                        f"(cần ≥ {_MIN_COLS} cột). "
                        "Cache đang dùng file template, không phải dữ liệu thực tế.\n\n"
                        "**Cách sửa:** Vào tab **📤 Upload HSTD** → upload lại file HSTD → Merge."
                    )
                    st.stop()
            else:
                # PGD role: filter pushdown tại read_parquet, cached per-PGD
                df = _load_hstd(CACHE_HSTD, _hstd_ts, ten_pgd=pgd_user)
                if df.empty:
                    _hstd_cols = duckdb.query(
                        f"DESCRIBE SELECT * FROM read_parquet('{CACHE_HSTD}')"
                    ).df()["column_name"].tolist()
                    if COT_TEN_PGD not in _hstd_cols:
                        st.error("Lỗi dữ liệu: Không tìm thấy cột 'Tên PGD' trong file gốc để phân quyền. Vui lòng liên hệ Admin.")
                        st.stop()
                    st.warning(f"Không có dữ liệu PGD: {pgd_user}"); st.stop()
                df_full = df

            _cur_mb, _peak_mb = (v / 1024 / 1024 for v in _tm.get_traced_memory())
            _tm.stop()
            _app_logger = __import__("logger").get_logger("app.ram")
            _app_logger.info(
                "load_hstd: role=%s pgd=%s rows=%d current=%.1fMB peak=%.1fMB",
                role, pgd_user or "CN", len(df), _cur_mb, _peak_mb,
            )

            if ws_hien_tai == "operation":
                if la_phan_he_pgd(role) and pgd_user:
                    path_hstd_pgd = duong_dan_hstd_hien_hanh(pgd_user)
                    if os.path.exists(path_hstd_pgd):
                        df_pgd = doc_hstd_pgd(pgd_user, ts_file(path_hstd_pgd))
                        if df_pgd is not None and not df_pgd.empty:
                            df = df_pgd
                        else:
                            st.warning(f"⚠️ File HSTD của `{pgd_user}` rỗng.")
                    else:
                        st.warning(f"⚠️ `{pgd_user}` chưa có dữ liệu HSTD.")
                elif la_phan_he_cn(role):
                    # _pgd_op_ts đã được tính và cache bên ngoài block — dùng lại
                    df_op = doc_hstd_toan_cn_pgd(_pgd_op_ts)
                    if df_op is not None and not df_op.empty:
                        df = df_op
            else:
                df = df_full

            # df_nq11: kv_store approach (upload 1 lần).
            # Backward compat: nếu kv_store chưa có IDs → đọc parquet cache cũ
            # để _enrich_hstd() fallback sang df_nq11.
            from data.hstd import doc_so_khe_uoc_nq11 as _check_nq11_ids
            _has_nq11_kv = bool(_check_nq11_ids())
            _df_nq11_fallback = None
            if not _has_nq11_kv and os.path.exists(CACHE_NQ11) and ws_hien_tai != "executive":
                _df_nq11_fallback = _load_nq11(CACHE_NQ11, _nq11_ts)

            df_gqvl = None
            if os.path.exists(FILE_PATH_SK_GQVL) and ws_hien_tai != "executive":
                df_gqvl = doc_file_sk_gqvl(FILE_PATH_SK_GQVL, _gqvl_ts)

            # Enrich HSTD với NQ11/GQVL flags — 1 lần, tất cả tabs dùng chung
            # QUAN TRỌNG: kiểm tra df is df_full TRƯỚC khi gọi _enrich_hstd vì hàm này
            # luôn trả về object mới (df.copy()) — nếu check sau thì df_full is not df
            # luôn True và enrich chạy 2 lần không cần thiết.
            _df_was_df_full = df is df_full
            df = _enrich_hstd(df, _df_nq11_fallback, df_gqvl)
            if _df_was_df_full:
                df_full = df  # cùng nguồn dữ liệu — dùng chung 1 bản enrich
            else:
                df_full = _enrich_hstd(df_full, _df_nq11_fallback, df_gqvl)

            # Xây df_nq11 cho tabs từ HSTD đã enrich (không cần file riêng)
            if "__is_nq11" in df.columns and df["__is_nq11"].any():
                df_nq11 = df[df["__is_nq11"]].copy()
                # Alias tên cột HSTD → tên cột NQ11 file (để tab_nq11.py không cần sửa)
                for _src, _dst in (
                    (COT_TONG_DU_NO, "DNO NQ11"),
                    (COT_DU_NO_TH,   "Nợ trong hạn"),
                    (COT_DU_NO_QH,   "Nợ quá hạn"),
                    (COT_MA_KH,      "Mã khách hàng"),
                    ("Tên KH",        "Tên khách hàng"),
                ):
                    if _src in df_nq11.columns and _dst not in df_nq11.columns:
                        df_nq11[_dst] = df_nq11[_src]
            else:
                df_nq11 = pd.DataFrame()

            _map_cache_ts = _hstd_ts
            if st.session_state.get("_pgd_map_cache_ts") != _map_cache_ts:
                if la_phan_he_pgd(role) and os.path.exists(CACHE_HSTD):
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
                df_gqvl=df_gqvl,
                pgd_xa_map=_pgd_xa_map,
                ds_pgd_all=_ds_pgd_all,
                ts_hstd=ts_file(CACHE_HSTD) if os.path.exists(CACHE_HSTD) else 0.0,
                hstd_path=CACHE_HSTD if os.path.exists(CACHE_HSTD) else None,
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
    elif ws == "admin_users" and normalize_role(role) == "admin_cn":
        st.title("👥 Quản lý người dùng")
        class _FakeTab:
            def __enter__(self): return self
            def __exit__(self,*a): pass
        auth.render(_FakeTab(), df_full=df_full, role=role, username=username)
    else:
        workspaces.ws_operation.render(**ctx)


main()
