# DELTA — VBSP-SCM
> Cập nhật sau mỗi lần hoàn thành tính năng (Trae tự append)
> Khi file > 200 dòng: gộp phần stable vào STABLE.md, xóa khỏi đây

---

## CẤU TRÚC THƯ MỤC HIỆN TẠI

```
├── app.py, auth.py, config.py, db.py, utils.py
├── snapshot_service.py, alert_center.py, health_check.py
├── pdf_service.py, gen_dcgiam_sheet.py
│
├── data/
│   ├── core.py, hstd.py, pgd.py, khtd.py
│   ├── cdtotkvv.py, den_han.py, dgd_helpers.py, giao_ban.py
│
├── components/
│   ├── delta_card.py, export_pdf.py, filter_bar.py
│   ├── loan_drawer.py, movers.py
│
├── services/
│   ├── upload_service.py, report_service.py, template_service.py
│   ├── ct_discovery.py, excel_service.py, khtd_service.py
│   ├── hhi_service.py, kiem_soat_service.py, period_compare.py
│   ├── du_phong_service.py, data_quality.py, migration_service.py
│
├── tabs/                        # 40+ tabs
│   ├── tab_tongquan.py, tab_tracuu.py, tab_candoi.py
│   ├── tab_khtd.py, tab_khtd_pgd.py, tab_khtd_nhap.py
│   ├── tab_khtd_giao_dc.py, tab_khtd_mau07.py, tab_khtd_xuat.py
│   ├── tab_gqvl.py, tab_nq11.py, tab_cbtd.py
│   ├── tab_baocao.py, tab_nhiem_vu.py, tab_tien_do.py
│   ├── tab_upload_khnv.py, tab_upload_pgd.py
│   ├── tab_ban_dai_dien.py      # 4 sub-tab: KPI, dự báo vốn, họp BĐD, sổ công văn
│   ├── tab_tien_do_nop.py       # Tiến độ nộp PGD từ GSheet
│   ├── tab_checklist_bc.py      # Checklist deadline báo cáo (kv_store)
│   ├── tab_xlrr_tong_hop.py     # XLRR 4 sub-tab
│   ├── tab_trang_thai_nguon.py  # Health check 6 sub-tab (mức B)
│   ├── tab_danhsach.py, tab_tracuu.py, tab_den_han.py
│   ├── tab_no_khoanh.py, tab_no_rui_ro.py, tab_hhi.py
│   ├── tab_so_sanh_ky.py, tab_canh_bao_som.py
│   ├── tab_cdtotkvv.py, tab_cdtotkvv_pgd.py
│   ├── tab_kiem_soat.py, tab_audit_log.py
│   ├── tab_diem_gd_pgd.py, tab_quan_ly_dgd.py
│   ├── tab_uy_thac.py, tab_qd62.py, tab_kh_gqvl.py, tab_kehoach.py
│
├── workspaces/
│   ├── ws_executive.py     # BGĐ — gauge, heatmap
│   ├── ws_management.py    # CN — render_sidebar_menu() + _build_all_items()
│   └── ws_operation.py     # PGD — lọc theo pgd_user
│
├── widgets/
│   ├── data_source_status.py, status_widget.py
│
├── templates/               # Word templates (.doc/.docx)
├── tests/                   # fixtures.py, test_pdf_service.py, test_smoke_snapshot.py
├── _archive/                # Deprecated files — không import
├── khtd-targets-app/        # React app (độc lập)
├── cache/                   # Parquet runtime: hstd.parquet, nq11.parquet, gqvl.parquet
├── pgd_data/                # Upload PGD: pgd_data/{slug}/hstd_latest.xlsx
└── docs/                    # ARCHITECTURE.md, CHANGELOG.md, ROLES.md, ...
```

---

## KIẾN TRÚC WORKSPACE

### ws_management (CN role)
```
Nhóm tab: Tổng quan | Kế hoạch | Tín dụng | Báo cáo | Điều hành | Hệ thống
```

