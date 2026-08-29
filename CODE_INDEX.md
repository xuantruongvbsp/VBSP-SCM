# CODE_INDEX — Tra nhanh file cần sửa

> **TỰ SINH** bởi `scripts/gen_code_index.py`. Chạy lại sau khi thêm file mới.
> Dành cho agent. Chỉ map chức năng → file → hàm.

---

## Core (luôn cần đọc trước)

| File | Hàm chính |
|---|---|
| `app.py` | `show_logo()`, `render_splash()`, `render_workspace_picker()`, `main()` |
| `auth.py` | `normalize_role()`, `role_label()`, `role_requires_pgd()`, `manageable_roles_for()`, `is_cn_role()` |
| `config.py` | `baseline_path()`, `baseline_cache()`, `danh_sach_nam_baseline()`, `baseline_pgd_path()`, `baseline_pgd_path_loai()` |
| `db.py` | `get_db_path()`, `get_conn()`, `reset_conn()`, `export_kv_json()`, `import_kv_json()` |
| `utils.py` | `norm_col_header()`, `auto_audit()`, `lay_config()`, `lay_ngay_so_lieu()`, `format_df_vn()` |
| `snapshot_service.py` | `luu_snapshot()`, `doc_snapshot()`, `doc_snapshot_range()`, `danh_sach_ky()`, `ky_baseline()` |

---

## Workspaces

| File | Hàm chính |
|---|---|
| `workspaces/ws_executive.py` | `render_sidebar_menu()`, `render()` |
| `workspaces/ws_management.py` | `render_sidebar_menu()`, `render()` |
| `workspaces/ws_operation.py` | `render_sidebar_menu()`, `render()` |

---

## Data Layer

| File | Hàm chính |
|---|---|
| `data/core.py` | `ts_file()`, `excel_to_parquet()`, `tong_hop_du_no_pgd()`, `dem_no_qua_han_pgd()`, `tong_hop_theo_xa()` |
| `data/hstd.py` | `doc_file()`, `doc_baseline()`, `doc_baseline_pgd()`, `ts_baseline_merged()`, `doc_baseline_merged()` |
| `data/pgd.py` | `pgd_slug()`, `thu_muc_pgd()`, `duong_dan_pgd()`, `kiem_tra_file_ton_tai_pgd()`, `duong_dan_hstd_hien_hanh()` |
| `data/khtd.py` | `doc_khtd()`, `luu_khtd()`, `doc_kehoach()`, `luu_kehoach()`, `doc_cbtd()` |
| `data/den_han.py` | `tinh_den_han_df()`, `loc_den_han_trong()`, `tong_hop_den_han()`, `canh_bao_tap_trung()` |
| `data/giao_ban.py` | `loc_theo_xa()`, `loc_baseline_cung_xa_pgd()`, `tinh_so_lieu_van_xuoi()`, `tao_bang_dvut()`, `tao_bang_chuong_trinh()` |
| `data/phan_ky_nxh.py` | `luu_phan_ky_nxh()`, `doc_phan_ky_nxh()`, `lay_ngay_du_lieu_phan_ky_nxh()` |

---

## Components

| File | Hàm chính |
|---|---|
| `components/delta_card.py` | `delta_card()`, `info_popover()`, `kpi_row()` |
| `components/export_pdf.py` | `fig_to_bytes()`, `xuat_pdf_co_chart()`, `download_pdf_button()` |
| `components/filter_bar.py` | `load_filter_presets()`, `save_filter_presets()`, `get_last_filter_preset_name()`, `set_last_filter_preset_name()`, `filter_bar()` |
| `components/loan_drawer.py` | `loan_detail_drawer()` |
| `components/movers.py` | `movers_analysis()` |

---

## Services

