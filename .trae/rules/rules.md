# VBSP-SCM — Trae / Claude Code Rules
> Đọc file này trước khi sinh bất kỳ code nào.
> Không chứa dữ liệu nhạy cảm — chỉ function names, column names, patterns.
> Cập nhật: 06/06/2026

---

## 1. Dự án

- **Tên:** Hệ thống Quản trị Tín dụng Nội bộ — NHCSXH Chi nhánh Đồng Nai
- **Stack:** Streamlit + Python + SQLite + PyArrow/Parquet
- **Chạy:** `venv\Scripts\python.exe -m streamlit run app.py --server.port 8502` → `http://localhost:8502`
- **Phạm vi:** 22 đơn vị (Hội sở + 21 PGD), 95 xã/phường, ~20 users, 9 role

### 1.1 Môi trường Python — BẮT BUỘC

- **Chỉ dùng:** `D:\VBSP-SCM\venv\Scripts\python.exe` (Python 3.12).
- **Không dùng / không probe / không tạo lại:** `D:\VBSP-SCM\.venv`.
- Nếu thấy thư mục `.venv*` thì coi là môi trường cũ hoặc đã vô hiệu hóa; bỏ qua hoàn toàn.
- Không chạy `python` trần, không chạy `.venv\Scripts\python.exe`, không tạo `python -m venv .venv`.
- Khi cần compile/import/test, dùng rõ:
  - `venv\Scripts\python.exe -c "import py_compile; py_compile.compile('file.py', doraise=True); print('OK')"`
  - `venv\Scripts\python.exe -m pytest ...`
- Nếu thiếu môi trường, chạy `setup_env.bat`; script này tạo/cài lại `venv`, không tạo `.venv`.

---

## 2. Cấu trúc thư mục

```
app.py                      ← entry point, routing, session
auth.py                     ← RBAC, normalize_role(), la_phan_he_*()
config.py                   ← MỌI hằng số: COT_*, DS_PGD, ROLE, TAG_MAP...
db.py                       ← kv_store, audit_log, get_conn()
utils.py                    ← fmt(), fmt_ty(), get_tab_context()
data/
  core.py                   ← ts_file(), excel_to_parquet()
  hstd.py                   ← doc_file(), danh_dau_khong_hd()
  pgd.py                    ← pgd_slug(), duong_dan_pgd(), doc_hstd_pgd()
  khtd.py                   ← doc_khtd(), luu_khtd()
components/
  delta_card.py             ← delta_card(), kpi_row()
  export_pdf.py             ← xuat_pdf_co_chart(), download_pdf_button()
  filter_bar.py             ← filter_bar(), apply_filters()
  loan_drawer.py            ← loan_detail_drawer()
  movers.py                 ← movers_analysis()
services/
  upload_service.py         ← luu_pgd_file(), merge_du_lieu_toan_cn(), KetQuaUpload
  report_service.py         ← xuat_bao_cao(), xuat_sheet_don()
  khtd_service.py           ← giao & điều chỉnh KHTD
  kiem_soat_service.py      ← kiểm soát Chi nhánh
tabs/tab_*.py               ← mỗi file = 1 tab UI
tabs/tab_khnv_noi_bo.py     ← Quản lý nội bộ Phòng KH-NV
tabs/tab_tien_do_nop.py     ← Tiến độ nộp BC từ PGD (đọc Google Sheets)
workspaces/
  ws_executive.py           ← BGĐ — chỉ đọc
  ws_management.py          ← Phòng KH-NV — toàn CN
  ws_operation.py           ← Hỗ trợ địa bàn PGD
cache/                      ← parquet (không commit)
pgd_data/                   ← file upload PGD (không commit)
```

---

## 2.1 Bản đồ file — đọc cái gì trước khi sửa cái gì

