# AGENTS.md — VBSP-SCM
> File này là context chính cho Trae AI / Cline / Cursor. Đọc toàn bộ trước khi sinh code.
> Cập nhật: 13/05/2026

---

## 1. Project là gì

Hệ thống Quản trị Tín dụng Nội bộ cho **Ngân hàng Chính sách Xã hội Chi nhánh Đồng Nai** (đã sáp nhập Bình Phước 2025).

- **Stack:** Streamlit + Python + SQLite
- **Người dùng:** ~20 users, 9 vai trò (tương thích cũ + mới)
- **Phạm vi:** 22 đơn vị (Hội sở + 21 PGD), 95 xã/phường
- **Phân hệ:** 2 cấp — CN (Chi nhánh) + PGD (Phòng giao dịch)
- **Chạy:** `streamlit run app.py` → `http://localhost:8501`

---

## 2. Cấu trúc thư mục

```
├── app.py                  # Điểm vào: routing, session, normalize_role
├── auth.py                 # Đăng nhập, RBAC, normalize_role(), la_phan_he_*()
├── config.py               # Hằng số toàn hệ thống (DS_PGD, cột, chương trình...)
├── db.py                   # SQLite: kv_store, users, audit_log, hstd_snapshot
├── utils.py                # fmt(), Excel helpers, get_tab_context()
│
├── data/
│   ├── core.py             # ts_file(), parquet cache
│   ├── hstd.py             # Đọc HSTD
│   ├── pgd.py              # pgd_slug(), duong_dan_pgd(), doc_hstd_pgd()
│   ├── khtd.py             # doc_kehoach(), luu_kehoach(), doc_cbtd()
│   └── ct_discovery.py     # ct_registry chương trình theo PGD
│
├── services/
│   ├── upload_service.py   # luu_pgd_file(), luu_file_he_thong(), luu_dienbao(), KetQuaUpload
│   ├── report_service.py   # Tạo báo cáo Excel
│   ├── khtd_service.py     # Giao & Điều chỉnh KHTD
│   ├── kiem_soat_service.py# Kiểm soát Chi nhánh
│   └── snapshot_service.py # HSTD snapshot theo kỳ (nền tảng Direction A/B/C)
│
├── tabs/                   # Mỗi file = 1 tab UI
│   ├── tab_ban_dai_dien.py # Ban Đại Diện (mount cả ws_management lẫn ws_operation)
│   └── ...
├── workspaces/
│   ├── ws_executive.py     # BGĐ — chỉ đọc
│   ├── ws_management.py    # Phòng KH-NV — toàn CN
│   └── ws_operation.py     # Hỗ trợ địa bàn PGD
│
├── cache/                  # Parquet cache (không commit)
└── pgd_data/               # File upload từng PGD (không commit)
```

---

## 3. Quy tắc BẮT BUỘC khi sinh code

### 3.1 Lưu trữ dữ liệu — CHỈ dùng kv_store

```python
value = db.doc_kv("key_name")           # đọc
db.ghi_kv("key_name", value, username)  # ghi
```

**Key chuẩn:**

| Key | Dùng cho |
|---|---|
| `khtd_cn` | KHTD Chi nhánh |
| `khtd_pgd_{slug}` | KHTD PGD |
| `ct_registry_{slug}` | Chương trình theo PGD |
| `merge_meta_{loai}` | Metadata merge |
| `kehoach` | KH Điện báo toàn CN |
| `kehoach_pgd_{slug}` | KH Điện báo PGD |
| `dgd_map` | Điểm giao dịch toàn CN |
| `kh_gqvl_cn_{nam}` | KH GQVL Chi nhánh theo năm |
| `kh_gqvl_pgd_{slug}_{nam}` | KH GQVL theo PGD (dự phòng) |

`slug` = `pgd_slug(ten_pgd)` từ `data/pgd.py`

### 3.2 Audit log — BẮT BUỘC sau mọi thao tác ghi

```python
username = st.session_state.get("username", "unknown")
db.ghi_audit(username, "ten_action", "mô tả chi tiết")
```

### 3.3 Upload file — LUÔN qua upload_service.py

```python
from services.upload_service import luu_pgd_file, luu_file_he_thong, luu_dienbao, KetQuaUpload

# ⚠️ luu_pgd_file KHÔNG nhận username — 3 tham số, không hơn
ket_qua = luu_pgd_file(ten_pgd, loai, file_bytes)
ket_qua.hien_thi()
```

Không hardcode đường dẫn file trong tab.

### 3.4 Cache — xóa sau khi lưu thành công

```python
st.cache_data.clear()
```

