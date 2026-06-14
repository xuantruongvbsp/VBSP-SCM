# DELTA — VBSP-SCM
> Cập nhật sau mỗi lần hoàn thành tính năng (Trae tự append)
> Khi file > 200 dòng: gộp phần stable vào STABLE.md, xóa khỏi đây

---

## [2026-06-15] Telegram Push Notification

### `services/telegram_service.py` — tạo mới
- `gui_tin(text)` — gửi bất kỳ tin nhắn văn bản (base)
- `gui_bao_cao_sang(ngay, tong_du_no, tong_qh, ty_le_qh, so_pgd_da_upload, tong_pgd)` — tóm tắt sáng
- `gui_canh_bao_deadline(ten_loai, deadline, chua_nop)` — nhắc PGD chưa nộp
- `gui_ket_qua_health_check(ok, warn, err, ngay, chi_tiet)` — health check
- `gui_thong_bao_merge(loai, so_pgd, username)` — sau merge toàn CN
- `gui_nhac_khoang_den_han(ds_khoang)` — khoản đến hạn 7 ngày
- `luu_config(token, chat_id, username)` — cập nhật bot qua kv_store key `telegram_config`

### `scripts/daily_report.py` — hook Telegram
- Dòng ~335: gọi `gui_bao_cao_sang()` sau khi lưu file Excel xong (try/except — không làm hỏng báo cáo nếu Telegram lỗi)

### `test_telegram.py` — file test double-click
- Gửi tin nhắn test; in "Gửi thành công!" nếu OK

---

## [2026-06-06] 4 card Dư nợ BQ: PGD / Tổ TKVV / Xã / Hội

### `tabs/tab_tongquan.py` — thêm 4 card BQ cuối grid Tổng quan danh mục tín dụng
- L329-348: tính `df_bq` với `pd.to_numeric()` trước groupby
- L402-422: 4 card HTML (soft-purple/indigo/blue/amber) hiển thị tr + số đơn vị

### `workspaces/ws_operation.py` — thêm Vùng B2 4 card BQ trong Trang Chủ
- L754-791: `kpi_row` 4 card, nằm dưới 8 KPI cards, trước divider

### Bug fix: `pd.to_numeric()` trước groupby.sum → sửa BQ PGD sai (2 thay vì 22)
### Bug fix: `nunique()` thay `groupby.ngroups` → sửa BQ Xã/Hội sai
### Bug fix: filter NaN/"CỘNG" khỏi nunique → sửa BQ Hội 5→4

### `BUGMAP.md` — ghi C13, C14, C15
### `.trae/rules/rules.md` — thêm lỗi #13, #14, #15 vào Section 9

---

## [2026-05-29] GSheet Tiến độ Báo cáo: refactor toàn diện + JWT fix + health check

### `tabs/tab_tien_do_nop.py` — REFACTOR LỚN (loại bỏ "Kỳ báo cáo")

**Lý do:** Các loại báo cáo (Kiểm toán NHNN, Đột xuất, KHTD...) là sự kiện 1 lần, không lặp tháng/quý. Kỳ báo cáo là thừa.

| Thành phần | Trước | Sau |
|---|---|---|
| **COT** | 8 cột (có `ky_bao_cao`) | 7 cột (bỏ `ky_bao_cao`) |
| **Deadline config** | `{loai: {ky: dl}}` | `{loai: dl}` |
| **Tab Tổng quan** | Dropdown chọn kỳ → ma trận PGD×Loại×Kỳ | Ma trận PGD×Loại luôn hiện |
| **Tab Danh sách** | 3 dropdown (Kỳ, Loại, Đơn vị) | 2 dropdown (Loại, Đơn vị) |
| **Tab Cài đặt** | Chọn Loại + Kỳ → cài deadline | Chọn Loại → cài deadline |
| **Tab Hướng dẫn** | Không có | Mới: flow diagram HTML + mockup Form |

### BUG FIX: Google Form thêm cột "Cột 8" → 9 cột nhưng COT chỉ 8
- **Dòng ~67:** `df = pd.DataFrame([r[:len(COT)] for r in data[1:]], columns=COT)`
- Chỉ lấy N cột đầu, chống lỗi khi Google Form thêm cột phụ

### BUG FIX: `invalid_grant: Invalid JWT Signature`
- **Nguyên nhân:** Google tự động Disable service account key vì phát hiện exposed trên public GitHub repo
- **Fix:** Xóa key cũ (`bf4faee...`, status=Disabled/Exposed) → tạo key mới trên GCP Console → copy đè `credentials.json`
- **Phòng ngừa:** `setup_env.bat` thêm Bước 1: đồng bộ thời gian `w32tm /resync` (tránh lỗi JWT do clock skew)

### `setup_env.bat` — thêm bước đồng bộ thời gian
- Nâng từ 5→6 bước: Bước 1 mới = `net start w32time && w32tm /resync /force`
- Cấu hình `w32time` thành `Automatic` (tự chạy khi khởi động)

### Health check toàn diện (29/05/2026)
| Chỉ số | Giá trị | Đánh giá |
|---|---|---|
| Tabs | 52/52 compile OK | 🟢 |
| .py files (active) | 230 files, 89,761 dòng | 🟢 |
| DB | 0.3MB, 25 tables, audit_log 75 dòng | 🟢 |
| Disk | 209.7GB, dùng 3% | 🟢 |
| `st.cache` deprecated | 0 | 🟢 |
| `st.beta_`/`st.experimental_` | 0 | 🟢 |
| `width='stretch'` còn sót | 0 — đã fix toàn bộ 31/05 | 🟢 |
| `_archive/` dead code | 21 .py files | 🟡 |
| `VBSP-SCM/` duplicate subfolder | 393 files | 🟡 |
| `html()` vs `markdown(unsafe_allow_html)` | Đã dùng `st.html()` | 🟢 |

---

## [2026-05-26] tab_pgd_cards redesign + fix applymap pandas 3.0

### `tabs/tab_pgd_cards.py` — REDESIGN TOÀN DIỆN
- **BUG FIX**: `Styler.applymap()` → `.map()` — pandas 3.0 đã xóa `applymap`; crash `AttributeError` nếu không fix
- CSS: gradient card `#0D1B2A→#112240`, hover glow xanh, badge NQH dạng pill có viền màu, rank badge #N góc phải
- KPI row: 5 metrics (thêm **BQ/hộ toàn CN**)
- Card HTML: 5 KPI block (thêm **BQ/hộ**, màu cyan), hiển thị số món vay
- Biểu đồ: Plotly combo chart bar dư nợ + scatter NQH% + scatter BQ/hộ; tab 2 = bar chart xếp hạng BQ/hộ với đường tham chiếu BQ CN
- Sort: thêm option **"BQ/hộ (giảm)"**
- Bảng xếp hạng: pandas Styler `.map()` color-coded NQH% + BQ/hộ cyan

### `services/tongquan_service.py` — `tinh_card_pgd()`
- Thêm cột output: `dn_binh_quan_ho` = `du_no / so_kh` (đơn vị đồng, fillna=0)
- Signature không đổi

**Pandas compatibility note:** pandas 3.0 xóa `Styler.applymap()` — dùng `.map()` thay thế (API giống nhau).

---

## [2026-05-26] test_components.py — 27 test cases components (ROADMAP §1.1)

### `tests/test_components.py` — **MỚI** (27 test cases)

| Class | Tests | Hàm được test |
|---|---|---|
| `TestFmtVnNum` | 5 | `delta_card._fmt_vn_num()` — số nguyên, thực, chuỗi, âm |
| `TestPickDimCol` | 5 | `movers._pick_dim_col()` — 5 dimension keys (pgd/xa/chuongtrinh/to/dvut) |
| `TestFormatValue` | 3 | `movers._format_value()` — tiền, tỷ lệ, số khác |
| `TestRenderField` | 8 | `loan_drawer._render_field()` — null, nan, tiền, pct, error path |
| `TestLocDuNoDuong` | 3 | `tongquan_service.loc_du_no_duong()` |
| `TestChuanHoaNgay` | 3 | `tongquan_service.chuan_hoa_ngay()` — datetime, string, missing column |

**Kết quả:** `27 passed in 0.79s ✅`

---

## [2026-05-26] daily_report_service — Báo cáo định kỳ sáng (ROADMAP §2.1)

### `services/daily_report_service.py` — **MỚI**

**Public API:**
```python
tao_bao_cao_sang(nguoi_tao="system") -> Path    # tạo Excel + lưu + audit
lay_bao_cao_sang_hom_nay() -> Path | None        # có báo cáo hôm nay chưa
lay_ds_bao_cao(n_ngay=7) -> list[dict]           # {ngay, path, ten_file, size_kb, hom_nay}
ten_file_ngay(d=None) -> str                     # "bao_cao_sang_DDMMYYYY.xlsx"
REPORTS_DIR: Path                                # BASE_DIR/cache/reports (tuyệt đối)
```

**4 sheets Excel:**
| Sheet | Nguồn dữ liệu |
|---|---|
| Tổng quan | `tong_hop_tq_kpi(CACHE_HSTD)` — 1 dòng KPI |
| Dư nợ theo PGD | `tong_hop_tq_pgd_full(CACHE_HSTD, year)` — 22 PGD |
| NQH theo PGD | `dem_no_qua_han_pgd(CACHE_HSTD)` |
| Đến hạn tháng này | pandas read_parquet → group by PGD |

**Integration:**
- `tabs/tab_bao_cao_dinh_ky.py` — UI tab (mount trong ws_management.py group "Báo cáo")
- `health_check.py` `__main__` — auto-generate nếu chưa có hôm nay

---

## [2026-05-26] filter_bar — Lưu cấu hình bộ lọc (ROADMAP §1.4)

### `components/filter_bar.py` — 4 hàm preset + UI Save/Load/Delete

**4 hàm public mới:**
```python
load_filter_presets(username)         # → {name: {field: value}}
save_filter_presets(username, presets) # ghi kv + audit + cache.clear()
get_last_filter_preset_name(username)  # → str | None
set_last_filter_preset_name(username, name)
```

**Key kv_store:** `filter_preset_{username}` → `{"presets": {...}, "last_used": "tên"}`

**Thay đổi `filter_bar()`:**
- Thêm param `username: str = ""` (optional — backward compatible)
- Auto-load preset lần cuối khi render lần đầu (flag `{key_prefix}_auto_loaded`)
- Hiện UI Save/Load/Delete 3 cột nếu `username` được truyền

**Cách dùng:**
```python
filter_values = filter_bar(df, filters, key_prefix="fb",
                            username=st.session_state.get("username", ""))
```

---

## [2026-05-26] Health check tự động ROADMAP §1.3/1.4 — kv_store + sidebar + Task Scheduler

### `health_check.py` — ghi kết quả vào kv_store

**Thêm `_ghi_ket_qua_kv(exit_code)`** (~dòng 298):
- Sau khi chạy xong 5 checks, ghi JSON vào `kv_store` key `health_check_result`
- Payload: `{ts, total, passed, failed, failed_labels, exit_code}`
- Ghi trực tiếp SQLite (không qua `db.py`) vì health_check chạy độc lập

