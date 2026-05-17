# STABLE — VBSP-SCM
> Cập nhật khi: đổi stack, thêm role, đổi schema DB, thêm component mới
> Tần suất: vài tháng/lần

---

## 1. TỔNG QUAN HỆ THỐNG

Hệ thống Quản trị Tín dụng Nội bộ cho **Ngân hàng Chính sách Xã hội Chi nhánh Đồng Nai** (đã sáp nhập Bình Phước 2025).

- **Stack:** Streamlit + Python + SQLite + DuckDB + PyArrow
- **Người dùng:** ~20 users, 7 vai trò (2 cấp)
- **Phạm vi:** 22 đơn vị (Hội sở + 21 PGD), 95 xã/phường
- **Entry point:** `streamlit run app.py` → `http://localhost:8501`

---

## 2. HỆ THỐNG ROLE (2 CẤP, 7 ROLE)

### Cấp Chi nhánh → ws_management
| Role | Quyền |
|---|---|
| `executive` | Chỉ đọc dashboard |
| `admin_cn` | Toàn quyền |
| `manager_cn` | Upload + giao chỉ tiêu |
| `chuyenvien_cn` | Thao tác, không quản lý user |

### Cấp PGD → ws_operation
| Role | Quyền |
|---|---|
| `admin_pgd` | Upload HSTD + quản lý user PGD |
| `manager_pgd` | Upload HSTD + nhập kế hoạch |
| `user_pgd` | Tác nghiệp, chỉ thấy PGD mình |

### Legacy (backward-compatible)
`admin` → `admin_cn` | `manager` → `manager_cn` | `user` → `user_pgd`

### Hàm bắt buộc — KHÔNG so sánh role string trực tiếp
```python
from auth import normalize_role, la_phan_he_cn, la_phan_he_pgd
from auth import get_permissions, get_tab_permissions
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

# ✅ ĐÚNG
role = normalize_role(str(kwargs.get("role") or "user"))
if la_phan_he_cn(role): ...

# ❌ SAI
if role == "admin": ...
if role in ["admin", "manager"]: ...
```

---

## 3. TẤT CẢ COT_* CONSTANTS (config.py)

```python
# ── Core ──
COT_TEN_PGD      = "Tên PGD"
COT_MA_KH        = "Mã KH"
COT_TEN_KH       = "Tên KH"
COT_SO_KU        = "Số khế ước"
COT_NGAY_VAY     = "Ngày vay"
COT_NGAY_DH      = "Ngày ĐH theo Gia hạn"
COT_NGAY_DEN_HAN = COT_NGAY_DH
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

# ── Extended ──
COT_CMND              = "Số CMND"
COT_TEN_TO            = "Tên tổ"
COT_TEN_XA            = "Tên xã"
COT_TEN_THON          = "Tên thôn"
COT_NGUON_VON         = "Nguồn vốn"          # 1=TW, 2=ĐP
COT_MA_NHA_DAU_TU     = "Mã nhà đầu tư"
COT_MA_CHUONG_TRINH   = "Mã chương trình"
COT_TEN_HSSV          = "Họ tên HSSV"
COT_TEN_VC            = "Họ tên vợ/chồng"

# ── Risk/Activity ──
COT_LAI_TON     = "Lãi tồn TH"
COT_LAI_TON_QH  = "Lãi tồn QH"
COT_SO_DU_TG    = "Số dư tiền gửi 105"
COT_LAI_THANG   = "Lãi DT trong tháng"
COT_DVUT        = "Tên ĐVUT"
COT_PHAN_LOAI   = "Phân loại"
COT_NGAY_GDGN   = "Ngày giao dịch gần nhất"
```

---

## 4. FUNCTION SIGNATURES

### auth.py
```python
def normalize_role(role) -> str
def is_cn_role(role) -> bool
def is_pgd_role(role) -> bool
def la_phan_he_cn(role) -> bool
def la_phan_he_pgd(role) -> bool
def get_permissions(role, pgd_user=None) -> dict
def get_tab_permissions(role) -> dict
def co_quyen_upload_pgd(role) -> bool
def co_quyen_quan_ly_user_pgd(role) -> bool
```

