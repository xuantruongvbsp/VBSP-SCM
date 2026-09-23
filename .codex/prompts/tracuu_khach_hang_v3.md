# Prompt cải tiến & nâng cấp Tab "🔍 Tra cứu Khách hàng" (v3)

> Dành cho: **DeepSeek** (agent viết code)
> Tạo: 2026-09-23
> Phạm vi: `tabs/tab_tracuu_v2.py` + `components/filter_panel.py`
> Trạng thái: CHỜ THỰC HIỆN — làm tuần tự theo 4 ĐỢT, mỗi đợt bàn giao riêng

---

## PHẦN 0 — BỐI CẢNH (bắt buộc đọc trước khi sửa)

**Dự án:** Hệ thống Quản trị Tín dụng Nội bộ — NHCSXH Chi nhánh Đồng Nai.
**Stack:** Streamlit + Python 3.12 + SQLite + PyArrow/Parquet + DuckDB.
**Python:** `D:\VBSP-SCM\venv\Scripts\python.exe` (KHÔNG dùng `.venv`).
**Chạy app thật:** `venv\Scripts\python.exe -m streamlit run app.py --server.port 8502`
**Port preview cho agent:** `18502` (dừng tiến trình sau khi kiểm tra xong).

### File phải đọc trước

| File | Lý do |
|---|---|
| `AGENTS.md` | Quy trình, chính sách model, bản đồ file |
| `.trae/rules/rules.md` | Quy tắc bắt buộc — đặc biệt section 6 |
| `BUGMAP.md` | Lỗi đã từng mắc — tránh lặp lại |
| `COT_REF.md`, `config.py` dòng 377–588 | Tên cột `COT_*` |
| `SIGNATURES.md` | Chữ ký hàm Components / Utils / Auth |
| `CODE_INDEX.md` | Map chức năng → file → hàm |
| `docs/UI_GUIDELINES.md` | Bảng màu, typography, pattern UI |
| `DELTA.md` | Thay đổi gần nhất |

### File được sửa

- `tabs/tab_tracuu_v2.py` (chính — 475 dòng)
- `components/filter_panel.py` (chính — 602 dòng, **chỉ tab này dùng**, refactor tự do)
- `tests/test_tracuu_search.py` (bổ sung test)
- `CHANGELOG.md`, `BUGMAP.md`, `CODE_INDEX.md`, `SIGNATURES.md`, `DELTA.md`, `TEST_COVERAGE.md`
- Đợt 4 (có hỏi user trước): `tabs/tab_tracuu.py`, `tests/test_smoke_imports.py`, module mới `components/ho_so_card.py`

### File CHỈ ĐỌC — không sửa

`app.py`, `db.py`, `auth.py`, `config.py`, `snapshot_service.py`, `utils.py`,
`components/export_pdf.py`, `components/delta_card.py`, `services/template_service.py`.

> ⚠️ Nếu buộc phải sửa `db.py` / `auth.py` / migration / phân quyền → **DỪNG LẠI**, báo user.
> Model đề xuất khi đó: `gpt-5.6-sol` (Effort High, Speed Standard).

### Cấu hình model đề xuất

```
🤖 Model: GPT-5.5 | Effort: Medium-High | Speed: Standard
Lý do: sửa bug + thêm tính năng ở tabs/ và components/ — không chạm auth/db.
```

---

## PHẦN 1 — HIỆN TRẠNG

### Đăng ký tab

- **CN (Hội sở):** `tab_registry.py:69` → nhóm `"Tổng quan"`, nhãn `"🔍 Tra cứu Khách hàng"`, hàm `tab_tracuu_v2.render`
- **PGD:** `tab_registry.py:132` → nhóm `"Tác nghiệp"`, nhãn `"🔍 Tra cứu hồ sơ"`, hàm `tab_tracuu_v2.render`
- `ws_management.py:338` mount trực tiếp: `_get_tab("tab_tracuu_v2").render(None, **kwargs)`

### Context nhận được (`app.py:1469-1482`)

```python
df, df_full, role, pgd_user, pgd_user_label, username,
df_nq11, df_gqvl, pgd_xa_map, ds_pgd_all, ts_hstd, hstd_path
```

> **QUAN TRỌNG:** với role CN (`management`, `executive`), `app.py:1414-1415` gán
> `df = _loc_hstd_active(df_full)` → **chỉ còn hồ sơ dư nợ > 0**.
> `df_full` = toàn bộ (kể cả đã tất toán).
> Với PGD: `df` = `doc_hstd_pgd(pgd_user)`, `df_full = df`.

### Luồng hiện tại

```
render(tab=None, **kwargs)                       # tab_tracuu_v2.py:357
  ├─ df = kwargs["df"]; df_nq11/df_gqvl = kwargs  # :359-371
  ├─ render_filter_panel(df,...)  → df_f          # filter_panel.py:453
  │    ├─ _pre_compute_search_text(df)            # :72
  │    ├─ search box + nút Tìm + nút Reset        # :199-214
  │    ├─ expander "Lọc nâng cao"                 # :219
  │    │    PGD/Xã/Thôn/CT/Nguồn vốn/Slider dư nợ
  │    │    Ngày vay/Ngày ĐH/4 toggle + nút Reset  # :258-458
  │    └─ trả về df đã lọc                         # :478
  ├─ _render_kpi_row(df_f)                        # :377-393
  ├─ _build_bang_ket_qua(df_f) → st.dataframe     # :326-354, :398-440
  └─ chọn dòng → map theo Số khế ước → _detail_dialog()  # :442-471, :138-257
```

### Tính năng đang có

Tìm 1 từ khóa (5 cột) · lọc PGD/Xã/Thôn/CT/Nguồn vốn/Slider dư nợ/Ngày vay/Ngày ĐH ·
4 toggle (QH·NQ11·GQVL·Khoanh) · KPI 5 metric · xuất Excel/PDF · dialog chi tiết.

---

## PHẦN 2 — 28 VẤN ĐỀ PHÁT HIỆN (đã xác minh bằng code)

