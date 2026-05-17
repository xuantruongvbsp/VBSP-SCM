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
