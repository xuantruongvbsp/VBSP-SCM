# Hướng dẫn sử dụng Quản lý Template

## Tổng quan

Module "📁 Quản lý Template" trong workspace Management (Phòng KH-NV) cho phép admin/manager:

1. **Upload template Word mới** (.docx)
2. **Xem danh sách template** với thông tin chi tiết
3. **Xóa template** không cần thiết
4. **Test template** với dữ liệu thực

## Quyền truy cập

✅ **Admin/Manager:** Thấy đầy đủ tab "📁 Quản lý Template"
❌ **User:** Không thấy tab này

## Tính năng chi tiết

### 1. 📤 Upload mẫu mới

- **Input:** File .docx từ máy tính
- **Tùy chọn:** Đổi tên file khi lưu
- **Kiểm tra:** File trùng tên, ghi đè
- **Lưu trữ:** Thư mục `templates/`

**Cách sử dụng:**
1. Chọn file .docx
2. Tùy chọn đổi tên (VD: "Mau_To_trinh_NOXH")
3. Nhấn "💾 Lưu Template"

### 2. 📋 Danh sách Template

**Hiển thị thông tin:**
- Tên hiển thị
- Tên file gốc
- Kích thước (KB)
- Ngày tạo/sửa

**Chức năng xóa:**
- Chọn template từ dropdown
- Xác nhận xóa
- Cập nhật danh sách tự động

### 3. 🧪 Test Template

**Chọn đối tượng test:**
- Template từ danh sách có sẵn
- Hồ sơ khách hàng (10 mẫu đầu)

**Thông tin hiển thị:**
- Mã KH, Tên KH
- Số khoản vay, Mức vay
- Dư nợ, Ngày vay, Thời hạn, Lãi suất

**Kết quả:**
- File Word đã điền thông tin
- Tên file: `Test_{Template}_{DateTime}.docx`
- Download trực tiếp

## Template Tags hỗ trợ

Hệ thống sử dụng `TAG_MAP` từ config.py:

```
{{ma_kh}}        → Mã khách hàng
{{ten_kh}}       → Tên khách hàng  
{{so_ku}}        → Số khoản vay
{{muc_vay}}      → Mức vay (đồng)
{{du_no}}        → Dư nợ hiện tại
{{ngay_vay}}     → Ngày giải ngân
{{thoi_han}}     → Thời hạn (tháng)
{{lai_suat}}     → Lãi suất (%)
{{ngay_in}}      → Ngày in hiện tại
{{nguoi_ky}}     → Người ký (từ extra_data)
{{chuc_vu}}      → Chức vụ (từ extra_data)
```

## Cấu trúc thư mục

```
VBSP-SCM/
├── templates/              # Thư mục chứa template
│   ├── Mau_To_trinh.docx   # Template tờ trình
│   ├── Mau_Quyet_dinh.docx # Template quyết định
│   └── Mau_Hop_dong.docx   # Template hợp đồng
├── workspaces/
│   └── ws_management.py    # Chứa _render_quan_ly_template()
└── config.py              # TAG_MAP định nghĩa tags
```

## Luồng hoạt động

1. **Admin/Manager login** → Vào workspace Management
2. **Chọn tab "📁 Quản lý Template"** 
3. **Upload template mới:**
   - Chọn file .docx có sẵn tags `{{ma_kh}}`, `{{ten_kh}}`...
   - Lưu với tên mô tả rõ ràng
4. **Test template:**
   - Chọn template vừa upload
   - Chọn hồ sơ khách hàng bất kỳ
   - Download file Word đã điền dữ liệu
5. **Kiểm tra kết quả:** Mở file Word, xem tags đã được thay thế

## Ví dụ Template Word

**Nội dung file .docx:**

```
NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM
CHI NHÁNH NGÂN HÀNG CHÍNH SÁCH XÃ HỘI THÀNH PHỐ ĐỒNG NAI

TỜ TRÌNH
Về việc cho vay vốn Nhà ở xã hội

Kính gửi: Ban Giám đốc Chi nhánh

1. Thông tin khách hàng:
   - Họ và tên: {{ten_kh}}
   - Mã khách hàng: {{ma_kh}}
   - Số khoản vay: {{so_ku}}

2. Thông tin khoản vay:
   - Mức vay: {{muc_vay}} đồng
   - Thời hạn: {{thoi_han}} tháng  
   - Lãi suất: {{lai_suat}}%/năm
   - Ngày giải ngân: {{ngay_vay}}

Ngày {{ngay_in}}
{{chuc_vu}}
{{nguoi_ky}}
```

**Kết quả sau khi test:**

```
NGÂN HÀNG CHÍNH SÁCH XÃ HỘI VIỆT NAM  
CHI NHÁNH NGÂN HÀNG CHÍNH SÁCH XÃ HỘI THÀNH PHỐ ĐỒNG NAI

TỜ TRÌNH
Về việc cho vay vốn Nhà ở xã hội

Kính gửi: Ban Giám đốc Chi nhánh

1. Thông tin khách hàng:
   - Họ và tên: Nguyễn Văn A
   - Mã khách hàng: KH001
   - Số khoản vay: 001/2024

2. Thông tin khoản vay:
   - Mức vay: 500 triệu đồng
   - Thời hạn: 240 tháng
   - Lãi suất: 6.5%/năm  
   - Ngày giải ngân: 15/01/2024

Ngày 27/04/2026
Phó Giám đốc Chi nhánh
Nguyễn Văn Test Manager
```

## Lợi ích

✅ **Tập trung quản lý:** Tất cả template ở 1 nơi
✅ **Upload dễ dàng:** Drag & drop file .docx
✅ **Test trước khi dùng:** Đảm bảo template hoạt động
✅ **Phân quyền rõ ràng:** Chỉ admin/manager quản lý
✅ **Tích hợp sẵn:** Dùng luôn trong các báo cáo NOXH 2026

## Troubleshooting

**Q: Template không hiển thị sau upload?**
A: Kiểm tra file .docx có bị lỗi không. Thử upload file khác.

**Q: Test template báo lỗi?**  
A: Kiểm tra tags trong template có đúng format `{{tag_name}}` không.

**Q: Không thấy tab "📁 Quản lý Template"?**
A: Chỉ admin/manager mới thấy. Kiểm tra role trong session.

**Q: File test không có dữ liệu?**
A: Đảm bảo đã upload dữ liệu HSTD ở tab Upload trước.