### `alert_center.py` — đọc kết quả và hiện cảnh báo sidebar

**Thêm `_kiem_tra_health_check()`** (~dòng 382):

| Trường hợp | Alert |
|---|---|
| Chưa chạy lần nào (`health_check_result` = None) | 🟡 LƯU Ý — hướng dẫn chạy thủ công |
| Kết quả stale > 25h | 🟡 LƯU Ý — kiểm tra Task Scheduler |
| `failed` ≥ 3 | 🔴 KHẨN — liệt kê labels tối đa 3+N |
| `failed` 1–2 | 🟠 CẢNH BÁO — liệt kê labels |
| `failed` = 0 | Không hiện gì |

**`_build_alert_items()`** gọi `_kiem_tra_health_check()` cho CN role.

### `scripts/setup_health_check_task.bat` — **MỚI**
- `schtasks /create /sc daily /st 06:30` — chạy mỗi ngày 6:30 sáng
- Log ra `logs/health_check.log`
- Chạy với quyền Administrator (Run as administrator)

---

## [2026-05-26] Performance §1.2 — 4 DuckDB aggregates + cache optimization

### 4 hàm DuckDB mới trong `data/core.py` (~dòng 235–455)

| Hàm | Thay thế | Mô tả |
|---|---|---|
| `tong_hop_tq_pgd(parquet_path, nam_ht)` | `tinh_tqpgd_extended()` (~4 pandas groupby) | Tổng hợp dư nợ/NQH/khoanh/đến hạn 22 PGD, 1 SQL |
| `tong_hop_tq_pgd_full(parquet_path, nam_ht, pgd_filter)` | `tinh_tqpgd_extended()` + merge | Tổng hợp có filter PGD |
| `tong_hop_tq_co_cau_ct(parquet_path, pgd_filter)` | `tinh_co_cau_ct()` (~6 pandas groupby) | Cơ cấu dư nợ theo chương trình TD |
| `tong_hop_tq_kpi(parquet_path, pgd_filter)` | `tinh_kpi_tongquan()` | KPI tổng quan: tổng dư nợ, NQH%, khoanh, cảnh báo |

**Pattern mỗi hàm:**
- Schema check `pd.read_parquet(parquet_path).columns.tolist()` trước query (§5.16)
- Fallback `return pd.DataFrame()` nếu lỗi, không raise
- Đọc trực tiếp từ Parquet — không nạp toàn bộ DataFrame vào RAM

### DuckDB cho `_build_tong_hop_sheets` trong `tabs/tab_so_sanh_ky/_export.py` (~dòng 599)

- Thêm param `parquet_path`
- Nếu `CACHE_HSTD` tồn tại → 3 DuckDB queries (PGD / Xã / CT) thay pandas groupby
- Fallback về pandas nếu không có parquet hoặc query lỗi

### Cache coverage — đã xác nhận

| File | Hàm | Cache |
|---|---|---|
| `app.py` | `_load_hstd()` | `@st.cache_resource(ttl=3600)` ✅ |
| `data/hstd.py` | `doc_file()` | `@st.cache_data(ttl=7200)` ✅ |
| `tabs/tab_tongquan.py` | 4 cache functions | `@st.cache_data(ttl=3600)` ✅ |
| `tabs/tab_so_sanh_ky/_export.py` | export state | `st.session_state` ✅ |

### Kết quả kiểm tra

```
✅ py_compile: data/core.py → OK
✅ py_compile: _export.py → OK
✅ import: 4 hàm DuckDB → OK
✅ convention check: data/core.py → OK
✅ convention check: _export.py → OK
```

---

## [2026-05-26] XLRR: Archive tab cũ + Fix GOM tháng + Bổ sung 13/14 XLN

### Tab đã xóa (deprecated)
- `tabs/tab_no_rui_ro.py` — đã xóa, bản sao lưu tại `_archive/tab_no_rui_ro_DEPRECATED.py`
- `tabs/tab_xlrr_tong_hop.py` — đã xóa, bản sao lưu tại `_archive/`

### Fix bug: GOM tháng sai trong `_subtab_tong_hop_cn`
- **Vấn đề:** 3 chỗ dùng `thang_hien_tai = now.month` (hardcode tháng hiện tại) thay vì tháng user chọn; vòng lặp gom tất cả 12 tháng thay vì chỉ tháng đang xem
- **Fix:** Thêm `thang_cn = st.selectbox(...)` → thay `now.month` ở Bước 1 (GOM), Bước 2 (Import Excel), Bước 3 (Rà soát)
- **File:** `tabs/tab_xu_ly_rui_ro.py` dòng ~961-1075

### Tính năng mới: 13/XLN · 14/XLN trong _subtab_tong_hop_cn
- **Vị trí:** dòng ~1255, cuối section Tổng hợp CN→TW
- **Chức năng:** Xuất báo cáo sau hạch toán khi có QĐ HĐQT
- **UI:** Expander nhập thông tin QĐ (số, ngày ký, từ–đến ngày) + 4 nút grid 2×2
- **Functions:** `_tao_word_13xln()`, `_tao_word_14xln()` từ `services/word_xln_service.py`; `_tong_hop_no()` từ `services/rui_ro_aggregation.py`
- **Guard:** Kiểm tra `so_qd_13.strip()` trước khi xuất; hiển thị warning nếu không có hồ sơ

---

## [2026-05-25] Fix 4 bugs XLRR — Claude Sonnet review

### Bug 1 (🔴 crash): `HoSoRuiRo.from_dict()` không convert ngay_ky_01/ngay_lap_02
- **File:** `services/xlrr_service.py` dòng ~134
- **Triệu chứng:** `AttributeError: 'str' object has no attribute 'strftime'` khi bấm xuất 01/XLN hoặc 02/XLN sau lần load từ kv_store
- **Fix:** Thêm `"ngay_ky_01", "ngay_lap_02"` vào list convert date trong `from_dict()`
- **Pattern:** Mỗi khi thêm `Optional[date]` field mới → bắt buộc thêm vào CẢ `to_dict()` VÀ `from_dict()`

### Bug 2 (🟡 logic): DON_VI_CHI_NHANH trong dropdown CN lập hồ sơ PGD
- **File:** `tabs/tab_xu_ly_rui_ro.py` dòng ~87
- **Fix:** Bỏ Hội sở khỏi dropdown → chỉ dùng `DS_PGD` (21 PGD)

### Bug 3 (🟡 UX): du_no_goc_display luôn trống
- **File:** `tabs/tab_xu_ly_rui_ro.py` dòng ~148
- **Fix:** Tính `tong_du_no_goc_val` từ `ds_chon` + `df_pgd` TRƯỚC khi vào form

### Bug 4 (🟡 data): pgd_slug="" khi import Excel từ PGD
- **File:** `services/xlrr_export_service.py` dòng ~206
- **Fix:** `pgd_slug=_pgd_slug(ten_pgd)` thay vì để rỗng

---

## [2026-05-25] Fix tab Xử lý Rủi ro — Sub-tab 5 Báo cáo

### Lỗi đã fix
`_subtab_bao_cao()` gọi 2 method không tồn tại trong `LuuTruXLRR`:
- `LuuTruXLRR.doc_ds_cn()` → **AttributeError** khi mở tab
- `LuuTruXLRR.doc_ds_pgd(pgd_user)` → **AttributeError** khi mở tab

### Fix
```python
# TRƯỚC (crash):
ds_hs = LuuTruXLRR.doc_ds_cn()
ds_hs = LuuTruXLRR.doc_ds_pgd(pgd_user)

# SAU (đúng):
ds_hs = LuuTruXLRR.doc_cn(int(nam_xuat), thang_xuat)
ds_hs += LuuTruXLRR.doc_qd62(int(nam_xuat), thang_xuat)
# PGD:
ds_hs = LuuTruXLRR.doc_pgd(pgd_slug(pgd_user), int(nam_xuat), thang_xuat)
```

### Cải thiện thêm
- Thêm **month/year selector** (T1–T12, 2020–2030) để chọn kỳ xuất biểu
- Selectbox hồ sơ dùng `id` làm key thay text-label → tránh collision khi trùng tên KH

---

## [2026-05-25] Thiết kế lại Hồ sơ đến hạn — Tổng hợp (`tab_tongquan.py`)

### Thay đổi layout
| Thành phần | Trước | Sau |
|---|---|---|
| Header + Nhóm TH | `st.subheader` + `st.selectbox([2,10])` tách riêng | Cùng hàng `st.columns([6,2])` |
| Filter tầng 1 | `st.expander` bao quanh `filter_bar()` (double toggle) | `st.multiselect` inline luôn hiển thị |
| Filter tầng 2 | `filter_bar()` có toggle ẩn/hiện bên trong mỗi tab | **Xóa** — gộp vào unified filter |
| 5 filter fields | PGD + CT (ngoài); Xã + NV + Dư nợ (trong tab) | PGD + CT + Xã + NV + Dư nợ slider (1 hàng duy nhất) |
| KPI | 3 × `st.metric()` | `kpi_row()` icon + help tooltip |
| Charts | Bar dọc → divider → Pie dọc | Bar (60%) \| Donut (40%) song song |
| Bảng | Trong `if nhom_col in df_loc.columns:` | Bên dưới 2 charts |
| Export | `st.columns(2)` nhỏ | `st.columns([3,3,4])` rõ ràng |

### Xóa code
- Toàn bộ block tầng 2 trong `_bang_den_han` (~60 dòng): `_df_bar`, `_filters_cfg`, `filter_bar()`, `ap_dung_loc_den_han_tab()`
- `tab_filters` dict (param của `_bang_den_han`)
- `st.divider()` giữa bar chart và bảng

### Function signature mới
```python
# CŨ:
def _bang_den_han(df_loc, label, key_prefix, tab_filters=None)
# MỚI (closure lấy _sel_pgd, _sel_ct, _sel_xa, _sel_nv, _no_range từ outer scope):
def _bang_den_han(df_loc, label, key_prefix)
```

---

## [2026-05-25] Card nền màu cho Tổng hợp Cảnh báo Tín dụng

### CSS classes mới: `.cb-card` + `.cb-{blue|green|red|purple}`
```
.cb-grid  — 5-column responsive grid
.cb-card  — card nền màu, dùng flex column
.cb-blue  — #dbeafe (Đến hạn)
.cb-green — #dcfce7 (KHĐ=0, QH=Không, Khoanh=0)
.cb-red   — #fee2e2 (KHĐ>0, QH=Có, Khoanh>0)
.cb-purple— #ede9fe (Đã gia hạn)
```

### 5 chỉ tiêu mới (tên rõ ràng)
| Cũ | Mới |
|---|---|
| Đến hạn (3 tháng) | 🔔 Đến hạn ≤ 3 tháng |
| 3 tháng không HĐ | ⚠️ ≥ 3 tháng không HĐ |
| Có nợ quá hạn | 🚨 Có nợ quá hạn |
| Khoanh khẩn | 📌 Khoanh cần kiểm tra (tổng ≤180d) |
| Đã gia hạn | 📅 Đã gia hạn (T/N) |

