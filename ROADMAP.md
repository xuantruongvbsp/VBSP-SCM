# ROADMAP — Lộ trình phát triển VBSP-SCM

> Cập nhật: 2026-05-26 (đồng bộ hiện trạng)
> Dự án: Hệ thống Quản trị Tín dụng Nội bộ — NHCSXH Chi nhánh Đồng Nai

---

## Hiện trạng (đã hoàn thành)

| Mảng | Tính năng | Ghi chú |
|---|---|---|
| **Tổng quan** | Dashboard KPI, Heatmap, Bản đồ PGD, Cơ cấu dư nợ | 3 workspace (BGĐ/KH-NV/Địa bàn) |
| **Cảnh báo Tín dụng** | 8 sub-tab: Tổng hợp, Đến hạn, 3 tháng KHĐ, BT→Rủi ro, NQH phát sinh, Cảnh báo sớm, Khoanh sắp hết hạn, Gia hạn nợ | ✅ |
| **Phân tích Đến hạn** | Radio 1/3/6/12 tháng, cảnh báo tập trung đúng tỷ lệ (N tháng / tổng PGD), lọc Xã/Tổ trưởng phụ thuộc PGD | ✅ 2026-05-23 |
| **So sánh kỳ** | 20+ báo cáo so sánh 2 kỳ (chi tiết, tăng trưởng, chất lượng, PAR, HHI, Movers, Radar, Aging, KHTD...) | Lazy-load tối ưu |
| **So sánh kỳ — mốc 31/12** | Baseline song song 22 PGD (`ThreadPoolExecutor`), xuất Excel/PDF mốc 31/12 | ✅ 2026-05-23 |
| **KHTD** | Giao/Điều chỉnh KHTD, Mau07, Nhập/Xuất KHTD | Cả CN + PGD |
| **Kiểm soát** | Kiểm soát Chi nhánh đầy đủ | `kiem_soat_service.py` |
| **Upload** | 2 luồng (CN + PGD), merge 22 đơn vị, baseline 31/12 | 3 loại: HSTD/NQ11/GQVL |
| **Snapshot** | Lưu trữ dữ liệu theo kỳ, phục vụ so sánh lịch sử | ✅ |
| **Nội bộ KH-NV** | 6 sub-tab, tải đầu việc mẫu theo chức vụ VP1/VP2/CBTD, PDF tiến độ | ✅ 2026-05-20 |
| **Kiểm toán Nội bộ (KTNB)** | 4 phân hệ: Kế hoạch & Lịch trình, Chọn mẫu đối chiếu, Nhập kết quả thực tế, Giám sát & Khắc phục lỗi | ✅ 2026-05-24 |
| **Xây dựng KHTD** | Kế hoạch tín dụng 1/3/5 năm, 4 sub-tab: Biểu 01C, 02C, Thuyết minh, Tổng hợp CN | ✅ 2026-05-26 |
| **CBTD Dashboard** | KPI cards, cảnh báo thông minh CBTD/ĐGD/Tổ TK&VV, pivot cross-module, xuất báo cáo | ✅ 2026-05-26 |
| **Phối hợp PGD** | Ghi nhận và theo dõi công việc CN giao/hỗ trợ PGD | ✅ 2026-05-26 |
| **Quản lý Công văn** | Lưu trữ + tra cứu công văn đến/đi, tổng hợp theo PGD | ✅ 2026-05-26 |
| **Báo cáo v2 (package)** | Refactor tab_baocao → package: tree navigation 21 báo cáo, skeleton loader, sticky table, inline filter, tooltip, alert_suggestion | ✅ 2026-05-26 |
| **Dark Mode** | Khóa toàn hệ thống dark mode, CSS biến tương thích, 14 vị trí hardcode đã sửa | ✅ 2026-05-19 |
| **TabContext / base_tab.py** | Pattern chuẩn `render(tab=None, **kwargs)` tập trung hóa role normalization, container fallback | ✅ 2026-05-15 |
| **Hiệu năng** | Lazy-load expander, df.copy subset, cache snapshot, cache baseline status | ✅ |
| **Cold start tối ưu** | Lazy import heavy modules (−44s), DuckDB full scan → `pd.read_parquet` (−10s) → tổng **−54s** cold start | ✅ 2026-05-24 |
| **DRY services extraction** | Tách 13+ services từ tabs: `word_xln_service`, `rui_ro_aggregation`, `so_sanh_ky_service`, `cdtotkvv_service`, `khtd_mau07_service`... | ✅ 2026-05-21 |
| **Test** | **43 file, 839 test cases** ✅ vượt mục tiêu 65% | Service + core + utils + tabs |

