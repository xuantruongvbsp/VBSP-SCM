# Checklist hiệu năng cho VBSP-SCM

## Trục hiệu năng chính của repo

- pandas trên tập HSTD lớn
- parquet cache trong `cache/`
- DuckDB đọc parquet
- Streamlit rerun và cache
- I/O Excel nhiều file từ `pgd_data/`
- snapshot và các truy vấn SQLite tổng hợp

## Quy tắc tối ưu

- Ưu tiên đọc parquet thay vì đọc Excel lặp lại.
- Nếu có thể filter ở lớp query/read thì không đọc full rồi mới lọc.
- Tôn trọng `@st.cache_data` và `@st.cache_resource`.
- Không xóa cache toàn cục nếu chỉ cần invalidation hẹp.
- Tránh groupby lặp lại trong nhiều tab nếu cùng một kết quả có thể tái dùng.
- Tránh `DataFrame.apply` theo dòng trên dữ liệu lớn khi có vectorized alternative.

## Pandas

- Chuẩn hóa dtype sớm khi load dữ liệu lớn.
- Chỉ copy DataFrame khi thực sự cần.
- Không format string sớm nếu sau đó còn tính toán.
- Giảm merge/join dư thừa giữa HSTD và các bảng phụ.

## Parquet và DuckDB

- `app.py` đang dùng DuckDB + parquet cho HSTD và NQ11, nên tối ưu theo hướng đó trước.
- Khi sửa query, cân nhắc filter ngay trong SQL.
- Không đổi tên hoặc cấu trúc cache parquet mà không kiểm các caller.
- Nếu thấy lỗi hiệu năng ở tab, kiểm tra dữ liệu đã được lấy từ cache parquet hay chưa.

## Streamlit

- Giảm số component nặng trong một lần render.
- Tránh import nặng hoặc load file nặng trong mỗi lần tab rerun.
- Dùng lazy import hoặc lazy tabs khi pattern hiện có đã áp dụng.
- Không nhét DataFrame lớn vào `st.session_state`.

## Thread và đồng bộ

- Upload/merge dùng lock ở service để tránh tranh chấp.
- Không thêm thread mới nếu không nắm rõ tác động với SQLite, file I/O và Streamlit state.
- Nếu cần song song, ưu tiên đọc nhiều nguồn độc lập và tránh đụng chung connection hoặc file ghi.

## I/O

- Hạn chế đọc nhiều file Excel giống nhau trong cùng một flow.
- Với dữ liệu `pgd_data/{slug}/`, quét trạng thái nhanh trước khi đọc full file.
- Khi tạo báo cáo, chỉ xuất phần dữ liệu đã lọc cần thiết.

## Snapshot và SQLite

- Truy vấn snapshot nên theo kỳ và index logic đã có.
- Tránh truy vấn lặp nhiều lần cùng một dữ liệu snapshot trong một render.
- Nếu thêm truy vấn tổng hợp mới, cân nhắc cache ngắn hạn ở `@st.cache_data`.

## Dấu hiệu cần tối ưu

- tab mở chậm sau upload hoặc merge
- CPU cao khi đổi filter
- rerun làm đọc lại Excel
- cùng một service bị gọi lặp nhiều lần mỗi render
- bảng lớn bị format từng ô nhiều lần

## Mục tiêu khi Codex tối ưu

- Không đổi behavior nghiệp vụ
- Có số đo trước và sau nếu có thể
- Nêu rõ trade-off cache, memory, độ phức tạp code
