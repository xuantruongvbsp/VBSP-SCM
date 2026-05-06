"""Nhập dữ liệu cho tab Kế hoạch Tín dụng (Chi nhánh + theo Xã/PGD)."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

import db
from auth import get_permissions
from config import CHUONG_TRINH_KHTD, COT_TEN_PGD, DS_PGD, PGD_XA_MAP
from utils import xuat_excel, ten_file_xuat, vn

from tabs.tab_khtd import (
    DATA_DIR,
    KV_KEY_CN,
    KV_KEY_XA,
    KHTD_CN_NHOM_MA_CT,
    MA_KEYS_CO_KHTD,
    _chon_ds_ct,
    _doc_kv,
    _fvn,
    _fmt_vn,
    _khtd_cn_hdr_cell,
    _luu_kv,
    _quet_ct_co_du_no,
    _ten_ct_base,
    _tinh_thuc_hien_theo_ct,
)
from tabs.tab_khtd_xuat import _hien_thi_bang_cn_readonly


# Thư mục lưu văn bản QĐ cấp Chi nhánh
QD_DIR_CN = DATA_DIR / "qd"


def _format_kich_thuoc(byte_count: int) -> str:
    """Định dạng dung lượng file thành chuỗi dễ đọc."""
    if byte_count >= 1_048_576:
        return f"{byte_count / 1_048_576:.1f} MB"
    return f"{byte_count / 1024:.1f} KB"


def _doc_meta_qd(kv_key: str) -> list[dict]:
    """Đọc danh sách metadata file QĐ từ kv_store."""
    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM kv_store WHERE key=?", (kv_key,)
            ).fetchone()
            if row:
                val = json.loads(row["value"])
                return val if isinstance(val, list) else []
    except Exception:
        pass
    return []


def _luu_meta_qd(kv_key: str, danh_sach: list[dict], username: str) -> None:
    """Ghi danh sách metadata file QĐ vào kv_store."""
    try:
        with db.get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO kv_store (key, value, updated_at, updated_by) "
                "VALUES (?,?,?,?)",
                (kv_key, json.dumps(danh_sach, ensure_ascii=False),
                 datetime.now().isoformat(), username),
            )
            conn.commit()
    except Exception as e:
        st.error(f"Lỗi lưu metadata file QĐ: {e}")


def _luu_file_qd(uploaded, thu_muc: Path, kv_key: str, username: str) -> Path:
    """Lưu file mới với timestamp prefix, cập nhật metadata trong kv_store."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ten_goc = uploaded.name
    ten_luu = f"{ts}_{ten_goc}"
    thu_muc.mkdir(parents=True, exist_ok=True)
    duong_dan = thu_muc / ten_luu
    noi_dung = uploaded.getvalue()
    duong_dan.write_bytes(noi_dung)

    danh_sach = _doc_meta_qd(kv_key)
    danh_sach.append({
        "ten_file":    ten_goc,
        "duong_dan":   str(duong_dan),
        "ngay_upload": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nguoi_upload": username,
        "kich_thuoc":  len(noi_dung),
    })
    _luu_meta_qd(kv_key, danh_sach, username)
    return duong_dan


def _hien_thi_lich_su_qd(kv_key: str, nhan: str, role: str, username: str) -> None:
    """Hiển thị bảng lịch sử file QĐ, nút tải xuống và (admin) nút xóa."""
    danh_sach = _doc_meta_qd(kv_key)
    st.markdown(f"**{nhan}**")
    if not danh_sach:
        st.info("📭 Chưa có file nào được upload.")
        return

    # Header bảng
    h1, h2, h3, h4, h5, h6 = st.columns([3, 2, 2, 1.5, 1, 1])
    h1.markdown("**Tên file**")
    h2.markdown("**Ngày upload**")
    h3.markdown("**Người upload**")
    h4.markdown("**Dung lượng**")

    for idx_rev, meta in enumerate(reversed(danh_sach)):
        idx_thuc = len(danh_sach) - 1 - idx_rev
        c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 1.5, 1, 1])
        c1.text(meta.get("ten_file", "—"))
        c2.text(meta.get("ngay_upload", "—"))
        c3.text(meta.get("nguoi_upload", "—"))
        c4.text(_format_kich_thuoc(meta.get("kich_thuoc", 0)))

        duong_dan = Path(meta.get("duong_dan", ""))
        if duong_dan.exists():
            c5.download_button(
                "⬇",
                data=duong_dan.read_bytes(),
                file_name=meta.get("ten_file", duong_dan.name),
                key=f"dl_{kv_key}_{idx_rev}",
                help="Tải xuống",
            )
        else:
            c5.markdown("⚠️")

        if get_permissions(role)["can_edit_khtd"]:
            if c6.button("🗑", key=f"del_{kv_key}_{idx_rev}", help="Xóa file"):
                if duong_dan.exists():
                    duong_dan.unlink()
                danh_sach.pop(idx_thuc)
                _luu_meta_qd(kv_key, danh_sach, username)
                db.ghi_audit(
                    username, "xoa_van_ban_qd",
                    f"File: {meta.get('ten_file')} · key: {kv_key}",
                )
                st.rerun()


