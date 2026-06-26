# Prompt viết test

Bạn đang viết test cho `VBSP-SCM`.

Yêu cầu:

1. Xác định behavior cần bảo vệ.
2. Chọn mức test phù hợp: unit, integration nhỏ, smoke.
3. Tái dùng pattern trong `tests/conftest.py`.
4. Ưu tiên test cho service hoặc helper thuần.
5. Nếu phải mock, chỉ mock phần biên như Streamlit, DB hoặc external service.

Không viết test:

- chỉ lặp lại implementation detail
- phụ thuộc dữ liệu lớn không cần thiết
- quá UI-centric nếu logic thật nằm ở service

Trước khi xong, nêu:

- bug/regression nào test đang chặn
- vì sao test này đáng có
