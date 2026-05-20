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
- [Template: Ghi nhận bug mới](#template-ghi-nhận-bug-mới)

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

### B5 — `ValueError: The truth value of a DataFrame is ambiguous`
| | |
|---|---|
| **File** | Thường gặp ở `ws_operation.py`, `tab_no_khoanh.py` |
| **Nguyên nhân** | Dùng `or` với DataFrame: `kwargs.get("df_full") or df` → Python cố evaluate bool của DataFrame |
| **Fix** | `df if _df_full is None else _df_full` — kiểm tra `is None` thay vì dùng `or` |

### B6 — Tab crash khi `tab=None` (context manager error)
| | |
|---|---|
| **File** | Các renderer trong `ws_operation.py` dùng `with tab_parent:` |
| **Nguyên nhân** | `tab=None` khi render ngoài context Streamlit tab |
| **Fix** | Thay `with tab_parent:` → `with get_tab_context(tab_parent):` (từ `utils.py`) |

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