def _section_van_ban_qd_cn(role: str, username: str) -> None:
    """Upload / hiển thị lịch sử văn bản QĐ cấp Chi nhánh."""
    with st.expander("📎 Văn bản QĐ", expanded=True):
        # ── Lịch sử từng loại ────────────────────────────────────────────
        col_hist1, col_hist2 = st.columns(2)
        with col_hist1:
            _hien_thi_lich_su_qd("qd_files_hdqt_tinh", "QĐ HĐQT tỉnh", role, username)
        with col_hist2:
            _hien_thi_lich_su_qd("qd_files_tw", "QĐ NHCSXH TW", role, username)

        if not get_permissions(role)["can_edit_khtd"]:
            st.caption("🔒 Chỉ Admin / Manager mới được upload văn bản QĐ.")
            return

        # ── Upload file mới ───────────────────────────────────────────────
        st.divider()
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            f_hdqt = st.file_uploader(
                "Upload QĐ HĐQT tỉnh",
                type=["pdf", "xlsx", "xls"],
                key="vb_hdqt_tinh_cn",
            )
            if f_hdqt:
                _id = f"qd_done_hdqt_tinh_{f_hdqt.name}_{f_hdqt.size}"
                if not st.session_state.get(_id):
                    st.session_state[_id] = True
                    try:
                        dp = _luu_file_qd(
                            f_hdqt,
                            QD_DIR_CN / "hdqt_tinh",
                            "qd_files_hdqt_tinh",
                            username,
                        )
                        db.ghi_audit(username, "upload_vb_qd_hdqt_tinh",
                                     f"File: {dp.name}")
                        st.success(f"✅ Đã lưu: `{dp.name}`")
                        st.rerun()
                    except Exception as e:
                        st.session_state.pop(_id, None)
                        st.error(f"Lỗi lưu file QĐ HĐQT tỉnh: {e}")
        with col_u2:
            f_tw = st.file_uploader(
                "Upload QĐ NHCSXH TW",
                type=["pdf", "xlsx", "xls"],
                key="vb_qd_tw_cn",
            )
            if f_tw:
                _id = f"qd_done_tw_{f_tw.name}_{f_tw.size}"
                if not st.session_state.get(_id):
                    st.session_state[_id] = True
                    try:
                        dp = _luu_file_qd(
                            f_tw,
                            QD_DIR_CN / "tw",
                            "qd_files_tw",
                            username,
                        )
                        db.ghi_audit(username, "upload_vb_qd_tw",
                                     f"File: {dp.name}")
                        st.success(f"✅ Đã lưu: `{dp.name}`")
                        st.rerun()
                    except Exception as e:
                        st.session_state.pop(_id, None)
                        st.error(f"Lỗi lưu file QĐ TW: {e}")


def _tao_df_mau_khtd_cn() -> pd.DataFrame:
    """DataFrame mẫu upload KHTD Chi nhánh (một dòng / ma_key trong CHUONG_TRINH_KHTD)."""
    rows: list[dict] = []
    for ma_key, _ma_ct, ten, nv, _ in CHUONG_TRINH_KHTD:
        rows.append({
            "Chương trình": ten,
            "Mã CT": ma_key,
            "Nguồn vốn": nv,
            "KH (triệu đồng)": 0.0,
        })
    return pd.DataFrame(rows)


def _doc_excel_khtd_cn_upload(file_bytes: bytes) -> tuple[dict[str, float], int, list[str]] | None:
    """
    Đọc Excel upload → dict ma_key → số đồng.
    Trả về None nếu thiếu cột bắt buộc hoặc không đọc được file.
    """
    try:
        df_up = pd.read_excel(BytesIO(file_bytes), header=0)
    except Exception as e:
        st.error(f"Không đọc được file Excel: {e}")
        return None

    ten_cot = {str(c).strip(): c for c in df_up.columns}
    if "Mã CT" not in ten_cot:
        st.error(
            "Không tìm thấy cột **Mã CT** trong file. Vui lòng dùng đúng file mẫu "
            "(nút **⬇️ Tải file mẫu Excel** phía trên) và giữ nguyên tên các cột."
        )
        return None

    col_kh = ten_cot.get("KH (triệu đồng)")
    if col_kh is None:
        for t, c in ten_cot.items():
            tl = t.lower()
            if "kh" in tl and ("triệu" in t or "trieu" in tl):
                col_kh = c
                break
    if col_kh is None:
        st.error(
            "Không tìm thấy cột **KH (triệu đồng)**. Vui lòng dùng file mẫu và không đổi tên cột KH."
        )
        return None

    col_ma = ten_cot["Mã CT"]
    out: dict[str, float] = {}
    bo_qua: list[str] = []
    for _, row in df_up.iterrows():
        ma_key = str(row[col_ma]).strip()
        if not ma_key or ma_key.lower() == "nan":
            continue
        if ma_key not in MA_KEYS_CO_KHTD:
            bo_qua.append(ma_key)
            continue
        v = row[col_kh]
        if pd.isna(v):
            continue
        try:
            kh_trieu = float(v)
        except (TypeError, ValueError):
            continue
        if kh_trieu == 0:
            continue
        out[ma_key] = kh_trieu * 1_000_000

    if bo_qua:
        st.warning(
            f"Bỏ qua **{len(bo_qua)}** dòng có Mã CT không thuộc danh mục KHTD: "
            f"{', '.join(sorted(set(bo_qua))[:12])}"
            + ("…" if len(set(bo_qua)) > 12 else "")
        )
    return out, len(out), bo_qua


