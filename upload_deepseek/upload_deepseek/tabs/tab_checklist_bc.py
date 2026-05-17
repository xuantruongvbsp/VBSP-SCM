import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import uuid
import db
from utils import get_tab_context
from auth import normalize_role

_KEY_CONFIG = "checklist_bc_config"
_TRANG_THAI = {
    "chua_lam": "⬜ Chưa làm",
    "dang_lam": "🔄 Đang làm",
    "da_nop":   "✅ Đã nộp",
    "tre_han":  "🔴 Trễ hạn",
}
_CHU_KY = {"thang": "Tháng", "quy": "Quý", "nam": "Năm"}
_DON_VI_NHAN = {"TW": "Trung ương", "tinh": "Tỉnh/UBND", "noi_bo": "Nội bộ"}
_SEED = [
    {"id": "bc_001", "ten": "Báo cáo dư nợ tháng", "chu_ky": "thang", "ngay_han": 5, "don_vi_nhan": "TW", "mo_ta": "Phụ lục 06/ĐGXL", "nguoi_phu_trach": ""},
    {"id": "bc_002", "ten": "Báo cáo chất lượng tín dụng", "chu_ky": "thang", "ngay_han": 7, "don_vi_nhan": "TW", "mo_ta": "Phụ lục 07/ĐGXL", "nguoi_phu_trach": ""},
    {"id": "bc_003", "ten": "Báo cáo NQH tháng", "chu_ky": "thang", "ngay_han": 5, "don_vi_nhan": "tinh", "mo_ta": "BC NQH gửi UBND tỉnh", "nguoi_phu_trach": ""},
    {"id": "bc_004", "ten": "Báo cáo NQ11", "chu_ky": "thang", "ngay_han": 10, "don_vi_nhan": "TW", "mo_ta": "BC NQ11/NQ-CP", "nguoi_phu_trach": ""},
    {"id": "bc_005", "ten": "Báo cáo quý — tổng hợp KHTD", "chu_ky": "quy", "ngay_han": 10, "don_vi_nhan": "TW", "mo_ta": "BC kết quả thực hiện KHTD quý", "nguoi_phu_trach": ""},
    {"id": "bc_006", "ten": "Báo cáo thi đua 5 chuyên đề", "chu_ky": "quy", "ngay_han": 15, "don_vi_nhan": "TW", "mo_ta": "Chấm điểm thi đua theo 5 chuyên đề", "nguoi_phu_trach": ""},
    {"id": "bc_007", "ten": "Báo cáo tổng kết năm", "chu_ky": "nam", "ngay_han": 20, "don_vi_nhan": "TW", "mo_ta": "BC tổng kết hoạt động tín dụng năm", "nguoi_phu_trach": ""},
    {"id": "bc_008", "ten": "Báo cáo kế hoạch năm sau", "chu_ky": "nam", "ngay_han": 30, "don_vi_nhan": "TW", "mo_ta": "Xây dựng KHTD năm kế tiếp", "nguoi_phu_trach": ""},
]


def _key_thang(nam: int, thang: int) -> str:
    return f"checklist_bc_{nam}_{thang:02d}"


def _doc_config() -> list[dict]:
    data = db.doc_kv(_KEY_CONFIG)
    if data and isinstance(data, list) and len(data) > 0:
        return data
    return _SEED


def _doc_trang_thai(nam: int, thang: int) -> dict[str, dict]:
    data = db.doc_kv(_key_thang(nam, thang))
    if data and isinstance(data, list):
        out = {}
        for r in data:
            bc_id = r.get("bc_id")
            if bc_id:
                out[str(bc_id)] = r
        return out
    return {}


def _ghi_trang_thai(nam: int, thang: int, ds: dict[str, dict], username: str):
    db.ghi_kv(_key_thang(nam, thang), list(ds.values()), username)
    db.ghi_audit(username, "cap_nhat_checklist_bc",
                 f"Kỳ {nam}-T{thang:02d}: {len(ds)} báo cáo")
    st.cache_data.clear()