### utils.py
```python
def fmt_so(x) -> str           # Format số (dấu phẩy ngàn)
def fmt_tien(x) -> str         # Format tiền (triệu đồng)
def fmt_ty(x) -> str           # Format tiền (tỷ đồng) — chia /1e12
def fmt_pct(x) -> str          # Format % (2 chữ số)
def fmt(x) -> str              # Format số tổng quát
def fmt_ngay(val) -> str       # Format ngày dd/mm/yyyy
def fmt_bang_ty(x, so_le=0) -> str
def fmt_cl(x) -> str
def fmt_tl(th, kh) -> str
def vn(x, d=1, show_sign=False) -> str
def norm_col_header(s: str) -> str
def hien_thi_dataframe_phan_trang(df, so_dong_moi_trang=500, key="df", **kwargs)
def format_df_vn(df: pd.DataFrame) -> pd.DataFrame
def xuat_excel(sheets: dict) -> bytes
def ten_file_xuat(prefix: str, ext="xlsx") -> str
def auto_fill_document(data_row, template_path, tag_map, ...)
def lay_config(key: str, fallback)
def get_tab_context(tab)        # fallback st.container() nếu tab=None
```

### db.py
```python
def get_conn() -> sqlite3.Connection   # threading.local(), không dùng SQLAlchemy
def doc_kv(key: str, default=None)
def ghi_kv(key: str, value, username: str)
def list_kv_prefix(prefix: str) -> list[str]
def doc_kv_prefix(prefix: str) -> dict[str, Any]
def doc_kv_nhieu(keys: list[str]) -> dict[str, Any]
def doc_kv_history(key: str, limit: int = 10) -> list[dict]
def ghi_audit(username: str, action: str, detail: str)
```

### data/core.py
```python
def ts_file(fp: str) -> float
def excel_to_parquet(excel_path, parquet_path, sheet, header, post_fn=None) -> pd.DataFrame
def tong_hop_du_no_pgd(parquet_path) -> pd.DataFrame
def dem_no_qua_han_pgd(parquet_path) -> pd.DataFrame
def tong_hop_theo_xa(parquet_path, ten_pgd) -> pd.DataFrame
```

### data/hstd.py
```python
def doc_file(path=FILE_PATH) -> pd.DataFrame
def doc_baseline(nam, _ts=0) -> pd.DataFrame | None
def doc_baseline_pgd(ten_pgd, nam, _ts=0) -> pd.DataFrame | None
def doc_file_nq11(path=FILE_PATH_NQ11) -> pd.DataFrame
def doc_file_gqvl(path=FILE_PATH_GQVL) -> pd.DataFrame
def danh_dau_khong_hd(df) -> pd.DataFrame
def canh_bao_migration(df) -> pd.DataFrame
```

### data/pgd.py
```python
def pgd_slug(ten_pgd) -> str
def duong_dan_pgd(ten_pgd) -> Path
def doc_hstd_pgd(ten_pgd) -> pd.DataFrame | None
def doc_nq11_pgd(ten_pgd) -> pd.DataFrame | None
def doc_hstd_toan_cn_pgd() -> pd.DataFrame | None
def doc_nq11_toan_cn_pgd() -> pd.DataFrame | None
```

### components/delta_card.py
```python
def kpi_row(cols: list[dict], num_columns: int = 4)
def delta_card(label, value, delta=None, delta_label="so với kỳ trước",
               delta_color="normal", help=None, icon="", suffix="",
               precision=0, key=None, use_container_width=True)
```

### components/filter_bar.py
```python
def filter_bar(df, filters: list[dict], key_prefix="fb", on_change=None) -> dict
# filters = [{"field": "Tên xã", "label": "Xã", "type": "select"}, ...]
# type: "select" | "multiselect" | "text" | "range"
def apply_filters(df, filter_values: dict) -> pd.DataFrame
```

