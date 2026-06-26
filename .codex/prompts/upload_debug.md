# Prompt debug upload

Bạn đang debug luồng upload của `VBSP-SCM`.

Hãy kiểm tra theo thứ tự:

1. `tabs/tab_upload_khnv.py`, `tabs/tab_upload_pgd.py` và các file con trong `tabs/tab_upload_khnv/`
2. `services/upload_service.py`
3. `services/data_quality.py`
4. `data/pgd.py`, `data/core.py`
5. `cache/*.parquet`
6. `snapshot_service.py`
7. `db.py` và audit liên quan

Yêu cầu:

- Xác định lỗi ở validate file, lưu file, merge, clear cache, snapshot hay UI.
- Kiểm tra tác động tới `merge_meta_{loai}`, parquet, Telegram, audit.
- Liệt kê nguyên nhân gốc và file liên quan trước khi sửa.
- Nếu chưa chắc, hỏi thêm thay vì đoán.
