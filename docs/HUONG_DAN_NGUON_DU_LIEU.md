# Hướng dẫn Nguồn Dữ liệu — VBSP-SCM
> Mô tả chi tiết các loại file dữ liệu, quy trình upload, cache và baseline.
> Cập nhật lần cuối: 08/05/2026

---

## Các loại file dữ liệu

| Loại | Tên file | Mô tả | Upload bởi |
|---|---|---|---|
| **HSTDCT** | `HSTD_Du_lieu_tho.XLSX` | Hồ sơ tín dụng chi tiết — dư nợ, khách hàng, chương trình | admin/manager (KH-NV) |
| **NQ11** | `SAO_KE_CT__NQ11_du_lieu_tho.XLSX` | Sao kê Nghị quyết 11 — giải ngân theo chương trình | admin/manager (KH-NV) |
| **GQVL** | `SK_GQVL_du_lieu_tho.xlsx` | Giải quyết vốn lưu động — sao kê chi tiết | admin/manager (KH-NV) |
| **Điện báo hiện tại** | `Dienbao_ht.xlsx` | Số liệu cân đối nguồn vốn kỳ hiện tại | admin |
| **Điện báo kỳ trước** | `Dienbao_prev.xlsx` | Số liệu cân đối kỳ trước — so sánh tăng/giảm | admin |
| **CDTOTKVV** | `CDTOTKVV_{thang}.xlsx` | Chấm điểm Tổ TK&VV theo tháng | admin_pgd / manager_pgd |

### Hằng số cấu hình (config.py)

```python
TEN_FILE      = "HSTD_Du_lieu_tho.XLSX"        # Đường dẫn: data/HSTD_Du_lieu_tho.XLSX
TEN_FILE_NQ11 = "SAO_KE_CT__NQ11_du_lieu_tho.XLSX"
TEN_FILE_DB   = "Dienbao_ht.xlsx"               # Cache: cache/dienbao_ht.xlsx
TEN_FILE_DB_PREV = "Dienbao_prev.xlsx"          # Cache: cache/dienbao_prev.xlsx
```

---

## Quy trình upload

### Luồng 1 — Upload tập trung (Phòng KH-NV)

```
Tab Upload KH-NV (tab_upload_khnv)
  → luu_file_he_thong(file, loai, username)
    → Kiểm tra ext (.xlsx/.xls) + kích thước (≥ 1KB)
    → Kiểm tra chất lượng (data_quality.py)
    → Lưu file gốc vào data/
    → merge_du_lieu_toan_cn(loai)
      → Đọc file từng PGD: pgd_data/{slug}/{loai}_latest.xlsx
      → ThreadPoolExecutor (max_workers=8) đọc song song
      -> excel_to_parquet() — cache Parquet
      → Ghi parquet tổng: cache/hstd.parquet / cache/nq11.parquet
  → st.cache_data.clear()
  → Ghi audit_log
```

### Luồng 2 — Upload phân tán (PGD địa bàn)

```
Tab Upload PGD (tab_upload_pgd)
  → luu_pgd_file(ten_pgd, loai, file, username)
    → Kiểm tra ext + kích thước
    → Kiểm tra chất lượng
    → Lưu file: pgd_data/{slug}/{loai}_latest.xlsx
    → Gọi merge_du_lieu_toan_cn() — cập nhật cache toàn CN
  → st.cache_data.clear()
  → Ghi audit_log
```

### Luồng 3 — Upload Điện báo

```
Tab Cân đối (tab_candoi)
  → luu_dienbao(file_ht, file_prev, username)
    → Lưu: cache/dienbao_ht.xlsx và cache/dienbao_prev.xlsx
    → Không gọi merge (điện báo độc lập, không gộp PGD)
```

---

## Cache & Parquet

Hệ thống sử dụng **2 lớp cache** để tối ưu tốc độ đọc:

### Lớp 1 — Parquet cache (data/core.py)

```python
def excel_to_parquet(excel_path, parquet_path, sheet, header, post_fn=None):
    # Chỉ chuyển đổi khi file Excel mới hơn cache
    if ts_file(parquet_path) < ts_file(excel_path):
        df = pd.read_excel(excel_path, ...)  # PyArrow backend
        df.to_parquet(parquet_path, compression='zstd')
    return pd.read_parquet(parquet_path)
```

### Lớp 2 — Streamlit cache (app.py)

```python
@st.cache_data(show_spinner=False, ttl=3600)  # Tự xóa sau 1 giờ
def _load_hstd(cache_path: str, _ts: float) -> pd.DataFrame:
    return duckdb.query(f"SELECT * FROM '{cache_path}'").df()
```

### Xóa cache

Sau mọi thao tác upload thành công, bắt buộc gọi:

```python
st.cache_data.clear()
```

### Vị trí cache

| File dữ liệu | Cache Parquet |
|---|---|
| `data/HSTD_Du_lieu_tho.XLSX` | `cache/hstd.parquet` |
| `data/SAO_KE_CT__NQ11_du_lieu_tho.XLSX` | `cache/nq11.parquet` |
| `data/SK_GQVL_du_lieu_tho.xlsx` | `cache/gqvl.parquet` |
| `data/baseline/HSTD_3112_{nam}.XLSX` | `cache/hstd_baseline_{nam}.parquet` |

---

## Baseline 31/12

Hệ thống hỗ trợ lưu trữ **dữ liệu mốc 31/12** hàng năm để so sánh tăng/giảm.

### Vị trí lưu trữ

```
data/baseline/HSTD_3112_{nam}.XLSX            # File tổng toàn CN
data/baseline_pgd/{slug}/HSTD_3112_{nam}.XLSX # File riêng từng PGD
```

### Hàm tiện ích

```python
from config import baseline_path, baseline_cache, danh_sach_nam_baseline

# Đường dẫn file baseline theo năm
path = baseline_path(2025)      # → "data/baseline/HSTD_3112_2025.XLSX"

# Cache parquet tương ứng
cache = baseline_cache(2025)    # → "cache/hstd_baseline_2025.parquet"

# Danh sách năm đã có baseline
years = danh_sach_nam_baseline()  # → [2026, 2025, ...] giảm dần
```

### Đọc dữ liệu baseline

```python
from data.hstd import doc_baseline, doc_baseline_merged

# Baseline của một đơn vị
df = doc_baseline(2025)

# Baseline đã merge tất cả đơn vị
df_merged = doc_baseline_merged(2025)
```

### Upload baseline PGD

```python
from config import baseline_pgd_path

# Lưu file baseline cho PGD
path = baseline_pgd_path("PGD Long Thành", 2025)
# → "data/baseline_pgd/pgd_long_thanh/HSTD_3112_2025.XLSX"
```

### Kiểm tra trạng thái baseline

```python
from config import trang_thai_baseline_pgd

# Xem PGD nào đã upload baseline cho năm 2025
status = trang_thai_baseline_pgd(2025)
# → {"Hội sở Chi nhánh tỉnh": True, "PGD Long Thành": False, ...}
```
