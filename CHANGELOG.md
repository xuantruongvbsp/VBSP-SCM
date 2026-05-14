# CHANGELOG

## [2026-05-14] — Cache sidebar I/O: giảm 12 I/O/rerun xuống ~1 (file stat)
- `data/pgd.py` dòng ~92 — Thêm `@st.cache_data(ttl=30)` cho `_doc_ngay_so_lieu()` + tham số `_mtime` làm cache key
- `data/pgd.py` dòng ~128 — Thêm `@st.cache_data(ttl=30)` cho `doc_trang_thai_file()` + tham số `_mtime` làm cache key
- `services/data_priority.py` dòng ~9 — Truyền `_mtime` vào `doc_trang_thai_file()` từ `os.path.getmtime`
- `alert_center.py` dòng ~15 — Cache `_kiem_tra_upload_tre()` vào `st.session_state["merge_meta_cache"]`, invalidate sau 60s

## [2026-05-14] — Tối ưu load dữ liệu: cache doc_hstd_toan_cn_pgd + session_state pgd_xa_map
- `data/pgd.py` dòng ~341 — Thêm `@st.cache_data(show_spinner=False)` + tham số `pgd_dir_mtime: float = 0.0` vào `doc_hstd_toan_cn_pgd()` để cache kết quả gộp toàn CN
- `app.py` dòng ~505 — Tính `_pgd_hstd_mtime = max(mtime)` từ các `hstd_latest.xlsx` trước khi gọi `doc_hstd_toan_cn_pgd()`
- `app.py` dòng ~551 — Wrap `_pgd_xa_map` + `_ds_pgd_all` + `lay_config()` vào `st.session_state` cache theo `ts_file(CACHE_HSTD)`, chỉ rebuild khi dữ liệu thay đổi

## [2026-05-13] — Fix logic codebase: DRY helpers, xóa dead code, fix nguon_von=0
- `tabs/tab_no_rui_ro.py` — Extract `_bo_border_cell`, `_set_cell`, `_set_row_font`, `_num` ra module-level (DRY), xóa 5+3 bản sao; thêm `italic` cho `_set_run` ở Tờ trình CN; xóa `fmt_bang_ty` dead import; thay `if "x" in locals()` bằng `locals().get("x","")`; xử lý `nguon_von=0` → mặc định về NGUON_TW + thêm `st.warning` khi phát hiện hồ sơ không có nguồn vốn

## [2026-05-13] — Cập nhật codebase_for_ai.md
- `codebase_for_ai.md` — Regenerate snapshot codebase (utf-8) để phản ánh thay đổi mới nhất

## [2026-05-13] — Thêm role `chuyenvien_cn` (Chuyên viên nghiệp vụ CN)
- `auth.py` — Thêm role `chuyenvien_cn` vào mapping/list quyền; can_upload/can_view_all_pgd/can_edit_khtd=True, can_manage_users=False; thêm helper `la_chuyen_vien_cn()`
- `config.py` — Bổ sung `chuyenvien_cn` vào danh sách role hợp lệ và nhóm quyền CN
- `workspaces/ws_management.py` — Đọc thêm `can_manage_users` từ `get_permissions()` (để dùng cho nhánh UI không quản lý user)
- `app.py` — Route `chuyenvien_cn` vào workspace `ws_management` (default/allowed) và cập nhật sidebar can_upload fallback

## [2026-05-13] — 04/XLN · 05/XLN · Tờ trình (01/TT, 02/TT) · 13/XLN · 14/XLN — python-docx thuần, tách TW/ĐP
- `tabs/tab_no_rui_ro.py` — Thêm xuất 04/XLN, 05/XLN; tách Tờ trình 01/TT (PGD) và 02/TT (CN); bổ sung nhập QĐ HĐQT cho 13/14; lưu thêm `dia_chi/ngay_vay/du_no_goc/lai_ton/nguon_von` vào kv; thay UI Bước 4 theo 2 section (trước/sau QĐ), tách TW/ĐP

