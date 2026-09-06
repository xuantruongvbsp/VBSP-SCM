# Thiết kế lại mục 👔 CBTD & Địa bàn → "Cán bộ tín dụng" (tab_cbtd.py) Implementation Plan

> Mục tiêu: User báo "phần Cán bộ tín dụng tôi thấy chưa được hay lắm" → Thiết kế lại tab "👔 Cán bộ tín dụng" theo nghiệp vụ thực tế VBSP Chi nhánh Đồng Nai: Thay vì chỉ 3 sub-tab xem (Danh sách / Bản đồ / Chi tiết) như hiện tại, tổ chức lại thành **6 nhóm nghiệp vụ theo luồng công việc thực tế CBTD từ đầu tháng → cuối tháng**.

---

## 1. Repository Research — Hiện trạng TAB "👔 Cán bộ tín dụng" (sửa sau WS_Management line 77)

### 1.1 Hiện trạng Tab CBTD (tabs/tab_cbtd.py, ~900 dòng)

```
📋 Danh sách CBTD  (Quản lý CRUD thông tin cá nhân / mã CB / phụ trách ĐGD)
├── Bộ lọc (search, PGD, workload, sort)
├── Form ➕ Thêm CBTD mới (schema v3: Họ tên · PGD · Chức vụ · Ngày bổ nhiệm · SĐT · Ghi chú · ĐGD phụ trách)
├── Form ✏️ Sửa CBTD
└── 🗑️ Xóa CBTD

🗺️ Bản đồ ĐGD → CBTD  (Kiểm tra trùng/thiếu ĐGD phụ trách)
└── Bảng (PGD · Xã · ĐGD · CBTD phụ trách · Trạng thái: có / chưa có CBTD)

🔎 Chi tiết CBTD  (Selectbox chọn 1 CBTD → xem hồ sơ năng lực)
├── 1. Thông tin cá nhân (mã CB, tên, SĐT, chức vụ, ngày bổ nhiệm, PGD)
├── 2. Địa bàn phụ trách (ĐGD · Số ấp/thôn phụ trách)
├── 3. KPI HSTD thực tế (Tổng KH · Tổng dư nợ · Tỷ lệ NQH · Lãi tích lũy)
└── 4. Danh sách Tổ TK&VV thuộc địa bàn (xếp loại A/B/C điểm tổ)
```

### 1.2 Vấn đề user báo "Chưa được hay lắm"

| # | Vấn đề nghiệp vụ | Giải thích tại sao user không ưng |
|---|---|---|
| **1** | Thiếu luồng công việc **ĐẦU THÁNG (01-10)** | CBTD đầu tháng cần: (a) Phân công Địa bàn / Tổ TK&VV phụ trách; (b) Nhận KHTD giao chỉ tiêu; (c) Xem hồ sơ KH chưa vay / vay hạn mức dư nợ tăng giảm theo kỳ. Tab hiện tại không có 3 mục này. |
| **2** | Thiếu luồng công việc **GIỮA THÁNG (11-20)** | CBTD giữa tháng cần: (a) Đôn đốc giải ngân còn hạn mức; (b) Giải ngân mới hợp đồng; (c) Theo dõi hợp đồng đến hạn trả nợ tháng; (d) Kiểm soát NQH 30/60/90 ngày tại địa bàn mình phụ trách. Tab hiện tại chỉ có KPI HSTD tổng → không drill down đến từng hợp đồng / từng ngày đến hạn. |
| **3** | Thiếu luồng công việc **CUỐI THÁNG (21-30/31)** | CBTD cuối tháng cần: (a) Tổng hợp kết quả thi công KHTD tháng; (b) Xuất báo cáo 10 loại mẫu biểu; (c) Chấm điểm xếp hạng CBTD tháng; (d) Soạn thảo nội dung giao ban ngày 01 tháng sau. Tab hiện tại không có các mục này. |
| **4** | Mục "Chi tiết CBTD" (Sub-tab 3) hiển thị KPI quá chung | KPI hiện tại là toàn bộ thời gian (từ ngày có HSTD đến nay). User cần **(i) KPI THÁNG NÀY** · **(ii) SO SÁNH THÁNG TRƯỚC** · **(iii) THỰC HIỆN / CHỈ TIÊU** (theo KHTD đã giao) — 3 view thời gian khác nhau, kèm đèn giao dịch (đạt / gần đạt / chưa đạt). |
| **5** | Không có mục "Công việc hôm nay" màn hình chính CBTD | Khi CBTD login vào app → màn hình đầu tiên sau chọn role nên là: "Hôm nay bạn có 8 hợp đồng đến hạn trả nợ + 3 đơn chờ giải ngân + 2 hợp đồng NQH quá 30 ngày → xử lý ngay". Tab hiện tại không có dashboard công việc cá nhân CBTD. |
| **6** | Không phân bổ Tổ TK&VV cho từng CBTD chi tiết | ĐGD → CBTD có, nhưng **Tổ TK&VV → CBTD phụ trách** chưa có mapping trực tiếp → CDTOTKVV thống kê theo CBTD chưa làm được (hiện tại chỉ theo PGD/Xã/ĐGD). User yêu cầu 03/09 muốn xem "Thống kê tuổi Tổ trưởng theo từng CBTD phụ trách". |
| **7** | Form CRUD CBTD (Sub-tab 1) tách rời khỏi luồng | User cần "click 1 CBTD → dropdown menu" có 8 lựa chọn (Xem thông tin · Phân công lại ĐGD · Phân công Tổ TK&VV · Giao KHTD · Xem KPI tháng · Đôn đốc đến hạn · Xếp hạng CBTD · Xuất PDF hồ sơ) thay vì phải qua 3 sub-tab khác nhau. |

