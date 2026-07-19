# AGENTS.md — VBSP-SCM
> Hướng dẫn dự án dành riêng cho **Codex** / Trae / Cline / Cursor.  
> Đọc toàn bộ file này trước khi đọc bất kỳ file code nào.  
> Cập nhật: 06/06/2026

---

## 1. Dự án là gì

Hệ thống Quản trị Tín dụng Nội bộ — **Ngân hàng Chính sách Xã hội Chi nhánh Đồng Nai**  
(đã sáp nhập Bình Phước 2025).

- **Stack:** Streamlit + Python + SQLite + PyArrow/Parquet
- **Chạy:** `venv\Scripts\python.exe -m streamlit run app.py --server.port 8502` → `http://localhost:8502`
- **Python chuẩn:** `D:\VBSP-SCM\venv\Scripts\python.exe` (Python 3.12)
- **Không dùng:** `D:\VBSP-SCM\.venv` / `.venv*` vì đây là môi trường cũ Python 3.14, dễ làm IDE/agent probe nhầm và gây cửa sổ CMD chớp
- **Người dùng:** ~20 users, 9 vai trò, 2 phân hệ
- **Phạm vi:** 22 đơn vị (Hội sở + 21 PGD), 95 xã/phường

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

## 3. Bản đồ file — đọc cái gì trước khi sửa cái gì

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
| Xử lý Rủi ro | `tab_xu_ly_rui_ro.py` + `services/xlrr_service.py` | File đó |
| Tiến độ Báo cáo PGD (GSheet) | `tabs/tab_tien_do_nop.py` + Google Form | Tab đó; credentials ở `credentials.json` |
| Upload file | `services/upload_service.py` | `luu_pgd_file()` / `luu_file_he_thong()` |
| Dữ liệu kv_store | `db.py` | `doc_kv()` / `ghi_kv()` |
| Thêm tab PGD | `tabs/tab_*.py` + `ws_operation.py` | File đó |
| Thêm tab toàn CN | `tabs/tab_*.py` + `ws_management.py` | File đó |
| Thêm chương trình TD | `config.py` | `CHUONG_TRINH_KHTD` |
| Thêm PGD mới | `config.py` | `DS_PGD`, `MA_PGD_MAP`, `PGD_XA_MAP` |
| Sửa format tiền | `utils.py` | `fmt_ty()` |
| Thêm báo cáo kiểm soát | `kiem_soat_service.py` | Thêm `BaoCaoMeta` |
| Sửa giao KHTD | `khtd_service.py` + `tab_khtd_giao_dc.py` | File đó |
| Sửa số liệu giao ban | `giao_ban.py` | `tinh_so_lieu_van_xuoi()` |
| Xuất Thông báo Kết luận Giao ban | `giao_ban.py` | `xuat_thong_bao_ket_luan_giao_ban()` |
| Snapshot HSTD theo kỳ | `snapshot_service.py` | upsert-safe, tự trigger sau merge |
| Tab Ban Đại Diện | `tab_ban_dai_dien.py` | Tham số `cap="tinh"` (CN) / `cap="xa"` (PGD) |

---

## 4. Luồng dữ liệu — PHẢI hiểu trước khi sửa

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

Snapshot (snapshot_service.py):
  → chạy tự động sau merge thành công
  → ghi vào bảng hstd_snapshot (db.py)
  → nền tảng cho risk heatmap, báo cáo Word/PDF tự động

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

Google Sheets → tab_tien_do_nop:
  PGD nộp Google Form
    → Google Sheets TIENDO_BAOCAO (Sheet ID: 15Ev2r...)
    → tab_tien_do_nop.py doc qua gspread (cache 5 phút)
    → Tab: Hướng dẫn | Cài đặt deadline | Tổng quan | Danh sách
    → credentials.json (Service Account, KHÔNG commit)
