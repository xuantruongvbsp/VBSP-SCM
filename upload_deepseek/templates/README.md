# Templates VBSP-SCM

Đặt file Word mẫu chuẩn vào đây với tên chính xác:

- `mau_06td.docx`   — Mẫu 06/TD Phiếu kiểm tra sử dụng vốn
- `mau_06atd.docx`  — Mẫu 06A/TD
- `mau_15td.docx`   — Mẫu 15/TD Danh sách đối chiếu số dư
- `mau_16td.docx`   — Mẫu 16/TD Biên bản kiểm tra Tổ TK&VV
- `ke_hoach_kt.docx` — Kế hoạch kiểm tra giám sát ủy thác
- `bb_xac_minh_no.docx` — Biên bản xác minh nợ chiếm dụng

## Hướng dẫn tạo template

1. Tạo file Word với nội dung mẫu chuẩn theo văn bản 727/HD-NHCS
2. Thay các giá trị động bằng cú pháp Jinja2: `{{ ten_bien }}`
3. Ví dụ: `{{ don_vi_kt }}`, `{{ ngay_kt }}`, `{{ ds_kh }}`
4. Lưu file vào thư mục này với tên đúng như danh sách trên
