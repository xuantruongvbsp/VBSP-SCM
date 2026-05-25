# Tổng hợp thay đổi - Tab Xử lý Rủi ro (XLRR)

**Ngày:** 25/05/2026  
**Người thực hiện:** Windsurf Cascade  
**Mục đích:** Cải tạo tab XLRR theo yêu cầu PGD/CN workflow

---

## 📊 Tổng quan thay đổi

### Trước: 5 sub-tabs
1. Lập hồ sơ PGD
2. **Lập hồ sơ CN** (QĐ62 trực tiếp) ← **XÓA**
3. Theo dõi QĐ62
4. Tổng hợp CN
5. Báo cáo

### Sau: 4 sub-tabs
1. 🏢 **Lập hồ sơ PGD** (cải tiến)
2. 📊 **Theo dõi QĐ62**
3. 📈 **Tổng hợp CN** (thêm nhập Excel)
4. 📄 **Xuất biểu mẫu** (thêm xuất Excel)

---

## 📝 Chi tiết thay đổi theo file

### 1. `services/xlrr_service.py`

**Thêm 15 fields mới vào `HoSoRuiRo`:**

```python
# Thông tin mẫu 01/XLN — Đơn đề nghị
ngay_ky_01: Optional[date] = None
ma_to: str = ""
ten_to_truong: str = ""
so_tien_thiet_hai_01: str = ""
muc_do_thiet_hai_01: str = ""
kha_nang_tra_no_01: str = ""
ke_hoach_tra_no_01: str = ""

# Thông tin mẫu 02/XLN — Biên bản
ngay_lap_02: Optional[date] = None
dia_diem_02: str = ""
ten_pgd_02: str = ""  # Phó GĐ NHCSXH
ten_ubnd_02: str = ""
ten_hoi_nd_02: str = ""
ten_cbtd_02: str = ""
ten_to_truong_02: str = ""
chi_tiet_thiet_hai_02: str = ""
danh_gia_thiet_hai_02: str = ""
danh_gia_du_an_02: str = ""
tai_san_hien_tai_02: str = ""
kha_nang_tra_no_02: str = ""
```

**Cập nhật `to_dict()`:** Thêm `ngay_ky_01` và `ngay_lap_02` vào danh sách convert date.

---

### 2. `services/xlrr_export_service.py` ⭐ FILE MỚI

**Chức năng:** Export/nhập Excel cho luồng PGD → CN

**API chính:**
```python
def xuat_danh_sach_rui_ro_excel(ds_hs, ten_pgd, nam, thang) -> bytes
# Xuất danh sách rủi ro của PGD sang Excel

def nhap_danh_sach_rui_ro_excel(file_bytes) -> list[HoSoRuiRo]
# Đọc file Excel từ PGD

def merge_du_lieu_pgd_vao_cn(ds_hs_pgd, nam, thang, nguoi_nhap) -> tuple[int, list[str]]
# Merge dữ liệu PGD vào database CN

def tong_hop_theo_bien_phap(ds_hs, bien_phap) -> list[HoSoRuiRo]
# Lọc hồ sơ theo biện pháp (cho mẫu 04/05)
```

**Cấu trúc file Excel:**
- Sheet 1: Dữ liệu hồ sơ (22 cột)
- Sheet 2: Metadata (tên PGD, ngày xuất, số lượng...)

---

### 3. `tabs/tab_xu_ly_rui_ro.py` ⭐ REFACTOR LỚN

#### a) Import (dòng 16-36)
- **Thêm:** `DON_VI_CHI_NHANH` để có đủ 22 đơn vị

#### b) `_subtab_lap_hs_pgd()` - Thêm chức năng

**Dropdown đơn vị (dòng 84-89):**
```python
ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD  # 22 đơn vị đầy đủ
ten_pgd = st.selectbox("📍 Chọn đơn vị để lập hồ sơ", ds_don_vi)
```

**Thêm expander nhập thông tin mẫu:**

```python
# Expander: Thông tin mẫu 01/XLN (dòng 217-231)
with st.expander("📝 Thông tin mẫu 01/XLN — Đơn đề nghị (tùy chọn)"):
    ngay_ky_01 = st.date_input("Ngày ký đơn:", ...)
    ma_to = st.text_input("Mã Tổ TK&VV:", ...)
    ten_to_truong = st.text_input("Tổ trưởng:", ...)
    # ... các field khác

# Expander: Thông tin mẫu 02/XLN (dòng 233-253)
with st.expander("📋 Thông tin mẫu 02/XLN — Biên bản (tùy chọn)"):
    ngay_lap_02 = st.date_input("Ngày lập biên bản:", ...)
    ten_pgd_02 = st.text_input("Phó GĐ NHCSXH:", ...)
    # ... các field khác
```

**Dư nợ - Lãi tồn nhập tay (dòng 201-215):**
```python
# Dư nợ gốc: readonly từ HSTD
du_no_goc_display = st.text_input("Dư nợ gốc (từ HSTD)", disabled=True)

# Dư nợ lãi: nhập tay để khớp số liệu kế toán
du_no_lai_input = st.number_input("Dư nợ lãi (nhập tay để khớp số liệu kế toán)", ...)
```

