# VBSP-SCM Project Rules — Dành cho AI Code Assistant

> **Mục đích:** File này giúp AI (Claude, GPT, Copilot...) hiểu cấu trúc dự án,
> tránh gọi sai function signature, sai tham số, hoặc tạo code không chạy được.
> **Không chứa dữ liệu nhạy cảm** — chỉ toàn function names, column names, patterns.

---

## 1. TỔNG QUAN DỰ ÁN

```
VBSP-SCM/
├── app.py              # Entry point - load data, routing workspace
├── config.py           # MỌI hằng số: COT_*, FILE_PATH, DS_PGD, ROLE, TAG_MAP...
├── utils.py            # 20+ utility functions
├── auth.py             # Authentication + 9 role system
├── db.py               # KV store, audit, baseline DB
├── snapshot_service.py # Snapshot versioning
├── logo.png            # Logo NHCSXH
├── assets/logo.png     # Logo NHCSXH (alt)
├── logo-vbsp.jpg       # Logo NHCSXH (alt)
├── data/               # Data loading module
│   ├── __init__.py     # Re-exports all public functions
│   ├── core.py         # ts_file, excel_to_parquet
│   ├── hstd.py         # doc_file, doc_file_nq11, danh_dau_khong_hd...
│   ├── pgd.py          # pgd_slug, doc_hstd_pgd, doc_hstd_toan_cn_pgd...
│   ├── khtd.py         # doc_khtd, luu_khtd
│   ├── cdtotkvv.py     # CDTổ/TKVV data
│   └── giao_ban.py     # Giao ban data
├── components/          # **5 components mới** (tự tạo)
│   ├── __init__.py      # Empty
│   ├── delta_card.py    # delta_card(), info_popover(), kpi_row()
│   ├── export_pdf.py    # xuat_pdf_co_chart(), download_pdf_button(), fig_to_bytes()
│   ├── filter_bar.py    # filter_bar(), apply_filters()
│   ├── loan_drawer.py   # loan_detail_drawer()
│   └── movers.py        # movers_analysis()
├── tabs/               # 40+ tab modules
│   ├── __init__.py
│   ├── tab_tongquan.py
│   ├── tab_baocao.py
│   ├── tab_so_sanh_ky.py
│   ├── pdf_service.py  # PDF export cũ (có logo, giữ lại)
│   ├── kiem_soat_service.py
│   └── ... (40+ files)
├── workspaces/         # 3 workspace (Phân hệ)
│   ├── ws_operation.py # PGD — Tác nghiệp
│   ├── ws_management.py # Chi nhánh — Điều hành
│   └── ws_executive.py # Lãnh đạo — Executive
├── services/           # 15+ service modules
│   ├── excel_service.py
│   ├── migration_service.py
│   ├── hhi_service.py
│   ├── du_phong_service.py
│   └── ...
├── templates/          # Word templates (.docx)
├── cache/              # Parquet files
│   ├── hstd.parquet    # ~30MB, 174 cột
│   └── nq11.parquet
└── .streamlit/
    └── config.toml
```

---

## 2. QUY TRÌNH BẮT BUỘC KHI VIẾT CODE

### Bước 1: ĐỌC HÀM GỐC trước khi gọi
```
⚠️ KHÔNG BAO GIỜ đoán tên tham số. Phải Grep/Read hàm gốc trước.
   Sai 1 chữ = lỗi runtime.
```

### Bước 2: CHECK COLUMN NAMES trong config.py
```
Tất cả tên cột dùng COT_* constants từ config.py.
Tuyệt đối không hardcode string tên cột tiếng Việt trong code.
```

### Bước 3: CHECK FUNCTION ĐƯỢC GỌI
```
Sau khi tạo function mới trong workspace, GREP xem function đó có
được gọi trong render() hoặc tab tương ứng không.
```

### Bước 4: COMPILE CHECK
```bash
python -c "import py_compile; py_compile.compile('path/to/file.py', doraise=True); print('OK')"
```

### Bước 5: IMPORT CHECK (nếu tạo component mới)
```bash
python -c "from components.xxx import yyy; print('OK')"
```

### Bước 6: RESTART SERVER + TEST
```bash
streamlit run app.py --server.port 8501
```

---

## 3. TẤT CẢ COT_* CONSTANTS (từ config.py)

