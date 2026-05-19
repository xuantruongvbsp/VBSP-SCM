# CONVENTIONS — VBSP-SCM

> Dành cho: AI coding tools (Trae, Cursor, Claude Code) và developer mới.  
> Mục đích: sinh code đúng convention ngay lần đầu, không lặp lại lỗi cũ.  
> Cập nhật: sau mỗi lần phát hiện lỗi mới (tra thêm từ CHANGELOG.md).

---

## PHẦN 1 — Các lỗi bị CẤM

### LỖI 1 — Role hardcode

```python
# ❌ SAI
if role == "admin":
if role in ["admin", "manager"]:

# ✅ ĐÚNG
from auth import normalize_role, la_phan_he_cn, la_phan_he_pgd
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

role = normalize_role(str(kwargs.get("role") or "user"))
if la_phan_he_cn(role): ...   # executive, admin_cn, manager_cn
if la_phan_he_pgd(role): ...  # admin_pgd, manager_pgd, user_pgd
```

---

### LỖI 2 — Tiền tệ sai đơn vị / tự format

```python
# ❌ SAI
tong / 1e9
tong / 1000000000
def _fmt(x): return f"{x/1e9:.3f}"   # tự định nghĩa

# ✅ ĐÚNG — quy ước 3 lớp bắt buộc
# Nhập liệu → triệu đồng (number_input)
# Lưu trữ  → VND nguyên (× 1_000_000 khi nhập)
# Hiển thị → fmt_ty(x)  (chia /1e12, ra chuỗi VN)

from utils import fmt_ty, fmt_tien, fmt_so
fmt_ty(gia_tri_vnd)      # → "1.234,560 tỷ"
fmt_tien(gia_tri_vnd)    # → "1.234 triệu"
```

> `fmt_ty` chia `/1e12` (không phải `/1e9`). Không dùng `NumberColumn` trong `st.dataframe` vì Streamlit hiển thị kiểu Mỹ.

---

### LỖI 3 — Tên cột hardcode

```python
# ❌ SAI
df["Dư nợ trong hạn"]
df["Tên PGD"]
df["Số điện thoại"]    # nhầm tên
df["Tên tổ TKVV"]     # cột không tồn tại

# ✅ ĐÚNG
from config import COT_DU_NO_TH, COT_TEN_PGD, COT_SDT, COT_TEN_TO
df[COT_DU_NO_TH], df[COT_TEN_PGD], df[COT_SDT], df[COT_TEN_TO]
```

**Alias sai thường gặp:**

| Sai | Đúng |
|---|---|
| `COT_DIEN_THOAI` | `COT_SDT` |
| `COT_TEN_TKVV` | `COT_TEN_TO` |
| `"PL NV"` (hardcode) | `COT_PL_NV` ("Phân loại NV") — đã rename khi merge |

---

### LỖI 4 — Kết nối DB trực tiếp

```python
# ❌ SAI
conn = sqlite3.connect("vbsp_scm.db")

# ✅ ĐÚNG
import db
conn = db.get_conn()   # threading.local, không dùng SQLAlchemy
```

---

### LỖI 5 — Ghi kv_store không có audit

```python
# ❌ SAI
db.ghi_kv(key, value, username)
# (không ghi audit)

# ✅ ĐÚNG
db.ghi_kv(key, value, username)
db.ghi_audit(username, "ten_action", "mô tả chi tiết")
```

---

### LỖI 6 — kwargs thiếu trong workspace

```python
# ❌ SAI — renderer không nhận đủ context
lambda tab: some_tab.render(tab)

# ✅ ĐÚNG — đầu _build_all_items() hoặc tương đương:
kwargs.setdefault("role", role)
kwargs.setdefault("username", username)
# Và truyền đầy đủ:
some_tab.render(tab, df=df, df_full=df_full, role=role, username=username, pgd_user=pgd_user)
```

---

### LỖI 7 — render() không dùng get_tab_context

```python
# ❌ SAI
def render(tab, **kwargs):
    with tab:   # crash khi tab=None

# ✅ ĐÚNG
from utils import get_tab_context
from auth import normalize_role, la_phan_he_cn

def render(tab=None, **kwargs):
    ctx = get_tab_context(tab)   # fallback st.container() khi tab=None
    with ctx:
        role     = normalize_role(str(kwargs.get("role") or "user"))
        username = kwargs.get("username") or st.session_state.get("username", "unknown")
        pgd_user = kwargs.get("pgd_user") or st.session_state.get("user_info", {}).get("pgd")
        la_cn    = la_phan_he_cn(role)
```

---

### LỖI 8 — Lưu dữ liệu ngoài kv_store

```python
# ❌ SAI
json.dump(data, open("data.json", "w"))
global cache_var; cache_var = data
pickle.dump(data, open("data.pkl", "wb"))

# ✅ ĐÚNG — mọi dữ liệu runtime đều qua kv_store
db.ghi_kv("key_name", value, username)
value = db.doc_kv("key_name")
```

---

### LỖI 9 — Không xóa cache sau khi ghi

```python
# ❌ SAI — UI hiển thị dữ liệu cũ sau khi lưu
db.ghi_kv(key, value, username)
st.success("Đã lưu")

# ✅ ĐÚNG
db.ghi_kv(key, value, username)
st.cache_data.clear()
st.success("Đã lưu")
```

