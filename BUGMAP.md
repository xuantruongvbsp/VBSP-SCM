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

---

## B. Streamlit UI

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

---

## Template: Ghi nhận bug mới

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
