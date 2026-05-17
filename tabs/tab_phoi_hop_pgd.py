"""Tab Công tác phối hợp với PGD — Ghi nhận và theo dõi các công việc CN giao / hỗ trợ PGD."""
from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

import db
from auth import normalize_role, la_phan_he_cn
from config import DS_PGD, DON_VI_CHI_NHANH, ROLES_PHAN_HE_CN
from utils import fmt_ngay

DS_PGD_ALL = [DON_VI_CHI_NHANH] + DS_PGD

TRANG_THAI = {
    "cho_xu_ly":      "⏳ Chờ xử lý",
    "dang_thuc_hien": "🔄 Đang thực hiện",
    "hoan_thanh":     "✅ Hoàn thành",
    "huy":            "❌ Hủy",
}
LOAI_PHOI_HOP = {
    "ho_so":    "📁 Hồ sơ / Thủ tục",
    "chi_tieu": "🎯 Chỉ tiêu / Kế hoạch",
    "bao_cao":  "📄 Báo cáo",
    "kiem_tra": "🔍 Kiểm tra / Hướng dẫn",
    "hop":      "👥 Họp / Trao đổi",
    "khac":     "📌 Khác",
}
UU_TIEN = {
    "khan_cap":    "🔴 Khẩn cấp",
    "quan_trong":  "🟡 Quan trọng",
    "binh_thuong": "🟢 Bình thường",
}
KV_KEY = "phoi_hop_list"


def _doc_ds() -> list[dict]:
    raw = db.doc_kv(KV_KEY)
    if not raw:
        return []
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []


def _luu_ds(ds: list[dict], username: str) -> None:
    db.ghi_kv(KV_KEY, json.dumps(ds, ensure_ascii=False), username)


def _id_moi(ds: list[dict]) -> int:
    return max((x.get("id", 0) for x in ds), default=0) + 1


def _render_tao_moi(username: str) -> None:
    st.subheader("➕ Tạo phiếu phối hợp mới")
    with st.form("phoi_hop_tao_moi", clear_on_submit=False):
        tieu_de = st.text_area("Nội dung công việc *", height=72,
                               placeholder="VD: Đôn đốc nộp báo cáo NQH tháng 5")

        c1, c2 = st.columns(2)
        with c1:
            loai = st.selectbox("Loại", list(LOAI_PHOI_HOP.keys()),
                                format_func=lambda x: LOAI_PHOI_HOP[x],
                                key="ph_loai")
            uu_tien = st.selectbox("Ưu tiên", list(UU_TIEN.keys()),
                                   format_func=lambda x: UU_TIEN[x],
                                   index=2, key="ph_uu_tien")
            nguoi_phu_trach = st.text_input("Cán bộ phụ trách (CN)",
                                            placeholder="Họ tên cán bộ theo dõi",
                                            key="ph_cb_pt")
        with c2:
            ngay_giao = st.date_input("Ngày giao", value=date.today(), key="ph_ngay_giao")
            ngay_ket_thuc = st.date_input("Ngày kết thúc", value=date.today(), key="ph_ngay_kt")

        st.markdown("**Đơn vị PGD liên quan**")
        _cc1, _cc2, _cc3 = st.columns(3)
        pgd_chon = []
        for _i, _pgd in enumerate(DS_PGD_ALL):
            with [_cc1, _cc2, _cc3][_i % 3]:
                if st.checkbox(_pgd, value=False, key=f"ph_pgd_{_i}"):
                    pgd_chon.append(_pgd)

        _so_chon = len(pgd_chon)
        if _so_chon == 0:
            st.caption("⚠️ Chưa chọn đơn vị nào — áp dụng cho tất cả 22 đơn vị")
        else:
            st.caption(f"✅ **{_so_chon}** đơn vị được chọn")

        noi_dung = st.text_area("Ghi chú / Nội dung chi tiết", height=80, key="ph_noi_dung")
        submitted = st.form_submit_button("💾 Tạo phiếu", type="primary")

    if submitted:
        if not str(tieu_de or "").strip():
            st.error("Vui lòng nhập nội dung công việc.")
            return
        ds = _doc_ds()
        item = {
            "id":             _id_moi(ds),
            "tieu_de":        tieu_de.strip(),
            "loai":           loai,
            "uu_tien":        uu_tien,
            "ds_pgd":         pgd_chon or DS_PGD_ALL,
            "ngay_giao":      ngay_giao.isoformat(),
            "ngay_ket_thuc":  ngay_ket_thuc.isoformat(),
            "trang_thai":     "cho_xu_ly",
            "noi_dung":       noi_dung.strip() or None,
            "nguoi_phu_trach": nguoi_phu_trach.strip() or None,
            "nguoi_tao":      username,
            "ngay_tao":       datetime.now().isoformat(),
        }
        ds.append(item)
        _luu_ds(ds, username)
        db.ghi_audit(username, "phoi_hop_tao",
                     f"ID={item['id']} · '{item['tieu_de']}' · "
                     f"{len(item['ds_pgd'])} PGD · hạn={ngay_ket_thuc}")
        st.toast(f"✅ Đã tạo: {item['tieu_de']}")
        st.rerun()