## [2026-05-13] — Thêm 13/XLN, 14/XLN và Tờ trình (tách TW/ĐP) — python-docx thuần
- `tabs/tab_no_rui_ro.py` — Thay xuất 13/XLN, 14/XLN, Tờ trình từ docxtpl/template sang python-docx thuần; tách TW/ĐP theo `COT_NGUON_VON` và thay UI Bước 4 theo block nút mới
- `tabs/tab_uy_thac.py` — Xóa import template constants/hàm không còn dùng (giữ `docx_bytes_to_pdf`)

## [2026-05-13] — Bước 4: Thêm xuất Word/PDF Mẫu 01/XLN và 02/XLN (python-docx) trong tab nợ rủi ro
- `tabs/tab_no_rui_ro.py` — Thêm hàm tạo Word `_tao_word_01xln()`/`_tao_word_02xln()` + 2 nút xuất biểu mẫu 01/XLN, 02/XLN ở Bước 4

## [2026-05-13] — B5: Option A — chuyển mẫu ủy thác sang python-docx (không cần template)
- `tabs/tab_uy_thac.py` — Thay nhánh docxtpl (co_template/dien_template) của Kế hoạch KT, Mẫu 06/06A, Mẫu 15 bằng tạo Word bằng python-docx để luôn chạy được không phụ thuộc templates/

## [2026-05-13] — B5: Triển khai sub-tab "Biên bản & Báo cáo" trong tab_uy_thac
- `tabs/tab_uy_thac.py` — Thêm tạo Word Mẫu 16/TD + Biên bản xác minh nợ chiếm dụng (python-docx, xuất Word/PDF) và báo cáo tổng hợp ủy thác (Excel)

## [2026-05-13] — B6: Cảnh báo 3 tháng không hoạt động (KHĐ) trong ws_operation
- `workspaces/ws_operation.py` dòng ~154-186, ~909-970 — Thêm banner cảnh báo KHĐ sau khi xác định df_pgd và thêm tab "🔔 Đôn đốc KHĐ" trong nhóm Kiểm soát & Rủi ro

## [2026-05-13] — Tiến độ: thêm sub-tab Quản lý đầu việc (sửa/đóng-mở/xóa)
- `tabs/tab_tien_do.py` dòng ~311-508, ~571-583 — Thêm `_render_quan_ly_task()` và gắn vào tabs để sửa task, đóng/mở lại, xóa (admin_cn xác nhận 2 bước), có audit log

