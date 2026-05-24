# DECISIONS.md — Nhật ký Quyết định Kiến trúc VBSP-SCM
> Ghi lại **lý do tại sao** khi có lựa chọn quan trọng.
> Đọc khi: muốn đổi công nghệ, thêm người mới, debug kiến trúc.
> Cập nhật: 2026-05-22

---

## Cấu trúc mỗi entry

```
## DXXX — [Tiêu đề]
- **Ngày**: YYYY-MM-DD
- **Quyết định**: chọn A
- **Các lựa chọn đã cân nhắc**: A / B / C
- **Lý do**: ...
- **Hệ quả**: ...
- **Điều kiện thay đổi**: khi nào nên xem xét lại
```

---

## D001 — SQLite thay vì PostgreSQL

- **Ngày**: 2024-Q3 (khởi tạo dự án)
- **Quyết định**: Dùng SQLite (`data.db`)
- **Các lựa chọn**: SQLite / PostgreSQL / MySQL / JSON file
- **Lý do**:
  - Hệ thống chạy trên 1 máy đơn (Windows Server của CN), không có multi-server
  - ~20 users đồng thời, không cần connection pool phức tạp
  - Không cần cài đặt server riêng → vận hành đơn giản, ít phụ thuộc hạ tầng
  - Backup = copy 1 file `.db` → cán bộ tự làm được
  - WAL mode (`PRAGMA journal_mode=WAL`) đủ cho write concurrency với ~20 users
- **Hệ quả**: Không scale horizontal; không dùng được stored procedures; type system yếu (TEXT cho datetime)
- **Điều kiện thay đổi**: Khi số đơn vị > 50, users > 100, hoặc cần multi-server deployment

---

## D002 — Parquet thay vì CSV/Feather/Excel cho cache

- **Ngày**: 2024-Q4
- **Quyết định**: Cache HSTD/NQ11/GQVL dưới dạng Parquet (`cache/*.parquet`)
- **Các lựa chọn**: CSV / Excel / Feather / Parquet / DuckDB file
- **Lý do**:
  - HSTD toàn CN: ~50k–100k dòng × 80+ cột → CSV đọc chậm (~2s), Parquet ~0.1s
  - Column-oriented: query chỉ cần vài cột → không load toàn bộ
  - Tích hợp tốt với pandas + DuckDB (đọc trực tiếp không cần load vào RAM)
  - Type preservation: datetime, int, float giữ nguyên type qua các lần đọc
  - Feather nhanh hơn nhưng kém portable, không đọc được bằng DuckDB SQL
- **Hệ quả**: Không đọc được bằng Excel; cần kiểm tra schema cột trước khi query
- **Điều kiện thay đổi**: Khi cần stream data real-time hoặc đồng bộ cloud

---

## D003 — DuckDB thay vì pandas thuần cho query lớn

- **Ngày**: 2025-Q1
- **Quyết định**: Dùng DuckDB để query parquet trong một số tab (tab_trang_thai_nguon, merge)
- **Các lựa chọn**: pandas groupby/filter / DuckDB SQL / polars
- **Lý do**:
  - Query SQL trực tiếp trên file parquet không cần load vào RAM → `read_parquet('cache/hstd.parquet')`
  - Dễ viết aggregation phức tạp hơn pandas (JOIN, WINDOW function, QUALIFY)
  - Team quen SQL hơn pandas API
  - polars nhanh hơn nhưng không đọc parquet on-disk, cần load hết vào RAM
- **Hệ quả**: Phải kiểm tra schema parquet trước khi chạy (xem BUGMAP A5); cần xử lý khi parquet thiếu cột
- **Pattern bắt buộc**:
  ```python
  df_check = con.execute("SELECT * FROM read_parquet(?) LIMIT 1", [path]).fetchdf()
  if "Tên PGD" not in df_check.columns:
      st.info("Chưa có dữ liệu.")
      return
  ```

---

## D004 — kv_store (SQLite TEXT/JSON) thay vì file JSON riêng lẻ

- **Ngày**: 2024-Q3
- **Quyết định**: Tất cả dữ liệu cấu hình/kế hoạch/danh mục lưu vào bảng `kv_store`
- **Các lựa chọn**: File JSON riêng (`khtd_cn.json`, ...) / SQLite kv_store / Redis / Pickle
- **Lý do**:
  - File JSON riêng → không có audit trail, dễ corrupt khi nhiều user ghi đồng thời
  - Redis: overkill cho hạ tầng hiện tại (thêm service, thêm port)
  - kv_store: 1 nơi duy nhất, backup cùng với DB, có `updated_by`/`updated_at` tự động
  - `kv_history` ghi lịch sử thay đổi → rollback được
  - Streamlit session_state KHÔNG dùng để persist (mất khi reload)
- **Hệ quả**: Value là JSON string → cần `json.loads()`/`json.dumps()`; không query được nội dung JSON trực tiếp bằng SQL (trừ `json_extract()`)
- **Điều kiện thay đổi**: Khi cần query nội dung JSON thường xuyên → xem xét cột riêng

