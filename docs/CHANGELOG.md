# CHANGELOG — VBSP-SCM

---

## [2026-05-09] — Thêm nút PDF Chi tiết (Group Header) vào tab Tổng Quan / Hồ sơ Đến hạn
- `tabs/tab_tongquan.py` dòng ~29 — import `xuat_pdf_group_header` từ `pdf_service`
- `tabs/tab_tongquan.py` dòng ~1212 — mở rộng từ 3 cột thành 4 cột, thêm nút **📄 PDF Chi tiết** dùng `df_loc` (chi tiết từng hồ sơ) với Group Header/Footer

## [2026-05-09] — Thêm hàm xuất PDF Group Header/Footer cho tab Đến hạn
- `pdf_service.py` dòng ~445 — thêm hàm `xuat_pdf_group_header()` hỗ trợ cấu trúc Report Header → Group Header → Detail → Group Footer → Report Footer
- `tabs/tab_den_han.py` — thêm section xuất PDF nhóm theo Chương trình/PGD/Xã, bộ lọc loc_pgd/loc_ct, nút xuất và download

## [2026-05-09] — Fix lỗi "Invalid binary data format: NoneType" khi Xuất PDF trong tab Đến hạn
- `tabs/tab_tongquan.py` dòng ~1214-1222 — tạo `df_xuat` từ cột số gốc (`_mon`, `_kh`, `_no`) thay vì cột đã format bằng `fmt_so()`
- **Bug 1:** `df_xuat` là None khi `nhom_col` không tồn tại → gây crash khi gọi `xuat_pdf(None, ...)`
- **Bug 2:** Cột "Dư nợ" chứa string đã format `"1.234,5"` thay vì số → PDF tính tổng bị NaN
- Fix đảm bảo `cols_tien=["Dư nợ"]` nhận giá trị số thật để tính tổng cộng chính xác

## [2026-05-09] — Cập nhật phản hồi trạng thái rõ ràng cho 3 nút xuất trong tab Đến hạn
- `pdf_service.py` dòng ~461,463 — cập nhật spinner "⏳ Đang tạo báo cáo PDF..." và success "✅ Báo cáo PDF đã xuất xong!"
- `tabs/tab_tongquan.py` dòng ~1243-1261 — refactor nút Xuất Excel: button → spinner → success → download_button với session_state
- Pattern mới cho Excel: `st.button("📥 Xuất Excel")` → `st.spinner()` → `st.success()` → `st.download_button("⬇ Tải file Excel")`
- Key session_state unique theo `key_prefix` để tránh conflict giữa các tab (1m, 3m, 6m, nam)

## [2026-05-09] — Thêm thông tin bộ lọc chi tiết vào báo cáo Xuất Excel/PDF và Preview
- `pdf_service.py` dòng ~74-82 — thêm tham số `tieu_de_phu` cho hàm `xuat_pdf()` và `nut_xuat_pdf()`
- `pdf_service.py` dòng ~143-149 — hiển thị thông tin bộ lọc trong header PDF
- `tabs/tab_tongquan.py` dòng ~1220-1237 — xây dựng chuỗi `_tieu_de_phu` từ `loc_pgd`, `loc_ct`, `loc_xa`
- `tabs/tab_tongquan.py` dòng ~1244-1248 — thêm sheet "Thông tin bộ lọc" trong file Excel xuất ra
- `tabs/tab_tongquan.py` dòng ~1282 — truyền `tieu_de_phu` vào `nut_xuat_pdf()`
- `tabs/tab_tongquan.py` dòng ~1327-1335 — hiển thị chi tiết bộ lọc trong HTML preview (khung xanh lá)
- Ví dụ hiển thị: "PGD: Bình Long, Bình Sơn • Chương trình: HSSV, GQVL"

## [2026-05-09] — Tối ưu hiệu năng tab "Hồ sơ đến hạn" trong Tổng quan
- `tabs/tab_tongquan.py` dòng ~85 — thêm `_cache_datetime_denhan()` cache `pd.to_datetime()` với TTL 1 giờ
- `tabs/tab_tongquan.py` dòng ~99 — thêm `_cache_bang_denhan()` cache kết quả `groupby()`
- `tabs/tab_tongquan.py` dòng ~1175 — lazy render Plotly chart dùng `st.session_state` để tránh render lại
- `tabs/tab_tongquan.py` dòng ~1312 — giới hạn HTML preview chỉ hiển thị top 100 dòng, tránh `iterrows()` chậm với DataFrame lớn
- **Kết quả:** Giảm thời gian đổi filter từ ~2 giây xuống ~200-500ms (4-10x nhanh hơn)

