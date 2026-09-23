# DELTA — VBSP-SCM
> Cập nhật sau mỗi lần hoàn thành tính năng (Trae tự append).
> Khi file > 200 dòng: gộp phần stable vào STABLE.md, xóa khỏi đây.
> **Entry cũ (≤ 2026-06-15):** xem `_archive/DELTA_2026-07-25.md`

---

## [2026-09-23] — Hoàn thiện Tab Tra cứu Khách hàng v3 (đợt cuối)

Hoàn tất các task còn lại của kế hoạch `.codex/prompts/tracuu_khach_hang_v3.md`:

### `tabs/tab_tracuu_v2.py`
- **Preset cột (3.3):** selectbox `Cơ bản / Đến hạn / Quá hạn / NQ11-GQVL / Huy động / Khoanh nợ / Tùy chỉnh` (`_COLUMN_PRESETS`); mở rộng `_VIEW_CATALOG` thêm Lãi tồn QH, Dư nợ khoanh, Mức vay, Ngày HH khoanh, Số lần GH, Mã NĐT.
- **Sắp xếp mặc định (3.3):** `_sort_mac_dinh()` — Dư nợ QH DESC, Tổng dư nợ DESC; map dòng dùng `df_tab` (đã sort) nhất quán với `df_view`.
- **Mask PII khi xuất (3.6):** `_mask_df_pii()` che CMND/SĐT trên Excel; thêm sheet `Ghi_chu_bao_mat` (người xuất, thời điểm, số dòng, trạng thái mask). Excel chuyển sang lazy callable.
- **Biểu đồ đính kèm PDF (3.7):** tách `_build_charts()` trả `list[(fig, title)]` → truyền `figs=` vào `xuat_pdf_co_chart`; `_render_charts()` dùng lại.
- **Whitelist NQ11/GQVL (C6):** `_render_chi_tiet_phu()` chỉ hiện ≤12 cột theo whitelist, tránh tràn dialog.

### `components/filter_panel.py`
- **💾 Lưu bộ lọc (A10):** bật nút (bỏ `disabled=True`). `_render_save_filter()` — Lưu/Áp/Xóa qua `db.ghi_kv` + `db.ghi_audit("luu_bo_loc_tra_cuu")`. `_snapshot_filters()`/`_restore_filters()`/`_apply_saved_filters()` tuần tự hóa date↔isoformat, tuple↔list; áp bằng cách xóa widget key `tc_*` rồi rerun.
- Selectbox `Đến hạn trong N ngày` / `Khoanh sắp hết hạn` đọc `index` từ dict `tracuu_filters` (khôi phục đúng khi Áp/Reset).

### `tests/test_tracuu_search.py`
- Thêm 4 test: `_mask_df_pii`, `_sort_mac_dinh`, snapshot/restore filter round-trip (tổng 11 test, pass).

### Docs
- `CODE_INDEX.md` / `TEST_COVERAGE.md`: bỏ ref `tab_tracuu.py` (v1 đã xóa), cập nhật v2 + filter_panel.

> **Còn hoãn (không thuộc nghiệm thu, nặng/rủi ro):** chip bộ lọc đang áp (3.2), filter+hiển thị CBTD phụ trách (D6), mode "Thẻ chi tiết" (3.4), highlight dòng QH/khoanh (3.3), debug timing (2.7), hợp nhất `_normalize_search_text` vào `utils.py` (4.2).

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