### 1.3 Các module/code hiện tại liên quan có thể tái sử dụng

| File hiện có | Chức năng hiện tại | Tái sử dụng cho thiết kế mới |
|---|---|---|
| `services/cbtd_dia_ban_service.py` | `lay_to_theo_cbtd()` · `canh_bao_cbtd_dia_ban()` · `tom_tat_kpi()` | ✅ Reuse full: Đã cross-join CBTD → ĐGD → Tổ TK&VV. Chỉ cần enrich thêm mapping Tổ → CBTD (mapping theo ĐGD phụ trách nếu chưa có). |
| `data/khtd.py` line 67-177 | SQLite bảng CBTD · helper `them_cot_cbtd_vao_df()` groupby theo CBTD | ✅ Reuse full: Schema bảng kv_store `cbtd_data` key đã có · Đã có hàm join CBTD vào HSTD (dùng cho báo cáo tổng hợp). |
| `tabs/tab_cbtd.py` line 118-325 | PDF hồ sơ năng lực CBTD 4 block | ✅ Reuse full cho mục (2g) Xuất PDF hồ sơ năng lực, chỉ cần thêm block 5 "KPI tháng N vs chỉ tiêu" vào PDF. |
| `tabs/tab_cbtd.py` line 491-667 | 3 sub-tab xem cũ | 🗂️ Dịch chuyển vào **Nhóm 1 (Quản lý hồ sơ)**. Không delete code cũ — tổ chức lại vị trí. |
| `db.py doc_dgd_map()` / `doc_kv("cbtd_data")` | kv_store persist ĐGD map + CBTD map | ✅ Reuse 100%. |
| `tabs/tab_don_doc_khd.py` | Đôn đốc 3 tháng không hoạt động — CBTD | ✅ Dịch vào **Nhóm 3 (Đôn đốc & Kiểm soát)** (tách riêng theo CBTD, không theo toàn PGD). |

---

## 2. Cấu trúc mới đề xuất cho Tab "👔 Cán bộ tín dụng" (6 nhóm nghiệp vụ theo đầu/giữa/cuối tháng)

