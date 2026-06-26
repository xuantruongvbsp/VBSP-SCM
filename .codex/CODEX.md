# Quy tắc Codex cho VBSP-SCM

Codex phải coi đây là dự án nội bộ có dữ liệu tín dụng, nhiều role, nhiều luồng upload, nhiều cache và có audit bắt buộc.

## Nguyên tắc nền

- Luôn đọc file liên quan trước khi sửa. Không suy đoán từ tên file.
- Phân tích nguyên nhân trước, sửa sau.
- Chỉ sửa trong phạm vi yêu cầu hoặc phạm vi cần thiết để fix triệt để lỗi.
- Ưu tiên sửa ít nhất có thể. Không refactor rộng nếu người dùng không yêu cầu.
- Không đổi UI, text, flow nghiệp vụ, quyền truy cập, dữ liệu hiển thị nếu không có yêu cầu rõ ràng.
- Không đổi API công khai, format dữ liệu đầu vào/đầu ra, key `kv_store`, schema SQLite, đường dẫn runtime, cấu trúc cache/parquet trừ khi được yêu cầu rõ.
- Giữ logging hiện có. Nếu thêm nhánh lỗi mới thì thêm log phù hợp, không xóa log cũ có ích.
- Giữ audit hiện có. Mọi thao tác ghi phải nghĩ đến `db.ghi_audit()`.
- Giữ chiến lược cache hiện có. Không tự ý bỏ `st.cache_data`, `st.cache_resource`, cache parquet hoặc xóa cache bừa bãi.
- Giữ snapshot và dữ liệu nền cho so sánh kỳ. Không phá `hstd_snapshot`.
- Giữ tương thích role cũ và mới thông qua `normalize_role()`.

## Điều Codex không được làm nếu chưa được yêu cầu

- Không đổi schema DB trong `db.py`.
- Không đổi cấu trúc bảng `kv_store`, `audit_log`, `hstd_snapshot`.
- Không đổi key pattern trong `kv_store`.
- Không hardcode role mới, cột mới, đường dẫn mới.
- Không đổi tên cột dữ liệu nếu chưa kiểm hết ảnh hưởng.
- Không chuyển logic từ service sang tab hoặc ngược lại chỉ vì "đẹp code".
- Không thay thế thư viện nền lớn khi chưa có lý do mạnh.
- Không bỏ logger, cache, audit, retry, fallback hiện có.
- Không sửa prompt, docs hay test để che lỗi code.

## Thứ tự làm việc bắt buộc

1. Xác định yêu cầu và module liên quan.
2. Đọc luồng gọi từ `app.py` hoặc `workspaces/` vào `tabs/`, rồi xuống `services/`, `data/`, `db.py` nếu cần.
3. Tìm nguồn dữ liệu thật: `cache/*.parquet`, `pgd_data/{slug}/`, `kv_store`, `hstd_snapshot`, file hệ thống trong `data/`.
4. Xác định role bị ảnh hưởng: `executive`, `admin_cn`, `manager_cn`, `chuyenvien_cn`, `admin_pgd`, `manager_pgd`, `user_pgd`.
5. Liệt kê rủi ro: số liệu, quyền, cache, snapshot, upload, audit, Telegram.
6. Chỉ sau đó mới đề xuất sửa.

## Quy tắc sửa an toàn

- Bắt đầu từ lớp thấp nhất có lỗi thật. Nếu bug nằm ở `services/`, tránh vá vòng ngoài ở tab.
- Khi sửa tab, dùng pattern `render(tab=None, **kwargs)` và fallback container.
- Khi sửa upload, merge, KHTD, security, Telegram, snapshot: luôn kiểm tra tác động tới audit và cache.
- Khi sửa hiển thị số tiền: dùng formatter trong `utils.py`, không tự chế formatter mới nếu không thật cần.
- Khi sửa dữ liệu role-based: dùng `normalize_role()`, `la_phan_he_cn()`, `la_phan_he_pgd()`, không so chuỗi thô.
- Khi sửa dữ liệu ghi xuống DB hoặc kv: kiểm tra rollback logic và dữ liệu cũ còn đọc được không.

## Mức ưu tiên khi có xung đột

1. An toàn dữ liệu.
2. Không đổi behavior ngoài phạm vi.
3. Đúng kiến trúc dự án.
4. Dễ review.
5. Tối ưu hiệu năng.
6. Đẹp code.

## Kết quả Codex phải trả về khi hoàn tất

- Nêu file đã đọc.
- Nêu nguyên nhân gốc.
- Nêu thay đổi đã làm và vì sao chọn cách đó.
- Nêu rủi ro còn lại.
- Nêu cách kiểm tra lại bằng app, test hoặc smoke.

## Cải tiến quy tắc đề xuất thêm

- Với mọi sửa liên quan upload hoặc merge, nên kiểm tra thêm `tests/test_integration_upload_merge.py` hoặc test gần nhất liên quan.
- Với mọi sửa liên quan số liệu lịch sử, nên kiểm tra thêm `snapshot_service.py` và tab dùng snapshot trong `ws_management.py`.
- Với mọi sửa liên quan bảo mật, phải soát cả `security.py`, `auth.py`, `tabs/tab_security.py`, `tests/test_security.py`.
