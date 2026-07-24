# VBSP-SCM — Trae / Claude Code Rules
> Đọc file này trước khi sinh bất kỳ code nào.
> Không chứa dữ liệu nhạy cảm — chỉ function names, column names, patterns.
> Cập nhật: 06/06/2026

---

## 1. Dự án

- **Tên:** Hệ thống Quản trị Tín dụng Nội bộ — NHCSXH Chi nhánh Đồng Nai
- **Stack:** Streamlit + Python + SQLite + PyArrow/Parquet
- **Chạy:** `venv\Scripts\python.exe -m streamlit run app.py --server.port 8502`
- **Phạm vi:** 22 đơn vị (Hội sở + 21 PGD), 95 xã/phường, ~20 users, 9 role

### 1.1 Môi trường Python — BẮT BUỘC

- **Chỉ dùng:** `D:\VBSP-SCM\venv\Scripts\python.exe` (Python 3.12)
- **KHÔNG dùng:** `D:\VBSP-SCM\.venv` (môi trường cũ Python 3.14)
- Compile: `venv\Scripts\python.exe -c "import py_compile; py_compile.compile('file.py', doraise=True); print('OK')"`
- Thiếu môi trường → chạy `setup_env.bat`

---

## 2. Cấu trúc thư mục

```
app.py          ← entry point, routing, session
auth.py         ← RBAC, normalize_role(), la_phan_he_*()
config.py       ← MỌI hằng số: COT_*, DS_PGD, ROLE, TAG_MAP...
db.py           ← kv_store, audit_log, get_conn()
utils.py        ← fmt(), fmt_ty(), get_tab_context()
data/           ← core.py, hstd.py, pgd.py, khtd.py
components/     ← delta_card.py, export_pdf.py, filter_bar.py, loan_drawer.py, movers.py
services/       ← upload_service.py, report_service.py, khtd_service.py, kiem_soat_service.py
tabs/tab_*.py   ← mỗi file = 1 tab UI
workspaces/     ← ws_executive.py (BGĐ), ws_management.py (KH-NV), ws_operation.py (PGD)
cache/          ← parquet (không commit)
pgd_data/       ← file upload PGD (không commit)
```

---

## 2.1 Bản đồ file — xem CODE_INDEX.md
Chi tiết map chức năng → file → hàm trong `CODE_INDEX.md`. File quan trọng: `upload_service.py`, `data/hstd.py`, `data/pgd.py`, `ws_*.py`, `tabs/tab_*.py`.

---

## 2.2 Luồng dữ liệu — PHẢI hiểu trước khi sửa

**PHÂN HỆ KH-NV:** `tab_upload_khnv` → `luu_file_he_thong()` → `merge_du_lieu_toan_cn()` → `cache/hstd.parquet` → dùng bởi `ws_management`, `ws_executive`. **KHÔNG** bị ảnh hưởng bởi PGD upload.

**PHÂN HỆ ĐỊA BÀN:** `tab_upload_pgd` → `luu_pgd_file()` → `pgd_data/{slug}/hstd_latest.xlsx` → dùng bởi `ws_operation`. `luu_pgd_file()` **KHÔNG** gọi `merge_du_lieu_toan_cn()`.

**Context render():** `df` (toàn CN hoặc PGD), `df_full` (luôn toàn CN), `role`, `pgd_user` (None nếu CN), `username`.

---

## 3. Quy trình bắt buộc khi viết code
```
Bước 0: ĐỌC BUGMAP.md  Bước 1: ĐỌC hàm gốc  Bước 2: Dùng COT_*
Bước 3: Grep hàm mới  Bước 4: Compile check  Bước 5: Import check
```

---

## 4. Tên cột — dùng COT_* từ config.py
```python
df[COT_TONG_DU_NO]    # ✅
df["Tổng dư nợ"]      # ❌
```
Tra cứu đầy đủ trong `COT_REF.md`.

---

## 5. Function Signatures — tra nhanh
Tra cứu đầy đủ trong `SIGNATURES.md`. Các lỗi tham số phổ biến:
- `kpi_row(cols, num_columns=4)` — **KHÔNG** phải `cols=4`
- `download_pdf_button(pdf_bytes=...)` — nhận **PDF bytes**
- `loan_detail_drawer(row: pd.Series)` — nhận **row**
- `luu_pgd_file(ten_pgd, loai, file_bytes)` — **3 tham số**

---

## 6. Quy tắc bắt buộc

