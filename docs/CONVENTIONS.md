# CONVENTIONS — VBSP-SCM
> Quy ước bắt buộc khi phát triển. Đọc file này trước khi sinh code.
> Cập nhật lần cuối: 08/05/2026

---

## 1. Lưu trữ dữ liệu — kv_store

**Chỉ dùng `kv_store` — không dùng JSON file, không dùng session_state để persist.**

```python
# Đọc
value = db.doc_kv("key_name")           # trả về None nếu không có
values = db.doc_kv_prefix("khtd_pgd_")  # đọc nhiều key cùng prefix
values = db.doc_kv_nhieu(list_of_keys)  # đọc nhiều key cụ thể

# Ghi
db.ghi_kv("key_name", value, username)
```

### Bảng key chuẩn

| Pattern key | Mô tả |
|---|---|
| `khtd_cn` | Kế hoạch tín dụng cấp Chi nhánh |
| `khtd_pgd_{slug}` | Kế hoạch tín dụng cấp PGD |
| `khtd_xa` | Kế hoạch tín dụng phân bổ theo xã |
| `ct_registry_{slug}` | Danh mục chương trình theo PGD |
| `merge_meta_{loai}` | Metadata merge (hstd / nq11 / gqvl) |
| `ds_pgd` | Danh sách PGD (config động) |
| `ma_pgd_map` | Mapping mã PGD ↔ tên PGD |
| `pgd_xa_map` | Mapping PGD → danh sách xã |
| `chuong_trinh_khtd` | Danh mục chương trình KHTD |
| `kh_gqvl_cn_{nam}` | KH GQVL Chi nhánh theo năm |
| `kh_gqvl_pgd_{slug}_{nam}` | KH GQVL theo PGD (dự phòng) |
| `kehoach` | KH Điện báo toàn CN |
| `kehoach_pgd_{slug}` | KH Điện báo PGD |
| `dgd_map` | Điểm giao dịch toàn CN |

`slug` = `pgd_slug(ten_pgd)` từ `data/pgd.py` — ví dụ: `"pgd_long_thanh"`.

---

## 2. Audit log — bắt buộc sau mọi thao tác ghi

```python
username = st.session_state.get("username", "unknown")
db.ghi_audit(username, "ten_action", "mô tả chi tiết")
```

### Tên action chuẩn

| Action | Khi nào |
|---|---|
| `login` | Đăng nhập thành công |
| `login_failed` | Đăng nhập thất bại |
| `luu_khtd_cn` | Lưu kế hoạch tín dụng Chi nhánh |
| `luu_khtd_pgd` | Lưu kế hoạch tín dụng PGD |
| `upload_hstd` | Upload file HSTD |
| `upload_nq11` | Upload file NQ11 |
| `upload_gqvl` | Upload file GQVL |
| `upload_dienbao` | Upload file Điện báo |
| `merge_hstd` | Merge dữ liệu HSTD toàn CN |
| `update_config` | Cập nhật cấu hình (ds_pgd, ma_pgd_map...) |
| `cap_nhat_ds_pgd` | Cập nhật danh sách PGD |

Format action string: **snake_case**, mô tả ngắn gọn.

---

## 3. Upload file — luôn qua upload_service.py

**Không hardcode đường dẫn trong tab. Không ghi file trực tiếp từ tab.**

```python
from services.upload_service import (
    luu_pgd_file,        # File riêng PGD → pgd_data/{slug}/
    luu_file_he_thong,   # File toàn hệ thống → gọi merge tự động
    luu_dienbao,         # File Điện báo
    KetQuaUpload,
)

ket_qua: KetQuaUpload = luu_pgd_file(ten_pgd, loai, uploaded_file, username)
ket_qua.hien_thi()  # Hiển thị kết quả ✅ / ⚠️
```

**Sau khi upload HSTD/NQ11/GQVL:** `merge_du_lieu_toan_cn()` được gọi tự động bên trong `luu_file_he_thong()`.

### Kiểu trả về

```python
@dataclass
class KetQuaUpload:
    thanh_cong: bool
    thong_bao: str
    duong_dan: str = ""

    def hien_thi(self) -> None:
        if self.thanh_cong:
            st.success(self.thong_bao)
        else:
            st.error(self.thong_bao)
```

---

## 4. Cache — xóa sau khi lưu thành công

```python
# Bắt buộc gọi sau khi luu_file_he_thong() hoặc luu_pgd_file() thành công
st.cache_data.clear()
```

Parquet cache nằm trong `CACHE_DIR`:

| File | Cache path |
|---|---|
| `HSTD_Du_lieu_tho.XLSX` | `cache/hstd.parquet` |
| `SAO_KE_CT__NQ11_du_lieu_tho.XLSX` | `cache/nq11.parquet` |
| `SK_GQVL_du_lieu_tho.xlsx` | `cache/gqvl.parquet` |

---

## 5. Tiền tệ — quy ước 3 lớp