### File changed
| File | Change |
|---|---|
| `tabs/tab_canh_bao_nqh.py` | `_render_tong_hop()`: thay 5 `st.metric()` bằng HTML card |

---

## [2026-05-24] Thiết kế lại bộ lọc Hồ sơ đến hạn — Tổng hợp (Tầng 1 + Tầng 2)

### Kiến trúc filter mới
```
Tầng 1 — Bộ lọc chung (trước lazy_tabs)
  Expander "🔍 Bộ lọc chung" (mặc định đóng)
    PGD [multiselect]      → filter_chung[PGD]
    Chương trình [multiselect] → filter_chung[CT]
  → dt_chung = apply_filters(dt, filter_chung) → dùng cho TẤT CẢ các tab

Tầng 2 — Bộ lọc trong tab (trong mỗi lazy_tab)
  Expander "🔍 Lọc trong tab" (mặc định đóng)
    Xã [multiselect]       → tab_filters["xa"]
    Nguồn vốn [TW/ĐP/Tất cả] → tab_filters["nv"]
    Dư nợ range [slider]   → tab_filters["no_range"]
  → df_tab = ap_dung_loc_den_han_tab(df_loc, ...)
  Key widget: tq_tab_{key_prefix}_{xa|nv|no} → độc lập giữa các tab

Tab mới: 📅 Tùy chỉnh
  → date_input Từ ngày / Đến ngày → loc_den_han với khoảng tùy chọn
```

### Files changed
| File | Change |
|---|---|
| `tabs/tab_tongquan.py` | Refactor ~290 dòng section đến hạn. `filter_values` → `filter_chung` + `tab_filters`. Tầng 2 filter trong mỗi tab |
| `services/tongquan_service.py` | Thêm `ap_dung_loc_den_han_tab()` |

### Performance impact
| Thay đổi | Trước | Sau |
|---|---|---|
| Filter Xã gây rerun | Cả 4 tab | Chỉ tab hiện tại |
| Số tab | 4 (1T/3T/6T/TN) | 5 (+Tùy chỉnh) |
| Chiều lọc | 3 (PGD/CT/Xã) | 5 (PGD/CT/Xã/NV/Dư nợ range) |

### API mới: ap_dung_loc_den_han_tab()
```python
def ap_dung_loc_den_han_tab(
    df, *, cot_xa, cot_nv, loc_xa, loc_nv, cot_tdn, range_no_trieu
) -> pd.DataFrame:
    # Lọc Xã theo multiselect
    # Lọc Nguồn vốn (1=TW, 2=ĐP)
    # Lọc Dư nợ theo range (triệu đồng → nhân 1e6)
```

### API thay đổi: _bang_den_han()
```python
def _bang_den_han(df_loc, label, key_prefix, tab_filters=None):
    # tab_filters: dict từ Tầng 2 filter
    # Dùng filter_chung + tab_filters để quyết định co_loc (Excel export)
    # PDF: truyền filter_chung.get(PGD), filter_chung.get(CT), tab_filters.get("xa")
```

---

## [2026-05-24] Tối ưu cold start tầng 1: lazy import + skip NQ11/GQVL

### Profiled bottlenecks
| Module | Import time |
|---|---|
| alert_center | 18.0s |
| widgets.status_widget | 25.8s |
| **TOTAL top-level imports** | **43.8s** |

### Changes
| File | Change | Impact |
|---|---|---|
| `app.py` dòng 59-60 | Removed top-level imports of `render_alert_sidebar` + `render_status_compact` | -44s cold start |
| `app.py` dòng ~300, ~314 | Lazy import inside `with st.sidebar:` block at point of use | Only pay import cost when sidebar renders |
| `app.py` dòng ~456, ~486 | Skip NQ11/GQVL load when `ws_hien_tai == "executive"` | -2-3s for executive users |

**Pattern**: top-level imports of heavy modules (alert_center, status_widget) run on every Streamlit rerun even when not used. Move to lazy import at point of use.

## [2026-05-24] Optimize cold start: bỏ object→category + DuckDB full scan

### Profiling measured bottlenecks
| Metric | Value |
|---|---|
| Parquet file | 29.7 MB |
| Data | 349,398 rows × 174 cols (163 object) |
| pd.read_parquet | 4.7s |
| DuckDB SELECT * → Arrow → pandas | 8.3s |
| _toi_uu_dtype(): nunique() × 163 cols | ~4s |
| _toi_uu_dtype(): astype("category") | ~2s |
| RAM after load | 738 MB (25× parquet size) |

### Changes
| File | Change | Impact |
|---|---|---|
| `app.py:_toi_uu_dtype()` | Removed object→category conversion loop (~25 lines) | -6s cold start, eliminates "category type does not support sum operations" bugs |
| `app.py:_load_hstd()` | Full scan (no WHERE) uses `pd.read_parquet()` instead of DuckDB; DuckDB kept for filtered queries | -3.5s for full scan |
| Total | | **~10s faster cold start** |

## [2026-05-24] Fix 13 lỗi Tab Kiểm toán Nội bộ — Phase 2 (Sonnet Review)

| Fix | File | Mức độ | Chi tiết |
|---|---|---|---|
| Guard empty danh mục lỗi | `ktnb_service.py` ~724 | 🔴 CRITICAL | Thêm `if df_dm.empty` check trước form — tránh `IndexError` khi bảng trống |
| Fix keyword args dòng 786 | `ktnb_service.py` ~786 | 🔴 CRITICAL | Sửa call `cap_nhat_trang_thai_loi()` sang keyword args (Phase 1 bỏ sót dòng này) |
| Fix `is_truong_doan` logic | `ktnb_service.py` ~690 | 🔴 CRITICAL | Check có vai_tro="truong_doan" trong đoàn, chứ không so sánh text == username (sai) |
| Cột trạng thái lịch | `ktnb_service.py` ~195 | 🟡 MEDIUM | Thêm cột "Trạng thái lịch hiển thị" vào bảng (map: sap_toi→📅, dung_han→✅, qua_han→⚠️) |
| Date format YYYY-MM-DD | `ktnb_service.py` ~213,214,735 | 🟡 MEDIUM | Thêm `format="DD/MM/YYYY"` vào 3 `st.date_input` (CLAUDE.md §5.9) |
| Widget key prefix | `ktnb_service.py` ~253 | 🟡 MEDIUM | Thêm `_ktnb_` prefix cho form_them_tv keys (`tv_*` → `_ktnb_tv_*`) |
| Excel export antipattern | `ktnb_service.py` ~528 | 🟡 MEDIUM | Sửa `st.button→st.download_button` thành session_state cache (tránh bytes mất) |

## [2026-05-24] Fix 7 lỗi Tab Kiểm toán Nội bộ — Phase 1 (Haiku)

| Fix | File | Mức độ | Chi tiết |
|---|---|---|---|
| Try-except file operations | `ktnb_service.py` ~671 | 🔴 CRITICAL | `_luu_minh_chung()` bây giờ handle OSError + unhandled exceptions, trả None nếu lỗi |
| Validate path after upload | `ktnb_service.py` ~756 | 🔴 CRITICAL | Check `path is not None`, thêm 10MB limit, dùng keyword args |
| Form validation | `ktnb_service.py` ~217 | 🟡 MEDIUM | Validate: Số CV ≤50 ký tự, Trưởng đoàn, Ngày bắt đầu ≤ Kết thúc |
| Session key consistency | `ktnb_service.py` ~183-383 | 🟡 MEDIUM | Dùng `_ktnb_*` prefix cho tất cả session keys (thay mix cũ) |
| Remove st.json() + duplicate | `ktnb_service.py` ~817 | 🔴 CRITICAL | Xóa raw JSON display + duplicate `render_ke_hoach_lich_trinh()` call |

---

## [2026-05-24] Fix 6 lỗi tab So sánh 2 kỳ

### Package `tabs/tab_so_sanh_ky/`

| Fix | File | Chi tiết |
|---|---|---|
| CSS classes mất màu delta | `_common.py` dòng ~105 | Thêm `.delta-pos`, `.delta-neg`, `.delta-zero` vào `Q_BAR_CSS`; trước đó class HTML gán nhưng không có style → bảng so sánh mất màu xanh/đỏ |
| Export UI antipattern | `_export.py` `render_export_ui()` | `st.button→st.download_button` lồng nhau → bytes biến mất sau rerun; thay bằng `session_state` cache + `st.download_button` trực tiếp |
| Cảnh báo PDF | `_export.py` `render_export_ui()` | Nếu `reportlab` chưa cài, hiện `st.warning` thay vì trả `b""` im lặng |
| Label quality bar lặp | `render_2_ky.py` dòng ~114 | `f"Kỳ {ky1} — {ky1}"` → `f"Kỳ {ky1}"` |
| CDTOTKVV thiếu metric | `render_2_ky.py` `_render_cdtotkvv_section()` | Bổ sung Tổ Khá + Tổ Trung bình vào KPI row (bản cũ chỉ có 4/6 metric) |
| CDTOTKVV mất pie charts | `render_2_ky.py` `_render_cdtotkvv_section()` | Thêm lại 2 pie charts song song 2 kỳ (mất khi refactor từ tab_so_sanh_2_ky.py) |

### `tabs/tab_so_sanh_2_ky.py`
Thêm `⚠️ DEPRECATED` — file không còn được gọi từ workspace nào.

---

## [2026-05-24] Refactor DRY: gộp _should_force_str + _normalize_code_series về 1 nơi + root-fix lỗi A4e tái đi tái lại

### Refactor — triệt tiêu duplicate code giữa core.py và hstd.py
`_should_force_str()` và `_normalize_code_series()` bị copy-paste giữa `data/core.py` (bản gốc, đã fix "số atm") và `data/hstd.py` (bản thiếu "số atm" + pattern `s.startswith("số ")`). Khi `doc_baseline_merged()` rebuild cache merge dùng bản `hstd.py` → cột "Số ATM" không được chuẩn hóa → vẫn mixed type → crash.

| Thay đổi | File | Dòng |
|---|---|---|
| Đưa `_should_force_str` + `_normalize_code_series` lên **module-level** | `data/core.py` | ~19–55 |
| Import từ `data.core` thay vì copy-paste | `data/hstd.py` | ~8 |
| Xóa block `try: import unicodedata...` + `_should_force_str` + `_norm_series` (~40 dòng) | `data/hstd.py` | ~141–182 |
| Gọi `_should_force_str` + `_normalize_code_series` từ import thay vì local | `data/hstd.py` | ~142–143 |

**Kết quả**: 1 nơi duy nhất định nghĩa 2 hàm → sau này sửa 1 lần là đủ.

### Lỗi A4e — Số ATM mixed type → PyArrow crash (đã fix trước đó, giờ thêm root cause)
- `data/core.py` dòng ~38 — Đã thêm `"số atm"` + pattern `s.startswith("số ") and ("kh" in s or "account" in s)` vào `_should_force_str()`
- `data/core.py` dòng ~88–89 — Check `any(isinstance(v, bytes) for v in _non_null.iloc[:100])` (100 phần tử, không chỉ `iloc[0]`)

## [2026-05-22] Root-fix df=None trong Phòng KH-NV