Thay vì 3 sub-tab (Danh sách / Bản đồ / Chi tiết) hiện tại, tổ chức lại thành **6 nhóm (tabs level-2)** theo thứ tự ưu tiên luồng công việc thực tế CBTD VBSP:

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 📌 Màn hình CHÍNH (Dashboard Công việc CÁ NHÂN CBTD) — Khi chọn 👔 Cán bộ tín dụng → MỞ ĐẦU │
│ ┌───────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Xin chào **CBTD 01 — Võ Thị Thủy** (PGD Long Khánh · Đội CBTD số 2 · 2 năm kinh nghiệm) │ │
│ │ ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐            │ │
│ │ │ 🔔 Hôm nay   | ⚠️ Đến hạn TN | 🚨 NQH > 30 ngày| 💰 Chưa Giải ngân| 📊 KPI tháng |            │ │
│ │ │ 8 mục cần làm|     8 HĐ      |    2 HĐ       |    3 đơn      |  78.5 / 100  |            │ │
│ │ └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘            │ │
│ │ Đèn giao dịch KPI THÁNG 8/2026 (Chỉ tiêu / Thực hiện · %):                             │ │
│ │ 🟢 Dư nợ 78%   🟢 Giải ngân 85%  🟢 KH mới 92%  🟡 NQH 11% (>10% → vàng)  🔴 Tổ mới 40% │ │
│ └───────────────────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────────────────┘

Level-2 Tabs MỚI (6 tabs) theo luồng công việc VBSP:

  📊 Trang chủ cá nhân   👥 Quản lý hồ sơ CBTD   📋 KHTD & Giao chỉ tiêu   💰 Tác nghiệp & Đôn đốc   📈 Xếp hạng & Báo cáo   🛠️ Công cụ bổ trợ
  ───────────────────   ──────────────────────   ────────────────────────   ───────────────────   ─────────────────────   ──────────────────
  (1) Dashboard CBTD    (2a) Danh sách CBTD      (3a) Giao chỉ tiêu KHTD    (4a) Hợp đồng đến hạn   (5a) Chấm điểm & Xếp hạng (6a) Quản lý mapping ĐGD
    · Công việc hôm nay  (2b) Thêm / Sửa / Xóa    (3b) KHTD theo CBTD        (4b) Kiểm soát NQH      (5b) Báo cáo tổng hợp   (6b) Mapping Tổ TK&VV
    · Đèn giao dịch KPI  (2c) Bản đồ ĐGD→CBTD    (3c) Theo dõi TH / CT     (4c) Đôn đốc Giải ngân  (5c) Soạn thảo nội dung   (6c) Xuất mẫu biểu 10 loại
    · Top 3 việc ưu tiên (2d) Chi tiết hồ sơ CBTD(3d) Ước tính Lãi tháng N  (4d) Danh sách KH mới   (5d) Xuất PDF báo cáo    (6d) Form tìm kiếm nâng cao
    · Phân công hôm nay  (2e) Phân công ĐGD/Tổ                                              (4e) Hoạt động 3 tháng KHD (5e) BXH xếp hạng CBTD
                           (2f) Gán quyền CBTD                                              (4f) Phiếu đến hạn trả nợ
                           (2g) Xuất PDF hồ sơ NL                                             (4g) Export Excel NQH