```

---

## 5. Quy tắc BẮT BUỘC — vi phạm = code sai

### 5.1 Lưu dữ liệu — CHỈ dùng kv_store

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
| `no_rui_ro_{slug}_{yyyy}_{mm}` | Hồ sơ rủi ro theo PGD/kỳ (cũ — deprecated) |
| `xlrr_pgd_{slug}_{yyyy}_{mm}` | Hồ sơ XLRR PGD lập theo kỳ |
| `xlrr_cn_{yyyy}_{mm}` | Hồ sơ XLRR CN tổng hợp theo kỳ |
| `qd62_cn_{yyyy}_{mm}` | Hồ sơ QĐ62 CN theo kỳ |
| `xlrr_ket_qua_{yyyy}_{mm}` | Kết quả XLRR từ NHCSXH TW theo kỳ |
| `kehoach` | KH Điện báo toàn CN |
| `kehoach_pgd_{slug}` | KH Điện báo từng PGD |
| `dgd_map` | Điểm giao dịch toàn CN |
| `kh_gqvl_cn_{nam}` | KH GQVL Chi nhánh |
| `kh_gqvl_pgd_{slug}_{nam}` | KH GQVL theo PGD (dự phòng) |
| `khnv_phan_cong_list` | Phân công cán bộ nội bộ Phòng KH-NV |
| `khnv_lich_list` | Lịch công tác Phòng KH-NV |
| `bao_cao_deadline_config` | Deadline từng loại BC `{loai: "YYYY-MM-DD"}` — dùng trong `tab_tien_do_nop.py` |

`slug` = `pgd_slug(ten_pgd)` từ `data/pgd.py`.

---

### 5.2 Audit log — BẮT BUỘC sau MỌI thao tác ghi

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

### 5.3 Upload file — LUÔN qua upload_service.py

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

### 5.4 Tiền tệ — quy ước 3 lớp

| Lớp | Đơn vị | Ghi chú |
|---|---|---|
| Nhập liệu | Triệu đồng | `number_input` hiển thị triệu |
| Lưu trữ | VND (`× 1_000_000`) | Ghi vào kv_store / DataFrame |
| Hiển thị (bảng) | `fmt_ty()` | Chia `/1e6` → **triệu đồng**, header cột phải ghi "(triệu đồng)" |
| Hiển thị (metric/card) | `vn(x / 1e9, 3) + " tỷ"` | Chia `/1e9` → **tỷ đồng** inline |

```python
from utils import fmt, fmt_tien, fmt_ty, fmt_pct, fmt_so

fmt_ty(gia_tri_vnd)                 # → "1.235" (triệu đồng, dùng cho cột bảng có header "(triệu đồng)")
vn(gia_tri_vnd / 1e9, 3) + " tỷ"  # → "1,235 tỷ" (metric/card inline) ← chuẩn VN
fmt(gia_tri_vnd)                   # → "1.234.567.890"
fmt_so(so_luong)                   # → "1.234"
```

**Quy tắc format số — LUÔN dùng kiểu Việt Nam:**

| Loại | Dùng | Ví dụ |
|---|---|---|
| Tiền tệ (cột bảng) | `fmt_ty(x)` | `1.235` (triệu đồng, 0 số lẻ, header cột ghi "(triệu đồng)") |
| Số lượng | `fmt_so(x)` | `1.234` |
| Phần trăm | `f"{x:.2f}".replace(".", ",") + "%"` | `12,34%` |
| **KHÔNG dùng** | `NumberColumn(format="%.3f")` | ~~`1,234.560`~~ (kiểu Mỹ) |

**Trong `st.dataframe`:** Chuyển cột float → string bằng `.apply(fmt_ty)` trước khi hiển thị — **không dùng `NumberColumn`** cho cột tiền tệ vì Streamlit luôn hiển thị kiểu Mỹ.

---

### 5.5 Phân quyền — KHÔNG check role bằng chuỗi thô

```python
# ❌ SAI — thiếu role mới
if role not in ("admin", "manager", "user"):
    ...

# ✅ ĐÚNG — dùng hàm từ auth.py
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

