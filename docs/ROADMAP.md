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

## Ghi chú kỹ thuật còn mở

- GSheet ID: `DCGIAM_SHEET_ID = 15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk`
- 4 key ĐP đã thêm vào config: `9_DP`, `12_DP`, `17_DP`, `26_DP`
- Đơn vị tiền tệ: `×1e6` (triệu → VND) — **KHÔNG dùng `×1e9`**
- Tab context chuẩn: `_tab_ctx = tab if tab is not None else _st.container()`
