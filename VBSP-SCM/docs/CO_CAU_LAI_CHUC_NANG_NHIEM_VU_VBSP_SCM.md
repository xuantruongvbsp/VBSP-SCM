# CƠ CẤU LẠI CHỨC NĂNG VBSP-SCM
> Dựa trên Bản Mô tả Công việc 6 chức danh: Trưởng phòng, Phó TP (vị trí 1 & 2),
> CBTD Hội sở tỉnh, Tổ trưởng KHNV PGD, CBTD PGD

---

## I. PHÂN TÍCH: NHIỆM VỤ THỰC TẾ → CHỨC NĂNG HỆ THỐNG

### Nhóm nhiệm vụ từ Bản Mô tả Công việc

| Nhóm nhiệm vụ | Chức danh liên quan | Chức năng SCM hiện có | Thiếu/cần bổ sung |
|---|---|---|---|
| **Kế hoạch tín dụng** — Xây dựng, giao/điều chỉnh chỉ tiêu KH | TP, PTP1, PTP2, Tổ trưởng PGD | tab_khtd, tab_khtd_pgd, tab_khtd_giao_dc, tab_khtd_mau07 | ✅ Đủ cơ bản |
| **Điện báo / Nguồn vốn** — Điện báo xin vốn, quỹ ATCT | TP, PTP2, Tổ trưởng PGD | tab_candoi (Điện Báo) | ✅ Có, đang dùng |
| **Cho vay / Thu nợ / HSTD** — Hồ sơ, thẩm định, giải ngân | CBTD HS, CBTD PGD | tab_tracuu, tab_danhsach | ✅ HSTD đã có |
| **Quản lý Tổ TK&VV** — Xếp loại, củng cố, kiện toàn | TP, Tổ trưởng PGD, CBTD PGD | tab_cdtotkvv, tab_cdtotkvv_pgd | ✅ Có |
| **Giao dịch xã** — Lịch GD, ĐGD, tỷ lệ GDX | TP, PTP1, CBTD HS, Tổ trưởng PGD, CBTD PGD | tab_diem_gd_pgd, tab_quan_ly_dgd | ⚠️ Thiếu: tỷ lệ GD tại xã, kết quả sau phiên |
| **Giao ban** — Họp giao ban CT-XH cấp xã/huyện, Thông báo KL | CBTD HS, Tổ trưởng PGD, CBTD PGD | Đang tái cấu trúc → tab_giao_ban | 🔴 Thiếu hoàn toàn |
| **Ủy thác / Hội đoàn thể** — Theo dõi CT-XH, kiểm tra kế hoạch | TP, PTP1, CBTD HS, CBTD PGD | Chưa có tab riêng | 🔴 Thiếu |
| **Nợ rủi ro / Xử lý nợ** — HSTD rủi ro, NQ11, báo cáo xử lý | TP, PTP2, Tổ trưởng PGD | tab_nq11, tab_kiem_soat | ⚠️ NQ11 có, thiếu luồng xử lý hồ sơ |
| **GQVL** — Cho vay việc làm, thẩm định 7a/7b | PTP1, Tổ trưởng PGD | tab_gqvl | ✅ Có |
| **Báo cáo & Thống kê** — Tháng/quý/năm, sơ kết | TP, PTP2, Tổ trưởng PGD | tab_baocao, ws_executive | ⚠️ Thiếu báo cáo định kỳ tự động |
| **Nhiệm vụ & Chấm điểm** — Phiếu giao việc, chấm điểm NV | TP, Tổ trưởng PGD | tab_nhiem_vu | ✅ Có |
| **BĐD HĐQT** — Họp BĐD, báo cáo kiểm tra, tổng hợp số liệu | TP, PTP1, PTP2 | tab_ban_dai_dien | ⚠️ Mới tạo, còn placeholder |
| **Kiểm tra nội bộ** — Tự kiểm tra, kiểm tra chéo | TP, PTP1, CBTD HS | tab_kiem_soat | ⚠️ Có nhưng cần bổ sung |
| **Upload dữ liệu** — HSTD, NQ11, GQVL, CDTOTKVV | Tổ trưởng PGD | tab_upload_pgd, tab_upload_khnv | ✅ Có |