| Muốn sửa | Đọc trước | Sửa ở đây |
|---|---|---|
| Logic giao diện tab | `tabs/tab_*.py` liên quan | Tab đó |
| Merge 22 PGD | `upload_service.py` dòng 288–480 | `merge_du_lieu_toan_cn()` |
| Đọc Excel → Parquet | `data/core.py` | `excel_to_parquet()` |
| Phân quyền / role | `auth.py`, `ROLES.md` | `auth.py` |
| Hằng số cột / chương trình | `config.py` | `config.py` |
| Xuất Word / PDF | `services/template_service.py` | Template + service |
| Workspace CN | `workspaces/ws_management.py` | File đó |
| Workspace PGD | `workspaces/ws_operation.py` | File đó |
| Upload file | `services/upload_service.py` | `luu_pgd_file()` / `luu_file_he_thong()` |
| Dữ liệu kv_store | `db.py` | `doc_kv()` / `ghi_kv()` |
| Thêm tab PGD | `tabs/tab_*.py` + `ws_operation.py` | File đó |
| Thêm tab toàn CN | `tabs/tab_*.py` + `ws_management.py` | File đó |
| Snapshot HSTD | `snapshot_service.py` | upsert-safe, tự trigger sau merge |
| Giao ban | `data/giao_ban.py` | `tinh_so_lieu_van_xuoi()` |
| Tiến độ nộp BC / GSheet | `tabs/tab_tien_do_nop.py` | `_doc_du_lieu()`, `_render_cai_dat()` |

---

## 2.2 Luồng dữ liệu — PHẢI hiểu trước khi sửa

```
PHÂN HỆ KH-NV: ws_management + ws_executive
  Phòng KH-NV upload 22 file:
    tab_upload_khnv
      → upload_service.luu_file_he_thong()
      → merge_du_lieu_toan_cn()  # gộp 22 PGD → 1 parquet
      → cache/hstd.parquet  # CACHE_HSTD
      → dùng bởi: ws_management, ws_executive...
  KHÔNG BAO GIỜ bị ảnh hưởng bởi PGD upload

PHÂN HỆ ĐỊA BÀN: ws_operation
  PGD tự upload file của mình:
    tab_upload_pgd
      → upload_service.luu_pgd_file()
      → pgd_data/{slug}/hstd_latest.xlsx
      → dùng bởi: ws_operation (lọc theo pgd_user)
  luu_pgd_file() KHÔNG được gọi merge_du_lieu_toan_cn()

Context truyền vào render():
  ctx = dict(
      df=df,              # toàn CN (CN role) hoặc chỉ PGD (PGD role)
      df_full=df_full,    # luôn là toàn CN — dùng cho báo cáo
      role=role,
      pgd_user=pgd_user,  # None nếu CN role
      username=username,
  )
```

---

## 3. Quy trình bắt buộc khi viết code

```
Bước 0: ĐỌC BUGMAP.md — kiểm tra các lỗi đã từng mắc liên quan đến file/thao tác sắp sửa
Bước 1: ĐỌC hàm gốc trước khi gọi — KHÔNG đoán tham số
Bước 2: Dùng COT_* từ config.py — KHÔNG hardcode tên cột tiếng Việt
Bước 3: Sau khi tạo hàm mới → grep xem có được gọi chưa
Bước 4: Compile check:
  venv\Scripts\python.exe -c "import py_compile; py_compile.compile('file.py', doraise=True); print('OK')"
Bước 5: Import check (nếu tạo component mới):
  venv\Scripts\python.exe -c "from components.xxx import yyy; print('OK')"
```

---

## 4. Tên cột — dùng COT_* từ config.py

```python
df[COT_TONG_DU_NO]    # ✅
df["Tổng dư nợ"]      # ❌
```

> **Tra cứu đầy đủ:** đọc `COT_REF.md` — liệt kê tất cả COT_* (Core, Extended, Personal, NQ11, GQVL, Risk).

---

## 5. Function Signatures — tra nhanh

> **Tra cứu đầy đủ:** đọc `SIGNATURES.md` — tất cả signatures của Components, Utils, Auth.

Các lỗi tham số phổ biến cần nhớ:
- `kpi_row(cols, num_columns=4)` — **KHÔNG** phải `cols=4`
- `download_pdf_button(pdf_bytes=...)` — nhận **PDF bytes**, không phải df
- `loan_detail_drawer(row: pd.Series)` — nhận **row**, không phải DataFrame
- `luu_pgd_file(ten_pgd, loai, file_bytes)` — **3 tham số**, không có username