### Nhóm A — BUG CHỨC NĂNG (ưu tiên cao nhất)

| # | Vấn đề | Vị trí | Chi tiết |
|---|---|---|---|
| **A1** | **Không tra được hồ sơ đã tất toán** | `tab_tracuu_v2.py:359` | Dùng `kwargs.get("df")` = active_only. v1 (`tab_tracuu.py:953-981`) đọc thẳng parquet `hstd_path` nên tra được dư nợ = 0. **v2 làm mất tính năng này.** |
| **A2** | **Nút "🔄 Reset" KHÔNG hoạt động** | `filter_panel.py:238-256`, `440-458` | Chỉ gán lại dict `tracuu_filters`, nhưng widget `key="tc_pgd"`, `tc_xa`, `tc_thon`, `tc_ct`, `tc_nv`, `tc_du_no`, `tc_ngay_vay_from`... vẫn giữ state cũ trong `st.session_state`. Streamlit **ưu tiên widget state hơn `default=`** → reset vô hiệu. |
| **A3** | **Nguy cơ crash slider sau khi upload HSTD kỳ mới** | `filter_panel.py:355-363` | Vừa truyền `value=safe_value` vừa `key="tc_du_no"`. Sau rerun `value` bị bỏ qua. Nếu kỳ mới có max dư nợ **nhỏ hơn** giá trị slider cũ trong session_state → `StreamlitAPIException: value out of range`. |
| **A4** | **Mở SAI hồ sơ khi Số khế ước trùng/rỗng** | `tab_tracuu_v2.py:448-453` | `mask = df[COT_SO_KU] == so_ku` rồi `.iloc[0]`. Nếu `so_ku` = `""`/`"nan"` (cột KU trống) hoặc trùng → hiện hồ sơ người khác. Phải map theo **index gốc của `df_f`**, không theo giá trị. |
| **A5** | **Tra ngược trên `df` thay vì `df_f`** | `tab_tracuu_v2.py:450` | `df` là tập gốc (đã lọc active), `df_f` là tập đã lọc. Index hai bên không tương ứng. |
| **A6** | **`_get_options_filtered` có thể `TypeError`** | `filter_panel.py:69` | `sorted(...unique().tolist())` **không** `str()` (khác `:32`). Cột Xã/Thôn lẫn số + chuỗi → sort crash. |
| **A7** | **Fallback NQ11/GQVL không bao giờ chạy** | `tab_tracuu_v2.py:366-371` | `app.py:1476` luôn truyền `df_nq11` (DataFrame **rỗng**, không phải `None`) → điều kiện `is None` sai → `_load_nq11_gqxl_data()` đọc lại file vô ích (IO + parse). |
| **A8** | **`filter_active` là dead state** | `filter_panel.py:197, 254, 456` | Khai báo `True` ở 3 chỗ, **không widget nào đọc, không mask nào dùng**. |
| **A9** | **Nút "🔍 Tìm" vô dụng** | `filter_panel.py:212` | `search_clicked` gán rồi bỏ. `st.text_input` đã tự rerun. |
| **A10** | **Nút "💾 Lưu bộ lọc" disabled cứng** | `filter_panel.py:460` | `disabled=True` vĩnh viễn → UI hứa hẹn tính năng không tồn tại. |

### Nhóm B — HIỆU NĂNG

| # | Vấn đề | Vị trí | Chi tiết |
|---|---|---|---|
| **B1** | **`@st.cache_data` hash toàn bộ DataFrame 5 lần/rerun** | `filter_panel.py:26, 36, 50, 61, 73` | Tham số `_df: pd.DataFrame` vẫn bị Streamlit hash. Với ~200k dòng → băm lại 5 lần mỗi rerun. `ts` không cứu được. |
| **B2** | **Normalize Unicode ở Python-level** | `filter_panel.py:81-82` | `.map(lambda x: unicodedata.normalize(...))` × 2 lần × 5 cột × 200k dòng = **~2 triệu lời gọi Python**. Cold cache rất chậm. |
| **B3** | **PDF được TẠO trong mỗi rerun** | `tab_tracuu_v2.py:309` | `xuat_pdf_co_chart(...)` chạy **mọi lần render**, kể cả khi user không bấm tải. 200 dòng + Plotly → block UI. |
| **B4** | **Không có spinner** | toàn tab | User không biết đang lọc hay đã đơ. |
| **B5** | **`key=f"tc_table_p{page}"` đổi theo trang** | `tab_tracuu_v2.py:437` | Mất selection state + rác widget state tích lũy. |

### Nhóm C — UX / GIAO DIỆN

| # | Vấn đề | Vị trí |
|---|---|---|
| **C1** | Slider "Khoảng dư nợ (**VNĐ**)" — sai đơn vị, vô dụng với dư nợ nghìn tỷ (mọi giá trị đều sát max) | `filter_panel.py:355` |
| **C2** | Tiền trong bảng bị `apply(fmt_ty)` → **thành string, mất khả năng sort số** của `st.dataframe` | `tab_tracuu_v2.py:345` |
| **C3** | Bảng chỉ 10 cột, **thiếu**: Ngày vay, Ngày đến hạn, Dư nợ QH, Dư nợ khoanh, Lãi suất, Mức vay, Cờ NQ11/GQVL, Nguồn vốn, Mã NĐT | `tab_tracuu_v2.py:328-339` |
| **C4** | Không có **chọn cột hiển thị**, không có **sắp xếp mặc định theo nghiệp vụ** | — |
| **C5** | Dialog auto-open (`tc_last_ku`) gây rối khi đổi trang/filter | `tab_tracuu_v2.py:461-469` |
| **C6** | `_render_chi_tiet_phu` dump **mọi cột** bảng NQ11/GQVL (30+) → tràn dialog | `tab_tracuu_v2.py:87-112` |
| **C7** | `height=460` cố định, không responsive | `tab_tracuu_v2.py:436` |
| **C8** | Không có "Tra cứu gần đây" — tra lại cùng KH phải gõ lại từ đầu | — |
| **C9** | Không gom theo **KHÁCH HÀNG** — 1 KH nhiều khế ước → trùng tên đầy bảng | — |
| **C10** | Không có biểu đồ phân bố khi kết quả lớn | — |