## [2026-05-13] — B7: Chuẩn hóa check role (normalize_role + la_phan_he_*) trong tabs/workspaces
- `tabs/tab_audit_log.py` dòng ~49 — Chuẩn hóa role trước khi check quyền xem Audit Log (admin→admin_cn)
- `tabs/tab_baocao.py` dòng ~100/~300 — Dùng role đã normalize + `la_phan_he_cn()` thay tuple role cứng khi chọn/lọc PGD
- `tabs/tab_cbtd.py` dòng ~24/~321 — Normalize role trước khi check quyền quản lý CBTD (loại trừ executive)
- `tabs/tab_checklist_bc.py` dòng ~476-492 — Normalize role và chuẩn hóa điều kiện truy cập/chỉnh sửa checklist
- `tabs/tab_diem_gd_pgd.py` dòng ~498-512 — Check CBTD bằng `normalize_role(... ) == user_pgd` thay vì so sánh `role != "user"`
- `tabs/tab_gqvl.py` dòng ~152/~172-199 — Normalize role và dùng `la_phan_he_cn()` (loại trừ executive) khi chọn PGD upload/xem
- `tabs/tab_kh_gqvl.py` dòng ~18-33 — Normalize role trước khi xác định quyền nhập KH GQVL (loại trừ executive)
- `tabs/tab_khtd_giao_dc.py` dòng ~565 — Duyệt tất cả chỉ cho CN roles sau normalize (admin_cn/manager_cn)
- `tabs/tab_khtd_nhap.py` dòng ~15/~982 — Chuẩn hóa check lịch sử phiên bản KHTD CN theo `normalize_role()==admin_cn`
- `tabs/tab_khtd_pgd.py` dòng ~552-575/~175 — Normalize role và chuẩn hóa điều kiện chọn PGD / upload văn bản QĐ (loại trừ executive)
- `tabs/tab_nhiem_vu.py` dòng ~533-545 — Normalize role trước khi phân nhánh UI manager vs user
- `tabs/tab_no_rui_ro.py` dòng ~36-51/~73-77 — Chuẩn hóa check CN/PGD bằng `la_phan_he_*` + normalize role
- `tabs/tab_quan_ly_dgd.py` dòng ~171 — Chỉ admin_cn được “Thay thế toàn bộ” (admin→admin_cn)
- `tabs/tab_tien_do.py` dòng ~549-556 — Dùng role đã normalize cho can_manage/is_exec/is_pgd_view
- `tabs/tab_upload_khnv.py` dòng ~23/~983/~1117 — Dùng `normalize_role()` khi check executive ở các nhánh thao tác
- `tabs/tab_xlrr_tong_hop.py` dòng ~264-275 — Normalize role và chuẩn hóa điều kiện truy cập Dashboard XLRR
- `tabs/tab_qd62.py` dòng ~13/~366 — Normalize role trong nhánh phân quyền duyệt hồ sơ
- `workspaces/ws_management.py` dòng ~22/~446/~854/~970 — Dùng `normalize_role()` cho các nhánh menu/quyền (Audit Log, Mã NĐT ĐP, edit)

## [2026-05-13] — Defensive coding: convert_dtypes trước khi ghi parquet + cảnh báo file trùng khi import hàng loạt
- `services/upload_service.py` dòng ~425-428 — Dùng `convert_dtypes()` trước khi ép object→str để giảm rủi ro ArrowTypeError khi có cột mixed-type
- `tabs/tab_upload_khnv.py` dòng ~803-808 — Hiển thị warning tổng hợp khi có file trùng (cùng đơn vị + cùng loại) trước khi bấm Import

## [2026-05-13] — Thêm lock + rollback an toàn khi merge parquet toàn CN
- `services/upload_service.py` dòng ~20-52, ~430-480 — Thêm module-level lock theo loại (hstd/nq11/gqvl) và cơ chế .bak (copy2/replace) để tránh race condition khi 2 session merge đồng thời

## [2026-05-13] — Sửa lỗi parse mã PGD dạng float trong upload NQ11
- `tabs/tab_upload_khnv.py` dòng ~113 — Thay `str(...).zfill(6)` bằng `int(float(raw))` để xử lý giá trị float (4602.0 → "004602") khi pandas đọc ô số từ Excel

## [2026-05-13] — Cập nhật codebase: sửa type hint và phân quyền tab_cdtotkvv
- `tabs/tab_cdtotkvv.py` dòng ~1160 — Sửa `**kwargs: dict` → `**kwargs` và ép kiểu `str()` cho role/username/cdto_mode/pgd_user
- `tabs/tab_cdtotkvv.py` dòng ~1176 — Dùng `la_phan_he_cn`/`la_phan_he_pgd` từ auth.py thay vì import hàm chưa tồn tại

## [2026-05-13] — Sửa nhận diện CDTOTKVV (tránh nhầm GQVL khi cùng có Sheet1)
- `tabs/tab_upload_khnv.py` dòng ~367 — Trong nhánh Sheet1: đọc header=7 và phân biệt CDTOTKVV theo cột "Tên đơn vị"

