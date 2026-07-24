# CODE_INDEX — Tra nhanh file cần sửa

> Dành cho agent. Chỉ map chức năng → file → hàm. Không thay AGENTS.md.

---

## Core (luôn cần đọc trước)

| Chức năng | File | Hàm / Export chính |
|---|---|---|
| Entry point, routing | `app.py` | `main()` |
| Phân quyền, login | `auth.py` | `normalize_role()`, `la_phan_he_cn()`, `la_phan_he_pgd()` |
| Hằng số toàn hệ thống | `config.py` | `COT_*`, `DS_PGD`, `MA_PGD_MAP`, `PGD_XA_MAP` |
| DB: kv_store, audit, users | `db.py` | `ghi_kv()`, `doc_kv()`, `doc_kv_prefix()`, `ghi_audit()` |
| Format, Excel, Word helpers | `utils.py` | `fmt_ty()`, `fmt()`, `fmt_so()`, `xuat_excel()`, `auto_fill_document()` |
| Snapshot lịch sử | `snapshot_service.py` | `luu_snapshot()`, `doc_snapshot()`, `compare_snapshot_2_ky()` |

---

## Workspaces (giao diện chính theo role)

| Role | File | Hàm |
|---|---|---|
| BGĐ (chỉ đọc) | `workspaces/ws_executive.py` | `render()` |
| Phòng KH-NV (toàn CN) | `workspaces/ws_management.py` | `render()`, `_build_all_items()` |
| PGD (địa bàn) | `workspaces/ws_operation.py` | `render()` |

---

## Data Layer (đọc dữ liệu)

| Dữ liệu | File | Hàm chính |
|---|---|---|
| HSTD (toàn CN) | `data/hstd.py` | `doc_file()`, `doc_baseline()` |
| HSTD (PGD) | `data/pgd.py` | `pgd_slug()`, `duong_dan_pgd()`, `doc_hstd_pgd()` |
| NQ11 | `data/hstd.py` | `doc_file_nq11()`, `luu_so_khe_uoc_nq11()` |
| GQVL | `data/hstd.py` | `doc_file_gqvl()` |
| CĐ Tổ TK&VV | `data/cdtotkvv.py` | `doc_cdtotkvv()`, `doi_chieu_cdtotkvv_hstd()` |
| Điện báo | `data/hstd.py` | `doc_dienbao()`, `doc_dienbao_matrix()` |
| Excel → Parquet | `data/core.py` | `excel_to_parquet()`, `ts_file()` |
| KHTD data | `data/khtd.py` | `doc_khtd()`, `luu_khtd()`, `doc_kehoach()`, `lay_ap_tu_dgd_list()` |
| Đến hạn | `data/den_han.py` | `tinh_den_han_df()`, `loc_den_han_trong()` |
| Giao ban | `data/giao_ban.py` | `tinh_so_lieu_van_xuoi()` |

---

## Services (business logic)

### Upload & Merge

| Chức năng | File | Hàm chính |
|---|---|---|
| Upload PGD | `services/upload_service.py` | `luu_pgd_file()`, `luu_file_he_thong()` |
| Merge toàn CN | `services/upload_service.py` dòng 288-480 | `merge_du_lieu_toan_cn()` |

### KHTD

| Chức năng | File | Hàm chính |
|---|---|---|
| Giao & Điều chỉnh KHTD | `services/khtd_service.py` | `luu_dot()`, `tong_hop()`, `duyet()`, `tao_dot_giao_dau_nam()` |
| Nhập KHTD từ Excel | `services/khtd_nhap_service.py` | `doc_excel_khtd_cn_upload()`, `tinh_th_gqvl_phan_tang()` |
| Xuất KHTD báo cáo | `services/khtd_xuat_service.py` | `xuat_excel_1pgd()`, `xuat_word_bao_cao_pgd()` |
| Mẫu 07 (UBND xã) | `services/khtd_mau07_service.py` | `tinh_du_no_ap_baseline()` |

### Kiểm soát & Kiểm tra

| Chức năng | File | Hàm chính |
|---|---|---|
| Kiểm soát CN | `services/kiem_soat_service.py` | `render_3m_khd()`, `render_nqh()`, `render_to_sai_so_tv()` |
| Kiểm tra nội bộ | `services/ktnb_service.py` | `render_ktnb()`, `xuat_word_bien_ban_ktnb()` |