### Nhóm D — TÍNH NĂNG THIẾU / NGHIỆP VỤ

| # | Vấn đề | Chi tiết |
|---|---|---|
| **D1** | **Search thiếu cột** | Chỉ 5 cột (`filter_panel.py:466`). Thiếu: `COT_TEN_HSSV`, `COT_TEN_VC`, `COT_TEN_TO`, `COT_TEN_THON`, `COT_DIA_CHI`, `COT_MA_NHA_DAU_TU`, `COT_TEN_TO_TRUONG`. v1 có HSSV + vợ/chồng → **v2 thụt lùi**. |
| **D2** | **Không hỗ trợ đa từ khóa** | `contains` trên chuỗi ghép `" | "` → gõ `"Đức Long Khánh"` hoặc `"0901 nguyen"` **không match** (yêu cầu đúng thứ tự liền mạch). Cần tách token AND/OR. |
| **D3** | **Ghi chú CBTD có sẵn trong DB nhưng không hiển thị** | `db.luu_ghi_chu_kv()` / `doc_ghi_chu_kv()` / `doc_ghi_chu_nhieu()` (bảng `loan_notes`, `db.py:198`) — chỉ `components/loan_drawer.py:198` dùng. Tab tra cứu **bỏ sót hoàn toàn**. → Quick win. |
| **D4** | **Không audit lượt tra cứu** | Dữ liệu PII (CMND, SĐT, ngày sinh, địa chỉ) mà không có `db.ghi_audit(username, "tra_cuu_kh", ...)`. Thiếu compliance. |
| **D5** | **Không mask PII theo role** | `executive` (chỉ đọc) vẫn tải Excel full CMND/SĐT. |
| **D6** | **Không hiển thị CBTD phụ trách** | `data/khtd.py:379` có `gan_cbtd_vao_df()`, `:349` `xay_ma_thon_to_cbtd_map()`. Tra ra hồ sơ mà không biết ai phụ trách. |
| **D7** | **Không có filter "Đến hạn trong N ngày"** | Nghiệp vụ PGD dùng nhiều nhất, hiện phải tự tính ngày. |
| **D8** | **Không có filter theo nhóm nợ / phân loại** | `COT_PHAN_LOAI`, `COT_PL_NV` (`config.py:426, 429`). |
| **D9** | **Không có filter theo Hội đoàn thể** | `COT_DVUT` (`config.py:424`). |
| **D10** | **Không tìm được theo Điểm giao dịch** | `COT_MA_DGD` / `COT_TEN_DGD` (`config.py:418, 421`). |
| **D11** | **Không có "Số dư TK 105 = 0"** | `COT_SO_DU_TG` (`config.py:417`) — nghiệp vụ huy động tiết kiệm. |
| **D12** | **PDF hồ sơ quá thô** | `_tao_pdf_ho_so` (`tab_tracuu_v2.py:115-135`) chỉ là list `(label, value)`. Không header đơn vị, không chữ ký, không dùng `services/template_service.py`. |

### Nhóm E — NỢ KỸ THUẬT

| # | Vấn đề | Chi tiết |
|---|---|---|
| **E1** | `tabs/tab_tracuu.py` (v1, 1264 dòng) là dead code trong production nhưng `tests/test_tracuu_search.py:15` và `tests/test_smoke_imports.py:73` vẫn import. Phải quyết định: xóa v1 + chuyển test, HOẶC giữ. |
| **E2** | v1 hardcode màu dark (`#1E2130`, `#94A3B8`, `#E0E6ED`, `#f8fafc`) → vi phạm rule 6.15. Kiểm tra v2 không lặp lại. |
| **E3** | `_pre_convert_dates` cache **dict chứa Series có thể biến đổi** trong `@st.cache_data` → rủi ro mutation leakage giữa các lần gọi. |
| **E4** | Hai bộ helper trùng chức năng: `_bo_dau`/`_tim_mem`/`_find_any`/`_find_all` (v1) vs `_normalize_search_text`/`_keyword_search_mask` (filter_panel). Phải hợp nhất về 1 chỗ. |

---

## PHẦN 3 — THIẾT KẾ GIAO DIỆN MỤC TIÊU

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 🔍 TRA CỨU KHÁCH HÀNG                                                    │
│ Nguồn: HSTD kỳ 09/2026 · 198.432 hồ sơ · Cập nhật 23/09/2026 08:15       │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────┐ ┌────────┐ ┌────────┐ │
│ │ 🔍 Tên KH · CMND · Số KU · SĐT · HSSV · Tổ...  │ │⚙ Lọc  │ │↺ Reset │ │
│ └────────────────────────────────────────────────┘ └────────┘ └────────┘ │
│  Gợi ý: [nguyễn văn a ×] [075xxx ×] · 🕘 Tra gần đây: ▾                  │
├──────────────────────────────────────────────────────────────────────────┤
│ Bộ lọc đang áp: [PGD Long Khánh ×] [Quá hạn ×] [CT: HSSV ×]  → 1.204 hồ sơ│
├──────────────────────────────────────────────────────────────────────────┤
│ 📁 1.204  💰 45.320 tr  ⚠️ 87 QH  ✨ 210 NQ11  📋 45 GQVL  👥 1.102 KH     │
├──────────────────────────────────────────────────────────────────────────┤
│ Chế độ: (•) Theo khế ước  ( ) Theo khách hàng  ( ) Thẻ chi tiết          │
│ Cột hiển thị: ▾  Sắp xếp: [Tổng dư nợ ▾]  📊 Biểu đồ  📥 Excel  📄 PDF   │
├──────────────────────────────────────────────────────────────────────────┤
│ ▸ KU.00123  NGUYỄN VĂN A  Long Khánh  HSSV  50.000  ⚠️2.000  [Chi tiết]  │
│ ▸ KU.00456  TRẦN THỊ B    Long Khánh  NS&VS 30.000   —       [Chi tiết]  │
│                                    ‹ 1 2 3 ... 7 ›   200/trang            │
└──────────────────────────────────────────────────────────────────────────┘
```

### Bảng màu — theo `docs/UI_GUIDELINES.md`

**Màu nhóm nghiệp vụ:**

| Nhóm | Background | Text |
|---|---|---|
| TW + Chỉ tiêu | `#1a3a5c` | `white` |
| Địa phương + Thực hiện | `#2d5986` | `white` |
| Huy động vốn ĐP | `#1D9E75` | `white` |
| Tổng | `#854F0B` | `white` |
| Chênh lệch / Delta | `#EF9F27` | `#1a1a1a` |
| Tỷ lệ / Progress | `#BA7517` | `white` |

