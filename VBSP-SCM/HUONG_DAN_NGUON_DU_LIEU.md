# Hướng dẫn Nguồn Dữ liệu — VBSP-SCM
> Cập nhật lần cuối: 05/2026

---

## 1. Tổng quan luồng dữ liệu

```
PGD upload file riêng
        │
        ▼
pgd_data/{slug}/          ← ws_operation đọc trực tiếp
        │
        ▼ merge_du_lieu_toan_cn()
        │
KH-NV upload file hệ thống ──► CACHE_HSTD / CACHE_NQ11 / CACHE_GQVL
                                        │
                                        ▼
                               ws_management / ws_executive đọc
```

---

## 2. Ba loại nguồn dữ liệu

### 2a. File hệ thống (Phòng KH-NV upload)
| File | Cache | Hàm đọc |
|---|---|---|
| HSTD tổng hợp 22 PGD | `CACHE_HSTD` | `core.doc_file()` |
| NQ11 tổng hợp | `CACHE_NQ11` | `core.doc_file()` |
| GQVL tổng hợp | `CACHE_GQVL` | `core.doc_file()` |
| Điện báo | `kv_store["dienbao_*"]` | `db.doc_kv()` |

### 2b. File riêng PGD (PGD tự upload)
```
pgd_data/
  pgd_long_thanh/
    hstd_latest.parquet
    nq11_latest.parquet
    gqvl_latest.parquet
  pgd_bien_hoa/
    ...
```
Đọc qua: `pgd.doc_hstd_pgd(ten_pgd, ts)`

### 2c. Kế hoạch & Nhiệm vụ (kv_store)
| Key | Nội dung |
|---|---|
| `khtd_cn` | Kế hoạch tín dụng Chi nhánh (VND) |
| `khtd_xa` | Kế hoạch phân bổ theo xã (VND) |
| `khtd_pgd_{slug}` | Kế hoạch PGD (VND) |
| `ct_registry_{slug}` | Danh mục chương trình theo PGD |
| `merge_meta_{loai}` | Metadata lần merge cuối (timestamp, số dòng) |
| `dienbao_{nam}_{thang}` | Điện báo tháng |

---

## 3. Quy tắc đọc dữ liệu theo Workspace

### ws_management / ws_executive
```python
# Đọc từ CACHE (22 PGD đã merge)
from config import CACHE_HSTD
df = core.doc_file(CACHE_HSTD)

# KHÔNG đọc file riêng PGD trong ws_management
```

### ws_operation (PGD)
```python
# Đọc file riêng PGD — lấy từ kwargs
df      = kwargs.get("df")        # HSTD của PGD này
df_nq11 = kwargs.get("df_nq11")

# KHÔNG import CACHE_HSTD trong tab ws_operation
```

---

## 4. Quy trình Upload & Merge

### Phòng KH-NV upload file hệ thống
```
1. tab_upload_khnv.py → upload_service.luu_file_he_thong()
2. Tự động gọi merge_du_lieu_toan_cn("hstd"|"nq11"|"gqvl")
3. st.cache_data.clear()
4. ws_management tự load CACHE mới khi reload
```

### PGD upload file riêng
```
1. tab_upload_pgd.py → upload_service.luu_pgd_file()
2. KHÔNG merge — chỉ lưu vào pgd_data/{slug}/
3. st.cache_data.clear()
4. ws_operation tự load file PGD khi reload
```

---

## 5. Cột dữ liệu quan trọng (HSTD)

| Hằng số config | Tên cột thực | Dùng cho |
|---|---|---|
| `COT_MA_CHUONG_TRINH` | `"Mã CT"` | Lọc chương trình tín dụng |
| `COT_NGUON_VON` | `"Nguồn vốn"` | Phân biệt TW (1) / ĐP (2) |
| `COT_TONG_DU_NO` | `"Tổng dư nợ"` | Thực hiện chính |
| `COT_DU_NO_TH` | `"Dư nợ trong hạn"` | Fallback nếu thiếu Tổng dư nợ |
| `COT_TEN_PGD` | `"Tên PGD"` | Lọc theo đơn vị |
| `COT_TEN_XA` | `"Tên xã"` | Lọc / tổng hợp theo xã |
| `COT_TEN_CT` | `"Tên chương trình"` | Hiển thị |

---

## 6. Thứ tự ưu tiên đọc cột TH (Thực hiện)

```python
col_th = (
    COT_TONG_DU_NO if COT_TONG_DU_NO in df.columns
    else COT_DU_NO_TH if COT_DU_NO_TH in df.columns
    else None
)
if col_th is None:
    return {}  # không có dữ liệu TH
```

---

## 7. Điện báo

### Cấu trúc file
- File Excel: `DienBao_2025_3112.xlsx`, `Dienbao_2026.xlsx`
- Cột quan trọng: Mã PGD, Tên PGD, Dư nợ, DS Cho vay, DS Thu nợ, NQH, Khoanh, Lãi tồn

### Đọc điện báo
```python
from khtd import doc_dienbao
df_db = doc_dienbao(nam, thang)
```

---

## 8. Kiểm tra trạng thái nguồn dữ liệu

Xem widget **Nguồn dữ liệu** ở sidebar — hiển thị:
- Thời gian upload cuối
- Số dòng dữ liệu
- Cảnh báo nếu dữ liệu cũ hơn ngưỡng `UPLOAD_CANH_BAO_NGAY`

```python
from data_source_status import render_trang_thai_nguon
render_trang_thai_nguon()  # inject vào sidebar
```

---

## 9. Các lỗi thường gặp

| Lỗi | Nguyên nhân | Xử lý |
|---|---|---|
| TH = 0 toàn bộ | Chưa upload HSTD hoặc file sai cột | Kiểm tra cột `COT_TONG_DU_NO` trong file |
| KH = 0 toàn bộ | Chưa nhập kế hoạch | Vào tab KHTD Chi nhánh nhập |
| Merge không chạy | File PGD lỗi format | Xem log lỗi trong tab Upload |
| Cache cũ | Quên `st.cache_data.clear()` | Gọi sau mọi thao tác ghi |
| Xã không khớp | Tên xã trong HSTD khác `PGD_XA_MAP` | Kiểm tra `config.PGD_XA_MAP` |
| Metric tỷ sai | Chia 1e9 thay vì 1e12 | Sửa thành `/ 1_000_000_000_000` |
