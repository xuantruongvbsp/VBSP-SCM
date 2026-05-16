# ROADMAP — VBSP-SCM
> Cập nhật lần cuối: 15/05/2026

---

## Đang triển khai

| # | Việc | File liên quan | Ghi chú |
|---|---|---|---|
| **R1** | **Phân hệ lập báo cáo (Word/Excel, không template)** | `tabs/tab_bao_cao.py` *(mới)*, `services/report_service.py` | Đang thiết kế |

---

## Backlog chiến lược — Chưa bắt đầu

| # | Việc | File liên quan | Phụ thuộc | Ghi chú |
|---|---|---|---|---|
| **S4** | **Dynamic NDT registry (`tab_ndt.py`)** | `tab_ndt.py` *(mới)*, `config.py` | — | Thay hằng số `MA_NDT_CAP_TINH_DUOI` cứng |
| **S5** | **Tiered GQVL pipeline** | `gen_dcgiam_sheet.py`, `khtd_service.py` | — | Cross-ref HSTDCT + GQVL qua số khế ước |
| **S6** | **Xác định mã NDT Bình Phước** | *(manual)* | S4 | Tra từ file GQVL thực tế sau khi có S4 |

---

## Không làm (đã xem xét và bỏ)

| Việc | Lý do |
|---|---|
| Chuyển sang React/Next.js | Quá tốn công, 20 users nội bộ không cần |
| streamlit-aggrid | Thêm dependency nặng, không cần thiết |
| Tab GQVL cho ws_management | Đã ẩn theo yêu cầu, giữ file |

---

## Tính năng đang thảo luận — chờ làm rõ nghiệp vụ

### CBTD ↔ ĐGD Integration
**Vấn đề:** Hai hệ thống hiện tại độc lập:
```
CBTD  →  [Mã thôn]     (flat list, kv_store key="cbtd")
PGD-Xã → ĐGD → [Ấp]   (kv_store key="dgd_map")
```
Thực tế nghiệp vụ cần: `CBTD → [ĐGD] → [Ấp/Thôn]`

**Hướng đề xuất:**
- Thêm `ds_dgd` vào `cbtd_data` → tự động suy ra `ds_thon` từ `dgd_map`
- Thêm hàm `gan_cbtd_vao_df(df, cbtd_data)` → join `Mã thôn` → cột `"CBTD"` → biểu đồ dư nợ theo CBTD

**Files liên quan:** `tabs/tab_cbtd.py`, `tabs/tab_diem_gd_pgd.py`, `data/khtd.py`, `db.py`, `data/dgd_helpers.py`

**Câu hỏi nghiệp vụ còn mở (chưa implement cho đến khi có câu trả lời):**
1. 1 CBTD phụ trách bao nhiêu ĐGD? Có thay đổi theo tháng không?
2. 1 ĐGD có thể do nhiều CBTD cùng phụ trách không?
3. CBTD gán vào ĐGD → phụ trách toàn bộ thôn hay chỉ một phần?
4. CBTD có thể chéo PGD không?
5. File HSTD có cột CBTD sẵn không hay chỉ suy từ `"Mã thôn"`?
6. Danh sách CBTD lấy từ đâu (nhập tay hay từ hệ thống)?
7. Mục tiêu dùng CBTD để làm gì (báo cáo hiệu suất, lọc dư nợ, phân công địa bàn)?

---

## Ghi chú kỹ thuật còn mở

- GSheet ID: `DCGIAM_SHEET_ID = 15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk`
- 4 key ĐP đã thêm vào config: `9_DP`, `12_DP`, `17_DP`, `26_DP`
- Đơn vị tiền tệ: `×1e6` (triệu → VND) — **KHÔNG dùng `×1e9`**
- Tab context chuẩn: `_tab_ctx = tab if tab is not None else _st.container()`