---

## Giai đoạn 1 — Củng cố nền tảng (Q3/2026)

### 1.1 Test coverage — lấp đầy lỗ hổng

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| Test data modules | `core.excel_to_parquet()`, `hstd.danh_dau_khong_hd()`, `hstd.canh_bao_migration()` | `tests/test_data_hstd.py` | ✅ Done |
| Test tabs UI (smoke) | `tab_tongquan.py`, `tab_canh_bao_nqh.py`, `tab_no_khoanh.py` | `tests/test_smoke_imports.py` | ✅ Done |
| Test components | `delta_card`, `movers_analysis`, `export_pdf`, `filter_bar`, `loan_drawer` | `tests/test_components.py`, `tests/test_movers.py`, `tests/test_filter_bar.py` | ✅ Done 2026-05-26 |
| Test alert_center | `canh_bao_no_khoanh_sap_het_han()` | `tests/test_alert_center.py` | ✅ Done |
| Test migration_service | Logic chuyển nợ | `tests/test_migration_service.py` | ✅ Done |
| Test KTNB | `ktnb_service.py` — lịch trình, đoàn kiểm tra, kết quả lỗi | `tests/test_ktnb_service.py`, `tests/test_ktnb_db.py` | ✅ Done |
| Test XLRR & Word XLN | Hồ sơ rủi ro, word_xln_service (14 mẫu) | `tests/test_word_xln_service.py`, `tests/test_rui_ro_aggregation.py` | ✅ Done |

> **Hiện tại:** 46 file test, **717 test cases** — vượt mục tiêu ≥65% coverage.

**KPI mới:** Duy trì ≥**80%** coverage; mỗi service mới bắt buộc có test file riêng.

### 1.2 Performance — giai đoạn 2

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| Cold start optimization | Lazy import heavy modules (alert_center, status_widget) — **−44s** | `app.py` | ✅ Done 2026-05-24 |
| DuckDB full scan → pd.read_parquet | Full scan không filter dùng pandas thay DuckDB — **−10s** | `app.py:_load_hstd()` | ✅ Done 2026-05-24 |
| DuckDB query optimization | Thay pandas groupby bằng DuckDB SQL trên parquet trực tiếp | `data/core.py` + `tabs/tab_so_sanh_ky/_export.py` | ✅ Done 2026-05-26 |
| Cache chiến lược | `@st.cache_data(ttl=300)` cho tất cả hàm đọc dữ liệu | `data/core.py`, `data/hstd.py` | ✅ Done 2026-05-26 |
| Lazy-load tab_so_sanh_2_ky | Wrap 5 expander còn lại (deprecated file, thay bằng package) | `tabs/tab_so_sanh_ky/` | 🟠 TB |
| Profile & bottleneck runtime | Đo thời gian render từng tab; xác định bottleneck tiếp theo | Toàn bộ | 🟡 Thấp |

**KPI đạt:** Cold start giảm ~54s ✅ | **Còn lại:** Load tab So sánh kỳ ≤ **3s**, load tab Tổng quan ≤ **2s**

### 1.3 Trust & Quality

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Data quality dashboard | Tỷ lệ missing cột, outlier, trùng lặp theo PGD | 🟠 TB |
| Health check tự động | Script chạy mỗi sáng kiểm tra file gốc + parquet + kv_store | ✅ Done 2026-05-26 |
| Migration validation | Tự động kiểm tra dữ liệu sau merge (số dòng, tổng dư nợ) | 🟠 TB |
| TabContext adoption | Áp dụng `TabContext` từ `tabs/base_tab.py` cho tất cả tabs còn lại (~45 tabs chưa dùng) | 🟠 TB |

