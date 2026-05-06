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
from data.dgd_helpers import (
    dem_thong_ke,
    dgd_dang_dung_trong_hstd,
    parse_excel_import,
    pool_thon_cho_xa,
    trang_thai_pgd_vs_map,
    _gop_thon_tu_bang,
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
                        m[ten_pgd] = parsed_xa
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
                        db.luu_dgd_map({ten_pgd: parsed_xa}, username)
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

    col_form, col_preview = st.columns([3, 2])

    with col_form:
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

    with col_preview:
        st.markdown("**📋 ĐGD hiện có tại xã này**")
        xa_hien_co_preview = dgd_map_imp.get(ten_pgd_imp, {}).get(chon_xa_imp, {})
        if not isinstance(xa_hien_co_preview, dict) or not xa_hien_co_preview:
            st.info("Chưa có ĐGD nào.")
        else:
            for dgd_name, thon_list in xa_hien_co_preview.items():
                tl = thon_list if isinstance(thon_list, list) else []
                so_thon = len([t for t in tl if str(t).strip()])
                ap_txt = (
                    ", ".join(str(x).strip() for x in tl if str(x).strip())
                    or "_(chưa gán thôn)_"
                )
                slug_x = re.sub(r"\W+", "_", str(dgd_name))[:80]

                with st.expander(f"📍 {dgd_name} · {so_thon} thôn/ấp"):
                    st.caption(ap_txt)
                    st.divider()

                    xn_imp_key = f"imp_xoa_xn_{slug_x}"
                    btn_imp_key = f"imp_xoa_dgd_{slug_x}"

                    st.warning(
                        f"Xóa **{dgd_name}** sẽ giải phóng "
                        f"{so_thon} thôn/ấp. Không thể hoàn tác."
                    )
                    xac_nhan_imp = st.checkbox(
                        "Tôi xác nhận muốn xóa", key=xn_imp_key
                    )
                    if st.button(
                        "🗑️ Xóa ĐGD này",
                        key=btn_imp_key,
                        disabled=not xac_nhan_imp,
                        use_container_width=True,
                    ):
                        try:
                            m = copy.deepcopy(db.doc_dgd_map())
                            del m[ten_pgd_imp][chon_xa_imp][dgd_name]
                            if not m[ten_pgd_imp][chon_xa_imp]:
                                del m[ten_pgd_imp][chon_xa_imp]
                            if not m[ten_pgd_imp]:
                                del m[ten_pgd_imp]
                            db.luu_dgd_map(m, username)
                            db.ghi_audit(
                                username,
                                "imp_xoa_dgd",
                                f"[{hn}] PGD={ten_pgd_imp} xã={chon_xa_imp} "
                                f"ĐGD={dgd_name} ({so_thon} thôn)",
                            )
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            db.ghi_audit(
                                username, "imp_loi_dgd", f"[{hn}] xóa ĐGD: {e}"
                            )
                            st.error(f"❌ Lỗi xóa: {e}")
            # Tổng kết
            tong_thon_da_gan = sum(
                len([t for t in tl if str(t).strip()])
                for tl in xa_hien_co_preview.values()
                if isinstance(tl, list)
            )
            st.metric("Đã phân bổ", f"{tong_thon_da_gan} thôn/ấp")


def _render_tong_quan(df_h: pd.DataFrame, username: str, hn: str) -> None:
    st.markdown("### 📋 Tổng quan")
    st.caption("So sánh dgd_map với danh mục xã trong config.PGD_XA_MAP.")
    dgd_map = db.doc_dgd_map()
    rows: list[dict[str, Any]] = []
    for ten_pgd in sorted(PGD_XA_MAP.keys()):
        block = dgd_map.get(ten_pgd, {})
        if not isinstance(block, dict):
            block = {}
        # Gộp dữ liệu theo tên xã chuẩn hóa để tránh đếm trùng
        from collections import defaultdict
        xa_grouped: dict[str, dict] = defaultdict(dict)  # {ten_xa_norm: {ten_dgd: [thon_list]}}

        for ten_xa_raw, xa_d in block.items():
            if not isinstance(xa_d, dict):
                continue
            ten_xa_norm = _normalize_xa_name(ten_xa_raw)
            # Gộp ĐGD và thôn vào cùng 1 xã chuẩn hóa
            for ten_dgd, thon_list in xa_d.items():
                if ten_dgd not in xa_grouped[ten_xa_norm]:
                    xa_grouped[ten_xa_norm][ten_dgd] = []
                if isinstance(thon_list, list):
                    xa_grouped[ten_xa_norm][ten_dgd].extend(thon_list)

        so_xa = len(xa_grouped)
        so_dgd = sum(len(dgd_dict) for dgd_dict in xa_grouped.values())
        so_ap = sum(
            len([t for t in thon_list if str(t).strip()])
            for dgd_dict in xa_grouped.values()
            for thon_list in dgd_dict.values()
        )
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

    st.divider()

    # BÁO CÁO 1: Thống kê ĐGD theo Xã/Phường
    st.markdown("### 📊 Thống kê ĐGD theo Xã/Phường")

    # Gộp dữ liệu theo tên xã chuẩn hóa để tránh trùng lặp ("Trảng Dài" vs "Phường Trảng Dài")
    from collections import defaultdict
    bc1_grouped: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "so_dgd": 0, "tong_thon": 0, "chi_tiet_parts": []
    })

    for ten_pgd, block in dgd_map.items():
        if not isinstance(block, dict):
            continue
        for ten_xa_raw, xa_dct in block.items():
            if not isinstance(xa_dct, dict):
                continue
            ten_xa_norm = _normalize_xa_name(ten_xa_raw)
            key = (ten_pgd, ten_xa_norm)

            so_dgd_xa = len(xa_dct)
            tong_thon_xa = sum(
                len([t for t in lst if str(t).strip()])
                for lst in xa_dct.values()
                if isinstance(lst, list)
            )
            chi_tiet_xa = "; ".join(
                f"{dgd} ({len([t for t in lst if str(t).strip()])} thôn)"
                for dgd, lst in xa_dct.items()
                if isinstance(lst, list)
            )

            bc1_grouped[key]["so_dgd"] += so_dgd_xa
            bc1_grouped[key]["tong_thon"] += tong_thon_xa
            bc1_grouped[key]["chi_tiet_parts"].append(chi_tiet_xa)

    rows_bc1: list[dict[str, Any]] = []
    for (ten_pgd, ten_xa_norm), data in bc1_grouped.items():
        rows_bc1.append({
            "PGD": ten_pgd,
            "Xã/Phường": ten_xa_norm.title(),  # Hiển thị tên chuẩn hóa
            "Số ĐGD": data["so_dgd"],
            "Tổng thôn/ấp": data["tong_thon"],
            "Chi tiết": "; ".join(data["chi_tiet_parts"]),
        })

    if rows_bc1:
        df_bc1 = pd.DataFrame(rows_bc1).sort_values(["PGD", "Xã/Phường"])

        ds_pgd_co = ["Tất cả"] + sorted(df_bc1["PGD"].unique().tolist())
        loc_pgd = st.selectbox("Lọc theo PGD", ds_pgd_co, key="bc1_loc_pgd")
        if loc_pgd != "Tất cả":
            df_bc1 = df_bc1[df_bc1["PGD"] == loc_pgd]

        hien_thi_dataframe_phan_trang(df_bc1, key="dgd_bc1_tbl", height=350)

        c1, c2, c3 = st.columns(3)
        c1.metric("Số xã đã cấu hình", fmt_so(len(df_bc1)))
        c2.metric("Tổng ĐGD", fmt_so(df_bc1["Số ĐGD"].sum()))
        c3.metric("Tổng thôn/ấp đã gắn", fmt_so(df_bc1["Tổng thôn/ấp"].sum()))
    else:
        st.info("Chưa có dữ liệu dgd_map.")

    st.divider()

    # BÁO CÁO 2: Thôn/ấp chưa gắn Điểm Giao Dịch
    st.markdown("### 🔍 Thôn/ấp chưa gắn Điểm Giao Dịch")
    st.caption("Lấy từ HSTD — so sánh với dgd_map để tìm thôn chưa được phân bổ.")

    @st.cache_data(ttl=300, show_spinner=False)
    def _load_hstd_pgd_cached(ten_pgd: str) -> pd.DataFrame:
        """Cache load file HSTD từng PGD để không đọc lại nhiều lần."""
        from data.pgd import doc_hstd_pgd
        df = doc_hstd_pgd(ten_pgd)
        return df if df is not None else pd.DataFrame()

    def _pool_thon_nhanh(df_h: pd.DataFrame, ten_pgd: str, ten_xa: str, dgd_map: dict, df_pgd_cached: pd.DataFrame) -> set[str]:
        """Phiên bản nhanh của pool_thon_cho_xa với df_pgd đã preload."""
        pool: set[str] = set()
        # 1. Thôn từ dgd_map
        xa_map = (dgd_map or {}).get(ten_pgd, {}).get(ten_xa, {})
        if isinstance(xa_map, dict):
            for thon_list in xa_map.values():
                for t in thon_list or []:
                    s = str(t).strip()
                    if s and s.lower() != "nan":
                        pool.add(s)
        # 2. Từ df_h truyền vào
        if not df_h.empty:
            pool |= _gop_thon_tu_bang(df_h, ten_pgd, ten_xa)
        # 3. Từ df_pgd_cached (đã preload, không đọc file nữa)
        if not df_pgd_cached.empty:
            pool |= _gop_thon_tu_bang(df_pgd_cached, ten_pgd, ten_xa)
        return pool

    with st.spinner("Đang tải dữ liệu..."):
        # Preload tất cả file HSTD của các PGD (mỗi file chỉ đọc 1 lần)
        _pgd_data_cache: dict[str, pd.DataFrame] = {}
        for ten_pgd in ([DON_VI_CHI_NHANH] + DS_PGD):
            _pgd_data_cache[ten_pgd] = _load_hstd_pgd_cached(ten_pgd)

        rows_bc2: list[dict[str, Any]] = []
        for ten_pgd in ([DON_VI_CHI_NHANH] + DS_PGD):
            block = dgd_map.get(ten_pgd, {})
            ds_xa = PGD_XA_MAP.get(ten_pgd, [])
            df_pgd_cached = _pgd_data_cache.get(ten_pgd, pd.DataFrame())

            for ten_xa in ds_xa:
                tat_ca_thon = _pool_thon_nhanh(df_h, ten_pgd, ten_xa, dgd_map, df_pgd_cached)

                xa_dct = block.get(ten_xa, {}) if isinstance(block, dict) else {}
                da_gan: set[str] = set()
                if isinstance(xa_dct, dict):
                    for lst in xa_dct.values():
                        for t in (lst or []):
                            s = str(t).strip()
                            if s and s.lower() != "nan":
                                da_gan.add(s)

                chua_gan = sorted(tat_ca_thon - da_gan)
                for thon in chua_gan:
                    rows_bc2.append({
                        "PGD": ten_pgd,
                        "Xã/Phường": ten_xa,
                        "Thôn/ấp chưa gắn": thon,
                    })

    if rows_bc2:
        df_bc2 = pd.DataFrame(rows_bc2)

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            ds_pgd_f = ["Tất cả"] + sorted(df_bc2["PGD"].unique().tolist())
            loc_pgd2 = st.selectbox("Lọc PGD", ds_pgd_f, key="bc2_loc_pgd")
        with col_f2:
            if loc_pgd2 != "Tất cả":
                df_bc2 = df_bc2[df_bc2["PGD"] == loc_pgd2]
            ds_xa_f = ["Tất cả"] + sorted(df_bc2["Xã/Phường"].unique().tolist())
            loc_xa2 = st.selectbox("Lọc Xã/Phường", ds_xa_f, key="bc2_loc_xa")
            if loc_xa2 != "Tất cả":
                df_bc2 = df_bc2[df_bc2["Xã/Phường"] == loc_xa2]

        st.warning(f"⚠️ Có **{fmt_so(len(df_bc2))}** thôn/ấp chưa được gắn ĐGD")
        hien_thi_dataframe_phan_trang(df_bc2, key="dgd_bc2_tbl", height=350)
    else:
        st.success("✅ Tất cả thôn/ấp đã được gắn Điểm Giao Dịch.")


