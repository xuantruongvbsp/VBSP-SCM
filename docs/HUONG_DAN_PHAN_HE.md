# Hướng dẫn sử dụng VBSP-SCM theo phân hệ
> Phân hệ Chi nhánh (CN) vs Phân hệ Phòng giao dịch (PGD)
> Cập nhật: 06/05/2026

---

## Phân hệ Chi nhánh (CN)

### Đối tượng sử dụng
- **TP/PTP KH-NV** — Tổ trưởng/Phó Tổ Kế hoạch - Nghiệp vụ
- **CBTD Hội sở** — Cán bộ tín dụng tại Hội sở Chi nhánh tỉnh
- **Ban Giám đốc** — Xem báo cáo, dashboard vĩ mô

### Tài khoản đăng nhập
| Role | Ví dụ | Mô tả |
|---|---|---|
| `executive` | `bgd` | Ban Giám đốc — chỉ đọc |
| `admin_cn` | `admin`, `admin_cn` | Quản trị CN — toàn quyền |
| `manager_cn` | `manager`, `manager_cn` | Lãnh đạo CN — upload, giao chỉ tiêu |

### Chức năng chính
- **Tổng hợp toàn bộ 22 PGD** — Xem số liệu tất cả đơn vị
- **Giao chỉ tiêu KHTD** — Giao KH tín dụng theo đợt
- **Upload file hệ thống** — Merge 22 file PGD
- **Báo cáo tổng hợp** — Xuất báo cáo toàn CN
- **Kiểm soát Chi nhánh** — Tra cứu, giám sát

### Workspace: ws_management
Các tab chính:
- 📊 Tổng quan — KPI toàn CN
- 🔍 Tra cứu — Hồ sơ toàn CN
- 📈 KH Tín dụng — KHTD toàn CN
- 📤 Giao KH theo Đợt — Giao & điều chỉnh
- ✅ Nhiệm vụ — Giao nhiệm vụ
- 🔒 Kiểm soát — Báo cáo kiểm soát
- 📤 Upload — 22 file PGD + merge

---

## Phân hệ PGD

### Đối tượng sử dụng
- **Giám đốc PGD** — Quản lý điểm giao dịch
- **Tổ trưởng KHNV** — Kế hoạch - Nghiệp vụ
- **CBTD PGD** — Cán bộ tín dụng địa bàn

### Tài khoản đăng nhập
| Role | Ví dụ | Mô tả |
|---|---|---|
| `admin_pgd` | `admin_long_thanh`, `admin_trang_bom` | Quản trị PGD — upload + quản lý user |
| `manager_pgd` | `manager_pgd_long_thanh` | Lãnh đạo PGD — upload, nhập KH |
| `user_pgd` | `user_long_thanh_001` | CBTD — tác nghiệp địa bàn |

### Chức năng chính
- **Upload HSTD riêng PGD** — File HSTD, NQ11, GQVL
- **Tác nghiệp địa bàn** — Tra cứu, nhập liệu theo PGD
- **Quản lý ủy thác** — Mẫu 06, 15, 16, KH KT
- **Theo dõi nhiệm vụ** — Nhận nhiệm vụ từ CN
- **Chỉ thấy PGD mình** — Dữ liệu cách ly theo PGD

### Workspace: ws_operation
Các tab chính:
- 🔍 Tra cứu — Hồ sơ PGD mình
- 📋 Danh sách KH — Khách hàng PGD
- 📈 KH Tín dụng — KHTD theo PGD
- 📄 Ủy thác — 5 sub-tab (Mẫu 06, 15, 16...)
- 🏠 Điểm GD — Quản lý điểm giao dịch
- 👥 Ban đại diện — Thông tin BĐD
- 📤 Upload — File riêng PGD

---

## Tài khoản mặc định theo PGD

### Format tài khoản
```
admin_{slug_pgd} / 123456
```

Trong đó `slug_pgd` = tên PGD viết thường, dấu cách → dấu `_`

### Danh sách tài khoản mặc định

