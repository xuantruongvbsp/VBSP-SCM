# CHANGELOG

## [2026-05-12] — Tắt prompt Streamlit “Welcome/Email” để chạy không tương tác
- `.streamlit/config.toml` — Thêm `browser.gatherUsageStats = false`, `server.headless = true`

## [2026-05-12] — Thêm hàm _xuat_pdf_nhiem_vu() với tiêu đề đầy đủ, font Times New Roman
- `tabs/tab_nhiem_vu.py` dòng ~555-661 — Thêm hàm _xuat_pdf_nhiem_vu() tạo PDF báo cáo "BÁO CÁO TÌNH HÌNH THỰC HIỆN NHIỆM VỤ" với header ngân hàng, font Times New Roman, bảng zebra, footer tự động

## [2026-05-12] — Chuyển navigation menu từ col_sidebar sang st.sidebar thật
- `workspaces/ws_management.py` dòng ~838-935 — Xóa `st.columns([1, 4])` + `with col_sidebar` + `with col_content`, thay bằng `with st.sidebar` và render nội dung trực tiếp
- `workspaces/ws_management.py` dòng ~842-865 — Cập nhật tất cả lambda trong ALL_ITEMS: bỏ `c=col_content`, dùng `st` làm đối số render

## [2026-05-12] — Sửa CSS sidebar: dùng st.container(border=True) thay CSS selector chung
- `workspaces/ws_management.py` dòng ~838-858 — Xóa toàn bộ CSS injection `<style>...</style>` dùng selector `div[data-testid="stHorizontalBlock"] > div:first-child` gây tô màu nhầm toàn trang
- `workspaces/ws_management.py` dòng ~908 — Wrap toàn bộ nội dung sidebar trong `st.container(border=True)` thay vì CSS hack, chỉ tô viền đúng cột sidebar

## [2026-05-12] — Di chuyển CSS sidebar ws_management.py lên cấp page
- `workspaces/ws_management.py` dòng ~837 — Di chuyển CSS injection sidebar ra ngoài `with col_sidebar` lên trước `st.columns()` để inject ở cấp page, thêm CSS cho button secondary
- `workspaces/ws_management.py` dòng ~886-899 — Xóa CSS injection cũ bên trong `with col_sidebar` để tránh trùng lặp

## [2026-05-12] — Thêm hàm fmt_bang_ty() và cập nhật import
- `utils.py` dòng ~243-261 — Thêm hàm `fmt_bang_ty()` format số tiền → tỷ đồng (cố định đơn vị)
- `tabs/tab_cdtotkvv_pgd.py` dòng ~31 — Thêm `fmt_bang_ty` vào import
- `tabs/tab_uy_thac.py` dòng ~20 — Thêm `fmt_bang_ty` vào import
- `tabs/tab_gqvl.py` dòng ~20 — Thêm `fmt_bang_ty` vào import

## [2026-05-12] — Xóa download PDF duplicate trong tab Tổng quan
- `tabs/tab_tongquan.py` dòng ~1357-1376 — Xóa phần "Tải file PDF đã tạo" với các nút 1 tháng/3 tháng/6 tháng/Trong năm để tránh trùng lặp với nút download trong mỗi tab