### 3.5 Tiền tệ — quy ước 3 lớp

| Lớp | Đơn vị |
|---|---|
| Nhập liệu | Triệu đồng |
| Lưu trữ | VND (× 1.000.000) |
| Hiển thị | `fmt_ty()` chia `/1e12` ← KHÔNG phải `/1e9` |

```python
from utils import fmt, fmt_tien, fmt_ty, fmt_pct, fmt_so
```

### 3.6 Phân quyền — LUÔN normalize trước khi check

```python
# app.py đã normalize, nhưng nếu tự lấy role thì phải normalize:
from auth import normalize_role
role = normalize_role(st.session_state["user_info"]["role"])
pgd_user = st.session_state["user_info"].get("pgd")  # None nếu không phải PGD user
```

| Role | Quyền |
|---|---|
| `executive` | Chỉ đọc |
| `admin` (= `admin_cn`) | Toàn quyền CN |
| `manager` (= `manager_cn`) | Upload CN, giao chỉ tiêu |
| `user` (= `user_pgd`) | Tác nghiệp PGD |
| `admin_cn` | Quản trị Chi nhánh |
| `manager_cn` | Lãnh đạo Chi nhánh |
| `admin_pgd` | Quản trị PGD — upload + quản lý user |
| `manager_pgd` | Lãnh đạo PGD — upload, nhập KH |
| `user_pgd` | CBTD PGD — tác nghiệp |

### 3.7 CSS & UI

- Inject CSS **một lần** trong `app.py` — không inject trong tab
- Bảng ≥ 8 cột → HTML thuần + `st.markdown(unsafe_allow_html=True)`
- Màu sắc → xem `UI_GUIDELINES.md`

### 3.8 pgd_mode — pattern song song 2 phân hệ

```python
pgd_mode = kwargs.get("pgd_mode", False)
pgd_user = kwargs.get("pgd_user")

if pgd_mode:
    path = duong_dan_pgd(pgd_user, "dienbao_ht")
    key  = f"kehoach_pgd_{pgd_slug(pgd_user)}"
    # prefix widget = f"pgd_{pgd_slug(pgd_user)}_"  ← tránh DuplicateElementKey
else:
    path = DB_HT_CACHE   # toàn CN, như cũ
    key  = "kehoach"
```

### 3.9 render(tab) — pattern fallback st.container()

Tất cả tabs dùng fallback `st.container()` thay vì `with tab:` trực tiếp:

```python
def render(tab=None, **kwargs):
    ctx = tab if tab is not None else st.container()
    with ctx:
        # ... nội dung tab
```

Không viết `with tab:` trực tiếp — tab có thể là `None` khi gọi standalone.

---

## 4. Luồng dữ liệu chính

```
Phòng KH-NV (tab_upload_khnv):
  → luu_file_he_thong()  — lưu file gốc vào data/
  → merge_du_lieu_toan_cn(loai)  — gộp 22 PGD → cache/hstd.parquet (CACHE_HSTD)
  → dùng bởi ws_management, ws_executive

PGD địa bàn (tab_upload_pgd):
  → luu_pgd_file(ten_pgd, loai, file_bytes)
  → pgd_data/{slug}/hstd_latest.xlsx
  → dùng bởi ws_operation

Snapshot (snapshot_service.py):
  → chạy tự động sau merge thành công
  → ghi vào bảng hstd_snapshot (db.py)
  → nền tảng cho risk heatmap, báo cáo Word/PDF tự động
```

---

## 5. Tham chiếu nhanh — sửa gì ở đâu

| Yêu cầu | File |
|---|---|
| Thêm tab PGD | `tabs/tab_*.py` + `ws_operation.py` |
| Thêm tab toàn CN | `tabs/tab_*.py` + `ws_management.py` |
| Sửa merge 22 PGD | `upload_service.py` → `merge_du_lieu_toan_cn()` |
| Thêm chương trình TD | `config.py` → `CHUONG_TRINH_KHTD` |
| Thêm PGD mới | `config.py` → `DS_PGD`, `MA_PGD_MAP`, `PGD_XA_MAP` |
| Sửa format tiền | `utils.py` → `fmt_ty()` |
| Sửa đọc HSTD | `data/hstd.py` hoặc `data/core.py` |
| Thêm báo cáo kiểm soát | `kiem_soat_service.py` → thêm `BaoCaoMeta` |
| Sửa giao KHTD | `khtd_service.py` + `tab_khtd_giao_dc.py` |
| Sửa số liệu giao ban | `giao_ban.py` → `tinh_so_lieu_van_xuoi()` |
| Xuất Thông báo Kết luận Giao ban | `giao_ban.py` → `xuat_thong_bao_ket_luan_giao_ban()` |
| Xuất PDF (docx2pdf) | `ws_operation.py` → `_render_thong_bao_ket_luan()` |
| Quản lý điểm GD | `db.doc_dgd_map()` / `db.luu_dgd_map()` |
| Tab Ban Đại Diện | `tab_ban_dai_dien.py` — tham số `cap="tinh"` (CN) hoặc `cap="xa"` (PGD) |
| Snapshot HSTD theo kỳ | `snapshot_service.py` — upsert-safe, tự trigger sau merge |

