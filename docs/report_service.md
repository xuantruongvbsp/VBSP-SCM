# Module services.report_service

## Tổng quan

Module `services.report_service` cung cấp chức năng xuất báo cáo Excel với định dạng chuẩn cho VBSP-SCM, bao gồm:

- Sheet "Bìa" với logo, thông tin báo cáo
- Định dạng header chuẩn (bold + background xanh nhạt)
- Freeze panes và auto column width
- Format số tiền tự động bằng `utils.fmt()`

## Các hàm chính

### `xuat_bao_cao(sheets, tieu_de, nguoi_xuat) -> bytes`

Xuất báo cáo Excel với nhiều sheet và sheet bìa tự động.

**Tham số:**
- `sheets`: `Dict[str, pd.DataFrame]` - Dictionary tên sheet và DataFrame
- `tieu_de`: `str` - Tiêu đề báo cáo hiển thị trong sheet Bìa
- `nguoi_xuat`: `str` - Tên người xuất báo cáo

**Trả về:** `bytes` - Nội dung file Excel để download

**Ví dụ:**
```python
from services import xuat_bao_cao, ten_file_bao_cao

sheets = {
    'Danh sách KH': df_customers,
    'Tổng hợp PGD': df_branches
}

file_bytes = xuat_bao_cao(
    sheets=sheets,
    tieu_de="BÁO CÁO TÍN DỤNG THÁNG 4/2026",
    nguoi_xuat="Nguyễn Văn Admin"
)

# Trong Streamlit
st.download_button(
    label="📥 Tải Excel",
    data=file_bytes,
    file_name=ten_file_bao_cao("BaoCao"),
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
```

### `xuat_sheet_don(df, tieu_de, nguoi_xuat) -> bytes`

Xuất nhanh 1 DataFrame thành Excel với sheet bìa.

**Tham số:**
- `df`: `pd.DataFrame` - DataFrame cần xuất
- `tieu_de`: `str` - Tiêu đề báo cáo
- `nguoi_xuat`: `str` - Tên người xuất

**Trả về:** `bytes` - Nội dung file Excel

### `ten_file_bao_cao(prefix, ext="xlsx") -> str`

Tạo tên file báo cáo với timestamp.

**Tham số:**
- `prefix`: `str` - Tiền tố tên file
- `ext`: `str` - Phần mở rộng (mặc định "xlsx")

**Trả về:** `str` - Tên file dạng `{prefix}_DDMMYYYY.{ext}`

## Tính năng

### Sheet "Bìa"
- Logo VBSP (nếu có file `assets/logo.png`)
- Tên ngân hàng và chi nhánh
- Tiêu đề báo cáo (in hoa, màu xanh)
- Ngày xuất, người xuất, thời gian
- Ghi chú tự động

### Sheet dữ liệu
- **Freeze panes:** Dòng 1 (header) luôn hiển thị
- **Header styling:** Bold + background xanh nhạt `#DAEEF3`
- **Auto column width:** Tối đa 50 ký tự, tối thiểu 8
- **Format số tiền:** Tự động nhận diện và format bằng `utils.fmt()`
- **Border:** Toàn bộ vùng dữ liệu có border mảnh

### Nhận diện cột tiền tự động

Hệ thống tự động nhận diện cột chứa số tiền dựa trên:
- Tên cột chứa từ khóa: `tiền`, `dư nợ`, `du_no`, `doanh số`, `giá trị`, `tổng`, `phí`, `lãi`, `nợ`
- Kiểu dữ liệu numeric

Các cột được nhận diện sẽ:
- Format theo `utils.fmt()` (tỷ/triệu)
- Align right
- Giữ nguyên giá trị gốc trong Excel

## Yêu cầu hệ thống

```python
# requirements.txt
openpyxl>=3.0.0
pandas>=1.3.0
```

## Import

```python
# Từ services package
from services import xuat_bao_cao, xuat_sheet_don, ten_file_bao_cao

# Hoặc import trực tiếp
from services.report_service import xuat_bao_cao, xuat_sheet_don, ten_file_bao_cao
```

## Lưu ý

1. **Logo:** Đặt file `assets/logo.png` để tự động thêm vào sheet Bìa
2. **Encoding:** Module xử lý tiếng Việt có dấu, nhưng tránh emoji trong môi trường Windows
3. **Performance:** Với file lớn (>10k rows), chỉ sample 5 dòng đầu để tính column width
4. **Sheet names:** Tên sheet tự động cắt về 31 ký tự (giới hạn Excel)

## Tích hợp Streamlit

```python
# Tab báo cáo chuẩn
def tab_bao_cao():
    st.header("📊 Xuất báo cáo Excel")
    
    col1, col2 = st.columns(2)
    with col1:
        tieu_de = st.text_input("Tiêu đề báo cáo", "BÁO CÁO TÍN DỤNG")
    with col2:
        nguoi_xuat = st.text_input("Người xuất", st.session_state.username)
    
    if st.button("🚀 Xuất báo cáo"):
        sheets = {"Dữ liệu": df_data}  # Thêm sheets khác nếu cần
        
        file_bytes = xuat_bao_cao(sheets, tieu_de, nguoi_xuat)
        
        st.download_button(
            label="📥 Tải xuống Excel",
            data=file_bytes,
            file_name=ten_file_bao_cao("BaoCao"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.success(f"✅ Đã tạo báo cáo với {len(sheets)} sheet dữ liệu!")
```