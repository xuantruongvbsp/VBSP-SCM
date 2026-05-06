# Definition of Ready cho NOXH 2026

Tài liệu này chốt điều kiện sẵn sàng trước khi triển khai sprint tự động hóa 25 mẫu biểu NOXH.

## 1) Điều kiện dữ liệu
- 100% luồng `HSTD/NQ11/GQVL` đi qua lớp kiểm soát chất lượng dữ liệu tập trung tại `services/data_quality.py`.
- Không còn lỗi cột bắt buộc ở lần merge gần nhất.
- Mã PGD, tên xã và mã chương trình đã được chuẩn hóa ngay bước ingest.
- Có báo cáo chất lượng dữ liệu theo loại file và theo kỳ merge trong giao diện quản trị.

## 2) Điều kiện vận hành
- Luồng upload từ `tabs/tab_upload_khnv.py` và `tabs/tab_upload_pgd.py` có chặn file khi chất lượng dữ liệu không đạt.
- Metadata chất lượng dữ liệu được ghi vào `kv_store` để truy vết.
- Người vận hành nhìn thấy trạng thái đạt/chưa đạt trong tab quản trị trước khi chạy báo cáo.

## 3) Điều kiện kiểm thử
- Unit test Data Quality chạy thành công.
- Smoke test kiểm tra upload đầu vào chạy thành công.
- Không có lỗi lint ở các file đã chỉnh sửa.

## 4) Điều kiện nghiệp vụ
- Danh sách mapping chuẩn (PGD/xã/chương trình) được rà soát và xác nhận bởi KH-NV.
- Quy trình xử lý lỗi dữ liệu (file sai, thiếu cột, sai mã) đã có hướng dẫn ngắn cho đơn vị upload.

## 5) Tiêu chí Go/No-Go
- Go: tất cả điều kiện mục 1-4 đạt.
- No-Go: còn lỗi cột bắt buộc hoặc lỗi chuẩn hóa mã nghiêm trọng ở kỳ merge gần nhất.
