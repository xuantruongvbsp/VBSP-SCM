# CLAUDE.md — VBSP-SCM
> Hướng dẫn dự án dành riêng cho **Claude Code**.  
> Đọc toàn bộ file này trước khi đọc bất kỳ file code nào.  
> Cập nhật: 13/05/2026

---

## 1. Dự án là gì

Hệ thống Quản trị Tín dụng Nội bộ — **Ngân hàng Chính sách Xã hội Chi nhánh Đồng Nai**  
(đã sáp nhập Bình Phước 2025).

- **Stack:** Streamlit + Python + SQLite + PyArrow/Parquet
- **Chạy:** `streamlit run app.py` → `http://localhost:8501`
- **Người dùng:** ~20 users, 9 vai trò, 2 phân hệ
- **Phạm vi:** 22 đơn vị (Hội sở + 21 PGD), 95 xã/phường

---

## 2. Bản đồ file — đọc cái gì trước khi sửa cái gì

| Muốn sửa | Đọc trước | Sửa ở đây |
|---|---|---|
| Logic giao diện tab | `tabs/tab_*.py` liên quan | Tab đó |
| Merge 22 PGD | `upload_service.py` dòng 288–480 | `merge_du_lieu_toan_cn()` |
| Đọc Excel → Parquet | `data/core.py` | `excel_to_parquet()` |
| Phân quyền / role | `auth.py`, `ROLES.md` | `auth.py` |
| Hằng số cột / chương trình | `config.py` | `config.py` |
| Xuất Word / PDF | `services/template_service.py` | Template + service |
| Xuất biểu mẫu XLN | `tab_no_rui_ro.py` | Hàm `_tao_word_*xln()` |
| Workspace CN | `workspaces/ws_management.py` | File đó |
| Workspace PGD | `workspaces/ws_operation.py` | File đó |
| Upload file | `services/upload_service.py` | `luu_pgd_file()` / `luu_file_he_thong()` |
| Dữ liệu kv_store | `db.py` | `doc_kv()` / `ghi_kv()` |

---

## 3. Luồng dữ liệu — PHẢI hiểu trước khi sửa

```
Phòng KH-NV upload 22 file:
  tab_upload_khnv
    → upload_service.luu_file_he_thong()
    → merge_du_lieu_toan_cn()          # gộp 22 PGD → 1 parquet
    → cache/hstd.parquet               # CACHE_HSTD
    → dùng bởi: ws_management, ws_executive, tab_baocao, tab_tracuu...

PGD tự upload file của mình:
  tab_upload_pgd
    → upload_service.luu_pgd_file()
    → pgd_data/{slug}/hstd_latest.xlsx
    → dùng bởi: ws_operation (lọc theo pgd_user)

Context truyền vào render():
  ctx = dict(
      df=df,              # toàn CN (CN role) hoặc chỉ PGD (PGD role)
      df_full=df_full,    # luôn là toàn CN — dùng cho báo cáo
      role=role,
      pgd_user=pgd_user,  # None nếu CN role
      username=username,
      df_nq11=df_nq11,
      df_sk_gqvl=df_sk_gqvl,
      pgd_xa_map=...,
      ds_pgd_all=...,
  )
```

---

## 4. Quy tắc BẮT BUỘC — vi phạm = code sai

### 4.1 Lưu dữ liệu — CHỈ dùng kv_store

```python
# ĐỌC
value = db.doc_kv("key_name")              # None nếu không có
values = db.doc_kv_prefix("khtd_pgd_")    # nhiều key cùng prefix

# GHI — luôn kèm username
db.ghi_kv("key_name", value, username)

# KHÔNG dùng: json.dump(), open(file, 'w'), session_state để persist
```

**Key chuẩn — dùng đúng pattern:**

