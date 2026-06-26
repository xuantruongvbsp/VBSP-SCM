# Kiến trúc thực tế của VBSP-SCM

`VBSP-SCM` là ứng dụng Streamlit nội bộ cho quản trị và tác nghiệp tín dụng. Repo có ba trục chính:

- UI theo `workspaces/` và `tabs/`
- nghiệp vụ theo `services/`
- đọc dữ liệu theo `data/`, `db.py`, `snapshot_service.py`, `cache/*.parquet`, `pgd_data/`

## Bức tranh tổng thể

```text
app.py
  -> auth.py + security.py + state_manager.py
  -> load data/cache
  -> enrich DataFrame
  -> route vào workspace

workspaces/ws_*.py
  -> import tab theo role / phân hệ
  -> truyền context chung

tabs/tab_*.py
  -> render UI
  -> gọi services/ hoặc data/

services/*.py
  -> xử lý nghiệp vụ, upload, merge, KHTD, Telegram, báo cáo, kiểm soát

data/*.py
  -> đọc file nguồn, pgd_data, parquet cache, chuẩn hóa dữ liệu

db.py
  -> SQLite + kv_store + audit_log + snapshot + nhiệm vụ
```

## app.py

`app.py` là điểm vào chính.

Vai trò thực tế:

- khởi tạo logging sớm để `logs/app.log` hoạt động ngay khi app import
- nạp `config`, `auth`, `security`, `db`, `state_manager`
- load HSTD từ parquet bằng DuckDB trong `_load_hstd()`
- load NQ11 và các nguồn liên quan
- enrich HSTD bằng cờ `__is_nq11`, `__is_gqvl`
- xác định workspace theo role qua `WORKSPACE_MAP`
- truyền `df`, `df_full`, `df_nq11`, `pgd_user`, `username`, `role` vào workspace

Điểm cần nhớ cho Codex:

- `app.py` là nơi quyết định luồng dữ liệu chính, không phải `tabs/`.
- `app.py` dùng `@st.cache_resource` cho load dữ liệu lớn.
- Nhiều thay đổi tưởng là "lỗi UI" thực ra xuất phát từ logic load hoặc enrich tại đây.

## workspaces

Ba workspace chính:

- `workspaces/ws_executive.py`: dashboard vĩ mô cho BGĐ, chủ yếu read-only.
- `workspaces/ws_management.py`: điều hành cấp Chi nhánh, tổng hợp 22 PGD, nhiều tab giám sát, KHTD, kiểm soát, báo cáo.
- `workspaces/ws_operation.py`: tác nghiệp cấp PGD, chỉ thấy dữ liệu của PGD hoặc phạm vi được phân quyền.

Vai trò workspace:

- gom tab thành nhóm theo nghiệp vụ
- truyền `kwargs` nhất quán
- xử lý phân nhánh role/pgd_mode
- lazy import tab để giảm tải khởi động

## tabs

`tabs/` là lớp UI chính. Mỗi file thường là một tab hoặc một phần tab.

Mẫu kiến trúc đang dùng:

- tab render nhận `tab=None, **kwargs`
- fallback `st.container()` hoặc helper `get_tab_context()`
- tab không nên hardcode đường dẫn dữ liệu
- tab gọi `services/` cho logic ghi, merge, xuất, kiểm tra

Các nhóm tab quan trọng:

- Upload: `tab_upload_khnv.py`, `tab_upload_pgd.py`, `tabs/tab_upload_khnv/*`
- KHTD: `tab_khtd.py`, `tab_khtd_giao_dc.py`, `tab_khtd_nhap.py`, `tab_khtd_xuat.py`, `tab_xay_dung_khtd.py`
- Dashboard/Báo cáo: `tabs/tab_baocao/*`, `tab_tongquan.py`, `tab_pgd_cards.py`, `tab_cbtd_dashboard.py`
- Chương trình chuyên đề: `tab_nq11.py`, `tab_gqvl.py`, `tab_cdtotkvv.py`, `tab_cdtotkvv_pgd.py`
- Kiểm soát và rủi ro: `tab_kiem_soat.py`, `tab_ktnb.py`, `tab_no_khoanh.py`, `tab_xu_ly_rui_ro.py`
- Bảo mật và quản trị: `tab_security.py`, `tab_telegram_admin.py`, `tab_audit_log.py`

## services

`services/` là nơi đặt logic nghiệp vụ tái sử dụng.

Service trọng yếu:

- `upload_service.py`: chuẩn hóa kiểm tra file, lưu file, merge toàn CN, xóa cache, metadata merge, một phần trigger downstream.
- `khtd_service.py`: giao và điều chỉnh KHTD, khóa `kv_store`, Google Sheet, lịch sử đợt.
- `telegram_service.py`: push notification 1 chiều, config trong `kv_store`, retry mức nhẹ.
- `data_priority_service.py`: widget và báo cáo trạng thái file upload ở `pgd_data/`.
- `cdtotkvv_service.py`: xử lý dữ liệu thuần cho chấm điểm Tổ TK&VV.
- `kiem_soat_service.py`, `report_service.py`, `template_service.py`, `migration_service.py`, `du_phong_service.py`: các khối chuyên trách theo domain.

Quy ước quan trọng:

- tab gọi service, service không phụ thuộc tab.
- khi có thể, logic tính toán thuần nên đưa xuống service để dễ test.

## data

`data/` là lớp đọc dữ liệu và tiện ích dữ liệu nền.

Vai trò:

- đọc file HSTD, NQ11, GQVL
- quản lý `pgd_data/{slug}/`
- chuẩn hóa đường dẫn theo `pgd_slug()`
- chuyển Excel sang parquet và hỗ trợ cache
- quét nguồn dữ liệu hoặc registry chương trình

Điểm quan trọng:

- `data.pgd` là nguồn chuẩn để xác định đường dẫn file PGD.
- `data.core` và các hàm parquet liên quan ảnh hưởng trực tiếp hiệu năng app.

## config

`config.py` là lõi hằng số toàn hệ thống.

Nó định nghĩa:

- thư mục runtime: `data`, `cache`, `pgd_data`, `templates`
- tên file hệ thống
- đường dẫn cache parquet
- danh sách PGD, mapping xã, mapping chương trình
- tên cột chuẩn, key danh mục, baseline path

Codex phải xem `config.py` là nguồn sự thật cho:

- tên cột
- danh sách đơn vị
- file path chuẩn
- chương trình tín dụng

## utils

`utils.py` chứa helper dùng xuyên suốt:

- format số liệu theo chuẩn VN
- decorator `auto_audit`
- helper hiển thị dataframe
- helper đọc cấu hình động từ `kv_store`

Quy tắc:

- nếu cần format tiền/tỷ lệ/ngày, ưu tiên dùng `utils.py`
- không tự định nghĩa formatter mới chỉ để dùng cục bộ nếu formatter hiện có đáp ứng được

## cache và parquet

Repo dùng hai lớp cache:

- cache Streamlit: `@st.cache_data`, `@st.cache_resource`
- cache file parquet: `cache/*.parquet`

Mục tiêu:

- giảm thời gian load HSTD lớn
- chia sẻ dữ liệu đã load giữa session
- giảm việc đọc Excel lặp lại

Điểm cần nhớ:

- `upload_service.py` và các flow ghi dữ liệu phải cân nhắc clear cache đúng lúc
- không xóa parquet hay clear toàn bộ cache nếu không cần
- thay đổi ở merge có thể ảnh hưởng trực tiếp `CACHE_HSTD`, `CACHE_NQ11`, `CACHE_GQVL`

## snapshot

`snapshot_service.py` lưu snapshot HSTD theo kỳ vào SQLite, bảng `hstd_snapshot`.

Dùng cho:

- so sánh kỳ
- delta NQH
- dashboard xu hướng
- heatmap hoặc báo cáo lịch sử

Nguyên tắc:

- snapshot là lớp dữ liệu lịch sử, không được phá khi sửa merge hoặc hiển thị
- các bug "số liệu kỳ này so với kỳ trước sai" thường cần xem cả merge lẫn snapshot

## audit

Audit dựa trên `db.ghi_audit()` và bảng `audit_log`.

Có mặt ở nhiều mảng:

- đăng nhập và lỗi đăng nhập
- upload, merge, lưu KHTD
- cập nhật config Telegram
- timeout, chặn IP, thao tác bảo mật
- snapshot, nhiệm vụ, cấu hình

Nếu Codex thêm thao tác ghi mới mà không thêm audit, đó thường là thiếu sót kiến trúc.

## Telegram

`services/telegram_service.py` là push notification 1 chiều.

Đặc điểm:

- config lấy từ `kv_store`, fallback env/default
- có chat chính và extra chat theo loại thông báo
- có retry nhẹ khi lỗi mạng
- có log gửi tin trong `kv_store`

Các flow hay chạm Telegram:

- merge thành công
- nhắc deadline
- health check
- khoản đến hạn, phân kỳ NXH

## API phụ

Repo có `api/app.py` và `khtd-targets-app/` phục vụ các nhu cầu phụ trợ. Không được giả định mọi thay đổi ở app Streamlit đều vô can với các thành phần này.

## Kết luận kiến trúc

Khi sửa trong repo này, Codex nên đi theo trục:

`app.py` -> `workspace` -> `tab` -> `service` -> `data/db/config`

Không nên bắt đầu bằng vá UI nếu chưa rõ dữ liệu gốc, quyền và cache đi qua đâu.
