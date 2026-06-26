# Checklist trước merge / release

## Mục tiêu

Đảm bảo thay đổi có thể merge hoặc đưa lên môi trường chạy mà không làm hỏng:

- số liệu
- quyền truy cập
- upload/merge
- cache/parquet
- snapshot
- audit
- Telegram/health check

## Checklist bắt buộc

- Đã đọc và hiểu file gốc bị ảnh hưởng
- Đã giới hạn thay đổi trong đúng phạm vi
- Không đổi schema DB, key `kv_store`, API, đường dẫn runtime nếu không được yêu cầu
- Có giữ logging và audit
- Có kiểm tra role CN/PGD nếu thay đổi chạm UI hoặc route
- Có kiểm tra cache và invalidation sau thao tác ghi
- Có kiểm tra tác động đến parquet và snapshot nếu chạm upload/merge
- Có kiểm tra tác động đến Telegram nếu thay đổi merge, deadline, health check

## Kiểm tra kỹ thuật

- `python -m compileall -q . -x ".venv|venv|__pycache__|\\.git"`
- `python scripts/check_conventions.py --all`
- `pytest tests/ -q --tb=short`

## Kiểm tra nghiệp vụ tối thiểu

- Mở app được bằng `streamlit run app.py`
- Tab/chức năng bị sửa render được
- Role chính liên quan không bị chặn sai
- Nếu sửa upload: upload thử hoặc smoke flow lưu file
- Nếu sửa merge: xác nhận metadata merge, cache, số liệu đầu ra
- Nếu sửa snapshot: xác nhận danh sách kỳ hoặc dữ liệu lịch sử còn đọc được

## Kiểm tra tài liệu handoff

- Mô tả nguyên nhân gốc
- Mô tả file đã sửa
- Mô tả rủi ro còn lại
- Mô tả cách rollback nếu cần

## Không nên merge nếu

- Chưa rõ tác động đến role khác
- Chưa kiểm cache/snapshot khi sửa upload hoặc số liệu
- Chưa có audit cho thao tác ghi mới
- Chưa kiểm tra smoke tối thiểu trên app
