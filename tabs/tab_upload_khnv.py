"""
Tab Upload KH-NV — Phòng Kế hoạch Nghiệp vụ.
──────────────────────────────────────────────
Quyền: role in ("admin", "manager")

Giao diện:
  - Selectbox chọn đơn vị: ["Hội sở Chi nhánh tỉnh"] + DS_PGD (22 đơn vị)
  - 4 uploader theo cột ngang: HSTD | NQ11 | GQVL | CDTOTKVV
  - Nút "📤 Upload" — xử lý cả 4 file cùng lúc
  - Kiểm tra tên đơn vị trong file trước khi lưu
  - Tự động merge toàn CN sau khi lưu HSTD/NQ11/GQVL
  - Bảng trạng thái 22 hàng × 5 cột
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import hashlib
import os
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from auth import la_phan_he_cn, normalize_role
from config import (
    DS_PGD, DON_VI_CHI_NHANH, MA_PGD_MAP,
    baseline_path, baseline_cache, danh_sach_nam_baseline,
    baseline_pgd_path, baseline_pgd_path_loai,
    danh_sach_nam_baseline_pgd, trang_thai_baseline_pgd, trang_thai_baseline_pgd_loai,
    LOAI_BASELINE,
)
from data.pgd import (
    duong_dan_pgd,
    kiem_tra_file_ton_tai_pgd,
    lay_trang_thai_upload_pgd,
)
from services.upload_service import (
    KetQuaUpload,
    kiem_tra_file,
    lay_meta_merge,
    merge_du_lieu_toan_cn,
    merge_baseline_toan_cn,
    danh_gia_chat_luong_file_upload,
)
from utils import fmt_so, hien_thi_dataframe_phan_trang


def _md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _md5_file(path: str) -> str:
    try:
        return hashlib.md5(open(path, "rb").read()).hexdigest()
    except Exception:
        return ""


# Bảng alias tên đơn vị: tên trong file Excel → tên nội bộ hệ thống  
# Dùng để so sánh "upload nhầm đơn vị" không bị lỗi do tên khác nhau
# "PGD Biên Hòa" là alias — trong HSTD tên thực là "Hội sở Chi nhánh tỉnh"
_TEN_DV_ALIAS: dict[str, str] = {
    "Hội sở CN Đồng Nai":      DON_VI_CHI_NHANH,
    "Hội sở CN tỉnh":          DON_VI_CHI_NHANH,
    "CN Đồng Nai":             DON_VI_CHI_NHANH,
    "PGD Biên Hòa":            DON_VI_CHI_NHANH,
    # Thêm alias khác nếu phát sinh
}

def _chuan_hoa_ten(ten: str) -> str:
    """Chuẩn hóa tên đơn vị từ file về tên nội bộ (tra _TEN_DV_ALIAS, fallback giữ nguyên)."""
    return _TEN_DV_ALIAS.get(ten.strip(), ten.strip())


def _ten_doc_ve_don_vi_chuan(val: str) -> str | None:
    """Map tên đọc từ file → đúng một phần tử trong DS_DON_VI (để `in DS_DON_VI` khi quét thư mục)."""
    if not val or str(val).strip().lower() in ("nan", "none", ""):
        return None
    t = _chuan_hoa_ten(str(val).strip())
    if t in DS_DON_VI:
        return t
    tl = t.lower()
    for ten_dv in DS_DON_VI:
        if ten_dv.lower() in tl:
            return ten_dv
    return None


# ── Danh sách 22 đơn vị ──────────────────────────────────────────────────────
DS_DON_VI: list[str] = [DON_VI_CHI_NHANH] + DS_PGD


# ── Đọc tên đơn vị từ file upload (kiểm tra trước khi lưu) ───────────────────

def _lay_ten_don_vi_trong_file(file_bytes: bytes, loai: str) -> str | None:
    """
    Đọc tên đơn vị từ file Excel theo từng loại.
    Trả về tên đơn vị (str) hoặc None nếu không đọc được.

    HSTD/GQVL : header=4, cột "Tên PGD" (sheet BCQUERY / Sheet1)
    NQ11       : header=4, cột "Mã PGD" → tra MA_PGD_MAP
    CDTOTKVV   : header=7, dropna("Mã đơn vị"), cột "Tên đơn vị"
    """
    try:
        buf = BytesIO(file_bytes)
        if loai == "hstd":
            df = pd.read_excel(buf, sheet_name="BCQUERY", header=4, nrows=5)
            df = df.iloc[:, 1:]
            cot = next((c for c in df.columns if "tên pgd" in str(c).lower()), None)
            if cot is None:
                return None
            vals = df[cot].dropna().astype(str).unique()
            return str(vals[0]).strip() if len(vals) > 0 else None

        elif loai == "nq11":
            df = pd.read_excel(buf, sheet_name="BCQUERY", header=4, nrows=5)
            df = df.iloc[:, 1:]
            cot = next((c for c in df.columns if "mã pgd" in str(c).lower()), None)
            if cot is None:
                return None
            raw = df[cot].dropna().iloc[0] if not df[cot].dropna().empty else None
            if raw is None:
                ma_pgd = None
            else:
                try:
                    # Xử lý trường hợp pandas đọc ô số dạng float (vd: 4602.0 → "004602")
                    ma_pgd = str(int(float(raw))).zfill(6)
                except (ValueError, TypeError):
                    ma_pgd = str(raw).strip().zfill(6)
            if ma_pgd is None:
                return None
            return MA_PGD_MAP.get(ma_pgd)

        elif loai == "gqvl":
            df = pd.read_excel(buf, sheet_name="Sheet1", header=4, nrows=5)
            df = df.iloc[:, 1:]
            cot = next((c for c in df.columns if "tên pgd" in str(c).lower()), None)
            if cot is None:
                return None
            vals = df[cot].dropna().astype(str).unique()
            return str(vals[0]).strip() if len(vals) > 0 else None

        elif loai == "cdtotkvv":
            df = pd.read_excel(buf, header=7, nrows=10)
            # Tìm cột "Mã đơn vị"
            cot_ma = next((c for c in df.columns if "mã đơn vị" in str(c).lower()), None)
            cot_ten = next((c for c in df.columns if "tên đơn vị" in str(c).lower()), None)
            if cot_ten is None:
                return None
            if cot_ma is not None:
                df = df.dropna(subset=[cot_ma])
            vals = df[cot_ten].dropna().astype(str).unique()
            return str(vals[0]).strip() if len(vals) > 0 else None

    except Exception:
        return None


def _kiem_tra_don_vi(file_bytes: bytes, loai: str, ten_dv_chon: str) -> tuple[bool, str]:
    """
    Kiểm tra tên đơn vị trong file có khớp với đơn vị đang chọn không.
    Trả về (khop: bool, thong_bao: str).
    """
    ten_trong_file = _lay_ten_don_vi_trong_file(file_bytes, loai)
    if ten_trong_file is None:
        # Không đọc được tên → cho phép qua (cảnh báo nhẹ)
        return True, "⚠️ Không đọc được tên đơn vị từ file — tiếp tục lưu."
    if _chuan_hoa_ten(ten_trong_file) == _chuan_hoa_ten(ten_dv_chon):
        return True, f"✅ Đơn vị khớp: **{_chuan_hoa_ten(ten_trong_file)}**"
    return False, (
        f"⚠️ Upload nhầm đơn vị! File chứa: **{ten_trong_file}** | Đang chọn: **{ten_dv_chon}**"
    )


# ── Bảng trạng thái upload ────────────────────────────────────────────────────

def _hien_thi_bang_trang_thai() -> None:
    """Bảng trạng thái 22 hàng × 6 cột: Đơn vị | HSTD | NQ11 | GQVL | CDTOTKVV | 31/12/YYYY."""
    from datetime import date as _date
    df_tt = st.session_state.get(
        "trang_thai_upload_pgd",
        lay_trang_thai_upload_pgd(DS_DON_VI),
    ).copy()

    # Thêm cột baseline 31/12 — hiển thị năm gần nhất có dữ liệu
    ds_nam_bl = danh_sach_nam_baseline_pgd()
    nam_bl = ds_nam_bl[0] if ds_nam_bl else (_date.today().year - 1)
    tt_bl = trang_thai_baseline_pgd(nam_bl)
    col_bl = f"31/12/{nam_bl}"
    df_tt[col_bl] = df_tt["Đơn vị"].map(
        lambda dv: "✅ Có" if tt_bl.get(dv, False) else "❌ Chưa có"
    )

    # Tô màu badge theo tiền tố: ✅ xanh | ⚠️ vàng | ❌ đỏ
    def style_trang_thai(val: str) -> str:
        v = str(val)
        if v.startswith("✅"):
            return "background-color: #d4edda; color: #155724; font-weight: bold"
        if v.startswith("⚠️"):
            return "background-color: #fff3cd; color: #856404"
        if v.startswith("❌"):
            return "background-color: #f8d7da; color: #721c24"
        return ""

    cols_loai = ["HSTD", "NQ11", "GQVL", "CDTOTKVV", col_bl]
    styled = df_tt.style.map(style_trang_thai, subset=cols_loai)
    hien_thi_dataframe_phan_trang(styled, key="upload_khnv_trang_thai", height=800)


# ── Giao diện upload chính ────────────────────────────────────────────────────

def _render_upload_form(ten_dv: str, prefix: str, username: str) -> None:
    """Form upload 4 file theo đơn vị đã chọn."""
    st.markdown(f"##### 📤 Upload file cho: **{ten_dv}**")

    _ver = st.session_state.setdefault(f"{prefix}_upload_ver", 0)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.caption("📊 HSTD Chi tiết")
        f_hstd = st.file_uploader("HSTD", type=["xlsx", "xls"],
                                   key=f"{prefix}_hstd_{_ver}", label_visibility="collapsed")
    with c2:
        st.caption("📑 Sao kê NQ11")
        f_nq11 = st.file_uploader("NQ11", type=["xlsx", "xls"],
                                   key=f"{prefix}_nq11_{_ver}", label_visibility="collapsed")
    with c3:
        st.caption("📋 Sao kê GQVL")
        f_gqvl = st.file_uploader("GQVL", type=["xlsx", "xls"],
                                   key=f"{prefix}_gqvl_{_ver}", label_visibility="collapsed")
    with c4:
        st.caption("🏆 Chấm điểm Tổ TK&VV")
        f_cdtotkvv = st.file_uploader("CDTOTKVV", type=["xlsx", "xls"],
                                       key=f"{prefix}_cdtotkvv_{_ver}", label_visibility="collapsed")

    co_file = any(f is not None for f in [f_hstd, f_nq11, f_gqvl, f_cdtotkvv])
    if not co_file:
        st.info("Chọn ít nhất 1 file để bắt đầu upload.")
        return

    if st.button("📤 Upload", type="primary", key=f"{prefix}_btn_upload"):
        with st.spinner("⏳ Đang xử lý file..."):
            _xu_ly_upload(ten_dv, username,
                          f_hstd, f_nq11, f_gqvl, f_cdtotkvv, prefix)


def _xu_ly_mot_file_khnv(
    loai: str,
    ten_file: str,
    ten_hien: str,
    file_bytes: bytes,
    ten_dv: str,
) -> tuple[str, KetQuaUpload, bool, tuple[str, str] | None]:
    """
    Xử lý một file: kiểm tra → DQ → lưu. Chạy trong thread riêng.
    Trả về (loai, ket_qua, can_merge, (action, audit_detail) | None).
    Không gọi st.* hay db.* — thread-safe.
    """
    from data.pgd import luu_file_pgd as _luu_pgd

    mb = len(file_bytes) / 1024 / 1024

    ok_kt, msg_kt = kiem_tra_file(ten_file, file_bytes)
    if not ok_kt:
        return loai, KetQuaUpload(False, msg_kt), False, None

    khop, msg_khop = _kiem_tra_don_vi(file_bytes, loai, ten_dv)
    if not khop:
        return loai, KetQuaUpload(False, msg_khop), False, None

    _, _msg_dq, bao_cao_dq = danh_gia_chat_luong_file_upload(loai, file_bytes)
    dq_pct = bao_cao_dq.get("ti_le_dat_chuan", 0)

    try:
        if loai == "cdtotkvv":
            from data.cdtotkvv import doc_thang_nam_tu_file
            from data.pgd import luu_file_pgd_voi_lich_su

            thang_tu_file = doc_thang_nam_tu_file(file_bytes)
            if thang_tu_file:
                path = luu_file_pgd_voi_lich_su(ten_dv, loai, file_bytes, thang_tu_file)
                msg = (
                    f"✅ {ten_hien} ({mb:.1f} MB) · Tháng {thang_tu_file} · DQ {dq_pct}%"
                )
            else:
                path = _luu_pgd(ten_dv, loai, file_bytes)
                msg = (
                    f"✅ {ten_hien} ({mb:.1f} MB) "
                    f"· ⚠️ Không đọc được tháng từ file · DQ {dq_pct}%"
                )
            audit = (
                "upload_pgd_khnv",
                f"CDTOTKVV — {ten_dv} tháng={thang_tu_file or 'unknown'} ({mb:.1f} MB)",
            )
            return loai, KetQuaUpload(True, msg, path), False, audit
        else:
            path = _luu_pgd(ten_dv, loai, file_bytes)
            can_merge = loai in ("hstd", "nq11", "gqvl")
            msg = f"✅ {ten_hien} ({mb:.1f} MB) · DQ {dq_pct}%"
            audit = ("upload_pgd_khnv", f"{loai.upper()} — {ten_dv} ({mb:.1f} MB)")
            return loai, KetQuaUpload(True, msg, path), can_merge, audit
    except Exception as e:
        return loai, KetQuaUpload(False, f"Lỗi lưu: {e}"), False, None


def _xu_ly_upload(
    ten_dv: str,
    username: str,
    f_hstd, f_nq11, f_gqvl, f_cdtotkvv,
    prefix: str,
) -> None:
    """Xử lý upload song song 4 file rồi ghi audit và merge."""
    danh_sach_file = [
        ("hstd",     f_hstd,     "📊 HSTD"),
        ("nq11",     f_nq11,     "📑 NQ11"),
        ("gqvl",     f_gqvl,     "📋 GQVL"),
        ("cdtotkvv", f_cdtotkvv, "🏆 CDTOTKVV"),
    ]

    # Đọc bytes trong main thread (đã in-memory, nhanh) trước khi vào thread
    file_data = [
        (loai, f_obj.name, ten_hien, f_obj.read())
        for loai, f_obj, ten_hien in danh_sach_file
        if f_obj is not None
    ]

    ket_qua_upload: dict[str, KetQuaUpload] = {}
    can_merge = False
    audit_records: list[tuple[str, str]] = []

    # Xử lý song song — I/O-bound nên thread hiệu quả
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                _xu_ly_mot_file_khnv, loai, ten_file, ten_hien, fbytes, ten_dv
            ): loai
            for loai, ten_file, ten_hien, fbytes in file_data
        }
        for future in as_completed(futures):
            loai_r, kq_r, cm_r, audit_r = future.result()
            ket_qua_upload[loai_r] = kq_r
            if cm_r:
                can_merge = True
            if audit_r:
                audit_records.append(audit_r)

    # Ghi audit tuần tự sau khi tất cả thread xong
    for action, detail in audit_records:
        db.ghi_audit(username, action, detail)

    # Hiển thị kết quả từng file trước rerun (sẽ mất sau rerun)
    cols = st.columns(4)
    loai_list = ["hstd", "nq11", "gqvl", "cdtotkvv"]
    nhan_list  = ["📊 HSTD", "📑 NQ11", "📋 GQVL", "🏆 CDTOTKVV"]
    for col, loai, nhan in zip(cols, loai_list, nhan_list):
        kq = ket_qua_upload.get(loai)
        if kq is None:
            col.info(f"**{nhan}**\n\nKhông có file")
        elif kq.thanh_cong:
            col.success(f"**{nhan}**\n\n{kq.thong_bao}")
        else:
            col.warning(f"**{nhan}**\n\n{kq.thong_bao}")

    # Ghi cờ cho fragment merge xử lý sau (không merge đồng bộ ở đây)
    if can_merge:
        for loai in ("hstd", "nq11", "gqvl"):
            if loai in ket_qua_upload and ket_qua_upload[loai].thanh_cong:
                st.session_state[f"can_merge_{loai}"] = True
        st.info("✅ File đã lưu. Nhấn nút bên dưới để cập nhật dữ liệu.")

    st.cache_data.clear()
    # Lưu kết quả vào session để render sau rerun
    st.session_state["khnv_ket_qua_upload"] = {
        k: {"thanh_cong": v.thanh_cong, "thong_bao": v.thong_bao}
        for k, v in ket_qua_upload.items()
    }
    # Reset file uploaders nếu có ít nhất 1 file upload thành công
    if any(v.thanh_cong for v in ket_qua_upload.values()):
        st.session_state[f"{prefix}_upload_ver"] = (
            st.session_state.get(f"{prefix}_upload_ver", 0) + 1
        )
        # Xóa cache bảng trạng thái để hiển thị đúng sau rerun
        st.session_state.pop("trang_thai_upload_pgd", None)
    st.rerun()


# ── Nhận diện PGD từ nội dung file (import hàng loạt) ─────────────────────────


def _nhan_dien_loai_tu_noi_dung(data: bytes) -> str | None:
    """
    Nhận diện loại file từ nội dung — không phụ thuộc tên file.
      HSTD     : sheet BCQUERY, header row 5 có cột 'Tên PGD'
      NQ11     : sheet BCQUERY, header row 5 không có 'Tên PGD', có 'Mã ĐVUT'
      GQVL     : không có BCQUERY, có Sheet1
      CDTOTKVV : không có BCQUERY, không có Sheet1,
                 row 10 có cột 'stt' + 'ma_dv' + 'tong_diem'
    """
    try:
        xl = pd.ExcelFile(BytesIO(data))
        sheets_upper = [s.upper() for s in xl.sheet_names]

        # ── HSTD hoặc NQ11 ───────────────────────────────────────────
        if "BCQUERY" in sheets_upper:
            real = xl.sheet_names[sheets_upper.index("BCQUERY")]
            df = pd.read_excel(
                BytesIO(data), sheet_name=real, header=4, nrows=1
            )
            cols = [str(c).strip().lower() for c in df.columns]
            if any("tên pgd" in c for c in cols):
                return "hstd"
            if any(
                "mã đvut" in c or "mã dvut" in c or "tến đvut" in c for c in cols
            ):
                return "nq11"
            # Fallback: BCQUERY nhưng không rõ → coi là NQ11
            return "nq11"

        # ── GQVL / CDTOTKVV ───────────────────────────────────────────
        if "SHEET1" in sheets_upper or any(
            s for s in sheets_upper
            if s not in ("BCQUERY",) and not s.startswith("_")
        ):
            try:
                if "SHEET1" in sheets_upper:
                    real = xl.sheet_names[sheets_upper.index("SHEET1")]
                    df_check = pd.read_excel(
                        BytesIO(data), sheet_name=real,
                        header=7, nrows=1
                    )
                    cols_check = [str(c).strip().lower() for c in df_check.columns]
                    if any("tên đơn vị" in c for c in cols_check):
                        return "cdtotkvv"
                    if any("tên pgd" in c for c in cols_check):
                        return "gqvl"
                    return "gqvl"

                real = xl.sheet_names[0]
                df_check = pd.read_excel(
                    BytesIO(data), sheet_name=real,
                    header=7, nrows=2
                )
                cols_check = [str(c).strip().lower() for c in df_check.columns]
                if any(
                    "khế ước" in c or "khe uoc" in c
                    or "dư nợ" in c or "du no" in c
                    or "mã kh" in c
                    for c in cols_check
                ):
                    return "gqvl"
            except Exception:
                pass

        # ── CDTOTKVV ─────────────────────────────────────────────────
        df2 = pd.read_excel(BytesIO(data), header=None, skiprows=9, nrows=2)
        if not df2.empty:
            vals = [
                str(v).strip().lower()
                for v in df2.iloc[0].tolist()
                if pd.notna(v)
            ]
            if any("stt" in v for v in vals) and any(
                "ma_dv" in v or "mã" in v for v in vals
            ):
                return "cdtotkvv"

    except Exception:
        pass
    return None


def _tim_ten_pgd_tu_noi_dung(file_bytes: bytes, loai: str) -> str | None:
    """
    Đọc tối thiểu nội dung file để nhận diện tên PGD (quét thư mục / import hàng loạt).

    HSTD/NQ11: sheet BCQUERY, header ở dòng 5 (pandas header=4), 1 dòng dữ liệu, cột "Tên PGD".
    GQVL: Sheet1, header=7 (khớp data/hstd.doc_file_gqvl).
    CDTOTKVV: quét tối đa 15 dòng đầu (layout không cố định).
    """
    buf = BytesIO(file_bytes)
    try:
        if loai in ("hstd", "nq11"):
            df = None
            try:
                df = pd.read_excel(
                    buf,
                    sheet_name="BCQUERY",
                    header=4,
                    nrows=1,
                    usecols=["Tên PGD"],
                )
            except (ValueError, KeyError):
                buf.seek(0)
                df_wide = pd.read_excel(
                    buf, sheet_name="BCQUERY", header=4, nrows=5
                ).iloc[:, 1:]
                cot = next(
                    (c for c in df_wide.columns if "tên pgd" in str(c).lower()),
                    None,
                )
                if cot is not None:
                    df = df_wide[[cot]].head(1)

            if df is not None and not df.empty:
                col = df.columns[0]
                raw = str(df[col].iloc[0]).strip()
                hit = _ten_doc_ve_don_vi_chuan(raw)
                if hit:
                    return hit

            if loai == "nq11":
                buf.seek(0)
                df_m = pd.read_excel(
                    buf, sheet_name="BCQUERY", header=4, nrows=5
                ).iloc[:, 1:]
                cot_ma = next(
                    (c for c in df_m.columns if "mã pgd" in str(c).lower()),
                    None,
                )
                if cot_ma is not None and not df_m[cot_ma].dropna().empty:
                    ma_pgd = str(df_m[cot_ma].dropna().iloc[0]).strip().zfill(6)
                    ten_ma = MA_PGD_MAP.get(ma_pgd)
                    if ten_ma and ten_ma in DS_DON_VI:
                        return ten_ma
            return None

        if loai == "gqvl":
            df = pd.read_excel(buf, sheet_name="Sheet1", header=7, nrows=10)
            if df.empty:
                return None

            cot_ma = next(
                (
                    c
                    for c in df.columns
                    if "mã đơn vị" in str(c).strip().lower()
                    or "ma don vi" in str(c).strip().lower()
                ),
                None,
            )
            if cot_ma is None:
                cot_ma = df.columns[1] if len(df.columns) > 1 else df.columns[0]

            s = df[cot_ma].dropna()
            if s.empty:
                return None

            raw = s.iloc[0]
            try:
                ma = str(int(float(raw))).zfill(6)
            except Exception:
                ma = str(raw).strip()
                digits = "".join(ch for ch in ma if ch.isdigit())
                if digits:
                    ma = digits.zfill(6)

            ten_ma = MA_PGD_MAP.get(ma)
            if ten_ma and ten_ma in DS_DON_VI:
                return ten_ma
            return ten_ma

        if loai == "cdtotkvv":
            df = pd.read_excel(buf, header=None, nrows=15)
            for _, row in df.iterrows():
                for cell in row:
                    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
                        continue
                    hit = _ten_doc_ve_don_vi_chuan(str(cell).strip())
                    if hit:
                        return hit
            return None

    except Exception:
        return None
    return None


def _folder_scan_trang_thai_row(r: dict) -> str:
    """Trạng thái hiển thị cho một dòng quét thư mục (tương thích session cũ thiếu key)."""
    if r.get("trang_thai"):
        return str(r["trang_thai"])
    ten_p = r["ten_pgd"]
    if r["nhan_dien"] and ten_p not in (
        "❓ Không nhận diện được",
        "❓ Lỗi đọc file",
    ):
        return "🔄 Cập nhật" if kiem_tra_file_ton_tai_pgd(ten_p, r["loai"]) else "🆕 Mới"
    return "❓ Không nhận diện được"


def _xu_ly_import_folder(danh_sach: list[dict], username: str) -> None:
    """Import song song theo 3 bước: đọc file, ghi file, rồi merge 1 lần/loại."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from data.pgd import luu_file_pgd as _ghi_file_pgd

    danh_sach_import = [r for r in danh_sach if r.get("co_the_import", False)]

    if not danh_sach_import:
        st.info("✅ Không có file nào cần import")
        return

    thanh_cong: list[dict] = []
    that_bai: list[str] = []
    loai_da_luu: set[str] = set()

    def _doc_file(r: dict) -> tuple[dict, bytes | None, str | None]:
        try:
            return r, Path(r["path"]).read_bytes(), None
        except Exception as e:
            return r, None, str(e)

    progress = st.progress(0.0, text="⏳ Đang đọc file...")
    tat_ca_bytes: list[tuple[dict, bytes]] = []

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_doc_file, r): r for r in danh_sach_import}
        for i, future in enumerate(as_completed(futures)):
            r, data, err = future.result()
            if err:
                that_bai.append(f"{r['ten_file']}: {err}")
            elif data is not None:
                tat_ca_bytes.append((r, data))
            progress.progress(
                ((i + 1) / len(danh_sach_import)) * 0.4,
                text=f"⏳ Đọc file {i + 1}/{len(danh_sach_import)}...",
            )

    def _ghi(r: dict, data: bytes) -> tuple[dict, str | None]:
        try:
            if r["loai"] == "cdtotkvv":
                from data.cdtotkvv import doc_thang_nam_tu_file
                from data.pgd import luu_file_pgd_voi_lich_su

                thang = doc_thang_nam_tu_file(data)
                if thang:
                    _ghi_file_pgd(r["ten_pgd"], r["loai"], data)
                    luu_file_pgd_voi_lich_su(
                        r["ten_pgd"], r["loai"], data, thang
                    )
                    db.ghi_audit(
                        username,
                        "folder_import_file",
                        f"CDTOTKVV — {r['ten_pgd']} "
                        f"tháng={thang} ({r['ten_file']})",
                    )
                else:
                    # Không đọc được tháng → lưu latest, cảnh báo
                    _ghi_file_pgd(r["ten_pgd"], r["loai"], data)
                    db.ghi_audit(
                        username,
                        "folder_import_file",
                        f"CDTOTKVV — {r['ten_pgd']} "
                        f"tháng=unknown ({r['ten_file']})",
                    )
                    # Ghi chú vào row để hiển thị cảnh báo sau
                    r["canh_bao"] = "⚠️ Không đọc được tháng — chỉ lưu latest"
            else:
                _ghi_file_pgd(r["ten_pgd"], r["loai"], data)
                db.ghi_audit(
                    username,
                    "folder_import_file",
                    f"{r['loai'].upper()} — {r['ten_pgd']} ({r['ten_file']})",
                )
            return r, None
        except Exception as e:
            return r, str(e)

    if tat_ca_bytes:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(_ghi, r, data): r for r, data in tat_ca_bytes}
            for i, future in enumerate(as_completed(futures)):
                r, err = future.result()
                if err:
                    that_bai.append(f"{r['ten_file']}: {err}")
                else:
                    thanh_cong.append(r)
                    loai_da_luu.add(r["loai"])
                progress.progress(
                    0.4 + ((i + 1) / len(tat_ca_bytes)) * 0.4,
                    text=f"💾 Lưu file {i + 1}/{len(tat_ca_bytes)}...",
                )

    loai_can_merge = sorted(loai_da_luu & {"hstd", "nq11", "gqvl"})
    ket_qua_merge: list[dict] = []
    for j, loai in enumerate(loai_can_merge):
        progress.progress(
            0.8 + ((j + 1) / max(len(loai_can_merge), 1)) * 0.2,
            text=f"🔄 Tổng hợp {loai.upper()} toàn Chi nhánh...",
        )
        kq_m = merge_du_lieu_toan_cn(loai)
        meta_m = lay_meta_merge(loai) if kq_m.thanh_cong else None
        ket_qua_merge.append(
            {
                "loai": loai,
                "thanh_cong": kq_m.thanh_cong,
                "thong_bao": kq_m.thong_bao,
                "so_pgd": (meta_m or {}).get("so_pgd"),
                "so_dong": (meta_m or {}).get("so_dong"),
            }
        )

    progress.empty()
    st.cache_data.clear()

    # Force refresh bảng trạng thái upload sau khi import
    from data.pgd import lay_trang_thai_upload_pgd as _lay_tt_upload
    from config import DS_PGD as _DS_PGD, DON_VI_CHI_NHANH as _DON_VI_CN

    ds_don_vi = [_DON_VI_CN] + _DS_PGD
    st.session_state["trang_thai_upload_pgd"] = _lay_tt_upload(ds_don_vi)

    db.ghi_audit(
        username,
        "folder_import_batch",
        f"{len(thanh_cong)} file thành công, {len(that_bai)} lỗi",
    )

    st.session_state["folder_import_ket_qua_merge"] = ket_qua_merge

    st.success(f"✅ Import thành công **{len(thanh_cong)}** file")
    st.toast("✅ Import hoàn tất!", icon="✅")
    if that_bai:
        st.warning("⚠️ Lỗi:\n" + "\n".join(that_bai))

    st.session_state.pop("folder_scan_result", None)
    st.session_state.pop("folder_scan_meta", None)
    # Reset file_uploader bằng cách tăng version → widget recreate rỗng
    st.session_state["khnv_bulk_uploader_ver"] = (
        st.session_state.get("khnv_bulk_uploader_ver", 0) + 1
    )
    st.session_state.pop("khnv_bulk_bytes", None)
    st.session_state.pop("khnv_bulk_ids", None)
    st.rerun()