### Bug — ALL_ITEMS closure stale (df=None) do sidebar render trước data load

**Root cause:** `app.py` render sidebar (dòng ~283) → `render_sidebar_menu(df=locals().get("df"))` → `df` chưa định nghĩa → `None` → `_build_all_items(df=None)` → lambda đóng gói df=None → `st.session_state["_mgmt_all_items"] = all_items` (stale) → `render()` pop ra → mọi tab nhận df=None.

| Thay đổi | File | Dòng |
|---|---|---|
| Xóa `st.session_state["_mgmt_all_items"] = all_items` | `workspaces/ws_management.py` | ~832 |
| `render()` luôn build ALL_ITEMS fresh (bỏ pop + if-None) | `workspaces/ws_management.py` | ~971 |

**Ghi chú:** trước đó CHANGELOG có entry "revert ý tưởng share menu qua session_state" nhưng chỉ thêm comment, không xóa dòng code → bug vẫn tồn tại.

---

## [2026-05-22] Fix tab Tổng quan: 3 section trống

### Bug — guard + else-clause cho 3 section không có bảng/dữ liệu

**Root cause** (chẩn đoán): cả 3 section đều bị guard `if col in df.columns:` nhưng **không có `else`** → khi cột bị thiếu (sai tên, dữ liệu chưa upload, file PGD riêng), heading vẫn render nhưng không có gì bên dưới — người dùng thấy phần trống.

| Thay đổi | File | Dòng |
|---|---|---|
| Guard `if df is None/empty: return` | `tabs/tab_tongquan.py` | ~164 |
| `if df_ct.empty: st.info(...)` | `tabs/tab_tongquan.py` | ~434 |
| `else: st.warning(tên cột thiếu)` cho "Cơ cấu dư nợ" | `tabs/tab_tongquan.py` | ~533 |
| `else: st.warning(...)` cho "Thông tin tổng quát PGD" | `tabs/tab_tongquan.py` | ~1008 |
| `else: st.warning(...)` cho "Hồ sơ đến hạn" | `tabs/tab_tongquan.py` | ~1289 |
| Expander debug "Chẩn đoán: Cột dữ liệu bị thiếu" | `tabs/tab_tongquan.py` | ~1296 |

**Khi xảy ra**: app sẽ hiển thị `st.warning(...)` với tên cột bị thiếu thay vì trống không, và expander debug liệt kê tất cả cột còn thiếu + số cột/dòng hiện có + hướng dẫn sửa.

---

## [2026-05-22] Thêm COT_GIAI_NGAN_TRONG_NAM

### Refactor — xoá hardcode "Giải ngân trong năm"
- `config.py` — thêm `COT_GIAI_NGAN_TRONG_NAM = "Giải ngân trong năm"` (trước `GQVL_COT_MAP`); `GQVL_COT_MAP` + `HSTD_DS_CHO_VAY_NAM_ALIASES` dùng constant thay dict-lookup
- `snapshot_service.py` — `_GN_NAM_ALIASES[0]` + `_COL_GN` → constant
- `tabs/tab_gqvl.py` — `G_GN_NAM` → constant
- `services/upload_service.py` — 3 list `_cols_so` → constant
- `tabs/tab_ban_dai_dien.py` — `_GN_NAM_ALIASES[0]` → constant

Phân tích Thời hạn vay + Dư nợ trong hạn: đã có `COT_THOI_HAN`/`COT_DU_NO_TH`, toàn bộ code guard `if col in df.columns` → **an toàn dù GQVL file thiếu 2 cột này**.

---

## [2026-05-22] Đồng bộ fmt_ty() + sửa TROUBLESHOOTING

### Sửa tài liệu — fmt_ty() bị doc sai /1e12 ở nhiều file
Phát hiện `fmt_ty()` thực tế chia `/1e6` → triệu đồng (0 số lẻ, không hậu tố "tỷ"), nhưng bị document sai là `/1e12` trong 12+ file. Đã sửa toàn bộ.

Quy ước đúng (đã đồng bộ vào STABLE.md, CLAUDE.md, CONVENTIONS.md, rules.md, AGENTS.md, .clinerules, .windsurfrules, codebase_for_ai.md, README.md, ARCHITECTURE.md):

| Ngữ cảnh | Code | Kết quả |
|---|---|---|
| Cột bảng | `fmt_ty(x)` | triệu đồng (0 số lẻ) |
| Metric card inline | `vn(x / 1e9, 3) + " tỷ"` | tỷ đồng (3 số lẻ) |

- `docs/TROUBLESHOOTING.md` §1 — xóa ví dụ sai `/1e12 = tỷ` → bảng hướng dẫn 2 lớp đúng
- `docs/UI_GUIDELINES.md` §7 metric card — `/1e12` → `/1e9` (metric card dùng /1e9, không phải /1e6)

---

## [2026-05-22] Tạo 3 file tài liệu: SCHEMA / TEST_COVERAGE / DECISIONS

### Thêm mới
- `SCHEMA.md` — 16 bảng SQLite đầy đủ (CREATE TABLE + migration columns + index), file parquet, query mẫu. **Tra ở đây thay vì đọc db.py khi cần schema.**
- `TEST_COVERAGE.md` — bản đồ 31 test file (~320 cases), phân loại ✅/🟡/🔴, danh sách ưu tiên viết test (tab_canh_bao_nqh, data/hstd.py, alert_center, migration_service là cao nhất).
- `DECISIONS.md` — 12 entry ADR (Architecture Decision Record): SQLite/Parquet/DuckDB/kv_store/render(tab=None)/pgd_mode/tiền VND/Streamlit/snapshot/git policy/RBAC/merge strategy.
- `CLAUDE.md` Section 11 — bổ sung 3 dòng SCHEMA/TEST_COVERAGE/DECISIONS vào bảng tài liệu tham chiếu.

---

## [2026-05-22] Fix tab_canh_bao_nqh.py — 3 lỗi runtime

### Bug fixes
- **Root cause lỗi "truth value of a DataFrame is ambiguous"**: `render()` dòng ~580 dùng `kwargs.get("df_full") or kwargs.get("df")` → `or` trên DataFrame kích hoạt `bool(DataFrame)` → exception. Fix: `df_full = kwargs.get("df_full", kwargs.get("df"))`.
- **Series index alignment**: `_render_tong_hop()` dòng ~97 tạo `gh_thang_series = ngay_gh[da_gh]` (subset index) rồi dùng `da_gh & gh_thang_series.dt.year == ...` → lệch index → NaN lan rộng. Fix: dùng `ngay_gh` trực tiếp.
- **Fragile DataFrame.get pattern**: `_render_khd()` dòng ~173 `df_kh[df_kh.get("is_3m_inactive", False)]` → nếu cột missing trả `False`, `df[False]` là KeyError. Fix: kiểm tra explicit `"is_3m_inactive" in df_kh.columns`.

---

## [2026-05-22] Tạo tab_canh_bao_nqh.py

### Tạo mới
- `tabs/tab_canh_bao_nqh.py` — tab Cảnh báo Tín dụng: **render(tab=None, **kwargs)**
  - 8 sub-tabs: Tổng hợp | Đến hạn | 3 tháng KHĐ | BT sang Rủi ro | Nợ QH phát sinh | Cảnh báo sớm | Khoanh sắp hết hạn | Gia hạn nợ
  - Dùng chung `danh_dau_khong_hd_cached`, `canh_bao_migration_cached`, `tong_hop_khong_hd_cached`, `ds_chi_tiet_khong_hd` từ `data/`
  - key_prefix phân biệt `cn_cbtd_` / `pgd_{slug}_cbtd_` tránh DuplicateElementKey
  - Được gọi từ `ws_management._render_canh_bao_no()` (CN) và `ws_operation._render_canh_bao_nqh_pgd()` (PGD)

---

## [2026-05-22] Hoàn thiện tab Trạng thái Nguồn dữ liệu

### Bug fixes
- `tab_trang_thai_nguon.py`: 6 chỗ `except Exception:` → `except Exception as e:` (NameError khi logger ghi `e`)
- `tab_trang_thai_nguon.py`: `_pgd_gqvl_path()` dùng `GQVL_PGD_DIR` (legacy) → thay bằng `_pgd_file_path(ten_pgd, loai)` gọi `duong_dan_pgd()` từ `data/pgd.py` — GQVL không còn luôn hiển thị ❌

### Thêm tính năng
| Nơi | Tính năng |
|---|---|
| `_render_tep_nguon` | Cột CDTOTKVV + metric thứ 4 |
| `_render_merge_cache` | Cột "Số dòng" + "PGD dùng SL cũ" trong bảng merge meta |
| `_render_merge_cache` | Cảnh báo đỏ/vàng + expander danh sách khi có `pgd_cu` |
| `_render_merge_cache` | Section "🔬 Chất lượng dữ liệu" từ `data_quality_meta_*` |
| `_render_he_thong` | Section "🔗 Sao lưu qua GitHub (kv_store)" — gộp từ sidebar `app.py` vào |

### Dọn dẹp
- `app.py` sidebar: xóa block backup 40 dòng, thay bằng caption link đến tab

---

## [2026-05-21] Logging + test coverage cho services quan trọng

### Logging thêm vào
| Service | Nơi thêm |
|---|---|
| `kiem_soat_service.py` | `get_logger(__name__)` + `logger.error` trong `_tinh_to_sai_so_tv` (DuckDB query) |
| `khtd_service.py` | `get_logger(__name__)` + `logger.error` trong `tinh_kh_dau_nam`, `doc_tu_sheet`, `push_kh_len_sheet` (×2), `luu_dot_khtd` |

### Tests mới
| File | Số tests | Covers |
|---|---|---|
| `test_rui_ro_aggregation.py` | 11 | `_loc_theo_nguon`, `_tong_hop_no` |
| `test_kiem_soat_service.py` | 20 | `_tinh_ngaygh_dp`, `_tinh_to_sai_so_tv`, `_fmt_so_cell`, `_ks_html_metric_card`, `_tong_hop_vp/ghv_theo_pgd` |
| `test_word_xln_service.py` | 24 | `_pgd_plain`, `_pgd_line`, `_num`, `_tao_word_01xln` + smoke 6 mẫu |

- Tổng: 421 → 510 tests (509 passed; 1 pre-existing fail `test_data_quality::test_pgd_hop_le`)

---

## [2026-05-21] Dọn dẹp: archive 2 file orphan trong tabs/
- `tabs/pdf_no_khoanh.py` → `_archive/` — bản sao y hệt `services/pdf_no_khoanh_service.py`, không ai import
- `tabs/kiem_soat_service.py` → `_archive/` — phiên bản cũ (34 KB), `services/kiem_soat_service.py` đã là bản cập nhật (38 KB)
- `tab_no_khoanh.py` và `tab_kiem_soat.py` compile OK sau khi dọn

---

## [2026-05-21] Refactor loạt lớn — tách logic thuần vào services/

