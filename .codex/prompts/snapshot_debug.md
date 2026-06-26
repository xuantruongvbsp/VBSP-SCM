# Prompt debug snapshot

Bạn đang debug snapshot trong `VBSP-SCM`.

Đọc trước:

1. `snapshot_service.py`
2. `db.py` với bảng `hstd_snapshot`
3. `services/upload_service.py` nếu lỗi phát sinh sau merge
4. `workspaces/ws_management.py` và tab dùng số liệu kỳ trước
5. test liên quan như `tests/test_snapshot_service.py`

Mục tiêu:

- Xác định lỗi ở suy ra kỳ, tổng hợp snapshot, truy vấn kỳ, cache dữ liệu hay render.
- Kiểm tra `ma_ct='ALL'`, `nguon_von='ALL'`, dòng `__CN__` và tổng theo PGD.
- Không thay đổi cấu trúc snapshot nếu chưa được yêu cầu rõ.
- Báo nguyên nhân gốc, phạm vi sửa và cách verify bằng dữ liệu 2 kỳ.
