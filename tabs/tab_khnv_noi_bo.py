"""Tab Quản lý nội bộ Phòng KH-NV — 6 sub-tab theo luồng 5 bước:
1. 👥 Nhân sự & Chức vụ    — khai báo cán bộ một lần
2. 📋 Phân công công việc  — dropdown cán bộ → đầu việc lọc theo chức vụ
3. 📊 Tiến độ / Chỉnh sửa  — cập nhật nhanh + edit chi tiết + xóa
4. 📄 In báo cáo           — PDF, Excel, checklist cấp trên
5. 📅 Lịch công tác        — giữ nguyên
6. 📖 Thông tin đầu việc   — bảng tham chiếu tĩnh TP01–TP17 + 38 việc cấp dưới
"""

import calendar
from uuid import uuid4
from datetime import date, datetime, timedelta
from collections import defaultdict

import streamlit as st
import pandas as pd

from auth import normalize_role, la_phan_he_cn
from db import doc_kv, ghi_kv, ghi_audit
from services import khnv_noi_bo_service
from services.khnv_noi_bo_service import (
    _xuat_bc_phan_cong,
    _xuat_bc_tien_do,
    _CHUC_VU_MAP,
    _CHUC_VU_LABEL,
    _CHUC_VU_SHORT,
    _CHUC_VU_TASK_FILTER,
    _MAU_GIAO_VIEC,
    _MAU_GIAO_VIEC_TP,
    _guess_chuc_vu,
    _safe_date_lt,
)
from utils import get_tab_context, xuat_excel

# ──────────────────────────────────────────────
# HẰNG SỐ & NHÃN
# ──────────────────────────────────────────────

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

# kv_store keys
KHNV_PHAN_CONG = "khnv_phan_cong_list"
KHNV_LICH      = "khnv_lich_list"
KHNV_CAN_BO    = "khnv_can_bo_list"   # {id, ho_ten, chuc_vu: "vp1"|"vp2"|"cbtd"}



# ──────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────


def _doc_ds(key: str) -> list:
    """Đọc danh sách từ kv_store, trả về list rỗng nếu chưa có."""
    return khnv_noi_bo_service.doc_ds(key)


def _ghi_ds(key: str, ds: list, username: str, action: str, mo_ta: str):
    """Ghi danh sách + audit."""
    khnv_noi_bo_service.ghi_ds(key, ds, username, action, mo_ta)
    st.cache_data.clear()




# ──────────────────────────────────────────────
# TẢI MẪU GIAO VIỆC
# ──────────────────────────────────────────────


def _tai_mau_giao_viec_v2(ds: list, username: str,
                           vp1: str, vp2: str, cbtd_list: list) -> None:
    """Tải mẫu giao việc — nhân bản task Cán bộ TD theo danh sách tên thực tế."""
    today_str = date.today().isoformat()
    vp1_name = vp1 or "Phó phòng (VT 1)"
    vp2_name = vp2 or "Phó phòng (VT 2)"
    cb_names = cbtd_list if cbtd_list else ["Cán bộ TD"]

    _nhom_ref = [""]  # mutable container để closure _mk đọc được nhom hiện tại

    def _mk(tieu_de: str, mo_ta: str, nguoi: str, chuc_vu: str) -> dict:
        return {
            "id": str(uuid4()),
            "tieu_de": tieu_de,
            "mo_ta": mo_ta,
            "nguoi_thuc_hien": nguoi,
            "chuc_vu": chuc_vu,
            "nhom": _nhom_ref[0],
            "uu_tien": "binh_thuong",
            "trang_thai": "chua_lam",
            "ngay_giao": today_str,
            "ngay_deadline": "",
            "ghi_chu_ket_qua": "",
            "ngay_hoan_thanh": None,
        }

    new_tasks = []
    for t in _MAU_GIAO_VIEC:
        _nhom_ref[0] = t.get("nhom", "")
        td, mo, ng = t["tieu_de"], t["mo_ta"], t["nguoi_thuc_hien"]
        if ng == "Phó phòng (VT 1)":
            new_tasks.append(_mk(td, mo, vp1_name, "vp1"))
        elif ng == "Phó phòng (VT 2)":
            new_tasks.append(_mk(td, mo, vp2_name, "vp2"))
        elif ng == "Phó phòng (VT 1 & VT 2)":
            new_tasks += [_mk(td, mo, vp1_name, "vp1"), _mk(td, mo, vp2_name, "vp2")]
        elif ng in ("Cán bộ TD", "Cán bộ TD (theo địa bàn)"):
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        elif ng == "Phó phòng (VT 1) + Cán bộ TD":
            new_tasks.append(_mk(td, mo, vp1_name, "vp1"))
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        elif ng == "Phó phòng (VT 2) + Cán bộ TD":
            new_tasks.append(_mk(td, mo, vp2_name, "vp2"))
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        elif ng == "Phó phòng (VT 1 & VT 2), Cán bộ TD":
            new_tasks += [_mk(td, mo, vp1_name, "vp1"), _mk(td, mo, vp2_name, "vp2")]
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        elif ng == "Tất cả cán bộ":
            new_tasks += [_mk(td, mo, vp1_name, "vp1"), _mk(td, mo, vp2_name, "vp2")]
            new_tasks += [_mk(td, mo, n, "cbtd") for n in cb_names]
        else:
            new_tasks.append(_mk(td, mo, ng, "cbtd"))

    ds.extend(new_tasks)
    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_tai_mau_giao_viec",
            f"Tải {len(new_tasks)} task từ Bảng giao việc Trưởng phòng KH-NVTD")
    st.success(f"✅ Đã tải {len(new_tasks)} task!")
    st.rerun()


def _tai_mau_tu_kv(ds: list, username: str) -> None:
    """Tải 38 đầu việc mẫu — đọc tên cán bộ từ KHNV_CAN_BO."""
    can_bo = _doc_ds(KHNV_CAN_BO)
    vp1_cb = next((c["ho_ten"] for c in can_bo if c["chuc_vu"] == "vp1"), "")
    vp2_cb = next((c["ho_ten"] for c in can_bo if c["chuc_vu"] == "vp2"), "")
    cbtd_list = [c["ho_ten"] for c in can_bo if c["chuc_vu"] == "cbtd"]
    _tai_mau_giao_viec_v2(ds, username, vp1_cb, vp2_cb, cbtd_list)


# ──────────────────────────────────────────────
# MINI DASHBOARD TIẾN ĐỘ
# ──────────────────────────────────────────────