### Services mới tạo
| Service | Nguồn gốc | Nội dung |
|---|---|---|
| `services/file_detection_service.py` | `tab_upload_khnv` | Nhận diện loại file, đọc tên đơn vị, MD5, TEN_DV_ALIAS |
| `services/word_xln_service.py` | `tab_no_rui_ro` | 18 hàm tạo Word XLN (01/02/04/05/13/14 + Tờ trình PGD/CN) |
| `services/rui_ro_aggregation.py` | `tab_no_rui_ro` | `_loc_theo_nguon`, `_tong_hop_no` |
| `services/task_data_service.py` | `tab_tien_do` | `_doc_tasks`, `_doc_ketqua_task`, `_sync_bien_hoa_ketqua`, etc. |
| `services/tien_do_pdf_service.py` | `tab_tien_do` | `_xuat_pdf_bao_cao_tien_do`, `_xuat_pdf_tien_do` + reportlab helpers |
| `services/pdf_no_khoanh_service.py` | `tabs/pdf_no_khoanh.py` | Toàn bộ module reportlab QLNK (không đổi nội dung) |
| `services/so_sanh_ky_service.py` | `tab_so_sanh_ky` | 11 hàm: `agg_mot_pgd`, `agg_theo_pgd`, `delta_str`, `top_movers`, `phan_tich_hhi_pgd`, ... |
| `services/cdtotkvv_service.py` | `tab_cdtotkvv` | 5 hàm: `tong_hop_tu_pgd_data`, `bang_trang_thai_cdtotkvv`, `loc_df`, ... |
| `services/tongquan_service.py` | `tab_tongquan` | `xuat_excel_tqpgd` |
| `services/khtd_nhap_service.py` | `tab_khtd_nhap` | 7 hàm: `clean_sheet_name`, `tao_df_mau_khtd_cn`, `luu_meta_qd`, `luu_file_qd`, ... |
| `services/khtd_mau07_service.py` | `tab_khtd_mau07` | 21 hàm: slug/KV helpers, `xuat_mau07_word`, `TEN_BY_MAKEY`, ... |
| `services/tien_do_excel_service.py` | `tab_tien_do` | `xuat_excel_tien_do()` — tạo 3-sheet Excel tiến độ với openpyxl |
| `services/no_khoanh_service.py` | `tab_no_khoanh` | `loc_khoanh()`, `bang_theo_nhom()` |
| `services/khnv_noi_bo_service.py` _(bổ sung)_ | `tab_khnv_noi_bo` | constants `_CHUC_VU_*`, `_MAU_GIAO_VIEC` (38), `_MAU_GIAO_VIEC_TP` (17), `_guess_chuc_vu`, `_safe_date_lt` |

### Tabs giảm dòng
| Tab | Trước | Sau | Giảm |
|---|---|---|---|
| `tab_no_rui_ro.py` | 2 411 | ~1 067 | -1 344 (-56%) |
| `tab_tien_do.py` | 1 962 | 1 109 | -853 (-43%) |
| `tab_khnv_noi_bo.py` | 1 802 | 1 039 | -763 (-42%) |
| `tab_upload_khnv.py` | ~1 640 | ~1 332 | -308 (-19%) |
| `tab_so_sanh_ky.py` | 1 405 | ~1 207 | -198 (-14%) |
| `tab_no_khoanh.py` | ~1 367 | 1 217 | -150 (-11%) |
| `tab_cdtotkvv.py` | 1 217 | ~1 097 | -120 (-10%) |
| `tab_khtd_mau07.py` | ~1 100 | ~880 | -220 (-20%) |

### Pattern áp dụng
- Hàm **không có `st.*`** → tách vào `services/`
- Import lại với alias giữ nguyên tên (VD: `from services.X import func as _func`) — call sites không đổi
- Hàm có `@st.cache_data` hoặc gọi `st.*` → giữ nguyên trong tab
- Tất cả file đều pass `python -m py_compile`

---

## [2026-05-20] Redesign tab Nội bộ KH-NV — kiến trúc 6 tab theo luồng 5 bước

### tab_khnv_noi_bo.py — thay đổi toàn diện (~840 → ~1 100 dòng)
- `render()`: 3 sub-tab → 6 sub-tab: 👥 Nhân sự / 📋 Phân công / 📊 Tiến độ / 📄 Báo cáo / 📅 Lịch / 📖 Thông tin đầu việc
- **Hằng số mới**: `KHNV_CAN_BO = "khnv_can_bo_list"` — lưu danh sách cán bộ `{id, ho_ten, chuc_vu: "vp1"|"vp2"|"cbtd"}`
- **Hằng số mới**: `_CHUC_VU_MAP`, `_CHUC_VU_LABEL`, `_CHUC_VU_TASK_FILTER` — mapping chức vụ ↔ nhãn ↔ đầu việc phù hợp
- **Dữ liệu mở rộng**: `_MAU_GIAO_VIEC` 32 → 38 đầu việc (bổ sung: chấm công VP2, KHTD toàn tỉnh VP2, lưu giữ hồ sơ NRR VP2, báo cáo hoạt động VP2, dự toán VP2, tổ GDLĐ VP1+VP2+CBTD)
- **Dữ liệu mới**: `_MAU_GIAO_VIEC_TP` — 17 đầu việc Trưởng phòng TP01–TP17 (tĩnh, chỉ tham chiếu)
- **Hàm mới** `_render_nhan_su(role_n, username)`: Tab 1 — thêm/xóa cán bộ, gom nhóm VP1/VP2/CBTD
- **Hàm mới** `_render_task_card(cv, ds, today, role_n, username, key_prefix)`: helper chung cho Tab 2+3 — 4 cols + quick buttons (🔴/🟡/✅) + expander Chỉnh sửa/Xóa
- **Hàm mới** `_render_phan_cong_v2(role_n, username)`: Tab 2 — dropdown cán bộ → đầu việc lọc theo chức vụ; gom nhóm theo vị trí (VP1/VP2/CBTD/📌); nút tải 38 mẫu từ KHNV_CAN_BO; form thủ công giữ nguyên
- **Hàm mới** `_render_tien_do_edit(role_n, username)`: Tab 3 — mini dashboard + bộ lọc tt/người + task cards
- **Hàm mới** `_render_bao_cao(role_n, username, **kwargs)`: Tab 4 — PDF tiến độ + Excel download + checklist cấp trên (wrapper tab_checklist_bc)
- **Hàm mới** `_render_thong_tin_dau_viec()`: Tab 6 — HTML table tĩnh TP01–TP17 + 38 đầu việc gom nhóm I–VIII
- **Hàm mới** `_tai_mau_tu_kv(ds, username)`: wrapper đọc từ KHNV_CAN_BO → gọi `_tai_mau_giao_viec_v2`
- **Hàm mới** `_guess_chuc_vu(cv)`: fallback đoán chức vụ từ `nguoi_thuc_hien` cũ → backward-compatible
- **Hàm mới** `_safe_date_lt(date_str, ref)`: helper parse date an toàn
- **Xóa**: `_render_phan_cong()` (thay bởi v2 + task_card)
- **Backward compat**: task cũ không có field `chuc_vu` → `_guess_chuc_vu()` tự suy luận, không cần migration
- Import thêm: `xuat_excel` từ `utils`; `_tai_mau_giao_viec_v2` giờ tạo task có thêm field `chuc_vu`
- `tabs/tab_khnv_noi_bo.py` sub-tab 📋 Phân công cán bộ: thêm nút "📥 Xuất PDF" — chuyển list dict → DataFrame (Tiêu đề, Người thực hiện, Mức ưu tiên, Ngày giao, Deadline, Trạng thái, Ghi chú) → `xuat_pdf_co_chart` với `them_dong_tong=False`
- `tabs/tab_khnv_noi_bo.py` sub-tab 📅 Lịch công tác: thêm nút "📥 Xuất PDF" — xuất danh sách đã lọc theo tháng/năm/loại (Ngày, Loại, Tiêu đề, Địa điểm, Thành viên, Ghi chú, Trạng thái)

## [2026-05-20] Tải đầu việc mẫu — nhân bản CB TD theo tên thực tế
- `tabs/tab_khnv_noi_bo.py` — `_tinh_so_task()` + `_tai_mau_giao_viec_v2()`: nhân bản task "Cán bộ TD" × N người; form 2 ô VP + 6 ô CB TD + live count ước tính task
- `tabs/tab_khnv_noi_bo.py` — `_MAU_GIAO_VIEC` (32 task, 8 nhóm), `_tai_mau_giao_viec()`, nút tải mẫu trong `_render_phan_cong()` (nổi bật khi trống / expander khi đã có data)

## [2026-05-20] Sub-tab "📊 Tiến độ thực hiện" trong Nội bộ Phòng KH-NV
- `tabs/tab_khnv_noi_bo.py` — thay "Giao việc PGD" (wrapper tab_tien_do) bằng `_render_tien_do_thuc_hien()`: tổng hợp tự động từ `khnv_phan_cong_list`
- Gồm: filter tháng/năm/cán bộ, 5 metric, progress bar màu theo % (đỏ/cam/xanh/lá), badge trễ hạn, bảng chi tiết, PDF export

## [2026-05-20] Nút PDF luôn hiển thị trong tab Nội bộ Phòng KH-NV
- `tabs/tab_khnv_noi_bo.py` — cả 2 sub-tab (Phân công cán bộ + Lịch công tác): nút "📥 Xuất PDF" luôn render, `disabled=True` khi chưa có dữ liệu, active khi có; tháng lọc không có sự kiện → disabled

## [2026-05-20] Fix dark mode bảng tổng hợp PGD (tab_tongquan)
- `tabs/tab_tongquan.py` dòng ~1186: thêm `color:#1a202c` vào `<tr style="background:{bg}">` → chữ đen rõ trên nền sáng ở dark mode
- `tabs/tab_tongquan.py` dòng ~1197: `<p style="color:#6B7280">` → `<div style="opacity:0.65">` để footnote thích ứng dark/light theme

## [2026-05-20] Fix danh_dau_khong_hd — Categorical date columns
- `data/hstd.py` hàm `danh_dau_khong_hd()` dòng ~238: cột ngày trong df có thể là Categorical (do Parquet cache); thêm `.astype(object)` trước `pd.to_datetime()` cho `COT_NGAY_SL`, `COT_NGAY_GDGN`, `COT_NGAY_VAY`

---

## CẤU TRÚC THƯ MỤC HIỆN TẠI