role = normalize_role(role)   # luôn normalize trước

if la_phan_he_cn(role):       # executive, admin_cn, manager_cn, admin, manager, chuyenvien_cn
if la_phan_he_pgd(role):      # admin_pgd, manager_pgd, user_pgd, user
if co_quyen_upload_pgd(role): # admin_pgd, manager_pgd
```

**Bảng role đầy đủ:**

| Role | Phân hệ | Quyền chính |
|---|---|---|
| `executive` | CN | Chỉ đọc dashboard |
| `admin_cn` / `admin` | CN | Toàn quyền |
| `manager_cn` / `manager` | CN | Upload, giao chỉ tiêu |
| `chuyenvien_cn` | CN | Tác nghiệp CN (không có quyền upload) |
| `admin_pgd` | PGD | Upload + quản lý user PGD |
| `manager_pgd` | PGD | Upload + nhập kế hoạch |
| `user_pgd` / `user` | PGD | Tác nghiệp, chỉ thấy PGD mình |

---

### 5.6 Tên đơn vị — dùng đúng constant

```python
from config import DON_VI_CHI_NHANH, TEN_CHI_NHANH_HIEN_THI

DON_VI_CHI_NHANH       = "Hội sở Chi nhánh tỉnh"             # dùng để LỌC df
TEN_CHI_NHANH_HIEN_THI = "Chi nhánh NHCSXH tỉnh Đồng Nai"   # dùng để HIỂN THỊ UI

# KHÔNG hardcode "PGD Biên Hòa" để lọc df — dùng DON_VI_CHI_NHANH
```

---

### 5.7 Widget key — tránh DuplicateElementKey

```python
# Khi 1 hàm render được gọi nhiều lần (CN mode + PGD mode),
# mọi st.* key phải có prefix riêng

# Pattern chuẩn:
key_prefix = "cn_"    # hoặc f"pgd_{pgd_slug(pgd_user)}_"
st.selectbox("PGD", options, key=f"{key_prefix}nrr_pgd")
st.button("Lưu",            key=f"{key_prefix}btn_luu")
```

---

### 5.8 pgd_mode — pattern song song 2 phân hệ

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

---

### 5.9 CSS & UI

- Inject CSS **một lần** trong `app.py` — không inject trong tab
- Bảng ≥ 8 cột → HTML thuần + `st.html(html_str)` (Streamlit ≥1.36) hoặc `st.markdown(html_str, unsafe_allow_html=True)` (cũ hơn)
- Màu sắc → xem `UI_GUIDELINES.md`
- HTML: **KHÔNG** hardcode `color:black` / `background:white` — dùng CSS variable tương thích dark mode
- `st.date_input` bắt buộc có `format="DD/MM/YYYY"`

---

### 5.10 Git — LUÔN làm việc tại worktree gốc

- **LUÔN** sửa file tại `D:/VBSP-SCM` (worktree gốc, branch `main`)
- **KHÔNG** sửa trong worktree phụ (`Codex/...`) — thay đổi sẽ không hiện trong GitHub Desktop
- Sau mỗi lần sửa: chạy `git status` tại `D:/VBSP-SCM` để xác nhận file đã modified
- **TUYỆT ĐỐI KHÔNG tự `git commit` hay `git push`** — người dùng tự commit qua GitHub Desktop
- **TUYỆT ĐỐI KHÔNG chạy `git add`** trừ khi người dùng yêu cầu rõ ràng
- Nếu đang ở worktree phụ: hỏi người dùng trước, đề xuất sửa tại `D:/VBSP-SCM`

---

### 5.11 Chọn model — theo mức độ quan trọng

| Mức độ | Tool | Model | Giá | Khi nào |
|---|---|---|---|---|
| Thấp | Trae | V4 Flash | rẻ nhất | Đọc, tìm, fix nhỏ, đổi label |
| Trung bình | Trae | V4 Pro | rẻ | Viết tính năng, tabs/, services/ |
| Cao | Trae | R1 | rẻ | Kiến trúc, debug logic khó |
| Quan trọng | Codex Desktop | Haiku 4.5 | $1/M | auth.py, ws_*.py, phân quyền, Trae fail |
| Rất quan trọng | Codex Desktop | Sonnet 4.6 | $3/M | db.py, migration |
| Cực quan trọng | Codex Desktop | Opus 4.6 | $5/M | Tính năng ảnh hưởng toàn hệ thống |

**Quy tắc chọn tool:**
- Sai thì chỉ ảnh hưởng UI → Trae
- Sai thì ảnh hưởng toàn bộ user/session → Codex Desktop Haiku
- Sai thì mất dữ liệu → Codex Desktop Sonnet/Opus
- Trae fail apply (không thấy edit_file_search_replace + status: success) → Codex Desktop Haiku ngay

**Quy tắc leo model:**
- Trae: Flash → Pro → R1
- Codex Desktop: Haiku → Sonnet → Opus
- Chỉ leo khi model nhẹ không đủ khả năng

---

### 5.12 Không thêm dependency mới

Trước khi dùng thư viện mới, kiểm tra đã có trong codebase:
- `pandas`, `openpyxl`, `pyarrow` — có
- `python-docx`, `docx2pdf` — có
- `streamlit`, `duckdb` — có
- `concurrent.futures`, `threading` — có (stdlib)

---

### 5.13 Tên cột — dùng COT_* từ config.py

```python
# ✅ ĐÚNG — dùng hằng số từ config.py
df[COT_TONG_DU_NO]    # ✅
df["Tổng dư nợ"]      # ❌

