# 📍 Hướng dẫn sử dụng Điểm Giao Dịch (dgd_map)

> VBSP-SCM · Workspace **Phòng KH-NV** (`ws_management`) & **Hỗ trợ địa bàn** (`ws_operation`) · Cập nhật: 05/2026

### 📌 Tóm tắt nhanh

1. **Điểm Giao Dịch là gì?** — Cấu hình ánh xạ **PGD → Xã → Điểm GD → Thôn/Ấp** dùng để phân loại hồ sơ HSTD theo địa bàn.
2. **Ai được dùng?** — **admin / manager**: quản lý toàn chi nhánh (Phòng KH-NV). **user (CBTD)**: chỉ PGD của mình (Hỗ trợ địa bàn).
3. **Ba cách nhập liệu** — Import Excel hàng loạt · Thêm thủ công từng ĐGD · Xem & Sửa trực tiếp.
4. **Quan trọng** — Khi Import, **chọn đúng PGD** trước khi upload file. File của PGD nào phải upload đúng PGD đó — nếu chọn nhầm, dữ liệu sẽ ghi sai nhánh.

---

## 1. Phân quyền

| Vai trò | Phòng KH-NV (toàn CN) | Hỗ trợ địa bàn (chỉ PGD mình) |
|---------|----------------------|-------------------------------|
| **admin** | Toàn quyền | — |
| **manager** | Import, Xem & Sửa, Tổng quan | — |
| **user (CBTD)** | Chỉ xem Tổng quan | Import, Xem & Sửa, Tổng quan |
| **executive** | Chỉ xem Tổng quan | — |

---

## 2. Ba tiểu tab

### 📥 Import từ file

Nhập dữ liệu hàng loạt từ file Excel. Phù hợp khi cần cấu hình nhiều xã / nhiều ĐGD cùng lúc.

### 🗺️ Xem & Sửa

Sửa từng ĐGD trực tiếp trên giao diện: đổi tên, thêm/bớt thôn, xóa ĐGD.

### 📋 Tổng quan

Xem thống kê số xã, số ĐGD, số ấp/KP và trạng thái cấu hình của từng PGD.

---

## 3. Import từ file — Hướng dẫn chi tiết

### Bước 1: Chuẩn bị file Excel

1. Bấm **📤 Tải file mẫu Excel** — hệ thống tạo file mẫu đúng định dạng cho PGD đang chọn.
2. Mở file, điền dữ liệu theo 4 cột:

| Cột A | Cột B | Cột C | Cột D |
|-------|-------|-------|-------|
| STT | Xã/Phường | Tên Điểm GD | Thôn/Ấp (phân cách bằng dấu phẩy) |
| 1 | An Phước | Điểm GD 1 | Ấp 1 An Phước, Ấp 2 An Phước |
| 2 | An Phước | Điểm GD 2 | Ấp 3 An Phước, Ấp Bàu Cá |

> **Lưu ý:** Nhiều dòng cùng tên Xã + tên ĐGD sẽ được gộp thôn lại. Tên xã phải khớp với danh mục xã trong hệ thống.

### Bước 2: Chọn đúng PGD

⚠️ **Đây là bước dễ nhầm nhất.**

- Selectbox **"Chọn PGD"** quyết định dữ liệu sẽ được lưu vào nhánh nào.
- **File của PGD nào → chọn đúng PGD đó.**
- Nếu chọn nhầm: dữ liệu Long Thành sẽ ghi vào Hội sở, Long Thành vẫn trống — không có cảnh báo nào từ hệ thống.

### Bước 3: Upload và kiểm tra Preview

1. Kéo file vào ô upload hoặc bấm chọn file.
2. Hệ thống hiển thị **Preview** — kiểm tra:
   - Số xã, số ĐGD, số ấp có đúng không?
   - Tên xã có khớp với PGD đã chọn không?
3. Nếu thấy xã lạ (không thuộc PGD) → dừng lại, kiểm tra lại file và PGD đã chọn.

### Bước 4: Merge hay Thay thế?

| Nút | Tác động | Khi nào dùng |
|-----|----------|--------------|
| **Merge vào dgd_map hiện tại** | Chỉ ghi đè nhánh PGD vừa chọn, các PGD khác giữ nguyên | ✅ Hầu hết trường hợp |
| **Thay thế toàn bộ dgd_map** | Xóa sạch toàn bộ tất cả PGD, chỉ còn PGD vừa chọn | ⚠️ Chỉ dùng khi reset hoàn toàn từ đầu |

> **KHÔNG bấm "Thay thế toàn bộ"** trừ khi bạn chắc chắn muốn xóa dữ liệu tất cả PGD còn lại. Thao tác này không thể hoàn tác tự động.

---

## 4. Thêm ĐGD thủ công (trong tab Import)

Dùng khi chỉ cần thêm 1–2 ĐGD mà không muốn tạo file Excel.

1. Chọn **Xã/Phường** từ danh sách.
2. Nhập **Tên Điểm giao dịch**.
3. Chọn **Thôn/Ấp** từ danh sách (lấy từ dữ liệu HSTD của PGD).
4. Bấm **➕ Thêm Điểm giao dịch**.

> Thôn/ấp đã gán cho ĐGD khác trong cùng xã sẽ bị ẩn khỏi danh sách chọn — tránh gán trùng.

---

## 5. Xem & Sửa

1. Chọn **PGD** và **Xã/Phường**.
2. Mỗi ĐGD hiển thị trong một khối thu gọn (expander).
3. Trong expander:
   - **Đổi tên ĐGD**: nhập tên mới → bấm 💾 Lưu thay đổi.
   - **Thêm/bớt thôn**: chỉnh multiselect → bấm 💾 Lưu thay đổi.
   - **Xóa ĐGD**: bấm 🗑️ Xóa ĐGD.
4. Thêm ĐGD mới: kéo xuống cuối → nhập tên → chọn thôn → bấm 💾 Lưu ĐGD mới.

> **Lưu ý:** Không thể đổi tên hoặc xóa ĐGD đang có hồ sơ trong HSTD. Cần cập nhật HSTD trước.

---

## 6. Khắc phục sự cố

### Lỡ Merge nhầm PGD

1. Tạo file Excel đúng cho PGD bị ghi sai (hoặc file rỗng nếu muốn xóa).
2. Chọn đúng PGD bị sai → Upload → bấm **Merge** để ghi đè lại.
3. Upload lại file đúng cho PGD bị thiếu.

### Thôn/ấp không hiện trong danh sách chọn

- Danh sách thôn lấy từ file HSTD của PGD. Nếu PGD chưa upload HSTD → danh sách rỗng.
- Giải pháp: Upload HSTD cho PGD đó trước, rồi quay lại cấu hình ĐGD.

### ĐGD không xóa được

- Hệ thống chặn xóa ĐGD đang có hồ sơ trong HSTD để tránh mất liên kết dữ liệu.
- Cần yêu cầu admin cập nhật cột "Tên điểm GD" trong HSTD trước.

---

## 7. Hỗ trợ địa bàn (CBTD — role=user)

CBTD chỉ thấy và chỉnh sửa dữ liệu **PGD của mình**. Giao diện tương tự Phòng KH-NV nhưng:

- PGD cố định theo tài khoản đăng nhập — không có selectbox chọn PGD.
- Không có nút **"Thay thế toàn bộ dgd_map"** — chỉ có **Merge** (chỉ ghi đè nhánh PGD mình).
- Tab Tổng quan chỉ hiện 1 dòng thống kê của PGD mình.
