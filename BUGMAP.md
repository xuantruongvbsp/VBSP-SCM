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

### B11 — Tab Tổng quan load lâu + không hiển thị "Thông tin tổng quát theo PGD"
| | |
|---|---|
| **File** | `tabs/tab_tongquan.py` (dòng ~530, ~573) + `services/tongquan_service.py` |
| **Dấu hiệu** | Sau phần "Cơ cấu dư nợ theo chương trình", phần "🟢 Thông tin tổng quát theo PGD" không hiển thị; app treo 8-12 giây |
| **Nguyên nhân** | (1) Dataframe gốc `df` bị trim lại dòng 573 nhưng điều kiện `if COT_TEN_PGD in df.columns:` dòng 530 cần `df` nguyên bản; (2) Hàm `tinh_tqpgd_extended()` thực hiện 5 `.merge()` liên tiếp, gây lag nặng trên DataFrame 50k rows |
| **Fix** | (1) Dòng 573: `df = df[cot_lay]` → `df_pgd_work = df[cot_lay]`; cập nhật tham chiếu dòng 574-605; (2) Gộp merge từ 5 lần → 2-3 lần trong `tinh_tqpgd_extended()`: khoanh + lãi tồn + DS cho vay tính chung 1 `.agg()` |
| **Load time** | Giảm từ 8-12s → 2-3s |
| **Ngày fix** | 2026-05-24 |

---

## C. Dữ liệu / DataFrame

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

### H5 — Loại bỏ "Kỳ báo cáo" khỏi Form/Sheet toàn bộ
| | |
|---|---|
| **File** | `tabs/tab_tien_do_nop.py` — toàn file |
| **Lý do** | Các loại báo cáo là sự kiện 1 lần (không lặp tháng/quý), không cần khái niệm "kỳ". PGD cũng muốn bỏ trường này khỏi Form. |
| **Thay đổi** | COT 8→7 cột (bỏ `ky_bao_cao`); deadline `{loai: {ky: dl}}` → `{loai: dl}`; bỏ dropdown kỳ ở 3 tab; ma trận PGD × Loại × Kỳ → PGD × Loại |
| **Ngày fix** | 2026-05-29 |

---

## I. Phân quyền / Role

### I1 — Logic role sai / bỏ sót role mới
| | |
|---|---|
| **Nguyên nhân** | Check role bằng chuỗi thô: `if role == "admin"` thay vì dùng helper |
| **Fix** | Dùng `from auth import la_phan_he_cn, la_phan_he_pgd, la_executive, la_admin_cn, normalize_role` |
| **Bảng nhanh** | `la_phan_he_cn(role)` → executive/admin_cn/manager_cn/admin/manager. `la_phan_he_pgd(role)` → admin_pgd/manager_pgd/user_pgd/user |

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