---

## 6. Quy tắc bắt buộc

### 6.1 Lưu dữ liệu — CHỈ kv_store
```python
db.doc_kv("key")                    # đọc → None nếu không có
db.doc_kv_prefix("khtd_pgd_")       # đọc nhiều key
db.ghi_kv("key", value, username)   # ghi
# KHÔNG: json.dump(), open(file,'w'), session_state để persist
```

**Key chuẩn:**
| Key | Dùng cho |
|---|---|
| `khtd_cn` | KHTD toàn Chi nhánh |
| `khtd_pgd_{slug}` | KHTD từng PGD |
| `ct_registry_{slug}` | Danh mục chương trình |
| `merge_meta_{loai}` | Metadata merge hstd/nq11/gqvl |
| `no_rui_ro_{slug}_{yyyy}_{mm}` | Hồ sơ rủi ro |
| `kehoach` / `kehoach_pgd_{slug}` | KH Điện báo |
| `dgd_map` | Điểm giao dịch toàn CN |
| `kh_gqvl_cn_{nam}` | KH GQVL Chi nhánh |
| `kh_gqvl_pgd_{slug}_{nam}` | KH GQVL theo PGD |
| `khnv_phan_cong_list` | Phân công cán bộ nội bộ Phòng KH-NV |
| `khnv_lich_list` | Lịch công tác Phòng KH-NV |
| `bao_cao_deadline_config` | Deadline từng loại báo cáo `{loai: "YYYY-MM-DD"}` |

`slug` = `pgd_slug(ten_pgd)` từ `data/pgd.py`

### 6.2 Audit — BẮT BUỘC sau MỌI thao tác ghi
```python
username = st.session_state.get("username", "unknown")
db.ghi_kv(key, value, username)
db.ghi_audit(username, "ten_action", "mô tả cụ thể")  # NGAY SAU
```
Action chuẩn: `luu_khtd_cn`, `luu_khtd_pgd`, `upload_hstd`, `upload_nq11`,
`upload_gqvl`, `upload_dienbao`, `merge_hstd`, `merge_nq11`, `merge_gqvl`,
`luu_no_rui_ro`, `xuat_bieu_cn`, `xuat_01xln`, `xuat_02xln`

### 6.3 Upload — LUÔN qua upload_service.py
```python
from services.upload_service import luu_pgd_file, luu_file_he_thong, KetQuaUpload
ket_qua = luu_pgd_file(ten_pgd, loai, file_bytes)  # 3 tham số, không có username
ket_qua.hien_thi()
st.cache_data.clear()  # BẮT BUỘC sau upload thành công
```

### 6.4 Tiền tệ — 3 lớp
| Lớp | Đơn vị | Xử lý |
|---|---|---|
| Nhập | Triệu đồng | `number_input` |
| Lưu | VND (×1_000_000) | kv_store / DataFrame |
| Hiển thị | `fmt_ty()` | từ utils.py |

```python
fmt_ty(x)   # → "1.500" (triệu đồng, 0 số lẻ, KHÔNG có hậu tố "tỷ")
            # Cột bảng phải ghi header "(triệu đồng)"
# KHÔNG dùng NumberColumn cho cột tiền tệ → .apply(fmt_ty) trước st.dataframe()
# KHÔNG dùng /1e9 hay /1e12 trực tiếp
```

**NumberColumn dùng d3-format:**
```python
st.column_config.NumberColumn(format=",.0f")   # ✅ số nguyên
st.column_config.NumberColumn(format=".2%")    # ✅ phần trăm
# ❌ SAI: format="%.0f", format="%d", format="%.2f%%"
```

### 6.5 Phân quyền — KHÔNG check chuỗi thô
```python
role = normalize_role(role)
if la_phan_he_cn(role): ...   # ✅  (executive/admin_cn/manager_cn/chuyenvien_cn/admin/manager)
if la_phan_he_pgd(role): ...  # ✅  (admin_pgd/manager_pgd/user_pgd/user)
if role == "admin": ...        # ❌
```