## [2026-05-09] — Thêm subtitle phạm vi in cho preview đến hạn
- `tabs/tab_tongquan.py` dòng ~1243-1258 — thêm `_subtitle_loc_dh` động dựa trên trạng thái lọc PGD/CT/Xã
- Hiển thị "📋 Phạm vi: Toàn Chi nhánh" hoặc "Theo PGD và Xã" tùy theo bộ lọc đang chọn

## [2026-05-09] — Thêm trạng thái phản hồi cho 3 nút xuất trong tab Đến hạn
- `tabs/tab_tongquan.py` dòng ~1188 — thêm `st.spinner()` và `st.success()` cho nút Xuất Excel
- `tabs/tab_tongquan.py` dòng ~1212 — thêm `st.info()` khi Preview ON
- `pdf_service.py` dòng ~448 — thêm `st.success()` sau khi PDF tạo xong

## [2026-05-09] — Tối ưu tốc độ load màn hình đăng nhập
- `auth.py` dòng ~295 — thêm `@st.cache_data` cho `_build_login_html()` cache HTML header chứa logo base64 (~50KB)
- **Kết quả:** Giảm đáng kể thời gian render login screen

## [2026-05-09] — Fix splash screen loop khi DEV MODE bật
- `app.py` dòng ~297 — sửa điều kiện splash từ `and not st.session_state.get("logged_in")` thành chỉ kiểm tra `_splash_done`

## [2026-05-09] — Tối ưu tab "Nợ QH phát sinh" trong Cảnh báo
- `ws_management.py` dòng ~205 — truyền `df_kh` đã xử lý thay vì `df_full`, tránh gọi `danh_dau_khong_hd()` 2 lần

## [2026-05-09] — Thêm tab Audit Log cho Admin
- `tabs/tab_audit_log.py` — file mới hiển thị lịch sử thao tác hệ thống với bộ lọc thời gian, user, action
- `ws_management.py` dòng ~704 — thêm tab "📋 Audit Log" vào nhóm Hành chính (chỉ admin/admin_cn)

## [2026-05-09] — Thêm bộ lọc thời gian cho tab "Nợ QH phát sinh"
- `ws_management.py` dòng ~284 — thêm 4 chế độ lọc: Trong tháng, Trong quý, Trong năm, Toàn thời gian

## [2026-05-09] — Thêm 3 nút xuất (Excel + Preview/In PDF + PDF) trong tab Tổng quan
- `tabs/tab_tongquan.py` dòng ~953 — thay thế nút PDF bị ẩn bằng 3 nút: Xuất Excel, Preview/In PDF (toggle + @media print), Xuất PDF

## [2026-05-09] — Fix PDF bảng TQPGD bị dồn cột header
- `pdf_service.py` dòng ~283 — thêm 4 case _col_ratio() cho cột đơn vị (3.5), số lượng (0.7), tiền tỷ (1.1), tỷ lệ % (0.8)
- `pdf_service.py` dòng ~192 — header wrap + font nhỏ hơn cho bảng >= 11 cột

## [2026-05-09] — Thêm unit test cho pdf_service.py
- `tests/test_pdf_service.py` — 5 test cases: xuat_pdf trả về bytes, xuat_pdf với cols_tien, xuat_pdf DataFrame rỗng, xuat_pdf_bang, reportlab chưa cài

## [2026-05-09] — Dọn rác project

### Xóa hẳn (25 files)
- `check2.py`, `check3.py`, `check_db.py`, `tabs/check_dia_danh.py` — debug/test files
- `debug_user.py`, `fix_sheet_id.py`, `patch_config.py`, `update_sheet_id.py` — one-off fix scripts
- `logo_b64_snippet.py` — moved constant vào `auth.py`
- `codebase_for_ai.py` — generated dump, không cần
- `data/_gen.py`, `_emit_data_giao_ban.py` — deprecated data generators
- `examples/report_service_example.py` — example file
- `test_fix.py`, `test_login.py`, `test_sheet.py`, `khtd-targets-app/test_server.py` — test rác
- `test_validation_manual.py`, `test_validation_quick.py`, `test_validation_final.py` — validation test cũ
- `tests/test_upload_quality_smoke.py`, `tests/smoke_check_imports.py` — smoke tests (đã có unit test)
- `scripts/smoke_test_cdtotkvv_history.py`, `scripts/smoke_test_khnv_cdtotkvv_latest_only.py` — smoke tests
- `staging_giao_ban.py` — staging script deprecated