### components/export_pdf.py
```python
def download_pdf_button(pdf_bytes, filename="bao_cao.pdf", label="📥 Tải PDF", key=None)
def xuat_pdf_co_chart(df, tieu_de, nguoi_xuat, figs=None, cols_tien=None,
                      don_vi_tien="đồng", prefix_file="",
                      them_dong_tong=True, them_ngay_xuat=True) -> bytes
```

### components/loan_drawer.py
```python
def loan_detail_drawer(row: pd.Series | dict, title=None,
                       extra_fields=None, field_configs=None)
```

### services/upload_service.py
```python
def luu_pgd_file(ten_pgd, loai, file_bytes) -> KetQuaUpload
def luu_file_he_thong(loai, file_bytes) -> KetQuaUpload
def luu_dienbao(file_bytes) -> KetQuaUpload
def merge_du_lieu_toan_cn()    # auto-trigger sau upload HSTD/NQ11/GQVL
# KetQuaUpload.hien_thi()     # hiển thị kết quả upload
```

---

## 5. QUY TẮC CODE

### Lưu trữ — CHỈ dùng kv_store
```python
value = db.doc_kv("key_name")
db.ghi_kv("key_name", value, username)
```

### kv_store key conventions
```
"khtd_cn"                        # KHTD cấp CN (VND)
"khtd_pgd_{slug}"                # KHTD cấp PGD
"merge_meta_{loai}"              # hstd / nq11 / gqvl
"ct_registry_{slug}"             # Danh mục chương trình theo PGD
"config_pgd_xa_map"              # Mapping PGD → danh sách xã
```

### Audit log — BẮT BUỘC sau mọi thao tác ghi
```python
db.ghi_audit(username, "ten_action", "mô tả chi tiết")
```

### Upload — qua upload_service.py
```python
ket_qua = luu_pgd_file(ten_pgd, loai, file_bytes)
ket_qua.hien_thi()
```

### Cache — xóa sau khi lưu thành công
```python
st.cache_data.clear()
```

### Tiền tệ — quy ước 3 lớp
| Lớp | Đơn vị |
|---|---|
| Nhập liệu | Triệu đồng |
| Lưu trữ | VND (× 1.000.000) |
| Hiển thị | `fmt_ty()` — KHÔNG dùng `/1e9` |

### render(tab) — pattern chuẩn
```python
def render(tab=None, **kwargs):
    ctx = get_tab_context(tab)   # utils.py — fallback st.container()
    with ctx:
        role = normalize_role(str(kwargs.get("role") or "user"))
        username = kwargs.get("username") or st.session_state.get("username", "unknown")
        pgd_user = kwargs.get("pgd_user") or st.session_state.get("user_info", {}).get("pgd")
        la_cn = la_phan_he_cn(role)
        perms = get_permissions(role)
```

---

## 6. STREAMLIT CONFIG (.streamlit/config.toml)

```toml
[theme]
base = "light"
primaryColor = "#1565C0"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F4FF"
textColor = "#1A1A2E"
font = "sans serif"

[server]
headless = true
```

---

## 7. LỖI THƯỜNG GẶP

| # | Sai | Đúng |
|---|---|---|
| 1 | `kpi_row(data, cols=4)` | `kpi_row(data, num_columns=4)` |
| 2 | `download_pfb_button(df=..., tieu_de=...)` | `download_pdf_button(pdf_bytes=xuat_pdf_co_chart(...))` |
| 3 | `loan_detail_drawer(df, row_id=0)` | `loan_detail_drawer(row=pd.Series(...))` |
| 4 | Hardcode tên cột tiếng Việt | Dùng `COT_*` từ config.py |
| 5 | `filter` là tên biến | Dùng `filters` (tránh built-in) |
| 6 | `COT_DIEN_THOAI` | `COT_SDT` |
| 7 | `COT_TEN_TKVV` | `COT_TEN_TO` |
| 8 | `role == "admin"` | `normalize_role(role)` + helper functions |
| 9 | `/1e9` cho tiền tệ | `/1e12` qua `fmt_ty()` |