| Key | Dùng cho |
|---|---|
| `khtd_cn` | KHTD toàn Chi nhánh |
| `khtd_pgd_{slug}` | KHTD từng PGD |
| `ct_registry_{slug}` | Danh mục chương trình theo PGD |
| `merge_meta_{loai}` | Metadata sau merge (hstd/nq11/gqvl) |
| `no_rui_ro_{slug}_{yyyy}_{mm}` | Hồ sơ rủi ro theo PGD/kỳ |
| `kehoach` | KH Điện báo toàn CN |
| `kehoach_pgd_{slug}` | KH Điện báo từng PGD |
| `dgd_map` | Điểm giao dịch toàn CN |
| `kh_gqvl_cn_{nam}` | KH GQVL Chi nhánh |

`slug` = `pgd_slug(ten_pgd)` từ `data/pgd.py`.

---

### 4.2 Audit log — BẮT BUỘC sau MỌI thao tác ghi

```python
# Lấy username từ session — KHÔNG hardcode
username = st.session_state.get("username", "unknown")

# Ghi NGAY SAU khi ghi dữ liệu thành công
db.ghi_audit(username, "ten_action", "mô tả cụ thể")
```

**Action chuẩn:**

| Action | Khi nào |
|---|---|
| `luu_khtd_cn` | Lưu KHTD Chi nhánh |
| `luu_khtd_pgd` | Lưu KHTD PGD |
| `upload_hstd` / `upload_nq11` / `upload_gqvl` | Upload file |
| `merge_hstd` / `merge_nq11` / `merge_gqvl` | Merge toàn CN |
| `luu_no_rui_ro` / `luu_no_rui_ro_cn` | Lưu hồ sơ rủi ro |
| `xuat_bieu_cn` | Xuất biểu mẫu cấp CN |
| `xuat_01xln` / `xuat_02xln` | Xuất mẫu XLN |
| `upload_dienbao` | Upload Điện báo |

---

### 4.3 Upload file — LUÔN qua upload_service.py

```python
from services.upload_service import (
    luu_pgd_file,        # (ten_pgd, loai, file_bytes) → KetQuaUpload
    luu_file_he_thong,   # (ten_file, file_bytes)       → KetQuaUpload
    luu_dienbao,         # (loai, file_bytes, ...)       → KetQuaUpload
    KetQuaUpload,
)

# ⚠️ luu_pgd_file — 3 tham số, KHÔNG có username
ket_qua = luu_pgd_file(ten_pgd, loai, file_bytes)
ket_qua.hien_thi()   # hiển thị ✅ / ⚠️

# KHÔNG: ghi file trực tiếp từ tab, hardcode đường dẫn
```

**Sau khi upload thành công — bắt buộc:**

```python
st.cache_data.clear()
```

---

### 4.4 Tiền tệ — quy ước 3 lớp

| Lớp | Đơn vị | Ghi chú |
|---|---|---|
| Nhập liệu | Triệu đồng | `number_input` hiển thị triệu |
| Lưu trữ | VND (`× 1_000_000`) | Ghi vào kv_store / DataFrame |
| Hiển thị | `fmt_ty()` chia `/1e12` | ← `/1e9` là SAI |

```python
from utils import fmt, fmt_tien, fmt_ty, fmt_pct, fmt_so

fmt_ty(gia_tri_vnd)      # → "1,234 tỷ"
fmt(gia_tri_vnd)         # → "1.234.567.890"
fmt_so(so_luong)         # → "1,234"
```

---

### 4.5 Phân quyền — KHÔNG check role bằng chuỗi thô

```python
# ❌ SAI — thiếu role mới
if role not in ("admin", "manager", "user"):
    ...

# ✅ ĐÚNG — dùng hàm từ auth.py
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

if la_phan_he_cn(role):       # executive, admin_cn, manager_cn, admin, manager
if la_phan_he_pgd(role):      # admin_pgd, manager_pgd, user_pgd, user
if co_quyen_upload_pgd(role): # admin_pgd, manager_pgd
```

**Bảng role đầy đủ:**

