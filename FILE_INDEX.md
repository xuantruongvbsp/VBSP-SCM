# FILE INDEX — VBSP-SCM
> Bản đồ hàm/section cho các file lớn (>1000 dòng).
> Dùng khi cần định vị nhanh chỗ cần sửa trước khi đưa vào Cursor/Windsurf.
> Cập nhật mỗi khi thêm hàm lớn mới.

---

## Cách dùng

1. Tìm file cần sửa bên dưới
2. Ctrl+F tên hàm → lấy số dòng
3. Paste vào prompt Cursor: `@file.py dòng NNN-MMM`

---

## `services/upload_service.py` — 769 dòng

```
dòng   60  : Hằng số kiểm tra file (EXTS_CHOPHEP, MAX_SIZE...)
dòng   81  : class KetQuaUpload         ← kiểu trả về chuẩn cho mọi upload
dòng   98  : danh_gia_chat_luong_file_upload()
dòng  130  : kiem_tra_file()            ← validate ext + size
dòng  153  : kiem_tra_file_he_thong()   ← validate tên file hệ thống
dòng  174  : _ghi_va_xoa_cache()        ← ghi bytes + xóa cache parquet
dòng  193  : luu_file_he_thong()        ← upload file CN (HSTD_CN, NQ11_CN...)
dòng  218  : luu_dienbao()              ← upload Điện báo
dòng  295  : merge_du_lieu_toan_cn()    ← ⭐ gộp 22 đơn vị → parquet
              ~dòng 440: normalize dtype sau concat
              ~dòng 472: ép kiểu thủ công (_cols_so_cn)
              ~dòng 484: string cleanup (_str_cols)  ← hay lỗi dtype mixed
              ~dòng 502: ghi parquet + rollback .bak
dòng  585  : luu_pgd_file()             ← upload file riêng PGD
dòng  698  : lay_meta_merge()           ← đọc metadata merge gần nhất
dòng  720  : format_caption_merge()     ← chuỗi caption "Cập nhật lúc..."
dòng  745  : lay_meta_chat_luong()
dòng  754  : luu_cdtotkvv()             ← upload chấm điểm Tổ TK&VV
```

---

## `workspaces/ws_management.py` — 1397 dòng

```
dòng   66  : _render_canh_bao()         ← cảnh báo KHĐ 3 tháng
dòng  199  : _render_canh_bao_no()      ← cảnh báo NQH
dòng  271  : _hien_thi_khd_tab()        ← tab KHĐ (kế hoạch điều hành)
dòng  362  : _tim_cot()                 ← helper tìm tên cột linh hoạt
dòng  379  : _hien_thi_nqh_tab()        ← tab NQH chi tiết
dòng  592  : _render_dgd_to_tkvv()      ← tab Điểm GD & Tổ TK&VV
dòng  607  : _render_ndt_dp()           ← tab NĐT ĐP
dòng  868  : _render_quan_ly_template() ← quản lý template Word/Excel
dòng 1112  : _build_all_items()         ← ⭐ danh sách menu sidebar (thêm/bớt tab đây)
dòng 1190  : render_sidebar_menu()      ← render sidebar navigation
dòng 1325  : render()                   ← entry point workspace
```

**Khi thêm tab mới vào menu:** chỉ sửa `_build_all_items()` dòng ~1112.

---

## `workspaces/ws_operation.py` — 1776 dòng

```
dòng   49  : _kpi_pgd_list()            ← tính 4 KPI DeltaCard trang chủ PGD
dòng  157  : _render_trang_chu()        ← trang chủ PGD (KPI + chart tổng quan)
dòng  289  : _render_don_doc()          ← bảng đôn đốc thu nợ
dòng  418  : _render_canh_bao_som_pgd() ← cảnh báo sớm PGD
dòng  425  : _banner_canh_bao_khd()     ← banner KHĐ sắp đến hạn
dòng  445  : _render_doc_hub()          ← Document Hub (trung tâm văn bản tự động)
dòng  569  : _init_gb2_session_for_doc_hub()
dòng  600  : _render_thong_bao_ket_luan()
dòng  826  : _render_bien_ban_giao_ban()← biên bản giao ban
dòng  920  : _render_bao_cao_giao_ban() ← báo cáo giao ban
dòng 1210  : render()                   ← entry point workspace
              ~dòng 1210-1250: load dữ liệu PGD + xác định mode
              ~dòng 1250+: render các tab PGD
```

---

## `tabs/tab_no_khoanh.py` — 2965 dòng
> File lớn nhất. Gồm 2 phần chính: PDF helpers + UI render.

