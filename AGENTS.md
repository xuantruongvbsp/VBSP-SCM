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

> **Chi tiết:** xem `.trae/rules/rules.md` section 6. Dưới đây là tóm tắt nhanh:

| # | Quy tắc | Tóm tắt |
|---|---|---|
| 5.1 | Lưu dữ liệu | CHỈ dùng `db.ghi_kv()` / `db.doc_kv()` — không json.dump(), session_state |
| 5.2 | Audit | `db.ghi_audit()` NGAY SAU mọi `db.ghi_kv()` |
| 5.3 | Upload | QUA `upload_service.py`; `st.cache_data.clear()` sau upload |
| 5.4 | Tiền tệ | Nhập: triệu, Lưu: VND, Hiển thị: `fmt_ty()` (triệu đồng) / `vn(x/1e9)+" tỷ"` |
| 5.5 | Phân quyền | `normalize_role()` rồi `la_phan_he_cn()` / `la_phan_he_pgd()` — không check chuỗi thô |
| 5.6 | Tên đơn vị | `DON_VI_CHI_NHANH` (lọc), `TEN_CHI_NHANH_HIEN_THI` (hiển thị) |
| 5.7 | Widget key | Prefix unique: `cn_` hoặc `pgd_{slug}_` — không dùng index loop |
| 5.8 | pgd_mode | `if pgd_mode: path=duong_dan_pgd(...)` else `path=DB_HT_CACHE` |
| 5.9 | CSS/UI | Inject CSS 1 lần trong app.py; `st.date_input(format="DD/MM/YYYY")`; không hardcode color |
| 5.10 | Git | TUYỆT ĐỐI không tự commit/push |
| 5.11 | Model | UI → Trae; auth/db → Codex Haiku+; mất dữ liệu → Opus |
| 5.12 | Dependency | Không thêm mới |
| 5.13 | Tên cột | Dùng `COT_*` từ config.py → tra `COT_REF.md` |
| 5.14 | Auth funcs | `normalize_role`, `la_phan_he_cn/pgd`, `co_quyen_*` → tra `SIGNATURES.md` |
| 5.15 | Logging | `logger.error("...", exc_info=True)` — không `except: pass` |
| 5.16 | DuckDB | `pq.read_schema()` kiểm tra cột trước khi query |

**Key chuẩn kv_store:** `khtd_cn`, `khtd_pgd_{slug}`, `merge_meta_{loai}`, `kehoach`, `dgd_map`, `khnv_phan_cong_list`, `bao_cao_deadline_config` — đầy đủ trong rules.md

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

## 8. Function Signatures — tra nhanh

> **Tra cứu đầy đủ:** đọc `SIGNATURES.md` — tất cả signatures của Components, Utils, Auth.
> Cũng tham khảo `CODE_INDEX.md` để map chức năng → file → hàm.

Các lỗi tham số phổ biến cần nhớ:
- `kpi_row(cols, num_columns=4)` — **KHÔNG** phải `cols=4`
- `download_pdf_button(pdf_bytes=...)` — nhận **PDF bytes**, không phải df
- `loan_detail_drawer(row: pd.Series)` — nhận **row**, không phải DataFrame
- `luu_pgd_file(ten_pgd, loai, file_bytes)` — **3 tham số**, không có username

---

 Checklist trước khi sửa

> **Đầy đủ:** xem `.trae/rules/rules.md` section 8 (Checklist) + section 8.1 (Rà soát). Tóm tắt nhanh:

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
| `CODE_INDEX.md` | Map chức năng → file → hàm chính — tra trước khi grep |
| `COT_REF.md` | Danh sách đầy đủ COT_* constants (tách từ rules.md) |
| `SIGNATURES.md` | Function signatures của Components, Utils, Auth (tách từ rules.md) |
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