---

## II. THIẾT KẾ LẠI ws_management (Hội sở CN — Trưởng phòng + Phó TP)

**Nguyên tắc:** Nhóm theo 5 mảng công việc chính của TP/PTP.
Thay tab ngang → **sidebar navigation** (đã lên kế hoạch).

### Cấu trúc sidebar mới (5 nhóm)

```
ws_management — Phòng KH-NVTD
│
├── 📊 TỔNG QUAN & ĐIỀU HÀNH
│   ├── 📈 Tổng quan                 [tab_tongquan]           — TP xem hàng ngày
│   ├── 📡 Điện Báo / Nguồn vốn     [tab_candoi]             — PTP2 phụ trách
│   └── 🎯 KH vs Thực hiện          [tab_kehoach]            — TP theo dõi tiến độ
│
├── 🗓️ KẾ HOẠCH TÍN DỤNG
│   ├── 📋 KH tín dụng năm (CN)     [tab_khtd, mode=cn]      — TP/PTP1
│   ├── 📤 Giao KH theo đợt         [tab_khtd_giao_dc]       — TP giao chỉ tiêu
│   ├── 📄 Mẫu 07 (QĐ UBND)        [tab_khtd_mau07]         — PTP1
│   └── 📝 Nhập KH (khnv)           [tab_upload_khnv]        — PTP2/admin
│
├── 📂 NGHIỆP VỤ TÍN DỤNG
│   ├── 🔍 Tra cứu HSTD             [tab_tracuu]             — CBTD HS
│   ├── 📋 Danh sách KH             [tab_danhsach]           — CBTD HS
│   ├── 💼 GQVL (Cho vay việc làm)  [tab_gqvl]              — PTP1 kiểm soát
│   ├── 📜 NQ11                     [tab_nq11]               — PTP2 theo dõi
│   └── ⚠️ Kiểm soát CN             [tab_kiem_soat]          — TP/PTP
│
├── 🏘️ MẠNG LƯỚI & HOẠT ĐỘNG
│   ├── 📍 Điểm Giao dịch (ĐGD)    [tab_diem_gd_pgd / tab_quan_ly_dgd]
│   ├── 🏘️ Tổ TK&VV                [tab_cdtotkvv, mode=cn]
│   ├── 🚨 Cảnh báo sớm             [_render_canh_bao]
│   └── 📢 Giao ban                 [tab_giao_ban]           — 🆕 Q2/2026
│
└── 📋 QUẢN LÝ & BÁO CÁO
    ├── 📊 Báo cáo chi tiết          [tab_baocao]
    ├── ✅ Nhiệm vụ                  [tab_nhiem_vu]
    ├── 🏛️ Ban Đại Diện             [tab_ban_dai_dien, cap=tinh]
    ├── 👔 Quản lý CBTD             [tab_cbtd]
    ├── 📁 Quản lý Template         [_render_quan_ly_template] — admin/manager only
    └── 📤 Upload PGD               [tab_upload_pgd]          — admin only
```

### Ánh xạ chức danh → nhóm chức năng ưu tiên

| Chức danh | Nhóm dùng nhiều nhất | Nhóm thứ yếu |
|---|---|---|
| **Trưởng phòng** | Tổng quan & Điều hành, KH Tín dụng | Quản lý & Báo cáo |
| **Phó TP vị trí 1** (TP Thành phố) | Nghiệp vụ TD (GQVL, tra cứu), KH TD | Mạng lưới |
| **Phó TP vị trí 2** (Báo cáo/NV/Nguồn vốn) | Điện báo, Báo cáo, NQ11 | KH TD |

---

## III. THIẾT KẾ LẠI ws_operation (PGD — Tổ trưởng + CBTD)

**Nguyên tắc:** CBTD dùng hàng ngày → tab ngang, gom lại còn ~10 tab theo luồng công việc.

### Cấu trúc tab mới (10 tab, giảm từ 16)

