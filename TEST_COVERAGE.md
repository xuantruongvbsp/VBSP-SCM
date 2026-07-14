# TEST_COVERAGE.md — Bản đồ Kiểm thử VBSP-SCM
> **Đọc trước khi viết test mới** — tránh trùng lặp, biết lỗ hổng.
> Cập nhật: 2026-05-22

---

## Tổng quan

| | Số lượng |
|---|---|
| File test | 45 |
| Test cases (ước tính) | ~820 |
| Modules có test | 28/~60 |
| 🔴 Modules chưa có test | ~32 |

---

## A. Modules đã có test — services/

| `data/core.py` | `test_core.py` | 21 | ✅ Cao | excel_to_parquet cache logic, 3 DuckDB queries |
| `data/pgd.py` | `test_pgd.py` | 19 | ✅ Cao | pgd_slug, duong_dan_pgd đầy đủ |
| `data/giao_ban.py` | `test_giao_ban.py` | 13 | ✅ Cao | tinh_so_lieu_van_xuoi: tags, tính toán, baseline |
| `alert_center.py` | `test_alert_center.py` | 11 | ✅ Cao | canh_bao_no_khoanh_sap_het_han |
| `services/migration_service.py` | `test_migration_service.py` | 18 | ✅ Cao | _nhan_nhom_no, matrix, monkeypatch SNAPSHOT_DIR |
| `services/khtd_nhap_service.py` | `test_khtd_nhap_service.py` | 29 | ✅ Cao | clean_sheet, format, CN/XA upload, luu_pdf |
| `services/excel_service.py` | `test_excel_service.py` | 13 | ✅ Cao | ten_file_xuat, ExcelReport build, chains |
| `components/movers.py` | `test_movers.py` | 12 | ✅ Cao | _compute_movers: tong_du_no, ty_le_nqh, roll_rate |
| `components/filter_bar.py` | `test_filter_bar.py` | 14 | ✅ Cao | apply_filters: scalar, list, range, multi |

| Module | Test file | Cases | Mức độ | Ghi chú |
|---|---|---|---|---|
| `upload_service.py` | `test_upload_service.py` | 9 | 🟡 Trung bình | Validation file; chưa test merge path đầy đủ |
| Merge toàn CN | `test_merge_du_lieu_toan_cn.py` | 22 | ✅ Cao | Schema, rollback, metadata, audit — toàn diện |
| `snapshot_service.py` | `test_snapshot_service.py` | 12 | ✅ Cao | CRUD, date parsing, ranges |
| `tien_do_service.py` | `test_tien_do_service.py` | 3 | 🔴 Thấp | Chỉ 3 smoke cases |
| `no_rui_ro_service.py` | `test_no_rui_ro_service.py` | 3 | 🔴 Thấp | KV key, roundtrip, delete |
| `khnv_noi_bo_service.py` | `test_khnv_noi_bo_service.py` | 2 | 🔴 Thấp | CRUD + audit |
| `tongquan_service.py` | `test_tongquan_service.py` | 10 | 🟡 Trung bình | KPI, heatmap, structure |
| `khtd_nhap_service.py` | `test_khtd_nhap_service.py` | 4 | 🟡 Trung bình | CN-level, XA-level, PDF |
| `khtd_mau07_service.py` | `test_khtd_mau07_service.py` | 4 | 🟡 Trung bình | Baseline, table, Word export |
| `khtd_service.py` | `test_khtd_service.py` | 3 | 🔴 Thấp | Action mapping, metadata |
| `template_service.py` (uy thác) | `test_uythac_template_service.py` | 13 | ✅ Cao | 13 form Word, smoke tests |
| `hhi_service.py` | `test_hhi_service.py` | 11 | ✅ Cao | HHI, concentration, classification |
| `no_khoanh_service.py` | `test_no_khoanh_service.py` | 7 | 🟡 Trung bình | Filter, groupby PGD |
| `so_sanh_ky_service.py` | `test_so_sanh_ky_service.py` | 14 | ✅ Cao | Aggregation, change class, HHI |
| `rui_ro_aggregation.py` | `test_rui_ro_aggregation.py` | 8 | ✅ Cao | Filter source, summarize |
| `report_service.py` | `test_report_service.py` | 7 | 🟡 Trung bình | Excel naming, sheets |
| `word_xln_service.py` | `test_word_xln_service.py` | 21 | ✅ Cao | Form 01–14, helpers, smoke |
| `kiem_soat_service.py` | `test_kiem_soat_service.py` | 9 | 🟡 Trung bình | Date calc, metrics, GHV |
| `data_quality.py` | `test_data_quality.py` | 13 | ✅ Cao | Column norm, debt validation |
| `kiem_soat_to_sai_so_tv.py` | `test_kiem_soat_to_sai_so_tv.py` | 9 | ✅ Cao | Shortage/surplus, DuckDB filter |
| `du_phong_service.py` | `test_du_phong_service.py` | 9 | 🟡 Trung bình | Monthly projection, breakdown |
| `cdtotkvv_service.py` | `test_cdtotkvv_service.py` | 7 | 🟡 Trung bình | Scoring, sheet naming |
| `period_compare.py` | `test_period_compare.py` | 16 | ✅ Cao | Status, loan join, cure rate |
| `services/file_detection_service.py` | `test_file_detection_service.py` | 21 | ✅ Cao | md5, alias, unit name detection, file-type sniffing |
| `services/uy_thac_service.py` | `test_uy_thac_service.py` | 26 | ✅ Cao | tinh_theo_dvut, loc_mau06/15, co_du_lieu_to, kv_key, payload builders, bien_ban CRUD |
| `services/tien_do_excel_service.py` | `test_tien_do_excel_service.py` | 8 | ✅ Cao | 3 sheets, styling, empty df |
| `services/telegram_service.py` | `test_telegram_service.py` | 4 | 🟡 Trung bình | Routing Upload PGD: chat PGD → chat phụ → chat chính; log lỗi theo notify key |