| File | Mô tả | Hàm chính |
|---|---|---|
| `services/bc_tongquan_service.py` | Dịch vụ xuất báo cáo Quản lý Công việc & Nhiệm vụ. | `tao_bc_tongquan()`, `loc_du_lieu_tien_do()`, `loc_du_lieu_nhiem_vu()`, `tinh_kpi()`, `tao_ma_tran()` |
| `services/cbtd_dia_ban_service.py` | Hàm xử lý dữ liệu (không có st.*) phục vụ Dashboard CBTD & Địa bàn. | `lay_to_theo_cbtd()`, `canh_bao_cbtd_dia_ban()`, `tom_tat_kpi()` |
| `services/cdtotkvv_service.py` | Các hàm xử lý dữ liệu thuần (không có st.*) cho tab Chấm điểm Tổ TK&VV. | `tong_hop_tu_pgd_data()`, `bang_trang_thai_cdtotkvv()`, `loc_df()`, `cdtotkvv_ten_sheet_excel()`, `fmt_xuat_to_khong_dat_vn()` |
| `services/ct_discovery.py` | Quét 3 file hàng ngày → cập nhật registry chương trình theo PGD. | `doc_ct_registry()`, `ghi_ct_registry()`, `quet_va_ghi_chuong_trinh()`, `doc_ket_qua_quet_cuoi()` |
| `services/data_priority.py` | Hiển thị trạng thái dữ liệu PGD — chỉ dùng cho widget sidebar/status, không quyế | `kiem_tra_nguon_uu_tien()` |
| `services/data_priority_service.py` | Dịch vụ Trạng thái Dữ liệu - VBSP SCM | `kiem_tra_nguon_uu_tien()`, `bao_cao_trang_thai_nguon()`, `cap_nhat_nguon_uu_tien()`, `lay_bao_cao_nguon()`, `render_widget_trang_thai()` |
| `services/data_quality.py` | Lớp chuẩn hóa và kiểm soát chất lượng dữ liệu tập trung. | `chuan_hoa_ten_cot()`, `kiem_tra_du_no_am()`, `kiem_tra_so_tien_giai_ngan()`, `kiem_tra_ma_don_vi_hop_le()`, `chuan_hoa_ma_don_vi()` |
| `services/du_phong_service.py` | Dự phóng Doanh số Thu nợ & Kế hoạch Dòng tiền — PGD / Xã. | `du_phong_dong_tien()`, `du_phong_chi_tiet()` |
| `services/excel_service.py` | Dịch vụ xuất Excel chuyên nghiệp (chuẩn VSPPRO) — KPI sheet + Detail sheet + Bìa | `xuat_excel_chuyen_nghiep()`, `ten_file_xuat()` |
| `services/file_detection_service.py` | Nhận diện loại file và tên đơn vị từ nội dung file Excel. | `md5_bytes()`, `md5_file()`, `chuan_hoa_ten()`, `ten_doc_ve_don_vi_chuan()`, `lay_ten_don_vi_trong_file()` |
| `services/giao_ban_thang_service.py` | Dịch vụ xuất báo cáo giao ban tháng tổng hợp toàn Chi nhánh — PDF A4 landscape. | `tao_bao_cao_giao_ban_thang()` |
| `services/hhi_service.py` | Giám sát tập trung rủi ro — Chỉ số Herfindahl-Hirschman (HHI). | `tinh_hhi()`, `tinh_hhi_breakdown()`, `danh_gia_hhi()` |
| `services/hstd_word_service.py` | Dịch vụ xuất báo cáo Tổng hợp HSTD Word (.docx) — toàn Chi nhánh. | `xuat_word_hstd_tong_hop()` |
| `services/ke_hoach_cv_khnv_service.py` | Service đọc Google Sheets kế hoạch/kết quả công việc nội bộ Phòng KH-NV. | `doc_config()`, `luu_config()`, `lay_loi_doc_gsheet_gan_nhat()`, `doc_ke_hoach()`, `doc_ket_qua()` |
| `services/khnv_bao_cao_service.py` | Dịch vụ tổng hợp dữ liệu cho báo cáo KHNV hàng tháng. | `tong_hop_so_lieu_thang()`, `tong_hop_tu_dienbao()`, `so_sanh_hstd_vs_dienbao()`, `lay_danh_sach_mau()`, `doc_noi_dung_mau()` |
| `services/khnv_lich_tuan_service.py` | Dịch vụ xuất Lịch làm việc tuần KH-NV ra file Word. | `xuat_lich_bang_tuan()`, `lay_tuan_tiep_theo()`, `xuat_lich_lam_viec_tuan()` |
| `services/khnv_noi_bo_service.py` | — | `doc_ds()`, `ghi_ds()` |
| `services/khtd_import_service.py` | Import Biểu 01C / Biểu 02C từ TTBC; lưu/đọc Thuyết minh và KH dư nợ tương lai. | `doc_bieu_01c()`, `luu_bieu_01c()`, `doc_bieu_01c_xd()`, `luu_bieu_02c()`, `doc_bieu_02c()` |
| `services/khtd_mau07_service.py` | Service cho Mẫu 07 — Giao/Điều chỉnh KHTD theo Ấp/Thôn. | `tinh_du_no_ap_baseline()`, `lay_so_goc_cho_ap()`, `xuat_mau07_word()` |
| `services/khtd_nhap_service.py` | Service: các hàm thuần túy cho tab KHTD Nhập (không có st.* calls). | `clean_sheet_name()`, `tinh_th_gqvl_phan_tang()`, `format_kich_thuoc()`, `doc_meta_qd()`, `luu_meta_qd()` |
| `services/khtd_service.py` | Dịch vụ KHTD — Giao KHTD & Điều chỉnh KHTD: Google Sheet, kv_store, duyệt, lũy k | `ghi_kv_va_audit()`, `luu_khtd_dict()`, `kv_key_mau07()`, `luu_khtd_mau07()`, `kv_key_dot()` |
| `services/khtd_xuat_service.py` | Xuất Excel / Word cho tab Xây dựng KHTD tương lai. | `xuat_excel_1pgd()`, `xuat_excel_tong_hop_cn()`, `xuat_word_bao_cao_pgd()`, `xuat_word_tong_hop_cn()` |
| `services/kiem_soat_service.py` | Kiểm soát Chi nhánh — registry báo cáo + render từng loại. | `chon_pgd_filter()`, `render_gqvl_tw_gan_mandt()`, `render_3m_khd()`, `render_nqh()`, `render_to_sai_so_tv()` |
| `services/ktnb_service.py` | KTNB Service — Kiểm toán Nội bộ (Internal Audit) | `them_dot_kiem_tra()`, `cap_nhat_dot_kiem_tra()`, `lay_danh_sach_dot()`, `lay_dot_by_id()`, `cap_nhat_thanh_phan_doan()` |
| `services/migration_service.py` | Ma trận chuyển dịch nhóm nợ — Loan-level snapshots + Migration Matrix. | `luu_snapshot()`, `danh_sach_ky()`, `doc_snapshot()`, `migration_matrix()` |
| `services/no_khoanh_service.py` | Helpers thuần dữ liệu cho tab Nợ khoanh — không phụ thuộc Streamlit. | `loc_khoanh()`, `bang_theo_nhom()` |
| `services/no_rui_ro_service.py` | — | `tao_kv_key_thang()`, `tao_kv_key()`, `doc_ho_so()`, `luu_ho_so()`, `xoa_ho_so()` |
| `services/onedrive_service.py` | OneDrive Service — Upload file công văn lên OneDrive qua Microsoft Graph API. | `kiem_tra_ket_noi()`, `upload_cong_van()` |
| `services/period_compare.py` | Logic so sánh hai kỳ cấp độ khế ước — port từ period-compare.ts. | `join_by_loan()`, `roll_cure_rate()`, `classify_changes()`, `vintage_nqh()`, `par_breakdown()` |
| `services/phan_loai_service.py` | Phân loại khách hàng theo mức độ rủi ro dựa trên dư nợ và lịch sử. | `phan_loai_khach_hang()`, `thong_ke_phan_loai()`, `tom_tat_cn()` |
| `services/report_service.py` | Dịch vụ xuất báo cáo Excel với định dạng chuẩn VBSP. | `xuat_bao_cao()`, `xuat_bao_cao_nang_cao()`, `ten_file_bao_cao()`, `xuat_sheet_don()` |
| `services/report_submission_service.py` | report_submission_service.py — Service lõi cho luồng PGD nộp báo cáo về Chi nhán | `chuan_hoa_ten_pgd()`, `lay_loi_doc_gsheet_gan_nhat()`, `kiem_tra_ket_noi_gsheet()`, `doc_du_lieu_gsheet()`, `doc_deadline_config()` |
| `services/so_sanh_ky_service.py` | Các hàm xử lý dữ liệu thuần (không có st.*) cho tab So sánh kỳ. | `agg_mot_pgd()`, `agg_theo_pgd()`, `agg_theo_dvut()`, `group_bien_dong()`, `delta_str()` |
| `services/telegram_delta.py` | So sánh snapshot Telegram đầu ngày với dữ liệu hiện tại, không có I/O. | `diff_deadline()`, `diff_progress()`, `diff_due_loans()` |
| `services/telegram_jobs.py` | Registry các job Telegram có thể chạy thủ công hoặc theo lịch. | `telegram_job_keys()`, `telegram_job_dedupe_key()`, `run_telegram_job()` |
| `services/telegram_schedule_service.py` | Rule engine cho Telegram scheduler, lưu cấu hình và runlog bằng kv_store. | `default_schedule_config()`, `doc_schedule_config()`, `normalize_rule()`, `validate_schedule_config()`, `luu_schedule_config()` |
| `services/telegram_service.py` | Gửi thông báo Telegram 1 chiều cho VBSP-SCM (push notification). | `luu_config()`, `luu_extra_chat()`, `luu_group_chat()`, `doc_deadline_bc_allowlist()`, `luu_deadline_bc_allowlist()` |
| `services/template_detection_service.py` | Tự động phát hiện cấu trúc cột từ file Excel/CSV mẫu để tạo template. | `phat_hien_cau_truc()` |
| `services/template_manager.py` | CRUD template cấu hình Google Sheet → kv_store. | `doc_ds_template()`, `doc_template()`, `luu_template()`, `xoa_template()`, `ten_da_ton_tai()` |
| `services/template_service.py` | Template-based document generation cho VBSP-SCM. | `co_template()`, `dien_template()`, `docx_to_pdf()`, `docx_bytes_to_pdf()`, `nut_tai_word_va_pdf()` |
| `services/tien_do_excel_service.py` | Xuất Excel báo cáo Tiến độ công việc — pure openpyxl, không phụ thuộc Streamlit. | `xuat_excel_tien_do()` |
| `services/tien_do_service.py` | — | `doc_tasks()`, `doc_ketqua_task()`, `khoi_tao_ketqua_task()`, `sync_bien_hoa_ketqua()`, `upsert_ketqua_xa()` |
| `services/tongquan_cdto_service.py` | Dịch vụ load & tính KPI CDTOTKVV toàn Chi nhánh — dùng chung cho tab Tổng quan v | `load_cdto_toan_cn()`, `compute_totkvv_kpi()`, `render_totkvv_html()`, `health_check_cdto()` |
| `services/tongquan_service.py` | Service: các hàm thuần túy cho tab Tổng quan (không có st.* calls). | `dem_so_to_hstd()`, `loc_ho_so_con_du_no()`, `tinh_kpi_tongquan()`, `tinh_heatmap_pgd()`, `tinh_co_cau_ct()` |
| `services/upload_service.py` | Dịch vụ xử lý upload file tập trung (Upload Service). | `duong_dan_pgd()`, `danh_gia_chat_luong_file_upload()`, `kiem_tra_file()`, `kiem_tra_file_he_thong()`, `luu_file_he_thong()` |
| `services/uy_thac_pdf_service.py` | Tạo PDF báo cáo số liệu và báo cáo điều hành Ủy thác bằng ReportLab. | `tao_pdf_bao_cao_dang_xem()`, `tao_pdf_dieu_hanh_uy_thac()` |
| `services/uy_thac_service.py` | — | `tong_quan_uy_thac()`, `danh_sach_to_co_lai_ton()`, `danh_sach_to_da_hoi()`, `tong_quan_dieu_hanh_uy_thac()`, `tong_hop_uy_thac_theo()` |
| `services/validation_schema.py` | Schema validation tập trung — single source of truth cho mọi quy tắc kiểm tra dữ | `get_schema()` |
| `services/validation_service.py` | Service validation dữ liệu đa tầng cho hệ thống VBSP-SCM | `validate_hstd_cross_pgd_duplicates()`, `validate_dataframe()`, `get_validation_summary()` |
| `services/xlrr_export_service.py` | Service xuất/nhập Excel cho luồng dữ liệu PGD → CN. | `xuat_danh_sach_rui_ro_excel()`, `nhap_danh_sach_rui_ro_excel()`, `merge_du_lieu_pgd_vao_cn()`, `tong_hop_theo_bien_phap()` |

