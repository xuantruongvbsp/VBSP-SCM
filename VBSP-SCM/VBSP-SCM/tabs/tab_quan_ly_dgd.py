"""Tab quản lý Điểm Giao Dịch (dgd_map) — Phân hệ ws_management."""
from __future__ import annotations

import copy
import difflib
import io
import re
import socket
from typing import TYPE_CHECKING, Any

import pandas as pd
import streamlit as st

from config import (
    DON_VI_CHI_NHANH,
    DS_PGD,
    PGD_XA_MAP,
)

import db
from data.dgd_helpers import (
    dem_thong_ke,
    dgd_dang_dung_trong_hstd,
    pool_thon_cho_xa,
    tao_file_mau_dgd,
)
from data.pgd import pgd_slug
from utils import fmt_so, hien_thi_dataframe_phan_trang

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def _df_hstd(kwargs: dict[str, Any]) -> pd.DataFrame:
    df = kwargs.get("df_full")
    if df is None or df.empty:
        df = kwargs.get("df")
    if df is None:
        return pd.DataFrame()
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _clean_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v).replace("\u00a0", " ").replace("\u202f", " ").strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return ""
    return re.sub(r"\s+", " ", s)


def _split_ap_cell(v: Any) -> list[str]:
    s = _clean_cell(v)
    if not s:
        return []
    parts = re.split(r"[,\n;]+", s)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        t = re.sub(r"\s+", " ", str(p).strip())
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _norm_cmp(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip()).lower()


def _file_id(up: Any) -> str:
    fid = getattr(up, "file_id", None)
    if fid:
        return str(fid)
    name = getattr(up, "name", "") or ""
    size = getattr(up, "size", "") or ""
    return f"{name}:{size}"


def _apply_xa_patch(
    parsed_xa: dict[str, dict[str, list[str]]], patch: dict[str, str]
) -> dict[str, dict[str, list[str]]]:
    if not parsed_xa or not patch:
        return parsed_xa

    patch_norm = {_norm_cmp(k): v for k, v in patch.items() if str(k).strip() and str(v).strip()}
    if not patch_norm:
        return parsed_xa

    out: dict[str, dict[str, list[str]]] = {}
    for xa, dct in parsed_xa.items():
        xa_new = patch_norm.get(_norm_cmp(xa), xa)
        cur = out.setdefault(xa_new, {})
        for dgd, aps in (dct or {}).items():
            lst = aps if isinstance(aps, list) else []
            if dgd not in cur:
                cur[dgd] = [str(a).strip() for a in lst if str(a).strip()]
            else:
                seen = {str(a).strip().lower() for a in cur[dgd] if str(a).strip()}
                for a in lst:
                    t = str(a).strip()
                    if not t:
                        continue
                    if t.lower() in seen:
                        continue
                    cur[dgd].append(t)
                    seen.add(t.lower())
    return out


def _apply_thon_patch(
    parsed_xa: dict[str, dict[str, list[str]]], patch: dict[str, str]
) -> dict[str, dict[str, list[str]]]:
    if not parsed_xa or not patch:
        return parsed_xa

    patch_norm = {_norm_cmp(k): v for k, v in patch.items() if str(k).strip() and str(v).strip()}
    if not patch_norm:
        return parsed_xa

    out: dict[str, dict[str, list[str]]] = {}
    for xa, dct in parsed_xa.items():
        out_xa: dict[str, list[str]] = {}
        for dgd, aps in (dct or {}).items():
            lst = aps if isinstance(aps, list) else []
            seen: set[str] = set()
            new_lst: list[str] = []
            for a in lst:
                t = str(a).strip()
                if not t:
                    continue
                t2 = patch_norm.get(_norm_cmp(t), t)
                k = _norm_cmp(t2)
                if k in seen:
                    continue
                seen.add(k)
                new_lst.append(t2)
            out_xa[dgd] = new_lst
        out[xa] = out_xa
    return out


_XA_PREFIX_RANK = (
    "thị trấn ",
    "thị xã ",
    "phường ",
    "xã ",
)


def _norm_xa_key(s: str) -> str:
    t = _norm_cmp(s)
    for prefix in _XA_PREFIX_RANK:
        if t.startswith(prefix):
            t = t[len(prefix) :].strip()
            break
    return _norm_cmp(t)


