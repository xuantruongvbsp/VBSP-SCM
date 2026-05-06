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
from io import BytesIO
import hashlib
import os
from pathlib import Path
import re
from datetime import datetime

import pandas as pd
import streamlit as st

import db
from config import DS_PGD, DON_VI_CHI_NHANH, MA_PGD_MAP
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
            ma_pgd = str(df[cot].dropna().iloc[0]).strip().zfill(6) if not df[cot].dropna().empty else None
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
            # Layout thực tế: row 11+ là data, cột C chứa "Tên đơn vị".
            df = pd.read_excel(buf, header=None, skiprows=10, nrows=5)
            if df.empty or df.shape[1] <= 2:
                return None
            ten_don_vi = str(df.iloc[0, 2]).strip()
            if not ten_don_vi or ten_don_vi.lower() in ("nan", "none"):
                return None
            return ten_don_vi

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
    """Bảng trạng thái 22 hàng × 5 cột: Đơn vị | HSTD | NQ11 | GQVL | CDTOTKVV."""
    df_tt = st.session_state.get(
        "trang_thai_upload_pgd",
        lay_trang_thai_upload_pgd(DS_DON_VI),
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

    cols_loai = ["HSTD", "NQ11", "GQVL", "CDTOTKVV"]
    styled = df_tt.style.map(style_trang_thai, subset=cols_loai)
    hien_thi_dataframe_phan_trang(styled, key="upload_khnv_trang_thai", height=800)


# ── Giao diện upload chính ────────────────────────────────────────────────────

def _render_upload_form(ten_dv: str, prefix: str, username: str) -> None:
    """Form upload 4 file theo đơn vị đã chọn."""
    st.markdown(f"##### 📤 Upload file cho: **{ten_dv}**")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.caption("📊 HSTD Chi tiết")
        f_hstd = st.file_uploader("HSTD", type=["xlsx", "xls"],
                                   key=f"{prefix}_hstd", label_visibility="collapsed")
    with c2:
        st.caption("📑 Sao kê NQ11")
        f_nq11 = st.file_uploader("NQ11", type=["xlsx", "xls"],
                                   key=f"{prefix}_nq11", label_visibility="collapsed")
    with c3:
        st.caption("📋 Sao kê GQVL")
        f_gqvl = st.file_uploader("GQVL", type=["xlsx", "xls"],
                                   key=f"{prefix}_gqvl", label_visibility="collapsed")
    with c4:
        st.caption("🏆 Chấm điểm Tổ TK&VV")
        f_cdtotkvv = st.file_uploader("CDTOTKVV", type=["xlsx", "xls"],
                                       key=f"{prefix}_cdtotkvv", label_visibility="collapsed")

    def _goi_y_6_thang() -> list[str]:
        now = datetime.now()
        ds: list[str] = []
        year = now.year
        month = now.month
        for i in range(6):
            m = month - i
            y = year
            while m <= 0:
                m += 12
                y -= 1
            ds.append(f"{m:02d}/{y}")
        return ds

    thang_cdtotkvv_chon: str | None = None
    if f_cdtotkvv is not None:
        from data.cdtotkvv import doc_thang_nam_tu_file

        file_bytes_preview = f_cdtotkvv.read()
        try:
            f_cdtotkvv.seek(0)
        except Exception:
            pass

        thang_tu_file = doc_thang_nam_tu_file(file_bytes_preview)
        ds_thang = _goi_y_6_thang()
        if thang_tu_file and thang_tu_file not in ds_thang:
            ds_thang = [thang_tu_file] + ds_thang
        idx_mac_dinh = ds_thang.index(thang_tu_file) if thang_tu_file in ds_thang else 0

        if thang_tu_file:
            st.info(f"✅ CDTOTKVV nhận diện tháng: **{thang_tu_file}**")
        else:
            st.warning("⚠️ CDTOTKVV không nhận diện được tháng từ file. Vui lòng chọn tháng dữ liệu.")

        thang_cdtotkvv_chon = st.selectbox(
            "Tháng dữ liệu CDTOTKVV",
            options=ds_thang,
            index=idx_mac_dinh,
            key=f"{prefix}_thang_cdtotkvv",
        )

    co_file = any(f is not None for f in [f_hstd, f_nq11, f_gqvl, f_cdtotkvv])
    if not co_file:
        st.info("Chọn ít nhất 1 file để bắt đầu upload.")
        return

    if st.button("📤 Upload", type="primary", key=f"{prefix}_btn_upload"):
        _xu_ly_upload(ten_dv, username,
                      f_hstd, f_nq11, f_gqvl, f_cdtotkvv, prefix,
                      thang_cdtotkvv_override=thang_cdtotkvv_chon)


def _xu_ly_upload(
    ten_dv: str,
    username: str,
    f_hstd, f_nq11, f_gqvl, f_cdtotkvv,
    prefix: str,
    thang_cdtotkvv_override: str | None = None,
) -> None:
    """Xử lý upload, kiểm tra đơn vị, lưu file và merge toàn CN."""
    danh_sach_file = [
        ("hstd",     f_hstd,     "📊 HSTD"),
        ("nq11",     f_nq11,     "📑 NQ11"),
        ("gqvl",     f_gqvl,     "📋 GQVL"),
        ("cdtotkvv", f_cdtotkvv, "🏆 CDTOTKVV"),
    ]

    ket_qua_upload: dict[str, KetQuaUpload] = {}
    can_merge = False

    for loai, f_obj, ten_hien in danh_sach_file:
        if f_obj is None:
            continue

        file_bytes = f_obj.read()

        # Kiểm tra cơ bản
        ok_kt, msg_kt = kiem_tra_file(f_obj.name, file_bytes)
        if not ok_kt:
            ket_qua_upload[loai] = KetQuaUpload(False, msg_kt)
            continue

        # Kiểm tra tên đơn vị trong file
        khop, msg_khop = _kiem_tra_don_vi(file_bytes, loai, ten_dv)
        if not khop:
            ket_qua_upload[loai] = KetQuaUpload(False, msg_khop)
            continue

        # Kiểm tra chất lượng dữ liệu tập trung
        _, _msg_dq, bao_cao_dq = danh_gia_chat_luong_file_upload(loai, file_bytes)
        # DQ chỉ cảnh báo, không chặn upload

        # Lưu file (không tự động merge ở đây, merge sau khi tất cả xong)
        from data.pgd import luu_file_pgd as _luu_pgd
        try:
            mb = len(file_bytes) / 1024 / 1024
            if loai == "cdtotkvv":
                from data.cdtotkvv import doc_thang_nam_tu_file
                from data.pgd import luu_file_pgd_voi_lich_su

                thang_tu_file = doc_thang_nam_tu_file(file_bytes)
                thang_luu = thang_cdtotkvv_override or thang_tu_file
                if thang_luu:
                    path = luu_file_pgd_voi_lich_su(
                        ten_dv, loai, file_bytes, thang_luu
                    )
                    ghi_chu_tay = " [tháng nhập tay]" if not thang_tu_file else ""
                    ket_qua_upload[loai] = KetQuaUpload(
                        True,
                        f"✅ {ten_hien} ({mb:.1f} MB) "
                        f"· Tháng {thang_luu}{ghi_chu_tay} · DQ {bao_cao_dq.get('ti_le_dat_chuan', 0)}%",
                        path,
                    )
                    db.ghi_audit(
                        username, "upload_pgd_khnv",
                        f"CDTOTKVV — {ten_dv} "
                        f"tháng={thang_luu}{ghi_chu_tay} ({mb:.1f} MB)"
                    )
                else:
                    path = _luu_pgd(ten_dv, loai, file_bytes)
                    ket_qua_upload[loai] = KetQuaUpload(
                        True,
                        f"✅ {ten_hien} ({mb:.1f} MB) "
                        f"· ⚠️ Không nhận diện/chọn được tháng, chỉ lưu latest · DQ {bao_cao_dq.get('ti_le_dat_chuan', 0)}%",
                        path,
                    )
                    db.ghi_audit(
                        username, "upload_pgd_khnv",
                        f"CDTOTKVV — {ten_dv} tháng=unknown_latest_only ({mb:.1f} MB)"
                    )
            else:
                path = _luu_pgd(ten_dv, loai, file_bytes)
                db.ghi_audit(username, "upload_pgd_khnv",
                             f"{loai.upper()} — {ten_dv} ({mb:.1f} MB)")
                ket_qua_upload[loai] = KetQuaUpload(
                    True,
                    f"✅ {ten_hien} ({mb:.1f} MB) · DQ {bao_cao_dq.get('ti_le_dat_chuan', 0)}%",
                    path,
                )
                if loai in ("hstd", "nq11", "gqvl"):
                    can_merge = True
        except Exception as e:
            ket_qua_upload[loai] = KetQuaUpload(False, f"Lỗi lưu: {e}")

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

    # Merge toàn CN nếu có ít nhất 1 file HSTD/NQ11/GQVL được lưu
    if can_merge:
        st.divider()
        with st.spinner("🔄 Đang tổng hợp dữ liệu toàn Chi nhánh..."):
            for loai in ("hstd", "nq11", "gqvl"):
                if loai in ket_qua_upload and ket_qua_upload[loai].thanh_cong:
                    kq_merge = merge_du_lieu_toan_cn(loai)
                    if kq_merge.thanh_cong:
                        st.success(kq_merge.thong_bao)
                    else:
                        st.warning(f"⚠️ Gộp {loai.upper()}: {kq_merge.thong_bao}")

    st.cache_data.clear()
    # Lưu kết quả vào session để render sau rerun
    st.session_state["khnv_ket_qua_upload"] = {
        k: {"thanh_cong": v.thanh_cong, "thong_bao": v.thong_bao}
        for k, v in ket_qua_upload.items()
    }
    st.rerun()


# ── Nhận diện PGD từ nội dung file (import hàng loạt) ─────────────────────────


def _nhan_dien_loai_tu_noi_dung(data: bytes, ten_file: str = "") -> str | None:
    """
    Nhận diện loại file từ nội dung — không phụ thuộc tên file.
      HSTD     : sheet BCQUERY, header row 5 có cột 'Tên PGD'
      NQ11     : sheet BCQUERY, header row 5 không có 'Tên PGD', có 'Mã ĐVUT'
      GQVL/CDTOTKVV: cùng có thể nằm ở Sheet1 -> phân biệt theo nội dung.
    """
    def _nhan_dien_loai_ten_file(ten: str) -> str | None:
        if not ten:
            return None
        upper = ten.upper()
        if upper.startswith(("CDTOTKVV", "CT_CDTOTKVV")):
            return "cdtotkvv"
        if upper.startswith(("GQVL", "SK_GQVL", "SAO_KE_GQVL")):
            return "gqvl"
        if upper.startswith(("HSTD", "CT_CDTO")):
            return "hstd"
        if upper.startswith(("NQ11", "SAO_KE_CT")):
            return "nq11"
        return None

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

        # ── GQVL/CDTOTKVV (ưu tiên CDTOTKVV trước) ───────────────────
        if "SHEET1" in sheets_upper:
            real = xl.sheet_names[sheets_upper.index("SHEET1")]
            try:
                df_check = pd.read_excel(
                    BytesIO(data), sheet_name=real, header=None, nrows=10
                )
                full_text = " ".join(
                    str(v).lower() for v in df_check.values.flatten() if pd.notna(v)
                )
                if any(
                    kw in full_text
                    for kw in ("chấm điểm", "tổng điểm", "xếp loại", "cdtotkvv")
                ):
                    return "cdtotkvv"
                return "gqvl"
            except Exception:
                loai_ten_file = _nhan_dien_loai_ten_file(ten_file)
                if loai_ten_file:
                    return loai_ten_file
                return "gqvl"

        # ── CDTOTKVV ─────────────────────────────────────────────────
        df2 = pd.read_excel(BytesIO(data), header=None, skiprows=7, nrows=3)
        if not df2.empty:
            vals = [
                str(v).strip().lower()
                for v in df2.to_numpy().flatten().tolist()
                if pd.notna(v)
            ]
            if any("tên đơn vị" in v or "ten don vi" in v for v in vals) and any(
                "tổng điểm" in v or "tong diem" in v for v in vals
            ):
                return "cdtotkvv"

    except Exception:
        loai_ten_file = _nhan_dien_loai_ten_file(ten_file)
        if loai_ten_file:
            return loai_ten_file
    return None


def _tim_ten_pgd_tu_noi_dung(
    file_bytes: bytes,
    loai: str,
    ten_file: str = "",
) -> str | None:
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
            df = pd.read_excel(buf, sheet_name="Sheet1", header=7, nrows=1)
            if df.empty:
                return None
            for col in df.columns:
                hit = _ten_doc_ve_don_vi_chuan(str(df[col].iloc[0]).strip())
                if hit:
                    return hit
            return None

        if loai == "cdtotkvv":
            # Cách 1: đọc cột C từ những dòng data đầu tiên.
            try:
                df = pd.read_excel(buf, header=None, skiprows=10, nrows=5)
                if not df.empty and df.shape[1] > 2:
                    for i in range(min(5, len(df))):
                        raw = str(df.iloc[i, 2]).strip()
                        hit = _ten_doc_ve_don_vi_chuan(raw)
                        if hit:
                            return hit
            except Exception:
                pass

            # Cách 2 fallback theo tên file: CT_CDTOTKVV_{ma_don_vi}_{ngay}.xlsx
            if ten_file:
                m = re.search(r"CDTOTKVV_(\d+)_", ten_file.upper())
                if m:
                    ma_pgd = m.group(1).zfill(6)
                    ten_ma = MA_PGD_MAP.get(ma_pgd)
                    if ten_ma and ten_ma in DS_DON_VI:
                        return ten_ma
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
        uploaded = st.file_uploader(
            "Chọn file",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="khnv_bulk_upload",
            label_visibility="collapsed",
        )

        if not uploaded:
            st.caption("Chưa có file nào được chọn.")
            return

        # ── Fallback: prefix tên file khi không đọc được loại từ nội dung ──
        PREFIX_MAP = {
            "hstd":     ("HSTD", "CT_CDTO"),
            "nq11":     ("NQ11", "SAO_KE_CT"),
            "gqvl":     ("GQVL", "SK_GQVL", "SAO_KE_GQVL"),
            "cdtotkvv": ("CDTOTKVV", "CT_CDTOTKVV"),
        }

        def _nhan_dien_loai_ten_file(ten_file: str) -> str | None:
            upper = ten_file.upper()
            for loai, prefixes in PREFIX_MAP.items():
                if any(upper.startswith(p.upper()) for p in prefixes):
                    return loai
            return None

        # ── Xây dựng danh sách rows để preview ───────────────────────
        cache_key = "khnv_bulk_bytes"
        file_names_now = [f.name for f in uploaded]
        if st.session_state.get("khnv_bulk_names") != file_names_now:
            st.session_state["khnv_bulk_names"] = file_names_now
            st.session_state[cache_key] = {f.name: f.read() for f in uploaded}

        bytes_map: dict[str, bytes] = st.session_state.get(cache_key, {})

        rows: list[dict] = []
        seen: dict[str, int] = {}

        with st.spinner("🔍 Đang nhận diện file..."):
            for ten_file, data in bytes_map.items():
                loai = _nhan_dien_loai_tu_noi_dung(data, ten_file=ten_file)
                if loai is None:
                    rows.append({
                        "ten_file": ten_file, "loai": "❓",
                        "ten_pgd": "—", "nhan_dien": False,
                        "trang_thai": "❓ Không rõ loại",
                        "co_the_import": False, "data": data,
                    })
                    continue

                ten_pgd = _tim_ten_pgd_tu_noi_dung(data, loai, ten_file=ten_file)
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
                elif _md5_bytes(data) != _md5_file(path_ht):
                    so_sanh = "🔄 Có thay đổi"
                    md5_co_the_import = True
                else:
                    so_sanh = "✅ Giống hệt"
                    md5_co_the_import = False

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
                 if "Trùng" in r["trang_thai"] and not r["co_the_import"]]
        bo_qua = [r for r in rows if not r["co_the_import"] and r["nhan_dien"]]
        st.caption(
            f"📊 Tổng **{len(rows)}** file · "
            f"✅ Sẵn sàng **{len(co_the_import)}** · "
            f"⏩ Bỏ qua **{len(bo_qua)}** (giống hệt) · "
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
    if role not in ("admin", "manager"):
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


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab=None, **kwargs) -> None:
    """
    Render tab Upload KH-NV.
    Nhận tab (st.tab object) hoặc render trực tiếp trong context hiện tại.
    """
    role     = kwargs.get("role", "")
    username = kwargs.get("username", "unknown")

    ctx = tab if tab is not None else st

    with ctx:
        if role not in ("admin", "manager"):
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
                    db.ghi_audit(
                        username,
                        "manual_merge_toan_cn",
                        f"loai={loai_chon}",
                    )
                    st.toast("✅ Tổng hợp hoàn tất!", icon="✅")

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