---

## 6. Checklist trước khi commit

- [ ] Dùng `db.doc_kv()` / `db.ghi_kv()` — không JSON file
- [ ] `db.ghi_audit()` sau mọi thao tác ghi
- [ ] `st.cache_data.clear()` sau upload thành công
- [ ] Upload qua `upload_service.py`
- [ ] `luu_pgd_file(ten_pgd, loai, file_bytes)` — 3 tham số, không truyền username
- [ ] Tiền: nhập triệu → lưu VND → hiển thị `fmt_ty()` chia `/1e12`
- [ ] `normalize_role(role)` trước khi check role
- [ ] Dùng `la_phan_he_cn()` / `la_phan_he_pgd()` thay vì so sánh chuỗi role
- [ ] Không hardcode đường dẫn file
- [ ] `render(tab=None, **kwargs)` với fallback `st.container()`
- [ ] `len(tab_names) == len(_tab_renderers)` nếu sửa ws_*.py
- [ ] prefix widget unique khi pgd_mode=True

---

## 7. Quy tắc bắt buộc (tổng hợp)

### Check role — BẮT BUỘC

```python
from auth import normalize_role, la_phan_he_cn, la_phan_he_pgd
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

role = normalize_role(role)   # luôn normalize trước

if la_phan_he_cn(role):       # CN roles: executive, admin_cn, manager_cn
if la_phan_he_pgd(role):      # PGD roles: admin_pgd, manager_pgd, user_pgd
if co_quyen_upload_pgd(role):
if co_quyen_quan_ly_user_pgd(role):
```

**KHÔNG dùng:** `role not in ("admin", "manager", "user")` — thiếu role mới.

### Tên đơn vị — BẮT BUỘC

| Constant | Dùng để |
|---|---|
| `DON_VI_CHI_NHANH = "Hội sở Chi nhánh tỉnh"` | **Chỉ dùng để lọc df** |
| `TEN_CHI_NHANH_HIEN_THI = "Chi nhánh NHCSXH tỉnh Đồng Nai"` | **Chỉ dùng để hiển thị UI** |

**⚠️ KHÔNG hardcode** `"PGD Biên Hòa"` để lọc df — luôn dùng `DON_VI_CHI_NHANH`.

### Template Word — BẮT BUỘC

- Dùng `services/template_service.py` — không tự render docx
- File template đặt trong `templates/`
- Test trước khi dùng: `python test_template.py`
- Quy ước đặt tên constant: `TMPL_*` trong `template_service.py`

---

## 8. File tài liệu đầy đủ

| File | Nội dung |
|---|---|
| `ARCHITECTURE.md` | Sơ đồ module chi tiết, quan hệ import |
| `CONVENTIONS.md` | Quy ước code đầy đủ |
| `UI_GUIDELINES.md` | Bảng màu, typography |
| `CHANGELOG.md` | Lịch sử thay đổi |
| `ROADMAP.md` | Sprint + backlog |
| `TROUBLESHOOTING.md` | Xử lý lỗi thường gặp |
| `ROLES.md` | Mô tả chi tiết hệ thống role |
| `TEMPLATES.md` | Hướng dẫn quản lý template Word |
| `HUONG_DAN_PHAN_HE.md` | Hướng dẫn sử dụng theo phân hệ |
| `HUONG_DAN_NGUON_DU_LIEU.md` | Luồng upload, cache, 2 luồng dữ liệu |

---

## 9. Sau mỗi lần apply — CẬP NHẬT CHANGELOG.md

Thêm entry mới lên ĐẦU FILE `CHANGELOG.md` (ngay sau dòng `# CHANGELOG`):

```
## [YYYY-MM-DD] — <mô tả ngắn task>
- `filename.py` dòng ~X — mô tả thay đổi
- `filename2.py` — mô tả thay đổi
```

**Quy tắc:**
- Dùng ngày thực tế hôm nay
- Mỗi file thay đổi = 1 dòng
- KHÔNG xóa entry cũ
- Áp dụng cho MỌI thay đổi kể cả fix nhỏ