| Lớp | Đơn vị | Ghi chú |
|---|---|---|
| Nhập liệu (form) | **Triệu đồng** | `number_input` format `"%.0f"` |
| Lưu trữ (kv_store / DB) | **VND** (đồng) | Nhân × 1.000.000 trước khi lưu |
| Hiển thị | Dùng `fmt*()` | Xem bảng hàm bên dưới |

**KHÔNG chia 1e9** — chỉ dùng 1e6 (triệu) hoặc 1e12 (tỷ):

| Hàm | Công thức | Ví dụ |
|---|---|---|
| `fmt(x)` | Tự động chọn triệu/tỷ | `fmt(1_500_000_000)` → `"1,5 tỷ"` |
| `fmt_tien(x)` | Luôn hiển thị VND | `fmt_tien(12_000_000)` → `"12,0 triệu đồng"` |
| `fmt_ty(x)` | Chia /1e12 → tỷ | `fmt_ty(13_199_000_000_000)` → `"13.199"` |
| `fmt_pct(x)` | Nhân 100 + % | `fmt_pct(0.856)` → `"85,6%"` |
| `fmt_so(x)` | Định dạng số | `fmt_so(1234)` → `"1.234"` |
| `vn(x, n)` | Làm tròn VN | `vn(1.234, 1)` → `"1,2"` |

---

## 6. Role & quyền

Hệ thống có **9 role** chia làm 2 phân hệ, hỗ trợ tương thích ngược với 4 role cũ.

### Phân hệ Chi nhánh (CN)

| Role | Mô tả | Quyền | Tương thích |
|---|---|---|---|
| `executive` | Ban Giám đốc | Chỉ đọc dashboard vĩ mô | — |
| `admin_cn` | Quản trị CN | Toàn quyền CN (users, config, upload, merge) | `admin` |
| `manager_cn` | Lãnh đạo CN | Upload CN, giao chỉ tiêu, xem báo cáo | `manager` |

### Phân hệ PGD

| Role | Mô tả | Quyền |
|---|---|---|
| `admin_pgd` | Quản trị PGD | Upload HSTD + quản lý user PGD + giao nhiệm vụ |
| `manager_pgd` | Lãnh đạo PGD | Upload HSTD + nhập kế hoạch + xem báo cáo |
| `user_pgd` | CBTD PGD | Tác nghiệp, chỉ thấy PGD mình |

### Routing workspace

```
CN roles  (executive/admin_cn/manager_cn)  → ws_management / ws_executive
PGD roles (admin_pgd/manager_pgd/user_pgd) → ws_operation
```

### Hàm helper

```python
from auth import la_phan_he_cn, la_phan_he_pgd
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

if la_phan_he_cn(role):      # CN roles
if la_phan_he_pgd(role):     # PGD roles
if co_quyen_upload_pgd(role):  # admin_pgd, manager_pgd
```

---

## 7. Hằng số tên đơn vị

| Constant | Giá trị | Dùng để |
|---|---|---|
| `DON_VI_CHI_NHANH` | `"Hội sở Chi nhánh tỉnh"` | **Key nội bộ** — lọc df (khớp cột Tên PGD trong HSTD) |
| `TEN_CHI_NHANH_HIEN_THI` | `"Chi nhánh NHCSXH tỉnh Đồng Nai"` | **Hiển thị UI** — tên đầy đủ cho người dùng |
| `DS_PGD` | 21 PGD | Danh sách Phòng giao dịch |
| `PGD_XA_MAP` | 95 xã/phường | Mapping PGD → danh sách xã |

**⚠️ KHÔNG hardcode** `"PGD Biên Hòa"` để lọc df — luôn dùng `DON_VI_CHI_NHANH`.

---

## 8. UI Guidelines

### Màu sắc

| Mục đích | Màu | Mã |
|---|---|---|
| VBSP brand (success) | Xanh lá | `#4CAF50` / `#388E3C` |
| Cảnh báo | Vàng cam | `#FFA726` / `#F57C00` |
| Nguy hiểm | Đỏ | `#EF5350` / `#D32F2F` |
| Thông tin | Xanh dương | `#42A5F5` / `#1565C0` |
| Nền chính | Xám nhạt | `#f0f4f8` |
| Sidebar | Xanh đậm gradient | `#0a1628 → #1a3a5c` |

### 3-state upload display

| Trạng thái | Màu | Icon |
|---|---|---|
| Upload thành công + DQ pass | Xanh | ✅ |
| Upload thành công + DQ warning | Vàng | ⚠️ |
| Upload thất bại | Đỏ | ❌ |

### Quy tắc CSS

- Inject CSS **một lần** trong `app.py` — không inject trong tab
- Bảng ≥ 8 cột → HTML thuần + `st.markdown(unsafe_allow_html=True)`
- Không hardcode chuỗi tên chương trình — dùng config constants
- Tiền tệ: luôn dùng `fmt_ty()` chia `/1e12`, không `/1e9`

### Streamlit patterns

- prefix widget unique khi `pgd_mode=True` → tránh `DuplicateElementKey`
- `len(tab_names) == len(_tab_renderers)` nếu sửa `ws_*.py`
- Dùng `st.cache_data(ttl=3600)` cho dữ liệu lớn (HSTD)
