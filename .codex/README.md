# .codex cho VBSP-SCM

Thư mục `.codex/` là bộ tài liệu nội bộ dành riêng cho Codex và các AI coding agent làm việc trong `VBSP-SCM`.

Mục tiêu của bộ này:

- Giúp Codex hiểu đúng kiến trúc thực tế của dự án trước khi phân tích hay sửa code.
- Giữ cách làm việc nhất quán với quy ước đang có trong `README.md`, `CONVENTIONS.md`, `docs/AGENTS.md`, `docs/ARCHITECTURE.md`.
- Giảm sửa sai phạm vi, giảm refactor thừa, giảm rủi ro phá audit, cache, snapshot, upload, quyền truy cập.
- Tạo sẵn các prompt theo tình huống để dùng hằng ngày.

## Dùng thế nào

Khi dùng Codex trong repo này:

1. Mở `.codex/CODEX.md` để nạp quy tắc nền.
2. Mở `.codex/ARCHITECTURE.md` để xác định đúng lớp liên quan: `app.py`, `workspaces/`, `tabs/`, `services/`, `data/`, `db.py`, `snapshot_service.py`, `security.py`.
3. Nếu đang xử lý lỗi hoặc yêu cầu cụ thể, chọn prompt trong `.codex/prompts/`.
4. Yêu cầu Codex đọc file liên quan trước khi đề xuất sửa.
5. Chỉ cho phép code sau khi đã có phân tích nguyên nhân, phạm vi file và rủi ro.

## Workflow chuẩn

```text
Chạy project
  ↓
Gặp lỗi / có yêu cầu mới
  ↓
Mở prompt phù hợp trong .codex/prompts/
  ↓
Codex đọc project và phân tích
  ↓
Codex đề xuất phạm vi sửa
  ↓
Codex sửa tối thiểu
  ↓
Review theo checklist
  ↓
Chạy lại app / test / smoke
```

## Chạy project

Môi trường làm việc hiện tại của dự án chủ yếu là Windows + Streamlit, nhưng CI chạy trên Ubuntu.

Lệnh chạy app:

```bash
streamlit run app.py
```

Các lệnh kiểm tra thường dùng:

```bash
pytest tests/ -q --tb=short
python -m compileall -q . -x ".venv|venv|__pycache__|\\.git"
python scripts/check_conventions.py --all
```

Nếu cần chạy nhanh trên máy nội bộ có thể dùng:

```bash
RUN_ALL_TEST.bat
Chay_VBSP_SCM.bat
run.bat
```

## Khi nào mở prompt nào

- `fix_bug.md`: lỗi nghiệp vụ hoặc lỗi runtime thông thường.
- `upload_debug.md`: lỗi ở upload, merge, cache parquet, dữ liệu đầu vào.
- `merge_debug.md`: sai số liệu sau merge toàn Chi nhánh.
- `snapshot_debug.md`: lỗi snapshot, số liệu so sánh kỳ, delta, heatmap.
- `review_changes.md` hoặc `code_review.md`: review diff.
- `add_feature.md`: thêm tính năng mới.
- `refactor.md`: dọn code nhưng không đổi behavior.
- `performance.md`: tối ưu tải dữ liệu, parquet, pandas, Streamlit.
- `security_review.md`: kiểm tra timeout, whitelist IP, 2FA, secret, upload path.
- `write_test.md`: viết hoặc cập nhật test.
- `release_check.md`: soát trước merge hoặc phát hành.
- `dashboard.md`, `telegram.md`, `cdtotkvv.md`, `nq11.md`, `gqvl.md`: dùng khi làm việc sâu với từng mảng.

## Phạm vi tài liệu này

Đây không phải tài liệu người dùng cuối. Nội dung ở đây ưu tiên:

- Kiến trúc kỹ thuật.
- Quy tắc sửa code an toàn.
- Luồng debug.
- Checklist review, test, release.
- Prompt làm việc chuẩn cho Codex.
