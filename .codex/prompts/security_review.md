# Prompt review bảo mật

Bạn đang review bảo mật cho `VBSP-SCM`.

Đọc trước:

- `security.py`
- `auth.py`
- `db.py`
- `services/upload_service.py`
- `services/telegram_service.py`
- `tabs/tab_security.py`

Kiểm tra:

- session timeout
- IP whitelist
- 2FA admin
- upload validation
- path traversal
- secret/token/config
- audit cho thao tác bảo mật
- role escalation

Yêu cầu:

- Liệt kê findings theo mức độ.
- Nêu file bị ảnh hưởng.
- Nêu cách khắc phục ít rủi ro nhất.
