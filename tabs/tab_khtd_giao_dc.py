"""
Tab Giao KHTD & Điều chỉnh KHTD — lũy kế đợt, Google Sheet, kv_store, duyệt tập trung.
"""
from __future__ import annotations

import socket
from datetime import datetime
import pandas as pd
import streamlit as st

import db
from config import CHUONG_TRINH_KHTD, DON_VI_CHI_NHANH, DS_PGD, GQVL_MA_KEY_GIAO, PGD_XA_MAP
from data.pgd import pgd_slug as _pgd_slug
from services import khtd_service
from services.khtd_service import LOAI_DIEU_CHINH, LOAI_GIAO
from utils import fmt_tien, hien_thi_dataframe_phan_trang, xuat_excel
from auth import la_phan_he_pgd, la_quan_ly_cn, normalize_role
from logger import get_logger
from tabs.base_tab import TabContext

logger = get_logger(__name__)

_SS = "khtd_gdc_"


def _hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


def _slug_to_ten(slug: str) -> str:
    if slug == "hoi_so":
        return DON_VI_CHI_NHANH
    for ten in DS_PGD:
        if _pgd_slug(ten) == slug:
            return ten
    return slug


def _ds_slug_label() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for s in khtd_service.ds_slug():
        out.append((_slug_to_ten(s), s))
    return out


def _doc_kv_dot(
    pgd_slug_s: str, nam: int | str, thang: str, dot: str
) -> dict | None:
    key = khtd_service.kv_key_dot(pgd_slug_s, nam, thang, dot)
    raw = db.doc_kv(key)
    return raw if isinstance(raw, dict) else None


def _badge_trang_thai(raw: dict | None) -> str:
    if not raw or not raw.get("du_lieu"):
        return "⬜ Chưa tải"
    tt = raw.get("trang_thai") or "cho_duyet"
    if tt == "cho_duyet":
        return "🔵 Chờ duyệt"
    if tt == "da_duyet":
        return "🟢 Đã duyệt"
    if tt == "tu_choi":
        return "🔴 Từ chối"
    return "🔵 Chờ duyệt"


def _chon_dot() -> tuple[int, str, str]:
    c1, c2, c3 = st.columns(3)
    with c1:
        nam = int(
            st.number_input(
                "Năm",
                min_value=2000,
                max_value=2100,
                value=int(st.session_state.get(_SS + "nam", 2026)),
                key=_SS + "nam",
            )
        )
    with c2:
        thang_opts = [f"{i:02d}" for i in range(1, 13)]
        default_th = str(st.session_state.get(_SS + "thang", "01")).zfill(2)
        idx = (
            thang_opts.index(default_th)
            if default_th in thang_opts
            else 0
        )
        thang = st.selectbox(
            "Tháng",
            thang_opts,
            index=idx,
            key=_SS + "thang",
        )
    with c3:
        dot = st.text_input(
            "Số đợt",
            value=st.session_state.get(_SS + "dot", "Dot1"),
            key=_SS + "dot",
            help="Ví dụ: Dot1, Dot2…",
        )
    return nam, thang, dot


