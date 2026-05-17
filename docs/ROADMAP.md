# ROADMAP — VBSP-SCM

> **Phiên bản:** 2.0 (hợp nhất)  
> **Cập nhật lần cuối:** 17/05/2026  
> **Mục tiêu:** Ổn định, mở rộng, dễ bảo trì cho 20+ users, 22 đơn vị, sẵn sàng sáp nhập Bình Phước.

---

## ✅ Hoàn thành gần đây

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| **O1** | **Tối ưu RAM: DuckDB read_parquet + filter pushdown** | `app.py`, `services/kiem_soat_service.py`, `tabs/tab_kiem_soat.py` | 16/05 — Giảm 60% RAM cho CN role, lọc theo PGD ngay tầng đĩa |
| **O2** | **Khôi phục file hệ thống bị mất** | `pdf_service.py` (root), `gen_dcgiam_sheet.py` | 16/05 — 22 files import pdf_service, 3 refs gen_dcgiam_sheet |
| **O3** | **Fix ws_management: NameError + TypeError** | `workspaces/ws_management.py` | 16/05 — Đưa import tab lên module-level, fix kwargs conflict |
| **O4** | **Rules: thêm Section 9B — Nguyên tắc trước khi xóa** | `.trae/rules/project_rules.md` | 16/05 — Quy trình 6 bước bắt buộc, bài học từ 4 trường hợp |
| **O5** | **Cập nhật codebase_for_ai.md** | `codebase_for_ai.md` | 16/05 — Reflect thay đổi: DuckDB + pdf_service root + gen_dcgiam_sheet |

---

## 🚀 Đang triển khai

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| **R1** | **Phân hệ lập báo cáo (Word/Excel, không template)** | `tabs/tab_bao_cao.py` *(mới)*, `services/report_service.py` | Đang thiết kế schema báo cáo động |
| **R2** | **Tối ưu RAM toàn diện: giảm 30→8 MB per session** | `app.py`, `data/core.py`, `services/*.py` | Chuyển tất cả pandas groupby → DuckDB SQL qua `read_parquet` |
| **R3** | **Dọn dẹp thư mục `_archive/`** | toàn bộ project | Xóa hoặc chuyển vào branch `legacy/` — giảm nhiễu codebase |
| **R4** | **Thêm type hints cho toàn bộ functions** | `utils.py`, `data/*.py`, `services/*.py` | Dùng `mypy` kiểm tra, tăng khả năng tự động hoàn thiện code |

---

## 📋 Backlog chiến lược (theo thứ tự ưu tiên)

| Ưu tiên | # | Việc | File liên quan | Phụ thuộc | Ghi chú |
|---------|---|------|----------------|-----------|---------|
| 🔴 **Cao** | **S1** | **Xử lý lỗi ngoại lệ tập trung** | `app.py`, tất cả modules đọc file/DB | — | Bọc try-except quanh file I/O, DuckDB, Excel → tránh crash đột ngột |
| 🔴 **Cao** | **S2** | **Validate schema khi đọc Excel** | `data/hstd.py`, `data/core.py` | — | Kiểm tra cột bắt buộc trước khi xử lý, báo lỗi rõ ràng |
| 🔴 **Cao** | **S3** | **Base class cho các tabs** | `tabs/base_tab.py` mới, 40+ tabs | — | Giảm duplicate code, đồng bộ logic render, filter, export |
| 🟠 **Trung bình** | **S4** | **Centralized State Manager** | `state_manager.py` mới | — | Thay thế `st.session_state` trực tiếp, cung cấp API get/set/reset |
| 🟠 **Trung bình** | **S5** | **Unit tests cho core services** | `tests/test_upload.py`, `tests/test_merge.py`, ... | — | Coverage >70% cho `services/` và `data/` |
| 🟠 **Trung bình** | **S6** | **Lock mechanism cho upload** | `upload_service.py` | — | Dùng `filelock` tránh 2 user upload cùng lúc corrupt data |
| 🟠 **Trung bình** | **S7** | **Re-organize tabs thành sub-packages** | `tabs/bao_cao/`, `tabs/quan_ly_tin_dung/`, ... | S3 | Dễ điều hướng, dễ mở rộng |
| 🟠 **Trung bình** | **S8** | **Snapshot tự động: Direction A/B/C delta** | `snapshot_service.py`, `tab_so_sanh_ky.py` | — | So sánh 2 snapshot → trend, heatmap |
| 🟠 **Trung bình** | **S9** | **PDF báo cáo tự động hàng tháng** | `components/export_pdf.py`, `tab_baocao.py` | R1 | Xuất PDF chuẩn NHCSXH không cần Word template |
| 🟡 **Thấp** | **S10** | **Dashboard real-time alert** | `alert_center.py`, `tab_canh_bao_som.py` | — | Push alert khi NQH tăng, KHĐ, tổ sai TV |
| 🟡 **Thấp** | **S11** | **Dynamic NDT registry (`tab_ndt.py`)** | `tab_ndt.py` mới, `config.py` | — | Thay hằng số `MA_NDT_CAP_TINH_DUOI` cứng |
| 🟡 **Thấp** | **S12** | **Tiered GQVL pipeline** | `gen_dcgiam_sheet.py`, `khtd_service.py` | — | Cross-ref HSTDCT + GQVL qua số khế ước |
| 🟡 **Thấp** | **S13** | **Multi-tenant: sáp nhập Bình Phước data** | `config.py`, `auth.py`, `data/pgd.py` | — | Tách biệt 2 tỉnh, switch context |
| 🟡 **Thấp** | **S14** | **Cache strategy: version + TTL** | `app.py`, `data/core.py` | — | Thay `st.cache_data.clear()` toàn bộ bằng cache version để không ảnh hưởng user khác |
| 🟡 **Thấp** | **S15** | **Monitoring & Alerting (Prometheus + Grafana)** | thêm metrics vào services | — | Phát hiện sớm lỗi hiệu năng, upload thất bại |

