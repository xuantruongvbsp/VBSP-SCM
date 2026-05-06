# ROADMAP — VBSP-SCM
> Cập nhật lần cuối: 05/2026

---

## Đang làm (Sprint hiện tại)

| # | Việc | File | Trạng thái |
|---|---|---|---|
| 1 | Apply prompt nâng cấp tab_khtd.py Phần A–E | `tab_khtd.py` | ✅ Xong |
| 2 | Cập nhật gen_dcgiam_sheet.py (GQVL phân tầng + push_kh_len_sheet) | `gen_dcgiam_sheet.py` | 🔄 Chưa làm |
| 3 | ARCHITECTURE.md cập nhật module mới | `ARCHITECTURE.md` | ✅ Xong |
| 4 | Fix bug metric /1e9 → /1e12 | `tab_khtd.py` | ✅ Xong |
| 5 | Bỏ expander form nhập KHTD CN | `tab_khtd.py` | ✅ Xong |
| 6 | KHTD theo Xã thêm cột TH TW/ĐP | `tab_khtd.py` | ✅ Xong |
| 7 | PDF: thêm logo, fix cột, font size | `pdf_service.py` | ✅ Xong |
| 8 | Cập nhật 3 file .md root | `.md files` | ✅ Xong |

---

## Backlog — Ưu tiên cao

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| B1 | gen_dcgiam_sheet.py: GQVL phân tầng | `gen_dcgiam_sheet.py` | Cần làm ngay |
| B2 | Bảng tóm tắt KHTD CN → HTML thuần | `tab_khtd.py` | Mockup đã có |
| B3 | Thêm chữ ký cuối PDF báo cáo | `pdf_service.py` | Chuẩn ngân hàng |
| B4 | Dòng tổng cộng cuối bảng PDF | `tab_khtd.py` | Thiếu trong PDF hiện tại |

---

## Backlog — Ưu tiên trung bình

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| M1 | Tab KHTD PGD: thêm cột TH theo PGD | `tab_khtd_pgd.py` | Tương tự KHTD CN |
| M2 | Export Excel KHTD theo Xã đầy đủ | `tab_khtd.py` | Hiện chỉ có PDF |
| M3 | Dashboard executive: cập nhật KPI mới | `ws_executive.py` | Sau khi KHTD CN ổn định |
| M4 | Tìm kiếm toàn văn trong tab Tra cứu | `tab_tracuu.py` | UX cải thiện |

---

## Không làm (đã xem xét và bỏ)

| Việc | Lý do |
|---|---|
| Chuyển sang React/Next.js | Quá tốn công, 20 users nội bộ không cần |
| streamlit-aggrid | Thêm dependency nặng, không cần thiết |
| Tab GQVL cho ws_management | Đã ẩn theo yêu cầu, giữ file |

---

## Ghi chú kỹ thuật còn mở

- `gen_dcgiam_sheet.py`: cần cập nhật `push_kh_len_sheet()` và GQVL phân tầng
- GSheet ID: `DCGIAM_SHEET_ID = 15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk`
- 4 key ĐP chưa có trong config gốc: `9_DP`, `12_DP`, `17_DP`, `26_DP` — đã thêm
