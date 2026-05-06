# Conventions — VBSP-SCM
> Quy ước bắt buộc khi phát triển. Cursor/Windsurf đọc file này trước khi sinh code.
> Cập nhật lần cuối: 05/2026

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
| `admin` | Toàn quyền |
| `manager` | Upload, nhập kế hoạch, giao nhiệm vụ |
| `user` | Tác nghiệp, chỉ thấy PGD được phân công |

**User chỉ thấy dữ liệu PGD của mình:**
```python
if role == "user" and pgd_user:
    df = df[df[COT_TEN_PGD] == pgd_user]
```

---

## 7. CSS & UI

- Inject CSS **một lần** trong `app.py` — không inject rải rác trong tab
- Bảng ≥ 8 cột → HTML thuần + `st.markdown(unsafe_allow_html=True)`
- Màu sắc → xem `UI_GUIDELINES.md`
- Không hardcode màu hex trong tab

---

## 8. File QĐ UBND

Lưu có phiên bản — không ghi đè. Dùng hàm trong `data/khtd.py`.

---

## 9. Không thêm dependency mới

Kiểm tra `utils.py`, `data/`, `services/` trước. Không dùng `streamlit-aggrid` hay thư viện UI nặng.

---

## 10. Mẫu prompt Cursor

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

## 11. Checklist trước khi commit

- [ ] Dùng `db.doc_kv()` / `db.ghi_kv()` — không dùng JSON file
- [ ] Gọi `db.ghi_audit()` sau mọi thao tác ghi
- [ ] Gọi `st.cache_data.clear()` sau upload thành công
- [ ] Upload đi qua `upload_service.py`
- [ ] Tiền tệ: nhập triệu → lưu VND → hiển thị `fmt*()`
- [ ] Metric tỷ đồng chia `/1e12` (không `/1e9`)
- [ ] Kiểm tra role trước khi cho phép ghi
- [ ] Không hardcode đường dẫn file