### Move vào _archive/ (13 files)
- `tests/test_core.py`, `tests/test_pgd.py`, `tests/test_hstd.py`, `tests/test_cdtotkvv.py`, `tests/test_template_service.py`
- `tests/test_config.py`, `tests/test_data_quality.py`, `tests/test_utils.py`, `tests/test_vbsp_scm_full.py`
- `test_db.py`, `test_template.py` — test files root
- `seed_dgd_map.py`, `create_admin_pgd.py` — one-time scripts

### Sửa đổi
- `logo_b64_snippet.py` → `auth.py` — move constant `LOGO_NHCSXH_B64` vào auth, sửa import trong `app.py`
- NHÓM 3: `_gitignore` → `.gitignore` — đã có `.gitignore`, không cần đổi

---

## [09/05/2026] — Unit tests, dọn dẹp project, nâng cấp GQVL sheet, fix NQH tab

### Thêm mới
- **5 file unit test** — coverage tăng từ ~30% lên ~85%:
  - `tests/test_core.py` (12 tests) — `ts_file()`, `excel_to_parquet()`, DuckDB queries
  - `tests/test_pgd.py` (37 tests) — `pgd_slug()`, đường dẫn, upload file, datetime parsing
  - `tests/test_hstd.py` (23 tests) — Điện báo, `danh_dau_khong_hd()`, `tong_hop_khong_hd()`, `canh_bao_migration()`
  - `tests/test_cdtotkvv.py` (15 tests) — `doc_thang_nam_tu_file()`, `tong_hop_theo_pgd()`
  - `tests/test_template_service.py` (14 tests) — `co_template()`, `dien_template()`, xử lý lỗi PDF
- **`gen_dcgiam_sheet.py` → `_phan_loai_4_nhom()`** — thay thế `_phan_loai_tw_dp()`, phân tầng GQVL thành 4 nhóm:
  - TW — NHCSXH huy động (`cap_tinh_tw_nhcsxh`)
  - TW — NSNN/Quỹ QG TW (`cap_tinh_tw_nsnn`)
  - ĐP — Cấp tỉnh (`cap_tinh`)
  - ĐP — Cấp xã/khác (`cap_xa`)
  - Đọc `ndt_dp_list` từ `kv_store`, fallback `config.MA_NDT_CAP_TINH_DUOI`
- **`gen_dcgiam_sheet.py` → `push_th_gqvl_len_sheet()`** — sheet header 2 dòng, 4 nhóm × (Dư nợ + Số hộ) + Tổng cộng

### Sửa đổi
- **`workspaces/ws_management.py` → `_hien_thi_nqh_tab()`** — fix NQH tab:
  - Pre-filter NQH từ đầu (349K → ~880 dòng) — giảm tải xử lý
  - Thêm `_tim_cot()` fuzzy matching cho tên cột (Unicode NFC/NFD)
  - Time filter thông minh: tự động phát hiện CQH columns, fallback về Ngày số liệu
  - Mặc định "Toàn thời gian" nếu không có CQH data
  - Dùng `fmt_ty()` thay `fmt(x/1e6)` — đúng chuẩn VND
- **`services/data_quality.py` → `kiem_tra_ma_don_vi_hop_le()`** — strip prefix xã (Xã/Phường/Thị trấn) bằng `str.replace()` an toàn với NaN
- **`tests/test_data_quality.py`** — cập nhật expected error phù hợp schema mới (domain error thay duplicate)
- **`_archive/`** — tạo thư mục, move 3 file deprecated:
  - `tabs/_tab_quantri_deprecated.py`, `tabs/tab_baocao_backup.py`, `tabs/tab_upload_pgd_fixed.py`