> Sau upload file: `st.cache_data.clear()` chưa đủ nếu dùng `@st.cache_resource` — cần xóa thêm session_state keys liên quan.

---

## PHẦN 2 — Conventions tích cực

### Upload file — luôn đi qua upload_service.py

```python
from services.upload_service import luu_pgd_file, luu_file_he_thong, KetQuaUpload

ket_qua = luu_pgd_file(ten_pgd, loai, file_bytes)  # 3 tham số, không có username
ket_qua.hien_thi()
db.ghi_audit(username, "upload_hstd", f"{ten_pgd} — {loai}")  # audit thủ công sau đó
st.cache_data.clear()
```

---

### Format hiển thị — chỉ dùng hàm từ utils.py

| Dùng khi | Hàm | Ví dụ output |
|---|---|---|
| Số lượng / đếm | `fmt_so(x)` | `1.234` |
| Tiền (tỷ đồng) | `fmt_ty(x)` | `1.234,560 tỷ` |
| Tiền (triệu đồng) | `fmt_tien(x)` | `1.234 triệu` |
| Phần trăm | `fmt_pct(x)` | `12,34%` |
| Ngày tháng | `fmt_ngay(val)` | `31/12/2025` |
| Số nguyên thô | `fmt(x)` | `1.234.567.890` |

Trong `st.dataframe`: convert cột float → string bằng `.apply(fmt_ty)` — **không dùng `NumberColumn`**.

---

### kv_store key pattern

```
"khtd_cn"                   # KHTD cấp Chi nhánh (VND)
"khtd_pgd_{slug}"           # KHTD cấp PGD
"merge_meta_{loai}"         # loai = hstd / nq11 / gqvl
"ct_registry_{slug}"        # Danh mục chương trình theo PGD
"no_rui_ro_{slug}_{yyyy}_{mm}"  # Hồ sơ rủi ro theo PGD/kỳ
"config_pgd_xa_map"         # Mapping PGD → danh sách xã
```

`slug` = `pgd_slug(ten_pgd)` từ `data/pgd.py`.

---

### st.date_input — luôn có format

```python
# ❌ SAI — mặc định hiển thị kiểu YYYY/MM/DD
st.date_input("Ngày", value=datetime.today())

# ✅ ĐÚNG
st.date_input("Ngày", value=datetime.today(), format="DD/MM/YYYY")
```

---

### Widget key — tránh DuplicateElementKey

```python
# Khi hàm render được gọi 2 lần (CN + PGD mode):
key_prefix = "cn_" if la_cn else f"pgd_{pgd_slug(pgd_user)}_"
st.selectbox("PGD", options, key=f"{key_prefix}nrr_pgd")
st.button("Lưu",            key=f"{key_prefix}btn_luu")
```

---

### session_state với data_editor

```python
# ✅ ĐÚNG
changes = st.session_state.get(editor_key)
if changes:
    db.ghi_kv(key, data, username)
    db.ghi_audit(username, action, detail)
    st.cache_data.clear()
    st.session_state.pop(editor_key, None)  # reset stale state
    st.rerun()
```

---

### Tên đơn vị — dùng đúng constant

```python
from config import DON_VI_CHI_NHANH, TEN_CHI_NHANH_HIEN_THI

DON_VI_CHI_NHANH        # "Hội sở Chi nhánh tỉnh"  → dùng để LỌC df
TEN_CHI_NHANH_HIEN_THI  # "Chi nhánh NHCSXH tỉnh Đồng Nai" → dùng để HIỂN THỊ UI
```

---

## PHẦN 3 — Checklist trước khi sinh code

- [ ] Không có `role == "..."` hay `role in [...]` — dùng `la_phan_he_cn()` / `la_phan_he_pgd()`
- [ ] Không có `/1e9` hay tự định nghĩa `_fmt()` cho tiền tệ — dùng `fmt_ty()`
- [ ] Không có tên cột tiếng Việt hardcode — dùng `COT_*` từ config.py
- [ ] Không có `sqlite3.connect()` trực tiếp — dùng `db.get_conn()`
- [ ] Mọi `ghi_kv` đều có `ghi_audit` ngay sau
- [ ] Mọi `render()` đều có `get_tab_context(tab)` và `normalize_role()`
- [ ] Mọi `st.date_input` đều có `format="DD/MM/YYYY"`
- [ ] Sau khi lưu thành công: có `st.cache_data.clear()`
- [ ] Upload file đi qua `upload_service.py`, không hardcode đường dẫn
- [ ] Widget key có prefix unique khi hàm render được gọi nhiều lần

---

## PHẦN 4 — Khi không chắc

| Cần tra | Xem ở đâu |
|---|---|
| Tên cột | `config.py` phần `COT_*` |
| Function signatures | `STABLE.md` phần 4 |
| Lỗi đã gặp | `CHANGELOG.md` |
| Kiến trúc import | `ARCHITECTURE.md` |
| Phân quyền chi tiết | `ROLES.md` |

**Quy tắc vàng: hỏi lại trước khi tự suy luận — đừng đoán tên hàm hay tên cột.**
