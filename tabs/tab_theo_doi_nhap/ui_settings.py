"""Cài đặt cấu hình Google Sheet & Quản lý Template."""
from __future__ import annotations

from datetime import date as _date

import streamlit as st

import db
from logger import get_logger
from services.template_manager import (
    doc_ds_template,
    luu_template,
    xoa_template,
    ten_da_ton_tai,
    clone_template,
    ap_dung_template,
    goi_y_template,
)
from services.template_detection_service import phat_hien_cau_truc

from .constants import DEFAULT_CT, LOAI_OPTIONS
from .data import (
    doc_ds_sheet,
    luu_ds_sheet,
    sheet_moi,
    doc_sheet,
    ket_noi_gsheet,
)

logger = get_logger(__name__)


def _render_form_sheet(cfg: dict, prefix: str) -> dict:
    """Form nhập 1 sheet config, trả về dict đã cập nhật."""
    ten = st.text_input(
        "Tên hiển thị", value=cfg.get("ten_hien_thi", ""),
        key=f"{prefix}_ten",
        help="VD: HSSV Lần 2 - 2026",
    )
    sid = st.text_input(
        "Google Sheet ID", value=cfg.get("sheet_id", ""),
        key=f"{prefix}_sid",
        help="Lấy từ URL: docs.google.com/spreadsheets/d/**[ID]**/edit",
    )
    tab = st.text_input(
        "Tên worksheet (tab)", value=cfg.get("sheet_tab", ""),
        key=f"{prefix}_tab",
        help="Tên đúng của tab trong Google Sheet (phân biệt HOA/thường, dấu)",
    )

    st.markdown("**Kiểu cấu trúc sheet**")
    loai_val = cfg.get("loai_cau_truc", "phan_cap_stt")
    loai_idx = (
        list(LOAI_OPTIONS.keys()).index(loai_val)
        if loai_val in LOAI_OPTIONS else 0
    )
    loai_chon = st.selectbox(
        "Kiểu cấu trúc",
        options=list(LOAI_OPTIONS.keys()),
        format_func=lambda k: LOAI_OPTIONS[k],
        index=loai_idx,
        key=f"{prefix}_loai",
    )

    st.markdown("**Cấu hình hàng & cột**")
    hr_col, nc_col = st.columns(2)
    with hr_col:
        hr = st.number_input(
            "Header row (hàng tên cột)", min_value=1, max_value=50,
            value=cfg.get("header_row", 10), key=f"{prefix}_hr",
            help="Hàng chứa tên các cột. Dữ liệu bắt đầu từ hàng tiếp theo",
        )
    with nc_col:
        nc = st.number_input(
            "Cột Tên đơn vị", min_value=1, max_value=30,
            value=cfg.get("name_col", 2), key=f"{prefix}_nc",
            help="Cột chứa tên PGD / tên xã phường",
        )

    if loai_chon == "phan_cap_stt":
        sc = st.number_input(
            "Cột STT (phân biệt PGD/xã)", min_value=1, max_value=30,
            value=cfg.get("stt_col", 1), key=f"{prefix}_sc",
            help="Cột STT: hàng PGD = chữ La Mã (I,II...), hàng xã = số (1,2...)",
        )
        pgd_col = cfg.get("pgd_col", 1)
    elif loai_chon == "cot_pgd":
        pgd_col = st.number_input(
            "Cột tên PGD", min_value=1, max_value=30,
            value=cfg.get("pgd_col", 1), key=f"{prefix}_pgd_col",
            help="Cột ghi tên PGD (lặp lại ở mỗi hàng)",
        )
        sc = cfg.get("stt_col", 1)
    else:
        sc = cfg.get("stt_col", 1)
        pgd_col = cfg.get("pgd_col", 1)

    st.markdown("**Cột cần theo dõi** (có thể thêm nhiều chương trình)")
    st.caption("Mỗi dòng = 1 chỉ tiêu cần theo dõi. Cột tính từ 1 (cột A=1, B=2, C=3...)")

    ds_ct_old = list(cfg.get("ds_chuong_trinh", list(DEFAULT_CT)))

    key_count = f"{prefix}_ct_count"
    if key_count not in st.session_state:
        st.session_state[key_count] = len(ds_ct_old)
    count = st.session_state[key_count]

    while len(ds_ct_old) < count:
        ds_ct_old.append({"ten": f"Chỉ tiêu {len(ds_ct_old)+1}", "col": 1})

    ds_ct_new = []
    for i in range(count):
        ct = ds_ct_old[i] if i < len(ds_ct_old) else {"ten": "", "col": 1}
        ca, cb, cc = st.columns([3, 1, 0.5])
        with ca:
            tn = st.text_input(
                "Tên chỉ tiêu", value=ct.get("ten", ""),
                key=f"{prefix}_ct{i}_ten",
                placeholder="VD: HSSV, Nước sạch, Việc làm...",
            )
        with cb:
            cl = st.number_input(
                "Cột số", min_value=1, max_value=100,
                value=ct.get("col", 1), key=f"{prefix}_ct{i}_col",
                help="A=1, B=2, C=3...",
            )
        with cc:
            st.write("")
            if count > 1 and st.button("✕", key=f"{prefix}_ct{i}_del",
                                        help="Xóa dòng này"):
                st.session_state[key_count] = max(1, count - 1)
                st.rerun()
        ds_ct_new.append({"ten": tn.strip(), "col": int(cl)})

    if st.button("➕ Thêm chỉ tiêu", key=f"{prefix}_ct_add"):
        st.session_state[key_count] = count + 1
        st.rerun()

    # ── Deadline field (⭐ MỚI) ───────────────────────────────────────────
    st.divider()
    st.markdown("**⏰ Hạn chót nhập liệu** (tùy chọn)")
    deadline_val = cfg.get("deadline", "")
    try:
        deadline_default = _date.fromisoformat(deadline_val) if deadline_val else None
    except (ValueError, TypeError):
        deadline_default = None

    deadline = st.date_input(
        "Hạn chót",
        value=deadline_default,
        key=f"{prefix}_deadline",
        format="DD/MM/YYYY",
    )

    return {
        "ten_hien_thi": ten.strip(),
        "sheet_id": sid.strip(),
        "sheet_tab": tab.strip(),
        "header_row": int(hr),
        "stt_col": int(sc),
        "name_col": int(nc),
        "pgd_col": int(pgd_col),
        "loai_cau_truc": loai_chon,
        "ds_chuong_trinh": ds_ct_new,
        "deadline": deadline.isoformat() if deadline else "",
    }