```python
# ── Core columns ──
COT_TEN_PGD      = "Tên PGD"
COT_MA_KH        = "Mã KH"
COT_TEN_KH       = "Tên KH"
COT_SO_KU        = "Số khế ước"
COT_NGAY_VAY     = "Ngày vay"
COT_NGAY_DH      = "Ngày ĐH theo Gia hạn"
COT_NGAY_DEN_HAN = COT_NGAY_DH          # alias
COT_NGAY_DH_HD   = "Ngày ĐH theo hợp đồng"
COT_THOI_HAN     = "Thời hạn vay"
COT_LAI_SUAT     = "Lãi suất"
COT_MUC_VAY      = "Mức vay"
COT_DU_NO_TH     = "Dư nợ trong hạn"
COT_DU_NO_QH     = "Dư nợ quá hạn"
COT_TONG_DU_NO   = "Tổng dư nợ"
COT_TEN_CT       = "Tên chương trình"
COT_TINH_TRANG   = "Tình trạng món vay"
COT_DIA_CHI      = "Địa chỉ"
COT_SDT          = "Số điện thoại"
COT_NGAY_SL      = "Ngày số liệu"
COT_GOC_TRA      = "Gốc đã trả"

# ── Extended columns ──
COT_CMND              = "Số CMND"
COT_TEN_TO            = "Tên tổ"
COT_TEN_XA            = "Tên xã"
COT_TEN_THON          = "Tên thôn"
COT_NGUON_VON         = "Nguồn vốn"          # 1=TW, 2=ĐP
COT_MA_NHA_DAU_TU     = "Mã nhà đầu tư"
COT_MA_CHUONG_TRINH   = "Mã chương trình"
COT_TEN_HSSV          = "Họ tên HSSV"
COT_TEN_VC            = "Họ tên vợ/chồng"

# ── Risk/Activity columns ──
COT_LAI_TON     = "Lãi tồn TH"
COT_LAI_TON_QH  = "Lãi tồn QH"
COT_SO_DU_TG    = "Số dư tiền gửi 105"
COT_LAI_THANG   = "Lãi DT trong tháng"
COT_DVUT        = "Tên ĐVUT"              # Đơn vị ủy thác
COT_PHAN_LOAI   = "Phân loại"
COT_NGAY_GDGN   = "Ngày giao dịch gần nhất"
```

---

## 4. TẤT CẢ FUNCTION SIGNATURES — COMPONENTS

### 4.1 delta_card.py
```python
# ⚠️ THAM SỐ: num_columns (KHÔNG phải cols)
def kpi_row(cols: list[dict], num_columns: int = 4):
    """cols là list[dict], mỗi dict là kwargs cho delta_card()"""

def delta_card(
    label: str,
    value: str | float | int,
    delta: float | None = None,
    delta_label: str = "so với kỳ trước",
    delta_color: str = "normal",     # "normal"|"inverse"|"off"
    help: str | None = None,
    icon: str = "",
    suffix: str = "",
    precision: int = 0,
    key: str | None = None,
    use_container_width: bool = True,
):
```

### 4.2 export_pdf.py
```python
# ⚠️ download_pdf_button nhận PDF BYTES (không phải df, tieu_de...)
def download_pdf_button(
    pdf_bytes: bytes,
    filename: str = "bao_cao.pdf",
    label: str = "📥 Tải PDF",
    key: str | None = None,
):

# Tạo PDF bytes TRƯỚC, rồi truyền vào download_pdf_button
def xuat_pdf_co_chart(
    df: pd.DataFrame,
    tieu_de: str,
    nguoi_xuat: str,
    figs: Sequence[tuple[go.Figure, str]] | None = None,
    cols_tien: list[str] | None = None,
    don_vi_tien: str = "đồng",
    prefix_file: str = "",
    them_dong_tong: bool = True,
    them_ngay_xuat: bool = True,
) -> bytes:

# Helper: chuyển Plotly figure → PNG bytes
def fig_to_bytes(fig: go.Figure, width=800, height=400) -> bytes | None:

# Logo tìm từ 3 vị trí: assets/logo.png, logo.png, logo-vbsp.jpg
def _tim_logo() -> str | None:
def _ve_header(elements, tieu_de, nguoi_xuat, usable_w):
```

### 4.3 filter_bar.py
```python
def filter_bar(
    df: pd.DataFrame,
    filters: list[dict],
    key_prefix: str = "fb",
    on_change: Callable | None = None,
) -> dict[str, Any]:
    """
    filters = [{"field": "Tên xã", "label": "Xã", "type": "select"}, ...]
    type: "select" | "multiselect" | "text" | "range"
    Returns: {field: value} — None nghĩa là "Tất cả"
    """

def apply_filters(df: pd.DataFrame, filter_values: dict) -> pd.DataFrame:
```

