"""Xây dựng Kế hoạch Tín dụng tương lai — 3 loại: 1 năm / 3 năm / 5 năm (2026–2030).

4 sub-tab: Biểu 01C | Biểu 02C | Thuyết minh | Tổng hợp CN
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from logger import get_logger

logger = get_logger(__name__)

import db
from auth import la_admin_cn, la_quan_ly_cn, la_phan_he_cn, normalize_role
from config import (
    CHUONG_TRINH_KHTD,
    DS_PGD,
    PGD_XA_MAP,
    THUYET_MINH_LABELS,
    TEN_CHI_NHANH_HIEN_THI,
)
from data.pgd import pgd_slug
from tabs.base_tab import TabContext
from services.khtd_import_service import (
    doc_bieu_01c_xd,
    doc_bieu_02c,
    doc_thuyet_minh,
    doc_thuyet_minh_tu_bieu_02c,
    doc_trang_thai_approval,
    duyet_ke_hoach_xd,
    is_khoa,
    luu_bieu_01c,
    luu_bieu_02c,
    luu_thuyet_minh,
    mo_lai_ke_hoach,
    nop_ke_hoach,
    tong_hop_bieu_01c_cn,
    tong_hop_bieu_02c_cn,
    trang_thai_approval_cn,
    trang_thai_xd_pgd,
)
from services.khtd_xuat_service import (
    xuat_excel_1pgd,
    xuat_excel_tong_hop_cn,
    xuat_word_bao_cao_pgd,
    xuat_word_tong_hop_cn,
)
from utils import fmt_ty

# Nguồn vốn huy động trong Biểu 02C
_NGUON_VON_LABELS: dict[str, str] = {
    "tien_gui_tc_cn":   "Tiền gửi tổ chức & cá nhân",
    "tien_gui_to_vien": "Tiền gửi tổ viên TK&VV",
    "utdt_dp":          "Nguồn vốn UTĐT địa phương",
    "quy_an_toan":      "Quỹ an toàn cho tổ viên",
}

_NAM_KE_HOACH = [2026, 2027, 2028, 2029, 2030]

_LOAI_MAP: dict[str, str] = {
    "📅 Kế hoạch 1 năm": "1n",
    "📆 Kế hoạch 3 năm": "3n",
    "📆 Kế hoạch 5 năm (2026–2030)": "5n",
}


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)
    role     = ctx.role_norm
    username = ctx.username or "unknown"
    pgd_user = ctx.pgd_user or kwargs.get("pgd_user")

    with ctx:
        st.subheader("🔭 Xây dựng Kế hoạch Tín dụng tương lai")

        # ── Chọn loại kế hoạch ────────────────────────────────────────────────
        loai_label = st.radio(
            "Loại kế hoạch",
            list(_LOAI_MAP.keys()),
            horizontal=True,
            key="xd_loai",
        )
        loai = _LOAI_MAP[loai_label]

        # ── Chọn năm + đơn vị ─────────────────────────────────────────────────
        h1, h2 = st.columns([2, 3])
        with h1:
            if loai == "5n":
                ds_nam = _NAM_KE_HOACH[:]
                st.caption("Giai đoạn: **2026–2030**")
            elif loai == "3n":
                nam_start = st.selectbox(
                    "Năm bắt đầu",
                    [2026, 2027, 2028],
                    key="xd_nam_3n",
                )
                ds_nam = [nam_start, nam_start + 1, nam_start + 2]
                st.caption(f"Giai đoạn: **{nam_start}–{nam_start + 2}**")
            else:
                nam_1n = st.selectbox(
                    "Năm kế hoạch",
                    _NAM_KE_HOACH,
                    key="xd_ky_chon",
                )
                ds_nam = [nam_1n]

        with h2:
            if la_phan_he_cn(role):
                pgd_chon = st.selectbox("Đơn vị PGD", DS_PGD, key="xd_pgd_chon")
            else:
                pgd_chon = pgd_user or (DS_PGD[0] if DS_PGD else "")
                st.info(f"Đơn vị: **{pgd_chon}**")

        if not pgd_chon:
            st.warning("⚠️ Chưa xác định đơn vị.")
            return

        # ── Kiểm tra lock — hiển thị banner nếu đã duyệt ─────────────────────
        _da_khoa = is_khoa(pgd_chon, ds_nam, loai)
        if _da_khoa:
            st.error(
                "🔒 Kế hoạch này **đã được CN phê duyệt** — không thể chỉnh sửa.\n\n"
                "Liên hệ admin_cn để mở lại nếu cần cập nhật.",
                icon="🔒",
            )

        # ── Sub-tabs ──────────────────────────────────────────────────────────
        if la_phan_he_cn(role):
            s1, s2, s3, s4, s5 = st.tabs(
                ["📥 Biểu 01C", "📊 Biểu 02C", "📝 Thuyết minh", "🏛️ Tổng hợp CN", "📈 So sánh thực hiện"]
            )
            _render_bieu_01c(s1, pgd_chon, ds_nam, loai, username, _da_khoa)
            _render_bieu_02c(s2, pgd_chon, ds_nam, loai, username, role, _da_khoa)
            _render_thuyet_minh(s3, pgd_chon, ds_nam, loai, username, role, _da_khoa)
            _render_tong_hop_cn(s4, ds_nam, loai, username, role)
            _render_so_sanh_thuc_hien(s5, ds_nam, loai)
        else:
            s1, s2, s3 = st.tabs(["📥 Biểu 01C", "📊 Biểu 02C", "📝 Thuyết minh"])
            _render_bieu_01c(s1, pgd_chon, ds_nam, loai, username, _da_khoa)
            _render_bieu_02c(s2, pgd_chon, ds_nam, loai, username, role, _da_khoa)
            _render_thuyet_minh(s3, pgd_chon, ds_nam, loai, username, role, _da_khoa)
            _render_approval_pgd(pgd_chon, ds_nam, loai, username, role)


# ── Sub-tab 1: Biểu 01C ───────────────────────────────────────────────────────

def _render_bieu_01c(
    tab,
    pgd_chon: str,
    ds_nam: list[int],
    loai: str,
    username: str,
    da_khoa: bool = False,
) -> None:
    with tab:
        st.markdown(f"#### Biểu 01C — Nhu cầu vay vốn ({pgd_chon})")

        with st.expander("📥 Import từ file KHNV_01C.XLSX (TTBC)", expanded=False):
            if da_khoa:
                st.warning("🔒 Kế hoạch đã duyệt — không thể import.")
            else:
                if len(ds_nam) > 1:
                    nam_upload = st.selectbox(
                        "Nhập cho năm",
                        ds_nam,
                        key=f"xd_01c_nam_up_{loai}_{pgd_slug(pgd_chon)}",
                    )
                else:
                    nam_upload = ds_nam[0]

                uploaded = st.file_uploader(
                    f"Chọn file KHNV_01C.XLSX (Năm {nam_upload})",
                    type=["xlsx", "xls"],
                    key=f"xd_01c_upload_{loai}_{pgd_slug(pgd_chon)}_{nam_upload}",
                )
                if uploaded is not None:
                    if st.button(
                        "⬆️ Import Biểu 01C",
                        key=f"xd_01c_btn_{loai}_{pgd_slug(pgd_chon)}_{nam_upload}",
                    ):
                        with st.spinner("Đang xử lý file..."):
                            ket_qua = luu_bieu_01c(
                                uploaded.read(), pgd_chon, nam_upload, username, loai
                            )
                        ket_qua.hien_thi()

        st.markdown("---")

        if len(ds_nam) == 1:
            _hien_thi_tong_hop_01c(pgd_chon, ds_nam[0], loai)
        else:
            y_tabs = st.tabs([f"Năm {n}" for n in ds_nam])
            for y_tab, nam in zip(y_tabs, ds_nam):
                with y_tab:
                    _hien_thi_tong_hop_01c(pgd_chon, nam, loai)


def _hien_thi_tong_hop_01c(pgd_chon: str, nam: int, loai: str) -> None:
    """Bảng tổng hợp nhu cầu vay theo xã."""
    ds_xa = PGD_XA_MAP.get(pgd_chon, [])
    if not ds_xa:
        st.info("Không có danh sách xã cho PGD này.")
        return

    all_ma_keys: set[str] = set()
    xa_data: dict[str, dict[str, float]] = {}
    for xa in ds_xa:
        raw = doc_bieu_01c_xd(pgd_chon, xa, nam, loai)
        if raw:
            tong_xa: dict[str, float] = {}
            for flat_key, val in raw.items():
                mk = flat_key.split("|", 1)[1] if "|" in flat_key else flat_key
                tong_xa[mk] = tong_xa.get(mk, 0.0) + val
                all_ma_keys.add(mk)
            xa_data[xa] = tong_xa

    if not xa_data:
        st.info(f"📭 Chưa có dữ liệu Biểu 01C năm {nam} ({loai}) cho {pgd_chon}.")
        return

    mk_tw = sorted(mk for mk in all_ma_keys if mk.endswith("_TW") or "_TW_" in mk)
    mk_dp = sorted(mk for mk in all_ma_keys if mk.endswith("_DP") or "_DP_" in mk)
    mk_order = mk_tw + mk_dp
    ten_ct = {mk: ten for mk, _, ten, _, _ in CHUONG_TRINH_KHTD}

    rows = []
    for xa, tong_xa in xa_data.items():
        row: dict = {"Xã/Phường": xa}
        for mk in mk_order:
            row[mk] = tong_xa.get(mk, 0.0)
        row["Tổng"] = sum(tong_xa.values())
        rows.append(row)

    total_row: dict = {"Xã/Phường": "TỔNG"}
    for mk in mk_order:
        total_row[mk] = sum(r[mk] for r in rows)
    total_row["Tổng"] = sum(r["Tổng"] for r in rows)
    rows.append(total_row)

    df = pd.DataFrame(rows)
    rename_map = {mk: ten_ct.get(mk, mk) for mk in mk_order}
    rename_map["Tổng"] = "Tổng (tr.đ)"
    df = df.rename(columns=rename_map)
    for col in df.columns[1:]:
        df[col] = df[col].apply(
            lambda v: fmt_ty(v * 1_000_000) if isinstance(v, (int, float)) else v
        )

    st.caption(f"Đơn vị: triệu đồng | {len(xa_data)} xã có dữ liệu")
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── Sub-tab 2: Biểu 02C ───────────────────────────────────────────────────────

def _render_bieu_02c(
    tab,
    pgd_chon: str,
    ds_nam: list[int],
    loai: str,
    username: str,
    role: str,
    da_khoa: bool = False,
) -> None:
    with tab:
        st.markdown(f"#### Biểu 02C — Kế hoạch tín dụng ({pgd_chon})")

        # Dùng da_khoa từ outer render (nhất quán, không đọc lại kv_store)
        locked = da_khoa
        if locked:
            st.info("🔒 Kế hoạch đã được Chi nhánh duyệt — chỉ xem.")

        with st.expander("📥 Import thuyết minh từ file KHNV_02C.XLSX", expanded=False):
            if locked:
                st.warning("🔒 Kế hoạch đã duyệt — không thể import.")
            else:
                if len(ds_nam) > 1:
                    nam_tm = st.selectbox(
                        "Lưu thuyết minh cho năm",
                        ds_nam,
                        key=f"xd_02c_tm_nam_{loai}_{pgd_slug(pgd_chon)}",
                    )
                else:
                    nam_tm = ds_nam[0]

                up2c = st.file_uploader(
                    "Chọn file KHNV_02C.XLSX",
                    type=["xlsx", "xls"],
                    key=f"xd_02c_upload_{loai}_{pgd_slug(pgd_chon)}",
                )
                if up2c is not None:
                    if st.button(
                        "🔄 Đọc & lưu thuyết minh",
                        key=f"xd_02c_btn_tm_{loai}_{pgd_slug(pgd_chon)}",
                    ):
                        with st.spinner("Đang đọc file..."):
                            try:
                                tm_data = doc_thuyet_minh_tu_bieu_02c(up2c.read())
                            except Exception as e:  # conv: skip
                                logger.error("Lỗi đọc Biểu 02C: %s", e, exc_info=True)
                                st.error(f"❌ Lỗi đọc file: {e}")
                                tm_data = {}
                        if tm_data:
                            luu_thuyet_minh(pgd_chon, nam_tm, tm_data, username, loai)
                            st.success(
                                f"✅ Đã lưu {len(tm_data)} chỉ tiêu thuyết minh "
                                f"(năm {nam_tm}, {loai})."
                            )
                        else:
                            st.warning("⚠️ Không tìm thấy dữ liệu thuyết minh trong file.")

        st.markdown("##### Dư nợ dự kiến theo chương trình (triệu đồng)")

        if len(ds_nam) == 1:
            _form_02c_nam(pgd_chon, ds_nam[0], loai, username, role, locked=locked)
        else:
            y_tabs = st.tabs([f"Năm {n}" for n in ds_nam])
            for y_tab, nam in zip(y_tabs, ds_nam):
                with y_tab:
                    _form_02c_nam(pgd_chon, nam, loai, username, role, locked=locked)


def _form_02c_nam(
    pgd_chon: str,
    nam: int,
    loai: str,
    username: str,
    role: str,
    locked: bool = False,
) -> None:
    """Form nhập dư nợ 02C cho một năm cụ thể."""
    du_lieu_cu = doc_bieu_02c(pgd_chon, nam, loai)
    du_no_cu = du_lieu_cu.get("du_no", {})
    nguon_von_cu = du_lieu_cu.get("nguon_von", {})
    co_quyen = normalize_role(role) not in ("executive",) and not locked
    slug = pgd_slug(pgd_chon)

    with st.form(f"xd_{loai}_02c_form_{slug}_{nam}"):
        st.markdown(f"**Năm {nam}**")

        st.markdown("**I. Nguồn vốn Trung ương**")
        du_no_nhap_tw: dict[str, float] = {}
        for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD:
            if nv != "TW":
                continue
            val_trieu = _to_trieu(du_no_cu.get(mk, 0.0))
            c1, c2 = st.columns([4, 2])
            with c1:
                st.markdown(f"<small>{ten}</small>", unsafe_allow_html=True)
            with c2:
                du_no_nhap_tw[mk] = st.number_input(
                    ten,
                    min_value=0.0,
                    step=100.0,
                    format="%.0f",
                    value=val_trieu,
                    key=f"xd_{loai}_02c_{slug}_{mk}_tw_{nam}",
                    label_visibility="collapsed",
                    disabled=not co_quyen,
                )

        st.markdown("**II. Nguồn vốn Địa phương**")
        du_no_nhap_dp: dict[str, float] = {}
        for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD:
            if nv != "DP":
                continue
            val_trieu = _to_trieu(du_no_cu.get(mk, 0.0))
            c1, c2 = st.columns([4, 2])
            with c1:
                st.markdown(f"<small>{ten}</small>", unsafe_allow_html=True)
            with c2:
                du_no_nhap_dp[mk] = st.number_input(
                    ten,
                    min_value=0.0,
                    step=100.0,
                    format="%.0f",
                    value=val_trieu,
                    key=f"xd_{loai}_02c_{slug}_{mk}_dp_{nam}",
                    label_visibility="collapsed",
                    disabled=not co_quyen,
                )

        st.markdown("---")
        st.markdown("**Nguồn vốn huy động (triệu đồng)**")
        nguon_von_nhap: dict[str, float] = {}
        for nv_key, nv_label in _NGUON_VON_LABELS.items():
            val_trieu = _to_trieu(nguon_von_cu.get(nv_key, 0.0))
            c1, c2 = st.columns([4, 2])
            with c1:
                st.markdown(f"<small>{nv_label}</small>", unsafe_allow_html=True)
            with c2:
                nguon_von_nhap[nv_key] = st.number_input(
                    nv_label,
                    min_value=0.0,
                    step=100.0,
                    format="%.0f",
                    value=val_trieu,
                    key=f"xd_{loai}_02c_nv_{slug}_{nv_key}_{nam}",
                    label_visibility="collapsed",
                    disabled=not co_quyen,
                )

        if co_quyen:
            submitted = st.form_submit_button(
                f"💾 Lưu Biểu 02C năm {nam}", type="primary"
            )
        else:
            st.form_submit_button(f"💾 Lưu Biểu 02C năm {nam}", disabled=True)
            submitted = False

    if submitted:
        du_no_vnd = {
            mk: v * 1_000_000
            for d in (du_no_nhap_tw, du_no_nhap_dp)
            for mk, v in d.items()
            if v > 0
        }
        nguon_von_vnd = {k: v * 1_000_000 for k, v in nguon_von_nhap.items() if v > 0}
        ok = luu_bieu_02c(
            pgd_chon, nam,
            {"du_no": du_no_vnd, "nguon_von": nguon_von_vnd},
            username, loai,
        )
        if ok:
            tong = sum(du_no_vnd.values())
            st.success(
                f"✅ Đã lưu Biểu 02C ({loai}) năm **{nam}** — "
                f"Tổng dư nợ: **{fmt_ty(tong)} triệu đồng**"
            )


# ── Sub-tab 3: Thuyết minh chỉ tiêu ──────────────────────────────────────────

def _render_thuyet_minh(
    tab,
    pgd_chon: str,
    ds_nam: list[int],
    loai: str,
    username: str,
    role: str,
    da_khoa: bool = False,
) -> None:
    with tab:
        st.markdown(f"#### Thuyết minh chỉ tiêu ({pgd_chon})")

        # Dùng da_khoa từ outer render thay vì đọc lại kv_store
        locked = da_khoa
        if locked:
            st.info("🔒 Kế hoạch đã được Chi nhánh duyệt — chỉ xem.")

        if len(ds_nam) == 1:
            _form_thuyet_minh_nam(pgd_chon, ds_nam[0], loai, username, role, locked=locked)
        else:
            y_tabs = st.tabs([f"Năm {n}" for n in ds_nam])
            for y_tab, nam in zip(y_tabs, ds_nam):
                with y_tab:
                    _form_thuyet_minh_nam(pgd_chon, nam, loai, username, role, locked=locked)


def _form_thuyet_minh_nam(
    pgd_chon: str,
    nam: int,
    loai: str,
    username: str,
    role: str,
    locked: bool = False,
) -> None:
    """Form nhập thuyết minh cho một năm cụ thể."""
    du_lieu_cu = doc_thuyet_minh(pgd_chon, nam, loai)
    co_quyen = normalize_role(role) not in ("executive",) and not locked
    slug = pgd_slug(pgd_chon)

    with st.form(f"xd_{loai}_tm_form_{slug}_{nam}"):
        st.markdown(f"**Năm {nam}**")
        nhap: dict[str, int] = {}
        cols = st.columns(2)
        for i, (key, label) in enumerate(THUYET_MINH_LABELS.items()):
            val_cu = int(du_lieu_cu.get(key, 0) or 0)
            with cols[i % 2]:
                nhap[key] = st.number_input(
                    label,
                    min_value=0,
                    step=1,
                    format="%d",
                    value=val_cu,
                    key=f"xd_{loai}_tm_{slug}_{key}_{nam}",
                    disabled=not co_quyen,
                )

        if co_quyen:
            submitted = st.form_submit_button(
                f"💾 Lưu thuyết minh năm {nam}", type="primary"
            )
        else:
            st.form_submit_button(f"💾 Lưu thuyết minh năm {nam}", disabled=True)
            submitted = False

    if submitted:
        ok = luu_thuyet_minh(pgd_chon, nam, {k: int(v) for k, v in nhap.items()}, username, loai)
        if ok:
            st.success(f"✅ Đã lưu thuyết minh ({loai}) năm **{nam}** cho {pgd_chon}.")


# ── Approval: PGD view ───────────────────────────────────────────────────────

def _render_approval_pgd(
    pgd_chon: str,
    ds_nam: list[int],
    loai: str,
    username: str,
    role: str,
) -> None:
    """Section phê duyệt kế hoạch — hiển thị dưới các sub-tab nhập liệu (PGD view)."""
    st.divider()
    st.markdown("#### 📋 Nộp & Theo dõi Phê duyệt")

    approval = doc_trang_thai_approval(pgd_chon, ds_nam, loai)
    tt = approval.get("trang_thai", "nhap_lieu")
    slug = pgd_slug(pgd_chon)
    giai_doan = str(ds_nam[0]) if len(ds_nam) == 1 else f"{ds_nam[0]}–{ds_nam[-1]}"

    # ── Badge trạng thái ──────────────────────────────────────────────────────
    _TT_LABEL = {
        "nhap_lieu": ("🖊️", "Đang nhập liệu", "info"),
        "da_nop":    ("⏳", "Đã nộp — Chờ Chi nhánh duyệt", "warning"),
        "da_duyet":  ("✅", "ĐÃ DUYỆT", "success"),
        "tu_choi":   ("❌", "Bị trả lại — Cần chỉnh sửa và nộp lại", "error"),
    }
    icon, label, badge_type = _TT_LABEL.get(tt, ("❓", tt, "info"))
    getattr(st, badge_type)(f"{icon} **{label}**")

    if tt == "da_duyet":
        ngay = (approval.get("ngay_duyet") or "")[:10]
        nguoi = approval.get("nguoi_duyet") or ""
        y_kien = approval.get("y_kien") or ""
        st.caption(f"Duyệt bởi: **{nguoi}** — Ngày: **{ngay}**")
        if y_kien:
            st.caption(f"Ý kiến: {y_kien}")
        # Export buttons (locked — read only)
        _render_export_buttons_pgd(pgd_chon, ds_nam, loai, slug)
        return

    if tt == "tu_choi":
        y_kien = approval.get("y_kien") or ""
        if y_kien:
            st.markdown(f"**Ý kiến Chi nhánh:** {y_kien}")
        nguoi_duyet = approval.get("nguoi_duyet") or ""
        if nguoi_duyet:
            st.caption(f"Trả lại bởi: {nguoi_duyet}")

    if tt == "da_nop":
        lan = approval.get("lan_nop", 1)
        ngay_nop = (approval.get("ngay_nop") or "")[:10]
        st.caption(f"Đã nộp lần {lan} — Ngày {ngay_nop}")
        _render_export_buttons_pgd(pgd_chon, ds_nam, loai, slug)
        return

    # ── Nút nộp (chỉ khi nhap_lieu hoặc tu_choi) ─────────────────────────────
    st.markdown("**Điều kiện nộp:** Phải có đầy đủ Biểu 01C, Biểu 02C và Thuyết minh cho tất cả các năm.")

    lan_nop = approval.get("lan_nop", 0)
    label_btn = f"📤 Nộp Kế hoạch ({giai_doan})" if lan_nop == 0 else f"🔄 Nộp lại Kế hoạch (lần {lan_nop + 1})"

    if st.button(label_btn, key=f"xd_nop_{slug}_{loai}_{ds_nam[0]}", type="primary"):
        ok = nop_ke_hoach(pgd_chon, ds_nam, loai, username)
        if ok:
            st.success("✅ Đã nộp kế hoạch thành công! Chi nhánh sẽ xem xét và phê duyệt.")
            st.rerun()
        else:
            st.error("❌ Chưa đủ dữ liệu để nộp. Hãy đảm bảo đã nhập đủ Biểu 01C, 02C và Thuyết minh.")

    _render_export_buttons_pgd(pgd_chon, ds_nam, loai, slug)


def _render_export_buttons_pgd(
    pgd_chon: str, ds_nam: list[int], loai: str, slug: str
) -> None:
    """Nút tải Excel + Word cho 1 PGD."""
    with st.expander("📥 Tải xuống", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            try:
                excel_bytes = xuat_excel_1pgd(pgd_chon, ds_nam, loai)
                st.download_button(
                    "📊 Tải Excel",
                    data=excel_bytes,
                    file_name=f"KHTD_{loai}_{slug}_{ds_nam[0]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"xd_dl_excel_{slug}_{loai}_{ds_nam[0]}",
                    use_container_width=True,
                )
            except Exception as e:
                logger.error("_render_export_buttons_pgd excel: %s", e, exc_info=True)
                st.caption(f"⚠️ Không xuất được Excel: {e}")
        with c2:
            try:
                word_bytes = xuat_word_bao_cao_pgd(pgd_chon, ds_nam, loai)
                st.download_button(
                    "📝 Tải Tờ trình Word",
                    data=word_bytes,
                    file_name=f"TT_KHTD_{loai}_{slug}_{ds_nam[0]}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"xd_dl_word_{slug}_{loai}_{ds_nam[0]}",
                    use_container_width=True,
                )
            except Exception as e:
                logger.error("_render_export_buttons_pgd word: %s", e, exc_info=True)
                st.caption(f"⚠️ Không xuất được Word: {e}")


# ── Sub-tab 4: Tổng hợp CN ────────────────────────────────────────────────────

def _render_tong_hop_cn(tab, ds_nam: list[int], loai: str, username: str = "", role: str = "") -> None:
    with tab:
        giai_doan = (
            str(ds_nam[0]) if len(ds_nam) == 1
            else f"{ds_nam[0]}–{ds_nam[-1]}"
        )
        st.markdown(f"#### Tổng hợp toàn Chi nhánh — Giai đoạn {giai_doan}")
        st.caption(TEN_CHI_NHANH_HIEN_THI)

        # ── Bảng trạng thái PGD ───────────────────────────────────────────
        st.markdown("##### Trạng thái nhập liệu")

        if len(ds_nam) == 1:
            _bang_trang_thai_1nam(ds_nam[0], loai)
        else:
            _bang_trang_thai_da_nam(ds_nam, loai)

        st.markdown("---")

        # ── Phê duyệt kế hoạch PGD ───────────────────────────────────────
        _render_approval_cn(ds_nam, loai, role)

        st.markdown("---")

        # ── Tổng hợp dư nợ ───────────────────────────────────────────────
        st.markdown("##### Tổng hợp dư nợ dự kiến toàn CN")

        if len(ds_nam) == 1:
            _bang_du_no_1nam(ds_nam[0], loai)
        else:
            _bang_du_no_da_nam(ds_nam, loai)

        st.markdown("---")

        # ── Xuất tổng hợp ────────────────────────────────────────────────
        with st.expander("📥 Xuất báo cáo tổng hợp CN", expanded=False):
            c1, c2 = st.columns(2)
            giai_doan_str = str(ds_nam[0]) if len(ds_nam) == 1 else f"{ds_nam[0]}-{ds_nam[-1]}"
            with c1:
                try:
                    excel_bytes = xuat_excel_tong_hop_cn(ds_nam, loai)
                    st.download_button(
                        "📊 Tải Excel tổng hợp",
                        data=excel_bytes,
                        file_name=f"KHTD_TH_CN_{loai}_{giai_doan_str}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"xd_cn_dl_excel_{loai}_{ds_nam[0]}",
                        use_container_width=True,
                    )
                except Exception as e:
                    logger.error("_render_tong_hop_cn excel: %s", e, exc_info=True)
                    st.caption(f"⚠️ {e}")
            with c2:
                try:
                    word_bytes = xuat_word_tong_hop_cn(ds_nam, loai)
                    st.download_button(
                        "📝 Tải Word tổng hợp",
                        data=word_bytes,
                        file_name=f"KHTD_TH_CN_{loai}_{giai_doan_str}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"xd_cn_dl_word_{loai}_{ds_nam[0]}",
                        use_container_width=True,
                    )
                except Exception as e:
                    logger.error("_render_tong_hop_cn word: %s", e, exc_info=True)
                    st.caption(f"⚠️ {e}")


def _render_approval_cn(ds_nam: list[int], loai: str, role: str = "") -> None:
    """Panel phê duyệt tập trung — dành cho admin_cn / manager_cn trong Tổng hợp CN."""
    st.markdown("##### ✅ Phê duyệt Kế hoạch PGD")

    co_quyen_duyet = la_admin_cn(role) or la_quan_ly_cn(role)

    approval_map = trang_thai_approval_cn(ds_nam, loai)
    da_nop = [(pgd, ap) for pgd, ap in approval_map.items() if ap.get("trang_thai") == "da_nop"]
    da_duyet = sum(1 for ap in approval_map.values() if ap.get("trang_thai") == "da_duyet")
    tu_choi  = sum(1 for ap in approval_map.values() if ap.get("trang_thai") == "tu_choi")

    c1, c2, c3 = st.columns(3)
    c1.metric("Chờ duyệt", len(da_nop))
    c2.metric("Đã duyệt", da_duyet)
    c3.metric("Bị trả lại", tu_choi)

    if not da_nop:
        st.info("📭 Không có PGD nào đang chờ duyệt.")
    else:
        st.markdown(f"**{len(da_nop)} PGD đang chờ duyệt:**")
        if not co_quyen_duyet:
            st.info("ℹ️ Chỉ Trưởng/Phó phòng KH-NV mới có quyền phê duyệt kế hoạch.")

        username_duyetvien = st.session_state.get("username", "unknown")

        for pgd_ten, ap in da_nop:
            slug = pgd_slug(pgd_ten)
            lan_nop = ap.get("lan_nop", 1)
            ngay_nop = (ap.get("ngay_nop") or "")[:10]
            nguoi_nop = ap.get("nguoi_nop") or ""

            with st.expander(f"📋 {pgd_ten} — Nộp lần {lan_nop} ({ngay_nop})", expanded=False):
                st.caption(f"Người nộp: {nguoi_nop}")

                y_kien = st.text_area(
                    "Ý kiến (tùy chọn)",
                    key=f"xd_yk_{slug}_{loai}_{ds_nam[0]}",
                    placeholder="Nhập ý kiến hoặc yêu cầu chỉnh sửa...",
                    height=80,
                )
                col_duyet, col_tuchoi = st.columns(2)
                with col_duyet:
                    if st.button(
                        "✅ Duyệt",
                        key=f"xd_duyet_{slug}_{loai}_{ds_nam[0]}",
                        type="primary",
                        use_container_width=True,
                        disabled=not co_quyen_duyet,
                    ):
                        duyet_ke_hoach_xd(pgd_ten, ds_nam, loai, "da_duyet", y_kien, username_duyetvien)
                        st.success(f"✅ Đã duyệt kế hoạch của {pgd_ten}")
                        st.rerun()
                with col_tuchoi:
                    if st.button(
                        "↩️ Trả lại",
                        key=f"xd_tuchoi_{slug}_{loai}_{ds_nam[0]}",
                        use_container_width=True,
                        disabled=not co_quyen_duyet,
                    ):
                        if not y_kien.strip():
                            st.warning("⚠️ Vui lòng nhập ý kiến khi trả lại kế hoạch.")
                        else:
                            duyet_ke_hoach_xd(pgd_ten, ds_nam, loai, "tu_choi", y_kien, username_duyetvien)
                            st.warning(f"↩️ Đã trả lại kế hoạch của {pgd_ten}")
                            st.rerun()

    # Danh sách đã duyệt — cho phép admin_cn mở lại
    da_duyet_list = [(pgd, ap) for pgd, ap in approval_map.items() if ap.get("trang_thai") == "da_duyet"]
    if da_duyet_list:
        with st.expander(f"🔓 Mở lại kế hoạch đã duyệt ({len(da_duyet_list)} PGD)", expanded=False):
            username_duyetvien = st.session_state.get("username", "unknown")
            for pgd_ten, ap in da_duyet_list:
                slug = pgd_slug(pgd_ten)
                ngay = (ap.get("ngay_duyet") or "")[:10]
                col_info, col_btn = st.columns([3, 1])
                col_info.markdown(f"**{pgd_ten}** — Duyệt: {ngay}")
                with col_btn:
                    if st.button(
                        "🔓 Mở lại",
                        key=f"xd_molai_{slug}_{loai}_{ds_nam[0]}",
                        use_container_width=True,
                        disabled=not la_admin_cn(role),
                    ):
                        mo_lai_ke_hoach(pgd_ten, ds_nam, loai, username_duyetvien)
                        st.info(f"🔓 Đã mở lại kế hoạch của {pgd_ten} để chỉnh sửa.")
                        st.rerun()


def _bang_trang_thai_1nam(nam: int, loai: str) -> None:
    trang_thai = trang_thai_xd_pgd(nam, loai)
    rows = []
    for pgd_ten, tt in trang_thai.items():
        rows.append({
            "PGD": pgd_ten,
            "Biểu 01C": "✅" if tt.get("co_01c") else "⏳",
            "Biểu 02C": "✅" if tt.get("co_02c") else "⏳",
            "Thuyết minh": "✅" if tt.get("co_tm") else "⏳",
        })
    so_xong = sum(
        1 for tt in trang_thai.values()
        if tt.get("co_01c") and tt.get("co_02c") and tt.get("co_tm")
    )
    st.caption(f"Hoàn thành cả 3 biểu: **{so_xong}/{len(DS_PGD)} PGD**")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _bang_trang_thai_da_nam(ds_nam: list[int], loai: str) -> None:
    all_tt = {nam: trang_thai_xd_pgd(nam, loai) for nam in ds_nam}
    rows = []
    for pgd_ten in DS_PGD:
        row: dict = {"PGD": pgd_ten}
        for nam in ds_nam:
            tt = all_tt[nam].get(pgd_ten, {})
            n_done = sum([
                tt.get("co_01c", False),
                tt.get("co_02c", False),
                tt.get("co_tm", False),
            ])
            row[str(nam)] = "✅" if n_done == 3 else (f"⚠️ {n_done}/3" if n_done > 0 else "⏳")
        rows.append(row)

    df_tt = pd.DataFrame(rows)
    # Tổng số PGD hoàn thành tất cả các năm
    so_xong_all = sum(
        1 for pgd in DS_PGD
        if all(
            all_tt[nam].get(pgd, {}).get("co_01c")
            and all_tt[nam].get(pgd, {}).get("co_02c")
            and all_tt[nam].get(pgd, {}).get("co_tm")
            for nam in ds_nam
        )
    )
    st.caption(
        f"PGD hoàn thành cả {len(ds_nam)} năm: "
        f"**{so_xong_all}/{len(DS_PGD)} PGD**"
    )
    st.dataframe(df_tt, use_container_width=True, hide_index=True)


def _bang_du_no_1nam(nam: int, loai: str) -> None:
    df = tong_hop_bieu_02c_cn(nam, loai)
    if df.empty:
        st.info(f"📭 Chưa có dữ liệu Biểu 02C năm {nam} ({loai}) từ PGD nào.")
        return

    df_ct = (
        df.groupby(["ma_key", "ten_ct", "nguon_von"], as_index=False)
          .agg(du_no_vnd=("du_no_vnd", "sum"))
    )
    df_ct["Dư nợ (tr.đ)"] = df_ct["du_no_vnd"].apply(fmt_ty)
    df_ct = df_ct.rename(columns={"ten_ct": "Chương trình", "nguon_von": "Nguồn vốn"})
    df_ct = df_ct[["Chương trình", "Nguồn vốn", "Dư nợ (tr.đ)"]].sort_values(
        ["Nguồn vốn", "Chương trình"]
    )
    tong = df["du_no_vnd"].sum()
    st.caption(f"Tổng dư nợ toàn CN: **{fmt_ty(tong)} triệu đồng**")
    st.dataframe(df_ct, use_container_width=True, hide_index=True)

    with st.expander("📊 Chi tiết theo PGD", expanded=False):
        df_piv = df.pivot_table(
            index="PGD", columns="ten_ct", values="du_no_vnd",
            aggfunc="sum", fill_value=0,
        )
        for col in df_piv.columns:
            df_piv[col] = df_piv[col].apply(fmt_ty)
        st.dataframe(df_piv, use_container_width=True)


def _bang_du_no_da_nam(ds_nam: list[int], loai: str) -> None:
    """Bảng so sánh dư nợ theo chương trình × năm (triệu đồng)."""
    frames: list[pd.DataFrame] = []
    tong_cn_vnd: float = 0.0
    for nam in ds_nam:
        df_y = tong_hop_bieu_02c_cn(nam, loai)
        if df_y.empty:
            continue
        tong_cn_vnd += float(df_y["du_no_vnd"].sum())
        df_agg = (
            df_y.groupby(["ten_ct", "nguon_von"], as_index=False)
                .agg(du_no_vnd=("du_no_vnd", "sum"))
        )
        df_agg = df_agg.rename(columns={"du_no_vnd": nam})
        frames.append(df_agg.set_index(["ten_ct", "nguon_von"]))

    if not frames:
        st.info("📭 Chưa có dữ liệu Biểu 02C cho giai đoạn này.")
        return

    df_combined = frames[0]
    for f in frames[1:]:
        df_combined = df_combined.join(f, how="outer")
    df_combined = df_combined.fillna(0).reset_index()
    df_combined = df_combined.rename(
        columns={"ten_ct": "Chương trình", "nguon_von": "Nguồn vốn"}
    )
    df_combined = df_combined.sort_values(["Nguồn vốn", "Chương trình"])

    # Cột tổng + format
    nam_cols = [c for c in df_combined.columns if isinstance(c, int)]
    df_combined["Tổng"] = df_combined[nam_cols].sum(axis=1)
    for col in nam_cols + ["Tổng"]:
        df_combined[col] = df_combined[col].apply(fmt_ty)

    st.caption(f"Tổng dư nợ giai đoạn: **{fmt_ty(tong_cn_vnd)} triệu đồng**")
    st.dataframe(df_combined, use_container_width=True, hide_index=True)


# ── Sub-tab 5: So sánh dự báo vs thực hiện ───────────────────────────────────

def _render_so_sanh_thuc_hien(tab, ds_nam: list[int], loai: str) -> None:
    """So sánh dư nợ KHTD dự báo (Biểu 02C) vs thực hiện (snapshot) theo năm."""
    import plotly.graph_objects as go

    with tab:
        st.markdown("#### 📈 So sánh dư nợ dự báo vs thực hiện")

        # ── 1. Dự báo từ Biểu 02C ──────────────────────────────────────────────
        plan_rows = []
        for nam in ds_nam:
            df_plan = tong_hop_bieu_02c_cn(nam, loai)
            plan_vnd = float(df_plan["du_no_vnd"].sum()) if not df_plan.empty else 0.0
            plan_rows.append({"nam": nam, "ke_hoach": plan_vnd})
        df_compare = pd.DataFrame(plan_rows)

        if df_compare["ke_hoach"].sum() == 0:
            st.info("ℹ️ Chưa có dữ liệu KHTD dự báo. Hãy nhập Biểu 02C cho các PGD.")
            return

        # ── 2. Thực hiện từ hstd_snapshot (kỳ mới nhất của mỗi năm) ──────────
        try:
            with db.get_conn() as conn:
                df_snap = conn.execute("""
                    WITH latest AS (
                        SELECT CAST(SUBSTR(ky, 1, 4) AS INTEGER) AS nam,
                               MAX(ky) AS ky_max
                        FROM hstd_snapshot
                        GROUP BY CAST(SUBSTR(ky, 1, 4) AS INTEGER)
                    )
                    SELECT l.nam, l.ky_max, SUM(s.tong_du_no) AS tong_dn
                    FROM hstd_snapshot s
                    JOIN latest l ON s.ky = l.ky_max
                    WHERE s.ma_ct = 'ALL' AND s.nguon_von = 'ALL'
                      AND s.ten_pgd = '__CN__'
                    GROUP BY l.nam
                    ORDER BY l.nam
                """).fetchall()
            snap_vnd = {row[0]: row[2] for row in df_snap}
            snap_ky  = {row[0]: row[1] for row in df_snap}
        except Exception as e:
            logger.error("_render_so_sanh_thuc_hien snapshot: %s", e, exc_info=True)
            snap_vnd = {}
            snap_ky  = {}

        df_compare["thuc_hien"] = df_compare["nam"].apply(lambda y: snap_vnd.get(y))
        df_compare["ky_sl"]     = df_compare["nam"].apply(lambda y: snap_ky.get(y, "—"))

        # ── 3. KPI cards ───────────────────────────────────────────────────────
        tong_kh = df_compare["ke_hoach"].sum()
        th_vals = df_compare["thuc_hien"].dropna()
        tong_th = float(th_vals.sum()) if len(th_vals) > 0 else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("Tổng KH dự báo", f"{tong_kh / 1e9:.2f} tỷ")
        c2.metric("Thực hiện (đã có SL)", f"{tong_th / 1e9:.2f} tỷ" if tong_th > 0 else "—")
        if tong_kh > 0 and tong_th > 0:
            c3.metric("% Đạt KH", f"{tong_th / tong_kh * 100:.1f}%")
        else:
            c3.metric("% Đạt KH", "—")

        # ── 4. Biểu đồ cột nhóm ───────────────────────────────────────────────
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_compare["nam"].astype(str),
            y=(df_compare["ke_hoach"] / 1e9).round(3),
            name="Dự báo KHTD",
            marker_color="#3b82f6",
            text=(df_compare["ke_hoach"] / 1e9).round(2).astype(str) + " tỷ",
            textposition="outside",
        ))
        has_actual = df_compare["thuc_hien"].notna().any()
        if has_actual:
            fig.add_trace(go.Bar(
                x=df_compare["nam"].astype(str),
                y=(df_compare["thuc_hien"].fillna(0) / 1e9).round(3),
                name="Thực hiện",
                marker_color="#10b981",
                text=(df_compare["thuc_hien"].fillna(0) / 1e9).round(2).astype(str) + " tỷ",
                textposition="outside",
            ))
        fig.update_layout(
            title=f"Dư nợ KH dự báo vs Thực hiện — {loai.upper()}",
            xaxis_title="Năm",
            yaxis_title="Tỷ đồng",
            barmode="group",
            height=420,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(t=80, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── 5. Bảng chi tiết theo năm ─────────────────────────────────────────
        st.markdown("##### Chi tiết theo năm")
        rows_show = []
        for _, row in df_compare.iterrows():
            kh_ty = round(row["ke_hoach"] / 1e9, 3)
            th_ty = round(row["thuc_hien"] / 1e9, 3) if pd.notna(row["thuc_hien"]) else None
            pct = round(th_ty / kh_ty * 100, 1) if (th_ty and kh_ty > 0) else None
            rows_show.append({
                "Năm": int(row["nam"]),
                "KH dự báo (tỷ)": kh_ty,
                "Thực hiện (tỷ)": th_ty if th_ty is not None else "—",
                "% Đạt": f"{pct}%" if pct is not None else "—",
                "Kỳ số liệu": row["ky_sl"],
            })
        st.dataframe(pd.DataFrame(rows_show), use_container_width=True, hide_index=True)

        if not has_actual:
            st.caption("💡 Cột 'Thực hiện' sẽ hiển thị khi có dữ liệu merge HSTD (snapshot tự động cập nhật sau merge).")

        # ── 6. Biểu đồ theo PGD — năm đầu tiên ───────────────────────────────
        st.markdown(f"##### Dư nợ dự báo theo PGD — Năm {ds_nam[0]}")
        df_pgd = tong_hop_bieu_02c_cn(ds_nam[0], loai)
        if not df_pgd.empty:
            df_pgd_agg = (
                df_pgd.groupby("PGD", as_index=False)["du_no_vnd"]
                .sum()
                .sort_values("du_no_vnd", ascending=False)
            )
            df_pgd_agg["Dư nợ (tỷ)"] = (df_pgd_agg["du_no_vnd"] / 1e9).round(3)
            fig_pgd = go.Figure(go.Bar(
                x=df_pgd_agg["PGD"],
                y=df_pgd_agg["Dư nợ (tỷ)"],
                marker_color="#6366f1",
                text=df_pgd_agg["Dư nợ (tỷ)"].round(2).astype(str) + " tỷ",
                textposition="outside",
            ))
            fig_pgd.update_layout(
                title=f"Dư nợ dự báo từng PGD — Năm {ds_nam[0]} ({loai.upper()})",
                xaxis_title="PGD",
                yaxis_title="Tỷ đồng",
                height=450,
                margin=dict(t=60, b=120),
                xaxis_tickangle=-40,
            )
            st.plotly_chart(fig_pgd, use_container_width=True)
        else:
            st.caption(f"📭 Chưa có dữ liệu Biểu 02C năm {ds_nam[0]}.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_trieu(vnd_or_zero) -> float:
    """Chuyển giá trị VND đã lưu → triệu đồng để hiển thị trong number_input."""
    try:
        return float(vnd_or_zero) / 1_000_000
    except (TypeError, ValueError):
        return 0.0