---

## B. Modules đã có test — core/auth/utils

| Module | Test file | Cases | Mức độ | Ghi chú |
|---|---|---|---|---|
| `auth.py` | `test_auth.py` | 14 | ✅ Cao | 9 roles, normalize, permissions |
| `config.py` | `test_config.py` | 7 | 🟡 Trung bình | PGD list, MA_PGD map |
| `db.py` | `test_db.py` | 7 | 🟡 Trung bình | kv_store CRUD, audit, prefix |
| `utils.py` (currency) | `test_utils.py` + `test_currency.py` | 28 + 14 | ✅ Cao | fmt_ty, fmt_so, fmt_pct |
| `pdf_service.py` | `test_pdf_service.py` | 5 | 🟡 Trung bình | reportlab dependency, smoke |

---

## C. Smoke tests

| Test file | Cases | Kiểm tra gì |
|---|---|---|
| `test_smoke_imports.py` | 2 | Import tất cả UI modules, không crash khi load |
| `test_smoke_snapshot.py` | 2 | Import + snapshot roundtrip cơ bản |

> ⚠️ Smoke import chỉ kiểm tra không crash khi `import`, không kiểm tra logic render.

---

## D. 🔴 CHƯA CÓ TEST — ưu tiên viết

### D1. Tabs UI (toàn bộ chưa có unit test)

| Tab file | Độ phức tạp | Rủi ro khi thiếu test | Ưu tiên |
|---|---|---|---|
| `tab_canh_bao_nqh.py` | ⭐⭐⭐⭐ Cao | Mới viết 8 sub-tab, 3 bug vừa fix | 🔴 Cao nhất |
| `tab_tongquan.py` | ⭐⭐⭐⭐ Cao | Dữ liệu core hiển thị cho BGĐ | 🔴 Cao |
| `tab_no_khoanh.py` | ⭐⭐⭐ TB | Logic tính toán phức tạp | 🔴 Cao |
| `tab_khtd_giao_dc.py` | ⭐⭐⭐ TB | Logic giao/điều chỉnh KHTD | 🟠 TB |
| `tab_tien_do.py` | ⭐⭐⭐ TB | 95 xã tracking | 🟠 TB |
| `tab_baocao.py` | ⭐⭐⭐ TB | Xuất Excel/Word nhiều loại | 🟠 TB |
| `tab_tracuu.py` | ⭐⭐ Thấp | Search đơn giản | 🟡 Thấp |
| `tab_upload_khnv.py` | ⭐⭐⭐ TB | Upload + merge trigger | 🟡 Thấp |
| `tab_den_han.py` | ⭐⭐ Thấp | Filter ngày đến hạn | 🟡 Thấp |
| `tab_canh_bao_som.py` | ⭐⭐⭐ TB | Alert logic | 🟠 TB |