### 4.4 loan_drawer.py
```python
# ⚠️ Nhận ROW (pd.Series | dict), KHÔNG phải DataFrame
def loan_detail_drawer(
    row: pd.Series | dict,
    title: str | None = None,
    extra_fields: list[tuple[str, str, str | None]] | None = None,
    field_configs: list[dict] | None = None,
):
    """Hiển thị nút "📄 Chi tiết", click mở drawer trượt phải."""
```

### 4.5 movers.py
```python
def movers_analysis(
    df_curr: pd.DataFrame,
    df_prev: pd.DataFrame | None = None,
    top_n: int = 10,
    key_prefix: str = "mover",
    on_select_dimension: Callable | None = None,
    on_select_metric: Callable | None = None,
    show_title: bool = True,
):
    """Phân tích biến động - Top cải thiện / giảm sút."""
```

---

## 5. TẤT CẢ FUNCTION SIGNATURES — UTILS (utils.py)

```python
def fmt_so(x) -> str:           # Format số (dấu phẩy ngàn)
def fmt_tien(x) -> str:         # Format tiền (triệu đồng)
def fmt_ty(x) -> str:           # Format tiền (tỷ đồng)
def fmt_pct(x) -> str:          # Format % (2 chữ số)
def fmt(x) -> str:              # Format số tổng quát
def fmt_ngay(val) -> str:       # Format ngày dd/mm/yyyy
def fmt_bang_ty(x, so_le=0) -> str:  # Format bảng theo tỷ
def fmt_cl(x) -> str:           # Format chất lượng
def fmt_tl(th, kh) -> str:      # Format tỷ lệ thực hiện/kế hoạch
def vn(x, d=1, show_sign=False) -> str:  # Format số Việt Nam
def norm_col_header(s: str) -> str:  # Chuẩn hóa tên cột
def hien_thi_dataframe_phan_trang(df, so_dong_moi_trang=500, key="df", **kwargs):
def format_df_vn(df: pd.DataFrame) -> pd.DataFrame:
def xuat_excel(sheets: dict) -> bytes:
def ten_file_xuat(prefix: str, ext="xlsx") -> str:
def quet_templates(templates_dir) -> list:
def auto_fill_document(data_row, template_path, tag_map, ...):
def auto_fill_klgb(df, template_path, ...):
def pick_hstd_column(df, *candidates) -> str | None:
def lay_config(key: str, fallback):  # Đọc config từ Streamlit secrets
```

---

## 6. TẤT CẢ FUNCTION SIGNATURES — DATA MODULE

```python
# data/__init__.py re-exports:

# Từ core.py:
def ts_file(path: str) -> float:       # Timestamp file
def excel_to_parquet(excel_path, parquet_path, ...):  # Convert Excel → Parquet

# Từ hstd.py:
def doc_file(path: str = FILE_PATH) -> pd.DataFrame:
def doc_file_nq11(path: str = FILE_PATH_NQ11) -> pd.DataFrame:
def doc_file_gqvl(path: str = FILE_PATH_GQVL) -> pd.DataFrame:
def doc_file_sk_gqvl(path: str = FILE_PATH_SK_GQVL) -> pd.DataFrame:
def doc_dienbao(path: str = FILE_PATH_DB) -> pd.DataFrame:
def db_lookup(ma_kh: str) -> dict | None:
def db_nqh_con(df: pd.DataFrame, ...) -> pd.DataFrame:
def danh_dau_khong_hd(df: pd.DataFrame) -> pd.DataFrame:
def danh_dau_khong_hd_cached(df: pd.DataFrame) -> pd.DataFrame:
def tong_hop_khong_hd(df, nhom_theo: str) -> pd.DataFrame:
def tong_hop_khong_hd_cached(df, nhom_theo: str) -> pd.DataFrame:
def ds_chi_tiet_khong_hd(df, nhom_theo: str, gia_tri_nhom=None) -> pd.DataFrame:
def canh_bao_migration(df) -> pd.DataFrame:
def canh_bao_migration_cached(df) -> pd.DataFrame:

# Từ pgd.py:
def pgd_slug(ten_pgd: str) -> str:     # "PGD Long Thành" → "pgd_long_thanh"
def duong_dan_pgd(ten_pgd: str) -> Path:
def doc_hstd_pgd(ten_pgd: str) -> pd.DataFrame | None:
def doc_nq11_pgd(ten_pgd: str) -> pd.DataFrame | None:
def doc_hstd_toan_cn_pgd() -> pd.DataFrame | None:
def doc_nq11_toan_cn_pgd() -> pd.DataFrame | None:
```