def _tinh_ngay_han(chu_ky: str, ngay_han: int, nam: int, thang: int) -> date | None:
    try:
        if chu_ky == "thang":
            return date(nam, thang, min(int(ngay_han), 28))
        if chu_ky == "quy":
            thang_cuoi_quy = ((thang - 1) // 3 + 1) * 3
            return date(nam, thang_cuoi_quy, min(int(ngay_han), 28))
        if chu_ky == "nam":
            return date(nam, 12, min(int(ngay_han), 31))
    except Exception:
        return None
    return None


def _tu_dong_cap_nhat_tre_han(
    ds_config: list[dict],
    trang_thai: dict[str, dict],
    nam: int,
    thang: int
) -> dict[str, dict]:
    hom_nay = date.today()
    for bc in (ds_config or []):
        bid = bc.get("id")
        if not bid:
            continue
        ngay_han = _tinh_ngay_han(bc.get("chu_ky"), bc.get("ngay_han", 0), nam, thang)
        if ngay_han and hom_nay > ngay_han:
            rec = trang_thai.get(
                bid,
                {"bc_id": bid, "trang_thai": "chua_lam", "ngay_cap_nhat": "", "ghi_chu": "", "nguoi_cap_nhat": ""},
            )
            if rec.get("trang_thai") == "chua_lam":
                rec["trang_thai"] = "tre_han"
                trang_thai[bid] = rec
    return trang_thai


def _ensure_seed_config(username: str) -> list[dict]:
    data = db.doc_kv(_KEY_CONFIG)
    if data and isinstance(data, list) and len(data) > 0:
        return data
    db.ghi_kv(_KEY_CONFIG, _SEED, username)
    db.ghi_audit(username, "seed_checklist_bc_config", f"Seed {len(_SEED)} báo cáo mặc định")
    st.cache_data.clear()
    return _SEED


def _render_bo_loc() -> tuple[int, int]:
    hom_nay = date.today()
    col1, col2 = st.columns(2)
    with col1:
        ds_nam = list(range(hom_nay.year - 1, hom_nay.year + 2))
        nam = st.selectbox("Năm", ds_nam, index=1, key="clbc_nam")
    with col2:
        thang = st.selectbox(
            "Tháng",
            list(range(1, 13)),
            index=hom_nay.month - 1,
            format_func=lambda x: f"Tháng {x}",
            key="clbc_thang",
        )
    return int(nam), int(thang)


def _render_tong_quan(ds_config, trang_thai, nam, thang):
    hom_nay = date.today()
    tong = len(ds_config)
    da_nop = sum(
        1 for bc in ds_config
        if trang_thai.get(bc.get("id"), {}).get("trang_thai") == "da_nop"
    )
    tre_han = sum(
        1 for bc in ds_config
        if trang_thai.get(bc.get("id"), {}).get("trang_thai") == "tre_han"
    )
    sap_han = 0
    for bc in ds_config:
        bid = bc.get("id")
        if not bid:
            continue
        tt = trang_thai.get(bid, {}).get("trang_thai")
        if tt in ("da_nop",):
            continue
        d_han = _tinh_ngay_han(bc.get("chu_ky"), bc.get("ngay_han", 0), nam, thang)
        if d_han:
            diff = (d_han - hom_nay).days
            if 0 <= diff <= 3:
                sap_han += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Tổng báo cáo", tong)
    c2.metric("✅ Đã nộp", da_nop)
    c3.metric("🔴 Trễ hạn", tre_han, delta=f"-{tre_han}" if tre_han else None, delta_color="inverse")
    c4.metric("⚠️ Sắp đến hạn (≤3 ngày)", sap_han, delta=f"!{sap_han}" if sap_han else None, delta_color="inverse")

    if tre_han > 0:
        ten_tre = [
            bc.get("ten", "")
            for bc in ds_config
            if trang_thai.get(bc.get("id"), {}).get("trang_thai") == "tre_han"
        ]
        ten_tre = [t for t in ten_tre if t]
        if ten_tre:
            st.warning("Trễ hạn: " + "; ".join(ten_tre))

    ds_sap = []
    for bc in ds_config:
        bid = bc.get("id")
        if not bid:
            continue
        tt = trang_thai.get(bid, {}).get("trang_thai")
        if tt in ("da_nop",):
            continue
        d_han = _tinh_ngay_han(bc.get("chu_ky"), bc.get("ngay_han", 0), nam, thang)
        if not d_han:
            continue
        diff = (d_han - hom_nay).days
        if 0 <= diff <= 3:
            ds_sap.append({"Báo cáo": bc.get("ten", ""), "Hạn": d_han.isoformat(), "Còn lại (ngày)": diff})
    if ds_sap:
        st.info("Báo cáo sắp đến hạn (≤3 ngày)")
        st.dataframe(pd.DataFrame(ds_sap), hide_index=True, width='stretch')


def _render_danh_sach(
    ds_config: list[dict],
    trang_thai: dict[str, dict],
    nam: int,
    thang: int,
    username: str,
    can_edit: bool,
):
    hom_nay = date.today()

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        loc_chu_ky = st.multiselect(
            "Chu kỳ",
            list(_CHU_KY.keys()),
            default=list(_CHU_KY.keys()),
            format_func=lambda x: _CHU_KY.get(x, x),
            key="clbc_loc_ck",
        )
    with col2:
        loc_dv = st.multiselect(
            "Đơn vị nhận",
            list(_DON_VI_NHAN.keys()),
            default=list(_DON_VI_NHAN.keys()),
            format_func=lambda x: _DON_VI_NHAN.get(x, x),
            key="clbc_loc_dv",
        )
    with col3:
        loc_tt = st.multiselect(
            "Trạng thái",
            list(_TRANG_THAI.keys()),
            default=list(_TRANG_THAI.keys()),
            format_func=lambda x: _TRANG_THAI.get(x, x),
            key="clbc_loc_tt",
        )

    ds_loc = []
    for bc in (ds_config or []):
        if loc_chu_ky and bc.get("chu_ky") not in loc_chu_ky:
            continue
        if loc_dv and bc.get("don_vi_nhan") not in loc_dv:
            continue
        bid = bc.get("id")
        tt = trang_thai.get(bid, {}).get("trang_thai", "chua_lam")
        if loc_tt and tt not in loc_tt:
            continue
        ds_loc.append(bc)

    if not ds_loc:
        st.info("Không có báo cáo nào khớp bộ lọc.")
        return

    with st.form("form_checklist_bc"):
        for i, bc in enumerate(ds_loc):
            bid = bc.get("id", "")
            if not bid:
                continue
            rec = trang_thai.get(
                bid,
                {"bc_id": bid, "trang_thai": "chua_lam", "ngay_cap_nhat": "", "ghi_chu": "", "nguoi_cap_nhat": ""},
            )
            d_han = _tinh_ngay_han(bc.get("chu_ky"), bc.get("ngay_han", 0), nam, thang)
            badge = ""
            if d_han:
                diff = (d_han - hom_nay).days
                if rec.get("trang_thai") != "da_nop":
                    if diff < 0:
                        badge = "🔴"
                    elif diff <= 3:
                        badge = "⚠️"
            tieu_de = f"{badge} {bc.get('ten','')}"
            with st.expander(tieu_de, expanded=(i == 0)):
                c1, c2, c3, c4 = st.columns([2, 1, 2, 2])
                with c1:
                    st.caption("Chu kỳ / Nơi nhận")
                    st.write(f"{_CHU_KY.get(bc.get('chu_ky'), bc.get('chu_ky'))} · {_DON_VI_NHAN.get(bc.get('don_vi_nhan'), bc.get('don_vi_nhan'))}")
                with c2:
                    st.caption("Ngày hạn")
                    st.write(d_han.strftime("%d/%m/%Y") if d_han else "—")
                with c3:
                    st.caption("Mô tả")
                    st.write(bc.get("mo_ta", "") or "—")
                with c4:
                    st.caption("Người phụ trách")
                    st.write(bc.get("nguoi_phu_trach", "") or "—")

                col_tt, col_note, col_meta = st.columns([1, 2, 1])
                with col_tt:
                    idx = list(_TRANG_THAI.keys()).index(rec.get("trang_thai", "chua_lam")) if rec.get("trang_thai") in _TRANG_THAI else 0
                    tt_moi = st.selectbox(
                        "Trạng thái",
                        list(_TRANG_THAI.keys()),
                        index=idx,
                        format_func=lambda x: _TRANG_THAI.get(x, x),
                        disabled=not can_edit,
                        key=f"clbc_tt_{bid}_{nam}_{thang:02d}",
                    )
                with col_note:
                    ghi_chu = st.text_input(
                        "Ghi chú",
                        value=rec.get("ghi_chu", "") or "",
                        disabled=not can_edit,
                        key=f"clbc_note_{bid}_{nam}_{thang:02d}",
                    )
                with col_meta:
                    st.caption("Cập nhật")
                    st.write(rec.get("ngay_cap_nhat") or "—")
                    st.write(rec.get("nguoi_cap_nhat") or "—")

                if can_edit:
                    rec_new = dict(rec)
                    rec_new["trang_thai"] = tt_moi
                    rec_new["ghi_chu"] = (ghi_chu or "").strip()
                    if (rec_new["trang_thai"] != rec.get("trang_thai")) or (rec_new["ghi_chu"] != (rec.get("ghi_chu") or "").strip()):
                        rec_new["ngay_cap_nhat"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        rec_new["nguoi_cap_nhat"] = username
                    trang_thai[bid] = rec_new

        submitted = st.form_submit_button("💾 Lưu trạng thái", type="primary", disabled=not can_edit)

    if submitted and can_edit:
        _ghi_trang_thai(nam, thang, trang_thai, username)
        st.success("Đã lưu trạng thái checklist.")
        st.rerun()


def _render_quan_tri(ds_config: list[dict], username: str, can_edit: bool) -> list[dict]:
    st.subheader("⚙️ Cấu hình danh sách báo cáo")
    if not can_edit:
        st.info("Chỉ admin/manager mới có thể thêm/sửa/xóa báo cáo.")
        return ds_config

    ds = [dict(x) for x in (ds_config or [])]
    ds = [x for x in ds if x.get("id") and x.get("ten")]
    ds_ids = [x["id"] for x in ds]

    for i, bc in enumerate(ds):
        with st.expander(f"{bc.get('id')} — {bc.get('ten')}", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                ten = st.text_input("Tên báo cáo", value=bc.get("ten", ""), key=f"clbc_cfg_ten_{bc['id']}")
            with c2:
                ngay_han = st.number_input(
                    "Ngày hạn",
                    min_value=1,
                    max_value=31,
                    value=int(bc.get("ngay_han", 1) or 1),
                    step=1,
                    key=f"clbc_cfg_han_{bc['id']}",
                )
            c3, c4, c5 = st.columns(3)
            with c3:
                ck = st.selectbox(
                    "Chu kỳ",
                    list(_CHU_KY.keys()),
                    index=list(_CHU_KY.keys()).index(bc.get("chu_ky", "thang")) if bc.get("chu_ky") in _CHU_KY else 0,
                    format_func=lambda x: _CHU_KY.get(x, x),
                    key=f"clbc_cfg_ck_{bc['id']}",
                )
            with c4:
                dv = st.selectbox(
                    "Nơi nhận",
                    list(_DON_VI_NHAN.keys()),
                    index=list(_DON_VI_NHAN.keys()).index(bc.get("don_vi_nhan", "TW")) if bc.get("don_vi_nhan") in _DON_VI_NHAN else 0,
                    format_func=lambda x: _DON_VI_NHAN.get(x, x),
                    key=f"clbc_cfg_dv_{bc['id']}",
                )
            with c5:
                nguoi = st.text_input(
                    "Người phụ trách",
                    value=bc.get("nguoi_phu_trach", "") or "",
                    key=f"clbc_cfg_nguoi_{bc['id']}",
                )

            mo_ta = st.text_input(
                "Mô tả / Tham chiếu",
                value=bc.get("mo_ta", "") or "",
                key=f"clbc_cfg_mota_{bc['id']}",
            )

            col_save, col_del = st.columns([1, 1])
            with col_save:
                if st.button("💾 Lưu", key=f"clbc_cfg_save_{bc['id']}"):
                    for x in ds:
                        if x["id"] == bc["id"]:
                            x["ten"] = (ten or "").strip()
                            x["chu_ky"] = ck
                            x["ngay_han"] = int(ngay_han)
                            x["don_vi_nhan"] = dv
                            x["mo_ta"] = (mo_ta or "").strip()
                            x["nguoi_phu_trach"] = (nguoi or "").strip()
                            break
                    db.ghi_kv(_KEY_CONFIG, ds, username)
                    db.ghi_audit(username, "cap_nhat_checklist_bc_config", f"Cập nhật báo cáo {bc['id']}")
                    st.cache_data.clear()
                    st.success("Đã lưu cấu hình.")
                    st.rerun()
            with col_del:
                if st.button("🗑️ Xóa", key=f"clbc_cfg_del_{bc['id']}"):
                    ds = [x for x in ds if x["id"] != bc["id"]]
                    db.ghi_kv(_KEY_CONFIG, ds, username)
                    db.ghi_audit(username, "xoa_checklist_bc_config", f"Xóa báo cáo {bc['id']}")
                    st.cache_data.clear()
                    st.success("Đã xóa.")
                    st.rerun()

    st.divider()
    st.markdown("##### ➕ Thêm báo cáo mới")
    with st.form("clbc_add_bc", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            ten_moi = st.text_input("Tên báo cáo", value="", key="clbc_ten")
        with c2:
            ngay_han_moi = st.number_input("Ngày hạn", min_value=1, max_value=31, value=5, step=1, key="clbc_ngay_han")
        c3, c4, c5 = st.columns(3)
        with c3:
            chu_ky_moi = st.selectbox("Chu kỳ", list(_CHU_KY.keys()), format_func=lambda x: _CHU_KY.get(x, x), key="clbc_chu_ky")
        with c4:
            dv_moi = st.selectbox("Nơi nhận", list(_DON_VI_NHAN.keys()), format_func=lambda x: _DON_VI_NHAN.get(x, x), key="clbc_dv")
        with c5:
            nguoi_moi = st.text_input("Người phụ trách", value="", key="clbc_nguoi")
        mo_ta_moi = st.text_input("Mô tả / Tham chiếu", value="", key="clbc_mo_ta")
        submitted = st.form_submit_button("➕ Thêm", type="primary")
    if submitted:
        ten_moi = (ten_moi or "").strip()
        if not ten_moi:
            st.error("Vui lòng nhập tên báo cáo.")
        else:
            new_id = f"bc_{uuid.uuid4().hex[:6]}"
            while new_id in ds_ids:
                new_id = f"bc_{uuid.uuid4().hex[:6]}"
            ds.append({
                "id": new_id,
                "ten": ten_moi,
                "chu_ky": chu_ky_moi,
                "ngay_han": int(ngay_han_moi),
                "don_vi_nhan": dv_moi,
                "mo_ta": (mo_ta_moi or "").strip(),
                "nguoi_phu_trach": (nguoi_moi or "").strip(),
            })
            db.ghi_kv(_KEY_CONFIG, ds, username)
            db.ghi_audit(username, "them_checklist_bc_config", f"Thêm báo cáo {new_id}")
            st.cache_data.clear()
            st.success("Đã thêm báo cáo mới.")
            st.rerun()

    return ds


def _render_xuat_excel(ds_config: list[dict], trang_thai: dict[str, dict], nam: int, thang: int):
    st.subheader("📤 Xuất Excel")
    rows = []
    for bc in (ds_config or []):
        bid = bc.get("id")
        if not bid:
            continue
        rec = trang_thai.get(bid, {})
        d_han = _tinh_ngay_han(bc.get("chu_ky"), bc.get("ngay_han", 0), nam, thang)
        rows.append({
            "ID": bid,
            "Tên báo cáo": bc.get("ten", ""),
            "Chu kỳ": _CHU_KY.get(bc.get("chu_ky"), bc.get("chu_ky")),
            "Nơi nhận": _DON_VI_NHAN.get(bc.get("don_vi_nhan"), bc.get("don_vi_nhan")),
            "Ngày hạn": d_han.isoformat() if d_han else "",
            "Trạng thái": _TRANG_THAI.get(rec.get("trang_thai", "chua_lam"), rec.get("trang_thai", "chua_lam")),
            "Ngày cập nhật": rec.get("ngay_cap_nhat", ""),
            "Người cập nhật": rec.get("nguoi_cap_nhat", ""),
            "Ghi chú": rec.get("ghi_chu", ""),
            "Mô tả": bc.get("mo_ta", ""),
            "Người phụ trách": bc.get("nguoi_phu_trach", ""),
        })
    df_out = pd.DataFrame(rows)
    if df_out.empty:
        st.info("Chưa có dữ liệu để xuất.")
        return

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(ds_config).to_excel(writer, sheet_name="Config", index=False)
        df_out.to_excel(writer, sheet_name=f"{nam}-T{thang:02d}", index=False)
    buf.seek(0)
    ten_file = f"Checklist_BaoCao_{nam}_T{thang:02d}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    st.download_button(
        "⬇️ Tải về Excel",
        data=buf.getvalue(),
        file_name=ten_file,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="clbc_dl_excel",
        width='stretch',
    )


def render(tab=None, **kwargs) -> None:
    import streamlit as st
    if tab is not None:
        _ctx = tab
    else:
        _ctx = st.container()
    with _ctx:
        role_raw = str(kwargs.get("role", "user") or "user")
        role = normalize_role(role_raw)
        username = kwargs.get("username", "unknown")
        can_edit = role in ("admin_cn", "manager_cn")

        st.title("✅ Checklist báo cáo định kỳ")
        st.caption("Theo dõi hạn nộp báo cáo tháng/quý/năm và trạng thái thực hiện.")

        if role not in ("admin_cn", "manager_cn"):
            st.warning("Bạn không có quyền truy cập checklist báo cáo.")
            return

        _ensure_seed_config(username)
        ds_config = _doc_config()

        st.divider()
        nam, thang = _render_bo_loc()

        trang_thai = _doc_trang_thai(nam, thang)
        trang_thai = _tu_dong_cap_nhat_tre_han(ds_config, trang_thai, nam, thang)

        t1, t2, t3 = st.tabs(["📊 Tổng quan", "🧾 Checklist", "⚙️ Cấu hình"])
        with t1:
            _render_tong_quan(ds_config, trang_thai, nam, thang)
            st.divider()
            _render_xuat_excel(ds_config, trang_thai, nam, thang)
        with t2:
            _render_danh_sach(ds_config, trang_thai, nam, thang, username, can_edit)
        with t3:
            _render_quan_tri(ds_config, username, can_edit)