### Rủi ro

| Chức năng | File | Hàm chính |
|---|---|---|
| Xử lý rủi ro | `services/xlrr_service.py` | XLRR CRUD, tổng hợp PGD→CN |
| Nợ khoanh | `services/no_khoanh_service.py` | Nợ khoanh CRUD |
| Word XLN | `services/word_xln_service.py` | Xuất biểu XLN |

### KH-NV nội bộ

| Chức năng | File | Hàm chính |
|---|---|---|
| Báo cáo KH-NV tháng | `services/khnv_bao_cao_service.py` | `tong_hop_so_lieu_thang()`, `xuat_word_bao_cao_khnv()` |
| Quản lý nội bộ KH-NV | `services/khnv_noi_bo_service.py` | `doc_ds()`, `ghi_ds()` |
| Lịch công tác tuần | `services/khnv_lich_tuan_service.py` | `xuat_lich_lam_viec_tuan()` |
| Kế hoạch CV (GSheet) | `services/ke_hoach_cv_khnv_service.py` | `doc_ke_hoach()`, `tinh_tong_hop()` |

### Báo cáo / PDF / Word

| Chức năng | File | Hàm chính |
|---|---|---|
| Xuất PDF | `components/export_pdf.py` | `xuat_pdf_co_chart()`, `download_pdf_button()` |
| Xuất PDF nâng cao | `pdf_service.py` | `xuat_pdf()`, `xuat_pdf_pivot()` |
| Template Word | `services/template_service.py` | `nut_tai_word_va_pdf()` |
| Báo cáo Excel | `services/report_service.py` | `xuat_bao_cao()`, `xuat_sheet_don()` |

### Khác

| Chức năng | File | Hàm chính |
|---|---|---|
| Ủy thác | `services/uy_thac_service.py` | Ủy thác CRUD |
| HHI | `services/hhi_service.py` | HHI calculations |
| Telegram | `services/telegram_service.py` | Bot notifications |
| Snapshot service | `snapshot_service.py` | `luu_snapshot()`, `doc_snapshot()` |
| Cảnh báo | `alert_center.py` | `render_alert_sidebar()` |
| Backup | `backup_service.py` | `chay_backup()`, `phuc_hoi_backup()` |
| Security | `security.py` | `check_session_timeout()`, `setup_2fa()` |

---

## Tabs (UI — entrypoint thường có `render(...)`; submodule có thể dùng `render_*()` hoặc được gọi qua module init/workspace)

### Tổng quan & Dashboard

| Tab | File |
|---|---|
| Tổng quan CN | `tabs/tab_tongquan.py` |
| PGD cards | `tabs/tab_pgd_cards.py` |
| Dashboard PGD | `tabs/tab_dashboard_suc_khoe_pgd.py` |

### Báo cáo

| Tab | File |
|---|---|
| Báo cáo (main) | `tabs/tab_baocao/__init__.py` |
| Tổng hợp HSTD | `tabs/tab_baocao/reports/tong_hop_hstd.py` |
| Tổng hợp HSTD v2 | `tabs/tab_baocao/reports/tong_hop_hstd_v2.py` |
| NQ11 | `tabs/tab_baocao/reports/nq11.py` |
| Nợ rủi ro | `tabs/tab_baocao/reports/no_rui_ro.py` |
| GQVL | `tabs/tab_baocao/reports/gqvl.py` |
| CĐ Tổ TK&VV | `tabs/tab_baocao/reports/cdtotkvv.py` |

### So sánh kỳ

| Tab | File |
|---|---|
| So sánh 2 kỳ | `tabs/tab_so_sanh_ky/render_2_ky.py` |
| So sánh nhiều kỳ | `tabs/tab_so_sanh_ky/render_nhieu_ky.py` |
| So sánh mốc năm | `tabs/tab_so_sanh_ky/render_moc_nam.py` |

### Upload

| Tab | File |
|---|---|
| Upload KH-NV (main) | `tabs/tab_upload_khnv/__init__.py` |
| Upload từng PGD | `tabs/tab_upload_khnv/_upload_don_vi.py` |
| Upload toàn CN | `tabs/tab_upload_khnv/_upload_toan_cn.py` |
| Merge panel | `tabs/tab_upload_khnv/_merge_panel.py` |
| Upload PGD | `tabs/tab_upload_pgd.py` |