def _render_template_section(username: str) -> None:
    """UI quản lý template cấu hình Google Sheet."""

    templates = doc_ds_template()
    if templates:
        st.markdown(f"**{len(templates)} template đã lưu:**")
        for t in templates:
            tid = t["id"]
            mo_ta = t.get("mo_ta") or ""
            label = f"📁 {t['ten']}" + (f" — {mo_ta}" if mo_ta else "")
            with st.expander(label, expanded=False):
                new_ten = st.text_input(
                    "Tên template", value=t["ten"],
                    key=f"tpl_e_{tid}_ten",
                )
                new_mo_ta = st.text_input(
                    "Mô tả", value=mo_ta,
                    key=f"tpl_e_{tid}_mo_ta",
                )
                cl1, cl2, cl3 = st.columns(3)
                with cl1:
                    if st.button("💾 Lưu tên/mô tả", key=f"tpl_e_{tid}_save",
                                 use_container_width=True):
                        if not new_ten.strip():
                            st.error("❌ Cần nhập tên.")
                        elif ten_da_ton_tai(new_ten.strip(), exclude_id=tid):
                            st.error(f"❌ Tên '{new_ten.strip()}' đã tồn tại.")
                        else:
                            luu_template(
                                {**t, "ten": new_ten.strip(),
                                 "mo_ta": new_mo_ta.strip()}, username,
                            )
                            st.success("✅ Đã lưu")
                            st.rerun()
                with cl2:
                    if st.button("📋 Clone", key=f"tpl_clone_{tid}",
                                 use_container_width=True,
                                 help="Tạo bản copy"):
                        st.session_state[f"tpl_clone_{tid}_show"] = True
                with cl3:
                    if st.button("🗑 Xóa", key=f"tpl_del_{tid}",
                                 use_container_width=True):
                        xoa_template(tid, username)
                        st.success(f"Đã xóa: {t['ten']}")
                        st.rerun()

                if st.session_state.get(f"tpl_clone_{tid}_show"):
                    clone_ten = st.text_input(
                        "Tên bản clone",
                        value=f"{t['ten']} (copy)",
                        key=f"tpl_clone_{tid}_ten",
                    )
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("✅ Tạo clone", key=f"tpl_clone_{tid}_ok",
                                     type="primary", use_container_width=True):
                            if not clone_ten.strip():
                                st.error("❌ Cần nhập tên.")
                            elif ten_da_ton_tai(clone_ten.strip()):
                                st.error(f"❌ '{clone_ten.strip()}' đã tồn tại.")
                            else:
                                clone_template(tid, clone_ten.strip(), username)
                                st.session_state.pop(f"tpl_clone_{tid}_show", None)
                                st.success(f"✅ Đã tạo: {clone_ten.strip()}")
                                st.rerun()
                    with cc2:
                        if st.button("✕ Huỷ", key=f"tpl_clone_{tid}_cancel",
                                     use_container_width=True):
                            st.session_state.pop(f"tpl_clone_{tid}_show", None)
                            st.rerun()
        st.divider()

    # ── Tạo template mới từ file mẫu ───────────────────────────────────────
    st.markdown("**Tạo template từ file mẫu**")
    uploaded = st.file_uploader(
        "Upload file Excel/CSV mẫu",
        type=["xlsx", "xls", "csv"],
        key="tpl_upload",
        help="Upload 1 file mẫu để hệ thống tự detect cấu trúc header, cột",
    )

    if uploaded:
        if st.button("🔍 Phân tích cấu trúc", key="tpl_analyze"):
            try:
                with st.spinner("Đang phân tích..."):
                    result = phat_hien_cau_truc(uploaded.read(), uploaded.name)
                st.session_state["tpl_detect_result"] = result
                st.session_state.pop("tpl_ct_count", None)
            except Exception as e:
                logger.error(
                    "_render_template_section: phân tích file — %s",
                    e, exc_info=True,
                )
                st.error(f"❌ {e}")

    detect = st.session_state.get("tpl_detect_result")
    if not detect:
        if not templates:
            st.caption(
                "💡 Upload file Excel từ Phòng KH-NV "
                "rồi nhấn **Phân tích cấu trúc** để tạo template."
            )
        return

    all_headers = detect.get("all_headers", [])
    if all_headers:
        st.caption(
            "Headers phát hiện: "
            + " · ".join(f"[{i+1}] {h}" for i, h in enumerate(all_headers)
                         if h.strip())
        )

    st.markdown("**Xem lại & điều chỉnh cấu hình:**")
    col_a, col_b = st.columns(2)
    with col_a:
        hr = st.number_input(
            "Header row", min_value=1, max_value=50,
            value=detect["header_row"], key="tpl_hr",
            help="Hàng chứa tên cột (đếm từ 1)",
        )
        sc = st.number_input(
            "Cột STT", min_value=1, max_value=30,
            value=detect["stt_col"], key="tpl_sc",
        )
    with col_b:
        nc = st.number_input(
            "Cột Tên đơn vị", min_value=1, max_value=30,
            value=detect["name_col"], key="tpl_nc",
        )
        _LOAI_OPTS = {
            "phan_cap_stt": "📊 Phân cấp STT",
            "phang": "📋 Phẳng",
            "cot_pgd": "🗂 Cột PGD riêng",
        }
        loai_val = detect.get("loai_cau_truc", "phan_cap_stt")
        loai_idx = (
            list(_LOAI_OPTS.keys()).index(loai_val)
            if loai_val in _LOAI_OPTS else 0
        )
        loai = st.selectbox(
            "Kiểu cấu trúc", list(_LOAI_OPTS.keys()),
            format_func=lambda k: _LOAI_OPTS[k],
            index=loai_idx, key="tpl_loai",
        )

    st.markdown("**Cột cần theo dõi** (nhấn ✕ để bỏ bớt):")
    ds_ct_init = list(detect.get("ds_chuong_trinh", []))

    key_count = "tpl_ct_count"
    if key_count not in st.session_state:
        st.session_state[key_count] = len(ds_ct_init)
    count = st.session_state[key_count]
    while len(ds_ct_init) < count:
        ds_ct_init.append({"ten": f"Cột {len(ds_ct_init)+1}", "col": 1})

    ds_ct_new = []
    for i in range(count):
        ct = ds_ct_init[i] if i < len(ds_ct_init) else {"ten": "", "col": 1}
        ca, cb, cc = st.columns([3, 1, 0.5])
        with ca:
            tn = st.text_input(
                "Tên", value=ct.get("ten", ""),
                key=f"tpl_ct{i}_ten", label_visibility="collapsed",
            )
        with cb:
            cl = st.number_input(
                "Cột", min_value=1, max_value=100,
                value=ct.get("col", 1), key=f"tpl_ct{i}_col",
                label_visibility="collapsed",
            )
        with cc:
            st.write("")
            if count > 1 and st.button("✕", key=f"tpl_ct{i}_del"):
                st.session_state[key_count] = max(1, count - 1)
                st.rerun()
        if tn.strip():
            ds_ct_new.append({"ten": tn.strip(), "col": int(cl)})

    if st.button("➕ Thêm cột", key="tpl_ct_add"):
        st.session_state[key_count] = count + 1
        st.rerun()

    st.divider()
    tpl_ten = st.text_input(
        "Tên template *", key="tpl_ten",
        placeholder="VD: NQH - Phân tích nguyên nhân",
    )
    tpl_mo_ta = st.text_input(
        "Mô tả (tùy chọn)", key="tpl_mo_ta",
        placeholder="VD: Dùng cho sheet NQH từ 2024+",
    )

    if st.button("💾 Lưu Template", key="tpl_save", type="primary"):
        if not tpl_ten.strip():
            st.error("❌ Cần nhập tên template.")
        elif ten_da_ton_tai(tpl_ten.strip()):
            st.error(f"❌ Template '{tpl_ten.strip()}' đã tồn tại. Dùng tên khác.")
        elif not ds_ct_new:
            st.error("❌ Cần có ít nhất 1 cột theo dõi.")
        else:
            template = {
                "ten": tpl_ten.strip(),
                "mo_ta": tpl_mo_ta.strip(),
                "nguoi_tao": username,
                "ngay_tao": _date.today().isoformat(),
                "header_row": int(hr),
                "stt_col": int(sc),
                "name_col": int(nc),
                "loai_cau_truc": loai,
                "ds_chuong_trinh": ds_ct_new,
            }
            luu_template(template, username)
            st.session_state.pop("tpl_detect_result", None)
            st.session_state.pop("tpl_ct_count", None)
            st.success(f"✅ Đã lưu template: {tpl_ten.strip()}")
            st.rerun()