### 1.4 Tính năng UX ngắn hạn

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| Dashboard "Ngày hôm nay" | Widget tổng hợp: dư nợ, NQH mới, khoản đến hạn tuần này; auto-highlight PGD biến động bất thường | `workspaces/ws_executive.py` | ✅ Done 2026-05-26 |
| Alert Center phân mức | Nhóm cảnh báo 🔴/🟠/🟡, badge số lượng sidebar, trạng thái "đã đọc" vào kv_store | `alert_center.py` | ✅ Done 2026-05-26 |
| Tab card 22 PGD | Mỗi PGD = 1 card: dư nợ, NQH%, đến hạn tháng này, trạng thái upload; click → drill-down | `tabs/tab_pgd_cards.py` (tab mới) | ✅ Done 2026-05-26 |
| Lưu cấu hình lọc | Lưu bộ lọc hay dùng (PGD + CT + ĐVUT) vào kv_store, load lại khi mở app | `components/filter_bar.py` + `db.py` | ✅ Done 2026-05-26 |
| Health check tự động | Schedule chạy 6:30 sáng, kiểm tra parquet/kv_store/số dòng, cảnh báo sidebar nếu lỗi | `health_check.py` + `alert_center.py` + `scripts/setup_health_check_task.bat` | ✅ Done 2026-05-26 |

---

## Giai đoạn 2 — Báo cáo & Phân tích (Q3-Q4/2026)

### 2.1 Báo cáo xuất tự động

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Báo cáo định kỳ đơn giản | Tự tạo Excel tóm tắt mỗi sáng, lưu vào `cache/reports/`, link tải trong app (không cần SMTP) | ✅ Done 2026-05-26 |
| Mẫu báo cáo Word/PDF | Tích hợp thêm mẫu: Báo cáo tổng hợp, Báo cáo NQH, Báo cáo KHTD | ✅ Done 2026-05-26 |
| Báo cáo Excel nâng cao | Multi-sheet, conditional formatting, pivot table style | 🟠 TB |
| Gửi email tự động | Dùng SMTP NHCSXH, gửi báo cáo cho BGĐ mỗi sáng | � Thấp |

### 2.2 Phân tích nâng cao

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Phân loại khách hàng | Scoring đơn giản dựa trên lịch sử trả nợ + tần suất giao dịch | 🟠 TB |
| Stress test danh mục | Kịch bản: 3%/5% khách hàng mất khả năng trả nợ → NQH dự kiến | 🟡 Thấp |
| Biểu đồ tương tác nâng cao | Altair selection, cross-filter, tooltip động | 🟡 Thấp |
| ~~Dự báo ML (Prophet/ARIMA)~~ | ~~Dữ liệu lịch sử chưa đủ dài, overkill~~ | ❌ Loại |

### 2.3 Phân tích Đến hạn nâng cao

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| So sánh đến hạn cùng kỳ năm trước | Tháng N/2025 vs N/2026 — phát hiện PGD tăng đột biến | `services/den_han_compare_service.py` | ✅ Done 2026-05-26 |
| Thông báo đến hạn Word/PDF | Từ danh sách khoản đến hạn → thư thông báo cho từng KH | `services/` + `templates/` | 🟠 TB |
| Phân tích Tổ TK&VV | Tổ có nhiều khoản đến hạn nhất, tổ có NQH > 0 | `tabs/tab_den_han.py` | 🟡 Thấp |

### 2.4 Quản lý Công văn — hoàn thiện

> File đã tồn tại (`tab_quan_ly_cv.py`, `tab_tong_hop_cv.py`), cần bổ sung tính năng nâng cao.

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| Tìm kiếm full-text | Tra cứu công văn theo số hiệu, ngày, từ khóa nội dung | `tabs/tab_quan_ly_cv.py` | 🔴 Cao |
| Gắn tag & phân loại | Phân loại: Hướng dẫn / Quyết định / Thông báo / Báo cáo TW | `tabs/tab_quan_ly_cv.py` | 🟠 TB |
| Xuất danh sách Excel/PDF | Danh sách công văn theo kỳ, trạng thái xử lý | `tabs/tab_tong_hop_cv.py` | 🟠 TB |
| Nhắc nhở deadline | Cảnh báo công văn cần xử lý trước ngày X | `alert_center.py` | 🟡 Thấp |