```

### 2.1 Mô tả chi tiết từng Level-2 Tab mới (6 nhóm)

| Nhóm | Tab Level-2 | Nội dung nghiệp vụ | Ưu tiên | Dùng code cũ / viết mới |
|---|---|---|---|---|
| **1** | **📊 Trang chủ cá nhân CBTD** | (a) 5 KPI card công việc hôm nay (Hôm nay / Đến hạn / NQH / Chưa GN / KPI tháng) · (b) Đèn giao dịch 5 KPI chính theo tháng (Dư nợ / Giải ngân / KH mới / NQH / Tổ mới) · (c) Top 3 việc ưu tiên theo ngày (gọi tên HĐ cụ thể) · (d) Phân công ĐGD/Tổ hôm nay CBTD đi làm thực tế (từ lịch tuần CBTD nhập vào app). | 🟥 **Ưu tiên CAO NHẤT** (user mở tab đầu tiên thấy ngay công việc) | Viết mới 90% (reuse `tom_tat_kpi()` từ service cũ + filter theo tháng / theo CBTD user đang login). |
| **2** | **👥 Quản lý hồ sơ CBTD** | Gom 3 sub-tab cũ (Danh sách / Bản đồ / Chi tiết) vào đây + thêm 4 mục quản lý mới: **(2e) Phân công ĐGD & Tổ TK&VV theo CBTD** (drag & drop ĐGD/Tổ cho từng CBTD, persist vào `cbtd_data` kv_store) · **(2f) Gán quyền CBTD** (role CBTD Hội sở / CBTD PGD / Trưởng đội CBTD) · **(2g) Xuất PDF hồ sơ năng lực** (reuse 100% PDF generator cũ) · Menu click 1 CBTD → dropdown 8 chức năng (không phải qua sub-tab nữa). | 🟥 **Ưu tiên CAO** | Reuse ~65% code CRUD cũ + viết mới (2e) Mapping Tổ→CBTD 35% (từ `lay_to_theo_cbtd` service). |
| **3** | **📋 KHTD & Giao chỉ tiêu (theo từng CBTD)** | (3a) Giao KHTD theo CBTD (thực tế VBSP giao KHTD xuống đội CBTD, rồi đội chia lại cho từng CBTD theo địa bàn phụ trách) · (3b) Bảng KHTD THÁNG N / THÁNG N-1 / TỔNG 6 THÁNG ĐẦU NĂM theo từng CBTD · (3c) Theo dõi thực hiện / chỉ tiêu từng CBTD theo tuần · (3d) Ước tính lãi thực thu tháng N nếu đạt 100% chỉ tiêu. | 🟧 **Ưu tiên CAO** (liên quan nghiệp vụ KHTD đang làm) | Viết mới 80% (reuse `giao_khtd_service.py` hiện có ở nhóm KHTD, thêm filter theo `ma_cb`). |
| **4** | **💰 Tác nghiệp & Đôn đốc (hàng ngày)** | (4a) Hợp đồng đến hạn trả nợ tháng N theo CBTD (click 1 CBTD → danh sách tất cả HĐ đến hạn + tổng tiền) · (4b) Kiểm soát NQH 30/60/90 ngày theo địa bàn phụ trách CBTD · (4c) Đôn đốc giải ngân hạn mức chưa dùng · (4d) Danh sách khách hàng mới cần duyệt hồ sơ vay · (4e) Reuse `tab_don_doc_khd.py` (lọc theo từng CBTD, không toàn PGD) · (4f) Phiếu đến hạn trả nợ Word (fill template theo từng hợp đồng) · (4g) Export Excel NQH gửi Giám đốc PGD. | 🟧 **Ưu tiên CAO** (công việc hàng ngày CBTD) | Viết mới 70% (reuse drawer hợp đồng từ `loan_drawer` · reuse `auto_fill_document` để fill phiếu đến hạn · reuse tab_don_doc_khd logic + filter theo `ma_cb`). |
| **5** | **📈 Xếp hạng & Báo cáo (cuối tháng)** | (5a) Chấm điểm CBTD tháng (reuse scorecard logic từ `services/cbtd_dia_ban_service.py` BUGMAP C49 đã fix max = 100, thêm chỉ số tháng này) · (5b) Bảng xếp hạng toàn chi nhánh (BXH 10 CBTD xuất sắc nhất tháng) · (5c) Soạn thảo nội dung giao ban ngày 01 tháng sau (template tự tạo từ KPI tháng) · (5d) Xuất báo cáo Word/PDF kết quả thi công tháng (12 mẫu biểu) · (5e) Download BXH + điểm để gửi email đội CBTD. | 🟨 **Ưu tiên TRUNG BÌNH** (chỉ dùng cuối tháng 21-31) | Viết mới 75% (reuse PDF service cũ · reuse scorecard logic score CBTD cũ từ BUGMAP C49). |
| **6** | **🛠️ Công cụ bổ trợ** | (6a) Quản lý ĐGD mapping (dịch từ tab_quan_ly_dgd?không — tab riêng vẫn giữ, đây là sub-view theo CBTD) · (6b) Mapping Tổ TK&VV → CBTD phụ trách (import Excel file CDTO đã có cột "CBTD phụ trách" hoặc auto-infer từ ĐGD mapping) · (6c) Xuất 10 mẫu biểu hành chính (Mẫu 01 đến Mẫu 10 VBSP) fill data CBTD → tải về Word/PDF · (6d) Form tìm kiếm nâng cao: Tìm HĐ theo KH / theo xã / theo ngày hết hạn / theo NQH / theo mức lãi / theo chương trình vay. | 🟩 **Ưu tiên THẤP** (sau khi 5 nhóm trên ổn định mới làm tiếp) | Viết mới 85% (reuse `template_service.py` fill Word mẫu biểu · reuse `filter_bar` component). |

---

## 3. Files and Modules (scope thay đổi)

| File | Loại thay đổi | Mô tả chi tiết |
|---|---|---|
| `tabs/tab_cbtd.py` | **REWRITE 60% dòng (~900 dòng hiện tại → ~1,800 dòng sau rewrite)** | Thêm wrapper `render()` đầu tiên hiển thị Dashboard CBTD (nhóm 1) + 6 `lazy_tabs` level-2 theo 6 nhóm nghiệp vụ ở mục 2.1. 3 sub-tab cũ CRUD / Bản đồ / Chi tiết → di chuyển vào Nhóm 2 "👥 Quản lý hồ sơ CBTD". Không xóa code helper PDF / CRUD cũ — chỉ dịch vị trí. |
| `services/cbtd_dia_ban_service.py` | **UPDATE 30%** (~dòng 1-150 hiện tại thêm 3 helper mới) | Thêm 3 hàm mới: `lay_kpi_cbtd_theo_thang(ma_cb, yyyy, mm)` → trả về dict KPI tháng (Dư nợ GN+Lãi+NQH+KH mới+Tổ mới) dùng cho Dashboard nhóm 1 · `top_3_viec_uu_tien(ma_cb, today)` → Top 3 việc hôm nay theo ngày đến hạn trả nợ + NQH + Chưa giải ngân · `cham_diem_cbtd_thang(ma_cb, yyyy, mm)` → scorecard tháng (max 100đ, fix theo C49). Các hàm `lay_to_theo_cbtd()` cũ giữ nguyên. |
| `data/khtd.py` | **UPDATE 10%** (thêm helper nhỏ line 155-177) | Thêm helper `gan_to_tk_vv_cho_cbtd(pgd=None)` → đọc `dgd_map` + `cbtd_data["ds_dgd"]` → suy ra danh sách Tổ TK&VV thuộc ĐGD phụ trách → tạo mapping `(ten_pgd, ten_xa, ten_to)` → `ma_cb` để groupby CDTOTKVV theo CBTD (đáp ứng yêu cầu cuối user 03/09 "thống kê tuổi Tổ trưởng theo CBTD"). Save vào `kv_store` key `to_cbtd_map`. |
| `workspaces/ws_management.py` | **UPDATE 5 dòng line 69-85** | Không đổi vị trí 4 sub-tab CBTD&Địa bàn (Dashboard · CBTD · ĐGD · Tổ TK&VV). Chỉ đổi label của lambda thứ 2 `_get_tab("tab_cbtd").render` → truyền thêm kw `role_cn = True` để tab_cbtd biết đang ở mode CN (hiển thị thêm các mục Giao chỉ tiêu KHTD toàn CN / BXH toàn chi nhánh / mapping ĐGD toàn CN). Nếu role=CBTD user PGD → hide các mục CN-only. |
| `config.py` | **UPDATE <1%** (thêm 1 constant COT_* nếu cần) | Thêm constant `COT_MA_CB = "Mã CBTD"` · `COT_TEN_CB = "Tên CBTD"` nếu 2 constant này chưa có (Check trước trong COT_REF.md trước khi thêm — tránh trùng lặp). Dùng cho groupby theo CBTD trong báo cáo. |
| `db.py` | **KHÔNG SỬA** | Schema kv_store hiện tại đã có `doc_dgd_map()` + `doc_kv("cbtd_data")` OK. Không cần thêm bảng mới / migration. |

---

## 4. Implementation Steps (thực thi sau khi user duyệt plan — 6 bước, tuần tự)

```
Step 1 (Tạo khung UI 6 nhóm, không thay đổi logic CRUD cũ)
  → tabs/tab_cbtd.py: Thêm 6 lazy_tabs() level-2 đầu hàm render().
  → Di chuyển 3 sub-tab cũ (Danh sách / Bản đồ / Chi tiết) vào Nhóm 2 "👥 Quản lý hồ sơ CBTD".
  → Kiểm tra: các widget key thêm "lv2_nhomX_" prefix unique (tránh DuplicateElementKey).
  → Compile pass. Preview 18502 load được 6 tab mới, CRUD CBTD cũ vẫn hoạt động giống hệt.
  → Expected: Khung UI xong, chức năng cũ 100% hoạt động. Rollback nếu lỗi key widget.

