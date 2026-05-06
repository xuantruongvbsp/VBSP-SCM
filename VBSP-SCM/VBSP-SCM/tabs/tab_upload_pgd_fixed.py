"""
Tab Upload Dữ liệu — Hỗ trợ địa bàn (PGD tự upload file của mình).
──────────────────────────────────────────────────────────────────────
Đã sửa lỗi: Logic kiểm tra đơn vị linh hoạt hơn
"""
from io import BytesIO
import re

import pandas as pd
import streamlit as st

import db
from config import DS_PGD, DON_VI_CHI_NHANH, MA_PGD_MAP
from data.pgd import luu_file_pgd
from services.upload_service import (
    KetQuaUpload,
    kiem_tra_file,
    danh_gia_chat_luong_file_upload,
)
from services.data_priority_service import (
    bao_cao_trang_thai_nguon, cap_nhat_nguon_uu_tien,
    hien_thi_trang_thai_nguon_widget
)


# ── Danh sách 22 đơn vị ──────────────────────────────────────────────────────
DS_DON_VI: list[str] = [DON_VI_CHI_NHANH] + DS_PGD


# ── Đọc tên đơn vị từ file upload ────────────────────────────────────────

def _lay_ten_don_vi_trong_file(file_bytes: bytes, loai: str) -> str | None:
    """Đọc tên đơn vị từ file Excel theo từng loại."""
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
            df = pd.read_excel(buf, header=7, nrows=10)
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


def _chuan_hoa_ten_don_vi(ten: str) -> str:
    """Chuẩn hóa tên đơn vị để so sánh."""
    ten = ten.strip().lower()
    # Loại bỏ các từ không quan trọng
    ten = re.sub(r'\b(pgd|phòng|giao|dịch|hội|sở|chi|nhánh|tỉnh)\b', '', ten)
    # Loại bỏ ký tự đặc biệt và khoảng trắng thừa
    ten = re.sub(r'[^\w\s]', ' ', ten)
    ten = re.sub(r'\s+', ' ', ten).strip()
    return ten


def _kiem_tra_don_vi(file_bytes: bytes, loai: str, ten_dv_chon: str) -> tuple[bool, str]:
    """
    Kiểm tra tên đơn vị trong file có khớp với đơn vị đang chọn.
    ĐÃ SỬA: Logic linh hoạt hơn để tránh false positive.
    """
    ten_trong_file = _lay_ten_don_vi_trong_file(file_bytes, loai)
    
    # Nếu không đọc được tên → cho phép upload (có thể file không có metadata)
    if ten_trong_file is None:
        return True, "⚠️ Không đọc được tên đơn vị từ file — tiếp tục lưu."
    
    # Kiểm tra khớp chính xác trước
    if ten_trong_file.strip() == ten_dv_chon.strip():
        return True, f"✅ Đơn vị khớp: **{ten_trong_file}**"
    
    # Chuẩn hóa và kiểm tra lại
    ten_file_chuan = _chuan_hoa_ten_don_vi(ten_trong_file)
    ten_chon_chuan = _chuan_hoa_ten_don_vi(ten_dv_chon)
    
    # Khớp sau chuẩn hóa
    if ten_file_chuan == ten_chon_chuan:
        return True, f"✅ Đơn vị khớp (chuẩn hóa): **{ten_trong_file}**"
    
    # Kiểm tra chứa từ khóa chính (để tránh reject file hợp lệ)
    if ten_file_chuan and ten_chon_chuan and len(ten_file_chuan) > 2:
        if ten_file_chuan in ten_chon_chuan or ten_chon_chuan in ten_file_chuan:
            return True, f"✅ Đơn vị tương tự: **{ten_trong_file}**"
    
    # Trường hợp đặc biệt: "Hội sở Chi nhánh" vs tên khác
    if "hội sở" in ten_chon_chuan and any(x in ten_file_chuan for x in ["biên hòa", "chi nhánh", "đồng nai"]):
        return True, f"✅ Thuộc Hội sở: **{ten_trong_file}**"
    
    # Thực sự không khớp
    return False, (
        f"⚠️ Upload nhầm đơn vị! File chứa: **{ten_trong_file}** | Đang chọn: **{ten_dv_chon}**"
    )


# ── Form upload ───────────────────────────────────────────────────────────────

def _render_upload_form(ten_dv: str, prefix: str, username: str) -> None:
    """Form upload 4 file cho đơn vị. Không merge toàn CN (việc của KH-NV)."""
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

    co_file = any(f is not None for f in [f_hstd, f_nq11, f_gqvl, f_cdtotkvv])
    if not co_file:
        st.info("Chọn ít nhất 1 file để bắt đầu upload.")
        return

    if st.button("📤 Upload", type="primary", key=f"{prefix}_btn_upload"):
        _xu_ly_upload(ten_dv, username, f_hstd, f_nq11, f_gqvl, f_cdtotkvv)