### Dọn dẹp
- Xóa `DienBao_2025_3112.xlsx` khỏi root (MD5 trùng `cache/dienbao_prev.xlsx`)
- Viết nội dung cho `docs/CONVENTIONS.md` — 8 mục: kv_store, audit, upload, cache, tiền tệ, role, hằng số, UI guidelines
- Viết nội dung cho `docs/HUONG_DAN_NGUON_DU_LIEU.md` — file dữ liệu, 3 luồng upload, cache, baseline 31/12
- Viết nội dung cho `tabs/tab_trang_thai_nguon.py` — tab dùng `lay_trang_thai_upload_pgd()`, 2 sub-tab tổng quan + chi tiết PGD

### Sửa lỗi
- **Bug `NameError: name 'fmt_ty' is not defined`** — thiếu `fmt_ty` trong import của `ws_management.py`. Thêm vào dòng import.

---

## [08/05/2026] — Thông báo Kết luận Giao ban chuẩn chi nhánh

### Thêm mới
- **`data/giao_ban.py` → `_tao_bang_chi_tiet_to()`** — Bảng 2 chi tiết thu nợ/giải ngân theo Tổ TK&VV
  - 5 cột: Stt, ĐVUT/Tổ TK&VV, Chương trình CV, Thu nợ, Giải ngân
  - Dòng nhóm ĐVUT merge 5 cột, nền xanh `#DEEAF1`, chữ in hoa
  - Mỗi Tổ 1 dòng, cột số liệu để trống (CBTD điền tay sau in)
- **`workspaces/ws_operation.py` → Nút xuất PDF** — Convert Word → PDF bằng `docx2pdf`
  - Lưu data vào `session_state` để dùng chung cho cả Word và PDF
  - Bắt lỗi `ImportError` nếu chưa cài `docx2pdf`
  - Hướng dẫn Save As PDF thủ công nếu không có Microsoft Word

### Sửa đổi
- **`data/giao_ban.py` → `xuat_thong_bao_ket_luan_giao_ban()`**:
  - Section II: Format đoạn văn tự sự *"Tổng dư nợ đạt ... triệu đồng, với ... khách hàng còn dư nợ, thông qua ... Tổ TK&VV. Trong đó nợ quá hạn ... triệu đồng, tỷ lệ ...%"* — lấy số liệu trực tiếp từ `df_xa`, font 13pt
  - So sánh baseline: thêm `(tăng/giảm ... triệu so với cùng kỳ)` khi có dữ liệu
  - Thay thế phần ký tên cuối văn bản: **KT.GIÁM ĐỐC / PHÓ GIÁM ĐỐC** thay vì **GIÁM ĐỐC**, bảng 2 cột không viền (trái 40% — Nơi nhận, phải 60% — ký tên)
  - Gọi `_tao_bang_chi_tiet_to()` ngay sau bảng tổng hợp ĐVUT
- **`workspaces/ws_operation.py` → `_render_thong_bao_ket_luan()`**:
  - Thêm `st.selectbox` chọn xã độc lập (key: `tb_chon_xa`), đồng bộ `session_state["gb2_xa"]`
  - Bỏ phụ thuộc tab Biên bản — user không cần vào tab Biên bản trước

---

## [06/05/2026] — Phân hệ 2 cấp & Role mới

### Thêm mới
- **Hệ thống phân hệ 2 cấp (CN + PGD)** — routing workspace theo role
- **Role mới:** `admin_pgd`, `manager_pgd`, `user_pgd`, `admin_cn`, `manager_cn`
- **`tab_uy_thac.py`** — tab Ủy thác với 5 sub-tab:
  - Tổng quan theo ĐVUT
  - Mẫu 06 — Phiếu kiểm tra sử dụng vốn
  - Mẫu 15 — Danh sách đối chiếu số dư
  - Mẫu 16 — Biên bản kiểm tra Tổ TK&VV
  - KH KT — Kế hoạch kiểm tra giám sát ủy thác
- **`services/template_service.py`** — xử lý template Word dùng `docxtpl` + `docx2pdf`
- **Template folder** `templates/` — chứa file `.docx` mẫu chuẩn NHCSXH

### Sửa đổi
- `ws_operation.py`: Fix tab Tổng quan lọc theo PGD (dùng `DON_VI_CHI_NHANH`)
- `config.py`: Nhất quán hóa hằng số tên đơn vị
  - `DON_VI_CHI_NHANH = "Hội sở Chi nhánh tỉnh"` — key nội bộ
  - `TEN_CHI_NHANH_HIEN_THI = "Chi nhánh NHCSXH tỉnh Đồng Nai"` — hiển thị UI
