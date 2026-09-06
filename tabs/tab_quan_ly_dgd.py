"""Tab quản lý Điểm Giao Dịch (dgd_map) — Phân hệ ws_management."""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import copy
import re
import socket
import unicodedata
from datetime import datetime
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
    khop_xa_dgd,
    pool_thon_cho_xa,
    trang_thai_pgd_vs_map,
)
from data.khtd import doc_cbtd, luu_cbtd
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


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        text = str(value).strip().lower()
    except Exception:
        return ""
    return "" if text in {"nan", "none", "<na>"} else text


def _fold_import_text(value: Any) -> str:
    """Chuẩn hóa mạnh để nhận diện header/tên từ Excel import."""
    text = _norm_text(value)
    if not text:
        return ""
    text = text.replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _split_import_thon(value: Any) -> list[str]:
    """Cho phép 1 ô chứa nhiều thôn, ngăn bằng xuống dòng/phẩy/chấm phẩy."""
    text = "" if value is None else str(value).strip()
    if not text or _norm_text(text) in {"nan", "none", "<na>"}:
        return []
    parts = re.split(r"[\n;,]+", text)
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        item = re.sub(r"\s+", " ", part).strip()
        key = _fold_import_text(item)
        if item and key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _pick_import_column(df: pd.DataFrame, kind: str) -> str | None:
    """Tìm cột import theo tên phổ biến, tránh bắt nhầm 'Tên xã' thành 'Tên ĐGD'."""
    if df is None or df.empty:
        return None
    for col in df.columns:
        h = _fold_import_text(col)
        if kind == "pgd" and (
            "pgd" in h
            or "phong gd" in h
            or ("phong giao dich" in h and "diem" not in h)
            or h in {"don vi", "ten don vi"}
        ):
            return col
        if kind == "xa" and ("xa" in h or "phuong" in h or "thi tran" in h):
            return col
        if kind == "dgd" and (
            "dgd" in h
            or "diem gd" in h
            or "diem giao dich" in h
            or h in {"ten diem", "ten dgd"}
        ):
            return col
        if kind == "thon" and (
            "thon" in h
            or "khu pho" in h
            or re.search(r"(^|[\s/_-])ap($|[\s/_-])", h)
            or re.search(r"(^|[\s/_-])kp($|[\s/_-])", h)
            or h in {"thon ap", "thon/ap", "ap/kp"}
        ):
            return col
    return None


def _canon_pgd_import(value: Any) -> str:
    raw = "" if value is None else str(value).strip()
    if not raw:
        return ""
    key = _fold_import_text(raw)
    for pgd in [DON_VI_CHI_NHANH] + DS_PGD:
        if _fold_import_text(pgd) == key:
            return _resolve_pgd_key(pgd)
    return _resolve_pgd_key(raw)


def _canon_xa_import(pgd: str, value: Any) -> str:
    raw = "" if value is None else str(value).strip()
    if not raw:
        return ""
    ds_xa = PGD_XA_MAP.get(_resolve_pgd_key(pgd), [])
    raw_key = _fold_import_text(raw)
    for xa in ds_xa:
        if _fold_import_text(xa) == raw_key or khop_xa_dgd(xa, raw):
            return xa
    return raw


def _infer_dgd_scope(pgd: str, xa: str, ten_dgd: str) -> tuple[str, str, str]:
    """Chuẩn hóa tên ĐGD và suy ra PGD/Xã khi file chỉ có tên ĐGD."""
    dgd_key = _fold_import_text(ten_dgd)
    if not dgd_key:
        return pgd, xa, ""

    matches = [d for d in DGD_DANH_SACH if _fold_import_text(d.get("ten", "")) == dgd_key]
    pgd_key = _resolve_pgd_key(pgd) if pgd else ""
    if pgd_key:
        matches = [d for d in matches if d.get("pgd") == pgd_key]
    if xa:
        matches = [d for d in matches if khop_xa_dgd(xa, d.get("xa", "")) or khop_xa_dgd(_canon_xa_import(pgd_key, xa), d.get("xa", ""))]

    if len(matches) != 1:
        return pgd_key or pgd, xa, ten_dgd

    found = matches[0]
    found_pgd = found.get("pgd", "") or pgd_key or pgd
    found_xa = xa
    if not found_xa:
        for xa_cfg in PGD_XA_MAP.get(found_pgd, []):
            if khop_xa_dgd(xa_cfg, found.get("xa", "")):
                found_xa = xa_cfg
                break
        found_xa = found_xa or str(found.get("xa", "")).strip()
    return found_pgd, found_xa, str(found.get("ten", ten_dgd)).strip()