### 6.1 Lưu dữ liệu — CHỈ kv_store
```python
db.doc_kv("key")              # đọc → None nếu không có
db.ghi_kv("key", value, username)   # ghi
```
**KHÔNG** dùng `json.dump()`, `open(file,'w')`, `session_state` để persist.

**Key chuẩn:** Xem trong `CODE_INDEX.md`. Các key thường dùng: `khtd_cn`, `khtd_pgd_{slug}`, `merge_meta_{loai}`, `kehoach`, `dgd_map`, `khnv_phan_cong_list`, `bao_cao_deadline_config`.

`slug` = `pgd_slug(ten_pgd)` từ `data/pgd.py`

### 6.2 Audit — BẮT BUỘC sau MỌI thao tác ghi
```python
username = st.session_state.get("username", "unknown")
db.ghi_kv(key, value, username)
db.ghi_audit(username, "ten_action", "mô tả cụ thể")  # NGAY SAU
```

### 6.3 Upload — LUÔN qua upload_service.py
```python
from services.upload_service import luu_pgd_file, luu_file_he_thong, KetQuaUpload
ket_qua = luu_pgd_file(ten_pgd, loai, file_bytes)  # 3 tham số
ket_qua.hien_thi()
st.cache_data.clear()  # BẮT BUỘC sau upload
```

### 6.4 Tiền tệ — 3 lớp
| Lớp | Đơn vị | Xử lý |
|---|---|---|
| Nhập | Triệu đồng | `number_input` |
| Lưu | VND (×1_000_000) | kv_store/DataFrame |
| Hiển thị | `fmt_ty()` | triệu đồng, 0 số lẻ, header "(triệu đồng)" |

**NumberColumn:** `format=",.0f"` (số nguyên), `format=".2%"` (phần trăm). **KHÔNG** dùng `%.0f`, `%.2f%%`.

### 6.5 Phân quyền — KHÔNG check chuỗi thô
```python
role = normalize_role(role)
if la_phan_he_cn(role): ...   # executive/admin_cn/manager_cn/admin/manager/chuyenvien_cn
if la_phan_he_pgd(role): ...  # admin_pgd/manager_pgd/user_pgd/user
```

| Role | Phân hệ | Quyền |
|---|---|---|
| `executive` | CN | Chỉ đọc |
| `admin_cn`/`admin` | CN | Toàn quyền |
| `manager_cn`/`manager` | CN | Upload, giao chỉ tiêu |
| `chuyenvien_cn` | CN | Tác nghiệp (không upload) |
| `admin_pgd` | PGD | Upload + quản lý user |
| `manager_pgd` | PGD | Upload + nhập kế hoạch |
| `user_pgd`/`user` | PGD | Tác nghiệp PGD mình |

### 6.6 Widget key — unique
```python
key_prefix = f"pgd_{pgd_slug(pgd_user)}_"  # hoặc "cn_"
st.selectbox(..., key=f"{key_prefix}filter")
```

### 6.7 render() — fallback khi tab=None
```python
def render(tab=None, **kwargs) -> None:
    ctx = tab if tab is not None else st.container()
    with ctx:
        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu.")
            return
```
**KHÔNG** dùng `with tab:` trực tiếp.

### 6.8 Logging — không nuốt lỗi
```python
from logger import get_logger
logger = get_logger(__name__)
try: ...
except Exception as e:
    logger.error("ten_ham: mo_ta — %s", e, exc_info=True)
```
**KHÔNG** `except Exception: pass` hoặc `print(e)`.

### 6.9 Tên đơn vị — dùng constant
```python
from config import DON_VI_CHI_NHANH, TEN_CHI_NHANH_HIEN_THI
```
`DON_VI_CHI_NHANH` → LỌC df; `TEN_CHI_NHANH_HIEN_THI` → HIỂN THỊ UI.

### 6.10 Git — TUYỆT ĐỐI không tự commit/push
- Sửa tại `D:/VBSP-SCM` (worktree gốc, branch main)
- **KHÔNG** tự `git add`, `git commit`, `git push` — user tự commit qua GitHub Desktop

### 6.11 Không thêm dependency mới
Đã có: `pandas`, `openpyxl`, `pyarrow`, `streamlit`, `duckdb`, `python-docx`, `docx2pdf`, `concurrent.futures`, `threading`

### 6.12 CHANGELOG.md — cập nhật sau mỗi lần sửa
Thêm lên ĐẦU FILE: `## [YYYY-MM-DD] — mô tả ngắn` + list file thay đổi. Dùng ngày thực tế, KHÔNG xóa entry cũ.