def _render_mini_tien_do(ds: list, today: date) -> None:
    """Compact progress dashboard — 4 metrics + progress bar mỗi cán bộ."""
    total_all = ht_all = tre_all = dl_all = 0
    per_person: dict = {}   # nguoi → {total, hoan_thanh, tre_han}

    for c in ds:
        tt    = c.get("trang_thai", "chua_lam")
        nguoi = c.get("nguoi_thuc_hien") or "Không rõ"
        if nguoi not in per_person:
            per_person[nguoi] = {"total": 0, "hoan_thanh": 0, "tre_han": 0}
        per_person[nguoi]["total"] += 1
        total_all += 1

        is_overdue = False
        if tt in ("chua_lam", "dang_lam") and c.get("ngay_deadline"):
            try:
                is_overdue = date.fromisoformat(c["ngay_deadline"]) < today
            except ValueError:
                pass

        if tt == "hoan_thanh":
            per_person[nguoi]["hoan_thanh"] += 1
            ht_all += 1
        elif tt == "tre_han" or is_overdue:
            per_person[nguoi]["tre_han"] += 1
            tre_all += 1
        elif tt == "dang_lam":
            dl_all += 1

    pct_all = round(ht_all / total_all * 100, 1) if total_all else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📋 Tổng việc",    total_all)
    m2.metric("✅ Hoàn thành",   f"{ht_all}  ({pct_all}%)")
    m3.metric("🟡 Đang làm",    dl_all)
    m4.metric("⛔ Trễ hạn",     tre_all,
              delta=f"-{tre_all}" if tre_all else None, delta_color="inverse")

    if per_person:
        bars_html = ""
        for nguoi, s in sorted(per_person.items()):
            pct = round(s["hoan_thanh"] / s["total"] * 100) if s["total"] else 0
            color = (
                "#22c55e" if pct == 100 else
                "#3b82f6" if pct >= 70 else
                "#f59e0b" if pct >= 30 else
                "#ef4444"
            )
            tre_badge = (
                f' <span style="color:#b91c1c;font-size:0.72rem;font-weight:700">⛔{s["tre_han"]}</span>'
                if s["tre_han"] else ""
            )
            bars_html += (
                f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:0.83rem">'
                f'<span style="min-width:140px;font-weight:600">{nguoi}{tre_badge}</span>'
                f'<div style="flex:1;background:#e5e7eb;border-radius:4px;height:10px">'
                f'<div style="background:{color};width:{pct}%;height:100%;border-radius:4px"></div></div>'
                f'<span style="min-width:60px;text-align:right;opacity:0.65">{s["hoan_thanh"]}/{s["total"]} ({pct}%)</span>'
                f'</div>'
            )
        st.markdown(bars_html, unsafe_allow_html=True)

    st.divider()


# ──────────────────────────────────────────────
# HELPER: TASK CARD (dùng chung ở Tab 2 và Tab 3)
# ──────────────────────────────────────────────


def _render_task_card(cv: dict, ds: list, today: date,
                      role_n: str, username: str, key_prefix: str = "") -> None:
    """Render 1 task card: 4 cols + quick buttons + edit/delete expander."""
    k = cv["id"]
    trang_thai = cv.get("trang_thai", "chua_lam")
    co_quyen_ghi = role_n in ("admin_cn", "manager_cn")
    co_quyen_xoa = role_n == "admin_cn"

    deadline_str = cv.get("ngay_deadline", "")
    try:
        deadline_date = date.fromisoformat(deadline_str) if deadline_str else None
    except ValueError:
        deadline_date = None

    # Màu nền theo mức độ trễ
    row_style = ""
    if trang_thai == "tre_han":
        row_style = "background:#ffe0e0;"
    elif deadline_date and trang_thai in ("chua_lam", "dang_lam"):
        delta = (deadline_date - today).days
        if delta < 0:
            row_style = "background:#ffe0e0;"
        elif delta <= 3:
            row_style = "background:#fff3cd;"

    st.markdown(
        f"<div style='{row_style}padding:8px;border-radius:4px;margin-bottom:4px;'>",
        unsafe_allow_html=True,
    )
    cols = st.columns([4, 1.5, 1.5, 2])
    with cols[0]:
        st.markdown(f"**{cv.get('tieu_de', '')}**")
        _nguoi = cv.get("nguoi_thuc_hien", "")
        _mo_ta = cv.get("mo_ta", "")
        st.caption(f"👤 {_nguoi}" + (f"  ·  {_mo_ta}" if _mo_ta else ""))
    with cols[1]:
        uu = cv.get("uu_tien", "binh_thuong")
        st.markdown(_UU_TIEN_LABEL.get(uu, uu))
    with cols[2]:
        if deadline_str:
            overdue_icon = "⚠️ " if (deadline_date and deadline_date < today
                                     and trang_thai not in ("hoan_thanh", "tre_han")) else "📅 "
            st.markdown(f"{overdue_icon}{deadline_str}")
        if cv.get("ngay_hoan_thanh"):
            st.caption(f"✓ {cv['ngay_hoan_thanh']}")
    with cols[3]:
        st.markdown(_TRANG_THAI_LABEL.get(trang_thai, trang_thai))

    # Quick status buttons — chỉ hiện nút ≠ trạng thái hiện tại
    if co_quyen_ghi:
        _sq1, _sq2, _sq3 = st.columns(3)
        with _sq1:
            if trang_thai != "chua_lam":
                if st.button("🔴 Chưa làm", key=f"{key_prefix}q_cl_{k}",
                             use_container_width=True):
                    cv["trang_thai"] = "chua_lam"
                    cv["ngay_hoan_thanh"] = None
                    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_cap_nhat_trang_thai",
                            f"Đổi → chưa làm: {cv.get('tieu_de', '')}")
                    st.rerun()
        with _sq2:
            if trang_thai != "dang_lam":
                if st.button("🟡 Đang làm", key=f"{key_prefix}q_dl_{k}",
                             use_container_width=True):
                    cv["trang_thai"] = "dang_lam"
                    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_cap_nhat_trang_thai",
                            f"Đổi → đang làm: {cv.get('tieu_de', '')}")
                    st.rerun()
        with _sq3:
            if trang_thai != "hoan_thanh":
                if st.button("✅ Xong", key=f"{key_prefix}q_ht_{k}",
                             use_container_width=True):
                    cv["trang_thai"] = "hoan_thanh"
                    if not cv.get("ngay_hoan_thanh"):
                        cv["ngay_hoan_thanh"] = today.isoformat()
                    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_cap_nhat_trang_thai",
                            f"Đổi → hoàn thành: {cv.get('tieu_de', '')}")
                    st.rerun()

        with st.expander("✏️ Chỉnh sửa / Xóa", expanded=False):
            new_td = st.text_input("Tiêu đề",
                                   value=cv.get("tieu_de", ""),
                                   key=f"{key_prefix}td_edit_{k}")
            new_mo = st.text_area("Mô tả / hướng dẫn",
                                  value=cv.get("mo_ta", ""),
                                  key=f"{key_prefix}mo_edit_{k}")
            _ec1, _ec2 = st.columns(2)
            with _ec1:
                new_ng = st.text_input("Người thực hiện",
                                       value=cv.get("nguoi_thuc_hien", ""),
                                       key=f"{key_prefix}ng_edit_{k}")
            with _ec2:
                _uu_idx = _UU_TIEN.index(cv.get("uu_tien", "binh_thuong")) \
                          if cv.get("uu_tien") in _UU_TIEN else 2
                new_uu = st.selectbox("Mức độ", _UU_TIEN,
                                      index=_uu_idx,
                                      format_func=lambda x: _UU_TIEN_LABEL.get(x, x),
                                      key=f"{key_prefix}uu_edit_{k}")
            try:
                _dl_val = date.fromisoformat(cv["ngay_deadline"]) \
                          if cv.get("ngay_deadline") else today
            except ValueError:
                _dl_val = today
            new_dl = st.date_input("Thời gian hoàn thành", value=_dl_val,
                                   key=f"{key_prefix}dl_edit_{k}")
            new_gc = st.text_area("Ghi chú kết quả",
                                  value=cv.get("ghi_chu_ket_qua", ""),
                                  key=f"{key_prefix}gc_edit_{k}")
            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("💾 Lưu", key=f"{key_prefix}save_{k}",
                             use_container_width=True):
                    if new_td.strip():
                        cv["tieu_de"] = new_td.strip()
                    cv["mo_ta"] = new_mo.strip()
                    if new_ng.strip():
                        cv["nguoi_thuc_hien"] = new_ng.strip()
                    cv["uu_tien"] = new_uu
                    cv["ngay_deadline"] = new_dl.isoformat()
                    cv["ghi_chu_ket_qua"] = new_gc.strip()
                    _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_sua_task",
                            f"Sửa: {cv.get('tieu_de', '')}")
                    st.success("✅ Đã lưu!")
                    st.rerun()
            with col_del:
                if co_quyen_xoa:
                    if st.checkbox("☑ Xác nhận xóa",
                                   key=f"{key_prefix}del_confirm_{k}"):
                        if st.button("🗑️ Xóa", key=f"{key_prefix}del_{k}",
                                     use_container_width=True):
                            ds.remove(cv)
                            _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_xoa_task",
                                    f"Xóa: {cv.get('tieu_de', '')}")
                            st.success("✅ Đã xóa!")
                            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# TAB 1: 👥 Nhân sự & Chức vụ
