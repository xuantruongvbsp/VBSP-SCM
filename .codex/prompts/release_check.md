# Prompt kiểm tra trước release

Bạn đang kiểm tra trước release hoặc merge cho `VBSP-SCM`.

Checklist:

1. Có đổi behavior ngoài phạm vi không.
2. Có ảnh hưởng role CN/PGD không.
3. Có ảnh hưởng upload, merge, cache parquet, snapshot không.
4. Có quên audit, logging, clear cache không.
5. Có rủi ro bảo mật không.
6. Có test hoặc smoke phù hợp không.

Yêu cầu:

- Trả kết quả theo dạng checklist pass/fail.
- Nêu blocking issue trước.
- Nêu residual risk nếu còn.
