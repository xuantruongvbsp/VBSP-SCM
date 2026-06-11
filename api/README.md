# API RESTful — VBSP-SCM
Chạy: python -m flask --app api.app run --port 8502
Endpoints:
- GET /api/health — kiểm tra trạng thái
- GET /api/pgd — danh sách PGD
- GET /api/du_no?pgd=<ten_pgd> — dư nợ (tất cả nếu bỏ pgd)
- GET /api/nqh — tỷ lệ NQH theo PGD
- GET /api/chuong_trinh — dư nợ theo chương trình