def _render_upload_hang_loat(role: str, username: str) -> None:
    """Upload hàng loạt qua trình duyệt — thay thế quét thư mục server."""
    _ = role

    with st.expander("📦 Import hàng loạt", expanded=True):

        # ── Hướng dẫn ────────────────────────────────────────────────
        st.info(
            "**Cách chọn nhiều file:**  \n"
            "• Windows: giữ **Ctrl** rồi click từng file, hoặc **Ctrl+A** "
            "để chọn tất cả trong thư mục  \n"
            "• Mac: giữ **⌘ Cmd** rồi click từng file  \n"
            "• Hỗ trợ tối đa 66 file (22 PGD × HSTD + NQ11 + GQVL)"
        )

        # ── Multi-file uploader ───────────────────────────────────────
        # Dùng version counter để reset widget sau import thành công.
        # Streamlit không cho xóa session_state key của widget trực tiếp;
        # cách duy nhất reset file_uploader là thay đổi key của nó.
        _ver = st.session_state.setdefault("khnv_bulk_uploader_ver", 0)
        uploaded = st.file_uploader(
            "Chọn file",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key=f"khnv_bulk_upload_{_ver}",
            label_visibility="collapsed",
        )

        if not uploaded:
            st.caption("Chưa có file nào được chọn.")
            return

        # ── Fallback: prefix tên file khi không đọc được loại từ nội dung ──
        PREFIX_MAP = {
            "hstd":     ("HSTD", "CT_CDTO"),
            "nq11":     ("NQ11", "SAO_KE_CT"),
            "cdtotkvv": ("CDTOTKVV", "CT_CDTOTKVV"),
        }

        def _nhan_dien_loai_ten_file(ten_file: str) -> str | None:
            upper = ten_file.upper()
            for loai, prefixes in PREFIX_MAP.items():
                if any(upper.startswith(p.upper()) for p in prefixes):
                    return loai
            return None

        # ── Tùy chọn import ──────────────────────────────────────────
        buoc_import = st.checkbox(
            "🔁 Bắt buộc import lại (kể cả file giống hệt trên đĩa)",
            value=False,
            key="khnv_force_import",
            help="Tích vào khi muốn ghi đè dù nội dung file không thay đổi.",
        )

        # ── Xây dựng danh sách rows để preview ───────────────────────
        # Dùng (tên, kích thước) làm khóa cache — tránh dùng bytes cũ khi upload
        # cùng tên nhưng nội dung mới (cache invalidation by size + name)
        cache_key = "khnv_bulk_bytes"
        file_ids_now = [(f.name, f.size) for f in uploaded]
        if st.session_state.get("khnv_bulk_ids") != file_ids_now:
            st.session_state["khnv_bulk_ids"] = file_ids_now
            st.session_state[cache_key] = {f.name: f.read() for f in uploaded}

        bytes_map: dict[str, bytes] = st.session_state.get(cache_key, {})

        rows: list[dict] = []
        seen: dict[str, int] = {}

        with st.spinner("🔍 Đang nhận diện file..."):
            for ten_file, data in bytes_map.items():
                loai = _nhan_dien_loai_tu_noi_dung(data)
                if loai is None:
                    loai = _nhan_dien_loai_ten_file(ten_file)
                if loai is None:
                    rows.append({
                        "ten_file": ten_file, "loai": "❓",
                        "ten_pgd": "—", "nhan_dien": False,
                        "trang_thai": "❓ Không rõ loại",
                        "co_the_import": False, "data": data,
                    })
                    continue

                ten_pgd = _tim_ten_pgd_tu_noi_dung(data, loai)
                if ten_pgd:
                    ten_pgd = _chuan_hoa_ten(ten_pgd)
                if ten_pgd is None or ten_pgd not in DS_DON_VI:
                    rows.append({
                        "ten_file": ten_file, "loai": loai.upper(),
                        "ten_pgd": "❓ Không nhận diện được",
                        "nhan_dien": False,
                        "trang_thai": "❓ Không rõ PGD",
                        "co_the_import": False, "data": data,
                    })
                    continue

                dk = f"{ten_pgd}|{loai}"
                if dk in seen:
                    rows[seen[dk]]["trang_thai"] = "⚠️ Trùng — bỏ qua (giữ file sau)"
                    rows[seen[dk]]["co_the_import"] = False
                    trang_thai = "⚠️ Trùng — sẽ import (file này)"
                else:
                    trang_thai = "✅ Sẵn sàng"

                co_the_import = trang_thai in (
                    "✅ Sẵn sàng",
                    "⚠️ Trùng — sẽ import (file này)",
                )

                path_ht = duong_dan_pgd(ten_pgd, loai.lower())
                if not os.path.exists(path_ht):
                    so_sanh = "🆕 Chưa có"
                    md5_co_the_import = True
                else:
                    da_giong = _md5_bytes(data) == _md5_file(path_ht)
                    if da_giong:
                        if buoc_import:
                            so_sanh = "🔁 Ghi đè"
                            md5_co_the_import = True
                        else:
                            so_sanh = "✅ Giống hệt"
                            md5_co_the_import = False
                    else:
                        so_sanh = "🔄 Có thay đổi"
                        md5_co_the_import = True

                co_the_import = co_the_import and md5_co_the_import

                idx = len(rows)
                seen[dk] = idx
                rows.append({
                    "ten_file": ten_file, "loai": loai.upper(),
                    "ten_pgd": ten_pgd, "nhan_dien": True,
                    "trang_thai": trang_thai,
                    "co_the_import": co_the_import,
                    "so_sanh": so_sanh,
                    "data": data,
                })

        so_trung = sum(1 for r in rows if "Trùng" in r.get("trang_thai", ""))
        if so_trung > 0:
            st.warning(
                f"⚠️ Có **{so_trung}** file trùng (cùng đơn vị + cùng loại). "
                f"Hệ thống sẽ giữ file xuất hiện sau cùng. Kiểm tra cột **Trạng thái** trước khi Import."
            )

        def _style_preview(val: str) -> str:
            if val.startswith("✅"):
                return "background-color:#d4edda;color:#155724;font-weight:bold"
            if val.startswith("⚠️"):
                return "background-color:#fff3cd;color:#856404"
            if val.startswith("❓"):
                return "background-color:#f8d7da;color:#721c24"
            return ""

        def _style_so_sanh(val: str) -> str:
            if val.startswith("🆕"):
                return "background-color:#d4edda;color:#155724;font-weight:bold"
            if val.startswith("🔄"):
                return "background-color:#fff3cd;color:#856404;font-weight:bold"
            if val.startswith("🔁"):
                return "background-color:#cce5ff;color:#004085;font-weight:bold"
            if val.startswith("✅"):
                return "background-color:#e9ecef;color:#495057"
            return ""

        df_preview = pd.DataFrame([
            {
                "Loại": r["loai"],
                "Tên file": r["ten_file"],
                "PGD": r["ten_pgd"],
                "So sánh": r.get("so_sanh", "—"),
                "Trạng thái": r["trang_thai"],
            }
            for r in rows
        ])
        styled = df_preview.style.map(_style_preview, subset=["Trạng thái"]).map(
            _style_so_sanh, subset=["So sánh"]
        )
        st.dataframe(
            styled,
            use_container_width=True, hide_index=True,
        )

        co_the_import = [r for r in rows if r["co_the_import"]]
        khong_nhan_dien = [r for r in rows if not r["nhan_dien"]]
        trung = [r for r in rows
                 if "Trùng" in r.get("trang_thai", "") and not r["co_the_import"]]
        giong_het = [r for r in rows
                     if r.get("nhan_dien") and not r["co_the_import"]
                     and r.get("so_sanh", "").startswith("✅")]
        st.caption(
            f"📊 Tổng **{len(rows)}** file · "
            f"✅ Sẵn sàng **{len(co_the_import)}** · "
            f"⏩ Giống hệt **{len(giong_het)}** · "
            f"❓ Không nhận diện **{len(khong_nhan_dien)}** · "
            f"⚠️ Trùng bỏ qua **{len(trung)}**"
        )

        if not co_the_import:
            st.warning("⚠️ Không có file nào hợp lệ để import.")
            return

        if st.button(
            f"📥 Import {len(co_the_import)} file",
            type="primary",
            key="btn_bulk_import",
        ):
            import tempfile

            danh_sach_for_import: list[dict] = []
            tmp_files: list[str] = []
            try:
                for r in co_the_import:
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False, suffix=".xlsx"
                    )
                    tmp.write(r["data"])
                    tmp.close()
                    tmp_files.append(tmp.name)
                    danh_sach_for_import.append({
                        "path": tmp.name,
                        "ten_file": r["ten_file"],
                        "ten_pgd": r["ten_pgd"],
                        "loai": r["loai"].lower(),
                        "phuong_phap": "nội dung",
                        "nhan_dien": True,
                        "co_the_import": True,
                    })
                _xu_ly_import_folder(danh_sach_for_import, username)
            finally:
                for p in tmp_files:
                    try:
                        os.unlink(p)
                    except Exception:
                        pass