def _bang_pivot_tom_tat(nam: int, thang: str, dot: str) -> pd.DataFrame:
    rows: list[dict] = []
    for _ten, slug in _ds_slug_label():
        raw = _doc_kv_dot(slug, nam, thang, dot)
        loai = raw.get("loai") if raw else None
        if loai == LOAI_GIAO:
            tong_tw = tong_dp = 0.0
            if raw and raw.get("du_lieu"):
                for r in raw["du_lieu"]:
                    if isinstance(r, dict):
                        tong_tw += float(r.get("kh_tw") or 0)
                        tong_dp += float(r.get("kh_dp") or 0)
            loai_txt = "📋 Giao"
        elif loai == LOAI_DIEU_CHINH:
            tong_tw = tong_dp = 0.0
            if raw and raw.get("du_lieu"):
                for r in raw["du_lieu"]:
                    if isinstance(r, dict):
                        tong_tw += float(r.get("dc_tw") or 0)
                        tong_dp += float(r.get("dc_dp") or 0)
            loai_txt = "📉 Điều chỉnh"
        else:
            tong_tw = tong_dp = 0.0
            loai_txt = "⬜ Chưa tải"

        rows.append(
            {
                "PGD": _slug_to_ten(slug),
                "Loại": loai_txt,
                "Tổng TW": tong_tw,
                "Tổng ĐP": tong_dp,
                "Trạng thái": _badge_trang_thai(raw),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    disp = df.copy()
    disp["Tổng TW"] = disp["Tổng TW"].map(fmt_tien)
    disp["Tổng ĐP"] = disp["Tổng ĐP"].map(fmt_tien)
    return disp


def _bang_chi_tiet_pgd(slug: str, nam: int, thang: str, dot: str) -> pd.DataFrame:
    raw = db.doc_kv(khtd_service.kv_key_dot(slug, nam, thang, dot))
    if not raw or not raw.get("du_lieu"):
        return pd.DataFrame(
            columns=[
                "Xã",
                "Chương trình",
                "Mã CT",
                "KH đã giao TW",
                "ĐC TW",
                "KH mới TW",
                "KH đã giao ĐP",
                "ĐC ĐP",
                "KH mới ĐP",
                "Lý do",
            ]
        )
    loai_dot = raw.get("loai")
    rows: list[dict] = []
    for r in raw["du_lieu"]:
        if not isinstance(r, dict):
            continue
        rows.append(
            {
                "Xã": r.get("xa", ""),
                "Chương trình": r.get("ten_ct", ""),
                "Mã CT": r.get("ma_key", ""),
                "KH đã giao TW": r.get("kh_tw", 0),
                "ĐC TW": r.get("dc_tw", 0),
                "KH mới TW": r.get("kh_moi_tw", 0),
                "KH đã giao ĐP": r.get("kh_dp", 0),
                "ĐC ĐP": r.get("dc_dp", 0),
                "KH mới ĐP": r.get("kh_moi_dp", 0),
                "Lý do": r.get("ly_do", ""),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    disp = df.copy()
    money_cols = [
        "KH đã giao TW",
        "ĐC TW",
        "KH mới TW",
        "KH đã giao ĐP",
        "ĐC ĐP",
        "KH mới ĐP",
    ]
    for c in money_cols:
        if c in disp.columns:
            disp[c] = disp[c].map(fmt_tien)
    if loai_dot == LOAI_GIAO:
        drop_c = ["ĐC TW", "ĐC ĐP", "Lý do"]
        disp = disp.drop(columns=[c for c in drop_c if c in disp.columns])
    return disp


def _tat_ca_da_nhap_giao(
    nam: int, thang: str, dot: str, slugs: list[str]
) -> bool:
    for s in slugs:
        raw = db.doc_kv(khtd_service.kv_key_dot(s, nam, thang, dot))
        if (
            not raw
            or raw.get("loai") != LOAI_GIAO
            or not raw.get("du_lieu")
        ):
            return False
    return True


def _section_a(
    username: str, nam: int, thang: str, dot: str, df_hstd: pd.DataFrame | None
) -> None:
    _ = df_hstd

    with st.expander(
        "📂 Upload file HSTD 31/12 (dùng cho đợt đầu năm)",
        expanded=False,
    ):
        st.caption(
            "Upload file HSTD xuất tại ngày 31/12 năm trước "
            "để làm căn cứ khởi tạo KH đầu năm."
        )
        f_up = st.file_uploader(
            "Chọn file HSTD 31/12",
            type=["xlsx", "xls"],
            key=_SS + "hstd_upload",
        )
        if f_up:
            try:
                df_31_12 = pd.read_excel(f_up)
                st.session_state["khtd_df_hstd_31_12"] = df_31_12
                st.success(
                    f"✅ Đã tải {len(df_31_12):,} dòng từ file HSTD 31/12"
                )
                db.ghi_audit(
                    username,
                    "upload_khtd_hstd_3112",
                    f"[{_hostname()}] session · {len(df_31_12)} dòng",
                )
            except Exception as e:
                logger.error("Không đọc được file HSTD 31/12: %s", e, exc_info=True)
                db.ghi_audit(
                    username,
                    "upload_khtd_hstd_3112_loi",
                    f"[{_hostname()}] {e}",
                )
                st.error(f"❌ Không đọc được file: {e}")

    with st.expander("🚀 Khởi tạo đợt đầu năm", expanded=False):
        df_31_12 = st.session_state.get("khtd_df_hstd_31_12")
        if df_31_12 is None:
            st.warning(
                "⚠️ Chưa upload file HSTD 31/12. "
                "Vui lòng upload ở mục trên trước."
            )
        else:
            st.info(
                f"Sẽ khởi tạo đợt giao đầu năm {nam} "
                f"cho 22 đơn vị dựa trên dư nợ 31/12/{nam - 1}."
            )
            if st.button(
                f"🚀 Khởi tạo đợt giao {nam}_01_Dot1",
                key=_SS + "btn_khoi_tao",
            ):
                with st.spinner("Đang khởi tạo…"):
                    ket_qua = khtd_service.tao_dot_giao_dau_nam(
                        nam, username, df_31_12
                    )
                rows = [
                    {
                        "Đơn vị": _slug_to_ten(s),
                        "Kết quả": (
                            "✅ ok"
                            if kq.thanh_cong
                            else f"❌ {kq.thong_bao[:100]}"
                        ),
                    }
                    for s, kq in ket_qua.items()
                ]
                hien_thi_dataframe_phan_trang(
                    pd.DataFrame(rows), key=_SS + "khoi_tao_result"
                )
                db.ghi_audit(
                    username,
                    "khoi_tao_dot_giao_dau_nam",
                    f"[{_hostname()}] nam={nam} · {len(ket_qua)} đơn vị",
                )

    loai_hien_tai = st.session_state.get(_SS + "loai", LOAI_DIEU_CHINH)
    if loai_hien_tai == LOAI_DIEU_CHINH:
        with st.expander("⬆️ Push KH lên GSheet", expanded=False):
            st.caption(
                "Điền KH kỳ trước vào cột F/I của GSheet "
                "trước khi PGD nhập điều chỉnh."
            )
            ds = _ds_slug_label()
            labels = [x[0] for x in ds]
            slugs = [x[1] for x in ds]
            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    "⬆️ Push tất cả 22 đơn vị",
                    key=_SS + "btn_push_all",
                ):
                    with st.spinner("Đang push…"):
                        for slug in slugs:
                            khtd_service.push_kh_len_sheet(
                                slug, nam, thang, dot, username
                            )
                    st.success("✅ Đã push KH lên GSheet cho tất cả.")
                    db.ghi_audit(
                        username,
                        "push_khtd_sheet_tat_ca",
                        f"[{_hostname()}] {nam}/{thang}/{dot}",
                    )
            with c2:
                idx = st.selectbox(
                    "Push riêng 1 đơn vị",
                    range(len(labels)),
                    format_func=lambda i: labels[i],
                    key=_SS + "sel_push_mot",
                )
                if st.button("⬆️ Push 1 đơn vị", key=_SS + "btn_push_mot"):
                    kq = khtd_service.push_kh_len_sheet(
                        slugs[idx], nam, thang, dot, username
                    )
                    kq.hien_thi()

        with st.expander("⬇️ Tải từ Google Sheet", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    "⬇️ Tải tất cả 22 đơn vị",
                    key=_SS + "btn_tai_all",
                ):
                    with st.spinner("Đang tải…"):
                        ket = khtd_service.tai_tat_ca(
                            nam, thang, dot, username
                        )
                    df_k = pd.DataFrame(
                        [
                            {
                                "PGD": _slug_to_ten(s),
                                "Trạng thái": (
                                    "✅ ok" if v == "ok" else "⚠️ Cần xem"
                                ),
                                "Ghi chú": v,
                            }
                            for s, v in ket.items()
                        ]
                    )
                    hien_thi_dataframe_phan_trang(
                        df_k, key=_SS + "tai_all_status"
                    )
            with c2:
                ds = _ds_slug_label()
                labels = [x[0] for x in ds]
                slugs = [x[1] for x in ds]
                idx = st.selectbox(
                    "Tải riêng 1 đơn vị",
                    range(len(labels)),
                    format_func=lambda i: labels[i],
                    key=_SS + "sel_tai_mot",
                )
                if st.button("⬇️ Tải riêng", key=_SS + "btn_tai_mot"):
                    kq = khtd_service.tai_va_luu_pgd(
                        slugs[idx], nam, thang, dot, username
                    )
                    kq.hien_thi()


def _section_b_giao(
    nam: int, thang: str, dot: str, role: str, username: str
) -> None:
    st.markdown("#### 📋 Nhập Kế hoạch Giao")

    ds = _ds_slug_label()
    labels = [x[0] for x in ds]
    slugs = [x[1] for x in ds]
    j = st.selectbox(
        "Chọn đơn vị",
        range(len(labels)),
        format_func=lambda i: labels[i],
        key=_SS + "sel_giao_pgd",
    )
    slug_chon = slugs[j]
    ten_chon = labels[j]

    kh_truoc = khtd_service.lay_kh_dot_truoc(slug_chon, nam, thang, dot)
    ds_xa = PGD_XA_MAP.get(ten_chon, [])

    rows_nhap: list[dict] = []
    for xa in ds_xa:
        for ma_key, _ma_ct, ten_ct, nguon, _ in CHUONG_TRINH_KHTD:
            if ma_key.startswith("3_") and ma_key not in GQVL_MA_KEY_GIAO:
                continue
            kh_prev = kh_truoc.get(ma_key, {})
            rows_nhap.append(
                {
                    "Xã": xa,
                    "Chương trình": ten_ct,
                    "Mã CT": ma_key,
                    "Nguồn": nguon,
                    "KH đợt trước\n(triệu đồng)": (
                        round(kh_prev.get("kh_moi_tw", 0) / 1e6, 1)
                        if nguon == "TW"
                        else round(kh_prev.get("kh_moi_dp", 0) / 1e6, 1)
                    ),
                    "KH giao TW\n(triệu đồng)": 0.0,
                    "KH giao ĐP\n(triệu đồng)": 0.0,
                }
            )
    df_nhap = pd.DataFrame(rows_nhap)

    readonly = normalize_role(role) == "executive"
    if not readonly:
        df_edited = st.data_editor(
            df_nhap,
            column_config={
                "Xã": st.column_config.TextColumn(disabled=True),
                "Chương trình": st.column_config.TextColumn(disabled=True),
                "Mã CT": st.column_config.TextColumn(disabled=True),
                "Nguồn": st.column_config.TextColumn(disabled=True),
                "KH đợt trước\n(triệu đồng)": st.column_config.NumberColumn(
                    disabled=True, format="%.1f"
                ),
                "KH giao TW\n(triệu đồng)": st.column_config.NumberColumn(
                    format="%.1f",
                    help="Nhập KH giao nguồn TW (triệu đồng)",
                ),
                "KH giao ĐP\n(triệu đồng)": st.column_config.NumberColumn(
                    format="%.1f",
                    help="Nhập KH giao nguồn ĐP (triệu đồng)",
                ),
            },
            key=_SS + f"editor_giao_{slug_chon}",
            hide_index=True,
            height=400,
        )
    else:
        hien_thi_dataframe_phan_trang(
            df_nhap, key=_SS + "view_giao", height=400
        )
        st.caption("*(Chế độ xem — không thực hiện nhập.)*")
        return

    tong_giao_tw = df_edited["KH giao TW\n(triệu đồng)"].sum()
    tong_giao_dp = df_edited["KH giao ĐP\n(triệu đồng)"].sum()
    c1, c2 = st.columns(2)
    c1.metric("Tổng KH giao TW\n(triệu đồng)", f"{tong_giao_tw:,.0f}")
    c2.metric("Tổng KH giao ĐP\n(triệu đồng)", f"{tong_giao_dp:,.0f}")

    if st.button(
        f"💾 Lưu KH giao — {ten_chon}",
        key=_SS + "btn_luu_giao",
        type="primary",
    ):
        du_lieu: list[dict] = []
        for _, row in df_edited.iterrows():
            du_lieu.append(
                {
                    "xa": row["Xã"],
                    "ma_key": row["Mã CT"],
                    "ten_ct": row["Chương trình"],
                    "nguon": row["Nguồn"],
                    "kh_tw": float(row["KH giao TW\n(triệu đồng)"]),
                    "dc_tw": 0.0,
                    "kh_moi_tw": float(row["KH giao TW\n(triệu đồng)"]),
                    "kh_dp": float(row["KH giao ĐP\n(triệu đồng)"]),
                    "dc_dp": 0.0,
                    "kh_moi_dp": float(row["KH giao ĐP\n(triệu đồng)"]),
                    "ly_do": "",
                }
            )
        kq = khtd_service.luu_dot(
            slug_chon,
            nam,
            thang,
            dot,
            LOAI_GIAO,
            du_lieu,
            username,
        )
        kq.hien_thi()
        if kq.thanh_cong:
            st.cache_data.clear()


def _section_c_tong_hop(
    nam: int,
    thang: str,
    dot: str,
    username: str,
    role: str,
    loai: str,
    readonly_exec: bool,
) -> None:
    st.markdown("#### 📊 Tổng hợp & Duyệt")

    hien_thi_dataframe_phan_trang(
        _bang_pivot_tom_tat(nam, thang, dot),
        key=_SS + "tom_tat",
        height=420,
    )

    ds = _ds_slug_label()
    labels = [x[0] for x in ds]
    slugs = [x[1] for x in ds]
    j = st.selectbox(
        "Chi tiết xã × chương trình",
        range(len(labels)),
        format_func=lambda i: labels[i],
        key=_SS + "sel_chi_tiet",
    )
    slug_chon = slugs[j]
    hien_thi_dataframe_phan_trang(
        _bang_chi_tiet_pgd(slug_chon, nam, thang, dot),
        key=_SS + "chi_tiet",
        height=360,
    )

    if loai == LOAI_DIEU_CHINH:
        if readonly_exec:
            cb = khtd_service.kiem_tra_can_bang(nam, thang, dot)
        else:
            if st.button(
                "⚖️ Kiểm tra cân bằng",
                key=_SS + "btn_can_bang",
            ):
                st.session_state[_SS + "can_bang"] = (
                    khtd_service.kiem_tra_can_bang(nam, thang, dot)
                )
            cb = st.session_state.get(_SS + "can_bang")

        if cb:
            rows_cb = []
            for ma_key, v in sorted(cb.items()):
                ok = v.get("can_bang", False)
                rows_cb.append(
                    {
                        "Chương trình": ma_key,
                        "Tổng ĐC_TW": fmt_tien(v.get("tong_dc_tw", 0)),
                        "Tổng ĐC_ĐP": fmt_tien(v.get("tong_dc_dp", 0)),
                        "Cân bằng": "✅" if ok else "❌",
                    }
                )
            hien_thi_dataframe_phan_trang(
                pd.DataFrame(rows_cb), key=_SS + "can_bang_ct"
            )
        all_can_bang = bool(cb) and all(
            v.get("can_bang") for v in cb.values()
        )
    else:
        all_can_bang = _tat_ca_da_nhap_giao(nam, thang, dot, slugs)
        if not all_can_bang:
            st.warning(
                "⚠️ Còn đơn vị chưa nhập đủ KH giao (hoặc chưa đúng loại Giao)."
            )

    if not readonly_exec and normalize_role(role) in ("admin_cn", "manager_cn"):
        y_all = st.text_input("Ý kiến duyệt tất cả", key=_SS + "y_kien_all")
        if st.button(
            "✅ Duyệt tất cả",
            key=_SS + "btn_duyet_all",
            disabled=not all_can_bang,
        ):
            for slug in slugs:
                raw = db.doc_kv(
                    khtd_service.kv_key_dot(slug, nam, thang, dot)
                )
                if raw and raw.get("trang_thai") == "cho_duyet":
                    khtd_service.duyet(
                        slug,
                        nam,
                        thang,
                        dot,
                        "da_duyet",
                        y_all,
                        username,
                    )
            st.cache_data.clear()
            st.session_state.pop(_SS + "can_bang", None)
            st.success("✅ Đã duyệt tất cả.")
            db.ghi_audit(
                username,
                "duyet_khtd_tat_ca",
                f"[{_hostname()}] {nam}/{thang}/{dot}",
            )

        st.markdown("**Duyệt / Từ chối từng đơn vị**")
        y_kien = st.text_area("Ý kiến", key=_SS + "y_kien_mot")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Duyệt", key=_SS + "btn_duyet_1"):
                khtd_service.duyet(
                    slug_chon,
                    nam,
                    thang,
                    dot,
                    "da_duyet",
                    y_kien,
                    username,
                )
                st.cache_data.clear()
                st.success("Đã duyệt.")
        with c2:
            if st.button("❌ Từ chối", key=_SS + "btn_tu_choi"):
                khtd_service.duyet(
                    slug_chon,
                    nam,
                    thang,
                    dot,
                    "tu_choi",
                    y_kien,
                    username,
                )
                st.cache_data.clear()
                st.warning("Đã từ chối.")
    else:
        st.caption("*(Chế độ xem — không thực hiện duyệt.)*")

    df_raw = khtd_service.tong_hop(nam, thang, dot)
    if not df_raw.empty:
        st.divider()
        df_x = df_raw.copy()
        df_x = df_x.rename(
            columns={
                "kh_tw": "KH đã giao TW",
                "dc_tw": "Tăng/Giảm TW",
                "kh_moi_tw": f"KH TH năm {nam} (TW)",
                "kh_dp": "KH đã giao ĐP",
                "dc_dp": "Tăng/Giảm ĐP",
                "kh_moi_dp": f"KH TH năm {nam} (ĐP)",
            }
        )
        for c in [
            "KH đã giao TW",
            "Tăng/Giảm TW",
            f"KH TH năm {nam} (TW)",
            "KH đã giao ĐP",
            "Tăng/Giảm ĐP",
            f"KH TH năm {nam} (ĐP)",
        ]:
            if c in df_x.columns:
                df_x[c] = df_x[c].map(fmt_tien)
        if st.button("📥 Tạo Excel tổng hợp", key=_SS + "btn_gen_xlsx"):
            try:
                st.session_state[_SS + "xls_bytes"] = xuat_excel(
                    {f"KHTD_{nam}_{thang}_{dot}": df_x}
                )
                st.session_state[_SS + "xls_fname"] = (
                    f"KHTD_{nam}_{thang}_{dot}_"
                    f"{datetime.now().strftime('%Y%m%d')}.xlsx"
                )
            except Exception as e:
                logger.error("tab_khtd_giao_dc xuat_excel: %s", e, exc_info=True)
                st.error(f"❌ Lỗi xuất Excel: {e}")
        if st.session_state.get(_SS + "xls_bytes"):
            st.download_button(
                "📥 Tải Excel tổng hợp",
                data=st.session_state[_SS + "xls_bytes"],
                file_name=st.session_state.get(_SS + "xls_fname", "KHTD.xlsx"),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                key=_SS + "dl_xlsx",
            )


def _section_d_user(
    pgd_user: str | None, nam: int, thang: str, dot: str
) -> None:
    st.markdown("#### 📍 Trạng thái PGD của tôi")
    if not pgd_user:
        st.warning("Không xác định được PGD. Liên hệ Admin.")
        return
    slug = _pgd_slug(pgd_user)
    raw = db.doc_kv(khtd_service.kv_key_dot(slug, nam, thang, dot))
    loai = raw.get("loai", "") if raw else ""
    st.markdown(f"**Đơn vị:** {pgd_user}")
    st.markdown(
        "**Loại đợt:** "
        f"{'📋 Giao' if loai == LOAI_GIAO else '📉 Điều chỉnh'}"
    )
    st.markdown(f"**Trạng thái:** {_badge_trang_thai(raw)}")
    if raw and raw.get("trang_thai") == "tu_choi":
        st.error(
            f"Ý kiến từ chối: {raw.get('y_kien_duyet', '—')} "
            f"— {raw.get('nguoi_duyet', '')} "
            f"· {raw.get('thoi_gian_duyet', '')}"
        )
    hien_thi_dataframe_phan_trang(
        _bang_chi_tiet_pgd(slug, nam, thang, dot),
        key=_SS + "chi_tiet_user",
        height=400,
    )


def render(tab=None, **kwargs) -> None:
    username = st.session_state.get("username", "unknown")
    role = kwargs.get("role", "user")
    pgd_user = kwargs.get("pgd_user")
    df_hstd = kwargs.get("df_full")

    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.subheader("📋 Giao & Điều chỉnh KHTD")
        st.caption(
            "Lưu theo đợt · Lũy kế giữa các đợt · Duyệt tập trung"
        )

        with st.expander("📖 Hướng dẫn sử dụng", expanded=False):
            st.markdown(
                """
**Quy trình:**
1. Admin upload file HSTD 31/12 → Khởi tạo đợt giao đầu năm
2. Các đợt tiếp theo:
   - Loại **Giao**: Admin/Manager nhập KH giao cho từng PGD
   - Loại **Điều chỉnh**: Admin push KH lên GSheet → PGD nhập +/-
3. Admin tải về → Kiểm tra → Duyệt hoặc Từ chối

---
**Lũy kế:**
- KH_giao đợt hiện tại = KH_mới của đợt liền trước
- Các đợt giao và điều chỉnh có thể xen kẽ tự do

---
### Quy tắc nhập GSheet (Điều chỉnh)
- ✅ Số **dương (+)** = tăng · Số **âm (-)** = giảm
- ✅ Đơn vị: **triệu đồng**
- ⚠️ ĐC ≠ 0 → **bắt buộc nhập Lý do**
- 🔒 Chỉ nhập cột **ĐC_TW (G)**, **ĐC_ĐP (J)**, **Lý do (L)**
- 🚫 Không thêm/xóa dòng · Không đổi tên tab GSheet

---

### Trạng thái đợt
| | Ý nghĩa |
|---|---|
| ⬜ Chưa tải | Chưa có dữ liệu |
| 🔵 Chờ duyệt | Đã nhập, chờ Admin xét |
| 🟢 Đã duyệt | Hoàn tất |
| 🔴 Từ chối | Cần sửa và tải lại |

---

### Phân quyền
| Vai trò | Quyền |
|---|---|
| **Admin** | Toàn quyền: khởi tạo, giao, tải GSheet, duyệt |
| **Manager** | Giao KH, xem tổng hợp, duyệt |
| **Executive** | Chỉ xem, không nhập |
| **User (PGD)** | Nhập ĐC vào GSheet, xem trạng thái PGD mình |
            """
            )

        nam, thang, dot = _chon_dot()

        if la_quan_ly_cn(role):
            loai_radio = st.radio(
                "Loại đợt",
                ["📋 Giao KHTD", "📉 Điều chỉnh KHTD"],
                horizontal=True,
                key=_SS + "loai_radio",
            )
            loai_val = (
                LOAI_GIAO if "Giao" in loai_radio else LOAI_DIEU_CHINH
            )
            st.session_state[_SS + "loai"] = loai_val
        else:
            loai_val = st.session_state.get(_SS + "loai", LOAI_DIEU_CHINH)

        if la_phan_he_pgd(role):
            _section_d_user(pgd_user, nam, thang, dot)
            return

        readonly_exec = normalize_role(role) == "executive"

        if normalize_role(role) in ("admin_cn", "admin"):
            st.divider()
            _section_a(username, nam, thang, dot, df_hstd)

        st.divider()

        if loai_val == LOAI_GIAO:
            _section_b_giao(nam, thang, dot, role, username)
            st.divider()

        _section_c_tong_hop(
            nam,
            thang,
            dot,
            username,
            role,
            loai_val,
            readonly_exec,
        )