def _xu_ly_upload(ten_dv: str, username: str, f_hstd, f_nq11, f_gqvl, f_cdtotkvv) -> None:
    """Xử lý upload, kiểm tra đơn vị, lưu file."""
    danh_sach_file = [
        ("hstd",     f_hstd,     "📊 HSTD"),
        ("nq11",     f_nq11,     "📑 NQ11"),
        ("gqvl",     f_gqvl,     "📋 GQVL"),
        ("cdtotkvv", f_cdtotkvv, "🏆 CDTOTKVV"),
    ]

    ket_qua_upload: dict[str, KetQuaUpload] = {}
    co_luu_thanh_cong = False

    for loai, f_obj, ten_hien in danh_sach_file:
        if f_obj is None:
            continue

        file_bytes = f_obj.read()

        # Kiểm tra cơ bản (định dạng, kích thước)
        ok_kt, msg_kt = kiem_tra_file(f_obj.name, file_bytes)
        if not ok_kt:
            ket_qua_upload[loai] = KetQuaUpload(False, msg_kt)
            continue

        # Kiểm tra tên đơn vị trong file (ĐÃ SỬA - linh hoạt hơn)
        khop, msg_khop = _kiem_tra_don_vi(file_bytes, loai, ten_dv)
        if not khop:
            # Upload nhầm đơn vị → hiển thị cảnh báo, không lưu
            st.warning(msg_khop)
            ket_qua_upload[loai] = KetQuaUpload(False, msg_khop)
            continue

        # Kiểm tra chất lượng dữ liệu tập trung trước khi lưu
        ok_dq, msg_dq, bao_cao_dq = danh_gia_chat_luong_file_upload(loai, file_bytes)
        if not ok_dq:
            ket_qua_upload[loai] = KetQuaUpload(False, msg_dq)
            continue

        # Lưu file
        try:
            path = luu_file_pgd(ten_dv, loai, file_bytes)
            mb = len(file_bytes) / 1024 / 1024
            db.ghi_audit(username, "upload_pgd_dia_ban",
                         f"{loai.upper()} — {ten_dv} ({mb:.1f} MB)")
            ket_qua_upload[loai] = KetQuaUpload(
                True,
                f"✅ {ten_hien} ({mb:.1f} MB) · DQ {bao_cao_dq.get('ti_le_dat_chuan', 0)}%",
                path,
            )
            co_luu_thanh_cong = True
        except Exception as e:
            ket_qua_upload[loai] = KetQuaUpload(False, f"Lỗi lưu: {e}")

    # Hiển thị kết quả từng file
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

    if co_luu_thanh_cong:
        st.success(
            "✅ Đã upload thành công. "
            "Phòng KH-NV sẽ tổng hợp dữ liệu toàn Chi nhánh."
        )

    st.rerun()


# ── Entry point ───────────────────────────────────────────────────────────────

def render(tab=None, **kwargs) -> None:
    """
    Render tab Upload Dữ liệu cho CBTD địa bàn.
    """
    role     = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user", "")

    ctx = tab if tab is not None else st

    with ctx:
        st.subheader("📤 Upload Dữ liệu — Địa bàn")
        st.caption(
            "Upload file HSTD · NQ11 · GQVL · CDTOTKVV của đơn vị mình · "
            "Phòng KH-NV sẽ tổng hợp toàn Chi nhánh"
        )
        
        # Hiển thị thông báo ưu tiên nguồn dữ liệu
        st.info(
            "🎯 **Ưu tiên nguồn dữ liệu:** Hệ thống sẽ ưu tiên sử dụng dữ liệu "
            "mà PGD tự upload thay vì dữ liệu từ hệ thống tập trung. "
            "Điều này đảm bảo tính chính xác và kịp thời của báo cáo địa bàn."
        )

        # ── Xác định đơn vị hiển thị ───────────────────────────────────────
        if role == "user":
            # CBTD chỉ thấy đơn vị của mình
            ten_dv = pgd_user or (DS_PGD[0] if DS_PGD else DON_VI_CHI_NHANH)
            st.info(f"🏢 Đơn vị của bạn: **{ten_dv}**")
        else:
            # admin/manager có thể chọn bất kỳ đơn vị
            ten_dv = st.selectbox(
                "🏢 Chọn đơn vị upload",
                DS_DON_VI,
                key="pgd_upload_chon_don_vi",
            )

        st.divider()

        # ── Form upload ────────────────────────────────────────────────────
        prefix = f"pgd_{ten_dv.lower().replace(' ', '_').replace('/', '_')}"
        _render_upload_form(ten_dv, prefix, username)