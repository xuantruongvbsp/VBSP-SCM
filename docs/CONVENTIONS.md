# Conventions — VBSP-SCM
> Quy ước bắt buộc khi phát triển. Cursor/Windsurf đọc file này trước khi sinh code.
> Cập nhật lần cuối: 06/05/2026

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

### Chuẩn đặt tên key

| Pattern | Dùng cho |
|---|---|
| `khtd_cn` | Kế hoạch tín dụng cấp Chi nhánh |
| `khtd_pgd_{slug}` | Kế hoạch tín dụng cấp PGD |
| `ct_registry_{slug}` | Danh mục chương trình theo PGD |
| `merge_meta_{loai}` | Metadata merge (hstd / nq11 / gqvl) |
| `ds_pgd` | Danh sách PGD (config động) |
| `ma_pgd_map` | Mapping mã PGD ↔ tên PGD |
| `pgd_xa_map` | Mapping PGD → danh sách xã |
| `chuong_trinh_khtd` | Danh mục chương trình KHTD |
| `kh_gqvl_cn_{nam}` | KH GQVL Chi nhánh theo năm |
| `kh_gqvl_pgd_{slug}_{nam}` | KH GQVL theo PGD (dự phòng) |

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
| `luu_khtd_cn` | Lưu kế hoạch tín dụng Chi nhánh |
| `luu_khtd_pgd` | Lưu kế hoạch tín dụng PGD |
| `upload_hstd` | Upload file HSTD |
| `upload_nq11` | Upload file NQ11 |
| `upload_gqvl` | Upload file GQVL |
| `upload_dienbao` | Upload file Điện báo |
| `merge_hstd` | Merge dữ liệu HSTD toàn CN |
| `update_config` | Cập nhật cấu hình (ds_pgd, ma_pgd_map...) |
| `cap_nhat_ds_pgd` | Cập nhật danh sách PGD |

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

---

## 4. Cache — xóa sau khi lưu thành công

```python
# Bắt buộc gọi sau khi luu_file_he_thong() hoặc luu_pgd_file() thành công
st.cache_data.clear()
```

Parquet cache: `cache/hstd.parquet`, `cache/nq11.parquet`, `cache/gqvl.parquet`

---

## 5. Tiền tệ — quy ước 3 lớp

| Lớp | Đơn vị | Ghi chú |
|---|---|---|
| Nhập liệu (form) | **Triệu đồng** | `number_input` format `"%.0f"` |
| Lưu trữ (kv_store / DB) | **VND** (đồng) | Nhân × 1.000.000 trước khi lưu |
| Hiển thị | Dùng `fmt*()` | Xem bảng hàm bên dưới |

```python
from utils import fmt, fmt_tien, fmt_ty, fmt_pct, fmt_so

fmt_ty(value)     # / 1e12 → tỷ đồng
fmt_tien(value)   # VND đầy đủ
fmt_pct(value)    # %
fmt_so(value)     # số nguyên có dấu phân cách
```

> ⚠️ **Bug thường gặp:** metric tỷ đồng phải chia `/1e12` — không phải `/1e9`.

---

## 6. Phân quyền — luôn kiểm tra role

```python
role     = st.session_state["user_info"]["role"]    # executive | admin | manager | user
pgd_user = st.session_state["user_info"].get("pgd") # None nếu không phải user PGD
username = st.session_state.get("username", "unknown")
```

| Role | Quyền |
|---|---|
| `executive` | Chỉ đọc, dashboard vĩ mô |
| `admin` | = `admin_cn` (tương thích ngược) |
| `manager` | = `manager_cn` (tương thích ngược) |
| `user` | = `user_pgd` (tương thích ngược) |
| `admin_cn` | Quản trị Chi nhánh — toàn quyền CN |
| `manager_cn` | Lãnh đạo CN — upload CN, giao chỉ tiêu |
| `admin_pgd` | Quản trị PGD — upload + quản lý user PGD |
| `manager_pgd` | Lãnh đạo PGD — upload, nhập kế hoạch |
| `user_pgd` | CBTD PGD — tác nghiệp, chỉ thấy PGD mình |

**User chỉ thấy dữ liệu PGD của mình:**
```python
# Dùng hàm từ auth.py để check phân hệ
from auth import la_phan_he_pgd

if la_phan_he_pgd(role) and pgd_user:
    df = df[df[COT_TEN_PGD] == pgd_user]
```

