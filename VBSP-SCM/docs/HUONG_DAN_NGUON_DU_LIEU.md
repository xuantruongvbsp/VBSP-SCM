# Hướng dẫn Nguồn Dữ liệu — VBSP-SCM
> Cập nhật lần cuối: 05/2026

---

## 1. Tổng quan các nguồn

Hệ thống đọc dữ liệu từ **4 nguồn chính**, mỗi nguồn có luồng upload riêng:

| Nguồn | Loại file | Upload tại | Dùng bởi |
|---|---|---|---|
| **HSTD** — Hồ sơ tín dụng | `.xlsx` | Tab Upload KH-NV hoặc Upload PGD | Toàn hệ thống |
| **NQ11** — Nghị quyết 11 | `.xlsx` | Tab Upload KH-NV hoặc Upload PGD | Tab NQ11, báo cáo |
| **GQVL** — Giải quyết việc làm | `.xlsx` | Tab Upload KH-NV hoặc Upload PGD | Tab GQVL, báo cáo |
| **Điện báo** — Cân đối nguồn vốn | `.xlsx` | Tab Điện Báo (Cân đối) | Tab Cân đối, KH vs TH |

---

## 2. Hai luồng upload

### Luồng 1 — Phòng KH-NV (tập trung)

**Tab:** `📤 Upload KH-NV`  
**Role được phép:** `admin`, `manager`  
**Hàm:** `luu_file_he_thong()`

- Upload file toàn Chi nhánh (gộp tất cả 22 đơn vị)
- Sau khi upload → tự động gọi `merge_du_lieu_toan_cn()` → cập nhật parquet cache
- Dùng bởi workspace **Phòng KH-NV** và **BGĐ**

```
File upload → cache/hstd.parquet
           → cache/nq11.parquet
           → cache/gqvl.parquet
```

### Luồng 2 — PGD địa bàn (phân tán)

**Tab:** `📤 Upload PGD`  
**Role được phép:** `user` (chỉ PGD của mình), `admin`  
**Hàm:** `luu_pgd_file()`

- Mỗi PGD upload file riêng của đơn vị mình
- Lưu vào `pgd_data/{slug}/hstd_latest.xlsx`
- Dùng bởi workspace **Hỗ trợ Địa bàn PGD**

```
File upload → pgd_data/pgd_long_thanh/hstd_latest.xlsx
           → pgd_data/pgd_long_thanh/nq11_latest.xlsx
           → pgd_data/pgd_long_thanh/gqvl_latest.xlsx
```

---

## 3. Nguồn HSTD

### Cấu trúc cột bắt buộc

Hệ thống đọc theo tên cột — **tên phải khớp** với `config.py`:

| Hằng số config | Tên cột trong file |
|---|---|
| `COT_TEN_PGD` | Tên PGD |
| `COT_TEN_KH` | Tên khách hàng |
| `COT_MA_KH` | Mã khách hàng |
| `COT_TONG_DU_NO` | Tổng dư nợ |
| `COT_DU_NO_TH` | Dư nợ trong hạn |
| `COT_DU_NO_QH` | Dư nợ quá hạn |
| `COT_TEN_CT` | Tên chương trình |
| `COT_NGAY_VAY` | Ngày vay |
| `COT_THOI_HAN` | Thời hạn |

### Kiểm tra khi merge thất bại

```python
# Xem log
SELECT * FROM audit_log WHERE action LIKE '%merge%' ORDER BY created_at DESC LIMIT 10

# Kiểm tra tên xã
from config import PGD_XA_MAP
print(PGD_XA_MAP["PGD Long Thành"])
# So sánh với cột "Tên xã" trong file HSTD
```

---

## 4. Nguồn Điện báo

### Cấu trúc file

Hệ thống đọc theo từng dòng — **không dùng header chuẩn pandas**:

| Cột | Nội dung |
|---|---|
| **Cột B** (cột thứ 2) | Tên chỉ tiêu (text) |
| **Cột C** (cột thứ 3) | Giá trị số (float) |

Hai file cần upload:
- **File hiện tại** — số liệu tại thời điểm báo cáo
- **File 31/12 năm trước** — mốc so sánh đầu năm

> Hai file phải **cùng cấu trúc** (cùng tên chỉ tiêu ở cột B, cùng đơn vị số ở cột C).

### Upload Điện báo

1. Đăng nhập role `admin` hoặc `manager`
2. Vào workspace **Phòng KH-NV** → tab **📡 Điện Báo**
3. Kéo đến mục **📤 Upload file Điện báo**
4. Upload file hiện tại và/hoặc file 31/12

Chi tiết → xem `HUONG_DAN_DIEN_BAO.md`.

---

## 5. Ưu tiên nguồn dữ liệu

Khi cả hai luồng đều có dữ liệu, hệ thống ưu tiên theo `data_priority_service.py`:

```
Luồng KH-NV (tập trung) > Luồng PGD (địa bàn)
```

Trạng thái nguồn hiển thị trong **sidebar** (widget `data_source_status.py`).

---

## 6. Kiểm tra trạng thái dữ liệu

### Xem merge metadata

```python
meta = db.doc_kv("merge_meta_hstd")
# {'ts': '2026-05-04T10:30:00', 'so_don_vi': 22, 'tong_ban_ghi': 45123}
```

### Xem trạng thái file PGD

```python
from data.pgd import doc_trang_thai_file
trang_thai = doc_trang_thai_file("PGD Long Thành", "hstd")
# {'co_file': True, 'ngay': '04/05/2026'}
```

### Tab trạng thái nguồn

Vào tab **🔌 Trạng thái Nguồn** (trong workspace Management) để xem tổng quan tất cả 22 đơn vị.

---

## 7. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| TH = 0 toàn bộ | Chưa upload HSTD hoặc chưa merge | Upload lại → kiểm tra audit log |
| Số liệu xã bị lệch | Tên xã trong file khác `PGD_XA_MAP` | Chuẩn hóa tên xã trong file Excel |
| `th_cn` lệch ~8 tỷ | Thiếu 4 key ĐP trong config | Kiểm tra `9_DP`, `12_DP`, `17_DP`, `26_DP` |
| Merge lỗi 1 PGD | File PGD bị lỗi format | Upload lại file PGD đó |
| Dữ liệu không cập nhật sau upload | Cache cũ | `st.cache_data.clear()` |

Chi tiết xử lý → xem `TROUBLESHOOTING.md`.