### D2. Data modules chưa test

| Module | Rủi ro | Ưu tiên |
|---|---|---|
| `data/hstd.py` — `danh_dau_khong_hd()` | ✅ Có test (29 cases, test_hstd.py) | — |
| `data/hstd.py` — `canh_bao_migration()` | ✅ Có test (29 cases, test_hstd.py) | — |
| `data/core.py` — `excel_to_parquet()` | ✅ Có test (21 cases, test_core.py) | — |
| `data/core.py` — `tong_hop_du_no_pgd()`, `dem_no_qua_han_pgd()`, `tong_hop_theo_xa()` | ✅ Có test (21 cases, test_core.py) | — |
| `data/pgd.py` — `pgd_slug()`, `duong_dan_pgd()` | ✅ Có test (19 cases, test_pgd.py) | — |
| `data/khtd.py` — `doc_kehoach()`, `luu_kehoach()` | TB — thin wrapper kv_store (test_db.py bao phủ) | 🟠 TB |
| `data/giao_ban.py` — `tinh_so_lieu_van_xuoi()` | ✅ Có test (13 cases, test_giao_ban.py) | — |

### D3. Services chưa test

| Module | Rủi ro | Ưu tiên |
|---|---|---|
| `services/migration_service.py` | ✅ Có test (18 cases, test_migration_service.py) | — |
| `services/khtd_nhap_service.py` — XA path | ✅ Có test (29 cases, test_khtd_nhap_service.py) | — |
| `services/excel_service.py` | ✅ Có test (13 cases, test_excel_service.py) | — |
| `alert_center.py` — `canh_bao_no_khoanh_sap_het_han()` | ✅ Có test (11 cases, test_alert_center.py) | — |
| `services/file_detection_service.py` | ✅ Có test (21 cases, test_file_detection_service.py) | — |
| `services/uy_thac_service.py` | ✅ Có test (26 cases, test_uy_thac_service.py) | — |
| `services/tien_do_excel_service.py` | ✅ Có test (8 cases, test_tien_do_excel_service.py) | — |

### D4. Components chưa test (`components/`)

| Module | Rủi ro | Ưu tiên |
|---|---|---|
| `components/export_pdf.py` — `xuat_pdf_co_chart()` | Cao — logic PDF, đã có BUGMAP F6 (Timestamp format) | 🔴 Cao |
| `components/movers.py` — `_compute_movers()` | ✅ Có test (12 cases, test_movers.py) | — |
| `components/delta_card.py` — `kpi_row()`, `delta_card()` | TB — UI pure, khó test ngoài Streamlit context | 🟡 Thấp |
| `components/filter_bar.py` — `apply_filters()` | ✅ Có test (14 cases, test_filter_bar.py) | — |
| `components/loan_drawer.py` — `loan_detail_drawer()` | TB — UI pure, khó test ngoài Streamlit context | 🟡 Thấp |

---

## E. Test patterns đang dùng

```python
# Fixtures (tests/fixtures.py)
from tests.fixtures import tao_file_hstd_hop_le  # → bytes Excel 8 cột

# Mock db để test không cần SQLite thật
import tempfile, os
db_path = tempfile.mktemp(suffix=".db")
monkeypatch.setenv("VBSP_DB_PATH", db_path)

# DataFrame fixture chuẩn
def _df_mau():
    return pd.DataFrame({
        "Tên PGD": ["PGD Long Thành"],
        "Tổng dư nợ": [1_500_000_000],
        "Dư nợ quá hạn": [0],
    })
```

---

## F. Chạy test

```bash
# Tất cả test
pytest tests/ -v

# Một file
pytest tests/test_auth.py -v

# Coverage report
pytest tests/ --cov=. --cov-report=term-missing

# Chỉ smoke tests (nhanh)
pytest tests/test_smoke_imports.py tests/test_smoke_snapshot.py -v

# Exclude slow tests
pytest tests/ -v -m "not slow"
```

---

## G. Cập nhật file này khi nào

- Viết test mới → cập nhật bảng A/B/C, xóa khỏi D
- Fix bug mới → kiểm tra D có thiếu test không → ưu tiên viết ngay
- Thêm tab/service mới → thêm vào D trước, sau đó chuyển lên A khi có test
