"""Tab Quản lý nội bộ Phòng KH-NV — 4 sub-tab:
1. Phân công cán bộ
2. Lịch công tác
3. Báo cáo cấp trên (wrapper)
4. Giao việc PGD (wrapper)
"""

from uuid import uuid4
from datetime import date, datetime, timedelta

import streamlit as st
import pandas as pd

from auth import normalize_role, la_phan_he_cn
from db import doc_kv, ghi_kv, ghi_audit
from utils import get_tab_context
from tabs import tab_checklist_bc, tab_tien_do

LOAI_LICH = {
    "hop": "🗓️ Họp",
    "kiem_tra": "🔍 Kiểm tra thực địa",
    "cong_tac": "✈️ Công tác",
    "tap_huan": "🎓 Tập huấn",
    "khac": "📌 Khác",
}

_TRANG_THAI_CV = ["chua_lam", "dang_lam", "hoan_thanh", "tre_han"]
_TRANG_THAI_LABEL = {
    "chua_lam": "🔴 Chưa làm",
    "dang_lam": "🟡 Đang làm",
    "hoan_thanh": "✅ Hoàn thành",
    "tre_han": "⛔ Trễ hạn",
}
_UU_TIEN = ["khan_cap", "quan_trong", "binh_thuong"]
_UU_TIEN_LABEL = {
    "khan_cap": "🔴 Khẩn cấp",
    "quan_trong": "🟠 Quan trọng",
    "binh_thuong": "🔵 Bình thường",
}

KHNV_PHAN_CONG = "khnv_phan_cong_list"
KHNV_LICH = "khnv_lich_list"


def _doc_ds(key: str) -> list:
    """Đọc danh sách từ kv_store, trả về list rỗng nếu chưa có."""
    val = doc_kv(key)
    return val if isinstance(val, list) else []


def _ghi_ds(key: str, ds: list, username: str, action: str, mo_ta: str):
    """Ghi danh sách + audit."""
    ghi_kv(key, ds, username)
    ghi_audit(username, action, mo_ta)
    st.cache_data.clear()


# ──────────────────────────────────────────────
# SUB-TAB 1: 📋 Phân công cán bộ
# ──────────────────────────────────────────────