## [2026-05-13] — Sửa nhận diện tên PGD trong file GQVL theo Mã đơn vị
- `tabs/tab_upload_khnv.py` dòng ~443 — Đọc "Mã đơn vị" trong Sheet1 (header=7) và tra `MA_PGD_MAP` để lấy tên PGD

## [2026-05-13] — Nới nhận diện GQVL theo nội dung sheet
- `tabs/tab_upload_khnv.py` dòng ~367 — Nhận diện GQVL không chỉ dựa vào tên sheet "Sheet1"; fallback đọc sheet đầu và kiểm tra các cột đặc trưng

## [2026-05-13] — Tối ưu DQ check khi merge_du_lieu_toan_cn
- `services/upload_service.py` dòng ~280/~384 — Thêm tham số `pgd_moi_upload`; chỉ chạy `kiem_tra_chat_luong()` cho PGD vừa upload (khớp `pgd_moi_upload`) khi `da_dung_cache=False`

## [2026-05-13] — Sửa fallback context trong tab_upload_pgd và tab_khtd_giao_dc
- `tabs/tab_upload_pgd.py` dòng ~380 — Thay `ctx = tab if tab is not None else st` thành `st.container()` khi tab=None
- `tabs/tab_khtd_giao_dc.py` dòng ~701 — Thay `ctx = tab if tab is not None else st` thành `st.container()` khi tab=None

## [2026-05-13] — Sửa context manager khi render tab_upload_khnv
- `tabs/tab_upload_khnv.py` dòng ~1045 — Thay `ctx = tab if tab is not None else st` bằng fallback `st.container()` để tránh lỗi "'module' object does not support the context manager protocol"

## [2026-05-13] — Bổ sung logic xuất Excel tất cả xã trong tab_khtd_nhap.py
- `tabs/tab_khtd_nhap.py` dòng ~1059 — Thay thế phần xử lý trống của nút "📥 Xuất Excel tất cả xã" bằng code hoàn chỉnh: tạo sheet "Tổng hợp PGD" + sheet riêng từng xã (chỉ xã có kế hoạch > 0), thêm dòng "Tổng cộng" cuối mỗi sheet, xuất file qua `xuat_excel()` + `st.download_button`

## [2026-05-13] — Fix 3 lỗi critical trong tab_khtd_nhap.py
- `tabs/tab_khtd_nhap.py` dòng ~36 — Xóa `_tinh_th_gqvl_phan_tang` khỏi danh sách import từ `tabs.tab_khtd` (hàm local đã được định nghĩa tại dòng 48)
- `tabs/tab_khtd_nhap.py` dòng ~1066 — Xóa dòng `df_full = kwargs.get("df")` trong block xuất Excel (biến `df_full` là tham số trực tiếp của hàm)
- `tabs/tab_khtd_nhap.py` dòng ~1374 — Di chuyển `st.form_submit_button("💾 Lưu kế hoạch xã này")` và toàn bộ logic lưu vào bên trong `with st.form(...)`, đặt cuối form trước khi đóng block

## [2026-05-13] — Sửa: Thay thế cards HTML bằng bảng DataFrame cho "Cơ cấu dư nợ theo chương trình tín dụng"
- `tabs/tab_tongquan.py` dòng ~552-615 — Thay thế phần hiển thị "Cơ cấu dư nợ theo chương trình tín dụng" (cards HTML) bằng bảng DataFrame 7 cột (Chương trình, Số món vay, Số KH, Dư nợ (tỷ), Nguồn TW (tỷ), Nguồn ĐP (tỷ), Tỷ trọng %); xóa hoàn toàn phần cards_html và expander cũ; thêm `_NGUON_MAP` (dict comprehension) ngay sau import; không thay đổi các phần khác của file

## [2026-05-13] — Thêm: Hiển thị Nguồn TW/ĐP trong Cơ cấu dư nợ theo chương trình tín dụng
- `tabs/tab_tongquan.py` dòng ~542-582 — Thêm `_NGUON_MAP` từ `DS_CHUONG_TRINH`; tách dư nợ theo nguồn (`du_no_tw`, `du_no_dp`); bổ sung hiển thị TW/ĐP trong cards HTML; thêm CSS `.ct-src`