| Role | Phân hệ | Quyền chính |
|---|---|---|
| `executive` | CN | Chỉ đọc dashboard |
| `admin_cn` / `admin` | CN | Toàn quyền |
| `manager_cn` / `manager` | CN | Upload, giao chỉ tiêu |
| `chuyenvien_cn` | CN | Tác nghiệp CN (không upload) |
| `admin_pgd` | PGD | Upload + quản lý user PGD |
| `manager_pgd` | PGD | Upload + nhập kế hoạch |
| `user_pgd` / `user` | PGD | Tác nghiệp, chỉ thấy PGD mình |

### 6.6 Tên cột — dùng COT_* từ config
```python
df[COT_TONG_DU_NO]    # ✅
df["Tổng dư nợ"]      # ❌
```

### 6.7 Widget key — unique
```python
key_prefix = f"pgd_{pgd_slug(pgd_user)}_"  # hoặc "cn_"
st.selectbox(..., key=f"{key_prefix}filter")
# KHÔNG dùng index loop làm key
```

### 6.8 render() — fallback khi tab=None
```python
def render(tab=None, **kwargs) -> None:
    role     = normalize_role(str(kwargs.get("role", "user") or "user"))
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)

    ctx = tab if tab is not None else st.container()
    with ctx:
        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu.")
            return
# KHÔNG dùng "with tab:" trực tiếp
```

### 6.9 Logging — không nuốt lỗi
```python
from logger import get_logger
logger = get_logger(__name__)
try: ...
except Exception as e:
    logger.error("ten_ham: mo_ta — %s", e, exc_info=True)
# KHÔNG: except Exception: pass
```

### 6.10 Tên đơn vị — dùng constant
```python
from config import DON_VI_CHI_NHANH, TEN_CHI_NHANH_HIEN_THI
# DON_VI_CHI_NHANH        → dùng để LỌC df
# TEN_CHI_NHANH_HIEN_THI  → dùng để HIỂN THỊ UI
```

### 6.11 Git — TUYỆT ĐỐI không tự commit/push
- Sửa tại `D:/VBSP-SCM` (worktree gốc, branch main)
- KHÔNG tự `git add`, `git commit`, `git push`
- Người dùng tự commit qua GitHub Desktop

### 6.12 Không thêm dependency mới
Đã có: `pandas`, `openpyxl`, `pyarrow`, `streamlit`, `duckdb`,
`python-docx`, `docx2pdf`, `concurrent.futures`, `threading`

### 6.13 CHANGELOG.md — cập nhật sau mỗi lần sửa
```
## [YYYY-MM-DD] — mô tả ngắn
- filename.py dòng ~X — mô tả thay đổi
```
Thêm lên ĐẦU FILE, dùng ngày thực tế, KHÔNG xóa entry cũ.

### 6.14 BUGMAP.md — cập nhật sau mỗi lần fix bug
- **BẮT BUỘC**: Mỗi khi fix bug, thêm entry mới vào BUGMAP.md theo template có sẵn (cuối file)
- Phân loại đúng section (A. Parquet, B. Streamlit UI, C. DataFrame, D. Database, E. Upload, F. PDF/Word, G. KHTD, H. GSheet, I. Role, J. Code Pattern)
- Nếu là dạng lỗi mới chưa có section phù hợp → tạo section mới
- Format: `### XX — [Tên lỗi]` với bảng `| | |` gồm: File, Dấu hiệu, Nguyên nhân, Fix, Ngày fix

### 6.15 pgd_mode — pattern song song 2 phân hệ
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

### 6.16 CSS & UI
- Inject CSS **một lần** trong `app.py` — không inject trong tab
- Bảng ≥ 8 cột → HTML thuần + `st.html(html_str)` (Streamlit ≥1.36) hoặc `st.markdown(html_str, unsafe_allow_html=True)` (cũ hơn)
- HTML: **KHÔNG** hardcode `color:black` / `background:white` — dùng CSS variable tương thích dark mode
- `st.date_input` bắt buộc có `format="DD/MM/YYYY"`
- Màu sắc → xem `UI_GUIDELINES.md`