# ──────────────────────────────────────────────


def _render_nhan_su(role_n: str, username: str) -> None:
    """Quản lý danh sách cán bộ — lưu vào KHNV_CAN_BO."""
    co_quyen = role_n in ("admin_cn", "manager_cn")
    can_bo = _doc_ds(KHNV_CAN_BO)

    st.markdown("### 👥 Danh sách cán bộ Phòng KH-NV")
    st.caption("Khai báo tên cán bộ tại đây — dùng để phân công và tải đầu việc mẫu ở Tab Phân công.")

    if not can_bo:
        st.info("ℹ️ Chưa có cán bộ. Thêm cán bộ để bắt đầu phân công.")
    else:
        edit_id = st.session_state.get("_edit_cb_id", None)
        for chuc_vu, label in _CHUC_VU_LABEL.items():
            nhom_cb = [c for c in can_bo if c["chuc_vu"] == chuc_vu]
            if not nhom_cb:
                continue
            st.markdown(f"**{label}**")
            for cb in nhom_cb:
                if edit_id == cb["id"]:
                    with st.container(border=True):
                        ho_ten_moi = st.text_input(
                            "Họ và tên", value=cb["ho_ten"], key=f"edit_cb_ten_{cb['id']}"
                        )
                        cv_keys = list(_CHUC_VU_LABEL.keys())
                        cv_idx = cv_keys.index(cb["chuc_vu"]) if cb["chuc_vu"] in cv_keys else 0
                        chuc_vu_moi = st.selectbox(
                            "Chức vụ / Vị trí",
                            cv_keys,
                            index=cv_idx,
                            format_func=lambda x: _CHUC_VU_LABEL[x],
                            key=f"edit_cb_cv_{cb['id']}",
                        )
                        c1, c2, _ = st.columns([1, 1, 4])
                        if c1.button("💾 Lưu", key=f"save_cb_{cb['id']}", type="primary",
                                      use_container_width=True):
                            if ho_ten_moi.strip():
                                cb["ho_ten"] = ho_ten_moi.strip()
                                cb["chuc_vu"] = chuc_vu_moi
                                _ghi_ds(KHNV_CAN_BO, can_bo, username,
                                        "khnv_sua_can_bo", f"Sửa cán bộ: {cb['ho_ten']}")
                                st.session_state.pop("_edit_cb_id", None)
                                st.rerun()
                            else:
                                st.error("Vui lòng nhập họ và tên.")
                        if c2.button("❌ Hủy", key=f"cancel_cb_{cb['id']}",
                                      use_container_width=True):
                            st.session_state.pop("_edit_cb_id", None)
                            st.rerun()
                else:
                    col_ten, col_sua, col_xoa = st.columns([5, 1, 1])
                    col_ten.write(f"👤 {cb['ho_ten']}")
                    if co_quyen:
                        if col_sua.button(
                            "✏️", key=f"sua_cb_{cb['id']}",
                            help=f"Chỉnh sửa {cb['ho_ten']}",
                        ):
                            st.session_state["_edit_cb_id"] = cb["id"]
                            st.rerun()
                        if col_xoa.button(
                            "🗑️", key=f"xoa_cb_{cb['id']}",
                            help="Xóa cán bộ này",
                        ):
                            can_bo.remove(cb)
                            _ghi_ds(KHNV_CAN_BO, can_bo, username,
                                    "khnv_xoa_can_bo", f"Xóa cán bộ: {cb['ho_ten']}")
                            st.rerun()

    if co_quyen:
        st.divider()
        with st.expander("➕ Thêm cán bộ", expanded=not can_bo):
            with st.form("form_them_can_bo", clear_on_submit=True):
                ho_ten = st.text_input("Họ và tên *")
                chuc_vu_sel = st.selectbox(
                    "Chức vụ / Vị trí",
                    list(_CHUC_VU_LABEL.keys()),
                    format_func=lambda x: _CHUC_VU_LABEL[x],
                    key="them_cb_chuc_vu",
                )
                if st.form_submit_button("✅ Thêm cán bộ", type="primary"):
                    if ho_ten.strip():
                        can_bo.append({
                            "id": str(uuid4()),
                            "ho_ten": ho_ten.strip(),
                            "chuc_vu": chuc_vu_sel,
                        })
                        _ghi_ds(KHNV_CAN_BO, can_bo, username,
                                "khnv_them_can_bo",
                                f"Thêm: {ho_ten.strip()} — {chuc_vu_sel}")
                        st.success(f"✅ Đã thêm {ho_ten.strip()}!")
                        st.rerun()
                    else:
                        st.error("Vui lòng nhập họ và tên.")


# ──────────────────────────────────────────────
# TAB 2: 📋 Phân công công việc
# ──────────────────────────────────────────────


