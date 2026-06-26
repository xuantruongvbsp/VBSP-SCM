# Prompt fix bug

Bạn đang làm việc trong `VBSP-SCM`.

Yêu cầu:

1. Đọc project trước, không đoán.
2. Xác định lỗi nằm ở `app.py`, `workspaces/`, `tabs/`, `services/`, `data/`, `db.py`, `snapshot_service.py` hay `security.py`.
3. Liệt kê file cần đọc trước khi sửa.
4. Tìm nguyên nhân gốc, không vá UI nếu lỗi nằm ở dữ liệu hoặc service.
5. Chưa sửa ngay. Trước hết hãy báo:
   - nguyên nhân khả dĩ
   - phạm vi file
   - rủi ro role, cache, audit, snapshot
6. Chỉ sau khi đã phân tích xong mới đề xuất bản vá tối thiểu.
7. Không refactor ngoài phạm vi.
8. Giữ logging, audit, cache, quyền truy cập.