def _render_phan_cong(tab, role_n: str, username: str):
    """Form + bảng phân công việc nội bộ phòng."""
    co_quyen_ghi = role_n in ("admin_cn", "manager_cn")
    co_quyen_xoa = role_n == "admin_cn"

    ds = _doc_ds(KHNV_PHAN_CONG)

    # ── Form thêm mới ──
    if co_quyen_ghi:
        with st.expander("➕ Giao việc mới", expanded=False):
            with st.form("form_phan_cong", clear_on_submit=True):
                tieu_de = st.text_input("Tiêu đề *")
                mo_ta = st.text_area("Mô tả / hướng dẫn")
                nguoi = st.text_input("Người thực hiện *")
                uu_tien = st.selectbox("Ưu tiên", _UU_TIEN, format_func=lambda x: _UU_TIEN_LABEL[x])
                ngay_giao = st.date_input("Ngày giao", value=date.today())
                ngay_deadline = st.date_input("Deadline *", value=date.today())
                submitted = st.form_submit_button("🚀 Giao việc", type="primary")
                if submitted:
                    if not tieu_de.strip() or not nguoi.strip():
                        st.error("Vui lòng nhập Tiêu đề và Người thực hiện.")
                    else:
                        ds.append({
                            "id": str(uuid4()),
                            "tieu_de": tieu_de.strip(),
                            "mo_ta": mo_ta.strip(),
                            "nguoi_thuc_hien": nguoi.strip(),
                            "uu_tien": uu_tien,
                            "trang_thai": "chua_lam",
                            "ngay_giao": ngay_giao.isoformat(),
                            "ngay_deadline": ngay_deadline.isoformat(),
                            "ghi_chu_ket_qua": "",
                            "ngay_hoan_thanh": None,
                        })
                        _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_giao_viec",
                                f"Giao: {tieu_de.strip()} → {nguoi.strip()}")
                        st.success("✅ Đã giao việc thành công!")
                        st.rerun()

    # ── Bảng danh sách ──
    if not ds:
        st.info("ℹ️ Chưa có việc nào được giao.")
        return

    # Sắp xếp: chưa làm / đang làm lên trước
    ds_sorted = sorted(ds, key=lambda x: (
        0 if x.get("trang_thai") in ("chua_lam", "dang_lam") else 1,
        x.get("ngay_deadline", ""),
    ))

    st.markdown("### 📋 Danh sách phân công")

    today = date.today()
    for i, cv in enumerate(ds_sorted):
        trang_thai = cv.get("trang_thai", "chua_lam")
        deadline_str = cv.get("ngay_deadline", "")
        try:
            deadline = date.fromisoformat(deadline_str) if deadline_str else None
        except ValueError:
            deadline = None

        # Màu dòng
        row_class = ""
        if trang_thai == "tre_han":
            row_class = "background-color: #ffe0e0;"  # đỏ nhạt
        elif deadline and trang_thai in ("chua_lam", "dang_lam"):
            delta_days = (deadline - today).days
            if delta_days < 0:
                row_class = "background-color: #ffe0e0;"
            elif delta_days <= 3:
                row_class = "background-color: #fff3cd;"  # vàng nhạt

        with st.container():
            st.markdown(f"<div style='{row_class} padding:8px; border-radius:4px; margin-bottom:4px;'>", unsafe_allow_html=True)
            cols = st.columns([3, 1.5, 1.5, 1.5, 2])
            with cols[0]:
                st.markdown(f"**{cv.get('tieu_de','')}**")
                if cv.get("mo_ta"):
                    st.caption(cv["mo_ta"])
            with cols[1]:
                st.markdown(f"👤 {cv.get('nguoi_thuc_hien','')}")
            with cols[2]:
                uu = cv.get("uu_tien", "binh_thuong")
                st.markdown(f"{_UU_TIEN_LABEL.get(uu, uu)}")
            with cols[3]:
                st.markdown(f"📅 {deadline_str}")
            with cols[4]:
                st.markdown(f"{_TRANG_THAI_LABEL.get(trang_thai, trang_thai)}")
                if cv.get("ngay_hoan_thanh"):
                    st.caption(f"✓ {cv['ngay_hoan_thanh']}")

            # Cập nhật trạng thái + ghi chú
            with st.expander("📝 Cập nhật", expanded=False):
                new_status = st.selectbox(
                    "Trạng thái",
                    _TRANG_THAI_CV,
                    index=_TRANG_THAI_CV.index(trang_thai) if trang_thai in _TRANG_THAI_CV else 0,
                    key=f"status_{cv['id']}",
                    format_func=lambda x: _TRANG_THAI_LABEL.get(x, x),
                )
                new_ghi_chu = st.text_area(
                    "Ghi chú kết quả",
                    value=cv.get("ghi_chu_ket_qua", ""),
                    key=f"note_{cv['id']}",
                )
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("💾 Cập nhật", key=f"update_{cv['id']}"):
                        cv["trang_thai"] = new_status
                        cv["ghi_chu_ket_qua"] = new_ghi_chu
                        if new_status == "hoan_thanh" and not cv.get("ngay_hoan_thanh"):
                            cv["ngay_hoan_thanh"] = today.isoformat()
                        _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_cap_nhat_trang_thai",
                                f"Cập nhật {cv.get('tieu_de','')} → {new_status}")
                        st.success("✅ Đã cập nhật!")
                        st.rerun()
                with col2:
                    if co_quyen_xoa:
                        confirm_key = f"del_confirm_{cv['id']}"
                        if st.checkbox("☑ Xác nhận xóa", key=confirm_key):
                            if st.button("🗑️ Xóa", key=f"del_{cv['id']}"):
                                ds.remove(cv)
                                _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_xoa_viec",
                                        f"Xóa: {cv.get('tieu_de','')}")
                                st.success("✅ Đã xóa!")
                                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# SUB-TAB 2: 📅 Lịch công tác
# ──────────────────────────────────────────────


