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
    COT_TEN_PGD, COT_MA_KH, COT_NGAY_SL, WORKSPACE_MAP,
    COT_TONG_DU_NO, COT_DU_NO_QH,
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
from utils_theme import init_theme, get_theme_css


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
    import duckdb

    sql = f'SELECT * FROM "{cache_path}"'
    where_clauses = []

    if ten_pgd:
        where_clauses.append(f'"{COT_TEN_PGD}" = \'{ten_pgd}\'')

    if active_only:
        where_clauses.append(f'("{COT_TONG_DU_NO}" > 0 OR "{COT_DU_NO_QH}" > 0 OR "{COT_DU_NO_KHOANH}" > 0)')

    if where_clauses:
        sql += ' WHERE ' + ' AND '.join(where_clauses)

    try:
        return duckdb.query(sql).df()
    except Exception:
        return pd.DataFrame()


@st.cache_resource(show_spinner=False, ttl=3600)
def _load_nq11(cache_path: str, _ts: float) -> pd.DataFrame:
    return duckdb.query(f"SELECT * FROM '{cache_path}'").df()



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
            render_status_compact(pgd_user if la_phan_he_pgd(role) else None)
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
            import tracemalloc as _tm
            _tm.start()
            if la_phan_he_cn(role) or not pgd_user:
                df_full = _load_hstd(CACHE_HSTD, _hstd_ts, active_only=True)
                df = df_full
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
                if la_phan_he_pgd(role) and pgd_user:
                    path_nq11_pgd = duong_dan_pgd(pgd_user, "nq11")
                    if os.path.exists(path_nq11_pgd):
                        df_nq11 = doc_nq11_pgd(pgd_user, ts_file(path_nq11_pgd))
                else:
                    df_nq11 = doc_nq11_toan_cn_pgd()

            if df_nq11 is None and os.path.exists(FILE_PATH_NQ11):
                if not os.path.exists(CACHE_NQ11):
                    doc_file_nq11(FILE_PATH_NQ11, ts_file(FILE_PATH_NQ11))
                if la_phan_he_pgd(role) and pgd_user:
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
                df_sk_gqvl=df_sk_gqvl,
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