**Màu dòng & hover:** chẵn `#FFFFFF` · lẻ `#F5F8FC` · hover `#f8fafc` · border `#ddd`

**Trạng thái:**

| Trạng thái | BG nhẹ | BG đậm | Text |
|---|---|---|---|
| Đạt / Tăng | `#e8f5e9` | `#4caf50` | `#2e7d32` |
| Cảnh báo | `#fff8e1` | `#ff9800` | `#854F0B` |
| Nguy hiểm | `#fff3cd` | `#ffc107` | `#856404` |
| Vượt / Giảm / QH | `#ffebee` | `#c62828` | `#b71c1c` |

**Typography:** font `'Inter','Segoe UI',system-ui,sans-serif` · dữ liệu bảng `0.88rem` ·
label/nhóm cột `0.72rem uppercase bold` · caption `0.78rem` · KPI `1.8–2.2rem bold` ·
dòng chẵn/lẻ + hover bắt buộc

**Nguyên tắc:**
- `st.dataframe` native khi ≤ 12 cột; ≥ 8 cột có nhóm header → HTML + `st.markdown(unsafe_allow_html=True)`
- Mọi `st.date_input` → `format="DD/MM/YYYY"`
- Widget key prefix duy nhất: **`tc2_`** (tránh đụng `tc_*` cũ trong lúc chuyển tiếp)
- Tiền: `NumberColumn(format="%,.0f")`, header ghi rõ `(triệu đồng)`. **CẤM** `%.0f`
- **CẤM** hardcode `color:black` / `background:white` — dùng CSS variable cho dark mode
- **CẤM** copy bảng màu dark của v1

---

## PHẦN 4 — KẾ HOẠCH THỰC THI (4 ĐỢT, làm tuần tự)

### 🔴 ĐỢT 1 — SỬA BUG NỀN TẢNG *(bắt buộc trước, không thêm tính năng)*

**Mục tiêu:** tab chạy đúng, không crash, không mở sai hồ sơ.

| Task | Sửa ở | Chi tiết |
|---|---|---|
| **1.1** | `tab_tracuu_v2.py:357-390` | Thêm toggle `bao_gom_tat_toan` trên UI. Khi **bật** → dùng `df_full`; **tắt** → dùng `df`. Mặc định: **bật cho CN, tắt cho PGD**. Guard: `df_full is None → fallback df`. Sửa A1. |
| **1.2** | `filter_panel.py:238-256, 440-458` | Viết `_reset_filter_state()`: xóa **trực tiếp** mọi key `tc_*` khỏi `st.session_state` → **rồi mới** gán lại dict → `st.rerun()`. Sửa A2. |
| **1.3** | `filter_panel.py:349-365` | Bỏ `key="tc_du_no"` **hoặc** bỏ `value=` (chỉ chọn 1). Khuyến nghị: bỏ `key`, dùng `value=safe_value` + đọc từ dict `tracuu_filters`. Thêm clamp chống A3. |
| **1.4** | `tab_tracuu_v2.py:442-471` | **Thay hoàn toàn** cơ chế map theo Số KU. Giữ `df_f.index` → `idx_goc = df_f.index[start + rows[0]]` → `hs_selected = df_nguon.loc[idx_goc]`. Cấm `.iloc[0]` theo giá trị KU. Sửa A4 + A5. |
| **1.5** | `filter_panel.py:60-69` | `_get_options_filtered`: ép `str(v)` trước `sorted()`, đồng bộ với `:32`. Sửa A6. |
| **1.6** | `tab_tracuu_v2.py:363-371` | Sửa điều kiện fallback: `if df_nq11 is None or (hasattr(df_nq11, "empty") and df_nq11.empty)`. Bỏ đọc file khi `app.py` đã nạp. Sửa A7. |
| **1.7** | `filter_panel.py` | Xóa `filter_active` (A8), xóa nút "🔍 Tìm" (A9). Giữ nút Reset. |
| **1.8** | `tab_tracuu_v2.py:432-440` | Đổi `key=f"tc_table_p{page}"` → `key="tc_table"` cố định. Lưu `tc2_selected_idx` trong session_state để giữ selection khi đổi trang. Sửa B5. |

**Nghiệm thu Đợt 1:**
- [ ] Role CN tra được 1 khách hàng **đã tất toán** (dư nợ = 0)
- [ ] Bấm Reset → mọi multiselect / slider / date_input về mặc định **thật sự**
- [ ] Upload HSTD kỳ mới có max dư nợ nhỏ hơn → **không crash**
- [ ] Hai khế ước cùng Số KU (hoặc KU rỗng) → bấm dòng nào ra **đúng** hồ sơ dòng đó
- [ ] `venv\Scripts\python.exe -m pytest tests/test_tracuu_search.py -q` pass
- [ ] Compile OK cả 2 file

---

### 🟠 ĐỢT 2 — HIỆU NĂNG

