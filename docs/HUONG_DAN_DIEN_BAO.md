# 📡 Hướng dẫn sử dụng Điện báo — Phân hệ Phòng KH-NV

> VBSP-SCM · Workspace **Phòng KH-NV** (`ws_management`) · Cập nhật: 05/2026

### 📌 Tóm tắt nhanh (đọc ngay trong tab Điện báo)

1. **Điện báo là gì?** — File Excel tổng hợp số liệu tín dụng / cân đối nguồn vốn **cấp Chi nhánh**.
2. **Tải mẫu ở đâu?** — **Báo cáo nhanh → Báo cáo theo công thức → Điện báo ngày → Chọn tick tất cả** (theo menu nội bộ VBSP).
3. **Hai cột chính trong mỗi file** — **Cột B** = tên chỉ tiêu (text), **Cột C** = giá trị số. Bạn upload **hai file riêng**: một cho **hiện tại**, một cho **31/12 năm trước**; hai file phải **cùng cấu trúc** (xem mục 7 bên dưới).
4. **Cách upload** — Tải mẫu, điền số liệu → mở tab **📡 Điện Báo** → kéo xuống **Upload file Điện báo** → chọn từng file trong hai ô upload (chọn xong là hệ thống xử lý).
5. **Lưu ý** — Đơn vị số **khớp mẫu** (thường VND trên biểu mẫu; nếu mẫu theo triệu thì thống nhất nội bộ); bản upload mới **ghi đè** bản cùng loại trên server; chỉ **admin** / **manager** được upload.

---

## 1. Mở đầu

### Chức năng Điện báo là gì?

**Điện báo** là file Excel tổng hợp số liệu tín dụng / cân đối nguồn vốn **cấp Chi nhánh**, dùng làm nguồn số liệu cho tab **📡 Điện Báo** (Cân đối Nguồn vốn & Sử dụng vốn), đối chiếu với **Kế hoạch vs Thực hiện** và các báo cáo liên quan — bổ trợ cho chuỗi dữ liệu HSTD / NQ11 / GQVL đã merge từ **22 đơn vị** (Hội sở + **21 PGD** trong `config.DS_PGD`).

### Ai được thao tác?

| Vai trò | Upload / cập nhật Điện báo |
|--------|----------------------------|
| **admin** | Có |
| **manager** | Có |
| **user** / **executive** | Không (executive chỉ đọc theo RBAC workspace) |

### Mục đích

- Nhập nhanh các chỉ tiêu tổng hợp trên biểu mẫu Điện báo (thay vì cộng tay từng PGD trên màn hình).
- So sánh **31/12 năm trước** và **số liệu hiện tại** trong cùng một tab.

---

## 2. 📥 Đường dẫn tải dữ liệu mẫu

**Theo quy trình nội bộ Chi nhánh:**

**Báo cáo nhanh → Báo cáo theo công thức → Điện báo ngày → Chọn tick tất cả**

> Nếu menu cụ thể thay đổi theo từng đợt cập nhật Core banking / VBSP, hãy lấy đúng mẫu **Điện báo** mà Phòng KH-NV đang ban hành.

### File mẫu tham khảo trong tài liệu dự án

- `DienBao_2025_3112.xlsx`
- `Dienbao_2026.xlsx`

*(Đặt bản sao trong kho mẫu nội bộ hoặc thư mục template của đơn vị — có thể không kèm trong repository.)*

### Cấu trúc file (khớp hàm đọc `doc_dienbao`)

Hệ thống đọc file Excel **theo từng dòng**, không dùng header chuẩn pandas:

| Vùng | Mô tả |
|------|--------|
| **Cột chỉ tiêu** | Cột **B** (cột thứ 2): tên chỉ tiêu dạng text |
| **Cột giá trị** | Cột **C** (cột thứ 3): số (float) |
| **Dòng bỏ qua** | Dòng trống, tiêu đề kiểu `Chỉ tiêu`, `Điện báo ngày` (chỉ để ghi chú trên mẫu) |
| **NQH con** | Dòng chỉ tiêu bắt đầu bằng `Trđ:` được gắn làm dòng con NQH của chỉ tiêu cha ngay phía trên |

Các chỉ tiêu mà tab **Cân đối** tra cứu gồm (ví dụ): `Tổng dư nợ`, `Nguồn vốn cân đối từ TW (KHA)`, `Tổng huy động vốn`, `Nguồn vốn nhận UTĐT tại ĐP`, `Dư nợ Quá hạn KHA`, `Dư nợ Quá hạn KHB`, `Dư nợ Kế hoạch A`, `Dư nợ Kế hoạch B`, … — **tên trên file phải khớp hoặc gần khớp** chuỗi mà hệ thống tìm (xem `db_lookup` trong mã nguồn).