```
├── app.py, auth.py, config.py, db.py, utils.py
├── snapshot_service.py, alert_center.py, health_check.py
├── pdf_service.py, gen_dcgiam_sheet.py
│
├── data/
│   ├── core.py, hstd.py, pgd.py, khtd.py
│   ├── cdtotkvv.py, den_han.py, dgd_helpers.py, giao_ban.py
│
├── components/
│   ├── delta_card.py, export_pdf.py, filter_bar.py
│   ├── loan_drawer.py, movers.py
│
├── services/
│   ├── upload_service.py, report_service.py, template_service.py
│   ├── ct_discovery.py, excel_service.py, khtd_service.py
│   ├── hhi_service.py, kiem_soat_service.py, period_compare.py
│   ├── du_phong_service.py, data_quality.py, migration_service.py
│   ├── file_detection_service.py  ← nhận diện loại file upload
│   ├── word_xln_service.py        ← Word XLN (01/02/04/05/13/14 + Tờ trình)
│   ├── rui_ro_aggregation.py      ← tổng hợp nợ rủi ro
│   ├── task_data_service.py       ← DB helpers cho tiến độ công việc
│   ├── tien_do_pdf_service.py     ← PDF báo cáo tiến độ
│   ├── pdf_no_khoanh_service.py   ← reportlab PDF QLNK
│   ├── so_sanh_ky_service.py      ← tổng hợp so sánh kỳ
│   ├── cdtotkvv_service.py        ← dữ liệu CDTOTKVV
│   ├── tongquan_service.py        ← Excel tổng quan PGD
│   ├── khtd_nhap_service.py       ← nhập KHTD, lưu meta QĐ
│   ├── khtd_mau07_service.py      ← Word mẫu 07 + KV helpers
│   ├── khnv_noi_bo_service.py     ← Word NĐ30/2020 + KV phân công/lịch
│
├── tabs/                        # 40+ tabs
│   ├── tab_tongquan.py, tab_tracuu.py, tab_candoi.py
│   ├── tab_khtd.py, tab_khtd_pgd.py, tab_khtd_nhap.py
│   ├── tab_khtd_giao_dc.py, tab_khtd_mau07.py, tab_khtd_xuat.py
│   ├── tab_gqvl.py, tab_nq11.py, tab_cbtd.py
│   ├── tab_baocao.py, tab_nhiem_vu.py, tab_tien_do.py
│   ├── tab_upload_khnv.py, tab_upload_pgd.py
│   ├── tab_ban_dai_dien.py      # 4 sub-tab: KPI, dự báo vốn, họp BĐD, sổ công văn
│   ├── tab_khnv_noi_bo.py       # 4 sub-tab: Phân công cán bộ, Lịch công tác, BC cấp trên, Giao việc PGD
│   ├── tab_tien_do_nop.py       # Tiến độ nộp PGD từ GSheet
│   ├── tab_quan_ly_bc.py        # Wrapper: 📥 BC từ PGD + 📤 BC lên cấp trên
│   ├── tab_checklist_bc.py      # Checklist deadline báo cáo (kv_store)
│   ├── tab_xlrr_tong_hop.py     # XLRR 4 sub-tab
│   ├── tab_trang_thai_nguon.py  # Health check 6 sub-tab (mức B)
│   ├── tab_danhsach.py, tab_tracuu.py, tab_den_han.py
│   ├── tab_no_khoanh.py, tab_no_rui_ro.py, tab_hhi.py
│   ├── tab_so_sanh_ky.py, tab_canh_bao_som.py
│   ├── tab_cdtotkvv.py, tab_cdtotkvv_pgd.py
│   ├── tab_kiem_soat.py, tab_audit_log.py
│   ├── tab_diem_gd_pgd.py, tab_quan_ly_dgd.py
│   ├── tab_uy_thac.py, tab_qd62.py, tab_kh_gqvl.py, tab_kehoach.py
│
├── workspaces/
│   ├── ws_executive.py     # BGĐ — gauge, heatmap
│   ├── ws_management.py    # CN — render_sidebar_menu() + _build_all_items()
│   └── ws_operation.py     # PGD — lọc theo pgd_user
│
├── widgets/
│   ├── data_source_status.py, status_widget.py
│
├── templates/               # Word templates (.doc/.docx)
├── tests/                   # fixtures.py, test_pdf_service.py, test_smoke_snapshot.py
├── _archive/                # Deprecated files — không import
├── khtd-targets-app/        # React app (độc lập)
├── cache/                   # Parquet runtime: hstd.parquet, nq11.parquet, gqvl.parquet
├── pgd_data/                # Upload PGD: pgd_data/{slug}/hstd_latest.xlsx
└── docs/                    # ARCHITECTURE.md, CHANGELOG.md, ROLES.md, ...
```

---

## KIẾN TRÚC WORKSPACE

### ws_management (CN role) — sidebar _build_all_items()
```
THÔNG TIN CHUNG   → 📊 Thông tin chung (mặc định khi mở app)
PHỐI HỢP VỚI PGD → Tiến độ Công việc ▸ (📅 Tiến độ công việc)
                  → 📋 Quản lý Báo cáo định kỳ (tab_quan_ly_bc)
                  → 📌 Nhiệm vụ PGD
GIÁM SÁT          → Cảnh báo NQH ▸ | 📊 So sánh kỳ
KIỂM SOÁT         → Kiểm soát nội bộ | Xử lý nợ rủi ro | Cán bộ tín dụng
                  → Tập trung rủi ro & HHI | 🔒 Chuyên Đề Nợ Khoanh ▸
KẾ HOẠCH KHTD     → Kế hoạch tín dụng | Giao & ĐC KHTD | Cân đối - Điện báo
                  → 📡 Điện báo | Xuất báo cáo KHTD
BÁO CÁO           → Báo cáo tín dụng ▸ (📊 Báo cáo tín dụng | ⏰ Nợ Đến Hạn)
ỦY THÁC           → 🏛️ Ban Đại Diện | 🤝 Ủy thác | Điểm GD & Tổ TK&VV ▸
HỆ THỐNG          → Template | Mã NĐT | Nhật ký | Trạng thái | Upload | Hướng dẫn
```

### ws_operation (PGD role)
```
Nhóm tab: Tác nghiệp | Upload | Kế hoạch PGD | Báo cáo PGD
```

### ws_executive (executive role)
```
Dashboard: gauge KPI, heatmap 22 đơn vị
```

