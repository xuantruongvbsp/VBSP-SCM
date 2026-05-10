# ROADMAP — VBSP-SCM
> Cập nhật lần cuối: 06/05/2026

---

## Đang làm (Sprint hiện tại)

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
| 9 | **Hệ thống phân hệ 2 cấp (CN + PGD)** | `auth.py`, `config.py`, `ws_*.py` | ✅ Xong |
| 10 | **Role mới:** admin_pgd, manager_pgd, user_pgd | `auth.py`, `config.py` | ✅ Xong |
| 11 | **Tab Ủy thác với 5 sub-tab** | `tab_uy_thac.py` | ✅ Xong |
| 12 | **Template service dùng docxtpl** | `template_service.py` | ✅ Xong |
| 13 | **Fix ws_operation Tab Tổng quan lọc PGD** | `ws_operation.py` | ✅ Xong |
| 14 | **Nhất quán hóa DON_VI_CHI_NHANH** | `config.py` | ✅ Xong |
| 15 | **Tab Upload HSTD cho admin_pgd** | `ws_operation.py` | ✅ Xong |
| 16 | **Cập nhật toàn bộ file .md** | `docs/*.md` | ✅ Xong |
| **17** | **GQVL 4 nhóm: tích hợp vào Giao & ĐC KHTD** | `config.py`, `khtd_service.py`, `tab_khtd_giao_dc.py`, `tab_khtd.py` | ✅ Xong |
| **18** | **Dashboard Cảnh báo tiến độ KH vs TH** | `tab_khtd_xuat.py` | ✅ Xong |

---

## Q2/2026 — Backlog ưu tiên cao

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| B1 | ✅ gen_dcgiam_sheet.py: GQVL phân tầng | `gen_dcgiam_sheet.py` | ✅ Xong |
| B2 | Bảng tóm tắt KHTD CN → HTML thuần | `tab_khtd.py` | Mockup đã có |
| B3 | Thêm chữ ký cuối PDF báo cáo | `pdf_service.py` | Chuẩn ngân hàng |
| B4 | Dòng tổng cộng cuối bảng PDF | `tab_khtd.py` | Thiếu trong PDF hiện tại |
| **B5** | **Biên bản kiểm tra sử dụng vốn (tab Ủy thác)** | `tab_uy_thac.py` | Mẫu 06TD |
| **B6** | **Cảnh báo 3 tháng không hoạt động** | `data/hstd.py`, `ws_operation.py` | Tự động phát hiện |
| **B7** | **Fix check role cứng trong các tab** | `tabs/*.py` | Dùng `la_phan_he_*()` |
| **B8** | **Dashboard Cảnh báo tiến độ KH vs TH** | `tab_khtd_xuat.py` | ✅ Xong |

---

## Q3/2026 — Backlog trung bình

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| M1 | Tab KHTD PGD: thêm cột TH theo PGD | `tab_khtd_pgd.py` | Tương tự KHTD CN |
| M2 | Export Excel KHTD theo Xã đầy đủ | `tab_khtd.py` | Hiện chỉ có PDF |
| M3 | Dashboard executive: cập nhật KPI mới | `ws_executive.py` | Sau khi KHTD CN ổn định |
| M4 | Tìm kiếm toàn văn trong tab Tra cứu | `tab_tracuu.py` | UX cải thiện |
| **M5** | **Xếp loại HĐT tổng hợp** | `tabs/tab_xep_loai_hdt.py` | Theo tiêu chí NHCSXH |
| **M6** | **Báo cáo tổng hợp gửi HĐT cấp tỉnh** | `services/report_service.py` | Mẫu chuẩn tỉnh |
| **M7** | **Tích hợp HĐT điện tử** | `services/hdt_service.py` | Kết nối API HĐT |

---

## Không làm (đã xem xét và bỏ)

| Việc | Lý do |
|---|---|
| Chuyển sang React/Next.js | Quá tốn công, 20 users nội bộ không cần |
| streamlit-aggrid | Thêm dependency nặng, không cần thiết |
| Tab GQVL cho ws_management | Đã ẩn theo yêu cầu, giữ file |

---

## Ghi chú kỹ thuật còn mở

- GQVL 4 nhóm đã tích hợp vào toàn bộ luồng Giao & Điều chỉnh KHTD (B1 ✅)
- GSheet ID: `DCGIAM_SHEET_ID = 15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk`
- 4 key ĐP chưa có trong config gốc: `9_DP`, `12_DP`, `17_DP`, `26_DP` — đã thêm