---

## D005 — `render(tab=None, **kwargs)` pattern cho tất cả tabs

- **Ngày**: 2024-Q4
- **Quyết định**: Mọi tab đều có signature `render(tab=None, **kwargs)` với fallback `st.container()`
- **Các lựa chọn**: `render(tab)` bắt buộc / class-based Tab / render(tab=None)
- **Lý do**:
  - `ws_management.py` và `ws_operation.py` mount cùng 1 tab function với context khác nhau (CN vs PGD)
  - Tab có thể được gọi standalone để test (không cần Streamlit tab context)
  - `tab=None` → fallback `st.container()` → luôn hoạt động được
  - `**kwargs` thay vì tham số positional → dễ thêm context mới mà không break signature cũ
- **Hệ quả**: Không type-safe; phải nhớ `normalize_role()` trước khi dùng role
- **Pattern bắt buộc**:
  ```python
  ctx = tab if tab is not None else st.container()
  with ctx:
      ...
  # KHÔNG: with tab:  ← tab có thể là None
  ```

---

## D006 — pgd_mode pattern (song song 2 phân hệ CN/PGD)

- **Ngày**: 2025-Q1
- **Quyết định**: Dùng `pgd_mode=True/False` + `key_prefix` để render cùng 1 hàm cho 2 phân hệ
- **Các lựa chọn**: 2 hàm riêng / 1 hàm với flag / 2 tab riêng
- **Lý do**:
  - Logic nghiệp vụ giống nhau, chỉ khác data scope (toàn CN vs 1 PGD) và đường dẫn file
  - 2 hàm riêng → code trùng lặp, sửa 1 chỗ phải sửa 2
  - `key_prefix` tránh `DuplicateElementKey` khi cả hai render trong cùng 1 session
- **Hệ quả**: Hàm phức tạp hơn; cần đọc kỹ để hiểu nhánh nào đang chạy
- **Pattern**:
  ```python
  pgd_mode = kwargs.get("pgd_mode", False)
  key_prefix = f"pgd_{pgd_slug(pgd_user)}_" if pgd_mode else "cn_"
  ```

---

## D007 — Tiền tệ lưu VND, hiển thị triệu đồng

- **Ngày**: 2024-Q3
- **Quyết định**: Lưu VND (×1_000_000), hiển thị bằng `fmt_ty()` (chia `/1e6` → triệu)
- **Các lựa chọn**: Lưu triệu / lưu tỷ / lưu VND
- **Lý do**:
  - Dữ liệu gốc từ Excel HSTD tính bằng VND → không convert khi đọc vào, tránh mất độ chính xác
  - `fmt_ty()` xử lý format kiểu VN (dấu chấm nghìn, dấu phẩy thập phân) → nhất quán
  - Bug cũ: `/1e9` → sai đơn vị (xem BUGMAP C1, test_currency.py)
- **Hệ quả**: Mọi số liệu trong DB và DataFrame là VND; cột header phải ghi `(triệu đồng)` khi hiển thị
- **Bất biến**: KHÔNG dùng `NumberColumn` của Streamlit cho cột tiền tệ → luôn dùng `.apply(fmt_ty)` trước

---

## D008 — Streamlit thay vì FastAPI + React/Vue

- **Ngày**: 2024-Q3 (khởi tạo dự án)
- **Quyết định**: Dùng Streamlit cho toàn bộ UI
- **Các lựa chọn**: Streamlit / FastAPI + React / Dash / Flask + Jinja2
- **Lý do**:
  - Team Python (không có frontend developer)
  - Thời gian phát triển tính bằng tuần, không bằng tháng
  - Streamlit: 1 file Python = 1 tính năng đầy đủ (upload, chart, table, form)
  - ~20 users không concurrent → không cần SPA
- **Hệ quả**: Không customize sâu UI; mỗi tương tác user = 1 full rerun (hiệu năng kém hơn SPA); widget key phải quản lý thủ công
- **Điều kiện thay đổi**: Khi cần mobile-first UI, real-time update, hoặc users > 100 đồng thời

---

## D009 — Snapshot riêng thay vì chỉ dùng Parquet cho time-series

- **Ngày**: 2025-Q1
- **Quyết định**: Tạo `hstd_snapshot`, `nq11_snapshot`, `gqvl_snapshot`, `cdtotkvv_snapshot` trong SQLite
- **Các lựa chọn**: Chỉ lưu parquet hiện tại / Parquet partitioned theo kỳ / SQLite snapshot tables
- **Lý do**:
  - Parquet cache bị overwrite mỗi lần merge → mất dữ liệu lịch sử
  - Time-series analysis (so sánh kỳ, heatmap, risk trend) cần dữ liệu nhiều tháng
  - SQLite UNIQUE constraint → upsert-safe, không duplicate kỳ
  - Query cross-period bằng SQL đơn giản hơn so với đọc nhiều file parquet
- **Hệ quả**: Dữ liệu lịch sử là aggregated (không lưu từng khế ước) → không drill-down được; phải chạy snapshot trigger sau mỗi merge

---