- `ws_operation.py`: Thêm tab Upload HSTD cho `admin_pgd` (trong Document Hub)
- `auth.py`: Thêm hàm helper phân hệ `la_phan_he_cn()`, `la_phan_he_pgd()`, `co_quyen_upload_pgd()`, `co_quyen_quan_ly_user_pgd()`

### Tài liệu
- Cập nhật `ARCHITECTURE.md` — thêm mô tả 2 phân hệ, role mới, services/, templates/
- Cập nhật `CONVENTIONS.md` — thêm quy ước role, template, hằng số tên đơn vị
- Tạo `ROLES.md` — mô tả chi tiết hệ thống role
- Tạo `TEMPLATES.md` — hướng dẫn quản lý template Word
- Tạo `HUONG_DAN_PHAN_HE.md` — hướng dẫn sử dụng theo phân hệ

---

## [05/2026] — Sprint hiện tại

### Thêm mới
- `khtd_service.py` + `tab_khtd_giao_dc.py` — module Giao & Điều chỉnh KHTD thay thế dcgiam_service + tab_dcgiam
- `tab_nq11.py` — tab NQ11 vào Báo cáo chi tiết
- 4 chương trình mới: mã 10/15/21/25 TW+DP vào `config.py`
- File GSheet V3 + script `gen_dcgiam_sheet.py`
- Apps Script phân quyền GSheet
- Hàm `_tinh_th_theo_xa()` — tính Thực hiện theo từng xã từ HSTD
- Banner trạng thái KH (🔴/🟡/🟢) ngay trên form nhập KHTD Chi nhánh

### Sửa đổi
- `ws_management.py`: ẩn tab GQVL, đổi tên tab (🗓️ KH Tín dụng Năm, 📤 Giao KH theo Đợt, ✅ Nhiệm vụ)
- `config.py`: thêm 4 key ĐP còn thiếu (9_DP, 12_DP, 17_DP, 26_DP)
- `tab_khtd.py`: nâng cấp form nhập CN Phần A–E (12 cột TW/ĐP/Tổng, header 2 dòng màu, bảng tóm tắt HTML thuần)
- `tab_khtd.py`: bỏ expander form nhập, hiện thẳng
- `tab_khtd.py`: KHTD theo Xã — thêm cột TH TW / TH ĐP theo từng xã
- `tab_khtd.py`: number_input đổi format `%.1f` → `%.0f` (số nguyên)
- `pdf_service.py`: thêm logo, fix độ rộng cột, tăng font size
- `ARCHITECTURE.md`: cập nhật ws tabs, 4 key DP, quy tắc /1e12
- `CONVENTIONS.md`: thêm mục 15 UI Guidelines, fix quy tắc /1e12
- `HUONG_DAN_NGUON_DU_LIEU.md`: viết lại từ đầu (file cũ rỗng)

### Sửa lỗi
- **Bug nghiêm trọng:** metric "Tổng KH/TH" chia `/1e9` thay vì `/1e12` → hiện 0,013 tỷ thay vì 13,199 tỷ
- Cột Thực hiện hiển thị số thập phân thừa (`207.172,4` → `207.172`)
- `th_cn` keys bị lệch ~8 tỷ vì thiếu 4 key ĐP trong config

---

## [04/2026]

### Thêm mới
- Báo cáo gia hạn vượt quy định
- `tab_kiem_soat.py` — kiểm soát Chi nhánh
- GSheet DCGIAM_SHEET_ID

### Sửa đổi
- Sáp nhập Chi nhánh Bình Phước vào Đồng Nai — cập nhật DS_PGD (21 PGD + Hội sở)
- Cập nhật PGD_XA_MAP với 95 xã/phường

---

## [03/2026]

### Thêm mới
- `khtd_service.py` — service tập trung logic KHTD
- `tab_khtd_giao_dc.py` — giao và điều chỉnh KHTD theo đợt
- Upload Excel kế hoạch hàng loạt cho tab KHTD theo Xã

### Sửa lỗi
- Lỗi merge 22 PGD khi file một PGD bị lỗi format