## [2026-05-12] — Sửa: Xóa context manager trong tabs/tab_tien_do_nop.py
- `tabs/tab_tien_do_nop.py` dòng ~57 — Xóa `ctx = tab if tab is not None else st` và `with ctx:`; render trực tiếp bằng `st.*` giữ nguyên toàn bộ logic bên trong

## [2026-05-12] — Sửa: lỗi import GSheet (oauth2client)
- `tabs/tab_tien_do_nop.py` dòng ~32 — ưu tiên dùng google-auth (`gspread.service_account`) và lazy-load `oauth2client` làm fallback để tránh ModuleNotFoundError; hiển thị lỗi rõ ràng khi thiếu dependencies/credentials
- `requirements.txt` — đã cài `oauth2client` trong môi trường bằng `pip install -r requirements.txt`
## [2026-05-12] — Thêm tab BC Tiến độ PGD
- `tabs/tab_tien_do_nop.py` — Tạo mới: đọc GSheet TIENDO_BAOCAO, dashboard tiến độ
- `workspaces/ws_management.py` — Thêm import & menu "BC Tiến độ PGD"

## [2026-05-12] — Ban Đại Diện: thay placeholder bằng 4 sub-tab chức năng
- `tabs/tab_ban_dai_dien.py` — Thêm 4 tab thật: tổng hợp KPI + export, dự báo vốn/room theo `khtd_cn`, quản lý họp (kv_store), lưu trữ văn bản (kv_store)

## [2026-05-12] — Bước 3: Auto-snapshot khi merge + cập nhật Executive tab Phân tích
- `services/upload_service.py` — Chuẩn hóa block auto-snapshot theo spec (alias `_luu_snap`, dùng session username)
- `workspaces/ws_executive.py` — Đổi KPI/heatmap theo spec (`_kpi_tang_truong`, line chart snapshot dùng `px.line`)

## [2026-05-12] — Chuẩn hóa schema/service snapshot theo spec Bước 1-2
- `db.py` — Chỉnh `hstd_snapshot` theo default `ma_ct/nguon_von='ALL'` và bỏ index ct theo spec
- `snapshot_service.py` — Cập nhật nội dung service theo spec Bước 2 (API + logic tổng hợp)
- `services/upload_service.py` — Auto tạo snapshot sau merge HSTD
- `workspaces/ws_executive.py` — KPI strip so với tháng trước + heatmap rủi ro PGD + line chart theo snapshot

## [2026-05-12] — Snapshot HSTD theo tháng + Executive Risk Heatmap
- `db.py` — Thêm bảng `hstd_snapshot` + index trong `init_db()`
- `snapshot_service.py` — Thêm service lưu/đọc/xóa snapshot theo kỳ (upsert-safe)
- `services/upload_service.py` — Auto tạo snapshot sau merge HSTD
- `workspaces/ws_executive.py` — KPI strip so với tháng trước + heatmap rủi ro PGD + line chart theo snapshot

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
- `workspaces/ws_management.py` — Đồng bộ lambda trong `_build_all_items()` với `render()` và thêm guard state cho `render_sidebar_menu()`

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
- `tabs/tab_tien_do.py` — Cho phép render(tab=None) bằng context fallback `st.container()` bằng `st.container()`
- `tabs/tab_cbtd.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
- `tabs/tab_khtd.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
- `tabs/tab_kehoach.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
- `tabs/tab_baocao.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
- `tabs/tab_candoi.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
- `tabs/tab_ban_dai_dien.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
- `tabs/tab_uy_thac.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
- `tabs/tab_nhiem_vu.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
- `tabs/tab_audit_log.py` — Cho phép render(tab=None) bằng context fallback `st.container()`
