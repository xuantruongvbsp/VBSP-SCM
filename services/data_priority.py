"""Hiển thị trạng thái dữ liệu PGD — chỉ dùng cho widget sidebar/status, không quyết định nguồn."""
import os
from datetime import datetime
from typing import Dict
import db
from config import DS_PGD, DON_VI_CHI_NHANH
from data.pgd import duong_dan_pgd, doc_trang_thai_file

def kiem_tra_nguon_uu_tien(ten_don_vi: str, loai_file: str) -> Dict:
    """Kiểm tra trạng thái file pgd_data/ của một đơn vị — chỉ dùng để hiển thị widget."""
    from pathlib import Path
    path = Path(duong_dan_pgd(ten_don_vi, loai_file))
    _mtime = os.path.getmtime(path) if path.exists() else 0.0
    pgd_info = doc_trang_thai_file(ten_don_vi, loai_file, mtime=_mtime)
    
    if pgd_info["co_file"]:
        return {
            "nguon_uu_tien": "pgd_upload",
            "duong_dan": duong_dan_pgd(ten_don_vi, loai_file),
            "ly_do": f"✅ Đã upload từ {ten_don_vi}",
            "canh_bao": [f"⚠️ Dữ liệu cũ {pgd_info['so_ngay_cu']} ngày"] if pgd_info["canh_bao"] == "cu" else []
        }
    else:
        return {
            "nguon_uu_tien": "chua_upload",
            "duong_dan": "",
            "ly_do": f"📤 {ten_don_vi} chưa upload {loai_file.upper()}",
            "canh_bao": [f"📤 {ten_don_vi} chưa upload {loai_file.upper()}"]
        }
