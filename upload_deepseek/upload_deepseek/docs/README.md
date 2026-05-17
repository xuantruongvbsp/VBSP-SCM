# VBSP-SCM — Hệ thống Quản trị Tín dụng Nội bộ

Hệ thống nội bộ cho **Ngân hàng Chính sách Xã hội Chi nhánh Đồng Nai** .

- **Stack:** Streamlit + Python + SQLite
- **Người dùng:** ~20 users, 4 vai trò
- **Phạm vi:** 22 đơn vị (Hội sở + 21 PGD), 95 xã/phường

---

## Cài đặt & Chạy

```bash
# 1. Cài dependencies
pip install -r requirements.txt

# 2. Chạy app
streamlit run app.py
```

Mở trình duyệt: `http://localhost:8501`

---

## Cấu trúc thư mục

```
VBSP-SCM/
├── app.py                  # Điểm vào: routing, session, load df
├── auth.py                 # Đăng nhập, RBAC, quản lý user
├── config.py               # Hằng số toàn hệ thống (DS_PGD, cột, chương trình...)
├── db.py                   # SQLite: kv_store, users, audit_log
├── utils.py                # fmt(), Excel helpers, tự động điền Word
│
├── data/                   # Lớp đọc dữ liệu
│   ├── core.py             # Parquet cache, ts_file()
│   ├── hstd.py             # Đọc HSTD, cảnh báo 3 tháng KHĐ
│   ├── pgd.py              # Đọc/lưu pgd_data/{slug}/
│   ├── khtd.py             # KHTD, CBTD, QĐ UBND
│   └── ct_discovery.py     # Quét → ct_registry chương trình theo PGD
│
├── services/               # Lớp nghiệp vụ
│   ├── upload_service.py   # Upload tập trung (KetQuaUpload)
│   ├── report_service.py   # Tạo báo cáo Excel
│   ├── khtd_service.py     # Giao & Điều chỉnh KHTD
│   └── kiem_soat_service.py# Kiểm soát Chi nhánh
│
├── tabs/                   # Giao diện — mỗi file = 1 tab
├── workspaces/             # ws_executive, ws_management, ws_operation
│
├── cache/                  # Parquet cache (không commit)
└── pgd_data/               # File upload từng PGD (không commit)
```

Chi tiết đầy đủ → xem `ARCHITECTURE.md`.

---

## Vai trò & Quyền hạn

| Vai trò | Quyền |
|---|---|
| `executive` | Chỉ đọc, dashboard BGĐ |
| `admin` | Toàn quyền |
| `manager` | Upload, nhập kế hoạch, giao nhiệm vụ |
| `user` | Tác nghiệp, chỉ thấy PGD được phân công |

---

## Tài liệu nội bộ

| File | Nội dung |
|---|---|
| `ARCHITECTURE.md` | Sơ đồ module, luồng dữ liệu, quan hệ import |
| `CONVENTIONS.md` | Quy ước code: kv_store, audit, tiền tệ, upload |
| `UI_GUIDELINES.md` | Bảng màu, typography, CSS chuẩn |
| `CHANGELOG.md` | Lịch sử thay đổi theo sprint |
| `ROADMAP.md` | Sprint hiện tại + backlog |
| `TROUBLESHOOTING.md` | Xử lý lỗi thường gặp |
| `HUONG_DAN_DIEN_BAO.md` | Hướng dẫn upload Điện báo |
| `HUONG_DAN_NGUON_DU_LIEU.md` | Tổng quan các nguồn dữ liệu |
| `HUONG_DAN_MANG_LUOI_TO.md` | Hướng dẫn module Tổ TK&VV |

---

## Quy ước phát triển nhanh

- Lưu dữ liệu → `db.ghi_kv()` + `db.ghi_audit()`
- Upload file → qua `upload_service.py`
- Sau upload → `st.cache_data.clear()`
- Tiền tệ: nhập **triệu** → lưu **VND** → hiển thị `fmt_ty()` (chia `/1e12`)

Chi tiết → xem `CONVENTIONS.md`.