Step 2 (Nhóm 1 — Trang chủ cá nhân CBTD: Dashboard + 5 KPI card + Đèn giao dịch tháng)
  → services/cbtd_dia_ban_service.py: Thêm 2 helper mới `lay_kpi_cbtd_theo_thang()` + `top_3_viec_uu_tien()`.
  → tab_cbtd.py: Render Nhóm 1 đầu tiên (sau title). 5 KPI card dùng kpi_row(num_columns=5).
  → Đèn giao dịch: 5 chỉ tiêu = 5 delta_card màu (xanh/vàng/đỏ theo ngưỡng: ≥85 xanh, 70-85 vàng, <70 đỏ).
  → Kiểm tra: Role CN → show toàn chi nhánh, role user_pgd (CBTD địa bàn) → filter theo ma_cb của user, PGD theo user.
  → Runtime test với 1 CBTD mẫu → số liệu khớp với HSTD parquet groupby ma_cb.

Step 3 (Nhóm 2 — Thêm mục (2e) Phân công ĐGD & Tổ TK&VV theo CBTD)
  → data/khtd.py: Helper `gan_to_tk_vv_cho_cbtd()` infer Tổ → CBTD từ ĐGD mapping.
  → tab_cbtd.py: UI (2e) 2 cột: bên trái List CBTD · bên phải Multiselect chọn ĐGD + listbox hiển thị danh sách Tổ TK&VV tương ứng.
  → Persist vào cbtd_data["ds_to_phu_trach"] trong kv_store. Có audit `db.ghi_audit()` sau khi lưu.
  → St.cache_data.clear() sau persist.
  → Kiểm tra: Click 1 CBTD → Xem Chi tiết → Danh sách Tổ TK&VV (section 4 cũ) hiện đúng những tổ user vừa chọn (không còn infer từ ĐGD nếu user override bằng tay).