### ws_operation (PGD role)
```
Nhóm tab: Tác nghiệp | Upload | Kế hoạch PGD | Báo cáo PGD
```

### ws_executive (executive role)
```
Dashboard: gauge KPI, heatmap 22 đơn vị
```

### Pattern tab trong workspace
```python
CAC_NHOM = {
    "nghiep_vu": {
        "label": "📋 Nghiệp vụ",
        "tabs": [
            ("🔍 Tra cứu", lambda tab: tab_tracuu.render(tab, **kwargs)),
        ],
    },
}
nhom_chon = st.radio("Chọn nhóm", ds_label, horizontal=True)
tabs_con = st.tabs(ten_tabs)
for i, tab_c in enumerate(tabs_con):
    with tab_c:
        renderers[i](tab_c)
```

---

## KIẾN TRÚC XỬ LÝ DỮ LIỆU

```
Excel gốc (data/*.xlsx)
  → excel_to_parquet()     → cache/*.parquet (PyArrow + zstd)
  → DuckDB read_parquet()  → aggregate lazy scan
  → Streamlit render

Upload flow:
  Phòng KH-NV (tab_upload_khnv):
    → luu_file_he_thong() → merge_du_lieu_toan_cn() → cache/*.parquet
  PGD (tab_upload_pgd):
    → luu_pgd_file() → pgd_data/{slug}/hstd_latest.xlsx
```

---

## THAM CHIẾU NHANH

| Yêu cầu | File |
|---|---|
| Thêm tab PGD | `tabs/tab_*.py` + `ws_operation.py` |
| Thêm tab toàn CN | `tabs/tab_*.py` + `ws_management.py` |
| Sửa merge 22 PGD | `upload_service.py` → `merge_du_lieu_toan_cn()` |
| Thêm chương trình TD | `config.py` → `CHUONG_TRINH_KHTD` |
| Thêm PGD mới | `config.py` → `DS_PGD`, `MA_PGD_MAP`, `PGD_XA_MAP` |
| Sửa format tiền | `utils.py` → `fmt_ty()` |
| Sửa đọc HSTD | `data/hstd.py` hoặc `data/core.py` |
| Xuất PDF | `components/export_pdf.py` |
| Template Word | `services/template_service.py` |
| Filter + Drill-down | `components/filter_bar.py`, `components/loan_drawer.py` |
| Cảnh báo sidebar | `alert_center.py` → `render_alert_sidebar()` |
| Snapshot HSTD | `snapshot_service.py` |
| Giao KHTD | `khtd_service.py` + `tab_khtd_giao_dc.py` |

---

## FILE DEPRECATED

| File | Lý do |
|---|---|
| `_archive/_tab_quantri_deprecated.py` | Tab quản trị cũ |
| `_archive/tab_baocao_backup.py` | Backup trước refactor |
| `_fix_all_buttons.py` | Script fix 1 lần |
| `_fix_template_service.py` | Script fix 1 lần |

---

## CHANGELOG