def _tab_khtd_chi_nhanh(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    st.subheader("🏛️ Kế hoạch Tín dụng Chi nhánh")

    co_quyen = get_permissions(role)["can_edit_khtd"]
    kh_cn = _doc_kv(KV_KEY_CN)
    th_cn = _tinh_thuc_hien_theo_ct(df_full) if df_full is not None else {}

    if not co_quyen:
        st.warning("⚠️ Chỉ Admin / Manager mới được nhập kế hoạch cấp Chi nhánh.")
        df_loc = df_full
        _hien_thi_bang_cn_readonly(kh_cn, th_cn, df_loc=df_loc, username=username)
        st.divider()
        _section_van_ban_qd_cn(role, username)
        return

    nv_chon = st.radio(
        "Hiển thị nguồn vốn (bảng tóm tắt)",
        ["Tất cả", "Trung ương", "Địa phương"],
        horizontal=True,
        key="khtd_cn_nv_radio",
    )
    df_loc = df_full
    ds_ct = _chon_ds_ct(nv_chon, df_loc, them_keys=set(kh_cn.keys()) | set(th_cn.keys()))

    # ── Phương thức 1: Upload Excel ─────────────────────────────────────
    with st.expander("📥 Upload Excel kế hoạch — nhanh nhất", expanded=True):
        df_mau = _tao_df_mau_khtd_cn()
        st.download_button(
            "⬇️ Tải file mẫu Excel",
            data=xuat_excel({"KHTD_CN": df_mau}),
            file_name=ten_file_xuat("Mau_KHTD_Chi_nhanh", "xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="khtd_cn_dl_mau",
        )
        f_up = st.file_uploader(
            "Chọn file Excel đã điền KH (triệu đồng)",
            type=["xlsx", "xls"],
            key="khtd_cn_upload",
        )
        if f_up:
            _uid = f"khtd_cn_up_done_{f_up.name}_{f_up.size}"
            if not st.session_state.get(_uid):
                try:
                    parsed = _doc_excel_khtd_cn_upload(f_up.getvalue())
                    if parsed is not None:
                        patch, dem, _bo_qua = parsed
                        if dem == 0:
                            st.session_state[_uid] = True
                            st.info(
                                "Không có dòng KH > 0 để lưu (đã bỏ qua giá trị 0 và ô trống)."
                            )
                        else:
                            kh_moi = dict(kh_cn)
                            kh_moi.update(patch)
                            if _luu_kv(KV_KEY_CN, kh_moi, username):
                                db.ghi_audit(
                                    username,
                                    "upload_khtd_cn",
                                    f"{dem} chỉ tiêu từ Excel",
                                )
                                st.session_state[_uid] = True
                                st.success(
                                    f"✅ Đã lưu **{dem}** chỉ tiêu kế hoạch Chi nhánh từ Excel."
                                )
                                st.rerun()
                except Exception as e:
                    st.error(f"Lỗi xử lý file: {e}")

    # ── Phương thức 2: Nhập thủ công (bảng gọn) ──────────────────────────
    _, ten_map_q = _quet_ct_co_du_no(df_loc)

    # ── Banner trạng thái KH ──
    tong_ct = len(MA_KEYS_CO_KHTD)
    so_ct_co_kh = sum(
        1 for mk in MA_KEYS_CO_KHTD if float(kh_cn.get(mk, 0.0)) > 0
    )
    tong_kh_ty = (
        sum(float(kh_cn.get(mk, 0.0)) for mk in MA_KEYS_CO_KHTD) / 1e12
    )

    if so_ct_co_kh == 0:
        mau = "#fff3cd"
        vien = "#ffc107"
        icon = "🔴"
        noi_dung = f"Chưa có kế hoạch — 0/{tong_ct} chương trình"
    elif so_ct_co_kh < tong_ct:
        mau = "#fff8e1"
        vien = "#ff9800"
        icon = "🟡"
        noi_dung = (
            f"Đã nhập {so_ct_co_kh}/{tong_ct} chương trình · "
            f"Tổng KH: {_fvn(tong_kh_ty, 3)} tỷ đồng"
        )
    else:
        mau = "#e8f5e9"
        vien = "#4caf50"
        icon = "🟢"
        noi_dung = (
            f"Đã nhập đủ {tong_ct}/{tong_ct} chương trình · "
            f"Tổng KH: {_fvn(tong_kh_ty, 3)} tỷ đồng"
        )

    st.markdown(
        f"<div style='padding:8px 14px;background:{mau};border-left:4px solid {vien};"
        f"border-radius:6px;font-size:0.9rem;font-weight:500;margin-bottom:8px'>"
        f"{icon} {noi_dung}</div>",
        unsafe_allow_html=True,
    )

    st.caption("📌 Đơn vị nhập và hiển thị: triệu đồng — số nguyên, không có thập phân")

    with st.expander("ℹ️ Hướng dẫn nhập kế hoạch", expanded=False):
        st.markdown("""
**Cách 1 — Upload Excel** (khuyến nghị):
1. Nhấn **⬇️ Tải file mẫu Excel** → điền số KH vào cột **KH (triệu đồng)** → lưu file
2. Kéo thả file vào ô Upload → nhấn **✅ Xác nhận lưu**

**Cách 2 — Nhập thủ công**:
1. Điền số kế hoạch vào cột **KH Trung ương** và/hoặc **KH Địa phương**
2. Nhấn **💾 Lưu kế hoạch**

> ⚠️ Đơn vị: **triệu đồng**, số nguyên. Cột Thực hiện và Còn phải TH tự động tính từ HSTD — không cần nhập.
""")

    _colw = [3, 1, 1, 1, 1, 1, 1, 1, 1]
    hr1 = st.columns(_colw)
    hr1[0].markdown(_khtd_cn_hdr_cell("", "#f0f4fa"), unsafe_allow_html=True)
    hr1[1].markdown(
        _khtd_cn_hdr_cell("NGUỒN VỐN TRUNG ƯƠNG", "#bbdefb", "#1565c0"),
        unsafe_allow_html=True,
    )
    for j in (2, 3):
        hr1[j].markdown(_khtd_cn_hdr_cell("", "#bbdefb"), unsafe_allow_html=True)
    hr1[4].markdown(
        _khtd_cn_hdr_cell("NGUỒN VỐN ĐỊA PHƯƠNG", "#c8e6c9", "#2e7d32"),
        unsafe_allow_html=True,
    )
    for j in (5, 6):
        hr1[j].markdown(_khtd_cn_hdr_cell("", "#c8e6c9"), unsafe_allow_html=True)
    hr1[7].markdown(
        _khtd_cn_hdr_cell("TỔNG CỘNG", "#ffe0b2", "#e65100"),
        unsafe_allow_html=True,
    )
    hr1[8].markdown(_khtd_cn_hdr_cell("", "#ffe0b2"), unsafe_allow_html=True)

    hr2 = st.columns(_colw)
    hr2[0].markdown(
        _khtd_cn_hdr_cell("Chương trình", "#f0f4fa", "#37474f"),
        unsafe_allow_html=True,
    )
    hr2[1].markdown(
        _khtd_cn_hdr_cell(
            "Kế hoạch Trung ương (triệu đồng)", "#e3f2fd", "#1565c0", bold=True
        ),
        unsafe_allow_html=True,
    )
    hr2[2].markdown(
        _khtd_cn_hdr_cell(
            "Thực hiện Trung ương (triệu đồng)", "#e3f2fd", "#1565c0", bold=True
        ),
        unsafe_allow_html=True,
    )
    hr2[3].markdown(
        _khtd_cn_hdr_cell(
            "Còn phải thực hiện Trung ương (triệu đồng)",
            "#e3f2fd",
            "#1565c0",
            bold=True,
        ),
        unsafe_allow_html=True,
    )
    hr2[4].markdown(
        _khtd_cn_hdr_cell(
            "Kế hoạch Địa phương (triệu đồng)", "#e8f5e9", "#2e7d32", bold=True
        ),
        unsafe_allow_html=True,
    )
    hr2[5].markdown(
        _khtd_cn_hdr_cell(
            "Thực hiện Địa phương (triệu đồng)", "#e8f5e9", "#2e7d32", bold=True
        ),
        unsafe_allow_html=True,
    )
    hr2[6].markdown(
        _khtd_cn_hdr_cell(
            "Còn phải thực hiện Địa phương (triệu đồng)",
            "#e8f5e9",
            "#2e7d32",
            bold=True,
        ),
        unsafe_allow_html=True,
    )
    hr2[7].markdown(
        _khtd_cn_hdr_cell(
            "Thực hiện cả hai nguồn (triệu đồng)",
            "#fff3e0",
            "#e65100",
            bold=True,
        ),
        unsafe_allow_html=True,
    )
    hr2[8].markdown(
        _khtd_cn_hdr_cell(
            "Còn phải thực hiện Tổng cộng (triệu đồng)",
            "#fff3e0",
            "#e65100",
            bold=True,
        ),
        unsafe_allow_html=True,
    )

    def _fvn_form(x: float, d: int = 1) -> str:
        return f"{float(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _md_right(val: str, color: str = "#212121") -> str:
        return (
            f"<div style='text-align:right;color:{color};font-size:0.88rem;"
            f"padding:2px 0'>{val}</div>"
        )

    st.markdown(
        """
<style>
[data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid #e2e8f0 !important;
    padding: 2px 0 !important;
}
[data-testid="stHorizontalBlock"]:hover {
    background-color: #f8fafc !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
    nhom_mau_nen = ["#eef6ff", "#eefaf3", "#fff8ee"]
    idx_nhom = 0
    for tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
        bg = nhom_mau_nen[idx_nhom % len(nhom_mau_nen)]
        idx_nhom += 1
        st.markdown(
            f"<p style='margin:0.8rem 0 0.4rem 0;padding:7px 12px;"
            f"background-color:{bg};border-radius:6px;font-weight:600;"
            f"font-size:0.9rem'>{tieu_de_nhom}</p>",
            unsafe_allow_html=True,
        )
        for ma_ct in ds_ma_ct:
            mk_tw = f"{ma_ct}_TW"
            mk_dp = f"{ma_ct}_DP"
            co_tw = mk_tw in MA_KEYS_CO_KHTD
            co_dp = mk_dp in MA_KEYS_CO_KHTD
            if not co_tw and not co_dp:
                continue
            cols = st.columns(_colw)
            ten_hang = _ten_ct_base(ma_ct, ten_map_q)
            cols[0].markdown(
                f"<div style='font-size:0.88rem;padding:4px 0'>{ten_hang}</div>",
                unsafe_allow_html=True,
            )

            k_tw = f"khtd_cn_inp_{ma_ct}_tw"
            k_dp = f"khtd_cn_inp_{ma_ct}_dp"
            kh_tw_vnd = float(kh_cn.get(mk_tw, 0.0))
            kh_dp_vnd = float(kh_cn.get(mk_dp, 0.0))
            ht_tw = kh_tw_vnd / 1_000_000
            ht_dp = kh_dp_vnd / 1_000_000
            th_tw_trieu = float((th_cn or {}).get(mk_tw, 0.0)) / 1e6
            th_dp_trieu = float((th_cn or {}).get(mk_dp, 0.0)) / 1e6

            if co_tw:
                cols[1].number_input(
                    f"tw_{ma_ct}",
                    value=ht_tw,
                    min_value=0.0,
                    step=1000.0,
                    format="%.0f",
                    label_visibility="collapsed",
                    help="Kế hoạch Trung ương — đơn vị: triệu đồng",
                    key=k_tw,
                )
                kh_tw_trieu = float(
                    st.session_state[k_tw]
                    if k_tw in st.session_state
                    else ht_tw
                )
            else:
                cols[1].caption("—")
                kh_tw_trieu = 0.0

            cols[2].markdown(
                _md_right(_fvn_form(th_tw_trieu, 0)), unsafe_allow_html=True
            )
            if kh_tw_trieu == 0:
                cols[3].markdown(
                    _md_right("—", "#9e9e9e"), unsafe_allow_html=True
                )
            else:
                cpth_tw = kh_tw_trieu - th_tw_trieu
                if cpth_tw < 0:
                    cols[3].markdown(
                        _md_right(_fvn_form(cpth_tw), "#c62828"),
                        unsafe_allow_html=True,
                    )
                elif cpth_tw == 0:
                    cols[3].markdown(
                        _md_right("0,0 ✓", "#2e7d32"), unsafe_allow_html=True
                    )
                else:
                    cols[3].markdown(
                        _md_right(_fvn_form(cpth_tw)), unsafe_allow_html=True
                    )

            if co_dp:
                cols[4].number_input(
                    f"dp_{ma_ct}",
                    value=ht_dp,
                    min_value=0.0,
                    step=1000.0,
                    format="%.0f",
                    label_visibility="collapsed",
                    help="Kế hoạch Địa phương — đơn vị: triệu đồng",
                    key=k_dp,
                )
                kh_dp_trieu = float(
                    st.session_state[k_dp]
                    if k_dp in st.session_state
                    else ht_dp
                )
            else:
                cols[4].caption("—")
                kh_dp_trieu = 0.0

            cols[5].markdown(
                _md_right(_fvn_form(th_dp_trieu, 0)), unsafe_allow_html=True
            )
            if kh_dp_trieu == 0:
                cols[6].markdown(
                    _md_right("—", "#9e9e9e"), unsafe_allow_html=True
                )
            else:
                cpth_dp = kh_dp_trieu - th_dp_trieu
                if cpth_dp < 0:
                    cols[6].markdown(
                        _md_right(_fvn_form(cpth_dp), "#c62828"),
                        unsafe_allow_html=True,
                    )
                elif cpth_dp == 0:
                    cols[6].markdown(
                        _md_right("0,0 ✓", "#2e7d32"), unsafe_allow_html=True
                    )
                else:
                    cols[6].markdown(
                        _md_right(_fvn_form(cpth_dp)), unsafe_allow_html=True
                    )

            th_tong = th_tw_trieu + th_dp_trieu
            cols[7].markdown(
                _md_right(_fvn_form(th_tong, 0)), unsafe_allow_html=True
            )
            kh_tong = kh_tw_trieu + kh_dp_trieu
            cpth_tong = kh_tong - th_tong
            if kh_tong == 0:
                cols[8].markdown(
                    _md_right("—", "#9e9e9e"), unsafe_allow_html=True
                )
            elif cpth_tong < 0:
                cols[8].markdown(
                    _md_right(_fvn_form(cpth_tong), "#c62828"),
                    unsafe_allow_html=True,
                )
            elif cpth_tong == 0:
                cols[8].markdown(
                    _md_right("0,0 ✓", "#2e7d32"), unsafe_allow_html=True
                )
            else:
                cols[8].markdown(
                    _md_right(_fvn_form(cpth_tong)), unsafe_allow_html=True
                )

    tong_kh_trieu_hien_tai = 0.0
    for _tieu_de, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
        for ma_ct in ds_ma_ct:
            mk_tw = f"{ma_ct}_TW"
            mk_dp = f"{ma_ct}_DP"
            if mk_tw in MA_KEYS_CO_KHTD:
                k_tw = f"khtd_cn_inp_{ma_ct}_tw"
                tong_kh_trieu_hien_tai += float(
                    st.session_state[k_tw]
                    if k_tw in st.session_state
                    else float(kh_cn.get(mk_tw, 0.0)) / 1_000_000
                )
            if mk_dp in MA_KEYS_CO_KHTD:
                k_dp = f"khtd_cn_inp_{ma_ct}_dp"
                tong_kh_trieu_hien_tai += float(
                    st.session_state[k_dp]
                    if k_dp in st.session_state
                    else float(kh_cn.get(mk_dp, 0.0)) / 1_000_000
                )
    tong_kh_nhap_form = tong_kh_trieu_hien_tai * 1_000_000

    if tong_kh_nhap_form <= 0:
        st.warning(
            "⚠️ Tất cả chỉ tiêu đang = 0, kiểm tra lại trước khi lưu"
        )

    if st.button("💾 Lưu kế hoạch Chi nhánh", type="primary", key="btn_luu_khtd_cn"):
        patch: dict[str, float] = {}
        for tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
            for ma_ct in ds_ma_ct:
                mk_tw = f"{ma_ct}_TW"
                mk_dp = f"{ma_ct}_DP"
                if mk_tw in MA_KEYS_CO_KHTD:
                    patch[mk_tw] = float(
                        st.session_state.get(f"khtd_cn_inp_{ma_ct}_tw", 0.0)
                    )
                if mk_dp in MA_KEYS_CO_KHTD:
                    patch[mk_dp] = float(
                        st.session_state.get(f"khtd_cn_inp_{ma_ct}_dp", 0.0)
                    )
        tong_kh_luu = sum(v * 1_000_000 for v in patch.values())
        if tong_kh_luu <= 0:
            st.warning(
                "⚠️ Tất cả chỉ tiêu đang = 0, kiểm tra lại trước khi lưu"
            )
        else:
            for ma_key, gia_tri_trieu in patch.items():
                kh_cn[ma_key] = gia_tri_trieu * 1_000_000
            if _luu_kv(KV_KEY_CN, kh_cn, username):
                tw_kh_d = sum(
                    float(kh_cn.get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "TW"
                )
                dp_kh_d = sum(
                    float(kh_cn.get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "DP"
                )
                tw_th_d = sum(
                    float((th_cn or {}).get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "TW"
                )
                dp_th_d = sum(
                    float((th_cn or {}).get(mk, 0.0))
                    for mk, _mc, _t, nv, _tm in CHUONG_TRINH_KHTD
                    if nv == "DP"
                )
                pt_tw = (
                    round(tw_th_d / tw_kh_d * 100, 1) if tw_kh_d > 0 else None
                )
                pt_dp = (
                    round(dp_th_d / dp_kh_d * 100, 1) if dp_kh_d > 0 else None
                )
                all_kh_d = tw_kh_d + dp_kh_d
                all_th_d = tw_th_d + dp_th_d
                pt_all = (
                    round(all_th_d / all_kh_d * 100, 1) if all_kh_d > 0 else None
                )
                db.ghi_audit(
                    username,
                    "luu_khtd_cn",
                    f"{len(patch)} chỉ tiêu, tổng {vn(sum(patch.values()), 1)} triệu",
                )
                st.cache_data.clear()
                st.session_state["khtd_cn_save_info"] = (
                    tw_kh_d,
                    tw_th_d,
                    pt_tw,
                    dp_kh_d,
                    dp_th_d,
                    pt_dp,
                    all_kh_d,
                    all_th_d,
                    pt_all,
                )
                st.rerun()

    _info_luu = st.session_state.pop("khtd_cn_save_info", None)
    if isinstance(_info_luu, tuple) and len(_info_luu) == 9:
        (
            tw_kh_d,
            tw_th_d,
            pt_tw,
            dp_kh_d,
            dp_th_d,
            pt_dp,
            all_kh_d,
            all_th_d,
            pt_all,
        ) = _info_luu
        _pt = lambda p: (f"{_fvn(p, 1)}%") if p is not None else "—"
        st.info(
            "💰 "
            f"KH Trung ương: **{_fvn(tw_kh_d / 1e6, 1)}** triệu đồng · "
            f"Thực hiện: **{_fvn(tw_th_d / 1e6, 0)}** triệu đồng · "
            f"Đạt **{_pt(pt_tw)}**\n\n"
            f"KH Địa phương: **{_fvn(dp_kh_d / 1e6, 1)}** triệu đồng · "
            f"Thực hiện: **{_fvn(dp_th_d / 1e6, 0)}** triệu đồng · "
            f"Đạt **{_pt(pt_dp)}**\n\n"
            f"Tổng cộng: KH **{_fvn(all_kh_d / 1e6, 1)}** triệu đồng · "
            f"Thực hiện: **{_fvn(all_th_d / 1e6, 0)}** triệu đồng · "
            f"Đạt **{_pt(pt_all)}**"
        )

    # ── Tóm tắt hiện trạng (luôn hiển thị) ───────────────────────────────
    st.markdown("##### 📊 Tóm tắt hiện trạng")
    _hien_thi_bang_cn_readonly(
        kh_cn,
        th_cn,
        ds_ct_loc=[mk for mk, _ in ds_ct],
        df_loc=df_loc,
        username=username,
    )

    st.divider()
    _section_van_ban_qd_cn(role, username)


def _tab_khtd_theo_xa(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    st.subheader("📍 Kế hoạch Tín dụng theo Xã")

    co_quyen = get_permissions(role)["can_edit_khtd"]
    if not co_quyen:
        st.warning("⚠️ Chỉ Admin / Manager mới được nhập kế hoạch theo Xã.")
        return

    kh_xa = _doc_kv(KV_KEY_XA)

    # ── Chọn PGD → Xã ────────────────────────────────────────────────────
    col_pgd, col_xa = st.columns(2)
    with col_pgd:
        pgd_chon = st.selectbox("Chọn PGD", DS_PGD, key="khtd_xa_pgd_sel")
    danh_sach_xa = PGD_XA_MAP.get(pgd_chon, [])
    with col_xa:
        xa_chon = st.selectbox(
            "Chọn Xã", danh_sach_xa if danh_sach_xa else ["(Không có xã)"],
            key="khtd_xa_xa_sel",
        )

    if not danh_sach_xa:
        st.warning(f"Chưa có danh sách xã cho **{pgd_chon}**.")
        return

    # ── Upload Excel hàng loạt ────────────────────────────────────────────
    with st.expander("📤 Upload Excel kế hoạch hàng loạt", expanded=False):
        st.caption(
            "Cấu trúc file: **Cột A** = Tên xã · **Cột B** = Mã CT (vd: `1_TW`) · "
            "**Cột C** = Giá trị (triệu đồng)"
        )
        file_up = st.file_uploader(
            "Chọn file Excel",
            type=["xlsx", "xls"],
            key="khtd_xa_file_upload",
        )
        if file_up:
            try:
                df_up = pd.read_excel(BytesIO(file_up.read()), header=0)
                dem = 0
                for _, row in df_up.iterrows():
                    ten_xa = str(row.iloc[0]).strip()
                    ma_ct  = str(row.iloc[1]).strip()
                    val    = float(row.iloc[2]) * 1_000_000 if pd.notna(row.iloc[2]) else 0.0
                    if ten_xa and ma_ct and val > 0:
                        kh_xa[f"{ten_xa}|{ma_ct}"] = val
                        dem += 1
                if _luu_kv(KV_KEY_XA, kh_xa, username):
                    db.ghi_audit(username, "upload_khtd_xa",
                                 f"{dem} chỉ tiêu từ Excel")
                    st.success(f"✅ Đã lưu {dem} chỉ tiêu kế hoạch xã từ file Excel!")
                    st.rerun()
            except Exception as e:
                st.error(f"Lỗi đọc file Excel: {e}")

    df_loc = df_full
    if df_loc is not None and not df_loc.empty and COT_TEN_PGD in df_loc.columns:
        pgd_norm = str(pgd_chon).strip()
        s_pgd = df_loc[COT_TEN_PGD].astype(str).str.strip()
        df_loc = df_loc[s_pgd == pgd_norm]

    th_xa = (
        _tinh_thuc_hien_theo_ct(df_loc)
        if df_loc is not None and not df_loc.empty
        else {}
    )

    st.divider()
    _, ten_map_q = _quet_ct_co_du_no(df_loc)
    st.caption("📌 Đơn vị nhập và hiển thị: triệu đồng")

    _colw_xa = [3, 1, 1, 1, 1]  # Chương trình | KH TW | TH TW | KH ĐP | TH ĐP

    # ── Header dòng 1 ──
    hr1 = st.columns(_colw_xa)
    hr1[0].markdown(_khtd_cn_hdr_cell("", "#f0f4fa"), unsafe_allow_html=True)
    hr1[1].markdown(
        _khtd_cn_hdr_cell("NGUỒN VỐN TRUNG ƯƠNG", "#bbdefb", "#1565c0"),
        unsafe_allow_html=True,
    )
    hr1[2].markdown(_khtd_cn_hdr_cell("", "#bbdefb"), unsafe_allow_html=True)
    hr1[3].markdown(
        _khtd_cn_hdr_cell("NGUỒN VỐN ĐỊA PHƯƠNG", "#c8e6c9", "#2e7d32"),
        unsafe_allow_html=True,
    )
    hr1[4].markdown(_khtd_cn_hdr_cell("", "#c8e6c9"), unsafe_allow_html=True)

    # ── Header dòng 2 ──
    hr2 = st.columns(_colw_xa)
    hr2[0].markdown(
        _khtd_cn_hdr_cell("Chương trình", "#f0f4fa", "#37474f", bold=True),
        unsafe_allow_html=True,
    )
    hr2[1].markdown(
        _khtd_cn_hdr_cell(
            "Kế hoạch Trung ương (triệu đồng)", "#e3f2fd", "#1565c0", bold=True
        ),
        unsafe_allow_html=True,
    )
    hr2[2].markdown(
        _khtd_cn_hdr_cell(
            "Thực hiện TW (triệu đồng)", "#e3f2fd", "#1565c0", bold=True
        ),
        unsafe_allow_html=True,
    )
    hr2[3].markdown(
        _khtd_cn_hdr_cell(
            "Kế hoạch Địa phương (triệu đồng)", "#e8f5e9", "#2e7d32", bold=True
        ),
        unsafe_allow_html=True,
    )
    hr2[4].markdown(
        _khtd_cn_hdr_cell(
            "Thực hiện ĐP (triệu đồng)", "#e8f5e9", "#2e7d32", bold=True
        ),
        unsafe_allow_html=True,
    )

    # ── CSS kẻ bảng ──
    st.markdown(
        """
<style>
[data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid #e2e8f0 !important;
    padding: 2px 0 !important;
}
[data-testid="stHorizontalBlock"]:hover {
    background-color: #f8fafc !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # ── Nhóm màu nền ──
    nhom_mau_nen = ["#eef6ff", "#eefaf3", "#fff8ee"]
    idx_nhom = 0

    with st.form(f"form_khtd_xa_{pgd_chon}_{xa_chon}"):
        gia_tri_moi: dict[str, float] = {}

        for tieu_de_nhom, ds_ma_ct in KHTD_CN_NHOM_MA_CT:
            bg = nhom_mau_nen[idx_nhom % len(nhom_mau_nen)]
            idx_nhom += 1
            st.markdown(
                f"<p style='margin:0.8rem 0 0.4rem 0;padding:7px 12px;"
                f"background-color:{bg};border-radius:6px;font-weight:600;"
                f"font-size:0.9rem'>{tieu_de_nhom}</p>",
                unsafe_allow_html=True,
            )
            for ma_ct in ds_ma_ct:
                mk_tw = f"{ma_ct}_TW"
                mk_dp = f"{ma_ct}_DP"
                khoa_tw = f"{xa_chon}|{mk_tw}"
                khoa_dp = f"{xa_chon}|{mk_dp}"
                co_tw = mk_tw in MA_KEYS_CO_KHTD
                co_dp = mk_dp in MA_KEYS_CO_KHTD
                if not co_tw and not co_dp:
                    continue

                cols = st.columns(_colw_xa)
                ten_hang = _ten_ct_base(ma_ct, ten_map_q)
                cols[0].markdown(
                    f"<div style='font-size:0.88rem;padding:4px 0'>{ten_hang}</div>",
                    unsafe_allow_html=True,
                )

                if co_tw:
                    gia_tri_moi[khoa_tw] = cols[1].number_input(
                        f"tw_{ma_ct}",
                        value=float(kh_xa.get(khoa_tw, 0.0)) / 1_000_000,
                        min_value=0.0,
                        step=1000.0,
                        format="%.0f",
                        label_visibility="collapsed",
                        help="Kế hoạch Trung ương — đơn vị: triệu đồng",
                        key=f"khtd_xa_inp_{xa_chon}_{ma_ct}_tw",
                    )
                else:
                    cols[1].caption("—")

                vnd_tw = float(th_xa.get(mk_tw, 0.0) or 0.0)
                trieu_tw = vnd_tw / 1e6
                txt_th_tw = (
                    f"{_fmt_vn(trieu_tw, 1)} tr" if trieu_tw > 0 else "—"
                )
                cols[2].markdown(
                    f"<div style='text-align:right;font-size:0.88rem;padding:4px 0'>"
                    f"{txt_th_tw}</div>",
                    unsafe_allow_html=True,
                )

                if co_dp:
                    gia_tri_moi[khoa_dp] = cols[3].number_input(
                        f"dp_{ma_ct}",
                        value=float(kh_xa.get(khoa_dp, 0.0)) / 1_000_000,
                        min_value=0.0,
                        step=1000.0,
                        format="%.0f",
                        label_visibility="collapsed",
                        help="Kế hoạch Địa phương — đơn vị: triệu đồng",
                        key=f"khtd_xa_inp_{xa_chon}_{ma_ct}_dp",
                    )
                else:
                    cols[3].caption("—")

                vnd_dp = float(th_xa.get(mk_dp, 0.0) or 0.0)
                trieu_dp = vnd_dp / 1e6
                txt_th_dp = (
                    f"{_fmt_vn(trieu_dp, 1)} tr" if trieu_dp > 0 else "—"
                )
                cols[4].markdown(
                    f"<div style='text-align:right;font-size:0.88rem;padding:4px 0'>"
                    f"{txt_th_dp}</div>",
                    unsafe_allow_html=True,
                )

        if st.form_submit_button("💾 Lưu kế hoạch xã này", type="primary"):
            for khoa, gia_tri_trieu in gia_tri_moi.items():
                kh_xa[khoa] = gia_tri_trieu * 1_000_000
            if _luu_kv(KV_KEY_XA, kh_xa, username):
                db.ghi_audit(username, "luu_khtd_xa",
                             f"PGD: {pgd_chon} — Xã: {xa_chon}")
                st.success(f"✅ Đã lưu kế hoạch cho xã **{xa_chon}**")
                st.rerun()


def render_nhap_cn(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    _tab_khtd_chi_nhanh(role, username, df_full)


def render_nhap_pgd(role: str, username: str, df_full: "pd.DataFrame | None") -> None:
    _tab_khtd_theo_xa(role, username, df_full)