| Tài khoản | PGD quản lý |
|---|---|
| `admin_bien_hoa` | Hội sở Chi nhánh tỉnh (DON_VI_CHI_NHANH) |
| `admin_long_thanh` | PGD Long Thành |
| `admin_trang_bom` | PGD Trảng Bom |
| `admin_long_khanh` | PGD Long Khánh |
| `admin_nhon_trach` | PGD Nhơn Trạch |
| `admin_xuan_loc` | PGD Xuân Lộc |
| `admin_dinh_quan` | PGD Định Quán |
| `admin_thong_nhat` | PGD Thống Nhất |
| `admin_cai_lay` | PGD Cai Lậy |
| `admin_tan_phuoc` | PGD Tân Phước |
| `admin_ham_tan` | PGD Hàm Tân |
| `admin_duc_lin_ha` | PGD Đức Linh Hà |
| `admin_tanh_lin_ha` | PGD Tánh Linh Hà |
| `admin_ham_thuan_bac` | PGD Hàm Thuận Bắc |
| `admin_ham_thuan_nam` | PGD Hàm Thuận Nam |
| `admin_tay_ho` | PGD Tây Hồ |
| `admin_bao_lam` | PGD Bảo Lâm |
| `admin_bao_loc` | PGD Bảo Lộc |
| `admin_da_huoai` | PGD Đạ Huoai |
| `admin_da_te` | PGD Đạ Tẻ |
| `admin_don_duong` | PGD Đơn Dương |

**⚠️ Lưu ý quan trọng:**
- Mật khẩu mặc định: `123456`
- **Đổi mật khẩu sau khi bàn giao!**
- Tài khoản chỉ có quyền trên PGD được phân công

---

## So sánh nhanh 2 phân hệ

| Tiêu chí | Phân hệ CN | Phân hệ PGD |
|---|---|---|
| **Đối tượng** | TP/PTP KH-NV, CBTD Hội sở, BGĐ | Giám đốc PGD, Tổ trưởng KHNV, CBTD |
| **Phạm vi** | Toàn CN (22 đơn vị) | Chỉ 1 PGD được phân công |
| **Workspace** | `ws_management` | `ws_operation` |
| **Upload** | Merge 22 file PGD | File riêng PGD |
| **Báo cáo** | Tổng hợp toàn CN | Theo PGD |
| **Quản lý user** | Toàn bộ users | Chỉ user trong PGD |
| **Role quản trị** | `admin`, `admin_cn` | `admin_pgd` |
| **Role lãnh đạo** | `manager`, `manager_cn` | `manager_pgd` |
| **Role tác nghiệp** | — | `user`, `user_pgd` |

---

## Quy trình làm việc phối hợp

### 1. CN giao chỉ tiêu → PGD thực hiện
```
CN (admin_cn/manager_cn)
    └── Giao KHTD đợt 1/2026
        └── PGD Long Thành (manager_pgd/user_pgd)
            └── Nhập KH theo xã
                └── Báo cáo tiến độ → CN
```

### 2. PGD upload dữ liệu → CN tổng hợp
```
PGD Long Thành (admin_pgd/manager_pgd)
    └── Upload HSTD, NQ11, GQVL
        └── CN (admin_cn) merge 22 PGD
            └── Tổng hợp toàn CN
                └── Báo cáo BGĐ
```

### 3. CN kiểm soát → PGD khắc phục
```
CN (admin_cn)
    └── Kiểm soát Chi nhánh
        └── Phát hiện vấn đề tại PGD X
            └── Giao nhiệm vụ khắc phục
                └── PGD X (user_pgd) thực hiện
```

---

## Xử lý sự cố

### Không đăng nhập được
1. Kiểm tra tài khoản có tồn tại không
2. Kiểm tra role có hợp lệ không
3. Reset mật khẩu qua admin cấp trên

### Không thấy dữ liệu PGD
- `user_pgd`/`user` chỉ thấy PGD được phân công trong `user_info["pgd"]`
- Liên hệ `admin_pgd` hoặc `admin_cn` để kiểm tra

### Không upload được
- `admin_pgd`/`manager_pgd`: Có quyền upload
- `user_pgd`: Không có quyền upload (chỉ tác nghiệp)
- `admin_cn`/`manager_cn`: Upload file merge toàn CN