## [15/05/2026]
- `tabs/tab_tien_do.py`: Thêm nút "📄 Xuất PDF báo cáo tiến độ" (sub-tab Xuất báo cáo) — tạo 1 file PDF 2 phần (Phần 1: Tiến độ theo đầu việc, Phần 2: Báo cáo trễ hạn) dùng Times New Roman + Table grid
- `tabs/tab_tien_do.py`: `_xuat_pdf_bao_cao_tien_do()` — hỗ trợ 2 mẫu theo `cap_theo_doi`: `pgd` (bảng 4 cột: STT/PDG/Trạng thái/Ghi chú) và `xa` (bảng 5 cột: STT/PGD/Xã/Trạng thái/Ghi chú) với xen kẽ dòng, grid xám
- `tabs/tab_tien_do.py`: Phần 2 (trễ hạn) dùng Table grid giống Phần 1, header đỏ `#C62828`, xen kẽ hồng `#FFEBEE`
- `tabs/tab_tien_do.py`: Thêm màu sắc cột Trạng thái — `td_green` `#2E7D32` cho Hoàn thành, `td_red` `#C62828` cho Chưa thực hiện (dùng ParagraphStyle riêng, không dùng TableStyle TEXTCOLOR vì không hoạt động với Paragraph)
- `tabs/tab_tien_do.py`: Đổi nhãn metadata: "Deadline" → "Thời hạn cuối cùng", "Tiến độ" → "Tiến độ hoàn thành"; tăng font size (header 13, meta 11, table 11, p2 11, chữ ký 12)
- `tabs/tab_tien_do.py`: Thêm chữ ký cuối báo cáo: Người lập, Kiểm soát, Giám đốc (ký, ghi rõ họ tên, đóng dấu)
- `tabs/tab_tien_do.py`: Tăng colWidths cột STT, PGD để tên PGD không bị xuống dòng (pgd 4 cột: 1.5/7.0/3.5/6.0cm, xa 5 cột: 1.2/5.2/4.3/3.3/4.0cm)
- `tabs/tab_tien_do.py`: Xóa toàn bộ mục "🔴 Báo cáo trễ hạn" cũ (nút PDF trễ hạn + Excel trễ hạn + metric cards) và xóa hàm `_xuat_pdf_tre_han()` (~245 dòng) — chức năng đã có trong Phần 2 của PDF báo cáo tiến độ mới
- `.streamlit/config.toml`: Đổi `fileWatcherType = "watchdog"` → `"poll"` để Streamlit tự động reload khi sửa bất kỳ file .py (không chỉ app.py)
- `tabs/tab_tien_do.py`: Thêm `_xuat_excel_tien_do()` — thay thế `pd.ExcelWriter` trần bằng openpyxl styling: header xanh `#003D7A` chữ trắng bold, border `#BDBDBD`, xen kẽ dòng xanh nhạt `#EEF4FB`, auto-width cột, number format `#,##0` cho cột số, `0.0"%"` cho Tỷ lệ HT%, font Times New Roman; đổi nhãn nút tải "⬇ Tải Excel báo cáo tiến độ"
- `tabs/base_tab.py` **(MỚI)**: Thêm `TabContext` class — base context cho mọi tab render; centralizes kwargs extraction (`role`, `username`, `pgd_user`, `df_full`), role normalization, tab container fallback (`tab if tab is not None else st.container()`), và các property tiện lợi (`is_cn`, `is_exec`, `is_pgd`, `role_norm`)
- `tabs/tab_tien_do.py`: Refactor `render()` và `render_tong_quan_only()` dùng `TabContext` — thay `normalize_role()` + `_tab_ctx` manual bằng `ctx = TabContext(tab, **kwargs); with ctx:`
- `tabs/tab_baocao.py`: Refactor `render()` dùng `TabContext` — giảm 10 dòng setup code, thay `normalize_role()` bằng `ctx.role_norm`