### Format ngày tháng & số liệu

- **Ngày trên mẫu**: thường là dòng mô tả (`Điện báo ngày`); nên dùng **dd/mm/yyyy** thống nhất trên mẫu nội bộ để tránh nhầm lẫn khi đối chiếu.
- **Giá trị số**: hệ thống đọc **trực tiếp** số trong ô (float). **Phải trùng đơn vị với file mẫu** (thường là **đồng VND** đầy đủ trên biểu mẫu tín dụng). Tab Điện báo **không** tự nhân `triệu × 1.000.000` như một số form nhập kế hoạch khác — nếu mẫu của đơn vị quy ước theo triệu, cần thống nhất nội bộ hoặc quy đổi trước khi lưu file.

---

## 3. 📤 Quy trình upload (thực tế giao diện)

1. **Bước 1**: Tải file mẫu theo mục 2, điền đủ chỉ tiêu — đối chiếu tên dòng với mẫu đang chạy tốt trên hệ thống.
2. **Bước 2**: Đăng nhập với tài khoản **admin** hoặc **manager**, vào workspace **📋 Phòng KH-NV**.
3. **Bước 3**: Mở tab **📡 Điện Báo** (Cân đối Nguồn vốn & Sử dụng vốn).
4. **Bước 4**: Kéo đến mục **📤 Upload file Điện báo**:
   - **File Điện báo hiện tại** (năm báo cáo hiện tại trên màn hình),
   - **File Điện báo 31/12 năm trước** (để so sánh và biểu đồ — tùy nhu cầu).
5. **Bước 5**: Chọn file `.xlsx` / `.xls` tương ứng — upload xong hệ thống gọi `upload_service.luu_dienbao()` và hiển thị thông báo kết quả (`KetQuaUpload.hien_thi()`).
6. **Bước 6**: Kiểm tra thông báo ✅ / ⚠️; nếu thành công, `st.cache_data.clear()` được gọi để làm mới dữ liệu hiển thị; đồng thời có ghi **audit** (`upload_dienbao`).

> **Lưu ý:** Tab **📤 Upload KH-NV** dùng cho HSTD / NQ11 / GQVL / CDTOTKVV theo từng đơn vị — **không** chứa form upload Điện báo. Điện báo chỉ upload tại tab **📡 Điện Báo** như trên.

---

## 4. 📊 Xem & tra cứu

- **Tab 📡 Điện Báo**: xem bảng cân đối, metric tổng quan, biểu đồ (khi đã có đủ file hiện tại / 31/12).
- **Tab 📈 Báo cáo chi tiết** / **🔍 Kiểm soát CN**: các báo cáo HSTD/NQ11 — **không** thay thế nguồn Điện báo; Điện báo phục vụ nhánh cân đối & kế hoạch.
- **Tab 📊 KH vs Thực hiện** (`tab_kehoach`): so sánh kế hoạch với số liệu **Điện báo hiện tại** đã upload (đọc từ cache file Điện báo).

**Xuất Excel:** trong tab **📡 Điện Báo** có nút xuất so sánh cân đối (khi đã có dữ liệu). Xuất PDF tùy từng báo cáo — nếu có nút tương ứng trên màn hình.

---

## 5. ⚠️ Lưu ý quan trọng

| Nội dung | Chi tiết |
|----------|-----------|
| **Lưu file trên server** | Mỗi loại chỉ giữ **một bản mới nhất**: `dienbao_ht.xlsx` (hiện tại) và `dienbao_prev.xlsx` (31/12 năm trước) trong thư mục cache — **upload mới ghi đè** file cùng loại. |
| **Đơn vị số trong Excel** | Đọc nguyên giá trị ô — **khớp mẫu**; không có bước tự động “triệu → VND” riêng cho luồng Điện báo. |
| **Merge HSTD/NQ11/GQVL** | Upload Điện báo **không** gọi `merge_du_lieu_toan_cn()`. Merge 22 đơn vị chỉ diễn ra khi upload **HSTD / NQ11 / GQVL** ở tab **📤 Upload KH-NV** (hoặc import hàng loạt). |
| **Audit** | Mỗi lần lưu thành công ghi `db.ghi_audit(..., "upload_dienbao", ...)`. Nên tra audit khi cần đối soát ai upload, thời điểm nào. |

---

## 6. 🔧 Xử lý lỗi thường gặp