### 6.17 DuckDB — LUÔN kiểm tra schema trước khi query
```python
import duckdb, pyarrow.parquet as pq

# PHẢI kiểm tra schema trước
schema = pq.read_schema(CACHE_HSTD)
cols = [f.name for f in schema]
if "Ten_ct" not in cols:
    st.warning("⚠️ Parquet thiếu cột Ten_ct")
    return

# Sau đó mới query
df = duckdb.query(f"SELECT ... FROM '{CACHE_HSTD}'").df()
```

### 6.18 Tóm tắt sau mỗi task — gửi Sonnet kiểm tra
**BẮT BUỘC**: Sau khi hoàn thành MỌI task, kết thúc bằng một đoạn tóm tắt ngắn gọn để người dùng copy gửi qua Sonnet kiểm tra. Format:

```
## Tóm tắt gửi Sonnet kiểm tra

### Task: [mô tả 1 dòng]

**Nguyên nhân:** [gốc rễ vấn đề, 1-2 dòng]

**Sửa:**
| File | Thay đổi |
|---|---|
| `path/file.py` | Mô tả ngắn |

**Verify:** compile OK × N, convention OK × N
```

- Chỉ liệt kê file thực sự đã sửa, không kể file chỉ đọc
- Mô tả thay đổi ≤ 1 dòng/file
- Nếu nhiều task trong 1 phiên → gộp chung 1 tóm tắt

### 6.19 Numeric columns — LUÔN pd.to_numeric() trước sum/mean/groupby
```python
# ❌ SAI — groupby.sum() trên cột mixed type nối chuỗi
tong = df.groupby("PGD")["Tổng dư nợ"].sum()
n_pgd = int((tong > 0).sum())  # kết quả sai

# ✅ ĐÚNG — copy + convert numeric trước
df_num = df.copy()
df_num["Tổng dư nợ"] = pd.to_numeric(df_num["Tổng dư nợ"], errors="coerce").fillna(0)
tong = df_num.groupby("PGD")["Tổng dư nợ"].sum()
n_pgd = int((tong > 0).sum())
```
Lý do: parquet từ Excel thường có mixed dtype (string/float). Groupby.sum trên object = nối chuỗi.

### 6.20 Đếm số chiều cho BQ — chọn đúng hàm đếm
| Muốn đếm | Dùng | Vì |
|---|---|---|
| Số PGD có dư nợ | `groupby(PGD)[DN].sum() > 0 → count` | 1 PGD có thể có dư nợ = 0 |
| Số Tổ TK&VV | `groupby([PGD, Tổ]).ngroups` | Tên Tổ trùng giữa các PGD |
| Số Xã | `df["Tên xã"].nunique()` | 1 xã thuộc 1 PGD duy nhất |
| Số Hội đoàn thể | `df["Tên ĐVUT"].dropna().loc[lambda s: (s!="") & (s!="CỘNG")].nunique()` | Loại NaN, rỗng, dòng tổng |

```python
# ❌ SAI — ngroups đếm cặp (PGD, Xã), không đếm unique Xã
n_xa = df.groupby([COT_TEN_PGD, COT_TEN_XA]).ngroups  # ra số cặp

# ✅ ĐÚNG
n_xa = df[COT_TEN_XA].nunique()  # ra số xã toàn CN
```

---

## 7. Lỗi đã từng mắc — KHÔNG lặp lại

