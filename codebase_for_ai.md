# Codebase: VBSP-SCM

**Generated:** 2026-05-16 23:55:00

---

## 1. TỔNG QUAN

Hệ thống Quản trị Tín dụng Nội bộ cho **Ngân hàng Chính sách Xã hội Chi nhánh Đồng Nai** (đã sáp nhập Bình Phước 2025).

- **Stack:** Streamlit + Python + SQLite + DuckDB + PyArrow
- **Người dùng:** ~20 users, 9 vai trò
- **Phạm vi:** 22 đơn vị (Hội sở + 21 PGD), 95 xã/phường
- **Phân hệ:** 2 cấp — CN (Chi nhánh) + PGD (Phòng giao dịch)
- **Entry point:** `streamlit run app.py` → `http://localhost:8501`

---

## 2. CẤU TRÚC THƯ MỤC

```
├── app.py                     # Entry point; DuckDB read_parquet filter-pushdown theo PGD để giảm RAM
├── auth.py                    # 9-role RBAC, normalize_role()
├── config.py                  # MỌI hằng số: COT_*, DS_PGD, TAG_MAP, ROLE_MAP...
├── db.py                      # SQLite: kv_store, audit_log, users, baseline
├── pdf_service.py              # PDF export (root) — nhiều tabs/workspaces import trực tiếp
├── gen_dcgiam_sheet.py         # CLI: push dữ liệu GQVL giảm/điều chỉnh lên Google Sheet
├── utils.py                   # 20+ helper: fmt_so, fmt_tien, fmt_ty, fmt_pct...
├── snapshot_service.py        # HSTD snapshot versioning
├── alert_center.py            # Sidebar alerts (upload delay, inactive loans)
├── health_check.py            # System health monitoring
├── requirements.txt           # Python dependencies
├── Chay_VBSP_SCM.bat          # Launch script
│
├── data/                      # Data loading module
│   ├── __init__.py            # Re-exports all public functions
│   ├── core.py                # ts_file(), excel_to_parquet(), DuckDB aggregates
│   ├── hstd.py                # doc_file(), doc_file_nq11(), doc_file_gqvl()
│   ├── pgd.py                 # pgd_slug(), doc_hstd_pgd(), doc_nq11_pgd()
│   ├── khtd.py                # doc_khtd(), luu_khtd(), doc_cbtd()
│   ├── cdtotkvv.py            # CDTổ/TKVV data
│   ├── den_han.py             # Den han analysis
│   ├── dgd_helpers.py         # Transaction point helpers
│   └── giao_ban.py            # Giao ban data aggregation
│
├── components/                # Reusable UI components
│   ├── __init__.py
│   ├── delta_card.py          # kpi_row(), delta_card(), info_popover()
│   ├── export_pdf.py          # xuat_pdf_co_chart(), download_pdf_button()
│   ├── filter_bar.py          # filter_bar(), apply_filters()
│   ├── loan_drawer.py         # loan_detail_drawer()
│   └── movers.py              # movers_analysis()
│
├── services/                  # Business logic services
│   ├── __init__.py
│   ├── ct_discovery.py        # Program discovery by PGD
│   ├── data_priority.py       # Data priority management
│   ├── data_priority_service.py
│   ├── data_quality.py        # Data quality checks
│   ├── du_phong_service.py    # Forecasting service
│   ├── excel_service.py       # Excel export service
│   ├── hhi_service.py         # HHI analysis
│   ├── khtd_service.py        # KHTD assignment/adjustment
│   ├── kiem_soat_service.py   # Control/branch audit
│   ├── migration_service.py   # Data migration service
│   ├── period_compare.py      # Period comparison
│   ├── report_service.py      # Excel report generation
│   ├── template_service.py    # Word template rendering
│   ├── upload_center.py       # Centralized upload management
│   └── upload_service.py      # File upload handling
│
├── tabs/                      # 40+ tab modules
│   ├── __init__.py
│   ├── kiem_soat_service.py
│   ├── pdf_service.py         # Legacy PDF export (keep)
│   ├── tab_audit_log.py
│   ├── tab_ban_dai_dien.py
│   ├── tab_baocao.py
│   ├── tab_candoi.py
│   ├── tab_canh_bao_som.py
│   ├── tab_cbtd.py
│   ├── tab_cdtotkvv.py
│   ├── tab_cdtotkvv_pgd.py
│   ├── tab_checklist_bc.py
│   ├── tab_danhsach.py
│   ├── tab_den_han.py
│   ├── tab_diem_gd_pgd.py
│   ├── tab_gqvl.py
│   ├── tab_hhi.py
│   ├── tab_kehoach.py
│   ├── tab_kh_gqvl.py
│   ├── tab_khtd.py
│   ├── tab_khtd_giao_dc.py
│   ├── tab_khtd_mau07.py
│   ├── tab_khtd_nhap.py
│   ├── tab_khtd_pgd.py
│   ├── tab_khtd_xuat.py
│   ├── tab_kiem_soat.py
│   ├── tab_nhiem_vu.py
│   ├── tab_no_khoanh.py
│   ├── tab_no_rui_ro.py
│   ├── tab_nq11.py
│   ├── tab_qd62.py
│   ├── tab_quan_ly_dgd.py
│   ├── tab_so_sanh_ky.py
│   ├── tab_tien_do.py
│   ├── tab_tien_do_nop.py
│   ├── tab_tongquan.py
│   ├── tab_tracuu.py
│   ├── tab_trang_thai_nguon.py
│   ├── tab_upload_khnv.py
│   ├── tab_upload_pgd.py
│   ├── tab_uy_thac.py
│   └── tab_xlrr_tong_hop.py
│
├── workspaces/                # 3 workspaces (Phân hệ)
│   ├── __init__.py
│   ├── ws_operation.py        # PGD — Tác nghiệp
│   ├── ws_management.py       # Chi nhánh — Điều hành
│   └── ws_executive.py        # Lãnh đạo — Executive
│
├── widgets/                   # Sidebar widgets
│   ├── __init__.py
│   ├── data_source_status.py
│   └── status_widget.py
│
├── templates/                 # Word templates (.doc/.docx)
│   ├── 7064.06 - QĐ giao cua Truong BDD tinh.doc
│   ├── 7064.07 - Thong bao giao chi tieu KHTD UBND xa cho thon.doc
│   ├── 7064.08 - To trinh cua PGD de nghi dieu chinh KHTD.doc
│   ├── 7064.09 - To trinh cua tinh gui TBĐD de nghi dieu chinh KHTD.doc
│   ├── 7064.10 - To trinh cua tinh gui TGD de nghi dieu chinh KHTD.doc
│   ├── 722. Thông báo kết luận họp giao ban tháng.docx
│   ├── BB_giao_ban_xa_template.docx
│   ├── Bieu so 11 - Quyet dinh uy quyen.doc
│   ├── mau_06td.docx, Mau_To_trinh_vay_von.docx, MẪU 16TD_Template.docx
│   └── TEST_mau_06td_output.docx
│
├── tests/                     # Test suite
│   ├── fixtures.py
│   ├── test_pdf_service.py
│   └── test_smoke_snapshot.py
│
├── _archive/                  # Deprecated/backup files
│   ├── _tab_quantri_deprecated.py
│   ├── create_admin_pgd.py, seed_dgd_map.py
│   ├── tab_baocao_backup.py, tab_upload_pgd_fixed.py
│   └── test_*.py (10 test files)
│
├── khtd-targets-app/          # React app for KHTD targets
│   └── src/
│       ├── components/ (Card, TargetsTable, Toast, TopBar, Tree)
│       ├── pages/ (Home, ImportSheet, Targets)
│       └── api.js, main.js, state.js, utils.js
│
├── .streamlit/
│   └── config.toml
├── cache/                     # Parquet cache runtime (auto-create): hstd.parquet, nq11.parquet, gqvl.parquet...
├── pgd_data/                  # Upload theo từng PGD (runtime, có thể rỗng cho tới khi upload)
├── data/
│   ├── qd/                    # PDF Quyết định (tạo khi upload; có thể rỗng)
│   └── *.xlsx                 # Source Excel (HSTD/NQ11/GQVL/Điện báo/...)
├── assets/logo.png
├── logo.png, logo-vbsp.jpg
└── docs/                      # Documentation
    ├── ARCHITECTURE.md, CHANGELOG.md, CONVENTIONS.md
    ├── HUONG_DAN_*.md (6 files)
    ├── README.md, ROADMAP.md, ROLES.md
    ├── TEMPLATES.md, TROUBLESHOOTING.md, UI_GUIDELINES.md
    └── AGENTS.md
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

## 4. TẤT CẢ FUNCTION SIGNATURES

### 4.1 components/delta_card.py

```python
def kpi_row(cols: list[dict], num_columns: int = 4):
    """cols là list[dict], mỗi dict là kwargs cho delta_card()"""