def _render_danh_sach(username: str, role_n: str, pgd_user: str = "") -> None:
    ds = _doc_ds()
    if not ds:
        st.info("Chưa có phiếu phối hợp nào.")
        return

    # Lọc theo PGD role
    if pgd_user and role_n not in ROLES_PHAN_HE_CN:
        ds = [x for x in ds if pgd_user in x.get("ds_pgd", [])]

    c1, c2, c3 = st.columns(3)
    with c1:
        loc_tt = st.selectbox("Trạng thái", ["Tất cả"] + list(TRANG_THAI.values()),
                              key="ph_loc_tt")
    with c2:
        loc_loai = st.selectbox("Loại", ["Tất cả"] + list(LOAI_PHOI_HOP.values()),
                                key="ph_loc_loai")
    with c3:
        if role_n in ROLES_PHAN_HE_CN:
            loc_pgd = st.selectbox("Đơn vị", ["Tất cả"] + DS_PGD_ALL, key="ph_loc_pgd")
        else:
            loc_pgd = pgd_user

    if loc_tt != "Tất cả":
        tt_key = next((k for k, v in TRANG_THAI.items() if v == loc_tt), None)
        ds = [x for x in ds if x.get("trang_thai") == tt_key]
    if loc_loai != "Tất cả":
        loai_key = next((k for k, v in LOAI_PHOI_HOP.items() if v == loc_loai), None)
        ds = [x for x in ds if x.get("loai") == loai_key]
    if loc_pgd and loc_pgd != "Tất cả":
        ds = [x for x in ds if loc_pgd in x.get("ds_pgd", [])]

    if not ds:
        st.info("Không có phiếu nào phù hợp.")
        return

    # Metrics
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Tổng phiếu", len(ds))
    mc2.metric("⏳ Chờ xử lý",      sum(1 for x in ds if x.get("trang_thai") == "cho_xu_ly"))
    mc3.metric("🔄 Đang thực hiện", sum(1 for x in ds if x.get("trang_thai") == "dang_thuc_hien"))
    mc4.metric("✅ Hoàn thành",     sum(1 for x in ds if x.get("trang_thai") == "hoan_thanh"))

    st.divider()

    hom_nay = date.today().isoformat()
    for item in sorted(ds, key=lambda x: x.get("ngay_ket_thuc", ""), reverse=True):
        tt = item.get("trang_thai", "cho_xu_ly")
        tt_label = TRANG_THAI.get(tt, tt)
        loai_label = LOAI_PHOI_HOP.get(item.get("loai", ""), "")
        uu_label = UU_TIEN.get(item.get("uu_tien", ""), "")
        ds_pgd = item.get("ds_pgd", [])
        han = item.get("ngay_ket_thuc", "")
        qua_han = (tt not in ("hoan_thanh", "huy")) and han < hom_nay

        with st.container(border=True):
            r1, r2 = st.columns([6, 2])
            with r1:
                st.markdown(
                    f"**#{item['id']} · {item['tieu_de']}**  "
                    f"{'🔴 Quá hạn' if qua_han else ''}"
                )
                st.caption(
                    f"{loai_label} · {uu_label} · "
                    f"Giao: {fmt_ngay(item.get('ngay_giao'))} → "
                    f"Hạn: **{fmt_ngay(han)}** · "
                    + (f"CB phụ trách: {item['nguoi_phu_trach']} · " if item.get("nguoi_phu_trach") else "")
                    + f"{len(ds_pgd)} đơn vị · Tạo bởi: {item.get('nguoi_tao','')}"
                )
                if item.get("noi_dung"):
                    st.caption(f"📝 {item['noi_dung']}")
                # Danh sách PGD
                st.caption("🏢 " + " · ".join(ds_pgd) if len(ds_pgd) <= 8
                           else f"🏢 {', '.join(ds_pgd[:6])} ... (+{len(ds_pgd)-6})")
            with r2:
                st.markdown(f"**{tt_label}**")
                if role_n in ROLES_PHAN_HE_CN:
                    new_tt = st.selectbox(
                        "Đổi TT",
                        list(TRANG_THAI.keys()),
                        format_func=lambda x: TRANG_THAI[x],
                        index=list(TRANG_THAI.keys()).index(tt),
                        key=f"ph_tt_{item['id']}",
                        label_visibility="collapsed",
                    )
                    if st.button("Lưu", key=f"ph_save_{item['id']}", width="stretch"):
                        full_ds = _doc_ds()
                        for x in full_ds:
                            if x["id"] == item["id"]:
                                x["trang_thai"] = new_tt
                                break
                        _luu_ds(full_ds, username)
                        db.ghi_audit(username, "phoi_hop_cap_nhat_tt",
                                     f"ID={item['id']} → {new_tt}")
                        st.toast("✅ Đã cập nhật trạng thái.")
                        st.rerun()


