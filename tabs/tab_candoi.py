"""Tab Cân đối — Điện báo Chi nhánh.

Redesign 2026-06-04:
- Upload lên đầu (state-based): chưa có file → form nổi bật; đã có file → compact bar + expander
- Sheet selector: chọn sheet HIỆN TẠI và sheet SO SÁNH từ cùng 1 file (M↔Y, DB↔KH_GIAO_DAU_NAM…)
- Gọi doc_dienbao() với sheet_name được chọn → KPI/bảng luôn đọc đúng sheet
- Rút gọn từ 6 xuống 4 sub-tabs (xóa "KH vs TH"; gộp "Toàn bộ chỉ tiêu" vào Tổng quan)
"""

from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import os
import socket
from io import BytesIO
from datetime import datetime
from typing import TYPE_CHECKING, Any

import streamlit as st
import pandas as pd

from config import (
    DB_HT_CACHE,
    DB_PREV_CACHE,
    FILE_PATH_DB,
    FILE_PATH_DB_PREV,
)
from utils import (
    fmt_ty,
    fmt_cl,
    xuat_excel,
    ten_file_xuat,
    hien_thi_dataframe_phan_trang,
)
from components.delta_card import kpi_row
from state_manager import SCMStateManager
import db
from data import ts_file, doc_dienbao, db_lookup
from data.pgd import duong_dan_pgd, pgd_slug
from services import luu_dienbao


if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


# ── Auto-map sheet hiện tại → gợi ý sheet so sánh ──────────────────────────
_AUTO_MAP_PREV: dict[str, str] = {
    "M": "Y",
    "Y": "M",
    "DB": "KH_GIAO_DAU_NAM",
    "KH_GIAO_DAU_NAM": "DB",
    "DB1": "Y",
    "DIEU_CHINH_KHTD": "KH_GIAO_DAU_NAM",
}

# ── Danh sách chương trình cho sub-tab Theo CT ──────────────────────────────
_CHUONG_TRINH_CANDOI: list[tuple[str, str | None]] = [
    ("── KẾ HOẠCH A ──",          None),
    ("Hộ nghèo KHA",               "Dư nợ hộ nghèo KHA"),
    ("Hộ cận nghèo KHA",           "Dư nợ hộ cận nghèo KHA"),
    ("Hộ mới thoát nghèo KHA",     "Dư nợ hộ mới thoát nghèo KHA"),
    ("HSSV có HCKK",               "Dư nợ HSSV"),
    ("Giải quyết việc làm KHA",    "Dư nợ GQVL KHA"),
    ("NSVSMT nông thôn",           "Dư nợ NSVSMT NT"),
    ("SXKD vùng KK",               "Dư nợ SXKD VKK"),
    ("TN vùng KK",                 "Dư nợ TN VKK"),
    ("Nhà ở hộ nghèo",             "Dư nợ hộ nghèo về nhà ở"),
    ("Nhà ở giai đoạn 2 KHA",      "Dư nợ nhà ở gđ 2 KHA"),
    ("Cho vay XKLĐ",               "Dư nợ XKLĐ"),
    ("KFW",                        "Dư nợ KFW"),
    ("DTTS ĐBKK KHA",              "Dư nợ DTTS ĐBKK KHA"),
    ("DTTS 2085 KHA",              "Dư nợ DTTS 2085 KHA"),
    ("NOXH 100% KHA",              "Dư nợ NOXH100 KHA"),
    ("Khác KHA",                   "Dư nợ Khác KHA"),
    ("Nợ quá hạn KHA",             "Dư nợ Quá hạn KHA"),
    ("Nợ khoanh KHA",              "Dư nợ Khoanh KHA"),
    ("── KẾ HOẠCH B ──",          None),
    ("Hộ nghèo KHB",               "Dư nợ hộ nghèo KHB"),
    ("Hộ cận nghèo KHB",           "Dư nợ hộ cận nghèo KHB"),
    ("Hộ mới thoát nghèo KHB",     "Dư nợ hộ mới thoát nghèo KHB"),
    ("Giải quyết việc làm KHB",    "Dư nợ GQVL KHB"),
    ("NSVSMT NT KHB",              "Dư nợ NSVSMT NT KHB"),
    ("DTTS ĐBKK KHB",              "Dư nợ DTTS ĐBKK KHB"),
    ("DTTS 2085 KHB",              "Dư nợ DTTS 2085 KHB"),
    ("NOXH 100% KHB",              "Dư nợ NOXH100 KHB"),
    ("Khác KHB",                   "Dư nợ Khác KHB"),
    ("Nợ quá hạn KHB",             "Dư nợ Quá hạn KHB"),
    ("Nợ khoanh KHB",              "Dư nợ Khoanh KHB"),
]


def _lay_nqh_con(rows: list[dict], ten_cha: str) -> float:
    """Tìm giá trị dòng NQH con ngay sau ten_cha."""
    for r in rows:
        if r["la_nqh_con"] and r["cha"] == ten_cha:
            return r["val"]
    return 0.0