---

## Tabs

| File | Mô tả | Hàm chính |
|---|---|---|
| `tabs/bc_tong_hop.py` | Báo cáo tổng hợp Quản lý Công việc & Nhiệm vụ. | `render()` |
| `tabs/tab_audit_log.py` | Tab Lịch sử giao dịch — hiển thị audit log (full mode cho Admin, compact cho mọi | `render()` |
| `tabs/tab_ban_dai_dien.py` | tab_ban_dai_dien.py — Ban Đại Diện HĐQT | `render()` |
| `tabs/tab_bao_cao_dinh_ky.py` | Tab Báo cáo Định kỳ — ROADMAP §2.1 | `render()` |
| `tabs/tab_bao_cao_giao_ban_pgd.py` | Báo cáo Giao ban PGD — tổng hợp dư nợ, cho vay, thu nợ theo ĐVUT và Xã. | `render()` |
| `tabs/tab_bien_ban_giao_ban.py` | Biên bản họp giao ban xã — xuất Word từ dữ liệu HSTD và baseline. | `render()` |
| `tabs/tab_candoi.py` | Tab Cân đối — Điện báo Chi nhánh. | `render()` |
| `tabs/tab_canh_bao_nqh.py` | Tab Cảnh báo Tín dụng — 7 sub-tab gom tất cả cảnh báo. | `render()` |
| `tabs/tab_canh_bao_som.py` | Nợ đến hạn có nguy cơ — khoản vay sắp đến hạn + KH không hoạt động > 90 ngày. | `tinh_du_soon_dormant()`, `tinh_chuyen_nqh_thang()`, `render()` |
| `tabs/tab_canh_bao_som_pgd.py` | Cảnh báo sớm đầy đủ cho PGD — Migration & 3 tháng không hoạt động. | `render()` |
| `tabs/tab_cbtd.py` | Tab CBTD — Quản lý Cán bộ Tín dụng theo ĐGD. | `render()` |
| `tabs/tab_cbtd_dashboard.py` | Tab Dashboard CBTD & Địa bàn — Tổng quan nhóm CBTD + ĐGD + Tổ TK&VV. | `render()` |
| `tabs/tab_cdtotkvv.py` | Tab Chấm điểm Tổ TK&VV — chỉ admin/manager. | `render()` |
| `tabs/tab_cdtotkvv_pgd.py` | Tab Chấm điểm Tổ TK&VV — ws_operation: chỉ dữ liệu upload của PGD (pgd_data). | `render()` |
| `tabs/tab_checklist_bc.py` | Tab Checklist Báo cáo — Quản lý checklist kiểm soát báo cáo định kỳ. | `render()` |
| `tabs/tab_danhsach.py` | Tab Danh sách & Lọc. | `render()` |
| `tabs/tab_dashboard_dgd_pgd.py` | Dashboard mini: KPI Điểm Giao Dịch & Tổ TK&VV trong phạm vi 1 PGD. | `render()` |
| `tabs/tab_dashboard_suc_khoe_pgd.py` | Dashboard Sức khỏe Tín dụng cho PGD — Gauge NQH + Heatmap rủi ro theo Xã. | `render()` |
| `tabs/tab_data_quality.py` | Tab Chất lượng Dữ liệu — phân tích toàn diện HSTD/NQ11/GQVL sau merge. | `render()` |
| `tabs/tab_den_han.py` | Tab Cảnh báo Khoản vay Đến hạn & Nợ đến hạn có nguy cơ. | `render()` |
| `tabs/tab_diem_gd_pgd.py` | Tab 📍 Điểm GD của tôi — CBTD cấu hình dgd_map chỉ trong phạm vi PGD đăng nhập. | `render()` |
| `tabs/tab_doc_hub.py` | Trung tâm Tự động hóa Văn bản — điền mẫu Word hàng loạt từ dữ liệu HSTD. | `render()` |
| `tabs/tab_don_doc_khd.py` | Đôn đốc 3 tháng không hoạt động — CBTD địa bàn PGD. | `render()` |
| `tabs/tab_donut_co_cau_pgd.py` | Donut chart — cơ cấu dư nợ theo chương trình tín dụng, phạm vi PGD. | `render()` |
| `tabs/tab_du_phong_dong_tien_pgd.py` | Dự phóng Doanh số & Kế hoạch Dòng tiền — phạm vi 1 PGD. | `render()` |
| `tabs/tab_gqvl.py` | Tab Theo dõi chỉ tiêu Giải quyết Việc làm (GQVL). | `render()` |
| `tabs/tab_gqvl_pgd.py` | Tab Giải quyết Việc làm (GQVL) — Phân hệ PGD. | `render()`, `render_tab()` |
| `tabs/tab_heatmap_dao_han_pgd.py` | Heatmap Đáo hạn — dư nợ đến hạn theo Tháng × Chương trình, phạm vi PGD. | `render()` |
| `tabs/tab_hhi.py` | Tab Nguồn vốn địa phương — Phân hệ Chi nhánh. | `render()` |
| `tabs/tab_histogram_du_no_pgd.py` | Histogram — phân bố dư nợ theo khoản vay, phạm vi 1 PGD. | `render()` |
| `tabs/tab_ke_hoach_cv_khnv.py` | Theo dõi kế hoạch và kết quả công việc nội bộ Phòng KH-NV qua Google Forms. | `render()` |
| `tabs/tab_kehoach.py` | Tab Kế hoạch Chi nhánh vs Thực hiện | `render()` |
| `tabs/tab_kh_gqvl.py` | Tab Kế hoạch GQVL Chi nhánh — nhập KH GQVL theo năm, phân tầng TW/ĐP. | `render()` |
| `tabs/tab_khnv_bao_cao.py` | Tab Báo cáo KHNV — Upload Điện báo & So sánh kỳ. | `render()` |
| `tabs/tab_khnv_noi_bo.py` | Tab Quản lý nội bộ Phòng KH-NV — 6 sub-tab theo luồng 5 bước: | `render()` |
| `tabs/tab_khtd.py` | Tab Kế hoạch Tín dụng — Phòng KH-NV quản lý, phân cấp đến Xã. | `render()` |
| `tabs/tab_khtd_giao_dc.py` | Tab Giao KHTD & Điều chỉnh KHTD — lũy kế đợt, Google Sheet, kv_store, duyệt tập  | `render()` |
| `tabs/tab_khtd_mau07.py` | Tab Mẫu 07 — Giao/Điều chỉnh Kế hoạch Tín dụng theo Ấp/Thôn. | `tinh_du_no_ap_baseline()`, `render()` |
| `tabs/tab_khtd_nhap.py` | Nhập dữ liệu cho tab Kế hoạch Tín dụng (Chi nhánh + theo Xã/PGD). | `render_nhap_cn()`, `render_nhap_pgd()` |
| `tabs/tab_khtd_pgd.py` | Tab Kế hoạch Tín dụng cấp PGD — Hỗ trợ địa bàn. | `render()` |
| `tabs/tab_khtd_xuat.py` | Xuất báo cáo / export cho tab Kế hoạch Tín dụng. | `xuat_khtd_theo_xa()`, `xuat_to_trinh_bgd_word()`, `render_xuat_baocao()` |
| `tabs/tab_kiem_soat.py` | Tab Kiểm soát Chi nhánh — chọn nhóm/báo cáo từ registry, gọi render_fn tương ứng | `render_tab()` |
| `tabs/tab_kiem_soat_du_lieu_pgd.py` | Kiểm soát nội bộ PGD — xem dữ liệu 3 tháng KHĐ và NQH cho 1 PGD. | `render()` |
| `tabs/tab_kiem_soat_noi_bo_pgd.py` | Kiểm soát Nội bộ PGD — Checklist 7 điểm tự kiểm tra trước khi báo cáo CN. | `render()` |
| `tabs/tab_ktnb.py` | Tab Kiểm toán Nội bộ (KTNB) — wrapper cho render_ktnb() từ ktnb_service. | `render()` |
| `tabs/tab_ndt_dp.py` | Tab Mã Nhà đầu tư Địa phương — Phiên bản PGD (chỉ xem). | `render()` |
| `tabs/tab_nhiem_vu.py` | Tab Quản lý Nhiệm vụ (Tháng / Quý / Năm) | `render()` |
| `tabs/tab_no_khoanh.py` | Phân tích Nợ khoanh — danh mục khoản vay đang trong giai đoạn khoanh nợ QĐ 62. | `render()` |
| `tabs/tab_nq11.py` | Tab NQ11. | `render()` |
| `tabs/tab_pgd_cards.py` | Tab Toàn cảnh 22 PGD — giám sát đa chiều. | `render()` |
| `tabs/tab_phan_ky_nxh.py` | Quản lý danh sách nợ đến hạn phân kỳ nhà ở xã hội (SKKU/NSVC/GQVL). | `render()` |
| `tabs/tab_phan_loai_kh.py` | Tab Phan loai Khach hang theo muc do rui ro (A/B/C/D). | `render()` |
| `tabs/tab_phan_tich_nqh_pgd.py` | Phân tích Nợ Quá Hạn — PGD view. | `render()` |
| `tabs/tab_phan_tich_pgd.py` | Phân tích PGD — Dự phóng dòng tiền + Heatmap đáo hạn + Histogram dư nợ + Donut c | `render()` |
| `tabs/tab_phoi_hop_pgd.py` | Tab Công tác phối hợp với PGD — Ghi nhận và theo dõi các công việc CN giao / hỗ  | `render()` |
| `tabs/tab_qd62.py` | Theo dõi nợ rủi ro QĐ62/QĐ-HĐQT NHCSXH — 2 luồng PGD (nhập) và Chi nhánh (kiểm s | `render()` |
| `tabs/tab_qlnk_dashboard.py` | Dashboard Tổng hợp Quản lý Nợ khoanh. | `render()` |
| `tabs/tab_quan_ly_bc.py` | Tab cha Quản lý Báo cáo định kỳ — wrapper điều hướng 3 sub-module. | `render()` |
| `tabs/tab_quan_ly_cv.py` | Wrapper: Dashboard Công việc — Quản lý Tiến độ & Nhiệm vụ. | `render()` |
| `tabs/tab_quan_ly_dgd.py` | Tab quản lý Điểm Giao Dịch (dgd_map) — Phân hệ ws_management. | `render()` |
| `tabs/tab_quan_ly_ndt_dp.py` | Quản lý Mã Nhà đầu tư Địa phương — dành cho Admin/Manager CN. | `render()` |
| `tabs/tab_security.py` | Tab Quản lý Bảo mật — IP Whitelist, 2FA, Session Management | `render()` |
| `tabs/tab_so_sanh_suc_khoe_pgd.py` | So sánh tăng trưởng & sức khỏe tín dụng giữa 22 PGD — stacked bar, scatter, bar  | `render()` |
| `tabs/tab_stress_test.py` | Stress test danh mục tín dụng — mô phỏng kịch bản rủi ro. | `render()` |
| `tabs/tab_telegram_admin.py` | Quản trị Telegram Bot — cấu hình, bật/tắt, lịch gửi, thao tác thủ công. | `render()` |
| `tabs/tab_theo_doi_khao_sat.py` | Theo dõi tiến độ PGD điền khảo sát HN/HCN/HTN — đọc từ Google Sheets. | `render()` |
| `tabs/tab_thong_bao_ket_luan.py` | Thông báo Kết luận giao ban (NĐ30) — xuất Word/PDF tự động. | `render()` |
| `tabs/tab_tien_do.py` | Tab Tiến độ — Theo dõi tiến độ thực hiện chỉ tiêu tín dụng theo PGD/Xã. | `render()`, `render_tong_quan_only()` |
| `tabs/tab_tien_do_nop_archive.py` | UI lưu trữ báo cáo cho tab Tiến độ nộp báo cáo. | `render_archive()` |
| `tabs/tab_tien_do_nop_list.py` | UI danh sách nộp và export cho tab Tiến độ nộp báo cáo. | `render_submission_list()` |
| `tabs/tab_tien_do_nop_manual.py` | UI đánh dấu thủ công cho tab Tiến độ nộp báo cáo. | `render_manual_override()` |
| `tabs/tab_tien_do_nop_settings.py` | UI cài đặt thời hạn cho tab Tiến độ nộp báo cáo. | `render_settings()` |
| `tabs/tab_tong_hop_cv.py` | Dashboard tổng hợp — kết hợp Tiến độ Công việc + Nhiệm vụ định kỳ. | `render()` |
| `tabs/tab_tongquan.py` | Tab Tổng quan. | `render()` |
| `tabs/tab_tracuu.py` | Tab Tra cứu hồ sơ — nâng cao. | `render()` |
| `tabs/tab_tracuu_v2.py` | Tab Tra cứu hồ sơ — Phiên bản 2.0. | `render()` |
| `tabs/tab_trang_chu_pgd.py` | Trang chủ dashboard PGD — KPI cards, truy cập nhanh, cảnh báo, nhiệm vụ. | `render()` |
| `tabs/tab_trang_thai_nguon.py` | tab_trang_thai_nguon.py | `render()` |
| `tabs/tab_upload_pgd.py` | Tab Upload Dữ liệu — Hỗ trợ địa bàn (PGD tự upload file của mình). | `render()` |
| `tabs/tab_uy_thac.py` | Tab Ủy thác — Theo dõi Hội đoàn thể và các mẫu biểu kiểm tra. | `render()` |
| `tabs/tab_xay_dung_khtd.py` | Xây dựng Kế hoạch Tín dụng tương lai — 3 loại: 1 năm / 3 năm / 5 năm (2026–2030) | `render()` |
| `tabs/tab_xu_huong_pgd.py` | Tab Phân tích Xu hướng — Phân hệ PGD. | `render()`, `render_tab()` |
| `tabs/tab_xu_ly_rui_ro.py` | Tab Xử lý Rủi ro (XLRR) — CN: 6 sub-tabs, PGD: 4 sub-tabs. | `render()` |
| `tabs/tab_baocao/` | Module tab_baocao - Báo cáo tín dụng từ 4 nguồn dữ liệu: HSTD, NQ11, GQVL, CDTOT | `render()` |
| `tabs/tab_so_sanh_ky/` | Package So sánh kỳ — tái cấu trúc khoa học từ tab_so_sanh_ky.py + tab_so_sanh_2_ | `render()` |
| `tabs/tab_theo_doi_nhap/` | Theo dõi tiến trình nhập liệu của PGD trên nhiều Google Sheet phân cấp. | `render()` |
| `tabs/tab_upload_khnv/` | Tab Upload KH-NV — Phòng Kế hoạch Nghiệp vụ. | `render()` |

---

## Scripts

| File | Mô tả |
|---|---|
| `scripts/backup_daily.py` | backup_daily.py — Sao lưu tự động hàng ngày. |
| `scripts/check_conventions.py` | scripts/check_conventions.py |
| `scripts/check_hardcode_cols.py` | Check hardcoded column names in staged/changed Python files. |
| `scripts/daily_report.py` | daily_report.py — Tạo báo cáo Excel tóm tắt định kỳ hằng ngày. |
| `scripts/daily_word_report.py` | Báo cáo Word định kỳ — Tổng quan + NQH + KHTD. |
| `scripts/gen_code_index.py` | scripts/gen_code_index.py |
| `scripts/html_to_pdf.py` | Chuyển file HTML sang PDF. |
| `scripts/html_to_pdf_playwright.py` | Chuyển HTML sang PDF dùng Playwright + Chrome. |
| `scripts/kiem_tra_khtd_th.py` | Script kiểm tra so sánh số liệu Thực hiện (TH) KHTD giữa: |
| `scripts/nhac_deadline.py` | nhac_deadline.py — Nhắc các PGD chưa nộp báo cáo + chưa hoàn thành nhập liệu qua |
| `scripts/perf_profiler.py` | Performance profiler cho các tab module của VBSP-SCM. |
| `scripts/seed_snapshot_mock.py` | Sinh dữ liệu ảo cho 4 loại snapshot: HSTD, NQ11, GQVL, CDTOTKVV. |
| `scripts/setup_hooks.py` | Install/update Git hooks for VBSP-SCM project. |
| `scripts/telegram_polling.py` | telegram_polling.py — Bot 2 chiều: nhận lệnh từ Telegram, trả kết quả. |
| `scripts/telegram_scheduler.py` | Chạy Telegram rule engine; được Windows Task Scheduler gọi mỗi 5 phút. |
| `scripts/validate_data.py` | scripts/validate_data.py |
| `scripts/validate_dependency_lock.py` | Validate that direct requirements and the complete lockfile stay in sync. |
