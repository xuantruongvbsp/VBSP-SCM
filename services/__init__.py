"""Package services — các dịch vụ dùng chung toàn ứng dụng.

Import được bọc try/except để health_check.py và telegram_service có thể
import từ package này mà không cần streamlit (chỉ ảnh hưởng môi trường
standalone — trong app/venv streamlit luôn có mặt và các re-export hoạt động
bình thường).
"""
try:
    from services.upload_service import (
        KetQuaUpload,
        FILES_HE_THONG,
        kiem_tra_file,
        kiem_tra_file_he_thong,
        luu_file_he_thong,
        luu_dienbao,
        trich_xuat_ky_dienbao,
        luu_pgd_file,
        luu_cdtotkvv,
        merge_du_lieu_toan_cn,
        lay_meta_chat_luong,
        danh_gia_chat_luong_file_upload,
    )
    from services.data_quality import (
        CANONICAL_SCHEMA,
        DataQualityResult,
        chuan_hoa_ten_cot,
        chuan_hoa_ma_don_vi,
        kiem_tra_chat_luong,
        tong_hop_bao_cao_chat_luong,
    )
    from services.ct_discovery import (
        quet_va_ghi_chuong_trinh,
        doc_ct_registry,
        ghi_ct_registry,
        doc_ket_qua_quet_cuoi,
    )
    from services.report_service import (
        xuat_bao_cao,
        xuat_sheet_don,
        ten_file_bao_cao,
    )
    from services.data_priority_service import (
        bao_cao_trang_thai_nguon,
        cap_nhat_nguon_uu_tien,
        lay_bao_cao_nguon,
        render_widget_trang_thai,
        lay_thong_tin_nguon_hien_tai,
        thong_ke_su_dung_nguon,
        hien_thi_trang_thai_nguon_widget,
        hien_thi_tong_quan_nguon,
    )
except ImportError:
    pass
# data_priority.py không nằm trong services/ — import trực tiếp khi cần:
# from data_priority import kiem_tra_nguon_uu_tien
# lay_du_lieu_uu_tien đã xóa theo kiến trúc 2 luồng (HUONG_DAN_NGUON_DU_LIEU.md)

__all__ = [
    # upload_service
    "KetQuaUpload",
    "FILES_HE_THONG",
    "kiem_tra_file",
    "kiem_tra_file_he_thong",
    "luu_file_he_thong",
    "luu_dienbao",
    "trich_xuat_ky_dienbao",
    "luu_pgd_file",
    "luu_cdtotkvv",
    "merge_du_lieu_toan_cn",
    "lay_meta_chat_luong",
    "danh_gia_chat_luong_file_upload",
    # data_quality
    "CANONICAL_SCHEMA",
    "DataQualityResult",
    "chuan_hoa_ten_cot",
    "chuan_hoa_ma_don_vi",
    "kiem_tra_chat_luong",
    "tong_hop_bao_cao_chat_luong",
    # ct_discovery
    "quet_va_ghi_chuong_trinh",
    "doc_ct_registry",
    "ghi_ct_registry",
    "doc_ket_qua_quet_cuoi",
    # report_service
    "xuat_bao_cao",
    "xuat_sheet_don", 
    "ten_file_bao_cao",
    # data_priority_service
    "bao_cao_trang_thai_nguon",
    "cap_nhat_nguon_uu_tien",
    "lay_bao_cao_nguon",
    "render_widget_trang_thai",
    "lay_thong_tin_nguon_hien_tai",
    "thong_ke_su_dung_nguon",
    "hien_thi_trang_thai_nguon_widget",
    "hien_thi_tong_quan_nguon",
]