| Task | Sửa ở | Chi tiết |
|---|---|---|
| **2.1** | `filter_panel.py:25-88` | **Loại bỏ hash DataFrame khỏi cache.** Đổi 5 hàm `@st.cache_data(_df, ...)` sang nhận `hstd_path: str` + `ts: float`, query **DuckDB**: `SELECT DISTINCT col FROM read_parquet('...')`. Sửa B1. |
| **2.2** | `filter_panel.py:72-88` | Vectorize `_pre_compute_search_text`: thay `.map(lambda)` bằng `str.lower().str.replace("đ","d")` + **1 lần** `str.normalize("NFD")` + `str.replace(r"[\u0300-\u036f]", "", regex=True)`. Từ ~2 triệu lời gọi Python xuống ~5 vectorized ops. Sửa B2. |
| **2.3** | `filter_panel.py` | Bắt buộc kiểm tra schema trước khi query DuckDB (rule 6.16): `pq.read_schema(CACHE_HSTD)` → chỉ select cột tồn tại → thiếu cột thì `st.warning` + `return`, không crash. |
| **2.4** | `tab_tracuu_v2.py:300-323` | **Không tạo PDF trong render.** Chuyển sang `st.download_button(data=<callable>)` (lazy) hoặc chỉ tạo khi user bấm, cache bytes vào session_state theo hash của `df_f`. Sửa B3. |
| **2.5** | `tab_tracuu_v2.py` | Bọc phần lọc + render bảng trong `with st.spinner("Đang tra cứu...")`. Sửa B4. |
| **2.6** | `filter_panel.py:49-57` | `_pre_convert_dates`: trả về **DataFrame bất biến** hoặc tuple thay vì dict-of-Series. Sửa E3. |
| **2.7** | `filter_panel.py:568` | Mở rộng `_debug_tracuu_filters`: in `rows_before/rows_after`, **thời gian lọc (ms)**, cache hit/miss. |

**Nghiệm thu Đợt 2:**
- [ ] Rerun lần 2 (warm cache) < **300 ms** với 200k dòng
- [ ] Cold cache < **3 s**
- [ ] Không tạo PDF khi chỉ đổi filter
- [ ] Không còn cảnh báo `st.cache_data` hash DataFrame trong log

---

### 🟡 ĐỢT 3 — TÍNH NĂNG MỚI *(phần giá trị nhất)*

#### 3.1 — Tìm kiếm thông minh (`filter_panel.py`)

- Mở rộng cột search, thêm: `COT_TEN_HSSV`, `COT_TEN_VC`, `COT_TEN_TO`, `COT_TEN_THON`, `COT_DIA_CHI`, `COT_TEN_TO_TRUONG`, `COT_MA_NHA_DAU_TU` → sửa **D1**
- **Multi-token:** tách từ khóa theo khoảng trắng → mode `AND` (mặc định) / `OR` (toggle). Mỗi token match bỏ dấu + không phân biệt hoa thường → sửa **D2**
- **Auto-detect loại từ khóa** để ưu tiên cột:

| Pattern | Loại | Cột ưu tiên |
|---|---|---|
| Toàn số, 9–12 ký tự | CMND/CCCD | `COT_CMND` |
| Bắt đầu `0`, 10–11 số | Số điện thoại | `COT_SDT` |
| Prefix `KU` / chứa `.` | Số khế ước | `COT_SO_KU` |
| Còn lại | Tên | `COT_TEN_KH` + các cột tên |

  → Hiện caption `"🎯 Đang tìm theo: **Số CMND**"` để user hiểu
- Placeholder động liệt kê cột đang search

#### 3.2 — Bộ lọc nâng cao bổ sung (`filter_panel.py`)

| Filter mới | Cột | Widget |
|---|---|---|
| Nhóm nợ / Phân loại | `COT_PHAN_LOAI`, `COT_PL_NV` | multiselect — **D8** |
| Hội đoàn thể | `COT_DVUT` | multiselect, cascade theo Xã — **D9** |
| Điểm giao dịch | `COT_TEN_DGD` | multiselect, cascade theo PGD — **D10** |
| **Đến hạn trong N ngày** | `COT_NGAY_DH` | selectbox `7/15/30/60/90`, tính từ `date.today()` — **D7** |
| Đã quá hạn N ngày | `COT_NGAY_DH` | number_input — **D7** |
| Số dư TK 105 = 0 | `COT_SO_DU_TG` | toggle — **D11** |
| Có gia hạn nợ | `COT_SO_LAN_GH` | toggle (`> 0`) |
| Khoanh nợ sắp hết hạn | `COT_NGAY_HH_KHOANH` | selectbox N ngày |
| **Khoảng dư nợ (triệu đồng)** | `COT_TONG_DU_NO` | **thay slider VNĐ** bằng selectbox bucket: `Tất cả / <10 / 10–30 / 30–50 / 50–100 / >100 (triệu)` + 2 number_input tự do — **C1** |
| CBTD phụ trách | join `data/khtd.py` | multiselect — **D6** |

- **Chip bộ lọc đang áp:** render hàng chip HTML ngay dưới search, mỗi chip có nút `×` xóa riêng (ghi session_state + `st.rerun()`)
- **💾 Lưu bộ lọc** (bật nút đang disabled — **A10**):
  ```python
  key = f"tracuu_filter_{pgd_slug(pgd_user) if pgd_user else 'cn'}_{username}"
  db.ghi_kv(key, {...}, username)
  db.ghi_audit(username, "luu_bo_loc_tra_cuu", f"n_filter={len(...)}")   # NGAY SAU
  ```
  UI: selectbox "Bộ lọc đã lưu" + nút Áp / Xóa

#### 3.3 — Bảng kết quả nâng cấp (`tab_tracuu_v2.py:326-354`)

- **Giữ kiểu số** cho cột tiền → `st.column_config.NumberColumn(format="%,.0f")`. **Bỏ `.apply(fmt_ty)`** — sửa **C2**. Header ghi `(triệu đồng)`
- **Column picker** với preset:

| Preset | Cột thêm vào bộ cơ bản |
|---|---|
| `Cơ bản` (mặc định) | 10 cột hiện tại |
| `Đến hạn` | Ngày vay, Ngày ĐH, Số ngày còn lại, Số lần GH |
| `Quá hạn` | Dư nợ QH, Lãi tồn QH, Phân loại, Ngày CNQH gần nhất |
| `NQ11 / GQVL` | Cờ NQ11, Cờ GQVL, Mã NĐT, Nguồn vốn |
| `Huy động` | Số dư TK 105, Lãi tồn TH |
| `Tùy chỉnh` | user tự chọn qua multiselect |