# ── Xóa dữ liệu PGD ──────────────────────────────────────────────────────────

def _xoa_du_lieu_pgd(ten_pgd: str, loai: str, username: str) -> tuple[bool, str]:
    """
    Xóa file gốc + cache parquet của 1 PGD cho 1 loại dữ liệu.
    Trả về (thanh_cong: bool, thong_bao: str).
    """
    import socket
    hostname = socket.gethostname()
    path_excel   = Path(duong_dan_pgd(ten_pgd, loai))
    path_parquet = path_excel.with_suffix(".parquet")

    if not path_excel.exists():
        return False, f"Không tìm thấy file {loai.upper()} của {ten_pgd}"

    try:
        path_excel.unlink()
        if path_parquet.exists():
            path_parquet.unlink()
        db.ghi_audit(username, "xoa_du_lieu_pgd",
                     f"[{hostname}] {loai.upper()} — {ten_pgd}")
        return True, f"✅ Đã xóa {loai.upper()} — {ten_pgd}"
    except Exception as e:
        db.ghi_audit(username, "loi_xoa_du_lieu_pgd",
                     f"[{hostname}] {loai.upper()} — {ten_pgd}: {e}")
        return False, f"❌ Lỗi xóa: {e}"


def _thuc_hien_xoa(
    ds_don_vi: list[str],
    loai_xoa: list[str],
    username: str,
) -> None:
    """Thực hiện xóa, hiển thị kết quả, rebuild CACHE, clear cache."""
    ket_qua = []
    can_merge_loai: set[str] = set()

    with st.spinner("🗑️ Đang xóa dữ liệu..."):
        for ten_pgd in ds_don_vi:
            for loai in loai_xoa:
                ok, msg = _xoa_du_lieu_pgd(ten_pgd, loai, username)
                ket_qua.append((ten_pgd, loai, ok, msg))
                if ok and loai in ("hstd", "nq11", "gqvl"):
                    can_merge_loai.add(loai)

    so_thanh_cong = sum(1 for _, _, ok, _ in ket_qua if ok)
    so_loi = len(ket_qua) - so_thanh_cong

    if so_thanh_cong:
        st.success(
            f"✅ Đã xóa **{so_thanh_cong}** file thành công"
            + (f" · ⚠️ {so_loi} lỗi" if so_loi else "")
        )
    for _, _, ok, msg in ket_qua:
        if not ok:
            st.warning(msg)

    # Rebuild CACHE cho các loại đã xóa
    if can_merge_loai:
        st.divider()
        for loai in sorted(can_merge_loai):
            with st.spinner(f"🔄 Đang rebuild CACHE {loai.upper()}..."):
                try:
                    kq_merge = merge_du_lieu_toan_cn(loai)
                    if kq_merge.thanh_cong:
                        meta = lay_meta_merge(loai)
                        so_pgd  = (meta or {}).get("so_pgd", "?")
                        so_dong = (meta or {}).get("so_dong", 0)
                        st.success(
                            f"✅ Rebuild **{loai.upper()}** — "
                            f"**{so_pgd}** đơn vị · **{fmt_so(so_dong)}** dòng"
                        )
                    else:
                        st.warning(f"⚠️ Rebuild {loai.upper()}: {kq_merge.thong_bao}")
                except Exception as e:
                    st.error(f"❌ Lỗi rebuild {loai.upper()}: {e}")

    st.cache_data.clear()
    # Làm mới bảng trạng thái
    st.session_state.pop("trang_thai_upload_pgd", None)
    st.rerun()


