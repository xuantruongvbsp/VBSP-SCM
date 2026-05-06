# Thiết kế trang (Desktop-first) — Giao/Điều chỉnh chỉ tiêu CN & PGD

## Global Styles (Design tokens)
- Layout grid: container max-width 1200px, gutter 24px, section spacing 24–32px.
- Màu nền: #F7F8FA; surface/card: #FFFFFF; viền: #E6E8EC.
- Primary: #0B5FFF; hover: #094BD1; danger: #D92D20; warning: #DC6803; success: #039855.
- Typography: font sans (Inter/Segoe UI); H1 24/32, H2 18/28, body 14/22; số liệu dùng tabular-nums.
- Button: height 36 (secondary), 40 (primary); trạng thái disabled rõ ràng.
- Input/table: focus ring 2px primary; cell padding 10–12px; sticky header cho bảng dài.
- Responsive: desktop-first; >=1200 3 cột khi cần; 768–1199 co về 2 cột; <768 xếp dọc, bảng chuyển dạng “stacked rows”.

---

## 1) Trang chủ
### Meta Information
- Title: "Chỉ tiêu CN/PGD"
- Description: "Điều hướng nhập dữ liệu Google Sheet và giao/điều chỉnh chỉ tiêu."
- Open Graph: title/description giống trên.

### Layout
- Flexbox + CSS Grid.
- Header cố định (sticky) + vùng nội dung 1 cột.

### Page Structure
1. Top bar
2. Khối chọn kỳ/đợt
3. Thẻ điều hướng nhanh
4. Thẻ trạng thái đồng bộ gần nhất

### Sections & Components
- **Top bar**: Logo/tiêu đề trái; phải có nút điều hướng nhanh ("Nhập Google Sheet", "Giao/Điều chỉnh").
- **Chọn kỳ/đợt** (Card): dropdown/combobox kỳ; nút "Áp dụng".
- **Quick actions** (Card grid 2 cột):
  - Card 1: "Nhập dữ liệu Google Sheet" + mô tả + nút "Mở".
  - Card 2: "Giao/Điều chỉnh chỉ tiêu" + mô tả + nút "Mở".
- **Trạng thái đồng bộ gần nhất** (Card): hiển thị thời gian, nguồn (sheetUrl rút gọn), kết quả; link "Xem chi tiết" dẫn sang trang nhập.

---

## 2) Trang Nhập dữ liệu Google Sheet
### Meta Information
- Title: "Nhập dữ liệu — Google Sheet"
- Description: "Tải dữ liệu chỉ tiêu từ Google Sheet, xem trước và kiểm tra lỗi."

### Layout
- Grid 12 cột: trái (4 cột) cấu hình; phải (8 cột) xem trước.
- Ở tablet: 2 khối xếp dọc.

### Page Structure
1. Breadcrumb: Trang chủ / Nhập dữ liệu
2. Panel cấu hình nguồn
3. Panel xem trước dữ liệu
4. Khu vực lỗi & hướng dẫn sửa

### Sections & Components
- **Panel cấu hình nguồn** (Card):
  - Field: Link Google Sheet (text)
  - Field: Tên tab (text)
  - Field: Kỳ/đợt (dropdown)
  - Actions: "Tải xem trước" (primary), "Xóa" (secondary)
  - Ghi chú nhỏ: yêu cầu quyền truy cập sheet (tài khoản/service account) để đồng bộ.
- **Panel xem trước** (Card):
  - Table preview (sticky header): các cột tối thiểu: cấp, mã đơn vị, tên đơn vị, mã cha, chỉ tiêu.
  - Badge tổng số dòng + số lỗi.
- **Danh sách lỗi** (Alert/Accordion):
  - Hiển thị lỗi theo dòng (rowIndex + message), hướng dẫn “sửa trên Google Sheet rồi tải lại”.

---

## 3) Trang Giao/Điều chỉnh chỉ tiêu (CN/PGD)
### Meta Information
- Title: "Giao/Điều chỉnh chỉ tiêu"
- Description: "Phân bổ và điều chỉnh chỉ tiêu theo phân cấp CN (tỉnh→xã) hoặc PGD (xã→thôn)."

### Layout
- Desktop: chia 2 vùng chính (left tree 320px, right content auto) bằng CSS Grid.
- Right content gồm: thanh bộ lọc + bảng nhập.

### Page Structure
1. Breadcrumb: Trang chủ / Giao/Điều chỉnh
2. Thanh bộ lọc & ngữ cảnh
3. Vùng trái: cây phân cấp
4. Vùng phải: bảng chỉ tiêu + kiểm tra tổng + lưu

### Sections & Components
- **Thanh bộ lọc** (Card mỏng, 1 hàng):
  - Toggle/segment: Loại đơn vị ("CN" | "PGD")
  - Dropdown: Kỳ/đợt
  - Dropdown/combobox: Đơn vị gốc
  - Nút: "Tải dữ liệu" (secondary)
- **Cây phân cấp** (Left panel):
  - Khi chọn **CN**: hiển thị tỉnh → xã.
  - Khi chọn **PGD**: hiển thị xã → thôn.
  - Interaction: click node để hiển thị danh sách con ở bảng bên phải.
- **Bảng chỉ tiêu** (Right panel):
  - Cột gợi ý: Cấp, Mã đơn vị, Tên đơn vị, Chỉ tiêu (editable numeric).
  - Cell edit: nhập số; hiển thị định dạng; chặn ký tự không hợp lệ.
  - Row state: highlight dòng đã sửa.
- **Kiểm tra tổng** (Summary bar dưới bảng):
  - Hiển thị tổng chỉ tiêu cấp con đang xem.
  - Cảnh báo (warning) khi tổng cấp con không khớp logic với tổng cấp cha (nếu có dữ liệu tổng cha).
- **Hành động**:
  - "Lưu" (primary): lưu kết quả điều chỉnh theo kỳ/đợt.
  - "Hoàn tác thay đổi" (secondary): trả về dữ liệu đã tải.

### Interaction & states
- Loading: skeleton cho cây và bảng khi tải.
- Empty state: hướng dẫn “hãy nhập dữ liệu Google Sheet trước” nếu chưa có dữ liệu cho kỳ/đợt.
- Error state: banner lỗi khi không tải được dữ liệu/không truy cập được sheet.