# Các COT_* phổ biến:
COT_TEN_PGD      = "Tên PGD"         COT_MA_KH         = "Mã KH"
COT_TEN_KH       = "Tên KH"          COT_SO_KU         = "Số khế ước"
COT_NGAY_VAY     = "Ngày vay"        COT_NGAY_DH       = "Ngày ĐH theo Gia hạn"
COT_DU_NO_TH     = "Dư nợ trong hạn" COT_DU_NO_QH      = "Dư nợ quá hạn"
COT_TONG_DU_NO   = "Tổng dư nợ"      COT_DU_NO_KHOANH  = "Dư nợ khoanh"
COT_TEN_CT       = "Tên chương trình" COT_TEN_XA       = "Tên xã"
COT_TEN_TO       = "Tên tổ"          COT_NGAY_SL       = "Ngày số liệu"
COT_SDT          = "Số điện thoại"   COT_CMND          = "Số CMND"
COT_TEN_NHA_DAU_TU = "Tên nhà đầu tư" COT_TEN_TO_TRUONG = "Tên tổ trưởng"

# Xem đầy đủ tại config.py — KHÔNG hardcode tên cột tiếng Việt
```

---

### 5.14 Auth functions — Tham chiếu nhanh

```python
from auth import (
    normalize_role,                  # "admin"→"admin_cn", "user"→"user_pgd"
    la_phan_he_cn,                   # executive/admin_cn/manager_cn/admin/manager/chuyenvien_cn
    la_phan_he_pgd,                  # admin_pgd/manager_pgd/user_pgd/user
    la_executive,
    la_admin_cn,
    la_chuyen_vien_cn,
    co_quyen_upload_pgd,             # admin_pgd, manager_pgd
    co_quyen_quan_ly_user_pgd,       # admin_pgd
    co_quyen_giao_nhiem_vu,
    get_permissions,                 # → dict
)
```

---

### 5.15 Error logging — KHÔNG nuốt lỗi

```python
from logger import get_logger
logger = get_logger(__name__)

try:
    xu_ly_gi_do()
except Exception as e:
    logger.error("ten_ham: mo_ta — %s", e, exc_info=True)
    st.error(f"❌ Lỗi: {e}")
# KHÔNG: except Exception: pass
# KHÔNG: except Exception as e: print(e)
```

---

### 5.16 DuckDB — LUÔN kiểm tra schema trước khi query

```python
import duckdb, pyarrow.parquet as pq