```
dòng   65  : Helpers tính toán
              _loc_khoanh(), _bang_theo_nhom(), _chart_nhom(), _heatmap_dao_han()

dòng  191  : PDF helpers (Mẫu QLNK theo CV 368)
              _dang_ky_font_qlnk()       dòng 191
              _style_*()                 dòng 263–320  ← styles chung
              _ve_header_pdf()           dòng 322
              _ve_footer_pdf()           dòng 385

dòng  426  : Xuất PDF từng mẫu
              _xuat_pdf_mau_kh()         dòng  426  ← Mẫu KH vay vốn
              _xuat_pdf_mau_01qlnk()     dòng  522  ← Mẫu 01/QLNK (thông báo)
              _xuat_pdf_mau_02qlnk()     dòng  666  ← Mẫu 02/QLNK (cam kết)
              _xuat_pdf_mau_03qlnk()     dòng  814  ← Mẫu 03/QLNK (biên bản)
              _xuat_pdf_mau_04qlnk()     dòng  975  ← Mẫu 04/QLNK
              _xuat_pdf_qlnk_06()        dòng 1065  ← Mẫu 06/QLNK
              _xuat_pdf_m10()            dòng 1171  ← Mẫu 10
              _xuat_pdf_ke_hoach_kt()    dòng 1264  ← Kế hoạch kiểm tra (NĐ 30)

dòng 1427  : ⭐ render()                ← entry point UI
              ~dòng 1430–1460: load dữ liệu, xác định PGD/mode
              ~dòng 1460–1560: st.tabs() — 8 tab con
              d0 "Tổng quan"             → tab_qlnk_dashboard.render()
              d1 "Danh sách nợ khoanh"
              d2 "Theo tổ"
              d3 "Sắp hết hạn"
              d4 "Báo cáo" (M08/M09/M10/Tiến độ)
              d_kt "Kiểm tra CV 368"     → _render_cv368_kt()
```

---

## `tabs/tab_no_rui_ro.py` — 2411 dòng

```
dòng   54  : Helpers định dạng
              _pgd_plain(), _pgd_line(), _style_doc_xln()
              _bo_border_cell(), _set_cell(), _set_row_font(), _num()

dòng  133  : Tạo file Word XLN
              _add_header_xln()          dòng  133
              _tao_word_01xln()          dòng  167  ← Mẫu 01/XLN
              _tao_word_02xln()          dòng  253  ← Mẫu 02/XLN
              _tao_word_xln_bao_cao()    dòng  450  ← Báo cáo tổng hợp XLN
              _tao_word_13xln()          dòng  635
              _tao_word_14xln()          dòng  657
              _tao_word_04xln()          dòng  679
              _tao_word_05xln()          dòng  892
              _tao_word_to_trinh_pgd()   dòng 1051  ← Tờ trình PGD
              _tao_word_to_trinh_cn()    dòng 1236  ← Tờ trình CN

dòng 1402  : Helpers lọc dữ liệu
              _lay_pgd_tu_user(), _loc_df_theo_pgd(), _tao_kv_key()

dòng 1425  : _hien_thi_chi_tiet()       ← hiển thị chi tiết 1 hồ sơ
dòng 1440  : _render_04_05_tt()         ← xuất 04/05 XLN + Tờ trình
dòng 1495  : _render_luong_nhap_ho_so() ← Bước 1→5 nhập hồ sơ XLN

dòng 1796  : _render_workspace_cn()     ← view cấp CN (admin/manager)
dòng 2095  : render()                   ← entry point
```

---

## `workspaces/ws_executive.py` — 1678 dòng

```
dòng   48  : Hằng số ngưỡng NQH
dòng   61  : Helpers format: _fmt(), _mau_nqh(), _gauge_nqh()
dòng  153  : _render_gauge_du_no()      ← gauge tổng dư nợ
dòng  160  : _render_metric_cards()     ← 4 KPI cards lãnh đạo
dòng  201  : _kpi_tang_truong()         ← chart tăng trưởng
dòng  248  : _heatmap_rui_ro_pgd()      ← heatmap rủi ro 22 PGD
dòng  358  : _the_suc_khoe()            ← thẻ sức khoẻ tín dụng
dòng  400  : _render_heatmap_pgd()      ← render section heatmap
dòng  673  : _render_bieu_do_tron()     ← biểu đồ tròn cơ cấu
dòng  711  : _tien_do_ke_hoach()        ← tiến độ KH/TH
dòng  761  : _canh_bao_xa_nqh()        ← cảnh báo xã NQH cao
dòng  819  : _hhi_giam_sat()           ← chỉ số HHI tập trung vốn
dòng  912  : _migration_matrix_section()← ma trận migration rủi ro
dòng 1010  : _canh_bao_migration()
dòng 1057  : _radar_compare_pgd()       ← radar so sánh PGD
dòng 1174  : _waterfall_du_no()         ← waterfall biến động dư nợ
dòng 1243  : _ranking_pgd()             ← xếp hạng PGD
dòng 1334  : _render_suc_khoe_tong_quan()
dòng 1344  : _render_tien_do_va_kh()
dòng 1378  : _render_so_sanh_xep_hang_pgd()
dòng 1390  : _render_nqh_xa_canh_bao()
dòng 1397  : _render_migration_section()
dòng 1405  : _render_pdf_section()
dòng 1473  : _build_exec_items()        ← ⭐ danh sách menu executive
dòng 1496  : render_sidebar_menu()
dòng 1569  : render()                   ← entry point
```

---

## Các file trung bình thường xuyên sửa

| File | Dòng | Hàm chính |
|---|---|---|
| `app.py` | ~1 | Entry point, session init, CSS global, load HSTD |
| `config.py` | ~853 | DS_PGD, PGD_XA_MAP, COT_*, CHUONG_TRINH_KHTD |
| `db.py` | ~1067 | get_conn, doc_kv, ghi_kv, ghi_audit, migration |
| `auth.py` | ~1066 | login, RBAC helpers, la_phan_he_cn/pgd, normalize_role |
| `utils.py` | ~600 | fmt, fmt_ty, fmt_so, fmt_pct, auto_fill_document |
| `data/core.py` | ~400 | ts_file, excel_to_parquet, load HSTD/NQ11/GQVL |
| `services/report_service.py` | ~500 | xuat_bao_cao, xuat_sheet_don |