def _render_upload_section(
    store_ht: str,
    store_prev: str,
    pgd_mode: bool,
    pgd_user: str | None,
    key_sfx: str,
    username: str,
    nam_ht: str,
    nam_prev: str,
) -> None:
    """Render khu upload 2 file Điện báo (dùng cả khi chưa có file và trong expander)."""
    up_col1, up_col2 = st.columns(2)

    with up_col1:
        st.caption(f"📅 File Điện báo **hiện tại** ({nam_ht})")
        f_db_ht = st.file_uploader(
            "Chọn file Điện báo hiện tại (.xlsx)",
            type=["xlsx", "xls"],
            key=f"up_db_ht{key_sfx}",
            label_visibility="collapsed",
        )
        if f_db_ht:
            try:
                with st.spinner("⏳ Đang xử lý..."):
                    kq = luu_dienbao(
                        "ht",
                        f_db_ht.read(),
                        f_db_ht.name,
                        ten_pgd=pgd_user if pgd_mode else None,
                    )
                kq.hien_thi()
                if kq.thanh_cong:
                    st.cache_data.clear()
                    st.rerun()
            except Exception as e:
                logger.error("Upload điện báo ht: %s", e, exc_info=True)
                db.ghi_audit(
                    username, "loi_he_thong",
                    f"[{socket.gethostname()}] upload điện báo ht: {e}",
                )
                st.error(f"❌ Lỗi: {e}")
        elif os.path.exists(store_ht):
            try:
                _mt = datetime.fromtimestamp(os.path.getmtime(store_ht)).strftime("%d/%m/%Y %H:%M")
                _kb = os.path.getsize(store_ht) // 1024
            except Exception:
                _mt, _kb = "—", "—"
            st.success(f"✅ {os.path.basename(store_ht)} · {_kb} KB · {_mt}")
        else:
            st.warning("⚠️ Chưa có file — vui lòng upload")

    with up_col2:
        st.caption(f"📅 File Điện báo **kỳ trước** ({nam_prev}) *(tùy chọn)*")
        st.caption("💡 Không bắt buộc — nếu file hiện tại đã có sheet so sánh (vd: Y, KH_GIAO_DAU_NAM) thì không cần upload thêm")
        f_db_prev = st.file_uploader(
            "Chọn file Điện báo kỳ trước (.xlsx)",
            type=["xlsx", "xls"],
            key=f"up_db_prev{key_sfx}",
            label_visibility="collapsed",
        )
        if f_db_prev:
            try:
                with st.spinner("⏳ Đang xử lý..."):
                    kq = luu_dienbao(
                        "prev",
                        f_db_prev.read(),
                        f_db_prev.name,
                        ten_pgd=pgd_user if pgd_mode else None,
                    )
                kq.hien_thi()
                if kq.thanh_cong:
                    st.cache_data.clear()
                    st.rerun()
            except Exception as e:
                logger.error("Upload điện báo prev: %s", e, exc_info=True)
                db.ghi_audit(
                    username, "loi_he_thong",
                    f"[{socket.gethostname()}] upload điện báo prev: {e}",
                )
                st.error(f"❌ Lỗi: {e}")
        elif os.path.exists(store_prev):
            try:
                _mt = datetime.fromtimestamp(os.path.getmtime(store_prev)).strftime("%d/%m/%Y %H:%M")
                _kb = os.path.getsize(store_prev) // 1024
            except Exception:
                _mt, _kb = "—", "—"
            st.success(f"✅ {os.path.basename(store_prev)} · {_kb} KB · {_mt}")
        else:
            st.info("Chưa có file kỳ trước")


from tabs.base_tab import TabContext


