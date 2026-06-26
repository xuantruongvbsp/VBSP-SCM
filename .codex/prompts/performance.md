# Prompt tối ưu hiệu năng

Bạn đang tối ưu hiệu năng cho `VBSP-SCM`.

Hãy phân tích:

1. Điểm nghẽn nằm ở pandas, parquet, DuckDB, SQLite, Streamlit rerun, file I/O hay render UI.
2. File nào đang đọc lại dữ liệu quá nhiều.
3. Có thể dùng cache hiện có tốt hơn không.
4. Có thể giảm copy DataFrame, groupby lặp, format sớm không.

Yêu cầu:

- Đưa ra baseline nếu có.
- Ưu tiên giải pháp ít rủi ro nhất.
- Không đổi behavior, không phá cache invalidation.
- Nếu chạm upload/merge, kiểm tra lại snapshot và parquet.
