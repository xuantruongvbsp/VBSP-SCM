# Debug Guide cho Codex

## Nguyên tắc debug

- Đọc luồng thật trước khi sửa.
- Xác định lỗi xuất phát từ dữ liệu, cache, role, service hay UI.
- Không kết luận từ một tab duy nhất; nhiều tab cùng dùng chung service hoặc cache.

## Luồng debug tổng quát

```text
Mô tả lỗi
  ↓
Xác định role / workspace / tab bị ảnh hưởng
  ↓
Đọc tab render
  ↓
Đọc service liên quan
  ↓
Đọc data / db / config / snapshot / cache nếu có
  ↓
Tái hiện điều kiện lỗi
  ↓
Khoanh nguyên nhân gốc
  ↓
Đề xuất sửa tối thiểu
```

## Checklist theo lớp

### 1. app.py

- Có load đúng parquet không
- Có enrich đúng `__is_nq11`, `__is_gqvl` không
- Có route đúng workspace theo role không
- Có truyền đủ `role`, `username`, `pgd_user`, `df`, `df_full` không

### 2. workspaces

- Có import đúng tab không
- Có `kwargs.setdefault("role", role)` và `kwargs.setdefault("username", username)` không
- Có gọi đúng tab cho role CN/PGD không
- Có lazy import gây che lỗi import module không

### 3. tabs

- Tab lấy dữ liệu từ `kwargs` hay tự đọc lại
- Có dùng `st.session_state` sai hoặc thiếu fallback không
- Có format chuỗi làm hỏng dữ liệu tính toán không
- Có widget key trùng khi `pgd_mode=True` không

### 4. services

- Logic ghi có qua service chuẩn chưa
- Có quên clear cache sau ghi thành công không
- Có quên audit không
- Có lock hoặc retry liên quan không

### 5. data / parquet / file runtime

- File gốc có tồn tại không
- File `pgd_data/{slug}/` có đúng đơn vị không
- Cache parquet có stale không
- Timestamp file có thay đổi như kỳ vọng không

### 6. snapshot

- Lỗi số liệu lịch sử có liên quan `hstd_snapshot` không
- Kỳ snapshot có suy ra đúng từ `COT_NGAY_SL` không
- Có thiếu snapshot khi merge hay xóa cache không

### 7. UI

- UI sai số liệu hay chỉ sai format
- Sai role gating hay sai dữ liệu nền
- Có bị lỗi vì formatter Việt hóa chuỗi quá sớm không

## Checklist riêng cho Upload

```text
tab_upload_*
  ↓
upload_service.py
  ↓
data quality
  ↓
ghi file
  ↓
merge_du_lieu_toan_cn()
  ↓
parquet cache
  ↓
snapshot
  ↓
audit + telegram
  ↓
tab tiêu thụ dữ liệu
```

## Checklist riêng cho lỗi Dashboard

- Dashboard đọc từ HSTD, NQ11, GQVL hay snapshot
- Số liệu sai ở một card hay toàn bộ
- Sai vì filter role/PGD hay sai nguồn dữ liệu
- Có formatter `fmt_ty()` làm hiểu nhầm đơn vị không

## Checklist riêng cho lỗi Merge

- File nguồn từng PGD có đúng format không
- Merge lock có hoạt động không
- Cache parquet đã bị xóa/ghi lại chưa
- `merge_meta_{loai}` có cập nhật không
- Snapshot có trigger đúng sau merge HSTD không

## Checklist riêng cho lỗi Security

- Timeout session
- IP whitelist
- 2FA cho admin
- Secret/token có bị log ra ngoài không
- `st.session_state` có bị reset sai không

## Điều Codex phải báo cáo sau khi debug

- File đã đọc
- Nơi phát sinh lỗi đầu tiên
- Nơi lan ra UI
- Cách tái hiện
- Cách sửa tối thiểu
- Rủi ro phụ và cách verify