Step 4 (Nhóm 3 — KHTD & Giao chỉ tiêu theo từng CBTD)
  → Dùng reuse service `khtd_service.py` (đã có giao KHTD theo PGD). Thêm layer filter "chia KHTD PGD xuống từng CBTD theo tỷ lệ Địa bàn phụ trách (% số Tổ TK&VV)".
  → tab_cbtd.py: (3b) Bảng KHTD THÁNG N vs N-1 st.dataframe + 2 selectbox (ma_cb / tháng).
  → (3c) Đèn giao dịch TH/CT giống nhóm 1 nhưng drill-down theo CBTD.
  → Kiểm tra: Tổng KHTD của tất cả CBTD trong cùng PGD = KHTD của PGD đó (không lệch tỷ lệ %).

Step 5 (Nhóm 4 — Tác nghiệp & Đôn đốc hàng ngày: Đến hạn / NQH / Giải ngân / KH mới)
  → tab_cbtd.py + reuse tab_don_doc_khd.py logic + filter theo ma_cb của user login (không theo toàn PGD).
  → (4f) Fill phiếu đến hạn trả nợ dùng `auto_fill_document(template_path=...)` từ utils.py.
  → Export Excel NQH (4g) dùng `xuat_excel({"Sheet1": df_nqh})` từ utils.
  → Kiểm tra: Login với role CBTD PGD Long Thành → chỉ thấy HĐ địa bàn phụ trách, không thấy HĐ của PGD Biên Hòa (filter đúng scope).

Step 6 (Nhóm 5 + 6 — Xếp hạng & Báo cáo cuối tháng + Công cụ bổ trợ)
  → BXH xếp hạng CBTD (5a/5e): Tính điểm 100đ max (fix BUGMAP C49) → sort desc → st.dataframe + medals🥇🥈🥉 top 3.
  → Xuất mẫu biểu 10 loại (6c): Mapping 10 loại mẫu VBSP → dict tag_map fill Word.
  → (6d) Tìm kiếm nâng cao: filter_bar() component với 8 loại điều kiện lọc (PGD/Xã/CT/ĐVUT/Lãi/Dư nợ/NQH/CBTD).
  → Sửa cuối: Compile toàn bộ 5 files (tab_cbtd.py + service + khtd.py + ws_management + config) PASS.
  → Runtime E2E smoke test 6 nhóm trên preview 18502. 6 group đều load, không trang trắng, không exception.