def _normalize_xa_name(xa_name: str) -> str:
    """Chuẩn hóa tên xã/phường bằng cách loại bỏ tiền tố 'Phường', 'Xã', 'Thị trấn'.

    Args:
        xa_name: Tên xã/phường gốc (vd: "Phường Trảng Dài", "Trảng Dài")

    Returns:
        Tên xã đã chuẩn hóa, lowercase để so sánh
    """
    if not xa_name:
        return ""
    name = str(xa_name).strip()
    # Loại bỏ các tiền tố phổ biến (case-insensitive)
    prefixes = ["phường", "phuong", "xã", "xa", "thị trấn", "thi tran"]
    name_lower = name.lower()
    for prefix in prefixes:
        if name_lower.startswith(prefix + " "):
            name = name[len(prefix) + 1 :].strip()
            break
    return name.lower()


def _match_xa_between_sources(
    xa_from_map: list[str], ds_xa_cfg: list[str]
) -> tuple[list[tuple[str, str]], list[str]]:
    """Match tên xã giữa dgd_map (tên ngắn) và PGD_XA_MAP (tên đầy đủ).

    Args:
        xa_from_map: Danh sách tên xã từ dgd_map (vd: ["Trảng Dài", "Biên Hòa"])
        ds_xa_cfg: Danh sách tên xã từ PGD_XA_MAP (vd: ["Phường Trảng Dài", "Phường Biên Hòa"])

    Returns:
        Tuple gồm:
        - matched: List các tuple (ten_ngan, ten_day_du) đã match được
        - unmatched_cfg: List tên xã trong cfg chưa có trong dgd_map
    """
    # Build map từ tên chuẩn hóa -> tên đầy đủ từ ds_xa_cfg
    cfg_normalized_map: dict[str, str] = {}
    for xa_cfg in ds_xa_cfg:
        norm = _normalize_xa_name(xa_cfg)
        if norm:
            cfg_normalized_map[norm] = xa_cfg

    matched: list[tuple[str, str]] = []
    seen_normalized: set[str] = set()

    for xa_map in xa_from_map:
        norm = _normalize_xa_name(xa_map)
        if norm and norm not in seen_normalized:
            seen_normalized.add(norm)
            # Tìm tên đầy đủ tương ứng trong cfg
            if norm in cfg_normalized_map:
                matched.append((xa_map, cfg_normalized_map[norm]))
            else:
                # Không tìm thấy trong cfg, giữ nguyên tên ngắn
                matched.append((xa_map, xa_map))

    # Tìm các xã trong cfg nhưng chưa có trong dgd_map
    unmatched_cfg: list[str] = []
    for xa_map in xa_from_map:
        seen_normalized.add(_normalize_xa_name(xa_map))

    for norm, xa_cfg in cfg_normalized_map.items():
        if norm not in seen_normalized:
            unmatched_cfg.append(xa_cfg)

    return matched, unmatched_cfg


