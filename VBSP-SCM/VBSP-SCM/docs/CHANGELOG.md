# CHANGELOG — VBSP-SCM

---

## [05/2026] — Sprint hiện tại

### Thêm mới
- `khtd_service.py` + `tab_khtd_giao_dc.py` — module Giao & Điều chỉnh KHTD thay thế dcgiam_service + tab_dcgiam
- `tab_nq11.py` — tab NQ11 vào Báo cáo chi tiết
- 4 chương trình mới: mã 10/15/21/25 TW+DP vào `config.py`
- File GSheet V3 + script `gen_dcgiam_sheet.py`
- Apps Script phân quyền GSheet
- Hàm `_tinh_th_theo_xa()` — tính Thực hiện theo từng xã từ HSTD
- Banner trạng thái KH (🔴/🟡/🟢) ngay trên form nhập KHTD Chi nhánh

### Sửa đổi
- `ws_management.py`: ẩn tab GQVL, đổi tên tab (🗓️ KH Tín dụng Năm, 📤 Giao KH theo Đợt, ✅ Nhiệm vụ)
- `config.py`: thêm 4 key ĐP còn thiếu (9_DP, 12_DP, 17_DP, 26_DP)
- `tab_khtd.py`: nâng cấp form nhập CN Phần A–E (12 cột TW/ĐP/Tổng, header 2 dòng màu, bảng tóm tắt HTML thuần)
- `tab_khtd.py`: bỏ expander form nhập, hiện thẳng
- `tab_khtd.py`: KHTD theo Xã — thêm cột TH TW / TH ĐP theo từng xã
- `tab_khtd.py`: number_input đổi format `%.1f` → `%.0f` (số nguyên)
- `pdf_service.py`: thêm logo, fix độ rộng cột, tăng font size
- `ARCHITECTURE.md`: cập nhật ws tabs, 4 key DP, quy tắc /1e12
- `CONVENTIONS.md`: thêm mục 15 UI Guidelines, fix quy tắc /1e12
- `HUONG_DAN_NGUON_DU_LIEU.md`: viết lại từ đầu (file cũ rỗng)

### Sửa lỗi
- **Bug nghiêm trọng:** metric "Tổng KH/TH" chia `/1e9` thay vì `/1e12` → hiện 0,013 tỷ thay vì 13,199 tỷ
- Cột Thực hiện hiển thị số thập phân thừa (`207.172,4` → `207.172`)
- `th_cn` keys bị lệch ~8 tỷ vì thiếu 4 key ĐP trong config

---

## [04/2026]

### Thêm mới
- Báo cáo gia hạn vượt quy định
- `tab_kiem_soat.py` — kiểm soát Chi nhánh
- GSheet DCGIAM_SHEET_ID

### Sửa đổi
- Sáp nhập Chi nhánh Bình Phước vào Đồng Nai — cập nhật DS_PGD (21 PGD + Hội sở)
- Cập nhật PGD_XA_MAP với 95 xã/phường

---

## [03/2026]

### Thêm mới
- `khtd_service.py` — service tập trung logic KHTD
- `tab_khtd_giao_dc.py` — giao và điều chỉnh KHTD theo đợt
- Upload Excel kế hoạch hàng loạt cho tab KHTD theo Xã

### Sửa lỗi
- Lỗi merge 22 PGD khi file một PGD bị lỗi format
