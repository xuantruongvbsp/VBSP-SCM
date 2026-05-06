"""Widget hiển thị trạng thái nguồn dữ liệu"""
import streamlit as st
from services.data_priority import kiem_tra_nguon_uu_tien
from config import DON_VI_CHI_NHANH

def render_status_compact(pgd_user: str = None):
    """Hiển thị widget trạng thái ngắn gọn"""
    don_vi = pgd_user if pgd_user else DON_VI_CHI_NHANH
    
    # Kiểm tra 3 loại file chính
    ds_loai = ["hstd", "nq11", "gqvl"]
    co_loi = False
    co_canh_bao = False
    
    for loai in ds_loai:
        tt = kiem_tra_nguon_uu_tien(don_vi, loai)
        if tt["nguon_uu_tien"] == "khong_co":
            co_loi = True
            break
        elif tt["canh_bao"]:
            co_canh_bao = True
    
    # Hiển thị theo mức độ
    if co_loi:
        st.error("🔴 **Nguồn dữ liệu:** Thiếu file quan trọng")
    elif co_canh_bao:
        st.warning("🟡 **Nguồn dữ liệu:** Cần cập nhật")
    else:
        st.success("🟢 **Nguồn dữ liệu:** Đầy đủ và mới")

def render_priority_info(don_vi: str):
    """Hiển thị thông tin ưu tiên cho đơn vị"""
    st.markdown(f"#### 📊 Trạng thái dữ liệu: **{don_vi}**")
    
    cols = st.columns(3)
    ds_loai = [("hstd", "📊 HSTD"), ("nq11", "📑 NQ11"), ("gqvl", "📋 GQVL")]
    
    for i, (loai, label) in enumerate(ds_loai):
        with cols[i]:
            tt = kiem_tra_nguon_uu_tien(don_vi, loai)
            
            if tt["nguon_uu_tien"] == "pgd_upload":
                if not tt["canh_bao"]:
                    st.success(f"**{label}**\n🔵 PGD (mới)")
                else:
                    st.warning(f"**{label}**\n🟡 PGD (cũ)")
            elif tt["nguon_uu_tien"] == "he_thong":
                st.info(f"**{label}**\n🟢 Hệ thống")
            else:
                st.error(f"**{label}**\n❌ Thiếu")
            
            st.caption(tt["ly_do"])