"""
Ví dụ sử dụng services.report_service cho xuất báo cáo Excel chuẩn VBSP.

Cách sử dụng trong Streamlit:
    from services import xuat_bao_cao, ten_file_bao_cao
    
    # Chuẩn bị dữ liệu
    sheets = {"Dữ liệu": df}
    
    # Xuất báo cáo
    file_bytes = xuat_bao_cao(sheets, "Báo cáo tháng", "Tên người xuất")
    
    # Download button
    st.download_button(
        label="📥 Tải xuống Excel", 
        data=file_bytes,
        file_name=ten_file_bao_cao("BaoCao"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
"""

import pandas as pd
from services import xuat_bao_cao, xuat_sheet_don, ten_file_bao_cao

# Tạo dữ liệu mẫu
def tao_du_lieu_mau():
    """Tạo dữ liệu mẫu cho báo cáo."""
    
    # DataFrame khách hàng
    df_khach_hang = pd.DataFrame({
        'Mã KH': ['KH001', 'KH002', 'KH003', 'KH004'],
        'Tên khách hàng': [
            'Nguyễn Văn An', 'Trần Thị Bình', 
            'Lê Văn Cường', 'Phạm Thị Dung'
        ],
        'Số tiền vay': [500_000_000, 750_000_000, 1_200_000_000, 300_000_000],
        'Dư nợ hiện tại': [450_000_000, 600_000_000, 1_000_000_000, 250_000_000],
        'Ngày giải ngân': pd.to_datetime([
            '2023-01-15', '2023-03-20', '2022-12-05', '2024-02-10'
        ]),
        'Trạng thái': ['Bình thường', 'Bình thường', 'Quá hạn', 'Bình thường']
    })
    
    # DataFrame tổng hợp theo PGD
    df_pgd = pd.DataFrame({
        'Phòng giao dịch': ['PGD Hà Nội', 'PGD Hồ Chí Minh', 'PGD Đà Nẵng'],
        'Số khách hàng': [1250, 2100, 850],
        'Tổng dư nợ': [25_000_000_000, 42_000_000_000, 15_500_000_000],
        'Nợ quá hạn': [1_200_000_000, 1_800_000_000, 650_000_000],
        'Tỷ lệ nợ xấu (%)': [4.8, 4.3, 4.2]
    })
    
    return df_khach_hang, df_pgd

def vi_du_xuat_nhieu_sheet():
    """Ví dụ xuất báo cáo nhiều sheet với sheet bìa."""
    print("=== VÍ DỤ: Xuất báo cáo nhiều sheet ===")
    
    df_kh, df_pgd = tao_du_lieu_mau()
    
    # Chuẩn bị dictionary sheets
    sheets = {
        'Danh sách khách hàng': df_kh,
        'Tổng hợp theo PGD': df_pgd
    }
    
    # Xuất báo cáo
    file_bytes = xuat_bao_cao(
        sheets=sheets,
        tieu_de="BÁO CÁO TÍN DỤNG THÁNG 4/2026",
        nguoi_xuat="Nguyễn Văn Admin"
    )
    
    # Lưu file
    ten_file = ten_file_bao_cao("BaoCaoTinDung")
    with open(ten_file, 'wb') as f:
        f.write(file_bytes)
    
    print(f"✓ Đã tạo file: {ten_file}")
    print(f"✓ Kích thước: {len(file_bytes):,} bytes")
    print(f"✓ Số sheet: {len(sheets) + 1} (bao gồm sheet Bìa)")

def vi_du_xuat_sheet_don():
    """Ví dụ xuất báo cáo 1 sheet đơn giản."""
    print("\n=== VÍ DỤ: Xuất sheet đơn ===")
    
    df_kh, _ = tao_du_lieu_mau()
    
    # Xuất 1 sheet
    file_bytes = xuat_sheet_don(
        df=df_kh,
        tieu_de="DANH SÁCH KHÁCH HÀNG VAY VỐN",
        nguoi_xuat="Trần Thị Quản lý"
    )
    
    # Lưu file
    ten_file = ten_file_bao_cao("DanhSachKhachHang")
    with open(ten_file, 'wb') as f:
        f.write(file_bytes)
    
    print(f"✓ Đã tạo file: {ten_file}")
    print(f"✓ Kích thước: {len(file_bytes):,} bytes")

def vi_du_su_dung_trong_streamlit():
    """Mã mẫu sử dụng trong Streamlit app."""
    code = '''
# === TRONG STREAMLIT APP ===
import streamlit as st
from services import xuat_bao_cao, ten_file_bao_cao

def tao_bao_cao_excel(df_data, ten_bao_cao, nguoi_xuat):
    """Tạo và download báo cáo Excel."""
    
    # Chuẩn bị sheets
    sheets = {"Dữ liệu chính": df_data}
    
    # Có thể thêm nhiều sheet khác
    if 'df_tong_hop' in locals():
        sheets["Tổng hợp"] = df_tong_hop
    
    # Xuất báo cáo
    file_bytes = xuat_bao_cao(sheets, ten_bao_cao, nguoi_xuat)
    
    # Download button
    st.download_button(
        label="📥 Tải xuống báo cáo Excel",
        data=file_bytes,
        file_name=ten_file_bao_cao("BaoCao"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Sử dụng trong tab báo cáo
if st.button("Xuất báo cáo"):
    tao_bao_cao_excel(df, "BÁO CÁO THÁNG", st.session_state.username)
    '''
    
    print("\n=== MÃ MẪU STREAMLIT ===")
    print(code)

if __name__ == "__main__":
    vi_du_xuat_nhieu_sheet()
    vi_du_xuat_sheet_don()
    vi_du_su_dung_trong_streamlit()
    
    print("\n🎉 Hoàn thành các ví dụ!")
    print("\nTính năng chính:")
    print("- Sheet 'Bìa' tự động với logo, thông tin báo cáo")
    print("- Header bold + background xanh nhạt #DAEEF3")
    print("- Freeze row 1 cho dễ xem")
    print("- Auto column width (tối đa 50)")
    print("- Format cột tiền bằng utils.fmt()")
    print("- Border cho toàn bộ dữ liệu")