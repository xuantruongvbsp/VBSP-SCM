"""Tab 📍 Điểm GD của tôi — CBTD cấu hình dgd_map chỉ trong phạm vi PGD đăng nhập."""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import copy
import re
import socket
from typing import TYPE_CHECKING, Any

import pandas as pd
import streamlit as st

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    DGD_DANH_SACH,
    DON_VI_CHI_NHANH,
    PGD_XA_MAP,
)

import db
from auth import normalize_role
from data.dgd_helpers import (
    khop_xa_dgd,
    pool_thon_cho_xa,
    trang_thai_pgd_vs_map,
)
from utils import fmt_so, hien_thi_dataframe_phan_trang, pick_hstd_column, xuat_excel


if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _normalize_entry(val: Any) -> dict:
    """Backward compat: list/dict → dict chỉ giữ trường 'thon'."""
    if isinstance(val, list):
        return {"thon": val}
    if isinstance(val, dict):
        return {"thon": val.get("thon", [])}
    return {"thon": []}


def _dgd_to_rows_pgd(dgd_map: dict, pgd_user: str) -> list[dict]:
    """Flatten dgd_map → list dicts, chỉ lấy nhánh của pgd_user."""
    rows: list[dict] = []
    pgd_key = _resolve_pgd_key(pgd_user)
    xa_dict = dgd_map.get(pgd_key, {})
    if not isinstance(xa_dict, dict):
        return rows
    for xa, dgd_dict in xa_dict.items():
        if not isinstance(dgd_dict, dict):
            continue
        for ten, entry in dgd_dict.items():
            e = _normalize_entry(entry)
            rows.append({
                "Xã": xa,
                "Tên ĐGD": ten,
                "Số thôn/ấp": len(e["thon"]),
                "Thôn/Ấp": ", ".join(e["thon"]),
            })
    return rows


def _resolve_pgd_key(pgd_user: str) -> str:
    """
    Chuẩn hóa tên PGD để lookup dgd_map.
    'PGD Biên Hòa' → DON_VI_CHI_NHANH vì dgd_map lưu key nội bộ.
    """
    if pgd_user in ("PGD Biên Hòa", "Hội sở CN tỉnh", "Hội sở CN Đồng Nai"):
        return DON_VI_CHI_NHANH
    return pgd_user


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        return "unknown"


def _render_thong_tin_dgd_pgd(pgd_filter: str) -> None:
    """Tab chỉ-đọc: hiển thị ĐGD của PGD này từ DGD_DANH_SACH."""
    st.markdown("### 📋 Thông tin Điểm Giao Dịch")
    data = [d for d in DGD_DANH_SACH if d["pgd"] == pgd_filter]
    df_show = pd.DataFrame([
        {
            "STT": d["stt"],
            "Tên ĐGD": d["ten"],
            "Xã/Phường": d["xa"],
            "Ngày GD": d["ngay_gd"],
            "Giờ GD": d["gio_gd"],
            "Địa điểm": d["dia_diem"],
        }
        for d in data
    ])
    st.caption(f"**{len(df_show)}** điểm giao dịch của **{pgd_filter}**")
    st.dataframe(df_show, use_container_width=True, hide_index=True)


