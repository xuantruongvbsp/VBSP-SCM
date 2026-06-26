# Prompt refactor

Bạn đang refactor `VBSP-SCM`.

Nguyên tắc:

- Không đổi behavior.
- Không đổi output nghiệp vụ.
- Không đổi key `kv_store`, schema DB, quyền, cache, snapshot nếu không có yêu cầu rõ.

Thứ tự làm việc:

1. Chỉ ra đoạn code đang trùng lặp hoặc khó bảo trì.
2. Chỉ ra file và caller bị ảnh hưởng.
3. Nêu vì sao refactor này an toàn.
4. Chỉ refactor trong phạm vi nhỏ, có thể review dễ.
5. Đề xuất test hoặc smoke check phù hợp.