def _render_phan_cong_v2(role_n: str, username: str) -> None:
    """Phân công: chọn cán bộ → dropdown đầu việc theo chức vụ → gom nhóm theo vị trí."""
    co_quyen_ghi = role_n in ("admin_cn", "manager_cn")
    today = date.today()

    can_bo_list = _doc_ds(KHNV_CAN_BO)
    ds = _doc_ds(KHNV_PHAN_CONG)

    # Mini dashboard ở trên nếu có dữ liệu
    if ds:
        _render_mini_tien_do(ds, today)

    if co_quyen_ghi:
        # ── Form giao việc từ dropdown ──
        if not can_bo_list:
            st.warning("⚠️ Chưa có cán bộ. Vào tab **Nhân sự & Chức vụ** để thêm trước.")
        else:
            with st.expander("➕ Giao việc từ danh sách mẫu", expanded=not ds):
                options_cb = [(c["id"], f"{c['ho_ten']} - {_CHUC_VU_SHORT.get(c['chuc_vu'], c['chuc_vu'])}") for c in can_bo_list]
                id_to_label = dict(options_cb)
                sel_id = st.selectbox(
                    "① Cán bộ thực hiện",
                    [x[0] for x in options_cb],
                    format_func=lambda i: id_to_label.get(i, i),
                    key="pc2_sel_cb",
                )
                sel_cb = next((c for c in can_bo_list if c["id"] == sel_id), None)

                if sel_cb:
                    allowed = _CHUC_VU_TASK_FILTER[sel_cb["chuc_vu"]]
                    mau_loc = [t for t in _MAU_GIAO_VIEC if t["nguoi_thuc_hien"] in allowed]
                    options_td = [
                        f"[{t['nhom'].split('.')[0]}] {t['tieu_de']}" for t in mau_loc
                    ]
                    sel_td_idx = st.selectbox(
                        "② Chọn đầu việc",
                        range(len(options_td)),
                        format_func=lambda i: options_td[i],
                        key="pc2_sel_td",
                    )
                    sel_mau = mau_loc[sel_td_idx]
                    st.caption(f"📝 {sel_mau['mo_ta']}")

                    _fc1, _fc2, _fc3 = st.columns(3)
                    with _fc1:
                        uu_sel = st.selectbox(
                            "Mức độ", _UU_TIEN,
                            format_func=lambda x: _UU_TIEN_LABEL[x],
                            index=2, key="pc2_uu",
                        )
                    with _fc2:
                        ngay_giao_sel = st.date_input("Ngày giao", value=today, key="pc2_ngay_giao")
                    with _fc3:
                        dl = st.date_input("Thời gian hoàn thành", value=today, key="pc2_dl")

                    if st.button("➕ Thêm đầu việc này", type="primary",
                                 key="pc2_btn_add", use_container_width=True):
                        ds.append({
                            "id": str(uuid4()),
                            "tieu_de": sel_mau["tieu_de"],
                            "mo_ta": sel_mau["mo_ta"],
                            "nguoi_thuc_hien": sel_cb["ho_ten"],
                            "chuc_vu": sel_cb["chuc_vu"],
                            "nhom": sel_mau["nhom"],
                            "uu_tien": uu_sel,
                            "trang_thai": "chua_lam",
                            "ngay_giao": ngay_giao_sel.isoformat(),
                            "ngay_deadline": dl.isoformat(),
                            "ghi_chu_ket_qua": "",
                            "ngay_hoan_thanh": None,
                        })
                        _ghi_ds(KHNV_PHAN_CONG, ds, username, "khnv_giao_viec",
                                f"Giao: {sel_mau['tieu_de']} → {sel_cb['ho_ten']}")
                        st.success("✅ Đã thêm!")
                        st.rerun()


    # ── Danh sách task gom nhóm theo chức vụ ──
    if not ds:
        st.info("ℹ️ Chưa có việc nào được giao.")
        return

    st.markdown("### 📋 Danh sách phân công theo vị trí")

    ds_sorted = sorted(ds, key=lambda x: (
        0 if x.get("trang_thai") in ("chua_lam", "dang_lam") else 1,
        x.get("ngay_deadline", ""),
    ))

    # Gom nhóm theo chức vụ
    nhom_cv: dict = {"vp1": [], "vp2": [], "cbtd": [], "other": []}
    for cv in ds_sorted:
        g = _guess_chuc_vu(cv)
        nhom_cv.get(g, nhom_cv["other"]).append(cv)

    cv_order = list(_CHUC_VU_LABEL.items()) + [("other", "📌 Thêm thủ công")]
    for chuc_vu, label in cv_order:
        tasks = nhom_cv.get(chuc_vu, [])
        if not tasks:
            continue
        ht = sum(1 for t in tasks if t.get("trang_thai") == "hoan_thanh")
        tre = sum(1 for t in tasks
                  if t.get("trang_thai") not in ("hoan_thanh",)
                  and t.get("ngay_deadline")
                  and _safe_date_lt(t["ngay_deadline"], today))
        badge_tre = f"  ·  ⛔ {tre} trễ" if tre else ""
        hdr = f"{label}  ·  {ht}/{len(tasks)} ✅{badge_tre}"
        with st.expander(hdr, expanded=True):
            for cv in tasks:
                _render_task_card(cv, ds, today, role_n, username, key_prefix="pc2_")



# ──────────────────────────────────────────────
# TAB 3: 📊 Tiến độ / Chỉnh sửa / Xóa
# ──────────────────────────────────────────────


def _render_tien_do_edit(role_n: str, username: str) -> None:
    """Tab tiến độ: mini dashboard + bộ lọc + quick buttons + edit chi tiết."""
    ds = _doc_ds(KHNV_PHAN_CONG)
    today = date.today()

    if not ds:
        st.info("📭 Chưa có đầu việc. Vào tab **Phân công** để thêm.")
        return

    _render_mini_tien_do(ds, today)

    # Bộ lọc
    col_f1, col_f2 = st.columns(2)
    filter_tt = col_f1.multiselect(
        "Lọc trạng thái",
        list(_TRANG_THAI_LABEL.keys()),
        format_func=lambda x: _TRANG_THAI_LABEL[x],
        key="td_filter_tt",
    )
    nguoi_options = ["Tất cả"] + sorted(
        {c.get("nguoi_thuc_hien", "") for c in ds if c.get("nguoi_thuc_hien")}
    )
    filter_nguoi = col_f2.selectbox("Lọc người", nguoi_options, key="td_filter_nguoi")

    ds_view = [
        c for c in ds
        if (not filter_tt or c.get("trang_thai") in filter_tt)
        and (filter_nguoi == "Tất cả" or c.get("nguoi_thuc_hien") == filter_nguoi)
    ]
    ds_view.sort(key=lambda x: (
        0 if x.get("trang_thai") in ("chua_lam", "dang_lam") else 1,
        x.get("ngay_deadline", ""),
    ))

    st.markdown(f"**{len(ds_view)} đầu việc**" + (" (đã lọc)" if filter_tt or filter_nguoi != "Tất cả" else ""))

    for cv in ds_view:
        _render_task_card(cv, ds, today, role_n, username, key_prefix="td_")




