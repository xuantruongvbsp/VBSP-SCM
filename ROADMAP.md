# ROADMAP — Lộ trình phát triển VBSP-SCM

> Cập nhật: 2026-05-26
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
| **Hiệu năng** | Lazy-load expander, df.copy subset, cache snapshot, cache baseline status | ✅ |
| **Test** | 31 file, ~320 test cases | Service + core + utils |

---

## Giai đoạn 1 — Củng cố nền tảng (Q3/2026)

### 1.1 Test coverage — lấp đầy lỗ hổng

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| Test data modules | `core.excel_to_parquet()`, `hstd.danh_dau_khong_hd()`, `hstd.canh_bao_migration()` | `tests/test_data_hstd.py` | 🔴 Cao |
| Test tabs UI (smoke) | `tab_tongquan.py`, `tab_canh_bao_nqh.py`, `tab_no_khoanh.py` | `tests/test_tabs_smoke.py` | 🔴 Cao |
| Test components | `delta_card`, `movers_analysis`, `export_pdf`, `filter_bar`, `loan_drawer` | `tests/test_components.py` | 🔴 Cao |
| Test alert_center | `canh_bao_no_khoanh_sap_het_han()` | `tests/test_alert_center.py` | 🟠 TB |
| Test migration_service | Logic chuyển nợ | `tests/test_migration_service.py` | 🟠 TB |

**KPI:** Coverage từ ~45% → **≥65%**

### 1.2 Performance — giai đoạn 2

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| DuckDB query optimization | Thay pandas groupby bằng DuckDB SQL trên parquet trực tiếp | `tabs/tab_so_sanh_ky.py` | 🔴 Cao |
| Cache chiến lược | `@st.cache_data(ttl=300)` cho tất cả hàm đọc dữ liệu | `data/core.py`, `data/hstd.py` | 🔴 Cao |
| Lazy-load tab_so_sanh_2_ky | Wrap 5 expander còn lại | `tabs/tab_so_sanh_2_ky.py` | 🟠 TB |
| Profile & bottleneck | Dùng `cProfile` hoặc Streamlit native profiler | Toàn bộ | 🟡 Thấp |

**KPI:** Load tab So sánh kỳ ≤ **3s**, load tab Tổng quan ≤ **2s**

### 1.3 Trust & Quality

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Data quality dashboard | Tỷ lệ missing cột, outlier, trùng lặp theo PGD | 🟠 TB |
| Health check tự động | Script chạy mỗi sáng kiểm tra file gốc + parquet + kv_store | 🟠 TB |
| Migration validation | Tự động kiểm tra dữ liệu sau merge (số dòng, tổng dư nợ) | 🟠 TB |

### 1.4 Tính năng UX ngắn hạn

| Mục tiêu | Chi tiết | File liên quan | Ưu tiên |
|---|---|---|---|
| Dashboard "Ngày hôm nay" | Widget tổng hợp: dư nợ, NQH mới, khoản đến hạn tuần này; auto-highlight PGD biến động bất thường | `workspaces/ws_executive.py` | ✅ Done 2026-05-26 |
| Alert Center phân mức | Nhóm cảnh báo 🔴/🟠/🟡, badge số lượng sidebar, trạng thái "đã đọc" vào kv_store | `alert_center.py` | ✅ Done 2026-05-26 |
| Tab card 22 PGD | Mỗi PGD = 1 card: dư nợ, NQH%, đến hạn tháng này, trạng thái upload; click → drill-down | `tabs/tab_pgd_cards.py` (tab mới) | ✅ Done 2026-05-26 |
| Lưu cấu hình lọc | Lưu bộ lọc hay dùng (PGD + CT + ĐVUT) vào kv_store, load lại khi mở app | `components/filter_bar.py` + `db.py` | 🟠 TB |
| Health check tự động | Schedule chạy 6:30 sáng, kiểm tra parquet/kv_store/số dòng, cảnh báo sidebar nếu lỗi | `health_check.py` | 🟠 TB |

---

## Giai đoạn 2 — Báo cáo & Phân tích (Q3-Q4/2026)

### 2.1 Báo cáo xuất tự động

| Mục tiêu | Chi tiết | Ưu tiên |
|---|---|---|
| Báo cáo định kỳ đơn giản | Tự tạo Excel tóm tắt mỗi sáng, lưu vào `cache/reports/`, link tải trong app (không cần SMTP) | 🔴 Cao |
| Mẫu báo cáo Word/PDF | Tích hợp thêm mẫu: Báo cáo tổng hợp, Báo cáo NQH, Báo cáo KHTD | 🔴 Cao |
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
| So sánh đến hạn cùng kỳ năm trước | Tháng N/2025 vs N/2026 — phát hiện PGD tăng đột biến | `data/den_han.py` + `tabs/tab_den_han.py` | 🟠 TB |
| Thông báo đến hạn Word/PDF | Từ danh sách khoản đến hạn → thư thông báo cho từng KH | `services/` + `templates/` | 🟠 TB |
| Phân tích Tổ TK&VV | Tổ có nhiều khoản đến hạn nhất, tổ có NQH > 0 | `tabs/tab_den_han.py` | 🟡 Thấp |

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
| Quản lý văn bản | Lưu trữ + tra cứu công văn, quyết định, hướng dẫn | 🟡 Thấp |
| Biểu đồ GIS | Bản đồ tương tác: khoanh vùng rủi ro theo xã | 🟡 Thấp |
| Ứng dụng Desktop | Đóng gói bằng PyInstaller hoặc Nuitka | 🟡 Thấp |
| ~~Chatbot nội bộ~~ | ~~Phụ thuộc LLM external, không phù hợp môi trường nội bộ~~ | ❌ Loại |

---

## Lộ trình theo thời gian

```
Q3/2026                    Q4/2026                    2027
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ 1.1 Test         │  │ 2.1 Báo cáo tự động│  │ 4.1 API RESTful   │
│ 1.2 Performance  │  │ 2.2 Phân tích     │  │ 4.2 Tính năng mới │
│ 1.3 Data Quality │  │ 2.3 Đến hạn nâng │  │ 4.2 Ghi chú KV    │
│ 1.4 UX ngắn hạn  │  │ 3.1 Deployment   │  │                   │
│ → Test ≥65%      │  │ 3.2 Backup       │  │                   │
│ → Load ≤3s       │  │ 3.3 Security     │  │                   │
│ → Dashboard hôm  │  │                   │  │                   │
│   nay + Alert    │  │                   │  │                   │
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
| 2026-05-26 | — | Hoàn thành 3/5 tính năng 1.4: Tab card 22 PGD, Alert Center phân mức, Dashboard Hôm nay BGĐ |