def _render_tim_kiem_pgd(dgd_map: dict, pgd_user: str, username: str) -> None:
    st.markdown("### 🔍 Tìm kiếm Thôn/Ấp đã gán")
    rows = _dgd_to_rows_pgd(dgd_map, pgd_user)
    if not rows:
        st.info("Chưa có thôn/ấp nào được gán cho PGD của bạn.")
        return

    df_all = pd.DataFrame(rows)

    c1, c2 = st.columns([3, 2])
    with c1:
        q = st.text_input(
            "🔍 Tìm nhanh", key="dgd_pgd_search_q",
            placeholder="Tên ĐGD, xã, thôn/ấp...",
        )
    with c2:
        xa_opts = ["(Tất cả)"] + sorted(df_all["Xã"].unique().tolist())
        fil_xa = st.selectbox("Lọc Xã/Phường", xa_opts, key="dgd_pgd_search_xa")

    df_f = df_all.copy()
    if fil_xa != "(Tất cả)":
        df_f = df_f[df_f["Xã"] == fil_xa]
    if q.strip():
        kw = q.strip().lower()
        mask = (
            df_f["Tên ĐGD"].str.lower().str.contains(kw, na=False)
            | df_f["Xã"].str.lower().str.contains(kw, na=False)
            | df_f["Thôn/Ấp"].str.lower().str.contains(kw, na=False)
        )
        df_f = df_f[mask]

    cols_show = ["Xã", "Tên ĐGD", "Số thôn/ấp", "Thôn/Ấp"]
    st.caption(f"Tìm thấy **{len(df_f)}** điểm giao dịch")
    hien_thi_dataframe_phan_trang(
        df_f[cols_show] if not df_f.empty else pd.DataFrame(columns=cols_show),
        key="dgd_pgd_search_tbl",
        height=400,
    )

    if not df_f.empty:
        from data.pgd import pgd_slug
        buf = xuat_excel({"Điểm GD": df_f})
        st.download_button(
            "📥 Xuất Excel", data=buf,
            file_name=f"danh_sach_dgd_{pgd_slug(pgd_user)}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dgd_pgd_search_dl_excel",
        )




def _render_gan_thon_pgd(
    pgd_user: str,
    username: str,
    hn: str,
    df_h: pd.DataFrame,
) -> None:
    """Gán thôn/ấp cho ĐGD — PGD cố định, tên & lịch GD bất biến."""
    dgd_map = copy.deepcopy(db.doc_dgd_map())
    ten_pgd = _resolve_pgd_key(pgd_user)

    ds_xa_cfg = list(PGD_XA_MAP.get(pgd_user, []))
    if not ds_xa_cfg:
        st.warning("PGD không có trong PGD_XA_MAP.")
        return

    chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa_cfg, key="dgd_pgd_op_edit_xa")

    ds_dgd_xa = [d for d in DGD_DANH_SACH if d["pgd"] == ten_pgd and khop_xa_dgd(chon_xa, d["xa"])]
    if not ds_dgd_xa:
        st.info(f"Không có ĐGD nào trong DGD_DANH_SACH cho PGD **{pgd_user}** / xã **{chon_xa}**.")
        return

    pool = pool_thon_cho_xa(df_h, ten_pgd, chon_xa, dgd_map)
    xa_dgd = dgd_map.get(ten_pgd, {}).get(chon_xa, {})
    if not isinstance(xa_dgd, dict):
        xa_dgd = {}

    st.caption(f"**{len(ds_dgd_xa)}** điểm GD tại {chon_xa} — chỉ được gán thôn/ấp.")

    for dgd_info in ds_dgd_xa:
        ten_dgd = dgd_info["ten"]
        e = _normalize_entry(xa_dgd.get(ten_dgd, {}))
        ds_thon = e["thon"]
        sid = re.sub(r"\W+", "_", ten_dgd)[:40]
        with st.expander(f"📍 {ten_dgd}  •  Ngày {dgd_info['ngay_gd']}  •  {dgd_info['gio_gd']}", expanded=False):
            st.caption(f"📌 {dgd_info['dia_diem']}")
            thon_sel = st.multiselect(
                "Thôn/ấp phụ trách",
                options=pool,
                default=[t for t in ds_thon if t in pool],
                key=f"dgd_pgd_op_th_{sid}_{ten_pgd}_{chon_xa}",
            )
            if st.button("💾 Lưu thôn/ấp", key=f"dgd_pgd_op_sv_{sid}_{ten_pgd}_{chon_xa}"):
                dup_m: list[str] = []
                for other, raw_e in xa_dgd.items():
                    if other == ten_dgd:
                        continue
                    thon_other = _normalize_entry(raw_e)["thon"]
                    for t in thon_sel:
                        if t in thon_other:
                            dup_m.append(f"{t} → {other}")
                if dup_m:
                    st.error("Trùng thôn/ấp với ĐGD khác: " + ", ".join(dup_m))
                else:
                    try:
                        m = copy.deepcopy(db.doc_dgd_map())
                        cur = m.setdefault(ten_pgd, {}).setdefault(chon_xa, {})
                        cur[ten_dgd] = {"thon": list(thon_sel)}
                        db.luu_dgd_map(m, username)
                        db.ghi_audit(
                            username, "cbtd_gan_thon_dgd",
                            f"[{hn}] PGD={pgd_user} xa={chon_xa} ĐGD={ten_dgd!r}: {thon_sel}",
                        )
                        st.cache_data.clear()
                        st.success("✅ Đã lưu.")
                        st.rerun()
                    except Exception as e:
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        db.ghi_audit(username, "cbtd_gan_thon_dgd_loi", f"[{hn}] {e}")
                        st.error(f"❌ {e}")