## [17/05/2026]
- `tabs/tab_trang_thai_nguon.py`: Implement mới hoàn toàn — 6 sub-tab health check mức B (tệp nguồn, merge & cache, snapshot, người dùng, hệ thống, audit log)
- `ws_management.py`: refactor `render_sidebar_menu()` + `_build_all_items()`
- `auth.py`: thêm `chuyenvien_cn` role, hệ thống 2 cấp 7 role hoàn chỉnh
- `snapshot_service.py`: `hstd_snapshot` by period, upsert-safe, auto-trigger post-merge
- `tab_ban_dai_dien.py`: 4 sub-tab (KPI + export, dự báo vốn, họp BĐD, sổ công văn)
- `tab_tien_do_nop.py`: tiến độ nộp PGD từ GSheet
- `tab_checklist_bc.py`: checklist deadline báo cáo via kv_store
- `tab_xlrr_tong_hop.py`: XLRR consolidated 4 sub-tab
- B7 refactor: normalize_role() thay hardcoded role check trong 6+ file
- `config.py`: thêm `COT_DU_NO_KHOANH` constant
- `tabs/tab_baocao.py`: refactor hardcode tên cột → `COT_*` constants (~40 replacements)
- `tabs/tab_danhsach.py`: hardcode `"Tên ĐVUT"`, `"Dư nợ khoanh"` → `COT_*`
- `tabs/tab_khtd_mau07.py`: xóa fallback patterns, dùng `COT_*` trực tiếp
- `tabs/tab_so_sanh_ky.py`: hardcode `"Ngày số liệu"`, `"Dư nợ khoanh"` → `COT_*`
- `tabs/tab_khtd.py`: `row.get("Nguồn vốn")`, `row.get("Mã nhà đầu tư")` → `COT_*`
- `tabs/tab_khtd_nhap.py`: `df.get("Mã nhà đầu tư")` → `COT_MA_NHA_DAU_TU`
- `tabs/tab_no_khoanh.py`: `nhom["Dư nợ khoanh"]` → `COT_DU_NO_KHOANH`
- `tabs/tab_tongquan.py`: `"Dư nợ khoanh"`, `"Tên xã"` → `COT_*`
- `services/ct_discovery.py`: `row.get("Nguồn vốn")`, `row.get("Phân loại NV")`, `row.get("Mã nhà đầu tư")` → `COT_*`
- `services/hhi_service.py`: `"Tổng dư nợ"` → `COT_TONG_DU_NO` + thêm import
- `services/kiem_soat_service.py`: `"Tên tổ"` (x9) → `COT_TEN_TO` + thêm import
- `services/upload_service.py`: `_cols_so` list → 10 `COT_*` constants + imports
- `scripts/check_hardcode_cols.py`: script kiểm tra hardcode column names (diff mode + full mode)
- `scripts/setup_hooks.py`: cài đặt Git pre-commit hook cho team
- `.git/hooks/pre-commit`: Git hook tự động chạy `check_hardcode_cols.py` khi commit
- `.trae/rules/rules.md`: section 10 — hướng dẫn pre-commit hook
- `app.py`: SQL `"Dư nợ khoanh"` → `COT_DU_NO_KHOANH` + import
- `utils.py`: `"Tên ĐVUT"` → `COT_DVUT` (3 hits)
- `workspaces/ws_operation.py`: `"Tên ĐVUT"` (x14) + `"Tên xã"` (x12) → `COT_*`
- `workspaces/ws_management.py`: `"Nguồn vốn"`, `"Dư nợ trong hạn"`, `"Dư nợ quá hạn"`, `"Tên ĐVUT"` → `COT_*` + imports
- `workspaces/ws_executive.py`: thêm `# noqa: COT` cho display labels (8 vị trí)
- `components/movers.py`: thêm `# noqa: COT` cho UI label dict

## [19/05/2026] — Hoàn thiện tab Nợ khoanh từ A-Z
- `db.py`: Thêm bảng `qlnk_ke_hoach` (13 cột + 3 index) vào `_init_db()`; thêm migration silent cho 3 cột mới; thay thế 3 stub functions (`doc_ke_hoach_kiem_tra`, `luu_ke_hoach_kiem_tra`, `duyet_ke_hoach`) bằng SQLite thật — hoàn thiện luồng d5 Kế hoạch và d7 Báo cáo Mẫu KH
- `tabs/tab_no_khoanh.py`: Import + dùng `get_tab_context(tab)` thay `tab if tab is not None else st.container()`
- `tabs/tab_no_khoanh.py` + `db.py`: **Redesign toàn bộ d5 Kế hoạch** — kế hoạch phân công cả năm: chọn năm + PGD → load toàn bộ món khoanh → data_editor điền ngày KT dự kiến từng món (không validate 120 ngày ở đây) → lưu JSON `ds_phan_cong`; schema `qlnk_ke_hoach` dùng `nam INTEGER` + `ds_phan_cong JSON`
- `tabs/tab_no_khoanh.py`: Mẫu 03/QLNK — viết lại hoàn toàn `_xuat_pdf_mau_03qlnk()` khớp mẫu thực tế: header 2 cột (đơn vị | Mẫu số), tiêu đề + khoảng thời gian, "Đơn vị ủy thác", gộp dòng theo khách hàng (SPAN dọc STT+Tên KH cho KH nhiều món), lọc `< 120 ngày`; UI thêm input Từ ngày/Đến ngày/Mã tổ/ĐVUT