### 6.13 BUGMAP.md — cập nhật sau mỗi lần fix bug
**BẮT BUỘC**: Thêm entry vào `BUGMAP.md` theo template (cuối file). Phân loại đúng section (A-J). Format: `### XX — [Tên lỗi]` với bảng File/Dấu hiệu/Nguyên nhân/Fix/Ngày fix.

### 6.14 pgd_mode — pattern song song 2 phân hệ
```python
pgd_mode = kwargs.get("pgd_mode", False)
if pgd_mode:
    path = duong_dan_pgd(pgd_user, "dienbao_ht")
    key = f"kehoach_pgd_{pgd_slug(pgd_user)}"
else:
    path = DB_HT_CACHE
    key = "kehoach"
```

### 6.15 CSS & UI
- Inject CSS 1 lần trong `app.py`
- Bảng ≥ 8 cột → HTML + `st.html()` hoặc `st.markdown(unsafe_allow_html=True)`
- **KHÔNG** hardcode `color:black`/`background:white` (dùng CSS variable cho dark mode)
- `st.date_input` bắt buộc `format="DD/MM/YYYY"`
- Màu sắc → xem `docs/UI_GUIDELINES.md`

### 6.16 DuckDB — kiểm tra schema trước khi query
```python
schema = pq.read_schema(CACHE_HSTD)
cols = [f.name for f in schema]
if "Ten_ct" not in cols:
    st.warning("⚠️ Parquet thiếu cột Ten_ct")
    return
df = duckdb.query(f"SELECT ... FROM '{CACHE_HSTD}'").df()
```

### 6.17 Tóm tắt sau mỗi task
Kết thúc mỗi task bằng tóm tắt ngắn để user gửi Codex kiểm tra. Xem format đầy đủ trong `SIGNATURES.md`.

### 6.18 Numeric columns — pd.to_numeric() trước groupby
```python
df_num = df.copy()
df_num["Tổng dư nợ"] = pd.to_numeric(df_num["Tổng dư nợ"], errors="coerce").fillna(0)
tong = df_num.groupby("PGD")["Tổng dư nợ"].sum()
```

### 6.19 Đếm số chiều cho BQ
| Đếm | Dùng |
|---|---|
| Số PGD có dư nợ | `groupby(PGD)[DN].sum() > 0 → count` |
| Số Tổ TK&VV | `groupby([PGD, Tổ]).ngroups` |
| Số Xã | `df["Tên xã"].nunique()` |
| Số Hội đoàn thể | `df["Tên ĐVUT"].dropna().loc[lambda s: (s!="") & (s!="CỘNG")].nunique()` |

**⚠️ KHÔNG** dùng `ngroups` để đếm unique — dùng `nunique()`.

---

## 7. Lỗi đã từng mắc — xem BUGMAP.md
Chi tiết trong `BUGMAP.md`. Các lỗi phổ biến: `kpi_row(num_columns=4)`, `download_pdf_button(pdf_bytes=...)`, `loan_detail_drawer(row: pd.Series)`, `luu_pgd_file(3 tham số)`, `COT_SDT` không phải `COT_DIEN_THOAI`, `pd.to_numeric()` trước groupby, `nunique()` không dùng `ngroups`.

---

## 8. Checklist trước khi báo "xong"
```
□ Compile OK  □ Grep hàm mới có call site  □ COT_* đúng  □ Audit sau ghi KV
□ Cache clear sau upload  □ Widget key unique  □ render(tab=None) fallback
□ Không tự git commit  □ date_input format="DD/MM/YYYY"  □ DuckDB check schema
□ HTML không hardcode color  □ CHANGELOG/BUGMAP cập nhật
```

### 8.1 Rà soát sau khi xong task
```
□ Entry point: render() gọi đúng hàm mới
□ Grep: hàm mới có ≥1 call site
□ Compile check file đã sửa
□ Nếu ghi dữ liệu: có db.ghi_audit() + st.cache_data.clear()
□ Nếu bugfix: nhánh lỗi cũ không còn reachable
```

---

## 9. Tài liệu tham chiếu
| File | Đọc khi |
|---|---|
| `DELTA.md` | **ĐẦU MỖI PHIÊN** |
| `CLAUDE.md` | Convention |
| `BUGMAP.md` | Gặp lỗi |
| `CODE_INDEX.md` | Map chức năng → file |
| `COT_REF.md` | Tên cột COT_* |
| `SIGNATURES.md` | Function signatures |
| `docs/ARCHITECTURE.md` | Quan hệ import |
| `CHANGELOG.md` | Lịch sử |