def _render_xoa_du_lieu(role: str, username: str) -> None:
    """Expander xóa dữ liệu PGD — chỉ admin/manager."""
    if not la_phan_he_cn(role) or normalize_role(role) == "executive":
        return

    with st.expander("🗑️ Xóa dữ liệu PGD", expanded=False):
        st.caption(
            "Xóa file pgd_data/ của PGD — hệ thống tự động rebuild CACHE sau khi xóa."
        )

        che_do = st.radio(
            "Chế độ xóa",
            ["Xóa từng PGD", "Xóa tất cả 22 đơn vị"],
            horizontal=True,
            key="xoa_pgd_che_do",
        )

        loai_xoa = st.multiselect(
            "Loại dữ liệu cần xóa",
            options=["hstd", "nq11", "gqvl", "cdtotkvv"],
            default=["hstd", "nq11", "gqvl"],
            format_func=lambda x: x.upper(),
            key="xoa_pgd_loai",
        )

        if not loai_xoa:
            st.info("Chọn ít nhất 1 loại dữ liệu cần xóa.")
            return

        if che_do == "Xóa từng PGD":
            # Chỉ hiện PGD đã có file
            pgd_co_file = [
                dv for dv in DS_DON_VI
                if any(kiem_tra_file_ton_tai_pgd(dv, l) for l in loai_xoa)
            ]
            if not pgd_co_file:
                st.info("ℹ️ Không có đơn vị nào có dữ liệu để xóa.")
                return

            ten_pgd_chon = st.selectbox(
                "Chọn đơn vị cần xóa",
                pgd_co_file,
                key="xoa_pgd_chon_dv",
            )

            # Preview file sẽ bị xóa
            st.markdown("**File sẽ bị xóa:**")
            cols_prev = st.columns(4)
            for col, loai in zip(cols_prev, ["hstd", "nq11", "gqvl", "cdtotkvv"]):
                co = kiem_tra_file_ton_tai_pgd(ten_pgd_chon, loai)
                se_xoa = loai in loai_xoa and co
                col.markdown(
                    f"**{loai.upper()}**  \n"
                    f"{'🗑️ Sẽ xóa' if se_xoa else ('⬜ Không có' if not co else '⏩ Bỏ qua')}"
                )

            st.warning(
                f"⚠️ Sẽ xóa **{', '.join(l.upper() for l in loai_xoa)}** "
                f"của **{ten_pgd_chon}** và rebuild CACHE."
            )
            if st.button(
                f"🗑️ Xác nhận xóa — {ten_pgd_chon}",
                type="primary",
                key="btn_xoa_1dv",
            ):
                _thuc_hien_xoa([ten_pgd_chon], loai_xoa, username)

        else:  # Xóa tất cả
            st.error(
                f"⚠️ **CẢNH BÁO:** Sẽ xóa **{', '.join(l.upper() for l in loai_xoa)}** "
                f"của **TẤT CẢ {len(DS_DON_VI)} đơn vị** và rebuild CACHE từ đầu."
            )
            xac_nhan = st.checkbox(
                "Tôi hiểu hành động này không thể hoàn tác",
                key="xoa_all_xac_nhan",
            )
            if xac_nhan:
                if st.button(
                    "🗑️ Xóa tất cả và rebuild CACHE",
                    type="primary",
                    key="btn_xoa_all",
                ):
                    _thuc_hien_xoa(DS_DON_VI, loai_xoa, username)


