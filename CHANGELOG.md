# CHANGELOG

## [2026-05-12] — Cập nhật Chay_VBSP_SCM.bat: tự mở trình duyệt
- `Chay_VBSP_SCM.bat` — Thêm `start "" http://localhost:8501` để tự động mở tab trình duyệt sau khi double-click

## [2026-05-12] — Fix sót `with tab:` trong tab_tien_do.py _render_tong_quan
- `tabs/tab_tien_do.py` dòng ~94 — `_render_tong_quan()` còn dùng `with tab:` thay vì `with get_tab_context(tab):` gây lỗi khi render từ sidebar (gọi với tab=None)
- `tabs/tab_tien_do.py` — Thêm `from utils import get_tab_context` ở đầu file, xoá import trùng ở dòng 542

## [2026-05-12] — Sửa lỗi context manager khi render tab trong ws_management
- `workspaces/ws_management.py` — ALL_ITEMS truyền `None` thay vì `st` vào render(tab, **kwargs); `_render_dgd_to_tkvv()` dùng `st.container()` khi tab_parent=None
- `tabs/tab_tongquan.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_tien_do.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_cbtd.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_khtd.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_kehoach.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_baocao.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_candoi.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_ban_dai_dien.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_uy_thac.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_nhiem_vu.py` — Cho phép render(tab=None) bằng `st.container()`
- `tabs/tab_audit_log.py` — Cho phép render(tab=None) bằng `st.container()`

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