```
ws_operation — Phòng Giao Dịch [slug PGD]
│
Tab 1: 📊 Tổng quan PGD          [tab_tongquan, lọc PGD]
Tab 2: 🔍 Tra cứu / HSTD         [tab_tracuu]
Tab 3: 🗓️ Kế hoạch TD            [tab_khtd_pgd + tab_kehoach gộp]
Tab 4: 💼 GQVL                   [tab_gqvl]
Tab 5: 📜 NQ11                   [tab_nq11]
Tab 6: 🏘️ Tổ TK&VV               [tab_cdtotkvv_pgd]
Tab 7: 📍 Điểm Giao Dịch         [tab_diem_gd_pgd + tab_quan_ly_dgd gộp]
Tab 8: 📢 Giao ban               [tab_giao_ban]             — 🆕 Q2/2026
Tab 9: ✅ Nhiệm vụ               [tab_nhiem_vu]
Tab 10: 📤 Upload                [tab_upload_pgd]
```

### Tab gộp cụ thể (giảm từ 16 → 10)

| Gộp | Từ | Vào | Lý do |
|---|---|---|---|
| `tab_khtd_pgd` + `tab_kehoach` | 2 tab | Tab 3 | Tổ trưởng cần xem KH và tiến độ cùng lúc |
| `tab_diem_gd_pgd` + `tab_quan_ly_dgd` | 2 tab | Tab 7 | ĐGD và quản lý ĐGD là cùng một luồng |
| `tab_cdtotkvv_pgd` | giữ nguyên | Tab 6 | Đủ độc lập |
| Xóa `tab_baocao` ở ws_operation | 1 tab | — | CBTD không dùng; báo cáo là của CN |
| Xóa `tab_candoi` ở ws_operation | 1 tab | — | Điện báo là việc của Tổ trưởng gửi lên CN, không cần tab riêng |
| Xóa `tab_tracuu` + `tab_danhsach` gộp | 2 tab | Tab 2 | Danh sách KH là một dạng tra cứu |

---

## IV. CHỨC NĂNG CẦN BỔ SUNG — ƯU TIÊN THEO BẢN MÔ TẢ CÔNG VIỆC

### 🔴 Thiếu nghiêm trọng (không có trong SCM, có trong mô tả CV)

#### 1. Tab Giao ban — `tab_giao_ban.py` (Q2/2026)
**Căn cứ CV:** CBTD HS mục 3d, CBTD PGD mục 3d: *"Chuẩn bị nội dung giao ban, tổng hợp kết quả giao ban theo định kỳ"*; PTP1 mục 5: *"Xây dựng dự thảo Thông báo kết luận phiên họp với tổ chức CT-XH"*

Nội dung cần có:
- Số liệu Hội đoàn thể (4 tổ chức CT-XH) theo từng xã
- Kết quả giao ban tháng (doanh số, NQH, Tổ TK&VV)
- Thông báo kết luận → xuất Word/PDF

#### 2. Theo dõi ủy thác CT-XH — chưa có tab
**Căn cứ CV:** TP mục 2c, CBTD HS mục 3, CBTD PGD mục 3: *"Theo dõi hợp đồng ủy thác, đánh giá tổ chức CT-XH cấp huyện/xã"*

Nội dung cần có:
- Theo dõi 4 tổ chức CT-XH (Hội Phụ nữ, Nông dân, CCB, Đoàn TN) theo PGD/xã
- Kết quả kiểm tra, đánh giá theo kỳ
- Danh sách nợ đến hạn theo Tổ TK&VV *(đã có trong roadmap Q2)*

#### 3. Mẫu 06/TD — Kiểm tra sử dụng vốn 30 ngày
**Căn cứ CV:** CBTD HS mục 7a, CBTD PGD mục 7a: *"Mẫu 06/TD kiểm tra sử dụng vốn trong vòng 30 ngày"*

Nội dung cần có:
- Danh sách món vay mới giải ngân cần kiểm tra (lọc theo ngày, PGD, xã)
- Tick hoàn thành kiểm tra
- Xuất mẫu 06/TD

### ⚠️ Có nhưng thiếu (chức năng mô tả nhưng SCM chưa đủ)