def delta_card(
    label: str,
    value: str | float | int,
    delta: float | None = None,
    delta_label: str = "so với kỳ trước",
    delta_color: str = "normal",
    help: str | None = None,
    icon: str = "",
    suffix: str = "",
    precision: int = 0,
    key: str | None = None,
    use_container_width: bool = True,
):
```

### 4.2 components/export_pdf.py

```python
def download_pdf_button(
    pdf_bytes: bytes,
    filename: str = "bao_cao.pdf",
    label: str = "📥 Tải PDF",
    key: str | None = None,
):

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

def fig_to_bytes(fig: go.Figure, width=800, height=400) -> bytes | None:
def _tim_logo() -> str | None:
def _ve_header(elements, tieu_de, nguoi_xuat, usable_w):
```

### 4.3 components/filter_bar.py

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

### 4.4 components/loan_drawer.py

```python
def loan_detail_drawer(
    row: pd.Series | dict,
    title: str | None = None,
    extra_fields: list[tuple[str, str, str | None]] | None = None,
    field_configs: list[dict] | None = None,
):
```

### 4.5 components/movers.py

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
```

### 4.6 utils.py

```python
def fmt_so(x) -> str:           # Format số (dấu phẩy ngàn)
def fmt_tien(x) -> str:         # Format tiền (triệu đồng)
def fmt_ty(x) -> str:           # Format tiền (triệu đồng, cột bảng) — chia /1e6
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
def lay_config(key: str, fallback):
```

