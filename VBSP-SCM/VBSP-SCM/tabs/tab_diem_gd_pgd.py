"""Tab 📍 Điểm GD của tôi — CBTD cấu hình dgd_map chỉ trong phạm vi PGD đăng nhập."""
from __future__ import annotations

import copy
import re
import socket
from typing import TYPE_CHECKING, Any

import pandas as pd
import streamlit as st

from config import (
    COT_TEN_PGD,
    COT_TEN_XA,
    PGD_XA_MAP,
)

import db
from data.dgd_helpers import (
    dem_thong_ke,
    dgd_dang_dung_trong_hstd,
    parse_excel_import,
    pool_thon_cho_xa,
    tao_file_mau_dgd,
    trang_thai_pgd_vs_map,
)
from data.pgd import pgd_slug
from utils import fmt_so, hien_thi_dataframe_phan_trang, pick_hstd_column

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def _render_import_pgd(
    pgd_user: str,
    username: str,
    hn: str,
    df_hstd_pgd: pd.DataFrame,
) -> None:
    """Giống tab KH-NV Import, chỉ cho một PGD; merge chỉ ghi đè nhánh dgd_map[pgd_user]."""
    st.markdown(f"**PGD:** {pgd_user}")
    ds_xa_cfg = list(PGD_XA_MAP.get(pgd_user, []) or [])
    dgd_map_cur = db.doc_dgd_map()
    buf_mau = tao_file_mau_dgd(pgd_user, dgd_map_cur)
    st.download_button(
        "📤 Tải file mẫu Excel (2 sheet: Nhập liệu + Danh mục thôn)",
        data=buf_mau,
        file_name=f"mau_dgd_{pgd_slug(pgd_user)}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dgd_pgd_op_imp_dl_mau",
        use_container_width=True,
    )
    up = st.file_uploader(
        "File Excel (cột A–D: STT | Xã | ĐGD | Ấp/KP)",
        type=["xlsx", "xls"],
        key="dgd_pgd_op_imp_up",
    )
    if up:
        try:
            parsed_xa = parse_excel_import(up.getvalue(), pgd_user)
        except Exception as e:
            st.error(f"❌ Không đọc được file: {e}")
            db.ghi_audit(username, "cbtd_import_dgd_loi", f"[{hn}] {e}")
            parsed_xa = {}

        if parsed_xa:
            # ── Validate xã trong file có khớp PGD chọn không ──
            ds_xa_cfg_set = {str(x).strip().lower() for x in ds_xa_cfg}
            xa_ngoai_pham_vi = [
                x
                for x in parsed_xa.keys()
                if str(x).strip().lower() not in ds_xa_cfg_set
            ]

            if ds_xa_cfg_set and xa_ngoai_pham_vi:
                st.warning(
                    f"⚠️ File chứa **{len(xa_ngoai_pham_vi)}** xã không thuộc PGD "
                    f"**{pgd_user}** theo cấu hình:\n\n"
                    + ", ".join(f"*{x}*" for x in sorted(xa_ngoai_pham_vi)[:10])
                    + ("…" if len(xa_ngoai_pham_vi) > 10 else "")
                    + "\n\n**Bạn có thể đã chọn nhầm PGD hoặc upload nhầm file.**"
                )
                chap_nhan = st.checkbox(
                    "Tôi hiểu dữ liệu có thể sai PGD và vẫn muốn tiếp tục",
                    key="dgd_pgd_op_imp_chap_nhan_sai_xa",
                )
            else:
                chap_nhan = True  # không có xã lạ → cho phép Merge bình thường

            _n_pgd, n_xa, n_dgd, n_ap = dem_thong_ke(parsed_xa)
            st.markdown(
                f"**Preview:** **{pgd_user}** — {fmt_so(n_xa)} xã, "
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
                hien_thi_dataframe_phan_trang(
                    pd.DataFrame(rows), key="dgd_pgd_op_imp_preview", height=280
                )
            else:
                st.warning("Không có dòng dữ liệu hợp lệ sau khi parse.")

            if st.button(
                "Merge vào dgd_map hiện tại (chỉ PGD của tôi)",
                type="primary",
                key="dgd_pgd_op_merge",
                disabled=not chap_nhan,
            ):
                try:
                    m = copy.deepcopy(db.doc_dgd_map())
                    m[pgd_user] = parsed_xa
                    db.luu_dgd_map(m, username)
                    db.ghi_audit(
                        username,
                        "cbtd_import_dgd_merge",
                        f"[{hn}] PGD={pgd_user} — "
                        f"{n_xa} xã, {n_dgd} ĐGD, {n_ap} ấp",
                    )
                    st.cache_data.clear()
                    st.success("✅ Đã merge cấu hình ĐGD cho PGD của bạn.")
                    st.rerun()
                except Exception as e:
                    db.ghi_audit(username, "cbtd_import_dgd_loi", f"[{hn}] {e}")
                    st.error(f"❌ Lỗi: {e}")
        else:
            st.info("Không có dữ liệu hợp lệ để preview/lưu.")
    else:
        st.info("Chọn file Excel để xem preview và lưu.")

    st.divider()
    st.markdown("### ➕ Thêm mới Điểm giao dịch")

    dgd_map_imp: dict[str, Any] = copy.deepcopy(db.doc_kv("dgd_map") or {})

    ds_xa_imp = [str(x).strip() for x in ds_xa_cfg]
    if not ds_xa_imp:
        st.warning(
            "PGD chưa có xã/phường trong PGD_XA_MAP — không thể thêm ĐGD thủ công."
        )
        return

    chon_xa_imp = st.selectbox(
        "Chọn Xã/Phường",
        options=ds_xa_imp,
        key="dgd_pgd_op_imp_chon_xa",
    )

    st.text_input(
        "Tên Điểm giao dịch",
        key="dgd_pgd_op_imp_ten_dgd",
        placeholder="Ví dụ: Điểm GD 1",
    )
    ten_dgd_typed = str(
        st.session_state.get("dgd_pgd_op_imp_ten_dgd", "")
    ).strip()

    pool_imp = pool_thon_cho_xa(
        pd.DataFrame(),
        pgd_user,
        chon_xa_imp,
        dgd_map_imp,
    )

    xa_hien_co = dgd_map_imp.get(pgd_user, {}).get(chon_xa_imp, {})
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
                if st.button(
                    "🗑️",
                    key=f"dgd_pgd_op_imp_xoa_{slug_x}",
                    help="Xóa ĐGD",
                ):
                    try:
                        del dgd_map_imp[pgd_user][chon_xa_imp][dgd_name]
                        if not dgd_map_imp[pgd_user][chon_xa_imp]:
                            del dgd_map_imp[pgd_user][chon_xa_imp]
                        if not dgd_map_imp[pgd_user]:
                            del dgd_map_imp[pgd_user]
                        db.luu_dgd_map(dgd_map_imp, username)
                        db.ghi_audit(
                            username,
                            "cbtd_imp_xoa_dgd",
                            f"[{hn}] PGD={pgd_user} xã={chon_xa_imp} ĐGD={dgd_name}",
                        )
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        db.ghi_audit(username, "cbtd_imp_loi_dgd", f"[{hn}] xóa ĐGD: {e}")
                        st.error(f"❌ Lỗi xóa: {e}")

    chon_thon_imp = st.multiselect(
        "Chọn thôn/ấp phụ trách",
        options=pool_kha_dung,
        help="Chỉ hiển thị thôn chưa gán cho ĐGD khác trong cùng xã.",
        key="dgd_pgd_op_imp_chon_thon",
    )
    if not pool_imp:
        st.caption("⚠️ Chưa có danh sách thôn — kiểm tra lại file HSTD của PGD này.")

    if st.button("➕ Thêm Điểm giao dịch", key="dgd_pgd_op_imp_btn_them", type="primary"):
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
                    cur = m.setdefault(pgd_user, {}).setdefault(chon_xa_imp, {})
                    cur[ten_dgd_typed] = [str(t).strip() for t in chon_thon_imp]
                    db.luu_dgd_map(m, username)
                    db.ghi_audit(
                        username,
                        "cbtd_imp_them_dgd",
                        f"[{hn}] PGD={pgd_user} xa={chon_xa_imp} "
                        f"{ten_dgd_typed}: {chon_thon_imp}",
                    )
                    st.cache_data.clear()
                    st.success(
                        f"✅ Đã thêm ĐGD '{ten_dgd_typed}' "
                        f"với {len(chon_thon_imp)} thôn."
                    )
                    st.rerun()
                except Exception as e:
                    db.ghi_audit(username, "cbtd_imp_loi_dgd", f"[{hn}] thêm ĐGD: {e}")
                    st.error(f"❌ Lỗi lưu: {e}")


def _render_xem_sua_pgd(
    pgd_user: str,
    username: str,
    hn: str,
    df_h: pd.DataFrame,
) -> None:
    """Giống _render_xem_sua KH-NV, PGD cố định."""
    dgd_map = copy.deepcopy(db.doc_dgd_map())
    ten_pgd = pgd_user

    xa_from_map = (
        sorted(dgd_map.get(ten_pgd, {}).keys())
        if isinstance(dgd_map.get(ten_pgd), dict)
        else []
    )
    ds_xa_cfg = list(PGD_XA_MAP.get(ten_pgd, []))

    if xa_from_map:
        chon_xa = st.selectbox(
            "Chọn Xã/Phường", xa_from_map, key="dgd_pgd_op_edit_xa"
        )
    elif ds_xa_cfg:
        st.info(
            f"**{ten_pgd}** chưa có dữ liệu trong dgd_map — chọn xã để thêm ĐGD."
        )
        chon_xa = st.selectbox(
            "Chọn Xã/Phường", ds_xa_cfg, key="dgd_pgd_op_edit_xa_boot"
        )
    else:
        st.warning("PGD không có trong PGD_XA_MAP.")
        return

    pool = pool_thon_cho_xa(df_h, ten_pgd, chon_xa, dgd_map)
    xa_dgd = dgd_map.get(ten_pgd, {}).get(chon_xa, {})
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
                key=f"dgd_pgd_op_nm_{sid}_{ten_pgd}_{chon_xa}",
            )
            thon_sel = st.multiselect(
                "Thôn/ấp",
                options=pool,
                default=[t for t in ds_thon if t in pool],
                key=f"dgd_pgd_op_th_{sid}_{ten_pgd}_{chon_xa}",
            )
            c_s, c_d = st.columns(2)
            with c_s:
                if st.button(
                    "💾 Lưu thay đổi",
                    key=f"dgd_pgd_op_sv_{sid}_{ten_pgd}_{chon_xa}",
                ):
                    tm = ten_moi.strip()
                    if not tm:
                        st.error("Tên ĐGD không được để trống.")
                    elif dgd_dang_dung_trong_hstd(
                        df_h, ten_pgd, chon_xa, ten_dgd
                    ) and (tm != ten_dgd.strip()):
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
                                cur = m.setdefault(ten_pgd, {}).setdefault(
                                    chon_xa, {}
                                )
                                if tm != ten_dgd:
                                    del cur[ten_dgd]
                                cur[tm] = list(thon_sel)
                                db.luu_dgd_map(m, username)
                                db.ghi_audit(
                                    username,
                                    "cbtd_sua_dgd_map",
                                    f"[{hn}] PGD={ten_pgd} xa={chon_xa} "
                                    f"ĐGD={ten_dgd!r} → {tm!r}",
                                )
                                st.cache_data.clear()
                                st.success("✅ Đã lưu.")
                                st.rerun()
                            except Exception as e:
                                db.ghi_audit(
                                    username,
                                    "cbtd_sua_dgd_map_loi",
                                    f"[{hn}] {e}",
                                )
                                st.error(f"❌ {e}")
            with c_d:
                if st.button(
                    "🗑️ Xóa ĐGD",
                    key=f"dgd_pgd_op_del_{sid}_{ten_pgd}_{chon_xa}",
                ):
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
                                "cbtd_xoa_dgd_map",
                                f"[{hn}] PGD={ten_pgd} xa={chon_xa} ĐGD={ten_dgd!r}",
                            )
                            st.cache_data.clear()
                            st.success("✅ Đã xóa.")
                            st.rerun()
                        except Exception as e:
                            db.ghi_audit(
                                username,
                                "cbtd_xoa_dgd_map_loi",
                                f"[{hn}] {e}",
                            )
                            st.error(f"❌ {e}")

    st.divider()
    st.markdown("**➕ Thêm ĐGD mới**")
    st_ten = st.text_input(
        "Tên điểm GD",
        key="dgd_pgd_op_add_ten",
        placeholder="Ví dụ: Điểm GD 1",
    )
    st_thon = st.multiselect("Chọn thôn/ấp", pool, key="dgd_pgd_op_add_thon")
    if st.button("💾 Lưu ĐGD mới", type="primary", key="dgd_pgd_op_add_btn"):
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
                        "cbtd_them_dgd_map",
                        f"[{hn}] PGD={ten_pgd} xa={chon_xa} ĐGD={st_ten.strip()!r}",
                    )
                    st.cache_data.clear()
                    st.success("✅ Đã thêm ĐGD.")
                    st.rerun()
                except Exception as e:
                    db.ghi_audit(username, "cbtd_them_dgd_map_loi", f"[{hn}] {e}")
                    st.error(f"❌ {e}")