def _gop_dgd_thon_tu_excel_df(
    df_imp: pd.DataFrame,
    fallback_pgd: str = "",
    fallback_xa: str = "",
    only_scope: bool = False,
) -> tuple[dict[str, dict[str, dict[str, list[str]]]], dict[str, Any]]:
    """
    Gom bảng Excel thành dgd_map patch: PGD -> Xã -> Tên ĐGD -> [Thôn/ấp].

    Hỗ trợ file có ô PGD/Xã/ĐGD bị merge bằng cách fill-down ba cột định danh.
    Nếu thiếu PGD/Xã, có thể dùng fallback hoặc suy ra từ DGD_DANH_SACH khi tên ĐGD khớp duy nhất.
    """
    grouped: dict[str, dict[str, dict[str, list[str]]]] = {}
    stats: dict[str, Any] = {
        "rows": 0,
        "used_rows": 0,
        "skip_blank": 0,
        "skip_scope": 0,
        "columns": {},
    }
    if df_imp is None or df_imp.empty:
        return grouped, stats

    df = df_imp.copy().fillna("")
    cols = {
        "pgd": _pick_import_column(df, "pgd"),
        "xa": _pick_import_column(df, "xa"),
        "dgd": _pick_import_column(df, "dgd"),
        "thon": _pick_import_column(df, "thon"),
    }
    stats["columns"] = cols
    if not cols["dgd"] or not cols["thon"]:
        stats["error"] = "Không tìm thấy cột Tên ĐGD hoặc Thôn/ấp."
        return grouped, stats

    for col in [cols["pgd"], cols["xa"], cols["dgd"]]:
        if col:
            df[col] = df[col].replace("", pd.NA).ffill().fillna("")

    fallback_pgd_key = _canon_pgd_import(fallback_pgd)
    fallback_xa_key = _canon_xa_import(fallback_pgd_key, fallback_xa)
    seen_by_dgd: dict[tuple[str, str, str], set[str]] = {}

    stats["rows"] = int(len(df))
    for _, row in df.iterrows():
        raw_pgd = row.get(cols["pgd"], "") if cols["pgd"] else fallback_pgd_key
        raw_xa = row.get(cols["xa"], "") if cols["xa"] else fallback_xa_key
        raw_dgd = row.get(cols["dgd"], "")
        thon_items = _split_import_thon(row.get(cols["thon"], ""))

        pgd = _canon_pgd_import(raw_pgd) or fallback_pgd_key
        xa = _canon_xa_import(pgd, raw_xa) or fallback_xa_key
        pgd, xa, dgd = _infer_dgd_scope(pgd, xa, raw_dgd)
        if pgd:
            xa = _canon_xa_import(pgd, xa)

        if only_scope and (
            (fallback_pgd_key and _resolve_pgd_key(pgd) != fallback_pgd_key)
            or (fallback_xa_key and _fold_import_text(xa) != _fold_import_text(fallback_xa_key))
        ):
            stats["skip_scope"] += 1
            continue

        if not pgd or not xa or not dgd or not thon_items:
            stats["skip_blank"] += 1
            continue

        key = (_resolve_pgd_key(pgd), xa, dgd)
        seen = seen_by_dgd.setdefault(key, set())
        target = grouped.setdefault(key[0], {}).setdefault(key[1], {}).setdefault(key[2], [])
        for thon in thon_items:
            th_key = _fold_import_text(thon)
            if th_key and th_key not in seen:
                seen.add(th_key)
                target.append(thon)
                stats["used_rows"] += 1

    return grouped, stats