> **Ghi chú ưu tiên:** Các mục từ S1 đến S3 là cần thiết ngay để giảm lỗi runtime và nợ kỹ thuật. Các mục S8–S15 có thể triển khai song song nếu có nguồn lực.

---

## 🗑️ Không làm (đã xem xét và bỏ)

| Việc | Lý do |
|---|---|
| Chuyển sang React/Next.js | Quá tốn công, 20 users nội bộ không cần |
| `streamlit-aggrid` | Thêm dependency nặng, không cần thiết |
| Tab GQVL cho `ws_management` | Đã ẩn theo yêu cầu, giữ file |
| Tách `pdf_service.py` thành microservice | Không cần, hiện tại đủ tốt |
| Dùng Redis thay SQLite cho kv_store | Quá mức, SQLite đáp ứng đủ |

---

## 🧠 Kiến trúc hiệu năng — đã & đang cải thiện

| Lớp | Trước 16/05 | Sau 16/05 | Mục tiêu |
|---|---|---|---|
| Load HSTD | `SELECT * FROM parquet` → 30 MB RAM | `read_parquet WHERE ...` → 3–8 MB RAM | ✅ Đạt |
| CN role | Load toàn bộ + filter pandas | `active_only=True` → chỉ hồ sơ còn dư nợ | ✅ Đạt |
| PGD role | Load toàn bộ 30 MB | `ten_pgd=...` → chỉ PGD đó | ✅ Đạt |
| Groupby/tổng hợp | pandas `.groupby().agg()` | DuckDB SQL → tận dụng columnar engine | 🔄 Đang làm (R2) |
| Cache strategy | `@st.cache_data` per df | `@st.cache_resource` per (path, filter) | ✅ Đạt |
| RAM per session | ~30 MB | ~8 MB (target) | 🔄 Đang làm (R2) |

---

## 🔄 Tính năng đang thảo luận — chờ làm rõ nghiệp vụ

### CBTD ↔ ĐGD Integration

**Vấn đề:** Hai hệ thống hiện tại độc lập:
- CBTD  →  `Mã thôn` (flat list, kv_store key=`"cbtd"`)
- PGD–Xã → ĐGD → `Ấp` (kv_store key=`"dgd_map"`)

Thực tế nghiệp vụ cần: **CBTD → [ĐGD] → [Ấp/Thôn]**

**Hướng đề xuất tạm thời (chờ nghiệp vụ):**
- Thêm `ds_dgd` vào `cbtd_data` → tự động suy ra `ds_thon` từ `dgd_map`
- Thêm hàm `gan_cbtd_vao_df(df, cbtd_data)` → join `Mã thôn` → cột `"CBTD"` → biểu đồ dư nợ theo CBTD

**Files liên quan:** `tabs/tab_cbtd.py`, `tabs/tab_diem_gd_pgd.py`, `data/khtd.py`, `db.py`, `data/dgd_helpers.py`

**Câu hỏi nghiệp vụ còn mở** (không implement cho đến khi có câu trả lời):
1. 1 CBTD phụ trách bao nhiêu ĐGD? Có thay đổi theo tháng không?
2. 1 ĐGD có thể do nhiều CBTD cùng phụ trách không?
3. CBTD gán vào ĐGD → phụ trách toàn bộ thôn hay chỉ một phần?
4. CBTD có thể chéo PGD không?
5. File HSTD có cột CBTD sẵn không hay chỉ suy từ `"Mã thôn"`?
6. Danh sách CBTD lấy từ đâu (nhập tay hay từ hệ thống)?
7. Mục tiêu dùng CBTD để làm gì (báo cáo hiệu suất, lọc dư nợ, phân công địa bàn)?

---

## 📌 Ghi chú kỹ thuật quan trọng

- **GSheet ID DCGIAM:** `15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk`
- **4 key ĐP đã thêm vào config:** `9_DP`, `12_DP`, `17_DP`, `26_DP`
- **Đơn vị tiền tệ:** `×1e6` (triệu → VND) — **KHÔNG dùng `×1e9`**
- **Tab context chuẩn:** `_tab_ctx = tab if tab is not None else st.container()`
- **Quy tắc sống còn:** Trước khi xóa bất kỳ file/thư mục nào → Grep toàn bộ codebase (xem `.trae/rules/project_rules.md` Section 9B)
- **Load HSTD:** `_load_hstd(cache_path, _ts, ten_pgd=None, active_only=False)` — cache per (path, ts, pgd, active) qua `@st.cache_resource`
- **`pdf_service.py` ở ROOT** là phiên bản chính (22 files import), **KHÔNG** phải bản trong `tabs/`

---

## 📅 Lộ trình đề xuất theo phase

| Phase | Thời gian | Trọng tâm | Các mục chính |
|-------|-----------|-----------|----------------|
| **Phase 1** | Tháng 6–7/2026 | Củng cố nền tảng | S1, S2, S3, R3, R4 |
| **Phase 2** | Tháng 8–9/2026 | Nâng cao maintainability & testing | S4, S5, S6, S7 |
| **Phase 3** | Tháng 10–11/2026 | Tối ưu & mở rộng | S8, S9, S10, S14, S15 (và S11–S13 nếu có nguồn lực) |

---

**Roadmap này thay thế phiên bản cũ và sẽ được cập nhật sau mỗi sprint.**
Mọi đề xuất thay đổi cần được thảo luận và ghi lại lịch sử.