# PHẢI kiểm tra schema trước khi query
schema = pq.read_schema(CACHE_HSTD)
cols = [f.name for f in schema]
if "Ten_ct" not in cols:
    st.warning("⚠️ Parquet thiếu cột Ten_ct")
    return

# Sau đó mới query
df = duckdb.query(f"SELECT ... FROM '{CACHE_HSTD}'").df()
```

---

## 6. Pattern chuẩn khi tạo tab mới

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


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    # 1. Giải kwargs — luôn theo thứ tự này
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")

    # 2. Tab context — fallback st.container() khi tab=None
    ctx = tab if tab is not None else st.container()
    with ctx:
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

> ⚠️ **KHÔNG viết `with tab:` trực tiếp** — tab có thể là `None` khi gọi standalone.

---

## 7. Các lỗi hay gặp và cách fix

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
agg_dict = {"Tổng_dư_nợ": (COT_TONG_DU_NO, "sum")}
if "Tổng giải ngân" in df.columns:
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

**Nguyên nhân:** Hàm helper lồng trong `render()`.

**Fix:** Nâng lên module-level với đủ tham số cần thiết.

---

### `luu_pgd_file` báo lỗi `username` không hợp lệ

**Nguyên nhân:** Hàm chỉ nhận 3 tham số `(ten_pgd, loai, file_bytes)` — không có `username`.

**Fix:** Gọi `db.ghi_audit()` thủ công sau khi `luu_pgd_file()` trả về.

---

## 8. Function Signatures — Components

### delta_card.py
```python
# ⚠️ THAM SỐ: num_columns (KHÔNG phải cols)
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
# ⚠️ download_pdf_button nhận PDF BYTES — không phải df, tieu_de
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
    on_change=None,
) -> dict: ...              # {field: value} — None = "Tất cả"

def apply_filters(df: pd.DataFrame, filter_values: dict) -> pd.DataFrame: ...
```

### loan_drawer.py
```python
# ⚠️ Nhận ROW (pd.Series | dict) — KHÔNG phải DataFrame
def loan_detail_drawer(
    row: pd.Series | dict,
    title: str | None = None,
    extra_fields: list[tuple] | None = None,
    field_configs: list[dict] | None = None,
): ...
```

### movers.py
```python
def movers_analysis(
    df_curr: pd.DataFrame,
    df_prev: pd.DataFrame | None = None,
    top_n: int = 10,
    key_prefix: str = "mover",
    on_select_dimension=None,
    on_select_metric=None,
    show_title: bool = True,
): ...
```

---

 Checklist trước khi sửa

```
□ ĐỌC BUGMAP.md — kiểm tra section liên quan đến file/thao tác sắp sửa để tránh lặp lỗi cũ
□ Đọc file cần sửa (view toàn bộ hoặc phần liên quan)
□ Xác định hàm/dòng cụ thể sẽ thay đổi
□ Kiểm tra hàm nào đang gọi hàm đó (grep ngược)
□ Sau khi sửa: có dùng db.ghi_audit() chưa?
□ Sau khi sửa: có gọi st.cache_data.clear() chưa (nếu ghi file)?
□ Widget key có unique không?
□ Tiền tệ: lưu VND hay triệu? Hiển thị fmt_ty() hay fmt()?
□ Role check: dùng la_phan_he_cn() hay check chuỗi thô?
□ normalize_role(role) trước khi check role
□ render(tab=None, **kwargs) với fallback st.container()
□ Convention check (nếu task có sửa code logic/UI):
  python scripts/check_conventions.py path/to/file.py
□ len(tab_names) == len(_tab_renderers) nếu sửa ws_*.py
□ prefix widget unique khi pgd_mode=True
□ st.date_input có format="DD/MM/YYYY"
□ DuckDB: check schema parquet trước khi query (5.16)
□ HTML: KHÔNG hardcode color:black/background:white (dark mode)
```

---

## 9. Sau mỗi lần apply — CẬP NHẬT CHANGELOG.md

Thêm entry mới lên **ĐẦU FILE** `CHANGELOG.md` (ngay sau dòng `# CHANGELOG`):

