# Prompt cho CDTOTKVV

Bạn đang làm việc với Chấm điểm Tổ TK&VV trong `VBSP-SCM`.

Đọc trước:

- `services/cdtotkvv_service.py`
- `tabs/tab_cdtotkvv.py`
- `tabs/tab_cdtotkvv_pgd.py`
- `data/pgd.py`
- `config.py` với `CDTOTKVV_*`

Kiểm tra:

- dữ liệu từ `pgd_data/{slug}/cdtotkvv`
- phân biệt mode CN và PGD
- trạng thái cập nhật 22 đơn vị
- format xuất Excel/PDF
- lọc theo đơn vị và mapping cột

Không sửa trực tiếp ở tab nếu lỗi nằm trong service xử lý dữ liệu thuần.