```

---

## 5. Dependencies and Considerations

| # | Yếu tố | Xử lý |
|---|---|---|
| **1** | **Backward compatibility với CBTD data cũ (kv_store `cbtd_data`)** | Không đổi schema cũ (key `cbtd_data` cấu trúc `{ma_cb: {ho_ten, pgd, ds_dgd, sdt, ghi_chu, ngay_cap, chuc_vu, ngay_bo_nhiem}}`). Các field mới `ds_to_phu_trach`, `nhom_cbtd` (đội 1/2/3) → append vào dict cũ khi user click save lần đầu, với default `[]` nếu chưa có. Không cần migration 1 lượt toàn bộ. |
| **2** | **Widget Key unique (Rule 6.6)** | Khung 6 tab mới tạo nhiều widget → thêm 2 prefix mới: `cbtd_nhom{N}_{ma_cb}_widget_*` với N=1→6. Không dùng index loop trong list CBTD để tạo key (dùng `ma_cb` là slug unique). |
| **3** | **Scope role (CN vs PGD vs CBTD địa bàn)** | Mỗi group thêm guard `if la_phan_he_cn(role): _render_cn(...) else if la_phan_he_pgd(role): _render_pgd(...)` theo Rule 6.5 normalize_role. Các mục "BXH toàn chi nhánh", "Giao chỉ tiêu toàn CN" → **CHỈ role CN mới thấy được** (executive có thể xem, manager/admin_cn edit được, CBTD PGD chỉ xem kết quả của mình). |
| **4** | **Không thêm dependency mới (Rule 6.11)** | Toàn bộ chức năng dùng thư viện đã có: streamlit, pandas, openpyxl, pyarrow, python-docx, duckdb. Không dùng pandas-ta / plotly / seaborn / dask. Chart dùng st.bar_chart builtin của Streamlit (native) — đủ cho 5 KPI monthly dashboard. |
| **5** | **Audit log sau mọi thao tác ghi dữ liệu (Rule 6.2)** | Step 3 (Lưu mapping Tổ→CBTD), Step 4 (Lưu chia KHTD cho từng CBTD), Step 5 (Lưu điểm xếp hạng tháng) → **ngay sau khi gọi `db.ghi_kv()` phải gọi `db.ghi_audit(username, "ACTION_NAME", "mô tả chi tiết")`. |
| **6** | **Date input Rule 6.15** | Mọi `st.date_input` trong Step 3 (Ngày bắt đầu phụ trách) · Step 5 (Ngày chấm điểm tháng) → bắt buộc `format="DD/MM/YYYY"`. |

---

## 6. Validation (sau mỗi step, kiểm tra ngay)

| Step | Kiểm tra cụ thể | Expected PASS |
|---|---|---|
| **Step 1** Khung UI 6 nhóm | Preview 18502 → Click vào 👔 Cán bộ tín dụng → thấy 6 tab level-2 mới (Trang chủ / Hồ sơ / KHTD / Tác nghiệp / Xếp hạng / Công cụ). Click qua lại 6 tab → không trang trắng, không DuplicateElementKey. Sub-tab Quản lý hồ sơ CRUD CBTD cũ hoạt động giống hệt (thêm/sửa/xóa CBTD). | Không crash, CRUD cũ 100% OK. |
| **Step 2** Dashboard CBTD | Kiểm tra 1 CBTD mẫu (vd Võ Thị Thủy, PGD Long Khánh) → 5 KPI card Tổng HĐ Đến hạn 8 + NQH 2 + Số liệu khớp với groupby theo Tên CBTD trong HSTD parquet kỳ 07/2026. Đèn giao dịch Dư nợ 78% → màu xanh, NQH 11% → màu vàng. | Số liệu groupby Tên CBTD khớp 100% KPI card. |
| **Step 3** (2e) Phân công Tổ TK&VV | Chọn 1 CBTD → Chọn ĐGD Phú Hữu A → Listbox hiển thị 14 tổ thuộc ĐGD Phú Hữu A → Click lưu → Reload lại → xem section 4 chi tiết CBTD → có 14 tổ đúng. | db.doc_kv("cbtd_data")["ds_to_phu_trach"] có dữ liệu, ghi_audit có entry. |
| **Step 4** KHTD theo CBTD | Giao chỉ tiêu PGD Long Khánh 50 tỷ → chia cho 5 CBTD trong PGD theo % số Tổ (CBTD Thủy phụ trách 21% tổ → nhận 10.5 tỷ chỉ tiêu) → TỔNG 5 CBTD = 50 tỷ đúng KHTD PGD. | Tổng KHTD per PGD không lệch. |
| **Step 5** Tác nghiệp hàng ngày | Login user_pgd=CBTD1_BH → list HĐ Đến hạn tháng chỉ có ~15 HĐ thuộc địa bàn phụ trách của user này (không thấy 370,282 hồ sơ toàn chi nhánh). Filter scope đúng. | Scope PGD đúng 100% không lộ dữ liệu PGD khác. |
| **Step 6** BXH & Xuất mẫu biểu | Chấm điểm 25 CBTD toàn CN → BXH top 3 có huy hiệu vàng/bạc/đồng → xuất file Word mẫu 01 thành công, tag_map fill không bị thiếu field nào. | PDF/Word không lỗi font (đã dùng TNR 13pt theo rule từ task trước). |

---

## 7. Risks and Handling

| Rủi ro | Cấp độ | Hậu quả nếu xảy ra | Xử lý dự phòng |
|---|---|---|---|
| **R1** | 🔴 CAO | **Scope dữ liệu lộ giữa các CBTD PGD (CBTD này thấy hợp đồng của PGD khác):** Sai filter scope theo role (Rule 6.5 normalize_role). | **Xử lý:** Bắt đầu mỗi hàm render group → **guard đầu hàm** `pgd_user = kwargs.get("pgd_user")`; nếu `pgd_user is not None` (role PGD/CBTD địa bàn) → **thêm `.query("PGD == @pgd_user")` vào df HSTD trước khi groupby**. Tất cả 4 helper service mới đều nhận **tham số bắt buộc `scope_pgd=None, scope_ma_cb=None`** để enforce scope không thể truyền sai. Viết 3 unit test pytest (scope_cn, scope_pgd, scope_cbtd) để regression trong `tests/test_cbtd_scope_filter.py`. |
| **R2** | 🟡 TRUNG BÌNH | **DuplicateElementKey widget (Rule 6.6) trong 6 tab mới:** 6 tab tạo nhiều widget key cùng tên. | Xử lý: Tất cả widget key bắt đầu bằng prefix `cbtd_lv2_N_{scope_slug}_` với N=1→6, scope_slug = `cn` hoặc `pgd_{slug_pgd}`. Không dùng `enumerate(i)` làm key, dùng `ma_cb` unique string. |
| **R3** | 🟡 TRUNG BÌNH | **Mapping Tổ TK&VV → CBTD (Step3) bị rơi tổ vào SAU (không có CBTD nào phụ trách):** ĐGD mapping thay đổi nhưng CBTD ds_dgd chưa cập nhật. | Xử lý: Thêm 1 st.warning trong (2e) hiển thị "⚠️ XX Tổ thuộc ĐGD chưa có CBTD phụ trách → vui lòng phân công" (giống warning trùng ĐGD hiện có ở sub-tab2 cũ). Cảnh báo rõ số lượng tổ bị thiếu → user không bỏ sót. |
| **R4** | 🟢 THẤP | **Scorecard chấm điểm tháng (6a) vượt ngưỡng 100 (BUGMAP C49 cũ):** Tổng điểm CBTD có thể lên 120. | Xử lý: Reuse fix đã có trong `services/cbtd_dia_ban_service.py` (BUGMAP C49) — baseline 30 điểm + 7 chỉ số max 100 tổng cộng → **clamp cuối 0 → 100** bằng `max(0, min(100, total_score))`. Unit test CBTD lý tưởng luôn =100. |
| **R5** | 🟢 THẤP | **Thời gian load Step4/5 nặng** (groupby HSTD 370k hồ sơ theo ma_cb nhiều lần). | Xử lý: Dùng `@st.cache_data(ttl=600)` cho `lay_kpi_cbtd_theo_thang()` và helper báo cáo cuối tháng (dữ liệu tháng cuối không đổi). Dùng duckdb thay vì pandas groupby cho HSTD 370k (Rule 6.16 check schema parquet trước khi query). |
