# BUGMAP — VBSP-SCM
> Bản đồ lỗi thường gặp. Cập nhật mỗi khi fix bug mới.
> Format: **Dấu hiệu → Nguyên nhân → File/Dòng → Fix**

---

## Cách dùng nhanh

1. Nhìn traceback → lấy **3 dòng cuối**
2. Ctrl+F tên exception hoặc từ khóa lỗi trong file này
3. Làm theo hướng dẫn, sau đó bổ sung vào đây nếu có chi tiết mới

---

## Mục lục

- [A. Parquet / PyArrow](#a-parquet--pyarrow)
- [B. Streamlit UI](#b-streamlit-ui)
- [C. Dữ liệu / DataFrame](#c-dữ-liệu--dataframe)
- [D. Database / kv_store](#d-database--kv_store)
- [E. Upload / Merge](#e-upload--merge)
- [F. PDF / Word](#f-pdf--word)
- [G. Kế hoạch tín dụng](#g-kế-hoạch-tín-dụng)
- [H. GSheet / Google Sheets](#h-gsheet--google-sheets)
- [I. Phân quyền / Role](#i-phân-quyền--role)
- [J. Python / Code Pattern](#j-python--code-pattern)

---

## A. Parquet / PyArrow

### A1 — `ArrowInvalid: Could not convert '' with type str: tried to convert to int64`
| | |
|---|---|
| **File** | `services/upload_service.py` → `merge_du_lieu_toan_cn()` ~dòng 485 |
| **Nguyên nhân** | Cột mã số (vd: `Mã xã`, `Mã KH`) có mixed type sau `pd.concat`: một số PGD trả `int` (10001), PGD khác trả `str` rỗng `""` → PyArrow không infer được dtype |
| **Fix** | Trong vòng lặp `_str_cols` cleanup, thêm nhánh ép `float nguyên → str(int(v))`: `str(int(v)) if isinstance(v, float) and v == int(v) else str(v).strip()` |
| **Test** | `test_merge_du_lieu_toan_cn.py::test_ma_xa_mixed_type_khong_crash_parquet` |

### A2 — `ArrowInvalid: DataType(null)` khi ghi parquet
| | |
|---|---|
| **File** | `services/upload_service.py` → `merge_du_lieu_toan_cn()` ~dòng 472 |
| **Nguyên nhân** | Cột toàn `None` sau concat → dtype `null` → PyArrow từ chối |
| **Fix** | Cột object: `df[col] = df[col].astype(str).replace("nan", "")`. Cột số: `pd.to_numeric(errors="coerce")` |

### A3 — `ArrowInvalid: Invalid comparison between dtype=str and int`
| | |
|---|---|
| **File** | Bất kỳ tab nào dùng `df_nq11` — thường thấy ở `tab_nq11.py` ~dòng 108 |
| **Nguyên nhân** | Cột số trong NQ11 bị đọc thành ArrowDtype string, so sánh với int bị lỗi |
| **Fix** | Sau khi load df_nq11: `df[col] = pd.to_numeric(df[col], errors='coerce')` cho các cột DNO, nợ TH, nợ QH, số tiền, dư nợ, GN |

### A4 — `fillna("")` crash trên ArrowDtype(int64) / pandas int64
| | |
|---|---|
| **File** | `services/upload_service.py` → `merge_du_lieu_toan_cn()` dòng ~483–496 |
| **Dấu hiệu** | `ValueError: Cannot convert '46007818' to int64` hoặc `TypeError/ArrowInvalid` khi gọi `.fillna("")` trên cột số |
| **Nguyên nhân** | Cột định danh như `Mã thôn` (46007818), `Mã xã` từ Excel đọc thành `int64` hoặc `float64` (không phải `object`). Code chỉ xử lý `CategoricalDtype` và `object` → bỏ qua int64/float64 → `fillna("")` crash vì int64 không nhận chuỗi rỗng. Float64 không crash nhưng ra "46007818.0" thay vì "46007818". |
| **Fix** | Thêm 2 nhánh `elif` trước `if ser.dtype == object`: (1) `is_integer_dtype` → `astype(object)`; (2) `is_float_dtype` → chuyển số nguyên dạng float → str rồi `astype(object)`. Dùng `pd.api.types.is_integer_dtype()` / `is_float_dtype()` thay vì so sánh `dtype ==`. |
| **Ngày fix** | 2026-05-23 |

### A4c — `Expected bytes, got a 'int' object — Conversion failed for column Mã thôn with type object`
| | |
|---|---|
| **File** | `data/core.py` → `excel_to_parquet()` dòng 87 |
| **Dấu hiệu** | `("Expected bytes, got a 'int' object", 'Conversion failed for column Mã thôn with type object')` khi merge toàn CN sau upload |
| **Nguyên nhân** | Cache parquet cũ (trước khi fix A4/A4b) chứa cột `Mã thôn` dạng int64. Khi `excel_to_parquet()` thấy cache còn mới hơn Excel, nó đọc thẳng parquet mà **không** chuẩn hóa. Các frame từ PGD khác có string, frame từ PGD cũ có int64 → sau `pd.concat` cột thành object mixed (int + str) → `to_parquet` crash với `Expected bytes, got a 'int' object`. |
| **Fix** | Chuẩn hóa code columns NGAY SAU khi đọc từ cache parquet (bất kể mới hay cũ): thêm vòng lặp `for col in result.columns: if _should_force_str(col): result[col] = _normalize_code_series(result[col])` trước `return result` trong `excel_to_parquet()`. Thao tác idempotent: cột string không thay đổi. |
| **Ngày fix** | 2026-05-23 |

### A4b — `Could not convert '46002612' ... Conversion failed for column Mã thôn with type object`
| | |
|---|---|
| **File** | `data/core.py` → `excel_to_parquet()` ~dòng 18–55 |
| **Dấu hiệu** | Upload/merge crash khi tạo cache parquet cho 1 PGD: `ArrowInvalid: Could not convert '46002612' with type str: tried to convert to int64` |
| **Nguyên nhân** | `pd.read_excel()` trả cột code (vd `Mã thôn`) dạng `object` mixed (int + str). Khi `to_parquet(engine="pyarrow")`, Arrow infer `int64` rồi gặp chuỗi → fail |
| **Fix** | Trước khi `to_parquet`, ép các cột định danh (`Mã *`, `Số khế ước`...) về string thống nhất (float nguyên → int → str; NaN → "") |
| **Ngày fix** | 2026-05-23 |

### A4e — `Expected bytes, got a 'float' object — Conversion failed for column Số ATM with type object`
| | |
|---|---|
| **File** | `data/core.py` → `excel_to_parquet()` dòng 31–42 và `data/hstd.py` → `doc_baseline_merged()` |
| **Dấu hiệu** | Tab “📊 So sánh kỳ” báo lỗi render; traceback chứa `(“Expected bytes, got a 'float' object”, 'Conversion failed for column Số ATM with type object')` |
| **Nguyên nhân** | (1) openpyxl đọc cột “Số ATM” trả về `bytes` cho ô có giá trị, `float(NaN)` cho ô trống → object column hỗn hợp. (2) Hội sở đọc “Số ATM” thành string (không bytes) trong khi các PGD Bình Phước đọc thành bytes → sau concat, `iloc[0]` là string nên check “chỉ đầu” bỏ sót bytes từ PGD thứ 2+. (3) “Số ATM” không trong danh sách `_should_force_str()` → không được chuẩn hóa thành string → column vẫn mixed type. |
| **Fix** | (1) Thêm “số atm” vào `_should_force_str()` (~dòng 38) để chuẩn hóa từ đầu. (2) Bytes→str sanitization trước `to_parquet` trong cả `excel_to_parquet` (dòng 81–94) và `doc_baseline_merged` (dòng 125–138). (3) **Check 100 phần tử** (`any(isinstance(v, bytes) for v in _non_null.iloc[:100])`), không phải chỉ `iloc[0]`, để phát hiện bytes dù chúng xuất hiện ở PGD giữa. (4) **Refactor DRY**: dua `_should_force_str` + `_normalize_code_series` len module-level trong `core.py`, `hstd.py` import lai -- triet tieu goc loi copy-paste lech nhau. |
| **Pattern tránh** | `isinstance(_s.iloc[0], bytes)` — sai khi đơn vị đầu tiên trong concat có dtype khác (string). Dùng `any(... for v in sample[:100])` thay thế. |
| **Ngày fix** | 2026-05-24 |

### A4d — Baseline 31/12 báo “chưa có dữ liệu” dù đã upload (cache baseline 0 cột)
| | |
|---|---|
| **File** | `data/hstd.py` → `doc_baseline_merged()` và `data/core.py` → `excel_to_parquet()` |
| **Dấu hiệu** | Tab So sánh kỳ báo `⚠️ Chưa có dữ liệu baseline 31/12/YYYY` trong khi `data/baseline_pgd/.../HSTD_3112_YYYY.XLSX` đã có; kiểm tra `cache/hstd_baseline_YYYY.parquet` thấy size rất nhỏ và đọc ra `(0, 0)` |
| **Nguyên nhân** | Cache baseline đã bị ghi “rỗng/không hợp lệ” từ lần merge trước (do mixed dtype ở các cột định danh như `Số CMND`/`CCCD`/`Số điện thoại` khiến `to_parquet` fail hoặc dữ liệu bị clean sai). Logic cache chỉ so mtime nên không tự rebuild khi cache rỗng. |
| **Fix** | (1) `doc_baseline_merged` coi cache rỗng hoặc `< 15 cột` là invalid → rebuild. (2) Chuẩn hóa thêm các cột định danh (`cmnd/cccd/sdt`) về string trước khi ghi parquet (cả ở `excel_to_parquet` và ngay trước `result.to_parquet` khi merge). |
| **Ngày fix** | 2026-05-23 |

### A4e — Cache baseline thiếu PGD sau lần đọc lỗi (silent skip → cache không tự chữa)
| | |
|---|---|
| **File** | `data/hstd.py` → `doc_baseline_merged()` |
| **Dấu hiệu** | Tab So sánh mốc năm → Theo PGD: một số PGD hiển thị `0` cho cột "DN mốc" dù file `data/baseline_pgd/{slug}/HSTD_3112_YYYY.XLSX` đã tồn tại trên đĩa. Các PGD khác vẫn hiển thị bình thường. |
| **Nguyên nhân** | `doc_baseline_merged()` build cache baseline bằng cách duyệt 23 đơn vị, đọc từng file Excel. Nếu đọc file của PGD X lỗi (sai sheet, sai header, < 15 cột sau clean…), PGD X bị **bỏ qua âm thầm** — chỉ ghi log, không hiển thị cảnh báo cho user. Cache ghi ra thiếu PGD X. Logic stale-check **chỉ so mtime** (`file_mtime > cache_mtime`). File PGD X tồn tại trước khi cache được ghi nên `file_mtime < cache_mtime` → cache được coi là "hợp lệ" → PGD X vĩnh viễn không có trong baseline cho đến khi file được upload lại hoặc cache bị xóa thủ công. |
| **Fix** | Sau khi đọc cache parquet, kiểm tra tính đầy đủ: nếu có PGD nào trên đĩa (`os.path.exists`) mà thiếu trong cột `COT_TEN_PGD` của cache → coi cache không hợp lệ → tự rebuild. |
| **Ngày fix** | 2026-05-25 |

### A4f — Baseline 31/12 giữ số liệu cũ sau khi upload/rebuild trong cùng phiên
| | |
|---|---|
| **File** | `data/hstd.py` → `doc_baseline_merged()`; `tabs/tab_so_sanh_ky/render_moc_nam.py`; `tabs/tab_bien_ban_giao_ban.py`; `tabs/tab_thong_bao_ket_luan.py`; `tabs/tab_khtd_mau07.py` |
| **Dấu hiệu** | Màn `📈 So sánh mốc năm` hoặc các chức năng dùng baseline 31/12 vẫn hiện `Tổng dư nợ 31/12/YYYY` cũ dù đã upload lại file mốc hoặc vừa bấm `🔄 Tổng hợp baseline ngay` |
| **Nguyên nhân** | `doc_baseline_merged()` dùng `@st.cache_resource` nhưng không nhận tham số bust-cache theo `mtime`; trong khi luồng upload/rebuild baseline chủ yếu chỉ `st.rerun()`/`st.cache_data.clear()`. Kết quả: Streamlit giữ lại object baseline cũ trong cùng phiên |
| **Fix** | Thêm helper `ts_baseline_merged(nam)` lấy `mtime` lớn nhất của cache parquet + toàn bộ file `HSTD_3112_YYYY.XLSX`, đổi `doc_baseline_merged(nam, ts=...)`, và tất cả call-site baseline 31/12 truyền `ts` này để tự reload đúng khi nguồn đổi |
| **Ngày fix** | 2026-07-02 |

### A4g — Cache baseline tự rebuild mỗi lần vì lệch alias Hội sở
| | |
|---|---|
| **File** | `data/hstd.py` → `_canon_ten_pgd_baseline()`, `doc_baseline_merged()` |
| **Dấu hiệu** | Tab `📈 So sánh mốc năm` vẫn load chậm và log `cache thiếu 1 PGD (22/22 đơn vị có file) → rebuild` ở mỗi lần mở, dù tổng số đơn vị và số liệu sau rebuild đều đúng |
| **Nguyên nhân** | File/cache baseline có dòng Hội sở với tên `Hội sở CN Đồng Nai` trong khi completeness check lại so với key nội bộ `DON_VI_CHI_NHANH = "Hội sở Chi nhánh tỉnh"`. Kết quả: cache luôn bị xem là thiếu 1 đơn vị giả |
| **Fix** | Chuẩn hóa alias Hội sở về `DON_VI_CHI_NHANH` ngay khi đọc cache parquet và khi rebuild từ từng file PGD, rồi mới so tập đơn vị có file trên đĩa |
| **Ngày fix** | 2026-07-03 |

### A4h — Fallback baseline tổng cũ không bust cache khi file `HSTD_3112_YYYY.XLSX` đổi
| | |
|---|---|
| **File** | `data/hstd.py` → `ts_baseline_merged()`, `doc_baseline_merged()` |
| **Dấu hiệu** | Ở môi trường chưa có baseline per-PGD, thay file tổng `data/baseline/HSTD_3112_YYYY.XLSX` rồi reload app nhưng màn `📈 So sánh mốc năm` vẫn giữ số cũ trong cùng phiên |
| **Nguyên nhân** | Helper `ts_baseline_merged()` và stale-check của `doc_baseline_merged()` chỉ nhìn cache parquet + file per-PGD; nhánh fallback `doc_baseline(nam)` dùng file tổng cũ không được đưa vào cache key |
| **Fix** | Khi chưa có file baseline per-PGD, thêm `baseline_path(nam)` vào timestamp tổng hợp và so luôn `mtime` file tổng với `cache_mtime` trước khi quyết định dùng lại cache |
| **Ngày fix** | 2026-07-03 |

### A4i — `ts_baseline_merged()` tự cache 5 phút làm baseline HSTD vẫn stale
| | |
|---|---|
| **File** | `data/hstd.py` → `ts_baseline_merged()` |
| **Dấu hiệu** | File baseline HSTD 31/12 đã đổi nhưng màn `📈 So sánh mốc năm` vẫn giữ `Tổng dư nợ 31/12/YYYY` cũ trong cùng process; `Ctrl+F5` không đổi số ngay |
| **Nguyên nhân** | `doc_baseline_merged()` đã nhận tham số `ts` để bust cache, nhưng chính helper `ts_baseline_merged()` lại bị `@st.cache_data(ttl=300)`. Khi file đổi trong vòng 5 phút, helper vẫn trả `ts` cũ nên `cache_resource` của baseline không bị invalidated |
| **Fix** | Bỏ cache khỏi `ts_baseline_merged()`. Hàm này chỉ `stat` ~22 file nên rất nhẹ, và cần luôn phản ánh `mtime` mới nhất của cache parquet/file baseline |
| **Ngày fix** | 2026-07-03 |

### A5 — DuckDB `Binder Error: Referenced column not found in FROM clause`
| | |
|---|---|
| **File** | `tabs/tab_trang_thai_nguon.py`, bất kỳ tab nào dùng DuckDB query trên parquet |
| **Dấu hiệu** | `duckdb.BinderException: Referenced column "X" not found in FROM clause` |
| **Nguyên nhân** | Parquet cache thiếu cột (chưa merge đủ, hoặc schema khác giữa các PGD) |
| **Fix** | Kiểm tra schema parquet TRƯỚC khi query: `df_check = con.execute("SELECT * FROM read_parquet(...) LIMIT 1").fetchdf()` → kiểm tra `if cot in df_check.columns` |
| **Ngày fix** | 2026-05-22 |

### A6 — GQVL parquet rỗng (0 cột)
| | |
|---|---|
| **Dấu hiệu** | `Invalid Input Error: Failed to read Parquet file ... Need at least one non-root column` |
| **Nguyên nhân** | Chưa upload/merge GQVL → file parquet rỗng hoặc không có cột |
| **Fix** | Kiểm tra `if os.path.exists(path) and os.path.getsize(path) > 0` trước khi `read_parquet()`; nếu không → `st.info("Chưa có dữ liệu GQVL")` thay vì crash |
| **Ngày fix** | 2026-05-22 |

### A7 — Báo cáo snapshot theo chương trình luôn rỗng
| | |
|---|---|
| **File** | `snapshot_service.py` → `doc_snapshot_theo_ct()` |
| **Dấu hiệu** | Màn nhiều kỳ có dữ liệu tổng nhưng phần `Theo CT` không có dòng nào |
| **Nguyên nhân** | Query tìm `ten_pgd='__CN__' AND ma_ct!='ALL'`, trong khi luồng ghi chỉ tạo dòng `__CN__/ALL/ALL`; chi tiết chương trình chỉ tồn tại ở các dòng PGD |
| **Fix** | Cộng các dòng `ten_pgd!='__CN__' AND ma_ct!='ALL'` theo `ma_ct` |
| **Test** | `tests/test_snapshot_service.py::TestDocSnapshot::test_doc_theo_ct_cong_tu_dong_chi_tiet_pgd` |
| **Ngày fix** | 2026-07-11 |

### A8 — Status board Snapshot HSTD cộng chồng nhiều lớp dữ liệu
| | |
|---|---|
| **File** | `tabs/tab_trang_thai_nguon.py` → `_doc_snapshot_status()`, `tabs/tab_canh_bao_nqh.py`, `tabs/tab_xay_dung_khtd.py` |
| **Dấu hiệu** | Tổng dư nợ snapshot cao gấp nhiều lần thực tế và số đơn vị có thể gồm cả `__CN__` |
| **Nguyên nhân** | Query cộng đồng thời dòng chi tiết CT/NV, tổng PGD và tổng CN; phần hiển thị tỷ đồng còn chia nhầm `/1e12` |
| **Fix** | Chỉ lấy `ma_ct='ALL' AND nguon_von='ALL' AND ten_pgd!='__CN__'`; quy đổi tỷ đồng bằng `/1e9` |
| **Test** | `tests/test_tab_trang_thai_nguon.py::test_snapshot_status_chi_cong_lop_tong_pgd` |
| **Ngày fix** | 2026-07-11 |

### A9 — Kỳ snapshot lấy dòng ngày số liệu đầu tiên thay vì ngày lớn nhất
| | |
|---|---|
| **File** | `snapshot_service.py` → `_ky_tu_df()`, `_ngay_so_lieu_max()`; `services/upload_service.py` |
| **Dấu hiệu** | Dữ liệu merge có nhiều mốc ngày nhưng snapshot bị gán vào tháng của dòng đầu tiên |
| **Nguyên nhân** | Logic cũ dùng `dropna().iloc[0]`, lệch với metadata merge vốn dùng ngày lớn nhất |
| **Fix** | Parse toàn bộ ngày với `format='mixed', dayfirst=True`, dùng `max()` cho cả kỳ và ngày lưu; hook CDTOTKVV gọi chung helper này |
| **Test** | `tests/test_snapshot_service.py::TestKyTuDf::test_nhieu_ngay_lay_ngay_lon_nhat` |
| **Ngày fix** | 2026-07-11 |

### A10 — Cache snapshot stale sau thao tác ghi hoặc xóa
| | |
|---|---|
| **File** | `snapshot_service.py` → `luu_snapshot()`, `xoa_snapshot()`; `services/upload_service.py` → `_snap_bg()` |
| **Dấu hiệu** | UI vẫn hiển thị danh sách kỳ/số liệu cũ tối đa 5 phút sau lưu, xóa hoặc auto-snapshot |
| **Nguyên nhân** | Các reader dùng `@st.cache_data(ttl=300)` nhưng writer không invalid cache sau commit |
| **Fix** | Gọi helper `_clear_snapshot_cache()` sau ghi/xóa thành công để clear riêng các reader snapshot, không xóa toàn bộ cache app |
| **Test** | `tests/test_snapshot_service.py::TestLuuSnapshot::test_luu_clear_cache`, `tests/test_snapshot_service.py::TestXoaSnapshot::test_xoa_clear_cache` |
| **Ngày fix** | 2026-07-11 |

### A11 — Xóa snapshot chỉ xóa HSTD và cache helper có thể crash
| | |
|---|---|
| **File** | `snapshot_service.py` → `xoa_snapshot()`, `_clear_snapshot_cache()` ~dòng 1013 |
| **Dấu hiệu** | Xóa một kỳ snapshot nhưng các bảng `uy_thac_snapshot`, `nq11_snapshot`, `gqvl_snapshot`, `cdtotkvv_snapshot` vẫn còn dữ liệu; hoặc writer gọi `.clear()` trực tiếp gây lỗi khi cache function chưa sẵn sàng |
| **Nguyên nhân** | `xoa_snapshot()` chỉ DELETE `hstd_snapshot`; cache invalidation vừa dùng global clear rộng, vừa có nơi gọi `.clear()` không qua guard |
| **Fix** | Khai báo `_SNAPSHOT_TABLES` và xóa cả 5 bảng trong một transaction; gom cache invalidation vào `_clear_snapshot_cache()` với `hasattr(fn, "clear")` và logging `exc_info=True` |
| **Test** | `tests/test_snapshot_service.py::TestXoaSnapshot::test_xoa_dong_bo_ca_5_bang`, `tests/test_snapshot_service.py::TestSnapshotServiceHelpers::test_compare_snapshot_2_ky_co_delta` |
| **Ngày fix** | 2026-07-19 |

---

## B. Streamlit UI

### B35 — Telegram NQH tuần hiển thị `12.903.4 tỷ` và chênh lệch `-0 tr`
| | |
|---|---|
| **File** | `services/telegram_service.py` → `gui_bao_cao_nqh_tuan()` |
| **Dấu hiệu** | Tổng dư nợ có hai dấu chấm thập phân; chênh lệch NQH dưới 1 triệu đồng có thể hiện tăng/giảm `0 tr` |
| **Nguyên nhân** | Thay dấu phân cách bằng `.replace(",", ".")` một bước làm lẫn dấu nghìn với dấu thập phân; mọi chênh lệch đều format 0 số lẻ |
| **Fix** | Đổi dấu qua ký tự trung gian để ra chuẩn Việt Nam (`12.903,4`); chênh lệch khác 0 nhưng dưới 1 triệu đồng hiển thị 1 số lẻ |
| **Ngày fix** | 2026-07-18 |

### B34 — Báo cáo NQH tuần lỗi import `CACHE_HSTD` từ sai module
| | |
|---|---|
| **File** | `tabs/tab_telegram_admin.py` dòng ~13, ~235–580 |
| **Dấu hiệu** | Bấm gửi Báo cáo NQH tuần báo `cannot import name 'CACHE_HSTD' from 'data.core'` |
| **Nguyên nhân** | Các nhánh gửi báo cáo Telegram import `CACHE_HSTD` từ `data.core`, trong khi constant được khai báo tại `config.py`; sau khi sửa nguồn import, gọi `.exists()` trực tiếp cũng sai vì `CACHE_HSTD` là `str` |
| **Fix** | Import `CACHE_HSTD` từ `config.py` ở module-level; kiểm tra file bằng `Path(CACHE_HSTD).exists()` cho cả 7 nhánh báo cáo dùng HSTD |
| **Ngày fix** | 2026-07-18 |

### B25 — Toàn cảnh 22 PGD hiển thị thời gian sửa file thay vì ngày số liệu HSTD
| | |
|---|---|
| **File** | `tabs/tab_pgd_cards.py` → `render()`, `_render_ranking_table()`, `_upload_info()` |
| **Dấu hiệu** | Thẻ PGD và cột HSTD trong bảng xếp hạng hiện thời điểm như `09/07 21:42`, trong khi ngày số liệu thực trong HSTD là `30/06/2026` |
| **Nguyên nhân** | `_upload_info()` dùng `os.path.getmtime()` nên lấy thời gian file được ghi lên đĩa, không phải giá trị nghiệp vụ trong cột `Ngày số liệu` |
| **Fix** | Đọc ngày lớn nhất hợp lệ từ `COT_NGAY_SL`, fallback `merge_meta_hstd["ngay_sl"]`; `_upload_info()` chỉ còn kiểm tra sự tồn tại của file để xác định trạng thái ✅/❌ |
| **Ngày fix** | 2026-07-11 |

### B26 — Giao KHTD dùng bảng ngang quá rộng, khó nhập và đối chiếu
| | |
|---|---|
| **File** | `tabs/tab_khtd_giao_dc.py` → `_section_b_giao()` |
| **Dấu hiệu** | Mỗi chương trình tạo ba cột `KH trước / Dư nợ / KH giao`; một PGD có nhiều chương trình khiến bảng phải cuộn ngang dài và khó xác định ô cần nhập |
| **Nguyên nhân** | Dữ liệu Xã × Chương trình bị pivot sang dạng wide phục vụ nhập liệu, làm số cột tăng theo số chương trình tín dụng |
| **Fix** | Chuyển màn nhập sang bảng dài: mỗi dòng là một Xã/Phường × Chương trình, sáu cột hiển thị ổn định và chỉ cột `KH giao (triệu đồng)` được phép sửa; giữ nguyên cấu trúc payload khi lưu |
| **Ngày fix** | 2026-07-11 |

### B27 — Tổng hợp KHTD thấp hơn dư nợ nhưng không giải thích chương trình chỉ thu hồi
| | |
|---|---|
| **File** | `tabs/tab_khtd_giao_dc.py` → `_section_c_tong_hop()` |
| **Dấu hiệu** | Tổng KH thấp hơn dư nợ thực hiện dù các số đều cùng đơn vị triệu đồng, khiến người dùng nghi ngờ sai quy đổi |
| **Nguyên nhân** | Mã 24 và mã 7 nguồn ĐP là chương trình chỉ thu hồi, không giao kế hoạch nên bị loại đúng nghiệp vụ nhưng giao diện chưa chú thích |
| **Fix** | Thêm một dòng ghi chú ngay dưới bảng Tổng hợp TW/ĐP, nêu tên hai chương trình và lý do Tổng KH có thể thấp hơn dư nợ |
| **Ngày fix** | 2026-07-11 |

### B28 — Nhập KH Giao hiển thị toàn bộ Dư nợ TH bằng 0
| | |
|---|---|
| **File** | `tabs/tab_khtd_giao_dc.py` → `_build_du_no_map()`, `_section_b_giao()` |
| **Dấu hiệu** | Cột `Dư nợ TH (triệu đồng)` bằng 0 ở mọi xã/chương trình dù HSTD đã có dư nợ |
| **Nguyên nhân** | `PGD_XA_MAP` dùng tên đầy đủ như `Xã Phước Thái`, còn HSTD thường lưu `Phước Thái`; code ghép bằng chuỗi tuyệt đối nên không tìm được khóa và luôn fallback `0.0` |
| **Fix** | Dùng `tim_ten_xa_trong_hstd()` và `casefold()` để chuẩn hóa tên xã ở cả HSTD lẫn danh mục trước khi group và lookup; giữ nguyên khóa mã chương trình + nguồn vốn |
| **Test** | `tests/test_khtd_giao_dc.py::test_build_du_no_map_chuan_hoa_tien_to_xa_phuong` |
| **Ngày fix** | 2026-07-11 |

### B29 — Ban Đại Diện: Bảng tổng hợp theo PGD thiếu phân cách hàng nghìn
| | |
|---|---|
| **File** | `tabs/tab_ban_dai_dien.py` → `_render_tong_hop()` |
| **Dấu hiệu** | Mục `🏛️ Ban Đại Diện → Bảng tổng hợp theo PGD` hiển thị các cột triệu đồng dạng số thô, khó đọc vì không có phân cách hàng nghìn kiểu Việt Nam |
| **Nguyên nhân** | `st.dataframe()` nhận trực tiếp `df_pgd` số thật; code chưa tạo bản hiển thị đã format cho các cột tiền/số lượng trước khi render |
| **Fix** | Giữ `df_pgd` số thật cho Excel/PDF, đồng thời tạo `df_pgd_display` và format các cột triệu đồng bằng `fmt_so()`, cột `Số KH` bằng `fmt_so()`, cột `NQH%` sang chuỗi `%` kiểu Việt Nam trước khi `st.dataframe()` |
| **Ngày fix** | 2026-07-12 |

### B30 — Script cài Telegram Scheduler gọi cmdlet repetition không tồn tại
| | |
|---|---|
| **File** | `scripts/setup_task_scheduler.ps1` |
| **Dấu hiệu** | Chạy script bằng PowerShell Administrator cài được `VBSP-DailyReport` và `VBSP-NhacDeadline`, sau đó dừng tại lỗi `New-ScheduledTaskRepetitionPattern is not recognized`; Scheduler 5 phút và Polling 1 phút không được tạo |
| **Nguyên nhân** | Windows ScheduledTasks module trên máy có tham số `RepetitionInterval` / `RepetitionDuration` ngay trong `New-ScheduledTaskTrigger`, nhưng không cung cấp cmdlet riêng `New-ScheduledTaskRepetitionPattern` |
| **Fix** | Tạo trigger `-Once -At (Get-Date).AddMinutes(1)` và truyền trực tiếp `-RepetitionInterval` / `-RepetitionDuration` cho cả Scheduler 5 phút và Polling 1 phút; thời hạn lặp 3650 ngày |
| **Ngày fix** | 2026-07-14 |

### B31 — Báo cáo hoàn thành không thể ẩn khỏi Cài deadline mà vẫn giữ lịch sử
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py`, `services/report_submission_service.py` |
| **Dấu hiệu** | Bấm `Ngưng` chỉ gỡ deadline nhưng loại báo cáo vẫn quay lại nhóm `Cần cài`; nếu xóa dòng Google Sheet để làm nó biến mất thì mất luôn lịch sử nộp trong ứng dụng |
| **Nguyên nhân** | Hệ thống chỉ có hai lớp dữ liệu Google Form và deadline, chưa có trạng thái nghiệp vụ `đã lưu trữ` độc lập |
| **Fix** | Lưu trạng thái theo loại báo cáo vào `bao_cao_archive_config`; loại lưu trữ được gỡ deadline và loại khỏi Tổng quan/Telegram nhưng dữ liệu Google Form vẫn hiện trong tab `Đã lưu trữ`, có xuất Excel và khôi phục |
| **Test** | `tests/test_report_submission_service.py::TestLuuTruBaoCao` |
| **Ngày fix** | 2026-07-15 |

### B32 — Báo cáo KHNV xuất số Điện báo bằng 0 và đối chiếu sai đơn vị
| | |
|---|---|
| **File** | `tabs/tab_khnv_bao_cao.py`, `services/khnv_bao_cao_service.py`, `data/hstd.py` |
| **Dấu hiệu** | Màn hình đọc được Điện báo nhưng file Word/Excel vẫn xuất tổng dư nợ bằng 0; bảng đối chiếu có thể lệch 1.000.000 lần hoặc bỏ sót phần KHB |
| **Nguyên nhân** | UI tạo dữ liệu xuất giả bằng 0; bộ đọc matrix chưa trả về đơn vị nguồn; đối chiếu chỉ dùng KHA và cố định sheet `DB1` |
| **Fix** | Dùng số Điện báo thực khi xuất, nhận diện và chuẩn hóa Đồng/Triệu đồng về VND, cộng KHA+KHB cho nợ quá hạn/nợ khoanh, cho chọn sheet thực tế và định dạng số Việt Nam |
| **Test** | `tests/test_khnv_bao_cao.py::TestTongHopDienBao`, `tests/test_hstd.py::TestDienBaoDonVi` |
| **Ngày fix** | 2026-07-16 |

### B33 — Thông báo Telegram nhầm ngày gửi với ngày số liệu
| | |
|---|---|
| **File** | `services/telegram_service.py`, `tests/test_telegram_service.py` |
| **Dấu hiệu** | Các tin Telegram trình bày không đồng nhất; một số tin chỉ hiện ngày gửi hoặc deadline nên người đọc có thể hiểu nhầm cache HSTD là số liệu mới nhất |
| **Nguyên nhân** | Từng hàm tự ghép nội dung, không có khung chung cho phạm vi, ngày số liệu, nguồn và thời điểm cập nhật |
| **Fix** | Chuẩn hóa tập trung tại cổng gửi theo `notify_key`; tin HSTD ưu tiên `merge_meta_hstd.ngay_sl`, tin GSheet dùng ngày quét hiện tại và không lấy nhầm deadline; bổ sung đủ tên, phạm vi, tóm tắt, chi tiết, nguồn và thời điểm cập nhật cho 19 loại |
| **Test** | `tests/test_telegram_service.py::TestChuanHoaThongBao` |
| **Ngày fix** | 2026-07-16 |

### B7 — Card grid HTML hiển thị raw code thay vì render
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` dòng ~883 |
| **Dấu hiệu** | Khối "Tổng quan nhanh các PGD" hiển thị toàn bộ HTML thô (`<div style=...>`) thay vì card grid đúng |
| **Nguyên nhân** | Streamlit 1.36+ không render HTML qua `st.markdown(..., unsafe_allow_html=True)` đáng tin cậy trong một số context — cần dùng `st.html()` |
| **Fix** | Thay `st.markdown(f"""...""", unsafe_allow_html=True)` bằng `st.html(f"""...""")` |
| **Ngày fix** | 2026-07-11 |

### B6 — `cannot import name 'render_nhap_cn' from partially initialized module 'tabs.tab_khtd_nhap'`
| | |
|---|---|
| **File** | `tabs/tab_khtd.py` dòng 404 |
| **Dấu hiệu** | Crash khi mở tab Xuất báo cáo KHTD: `cannot import name 'render_nhap_cn' from partially initialized module 'tabs.tab_khtd_nhap' (most likely due to a circular import)` |
| **Nguyên nhân** | `tab_khtd.py` import `render_nhap_cn, render_nhap_pgd` từ `tab_khtd_nhap` ở **module-level**; trong khi `tab_khtd_nhap` cũng import các hằng/hàm từ `tab_khtd` ở module-level → vòng tròn: A chưa xong đã bị B hỏi, B chưa xong đã bị A hỏi |
| **Fix** | Xóa module-level import dòng 404; chuyển thành **lazy import** bên trong `with tab_cn:` / `with tab_xa:` block — đúng pattern đã dùng cho `render_xuat_baocao` (line 449) |
| **Pattern chuẩn** | Bất kỳ hai tab nào import lẫn nhau → bên **gọi hàm** phải dùng lazy import bên trong hàm/block, không để ở module-level |
| **Ngày fix** | 2026-06-04 |

### B5 — KPI Điện báo hiển thị sai 1000x (scan đơn vị chỉ quét 15 cột)
| | |
|---|---|
| **File** | `tabs/tab_candoi.py` dòng ~199–209 |
| **Dấu hiệu** | KPI "Tổng dư nợ" hiển thị `13,430,710 tỷ đồng` thay vì `13,430.7 tỷ đồng`; biểu đồ thanh thấp bất thường (giá trị chia /1,000,000 thay vì /1000) |
| **Nguyên nhân** | Vòng lặp detect "triệu đồng" chỉ quét 15 cột đầu → sheet M có text đơn vị ở cột xa → `_don_vi_trieu = False` → `_to_ty(x)` trả về `x` nguyên vẹn thay vì `/1000`; `_dv_div = 1_000_000` thay vì `1000` |
| **Fix** | Mặc định `_don_vi_trieu = True` (tất cả file Điện báo VBSP đều dùng triệu đồng). `_to_ty(x) = round(x/1000, 2)` unconditional. `_dv_div = 1000` unconditional |
| **Ngày fix** | 2026-06-04 |

### B4 — Tab HỖ TRỢ ĐỊA BÀN load chậm (mọi rerun)
| | |
|---|---|
| **File** | `workspaces/ws_operation.py` dòng ~159-409 |
| **Dấu hiệu** | Tab Trang Chủ PGD phản hồi chậm 0.5-3s sau mọi thao tác click/tương tác |
| **Nguyên nhân** | `_kpi_pgd_list()` gọi `df.to_json()` lên đến 1000 hàng TRƯỚC khi gọi hàm cache — to_json chạy dù cache đã có kết quả; trên cache miss còn thêm `pd.read_json()` để parse lại |
| **Fix** | Thay `_df_json: str` bằng `_df: pd.DataFrame` (prefix `_` → Streamlit không hash); loại bỏ `to_json()` hoàn toàn; dùng `df_hash` làm cache key |
| **Ngày fix** | 2026-06-03 |

### B2 — `StreamlitAPIException: Selectbox has no options`
| | |
|---|---|
| **File** | `tabs/tab_theo_doi_nhap/ui_detail.py` dòng ~281 |
| **Dấu hiệu** | Crash khi user filter → 0 kết quả, drill-down selectbox nhận list rỗng |
| **Nguyên nhân** | `st.selectbox` không cho phép options=[] — ném APIException ngay |
| **Fix** | Guard `if not pgd_list: st.info(...); return` trước khi gọi selectbox |
| **Ngày fix** | 2026-05-31 |

### B3 — Checkbox mutual-exclusivity logic sai (UI vs Python state)
| | |
|---|---|
| **File** | `tabs/tab_theo_doi_nhap/ui_detail.py` |
| **Dấu hiệu** | Filter hoạt động đúng nhưng checkbox "Tất cả" vẫn hiển thị tích dù đã chọn filter con |
| **Nguyên nhân** | Gán lại biến Python sau `st.checkbox()` không cập nhật widget state trên browser |
| **Fix** | Dùng `st.radio` với `horizontal=True` thay vì nhiều checkbox mutual-exclusive |
| **Ngày fix** | 2026-05-31 |

### B1 — `DuplicateElementKey`
| | |
|---|---|
| **File** | Bất kỳ tab nào render nhiều lần |
| **Nguyên nhân** | Widget key trùng giữa 2 render cycle, hoặc dùng index loop làm key |
| **Fix** | Thêm suffix unique: `key=f"filter_pgd_{tab_id}"`. Tuyệt đối không dùng index loop |
| **Kiểm tra nhanh** | `grep -n 'key="' file.py` → tìm key trùng |

### B2 — Trang trắng / crash sau khi dùng `width='stretch'`
| | |
|---|---|
| **File** | Bất kỳ tab nào dùng `st.dataframe()` |
| **Nguyên nhân** | Streamlit 1.57.0+ không còn hỗ trợ `width='stretch'` |
| **Fix** | Thay toàn bộ `width='stretch'` → `use_container_width=True` |
| **Bulk fix** | `grep -rn "width='stretch'" tabs/ workspaces/` |

### B3 — CSS không có hiệu lực sau khi click tab
| | |
|---|---|
| **File** | `app.py` block `# ── Global CSS ──` |
| **Nguyên nhân** | CSS inject bọc trong guard `if "_css_injected" not in st.session_state` → chỉ inject lần đầu, rerun tiếp theo mất CSS |
| **Fix** | Bỏ guard, inject CSS vô điều kiện mỗi rerun |

### B4 — Sidebar mất màu navy
| | |
|---|---|
| **File** | `app.py` → block CSS global |
| **Fix** | Kiểm tra CSS inject có bị guard không (xem B3). Hard refresh `Ctrl+Shift+R` |

### B5 — Section trong tab hiện heading nhưng không có bảng/dữ liệu gì
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` (và bất kỳ tab nào dùng pattern `if col in df.columns:`) |
| **Dấu hiệu** | Heading render (`st.markdown("**📂 Cơ cấu...**")`), phần nội dung bên dưới hoàn toàn trống, không có lỗi |
| **Nguyên nhân** | `if col in df.columns:` guard thiếu `else` → khi cột bị thiếu (file PGD riêng, tên cột sai, chưa merge) toàn bộ nội dung bị bỏ qua im lặng |
| **Fix** | Thêm `else: st.warning(f"Thiếu cột {col}...")` + expander debug liệt kê cột còn thiếu. Đã fix cho 3 section trong `tab_tongquan.py` (2026-05-22) |
| **Phòng tránh** | Mọi `if col in df.columns:` block có nội dung quan trọng phải có `else` thông báo |
| **Ngày fix** | 2026-05-22 |

### B5 — `ValueError: The truth value of a DataFrame is ambiguous`
| | |
|---|---|
| **File** | `ws_operation.py`, `tab_no_khoanh.py`, `tabs/tab_canh_bao_nqh.py` ~dòng 580 |
| **Nguyên nhân** | Dùng `or` với DataFrame: `kwargs.get("df_full") or kwargs.get("df")` → Python gọi `bool(DataFrame)` → exception |
| **Fix** | `df = kwargs.get("df"); df_full = kwargs.get("df_full", df)` — dùng default của `.get()` thay vì `or`; hoặc `_df = kwargs.get("df_full"); df_full = _df if _df is not None else kwargs.get("df")` |
| **Ngày fix** | 2026-05-22 |

### B6 — Tab crash khi `tab=None` (context manager error)
| | |
|---|---|
| **File** | Các renderer trong `ws_operation.py` dùng `with tab_parent:` |
| **Nguyên nhân** | `tab=None` khi render ngoài context Streamlit tab |
| **Fix** | Thay `with tab_parent:` → `with get_tab_context(tab_parent):` (từ `utils.py`) |

### B7 — Index lệch khi subset pandas Series bằng boolean mask
| | |
|---|---|
| **Dấu hiệu** | Kết quả tính toán sai lệch, hoặc `ValueError` về index alignment |
| **File** | `tabs/tab_canh_bao_nqh.py` ~dòng 97 |
| **Nguyên nhân** | Tạo Series con qua subset index: `s2 = s[da_mask]` → index bị skip, khi dùng lại với mask khác gây lệch |
| **Fix** | Dùng Series gốc trực tiếp với mask: `s[da_mask]` ngay tại chỗ cần, KHÔNG lưu Series đã subset vào biến trung gian |
| **Ngày fix** | 2026-05-22 |

### B8 — `.get("col", False)` fragile pattern trên DataFrame
| | |
|---|---|
| **Dấu hiệu** | Cột kiểm tra tồn tại nhưng `.get()` trả về `False` → nhầm với "cột không tồn tại" |
| **File** | `tabs/tab_canh_bao_nqh.py` ~dòng 173 |
| **Nguyên nhân** | `df_kh.get("is_3m_inactive", False)` — nếu cột có giá trị `0` hoặc `False`, `.get` trả về giá trị falsy đó thay vì nhận diện cột tồn tại |
| **Fix** | Kiểm tra tường minh: `"is_3m_inactive" in df.columns` sau đó `.fillna(False).astype(bool)` |
| **Ngày fix** | 2026-05-22 |

### B9 — Chữ trắng bóc / vô hình trong bảng HTML (`unsafe_allow_html`)
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` — bảng "Cơ cấu dư nợ theo chương trình tín dụng" |
| **Dấu hiệu** | Text trong `<td>` không nhìn thấy dù đã set `color` bằng CSS class hoặc inline style |
| **Nguyên nhân** | Streamlit dark mode inject CSS `color: var(--text-color) !important` vào table cells — thắng cả inline style thông thường do CSS cascade |
| **Fix** | Thay HTML table thủ công bằng `hien_thi_dataframe_phan_trang()` — native component tự xử lý light/dark mode |
| **Bài học** | Bảng HTML qua `st.markdown(unsafe_allow_html=True)` không an toàn với dark mode. Bảng đơn giản → dùng `hien_thi_dataframe_phan_trang`. Bảng cần màu điều kiện → set cả `background-color` per-cell (không chỉ per-row) |
| **Ngày fix** | 2026-05-23 |

### B10 — Shortcut/alert set `ws_op_nhom`/`ws_op_jump_tab` nhưng không nhảy tab
| | |
|---|---|
| **File** | `workspaces/ws_operation.py` + `alert_center.py` |
| **Dấu hiệu** | Click “Truy cập nhanh”/cảnh báo → app `st.rerun()` nhưng vẫn ở nhóm/tab cũ; `ws_op_jump_tab` bị pop mà không được dùng |
| **Nguyên nhân** | Điều hướng dùng `st.tabs()` (không control được tab active) và code chỉ `pop("ws_op_jump_tab")` rồi render toàn bộ tabs |
| **Fix** | Chuyển outer navigation sang `st.radio` + inner dùng `lazy_tabs()` (render 1 tab); jump-tab đọc one-shot từ `SCMStateManager.nav_ws_op_jump_tab` và set `st.session_state[f\"_{inner_key}_idx\"]` |
| **Ngày fix** | 2026-05-24 |

### B12 — Login header hiện thô HTML/base64 sau splash
| | |
|---|---|
| **File** | `auth.py` → `_build_login_html()` / `hien_thi_login()` |
| **Dấu hiệu** | Sau splash, màn đăng nhập hiển thị nguyên đoạn `border-radius:12px...` và chuỗi `data:image/jpeg;base64,...` thay vì card logo đăng nhập |
| **Nguyên nhân** | HTML header được đưa qua `st.markdown(..., unsafe_allow_html=True)` với các dòng `style` thụt vào; Markdown coi các dòng này là code block nên escape HTML |
| **Fix** | Compact HTML attribute về một dòng và render bằng `st.html(_build_login_html())` để không đi qua Markdown parser |
| **Ngày fix** | 2026-06-30 |

### B11 — Tab Tổng quan load lâu + không hiển thị "Thông tin tổng quát theo PGD"
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` (dòng ~530, ~573) + `services/tongquan_service.py` |
| **Dấu hiệu** | Sau phần "Cơ cấu dư nợ theo chương trình", phần "🟢 Thông tin tổng quát theo PGD" không hiển thị; app treo 8-12 giây |
| **Nguyên nhân** | (1) Dataframe gốc `df` bị trim lại dòng 573 nhưng điều kiện `if COT_TEN_PGD in df.columns:` dòng 530 cần `df` nguyên bản; (2) Hàm `tinh_tqpgd_extended()` thực hiện 5 `.merge()` liên tiếp, gây lag nặng trên DataFrame 50k rows |
| **Fix** | (1) Dòng 573: `df = df[cot_lay]` → `df_pgd_work = df[cot_lay]`; cập nhật tham chiếu dòng 574-605; (2) Gộp merge từ 5 lần → 2-3 lần trong `tinh_tqpgd_extended()`: khoanh + lãi tồn + DS cho vay tính chung 1 `.agg()` |
| **Load time** | Giảm từ 8-12s → 2-3s |
| **Ngày fix** | 2026-05-24 |

### B15 — Chữ tối/khó đọc trên dark mode trong bảng KHTD (HTML hardcode màu)
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` (header bảng CN, tiêu đề nhóm, `_md_right`, sub GQVL, hover) |
| **Dấu hiệu** | Tab "🏛️ Kế hoạch Tín dụng — Phòng KH-NV": header "NGUỒN VỐN TRUNG ƯƠNG" nền tối + chữ tối; ô số liệu/tiêu đề nhóm chữ chìm trên nền tối |
| **Nguyên nhân** | (1) Header CN dùng nền tối `#0D2137` + chữ `#1565c0` (lỗi copy, bảng PGD dùng nền sáng); (2) `<p>` tiêu đề nhóm set nền pastel sáng cố định nhưng KHÔNG set `color` → chữ kế thừa `var(--text-color)` sáng của dark mode → sáng-trên-sáng; (3) `_md_right()` default `color:#212121` (đen) cho ô số liệu trên nền theme tối |
| **Fix** | Nền cố định sáng PHẢI kèm `color` tối cố định (`#1f2937`); ô không set nền dùng `color:var(--text-color)`; hover đổi `#f8fafc` → `rgba(128,128,128,0.12)` |
| **Bài học** | Khi `st.markdown(unsafe_allow_html)` đặt nền cố định sáng thì bắt buộc đặt luôn `color` tối cố định (cặp khóa). Khi KHÔNG đặt nền → dùng `var(--text-color)`. Không bao giờ để 1 vế cố định, 1 vế theo theme. (rule 8.16) |
| **Ngày fix** | 2026-06-21 |

### B15b — Cột "Chương trình" trong bảng KHTD CN không thấy tên / tên quá chìm
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` ~dòng 58, ~381, ~475 |
| **Dấu hiệu** | Màn `📈 Kế hoạch tín dụng` → `🏛️ Kế hoạch Tín dụng Chi nhánh`: cột đầu của bảng nhập không nổi tên chương trình; user khó thấy các dòng như `Hộ nghèo`, `Hộ cận nghèo`, `Hộ mới thoát nghèo`. Ngoài ra thanh tiêu đề nhóm nền pastel sáng cũng làm chữ khó nhìn |
| **Nguyên nhân** | Cột `Chương trình` render tên dài từ `_ten_ct_base()` với style quá nhẹ (`font-size` + `padding`), không có `color`/`font-weight` rõ ràng; đồng thời thanh tiêu đề nhóm dùng nền pastel sáng nên độ tương phản tổng thể còn thấp trên một số giao diện |
| **Fix** | Thêm helper nhãn ngắn `_ten_ct_hien_thi_nhap_cn()` cho bảng nhập KHTD CN và set style cột đầu với `color:var(--text-color, inherit)` + `font-weight:600` + `line-height` rõ hơn; đổi thanh tiêu đề nhóm sang nền đậm hơn + chữ trắng đậm để tăng tương phản |
| **Ngày fix** | 2026-06-21 |

### B16b — `📋 Trạng thái Upload — 22 Đơn vị` giữ ngày cũ sau khi đã upload file mới
| | |
|---|---|
| **File** | `tabs/tab_upload_khnv/_status_board.py` |
| **Dấu hiệu** | Vừa upload file HSTD/NQ11/GQVL/CDTOTKVV mới nhưng bảng `📋 Trạng thái Upload — 22 Đơn vị` vẫn hiện badge ngày cũ; ví dụ file HSTD Hội sở đã lên ngày `23/06/2026` nhưng ô HSTD vẫn hiện `31/05/2026` |
| **Nguyên nhân** | Bảng trạng thái bị giữ snapshot cũ trong `st.session_state["trang_thai_upload_pgd"]`; khi rerun lại tab, code tái sử dụng DataFrame cũ thay vì đọc lại trạng thái mới từ đĩa. Nhánh vá cũ chỉ sửa riêng trường hợp HSTD đang là `❌`, nên các badge `✅/⚠️` cũ vẫn bị kẹt |
| **Fix** | Không cache toàn bộ bảng trạng thái trong `session_state`; mỗi lần render gọi lại `lay_trang_thai_upload_pgd(DS_DON_VI)`. Việc đọc ngày trong file vẫn được cache theo `mtime` tại `data/pgd.py`, nên vẫn hiệu quả mà badge luôn phản ánh file mới nhất |
| **Bài học** | Với bảng trạng thái runtime, chỉ cache ở tầng hàm nguồn theo `mtime`; không giữ snapshot DataFrame hoàn chỉnh trong session nếu yêu cầu UI phải cập nhật ngay sau upload |
| **Ngày fix** | 2026-06-25 |

### B16c — HSTD trạng thái vẫn hiện ngày cũ vì đọc nhầm `hstd_latest.xlsx` thay vì `hstd_khnv.xlsx` mới hơn
| | |
|---|---|
| **File** | `data/pgd.py` |
| **Dấu hiệu** | Vừa import/upload HSTD từ KH-NV cho một đơn vị nhưng bảng `📋 Trạng thái Upload — 22 Đơn vị` vẫn hiện ngày số liệu cũ; kiểm tra trên đĩa thấy cả `hstd_latest.xlsx` và `hstd_khnv.xlsx` cùng tồn tại, trong đó `hstd_khnv.xlsx` mới hơn |
| **Nguyên nhân** | `doc_trang_thai_file(loai="hstd")` chỉ fallback sang `hstd_khnv.xlsx` khi `hstd_latest.xlsx` không tồn tại. Nếu cả hai file cùng tồn tại thì hàm luôn đọc `hstd_latest.xlsx`, dù file `hstd_khnv.xlsx` vừa được KH-NV cập nhật mới hơn |
| **Fix** | Với `loai="hstd"`, chọn file có `mtime` mới hơn giữa `hstd_latest.xlsx` và `hstd_khnv.xlsx` rồi mới đọc `ngày upload` / `ngày số liệu` |
| **Bài học** | Khi một loại dữ liệu có nhiều nguồn file song song, fallback “nếu file A không tồn tại thì dùng file B” là chưa đủ; cần xác định rõ file nào là bản hiện hành, thường là file mới hơn theo `mtime` |
| **Ngày fix** | 2026-06-25 |

### B16d — Bảng Upload KH-NV hiện ngày upload vì đọc sai cột `Ngày số liệu` HSTD
| | |
|---|---|
| **File** | `data/pgd.py` → `_doc_ngay_so_lieu()` |
| **Dấu hiệu** | Bảng `📋 Trạng thái Upload — 22 Đơn vị` hiển thị ngày file được upload/lưu thay vì ngày trong HSTD; các file HSTD mới có `Ngày số liệu = 30/06/2026` nhưng badge không hiện `SL: 30/06` |
| **Nguyên nhân** | Hàm đọc ngày HSTD hardcode cột `FS`, trong khi một số file mới có thêm 1 cột và đẩy `Ngày số liệu` sang `FT`; khi đọc không ra ngày thì `_format_badge()` fallback về `ngay_upload` |
| **Fix** | Với HSTD, đọc nhanh XML của worksheet, tự tìm header `Ngày số liệu` ở dòng 5 rồi lấy ngày ở đúng cột đó; hỗ trợ cả layout cũ `FS` và layout mới `FT` |
| **Test** | `tests/test_pgd.py::TestDocNgaySoLieuHstd::test_doc_ngay_so_lieu_hstd_layout_cu_fs`, `tests/test_pgd.py::TestDocNgaySoLieuHstd::test_doc_ngay_so_lieu_hstd_layout_moi_ft` |
| **Ngày fix** | 2026-07-10 |

### B14 — Lambda params với default values khiến `lazy_tabs` truyền sai tham số
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` → `_make_renderer()` dòng ~1547 |
| **Dấu hiệu** | `TypeError: '>' not supported between instances of 'function' and 'int'` khi render phần "Hồ sơ đến hạn — Tổng hợp" |
| **Nguyên nhân** | Lambda dạng `lambda _den=den, _lbl=lbl, _key=key: ...` có `n_params=3` → `lazy_tabs` gọi `renderer(st.container())` → DeltaGenerator gán vào `_den` thay vì Timestamp; lỗi bị ẩn bởi `lazy_tabs` cũ nhưng expose sau B13 được fix |
| **Fix** | Bỏ default params khỏi lambdas: `lambda: _bang_den_han(...)` — `_make_renderer` là function riêng nên closure bắt đúng `den`/`lbl`/`key` mà không cần default params |
| **Nguyên tắc** | Default params trong lambda chỉ cần thiết khi lambda định nghĩa trong vòng lặp (tránh late binding). Khi đã bọc trong function riêng, dùng closure bình thường. |
| **Ngày fix** | 2026-06-02 |

### B13 — `lazy_tabs` nuốt TypeError của renderer → lỗi bị mask thành "missing argument: 'tab'"
| | |
|---|---|
| **File** | `utils.py` → `lazy_tabs()` dòng ~674 |
| **Dấu hiệu** | `TypeError: render.<locals>.<lambda>() missing 1 required positional argument: 'tab'` — lỗi thật bên trong lambda bị ẩn |
| **Nguyên nhân** | `try: inspect.signature(); renderer(st.container()); except (ValueError, TypeError): renderer()` — `except` bắt cả TypeError từ BÊN TRONG lambda; fallback gọi `renderer()` không có `tab` → sinh lỗi "missing argument" che khuất lỗi gốc |
| **Fix** | Tách `inspect.signature` ra ngoài try/except riêng: `try: n_params = len(inspect.signature(r).parameters); except ...: n_params = 0` → sau đó gọi `renderer(st.container())` hoặc `renderer()` bên ngoài try/except |
| **Pattern nguy hiểm** | `except TypeError: fn()` trong generic dispatch bắt lỗi từ bên trong `fn`, không chỉ từ bước setup — mọi TypeError bên trong fn đều bị nuốt và gọi lại fn theo cách sai |
| **Ngày fix** | 2026-06-02 |

### B16 — Bảng Trạng thái Upload luôn ❌ dù file đã tồn tại trên đĩa
| | |
|---|---|
| **File** | `data/pgd.py` → `doc_trang_thai_file()` dòng ~140, `_doc_ngay_so_lieu()` dòng ~104, `lay_trang_thai_upload_pgd()` dòng ~210 |
| **Dấu hiệu** | Cột HSTD (và các loại khác) trong bảng "Trạng thái Upload — 22 Đơn vị" hiển thị toàn ❌ Chưa có dù file đã upload thành công và tồn tại trên đĩa. Xảy ra nhất quán kể cả sau khi reload trang. |
| **Nguyên nhân** | `@st.cache_data` LOẠI KHỎI cache key tất cả tham số có prefix `_`. Cả `doc_trang_thai_file(…, _mtime)` lẫn `_doc_ngay_so_lieu(…, _mtime)` dùng `_mtime` với underscore → mtime KHÔNG được tính vào cache key → cache entry `(ten_dv, "hstd")` được dùng lại trong 2 giờ (TTL) dù file đã thay đổi. Ngoài ra `lay_trang_thai_upload_pgd` gọi `doc_trang_thai_file(ten_dv, "hstd")` không truyền mtime → luôn dùng cache entry cũ nhất. |
| **Fix** | Đổi `_mtime` → `mtime` (bỏ underscore) trong cả hai hàm → `mtime` được tính vào cache key. Cập nhật `lay_trang_thai_upload_pgd` tính `mtime` thực từ `os.stat()` cho từng loại file (kể cả `hstd_khnv.xlsx` cho HSTD) rồi truyền vào. Khi file chưa tồn tại: `mtime=0.0`; sau khi upload: `mtime=actual_timestamp` → cache key khác → hàm chạy lại → trả ✅. |
| **Pattern chuẩn** | Streamlit `@st.cache_data`: **KHÔNG dùng `_` prefix** cho tham số cache-busting. Underscore chỉ dùng cho object không thể hash (như DataFrame) mà bạn KHÔNG muốn bust cache. Với số (mtime), để nguyên tên → luôn nằm trong cache key. |
| **Ngày fix** | 2026-06-06 |

### B17 — Bảng tra cứu hồ sơ đổi sang `Tên tổ trưởng` nên cột bị trống
| | |
|---|---|
| **File** | `tabs/tab_tracuu_v2.py` |
| **Dấu hiệu** | Màn `🔍 Tra cứu hồ sơ khách hàng` hiện cột tổ nhưng toàn bộ dữ liệu trống dù HSTD đã upload bình thường |
| **Nguyên nhân** | Bảng kết quả bị đổi sang đọc `COT_TEN_TO_TRUONG`, trong khi HSTD thực tế đang có cột `Tên tổ` chứ không có `Tên tổ trưởng`; code fallback tạo chuỗi rỗng nên nhìn như mất dữ liệu |
| **Fix** | Đổi lại bảng tra cứu về đúng cột `COT_TEN_TO` với nhãn `Tên tổ`; bỏ fallback `Tên tổ trưởng` trong màn tra cứu |
| **Bài học** | Trước khi đổi cột hiển thị từ HSTD phải kiểm tra schema thực tế của `cache/hstd.parquet` hoặc file `hstd_khnv.xlsx`; không suy đoán rằng file đang có `Tên tổ trưởng` nếu chưa thấy header thật |
| **Ngày fix** | 2026-06-21 |

### B18 — Nút `Xuất PDF hồ sơ` trong popup tra cứu bấm không thấy phản hồi
| | |
|---|---|
| **File** | `tabs/tab_tracuu_v2.py` |
| **Dấu hiệu** | Trong popup chi tiết hồ sơ, bấm `📄 Xuất PDF hồ sơ` nhưng user không thấy thay đổi gì rõ ràng nên tưởng nút không hoạt động |
| **Nguyên nhân** | Luồng cũ lưu PDF bytes vào `st.session_state` rồi gọi `st.rerun()` ngay trong dialog. Với popup tra cứu, rerun này không tạo tín hiệu thị giác rõ ràng; nút tải PDF chỉ xuất hiện sau rerun nên dễ bị hiểu là "không có phản hồi" |
| **Fix** | Bỏ `st.rerun()`; khi bấm nút thì tạo PDF ngay trong `st.spinner()`, hiện `st.success()` sau khi tạo xong, và render luôn nút `📥 Tải PDF hồ sơ` ngay bên dưới trong cùng lần bấm |
| **Bài học** | Với export trong dialog/modal, tránh `st.rerun()` nếu không thật sự cần. Ưu tiên phản hồi tại chỗ (`spinner`, `success`, `download_button` hiện ngay) để user thấy luồng thao tác đang chạy và đã xong |
| **Ngày fix** | 2026-06-21 |

### B12 — Nút in báo cáo không phản hồi / app treo (unconditional generation)
| | |
|---|---|
| **File** | `workspaces/ws_executive.py` — `_render_pdf_section` (PDF×2), `_render_suc_khoe_theo_pgd` (Excel×2), `_render_radar_so_sanh` (Excel×1), `_render_xep_hang_pgd` (Excel×1); `workspaces/ws_operation.py` — `_render_bao_cao_giao_ban` (~dòng 1293), `_render_heatmap_dao_han` (~dòng 1759); `tabs/tab_baocao/components/export_panel.py` |
| **Dấu hiệu** | Bấm nút "Xuất Excel" / "Xuất PDF" không có phản hồi; app treo vài giây hoặc crash âm thầm khi dependency lỗi |
| **Nguyên nhân** | `st.download_button(data=xuat_excel_chuyen_nghiep(...))` / `download_pdf_button(pdf_bytes=xuat_pdf_co_chart(...))` gọi hàm tạo file **mỗi lần Streamlit rerun** — kể cả khi user chưa bấm nút. Nếu hàm export throw exception → crash thầm lặng (không có try/except). |
| **Fix** | Tách 2 bước: (1) Button "Tạo file" → gọi hàm → lưu bytes vào `st.session_state`; (2) `st.download_button(data=st.session_state[...])` chỉ render khi bytes đã có. Thêm `try/except` + `logger.error()` + `st.error()` quanh bước tạo file. |
| **Pattern chuẩn** | `if st.button("Tạo"): st.session_state["_key"] = gen_bytes()` → `if st.session_state.get("_key"): st.download_button(data=st.session_state["_key"])` |
| **Ngày fix** | 2026-06-02 (ws_operation bản đầu); 2026-06-09 (ws_executive.py — 6 buttons PDF+Excel; tabs/ — tab_ban_dai_dien, tab_den_han, tab_don_doc_khd, tab_khtd_giao_dc, tab_phan_tich_pgd; ws_operation.py — 3 instances L1172, L4051, L5168) |
| **Còn lại** | `tabs/tab_khtd_nhap.py:L244` — template tĩnh nhỏ, bỏ qua (low risk); tất cả instance khác đã fix |

### B19 — Telegram Bot chỉ hiện lỗi HTTP 400 bị cắt cụt `Bad Re...`
| | |
|---|---|
| **File** | `services/telegram_service.py`, `tabs/tab_telegram_admin.py` |
| **Dấu hiệu** | Màn `🤖 Quản trị Telegram Bot` báo lỗi kiểu `❌ HTTP 400: {"ok":false,...,"description":"Bad Re...` nên không biết là sai `Chat ID`, `Token` hay lỗi parse HTML |
| **Nguyên nhân** | `gui_tin()` chỉ trả `bool`, còn lỗi HTTP bị cắt ngắn bằng `r.text[:100]`; tab admin lại chỉ hiện chung chung `Gửi thất bại — kiểm tra Token và Chat ID.` nên che mất nguyên nhân thật từ Telegram |
| **Fix** | Tách core sender trả `(ok, err)`, bóc `description` từ JSON Telegram để hiện đúng lỗi thực; nút test hiển thị lỗi chi tiết và tự fallback gửi plain text nếu lỗi do `parse_mode=HTML`; bảng lịch sử tăng độ dài chuỗi lỗi hiển thị |
| **Ngày fix** | 2026-06-30 |

### B20 — Telegram Admin test nhầm config cũ, `Gửi ngay` báo sai lỗi
| | |
|---|---|
| **File** | `services/telegram_service.py`, `tabs/tab_telegram_admin.py` |
| **Dấu hiệu** | Bấm `🧪 Test kết nối` sau khi sửa Token/Chat ID nhưng chưa lưu vẫn test cấu hình cũ; bấm `▶ Gửi ngay` thất bại nhưng toast lại hiện chuỗi kiểu `22/22 PGD`, `(Test thủ công)` hoặc số lượng nghiệp vụ thay vì lỗi Telegram thật |
| **Nguyên nhân** | Nút test gọi hàm đọc config từ `kv_store`, không dùng giá trị đang nhập trên form; `_gui_ngay()` trả `(ok, info nghiệp vụ)` nên UI dùng sai chuỗi ở nhánh fail; các nhánh batch `phan_ky_nxh` và `deadline_bc` còn có thể nuốt lỗi từng lượt gửi |
| **Fix** | Thêm sender chi tiết nhận `token/chat_id` trực tiếp cho admin test; thêm helper đọc lỗi log gần nhất theo `notify_key` để chuẩn hóa toast lỗi; refactor nhánh batch đếm `sent/failed` và trả lỗi đầu tiên; `gui_tin_pgd()` dùng chung `_gui_tin_core()` để log lỗi không bị cắt cụt |
| **Ngày fix** | 2026-07-01 |

### B21 — Telegram `nhap_lieu` chạy ngầm nhưng không quản trị được từ tab Admin
| | |
|---|---|
| **File** | `tabs/tab_telegram_admin.py`, `scripts/nhac_deadline.py`, `scripts/telegram_polling.py`, `services/telegram_service.py` |
| **Dấu hiệu** | Script `nhac_deadline.py` vẫn gửi nhắc nhập liệu theo key `nhap_lieu`, nhưng tab `🤖 Quản trị Telegram Bot` không có toggle/chat phụ/`Gửi ngay` cho loại này; bot polling 2 chiều cũng dùng sender riêng nên khi Telegram từ chối phản hồi lệnh thì khó biết lỗi thật |
| **Nguyên nhân** | `nhap_lieu` chỉ tồn tại trong script scheduler, không được khai báo trong `_NOTIFY_META`; sender trong `telegram_polling.py` gọi `requests.post` trực tiếp và chỉ trả `bool`, không tái dùng helper đã chuẩn hóa lỗi Telegram |
| **Fix** | Thêm `nhap_lieu` vào metadata quản trị + giờ Task Scheduler + nhánh `▶ Gửi ngay`; đổi `_nhac_theo_doi_nhap_lieu()` sang trả trạng thái chi tiết và gửi theo `notify_key='nhap_lieu'`; refactor polling bot dùng sender chuẩn hóa lỗi từ `telegram_service.py` |
| **Ngày fix** | 2026-07-01 |

### B22 — Telegram Admin crash khi allowlist deadline chứa loại báo cáo stale
| | |
|---|---|
| **File** | `tabs/tab_telegram_admin.py` → expander `🧾 Nhắc nộp báo cáo`, `_gui_ngay("deadline_bc")` |
| **Dấu hiệu** | Mở tab `🤖 Quản trị Telegram Bot` có thể crash ở `st.multiselect`, hoặc `▶ Gửi ngay` báo số loại lọc sai, sau khi một loại báo cáo trong `bao_cao_deadline_config` đã bị xóa/đổi tên nhưng vẫn còn trong kv key `telegram_deadline_bc_allowlist` |
| **Nguyên nhân** | `st.multiselect` yêu cầu `default` phải là tập con của `options`. Code dùng thẳng allowlist đã lưu làm `default`, nên state stale từ kv_store không còn khớp danh mục deadline hiện tại |
| **Fix** | Chuẩn hóa allowlist trước khi render/gửi: chỉ giữ các loại còn tồn tại trong `deadline_cfg`, cảnh báo số loại stale bị loại bỏ, và khi user bấm lưu thì chỉ persist danh sách đã được làm sạch |
| **Ngày fix** | 2026-07-01 |

### B22a — Telegram: Upload PGD không gửi vào chat PGD dù đã cấu hình
| | |
|---|---|
| **File** | `services/telegram_service.py`, `tabs/tab_telegram_admin.py` |
| **Dấu hiệu** | Đã cấu hình `Chat ID riêng từng PGD` nhưng tin `📤 PGD upload file` vẫn chỉ gửi vào chat chính (hoặc chat phụ `upload_pgd`), không đi vào group của PGD |
| **Nguyên nhân** | `gui_thong_bao_upload_pgd()` dùng `_gui_tin_for(..., notify_key='upload_pgd')` nên bỏ qua routing `pgd_chats[slug]` |
| **Fix** | Đổi `gui_thong_bao_upload_pgd()` dùng `gui_tin_pgd(..., notify_key='upload_pgd')` để ưu tiên chat PGD; log vẫn theo `upload_pgd` để tab admin hiển thị lỗi đúng loại thông báo |
| **Ngày fix** | 2026-07-14 |

### B23 — Báo cáo tín dụng `🔴 CDTOTKVV` báo trống dù đã upload
| | |
|---|---|
| **File** | `tabs/tab_baocao/__init__.py` |
| **Dấu hiệu** | Vào `📊 Báo cáo tín dụng` thấy card/report `🔴 CDTOTKVV` báo `⚠️ Chưa có dữ liệu CDTOTKVV.` dù tab `🏘️ Mạng lưới Tổ TK&VV` hoặc trạng thái upload cho thấy file đã tồn tại |
| **Nguyên nhân** | `tab_baocao` chỉ đọc `df_cdtotkvv` từ `kwargs`, nhưng `app.py`/workspace hiện không nạp và không truyền context này; kết quả là riêng màn Báo cáo tín dụng luôn nhận `None` và hiển thị trống |
| **Fix** | Thêm fallback ngay trong `tab_baocao`: nếu `df_cdtotkvv` chưa được truyền thì tự gọi `load_cdto_toan_cn()` để nạp từ `pgd_data/*/cdtotkvv_*.xlsx` hoặc `cdtotkvv_latest.xlsx`; PGD mode lọc tiếp theo `pgd_user` |
| **Ngày fix** | 2026-06-30 |

### B24 — Mục “Chọn loại báo cáo để sửa / xóa” gây hiểu nhầm, nút xóa khó thấy
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py` → `_render_cai_dat()` |
| **Dấu hiệu** | Trong `📋 Tiến độ Báo cáo của PGD → ⚙️ Cài đặt thời hạn`, người dùng khó phân biệt giữa xóa dữ liệu báo cáo đã nộp và xóa cấu hình deadline; nút xóa bị ẩn trong `popover`, danh sách chọn lại trộn cả loại đã cài deadline với loại chỉ mới xuất hiện từ Google Form nên giao diện rối và khó thao tác |
| **Nguyên nhân** | UI đang dùng chung một `selectbox` cho toàn bộ `set(GSheet ∪ deadline_cfg)` và label `sửa / xóa` quá chung; hành động xóa chỉ hiện khi đã mở `popover`, không đủ nổi bật cho thao tác “ngừng theo dõi” |
| **Fix** | Tách rõ 2 nhóm: loại đã cài deadline và loại chưa cài; chỉ cho sửa/xóa trên nhóm đang theo dõi; đổi wording thành “ngừng theo dõi” để tránh hiểu nhầm; đưa nút `🗑 Xóa khỏi danh sách theo dõi` ra hiển thị trực tiếp kèm checkbox xác nhận; đồng thời thêm khối cài nhanh deadline cho các loại đã xuất hiện từ Google Form nhưng chưa theo dõi |
| **Ngày fix** | 2026-06-30 |

---

## C. Dữ liệu / DataFrame

### C7 — Cột "Thời hạn vay" luôn trả "—" trong card tra cứu
| | |
|---|---|
| **File** | `data/core.py`, `components/result_card.py` |
| **Dấu hiệu** | `⏱️ — tháng` trong tất cả thẻ kết quả tra cứu |
| **Nguyên nhân** | Excel BCQUERY lưu header cell có ký tự xuống dòng: `"Thời hạn\nvay"`. `excel_to_parquet()` không normalize → cột trong parquet là `"Thời hạn\nvay"` thay vì `"Thời hạn vay"`. `hs.get(COT_THOI_HAN)` trả `None` |
| **Fix** | `excel_to_parquet()`: normalize `\n`/`\r` → space khi ghi VÀ khi đọc parquet (để xử lý cả cache cũ). Áp dụng toàn bộ file (HSTD, NQ11, baseline...) |
| **Ngày fix** | 2026-06-12 |

### C1 — Metric hiển thị sai (vd: 0,013 thay vì 13,199 tỷ)
| | |
|---|---|
| **Nguyên nhân** | Dùng `/1e9` thay vì `/1e12` cho giá trị lưu VND |
| **Quy ước** | Lưu VND → hiển thị tỷ: chia `/1_000_000` ra triệu, dùng `fmt_ty()`. **Không dùng `/1e9` hay `/1e12` trực tiếp** |
| **Fix** | `fmt_ty(gia_tri_vnd)` — hàm tự xử lý đơn vị |

### C2 — TH = 0 toàn bộ
| | |
|---|---|
| **Kiểm tra theo thứ tự** | 1. HSTD đã upload chưa? 2. Cột `Tổng dư nợ` có không? (`COT_TONG_DU_NO`) 3. Merge đã chạy? (`merge_meta_hstd` trong kv_store) 4. Cache cũ? `st.cache_data.clear()` |

### C3 — Số liệu xã bị lệch / không khớp
| | |
|---|---|
| **Nguyên nhân** | Tên xã trong HSTD khác với `PGD_XA_MAP` trong `config.py` |
| **Debug** | `print(PGD_XA_MAP["PGD Long Thành"])` → so với cột `Tên xã` thực tế trong file HSTD |

### C4 — `th_cn` bị lệch ~8 tỷ
| | |
|---|---|
| **Nguyên nhân** | Thiếu key nguồn vốn ĐP trong `CHUONG_TRINH_KHTD` |
| **Kiểm tra** | 4 key phải có: `9_DP`, `12_DP`, `17_DP`, `26_DP` trong `config.py` |

### C5 — `TypeError: unsupported operand type(s) for /: 'str' and 'int'`
| | |
|---|---|
| **File** | `tab_ban_dai_dien.py`, bất kỳ tab nào chia cột tiền tệ |
| **Nguyên nhân** | Cột số bị đọc thành string (ArrowDtype hoặc object) |
| **Fix** | Thêm helper: `_num = lambda v: pd.to_numeric(v, errors='coerce')` trước khi chia |

### C6 — Tên cột không tìm thấy / `KeyError`
| | |
|---|---|
| **Nguyên nhân** | Hardcode tên cột thay vì dùng constant từ `config.py` |
| **Fix** | Dùng `COT_*` từ config. Alias hay nhầm: `COT_DIEN_THOAI` → `COT_SDT`; `COT_TEN_TKVV` → `COT_TEN_TO`; `"PL NV"` → `COT_PL_NV` |

### C7 — `category type does not support sum operations`
| | |
|---|---|
| **Dấu hiệu** | `ValueError: category type does not support sum operations` khi groupby/sum |
| **File** | Bất kỳ tab nào merge dữ liệu từ parquet — đặc biệt `tab_tongquan.py`, `tab_no_khoanh.py` |
| **Nguyên nhân** | Cột số bị lưu thành categorical dtype trong parquet do mixed type hoặc merge schema không đồng nhất |
| **Fix** | Ép toàn bộ cột tiền tệ về numeric: `df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)`. Nếu vẫn lỗi: `.astype(object)` rồi mới `pd.to_numeric()` |
| **Ngày fix** | 2026-05-20 |

### C8 — `cannot subtract DatetimeArray from Categorical`
| | |
|---|---|
| **Dấu hiệu** | `TypeError: cannot subtract DatetimeArray from Categorical` khi tính số ngày đến hạn |
| **File** | Tab Sức khỏe tín dụng, bất kỳ tab nào tính `ngay_dh - ngay_hien_tai` |
| **Nguyên nhân** | Cột ngày bị parquet lưu thành categorical thay vì datetime |
| **Fix** | Ép về datetime trước khi tính: `pd.to_datetime(df[col], dayfirst=True, errors='coerce')` |
| **Ngày fix** | 2026-05-20 |

### C9 — `ufunc 'subtract' did not contain a loop with signature matching types (dtype('<U516818'), dtype('int64'))`
| | |
|---|---|
| **Dấu hiệu** | Tab So sánh kỳ → Kỳ hiện tại → 5 chỗ crash khi subtract: "🏢 Theo PGD", "📋 Theo CT", "📍 Theo Xã", export sheet, _render_top_bien_dong; `TypeError: ufunc 'subtract' did not contain a loop with signature...` |
| **File** | `tabs/tab_so_sanh_ky/render_moc_nam.py` & `render_2_ky.py` |
| **Nguyên nhân** | `pd.merge(..., suffixes=...).fillna(0)` sau merge 2 DataFrame **không** convert về numeric. Khi trừ, numpy nhận thấy column là string (dtype `<U516818>`) và int64 → crash |
| **Pattern** | `fillna(0)` giữ nguyên dtype object/string của column. Chỉ replace NaN → 0 text. Nếu merge tạo ra mixed-type column thì `fillna` không rescue. |
| **Fix** | Sau `fillna(0)`, loop và **explicit `pd.to_numeric()`** trước khi tính toán: `for col in [...]: if col in merged.columns: merged[col] = pd.to_numeric(merged[col], errors='coerce').fillna(0)` |
| **Đã fix** | (1) `render_2_ky.py` dòng 150-153: `_render_bang_pgd()` (2) `render_moc_nam.py` dòng 303-306: Tab "🏢 Theo PGD" (3) dòng 352-355: Tab "📋 Theo CT" (4) dòng 376-379: Tab "📍 Theo Xã" (5) dòng 494-497: Export PGD sheet (6) dòng 99-101: `_render_top_bien_dong()` |
| **Ngày fix** | 2026-05-24 |

### C9 — `UnicodeEncodeError: surrogates not allowed` trong emoji
| | |
|---|---|
| **Dấu hiệu** | `UnicodeEncodeError: 'utf-8' codec can't encode characters ... surrogates not allowed` |
| **File** | Tab Cảnh báo NQH, bất kỳ tab nào dùng emoji trong markdown |
| **Nguyên nhân** | Một số ký tự emoji chứa surrogate pair không hợp lệ với UTF-8 strict mode |
| **Fix** | `.encode('utf-8', errors='replace').decode('utf-8')` hoặc thay emoji surrogate bằng emoji an toàn |
| **Ngày fix** | 2026-05-17 |

### C12 — `canh_bao_tap_trung()` tính tỷ lệ % đến hạn sai (mẫu số bị thu nhỏ)
| | |
|---|---|
| **File** | `data/den_han.py` → `canh_bao_tap_trung()`, `tabs/tab_den_han.py` ~dòng 159 |
| **Dấu hiệu** | Cảnh báo ⚠️ hiện tỷ lệ ~48% (PGD Cẩm Mỹ, Trảng Bom...) thay vì ~10-15% thực tế |
| **Nguyên nhân** | `tab_den_han.py` gọi `canh_bao_tap_trung(df_loc)` với `df_loc` đã bị lọc chỉ còn khoản đến hạn ≤N tháng. Bên trong hàm, `tong_pgd = df.groupby(PGD)[TONG_DU_NO].sum()` tính trên chính `df_loc` đó → mẫu số = tổng đến hạn ≤N tháng (không phải tổng dư nợ PGD). Kết quả: `ty_le = dư_nợ_1_tháng / dư_nợ_≤6_tháng` thay vì `/ tổng_dư_nợ_PGD` |
| **Fix** | (1) Tạo `df_tinh_filtered` = `df_tinh` sau filter PGD/CT/ĐVUT nhưng **không** lọc tháng; (2) Truyền `df_tinh_filtered` vào `canh_bao_tap_trung()`; (3) Thêm `den_thang` param vào hàm để group theo toàn khoảng thay vì từng tháng riêng |
| **Pattern tránh** | Không truyền DataFrame đã lọc thời gian vào hàm cần tính tỷ lệ trên tổng — luôn dùng dataset gốc (chỉ lọc dimension, không lọc metric) làm mẫu số |
| **Ngày fix** | 2026-05-23 |

### C10 — DataFrame/Series rỗng gây crash
| | |
|---|---|
| **Dấu hiệu** | `KeyError`, `IndexError`, hoặc `AttributeError` khi xử lý DataFrame rỗng |
| **File** | `data/cdtotkvv.py` ~dòng 95, `data/den_han.py` ~dòng 81, `tabs/tab_kehoach.py` ~dòng 225 |
| **Nguyên nhân** | Không guard `df.empty` trước khi gán cột hoặc truy cập column |
| **Fix** | Thêm `if df.empty: return df` (hoặc `return None`) ở đầu hàm xử lý |
| **Ngày fix** | 2026-05-21 |

### C11 — `UnboundLocalError` do Python 3.14 `except Exception:` syntax
| | |
|---|---|
| **Dấu hiệu** | `UnboundLocalError: cannot access local variable 'e' where it is not associated with a value` |
| **File** | `tabs/tab_tongquan.py`, bất kỳ file nào có `except Exception: logger.error("...%s", e)` |
| **Nguyên nhân** | Python 3.14: `except Exception:` (không `as e`) tự động unbind biến `e` khỏi scope ngoài. Dùng `e` trong block except gây UnboundLocalError |
| **Fix** | Luôn dùng `except Exception as e:` — không bao giờ `except Exception:` |
| **Ngày fix** | 2026-05-21 |

### C8 — Nguồn vốn TW/ĐP = 0 trong Báo cáo KHNV
| | |
|---|---|
| **File** | `services/khnv_bao_cao_service.py` dòng ~88 |
| **Dấu hiệu** | `nguon_von_tw = 0`, `nguon_von_dp = 0` trong tab Báo cáo KHNV mode HSTD |
| **Nguyên nhân** | Excel lưu Nguồn vốn là số float → đọc vào parquet là `'1.0'`, `'2.0'`. Service dùng `.isin(["1", "TW"])` và `.isin(["2", "ĐP"])` → không khớp vì `'1.0' ≠ '1'` |
| **Fix** | Chuẩn hoá: `pd.to_numeric(..., errors='coerce').fillna(-1).astype(int).astype(str)` rồi mới isin() |
| **Ngày fix** | 2026-07-19 |

### C10 — Số KH Báo cáo KHNV tính nhầm vì Tên KH trùng lặp
| | |
|---|---|
| **File** | `services/khnv_bao_cao_service.py` dòng ~81 |
| **Dấu hiệu** | Số KH = 109.372 thay vì ~214.120 |
| **Nguyên nhân** | `Tên KH.nunique()` không phân biệt được nhiều người cùng tên. Trong data có 12.721 tên có từ 3+ Mã KH khác nhau — rõ ràng là các người khác nhau. Mỗi Mã KH ↔ 1 Số CMND (1-to-1) nên Mã KH là định danh đúng. |
| **Fix** | Đổi sang `Mã KH.nunique()` với filter active (dư nợ > 0) trên df được truyền vào, để đếm đúng KH còn dư nợ dù df_full hay df_active được dùng |
| **Ngày fix** | 2026-07-19 |

### C9 — Số KH và Giải ngân tháng trong Báo cáo KHNV thấp hơn thực tế
| | |
|---|---|
| **File** | `app.py` dòng ~1259-1313 |
| **Dấu hiệu** | Số KH = 109.372 thay vì 123.963; Giải ngân = 459,05 tỷ thay vì 459,93 tỷ |
| **Nguyên nhân** | `df_full` được load với `active_only=True` → bỏ 73K hồ sơ đã tất toán (dư nợ=0). Trong số đó có 14.591 KH unique và 12 hồ sơ có giải ngân tháng 0,88 tỷ |
| **Fix** | Tách `df_full = _load_hstd(..., active_only=False)` và `df = _load_hstd(..., active_only=True)`. Bỏ dòng `df = df_full` cho management/executive workspace để `df` (tìm kiếm) vẫn là active_only |
| **Ngày fix** | 2026-07-19 |

---

## D. Database / kv_store

### D1 — `database is locked`
| | |
|---|---|
| **Nguyên nhân** | Nhiều process Streamlit cùng ghi SQLite |
| **Fix** | Chỉ chạy 1 instance. Hoặc tăng timeout: `PRAGMA busy_timeout = 5000` trong `db.py` |

### D2 — Key kv_store trả về `None` bất ngờ
| | |
|---|---|
| **Debug** | `sqlite3 data.db "SELECT key, updated_at FROM kv_store"` → kiểm tra key có tồn tại không |
| **Nguyên nhân thường gặp** | Ghi với key sai (slug PGD sai, thiếu prefix) hoặc chưa bao giờ ghi |

### D3 — Thao tác ghi thành công nhưng không thấy trong audit log
| | |
|---|---|
| **Nguyên nhân** | Quên gọi `db.ghi_audit()` sau `db.ghi_kv()` |
| **Fix** | Bắt buộc pattern: `db.ghi_kv(key, val, username)` → ngay tiếp theo `db.ghi_audit(username, action, detail)` |

### D4 — SQLite thread-safety: ghi audit trong ThreadPoolExecutor crash
| | |
|---|---|
| **Dấu hiệu** | `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` |
| **File** | `tabs/tab_upload_khnv.py` — import hàng loạt KH-NV |
| **Nguyên nhân** | `db.ghi_audit()` được gọi từ worker thread trong `ThreadPoolExecutor` |
| **Fix** | Gom audit records vào list ở worker thread, ghi tuần tự ở main thread sau khi executor hoàn tất |
| **Ngày fix** | 2026-05-21 |

### D5 — `no such column: X` — schema mismatch
| | |
|---|---|
| **Dấu hiệu** | `sqlite3.OperationalError: no such column: ten_task` / `ngay_doi_mk` / `ngay_kiem_tra` |
| **Nguyên nhân** | Một trong hai: (1) Query dùng sai tên cột không khớp schema thực tế trong `db.py`; (2) Migration chưa chạy để thêm cột mới |
| **Fix** | Kiểm tra `db.py` để lấy tên cột chính xác từ `CREATE TABLE`. Nếu cần cột mới → thêm migration trong `db.py` |
| **Ngày fix** | 2026-05-19/22 |

### D6 — `ngay_doi_mk` không có trong schema → log ERROR liên tục
| | |
|---|---|
| **File** | `tabs/tab_trang_thai_nguon.py` → `_render_nguoi_dung()` ~dòng 528, `db.py` → `init_db()` |
| **Dấu hiệu** | Log: `sqlite3.OperationalError: no such column: ngay_doi_mk` mỗi lần mở tab "Người dùng" |
| **Nguyên nhân** | Cột `ngay_doi_mk` được query nhưng chưa có trong CREATE TABLE users và chưa có ALTER TABLE migration. Khi pull code về máy khác (DB tạo mới), cột không tồn tại → lỗi. |
| **Fix** | (1) Thêm `ngay_doi_mk TEXT` vào CREATE TABLE users; (2) Thêm `ALTER TABLE users ADD COLUMN ngay_doi_mk TEXT` migration vào `init_db()`; (3) Hạ log level ERROR → WARNING trong catch block |
| **Ngày fix** | 2026-05-22 |

---

## E. Upload / Merge

### E1 — Upload thành công nhưng dữ liệu không cập nhật
| | |
|---|---|
| **Nguyên nhân** | Quên `st.cache_data.clear()` sau khi lưu file |
| **Fix** | Sau mọi upload thành công: `st.cache_data.clear()` + gọi `merge_du_lieu_toan_cn(loai)` nếu là file hệ thống |

### E2 — Merge báo lỗi 1 PGD cụ thể
| | |
|---|---|
| **Debug** | `sqlite3 data.db "SELECT * FROM audit_log WHERE action LIKE '%merge%' ORDER BY created_at DESC LIMIT 10"` |
| **Nguyên nhân thường gặp** | File PGD lỗi format hoặc thiếu cột bắt buộc |
| **Fix** | Upload lại file PGD đó. Kiểm tra file có đúng sheet name và header row không |

### E3 — `luu_pgd_file()` trả về `KetQuaUpload(thanh_cong=False, "Thiếu cột bắt buộc: Số khế ước, Mã KH...")`
| | |
|---|---|
| **File** | `services/upload_service.py` dòng ~1036 |
| **Dấu hiệu** | Tất cả cột required đều báo missing dù file có đủ cột |
| **Nguyên nhân** | Validation đọc Excel bằng `pd.read_excel(file)` mặc định (header=0), trong khi HSTD có header ở row 4 → cột đọc ra là số nguyên, không phải tên cột thật |
| **Fix** | Dùng `sheet_name="BCQUERY", header=4` cho hstd/nq11; `sheet_name="Sheet1", header=7` cho gqvl + `df.iloc[:, 1:]` |
| **Ngày fix** | 2026-06-11 |

### E3 — File upload xong nhưng mất sau restart
| | |
|---|---|
| **Nguyên nhân** | Lưu vào `/tmp` hoặc RAM thay vì disk |
| **Kiểm tra** | `UPLOAD_DIR` trong `config.py` phải trỏ thư mục persistent, không phải `/tmp` |

### E4 — Merge chậm / treo (>10s)
| | |
|---|---|
| **File** | `services/upload_service.py` ~dòng 484 |
| **Nguyên nhân** | String cleanup chạy trên tất cả cột thay vì chỉ cột object |
| **Fix** | Chỉ cleanup cột `dtype == object`: `obj_cols = df.select_dtypes(include='object').columns` |

### E5 — "Nguồn vốn" toàn NaN sau merge GQVL
| | |
|---|---|
| **Dấu hiệu** | Cột `COT_NGUON_VON` = NaN trên toàn bộ dòng sau merge GQVL |
| **File** | `services/upload_service.py` ~dòng 462 |
| **Nguyên nhân** | Cột "Nguồn vốn" (text "TW"/"ĐP") bị đưa vào danh sách `_cols_so_cn` → bị ép `pd.to_numeric()` → NaN |
| **Fix** | Loại "Nguồn vốn" khỏi `_cols_so_cn` — đây là cột text, không phải cột số |
| **Ngày fix** | 2026-05-16 |

### E6 — `file_uploader` không reset sau import hàng loạt
| | |
|---|---|
| **Dấu hiệu** | Upload file lần 2 cùng tên → không kích hoạt import |
| **File** | `tabs/tab_upload_khnv.py` ~dòng 707 |
| **Nguyên nhân** | Streamlit `file_uploader` giữ state cũ, không detect file mới cùng tên |
| **Fix** | Dùng version counter trong key: `key=f"upload_{_ver}"` → tăng `_ver` sau mỗi lần import thành công để widget reset |
| **Ngày fix** | 2026-05-17 |

### E7 — "Upload nhầm đơn vị" sai khi upload HSTD Hội sở CN
| | |
|---|---|
| **Dấu hiệu** | Upload HSTD cho "Hội sở Chi nhánh tỉnh" bị báo lỗi: "File chứa: Hội sở CN Đồng Nai \| Đang chọn: Hội sở Chi nhánh tỉnh" |
| **File** | `tabs/tab_upload_pgd.py` hàm `_kiem_tra_don_vi()` |
| **Nguyên nhân** | Hàm `chuan_hoa_ten()` dùng regex xóa luôn các từ "hội/sở/chi/nhánh/tỉnh" → tên Hội sở bị biến thành chuỗi rỗng, không bao giờ khớp. Ngoài ra thiếu bảng alias "Hội sở CN Đồng Nai" → `DON_VI_CHI_NHANH` |
| **Fix** | Thêm `_TEN_DV_ALIAS` (giống `TEN_DV_ALIAS` trong `file_detection_service.py`); áp alias trước khi so sánh; xóa regex sai |
| **Ngày fix** | 2026-06-01 |

### E9 — NQ11 upload nhưng không trigger merge
| | |
|---|---|
| **File** | `tabs/tab_upload_khnv/_upload_toan_cn.py` → `render_nq11_toan_cn()` |
| **Dấu hiệu** | Upload danh sách mã KU NQ11 thành công nhưng HSTD không có nhãn NQ11 mới |
| **Nguyên nhân** | `_render_nq11_toan_cn()` cũ chỉ lưu danh sách mã KU, không gọi merge HSTD. CDTO và GQVL đều merge sau upload nhưng NQ11 thì không |
| **Fix** | Thêm `them_vao_hang_cho("nq11")` sau khi lưu thành công — merge sẽ được thực hiện khi user bấm "Merge toàn CN" ở tab Tổng quan |
| **Ngày fix** | 2026-06-12 |

### E10 — Kết quả merge hiển thị 2 lần sau import hàng loạt
| | |
|---|---|
| **File** | `tabs/tab_upload_khnv/` (đã fix trong tái cấu trúc) |
| **Dấu hiệu** | Sau import hàng loạt, kết quả merge hiện trong spinner VÀ sau rerun qua `folder_import_ket_qua_merge` session state |
| **Nguyên nhân** | `_xu_ly_upload()` ghi `ket_qua_merge` vào session state, sau rerun `render()` pop và hiện lại. Cả 2 cùng hiện trước và sau `st.rerun()` |
| **Fix** | Trong architecture batch merge mới: `_xu_ly_upload()` không merge ngay → không có `ket_qua_merge`. Kết quả merge hiện duy nhất trong `_merge_panel.py` |
| **Ngày fix** | 2026-06-12 |

### E11 — "Tổng quan danh mục" hiển thị ít dữ liệu hơn sau upload 22 PGD
| | |
|---|---|
| **File** | `services/upload_service.py` ~dòng 74; `data/hstd.py` ~dòng 17 |
| **Dấu hiệu** | Upload đủ 22 PGD + Hội sở, parquet hstd chỉ có ~36,350 dòng (2 PGD) thay vì ~359,000 dòng (22 PGD). Tab Tổng quan danh mục tín dụng hiển thị dữ liệu ít hơn thực tế |
| **Nguyên nhân** | 2 bug kết hợp: (1) `FILES_HE_THONG[TEN_FILE]` có `"cache": CACHE_HSTD` → `luu_file_he_thong()` gọi `os.remove(CACHE_HSTD)` khi upload file hệ thống cũ → xóa parquet merged 22 PGD. (2) `doc_file()` trong `data/hstd.py` gọi `excel_to_parquet(FILE_PATH, CACHE_HSTD, ...)` → rebuild CACHE_HSTD từ file đơn lẻ (chỉ 2 PGD: Trảng Bom + Long Thành). Kết quả: CACHE_HSTD bị ghi đè bằng dữ liệu 2 PGD thay vì 22 PGD |
| **Fix** | (1) Xóa `"cache"` khỏi `FILES_HE_THONG[TEN_FILE]` — file hệ thống cũ không được xóa/ghi CACHE_HSTD. (2) `doc_file()` cache vào `fp_pq = fp.with_suffix(".parquet")` (cùng thư mục với Excel) thay vì `CACHE_HSTD` |
| **Khắc phục tức thời** | Vào tab Upload HSTD → bấm Merge để rebuild parquet từ 22 file khnv đã upload |
| **Ngày fix** | 2026-06-20 |

### E8 — "Toàn cảnh 22 PGD" cột Upload HSTD luôn ❌ dù đã upload
| | |
|---|---|
| **File** | `tabs/tab_pgd_cards.py` → `_upload_info()`, `_render_ranking_table()`, `render()` |
| **Dấu hiệu** | Bảng xếp hạng tổng hợp / Toàn cảnh 22 PGD cột "Upload HSTD" hiển thị ❌ Thiếu dù Phòng KH-NV đã upload qua tab Upload KHNV |
| **Nguyên nhân** | KH-NV upload HSTD lưu vào `hstd_khnv.xlsx` (riêng Phòng KH-NV), nhưng `_upload_info()` chỉ kiểm tra `hstd_latest.xlsx` (đường dẫn của PGD tự upload). Tương tự, KPI "File HSTD" và bộ lọc upload cũng chỉ check `hstd_latest.xlsx` |
| **Fix** | Thêm `_pgd_khnv_path()` kiểm tra `hstd_khnv.xlsx`; `_upload_info()` check cả 2 file lấy timestamp mới nhất; `n_upload` và `upload_status` check cả 2 đường dẫn |
| **Ngày fix** | 2026-06-06 |

### E9 — CDTOTKVV gắn nhầm tháng (tháng 4 vs tháng 5) giữa 2 luồng upload
| | |
|---|---|
| **File** | `services/upload_service.py` ~dòng 428, `tabs/tab_upload_khnv/_upload_toan_cn.py` ~dòng 60, `tabs/tab_upload_khnv.py` ~dòng 553 |
| **Dấu hiệu** | Card "Xếp loại Tổ TK&VV toàn Chi nhánh" hiển thị tháng không nhất quán: luồng 22 PGD tự upload gắn tháng 4 (ngày chốt 30/4), luồng upload 1 file tổng có thể gắn tháng 5 (đọc tiêu đề/ngày xuất). Cùng kỳ chấm điểm nhưng bị tách thành 2 tháng → card chọn tháng mới nhất và báo "thiếu PGD" |
| **Nguyên nhân** | Luồng file tổng ưu tiên `doc_thang_nam_tu_file()` (đọc header/tiêu đề — có thể là kỳ báo cáo / ngày xuất tháng 5), chỉ fallback sang `doc_thang_tu_cdto_toan_cn()` (đọc NGAYBC cột S = ngày chốt số liệu = tháng 4). Luồng PGD tự upload lại đọc ngày chốt trong thân file → lệch tháng |
| **Fix** | Đảo thứ tự ở cả 3 nơi: `doc_thang_tu_cdto_toan_cn(file_bytes) or doc_thang_nam_tu_file(file_bytes)` → thống nhất gắn tháng theo NGÀY CHỐT SỐ LIỆU (NGAYBC), khớp với luồng PGD tự upload |
| **Ngày fix** | 2026-06-21 |

### E10 — CDTOTKVV hiển thị `22/21 PGD` do lẫn Hội sở với mẫu số 21 PGD
| | |
|---|---|
| **File** | `services/tongquan_cdto_service.py`, `tabs/tab_tongquan.py`, `tabs/tab_cdtotkvv.py` |
| **Dấu hiệu** | Badge CDTOTKVV hiện kiểu `đủ 22/21 PGD`; người dùng khó hiểu dữ liệu lấy từ đâu, có tính Biên Hòa/Hội sở hay không |
| **Nguyên nhân** | Dữ liệu CDTOTKVV thực tế có 22 đơn vị (Hội sở Chi nhánh tỉnh + 21 PGD) và tên trong file có thể là alias `Hội sở CN Đồng Nai`, nhưng UI lại lấy tử số từ `ten_dv` raw còn mẫu số từ `len(DS_PGD)=21` |
| **Fix** | Chuẩn hóa tên đơn vị CDTOTKVV qua alias về key nội bộ, đếm theo `22 đơn vị` kỳ vọng và hiển thị chú thích rõ nguồn `pgd_data/*/cdtotkvv_*.xlsx`; tháng hiển thị lấy theo ngày báo cáo trong file CDTOTKVV |
| **Ngày fix** | 2026-06-30 |

### E12 — Upload `CDTOTKVV toàn CN` fail khi file tổng hợp lệch 1 cột
| | |
|---|---|
| **File** | `data/cdtotkvv.py` |
| **Dấu hiệu** | Upload file tổng hợp `CT_CDT...052026.xlsx` có lúc báo `Không tìm thấy dòng dữ liệu hợp lệ...`, có lúc preview chỉ nhận `1 đơn vị` dù file là toàn CN |
| **Nguyên nhân** | Parser vừa khóa cứng vị trí cột theo layout cũ, vừa có thể bắt nhầm cột mã khác khi file chứa nhiều cột kiểu `Mã đơn vị` / `Mã PGD`; ngoài ra có file không lặp `Mã PGD` đầy đủ ở mọi dòng mà chỉ còn `Tên PGD/Tên đơn vị` theo block. Hậu quả là mã PGD không được đọc đúng hoặc toàn bộ file bị gom về 1 mã |
| **Fix** | Dò header theo tên cột chuẩn hóa (`STT`, `Mã PGD`, `Tên PGD`, `NGAYBC`...) rồi map index động; chọn cột có nhiều mã PGD hợp lệ nhất thay vì tin tuyệt đối vào header đầu tiên; fallback nhận diện theo `Tên PGD/Tên đơn vị` và kế thừa đơn vị theo block khi mã bị trống. Đồng thời bỏ thông báo lỗi hardcode `cột B` để tránh gây hiểu nhầm |
| **Ngày fix** | 2026-06-30 |

### E13 — CDTOTKVV mất số 0 đầu ở mã đơn vị/xã/tổ sau khi đọc Excel
| | |
|---|---|
| **File** | `data/cdtotkvv.py` → `doc_cdtotkvv_path()` |
| **Dấu hiệu** | File CDTOTKVV có `Mã đơn vị`/`Mã tổ` như `004601`, `0126259` nhưng sau khi đọc bằng pandas thành `4601`, `126259` |
| **Nguyên nhân** | `pd.read_excel()` infer các cột mã dạng số nguyên, rồi code cũ chỉ `astype(str)`/xóa `.0` nên không khôi phục được số 0 đầu |
| **Fix** | Chuẩn hóa các cột định danh bằng `_normalize_code_value()`: `ma_dv` zfill 6, `ma_xa` zfill 6, `ma_to` zfill 7 khi giá trị là số |
| **Test** | `tests/test_cdtotkvv_service.py::TestCdtotkvvToanCnParser::test_tach_file_doc_lai_dung_cot_cho_ca_layout_cu_va_moi` |
| **Ngày fix** | 2026-06-30 |

### E14 — CDTOTKVV toàn CN vẫn nhận 1 đơn vị khi file thiếu hẳn cột `Mã PGD`
| | |
|---|---|
| **File** | `data/cdtotkvv.py` → `_tim_header_cdto_toan_cn()` / `tach_file_cdto_toan_cn()`; `services/file_detection_service.py` → `ten_doc_ve_don_vi_chuan()` |
| **Dấu hiệu** | Upload CDTOTKVV toàn CN vẫn báo `Số đơn vị nhận diện: 1` dù đã fallback theo tên; thường gặp khi file chỉ có `Tên đơn vị` hoặc tên rút gọn như `Long Thành`, không có cột `Mã PGD` |
| **Nguyên nhân** | Hàm dò header vẫn yêu cầu `STT` + `Mã PGD` nên bỏ qua header chỉ có `Tên đơn vị`, rơi về index fallback cũ và map lệch cột. Đồng thời chuẩn hóa tên đơn vị chưa nhận tên PGD rút gọn không có tiền tố `PGD` |
| **Fix** | Chấp nhận header có `Tên PGD/Tên đơn vị` dù thiếu `Mã PGD`; chỉ dùng fallback index khi không dò được header; mở rộng `ten_doc_ve_don_vi_chuan()` để map tên rút gọn/có ngữ cảnh NHCSXH về tên nội bộ |
| **Test** | `tests/test_cdtotkvv_service.py::TestCdtotkvvToanCnParser::test_tach_file_van_map_dung_khi_header_khong_co_ma_pgd`; `tests/test_file_detection_service.py::test_ten_doc_ve_don_vi_chuan_short_pgd_name` |
| **Ngày fix** | 2026-06-30 |

### E15 — Baseline/HSTD toàn CN bị cộng dư nợ do cùng khoản vay xuất hiện ở nhiều PGD
| | |
|---|---|
| **File** | `services/validation_service.py` → `validate_hstd_cross_pgd_duplicates()`; `services/upload_service.py` → `merge_du_lieu_toan_cn()` / `merge_baseline_toan_cn()`; `tabs/tab_upload_khnv.py` |
| **Dấu hiệu** | Màn `📈 So sánh mốc năm` hoặc merge HSTD toàn Chi nhánh cho tổng dư nợ cao bất thường so với báo cáo tổng hợp THDNO46; kiểm tra sâu thấy cùng `Mã KH + Số khế ước` xuất hiện ở 2 PGD khác nhau |
| **Nguyên nhân** | Luồng merge cũ chỉ `concat` 22 file chi tiết rồi ghi cache, không hề kiểm tra trùng chéo khoản vay giữa các đơn vị. Vì vậy khi file nguồn baseline/HSTD bị overlap liên PGD, dư nợ toàn Chi nhánh bị cộng đúp nhưng app vẫn publish cache như dữ liệu hợp lệ |
| **Fix** | Thêm validator liên PGD cho HSTD theo khóa `Mã KH + Số khế ước`, tổng hợp top cặp PGD lệch nhiều nhất + mẫu dòng để rà nguồn. Nếu phát hiện trùng chéo thì block merge cả ở dữ liệu hiện tại lẫn baseline, giữ nguyên cache đang dùng và hiển thị chẩn đoán thay vì ghi đè số sai |
| **Test** | `tests/test_merge_du_lieu_toan_cn.py::TestMergeCrossPgdDuplicateBlock::test_hstd_hien_tai_trung_cheo_bi_chan_khong_ghi_cache`; `tests/test_merge_du_lieu_toan_cn.py::TestMergeCrossPgdDuplicateBlock::test_baseline_hstd_trung_cheo_giu_nguyen_cache_cu` |
| **Ngày fix** | 2026-07-03 |

---
### E16 — "Ngày cập nhật" ở tab Tổng quan hiển thị ngày hiện tại thay vì ngày số liệu HSTD
| | |
|---|---|
| **Dấu hiệu** | Tab Tổng quan hiển thị "Cập nhật: 01/07/2026" trong khi dữ liệu HSTD là ngày 30/06/2026 |
| **File** | `services/upload_service.py` (~d.1006-1015); `tabs/tab_tongquan.py` (~d.384-388) |
| **Nguyên nhân** | 2 bug kết hợp: (1) `merge_meta_hstd` không lưu trường `ngay_sl` → fallback `merge_meta_hstd.get("ngay_sl")` luôn thất bại. (2) Fallback cuối dùng `datetime.now()` → hiển thị sai ngày |
| **Fix** | (1) Thêm logic trích xuất `COT_NGAY_SL` max từ `df_toan_cn` và lưu vào `merge_meta_{loai}`. (2) Thay `datetime.now()` bằng `"—"` |
| **Ngày fix** | 2026-07-10 |

### E17 — Tab Ban Đại Diện, section "Dự báo vốn" bị ẩn do `_ngay_so_lieu()` fail
| | |
|---|---|
| **Dấu hiệu** | Tab Ban Đại Diện → "Dự báo Nguồn vốn" không hiển thị, chỉ thấy "⚠️ Không xác định được ngày số liệu." |
| **File** | `tabs/tab_ban_dai_dien.py` dòng ~82-92 (cũ) |
| **Nguyên nhân** | `_ngay_so_lieu()` dùng `datetime.strptime(str(sl.iloc[0]), "%d/%m/%Y")` — khi Parquet lưu "Ngày số liệu" dạng datetime64, `str(datetime64)` ra định dạng `"2026-06-30 00:00:00"` không khớp `%d/%m/%Y` → luôn vào except → return None |
| **Fix** | Thay bằng `lay_ngay_so_lieu()` từ utils — dùng `pd.to_datetime()` với `dayfirst=True`, xử lý cả string lẫn datetime64 |
| **Ngày fix** | 2026-07-10 |

### E18 — Tờ trình BGĐ hiển thị ngày hiện tại thay vì ngày số liệu HSTD
| | |
|---|---|
| **Dấu hiệu** | Tờ trình BGĐ ghi "Tính đến ngày 10/07/2026" trong khi số liệu HSTD là 30/06/2026 |
| **File** | `tabs/tab_khtd_xuat.py` dòng ~950 (cũ) |
| **Nguyên nhân** | `ngay_sl = _date.today().strftime("%d/%m/%Y")` gán trước — nếu metadata không có `ngay_sl` (do lỗi E16) thì dùng luôn ngày hiện tại |
| **Fix** | Khởi tạo `ngay_sl = ""`, đọc metadata trước, nếu metadata không có thì fallback `lay_ngay_so_lieu()` đọc trực tiếp từ DataFrame HSTD |
| **Ngày fix** | 2026-07-10 |

### E19 — Import hàng loạt KH-NV xong nhưng Tổng quan vẫn dùng cache cũ
| | |
|---|---|
| **Dấu hiệu** | Import hàng loạt HSTD/NQ11/GQVL thành công, bảng trạng thái file đã đổi nhưng `📊 Thông tin chung`/cache toàn CN vẫn giữ số liệu cũ cho đến khi người dùng tự bấm `Merge toàn CN` |
| **File** | `tabs/tab_upload_khnv/_upload_don_vi.py` → `_xu_ly_import_folder()` |
| **Nguyên nhân** | Luồng import chỉ lưu file vào `pgd_data` và thêm loại vào pending queue (`them_vao_hang_cho`), không gọi merge ngay. Người dùng dễ hiểu import là đã áp dụng số liệu toàn CN |
| **Fix** | Sau import hàng loạt, tự gọi `merge_nhieu_loai_toan_cn()` cho các loại HSTD/NQ11/GQVL vừa lưu, xóa các loại merge thành công khỏi pending queue và gọi `lam_moi_du_lieu_app()` để app đọc cache mới |
| **Ngày fix** | 2026-07-10 |

---

## F. PDF / Word

### F1 — Lỗi font (tofu □□□)
| | |
|---|---|
| **Nguyên nhân** | Thiếu file font Times New Roman |
| **Fix** | Đặt `assets/times.ttf` và `assets/timesbd.ttf`. Trên Windows tự tìm `C:/Windows/Fonts/` |

### F5 — `UnboundLocalError: e` trong PDF fallback font handler
| | |
|---|---|
| **File** | `tabs/tab_nhiem_vu.py` → `_xuat_pdf_nhiem_vu()` |
| **Dấu hiệu** | Xuất PDF crash với `UnboundLocalError: cannot access local variable 'e'` khi font TTF không tìm thấy |
| **Nguyên nhân** | `except Exception:` (không có biến) nhưng dòng tiếp theo gọi `logger.error(..., e, ...)` — `e` chưa được bind |
| **Fix** | Đổi thành `except Exception as e:` để bind biến; log warning thay vì error vì fallback font là hành vi bình thường trên máy không có font |
| **Ngày fix** | 2026-05-23 |

### F2 — `docx2pdf failed` / `Word not found`
| | |
|---|---|
| **Nguyên nhân** | `docx2pdf` yêu cầu Microsoft Word cài trên máy Windows |
| **Thay thế** | Mở file `.docx` → File → Save As → PDF thủ công. Linux: `libreoffice --headless --convert-to pdf` |

### F3 — Nút download PDF không hiện
| | |
|---|---|
| **Nguyên nhân** | Chưa bấm "Xuất Word" — button PDF cần dữ liệu từ `session_state` do bước Word tạo ra |
| **Thứ tự đúng** | Xuất Word → Xuất PDF → Download |

### F4 — PDF thiếu logo
| | |
|---|---|
| **Fix** | Kiểm tra `assets/logo.png` tồn tại. `pdf_service.py` tự fallback về text nếu thiếu |

### F5 — `NameError: TA_LEFT` trong PDF
| | |
|---|---|
| **Dấu hiệu** | `NameError: name 'TA_LEFT' is not defined` khi tạo PDF |
| **File** | `pdf_service.py` ~dòng 31 |
| **Nguyên nhân** | Thiếu `TA_LEFT` trong `from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT` |
| **Fix** | Import đầy đủ: `from reportlab.lib.enums import TA_LEFT` |
| **Ngày fix** | 2026-05-22 |

### F6 — Định dạng ngày Timestamp → dd/mm/yyyy trong PDF
| | |
|---|---|
| **Dấu hiệu** | Ngày trong PDF hiển thị `2026-05-16 00:00:00` thay vì `16/05/2026` |
| **File** | `tabs/tab_tien_do.py`, bất kỳ PDF nào có cột ngày |
| **Nguyên nhân** | `pd.Timestamp` bị convert thẳng thành string giữ format ISO |
| **Fix** | Dùng `.strftime("%d/%m/%Y")` hoặc `fmt_ngay()` từ `utils.py` trước khi đưa vào PDF |
| **Ngày fix** | 2026-05-16 |

### F7 — Ban Đại Diện: PDF bảng tổng hợp theo PGD chưa format phân cách hàng nghìn
| | |
|---|---|
| **File** | `tabs/tab_ban_dai_dien.py` → `_render_tong_hop()` |
| **Dấu hiệu** | Màn hình `Bảng tổng hợp theo PGD` đã có format kiểu Việt Nam nhưng bản `Xuất PDF` để in vẫn còn các giá trị số chưa đồng nhất, đặc biệt ở `GN năm`, `Số KH`, `NQH%` |
| **Nguyên nhân** | Luồng PDF dùng `df_pgd` gần như thô; chỉ một phần cột được đưa qua nhánh `cols_tien`, còn các cột số khác đi thẳng vào PDF dưới dạng raw |
| **Fix** | Tạo helper format dùng chung cho bảng tổng hợp theo PGD, rồi tái sử dụng cho cả `st.dataframe()` và `xuat_pdf()`; PDF in dùng chính bản đã format và tắt dòng tổng số tự động để tránh lệch kiểu dữ liệu |
| **Ngày fix** | 2026-07-12 |

### F8 — Tab Ủy thác thiếu PDF báo cáo điều hành và phụ thuộc Microsoft Word
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py`, `services/uy_thac_pdf_service.py` |
| **Dấu hiệu** | Khu Báo cáo số liệu chỉ xuất Excel; PDF chỉ có ở các mẫu Word, thiếu KPI, biểu đồ, cảnh báo, điểm nóng và biến động nhiều kỳ |
| **Nguyên nhân** | Tab chưa có engine PDF chuyên biệt; luồng cũ chủ yếu gọi `docx2pdf`, phụ thuộc Microsoft Word và không phù hợp báo cáo điều hành nhiều bảng |
| **Fix** | Tạo engine ReportLab riêng với hai lựa chọn `PDF báo cáo đang xem` và `PDF điều hành Ủy thác`; hỗ trợ logo, Times New Roman, KPI, nhận định, biểu đồ, bảng rộng chia nhóm cột, header lặp, số trang và quy đổi VND sang triệu đồng |
| **Test** | `tests/test_uy_thac_pdf_service.py::test_tao_pdf_bao_cao_dang_xem_dung_don_vi_trieu`, `tests/test_uy_thac_pdf_service.py::test_tao_pdf_dieu_hanh_co_du_cac_phan_va_nhieu_trang` |
| **Ngày fix** | 2026-07-14 |

### F9 — `NameError: WD_ALIGN_PARAGRAPH` làm crash tab Thông tin chung
| | |
|---|---|
| **File** | `services/hstd_word_service.py` dòng ~28-48; import từ `tabs/tab_tongquan.py` |
| **Dấu hiệu** | Mở `📊 Thông tin chung` báo `Lỗi render **📊 Thông tin chung**: name 'WD_ALIGN_PARAGRAPH' is not defined`; log có `ModuleNotFoundError: No module named 'docx'` hoặc import `docx` lỗi trước đó |
| **Nguyên nhân** | `python-docx` là dependency tùy chọn ở runtime, nhưng file service dùng `WD_ALIGN_PARAGRAPH.LEFT` và `.CENTER` trong default argument của helper module-level. Khi import `docx` thất bại, `except ImportError` chỉ set `_DOCX_READY=False`, còn symbol enum không tồn tại nên module crash ngay lúc định nghĩa hàm |
| **Fix** | Trong nhánh `except ImportError`, khai báo fallback object có các thuộc tính `LEFT/CENTER/RIGHT/JUSTIFY` và `WD_TABLE_ALIGNMENT.CENTER`. Nhờ vậy tab Tổng quan import/render bình thường; hàm xuất Word vẫn dừng sớm với thông báo thiếu `python-docx` khi được gọi |
| **Ngày fix** | 2026-07-19 |

---

## G. Kế hoạch tín dụng

### G1 — KH nhập xong nhưng không lưu
| | |
|---|---|
| **Kiểm tra** | 1. Đã nhấn `💾 Lưu kế hoạch`? 2. Role có phải `admin` / `manager`? 3. `SELECT * FROM audit_log WHERE action = 'luu_khtd_cn' ORDER BY created_at DESC LIMIT 5` |

### G2 — Form nhập hiện số thập phân không mong muốn
| | |
|---|---|
| **Fix** | `number_input(format="%.0f")` thay vì `format="%.1f"` |

### G3 — Cột TH Xã hiển thị 0 dù có dữ liệu
| | |
|---|---|
| **Nguyên nhân** | `df_full` chưa được truyền vào `_tab_khtd_xa()` |
| **Fix** | Kiểm tra signature hàm và chỗ gọi trong `render()` |

### G5 — KHTD dark mode: text vô hình trên nền pastel / nền trắng hardcode

### G6 — NameError: name 'xa_chon' is not defined trong tab Kế hoạch theo Xã
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` — hàm `_tab_khtd_theo_xa()` |
| **Dấu hiệu** | Tab "📈 Kế hoạch tín dụng" báo `NameError: name 'xa_chon' is not defined` |
| **Nguyên nhân** | `xa_chon` được dùng từ dòng ~1404 nhưng chưa bao giờ được định nghĩa (selectbox chọn xã bị thiếu) |
| **Fix** | Thêm `xa_chon = st.selectbox("Chọn Xã/Phường", danh_sach_xa, key="khtd_xa_xa_sel")` ngay sau `st.divider()` tại dòng ~1368 |
| **Ngày fix** | 2026-07-11 |
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` dòng ~324, `tabs/tab_khtd_xuat.py` dòng ~224 & ~265 |
| **Dấu hiệu** | Trong Streamlit dark mode: banner trạng thái KH không đọc được; dòng GQVL và TỔNG CỘNG trong bảng readonly mờ/vô hình |
| **Nguyên nhân** | 1. Banner div có nền pastel sáng nhưng không set `color` → Streamlit dark mode kế thừa text màu trắng → chữ trắng trên nền vàng = vô hình. 2. GQVL sub-row dùng `background:#ffffff` hardcode trên `<tr>` → tương tự. 3. Dòng TỔNG CỘNG dùng `TONG_BG=#E8F4FD` (sáng) không set `color` |
| **Fix** | Thêm `color:#1f2937` cho mọi element có nền sáng cố định. Bỏ `background` hardcode trên `<tr>` GQVL sub-row để kế thừa nền trang |
| **Quy tắc** | Bất kỳ HTML inline nào set `background` sáng → PHẢI set `color` tối tương ứng. Không set background → kế thừa dark/light theme tự động |
| **Ngày fix** | 2026-06-21 |

### G6 — Tóm tắt hiện trạng: CT có 2 nguồn vốn (TW+ĐP) bị "nhảy lên" nhóm Trung ương
| | |
|---|---|
| **File** | `tabs/tab_khtd_xuat.py` — `_hien_thi_bang_cn_readonly()` vòng lặp `for ma_ct in order_ma_ct` |
| **Dấu hiệu** | Chương trình có cả 2 nguồn vốn TW và ĐP hiển thị gộp 1 dòng dưới nhóm "I. Nguồn vốn Trung ương", phần ĐP biến mất khỏi nhóm "II". GQVL phần ĐP cũng nằm nhầm nhóm I |
| **Nguyên nhân** | Code gộp `kh_tong = kh_tw + kh_dp` thành 1 dòng rồi gán nhóm theo điều kiện `if kh_tw > 0: nhóm I else nhóm II` → có TW là cả CT vào nhóm I. Header nhóm ghi lazy trong vòng lặp theo thứ tự mã CT → lặp header / sai thứ tự |
| **Fix** | Duyệt 2 lượt: lượt 1 chỉ render phần TW (kh_tw/th_tw) vào nhóm I, lượt 2 chỉ render phần ĐP (kh_dp/th_dp) vào nhóm II; GQVL lọc sub-row theo `t[2]=="TW"/"ĐP"` về đúng nhóm. Header chỉ ghi 1 lần khi nhóm có dòng. STT dùng counter `stt_no` liên tục; `Số CT có KH` đếm CT duy nhất (tránh nhân đôi) |
| **Bài học** | Khi 1 thực thể có nhiều phân loại (TW/ĐP) cần tách dòng theo phân loại, KHÔNG gộp tổng rồi gán nhóm theo phân loại đầu tiên gặp |
| **Ngày fix** | 2026-06-21 |

### G4 — CI smoke render fail: `TypeError: takes 3 positional arguments but 7 were given`
| | |
|---|---|
| **File** | `tabs/tab_khtd_giao_dc.py` — `render()` dòng ~1292 |
| **Dấu hiệu** | CI `test_smoke_imports.py::TestSmokeRender::test_render[tabs.tab_khtd_giao_dc]` fail với `TypeError` |
| **Nguyên nhân** | Refactor `_section_c_tong_hop()` bỏ 4 param (username, role, loai_val, readonly_exec) nhưng call site trong `render()` vẫn truyền 7 args |
| **Fix** | Đổi call thành `_section_c_tong_hop(nam, thang, dot)` |
| **Bài học** | Khi rút gọn signature hàm helper, grep tất cả call site trong cùng file: `grep -n "_section_c_tong_hop" tabs/tab_khtd_giao_dc.py` |
| **Ngày fix** | 2026-06-20 |

### G7 — NSVSMT ĐP (mã 06) bị gộp chung `6_DP`, không tách nguồn cấp tỉnh / cấp xã
| | |
|---|---|
| **File** | `tabs/tab_khtd.py`, `tabs/tab_khtd_nhap.py`, `tabs/tab_khtd_xuat.py`, `config.py` |
| **Dấu hiệu** | HSTD mới có `Mã chương trình = 06`, `Nguồn vốn = ĐP`, kèm `Mã nhà đầu tư` nhưng màn `🏛️ Kế hoạch Tín dụng Chi nhánh` và phần `📊 Báo cáo & Xuất file` chỉ hiện 1 dòng `6_DP`; không nhìn ra dư nợ `NSVSMT ĐP` thuộc nguồn cấp tỉnh hay cấp xã |
| **Nguyên nhân** | Logic `_tinh_thuc_hien_theo_ct()` trước đó chỉ group theo `(Mã chương trình, Nguồn vốn)` nên toàn bộ `ma_ct=6`, `nv=2` bị cộng chung vào `6_DP`; UI KHTD cũng chỉ có 1 dòng `NSVSMT ĐP` |
| **Fix** | Giữ `6_DP` tổng hợp để tương thích dữ liệu cũ, đồng thời bổ sung 2 sub-key `6_DP_TINH` / `6_DP_XA`; phân tầng TH từ HSTD theo `Mã nhà đầu tư` (thuộc danh mục NĐT cấp tỉnh → `6_DP_TINH`, còn lại/thiếu mã → `6_DP_XA`); màn nhập/xuất KHTD CN render 2 sub-row chi tiết. File Excel cũ chỉ có `6_DP` được fallback sang `6_DP_TINH` để không mất số |
| **Bài học** | Với chương trình ĐP mà nghiệp vụ cần tách nguồn bên trong cùng `ma_ct`, không được chỉ group theo `(ma_ct, nv)`; phải đọc thêm chiều phân loại nghiệp vụ (`Mã nhà đầu tư`, `Phân loại NV`...) và vẫn giữ key tổng hợp cũ nếu hệ thống đang có dữ liệu lịch sử |
| **Ngày fix** | 2026-06-21 |

### G9 — `tong_kh` trong tab Tiến độ KH vs TH tính kép backward-compat keys
| | |
|---|---|
| **File** | `tabs/tab_khtd_xuat.py` dòng ~562 hàm `_tab_tien_do_kh_th()` |
| **Dấu hiệu** | Metric "Tổng KH" hiển thị cao hơn thực tế; "Tỷ lệ CN" bị thấp hơn thực tế |
| **Nguyên nhân** | `kh_cn` từ kv_store chứa cả sub-key lẫn backward-compat total (`6_DP_TINH` + `6_DP_XA` + `6_DP`; `3_TW_NHCSXH` + `3_TW_NSNN` + `3_TW`; `3_DP_TINH` + `3_DP_XA` + `3_DP`). Dùng `sum(kh_cn.values())` sẽ tính kép nhóm GQVL và NSVSMT ĐP |
| **Fix** | Đổi sang `sum(kh_cn.get(mk, 0) for mk, *_ in CHUONG_TRINH_KHTD)` — chỉ tổng hợp các key "chính" trong CHUONG_TRINH_KHTD, không bao gồm backward-compat alias; khớp cách tính `tong_th` |
| **Bài học** | Khi lưu cả sub-key lẫn total vào cùng dict để tương thích, KHÔNG dùng `dict.values()` để tổng hợp — phải lọc theo tập key chuẩn |
| **Ngày fix** | 2026-06-21 |

### G8 — Danh mục Mã NĐT ĐP thiếu `Mã CT áp dụng` nên rule dễ bị dùng nhầm giữa các chương trình
| | |
|---|---|
| **File** | `db.py`, `tabs/tab_khtd.py`, `tabs/tab_quan_ly_ndt_dp.py`, `tabs/tab_ndt_dp.py` |
| **Dấu hiệu** | Danh mục NĐT ĐP trước đây chỉ lưu `ma` + `cap`; khi thêm NSVSMT ĐP phải tách riêng thêm 1 list khác. Người dùng khó biết một mã đang áp cho CT nào, còn code thì dễ mặc định dùng chung rule giữa `03_DP` và `06_DP` |
| **Nguyên nhân** | Thiết kế danh mục thiếu chiều nghiệp vụ `Mã CT áp dụng`, nên không thể tra chắc theo cặp `(ma_ct, ma_ndt)`; phải ngầm hiểu danh sách nào thuộc chương trình nào |
| **Fix** | Chuẩn hóa sang danh mục rule `ndt_dp_rule_list` với cấu trúc `{"ma_ct", "ma", "ghi_chu", "cap"}`; thêm helper `phan_loai_ndt_dp_cap(ma_ct, ma_ndt)` ưu tiên match exact `(ma_ct, ma_ndt)`, fallback rule chung `ma_ct=None`; UI quản lý/xem-only hiển thị thêm `CT 03` / `CT 06` |
| **Bài học** | Với danh mục dùng để phân loại nhiều chương trình, phải lưu đủ khóa nghiệp vụ tối thiểu ngay từ đầu; đừng dựa vào tên tab hoặc key kv riêng để ngầm suy ra ngữ cảnh chương trình |
| **Ngày fix** | 2026-06-21 |

### G25 — Tab Nguồn vốn địa phương vẫn gộp cấp tỉnh/cấp xã dù đã có rule Mã NĐT
| | |
|---|---|
| **File** | `tabs/tab_hhi.py` |
| **Dấu hiệu** | Sau khi cấu hình mã nhà đầu tư cấp tỉnh/cấp xã, màn `🏦 Nguồn vốn địa phương` vẫn chỉ có `Trung ương` và `Địa phương`; KPI, biểu đồ, bảng và Excel không cho biết phần ĐP nào thuộc cấp tỉnh hay cấp xã/khác |
| **Nguyên nhân** | Tab phân tích chỉ map theo cột `Nguồn vốn`, chưa đọc rule `Mã CT + Mã nhà đầu tư` từ `ndt_dp_rule_list`; vì vậy lớp nghiệp vụ mới ở tab quản lý mã NĐT không được phản ánh vào báo cáo điều hành |
| **Fix** | Thêm `_nv_cap_label` trong bước chuẩn hóa dữ liệu, dựng lookup rule một lần mỗi render, tách ĐP thành `ĐP cấp tỉnh` và `ĐP cấp xã/khác`; cập nhật KPI, pie, treemap, bảng chi tiết và Excel export theo 2 cấp này |
| **Bài học** | Khi đã có danh mục phân loại nghiệp vụ, mọi báo cáo cùng chuyên đề phải dùng lại danh mục đó; không dừng ở chiều tổng hợp cũ nếu người dùng đã cung cấp khóa phân loại chi tiết |
| **Ngày fix** | 2026-07-19 |

### G26 — `_tinh_thuc_hien_theo_ct` chia 50/50 GQVL ĐP thay vì theo Mã NĐT
| | |
|---|---|
| **File** | `tabs/tab_khtd.py` ~dòng 484 |
| **Dấu hiệu** | Tab KHTD — TH hiển thị cho GQVL ĐP: `3_DP_TINH` = `3_DP_XA` = 50% thay vì tỷ lệ thực tế (vd 95%/5%) |
| **Nguyên nhân** | `_tinh_thuc_hien_theo_ct()` không có logic phân tầng cho GQVL ĐP. Khi lookup `(ma_ct=3, nv=2)` trả về 2 key `["3_DP_TINH", "3_DP_XA"]`, code chia đều `float(val) / len(mk_list)` → luôn 50/50. Khác với NSVSMT ĐP (ma_ct=6) đã có `_tinh_th_nsvsmt_dp_phan_tang` dùng Mã NĐT để phân tầng |
| **Fix** | Tạo `_tinh_th_gqvl_dp_phan_tang()` — copy pattern từ `_tinh_th_nsvsmt_dp_phan_tang`, đổi `ma_ct == 6` → `ma_ct == 3` và key `6_DP_*` → `3_DP_*`. Sau groupby loop, thêm block override GQVL ĐP (tương tự block NSVSMT ĐP ở dòng 506-511) |
| **Bài học** | Mọi chương trình DP có 2 sub-key (TINH/XA) trong `CHUONG_TRINH_KHTD` đều cần hàm phân tầng riêng dựa trên Mã NĐT; không được dùng `len(mk_list)` chia đều |
| **Ngày fix** | 2026-07-19 |

### G27 — `_tinh_thuc_hien_theo_ct` (tab PGD) ép 100% GQVL ĐP vào `3_DP_TINH`, `3_DP_XA` luôn = 0
| | |
|---|---|
| **File** | `tabs/tab_khtd_pgd.py` ~dòng 540 |
| **Dấu hiệu** | Bảng KH/TH PGD — cột `3_DP_XA` (GQVL xã) luôn bằng 0, toàn bộ GQVL ĐP dồn vào `3_DP_TINH`. Tương tự, NSVSMT ĐP (ma_ct=6) không tách được `6_DP_TINH`/`6_DP_XA` |
| **Nguyên nhân** | `lookup` trong `_tinh_thuc_hien_theo_ct` dùng first-win: `(3, 2)` → `"3_DP_TINH"`, `"3_DP_XA"` không bao giờ được gán. Groupby gộp toàn bộ GQVL ĐP vào `3_DP_TINH`. Không có block phân tầng theo Mã NĐT như G26 đã fix ở `tab_khtd.py` |
| **Fix** | Sau groupby loop, thêm block override: với mask `(ma_ct==3, nv==2)` và `(ma_ct==6, nv==2)`, map từng dòng sang `phan_loai_ndt_dp_cap()` rồi tổng hợp lại thành `3_DP_TINH`/`3_DP_XA` và `6_DP_TINH`/`6_DP_XA`. Xóa key tạm `6_DP` sau khi tách |
| **Bài học** | Mọi fix phân tầng ĐP phải áp dụng đồng bộ cho cả `tab_khtd.py` (màn CN) lẫn `tab_khtd_pgd.py` (màn PGD). Khi fix G26 chỉ sửa tab CN, tab PGD vẫn mang bug cũ |
| **Ngày fix** | 2026-07-19 |

### G28 — Tab Nguồn vốn địa phương thiếu bảng đối chiếu 02 chương trình nguồn vốn xã
| | |
|---|---|
| **File** | `tabs/tab_hhi.py` → `_bang_nguon_von_xa_02_ct()` ~dòng 257; `db.py` → `_seed_ndt_dp_rules()` ~dòng 1226 |
| **Dấu hiệu** | User cần đối chiếu riêng dư nợ GQVL và NS&VSMTNT nguồn ngân sách cấp xã theo 22 đơn vị, nhưng tab chỉ hiển thị tổng TW/ĐP/cấp tỉnh/cấp xã; sau khi sửa rule Mã NĐT, số có thể vẫn cũ trong session vì cache label nguồn vốn không phụ thuộc version rule |
| **Nguyên nhân** | Báo cáo tổng hợp `_bang_theo_nv()` không tách riêng trục chương trình 03/06 cho phần `ĐP cấp xã/khác`; `_nhan_nv_numeric()` dùng cache key theo `ts_hstd` nhưng chưa fingerprint `ndt_dp_rule_list`; seed mặc định còn mã CT06 `INV1201260090198` đã được xác nhận không thuộc cấp tỉnh |
| **Fix** | Thêm bảng đối chiếu riêng lọc `Nguồn vốn = Địa phương`, `_nv_cap_label = ĐP cấp xã/khác`, `Mã CT in (3, 6)`; thêm `_rules_cache_key()` vào `nv_cache_key`; bỏ seed CT06 `INV1201260090198`; khóa test tổng chuẩn `GQVL=93.479`, `NS&VSMTNT=2.480`, `Tổng=95.959` triệu |
| **Test** | `tests/test_tab_hhi.py::test_bang_nguon_von_xa_02_ct_khop_so_chuan`, `tests/test_tab_hhi.py::test_bang_nguon_von_xa_02_ct_loai_tru_rule_cap_tinh` |
| **Ngày fix** | 2026-07-19 |

### G10 — `🏛️ KHTD Chi nhánh`: `TH` GQVL bị lấy nhầm tiền từ `GQVL.parquet` thay vì `HSTD`
| | |
|---|---|
| **File** | `services/khtd_nhap_service.py`, `tabs/tab_khtd_nhap.py`, `tabs/tab_khtd_xuat.py` |
| **Dấu hiệu** | Mục `🏛️ Kế hoạch Tín dụng Chi nhánh` cần theo dõi `TH` theo `HSTD`, nhưng phân tầng GQVL lại cộng trực tiếp tiền từ `GQVL.parquet`; số từng nhóm có thể không khớp với tổng `TH` nghiệp vụ đang dùng ở HSTD |
| **Nguyên nhân** | Hiểu sai vai trò của file `GQVL`: file này chỉ là nguồn tham chiếu để biết mỗi `Số khế ước` GQVL thuộc nhóm `TW/ĐP/tỉnh/xã`, còn số `TH` chính thức vẫn phải lấy từ `HSTD`. Hàm cũ `tinh_th_gqvl_phan_tang(df_gqvl)` lấy cả phân tầng lẫn số tiền từ `GQVL.parquet` |
| **Fix** | Đổi `tinh_th_gqvl_phan_tang(df_hstd, df_gqvl)` sang lấy dư nợ từ `HSTD`, join `GQVL` theo `Số khế ước` để xác định nhóm; nếu thiếu tham chiếu thì fallback chia đều theo nguồn như logic cũ để không hụt tổng |
| **Bài học** | Với dữ liệu tham chiếu chéo, phải tách rõ: file nào là nguồn số tiền chính, file nào chỉ dùng để gắn nhãn/phân loại; không được lấy nhầm số tiền từ file tham chiếu |
| **Ngày fix** | 2026-06-25 |

### G11 — `📊 Tóm tắt hiện trạng` sinh đúng subtotal nhưng UI chưa hiện đủ hàng HTML
| | |
|---|---|
| **File** | `tabs/tab_khtd_xuat.py` |
| **Dấu hiệu** | Màn `📈 Kế hoạch tín dụng` → `🏛️ KHTD Chi nhánh` reload xong vẫn không thấy các hàng `TỔNG CỘNG PHẦN I` / `TỔNG CỘNG PHẦN II`, dù helper `_hien_thi_bang_cn_readonly()` đã append đủ các dòng subtotal vào HTML |
| **Nguyên nhân** | Bảng readonly được render bằng `st.markdown(html, unsafe_allow_html=True)`. Với HTML table dài, runtime/frontend hiện tại có thể không phản ánh đầy đủ các hàng subtotal dù chuỗi HTML đầu ra đã đúng |
| **Fix** | Đổi `_hien_thi_bang_cn_readonly()` sang ưu tiên `st.html(html)` để render HTML table đúng hơn; chỉ fallback `st.markdown(..., unsafe_allow_html=True)` khi runtime cũ chưa hỗ trợ `st.html` |
| **Bài học** | Với bảng HTML thuần nhiều dòng/cột trong Streamlit, ưu tiên `st.html()` nếu version hỗ trợ; không nên mặc định tin rằng `st.markdown(..., unsafe_allow_html=True)` sẽ luôn render đúng toàn bộ cấu trúc bảng |
| **Ngày fix** | 2026-06-27 |

### G12 — `🏛️ KHTD Chi nhánh`: ô nhập KH không có dấu phân cách nên khó kiểm tra trước khi lưu
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` |
| **Dấu hiệu** | Ở bảng nhập `🏛️ KHTD Chi nhánh`, người dùng gõ các số lớn như `1250000` nhưng ô nhập không hiện dạng `1.250.000`, nên khó rà soát đã nhập đúng hay chưa; cột số cũng khá sít nhau nên nhìn mỏi mắt |
| **Nguyên nhân** | `st.number_input` chỉ dùng `format="%.0f"` để tránh lỗi render trước đó, nên không hỗ trợ hiển thị dấu phân cách hàng nghìn trong ô nhập. Bố cục `st.columns()` cũ cũng dành hơi ít không gian cho các cột số |
| **Fix** | Đổi riêng phần nhập KH của `🏛️ KHTD Chi nhánh` sang `text_input` + parse số nguyên triệu đồng an toàn; sau khi bấm `👁 Xem trước tính toán` hoặc `💾 Lưu`, giá trị được chuẩn hóa lại thành dạng `1.234.567` ngay trên ô nhập. Đồng thời nới tỷ lệ cột và padding để bảng thoáng hơn |
| **Bài học** | Với form cần tránh rerun liên tục nhưng vẫn muốn user tự rà số lớn, không nên ép `number_input` làm việc nó không hỗ trợ; dùng `text_input` + parse/format ở bước preview/save sẽ an toàn và rõ ràng hơn |
| **Ngày fix** | 2026-06-29 |

### G13 — `🏛️ KHTD Chi nhánh`: phần nhập dạng nhiều cột rời khó dò ngang và khó nhập liên tục
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` |
| **Dấu hiệu** | Ở màn `📈 Kế hoạch tín dụng` → `🏛️ KHTD Chi nhánh`, khu vực nhập KH bên dưới dù đã có viền CSS nhưng thực chất là nhiều `st.columns()` ghép lại; khi rà theo hàng hoặc nhập liên tiếp dễ hụt cột, nhất là với các nhóm GQVL/NSVSMT có dòng tách nhỏ |
| **Nguyên nhân** | UI cũ mô phỏng bảng bằng HTML header + `st.columns()` cho từng dòng, nên không có lưới bảng thật, không khóa được nhịp mắt theo hàng/cột như spreadsheet |
| **Fix** | Dựng lại phần nhập thành `st.data_editor` với các cột `KH/TH/Còn TH` cho TW và ĐP, giữ cột tính toán ở chế độ read-only, đồng thời lưu draft vào `session_state` để số liệu tính lại ngay sau mỗi lần chỉnh |
| **Bài học** | Với màn nhập số liệu nhiều dòng, nhiều cột và cần đối chiếu ngang, nên ưu tiên grid editor thật thay vì dựng giả bằng `st.columns()` + CSS; cách này dễ nhìn hơn và ít lỗi thao tác hơn |
| **Ngày fix** | 2026-07-11 |

### G14 — `🏛️ KHTD Chi nhánh`: bảng nhập `data_editor` hiện `,0f` và `None` thay vì số
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` |
| **Dấu hiệu** | Sau khi đổi sang bảng `data_editor`, các cột `TH` / `Còn TH` hiển thị literal như `,0f` và chữ `None`, làm bảng rất khó đọc dù dữ liệu tính toán vẫn có |
| **Nguyên nhân** | Các cột chỉ đọc vẫn được khai báo `NumberColumn(format=\"...")` trong runtime hiện tại, trong khi dữ liệu có nhiều giá trị `None` cho dòng không áp dụng; frontend render không ổn định nên lộ cả format literal lẫn `None` |
| **Fix** | Giữ lại chỉ 2 cột `KH TW` và `KH ĐP` là số editable; chuyển toàn bộ cột `TH` / `Còn TH` / `TH tổng` sang text đã format sẵn bằng helper, đồng thời dùng `Int64` nullable cho cột KH để nhập số nguyên gọn hơn |
| **Bài học** | Với `data_editor`, các cột chỉ dùng để xem nên format sẵn thành text nếu runtime render NumberColumn không ổn định; không nên cố ép mọi cột sang NumberColumn khi có nhiều ô trống/không áp dụng |
| **Ngày fix** | 2026-07-11 |

### G15 — `🏛️ KHTD Chi nhánh`: vừa sửa ô `KH` là bị mất focus, không nhập liên tục được
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` |
| **Dấu hiệu** | Sau khi đổi sang `data_editor`, người dùng vừa chạm sửa cột `KH TW` / `KH ĐP` thì bảng refresh ngay, ô nhập mất focus nên cảm giác "không nhập được" hoặc rất khó gõ liên tiếp |
| **Nguyên nhân** | Code gọi `st.rerun()` ngay sau khi phát hiện dữ liệu editor thay đổi; điều này làm widget bị dựng lại tức thì ở mỗi lần edit |
| **Fix** | Bỏ `st.rerun()` cưỡng bức; chỉ cập nhật draft vào `session_state` và để editor tiếp tục giữ phiên nhập hiện tại |
| **Bài học** | Với `st.data_editor`, không nên tự `st.rerun()` ngay sau mỗi thay đổi của chính editor nếu mục tiêu là cho phép người dùng nhập liên tục; rerun cưỡng bức rất dễ làm mất focus và khóa thao tác |
| **Ngày fix** | 2026-07-11 |

### G16 — `📈 KHTD Chi nhánh`: mô hình chương trình tách ngang sai nghiệp vụ, tên CT lệch HSTD
| | |
|---|---|
| **File** | `tabs/tab_khtd.py`, `tabs/tab_khtd_nhap.py`, `tabs/tab_khtd_xuat.py` |
| **Dấu hiệu** | Màn nhập/xuất KHTD tách ngang cho nhiều chương trình, `NSVSMT ĐP` còn chia tỉnh/xã, tên chương trình ở màn nhập không khớp tên HSTD, và GQVL không bám đúng rule dùng HSTD làm chính + GQVL làm file phụ để tách nguồn |
| **Nguyên nhân** | Model hiển thị và model nghiệp vụ bị trộn lẫn: dùng nhiều `ma_key` chi tiết để render trực tiếp UI thay vì có một lớp row model chuẩn cho KHTD Chi nhánh; vì vậy UI bị kéo theo cấu trúc key cũ thay vì phản ánh rule nghiệp vụ thật |
| **Fix** | Thêm helper chuẩn cho KHTD CN trong `tab_khtd.py`: chỉ GQVL có 4 dòng con; chương trình thường giữ 1 dòng với trục dọc `TW/ĐP`; TH lấy từ HSTD làm chính, GQVL chỉ dùng để tách `TW` thành `NS Trung ương cấp` và `NHCSXH huy động`, còn `ĐP` tách theo `Mã NĐT địa phương`; ưu tiên tên CT từ HSTD; đồng bộ màn nhập, readonly và xuất Word qua cùng `_iter_khtd_cn_group_rows()` thay vì lặp trực tiếp danh mục key lưu trữ |
| **Bài học** | Với màn nghiệp vụ có nhiều nguồn dữ liệu, không nên render trực tiếp từ `ma_key` lưu trữ. Cần có một row model trung gian phản ánh đúng nghiệp vụ trước, rồi mới map sang key lưu dữ liệu và số TH thực tế |
| **Ngày fix** | 2026-07-11 |

### G17 — `📈 KHTD`: thiếu `7_DP` và `ma_ct 13` làm tổng TH lệch `Tổng dư nợ` HSTD
| | |
|---|---|
| **File** | `config.py`, `tabs/tab_khtd.py` |
| **Dấu hiệu** | Tổng `TH` trên KHTD nhỏ hơn `Tổng dư nợ` HSTD đúng 508.000.000 đồng dù logic lấy `TH` đã dùng `COT_TONG_DU_NO` |
| **Nguyên nhân** | Danh mục `CHUONG_TRINH_KHTD` chưa bao phủ hết các cặp `(Mã chương trình, Nguồn vốn)` đang tồn tại trong HSTD: thiếu `7_DP` (8 triệu) và thiếu `ma_ct 13` phía ĐP (500 triệu) |
| **Fix** | Bổ sung `7_DP` và `13_DP` vào `CHUONG_TRINH_KHTD`, đồng thời đưa `ma_ct 13` vào nhóm hiển thị KHTD Chi nhánh để row model mới tự map đủ vào nhập/xuất/tính TH |
| **Bài học** | Mỗi khi đối chiếu `TH` với HSTD, phải kiểm tra đủ coverage của danh mục `(ma_ct, nguồn vốn)` trước khi nghi ngờ helper tính tổng; thiếu một mã nhỏ cũng làm lệch toàn bộ số tổng |
| **Ngày fix** | 2026-07-11 |

### G18 — `📈 KHTD`: lỗi render `name 'MA_KEYS_CO_KHTD' is not defined` sau refactor
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` |
| **Dấu hiệu** | Mở tab `📈 Kế hoạch tín dụng` bị crash ngay khi render với thông báo `name 'MA_KEYS_CO_KHTD' is not defined` |
| **Nguyên nhân** | Sau khi refactor row model KHTD, `tab_khtd_nhap.py` vẫn dùng `MA_KEYS_CO_KHTD` ở nhiều nhánh nhập/xuất theo xã nhưng danh sách import từ `tab_khtd.py` đã bị rơi mất constant này |
| **Fix** | Bổ sung lại `MA_KEYS_CO_KHTD` vào import list của `tab_khtd_nhap.py` |
| **Bài học** | Khi tách hoặc dọn import sau refactor, cần grep lại toàn file theo tên constant dùng chung; lỗi thiếu import ở module-level sẽ chỉ lộ ra lúc render runtime |
| **Ngày fix** | 2026-07-11 |

### G19 — `📈 KHTD`: lỗi render `order_ma_ct is not defined` trong bảng readonly xuất
| | |
|---|---|
| **File** | `tabs/tab_khtd_xuat.py` |
| **Dấu hiệu** | Mở phần xuất/readonly của `📈 Kế hoạch tín dụng` bị crash tại `_hien_thi_bang_cn_readonly()` với lỗi `name 'order_ma_ct' is not defined` |
| **Nguyên nhân** | Sau refactor sang row model `_iter_khtd_cn_group_rows()`, biến cũ `order_ma_ct` đã bị loại bỏ nhưng dòng tính `tong_ct = len(order_ma_ct)` còn sót lại trong đầu hàm |
| **Fix** | Tính `tong_ct` trực tiếp từ tập `ma_ct` lấy ra từ row model mới, đồng thời tái sử dụng luôn `tat_ca_rows` cho phần đếm số CT có KH ở cuối hàm |
| **Bài học** | Khi thay mô hình lặp chính của một hàm, cần rà toàn bộ các biến phụ trợ như đếm tổng, thứ tự, header state; các biến này thường không còn compile error nhưng sẽ nổ khi runtime đi qua nhánh cũ |
| **Ngày fix** | 2026-07-11 |

### G20 — `📈 KHTD`: cột nhập KH hiển thị số thô, không có phân cách hàng nghìn nên khó rà
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` |
| **Dấu hiệu** | Ở phần nhập KHTD Chi nhánh, các ô `KH TW` / `KH ĐP` hiển thị số nguyên thô như `1250000`, rất khó nhìn và dễ nhập nhầm khi số lớn |
| **Nguyên nhân** | `data_editor` đang dùng `NumberColumn` cho cột KH editable, nên khi render/nhập Streamlit giữ số thô thay vì format theo kiểu `1.250.000` như người dùng mong muốn |
| **Fix** | Chuyển `KH TW` / `KH ĐP` sang `TextColumn`, dựng giá trị hiển thị bằng `_fmt_trieu_input()`, parse lại bằng `_parse_trieu_input()` khi trích patch lưu; nếu user gõ sai định dạng thì tạm giữ giá trị cũ và hiện cảnh báo |
| **Bài học** | Với màn nhập số liệu hành chính nhiều chữ số, ưu tiên hiển thị string đã format hơn là để `NumberColumn` số thô; readability quan trọng hơn việc ép kiểu số ngay ở lớp UI |
| **Ngày fix** | 2026-07-11 |

### G21 — `📈 KHTD`: nhóm hiển thị trong bảng nhập thiếu logic nghiệp vụ, gây khó rà soát
| | |
|---|---|
| **File** | `tabs/tab_khtd.py` |
| **Dấu hiệu** | Các nhóm trong bảng nhập KHTD Chi nhánh trộn các chương trình không cùng bản chất như `Nhà ở · DTTS · Xuất khẩu lao động` hoặc gom `13/26/99` vào `Hỗ trợ khác`, khiến người nhập phải dò lại từng dòng |
| **Nguyên nhân** | `KHTD_CN_NHOM_MA_CT` được gom chủ yếu theo lịch sử phát sinh mã và nhu cầu hiển thị tạm thời, chưa phản ánh nhóm nghiệp vụ dễ hiểu cho người dùng |
| **Fix** | Sắp lại nhóm theo ngữ nghĩa nghiệp vụ: hộ nghèo/cận nghèo/mới thoát nghèo; HSSV/việc làm/xuất khẩu lao động; nhà ở/nước sạch; vùng khó khăn; DTTS/miền núi; đối tượng đặc thù/khác |
| **Bài học** | Với màn nhập liệu nhiều dòng, chất lượng grouping ảnh hưởng trực tiếp đến tốc độ nhập và khả năng soát số; nên ưu tiên nhóm theo tư duy nghiệp vụ của người nhập hơn là theo cấu trúc mã nội bộ |
| **Ngày fix** | 2026-07-11 |

### G22 — `📈 KHTD`: lỗi render `KHTD_CN_NHOM_MA_CT is not defined`
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` |
| **Dấu hiệu** | Mở `📈 Kế hoạch tín dụng` báo `name 'KHTD_CN_NHOM_MA_CT' is not defined`, thường khi vào phần KHTD theo Xã hoặc xuất Excel/PDF theo xã |
| **Nguyên nhân** | `KHTD_CN_NHOM_MA_CT` được định nghĩa trong `tabs.tab_khtd` và `tab_khtd_nhap.py` vẫn dùng ở nhiều vòng lặp theo xã, nhưng import list sau refactor chỉ kéo `MA_KEYS_CO_KHTD` và helper, thiếu constant nhóm chương trình |
| **Fix** | Bổ sung `KHTD_CN_NHOM_MA_CT` vào import list từ `tabs.tab_khtd` trong `tab_khtd_nhap.py` |
| **Bài học** | Sau khi refactor constant dùng chung của KHTD, grep toàn bộ module con theo tên constant và kiểm tra import list tương ứng, nhất là các nhánh render lazy chỉ nổ khi user mở đúng sub-tab |
| **Ngày fix** | 2026-07-19 |

### G24 — `PGD_XA_MAP` tên xã không khớp HSTD — toàn bộ 22 PGD
| | |
|---|---|
| **File** | `config.py` dòng ~868-946 |
| **Dấu hiệu** | Mọi filter `df[df['Tên xã'].isin(PGD_XA_MAP[pgd])]` trả DataFrame rỗng; số liệu TH theo xã/phân tầng GQVL ĐP đều bằng 0 |
| **Nguyên nhân** | `PGD_XA_MAP` dùng "Xã La Ngà", "Phường Biên Hòa"... còn HSTD dùng "La Ngà", "Biên Hòa" (không prefix), hoặc lowercase "phường Tân Phú" cho đơn vị đô thị hóa gần đây. Prefix không khớp → join/isin fail hoàn toàn |
| **Fix** | Bỏ prefix "Xã "/"Phường " thừa; giữ lowercase "phường " cho đơn vị đã đô thị hóa; xác minh từng PGD bằng so sánh `HSTD parquet` với `PGD_XA_MAP`. 22/22 PGD đạt OK |
| **Ngày fix** | 2026-07-19 |

### G23 — `📈 KHTD theo Xã`: tóm tắt hiện trạng lấy số cả PGD và hiện nhiều dòng 0
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py` |
| **Dấu hiệu** | Trong `📈 Kế hoạch tín dụng` → `📍 KHTD theo Xã`, chọn một xã nhưng `Tổng cộng` và cột `TH` giống số toàn PGD; bảng tóm tắt/form vẫn hiện nhiều chương trình xã không có dư nợ, không giải ngân, không thu nợ trong năm |
| **Nguyên nhân** | `_du_lieu_khtd_pgd_cached()` chỉ lọc theo `COT_TEN_PGD`, chưa lọc tiếp `COT_TEN_XA`, rồi truyền dict `th_xa` đó cho từng xã. Bảng tóm tắt cũng render toàn bộ `KHTD_CN_NHOM_MA_CT` trước khi biết dòng nào thật sự có dữ liệu |
| **Fix** | Thêm `_du_lieu_khtd_xa_cached()` lọc đúng PGD + xã, tính `TH` từ `df_xa`; thêm `_ma_keys_phat_sinh_nam()` để giữ các chương trình có dư nợ/giải ngân/thu nợ năm; bảng tóm tắt và form mặc định chỉ hiện dòng có KH hoặc có phát sinh, kèm checkbox `Hiện tất cả chương trình` |
| **Bài học** | Tên biến `th_xa` phải phản ánh đúng cấp lọc dữ liệu. Với màn theo xã, không được tái sử dụng dict đã tính ở cấp PGD nếu không kèm lọc xã trước khi groupby |
| **Ngày fix** | 2026-07-19 |

---

## H. GSheet / Google Sheets

### H1 — Push GSheet thất bại
| | |
|---|---|
| **Kiểm tra theo thứ tự** | 1. `credentials.json` trong root? 2. Service account có quyền Editor? 3. `DCGIAM_SHEET_ID` đúng? 4. Quota API chưa vượt? |

### H2 — Sheet trống / thiếu số liệu GQVL
| | |
|---|---|
| **Nguyên nhân** | Chưa có `gqvl.parquet` (chưa upload/merge GQVL) hoặc thiếu cột nguồn vốn/PL NV/Mã NĐT |
| **Fix** | Upload lại GQVL → merge → kiểm tra parquet có cột theo `config.GQVL_COT_MAP` |

### H3 — `invalid_grant: Invalid JWT Signature` khi kết nối GSheet
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py` → `_ket_noi_gsheet()` ~dòng 38 |
| **Dấu hiệu** | UI báo: `Lỗi kết nối GSheet: ('invalid_grant: Invalid JWT Signature.', ...)` |
| **Nguyên nhân** | (1) Service Account key bị Google tự động **Disable** vì phát hiện exposed trên public GitHub repo; (2) Windows Time Service (`w32time`) không chạy → đồng hồ sai lệch |
| **Fix** | Xóa key cũ trên GCP Console → tạo key mới (JSON) → copy đè `credentials.json`. Đồng thời: `net start w32time && w32tm /resync /force`. Đã thêm bước đồng bộ thời gian vào `setup_env.bat` |
| **Ngày fix** | 2026-05-29 |

### H4 — Số cột Sheet không khớp COT (Google Form thêm cột mới)
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py` → `_doc_du_lieu()` ~dòng 67 |
| **Dấu hiệu** | `8 columns passed, passed data had 9 columns` |
| **Nguyên nhân** | Google Form thêm cột phụ (ví dụ "Cột 8" trống) → `data[1:]` có 9 cột nhưng `COT` chỉ có 8 |
| **Fix** | `df = pd.DataFrame([r[:len(COT)] for r in data[1:]], columns=COT)` — chỉ lấy N cột đầu, bỏ qua cột thừa |
| **Ngày fix** | 2026-05-29 |

### H6 — Deadline config kv_store định dạng cũ (nested dict)
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py` → `_doc_deadline_config()` |
| **Dấu hiệu** | `pd.to_datetime({"05/2026": "2026-06-01"})` → crash; hoặc trạng thái luôn "Chưa nộp" dù đã cài deadline |
| **Nguyên nhân** | Dữ liệu cũ trong kv_store có dạng `{loai: {ky: "YYYY-MM-DD"}}` (nested dict) sau khi bỏ concept "kỳ" → `deadline_cfg.get(loai)` trả về dict thay vì str |
| **Fix** | Normalize trong `_doc_deadline_config()`: nếu value là dict → lấy `list(val.values())[0]`; nếu là str → giữ nguyên. Không cần xóa dữ liệu cũ trong kv_store |
| **Ngày fix** | 2026-05-30 |

### H7 — Tên PGD từ Google Form không khớp DS_PGD
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py` → `_doc_du_lieu()` |
| **Dấu hiệu** | Tab Tổng quan hiển thị toàn 🔴 Chưa nộp dù PGD đã nộp; ma trận không khớp |
| **Nguyên nhân** | Google Form lưu tên PGD dạng `"Phòng giao dịch Long Thành"` nhưng `DS_PGD` dùng `"PGD Long Thành"` → `df[df["ten_pgd"] == pgd]` không match |
| **Fix** | Thêm hàm `_chuan_hoa_ten_pgd(raw)` normalize prefix: `"Phòng giao dịch "` / `"Phong giao dich "` / `"pgd "` → `"PGD "`. Gọi trong `_doc_du_lieu()` sau khi đọc sheet |
| **Ngày fix** | 2026-05-30 |

### H8 — GSheet API 500 Internal error khi đọc TIENDO_BAOCAO
| | |
|---|---|
| **File** | `services/report_submission_service.py` → `_doc_raw_values_sheet()`, `kiem_tra_ket_noi_gsheet()`; `tabs/tab_tien_do_nop.py` |
| **Dấu hiệu** | Tab Tiến độ nộp BC báo `🔴 GSheet lỗi: APIError: [500]: Internal error encountered` |
| **Nguyên nhân** | Lỗi tạm thời phía Google Sheets API; `get_all_values()` qua gspread không retry; health-check tab chỉ tìm `credentials.json` ở 1 path |
| **Fix** | Đọc qua REST `values/{tab}` trực tiếp, retry 3 lần khi 5xx/429; gom `kiem_tra_ket_noi_gsheet()` vào service; UI hiện gợi ý thử Làm mới |
| **Ngày fix** | 2026-07-04 |

### H9 — `AttributeError: 'Client' object has no attribute 'request'` khi đọc GSheet REST
| | |
|---|---|
| **File** | `services/report_submission_service.py` → `_doc_raw_values_sheet()`; `tabs/tab_theo_doi_nhap/data.py` → `doc_dieu_chinh_tu_dong()` |
| **Dấu hiệu** | UI báo `🔴 GSheet lỗi: AttributeError: 'Client' object has no attribute 'request'` hoặc màn theo dõi nhập liệu crash ở batchGet |
| **Nguyên nhân** | Code gọi thẳng `client.request(...)` / `ss.client.request(...)`, nhưng ở một số version `gspread` đối tượng `Client` không expose method này; request nằm ở `http_client.request(...)` hoặc `session.request(...)` |
| **Fix** | Thêm adapter `_gsheet_request_json()` để dò lần lượt `request` → `http_client.request` → `session.request`, rồi mới gọi REST API; giữ nguyên payload/flow hiện tại nhưng bỏ phụ thuộc vào 1 shape cụ thể của `gspread` |
| **Ngày fix** | 2026-07-05 |

### H10 — Tên báo cáo ở Cài đặt/Tổng quan lệch với Google Form khi đổi giai đoạn năm
| | |
|---|---|
| **File** | `services/report_submission_service.py` → `xay_dung_danh_muc_theo_doi()`, `gan_trang_thai()`, `tao_ma_tran_tien_do()`; `tabs/tab_tien_do_nop.py` |
| **Dấu hiệu** | `⚙️ Cài đặt thời hạn` vẫn hiện tên cũ như `Rà soát KHTD 2023-2026` trong khi Form đã dùng `Rà soát KHTD 2027-2030`; tab Tổng quan/Telegram có thể hiểu như 2 loại khác nhau nếu chưa bấm liên kết tay |
| **Nguyên nhân** | Deadline config lưu key lịch sử trong `kv_store`, còn dữ liệu GSheet dùng tên hiện tại trên Form; code trước đây chỉ match exact string, còn gợi ý lệch tên chỉ dùng để cảnh báo chứ chưa được áp dụng runtime |
| **Fix** | Tạo danh mục theo dõi hiệu lực: alias tên Form → key đang theo dõi khi match rõ ràng theo base name bỏ giai đoạn năm; UI ưu tiên hiển thị tên trên Form, trạng thái/ma trận/nhắc hạn dùng cùng mapping; thêm nút `🔗 Chuẩn hóa tất cả` để persist hàng loạt khi muốn |
| **Ngày fix** | 2026-07-05 |

### H5 — Loại bỏ "Kỳ báo cáo" khỏi Form/Sheet toàn bộ
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py` — toàn file |
| **Lý do** | Các loại báo cáo là sự kiện 1 lần (không lặp tháng/quý), không cần khái niệm "kỳ". PGD cũng muốn bỏ trường này khỏi Form. |
| **Thay đổi** | COT 8→7 cột (bỏ `ky_bao_cao`); deadline `{loai: {ky: dl}}` → `{loai: dl}`; bỏ dropdown kỳ ở 3 tab; ma trận PGD × Loại × Kỳ → PGD × Loại |
| **Ngày fix** | 2026-05-29 |

---

## I. Phân quyền / Role

### I3 — Card Xếp loại Tổ TK&VV tại Phân hệ Hỗ trợ địa bàn hiện toàn Chi nhánh

| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` dòng ~420, `services/tongquan_cdto_service.py` |
| **Dấu hiệu** | Tại Phân hệ Hỗ trợ địa bàn (ws_operation), card Xếp loại Tổ TK&VV trong tab "Thông tin chung" hiện số liệu 4.552 tổ (toàn CN) thay vì chỉ tổ của PGD/Hội sở đang đăng nhập |
| **Nguyên nhân** | `tab_tongquan.py` gọi `load_cdto_toan_cn()` + `render_totkvv_html()` mà không lọc theo `pgd_user`; `render_totkvv_html()` hardcode title "toàn Chi nhánh" |
| **Fix** | Khi `pgd_user` có giá trị: filter `cdto["df_raw"]` qua `loc_df(df, "pgd", pgd_user)`, recompute KPI, truyền `ten_don_vi=pgd_user` vào `render_totkvv_html()`; thêm param `ten_don_vi` vào hàm này |
| **Ngày fix** | 2026-06-02 |

### I4 — Menu `🗺️ Hỗ trợ địa bàn` hiển thị số liệu toàn CN dưới nhãn PGD (Biên Hòa)
| | |
|---|---|
| **File** | `app.py` → build context workspace `operation`; `workspaces/ws_operation.py` → `render_sidebar_menu()`, `render()` |
| **Dấu hiệu** | Sidebar hiển thị tiêu đề `🏦 PGD/Biên Hòa` nhưng số hồ sơ / tra cứu nhanh lại dựa trên DataFrame toàn Chi nhánh |
| **Nguyên nhân** | `pgd_user` có thể là alias (`PGD Biên Hòa`) không khớp giá trị thực trong cột `Tên PGD` (đang dùng `Hội sở Chi nhánh tỉnh`), trong đường dẫn `pgd_data/hoi_so_chi_nhanh_tinh`, và logic build `df_pgd` có nhánh rơi về `_df_op` (toàn CN) khi không lọc được |
| **Fix** | Chuẩn hóa `pgd_user` qua `ten_doc_ve_don_vi_chuan()` ngay sau login để load cache, đọc file PGD upload, context, sidebar và `ws_operation.render()` dùng cùng key nội bộ; với ngữ cảnh PGD thì không fallback về dữ liệu toàn CN |
| **Ngày fix** | 2026-06-29 |

### I5 — Quản lý user bị lẫn role giữa `📋 Phòng KH-NV` và `🗺️ Hỗ trợ địa bàn`
| | |
|---|---|
| **File** | `auth.py`, `app.py`, `db.py` |
| **Dấu hiệu** | Màn `👥 Quản lý Users` vẫn sinh role legacy `admin/manager/user`, admin PGD bấm vào màn quản lý user thì bị bật ngược về workspace Operation, còn `user_pgd` lại thấy gần như full menu PGD |
| **Nguyên nhân** | App đã route/workspace theo role mới (`admin_cn`, `admin_pgd`, `user_pgd`...) nhưng UI quản lý user vẫn tạo role cũ; nhánh `admin_users` chỉ render cho `admin_cn`; `get_tab_permissions("user_pgd")` cấp quá nhiều nhóm quyền |
| **Fix** | Tách quản lý user theo phân hệ: `admin_cn` chỉ tạo/sửa role KH-NV (`executive`, `admin_cn`, `manager_cn`, `chuyenvien_cn`), `admin_pgd` chỉ quản lý role PGD của đơn vị mình (`admin_pgd`, `manager_pgd`, `user_pgd`); cho `admin_pgd` mở được workspace `admin_users`; migration DB chuẩn hóa role legacy sang role mới; siết `user_pgd` về đúng quyền cơ bản |
| **Ngày fix** | 2026-06-29 |

### I6 — Không đăng nhập được theo phân hệ vì app auto-login `admin_cn`
| | |
|---|---|
| **File** | `app.py`, `auth.py` |
| **Dấu hiệu** | Mở app là vào thẳng tài khoản admin của `📋 Phòng KH-NV`, không hiện màn đăng nhập và không kiểm tra tài khoản/role thực tế; chuyển user khác dễ bị giữ lại `workspace`/context cũ |
| **Nguyên nhân** | Block `DEV MODE` trong `app.py` ép `logged_in=True` + `user_info=admin_cn`; sau login thật cũng chưa reset đầy đủ session liên quan đến phân hệ |
| **Fix** | Bỏ block auto-login; khi login thành công thì reset `workspace`, xóa `_ctx`, lưu lại `username`/`role` trong session để app tự route lại đúng phân hệ mặc định |
| **Ngày fix** | 2026-06-29 |

### I7 — Đăng nhập lại cùng phân hệ có thể crash vì `_ctx_cache_key` còn sót
| | |
|---|---|
| **File** | `auth.py`, `app.py` |
| **Dấu hiệu** | Sau khi đăng xuất rồi đăng nhập lại bằng tài khoản cùng role/PGD, app có thể crash ở nhánh đọc `st.session_state["_ctx"]` dù `_ctx` đã bị xóa |
| **Nguyên nhân** | Login chỉ xóa `_ctx` nhưng giữ `_ctx_cache_key`; nếu `_data_version` phiên mới trùng phiên cũ, `app.py` bỏ qua block load dữ liệu và cố dùng `_ctx` không còn tồn tại |
| **Fix** | Khi login/logout, xóa đồng bộ `_ctx`, `_ctx_cache_key`, map cache PGD, `_pgd_op_mtime_ss`, `df_full`; login cũng lưu `role` đã `normalize_role()` |
| **Ngày fix** | 2026-06-29 |

### I8 — Splash khởi động bị tắt nên không còn màn nhận diện hệ thống/phân hệ
| | |
|---|---|
| **File** | `app.py` |
| **Dấu hiệu** | Mở app đi thẳng vào login/workspace, không còn màn splash báo hiệu `VBSP-SCM`, `Phòng KH-NV`, `Hỗ trợ địa bàn`, `Ban Giám đốc` |
| **Nguyên nhân** | `main()` gán cứng `st.session_state["_splash_done"] = True` để debug nên splash không bao giờ hiển thị |
| **Fix** | Khôi phục `render_splash()` trong `app.py`, cho splash hiện 1 lần mỗi phiên và reset lại sau khi đăng xuất |
| **Ngày fix** | 2026-06-29 |

### I1 — Logic role sai / bỏ sót role mới
| | |
|---|---|
| **Nguyên nhân** | Check role bằng chuỗi thô: `if role == "admin"` thay vì dùng helper |
| **Fix** | Dùng `from auth import la_phan_he_cn, la_phan_he_pgd, la_executive, la_admin_cn, la_quan_ly_cn, normalize_role` |
| **Bảng nhanh** | `la_phan_he_cn(role)` → executive/admin_cn/manager_cn/admin/manager/chuyenvien_cn. `la_phan_he_pgd(role)` → admin_pgd/manager_pgd/user_pgd/user. `la_quan_ly_cn(role)` → admin_cn/admin/manager_cn/manager (không có executive/chuyenvien_cn). `la_admin_cn(role)` → admin_cn/admin |
| **Instances đã fix** | `app.py:311` (2026-06-09), `tab_khtd_giao_dc.py:769` (2026-06-09), `tab_cdtotkvv_pgd.py:594` (2026-06-09), `tab_nhiem_vu.py:568` (2026-05-23) |

### I3 — `chuyenvien_cn` thấy giao diện CBTD thay vì giao diện Manager
| | |
|---|---|
| **File** | `tabs/tab_nhiem_vu.py` dòng 568 (cũ) |
| **Dấu hiệu** | User role `chuyenvien_cn` vào tab Nhiệm vụ thấy "Nhiệm vụ được giao" thay vì "Tổng quan / Danh sách / Tạo mới" |
| **Nguyên nhân** | Check cứng `if role in ("admin_cn", "manager_cn"):` bỏ sót `chuyenvien_cn` |
| **Fix** | Dùng `la_phan_he_cn(role) and not la_executive(role)` — bao gồm tất cả role CN trừ executive |
| **Ngày fix** | 2026-05-23 |

### I2 — User thấy dữ liệu PGD khác
| | |
|---|---|
| **File** | `auth.py`, `ws_operation.py` |
| **Nguyên nhân** | Quên filter `st.session_state["user_info"]["pgd"]` |
| **Fix** | `pgd_user = st.session_state.get("user_info", {}).get("pgd")` → filter DataFrame theo `COT_TEN_PGD` |

---

## J. Python / Code Pattern

### J3 — Integration test patch sai target → ghi đè cache/hstd.parquet thật

| | |
|---|---|
| **File** | `tests/test_merge_regression.py` |
| **Dấu hiệu** | `cache/hstd.parquet` bị ghi đè từ 359.158 dòng (22 PGD) xuống ~36.350 dòng (2 PGD) lúc test chạy; audit log có entry `merge_hstd` từ test_regression với 2 PGD |
| **Nguyên nhân** | Test patch `config.CACHE_DIR` và `config.PGD_DATA_DIR` KHÔNG có tác dụng: `upload_service.py` import `CACHE_HSTD` ở module-level (đã bind trước khi patch chạy); `data/pgd.py` cũng import `PGD_DATA_DIR` ở module-level nên `duong_dan_pgd()` vẫn đọc pgd_data thật. Kết quả: merge đọc file Excel thật của 2 PGD, ghi 36.350 dòng vào `cache/hstd.parquet` thật |
| **Fix** | Thay `patch("config.CACHE_DIR", ...)` bằng `patch.object(svc, "CACHE_HSTD", str(tmp_path / "hstd.parquet"))` và thay `patch("config.PGD_DATA_DIR", ...)` bằng `patch.object(svc, "duong_dan_pgd", side_effect=fake_fn)`. Thêm autouse fixture block Telegram + snapshot background threads |
| **Ngày fix** | 2026-06-21 |

### J4 — Background snapshot thread ghi vào DB thật sau khi mock_db đã exit

| | |
|---|---|
| **File** | `tests/test_merge_du_lieu_toan_cn.py` — `TestMergeGQVL` (và HSTD, NQ11) |
| **Dấu hiệu** | audit_log có entry `luu_gqvl_snapshot` từ `test_user` với 2 dòng trong giờ test chạy; gqvl_snapshot table có data test nhỏ từ `test_user` |
| **Nguyên nhân** | `merge_du_lieu_toan_cn()` spawn daemon thread gọi `luu_gqvl_snapshot()` NGOÀI lock lock (dòng ~987 upload_service.py). Thread bắt đầu trong `with patch.object(svc.db, "ghi_audit")` nhưng có thể hoàn thành sau khi context exit → gọi `db.ghi_audit()` thật + `db.get_conn()` thật → ghi DB production |
| **Fix** | Thêm autouse fixture `mock_snapshot_services` trong test file: patch 4 hàm `luu_*_snapshot` trong module `snapshot_service` → background thread gọi mock thay vì DB thật |
| **Ngày fix** | 2026-06-21 |

### J2 — Stale closure df=None: sidebar render trước data load → tab trắng

| | |
|---|---|
| **File** | `workspaces/ws_management.py` + `app.py` |
| **Dấu hiệu** | Tab "Thông tin chung" (và mọi tab trong Phòng KH-NV) chỉ hiện "⚠️ Chưa có dữ liệu HSTD" dù parquet có đủ dữ liệu |
| **Nguyên nhân** | `app.py` sidebar render (dòng ~283) gọi `render_sidebar_menu(df=locals().get("df"))` TRƯỚC khi data load (dòng ~347). `df` chưa có → `None`. `_build_all_items(df=None)` tạo lambda closure với df=None. Hàm cũ lưu vào `st.session_state["_mgmt_all_items"]`. `render()` pop ra → dùng closures stale → tab nhận df=None |
| **Fix** | Xóa `st.session_state["_mgmt_all_items"] = all_items` khỏi `render_sidebar_menu()`. `render()` luôn build ALL_ITEMS fresh từ kwargs đầy đủ |
| **Ngày fix** | 2026-05-22 |

**Pattern nguy hiểm — tránh lặp:**
```python
# ❌ SAI — sidebar render trước data load
with st.sidebar:
    render_sidebar_menu(df=locals().get("df"))  # df=None vì chưa load!
    # → build closures với df=None → lưu vào session_state → render() dùng stale

# ✅ ĐÚNG — render() luôn build fresh
def render(**kwargs):
    ALL_ITEMS = _build_all_items(..., df=kwargs.get("df"), ...)  # df đúng từ ctx
```

---

### J7 — KeyError '\n background' khi render tab So sánh kỳ

| | |
|---|---|
| **File** | `tabs/tab_so_sanh_ky/_kpi_cards.py` L186 |
| **Dấu hiệu** | `❌ Lỗi render 📊 So sánh kỳ: '\n background'` |
| **Nguyên nhân** | `_CARD_CSS.format(bg_from=..., ...)` — Python dùng str `.format()` trên chuỗi CSS có cả format placeholder `{bg_from}` lẫn CSS class braces `{...}`. Khi gặp `.mini-card {\n    background:`, Python mở field mode tại `{`, quét đến `}` đầu tiên → field name = `\n background` → KeyError |
| **Fix** | Thay `.format(...)` bằng vòng lặp `.replace(k, v)` trong `_inject_card_css()` — str.replace không phân tích cú pháp nên không bị nhầm CSS braces |
| **Ngày fix** | 2026-06-09 |

---

### J3 — TypeError: tuple indices must be integers or slices, not tuple (openpyxl column width)

| | |
|---|---|
| **File** | `services/tien_do_excel_service.py` dòng ~79, ~137 |
| **Dấu hiệu** | `TypeError: tuple indices must be integers or slices, not tuple` khi gọi `xuat_excel_tien_do()` |
| **Nguyên nhân** | `ws[row_start:row_end]` trả về tuple of row tuples (openpyxl); dùng thêm `[:, col_idx-1]` theo kiểu numpy 2D — không hợp lệ với plain tuple |
| **Fix** | Thay `for cell in ws[ws.min_row:ws.max_row][:, col_idx-1]` → `for r in range(ws.min_row, ws.max_row+1): ws.cell(row=r, column=col_idx)` |
| **Ngày fix** | 2026-05-23 |

---

### J4 — `except Exception:` không bind `e` nhưng dùng `e` trong logger

| | |
|---|---|
| **File** | `tabs/tab_tien_do.py`, `services/tien_do_service.py` |
| **Dấu hiệu** | `NameError: name 'e' is not defined` trong except block |
| **Nguyên nhân** | Viết `except Exception:` (không có `as e`) nhưng body vẫn dùng `logger.error(..., e, ...)` — `e` không được định nghĩa. Ngoài ra logger message `"Lỗi trong khối except"` không mang thông tin context. |
| **Fix** | Đổi thành `except Exception as e:  # conv: skip`. Với lỗi parse/lookup nhỏ dùng `logger.warning()` thay `logger.error()`. Đặt message mô tả hành động: `"Lỗi tạo task '%s': %s"`, `"Không parse ngày deadline task_id=%s: %s"`, v.v. |
| **Ngày fix** | 2026-05-23 (lần 1: tien_do_service.py); 2026-05-24 (lần 2: 8 chỗ còn lại trong _render_quan_ly_task, _fmt_task, _fmt_cap_nhat_opt, _fmt_task_pdf) |

---

### J6 — `from_dict()` bỏ sót field date mới → `.strftime()` crash khi xuất biểu mẫu

| | |
|---|---|
| **File** | `services/xlrr_service.py` dòng ~134 |
| **Dấu hiệu** | `AttributeError: 'str' object has no attribute 'strftime'` khi bấm nút xuất 01/XLN hoặc 02/XLN sau lần load hồ sơ từ kv_store |
| **Nguyên nhân** | `HoSoRuiRo.from_dict()` chỉ convert `["ngay_vay", "ngay_dh", "ngay_rr"]` từ string→date, nhưng `ngay_ky_01` và `ngay_lap_02` (2 field mới) bị bỏ sót → sau khi đọc từ kv_store, 2 field này vẫn là ISO string → `.strftime()` crash ở tab xuất biểu mẫu |
| **Fix** | Thêm `"ngay_ky_01", "ngay_lap_02"` vào list convert trong `from_dict()` |
| **Ngày fix** | 2026-05-25 |
| **Pattern nguy hiểm** | Mỗi khi thêm field `Optional[date]` mới vào dataclass, **bắt buộc** thêm tên field đó vào cả `to_dict()` và `from_dict()`. Chỉ thêm một chiều sẽ gây crash âm thầm khi load. |

---

### J5 — `_frozen_importlib._DeadlockError`: circular import giữa `data` và `services`

| | |
|---|---|
| **File** | `services/upload_service.py` dòng ~37 |
| **Dấu hiệu** | `_DeadlockError: deadlock detected by _ModuleLock('data.pgd')` khi Streamlit khởi động; traceback: `app.py → data.__init__ → data.hstd → services.__init__ → upload_service → data.pgd` |
| **Nguyên nhân** | `upload_service.py` import `from data.pgd import duong_dan_pgd` ở module-level. Khi `data.hstd` (đang load trong `data.__init__`) import `from services.data_quality import ...`, Python phải chạy `services/__init__.py` → kéo `upload_service` → lại cần lock `data.pgd` (đang bị `data.__init__` giữ) → deadlock. |
| **Fix** | Chuyển import `from data.pgd import duong_dan_pgd` thành lazy wrapper: `def _duong_dan_pgd(ten_pgd, loai): from data.pgd import duong_dan_pgd as _fn; return _fn(ten_pgd, loai)` — thay mọi chỗ dùng `duong_dan_pgd(...)` bằng `_duong_dan_pgd(...)` |
| **Pattern** | Bất cứ khi nào `services/` import `data.*` ở module-level và `data/` import `services` → phải lazy-load. |
| **Ngày fix** | 2026-05-24 |

**Rule phòng ngừa:**
```python
# ❌ SAI — module-level import trong services/ kéo ngược data/
# services/upload_service.py
from data.pgd import duong_dan_pgd   # deadlock nếu data đang load services

# ✅ ĐÚNG — lazy import trong hàm wrapper
def _duong_dan_pgd(ten_pgd: str, loai: str) -> str:
    from data.pgd import duong_dan_pgd as _fn  # chỉ chạy khi hàm được gọi
    return _fn(ten_pgd, loai)
```

---

### J7 — TypeError: `'<' not supported between instances of 'int' and 'list'` từ min([N], int)

| | |
|---|---|
| **File** | `data/hstd.py` dòng 376 trong `doc_dienbao_matrix()` |
| **Dấu hiệu** | Tab Cân đối → sub-tab "Dữ liệu thô" → `❌ Lỗi: '<' not supported between instances of 'int' and 'list'` |
| **Nguyên nhân** | Trae viết `min([5], len(df_raw))` thay vì `min(5, len(df_raw))`. Python's `min(a,b)` thực hiện `b < a` để so sánh → `int < list` → TypeError. |
| **Fix** | `min([5], len(df_raw))` → `min(5, len(df_raw))` |
| **Ngày fix** | 2026-06-04 |

---

### J1 — UnboundLocalError: cannot access local variable 'X' where it is not associated with a value
| | |
|---|---|
| **File** | Bất kỳ file nào có `from x import Y` ở cả top-level lẫn trong thân hàm |
| **Dấu hiệu** | `UnboundLocalError: cannot access local variable 'Path' where it is not associated with a value` |
| **Nguyên nhân** | Import cục bộ `from pathlib import Path` trong thân hàm khiến Python coi `Path` là local variable cho toàn bộ hàm. Dòng code dùng `Path` phía trên import cục bộ sẽ bị `UnboundLocalError`. |
| **Fix** | Xóa import cục bộ thừa, dùng top-level import có sẵn. Chỉ import trong hàm khi thực sự cần lazy-load. |
| **Ngày fix** | 2026-05-22 |

---

### D2 — `OperationalError: no such column` do tên cột không khớp schema mới

| | |
|---|---|
| **File** | `services/ktnb_service.py` dòng ~821 |
| **Dấu hiệu** | `OperationalError: no such column: ten_dot` khi gọi `tong_hop_ktnb_theo_nam()` hoặc `xuat_bao_cao_ktnb_excel()` |
| **Nguyên nhân** | Hàm query `SELECT id, ten_dot, ...` nhưng bảng `ktnb_dot_kiem_tra` không có cột `ten_dot` — chỉ có `ten_pgd_ks` (xem schema `db.py:433`). Code mới tạo dùng nhầm tên cột. |
| **Fix** | Thay `ten_dot` → `ten_pgd_ks` trong SQL query + `dot["ten_dot"]` → `dot["ten_pgd_ks"]` (3 chỗ: dòng 821, 844, 892) |
| **Ngày fix** | 2026-05-26 |

**Pattern phòng ngừa:** Mỗi khi viết SQL query mới, đối chiếu tên cột với schema trong `db.py` hoặc `SCHEMA.md` trước.

---

### J7 — Key mismatch `df_sk_gqvl` / `df_gqvl` → dữ liệu GQVL luôn `None` trong tab

| | |
|---|---|
| **File** | `app.py` dòng ~561 (ctx dict), `tabs/tab_tracuu.py` dòng ~447, `tabs/tab_baocao/components/export_panel.py` |
| **Dấu hiệu** | Tab Tra cứu / Báo cáo: filter GQVL không hoạt động, số liệu GQVL = 0 hoặc None dù đã merge |
| **Nguyên nhân** | `app.py` truyền key `df_sk_gqvl` vào ctx dict, nhưng `tab_baocao` và `tab_tracuu` đọc bằng `kwargs.get("df_gqvl")` → luôn nhận `None` |
| **Fix** | Đổi tên biến trong `app.py`: `df_sk_gqvl` → `df_gqvl` (cả khai báo lẫn truyền vào ctx); đồng bộ `tab_tracuu.py`: `_xay_gqvl_nq11_set(df_sk_gqvl)` → `df_gqvl` |
| **Pattern phòng ngừa** | Mỗi khi thêm key vào ctx dict ở `app.py`, kiểm tra ngay tên key tại nơi đọc (`kwargs.get("...")`) trong tab. Không đổi tên biến 1 chiều. |
| **Ngày fix** | 2026-06-02 |

---

## K. Performance / Tốc độ

### K1 — `df.iterrows()` trong validation — upload PGD chậm 15-30 giây
| | |
|---|---|
| **File** | `services/validation_service.py` → `_validate_pgd_xa_relationship()` |
| **Dấu hiệu** | Upload file HSTD/GQVL/NQ11 treo lâu, UI không phản hồi; tab loading chậm sau khi upload (vì UI thread bị block) |
| **Nguyên nhân** | `for _, row in df.iterrows():` duyệt từng dòng trong Python → O(n) với overhead Python interpreter. DataFrame 50k rows → 15-30 giây. `iterrows()` chậm hơn vectorized ~100x |
| **Fix** | Thay bằng vectorized: lấy distinct pairs `(xa, pgd)` → `.map(xa_to_pgd)` → so sánh → tìm mismatch. Không cần vòng lặp Python. `iterrows()` chỉ dùng cho ≤3 hàng mẫu hiển thị lỗi |
| **Pattern tránh** | `for _, row in df.iterrows():` khi validate/transform toàn DataFrame. Thay bằng `.map()`, `.isin()`, `.merge()`, boolean mask |
| **Ngày fix** | 2026-05-24 |

### K2 — `@st.cache_data` pickle overhead — tab "So sánh kỳ" treo khi đọc baseline
| | |
|---|---|
| **File** | `data/hstd.py` → `doc_baseline_merged()` |
| **Dấu hiệu** | Tab "So sánh kỳ" treo 3-8 giây ngay cả khi baseline đã cache; lần đầu (cache miss) treo 30-120 giây |
| **Nguyên nhân** | `@st.cache_data` pickle/unpickle toàn bộ DataFrame mỗi lần trả kết quả — ngay cả cache hit. DataFrame 22 PGD × 50k+ dòng → serialize/deserialize tốn nhiều giây. Roll rate `st.expander` (không lazy) khiến `join_by_loan()` luôn chạy. `agg_theo_dvut()` không có cache |
| **Fix** | (1) Đổi `@st.cache_data` → `@st.cache_resource` cho `doc_baseline_merged()` — trả cùng object, không pickle. Thêm `.copy()` tại nơi gọi để tránh mutate. (2) Đổi `st.expander` → `_lazy_expander` cho section Roll rate. (3) Thêm `@st.cache_data` cho `agg_theo_dvut()`. (4) Cache groupby trong `_chart_tang_truong()` bằng `_cached_group()` module-level |
| **Pattern tránh** | `@st.cache_data` cho hàm trả DataFrame lớn (>10MB). Dùng `@st.cache_resource` + `.copy()` tại nơi gọi. `st.expander(expanded=False)` vẫn execute code bên trong — dùng `lazy_expander` từ `utils.py` |
| **Ngày fix** | 2026-05-24 |

### K3 — Categorical "values should be unique if codes is not None" — tab So sánh kỳ
| | |
|---|---|
| **File** | `services/so_sanh_ky_service.py` → `group_bien_dong()`, `agg_theo_pgd()` |
| **Dấu hiệu** | Tab "📊 So sánh kỳ" crash với message "values should be unique if codes is not None" khi render section HSTD |
| **Nguyên nhân** | HSTD parquet đọc về có cột string (VD: `Tên chương trình`, `Tên PGD`) dạng `CategoricalDtype`. Khi `groupby(dim, dropna=False)` trả `CategoricalIndex`, sau đó `merge(g_ht, g_bl, on=dim)` pandas cố union 2 category list → tạo ra duplicate categories → raise lỗi Categorical |
| **Fix** | Trong `group_bien_dong`: convert `df[dim]` từ Categorical → object trước `groupby`, và `g[dim]` → object sau `reset_index()`. Trong `agg_theo_pgd`: convert `COT_TEN_PGD` → object trước `groupby` và kết quả sau `reset_index()` |
| **Pattern tránh** | `groupby()` + `merge()` trên Categorical column từ parquet mà không normalize. Luôn dùng `if isinstance(df[col].dtype, pd.CategoricalDtype): df[col] = df[col].astype(object)` trước groupby/merge |
| **Ngày fix** | 2026-05-25 |

### K4 — Categorical "values should be unique" — tab Cảnh báo Tín dụng (Tổng hợp)
| | |
|---|---|
| **File** | `tabs/tab_canh_bao_nqh.py` → `_render_tong_hop()` |
| **Dấu hiệu** | Sub-tab "Tổng hợp" crash với "values should be unique if codes is not None" khi render bảng Tổng hợp cảnh báo theo PGD |
| **Nguyên nhân** | `df_full_loc[COT_TEN_PGD]` và `df_kh_loc[COT_TEN_PGD]` từ parquet có dtype Categorical. Khi `groupby(COT_TEN_PGD)` tạo CategoricalIndex → pandas safe_sort crash |
| **Fix** | Thêm đoạn convert Categorical → object cho cả `df_full_loc` và `df_kh_loc` trước khi dùng groupby: `if isinstance(_df[COT_TEN_PGD].dtype, pd.CategoricalDtype): _df[COT_TEN_PGD] = _df[COT_TEN_PGD].astype(object)` |
| **Ngày fix** | 2026-05-25 |

### K7 — PGD upload file mới không tự reload dữ liệu ở workspace Operation
| | |
|---|---|
| **File** | `app.py` dòng ~501-504 |
| **Dấu hiệu** | CN role vào workspace Operation sau khi PGD upload file mới → vẫn thấy dữ liệu cũ; phải bấm "Làm mới cache" thủ công |
| **Nguyên nhân** | `_data_version` chỉ gồm timestamp của file hệ thống (HSTD/NQ11/GQVL parquet). Khi PGD upload `hstd_latest.xlsx` mà chưa merge, `_hstd_ts` không đổi → `_ctx_cache_key` vẫn khớp → block load data bị skip → PGD data mới không được đọc |
| **Fix** | Tính `_pgd_op_ts` (mtime PGD upload files) trước `_data_version`. PGD role: check 1 file (rẻ). CN role: quét 22 thư mục với session cache 30s. Thêm `_pgd_op_ts` vào `_data_version`. Bên trong loading block dùng lại giá trị đã tính |
| **Pattern tránh** | Cache key chỉ dựa vào hệ thống file parquet — nếu có nguồn dữ liệu phụ (PGD upload) cũng cần đưa mtime vào key |
| **Ngày fix** | 2026-06-11 |

### K6 — `_enrich_hstd` chạy 2 lần mỗi session load
| | |
|---|---|
| **File** | `app.py` dòng ~595 |
| **Dấu hiệu** | F5 reload / workspace switch chậm hơn cần thiết |
| **Nguyên nhân** | `_enrich_hstd()` luôn trả về object mới (do `df = df.copy()` bên trong). `if df_full is not df:` được check SAU khi gọi → luôn True → enrich chạy 2 lần dù `df` và `df_full` cùng nguồn |
| **Fix** | `_df_was_df_full = df is df_full` trước khi gọi. Nếu `_df_was_df_full`: `df_full = df` (dùng chung kết quả). Else: enrich `df_full` riêng |
| **Ngày fix** | 2026-06-11 |

### K5 — DB write mỗi Streamlit rerun — sidebar reload chậm mỗi lần click
| | |
|---|---|
| **File** | `alert_center.py` → `_xoa_da_doc_cu()`, `_lay_da_doc()` |
| **Dấu hiệu** | App reload chậm sau mỗi tương tác widget bất kỳ; sidebar giật lag |
| **Nguyên nhân** | `render_alert_sidebar()` gọi `_xoa_da_doc_cu()` mỗi rerun → luôn gọi `_lay_da_doc()` (SQLite read) + `_luu_da_doc()` (SQLite write + audit_log write). Không có guard "chỉ ghi khi thay đổi". `_lay_da_doc()` cũng được gọi thêm lần 2 ngay sau đó |
| **Fix** | (1) `_lay_da_doc()`: thêm session_state cache 60s — không đọc DB mỗi rerun. (2) `_luu_da_doc()`: cập nhật session cache sau khi ghi. (3) `_xoa_da_doc_cu()`: guard `if pruned != da_doc` — chỉ ghi khi set thực sự thay đổi. Kết quả: 0 DB I/O trong 60s sau lần ghi/đọc cuối |
| **Pattern tránh** | Gọi `db.ghi_kv()` / `db.ghi_audit()` trong hàm chạy mỗi rerun mà không có cache/guard |
| **Ngày fix** | 2026-06-11 |

### K8 — `📈 Kế hoạch tín dụng` phần nhập load chậm do quét HSTD/GQVL lặp lại mỗi rerun
| | |
|---|---|
| **File** | `tabs/tab_khtd_nhap.py`, `tabs/tab_khtd_xuat.py` |
| **Dấu hiệu** | Mở tab `🏛️ KHTD Chi nhánh` hoặc đổi lựa chọn trong phần nhập thấy màn hình khựng/lâu; sau khi bấm lưu hoặc xem trước phải chờ lâu mới render lại |
| **Nguyên nhân** | Cùng một rerun đang quét `df_full` nhiều lần: `_tab_khtd_chi_nhanh()` tự tính `TH theo CT` + `GQVL phân tầng`, rồi `_hien_thi_bang_cn_readonly()` lại đọc `gqvl.parquet` và tính `GQVL phân tầng` thêm lần nữa. Ngoài ra caller còn gọi lại `_tinh_th_nsvsmt_dp_phan_tang()` dù `_tinh_thuc_hien_theo_ct()` đã gộp sẵn. Một nhánh phụ nữa là helper đọc parquet lớn dùng tham số `_ts`; với Streamlit, prefix `_` bị loại khỏi cache key nên `mtime` không thực sự bust cache. |
| **Fix** | (1) Thêm cache theo `mtime` cho `TH` KHTD Chi nhánh, dữ liệu TH/ten_map theo PGD, và danh sách CT hiển thị màn Chi nhánh. (2) Bỏ lần tính trùng `NSVSMT`. (3) Cho `_hien_thi_bang_cn_readonly()` nhận `th_gqvl` từ caller để không tự đọc lại `gqvl.parquet` khi caller đã có sẵn kết quả. (4) Đổi reader parquet lớn sang `st.cache_resource` và đổi tham số `_ts` → `ts` để `mtime` thật sự nằm trong cache key. |
| **Ngày fix** | 2026-06-27 |

### K9 — `📈 Kế hoạch tín dụng` vẫn mất 10 giây do quét từng dòng HSTD
| | |
|---|---|
| **File** | `tabs/tab_khtd.py` → `_quet_ct_co_du_no()` |
| **Dấu hiệu** | Sau tối ưu K8, lần cache miss đầu tiên vẫn chờ lâu; profiler ghi nhận riêng helper quét chương trình mất khoảng 10 giây |
| **Nguyên nhân** | Helper dùng vòng lặp Python với `.iat` qua 366.503 dòng HSTD để tìm vài chục cặp `(Mã CT, Nguồn vốn)` duy nhất |
| **Fix** | Lọc và `drop_duplicates()` bằng pandas vector hóa trước, sau đó chỉ map các cặp duy nhất; đồng thời lấy tên HSTD đầu tiên không rỗng theo từng cặp |
| **Test** | `tests/test_khtd_quets.py::test_quet_ct_vectorized_loc_du_no_va_uu_tien_ten_hstd` |
| **Ngày fix** | 2026-07-11 |

---

## Lệnh debug nhanh

```bash
# 20 audit log gần nhất
sqlite3 data.db "SELECT created_at, username, action, detail FROM audit_log ORDER BY created_at DESC LIMIT 20"

# Tất cả key kv_store
sqlite3 data.db "SELECT key, length(value), updated_by, updated_at FROM kv_store ORDER BY updated_at DESC"

# Kiểm tra merge đã chạy chưa
sqlite3 data.db "SELECT key, value FROM kv_store WHERE key LIKE 'merge_meta%'"

# Tìm lỗi merge gần nhất
sqlite3 data.db "SELECT * FROM audit_log WHERE action LIKE '%merge%loi%' ORDER BY created_at DESC LIMIT 10"

# Chạy debug mode
DEBUG=1 streamlit run app.py
```

---

## J. Code Pattern

### J01 — alert_center.py ngưỡng khẩn/cảnh báo sai
| | |
|---|---|
| **File** | `alert_center.py` → `canh_bao_no_khoanh_sap_het_han()` ~dòng 226 |
| **Dấu hiệu** | Test fail: 60 ngày bị tính là `so_khan` thay vì `so_canh_bao` |
| **Nguyên nhân** | Threshold "khẩn" hardcode 120 ngày thay vì 30 ngày; "cảnh báo" khoảng 120–180 thay vì 30–180 |
| **Fix** | `khan = df[df['con_lai'] <= 30]`; `canh_bao = df[(df['con_lai'] > 30) & (df['con_lai'] <= 180)]` |
| **Test** | `test_alert_center.py::TestCanhBaoNoKhoanh` |
| **Ngày fix** | 2026-05-25 |

### J02 — NameError `_ts` trong doc_baseline_merged fallback
| | |
|---|---|
| **File** | `data/hstd.py` → `doc_baseline_merged()` ~dòng 162 |
| **Dấu hiệu** | `NameError: name '_ts' is not defined` khi render `tab_so_sanh_ky` |
| **Nguyên nhân** | Hàm `doc_baseline_merged(nam)` không có tham số `_ts` nhưng fallback gọi `doc_baseline(nam, _ts)` |
| **Fix** | Đổi thành `return doc_baseline(nam)` (dùng default `_ts=0`) |
| **Test** | `test_smoke_imports.py::TestSmokeRender::test_render[tabs.tab_so_sanh_ky]` |
| **Ngày fix** | 2026-05-25 |

### J03 — patch.object svc.duong_dan_pgd AttributeError (21 test merge fail)
| | |
|---|---|
| **File** | `services/upload_service.py` → `_duong_dan_pgd()` ~dòng 39 |
| **Dấu hiệu** | `AttributeError: module 'services.upload_service' does not have attribute 'duong_dan_pgd'` |
| **Nguyên nhân** | Hàm wrapper đặt tên `_duong_dan_pgd` (private); test cần `patch.object(svc, "duong_dan_pgd", ...)` nhưng tên không khớp |
| **Fix** | Đổi tên `_duong_dan_pgd` → `duong_dan_pgd` (public) và cập nhật toàn bộ chỗ gọi trong file |
| **Test** | `test_merge_du_lieu_toan_cn.py` — 21 tests |
| **Ngày fix** | 2026-05-25 |

### J04 — SQLite CASCADE DELETE không hoạt động (PRAGMA foreign_keys OFF)
| | |
|---|---|
| **File** | `db.py` ~dòng 31 + `tests/test_ktnb_db.py` fixture |
| **Dấu hiệu** | `test_delete_dot_cascade` fail: row con vẫn còn sau DELETE cha |
| **Nguyên nhân** | SQLite mặc định `foreign_keys=OFF`; cả production và test fixture đều không bật |
| **Fix** | Thêm `PRAGMA foreign_keys=ON` vào `db.py` connection setup và fixture `in_memory_db` |
| **Test** | `test_ktnb_db.py::TestKtnbDotKiemTra::test_delete_dot_cascade` |
| **Ngày fix** | 2026-05-25 |

### J05 — UnboundLocalError `fmt` trong `_subtab_lap_hs_pgd()` do import cục bộ
| | |
|---|---|
| **File** | `tabs/tab_xu_ly_rui_ro.py` → `_subtab_lap_hs_pgd()` ~dòng 158 |
| **Dấu hiệu** | `UnboundLocalError: cannot access free variable 'fmt' where it is not associated with a value in enclosing scope` khi mở tab Xử lý Rủi ro |
| **Nguyên nhân** | `from utils import fmt` trong thân hàm khiến Python coi `fmt` là local variable cho toàn bộ hàm. Lambda `lambda x: fmt(x) if pd.notna(x) else ""` ở dòng trên import cục bộ bị lỗi vì `fmt` chưa được gán trong local scope tại thời điểm lambda chạy. |
| **Fix** | Xóa `from utils import fmt` dư thừa — `fmt` đã được import ở module level (dòng 55) |
| **Ngày fix** | 2026-05-25 |

### J13 — Test gửi tin nhắn Telegram thật khi chạy `luu_pgd_file()`
| | |
|---|---|
| **File** | `tests/test_upload_supplement.py`, `tests/conftest.py` |
| **Dấu hiệu** | Khi chạy `pytest` (RUN ALL TEST), Telegram nhận tin nhắn thật "📤 PGD Long Thành vừa upload HSTD" — mỗi test gọi `luu_pgd_file()` gửi 1 HTTP request tới Telegram API |
| **Nguyên nhân** | `luu_pgd_file()` trong `upload_service.py` gọi `gui_thong_bao_upload_pgd()` — hàm này gửi HTTP POST thật qua `requests`. Test không mock `services.telegram_service.gui_thong_bao_upload_pgd`. Các test merge khác đã mock `gui_thong_bao_merge` nhưng bỏ sót `gui_thong_bao_upload_pgd` |
| **Fix** | (1) `test_upload_supplement.py`: thêm `@pytest.fixture(autouse=True)` mock `gui_thong_bao_upload_pgd`. (2) `conftest.py`: thêm fixture toàn cục block cả `gui_thong_bao_upload_pgd` + `gui_thong_bao_merge` để bảo vệ toàn bộ test suite |
| **Ngày fix** | 2026-07-10 |

### J06 — GOM vào CN luôn dùng tháng hiện tại, bỏ qua tháng user chọn
| | |
|---|---|
| **File** | `tabs/tab_xu_ly_rui_ro.py` → `_subtab_tong_hop_cn()` ~dòng 993-1075 |
| **Dấu hiệu** | Bấm "GOM vào CN" hoặc "Merge file Excel" luôn lưu vào tháng hiện tại (`now.month`), kể cả khi user đang xem kỳ khác; bảng Rà soát (Bước 3) cũng đọc nhầm tháng |
| **Nguyên nhân** | Ba chỗ dùng `thang_hien_tai = now.month` thay vì biến `thang_cn` từ selectbox; thêm vào đó vòng lặp `for thang in range(1, 13)` gom cả 12 tháng thay vì chỉ tháng đang chọn |
| **Fix** | Thêm `thang_cn = st.selectbox("Tháng lưu CN", ...)` (layout 2 cột cạnh `nam`); xóa vòng lặp 12 tháng → dùng `LuuTruXLRR.doc_pgd(slug, nam, thang_cn)`; thay 3 chỗ `thang_hien_tai = now.month` → `thang_cn` |
| **Ngày fix** | 2026-05-26 |

---

### J7 — `except Exception: pass` nuốt lỗi im trong hàm visualization/helper

| | |
|---|---|
| **File** | `workspaces/ws_operation.py` → `_heatmap_rui_ro_xa()` ~dòng 778 |
| **Dấu hiệu** | Cột "Tăng trưởng" trong heatmap Xã luôn hiện "—" dù có dữ liệu snapshot; không có log lỗi nào → không biết tại sao |
| **Nguyên nhân** | Khối try/except bọc toàn bộ snapshot lookup dùng `except Exception: pass` — nếu `snapshot_service.doc_snapshot()` raise lỗi (file missing, schema mismatch...) thì bị bỏ qua hoàn toàn |
| **Fix** | `except Exception as e: logger.error("_heatmap_rui_ro_xa snapshot: %s", e, exc_info=True)` |
| **Ngày fix** | 2026-05-30 |

**Pattern nguy hiểm — tránh lặp:**
```python
# ❌ SAI — không biết gì khi lỗi
try:
    snapshot_data = doc_snapshot(ky)
    ...
except Exception:
    pass

# ✅ ĐÚNG — fallback im lặng nhưng ghi log để debug
try:
    snapshot_data = doc_snapshot(ky)
    ...
except Exception as e:
    logger.error("ten_ham snapshot: %s", e, exc_info=True)
    # tt giữ nguyên None → hiển thị "—" là đúng hành vi fallback
```

---

### J8 — `DataFrame.get(key, default_series)` deprecated trong pandas 2.x

| | |
|---|---|
| **File** | `workspaces/ws_operation.py` → `_render_dashboard_nang_cao_pgd()` ~dòng 865 |
| **Dấu hiệu** | `FutureWarning: DataFrame.get with a non-scalar key is deprecated` trong log; hành vi có thể thay đổi giữa các phiên bản pandas |
| **Nguyên nhân** | `df_pgd.get(COT_DU_NO_TH, pd.Series([0]*len(df_pgd))).sum()` — kết hợp guard `if col in df.columns` bên ngoài với `.get(col, default)` bên trong là thừa; pandas 2.x deprecated `df.get(key)` cho dict-style access với non-scalar |
| **Fix** | `pd.to_numeric(df_pgd[COT_DU_NO_TH], errors="coerce").sum() if COT_DU_NO_TH in df_pgd.columns else 0` |
| **Ngày fix** | 2026-05-30 |

**Pattern chuẩn — dùng nhất quán:**
```python
# ❌ SAI — thừa + deprecated
val = df.get(COT_X, pd.Series([0]*len(df))).sum() if COT_X in df.columns else 0

# ✅ ĐÚNG — rõ ràng, không deprecated
val = pd.to_numeric(df[COT_X], errors="coerce").sum() if COT_X in df.columns else 0
```

---
## Template: Ghi nhận bug mới

### J09 — `hasattr(ngay_nop, "__class__")` redundant check in phan_loai_trang_thai
| | |
|---|---|
| **File** | `services/report_submission_service.py` → `phan_loai_trang_thai()` L557, `lay_danh_sach_can_nhac()` L713 |
| **Dấu hiệu** | Code dùng `ngay_nop is None or (hasattr(ngay_nop, "__class__") and pd.isna(ngay_nop))` — `hasattr` luôn True với mọi object Python, check dư thừa |
| **Nguyên nhân** | Cố gắng phân biệt None với NaN, nhưng `pd.isna(None)` đã trả True → điều kiện đơn giản có thể là `pd.isna(ngay_nop)` |
| **Fix** | Rút gọn thành `if pd.isna(ngay_nop): return "chua_nop"` ở cả 2 nơi |
| **Ngày fix** | 2026-07-05 |

### J10 — `_gan_khoa_theo_doi` double call in `tao_ma_tran_tien_do`
| | |
|---|---|
| **File** | `services/report_submission_service.py` → `tao_ma_tran_tien_do()` L744-745 |
| **Dấu hiệu** | `df = gan_trang_thai(df, deadline_cfg)` (gọi `_gan_khoa_theo_doi` lần 1) rồi `_, dm = _gan_khoa_theo_doi(df, deadline_cfg)` (lần 2) — lãng phí |
| **Nguyên nhân** | `gan_trang_thai` không trả về `dm` nên phải gọi lại để lấy danh mục |
| **Fix** | Đổi `gan_trang_thai` trả về tuple `(df, dm)`. Cập nhật 3 call site: `tao_ma_tran_tien_do`, `tab_tien_do_nop.py`, test |
| **Ngày fix** | 2026-07-05 |

### J11 — f-string with error object may crash in `_doc_raw_values_sheet`
| | |
|---|---|
| **File** | `services/report_submission_service.py` → `_doc_raw_values_sheet()` L213 |
| **Dấu hiệu** | `f"{type(last_err).__name__}: {last_err}{...}"` — nếu `str(last_err)` chứa ngoặc nhọn `{` `}`, f-string sẽ raise `KeyError` |
| **Nguyên nhân** | Python f-string parse `{last_err}` trong template → nếu error message chứa `{field}`, Python cố tìm biến `field` |
| **Fix** | Dùng `"...{}...".format(...)` thay vì f-string để tránh parse ngoặc nhọn trong message |
| **Ngày fix** | 2026-07-05 |

### J12 — `_migrate_allowlist_loai` silently normalizes non-matching allowlist items
| | |
|---|---|
| **File** | `services/report_submission_service.py` → `_migrate_allowlist_loai()` L430-434 |
| **Dấu hiệu** | Item trong Telegram allowlist không khớp tên đổi bị thay bằng bản chuẩn hóa (`_chuan_hoa_ten_loai`) thay vì giữ nguyên giá trị gốc |
| **Nguyên nhân** | Vòng lặp `else: ds_moi.append(loai)` thay vì `ds_moi.append(item)` — ghi đè item gốc bằng bản đã trim whitespace, mất định dạng ban đầu |
| **Fix** | `ds_moi.append(item)` — giữ nguyên item gốc, không normalize khi không cần đổi tên |
| **Ngày fix** | 2026-07-05 |

---
## Template: Ghi nhận bug mới

### C13 — BQ metrics: `n_xa`/`n_hoi` sai do dùng `groupby ngroups` thay vì `nunique()`
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` L329-348, `workspaces/ws_operation.py` L756-775 |
| **Dấu hiệu** | Card Dư nợ BQ Hội ghi chú "10 hội đoàn thể" (thực tế chỉ có 4); card BQ Xã ghi "11 xã" (thực tế ~95) |
| **Nguyên nhân** | `groupby([COT_TEN_PGD, COT_DVUT]).ngroups` đếm số **cặp** (PGD, ĐVUT) thay vì số giá trị unique của chính cột ĐVUT. Với 4 Hội × 22 PGD → 10-88 cặp tùy dữ liệu thực tế |
| **Fix** | `df_bq[COT_DVUT].nunique()` và `df_bq[COT_TEN_XA].nunique()` thay vì groupby ngroups. Riêng `n_to` giữ nguyên groupby ngroups vì tên Tổ trùng giữa các PGD |
| **Ngày fix** | 2026-06-06 |

### C14 — BQ Hội đếm 5 thay vì 4 do dòng rỗng/"CỘNG"
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` L345, `workspaces/ws_operation.py` L773 |
| **Dấu hiệu** | Card Dư nợ BQ Hội ghi chú "5 hội đoàn thể" (có 4 hội chính + 1 dòng rỗng hoặc "CỘNG") |
| **Nguyên nhân** | Cột `COT_DVUT` có dòng NaN/rỗng hoặc dòng tổng "CỘNG" → `nunique()` đếm thành 1 giá trị unique thừa |
| **Fix** | `.dropna().loc[lambda s: (s != "") & (s != "CỘNG")].nunique()` — loại NaN, rỗng, và dòng tổng trước khi đếm |
| **Ngày fix** | 2026-06-06 |

### C15 — BQ PGD chỉ hiện 2 PGD thay vì 22 do groupby.sum() trên cột object
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` L329-334, `workspaces/ws_operation.py` L756-760 |
| **Dấu hiệu** | Card Dư nợ BQ PGD ghi "2 PGD có dư nợ" (thực tế 22 PGD đều có dữ liệu); giá trị BQ/PGD ~600 tỷ (vô lý) |
| **Nguyên nhân** | Cột `COT_TONG_DU_NO` trong parquet có mixed dtype (string/float). `groupby().sum()` trên cột object nối chuỗi thay vì cộng số → `> 0` filter cho kết quả sai (chỉ 2 PGD có dư nợ `> 0` sau khi so sánh chuỗi) |
| **Fix** | Tạo `df_bq.copy()`, chạy `pd.to_numeric(df_bq[COT_TONG_DU_NO], errors="coerce").fillna(0)` trước khi groupby — khớp với cách KPI đang tính `tdn` |
| **Ngày fix** | 2026-06-06 |

### C16 — BQ Xã đếm 96 thay vì 95 do nunique() lẫn NaN/rỗng/"CỘNG"
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` L344, `workspaces/ws_operation.py` L770, `workspaces/ws_operation.py` L363 |
| **Dấu hiệu** | Card Dư nợ BQ Xã ghi "96 xã" (thực tế chỉ có 95 xã/phường) |
| **Nguyên nhân** | Cột `COT_TEN_XA` có dòng NaN/rỗng hoặc dòng tổng "CỘNG" → `nunique()` đếm thành 1 giá trị unique thừa. C14 chỉ fix cho `n_hoi` nhưng bỏ sót `n_xa` |
| **Fix** | `.dropna().loc[lambda s: (s != "") & (s != "CỘNG")].nunique()` — loại NaN, rỗng, và "CỘNG" trước khi đếm, thống nhất với cách tính `n_hoi` |
| **Ngày fix** | 2026-06-07 |

### C17 — `so_mon` bảng cơ cấu chương trình cao hơn thực tế (count thay nunique, sai cột)
| | |
|---|---|
| **File** | `services/tongquan_service.py` → `tinh_co_cau_ct()` L116 |
| **Dấu hiệu** | Cột "Số món vay" trong bảng cơ cấu chương trình tín dụng lớn hơn thực tế |
| **Nguyên nhân** | Dùng `df.groupby(ct)[cot_ma_kh].count()` — 2 lỗi: (1) `count()` không loại trùng, (2) đếm `Mã KH` thay vì `Số khế ước` |
| **Fix** | Thêm param `cot_so_ku`, dùng `df_loc.groupby(ct)[cot_so_ku].nunique()`; `so_kh` cũng đổi sang `df_loc` |
| **Ngày fix** | 2026-06-07 |

### C18 — Kiểm tra cân đối nợ luôn hiện ✅ dù không thực sự kiểm tra
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` → `render()` L436–442 |
| **Dấu hiệu** | Caption "Kiểm tra cân đối … = X tỷ ✅" luôn xanh dù số có thể lệch |
| **Nguyên nhân** | `✅` hardcode trong f-string, không có logic kiểm tra `dth + dqh + dnk == tdn` |
| **Fix** | `_can_doi_ok = abs((dth+dqh+dnk)-tdn) < 1e4`; icon động theo kết quả |
| **Ngày fix** | 2026-06-07 |

### C19 — KPI đến hạn dùng `fmt()` hiển thị đồng nguyên, label ghi triệu đồng
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` → `_bang_den_han()` L1390, L1484; `_xuat_pdf_den_han()` L209 |
| **Dấu hiệu** | Card "Tổng dư nợ" hiện số rất lớn (1.234.567.890) nhưng label "Đơn vị: triệu đồng" |
| **Nguyên nhân** | `fmt(tong_no)` format VND nguyên; nên dùng `fmt_ty(tong_no)` chia /1e6 |
| **Fix** | Đổi toàn bộ `fmt(tong_no)` → `fmt_ty(tong_no)` ở 3 chỗ |
| **Ngày fix** | 2026-06-07 |

### C18 — Điện báo/KH&TH card Tổng dư nợ bị trùng 2 lần
| | |
|---|---|
| **File** | `tabs/tab_candoi.py` L455-465, L473-482 |
| **Dấu hiệu** | Mục Điện báo & KH vs TH hiển thị "Tổng dư nợ" ở kpi_row #1 và "Tổng DN KHA+KHB" ở kpi_row #2 — cùng giá trị, gây hiểu lầm |
| **Nguyên nhân** | `tong_dn_ht` = tổng dư nợ toàn CN = KHA + KHB. Card "Tổng DN KHA+KHB" tính `kha_ht + khb_ht` cho ra cùng giá trị với card "Tổng dư nợ" ở hàng trên |
| **Fix** | Xóa card "Tổng DN KHA+KHB" khỏi kpi_row #2 (cả 2 nhánh có/không kỳ trước), đổi `num_columns=3` |
| **Ngày fix** | 2026-06-07 |

---

### C20 — Tra cứu không ra hồ sơ dù dữ liệu có (lọc dính state / mismatch dtype)
| | |
|---|---|
| **File** | `components/filter_panel.py` → `render_filter_panel()` |
| **Dấu hiệu** | Một số hộ tra cứu không ra, trong khi chắc chắn có trong HSTD; thường xảy ra khi đã từng chọn PGD/CT/Nguồn vốn hoặc khi nhập từ khóa không dấu |
| **Nguyên nhân** | (1) Bộ lọc nâng cao nằm trong expander nên dễ "dính" filter cũ trong `st.session_state`. (2) Lọc `.isin()`/so sánh trực tiếp trên cột mixed dtype (string/int/float) làm loại nhầm dữ liệu. (3) `Nguồn vốn` có thể là `01/02/TW/ĐP` nhưng UI chọn `1/2` → không match. (4) Keyword search chỉ `.lower()` nên gõ không dấu không match tên có dấu |
| **Fix** | Thêm nút `🔄 Reset` luôn hiển thị; ép numeric trước khi lọc dư nợ/quá hạn/khoanh; chuẩn hóa `Nguồn vốn` về `1/2` trước khi hiển thị/lọc; keyword search hỗ trợ có dấu/không dấu bằng `vn()` |
| **Ngày fix** | 2026-06-23 |

### C21 — Ủy thác: `Số Tổ TK&VV` theo Hội đoàn thể bị thấp do trùng tên Tổ giữa các PGD
| | |
|---|---|
| **File** | `services/uy_thac_service.py` → `tinh_theo_dvut()` |
| **Dấu hiệu** | Tab `🤝 Ủy thác` → `📊 Theo Hội đoàn thể`: cột/metric `Số Tổ` nhỏ hơn thực tế, nhất là khi tổng hợp toàn Chi nhánh |
| **Nguyên nhân** | Đếm bằng `nunique(COT_TEN_TO)` theo Hội → undercount vì tên Tổ có thể trùng giữa nhiều PGD (hoặc nhiều xã) |
| **Fix** | Đếm theo tổ hợp định danh: ưu tiên `(Hội, PGD, Xã, Tổ)`; nếu thiếu Xã/PGD thì fallback `(Hội, PGD, Tổ)` hoặc `(Hội, Xã, Tổ)`; đồng thời `pd.to_numeric(..., errors='coerce')` trước các phép `sum()` để tránh lỗi mixed dtype |
| **Ngày fix** | 2026-06-29 |

### C22 — Ủy thác: metric `Tổng Tổ TK&VV` bị double-count khi 1 Tổ xuất hiện với nhiều Hội
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py` → `_render_theo_dvut()` |
| **Dấu hiệu** | Metric `Tổng Tổ TK&VV` (tính bằng `sum(Số Tổ theo Hội)`) lớn hơn tổng số Tổ unique toàn Chi nhánh |
| **Nguyên nhân** | Một số bản ghi HSTD có cùng `(PGD, Xã, Tổ)` nhưng gán khác `Hội đoàn thể` → nếu cộng số tổ theo từng Hội sẽ đếm trùng |
| **Fix** | Metric tổng hiển thị theo total unique `(PGD, Xã, Tổ)` khi đủ cột; fallback `(PGD, Tổ)` hoặc `(Xã, Tổ)` nếu thiếu cột; thêm caption cảnh báo khi phát hiện Tổ đa Hội |
| **Ngày fix** | 2026-06-29 |

### C23 — Chênh lệch số Tổ giữa `🏘️ Xếp loại Tổ TK&VV` và `🤝 Ủy thác` do khác nguồn dữ liệu/định nghĩa
| | |
|---|---|
| **File** | `tabs/tab_cdtotkvv.py` → `_sub_tong_hop()`, `tabs/tab_uy_thac.py` → `_render_theo_dvut()` |
| **Dấu hiệu** | `▶ 📊 Thông tin chung` trong `🏘️ Xếp loại Tổ TK&VV toàn Chi nhánh` có tổng Tổ khác với tab `🤝 Ủy thác` |
| **Nguyên nhân** | CDTOTKVV là danh sách Tổ được chấm điểm theo kỳ (có thể thiếu PGD/Tổ hoặc có dòng trùng), còn `Ủy thác` đếm Tổ từ HSTD (tổ có món vay phát sinh). Hai nguồn dữ liệu không nhất thiết bằng nhau |
| **Fix** | Trong `Xếp loại Tổ`, hiển thị tổng Tổ theo CDTOTKVV unique `(PGD, Mã Tổ)`, dùng mẫu số unique cho các tỷ lệ xếp loại, và kèm tham chiếu tổng Tổ từ HSTD theo `(PGD, Xã, Tổ)`; thêm caption giải thích chênh lệch |
| **Ngày fix** | 2026-06-29 |

### C24 — Ủy thác: `Tổng KH` theo Hội đoàn thể đếm nhầm số khế ước
| | |
|---|---|
| **File** | `services/uy_thac_service.py` → `tinh_theo_dvut()`, `tabs/tab_uy_thac.py` → `_render_theo_dvut()` |
| **Dấu hiệu** | Tab `🤝 Ủy thác` → `📊 Thống kê theo Hội đoàn thể`: metric `Tổng KH` bằng tổng món vay (vd `291.522`) thay vì khớp `📊 Thông tin chung` `Tổng khách hàng` (vd `213.343`, BQ `1,4 món/KH`) |
| **Nguyên nhân** | Service đặt tên cột `so_kh` nhưng lại tính bằng `nunique(COT_SO_KU)`; `Số khế ước` là món vay, không phải khách hàng |
| **Fix** | Tính `so_kh` bằng `nunique(COT_MA_KH)` khi có cột `Mã KH`, chỉ fallback sang `Số khế ước` nếu dữ liệu thiếu mã khách hàng; metric tổng trong tab lấy unique trực tiếp trên subset có `Tên ĐVUT` để vừa đúng phạm vi Hội vừa không double-count |
| **Test** | `tests/test_uy_thac_service.py::test_tinh_theo_dvut_counts_distinct_ma_kh_not_so_ku` |
| **Ngày fix** | 2026-06-29 |

### C25 — Ủy thác: `Tổng dư nợ` theo Hội đoàn thể bị thấp hơn `Thông tin chung`
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py` → `_render_theo_dvut()` |
| **Dấu hiệu** | Tab `🤝 Ủy thác` → `📊 Thống kê theo Hội đoàn thể`: metric `Tổng dư nợ (triệu đồng)` ra `13.291.942` thay vì khớp tổng dư nợ ở `📊 Thông tin chung` |
| **Nguyên nhân** | `Thông tin chung` và `Thống kê theo Hội đoàn thể` là hai phạm vi khác nhau: tab Hội chỉ nên tính trên các dòng có `Tên ĐVUT`, không phải toàn bộ HSTD |
| **Fix** | Giữ metric `Tổng dư nợ` theo đúng subset có `Tên ĐVUT`, và chuẩn hóa để các metric tổng khác trong block (`Tổ`, `KH`) cũng cùng bám subset này thay vì lẫn với phạm vi toàn HSTD |

### C26 — `Thông tin chung`: card `Tổng dư nợ` ghi ngày hệ thống thay vì ngày HSTD và thiếu tách `Ủy thác / Trực tiếp`
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` → `render()` |
| **Dấu hiệu** | Card `Tổng dư nợ` hiển thị `Số liệu đến ...` theo ngày hiện tại của máy chủ, không phản ánh đúng ngày số liệu HSTD; người dùng cũng không biết trong tổng dư nợ có bao nhiêu là qua ủy thác, bao nhiêu là trực tiếp |
| **Nguyên nhân** | Caption dùng `datetime.now()` thay vì đọc `COT_NGAY_SL`/`merge_meta_hstd`; card chỉ hiển thị tổng, chưa tách cấu phần |
| **Fix** | Lấy ngày ưu tiên từ `COT_NGAY_SL`, fallback `merge_meta_hstd`; bổ sung dòng phụ `Ủy thác X tỷ · Trực tiếp Y tỷ`, trong đó `trực tiếp` là các món không có `Tổ TK&VV` và không có `ĐVUT` |
| **Ngày fix** | 2026-06-29 |

### C27 — `Thông tin chung`: `Dư nợ BQ xã` chỉ hiện 82 do đếm theo HSTD active thay vì danh mục địa bàn
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` → `_cache_bq_counts()` |
| **Dấu hiệu** | Trong `▶ 📊 Thông tin chung`, card `Dư nợ BQ xã` chỉ hiện `82 xã` dù danh mục địa bàn toàn CN có `95 xã/phường` |
| **Nguyên nhân** | App nạp HSTD CN với `active_only=True`, nên helper đếm xã trực tiếp từ HSTD chỉ phản ánh xã đang có hồ sơ dư nợ; đồng thời tên xã trong HSTD thường bỏ prefix `Xã/Phường`, không phải mẫu số địa bàn quản lý |
| **Fix** | Đếm xã/phường theo `PGD_XA_MAP`: toàn CN dùng `95`, theo PGD dùng số xã cấu hình của PGD; chỉ fallback sang HSTD nếu PGD không có trong danh mục cấu hình |
| **Ngày fix** | 2026-06-30 |
| **Ngày fix** | 2026-06-29 |

### C28 — `Tổng quan danh mục tín dụng`: `Dư nợ BQ tổ TKVV` đếm sai do `groupby(PGD, Tên tổ)`
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` → `_cache_bq_counts()`, `services/tongquan_service.py` |
| **Dấu hiệu** | Card hiện `4.536 tổ` / BQ `3.012,1 tr` trong khi CDTOTKVV ~`4.552` tổ — chênh ~16 tổ, dễ hiểu nhầm là hai nguồn lệch lớn |
| **Nguyên nhân** | Đếm `groupby([PGD, Tên tổ])` gộp nhầm các tổ **trùng tên** trong cùng PGD (khác xã/mã tổ); HSTD active có ~99,8% dòng có `Mã tổ`, đối chiếu CDTO khớp ~4.317/4.5k tổ |
| **Fix** | `dem_so_to_hstd()` ưu tiên `(PGD, Mã tổ)`, fallback `(PGD, Xã, Tên tổ)`; mẫu số BQ lấy từ cùng `df` HSTD đang hiển thị, không thay bằng CDTOTKVV |
| **Test** | `tests/test_tongquan_service.py::test_dem_so_to_hstd_uu_tien_ma_to` |
| **Ngày fix** | 2026-07-05 |

### C29 — `_cache_bq_counts` thiếu `COT_MA_TO` → fix C28 chưa có hiệu lực trên UI
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` → `_cache_bq_counts()` |
| **Dấu hiệu** | Sau fix C28, card vẫn có thể hiện ~4.555 tổ (fallback `PGD+Xã+Tên tổ`) thay vì ~4.559 theo `Mã tổ` |
| **Nguyên nhân** | `cols_need` khi copy `df_bq` không gồm `COT_MA_TO` → `dem_so_to_hstd()` không thấy cột Mã tổ |
| **Fix** | Thêm `COT_MA_TO` vào `cols_need` |
| **Ngày fix** | 2026-07-05 |

### C30 — `Thông tin chung`: Tổng món vay/Tổng khách hàng đếm cả hồ sơ dư nợ 0
| | |
|---|---|
| **File** | `services/tongquan_service.py` → `tinh_kpi_tongquan()`; `tabs/tab_tongquan.py` → `render()` |
| **Dấu hiệu** | `📊 Thông tin chung` có thể hiện Tổng món vay/Tổng khách hàng cao hơn thực tế nếu tab nhận HSTD chưa lọc active; cache hiện tại chênh `337.186` vs `293.067` món khi đếm toàn bộ HSTD |
| **Nguyên nhân** | Phân hệ CN nạp `active_only=True`, nhưng luồng PGD/standalone có thể truyền cả các dòng `Tổng dư nợ = 0`. KPI dùng `nunique()` trên toàn bộ `df`, nên đếm cả hồ sơ đã tất toán |
| **Fix** | Thêm `loc_ho_so_con_du_no()` lọc theo `Tổng dư nợ > 0 OR Dư nợ quá hạn > 0 OR Dư nợ khoanh > 0`; dùng trong KPI service và đầu `tab_tongquan.render()` |
| **Test** | `tests/test_tongquan_service.py::test_tinh_kpi_tongquan_bo_qua_ho_so_du_no_0_khi_dem` |
| **Ngày fix** | 2026-07-10 |

---

### H11 — Đổi tên giai đoạn KHTD không lên UI khi tên Form chèn thêm cụm từ
| | |
|---|---|
| **File** | `services/report_submission_service.py` → `_ten_loai_khong_nam()`, `_tim_ten_form_goi_y()`, `phat_hien_ten_lech_ten()` |
| **Dấu hiệu** | Mục `RÀ SOÁT XÂY DỰNG KHTD 2023-2026` vẫn hiện tên cũ ở `⚙️ Cài đặt thời hạn` / `📊 Tổng quan` dù Google Form đã đổi sang tên mới cùng nghĩa nhưng có chèn thêm cụm như `GIAI ĐOẠN 2027-2030` |
| **Nguyên nhân** | Logic cũ chỉ match khi phần tên sau khi bỏ năm phải bằng nhau tuyệt đối; nếu Form thêm vài từ trung gian thì không còn match exact nên `tracked_to_display` vẫn giữ key cũ |
| **Fix** | Bỏ year-range ở mọi vị trí trong chuỗi, chuẩn hóa dấu câu + khoảng trắng, rồi thêm bước match containment có kiểm soát: chỉ nhận gợi ý khi có đúng 1 candidate rõ ràng trên Form |
| **Test** | `tests/test_report_submission_service.py::TestPhatHienTenLechTen::test_goi_y_khi_ten_form_chen_them_cum_tu`, `tests/test_report_submission_service.py::TestDanhMucTheoDoi::test_hien_ten_form_khi_ten_moi_chen_them_cum_tu` |
| **Ngày fix** | 2026-07-05 |

---

### H12 — “Chưa hoàn thành” ở tab tiến độ bị hiểu sai theo raw rows Google Form
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py`, `services/report_submission_service.py` |
| **Dấu hiệu** | Tab `📋 Danh sách nộp` và phần xuất báo cáo có thể coi “chưa hoàn thành” là các dòng raw từ Google Form, nên PGD chưa hề nộp một dòng nào cho loại báo cáo đang theo dõi không xuất hiện đầy đủ trong danh sách cần đôn đốc |
| **Nguyên nhân** | Logic cũ chỉ lọc trên DataFrame các lượt nộp thực tế từ GSheet; nguồn này không có bản ghi cho nghĩa vụ chưa phát sinh submission, nên không thể đại diện đúng cho ma trận `PGD × loại deadline` |
| **Fix** | Tạo helper `lap_bang_nghia_vu_bao_cao()` và `tong_hop_bao_cao_dieu_hanh()` để sinh bảng nghĩa vụ đầy đủ theo `PGD × loại báo cáo`; UI tổng quan và kiểm soát deadline đọc từ bảng này, còn tab `Danh sách nộp` chỉ còn là lớp raw submissions |
| **Test** | `tests/test_report_submission_service.py::TestBaoCaoDieuHanh::test_lap_bang_nghia_vu_tinh_ca_don_vi_chua_co_dong_nop`, `tests/test_report_submission_service.py::TestBaoCaoDieuHanh::test_tong_hop_bao_cao_dieu_hanh_tach_thieu_file_khoi_da_hoan_thanh` |
| **Ngày fix** | 2026-07-15 |

---

## Template: Ghi nhận bug mới

### J13 — `_upload_info()` đổi kiểu trả về làm test unpack bị lỗi
| | |
|---|---|
| **File** | `tabs/tab_pgd_cards.py` → `_upload_info()` ~dòng 71 |
| **Dấu hiệu** | 4 test trong `TestUploadInfo` lỗi `TypeError: cannot unpack non-iterable bool object` |
| **Nguyên nhân** | Fix B25 đổi helper từ tuple `(ok, timestamp)` sang `bool`, phá vỡ hợp đồng API đang được test dù UI chỉ cần trạng thái upload |
| **Fix** | Khôi phục tuple tương thích; `upload_info_map` chỉ lấy phần tử trạng thái, nên UI vẫn dùng ngày số liệu HSTD và không quay lại hiển thị mtime |
| **Test** | `tests/test_pgd_cards.py::TestUploadInfo` |
| **Ngày fix** | 2026-07-11 |

### J16 — Ban Đại Diện còn sót call `_ngay_so_lieu()` sau khi đã chuyển sang helper mới
| | |
|---|---|
| **File** | `tabs/tab_ban_dai_dien.py` |
| **Dấu hiệu** | Mở `🏛️ Ban Đại Diện` → `📊 Tổng hợp số liệu tín dụng chính sách` bị lỗi `NameError: name '_ngay_so_lieu' is not defined` |
| **Nguyên nhân** | File đã import `lay_ngay_so_lieu()` từ `utils`, nhưng trong `_render_tong_hop()` vẫn còn 1 call cũ `_ngay_so_lieu(df)` từ trước đợt refactor helper ngày số liệu |
| **Fix** | Đổi call còn sót sang `lay_ngay_so_lieu(df)` và chạy lại compile + convention check |
| **Ngày fix** | 2026-07-11 |

### J17 — Tab Ủy thác trộn báo cáo số liệu với mẫu biểu kiểm tra ngang hàng
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py`, `services/uy_thac_service.py` |
| **Dấu hiệu** | Người dùng vào tab `🤝 Ủy thác` phải đi qua nhiều nhánh `01/KH`, `06`, `15`, `16`, biên bản... trước khi tới được phần báo cáo số liệu; luồng dùng tab bị lệch sang “soạn biểu mẫu” thay vì “xem và xuất báo cáo” |
| **Nguyên nhân** | Điều hướng cũ đặt báo cáo số liệu và các mẫu kiểm tra ở cùng cấp độ ưu tiên, trong khi service mới mạnh ở thống kê cơ bản theo Hội và chưa có lớp tổng hợp báo cáo đa chiều riêng |
| **Fix** | Tách lại thành 4 khu `Tổng quan Ủy thác / Báo cáo số liệu / Theo dõi kiến nghị / Kho mẫu biểu`; bổ sung helper tổng quan, tổng hợp theo chiều và danh sách chi tiết để báo cáo số liệu trở thành luồng mặc định |
| **Test** | `tests/test_uy_thac_service.py` |
| **Ngày fix** | 2026-07-11 |

### J18 — Tab Ủy thác mới có khung 3 khu nhưng chưa đủ chiều sâu báo cáo và theo dõi kiến nghị
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py`, `services/uy_thac_service.py` |
| **Dấu hiệu** | Sau khi bỏ `Kho mẫu biểu`, tab `Ủy thác` đã gọn hơn nhưng `Tổng quan` còn mỏng, `Báo cáo số liệu` chưa có đủ lát cắt theo PGD/xã/Hội/tổ, còn `Theo dõi kiến nghị` chủ yếu là danh sách thô chưa có KPI hạn xử lý |
| **Nguyên nhân** | Đợt redesign đầu mới dừng ở việc đổi điều hướng và thêm lớp tổng hợp cơ bản; chưa hoàn thiện phần quản trị điểm nóng, drill-down và cảnh báo quá hạn cho kiến nghị |
| **Fix** | Bổ sung KPI sâu + bảng top điểm nóng ở `Tổng quan`; mở rộng `Báo cáo số liệu` theo PGD/xã/Hội/tổ, thêm drill-down chi tiết và bộ export nhiều sheet; thêm helper `tong_hop_kien_nghi()` / `tao_bang_theo_doi_kien_nghi()` để `Theo dõi kiến nghị` có KPI, cảnh báo hạn và Excel theo dõi |
| **Test** | `tests/test_uy_thac_service.py::test_tong_hop_kien_nghi_dem_dung_trang_thai_va_han`, `tests/test_uy_thac_service.py::test_tao_bang_theo_doi_kien_nghi_them_canh_bao_han` |
| **Ngày fix** | 2026-07-11 |

### J19 — Tab Ủy thác lỗi export, lọc lãi tồn và sai phạm vi/đơn vị hiển thị
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py`, `services/uy_thac_service.py` |
| **Dấu hiệu** | Nút tạo Excel phát sinh `TypeError`; lọc khoản có lãi tồn không lọc; số gắn nhãn triệu đồng vẫn hiện VND; KPI có thể gồm khoản trực tiếp và đếm trùng Tổ đa hội |
| **Nguyên nhân** | Gọi `xuat_excel()` với tham số `ten_file` không có trong signature; chi tiết đã đổi cột lãi thành `Nợ lãi` nhưng filter còn kiểm tra constant cũ; dùng `fmt()` thay `fmt_ty()`; lớp chuẩn hóa chưa giới hạn dòng có ĐVUT và tổng Tổ cộng theo từng Hội |
| **Fix** | Gọi đúng signature; lọc theo `Nợ lãi`; dùng `fmt_ty()` cho cột/card triệu đồng; lọc hồ sơ có ĐVUT và đếm unique `(PGD, Xã, Tổ)` cho KPI tổng |
| **Test** | `tests/test_uy_thac_service.py::test_tong_quan_uy_thac_excludes_direct_loans_and_deduplicates_multi_hoi_to` |
| **Ngày fix** | 2026-07-11 |

### J20 — Tab Ủy thác có nhiều lát cắt nhưng vẫn thiếu số liệu điều hành
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py`, `services/uy_thac_service.py` |
| **Dấu hiệu** | `Báo cáo số liệu` đã có nhiều kiểu group nhưng các bảng chủ yếu lặp lại cùng bộ chỉ tiêu nền; thiếu góc nhìn điều hành như tỷ trọng dư nợ, bình quân/Tổ, bình quân/KH, số Tổ có NQH/lãi tồn và danh sách điểm nóng xã/tổ |
| **Nguyên nhân** | Lớp tổng hợp chung `tong_hop_uy_thac_theo()` mới dừng ở các chỉ tiêu cơ bản (`so_to/so_kh/tong_dn/nqh/lai_ton`) nên tab chỉ đổi chiều group chứ chưa có lớp báo cáo điều hành dẫn xuất |
| **Fix** | Thêm helper `tao_bao_cao_dieu_hanh_uy_thac()` để tính chỉ tiêu điều hành và số Tổ có vấn đề theo từng nhóm; gắn vào `tab_uy_thac.py` qua các báo cáo mới `Điều hành theo PGD`, `Điều hành theo Hội`, `Điểm nóng xã/Tổ`, kèm KPI nhanh và sheet Excel điều hành |
| **Test** | `tests/test_uy_thac_service.py::test_tao_bao_cao_dieu_hanh_uy_thac_adds_derived_metrics`, `tests/test_uy_thac_service.py::test_tao_bao_cao_dieu_hanh_uy_thac_counts_problem_to_uniquely` |
| **Ngày fix** | 2026-07-12 |

### J21 — Ủy thác: `Biến động nhiều kỳ` chỉ đọc tổng CN/PGD nên thiếu chiều Hội/Xã
| | |
|---|---|
| **File** | `snapshot_service.py`, `tabs/tab_uy_thac.py` |
| **Dấu hiệu** | Màn `Biến động nhiều kỳ` chỉ xem được toàn CN hoặc 1 PGD; không thể theo dõi xu hướng riêng của từng Hội đoàn thể hoặc từng xã/phường qua các kỳ snapshot |
| **Nguyên nhân** | Snapshot Ủy thác đã lưu đủ các cấp `CN/PGD/XA/HOI/TO`, nhưng reader `doc_uy_thac_snapshot_multi()` chỉ suy luận `CN/PGD`; nhánh UI cũng chưa có chọn cấp biến động và đối tượng snapshot |
| **Fix** | Mở rộng `doc_uy_thac_snapshot_multi()` để đọc theo `HOI/XA` với tham số lọc `dvut/ten_xa/ten_pgd`; cập nhật `tab_uy_thac.py` để chọn `Tổng phạm vi / Hội đoàn thể / Xã-phường` và xuất được sheet biến động đang xem |
| **Test** | `tests/test_snapshot_service.py::TestUyThacSnapshot::test_doc_theo_hoi`, `tests/test_snapshot_service.py::TestUyThacSnapshot::test_doc_theo_xa` |
| **Ngày fix** | 2026-07-12 |

### J22 — Ủy thác: KPI nhanh và bundle Excel lệch dữ liệu sau đợt mở rộng báo cáo điều hành
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py`, `services/uy_thac_service.py` |
| **Dấu hiệu** | KPI `Tổ có NQH`/`Tỷ lệ Tổ có NQH` có thể vượt thực tế khi 1 Tổ xuất hiện đa Hội; sheet `DiemNongXa`/`DiemNongTo` trong bộ Excel chứa cả dòng không phải điểm nóng; bundle Excel thiếu `Cảnh báo trọng điểm` hoặc `Biến động nhiều kỳ` nếu user không đứng đúng radio tương ứng |
| **Nguyên nhân** | KPI nhanh cộng `so_to_nqh` từ bảng đã group theo `PGD/Xã/Hội/Tổ` nhưng lại chia cho `so_to` unique toàn phạm vi; bundle Excel dùng bản report điểm nóng chưa lọc và phụ thuộc `current_export/current_name` của UI hiện tại |
| **Fix** | Thêm `tong_quan_dieu_hanh_uy_thac()` để tính KPI điều hành toàn phạm vi theo identity unique; tách helper lọc `DiemNongXa/DiemNongTo`; bundle Excel luôn build sẵn `XepHangChatLuong`, `CanhBaoTrongDiem`, `BienDongNhieuKy` từ dữ liệu scope hiện tại |
| **Test** | `tests/test_uy_thac_service.py::test_tong_quan_dieu_hanh_uy_thac_counts_problem_to_uniquely_for_multi_hoi_to` |
| **Ngày fix** | 2026-07-12 |

### J23 — Ủy thác: Snapshot `Hội` chỉ lưu toàn Chi nhánh nên không xem được biến động theo từng PGD
| | |
|---|---|
| **File** | `snapshot_service.py`, `tabs/tab_uy_thac.py` |
| **Dấu hiệu** | Màn `Biến động nhiều kỳ` theo `Hội đoàn thể` chỉ xem được xu hướng toàn Chi nhánh; không thể trả lời các câu hỏi kiểu “Hội Phụ nữ ở PGD X biến động thế nào qua các kỳ” |
| **Nguyên nhân** | `luu_uy_thac_snapshot()` chỉ lưu snapshot cấp `HOI` theo `dvut`, không lưu thêm grain `PGD + Hội`; vì vậy reader và UI không có dữ liệu để drill xuống từng PGD |
| **Fix** | Lưu thêm snapshot `HOI` theo cặp `PGD + Hội`; khi đọc `HOI` không có `ten_pgd` thì mặc định lấy bản `__ALL__` để giữ tương thích ngược, còn UI cho phép chọn `Toàn Chi nhánh / PGD cụ thể` trước khi chọn Hội |
| **Test** | `tests/test_snapshot_service.py::TestUyThacSnapshot::test_doc_theo_hoi`, `tests/test_snapshot_service.py::TestUyThacSnapshot::test_doc_theo_hoi_trong_tung_pgd` |
| **Ngày fix** | 2026-07-12 |

### J24 — Ủy thác: bundle `BienDongNhieuKy` xuất sai scope khi đang xem `Hội trong PGD`
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py`, `tests/test_snapshot_service.py` |
| **Dấu hiệu** | Màn `Biến động nhiều kỳ` đang xem đúng `PGD X - Hội A`, nhưng sheet Excel `BienDongNhieuKy` trong bộ báo cáo vẫn có thể lấy bản tổng phạm vi `CN/PGD`; với snapshot lịch sử cũ, chuỗi `Hội trong PGD` còn có thể thiếu kỳ mà user không biết lý do |
| **Nguyên nhân** | Bundle Excel dùng `report_bd_bundle` build sẵn theo snapshot tổng phạm vi, không bám `current_export` của nhánh biến động đang mở; UI chưa nhắc khi dữ liệu lịch sử chưa có grain `PGD + Hội` |
| **Fix** | Sheet `BienDongNhieuKy` trong bundle ưu tiên `current_export` khi user đang đứng ở một báo cáo biến động; thêm cảnh báo nhẹ khi chuỗi `Hội trong PGD` thiếu kỳ do snapshot lịch sử chưa backfill grain mới |
| **Test** | `tests/test_snapshot_service.py::TestUyThacSnapshot::test_doc_theo_hoi_khong_lan_cn_va_pgd_khi_cung_hoi_o_nhieu_pgd`, `tests/test_snapshot_service.py::TestUyThacSnapshot::test_doc_theo_hoi_suy_luan_dung_backward_compatible_khi_truyen_dvut_va_ten_pgd` |
| **Ngày fix** | 2026-07-12 |

### J25 — Ủy thác: API snapshot Hội dễ chọn nhầm grain tại call-site
| | |
|---|---|
| **File** | `snapshot_service.py`, `tabs/tab_uy_thac.py` |
| **Dấu hiệu** | Call-site muốn đọc `Hội trong PGD` nhưng quên truyền `ten_pgd` sẽ nhận dữ liệu Hội toàn Chi nhánh mà không có lỗi |
| **Nguyên nhân** | Một API tổng quát dùng tổ hợp tham số tùy chọn để suy luận cả hai grain `HOI`; khác biệt chỉ nằm ở sentinel `ten_pgd='__ALL__'` nên ý định của call-site không được thể hiện trong tên hàm |
| **Fix** | Thêm API chuyên biệt `doc_uy_thac_snapshot_hoi_cn()` và `doc_uy_thac_snapshot_hoi_pgd()`; API PGD từ chối truy vấn khi thiếu `ten_pgd`; UI dùng API tương ứng theo phạm vi đã chọn, đồng thời giữ API cũ để tương thích ngược |
| **Test** | `tests/test_snapshot_service.py::TestUyThacSnapshot::test_api_hoi_cn_chi_doc_grain_toan_chi_nhanh`, `tests/test_snapshot_service.py::TestUyThacSnapshot::test_api_hoi_pgd_chi_doc_grain_pgd`, `tests/test_snapshot_service.py::TestUyThacSnapshot::test_api_hoi_pgd_khong_truy_van_khi_thieu_pham_vi` |
| **Ngày fix** | 2026-07-12 |

### J26 — Backfill baseline HSTD không sinh snapshot Ủy thác nên kỳ cũ thiếu grain `PGD + Hội`
| | |
|---|---|
| **File** | `services/upload_service.py` → `merge_baseline_toan_cn()`; `snapshot_service.py` → `luu_uy_thac_snapshot()` |
| **Dấu hiệu** | Màn `Ủy thác → Biến động nhiều kỳ → Theo Hội đoàn thể → chọn PGD` chỉ đầy đủ từ các kỳ snapshot mới; các kỳ cũ đã rebuild HSTD vẫn thiếu dữ liệu `Hội trong PGD` |
| **Nguyên nhân** | Pipeline baseline `loai="hstd"` chỉ gọi `luu_snapshot()` nên chỉ sinh `hstd_snapshot`; bảng `uy_thac_snapshot` không được backfill. Đồng thời writer `luu_uy_thac_snapshot()` không có `ky` override nên khó chạy backfill an toàn theo kỳ lịch sử |
| **Fix** | Thêm tham số `ky` cho `luu_uy_thac_snapshot()` để backfill đúng kỳ; sau `merge_baseline_toan_cn(loai="hstd")` gọi thêm `luu_uy_thac_snapshot(df_all, username, ky=f"{nam}-12")` để sinh đủ grain `PGD + Hội` cho snapshot cũ |
| **Test** | `tests/test_snapshot_service.py::TestUyThacSnapshot::test_luu_uy_thac_cho_phep_override_ky_backfill`, `tests/test_merge_du_lieu_toan_cn.py::TestMergeBaselineUyThacSnapshot::test_baseline_hstd_goi_ca_hstd_va_uy_thac_snapshot` |
| **Ngày fix** | 2026-07-12 |

### J27 — Cảnh báo lãi tồn và Tổ đa hội không có danh sách đối chiếu ngay tại chỗ
| | |
|---|---|
| **File** | `tabs/tab_uy_thac.py`, `services/uy_thac_service.py` |
| **Dấu hiệu** | Mục Tổng quan chỉ báo có lãi tồn và số Tổ xuất hiện ở hơn một Hội, nhưng người dùng không biết hồ sơ/Tổ nào cần kiểm tra |
| **Nguyên nhân** | Khối cảnh báo chỉ dùng chỉ tiêu tổng và hàm đếm; chưa dựng bảng chi tiết theo cùng phạm vi PGD đang xem |
| **Fix** | Tổng hợp danh sách Tổ/Hội có lãi tồn và danh sách Tổ đa hội theo `PGD + Xã + Tổ`, rồi hiển thị hai bảng mở ngay dưới cảnh báo |
| **Test** | `tests/test_uy_thac_service.py::test_danh_sach_to_co_lai_ton_tong_hop_theo_to_va_hoi`, `tests/test_uy_thac_service.py::test_danh_sach_to_da_hoi_hien_day_du_cac_hoi` |
| **Ngày fix** | 2026-07-14 |

### J28 — Màn chọn workspace dùng hằng số tên Chi nhánh nhưng thiếu import
| | |
|---|---|
| **File** | `app.py` → `render_workspace_picker()` |
| **Dấu hiệu** | Ứng dụng dừng với `NameError: name 'TEN_CHI_NHANH_HIEN_THI' is not defined` khi mở màn chọn workspace |
| **Nguyên nhân** | Giao diện mới tham chiếu `TEN_CHI_NHANH_HIEN_THI` trong hai f-string nhưng hằng số chưa được thêm vào danh sách import từ `config.py` |
| **Fix** | Import `TEN_CHI_NHANH_HIEN_THI` ở module-level cùng các hằng số cấu hình khác |
| **Test** | Compile `app.py`, kiểm tra convention và import module thành công |
| **Ngày fix** | 2026-07-16 |

### C31 — CDTO toàn Chi nhánh bị cộng gần gấp đôi sau upload
| | |
|---|---|
| **File** | `data/cdtotkvv.py`, `data/pgd.py`, `services/upload_service.py`, `tabs/tab_upload_khnv.py` |
| **Dấu hiệu** | Kỳ 06/2026 có 4.560 Tổ thực tế nhưng một số màn hình đọc lịch sử ghi nhận 8.885 dòng |
| **Nguyên nhân** | File toàn CN 4.560 dòng từng bị import như file Hội sở; lần upload toàn CN sau đó tách đúng 22 đơn vị nhưng bản lịch sử Hội sở không được ghi đè, nên loader concat file sai với 21 file PGD và cộng dư 4.325 dòng |
| **Fix** | Cho luồng upload toàn CN ghi đè lịch sử đã tách, chặn import file nhiều đơn vị vào một đơn vị, đồng thời loại trùng phòng vệ theo `ma_dv + ma_to` khi đọc lịch sử |
| **Test** | `tests/test_cdtotkvv_history.py` |
| **Ngày fix** | 2026-07-14 |

### C32 — KPI CDTO tính cả Tổ dư nợ 0 và bỏ sót nhãn `Yếu kém`
| | |
|---|---|
| **File** | `data/cdtotkvv.py`, `services/cdtotkvv_service.py`, `snapshot_service.py`, `tabs/tab_cdtotkvv.py` |
| **Dấu hiệu** | Kỳ 06/2026 hiển thị 4.560 Tổ thay vì 4.557 Tổ còn dư nợ; sáu Tổ `Yếu kém` có thể bị hiển thị thành 0 Tổ Yếu |
| **Nguyên nhân** | Các loader chỉ kiểm tra STT hợp lệ, không lọc `du_no > 0`; code tổng hợp so sánh đúng chuỗi `Yếu` trong khi file nguồn dùng `Yếu kém` |
| **Fix** | Chuẩn hóa tập phân tích dùng chung: giữ `du_no > 0`, quy đổi `Yếu kém` về `Yếu`; áp dụng phòng vệ tại aggregator/snapshot và lọc dư nợ dương khi đối chiếu HSTD |
| **Test** | `tests/test_cdtotkvv_history.py::test_chuan_hoa_phan_tich_bo_to_du_no_0_va_gop_nhan_yeu_kem`, `tests/test_cdtotkvv_history.py::test_tong_hop_theo_pgd_chi_dem_to_co_du_no_va_dem_yeu_kem`, `tests/test_cdtotkvv_history.py::test_snapshot_cdto_phong_ve_loai_du_no_0_va_dem_yeu_kem` |
| **Ngày fix** | 2026-07-14 |

### C33 — Đối chiếu CDTO/HSTD đếm theo tên Tổ thay vì Mã Tổ
| | |
|---|---|
| **File** | `data/cdtotkvv.py`, `tabs/tab_cdtotkvv.py` |
| **Dấu hiệu** | CDTO có 4.557 Tổ nhưng đối chiếu HSTD báo 4.555; các Tổ đổi tên hoặc cùng Tổ trưởng làm số lượng khó giải thích |
| **Nguyên nhân** | Hàm đối chiếu cũ bỏ qua cột `Mã tổ` đã có trong `hstd.parquet`, group theo `PGD + Xã + Tên tổ`; đồng thời chưa loại mã `0000000` là dư nợ không qua Tổ |
| **Fix** | Đối chiếu bằng `Mã PGD + Mã tổ`, chỉ tính tổng dư nợ dương, loại `0000000`; tách `Hình thức vay = 1` thành ghi chú cho vay trực tiếp; hiển thị số mã khớp và danh sách Tổ ủy thác còn thiếu CDTO |
| **Test** | `tests/test_cdtotkvv_history.py::test_doi_chieu_hstd_theo_ma_to_loai_ma_0_va_hien_to_thieu_cdto` |
| **Ngày fix** | 2026-07-14 |

### J29 — Pre-commit phụ thuộc PATH và xử lý đối số file chưa an toàn
| | |
|---|---|
| **File** | `pre_commit.bat`, `scripts/check_conventions.py` |
| **Dấu hiệu** | Batch trả exit 1 với thông báo `python is not recognized` dù dự án có venv; gọi từ thư mục khác hoặc truyền đường dẫn có khoảng trắng có thể không chạy đúng; `backups` vẫn bị convention checker quét |
| **Nguyên nhân** | Script gọi thẳng `python`, dùng đường dẫn tương đối theo current directory và nội suy tên file trực tiếp vào Python source; danh sách skip giữa hai bước không đồng nhất |
| **Fix** | Chuyển về thư mục chứa batch; kiểm tra lần lượt `VBSP_PYTHON`, hai venv và PATH; truyền tên file qua `sys.argv`; xử lý từng đối số bằng `%~f1`; thêm `venv` và `backups` vào `_SKIP_DIRS` |
| **Test** | Chạy `pre_commit.bat db.py`, chạy batch từ thư mục ngoài dự án, truyền file `.py` bằng đường dẫn tuyệt đối có khoảng trắng |
| **Ngày fix** | 2026-07-17 |

### J30 — Hàm đọc DB trả fallback nhưng không ghi nhận lỗi thật
| | |
|---|---|
| **File** | `db.py` → `doc_kv()`, `doc_kv_prefix()`, `doc_kv_nhieu()`, `doc_kv_history()`, các hàm đọc ghi chú |
| **Dấu hiệu** | Lỗi SQLite hoặc JSON hỏng bị hiển thị giống trạng thái không có dữ liệu, không có traceback để điều tra |
| **Nguyên nhân** | Các hàm bắt rộng `Exception` rồi trả `None`, `{}` hoặc `[]` mà không logging |
| **Fix** | Giữ nguyên giá trị fallback để tương thích UI, đồng thời thêm `logger.error(..., exc_info=True)` với key/prefix hoặc số lượng phần tử, không log nội dung dữ liệu |
| **Test** | Convention check và compile `db.py`; kiểm tra các test DB hiện có giữ nguyên kiểu trả về |
| **Ngày fix** | 2026-07-17 |

### J31 — Data validation và compile-all bỏ sót lỗi trong scripts
| | |
|---|---|
| **File** | `pre_commit.bat`, `scripts/validate_data.py`, `db.py` |
| **Dấu hiệu** | `pre_commit.bat` chạy toàn project nhưng không compile `scripts/*.py`; `validate_data.py` có thể báo schema nhiễu cho NQ11/GQVL và chưa phát hiện thiếu đơn vị, trùng khế ước hoặc ngày số liệu phân tán |
| **Nguyên nhân** | Compile-all dùng filter loại cả thư mục `scripts`; validate chỉ kiểm tổng/số âm cơ bản và dùng danh sách cột phụ HSTD cho mọi loại parquet |
| **Fix** | Cho compile-all kiểm cả `scripts/*.py`; validate tách required/nice columns theo từng parquet, kiểm đủ 22 đơn vị, khóa nghiệp vụ trống, trùng `PGD + Số khế ước`, ngày số liệu không parse/phân tán; DB writer chuẩn hóa `None` trước khi ghi audit |
| **Test** | Compile `db.py` và `scripts/validate_data.py`; chạy `python scripts/validate_data.py` |
| **Ngày fix** | 2026-07-17 |

### J32 — Validate HSTD bỏ sót `Mã tổ` và báo cột lạ quá nhiễu
| | |
|---|---|
| **File** | `scripts/validate_data.py` |
| **Dấu hiệu** | Script chỉ báo 14 dòng trùng khóa, không phát hiện 594 dòng dư nợ dương nhưng thiếu `Mã tổ`; mục “cột lạ” in gần như toàn bộ schema HSTD nên khó đọc |
| **Nguyên nhân** | `_HSTD_CODE_COLS` chỉ kiểm `Mã PGD` và `Mã xã`, bỏ quên `Mã tổ`; whitelist cột HSTD viết tay ngắn hơn schema thực tế nên sinh nhiều nhiễu |
| **Fix** | Thêm `COT_MA_TO` vào nhóm mã bắt buộc, dựng tập cột chuẩn từ các hằng `COT_*` trong `config.py`, rút gọn đầu ra cột chưa map và tách kiểm đủ đơn vị theo từng parquet |
| **Test** | Compile + convention `scripts/validate_data.py`; chạy `python scripts/validate_data.py` xác nhận còn đúng 2 cảnh báo nghiệp vụ thật |
| **Ngày fix** | 2026-07-17 |

### J33 — Test tongquan ghi đè coverage cũ bằng assertion quá lỏng
| | |
|---|---|
| **File** | `tests/test_tongquan_service.py` |
| **Dấu hiệu** | Bộ test vẫn 15/15 pass nhưng có assertion dạng `>= 4`, comment sai dữ liệu mẫu, và làm rơi coverage cũ cho `tinh_tqpgd_extended`/luồng đến hạn |
| **Nguyên nhân** | File tracked cũ bị thay thế bằng bộ test mới tối giản, thiên về “pass” hơn là khóa hành vi nghiệp vụ |
| **Fix** | Viết lại 15 test với assertion chặt, dùng `COT_*` đúng convention, phục hồi các case quan trọng về lọc dư nợ, KPI, cơ cấu CT, tổng quan PGD mở rộng và tổng hợp đến hạn |
| **Test** | Compile + convention `tests/test_tongquan_service.py`; chạy `pytest tests/test_tongquan_service.py` và bộ tổng 149 test |
| **Ngày fix** | 2026-07-17 |

### J34 — State điều hướng giữ label parent accordion làm workspace render sai tab con
| | |
|---|---|
| **File** | `workspaces/ws_management.py` |
| **Dấu hiệu** | Role `admin_cn`/`manager_cn` mở lại session cũ có thể thấy nội dung hoặc sidebar của `🏦 Nguồn vốn địa phương` không khớp, vì state còn giữ label parent thay vì label child thực thi được |
| **Nguyên nhân** | Menu mới đổi `🏦 Nguồn vốn địa phương` từ item có `fn` sang accordion có `children`; `valid_labels` vẫn chấp nhận label parent nên nav cũ không bị loại, nhưng luồng render/sidebar không chuẩn hóa về child đầu tiên |
| **Fix** | Thêm `_normalize_active_label()` để map label parent accordion sang child đầu tiên ở cả `render_sidebar_menu()` và `render()`, sau đó persist lại state/kv bằng label child chuẩn hóa |
| **Test** | Compile + convention `workspaces/ws_management.py`; import `workspaces.ws_management` thành công |
| **Ngày fix** | 2026-07-17 |

### J35 — Nhấp parent accordion chỉ mở menu, không đổi nội dung workspace
| | |
|---|---|
| **File** | `workspaces/ws_management.py` → `render_sidebar_menu()` ~dòng 401 |
| **Dấu hiệu** | Nhấp `🏦 Nguồn vốn địa phương` chỉ mở danh sách con; vùng bên phải vẫn hiển thị tab `📊 Thông tin chung` |
| **Nguyên nhân** | Handler nút parent chỉ đảo `ws_mgmt_acc_*` rồi rerun, không cập nhật `state.nav_ws_mgmt_menu`; `_normalize_active_label()` vì thế không có label parent mới để chuẩn hóa |
| **Fix** | Mỗi khi nhấp parent có children, gán `state.nav_ws_mgmt_menu` bằng label child đầu tiên trước `st.rerun()`; child active sẽ giữ accordion mở sau rerun |
| **Test** | Compile, convention check và kiểm tra tĩnh handler cập nhật child đầu tiên trước rerun |
| **Ngày fix** | 2026-07-18 |

### J36 — Session Streamlit giữ cache menu cũ làm sidebar và nội dung lệch nhau
| | |
|---|---|
| **File** | `workspaces/ws_management.py` → `render()` ~dòng 575 |
| **Dấu hiệu** | Sau khi đổi `🏦 Nguồn vốn địa phương` từ accordion sang một trang gộp, sidebar có thể đã đúng nhưng vùng bên phải vẫn giữ `📊 Thông tin chung` hoặc render theo cấu trúc menu cũ trong cùng session |
| **Nguyên nhân** | `render()` lưu `_mgmt_all_items_cache` trong `st.session_state` theo `id(df_full)`, nên hot-reload/code mới vẫn có thể dùng danh sách item và lambda cũ; trong khi sidebar build lại menu mới trực tiếp |
| **Fix** | Bỏ cache danh sách menu trong `render()`; `_build_all_items()` rẻ và được gọi lại mỗi rerun để sidebar và nội dung luôn dùng cùng cấu trúc mới nhất |
| **Test** | Compile, convention check và kiểm tra tĩnh không còn tham chiếu `_mgmt_all_items_cache` trong `workspaces/ws_management.py` |
| **Ngày fix** | 2026-07-18 |

### J37 — Badge Mã NĐT mới có số nhưng tab mặc định không hiện danh sách phát sinh
| | |
|---|---|
| **File** | `tabs/tab_quan_ly_ndt_dp.py` → `render()` ~dòng 766 |
| **Dấu hiệu** | Nhãn tab hiển thị `🏷️ Mã NĐT địa phương (87 mới)` nhưng khi mở tab người dùng chỉ thấy màn `📊 Tổng quan`/danh mục rule, không thấy danh sách 87 mã mới |
| **Nguyên nhân** | Số mới được tính ở trang cha, còn tab quản lý dùng radio mặc định `📊 Tổng quan`; danh sách phát sinh nằm ở chế độ `🆕 Mã mới từ HSTD` nên dễ bị hiểu là không có dữ liệu |
| **Fix** | Đếm nhanh mã mới từ `df_full`; nếu còn mã mới và session chưa tự mở lần nào, đặt `st.session_state["ndt_dp_mode"] = "🆕 Mã mới từ HSTD"` để hiện ngay bảng phát sinh |
| **Test** | Compile, convention check và kiểm tra tĩnh có helper `_dem_ma_moi_tu_hstd()` cùng auto-open mode trước `st.radio()` |
| **Ngày fix** | 2026-07-18 |

### J38 — Launcher mở browser quá sớm và thoát ngay không hiện lỗi
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat` |
| **Dấu hiệu** | Double-click launcher không vào app; người dùng chỉ thấy cửa sổ console đen chớp/tắt hoặc Chrome mở `localhost:8502` khi server chưa sẵn sàng |
| **Nguyên nhân** | Batch mở trình duyệt trước khi Streamlit lắng nghe port; kiểm tra `import streamlit` nuốt stderr nên lỗi môi trường không rõ; nếu Streamlit thoát mã 0 thì console cũng đóng ngay |
| **Fix** | Kiểm tra import trực tiếp trên console; helper ẩn chờ port 8502 rồi mới mở browser; truyền `--server.headless true`; sau khi Streamlit thoát luôn in trạng thái và `pause` để đọc lỗi |
| **Test** | Chạy `cmd /c Chay_VBSP_SCM.bat` trong sandbox xác nhận lỗi import được in ra; kiểm tra diff và trạng thái git |
| **Ngày fix** | 2026-07-19 |

### J39 — Helper tự mở trình duyệt trong launcher vẫn tạo cửa sổ chớp
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat`, `run.bat` |
| **Dấu hiệu** | Sau khi thêm logic chờ server, máy người dùng vẫn còn hiện tượng cửa sổ đen chớp liên tục và app không vào được |
| **Nguyên nhân** | `start powershell -WindowStyle Hidden ...` vẫn có thể tạo process/cửa sổ phụ trên một số máy; shortcut cũng có thể trỏ sang `run.bat` cũ còn `start "" http://localhost:8502` |
| **Fix** | Bỏ hoàn toàn tự mở browser/helper PowerShell ở cả hai launcher; chỉ chạy Streamlit foreground và in URL để người dùng mở thủ công sau khi thấy dòng `Local URL` |
| **Test** | Kiểm tra tĩnh `Chay_VBSP_SCM.bat` và `run.bat` không còn lệnh `start`; chạy batch trong sandbox xác nhận lỗi hiện trực tiếp, không spawn browser/helper |
| **Ngày fix** | 2026-07-19 |

### J40 — Python venv trả mã 0 nhưng không thực thi lệnh
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat`, `run.bat` |
| **Dấu hiệu** | `python -m streamlit run app.py` thoát mã 0 ngay, không in `Local URL`, không mở port 8502; app không vào được dù bước kiểm tra Streamlit có thể báo OK |
| **Nguyên nhân** | Venv/Python nền hỏng hoặc không tương thích, khiến `python.exe` trả về nhưng không thực thi nội dung `-c`/script; kiểm tra bằng exit code đơn thuần không phát hiện được |
| **Fix** | Thêm probe bắt buộc Python ghi file `tmp/python_exec_check.txt`; nếu file không xuất hiện hoặc nội dung không đúng thì dừng launcher và yêu cầu cài Python 3.12 + chạy lại `setup_env.bat`. `setup_env.bat` cũng có probe riêng, ưu tiên `py -3.12`/`py -3.13` và chặn Python 3.14+ để không tái tạo venv lỗi |
| **Test** | Chạy batch trong sandbox xác nhận lỗi Python không bị hiểu nhầm là Streamlit OK; probe không phụ thuộc stdout/stderr |
| **Ngày fix** | 2026-07-19 |

### J41 — Khó phân biệt launcher thật bị gọi lặp hay cửa sổ từ nguồn khác
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat` |
| **Dấu hiệu** | Sau khi bỏ `start`/PowerShell, người dùng vẫn thấy cửa sổ đen bật tắt liên tục khi chạy launcher sau khởi động máy |
| **Nguyên nhân** | Cần phân biệt `Chay_VBSP_SCM.bat` thật có bị gọi lặp hay cửa sổ đến từ task/shortcut/process khác; quan sát bằng mắt không đủ vì process có thể sống rất ngắn |
| **Fix** | Thêm khóa single-instance `tmp/vbsp_launcher.lock` và log từng bước vào `logs/launcher_last.log`; nếu file thật chạy, log luôn ghi mốc `START`, bước kiểm tra và lỗi cuối |
| **Test** | Chạy `cmd /c Chay_VBSP_SCM.bat` xác nhận log ghi lỗi Python probe và batch dừng ở `pause`, không lặp |
| **Ngày fix** | 2026-07-19 |

### J42 — `setup_env.bat` báo `'t'/'not' is not recognized`
| | |
|---|---|
| **File** | `setup_env.bat` |
| **Dấu hiệu** | Ngay bước `[0/6] Kiem tra Python...`, CMD in `'t' is not recognized` và `'not' is not recognized` trước khi báo lỗi Python |
| **Nguyên nhân** | Batch dùng biến lệnh Python có khoảng trắng (`py -3.12`) trong các block `if (...)` lồng nhau; CMD parse/expand sớm làm vỡ câu lệnh thành token rác |
| **Fix** | Viết lại `setup_env.bat` bản ASCII tối giản, chỉ dùng `py -3.12`, dùng nhãn `goto` thay cho block lồng phức tạp và probe Python bằng file tạm |
| **Test** | Chạy `cmd /c setup_env.bat` khi chưa có Python 3.12: báo gọn `Khong tim thay Python 3.12`, không còn `'t'/'not'` |
| **Ngày fix** | 2026-07-19 |

### J43 — Streamlit lỗi `ModuleNotFoundError: google.protobuf` dù pip báo installed
| | |
|---|---|
| **File** | `setup_env.bat`, `venv` |
| **Dấu hiệu** | `Chay_VBSP_SCM.bat` qua được Python probe nhưng lỗi ở bước `Kiem tra Streamlit`; log có `ModuleNotFoundError: No module named 'google.protobuf'` hoặc trước đó thiếu `blinker` |
| **Nguyên nhân** | Lần cài requirements bị nửa vời: `.dist-info` tồn tại nên pip tưởng đã cài, nhưng thư mục module thật trong `site-packages` bị thiếu; `pip check` có thể không bắt lỗi namespace package này |
| **Fix** | Chạy lại `pip install -r requirements.txt`, ép `pip install --force-reinstall protobuf`; thêm bước force reinstall `protobuf` và `pip check` vào `setup_env.bat` |
| **Test** | `python -c "import streamlit; print(streamlit.__version__)"` trả `1.59.2`; `pip check` báo `No broken requirements found` |
| **Ngày fix** | 2026-07-19 |

### J44 — Launcher chạy ổn nhưng không tự mở Chrome
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat`, `run.bat` |
| **Dấu hiệu** | Server Streamlit đã lên `Local URL: http://localhost:8502` nhưng Chrome không tự bật như trước |
| **Nguyên nhân** | Trong lúc xử lý lỗi cửa sổ đen chớp, launcher được chuyển sang `--server.headless true` và bỏ mọi lệnh tự mở trình duyệt để loại trừ nguồn spawn cửa sổ phụ |
| **Fix** | Đổi sang `--server.headless false` để chính Streamlit tự mở trình duyệt sau khi server sẵn sàng; vẫn không dùng `start chrome`/PowerShell phụ |
| **Test** | Kiểm tra tĩnh hai launcher dùng `--server.headless false` và không có `start chrome`/PowerShell |
| **Ngày fix** | 2026-07-19 |

### J45 — Launcher báo còn lần khởi động khác dù app đã tắt
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat` |
| **Dấu hiệu** | Batch báo `VBSP-SCM dang co mot lan khoi dong khac dang chay` và yêu cầu xóa `tmp/vbsp_launcher.lock`, dù port 8502 không chạy |
| **Nguyên nhân** | Lần chạy trước bị dừng bằng cách đóng cửa sổ hoặc bị ngắt trước nhãn cleanup, làm thư mục lock còn sót |
| **Fix** | Khi lock tồn tại, launcher kiểm tra port 8502; nếu port không listening thì tự xóa lock cũ và chạy tiếp |
| **Test** | Xóa lock thủ công lần hiện tại; kiểm tra tĩnh nhánh stale lock trong `Chay_VBSP_SCM.bat` |
| **Ngày fix** | 2026-07-19 |

### J46 — Pandas báo thiếu dependency dateutil
| | |
|---|---|
| **File** | `setup_env.bat`, `Chay_VBSP_SCM.bat`, `venv` |
| **Dấu hiệu** | App báo `ImportError: Unable to import required dependency dateutil`; kiểm tra `venv\Scripts\python.exe` có thể báo đang trỏ về `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe` đã không còn tồn tại |
| **Nguyên nhân** | Python 3.12 gốc bị gỡ hoặc venv bị cài nửa vời, làm pandas còn metadata nhưng thiếu module `dateutil`/`python-dateutil` hoặc venv không chạy được Python nền |
| **Fix** | `setup_env.bat` force-reinstall `python-dateutil` cùng `protobuf`, kiểm tra `import dateutil`, và fallback sang Python 3.12 trực tiếp trong `%LOCALAPPDATA%` nếu Python Launcher `py -3.12` không nhận bản cài; launcher kiểm tra sớm `pandas/dateutil` để dừng với thông báo rõ |
| **Test** | Cài lại `python-dateutil` và `pandas` trong venv; `import pandas/dateutil/streamlit/google.protobuf/blinker` OK; `pip check` OK; `app.py` compile OK |
| **Ngày fix** | 2026-07-19 |

### J47 — Launcher báo app đang chạy dù không có CMD nào
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat` |
| **Dấu hiệu** | Launcher báo `App dang chay tren cong 8502` nhưng người dùng không thấy cửa sổ CMD/Streamlit; `localhost:8502` không truy cập được |
| **Nguyên nhân** | Batch dùng `%errorlevel%` bên trong block `if exist "%LOCK_DIR%" (...)`; CMD mở rộng biến trước khi chạy `netstat`, nên có thể dùng giá trị cũ và nhận nhầm port đang listening |
| **Fix** | Đổi các nhánh kiểm tra port/lock sang `if not errorlevel 1` và `if errorlevel 1` để đọc trạng thái runtime đúng; xóa lock cũ `tmp\vbsp_launcher.lock` |
| **Test** | Sau khi xóa lock: `Test-Path tmp\vbsp_launcher.lock` = False; `netstat :8502` không có dòng listening; health endpoint không còn kết nối khi app đã tắt |
| **Ngày fix** | 2026-07-19 |

### J50 — daily_report.py: 2 hàm cảnh báo chết im do sai signature + sai cột
| | |
|---|---|
| **File** | `scripts/daily_report.py` → `_canh_bao_qh_moi()` dòng ~540, `_canh_bao_khoanh_tang()` dòng ~621 |
| **Dấu hiệu** | Hàm không raise exception nhưng luôn trả về 0; không gửi Telegram |
| **Nguyên nhân** | (1) Gọi `doc_snapshot_range(tu_ky=None, den_ky=None, n_ky=2)` — param `n_ky` không tồn tại trong hàm thật, gọi sai signature. (2) Dùng `COT_TEN_PGD`, `COT_TONG_DU_NO`, `COT_DU_NO_QH`, `COT_DU_NO_KHOANH` (tên cột tiếng Việt) nhưng `doc_snapshot()` trả về DataFrame với cột snake_case: `ten_pgd`, `tong_du_no`, `du_no_qh`, `du_no_khoanh` |
| **Fix** | Thay `doc_snapshot_range(n_ky=2)` bằng `danh_sach_ky()` + `ky_baseline()` + `doc_snapshot()`; đổi tham chiếu cột sang snake_case; lọc bỏ dòng `__CN__` |
| **Ngày fix** | 2026-07-19 |

### J49 — ws_executive.py: biến động PGD dùng `_ds_ky[-2]` = kỳ gần cũ nhất thay vì kỳ trước
| | |
|---|---|
| **File** | `workspaces/ws_executive.py` → `_render_hom_nay()` dòng ~1104 |
| **Dấu hiệu** | Bảng "PGD biến động ≥ 5%" so sánh với kỳ rất xa trong quá khứ (gần cuối danh sách), biến động luôn rất lớn |
| **Nguyên nhân** | `danh_sach_ky()` sorted giảm dần (mới → cũ), nên `_ds_ky[-2]` là kỳ thứ hai từ cuối — gần kỳ cũ nhất, không phải kỳ trước |
| **Fix** | Dùng `ky_baseline(_ds_ky, _ds_ky[0])` thay vì `_ds_ky[-2]`; đồng thời sửa `COT_TEN_PGD`/`COT_TONG_DU_NO` → snake_case `ten_pgd`/`tong_du_no` |
| **Ngày fix** | 2026-07-19 |

### J48 — Cửa sổ đen chớp do `.venv` Python 3.14 cũ bị probe liên tục
| | |
|---|---|
| **File** | `.venv`, `venv` |
| **Dấu hiệu** | Nhiều cửa sổ đen/conhost chớp liên tục dù `Chay_VBSP_SCM.bat` không ghi log START mới; process monitor bắt được nhiều `D:\VBSP-SCM\.venv\Scripts\python.exe -I -c "...sys.version_info..."` sinh ra rồi tắt rất nhanh |
| **Nguyên nhân** | Trong repo còn `.venv` cũ tạo bằng Python 3.14 (`C:\Users\dell\AppData\Local\Programs\Python\Python314`); IDE/agent khác tự quét interpreter `.venv` liên tục, mỗi lần probe tạo `conhost.exe` nên thấy màn hình CMD chớp |
| **Fix** | Đổi tên `.venv` cũ thành `.venv_py314_disabled_20260719`; app tiếp tục dùng `venv` Python 3.12 |
| **Test** | Sau khi đổi tên: bắt process 8 giây không còn match `VBSP-SCM\.venv`; `venv\Scripts\python.exe -c "import pandas; import streamlit"` OK |
| **Ngày fix** | 2026-07-19 |

### J51 — `st.cache_data` không bust cache vì tham số sentinel bắt đầu bằng `_`
| | |
|---|---|
| **File** | `tabs/tab_hhi.py`, `tabs/tab_quan_ly_ndt_dp.py` |
| **Dấu hiệu** | Mã NĐT mới từ HSTD hoặc file Excel xuất ở tab Nguồn vốn địa phương có thể giữ dữ liệu cũ sau khi HSTD đổi; Excel còn có nguy cơ dùng lại dữ liệu giữa view CN/PGD |
| **Nguyên nhân** | Streamlit bỏ qua tham số bắt đầu bằng `_` khi hash cache. Các helper cache dùng `_ts`, `_is_pgd_view`, `_extra_cols`, nên sentinel `ts_hstd` và view context không tham gia cache key |
| **Fix** | Đổi sentinel/cache key thành tham số không có `_`: `ts`, `is_pgd_view`, `extra_cols`, `view_key`; truyền `ts_hstd` xuống đầy đủ tới `_render_ma_moi_tu_hstd()` |
| **Ngày fix** | 2026-07-19 |

### J52 — Fallback xuất Excel rỗng có thể crash tiếp
| | |
|---|---|
| **File** | `tabs/tab_hhi.py` → `render()` phần xuất Excel ~dòng 555 |
| **Dấu hiệu** | Nếu `_cached_excel_sheets()` lỗi, nhánh `except` gọi `xuat_excel({})`; openpyxl có thể lỗi tiếp vì workbook không có sheet nào |
| **Nguyên nhân** | Fallback tạo workbook từ dict rỗng và không log exception gốc, trái pattern không nuốt lỗi |
| **Fix** | Log `logger.error(..., exc_info=True)`, hiện cảnh báo Streamlit, và tạo workbook fallback có sheet `Lỗi xuất file` chứa thông tin lỗi |
| **Test** | Kiểm tra tĩnh phần `except Exception as e` không còn gọi `xuat_excel({})`; compile bị chặn do venv Python 3.12 nền không tạo được process |
| **Ngày fix** | 2026-07-19 |

---

### B36 — Sub-tab "Đến hạn" trong tab Cảnh báo Tín dụng chồng chức năng với tab_den_han
| | |
|---|---|
| **File** | `tabs/tab_canh_bao_nqh.py` → `render()` sub_labels + `_render_den_han_tab()`; `workspaces/ws_management.py` dòng 334 |
| **Dấu hiệu** | Tab "⏰ Nợ Đến Hạn" trong menu gọi `tab_canh_bao_nqh` → user phải chọn sub-tab "Đến hạn" 2 lần để xem; code trùng logic |
| **Nguyên nhân** | Sub-tab "Đến hạn" trong `tab_canh_bao_nqh.py` delegate qua `_render_den_han_tab()` → `tab_den_han.render()`, chồng với menu "⏰ Nợ Đến Hạn" cũng gọi `tab_canh_bao_nqh` |
| **Fix** | Xóa sub-tab "Đến hạn" khỏi `sub_labels` và `_render_den_han_tab()`; menu "⏰ Nợ Đến Hạn" trỏ thẳng `tab_den_han` |
| **Ngày fix** | 2026-07-19 |

### B37 — Dropdown PGD trong tab Nợ khoanh thiếu Hội sở
| | |
|---|---|
| **File** | `tabs/tab_no_khoanh.py` → `render()` dòng 867, `_render_cv368_kt()` dòng 722 |
| **Dấu hiệu** | User CN không lọc được Hội sở trong tab Nợ khoanh và CV 368 |
| **Nguyên nhân** | `_opts_pgd = ["Tất cả"] + DS_PGD` thiếu `DON_VI_CHI_NHANH` |
| **Fix** | Đổi thành `["Tất cả"] + [DON_VI_CHI_NHANH] + DS_PGD` ở cả 2 vị trí |
| **Ngày fix** | 2026-07-19 |

### B38 — Lọc NQH "trong tháng" sai kỳ khi dữ liệu cũ chạy sang tháng mới
| | |
|---|---|
| **File** | `tabs/tab_canh_bao_nqh.py` → `_render_nqh()` dòng 608, `_render_tong_hop()` dòng 221 |
| **Dấu hiệu** | Lọc "Chuyển nợ quá hạn trong tháng" dùng `datetime.now()` → nếu dữ liệu kỳ cũ (vd tháng 6) chạy sang tháng 7, kết quả lọc sai |
| **Nguyên nhân** | Fallback `datetime.now()` không dùng mốc thời gian từ dữ liệu |
| **Fix** | Dùng `lay_ngay_so_lieu(df)` từ `utils.py` (đọc `COT_NGAY_SL` max), fallback `datetime.now()` |
| **Ngày fix** | 2026-07-19 |

### B39 — Tổng hợp Cảnh báo Tín dụng còn dùng ngày máy và quyền session_state
| | |
|---|---|
| **File** | `tabs/tab_canh_bao_nqh.py` → `_dem_den_han()`, `_render_tong_hop()`, `_render_risk_heatmap()`, `_render_khoanh_sap_hh()`, `_render_gia_han()`, `_render_nqh_so_sanh_ky()` |
| **Dấu hiệu** | Card/bảng "Đến hạn ≤ 3 tháng" có thể lệch giữa kỳ dữ liệu cũ và ngày chạy app; admin được truyền qua workspace có thể không thấy cấu hình ngưỡng; trend chart N kỳ lỗi nhưng UI im lặng |
| **Nguyên nhân** | `_dem_den_han()` và bảng PGD dùng `pd.Timestamp.today()`; quyền đọc từ `st.session_state["role"]` thay vì role đã normalize trong render; `except Exception: pass` ở chart |
| **Fix** | `_dem_den_han(df, n_thang, ref_date)` nhận mốc `lay_ngay_so_lieu()`, `_render_tong_hop()` truyền `role` và dùng `la_admin_cn(role)`, chart log `logger.error(..., exc_info=True)` + hiện caption |
| **Test** | Compile + convention `tabs/tab_canh_bao_nqh.py`; kiểm tra tĩnh `_dem_den_han()` nhận `ref_date` và call site truyền mốc ngày số liệu |
| **Ngày fix** | 2026-07-19 |

### B41 — Tra cứu: chọn nhầm hồ sơ khi phân trang (static dataframe key)
| | |
|---|---|
| **File** | `tabs/tab_tracuu_v2.py` dòng ~437 |
| **Dấu hiệu** | User chọn row X trang 1, chuyển sang trang 2 → dialog mở hồ sơ sai (vị trí X + start_trang2) |
| **Nguyên nhân** | `key="tc_table"` cố định → Streamlit giữ nguyên `event.selection.rows` khi data chunk đổi, `pos = rows[0] + start` tính sai vị trí trong `ku_series` |
| **Fix** | Đổi thành `key=f"tc_table_p{page}"` để widget key đổi theo trang, reset selection tự động |
| **Test** | Compile OK |
| **Ngày fix** | 2026-07-19 |

### B40 — Badge mức độ rủi ro nợ khoanh phụ thuộc index nguồn
| | |
|---|---|
| **File** | `tabs/tab_no_khoanh.py` → bảng chi tiết nợ khoanh dòng ~1043 |
| **Dấu hiệu** | Cột `⚠️ Mức độ` có thể lệch dòng nếu DataFrame nguồn/hiển thị thay đổi index hoặc thứ tự trước khi gán |
| **Nguyên nhân** | Tính `con_lai` từ `df_kh[COT_NGAY_HH_KHOANH]` rồi gán vào `df_hien`, phụ thuộc align index ngầm |
| **Fix** | Tính trực tiếp từ `df_hien[COT_NGAY_HH_KHOANH]` trước khi gán badge |
| **Test** | Compile + convention `tabs/tab_no_khoanh.py` |
| **Ngày fix** | 2026-07-19 |

### B42 — Bảng PGD Nguồn vốn địa phương thiếu dòng tổng cộng
| | |
|---|---|
| **File** | `tabs/tab_hhi.py` → `_bang_theo_nv()`, `_render_sub_pgd()` dòng ~144, ~355 |
| **Dấu hiệu** | Bảng `Bảng chi tiết theo PGD` chỉ liệt kê từng PGD, không có dòng cuối để đối chiếu nhanh tổng TW/ĐP/Tổng toàn Chi nhánh |
| **Nguyên nhân** | `_bang_theo_nv()` chỉ trả dữ liệu đã group theo đơn vị và format hiển thị, chưa có tùy chọn chèn tổng sau khi cộng các nhóm |
| **Fix** | Thêm tham số `them_dong_tong`; khi bật, cộng các cột tiền trên số VND gốc, tính lại `Tỷ trọng ĐP (%)`, rồi append dòng `Tổng cộng` cuối bảng |
| **Test** | `tests/test_tab_hhi.py::test_bang_theo_nv_them_dong_tong_cuoi_bang` |
| **Ngày fix** | 2026-07-19 |

---

### J8 — `int(x or 0)` crash với whitespace-only string → `invalid literal for int() with base 10: ''`

| | |
|---|---|
| **File** | `tabs/tab_tien_do.py` → `_render_tong_quan()` dòng ~104, `_render_cap_nhat()` ~895, `_render_xuat()` ~1036-1037 |
| **Dấu hiệu** | `❌ Lỗi render ** Quản lý Công việc & Nhiệm vụ**: invalid literal for int() with base 10: ''` — cả tab bị crash qua ws_management.py line ~621 |
| **Nguyên nhân** | Pattern `int(r.get("pct_hoan_thanh") or 0)` dùng để guard `None`/`0`/`""`. Nhưng khi DB có giá trị whitespace-only `"  "`: `"  " or 0` = `"  "` (non-empty string là truthy), rồi `int("  ")` Python tự strip → raises `ValueError: invalid literal for int() with base 10: ''`. Nằm trong list comprehension không có try/except nên crash toàn tab. |
| **Fix** | Thêm helper `_to_int(val, default=0)` dùng try/except, thay 4 chỗ `int(x or 0)` → `_to_int(x)` |
| **Ngày fix** | 2026-07-19 |

**Pattern nguy hiểm — tránh lặp:**
```python
# ❌ SAI — whitespace-only string vượt qua guard `or 0`
int(r.get("pct_hoan_thanh") or 0)   # "  " or 0 = "  " → int("  ") → crash

# ✅ ĐÚNG — try/except bắt mọi giá trị lạ
def _to_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default
```

---

### J53 — Launcher mất biến trong block CMD
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat` dòng ~2-155 |
| **Dấu hiệu** | Launcher in `ECHO is off.`, báo `'""' is not recognized`, hoặc thoát mã `9009`; log/console cho thấy `%URL%` hoặc `%PY_EXE%` rỗng ở bước launch |
| **Nguyên nhân** | Batch bật delayed expansion nhưng vẫn đọc các biến vừa set trong block bằng `%VAR%`; CMD mở rộng `%VAR%` trước khi block chạy nên `PROBE_OK`, `PYVER`, `PY_CMD` hoặc `%errorlevel%` có thể stale/rỗng. Ngoài ra `PY_CMD=py -3.12` dùng chung với đường dẫn Python có khoảng trắng dễ làm vỡ command; ký tự Unicode trang trí và LF line endings có thể khiến CMD đọc sai encoding/label. |
| **Fix** | Dùng `!VAR!`/`!errorlevel!` trong block, tách `PY_CMD` và `PY_ARGS`, đổi auto-setup sang flow `goto` tuyến tính, chỉ chọn candidate Python nếu chạy được `--version`, và chuyển launcher về ASCII + CRLF. |
| **Test** | Kiểm tra tĩnh không còn `%errorlevel%` trong block probe, không còn `%PY_CMD%/%PYVER%/%PROBE_OK%`; quét file xác nhận `PY_EXE` được join bằng `%ROOT%\venv\Scripts\python.exe` sau khi strip trailing slash; chạy `cmd /v:on /c "Chay_VBSP_SCM.bat < NUL"` trên nhánh không có Python 3.12 để xác nhận batch dừng đúng ở thông báo thiếu Python và không chạy tiếp Streamlit. |
| **Ngày fix** | 2026-07-19 |

### J54 — Launcher không tự tắt Streamlit cũ đang chiếm port
| | |
|---|---|
| **File** | `Chay_VBSP_SCM.bat` dòng ~34-86, ~303-319 |
| **Dấu hiệu** | Double-click launcher khi còn cửa sổ Streamlit/CMD cũ: batch chỉ báo app đang chạy hoặc mở URL cũ, không tạo phiên app mới sạch |
| **Nguyên nhân** | Logic port conflict cũ coi `localhost:8502` đang `LISTENING` là thành công và thoát; lock cũ + port đang nghe cũng không xử lý process cũ |
| **Fix** | Thêm `:kill_port_processes`: lấy PID đang `LISTENING` trên `%PORT%` bằng `netstat`, kill đúng PID đó bằng `taskkill /F /PID`, chờ 2 giây rồi kiểm tra lại port trước khi chạy tiếp. Không kill đại trà mọi `python.exe`. |
| **Test** | Kiểm tra tĩnh có call `:kill_port_processes` ở cả nhánh lock và port conflict; chạy `cmd /v:on /c "Chay_VBSP_SCM.bat < NUL"` trên máy chưa có Python 3.12 để xác nhận batch vẫn dừng đúng ở lỗi môi trường, không vỡ cú pháp. |
| **Ngày fix** | 2026-07-19 |

---

### J55 — `venv` báo `Unable to create process` vì mất Python 3.12 nền
| | |
|---|---|
| **File** | `venv/pyvenv.cfg`, Python nền `C:\Users\Administrator\AppData\Local\Programs\Python\Python312` |
| **Dấu hiệu** | Chạy `venv\Scripts\python.exe` báo `Unable to create process using '"...\Python312\python.exe" ...'`; `py -0p` báo `No installed Pythons found`; Streamlit/app không khởi động dù thư mục `venv` còn tồn tại |
| **Nguyên nhân** | Virtualenv trên Windows phụ thuộc interpreter nền ghi trong `pyvenv.cfg`. Python 3.12 nền đã bị gỡ hoặc mất khỏi `AppData`, nên launcher trong `venv\Scripts` không tạo được process. Có thể kèm lock stale `tmp/vbsp_launcher.lock` khiến launcher nhận nhầm app đang chạy |
| **Fix** | Cài lại Python 3.12.7 vào đúng `...\Python312`, đổi tên `venv` cũ để backup, tạo lại `venv`, cài `requirements.txt`, chạy `pip check`, import smoke, compile app; xóa `tmp/vbsp_launcher.lock` nếu port 8502 không `LISTENING`. Nếu Python nền lại mất nhưng packages trong `venv` còn nguyên, có thể sửa nhanh `venv/pyvenv.cfg` trỏ sang Python 3.12.x còn tồn tại rồi chạy import smoke lại. |
| **Test** | `venv\Scripts\python.exe -c "import streamlit, pandas, gspread"` OK; `venv\Scripts\python.exe -m pip check` OK; `/_stcore/health` trả `200 ok`; browser mở được màn đăng nhập Phòng KH-NV |
| **Ngày fix** | 2026-07-23 |

---

### J56 — Đăng nhập Phòng KH-NV chậm do load/enrich HSTD lặp
| | |
|---|---|
| **File** | `app.py` → block load dữ liệu sau đăng nhập ~dòng 1260 |
| **Dấu hiệu** | Nhập mật khẩu/bấm đăng nhập xong phải chờ lâu ở lần đầu sau restart; log `app.ram` ghi `load_hstd: role=admin_cn ... rows=293496` |
| **Nguyên nhân** | Không phải `bcrypt` vì `checkpw` chỉ khoảng 0,24s. Sau `st.rerun()`, role Chi nhánh đọc `cache/hstd.parquet` full rồi đọc thêm bản `active_only`, sau đó `_enrich_hstd()` chạy cho cả hai DataFrame trên dataset lớn |
| **Fix** | Chỉ `_load_hstd(... active_only=False)` một lần cho role Chi nhánh, enrich bản full một lần, rồi dùng `_loc_hstd_active()` lọc hồ sơ còn dư nợ từ bản full đã enrich |
| **Test** | `venv\Scripts\python.exe -m py_compile app.py`; `venv\Scripts\python.exe scripts\check_conventions.py app.py` |
| **Ngày fix** | 2026-07-23 |

---

### J57 — daily_report.py không parse được ngày đến hạn `DD/MM/YYYY`
| | |
|---|---|
| **File** | `scripts/daily_report.py` → `_build_den_han_sheet()`, `generate_daily_report()`, `_tong_ket_thang()` |
| **Dấu hiệu** | Sheet `Đến hạn 30 ngày` chỉ có `⚠️ Lỗi truy vấn`; Telegram nhắc khoản đến hạn trong tháng có thể gửi rỗng dù HSTD có dữ liệu; kiểm DuckDB thấy `count(TRY_CAST("Ngày ĐH theo Gia hạn" AS DATE)) = 0` |
| **Nguyên nhân** | Parquet HSTD đang lưu `COT_NGAY_DH` dạng chuỗi Việt Nam `DD/MM/YYYY`. DuckDB `TRY_CAST(... AS DATE)` không parse được format này, còn các chỗ Pandas so sánh trực tiếp chuỗi với `Timestamp`/date làm lỗi hoặc lọc sai |
| **Fix** | Thêm `_duckdb_date_expr()` dùng `TRY_CAST` + `TRY_STRPTIME('%d/%m/%Y')`, dùng ngày đã parse cho Excel/Telegram; thêm `_parse_date_series()` với `dayfirst=True` cho tổng kết tháng |
| **Test** | `venv\Scripts\python.exe -m py_compile scripts\daily_report.py`; `venv\Scripts\python.exe scripts\check_conventions.py scripts\daily_report.py`; kiểm workbook tạm sheet `Đến hạn 30 ngày` ra 1.540 khoản với HSTD hiện tại |
| **Ngày fix** | 2026-07-24 |

---

### J58 — Scheduled Tasks VBSP trỏ về Python 3.14 cũ
| | |
|---|---|
| **File** | `scripts/setup_task_scheduler.ps1`; Windows Task Scheduler |
| **Dấu hiệu** | Task ở trạng thái `Ready` nhưng `LastTaskResult=2147942402` (`0x80070002`) hoặc `1`; Telegram/daily_report không chạy đều dù task đã bật |
| **Nguyên nhân** | Action của `VBSP-DailyReport`, `VBSP-NhacDeadline`, `VBSP-TelegramScheduler`, `VBSP-TelegramPolling` trỏ tới `C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe`, trong khi repo chuẩn dùng `D:\VBSP-SCM\venv\Scripts\python.exe` Python 3.12. Script setup cũng ưu tiên Python 3.14 nên có thể tái tạo cấu hình sai |
| **Fix** | Sửa `scripts/setup_task_scheduler.ps1` ưu tiên `$ProjectDir\venv\Scripts\python.exe`; chạy lại setup với `-PythonPath D:\VBSP-SCM\venv\Scripts\python.exe`; kiểm action 4 task Python đều trỏ đúng venv |
| **Test** | `Get-ScheduledTask` kiểm 5 task `Ready`; kiểm action/path không còn Python 3.14; `venv\Scripts\python.exe --version` = Python 3.12.13 |
| **Ngày fix** | 2026-07-24 |

---

### J59 — Cảnh báo rủi ro gộp vẫn phụ thuộc key/lịch NQH
| | |
|---|---|
| **File** | `scripts/daily_report.py`, `services/telegram_service.py`, `tabs/tab_telegram_admin.py` |
| **Dấu hiệu** | Sau khi gộp NQH + nợ khoanh, nếu `qh_moi` tắt hoặc không đúng giờ thì nợ khoanh có thể không gửi; nút `Gửi ngay` nợ khoanh vẫn dùng format tin riêng; phần trăm nợ khoanh hiển thị `+23.0%` thay vì `+23,0%` |
| **Nguyên nhân** | Job gộp chỉ được gọi qua `_trong_gio_gui("qh_moi")` và gửi bằng notify key `qh_moi`; đường gửi thủ công của `khoanh_tang` vẫn gọi `gui_canh_bao_khoanh_tang()` riêng; format `tang_pct` dùng `.replace(",", ",")` không đổi dấu thập phân |
| **Fix** | Thêm `_den_gio_gui_rui_ro()` chạy khi tới giờ của `qh_moi` hoặc `khoanh_tang` đang bật; thêm notify key `rui_ro_tin_dung`; chuyển helper cũ và nút `Gửi ngay` sang `_canh_bao_tong_hop_rui_ro()`; sửa format phần trăm nợ khoanh `.replace(".", ",")` |
| **Test** | `venv\Scripts\python.exe -m py_compile scripts\daily_report.py services\telegram_service.py tabs\tab_telegram_admin.py tests\test_telegram_service.py`; `venv\Scripts\python.exe scripts\check_conventions.py scripts\daily_report.py services\telegram_service.py tabs\tab_telegram_admin.py`; smoke inline xác nhận key `rui_ro_tin_dung`, mốc `31/12/2025`, format `+23,0%`, và lịch vẫn chạy khi chỉ bật `khoanh_tang`; pytest chưa chạy được vì venv thiếu module `pytest` |
| **Ngày fix** | 2026-07-24 |

---

### J60 — CODE_INDEX trỏ sai path và mô tả quá rộng về tab render
| | |
|---|---|
| **File** | `CODE_INDEX.md` |
| **Dấu hiệu** | Agent tra CĐ Tổ TK&VV gặp path không tồn tại `data/cdotkvv.py`; hoặc giả định mọi tab/submodule đều có `render(tab=None, **kwargs)` |
| **Nguyên nhân** | Typo tên module `cdtotkvv` và câu mô tả gom chung entrypoint tab với các submodule báo cáo/so sánh/upload |
| **Fix** | Sửa path sang `data/cdtotkvv.py`; đổi heading Tabs để nói rõ chỉ entrypoint thường có `render(...)`, submodule có thể dùng `render_*()` hoặc được gọi qua module init/workspace |
| **Test** | Kiểm tra lại path trong `CODE_INDEX.md` bằng filesystem; kiểm `CODE_INDEX` đã có entry trong `CHANGELOG.md` |
| **Ngày fix** | 2026-07-24 |

---

### J61 — File ref sau tách rules thiếu COT và sai signature
| | |
|---|---|
| **File** | `COT_REF.md`, `SIGNATURES.md`, `AGENTS.md` |
| **Dấu hiệu** | `COT_REF.md` tự mô tả là danh sách đầy đủ nhưng chỉ có 53/200 `COT_*`; `SIGNATURES.md` ghi sai một số hàm như `xuat_excel(sheets, ten_file)`, thiếu `username` ở `filter_bar()`/`loan_detail_drawer()`; checklist trong `AGENTS.md` bị rơi khỏi heading và ví dụ `auto_fill_document()` còn tham số cũ |
| **Nguyên nhân** | Khi tách rules chính sang file tra cứu, nội dung ref được rút gọn theo nhóm thường dùng nhưng pointer vẫn ghi "đầy đủ"; signature được chép theo tài liệu cũ thay vì đối chiếu lại code gốc |
| **Fix** | Bổ sung toàn bộ `COT_*` theo `config.py`; sửa signature tra nhanh theo code gốc; đổi heading section 8 trong `AGENTS.md` để checklist là subsection rõ ràng |
| **Test** | Đối chiếu count `COT_*` unique giữa `config.py` và `COT_REF.md`; grep lại các signature đã sửa trong code gốc |
| **Ngày fix** | 2026-07-24 |

---

Mỗi khi fix bug, copy template dưới đây và điền vào đúng mục:

```
### XX — [Tên lỗi ngắn gọn]
| | |
|---|---|
| **File** | `path/to/file.py` → `tên_hàm()` ~dòng NNN |
| **Dấu hiệu** | Exception message hoặc triệu chứng UI |
| **Nguyên nhân** | Giải thích 1-2 câu |
| **Fix** | Code snippet hoặc mô tả thay đổi |
| **Test** | `test_file.py::test_name` (nếu có) |
| **Ngày fix** | YYYY-MM-DD |
```