| # | Lỗi | Sai | Đúng |
|---|-----|-----|------|
| 1 | kpi_row tham số | `kpi_row(data, cols=4)` | `kpi_row(data, num_columns=4)` |
| 2 | download_pdf_button | `download_pdf_button(df=..., tieu_de=...)` | `download_pdf_button(pdf_bytes=xuat_pdf_co_chart(...))` |
| 3 | loan_detail_drawer | `loan_detail_drawer(df, row_id=0)` | `loan_detail_drawer(row: pd.Series)` |
| 4 | Tên cột sai | `COT_DIEN_THOAI` | `COT_SDT` |
| 5 | Tên cột sai | `COT_TEN_TKVV` | `COT_TEN_TO` |
| 6 | Tên cột hardcode | `"PL NV"` | `COT_PL_NV` |
| 7 | Python built-in | `for i, f in enumerate(filter)` | `filters` |
| 8 | or với DataFrame | `kwargs.get("df_full") or df` | `df if _df_full is None else _df_full` |
| 9 | Chia tiền sai | `/1e9` hay `/1e12` | `fmt_ty(x)` |
| 10 | width deprecated | `width='stretch'` | `use_container_width=True` |
| 11 | CSS guard | inject CSS trong session_state guard | Inject vô điều kiện mỗi rerun |
| 12 | Mixed dtype parquet | float + str rỗng cùng cột | ép str: `str(int(v)) if v==int(v) else str(v)` |
| 13 | groupby.sum trên object | `df.groupby("PGD")["Tổng dư nợ"].sum()` | `pd.to_numeric(s, errors="coerce")` trước groupby |
| 14 | ngroups đếm cặp | `df.groupby([PGD, DVUT]).ngroups` | `df[DVUT].nunique()` nếu cần đếm unique values |
| 15 | nunique có lẫn NaN | `df[DVUT].nunique()` | `.dropna().loc[lambda s: s!=""].nunique()` |

---

## 8. Checklist trước khi báo "xong"

```
□ python -c "py_compile.compile('file.py', doraise=True)" → OK
□ Grep function mới → ĐƯỢC GỌI trong render() hoặc tab
□ COT_* đúng chính tả (không hardcode string tiếng Việt)
□ Function signatures đọc từ code gốc (không đoán)
□ db.ghi_audit() sau mọi db.ghi_kv()
□ st.cache_data.clear() sau upload/lưu file
□ Widget key có suffix unique
□ render(tab=None) với fallback st.container()
□ KHÔNG tự git commit/push
□ st.date_input có format="DD/MM/YYYY"
□ DuckDB: check schema parquet trước khi query (mục 6.17)
□ HTML: KHÔNG hardcode color:black/background:white (dark mode)
□ CHANGELOG.md đã cập nhật
□ BUGMAP.md đã cập nhật (nếu fix bug)
```

### 8.1 Rà soát sau khi xong task (đảm bảo đã "ghi vào chức năng")

```
□ Xác nhận điểm gắn (entry point):
  - Nếu sửa tab: render() gọi đúng hàm mới / signature mới
  - Nếu thêm UI: label/keys mới xuất hiện trong đúng sub-tab/workspace

□ Grep theo “dấu vết” của task:
  - Tên hàm mới, key_prefix, label UI, hoặc tên biến chính
  - Đảm bảo có ít nhất 1 call site từ render()/workspace/tab

□ Compile check đúng file đã sửa:
  python -c "import py_compile; py_compile.compile('path/to/file.py', doraise=True); print('OK')"

□ Convention check (nếu task có sửa code logic/UI):
  python scripts/check_conventions.py path/to/file.py

□ Nếu có ghi dữ liệu (db.ghi_kv):
  - Có db.ghi_audit() ngay sau đó
  - Có st.cache_data.clear() (nếu thao tác upload/lưu file/cache)

□ Nếu task là bugfix:
  - Có case tái hiện (ít nhất bằng grep/log hoặc đường đi UI)
  - Đảm bảo nhánh lỗi cũ không còn reachable (hoặc đã được handle rõ ràng)
```

---

## 9. Tài liệu tham chiếu (tự đọc khi cần)

| File | Đọc khi |
|---|---|
| `DELTA.md` | **ĐỌC ĐẦU MỖI PHIÊN** — thay đổi gần đây, component mới, signature đã cập nhật |
| `CLAUDE.md` | Convention đầy đủ, luồng dữ liệu, pattern chuẩn |
| `BUGMAP.md` | Gặp lỗi — tra trước khi debug |
| ~~`FILE_INDEX.md`~~ | *(đã xóa)* |
| `ARCHITECTURE.md` | Quan hệ import giữa các module |
| `TROUBLESHOOTING.md` | Lỗi vận hành thường gặp |
| `CHANGELOG.md` | Lịch sử thay đổi |
| `BACKLOG.md` | Yêu cầu người dùng — đã làm & sẽ làm |