### 4.7 data/core.py

```python
def ts_file(fp: str) -> float:       # Timestamp file
def excel_to_parquet(excel_path, parquet_path, sheet, header, post_fn=None) -> pd.DataFrame:
def _duckdb_query(sql, params=None) -> pd.DataFrame:
def tong_hop_du_no_pgd(parquet_path) -> pd.DataFrame:
def dem_no_qua_han_pgd(parquet_path) -> pd.DataFrame:
def tong_hop_theo_xa(parquet_path, ten_pgd) -> pd.DataFrame:
```

### 4.8 data/hstd.py

```python
def doc_file(path=FILE_PATH) -> pd.DataFrame:           # HSTD
def doc_baseline(nam, _ts=0) -> pd.DataFrame | None:    # 31/12 baseline
def doc_baseline_pgd(ten_pgd, nam, _ts=0) -> pd.DataFrame | None:
def doc_baseline_merged(nam, _ts=0) -> pd.DataFrame | None:
def doc_file_nq11(path=FILE_PATH_NQ11) -> pd.DataFrame:  # NQ11
def doc_file_gqvl(path=FILE_PATH_GQVL) -> pd.DataFrame:   # GQVL
def doc_file_sk_gqvl(path=FILE_PATH_SK_GQVL) -> pd.DataFrame:
def doc_dienbao(path=FILE_PATH_DB) -> list:
def db_lookup(ma_kh) -> dict | None:
def db_nqh_con(df, ...) -> pd.DataFrame:
def danh_dau_khong_hd(df) -> pd.DataFrame:               # 3-month inactive
def danh_dau_khong_hd_cached(df) -> pd.DataFrame:
def tong_hop_khong_hd(df, nhom_theo) -> pd.DataFrame:
def tong_hop_khong_hd_cached(df, nhom_theo) -> pd.DataFrame:
def ds_chi_tiet_khong_hd(df, nhom_theo, gia_tri_nhom=None) -> pd.DataFrame:
def canh_bao_migration(df) -> pd.DataFrame:
def canh_bao_migration_cached(df) -> pd.DataFrame:
```

### 4.9 data/pgd.py

```python
def pgd_slug(ten_pgd) -> str:
def duong_dan_pgd(ten_pgd) -> Path:
def doc_hstd_pgd(ten_pgd) -> pd.DataFrame | None:
def doc_nq11_pgd(ten_pgd) -> pd.DataFrame | None:
def doc_hstd_toan_cn_pgd() -> pd.DataFrame | None:
def doc_nq11_toan_cn_pgd() -> pd.DataFrame | None:
```

### 4.10 auth.py

```python
def normalize_role(role) -> str:
def is_cn_role(role) -> bool:
def is_pgd_role(role) -> bool:
def la_phan_he_cn(role) -> bool:
def get_permissions(role, pgd_user=None) -> dict:
def get_tab_permissions(role) -> dict:
```

---

## 5. KIẾN TRÚC WORKSPACE

Mỗi workspace file có 1 hàm `render(**kwargs)` chính. kwargs gồm:
- `df`: DataFrame HSTD
- `df_nq11`: DataFrame NQ11
- `role`: Role người dùng
- `pgd_user`: PGD hiện tại (nếu là PGD role)

Pattern tab trong workspace:
```python
CAC_NHOM = {
    "nghiep_vu_pgd": {
        "label": "📋 Nghiệp vụ PGD",
        "tabs": [
            ("🔍 Tra cứu", lambda tab: tab_tracuu.render(tab, **kwargs)),
            ("📊 Danh sách", lambda tab: tab_danhsach.render(tab, **kwargs)),
        ],
    },
}

nhom_chon = st.radio("Chọn nhóm", ds_label, horizontal=True)
tabs_con = st.tabs(ten_tabs)
for i, tab_c in enumerate(tabs_con):
    with tab_c:
        renderers[i](tab_c)
```

---

## 6. KIẾN TRÚC XỬ LÝ DỮ LIỆU