```
## [YYYY-MM-DD] — <mô tả ngắn task>
- `filename.py` dòng ~X — mô tả thay đổi
- `filename2.py` — mô tả thay đổi
```

**Quy tắc:** dùng ngày thực tế, mỗi file thay đổi = 1 dòng, KHÔNG xóa entry cũ, áp dụng cho MỌI thay đổi kể cả fix nhỏ.

### 9.1 Sau mỗi lần fix bug — CẬP NHẬT BUGMAP.md

Mỗi khi fix bug, thêm entry vào `BUGMAP.md` theo template có sẵn (cuối file):

- Phân loại đúng section: A. Parquet, B. Streamlit UI, C. DataFrame, D. Database, E. Upload, F. PDF/Word, G. KHTD, H. GSheet, I. Role, J. Code Pattern
- Nếu là dạng lỗi mới chưa có section → tạo section mới
- Format: `### XX — [Tên lỗi]` với bảng `| | |` gồm: File, Dấu hiệu, Nguyên nhân, Fix, Ngày fix

---

## 10. Tham chiếu nhanh

| Yêu cầu | Hàm / File |
|---|---|
| Slug từ tên PGD | `pgd_slug(ten_pgd)` — `data/pgd.py` |
| Đường dẫn file PGD | `duong_dan_pgd(ten_pgd, loai)` — `data/pgd.py` |
| Format tiền tệ | `fmt()`, `fmt_ty()`, `fmt_so()` — `utils.py` |
| Hiển thị bảng phân trang | `hien_thi_dataframe_phan_trang(df, key=...)` — `utils.py` |
| Xuất Excel nhiều sheet | `xuat_excel({"Sheet1": df1, "Sheet2": df2})` — `utils.py` |
| Fill hợp đồng Word | `auto_fill_document(data_row, template_path, tag_map, output_path)` — `utils.py` |
| Fill hàng loạt | `auto_fill_batch(df_rows, template_path, tag_map, ...)` — `utils.py` |
| Ghi audit log tự động | `auto_audit(action, clear_cache=True)` — `utils.py` |
| Lazy loading tabs | `lazy_tabs(labels, renderers, key="lt")` — `utils.py` |
| Nút tải Word + PDF | `nut_tai_word_va_pdf(docx_bytes, ten_file, key)` — `template_service.py` |
| Đọc kv_store nhiều key | `db.doc_kv_prefix("prefix_")` — `db.py` |
| Gộp 22 PGD | `merge_du_lieu_toan_cn(loai)` — `upload_service.py` |
| Metadata merge | `lay_meta_merge(loai)` — `upload_service.py` |
| Kiểm tra quyền upload | `co_quyen_upload_pgd(role)` — `auth.py` |
| Quản lý điểm GD | `db.doc_dgd_map()` / `db.luu_dgd_map()` — `db.py` |

---

## 11. Tài liệu liên quan