## D010 — Không tự git commit/push

- **Ngày**: 2025-Q2
- **Quyết định**: AI (Trae/Claude) KHÔNG tự `git add`, `git commit`, `git push`
- **Lý do**:
  - Commit message phải do người có trách nhiệm ký tên
  - GitHub Desktop cho phép review diff trực quan trước khi commit
  - Tránh AI tự ý push code chưa review lên main branch
  - Worktree phụ của Claude không hiển thị trong GitHub Desktop → người dùng bị mất kiểm soát
- **Hệ quả**: Mọi deploy phải qua tay người dùng; không có CI/CD tự động
- **Áp dụng cho**: Claude Code (worktree gốc `D:/VBSP-SCM`) + Trae

---

## D011 — RBAC 9 role thay vì permission matrix

- **Ngày**: 2024-Q3
- **Quyết định**: 9 role cố định (`executive`, `admin_cn`, `manager_cn`, `admin`, `manager`, `admin_pgd`, `manager_pgd`, `user_pgd`, `user`)
- **Các lựa chọn**: Permission matrix / Role-based / Attribute-based
- **Lý do**:
  - Ngân hàng nhà nước có cấu trúc tổ chức cứng → role ổn định, ít thay đổi
  - 9 role đủ để phân biệt CN vs PGD, quản lý vs tác nghiệp, đọc vs ghi
  - Permission matrix phức tạp hơn, khó audit
- **Hệ quả**: Thêm role mới → phải sửa `auth.py` + ROLES.md; không granular như permission matrix
- **Alias backward-compat**: `admin` = `admin_cn`, `manager` = `manager_cn`, `user` = `user_pgd`

---

## D012 — Merge 22 file PGD → 1 Parquet (thay vì query từng PGD)

- **Ngày**: 2025-Q1
- **Quyết định**: Phòng KH-NV upload 22 file → merge thành `cache/hstd.parquet`; không đọc từng PGD realtime
- **Các lựa chọn**: Merge offline → 1 parquet / Query từng PGD file khi cần / Database trung tâm
- **Lý do**:
  - 22 file × 2–5MB = ~50–100MB → đọc đồng thời chậm, cần cache
  - Phân tích toàn CN (cross-PGD) cần 1 DataFrame thống nhất schema
  - Merge có schema normalization → bắt lỗi cột sai tên/type ngay lúc upload
  - `merge_meta_hstd` trong kv_store ghi lại trạng thái → biết PGD nào dùng số liệu cũ
- **Hệ quả**: Dữ liệu CN lag sau khi PGD upload (phải chờ merge); rollback được nếu merge lỗi

---

## D013 — Không dùng Streamlit Multipage, giữ monolithic app.py

- **Ngày**: 2026-05-24
- **Quyết định**: KHÔNG tách workspace thành `pages/` (multipage), giữ nguyên `app.py` điều phối 3 workspace dựa trên role
- **Các lựa chọn**: Multipage (pages/) / Giữ monolithic app.py / Tách mỗi workspace thành app riêng
- **Lý do**:
  - Kiến trúc workspace-by-role (`ws_executive` / `ws_management` / `ws_operation`) không phải tính năng độc lập — `app.py` điều phối dựa trên `role` từ session sau login
  - Multipage yêu cầu: duplicate auth + session check mỗi page, không có `st.session_state` cross-page đáng tin, phải refactor toàn bộ routing
  - 3 workspace × 1800+ dòng mỗi cái → rủi ro refactor cao, lợi ích không tương xứng cho 20 users
  - Tầng 1 (lazy import 44s + skip NQ11/GQVL) đã đạt KPI ROADMAP ≤3s load
- **Hệ quả**: Mỗi lần thêm tab làm workspace phình to hơn → phải tiếp tục lazy import; không tách được deployment từng workspace
- **Điều kiện thay đổi**: Khi workspace > 5000 dòng, hoặc cần deploy PGD workspace riêng biệt

---

## D014 — FastAPI backend hoãn đến 2027 (Giai đoạn 4)

- **Ngày**: 2026-05-24
- **Quyết định**: Hoãn triển khai FastAPI/data server đến 2027; tiếp tục dùng DuckDB trực tiếp trong Streamlit process
- **Các lựa chọn**: FastAPI ngay / Hoãn 2027 / Không bao giờ
- **Lý do**:
  - ROADMAP.md Giai đoạn 4 (2027) đã ghi: "Khi số đơn vị > 50, users > 100, hoặc cần multi-server deployment"
  - Hiện tại 22 đơn vị (~20 users), Windows Server nội bộ đơn → chưa đến ngưỡng
  - Thêm FastAPI tạo dependency hạ tầng mới: đảm bảo server luôn chạy, startup order, port conflict
  - Tầng 1 lazy import đã đạt target performance cho quy mô hiện tại
- **Hệ quả**: Streamlit vẫn load toàn bộ parquet trong process (~700MB RAM); khi data gấp đôi phải xem xét lại
- **Điều kiện thay đổi**: >100 users đồng thời, data >1GB, hoặc cần mobile app
