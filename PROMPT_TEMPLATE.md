# PROMPT TEMPLATE — VBSP-SCM
> Copy-paste vào Cursor/Windsurf. Điền [PLACEHOLDER] rồi xóa dòng không dùng.

---

## Template 1 — Bugfix (dùng khi có traceback)

```
Bugfix: [mô tả lỗi 1 câu]

Traceback gốc:
  File "[file]", line [N], in [function]
    [dòng lỗi]
[ExceptionType]: [message]

File cần sửa:
- [path/file.py] dòng [N]-[M]: [sửa gì]

Yêu cầu:
- Chỉ sửa đúng hàm [tên_hàm()], không thay đổi logic xung quanh
- Giữ nguyên rollback/audit/cache logic đã có
- Thêm comment giải thích fix

Tái sử dụng:
- [hàm/pattern có sẵn]

Không làm:
- Không import thêm dependency mới
- Không sửa signature hàm (caller không thay đổi)
```

---

## Template 2 — Thêm tính năng nhỏ (trong tab có sẵn)

```
Thêm [tính năng] vào [tab/file].

File cần sửa:
- [path/tab_xxx.py] dòng ~[N]: [thêm gì sau/trước đoạn nào]

Yêu cầu:
- Dùng db.doc_kv(key) / db.ghi_kv(key, value, username) để lưu dữ liệu
- Gọi db.ghi_audit(username, "action_name", "mô tả") sau khi ghi
- Gọi st.cache_data.clear() sau thao tác thành công
- Tiền tệ: nhập triệu → lưu VND (×1_000_000) → hiển thị fmt_ty()
- Widget key: dùng suffix unique tránh DuplicateElementKey

Key kv_store dùng:
- "[key_name]" — [mô tả dữ liệu lưu]

Tái sử dụng:
- config.DS_PGD cho danh sách PGD
- config.COT_* cho tên cột
- utils.fmt_ty() cho hiển thị tiền tệ
- auth.la_phan_he_cn(role) / la_phan_he_pgd(role) cho phân quyền

Trường hợp đặc biệt:
- [edge case cần xử lý]
```

---

## Template 3 — Upload file mới

```
Thêm loại file upload "[tên_loai]" vào [tab].

File cần sửa:
- services/upload_service.py: thêm hàm luu_[loai]()
- tabs/[tab].py dòng ~[N]: thêm UI upload

Yêu cầu upload_service:
- Validate qua kiem_tra_file() trước khi lưu
- Lưu vào [UPLOAD_DIR / "subfolder" / "filename"]
- Trả về KetQuaUpload(True/False, message, path)
- Ghi audit: db.ghi_audit(username, "upload_[loai]", f"file={ten} ({mb:.1f} MB)")

Yêu cầu tab UI:
- st.file_uploader() → gọi luu_[loai]()
- ket_qua.hien_thi() để hiển thị kết quả
- st.cache_data.clear() sau upload thành công
- Nếu trigger merge: gọi merge_du_lieu_toan_cn("[loai]") sau đó

Tái sử dụng:
- KetQuaUpload từ services/upload_service.py
- Pattern luu_pgd_file() / luu_file_he_thong() làm mẫu
```

---

## Template 4 — Thêm báo cáo / xuất Excel

```
Thêm báo cáo "[tên báo cáo]" vào [tab/service].

Dữ liệu nguồn:
- DataFrame: [biến df nào, từ đâu]
- Cột cần: [danh sách cột từ config.COT_*]
- Lọc: [điều kiện lọc]

File cần sửa:
- [tab hoặc service]: thêm hàm [tên_hàm]()
- [tab UI]: thêm nút xuất

Yêu cầu:
- Dùng xuat_excel() từ utils.py hoặc xuat_excel_chuyen_nghiep() từ excel_service.py
- Format tiền tệ: fmt_ty() trước khi đưa vào Excel
- Tên file: "[TEN_BAO_CAO]_{thang}_{nam}.xlsx"
- Ghi audit: db.ghi_audit(username, "xuat_[ten]", f"pgd={pgd} thang={thang}")

Tái sử dụng:
- ten_file_bao_cao() từ report_service.py cho đặt tên file
- xuat_sheet_don() từ report_service.py nếu 1 sheet đơn giản
```

---

## Template 5 — Fix UI / hiển thị

```
Fix UI: [mô tả vấn đề]

File cần sửa:
- [path/file.py] dòng ~[N]: [sửa gì]

Vấn đề hiện tại:
[paste đoạn code bị lỗi]

Mong muốn:
[mô tả kết quả đúng]

Ràng buộc:
- Không dùng NumberColumn cho cột tiền tệ — dùng .apply(fmt_ty) trước st.dataframe()
- Không dùng width='stretch' — dùng use_container_width=True
- CSS inject không dùng guard session_state (inject mỗi rerun)
- Widget key phải unique: thêm suffix tab/pgd/index
```

---

## Checklist trước khi gửi prompt

```
□ Đã xác định đúng file và số dòng cần sửa (dùng SCHEMA.md hoặc grep)
□ Đã kiểm tra BUGMAP.md xem lỗi này đã có pattern fix chưa
□ Đã paste đúng đoạn code liên quan (không paste cả file)
□ Đã ghi rõ "không sửa gì" (prevent over-engineering)
□ Đã chỉ rõ key kv_store nếu có lưu dữ liệu
□ Đã chỉ rõ action audit log
□ Đã nhắc cache clear nếu sau upload/lưu
□ Đã dùng COT_* từ config thay vì hardcode tên cột
```

---

## Ví dụ thực tế đã dùng

### Ví dụ 1 — Fix dtype parquet (bug 2026-05-20)

```
Bugfix: ArrowInvalid khi ghi parquet — cột "Mã xã" có mixed type (int + str rỗng)

Traceback gốc:
  File "services/upload_service.py", line 498, in merge_du_lieu_toan_cn
    df_toan_cn.to_parquet(cache_path, ...)
pyarrow.lib.ArrowInvalid: Could not convert '' with type str: tried to convert to int64
  Conversion failed for column Mã xã with type object

File cần sửa:
- services/upload_service.py dòng 484-500: vòng lặp _str_cols cleanup

Yêu cầu:
- Chỉ sửa lambda trong vòng lặp _str_cols
- Thêm nhánh: float nguyên (10001.0) → str(int(v)) = "10001"
- Giữ nguyên _BAD_VALS, _cols_so_cn, rollback .bak

Không làm:
- Không thay đổi logic đọc file hay concat
- Không sửa cột tiền tệ trong _cols_so_cn
```

### Ví dụ 2 — Thêm filter chương trình tín dụng

```
Thêm bộ lọc "Chương trình tín dụng" vào tab_tracuu.py, load động từ ct_registry.

File cần sửa:
- tabs/tab_tracuu.py dòng ~[N sau filter PGD]: thêm selectbox

Yêu cầu:
- Load danh sách từ db.doc_kv(f"ct_registry_{pgd_slug}")
- Mặc định "Tất cả"
- Lọc df theo cột COT_TEN_CT nếu có chọn
- Giữ nguyên filter PGD/Xã hiện tại

Tái sử dụng:
- config.DS_PGD, config.COT_TEN_CT
- data.pgd.pgd_slug() để tính slug từ tên PGD
```