**Check quyền upload PGD:**
```python
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

if co_quyen_upload_pgd(role):
    # Hiện form upload
    pass

if co_quyen_quan_ly_user_pgd(role):
    # Hiện panel quản lý user
    pass
```

---

## 7. CSS & UI

- Inject CSS **một lần** trong `app.py` — không inject rải rác trong tab
- Bảng ≥ 8 cột → HTML thuần + `st.markdown(unsafe_allow_html=True)`
- Màu sắc → xem `UI_GUIDELINES.md`
- Không hardcode màu hex trong tab

---

## 8. Template Word — docxtpl

### Thư mục
Template đặt trong `templates/` — file `.docx` mẫu chuẩn NHCSXH.

### Cú pháp placeholder
| Loại | Cú pháp | Ví dụ |
|---|---|---|
| Biến đơn | `{{ten_truong}}` | `{{ten_kh}}`, `{{so_ku}}` |
| Vòng lặp bảng | `{%tr for item in ds %}...{%tr endfor %}` | Lặp qua danh sách KH |
| Điều kiện | `{% if condition %}...{% endif %}` | Hiện/ẩn section |

### Quy ước đặt tên template constant
```python
# Trong services/template_service.py
TMPL_MAU06    = "mau_06td.docx"    # Phiếu KT sử dụng vốn
TMPL_MAU06A   = "mau_06atd.docx"   # Phiếu KT mở rộng
TMPL_MAU15    = "mau_15td.docx"   # DS đối chiếu số dư
TMPL_MAU16    = "mau_16td.docx"   # BB kiểm tra Tổ TK&VV
TMPL_KH_KT    = "ke_hoach_kt.docx" # KH kiểm tra GS ủy thác
TMPL_BB_XMN   = "bb_xac_minh_no.docx"  # BB xác minh nợ chiếm dụng
```

### Sử dụng
```python
from services.template_service import dien_template, nut_tai_word_va_pdf, TMPL_MAU06

context = {"ten_kh": "Nguyễn Văn A", "so_ku": "12345"}
docx_bytes = dien_template(TMPL_MAU06, context)
nut_tai_word_va_pdf(docx_bytes, "Mau06_001", "prefix")
```

---

## 9. Hằng số tên đơn vị

| Constant | Giá trị | Dùng để |
|---|---|---|
| `DON_VI_CHI_NHANH` | `"Hội sở Chi nhánh tỉnh"` | Key nội bộ để lọc DataFrame (khớp cột Tên PGD trong HSTD) |
| `TEN_CHI_NHANH_HIEN_THI` | `"Chi nhánh NHCSXH tỉnh Đồng Nai"` | Nhãn hiển thị trên UI |

**⚠️ KHÔNG hardcode** `"PGD Biên Hòa"` để lọc df — dùng `DON_VI_CHI_NHANH`.

---

## 10. File QĐ UBND

Lưu có phiên bản — không ghi đè. Dùng hàm trong `data/khtd.py`.

---

## 11. Không thêm dependency mới

Kiểm tra `utils.py`, `data/`, `services/` trước. Không dùng `streamlit-aggrid` hay thư viện UI nặng.

---

## 12. Mẫu prompt Cursor

```
[Mô tả task 1-2 câu]

File cần sửa:
- [path]: [sửa gì]

Yêu cầu:
- db.doc_kv() / db.ghi_kv() để lưu
- db.ghi_audit() sau khi ghi
- st.cache_data.clear() sau thành công
- Upload qua upload_service.py
- Tiền: nhập triệu, lưu VND, hiển thị fmt()

Tái sử dụng:
- [hàm]: [mục đích]
```

---

## 13. Checklist trước khi commit

- [ ] Dùng `db.doc_kv()` / `db.ghi_kv()` — không dùng JSON file
- [ ] Gọi `db.ghi_audit()` sau mọi thao tác ghi
- [ ] Gọi `st.cache_data.clear()` sau upload thành công
- [ ] Upload đi qua `upload_service.py`
- [ ] Tiền tệ: nhập triệu → lưu VND → hiển thị `fmt*()`
- [ ] Metric tỷ đồng chia `/1e12` (không `/1e9`)
- [ ] Kiểm tra role trước khi cho phép ghi (dùng `la_phan_he_cn()`, `la_phan_he_pgd()`)
- [ ] Không hardcode đường dẫn file
- [ ] Dùng `DON_VI_CHI_NHANH` để lọc df (không dùng `"PGD Biên Hòa"`)
- [ ] Đặt template constant `TMPL_*` trong `template_service.py`
