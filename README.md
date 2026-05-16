# VBSP-SCM

Hệ thống Quản trị & Tác nghiệp Tín dụng Nội bộ — NHCSXH Chi nhánh tỉnh Đồng Nai.

## Yêu cầu hệ thống

- **Python** 3.10 trở lên
- **Windows** (hỗ trợ font Times New Roman cho PDF)

## 1. Cài đặt môi trường

```bash
# Kiểm tra phiên bản Python
python --version

# Tạo môi trường ảo (khuyến nghị)
python -m venv .venv

# Kích hoạt môi trường ảo (Windows)
.venv\Scripts\activate
```

## 2. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

**Thư viện PDF** (cài riêh nếu cần xuất PDF):

```bash
pip install reportlab kaleido
```

## 3. Font chữ tiếng Việt cho PDF

Để xuất PDF hỗ trợ tiếng Việt, cần file font Times New Roman.

**Cách 1 (tự động):** Hệ thống tự tìm trong `C:/Windows/Fonts/times.ttf`

**Cách 2 (thủ công):**
```bash
mkdir assets
copy C:\Windows\Fonts\times.ttf assets\
copy C:\Windows\Fonts\timesbd.ttf assets\
```

## 4. Chạy ứng dụng

```bash
streamlit run app.py
```

Truy cập: **http://localhost:8501**

## 5. Cấu trúc dự án

```
VBSP-SCM/
├── app.py                  # Điểm vào: routing, session, load dữ liệu
├── config.py               # Hằng số toàn hệ thống
├── auth.py                 # Đăng nhập, phân quyền
├── db.py                   # SQLite
├── utils.py                # Hàm tiện ích
│
├── pdf_service.py          # Xuất PDF (reportlab), KPI Cards, biểu đồ
├── services/               # Nghiệp vụ
│   ├── excel_service.py    # Xuất Excel chuyên nghiệp (3 sheet)
│   ├── hhi_service.py      # Phân tích HHI
│   ├── du_phong_service.py # Dự phóng dòng tiền
│   └── migration_service.py# Ma trận chuyển dịch nhóm nợ
│
├── workspaces/             # 3 không gian làm việc
│   ├── ws_executive.py     # Ban Giám đốc (dashboard vĩ mô)
│   ├── ws_management.py    # Phòng KH-NV (điều hành)
│   └── ws_operation.py     # PGD (tác nghiệp)
│
├── data/                   # Lớp đọc dữ liệu
├── tabs/                   # Components giao diện
├── assets/                 # Font, logo
├── cache/                  # Parquet cache
└── pgd_data/               # Dữ liệu upload từng PGD
```

## 6. Phân quyền

| Role | Mô tả | Workspace |
|------|-------|-----------|
| `executive` | Ban Giám đốc | `ws_executive` |
| `admin_cn` / `manager_cn` | Phòng KH-NV | `ws_management` |
| `admin_pgd` / `user_pgd` | PGD | `ws_operation` |

## 7. Xử lý sự cố

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| `ModuleNotFoundError: reportlab` | Chưa cài reportlab | `pip install reportlab` |
| `ModuleNotFoundError: kaleido` | Chưa cài kaleido | `pip install kaleido` |
| PDF lỗi font, không dấu | Thiếu times.ttf | Copy font vào `assets/` |
| Không có dữ liệu | Chưa upload HSTD | Upload qua tab Quản trị |