## [19/05/2026]
- `scripts/check_conventions.py`: thêm encoding fix cho Windows — `import os` + `os.environ.setdefault("PYTHONIOENCODING", "utf-8")` + `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`
- `scripts/check_conventions.py`: sửa typo `fromfrom __future__ import annotations` → `from __future__ import annotations`; xóa duplicate `os.environ.setdefault()`
- Dọn temp files: xóa `_fix_final.py`, `_fix_noqa.py`, `_fix_noqa2.py`, `_refix.py`
- `.streamlit/config.toml`: đổi theme `light` → `dark` (nền tối `#0E1117`, chữ trắng `#FFFFFF`, primary `#42A5F5`)
- `app.py`: rewrite toàn bộ CSS (18 section) từ light theme → dark theme — sidebar navy `#1A1D2E`, main area `#0E1117`, card `#1E2130`, border `#2A2D3E`, chữ sáng `#CBD5E1`/`#F0F4F8`; giữ nguyên màu xanh `#2E7D32` accent
- `tests/test_period_compare.py`: viết mới toàn bộ — 5 test class, 23 test method cho join_by_loan, classify_changes, roll_cure_rate, vintage_nqh, par_breakdown
- `tabs/tab_ban_dai_dien.py`: fix ValueError "truth value of DataFrame is ambiguous" — thay `kwargs.get("df_full") or kwargs.get("df")` bằng check None/empty
- `tabs/tab_no_khoanh.py`: Mở rộng 2 sub-tab mới d5 "Kiểm tra" và d6 "Báo cáo" — form nhập kết quả kiểm tra (Mẫu 01/QLNK), lưu tạm/phê duyệt, báo cáo M08/M09/M10 + tiến độ kiểm tra theo PGD
- `workspaces/ws_operation.py`: Thêm tab "🔒 Nợ khoanh" vào nhóm Kiểm soát & Rủi ro — gọi tab_no_khoanh.render() với df=df_pgd, df_full=None
- `workspaces/ws_management.py` + `workspaces/ws_operation.py`: Đồng bộ tên 15 tab giống nhau giữa CN và PGD — thêm emoji + thống nhất tên gọi (Thông tin chung, Tiến độ công việc, Báo cáo tín dụng, Điện báo, Nhiệm vụ, So sánh kỳ, Nợ khoanh, Giao & ĐC KHTD, Ban Đại Diện, Ủy thác, Trạng thái hệ thống, Hướng dẫn)
- `tabs/tab_no_khoanh.py`: Fix lỗi `username` not defined trong render() + sửa anti-pattern 5 expander xuất Word (Mẫu KH, 01–04/QLNK) — dùng `nut_tai_word_va_pdf()` + `hien_thi_nut_tai()` từ template_service thay vì `st.download_button` inline trong `if st.button()`
- `tabs/tab_no_khoanh.py`: **Chuyển toàn bộ 5 biểu mẫu từ python-docx → reportlab PDF** — xóa ~650 dòng code Word `_qlnk_*` helpers + `_tao_word_*` + import `docx`/`template_service`; thêm reportlab PDF engine: đăng ký font TNR, header logo NHCSXH + quốc hiệu, style body/table/signature, 5 hàm `_xuat_pdf_mau_*` (KH, 01–04/QLNK) với Times New Roman 12-13pt, line-spacing 1.3-1.5, bảng xanh #2E7D32 xen kẽ dòng, chữ ký chuyên nghiệp, không phụ thuộc MS Word
- `tabs/tab_no_khoanh.py`: Sửa 5 expander UI: nút "📄 Tạo Word" → "📥 Xuất PDF", thêm form editable tối giản (Cán bộ KT, Nội dung bổ sung, Kết luận, Số tiền cam kết/thời hạn/phương thức, Ghi chú, Hạn cuối), lưu PDF vào session_state + download button

