"""Service xuất/nhập Excel cho luồng dữ liệu PGD → CN.

Chức năng:
- Xuất danh sách rủi ro từ PGD sang Excel
- Nhập file Excel từ PGD vào CN
- Merge dữ liệu nhiều PGD thành tổng hợp CN
"""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Optional

import pandas as pd

from services.xlrr_service import HoSoRuiRo


# ── Constants ───────────────────────────────────────────────────────────────

EXCEL_COLUMNS = [
    "id",
    "ma_kh",
    "ten_kh",
    "so_ku",
    "xa",
    "ten_pgd",
    "ten_ct",
    "du_no_goc",
    "du_no_lai",
    "bien_phap",
    "nguyen_nhan",
    "muc_do",
    "so_thang",
    "ngay_rr",
    "nguon_von",
    "trang_thai",
    # Thông tin 01/XLN
    "ngay_ky_01",
    "ma_to",
    "ten_to_truong",
    "so_tien_thiet_hai_01",
    "muc_do_thiet_hai_01",
    "kha_nang_tra_no_01",
    "ke_hoach_tra_no_01",
    # Thông tin 02/XLN
    "ngay_lap_02",
    "dia_diem_02",
    "ten_pgd_02",
    "ten_ubnd_02",
    "ten_hoi_nd_02",
    "ten_cbtd_02",
    "ten_to_truong_02",
    "chi_tiet_thiet_hai_02",
    "danh_gia_thiet_hai_02",
    "danh_gia_du_an_02",
    "tai_san_hien_tai_02",
    "kha_nang_tra_no_02",
]


# ═════════════════════════════════════════════════════════════════════════════
# EXPORT: PGD → Excel
# ═════════════════════════════════════════════════════════════════════════════

def xuat_danh_sach_rui_ro_excel(
    ds_hs: list[HoSoRuiRo],
    ten_pgd: str,
    nam: int,
    thang: int,
) -> bytes:
    """Xuất danh sách rủi ro của PGD sang Excel để gửi CN.
    
    Args:
        ds_hs: Danh sách hồ sơ rủi ro
        ten_pgd: Tên PGD
        nam: Năm báo cáo
        thang: Tháng báo cáo
        
    Returns:
        File Excel dạng bytes
    """
    if not ds_hs:
        # Trả về file Excel trống với header
        df = pd.DataFrame(columns=EXCEL_COLUMNS)
    else:
        # Chuyển đổi HoSoRuiRo sang dict
        data = []
        for hs in ds_hs:
            row = {
                "id": hs.id,
                "ma_kh": hs.ma_kh,
                "ten_kh": hs.ten_kh,
                "so_ku": hs.so_ku,
                "xa": hs.xa,
                "ten_pgd": hs.ten_pgd,
                "ten_ct": hs.ten_ct,
                "du_no_goc": hs.du_no_goc,
                "du_no_lai": hs.du_no_lai,
                "bien_phap": hs.bien_phap,
                "nguyen_nhan": hs.nguyen_nhan,
                "muc_do": hs.muc_do,
                "so_thang": hs.so_thang,
                "ngay_rr": hs.ngay_rr.isoformat() if hs.ngay_rr else None,
                "nguon_von": hs.nguon_von,
                "trang_thai": hs.trang_thai,
                # 01/XLN
                "ngay_ky_01": hs.ngay_ky_01.isoformat() if hs.ngay_ky_01 else None,
                "ma_to": hs.ma_to,
                "ten_to_truong": hs.ten_to_truong,
                "so_tien_thiet_hai_01": hs.so_tien_thiet_hai_01,
                "muc_do_thiet_hai_01": hs.muc_do_thiet_hai_01,
                "kha_nang_tra_no_01": hs.kha_nang_tra_no_01,
                "ke_hoach_tra_no_01": hs.ke_hoach_tra_no_01,
                # 02/XLN
                "ngay_lap_02": hs.ngay_lap_02.isoformat() if hs.ngay_lap_02 else None,
                "dia_diem_02": hs.dia_diem_02,
                "ten_pgd_02": hs.ten_pgd_02,
                "ten_ubnd_02": hs.ten_ubnd_02,
                "ten_hoi_nd_02": hs.ten_hoi_nd_02,
                "ten_cbtd_02": hs.ten_cbtd_02,
                "ten_to_truong_02": hs.ten_to_truong_02,
                "chi_tiet_thiet_hai_02": hs.chi_tiet_thiet_hai_02,
                "danh_gia_thiet_hai_02": hs.danh_gia_thiet_hai_02,
                "danh_gia_du_an_02": hs.danh_gia_du_an_02,
                "tai_san_hien_tai_02": hs.tai_san_hien_tai_02,
                "kha_nang_tra_no_02": hs.kha_nang_tra_no_02,
            }
            data.append(row)
        
        df = pd.DataFrame(data)
    
    # Xuất ra Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=f"XLRR_{thang:02d}_{nam}", index=False)
        
        # Thêm sheet metadata
        meta_df = pd.DataFrame({
            "Field": ["ten_pgd", "nam", "thang", "so_ho_so", "ngay_xuat"],
            "Value": [ten_pgd, nam, thang, len(ds_hs), datetime.now().isoformat()],
        })
        meta_df.to_excel(writer, sheet_name="Metadata", index=False)
    
    buf.seek(0)
    return buf.getvalue()


