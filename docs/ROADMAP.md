# ROADMAP — VBSP-SCM
> Cập nhật lần cuối: 12/05/2026

---

## Sprint đã hoàn thành ✅

| # | Việc | File | Trạng thái |
|---|---|---|---|
| 1 | Apply prompt nâng cấp tab_khtd.py Phần A–E | `tab_khtd.py` | ✅ Xong |
| 2 | Cập nhật gen_dcgiam_sheet.py (GQVL phân tầng + push_kh_len_sheet) | `gen_dcgiam_sheet.py` | ✅ Xong |
| 3 | ARCHITECTURE.md cập nhật module mới | `ARCHITECTURE.md` | ✅ Xong |
| 4 | Fix bug metric /1e9 → /1e12 | `tab_khtd.py` | ✅ Xong |
| 5 | Bỏ expander form nhập KHTD CN | `tab_khtd.py` | ✅ Xong |
| 6 | KHTD theo Xã thêm cột TH TW/ĐP | `tab_khtd.py` | ✅ Xong |
| 7 | PDF: thêm logo, fix cột, font size | `pdf_service.py` | ✅ Xong |
| 8 | Cập nhật 3 file .md root | `.md files` | ✅ Xong |
| 9 | Hệ thống phân hệ 2 cấp (CN + PGD) | `auth.py`, `config.py`, `ws_*.py` | ✅ Xong |
| 10 | Role mới: admin_pgd, manager_pgd, user_pgd | `auth.py`, `config.py` | ✅ Xong |
| 11 | Tab Ủy thác với 5 sub-tab | `tab_uy_thac.py` | ✅ Xong |
| 12 | Template service dùng docxtpl | `template_service.py` | ✅ Xong |
| 13 | Fix ws_operation Tab Tổng quan lọc PGD | `ws_operation.py` | ✅ Xong |
| 14 | Nhất quán hóa DON_VI_CHI_NHANH | `config.py` | ✅ Xong |
| 15 | Tab Upload HSTD cho admin_pgd | `ws_operation.py` | ✅ Xong |
| 16 | Cập nhật toàn bộ file .md | `docs/*.md` | ✅ Xong |
| 17 | GQVL 4 nhóm: tích hợp vào Giao & ĐC KHTD | `config.py`, `khtd_service.py`, `tab_khtd_giao_dc.py`, `tab_khtd.py` | ✅ Xong |
| 18 | Dashboard Cảnh báo tiến độ KH vs TH | `tab_khtd_xuat.py` | ✅ Xong |
| 19 | Menu sidebar 2 cấp trong ws_management | `app.py`, `ws_management.py` | ✅ Xong |
| 20 | Dashboard tổng hợp XLRR (QĐ62 + Nợ RR) | `tab_xlrr_tong_hop.py` | ✅ Xong |
| 21 | Checklist báo cáo định kỳ | `tab_checklist_bc.py` | ✅ Xong |
| 22 | Chuẩn hóa tab context (tab=None) | `tabs/*.py`, `utils.py` | ✅ Xong |
| B1 | gen_dcgiam_sheet.py: GQVL phân tầng | `gen_dcgiam_sheet.py` | ✅ Xong |
| B3 | Chữ ký cuối PDF báo cáo | `pdf_service.py` | ✅ Xong (đã có phần chữ ký) |
| B4 | Dòng tổng cộng cuối bảng PDF | `pdf_service.py`, `tab_khtd_xuat.py` | ✅ Xong (`them_dong_tong=True`) |
| B5 | Mẫu 06TD — Phiếu kiểm tra sử dụng vốn | `tab_uy_thac.py` | ✅ Xong (xuất Word/PDF) |
| B6 | Cảnh báo 3 tháng không hoạt động (UI) | `data/hstd.py`, `ws_operation.py` | ✅ Xong (`danh_dau_khong_hd`) |
| M1 | Tab KHTD PGD: bảng KH vs TH + metric TH PGD | `tab_khtd_pgd.py` | ✅ Xong |

---

## Q2/2026 — Backlog ưu tiên cao (CÒN LẠI)

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| **B2** | **Bảng tóm tắt KHTD CN → HTML thuần** | `tab_khtd.py` | Mockup có sẵn, chưa implement `unsafe_allow_html` |
| **B7** | **Fix check role cứng → dùng `la_phan_he_*()`** | `tabs/*.py` | Refactor hàng loạt, chưa hoàn tất |

---

## Q3/2026 — Backlog trung bình (CÒN LẠI)

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| **M2** | **Export Excel KHTD theo Xã đầy đủ** | `tab_khtd.py` | Chưa có flow xuất Excel theo Xã |
| **M3** | **Dashboard executive: KPI mới** | `ws_executive.py` | Chờ KHTD CN ổn định |
| **M4** | **Tìm kiếm toàn văn tab Tra cứu** | `tab_tracuu.py` | Hiện vẫn là filter cơ bản |
| **M5** | **Xếp loại HĐT tổng hợp** | `tab_xep_loai_hdt.py` *(mới)* | Chưa có file |
| **M6** | **Báo cáo tổng hợp gửi HĐT cấp tỉnh** | `report_service.py` | Chưa có mẫu chuẩn tỉnh |
| **M7** | **Tích hợp HĐT điện tử** | `hdt_service.py` *(mới)* | Chờ API HĐT |

---

## Backlog chiến lược — Chưa bắt đầu

| # | Việc | File liên quan | Phụ thuộc | Ghi chú |
|---|---|---|---|---|
| **S1** | **HSTD Snapshot System** | `hstd.py`, `db.py` *(schema mới)* | — | Nền tảng cho S2 |
| **S2** | **Risk Heatmap ws_executive** | `ws_executive.py` | S1 | Biểu đồ rủi ro theo PGD |
| **S3** | **Automated Word/PDF reporting** | `report_service.py`, `pdf_service.py` | S1 + S2 | Báo cáo tự động từ snapshot |
| **S4** | **Dynamic NDT registry (`tab_ndt.py`)** | `tab_ndt.py` *(mới)*, `config.py` | — | Thay hằng số `MA_NDT_CAP_TINH_DUOI` cứng |
| **S5** | **Tiered GQVL pipeline** | `gen_dcgiam_sheet.py`, `khtd_service.py` | — | Cross-ref HSTDCT + GQVL qua số khế ước |
| **S6** | **Xác định mã NDT Bình Phước** | *(manual)* | S4 | Tra từ file GQVL thực tế sau khi có S4 |

---

## Không làm (đã xem xét và bỏ)

| Việc | Lý do |
|---|---|
| Chuyển sang React/Next.js | Quá tốn công, 20 users nội bộ không cần |
| streamlit-aggrid | Thêm dependency nặng, không cần thiết |
| Tab GQVL cho ws_management | Đã ẩn theo yêu cầu, giữ file |

---

## Ghi chú kỹ thuật còn mở

- GSheet ID: `DCGIAM_SHEET_ID = 15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk`
- 4 key ĐP đã thêm vào config: `9_DP`, `12_DP`, `17_DP`, `26_DP`
- Đơn vị tiền tệ: `×1e6` (triệu → VND) — **KHÔNG dùng `×1e9`**
- Tab context chuẩn: `_tab_ctx = tab if tab is not None else _st.container()`
