# Hướng dẫn viết test cho Codex

## Mục tiêu

Viết test đủ để chặn regression thật, không viết test hình thức.

## Nền test hiện có

- Framework: `pytest`
- Cấu hình: `pytest.ini`
- Thư mục test: `tests/`
- CI chạy `pytest tests/ -q --tb=short --cov=.`
- `tests/conftest.py` mock `streamlit` để import module gốc khi chạy test

## Quy tắc chọn mức test

- Nếu logic thuần: ưu tiên unit test ở `services/` hoặc helper.
- Nếu bug liên quan upload/merge: ưu tiên test integration ngắn, gần dữ liệu thật.
- Nếu bug là role gating hoặc render helper: có thể dùng smoke test/import test.
- Nếu thay đổi chỉ là docs hoặc prompt: không thêm test.

## Khi nào phải thêm test

- Sửa bug có nguy cơ lặp lại.
- Sửa service dùng chung bởi nhiều tab.
- Sửa logic merge, snapshot, KHTD, security, Telegram config.
- Thêm formatter hoặc helper được gọi rộng khắp.

## Khi nào không nên thêm test nặng

- Chỉ đổi text UI nhỏ.
- Chỉ đổi markdown/doc.
- Sửa cục bộ mà smoke/manual check đã đủ.

## Pattern viết test trong repo này

- Dùng `tests/conftest.py` để import module cần test mà không cần Streamlit runtime thật.
- Dữ liệu test nên nhỏ, rõ ý nghĩa nghiệp vụ.
- Tránh phụ thuộc file Excel lớn thật nếu có thể thay bằng DataFrame fixture.
- Nếu cần patch DB, patch ở mức `db.doc_kv`, `db.ghi_kv`, `db.get_conn` hoặc fixture tạm.

## Danh mục nên ưu tiên test

- `services/upload_service.py`
- `services/khtd_service.py`
- `snapshot_service.py`
- `services/data_priority_service.py`
- `services/cdtotkvv_service.py`
- `security.py`
- `auth.py`

## Checklist cho Codex trước khi nộp test

- Test có fail nếu bug cũ quay lại không
- Test có đang chỉ lặp lại implementation detail không
- Tên test có mô tả behavior thật không
- Có che mất bug bằng mock quá mức không
- Có tương thích với pattern mock Streamlit hiện tại không

## Lệnh chạy test

```bash
pytest tests/ -q --tb=short
```

Chạy file riêng:

```bash
pytest tests/test_upload_service.py -q --tb=short
```

## Kỳ vọng với Codex

- Nêu rõ vì sao thêm test này.
- Nếu không thêm test, phải giải thích vì sao manual/smoke check là đủ.
