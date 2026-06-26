# Prompt debug merge

Bạn đang debug merge dữ liệu toàn Chi nhánh trong `VBSP-SCM`.

Checklist phân tích:

1. Đọc `services/upload_service.py`, đặc biệt flow `merge_du_lieu_toan_cn()`.
2. Đọc `config.py` để biết file path, cache path, PGD list, tên cột.
3. Đọc `data/pgd.py` và `data/core.py`.
4. Kiểm tra `cache/hstd.parquet`, `cache/nq11.parquet`, `cache/gqvl.parquet`.
5. Kiểm tra `merge_meta_{loai}` trong `kv_store`.
6. Nếu là HSTD, kiểm tra thêm `snapshot_service.py`.

Yêu cầu:

- Chỉ ra lỗi nằm ở dữ liệu nguồn, concat/normalize, parquet, cache invalidation hay tab tiêu thụ.
- Không sửa UI trước khi chốt nguyên nhân gốc.
- Nêu rõ rủi ro về số liệu, snapshot, audit, Telegram.
