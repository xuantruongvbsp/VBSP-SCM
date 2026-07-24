# SIGNATURES — Tra cứu nhanh function signatures

> Tách từ rules.md + AGENTS.md để tiết kiệm token. Agent chỉ đọc khi cần gọi hàm.
> Luôn kiểm tra signature từ code gốc nếu có thể — file này chỉ để tra nhanh.

---

## Components

### delta_card.py
```python
# THAM SỐ: num_columns (KHÔNG phải cols)
def kpi_row(cols: list[dict], num_columns: int = 4): ...

def delta_card(
    label: str,
    value: str | float | int,
    delta: float | None = None,
    delta_label: str = "so với kỳ trước",
    delta_color: str = "normal",   # "normal"|"inverse"|"off"
    help: str | None = None,
    icon: str = "",
    suffix: str = "",
    precision: int = 0,
    key: str | None = None,
    use_container_width: bool = True,
): ...
```

### export_pdf.py
```python
# download_pdf_button nhận PDF bytes — không phải df
def download_pdf_button(
    pdf_bytes: bytes,
    filename: str = "bao_cao.pdf",
    label: str = "📥 Tải PDF",
    key: str | None = None,
): ...

def xuat_pdf_co_chart(
    df: pd.DataFrame,
    tieu_de: str,
    nguoi_xuat: str,
    figs: list[tuple[go.Figure, str]] | None = None,
    cols_tien: list[str] | None = None,
    don_vi_tien: str = "đồng",
    prefix_file: str = "",
    them_dong_tong: bool = True,
    them_ngay_xuat: bool = True,
) -> bytes: ...
```

### filter_bar.py
```python
def filter_bar(
    df: pd.DataFrame,
    filters: list[dict],    # [{"field": "Tên xã", "label": "Xã", "type": "select"}]
    key_prefix: str = "fb", # type: "select"|"multiselect"|"text"|"range"
    on_change: Callable | None = None,
    username: str = "",     # nếu có → hiện nút Lưu/Tải preset
) -> dict[str, Any]: ...

def apply_filters(df: pd.DataFrame, filter_values: dict) -> pd.DataFrame: ...
```

### loan_drawer.py
```python
# Nhận row (pd.Series | dict) — KHÔNG phải DataFrame
def loan_detail_drawer(
    row: pd.Series | dict,
    title: str | None = None,
    extra_fields: list[tuple[str, str, str | None]] | None = None,
    field_configs: list[dict] | None = None,
    username: str = "",
): ...
```

### movers.py
```python
def movers_analysis(
    df_curr: pd.DataFrame,
    df_prev: pd.DataFrame | None = None,
    top_n: int = 10,
    key_prefix: str = "mover",
    on_select_dimension: Callable | None = None,
    on_select_metric: Callable | None = None,
    show_title: bool = True,
): ...
```

---

## Utils (utils.py)

```python
def fmt_so(x) -> str: ...          # "1.234"
def fmt_tien(x) -> str: ...        # triệu đồng
def fmt_ty(x) -> str: ...          # "1.500" (triệu đồng, 0 số lẻ — không hậu tố "tỷ")
def fmt_pct(x) -> str: ...         # "12,34%"
def fmt(x) -> str: ...             # "1.234.567.890"
def vn(x, d=1, show_sign: bool = False): ...
def get_tab_context(tab): ...      # fallback st.container() khi tab=None
def hien_thi_dataframe_phan_trang(df, so_dong_moi_trang=500, key="df", **kwargs): ...
def xuat_excel(sheets: dict) -> bytes: ...
def auto_fill_document(data_row, template_path: str, tag_map: dict, extra: dict = None) -> bytes: ...
def auto_fill_batch(df_rows, template_path: str, tag_map: dict, extra: dict = None) -> bytes: ...
def auto_audit(action: str = "", clear_cache: bool = True): ...
def lazy_tabs(labels: list[str], renderers: list, key: str = "lt", horizontal: bool = True) -> None: ...
```

`pgd_slug()` ở `data/pgd.py` (không phải `utils.py`).

---

## Auth (auth.py)

```python
def normalize_role(role: str) -> str: ...      # "admin"→"admin_cn", "user"→"user_pgd"
def is_cn_role(role: str) -> bool: ...
def is_pgd_role(role: str) -> bool: ...
la_phan_he_cn = is_cn_role
la_phan_he_pgd = is_pgd_role

def la_executive(role: str) -> bool: ...
def la_admin_cn(role: str) -> bool: ...
def la_quan_ly_cn(role: str) -> bool: ...
def la_chuyen_vien_cn(role: str) -> bool: ...
def co_quyen_upload_pgd(role: str) -> bool: ...
def co_quyen_quan_ly_user_pgd(role: str) -> bool: ...
def co_quyen_giao_nhiem_vu(role: str) -> bool: ...
def get_permissions(role: str) -> dict: ...
```