def _rows_preview_import_grouped(grouped: dict[str, dict[str, dict[str, list[str]]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pgd, xa_block in grouped.items():
        for xa, dgd_block in xa_block.items():
            for dgd_name, th_list in dgd_block.items():
                rows.append({
                    "PGD": pgd,
                    "Xã": xa,
                    "Tên ĐGD": dgd_name,
                    "Số thôn/ấp": len(th_list),
                    "Thôn/Ấp": ", ".join(th_list),
                })
    return rows


def _apply_import_grouped_to_map(
    current_map: dict,
    grouped: dict[str, dict[str, dict[str, list[str]]]],
) -> dict:
    """Áp dụng patch import vào dgd_map, gỡ trùng thôn trong cùng xã trước khi set ĐGD mới."""
    out = copy.deepcopy(current_map or {})
    for pgd, xa_block in grouped.items():
        pgd_block = out.setdefault(_resolve_pgd_key(pgd), {})
        for xa, dgd_block in xa_block.items():
            cur_xa = pgd_block.setdefault(xa, {})
            prospective = _build_prospective_xa_dgd(cur_xa, dgd_block)
            for dgd_name, th_list in prospective.items():
                cur_xa[dgd_name] = {"thon": list(th_list)}
    return out


def _validate_trung_thon_toan_xa(the_dict: dict[str, list[str]]) -> list[str]:
    """Trả về list msg các thôn bị trùng giữa 2 ĐGD bất kỳ trong một xã."""
    ap_owner: dict[str, str] = {}
    errors: list[str] = []
    for dgd_name, th_list in the_dict.items():
        for thon_name in th_list:
            key_th = _norm_text(thon_name)
            if not key_th:
                continue
            if key_th in ap_owner and ap_owner[key_th] != dgd_name:
                errors.append(f"⚠️ Thôn **{thon_name}** bị trùng: **{ap_owner[key_th]}** ↔ **{dgd_name}**")
            else:
                ap_owner[key_th] = dgd_name
    return errors


def _build_prospective_xa_dgd(
    xa_dgd: dict,
    pending_block: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Tạo trạng thái dự kiến; thôn trong ĐGD pending sẽ được gỡ khỏi ĐGD cũ trước."""
    prospective: dict[str, list[str]] = {}
    for d_name, raw_entry in (xa_dgd or {}).items():
        prospective[d_name] = list(_normalize_entry(raw_entry)["thon"])

    for d_name, th_list in (pending_block or {}).items():
        th_clean: list[str] = []
        seen: set[str] = set()
        for th in th_list:
            key_th = _norm_text(th)
            if not key_th or key_th in seen:
                continue
            seen.add(key_th)
            th_clean.append(str(th).strip())

        moved_keys = {_norm_text(th) for th in th_clean}
        for other_name, other_list in list(prospective.items()):
            if other_name == d_name:
                continue
            prospective[other_name] = [
                th for th in other_list
                if _norm_text(th) not in moved_keys
            ]
        prospective[d_name] = th_clean

    return prospective


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception as e:
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

        t_info, t_edit, t_cbtd, t_search, t_sum = st.tabs(
            ["📋 Thông tin điểm GD", "✏️ Gán Thôn/Ấp", "👤 Gán CBTD", "🔍 Tìm kiếm", "📋 Tổng quan"]
        )

        with t_info:
            _render_thong_tin_dgd(st)

        with t_edit:
            if not la_phan_he_cn(role) or normalize_role(role) == "executive":
                st.warning("Bạn không có quyền sửa.")
            else:
                _render_gan_thon(df_h, username, hn)

        with t_cbtd:
            if not la_phan_he_cn(role) or normalize_role(role) == "executive":
                st.warning("Bạn không có quyền sửa.")
            else:
                _render_gan_cbtd(df_h, username, hn)

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
    """Tab gán thôn/ấp cho ĐGD — Batch save + Cross-check HSTD + Validate trùng + Import Excel."""
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

    # --- Cross-check HSTD % (NEW Gói 3) --- Build set thôn có dư nợ > 0
    ap_co_dn: set[str] = set()
    if df_h is not None and not df_h.empty:
        try:
            from config import COT_TEN_XA, COT_TEN_THON, COT_TONG_DU_NO
            if COT_TEN_XA in df_h.columns and COT_TEN_THON in df_h.columns and COT_TONG_DU_NO in df_h.columns:
                pgd_k = _resolve_pgd_key(ten_pgd)
                # Lọc theo PGD + Xã (không phân biệt chữ hoa/thường)
                norm_xa_target = _norm_text(chon_xa)
                mask_pgd = (df_h.get("PGD", pd.Series(dtype="object")).apply(_norm_text) == _norm_text(pgd_k)) \
                    if "PGD" in df_h.columns else pd.Series([True]*len(df_h))
                mask_xa = df_h[COT_TEN_XA].fillna("").astype(str).apply(_norm_text) == norm_xa_target
                dn = pd.to_numeric(df_h[COT_TONG_DU_NO], errors="coerce").fillna(0)
                mask_dn = dn > 0
                sub = df_h.loc[mask_pgd & mask_xa & mask_dn]
                if not sub.empty:
                    for _, r in sub.iterrows():
                        th = _norm_text(r.get(COT_TEN_THON, ""))
                        if th:
                            ap_co_dn.add(th)
        except Exception as e_cross:
            logger.error("_render_gan_thon cross-check HSTD — %s", e_cross, exc_info=True)

    st.caption(f"**{len(ds_dgd_xa)}** điểm GD tại {chon_xa} — chỉ được gán thôn/ấp, tên & lịch GD là bất biến.")

    # --- (NEW) KPI Block Cross-check ---
    if ap_co_dn:
        tong_thon_co_dn = len(ap_co_dn)
        thon_da_gan_xa: set[str] = set()
        for _, entry in xa_dgd.items():
            for t in _normalize_entry(entry)["thon"]:
                thon_da_gan_xa.add(str(t).strip().lower())
        thon_match = ap_co_dn & thon_da_gan_xa
        pct_match = round(len(thon_match) / tong_thon_co_dn * 100, 1) if tong_thon_co_dn else 0.0
        kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
        kpi_c1.metric(f"📊 Thôn có dư nợ (HSTD)", f"{tong_thon_co_dn}")
        kpi_c2.metric(f"✅ Đã gán ĐGD", f"{len(thon_match)}", delta=f"{pct_match:.0f}%",
                     delta_color="normal" if pct_match >= 80 else "inverse")
        kpi_c3.metric(f"🔴 Chưa gán", f"{tong_thon_co_dn - len(thon_match)}")
        if pct_match < 80:
            st.error(f"🚨 **{pct_match:.1f}% thôn có dư nợ chưa được gán ĐGD** "
                     f"(ngưỡng an toàn ≥80%). Cần bổ sung cấu hình.")
        elif pct_match < 95:
            st.warning(f"⚠️ {pct_match:.1f}% thôn đã gán (chưa đầy đủ ≥95%).")
        else:
            st.success(f"✅ {pct_match:.1f}% thôn có dư nợ đã được gán (mức tốt).")

    st.divider()

    # --- Import Excel toàn bộ: gom Thôn/Ấp theo ĐGD trước khi gắn CBTD ---
    with st.expander("📤 Import Excel địa bàn → tự gom thôn theo Điểm GD", expanded=False):
        st.caption(
            "File nên có các cột: **PGD | Xã | Tên ĐGD | Thôn/ấp**. "
            "Nếu PGD/Xã/ĐGD là ô merge, hệ thống sẽ tự fill xuống; một ô thôn có thể chứa nhiều tên ngăn bằng dấu phẩy hoặc xuống dòng."
        )
        only_current_scope = st.checkbox(
            "Chỉ lấy các dòng thuộc PGD/Xã đang chọn",
            value=False,
            key=f"dgd_import_all_scope_{ten_pgd}_{chon_xa}",
        )
        file_all = st.file_uploader(
            "Chọn file Excel địa bàn (.xlsx)",
            type=["xlsx"],
            key=f"dgd_import_all_{ten_pgd}_{chon_xa}",
            accept_multiple_files=False,
        )
        if file_all is not None:
            try:
                df_imp_all = pd.read_excel(file_all, dtype=str).fillna("")
                grouped_all, stats_all = _gop_dgd_thon_tu_excel_df(
                    df_imp_all,
                    fallback_pgd=ten_pgd,
                    fallback_xa=chon_xa,
                    only_scope=only_current_scope,
                )
                st.caption(
                    f"Đọc {stats_all.get('rows', 0)} dòng · "
                    f"cột nhận diện: {stats_all.get('columns', {})}"
                )
                if stats_all.get("error"):
                    st.error(f"❌ {stats_all['error']}")
                rows_all = _rows_preview_import_grouped(grouped_all)
                if rows_all:
                    so_pgd = len(grouped_all)
                    so_xa = sum(len(xa_block) for xa_block in grouped_all.values())
                    so_dgd = len(rows_all)
                    so_thon = sum(int(r["Số thôn/ấp"]) for r in rows_all)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("PGD", fmt_so(so_pgd))
                    c2.metric("Xã", fmt_so(so_xa))
                    c3.metric("ĐGD", fmt_so(so_dgd))
                    c4.metric("Thôn/ấp", fmt_so(so_thon))
                    if stats_all.get("skip_blank") or stats_all.get("skip_scope"):
                        st.warning(
                            f"Bỏ qua {stats_all.get('skip_blank', 0)} dòng thiếu PGD/Xã/ĐGD/Thôn "
                            f"và {stats_all.get('skip_scope', 0)} dòng ngoài phạm vi chọn."
                        )
                    hien_thi_dataframe_phan_trang(
                        pd.DataFrame(rows_all),
                        key=f"dgd_import_all_preview_{ten_pgd}_{chon_xa}",
                        height=min(420, 70 + len(rows_all) * 38),
                    )
                    confirm_all = st.checkbox(
                        "Xác nhận lưu cấu hình đã gom vào dgd_map",
                        key=f"dgd_import_all_confirm_{ten_pgd}_{chon_xa}",
                    )
                    if st.button(
                        "💾 Lưu địa bàn đã gom",
                        type="primary",
                        disabled=not confirm_all,
                        key=f"dgd_import_all_apply_{ten_pgd}_{chon_xa}",
                    ):
                        m_all = _apply_import_grouped_to_map(db.doc_dgd_map(), grouped_all)
                        db.luu_dgd_map(m_all, username)
                        db.ghi_audit(
                            username,
                            "gan_thon_dgd_import_excel_toan_bo",
                            f"[{hn}] import file={getattr(file_all, 'name', '')} "
                            f"pgd={so_pgd} xa={so_xa} dgd={so_dgd} thon={so_thon} "
                            f"only_scope={only_current_scope}",
                        )
                        st.cache_data.clear()
                        st.success(f"✅ Đã lưu {so_thon} thôn/ấp vào {so_dgd} ĐGD.")
                        st.rerun()
                elif not stats_all.get("error"):
                    st.info("Không có dòng hợp lệ để gom. Kiểm tra lại cột PGD/Xã/Tên ĐGD/Thôn.")
            except Exception as e_all:
                logger.error("_render_gan_thon import Excel toàn bộ — %s", e_all, exc_info=True)
                st.error(f"❌ Lỗi import: {e_all}")

    st.divider()

    # --- (NEW) Import Excel Cấu hình ĐGD Block ---
    with st.expander("📤 Import Excel cấu hình ĐGD (batch cập nhật thôn)", expanded=False):
        st.caption("Template Excel các cột: **PGD | Xã | Tên ĐGD | Thôn/ấp** (mỗi dòng 1 thôn, cùng ĐGD lặp nhiều dòng).")
        file_up = st.file_uploader("Chọn file Excel (.xlsx)", type=["xlsx"],
                                   key=f"dgd_import_{ten_pgd}_{chon_xa}",
                                   accept_multiple_files=False)
        if file_up is not None:
            try:
                df_imp = pd.read_excel(file_up, dtype=str).fillna("")
                st.caption(f"Đọc được {len(df_imp)} dòng. Column: {list(df_imp.columns)}")
                # Xác định cột theo tên phổ biến
                col_pgd_cand = [c for c in df_imp.columns if "pgd" in str(c).lower()]
                col_xa_cand = [c for c in df_imp.columns if "xã" in str(c).lower() or "xa" == str(c).lower()]
                col_dgd_cand = [c for c in df_imp.columns if "đgd" in str(c).lower() or "dgd" in str(c).lower() or "tên" in str(c).lower()]
                col_th_cand = [c for c in df_imp.columns if "thôn" in str(c).lower() or "thon" in str(c).lower() or "ấp" in str(c).lower() or "ap" in str(c).lower()]
                c_pgd = col_pgd_cand[0] if col_pgd_cand else df_imp.columns[0]
                c_xa  = col_xa_cand[0]  if col_xa_cand  else df_imp.columns[1]
                c_dgd = col_dgd_cand[0] if col_dgd_cand else df_imp.columns[2]
                c_th  = col_th_cand[0]  if col_th_cand  else df_imp.columns[3]
                # Group theo ĐGD
                imp_dgd_thon: dict[str, list[str]] = {}
                skip_pgd = skip_xa = skip_blank = 0
                for _, r in df_imp.iterrows():
                    rv_pgd = str(r.get(c_pgd, "")).strip()
                    rv_xa = str(r.get(c_xa, "")).strip()
                    rv_dgd = str(r.get(c_dgd, "")).strip()
                    rv_th = str(r.get(c_th, "")).strip()
                    # Lọc theo PGD+Xã hiện tại (chỉ import những dòng khớp, tránh overwrite nhầm)
                    if rv_pgd and _norm_text(rv_pgd) != _norm_text(ten_pgd):
                        skip_pgd += 1
                        continue
                    if rv_xa and _norm_text(rv_xa) != _norm_text(chon_xa):
                        skip_xa += 1
                        continue
                    if not rv_dgd or not rv_th:
                        skip_blank += 1
                        continue
                    imp_dgd_thon.setdefault(rv_dgd, [])
                    if rv_th not in imp_dgd_thon[rv_dgd]:
                        imp_dgd_thon[rv_dgd].append(rv_th)
                st.caption(
                    f"Đã lọc {sum(len(v) for v in imp_dgd_thon.values())} dòng khớp "
                    f"PGD={ten_pgd}, Xã={chon_xa}; bỏ qua {skip_pgd + skip_xa + skip_blank} dòng "
                    f"(PGD khác: {skip_pgd}, xã khác: {skip_xa}, thiếu ĐGD/thôn: {skip_blank})."
                )
                if imp_dgd_thon:
                    st.markdown(f"📋 **{len(imp_dgd_thon)} ĐGD sẽ được cập nhật:**")
                    prev_rows = []
                    for dgd_name, th_list in imp_dgd_thon.items():
                        prev_rows.append({"Tên ĐGD": dgd_name, "Số thôn": len(th_list),
                                          "Danh sách thôn": ", ".join(th_list)})
                    hien_thi_dataframe_phan_trang(pd.DataFrame(prev_rows),
                                                  key=f"dgd_import_preview_{ten_pgd}_{chon_xa}")
                    xn_imp = st.checkbox("Xác nhận áp dụng (sẽ overwrite cấu hình thôn của các ĐGD này)",
                                         key=f"dgd_import_xn_{ten_pgd}_{chon_xa}")
                    if st.button("💾 Áp dụng cấu hình từ Excel", type="primary",
                                 disabled=not xn_imp,
                                 key=f"dgd_import_apply_{ten_pgd}_{chon_xa}"):
                        m_imp = copy.deepcopy(db.doc_dgd_map())
                        cur_blk = m_imp.setdefault(_resolve_pgd_key(ten_pgd), {}).setdefault(chon_xa, {})
                        prospective_import = _build_prospective_xa_dgd(cur_blk, imp_dgd_thon)
                        for dgd_n, th_list in prospective_import.items():
                            cur_blk[dgd_n] = {"thon": list(th_list)}
                        db.luu_dgd_map(m_imp, username)
                        db.ghi_audit(username, "gan_thon_dgd_import_excel",
                                     f"[{hn}] PGD={ten_pgd} xa={chon_xa} "
                                     f"import {len(imp_dgd_thon)} DGD: {list(imp_dgd_thon.keys())}")
                        st.cache_data.clear()
                        st.success(f"✅ Đã cập nhật {len(imp_dgd_thon)} ĐGD từ Excel.")
                        st.rerun()
                else:
                    st.info("Không có dòng nào khớp với PGD/Xã đang chọn (kiểm tra lại cột PGD, Xã).")
            except Exception as e_imp:
                logger.error("_render_gan_thon import Excel — %s", e_imp, exc_info=True)
                st.error(f"❌ Lỗi import: {e_imp}")

    st.divider()

    # --- Pending state dict (NEW Gói 3: Batch save nhiều ĐGD 1 lần) ---
    pending_state_key = f"dgd_batch_pending_{ten_pgd}_{chon_xa}"
    if pending_state_key not in st.session_state:
        st.session_state[pending_state_key] = {}

    # --- Build các ĐGD + multiselect, lưu vào pending dict, chỉ lưu khi bấm Lưu TẤT CẢ ---
    has_changes_batch = False
    for dgd_info in ds_dgd_xa:
        ten_dgd = dgd_info["ten"]
        e = _normalize_entry(xa_dgd.get(ten_dgd, {}))
        ds_thon_hien_tai = list(e["thon"])
        sid = re.sub(r"\W+", "_", ten_dgd)[:40]
        with st.expander(f"📍 {ten_dgd}  •  Ngày {dgd_info['ngay_gd']}  •  {dgd_info['gio_gd']}", expanded=False):
            st.caption(f"📌 {dgd_info['dia_diem']}")
            # Đặt default từ session state nếu có chỉnh sửa trước đó
            key_multisel = f"dgd_th_{sid}_{ten_pgd}_{chon_xa}"
            if key_multisel not in st.session_state:
                st.session_state[key_multisel] = [t for t in ds_thon_hien_tai if t in pool]
            thon_sel = st.multiselect(
                "Thôn/ấp phụ trách",
                options=pool,
                default=st.session_state[key_multisel],
                key=key_multisel,
            )
            # Cập nhật pending dict
            if sorted(thon_sel) != sorted(ds_thon_hien_tai):
                st.session_state[pending_state_key][ten_dgd] = list(thon_sel)
                has_changes_batch = True
            else:
                if ten_dgd in st.session_state[pending_state_key]:
                    del st.session_state[pending_state_key][ten_dgd]
            # --- Cross-check per ĐGD: thôn có dư nợ nhưng chưa gán? ---
            if ap_co_dn and thon_sel:
                norm_th_sel = {str(t).strip().lower() for t in thon_sel}
                cover = ap_co_dn & norm_th_sel
                miss = ap_co_dn - norm_th_sel
                if cover:
                    st.success(f"📈 Đã bao phủ {len(cover)}/{tong_thon_co_dn} thôn có dư nợ ({len(cover)/tong_thon_co_dn*100:.0f}%).")

    st.divider()

    # --- Pending summary + Validate trùng + Batch save ---
    pending_block: dict = st.session_state.get(pending_state_key, {}) or {}
    if pending_block:
        st.markdown(f"**📝 {len(pending_block)} ĐGD có thay đổi (chưa Lưu):**")
        prev_rows = []
        for dgd_name, th_list in pending_block.items():
            old_list = _normalize_entry(xa_dgd.get(dgd_name, {}))["thon"]
            add = [t for t in th_list if t not in old_list]
            rem = [t for t in old_list if t not in th_list]
            prev_rows.append({
                "Tên ĐGD": dgd_name,
                "Số thôn mới": len(th_list),
                "+ Thêm": ", ".join(add) if add else "—",
                "− Bớt": ", ".join(rem) if rem else "—",
            })
        hien_thi_dataframe_phan_trang(pd.DataFrame(prev_rows),
                                      key=f"dgd_pending_{ten_pgd}_{chon_xa}",
                                      height=min(260, 50 + len(prev_rows)*42))
    else:
        st.caption("ℹ️ Chưa có thay đổi nào so với dữ liệu đã lưu.")

    # Build prospective dict = xa_dgd hiện tại + override từ pending
    prospective_xa_dgd = _build_prospective_xa_dgd(xa_dgd, pending_block)
    dup_list = _validate_trung_thon_toan_xa(prospective_xa_dgd)
    if dup_list:
        with st.expander(f"⚠️ **{len(dup_list)} trùng thôn cross-ĐGD** (phải sửa trước khi Lưu)",
                         expanded=True):
            for d_msg in dup_list:
                st.error(d_msg)

    btn_col_1, btn_col_2, btn_col_3 = st.columns([1, 1, 3])
    with btn_col_1:
        if st.button("🔄 Reset pending", key=f"dgd_reset_pending_{ten_pgd}_{chon_xa}",
                     disabled=not pending_block):
            # Clear session state multiselect về giá trị gốc
            for dgd_info in ds_dgd_xa:
                ten_dgd = dgd_info["ten"]
                sid = re.sub(r"\W+", "_", ten_dgd)[:40]
                k = f"dgd_th_{sid}_{ten_pgd}_{chon_xa}"
                e2 = _normalize_entry(xa_dgd.get(ten_dgd, {}))
                st.session_state[k] = [t for t in e2["thon"] if t in pool]
            st.session_state[pending_state_key] = {}
            st.rerun()
    with btn_col_2:
        disabled_save = (not pending_block) or bool(dup_list)
        if st.button("💾 LƯU TẤT CẢ thay đổi", type="primary", disabled=disabled_save,
                     key=f"dgd_luu_batch_{ten_pgd}_{chon_xa}"):
            try:
                m = copy.deepcopy(db.doc_dgd_map())
                cur = m.setdefault(_resolve_pgd_key(ten_pgd), {}).setdefault(chon_xa, {})
                for dgd_n, th_l in prospective_xa_dgd.items():
                    cur[dgd_n] = {"thon": list(th_l)}
                db.luu_dgd_map(m, username)
                db.ghi_audit(
                    username, "gan_thon_dgd_batch",
                    f"[{hn}] PGD={ten_pgd} xa={chon_xa} "
                    f"batch {len(pending_block)} DGD: {list(pending_block.keys())}",
                )
                st.cache_data.clear()
                st.session_state[pending_state_key] = {}
                st.success(f"✅ Đã lưu batch {len(pending_block)} ĐGD.")
                st.rerun()
            except Exception as e:
                logger.error("gan_thon_dgd_batch error: %s", e, exc_info=True)
                db.ghi_audit(username, "gan_thon_dgd_loi", f"[{hn}] batch err: {e}")
                st.error(f"❌ {e}")


def _render_gan_cbtd(df_h: pd.DataFrame, username: str, hn: str) -> None:
    """Tab gán CBTD cho ĐGD — gán từ ĐGD, lưu ngược vào cbtd_data."""
    st.markdown("### 👤 Gán CBTD cho Điểm Giao Dịch")
    st.caption("Chọn PGD → Xã → ĐGD, sau đó chọn CBTD phụ trách. Mỗi ĐGD chỉ được 1 CBTD.")

    cbtd_data: dict = doc_cbtd()
    dgd_map: dict = db.doc_dgd_map() or {}

    # Build reverse mapping: (pgd, dgd) -> ma_cb
    dgd_to_cbtd: dict[tuple[str, str], str] = {}
    for ma_cb, info in cbtd_data.items():
        pgd_cb = info.get("pgd", "")
        for dgd in info.get("ds_dgd", []):
            dgd_to_cbtd[(pgd_cb, dgd)] = ma_cb

    # Select PGD
    ten_pgd = st.selectbox("Chọn PGD", [DON_VI_CHI_NHANH] + DS_PGD, key="cbtd_gan_pgd")

    # Get DGD list for this PGD
    from config import lay_dgd_cho_pgd
    ds_dgd_pgd = lay_dgd_cho_pgd(ten_pgd)
    if not ds_dgd_pgd:
        st.info(f"Không có ĐGD nào trong DGD_DANH_SACH cho PGD **{ten_pgd}**.")
        return

    # Group by xa
    xa_to_dgd: dict[str, list[dict]] = {}
    for d in ds_dgd_pgd:
        xa = d["xa"]
        if xa not in xa_to_dgd:
            xa_to_dgd[xa] = []
        xa_to_dgd[xa].append(d)

    chon_xa = st.selectbox("Chọn Xã/Phường", sorted(xa_to_dgd.keys()), key="cbtd_gan_xa")
    ds_dgd_xa = xa_to_dgd.get(chon_xa, [])

    if not ds_dgd_xa:
        st.info(f"Không có ĐGD nào cho xã **{chon_xa}**.")
        return

    # Get CBTD list for this PGD
    ds_cbtd_pgd = [(ma, info) for ma, info in cbtd_data.items() if info.get("pgd") == ten_pgd]

    st.caption(f"**{len(ds_dgd_xa)}** ĐGD tại {chon_xa} — **{len(ds_cbtd_pgd)}** CBTD trong {ten_pgd}")

    # Build options for selectbox
    cbtd_opts = ["— Chưa gán"] + [f"{ma} — {info['ho_ten']}" for ma, info in ds_cbtd_pgd]
    cbtd_map = {f"{ma} — {info['ho_ten']}": ma for ma, info in ds_cbtd_pgd}

    # Track changes
    changed = False
    new_assignments: dict[str, str | None] = {}  # dgd_name -> ma_cb or None

    for dgd_info in ds_dgd_xa:
        ten_dgd = dgd_info["ten"]
        current_ma = dgd_to_cbtd.get((ten_pgd, ten_dgd))
        current_label = f"{current_ma} — {cbtd_data[current_ma]['ho_ten']}" if current_ma else "— Chưa gán"

        # Find ap list for this DGD
        ap_list: list[str] = []
        xa_dgd = dgd_map.get(ten_pgd, {}).get(chon_xa, {})
        if isinstance(xa_dgd, dict) and ten_dgd in xa_dgd:
            entry = xa_dgd[ten_dgd]
            if isinstance(entry, dict):
                ap_list = entry.get("thon", [])
            elif isinstance(entry, list):
                ap_list = entry

        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**📍 {ten_dgd}**")
            st.caption(f"📌 {dgd_info['dia_diem']} — Ngày {dgd_info['ngay_gd']} {dgd_info['gio_gd']}")
        with col2:
            selected = st.selectbox(
                "CBTD phụ trách",
                cbtd_opts,
                index=cbtd_opts.index(current_label) if current_label in cbtd_opts else 0,
                key=f"cbtd_sel_{ten_pgd}_{chon_xa}_{ten_dgd}",
            )
            selected_ma = cbtd_map.get(selected)
            if selected_ma != current_ma:
                new_assignments[ten_dgd] = selected_ma
                changed = True

        if ap_list:
            st.caption(f"   └─ {len(ap_list)} thôn/ấp: {', '.join(ap_list[:5])}{'...' if len(ap_list) > 5 else ''}")
        else:
            st.caption("   └─ ⚠️ Chưa gán thôn/ấp")
        st.divider()

    # Summary table
    if new_assignments:
        st.markdown("**📝 Thay đổi sắp lưu:**")
        for dgd, ma_cb in new_assignments.items():
            if ma_cb:
                st.caption(f"• **{dgd}** → {ma_cb} — {cbtd_data[ma_cb]['ho_ten']}")
            else:
                old_ma = dgd_to_cbtd.get((ten_pgd, dgd))
                if old_ma:
                    st.caption(f"• **{dgd}** → ❌ Bỏ gán (đang thuộc {old_ma})")

    if st.button("💾 Lưu phân công", type="primary", key="btn_luu_gan_cbtd", disabled=not changed):
        # Update cbtd_data
        for dgd, new_ma in new_assignments.items():
            old_ma = dgd_to_cbtd.get((ten_pgd, dgd))
            if old_ma and old_ma != new_ma:
                # Remove from old CBTD
                if dgd in cbtd_data[old_ma].get("ds_dgd", []):
                    cbtd_data[old_ma]["ds_dgd"].remove(dgd)
                    cbtd_data[old_ma]["ngay_cap"] = datetime.today().strftime("%d/%m/%Y %H:%M")
            if new_ma:
                # Add to new CBTD
                if dgd not in cbtd_data[new_ma].get("ds_dgd", []):
                    cbtd_data[new_ma].setdefault("ds_dgd", []).append(dgd)
                    cbtd_data[new_ma]["ngay_cap"] = datetime.today().strftime("%d/%m/%Y %H:%M")

        luu_cbtd(cbtd_data)
        db.ghi_audit(
            username, "gan_cbtd_dgd",
            f"[{hn}] PGD={ten_pgd} xa={chon_xa} assignments={new_assignments}",
        )
        st.success("✅ Đã lưu phân công CBTD.")
        st.rerun()
