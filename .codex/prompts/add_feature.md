# Prompt thêm tính năng

Bạn đang thêm tính năng cho `VBSP-SCM`.

Trước khi code, bắt buộc:

1. Đọc kiến trúc liên quan.
2. Xác định tính năng này thuộc `workspace`, `tab`, `service`, `data`, `db`, `config` hay `component`.
3. Liệt kê file sẽ chạm vào.
4. Đánh giá rủi ro:
   - role
   - cache/parquet
   - snapshot
   - audit
   - Telegram
   - hiệu năng
5. Chỉ đề xuất thay đổi tối thiểu để khớp kiến trúc hiện có.

Không được:

- đổi behavior cũ ngoài phạm vi
- đổi schema DB
- tạo flow dữ liệu song song không cần thiết
- hardcode role, cột, PGD, path