# ═════════════════════════════════════════════════════════════════════════════
# IMPORT: Excel → CN
# ═════════════════════════════════════════════════════════════════════════════

def nhap_danh_sach_rui_ro_excel(file_bytes: bytes) -> list[HoSoRuiRo]:
    """Đọc file Excel từ PGD, trả về list HoSoRuiRo.
    
    Args:
        file_bytes: Nội dung file Excel
        
    Returns:
        Danh sách HoSoRuiRo
    """
    buf = io.BytesIO(file_bytes)
    
    # Đọc sheet chính
    df = pd.read_excel(buf, sheet_name=0)
    
    ds_hs: list[HoSoRuiRo] = []
    
    for _, row in df.iterrows():
        # Xử lý các giá trị null
        def get_val(col, default=""):
            val = row.get(col)
            if pd.isna(val):
                return default
            return val
        
        def get_date(col):
            val = row.get(col)
            if pd.isna(val):
                return None
            if isinstance(val, str):
                try:
                    return date.fromisoformat(val)
                except ValueError:
                    return None
            if isinstance(val, datetime):
                return val.date()
            return val
        
        def get_float(col, default=0.0):
            val = row.get(col)
            if pd.isna(val):
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
        
        hs = HoSoRuiRo(
            id=str(get_val("id", "")),
            ma_kh=str(get_val("ma_kh", "")),
            ten_kh=str(get_val("ten_kh", "")),
            so_ku=str(get_val("so_ku", "")),
            xa=str(get_val("xa", "")),
            ten_pgd=str(get_val("ten_pgd", "")),
            pgd_slug="",  # Sẽ được tính lại
            ten_ct=str(get_val("ten_ct", "")),
            du_no_goc=get_float("du_no_goc"),
            du_no_lai=get_float("du_no_lai"),
            lai_ton=get_float("du_no_lai"),
            bien_phap=str(get_val("bien_phap", "khoanh")),
            nguyen_nhan=str(get_val("nguyen_nhan", "")),
            muc_do=str(get_val("muc_do", "")),
            so_thang=int(get_float("so_thang")),
            ngay_rr=get_date("ngay_rr"),
            nguon_von=int(get_val("nguon_von", 1)),
            trang_thai=str(get_val("trang_thai", "cho_duyet")),
            # 01/XLN
            ngay_ky_01=get_date("ngay_ky_01"),
            ma_to=str(get_val("ma_to", "")),
            ten_to_truong=str(get_val("ten_to_truong", "")),
            so_tien_thiet_hai_01=str(get_val("so_tien_thiet_hai_01", "")),
            muc_do_thiet_hai_01=str(get_val("muc_do_thiet_hai_01", "")),
            kha_nang_tra_no_01=str(get_val("kha_nang_tra_no_01", "")),
            ke_hoach_tra_no_01=str(get_val("ke_hoach_tra_no_01", "")),
            # 02/XLN
            ngay_lap_02=get_date("ngay_lap_02"),
            dia_diem_02=str(get_val("dia_diem_02", "")),
            ten_pgd_02=str(get_val("ten_pgd_02", "")),
            ten_ubnd_02=str(get_val("ten_ubnd_02", "")),
            ten_hoi_nd_02=str(get_val("ten_hoi_nd_02", "")),
            ten_cbtd_02=str(get_val("ten_cbtd_02", "")),
            ten_to_truong_02=str(get_val("ten_to_truong_02", "")),
            chi_tiet_thiet_hai_02=str(get_val("chi_tiet_thiet_hai_02", "")),
            danh_gia_thiet_hai_02=str(get_val("danh_gia_thiet_hai_02", "")),
            danh_gia_du_an_02=str(get_val("danh_gia_du_an_02", "")),
            tai_san_hien_tai_02=str(get_val("tai_san_hien_tai_02", "")),
            kha_nang_tra_no_02=str(get_val("kha_nang_tra_no_02", "")),
        )
        ds_hs.append(hs)
    
    return ds_hs


