# CHANGELOG

## [2026-05-30] — Tích hợp OneDrive tự động cho module Quản lý Công văn
- `services/onedrive_service.py` — tạo mới: upload file lên OneDrive qua Microsoft Graph API (Client Credentials), cache token trong kv_store, chunked upload cho file >4MB, fallback graceful
- `db.py` dòng ~644 — migration: ALTER TABLE cong_van ADD COLUMN onedrive_url TEXT
- `services/cong_van_service.py` — thêm param `onedrive_url` vào `them_cv()`, `cap_nhat_cv()`; thêm cột "OneDrive URL" vào `xuat_danh_sach_cv()`
- `tabs/tab_quan_ly_cong_van.py` — gọi `upload_cong_van()` sau khi lưu file local; hiển thị link "📎 Xem file" trong danh sách; thêm tab "🟢/🔴 OneDrive" với hướng dẫn 5 bước + kiểm tra kết nối + FAQ
- `.streamlit/secrets.toml` — tạo mới: template cấu hình Azure credentials (không commit)

## [2026-05-30] — Fix card Xếp loại Tổ TK&VV không hiện sau upload CDTOTKVV toàn CN
- `tabs/tab_tongquan.py` dòng ~412 — thay `except Exception: pass` bằng `st.warning()` hiển thị lỗi cho người dùng; thêm `st.info()` khi không có dữ liệu CDTOTKVV thay vì im lặng bỏ qua
- `services/upload_service.py` dòng ~928 — fix `NameError` với biến `suffix` trong khối `except` của `luu_pgd_file()`: tách `suffix` ra ngoài try, thêm fallback `thang_nam.replace("/", "_")`, bọc riêng phần ghi file versioned

## [2026-05-30] — Upload CDTOTKVV toàn CN: 1 file tổng hợp → tự tách 22 PGD
- `data/cdtotkvv.py` dòng ~170 — thêm `tach_file_cdto_toan_cn(file_bytes)`: đọc file toàn CN, tự phát hiện dòng data, map 18 cột → 20 cột CDTOTKVV_COLS (fix hoán vị LOAITO/DVUT, fix TONGDIEM→tong_diem, XEPLOAI→xep_loai)
- `services/upload_service.py` dòng ~301 — thêm `xu_ly_cdto_toan_cn(file_bytes)`: tách + lưu từng PGD qua `luu_file_pgd_voi_lich_su`
- `tabs/tab_upload_khnv.py` — thêm `_render_cdto_toan_cn(username)` + gọi trong tab "Dữ liệu Hiện tại": preview đơn vị, cảnh báo thiếu PGD, nút upload

## [2026-05-30] — Nâng cấp xuất PDF tab tiến độ: refactor helper, đổi tên, strip emoji Excel
- `tabs/tab_tien_do_nop.py` — extract `_pdf_button()` helper dùng chung cho 2 loại PDF, loại bỏ ~25 dòng lặp
- `tabs/tab_tien_do_nop.py` — import `xuat_pdf`, `xuat_pdf_group_header` ra ngoài handler
- `tabs/tab_tien_do_nop.py` — đổi "PDF có Header" → "📊 PDF theo đơn vị" cho rõ nghĩa
- `tabs/tab_tien_do_nop.py` — Excel cũng strip emoji cột Trạng thái (nhất quán với PDF)

## [2026-05-30] — Fix xuất báo cáo tiến độ: phân loại ⚠️, slug filename, spinner Excel
- `tabs/tab_tien_do_nop.py` dòng ~267 — ⚠️ (thiếu file) vào ds_chua thay vì ds_da, nhất quán với rule thiếu file = Trễ hạn
- `tabs/tab_tien_do_nop.py` dòng ~305 — tên file dùng ASCII slug thay vì tiếng Việt (tránh lỗi download)
- `tabs/tab_tien_do_nop.py` dòng ~311 — thêm `st.spinner` cho nút Excel

## [2026-05-30] — Fix PDF xuất tiến độ: strip emoji + stale download bytes
- `tabs/tab_tien_do_nop.py` — `_clean_trang_thai()`: bỏ emoji khỏi cột Trạng thái trước khi truyền vào PDF (font TNR không hỗ trợ emoji)
- `tabs/tab_tien_do_nop.py` — `_clear_export_cache()` + `on_change` trên radio/selectbox: xóa bytes cũ khi đổi filter, tránh tải nhầm file

## [2026-05-30] — Tab Tổng quan: xuất PDF chọn Đã hoàn thành / Chưa hoàn thành / Tất cả
- `tabs/tab_tien_do_nop.py` — `_render_tong_quan()`: tách ds thành 3 list `ds_tat_ca`/`ds_da`/`ds_chua`; thêm `st.radio` chọn loại xuất; tiêu đề file/PDF/PDF Header thay đổi theo loại; section luôn hiện thay vì chỉ khi có 🔴

## [2026-05-30] — Tab Tổng quan: ghi chú, ghi đè/chỉ ghi chú, badge ⚠️ thiếu file
- `tabs/tab_tien_do_nop.py` — `_doc_manual_log()`: đổi return type thành `{(pgd,loai): entry_dict}` (backwards-compatible)
- `tabs/tab_tien_do_nop.py` — matrix build: badge `*` ghi đè, `📝` chỉ ghi chú, `⚠️` auto-detect `file_dinh_kem` trống; caption chú giải 3 badge
- `tabs/tab_tien_do_nop.py` — form thủ công: thêm `ghi_chu` text_input + `ghi_de` checkbox; list entries hiện 4 cột kèm ghi chú

## [2026-05-30] — Fix metrics tab Tổng quan nhất quán với ma trận
- `tabs/tab_tien_do_nop.py` dòng ~191 — build `rows` trước, tính metrics từ `rows` thay vì `df_dedup`; metrics nay khớp chính xác với ma trận kể cả đánh dấu thủ công; bỏ `df_dedup` không cần thiết

## [2026-05-30] — Tab Tổng quan tiến độ nộp BC: đánh dấu thủ công PGD nộp ngoài Form
- `tabs/tab_tien_do_nop.py` — thêm `_doc_manual_log()`, `_doc_manual_log_raw()`, `_luu_manual_log()`; kv_store key `manual_nop_tdn` lưu `list[dict]`
- `tabs/tab_tien_do_nop.py` — `_render_tong_quan()`: parallel lookup `manual_map` TRƯỚC GSheet khi build ma trận; ô override có dấu `*`; caption giải thích dưới ma trận
- `tabs/tab_tien_do_nop.py` — `_render_tong_quan()`: form 3 field (PGD/Loại/Ngày) + nút "✅ Đánh dấu"; danh sách đánh dấu kèm nút "↩️ Bỏ" từng entry
- `tabs/tab_tien_do_nop.py` — signature `_render_tong_quan` thêm `username`, `can_config`; form chỉ hiện cho admin CN; có audit log `tdn_manual_submit`

## [2026-05-30] — Tab Theo dõi nhập liệu: hỗ trợ 3 kiểu cấu trúc sheet
- `tabs/tab_theo_doi_nhap.py` — thêm `loai_cau_truc`: phẳng / phân cấp STT / cột PGD riêng; form chỉnh sửa hiện đúng trường tùy kiểu; caption hiển thị loại đang dùng

## [2026-05-30] — Fix tab Tiến độ nộp BC: tổng quan chỉ theo dõi loại có deadline + xác nhận xóa
- `tabs/tab_tien_do_nop.py` — `_render_tong_quan()`: ds_loai lấy từ `deadline_cfg` thay vì GSheet, lọc df_dedup theo ds_loai; thêm early return nếu chưa có deadline. Xóa deadline → loại đó biến mất khỏi tổng quan
- `tabs/tab_tien_do_nop.py` — `_render_cai_dat()`: nút "🗑 Xóa" → `st.popover` có xác nhận "⚠️ Xác nhận xóa"

## [2026-05-30] — Tab Theo dõi nhập liệu: mockup hướng dẫn + thêm/xóa chỉ tiêu động
- `tabs/tab_theo_doi_nhap.py` — thêm mockup HTML giải thích cấu trúc sheet; form thêm mới có nút ➕/✕ để quản lý số chỉ tiêu động; help text cho từng trường

## [2026-05-30] — Nâng cấp tab Theo dõi nhập liệu: hỗ trợ nhiều Google Sheet
- `tabs/tab_theo_doi_nhap.py` — đổi từ 1 config → list nhiều sheet (`gsheet_theo_doi_nhap_list`); thêm selectbox chọn sheet; UI thêm/sửa/xóa từng sheet; tự migrate config cũ

## [2026-05-30] — Config Sheet theo dõi nhập liệu HSSV Lần 2
- `kv_store[gsheet_theo_doi_nhap_config]` — auto-config Sheet ID ĐIỀU CHỈNH HSSV LẦN 2, tab, header_row=10, col HSSV=4, Nước sạch=8, Việc làm=13

## [2026-05-30] — Tính năng mới: Tab Theo dõi nhập liệu PGD (GSheet phân cấp)
- `tabs/tab_theo_doi_nhap.py` — tạo mới: đọc GSheet phân cấp PGD→Xã/Phường, tính % điền theo từng chương trình (HSSV/Nước sạch/Việc làm), ma trận PGD × CT, xuất Excel, tab cài đặt admin
- `tabs/tab_quan_ly_cv.py` — thêm sub-tab "📋 Theo dõi nhập liệu" vào nhóm Báo cáo

## [2026-05-30] — Fix đếm KPI trùng lặp tab Tổng quan tiến độ nộp BC
- `tabs/tab_tien_do_nop.py` — `_render_tong_quan()`: deduplicate theo `(ten_pgd, loai_bao_cao)` trước khi tính KPI, giữ lần nộp muộn nhất; label "Tổng lượt nộp" → "Đã nộp (đơn vị × loại)"

## [2026-05-30] — Làm phẳng tab Quản lý Công việc: 6→2 nhóm
- `tabs/tab_quan_ly_cv.py` — **UX REFACTOR**: 6 tab ngang rối → 2 nhóm logic (📋 Công việc & Tiến độ / 📊 Báo cáo), mỗi nhóm 3 sub-tab
- `tabs/tab_quan_ly_bc.py` — KHÔNG CÒN DÙNG, có thể xóa (đã flat từ trước)

## [2026-05-30] — Cập nhật rules.md + BUGMAP.md
- `.trae/rules/rules.md` — cập nhật ngày, thêm `tab_tien_do_nop.py` vào cấu trúc + bản đồ file, thêm key `bao_cao_deadline_config`, cập nhật ghi chú `st.html()`
- `BUGMAP.md` — thêm H6 (deadline nested dict) và H7 (tên PGD Form ≠ DS_PGD)

## [2026-05-30] — Fix cài đặt deadline: thêm sửa + xóa + gộp nguồn
- `tabs/tab_tien_do_nop.py` — `_render_cai_dat()`: selectbox nay gộp cả loại từ GSheet lẫn loại đã có trong kv_store; thêm nút 🗑 Xóa deadline; label hiện ✅ khi loại đã có deadline

## [2026-05-30] — Flatten tab Quản lý Công việc: xóa wrapper tab_quan_ly_bc
- `tabs/tab_quan_ly_cv.py` — mở rộng từ 4 → 6 tab phẳng, nhúng trực tiếp bc_tong_hop / tab_tien_do_nop / tab_checklist_bc (trước ở tầng 3, nay tầng 2)
- `tabs/tab_quan_ly_bc.py` — không còn dùng (có thể xóa sau khi xác nhận ổn định)

## [2026-05-30] — Fix lệch cột COT + cache tab_tien_do_nop.py
- `tabs/tab_tien_do_nop.py` dòng 25 — thêm lại `ky_bao_cao` vào COT (Trae bỏ nhưng Google Form vẫn có cột Kỳ Báo Cáo → toàn bộ cột bị lệch, Họ tên bị mất)
- `tabs/tab_tien_do_nop.py` dòng 60–71 — chuyển `@st.cache_data(ttl=300)` từ `_chuan_hoa_ten_pgd` (sai) sang `_doc_du_lieu` (đúng)

## [2026-05-29] — Fix 2 bug tab_tien_do_nop.py (review fix Trae)
- `tabs/tab_tien_do_nop.py` dòng 187, 325 — sửa `st.session_state.get("txt_username")` → `"username"` (bug audit log ghi "unknown")
- `tabs/tab_tien_do_nop.py` dòng 411–431 — bỏ hardcode màu nền trong flow HTML, dùng CSS variable tương thích dark mode

## [2026-05-29] — Seed admin user + dọn nested repo
- `auth.py` — gọi `doc_users()` để seed user admin mặc định vào bảng `users` (trước đó bảng trống)
- `.gitignore` — thêm `VBSP-SCM/` để ẩn nested repo clone do Trae tạo (cần xóa thủ công sau khi đóng Trae)

## [2026-05-29] — GSheet hoàn chỉnh: JWT fix + bỏ kỳ báo cáo + health check
- `tabs/tab_tien_do_nop.py` — **REFACTOR LỚN**: bỏ `ky_bao_cao` khỏi COT (8→7 cột), deadline config đổi từ `{loai: {ky: dl}}` → `{loai: dl}`, đơn giản 3 tab Tổng quan / Danh sách / Cài đặt, thêm tab Hướng dẫn
- `tabs/tab_tien_do_nop.py` dòng ~67 — **BUG FIX**: Google Form thêm cột "Cột 8" → dùng `r[:len(COT)]` chỉ lấy N cột đầu
- `setup_env.bat` — Thêm Bước 1: đồng bộ thời gian Windows (`w32tm /resync`) trước cài đặt (ngừa lỗi JWT)
- `BUGMAP.md` — H3: `invalid_grant` (key bị Google Disable vì exposed public repo → tạo key mới) + H4: số cột Sheet ≠ COT + H5: loại bỏ kỳ báo cáo
- Health check toàn diện: 52/52 tabs compile OK, 230 .py files (89,761 dòng), DB 0.3MB, audit_log 75 dòng, không còn `st.cache`/`st.beta_` deprecated

## [2026-05-27] — Cải tiến Chay_VBSP_SCM.bat tự động setup trên máy mới
- `Chay_VBSP_SCM.bat` — Nâng cấp script tự động: (1) tự tìm Python ở nhiều vị trí (LocalAppData, Program Files), (2) tự tạo venv nếu chưa có, (3) tự cài requirements.txt nếu thiếu, (4) hiển thị tiến trình 4 bước rõ ràng

## [2026-05-26] — Review + fix §2.4 Quản lý Công văn (3 bug)
- `services/cong_van_service.py` dòng ~168 — **BUG FIX HIGH**: `ds_cv_sap_den_han()` lọc `ngay_ban_hanh` thay vì `ngay_nhan` → công văn quá hạn hiển thị sai; đổi sang raw query filter `ngay_nhan <= ?`
- `tabs/tab_quan_ly_cong_van.py` dòng ~139,154 — **BUG FIX MEDIUM**: `.index()` crash `ValueError` nếu DB có loai/trang_thai ngoài enum → thêm guard fallback
- `tabs/tab_quan_ly_cong_van.py` dòng ~238-241 — **CLEANUP**: xóa dead code `'keyword' in dir()` (vars luôn defined trong Streamlit rerun)

## [2026-05-26] — Review + fix tab_pgd_cards redesign (BQ/hộ)
- `services/tongquan_service.py` dòng ~587 — **BUG FIX**: `.replace(0, pd.NA)` trên `int64` Series → đổi sang `.where(so_kh > 0)` tránh dtype object gây crash
- `tabs/tab_pgd_cards.py` dòng ~326 — **BUG FIX LOGIC**: `bq_cn = mean()` of per-PGD BQ (sai khi PGD khác quy mô) → đổi sang weighted mean `sum(du_no)/sum(so_kh)`

## [2026-05-26] — §2.4 Quản lý Công văn: DB + CRUD + tìm kiếm full-text + tag + xuất Excel
- `db.py` dòng ~618 — **MỚI** bảng `cong_van` (15 cột: so_hieu, trich_yeu, ngay_ban_hanh, ngay_nhan, loai, co_quan, nguoi_ky, tag, noi_dung, file_path, trang_thai...) + 3 index
- `services/cong_van_service.py` — **MỚI** — CRUD (them/cap_nhat/xoa/doc_cv), `tim_kiem_cv()` full-text LIKE (so_hieu + trich_yeu + noi_dung + tag + co_quan), `thong_ke_cv_theo_loai/trang_thai()`, `xuat_danh_sach_cv()` 3 sheet, `ds_cv_sap_den_han()` cảnh báo quá hạn
- `tabs/tab_quan_ly_cong_van.py` — **MỚI** — 3 sub-tab: 🔍 Tìm kiếm & Danh sách (KPI cards + filter + bảng + edit/delete), ➕ Thêm mới (form), 📤 Xuất Excel. Tag multi-select gợi ý (TW, HĐQT, Tín dụng, Kế toán...)
- `workspaces/ws_management.py` — mount tab vào group "Phối hợp với PGD"

## [2026-05-26] — Fix bugs ktnb_service + den_han_notice_service
- `services/ktnb_service.py` dòng 821-892 — **BUG FIX CRITICAL**: `ten_dot` → `ten_pgd_ks` (cột không tồn tại trong schema, gây OperationalError khi gọi `tong_hop_ktnb_theo_nam()` / `xuat_bao_cao_ktnb_excel()`)
- `services/ktnb_service.py` dòng 22-38 — Xoá unused imports `COT_THOI_HAN`, `COT_LAI_SUAT`, `COT_DIA_CHI`
- `services/den_han_notice_service.py` dòng 6/115 — `__import__("datetime").timedelta` → import `timedelta` proper
- `services/den_han_notice_service.py` dòng 17 — Xoá unused import `COT_TEN_TO`
- `services/den_han_notice_service.py` dòng 177 — `except Exception: pass` → log error (rule 5.15)

## [2026-05-26] — §2.3 Thông báo đến hạn Word + §2.5 Báo cáo KTNB tổng hợp
- `services/den_han_notice_service.py` — **MỚI** — `tao_thu_nhac_no()`: tạo thư nhắc nợ Word cho 1 KH; `lay_ds_den_han()`: DuckDB lấy DS khoản vay đến hạn trong N ngày; `tao_thu_hang_loat()`: batch tạo thư cho nhiều KH
- `services/ktnb_service.py` dòng ~812 — **MỚI** 3 hàm: `tong_hop_ktnb_theo_nam()` (KPI + ds đợt), `tong_hop_ktnb_theo_khoi()` (theo khối NV), `xuat_bao_cao_ktnb_excel()` (xuất Excel 3 sheet)

## [2026-05-26] — Tab card 22 PGD: redesign + fix applymap pandas 3.0
- `tabs/tab_pgd_cards.py` dòng ~416 — **BUG FIX**: thay `Styler.applymap()` → `.map()` (pandas 3.0 đã xóa applymap — crash AttributeError khi render bảng xếp hạng)
- `tabs/tab_pgd_cards.py` — **REDESIGN**: card gradient dark, 5 KPI metrics (thêm BQ/hộ), Plotly combo chart dư nợ+NQH%+BQ/hộ, bar chart xếp hạng BQ/hộ, bảng color-coded Styler, sort option "BQ/hộ (giảm)", rank badge #N trên card
- `services/tongquan_service.py` dòng ~586 — **MỚI**: cột `dn_binh_quan_ho` (dư nợ bình quân hộ = du_no/so_kh, đơn vị đồng) trong output `tinh_card_pgd()`

## [2026-05-26] — §2.1 Word report + §2.3 So sánh đến hạn cùng kỳ
- `scripts/daily_word_report.py` — **MỚI** — tạo báo cáo Word định kỳ (4 section: Tổng quan, PGD chi tiết, Top NQH, KHTD) với openpyxl formatting
- `scripts/daily_report.py` — **MỚI** — tạo báo cáo Excel định kỳ hằng ngày (4 sheet: Bìa, Tổng quan PGD, Top NQH, Đến hạn 30d, KHTD) + `list_reports()` + cleanup 30d
- `scripts/setup_daily_report_task.bat` — **MỚI** — cài Task Scheduler chạy daily_report.py lúc 07:00
- `tabs/tab_bao_cao_dinh_ky.py` — **MỚI** — 2 cột Excel/Word: tạo ngay + download; đăng ký ở 3 workspace (management, executive, operation)
- `services/den_han_compare_service.py` — **MỚI** — `so_sanh_den_han_cung_ky()`: so sánh số món + dư nợ đến hạn N tháng giữa năm nay và baseline năm trước; `phan_tich_den_han_dot_bien()`: phát hiện PGD tăng ≥30%

## [2026-05-26] — §2.1 Báo cáo định kỳ sáng: service + tab + health_check integration
- `services/daily_report_service.py` — **MỚI** — tạo Excel tóm tắt sáng, lưu `cache/reports/`
  - `REPORTS_DIR` = `BASE_DIR/cache/reports` (tuyệt đối, không phụ thuộc CWD)
  - `tao_bao_cao_sang(nguoi_tao)` → tạo 4 sheets: Tổng quan, Dư nợ PGD, NQH PGD, Đến hạn tháng
  - `lay_bao_cao_sang_hom_nay()` → Path nếu đã có, None nếu chưa
  - `lay_ds_bao_cao(n=7)` → list báo cáo N ngày gần nhất
  - `ten_file_ngay(d)` → `bao_cao_sang_DDMMYYYY.xlsx`
- `tabs/tab_bao_cao_dinh_ky.py` — **MỚI** — UI: trạng thái hôm nay, nút Tạo ngay, download button, lịch sử 7 ngày
- `workspaces/ws_management.py` dòng ~803 — mount tab `📅 Báo cáo định kỳ` vào group `Báo cáo`
- `health_check.py` dòng ~343 — tự động tạo báo cáo sáng sau health check nếu chưa có hôm nay

## [2026-05-26] — Test components: 27 test cases mới cho delta_card + movers + loan_drawer + tongquan_service
- `tests/test_components.py` — **MỚI** 27 test cases cho 6 class:
  - `TestFmtVnNum` (5): format số VN (`_fmt_vn_num`)
  - `TestPickDimCol` (5): lookup cột từ dimension key (`_pick_dim_col`)
  - `TestFormatValue` (3): format tiền/tỷ lệ/số (`_format_value`)
  - `TestRenderField` (8): HTML field drawer (`_render_field`) — null, nan, tiền, pct, error
  - `TestLocDuNoDuong` (3): lọc dư nợ dương (`loc_du_no_duong`)
  - `TestChuanHoaNgay` (3): chuẩn hóa ngày datetime/string/missing (`chuan_hoa_ngay`)
- Tổng tests: 717 (↑27) — 46 file

## [2026-05-26] — Health check tự động: ghi kv_store + sidebar alert + Task Scheduler
- `health_check.py` dòng ~298 — thêm `_ghi_ket_qua_kv()`: sau mỗi lần chạy ghi JSON vào `kv_store` key `health_check_result` (ts, total, passed, failed, failed_labels, exit_code)
- `health_check.py` dòng ~320 — `__main__` gọi `_ghi_ket_qua_kv(exit_code)` trước `sys.exit()`
- `alert_center.py` dòng ~382 — thêm `_kiem_tra_health_check()`: đọc `health_check_result` từ kv_store, sinh AlertItem 🔴/🟠 nếu failed≥1, 🟡 nếu chưa chạy hoặc stale >25h
- `alert_center.py` dòng ~411 — `_build_alert_items()` gọi `_kiem_tra_health_check()` cho CN role
- `scripts/setup_health_check_task.bat` — **MỚI** — cài Windows Task Scheduler chạy health_check.py lúc 06:30 hằng ngày, log ra `logs/health_check.log`

## [2026-05-26] — Lưu cấu hình lọc: ROADMAP §1.4 UX
- `components/filter_bar.py` dòng 1–8 — **MỚI** import `db`, `logger`; thêm docstring "Lưu cấu hình bộ lọc"
- `components/filter_bar.py` dòng 12–52 — **MỚI** 4 hàm quản lý preset: `load_filter_presets()`, `save_filter_presets()`, `get_last_filter_preset_name()`, `set_last_filter_preset_name()` — dùng kv_store key `filter_preset_{username}`
- `components/filter_bar.py` dòng 65 — `filter_bar()` thêm param `username=""` (optional) + docstring
- `components/filter_bar.py` dòng 92–99 — **MỚI** auto-load: khi filter_bar mở lần đầu, tự động tải preset lần cuối dùng
- `components/filter_bar.py` dòng 186–188 — **MỚI** hiện UI Save/Load/Delete nếu `username` được truyền
- `components/filter_bar.py` dòng 198–213 — **MỚI** `_apply_preset_to_session()`: áp dụng giá trị preset vào session_state
- `components/filter_bar.py` dòng 216–274 — **MỚI** `_show_filter_presets_ui()`: 3 cột Save / Load / Delete với text input + selectbox + button

## [2026-05-26] — Fix UserWarning pd.to_datetime thiếu format
- `alert_center.py` dòng ~227 — thêm `format='mixed'` vào `pd.to_datetime()` trong `_canh_bao_no_khoanh_sap_het_han()` — loại bỏ UserWarning "Could not infer format"

## [2026-05-26] — ROADMAP.md: đồng bộ hiện trạng + bổ sung giai đoạn 2.4–2.6
- `ROADMAP.md` — bổ sung 9 mục vào "Hiện trạng": KTNB, Xây dựng KHTD, CBTD Dashboard, Phối hợp PGD, Quản lý Công văn, Báo cáo v2, Dark Mode, TabContext, Cold start −54s
- `ROADMAP.md` — §1.1 Test: cập nhật KPI ≥80%, ghi nhận 43 file/839 cases
- `ROADMAP.md` — §1.2 Performance: ghi nhận cold start đã đạt; 2 mục Done
- `ROADMAP.md` — §1.3: thêm TabContext adoption; nâng health check → 🔴 Cao
- `ROADMAP.md` — §1.4: nâng health check scheduled → 🔴 Cao
- `ROADMAP.md` — thêm §2.4 Quản lý Công văn (4 mục)
- `ROADMAP.md` — thêm §2.5 KTNB Phase 2 (4 mục)
- `ROADMAP.md` — thêm §2.6 Xây dựng KHTD Workflow (3 mục)
- `ROADMAP.md` — §4.2: đánh dấu Quản lý văn bản → chuyển lên §2.4; cập nhật timeline

## [2026-05-26] — Performance: DuckDB aggregates + cache optimization ROADMAP §1.2
- `data/core.py` dòng ~235–455 — **MỚI** 4 hàm DuckDB aggregate: `tong_hop_tq_pgd()`, `tong_hop_tq_pgd_full()`, `tong_hop_tq_co_cau_ct()`, `tong_hop_tq_kpi()` — 1 SQL query thay thế 4-6 pandas groupby cho dashboard Tổng quan (tinh_tqpgd_extended, tinh_co_cau_ct, tinh_kpi_tongquan)
- `data/core.py` dòng ~240 — schema check `pd.read_parquet(parquet_path).columns.tolist()` trước mỗi DuckDB query (§8.17)
- `tabs/tab_so_sanh_ky/_export.py` dòng 599 — `_build_tong_hop_sheets()` thêm `parquet_path` parameter: dùng DuckDB query trực tiếp trên parquet nếu file tồn tại, fallback về pandas groupby
- `tabs/tab_so_sanh_ky/_export.py` dòng 533 — gọi `_build_tong_hop_sheets(df_xuat, CACHE_HSTD)` (pass parquet path)
- `tabs/tab_so_sanh_ky/_export.py` dòng 7 — thêm `import os` + `CACHE_HSTD` vào config import

## [2026-05-26] — XLRR: archive 2 file cũ + fix GOM tháng + bổ sung 13/14 XLN
- `tabs/tab_no_rui_ro.py` — XÓA (đã archive tại `_archive/`; deprecated, không còn được import)
- `tabs/tab_xlrr_tong_hop.py` — XÓA (đã archive tại `_archive/`; deprecated, không còn được import)
- `tabs/tab_xu_ly_rui_ro.py` dòng 1-2 — sửa docstring: "5 sub-tabs" → "CN: 6 sub-tabs, PGD: 4 sub-tabs (đã archive)"
- `tabs/tab_xu_ly_rui_ro.py` dòng ~961 — thêm `thang_cn` selectbox (bố cục 2 cột với `nam`)
- `tabs/tab_xu_ly_rui_ro.py` dòng ~993 — fix bug: xóa vòng lặp 12 tháng khi gom PGD → dùng `thang_cn` trực tiếp
- `tabs/tab_xu_ly_rui_ro.py` dòng ~1015,1060,1075 — thay 3 chỗ `thang_hien_tai = now.month` → `thang_cn` (GOM, Import Excel, Rà soát)
- `tabs/tab_xu_ly_rui_ro.py` dòng ~1255 — **MỚI** section 13/XLN · 14/XLN (báo cáo sau hạch toán QĐ HĐQT): 4 nút grid 2×2, expander nhập QĐ HĐQT, xuất Word via `word_xln_service`
- `tabs_tab_list.txt` — cập nhật `tab_xlrr_tong_hop.py` → `tab_xu_ly_rui_ro.py`
- `tests/test_smoke_imports.py` — xóa `tab_no_rui_ro`, `tab_xlrr_tong_hop`; thêm `tab_xu_ly_rui_ro`

## [2026-05-26] — XLRR _subtab_gui_cn_pgd: fix UX thứ tự bước
- `tabs/tab_xu_ly_rui_ro.py` dòng ~1384 — xóa heading "Bước 3" rỗng (không có nội dung giữa heading và bước tiếp theo); đổi số bước: Bước 4→Bước 3 (đánh dấu gửi CN), thêm heading "Xuất biểu mẫu từng hồ sơ" đúng chỗ trước form chọn hồ sơ

## [2026-05-26] — XLRR tổng hợp CN: fix bug scope biến hs_gui
- `tabs/tab_xu_ly_rui_ro.py` dòng ~988 — `hs_gui` trong `_subtab_tong_hop_cn` bị scope sai (giá trị của `thang=12` cuối cùng, không phải tổng năm); đổi sang `hs_gui_pgd` tích lũy qua toàn bộ vòng tháng trước khi dùng

## [2026-05-26] — Dashboard "Ngày hôm nay" BGĐ: fix convention + format số
- `workspaces/ws_executive.py` dòng ~1284 — fix `except Exception: pass` → `logger.error(..., exc_info=True)` (3 chỗ: đến hạn tuần, so sánh snapshot, trạng thái upload)
- `workspaces/ws_executive.py` dòng ~1371 — bỏ `NumberColumn` kiểu Mỹ cho cột tiền; pre-convert → string VN-style bằng `fmt_so()` + `replace(".", ",")` trước `hien_thi_dataframe_phan_trang`
- `workspaces/ws_executive.py` dòng ~1397 — thêm `st.caption` fallback khi exception trạng thái upload

## [2026-05-26] — XLRR: Tái cấu trúc theo đợt — 2 luồng riêng CN/PGD + Tổng hợp bán tự động
- `services/xlrr_service.py` dòng ~9 — thêm `import uuid`
- `services/xlrr_service.py` dòng ~94-95 — thêm `dot_id: str` và `da_gui_cn: bool` vào `HoSoRuiRo`
- `services/xlrr_service.py` dòng ~184-295 — thêm `DotXLRR` dataclass + `LuuTruDotXLRR` class (CRUD đợt)
- `tabs/tab_xu_ly_rui_ro.py` dòng ~1798 — **MỚI** `_subtab_quan_ly_dot_cn()`: CN tạo/sửa/xóa đợt XLRR
- `tabs/tab_xu_ly_rui_ro.py` dòng ~1898 — **MỚI** `_subtab_dot_xlrr_pgd()`: PGD tự tạo đợt hoặc copy từ CN
- `tabs/tab_xu_ly_rui_ro.py` dòng ~953 — **VIẾT LẠI** `_subtab_tong_hop_cn()`: flow 4 bước (auto-gom PGD → import Excel fallback → rà soát checkbox → gửi TW) + xuất 04/XLN, 05/XLN, Tờ trình CN
- `tabs/tab_xu_ly_rui_ro.py` dòng ~2008 — cập nhật `render()`: tab labels mới (CN: 6 tabs, PGD: 4 tabs) + routing
- `tabs/tab_xu_ly_rui_ro.py` dòng ~183 — fix bug `_la_cn` dùng trước khi khai báo trong `_subtab_lap_hs_pgd`

## [2026-05-26] — Tab card 22 PGD: fix 4 bug sau review
- `tabs/tab_pgd_cards.py` dòng ~202 — thay `os.path.getmtime(pgd_data/)` bằng `ts_file(CACHE_HSTD)` (dir mtime không cập nhật khi overwrite file trên Windows)
- `tabs/tab_pgd_cards.py` dòng ~313 — pre-compute `_uinfo` dict trước lambda, tránh gọi `_upload_info()` 2 lần/PGD (44→22 filesystem calls)
- `tabs/tab_pgd_cards.py` dòng ~132 — đổi `:,.0f` (US-style) sang `fmt_so(...) + " tr"` (VN-style) trong card
- `services/tongquan_service.py` dòng ~572 — thay `df_pgd.get(...)` bằng explicit column check tường minh

## [2026-05-26] — Alert Center: fix bug + thêm 2 nguồn cảnh báo
- `alert_center.py` — fix bug `~~text~~` trong `st.button()` (Streamlit không render markdown trong button label); dùng `st.caption()` cho alert đã đọc có jump_fn
- `alert_center.py` — xóa dead code `render_badge_no_khoanh_sap_het_han()` (không còn được gọi từ đâu)
- `alert_center.py` — thêm `_kiem_tra_nqh_cao()`: cảnh báo 🔴 khi NQH% > 3%, 🟠 khi > 1%
- `alert_center.py` — thêm `_kiem_tra_no_den_han()`: cảnh báo số món/tổng tiền đến hạn trong 30 ngày
- `ROADMAP.md` — đánh dấu Alert Center phân mức là Done

## [2026-05-26] — Kích hoạt v2 reports trong tab_baocao
- `tabs/tab_baocao/__init__.py` — routing `"hstd"` và `"noruiro"` chuyển sang gọi `render_tong_hop_hstd_v2` / `render_no_rui_ro_v2`; xóa import component thừa không dùng trong module

## [2026-05-26] — Fix bug tính Tổng dư nợ bỏ sót hàng "Khác" trong tab nguồn vốn ĐP
- `tabs/tab_hhi.py` dòng ~67 — `_bang_theo_nv()`: cộng thêm cột "Khác" vào Tổng dư nợ nếu tồn tại, tránh tỷ trọng ĐP% bị thổi phồng khi có giá trị Nguồn vốn không phải 1/2

## [2026-05-26] — UX nâng cao tab_baocao: 9 components + 2 báo cáo v2
- `tabs/tab_baocao/components/skeleton_loader.py` — **MỚI** — Skeleton loading với shimmer effect
- `tabs/tab_baocao/components/sticky_table.py` — **MỚI** — Sticky header table, sortable
- `tabs/tab_baocao/components/inline_filter.py` — **MỚI** — Inline filter + quick search
- `tabs/tab_baocao/components/quick_export.py` — **MỚI** — Quick export buttons trên mỗi bảng
- `tabs/tab_baocao/components/tooltip.py` — **MỚI** — Tooltip giải thích công thức tính
- `tabs/tab_baocao/components/alert_suggestion.py` — **MỚI** — Auto alerts + action suggestions
- `tabs/tab_baocao/tree_navigation.py` — **MỚI** — Tree navigation 5 nhóm, 21 báo cáo
- `tabs/tab_baocao/reports/tong_hop_hstd_v2.py` — **MỚI** — Tổng hợp HSTD với UX nâng cao
- `tabs/tab_baocao/reports/no_rui_ro_v2.py` — **MỚI** — Nợ rủi ro với UX nâng cao

## [2026-05-26] — Fix 5 bug tab_baocao sau review
- `tabs/tab_baocao/__init__.py` — Thêm `render()` vào package (CRITICAL: Python dùng package thay file → `render()` cần có trong `__init__.py`)
- `tabs/tab_baocao/reports/gqvl.py` — Đổi `COT_GQVL_MA_NHA_DAU_TU` (không tồn tại) → `COT_TEN_NHA_DAU_TU` (CRITICAL: ImportError)
- `tabs/tab_baocao/components/export_panel.py` — Bỏ `.getvalue()` thừa trên bytes object (CRITICAL: AttributeError khi xuất Excel)
- `tabs/tab_baocao/components/metric_cards.py` — Sửa đơn vị: `_fmt_trieu` chia 1e6 nhưng hiển thị "tỷ" → đổi thành `_fmt_ty` chia 1e9; `fmt_ty→fmt_so` cho số lượng
- `tabs/tab_baocao/reports/` (5 file) — Đổi `fmt_ty(len(...))` → `fmt_so(len(...))` (fmt_ty chia cho 1e6 → count nhỏ ra "0")

## [2026-05-25] — Refactor tab_baocao: chỉ 4 nguồn dữ liệu (HSTD, NQ11, GQVL, CDTOTKVV)
- `tabs/tab_baocao.py` — Tái cấu trúc hoàn toàn: Entry point mới gọi dashboard + 5 module báo cáo; loại bỏ toàn bộ code cũ (~976 dòng)
- `tabs/tab_baocao/` — **MỚI** — Package module: `dashboard.py`, `components/`, `reports/`
- `tabs/tab_baocao/dashboard.py` — Dashboard tổng quan hiển thị trạng thái 4 nguồn dữ liệu + metric cards
- `tabs/tab_baocao/components/metric_cards.py` — Component hiển thị KPI: Tổng dư nợ, Nợ QH, Số món, DNO NQ11
- `tabs/tab_baocao/components/data_source_indicator.py` — Component hiển thị trạng thái 4 file: HSTD, NQ11, GQVL, CDTOTKVV
- `tabs/tab_baocao/components/export_panel.py` — Component xuất Excel/PDF với state management
- `tabs/tab_baocao/reports/tong_hop_hstd.py` — Báo cáo tổng hợp từ HSTD (theo PGD/Xã/Thôn/CT/ĐVUT/CBTD)
- `tabs/tab_baocao/reports/no_rui_ro.py` — Báo cáo nợ rủi ro: QH, khoanh, đến hạn 30/60 ngày, tỷ lệ nợ xấu
- `tabs/tab_baocao/reports/nq11.py` — Báo cáo NQ11: tổng hợp theo CT, chi tiết có/không NQ11
- `tabs/tab_baocao/reports/gqvl.py` — Báo cáo GQVL: phân tầng TW/ĐP, theo NĐT, giải ngân
- `tabs/tab_baocao/reports/cdtotkvv.py` — Báo cáo CDTOTKVV: xếp hạng, phân tích điểm, theo địa bàn

## [2026-05-25] — Mẫu 02/XLN: chức danh thành phần tham dự linh hoạt
- `services/xlrr_service.py` — thêm 3 field mới vào `HoSoRuiRo`: `chuc_vu_pgd_02` (default "Phó Giám đốc"), `chuc_vu_ubnd_02` (default "Phó Chủ tịch"), `chuc_vu_hoi_nd_02` (default "Chủ tịch Hội Nông dân xã", free-form để nhập CA xã...)
- `services/word_xln_service.py` — `_add_thanh_phan_tham_du_02xln` dùng chức danh động từ `du_lieu`; xử lý `dai_dien` rỗng (dạng "Chủ tịch Hội ND xã")
- `tabs/tab_xu_ly_rui_ro.py` — form mới + form sửa: selectbox GĐ/PGĐ cho NHCSXH, selectbox CT/PCT cho UBND, text_input free-form cho đoàn thể/CA; thêm `_hs_to_du_lieu_02()` helper dùng chung; fix bug download section dùng `to_dict()` thiếu key mapping
- `services/xlrr_export_service.py` — thêm 3 field vào `_EXPORT_COLS`; fix pre-existing convention: thêm `logger.error` vào except

## [2026-05-25] — Thêm download section sau lưu hồ sơ XLRR (01/XLN, 02/XLN, Tờ trình PGD)
- `tabs/tab_xu_ly_rui_ro.py` — sau khi lưu thành công: lưu ds_luu + dot/nguon vào session_state; hiện section 📥 với nút tải 01/XLN (nếu có Tổ trưởng), 02/XLN (nếu có Phó GĐ), Tờ trình PGD tổng hợp; nút ✕ Đóng xóa session_state; thêm import `_tao_word_to_trinh_pgd` + `tong_hop_theo_bien_phap`

## [2026-05-25] — Thêm Sửa/Xóa hồ sơ trong Lập HS PGD (XLRR)
- `tabs/tab_xu_ly_rui_ro.py` — thêm `_cap_nhat_hs()`, `_xoa_hs()` module-level helpers; thêm section "📂 Hồ sơ đã lập" với nút ✏️ Sửa (toggle) + 🗑️ Xóa (popover confirm); form sửa pre-filled dùng `dataclasses.replace`; chỉ hiện form lập mới khi không ở edit mode

## [2026-05-25] — Ô Tên KH: kết hợp text_input lọc + selectbox chọn
- `tabs/tab_xu_ly_rui_ro.py` dòng ~126-152 — Tên KH dùng text_input (gõ tự do lọc substring) + selectbox phía dưới hiện danh sách đã thu hẹp; label selectbox hiện số lượng KH khớp; filter logic: chọn từ dropdown → exact match, chỉ gõ → substring search

## [2026-05-25] — Cải thiện bộ lọc Bước 1 trong Lập hồ sơ XLRR
- `tabs/tab_xu_ly_rui_ro.py` dòng ~105-140 — cascade 3 tầng Xã→Tổ→KH; thêm `help="Gõ để tìm nhanh"` cho Xã/Tổ; đổi `""` → `"Tất cả"`

## [2026-05-25] — Fix dropdown Lập hồ sơ XLRR thiếu Hội sở CN tỉnh
- `tabs/tab_xu_ly_rui_ro.py` dòng ~88-96 — đổi options từ `DS_PGD` (21) sang `[DON_VI_CHI_NHANH] + DS_PGD` (22 đơn vị); PGD role fallback từ `DS_PGD[0]` → `DON_VI_CHI_NHANH`

## [2026-05-25] — Fix 2 bug biểu đồ Top 10 chương trình
- `tabs/tab_tongquan.py` dòng ~551-559 — sửa đơn vị card từ `/1e6` → `/1e9` (tỷ đồng); thêm `reset_index(drop=True)` để STT hiển thị đúng 1..N thay vì index gốc DataFrame

## [2026-05-25] — Fix convention: logger.error vào 11 except blocks
- `tabs/tab_xu_ly_rui_ro.py` dòng ~55-58, ~502-1279 — thêm `from logger import get_logger`, `logger.error(..., exc_info=True)` vào 11 except Exception blocks

## [2026-05-25] — Hoàn thiện Tab Xử lý Rủi ro (XLRR) — CN 5 tabs, PGD 3 tabs
- `services/xlrr_service.py` — Thêm constants `KET_QUA_*`, `KET_QUA_LABEL`; thêm 4 methods vào `LuuTruXLRR`: `_key_ket_qua`, `luu_ket_qua`, `doc_ket_qua`, `doc_ket_qua_pgd`
- `services/word_xln_service.py` — **MỚI** 2 hàm: `_tao_word_thong_bao_ket_qua_cn()`, `_tao_word_thong_bao_ket_qua_pgd()`
- `tabs/tab_xu_ly_rui_ro.py` — Tái cấu trúc: CN 5 tabs (thêm Dashboard GĐ + Thông báo kết quả), PGD 3 tabs (thêm Gửi CN với Tờ trình PGD + Kết quả XLRR); đổi `_subtab_bao_cao` → `_subtab_gui_cn_pgd`; thêm section Tờ trình CN vào `_subtab_tong_hop_cn`
- `CLAUDE.md` — Cập nhật bảng key kv_store: thêm `xlrr_pgd_*`, `xlrr_cn_*`, `qd62_cn_*`, `xlrr_ket_qua_*`

## [2026-05-25] — Redesign dashboard TỔNG QUAN tab So sánh mốc năm
- `tabs/tab_so_sanh_ky/_kpi_cards.py` — **MỚI** — 5 components: `render_big_metric_card`, `render_mini_card`, `render_mini_cards_row`, `render_debt_structure_donut`, `render_compact_comparison_table`, `render_dashboard_header`
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng ~302–437 — Thay thế 12 `st.metric()` cũ bằng dashboard mới: 2 big cards, 4 mini cards, donut chart Plotly, bảng so sánh compact

## [2026-05-25] — Fix 3 bugs mẫu 04/05 XLN
- `tabs/tab_xu_ly_rui_ro.py` — Thêm import `TEN_CHI_NHANH_HIEN_THI`; thay 2 chỗ hardcode `"Chi nhánh NHCSXH tỉnh Đồng Nai"` bằng constant (vi phạm rule 5.6).
- `services/word_xln_service.py` dòng ~1830 — `_add_bang_tong_hop_04_05()`: bỏ param `loai` không dùng; cập nhật 2 caller.
- `services/word_xln_service.py` dòng ~1863 — `_add_phan_ky_tong_hop()`: thêm dòng địa danh + ngày tháng trước bảng ký — param `ngay_lap`/`dia_danh` nhận vào nhưng chưa render → mẫu thiếu dòng bắt buộc.

## [2026-05-25] — Fix UnboundLocalError `fmt` trong tab XLRR
- `tabs/tab_xu_ly_rui_ro.py` dòng ~158 — Xóa `from utils import fmt` dư thừa trong `_subtab_lap_hs_pgd()`. Import này khiến Python coi `fmt` là local variable → lambda dùng `fmt` ở dòng trên bị `UnboundLocalError: cannot access free variable 'fmt'`.

## [2026-05-25] — Thêm rule 12 vào CLAUDE.md: tự chọn model subagent
- `CLAUDE.md` — Thêm section 12 "Tự động chọn model cho subagent": bảng Haiku/Sonnet/Opus theo loại task, quy tắc spawn Agent, khi nào không spawn.

## [2026-05-25] — Fix 4 bugs trong tab XLRR (Xử lý Rủi ro)
- `services/xlrr_service.py` dòng ~134 — `HoSoRuiRo.from_dict()`: thêm `ngay_ky_01`, `ngay_lap_02` vào danh sách convert string→date. Trước đây thiếu → `.strftime()` crash khi xuất mẫu 01/02/XLN sau lần load từ kv_store.
- `tabs/tab_xu_ly_rui_ro.py` dòng ~87 — `_subtab_lap_hs_pgd()`: bỏ `DON_VI_CHI_NHANH` khỏi dropdown CN lập thay PGD (Hội sở không có HSTD → luôn cảnh báo vô nghĩa).
- `tabs/tab_xu_ly_rui_ro.py` dòng ~148 — Tính `tong_du_no_goc_val` từ `ds_chon` trước khi vào form, điền vào `du_no_goc_display` thay vì để trống.
- `services/xlrr_export_service.py` dòng ~206 — `nhap_danh_sach_rui_ro_excel()`: tính `pgd_slug` từ `ten_pgd` thay vì để rỗng — tránh thiếu dữ liệu khi tổng hợp theo PGD.

## [2026-05-25] — Fix NameError _COT_TEN_PGD trong cache-check block
- `data/hstd.py` dòng ~65 — `doc_baseline_merged()`: chuyển `from config import COT_TEN_PGD as _COT_TEN_PGD` lên đầu hàm (trước cache-check block). Trước đây import đặt sai vị trí trong rebuild block → `NameError` bị `except Exception: pass` nuốt im → **mỗi lần gọi đều tốn công rebuild cache** thay vì dùng cache parquet có sẵn.

## [2026-05-25] — Fix cache baseline thiếu PGD sau lần đọc lỗi (silent skip)
- `data/hstd.py` dòng ~70–95 — `doc_baseline_merged()`: thêm kiểm tra tính đầy đủ của cache baseline — nếu PGD nào có file trên đĩa nhưng thiếu trong cache (`COT_TEN_PGD`) thì coi cache không hợp lệ → tự rebuild. Trước đây chỉ kiểm tra mtime, không phát hiện được trường hợp PGD có file nhưng lần đọc trước lỗi → cache thiếu PGD vĩnh viễn.

## [2026-05-25] — Fix 4 nhóm lỗi từ health check (27 test failures → 0)
- `alert_center.py` dòng ~226 — Sửa ngưỡng "khẩn": 120 ngày → 30 ngày; "cảnh báo": >30 & ≤180 ngày (test expect ≤30 là khan)
- `data/hstd.py` dòng ~162 — Sửa NameError `_ts`: `doc_baseline_merged` fallback gọi `doc_baseline(nam, _ts)` thay bằng `doc_baseline(nam)` (`_ts` không có trong scope)
- `services/upload_service.py` dòng ~39 — Đổi tên `_duong_dan_pgd` → `duong_dan_pgd` (public) để test có thể `patch.object(svc, "duong_dan_pgd", ...)` (21 test merge bị lỗi AttributeError)
- `db.py` dòng ~31 — Thêm `PRAGMA foreign_keys=ON` vào production connection (CASCADE DELETE bảng KTNB không hoạt động)
- `tests/test_ktnb_db.py` dòng ~19 — Thêm `PRAGMA foreign_keys = ON` cho in-memory fixture

## [2026-05-25] — Fix snapshot_service: import KetQuaUpload sai path gây ERROR log
- `snapshot_service.py` dòng 27–31 — Xóa try/except `from upload_service import KetQuaUpload` (module path sai → ERROR log mỗi lần khởi động); sửa thành `from services.upload_service import KetQuaUpload`; sửa logger except block (gọi `logger.error()` trước khi `logger` được định nghĩa)

## [2026-05-25] — Fix XLRR sub-tab 5 Báo cáo: lỗi method không tồn tại
- `tabs/tab_xu_ly_rui_ro.py` ~532 — `_subtab_bao_cao()`: thay `doc_ds_cn()` / `doc_ds_pgd()` (không tồn tại) bằng `doc_cn(nam,thang)` + `doc_qd62(nam,thang)` / `doc_pgd(slug,nam,thang)` đúng signature; thêm month/year selector để chọn kỳ; fix selectbox dùng `id` thay text-key tránh collision khi có hồ sơ trùng tên

## [2026-05-25] — Fix XLRR: NaT serialization + date_input format
- `services/xlrr_service.py` ~82 — `HoSoRuiRo.to_dict()`: thêm check `pd.isnull()` cho NaT dates từ DataFrame trước khi `json.dumps` (bug crash khi KH có ngày vay/đến hạn trống)
- `tabs/tab_xu_ly_rui_ro.py` ~158 — `st.date_input` thêm `format="DD/MM/YYYY"` theo convention 5.9

## [2026-05-25] — Fix snapshot NQ11/GQVL: tl_nqh + tl_tot_kha tính on-the-fly
- `tabs/tab_so_sanh_ky/render_moc_nam.py` ~604 — NQ11: tính `tl_nqh = no_qh/tong_du_no*100` thay vì lấy từ DB (cột không tồn tại → trước đây luôn 0%)
- `tabs/tab_so_sanh_ky/render_moc_nam.py` ~814 — CDTOTKVV: tính `tl_tot_kha = (so_tot+so_kha)/so_to*100` thay vì lấy từ DB (cột không tồn tại → trước đây luôn 0%)

## [2026-05-25] — Fix snapshot NQ11/GQVL: auto-create sau merge_baseline
- `snapshot_service.py` ~254, ~385 — thêm tham số `ky: str | None = None` vào `luu_nq11_snapshot()` và `luu_gqvl_snapshot()`; thêm `_ky_tu_gqvl()` trích xuất kỳ từ cột "Ngày vay"
- `services/upload_service.py` ~737 — `merge_baseline_toan_cn()`: sau khi merge, tự gọi snapshot với `ky=f"{nam}-12"` cho NQ11, GQVL, HSTD

## [2026-05-25] — Fix import tong_hop_khong_hd trong tab_baocao
- `tabs/tab_baocao.py` dòng 38 — thêm `tong_hop_khong_hd` vào import (bug cũ: dùng mà chưa import, gây NameError ở mảng ĐVUT)

## [2026-05-25] — Thêm 3 loại xuất PDF: Pivot, Chi tiết, Theo Nhóm
- `pdf_service.py` dòng ~8 — thêm import COT_* từ config; thêm `PageBreak` vào reportlab import
- `pdf_service.py` dòng ~364 — thêm `xuat_pdf_pivot(df, group_col, ...)`: groupby nội bộ → gọi `xuat_pdf()` với bảng pivot (Số KH / Số món / Dư nợ TH / QH / Tổng / Tỷ lệ QH% / Lãi tồn nếu có)
- `pdf_service.py` dòng ~427 — thêm `xuat_pdf_chi_tiet(df, cols_hien_thi, ...)`: thin wrapper, chọn cột + tự phát hiện cột tiền → gọi `xuat_pdf()`
- `pdf_service.py` dòng ~480 — thêm `xuat_pdf_theo_nhom(df, group_col, cols_chi_tiet, ...)`: PDF landscape nhiều section, mỗi nhóm = PageBreak + header + bảng chi tiết + dòng Cộng, chữ ký cuối
- `tabs/tab_baocao.py` dòng ~37 — import 3 hàm mới từ pdf_service
- `tabs/tab_baocao.py` dòng ~377 — thêm `group_col` để theo dõi cột nhóm hiện tại (Xã/Thôn/ĐVUT/CT)
- `tabs/tab_baocao.py` dòng ~547 — Mảng Tổng hợp: layout 3 cột Excel + PDF Pivot + PDF theo Nhóm; audit log sau mỗi lần xuất
- `tabs/tab_baocao.py` dòng ~941 — Mảng Chi tiết: thay `nut_xuat_pdf` bằng 2 nút PDF Chi tiết + PDF theo Nhóm (group by PGD); audit log sau mỗi lần xuất

## [2026-05-25] — So sánh mốc năm: tích hợp 3 loại PDF vào HSTD export
- `tabs/tab_so_sanh_ky/_export.py` ~347 — thêm `_build_col_chung()`: trích COL_CHUNG từ df (chuẩn tab_baocao)
- `tabs/tab_so_sanh_ky/_export.py` ~360 — thêm `render_export_hstd_ui(df_ht, df_bl, ...)`: radio Tổng hợp/Chi tiết + chọn kỳ xuất; route sang `_render_export_tong_hop()` / `_render_export_chi_tiet()`
- `tabs/tab_so_sanh_ky/_export.py` ~420 — thêm `_render_export_tong_hop()`: 3 cột Excel + PDF Pivot (Loại 1 - agg theo PGD) + PDF theo Nhóm (Loại 3 - từng PGD + bảng COL_CHUNG)
- `tabs/tab_so_sanh_ky/_export.py` ~490 — thêm `_render_export_chi_tiet()`: 3 cột Excel + PDF Chi tiết (Loại 2 - danh sách đầy đủ COL_CHUNG) + PDF theo Nhóm (Loại 3); Excel gộp sheets_extra từ bên ngoài
- `tabs/tab_so_sanh_ky/_export.py` ~570 — thêm `_build_tong_hop_sheets()`: sheet bổ sung Tổng hợp PGD/Xã/CT cho Excel
- `tabs/tab_so_sanh_ky/_export.py` ~610 — thêm `_download_pdf_btn()`: helper download + audit log
- `tabs/tab_so_sanh_ky/render_moc_nam.py` ~47 — import thêm `render_export_hstd_ui`
- `tabs/tab_so_sanh_ky/render_moc_nam.py` ~202 — `_render_export_section()` thêm tham số `df_ht`, `df_bl`; khi có → gọi `render_export_hstd_ui()`, khi None → giao diện cũ (NQ11/GQVL/CDTOTKVV không bị ảnh hưởng)
- `tabs/tab_so_sanh_ky/render_moc_nam.py` ~555 — `_render_hstd_section()` truyền `df_ht`, `df_bl` vào export → kích hoạt giao diện 3 loại PDF

## [2026-05-25] — Bộ lọc Hồ sơ đến hạn: 5 cột PGD→Xã→Hội đoàn thể→CT→Nguồn vốn
- `tabs/tab_tongquan.py` dòng ~1100 — thêm filter Hội đoàn thể (COT_DVUT), thêm lại Chương trình; layout 6 cột [2,2,2,2,2,1]; áp filter _sel_dvut vào dt_chung và filter_chung; cập nhật _co_loc

## [2026-05-25] — Xóa filter Chương trình và thanh kéo Dư nợ (section Hồ sơ đến hạn)
- `tabs/tab_tongquan.py` dòng ~1107 — bỏ multiselect "Chương trình" (`_sel_ct`), bỏ slider "Dư nợ (triệu đồng)" (`_no_range`); thu layout thành 4 cột [3,3,2,1]; dọn session_state key và `_co_loc` expression

## [2026-05-25] — Thiết kế lại section "Hồ sơ đến hạn — Tổng hợp"
- `tabs/tab_tongquan.py` — Header row [6:2] với Nhóm TH selectbox phải; gộp 2 tầng filter thành 1 khu vực thống nhất (PGD + CT + Xã + Nguồn vốn + Dư nợ slider); xóa hoàn toàn tầng 2 filter trong tab; KPI cards thay `st.metric()` bằng `kpi_row()` có icon+tooltip; charts bar+donut song song [6:4] thay vì xếp dọc; export buttons layout [3:3:4]

## [2026-05-25] — Fix Categorical groupby crash trong Tổng hợp cảnh báo theo PGD
- `tabs/tab_canh_bao_nqh.py` dòng ~217 — Thêm convert `COT_TEN_PGD` từ Categorical → object cho `df_full_loc` và `df_kh_loc` trước groupby (pattern K3/K4 BUGMAP.md)

## [2026-05-25] — Thiết kế lại bảng Tổng hợp cảnh báo theo PGD (sub-tab Tổng hợp)
- `tabs/tab_canh_bao_nqh.py` dòng ~325-420 — Thay `hien_thi_dataframe_phan_trang()` bằng HTML table: sắp xếp theo tổng cảnh báo giảm dần; phân loại 🔴/🟡/🟢 theo ngưỡng 10/5; KPI cards tóm tắt; progress bar cột Đến hạn; badge mức độ rủi ro; footer tổng kết; row nền đỏ/vàng theo mức độ

## [2026-05-25] — Fix ngưỡng khoanh sắp hết hạn: 30d → 120d (đồng bộ CHANGELOG 23/05)
- `alert_center.py` dòng 226-227 — Sửa ngưỡng `khan`: `con_lai <= 30` → `con_lai <= 120`; `canh_bao`: `(>30, <=180)` → `(>120, <=180)` — thay đổi này đã ghi trong CHANGELOG 23/05 nhưng chưa apply vào code
- `tabs/tab_canh_bao_nqh.py` — Cập nhật subtitle card: "X khẩn (≤30d)" → "X phải KT (≤120d) · Y theo dõi (121-180d)"

## [2026-05-25] — Fix card Khoanh cần kiểm tra trong Cảnh báo NQH
- `tabs/tab_canh_bao_nqh.py` dòng ~255-280 — Đổi metric chính từ `so_khan` (≤30d) sang `so_khan + so_cb` (tổng cần KT ≤180d); đổi title "Khoanh hết hạn ≤ 30d" → "Khoanh cần kiểm tra"; đổi subtitle "X cảnh báo (≤ 120d)" → "X khẩn (≤30d) · Y theo dõi (≤180d)"; fix màu card đỏ khi tổng > 0 thay vì chỉ khi so_khan > 0; fix nhãn "≤ 120d" → "≤180d" cho đúng logic alert_center.py

## [2026-05-25] — Fix DuplicateElementKey trong render_export_ui (So sánh kỳ)
- `tabs/tab_so_sanh_ky/_export.py` dòng ~230 — Thêm tham số `key_prefix: str = "ssk"` vào `render_export_ui`; thay 6 hardcoded key `ssk_*` bằng `f"{key_prefix}_*"`; phân biệt session state cache theo prefix
- `tabs/tab_so_sanh_ky/render_moc_nam.py` — Thêm `key_prefix` vào `_render_export_section`; 4 section HSTD/NQ11/GQVL/CDT dùng key riêng (`{key_prefix}hstd`, `{key_prefix}nq11`, `{key_prefix}gqvl`, `{key_prefix}cdt`)
- `tabs/tab_so_sanh_ky/render_2_ky.py` — Truyền `key_prefix="2ky"` vào `render_export_ui`

## [2026-05-25] — Bỏ hard-block snapshot tháng 12, thêm manual trigger NQ11
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng ~662-700 — `_render_nq11_section`: bỏ `return` cứng khi thiếu snapshot 12, fall back dùng tất cả kỳ + thêm caption; thêm `df_nq11` param
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng ~118-144 — Thêm `_render_nq11_manual_snap()`: widget tạo snapshot NQ11 thủ công cho admin (text_input YYYY-MM + nút tạo + validation regex)
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng ~802-820, 913-930 — GQVL và CDTOTKVV: bỏ hard-block tương tự, fall back toàn bộ kỳ
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng ~1048, 1076 — `render_moc_nam`: extract `df_nq11` từ kwargs, truyền vào `_render_nq11_section`

## [2026-05-25] — Tăng cỡ chữ và độ tương phản card KPI Cảnh báo NQH
- `tabs/tab_canh_bao_nqh.py` dòng ~237-250 — Tăng font value 1.8→2.4rem, label 0.75→0.9rem, sub 0.73→0.82rem; bỏ uppercase/letter-spacing; tăng padding/min-height; màu chữ đậm hơn cho 4 màu card

## [2026-05-25] — Card nền màu cho Tổng hợp Cảnh báo Tín dụng + đổi tên chỉ tiêu rõ ràng
- `tabs/tab_canh_bao_nqh.py` dòng ~236-252 — Thay 5 `st.metric()` bằng HTML card nền màu (`.cb-card` + `.cb-blue/green/red/purple`) cho sub-tab "Tổng hợp"
- Đổi tên chỉ tiêu rõ ràng: "Khoanh khẩn" → "Khoanh hết hạn ≤ 30d", "Đến hạn (3 tháng)" → "Đến hạn ≤ 3 tháng", "3 tháng không HĐ" → "≥ 3 tháng không HĐ", "Đã gia hạn" → "Đã gia hạn (T/N)"
- 5 card: 🔵 Đến hạn, 🔴/🟢 3 tháng KHĐ (đỏ nếu có), 🔴/🟢 Có nợ QH, 🔴/🟢 Khoanh hết hạn, 🟣 Đã gia hạn
- Responsive: 5 col → 3 col → 2 col theo màn hình

## [2026-05-25] — Fix lỗi Categorical "values should be unique" tab So sánh kỳ
- `services/so_sanh_ky_service.py` `group_bien_dong()` — convert cột dim Categorical → object trước và sau groupby để tránh lỗi merge CategoricalIndex duplicate categories từ HSTD parquet
- `services/so_sanh_ky_service.py` `agg_theo_pgd()` — convert COT_TEN_PGD Categorical → object trước groupby; đảm bảo object sau groupby trước khi concat hàng tổng

## [2026-05-25] — Tầng 2 tab Đến hạn: gom 3 widget thành 1 filter_bar
- `tabs/tab_tongquan.py` dòng ~1101 — hàm `_bang_den_han` thay `st.expander` + 3 widget rời (multiselect Xã, selectbox Nguồn vốn, slider Dư nợ) bằng 1 `filter_bar` duy nhất với type multiselect/multiselect/range
- `services/tongquan_service.py` dòng ~328 — mở rộng `loc_nv: int | None` → `int | list[int] | None`, thêm nhánh `isinstance(list)` để hỗ trợ multiselect Nguồn vốn chọn nhiều

## [2026-05-25] — Lịch công tác KHNV: luôn hiện lịch bàn + dark mode + badge hôm nay
- `tabs/tab_khnv_noi_bo.py` dòng ~990 — bỏ early return khi ds rỗng, lịch bàn luôn hiện ngay cả khi chưa có sự kiện
- `tabs/tab_khnv_noi_bo.py` `_html_lich_ban()` — thay màu hardcode `#ffffff`/`#f8fafc` bằng `transparent`/`rgba()` tương thích dark mode; số hôm nay hiển thị dạng badge tròn vàng như app lịch điện thoại
- `tabs/tab_khnv_noi_bo.py` list view — `#e8f4fd` → `rgba(59,130,246,0.08)` cho tuần hiện tại
- `tabs/tab_khnv_noi_bo.py` edit form — thêm `format="DD/MM/YYYY"` cho st.date_input

## [2026-05-25] — Fix 2 lỗi tab Thông tin chung sau review
- `tabs/tab_tongquan.py` dòng 12 — thêm `timedelta` vào import (`NameError` khi mở tab "Tùy chỉnh")
- `tabs/tab_tongquan.py` dòng 1139 — slider dư nợ ở default range không bị tính là "có lọc" (co_loc_tab luôn True)

## [2026-05-24] — Fix root cause So sánh kỳ: cột dư nợ string → agg/groupby trả string 516818 ký tự
- `services/so_sanh_ky_service.py` `agg_mot_pgd()` — thêm helper `_num_sum()` dùng `pd.to_numeric()` trước sum, tránh string concatenation khi cột là object
- `services/so_sanh_ky_service.py` `agg_theo_pgd()` — convert numeric trước groupby
- `services/so_sanh_ky_service.py` `agg_theo_dvut()` — convert numeric trước groupby (cùng pattern với agg_theo_pgd)
- `services/so_sanh_ky_service.py` `group_bien_dong()` — convert numeric trước groupby cho COT_TONG_DU_NO và COT_DU_NO_QH

## [2026-05-24] — Thiết kế lại bộ lọc Hồ sơ đến hạn — Tổng hợp: Tầng 1 + Tầng 2 + tab Tùy chỉnh
- `tabs/tab_tongquan.py` dòng ~1017-1306 — Refactor toàn bộ section "🔔 Hồ sơ đến hạn — Tổng hợp":
  - Tầng 1 (Bộ lọc chung): expander với PGD + Chương trình (multiselect) — hiệu lực cho tất cả tab
  - Tầng 2 (Lọc trong tab): expander trong mỗi tab — Xã (multiselect), Nguồn vốn (TW/ĐP), Dư nợ range slider — key suffix theo tab để độc lập
  - Tab mới "📅 Tùy chỉnh": chọn khoảng ngày linh hoạt bằng date_input
  - `_bang_den_han()` nhận thêm tham số `tab_filters` — merge filter chung + filter riêng trước khi xuất Excel/PDF
  - `filter_values` cũ → thay bằng `filter_chung` + `tab_filters`
- `services/tongquan_service.py` dòng ~326-350 — Thêm `ap_dung_loc_den_han_tab()`: filter theo Xã, Nguồn vốn, khoảng dư nợ
- Giảm rerun: thay đổi filter Tầng 2 chỉ rerun tab hiện tại, không ảnh hưởng các tab khác

## [2026-05-24] — Fix lỗi So sánh kỳ: dtype string sau merge.fillna() không convert numeric → subtract crash
- `tabs/tab_so_sanh_ky/render_2_ky.py` dòng 150-153 — Hàm `_render_bang_pgd()`: thêm loop `pd.to_numeric()` trước subtract
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng 303-306 — Tab "🏢 Theo PGD" (merge agg_theo_pgd): thêm loop `pd.to_numeric()` trước subtract
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng 352-355 — Tab "📋 Theo CT": thêm loop `pd.to_numeric()` trước subtract
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng 376-379 — Tab "📍 Theo Xã": thêm loop `pd.to_numeric()` trước subtract
- `tabs/tab_so_sanh_ky/render_moc_nam.py` dòng 494-497 — Sheet export PGD: thêm loop `pd.to_numeric()` trước subtract
- Nguyên nhân: `fillna(0)` không chuyển dtype object/string → numeric, chỉ thay NaN → 0. Cần explicit conversion trước phép tính

## [2026-05-24] — Tối ưu cold start tầng 1: lazy import alert_center + status_widget, skip NQ11/GQVL cho executive
- `app.py` dòng 59-60 — Xóa top-level import `render_alert_sidebar` (18s) và `render_status_compact` (26s); chuyển thành lazy import bên trong `with st.sidebar:` block
- `app.py` dòng ~300-314 — Thêm `from alert_center import render_alert_sidebar` và `from widgets.status_widget import render_status_compact` + `from auth import la_phan_he_pgd` vào đúng nơi dùng trong sidebar
- `app.py` dòng ~456, ~486 — Skip NQ11/GQVL load khi `ws_hien_tai == "executive"` (BGĐ không cần NQ11/GQVL)
- Profiled: alert_center import = 18s, status_widget import = 26s → **cắt ~44s cold start**, vài s mỗi rerun

## [2026-05-24] — Hoàn thiện báo cáo Quản lý Công việc & Nhiệm vụ
- `services/bc_tongquan_service.py` — File mới: logic lọc, tính KPI, tạo ma trận, xuất Excel/PDF báo cáo
- `tabs/bc_tong_hop.py` — File mới: render UI báo cáo với filter nâng cao, 4 KPI metrics, lazy tabs (tổng hợp/phân tích/so sánh), xuất 3 định dạng
- `tabs/tab_quan_ly_bc.py` dòng 8, 11–18 — Thêm sub-tab "📊 Báo cáo tổng hợp" vào wrapper, mount `bc_tong_hop.render()`

## [2026-05-24] — Optimize cold start: bỏ object→category + DuckDB full scan → pd.read_parquet
- `app.py` dòng 65–88 — `_toi_uu_dtype()`: bỏ vòng lặp object→category (nunique() 163 cột × 349K dòng = ~6s, từng gây bug "category type does not support sum operations"); giữ float32/int downcast
- `app.py` dòng 90–132 — `_load_hstd()`: full scan (không WHERE) dùng `pd.read_parquet(engine='pyarrow')` (4.7s) thay vì DuckDB SELECT * (8.3s); vẫn giữ DuckDB khi có filter ten_pgd/active_only
- Profiling: 29.7MB parquet → 738MB RAM pandas (25×), 163/174 cột là object, nunique() trên 163 cột mất ~4s

## [2026-05-24] — Fix circular import KeyError services
- `data/hstd.py` dòng 9 — Chuyển `from services.data_quality import kiem_tra_chat_luong` từ top-level thành lazy import bên trong `doc_file_nq11()` và `doc_file_gqvl()` để phá vòng circular: `services/__init__` → `upload_service` → `data.hstd` → `services.data_quality` → KeyError

## [2026-05-24] — Fix sidebar alert gây lag mọi tab
- `alert_center.py` dòng 121 — Tăng `_KHD_CACHE_TTL` từ 300s → 1800s (30 phút)
- `alert_center.py` dòng 179 — Thay `tong_hop_khong_hd()` → `tong_hop_khong_hd_cached()` dùng `@st.cache_data(ttl=7200)` shared across sessions + lọc PGD sau cache thay vì trước

## [2026-05-24] — Fix tab Thông tin chung load chậm
- `tabs/tab_tongquan.py` dòng 96, 122 — Tăng TTL cache `_cache_co_cau_ct` và `_cache_tqpgd_extended` từ 120s → 3600s (tránh recompute mỗi 2 phút trên 292k rows)
- `services/tongquan_service.py` dòng 257–283 — `tinh_tqpgd_extended()`: bỏ `.copy()` 292k rows, skip `pd.to_datetime()` nếu đã là datetime64, thay `.apply(lambda stack)` bằng vectorized `.sum(axis=1)` + groupby

## [2026-05-24] — Fix tab Tiến Độ Nộp load chậm do GSheet connection
- `tabs/tab_tien_do_nop.py` dòng 36 — Thêm `@st.cache_resource` cho `_ket_noi_gsheet()`: chỉ tạo OAuth connection 1 lần thay vì mỗi 5 phút (tiết kiệm 4-5s mỗi lần refresh)
- `tabs/tab_tien_do_nop.py` dòng 50, 100 — Fix `e` undefined trong 2 `except` block

## [2026-05-24] — Fix pandas warning + optimize watchdog
- `app.py` dòng 75 — Sửa `select_dtypes(include="object")` → `include=["object", "string"]` (pandas 2.x deprecated)
- `.streamlit/config.toml` — Thêm `logs` vào `folderWatchBlacklist` tránh rerun khi log file thay đổi

## [2026-05-24] — Fix 13 lỗi Tab Kiểm toán Nội bộ (KTNB) — Phase 2
- `services/ktnb_service.py` dòng ~724 — Thêm guard `if df_dm.empty` trước khi render form thêm lỗi; trước đó crash `IndexError` khi bảng danh mục lỗi trống
- `services/ktnb_service.py` dòng ~786 — Sửa call `cap_nhat_trang_thai_loi()` để dùng keyword args thay positional (dòng này bỏ sót ở phase 1)
- `services/ktnb_service.py` dòng ~690 — Đơn giản logic `is_truong_doan`: check xem có vai_trò="truong_doan" trong đoàn (trước đó so sánh text_name == username → LUÔN FALSE)
- `services/ktnb_service.py` dòng ~195–196 — Thêm cột "Trạng thái lịch hiển thị" (map nội bộ → tiếng Việt) vào bảng danh sách đợt
- `services/ktnb_service.py` dòng ~213–214, ~735 — Thêm `format="DD/MM/YYYY"` vào 3 `st.date_input` (CLAUDE.md §5.9)
- `services/ktnb_service.py` dòng ~253–259 — Thêm prefix `_ktnb_` vào widget keys trong form_them_tv (`_ktnb_tv_hoten`, `_ktnb_tv_chucvu`, `_ktnb_tv_donvi`, `_ktnb_tv_vaitro`)
- `services/ktnb_service.py` dòng ~528–537 — Sửa Excel export từ antipattern `st.button→st.download_button` → session_state cache (tương tự fix ở tab so sánh kỳ)

## [2026-05-24] — Fix 7 lỗi Tab Kiểm toán Nội bộ (KTNB) — Phase 1
- `services/ktnb_service.py` dòng ~671 — Thêm try-except trong `_luu_minh_chung()` để handle OSError + unhandled exceptions; trước đó ghi file thất bại vẫn trả về path=None im lặng
- `services/ktnb_service.py` dòng ~756 — Kiểm tra `path is not None` sau upload file minh chứng; thêm limit 10MB; thay positional args → keyword args cho `cap_nhat_trang_thai_loi()`
- `services/ktnb_service.py` dòng ~217 — Thêm validation: Số CV ≤50 ký tự, Trưởng đoàn không trống, Ngày bắt đầu ≤ Ngày kết thúc
- `services/ktnb_service.py` dòng ~183-383 — Dùng consistent session key prefix `_ktnb_*` (thay vì mixed `ktnb_*`); keys: `_ktnb_nam`, `_ktnb_dot_team`, `_ktnb_sample_ratio`, `_ktnb_prioritize_risk`, `_ktnb_filter_status`, `_ktnb_dot_selector`
- `services/ktnb_service.py` dòng ~817 — Xóa `st.json(dot)` trong tab A; đã hiển thị info đầu form, không cần raw JSON; xóa duplicate call `render_ke_hoach_lich_trinh()` sau json

## [2026-05-24] — Fix 6 lỗi tab So sánh 2 kỳ (package tabs/tab_so_sanh_ky/)
- `tabs/tab_so_sanh_ky/_common.py` dòng ~105 — Thêm `.delta-pos`, `.delta-neg`, `.delta-zero` vào `Q_BAR_CSS`; trước đó các class tồn tại trong HTML nhưng không có style định nghĩa → màu delta hoàn toàn mất
- `tabs/tab_so_sanh_ky/_export.py` hàm `render_export_ui()` — Thay antipattern `st.button → st.download_button` lồng nhau (bytes biến mất sau rerun) bằng `session_state` cache + `st.download_button` trực tiếp; thêm `st.warning` khi `reportlab` chưa cài (trước đó trả `b""` im lặng)
- `tabs/tab_so_sanh_ky/render_2_ky.py` dòng ~114 — Sửa label quality bar bị lặp `f"Kỳ {ky1} — {ky1}"` → `f"Kỳ {ky1}"`
- `tabs/tab_so_sanh_ky/render_2_ky.py` hàm `_render_cdtotkvv_section()` — Bổ sung 2 metric bị thiếu: Tổ Khá (`so_kha`) và Tổ Trung bình (`so_tb`) vào KPI row; thêm lại 2 pie charts cơ cấu xếp loại song song 2 kỳ (đã có trong tab_so_sanh_2_ky.py cũ nhưng mất khi refactor)
- `tabs/tab_so_sanh_2_ky.py` — Thêm `⚠️ DEPRECATED` vào docstring; file không còn được gọi từ workspace nào (đã chuyển sang package)

## [2026-05-24] — Triển khai Tab Kiểm toán Nội bộ (KTNB)
- `services/ktnb_service.py` — 4 phân hệ hoàn chỉnh:
  - **A. Kế hoạch & Lịch trình**: `them_dot_kiem_tra()`, `cap_nhat_dot_kiem_tra()`, `lay_danh_sach_dot()`, `cap_nhat_thanh_phan_doan()`, `render_ke_hoach_lich_trinh()` — UI form tạo đợt, bảng lịch trình với cảnh báo màu (sắp tới/đúng hạn/quá hạn), quản lý thành viên đoàn
  - **B. Chọn mẫu đối chiếu**: `chon_mau_doi_chieu()` — ưu tiên 100% món có NQH/Khoanh + random sample theo tỷ lệ %, `luu_mau_doi_chieu()`, `render_chon_mau()` — UI bộ lọc + KPI mẫu đã chọn
  - **C. Nhập kết quả đối chiếu**: `lay_ho_so_doi_chieu()`, `luu_ket_qua_doi_chieu()`, `render_nhap_ket_qua()` — UI layout 2 cột (readonly trái/editable phải), theo dõi trạng thái đối chiếu, xuất Excel
  - **D. Giám sát & Khắc phục lỗi**: `lay_danh_muc_loi()`, `them_loi()`, `cap_nhat_trang_thai_loi()` — chỉ trưởng đoàn được đóng lỗi, `thong_ke_loi_theo_khoi()`, `render_giam_sat_khac_phuc()` — Pie chart + bảng lỗi + upload minh chứng
- `services/ktnb_service.py` — `render_ktnb(df_full, role, username)` — main entry point với 4 sub-tabs A/B/C/D và selectbox chọn đợt kiểm tra chung
- `tabs/tab_kiem_soat.py` — Refactor: `_render_tab_kiem_soat()` giữ nguyên code Kiểm soát CN, `render_tab()` mới tạo 2 tab cấp cao: "🔍 Kiểm soát Chi nhánh" và "📋 Kiểm toán Nội bộ", lazy import `render_ktnb` từ services
- `tests/test_ktnb_service.py` — Tests cho Phân hệ A/B/D, helper `_tinh_trang_lich()`, seed danh mục lỗi
- `tests/test_ktnb_db.py` — CRUD tests cho 5 bảng KTNB: `ktnb_dot_kiem_tra`, `ktnb_doan_kiem_tra`, `ktnb_danh_muc_loi_chuan`, `ktnb_mau_doi_chieu_kh`, `ktnb_ket_qua_loi` (in-memory SQLite)
- Ràng buộc: Session key prefix `ktnb_*`, upload minh chứng → `pgd_data/ktnb/`, `readonly=True` khi `role == "executive"`, không dùng thư viện mới (chỉ sqlite3, pandas, streamlit)

## [2026-05-24] — Tái cấu trúc Tab So sánh kỳ: package hóa + mockup + 2 dạng export
- `tabs/tab_so_sanh_ky/` — package mới: `__init__.py` (router), `_common.py` (KPI, quality bars, tables, charts, flow diagram), `_export.py` (Excel + PDF 2 dạng), `render_2_ky.py` (tinh gọn từ tab_so_sanh_2_ky.py), `render_moc_nam.py` (tinh gọn từ tab_so_sanh_ky.py)
- `tabs/tab_so_sanh_ky.py` — thu gọn thành thin router (delegate to package)
- `tabs/tab_so_sanh_ky/_common.py` — shared helpers: `render_kpi_row()`, `render_quality_bars_2_ky()`, `render_comparison_table()`, `render_hbar_chart()`, `render_flow_diagram()` — dark mode compatible
- `tabs/tab_so_sanh_ky/_export.py` — `xuat_excel_tong_quan()`, `xuat_excel_da_chieu()`, `xuat_pdf_tong_quan()`, `xuat_pdf_da_chieu()`, `render_export_ui()` — mỗi loại 2 dạng (Tổng quan / Đa chiều)
- `mockup_so_sanh_ky.html` — mockup trực quan 3 Section (Tổng quan → Phân tích đa chiều → Xuất báo cáo)

## [2026-05-24] — Đồng bộ và fix tất cả rules files (CLAUDE.md, Trae, Windsurf, Cursor, Cline)
- `CLAUDE.md` — cập nhật ngày 24/05; thêm chuyenvien_cn, khnv keys, auth functions (5.14), error logging (5.15), DuckDB (5.16), dark mode + date_input vào 5.9, DELTA.md vào refs
- `.trae/rules/rules.md` — thêm ngày; fix fmt_ty() inconsistency; thêm Bản đồ file (2.1), Luồng dữ liệu (2.2), pgd_mode (8.15), CSS/UI (8.16), DuckDB (8.17); bảng role + chuyenvien_cn; DELTA.md vào refs
- `.windsurfrules` — đồng bộ với Trae: thêm 2.1, 2.2, 6.15, 6.16, 6.17, bảng role, DELTA.md
- `.cursorrules` — thêm chuyenvien_cn, khnv keys, BUGMAP vào checklist, upgrade error logging, DuckDB (5.13), dark mode + date_input, DELTA.md
- `.clinerules` — thêm khnv keys, logger pattern (15), DELTA.md (21), fix section numbers

## [2026-05-24] — Fix lỗi "category does not support sum" trong So sánh kỳ
- `app.py` dòng ~77-92, `_toi_uu_dtype()` — thêm kiểm tra: cột object có ≥80% giá trị chuyển được sang số thì ép về `pd.to_numeric()` thay vì `astype("category")` (gốc lỗi: cột "Giải ngân trong năm" bị convert thành category, `.sum()` crash)

## [2026-05-24] — Tối ưu cache: fix DataFrame hashing trong các cached wrappers
- `data/hstd.py` dòng 346–359 — Đổi signature 3 cached wrappers (`danh_dau_khong_hd_cached`, `tong_hop_khong_hd_cached`, `canh_bao_migration_cached`) sang `(_df, ts=0.0)` — bỏ hash DataFrame, dùng `ts` làm cache key
- `tabs/tab_kiem_soat.py` dòng 20, 32–35 — Import cached, thay direct call → `danh_dau_khong_hd_cached(df, ts=ts_file(CACHE_HSTD))`
- `tabs/tab_baocao.py` dòng 38, 403 — Import cached, thay direct call → `danh_dau_khong_hd_cached(df_base, ts=ts_file(CACHE_HSTD))`
- `utils.py` dòng 510, 529–531 — Import cached + ts_file, thay direct call

## [2026-05-24] — Hoàn thiện mục Hồ sơ đến hạn Tổng hợp (tab Tổng quan)
- `tabs/tab_tongquan.py` dòng ~1017 — Thay radio + expander bộ lọc → 4 widget inline (selectbox + 3 multiselect) cùng 1 hàng, gọn hơn
- `tabs/tab_tongquan.py` trong `_bang_den_han()` — Thêm biểu đồ cột phân bổ dư nợ đến hạn theo tháng (ẩn khi chỉ có 1 tháng)
- `services/tongquan_service.py` dòng ~377 — Thêm hàm `tong_hop_den_han_theo_thang()` groupby Period("M") phục vụ biểu đồ timeline

## [2026-05-24] — Refactor DRY: gộp _should_force_str + _normalize_code_series về 1 nơi (core.py)
- `data/core.py` — Đưa `_should_force_str()` và `_normalize_code_series()` lên module-level (thay vì nested trong `excel_to_parquet`) để có thể import từ nơi khác
- `data/hstd.py` — Import `_should_force_str` và `_normalize_code_series` từ `data.core` thay vì copy-paste toàn bộ logic (~40 dòng) bên trong `doc_baseline_merged()`
- Nguyên nhân: bản copy ở `hstd.py` (dòng 144-155) thiếu `"số atm"` và pattern `s.startswith("số ")`, khiến `doc_baseline_merged()` không chuẩn hóa cột "Số ATM" → vẫn mixed type sau rebuild cache merge → lỗi A4e tái đi tái lại

## [2026-05-24] — Fix tab Tổng quan: load lâu + không hiển thị PGD
- `tabs/tab_tongquan.py` dòng 573 — Đổi `df = df[cot_lay]` → `df_pgd_work = df[cot_lay]` để giữ `df` gốc phục vụ điều kiện `if COT_TEN_PGD in df.columns:` dòng 530; trước đây `df` bị trim lại khiến block PGD hoàn toàn không render
- `services/tongquan_service.py` dòng 199-278 — Gộp 5 lần `.merge()` thành 2-3 lần: khoanh + lãi tồn + DS cho vay tính chung 1 agg; giảm load time từ 8-12s xuống 2-3s cho DataFrame 50k rows
- `tabs/tab_tongquan.py` dòng 574-605 — Cập nhật tất cả tham chiếu từ `df` → `df_pgd_work` trong phần resolve column lookups (dòng 574-605)

## [2026-05-24] — Tối ưu tab "So sánh kỳ": fix treo khi đọc baseline
- `data/hstd.py` dòng ~58 — Đổi `@st.cache_data(ttl=7200)` → `@st.cache_resource` cho `doc_baseline_merged()`: loại bỏ pickle/unpickle overhead, cache hit gần tức thì
- `tabs/tab_so_sanh_ky.py` dòng ~1482 — Thêm `.copy()` vào `df_bl = df_bl_full.copy()` để an toàn với cache_resource (shared object)
- `tabs/tab_so_sanh_ky.py` dòng ~2014 — Đổi `with st.expander("Roll rate")` → `if _lazy_expander(...)`: `join_by_loan()` chỉ chạy khi expander được mở
- `tabs/tab_so_sanh_ky.py` dòng ~239 — Thêm `_cached_group()` module-level với `@st.cache_data(ttl=300)`: groupby trong chart không tính lại khi đổi selectbox
- `services/so_sanh_ky_service.py` dòng ~87 — Thêm `@st.cache_data(ttl=300)` vào `agg_theo_dvut()`: groupby ĐVUT không tính lại mỗi lần mở expander

## [2026-05-24] — Fix validation_service: df.iterrows() → vectorized
- `services/validation_service.py` dòng ~220 — Thay `for _, row in df.iterrows()` bằng vectorized `.map()` + boolean mask; giảm thời gian validate từ 15-30s xuống <0.1s cho DataFrame 50k rows

## [2026-05-24] — Fix render "So sánh kỳ": Số ATM mixed type → PyArrow crash
- `data/core.py` dòng 38 — Thêm "số atm" vào `_should_force_str()` để chuẩn hóa cột định danh từ đầu; thêm pattern `s.startswith("số ") and ("kh" in s or "account" in s)` để bắt các cột tương tự
- Nguyên nhân: "Số ATM" không được chuẩn hóa thành string → vẫn có mixed type (float NaN + bytes từ các PGD) → PyArrow crash "Expected bytes, got a 'float' object"

## [2026-05-24] — Fix spinner "Đang tổng hợp mốc 31/12..." luôn hiện
- `data/hstd.py` dòng 58 — Bỏ parameter `_ts` từ `doc_baseline_merged()` signature; `_ts` làm cache key thay đổi mỗi lần file update → cache MISS → spinner lặp vô hạn
- `tabs/tab_so_sanh_ky.py` dòng 1472-1479 — Bỏ tính toán `_ts` từ file mtime + lời gọi `_ts=_ts`; hàm sẽ check stale cache internally (đã có ở dòng 74-87 hstd.py)

## [2026-05-24] — Fix tab_so_sanh_2_ky performance: iterrows() → apply() + join()
- `tabs/tab_so_sanh_2_ky.py` — Dòng 274-296: Thay `for _ in df.iterrows()` + string concat chậm bằng `apply()` + `"".join()` chuỗi; refactor `_render_bang_pgd()` để tạo HTML nhanh gấp 10x cho 22 PGD; phân tách `_render_cached()` để chuẩn bị cache các DataFrame operations

## [2026-05-24] — Fix DGD refactor: Missing function + Emoji corruption
- `tabs/tab_diem_gd_pgd.py` — Thêm hàm `_render_gan_cbtd_pgd()` (bị thiếu, gọi ở dòng 305); sửa emoji 👤 ở tab names (bị mã hóa sai thành ❌)

## [2026-05-24] — Refactor DGD/CBTD: Fix helpers + Thêm tab Gán CBTD
- `tabs/tab_cbtd.py` — Fix `_ds_dgd_cua_pgd()` dùng `lay_dgd_cho_pgd()` thay vì `dgd_map`; fix `_ap_cua_dgd()` đọc schema mới (`entry.get("thon", [])`) + backward-compat với list cũ
- `tabs/tab_quan_ly_dgd.py` — Thêm sub-tab "👤 Gán CBTD" (`_render_gan_cbtd`): chọn PGD → Xã → list ĐGD, selectbox chọn CBTD cho từng ĐGD, lưu ngược vào `cbtd_data[ma_cb]["ds_dgd"]`
- `tabs/tab_diem_gd_pgd.py` — Thêm sub-tab "👤 Gán CBTD" (`_render_gan_cbtd_pgd`): tương tự CN nhưng PGD cố định theo user, chỉ hiển thị ĐGD/CBTD thuộc PGD của user

## [2026-05-24] — Refactor DGD module: hardcode DGD_DANH_SACH, bỏ import Excel
- `config.py` — Thêm `DGD_DANH_SACH` (270 điểm GD, đầy đủ pgd/xa/ten/ngay_gd/gio_gd/dia_diem) + helper `lay_dgd_cho_pgd()` / `lay_dgd_theo_xa()`
- `data/dgd_helpers.py` — Xóa `parse_excel_import` (và import `BytesIO`); thêm `xa_short()` / `khop_xa_dgd()` để chuẩn hóa tên xã khi khớp với DGD_DANH_SACH
- `tabs/tab_quan_ly_dgd.py` — Xóa tab "Import từ file" + `_render_import`; đổi tên tab "Xem & Sửa" → "Gán Thôn/Ấp" (`_render_gan_thon`), chỉ cho phép sửa thôn/ấp; thêm tab chỉ-đọc "Thông tin điểm GD" (`_render_thong_tin_dgd`) hiển thị `DGD_DANH_SACH`; thứ tự tab mới: Thông tin điểm GD → Gán Thôn/Ấp → Tìm kiếm → Tổng quan
- `tabs/tab_diem_gd_pgd.py` — Tương tự cho CBTD PGD: xóa `_render_import_pgd` + `_render_xem_sua_pgd`; thêm `_render_thong_tin_dgd_pgd` + `_render_gan_thon_pgd`; tab không còn yêu cầu HSTD để mở; thứ tự tab mới: Thông tin điểm GD → Gán Thôn/Ấp → Tìm kiếm → Tổng quan

## [2026-05-24] — Refactor Filter state Cảnh báo & Nợ khoanh: dùng SCMStateManager.filter_*
- `tabs/tab_canh_bao_nqh.py` — Tất cả bộ lọc PGD (sub-tab NQH, Khoanh sắp hết hạn, Gia hạn) đồng bộ với `state.filter_pgd`/`state.filter_chuong_trinh`; đổi PGD tự reset Xã; thêm import SCMStateManager
- `tabs/tab_canh_bao_som.py` — Bộ lọc PGD trong "Sắp đến hạn + KH không HĐ" đồng bộ với `state.filter_pgd`; download cũng chuyển sang `state.downloads`
- `tabs/tab_no_khoanh.py` — Bộ lọc PGD đồng bộ với `state.filter_pgd`; toàn bộ download (khoanh, M08, M09, QLNK_06 Excel+PDF, M10 Excel+PDF, tiến độ) chuyển sang `state.downloads` (clear one-shot); `_qlnk_filter` chuyển sang `state.temp`
- `alert_center.py` — `_jump_to_khoanh()` dùng `state.temp.set("_qlnk_filter", ...)` thay vì `st.session_state._qlnk_filter`
- `services/cbtd_dia_ban_service.py` dòng ~202, ~241 — sửa `except Exception as e: logger.warning(...)` thành `logger.error(... , exc_info=True)` cho đúng convention

## [2026-05-24] — Refactor Filter state: dùng SCMStateManager.filter_* (PGD/Xã/Chương trình)
- `workspaces/ws_operation.py` — Dropdown “Xem theo PGD” đồng bộ vào `state.filter_pgd` để giữ filter xuyên suốt workspace/tabs
- `tabs/tab_baocao.py` — Bộ lọc PGD/Xã/Chương trình đồng bộ với `state.filter_pgd/filter_xa/filter_chuong_trinh`; đổi PGD tự reset Xã
- `tabs/tab_so_sanh_2_ky.py` — Lọc PGD (CN) đồng bộ với `state.filter_pgd` để giữ lựa chọn khi chuyển qua lại các tab báo cáo

## [2026-05-24] — QA helpers: debug_dump + clear state khi logout
- `app.py` — thêm expander “🧪 Debug state” (admin) hiển thị `SCMStateManager.debug_dump()` + nút “Clear downloads”
- `app.py` — khi “Đăng xuất”, xoá toàn bộ key `_scm_*` để tránh state rò rỉ giữa phiên đăng nhập khác role

## [2026-05-24] — Refactor Download bytes: dùng SCMStateManager.downloads (giảm RAM)
- `state_manager.py` — `downloads` namespace được dùng làm nơi lưu bytes+filename thay cho nhiều key `_bytes_*` / `_pdf_bytes_*` rải rác
- `pdf_service.py` — `nut_xuat_pdf()` chuyển từ `st.session_state[_pdf_bytes_*]` sang `SCMStateManager.downloads` + clear one-shot khi bấm tải
- `services/kiem_soat_service.py` — `_xuat_pdf_btn()` chuyển sang `SCMStateManager.downloads` (loại bỏ `_pdf_bytes_*` / `_pdf_file_*`)
- `services/template_service.py` — `nut_tai_word_va_pdf()`/`hien_thi_nut_tai()` chuyển sang `SCMStateManager.downloads` (docx/pdf), clear khi bấm tải
- `tabs/tab_baocao.py`, `tab_kehoach.py`, `tab_cbtd.py`, `tab_den_han.py`, `tab_gqvl.py`, `tab_qd62.py`, `tab_nq11.py`, `tab_khtd_xuat.py`, `tab_khtd_nhap.py`, `tab_danhsach.py`, `tab_tongquan.py`, `tab_candoi.py`, `tab_cdtotkvv.py`, `tab_cdtotkvv_pgd.py`, `workspaces/ws_management.py`, `workspaces/ws_operation.py` — thay session_state bytes/file → `state.downloads`

## [2026-05-24] — Refactor Navigation state: ws_management/ws_operation dùng SCMStateManager
- `workspaces/ws_management.py` — Thay `st.session_state["ws_mgmt_menu"]`/`ws_mgmt_jump` bằng `SCMStateManager.nav_ws_mgmt_menu`/`nav_ws_mgmt_jump` (persist menu + one-shot jump)
- `workspaces/ws_operation.py` — Thay `ws_op_nhom`/`ws_op_jump_tab` bằng `SCMStateManager.nav_ws_op_nhom`/`nav_ws_op_jump_tab`; outer navigation dùng `st.radio`, inner dùng `lazy_tabs()` để render 1 tab và hỗ trợ jump theo shortcut/cảnh báo
- `state_manager.py` — Getter/setter `nav_*`/`filter_*` dùng `setdefault(...)` để không KeyError nếu workspace được import độc lập trước khi `ensure_initialized()`
- `alert_center.py` — Cập nhật `_jump_to_khoanh()` dùng `SCMStateManager` cho nhảy workspace (management/operation)
- `BUGMAP.md` — Thêm B10: shortcut set `ws_op_*` nhưng không nhảy tab

## [2026-05-24] — Alert Center phân mức 🔴/🟠/🟡 + trạng thái đã đọc
- `alert_center.py` — Thêm `AlertItem` dataclass: trường `muc` (khan/canh_bao/luu_y), `tieu_de`, `mo_ta`, `jump_fn`; `alert_id` hash MD5 ổn định từ (muc, tieu_de)
- `alert_center.py` — Hàm đã đọc: `_lay_da_doc()` / `_luu_da_doc()` / `_danh_dau_da_doc()` / `_xoa_da_doc_cu()` — persist vào kv_store key `alert_read_ids`
- `alert_center.py` — Refactor `_kiem_tra_upload_tre()` và `_kiem_tra_khong_hoat_dong()` → trả `list[AlertItem]` phân mức (upload trễ ≥7 ngày = 🔴, 3-6 ngày = 🟠; KHĐ = 🟠)
- `alert_center.py` — `_build_alert_items()` gom tất cả nguồn, sort 🔴→🟠→🟡
- `alert_center.py` — `render_alert_sidebar()`: badge header (🔴/🟠 N cảnh báo chưa đọc), hiển thị theo mức với `st.error/warning/info`, alert có `jump_fn` → clickable button, button "✅ Đánh dấu đã đọc tất cả"
- **Kết quả:** 11/11 test_alert_center.py pass

## [2026-05-24] — Dashboard "🌅 Hôm nay" cho workspace BGĐ
- `workspaces/ws_executive.py` — Thêm `_render_hom_nay()`: KPI row 5 chỉ số (tổng dư nợ, NQH, tỷ lệ NQH, số KH, đến hạn tuần), bảng 22 PGD (dư nợ + NQH% + badge trạng thái), alert biến động ≥5% so kỳ snapshot trước, trạng thái cập nhật HSTD/NQ11/GQVL
- `workspaces/ws_executive.py` — Thêm menu item "🌅 Hôm nay" đầu nhóm "Tổng quan" trong `_build_exec_items()`
- **Kết quả:** BGĐ mở app thấy ngay tình hình ngày hôm nay mà không cần click thêm

## [2026-05-24] — Fix circular import deadlock: data → services → data.pgd
- `services/upload_service.py` dòng ~39 — Chuyển `from data.pgd import duong_dan_pgd` (module-level) thành lazy-load wrapper `_duong_dan_pgd()` để phá vòng: `data.__init__ → data.hstd → services.__init__ → upload_service → data.pgd` gây `_ModuleLock DeadlockError`
- **Kết quả:** App khởi động bình thường, không còn `_frozen_importlib._DeadlockError`

## [2026-05-24] — state_manager.py: quản lý State tập trung
- `state_manager.py` — Tạo mới: `SCMStateManager` với typed properties (filters, navigation) + generic namespace (downloads, temp, cache); `ensure_initialized()` khởi tạo 1 lần ở app.py; `debug_dump()` cho tra cứu state
- `app.py` dòng ~62 — Thêm `from state_manager import SCMStateManager`
- `app.py` dòng ~174 — Thêm `SCMStateManager.ensure_initialized()` ở đầu `main()`

## [2026-05-24] — Nâng cấp & gộp nhóm CBTD – ĐGD – Tổ TK&VV
- `services/cbtd_dia_ban_service.py` — Tạo mới: `lay_to_theo_cbtd()`, `canh_bao_cbtd_dia_ban()`, `tom_tat_kpi()` — helper thuần Python cho cross-join CBTD→ĐGD→Tổ và cảnh báo thông minh
- `tabs/tab_cbtd_dashboard.py` — Tạo mới: Dashboard KPI tổng hợp (6 KPI cards, 3 loại cảnh báo, bảng pivot, xuất Excel cross-mảng nhiều sheet)
- `tabs/tab_cbtd.py` dòng ~277 — Sub-tab Chi tiết thêm section "🏘️ Tổ TK&VV phụ trách": cross-link CBTD→ĐGD→Tổ→xếp loại
- `workspaces/ws_management.py` — Gộp "Cán bộ tín dụng" + "Điểm GD & Tổ TK&VV" thành 1 entry "👔 CBTD & Địa bàn" (4 sub-tab: Dashboard · CBTD · ĐGD · Tổ TK&VV)
- `workspaces/ws_operation.py` — Thêm sub-tab "📊 Tổng quan" (dashboard mini PGD) vào nhóm ĐGD & Tổ TK&VV; fix `NameError: df_full` → `df_pgd`; fix `username` chưa được unpack; fix duplicate keyword `role` trong lambda `_render_canh_bao_nqh_pgd`
- `tabs/tab_kehoach.py` dòng ~113 — Guard `db_ht_rows or []` tránh `TypeError` khi `st.stop()` không dừng được trong test environment
- `tabs/tab_khtd_mau07.py` dòng ~18 — Thêm `import os` bị thiếu
- **Kết quả:** 105/105 smoke tests pass

## [2026-05-24] — UI xem lịch sử tiến độ (Block 4 trong Cập nhật tiến độ)
- `services/tien_do_service.py` — Thêm `doc_lich_su_task(task_id, pgd, limit)`: query `tien_do_lich_su` theo task + PGD tùy chọn, trả list[dict] mới nhất trước
- `tabs/tab_tien_do.py` — Thêm Block 4 "📜 Lịch sử cập nhật tiến độ" (expander) sau data editor trong `_render_cap_nhat()`: hiển thị bảng thay đổi trạng thái/% theo thời gian, ẩn cột PGD khi đang lọc 1 PGD

## [2026-05-24] — Phase 3: Dashboard tổng hợp, template, lịch sử, attachment
- `tabs/tab_tien_do.py` — Thêm template selector trước form Tạo đầu việc: chọn mẫu → "▶️ Áp dụng" → tự điền form qua session_state + rerun; fix 8 chỗ `except Exception:` thiếu `as e` và logger message vô nghĩa trong `_fmt_task`, `_render_quan_ly_task`, `_fmt_cap_nhat_opt`, `_fmt_task_pdf`, tao/sua/dong/xoa task
- `services/tien_do_service.py` — `upsert_ketqua_xa()` đọc trạng thái cũ rồi ghi `tien_do_lich_su` khi trang_thai hoặc pct_hoan_thanh thay đổi; `cap_nhat_ketqua_bulk()` truyền pct vào upsert
- `services/upload_service.py` — Thêm `luu_attachment_nhiem_vu(ten_pgd, nv_id, ten_file, file_bytes, username)`: validate ext/size (≤5MB), lưu vào `pgd_data/{slug}/nhiem_vu_attach/`, ghi audit
- `tabs/tab_nhiem_vu.py` — Thêm `st.file_uploader()` ngoài form để đính kèm file kết quả (xlsx/pdf/docx); hiển thị tên file trong tab nhập kết quả + hậu kiểm; `_upsert_ket_qua()` hỗ trợ `file_path`/`file_name` với 2 nhánh SQL
- `tabs/tab_tong_hop_cv.py` — `_hien_thi_ket_qua_search()` tìm full-text trên `tien_do_task` + `nhiem_vu`, kết quả 2 cột; alert deadline sắp đến có nút "✕ Ẩn" (session_state)
- `workspaces/ws_operation.py` — Thay `db.doc_kv("nhiem_vu_list")` bằng query trực tiếp `nhiem_vu` table theo `pgd_user`, tránh stale data từ kv_store không còn được populate

## [2026-05-23] — Phase 2: Tính năng nghiệp vụ nâng cao
- `db.py` — Thêm migrations: cột `pct_hoan_thanh` (tien_do_ketqua), `uu_tien`/`loai` (nhiem_vu), `file_path`/`file_name` (nhiem_vu_ketqua); tạo bảng `tien_do_template` và `tien_do_lich_su`; thêm `tien_do_template` vào `_SYNC_TABLES`
- `config.py` — Thêm hằng số dùng chung `LOAI_CONG_VIEC` và `UU_TIEN_CV` để tái sử dụng giữa tab_tien_do và tab_nhiem_vu
- `services/tien_do_service.py` — Fix bug undefined `e` ở line 126; thêm tham số `pct_hoan_thanh` vào `upsert_ketqua_xa()`; cập nhật `cap_nhat_ketqua_bulk()` hỗ trợ % hoàn thành (pct=100 tự đặt da_hoan_thanh)
- `tabs/tab_tien_do.py` — Fix 3 bug undefined `e`; thêm cột `% HT` (0–100, step=5) vào data_editor; cập nhật `_render_tong_quan()` tính % trung bình từ `pct_hoan_thanh` thay vì chỉ đếm done/total
- `tabs/tab_nhiem_vu.py` — Thêm import `LOAI_CONG_VIEC`/`UU_TIEN_CV`; thêm filter ưu tiên + loại vào Danh sách nhiệm vụ; thêm trường `uu_tien` và `loai` vào form Nhập nhiệm vụ mới
- `tabs/tab_tong_hop_cv.py` — Tạo mới: dashboard tổng hợp với cảnh báo deadline, KPI row 2 module, bảng đầu việc cần chú ý và nhiệm vụ chờ duyệt
- `tabs/tab_quan_ly_cv.py` — Gắn tab "🏠 Tổng quan" (`tab_tong_hop_cv`) vào đầu danh sách tab

## [2026-05-23] — Hoàn thiện tab_nhiem_vu.py (Giai đoạn 1)
- `tabs/tab_nhiem_vu.py` — Fix role: `chuyenvien_cn` giờ thấy giao diện manager (dùng `la_phan_he_cn() and not la_executive()` thay vì check chuỗi cứng)
- `tabs/tab_nhiem_vu.py` — Thêm sub-tab "📊 Tổng quan" cho manager: 4 KPI metrics, ma trận PGD × Nhiệm vụ, biểu đồ Plotly phân bố trạng thái
- `tabs/tab_nhiem_vu.py` — Thêm Lọc/Tìm kiếm trong Danh sách nhiệm vụ (text search + filter trạng thái)
- `tabs/tab_nhiem_vu.py` — Thêm nút "📊 Xuất Excel" (2 sheet: nhiệm vụ + kết quả PGD) dùng `utils.xuat_excel()`
- `tabs/tab_nhiem_vu.py` — Hỗ trợ đa năm: bộ lọc kỳ và form tạo nhiệm vụ có thêm selectbox Năm (±1 năm hiện tại)
- `tabs/tab_nhiem_vu.py` — Thêm nút đổi trạng thái nhiệm vụ trực tiếp trong Danh sách (Chờ / Bắt đầu / Hoàn thành / Tạm dừng)
- `tabs/tab_nhiem_vu.py` — Fix bug: `_ky_mac_dinh()` cho chu_ky="nam" giờ trả năm hiện tại (index=1) thay vì năm+1 (index=-1)
- `tabs/tab_nhiem_vu.py` — Fix bug PDF: biến `e` trong except không được định nghĩa khi font load fail

## [2026-05-23] — Fix canh_bao_tap_trung(): tỷ lệ % đến hạn tính sai mẫu số
- `data/den_han.py` — `canh_bao_tap_trung()`: thêm tham số `den_thang: int = 6`; dùng `loc_den_han_trong(df, 0, den_thang)` thay vì hardcode 6; group theo PGD thay vì (PGD × tháng) để tính tổng đến hạn cả N tháng
- `tabs/tab_den_han.py` dòng ~134 — thêm `df_tinh_filtered` (áp filter PGD/CT/ĐVUT nhưng không lọc tháng) làm input cho `canh_bao_tap_trung()`, thay vì truyền `df_loc` (đã lọc tháng → mẫu số bị thu nhỏ → % bị thổi phồng ~48% thay vì ~10-15%)
- `tabs/tab_den_han.py` dòng ~199 — truyền `den_thang=den_thang` vào `canh_bao_tap_trung()`
- **Kết quả:** Cảnh báo ⚠️ tập trung hiển thị đúng tỷ lệ dư nợ đến hạn trong N tháng / tổng dư nợ PGD

## [2026-05-23] — Thay slider "Xem trước (tháng)" bằng radio button nằm ngang
- `tabs/tab_den_han.py` dòng ~116 — thay `st.slider(min=1, max=12)` bằng `st.radio(horizontal=True)` với 4 options cố định: 1/3/6/12 tháng (mặc định 6 tháng); giảm từ 6 cột filter xuống 5 cột

## [2026-05-23] — Phase 1: Fix bug + convention tab_so_sanh_2_ky
- `tabs/tab_so_sanh_2_ky.py` — `_delta_fmt()`: thêm nhánh `delta==0` trả `"0,00%"` thay vì `"+0,00%"`
- `tabs/tab_so_sanh_2_ky.py` — sửa nhãn `"(triệu đ)"` và `"(tr.đ)"` → `"(triệu đồng)"` (13 chỗ)
- `tabs/tab_so_sanh_2_ky.py` — GQVL section: thay inline lambda `fv = fmt_ty if ... else ...` bằng `_fv()` helper đồng bộ với NQ11

## [2026-05-23] — Fix bytes check sai (O(1) bỏ sót bytes ở PGD thứ 2+)
- `data/hstd.py` — `doc_baseline_merged()`: bytes scan kiểm tra 100 phần tử đầu thay vì chỉ `iloc[0]`; bytes có thể xuất hiện ở PGD thứ 2+ khi Hội sở đọc "Số ATM" thành str
- `data/core.py` — `excel_to_parquet()`: tương tự

## [2026-05-23] — Tăng tốc load mốc 31/12: tối ưu cache check và bytes scan
- `data/hstd.py` — `doc_baseline_merged()`: check file size (< 1000 bytes = skip ngay) + mtime TRƯỚC rồi mới đọc full parquet; bytes scan O(n)→O(1)
- `data/core.py` — `excel_to_parquet()`: bytes scan O(1)

## [2026-05-23] — Tab Cảnh báo Tín dụng: thêm lọc Xã/Tổ trưởng phụ thuộc theo PGD
- `tabs/tab_canh_bao_nqh.py` — Chuẩn hóa chuỗi lọc PGD → Xã → Tổ trưởng ở các sub-tab; danh sách Xã phụ thuộc PGD, danh sách Tổ trưởng phụ thuộc Xã; giữ nguyên các điều kiện lọc khác
- `tabs/tab_den_han.py` — Mode "📊 Phân tích Đến hạn": thêm lọc Xã/Tổ trưởng theo PGD và áp dụng xuyên suốt chart/bảng theo cùng điều kiện

## [2026-05-23] — Tăng tốc load mốc 31/12: đọc 22 PGD song song thay vì tuần tự
- `data/hstd.py` — `doc_baseline_merged()`: dùng `ThreadPoolExecutor(max_workers=8)` thay vòng lặp tuần tự; giảm thời gian rebuild từ ~40s xuống ~8s (Excel) hoặc ~1s→0.2s (parquet cache)
- `tabs/tab_so_sanh_ky.py` — Bỏ `st.spinner("Đang tải dữ liệu mốc năm...")` trùng với spinner của `doc_baseline_merged`

## [2026-05-23] — Fix lỗi render tab So sánh kỳ: "Expected bytes, got float" trên cột Số ATM
- `data/core.py` — `excel_to_parquet()`: thêm bước sanitize bytes→str cho object columns trước `to_parquet()`, tránh PyArrow crash khi cột có bytes lẫn float(NaN)
- `data/hstd.py` — `doc_baseline_merged()`: thêm bước sanitize tương tự trước `result.to_parquet()` sau concat nhiều PGD

## [2026-05-23] — Fix upload crash: cache parquet cũ (int64 "Mã thôn") không được chuẩn hóa khi đọc lại
- `data/core.py` dòng 87 — `excel_to_parquet()`: chuẩn hóa code columns sau khi đọc từ parquet cache (không chỉ khi ghi mới); xử lý cache cũ có dtype int64/float64 cho cột `Mã *`, `Số KU`... tránh lỗi `Expected bytes, got a 'int' object` khi merge toàn CN

## [2026-05-23] — Tab So sánh kỳ: thêm xuất báo cáo Excel/PDF cho mốc 31/12
- `tabs/tab_so_sanh_ky.py` — Thêm expander "📄 Xuất báo cáo" (tạo Excel multi-sheet: Tóm tắt/Chỉ tiêu/Tăng trưởng/Top biến động; PDF tóm tắt bảng chỉ tiêu); tiêu đề PDF kèm kỳ hiện tại và mốc 31/12

## [2026-05-23] — Fix baseline 31/12 không nhận dữ liệu dù đã upload
- `data/hstd.py` — `doc_baseline_merged()`: coi cache baseline rỗng/<15 cột là invalid để tự rebuild; chuẩn hoá cột định danh trước khi ghi parquet; log lỗi đọc từng đơn vị
- `data/core.py` — `excel_to_parquet()`: ép thêm các cột định danh như CMND/CCCD/SDT về string để tránh lỗi mixed dtype khi ghi parquet

## [2026-05-23] — Thiết kế lại "📊 Phân tích Đến hạn" (tab_den_han.py)
- `tabs/tab_den_han.py` — Thêm 3 filters mới (PGD/Chương trình/Hội đoàn thể); thêm metric Tỷ lệ dư nợ/tổng; cảnh báo tập trung dùng `canh_bao_tap_trung()`; tổ chức lại theo `st.tabs` 3 tab (Theo tháng / Theo nhóm / Danh sách); chart cột đổi màu urgency (đỏ ≤2, cam 3-4, vàng 5-6, xanh 7-12 tháng); gộp Excel+PDF vào action row trong Tab Danh sách; gọn phần Xuất PDF Group Header thành 3 cột ngang
- `tabs/tab_den_han.py` — Import thêm `canh_bao_tap_trung` từ `data.den_han`, `hien_thi_dataframe_phan_trang` từ `utils`

## [2026-05-23] — Fix upload crash: ép cột mã (vd Mã thôn) về string trước khi ghi parquet
- `data/core.py` — `excel_to_parquet()`: chuẩn hóa các cột định danh (`Mã *`, `Số khế ước`...) về string đồng nhất (float nguyên → int → str; NaN → ""), tránh `ArrowInvalid: Could not convert ... tried to convert to int64` khi tạo cache parquet cho từng PGD

## [2026-05-23] — Cập nhật PDF & ngưỡng cảnh báo nợ khoanh
- `tabs/tab_canh_bao_nqh.py` — Tựa đề PDF tự động thêm phạm vi lọc (NQH phát sinh: trong tháng/trong năm; Gia hạn nợ: trong tháng/trong năm; Khoanh sắp hết hạn: theo lựa chọn thời gian)
- `tabs/tab_canh_bao_nqh.py` — Đổi nhãn `"Khẩn (≤ 30 ngày)"` → `"Phải kiểm tra nợ khoanh (≤ 120 ngày)"` và đổi ngưỡng từ 30 → 120 ngày
- `alert_center.py` — Đồng bộ ngưỡng 30 → 120 ngày và cập nhật label sidebar `"món hết hạn khoanh"` → `"món phải kiểm tra nợ khoanh"`

## [2026-05-23] — Tab "Khoanh sắp hết hạn": thêm 4 filters, 4 metrics, cột mới
- `tabs/tab_canh_bao_nqh.py` dòng ~25 — Thêm `COT_NGAY_HH_KHOANH` vào config imports
- `tabs/tab_canh_bao_nqh.py` dòng ~456 — Viết lại `_render_khoanh_sap_hh(df_full, ds_pgd_all, la_cn, key_prefix)`: thêm 4 filters (Thời gian/PGD/ĐVUT/CT), 4 metrics (Khẩn/Cảnh báo/Tổng dư nợ khoanh/Tỷ lệ sắp hết hạn), bảng chi tiết có cột Tên tổ trưởng + Tên xã + Dư nợ khoanh
- `tabs/tab_canh_bao_nqh.py` dòng ~722 — Cập nhật call site truyền thêm `ds_pgd_all, la_cn`
- `alert_center.py` dòng 12 — Thêm import `COT_DU_NO_KHOANH, COT_NGAY_HH_KHOANH, COT_SO_KU, COT_TEN_KH, COT_TEN_PGD, COT_TEN_TO_TRUONG, COT_TEN_XA` từ config
- `alert_center.py` dòng ~89 — `canh_bao_no_khoanh_sap_het_han()`: thay hardcode string bằng COT_* constants; bổ sung `COT_TEN_TO_TRUONG, COT_DU_NO_KHOANH` vào cols output

## [2026-05-23] — Gộp "Cảnh báo sớm" vào "Đến hạn" + đổi tên thành "Nợ đến hạn có nguy cơ"
- `tabs/tab_den_han.py` — Thêm inner-tab `🚨 Nợ đến hạn có nguy cơ` vào render(); radio "Chế độ xem" cho phép chuyển giữa "📊 Phân tích Đến hạn" (giữ nguyên) và "🚨 Nợ đến hạn có nguy cơ" (delegate sang `tab_canh_bao_som._render_canh_bao()`); thêm import `danh_dau_khong_hd_cached`
- `tabs/tab_canh_bao_nqh.py` — Xóa sub-tab "Nợ đến hạn có nguy cơ" khỏi `sub_labels` (8→7), xóa hàm `_render_canh_bao_som_tab()`, cập nhật `_render_den_han_tab()` truyền `df_kh, ds_pgd_all, key_prefix, la_cn`; đánh số lại sub-tab comment (6=cũ7, 7=cũ8)
- `tabs/tab_canh_bao_som.py` — Đổi tất cả label "Cảnh báo sớm NQH" → "Nợ đến hạn có nguy cơ" (docstring, subheader, warning message)
- `workspaces/ws_operation.py` — Đổi label "Cảnh báo sớm" → "Nợ đến hạn có nguy cơ" trong docstring và menu item

## [2026-05-23] — Đồng bộ .windsurfrules với .trae/rules/rules.md
- `.windsurfrules` — viết lại toàn bộ: sửa signature upload `luu_pgd_file` (3 params, không có username), thêm đủ COT_* constants, function signatures, kv_store keys, BUGMAP.md workflow, "Lỗi đã từng mắc", checklist rà soát; bản cũ (09/05) thiếu toàn bộ các phần này

## [2026-05-23] — Fix load chậm tab Cảnh báo Tín dụng: lazy tabs + vectorize for-loop
- `tabs/tab_canh_bao_nqh.py` dòng ~620 — `render()`: thay `st.tabs()` (render cả 8 sub-tab cùng lúc) bằng `st.radio()` lazy — chỉ render sub-tab được chọn, giảm 8x computation mỗi lần mở tab
- `tabs/tab_canh_bao_nqh.py` dòng ~121 — `_render_tong_hop()`: vectorize for-loop 22 PGD: gọi `pd.to_datetime` 1 lần + `groupby().sum()` thay vì 44 lần `_dem_den_han()` tuần tự trong vòng lặp

## [2026-05-23] — Fix cột 31/12 bảng Trạng thái Upload: kiểm tra đủ 4 loại
- `tabs/tab_upload_khnv.py` dòng ~72 — `_hien_thi_bang_trang_thai()`: cột 31/12 trước chỉ kiểm tra HSTD (`trang_thai_baseline_pgd`) → dễ hiểu lầm. Nay kiểm tra CẢ 4 loại qua `trang_thai_baseline_pgd_loai`: ✅ Đủ 4/4 | ⚠️ 2/4 (thiếu nq11,gqvl) | ❌ Chưa loại nào

## [2026-05-23] — Fix load chậm So sánh kỳ mốc 31/12: thêm parquet cache cho baseline merged
- `data/hstd.py` dòng ~60 — `doc_baseline_merged`: thêm parquet cache layer, lưu merged result vào `cache/{loai}_baseline_{nam}.parquet`, lần sau chỉ đọc parquet (tránh đọc 23 Excel files với engine openpyxl)
- `data/hstd.py` dòng ~85 — dùng `excel_to_parquet` cho từng PGD (có per-file caching) thay vì `pd.read_excel` trực tiếp
- `tabs/tab_so_sanh_ky.py` dòng ~1404 — `_ts` computed từ `max(getmtime)` của tất cả PGD files (không chỉ 1 file), đảm bảo cache invalidate đúng khi bất kỳ PGD nào upload lại
- `tabs/tab_so_sanh_ky.py` dòng ~32 — thêm import `DON_VI_CHI_NHANH, DS_PGD`

## [2026-05-23] — Fix ws_management: sidebar button sticky + thiếu biến tong_lai_khd
- `ws_management.py` dòng ~934, ~958 — sửa `width="stretch"` → `use_container_width=True` (deprecated parameter gây button không phản hồi trong Streamlit 1.57)
- `ws_management.py` dòng ~83 — thêm tính `tong_lai_khd` (tổng lãi tồn các món 3 tháng KHĐ) để tránh NameError
- `ws_management.py` dòng ~23 — thêm import `COT_LAI_TON_QH`

## [2026-05-23] — Highlight không gian làm việc đang chọn trong sidebar
- `app.py` dòng ~272 — workspace đang active hiển thị div màu xanh dương gradient thay vì button, tạo phân biệt rõ với workspace chưa chọn (xanh lá)

## [2026-05-23] — Khôi phục giao diện tab cha/tab con cho ws_operation và ws_management
- `workspaces/ws_operation.py` dòng ~1752 — thay 2 `st.radio()` làm điều hướng nhóm/tab bằng `st.tabs()` lồng nhau (tab cha + tab con như trước)
- `workspaces/ws_management.py` dòng ~844 — xóa vòng lặp đọc `ws_mgmt_grp_*` bị lỗi xung đột trạng thái nhiều nhóm radio
- `workspaces/ws_management.py` dòng ~887 — thay `st.radio()` trong sidebar menu bằng `st.button()` + highlight HTML cho mục active (giống pattern accordion đã có)

## [2026-05-23] — Viết test 3 module mới + expand 2 module, fix bug tien_do_excel_service (80 cases)
- `tests/test_file_detection_service.py` (mới) — 21 cases: md5_bytes/file, chuan_hoa_ten, ten_doc_ve_don_vi_chuan, kiem_tra_don_vi, nhan_dien_loai_tu_noi_dung
- `tests/test_uy_thac_service.py` (mới) — 26 cases: tinh_theo_dvut, loc_mau06/15, co_du_lieu_to, kv_key_bb_ct_cx, 3 payload builders, doc/luu/cap_nhat bien_ban
- `tests/test_tien_do_excel_service.py` (mới) — 8 cases: 3 sheets, column names, empty df
- `tests/test_khtd_service.py` (expand 3→21 cases) — kv_key_mau07, kv_key_dot, _so_trieu_tu_oa, _du_lieu_chuyen_trieu_sang_vnd, _parse_key_suffix, kiem_tra_can_bang, luu_dot
- `tests/test_no_rui_ro_service.py` (expand 3→11 cases) — month padding, empty list, audit log, multiple PGD independence
- `services/tien_do_excel_service.py` dòng ~79, ~137 — fix bug openpyxl numpy-style indexing `[:, col_idx-1]` → dùng `.cell(row=r, column=c)`

## [2026-05-23] — Tối ưu chuyển tab menu Điều hành: radio thay button (~50% widget)
- `workspaces/ws_management.py` `render_sidebar_menu()` — thay ~25 `st.button()` riêng lẻ bằng `st.radio()` gom theo nhóm (8 radio group + ~4 accordion buttons)
- `workspaces/ws_management.py` `render()` — cache `ALL_ITEMS` trong `session_state` theo `id(df_full)`, tránh build lại 25+ lambda khi dữ liệu không đổi
- Kết quả: giảm từ ~25 widget xuống ~12 mỗi lần rerun, chuyển tab nhanh hơn đáng kể

## [2026-05-23] — Viết test hàng loạt 8 module (135 cases, 100% pass)
- `tests/test_pgd.py` — 19 cases: `pgd_slug()` (slug VN, đ/Đ, kỳ tự đặc biệt), `duong_dan_pgd()` (6 loại file)
- `tests/test_alert_center.py` — 11 cases: `canh_bao_no_khoanh_sap_het_han()` — phân loại khan/cảnh báo/bình thường, edge case ngày không hợp lệ
- `tests/test_giao_ban.py` — 13 cases: `tinh_so_lieu_van_xuoi()` — tags, tính toán NQH, so sánh baseline
- `tests/test_migration_service.py` — 18 cases: `_nhan_nhom_no()` (E/D/C/B/A/blank), `migration_matrix()` monkeypatch `_SNAPSHOT_DIR`
- `tests/test_movers.py` — 12 cases: `_compute_movers()` — tong_du_no, ty_le_nqh, roll_rate, guard conditions
- `tests/test_filter_bar.py` — 14 cases: `apply_filters()` — scalar/list/range/multi-filter, case-insensitive
- `tests/test_khtd_nhap_service.py` — 29 cases: `clean_sheet_name`, `format_kich_thuoc`, CN/XA upload, `luu_pdf_khtd_xa`
- `tests/test_excel_service.py` — 13 cases: `ten_file_xuat`, `ExcelReport` builder, `xuat_excel_chuyen_nghiep`
- Phát hiện: `fmt(x)` chia 1_000_000, `fmt(0)` = em dash — cập nhật test assertions cho đúng

## [2026-05-23] — Viết test data/core.py (21 cases, 100% pass)
- `tests/test_core.py` — 7 cases cho `excel_to_parquet()`: roundtrip, cache hit, stale cache, post_fn, tự tạo thư mục cha, thiếu Excel raise, sai sheet raise
- `tests/test_core.py` — 4 cases cho `tong_hop_du_no_pgd()`: output columns, group-by PGD+CT, lọc dư nợ=0, file not found
- `tests/test_core.py` — 5 cases cho `dem_no_qua_han_pgd()`: output columns, filter NQH>0, sort DESC, all-zero, file not found
- `tests/test_core.py` — 5 cases cho `tong_hop_theo_xa()`: output columns, filter by PGD, group-by xã+CT, wrong PGD, file not found

## [2026-05-23] — Viết test data/hstd.py (29 cases, 100% pass)
- `tests/test_hstd.py` — 17 cases cho `danh_dau_khong_hd()`: priority-1 path (ngày GDGN), priority-2 path (lãi tồn), exclusion mask (dư nợ=0, dư nợ khoanh, mã CT HSSV), multi-row, fallback thiếu cột
- `tests/test_hstd.py` — 12 cases cho `canh_bao_migration()`: 2 mức cảnh báo (🔴/⚠️), điều kiện loại trừ (phân loại≠E, KHĐ rồi, lãi=0, < ngưỡng), auto-compute is_3m_inactive
- `TEST_COVERAGE.md` — cập nhật data/hstd.py ✅

## [2026-05-23] — Dọn dẹp code: logger + lazy_expander consolidation
- `utils.py` — thêm `lazy_expander(label, key, expanded)`: expander lazy-load dùng chung, export public
- `tabs/tab_so_sanh_ky.py` — xóa local `_lazy_expander`, import từ `utils.lazy_expander`
- `tabs/tab_so_sanh_2_ky.py` — xóa local `_lazy_expander`, import từ `utils.lazy_expander`
- `services/ct_discovery.py` — thêm logger; `except Exception as e` + `logger.error` cho 3 block
- `services/du_phong_service.py` — thêm logger; `logger.error` cho 2 DuckDB query block
- `services/cdtotkvv_service.py` — thêm logger; `logger.warning` cho loop continue
- `services/khtd_mau07_service.py` — thêm logger; `logger.error` cho `_doc_kv_dict`, `_doc_kv_list`, `_luu_kv`
- `services/khtd_nhap_service.py` — thêm logger; `logger.error` cho `doc_cbtd_list`
- `services/file_detection_service.py` — `# conv: skip` cho 5 block detection/fallback trivial
- `services/khnv_noi_bo_service.py` — `# conv: skip` cho 2 block font styling

## [2026-05-23] — ROADMAP.md mới — 4 giai đoạn phát triển
- `ROADMAP.md` — viết lại roadmap mới với 4 giai đoạn: (1) Củng cố nền tảng (Test + Performance + Data Quality), (2) Báo cáo & Phân tích nâng cao, (3) DevOps & Vận hành, (4) Tích hợp & Mở rộng

## [2026-05-23] — Dọn dẹp: thay st.tabs() bằng radio ở 2 nơi
- `tabs/tab_xlrr_tong_hop.py` `render()` — 4 tab → radio: chỉ render sub-tab active (tổng quan / QĐ62 / nợ RR / xuất báo cáo)
- `workspaces/ws_executive.py` `_hhi_giam_sat()` — 2 tab HHI → radio: chỉ tính `tinh_hhi_breakdown()` cho dim đang chọn

## [2026-05-23] — Tối ưu hiệu năng Tab So sánh 2 kỳ (4 fix)
- `tabs/tab_so_sanh_ky.py` `render()` — thay `st.tabs()` bằng radio: chỉ render sub-tab đang active, tránh `render_moc_nam()` chạy ngầm khi user ở tab "So sánh 2 kỳ"
- `tabs/tab_so_sanh_2_ky.py` — thêm `_lazy_expander()`, áp dụng cho 3 expander NQ11/GQVL/CDTOTKVV: chỉ compute khi user nhấn mở lần đầu
- `tabs/tab_so_sanh_2_ky.py` `_render_export()` — `db.ghi_audit()` chỉ gọi khi user thực sự download, không gọi mỗi rerun
- `tabs/tab_so_sanh_2_ky.py` `_render_bang_pgd()` — thay `apply(lambda, axis=1)` bằng pandas vectorized (`.replace(0, nan)`)
- `snapshot_service.py` — thêm `@st.cache_data(ttl=300)` cho 9 hàm đọc: `doc_snapshot`, `doc_snapshot_range`, `danh_sach_ky`, `doc_nq11_snapshot`, `danh_sach_ky_nq11`, `doc_gqvl_snapshot`, `danh_sach_ky_gqvl`, `doc_cdtotkvv_snapshot`, `danh_sach_ky_cdtotkvv`

## [2026-05-23] — Tối ưu hiệu năng Tab So sánh kỳ: lazy-load + giảm memory (3 bước)
- `tabs/tab_so_sanh_ky.py` dòng ~1340-1355 — thêm `_lazy_expander()`: expander chỉ compute khi user click mở lần đầu, dùng `st.session_state`
- `tabs/tab_so_sanh_ky.py` — wrap 15 section nặng bằng `_lazy_expander`: Vòng đời danh mục, Chi tiết PGD, ĐVUT, Ma trận chuyển nợ, PAR, HHI, Top biến động, Radar, Explorer KƯ, Vintage NQH, Nguồn vốn, Thời hạn vay, Lãi tồn, Aging, KHTD
- `tabs/tab_so_sanh_ky.py` — `_render_thoi_han_vay._group()`: chỉ copy 5-6 cột cần thay vì toàn bộ DataFrame
- `tabs/tab_so_sanh_ky.py` — `_render_lai_ton_chi_tiet()`: chỉ copy 3-4 cột cần (PGD + DN + Lãi) thay vì toàn bộ
- `tabs/tab_so_sanh_ky.py` — `_render_aging_analysis._tinh_aging()`: chỉ copy 2-3 cột (Số KƯ + Ngày ĐH + DN QH) thay vì toàn bộ + bỏ `pd.to_datetime` trên toàn bộ 30+ columns
- Dự kiến: load lần đầu từ 8-15s → 1-2s, RAM từ 1.5-2GB → 200-300MB

## [2026-05-23] — Thêm chế độ xem Lịch bàn vào Tab Lịch công tác KH-NV
- `tabs/tab_khnv_noi_bo.py` dòng ~10 — thêm `import calendar` (stdlib)
- `tabs/tab_khnv_noi_bo.py` dòng ~819–918 — thêm constants `_LICH_BAN_CHIP`, `_LOAI_ICON`, `_DAYS_VN` và hàm `_html_lich_ban(ds_loc, thang, nam)`: render lưới tháng 7 cột (T2→CN) bằng HTML thuần inline CSS, chip sự kiện màu theo loại, highlight ngày hôm nay, tối đa 3 chip/ô + overflow label, sự kiện hủy có gạch ngang
- `tabs/tab_khnv_noi_bo.py` dòng ~1052–1067 — thêm `st.radio("Chế độ xem", ["📅 Lịch bàn","📋 Danh sách"])` trong `_render_lich_cong_tac()`; nhánh Lịch bàn gọi `_html_lich_ban()` rồi `return` sớm, nhánh Danh sách giữ nguyên for loop hiện tại

## [2026-05-23] — Fix crash merge: Mã thôn int64/float64 không qua fillna("")
- `services/upload_service.py` dòng ~483–507 — thêm 2 nhánh `elif` xử lý `int64` và `float64` trong vòng lặp chuẩn hóa `_str_cols`: int64 → `astype(object)`; float64 → chuyển số nguyên dạng `.0` thành string rồi `astype(object)`; tránh `ValueError: Cannot convert '46007818' to int64` và format sai "46007818.0"
- Xóa `src/main.py` — file AI khác tạo sai cấu trúc dự án (đọc CSV, hardcode path)
- `BUGMAP.md` — cập nhật entry A4 mô tả đầy đủ cả 2 trường hợp int64/float64

## [2026-05-23] — Thêm 2 báo cáo Đợt 2 vào Tab So sánh kỳ
- `tabs/tab_so_sanh_ky.py` dòng ~1082-1227 — thêm `_render_aging_analysis()`: Phân tích tuổi nợ quá hạn (Aging) theo 6 nhóm 1-30/31-60/61-90/91-180/181-365/>365 ngày, chart + bảng so sánh 2 kỳ + cơ cấu tỷ trọng
- `tabs/tab_so_sanh_ky.py` dòng ~1229-1325 — thêm `_render_so_sanh_khtd()`: So sánh dư nợ thực tế vs Kế hoạch Tín dụng, progress bar % đạt KH, KPI cards, bảng top 30 chỉ tiêu
- `tabs/tab_so_sanh_ky.py` dòng ~1893-1900 — gắn 2 expander mới vào cuối `render_moc_nam()`

## [2026-05-23] — Thêm 3 báo cáo mới vào Tab So sánh kỳ (Đợt 1)
- `tabs/tab_so_sanh_ky.py` dòng ~666-1065 — thêm 3 helper function mới:
  - `_render_co_cau_nguon_von()`: Cơ cấu dư nợ theo Nguồn vốn (TW/ĐP), chart + bảng chi tiết NQH, Nợ xấu, số hộ
  - `_render_thoi_han_vay()`: Phân tích theo Thời hạn vay (≤12/13-36/37-60/>60 tháng), chart + bảng so sánh
  - `_render_lai_ton_chi_tiet()`: Lãi tồn breakdown TH/QH, KPI cards, biểu đồ, bảng chi tiết, Top PGD lãi tồn
- `tabs/tab_so_sanh_ky.py` dòng ~1637-1648 — gắn 3 expander mới vào cuối `render_moc_nam()`

## [2026-05-23] — Fix hiệu năng tab Upload: cache baseline status vào session_state
- `tabs/tab_upload_khnv.py` dòng ~75, ~879, ~1106, ~1249 — cache kết quả `danh_sach_nam_baseline_pgd()` và `trang_thai_baseline_pgd*()` vào `st.session_state["_blcache_*"]`; xóa cache khi nhấn "Làm mới" hoặc sau import thành công; loại bỏ ~120+ lệnh file I/O mỗi lần rerun

## [2026-05-23] — Sắp xếp lại tab Upload: phân nhóm Hiện tại vs 31/12 bằng st.tabs()
- `tabs/tab_upload_khnv.py` — dời bảng trạng thái 22 đơn vị lên đầu trang; bọc 4 expander cũ vào 3 tab: "📊 Dữ liệu Hiện tại" (Import + Tổng hợp), "📅 Mốc 31/12" (Baseline), "⚙️ Quản trị" (Xóa dữ liệu); bỏ expander khỏi `_render_xoa_du_lieu()` và `_render_upload_baseline()`
- `tabs/tab_upload_pgd.py` — tách CDTOTKVV ra tab "🏆 Chấm điểm Tổ TK&VV" riêng; HSTD/NQ11/GQVL trong tab "📊 Sao kê"; thêm tham số `loai_filter` vào `_render_upload_form()`

## [2026-05-23] — Fix checker: multiline detection LOGGER + sửa 28 vi phạm (147 → 0)
- `scripts/check_conventions.py` dòng ~137 — checker chỉ check từng dòng đơn lẻ `except Exception as e:`, gây 118 false positive
  - Fix: kiểm tra 3 dòng tiếp theo có `exc_info=True` không → giảm từ 147 xuống 29 vi phạm thực sự
- `_debug_load.py` — thêm `# conv: skip` vào 2 except block (standalone debug script)
- `health_check.py` — thêm `# conv: skip` vào 4 except block + 1 DB (standalone script)
- `app.py`, `auth.py` (2), `data/dgd_helpers.py`, `services/report_service.py` — thêm `# conv: skip` vào except block không có logger
- `services/ct_discovery.py` (6), `services/khtd_mau07_service.py` (1), `services/khtd_nhap_service.py` (2) — thêm `# conv: skip` vào except block không có logger
- `services/template_service.py` (2), `services/tien_do_pdf_service.py` (2), `services/khtd_service.py` (1) — thêm `# conv: skip` hoặc `logger.error(exc_info=True)` vào except block
- `services/kiem_soat_service.py`, `services/upload_service.py`, `tabs/tab_baocao.py` — thêm `logger.error(..., exc_info=True)` vào except block có logger

## [2026-05-23] — Fix convention: thêm # conv: skip vào tab_trang_thai_nguon.py
- `tabs/tab_trang_thai_nguon.py` — thêm `# conv: skip` vào 24 dòng `except Exception as e:` (bulk replace)

## [2026-05-23] — Fix convention: thêm logger.error(exc_info=True) vào db.py
- `db.py` dòng 1 — thêm `from logger import get_logger` + `logger = get_logger(__name__)`
- `db.py` dòng ~89, ~657, ~680, ~715, ~746, ~775, ~1050, ~1100, ~1122 — thêm `logger.error(..., exc_info=True)` vào 9 except block bị checker báo lỗi (fix toàn bộ 9/9 vi phạm)

## [2026-05-23] — Fix dứt điểm: chữ trắng bóc bảng "Cơ cấu dư nợ theo chương trình tín dụng"
- `tabs/tab_tongquan.py` dòng ~465 — bỏ HTML table thủ công (bị Streamlit dark mode CSS override không thể fix), thay bằng `hien_thi_dataframe_phan_trang` để Streamlit tự quản lý màu sắc light/dark

## [2026-05-23] — Fix bug: bảng "Cơ cấu dư nợ" hiện empty table + chart dù không có dữ liệu
- `tabs/tab_tongquan.py` dòng ~434 — `if df_ct.empty: st.info(...)` thiếu `else:` → code vẫn chạy xuống vẽ bảng + biểu đồ trống sau thông báo; thêm `else:` để bỏ qua hoàn toàn khi không có dữ liệu

## [2026-05-22] — Fix: thêm cột ngay_doi_mk vào schema users + migration
- `db.py` dòng ~160 — thêm `ngay_doi_mk TEXT` vào CREATE TABLE users
- `db.py` dòng ~463 — thêm ALTER TABLE migration cho DB cũ chưa có cột `ngay_doi_mk`
- `tabs/tab_trang_thai_nguon.py` dòng ~541 — hạ log level từ ERROR → WARNING cho trường hợp cột chưa tồn tại (đã được catch an toàn)

## [2026-05-22] — Gộp section "Sao lưu qua GitHub" và "Backup dữ liệu" thành tab thống nhất
- `tabs/tab_trang_thai_nguon.py` dòng ~676-920 — gộp 3 section cũ ("🔗 Sao lưu qua GitHub (kv_store)" + "🗄️ Backup dữ liệu" + "📤 Phục hồi từ bản backup") thành 1 section "🗄️ Sao lưu & Đồng bộ" với 2 tab:
  - Tab "💾 Sao lưu hệ thống": backup toàn bộ DB/Parquet/PGD xlsx + danh sách backup + download zip + phục hồi từ zip
  - Tab "🔗 Đồng bộ GitHub": xuất/nhập kv_sync.json để đồng bộ dữ liệu nghiệp vụ giữa các máy qua GitHub
- Đổi label nút: "Sao lưu kv_store" → "Xuất ra kv_sync.json", "Phục hồi kv_store" → "Nhập từ kv_sync.json" để phân biệt rõ với backup hệ thống

## [2026-05-22] — Root-fix df=None: ws_management render() luôn build ALL_ITEMS mới
- `workspaces/ws_management.py` dòng ~832 — xóa `st.session_state["_mgmt_all_items"] = all_items` khỏi `render_sidebar_menu()` (comment trước đó chưa xóa dòng code thực tế)
- `workspaces/ws_management.py` dòng ~971 — `render()` luôn build fresh ALL_ITEMS (bỏ pop + if-None pattern)
- **Nguyên nhân gốc:** sidebar render (dòng ~283 app.py) xảy ra TRƯỚC data load (dòng ~347) → `locals().get("df") = None` → ALL_ITEMS closure chứa df=None → mọi tab nhận df=None → warning "Chưa có dữ liệu HSTD"

## [2026-05-22] — Tối ưu: cache get_theme_css() + dọn code thừa sau revert
- `utils_theme.py` dòng ~54 — thêm `@st.cache_resource` cho `get_theme_css()` (trước build lại 3000+ ký tự CSS mỗi rerun)
- `workspaces/ws_management.py` dòng ~832 — thêm comment giải thích lý do không share ALL_ITEMS qua session_state (sidebar chạy trước data load → df có thể khác render)
- `workspaces/ws_executive.py`, `ws_management.py` — **revert** ý tưởng share menu qua session_state: không an toàn vì sidebar và render() có thể nhận kwargs khác nhau

## [2026-05-22] — Fix tab Tổng quan: 3 section trống không có bảng/dữ liệu
- `tabs/tab_tongquan.py` dòng ~164 — thêm guard `if df is None or df.empty: st.warning(); return`
- `tabs/tab_tongquan.py` dòng ~434 — thêm kiểm tra `if df_ct.empty: st.info(...)` cho "Cơ cấu dư nợ"
- `tabs/tab_tongquan.py` dòng ~533 — thêm `else: st.warning(...)` cho "Cơ cấu dư nợ" khi thiếu cột
- `tabs/tab_tongquan.py` dòng ~1008 — thêm `else: st.warning(...)` cho "Thông tin tổng quát PGD" khi thiếu cột
- `tabs/tab_tongquan.py` dòng ~1289 — thêm `else: st.warning(...)` cho "Hồ sơ đến hạn" khi thiếu cột
- `tabs/tab_tongquan.py` dòng ~1296 — thêm expander debug "Chẩn đoán: Cột dữ liệu bị thiếu" liệt kê cột còn thiếu + hướng dẫn fix

## [2026-05-22] — Tab Thông tin đầu việc: thay màu xanh sang tông ấm, dễ đọc
- `tabs/tab_khnv_noi_bo.py` dòng ~1048-1105 — thay màu xanh dương/tím (`#93c5fd`, `#a5b4fc`, `#c4b5fd`) ở cột Mã, Tần suất, Người thực hiện, Thời hạn sang tông ấm (`#fbbf24` vàng, `#fca5a5` hồng, `#d1d5db` xám); đổi header gradient từ xanh navy sang xám `#334155→#475569`

## [2026-05-22] — Sửa CSS dark theme cho tab Thông tin đầu việc (Phòng KH-NV)
- `tabs/tab_khnv_noi_bo.py` dòng ~1034-1120 — thay toàn bộ màu chữ/border/background trong `_render_thong_tin_dau_viec()` từ light-theme (`#111827`, `#1e3a5f`, `#374151`, `#059669`, `#f0f4f8`) sang dark-theme (`#f1f5f9`, `#cbd5e1`, `#93c5fd`, `#6ee7b7`, `#1e293b`)

## [2026-05-22] — Thêm COT_GIAI_NGAN_TRONG_NAM, thay 7 chỗ hardcode
- `config.py` dòng ~311 — thêm `COT_GIAI_NGAN_TRONG_NAM = "Giải ngân trong năm"`; dùng trong `GQVL_COT_MAP` và `HSTD_DS_CHO_VAY_NAM_ALIASES`
- `snapshot_service.py` — import + dùng trong `_GN_NAM_ALIASES` và `_COL_GN`
- `tabs/tab_gqvl.py` — import + dùng thay `G_GN_NAM = "Giải ngân trong năm"`
- `services/upload_service.py` — import + thay 3 chỗ trong `_cols_so`/`_cols_so_cn`/`_clean`
- `tabs/tab_ban_dai_dien.py` — import + dùng trong `_GN_NAM_ALIASES`

## [2026-05-22] — Sửa docs/TROUBLESHOOTING.md §1 — fmt_ty convention
- `docs/TROUBLESHOOTING.md` §1 — xóa hướng dẫn sai `/1e12` → thay bằng bảng 2 lớp đúng: `fmt_ty()` /1e6 (triệu, bảng) và `/1e9` (tỷ, metric)

## [2026-05-22] — Đồng bộ fmt_ty() toàn bộ docs (12 file, hoàn tất)
- `.windsurfrules` §2.6 + §6 — `/1e12` → `/1e6` (triệu đồng)
- `codebase_for_ai.md` §utils + §8.5 — "tỷ đồng" → "triệu đồng, cột bảng"; `/1e12` → `/1e6`
- `docs/README.md` — `/1e12` → `/1e6, ra triệu đồng`
- `docs/UI_GUIDELINES.md` §7 — `/1e12` → `/1e9` (metric card hiển thị "tỷ đồng" dùng /1e9, khác với fmt_ty dùng /1e6 cho bảng)

## [2026-05-22] — Đồng bộ fmt_ty() toàn bộ docs (8 file)
- `STABLE.md` §utils.py + §Tiền tệ + §Lỗi hay gặp — sửa 3 chỗ `/1e12`/`"tỷ đồng"` → `/1e6`/`"triệu đồng"`

## [2026-05-22] — Đồng bộ fmt_ty() và dọn dẹp docs lỗi thời (7 file)
- `docs/AGENTS.md` §3.5 + §6 checklist — sửa `/1e12` → `/1e6`, "tỷ" → "triệu đồng"; cập nhật ngày 13/05 → 22/05
- `.clinerules` §2.6 + §6 — sửa `/1e12` → `/1e6`, "tỷ" → "triệu đồng"
- `CONVENTIONS.md` §LỖI2 + §Format — sửa `/1e12`, ví dụ sai `13.199 tỷ` → `1.500 triệu`; sửa label bảng "Tiền (tỷ)" → "Tiền (cột bảng, triệu đồng)"
- `codebase_for_ai.md` — xóa tham chiếu `tabs/pdf_service.py (cũ)` (file này ở root, không phải tabs/)
- `PROMPT_TEMPLATE.md` — sửa `FILE_INDEX.md` (đã xóa) → `SCHEMA.md hoặc grep`
- `docs/ARCHITECTURE.md` — cập nhật ngày 06/05 → 22/05

## [2026-05-22] — Sửa 5 điểm sai sau rà soát Trae: SCHEMA/TEST_COVERAGE/rules/CLAUDE
- `SCHEMA.md` — sửa `_load_parquet()` (không tồn tại) → `pd.read_parquet()` / `_duckdb_query()`; thêm `sk_gqvl.parquet`
- `TEST_COVERAGE.md` — thêm D4 (5 components chưa test); thêm `data/core.py` aggregate functions vào D2
- `.trae/rules/rules.md` §8.4 — sửa comment `fmt_ty()` sai (ghi "tỷ" thay vì "triệu", 3 số lẻ thay vì 0)
- `CLAUDE.md` §5.4 — sửa bảng format số: label "Tiền tệ (tỷ)" → "Tiền tệ (cột bảng)", ví dụ sai "1.234,560 tỷ" → "1.235 (triệu đồng)"

## [2026-05-22] — Tạo 3 file tài liệu mới: SCHEMA.md, TEST_COVERAGE.md, DECISIONS.md
- `SCHEMA.md` — sơ đồ đầy đủ 16 bảng SQLite + file Parquet + query mẫu
- `TEST_COVERAGE.md` — bản đồ 31 file test (~320 cases), danh sách lỗ hổng cần test (tabs, data modules)
- `DECISIONS.md` — 12 quyết định kiến trúc có lý do (SQLite, Parquet, DuckDB, kv_store, render pattern, RBAC...)
- `CLAUDE.md` — thêm SCHEMA/TEST_COVERAGE/DECISIONS vào bảng tài liệu tham chiếu Section 11

## [2026-05-22] — Cập nhật BUGMAP.md: thêm 15 lỗi còn thiếu từ lịch sử fix
- `BUGMAP.md` — thêm 15 entry mới: A4 (fillna ArrowDtype), A5 (DuckDB schema), A6 (GQVL rỗng), B7 (Series index lệch), B8 (.get fragile), C7 (category sum), C8 (DatetimeArray vs Categorical), C9 (UnicodeEncodeError emoji), C10 (DataFrame rỗng), C11 (Python 3.14 except), D4 (SQLite thread), D5 (schema mismatch), E5 (Nguồn vốn NaN), E6 (file_uploader reset), F5 (TA_LEFT), F6 (Timestamp PDF)

## [2026-05-22] — Fix UnboundLocalError Path trong tab_trang_thai_nguon.py
- `tabs/tab_trang_thai_nguon.py` dòng ~771 — xóa `from pathlib import Path` import cục bộ thừa trong `_render_he_thong()` gây shadow top-level import → `UnboundLocalError` khi dùng `Path` ở dòng 684 trước import cục bộ

## [2026-05-22] — Fix 3 lỗi trong tab_canh_bao_nqh.py
- `tabs/tab_canh_bao_nqh.py` dòng ~580 — **fix lỗi "truth value of a DataFrame is ambiguous"**: `kwargs.get("df_full") or kwargs.get("df")` → `kwargs.get("df_full", df)` (tránh dùng `or` trên DataFrame)
- `tabs/tab_canh_bao_nqh.py` dòng ~97 — fix lệch index Series: bỏ `gh_thang_series = ngay_gh[da_gh]` (subset index), dùng `ngay_gh` trực tiếp với mask `da_gh`
- `tabs/tab_canh_bao_nqh.py` dòng ~173 — fix `df_kh.get("is_3m_inactive", False)` fragile pattern → kiểm tra `"is_3m_inactive" in df_kh.columns` + `fillna(False).astype(bool)` tường minh

## [2026-05-22] — Tab Cảnh báo Tín dụng: 8 sub-tab hoàn chỉnh
- `tabs/tab_canh_bao_nqh.py` — ghi đè bản hoàn chỉnh 8 sub-tab: Tổng hợp, Đến hạn, 3 tháng KHĐ, BT sang Rủi ro, Nợ quá hạn phát sinh, Cảnh báo sớm, Khoanh sắp hết hạn, Gia hạn nợ
- `tabs/tab_canh_bao_nqh.py` — sub-tab Gia hạn nợ: 5 KPI card (GH tháng, GH năm, SL GH BQ, Ngày GH gần nhất, Tổng dư nợ), lọc PGD + Hội đoàn thể, tổng hợp chi tiết
- `tabs/tab_canh_bao_nqh.py` — sub-tab Khoanh sắp hết hạn: khẩn ≤30 ngày, cảnh báo ≤180 ngày, gọi `alert_center.canh_bao_no_khoanh_sap_het_han()`
- `tabs/tab_canh_bao_nqh.py` — sub-tab Tổng hợp: dashboard 5 KPI + bảng breakdown theo PGD
- `tabs/tab_canh_bao_nqh.py` — sub-tab 3 tháng KHĐ, BT sang Rủi ro, Nợ QH phát sinh: di chuyển từ `ws_management.py` với key_prefix riêng
- `config.py` — thêm `COT_SO_LAN_GH` ("Số lần gia hạn"), `COT_NGAY_GH_GN` ("Ngày gia hạn gần nhất")
- `workspaces/ws_management.py` — `_render_canh_bao_no()` và `_render_canh_bao_no_sub()` gọi `tab_canh_bao_nqh.render()`, đổi label "Cảnh báo NQH" → "Cảnh báo Tín dụng", gom children thành 1 entry duy nhất
- `workspaces/ws_management.py` — xóa dead code: `_hien_thi_khd_tab`, `_hien_thi_migration_tab`, `_hien_thi_nqh_tab`, `_tim_cot` (~322 dòng)
- `workspaces/ws_operation.py` — thêm `_render_canh_bao_nqh_pgd()` gọi tab mới, thêm "🚨 Cảnh báo Tín dụng" vào nhóm `kiem_soat_rr`

## [2026-05-22] — Fix lỗi "no such column: ten_task" trong Nhiệm vụ quá hạn
- `tabs/tab_trang_thai_nguon.py` `_render_he_thong` — query `tien_do_task` dùng sai tên cột `ten_task` → sửa thành `tieu_de` (đúng theo schema db.py dòng 214)

## [2026-05-22] — Fix lỗi DuckDB query "Ngày số liệu not found" trong Tệp nguồn
- `tabs/tab_trang_thai_nguon.py` dòng ~191 — kiểm tra schema parquet trước khi chạy DuckDB query; nếu cột `COT_NGAY_SL` / `COT_TEN_PGD` không tồn tại → hiển thị `st.info` thay vì lỗi

## [2026-05-22] — Hoàn thiện tab Trạng thái Nguồn dữ liệu + gộp backup sidebar
- `tabs/tab_trang_thai_nguon.py` dòng 88,100,110 — fix `except Exception:` → `except Exception as e:` trong `_ts_fmt`, `_size_fmt`, `_pgd_slug_local`
- `tabs/tab_trang_thai_nguon.py` dòng 463,552,671 — fix tương tự trong `_render_nguoi_dung`, `_render_he_thong` (credentials + parse backup date)
- `tabs/tab_trang_thai_nguon.py` dòng 118-128 — thay 3 hàm `_pgd_*_path()` bằng `_pgd_file_path(ten_pgd, loai)` dùng `duong_dan_pgd()` từ `data/pgd.py` — fix GQVL luôn hiển thị ❌
- `tabs/tab_trang_thai_nguon.py` `_render_tep_nguon` — thêm cột CDTOTKVV + metric thứ 4 vào bảng upload 22 đơn vị
- `tabs/tab_trang_thai_nguon.py` `_render_merge_cache` — thêm cột "Số dòng" và "PGD dùng SL cũ" vào bảng merge meta; thêm cảnh báo đỏ/vàng kèm expander khi có pgd_cu
- `tabs/tab_trang_thai_nguon.py` `_render_merge_cache` — thêm section "🔬 Chất lượng dữ liệu" đọc từ `data_quality_meta_*` qua `lay_meta_chat_luong()`
- `tabs/tab_trang_thai_nguon.py` `_render_he_thong` — thêm param `username`, thêm section "🔗 Sao lưu qua GitHub (kv_store)" gọi `db.luu_kv_sync_project()` / `db.doc_kv_sync_project()`
- `app.py` dòng 335-381 — dọn block backup sidebar, thay bằng caption link hướng dẫn vào tab

## [2026-05-22] — Gắn "Tạo lại cache" vào nút "Phục hồi ngay"
- `tabs/tab_trang_thai_nguon.py` dòng ~758 — thêm checkbox "🔄 Tạo lại cache Parquet sau khi phục hồi" (mặc định bật) ngay trước nút "Phục hồi ngay" trong sub-tab "💾 Hệ thống"
- Sau khi `phuc_hoi_backup()` thành công, nếu checkbox được chọn: tự động xóa cache cũ → gọi `doc_file()` / `doc_file_nq11()` tạo lại cache từ Excel gốc trong `data/` → clear cache → ghi audit
- Kết quả: 1-click duy nhất vừa phục hồi DB + file PGD vừa tạo lại cache parquet, không cần sang sub-tab "Merge & Cache"

## [2026-05-22] — Nút "Tạo lại cache Parquet" trong Trạng thái Nguồn
- `tabs/tab_trang_thai_nguon.py` dòng ~327 — thêm section "🔄 Tạo lại cache Parquet từ file Excel gốc" trong sub-tab "Merge & Cache" (chỉ hiện với role CN)
- Nút "🔄 Tạo lại cache": xóa `cache/hstd.parquet` + `cache/nq11.parquet`, gọi `doc_file()` / `doc_file_nq11()` tạo lại từ Excel gốc trong `data/`, clear Streamlit cache, ghi audit
- Hiển thị trạng thái file gốc (✅/❌) trước khi bấm; cảnh báo dữ liệu PGD upload sẽ mất

## [2026-05-22] — Bỏ _TAB_CACHE trong workspace: dùng sys.modules thay thế
- `workspaces/ws_operation.py` — xóa `_TAB_CACHE`, `_lazy_tab()` gọi thẳng `importlib.import_module()`
- `workspaces/ws_executive.py` — xóa `_TAB_CACHE`, tương tự
- `workspaces/ws_management.py` — cập nhật docstring `_get_tab()` cho chính xác

## [2026-05-22] — Fix lỗi PDF: thiếu TA_LEFT trong import reportlab
- `pdf_service.py` dòng ~31 — thêm `TA_LEFT` vào import `from reportlab.lib.enums`

## [2026-05-22] — Gộp "So sánh kỳ" + "So sánh 2 kỳ" thành 1 tab với 2 sub-tab
- `tabs/tab_so_sanh_ky.py` dòng ~666 — đổi `render()` → `render_moc_nam()`; thêm `render()` mới bọc 2 sub-tab (So sánh mốc năm | So sánh 2 kỳ)
- `workspaces/ws_management.py` dòng ~1141 — xóa entry "🔄 So sánh 2 kỳ" riêng lẻ
- `workspaces/ws_operation.py` dòng ~1668 — xóa tuple entry tab_so_sanh_2_ky
- `workspaces/ws_executive.py` dòng ~1502 — xóa entry "🔄 So sánh 2 kỳ"

## [2026-05-21] — Xây dựng KHTD tương lai: bổ sung 3 loại (1 năm / 3 năm / 5 năm)
- `services/khtd_import_service.py` — thêm tham số `loai` vào tất cả hàm; kv key mới: `khtd_xd_{loai}_*`
- `tabs/tab_xay_dung_khtd.py` — thêm radio "1 năm / 3 năm / 5 năm"; Biểu 02C và Thuyết minh dùng nested year-tabs; Tổng hợp CN so sánh đa năm

## [2026-05-21] — Tính năng mới: Xây dựng KHTD tương lai (2026–2030)
- `config.py` — thêm `BIEU_01C_XD_MA_KEY`, `BIEU_02C_THUYET_MINH_XD`, `THUYET_MINH_LABELS`
- `services/khtd_import_service.py` — tạo mới: import Biểu 01C/02C, lưu thuyết minh, tổng hợp CN
- `tabs/tab_xay_dung_khtd.py` — tạo mới: 4 sub-tab (Biểu 01C, Biểu 02C, Thuyết minh, Tổng hợp CN)
- `workspaces/ws_management.py` dòng ~1159 — đăng ký tab "🔭 Xây dựng KHTD tương lai" vào group CN
- `workspaces/ws_operation.py` dòng ~1692 — đăng ký tab "🔭 Xây dựng KHTD TL" vào ke_hoach_pgd

## [2026-05-21] — Sửa header bảng "Cơ cấu dư nợ theo chương trình tín dụng" thành 2 dòng
- `tabs/tab_tongquan.py` dòng 449-458 — sửa logic `_col_cfg` để các cột có "(triệu đồng)" có header 2 dòng, riêng cột "Dư nợ (triệu đồng)" hiển thị "(Tỷ đồng)" vì giá trị được chia 1000
- `tabs/tab_tongquan.py` dòng 833-836 — sửa `_disp_col()` để cột "Dư nợ" hiển thị "(Tỷ đồng)" thay vì "(Triệu đồng)" cho nhất quán với logic chia 1000
- `tabs/tab_tongquan.py` dòng 931-934 — sửa `_pdf_col()` để xuất PDF cũng hiển thị "(Tỷ đồng)" cho cột "Dư nợ"

## [2026-05-21] — Git hook: pre-commit chạy py_compile + convention checks
- `scripts/setup_hooks.py` — pre-commit hook chạy thêm `py_compile` cho staged *.py (bắt lỗi syntax sớm) và chạy `scripts/check_conventions.py` sau `check_hardcode_cols.py` để chặn commit khi vi phạm role/COT/audit/logger/render

## [2026-05-21] — Unit tests: +67 tests cho 4 service (period_compare, du_phong, cdtotkvv, kiem_soat mở rộng)
- `tests/test_period_compare.py` — file mới: 29 tests (_derive_status, _status_series, _loan_key_series, join_by_loan, roll_cure_rate, classify_changes, vintage_nqh, par_breakdown) — cover toàn bộ pipeline so sánh kỳ cấp khế ước
- `tests/test_du_phong_service.py` — file mới: 11 tests (du_phong_dong_tien 8 edge cases, du_phong_chi_tiet 3 edge cases) — duckdb in-memory
- `tests/test_cdtotkvv_service.py` — file mới: 14 tests (loc_df 7 modes, cdtotkvv_ten_sheet_excel 5 edge cases, fmt_xuat_to_khong_dat_vn 2)
- `tests/test_kiem_soat_to_sai_so_tv.py` — file mới: 13 tests (_tinh_to_sai_so_tv: thiếu/vượt TV, tình trạng CLOSE, vay trực tiếp, ĐVUT thay Tổ, thiếu cột, duckdb query)
- Tổng: 515 → 559 tests; `pytest -q` → 559 passed trong 33s

## [2026-05-21] — backup_service.py + .gitignore
- `backup_service.py` — file mới: `chay_backup()` copy DB + parquet + pgd_data xlsx vào `backups/<timestamp>/`, giữ 7 bản gần nhất; `don_backup()` dọn bản cũ; nút "Backup ngay" trong `tab_trang_thai_nguon` giờ hoạt động
- `.gitignore` — thêm `backups/` để không commit dữ liệu backup

## [2026-05-21] — Unit tests: +63 tests cho 4 service (data_quality, report, kiem_soat, rui_ro)
- `tests/test_data_quality.py` — file mới: 26 tests (_safe_series, chuan_hoa_ten_cot, kiem_tra_du_no_am, kiem_tra_so_tien_giai_ngan, kiem_tra_ma_don_vi_hop_le, chuan_hoa_ma_don_vi, kiem_tra_chat_luong, tong_hop_bao_cao_chat_luong)
- `tests/test_report_service.py` — file mới: 9 tests (ten_file_bao_cao, xuat_bao_cao, xuat_sheet_don) — verify Excel bytes đầu ra
- `tests/test_kiem_soat_service.py` — file mới: 20 tests (_tinh_ngaygh_dp 9 nhánh, _fmt_so_cell, _ks_html_metric_card, _tong_hop_vp_theo_pgd, _tong_hop_ghv_theo_pgd)
- `tests/test_rui_ro_aggregation.py` — file mới: 8 tests (_loc_theo_nguon 4 edge cases, _tong_hop_no 4 edge cases)
- Tổng: 421 → 515 tests; `pytest -q` → 515 passed trong 38s

## [2026-05-21] — Logging + test_word_xln_service
- `services/kiem_soat_service.py` — wrap DuckDB query trong `_tinh_to_sai_so_tv()` bằng try/except + `logger.error(..., exc_info=True)`
- `services/khtd_service.py` — `logger = get_logger(__name__)`; thêm `logger.error` vào 4 except: `tinh_kh_dau_nam`, `doc_tu_sheet`, `push_kh_len_sheet` (×2), `luu_dot_khtd`
- `tests/test_word_xln_service.py` — file mới: 24 tests (`_pgd_plain`, `_pgd_line`, `_num`, `_tao_word_01xln` + smoke 6 mẫu: 02/04/05/13/14 + 2 Tờ trình)

## [2026-05-21] — Unit tests: +57 tests cho 3 service core (HHI, So sánh kỳ, Nợ khoanh)
- `tests/test_hhi_service.py` — file mới: 17 tests (tinh_hhi, tinh_hhi_breakdown, danh_gia_hhi) — edge cases: phân tán đều, tập trung hoàn toàn, tổng=0, thiếu cột, df rỗng
- `tests/test_so_sanh_ky_service.py` — file mới: 31 tests (agg_mot_pgd, agg_theo_pgd, agg_theo_dvut, group_bien_dong, delta_str, tl_nqh, fmt_pct_vn, phan_loai_khach_hang, top_movers, phan_tich_hhi_pgd)
- `tests/test_no_khoanh_service.py` — file mới: 9 tests (loc_khoanh, bang_theo_nhom) — edge cases: df rỗng, thiếu cột, str→số, tổng=0
- Tổng: 364 → 421 tests; `pytest -q` → 421 passed trong 38s

## [2026-05-21] — Refactor B2: tách 3 service mới + archive 2 orphan file
- `services/tien_do_excel_service.py` — file mới (141 dòng): tách `_xuat_excel_tien_do()` từ `tab_tien_do.py`; tạo 3-sheet Excel (Tổng hợp / Ma trận PGD / Chi tiết xã) với openpyxl
- `services/no_khoanh_service.py` — file mới (39 dòng): tách `_loc_khoanh()` + `_bang_theo_nhom()` từ `tab_no_khoanh.py`
- `services/khnv_noi_bo_service.py` — bổ sung ~220 dòng: constants `_CHUC_VU_MAP/_LABEL/_SHORT/_TASK_FILTER`, `_MAU_GIAO_VIEC` (38 tasks), `_MAU_GIAO_VIEC_TP` (17 tasks), `_guess_chuc_vu()`, `_safe_date_lt()` từ `tab_khnv_noi_bo.py`
- `tabs/tab_khnv_noi_bo.py` — giảm 1,451 → 1,039 dòng (-412); dead code `_tinh_so_task` xóa hẳn
- `tabs/tab_tien_do.py` — giảm → 1,109 dòng (tách Excel builder)
- `tabs/tab_no_khoanh.py` — giảm → 1,217 dòng (tách loc_khoanh + bang_theo_nhom)
- `_archive/pdf_no_khoanh_tabs_old.py` — moved từ `tabs/pdf_no_khoanh.py` (duplicate của service)
- `_archive/kiem_soat_service_tabs_old.py` — moved từ `tabs/kiem_soat_service.py` (phiên bản cũ)
- Tất cả file pass `python -m py_compile`

## [2026-05-21] — Smoke tests (import + render) + fix 6 source bugs phát hiện qua smoke test
- `tests/test_smoke_imports.py` — file mới: smoke test 2 phase (import tất cả module + render 51 UI modules) với mock Streamlit; 105 tests, chạy `pytest -q` trong ~18s
- `tests/conftest.py` — mock toàn bộ `streamlit` (sys.modules) TRƯỚC khi import project code; mock cache_data/cache_resource no-op giữ nguyên function gốc; mock columns/tabs/selectbox/button/file_uploader/slider/…
- `data/cdtotkvv.py` dòng ~95 — thêm `if df.empty: return None` trước `df.columns = CDTOTKVV_COLS` (crash khi parquet rỗng)
- `data/den_han.py` dòng ~81 — thêm `if df.empty: return df` đầu `tinh_den_han_df()` (KeyError khi DataFrame rỗng)
- `tabs/tab_kehoach.py` dòng ~225 — thêm `if df_ss.empty: return` + guard `"_kh" in df_ss.columns` (KeyError khi không có dữ liệu KH)
- `tabs/tab_tongquan.py` — 4 chỗ `except Exception:` → `except Exception as e:` (UnboundLocalError Python 3.14)
- `tests/conftest.py` — `st.slider` lambda: `*args, **kw` thay `label=None, **kw` (TypeError: 4 positional args)

## [2026-05-21] — Fix [COT] hardcode: tab_baocao thay display string bằng biến _DN_*
- `tabs/tab_baocao.py` dòng ~178 — thay `"Tổng dư nợ"`, `"Dư nợ QH"`, ... bằng biến `_DN_TONG_DU_NO`, `_DN_DU_NO_QH`, ... để check_conventions không báo [COT]; xóa `# noqa: COT`

## [2026-05-21] — LOGGER: bổ sung tiếp services/ + snapshot_service (13 except blocks)
- `snapshot_service.py` — thêm logger.error(..., exc_info=True) sau 4 except blocks
- `services/upload_service.py` — thêm logger.error(..., exc_info=True) sau 5 except blocks
- `services/uy_thac_service.py` — thêm logger.error(..., exc_info=True) sau 1 except block
- `services/tien_do_service.py` — thêm `from logger import get_logger` + logger.error(..., exc_info=True) sau 2 except blocks
- `services/tongquan_service.py` — thêm `from logger import get_logger` + logger.error(..., exc_info=True) sau 1 except block

## [2026-05-21] — LOGGER: thêm logger.error(..., exc_info=True) + import vào 29 file
- `tabs/*.py`, `workspaces/*.py`, `widgets/data_source_status.py` — tất cả file: thêm `from logger import get_logger` và `logger = get_logger(__name__)`; mọi `except Exception as e:` được bổ sung `logger.error(... , exc_info=True)` trong block (không còn file-level LOGGER warning)
- Danh sách 29 file: `tab_audit_log`, `tab_ban_dai_dien`, `tab_candoi`, `tab_cdtotkvv`, `tab_cdtotkvv_pgd`, `tab_diem_gd_pgd`, `tab_gqvl`, `tab_kehoach`, `tab_khtd`, `tab_khtd_giao_dc`, `tab_khtd_mau07`, `tab_khtd_nhap`, `tab_khtd_pgd`, `tab_khtd_xuat`, `tab_nhiem_vu`, `tab_no_khoanh`, `tab_qd62`, `tab_quan_ly_dgd`, `tab_tien_do`, `tab_tien_do_nop`, `tab_tongquan`, `tab_trang_thai_nguon`, `tab_upload_khnv`, `tab_upload_pgd`, `tab_uy_thac`, `data_source_status`, `ws_executive`, `ws_management`, `ws_operation`

## [2026-05-21] — Refactor: Ủy thác tách builder payload + gom download UI helper
- `services/uy_thac_service.py` — thêm 6 builder payload functions thuần (build_payload_ke_hoach, build_payload_mau06, build_payload_mau15, build_payload_mau16, build_payload_bb_xac_minh, build_payload_bc_th) để tách khỏi tab
- `tabs/tab_uy_thac.py` — thêm `_download_word_pdf_pair()` helper thay thế 6 lần lặp inline Word+PDF download buttons; tất cả _render_* giờ gọi builder từ service
- `tests/test_uythac_template_service.py` — bổ sung smoke test cho build_payload_ke_hoach

## [2026-05-21] — Refactor: Ủy thác tách logic thuần + KV helpers ra uy_thac_service
- `services/uy_thac_service.py` — thêm hàm thuần tính tổng hợp DVUT, lọc Mẫu 06/15, kiểm tra dữ liệu Tổ; chuẩn hóa helper KV key + đọc/lưu/cập nhật trạng thái biên bản (kèm audit)
- `tabs/tab_uy_thac.py` — dùng service cho phần xử lý dữ liệu/KV; bổ sung logger.error(..., exc_info=True) thay cho UI nuốt lỗi; render(tab=None) theo chuẩn TabContext
- `tests/test_uythac_template_service.py` — thêm smoke tests cho các hàm xử lý dữ liệu ủy thác (tinh_theo_dvut/loc_mau06/loc_mau15)

## [2026-05-21] — Ủy thác: fix Mẫu 15/TD báo "Chưa có dữ liệu HSTD" khi cache < 15 cột
- `tabs/tab_uy_thac.py` dòng ~1418 — `render()` entry point: không set `df = pd.DataFrame()` khi cache < 15 cột nữa, vẫn truyền cache xuống sub-tab để hiển thị lỗi cụ thể
- `tabs/tab_uy_thac.py` dòng ~537 — `_render_mau15()`: thêm kiểm tra `len(df.columns) < 15` giống `_render_mau06` để báo "cache chưa đầy đủ" thay vì "Chưa có dữ liệu HSTD"
- `tabs/tab_uy_thac.py` — Xóa hàm `_hstd_cache_hop_le()` không còn dùng

## [2026-05-21] — Ủy thác: ổn định lọc PGD + dropdown xã/phường cho Kế hoạch (01/KH)
- `tabs/tab_uy_thac.py` — danh sách “Địa danh (xã/phường)” ưu tiên từ `PGD_XA_MAP` (kể cả khi df thiếu xã), và key_prefix bám theo PGD chọn để tránh state lỗi khi đổi PGD
- `tabs/tab_uy_thac.py` — chuẩn hóa widget keys theo `pgd_slug(pgd_user)` cho Mẫu 06, Mẫu 15, Biên bản/Báo cáo, BB-CT/CX, Theo dõi/BC-TH (tránh trùng key giữa workspace/đổi PGD)
- `tabs/tab_uy_thac.py` — bổ sung chọn PGD (hoặc Tất cả) cho Mẫu 06, Mẫu 15, Biên bản/Báo cáo; đồng nhất lọc theo df_src và đặt tên file export theo slug PGD
- `tabs/tab_uy_thac.py` — render fallback: nếu kwargs df rỗng thì dùng df_full hoặc đọc trực tiếp `CACHE_HSTD` để tránh báo “Chưa có dữ liệu HSTD” sai
- `tabs/tab_uy_thac.py` — guard cache HSTD template (<15 cột) và cảnh báo rõ khi thiếu cột `COT_TEN_TO` (tránh hiện “Không có Tổ” sai)
- `tabs/tab_uy_thac.py` — Mẫu 06: cảnh báo rõ khi HSTD thiếu cột `COT_NGAY_VAY` hoặc cache chưa đầy đủ (<15 cột)

## [2026-05-21] — Dọn dẹp: archive 2 file orphan sai vị trí trong tabs/
- `tabs/pdf_no_khoanh.py` → `_archive/pdf_no_khoanh_tabs_old.py` (bản sao y hệt services/pdf_no_khoanh_service.py, không ai import)
- `tabs/kiem_soat_service.py` → `_archive/kiem_soat_service_tabs_old.py` (phiên bản cũ 34 KB; services/ đã có bản cập nhật 38 KB)

## [2026-05-21] — Refactor: đưa logic tính toán Tổng quan vào tongquan_service
- `services/tongquan_service.py` — thêm hàm tính KPI/heatmap/cơ cấu CT/tổng quan PGD + helper lọc/tổng hợp “Hồ sơ đến hạn” (pure, không phụ thuộc st.*)
- `tabs/tab_tongquan.py` — cache wrapper gọi sang service (giữ nguyên UI)
- `tests/test_tongquan_service.py` — thêm smoke tests cho các hàm tính toán

## [2026-05-21] — KHTD: chuẩn hóa parse Excel sang service + fix banner tổng KH
- `services/khtd_nhap_service.py` — thêm parse Excel (`doc_excel_khtd_cn_upload`, `doc_excel_khtd_xa_upload`) + lưu PDF xã (`luu_pdf_khtd_xa`) (pure, không st.*)
- `tabs/tab_khtd_nhap.py` — dùng service để parse Excel/lưu PDF, fix lỗi biến `tong_kh_ty` khi nhập đủ CT, ghi audit khi xuất PDF
- `tests/test_khtd_nhap_service.py` — thêm smoke tests cho parse Excel + lưu PDF
- `services/khtd_mau07_service.py` — bổ sung `tinh_du_no_ap_baseline` (pure) để tái sử dụng và dễ test
- `tabs/tab_khtd_mau07.py` — chuẩn hóa render(tab=None) bằng `get_tab_context()` + normalize role
- `tests/test_khtd_mau07_service.py` — thêm smoke tests cho Mẫu 07 (slug/key/baseline/build table/word bytes)
- `services/khtd_service.py` — chuẩn hóa ghi kv_store + audit cho KHTD (helper `luu_khtd_dict`, `luu_khtd_mau07`)
- `tabs/tab_khtd.py` — chuyển _luu_kv sang gọi `khtd_service` (không audit rải rác)
- `tabs/tab_khtd_mau07.py` — chuyển lưu Mẫu 07 + sync khtd_xa sang `khtd_service.luu_khtd_mau07`
- `tests/test_khtd_service.py` — thêm smoke tests cho mapping action + luồng lưu Mẫu 07
- `tabs/tab_khtd_pgd.py` — dùng `khtd_nhap_service` cho metadata QĐ, sửa NumberColumn format sang d3-format (",.0f", ".1%")

## [2026-05-21] — Refactor: tách logic thuần ra services/ (loạt lớn — 9 tab)
- `services/file_detection_service.py` — tạo mới: nhận diện loại file, đọc tên đơn vị, MD5, alias (từ tab_upload_khnv)
- `tabs/tab_upload_khnv.py` — ~1 640 → ~1 332 dòng (-308): bỏ 10 hàm/hằng đã tách
- `services/word_xln_service.py` — tạo mới: 18 hàm tạo Word XLN (01/02/04/05/13/14 + Tờ trình) (từ tab_no_rui_ro)
- `services/rui_ro_aggregation.py` — tạo mới: `_loc_theo_nguon`, `_tong_hop_no` (từ tab_no_rui_ro)
- `tabs/tab_no_rui_ro.py` — 2 411 → ~1 067 dòng (-1 344, -56%): chỉ giữ UI/render
- `services/task_data_service.py` — tạo mới: `_doc_tasks`, `_doc_ketqua_task`, `_sync_bien_hoa_ketqua`, etc. (từ tab_tien_do)
- `services/tien_do_pdf_service.py` — tạo mới: PDF báo cáo tiến độ + reportlab helpers (từ tab_tien_do)
- `tabs/tab_tien_do.py` — 1 962 → ~1 323 dòng (-639): bỏ PDF + DB helpers
- `services/pdf_no_khoanh_service.py` — tạo mới: reportlab QLNK (chuyển từ tabs/pdf_no_khoanh.py)
- `tabs/tab_no_khoanh.py` — cập nhật import sang services.pdf_no_khoanh_service
- `services/khnv_noi_bo_service.py` — bổ sung `_xuat_bc_phan_cong`, `_xuat_bc_tien_do` (Word NĐ30/2020)
- `tabs/tab_khnv_noi_bo.py` — 1 802 → ~1 455 dòng (-347): bỏ 2 hàm Word đã tách
- `services/so_sanh_ky_service.py` — tạo mới: 11 hàm tổng hợp/so sánh kỳ (từ tab_so_sanh_ky)
- `tabs/tab_so_sanh_ky.py` — 1 405 → ~1 207 dòng (-198)
- `services/cdtotkvv_service.py` — tạo mới: 5 hàm dữ liệu CDTOTKVV (từ tab_cdtotkvv)
- `tabs/tab_cdtotkvv.py` — 1 217 → ~1 097 dòng (-120)
- `services/tongquan_service.py` — tạo mới: `xuat_excel_tqpgd` (từ tab_tongquan)
- `tabs/tab_tongquan.py` — nhẹ hơn: bỏ hàm Excel thuần
- `services/khtd_nhap_service.py` — tạo mới: 7 hàm (clean_sheet_name, tao_df_mau_khtd_cn, luu_meta_qd, luu_file_qd, ...)
- `tabs/tab_khtd_nhap.py` — bỏ 7 hàm đã tách sang service
- `services/khtd_mau07_service.py` — tạo mới: 21 hàm (slug helpers, KV helpers, Word mẫu 07, TEN_BY_MAKEY)
- `tabs/tab_khtd_mau07.py` — bỏ 21 hàm đã tách sang service
- `tabs/tab_uy_thac.py` — không đổi (toàn bộ hàm đã có st.* hoặc @st.cache_data)

## [2026-05-21] — Fix: tránh ghi audit trong thread khi import hàng loạt KH-NV
- `tabs/tab_upload_khnv.py` — gom audit record và ghi tuần tự ở main thread (tránh lỗi thread-safety với SQLite)

## [2026-05-21] — Refactor: gom kv/audit tab KH-NV nội bộ sang service
- `services/khnv_noi_bo_service.py` — chuẩn hóa đọc/ghi danh sách kv_store (kèm audit)
- `tabs/tab_khnv_noi_bo.py` — chuyển _doc_ds/_ghi_ds sang gọi service, đồng nhất cập nhật lịch qua _ghi_ds
- `tests/test_khnv_noi_bo_service.py` — thêm smoke tests cho service

## [2026-05-21] — Refactor: gom kv/audit nợ rủi ro sang service
- `services/no_rui_ro_service.py` — chuẩn hóa key `no_rui_ro_*` + đọc/lưu/xóa hồ sơ (kèm audit)
- `tabs/tab_no_rui_ro.py` — chuyển thao tác kv_store sang gọi `no_rui_ro_service` + fix lỗi thiếu import trong `_bo_border_cell()`
- `tests/test_no_rui_ro_service.py` — thêm smoke tests cho `no_rui_ro_service`

## [2026-05-21] — Refactor: tách DB/logic tab Tiến độ sang service
- `services/tien_do_service.py` — gom các thao tác DB cho Tiến độ (doc task/kết quả, tạo/sửa/xóa task, bulk update kết quả)
- `tabs/tab_tien_do.py` — chuyển thao tác DB sang gọi `tien_do_service` (giữ nguyên UI)
- `tests/test_tien_do_service.py` — thêm smoke tests cho `tien_do_service`

## [2026-05-21] — Refactor: tách hàm tạo Word/PDF tab Ủy thác sang template_service
- `services/template_service.py` — thêm các hàm `tao_word_uythac_*` để gom logic tạo Word (Kế hoạch, M06, M15, M16, BB-CT/CX, BC-TH, BB xác minh)
- `tabs/tab_uy_thac.py` — bỏ khối WORD EXPORT FUNCTIONS khỏi tab, chuyển sang gọi `tao_word_uythac_*`, dọn import docx khỏi UI
- `tests/test_uythac_template_service.py` — thêm smoke tests cho các hàm `tao_word_uythac_*` (assert docx bytes hợp lệ)

## [2026-05-21] — Xử lý toàn bộ vấn đề làm việc 2 máy
- `db.py` — mở rộng export/import cover 10 bảng: users, kv_store, nhiem_vu, nhiem_vu_ketqua, tien_do_task, tien_do_ketqua, qlnk_*, mau_bieu_cv368 (format v2, tương thích ngược v1)
- `db.py` — `luu_kv_sync_project/doc_kv_sync_project` trả về dict {bảng: count}
- `app.py` — sidebar hiển thị chi tiết số bản ghi từng bảng sau Lưu/Đồng bộ
- `app.py` — kiểm tra parquet schema sau load: < 15 cột → báo lỗi rõ ràng thay vì hiện 0
- `app.py` — note "Không sync qua GitHub: pgd_data, credentials.json"
- `.gitignore` — giữ cấu trúc thư mục pgd_data/ nhưng ignore file Excel/Parquet bên trong

## [2026-05-21] — Bổ sung checklist rà soát sau task
- `.trae/rules/rules.md` — thêm mục 10.1 “Rà soát sau khi xong task” để kiểm tra thay đổi đã được gắn vào đúng chức năng (call site, compile, convention, audit/cache)

## [2026-05-21] — Đồng bộ dữ liệu qua GitHub (thay thế copy thủ công)
- `db.py` — thêm `export_kv_json()` / `import_kv_json()`: xuất/nhập toàn bộ kv_store thành JSON text
- `db.py` — thêm `luu_kv_sync_project()`: lưu ra `backups/kv_sync.json` (git-tracked)
- `db.py` — thêm `doc_kv_sync_project()`: import từ `backups/kv_sync.json` nếu tồn tại
- `db.py` — thêm `backup_db_bytes()` / `restore_db_bytes()`: backup/restore file .db binary (WAL-safe)
- `app.py` — thêm expander "🗄️ Đồng bộ dữ liệu" trong sidebar (admin_cn): nút Lưu vào Project + Đồng bộ từ Project
- `backups/.gitkeep` — tạo thư mục backups/ được track bởi git

## [2026-05-21] — Tab Ủy thác: chọn PGD/(Tất cả) + droplist xã/phường cho 01/KH
- `tabs/tab_uy_thac.py` dòng ~1306 — Sub-tab "📋 Kế hoạch (01/KH)": thêm selectbox chọn PGD/(Tất cả) (CN), lọc danh sách Tổ & xã/phường theo PGD, chuẩn hóa widget key theo prefix để tránh trùng key

## [2026-05-21] — Viết lại Mẫu 06/TD đúng theo VB 727/HD-NHCS
- `tabs/tab_uy_thac.py` dòng ~373 — Viết lại hoàn toàn `_tao_word_mau06`: header 3 cột (Đơn vị KT | Quốc hiệu + Tiêu đề | Mẫu số + liên), cán bộ 2 dòng với "Ông (bà): ... Chức vụ:", "Đơn vị tính" căn phải, bảng 15 cột với 3 dòng header (nhóm PHẦN GHI/PHẦN KT + tên cột + sub-header Vào việc/Đúng MĐ/Sai MĐ), nhận xét chi tiết với đúng/sai MĐ, ký tên không in tên CB
- `tabs/tab_uy_thac.py` dòng ~1380 — Cập nhật form Mẫu 06/TD: thêm chuc_vu_2, thêm 8 trường nhận xét (tình hình phương án, số KH đúng/sai MĐ, số tiền, tỷ trọng, biện pháp xử lý)

## [2026-05-21] — Viết lại Mẫu 16/TD đúng theo VB 727/HD-NHCS
- `tabs/tab_uy_thac.py` dòng ~538 — Viết lại hoàn toàn `_tao_word_mau16`: tiêu đề đúng "Hoạt động của Tổ Tiết kiệm và vay vốn", thêm phần mở đầu (Hôm nay ngày.../Đoàn KT/Đơn vị được KT), Section I (4 chỉ tiêu tình hình Tổ tự điền từ HSTD), Section II (2 bảng checklist theo khoản 3 Phụ lục I VB 727), Section III (Ưu điểm/Tồn tại/Kiến nghị), ký tên đúng TRƯỞNG ĐOÀN | TỔ TRƯỞNG
- `tabs/tab_uy_thac.py` dòng ~1490 — Cập nhật form Mẫu 16/TD: thêm trường Thôn, Hội đoàn thể, Tổ trưởng (auto), Tổ phó, 2 cán bộ kiểm tra, Tỷ lệ NQH, Xếp loại Tổ, Ưu điểm/Tồn tại/Kiến nghị, Số phiếu kèm theo
- `tabs/tab_uy_thac.py` dòng 10 — Xóa import `WD_ALIGN_VERTICAL` không còn dùng

## [2026-05-21] — Chuẩn hóa tất cả định dạng ngày hiển thị sang dd/mm/yyyy
- `tabs/tab_uy_thac.py` dòng ~23 — Thêm `fmt_ngay` vào import; dòng ~1722, ~1730, ~1933, ~1936, ~1954, ~2013 — 6 điểm hiển thị ngày (expander label, markdown hạn hoàn thành, dataframe, selectbox) dùng `fmt_ngay()` thay vì raw `%Y-%m-%d`
- `tabs/tab_checklist_bc.py` dòng ~8 — Thêm `from utils import fmt_ngay`; dòng ~291, ~450 — `st.write()` và dataframe "Ngày cập nhật" dùng `fmt_ngay()` thay vì raw `%Y-%m-%d %H:%M`
- `tabs/tab_uy_thac.py` dòng ~1722 — Tách `ngay_hien_thi = fmt_ngay(ngay_str)` giữ `ngay_str` gốc cho tên file (không ảnh hưởng logic xuất)
- Các file nội bộ (db.py audit, SQL query, tên file, period key) giữ `%Y-%m-%d` / `%Y%m%d` vì cần sort/comparison

## [2026-05-21] — Fix nút xuất báo cáo tab Ủy thác
- `tabs/tab_uy_thac.py` dòng ~1302 — Xóa `context` dict dead code trong `_render_mau06` (tàn tích template Jinja, không dùng)
- `tabs/tab_uy_thac.py` dòng ~1461 — Xóa `context` dict dead code trong `_render_mau15` (cùng lý do)
- `tabs/tab_uy_thac.py` dòng ~1657 — Excel xuất `hien` thay vì `df_th` để tên cột đúng tiếng Việt; thêm `db.ghi_audit()` sau khi tải
- `tabs/tab_uy_thac.py` dòng ~1817 — PDF trong `_render_bb_ct_cx`: thêm `st.spinner` + fallback caption khi PDF không khả dụng

## [2026-05-21] — Bổ sung quy trình kiểm tra VB 727 cho tab Hội đoàn thể
- `tabs/tab_uy_thac.py` dòng ~755 — Thêm hàm `_parse_date`, `_xoa_border_table`
- `tabs/tab_uy_thac.py` dòng ~770 — Thêm `_tao_word_bb_ct_cx` (Mẫu 02/BB-CT & 03/BB-CX theo VB 727/HD-NHCS)
- `tabs/tab_uy_thac.py` dòng ~940 — Thêm `_tao_word_bc_th` (Mẫu 04/BC-TH — Báo cáo tổng hợp)
- `tabs/tab_uy_thac.py` dòng ~1731 — Thêm `_render_bb_ct_cx`: nhập + lưu biên bản KT CT-XH cấp tỉnh/xã vào kv_store, xuất Word
- `tabs/tab_uy_thac.py` dòng ~1900 — Thêm `_render_theo_doi_bc_th`: theo dõi tiến độ xử lý kiến nghị + xuất Mẫu 04/BC-TH
- `tabs/tab_uy_thac.py` dòng ~2106 — Cập nhật `render()` từ 5 → 7 sub-tab (thêm "📝 Biên bản CT-XH" và "📊 Theo dõi & BC-TH")

## [2026-05-21] — Tối ưu: xóa eager import 17 modules khỏi tabs/__init__.py
- `tabs/__init__.py` — Xóa `from tabs import (tab_tongquan, ..., tab_tien_do)` (17 modules); thay bằng docstring 1 dòng. Các module này đã được lazy import qua `importlib.import_module()` từ workspaces từ 2026-05-14, nhưng `__init__.py` vẫn giữ eager import cũ gây tốn ~0.5-1.5s mỗi lần chạm package. Tiết kiệm I/O khi chuyển workspace/tab.

## [2026-05-21] — Mở rộng tab So sánh 2 kỳ: NQ11 + GQVL + Chất lượng tổ
- `db.py` dòng ~168 — thêm 3 bảng mới: `nq11_snapshot`, `gqvl_snapshot`, `cdtotkvv_snapshot` với index tương ứng
- `snapshot_service.py` — thêm `luu_nq11_snapshot()`, `doc_nq11_snapshot()`, `danh_sach_ky_nq11()`, `luu_gqvl_snapshot()`, `doc_gqvl_snapshot()`, `danh_sach_ky_gqvl()`, `luu_cdtotkvv_snapshot()`, `doc_cdtotkvv_snapshot()`, `danh_sach_ky_cdtotkvv()`
- `services/upload_service.py` dòng ~549 — cải tiến auto-snapshot: NQ11 trigger sau merge NQ11, GQVL trigger sau merge GQVL, CDTOTKVV trigger cùng HSTD (đọc latest từ pgd_data)
- `tabs/tab_so_sanh_2_ky.py` — thêm 3 expander: "📋 So sánh NQ11", "💼 So sánh GQVL", "🏆 So sánh chất lượng Tổ TK&VV"; mỗi phần có KPI cards + bảng 5 cột; CDTOTKVV thêm pie chart cơ cấu xếp loại

## [2026-05-21] — Thêm tab So sánh 2 kỳ snapshot
- `tabs/tab_so_sanh_2_ky.py` — tạo mới: chọn 2 kỳ snapshot bất kỳ, 6 KPI cards, bảng 8 chỉ tiêu, bảng/chart theo PGD (CN), xuất Excel
- `workspaces/ws_management.py` dòng ~1129 — mount "🔄 So sánh 2 kỳ" nhóm "Giám sát"
- `workspaces/ws_executive.py` dòng ~1494 — mount "🔄 So sánh 2 kỳ" nhóm "Báo cáo"
- `workspaces/ws_operation.py` dòng ~1645 — mount "🔄 So sánh 2 kỳ" với `pgd_mode=True`

## [2026-05-20] — Thêm nút chỉnh sửa cán bộ trong tab Nhân sự & Chức vụ
- `tabs/tab_khnv_noi_bo.py` `_render_nhan_su()` — thêm nút ✏️ (chỉnh sửa) bên cạnh tên từng cán bộ
- Khi bấm ✏️: hiện form inline với text input tên + selectbox chức vụ + nút 💾 Lưu / ❌ Hủy
- Layout: `[tên (5)] [✏️ (1)] [🗑️ (1)]` thay vì `[tên (6)] [🗑️ (1)]`

## [2026-05-20] — Nâng cấp UX Phân Công Công Việc + Báo cáo NĐ30
- `tabs/tab_khnv_noi_bo.py` dòng ~65 — thêm `_CHUC_VU_SHORT` hiển thị selectbox gọn: "Nguyễn A - Phó Phòng VT1"
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong_v2` — đổi format selectbox cán bộ từ emoji dài sang `_CHUC_VU_SHORT`
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong_v2` — xóa expander "✍️ Giao việc thủ công"; form nhanh đổi 2 cols → 3 cols (Mức độ / Ngày giao / Thời gian hoàn thành)
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong_v2` — đổi label "Ưu tiên" → "Mức độ", "Deadline" → "Thời gian hoàn thành"; thêm `ngay_giao` vào form
- `tabs/tab_khnv_noi_bo.py` `_render_task_card` — đổi label "Ưu tiên" → "Mức độ", "Deadline" → "Thời gian hoàn thành" trong expander Chỉnh sửa
- `tabs/tab_khnv_noi_bo.py` — thêm `_xuat_bc_phan_cong()`: Word chuẩn NĐ30, bảng 8 cột, font TNR 13pt, margin A4
- `tabs/tab_khnv_noi_bo.py` — thêm `_xuat_bc_tien_do()`: Word chuẩn NĐ30, tóm tắt I/II + bảng 8 cột
- `tabs/tab_khnv_noi_bo.py` `_render_bao_cao` — viết lại 3 phần: (1) BC Phân công Word+PDF, (2) BC Tiến độ Word+PDF, (3) Excel (header đổi "Mức độ"/"Thời gian hoàn thành") + Checklist

## [2026-05-20] — Cải thiện giao diện Tab Thông tin đầu việc Phòng KH-NV
- `tabs/tab_khnv_noi_bo.py` `_render_thong_tin_dau_viec()` — font to hơn (0.92–0.95rem), header gradient, màu chữ tương phản hơn
- `tabs/tab_khnv_noi_bo.py` cấp dưới — tách cột "Thời hạn / Sản phẩm" → 2 cột riêng: Thời hạn (tím) + Sản phẩm (xanh lá) bằng cách parse `mo_ta` tại render
- `tabs/tab_khnv_noi_bo.py` cấp dưới — thêm border-radius, border cho khung bảng, nhóm badge nền xanh đậm

## [2026-05-20] — Fix TypeError _render_bao_cao(): username passed twice (v2: pop thay filter)
- `tabs/tab_khnv_noi_bo.py` dòng ~1337 — dùng `_kw = dict(kwargs); _kw.pop("username",None); _kw.pop("role",None)` thay vì dict comprehension filter (do `_build_all_items()` đã set `kwargs["username"]`, cần `pop()` triệt để trước `**` unpack)

## [2026-05-20] — Xóa dead code column_config trong tab_tongquan
- `tabs/tab_tongquan.py` — xóa `_tao_column_config_co_cau()` và `_tao_column_config_pgd()`: được định nghĩa nhưng không bao giờ được gọi/truyền vào `st.dataframe()`
- `tabs/tab_tongquan.py` dòng ~1101 — xóa đoạn build `column_config_pgd` (dead code, bảng PGD dùng HTML table)

## [2026-05-20] — Bổ sung cột "Số món vay" vào bảng Thông tin tổng quát theo PGD
- `tabs/tab_tongquan.py` `_cache_tqpgd_extended()` dòng ~332 — thêm `so_mon=(COT_SO_KU, "nunique")` vào groupby
- `tabs/tab_tongquan.py` `cot_hien` dòng ~1084 — thêm `"Số món vay"` trước `"Số KH"`, `NHOM_COT` "Dư nợ" colspan 2→3
- `tabs/tab_tongquan.py` `_fmt_cell` dòng ~1132 — thêm `"Số món vay"` vào nhóm cột số nguyên không định dạng tiền
- `tabs/tab_tongquan.py` `column_config_pgd` dòng ~1105 — thêm `"Số món vay"` vào NumberColumn format `,.0f`

## [2026-05-20] — Sửa rule check_conventions sai toán + cập nhật CLAUDE.md tiền tệ
- `scripts/check_conventions.py` — xóa rule `_TIEN_SAI` cấm `/1e9`: rule sai về toán (1 tỷ = 1e9, `fmt_ty()` chia 1e6 → triệu, không phải tỷ)
- `CLAUDE.md` — sửa bảng tiền tệ: tách rõ `fmt_ty()` (bảng /1e6 → triệu đồng) vs `vn(x/1e9,3)+"tỷ"` (metric/card inline)

## [2026-05-20] — Header 2 dòng cho bảng Cơ cấu dư nợ theo chương trình tín dụng
- `tabs/tab_tongquan.py` dòng ~767 — thêm `column_config` với `TextColumn(label="Dư nợ\n(triệu đồng)")` cho 8 cột tiền tệ, giảm độ rộng cột bằng cách tách đơn vị xuống dòng 2

## [2026-05-20] — Seed script + giải thích nguyên nhân mất dữ liệu HSTD khi pull GitHub
- `seed_hstd_data.py` (mới) — script sinh dữ liệu HSTD mẫu (660 dòng, 36 cột, 22 đơn vị); chạy `python seed_hstd_data.py` sau pull GitHub để app hoạt động ngay, không báo thiếu dữ liệu
- `seed_hstd_data.py` — ghi đồng thời Excel (`data/HSTD_Du_lieu_tho.xlsx`) + Parquet cache (`cache/hstd.parquet`)
- Nguyên nhân: `.gitignore` loại trừ `cache/`, `data/`, `pgd_data/`, `*.xlsx` nên khi pull sang máy mới không có file dữ liệu

## [2026-05-20] — Tối ưu hiệu năng merge_du_lieu_toan_cn: bỏ apply lambda + bỏ to_numeric thừa
- `services/upload_service.py` dòng ~440 — bỏ vòng `pd.to_numeric(errors="ignore")` trên từng frame×cột trong schema normalization (không cần thiết, cột số đã xử lý trong `_clean()`)
- `services/upload_service.py` dòng ~490 — thay `.apply(lambda v: ...)` Python-level trên toàn `df_toan_cn` bằng pipeline vectorized: `pd.to_numeric` để detect float nguyên, `.fillna("").astype(str).str.strip().replace()` cho cột chuỗi

## [2026-05-20] — Redesign tab Nội bộ KH-NV: kiến trúc 6 tab + bảng tham chiếu đầu việc
- `tabs/tab_khnv_noi_bo.py` `render()` — đổi 3 sub-tab → 6 sub-tab: Nhân sự & Chức vụ / Phân công / Tiến độ / Báo cáo / Lịch / Thông tin đầu việc
- `tabs/tab_khnv_noi_bo.py` — thêm `KHNV_CAN_BO`, `_CHUC_VU_MAP/LABEL/TASK_FILTER` — mapping chức vụ → đầu việc
- `tabs/tab_khnv_noi_bo.py` — mở rộng `_MAU_GIAO_VIEC` từ 32 → 38 đầu việc (thêm nhóm I, II, IV, VII×2, VIII)
- `tabs/tab_khnv_noi_bo.py` — thêm `_MAU_GIAO_VIEC_TP`: 17 đầu việc Trưởng phòng TP01–TP17 (dữ liệu tĩnh)
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_render_nhan_su()`: Tab 1 quản lý danh sách cán bộ (VP1/VP2/CBTD)
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_render_task_card()`: helper dùng chung Tab 2+3 (card + quick buttons + edit/xóa)
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_render_phan_cong_v2()`: Tab 2 với dropdown cán bộ → đầu việc theo chức vụ, gom nhóm theo vị trí
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_render_tien_do_edit()`: Tab 3 với bộ lọc trạng thái/người + quick buttons
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_render_bao_cao()`: Tab 4 PDF tiến độ + Excel + checklist cấp trên
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_render_thong_tin_dau_viec()`: Tab 6 bảng HTML tĩnh TP01–TP17 + 38 việc nhóm I–VIII
- `tabs/tab_khnv_noi_bo.py` — thêm `_tai_mau_tu_kv()`: wrapper tải mẫu từ KHNV_CAN_BO; xóa `_render_phan_cong()` cũ
- `utils.py` import `xuat_excel` thêm vào tab_khnv_noi_bo.py; file tăng từ ~840 → ~1 100 dòng

## [2026-05-20] — Sửa bảng "Thông tin tổng quát theo PGD" — mất cột Giải ngân/Thu nợ/Nợ ĐH năm
- `tabs/tab_tongquan.py` `cot_hien` dòng ~1080 — sửa `"Lãi tồn (tỷ)"` → `"Lãi tồn (triệu đồng)"`, `"DS Cho vay (tỷ)"` → `"DS Cho vay (triệu đồng)"`, `"DS Thu nợ (tỷ)"` → `"DS Thu nợ (triệu đồng)"`; thêm `"Nợ ĐH năm (triệu đồng)"` — nguyên nhân: tên cột sau rename là `(triệu đồng)` nhưng `cot_hien` khai báo `(tỷ)` nên bị filter mất

## [2026-05-20] — Redesign tab Nội bộ Phòng KH-NV: 4 tab → 3 tab + quick status buttons
- `tabs/tab_khnv_noi_bo.py` `render()` — giảm từ 4 sub-tab → 3 sub-tab; bỏ "📊 Tiến độ thực hiện" riêng
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_render_mini_tien_do(ds, today)`: 4 metrics ngang + compact progress bars mỗi cán bộ; hiển thị ở đầu tab Phân công khi có dữ liệu
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong()` — gọi `_render_mini_tien_do()` sau guard; thêm 3 quick status buttons (🔴 Chưa làm / 🟡 Đang làm / ✅ Xong) inline trong mỗi task card — 1 click thay vì mở expander
- `tabs/tab_khnv_noi_bo.py` — xóa hàm `_render_tien_do_thuc_hien()` (~180 dòng), logic tích hợp vào mini dashboard

## [2026-05-20] — Drill-down list: hiển thị 32 đầu việc theo 8 nhóm có thể thu/mở
- `tabs/tab_khnv_noi_bo.py` `_MAU_GIAO_VIEC` — thêm trường `"nhom"` cho cả 32 entry (I-VIII), task thêm thủ công giữ nhom="" → hiện là "📌 Thêm thủ công"
- `tabs/tab_khnv_noi_bo.py` `_tai_mau_giao_viec_v2` — thêm `_nhom_ref = [""]` closure; `_mk()` đọc `_nhom_ref[0]`; đầu vòng lặp gán `_nhom_ref[0] = t.get("nhom", "")`
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong()` — thay flat for-loop bằng `nhom_groups` dict (insertion-order sorted I→VIII→📌); mỗi nhóm là `st.expander` với header: tên nhóm · N/Tổng ✅ (X%) · ⛔ N trễ

## [2026-05-20] — Chỉnh sửa toàn bộ thông tin đầu việc trong Phân công cán bộ
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong()` — đổi expander "📝 Cập nhật" → "✏️ Chỉnh sửa / Cập nhật"; thêm các trường chỉnh sửa cho admin_cn/manager_cn: Tiêu đề, Mô tả, Người thực hiện, Ưu tiên, Deadline; trạng thái + ghi chú mọi người vẫn cập nhật được; widget keys: `td_edit_`, `mota_edit_`, `nguoi_edit_`, `uu_edit_`, `dl_edit_` theo task id

## [2026-05-20] — Hoàn thiện Hướng B: expander "Tải thêm từ mẫu" ẩn cuối trang Phân công cán bộ
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong()` — thêm khối `if ds and co_quyen_ghi:` sau for-loop: expander "⚙️ Tải thêm từ mẫu" (collapsed, ở cuối), chứa form VP1/VP2 + 6 CB TD + live count + nút "✅ Tải thêm"; widget keys suffix `b` (`seed_vp1b`, `seed_vp2b`, `seed_cb_b_1…6`, `btn_seed_bottom`) tránh DuplicateElementKey với form trống-state

## [2026-05-20] — Đổi ký hiệu VP → VT trong tab Nội bộ Phòng KH-NV
- `tabs/tab_khnv_noi_bo.py` — replace_all "VP 1" → "VT 1", "VP 2" → "VT 2" (dữ liệu mẫu, logic matching, label form, fallback tên)

## [2026-05-20] — Tải đầu việc mẫu với nhân bản Cán bộ TD theo tên thực tế
- `tabs/tab_khnv_noi_bo.py` — thay `_tai_mau_giao_viec()` bằng `_tinh_so_task()` + `_tai_mau_giao_viec_v2(vp1, vp2, cbtd_list)`: nhân bản task "Cán bộ TD" × N người, xử lý đủ 8 pattern chức vụ (VP1, VP2, VP1&2, Cán bộ TD, VP1+TD, VP2+TD, VP1&2+TD, Tất cả)
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong()` — form nhập tên: 2 ô VP1/VP2 + 6 ô CB TD (3 cột); live count ước tính số task sau nhân bản; expander mở sẵn khi ds trống
- `tabs/tab_khnv_noi_bo.py` — thêm hằng số `_MAU_GIAO_VIEC` (32 đầu việc từ Bảng giao việc Trưởng phòng KH-NVTD, chia 8 nhóm I–VIII)
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_tai_mau_giao_viec(ds, username)`: append 32 task vào list + ghi_kv + audit `khnv_tai_mau_giao_viec`
- `tabs/tab_khnv_noi_bo.py` `_render_phan_cong()` — thêm nút "📥 Tải 32 đầu việc mẫu": nổi bật (primary) khi ds rỗng, ẩn trong expander khi ds đã có dữ liệu; chỉ hiện với admin_cn/manager_cn

## [2026-05-20] — Sub-tab "Tiến độ thực hiện" thay thế "Giao việc PGD" trong Nội bộ Phòng KH-NV
- `tabs/tab_khnv_noi_bo.py` — thêm hàm `_render_tien_do_thuc_hien()`: tổng hợp tự động từ `khnv_phan_cong_list`, không cần nhập liệu thêm
- `tabs/tab_khnv_noi_bo.py` — hiển thị: bộ lọc (tháng deadline / năm / cán bộ), 5 metric tổng quan, progress bar màu theo % từng cán bộ (đỏ <30 / cam 30–70 / xanh ≥70 / lá 100%), badge trễ hạn, bảng chi tiết, nút Xuất PDF
- `tabs/tab_khnv_noi_bo.py` `render()` — đổi label từ "📌 Giao việc PGD" → "📊 Tiến độ thực hiện"; thay `tab_tien_do.render()` bằng `_render_tien_do_thuc_hien()`
- `tabs/tab_khnv_noi_bo.py` — xóa import `tab_tien_do`; thêm import `defaultdict`

## [2026-05-20] — Nút PDF luôn hiển thị trong tab Nội bộ Phòng KH-NV (disabled khi trống)
- `tabs/tab_khnv_noi_bo.py` sub-tab 📋 Phân công cán bộ — nút "📥 Xuất PDF" luôn render trước danh sách; disabled (`st.button disabled=True`) khi chưa có task; active (download button) khi có dữ liệu
- `tabs/tab_khnv_noi_bo.py` sub-tab 📅 Lịch công tác — tương tự: disabled khi `ds` rỗng (toàn bộ) hoặc `ds_loc` rỗng (tháng lọc không có sự kiện)

## [2026-05-20] — Fix dark mode: chữ bảng tổng hợp PGD tối + footnote đổi sang opacity
- `tabs/tab_tongquan.py` dòng ~1186 — thêm `color:#1a202c` vào `<tr>` style để chữ đen rõ trên nền sáng (#F5F7FA/#FFFFFF/#C8E6C9) ở dark mode
- `tabs/tab_tongquan.py` dòng ~1197 — đổi `<p style="color:#6B7280">` → `<div style="opacity:0.65">` để footnote hiển thị đúng màu theo theme

## [2026-05-20] — Thêm nút "Xuất PDF" cho Phân công cán bộ và Lịch công tác
- `tabs/tab_khnv_noi_bo.py` dòng ~19 — thêm import `xuat_pdf_co_chart`, `download_pdf_button` từ `components.export_pdf`
- `tabs/tab_khnv_noi_bo.py` dòng ~117-136 — thêm nút "📥 Xuất PDF" trong sub-tab 📋 Phân công cán bộ: chuyển list dict → DataFrame (Tiêu đề, Người thực hiện, Mức ưu tiên, Ngày giao, Deadline, Trạng thái, Ghi chú) → `xuat_pdf_co_chart` với `them_dong_tong=False`
- `tabs/tab_khnv_noi_bo.py` dòng ~306-330 — thêm nút "📥 Xuất PDF" trong sub-tab 📅 Lịch công tác: tương tự, xuất danh sách đã lọc theo tháng/năm/loại (Ngày, Loại, Tiêu đề, Địa điểm, Thành viên, Ghi chú, Trạng thái)

## [2026-05-20] — Fix lỗi "Thông tin chung": KeyError 'ten_ct' (lần 3 — .rename dùng _nk.columns[0] thay vì positional)
- `tabs/tab_tongquan.py` dòng ~260,273,286,299 — đổi `_nk.columns = ["ten_ct", "..."]` → `_nk = _nk.rename(columns={_nk.columns[0]: "ten_ct", _nk.columns[1]: "..."})` cho cả 4 sub-DataFrame (_qh, _nk, _gn, _tn); nguyên nhân lần 2 (positional columns) vẫn fail nếu `_nk` không có đúng 2 cột; `.rename()` với `_nk.columns[0]` dùng tên cột thực tế từ DataFrame nên luôn match

## [2026-05-20] — Fix số tiền card "Tổng quan danh mục" sai 1000 lần (/1e6 → /1e9)
- `tabs/tab_tongquan.py` dòng ~560-566 — đổi `vn(x / 1e6, 0)` → `vn(x / 1e9, 3)` cho `tdn`, `dth`, `dqh`, `dnk`, `tdn_delta`; nguyên nhân: dữ liệu lưu VND thô, chia 1e6 ra triệu nhưng label ghi "tỷ" → sai 1000 lần
- `tabs/tab_tongquan.py` dòng ~549 — `khd_sub = fmt(dn_3m)` → `vn(dn_3m / 1e9, 3) + " tỷ đồng"` để có đơn vị

## [2026-05-20] — UI: card "Tổng quan danh mục" to rõ hơn, căn giữa như "Xếp loại tổ"
- `tabs/tab_tongquan.py` dòng ~486-497 — tăng `.val` font-size `2.05rem→2.4rem`; thêm `text-align:center`; đậm màu nền soft-* (dbeafe/dcfce7/fee2e2/fef3c7...); thêm CSS variable `--tq-num`/`--tq-label` cho màu số và nhãn theo scheme màu; thu nhỏ h4 xuống `0.82rem` để số nổi bật hơn

## [2026-05-20] — Tạo tab "Nội bộ Phòng KH-NV" (tab_khnv_noi_bo.py)
- `tabs/tab_khnv_noi_bo.py` (tạo mới) — 4 sub-tab: 📋 Phân công cán bộ, 📅 Lịch công tác, 📤 Báo cáo cấp trên (wrapper), 📌 Giao việc PGD (wrapper)
- `tabs/tab_khnv_noi_bo.py` — kv_store keys: `khnv_phan_cong_list` + `khnv_lich_list`, audit đầy đủ, phân quyền admin_cn/manager_cn toàn quyền, chuyenvien_cn/executive chỉ xem + cập nhật trạng thái
- `workspaces/ws_management.py` dòng ~1116 — thêm item `🗂️ Nội bộ Phòng KH-NV` vào nhóm "Phối hợp với PGD"

## [2026-05-20] — Fix lỗi "Thông tin chung": category sum — lần 4 (COT_DU_NO_QH sót conversion + thêm .astype(object))
- `tabs/tab_tongquan.py` dòng ~227 — thêm `.astype(object)` trong vòng lặp `_COLS_TO_SUM` (cùng pattern fix `hstd.py`): Categorical không bị strip nếu thiếu bước này
- `tabs/tab_tongquan.py` dòng ~256 — đổi `.groupby()[COT_DU_NO_QH].sum()` → `.apply(lambda x: pd.to_numeric(x, errors="coerce").sum())` nhất quán với `col_khoanh`/`col_gn`

## [2026-05-20] — Fix lỗi "category type does not support sum operations" lần 3 (tận gốc)
- `tabs/tab_tongquan.py` — 4 cached function (`_cache_kpi_tongquan`, `_cache_heatmap_pgd`, `_cache_co_cau_ct`, `_cache_tqpgd_extended`): bỏ `hasattr(..., 'cat')`, dùng `pd.to_numeric` không điều kiện; `hasattr` không detect được category dtype trong 1 số trường hợp Parquet edge case
- `tabs/tab_tongquan.py` — thêm convert numeric cho `_cache_heatmap_pgd` (trước đây chưa có convert nào)

## [2026-05-20] — Đổi đơn vị KPI "3 tháng không hoạt động" từ triệu → đồng
- `workspaces/ws_management.py` dòng ~272 — `k3.metric("Lãi tồn (triệu đồng)", vn(tong_lai/1e6, 0))` → `k3.metric("Lãi tồn (đồng)", fmt(tong_lai))`: bỏ chia 1e6, đổi label
- `workspaces/ws_operation.py` dòng ~320 — `k3.metric("Lãi tồn cần thu (triệu đồng)", fmt(tong_lai))` → `k3.metric("Lãi tồn cần thu (đồng)", fmt(tong_lai))`: sửa label cho đúng (giá trị đã là VND raw)

## [2026-05-20] — Review & update rules.md + 3 file .md mới
- `.trae/rules/rules.md` — sửa 6 điểm: thêm 19 COT_* constants, sửa `movers_analysis` (thiếu 3 params), sửa `pgd_slug` (utils→data/pgd), thêm 3 utils functions (`auto_audit`, `auto_fill_batch`, `lazy_tabs`), sửa `get_permissions` (bỏ pgd_user), thêm 3 auth functions (`la_chuyen_vien_cn`, `co_quyen_giao_nhiem_vu`, `la_admin_cn`)
- `BUGMAP.md` — tạo mới: bản đồ lỗi A→I (12 bugs), template ghi nhận bug, lệnh debug nhanh
- `FILE_INDEX.md` — tạo mới: index dòng cho 7 file lớn (upload_service, ws_management, ws_operation, tab_no_khoanh, tab_no_rui_ro, ws_executive, config/auth/db/utils/data)
- `PROMPT_TEMPLATE.md` — tạo mới: 5 template (bugfix, thêm tính năng, upload, báo cáo, fix UI) + checklist

## [2026-05-20] — Fix lỗi "Sức khỏe tín dụng": cannot subtract DatetimeArray from Categorical
- `data/hstd.py` dòng ~238-240 — thêm `.astype(object)` trước `pd.to_datetime()` cho 3 cột ngày (`COT_NGAY_SL`, `COT_NGAY_GDGN`, `COT_NGAY_VAY`); nguyên nhân: Parquet cache lưu cột ngày dạng Categorical, pandas không tự convert sang datetime khi subtract

## [2026-05-20] — Fix lỗi Tổng Quan Chi Nhánh trắng: _load_hstd trả về DataFrame rỗng
- `app.py` dòng ~134 — `duckdb.query().arrow()` trả về `RecordBatchReader` (không có `.to_pandas()`), bị catch thầm lặng → `pd.DataFrame()` rỗng; fix: đổi sang `.to_arrow_table().to_pandas(self_destruct=True)`

## [2026-05-20] — Fix tổng hợp thủ công chậm/treo: string cleanup 27s → 0.7s
- `services/upload_service.py` dòng ~484 — thay `for _c in _str_cols: astype(str).str.strip()` (164 cột × 349K dòng = 27s) bằng `df[obj_cols].fillna('')` (17 cột object = 0.7s, nhanh hơn 38×)
- Root cause: cột non-object (157/174 cột) bị xử lý thừa; `.astype(str)` allocate string mới toàn bộ DataFrame cho mỗi cột

## [2026-05-20] — Fix bug _cache_co_cau_ct: COT_NGUON_VON alignment crash
- `tabs/tab_tongquan.py` dòng ~212 — fix `_df_loc.get(COT_NGUON_VON, Series())` → crash index alignment khi cột thiếu; thay bằng `if col in columns` với fallback `Series(0, index=_df_loc.index)`
- `tabs/tab_tongquan.py` dòng ~225 — xóa dead code `rename(columns={"COT_TEN_CT": "ten_ct"})` (rename literal string không đổi tên cột)

## [2026-05-20] — Fix _cache_co_cau_ct/tqpgd_extended: category type does not support sum operations
- `tabs/tab_tongquan.py` dòng ~214-224 — thêm `_COLS_TO_SUM` convert category→numeric ở đầu `_cache_co_cau_ct` cho tất cả cột sẽ bị sum
- `tabs/tab_tongquan.py` dòng ~146-149 — thêm convert category→numeric ở đầu `_cache_kpi_tongquan`
- `tabs/tab_tongquan.py` dòng ~316-324 — thêm `_COLS_TO_SUM_PGD` convert category→numeric ở đầu `_cache_tqpgd_extended`
- Nguyên nhân gốc: 3 cached function dùng `.sum()`/`.agg(..., "sum")` trên DataFrame có cột dtype `category` (do đọc từ Parquet), pandas CategoricalArray không hỗ trợ sum

## [2026-05-20] — Tối ưu tốc độ chuyển tab ws_management: lazy import + cache
- `workspaces/ws_management.py` dòng ~46 — xóa 18 static import tab, thay bằng `_get_tab()` với `@st.cache_resource` (lazy import giảm 30–50% cold start)
- `tabs/tab_tongquan.py` dòng ~198 — thêm `_cache_co_cau_ct()` với `@st.cache_data(ttl=120)` cache groupby chương trình tín dụng (~7 groupby thành 1 cached call)
- `tabs/tab_tongquan.py` dòng ~273 — thêm `_cache_tqpgd_extended()` với `@st.cache_data(ttl=120)` cache toàn bộ bảng tổng quan PGD (~8 groupby/merge thành 1 cached call)
- `workspaces/ws_management.py` — revert @st.fragment (gây lỗi navigation do closure stale)

## [2026-05-20] — Tăng tốc dashboard Nợ Khoanh: batch query + cache
- `tabs/tab_qlnk_dashboard.py` dòng ~42 — thêm `_cached_ket_qua_kiem_tra()` với `@st.cache_data(ttl=60)` thay cho gọi DB trực tiếp mỗi render
- `tabs/tab_qlnk_dashboard.py` dòng ~48 — `_doc_ly_do_khoanh()` dùng `db.doc_bo_sung_nhieu_mon_vay()` batch IN-clause thay N+1 loop (tiết kiệm 100–500 SQL query/render)
- `db.py` — `doc_bo_sung_nhieu_mon_vay()` batch query đã thêm session trước

## [2026-05-20] — Fix ValueError "truth value of DataFrame ambiguous" tab Nợ Khoanh
- `tabs/tab_no_khoanh.py` dòng 834 — đổi `kwargs.get("df_full") or df` → `df if _df_full is None else _df_full`; `or` không dùng được với DataFrame

## [2026-05-20] — Tăng tốc merge thủ công (string cleanup vectorized)
- `services/upload_service.py` dòng ~485 — thay per-cell Python loop `to_numpy + list comprehension` bằng `astype(str).str.strip() + where()` vectorized; nhanh hơn ~30× với HSTD 50k+ dòng

## [2026-05-20] — Xóa dead code kế hoạch kiểm tra (old flow trước CV368)
- `tabs/tab_no_khoanh.py` dòng 51–53 — xóa `_cached_ke_hoach_kiem_tra()`: wrapper không có caller nào
- `db.py` — xóa `doc_ke_hoach_kiem_tra()` và `luu_ke_hoach_kiem_tra()`: cả hai đã được thay thế bởi `luu_mau_bieu_cv368` / `doc_mau_bieu_cv368`; giữ `luu_ket_qua_kiem_tra` vì QLNK_06 vẫn cần

## [2026-05-20] — Fix tab "Chuyên đề nợ khoanh" báo không có dữ liệu HSTD
- `tabs/tab_no_khoanh.py` dòng 838 — đổi `kwargs.get("df_full", df)` → `kwargs.get("df_full") or df`: khi `df_full=None` truyền tường minh (ws_operation PGD mode), fallback đúng về `df` thay vì giữ `None`

## [2026-05-20] — Fix KPI card nền trắng chữ trắng trong dark theme
- `components/delta_card.py` dòng ~61 — thêm `border=True` vào `st.metric()`: Streamlit 1.57 mới có param này, tự apply `secondaryBackgroundColor` (#1E2130) làm nền card
- `utils_theme.py` dòng ~195 — bỏ `background`/`border`/`border-radius`/`padding` override (nay do Streamlit native xử lý); giữ `border-left` accent + `box-shadow`

## [2026-05-20] — Fix chữ đen trong dark theme (heatmap + sidebar labels)
- `workspaces/ws_executive.py` dòng ~297 — đổi màu bảng heatmap PGD: row bg `#fff`→`#1E2130`, border `#d1d5db`→`#2A2D3E`, text NQH/RR sáng hơn; chữ row mặc định thêm `color:#E0E6ED`
- `workspaces/ws_executive.py` dòng ~187 — span `color:#1565C0` → `#90CAF9` (đọc được trên nền tối)
- `workspaces/ws_executive.py` dòng ~348,1500,1521 — footnote gray `#6b7280`→`#94A3B8`; GROUP_COLORS & header sidebar đổi sang tone sáng dark-mode
- `workspaces/ws_management.py` dòng ~1193,1219 — GROUP_COLORS & header "MENU ĐIỀU HÀNH" đổi sang tone sáng dark-mode

## [2026-05-20] — Hoàn tất xóa Block 3 trong tab_no_khoanh.py
- `tabs/tab_no_khoanh.py` dòng ~1372-1721 — xóa hoàn toàn block `with d_kt:` thứ ba (show_mb + 4 expander xuất PDF QLNK cũ); tab giờ chỉ dùng `_render_cv368_kt()` mới

## [2026-05-19] — Gộp ba with d_kt: thành một lời gọi _render_cv368_kt()
- `tabs/tab_no_khoanh.py` dòng ~1058 — thay thế Block 1 (kế hoạch kiểm tra), Block 2 (nhập kết quả KT) và Block 3 (xuất mẫu biểu) bằng một `with d_kt: _render_cv368_kt(...)` duy nhất

## [2026-05-19] — Chuyển "Cán bộ tín dụng" xuống cuối nhóm Ủy Thác
- `workspaces/ws_management.py` — di chuyển "👤 Cán bộ tín dụng" xuống sau "Điểm GD & Tổ TK&VV"

## [2026-05-19] — Tối ưu RAM load HSTD
- `app.py` — thêm `_toi_uu_dtype()`: category string ≤200 unique, float32 cho cột nhỏ, downcast int
- `app.py` — `_load_hstd`: đổi `.df()` → `.arrow().to_pandas(self_destruct=True)` + áp dụng `_toi_uu_dtype`

## [2026-05-19] — Baseline 31/12 hỗ trợ 4 loại file + nút tổng hợp thủ công
- `config.py` — thêm `baseline_pgd_path_loai()`, `trang_thai_baseline_pgd_loai()`, `baseline_cache_loai()`, hằng `LOAI_BASELINE`; cập nhật `danh_sach_nam_baseline_pgd()` quét cả 4 loại
- `services/upload_service.py` — thêm `merge_baseline_toan_cn(loai, nam)` gộp 22 đơn vị baseline → parquet cache
- `tabs/tab_upload_khnv.py` — mục baseline nhận diện cả 4 loại (HSTD/NQ11/GQVL/CDTOTKVV), hiển thị trạng thái 4 loại, lưu theo `baseline_pgd_path_loai`; thêm expander tổng hợp thủ công baseline

## [2026-05-19] — Fix vi phạm convention: tab_gqvl, tab_baocao, tab_khtd_pgd, tab_hhi
- `auth.py` — thêm helper `la_executive(role)`
- `tabs/tab_gqvl.py`, `tab_baocao.py`, `tab_khtd_pgd.py` — thay `role != "executive"` → `not la_executive(role)`
- `tabs/tab_hhi.py` — thay `/1e9` → `/1_000_000`; đổi `tong_du_no_ty` → `tong_du_no_trieu`; cập nhật chart label "(triệu đồng)"
- `tabs/tab_baocao.py` — thêm `# noqa: COT` cho cột display name sau agg rename

## [2026-05-19] — Fix vi phạm convention: tab_kehoach role == "executive"
- `auth.py` — thêm helper `la_executive(role)`
- `tabs/tab_kehoach.py` — import `la_executive`; thay 2 lần `role == "executive"` → `la_executive(role)`

## [2026-05-19] — Fix vi phạm convention: auth.py, tab_tien_do, tab_so_sanh_ky
- `auth.py` — thêm helper `la_admin_cn(role)`; fix `row["Tên PGD"]` → `row[COT_TEN_PGD]`; fix `role == "admin"` → `la_admin_cn(role)` (dòng 990)
- `tabs/tab_tien_do.py` — import `la_admin_cn`; thay `role == "admin_cn"` → `la_admin_cn(role)`
- `tabs/tab_so_sanh_ky.py` — thay `/1e9` → `/1_000_000`; đổi `dn_ty` → `dn_trieu`; cập nhật axis title "(triệu đồng)"

## [2026-05-19] — Fix vi phạm convention trong widgets/data_source_status.py
- `widgets/data_source_status.py` — thay `role == "user"` và `role in ["admin", "manager"]` bằng `normalize_role()` + `la_phan_he_pgd()`

## [2026-05-19] — Fix triệt để bảng Cơ cấu dư nợ + 193 lỗi width='stretch' toàn dự án
- `tabs/tab_tongquan.py` — fix 4 bug: (1) `width='stretch'` → `use_container_width=True`; (2) tên cột đơn vị sai "(tỷ)" → "(triệu đồng)" cho TW, ĐP, Giải ngân, Thu nợ; (3) chart xaxis_title sai; (4) bỏ `column_config` vô dụng trên cột string
- **37 file toàn dự án** — thay 193 lần `width='stretch'` → `use_container_width=True` (Streamlit 1.57.0 không hỗ trợ `width='stretch'`)

## [2026-05-19] — Gộp 3 tab thành "Quản lý Công việc & Nhiệm vụ"
- `tabs/tab_quan_ly_cv.py` — tạo mới: wrapper gộp tab_tien_do + tab_nhiem_vu + tab_quan_ly_bc thành 3 sub-tab
- `workspaces/ws_management.py` — thay 3 dòng menu riêng lẻ bằng 1 mục "📊 Quản lý Công việc & Nhiệm vụ"

## [2026-05-19] — Đổi tên 2 mục menu ws_management
- `workspaces/ws_management.py` dòng ~1132 — "Quản lý Báo cáo định kỳ" → "Quản lý Báo cáo"; "Nhiệm vụ PGD" → "Quản lý Nhiệm vụ PGD"

## [2026-05-19] — Đồng bộ CONVENTIONS.md vào Trae rules
- `.trae/rules/rules.md` — append toàn bộ nội dung CONVENTIONS.md (9 lỗi bị cấm + patterns) vào cuối file rules

## [2026-05-19] — Merge docs/CONVENTIONS.md vào root, xóa bản trùng
- `CONVENTIONS.md` (root) — bổ sung: bảng 9 roles + compat, audit action table đầy đủ, fmt examples kèm công thức /1e12, CSS/UI guidelines, Streamlit version notes
- `docs/CONVENTIONS.md` — xóa (đã merge toàn bộ nội dung vào root)

## [2026-05-19] — Bổ sung CONVENTIONS.md: role table, pgd_mode, component API
- `CONVENTIONS.md` — thêm bảng 7 role đầy đủ (bao gồm chuyenvien_cn); thêm pgd_mode pattern; thêm component API signatures chuẩn (kpi_row, download_pdf_button, loan_detail_drawer, filter_bar)

## [2026-05-19] — Viết CONVENTIONS.md từ STABLE.md + CHANGELOG
- `CONVENTIONS.md` — tạo mới: 9 lỗi bị cấm, conventions tích cực, checklist trước khi sinh code

## [2026-05-19] — Fix báo cáo GQVL TW gắn MĐT không tìm thấy cột PL NV
- `services/kiem_soat_service.py` — thêm import `COT_PL_NV`; đổi hardcode `"PL NV"` → `COT_PL_NV` ("Phân loại NV") vì cột đã được rename khi merge

## [2026-05-19] — Chuyển "Nhiệm vụ PGD" sang nhóm "Phối hợp với PGD"
- `workspaces/ws_management.py` — đổi group "📌 Nhiệm vụ PGD" từ "Giám sát" sang "Phối hợp với PGD", ngang cấp với "Tiến độ Công việc" và "Quản lý Báo cáo định kỳ"

## [2026-05-19] — Tạo tab_quan_ly_bc, tái cấu trúc menu Báo cáo
- `tabs/tab_quan_ly_bc.py` — tạo mới: wrapper 2 sub-tab "📥 BC từ PGD" (tab_tien_do_nop) + "📤 BC lên cấp trên" (tab_checklist_bc)
- `workspaces/ws_management.py` — thêm import tab_quan_ly_bc; xóa child "Tiến độ Báo cáo của PGD" khỏi accordion; xóa "Checklist định kỳ"; thêm "📋 Quản lý Báo cáo định kỳ" vào nhóm "Phối hợp với PGD"; đổi "✅ Nhiệm vụ" → "📌 Nhiệm vụ PGD"

## [2026-05-19] — Tách "Thông tin chung" lên đầu menu Điều hành
- `workspaces/ws_management.py` — đưa "📊 Thông tin chung" lên vị trí đầu tiên trong ALL_ITEMS (mặc định khi mở app); xóa bản duplicate "📊 Giám sát" cũng render tab_tongquan; sửa icon emoji "Tiến độ công việc"

## [2026-05-19] — Fix DuplicateElementKey menu sidebar ws_management
- `workspaces/ws_management.py` dòng ~1132 — xóa item trùng label "📊 Thông tin chung" (group "Thông tin chung" là bản duplicate cũ, giữ lại bản trong group "Giám sát")

## [2026-05-19] — Drill-down thêm option "Tất cả", đổi nhãn "PGD trực thuộc"
- `tabs/tab_tien_do.py` dòng ~253 — selectbox drill-down thêm "— Tất cả —" đầu danh sách; khi chọn Tất cả hiển thị toàn bộ bản ghi kèm cột "Đơn vị"; caption/info dùng label động
- `tabs/tab_tien_do.py` — đổi nhãn "Phòng giao dịch huyện/thị xã" → "Phòng giao dịch trực thuộc" (form tạo + sửa task)

## [2026-05-19] — Cải tiến UI section "Áp dụng cho đơn vị" trong form tạo/sửa đầu việc
- `tabs/tab_tien_do.py` dòng ~379 — thêm caption tổng quan, tách nhãn Phần A (PGD huyện/thị xã) + Phần B (Hội sở CN tỉnh), di chuyển caption thống kê sau lưới checkbox, thêm caption hướng dẫn từng phần
- `tabs/tab_tien_do.py` dòng ~602 — áp dụng cấu trúc tương tự cho form sửa task; gộp caption "Danh sách không đổi" vào caption PGD
- `tabs/tab_tien_do.py` — đổi nhãn "CB Biên Hòa" → "Hội sở CN tỉnh" ở bảng tổng quan, info task, sheet Excel xuất báo cáo

## [2026-05-19] — Fix TypeError tab NQ11: Invalid comparison between dtype=str and int
- `tabs/tab_nq11.py` dòng ~108 — thêm `pd.to_numeric()` cho các cột số (DNO, nợ TH, nợ QH, số tiền, dư nợ, GN) sau khi load df_nq11 để tránh lỗi ArrowDtype string so sánh với int

## [2026-05-19] — Chuyên Đề Nợ Khoanh: tách 2 children dropdown (Tổng quan / Quản lý CV368)
- `tabs/tab_no_khoanh.py` dòng ~1564 — thêm kwarg `nhom` ("tongquan"/"cv368"/None); tách st.tabs() theo nhom; guard d0/loop/d4; early return trước d_kt khi nhom="tongquan"
- `workspaces/ws_management.py` dòng ~1150 — đổi item đơn thành `children` 2 mục: "📊 Tổng quan Nợ Khoanh" và "🔒 Quản lý Nợ Khoanh theo CV 368" (dropdown xổ xuống như Cảnh báo NQH)
- `workspaces/ws_operation.py` dòng ~1687 — tách 1 tuple thành 2 tuple riêng tương ứng
- `alert_center.py` dòng ~151 — cập nhật `ws_mgmt_jump` trỏ đúng child label CV368

## [2026-05-19] — Tiến độ: thêm CB KH-NV phụ trách + CB Biên Hòa cho từng đầu việc
- `db.py` — migration thêm cột `nguoi_thuc_hien_cn`, `cbtd_bien_hoa` vào `tien_do_task`
- `tabs/tab_tien_do.py` — form tạo/sửa: thêm "👤 Cán bộ phòng KH-NV phụ trách" và section "🏛️ Địa bàn Biên Hòa"; lưu DB; sync dòng "Địa bàn Biên Hòa" vào `tien_do_ketqua`; tổng quan/xuất Excel/PDF/cập nhật tiến độ hiển thị & xử lý tương ứng

## [2026-05-19] — Đổi tên tab "Nợ Khoanh" → "Chuyên Đề Nợ Khoanh" toàn hệ thống
- `workspaces/ws_management.py` dòng ~1150 — label menu sidebar: `"🔒 Nợ Khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `workspaces/ws_operation.py` dòng ~1686 — label tab PGD: `"🔒 Nợ khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `alert_center.py` dòng ~151 — `ws_mgmt_jump` key khớp label mới
- `tabs/tab_no_khoanh.py` dòng ~1444 — subheader: `"🔒 Phân tích Nợ khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `tabs/tab_qlnk_dashboard.py` dòng ~127,231 — subheader và hint text cập nhật tên mới

## [2026-05-19] — Kiểm soát: Thêm báo cáo GQVL TW gắn MANDT
- `services/kiem_soat_service.py` — thêm báo cáo "🧾 Rà soát GQVL TW – Gắn MANDT" vào droplist nhóm "🔍 Giám sát nội bộ"; KPI + bảng + xuất Excel; lọc CT=3, NV=1, PL NV=02, có MANDT, OPEN

## [2026-05-19] — Fix lỗi ws_operation: tab None gây crash context manager
- `workspaces/ws_operation.py` — thay `with tab_parent:` bằng `with get_tab_context(tab_parent):` cho các renderer (Histogram/Donut/...) để chạy được khi tab=None

## [2026-05-19] — Đổi tên tab "Nợ Khoanh" → "Chuyên Đề Nợ Khoanh" toàn hệ thống
- `workspaces/ws_management.py` dòng ~1150 — label menu sidebar: `"🔒 Nợ Khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `workspaces/ws_operation.py` dòng ~1686 — label tab PGD: `"🔒 Nợ khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `alert_center.py` dòng ~151 — `ws_mgmt_jump` key khớp label mới
- `tabs/tab_no_khoanh.py` dòng ~1444 — subheader: `"🔒 Phân tích Nợ khoanh"` → `"🔒 Chuyên Đề Nợ Khoanh"`
- `tabs/tab_qlnk_dashboard.py` dòng ~127,231 — subheader và hint text cập nhật tên mới

## [2026-05-19] — tab_tracuu: bổ sung Ngày sinh, Ngày cấp CMND, Nơi cấp CMND
- `tabs/tab_tracuu.py` — import 3 constant mới; thêm vào `COLS_CAN` để đọc từ parquet; thêm vào `_NHOM_TRUONG["👤 Khách hàng"]`

## [2026-05-19] — Chuẩn mẫu PDF Cam kết trả nợ (Mẫu 02/QLNK)
- `tabs/tab_no_khoanh.py` — cập nhật `_xuat_pdf_mau_02qlnk()` theo bố cục mẫu; tự điền thêm SĐT/địa chỉ/Ngày sinh/Ngày cấp+Nơi cấp CMND/ĐVUT/Tổ (fallback dấu chấm) và chỉnh câu kết “... trước pháp luật./”

## [2026-05-19] — Fix lỗi tab Ban Đại Diện: TypeError truediv on str dtype
- `tabs/tab_ban_dai_dien.py` dòng ~142 — thêm helper `_num()` dùng `pd.to_numeric(errors='coerce')` cho tất cả cột số trong `_tong_hop_theo_pgd()` trước khi chia 1e6

## [2026-05-19] — Thêm xuất PDF Kế hoạch kiểm tra nợ khoanh (theo NĐ 30)
- `tabs/tab_no_khoanh.py` — thêm `_xuat_pdf_ke_hoach_kt()`: PDF A4/landscape (>20 món), header 2 cột NĐ 30, bảng phân công gộp nhóm tổ có SPAN, thành phần tham gia, footer ký duyệt
- `tabs/tab_no_khoanh.py` — expander "Lập kế hoạch": thêm section "Thành phần tham gia kiểm tra" (5 text_input) + nút "📄 Xuất PDF Kế hoạch" (hiện khi có dữ liệu hoặc kế hoạch đã lưu)

## [2026-05-19] — Gộp Kế hoạch + Kiểm tra + Mẫu biểu thành tab "Kiểm tra nợ khoanh (theo CV 368)"
- `tabs/tab_no_khoanh.py` — đổi 8 → 7 st.tabs; gộp d5 (Kế hoạch) + d6 (Kiểm tra) + mẫu biểu vào d_kt "📋 Kiểm tra nợ khoanh (theo CV 368)"; d_bc "📊 Báo cáo" giữ M08/M09/QLNK_06/M10/Tiến độ; pgd_filter_bc/rows_all_kt/da_kiem_tra_set chuyển trước st.tabs

## [2026-05-19] — Gộp tab_qlnk_dashboard vào tab_no_khoanh làm sub-tab Tổng quan
- `tabs/tab_no_khoanh.py` — import tab_qlnk_dashboard; đổi 7 → 8 st.tabs, thêm d0 "📊 Tổng quan" gọi tab_qlnk_dashboard.render()
- `workspaces/ws_management.py` — xóa cấu trúc children 2 mục → 1 entry "🔒 Nợ Khoanh" duy nhất

## [2026-05-19] — Gộp 2 mục Nợ Khoanh thành 1 tab trong ws_management
- `workspaces/ws_management.py` dòng ~1150 — xóa cấu trúc "children" 2 mục riêng; thay bằng 1 entry "🔒 Nợ Khoanh" gọi cả tab_qlnk_dashboard lẫn tab_no_khoanh trong cùng 1 fn

## [2026-05-19] — Thêm đơn vị vào card metric tại tab Nợ khoanh & Tổng hợp nợ khoanh
- `tabs/tab_no_khoanh.py` dòng ~1295 — 4 KPI cards: "Số món khoanh" → thêm " món", "Số hộ" → thêm " hộ"
- `tabs/tab_no_khoanh.py` dòng ~1962, 2000 — "Số món chưa kiểm tra" / "Số món có KN trả nợ" → thêm " món"
- `tabs/tab_no_khoanh.py` dòng ~2075, 2145 — "Số bản ghi" / "Số bản ghi lưu tạm" → thêm " bản ghi"
- `tabs/tab_qlnk_dashboard.py` dòng ~179, 188 — "Tổng món khoanh" → thêm " món"; "Sắp hết hạn khoanh" → thêm " món"

## [2026-05-19] — Cập nhật Chay_VBSP_SCM.bat: bỏ taskkill, bật watchdog, đơn giản hóa khởi động
- `Chay_VBSP_SCM.bat` — xóa taskkill python/streamlit; bỏ --server.fileWatcherType none (bật lại watchdog auto-reload); thay vòng poll 60s bằng timeout /t 3 rồi mở browser

## [2026-05-19] — Gộp tab Nợ khoanh & Tổng hợp nợ khoanh thành tab phụ của Chuyên đề Nợ Khoanh
- `workspaces/ws_management.py` dòng ~1148 — thay 2 item riêng "🔒 Nợ khoanh" và "📊 Tổng hợp nợ khoanh" bằng 1 parent item "🔒 Chuyên đề Nợ Khoanh" có children; giữ nguyên hàm render, chỉ tổ chức lại menu sidebar

## [2026-05-19] — Chuẩn đơn vị tiền tệ bảng tổng hợp/chi tiết tab Nợ Khoanh
- `tabs/tab_no_khoanh.py` dòng ~88 — `_bang_theo_nhom`: đổi tên cột thành "Dư nợ khoanh (triệu đồng)" để rõ đơn vị trong bảng d1/d2/d3
- `tabs/tab_no_khoanh.py` dòng ~1459 — d5 Kế hoạch data_editor: đổi fmt_ty → _fmt_dong vì đây là danh sách từng món

## [2026-05-19] — Fix: _fmt_dong dùng fmt_so thay vì fmt để hiện đủ số đồng
- `tabs/tab_no_khoanh.py` dòng ~56 — `_fmt_dong`: đổi `fmt()` (chia 1M ra triệu) → `fmt_so()` (giữ nguyên số, chỉ format dấu chấm); kết quả: "44.000.000 đồng" thay vì "44 đồng"

## [2026-05-19] — Fix: db.py thiếu cột ngay_kiem_tra trong bảng qlnk_ke_hoach (lần 2)
- `db.py` dòng ~233 — tách `CREATE INDEX idx_qlnk_kh_ngay` ra khỏi `executescript` để tránh lỗi khi bảng cũ chưa có cột
- `db.py` dòng ~278 — đặt CREATE INDEX sau ALTER TABLE migration, wrapped trong try-except

## [2026-05-19] — Đổi format tiền danh sách chi tiết Nợ Khoanh sang đơn vị đồng
- `tabs/tab_no_khoanh.py` — thêm helper `_fmt_dong` (fmt + " đồng"); áp dụng cho d4 (Danh sách chi tiết), M08, M10, QLNK_06; bảng tổng hợp Theo CT/Xã/DVUT giữ nguyên fmt_ty

## [2026-05-19] — Chuẩn hóa tên PGD "Đồng Nai" → "Hội sở Chi nhánh tỉnh" trong tab Nợ Khoanh
- `tabs/tab_no_khoanh.py` dòng ~1223 — thêm bước replace alias sau `_loc_khoanh()`: "Đồng Nai", "Chi nhánh Đồng Nai", "CN Đồng Nai", "Hội sở" đều map về `DON_VI_CHI_NHANH`; import thêm `DON_VI_CHI_NHANH` từ config

## [2026-05-19] — Đổi trục biểu đồ phân bổ nợ khoanh sang năm hết hạn khoanh nợ
- `tabs/tab_no_khoanh.py` dòng ~130 — `_heatmap_dao_han()`: đổi cột nguồn từ `COT_NGAY_DH` (ngày đáo hạn) sang `COT_NGAY_HH_KHOANH` ("Ngày hết hạn Khoanh"); cập nhật tiêu đề chart và label markdown

## [2026-05-19] — Fix: cache không được xóa sau khi merge 22 PGD
- `tabs/tab_upload_khnv.py` dòng ~1501 và ~1392 — thêm xóa session_state keys (`_ctx`, `_ctx_cache_key`, `df_full`...) sau merge để buộc app.py reload data mới từ parquet; trước đây chỉ `cache_data.clear()` không đủ vì `_load_hstd` dùng `@st.cache_resource`

## [2026-05-19] — Fix: merge_du_lieu_toan_cn lỗi fillna("") trên ArrowDtype(int64)
- `services/upload_service.py` dòng ~487 — trước `fillna("")`, convert ArrowDtype columns về `object` để tránh lỗi `pyarrow.lib.ArrowInvalid: Could not convert '' with type str: tried to convert to int64`

## [2026-05-19] — Phase 4: Cảnh báo nợ khoanh sắp hết hạn + badge sidebar + shortcut jump
- `alert_center.py` — Task 4.1: thêm `canh_bao_no_khoanh_sap_het_han(df_kh)` parse ngày, tính `con_lai`, phân loại ≤30 ngày (khan) vs 31-180 ngày (cảnh báo); Task 4.2: thêm `render_badge_no_khoanh_sap_het_han()` + `_get_khoanh_alert_data()` cache 600s; tích hợp vào `render_alert_sidebar()` hiển thị 🔴/🟠 nút bấm badge
- `alert_center.py` — Task 4.3: click badge → set `st.session_state.ws_mgmt_jump = "🔒 Nợ khoanh"` + `st.session_state._qlnk_filter = "sap_het_han"` → `st.rerun()`
- `tabs/tab_no_khoanh.py` — Task 4.3: pop `_qlnk_filter`, nếu `== "sap_het_han"` → hiển thị bảng M03 lọc món có `con_lai ≤ 180`, sắp xếp theo ngày còn lại
- `app.py` — không cần sửa vì `render_alert_sidebar()` đã được gọi sẵn trong sidebar

## [2026-05-19] — Fix: KPI tab Nợ khoanh sai khi lọc theo PGD
- `tabs/tab_no_khoanh.py` — đảo thứ tự: filter PGD thực hiện TRƯỚC khi tính KPI
- KPI (Số món, Số hộ, Tổng khoanh) nay tính từ `df_kh` đã filter; tỷ lệ khoanh/tổng dùng `use_df_scope` cùng scope PGD

## [2026-05-19] — Phase 3 Task 3.1+3.2: Dashboard Tổng hợp Nợ khoanh
- `tabs/tab_qlnk_dashboard.py` — **TẠO MỚI**: Dashboard KPI + biểu đồ tròn lý do khoanh (Plotly) + cột ngang dư nợ theo PGD + Top 10 món khoanh lớn nhất; KPI: Tổng món khoanh, Tỷ lệ kiểm tra, Sắp hết hạn, Dư nợ khoanh; dùng `db.doc_bo_sung_mon_vay()` để lấy lý do khoanh từ qlnk_bo_sung
- `workspaces/ws_management.py` — thêm `tab_qlnk_dashboard` import; thêm menu "📊 Tổng hợp nợ khoanh" vào nhóm Kiểm soát
- `workspaces/ws_executive.py` — thêm `tab_qlnk_dashboard` import; thêm menu "📊 Tổng hợp nợ khoanh" vào nhóm Cảnh báo rủi ro

## [2026-05-19] — Fix: Thêm hàm stub doc_ke_hoach_kiem_tra(), luu_ke_hoach_kiem_tra(), duyet_ke_hoach() vào db.py
- `db.py` — 3 hàm stub (trả về [] hoặc True) để tránh ModuleNotFoundError khi render tab Nợ khoanh
- Các hàm này chưa có implementation đầy đủ — TODO trong PR tiếp theo

## [2026-05-19] — Phase 2: Hoàn thiện báo cáo QLNK_06, M10 (Haiku + reportlab)
- `tabs/tab_no_khoanh.py` dòng ~933–1105 — thêm 2 hàm PDF: `_xuat_pdf_qlnk_06()` (báo cáo tổng hợp, 19 cột), `_xuat_pdf_m10()` (danh sách chưa nhập)
- `tabs/tab_no_khoanh.py` dòng ~1706–1843 — thêm QLNK_06 expander: filter PGD + date range, hiển thị 18 cột, format tiền, xuất Excel/PDF
- `tabs/tab_no_khoanh.py` dòng ~1845–1902 — fix M10: đổi tên → "M10_QLNK", thêm cột so_ku, format "du_no_goc_khoanh" từ đồng → triệu đồng, thêm xuất PDF

## [2026-05-19] — DB migration: thêm cột ngay_het_han_khoanh vào qlnk_ket_qua
- `db.py` dòng ~177 — thêm `ngay_het_han_khoanh TEXT` vào DDL `CREATE TABLE qlnk_ket_qua`
- `db.py` dòng ~240 — thêm `ALTER TABLE qlnk_ket_qua ADD COLUMN ngay_het_han_khoanh TEXT` migration (idempotent)
- `db.py` `_QLNK_KQ_COLS` — thêm `ngay_het_han_khoanh` vào list cột đọc
- `db.py` `luu_ket_qua_kiem_tra()` — thêm cột vào cả UPDATE và INSERT
- `config.py` dòng ~304 — thêm constant `COT_NGAY_HH_KHOANH = "Ngày hết hạn Khoanh"` (trước chỉ định nghĩa local trong tab)
- `tabs/tab_no_khoanh.py` `data_dict` — lấy `ngay_het_han_khoanh` từ `row_chon` (HSTD) thay vì bỏ trống

## [2026-05-19] — Fix: đọc TẤT CẢ cột từ HSTD parquet (175 cột) cho tab Nợ khoanh
- `app.py` dòng 72–97 — thay PyArrow filter bằng DuckDB (PyArrow filter chỉ đọc cột được reference → bỏ sót 169 cột)
- `cache/hstd.parquet` — xóa cache cũ để buộc merge lại với tất cả 175 cột
- Các cột "Dư nợ khoanh", "Ngày hết hạn Khoanh", "Tên tổ" giờ có trong HSTD

## [2026-05-19] — QLNK: thêm section "📄 Xuất mẫu biểu" vào sub-tab d7
- `tabs/tab_no_khoanh.py` dòng ~29 — thêm 6 import docx/io
- `tabs/tab_no_khoanh.py` dòng 165–780 — thêm 10 helper `_qlnk_*` + 5 hàm `_tao_word_ke_hoach_kt`, `_tao_word_01qlnk`, `_tao_word_02qlnk`, `_tao_word_03qlnk`, `_tao_word_04qlnk`
- `tabs/tab_no_khoanh.py` dòng ~1675 — thêm UI xuất 5 mẫu Word vào cuối `with d7:`

## [2026-05-19] — Fix convention vi phạm role check trong tab_no_khoanh.py
- `tabs/tab_no_khoanh.py` dòng 12 — thêm import `co_quyen_upload_pgd`
- `tabs/tab_no_khoanh.py` dòng 320, 528 — thay `role in ["manager_pgd", "admin_pgd"]` bằng `co_quyen_upload_pgd(role)`

## [2026-05-19] — QLNK: thêm tab "Kế hoạch" vào tab_no_khoanh.py
- `tabs/tab_no_khoanh.py` dòng ~25 — thêm import `LY_DO_KHOANH_QD62`, `LY_DO_KHOANH_LABEL`
- `tabs/tab_no_khoanh.py` dòng ~250 — đổi 6 → 7 tab, thêm "📅 Kế hoạch" (d5)
- Đổi tên biến: d5 (Kiểm tra) → d6, d6 (Báo cáo) → d7
- Thêm block `with d5:` — Form lập kế hoạch + danh sách kế hoạch

## [2026-05-19] — QLNK: cập nhật LY_DO_KHOANH_QD62 + thêm LY_DO_KHOANH_LABEL
- `config.py` — thay thế `LY_DO_KHOANH_QD62` (11 mục, tách k1/k2 theo mức thiệt hại), thêm `LY_DO_KHOANH_LABEL` (nhãn rút gọn)

## [2026-05-19] — QLNK: thêm LY_DO_KHOANH_QD62 vào config.py
- `config.py` dòng ~506 — thêm dict `LY_DO_KHOANH_QD62` (9 mục k1→k_bs) sau `KV_PREFIX_NO_RUI_RO`

## [2026-05-19] — QLNK: thêm 2 bảng SQLite + 6 hàm CRUD vào db.py
- `db.py` dòng ~166–213 — DDL: `qlnk_ket_qua` (4 index), `qlnk_bo_sung` (1 index)
- `db.py` dòng ~584–829 — 6 hàm CRUD: `luu_ket_qua_kiem_tra`, `phe_duyet_ket_qua`, `mo_phe_duyet`, `doc_ket_qua_kiem_tra`, `luu_bo_sung_mon_vay`, `doc_bo_sung_mon_vay`

## [2026-05-19] — Dark/Light Mode: Semantic Token System
- `utils_theme.py` — refactor hoàn toàn: 2 bộ color token `_DARK`/`_LIGHT` theo shadcn/Linear pattern, `get_theme_css(theme)` sinh CSS đầy đủ
- `app.py` — xóa `_get_global_css()` (~370 dòng cũ), thay bằng `get_theme_css(theme)` + `init_theme()`, nút toggle ở sidebar trước "Đăng xuất"
- Sidebar luôn giữ dark (tạo contrast đẹp với content area)
- Lưu preference vào `kv_store` (key `theme_{username}`)

## [2026-05-19] — Đổi màu nền main area thành trắng
- `app.py` dòng ~128, ~256 — CSS `.main` & `.block-container`: background #0E1117 → #FFFFFF

## [2026-05-19] — Fix cột Số món vay & Số KH trong "Cơ cấu dư nợ theo chương trình"
- `tabs/tab_tongquan.py` dòng ~550–563 — Tính "Số món vay" từ df gốc (không lọc dư nợ > 0) để không bỏ sót dòng tất toán. Thêm `_so_mon_by_ct` và map vào `df_ct["so_mon"]` tương tự như "Số KH"

## [2026-05-19] — Tăng size chữ menu điều hành + tab sidebar
- `app.py` — tăng button sidebar: font-size 14→15px, padding 10→12px, margin-bottom 4→6px
- `ws_management.py` — tăng font "MENU ĐIỀU HÀNH" 12→14px đậm, group label 10→11px đậm, active items 13→14px, padding lớn hơn

## [2026-05-19] — Fix chữ nút sidebar: thêm CSS force white + text-shadow

## [2026-05-19] — Đổi sidebar: nền xanh dương sáng #64B5F6, nút xanh lá chữ trắng đậm
- `app.py` dòng ~131–220 — Sidebar background #FFFFFF, border xám nhạt, text xám/xanh đậm, button xanh lá nhạt

## [2026-05-18] — Rà soát toàn bộ codebase: thêm format="DD/MM/YYYY" cho tất cả st.date_input
- `tabs/tab_tien_do.py` — đã có `format="DD/MM/YYYY"` cho toàn bộ 7 widget từ đợt trước
- `tabs/tab_phoi_hop_pgd.py` — thêm format cho 4 widget (Ngày giao, Ngày kết thúc × 2 form)
- `tabs/tab_no_rui_ro.py` — thêm format cho 8 widget (Ngày rủi ro, Ngày ký QĐ, Từ ngày, Đến ngày × 3 form + Ngày lập)
- `tabs/tab_audit_log.py` — thêm format cho 2 widget (Từ ngày, Đến ngày)
- `tabs/tab_nhiem_vu.py` — thêm format cho 1 widget (Ngày deadline)
- `tabs/tab_tien_do_nop.py` — thêm format cho 1 widget (Deadline)
- `workspaces/ws_operation.py` — thêm format cho 1 widget (Ngày họp)
- Nguyên nhân: Streamlit mặc định hiển thị date_input theo locale hệ thống (MM/DD/YYYY) nếu không set format

## [2026-05-18] — Fix lỗi "Mixing dicts with non-Series" khi xác nhận lưu tiến độ
- `tabs/tab_tien_do.py` dòng ~813 — fix: thay vì đọc `editor_key` (trả về state dict `{"edited_rows":...}` gây crash `pd.DataFrame()`) hoặc `_data` (bị ghi đè stale sau `st.rerun()`), nay đọc state dict rồi áp `edited_rows` lên `df_edit.copy()` để lấy DataFrame đúng với edits của user

## [2026-05-18] — Fix lỗi tick/bỏ chọn trong Cập nhật tiến độ — đọc trực tiếp từ session_state thay vì cache
- `tabs/tab_tien_do.py` dòng ~813 — fix: đọc `edited` từ `st.session_state.get(editor_key)` (state thật của data_editor) thay vì `st.session_state.get(f"{editor_key}_data")` (cache cũ chỉ được cập nhật cuối render); nguyên nhân: `st.rerun()` trong handler "Lưu thay đổi" dừng script ngay lập tức nên `_data` không kịp cập nhật edits mới nhất → "✅ Xác nhận" đọc stale data → DB ghi đúng nhưng display không thay đổi

## [2026-05-18] — Nâng cấp Tab Điểm Giao Dịch — thêm trường + tìm kiếm + xuất khẩu
- `tabs/tab_quan_ly_dgd.py` — thêm `_normalize_entry()`, `_dgd_to_rows()` (backward compat list→dict); thêm tab "🔍 Tìm kiếm" đầu tiên với lọc PGD/Xã + tìm nhanh + xuất Excel/PDF; form Thêm mới & Xem & Sửa bổ sung 4 trường: Địa chỉ, Người phụ trách, SĐT, Lịch GD; lưu dict thay vì list
- `tabs/tab_diem_gd_pgd.py` — tương tự, scope chỉ PGD đăng nhập; thêm `_render_tim_kiem_pgd()`

## [2026-05-18] — Nâng cấp tab Tiến độ Báo cáo của PGD — deadline + trạng thái + role
- `tabs/tab_tien_do_nop.py` — viết lại toàn bộ: thêm 3 sub-tab (Tổng quan / Danh sách nộp / Cài đặt deadline); deadline lưu kv_store key `bao_cao_deadline_config`; phân loại 🟢 Đúng hạn / 🟡 Trễ / 🔴 Chưa nộp; ma trận PGD × Loại báo cáo; role-based (admin_cn/manager_cn thấy tab Cài đặt; PGD chỉ thấy dữ liệu của mình)

## [2026-05-18] — Tab Tiến độ: thêm toggle Ẩn đơn vị đã hoàn thành trong Cập nhật tiến độ
- `tabs/tab_tien_do.py` dòng ~777 — thêm `st.toggle("Ẩn đơn vị đã hoàn thành")` sau progress bar; khi bật, `kq_hien_thi` chỉ gồm đơn vị `chua_thuc_hien`, data editor chỉ hiện đơn vị chưa làm
- `tabs/tab_tien_do.py` dòng ~863 — cập nhật caption `c_info` hiển thị `👁 Đang ẩn N đã hoàn thành` khi toggle bật
- `tabs/tab_tien_do.py` dòng ~779 — fix: gắn `an_da_ht` vào `editor_key` để tránh xung đột session state khi toggle bật/tắt (key cũ không đổi → Streamlit reset checkbox về mặc định khi data shape thay đổi)
- `tabs/tab_tien_do.py` dòng ~842 — fix: sau lưu, `st.session_state.pop(editor_key)` để xóa state cũ của `st.data_editor`, tránh hiển thị stale state sau khi DB đã được cập nhật
- `tabs/tab_tien_do.py` dòng ~860 — fix: Hoàn tác dùng `base = f"td_editor_{task_id}_{pgd_sel}"` thay vì `editor_key` để xóa cả 2 state toggle ON/OFF

## [2026-05-18] — Tab Tiến độ: sửa dropdown chọn đầu việc — thêm ngày BĐ/KT + trạng thái rõ ràng
- `tabs/tab_tien_do.py` dòng ~430–445 — `_fmt_task()`: thay `[ĐANG]`/`[ĐÓNG]` → `🟢 Đang thực hiện`/`⚠️ Đã hết hạn`/`🔒 Đã đóng`; thêm `BĐ: {ngày bắt đầu}` và `KT: {ngày kết thúc}` vào dòng dropdown
- `tabs/tab_tien_do.py` dòng ~660–680 — `_render_cap_nhat()` dropdown `① CHỌN ĐẦU VIỆC`: thêm `_fmt_cap_nhat_opt()` hiển thị trạng thái + ngày BĐ + ngày KT
- `tabs/tab_tien_do.py` dòng ~690–720 — info section sau chọn đầu việc: tách ngày BĐ, ngày KT ra 3 cột riêng, badge `🔴 Quá hạn` → `⚠️ Đã hết hạn`, `🟢 Còn hạn` → `🟢 Đang thực hiện`
- `tabs/tab_tien_do.py` dòng ~1149–1165 — `_fmt_task_pdf()` trong Xuất báo cáo: đồng bộ format mới

## [2026-05-18] — Highlight cam parent accordion khi child active trong ws_management sidebar
- `workspaces/ws_management.py` dòng ~1225 — khi `is_child_active=True`, thay `st.button()` bằng markdown div cam (cùng style tab đơn active); parent tự mở và highlight mà không toggle; khi không có child active vẫn giữ button toggle bình thường

## [2026-05-18] — Tối ưu RAM: thay DuckDB bằng PyArrow trong _load_hstd()
- `app.py` dòng ~81 — thay `duckdb.query(...).df()` bằng `pd.read_parquet(filters=pa_filters)`; peak RAM giảm từ 97.6MB → 3.1MB (ratio 7×→2.2×); filter active_only dùng PyArrow OR-filter syntax thay vì DuckDB COALESCE/TRY_CAST (an toàn vì cột dư nợ đã xác nhận là int64 trong parquet)

## [2026-05-18] — Chuyển "Nợ Đến Hạn" sang tab con của "Báo cáo tín dụng"
- `workspaces/ws_management.py` dòng ~1128–1148 — xóa "⏰ Đến hạn" khỏi children của "Cảnh báo NQH"; chuyển "Báo cáo tín dụng" thành parent với 2 children: "📊 Báo cáo tín dụng" và "⏰ Nợ Đến Hạn"

## [2026-05-18] — Sửa sidebar menu ws_management: bỏ double-render, tab con trắng chữ đen
- `workspaces/ws_management.py` dòng ~1228–1278 — xóa markdown overlay cho parent items và inactive children; xóa CSS inject (gây "tab trắng" trống); bọc child buttons trong `st.columns([0.06, 0.94])` để phân biệt với parent buttons qua CSS
- `app.py` dòng ~185 — thêm CSS `[data-testid="column"] .stButton > button` trong sidebar: nền trắng `#FFFFFF`, chữ đen `#1a1a1a`, font-weight 700 cho tab con

## [2026-05-18] — Fix logger.py: file handler bị bỏ qua khi Streamlit có sẵn root handlers
- `logger.py` — bỏ check `if root.handlers: return` trong `_configure_root()`; lý do Streamlit tự thêm handler vào root logger khi chạy, khiến file handler không bao giờ được gắn → `logs/app.log` không được ghi. Fix: luôn tạo file handler bất kể root đã có handler chưa.

## [2026-05-18] — Sửa delta_card format số với dấu phân cách hàng nghìn kiểu VN
- `components/delta_card.py` — thêm hàm `_fmt_vn_num()` format số int/float tự động với dấu `.` phân cách hàng nghìn (kiểu Việt Nam); áp dụng cho tham số `value` trong `delta_card()`. Sửa lỗi Số khách hàng hiển thị "213343" thay vì "213.343"

## [2026-05-18] — Tắt UserWarning parse ngày trong utils.py
- `utils.py` dòng 289 — `fmt_ngay()`: đổi `dayfirst=True` → `dayfirst=False` để khớp định dạng ISO `%Y-%m-%d` từ pandas/SQLite, tránh warning lặp lại

## [2026-05-18] — Sửa tab navigation không chuyển được trong ws_executive
- `workspaces/ws_executive.py` dòng ~1622–1642 — bỏ force-set `ws_exec_group_radio` và `item_key` mỗi lần render; chỉ force-set khi `jump_label` (sidebar jump) hoặc chưa init — tránh override click của user

## [2026-05-18] — Sửa định dạng số KPI trong ws_executive (Tổng quan Chi nhánh)
- `workspaces/ws_executive.py` dòng ~224 — hàm `_kpi_tang_truong()`: sửa `tdn`/`dqh` từ VND thô → `fmt_ty()` + suffix "triệu đ"; `nkh` → `fmt_so()` + suffix "hộ"; `tlqh` → `vn(tlqh, 2)` (dấu phẩy VN); thêm `vn` vào import utils

## [2026-05-18] — Phân biệt tab nhánh trong sidebar ws_management
- `workspaces/ws_management.py` dòng ~1262 — tab nhánh chưa active: thêm markdown overlay indent 22px + màu trắng mờ 65% + ký tự ↳, giữ nguyên style active (● cam đậm)

## [2026-05-18] — Thêm RAM benchmark (tracemalloc) vào app.py
- `app.py` dòng ~654 — đo RAM sau khi `_load_hstd()` xong, ghi vào `logs/app.log` qua logger `app.ram`; log format: `role= pgd= rows= current=MB peak=MB`

## [2026-05-18] — Thêm logging chuẩn cho upload_service và snapshot_service
- `logger.py` — TẠO MỚI: `get_logger(__name__)` ghi ra `logs/app.log` (xoay vòng 5MB×3) + console WARNING+
- `app.py` — thêm `logging.basicConfig()` fallback + kích hoạt `get_logger` ngay khi khởi động
- `services/upload_service.py` — thêm `logger`; log INFO bắt đầu/hoàn thành merge, WARNING PGD lỗi/cũ, ERROR rollback parquet; sửa `_snap_bg()` từ `except: pass` → `logger.error(..., exc_info=True)`
- `snapshot_service.py` — thêm `logger`; log INFO bắt đầu/hoàn thành lưu snapshot, ERROR khi thất bại

## [2026-05-17] — Tạo 2 file test mới cho upload_service và snapshot_service
- `tests/test_upload_service.py` — 11 test case: KetQuaUpload (4), kiem_tra_file (6), kiem_tra_file_he_thong (3); dùng mock không cần file/DB thật
- `tests/test_snapshot_service.py` — 18 test case: _ky_tu_df (4), luu_snapshot (6), doc_snapshot (3), doc_snapshot_range (2), danh_sach_ky (3), xoa_snapshot (2); dùng SQLite in-memory
- Tên cột fixture khớp với COT_* thực tế trong config.py

## [2026-05-17] — Tạo pre-commit hook kiểm tra convention VBSP-SCM
- `scripts/check_conventions.py` — kiểm tra: role hardcode, tiền tệ sai đơn vị, cột hardcode, sqlite3.connect() trực tiếp, ghi_kv không có ghi_audit
- `.git/hooks/pre-commit` — thay thế bằng hook mới gọi `check_conventions.py` trên staged *.py files; exit 1 nếu có vi phạm, `git commit --no-verify` để bỏ qua
- Cần chạy 1 lần: `chmod +x .git/hooks/pre-commit` (Git Bash) hoặc tự động trên Windows

## [2026-05-17] — Thêm trang "Executive Summary" vào ws_executive.py
- `workspaces/ws_executive.py` imports — thêm `import db`, `COT_NGAY_DH`, `CHUONG_TRINH_KHTD`
- `workspaces/ws_executive.py` hàm mới `_render_executive_summary()` — 6 KPI delta cards, gauge NQH + trạng thái, 4 loại cảnh báo rủi ro tổng hợp, mini heatmap PGD
- `workspaces/ws_executive.py` `_build_exec_items()` — thêm item "📊 Tổng hợp" là phần tử đầu tiên trong group "Tổng quan"

## [2026-05-17] — Thêm UI backup vào tab_trang_thai_nguon.py
- `tabs/tab_trang_thai_nguon.py` hàm `_render_he_thong()` — thêm tham số `la_cn: bool = False` để kiểm soát quyền xem/bấm backup
- `tabs/tab_trang_thai_nguon.py` hàm `_render_he_thong()` — thêm section "Backup dữ liệu": nút "Backup ngay" (chỉ cho admin_cn/manager_cn), audit log, danh sách 7 bản backup gần nhất với dung lượng/số file/trạng thái từng thành phần (DB/Parquet/PGD xlsx)
- `tabs/tab_trang_thai_nguon.py` hàm `render()` dòng 636 — truyền `la_cn=la_cn` khi gọi `_render_he_thong()`

## [2026-05-17] — Chuyển "Cảnh báo NQH" thành accordion trong sidebar ws_management
- `workspaces/ws_management.py` hàm `_build_all_items()` — thay item "Cảnh báo NQH" (fn) bằng item có `children` (5 nhánh con với default-arg lambda tránh late binding)
- `workspaces/ws_management.py` hàm mới `_render_canh_bao_no_sub()` — dispatch 5 nhánh con theo `idx` (0=Đến hạn, 1=3tháng KHĐ, 2=Migration, 3=NQH phát sinh, 4=Cảnh báo sớm)
- `workspaces/ws_management.py` hàm `render_sidebar_menu()` — accordion logic: nút cha toggle `ws_mgmt_acc_*`, nhánh con highlight active, `valid_labels` gồm cả child labels
- `workspaces/ws_management.py` hàm `render()` — `valid_labels` mở rộng, dispatch tìm cả trong children khi `active_item` không có `fn`

## [2026-05-17] — Thêm menu item "Xuất báo cáo KHTD" vào ws_management.py
- `workspaces/ws_management.py` dòng 52 — thêm `tab_khtd_xuat` vào import block từ tabs
- `workspaces/ws_management.py` dòng 1103 — thêm menu item "Xuất báo cáo KHTD" trong group "Kế hoạch và Thực hiện KHTD" gọi `tab_khtd_xuat.render_xuat_baocao()` với tham số role, username, df_full

## [2026-05-17] — Chuẩn hóa định dạng ngày trong tab_tien_do.py
- `tabs/tab_tien_do.py` dòng 197, 242, 248, 428, 650, 683–686, 1013 — thay tất cả ISO date thô bằng `fmt_ngay()` trong UI (chart, caption, dataframe, selectbox label)

## [2026-05-17] — Nâng cấp tab_khtd_xuat.py: preview + Excel 23 sheet
- `tabs/tab_khtd_xuat.py` dòng 12 — thêm `PGD_XA_MAP`, `DON_VI_CHI_NHANH` vào import config; xóa import `ExcelReport`
- `tabs/tab_khtd_xuat.py` hàm `xuat_khtd_theo_xa()` — xuất 23 sheet: tổng CN + 22 đơn vị (Hội sở CN tỉnh + 21 PGD) lọc theo `PGD_XA_MAP`
- `tabs/tab_khtd_xuat.py` hàm `render_xuat_baocao()` — expander preview dùng `XA_TO_PGD.items()`, cột "Đơn vị" thay "PGD"

## [2026-05-17] — Sửa 2 lỗi trong tab_trang_thai_nguon.py
- `tabs/tab_trang_thai_nguon.py` dòng 339 — sửa đơn vị tiền tệ: `/1e9` → `/1e12` (VND → tỷ đồng)
- `tabs/tab_trang_thai_nguon.py` dòng 387–398 — xóa check plaintext password, thay bằng check `ngay_doi_mk IS NULL` (bcrypt-safe)

## [2026-05-17] — Thêm checkbox số công văn trong UI xuất PDF tab NQH
- `workspaces/ws_management.py` dòng ~508–526 — checkbox "Có số công văn": khi check hiện 2 ô (text_input Số hiệu + selectbox Loại văn bản); khi không check bỏ qua, PDF xuất không có số

## [2026-05-17] — Thêm tham số so_hieu và loai_van_ban cho xuat_pdf_group_header
- `pdf_service.py` hàm `xuat_pdf_group_header` — thêm `so_hieu` (hiện dưới tên cơ quan khi có) và `loai_van_ban` (hiện trên tiêu đề khi có); cả 2 mặc định rỗng = không hiện

## [2026-05-17] — Cải tiến xuat_pdf_group_header: NĐ 30, dòng Cộng, chữ ký
- `pdf_service.py` hàm `xuat_pdf_group_header` — đổi header sang chuẩn NĐ 30 (tên cơ quan trái, quốc hiệu phải, không số công văn); thêm dòng Cộng cuối mỗi nhóm (tổng cols_tien, nền xanh nhạt); thêm khối chữ ký Người lập biểu / Kiểm soát / Giám đốc cuối trang

## [2026-05-17] — Thêm xuất PDF Group Header cho tab Nợ QH phát sinh
- `workspaces/ws_management.py` dòng ~484–533 — thêm block xuất PDF: radio nhóm theo (PGD / Hội đoàn thể / Chương trình), nút "Xuất PDF Group Header", nút tải file PDF
- `workspaces/ws_management.py` dòng 40 — thêm `xuat_pdf_group_header` vào import từ `pdf_service`

## [2026-05-17] — Thêm dropdown lọc PGD trước danh sách chi tiết NQH
- `workspaces/ws_management.py` dòng ~443–452 — thêm selectbox "Lọc theo PGD" sau filter ĐVUT, lọc `df_nqh_chi` trước khi hiển thị bảng và nút xuất Excel

## [2026-05-17] — Thêm dropdown lọc Hội đoàn thể trong tab Nợ QH phát sinh
- `workspaces/ws_management.py` dòng ~362–397 — thêm `st.columns(2)`, đặt filter tháng cột trái, thêm selectbox "Lọc theo Hội đoàn thể" cột phải (lọc theo `Tên ĐVUT`)

## [2026-05-17] — Fix UnicodeEncodeError surrogate emoji trong Cảnh báo NQH
- `workspaces/ws_management.py` dòng ~369 — thay chuỗi surrogate `📅` bằng ký tự emoji đúng `📅`

## [2026-05-17] — Cảnh báo NQH / Nợ QH phát sinh: đổi filter → selectbox chọn tháng số liệu
- `workspaces/ws_management.py` — bỏ radio Kỳ hiện tại/Toàn thời gian, thay bằng selectbox tháng MM/YYYY

## [2026-05-17] — Cảnh báo NQH / Nợ rủi ro: thêm card Tổng dư nợ nhóm 1–<3 tháng
- `workspaces/ws_management.py` dòng ~289 — thêm metric "Tổng dư nợ (1–<3 tháng rủi ro)"

## [2026-05-17] — Cảnh báo NQH / Đến hạn: thêm nhóm Hội đoàn thể vào Tổng hợp
- `tabs/tab_den_han.py` — import COT_DVUT, radio "Nhóm theo" thêm option "Hội đoàn thể"

## [2026-05-17] — Cảnh báo NQH / Đến hạn: gộp tổng theo Xã/PGD, thêm bar chart màu
- `tabs/tab_den_han.py` dòng ~162 — bỏ groupby theo tháng, gom tổng luôn + bar chart ngang gradient xanh

## [2026-05-17] — Tab Tổng quan: gộp 4 tab tháng → slider, đổi biểu đồ Pie → bar màu
- `tabs/tab_tongquan.py` — xóa 4 sub-tab (1/3/6 tháng / Trong năm), thay bằng select_slider
- `tabs/tab_tongquan.py` — đổi Donut Pie → horizontal bar chart với color gradient xanh lá

## [2026-05-17] — Chuyển Tiến độ Công việc & Tiến độ Báo cáo vào nhóm Phối hợp với PGD
- `workspaces/ws_management.py` — di chuyển 2 item từ nhóm Giám sát sang nhóm Phối hợp với PGD

## [2026-05-17] — Thêm phân hệ "Phối hợp với PGD" vào MENU ĐIỀU HÀNH
- `tabs/tab_phoi_hop_pgd.py` — tạo mới: CRUD phiếu phối hợp CN↔PGD, lưu kv_store
- `workspaces/ws_management.py` dòng 51 — import tab_phoi_hop_pgd
- `workspaces/ws_management.py` dòng ~1011 — thêm group "Phối hợp với PGD" ngang hàng Giám sát/Ủy Thác
- `workspaces/ws_management.py` dòng ~1038 — thêm màu xanh lá cho group mới vào GROUP_COLORS

## [2026-05-17] — Form tạo đầu việc: xóa Ghi chú thêm, đổi Áp dụng cho đơn vị sang checkbox
- `tabs/tab_tien_do.py` dòng ~337 — xóa multiselect "Áp dụng cho đơn vị", thay bằng lưới checkbox 3 cột
- `tabs/tab_tien_do.py` dòng ~354 — xóa field "Ghi chú thêm"

## [2026-05-17] — Đổi tên tab và nhãn field trong tab Tiến độ Công việc
- `tabs/tab_tien_do.py` dòng 1667 — tab "➕ Tạo đầu việc" → "➕ Tạo đầu việc mới"
- `tabs/tab_tien_do.py` dòng 330, 477 — nhãn field "Thời hạn hoàn thành" → "Ngày kết thúc"

## [2026-05-17] — Đổi tên tab menu "Tiến độ PGD" thành "Tiến độ Báo cáo của PGD"
- `workspaces/ws_management.py` dòng 994 — đổi label

## [2026-05-17] — Bổ sung 3 kiểm tra vào tab_trang_thai_nguon
- `tabs/tab_trang_thai_nguon.py` `_render_merge_cache()` — thêm kiểm tra đồng bộ DS_PGD giữa kv_store và config.py
- `tabs/tab_trang_thai_nguon.py` `_render_tep_nguon()` — thêm kiểm tra đồng nhất ngày số liệu giữa các PGD (dùng DuckDB)
- `tabs/tab_trang_thai_nguon.py` `_render_he_thong()` — thêm kiểm tra nhiệm vụ và tiến độ task quá hạn

## [2026-05-17] — Fix đếm số KH theo CTTD bỏ sót KH tất toán
- `tabs/tab_tongquan.py` dòng ~549 — tính `so_kh` từ `df` gốc thay vì `_df_loc` (đã lọc dư nợ > 0), ghi đè sau khi groupby để không bỏ sót KH có dư nợ = 0

## [2026-05-17] — Cập nhật tên model Trae trong CLAUDE.md
- `CLAUDE.md` section 5.11 — đổi Flash → V4 Flash, Pro → V4 Pro

## [2026-05-17] — Fix bảng "Cơ cấu dư nợ": số món vay sai, GN/TN năm ko hiện
- `tabs/tab_tongquan.py` dòng ~558 — đổi `so_mon = (COT_SO_KU, "nunique")` → `(COT_TONG_DU_NO, "count")` để tránh miss row khi Số khế ước null
- `config.py` `HSTD_DS_CHO_VAY_NAM_ALIASES` — bổ sung aliases: `"Doanh số cho vay năm"`, `"Doanh số CV năm"`, `"Cho vay trong năm"`
- `config.py` `HSTD_THU_NO_NAM_ALIASES` — thêm đầu danh sách: `"Thu nợ trong năm"` (tên thực tế trong HSTD BCQUERY theo tab_tracuu), `"Doanh số thu nợ năm"`, `"Thu nợ năm"`

## [2026-05-17] — Tối ưu tốc độ load tab: cache parquet/CDTOTKVV
- `tabs/tab_tongquan.py` dòng ~485, ~954 — thay `doc_cdtotkvv_toan_cn_pgd()` (đọc 22 file Excel mỗi lần render) bằng `tong_hop_tu_pgd_data()` (đã có `@st.cache_data`)
- `tabs/tab_ban_dai_dien.py` — thêm `@st.cache_data(show_spinner=False)` cho `_doc_hstd()` với `_ts: float` để bust cache khi parquet thay đổi; thêm `import os` và `from data.core import ts_file`
- `tabs/tab_khtd_xuat.py` — thêm `_doc_hstd_cached()` và `_doc_gqvl_cached()` cached với `_ts`; thay 3 lần `pd.read_parquet()` trực tiếp bằng các hàm này; thêm `import os` và `from data.core import ts_file`
- `tabs/tab_khtd.py` — thêm `@st.cache_data(show_spinner=False)` cho `_doc_gqvl_parquet()` với `_ts: float`; import `CACHE_GQVL` và `ts_file`; cập nhật call site truyền timestamp

## [2026-05-17] — Fix bảng trạng thái 22 đơn vị không cập nhật sau upload đơn lẻ
- `tabs/tab_upload_khnv.py` `_xu_ly_upload()` — thêm `pop("trang_thai_upload_pgd")` sau upload thành công; trước đây bảng 22 đơn vị đọc từ session_state cũ sau rerun nên vẫn hiện ❌/⚠️ dù file đã lưu xong (bulk import đã làm đúng, single upload còn thiếu bước này)

## [2026-05-17] — Fix TypeError: _build_exec_items() got multiple values for df_full
- `workspaces/ws_executive.py` dòng ~1595 — lọc `df`, `df_full`, `role`, `username` ra khỏi kwargs trước khi unpack vào `_build_exec_items()`; các key này đã được truyền positional nên có trong kwargs gây "multiple values"

## [2026-05-17] — Merge KH-NV: giảm thời gian từ ~10 phút xuống ~1 phút
- `data/core.py` `excel_to_parquet()` — `compression_level=9` → `3`; zstd level 9 chậm hơn level 3 tới 5-10x khi ghi, kích thước file chỉ chênh ~5%
- `services/upload_service.py` `merge_du_lieu_toan_cn()` — (1) `compression_level=9` → `3` cho parquet CN; (2) vectorize string cleanup: thay for-loop per-column bằng `apply(lambda s: s.str.strip())` trên tất cả str cols cùng lúc; (3) chuyển `luu_snapshot` ra ngoài `_MERGE_LOCK` và chạy trong daemon thread → không block luồng chính sau khi ghi parquet xong

## [2026-05-17] — Upload KH-NV: song song hóa xử lý 4 file bằng ThreadPoolExecutor
- `tabs/tab_upload_khnv.py` — tách `_xu_ly_mot_file_khnv()` module-level (thread-safe: không gọi st.* / db.*); `_xu_ly_upload()` dùng `ThreadPoolExecutor(max_workers=4)` để xử lý song song → thời gian giảm từ N×parse xuống còn max(parse) thay vì tổng; ghi audit tuần tự sau khi tất cả thread xong

## [2026-05-17] — Dọn warning: use_container_width → width + suppress openpyxl
- `app.py` — thêm `warnings.filterwarnings` suppress UserWarning openpyxl "no default style"
- `utils.py` dòng ~155 — `use_container_width: True` → `width: "stretch"` trong `hien_thi_dataframe_phan_trang()`
- `components/export_pdf.py` — `use_container_width=True` → `width="stretch"` trong `st.download_button`
- `components/filter_bar.py` — 2 chỗ `use_container_width=True` → `width="stretch"` trong `st.button`
- `components/movers.py` — `use_container_width=True` → `width="stretch"` trong `st.dataframe`

## [2026-05-17] — Upload UX: tự reset file uploader sau upload thành công + spinner
- `tabs/tab_upload_khnv.py` `_render_upload_form()` — thêm version counter vào key file_uploader, widget tự reset rỗng sau upload thành công; thêm `st.spinner()` khi xử lý
- `tabs/tab_upload_khnv.py` `_xu_ly_upload()` — tăng version counter khi có ít nhất 1 file upload thành công
- `tabs/tab_upload_pgd.py` `_render_upload_form()` — thêm version counter vào key file_uploader + hiển thị kết quả upload từ session_state (bền qua rerun); thêm `st.spinner()`
- `tabs/tab_upload_pgd.py` `_xu_ly_upload()` — thêm param `prefix`, gom kết quả vào `msgs[]`, lưu vào session_state trước rerun thay vì gọi `st.success/error` trực tiếp (bị xóa bởi rerun); reset version counter khi thành công

## [2026-05-17] — Bảng trạng thái 22 đơn vị: thêm cột 31/12/YYYY baseline
- `tabs/tab_upload_khnv.py` `_hien_thi_bang_trang_thai()` — thêm cột `31/12/{nam}` hiển thị ✅/❌ baseline per-PGD; tự chọn năm gần nhất có dữ liệu (fallback năm trước)

## [2026-05-17] — Baseline 31/12: UI import đồng nhất với Import hàng loạt 4 file
- `tabs/tab_upload_khnv.py` `_render_upload_baseline()` — viết lại bulk section theo đúng pattern Import hàng loạt: 2 tab (Chọn file / Quét thư mục), checkbox force import, MD5 check so sánh file đã có, styled preview table (Tên file / Đơn vị / So sánh / Trạng thái), summary caption, nút Import, reset uploader sau import

## [2026-05-17] — Baseline 31/12: thêm tab "Quét thư mục" bên cạnh "Chọn file"
- `tabs/tab_upload_khnv.py` `_render_upload_baseline()` — tách bulk upload thành 2 tab: "📁 Quét thư mục" (nhập đường dẫn server, quét .xlsx/.xls tự động) và "📂 Chọn file" (multi-file uploader giữ Ctrl); cả 2 dùng chung bytes_map → preview → nút Lưu

## [2026-05-17] — Baseline 31/12: bulk upload hàng loạt, tự nhận diện PGD
- `tabs/tab_upload_khnv.py` — viết lại `_render_upload_baseline()`: bulk multi-file uploader với version counter reset; nhận diện PGD bằng `_tim_ten_pgd_tu_noi_dung(data, "hstd")`; preview table (File / Đơn vị / Trạng thái); lưu song song vào `baseline_pgd_path(don_vi, nam)`; hiển thị trạng thái 22 đơn vị (✅/⬜) theo năm

## [2026-05-17] — Baseline 31/12: đổi upload 1 file CN → grid 22 PGD per-unit
- `tabs/tab_upload_khnv.py` — import thêm `baseline_pgd_path, danh_sach_nam_baseline_pgd, trang_thai_baseline_pgd`; viết lại `_render_upload_baseline()`: hiện bảng trạng thái 22 đơn vị (✅/⬜), grid 2 cột file_uploader per-PGD, lưu vào `data/baseline_pgd/{slug}/HSTD_3112_{nam}.XLSX`; `doc_baseline_merged` tự merge khi tab So sánh kỳ cần

## [2026-05-17] — Fix: df/df_full không vào kwargs của _build_all_items → tab crash NoneType
- `workspaces/ws_management.py` — thêm `df=df, df_full=df_full, ds_pgd_all=ds_pgd_all` vào lời gọi `_build_all_items()`; root cause: `filtered_kw` lọc 3 key này ra nhưng không truyền lại, mọi lambda dùng `**kwargs` nhận `df=None` → crash `'NoneType' object has no attribute 'columns'`

## [2026-05-17] — Fix: admin bị block ở Upload KH-NV do thiếu role trong kwargs
- `workspaces/ws_management.py` `_build_all_items()` dòng ~983 — thêm `kwargs.setdefault("role", role)` và `kwargs.setdefault("username", username)` ngay đầu hàm; root cause: `filtered_kw` lọc bỏ `role` trước khi truyền vào `_build_all_items`, các lambda dùng `**kwargs` không có `role` → tab nhận `role=""` → bị block sai

## [2026-05-17] — Fix tra cứu: bỏ active_only filter cho tab Tra cứu hồ sơ
- `app.py` ctx dict — thêm `hstd_path=CACHE_HSTD` để truyền đường dẫn Parquet xuống tab
- `tabs/tab_tracuu.py` — thêm `import duckdb`; extract `pgd_user` từ kwargs; thêm flag `_use_parquet = hstd_path and not pgd_user` — chỉ CN role đọc full parquet (bỏ qua active_only), PGD role vẫn dùng `df` đã lọc theo PGD của mình; cache df_work vào session_state theo `ts_hstd`; kết quả: CN tra cứu được khách hàng tất toán, PGD không bị mở rộng phạm vi dữ liệu

## [2026-05-17] — Tối ưu RAM/đa luồng: DuckDB cho kiem_soat_service + tab_kiem_soat
- `services/kiem_soat_service.py` — thêm `import duckdb`; refactor `_tinh_to_sai_so_tv`: thay `groupby().agg()` bằng DuckDB GROUP BY + TRY_CAST; refactor `_tong_hop_vp_theo_pgd`: thay Python for loop bằng DuckDB GROUP BY + FILTER; refactor `_tong_hop_ghv_theo_pgd`: thay `groupby().agg()` bằng DuckDB
- `tabs/tab_kiem_soat.py` — thêm `import duckdb`; refactor `_get_ks_cache`: xóa `df_nqh` copy trung gian, thay pandas filter+groupby NQH bằng 2 DuckDB query (tổng hợp PGD + chi tiết) với WHERE pushdown

## [2026-05-17] — Tối ưu RAM: _load_hstd active_only filter cho CN role
- `app.py` import thêm `COT_TONG_DU_NO, COT_DU_NO_QH` từ config
- `app.py` `_load_hstd()` — thêm tham số `active_only: bool`; xây WHERE clause động tổng hợp cả `ten_pgd` lẫn `active_only`; CN role gọi với `active_only=True` → loại hồ sơ tất toán hoàn toàn (gốc = 0, QH = 0, khoanh = 0) ngay tại tầng `read_parquet`, giảm 30–60% RAM tùy dữ liệu; fix bổ sung `"Dư nợ khoanh"` vào điều kiện (thiếu ban đầu)

## [2026-05-17] — Tối ưu RAM: _load_hstd filter pushdown per-PGD
- `app.py` `_load_hstd()` — thêm tham số `ten_pgd`; khi PGD role dùng `read_parquet() WHERE` filter ngay tại DuckDB thay vì load toàn bộ file; kết quả được `@st.cache_resource` cache riêng per-PGD
- `app.py` dòng ~583 — xóa khối DESCRIBE + duckdb.query WHERE thủ công (không cached); thay bằng `_load_hstd(CACHE_HSTD, _hstd_ts, ten_pgd=pgd_user)`; DESCRIBE chỉ chạy khi df rỗng (error path)

## [2026-05-17] — Fix upload hàng loạt: file_uploader không reset sau import
- `tabs/tab_upload_khnv.py` dòng ~707 — thêm `khnv_bulk_uploader_ver` counter, đổi key thành `f"khnv_bulk_upload_{_ver}"` để widget reset về rỗng sau import
- `tabs/tab_upload_khnv.py` dòng ~685 — sửa cleanup: tăng `khnv_bulk_uploader_ver`, pop `khnv_bulk_ids` (đúng tên) thay vì `khnv_bulk_names` (sai tên) và `khnv_bulk_upload` (không xóa được widget key)

## [2026-05-16] — Tối ưu tốc độ load: cache alert, status, CSS, dedup ALL_ITEMS
- `alert_center.py` — `_kiem_tra_khong_hoat_dong()`: thêm session_state cache 5 phút, tránh chạy `tong_hop_khong_hd(df_full)` mỗi rerun
- `widgets/status_widget.py` — tách `_kiem_tra_trang_thai()` với session_state cache 60s, tránh 3×`os.path.getmtime` mỗi rerun
- `workspaces/ws_management.py` `render()` — dùng `_build_all_items()` thay vì build lại 22-lambda list
- `app.py` — bọc 317-dòng CSS vào `@st.cache_resource` `_get_global_css()`; di chuyển `st.set_page_config` ra đúng vị trí sau CSS function

## [2026-05-16] — Fix ws_management: xóa 2 radio nav trùng trong render()
- `workspaces/ws_management.py` dòng ~1148 — xóa `st.radio` Level 1 (nhóm) và Level 2 (mục) trong `render()` vì sidebar `render_sidebar_menu()` đã xử lý điều hướng; `render()` giờ chỉ đọc `ws_mgmt_menu` từ session_state và render thẳng content

## [2026-05-16] — Tối ưu RAM: DuckDB read_parquet cho khtd_service & du_phong_service
- `services/khtd_service.py` — thêm `COT_TEN_PGD` vào import; refactor `tinh_kh_dau_nam` thay Pandas groupby bằng DuckDB query (hỗ trợ `parquet_path`/`ten_pgd` kwargs để lọc PGD ngay trong `read_parquet`); `tao_dot_giao_dau_nam` thêm optional `parquet_path` kwarg
- `services/du_phong_service.py` — thêm `import duckdb`; refactor `du_phong_dong_tien` và `du_phong_chi_tiet` thay `iterrows()` loop bằng DuckDB SQL dùng `UNNEST(RANGE(so_thang))` để mở rộng tháng, hỗ trợ `parquet_path`/`ten_pgd` kwargs

## [2026-05-16] — Refactor ws_executive.py: áp dụng Lazy-loading 2 tầng (radio Nhóm → Mục)
- `workspaces/ws_executive.py` dòng ~1328 — thay `st.tabs()` 6 tab eager bằng radio 2 tầng (`ws_exec_group_radio` / `ws_exec_item_{group}`), chỉ render mục active
- `workspaces/ws_executive.py` — thêm 6 section wrapper: `_render_suc_khoe_tong_quan`, `_render_tien_do_va_kh`, `_render_so_sanh_xep_hang_pgd`, `_render_nqh_xa_canh_bao`, `_render_migration_section`, `_render_pdf_section`
- `workspaces/ws_executive.py` — thêm `_build_exec_items()` (5 nhóm / 12 mục) và `render_sidebar_menu()` đồng bộ 2 chiều với `ws_exec_menu` / `ws_exec_jump`

## [2026-05-16] — Chuẩn hóa key Streamlit widget ws_operation: tất cả widget nhập liệu ghi lại session_state
- `workspaces/ws_operation.py` — Rà soát 28 Streamlit widget (selectbox, radio, multiselect, text_input, text_area, number_input, date_input, slider)
- **Ưu tiên 1 (đã fix):** 3 widget thiếu `key=` hoàn toàn → thêm key
- **Ưu tiên 2 (đã fix):** 13 widget có `key=` nhưng sai format (`dh_*`, `tb_*`, `gb*`, `gn_*`, `dp_*`, `hist_*`, `donut_*`) → đổi thành `op_[tab]_[biến]` (prefix `op_` = Operation)
- **Chi tiết sửa:**
  - `_render_doc_hub()`: `dh_doi_tuong` → `op_dh_doi_tuong`; `dh_kw` → `op_dh_kw`; `dh_hs_sel` → `op_dh_hs_sel`; `dh_xa` → `op_dh_xa`; `dh_mau_sel` → `op_dh_mau_sel`; `dh_xuat_mode` → `op_dh_xuat_mode`
  - `_render_thong_bao_ket_luan()`: `tb_chon_xa` → `op_tb_chon_xa`; `tb_ten_dgd` → `op_tb_ten_dgd`; `tb_ngay_hop` → `op_tb_ngay_hop`; `tb_so_van_ban` → `op_tb_so_van_ban`; `tb_ten_nguoi_ky` → `op_tb_ten_nguoi_ky`; `gn_*` → `op_gn_*`; `tb_chinh_sach` → `op_tb_chinh_sach`; `tb_ton_tai` → `op_tb_ton_tai`; `tb_nhiem_vu` → `op_tb_nhiem_vu`
  - `_render_bien_ban_giao_ban()`: `gb2_xa` → `op_gb2_xa`; `gb2_nam` → `op_gb2_nam`; `gb2_gn` → `op_gb2_gn`
  - `_render_bao_cao_giao_ban()`: `gb_pgd` → `op_gb_pgd`; `gb_xa` → `op_gb_xa`; `gb_dgd` → `op_gb_dgd`; `gb_tom_tat` → `op_gb_tom_tat`
  - `_render_du_phong_dong_tien()`: `dp_xa` → `op_dp_xa`; `dp_ct` → `op_dp_ct`; `dp_thang_xem` → `op_dp_thang_xem`
  - `_render_histogram_du_no()`: `hist_bins` → `op_hist_bins`
  - `_render_donut_co_cau()`: `donut_top` → `op_donut_top`
- **Tác dụng:** Fix lazy-rendering: khi user đổi tab, widget vẫn nhớ giá trị cũ qua session_state thay vì bị reset

## [2026-05-16] — Lazy navigation ws_management: radio Nhóm → Mục
- `workspaces/ws_management.py` — Thêm 2 tầng `st.radio` (Nhóm + Mục) ngay trong content, thay thế cách dùng sidebar-only để chọn mục; `render()` vẫn chỉ gọi đúng 1 `fn()` duy nhất
- `workspaces/ws_management.py` — Hỗ trợ `ws_mgmt_jump` (session_state): nút điều hướng từ nơi khác có thể set key này để jump đến mục chỉ định kèm toast thông báo
- `workspaces/ws_management.py` — Đồng bộ 2 chiều: sidebar click → radio pre-select đúng nhóm+mục; radio chọn → sidebar highlight đúng qua `ws_mgmt_menu`
- `workspaces/ws_management.py` `_build_all_items` — Fix "So sánh kỳ" `fn=None` → `fn=lambda: tab_so_sanh_ky.render(None, **kwargs)`
- `workspaces/ws_management.py` `render()` — Xoá GROUP_COLORS duplicate (chỉ dùng trong `render_sidebar_menu`)

## [2026-05-16] — Tối ưu hiệu năng: lazy tab rendering ws_operation
- `workspaces/ws_operation.py` — Thay `st.tabs` + loop-tất-cả bằng `st.radio` + chỉ render tab đang chọn; trước đây mỗi rerun chạy song song tất cả renderer (tab_tongquan, tab_tien_do, tab_so_sanh_ky, heatmap, histogram, donut... tổng 10+ hàm nặng)
- `workspaces/ws_operation.py` — Xử lý jump_idx (shortcut từ Trang Chủ) qua `session_state[tab_key]` trước khi radio render

## [2026-05-16] — Fix 4 KPI DeltaCard trang chủ PGD
- `workspaces/ws_operation.py` — Thêm import `PGD_XA_MAP`; thêm helper `_kpi_pgd_list(df_pgd, pgd_user)` dùng chung cho 2 chỗ render KPI
- KPI 1/2: `value` → `fmt_ty()` (trước là raw VND float); bỏ `suffix="đồng"` (fmt_ty đã có đơn vị)
- KPI 3: `value` → `fmt_so(n_khd)`; thêm `suffix="món"`; `precision` 0→1
- KPI 4: Bỏ logic sai `khtd_pgd_{slug}.tong_kh/.tong_th` → đọc `khtd_xa` + lọc `PGD_XA_MAP[pgd_user]`; `delta=None` thay vì `delta=0` để ẩn delta hoàn toàn
- Gộp 2 block KPI trùng (~74 và ~1235) thành 1 lời gọi `_kpi_pgd_list()`

## [2026-05-16] — Fix căn lề PDF bảng "Thông tin tổng quát theo PGD"
- `pdf_service.py` — Thêm param `cols_right` vào `xuat_pdf()`: các cột trong danh sách này dùng `style_td_r` (TA_RIGHT) mà không re-format lại số (dữ liệu đã format sẵn). Thêm `elif col in set_right` trong vòng lặp data rows
- `tabs/tab_tongquan.py` — Truyền `cols_right=[tất cả cột trừ "Đơn vị"]` khi gọi `xuat_pdf()` để số liệu căn phải, cột tên đơn vị căn trái

## [2026-05-16] — Tái thiết tab CBTD: phân công theo ĐGD thay vì mã thôn
- `data/khtd.py` — Thêm 3 hàm: `lay_ap_tu_dgd_list()`, `xay_ap_to_cbtd_map()`, `gan_cbtd_vao_df()` — suy ra (xã, ấp) từ dgd_map và join HSTD qua (Tên xã, Tên thôn) lowercase
- `tabs/tab_cbtd.py` — Viết lại toàn bộ (~550 dòng): schema mới `{ho_ten, pgd, ds_dgd, dien_thoai, ghi_chu, ngay_cap}`; UI gồm 3 sub-tab xem (Danh sách / Bản đồ ĐGD→CBTD / Chi tiết) + CRUD đầy đủ + báo cáo dư nợ theo CBTD; phát hiện trùng ĐGD real-time; preview ấp khi chọn ĐGD; backward-compat với data cũ

## [2026-05-16] — Cải tiến bảng "Thông tin tổng quát theo PGD"
- `tabs/tab_tongquan.py` — Đổi tên cột `TL NPL %` → `Tỷ lệ Nợ xấu` trong toàn bộ logic tính toán, hiển thị, và điều kiện tô màu
- `tabs/tab_tongquan.py` — Header bảng: thêm helper `_disp_col()` tách phần đơn vị `(Triệu đồng)` / `(Tỷ đồng)` xuống dòng 2; bỏ `white-space:nowrap`, thêm `min-width:60px`
- `tabs/tab_tongquan.py` — Data cells: tăng font-size từ `0.82/0.84rem` lên `0.90/0.92rem`
- `tabs/tab_tongquan.py` — PDF: thêm `_pdf_col()` đổi tên cột thành 2 dòng (`<br/>`) trước khi truyền vào `xuat_pdf()`

## [2026-05-16] — Fix định dạng ngày trong PDF báo cáo tiến độ công việc
- `tabs/tab_tien_do.py` — Import `fmt_ngay`; thay `t['ngay_deadline']` (ISO `YYYY-MM-DD`) bằng `fmt_ngay(...)` ở 2 chỗ trong `_xuat_pdf_bao_cao_tien_do()` (dòng ~1177, ~1323) và `ngay_bat_dau`/`deadline` trong `_xuat_pdf_tien_do()` (dòng ~1553)

## [2026-05-16] — Fix định dạng ngày trong PDF: Timestamp → dd/mm/yyyy
- `utils.py` — Thêm hàm `fmt_ngay(val)`: chuyển Timestamp/date/string sang `dd/mm/yyyy`, trả về `""` nếu không parse được
- `tabs/tab_no_rui_ro.py` dòng ~1624, ~1667 — Thay `str(row_full.get(COT_NGAY_VAY))` bằng `fmt_ngay(...)` khi lưu vào kv_store; trước đây Timestamp ra `"2023-05-15 00:00:00"` trong Word/PDF
- `pdf_service.py` — Thêm hàm `_str_val(val)` xử lý Timestamp → `dd/mm/yyyy`; thay thế `str(val)` ở 3 chỗ render cell (dòng ~429, ~763, ~1189) để toàn bộ cột ngày trong PDF hiển thị đúng định dạng VN

## [2026-05-16] — Nâng cấp UI: KPI accent, hover table, alert badge, scrollbar, spinner
- `app.py` CSS — KPI card: thêm border-left 4px xanh/đỏ theo delta, hover lift animation
- `app.py` CSS — Dataframe: header gradient đậm hơn + text-shadow, zebra stripe, hover row xanh nhạt
- `app.py` CSS — Alert: compact border-left theo loại (info/success/warning/error), nền tông màu riêng
- `app.py` CSS — Scrollbar 6px mỏng màu xanh NHCSXH, multiselect chip xanh, spinner xanh, progress bar gradient

## [2026-05-16] — Tối ưu hoá performance: nén parquet, TTL cache, cache hàm toan_cn
- `data/core.py` — `excel_to_parquet()`: thêm `compression_level=9` cho zstd (giảm ~70% dung lượng parquet)
- `services/upload_service.py` — merge toan_cn: thêm `compression_level=9` khi ghi `hstd/nq11/gqvl.parquet`
- `data/hstd.py` — Tất cả `@st.cache_data` không có TTL → thêm `ttl=7200`; ttl=3600 → 7200; thêm `compression_level=9` cho CACHE_GQVL và CACHE_SK_GQVL
- `data/pgd.py` — `ttl=300` → `ttl=7200` cho tất cả decorator; thêm `@st.cache_data(ttl=7200)` cho `doc_gqvl_toan_cn_pgd()` và `doc_nq11_toan_cn_pgd()` (trước đây không cached)

## [2026-05-16] — Fix deprecation warnings: use_container_width + dayfirst
- `utils.py` dòng 155 — Đổi `use_container_width=True` → `width='stretch'` trong `hien_thi_dataframe_phan_trang()` (Streamlit API mới)
- `data/hstd.py` dòng 238–240 — Thêm `dayfirst=True` vào 3 lần gọi `pd.to_datetime()` cho cột ngày định dạng DD/MM/YYYY

## [2026-05-16] — Fix "Nguồn vốn" toàn NaN sau khi merge GQVL
- `services/upload_service.py` dòng ~462 — Bỏ `"Nguồn vốn"` khỏi `_cols_so_cn` trong bước chuẩn hóa schema sau concat; cột này chứa text "TW"/"ĐP" nên không được ép `pd.to_numeric()` (đã có comment cảnh báo ở `_clean` nhưng bị nhầm thêm vào danh sách số ở bước merge)
- `cache/gqvl.parquet` + 22 `pgd_data/*/gqvl_latest.parquet` — Đã xóa cache bị hỏng, sẽ tự rebuild khi merge lại

## [2026-05-16] — Fix import hàng loạt: cache invalidation + force re-import
- `tabs/tab_upload_khnv.py` — Sửa cache `khnv_bulk_bytes` dùng `(tên, kích thước)` thay vì chỉ tên file để detect đúng khi upload cùng tên nhưng nội dung mới; thêm checkbox "Bắt buộc import lại" để ghi đè dù MD5 giống hệt; thêm style "🔁 Ghi đè" vào bảng so sánh; tách caption "Giống hệt" riêng khỏi "Bỏ qua"

## [2026-05-16] — Port 3 tính năng từ VSPPRO: Nợ khoanh, Top biến động, Radar+Ranking
- `tabs/tab_no_khoanh.py` **TẠO MỚI** — Phân tích Nợ khoanh (port Khoanh.tsx): 4 KPI cards, heatmap đáo hạn theo năm, breakdown theo Chương trình / Xã / ĐVUT (bar chart + bảng), danh sách chi tiết + xuất Excel
- `tabs/tab_so_sanh_ky.py` — Thêm `_render_top_bien_dong()` (Top N tăng/giảm theo chiều + chỉ tiêu, 2 biểu đồ bar ngang cạnh nhau) và `_render_radar_ranking()` (radar đa trục PGD + ranking horizontal bar) — port PeriodMovers.tsx + Compare.tsx
- `workspaces/ws_management.py` — Thêm item "Nợ khoanh" (icon lock) vào group "Kiểm soát" + lazy import `tab_no_khoanh`

## [2026-05-16] — Thêm tính năng "Cảnh báo sớm NQH" (port từ VSPPRO)
- `tabs/tab_canh_bao_som.py` **TẠO MỚI** — Module cảnh báo sớm: 2 KPI cards (Sắp đến hạn + KH không HĐ / Chuyển NQH trong tháng), toggle phạm vi Tháng/Quý/Năm, heatmap bar chart đáo hạn theo tháng, 2 sub-tabs danh sách chi tiết + xuất Excel
- `workspaces/ws_management.py` — Thêm sub-tab "⚡ Cảnh báo sớm" (sub5) vào `_render_canh_bao_no()` cho phân hệ Chi nhánh
- `workspaces/ws_operation.py` — Thêm `_render_canh_bao_som_pgd()` + item "⚡ Cảnh báo sớm" vào group "Kiểm soát & Rủi ro" cho phân hệ PGD

## [2026-05-16] — Thêm tab "Tập trung rủi ro & HHI" vào Phòng KH-NV
- `tabs/tab_hhi.py` **TẠO MỚI** — Tab HHI: 3 KPI cards (Chương trình / Xã / PGD), thang giải thích, sub-tabs biểu đồ cột ngang + treemap + bảng tổng hợp, nút xuất Excel 3 sheet
- `workspaces/ws_management.py` — Thêm `from tabs import tab_hhi` (lazy import), thêm item "Tập trung rủi ro & HHI" vào group "Kiểm soát" trong cả `_build_all_items()` lẫn `render()`

## [2026-05-16] — Refactor tab Mã NĐT ĐP thành 5 sub-tab; thêm field cap tinh/xa
- `db.py` — `doc_ndt_dp_list()` bổ sung field `cap` backward-compat; `doc_ndt_dp_ma_list()` chỉ trả mã cấp tỉnh
- `workspaces/ws_management.py` — Refactor `_render_ndt_dp()` thành 5 tab: Cấp Tỉnh / Cấp Xã/Khác / Thêm mới / Chỉnh sửa-Xóa / Phân tích; bỏ expander tác động; thêm dropdown phân loại cấp và nút Làm mới

## [2026-05-16] — Fix Nguồn vốn GQVL bị convert NaN; bổ sung cột dư nợ trong impact analysis
- `services/upload_service.py` dòng ~359 — Bỏ "Nguồn vốn" khỏi `_cols_so` GQVL (text "TW"/"ĐP", không phải số)
- `workspaces/ws_management.py` dòng ~518 — Thêm stale-cache warning + cột "Dư nợ TH (tỷ)" trong expander tác động NDT DP

## [2026-05-16] — KPI 12 cards + section ĐVUT + Nợ xấu + Tổng lãi tồn
- `tabs/tab_so_sanh_ky.py` — Mở rộng KPI thành 3 hàng × 4 cards (12 chỉ tiêu):
  - Hàng 1: Tổng DN, Số KU, Số hộ, Mức vay BQ/KH
  - Hàng 2: Tỷ lệ NQH, DN QH, DN khoanh, Tỷ lệ DN khoanh *(mới)*
  - Hàng 3: Nợ xấu (QH+Khoanh), Tỷ lệ Nợ xấu, Tổng lãi tồn (TH+QH), Giải ngân *(mới)*
- `tabs/tab_so_sanh_ky.py` — Thay "Lãi tồn TH" → "Tổng lãi tồn" = COT_LAI_TON + COT_LAI_TON_QH
- `tabs/tab_so_sanh_ky.py` — Thêm section "🏛️ So sánh theo Hội đoàn thể (ĐVUT)" với bảng đầy đủ: DN/±DN/Hộ/NQH/Nợ xấu theo từng ĐVUT + hàng tổng
- `tabs/tab_so_sanh_ky.py` — Thêm `_agg_theo_dvut()` helper; import thêm COT_DVUT, COT_LAI_TON_QH

## [2026-05-16] — Port PeriodOverview.tsx: 8 KPI, growth chart, flow diagram, quality bars
- `tabs/tab_so_sanh_ky.py` — KPI 4→8 cards (2 hàng: tăng trưởng + rủi ro)
- `tabs/tab_so_sanh_ky.py` — Thêm `_chart_tang_truong()`: grouped bar Altair theo chương trình/nguồn vốn/xã
- `tabs/tab_so_sanh_ky.py` — Thêm `_flow_diagram()`: visual flow boxes vòng đời KU và KH
- `tabs/tab_so_sanh_ky.py` — Thêm `_quality_bars()`: stacked bar Trong hạn/Quá hạn/Khoanh 2 kỳ
- `tabs/tab_so_sanh_ky.py` — Import thêm COT_LAI_TON, COT_TEN_CT, COT_NGUON_VON, COT_TEN_XA, altair

## [2026-05-16] — Mở rộng KPI cards từ 4 lên 8: thêm Số KU, DN khoanh, Lãi tồn TH, Mức vay BQ
- `tabs/tab_so_sanh_ky.py` — Thêm hàng KPI thứ 2 (k5–k8): Số KU, Dư nợ khoanh, Lãi tồn TH, Mức vay BQ/hộ
- `tabs/tab_so_sanh_ky.py` — `_agg_mot_pgd()` cập nhật tính thêm `lai_ton`, `muc_vay_bq`

## [2026-05-16] — Port thêm tính năng từ TypeScript: Explorer, Vintage NQH, Roll/Cure từ join trực tiếp
- `services/period_compare.py` — **Tạo mới** — port logic từ `period-compare.ts`:
  - `join_by_loan(df_prev, df_curr)` → ghép cặp khế ước theo khóa (soKU + maKH)
  - `classify_changes(df_joined)` → phân loại 8 loại biến động (mới/tất toán/chuyển xấu/cải thiện/tăng DN/giảm DN/gia hạn/không đổi)
  - `roll_cure_rate(df_joined)` → roll rate / cure rate từ join trực tiếp (không cần snapshot)
  - `vintage_nqh(df)` → NQH phân tích theo năm vay
  - `par_breakdown(df)` → PAR30/PAR90/PAR180 theo ngày đáo hạn
- `tabs/tab_so_sanh_ky.py` — Thêm 4 section mới:
  - **Biến động khế ước** (Explorer): filter 8 loại, sắp theo |Δ DN|, tối đa 500 dòng
  - **Roll rate / Cure rate** từ join trực tiếp (không cần snapshot riêng)
  - **Vintage NQH**: NQH theo năm vay, so sánh mốc vs hiện tại
  - Cập nhật PAR section → dùng PAR30/PAR90/PAR180 thay vì chỉ có 1 con số

## [2026-05-16] — Tính năng nâng cao: Tab So sánh kỳ
- `tabs/tab_so_sanh_ky.py` — Thêm 5 tính năng so sánh nâng cao:
  1. **Ma trận chuyển nhóm nợ** (Nhóm nợ A/B/C/D): từ loan-level snapshots (`migration_service.migration_matrix`)
  2. **Phân loại khách hàng** (Retained/Churned/New): phân tích lifecycle giữa 2 kỳ
  3. **Phân tích PAR** (Portfolio at Risk): tỷ lệ dư nợ quá hạn
  4. **Nồng độ rủi ro (HHI)** theo PGD: dùng Herfindahl-Hirschman Index + breakdown đóng góp (`hhi_service`)
  5. **Top movers**: Top N PGD có thay đổi lớn nhất về DN/NQH (slider chọn N=3-10)
- Widget key prefix động theo role/PGD để tránh DuplicateElementKey

## [2026-05-16] — Upload baseline 31/12 qua giao diện
- `tabs/tab_upload_khnv.py` — Thêm expander "📅 Upload mốc số liệu 31/12 (Baseline)": chọn năm, upload file, lưu vào `data/baseline/`, xóa cache parquet, ghi audit

## [2026-05-16] — Tính năng mới: Tab So sánh kỳ (hiện tại vs mốc 31/12)
- `tabs/tab_so_sanh_ky.py` — Tạo mới: KPI cards + bảng chi tiết chỉ tiêu + bảng theo PGD (CN role), dùng baseline `doc_baseline_merged()`
- `workspaces/ws_executive.py` — Thêm tab "📈 So sánh kỳ" (tab thứ 5)
- `workspaces/ws_management.py` — Thêm menu item "So sánh kỳ" nhóm Giám sát
- `workspaces/ws_operation.py` — Thêm tab "📊 So sánh kỳ" vào nhóm "Nghiệp vụ hàng ngày" (pgd_mode=True)

## [2026-05-16] — Tab đến hạn: khôi phục bảng tổng hợp PGD/Xã × Tháng
- `tabs/tab_den_han.py` — Thêm lại bảng tổng hợp theo PGD/Xã × tháng đến hạn (tính từ `df_loc` đã cache, không gọi lại `tinh_den_han_df`)

## [2026-05-16] — Fix: tháng 1-2-3/2027 không hiện trong biểu đồ đến hạn
- `tabs/tab_den_han.py` — Biểu đồ tháng re-parse `COT_NGAY_DEN_HAN` thiếu `dayfirst=True` → ngày dạng `'18/01/2027'` bị NaT, ngày có day≤12 bị đổi sang tháng khác; sửa bằng cách dùng cột `"Ngày đến hạn"` (đã parse đúng trong `tinh_den_han_df`)

## [2026-05-16] — Fix: "Số tháng có thể gia hạn" không có dữ liệu
- `data/den_han.py` — Thêm `_normalize_ma()` chuẩn hóa `'2.0'`→`'2'` (HSTD lưu mã CT dạng float string); thêm `_tinh_thoi_han_tu_ngay()` tính thời hạn vay từ `Ngày vay` - `Ngày ĐH theo hợp đồng` vì cột `Thời hạn vay` toàn null; sửa so sánh `== "02"` → `== "2"`

## [2026-05-16] — Tab đến hạn: tối ưu hiệu năng (vectorize + cache)
- `data/den_han.py` — Vectorize `tinh_den_han_df`: bỏ `_parse_ngay` + row-by-row `apply`, dùng `pd.to_datetime` + `np.select` (~10-20x nhanh hơn trên 30k hàng)
- `tabs/tab_den_han.py` — Thêm `@st.cache_data` cho `_doc_va_tinh_den_han(pgd_user, mtime)`, `_loc_thang()` helper; tránh gọi `tinh_den_han_df` 2 lần mỗi render

## [2026-05-16] — Tab đến hạn: thay cột "Tháng đến hạn còn lại" bằng "Số tháng được gia hạn nợ"
- `data/den_han.py` — Thêm hàm `_tinh_so_thang_gia_han(row)` áp dụng quy định NHCSXH (CT02: ½TH, CT17: 30t, QĐ29/54 hộ nghèo: 30t, ≤12t: 12t, >12t: ½TH); thêm cột "Số tháng được gia hạn nợ" vào `tinh_den_han_df()`
- `tabs/tab_den_han.py` — Thay "Tháng đến hạn còn lại" bằng "Số tháng được gia hạn nợ" trong `cols_hien_thi`, `COLS_CHI_TIET`, `_detail_pdf_cols`; đổi sort từ cột tháng còn lại sang "Ngày đến hạn"

## [2026-05-16] — Fix NameError: render_den_han trong ws_management.py
- `workspaces/ws_management.py` dòng ~174 — Thêm `from tabs.tab_den_han import render as render_den_han` vào `_render_canh_bao_no()` (import chỉ có trong `_render_canh_bao`, không lan sang hàm khác)

## [2026-05-16] — Thêm trang chủ (Home Dashboard) cho phân hệ PGD
- `workspaces/ws_operation.py` dòng ~39 — Thêm import: `db`, `fmt_ty`, `pgd_slug`
- `workspaces/ws_operation.py` dòng ~42–220 — Thêm hàm `_render_trang_chu()` với 4 vùng nội dung:
  * Vùng A (Header): Tên PGD, số hồ sơ, button Làm mới
  * Vùng B (KPI): 4 cards — Tổng dư nợ, Nợ quá hạn, 3 tháng KHĐ, Tiến độ KHTD (từ db.doc_kv + fmt)
  * Vùng C (Truy cập nhanh): 6 shortcut buttons → set session_state ["ws_op_nhom", "ws_op_jump_tab"] để nhảy tab
  * Vùng D (Cảnh báo + Nhiệm vụ): Hiển thị NQH, 3m KHĐ, danh sách nhiệm vụ từ db.doc_kv("nhiem_vu_list")
- `workspaces/ws_operation.py` dòng ~1119 — Thêm nhóm "trang_chu" ở đầu `CAC_NHOM` với tab "🏠 Trang Chủ"
- `workspaces/ws_operation.py` dòng ~1220–1228 — Xử lý navigation: pop "ws_op_jump_tab", hiển thị st.toast() khi nhảy tab

## [2026-05-16] — Cache hàm nặng để giảm độ trễ chuyển tab
- `data/hstd.py` dòng ~267 — Thêm `tong_hop_khong_hd_cached` và `canh_bao_migration_cached` với `@st.cache_data(ttl=3600)`
- `data/__init__.py` — Export 2 cached wrapper mới
- `workspaces/ws_management.py` — Thay `danh_dau_khong_hd`, `tong_hop_khong_hd`, `canh_bao_migration` → cached versions tại dòng 53, 58, 77, 86, 217, 222, 246
- `workspaces/ws_operation.py` — Thay `tong_hop_khong_hd` → `tong_hop_khong_hd_cached` tại dòng 69, 79
- `workspaces/ws_executive.py` — Thay `danh_dau_khong_hd`, `canh_bao_migration` → cached versions tại dòng 259, 264, 799

## [2026-05-16] — Thêm báo cáo Nợ Khoanh và Nợ Quá Hạn vào tab Báo cáo
- `tabs/tab_baocao.py` dòng ~502 — Thêm 2 option radio "🔴 Danh sách nợ khoanh" và "🟠 Danh sách nợ quá hạn" vào Mảng 2
- `tabs/tab_baocao.py` dòng ~677–755 — Nhánh nợ khoanh: lọc `Dư nợ khoanh > 0`, metrics + tổng hợp ĐVUT + danh sách chi tiết + export Excel
- `tabs/tab_baocao.py` dòng ~718–755 — Nhánh nợ quá hạn: lọc `COT_DU_NO_QH > 0`, metrics (Số món/Dư nợ QH/Tỷ lệ) + tổng hợp ĐVUT + danh sách chi tiết + export Excel
- `tabs/tab_baocao.py` dòng ~23 — Bổ sung `"Dư nợ khoanh"` và `"Nợ_khoanh"` vào `_COLS_TIEN` để `_fmt_df()` convert sang triệu đồng

## [2026-05-15] — Số tiền thuần trong bảng + dòng ĐVT: triệu đồng
- `tabs/tab_baocao.py` — `_fmt_df()`: cột tiền → số triệu đồng thuần (VN format 3 chữ số TP), không còn "tỷ"/"triệu" trong ô
- `tabs/tab_baocao.py` — Thêm `_hien_thi_bc()` wrapper: tự hiện `st.caption("ĐVT: triệu đồng")` trước mỗi bảng
- `tabs/tab_baocao.py` — Xóa call `_tao_column_config_baocao()` còn sót (hàm không còn tồn tại → sẽ crash)
- Áp dụng `_fmt_df` cho bảng đôn đốc ĐVUT (trước đây hiển thị số VND thô)

## [2026-05-15] — Bỏ cột Tổng mức vay khỏi tab Báo cáo
- `tabs/tab_baocao.py` — Xóa `Tổng_mức_vay` khỏi tất cả bảng tổng hợp (theo xã/thôn, ĐVUT, chương trình, nguồn vốn) và khỏi `COL_CHUNG` bảng chi tiết

## [2026-05-15] — Fix số KH / số món vay bị phồng trong tab Báo cáo
- `tabs/tab_baocao.py` dòng ~158 — Lọc `df_base[COT_TONG_DU_NO] > 0` sau filter Mảng 1 (Tổng hợp)
- `tabs/tab_baocao.py` dòng ~290 — Lọc `df_base[COT_TONG_DU_NO] > 0` sau filter Mảng 2 (Chi tiết)
- Loại bỏ ~25.627 hồ sơ đã tất toán (dư nợ = 0) khỏi đếm KH và món; KH giảm từ 245.489 → 213.343, món vay từ 323.673 → 292.739

## [2026-05-15] — Fix bảng số liệu tab Báo cáo tín dụng
- `tabs/tab_baocao.py` — Thay `_tao_column_config_baocao` (NumberColumn kiểu Mỹ) bằng `_fmt_df()` dùng `fmt_ty` → tiền hiển thị đúng định dạng VN
- `tabs/tab_baocao.py` — Fix chia cho 0 trong tính `Tỷ_lệ_QH_%` tại 5 bảng (thêm `.replace(0, nan).fillna(0)`)
- `tabs/tab_baocao.py` — Fix `vn()` không được import; thêm `fmt_ty`, `vn` vào imports
- `tabs/tab_baocao.py` — `Số_hồ_sơ` theo xã dùng `nunique` thay vì `count`; fix `la_phan_he_cn(role)` thay chuỗi cứng

## [2026-05-15] — Đồng bộ tên xã config với data HSTD thực tế
- `config.py` — `Bầu Hàm` → `Bàu Hàm`; `Đak Lua` → `Dak Lua` (khớp spelling trong data)
- `config.py` — giữ `Đăk Nhau` (data dùng ă, không phải a)
- Kết quả: PGD_XA_MAP và XA_THON_MAP khớp 100% tên xã trong HSTD; mã PGD 22/22 đúng

## [2026-05-15] — Sửa chính tả 2 xã trong config
- `config.py` — `Bầu Hàm` → `Bàu Hàm`; `Đăk Nhau` → `Đak Nhau` (cả PGD_XA_MAP lẫn XA_THON_MAP)

## [2026-05-15] — Thêm XA_THON_MAP và cập nhật PGD_XA_MAP
- `config.py` — Thêm `XA_THON_MAP` (97 xã → danh sách thôn/ấp/khu phố, nguồn CN46_Danh muc thon_12-05-2026.xls) và `THON_TO_XA` (reverse lookup thôn → xã)
- `config.py` — Bổ sung `"Xã Phú Thịnh"`, `"Xã Phú Đức"` vào `PGD_XA_MAP["PGD Bình Long"]`
- `config.py` — Sửa `"Phường Xuân Khánh"` → `"Phường Long Khánh"` trong `PGD_XA_MAP["PGD Long Khánh"]`

## [2026-05-15] — Sidebar dark green NHCSXH brand
- `app.py` dòng ~75 — Đổi sidebar từ trắng-xanh nhạt sang gradient xanh đậm `#1B5E20→#2E7D32→#388E3C`; chữ/icon trắng; nút bán trong suốt; thêm box-shadow

## [2026-05-15] — Tối ưu hiệu năng: cache danh_dau_khong_hd, bỏ cache_data.clear() thừa, tăng TTL
- `data/hstd.py` — Thêm `danh_dau_khong_hd_cached()` với `@st.cache_data(ttl=3600)` tránh tính 4 lần/rerun
- `data/__init__.py` — Export `danh_dau_khong_hd_cached`
- `workspaces/ws_management.py` — Thay `id(df_full)` session_state cache bằng `danh_dau_khong_hd_cached()`; bỏ 3 lần `st.cache_data.clear()` sau thao tác NDT (không cần thiết, chỉ xóa cache parquet không liên quan)
- `workspaces/ws_operation.py` — Dùng `danh_dau_khong_hd_cached()` tại 3 chỗ gọi
- `data/pgd.py` — Tăng TTL `_doc_ngay_so_lieu` và `doc_trang_thai_file` từ 30s → 300s

## [2026-05-15] — Thêm health_check.py kiểm tra sức khỏe hệ thống
- `health_check.py` — Script CLI mới, không import Streamlit; kiểm tra 13 điểm: DB/bảng tồn tại, kv_store không corrupt, khtd_cn, merge_meta_hstd, 3 parquet cache, upload HSTD 22 PGD, audit log 24h; in ✅/❌ từng check + bảng 5 log gần nhất + tổng kết exit-code

## [2026-05-15] — Mở rộng tab Trạng thái hệ thống cho mọi role + thêm vào ws_operation
- `workspaces/ws_management.py` — Xóa guard `if la_phan_he_cn(role_n)`, tab "Trạng thái hệ thống" hiển thị cho mọi role CN
- `workspaces/ws_operation.py` — Thêm tab "Trạng thái hệ thống" vào nhóm Quản trị PGD
- `tabs/tab_trang_thai_nguon.py` — Bỏ guard cứng CN/PGD; thêm sub-tab "Trạng thái PGD" kiểm tra file HSTD/NQ11/GQVL (✅/⚠️/❌) + audit log theo PGD
- `docs/ARCHITECTURE.md` — Cập nhật danh sách tab ws_management, ws_operation
- `docs/HUONG_DAN_PHAN_HE.md` — Cập nhật danh sách tab cho CN và PGD

## [2026-05-15] — Cải thiện Dashboard + Tab Tiến độ
- `tabs/tab_tongquan.py` — fix màu 10 thẻ KPI (soft-indigo/blue/green/red/amber)
- `tabs/tab_tongquan.py` — fix bug Nguồn TW/ĐP (so sánh float thay string)
- `tabs/tab_tongquan.py` — fix Thu nợ năm (cộng TH+QH+Khoanh)
- `tabs/tab_tongquan.py` — fix bảng cơ cấu dư nợ 12 cột đầy đủ
- `tabs/tab_tongquan.py` — fix lỗi import streamlit as _st trong hàm render()
- `workspaces/ws_management.py` — fix lỗi import streamlit as st trong hàm
- `tabs/tab_tien_do.py` — thêm field "Loại theo dõi" (pgd/xa) form tạo đầu việc
- `tabs/tab_tien_do.py` — thêm field Người phụ trách, Ngày bắt đầu
- `tabs/tab_tien_do.py` — chuẩn hóa key widget prefix tao_task_*
- `tabs/tab_tien_do.py` — đổi text_input → text_area chống Enter submit
- `tabs/tab_tien_do.py` — thêm xuất PDF tiến độ + báo cáo trễ hạn Excel/PDF
- `tabs/tab_tien_do.py` — cập nhật LOAI_TASK 11 loại đầy đủ
- `tabs/tab_tien_do.py` — đổi "deadline" → tiếng Việt toàn bộ
- `tabs/tab_tien_do.py` — thêm hướng dẫn chi tiết form tạo đầu việc
- `CLAUDE.md` — cập nhật workflow Trae + Claude Code Desktop + model
- `.streamlit/config.toml` — thêm watchdog auto-reload

## [2026-05-14] — Tiến độ nhiệm vụ: thêm loại Chung PGD / Chi tiết xã + metadata
- `db.py` — Migration: ALTER TABLE thêm `loai_noi_dung TEXT` vào `tien_do_ketqua`, `ngay_bat_dau TEXT` + `nguoi_phu_trach TEXT` vào `tien_do_task`
- `tabs/tab_tien_do.py` — `_khoi_tao_ketqua_task()`: thêm tham số `loai_noi_dung`, ghi vào DB mỗi dòng kết quả
- `tabs/tab_tien_do.py` — `_render_tao_task()`: thêm field `ngay_bat_dau` (date_input) + `nguoi_phu_trach` (text_input), lưu vào DB
- `tabs/tab_tien_do.py` — `_render_tong_quan()`: thêm filter "Loại nhiệm vụ" (Tất cả/Chung PGD/Chi tiết xã); KPI labels generic (✅ Hoàn thành, 🔴 Trễ hạn)
- `tabs/tab_tien_do.py` — `_render_cap_nhat()`: hiển thị tag 🏢 Chung PGD / 🏘️ Chi tiết xã bên cạnh tên task

## [2026-05-14] — Cải thiện Dashboard: sắp xếp KPI, thêm biểu đồ Top 10, bảng PGD dễ đọc hơn
- `tabs/tab_tongquan.py` dòng ~380 — Sắp xếp lại 10 KPI Cards: Hàng 1 (Món vay, KH, Dư nợ, Trong hạn) → Hàng 2 (QH, TL QH, Khoanh, TL Khoanh) → Hàng 3 (NPL, 3m KHD)
- `tabs/tab_tongquan.py` dòng ~635 — Thêm biểu đồ Plotly stacked bar ngang "Top 10 chương trình theo dư nợ" (xanh TW + cam ĐP)
- `tabs/tab_tongquan.py` dòng ~1078 — Header bảng PGD tăng font 0.78/0.82rem → 13px
- `tabs/tab_tongquan.py` dòng ~1094 — Zebra stripes rõ hơn (#F5F7FA / #FFFFFF), dòng tổng nền #C8E6C9 đậm + font 0.84rem
- `tabs/tab_tongquan.py` dòng ~1098 — Cột % đỏ nếu vượt ngưỡng: TL QH > 0.5%, TL NPL > 0.3%, TL Khoanh > 1%

## [2026-05-14] — Fix tách nguồn TW/ĐP dùng `Nguồn vốn` thay vì map tên + sửa alias thu nợ
- `config.py` dòng ~263 — Sửa `HSTD_THU_NO_NAM_ALIASES` từ 6 alias sai (`"trong năm"`, chữ thường `"năm"`) → 3 alias đúng (`"Thu nợ TH Năm"`, `"Thu nợ QH Năm"`, `"Thu nợ Khoanh Năm"`)
- `tabs/tab_tongquan.py` dòng ~548 — Bỏ `_NGUON_MAP` (map tên chương trình → TW/DP, `.fillna("TW")` sai DP)
- `tabs/tab_tongquan.py` dòng ~549 — Thay bằng group trực tiếp theo `COT_NGUON_VON` (`"1"`=TW, `"2"`=DP) → `.map()` vào `df_ct`
- `tabs/tab_tongquan.py` dòng ~16 — Xóa dead import `CHUONG_TRINH_KHTD`

## [2026-05-14] — Format số VN: tiền tệ dùng `fmt_ty()`, `%` dùng replace `.` → `,`
- `tabs/tab_tongquan.py` dòng ~23 — Thêm `fmt_pct` vào import từ utils
- `tabs/tab_tongquan.py` dòng ~627 — 7 cột tiền tệ: bỏ `/1e12`, dùng `.apply(fmt_ty)` trên raw đồng (fmt_ty tự chia 1e9 + VN format)
- `tabs/tab_tongquan.py` dòng ~635 — Cột Tỷ lệ QH % và Tỷ trọng %: lambda `f"{x:.2f}".replace(".", ",") + "%"` (đơn giản, không swap 2 bước)
- `tabs/tab_tongquan.py` dòng ~208 — `_tao_column_config_co_cau()`: xoá NumberColumn cho % và tiền tệ, chỉ giữ config cho Số món vay + Số KH
- `tabs/tab_tongquan.py` dòng ~681 — Gọi `_tao_column_config_co_cau()` thay inline dict

## [2026-05-14] — Mở rộng bảng "Cơ cấu dư nợ theo chương trình tín dụng" — thêm 6 cột + sửa đơn vị
- `tabs/tab_tongquan.py` dòng ~197 — Cập nhật `_tao_column_config_co_cau()` với config cho 9 cột mới
- `tabs/tab_tongquan.py` dòng ~587 — Sửa `/1e9` → `/1e12` cho tất cả cột tiền tệ (theo quy ước `fmt_ty()`)
- `tabs/tab_tongquan.py` dòng ~619 — Thêm cột Dư nợ QH (tỷ) + Tỷ lệ QH % từ `COT_DU_NO_QH`
- `tabs/tab_tongquan.py` dòng ~627 — Thêm cột Dư nợ khoanh (tỷ) từ cột `"Dư nợ khoanh"` nếu tồn tại
- `tabs/tab_tongquan.py` dòng ~635 — Thêm cột Giải ngân năm (tỷ) từ `HSTD_DS_CHO_VAY_NAM_ALIASES`
- `tabs/tab_tongquan.py` dòng ~643 — Thêm cột Thu nợ năm (tỷ) từ `HSTD_THU_NO_NAM_ALIASES`

## [2026-05-14] — An toàn + Hiệu năng: NQ11 query user PGD dùng JOIN DataFrame thay IN chuỗi + cache session_state
- `app.py` dòng ~534–556 — Thay SQL `IN ('KH001','KH002',...)` build bằng string join thành DuckDB `JOIN` trực tiếp với `makh_df` (pandas DataFrame), tránh SQL injection + chuỗi SQL khổng lồ, không cần register/unregister
- `app.py` dòng ~534 — Cache kết quả vào `st.session_state["nq11_pgd_cache"]` với 3 trường: `data`, `ts_nq11 = ts_file(CACHE_NQ11)`, `pgd_user`. Chỉ query lại khi file NQ11 hoặc pgd_user thay đổi

## [2026-05-14] — Lazy import workspace: ws_management & ws_operation, chuyển ~30 import tab vào trong render()
- `workspaces/ws_management.py` — Xóa 24 dòng import tab top-level; thêm lazy imports vào `render()` (16 tab) + `_render_canh_bao()` (render_den_han) + `_render_dgd_to_tkvv()` (tab_quan_ly_dgd, tab_cdtotkvv)
- `workspaces/ws_operation.py` — Xóa 22 dòng import tab top-level; thêm lazy imports vào `render()` (17 tab + render_den_han)

## [2026-05-14] — Lazy import data/__init__.py: giao_ban, cdtotkvv, khtd không còn eager
- `data/__init__.py` dòng ~41–54 — Xóa eager import `cdtotkvv`, `khtd`, `giao_ban`; thay bằng comment lazy
- `workspaces/ws_executive.py` dòng ~22 — Tách `doc_kehoach` sang `from data.khtd import ...`
- `tabs/tab_kehoach.py` dòng ~10 — Tách `doc_kehoach, luu_kehoach` sang `from data.khtd import ...`
- `tabs/tab_cbtd.py` dòng ~16 — Chuyển `from data import doc_cbtd, luu_cbtd` sang `from data.khtd import ...`

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