def _render_bao_cao(role_n: str, username: str, **kwargs) -> None:
    """Tab báo cáo: Word/PDF phân công, Word/PDF tiến độ, Excel, Checklist."""
    ds = _doc_ds(KHNV_PHAN_CONG)
    today = date.today()

    st.markdown("### 📄 Xuất báo cáo")

    # ── Tham số chung (tháng/năm/tên trưởng phòng) ──
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        thang_bc = st.number_input("Tháng báo cáo", min_value=1, max_value=12,
                                   value=today.month, step=1, key="bc_thang")
    with col_p2:
        nam_bc = st.number_input("Năm báo cáo", min_value=2020, max_value=2099,
                                 value=today.year, step=1, key="bc_nam")
    with col_p3:
        ten_tp = st.text_input("Tên Trưởng phòng", value="", key="bc_ten_tp",
                               placeholder="Nguyễn Văn A")

    st.divider()

    # ── Phần 1: Danh sách phân công và giao việc ──
    st.markdown("**📋 1. Báo cáo danh sách phân công và giao việc**")
    col1a, col1b = st.columns(2)
    with col1a:
        if ds:
            docx_pc = _xuat_bc_phan_cong(ds, int(thang_bc), int(nam_bc), ten_tp)
            st.download_button(
                "📄 Xuất Word",
                data=docx_pc,
                file_name=f"phan_cong_t{int(thang_bc)}_{int(nam_bc)}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="bc_dl_pc_word",
                use_container_width=True,
            )
        else:
            st.button("📄 Xuất Word", disabled=True, key="bc_dl_pc_word_dis",
                      use_container_width=True)
    with col1b:
        if ds:
            if st.button("🖨️ Xuất PDF", key="bc_btn_pc_pdf", use_container_width=True):
                try:
                    import tempfile
                    import os as _os
                    from docx2pdf import convert  # conv: skip
                    _bytes = _xuat_bc_phan_cong(ds, int(thang_bc), int(nam_bc), ten_tp)
                    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as _f:
                        _f.write(_bytes)
                        _tmp_docx = _f.name
                    _tmp_pdf = _tmp_docx.replace(".docx", ".pdf")
                    try:
                        convert(_tmp_docx, _tmp_pdf)
                        st.session_state["_bc_pc_pdf"] = open(_tmp_pdf, "rb").read()
                        ghi_audit(username, "xuat_bieu_cn",
                                  f"Xuất PDF phân công T{int(thang_bc)}/{int(nam_bc)}")
                    finally:
                        _os.unlink(_tmp_docx)
                        if _os.path.exists(_tmp_pdf):
                            _os.unlink(_tmp_pdf)
                except ImportError:
                    st.warning("⚠️ Cần cài đặt MS Word để xuất PDF. "
                               "Hãy tải file Word và tự chuyển đổi.")
                except Exception as _e:
                    st.warning(f"⚠️ Không thể xuất PDF: {_e}. "
                               "Hãy tải file Word để chuyển đổi thủ công.")
            if "_bc_pc_pdf" in st.session_state:
                st.download_button(
                    "📥 Tải PDF phân công",
                    data=st.session_state["_bc_pc_pdf"],
                    file_name=f"phan_cong_t{int(thang_bc)}_{int(nam_bc)}.pdf",
                    mime="application/pdf",
                    key="bc_dl_pc_pdf",
                    use_container_width=True,
                )
        else:
            st.button("🖨️ Xuất PDF", disabled=True, key="bc_btn_pc_pdf_dis",
                      use_container_width=True)
    if not ds:
        st.caption("⚠️ Chưa có dữ liệu phân công. Vào tab Phân công để thêm.")

    st.divider()

    # ── Phần 2: Báo cáo tiến độ thực hiện ──
    st.markdown("**📊 2. Báo cáo tiến độ thực hiện công việc**")
    col2a, col2b = st.columns(2)
    with col2a:
        if ds:
            docx_td = _xuat_bc_tien_do(ds, int(thang_bc), int(nam_bc), ten_tp)
            st.download_button(
                "📄 Xuất Word",
                data=docx_td,
                file_name=f"tien_do_t{int(thang_bc)}_{int(nam_bc)}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="bc_dl_td_word",
                use_container_width=True,
            )
        else:
            st.button("📄 Xuất Word", disabled=True, key="bc_dl_td_word_dis",
                      use_container_width=True)
    with col2b:
        if ds:
            if st.button("🖨️ Xuất PDF", key="bc_btn_td_pdf", use_container_width=True):
                try:
                    import tempfile
                    import os as _os
                    from docx2pdf import convert  # conv: skip
                    _bytes = _xuat_bc_tien_do(ds, int(thang_bc), int(nam_bc), ten_tp)
                    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as _f:
                        _f.write(_bytes)
                        _tmp_docx = _f.name
                    _tmp_pdf = _tmp_docx.replace(".docx", ".pdf")
                    try:
                        convert(_tmp_docx, _tmp_pdf)
                        st.session_state["_bc_td_pdf"] = open(_tmp_pdf, "rb").read()
                        ghi_audit(username, "xuat_bieu_cn",
                                  f"Xuất PDF tiến độ T{int(thang_bc)}/{int(nam_bc)}")
                    finally:
                        _os.unlink(_tmp_docx)
                        if _os.path.exists(_tmp_pdf):
                            _os.unlink(_tmp_pdf)
                except ImportError:
                    st.warning("⚠️ Cần cài đặt MS Word để xuất PDF. "
                               "Hãy tải file Word và tự chuyển đổi.")
                except Exception as _e:
                    st.warning(f"⚠️ Không thể xuất PDF: {_e}. "
                               "Hãy tải file Word để chuyển đổi thủ công.")
            if "_bc_td_pdf" in st.session_state:
                st.download_button(
                    "📥 Tải PDF tiến độ",
                    data=st.session_state["_bc_td_pdf"],
                    file_name=f"tien_do_t{int(thang_bc)}_{int(nam_bc)}.pdf",
                    mime="application/pdf",
                    key="bc_dl_td_pdf",
                    use_container_width=True,
                )
        else:
            st.button("🖨️ Xuất PDF", disabled=True, key="bc_btn_td_pdf_dis",
                      use_container_width=True)
    if not ds:
        st.caption("⚠️ Chưa có dữ liệu phân công. Vào tab Phân công để thêm.")

    st.divider()

    # ── Phần 3: Excel ──
    st.markdown("**📋 3. Xuất Excel danh sách phân công**")
    if ds:
        _uu_map = {"khan_cap": "Khẩn cấp", "quan_trong": "Quan trọng", "binh_thuong": "Bình thường"}
        _tt_map = {"chua_lam": "Chưa làm", "dang_lam": "Đang làm",
                   "hoan_thanh": "Hoàn thành", "tre_han": "Trễ hạn"}
        _df_xls = pd.DataFrame([{
            "Tiêu đề": c.get("tieu_de", ""),
            "Nhóm": c.get("nhom", ""),
            "Người TH": c.get("nguoi_thuc_hien", ""),
            "Mức độ": _uu_map.get(c.get("uu_tien", ""), ""),
            "Ngày giao": c.get("ngay_giao", ""),
            "Thời gian hoàn thành": c.get("ngay_deadline", ""),
            "Trạng thái": _tt_map.get(c.get("trang_thai", ""), ""),
            "Ghi chú": c.get("ghi_chu_ket_qua", ""),
        } for c in ds])
        _xl_bytes = xuat_excel({"Phân công": _df_xls})
        st.download_button(
            "📥 Tải Excel phân công",
            data=_xl_bytes,
            file_name="phan_cong_khnv.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="bc_excel_dl",
            use_container_width=True,
        )
        ghi_audit(username, "xuat_bieu_cn", "Xuất Excel phân công Phòng KH-NV")
    else:
        st.button("📥 Tải Excel phân công", disabled=True,
                  key="bc_excel_dis", use_container_width=True)
        st.caption("⚠️ Chưa có dữ liệu phân công. Vào tab Phân công để thêm.")



