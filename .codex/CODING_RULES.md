# Coding Rules cho VBSP-SCM

## Quy tắc chung

- Ưu tiên type hint cho hàm mới hoặc hàm đang được sửa đáng kể.
- Giữ logging hiện có, thêm logging ở nhánh lỗi quan trọng.
- Không dùng magic string cho role, tên cột, đường dẫn, key dữ liệu khi đã có hằng số hoặc helper.
- Giữ tên biến và hàm bằng tiếng Việt không dấu nếu đó là convention của module hiện tại.
- Không tạo abstraction mới nếu chưa có lặp thực sự.

## Streamlit

- Tab mới hoặc tab sửa nên theo mẫu `render(tab=None, **kwargs)`.
- Dùng fallback container, không viết `with tab:` trực tiếp nếu có thể gọi standalone.
- Giảm re-run không cần thiết. Tránh đọc file lớn hoặc tính toán nặng ngay trong nhánh UI.
- Khi ghi dữ liệu thành công, kiểm tra có cần `st.cache_data.clear()` hay dọn `st.session_state` liên quan hay không.
- Tôn trọng `st.session_state` hiện có. Không xóa bừa toàn bộ state nếu không phải logout/reset rõ ràng.

## Session state

- Lấy role, username, `pgd_user` từ `kwargs` trước, fallback `st.session_state` sau.
- Không nhét dữ liệu lớn vào `st.session_state` nếu đã có cache/parquet/SQLite.
- Không dùng `session_state` thay cho `kv_store`.

## Pandas và dữ liệu

- Dùng `pd.to_numeric(..., errors="coerce")` khi chuẩn hóa số liệu đầu vào.
- Tránh chain dài khó debug trên DataFrame nghiệp vụ lớn.
- Khi lọc hoặc groupby, kiểm tra tên cột có đi qua `config.py` chưa.
- Nếu cần format để hiển thị, format ở lớp hiển thị hoặc bản copy, không phá kiểu dữ liệu của DataFrame dùng để tính toán.
- Với dữ liệu lớn, ưu tiên thao tác vectorized; tránh `apply` hàng dòng nếu có thể.

## Parquet và I/O

- Luồng đọc dữ liệu lớn ưu tiên parquet hơn đọc Excel lặp lại.
- Không tự tạo file cache mới ngoài pattern hiện có nếu chưa đánh giá invalidation.
- Khi sửa merge hoặc import, luôn nghĩ đến tính nhất quán giữa file gốc, parquet và cache Streamlit.

## SQLite, kv_store, audit

- Kết nối DB chỉ qua `db.get_conn()`.
- Dữ liệu runtime bền vững đi qua `db.doc_kv()` và `db.ghi_kv()`.
- Mọi thao tác ghi quan trọng phải có `db.ghi_audit()`.
- Không ghi file JSON cục bộ để thay thế `kv_store`.
- Không đổi key pattern đang dùng nếu chưa migrate toàn bộ caller.

## Exception handling

- Không nuốt lỗi im lặng trừ khi đó là chủ ý đã có sẵn trong module và đã log.
- Nếu bắt `Exception`, nên log đủ ngữ cảnh.
- Lỗi nghiệp vụ trả về thông báo cho UI nên rõ loại lỗi, không chung chung "có lỗi xảy ra".

## Naming

- Tên cột: lấy từ `config.py`.
- Role: dùng `normalize_role()`, `la_phan_he_cn()`, `la_phan_he_pgd()`.
- Đường dẫn PGD: dùng helper trong `data.pgd`.
- Key `kv_store`: bám pattern hiện có như `khtd_pgd_{slug}`, `merge_meta_{loai}`, `ct_registry_{slug}`.

## Logging

- Dùng logger theo module qua `get_logger(__name__)` nếu module đã theo pattern đó.
- Log phải có giá trị điều tra: kỳ, loại file, PGD, username, key, số dòng, trạng thái.
- Không log secret, token, password, OTP, nội dung nhạy cảm không cần thiết.

## Bảo toàn behavior

- Refactor không được đổi behavior đầu ra.
- Khi đổi helper dùng chung, phải nghĩ đến tác động trên nhiều tab và nhiều role.
- Với formatter như `fmt_ty()`, `fmt_tien()`, thay đổi nhỏ cũng có thể làm vỡ toàn bộ UI hoặc test snapshot.

## Khi viết code mới

- Hỏi: logic này nên nằm ở `tabs/`, `services/`, `data/`, `db.py` hay `utils.py`?
- Nếu là xử lý thuần có thể test được, ưu tiên `services/`.
- Nếu là hiển thị Streamlit, để ở `tabs/` hoặc `components/`.
- Nếu là đường dẫn, cột, mapping, để ở `config.py` hoặc helper chuẩn.
