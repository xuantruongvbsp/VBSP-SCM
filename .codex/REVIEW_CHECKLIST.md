# Review Checklist cho VBSP-SCM

## Mục tiêu review

Review trong repo này phải ưu tiên:

- bug mới
- regression nghiệp vụ
- sai số liệu
- sai role / sai quyền
- sai cache / snapshot / audit
- rủi ro bảo mật

## Checklist bắt buộc

- Có sửa đúng file nguồn gốc của vấn đề chưa, hay chỉ vá UI
- Có phát sinh bug mới cho role khác không
- Có làm sai số liệu HSTD / NQ11 / GQVL / CDTOTKVV không
- Có đổi behavior ngoài phạm vi yêu cầu không
- Có duplicate logic thay vì tái dùng service/helper hiện có không
- Có hardcode role, cột, đường dẫn, PGD, key không
- Có phá format tiền tệ hoặc đơn vị hiển thị không
- Có quên `db.ghi_audit()` cho thao tác ghi không
- Có quên `st.cache_data.clear()` hoặc dọn cache liên quan không
- Có thể làm stale `cache/*.parquet` không
- Có ảnh hưởng `hstd_snapshot` hoặc các tab so sánh kỳ không
- Có ảnh hưởng Telegram hoặc job health check không
- Có xử lý lỗi và log đủ ngữ cảnh không

## Checklist theo lớp

### Tab/UI

- Widget key có unique chưa
- `render(tab=None, **kwargs)` có còn hoạt động standalone không
- `kwargs` có truyền đủ role, username, pgd_user không
- Có dùng formatter sai chỗ làm hỏng kiểu dữ liệu không

### Service

- Có giữ service là nơi chứa nghiệp vụ không
- Có thêm side effect mới không được nêu rõ không
- Có thêm write path nhưng thiếu audit/log không

### Data/DB

- Có dùng `db.get_conn()` thay vì kết nối thô không
- Có dùng key `kv_store` đúng pattern không
- Có giữ backward compatibility với dữ liệu cũ không

### Security

- Có lộ secret hoặc token trong code/log không
- Có mở rộng quyền không chủ ý không
- Có bỏ qua validation upload/path không

### Performance

- Có thêm vòng lặp DataFrame lớn không
- Có tăng số lần đọc Excel hoặc đọc DB không cần thiết không
- Có làm tăng re-run Streamlit không

## Kiểm tra rollback

- Nếu revert thay đổi này thì dữ liệu có cần migrate ngược không
- Nếu lỗi xảy ra giữa chừng thì hệ thống có ở trạng thái nửa vời không
- Nếu merge hoặc ghi kv lỗi, audit/log có phản ánh đúng không

## Kết luận review nên trả về

- Finding theo mức độ
- File/khối bị ảnh hưởng
- Rủi ro chính
- Test còn thiếu
- Có nên merge ngay hay chưa
