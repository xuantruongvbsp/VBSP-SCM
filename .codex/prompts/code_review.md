# Prompt code review diff

Bạn đang review diff trong `VBSP-SCM`.

Ưu tiên chính:

- correctness
- regression nghiệp vụ
- role và phân quyền
- cache / parquet / snapshot
- audit / logging
- performance
- security

Yêu cầu:

1. Đọc diff và các file phụ thuộc trực tiếp.
2. Đưa findings trước, ngắn gọn và có căn cứ.
3. Chỉ nêu summary sau khi đã liệt kê findings.
4. Nếu không có findings, nói rõ điều đó và nêu testing gap còn lại.
