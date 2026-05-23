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

### C9 — `UnicodeEncodeError: surrogates not allowed` trong emoji
| | |
|---|---|
| **Dấu hiệu** | `UnicodeEncodeError: 'utf-8' codec can't encode characters ... surrogates not allowed` |
| **File** | Tab Cảnh báo NQH, bất kỳ tab nào dùng emoji trong markdown |
| **Nguyên nhân** | Một số ký tự emoji chứa surrogate pair không hợp lệ với UTF-8 strict mode |
| **Fix** | `.encode('utf-8', errors='replace').decode('utf-8')` hoặc thay emoji surrogate bằng emoji an toàn |
| **Ngày fix** | 2026-05-17 |

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

---

## I. Phân quyền / Role

### I1 — Logic role sai / bỏ sót role mới
| | |
|---|---|
| **Nguyên nhân** | Check role bằng chuỗi thô: `if role == "admin"` thay vì dùng helper |
| **Fix** | Dùng `from auth import la_phan_he_cn, la_phan_he_pgd, la_executive, la_admin_cn, normalize_role` |
| **Bảng nhanh** | `la_phan_he_cn(role)` → executive/admin_cn/manager_cn/admin/manager. `la_phan_he_pgd(role)` → admin_pgd/manager_pgd/user_pgd/user |

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

### J1 — UnboundLocalError: cannot access local variable 'X' where it is not associated with a value
| | |
|---|---|
| **File** | Bất kỳ file nào có `from x import Y` ở cả top-level lẫn trong thân hàm |
| **Dấu hiệu** | `UnboundLocalError: cannot access local variable 'Path' where it is not associated with a value` |
| **Nguyên nhân** | Import cục bộ `from pathlib import Path` trong thân hàm khiến Python coi `Path` là local variable cho toàn bộ hàm. Dòng code dùng `Path` phía trên import cục bộ sẽ bị `UnboundLocalError`. |
| **Fix** | Xóa import cục bộ thừa, dùng top-level import có sẵn. Chỉ import trong hàm khi thực sự cần lazy-load. |
| **Ngày fix** | 2026-05-22 |

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