def _render_tong_quan_pgd(pgd_user: str) -> None:
    st.markdown("### 📋 Tổng quan PGD của tôi")
    st.caption("So sánh dgd_map với danh mục xã trong PGD_XA_MAP (chỉ đơn vị bạn).")
    dgd_map = db.doc_dgd_map()
    block = dgd_map.get(_resolve_pgd_key(pgd_user), {})
    if not isinstance(block, dict):
        block = {}
    so_xa = len(block)
    so_dgd = 0
    so_ap = 0
    for xa_d in block.values():
        if isinstance(xa_d, dict):
            so_dgd += len(xa_d)
            for entry in xa_d.values():
                so_ap += len(_normalize_entry(entry)["thon"])
    stt, note = trang_thai_pgd_vs_map(pgd_user, dgd_map)
    df_o = pd.DataFrame(
        [
            {
                "PGD": pgd_user,
                "Số xã": fmt_so(so_xa),
                "Số ĐGD": fmt_so(so_dgd),
                "Số ấp/KP": fmt_so(so_ap),
                "Trạng thái": stt,
                "Ghi chú": note,
            }
        ]
    )
    hien_thi_dataframe_phan_trang(df_o, key="dgd_pgd_op_tongquan_tbl", height=160)


def render(tab: "DeltaGenerator", **kwargs: dict) -> None:
    df: pd.DataFrame | None = kwargs.get("df")
    role: str = kwargs.get("role", "user")
    pgd_user: str | None = kwargs.get("pgd_user")
    username: str = kwargs.get("username") or st.session_state.get("username", "unknown")

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("📍 Điểm GD của tôi")
        st.caption(
            "Cấu hình điểm giao dịch — gán thôn/ấp cho từng điểm GD trong PGD của bạn."
        )

        if normalize_role(str(role or "user")) != "user_pgd":
            st.info("Tab này dành cho CBTD (role=user).")

        if not pgd_user:
            st.error("Không xác định được PGD của người dùng.")
            return

        df_pgd: pd.DataFrame = pd.DataFrame()
        if df is not None and not df.empty:
            col_xa = pick_hstd_column(df, COT_TEN_XA, "Tên xã", "Tên Xã")
            col_pgd = pick_hstd_column(df, COT_TEN_PGD, "Tên PGD")
            if col_pgd:
                s_pgd = df[col_pgd].astype(str).str.strip()
                df_pgd = df[s_pgd == str(pgd_user).strip()].copy()
            elif col_xa:
                df_pgd = df.copy()

        hn = _hostname()
        t_info, t_edit, t_search, t_sum = st.tabs(
            ["📋 Thông tin điểm GD", "✏️ Gán Thôn/Ấp", "🔍 Tìm kiếm", "📋 Tổng quan"]
        )

        with t_info:
            _render_thong_tin_dgd_pgd(pgd_user)

        with t_edit:
            _render_gan_thon_pgd(pgd_user, username, hn, df_pgd)

        with t_search:
            _render_tim_kiem_pgd(db.doc_dgd_map(), pgd_user, username)

        with t_sum:
            _render_tong_quan_pgd(pgd_user)