### KHTD

| Tab | File |
|---|---|
| KHTD overview | `tabs/tab_khtd.py` |
| Giao & Điều chỉnh | `tabs/tab_khtd_giao_dc.py` |
| Nhập KHTD | `tabs/tab_khtd_nhap.py` |
| Xuất KHTD | `tabs/tab_khtd_xuat.py` |
| Mẫu 07 | `tabs/tab_khtd_mau07.py` |

### Danh mục & Tra cứu

| Tab | File |
|---|---|
| Danh sách món vay | `tabs/tab_danhsach.py` |
| Tra cứu (v2) | `tabs/tab_tracuu_v2.py` |
| Quản lý Điểm GD | `tabs/tab_quan_ly_dgd.py` |

### Kiểm soát & Rủi ro

| Tab | File |
|---|---|
| Kiểm soát CN | `tabs/tab_kiem_soat.py` |
| Kiểm tra nội bộ | `tabs/tab_ktnb.py` |
| Xử lý rủi ro | `tabs/tab_xu_ly_rui_ro.py` |
| Nợ khoanh | `tabs/tab_no_khoanh.py` |
| Cảnh báo NQH | `tabs/tab_canh_bao_nqh.py` |
| Cảnh báo sớm | `tabs/tab_canh_bao_som.py` |
| QĐ 62 | `tabs/tab_qd62.py` |

### Phân tích PGD

| Tab | File |
|---|---|
| Phân tích PGD | `tabs/tab_phan_tich_pgd.py` |
| Phân tích NQH PGD | `tabs/tab_phan_tich_nqh_pgd.py` |

### Giao ban & Ban Đại Diện

| Tab | File |
|---|---|
| Ban Đại Diện | `tabs/tab_ban_dai_dien.py` |
| Biên bản giao ban | `tabs/tab_bien_ban_giao_ban.py` |
| Thông báo kết luận | `tabs/tab_thong_bao_ket_luan.py` |

### KH-NV Nội bộ

| Tab | File |
|---|---|
| Quản lý nội bộ | `tabs/tab_khnv_noi_bo.py` |
| Báo cáo tháng | `tabs/tab_khnv_bao_cao.py` |
| Kế hoạch CV | `tabs/tab_ke_hoach_cv_khnv.py` |

### Tiến độ & Định kỳ

| Tab | File |
|---|---|
| Tiến độ nộp BC (GSheet) | `tabs/tab_tien_do_nop.py` |
| Tiến độ báo cáo | `tabs/tab_tien_do.py` |

### Khác

| Tab | File |
|---|---|
| HHI | `tabs/tab_hhi.py` |
| Đến hạn | `tabs/tab_den_han.py` |
| Ủy thác | `tabs/tab_uy_thac.py` |
| CĐ Tổ TK&VV | `tabs/tab_cdtotkvv.py` |
| GQVL | `tabs/tab_gqvl.py` |
| NQ11 | `tabs/tab_nq11.py` |
| Kế hoạch Điện báo | `tabs/tab_kehoach.py` |
| Security | `tabs/tab_security.py` |
| Audit log | `tabs/tab_audit_log.py` |
| Telegram admin | `tabs/tab_telegram_admin.py` |
| Phân kỳ NXH | `tabs/tab_phan_ky_nxh.py` |

---

## Components (widget tái sử dụng)

| Component | File | Hàm |
|---|---|---|
| Metric cards | `components/delta_card.py` | `delta_card()`, `kpi_row()` |
| PDF export | `components/export_pdf.py` | `xuat_pdf_co_chart()`, `download_pdf_button()` |
| Filter bar | `components/filter_bar.py` | `filter_bar()`, `apply_filters()` |
| Loan drawer | `components/loan_drawer.py` | `loan_detail_drawer()` |
| Movers analysis | `components/movers.py` | `movers_analysis()` |

---

## Scripts (tools)

| Script | Mục đích |
|---|---|
| `scripts/daily_report.py` | Báo cáo hàng ngày |
| `scripts/check_conventions.py` | Kiểm tra convention |
| `scripts/check_hardcode_cols.py` | Phát hiện tên cột hardcode |
| `scripts/backup_daily.py` | Backup định kỳ |
| `scripts/telegram_scheduler.py` | Lên lịch Telegram |
| `scripts/nhac_deadline.py` | Nhắc deadline |