| Role | Phân hệ | Quyền chính |
|---|---|---|
| `executive` | CN | Chỉ đọc dashboard |
| `admin_cn` / `admin` | CN | Toàn quyền |
| `manager_cn` / `manager` | CN | Upload, giao chỉ tiêu |
| `admin_pgd` | PGD | Upload + quản lý user PGD |
| `manager_pgd` | PGD | Upload + nhập kế hoạch |
| `user_pgd` / `user` | PGD | Tác nghiệp, chỉ thấy PGD mình |

---

### 4.6 Tên đơn vị — dùng đúng constant

```python
from config import DON_VI_CHI_NHANH, TEN_CHI_NHANH_HIEN_THI

DON_VI_CHI_NHANH       = "Hội sở Chi nhánh tỉnh"   # dùng để LỌC df
TEN_CHI_NHANH_HIEN_THI = "Chi nhánh NHCSXH tỉnh Đồng Nai"  # dùng để HIỂN THỊ UI

# KHÔNG hardcode "PGD Biên Hòa" để lọc df — dùng DON_VI_CHI_NHANH
```

---

### 4.7 Widget key — tránh DuplicateElementKey

```python
# Khi 1 hàm render được gọi nhiều lần (CN mode + PGD mode),
# mọi st.* key phải có prefix riêng

# Pattern chuẩn:
key_prefix = "cn_"    # hoặc f"pgd_{pgd_slug(pgd_user)}_"
st.selectbox("PGD", options, key=f"{key_prefix}nrr_pgd")
st.button("Lưu",            key=f"{key_prefix}btn_luu")
```

---

### 4.8 Không thêm dependency mới

Trước khi dùng thư viện mới, kiểm tra đã có trong codebase:
- `pandas`, `openpyxl`, `pyarrow` — có
- `python-docx`, `docx2pdf` — có  
- `streamlit`, `duckdb` — có
- `concurrent.futures`, `threading` — có (stdlib)

---

## 5. Pattern chuẩn khi tạo tab mới

```python
"""Mô tả ngắn tab này làm gì."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

import db
from config import COT_TEN_PGD, COT_MA_KH, ...
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from data.pgd import pgd_slug
from utils import fmt, hien_thi_dataframe_phan_trang


def render(tab: DeltaGenerator, **kwargs) -> None:
    # 1. Giải kwargs — luôn theo thứ tự này
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")

    # 2. Tab context — pattern chuẩn
    _tab_ctx = tab if tab is not None else __import__('streamlit').container()
    with _tab_ctx:
        st.subheader("📋 Tên Tab")

        # 3. Guard: kiểm tra dữ liệu
        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu.")
            return

        # 4. Phân nhánh CN vs PGD (nếu cần)
        if la_phan_he_cn(role):
            _render_cn(df_full, username)
            return
        
        # 5. Luồng PGD
        ...
```

---

## 6. Các lỗi hay gặp và cách fix

### Lỗi `DataType(null)` khi merge GQVL

**Nguyên nhân:** `dtype_backend='pyarrow'` trong `excel_to_parquet()` suy luận cột toàn null thành `ArrowDtype(null)` → `pd.concat()` crash.

**Fix:**
1. Bỏ `dtype_backend='pyarrow'` trong `data/core.py`
2. Ép kiểu cột số trong `_clean()` của GQVL bằng `pd.to_numeric(errors='coerce')`
3. Chuẩn hóa schema (union cột, fill `pd.NA`) trước `pd.concat()`
4. Thay `convert_dtypes()` bằng ép kiểu thủ công tường minh sau concat

---

### Lỗi bảng không hiển thị (trả về `None`)

**Nguyên nhân:** Thường do cột không tồn tại trong DataFrame khiến `.agg()` throw exception bị nuốt im.

