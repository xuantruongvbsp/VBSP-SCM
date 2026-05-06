# KHTD Targets Demo (React CDN + Mock API)

Chạy demo 3 màn hình:
- Trang chủ
- Nhập Google Sheet (preview)
- Giao/Điều chỉnh chỉ tiêu CN/PGD

## Chạy server

```bash
python khtd-targets-app/server.py
```

Mở trình duyệt: `http://127.0.0.1:5174/`

## API mock

- `POST /api/sheets/preview`
- `GET /api/targets?unitType=CN&period=2026-Q2`
- `POST /api/targets/save`

## Dữ liệu mẫu

Dữ liệu lưu trong `khtd-targets-app/store.json` và sẽ được cập nhật khi bấm Lưu.