- **Highlight dòng:** QH > 0 → `#ffebee`; khoanh > 0 → `#fff8e1`; NQ11 → prefix `✨`
- **Sắp xếp mặc định:** `Dư nợ quá hạn DESC, Tổng dư nợ DESC`
- **Phân trang:** selectbox `100/200/500` + nút `‹ ›` + nhảy trang

#### 3.4 — Chế độ xem "Theo khách hàng" *(mới — sửa C9)*

- `st.radio`: `Theo khế ước` | `Theo khách hàng` | `Thẻ chi tiết`
- **Theo khách hàng:** `groupby(COT_MA_KH)` → mỗi dòng = 1 KH: Tên KH, CMND, SĐT, Xã, PGD, **Số món vay**, Tổng dư nợ, Dư nợ QH, Tổng lãi tồn, Số dư TK 105. Bấm → dialog liệt kê khế ước con.
  - Nhớ rule 6.18: `pd.to_numeric(errors="coerce").fillna(0)` **trước** groupby
  - Đếm số món: `.ngroup`/`len` trên group — **KHÔNG** dùng `ngroups` để đếm unique (rule 6.19)
- **Thẻ chi tiết:** giới hạn 20 thẻ, tham khảo `_render_card` của v1 nhưng **theo bảng màu UI_GUIDELINES**, không hardcode dark

#### 3.5 — Dialog chi tiết hồ sơ nâng cấp (`_detail_dialog`, `tab_tracuu_v2.py:138-257`)

```
┌─ 📋 Chi tiết hồ sơ ─────────────────────────── ✕ ─┐
│ NGUYỄN VĂN A                    [✨NQ11] [⚠️QH]   │
│ Mã KH 0123456 · KU.00123 · PGD Long Khánh         │
├───────────────────────────────────────────────────┤
│ 📁 Tổng quan (4 KPI)                              │
│  Tổng dư nợ │ Dư nợ QH │ Lãi tồn │ Số dư TK105    │
├──────────────┬────────────────────────────────────┤
│ 👤 Khách hàng│ 💰 Khoản vay                       │
│ ▸ CMND/CCCD  │ ▸ Chương trình / Nguồn vốn         │
│ ▸ Ngày sinh  │ ▸ Ngày vay → Ngày ĐH (còn N ngày)  │
│ ▸ SĐT · Địa chỉ│ ▸ Mức vay · Lãi suất · Thời hạn │
│ ▸ Tổ · Xã · ĐGD│ ▸ Dư nợ TH/QH/Khoanh            │
│ ▸ Vợ/chồng · HSSV│ ▸ Gốc đã trả · Lãi đã trả      │
├──────────────┴────────────────────────────────────┤
│ 👔 CBTD phụ trách: Trần Thị C — 09xx.xxx.xxx      │
├───────────────────────────────────────────────────┤
│ ▸ 📝 Ghi chú CBTD (loan_notes)      [💾 Lưu]      │
│ ▸ 📜 Toàn bộ trường gốc (theo _NHOM_TRUONG của v1)│
│ ▸ ✨ Chi tiết NQ11 / 📋 Chi tiết GQVL (whitelist) │
│ ▸ 🏦 Các khế ước khác của khách hàng này          │
├───────────────────────────────────────────────────┤
│ [📥 Excel] [📄 PDF] [📋 Copy thông tin] [🖨 In]   │
└───────────────────────────────────────────────────┘
```

- **Ghi chú CBTD (D3):** `db.doc_ghi_chu_kv(so_ku)` / `db.luu_ghi_chu_kv(so_ku, text, username)`.
  `luu_ghi_chu_kv` **đã tự ghi audit** (`db.py:219`) → **không** gọi `db.ghi_audit` lần nữa.
  Quyền ghi: `admin_cn`, `manager_cn`, `chuyenvien_cn`, `admin_pgd`, `manager_pgd`.
  `executive` / `user_pgd` → **chỉ đọc**.
  Check bằng `normalize_role()` + `la_phan_he_cn()` / `la_phan_he_pgd()` — **cấm so chuỗi thô** (rule 6.5).
- **Chi tiết NQ11/GQVL (C6):** whitelist ~10 cột thay vì dump hết
- **Khế ước khác cùng KH:** `df_full[df_full[COT_MA_KH] == ma_kh]`, hiện bảng nhỏ
- **PDF hồ sơ (D12):** ưu tiên `services/template_service.py` nếu có template; nếu không, cải thiện `xuat_pdf_co_chart` với `tieu_de` có tên đơn vị (`TEN_CHI_NHANH_HIEN_THI`), header 2 cấp, ghi rõ "Đơn vị: triệu đồng"

#### 3.6 — Audit & PII (`tab_tracuu_v2.py`) — sửa D4, D5

```python
username = st.session_state.get("username", "unknown")
db.ghi_audit(username, "tra_cuu_kh", f"kw={mask_kw}; n={len(df_f)}; pgd={pgd_scope}")
```

- **Chỉ ghi khi user thực sự tra cứu có từ khóa.** Debounce: so keyword với `st.session_state["tc2_last_audited_kw"]`, trùng thì bỏ qua (tránh spam mỗi rerun)
- **KHÔNG log CMND/SĐT đầy đủ** vào audit → mask `075***678`
- Toggle `"🕶️ Ẩn thông tin nhạy cảm"`: mặc định **tắt** cho CN, **bật** khi role = `executive`.
  Che CMND `075***678`, SĐT `09xx***001`. Excel/PDF xuất ra cũng áp mask khi toggle bật
- Sheet "Ghi chú bảo mật" trong Excel export: người xuất + thời điểm + số dòng

#### 3.7 — Biểu đồ phân bố *(mới — sửa C10)*

Trong `st.expander("📊 Phân bố kết quả")`, 4 chart nhỏ (2×2) bằng `plotly.graph_objects` (đã có sẵn):

