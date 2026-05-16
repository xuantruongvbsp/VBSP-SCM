# ROADMAP — VBSP-SCM
> Cập nhật lần cuối: 16/05/2026

---

## ✅ Hoàn thành gần đây

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| **O1** | **Tối ưu RAM: DuckDB read_parquet + filter pushdown** | `app.py`, `services/kiem_soat_service.py`, `tabs/tab_kiem_soat.py` | 16/05 — Giảm 60% RAM cho CN role, lọc theo PGD ngay tầng đĩa |
| **O2** | **Khôi phục file hệ thống bị mất** | `pdf_service.py` (root), `gen_dcgiam_sheet.py` | 16/05 — 22 files import pdf_service, 3 refs gen_dcgiam_sheet |
| **O3** | **Fix ws_management: NameError + TypeError** | `workspaces/ws_management.py` | 16/05 — Đưa import tab lên module-level, fix kwargs conflict |
| **O4** | **Rules: thêm Section 9B — Nguyên tắc trước khi xóa** | `.trae/rules/project_rules.md` | 16/05 — Quy trình 6 bước bắt buộc, bài học máu 4 trường hợp |
| **O5** | **Cập nhật codebase_for_ai.md** | `codebase_for_ai.md` | 16/05 — Reflect thay đổi: DuckDB + pdf_service root + gen_dcgiam_sheet |

---

## Đang triển khai

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| **R1** | **Phân hệ lập báo cáo (Word/Excel, không template)** | `tabs/tab_bao_cao.py` *(mới)*, `services/report_service.py` | Đang thiết kế |
| **R2** | **Tối ưu RAM toàn diện: giảm 30→ 8 MB per session** | `app.py`, `data/core.py`, `services/*.py` | Chuyển tất cả pandas groupby → DuckDB SQL qua read_parquet |

---

## Backlog chiến lược — Chưa bắt đầu

| # | Việc | File liên quan | Phụ thuộc | Ghi chú |
|---|---|---|---|---|
| **S1** | **Snapshot tự động: Direction A/B/C delta** | `snapshot_service.py`, `tab_so_sanh_ky.py` | — | So sánh 2 snapshot → trend, heatmap |
| **S2** | **PDF báo cáo tự động hàng tháng** | `components/export_pdf.py`, `tab_baocao.py` | R1 | Xuất PDF chuẩn NHCSXH không cần Word template |
| **S3** | **Dashboard real-time alert** | `alert_center.py`, `tab_canh_bao_som.py` | — | Push alert khi NQH tăng, KHĐ, tổ sai TV |
| **S4** | **Dynamic NDT registry (`tab_ndt.py`)** | `tab_ndt.py` *(mới)*, `config.py` | — | Thay hằng số `MA_NDT_CAP_TINH_DUOI` cứng |
| **S5** | **Tiered GQVL pipeline** | `gen_dcgiam_sheet.py`, `khtd_service.py` | — | Cross-ref HSTDCT + GQVL qua số khế ước |
| **S6** | **Xác định mã NDT Bình Phước** | *(manual)* | S4 | Tra từ file GQVL thực tế sau khi có S4 |
| **S7** | **Multi-tenant: sáp nhập Bình Phước data** | `config.py`, `auth.py`, `data/pgd.py` | — | Tách biệt 2 tỉnh, switch context |

---

## Không làm (đã xem xét và bỏ)

| Việc | Lý do |
|---|---|
| Chuyển sang React/Next.js | Quá tốn công, 20 users nội bộ không cần |
| streamlit-aggrid | Thêm dependency nặng, không cần thiết |
| Tab GQVL cho ws_management | Đã ẩn theo yêu cầu, giữ file |

---

## Kiến trúc hiệu năng — đã & đang cải thiện

| Lớp | Trước 16/05 | Sau 16/05 | Mục tiêu |
|---|---|---|---|
| Load HSTD | `SELECT * FROM parquet` → 30 MB RAM | `read_parquet WHERE ...` → 3–8 MB RAM | ✅ Đạt |
| CN role | Load toàn bộ + filter pandas | `active_only=True` → chỉ hồ sơ còn dư nợ | ✅ Đạt |
| PGD role | Load toàn bộ 30 MB | `ten_pgd=...` → chỉ PGD đó | ✅ Đạt |
| Groupby/tổng hợp | pandas `.groupby().agg()` | DuckDB SQL → tận dụng columnar engine | 🔄 Đang làm |
| Cache strategy | `@st.cache_data` per df | `@st.cache_resource` per (path, filter) | ✅ Đạt |

---

## Tính năng đang thảo luận — chờ làm rõ nghiệp vụ

### CBTD ↔ ĐGD Integration
**Vấn đề:** Hai hệ thống hiện tại độc lập:
```
CBTD  →  [Mã thôn]     (flat list, kv_store key="cbtd")
PGD-Xã → ĐGD → [Ấp]   (kv_store key="dgd_map")
```
Thực tế nghiệp vụ cần: `CBTD → [ĐGD] → [Ấp/Thôn]`

**Hướng đề xuất:**
- Thêm `ds_dgd` vào `cbtd_data` → tự động suy ra `ds_thon` từ `dgd_map`
- Thêm hàm `gan_cbtd_vao_df(df, cbtd_data)` → join `Mã thôn` → cột `"CBTD"` → biểu đồ dư nợ theo CBTD

**Files liên quan:** `tabs/tab_cbtd.py`, `tabs/tab_diem_gd_pgd.py`, `data/khtd.py`, `db.py`, `data/dgd_helpers.py`

**Câu hỏi nghiệp vụ còn mở (chưa implement cho đến khi có câu trả lời):**
1. 1 CBTD phụ trách bao nhiêu ĐGD? Có thay đổi theo tháng không?
2. 1 ĐGD có thể do nhiều CBTD cùng phụ trách không?
3. CBTD gán vào ĐGD → phụ trách toàn bộ thôn hay chỉ một phần?
4. CBTD có thể chéo PGD không?
5. File HSTD có cột CBTD sẵn không hay chỉ suy từ `"Mã thôn"`?
6. Danh sách CBTD lấy từ đâu (nhập tay hay từ hệ thống)?
7. Mục tiêu dùng CBTD để làm gì (báo cáo hiệu suất, lọc dư nợ, phân công địa bàn)?

---

## Ghi chú kỹ thuật còn mở

- GSheet ID: `DCGIAM_SHEET_ID = 15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk`
- 4 key ĐP đã thêm vào config: `9_DP`, `12_DP`, `17_DP`, `26_DP`
- Đơn vị tiền tệ: `×1e6` (triệu → VND) — **KHÔNG dùng `×1e9`**
- Tab context chuẩn: `_tab_ctx = tab if tab is not None else _st.container()`
- **Quy tắc sống còn:** Trước khi xóa bất kỳ file/thư mục nào → Grep toàn bộ codebase (xem `.trae/rules/project_rules.md` Section 9B)
- `_load_hstd(cache_path, _ts, ten_pgd=None, active_only=False)` — cache per (path, ts, pgd, active) qua `@st.cache_resource`
- `pdf_service.py` ở ROOT là phiên bản chính (22 files import), KHÔNG phải bản trong `tabs/`