def render_cai_dat(ds_sheet: list[dict], username: str) -> None:
    with st.expander("📁 Quản lý Template", expanded=False):
        _render_template_section(username)

    st.divider()
    st.markdown("**Danh sách Google Sheet đang theo dõi**")

    if not ds_sheet:
        st.info("Chưa có sheet nào. Thêm mới bên dưới.")
    else:
        for i, cfg in enumerate(ds_sheet):
            ten = cfg.get("ten_hien_thi") or cfg.get("sheet_tab", f"Sheet {i+1}")
            with st.expander(f"📄 {ten}", expanded=False):
                new_cfg = _render_form_sheet(cfg, prefix=f"cd_{i}")

                col_t, col_s, col_d = st.columns([1, 1, 1])
                with col_t:
                    if st.button("🔌 Test", key=f"cd_{i}_test",
                                 use_container_width=True):
                        try:
                            with st.spinner("Kết nối..."):
                                rows = doc_sheet(
                                    new_cfg["sheet_id"],
                                    new_cfg["sheet_tab"],
                                    new_cfg["header_row"],
                                )
                            n = sum(
                                1 for r in rows
                                if any(str(c).strip() for c in r)
                            )
                            st.success(f"✅ OK — {n} hàng dữ liệu")
                        except Exception as e:
                            logger.error(
                                "_sub_cau_hinh doc_sheet: %s", e, exc_info=True,
                            )
                            st.error(f"❌ {e}")
                with col_s:
                    if st.button("💾 Lưu", key=f"cd_{i}_save", type="primary",
                                 use_container_width=True):
                        ds_sheet[i] = new_cfg
                        doc_sheet.clear()
                        luu_ds_sheet(ds_sheet, username)
                        st.success("✅ Đã lưu")
                        st.rerun()
                with col_d:
                    if st.button("🗑 Xóa", key=f"cd_{i}_del",
                                 use_container_width=True):
                        ds_sheet.pop(i)
                        luu_ds_sheet(ds_sheet, username)
                        st.success("✅ Đã xóa")
                        st.rerun()

                if st.button("📁 Lưu thành Template", key=f"cd_{i}_to_tpl",
                             use_container_width=True):
                    st.session_state[f"cd_mig_{i}"] = True

                if st.session_state.get(f"cd_mig_{i}"):
                    mig_ten = st.text_input(
                        "Tên template mới",
                        value=new_cfg.get("ten_hien_thi", ""),
                        key=f"cd_mig_{i}_ten",
                        placeholder="VD: NQH - Phân tích nguyên nhân",
                    )
                    cm1, cm2 = st.columns(2)
                    with cm1:
                        if st.button("✅ Lưu Template", key=f"cd_mig_{i}_ok",
                                     type="primary", use_container_width=True):
                            if not mig_ten.strip():
                                st.error("❌ Cần nhập tên.")
                            elif ten_da_ton_tai(mig_ten.strip()):
                                st.error(f"❌ '{mig_ten.strip()}' đã tồn tại.")
                            else:
                                luu_template({
                                    "ten": mig_ten.strip(),
                                    "mo_ta": (
                                        f"Tạo từ: {new_cfg.get('ten_hien_thi','')}"
                                    ),
                                    "nguoi_tao": username,
                                    "ngay_tao": _date.today().isoformat(),
                                    "header_row": new_cfg.get("header_row", 10),
                                    "stt_col": new_cfg.get("stt_col", 1),
                                    "name_col": new_cfg.get("name_col", 2),
                                    "pgd_col": new_cfg.get("pgd_col", 1),
                                    "loai_cau_truc": new_cfg.get(
                                        "loai_cau_truc", "phan_cap_stt"
                                    ),
                                    "ds_chuong_trinh": list(
                                        new_cfg.get("ds_chuong_trinh", [])
                                    ),
                                }, username)
                                st.session_state.pop(f"cd_mig_{i}", None)
                                st.success(
                                    f"✅ Template '{mig_ten.strip()}' đã được lưu."
                                )
                                st.rerun()
                    with cm2:
                        if st.button("✕ Huỷ", key=f"cd_mig_{i}_cancel",
                                     use_container_width=True):
                            st.session_state.pop(f"cd_mig_{i}", None)
                            st.rerun()

    # ── Thêm Google Sheet mới ─────────────────────────────────────────────
    st.divider()
    st.markdown("**➕ Thêm Google Sheet mới**")

    url_input = st.text_input(
        "Paste link Google Sheet",
        key="cd_url_input",
        placeholder="https://docs.google.com/spreadsheets/d/...",
        label_visibility="collapsed",
    )

    if url_input.strip():
        import re
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_input)
        if not m:
            st.error(
                "❌ Link không hợp lệ. "
                "Cần dạng: .../spreadsheets/d/[ID]/..."
            )
        else:
            sid = m.group(1)
            existing_ids = [s.get("sheet_id") for s in ds_sheet]
            if sid in existing_ids:
                st.warning("⚠️ Sheet này đã có trong danh sách.")
            else:
                try:
                    with st.spinner("Đang đọc danh sách tab..."):
                        client = ket_noi_gsheet()
                        ss = client.open_by_key(sid)
                        tab_list = [w.title for w in ss.worksheets()]

                    _templates = doc_ds_template()
                    _existing_tabs = {
                        s.get("sheet_tab") for s in ds_sheet
                        if s.get("sheet_id") == sid
                    }

                    if _templates:
                        _tpl_opts = {"": "📋 Copy từ sheet đầu tiên"}
                        _tpl_opts.update({
                            t["id"]: f"📁 {t['ten']}" for t in _templates
                        })
                        _tpl_keys = list(_tpl_opts.keys())
                        _suggest_id = goi_y_template(
                            tab_list[0] if tab_list else "", _templates,
                        )
                        _suggest_idx = (
                            _tpl_keys.index(_suggest_id)
                            if _suggest_id and _suggest_id in _tpl_keys else 0
                        )
                        tpl_sel_id = st.selectbox(
                            "Áp dụng template",
                            _tpl_keys,
                            format_func=lambda k: _tpl_opts[k],
                            index=_suggest_idx,
                            key="cd_tpl_sel",
                        )
                        if _suggest_id and _suggest_id == tpl_sel_id:
                            st.caption(
                                "✨ Tự động gợi ý dựa trên tên tab đầu tiên."
                            )
                    else:
                        tpl_sel_id = ""

                    st.markdown("**Chọn tab cần theo dõi:**")
                    tab_chon_list = []
                    for tab_name in tab_list:
                        da_co = tab_name in _existing_tabs
                        label = tab_name + (" *(đã có)*" if da_co else "")
                        checked = st.checkbox(
                            label,
                            value=(not da_co),
                            key=f"cd_chk_{sid[:8]}_{tab_name[:30]}",
                            disabled=da_co,
                        )
                        if checked and not da_co:
                            tab_chon_list.append(tab_name)

                    n_chon = len(tab_chon_list)
                    if n_chon == 0:
                        st.info("Chưa chọn tab nào.")
                    else:
                        if st.button(
                            f"➕ Thêm {n_chon} tab đã chọn",
                            key="cd_add_multi", type="primary",
                        ):
                            added = []
                            for tab_name in tab_chon_list:
                                ten = tab_name[:40]
                                if tpl_sel_id:
                                    new_cfg = ap_dung_template(
                                        tpl_sel_id, sid, tab_name, ten,
                                    )
                                    if new_cfg is None:
                                        st.warning(
                                            f"⚠️ Template lỗi, "
                                            f"bỏ qua tab: {tab_name}"
                                        )
                                        continue
                                else:
                                    base_cfg = (
                                        ds_sheet[0] if ds_sheet
                                        else sheet_moi()
                                    )
                                    new_cfg = {
                                        **base_cfg,
                                        "ten_hien_thi": ten,
                                        "sheet_id": sid,
                                        "sheet_tab": tab_name,
                                    }
                                ds_sheet.append(new_cfg)
                                added.append(ten)
                            if added:
                                doc_sheet.clear()
                                luu_ds_sheet(ds_sheet, username)
                                st.success(
                                    f"✅ Đã thêm {len(added)} tab: "
                                    + " · ".join(added)
                                )
                                st.rerun()

                    if tpl_sel_id and _templates:
                        st.caption(
                            "💡 Cấu hình từ template "
                            f"**{_tpl_opts.get(tpl_sel_id, '')}**"
                        )
                    elif ds_sheet:
                        st.caption(
                            "💡 Không chọn template → copy cấu hình từ "
                            f"**{ds_sheet[0].get('ten_hien_thi', 'sheet đầu tiên')}**."
                        )
                    else:
                        st.caption(
                            "💡 Tạo template trong mục 📁 Quản lý Template "
                            "để tự động điền cấu hình."
                        )
                except Exception as e:
                    logger.error(
                        "_sub_tong_hop doc_sheet: %s", e, exc_info=True,
                    )
                    st.error(f"❌ Không đọc được sheet: {e}")