**Fix pattern:**
```python
# Kiểm tra cột trước khi agg
agg_dict = {"Tổng_dư_nợ": (COT_TONG_DU_NO, "sum")}
if "Tổng giải ngân" in df.columns:           # cột tuỳ chọn
    agg_dict["Tổng_giải_ngân"] = ("Tổng giải ngân", "sum")

try:
    result = df.groupby(COT_TEN_CT).agg(**agg_dict).reset_index()
except Exception as e:
    st.error(f"❌ Lỗi tổng hợp: {e}")
    result = None
```

---

### Lỗi `DuplicateElementKey`

**Nguyên nhân:** Hàm render được gọi 2 lần (tab CN + PGD) với cùng key widget.

**Fix:** Thêm `key_prefix` vào signature và dùng `f"{key_prefix}{key_goc}"` cho mọi widget.

---

### Nested function không dùng được từ ngoài

**Nguyên nhân:** Hàm helper lồng trong `render()` (ví dụ `_render_04_05_tt`).

**Fix:** Nâng lên module-level với đủ tham số cần thiết.

---

### `luu_pgd_file` báo lỗi `username` không hợp lệ

**Nguyên nhân:** Hàm chỉ nhận 3 tham số `(ten_pgd, loai, file_bytes)` — không có `username`.

**Fix:** Gọi `db.ghi_audit()` thủ công sau khi `luu_pgd_file()` trả về.

---

## 7. Trước khi sửa — checklist bắt buộc

```
□ Đọc file cần sửa (view toàn bộ hoặc phần liên quan)
□ Xác định hàm/dòng cụ thể sẽ thay đổi
□ Kiểm tra hàm nào đang gọi hàm đó (grep ngược)
□ Sau khi sửa: có dùng db.ghi_audit() chưa?
□ Sau khi sửa: có gọi st.cache_data.clear() chưa (nếu ghi file)?
□ Widget key có unique không?
□ Tiền tệ: lưu VND hay triệu? Hiển thị fmt_ty() hay fmt()?
□ Role check: dùng la_phan_he_cn() hay check chuỗi thô?
```

---

## 8. Tham chiếu nhanh

| Yêu cầu | Hàm / File |
|---|---|
| Slug từ tên PGD | `pgd_slug(ten_pgd)` — `data/pgd.py` |
| Đường dẫn file PGD | `duong_dan_pgd(ten_pgd, loai)` — `data/pgd.py` |
| Format tiền tệ | `fmt()`, `fmt_ty()`, `fmt_so()` — `utils.py` |
| Hiển thị bảng phân trang | `hien_thi_dataframe_phan_trang(df, key=...)` — `utils.py` |
| Xuất Excel nhiều sheet | `xuat_excel({"Sheet1": df1, "Sheet2": df2})` — `utils.py` |
| Nút tải Word + PDF | `nut_tai_word_va_pdf(docx_bytes, ten_file, key)` — `template_service.py` |
| Đọc kv_store nhiều key | `db.doc_kv_prefix("prefix_")` — `db.py` |
| Gộp 22 PGD | `merge_du_lieu_toan_cn(loai)` — `upload_service.py` |
| Metadata merge | `lay_meta_merge(loai)` — `upload_service.py` |
| Kiểm tra quyền upload | `co_quyen_upload_pgd(role)` — `auth.py` |

---

## 9. Tài liệu liên quan

| File | Đọc khi nào |
|---|---|
| `ARCHITECTURE.md` | Cần hiểu quan hệ import giữa các module |
| `CONVENTIONS.md` | Cần biết quy ước chi tiết về kv_store, upload, CSS |
| `ROLES.md` | Cần phân quyền chi tiết theo role mới |
| `TROUBLESHOOTING.md` | Gặp lỗi thường gặp về dữ liệu, cache, upload |
| `HUONG_DAN_NGUON_DU_LIEU.md` | Cần hiểu 2 luồng dữ liệu CN vs PGD |
| `AGENTS.md` | Context cho Trae AI — tương tự file này |