### 2.5 KTNB — Kiểm toán Nội bộ Phase 2

> Phase 1 (4 phân hệ cơ bản) đã hoàn thành 2026-05-24. Phase 2 tập trung phân tích & báo cáo.

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| Báo cáo KTNB tổng hợp | Tổng hợp kết quả kiểm toán theo đoàn, theo năm; tỷ lệ lỗi theo loại | `services/ktnb_service.py` | 🔴 Cao |
| Xuất biên bản PDF | Biên bản kiểm toán đúng mẫu Ngân hàng Chính sách, ký số | `services/ktnb_service.py` + `templates/` | 🟠 TB |
| Theo dõi khắc phục lỗi | Dashboard tiến độ sửa lỗi sau kiểm toán theo PGD | `services/ktnb_service.py` | 🟠 TB |
| Lịch sử kiểm toán | Timeline cuộc kiểm toán nhiều năm; xu hướng cải thiện | `db.py` + `tabs/` | 🟡 Thấp |

### 2.6 Xây dựng KHTD — Workflow phê duyệt

> Tab đã có nhập liệu (Biểu 01C/02C/Thuyết minh). Phase 2 bổ sung vòng phê duyệt.

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| Approval workflow BGĐ | Trưởng phòng trình → BGĐ phê duyệt → lock dữ liệu | `tabs/tab_xay_dung_khtd.py` + `db.py` | 🟠 TB |
| So sánh dự báo vs thực hiện | KHTD đã duyệt vs dư nợ thực tế từng năm — biểu đồ trend | `tabs/tab_xay_dung_khtd.py` + snapshot | 🟠 TB |
| Xuất tờ trình BGĐ | Tự động tạo tờ trình Word từ Biểu 01C/02C đã nhập | `services/khtd_import_service.py` + `templates/` | 🟡 Thấp |

---

## Giai đoạn 3 — DevOps & Vận hành (Q4/2026)

### 3.1 Deployment

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Docker hóa | `Dockerfile` + `docker-compose.yml` (app + SQLite) | 🔴 Cao |
| CI/CD pipeline | GitHub Actions: py_compile → pytest → convention check → deploy | 🔴 Cao |
| Multi-instance | Load balancer cho nhiều user (>50 concurrent) | 🟡 Thấp |
| HTTPS & domain | Cấu hình domain + SSL cho truy cập từ xa | 🟡 Thấp |

### 3.2 Backup & Disaster Recovery

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Auto-backup | Cron job backup DB + parquet + PGD files mỗi ngày | 🔴 Cao |
| Retention policy | Giữ 7 daily + 4 weekly + 12 monthly backups | 🟠 TB |
| Restore drill | Script kiểm tra tính toàn vẹn của bản backup | 🟠 TB |
| Monitoring | Dashboard trạng thái: uptime, memory, disk, errors | 🟡 Thấp |

### 3.3 Security

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Audit log viewer | Giao diện tra cứu audit log theo user/thời gian/hành động | 🟠 TB |
| 2FA cho admin | Google Authenticator + backup code | 🟡 Thấp |
| Session timeout | Tự động logout sau 30 phút inactive | 🟠 TB |
| IP whitelist | Giới hạn truy cập theo IP nội bộ NHCSXH | 🟡 Thấp |

---

## Giai đoạn 4 — Tích hợp & Mở rộng (2027)

### 4.1 Tích hợp hệ thống

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| API RESTful | Flask/FastAPI nhẹ cho query dữ liệu (đọc parquet qua DuckDB) | 🟠 TB |
| Mobile UI | PWA hoặc Streamlit mobile view cho PGD đi địa bàn | � Thấp |
| ~~SSO/LDAP~~ | ~~NHCSXH không có AD domain riêng cấp Chi nhánh~~ | ❌ Loại |
| ~~Tích hợp NHCSXH TW~~ | ~~Chưa có API từ cấp trên~~ | ❌ Loại |

