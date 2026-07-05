# Kế hoạch nâng cấp chức năng báo cáo từ Phòng giao dịch

> Cập nhật: 2026-07-03
> Phạm vi ưu tiên: luồng `PGD nộp báo cáo về Chi nhánh`

---

## 1. Mục tiêu

Hoàn thiện và nâng cấp chức năng báo cáo từ Phòng giao dịch theo hướng:

- Ổn định luồng tiếp nhận báo cáo từ Google Form / Google Sheets.
- Chuẩn hóa logic trạng thái nộp báo cáo giữa UI và Telegram Scheduler.
- Tăng khả năng quản trị danh mục báo cáo, deadline, override thủ công.
- Tạo dashboard điều hành rõ ràng cho Chi nhánh.
- Chuẩn bị nền kỹ thuật để mở rộng sau này mà không phải sửa lại toàn bộ tab.

---

## 2. Phạm vi của kế hoạch

### 2.1 Trong phạm vi

Luồng `PGD nộp báo cáo về CN`, bao gồm:

- Đọc dữ liệu nộp báo cáo từ Google Sheets.
- Chuẩn hóa tên PGD và loại báo cáo.
- Cấu hình deadline theo loại báo cáo.
- Phân loại trạng thái `đúng hạn / trễ / chưa nộp / đã nộp chưa cấu hình deadline`.
- Đánh dấu thủ công và ghi đè trạng thái khi cần.
- Nhắc hạn qua Telegram.
- Dashboard tổng quan và danh sách chi tiết tại tab `Tiến độ nộp BC`.

### 2.2 Ngoài phạm vi đợt này

Các màn hình `PGD tự xuất báo cáo nghiệp vụ` từ dữ liệu HSTD/NQ11/GQVL như:

- `tabs/tab_bao_cao_giao_ban_pgd.py`
- `tabs/tab_bao_cao_dinh_ky.py`
- Các báo cáo nghiệp vụ trong `workspaces/ws_operation.py`

Nhóm này chỉ rà soát dependency, chưa đưa vào triển khai đợt hiện tại để tránh lan phạm vi.

---

## 3. Hiện trạng kỹ thuật

## 3.1 File chính đang tham gia

- `tabs/tab_tien_do_nop.py`: UI theo dõi, deadline, matrix trạng thái, export.
- `scripts/nhac_deadline.py`: scheduler gửi nhắc hạn Telegram.
- `services/telegram_service.py`: lưu allowlist và gửi Telegram.
- `db.py`: lưu `kv_store`.
- `workspaces/ws_management.py`: mount tab phía CN.

## 3.2 Key dữ liệu đang dùng

- `bao_cao_deadline_config`
- `manual_nop_tdn`
- `telegram_deadline_bc_allowlist`

## 3.3 Điểm yếu hiện tại

- Logic đọc GSheet, chuẩn hóa dữ liệu và phân loại trạng thái đang bị lặp giữa UI và scheduler.
- `tab_tien_do_nop.py` đang ôm quá nhiều việc, khó bảo trì và khó test.
- Rủi ro vận hành còn lớn ở `credentials.json`, quyền Service Account, quota hoặc lỗi Google Sheets tạm thời.
- Danh mục loại báo cáo thay đổi có thể gây stale config cho deadline hoặc allowlist Telegram.
- Chưa có service domain riêng cho vòng đời báo cáo PGD.

---

## 4. Mục tiêu đầu ra sau khi hoàn thiện

Sau khi triển khai xong, hệ thống cần đạt:

- Một nguồn logic thống nhất cho trạng thái báo cáo PGD.
- UI và Telegram cho cùng một kết quả trên cùng dữ liệu.
- Dễ thêm loại báo cáo mới mà không phải sửa nhiều nơi.
- Có nhật ký thao tác thủ công rõ ràng.
- Có dashboard tổng hợp cho Chi nhánh theo PGD, loại báo cáo và kỳ theo dõi.
- Có cơ chế phát hiện sớm lỗi nguồn dữ liệu GSheet.

---

## 5. Kiến trúc đề xuất

Tạo service mới:

- `services/report_submission_service.py`

Service này là nơi duy nhất xử lý:

- Đọc dữ liệu từ Google Sheets.
- Chuẩn hóa cột và tên PGD.
- Đọc deadline config.
- Đọc manual override.
- Tính trạng thái nghiệp vụ.
- Sinh ma trận tổng hợp cho UI.
- Sinh danh sách cần nhắc Telegram.
- Kiểm tra dữ liệu lỗi hoặc bất thường.

