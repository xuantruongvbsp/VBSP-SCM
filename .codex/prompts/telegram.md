# Prompt cho Telegram

Bạn đang làm việc với Telegram trong `VBSP-SCM`.

Đọc trước:

- `services/telegram_service.py`
- `tabs/tab_telegram_admin.py`
- các flow gọi Telegram từ upload, merge, health check, nhắc deadline

Kiểm tra:

- token/chat id lấy từ đâu
- có extra chat theo loại thông báo không
- retry khi lỗi mạng
- audit khi đổi config
- log gửi tin trong `kv_store`

Không:

- hardcode token mới
- log secret
- tạo flow gửi Telegram rời rạc ngoài service nếu không thật cần