def _render_tong_quan_pgd(pgd_user: str) -> None:
    st.markdown("### 📋 Tổng quan PGD của tôi")
    st.caption("So sánh dgd_map với danh mục xã trong PGD_XA_MAP (chỉ đơn vị bạn).")
    dgd_map = db.doc_dgd_map()
    block = dgd_map.get(pgd_user, {})
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

    with tab:
        st.subheader("📍 Điểm GD của tôi")
        st.caption(
            "Cấu hình điểm giao dịch — Import Excel, xem & sửa theo xã (chỉ PGD của bạn)."
        )

        with st.expander("📖 Hướng dẫn sử dụng", expanded=False):
            st.markdown(
                """
**Import từ file**
- Bấm **Tải file mẫu Excel** để có file đúng định dạng (4 cột: STT | Xã | ĐGD | Ấp/KP).
- Upload file → kiểm tra Preview → bấm **Merge** (chỉ ghi đè PGD của bạn, không ảnh hưởng PGD khác).

**Xem & Sửa**
- Chọn Xã → mở expander từng ĐGD để đổi tên / thêm bớt thôn / xóa.
- Không thể xóa ĐGD đang có hồ sơ trong HSTD.

**Thôn/ấp không hiện trong danh sách?**
- Danh sách lấy từ HSTD của PGD. Cần upload HSTD trước rồi quay lại cấu hình.
"""
            )

        if role != "user":
            st.info("Tab này dành cho CBTD (role=user).")

        if not pgd_user:
            st.error("Không xác định được PGD của người dùng.")
            return

        if df is None or df.empty:
            st.warning("Chưa có dữ liệu HSTD của PGD. Vui lòng upload trước.")
            return

        col_xa = pick_hstd_column(df, COT_TEN_XA, "Tên xã", "Tên Xã")
        if col_xa is None:
            st.warning("Không tìm thấy cột 'Tên xã' trong dữ liệu.")
            return

        df_pgd = df
        col_pgd = pick_hstd_column(df_pgd, COT_TEN_PGD, "Tên PGD")
        if col_pgd:
            s_pgd = df_pgd[col_pgd].astype(str).str.strip()
            df_pgd = df_pgd[s_pgd == str(pgd_user).strip()].copy()
            if df_pgd.empty:
                st.warning(f"Không có dữ liệu HSTD thuộc PGD **{pgd_user}**.")
                return

        hn = _hostname()
        t_imp, t_edit, t_sum = st.tabs(
            ["📥 Import từ file", "🗺️ Xem & Sửa", "📋 Tổng quan"]
        )

        with t_imp:
            _render_import_pgd(pgd_user, username, hn, df_pgd)

        with t_edit:
            _render_xem_sua_pgd(pgd_user, username, hn, df_pgd)

        with t_sum:
            _render_tong_quan_pgd(pgd_user)
