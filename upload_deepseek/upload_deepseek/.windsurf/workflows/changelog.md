---
description: Tự động cập nhật CHANGELOG.md sau mỗi lần apply code changes
---

# CHANGELOG Auto-Update Workflow

## Mục đích
Tự động ghi lại các thay đổi code vào `docs/CHANGELOG.md` sau mỗi lần apply.

## Quy tắc ghi CHANGELOG

### 1. Thời điểm ghi
- **BẮT BUỘC** sau mỗi lần apply changes thành công
- Ngay sau khi confirm code chạy được (không lỗi syntax)
- Trước khi chuyển sang task khác

### 2. Format chuẩn
```markdown
## [YYYY-MM-DD] — <mô tả ngắn gọn>
- `filename.py` dòng ~X — mô tả thay đổi cụ thể
- `filename2.py` — mô tả thay đổi
- **Kết quả:** (nếu có impact rõ ràng)
```

### 3. Vị trí ghi
- Thêm vào **đầu file** (ngay sau dòng `# CHANGELOG — VBSP-SCM`)
- Không xóa entry cũ
- Các entry cùng ngày nên nhóm lại hoặc để riêng tùy mức độ liên quan

### 4. Nội dung cần ghi
- **Tên file** đã sửa (đường dẫn tương đối từ root)
- **Dòng số** (ước tính)
- **Mô tả ngắn** (1 dòng, không quá dài)
- **Impact** (nếu đáng kể: tốc độ, UX, bug fix...)

### 5. Loại thay đổi nào cần ghi
- ✅ Feature mới
- ✅ Bug fix
- ✅ Refactor/Tối ưu hiệu năng
- ✅ UI/UX improvements
- ✅ Thêm/sửa/xóa file
- ❌ Không ghi: typo fix, comment thêm/xóa, format lại code

### 6. Ví dụ đúng
```markdown
## [2026-05-09] — Tối ưu cache trong tab Tổng quan
- `tabs/tab_tongquan.py` dòng ~85 — thêm `_cache_datetime_denhan()` cache `pd.to_datetime()`
- `tabs/tab_tongquan.py` dòng ~99 — thêm `_cache_bang_denhan()` cache `groupby()`
- **Kết quả:** Giảm thời gian load từ 2s xuống 200ms
```

## Script kiểm tra (tùy chọn)
```python
# check_changelog.py - Chạy để kiểm tra format
import re

with open('docs/CHANGELOG.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Kiểm tra format ngày
pattern = r'## \[(\d{4}-\d{2}-\d{2})\] — (.+)'
dates = re.findall(pattern, content)
print(f"Found {len(dates)} entries")
for date, desc in dates[:5]:
    print(f"  [{date}] {desc}")
```

## Checklist sau khi apply changes
- [ ] Code chạy không lỗi (syntax check)
- [ ] Thêm entry vào CHANGELOG.md
- [ ] Format đúng chuẩn
- [ ] Đặt ở đầu file

## Lưu ý
- **KHÔNG** để lâu rồi mới ghi — dễ quên chi tiết
- **KHÔNG** ghi chung chung như "sửa lỗi" — phải rõ file và dòng
- **CÓ THỂ** nhóm nhiều thay đổi liên quan vào 1 entry