Phân vai sau khi refactor:

- `tabs/tab_tien_do_nop.py`: chỉ render UI, gọi service lấy dữ liệu đã xử lý.
- `scripts/nhac_deadline.py`: chỉ gọi service để lấy danh sách cần nhắc.
- `services/telegram_service.py`: chỉ lo cấu hình Telegram và gửi tin.

---

## 6. Lộ trình triển khai

## Phase 0 - Chốt rule nghiệp vụ

Mục tiêu:

- Chốt chính xác trạng thái nào được coi là `đúng hạn`, `trễ`, `chưa nộp`, `đã nộp`.
- Chốt rõ logic khi `có nộp nhưng chưa khai deadline`.
- Chốt rõ override thủ công có ghi đè hoàn toàn hay chỉ là ghi chú bổ sung.
- Chốt rõ Telegram có nhắc lại báo cáo đã nộp trễ hay không.

Đầu ra:

- Bộ rule nghiệp vụ thống nhất dùng chung cho UI và scheduler.

## Phase 1 - Tách service lõi

Mục tiêu:

- Tạo `services/report_submission_service.py`.
- Di chuyển logic cốt lõi ra khỏi `tabs/tab_tien_do_nop.py`.
- Loại bỏ trùng lặp với `scripts/nhac_deadline.py`.

Hàm dự kiến:

- `doc_du_lieu_nop_bao_cao()`
- `doc_deadline_bao_cao()`
- `doc_manual_override_bao_cao()`
- `chuan_hoa_du_lieu_bao_cao(df)`
- `gan_trang_thai_bao_cao(df, deadline_map, manual_map)`
- `tao_ma_tran_tien_do(df_status, deadline_map)`
- `lay_danh_sach_can_nhac(df_status, deadline_map, allowlist=None)`
- `kiem_tra_suc_khoe_nguon_bao_cao()`

Đầu ra:

- UI và scheduler cùng gọi chung một service.

## Phase 2 - Nâng cấp UI `Tiến độ nộp BC`

Mục tiêu:

- Tách UI thành các khối rõ ràng hơn.
- Giảm file `tab_tien_do_nop.py` về đúng vai trò render.
- Tăng khả năng quản trị mà không gây rối thao tác.

Hạng mục:

- Khối `Sức khỏe nguồn dữ liệu`: credentials, kết nối, số dòng hợp lệ, lần cập nhật gần nhất.
- Khối `Cài đặt deadline`: thêm/sửa/xóa loại báo cáo an toàn.
- Khối `Danh mục báo cáo đang theo dõi`: tránh lẫn với dữ liệu submit thật.
- Khối `Tổng quan điều hành`: KPI, top PGD trễ, loại báo cáo quá hạn nhiều.
- Khối `Danh sách nộp`: lọc theo PGD, trạng thái, loại báo cáo, thời gian.
- Khối `Override thủ công`: lưu lý do, người thao tác, thời điểm thao tác.

Đầu ra:

- Màn hình rõ vai trò, dễ vận hành, dễ giải thích cho người dùng cuối.

## Phase 3 - Đồng bộ Telegram và cảnh báo

Mục tiêu:

- Cho Telegram dùng đúng kết quả tính từ service chung.
- Tránh trường hợp UI đúng nhưng tin nhắn sai.

Hạng mục:

- Chuẩn hóa payload nhắc hạn.
- Kiểm tra `allowlist` stale trước khi gửi.
- Ghi log rõ khi GSheet lỗi hoặc dữ liệu rỗng bất thường.
- Cân nhắc cảnh báo riêng khi scheduler bỏ qua lượt nhắc do lỗi nguồn.

Đầu ra:

- Telegram nhắc đúng, dễ debug, không âm thầm bỏ sót.

## Phase 4 - Báo cáo điều hành và theo dõi xu hướng

Mục tiêu:

- Tăng giá trị quản trị cho Chi nhánh, không chỉ dừng ở xem danh sách nộp.

Hạng mục:

- Tỷ lệ đúng hạn theo PGD.
- Tỷ lệ đúng hạn theo loại báo cáo.
- Lịch sử 3-6 kỳ gần nhất.
- Danh sách PGD nộp trễ lặp lại.
- Danh sách loại báo cáo thường xuyên quá hạn.
- Export Excel/PDF từ cùng nguồn dữ liệu đã chuẩn hóa.

Đầu ra:

- Có dashboard điều hành và tài liệu tổng hợp phục vụ họp/giao ban.

---

## 7. Backlog ưu tiên

### P0 - Bắt buộc làm trước