def _render_lich_cong_tac(tab, role_n: str, username: str):
    """Quản lý lịch họp / kiểm tra / công tác / tập huấn."""
    co_quyen_ghi = role_n in ("admin_cn", "manager_cn")
    co_quyen_xoa = role_n == "admin_cn"

    ds = _doc_ds(KHNV_LICH)
    today = date.today()

    # Tự động cập nhật trạng thái sự kiện đã qua
    changed = False
    for ev in ds:
        if ev.get("trang_thai") == "sap_dien_ra":
            try:
                ngay = date.fromisoformat(ev["ngay"])
                if ngay < today:
                    ev["trang_thai"] = "da_hoan_thanh"
                    changed = True
            except (ValueError, KeyError):
                pass
    if changed:
        ghi_kv(KHNV_LICH, ds, username)
        ghi_audit(username, "khnv_tu_dong_cap_nhat_lich", "Tự động cập nhật trạng thái lịch đã qua")

    # ── Form thêm sự kiện ──
    if co_quyen_ghi:
        with st.expander("➕ Thêm sự kiện", expanded=False):
            with st.form("form_lich", clear_on_submit=True):
                tieu_de = st.text_input("Tiêu đề *")
                loai = st.selectbox("Loại", list(LOAI_LICH.keys()), format_func=lambda x: LOAI_LICH[x])
                ngay = st.date_input("Ngày *", value=today)
                dia_diem = st.text_input("Địa điểm")
                thanh_vien = st.text_area("Thành viên tham dự")
                ghi_chu = st.text_area("Ghi chú")
                submitted = st.form_submit_button("🚀 Thêm", type="primary")
                if submitted:
                    if not tieu_de.strip():
                        st.error("Vui lòng nhập Tiêu đề.")
                    else:
                        ds.append({
                            "id": str(uuid4()),
                            "tieu_de": tieu_de.strip(),
                            "loai": loai,
                            "ngay": ngay.isoformat(),
                            "dia_diem": dia_diem.strip(),
                            "thanh_vien": thanh_vien.strip(),
                            "ghi_chu": ghi_chu.strip(),
                            "trang_thai": "sap_dien_ra",
                        })
                        _ghi_ds(KHNV_LICH, ds, username, "khnv_them_lich",
                                f"{LOAI_LICH.get(loai,loai)}: {tieu_de.strip()} ngày {ngay.isoformat()}")
                        st.success("✅ Đã thêm sự kiện!")
                        st.rerun()

    if not ds:
        st.info("ℹ️ Chưa có lịch công tác nào.")
        return

    # ── Bộ lọc ──
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        thang_loc = st.selectbox("Tháng", list(range(1, 13)), index=today.month - 1, key="lich_thang")
    with col_f2:
        nam_loc = st.selectbox("Năm", list(range(today.year - 2, today.year + 3)), index=2, key="lich_nam")
    loai_loc = st.selectbox("Loại", ["Tất cả"] + list(LOAI_LICH.keys()),
                            format_func=lambda x: "Tất cả" if x == "Tất cả" else LOAI_LICH[x],
                            key="lich_loai")

    # Lọc
    ds_loc = []
    for ev in ds:
        try:
            ev_date = date.fromisoformat(ev["ngay"])
        except (ValueError, KeyError):
            continue
        if ev_date.month != thang_loc or ev_date.year != nam_loc:
            continue
        if loai_loc != "Tất cả" and ev.get("loai") != loai_loc:
            continue
        ds_loc.append(ev)

    ds_loc.sort(key=lambda x: x.get("ngay", ""))

    # ── Bảng ──
    st.markdown("### 📅 Lịch công tác trong tháng")
    for ev in ds_loc:
        try:
            ev_date = date.fromisoformat(ev["ngay"])
        except (ValueError, KeyError):
            ev_date = None

        # Highlight tuần hiện tại
        is_current_week = False
        if ev_date:
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            is_current_week = start_week <= ev_date <= end_week

        bg = "#e8f4fd;" if is_current_week else ""
        st.markdown(f"<div style='background-color:{bg} padding:8px; border-radius:4px; margin-bottom:4px;'>", unsafe_allow_html=True)

        cols = st.columns([1.5, 1.5, 3, 2, 2, 1.5])
        with cols[0]:
            st.markdown(f"**{ev.get('ngay','')}**")
        with cols[1]:
            loai = ev.get("loai", "khac")
            st.markdown(LOAI_LICH.get(loai, loai))
        with cols[2]:
            st.markdown(f"**{ev.get('tieu_de','')}**")
        with cols[3]:
            st.markdown(f"📍 {ev.get('dia_diem','')}")
        with cols[4]:
            st.markdown(f"👥 {ev.get('thanh_vien','')}")
        with cols[5]:
            tt = ev.get("trang_thai", "sap_dien_ra")
            if tt == "sap_dien_ra":
                st.markdown("🟡 Sắp diễn ra")
            elif tt == "da_hoan_thanh":
                st.markdown("✅ Đã hoàn thành")
            elif tt == "huy_bo":
                st.markdown("❌ Hủy bỏ")

        if co_quyen_ghi:
            with st.expander("✏️ Sửa / Xóa", expanded=False):
                new_tieu_de = st.text_input("Tiêu đề", value=ev.get("tieu_de", ""), key=f"lt_{ev['id']}")
                new_loai = st.selectbox("Loại", list(LOAI_LICH.keys()),
                                        index=list(LOAI_LICH.keys()).index(ev.get("loai", "khac")) if ev.get("loai") in LOAI_LICH else 0,
                                        key=f"ll_{ev['id']}",
                                        format_func=lambda x: LOAI_LICH[x])
                new_ngay = st.date_input("Ngày",
                                         value=date.fromisoformat(ev["ngay"]) if ev.get("ngay") else today,
                                         key=f"ln_{ev['id']}")
                new_dia_diem = st.text_input("Địa điểm", value=ev.get("dia_diem", ""), key=f"ld_{ev['id']}")
                new_thanh_vien = st.text_area("Thành viên", value=ev.get("thanh_vien", ""), key=f"ltv_{ev['id']}")
                new_ghi_chu = st.text_area("Ghi chú", value=ev.get("ghi_chu", ""), key=f"lg_{ev['id']}")
                new_trang_thai = st.selectbox("Trạng thái",
                                              ["sap_dien_ra", "da_hoan_thanh", "huy_bo"],
                                              index=["sap_dien_ra", "da_hoan_thanh", "huy_bo"].index(ev.get("trang_thai", "sap_dien_ra")),
                                              key=f"ltt_{ev['id']}",
                                              format_func=lambda x: {"sap_dien_ra": "🟡 Sắp diễn ra",
                                                                     "da_hoan_thanh": "✅ Đã hoàn thành",
                                                                     "huy_bo": "❌ Hủy bỏ"}.get(x, x))
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    if st.button("💾 Lưu", key=f"save_lich_{ev['id']}"):
                        if new_tieu_de.strip():
                            ev["tieu_de"] = new_tieu_de.strip()
                            ev["loai"] = new_loai
                            ev["ngay"] = new_ngay.isoformat()
                            ev["dia_diem"] = new_dia_diem.strip()
                            ev["thanh_vien"] = new_thanh_vien.strip()
                            ev["ghi_chu"] = new_ghi_chu.strip()
                            ev["trang_thai"] = new_trang_thai
                            _ghi_ds(KHNV_LICH, ds, username, "khnv_sua_lich",
                                    f"Sửa: {new_tieu_de.strip()}")
                            st.success("✅ Đã lưu!")
                            st.rerun()
                with col_s2:
                    if co_quyen_xoa:
                        confirm_key = f"del_lich_confirm_{ev['id']}"
                        if st.checkbox("☑ Xác nhận xóa", key=confirm_key):
                            if st.button("🗑️ Xóa", key=f"del_lich_{ev['id']}"):
                                ds.remove(ev)
                                _ghi_ds(KHNV_LICH, ds, username, "khnv_xoa_lich",
                                        f"Xóa: {ev.get('tieu_de','')}")
                                st.success("✅ Đã xóa!")
                                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# RENDER CHÍNH
# ──────────────────────────────────────────────


def render(tab=None, **kwargs):
    """4 sub-tab: Phân công cán bộ, Lịch công tác, Báo cáo cấp trên, Giao việc PGD.

    Chỉ khả dụng cho phòng KH-NV (admin_cn, manager_cn, chuyenvien_cn, executive).
    """
    ctx = get_tab_context(tab)
    role_n = normalize_role(str(kwargs.get("role", "user")))
    username = kwargs.get("username", "unknown")

    if role_n in ("user", "manager_pgd", "admin_pgd"):
        with ctx:
            st.warning("⚠️ Tab này chỉ dành cho phòng KH-NV.")
        return

    with ctx:
        t1, t2, t3, t4 = st.tabs([
            "📋 Phân công cán bộ",
            "📅 Lịch công tác",
            "📤 Báo cáo cấp trên",
            "📌 Giao việc PGD",
        ])
        with t1:
            _render_phan_cong(t1, role_n, username)
        with t2:
            _render_lich_cong_tac(t2, role_n, username)
        with t3:
            tab_checklist_bc.render(t3, **kwargs)
        with t4:
            tab_tien_do.render(t4, **kwargs)