def _render_chinh_sua(username: str) -> None:
    ds = _doc_ds()
    if not ds:
        st.info("Chưa có phiếu nào.")
        return

    id_map = {x["id"]: x for x in ds}
    sel_id = st.selectbox(
        "Chọn phiếu",
        options=list(id_map.keys()),
        format_func=lambda x: f"#{x} · {id_map[x]['tieu_de'][:60]} · {TRANG_THAI.get(id_map[x].get('trang_thai',''),'')}"
    )
    item = id_map.get(sel_id)
    if not item:
        return

    with st.form(f"ph_sua_{sel_id}"):
        tieu_de = st.text_area("Nội dung *", value=item.get("tieu_de", ""), height=72)
        c1, c2 = st.columns(2)
        with c1:
            loai_keys = list(LOAI_PHOI_HOP.keys())
            loai = st.selectbox("Loại", loai_keys,
                                format_func=lambda x: LOAI_PHOI_HOP[x],
                                index=loai_keys.index(item.get("loai", loai_keys[0]))
                                if item.get("loai") in loai_keys else 0)
            uu_keys = list(UU_TIEN.keys())
            uu_tien = st.selectbox("Ưu tiên", uu_keys,
                                   format_func=lambda x: UU_TIEN[x],
                                   index=uu_keys.index(item.get("uu_tien", "binh_thuong"))
                                   if item.get("uu_tien") in uu_keys else 2)
            nguoi_phu_trach = st.text_input("CB phụ trách",
                                            value=item.get("nguoi_phu_trach") or "")
            tt_keys = list(TRANG_THAI.keys())
            trang_thai = st.selectbox("Trạng thái", tt_keys,
                                      format_func=lambda x: TRANG_THAI[x],
                                      index=tt_keys.index(item.get("trang_thai", "cho_xu_ly"))
                                      if item.get("trang_thai") in tt_keys else 0)
        with c2:
            try:
                ngay_giao_def = date.fromisoformat(item.get("ngay_giao") or date.today().isoformat())
            except Exception:
                ngay_giao_def = date.today()
            try:
                ngay_kt_def = date.fromisoformat(item.get("ngay_ket_thuc") or date.today().isoformat())
            except Exception:
                ngay_kt_def = date.today()
            ngay_giao = st.date_input("Ngày giao", value=ngay_giao_def)
            ngay_ket_thuc = st.date_input("Ngày kết thúc", value=ngay_kt_def)
        noi_dung = st.text_area("Ghi chú", value=item.get("noi_dung") or "", height=80)
        submitted = st.form_submit_button("💾 Lưu thay đổi", type="primary")

    if submitted:
        if not str(tieu_de or "").strip():
            st.error("Vui lòng nhập nội dung.")
            return
        full_ds = _doc_ds()
        for x in full_ds:
            if x["id"] == sel_id:
                x.update({
                    "tieu_de":        tieu_de.strip(),
                    "loai":           loai,
                    "uu_tien":        uu_tien,
                    "ngay_giao":      ngay_giao.isoformat(),
                    "ngay_ket_thuc":  ngay_ket_thuc.isoformat(),
                    "trang_thai":     trang_thai,
                    "noi_dung":       noi_dung.strip() or None,
                    "nguoi_phu_trach": nguoi_phu_trach.strip() or None,
                })
                break
        _luu_ds(full_ds, username)
        db.ghi_audit(username, "phoi_hop_sua",
                     f"ID={sel_id} · '{tieu_de.strip()}' → {trang_thai}")
        st.toast("✅ Đã lưu thay đổi.")
        st.rerun()

    st.divider()
    if st.button("🗑️ Xóa phiếu này", key=f"ph_xoa_{sel_id}"):
        st.session_state[f"_ph_xoa_confirm_{sel_id}"] = True
        st.rerun()
    if st.session_state.get(f"_ph_xoa_confirm_{sel_id}"):
        st.warning("⚠️ Hành động này không thể hoàn tác.")
        if st.button("Xác nhận xóa", type="primary", key=f"ph_xoa_ok_{sel_id}"):
            full_ds = [x for x in _doc_ds() if x["id"] != sel_id]
            _luu_ds(full_ds, username)
            db.ghi_audit(username, "phoi_hop_xoa", f"ID={sel_id}")
            st.session_state.pop(f"_ph_xoa_confirm_{sel_id}", None)
            st.toast("🗑️ Đã xóa phiếu.")
            st.rerun()


def render(tab=None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role_n   = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user") or ""

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🤝 Công tác phối hợp với PGD")

        can_manage = role_n in ROLES_PHAN_HE_CN and role_n != "executive"

        if can_manage:
            t1, t2, t3 = st.tabs([
                "📋 Danh sách phối hợp",
                "➕ Tạo phiếu mới",
                "✏️ Chỉnh sửa / Xóa",
            ])
            with t1:
                _render_danh_sach(username, role_n, pgd_user)
            with t2:
                _render_tao_moi(username)
            with t3:
                _render_chinh_sua(username)
        else:
            _render_danh_sach(username, role_n, pgd_user)
