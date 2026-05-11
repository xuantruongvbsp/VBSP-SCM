# CHANGELOG

## [2026-05-12] — Thêm màu nền sidebar cho ws_management.py
- `workspaces/ws_management.py` dòng ~885 — Thêm CSS injection tô màu nền sidebar #F1EFE8 để dễ phân biệt với vùng nội dung

## [2026-05-12] — Thêm hàm fmt_bang_ty() và cập nhật import
- `utils.py` dòng ~243-261 — Thêm hàm `fmt_bang_ty()` format số tiền → tỷ đồng (cố định đơn vị)
- `tabs/tab_cdtotkvv_pgd.py` dòng ~31 — Thêm `fmt_bang_ty` vào import
- `tabs/tab_uy_thac.py` dòng ~20 — Thêm `fmt_bang_ty` vào import
- `tabs/tab_gqvl.py` dòng ~20 — Thêm `fmt_bang_ty` vào import

## [2026-05-12] — Xóa download PDF duplicate trong tab Tổng quan
- `tabs/tab_tongquan.py` dòng ~1357-1376 — Xóa phần "Tải file PDF đã tạo" với các nút 1 tháng/3 tháng/6 tháng/Trong năm để tránh trùng lặp với nút download trong mỗi tab