# ── Upload Baseline 31/12 ─────────────────────────────────────────────────────

_NHAN_BASELINE = {
    "hstd":     "📊 HSTD",
    "nq11":     "📑 NQ11",
    "gqvl":     "📋 GQVL",
    "cdtotkvv": "🏆 CDTOTKVV",
}


def _render_upload_baseline(username: str) -> None:
    """Expander upload file mốc 31/12 (4 loại) per-PGD — bulk upload + tổng hợp thủ công."""
    with st.expander("📅 Upload mốc số liệu 31/12 (Baseline)", expanded=False):
        st.caption(
            "Upload 4 loại file (HSTD, NQ11, GQVL, CDTOTKVV) cho ngày 31/12 — "
            "định dạng y hệt file hàng ngày, nhưng ngày số liệu là 31/12."
        )

        from datetime import date as _date
        nam_mac_dinh = _date.today().year - 1

        chon_nam = st.number_input(
            "Năm cần upload (31/12/năm)",
            min_value=2020,
            max_value=_date.today().year,
            value=nam_mac_dinh,
            step=1,
            key="upload_baseline_nam",
        )
        nam = int(chon_nam)

        # ── Trạng thái 22 đơn vị × 4 loại ───────────────────────────
        tt_loai = {loai: trang_thai_baseline_pgd_loai(nam, loai) for loai in LOAI_BASELINE}
        da_co_hstd = sum(1 for v in tt_loai["hstd"].values() if v)
        tong = len([DON_VI_CHI_NHANH] + DS_PGD)

        cols_tt = st.columns(4)
        for col, loai in zip(cols_tt, LOAI_BASELINE):
            da_co = sum(1 for v in tt_loai[loai].values() if v)
            nhan = _NHAN_BASELINE[loai]
            if da_co == tong:
                col.success(f"{nhan}\n\n✅ {da_co}/{tong}")
            elif da_co > 0:
                col.warning(f"{nhan}\n\n⏳ {da_co}/{tong}")
            else:
                col.info(f"{nhan}\n\n❌ 0/{tong}")

        st.divider()

        # ── Import hàng loạt: chọn file hoặc quét thư mục ──────────────
        st.markdown("**📦 Import hàng loạt** — hệ thống tự nhận diện loại và PGD từ nội dung file")

        tab_file, tab_folder = st.tabs(["📂 Chọn file", "📁 Quét thư mục"])

        with tab_file:
            st.info(
                "**Cách chọn nhiều file:**  \n"
                "• Windows: giữ **Ctrl** rồi click từng file, hoặc **Ctrl+A** "
                "để chọn tất cả trong thư mục  \n"
                "• Mac: giữ **⌘ Cmd** rồi click từng file  \n"
                "• Hỗ trợ tối đa 88 file (22 PGD × 4 loại)"
            )
            _bl_ver = st.session_state.setdefault("bl_bulk_ver", 0)
            uploaded = st.file_uploader(
                "Chọn file baseline",
                type=["xlsx", "xls"],
                accept_multiple_files=True,
                key=f"bl_bulk_{nam}_{_bl_ver}",
                label_visibility="collapsed",
            )
            if uploaded:
                _bl_ids_now = [(f.name, f.size) for f in uploaded]
                if st.session_state.get("_bl_ids") != _bl_ids_now:
                    st.session_state["_bl_ids"] = _bl_ids_now
                    st.session_state["_bl_bytes"] = {f.name: f.read() for f in uploaded}

        with tab_folder:
            st.caption("Nhập đường dẫn thư mục chứa 4 loại file baseline 31/12 trên máy tính.")
            thu_muc = st.text_input(
                "Đường dẫn thư mục",
                placeholder=r"Ví dụ: D:\Data\Baseline_3112_2025",
                key="bl_folder_path",
                label_visibility="collapsed",
            )
            if st.button("🔍 Quét thư mục", key="btn_bl_scan_folder"):
                if not thu_muc or not os.path.isdir(thu_muc):
                    st.error("❌ Thư mục không tồn tại.")
                else:
                    files = [f for f in Path(thu_muc).iterdir()
                             if f.suffix.lower() in (".xlsx", ".xls")]
                    if not files:
                        st.warning("⚠️ Không có file Excel nào trong thư mục.")
                    else:
                        _bm: dict[str, bytes] = {}
                        for f in files:
                            try:
                                _bm[f.name] = f.read_bytes()
                            except Exception:
                                pass
                        st.session_state["_bl_bytes"] = _bm
                        st.session_state["_bl_ids"] = [(k, len(v)) for k, v in _bm.items()]
                        st.success(f"✅ Tìm thấy {len(_bm)} file.")
                        st.rerun()

        bytes_map: dict[str, bytes] = st.session_state.get("_bl_bytes", {})
        if not bytes_map:
            st.caption("Chưa có file nào.")
        else:
            # ── Tùy chọn ─────────────────────────────────────────────────
            buoc_import = st.checkbox(
                "🔁 Bắt buộc import lại (kể cả file giống hệt trên đĩa)",
                value=False,
                key="bl_force_import",
            )

            # ── Nhận diện loại + PGD + so sánh MD5 ───────────────────────
            rows: list[dict] = []
            ds_don_vi_chuan = set([DON_VI_CHI_NHANH] + DS_PGD)
            seen: dict[str, int] = {}  # key = "ten_pgd|loai"

            with st.spinner("🔍 Đang nhận diện file..."):
                for ten_file, data in bytes_map.items():
                    loai = _nhan_dien_loai_tu_noi_dung(data)
                    if loai is None:
                        rows.append({
                            "ten_file": ten_file, "loai": "❓",
                            "ten_pgd": "—", "nhan_dien": False,
                            "trang_thai": "❓ Không rõ loại",
                            "so_sanh": "—", "co_the_import": False, "data": data,
                        })
                        continue

                    ten_pgd = _tim_ten_pgd_tu_noi_dung(data, loai)
                    if ten_pgd:
                        ten_pgd = _chuan_hoa_ten(ten_pgd)

                    if not ten_pgd or ten_pgd not in ds_don_vi_chuan:
                        rows.append({
                            "ten_file": ten_file, "loai": loai.upper(),
                            "ten_pgd": ten_pgd or "❓", "nhan_dien": False,
                            "trang_thai": "❓ Không rõ PGD",
                            "so_sanh": "—", "co_the_import": False, "data": data,
                        })
                        continue

                    dk = f"{ten_pgd}|{loai}"
                    if dk in seen:
                        rows[seen[dk]]["trang_thai"] = "⚠️ Trùng — bỏ qua (giữ file sau)"
                        rows[seen[dk]]["co_the_import"] = False
                        tt = "⚠️ Trùng — sẽ import (file này)"
                    else:
                        tt = "✅ Sẵn sàng"

                    dest = baseline_pgd_path_loai(ten_pgd, nam, loai)
                    if not os.path.exists(dest):
                        so_sanh = "🆕 Chưa có"
                        md5_ok = True
                    else:
                        giong = _md5_bytes(data) == _md5_file(dest)
                        if giong:
                            so_sanh = "🔁 Ghi đè" if buoc_import else "✅ Giống hệt"
                            md5_ok = buoc_import
                        else:
                            so_sanh = "🔄 Có thay đổi"
                            md5_ok = True

                    co_the_import = tt in ("✅ Sẵn sàng", "⚠️ Trùng — sẽ import (file này)") and md5_ok
                    seen[dk] = len(rows)
                    rows.append({
                        "ten_file": ten_file, "loai": loai.upper(),
                        "ten_pgd": ten_pgd, "nhan_dien": True,
                        "trang_thai": tt, "so_sanh": so_sanh,
                        "co_the_import": co_the_import, "data": data,
                    })

            # ── Preview table ─────────────────────────────────────────
            so_trung = sum(1 for r in rows if "Trùng" in r.get("trang_thai", ""))
            if so_trung:
                st.warning(f"⚠️ Có **{so_trung}** file trùng — hệ thống giữ file cuối.")

            def _style_tt(v: str) -> str:
                if v.startswith("✅"): return "background-color:#d4edda;color:#155724;font-weight:bold"
                if v.startswith("⚠️"): return "background-color:#fff3cd;color:#856404"
                if v.startswith("❓"): return "background-color:#f8d7da;color:#721c24"
                return ""

            def _style_ss(v: str) -> str:
                if v.startswith("🆕"): return "background-color:#d4edda;color:#155724;font-weight:bold"
                if v.startswith("🔄"): return "background-color:#fff3cd;color:#856404;font-weight:bold"
                if v.startswith("🔁"): return "background-color:#cce5ff;color:#004085;font-weight:bold"
                if v.startswith("✅"): return "background-color:#e9ecef;color:#495057"
                return ""

            df_preview = pd.DataFrame([
                {
                    "Loại": r["loai"], "Tên file": r["ten_file"],
                    "Đơn vị": r["ten_pgd"], "So sánh": r["so_sanh"],
                    "Trạng thái": r["trang_thai"],
                }
                for r in rows
            ])
            st.dataframe(
                df_preview.style
                    .map(_style_tt, subset=["Trạng thái"])
                    .map(_style_ss, subset=["So sánh"]),
                use_container_width=True, hide_index=True,
            )

            co_the_import_list = [r for r in rows if r["co_the_import"]]
            khong_nd  = [r for r in rows if not r["nhan_dien"]]
            giong_het = [r for r in rows if r["nhan_dien"] and not r["co_the_import"]
                         and r.get("so_sanh", "").startswith("✅")]
            st.caption(
                f"📊 Tổng **{len(rows)}** file · "
                f"✅ Sẵn sàng **{len(co_the_import_list)}** · "
                f"⏩ Giống hệt **{len(giong_het)}** · "
                f"❓ Không nhận diện **{len(khong_nd)}**"
            )

            if not co_the_import_list:
                st.warning("⚠️ Không có file nào hợp lệ để import.")
            elif st.button(
                f"📥 Import {len(co_the_import_list)} file baseline {nam}",
                type="primary",
                key="btn_luu_bulk_baseline",
            ):
                thanh_cong, that_bai = 0, []
                for r in co_the_import_list:
                    dest = baseline_pgd_path_loai(r["ten_pgd"], nam, r["loai"].lower())
                    try:
                        Path(dest).parent.mkdir(parents=True, exist_ok=True)
                        with open(dest, "wb") as fh:
                            fh.write(r["data"])
                        mb = len(r["data"]) / 1024 / 1024
                        db.ghi_audit(
                            username, "upload_baseline",
                            f"{r['loai']} 31/12/{nam} — {r['ten_pgd']} ({mb:.1f} MB)",
                        )
                        thanh_cong += 1
                    except Exception as e:
                        that_bai.append(f"{r['ten_pgd']} {r['loai']}: {e}")

                st.cache_data.clear()
                if thanh_cong:
                    st.success(f"✅ Đã lưu **{thanh_cong}/{len(co_the_import_list)}** file baseline {nam}.")
                if that_bai:
                    st.error("❌ Lỗi:\n" + "\n".join(that_bai))

                _bl_ver_new = st.session_state.get("bl_bulk_ver", 0) + 1
                st.session_state["bl_bulk_ver"] = _bl_ver_new
                st.session_state.pop("_bl_ids", None)
                st.session_state.pop("_bl_bytes", None)
                st.rerun()

        # ── Tổng hợp thủ công Baseline ────────────────────────────────
        st.divider()
        st.markdown("**🔄 Tổng hợp thủ công** — gộp file baseline 22 đơn vị thành dữ liệu chung")
        st.caption(
            "Dùng sau khi upload đủ file baseline cho các đơn vị, hoặc khi cần rebuild cache 31/12."
        )

        loai_bl_chon = st.multiselect(
            "Chọn loại cần tổng hợp",
            options=list(LOAI_BASELINE),
            default=["hstd", "nq11", "gqvl"],
            format_func=lambda x: _NHAN_BASELINE.get(x, x.upper()),
            key="bl_manual_merge_loai",
        )
        if st.button(
            "🔄 Tổng hợp baseline ngay",
            type="primary",
            key="btn_bl_manual_merge",
            disabled=not loai_bl_chon,
        ):
            if not loai_bl_chon:
                st.warning("⚠️ Chọn ít nhất 1 loại.")
            else:
                tong_buoc = len(loai_bl_chon)
                progress_bar = st.progress(0, text="⏳ Chuẩn bị tổng hợp baseline...")
                for idx, loai in enumerate(loai_bl_chon):
                    progress_bar.progress(
                        idx / tong_buoc,
                        text=f"🔄 Tổng hợp **{_NHAN_BASELINE.get(loai, loai.upper())}** "
                             f"31/12/{nam} ({idx + 1}/{tong_buoc})...",
                    )
                    kq = merge_baseline_toan_cn(loai, nam)
                    progress_bar.progress((idx + 1) / tong_buoc)
                    if kq.thanh_cong:
                        st.success(kq.thong_bao)
                    else:
                        st.error(f"❌ {_NHAN_BASELINE.get(loai, loai.upper())}: {kq.thong_bao}")

                progress_bar.progress(1.0, text="✅ Hoàn tất!")
                st.cache_data.clear()
                db.ghi_audit(
                    username, "manual_merge_baseline",
                    f"loai={loai_bl_chon} nam={nam}",
                )
                st.toast("✅ Tổng hợp baseline hoàn tất!", icon="✅")
                st.rerun()