#### 4. Tỷ lệ Giao dịch tại xã
**Căn cứ CV:** TP mục 4: *"Tỷ lệ giao dịch tại xã (giải ngân, thu nợ, thu lãi)"*
→ Cần thêm chỉ tiêu % GD tại ĐGD vào tab_diem_gd_pgd / tab_tongquan
*(đã có trong Roadmap Q4)*

#### 5. Kế hoạch kiểm tra, giám sát hàng năm
**Căn cứ CV:** PTP1 mục 3, Tổ trưởng PGD mục 4: *"Kế hoạch kiểm tra nội bộ, kiểm tra chéo địa bàn"*
→ Cần thêm vào tab_kiem_soat: tạo/theo dõi kế hoạch kiểm tra

#### 6. Báo cáo chấm điểm nhiệm vụ định lượng
**Căn cứ CV:** TP mục 6: *"Chấm điểm nhiệm vụ (Phụ lục 07/ĐGXL)"*, Tổ trưởng PGD mục 4
→ Cần bổ sung vào tab_nhiem_vu: tổng hợp chấm điểm định lượng
*(đã có trong Roadmap Q3)*

---

## V. MA TRẬN: CHỨC DANH × TAB

> ✅ = Cần dùng thường xuyên | ⚠️ = Thỉnh thoảng | — = Không cần

| Tab / Chức năng | TP | PTP1 | PTP2 | CBTD HS | Tổ trưởng PGD | CBTD PGD |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Tổng quan | ✅ | ✅ | ✅ | — | ✅ | — |
| Điện báo / Nguồn vốn | ✅ | ⚠️ | ✅ | — | ✅ | — |
| KH Tín dụng (CN) | ✅ | ✅ | ⚠️ | — | — | — |
| KH Tín dụng (PGD) | — | — | — | — | ✅ | ⚠️ |
| Giao KH theo đợt | ✅ | ✅ | — | — | — | — |
| Tra cứu HSTD | ⚠️ | ✅ | — | ✅ | ✅ | ✅ |
| GQVL | ⚠️ | ✅ | — | ✅ | ✅ | ✅ |
| NQ11 | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| Tổ TK&VV | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ |
| Điểm Giao Dịch | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| Giao ban | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Báo cáo | ✅ | ⚠️ | ✅ | — | ⚠️ | — |
| Nhiệm vụ | ✅ | ⚠️ | ⚠️ | — | ✅ | ✅ |
| BĐD HĐQT | ✅ | ✅ | ✅ | — | — | — |
| Kiểm soát CN | ✅ | ✅ | ✅ | — | — | — |
| Upload PGD | — | — | — | — | ✅ | — |
| Quản lý CBTD | ✅ | ⚠️ | — | — | — | — |

---

## VI. ROADMAP ĐỀ XUẤT (CẬP NHẬT THEO BẢN MÔ TẢ CÔNG VIỆC)

### Q2/2026 (đang làm)
- [ ] `tab_giao_ban.py` — Thông báo KL giao ban (fix 4 lỗi → gộp tab → thêm số liệu Hội đoàn thể)
- [ ] Danh sách nợ đến hạn theo Tổ TK&VV (ws_operation)
- [ ] Checklist Mẫu 06/TD kiểm tra vốn 30 ngày

### Q3/2026
- [ ] Xếp loại Tổ TK&VV hàng tháng (tự động từ upload)
- [ ] Chấm điểm nhiệm vụ định lượng (Phụ lục 07/ĐGXL)
- [ ] Số liệu họp BĐD tỉnh (tab_ban_dai_dien — điền nội dung thực)
- [ ] Tái cấu trúc ws_management → sidebar 5 nhóm

### Q4/2026
- [ ] Tỷ lệ GD tại xã (% giải ngân/thu nợ/thu lãi tại ĐGD)
- [ ] Nguồn vốn ủy thác địa phương
- [ ] Tab theo dõi ủy thác CT-XH (Hợp đồng ủy thác + đánh giá định kỳ)
- [ ] Kế hoạch kiểm tra nội bộ (bổ sung tab_kiem_soat)
