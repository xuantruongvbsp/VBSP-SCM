"""Tab quản lý Điểm Giao Dịch (dgd_map) — Phân hệ ws_management."""


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
    DGD_DANH_SACH,
    DON_VI_CHI_NHANH,
    DS_PGD,
    PGD_XA_MAP,
)

import db
from auth import la_phan_he_cn, normalize_role
from data.dgd_helpers import (
    dgd_dang_dung_trong_hstd,
    pool_thon_cho_xa,
    trang_thai_pgd_vs_map,
)
from data.pgd import pgd_slug
from utils import fmt_so, hien_thi_dataframe_phan_trang, xuat_excel


if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _normalize_entry(val: Any) -> dict:
    """Backward compat: list/dict → dict chỉ giữ trường 'thon'."""
    if isinstance(val, list):
        return {"thon": val}
    if isinstance(val, dict):
        return {"thon": val.get("thon", [])}
    return {"thon": []}


def _dgd_to_rows(dgd_map: dict) -> list[dict]:
    """Flatten dgd_map → list dicts để search/filter/export."""
    rows: list[dict] = []
    for pgd, xa_dict in dgd_map.items():
        if not isinstance(xa_dict, dict):
            continue
        for xa, dgd_dict in xa_dict.items():
            if not isinstance(dgd_dict, dict):
                continue
            for ten, entry in dgd_dict.items():
                e = _normalize_entry(entry)
                rows.append({
                    "PGD": pgd,
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


def _df_hstd(kwargs: dict[str, Any]) -> pd.DataFrame:
    df = kwargs.get("df_full")
    if df is None or df.empty:
        df = kwargs.get("df")
    if df is None:
        return pd.DataFrame()
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def render(tab: DeltaGenerator | None = None, **kwargs: Any) -> None:
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    df_h = _df_hstd(kwargs)
    hn = _hostname()

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("📍 Điểm Giao Dịch (dgd_map)")
        st.caption(
            "Cấu hình ĐGD — gán thôn/ấp cho từng điểm giao dịch theo PGD/Xã."
        )

        if normalize_role(role) == "executive":
            _render_tong_quan(df_h, username, hn)
            return

        t_info, t_edit, t_search, t_sum = st.tabs(
            ["📋 Thông tin điểm GD", "✏️ Gán Thôn/Ấp", "🔍 Tìm kiếm", "📋 Tổng quan"]
        )

        with t_info:
            _render_thong_tin_dgd(st)

        with t_edit:
            if not la_phan_he_cn(role) or normalize_role(role) == "executive":
                st.warning("Bạn không có quyền sửa.")
            else:
                _render_gan_thon(df_h, username, hn)

        with t_search:
            _render_tim_kiem(db.doc_dgd_map(), username)

        with t_sum:
            _render_tong_quan(df_h, username, hn)


def _render_thong_tin_dgd(ctx: Any, pgd_filter: str | None = None) -> None:
    """Tab chỉ-đọc: hiển thị 270 ĐGD từ DGD_DANH_SACH."""
    ctx.markdown("### 📋 Thông tin Điểm Giao Dịch")
    data = DGD_DANH_SACH if not pgd_filter else [
        d for d in DGD_DANH_SACH if d["pgd"] == pgd_filter
    ]
    pgd_opts = ["(Tất cả)"] + sorted({d["pgd"] for d in DGD_DANH_SACH})
    sel_pgd = ctx.selectbox("Lọc theo PGD", pgd_opts, key="info_dgd_pgd_filter")
    if sel_pgd != "(Tất cả)":
        data = [d for d in DGD_DANH_SACH if d["pgd"] == sel_pgd]
    df_show = pd.DataFrame([
        {
            "STT": d["stt"],
            "Tên ĐGD": d["ten"],
            "Xã/Phường": d["xa"],
            "Phòng GD": d["pgd"],
            "Ngày GD": d["ngay_gd"],
            "Giờ GD": d["gio_gd"],
            "Địa điểm": d["dia_diem"],
        }
        for d in data
    ])
    ctx.caption(f"**{len(df_show)}** điểm giao dịch")
    ctx.dataframe(df_show, use_container_width=True, hide_index=True)


def _render_tim_kiem(dgd_map: dict, username: str = "unknown") -> None:
    st.markdown("### 🔍 Tìm kiếm Thôn/Ấp đã gán")
    rows = _dgd_to_rows(dgd_map)
    if not rows:
        st.info("Chưa có dữ liệu thôn/ấp được gán.")
        return

    df_all = pd.DataFrame(rows)

    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        q = st.text_input(
            "🔍 Tìm nhanh", key="dgd_cn_search_q",
            placeholder="Tên ĐGD, xã, thôn/ấp...",
        )
    with c2:
        pgd_opts = ["(Tất cả)"] + sorted(df_all["PGD"].unique().tolist())
        fil_pgd = st.selectbox("Lọc PGD", pgd_opts, key="dgd_cn_search_pgd")
    with c3:
        xa_src = df_all if fil_pgd == "(Tất cả)" else df_all[df_all["PGD"] == fil_pgd]
        xa_opts = ["(Tất cả)"] + sorted(xa_src["Xã"].unique().tolist())
        fil_xa = st.selectbox("Lọc Xã/Phường", xa_opts, key="dgd_cn_search_xa")

    df_f = df_all.copy()
    if fil_pgd != "(Tất cả)":
        df_f = df_f[df_f["PGD"] == fil_pgd]
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

    cols_show = ["PGD", "Xã", "Tên ĐGD", "Số thôn/ấp", "Thôn/Ấp"]
    st.caption(f"Tìm thấy **{len(df_f)}** điểm giao dịch")
    hien_thi_dataframe_phan_trang(
        df_f[cols_show] if not df_f.empty else pd.DataFrame(columns=cols_show),
        key="dgd_cn_search_tbl",
        height=400,
    )

    if not df_f.empty:
        buf = xuat_excel({"Điểm GD": df_f})
        st.download_button(
            "📥 Xuất Excel", data=buf,
            file_name="danh_sach_dgd.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dgd_cn_search_dl_excel",
        )




def _render_tong_quan(df_h: pd.DataFrame, username: str, hn: str) -> None:
    _ = df_h, username, hn
    st.markdown("### 📋 Tổng quan")
    st.caption("So sánh dgd_map với danh mục xã trong config.PGD_XA_MAP.")
    dgd_map = db.doc_dgd_map()
    rows: list[dict[str, Any]] = []
    for ten_pgd in sorted(PGD_XA_MAP.keys()):
        block = dgd_map.get(ten_pgd, {})
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
        stt, note = trang_thai_pgd_vs_map(ten_pgd, dgd_map)
        rows.append(
            {
                "PGD": ten_pgd,
                "Số xã": fmt_so(so_xa),
                "Số ĐGD": fmt_so(so_dgd),
                "Số ấp/KP": fmt_so(so_ap),
                "Trạng thái": stt,
                "Ghi chú": note,
            }
        )
    df_o = pd.DataFrame(rows)
    if df_o.empty:
        st.info("Không có PGD trong PGD_XA_MAP.")
        return

    def _uu_tien(r: pd.Series) -> int:
        chua = (
            str(r["Trạng thái"]).startswith("⚠️")
            or r["PGD"] not in dgd_map
            or not dgd_map.get(r["PGD"])
        )
        return 0 if chua else 1

    df_o["_uu"] = df_o.apply(_uu_tien, axis=1)
    df_o = df_o.sort_values(["_uu", "PGD"]).drop(columns=["_uu"])
    hien_thi_dataframe_phan_trang(df_o, key="dgd_tongquan_tbl", height=420)


def _render_gan_thon(df_h: pd.DataFrame, username: str, hn: str) -> None:
    """Tab gán thôn/ấp cho ĐGD — tên & lịch GD là bất biến (lấy từ DGD_DANH_SACH)."""
    dgd_map = copy.deepcopy(db.doc_dgd_map())
    ten_pgd = st.selectbox("Chọn PGD", [DON_VI_CHI_NHANH] + DS_PGD, key="dgd_edit_pgd")

    ds_xa_cfg = list(PGD_XA_MAP.get(ten_pgd, []))
    if not ds_xa_cfg:
        st.warning("PGD không có trong PGD_XA_MAP.")
        return

    chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa_cfg, key="dgd_edit_xa")

    from data.dgd_helpers import khop_xa_dgd
    ds_dgd_xa = [d for d in DGD_DANH_SACH if d["pgd"] == _resolve_pgd_key(ten_pgd) and khop_xa_dgd(chon_xa, d["xa"])]
    if not ds_dgd_xa:
        st.info(f"Không có ĐGD nào trong DGD_DANH_SACH cho PGD **{ten_pgd}** / xã **{chon_xa}**.")
        return

    pool = pool_thon_cho_xa(df_h, _resolve_pgd_key(ten_pgd), chon_xa, dgd_map)
    xa_dgd = dgd_map.get(_resolve_pgd_key(ten_pgd), {}).get(chon_xa, {})
    if not isinstance(xa_dgd, dict):
        xa_dgd = {}

    st.caption(f"**{len(ds_dgd_xa)}** điểm GD tại {chon_xa} — chỉ được gán thôn/ấp, tên & lịch GD là bất biến.")

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
                key=f"dgd_th_{sid}_{ten_pgd}_{chon_xa}",
            )
            if st.button("💾 Lưu thôn/ấp", key=f"dgd_sv_{sid}_{ten_pgd}_{chon_xa}"):
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
                        cur = m.setdefault(_resolve_pgd_key(ten_pgd), {}).setdefault(chon_xa, {})
                        cur[ten_dgd] = {"thon": list(thon_sel)}
                        db.luu_dgd_map(m, username)
                        db.ghi_audit(
                            username, "gan_thon_dgd",
                            f"[{hn}] PGD={ten_pgd} xa={chon_xa} ĐGD={ten_dgd!r}: {thon_sel}",
                        )
                        st.cache_data.clear()
                        st.success("✅ Đã lưu.")
                        st.rerun()
                    except Exception as e:
                        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                        db.ghi_audit(username, "gan_thon_dgd_loi", f"[{hn}] {e}")
                        st.error(f"❌ {e}")