| Hiện tượng | Nguyên nhân gợi ý | Cách xử lý |
|-------------|-------------------|------------|
| Lỗi format / không đọc được chỉ tiêu | Sai vị trí cột B/C hoặc tên chỉ tiêu lệch mẫu | Đối chiếu lại với file mẫu; đảm bảo cột **B** = tên, **C** = số |
| Số liệu hiển thị sai tỷ / triệu | Nhập sai thứ bậc đơn vị (đồng vs triệu) | Kiểm tra lại ô trên mẫu chuẩn; thử một chỉ tiêu đã biết giá trị chuẩn |
| Ngày trên mẫu gây hiểu nhầm | Format ngày không thống nhất | Thống nhất **dd/mm/yyyy** trên dòng mô tả |
| Tab KH vs TH báo thiếu Điện báo | Chưa upload **Điện báo hiện tại** | Vào tab **📡 Điện Báo**, upload file hiện tại |
| Tên PGD / 21 PGD | File Điện báo **theo mẫu dọc chỉ tiêu** không thay thế danh sách PGD trong `DS_PGD` | Danh sách **21 PGD** + Hội sở dùng cho upload HSTD/NQ11/GQVL; tra `config.DS_PGD` khi làm việc với file theo **từng PGD** |

---

## 7. Cấu trúc file Điện báo (hai bản: hiện tại & 31/12 năm trước)

Hệ thống nhận **hai file Excel riêng** (upload tại tab **📡 Điện Báo**). Trong **mỗi** file, bố cục đọc dữ liệu giống nhau (xem mục 2 — `doc_dienbao`):

| Vai trò trong từng file | Cột trên Excel | Ý nghĩa nghiệp vụ |
|-------------------------|----------------|-------------------|
| Tên chỉ tiêu (text) | **Cột B** (cột thứ 2) | Dòng mô tả chỉ tiêu cần tra cứu |
| Giá trị số (float) | **Cột C** (cột thứ 3) | **File Điện báo hiện tại:** số liệu tại thời điểm upload — nguồn vốn / sử dụng vốn mới nhất. **File 31/12 năm trước:** số liệu cuối năm trước làm **mốc so sánh**; tab Cân đối dùng để tính chênh lệch tăng/giảm so với đầu năm / so với hiện tại. |

### Lưu ý bắt buộc

- Hai file phải **cùng cấu trúc** (cùng thứ tự / tên chỉ tiêu ở cột B, cùng quy ước ô số ở cột C) để so sánh và biểu đồ không lệch.
- **Tên file nên có ngày đúng dạng `YYYYMMDD`** (ví dụ mốc 31/12/2025: `DienBao_2025_3112.xlsx`) để quản lý phiên bản và đối soát nội bộ — hệ thống vẫn chấp nhận `.xlsx` / `.xls` hợp lệ khi upload.
- **Đơn vị số trong ô (cột C):** phải **khớp mẫu** đơn vị đang dùng (thường là **VND** đầy đủ trên biểu mẫu; nếu mẫu nội bộ quy ước theo triệu thì cả hai file phải thống nhất cùng một quy ước trước khi upload).

### Ví dụ minh họa (hai cột số liệu sau khi đối chiếu trên màn hình — không nhất thiết là hai cột C trên một sheet)

| Chỉ tiêu | 31/12 năm trước (file mốc) | Hiện tại (file mới nhất) | Chênh lệch (minh họa) |
|----------|----------------------------|--------------------------|------------------------|
| Tổng nguồn vốn (minh họa) | 120.000 | 150.000 | +30.000 |
| Dư nợ (minh họa) | 115.000 | 145.000 | +30.000 |

*(Giá trị minh họa; đơn vị hiển thị trên tab theo `fmt_ty` / quy ước hệ thống.)*

---

## 8. ✅ Checklist nhanh trước khi upload

- [ ] Đã tải đúng mẫu **Điện báo ngày** / mẫu năm theo hướng dẫn nội bộ  
- [ ] Cột **B/C** đúng cấu trúc, tên chỉ tiêu khớp mẫu chạy tốt  
- [ ] Đã chọn đúng file **hiện tại** vs **31/12 năm trước**  
- [ ] Sau upload: kiểm tra thông báo và (nếu cần) **audit log**  

---

*Tài liệu kỹ thuật tham chiếu thêm: `HUONG_DAN_NGUON_DU_LIEU.md` (mục Điện báo), `services/upload_service.py` (`luu_dienbao`), `data/hstd.py` (`doc_dienbao`).*
