# Hướng dẫn sử dụng Mạng lưới Tổ TK&VV

> VBSP-SCM · Module Cán bộ Tổ TK&VV · Cập nhật: 05/2026

---

## 1. Giới thiệu

### Mạng lưới Tổ TK&VV là gì?

Module quản lý và đánh giá chất lượng hoạt động của **Tổ Tiết kiệm & Vay vốn**
trên địa bàn 21 PGD, 95 xã/phường.

### Ai sử dụng?

- **Admin**: Toàn quyền
- **Manager**: Xem báo cáo, xuất dữ liệu
- **User**: Xem dữ liệu PGD được phân công
- **Executive**: Dashboard tổng quan (không truy cập tab này)

---

## 2. Các sub-tab chính

### Phân tích Chất lượng

Đánh giá tổ theo **6 tiêu chí**:

1. Tổ viên tham gia tiền gửi
2. Tỷ lệ nợ quá hạn
3. Tỷ lệ thu lãi
4. Thu nợ đến hạn
5. Số dư tiền gửi tăng thêm
6. Giao dịch tại xã

**Điểm số:**

- Mỗi tiêu chí có điểm tối đa riêng (theo cấu hình hệ thống)
- Tổng điểm tối đa lý thuyết: **100** (5 + 30 + 20 + 15 + 10 + 20)
- Xếp loại: Xuất sắc / Khá / Trung bình / Yếu

---

## 3. Xuất danh sách Tổ không đạt tiêu chí

### Mục đích

Xuất file Excel danh sách các tổ **chưa đạt đủ điểm tối đa** của 1 hoặc nhiều tiêu chí.

### Hướng dẫn từng bước

#### Bước 1: Truy cập

1. Vào tab **Mạng lưới Tổ TK&VV**
2. Chọn sub-tab **Phân tích Chất lượng**
3. Chọn **tháng** cần phân tích ở đầu trang
4. Kéo xuống phần **Xuất danh sách Tổ không đạt tiêu chí**

#### Bước 2: Chọn bộ lọc

**Chọn tiêu chí:**

- Hộp chọn hỗ trợ **chọn nhiều tiêu chí** cùng lúc
- Ví dụ: Chọn cả "Tỷ lệ nợ quá hạn" và "Thu nợ đến hạn"
- Kết quả: File Excel có nhiều sheet, mỗi sheet một tiêu chí

**Lọc theo PGD (tùy chọn):**

- Mặc định: "Tất cả" (toàn Chi nhánh)
- Có thể chọn một hoặc nhiều PGD cụ thể
- Ví dụ: Chỉ xem PGD Long Thành và PGD Nhơn Trạch

#### Bước 3: Xem thống kê

Sau khi chọn tiêu chí, hệ thống hiển thị:

**Thống kê tổng hợp:**

- Tổng số dòng tổ không đạt (gộp theo các tiêu chí đã chọn; một tổ có thể xuất hiện ở nhiều sheet nếu không đạt nhiều tiêu chí)
- Số PGD trong phạm vi lọc
- Số tiêu chí đã chọn
- Tỷ lệ không đạt (%)

**Chi tiết theo tiêu chí:**

- Mỗi tiêu chí một khối thu gọn (expander)
- Điểm trung bình / thấp nhất / cao nhất
- Xem trước tối đa 20 tổ đầu tiên

#### Bước 4: Xuất Excel

1. Bấm **Xuất Excel**
2. Đợi hệ thống tạo file (thường vài giây)
3. Bấm **Tải xuống** để lưu file về máy

---

## 4. Cấu trúc file Excel xuất ra

### Nếu chọn 1 tiêu chí

**Tên file:** `To_khong_dat_[mã_tieu_chi]_[timestamp].xlsx`

**Cột trong sheet (thứ tự gợi ý):**

| Cột | Mô tả |
|-----|--------|
| Tiêu chí | Tên hiển thị tiêu chí |
| Điểm tối đa | Điểm tối đa của tiêu chí |
| Điểm đạt được | Điểm số (số) tổ đạt được |
| Chênh lệch | Điểm tối đa trừ điểm đạt được |
| PGD | Tên đơn vị / PGD |
| Xã | Tên xã |
| Mã Tổ | Mã định danh tổ |
| Tổ trưởng | Họ tên tổ trưởng (nếu có trong nguồn) |
| Tổng điểm | Tổng điểm tổ |
| Xếp loại | Xếp loại chung |
| Dư nợ | Dư nợ (nếu có) |
| Số dư TK | Số dư tiết kiệm (nếu có) |
| [Tên tiêu chí] | Giá trị gốc trên sheet nguồn |

### Nếu chọn nhiều tiêu chí

**Tên file:** `To_khong_dat_[N]_tieu_chi_[timestamp].xlsx`

- Mỗi tiêu chí một sheet; tên sheet rút gọn theo giới hạn Excel (31 ký tự), tránh trùng tên.

---

## 5. Ý nghĩa "Không đạt"

**"Không đạt"** trong ngữ cảnh xuất Excel nghĩa là:

> Tổ có **điểm đạt được nhỏ hơn điểm tối đa** của tiêu chí đó.

**Không đồng nghĩa với:**

- Điểm bằng 0
- Tổ xếp loại yếu (trừ khi trùng khớp dữ liệu)
- Vi phạm quy định

**Ví dụ:**

- Tiêu chí "Tỷ lệ nợ quá hạn" có điểm tối đa = 30
- Tổ A đạt 12 điểm → nằm trong danh sách "không đạt tối đa" (thiếu 18 điểm so với trần)
- Tổ B đạt 30 điểm → không xuất hiện trong danh sách xuất của tiêu chí này

---

## 6. Use cases thực tế

### Case 1: Tìm tổ yếu về thu nợ

1. Chọn tiêu chí: "Thu nợ đến hạn"
2. Lọc PGD: "Tất cả"
3. Bấm **Xuất Excel** rồi **Tải xuống**
4. Gửi file cho các PGD để đôn đốc theo danh sách

### Case 2: Rà soát một cụm PGD

1. Chọn nhiều tiêu chí (ví dụ nợ quá hạn + thu lãi)
2. Lọc PGD: chọn 2–3 PGD cần họp giao ban
3. Xem thống kê và expander từng tiêu chí trước khi xuất

### Case 3: Báo cáo định kỳ đa tiêu chí

1. Chọn đủ các tiêu chí cần theo dõi kỳ báo cáo
2. Xuất một file nhiều sheet để lưu trữ và đối chiếu nội bộ

---

Tài liệu này mô tả giao diện và luồng sử dụng; tham số điểm tối đa từng tiêu chí lấy theo cấu hình trong mã nguồn (`_CDTOTKVV_DIEM_TOI_DA`).
