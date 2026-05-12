# CHANGELOG

## [2026-05-12] — Cập nhật ROADMAP B2/B7 và refactor role check theo auth.py
- `docs/ROADMAP.md` — Đánh dấu B2 hoàn tất và B7 hoàn tất theo thực tế code
- `tabs/tab_khtd_giao_dc.py` — Dùng `normalize_role()`/`la_phan_he_pgd()` thay check role cứng
- `tabs/tab_khtd_mau07.py` — Dùng `la_phan_he_pgd()` thay `role == "user"`
- `tabs/tab_khtd_pgd.py` — Dùng `normalize_role()` thay `role == "admin"` khi xóa văn bản
- `tabs/tab_kiem_soat.py` — Dùng `normalize_role()` cho chế độ readonly executive
- `tabs/tab_quan_ly_dgd.py` — Dùng `normalize_role()` cho nhánh executive/readonly
- `tabs/tab_tien_do.py` — Dùng `normalize_role()` cho biến `is_exec`
- `tabs/tab_upload_pgd.py` — Dùng `la_phan_he_pgd()`/`normalize_role()` thay check role cứng

## [2026-05-12] — Chuẩn hóa context manager cho render(tab) trong tabs
- `tabs/tab_cdtotkvv.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_cdtotkvv_pgd.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_danhsach.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_diem_gd_pgd.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_gqvl.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_khtd_mau07.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_khtd_pgd.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_nhiem_vu.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_no_rui_ro.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_nq11.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_quan_ly_dgd.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_tien_do.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_tracuu.py` — Thay `with tab:` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_xlrr_tong_hop.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_audit_log.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_baocao.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_ban_dai_dien.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_cbtd.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_candoi.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_khtd.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_kehoach.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_tongquan.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None
- `tabs/tab_uy_thac.py` — Thay `get_tab_context(tab)` bằng context fallback `st.container()` khi tab=None

## [2026-05-12] — Checklist BC: đổi context render(tab)
- `tabs/tab_checklist_bc.py` — `render()` dùng `tab` nếu có, fallback `st.container()` nếu tab=None

## [2026-05-12] — Thêm tab Checklist báo cáo định kỳ
- `tabs/tab_checklist_bc.py` — Checklist theo dõi hạn nộp báo cáo tháng/quý/năm, cập nhật trạng thái và xuất Excel (lưu kv_store)

## [2026-05-12] — Đổi nhãn menu XLRR theo QĐ62
- `workspaces/ws_management.py` — Đổi label menu “XLRR theo QĐ” → “Xử lý rủi ro theo QĐ62”

## [2026-05-12] — Thêm dashboard XLRR tổng hợp (QĐ62 + nợ RR HSTD)
- `tabs/tab_xlrr_tong_hop.py` — Dashboard tổng hợp XLRR toàn CN với 4 tab con + xuất Excel
- `workspaces/ws_management.py` — Thêm menu “XLRR Tổng hợp” trong nhóm “Kiểm soát”

## [2026-05-12] — Đổi tên menu XLRR
- `workspaces/ws_management.py` — Đổi nhãn menu "Nợ rủi ro & XLRR" thành "XLRR theo QĐ"

## [2026-05-12] — Gộp menu QĐ62 vào dashboard XLRR
- `workspaces/ws_management.py` — Xóa item “Nợ rủi ro QĐ62”, đổi label “XLRR Tổng hợp” → “Nợ rủi ro & XLRR”

## [2026-05-12] — Chuyển menu Điều hành sang sidebar cấp app.py
- `app.py` — Gọi `render_sidebar_menu()` (ws_management) ngay sau phần “Không gian làm việc” trong sidebar
- `workspaces/ws_management.py` — Xóa block `with st.sidebar:` trong `render()` vì menu đã render từ `app.py`

## [2026-05-12] — Đổi nhãn menu “Tiến độ” → “Tiến độ Công việc”
- `workspaces/ws_management.py` — Đổi label menu “Tiến độ” thành “Tiến độ Công việc” để hiển thị rõ nghĩa

## [2026-05-12] — Căn chỉnh helper menu Điều hành (ws_management)
- `workspaces/ws_management.py` — Đồng bộ lambda trong `_build_all_items()` với `render()` và thêm guard state cho `render_sidebar_menu()`

## [2026-05-12] — Thêm hàm dựng menu điều hành cho app.py gọi
- `workspaces/ws_management.py` — Thêm `_build_all_items()` và `render_sidebar_menu()` để tách logic menu sidebar dùng chung

## [2026-05-12] — Fix thiếu dòng Hội sở trong bảng tổng quan PGD
- `tabs/tab_tongquan.py` dòng ~673 — Thêm `DON_VI_CHI_NHANH` vào list `pgd_thieu_bang` để không bỏ sót "Hội sở Chi nhánh tỉnh" khi render bảng
- `tabs/tab_tongquan.py` dòng ~16 — Import thêm `DON_VI_CHI_NHANH`

## [2026-05-12] — Cập nhật Chay_VBSP_SCM.bat: start /b + timeout chờ server
- `Chay_VBSP_SCM.bat` — Dùng `start /b` để chạy server ngầm + `timeout /t 4` chờ 4 giây rồi mới mở trình duyệt

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
