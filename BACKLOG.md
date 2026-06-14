# Backlog

Ghi lại các yêu cầu/user feedback của người dùng để tiện theo dõi.

## ✅ Đã hoàn thành — 2026-06-15 (Telegram notification)

- [x] Tạo `services/telegram_service.py` — push notification 1 chiều qua Telegram Bot API (không cần thư viện mới)
- [x] Hook gửi tóm tắt số liệu sáng vào `scripts/daily_report.py`
- [x] `test_telegram.py` — file test double-click cho người dùng cuối

## ✅ Đã hoàn thành — 2026-05-30 (refactor CDTOTKVV)

- [x] Rà soát `except Exception` còn lại trong `tab_tongquan.py` — sửa `pass` thành `st.caption()` cảnh báo; các chỗ khác đã có `st.error()` hoặc fallback hợp lý
- [x] Kiểm tra toàn project các `except Exception:` dùng biến chưa khởi tạo → NameError ẩn — đã fix `suffix` trong `upload_service.py`; các chỗ khác dùng `as e` an toàn
- [x] Tách logic load CDTOTKVV ra `services/tongquan_cdto_service.py` — giảm ~60 dòng trong `tab_tongquan.py`
- [x] Thêm unit test smoke cho pipeline CDTOTKVV — `tests/test_tongquan_cdto_service.py` (10 tests)
- [x] Thêm badge trạng thái CDTOTKVV trong tab Tổng quan (✅/⚠️/ℹ️ giống badge HSTD)
- [x] Thống nhất `tab_tongquan.py` + `tab_cdtotkvv.py` dùng chung service `load_cdto_toan_cn()`
- [x] Health-check CDTOTKVV sau merge: card + badge "⚠️ Thiếu X PGD" thay vì ẩn card

## ✅ Đã hoàn thành — trước đó

- [x] Tạo tab "Nội bộ Phòng KH-NV" (tab_khnv_noi_bo.py) — 4 sub-tab — 2026-05-20
- [x] Fix lỗi "category type does not support sum operations" lần 4 (COT_DU_NO_QH sót + astype(object)) — 2026-05-20
- [x] Fix lỗi "category type does not support sum operations" lần 3 (tận gốc): bỏ hasattr, dùng pd.to_numeric không điều kiện — 2026-05-20
- [x] Đổi đơn vị KPI "3 tháng không hoạt động" từ triệu → đồng — 2026-05-20
- [x] Fix lỗi "category type does not support sum operations" ở tab Tổng quan — 2026-05-20
- [x] Fix lỗi "cannot subtract DatetimeArray from Categorical" ở Sức khỏe tín dụng — 2026-05-20
- [x] Fix lỗi Tổng Quan Chi Nhánh trắng do duckdb RecordBatchReader — 2026-05-20
- [x] Fix tổng hợp thủ công chậm/treo: string cleanup 27s → 0.7s — 2026-05-20
- [x] Fix card Xếp loại Tổ TK&VV không hiện sau upload CDTOTKVV toàn CN — 2026-05-30
- [x] Upload CDTOTKVV toàn CN: 1 file tổng hợp → tự tách 22 PGD — 2026-05-30