**Lưu hồ sơ với data đầy đủ (dòng 287-333):**
- Dùng `du_no_lai_input * 1_000_000` cho lãi tồn
- Truyền đầy đủ 15 fields mới vào `HoSoRuiRo`

#### c) **XÓA** `_subtab_lap_hs_cn()` (dòng 349-457 cũ)
- Xóa toàn bộ function "Lập QĐ62 trực tiếp"
- Lý do: Logic sai (không thể lập hồ sơ không có trong HSTD)

#### d) `_subtab_tong_hop_cn()` - Thêm nhập Excel

**Section nhập dữ liệu PGD (dòng 473-524):**
```python
st.markdown("#### 📥 Nhập dữ liệu từ PGD")
uploaded_files = st.file_uploader(
    "Chọn file Excel từ các PGD (có thể chọn nhiều file)",
    type=['xlsx'],
    accept_multiple_files=True,
)

if uploaded_files:
    # Preview data
    # Merge button
    if st.button("💾 Merge vào CN"):
        merge_du_lieu_pgd_vao_cn(ds_all, nam, thang, username)
```

**Thêm xuất mẫu 04/05 (dòng 554-576):**
```python
st.markdown("#### 📄 Xuất mẫu tổng hợp 04/XLN và 05/XLN")
ds_khoanh = tong_hop_theo_bien_phap(ds_cn, "khoanh")
ds_xoa = tong_hop_theo_bien_phap(ds_cn, "xoa")
# Placeholder buttons
```

#### e) `_subtab_bao_cao()` - Rút gọn + xuất Excel

**Xuất Excel cho PGD (dòng 547-569):**
```python
if la_phan_he_pgd(role):
    if st.button("📥 Xuất Excel"):
        excel_bytes = xuat_danh_sach_rui_ro_excel(ds_hs, pgd_user, nam, thang)
        st.download_button("⬇️ Tải file Excel", ...)
```

**Xuất Word đơn giản (dòng 605-701):**
- Dùng data đã lưu trong `HoSoRuiRo` (không nhập lại)
- Format biện pháp: `"Khoanh Nợ"` / `"Xóa Nợ"` (bỏ "(QĐ62)")
- Kiểm tra trạng thái: cảnh báo nếu chưa nhập đủ 01/02

#### f) `render()` - Đổi 5 tabs → 4 tabs (dòng 707-756)

```python
# CN: 4 tabs
tab_labels = [
    "🏢 Lập hồ sơ PGD",
    "📊 Theo dõi QĐ62",
    "📈 Tổng hợp CN",
    "📄 Xuất biểu mẫu",
]

# PGD: 2 tabs
tab_labels = [
    "🏢 Lập hồ sơ PGD",
    "📄 Xuất biểu mẫu",
]
```

---

## 🔄 Luồng dữ liệu mới

```
┌─────────────────────────────────────────────────────────────┐
│  PGD                                                        │
│  ─────────────────────────────────────────────────────────  │
│  1. Lập hồ sơ PGD                                           │
│     - Chọn hộ vay từ HSTD                                   │
│     - Nhập thông tin rủi ro                                 │
│     - Nhập thông tin mẫu 01/XLN (expander)                  │
│     - Nhập thông tin mẫu 02/XLN (expander)                  │
│     - Nhập dư nợ lãi tay (khớp kế toán)                     │
│     - Lưu hồ sơ                                             │
│                                                             │
│  2. Xuất biểu mẫu                                           │
│     - Nút "📥 Xuất Excel" → file .xlsx                      │
│     - Gửi file cho CN                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  CN                                                         │
│  ─────────────────────────────────────────────────────────  │
│  3. Tổng hợp CN                                             │
│     - Upload file Excel từ nhiều PGD                        │
│     - Preview dữ liệu                                       │
│     - Nút "💾 Merge vào CN"                                 │
│                                                             │
│  4. Xuất mẫu tổng hợp 04/05                                 │
│     - Tổng hợp theo biện pháp (Khoanh/Xóa)                  │
│     - Xuất mẫu (placeholder)                                │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ Kiểm tra compile

```bash
✅ xlrr_service.py - OK
✅ xlrr_export_service.py - OK
✅ tab_xu_ly_rui_ro.py - OK
```

---

## ⚠️ Lưu ý cho Claude Sonnet review

### Cần review kỹ:
1. **Logic xóa `Lập hồ sơ CN`** - Có đúng là không cần thiết?
2. **Lãi tồn nhập tay** - Có đúng format (triệu đồng × 1_000_000)?
3. **Export/Import Excel** - Có đủ fields? Có lỗi encoding?
4. **Merge dữ liệu** - Có xử lý trùng ID đúng?

### Chưa làm (placeholder):
- `_tao_word_04xln_v2()` - Mẫu tổng hợp Khoanh nợ
- `_tao_word_05xln_v2()` - Mẫu tổng hợp Xóa nợ

---

## 📎 File liên quan

| File | Mô tả |
|------|-------|
| `services/xlrr_service.py` | Data model HoSoRuiRo |
| `services/xlrr_export_service.py` | Export/import Excel |
| `services/word_xln_service.py` | Template Word 01/02/04/05 |
| `tabs/tab_xu_ly_rui_ro.py` | UI chính 4 sub-tabs |
| `config.py` | DS_PGD, DON_VI_CHI_NHANH |