1. Tạo `services/report_submission_service.py`.
2. Gom logic đọc GSheet, deadline, override và phân loại trạng thái về một chỗ.
3. Cho `scripts/nhac_deadline.py` dùng service chung.
4. Thêm health-check nguồn dữ liệu GSheet.
5. Chuẩn hóa phản ứng khi dữ liệu nguồn lỗi hoặc rỗng.

### P1 - Nên làm ngay sau P0

1. Tái cấu trúc `tabs/tab_tien_do_nop.py` thành các khối render nhỏ.
2. Bổ sung nhật ký override thủ công đầy đủ hơn.
3. Thêm bộ lọc mạnh hơn cho danh sách nộp báo cáo.
4. Thêm KPI điều hành tại màn `Tổng quan`.
5. Chuẩn hóa export Excel/PDF dùng chung nguồn dữ liệu đã xử lý.

### P2 - Mở rộng sau khi ổn định

1. Lịch sử xu hướng theo tháng/kỳ.
2. Xếp hạng PGD theo độ tuân thủ deadline.
3. Dashboard theo loại báo cáo.
4. Cảnh báo bất thường khi một kỳ không có dữ liệu nộp mới.
5. Hợp nhất dần với checklist báo cáo nếu nghiệp vụ xác nhận cần một hệ thống chung.

---

## 8. Mapping file triển khai

| File | Vai trò trong kế hoạch |
|---|---|
| `services/report_submission_service.py` | Service lõi mới cho toàn bộ logic báo cáo PGD |
| `tabs/tab_tien_do_nop.py` | Giảm về vai trò render UI và gọi service |
| `scripts/nhac_deadline.py` | Dùng service chung để lấy danh sách cần nhắc |
| `services/telegram_service.py` | Giữ vai trò config và sender |
| `db.py` | Tái dùng kv_store; chỉ bổ sung helper nếu thật sự cần |
| `BACKLOG.md` | Theo dõi thứ tự triển khai |
| `CHANGELOG.md` | Ghi nhận từng đợt thay đổi |
| `BUGMAP.md` | Bổ sung bug mới nếu phát sinh trong lúc refactor |

---

## 9. Tiêu chí nghiệm thu

Đợt nâng cấp được coi là đạt khi:

- UI và Telegram cho cùng một kết quả trên cùng tập dữ liệu.
- Không còn lặp logic phân loại trạng thái giữa tab và script.
- Có thể thêm một loại báo cáo mới chỉ bằng cấu hình deadline/danh mục, không cần sửa nhiều file.
- Có thể truy ra ai override thủ công, lúc nào, vì lý do gì.
- Khi GSheet lỗi hoặc rỗng bất thường, hệ thống hiện cảnh báo rõ thay vì im lặng.
- Các file thay đổi qua được compile/convention check theo chuẩn dự án.

---

## 10. Thứ tự triển khai đề xuất

Để an toàn và ít rủi ro nhất, nên làm theo 2 đợt:

### Đợt 1 - Ổn định logic

- Phase 0
- Phase 1
- Phần lõi của Phase 3

### Đợt 2 - Nâng cấp trải nghiệm và quản trị

- Phase 2
- Phase 4

Lý do:

- Nếu chưa gom logic chung mà làm UI trước, sẽ chỉ đẹp hơn chứ chưa chắc đúng hơn.
- Nếu chưa xử lý lỗi nguồn dữ liệu, Telegram vẫn có nguy cơ nhắc sai hoặc bỏ sót.

---

## 11. Gợi ý chia task thực thi

### Task 1

- Tạo service mới và di chuyển logic đọc/chuẩn hóa dữ liệu.

### Task 2

- Di chuyển logic trạng thái và ma trận tiến độ sang service.

### Task 3

- Refactor `scripts/nhac_deadline.py` sang dùng service chung.

### Task 4

- Refactor UI `tab_tien_do_nop.py` thành các block render nhỏ.

### Task 5

- Bổ sung KPI quản trị, log override và health-check nguồn dữ liệu.

### Task 6

- Bổ sung test/regression cho rule trạng thái và danh sách nhắc hạn.

---

## 12. Kết luận

Kế hoạch này ưu tiên sửa tận gốc phần `logic nghiệp vụ` trước, sau đó mới nâng cấp phần `giao diện và trải nghiệm quản trị`.

Nếu bám đúng lộ trình trên, chức năng báo cáo từ Phòng giao dịch sẽ:

- Dễ bảo trì hơn
- Dễ mở rộng hơn
- Ít lệch logic hơn
- An toàn hơn khi vận hành thật
