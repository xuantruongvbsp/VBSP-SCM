# DELTA — VBSP-SCM
> Cập nhật sau mỗi lần hoàn thành tính năng (Trae tự append).
> Khi file > 200 dòng: gộp phần stable vào STABLE.md, xóa khỏi đây.
> **Entry cũ (≤ 2026-06-15):** xem `_archive/DELTA_2026-07-25.md`

---

## [2026-07-25] — Tự động hóa documentation & convention checker

### `scripts/gen_code_index.py` — tạo mới
- Tự sinh `CODE_INDEX.md` từ AST: quét hàm public + docstring trong tabs/, services/, data/, components/, workspaces/
- Chạy: `venv/Scripts/python.exe scripts/gen_code_index.py`
- Chạy lại sau khi thêm file mới để index luôn cập nhật

### `scripts/check_conventions.py` — mở rộng
- Rule 11: phát hiện `from config import *` (wildcard import)
- Rule 12: widget thiếu `key=` trong tabs/ (chống DuplicateElementKey)
- Skip `.venv*` directories
- Chạy: `venv/Scripts/python.exe scripts/check_conventions.py`

### Tài liệu tối ưu token
- `CODE_INDEX.md` — tự sinh, map chức năng → file → hàm (đọc khi cần tìm file sửa)
- `COT_REF.md` — danh sách COT_* constants (đọc khi cần tên cột)
- `SIGNATURES.md` — function signatures (đọc khi cần gọi hàm)
- `.trae/rules/rules.md` — < 10,000 ký tự (core rules luôn load)
- `AGENTS.md` — tóm tắt quy tắc + bảng tra (đọc khi cần overview)

---

## [2026-07-25] — Tách UI tab Tiến độ nộp BC
- `tabs/tab_tien_do_nop_settings.py` — Cài đặt thời hạn
- `tabs/tab_tien_do_nop_manual.py` — Đánh dấu thủ công
- `tabs/tab_tien_do_nop_archive.py` — Đã lưu trữ
- `tabs/tab_tien_do_nop.py` — giảm trách nhiệm UI chi tiết