1. Dư nợ theo **Chương trình** — bar ngang, top 10
2. Dư nợ theo **PGD** — bar ngang (chỉ role CN)
3. Dư nợ theo **Nguồn vốn TW/ĐP** — donut, màu `#1a3a5c` / `#1D9E75`
4. **Tuổi nợ** theo Ngày vay — histogram theo năm

- Truyền `figs=[(fig, "Tiêu đề"), ...]` vào `xuat_pdf_co_chart` để đính kèm PDF
- Chỉ render khi `len(df_f) > 0` **và** user mở expander (lazy)
- Cột số: `pd.to_numeric(errors="coerce").fillna(0)` trước khi agg

#### 3.8 — Tra cứu gần đây *(mới — sửa C8)*

- `st.session_state["tc2_recent"]` = deque tối đa 10 mục `{tu_khoa, ts, n_ket_qua, ten_kh_dau}`
- Render `st.popover("🕘 Tra cứu gần đây")` cạnh ô search → bấm để nạp lại từ khóa
- **KHÔNG persist xuống DB** (tránh lộ PII trong `kv_store`)

**Nghiệm thu Đợt 3:**
- [ ] Gõ `"nguyen van a long khanh"` (không dấu, 2 token) → ra đúng kết quả
- [ ] Gõ số CMND 12 chữ số → caption hiện "Đang tìm theo: Số CMND"
- [ ] Bật "Đến hạn trong 30 ngày" → chỉ ra hồ sơ có `COT_NGAY_DH` trong khoảng
- [ ] Đổi preset cột "Quá hạn" → bảng hiện thêm 4 cột, **sort số hoạt động**
- [ ] Mode "Theo khách hàng": KH có 3 khế ước → 1 dòng, `Số món vay = 3`, tổng dư nợ đúng
- [ ] Ghi chú CBTD: `manager_pgd` lưu được + có dòng trong `audit_log`; `executive` chỉ đọc
- [ ] Toggle ẩn PII → CMND/SĐT bị che cả trên bảng lẫn file Excel
- [ ] Có dòng `tra_cuu_kh` trong `audit_log`, **CMND đã mask**
- [ ] 4 biểu đồ render đúng, đính kèm được vào PDF
- [ ] Lưu bộ lọc → F5 lại vẫn còn, có dòng `luu_bo_loc_tra_cuu` trong audit

---

### 🟢 ĐỢT 4 — DỌN DẸP & KIỂM THỬ

| Task | Chi tiết |
|---|---|
| **4.1** | **Quyết định số phận `tabs/tab_tracuu.py` (v1).** Đề xuất: chuyển `_tim_mem`, `_bo_dau`, `_NHOM_TRUONG`, `_render_full_record`, `_render_card`, `_build_charts` sang module mới `components/ho_so_card.py` → **xóa** `tabs/tab_tracuu.py` → cập nhật `tests/test_tracuu_search.py` (import từ `components.filter_panel`) + `tests/test_smoke_imports.py:73`. **HỎI USER TRƯỚC KHI XÓA.** Sửa E1. |
| **4.2** | Hợp nhất `_bo_dau` / `_normalize_search_text` thành **1 hàm duy nhất** trong `utils.py`. Cập nhật mọi call site (grep trước khi sửa). Sửa E4. |
| **4.3** | Rà hardcode màu trong v2 — thay bằng hằng theo `docs/UI_GUIDELINES.md` hoặc CSS variable. Sửa E2. |
| **4.4** | **Viết test mới** trong `tests/test_tracuu_search.py`: multi-token AND/OR · auto-detect loại từ khóa · bucket dư nợ · đến hạn N ngày · group-by KH · mask PII · index-mapping (A4) · reset filter (A2) |
| **4.5** | Chạy full smoke: `venv\Scripts\python.exe -m pytest tests/ -q` |
| **4.6** | Cập nhật tài liệu: `CHANGELOG.md` (đầu file, ngày thực tế) · `BUGMAP.md` (mỗi bug nhóm A = 1 entry, phân loại đúng section A–J) · `CODE_INDEX.md` · `SIGNATURES.md` · `DELTA.md` · `TEST_COVERAGE.md` |

---

## PHẦN 5 — RÀNG BUỘC BẮT BUỘC (trích `.trae/rules/rules.md`)

```
□ CHỈ dùng COT_* từ config.py — CẤM chuỗi thô "Tổng dư nợ"
□ CHỈ persist bằng db.ghi_kv() / doc_kv() — CẤM json.dump / open(w) / session_state
□ db.ghi_audit(username, action, detail) NGAY SAU mọi db.ghi_kv()
□ normalize_role() + la_phan_he_cn()/la_phan_he_pgd() — CẤM so sánh chuỗi role
□ Widget key duy nhất, prefix "tc2_" — CẤM dùng index vòng lặp
□ render(tab=None, **kwargs) — fallback st.container(), CẤM "with tab:"
□ st.date_input(format="DD/MM/YYYY")
□ NumberColumn format="%,.0f" / ".2%" — CẤM "%.0f" / "%.2f%%"
□ Tiền: nhập = triệu, lưu = VND, hiển thị = fmt_ty() + header "(triệu đồng)"
□ pd.to_numeric(errors="coerce").fillna(0) TRƯỚC mọi groupby/sum
□ nunique() để đếm unique — CẤM ngroups
□ DuckDB: pq.read_schema() kiểm tra cột TRƯỚC khi query
□ logger.error("...", exc_info=True) — CẤM "except: pass" / print(e)
□ CẤM hardcode color:black / background:white
□ CẤM thêm dependency mới
□ CẤM tự git add / commit / push (user tự commit qua GitHub Desktop)
□ DON_VI_CHI_NHANH để LỌC; TEN_CHI_NHANH_HIEN_THI để HIỂN THỊ
□ Compile check sau mỗi file sửa:
   venv\Scripts\python.exe -c "import py_compile; py_compile.compile('FILE', doraise=True); print('OK')"
```

