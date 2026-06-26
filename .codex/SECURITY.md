# Checklist bảo mật cho VBSP-SCM

## Bề mặt cần kiểm tra

- đăng nhập và phân quyền trong `auth.py`
- timeout, IP whitelist, 2FA trong `security.py`
- upload file trong `services/upload_service.py`
- secret và config Telegram trong `services/telegram_service.py`
- dữ liệu nhạy cảm trong `kv_store`, `audit_log`, log file

## Checklist bảo mật

- Có validate loại file upload, kích thước và tên file chưa
- Có dùng đường dẫn chuẩn từ `config.py` hoặc `data.pgd` chưa
- Có khả năng path traversal hoặc ghi đè file ngoài thư mục dự án không
- Có log secret, token, password, OTP, chat id nhạy cảm không cần thiết không
- Có mở rộng quyền role ngoài ý muốn không
- Có bypass `normalize_role()` hoặc kiểm role bằng chuỗi cứng không
- Có thao tác ghi cấu hình mà thiếu audit không
- Có reset session hoặc timeout không an toàn không
- Có thêm endpoint hoặc API phụ mà thiếu kiểm soát truy cập không

## Upload file

- File phải đi qua `upload_service.py` hoặc flow chuẩn tương đương.
- Không đọc file upload trực tiếp trong tab rồi ghi xuống tùy ý.
- Kiểm tra loại `.xlsx/.xls` hoặc loại hợp lệ đúng theo flow.
- Tệp tạm hoặc file output phải ở thư mục runtime dự án, không dùng path người dùng tự nhập mà chưa chuẩn hóa.

## Secret và config

- Token Telegram không được hardcode mới trong code.
- Ưu tiên cấu hình qua `kv_store` hoặc environment theo pattern sẵn có.
- Không in secret vào UI, log, exception message.

## Session và truy cập

- Giữ `SESSION_TIMEOUT_MINUTES`.
- Không bỏ `check_and_handle_timeout()` hoặc `is_ip_allowed()` khỏi flow khi không có yêu cầu rõ.
- Với admin flow, phải tôn trọng 2FA hiện có.

## Audit và điều tra

- Mọi thay đổi bảo mật hoặc cấu hình nên có audit.
- Lỗi chặn IP, timeout, cập nhật whitelist phải để lại dấu vết.
- Không sửa theo kiểu "làm chạy được" nhưng xóa audit để đỡ phiền.

## Telegram

- Chỉ gửi tin ra ngoài qua `telegram_service.py`.
- Không tự viết request Telegram mới rải rác trong tab/service khác nếu không thật cần.
- Không gửi dữ liệu khách hàng nhạy cảm quá mức vào thông báo.

## Đề xuất cải tiến quy tắc

- Bất kỳ thay đổi nào chạm `security.py`, `auth.py`, `tab_security.py`, `tab_telegram_admin.py` nên kèm review bảo mật bắt buộc.
- Nên giữ test hoặc smoke tối thiểu cho các flow timeout, role, config Telegram, upload validation.