# ──────────────────────────────────────────────
# TAB 5: 📅 Lịch công tác
# ──────────────────────────────────────────────

_LICH_BAN_CHIP = {  # (bg, fg, border-left) theo loại × trạng thái
    "sap_dien_ra": {
        "hop":      ("#dbeafe", "#1e40af", "#3b82f6"),
        "kiem_tra": ("#fef9c3", "#854d0e", "#eab308"),
        "cong_tac": ("#dcfce7", "#14532d", "#22c55e"),
        "tap_huan": ("#ede9fe", "#4c1d95", "#8b5cf6"),
        "khac":     ("#f1f5f9", "#334155", "#94a3b8"),
    },
    "da_hoan_thanh": ("#f0fdf4", "#6b7280", "#86efac"),
    "huy_bo":        ("#fef2f2", "#9ca3af", "#fca5a5"),
}
_LOAI_ICON = {
    "hop": "🗓️", "kiem_tra": "🔍", "cong_tac": "✈️", "tap_huan": "🎓", "khac": "📌",
}
_DAYS_VN = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]


def _html_lich_ban(ds_loc: list, thang: int, nam: int) -> str:
    """Tạo HTML lưới lịch bàn 7 cột (T2→CN) cho tháng/năm chỉ định.

    Mỗi ô ngày hiển thị chip sự kiện màu theo loại. Hôm nay highlight vàng.
    Dùng inline CSS hoàn toàn (không inject style block).
    """
    # Index sự kiện theo ngày trong tháng
    ev_by_day: dict[int, list] = defaultdict(list)
    for ev in ds_loc:
        try:
            ev_by_day[date.fromisoformat(ev["ngay"]).day].append(ev)
        except (ValueError, KeyError):
            pass

    today = date.today()
    today_day = today.day if (today.month == thang and today.year == nam) else -1

    # Header hàng thứ
    header = "".join(
        f'<th style="background:rgba(30,58,95,0.85);color:#e2e8f0;padding:10px 4px;'
        f'text-align:center;font-size:0.8rem;font-weight:600;'
        f'border:1px solid rgba(255,255,255,0.08)">{d}</th>'
        for d in _DAYS_VN
    )

    rows_html = ""
    for week in calendar.monthcalendar(nam, thang):
        cells = ""
        for day_num in week:
            if day_num == 0:
                cells += (
                    '<td style="background:rgba(0,0,0,0.03);'
                    'border:1px solid rgba(128,128,128,0.12);'
                    'min-width:100px;min-height:90px;width:14.28%"></td>'
                )
                continue

            is_today = (day_num == today_day)
            bg_cell = "rgba(251,191,36,0.12)" if is_today else "transparent"
            bd_top  = "3px solid #f59e0b" if is_today else "1px solid rgba(128,128,128,0.15)"
            if is_today:
                day_lbl = (
                    f'<div style="text-align:right;padding:3px 6px 4px 0">'
                    f'<span style="display:inline-flex;align-items:center;'
                    f'justify-content:center;width:26px;height:26px;border-radius:50%;'
                    f'background:#f59e0b;color:#fff;font-size:0.82rem;font-weight:700">'
                    f'{day_num}</span></div>'
                )
            else:
                day_lbl = (
                    f'<div style="font-size:0.82rem;font-weight:500;'
                    f'text-align:right;padding:3px 6px 4px 0;opacity:0.7">{day_num}</div>'
                )

            evs = ev_by_day.get(day_num, [])
            MAX_CHIPS = 3
            chips = ""
            for ev in evs[:MAX_CHIPS]:
                loai = ev.get("loai", "khac")
                tt   = ev.get("trang_thai", "sap_dien_ra")
                tieu_de_raw = ev.get("tieu_de", "") or ""
                short = tieu_de_raw[:18] + ("…" if len(tieu_de_raw) > 18 else "")
                icon  = _LOAI_ICON.get(loai, "📌")

                if tt in ("da_hoan_thanh", "huy_bo"):
                    bg_c, fg_c, bd_c = _LICH_BAN_CHIP[tt]
                else:
                    palette = _LICH_BAN_CHIP["sap_dien_ra"]
                    bg_c, fg_c, bd_c = palette.get(loai, palette["khac"])

                opacity  = "opacity:0.75;" if tt != "sap_dien_ra" else ""
                strike   = "text-decoration:line-through;" if tt == "huy_bo" else ""
                full_esc = tieu_de_raw.replace('"', "&quot;")
                chips += (
                    f'<div title="{full_esc}" style="background:{bg_c};color:{fg_c};'
                    f'border-left:3px solid {bd_c};border-radius:3px;'
                    f'padding:1px 4px;margin:1px 0;font-size:0.72rem;'
                    f'line-height:1.4;overflow:hidden;white-space:nowrap;'
                    f'text-overflow:ellipsis;{opacity}{strike}">'
                    f'{icon} {short}</div>'
                )

            overflow = len(evs) - MAX_CHIPS
            if overflow > 0:
                chips += (
                    f'<div style="font-size:0.68rem;color:#6b7280;'
                    f'padding:1px 4px;font-style:italic">+{overflow} sự kiện</div>'
                )

            cells += (
                f'<td style="background:{bg_cell};border-top:{bd_top};'
                f'border-left:1px solid rgba(128,128,128,0.12);'
                f'border-right:1px solid rgba(128,128,128,0.12);'
                f'border-bottom:1px solid rgba(128,128,128,0.12);'
                f'vertical-align:top;padding:4px;'
                f'min-width:100px;min-height:90px;width:14.28%">'
                f'{day_lbl}{chips}</td>'
            )
        rows_html += f"<tr>{cells}</tr>\n"

    return (
        '<div style="overflow-x:auto;margin:8px 0 16px 0">'
        '<table style="border-collapse:collapse;width:100%;'
        "font-family:'Inter','Segoe UI',sans-serif;table-layout:fixed\">"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table></div>"
    )


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
        _ghi_ds(KHNV_LICH, ds, username, "khnv_tu_dong_cap_nhat_lich",
                "Tự động cập nhật trạng thái lịch đã qua")

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

    # ── Bộ lọc ──
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        thang_loc = st.selectbox("Tháng", list(range(1, 13)), index=today.month - 1, key="lich_thang")
    with col_f2:
        nam_loc = st.selectbox("Năm", list(range(today.year - 2, today.year + 3)), index=2, key="lich_nam")
    loai_loc = st.selectbox("Loại", ["Tất cả"] + list(LOAI_LICH.keys()),
                            format_func=lambda x: "Tất cả" if x == "Tất cả" else LOAI_LICH[x],
                            key="lich_loai")

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

    # ── Xuất PDF ──
    col_pdf, _ = st.columns([1, 5])
    with col_pdf:
        if ds_loc:
            _loai_map = {
                k: v.replace("🗓️ ", "").replace("🔍 ", "").replace("✈️ ", "")
                    .replace("🎓 ", "").replace("📌 ", "")
                for k, v in LOAI_LICH.items()
            }
            _tt_lich = {"sap_dien_ra": "Sắp diễn ra", "da_hoan_thanh": "Đã hoàn thành", "huy_bo": "Hủy bỏ"}
            _df_lich = pd.DataFrame([{
                "Ngày": e.get("ngay", ""),
                "Loại": _loai_map.get(e.get("loai", ""), e.get("loai", "")),
                "Tiêu đề": e.get("tieu_de", ""),
                "Địa điểm": e.get("dia_diem", ""),
                "Thành viên": e.get("thanh_vien", ""),
                "Ghi chú": e.get("ghi_chu", ""),
                "Trạng thái": _tt_lich.get(e.get("trang_thai", ""), e.get("trang_thai", "")),
            } for e in ds_loc])
            _pdf_bytes = xuat_pdf_co_chart(
                _df_lich, "Lịch công tác Phòng KH-NV", username,
                them_dong_tong=False, cols_tien=None,
            )
            download_pdf_button(_pdf_bytes, "lich_cong_tac.pdf",
                                "📥 Xuất PDF", key="pdf_lich")
        else:
            st.button("📥 Xuất PDF", disabled=True, key="pdf_lich_dis",
                      use_container_width=True)

    # ── Chế độ xem ──
    view_mode = st.radio(
        "Chế độ xem",
        ["📅 Lịch bàn", "📋 Danh sách"],
        horizontal=True,
        key="lich_view_mode",
    )

    st.markdown("### 📅 Lịch công tác trong tháng")

    if view_mode == "📅 Lịch bàn":
        # Luôn hiển thị lưới lịch bàn, dù có hay không có sự kiện
        st.markdown(_html_lich_ban(ds_loc, thang_loc, nam_loc), unsafe_allow_html=True)
        
        # Thông báo hướng dẫn nếu chưa có sự kiện
        if not ds_loc:
            st.info("ℹ️ Chưa có sự kiện nào trong tháng này. Click '➕ Thêm sự kiện' ở trên để tạo lịch mới.")
        
        return  # bỏ qua for loop danh sách bên dưới

    # ── Chế độ Danh sách ──
    if not ds_loc:
        if not ds:
            st.info("ℹ️ Chưa có lịch công tác nào. Dùng '➕ Thêm sự kiện' ở trên để tạo lịch mới.")
        else:
            st.info("ℹ️ Không có sự kiện trong tháng này.")
        return

    for ev in ds_loc:
        try:
            ev_date = date.fromisoformat(ev["ngay"])
        except (ValueError, KeyError):
            ev_date = None

        is_current_week = False
        if ev_date:
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            is_current_week = start_week <= ev_date <= end_week

        bg = "rgba(59,130,246,0.08);" if is_current_week else ""
        st.markdown(
            f"<div style='background-color:{bg} padding:8px; border-radius:4px; margin-bottom:4px;'>",
            unsafe_allow_html=True,
        )

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
                new_loai = st.selectbox(
                    "Loại", list(LOAI_LICH.keys()),
                    index=list(LOAI_LICH.keys()).index(ev.get("loai", "khac")) if ev.get("loai") in LOAI_LICH else 0,
                    key=f"ll_{ev['id']}",
                    format_func=lambda x: LOAI_LICH[x],
                )
                new_ngay = st.date_input(
                    "Ngày",
                    value=date.fromisoformat(ev["ngay"]) if ev.get("ngay") else today,
                    key=f"ln_{ev['id']}",
                    format="DD/MM/YYYY",
                )
                new_dia_diem   = st.text_input("Địa điểm", value=ev.get("dia_diem", ""), key=f"ld_{ev['id']}")
                new_thanh_vien = st.text_area("Thành viên", value=ev.get("thanh_vien", ""), key=f"ltv_{ev['id']}")
                new_ghi_chu    = st.text_area("Ghi chú", value=ev.get("ghi_chu", ""), key=f"lg_{ev['id']}")
                new_trang_thai = st.selectbox(
                    "Trạng thái",
                    ["sap_dien_ra", "da_hoan_thanh", "huy_bo"],
                    index=["sap_dien_ra", "da_hoan_thanh", "huy_bo"].index(ev.get("trang_thai", "sap_dien_ra")),
                    key=f"ltt_{ev['id']}",
                    format_func=lambda x: {
                        "sap_dien_ra": "🟡 Sắp diễn ra",
                        "da_hoan_thanh": "✅ Đã hoàn thành",
                        "huy_bo": "❌ Hủy bỏ",
                    }.get(x, x),
                )
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    if st.button("💾 Lưu", key=f"save_lich_{ev['id']}"):
                        if new_tieu_de.strip():
                            ev["tieu_de"]     = new_tieu_de.strip()
                            ev["loai"]        = new_loai
                            ev["ngay"]        = new_ngay.isoformat()
                            ev["dia_diem"]    = new_dia_diem.strip()
                            ev["thanh_vien"]  = new_thanh_vien.strip()
                            ev["ghi_chu"]     = new_ghi_chu.strip()
                            ev["trang_thai"]  = new_trang_thai
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
# TAB 6: 📖 Thông tin đầu việc (tham chiếu tĩnh)
# ──────────────────────────────────────────────


