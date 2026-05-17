# CHANGELOG

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