### 4.2 Tính năng mới (dự kiến)

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Ghi chú khoản vay | CBTD ghi chú trực tiếp vào drawer, lưu SQLite `loan_notes`, badge 📝 trong bảng | `components/loan_drawer.py` + `db.py` | 🟠 TB |
| ~~Quản lý văn bản~~ | ~~Đã triển khai tại Giai đoạn 2.4 (tab_quan_ly_cv + tab_tong_hop_cv)~~ | ✅ Chuyển lên §2.4 |
| Biểu đồ GIS | Bản đồ tương tác: khoanh vùng rủi ro theo xã | 🟡 Thấp |
| Ứng dụng Desktop | Đóng gói bằng PyInstaller hoặc Nuitka | 🟡 Thấp |
| ~~Chatbot nội bộ~~ | ~~Phụ thuộc LLM external, không phù hợp môi trường nội bộ~~ | ❌ Loại |

---

## Lộ trình theo thời gian

```
Q3/2026                    Q4/2026                    2027
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ ✅ 1.1 Test ≥80% │  │ 2.4 Quản lý CV   │  │ 4.1 API RESTful   │
│ ✅ 1.2 Cold -54s │  │ 2.5 KTNB Phase 2 │  │ 4.2 Tính năng mới │
│ 1.3 Health check │  │ 2.6 KHTD Approval│  │ 4.2 Ghi chú KV    │
│ 1.3 TabContext   │  │ 3.1 Deployment   │  │                   │
│ 1.4 Filter save  │  │ 3.2 Backup       │  │                   │
│ 1.4 Health sched │  │ 3.3 Security     │  │                   │
│                   │  │ 2.1 Báo cáo auto │  │                   │
│                   │  │ 2.2 Phân tích    │  │                   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## Nguyên tắc ưu tiên

1. **Không làm hỏng chức năng đang chạy** → test trước khi deploy
2. **Test coverage lên trước** → feature mới sau
3. **Hiệu năng ảnh hưởng trải nghiệm** → tối ưu trước khi thêm tính năng
4. **Bảo mật là bắt buộc** → audit log sau mọi thao tác ghi
5. **Không thêm dependency mới** (trừ khi thực sự cần)
6. **Mỗi thay đổi = 1 entry CHANGELOG.md**

---

## Cập nhật ROADMAP

| Ngày | Người | Thay đổi |
|---|---|---|
| 2026-05-23 | — | Khởi tạo phiên bản mới — 4 giai đoạn |
| 2026-05-23 | — | Cập nhật hiện trạng (+4 mục), thêm mục 1.4 UX ngắn hạn, 2.3 Đến hạn nâng cao; loại 5 mục không khả thi |
| 2026-05-26 | — | ✅ Hoàn thành GĐ2: Báo cáo Excel/Word định kỳ + So sánh đến hạn cùng kỳ năm trước |
| 2026-05-26 | — | ✅ Hoàn thành §1.1 Test components: test_components.py 27 tests (delta_card, movers, loan_drawer, tongquan_service) |
| 2026-05-26 | — | ✅ Hoàn thành §1.3 Health check: check DB, kv_store, parquet, PGD uploads, audit log, alert sidebar |
| 2026-05-26 | — | ✅ Hoàn thành §1.4: Lưu cấu hình lọc (filter_bar preset save/load/auto-load vào kv_store) |
| 2026-05-26 | — | ✅ Hoàn thành ROADMAP §1.2: DuckDB aggregates (4 hàm mới trong data/core.py), cache TTL, DuckDB cho _export.py |
| 2026-05-26 | — | Hoàn thành 3/5 tính năng 1.4: Tab card 22 PGD, Alert Center phân mức, Dashboard Hôm nay BGĐ |
| 2026-05-26 | — | Đồng bộ hiện trạng: bổ sung 9 mục đã hoàn thành (KTNB, Xây dựng KHTD, CBTD Dashboard, Phối hợp PGD, Quản lý CV, Báo cáo v2, Dark Mode, TabContext, Cold start); nâng KPI test ≥80%; thêm §2.4–2.6 (Quản lý CV, KTNB P2, KHTD Approval); health check lên 🔴 Cao |
