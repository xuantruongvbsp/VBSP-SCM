# TROUBLESHOOTING — VBSP-SCM
> Cập nhật lần cuối: 05/2026

---

## 1. Dữ liệu hiển thị sai / Metric sai

### Tổng KH/TH hiện sai (ví dụ: 0,013 thay vì 13,199 tỷ)
**Nguyên nhân:** Chia `/1e9` thay vì `/1e12`
```python
# SAI
tong_kh / 1e9

# ĐÚNG
tong_kh / 1e12   # th_cn/kh_cn lưu VND → /1e12 = tỷ
```

### TH = 0 toàn bộ
**Kiểm tra theo thứ tự:**
1. File HSTD đã được upload chưa? → Tab Upload KH-NV
2. File có cột `Tổng dư nợ` không? → Xem `COT_TONG_DU_NO` trong config
3. Merge đã chạy chưa? → Kiểm tra `merge_meta_hstd` trong kv_store
4. Cache cũ? → `st.cache_data.clear()`

### Số liệu xã bị lệch / không khớp
**Nguyên nhân:** Tên xã trong HSTD khác với `PGD_XA_MAP` trong config
```python
# Kiểm tra
from config import PGD_XA_MAP
print(PGD_XA_MAP["PGD Long Thành"])
# So sánh với cột "Tên xã" trong file HSTD
```

### th_cn bị lệch ~8 tỷ
**Nguyên nhân:** Thiếu key ĐP trong `CHUONG_TRINH_KHTD`
→ Kiểm tra 4 key: `9_DP`, `12_DP`, `17_DP`, `26_DP` đã có trong config chưa

---

## 2. Upload File

### Upload thành công nhưng dữ liệu không cập nhật
```python
# Bắt buộc sau khi lưu file
st.cache_data.clear()
# Và gọi merge nếu là file hệ thống
merge_du_lieu_toan_cn("hstd")
```

### Merge báo lỗi một PGD
**Nguyên nhân:** File PGD bị lỗi format hoặc thiếu cột bắt buộc
→ Kiểm tra log audit: `SELECT * FROM audit_log WHERE action LIKE '%merge%' ORDER BY created_at DESC LIMIT 10`
→ Upload lại file PGD đó

### File upload xong nhưng mất sau khi restart
**Nguyên nhân:** Lưu vào `/tmp` hoặc RAM thay vì disk
→ Kiểm tra `UPLOAD_DIR` trong config — phải trỏ đến thư mục persistent

---

## 3. Kế hoạch Tín dụng

### KH nhập xong nhưng không lưu
**Kiểm tra:**
1. Có nhấn nút `💾 Lưu kế hoạch` không?
2. Role có phải `admin` hoặc `manager` không?
3. Xem audit log: `SELECT * FROM audit_log WHERE action = 'luu_khtd_cn' ORDER BY created_at DESC LIMIT 5`

### Form nhập hiện số thập phân
→ `format="%.1f"` → sửa thành `format="%.0f"` trong `number_input`

### Cột TH Xã hiển thị 0 dù có dữ liệu
**Nguyên nhân:** `df_full` chưa được truyền vào `_tab_khtd_xa()`
→ Kiểm tra signature hàm và chỗ gọi trong `render()`

---

## 4. GSheet / Google Sheets

### Push dữ liệu lên GSheet thất bại
**Kiểm tra theo thứ tự:**
1. `credentials.json` có tồn tại trong root không?
2. Service account có quyền Editor trên sheet không?
3. `DCGIAM_SHEET_ID` đúng không? (`15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk`)
4. Quota Google Sheets API chưa bị vượt?

---

## 5. PDF Xuất

### PDF thiếu logo
→ Kiểm tra file `assets/logo.png` có tồn tại không
→ `pdf_service.py` sẽ fallback về text nếu không có logo

### Chữ trong PDF bị lỗi font (tofu □□□)
**Nguyên nhân:** Thiếu file font Times New Roman
→ Đặt `assets/times.ttf` và `assets/timesbd.ttf` vào thư mục `assets/`
→ Hoặc chạy trên Windows — tự tìm `C:/Windows/Fonts/times.ttf`

### PDF font size quá nhỏ
→ Sửa logic trong `pdf_service.py`:
```python
if n_cols <= 6:   font_size = 11
elif n_cols <= 10: font_size = 10
elif n_cols <= 14: font_size = 9
else:              font_size = 8
header_font_size = font_size + 2
```

---

## 6. Streamlit / UI

### CSS inject không có hiệu lực
1. Hard refresh: `Ctrl+Shift+R`
2. Restart Streamlit: `Ctrl+C` → `streamlit run app.py`
3. Kiểm tra selector — Streamlit hay đổi `data-testid` theo version

### Sidebar không có màu navy
→ CSS global chưa được inject hoặc bị override
→ Kiểm tra block `# ── Global CSS ──` trong `app.py`

### `st.columns` với 12 cột bị co hẹp, chữ nhỏ
→ Đây là giới hạn của Streamlit — dùng HTML table thuần thay thế cho phần hiển thị, giữ `st.columns` chỉ cho phần nhập liệu

---

## 7. Database / kv_store

### Lỗi "database is locked"
**Nguyên nhân:** Nhiều process Streamlit cùng ghi SQLite
→ Chỉ chạy 1 instance Streamlit
→ Hoặc tăng timeout: `PRAGMA busy_timeout = 5000`

### Key kv_store không tìm thấy
```python
# Debug
import db
val = db.doc_kv("khtd_cn")
print(val)  # None nếu chưa có

# Xem tất cả keys
with db.get_conn() as conn:
    rows = conn.execute("SELECT key, updated_at FROM kv_store").fetchall()
    print(rows)
```

---

## 9. docx2pdf / Xuất PDF

### Lỗi "No module named docx2pdf"
**Nguyên nhân:** Chưa cài package `docx2pdf`
```bash
pip install docx2pdf
```

### Lỗi "docx2pdf failed" / "Word not found"
**Nguyên nhân:** `docx2pdf` yêu cầu Microsoft Word trên Windows
- **Có Word:** Kiểm tra Word có bị lỗi không, mở được file .docx không
- **Không Word:** Mở file Word đã tạo → **File → Save As → PDF** thủ công
- **Linux/Mac:** `docx2pdf` không hỗ trợ — dùng `libreoffice --headless --convert-to pdf`

### PDF xuất ra thiếu font / lỗi hiển thị
**Nguyên nhân:** Font Times New Roman không khả dụng trong Word
→ Cài font Times New Roman trên máy tính trước khi convert

### Nút PDF không hiện download button
**Nguyên nhân:** Cần bấm **📄 Xuất PDF** trước — button download chỉ hiện sau khi convert thành công
→ Kiểm tra: đã bấm "Xuất Word" để tạo dữ liệu chưa? Nút PDF cần dữ liệu từ session_state

---

## 10. Lệnh debug hữu ích

```bash
# Xem 20 audit log gần nhất
sqlite3 data.db "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 20"

# Xem tất cả key trong kv_store
sqlite3 data.db "SELECT key, length(value), updated_by, updated_at FROM kv_store"

# Kiểm tra merge meta
sqlite3 data.db "SELECT key, value FROM kv_store WHERE key LIKE 'merge_meta%'"

# Chạy với DEBUG mode
DEBUG=1 streamlit run app.py
```