def _render_thong_tin_dau_viec() -> None:
    """Bảng tham chiếu tĩnh: đầu việc Trưởng phòng TP01–TP17 + 38 việc cấp dưới."""

    # ── Phần 1: Đầu việc Trưởng phòng ──
    st.markdown(
        "<h2 style='color:#e2e8f0;margin-bottom:4px'>📌 Bảng đầu việc của Trưởng phòng KH-NVTD</h2>",
        unsafe_allow_html=True,
    )
    st.caption("17 đầu việc chính (TP01–TP17) — chỉ đọc, dùng để tra cứu và tham chiếu")

    rows_tp = ""
    for t in _MAU_GIAO_VIEC_TP:
        rows_tp += (
            f"<tr style='border-bottom:1px solid #334155'>"
            f"<td style='padding:10px 12px;white-space:nowrap;font-weight:700;color:#fbbf24;font-size:0.95rem'>{t['ma']}</td>"
            f"<td style='padding:10px 12px;font-weight:600;color:#f1f5f9;font-size:0.95rem'>{t['tieu_de']}</td>"
            f"<td style='padding:10px 12px;color:#cbd5e1;font-size:0.9rem;line-height:1.5'>{t['mo_ta']}</td>"
            f"<td style='padding:10px 12px;white-space:nowrap;color:#d1d5db;font-weight:600;font-size:0.9rem'>{t['tan_suat']}</td>"
            f"</tr>"
        )
    st.markdown(
        f"""<div style="overflow-x:auto;margin-bottom:28px">
        <table style="width:100%;border-collapse:collapse;font-size:0.92rem">
          <thead>
            <tr style="background:linear-gradient(135deg,#334155,#475569);color:white">
              <th style="padding:12px 12px;text-align:left;white-space:nowrap;font-size:0.95rem">Mã</th>
              <th style="padding:12px 12px;text-align:left;font-size:0.95rem">Đầu việc</th>
              <th style="padding:12px 12px;text-align:left;font-size:0.95rem">Mô tả chi tiết</th>
              <th style="padding:12px 12px;text-align:left;font-size:0.95rem">Tần suất</th>
            </tr>
          </thead>
          <tbody>{rows_tp}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Phần 2: Bảng giao việc cấp dưới (38 việc) ──
    st.markdown(
        "<h2 style='color:#e2e8f0;margin-bottom:4px'>📋 Bảng giao việc cấp dưới "
        "<span style='font-size:0.9rem;font-weight:400;color:#94a3b8'>(38 đầu việc nhóm I–VIII)</span></h2>",
        unsafe_allow_html=True,
    )
    st.caption("Phó phòng VT1, VT2 và Cán bộ TD tại Hội sở")

    nhom_groups: dict = {}
    for idx, t in enumerate(_MAU_GIAO_VIEC, start=1):
        nh = t.get("nhom", "")
        nhom_groups.setdefault(nh, []).append((idx, t))

    for nhom_name, items in dict(sorted(nhom_groups.items())).items():
        nhom_stt = nhom_name.split(".")[0] if "." in nhom_name else ""
        st.markdown(
            f"<h3 style='color:#cbd5e1;margin:20px 0 8px 0;font-size:1.05rem'>"
            f"<span style='display:inline-block;background:#2563eb;color:white;"
            f"border-radius:6px;padding:2px 12px;margin-right:8px;font-size:0.9rem'>"
            f"{nhom_stt}</span> {nhom_name.split('. ', 1)[1] if '. ' in nhom_name else nhom_name}</h3>",
            unsafe_allow_html=True,
        )
        rows = ""
        for stt, t in items:
            mo = t.get("mo_ta", "")
            parts = mo.split("·")
            thoi_han = parts[0].replace("⏱", "").strip() if len(parts) > 0 else ""
            san_pham = parts[1].replace("📄", "").strip() if len(parts) > 1 else ""
            rows += (
                f"<tr style='border-bottom:1px solid #334155'>"
                f"<td style='padding:8px 10px;text-align:center;color:#94a3b8;width:44px;font-size:0.88rem'>{stt}</td>"
                f"<td style='padding:8px 10px;font-weight:500;color:#f1f5f9;font-size:0.93rem;line-height:1.5'>{t['tieu_de']}</td>"
                f"<td style='padding:8px 10px;white-space:nowrap;color:#fbbf24;font-weight:600;font-size:0.88rem'>{t['nguoi_thuc_hien']}</td>"
                f"<td style='padding:8px 10px;white-space:nowrap;color:#fca5a5;font-size:0.88rem'>{thoi_han}</td>"
                f"<td style='padding:8px 10px;color:#6ee7b7;font-weight:500;font-size:0.88rem;line-height:1.4'>{san_pham}</td>"
                f"</tr>"
            )
        st.markdown(
            f"""<div style="overflow-x:auto;margin-bottom:24px;border-radius:10px;border:1px solid #334155;padding:2px">
            <table style="width:100%;border-collapse:collapse;font-size:0.92rem">
              <thead>
                <tr style="background:#1e293b;border-bottom:2px solid #475569">
                  <th style="padding:10px 10px;width:44px;text-align:center;font-size:0.9rem;color:#e2e8f0">STT</th>
                  <th style="padding:10px 10px;text-align:left;font-size:0.9rem;color:#e2e8f0">Đầu việc</th>
                  <th style="padding:10px 10px;text-align:left;font-size:0.9rem;color:#e2e8f0">Người thực hiện</th>
                  <th style="padding:10px 10px;text-align:left;font-size:0.9rem;color:#e2e8f0">Thời hạn</th>
                  <th style="padding:10px 10px;text-align:left;font-size:0.9rem;color:#e2e8f0">Sản phẩm</th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
            </table></div>""",
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────
# RENDER CHÍNH — 6 tab
# ──────────────────────────────────────────────


def render(tab=None, **kwargs):
    from components.export_pdf import xuat_pdf_co_chart, download_pdf_button
    """6 sub-tab theo luồng: Nhân sự → Phân công → Tiến độ → Báo cáo → Lịch → Thông tin.

    Chỉ khả dụng cho phòng KH-NV (admin_cn, manager_cn, executive).
    """
    ctx = get_tab_context(tab)
    role_n = normalize_role(str(kwargs.get("role", "user")))
    username = kwargs.get("username", "unknown")

    if role_n in ("user", "manager_pgd", "admin_pgd"):
        with ctx:
            st.warning("⚠️ Tab này chỉ dành cho phòng KH-NV.")
        return

    with ctx:
        t1, t2, t3, t4, t5, t6 = st.tabs([
            "👥 Nhân sự & Chức vụ",
            "📋 Phân công công việc",
            "📊 Tiến độ / Chỉnh sửa",
            "📄 In báo cáo",
            "📅 Lịch công tác",
            "📖 Thông tin đầu việc",
        ])
        with t1:
            _render_nhan_su(role_n, username)
        with t2:
            _render_phan_cong_v2(role_n, username)
        with t3:
            _render_tien_do_edit(role_n, username)
        with t4:
            _kw = dict(kwargs)
            _kw.pop("username", None)
            _kw.pop("role", None)
            _render_bao_cao(role_n, username, **_kw)
        with t5:
            _render_lich_cong_tac(t5, role_n, username)
        with t6:
            _render_thong_tin_dau_viec()