---

## 7. TẤT CẢ FUNCTION SIGNATURES — AUTH

```python
def normalize_role(role: str) -> str:   # "admin" → "admin_cn", "user" → "user_pgd"
def is_cn_role(role: str) -> bool:      # Chi nhánh?
def is_pgd_role(role: str) -> bool:     # PGD?
def la_phan_he_cn(role: str) -> bool:   # Alias cho is_cn_role
def get_permissions(role: str, pgd_user=None) -> dict:
def get_tab_permissions(role: str) -> dict:
```

---

## 8. KIẾN TRÚC WORKSPACE

Mỗi workspace file có 1 hàm `render(**kwargs)` chính. kwargs gồm:
- `df`: DataFrame HSTD
- `df_nq11`: DataFrame NQ11
- `role`: Role người dùng
- `pgd_user`: PGD hiện tại (nếu là PGD role)

Pattern tab trong workspace:
```python
# Định nghĩa tab group:
CAC_NHOM = {
    "nghiep_vu_pgd": {
        "label": "📋 Nghiệp vụ PGD",
        "tabs": [
            ("🔍 Tra cứu", lambda tab: tab_tracuu.render(tab, **kwargs)),
            ("📊 Danh sách", lambda tab: tab_danhsach.render(tab, **kwargs)),
        ],
    },
    ...
}

# Render:
nhom_chon = st.radio("Chọn nhóm", ds_label, horizontal=True)
tabs_con = st.tabs(ten_tabs)
for i, tab_c in enumerate(tabs_con):
    with tab_c:
        renderers[i](tab_c)
```

---

## 9. LỖI THƯỜNG GẶP — CHECKLIST

### ❌ Các lỗi ĐÃ TỪNG MẮC (tuyệt đối không lặp lại):

| # | Lỗi | Sai | Đúng |
|---|-----|-----|------|
| 1 | kpi_row tham số | `kpi_row(data, cols=4)` | `kpi_row(data, num_columns=4)` |
| 2 | download_pdf_button tham số | `download_pdf_button(df=..., tieu_de=...)` | `download_pdf_button(pdf_bytes=xuat_pdf_co_chart(...))` |
| 3 | loan_detail_drawer tham số | `loan_detail_drawer(df, row_id=0, key_suffix="x")` | `loan_detail_drawer(row: pd.Series)` |
| 4 | Biến sai tên | `n_kh` (ws_executive _kpi_tang_truong) | `nkh` |
| 5 | Function không được gọi | Tạo _render_xxx() nhưng không gọi trong render() | Phải gọi trong render() hoặc tab |
| 6 | Thiếu import | Dùng component mà quên `from components.xxx import yyy` | Luôn kiểm tra imports |
| 7 | Tên cột hardcode | `"Tổng dư nợ"` thay vì `COT_TONG_DU_NO` | Luôn dùng COT_* |
| 8 | for i, f in enumerate(filter) | `filter` là Python built-in | `filters` |
| 9 | COT_DIEN_THOAI không tồn tại | Dùng `COT_DIEN_THOAI` | `COT_SDT` |
| 10 | COT_TEN_TKVV không tồn tại | Dùng `COT_TEN_TKVV` | `COT_TEN_TO` |

### ✅ Checklist trước khi báo "xong":

- [ ] `python -c "import py_compile; py_compile.compile('file.py', doraise=True)"` → OK
- [ ] Grep function name trong file workspace → ĐƯỢC GỌI
- [ ] Tất cả COT_* constants dùng đúng chính tả tiếng Việt
- [ ] Tất cả function gọi đúng signature (đọc code gốc, không đoán)
- [ ] `from components.xxx import yyy` có trong imports
- [ ] Code mới không hardcode string tiếng Việt cho tên cột
- [ ] Logo PDF: dùng `_tim_logo()` → `assets/logo.png` | `logo.png` | `logo-vbsp.jpg`
- [ ] Server restart: `streamlit run app.py --server.port 8501`

---

