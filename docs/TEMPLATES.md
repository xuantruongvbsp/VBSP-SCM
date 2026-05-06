# Template Word VBSP-SCM
> Hướng dẫn quản lý và sử dụng template Word mẫu chuẩn NHCSXH
> Cập nhật: 06/05/2026

---

## Thư mục templates/

Chứa file Word mẫu chuẩn NHCSXH đã chèn placeholder `{{...}}` để tự động điền dữ liệu.

```
templates/
├── mau_06td.docx         # Phiếu kiểm tra sử dụng vốn vay
├── mau_16td.docx         # Biên bản kiểm tra Tổ TK&VV
├── mau_15td.docx         # Danh sách đối chiếu số dư (chờ template)
├── ke_hoach_kt.docx      # Kế hoạch kiểm tra GS ủy thác (chờ template)
├── bb_xac_minh_no.docx   # Biên bản xác minh nợ chiếm dụng (chờ template)
└── README.md             # Hướng dẫn cơ bản
```

---

## Danh sách template

| File | Mẫu | Trạng thái | Sub-tab |
|---|---|---|---|
| `mau_06td.docx` | Phiếu KT sử dụng vốn | ✅ Sẵn sàng | tab_uy_thac → Mẫu 06 |
| `mau_16td.docx` | BB kiểm tra Tổ TK&VV | ✅ Sẵn sàng | tab_uy_thac → Mẫu 16 |
| `mau_15td.docx` | DS đối chiếu số dư | ⏳ Chờ template | tab_uy_thac → Mẫu 15 |
| `ke_hoach_kt.docx` | KH kiểm tra GS ủy thác | ⏳ Chờ template | tab_uy_thac → KH KT |
| `bb_xac_minh_no.docx` | BB xác minh nợ chiếm dụng | ⏳ Chờ template | TBD |

---

## Cú pháp placeholder (docxtpl)

### Biến đơn
```
{{ten_truong}}
```
Ví dụ: `{{ten_kh}}`, `{{so_ku}}`, `{{ten_pgd}}`

### Vòng lặp bảng
```
{%tr for kh in ds_kh %}
{{kh.ten_kh}}    {{kh.so_ku}}    {{kh.du_no}}
{%tr endfor %}
```

### Điều kiện
```
{% if co_tai_san_dam_bao %}
Có tài sản đảm bảo: {{tai_san}}
{% endif %}
```

### Ngày tháng định dạng
```
{{ngay_ky|date:"dd/MM/yyyy"}}
```

---

## Hằng số template (services/template_service.py)

```python
# services/template_service.py

TMPL_MAU06    = "mau_06td.docx"      # Phiếu KT sử dụng vốn
TMPL_MAU06A   = "mau_06atd.docx"     # Phiếu KT mở rộng
TMPL_MAU15    = "mau_15td.docx"      # DS đối chiếu số dư
TMPL_MAU16    = "mau_16td.docx"      # BB kiểm tra Tổ TK&VV
TMPL_KH_KT    = "ke_hoach_kt.docx"    # KH kiểm tra GS ủy thác
TMPL_BB_XMN   = "bb_xac_minh_no.docx" # BB xác minh nợ chiếm dụng
```

---

## API sử dụng template

### 1. Kiểm tra template tồn tại
```python
from services.template_service import co_template, TMPL_MAU06

if co_template(TMPL_MAU06):
    # Template có sẵn
    pass
else:
    st.warning("Template chưa được upload")
```

### 2. Điền dữ liệu vào template
```python
from services.template_service import dien_template

context = {
    "ten_kh": "Nguyễn Văn A",
    "so_ku": "12345",
    "ten_pgd": "PGD Long Thành",
    "ngay_ky": "06/05/2026",
    "ds_kh": [
        {"ten_kh": "A", "so_ku": "001", "du_no": 100000000},
        {"ten_kh": "B", "so_ku": "002", "du_no": 200000000},
    ]
}

docx_bytes = dien_template(TMPL_MAU06, context)
```

### 3. Tạo nút tải Word + PDF
```python
from services.template_service import nut_tai_word_va_pdf

nut_tai_word_va_pdf(
    docx_bytes=docx_bytes,
    ten_file_goc="Mau06_PGD_LongThanh_06052026",
    key_prefix="mau06_001"
)
```

---

## Thêm template mới

### Bước 1: Chuẩn bị file Word mẫu
1. Mở file Word mẫu chuẩn của NHCSXH
2. Xác định các vị trí cần điền dữ liệu
3. Thay các dấu `......` hoặc `[_]` bằng placeholder `{{ten_field}}`

### Bước 2: Lưu vào thư mục templates/
```
templates/
└── ten_template_moi.docx
```

### Bước 3: Thêm hằng số vào template_service.py
```python
# services/template_service.py
TMPL_TEN_MOI = "ten_template_moi.docx"
```

### Bước 4: Test trước khi dùng
```bash
# Chạy test script
python test_template.py
```

### Bước 5: Sử dụng trong tab
```python
from services.template_service import dien_template, nut_tai_word_va_pdf, TMPL_TEN_MOI

context = {"field1": "value1", "field2": "value2"}
docx_bytes = dien_template(TMPL_TEN_MOI, context)
nut_tai_word_va_pdf(docx_bytes, "TenMoi_001", "prefix")
```

---

## Ví dụ: Template mau_06td.docx

### Context mẫu
```python
context = {
    "ten_cn": "Chi nhánh NHCSXH tỉnh Đồng Nai",
    "ten_pgd": "PGD Long Thành",
    "ten_xa": "Xã Bình An",
    "ngay_kt": "06/05/2026",
    "thanh_vien_doan": [
        {"ho_ten": "Nguyễn Văn A", "chuc_vu": "Tổ trưởng KHNV"},
        {"ho_ten": "Trần Thị B", "chuc_vu": "CBTD"},
    ],
    "ds_kh": [
        {
            "stt": 1,
            "ten_kh": "Lê Văn C",
            "so_ku": "12345",
            "ten_ct": "NƠXH 2026",
            "muc_vay": 50000000,
            "muc_dieu_chinh": 0,
            "von_vay": 50000000,
            "von_da_giai_ngan": 50000000,
            "von_da_thu_hoi": 10000000,
            "von_con_no": 40000000,
        }
    ],
    "tong_von_vay": 50000000,
    "tong_von_da_giai_ngan": 50000000,
    "tong_von_con_no": 40000000,
}
```

---

## Dependencies

Template service sử dụng:
- `docxtpl`: Render template Word
- `docx2pdf`: Convert Word → PDF (yêu cầu MS Word trên Windows)

Cài đặt:
```bash
pip install docxtpl docx2pdf
```

**Lưu ý:** `docx2pdf` chỉ hoạt động trên Windows với MS Word đã cài đặt.
Trên Linux/Mac, chỉ tải được Word (PDF sẽ ẩn nút download).