## [19/05/2026] — Fix tab Ban Đại Diện: TypeError truediv on PyArrow string dtype
- `tabs/tab_ban_dai_dien.py`: `_tong_hop_theo_pgd()` — thêm `_num()` helper (`pd.to_numeric(errors='coerce').fillna(0)`) cho du_no/dth/dqh/nkh/gn_nam sau groupby, tránh lỗi khi cột nguồn có dtype PyArrow large_string

## [19/05/2026] — Xuất PDF Kế hoạch kiểm tra nợ khoanh (theo NĐ 30)
- `tabs/tab_no_khoanh.py`: Thêm `_xuat_pdf_ke_hoach_kt(data_kh, ds_phan_cong, thanh_phan, ten_pgd, nam)` — PDF A4 dọc (≤20 món) hoặc landscape (>20 món); header 2 cột NĐ 30 (NHCSXH + CHXHCNVN); bảng phân công 8 cột gộp SPAN theo tên tổ; dòng tổng cộng; thành phần tham gia 5 mục; footer ký duyệt NGƯỜI LẬP / GIÁM ĐỐC
- `tabs/tab_no_khoanh.py`: Expander "Lập / cập nhật kế hoạch": thêm section "📋 Thành phần tham gia kiểm tra" (5 text_input: NHCSXH, Ban QL tổ prefill từ tổ trưởng, CT-XH, Trưởng thôn, UBND xã) + nút "📄 Xuất PDF Kế hoạch" (hiện khi `_rows_kh_pdf` không rỗng hoặc `df_kh_form` có dữ liệu); session state key `kh_pdf_buf`

## [19/05/2026] — Cải tiến tab Nợ Khoanh (heatmap, đơn vị, merge menu, cấu trúc sub-tab)
- `tabs/tab_no_khoanh.py`: `_heatmap_dao_han()` đổi tiêu đề → "Phân bổ theo năm hết hạn khoanh nợ", data source COT_NGAY_DH → COT_NGAY_HH_KHOANH
- `tabs/tab_no_khoanh.py`: Chuẩn hóa tên PGD runtime — thay "Đồng Nai"/"CN Đồng Nai"/"Hội sở" → `DON_VI_CHI_NHANH` sau khi lọc `df_kh`
- `tabs/tab_no_khoanh.py`: Thêm `_fmt_dong` lambda dùng `fmt_so()` — bảng tổng hợp hiển thị "triệu đồng" (cột đổi tên), bảng chi tiết hiển thị "X.XXX.XXX đồng"
- `tabs/tab_no_khoanh.py`: Import `tab_qlnk_dashboard`; đổi 7 → 8 st.tabs; thêm d0 "📊 Tổng quan" gọi `tab_qlnk_dashboard.render(d0, **kwargs)`
- `workspaces/ws_management.py`: Xóa cấu trúc `children` 2 mục Nợ Khoanh → 1 entry "🔒 Nợ Khoanh" duy nhất gọi `tab_no_khoanh.render()`
- `Chay_VBSP_SCM.bat`: Xóa `taskkill`, xóa `--server.fileWatcherType none` (bật lại watchdog auto-reload), thay poll loop 60s bằng `timeout /t 3`
- `tabs/tab_no_khoanh.py`: Đổi 8 → 7 st.tabs; gộp d5 (Kế hoạch) + d6 (Kiểm tra) + mẫu biểu vào tab mới "📋 Kiểm tra nợ khoanh (theo CV 368)"; d_bc "📊 Báo cáo" giữ M08/M09/QLNK_06/M10/Tiến độ; `pgd_filter_bc`/`rows_all_kt`/`da_kiem_tra_set` chuyển trước `st.tabs`