### Pattern tab trong workspace
```python
CAC_NHOM = {
    "nghiep_vu": {
        "label": "📋 Nghiệp vụ",
        "tabs": [
            ("🔍 Tra cứu", lambda tab: tab_tracuu.render(tab, **kwargs)),
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

## KIẾN TRÚC XỬ LÝ DỮ LIỆU

```
Excel gốc (data/*.xlsx)
  → excel_to_parquet()     → cache/*.parquet (PyArrow + zstd)
  → DuckDB read_parquet()  → aggregate lazy scan
  → Streamlit render

Upload flow:
  Phòng KH-NV (tab_upload_khnv):
    → luu_file_he_thong() → merge_du_lieu_toan_cn() → cache/*.parquet
  PGD (tab_upload_pgd):
    → luu_pgd_file() → pgd_data/{slug}/hstd_latest.xlsx
```

---

## THAM CHIẾU NHANH

| Yêu cầu | File |
|---|---|
| Thêm tab PGD | `tabs/tab_*.py` + `ws_operation.py` |
| Thêm tab toàn CN | `tabs/tab_*.py` + `ws_management.py` |
| Tab wrapper 2 sub-module | `tabs/tab_quan_ly_bc.py` — pattern wrapper gọi render() con |
| Sửa merge 22 PGD | `upload_service.py` → `merge_du_lieu_toan_cn()` |
| Thêm chương trình TD | `config.py` → `CHUONG_TRINH_KHTD` |
| Thêm PGD mới | `config.py` → `DS_PGD`, `MA_PGD_MAP`, `PGD_XA_MAP` |
| Sửa format tiền | `utils.py` → `fmt_ty()` |
| Sửa đọc HSTD | `data/hstd.py` hoặc `data/core.py` |
| Xuất PDF | `components/export_pdf.py` |
| Template Word | `services/template_service.py` |
| Filter + Drill-down | `components/filter_bar.py`, `components/loan_drawer.py` |
| Cảnh báo sidebar | `alert_center.py` → `render_alert_sidebar()` |
| Snapshot HSTD | `snapshot_service.py` |
| Giao KHTD | `khtd_service.py` + `tab_khtd_giao_dc.py` |

---

## FILE DEPRECATED

| File | Lý do |
|---|---|
| `_archive/_tab_quantri_deprecated.py` | Tab quản trị cũ |
| `_archive/tab_baocao_backup.py` | Backup trước refactor |
| `_fix_all_buttons.py` | Script fix 1 lần |
| `_fix_template_service.py` | Script fix 1 lần |

---

## CHANGELOG

## [20/05/2026] — Fix _load_hstd: arrow() → to_arrow_table()
- `app.py` dòng ~134 — `duckdb.query().arrow()` trả về `RecordBatchReader` (không có `.to_pandas()`); catch Exception thầm lặng → ws_executive hiển thị "Chưa có dữ liệu HSTD"; fix: đổi sang `.to_arrow_table().to_pandas(self_destruct=True)`

## [19/05/2026] — tab_tien_do, ws_management, tab_quan_ly_bc, kiem_soat fix
- `tabs/tab_tien_do.py`: form tạo/sửa task — section "Áp dụng cho đơn vị" tách Phần A "🏢 Phòng giao dịch trực thuộc" + Phần B "🏛️ Hội sở CN tỉnh"; caption tổng quan + hướng dẫn từng phần; nhãn "CB Biên Hòa" → "Hội sở CN tỉnh" toàn bộ UI
- `tabs/tab_tien_do.py`: drill-down thêm "— Tất cả —" đầu selectbox; khi chọn hiển thị toàn bộ bản ghi kèm cột "Đơn vị"
- `tabs/tab_quan_ly_bc.py` **(MỚI)**: wrapper thuần — 2 sub-tab "📥 BC từ PGD" (tab_tien_do_nop) + "📤 BC lên cấp trên" (tab_checklist_bc); dùng get_tab_context(tab)
- `workspaces/ws_management.py`: fix DuplicateElementKey — xóa bản duplicate "📊 Thông tin chung"; đưa "Thông tin chung" lên đầu ALL_ITEMS (mục mặc định); thêm "📋 Quản lý Báo cáo định kỳ" vào nhóm "Phối hợp với PGD"; chuyển "📌 Nhiệm vụ PGD" từ "Giám sát" sang "Phối hợp với PGD"
- `services/kiem_soat_service.py`: thêm import `COT_PL_NV`; đổi hardcode `"PL NV"` → `COT_PL_NV` ("Phân loại NV") — fix báo cáo GQVL TW gắn MĐT không tìm thấy cột

## [19/05/2026]
- `tabs/tab_tien_do.py` form tạo/sửa task: thêm caption tổng quan, tách Phần A (🏢 PGD huyện/thị xã) + Phần B (🏛️ Hội sở CN tỉnh), đổi nhãn text_input "Cán bộ KH-NV phụ trách", caption hướng dẫn sau từng phần
- `tabs/tab_tien_do.py` nhãn bảng/info/Excel: "CB Biên Hòa" → "Hội sở CN tỉnh" (bảng tổng quan, info task, sheet Excel báo cáo)

## [15/05/2026]
- `tabs/tab_tien_do.py`: Thêm nút "📄 Xuất PDF báo cáo tiến độ" (sub-tab Xuất báo cáo) — tạo 1 file PDF 2 phần (Phần 1: Tiến độ theo đầu việc, Phần 2: Báo cáo trễ hạn) dùng Times New Roman + Table grid
- `tabs/tab_tien_do.py`: `_xuat_pdf_bao_cao_tien_do()` — hỗ trợ 2 mẫu theo `cap_theo_doi`: `pgd` (bảng 4 cột: STT/PDG/Trạng thái/Ghi chú) và `xa` (bảng 5 cột: STT/PGD/Xã/Trạng thái/Ghi chú) với xen kẽ dòng, grid xám
- `tabs/tab_tien_do.py`: Phần 2 (trễ hạn) dùng Table grid giống Phần 1, header đỏ `#C62828`, xen kẽ hồng `#FFEBEE`
- `tabs/tab_tien_do.py`: Thêm màu sắc cột Trạng thái — `td_green` `#2E7D32` cho Hoàn thành, `td_red` `#C62828` cho Chưa thực hiện (dùng ParagraphStyle riêng, không dùng TableStyle TEXTCOLOR vì không hoạt động với Paragraph)
- `tabs/tab_tien_do.py`: Đổi nhãn metadata: "Deadline" → "Thời hạn cuối cùng", "Tiến độ" → "Tiến độ hoàn thành"; tăng font size (header 13, meta 11, table 11, p2 11, chữ ký 12)
- `tabs/tab_tien_do.py`: Thêm chữ ký cuối báo cáo: Người lập, Kiểm soát, Giám đốc (ký, ghi rõ họ tên, đóng dấu)
- `tabs/tab_tien_do.py`: Tăng colWidths cột STT, PGD để tên PGD không bị xuống dòng (pgd 4 cột: 1.5/7.0/3.5/6.0cm, xa 5 cột: 1.2/5.2/4.3/3.3/4.0cm)
- `tabs/tab_tien_do.py`: Xóa toàn bộ mục "🔴 Báo cáo trễ hạn" cũ (nút PDF trễ hạn + Excel trễ hạn + metric cards) và xóa hàm `_xuat_pdf_tre_han()` (~245 dòng) — chức năng đã có trong Phần 2 của PDF báo cáo tiến độ mới
- `.streamlit/config.toml`: Đổi `fileWatcherType = "watchdog"` → `"poll"` để Streamlit tự động reload khi sửa bất kỳ file .py (không chỉ app.py)
- `tabs/tab_tien_do.py`: Thêm `_xuat_excel_tien_do()` — thay thế `pd.ExcelWriter` trần bằng openpyxl styling: header xanh `#003D7A` chữ trắng bold, border `#BDBDBD`, xen kẽ dòng xanh nhạt `#EEF4FB`, auto-width cột, number format `#,##0` cho cột số, `0.0"%"` cho Tỷ lệ HT%, font Times New Roman; đổi nhãn nút tải "⬇ Tải Excel báo cáo tiến độ"
- `tabs/base_tab.py` **(MỚI)**: Thêm `TabContext` class — base context cho mọi tab render; centralizes kwargs extraction (`role`, `username`, `pgd_user`, `df_full`), role normalization, tab container fallback (`tab if tab is not None else st.container()`), và các property tiện lợi (`is_cn`, `is_exec`, `is_pgd`, `role_norm`)
- `tabs/tab_tien_do.py`: Refactor `render()` và `render_tong_quan_only()` dùng `TabContext` — thay `normalize_role()` + `_tab_ctx` manual bằng `ctx = TabContext(tab, **kwargs); with ctx:`
- `tabs/tab_baocao.py`: Refactor `render()` dùng `TabContext` — giảm 10 dòng setup code, thay `normalize_role()` bằng `ctx.role_norm`

## [17/05/2026]
- `tabs/tab_trang_thai_nguon.py`: Implement mới hoàn toàn — 6 sub-tab health check mức B (tệp nguồn, merge & cache, snapshot, người dùng, hệ thống, audit log)
- `ws_management.py`: refactor `render_sidebar_menu()` + `_build_all_items()`
- `auth.py`: thêm `chuyenvien_cn` role, hệ thống 2 cấp 7 role hoàn chỉnh
- `snapshot_service.py`: `hstd_snapshot` by period, upsert-safe, auto-trigger post-merge
- `tab_ban_dai_dien.py`: 4 sub-tab (KPI + export, dự báo vốn, họp BĐD, sổ công văn)
- `tab_tien_do_nop.py`: tiến độ nộp PGD từ GSheet
- `tab_checklist_bc.py`: checklist deadline báo cáo via kv_store
- `tab_xlrr_tong_hop.py`: XLRR consolidated 4 sub-tab
- B7 refactor: normalize_role() thay hardcoded role check trong 6+ file
- `config.py`: thêm `COT_DU_NO_KHOANH` constant
- `tabs/tab_baocao.py`: refactor hardcode tên cột → `COT_*` constants (~40 replacements)
- `tabs/tab_danhsach.py`: hardcode `"Tên ĐVUT"`, `"Dư nợ khoanh"` → `COT_*`
- `tabs/tab_khtd_mau07.py`: xóa fallback patterns, dùng `COT_*` trực tiếp
- `tabs/tab_so_sanh_ky.py`: hardcode `"Ngày số liệu"`, `"Dư nợ khoanh"` → `COT_*`
- `tabs/tab_khtd.py`: `row.get("Nguồn vốn")`, `row.get("Mã nhà đầu tư")` → `COT_*`
- `tabs/tab_khtd_nhap.py`: `df.get("Mã nhà đầu tư")` → `COT_MA_NHA_DAU_TU`
- `tabs/tab_no_khoanh.py`: `nhom["Dư nợ khoanh"]` → `COT_DU_NO_KHOANH`
- `tabs/tab_tongquan.py`: `"Dư nợ khoanh"`, `"Tên xã"` → `COT_*`
- `services/ct_discovery.py`: `row.get("Nguồn vốn")`, `row.get("Phân loại NV")`, `row.get("Mã nhà đầu tư")` → `COT_*`
- `services/hhi_service.py`: `"Tổng dư nợ"` → `COT_TONG_DU_NO` + thêm import
- `services/kiem_soat_service.py`: `"Tên tổ"` (x9) → `COT_TEN_TO` + thêm import
- `services/upload_service.py`: `_cols_so` list → 10 `COT_*` constants + imports
- `scripts/check_hardcode_cols.py`: script kiểm tra hardcode column names (diff mode + full mode)
- `scripts/setup_hooks.py`: cài đặt Git pre-commit hook cho team
- `.git/hooks/pre-commit`: Git hook tự động chạy `check_hardcode_cols.py` khi commit
- `.trae/rules/rules.md`: section 10 — hướng dẫn pre-commit hook
- `app.py`: SQL `"Dư nợ khoanh"` → `COT_DU_NO_KHOANH` + import
- `utils.py`: `"Tên ĐVUT"` → `COT_DVUT` (3 hits)
- `workspaces/ws_operation.py`: `"Tên ĐVUT"` (x14) + `"Tên xã"` (x12) → `COT_*`
- `workspaces/ws_management.py`: `"Nguồn vốn"`, `"Dư nợ trong hạn"`, `"Dư nợ quá hạn"`, `"Tên ĐVUT"` → `COT_*` + imports
- `workspaces/ws_executive.py`: thêm `# noqa: COT` cho display labels (8 vị trí)
- `components/movers.py`: thêm `# noqa: COT` cho UI label dict

## [19/05/2026] — Hoàn thiện tab Nợ khoanh từ A-Z
- `db.py`: Thêm bảng `qlnk_ke_hoach` (13 cột + 3 index) vào `_init_db()`; thêm migration silent cho 3 cột mới; thay thế 3 stub functions (`doc_ke_hoach_kiem_tra`, `luu_ke_hoach_kiem_tra`, `duyet_ke_hoach`) bằng SQLite thật — hoàn thiện luồng d5 Kế hoạch và d7 Báo cáo Mẫu KH
- `tabs/tab_no_khoanh.py`: Import + dùng `get_tab_context(tab)` thay `tab if tab is not None else st.container()`
- `tabs/tab_no_khoanh.py` + `db.py`: **Redesign toàn bộ d5 Kế hoạch** — kế hoạch phân công cả năm: chọn năm + PGD → load toàn bộ món khoanh → data_editor điền ngày KT dự kiến từng món (không validate 120 ngày ở đây) → lưu JSON `ds_phan_cong`; schema `qlnk_ke_hoach` dùng `nam INTEGER` + `ds_phan_cong JSON`
- `tabs/tab_no_khoanh.py`: Mẫu 03/QLNK — viết lại hoàn toàn `_xuat_pdf_mau_03qlnk()` khớp mẫu thực tế: header 2 cột (đơn vị | Mẫu số), tiêu đề + khoảng thời gian, "Đơn vị ủy thác", gộp dòng theo khách hàng (SPAN dọc STT+Tên KH cho KH nhiều món), lọc `< 120 ngày`; UI thêm input Từ ngày/Đến ngày/Mã tổ/ĐVUT

## [19/05/2026]
- `scripts/check_conventions.py`: thêm encoding fix cho Windows — `import os` + `os.environ.setdefault("PYTHONIOENCODING", "utf-8")` + `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`
- `scripts/check_conventions.py`: sửa typo `fromfrom __future__ import annotations` → `from __future__ import annotations`; xóa duplicate `os.environ.setdefault()`
- Dọn temp files: xóa `_fix_final.py`, `_fix_noqa.py`, `_fix_noqa2.py`, `_refix.py`
- `.streamlit/config.toml`: đổi theme `light` → `dark` (nền tối `#0E1117`, chữ trắng `#FFFFFF`, primary `#42A5F5`)
- `app.py`: rewrite toàn bộ CSS (18 section) từ light theme → dark theme — sidebar navy `#1A1D2E`, main area `#0E1117`, card `#1E2130`, border `#2A2D3E`, chữ sáng `#CBD5E1`/`#F0F4F8`; giữ nguyên màu xanh `#2E7D32` accent
- `tests/test_period_compare.py`: viết mới toàn bộ — 5 test class, 23 test method cho join_by_loan, classify_changes, roll_cure_rate, vintage_nqh, par_breakdown
- `tabs/tab_ban_dai_dien.py`: fix ValueError "truth value of DataFrame is ambiguous" — thay `kwargs.get("df_full") or kwargs.get("df")` bằng check None/empty
- `tabs/tab_no_khoanh.py`: Mở rộng 2 sub-tab mới d5 "Kiểm tra" và d6 "Báo cáo" — form nhập kết quả kiểm tra (Mẫu 01/QLNK), lưu tạm/phê duyệt, báo cáo M08/M09/M10 + tiến độ kiểm tra theo PGD
- `workspaces/ws_operation.py`: Thêm tab "🔒 Nợ khoanh" vào nhóm Kiểm soát & Rủi ro — gọi tab_no_khoanh.render() với df=df_pgd, df_full=None
- `workspaces/ws_management.py` + `workspaces/ws_operation.py`: Đồng bộ tên 15 tab giống nhau giữa CN và PGD — thêm emoji + thống nhất tên gọi (Thông tin chung, Tiến độ công việc, Báo cáo tín dụng, Điện báo, Nhiệm vụ, So sánh kỳ, Nợ khoanh, Giao & ĐC KHTD, Ban Đại Diện, Ủy thác, Trạng thái hệ thống, Hướng dẫn)
- `tabs/tab_no_khoanh.py`: Fix lỗi `username` not defined trong render() + sửa anti-pattern 5 expander xuất Word (Mẫu KH, 01–04/QLNK) — dùng `nut_tai_word_va_pdf()` + `hien_thi_nut_tai()` từ template_service thay vì `st.download_button` inline trong `if st.button()`
- `tabs/tab_no_khoanh.py`: **Chuyển toàn bộ 5 biểu mẫu từ python-docx → reportlab PDF** — xóa ~650 dòng code Word `_qlnk_*` helpers + `_tao_word_*` + import `docx`/`template_service`; thêm reportlab PDF engine: đăng ký font TNR, header logo NHCSXH + quốc hiệu, style body/table/signature, 5 hàm `_xuat_pdf_mau_*` (KH, 01–04/QLNK) với Times New Roman 12-13pt, line-spacing 1.3-1.5, bảng xanh #2E7D32 xen kẽ dòng, chữ ký chuyên nghiệp, không phụ thuộc MS Word
- `tabs/tab_no_khoanh.py`: Sửa 5 expander UI: nút "📄 Tạo Word" → "📥 Xuất PDF", thêm form editable tối giản (Cán bộ KT, Nội dung bổ sung, Kết luận, Số tiền cam kết/thời hạn/phương thức, Ghi chú, Hạn cuối), lưu PDF vào session_state + download button

## [19/05/2026] — tab_tracuu: bổ sung cột Ngày sinh, Ngày cấp/Nơi cấp CMND
- `tabs/tab_tracuu.py`: import `COT_NGAY_SINH`, `COT_NGAY_CAP_CMND`, `COT_NOI_CAP_CMND` từ config; thêm 3 cột vào `COLS_CAN` (đọc từ parquet khi tra cứu); thêm vào `_NHOM_TRUONG["👤 Khách hàng"]` để hiện trong bộ lọc cột

## [19/05/2026] — Chuyên Đề Nợ Khoanh: dropdown 2 nhóm (Tổng quan / CV368)
- `tabs/tab_no_khoanh.py`: kwarg `nhom` điều khiển hiển thị; d0/loop/d4 guard; early return khi nhom="tongquan"
- `workspaces/ws_management.py`: `children` pattern 2 mục — xổ xuống như Cảnh báo NQH
- `workspaces/ws_operation.py`: 2 tuple tab riêng thay 1
- `alert_center.py`: ws_mgmt_jump → "🔒 Quản lý Nợ Khoanh theo CV 368"

## [19/05/2026] — Đổi tên tab Nợ Khoanh → Chuyên Đề Nợ Khoanh toàn hệ thống
- `workspaces/ws_management.py`: label sidebar `"🔒 Nợ Khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `workspaces/ws_operation.py`: label tab PGD `"🔒 Nợ khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `alert_center.py`: `ws_mgmt_jump` key cập nhật khớp label mới
- `tabs/tab_no_khoanh.py`: subheader `"🔒 Phân tích Nợ khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `tabs/tab_qlnk_dashboard.py`: subheader + hint text cập nhật tên mới

## [19/05/2026] — Mẫu 02/QLNK tự điền từ HSTD (năm sinh, CMND, chương trình)
- `config.py`: Thêm 3 constant — `COT_NGAY_SINH = "Ngày sinh"`, `COT_NGAY_CAP_CMND = "Ngày cấp CMND"`, `COT_NOI_CAP_CMND = "Nơi cấp CMND"`
- `tabs/tab_no_khoanh.py`: `_xuat_pdf_mau_02qlnk()` — import 3 constant mới; tự rút năm sinh từ `COT_NGAY_SINH`; điền ngày cấp + nơi cấp CMND; điền tên chương trình vay vốn; các trường SĐT/địa chỉ/tổ/ĐVUT đã có từ trước

## [19/05/2026] — Fix tab Ban Đại Diện: TypeError truediv on PyArrow string dtype
- `tabs/tab_ban_dai_dien.py`: `_tong_hop_theo_pgd()` — thêm `_num()` helper (`pd.to_numeric(errors='coerce').fillna(0)`) cho du_no/dth/dqh/nkh/gn_nam sau groupby, tránh lỗi khi cột nguồn có dtype PyArrow large_string

## [19/05/2026] — Xuất PDF Kế hoạch kiểm tra nợ khoanh (theo NĐ 30)
- `tabs/tab_no_khoanh.py`: Thêm `_xuat_pdf_ke_hoach_kt(data_kh, ds_phan_cong, thanh_phan, ten_pgd, nam)` — PDF A4 dọc (≤20 món) hoặc landscape (>20 món); header 2 cột NĐ 30 (NHCSXH + CHXHCNVN); bảng phân công 8 cột gộp SPAN theo tên tổ; dòng tổng cộng; thành phần tham gia 5 mục; footer ký duyệt NGƯỜI LẬP / GIÁM ĐỐC
- `tabs/tab_no_khoanh.py`: Expander "Lập / cập nhật kế hoạch": thêm section "📋 Thành phần tham gia kiểm tra" (5 text_input: NHCSXH, Ban QL tổ prefill từ tổ trưởng, CT-XH, Trưởng thôn, UBND xã) + nút "📄 Xuất PDF Kế hoạch" (hiện khi `_rows_kh_pdf` không rỗng hoặc `df_kh_form` có dữ liệu); session state key `kh_pdf_buf`

## [19/05/2026] — Cải tiến tab Nợ Khoanh (heatmap, đơn vị, merge menu, cấu trúc sub-tab)
- `tabs/tab_no_khoanh.py`: `_heatmap_dao_han()` đổi tiêu đề → "Phân bổ theo năm hết hạn khoanh nợ", data source COT_NGAY_DH → COT_NGAY_HH_KHOANH
- `tabs/tab_no_khoanh.py`: Chuẩn hóa tên PGD runtime — thay "Đồng Nai"/"CN Đồng Nai"/"Hội sở" → `DON_VI_CHI_NHANH` sau khi lọc `df_kh`
- `tabs/tab_no_khoanh.py`: Thêm `_fmt_dong` lambda dùng `fmt_so()` — bảng tổng hợp hiển thị "triệu đồng" (cột đổi tên), bảng chi tiết hiển thị "X.XXX.XXX đồng"
- `tabs/tab_no_khoanh.py`: Import `tab_qlnk_dashboard`; đổi 7 → 8 st.tabs; thêm d0 "📊 Tổng quan" gọi `tab_qlnk_dashboard.render(d0, **kwargs)`
- `workspaces/ws_management.py`: Xóa cấu trúc `children` 2 mục Nợ Khoanh → 1 entry "🔒 Nợ Khoanh" duy nhất gọi `tab_no_khoanh.render()`
- `Chay_VBSP_SCM.bat`: Xóa `taskkill`, xóa `--server.fileWatcherType none` (bật lại watchdog auto-reload), thay poll loop 60s bằng `timeout /t 3`

## [19/05/2026] — Tối ưu tốc độ load tab Nợ khoanh (#1-#3)
- `tabs/tab_no_khoanh.py`: Thêm 4 cached wrapper `@st.cache_data(ttl=60)` — `_cached_ket_qua_kiem_tra`, `_cached_ke_hoach_kiem_tra`, `_cached_mau_bieu_cv368` (60s), `_cached_bo_sung_mon_vay` (30s); thay tất cả 16 `db.doc_*()` read call trong render() và `_render_mau*()` bằng cached version
- `tabs/tab_no_khoanh.py`: Lazy-load section "Xuất mẫu biểu theo CV 368" — wrap 5 expander trong `st.checkbox("📄 Hiện mẫu biểu xuất PDF", value=False)` để skip toàn bộ DB queries + UI khi chưa check
- `tabs/pdf_no_khoanh.py`: **Tách module mới** — move toàn bộ PDF helpers + 9 hàm `_xuat_pdf_*()` (~1386 dòng) từ `tab_no_khoanh.py` sang file riêng; `tab_no_khoanh.py` giảm từ 3764 → 2378 dòng
- `tabs/tab_no_khoanh.py`: Remove `try/except reportlab` + `BytesIO`/`Path` import; thay bằng `from tabs.pdf_no_khoanh import (...)`
- `tabs/pdf_no_khoanh.py`: Fix missing imports — thêm `from config import (... 17 COT_* + LY_DO_KHOANH_LABEL)`, `from utils import fmt_so` + `_fmt_dong` lambda; test thực tế: 5 hàm PDF tạo file 100-113KB OK với font TNR + logo NHCSXH
- `tabs/tab_no_khoanh.py`: Fix `SyntaxError: keyword argument repeated: use_container_width` trên `st.dataframe()` line 961
- `tabs/tab_no_khoanh.py`: Đổi 8 → 7 st.tabs; gộp d5 (Kế hoạch) + d6 (Kiểm tra) + mẫu biểu vào tab mới "📋 Kiểm tra nợ khoanh (theo CV 368)"; d_bc "📊 Báo cáo" giữ M08/M09/QLNK_06/M10/Tiến độ; `pgd_filter_bc`/`rows_all_kt`/`da_kiem_tra_set` chuyển trước `st.tabs`

## [19/05/2026] — Khóa Dark Mode toàn hệ thống + sửa 14 vị trí màu hardcode
- `utils_theme.py`: Xóa `_LIGHT` tokens + `toggle_theme()` + `_tokens()`; `get_theme_css()` không nhận param; `init_theme()` luôn trả `"dark"`; bỏ `import db`
- `app.py`: Xóa nút toggle `🌙/☀️` khỏi sidebar; bỏ `toggle_theme` import; `get_theme_css()` không param
- `components/loan_drawer.py`: Drawer `background:#1E2130` + text `#E0E6ED` + label `#94A3B8` + border `#2A2D3E` + group title `#66BB6A` + hover `#0D2818`
- `components/delta_card.py`: Info icon `#6b7a8d` → `#94A3B8`, border `#ccc` → `#2A2D3E`
- `components/movers.py`: 7 hardcoded colors → dark: bg `#0D2818`/`#2D0D14`, border `#66BB6A`/`#EF5350`, text `#94A3B8`/`#81C784`/`#EF9A9A`, kpi box `#1E2130`
- `tabs/tab_tracuu.py`: 8 hardcoded colors → dark: label `#94A3B8`, value `#E0E6ED`, card bg `#1E2130`, badge `#1B5E20/#2D0D14`, NQH `#2D0D14/#EF9A9A`, border `#EF5350/#42A5F5`
- `tabs/tab_khtd_nhap.py`: ~30 hardcoded header colors → dark: TW `#0D2137/#90CAF9`, DP `#0D2818/#81C784`, Tổng `#2D1F0D/#FFD54F`, empty `#262B3D`, muted `#64748B`, text `#E0E6ED`
- `.streamlit/config.toml`: `base="dark"` giữ nguyên — toàn bộ app chỉ dark mode

## [20/05/2026] (Batch 2)
- 	abs/tab_tongquan.py: Thay st.tabs 4 sub-tabs d�o h?n b?ng lazy_tabs()  ch? render 1 tab
- 	abs/tab_baocao.py: Thay st.tabs B�o c�o chi ti?t / NQ11 b?ng st.radio  ch? render tab du?c ch?n
- workspaces/ws_operation.py: X�a eager import 21 tab module kh?i 
ender(), d�ng _lazy_tab() lazy-load