def _merge_xa_blocks(blocks: list[Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for b in blocks:
        if not isinstance(b, dict):
            continue
        for dgd, lst in b.items():
            if dgd not in out:
                out[dgd] = []
            if not isinstance(lst, list):
                continue
            seen = {str(t).strip().lower() for t in out[dgd] if str(t).strip()}
            for t in lst:
                s = str(t).strip()
                if not s or s.lower() == "nan":
                    continue
                if s.lower() in seen:
                    continue
                out[dgd].append(s)
                seen.add(s.lower())
    return out


def _get_xa_block_norm(block: dict[str, Any], ten_xa: str) -> dict[str, list[str]]:
    if not isinstance(block, dict):
        return {}
    n = _norm_xa_key(ten_xa)
    keys = [k for k in block.keys() if _norm_xa_key(str(k)) == n]
    if not keys:
        return {}
    return _merge_xa_blocks([block.get(k) for k in keys])


def _merge_alias_xa_keys_in_map(m: dict[str, Any], ten_pgd: str, ten_xa: str) -> None:
    pgd_block = (m or {}).get(ten_pgd, {})
    if not isinstance(pgd_block, dict):
        return
    n = _norm_xa_key(ten_xa)
    keys = [k for k in list(pgd_block.keys()) if _norm_xa_key(str(k)) == n]
    if not keys:
        return
    merged = _merge_xa_blocks([pgd_block.get(k) for k in keys])
    pgd_block[ten_xa] = merged
    for k in keys:
        if k != ten_xa:
            pgd_block.pop(k, None)


def _trang_thai_pgd_day_du(ten_pgd: str, dgd_map: dict[str, Any]) -> tuple[str, str]:
    block = (dgd_map or {}).get(ten_pgd, {})
    if not isinstance(block, dict) or not block:
        return "⚠️ Chưa cấu hình", "Chưa có dgd_map"

    ds_xa = PGD_XA_MAP.get(ten_pgd, []) or []
    empty_df = pd.DataFrame()
    co_du_lieu_hstd = False
    chua_gan = 0

    for ten_xa in ds_xa:
        pool = pool_thon_cho_xa(empty_df, ten_pgd, ten_xa, dgd_map)
        pool_set = {
            str(t).strip()
            for t in (pool or [])
            if str(t).strip() and str(t).strip().lower() != "nan"
        }
        if pool_set:
            co_du_lieu_hstd = True

        xa_block = _get_xa_block_norm(block, ten_xa)
        da_gan = {
            str(t).strip()
            for lst in xa_block.values()
            for t in (lst if isinstance(lst, list) else [])
            if str(t).strip() and str(t).strip().lower() != "nan"
        }

        chua_gan += len(pool_set - da_gan)

    if not co_du_lieu_hstd:
        return "❓ Chưa có HSTD", "Upload HSTD để kiểm tra"
    if chua_gan > 0:
        return f"⚠️ Còn {chua_gan} thôn chưa gán", ""
    return "✅ Đầy đủ", ""


def _build_rows_tong_quan(dgd_map: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    tong_xa = 0
    tong_dgd = 0
    tong_ap = 0
    n_ok = 0
    n_warn = 0
    n_unknown = 0

    for ten_pgd in sorted(PGD_XA_MAP.keys()):
        block = (dgd_map or {}).get(ten_pgd, {})
        if not isinstance(block, dict):
            block = {}
        so_xa = len(block)
        so_dgd = 0
        so_ap = 0
        for xa_d in block.values():
            if isinstance(xa_d, dict):
                so_dgd += len(xa_d)
                for lst in xa_d.values():
                    if isinstance(lst, list):
                        so_ap += len(lst)

        tong_xa += so_xa
        tong_dgd += so_dgd
        tong_ap += so_ap

        stt, note = _trang_thai_pgd_day_du(ten_pgd, dgd_map)
        if str(stt).startswith("✅"):
            n_ok += 1
        elif str(stt).startswith("⚠️"):
            n_warn += 1
        elif str(stt).startswith("❓"):
            n_unknown += 1

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

    return rows, {
        "tong_xa": tong_xa,
        "tong_dgd": tong_dgd,
        "tong_ap": tong_ap,
        "n_ok": n_ok,
        "n_warn": n_warn,
        "n_unknown": n_unknown,
    }


def _render_panel_loi(errors: list[dict[str, Any]]) -> None:
    if not errors:
        return
    with st.expander(
        f"⚠️ {len(errors)} lỗi cần xử lý — nhấn để xem chi tiết", expanded=True
    ):
        st.dataframe(
            pd.DataFrame(errors)[["hang", "cot", "loi", "huong_xu_ly"]],
            column_config={
                "hang": st.column_config.NumberColumn("Hàng", format="%d"),
                "cot": st.column_config.TextColumn("Cột"),
                "loi": st.column_config.TextColumn("Lỗi"),
                "huong_xu_ly": st.column_config.TextColumn("Hướng xử lý"),
            },
            hide_index=True,
            use_container_width=True,
        )
        if st.button("🔄 Upload lại file khác", key="dgd_retry_upload"):
            st.session_state["dgd_xa_patch"] = {}
            st.session_state["dgd_thon_patch"] = {}
            st.session_state["dgd_last_file_id"] = ""
            st.session_state["dgd_uploader_ver"] = int(
                st.session_state.get("dgd_uploader_ver", 0)
            ) + 1
            st.rerun()


def _render_panel_khop_ten(
    parsed_xa: dict[str, dict[str, list[str]]], ten_pgd: str
) -> dict[str, dict[str, list[str]]]:
    if not parsed_xa:
        return parsed_xa

    ds_xa_cfg = [str(x).strip() for x in (PGD_XA_MAP.get(ten_pgd, []) or []) if str(x).strip()]
    if not ds_xa_cfg:
        return parsed_xa

    cfg_norm = {_norm_cmp(x) for x in ds_xa_cfg}
    xa_khong_khop = [xa for xa in parsed_xa.keys() if _norm_cmp(xa) not in cfg_norm]
    if not xa_khong_khop:
        return parsed_xa

    dgd_map = db.doc_dgd_map()
    tab_xa, tab_thon = st.tabs(["🏘️ Xã/Phường không khớp", "🏡 Thôn/Ấp không khớp"])

    with tab_xa:
        st.caption("Chọn gợi ý đúng để patch tên xã trong session (không lưu DB).")
        for xa in xa_khong_khop:
            best = ""
            best_ratio = 0.0
            xa_n = _norm_cmp(xa)
            for cand in ds_xa_cfg:
                r = difflib.SequenceMatcher(None, xa_n, _norm_cmp(cand)).ratio()
                if r > best_ratio:
                    best_ratio = r
                    best = cand
            if best_ratio < 0.5:
                best = ""

            c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
            with c1:
                st.write(xa)
            with c2:
                st.write(best or "—")
            with c3:
                st.write(f"{int(best_ratio * 100)}%")
            with c4:
                if st.button(
                    "✅ Dùng tên này",
                    key=f"dgd_patch_xa_{_norm_cmp(xa)}",
                    disabled=not bool(best),
                ):
                    st.session_state.setdefault("dgd_xa_patch", {})[xa] = best
                    st.rerun()

    with tab_thon:
        st.caption("Chỉ hiển thị thôn/ấp thuộc xã đã khớp (hoặc đã patch).")
        thon_patch: dict[str, str] = st.session_state.get("dgd_thon_patch", {}) or {}
        xa_resolved = [xa for xa in parsed_xa.keys() if _norm_cmp(xa) in cfg_norm]
        xa_unresolved = [xa for xa in parsed_xa.keys() if _norm_cmp(xa) not in cfg_norm]
        if xa_unresolved:
            st.caption(
                "Đang khoá kiểm tra thôn/ấp vì tên xã chưa khớp: "
                + ", ".join(xa_unresolved[:10])
                + ("…" if len(xa_unresolved) > 10 else "")
            )
        if not xa_resolved:
            st.info("Chưa có xã nào khớp để kiểm tra thôn/ấp.")
            return parsed_xa

        max_rows = 120
        shown = 0
        for xa in xa_resolved:
            dgd_block = (dgd_map or {}).get(ten_pgd, {}).get(xa, {})
            if not isinstance(dgd_block, dict):
                dgd_block = {}
            ref_thon = sorted(
                {
                    str(t).strip()
                    for lst in dgd_block.values()
                    for t in (lst or [])
                    if str(t).strip()
                }
            )
            if not ref_thon:
                continue

            ref_norm = {_norm_cmp(t) for t in ref_thon}
            thon_in_file = sorted(
                {
                    str(t).strip()
                    for dct in (parsed_xa.get(xa, {}) or {}).values()
                    for t in (dct or [])
                    if str(t).strip()
                }
            )
            thon_khong_khop = [t for t in thon_in_file if _norm_cmp(t) not in ref_norm]
            if not thon_khong_khop:
                continue

            st.markdown(f"**{xa}**")
            for thon in thon_khong_khop:
                if shown >= max_rows:
                    st.caption("Đã giới hạn hiển thị để tránh lag — thu hẹp dữ liệu để xem thêm.")
                    return parsed_xa

                best = ""
                best_ratio = 0.0
                tn = _norm_cmp(thon)
                for cand in ref_thon:
                    r = difflib.SequenceMatcher(None, tn, _norm_cmp(cand)).ratio()
                    if r > best_ratio:
                        best_ratio = r
                        best = cand
                if best_ratio < 0.5:
                    best = ""

                c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
                with c1:
                    st.write(thon)
                with c2:
                    st.write(best or "—")
                with c3:
                    st.write(f"{int(best_ratio * 100)}%")
                with c4:
                    if st.button(
                        "✅ Dùng tên này",
                        key=f"dgd_patch_thon_{_norm_cmp(xa)}_{_norm_cmp(thon)}",
                        disabled=not bool(best),
                    ):
                        thon_patch[thon] = best
                        st.session_state["dgd_thon_patch"] = thon_patch
                        st.rerun()
                shown += 1

        if shown == 0:
            st.info("Không phát hiện thôn/ấp lệch danh mục (hoặc danh mục thôn chưa có trong dgd_map).")

    return parsed_xa


def _render_modal_danh_muc(ten_pgd: str) -> None:
    with st.expander("📖 Tra cứu danh mục xã/thôn hợp lệ", expanded=False):
        col_pgd, col_search = st.columns([2, 3])
        with col_pgd:
            options = ["Tất cả"] + DS_PGD
            idx = options.index(ten_pgd) if ten_pgd in options else 0
            pgd_loc = st.selectbox("Lọc theo PGD", options, index=idx, key="dm_pgd")
        with col_search:
            tu_khoa = st.text_input(
                "🔍 Tìm tên xã/thôn",
                placeholder="Nhập tên...",
                key="dm_search",
            ).strip()

        dgd_map = db.doc_dgd_map()
        ds_hien_thi: list[tuple[str, str]] = []
        tu_khoa_n = tu_khoa.lower()

        for pgd, ds_xa in PGD_XA_MAP.items():
            if pgd_loc != "Tất cả" and pgd != pgd_loc:
                continue
            for xa in ds_xa or []:
                xa_s = str(xa).strip()
                if not xa_s:
                    continue
                if tu_khoa_n and tu_khoa_n not in xa_s.lower():
                    dgd_block = (dgd_map or {}).get(pgd, {}).get(xa_s, {})
                    if not isinstance(dgd_block, dict):
                        dgd_block = {}
                    all_thon = [
                        str(t).strip()
                        for lst in dgd_block.values()
                        for t in (lst or [])
                        if str(t).strip()
                    ]
                    if not any(tu_khoa_n in t.lower() for t in all_thon):
                        continue
                ds_hien_thi.append((pgd, xa_s))

        if not ds_hien_thi:
            st.info("Không tìm thấy kết quả.")
            return

        st.caption(f"Tìm thấy {len(ds_hien_thi)} xã/phường")
        for pgd, xa in ds_hien_thi[:50]:
            dgd_block = (dgd_map or {}).get(pgd, {}).get(xa, {})
            if not isinstance(dgd_block, dict):
                dgd_block = {}
            all_thon = sorted(
                {
                    str(t).strip()
                    for lst in dgd_block.values()
                    for t in (lst or [])
                    if str(t).strip()
                }
            )

            label = f"**{xa}** ({pgd})"
            if all_thon:
                label += f" — {len(all_thon)} thôn/ấp"

            with st.expander(label, expanded=False):
                col_info, col_copy = st.columns([4, 1])
                with col_info:
                    st.code(xa, language=None)
                    if all_thon:
                        for t in all_thon:
                            st.text(f"  └ {t}")
                    else:
                        st.caption("(Chưa có thôn/ấp trong dgd_map)")
                with col_copy:
                    st.caption("Tên chuẩn:")
                    st.code(xa, language=None)

        if len(ds_hien_thi) > 50:
            st.caption(
                f"Đang hiển thị 50/{len(ds_hien_thi)} — thu hẹp bộ lọc để xem thêm."
            )


def _parse_excel_import(
    uploaded: bytes, ten_pgd: str
) -> tuple[dict[str, dict[str, list[str]]], list[dict[str, Any]]]:
    _ = ten_pgd
    raw = pd.read_excel(io.BytesIO(uploaded), header=None)
    if raw.shape[1] < 4:
        raise ValueError("File phải có ít nhất 4 cột (A–D).")

    start = 0
    if raw.shape[0] > 0:
        c0 = _clean_cell(raw.iloc[0, 0]).lower()
        c1 = _clean_cell(raw.iloc[0, 1]).lower() if raw.shape[1] > 1 else ""
        if c0 in ("stt", "số tt", "so tt") or ("xã" in c1 or "phường" in c1):
            start = 1

    body = raw.iloc[start:, :4].copy()
    body.columns = ["stt", "xa", "dgd", "ap"]

    out: dict[str, dict[str, list[str]]] = {}
    errors: list[dict[str, Any]] = []

    xa_norm_to_key: dict[str, str] = {}
    dgd_seen_by_xa: dict[str, set[str]] = {}
    ap_seen_by_xa: dict[str, set[str]] = {}

    for pos, (_, row) in enumerate(body.iterrows()):
        ten_xa = _clean_cell(row["xa"])
        ten_dgd = _clean_cell(row["dgd"])
        ds_ap = _split_ap_cell(row["ap"])

        if not ten_xa and not ten_dgd and not ds_ap:
            continue

        hang_excel = pos + start + 1

        if not ten_xa:
            errors.append(
                {
                    "hang": hang_excel,
                    "cot": "Xã",
                    "loi": "Thiếu tên xã",
                    "huong_xu_ly": "Điền tên xã vào cột B",
                }
            )
            continue

        if not ten_dgd:
            errors.append(
                {
                    "hang": hang_excel,
                    "cot": "ĐGD",
                    "loi": "Thiếu tên ĐGD",
                    "huong_xu_ly": "Điền tên điểm giao dịch vào cột C",
                }
            )
            continue

        xa_norm = ten_xa.lower()
        xa_key = xa_norm_to_key.setdefault(xa_norm, ten_xa)

        dgd_norm = ten_dgd.lower()
        dgd_seen = dgd_seen_by_xa.setdefault(xa_norm, set())
        if dgd_norm in dgd_seen:
            errors.append(
                {
                    "hang": hang_excel,
                    "cot": "ĐGD",
                    "loi": "ĐGD trùng tên",
                    "huong_xu_ly": "Đổi tên hoặc gộp ấp vào 1 dòng",
                }
            )
            continue

        ap_seen = ap_seen_by_xa.setdefault(xa_norm, set())
        if ds_ap:
            ap_norms = [a.lower() for a in ds_ap]
            if any(a in ap_seen for a in ap_norms):
                errors.append(
                    {
                        "hang": hang_excel,
                        "cot": "Ấp/KP",
                        "loi": "Ấp/KP trùng",
                        "huong_xu_ly": "Mỗi ấp chỉ được gán cho 1 ĐGD",
                    }
                )
                continue

        xa_block = out.setdefault(xa_key, {})
        xa_block[ten_dgd] = list(ds_ap)
        dgd_seen.add(dgd_norm)
        for a in ds_ap:
            ap_seen.add(a.lower())

    return out, errors


def render(tab: DeltaGenerator, **kwargs: Any) -> None:
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    df_h = _df_hstd(kwargs)
    hn = _hostname()

    with tab:
        st.subheader("📍 Điểm Giao Dịch (dgd_map)")
        st.caption(
            "Cấu hình ĐGD — thôn/ấp theo PGD/Xã. Import Excel hoặc sửa trực tiếp."
        )

        with st.expander("📖 Hướng dẫn sử dụng", expanded=False):
            st.markdown(
                """
**Import từ file**
- Chọn đúng PGD trước khi upload — file PGD nào chọn đúng PGD đó.
- Bấm **Tải file mẫu Excel** để có file đúng định dạng (4 cột: STT | Xã | ĐGD | Ấp/KP).
- Kiểm tra Preview trước khi bấm Merge.
- **Merge**: chỉ ghi đè PGD đang chọn, các PGD khác giữ nguyên. ✅ Dùng hầu hết trường hợp.
- **Thay thế toàn bộ**: xóa sạch toàn bộ map, chỉ còn PGD vừa chọn. ⚠️ Chỉ admin, chỉ dùng khi reset hoàn toàn.

**Xem & Sửa**
- Chọn PGD → Chọn Xã → mở expander từng ĐGD để đổi tên / thêm bớt thôn / xóa.
- Không thể đổi tên hoặc xóa ĐGD đang có hồ sơ trong HSTD.

**Lỡ Merge nhầm PGD?**
- Upload lại file đúng cho PGD bị ghi sai → Merge lại để ghi đè.
- Sau đó upload file đúng cho PGD bị thiếu.
"""
            )

        if role == "executive":
            _render_tong_quan(df_h, username, hn)
            return

        t_imp, t_edit, t_sum = st.tabs(
            ["📥 Import từ file", "🗺️ Xem & Sửa", "📋 Tổng quan"]
        )

        with t_imp:
            if role not in ("admin", "manager"):
                st.warning("Bạn chỉ có quyền xem tổng quan (executive) hoặc không đủ quyền.")
            else:
                _render_import(role, username, hn)

        with t_edit:
            if role not in ("admin", "manager"):
                st.warning("Bạn không có quyền sửa.")
            else:
                _render_xem_sua(df_h, username, hn)

        with t_sum:
            _render_tong_quan(df_h, username, hn)


def _render_import(role: str, username: str, hn: str) -> None:
    ten_pgd = st.selectbox("Chọn PGD", [DON_VI_CHI_NHANH] + DS_PGD, key="dgd_imp_pgd")
    dgd_map_cur = db.doc_dgd_map()
    buf_mau = tao_file_mau_dgd(ten_pgd, dgd_map_cur)
    st.download_button(
        "📤 Tải file mẫu Excel (2 sheet: Nhập liệu + Danh mục thôn)",
        data=buf_mau,
        file_name=f"mau_dgd_{pgd_slug(ten_pgd)}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dgd_imp_dl_mau",
        use_container_width=True,
    )
    if "dgd_uploader_ver" not in st.session_state:
        st.session_state["dgd_uploader_ver"] = 0

    _render_modal_danh_muc(ten_pgd)

    up = st.file_uploader(
        "File Excel (cột A–D: STT | Xã | ĐGD | Ấp/KP)",
        type=["xlsx", "xls"],
        key=f"dgd_uploader_{st.session_state['dgd_uploader_ver']}",
    )
    if up:
        parse_failed = False
        try:
            with st.spinner("⏳ Đang đọc và kiểm tra file..."):
                parsed_xa, errors = _parse_excel_import(up.getvalue(), ten_pgd)
        except Exception as e:
            st.error(f"❌ Không đọc được file: {e}")
            db.ghi_audit(username, "import_dgd_map_loi", f"[{hn}] {e}")
            parsed_xa = {}
            errors = []
            parse_failed = True

        if not parse_failed:
            fid = _file_id(up)
            if (
                "dgd_last_file_id" not in st.session_state
                or st.session_state["dgd_last_file_id"] != fid
            ):
                st.session_state["dgd_xa_patch"] = {}
                st.session_state["dgd_thon_patch"] = {}
                st.session_state["dgd_last_file_id"] = fid

            parsed_xa = _apply_xa_patch(
                parsed_xa, st.session_state.get("dgd_xa_patch", {}) or {}
            )
            parsed_xa = _apply_thon_patch(
                parsed_xa, st.session_state.get("dgd_thon_patch", {}) or {}
            )

            if parsed_xa:
                _n_pgd, n_xa, n_dgd, n_ap = dem_thong_ke(parsed_xa)
                st.success(
                    f"✅ Đã đọc file: {fmt_so(n_xa)} xã · {fmt_so(n_dgd)} ĐGD · {fmt_so(n_ap)} ấp/KP"
                )
            else:
                st.warning("⚠️ File không có dòng dữ liệu hợp lệ để import.")

            _render_panel_loi(errors)

            if parsed_xa:
                parsed_xa = _render_panel_khop_ten(parsed_xa, ten_pgd)

            # ── Validate xã trong file có khớp PGD chọn không ──
            ds_xa_cfg = {
                str(x).strip().lower()
                for x in (PGD_XA_MAP.get(ten_pgd, []) or [])
            }
            xa_ngoai_pham_vi = [
                x
                for x in parsed_xa.keys()
                if str(x).strip().lower() not in ds_xa_cfg
            ]

            if ds_xa_cfg and xa_ngoai_pham_vi:
                st.warning(
                    f"⚠️ File chứa **{len(xa_ngoai_pham_vi)}** xã không thuộc PGD "
                    f"**{ten_pgd}** theo cấu hình:\n\n"
                    + ", ".join(f"*{x}*" for x in sorted(xa_ngoai_pham_vi)[:10])
                    + ("…" if len(xa_ngoai_pham_vi) > 10 else "")
                    + "\n\n**Bạn có thể đã chọn nhầm PGD hoặc upload nhầm file.**"
                )
                # Vẫn hiển thị preview và cho phép Merge — nhưng disable nút
                # bằng cách thêm checkbox xác nhận
                chap_nhan = st.checkbox(
                    "Tôi hiểu dữ liệu có thể sai PGD và vẫn muốn tiếp tục",
                    key="dgd_imp_chap_nhan_sai_xa",
                )
            else:
                chap_nhan = True  # không có xã lạ → cho phép Merge bình thường

            _n_pgd, n_xa, n_dgd, n_ap = dem_thong_ke(parsed_xa)
            st.markdown(
                f"**Preview:** PGD **{ten_pgd}** — {fmt_so(n_xa)} xã, "
                f"{fmt_so(n_dgd)} ĐGD, {fmt_so(n_ap)} ấp/khu phố."
            )
            rows = []
            for xa, dct in sorted(parsed_xa.items()):
                for dgd, ds_ap in sorted(dct.items()):
                    rows.append(
                        {
                            "Xã": xa,
                            "Điểm GD": dgd,
                            "Ấp/KP": ", ".join(ds_ap),
                            "Số ấp": len(ds_ap),
                        }
                    )
            if rows:
                hien_thi_dataframe_phan_trang(pd.DataFrame(rows), key="dgd_imp_preview", height=280)
            else:
                st.warning("Không có dòng dữ liệu hợp lệ sau khi parse.")

            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    "Merge vào dgd_map hiện tại",
                    type="primary",
                    key="dgd_merge",
                    disabled=not chap_nhan,
                ):
                    try:
                        m = copy.deepcopy(db.doc_dgd_map())
                        m[ten_pgd] = parsed_xa
                        db.luu_dgd_map(m, username)
                        db.ghi_audit(
                            username,
                            "import_dgd_map_merge",
                            f"[{hn}] merge PGD={ten_pgd} — "
                            f"{n_xa} xã, {n_dgd} ĐGD, {n_ap} ấp",
                        )
                        st.cache_data.clear()
                        st.success("✅ Đã lưu. Đang tải lại...")
                        st.rerun()
                    except Exception as e:
                        db.ghi_audit(username, "import_dgd_map_loi", f"[{hn}] {e}")
                        st.error(f"❌ Lỗi: {e}")
            with c2:
                if role != "admin":
                    st.caption('Nút "Thay thế toàn bộ" chỉ dành cho admin.')
                else:
                    st.warning(
                        "⚠️ **Thay thế toàn bộ** sẽ xóa sạch dữ liệu tất cả PGD còn lại, "
                        "chỉ giữ lại PGD vừa chọn. Thao tác không thể hoàn tác tự động."
                    )
                    xn_replace = st.checkbox(
                        f"Tôi xác nhận muốn xóa toàn bộ dgd_map và chỉ giữ lại **{ten_pgd}**",
                        key="dgd_replace_xn",
                    )
                    if st.button(
                        "Thay thế toàn bộ dgd_map",
                        type="secondary",
                        key="dgd_replace_all",
                        disabled=not xn_replace,
                    ):
                        try:
                            db.luu_dgd_map({ten_pgd: parsed_xa}, username)
                            db.ghi_audit(
                                username,
                                "thay_the_dgd_map_toan_bo",
                                f"[{hn}] chỉ còn PGD={ten_pgd} (toàn bộ map bị ghi đè)",
                            )
                            st.cache_data.clear()
                            st.success("✅ Đã lưu. Đang tải lại...")
                            st.rerun()
                        except Exception as e:
                            db.ghi_audit(username, "import_dgd_map_loi", f"[{hn}] {e}")
                            st.error(f"❌ Lỗi: {e}")
    else:
        st.info("Chọn file Excel để xem preview và lưu.")

    st.divider()
    st.markdown("### ➕ Thêm mới Điểm giao dịch")

    dgd_map_imp: dict[str, Any] = copy.deepcopy(db.doc_kv("dgd_map") or {})

    ten_pgd_imp = st.selectbox(
        "Chọn PGD",
        options=[DON_VI_CHI_NHANH] + DS_PGD,
        key="imp_chon_pgd",
    )

    ds_xa_imp = [str(x).strip() for x in (PGD_XA_MAP.get(ten_pgd_imp, []) or [])]
    if not ds_xa_imp:
        st.warning(
            "PGD chưa có xã/phường trong PGD_XA_MAP — không thể thêm ĐGD thủ công."
        )
        return

    chon_xa_imp = st.selectbox(
        "Chọn Xã/Phường",
        options=ds_xa_imp,
        key="imp_chon_xa",
    )

    st.text_input(
        "Tên Điểm giao dịch",
        key="imp_ten_dgd",
        placeholder="Ví dụ: Điểm GD 1",
    )
    ten_dgd_typed = str(st.session_state.get("imp_ten_dgd", "")).strip()

    pool_imp = pool_thon_cho_xa(
        pd.DataFrame(),
        ten_pgd_imp,
        chon_xa_imp,
        dgd_map_imp,
    )

    xa_hien_co = dgd_map_imp.get(ten_pgd_imp, {}).get(chon_xa_imp, {})
    if not isinstance(xa_hien_co, dict):
        xa_hien_co = {}

    thon_da_gan: set[str] = {
        str(t).strip()
        for dgd, thon_list in xa_hien_co.items()
        if dgd != ten_dgd_typed
        for t in (thon_list or [])
        if str(t).strip() and str(t).strip().lower() != "nan"
    }
    pool_kha_dung = [t for t in pool_imp if t not in thon_da_gan]

    if xa_hien_co:
        st.markdown(f"**ĐGD hiện có tại {chon_xa_imp}:**")
        for dgd_name, thon_list in list(xa_hien_co.items()):
            tl = thon_list if isinstance(thon_list, list) else []
            ap_txt = ", ".join(str(x).strip() for x in tl if str(x).strip()) or "(chưa gán thôn)"
            slug_x = re.sub(r"\W+", "_", str(dgd_name))[:80]
            col_dgd, col_xoa = st.columns([5, 1])
            with col_dgd:
                st.write(f"📍 **{dgd_name}** — {ap_txt}")
            with col_xoa:
                if st.button("🗑️", key=f"imp_xoa_dgd_{slug_x}", help="Xóa ĐGD"):
                    try:
                        del dgd_map_imp[ten_pgd_imp][chon_xa_imp][dgd_name]
                        if not dgd_map_imp[ten_pgd_imp][chon_xa_imp]:
                            del dgd_map_imp[ten_pgd_imp][chon_xa_imp]
                        if not dgd_map_imp[ten_pgd_imp]:
                            del dgd_map_imp[ten_pgd_imp]
                        db.luu_dgd_map(dgd_map_imp, username)
                        db.ghi_audit(
                            username,
                            "imp_xoa_dgd",
                            f"[{hn}] PGD={ten_pgd_imp} xã={chon_xa_imp} ĐGD={dgd_name}",
                        )
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        db.ghi_audit(username, "imp_loi_dgd", f"[{hn}] xóa ĐGD: {e}")
                        st.error(f"❌ Lỗi xóa: {e}")

    chon_thon_imp = st.multiselect(
        "Chọn thôn/ấp phụ trách",
        options=pool_kha_dung,
        help="Chỉ hiển thị thôn chưa gán cho ĐGD khác trong cùng xã.",
        key="imp_chon_thon",
    )
    if not pool_imp:
        st.caption("⚠️ Chưa có danh sách thôn — kiểm tra lại file HSTD của PGD này.")

    if st.button("➕ Thêm Điểm giao dịch", key="imp_btn_them", type="primary"):
        if not ten_dgd_typed:
            st.error("❌ Vui lòng nhập tên Điểm giao dịch.")
        elif ten_dgd_typed in xa_hien_co:
            st.error(f"❌ ĐGD '{ten_dgd_typed}' đã tồn tại tại {chon_xa_imp}.")
        else:
            dup_b: list[str] = []
            for other, lst in xa_hien_co.items():
                if not isinstance(lst, list):
                    continue
                for t in chon_thon_imp:
                    if t in lst:
                        dup_b.append(f"{t} → {other}")
            if dup_b:
                st.error(
                    "❌ Trùng thôn/ấp với ĐGD khác: " + ", ".join(dup_b)
                )
            else:
                try:
                    m = copy.deepcopy(db.doc_dgd_map())
                    cur = m.setdefault(ten_pgd_imp, {}).setdefault(chon_xa_imp, {})
                    cur[ten_dgd_typed] = [str(t).strip() for t in chon_thon_imp]
                    db.luu_dgd_map(m, username)
                    db.ghi_audit(
                        username,
                        "them_dgd",
                        f"[{hn}] PGD={ten_pgd_imp} / {chon_xa_imp} / "
                        f"{ten_dgd_typed}: {chon_thon_imp}",
                    )
                    st.cache_data.clear()
                    st.success(
                        f"✅ Đã thêm ĐGD '{ten_dgd_typed}' "
                        f"với {len(chon_thon_imp)} thôn."
                    )
                    st.rerun()
                except Exception as e:
                    db.ghi_audit(username, "imp_loi_dgd", f"[{hn}] thêm ĐGD: {e}")
                    st.error(f"❌ Lỗi lưu: {e}")


def _render_tong_quan(df_h: pd.DataFrame, username: str, hn: str) -> None:
    _ = df_h, username, hn
    st.markdown("### 📋 Tổng quan")
    st.caption("So sánh dgd_map với danh mục xã trong config.PGD_XA_MAP.")
    dgd_map = db.doc_dgd_map()
    with st.spinner("Đang kiểm tra dữ liệu..."):
        rows, stats = _build_rows_tong_quan(dgd_map)
    df_o = pd.DataFrame(rows)
    if df_o.empty:
        st.info("Không có PGD trong PGD_XA_MAP.")
        return
    info = f"📊 {len(df_o)} PGD — ✅ {stats['n_ok']} đầy đủ · ⚠️ {stats['n_warn']} cần xử lý"
    if stats["n_unknown"] > 0:
        info += f" · ❓ {stats['n_unknown']} chưa có HSTD"
    st.info(info)
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
    st.markdown(
        f"**Tổng:** {stats['tong_xa']} xã · {stats['tong_dgd']} ĐGD · {stats['tong_ap']} ấp/KP"
    )


def _render_xem_sua(df_h: pd.DataFrame, username: str, hn: str) -> None:
    dgd_map = copy.deepcopy(db.doc_dgd_map())
    ten_pgd = st.selectbox("Chọn PGD", [DON_VI_CHI_NHANH] + DS_PGD, key="dgd_edit_pgd")

    pgd_block = dgd_map.get(ten_pgd, {})
    if not isinstance(pgd_block, dict):
        pgd_block = {}
    xa_from_map = sorted(pgd_block.keys())
    ds_xa_cfg = list(PGD_XA_MAP.get(ten_pgd, []))

    if ds_xa_cfg:
        cfg_norm = {_norm_xa_key(x) for x in ds_xa_cfg}
        extra_xa = [x for x in xa_from_map if _norm_xa_key(x) not in cfg_norm]
        missing_xa = [
            x
            for x in ds_xa_cfg
            if not any(_norm_xa_key(k) == _norm_xa_key(x) for k in xa_from_map)
        ]
        dup: dict[str, list[str]] = {}
        for k in xa_from_map:
            nk = _norm_xa_key(k)
            if nk in cfg_norm:
                dup.setdefault(nk, []).append(k)
        dup = {nk: ks for nk, ks in dup.items() if len(ks) > 1}

        if missing_xa:
            st.caption(f"ℹ️ {len(missing_xa)} xã/phường chưa có dữ liệu trong dgd_map.")
        if extra_xa:
            st.warning(
                "⚠️ dgd_map có xã/phường không thuộc danh mục: "
                + ", ".join(extra_xa[:8])
                + (" …" if len(extra_xa) > 8 else "")
            )
        if dup:
            sample = []
            for ks in list(dup.values())[:3]:
                sample.append(" / ".join(ks[:3]))
            st.warning(
                "⚠️ dgd_map có xã/phường bị trùng tên (khác tiền tố): "
                + " · ".join(sample)
                + (" …" if len(dup) > 3 else "")
            )

        xa_options = list(ds_xa_cfg) + extra_xa
        chon_xa = st.selectbox("Chọn Xã/Phường", xa_options, key="dgd_edit_xa")
    elif xa_from_map:
        chon_xa = st.selectbox("Chọn Xã/Phường", xa_from_map, key="dgd_edit_xa")
    else:
        st.warning("PGD không có trong PGD_XA_MAP.")
        return

    alias_keys = [k for k in xa_from_map if _norm_xa_key(k) == _norm_xa_key(chon_xa)]
    xa_dgd = _merge_xa_blocks([pgd_block.get(k) for k in alias_keys])
    if alias_keys and (len(alias_keys) > 1 or alias_keys[0] != chon_xa):
        st.caption(
            "ℹ️ Dữ liệu xã đang được gộp từ: "
            + ", ".join(alias_keys[:5])
            + (" …" if len(alias_keys) > 5 else "")
        )

    if alias_keys:
        pgd_block_view = dict(pgd_block)
        pgd_block_view[chon_xa] = xa_dgd
        for k in alias_keys:
            if k != chon_xa:
                pgd_block_view.pop(k, None)
        dgd_map_view = dict(dgd_map)
        dgd_map_view[ten_pgd] = pgd_block_view
    else:
        dgd_map_view = dgd_map

    pool = pool_thon_cho_xa(df_h, ten_pgd, chon_xa, dgd_map_view)

    st.markdown(f"**ĐGD tại {chon_xa}**")

    da_gan = {
        str(t).strip()
        for lst in xa_dgd.values()
        for t in (lst if isinstance(lst, list) else [])
        if str(t).strip() and str(t).strip().lower() != "nan"
    }
    pool_set = {
        str(t).strip()
        for t in (pool or [])
        if str(t).strip() and str(t).strip().lower() != "nan"
    }
    chua_gan = [t for t in sorted(pool_set) if t not in da_gan]

    if not pool_set:
        st.caption("❓ Chưa có dữ liệu HSTD — không tính được thôn còn thiếu.")
    elif chua_gan:
        st.warning(
            f"⚠️ {len(chua_gan)} thôn/ấp chưa gán vào ĐGD nào: "
            + ", ".join(chua_gan[:5])
            + (" …" if len(chua_gan) > 5 else "")
        )
    else:
        st.success("✅ Tất cả thôn/ấp đã được gán vào ĐGD.")

    for ten_dgd in list(xa_dgd.keys()):
        ds_thon = xa_dgd.get(ten_dgd, [])
        if not isinstance(ds_thon, list):
            ds_thon = []
        sid = re.sub(r"\W+", "_", ten_dgd)[:40]
        with st.expander(f"📍 {ten_dgd}", expanded=False):
            ten_moi = st.text_input(
                "Tên ĐGD",
                value=ten_dgd,
                key=f"dgd_nm_{sid}_{ten_pgd}_{chon_xa}",
            )
            thon_sel = st.multiselect(
                "Thôn/ấp",
                options=pool,
                default=[t for t in ds_thon if t in pool],
                key=f"dgd_th_{sid}_{ten_pgd}_{chon_xa}",
            )
            c_s, c_d = st.columns(2)
            with c_s:
                if st.button("💾 Lưu thay đổi", key=f"dgd_sv_{sid}_{ten_pgd}_{chon_xa}"):
                    tm = ten_moi.strip()
                    if not tm:
                        st.error("Tên ĐGD không được để trống.")
                    elif dgd_dang_dung_trong_hstd(df_h, ten_pgd, chon_xa, ten_dgd) and (
                        tm != ten_dgd.strip()
                    ):
                        st.error(
                            "ĐGD đang có hồ sơ trong HSTD — không đổi tên được. "
                            "Cập nhật HSTD trước."
                        )
                    elif tm != ten_dgd and tm in xa_dgd:
                        st.error("Tên ĐGD mới đã tồn tại.")
                    else:
                        dup_m: list[str] = []
                        for other, lst in xa_dgd.items():
                            if other == ten_dgd:
                                continue
                            if not isinstance(lst, list):
                                continue
                            for t in thon_sel:
                                if t in lst:
                                    dup_m.append(f"{t} → {other}")
                        if dup_m:
                            st.error(
                                "Trùng thôn/ấp với ĐGD khác: " + ", ".join(dup_m)
                            )
                        else:
                            try:
                                m = copy.deepcopy(db.doc_dgd_map())
                                _merge_alias_xa_keys_in_map(m, ten_pgd, chon_xa)
                                cur = m.setdefault(ten_pgd, {}).setdefault(
                                    chon_xa, {}
                                )
                                if tm != ten_dgd:
                                    del cur[ten_dgd]
                                cur[tm] = list(thon_sel)
                                db.luu_dgd_map(m, username)
                                db.ghi_audit(
                                    username,
                                    "sua_dgd_map",
                                    f"[{hn}] PGD={ten_pgd} xa={chon_xa} "
                                    f"ĐGD={ten_dgd!r} → {tm!r}",
                                )
                                st.cache_data.clear()
                                st.success("✅ Đã lưu.")
                                st.rerun()
                            except Exception as e:
                                db.ghi_audit(
                                    username, "sua_dgd_map_loi", f"[{hn}] {e}"
                                )
                                st.error(f"❌ {e}")
            with c_d:
                if st.button("🗑️ Xóa ĐGD", key=f"dgd_del_{sid}_{ten_pgd}_{chon_xa}"):
                    if dgd_dang_dung_trong_hstd(df_h, ten_pgd, chon_xa, ten_dgd):
                        st.error(
                            "ĐGD đang có hồ sơ trong HSTD, không thể xóa."
                        )
                    else:
                        try:
                            m = copy.deepcopy(db.doc_dgd_map())
                            _merge_alias_xa_keys_in_map(m, ten_pgd, chon_xa)
                            del m[ten_pgd][chon_xa][ten_dgd]
                            if not m[ten_pgd][chon_xa]:
                                del m[ten_pgd][chon_xa]
                            if not m[ten_pgd]:
                                del m[ten_pgd]
                            db.luu_dgd_map(m, username)
                            db.ghi_audit(
                                username,
                                "xoa_dgd_map",
                                f"[{hn}] PGD={ten_pgd} xa={chon_xa} ĐGD={ten_dgd!r}",
                            )
                            st.cache_data.clear()
                            st.success("✅ Đã xóa.")
                            st.rerun()
                        except Exception as e:
                            db.ghi_audit(
                                username, "xoa_dgd_map_loi", f"[{hn}] {e}"
                            )
                            st.error(f"❌ {e}")

    st.divider()
    st.markdown("**➕ Thêm ĐGD mới**")
    st_ten = st.text_input("Tên điểm GD", key="dgd_add_ten", placeholder="Ví dụ: Điểm GD 1")
    st_thon = st.multiselect("Chọn thôn/ấp", pool, key="dgd_add_thon")
    if st.button("💾 Lưu ĐGD mới", type="primary", key="dgd_add_btn"):
        if not st_ten.strip():
            st.error("Vui lòng nhập tên điểm giao dịch.")
        elif not st_thon:
            st.error("Vui lòng chọn ít nhất 1 thôn/ấp.")
        elif st_ten.strip() in xa_dgd:
            st.error("Tên điểm giao dịch đã tồn tại.")
        else:
            dup_a: list[str] = []
            for _dgd, lst in xa_dgd.items():
                if not isinstance(lst, list):
                    continue
                for t in st_thon:
                    if t in lst:
                        dup_a.append(f"{t} ({_dgd})")
            if dup_a:
                st.error(
                    "❌ Thôn/ấp đã gán cho ĐGD khác: " + ", ".join(dup_a)
                )
            else:
                try:
                    m = copy.deepcopy(db.doc_dgd_map())
                    _merge_alias_xa_keys_in_map(m, ten_pgd, chon_xa)
                    cur = m.setdefault(ten_pgd, {}).setdefault(chon_xa, {})
                    cur[st_ten.strip()] = list(st_thon)
                    db.luu_dgd_map(m, username)
                    db.ghi_audit(
                        username,
                        "them_dgd_map",
                        f"[{hn}] PGD={ten_pgd} xa={chon_xa} ĐGD={st_ten.strip()!r}",
                    )
                    st.cache_data.clear()
                    st.success("✅ Đã thêm ĐGD.")
                    st.rerun()
                except Exception as e:
                    db.ghi_audit(username, "them_dgd_map_loi", f"[{hn}] {e}")
                    st.error(f"❌ {e}")
