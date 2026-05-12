"""Tab quản lý Điểm Giao Dịch (dgd_map) — Phân hệ ws_management."""
from __future__ import annotations

import copy
import re
import socket
from io import BytesIO
from typing import TYPE_CHECKING, Any

import pandas as pd
import streamlit as st

from config import (
    DON_VI_CHI_NHANH,
    DS_PGD,
    PGD_XA_MAP,
)

import db
from auth import la_phan_he_cn, normalize_role
from data.dgd_helpers import (
    dem_thong_ke,
    dgd_dang_dung_trong_hstd,
    parse_excel_import,
    pool_thon_cho_xa,
    trang_thai_pgd_vs_map,
)
from data.pgd import pgd_slug
from utils import fmt_so, hien_thi_dataframe_phan_trang

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


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
        return "unknown"


def _df_hstd(kwargs: dict[str, Any]) -> pd.DataFrame:
    df = kwargs.get("df_full")
    if df is None or df.empty:
        df = kwargs.get("df")
    if df is None:
        return pd.DataFrame()
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def render(tab: DeltaGenerator, **kwargs: Any) -> None:
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    df_h = _df_hstd(kwargs)
    hn = _hostname()

    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("📍 Điểm Giao Dịch (dgd_map)")
        st.caption(
            "Cấu hình ĐGD — thôn/ấp theo PGD/Xã. Import Excel hoặc sửa trực tiếp."
        )

        if normalize_role(role) == "executive":
            _render_tong_quan(df_h, username, hn)
            return

        t_imp, t_edit, t_sum = st.tabs(
            ["📥 Import từ file", "🗺️ Xem & Sửa", "📋 Tổng quan"]
        )

        with t_imp:
            if not la_phan_he_cn(role) or normalize_role(role) == "executive":
                st.warning("Bạn chỉ có quyền xem tổng quan (executive) hoặc không đủ quyền.")
            else:
                _render_import(role, username, hn)

        with t_edit:
            if not la_phan_he_cn(role) or normalize_role(role) == "executive":
                st.warning("Bạn không có quyền sửa.")
            else:
                _render_xem_sua(df_h, username, hn)

        with t_sum:
            _render_tong_quan(df_h, username, hn)