# ── Entry point ───────────────────────────────────────────────────────────────

@st.fragment
def _fragment_merge_toan_cn():
    co_cho_merge = any(
        st.session_state.get(f"can_merge_{loai}", False)
        for loai in ["hstd", "nq11", "gqvl"]
    )
    if not co_cho_merge:
        return

    st.divider()
    st.subheader("🔄 Cập nhật dữ liệu toàn Chi nhánh")
    st.caption("Tổng hợp file vừa upload vào hệ thống dữ liệu chung (22 đơn vị).")

    if st.button("▶️ Bắt đầu cập nhật", type="primary",
                 key="btn_merge_toan_cn"):
        with st.spinner("⏳ Đang merge 22 đơn vị... Vui lòng chờ."):
            try:
                from services.upload_service import merge_du_lieu_toan_cn

                for loai in ("hstd", "nq11", "gqvl"):
                    if st.session_state.get(f"can_merge_{loai}", False):
                        merge_du_lieu_toan_cn(loai)

                for loai in ("hstd", "nq11", "gqvl"):
                    st.session_state.pop(f"can_merge_{loai}", None)

                st.cache_data.clear()
                for _k in ["_ctx", "_ctx_cache_key", "_pgd_map_cache_ts", "_pgd_xa_map_cached", "_ds_pgd_all_cached", "df_full"]:
                    st.session_state.pop(_k, None)

                username = st.session_state.get("username", "unknown")
                db.ghi_audit(username, "merge_toan_cn",
                             "Merge thành công (non-blocking fragment)")

                st.success("✅ Cập nhật hoàn tất! Dữ liệu mới sẵn sàng.")
                st.balloons()
                st.rerun()

            except Exception as e:
                st.error(f"❌ Lỗi khi merge: {e}")