def _render_xem_sua(df_h: pd.DataFrame, username: str, hn: str) -> None:
    dgd_map = copy.deepcopy(db.doc_dgd_map())
    ten_pgd = st.selectbox("Chọn PGD", [DON_VI_CHI_NHANH] + DS_PGD, key="dgd_edit_pgd")

    xa_from_map = (
        sorted(dgd_map.get(ten_pgd, {}).keys())
        if isinstance(dgd_map.get(ten_pgd), dict)
        else []
    )
    ds_xa_cfg = list(PGD_XA_MAP.get(ten_pgd, []))

    # Match tên xã giữa 2 nguồn để tránh dropdown trùng lặp
    matched_xa, unmatched_cfg = _match_xa_between_sources(xa_from_map, ds_xa_cfg)

    # Build dict để map tên hiển thị (đầy đủ) -> tên key trong dgd_map (ngắn)
    display_to_map_key: dict[str, str] = {}
    display_options: list[str] = []

    for ten_ngan, ten_day_du in matched_xa:
        display_to_map_key[ten_day_du] = ten_ngan
        display_options.append(ten_day_du)

    # Thêm các xã trong cfg nhưng chưa có trong dgd_map
    for xa_cfg in unmatched_cfg:
        if xa_cfg not in display_to_map_key:
            display_to_map_key[xa_cfg] = xa_cfg
            display_options.append(xa_cfg)

    if not display_options:
        st.warning("PGD không có trong PGD_XA_MAP.")
        return

    # Thông báo nếu PGD chưa có dữ liệu trong dgd_map
    if not xa_from_map:
        st.info(
            f"**{ten_pgd}** chưa có dữ liệu trong dgd_map — chọn xã để thêm ĐGD."
        )

    chon_xa_display = st.selectbox(
        "Chọn Xã/Phường", display_options, key="dgd_edit_xa"
    )

    # Lấy tên key trong dgd_map tương ứng với lựa chọn hiển thị
    chon_xa = display_to_map_key.get(chon_xa_display, chon_xa_display)

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
                so_thon_hien_co = len([t for t in ds_thon if str(t).strip()])

                if dgd_dang_dung_trong_hstd(df_h, ten_pgd, chon_xa, ten_dgd):
                    st.button(
                        "🗑️ Xóa ĐGD",
                        key=f"dgd_del_{sid}_{ten_pgd}_{chon_xa}",
                        disabled=True,
                        help="ĐGD đang có hồ sơ trong HSTD — cập nhật HSTD trước khi xóa.",
                    )
                    st.caption("⚠️ Đang có hồ sơ HSTD")
                else:
                    xn_key = f"dgd_del_xn_{sid}_{ten_pgd}_{chon_xa}"
                    btn_key = f"dgd_del_{sid}_{ten_pgd}_{chon_xa}"

                    st.warning(
                        f"Xóa **{ten_dgd}** sẽ giải phóng "
                        f"{so_thon_hien_co} thôn/ấp. Không thể hoàn tác."
                    )
                    xac_nhan = st.checkbox("Tôi xác nhận muốn xóa", key=xn_key)

                    if st.button(
                        "🗑️ Xóa ĐGD",
                        key=btn_key,
                        type="primary",
                        disabled=not xac_nhan,
                        use_container_width=True,
                    ):
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
                                f"[{hn}] PGD={ten_pgd} xa={chon_xa} "
                                f"ĐGD={ten_dgd!r} ({so_thon_hien_co} thôn)",
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