def _render_import(role: str, username: str, hn: str) -> None:
    ten_pgd = st.selectbox("Chọn PGD", [DON_VI_CHI_NHANH] + DS_PGD, key="dgd_imp_pgd")
    ds_xa = PGD_XA_MAP.get(ten_pgd, []) or []
    xa_vi_du = str(ds_xa[0]).strip() if ds_xa else ""
    df_mau = pd.DataFrame(
        [
            {"STT": 1, "Xã": xa_vi_du, "ĐGD": "Điểm GD 1", "Ấp/KP": ""},
            {"STT": 2, "Xã": xa_vi_du, "ĐGD": "Điểm GD 1", "Ấp/KP": ""},
            {"STT": 3, "Xã": xa_vi_du, "ĐGD": "Điểm GD 1", "Ấp/KP": ""},
        ]
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df_mau.to_excel(w, index=False, sheet_name="Mau")
    st.download_button(
        "📤 Tải file mẫu Excel",
        data=buf.getvalue(),
        file_name=f"mau_dgd_{pgd_slug(ten_pgd)}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dgd_imp_dl_mau",
        use_container_width=True,
    )
    up = st.file_uploader("File Excel (cột A–D: STT | Xã | ĐGD | Ấp/KP)", type=["xlsx", "xls"])
    if up:
        try:
            parsed_xa = parse_excel_import(up.getvalue(), ten_pgd)
        except Exception as e:
            st.error(f"❌ Không đọc được file: {e}")
            db.ghi_audit(username, "import_dgd_map_loi", f"[{hn}] {e}")
            parsed_xa = {}

        if parsed_xa:
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
                if st.button("Merge vào dgd_map hiện tại", type="primary", key="dgd_merge"):
                    try:
                        m = copy.deepcopy(db.doc_dgd_map())
                        m[_resolve_pgd_key(ten_pgd)] = parsed_xa
                        db.luu_dgd_map(m, username)
                        db.ghi_audit(
                            username,
                            "import_dgd_map_merge",
                            f"[{hn}] merge PGD={ten_pgd} — "
                            f"{n_xa} xã, {n_dgd} ĐGD, {n_ap} ấp",
                        )
                        st.cache_data.clear()
                        st.success("✅ Đã merge vào dgd_map.")
                        st.rerun()
                    except Exception as e:
                        db.ghi_audit(username, "import_dgd_map_loi", f"[{hn}] {e}")
                        st.error(f"❌ Lỗi: {e}")
            with c2:
                if role != "admin":
                    st.caption('Nút "Thay thế toàn bộ" chỉ dành cho admin.')
                elif st.button("Thay thế toàn bộ dgd_map", type="secondary", key="dgd_replace_all"):
                    try:
                        db.luu_dgd_map({_resolve_pgd_key(ten_pgd): parsed_xa}, username)
                        db.ghi_audit(
                            username,
                            "thay_the_dgd_map_toan_bo",
                            f"[{hn}] chỉ còn PGD={ten_pgd} (toàn bộ map bị ghi đè)",
                        )
                        st.cache_data.clear()
                        st.success(
                            "✅ Đã thay thế toàn bộ dgd_map — chỉ còn dữ liệu PGD vừa chọn "
                            "(các PGD khác đã bị xóa khỏi map)."
                        )
                        st.rerun()
                    except Exception as e:
                        db.ghi_audit(username, "import_dgd_map_loi", f"[{hn}] {e}")
                        st.error(f"❌ Lỗi: {e}")
        else:
            st.info("Không có dữ liệu hợp lệ để preview/lưu.")
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

    xa_hien_co = dgd_map_imp.get(_resolve_pgd_key(ten_pgd_imp), {}).get(chon_xa_imp, {})
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
                        del dgd_map_imp[_resolve_pgd_key(ten_pgd_imp)][chon_xa_imp][dgd_name]
                        if not dgd_map_imp[_resolve_pgd_key(ten_pgd_imp)][chon_xa_imp]:
                            del dgd_map_imp[_resolve_pgd_key(ten_pgd_imp)][chon_xa_imp]
                        if not dgd_map_imp[_resolve_pgd_key(ten_pgd_imp)]:
                            del dgd_map_imp[_resolve_pgd_key(ten_pgd_imp)]
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
                    cur = m.setdefault(_resolve_pgd_key(ten_pgd_imp), {}).setdefault(chon_xa_imp, {})
                    cur[ten_dgd_typed] = [str(t).strip() for t in chon_thon_imp]
                    db.luu_dgd_map(m, username)
                    db.ghi_audit(
                        username,
                        "them_dgd",
                        f"[{hn}] PGD={_resolve_pgd_key(ten_pgd_imp)} / {chon_xa_imp} / "
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
                for lst in xa_d.values():
                    if isinstance(lst, list):
                        so_ap += len(lst)
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


def _render_xem_sua(df_h: pd.DataFrame, username: str, hn: str) -> None:
    dgd_map = copy.deepcopy(db.doc_dgd_map())
    ten_pgd = st.selectbox("Chọn PGD", [DON_VI_CHI_NHANH] + DS_PGD, key="dgd_edit_pgd")

    xa_from_map = (
        sorted(dgd_map.get(_resolve_pgd_key(ten_pgd), {}).keys())
        if isinstance(dgd_map.get(_resolve_pgd_key(ten_pgd)), dict)
        else []
    )
    ds_xa_cfg = list(PGD_XA_MAP.get(ten_pgd, []))

    if xa_from_map:
        chon_xa = st.selectbox(
            "Chọn Xã/Phường", xa_from_map, key="dgd_edit_xa"
        )
    elif ds_xa_cfg:
        st.info(
            f"**{ten_pgd}** chưa có dữ liệu trong dgd_map — chọn xã để thêm ĐGD."
        )
        chon_xa = st.selectbox("Chọn Xã/Phường", ds_xa_cfg, key="dgd_edit_xa_boot")
    else:
        st.warning("PGD không có trong PGD_XA_MAP.")
        return

    pool = pool_thon_cho_xa(df_h, _resolve_pgd_key(ten_pgd), chon_xa, dgd_map)
    xa_dgd = dgd_map.get(_resolve_pgd_key(ten_pgd), {}).get(chon_xa, {})
    if not isinstance(xa_dgd, dict):
        xa_dgd = {}

    st.markdown(f"**ĐGD tại {chon_xa}**")

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
                    elif dgd_dang_dung_trong_hstd(df_h, _resolve_pgd_key(ten_pgd), chon_xa, ten_dgd) and (
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
                                cur = m.setdefault(_resolve_pgd_key(ten_pgd), {}).setdefault(
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