```
Excel gốc (data/*.xlsx)
  → excel_to_parquet() — Convert → Parquet (PyArrow + zstd)
  → DuckDB query — Aggregate trực tiếp trên Parquet (lazy scan)
  → Streamlit render

Quy trình upload:
  Phòng KH-NV (tab_upload_khnv):
    → luu_file_he_thong() → merge_du_lieu_toan_cn() → cache/*.parquet
  PGD địa bàn (tab_upload_pgd):
    → luu_pgd_file() → pgd_data/{slug}/hstd_latest.xlsx
```

---

## 7. STREAMLIT CONFIG

```toml
[theme]
base = "light"
primaryColor = "#1565C0"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F4FF"
textColor = "#1A1A2E"
font = "sans serif"

[browser]
gatherUsageStats = false

[server]
headless = true
```

---

## 8. QUY TẮC CODE

### 8.1 Lưu trữ — CHỈ dùng kv_store

```python
value = db.doc_kv("key_name")           # đọc
db.ghi_kv("key_name", value, username)  # ghi
```

### 8.2 Audit log — BẮT BUỘC sau mọi thao tác ghi

```python
db.ghi_audit(username, "ten_action", "mô tả chi tiết")
```

### 8.3 Upload file — qua upload_service.py

```python
ket_qua = luu_pgd_file(ten_pgd, loai, file_bytes)   # 3 tham số
ket_qua.hien_thi()
```

### 8.4 Cache — xóa sau khi lưu thành công

```python
st.cache_data.clear()
```

### 8.5 Tiền tệ — quy ước 3 lớp

| Lớp | Đơn vị |
|---|---|
| Nhập liệu | Triệu đồng |
| Lưu trữ | VND (× 1.000.000) |
| Hiển thị | `fmt_ty()` chia `/1e6` → triệu đồng |

### 8.6 render(tab) — pattern fallback st.container()

```python
def render(tab=None, **kwargs):
    ctx = tab if tab is not None else st.container()
    with ctx:
        ...
```

---

## 9. THAM CHIẾU NHANH

| Yêu cầu | File |
|---|---|
| Thêm tab PGD | `tabs/tab_*.py` + `ws_operation.py` |
| Thêm tab toàn CN | `tabs/tab_*.py` + `ws_management.py` |
| Sửa merge 22 PGD | `upload_service.py` → `merge_du_lieu_toan_cn()` |
| Thêm chương trình TD | `config.py` → `CHUONG_TRINH_KHTD` |
| Thêm PGD mới | `config.py` → `DS_PGD`, `MA_PGD_MAP`, `PGD_XA_MAP` |
| Sửa format tiền | `utils.py` → `fmt_ty()` |
| Sửa đọc HSTD | `data/hstd.py` hoặc `data/core.py` |
| Thêm báo cáo kiểm soát | `kiem_soat_service.py` |
| Sửa giao KHTD | `khtd_service.py` + `tab_khtd_giao_dc.py` |
| Xuất PDF (docx2pdf) | `components/export_pdf.py` hoặc `pdf_service.py` (root) |
| Template Word | `services/template_service.py` |
| Filter + Drill-down | `components/filter_bar.py`, `components/loan_drawer.py` |
| Phân tích biến động | `components/movers.py` |
| Cảnh báo sidebar | `alert_center.py` → `render_alert_sidebar()` |
| Snapshot HSTD | `snapshot_service.py` |
| Quản lý điểm GD | `db.doc_dgd_map()` / `db.luu_dgd_map()` |

---

## 10. FILE ĐÃ DEPRECATED / LƯU TRỮ

| File | Lý do |
|---|---|
| `_archive/_tab_quantri_deprecated.py` | Tab quản trị cũ |
| `_archive/tab_baocao_backup.py` | Backup trước khi refactor |
| `_archive/test_*.py` | Test cũ, không dùng nữa |
| `_fix_all_buttons.py` | Script fix 1 lần — không chạy lại |
| `_fix_template_service.py` | Script fix 1 lần — không chạy lại |

---

## 11. LỖI THƯỜNG GẶP

| # | Lỗi | Đúng |
|---|---|---|
| 1 | `kpi_row(data, cols=4)` | `kpi_row(data, num_columns=4)` |
| 2 | `download_pfb_button(df=..., tieu_de=...)` | `download_pdf_button(pdf_bytes=xuat_pdf_co_chart(...))` |
| 3 | `loan_detail_drawer(df, row_id=0)` | `loan_detail_drawer(row=pd.Series(...))` |
| 4 | Hardcode tên cột tiếng Việt | Dùng `COT_*` từ config.py |
| 5 | `filter` là tên biến | Dùng `filters` (tránh built-in) |
| 6 | `COT_DIEN_THOAI` | `COT_SDT` |
| 7 | `COT_TEN_TKVV` | `COT_TEN_TO` |