def merge_du_lieu_pgd_vao_cn(
    ds_hs_pgd: list[HoSoRuiRo],
    nam: int,
    thang: int,
    nguoi_nhap: str,
) -> tuple[int, list[str]]:
    """Merge dữ liệu từ PGD vào database CN.
    
    Args:
        ds_hs_pgd: Danh sách hồ sơ từ PGD
        nam: Năm
        thang: Tháng
        nguoi_nhap: Người thực hiện nhập
        
    Returns:
        Tuple (số hồ sơ đã nhập, danh sách lỗi nếu có)
    """
    from services.xlrr_service import LuuTruXLRR
    
    errors = []
    count = 0
    
    try:
        # Lấy dữ liệu hiện tại của CN
        ds_cn_hien_tai = LuuTruXLRR.doc_cn(nam, thang)
        
        # Tạo dict để tránh trùng lặp theo id
        cn_dict = {hs.id: hs for hs in ds_cn_hien_tai}
        
        # Merge dữ liệu PGD vào
        for hs in ds_hs_pgd:
            # Cập nhật metadata
            hs.nguoi_tao = nguoi_nhap
            hs.ngay_tao = datetime.now()
            cn_dict[hs.id] = hs
            count += 1
        
        # Lưu lại toàn bộ
        ds_merged = list(cn_dict.values())
        LuuTruXLRR.luu_cn(ds_merged, nam, thang, nguoi_nhap)
        
    except Exception as e:
        errors.append(str(e))
    
    return count, errors


# ═════════════════════════════════════════════════════════════════════════════
# TỔNG HỢP THEO BIỆN PHÁP (cho mẫu 04/05)
# ═════════════════════════════════════════════════════════════════════════════

def tong_hop_theo_bien_phap(
    ds_hs: list[HoSoRuiRo],
    bien_phap: str,  # "khoanh" hoặc "xoa"
) -> list[HoSoRuiRo]:
    """Lọc danh sách hồ sơ theo biện pháp xử lý.
    
    Args:
        ds_hs: Danh sách hồ sơ
        bien_phap: "khoanh" hoặc "xoa"
        
    Returns:
        Danh sách đã lọc
    """
    return [hs for hs in ds_hs if hs.bien_phap == bien_phap]


__all__ = [
    "xuat_danh_sach_rui_ro_excel",
    "nhap_danh_sach_rui_ro_excel",
    "merge_du_lieu_pgd_vao_cn",
    "tong_hop_theo_bien_phap",
]