def render(tab=None, **kwargs) -> None:
    """
    Render tab Upload KH-NV.
    Nhận tab (st.tab object) hoặc render trực tiếp trong context hiện tại.
    """
    role     = kwargs.get("role", "")
    username = kwargs.get("username", "unknown")

    _ctx = tab if tab is not None else st.container()
    with _ctx:
        if not la_phan_he_cn(role) or normalize_role(role) == "executive":
            st.error("🔒 Chức năng này chỉ dành cho Phòng KH-NV (admin/manager).")
            return

        col_title, col_badge = st.columns([6, 1])
        with col_title:
            st.markdown("## 📤 Upload Dữ liệu — Phòng KH-NV")
        with col_badge:
            st.markdown(
                "<div style='text-align:right;padding-top:14px'>"
                "<span style='background:#0d6efd;color:white;padding:4px 12px;"
                "border-radius:12px;font-size:12px;font-weight:600'>KH-NV</span>"
                "</div>",
                unsafe_allow_html=True,
            )
        st.divider()

        st.info(
            "💡 Xem hướng dẫn chi tiết tại đầu workspace **Phòng KH-NV** → "
            "**📖 Hướng dẫn Điện báo**. "
            "Upload file Điện báo thực hiện tại tab **📡 Điện Báo** (mục *Upload file Điện báo*), "
            "không phải tab Upload này."
        )

        _render_upload_hang_loat(role, username)

        _render_xoa_du_lieu(role, username)

        _render_upload_baseline(username)

        with st.expander("🔄 Tổng hợp toàn Chi nhánh thủ công",
                         expanded=False):
            st.caption(
                "Dùng khi merge bị lỗi giữa chừng, hoặc sau khi "
                "upload nhiều đơn vị liên tiếp cần gộp lại."
            )
            loai_chon = st.multiselect(
                "Chọn loại cần tổng hợp",
                options=["hstd", "nq11", "gqvl"],
                default=["hstd", "nq11", "gqvl"],
                format_func=lambda x: x.upper(),
                key="khnv_manual_merge_loai",
            )
            if st.button("🔄 Tổng hợp ngay", type="primary",
                         key="btn_manual_merge"):
                if not loai_chon:
                    st.warning("⚠️ Chọn ít nhất 1 loại.")
                else:
                    tong_buoc = len(loai_chon)
                    progress_bar = st.progress(0, text="⏳ Chuẩn bị tổng hợp...")
                    status_text = st.empty()

                    for idx, loai in enumerate(loai_chon):
                        pct_bat_dau = idx / tong_buoc
                        pct_ket_thuc = (idx + 1) / tong_buoc

                        progress_bar.progress(
                            pct_bat_dau,
                            text=f"🔄 Đang đọc và gộp **{loai.upper()}** "
                                 f"({idx + 1}/{tong_buoc}) — "
                                 f"đọc 22 đơn vị song song, vui lòng chờ..."
                        )
                        status_text.caption(
                            f"⏳ {loai.upper()}: Đọc file từng PGD → gộp → ghi cache. "
                            f"File lớn (~14MB) mất 10–30 giây lần đầu, "
                            f"lần sau nhanh hơn nhờ cache."
                        )

                        kq = merge_du_lieu_toan_cn(loai)
                        progress_bar.progress(pct_ket_thuc)

                        if kq.thanh_cong:
                            meta = lay_meta_merge(loai)
                            so_pgd  = (meta or {}).get("so_pgd", "?")
                            so_dong = (meta or {}).get("so_dong", 0)
                            st.success(
                                f"✅ **{loai.upper()}** — "
                                f"**{so_pgd}** đơn vị · "
                                f"**{fmt_so(so_dong)}** dòng"
                            )
                        else:
                            st.error(f"❌ {loai.upper()}: {kq.thong_bao}")

                    progress_bar.progress(1.0, text="✅ Hoàn tất!")
                    status_text.empty()
                    st.cache_data.clear()
                    for _k in ["_ctx", "_ctx_cache_key", "_pgd_map_cache_ts", "_pgd_xa_map_cached", "_ds_pgd_all_cached", "df_full"]:
                        st.session_state.pop(_k, None)

                    db.ghi_audit(
                        username,
                        "manual_merge_toan_cn",
                        f"loai={loai_chon}",
                    )
                    st.toast("✅ Tổng hợp hoàn tất!", icon="✅")
                    st.rerun()

        if "folder_import_ket_qua_merge" in st.session_state:
            merge_rows = st.session_state.pop("folder_import_ket_qua_merge")
            if merge_rows:
                st.markdown("##### 🔄 Tổng hợp toàn Chi nhánh")
                cols_merge = st.columns(len(merge_rows)) if merge_rows else []
                for col_m, row in zip(cols_merge, merge_rows):
                    loai_m = str(row.get("loai", "")).upper()
                    sp = row.get("so_pgd")
                    sd = row.get("so_dong")
                    if row.get("thanh_cong"):
                        col_m.success(
                            f"**{loai_m}**\n\n"
                            f"{'**' + str(sp) + '** đơn vị' if sp else ''}"
                            f"{' · **' + fmt_so(sd) + '** dòng' if sd else ''}"
                        )
                    else:
                        col_m.warning(f"**{loai_m}**\n\n{row.get('thong_bao', '')}")

        # ── Hiển thị kết quả upload từ session_state ──────────────────────
        if "khnv_ket_qua_upload" in st.session_state:
            kq_map = st.session_state.pop("khnv_ket_qua_upload")
            cols = st.columns(4)
            for col, loai, nhan in zip(cols, ["hstd","nq11","gqvl","cdtotkvv"],
                                       ["📊 HSTD","📑 NQ11","📋 GQVL","🏆 CDTOTKVV"]):
                kq = kq_map.get(loai)
                if kq is None: 
                    col.info(f"**{nhan}**\n\nKhông có file")
                elif kq["thanh_cong"]: 
                    col.success(f"**{nhan}**\n\n{kq['thong_bao']}")
                else: 
                    col.warning(f"**{nhan}**\n\n{kq['thong_bao']}")

        _fragment_merge_toan_cn()

        st.markdown("---")
        col_tt, col_rf = st.columns([5, 1])
        with col_tt:
            st.markdown("#### 📋 Trạng thái Upload — 22 Đơn vị")
        with col_rf:
            if st.button(
                "🔄 Làm mới",
                key="btn_refresh_trang_thai",
                use_container_width=True,
            ):
                st.session_state.pop("trang_thai_upload_pgd", None)
                st.rerun()
        with st.container(key="khnv_bang_trang_thai_upload"):
            _hien_thi_bang_trang_thai()