| File | Đọc khi nào |
|---|---|
| `DELTA.md` | **ĐỌC ĐẦU MỖI PHIÊN** — thay đổi gần đây, component mới, signature đã cập nhật |
| `ARCHITECTURE.md` | Cần hiểu quan hệ import giữa các module |
| `CONVENTIONS.md` | Cần biết quy ước chi tiết về kv_store, upload, CSS |
| `UI_GUIDELINES.md` | Bảng màu, typography |
| `ROLES.md` | Cần phân quyền chi tiết theo role mới |
| `TROUBLESHOOTING.md` | Gặp lỗi thường gặp về dữ liệu, cache, upload |
| `BUGMAP.md` | ĐỌC TRƯỚC KHI CODE — tra lỗi đã mắc để tránh lặp; sau khi fix bug thì ghi thêm |
| `SCHEMA.md` | **ĐỌC TRƯỚC KHI VIẾT SQL** — schema 16 bảng SQLite + parquet + query mẫu |
| `TEST_COVERAGE.md` | Bản đồ 31 file test, lỗ hổng cần test — đọc khi viết test mới |
| `DECISIONS.md` | Lý do chọn SQLite/Parquet/DuckDB/kv_store/render pattern — đọc khi muốn đổi công nghệ |
| `CHANGELOG.md` | Lịch sử thay đổi |
| `BACKLOG.md` | Yêu cầu người dùng — đã làm & sẽ làm |
| `ROADMAP.md` | Sprint + backlog |
| `TEMPLATES.md` | Hướng dẫn quản lý template Word |
| `HUONG_DAN_PHAN_HE.md` | Hướng dẫn sử dụng theo phân hệ |
| `HUONG_DAN_NGUON_DU_LIEU.md` | Luồng upload, cache, 2 luồng dữ liệu |

---

## 12. Tự động chọn model cho subagent

**Workflow thực tế:** AI khác (Cascade/Trae/Windsurf) viết code → **Sonnet chỉ review + fix**.  
Khi nhận task review, tự đánh giá và spawn model phù hợp — không dùng Sonnet cho mọi bước.

### 12.1 Bảng chọn model theo bước review

| Bước | Model | Làm gì |
|---|---|---|
| **Đọc + hiểu** code mới viết | `haiku` | Đọc file, grep pattern, hiểu cấu trúc, tóm tắt thay đổi |
| **Review + fix** bug thường | `sonnet` | Phân tích logic, tìm bug, sửa code `tabs/`, `services/` |
| **Review** code chạm `auth.py` / `db.py` / migration | `opus` | Gợi ý user restart — KHÔNG tự spawn Opus |

### 12.2 Quy tắc bắt buộc

**Trước khi review, đánh giá:**

```
Chưa đọc file nào  →  spawn Haiku đọc + tóm tắt trước, Sonnet review + fix sau
Đã có summary      →  Sonnet review + fix trực tiếp
Code chạm auth/db  →  Cảnh báo user: "nên dùng Opus"
```

**Ví dụ thực tế:**

```python
# Bước 1: Haiku đọc code mới để hiểu cấu trúc
Agent(subagent_type="Explore", model="haiku",
      prompt="Đọc tab_xu_ly_rui_ro.py và xlrr_service.py, tóm tắt các hàm chính, luồng dữ liệu")

# Bước 2: Sonnet nhận tóm tắt → review logic → fix bug
# (làm trực tiếp, không spawn thêm)

# Nếu code chạm auth.py/db.py → KHÔNG spawn Opus, thay vào đó nói:
# "⚠️ Code này sửa db.py — sai thì mất dữ liệu. Nên dùng Opus.
#  Bạn restart với `Codex --model Codex-opus-4-7` không?"
```

### 12.3 Khi nào KHÔNG spawn subagent

- User đã gửi kèm summary/tóm tắt thay đổi → Sonnet review trực tiếp, bỏ bước Haiku
- Chỉ sửa ≤ 2 file nhỏ → làm trực tiếp không cần spawn
- User đang hỏi/giải thích → trả lời trực tiếp

### 12.4 BẮT BUỘC — Hiện model ở đầu mỗi task

**Mỗi khi bắt đầu làm task (không phải hỏi/trả lời thường), PHẢI hiện dòng:**

```
🤖 Model: Sonnet 4.6  |  Lý do: [1 câu ngắn]
```

Hoặc khi spawn subagent:

```
🤖 Bước 1 — Haiku đọc file  |  Bước 2 — Sonnet review + fix
```

Hoặc khi cần Opus:

```
⚠️ Model đề xuất: Opus 4.7  |  Lý do: task chạm db.py — sai thì mất dữ liệu
   → Restart: Codex --model Codex-opus-4-7
```

**Mục đích:** User luôn biết model nào đang xử lý task, tự kiểm soát chi phí và độ tin cậy.