## 9B. 🚫 NGUYÊN TẮC SINH TỬ — TRƯỚC KHI XOÁ BẤT KỲ FILE/THƯ MỤC NÀO

> **TUYỆT ĐỐI CẤM xoá mà chưa kiểm tra reference. Vi phạm = mất dữ liệu thật, crash hệ thống.**

### 🔴 ĐÃ TỪNG MẮC (2026-05-16) — bài học máu:

| Hành động sai | Hậu quả | Lẽ ra phải làm |
|---|---|---|
| Xoá `pdf_service.py` (root) | 22 files import → crash toàn bộ nút Xuất PDF | **Grep `from pdf_service import`** → thấy 22 references → KHÔNG xoá |
| Xoá `gen_dcgiam_sheet.py` | `tab_kh_gqvl.py` gọi `subprocess` → crash nút Generate GQVL | **Grep `gen_dcgiam_sheet`** → thấy 3 references → KHÔNG xoá |
| Xoá `pgd_data/` (322 MB) | 37 files tham chiếu, toàn bộ dữ liệu PGD bốc hơi | **Grep `pgd_data` + `PGD_DATA_DIR`** → thấy 37 references → KHÔNG xoá |
| Xoá `data/qd/` (242 MB) | Mất toàn bộ Quyết định PDF đã upload | **Grep `data/qd` + `QD_DIR`** → KHÔNG xoá |

### 📋 QUY TRÌNH BẮT BUỘC TRƯỚC KHI XOÁ:

```
1. GREP toàn bộ codebase tìm tên file / tên thư mục
   → Nếu có KẾT QUẢ: DỪNG — không xoá
   → Chỉ xoá nếu 0 references

2. Với file .py:
   Grep "from <tên_file> import" + "import <tên_file>"

3. Với file .xlsx / .pdf / .parquet:
   Grep tên file đầy đủ + grep tên folder chứa nó

4. Với thư mục dữ liệu (data/, pgd_data/, cache/...):
   Grep CONSTANT dẫn đến nó (VD: PGD_DATA_DIR, CACHE_DIR, FILE_PATH_*)
   → Nếu có import constant đó trong config.py: DỪNG

5. Với file __pycache__ / .pyc:
   → An toàn để xoá (Python tự sinh lại)
   → Nhưng vẫn grep `.pyc` hoặc `__pycache__` cho chắc

6. SAU KHI XOÁ: chạy compile check toàn bộ workspace + tabs
```

### ⚠️ GHI CHÚ QUAN TRỌNG:

- **`pgd_data/`** và **`data/qd/`** là **dữ liệu thật**, không phải rác
- **`cache/`** chứa file `.parquet` — được tạo từ `excel_to_parquet()`, xoá cache thì phải import lại từ Excel
- File `.db-shm` và `.db-wal` trong root SQLite — rác, an toàn để xoá
- File `__pycache__/` — an toàn để xoá (Python tự sinh lại)
- **Tuyệt đối không xoá bất kỳ file `.py` nào ở root mà chưa grep**

---

## 10. CÁC FILE LIÊN QUAN KHI TẠO TÍNH NĂNG MỚI

| Muốn làm gì | Cần đọc file nào |
|-------------|-----------------|
| Thêm KPI card | `components/delta_card.py` + workspace file |
| Xuất PDF | `components/export_pdf.py` (mới) hoặc `tabs/pdf_service.py` (cũ) |
| Xuất Excel | `services/excel_service.py` |
| Lọc dữ liệu | `components/filter_bar.py` |
| Xem chi tiết khoản vay | `components/loan_drawer.py` |
| Phân tích biến động | `components/movers.py` |
| Tab mới trong workspace | Pattern `CAC_NHOM` trong workspace file |
| Đọc dữ liệu | `data/__init__.py` → check function available |
| Format số/tiền | `utils.py` → `fmt_tien`, `fmt_ty`, `fmt_so`, `fmt_pct` |
| Phân quyền | `auth.py` → `is_cn_role`, `is_pgd_role`, `normalize_role` |
| Tên cột | `config.py` → tất cả `COT_*` |
| Cấu hình role | `config.py` → `ALL_ROLES`, `ROLE_MAP` |
| Chương trình KHTD | `config.py` → `CHUONG_TRINH_KHTD` |
| Tag mapping Word | `config.py` → `TAG_MAP`, `TAG_MAP_KLGB` |
| Danh sách PGD | `config.py` → `DS_PGD`, `DON_VI_CHI_NHANH` |