def render(tab: DeltaGenerator | None = None, **kwargs: dict) -> None:
    import plotly.express as px
    import plotly.graph_objects as go

    ctx = TabContext(tab, **kwargs)
    df        = kwargs.get("df")
    df_full   = ctx.df_full if ctx.df_full is not None and not ctx.df_full.empty else df
    role      = ctx.role_norm
    pgd_user  = ctx.pgd_user
    username  = ctx.username
    pgd_mode  = kwargs.get("pgd_mode", False)

    if pgd_mode and not pgd_user:
        with ctx:
            st.error("Không xác định được PGD.")
        return

    key_sfx = f"_{pgd_slug(pgd_user)}" if pgd_mode else ""

    path_dien_ht   = duong_dan_pgd(pgd_user, "dienbao_ht")   if pgd_mode else None
    path_dien_prev = duong_dan_pgd(pgd_user, "dienbao_prev") if pgd_mode else None
    store_ht   = path_dien_ht   if pgd_mode else DB_HT_CACHE
    store_prev = path_dien_prev if pgd_mode else DB_PREV_CACHE

    with ctx:
        nam_ht   = str(datetime.today().year)
        nam_prev = str(datetime.today().year - 1)

        if pgd_mode:
            st.subheader(f"📌 Điện báo {pgd_user}")
        else:
            st.subheader("📌 Điện báo Chi nhánh")
        st.caption("⚖️ Cân đối Nguồn vốn & Sử dụng vốn")

        with st.expander("📖 Hướng dẫn Điện báo", expanded=False):
            from pathlib import Path
            _guide = Path(__file__).resolve().parent.parent / "docs" / "HUONG_DAN_DIEN_BAO.md"
            if _guide.exists():
                st.markdown(_guide.read_text(encoding="utf-8"))

        # ── Format helpers ─────────────────────────────────────────────────
        def vfmt_cd(x, d=1):
            try:
                x = float(x)
                s = f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return s.rstrip("0").rstrip(",") if "," in s else s
            except Exception:
                return "—"

        def fmt_pct(x):
            try:
                x = float(x)
                return (f"+{vfmt_cd(x,1)}%" if x > 0 else f"{vfmt_cd(x,1)}%") if x != 0 else "0%"
            except Exception:
                return "—"

        def _fmt_trd(x):
            try:
                if pd.isna(x):
                    return "—"
                return vfmt_cd(float(x), 0)
            except Exception:
                return "—"

        # ── Xác định đường dẫn file ────────────────────────────────────────
        if pgd_mode:
            path_ht   = path_dien_ht   if path_dien_ht   and os.path.exists(path_dien_ht)   else None
            path_prev = path_dien_prev if path_dien_prev and os.path.exists(path_dien_prev) else None
        else:
            path_ht   = DB_HT_CACHE   if os.path.exists(DB_HT_CACHE)   else (FILE_PATH_DB      if os.path.exists(FILE_PATH_DB)      else None)
            path_prev = DB_PREV_CACHE if os.path.exists(DB_PREV_CACHE) else (FILE_PATH_DB_PREV if os.path.exists(FILE_PATH_DB_PREV) else None)

        # ══════════════════════════════════════════════════════════════════
        # STATE A: Chưa có file → Upload nổi bật, return sớm
        # ══════════════════════════════════════════════════════════════════
        if not path_ht:
            with st.container(border=True):
                st.markdown("### 📤 Upload file Điện báo để bắt đầu")
                st.caption(
                    "Tải file Điện báo từ Core Banking (thường có nhiều sheet: M, Y, DB, KH_GIAO_DAU_NAM…). "
                    "Upload 1 file là đủ — hệ thống sẽ đọc 2 sheet để so sánh."
                )
                _render_upload_section(store_ht, store_prev, pgd_mode, pgd_user, key_sfx, username, nam_ht, nam_prev)
            return

        # ══════════════════════════════════════════════════════════════════
        # STATE B: Đã có file → Compact info bar + Upload expander
        # ══════════════════════════════════════════════════════════════════
        try:
            _mtime = datetime.fromtimestamp(os.path.getmtime(path_ht)).strftime("%d/%m/%Y %H:%M")
            _kb    = os.path.getsize(path_ht) // 1024
        except Exception:
            _mtime, _kb = "—", "—"

        _prev_note = (
            f" · Kỳ trước: **{os.path.basename(path_prev)}**"
            if (path_prev and path_prev != path_ht and os.path.exists(path_prev))
            else ""
        )
        st.caption(f"📂 **{os.path.basename(path_ht)}** · {_kb} KB · {_mtime}{_prev_note}")

        with st.expander("📤 Đổi file / Upload mới", expanded=False):
            _render_upload_section(store_ht, store_prev, pgd_mode, pgd_user, key_sfx, username, nam_ht, nam_prev)

        # ══════════════════════════════════════════════════════════════════
        # SHEET SELECTOR
        # ══════════════════════════════════════════════════════════════════
        from data.hstd import liet_ke_sheet_dienbao

        sheet_ht: str | None = None
        sheet_pv: str | None = None
        label_ht = f"{nam_ht} (HT)"
        label_pv = f"31/12/{nam_prev}"

        try:
            ds_sheet = liet_ke_sheet_dienbao(path_ht)
        except Exception as _e:
            logger.warning("liet_ke_sheet_dienbao: %s", _e)
            ds_sheet = []

        if ds_sheet:
            sheet_opts   = [s["sheet"] for s in ds_sheet]
            sheet_info_m = {s["sheet"]: s for s in ds_sheet}

            if len(ds_sheet) == 1:
                # Chỉ 1 sheet — không cần selectbox
                sheet_ht = sheet_opts[0]
                # Thử đọc sheet_pv từ path_prev nếu có
                if path_prev and path_prev != path_ht and os.path.exists(path_prev):
                    sheet_pv = None  # đọc sheet mặc định của file prev
            else:
                col_sh, col_shp = st.columns(2)
                with col_sh:
                    _default_ht = next(
                        (s for s in ["M", "DB1", "DB"] if s in sheet_opts),
                        sheet_opts[0],
                    )
                    sheet_ht = st.selectbox(
                        "📊 Sheet HIỆN TẠI",
                        sheet_opts,
                        index=sheet_opts.index(_default_ht),
                        key=f"cd_sheet_ht{key_sfx}",
                        format_func=lambda s: (
                            f"{s} · {sheet_info_m[s]['rows']} dòng"
                            + (f" · {sheet_info_m[s].get('ngay','')[:22]}" if sheet_info_m[s].get("ngay") else "")
                        ),
                    )
                with col_shp:
                    _auto_pv    = _AUTO_MAP_PREV.get(sheet_ht, "")
                    _default_pv = _auto_pv if _auto_pv in sheet_opts else sheet_opts[0]
                    sheet_pv = st.selectbox(
                        "📊 Sheet SO SÁNH",
                        sheet_opts,
                        index=sheet_opts.index(_default_pv),
                        key=f"cd_sheet_pv{key_sfx}",
                        format_func=lambda s: (
                            f"{s} · {sheet_info_m[s]['rows']} dòng"
                            + (f" · {sheet_info_m[s].get('ngay','')[:22]}" if sheet_info_m[s].get("ngay") else "")
                        ),
                    )

            # Label từ metadata sheet
            _si_ht = sheet_info_m.get(sheet_ht or "", {})
            _si_pv = sheet_info_m.get(sheet_pv or "", {})
            if _si_ht.get("ngay"):
                label_ht = _si_ht["ngay"][:30]
            if _si_pv.get("ngay"):
                label_pv = _si_pv["ngay"][:30]

        # ── Đọc dữ liệu với sheet được chọn ──────────────────────────────
        db_ht_rows:   list | None = None
        db_prev_rows: list | None = None

        try:
            db_ht_rows = doc_dienbao(path_ht, ts_file(path_ht), sheet_name=sheet_ht)
        except Exception as e:
            logger.error("Đọc Điện báo ht sheet=%s: %s", sheet_ht, e, exc_info=True)
            st.error(f"❌ Lỗi đọc file Điện báo hiện tại: {e}")

        # Nguồn so sánh: ưu tiên sheet_pv từ cùng file; fallback file path_prev
        if sheet_pv and sheet_pv != sheet_ht:
            try:
                db_prev_rows = doc_dienbao(path_ht, ts_file(path_ht), sheet_name=sheet_pv)
            except Exception as e:
                logger.error("Đọc Điện báo pv sheet=%s: %s", sheet_pv, e, exc_info=True)
        elif path_prev and path_prev != path_ht and os.path.exists(path_prev):
            try:
                db_prev_rows = doc_dienbao(path_prev, ts_file(path_prev), sheet_name=None)
            except Exception as e:
                logger.error("Đọc Điện báo file prev: %s", e, exc_info=True)
        # else: db_prev_rows = None → hiển thị KPI không có delta

        # ── Helpers phụ thuộc dữ liệu ─────────────────────────────────────
        _dv_div = 1000  # giá trị gốc (triệu đồng) → tỷ đồng

        def _to_ty(x: float) -> float:
            """Triệu đồng → tỷ đồng (chia 1000)."""
            return round(x / 1000, 2)

        def _pct(ht: float, pv: float) -> float | None:
            return round((ht - pv) / pv * 100, 1) if pv else None

        def build_row(ten_hien: str, val_ht: float, val_pv: float, la_con: bool = False) -> dict[str, Any]:
            cl  = val_ht - val_pv if db_prev_rows is not None else None
            tl  = (cl / val_pv * 100) if (cl is not None and val_pv and val_pv != 0) else None
            ind = "　　" if la_con else ""
            return {
                "Chỉ tiêu":  ind + ten_hien,
                label_pv:    val_pv if db_prev_rows else 0,
                label_ht:    val_ht,
                "Chênh lệch": cl if cl is not None else 0,
                "Tỷ lệ %":   tl if tl is not None else 0,
                "_ht": val_ht, "_pv": val_pv or 0, "_cl": cl or 0,
            }

        # ══════════════════════════════════════════════════════════════════
        # 4 SUB-TABS
        # ══════════════════════════════════════════════════════════════════
        cd_tab1, cd_tab2, cd_tab3, cd_tab4 = st.tabs([
            "📊 Tổng quan",
            "📌 Theo chương trình",
            "📊 Biểu đồ",
            "🔍 Ma trận PGD",
        ])

        # ──────────────────────────────────────────────────────────────────
        # TAB 1: TỔNG QUAN — KPI + bảng chi tiết (expander)
        # ──────────────────────────────────────────────────────────────────
        with cd_tab1:
            if db_ht_rows is None:
                st.info("⚠️ Không đọc được dữ liệu từ file. Kiểm tra lại file hoặc chọn sheet khác.")
            else:
                tong_dn_ht  = db_lookup(db_ht_rows, "Tổng dư nợ")
                nguon_tw_ht = db_lookup(db_ht_rows, "Nguồn vốn cân đối từ TW (KHA)")
                huy_dong_ht = db_lookup(db_ht_rows, "Tổng huy động vốn")
                utdt_ht     = db_lookup(db_ht_rows, "Nguồn vốn nhận UTĐT tại ĐP")
                nqh_ht      = db_lookup(db_ht_rows, "Dư nợ Quá hạn KHA") + db_lookup(db_ht_rows, "Dư nợ Quá hạn KHB")
                kha_ht      = db_lookup(db_ht_rows, "Dư nợ Kế hoạch A")
                khb_ht      = db_lookup(db_ht_rows, "Dư nợ Kế hoạch B")
                tl_nqh      = round(nqh_ht / tong_dn_ht * 100, 2) if tong_dn_ht else 0

                _title = f"📊 {pgd_user}" if pgd_mode else "📊 Toàn Chi nhánh"
                _sub   = f"Sheet **{sheet_ht}** so sánh với **{sheet_pv or '—'}**" if ds_sheet else ""
                st.markdown(f"### {_title}")
                if _sub:
                    st.caption(_sub)

                if db_prev_rows:
                    tong_dn_pv  = db_lookup(db_prev_rows, "Tổng dư nợ")
                    nguon_tw_pv = db_lookup(db_prev_rows, "Nguồn vốn cân đối từ TW (KHA)")
                    huy_dong_pv = db_lookup(db_prev_rows, "Tổng huy động vốn")
                    utdt_pv     = db_lookup(db_prev_rows, "Nguồn vốn nhận UTĐT tại ĐP")
                    nqh_pv      = db_lookup(db_prev_rows, "Dư nợ Quá hạn KHA") + db_lookup(db_prev_rows, "Dư nợ Quá hạn KHB")
                    kha_pv      = db_lookup(db_prev_rows, "Dư nợ Kế hoạch A")
                    khb_pv      = db_lookup(db_prev_rows, "Dư nợ Kế hoạch B")

                    kpi_row([
                        {"label": "Tổng dư nợ",   "value": _to_ty(tong_dn_ht),  "icon": "💰", "suffix": "tỷ đồng", "precision": 1,
                         "delta": _pct(tong_dn_ht, tong_dn_pv),   "delta_label": f"vs {label_pv}", "delta_color": "normal"},
                        {"label": "Vốn TW (KHA)",  "value": _to_ty(nguon_tw_ht), "icon": "🏦", "suffix": "tỷ đồng", "precision": 1,
                         "delta": _pct(nguon_tw_ht, nguon_tw_pv), "delta_label": f"vs {label_pv}", "delta_color": "normal"},
                        {"label": "Huy động vốn",  "value": _to_ty(huy_dong_ht), "icon": "💵", "suffix": "tỷ đồng", "precision": 1,
                         "delta": _pct(huy_dong_ht, huy_dong_pv), "delta_label": f"vs {label_pv}", "delta_color": "normal"},
                        {"label": "Vốn UTĐT ĐP",   "value": _to_ty(utdt_ht),     "icon": "🤝", "suffix": "tỷ đồng", "precision": 1,
                         "delta": _pct(utdt_ht, utdt_pv),         "delta_label": f"vs {label_pv}", "delta_color": "normal"},
                    ], num_columns=4)

                    kpi_row([
                        {"label": "Dư nợ KHA",     "value": _to_ty(kha_ht),  "icon": "📋", "suffix": "tỷ đồng", "precision": 1,
                         "delta": _pct(kha_ht, kha_pv), "delta_label": f"vs {label_pv}", "delta_color": "normal"},
                        {"label": "Dư nợ KHB",     "value": _to_ty(khb_ht),  "icon": "📋", "suffix": "tỷ đồng", "precision": 1,
                         "delta": _pct(khb_ht, khb_pv), "delta_label": f"vs {label_pv}", "delta_color": "normal"},
                        {"label": "NQH (KHA+KHB)", "value": _to_ty(nqh_ht),  "icon": "⚠️", "suffix": "tỷ đồng", "precision": 2,
                         "delta": tl_nqh, "delta_label": "% tổng DN", "delta_color": "inverse",
                         "help": f"Tỷ lệ NQH/Tổng dư nợ: {tl_nqh}%"},
                        {"label": "Tổng DN KHA+KHB", "value": _to_ty(kha_ht + khb_ht), "icon": "📊", "suffix": "tỷ đồng", "precision": 1,
                         "delta": _pct(kha_ht + khb_ht, kha_pv + khb_pv), "delta_label": f"vs {label_pv}", "delta_color": "normal"},
                    ], num_columns=4)

                else:
                    kpi_row([
                        {"label": "Tổng dư nợ",   "value": _to_ty(tong_dn_ht),  "icon": "💰", "suffix": "tỷ đồng", "precision": 1},
                        {"label": "Vốn TW (KHA)",  "value": _to_ty(nguon_tw_ht), "icon": "🏦", "suffix": "tỷ đồng", "precision": 1},
                        {"label": "Huy động vốn",  "value": _to_ty(huy_dong_ht), "icon": "💵", "suffix": "tỷ đồng", "precision": 1},
                        {"label": "Vốn UTĐT ĐP",   "value": _to_ty(utdt_ht),     "icon": "🤝", "suffix": "tỷ đồng", "precision": 1},
                    ], num_columns=4)

                    kpi_row([
                        {"label": "Dư nợ KHA",     "value": _to_ty(kha_ht),  "icon": "📋", "suffix": "tỷ đồng", "precision": 1},
                        {"label": "Dư nợ KHB",     "value": _to_ty(khb_ht),  "icon": "📋", "suffix": "tỷ đồng", "precision": 1},
                        {"label": "NQH (KHA+KHB)", "value": _to_ty(nqh_ht),  "icon": "⚠️", "suffix": "tỷ đồng", "precision": 2,
                         "delta": tl_nqh, "delta_label": "% tổng DN", "delta_color": "inverse"},
                        {"label": "Tổng DN KHA+KHB", "value": _to_ty(kha_ht + khb_ht), "icon": "📊", "suffix": "tỷ đồng", "precision": 1},
                    ], num_columns=4)

                # ── Bảng chi tiết tất cả chỉ tiêu (gộp từ tab cũ) ────────
                with st.expander("📋 Bảng chi tiết tất cả chỉ tiêu", expanded=False):
                    NHOM_KEYS_LOC = {
                        "Nguồn vốn":         ["Nguồn vốn","Tổng huy động","Tiền gửi","UTĐT","Vốn Trung ương","Vốn TW","HĐV"],
                        "Dư nợ KHA":         ["KHA","Kế hoạch A","GQVL KHA","NSVSMT NT","HSSV",
                                              "hộ nghèo KHA","cận nghèo KHA","thoát nghèo KHA",
                                              "SXKD VKK","XKLĐ","KFW","nhà ở","DTTS","NOXH",
                                              "TN VKK","nhà ở gđ","Quá hạn KHA","Khoanh KHA"],
                        "Dư nợ KHB":         ["KHB","Kế hoạch B","GQVL KHB","NSVSMT NT KHB",
                                              "hộ nghèo KHB","cận nghèo KHB","thoát nghèo KHB",
                                              "DTTS ĐBKK KHB","NOXH100 KHB",
                                              "Quá hạn KHB","Khoanh KHB","Khác KHB","DTTS 2085"],
                        "Vốn an toàn & quỹ": ["Vốn An toàn","Tồn quỹ","Tiền gửi tại NHNN"],
                    }
                    nhom_loc = st.radio(
                        "Lọc nhóm",
                        ["Tất cả"] + list(NHOM_KEYS_LOC.keys()),
                        horizontal=True,
                        key=f"cd_nhom{key_sfx}",
                    )
                    rows_detail: list[dict] = []
                    for r in db_ht_rows:
                        val_pv_r = 0.0
                        if db_prev_rows:
                            for rp in db_prev_rows:
                                if rp["la_nqh_con"] == r["la_nqh_con"] and rp["cha"] == r["cha"] and rp["ten"] == r["ten"]:
                                    val_pv_r = rp["val"]; break
                                if not r["la_nqh_con"] and not rp["la_nqh_con"] and rp["ten"] == r["ten"]:
                                    val_pv_r = rp["val"]; break
                        if nhom_loc != "Tất cả":
                            kws = NHOM_KEYS_LOC.get(nhom_loc, [])
                            ten_check = (r["cha"] or r["ten"]) if r["la_nqh_con"] else r["ten"]
                            if not any(kw.lower() in ten_check.lower() for kw in kws):
                                continue
                        rows_detail.append(build_row(
                            r["ten"].replace("  NQH: ", "  └ NQH: "),
                            r["val"], val_pv_r, r["la_nqh_con"],
                        ))
                    if rows_detail:
                        cols_s = ["Chỉ tiêu", label_pv, label_ht, "Chênh lệch", "Tỷ lệ %"]
                        df_s = pd.DataFrame(rows_detail)[cols_s].copy()
                        for _col in [label_pv, label_ht, "Chênh lệch"]:
                            df_s[_col] = df_s[_col].apply(_fmt_trd)
                        df_s["Tỷ lệ %"] = df_s["Tỷ lệ %"].apply(fmt_pct)
                        hien_thi_dataframe_phan_trang(
                            df_s,
                            key=f"candoi_ss_chitieu{key_sfx}",
                            height=480,
                        )
                    else:
                        st.info("Không có dữ liệu phù hợp.")

        # ──────────────────────────────────────────────────────────────────
        # TAB 2: THEO CHƯƠNG TRÌNH
        # ──────────────────────────────────────────────────────────────────
        with cd_tab2:
            if db_ht_rows is None:
                st.info("⚠️ Không có dữ liệu.")
            else:
                st.markdown(f"**So sánh dư nợ từng chương trình: {label_pv} vs {label_ht}**")
                rows_ct = []
                for ten_hien, key_ct in _CHUONG_TRINH_CANDOI:
                    if key_ct is None:
                        rows_ct.append({
                            "Chương trình": ten_hien,
                            label_pv: float("nan"), label_ht: float("nan"),
                            "Chênh lệch": float("nan"), "Tỷ lệ %": float("nan"),
                            "NQH hiện tại": float("nan"), "NQH kỳ trước": float("nan"),
                            "_is_header": True, "_ht": 0, "_pv": 0,
                        })
                        continue
                    val_ht_ct  = db_lookup(db_ht_rows,   key_ct)
                    val_pv_ct  = db_lookup(db_prev_rows, key_ct) if db_prev_rows else 0.0
                    nqh_ht_ct  = _lay_nqh_con(db_ht_rows,   key_ct)
                    nqh_pv_ct  = _lay_nqh_con(db_prev_rows, key_ct) if db_prev_rows else 0.0
                    cl_ct      = val_ht_ct - val_pv_ct
                    tl_ct      = (cl_ct / val_pv_ct * 100) if val_pv_ct else None
                    rows_ct.append({
                        "Chương trình":  ten_hien,
                        label_pv:        val_pv_ct,
                        label_ht:        val_ht_ct,
                        "Chênh lệch":    cl_ct,
                        "Tỷ lệ %":       tl_ct if tl_ct is not None else 0,
                        "NQH hiện tại":  nqh_ht_ct,
                        "NQH kỳ trước":  nqh_pv_ct,
                        "_is_header": False, "_ht": val_ht_ct, "_pv": val_pv_ct,
                    })

                df_ct = pd.DataFrame(rows_ct)
                cols_ct = ["Chương trình", label_pv, label_ht, "Chênh lệch", "Tỷ lệ %", "NQH hiện tại", "NQH kỳ trước"]
                df_ct_view = df_ct[cols_ct].copy()
                for _col in [label_pv, label_ht, "Chênh lệch", "NQH hiện tại", "NQH kỳ trước"]:
                    df_ct_view[_col] = df_ct_view[_col].apply(_fmt_trd)
                df_ct_view["Tỷ lệ %"] = df_ct_view["Tỷ lệ %"].apply(fmt_pct)
                hien_thi_dataframe_phan_trang(
                    df_ct_view,
                    key=f"candoi_ct_chuong_trinh{key_sfx}",
                    height=560,
                )

                if db_prev_rows:
                    st.divider()
                    df_ct_loc = df_ct[~df_ct["_is_header"] & (df_ct["_ht"] > 0)]
                    c_tang, c_giam = st.columns(2)
                    with c_tang:
                        st.markdown("**📈 Tăng mạnh nhất (top 8)**")
                        top_tang = (
                            df_ct_loc[df_ct_loc["_ht"] > df_ct_loc["_pv"]]
                            .assign(_cl=lambda x: x["_ht"] - x["_pv"])
                            .nlargest(8, "_cl")
                        )
                        if not top_tang.empty:
                            top_tang["_tl"] = (top_tang["_cl"] / top_tang["_pv"] * 100).round(1)
                            fig_t = px.bar(
                                top_tang, x="_cl", y="Chương trình", orientation="h",
                                text=top_tang["_tl"].apply(lambda x: f"+{x:.1f}%"),
                                color="_cl", color_continuous_scale="Blues",
                            )
                            fig_t.update_traces(textposition="outside")
                            fig_t.update_layout(
                                height=300, margin=dict(l=0, r=60, t=5, b=5),
                                xaxis_title="", yaxis=dict(title="", autorange="reversed"),
                                coloraxis_showscale=False,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            )
                            st.plotly_chart(fig_t, use_container_width=True)
                    with c_giam:
                        st.markdown("**📉 Giảm mạnh nhất (top 8)**")
                        top_giam = (
                            df_ct_loc[df_ct_loc["_ht"] < df_ct_loc["_pv"]]
                            .assign(_cl=lambda x: x["_ht"] - x["_pv"])
                            .nsmallest(8, "_cl")
                        )
                        if not top_giam.empty:
                            top_giam["_tl"] = (top_giam["_cl"] / top_giam["_pv"] * 100).round(1)
                            fig_g = px.bar(
                                top_giam, x="_cl", y="Chương trình", orientation="h",
                                text=top_giam["_tl"].apply(lambda x: f"{x:.1f}%"),
                                color="_cl", color_continuous_scale="Reds_r",
                            )
                            fig_g.update_traces(textposition="outside")
                            fig_g.update_layout(
                                height=300, margin=dict(l=0, r=60, t=5, b=5),
                                xaxis_title="", yaxis=dict(title="", autorange="reversed"),
                                coloraxis_showscale=False,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            )
                            st.plotly_chart(fig_g, use_container_width=True)

        # ──────────────────────────────────────────────────────────────────
        # TAB 3: BIỂU ĐỒ SO SÁNH
        # ──────────────────────────────────────────────────────────────────
        with cd_tab3:
            if db_ht_rows is None:
                st.info("⚠️ Không có dữ liệu.")
            elif not db_prev_rows:
                st.info(
                    "💡 Chọn sheet SO SÁNH khác với sheet HIỆN TẠI (ví dụ M vs Y) "
                    "hoặc upload file kỳ trước để xem biểu đồ so sánh."
                )
            else:
                BD_GROUPS = {
                    "Nguồn vốn": [
                        ("Vốn TW (KHA)",  "Nguồn vốn cân đối từ TW (KHA)"),
                        ("Huy động vốn",  "Tổng huy động vốn"),
                        ("Vốn UTĐT ĐP",  "Nguồn vốn nhận UTĐT tại ĐP"),
                    ],
                    "Dư nợ tổng & phân kỳ": [
                        ("Tổng dư nợ",    "Tổng dư nợ"),
                        ("Dư nợ KHA",     "Dư nợ Kế hoạch A"),
                        ("Dư nợ KHB",     "Dư nợ Kế hoạch B"),
                    ],
                    "Chương trình lớn nhất": [
                        ("GQVL KHA",      "Dư nợ GQVL KHA"),
                        ("NSVSMT NT",     "Dư nợ NSVSMT NT"),
                        ("HSSV HCKK",     "Dư nợ HSSV"),
                        ("SXKD VKK",      "Dư nợ SXKD VKK"),
                        ("GQVL KHB",      "Dư nợ GQVL KHB"),
                        ("NOXH KHA",      "Dư nợ NOXH100 KHA"),
                        ("NOXH KHB",      "Dư nợ NOXH100 KHB"),
                        ("Hộ MTN KHA",    "Dư nợ hộ mới thoát nghèo KHA"),
                        ("Cận nghèo KHA", "Dư nợ hộ cận nghèo KHA"),
                    ],
                }
                chon_bd = st.radio(
                    "Nhóm biểu đồ", list(BD_GROUPS.keys()),
                    horizontal=True, key=f"cd_bd_nhom{key_sfx}",
                )
                items    = BD_GROUPS[chon_bd]
                ten_ng   = [i[0] for i in items]
                val_ht_b = [db_lookup(db_ht_rows,   i[1]) / _dv_div for i in items]
                val_pv_b = [db_lookup(db_prev_rows, i[1]) / _dv_div for i in items]

                def _vn(v: float) -> str:
                    return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

                fig_bd = go.Figure()
                fig_bd.add_bar(
                    name=label_pv, x=ten_ng, y=val_pv_b,
                    marker_color="#90CAF9",
                    text=[_vn(v) for v in val_pv_b],
                    textposition="outside",
                )
                fig_bd.add_bar(
                    name=label_ht, x=ten_ng, y=val_ht_b,
                    marker_color="#1565C0",
                    text=[_vn(v) for v in val_ht_b],
                    textposition="outside",
                )
                fig_bd.update_layout(
                    barmode="group", height=420, yaxis_title="Tỷ đồng",
                    margin=dict(l=0, r=20, t=10, b=10),
                    legend=dict(orientation="h", y=1.08),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_bd, use_container_width=True)

        # ──────────────────────────────────────────────────────────────────
        # TAB 4: MA TRẬN PGD (dữ liệu thô từng đơn vị)
        # ──────────────────────────────────────────────────────────────────
        with cd_tab4:
            from data.hstd import doc_dienbao_matrix, liet_ke_sheet_dienbao as _lk_sheet

            _fp_matrix = path_ht
            if not _fp_matrix or not os.path.exists(_fp_matrix):
                st.info("Chưa có file Điện báo.")
            else:
                st.caption(f"📂 {os.path.basename(_fp_matrix)}")

                try:
                    _ds_sheet_raw = _lk_sheet(_fp_matrix)
                except Exception:
                    _ds_sheet_raw = []

                if _ds_sheet_raw:
                    # Metadata bảng sheet
                    with st.expander("📑 Danh sách sheet trong file", expanded=False):
                        st.dataframe(pd.DataFrame(_ds_sheet_raw), use_container_width=True, hide_index=True)

                    # Chọn sheet — mặc định theo sheet_ht đã chọn ở trên
                    _sheet_opts_raw = [s["sheet"] for s in _ds_sheet_raw]
                    _default_matrix = sheet_ht if (sheet_ht and sheet_ht in _sheet_opts_raw) else _sheet_opts_raw[0]
                    _chon_sheet_raw = st.selectbox(
                        "Chọn sheet để xem ma trận",
                        _sheet_opts_raw,
                        index=_sheet_opts_raw.index(_default_matrix),
                        key=f"cd_raw_sheet{key_sfx}",
                    )

                    if _chon_sheet_raw:
                        try:
                            data_matrix = doc_dienbao_matrix(_fp_matrix, 0, sheet_name=_chon_sheet_raw)
                            units  = data_matrix.get("units", [])
                            rows_m = data_matrix.get("rows", [])
                            matrix = data_matrix.get("matrix", {})

                            col_meta1, col_meta2 = st.columns(2)
                            col_meta1.metric("Ngày báo cáo", data_matrix.get("ngay_bao_cao", "—")[:25])
                            col_meta2.metric("Số đơn vị", len(units))

                            if matrix and units:
                                dv_chon = st.multiselect(
                                    "Chọn đơn vị hiển thị",
                                    units,
                                    default=units[:6] if len(units) >= 6 else units,
                                    key=f"cd_raw_dv{key_sfx}",
                                )
                                if dv_chon:
                                    data_rows_m = []
                                    for r_m in rows_m:
                                        if r_m["la_nqh_con"]:
                                            continue
                                        ten_ct = r_m["ten"]
                                        row_d  = {"Chỉ tiêu": ten_ct, "Cộng": r_m["val"]}
                                        if ten_ct in matrix:
                                            for dv in dv_chon:
                                                row_d[dv] = matrix[ten_ct].get(dv, 0)
                                        data_rows_m.append(row_d)

                                    df_view = pd.DataFrame(data_rows_m)
                                    cols_hien = ["Chỉ tiêu", "Cộng"] + dv_chon
                                    df_view = df_view[[c for c in cols_hien if c in df_view.columns]]

                                    df_view_fmt = df_view.copy()
                                    for _c in df_view_fmt.columns:
                                        if _c != "Chỉ tiêu":
                                            df_view_fmt[_c] = df_view_fmt[_c].apply(_fmt_trd)

                                    hien_thi_dataframe_phan_trang(
                                        df_view_fmt,
                                        key=f"cd_raw_table{key_sfx}",
                                        column_config={"Chỉ tiêu": st.column_config.TextColumn("Chỉ tiêu", width="large")},
                                        height=500,
                                    )

                                    buf_raw = BytesIO()
                                    with pd.ExcelWriter(buf_raw, engine="openpyxl") as _w:
                                        df_view.to_excel(_w, index=False, sheet_name=_chon_sheet_raw)
                                    st.download_button(
                                        "⬇️ Tải Excel ma trận",
                                        data=buf_raw.getvalue(),
                                        file_name=f"DienBao_{_chon_sheet_raw}_{datetime.today().strftime('%d%m%Y')}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key=f"cd_raw_dl{key_sfx}",
                                    )
                            else:
                                st.info("Sheet này không có dữ liệu ma trận (nhiều cột PGD).")
                        except Exception as e:
                            logger.error("Đọc ma trận sheet=%s: %s", _chon_sheet_raw, e, exc_info=True)
                            st.error(f"❌ Lỗi: {e}")
                else:
                    st.info("Không thể phân tích cấu trúc file.")

        # ══════════════════════════════════════════════════════════════════
        # XUẤT EXCEL SO SÁNH CÂN ĐỐI
        # ══════════════════════════════════════════════════════════════════
        st.divider()
        if db_ht_rows is None:
            st.caption("Xuất Excel: cần có dữ liệu Điện báo.")
        elif st.button("📥 Xuất so sánh cân đối ra Excel", key=f"btn_xuat_cd{key_sfx}"):
            buf = BytesIO()
            rows_ex1, rows_ex2 = [], []
            for r_e in db_ht_rows:
                val_pv_e = 0.0
                if db_prev_rows:
                    for rp_e in db_prev_rows:
                        if rp_e["la_nqh_con"] == r_e["la_nqh_con"] and rp_e["ten"] == r_e["ten"]:
                            val_pv_e = rp_e["val"]; break
                cl_e = r_e["val"] - val_pv_e
                rows_ex1.append({
                    "Chỉ tiêu":  r_e["ten"],
                    "Loại":      "NQH (dòng con)" if r_e["la_nqh_con"] else "Chỉ tiêu chính",
                    label_pv:    val_pv_e,
                    label_ht:    r_e["val"],
                    "Chênh lệch": cl_e,
                    "Tỷ lệ %":   round(cl_e / val_pv_e * 100, 2) if val_pv_e else 0,
                })
            for ten_hien_e, key_e in _CHUONG_TRINH_CANDOI:
                if key_e is None:
                    continue
                val_ht_e  = db_lookup(db_ht_rows,   key_e)
                val_pv_e  = db_lookup(db_prev_rows, key_e) if db_prev_rows else 0
                nqh_ht_e  = _lay_nqh_con(db_ht_rows,   key_e)
                nqh_pv_e  = _lay_nqh_con(db_prev_rows, key_e) if db_prev_rows else 0
                cl_e = val_ht_e - val_pv_e
                rows_ex2.append({
                    "Chương trình": ten_hien_e,
                    f"DN {label_pv}": val_pv_e,
                    f"DN {label_ht}": val_ht_e,
                    "Chênh lệch":    cl_e,
                    "Tỷ lệ %":       round(cl_e / val_pv_e * 100, 2) if val_pv_e else 0,
                    f"NQH {label_pv}": nqh_pv_e,
                    f"NQH {label_ht}": nqh_ht_e,
                })
            with pd.ExcelWriter(buf, engine="openpyxl") as _w:
                pd.DataFrame(rows_ex1).to_excel(_w, index=False, sheet_name="Tổng hợp chỉ tiêu")
                pd.DataFrame(rows_ex2).to_excel(_w, index=False, sheet_name="Theo chương trình")
            state = SCMStateManager()
            state.downloads.set(
                f"cd_excel{key_sfx}",
                buf.getvalue(),
                f"CanDoi_{label_pv[:10]}_vs_{label_ht[:10]}_{datetime.today().strftime('%d%m%Y')}.xlsx",
            )

        state = SCMStateManager()
        if state.downloads.has(f"cd_excel{key_sfx}"):
            if st.download_button(
                "⬇ Tải Excel",
                data=state.downloads.get_bytes(f"cd_excel{key_sfx}"),
                file_name=state.downloads.get_filename(f"cd_excel{key_sfx}") or "CanDoi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_cd_excel{key_sfx}",
            ):
                state.downloads.clear(f"cd_excel{key_sfx}")