**Dependency đã có (không thêm mới):** `pandas`, `openpyxl`, `pyarrow`, `streamlit`,
`duckdb`, `python-docx`, `docx2pdf`, `plotly`, `concurrent.futures`, `threading`, `gspread`.

### Chữ ký hàm dễ sai — dùng CHÍNH XÁC

```python
# components/delta_card.py
kpi_row(cols: list[dict], num_columns: int = 4)        # KHÔNG phải cols=4

# components/export_pdf.py
download_pdf_button(pdf_bytes: bytes, filename=None, label="📄 Tải PDF",
                    key="dl_pdf", use_container_width=True, btn_type="secondary")
xuat_pdf_co_chart(df, tieu_de, nguoi_xuat, figs=None, cols_tien=None,
                  don_vi_tien="đồng", prefix_file="", them_dong_tong=True,
                  them_ngay_xuat=True, cols_percent=None, cols_dem=None,
                  bang_phu=None) -> bytes

# utils.py
xuat_excel(sheets: dict[str, DataFrame], ten_file_prefix: str = "") -> bytes
hien_thi_dataframe_phan_trang(df, so_dong_moi_trang=500, key="df",
                              hien_thi_chon=False, **kwargs) -> DataFrame | None
fmt(x) / fmt_ty(x) / fmt_tien(x) / fmt_so(x) / fmt_ngay(val) / vn(x, d=1)
auto_audit(action, clear_cache=True)
lazy_tabs(labels, renderers, key="lt")

# components/filter_panel.py
render_filter_panel(df, df_nq11=None, df_gqvl=None, pgd_user=None,
                    on_filter_change=None, ts_hstd=0.0) -> DataFrame

# db.py
doc_kv(key, default=None)
ghi_kv(key, value: dict, username="system", note=None)
doc_ghi_chu_kv(ma_so_ku: str) -> dict | None
luu_ghi_chu_kv(ma_so_ku: str, ghi_chu: str, username: str) -> bool   # ĐÃ TỰ AUDIT
doc_ghi_chu_nhieu(ds_ma: list[str]) -> dict[str, dict]
ghi_audit(username: str, action: str, detail: str = "")
lay_danh_sach_gan_day(gioi_han=50) -> list[dict]
doc_dgd_map() / luu_dgd_map(ma_dgd, dia_diem, username="system")

# data/pgd.py
pgd_slug(ten_pgd) -> str
duong_dan_pgd(ten_pgd, loai) -> Path
doc_hstd_pgd(pgd_user) -> DataFrame

# data/khtd.py  — ĐỌC SIGNATURES.md TRƯỚC KHI GỌI
gan_cbtd_vao_df(...)          # dòng 379
xay_ma_thon_to_cbtd_map(...)  # dòng 349
doc_cbtd()                    # dòng 259
```

### Checklist rà soát sau khi xong mỗi đợt

```
□ Entry point render() gọi đúng hàm mới
□ Grep: hàm mới có ≥ 1 call site
□ Compile check mọi file đã sửa
□ Nếu ghi dữ liệu: có db.ghi_audit() (+ st.cache_data.clear() nếu upload)
□ Nếu bugfix: nhánh lỗi cũ không còn reachable
□ Widget key không trùng khi tab mount ở cả CN lẫn PGD
```

---

## PHẦN 6 — CÁCH BÀN GIAO

**MỖI ĐỢT = 1 lần bàn giao riêng.** Sau mỗi đợt phải:

1. Compile check mọi file đã sửa
2. Chạy `venv\Scripts\python.exe -m pytest tests/test_tracuu_search.py -q`
3. Cập nhật `CHANGELOG.md` — thêm lên **ĐẦU FILE**, ngày thực tế, mỗi file = 1 dòng
4. Cập nhật `BUGMAP.md` cho mỗi bug nhóm A đã sửa (đúng section A–J, format `### XX — [Tên lỗi]`)
5. Xuất **1 khối `CODEX_REVIEW` riêng cho đúng đợt đó** theo template rule 6.17 —
   **TUYỆT ĐỐI KHÔNG gom nhiều đợt thành 1 khối tổng hợp**
6. **DỪNG**, chờ user xác nhận trước khi sang đợt kế

### Template `CODEX_REVIEW`

````markdown
## CODEX_REVIEW — {tên đợt + phạm vi}

### Thay đổi
| File | Dòng | Hàm/Khu vực | Mô tả |
|---|---|---|---|
| `tabs/tab_tracuu_v2.py` | ~NNN | `_xxx()` | ... |

### Lý do
{1-2 câu: bug gì / yêu cầu gì}

### Cần kiểm tra
- [ ] {logic cụ thể, vd: "index mapping sau khi đổi trang có đúng không?"}
- [ ] {edge case, vd: "df_full=None khi role PGD thì toggle tất toán có crash không?"}
- [ ] {scope, vd: "biến _ma_kh định nghĩa trước khi dùng ở nhánh NQ11 không?"}

### Không cần kiểm tra
- {phần không thay đổi}

### Trạng thái
- Compile: ✅/❌
- CHANGELOG: ✅/❌
- BUGMAP: ✅/❌
````

> Nếu task chạm `auth.py` / `db.py` → thêm dòng: `⚠️ Rủi ro cao — đề xuất GPT-5.6-sol`

### Thứ tự ưu tiên nếu thiếu thời gian

```
Đợt 1  →  3.1 (search)  →  3.3 (bảng)  →  3.5 (dialog)  →  3.2 (filter)
       →  Đợt 2 (perf)  →  3.6 (audit/PII)  →  3.4 (group KH)
       →  3.7 (chart)  →  3.8 (recent)  →  Đợt 4 (dọn dẹp)
```

### CẤM

- Sửa `app.py`, `db.py`, `auth.py`, `config.py`, `snapshot_service.py` (chỉ đọc)
- Đổi schema DB / tạo migration
- Thêm thư viện mới
- `git add` / `git commit` / `git push`
- Chạy app trên port `8502` (agent dùng `18502` và **dừng tiến trình sau khi kiểm tra**)
- Đổi behavior của tab khác ngoài phạm vi
- Tạo flow dữ liệu song song không cần thiết
