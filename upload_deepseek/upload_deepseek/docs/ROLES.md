# Hệ thống Role VBSP-SCM
> Mô tả chi tiết phân quyền người dùng theo 2 phân hệ: Chi nhánh (CN) và Phòng giao dịch (PGD)
> Cập nhật: 06/05/2026

---

## Phân hệ Chi nhánh (CN)

Dành cho TP/PTP KH-NV, CBTD Hội sở, Ban Giám đốc tại **Hội sở Chi nhánh tỉnh**.

| Role | Mô tả | Quyền | Tương thích ngược |
|---|---|---|---|
| `executive` | Ban Giám đốc | Chỉ đọc dashboard vĩ mô | — |
| `admin_cn` | Quản trị CN | Toàn quyền CN (users, config, upload, merge) | `admin` |
| `manager_cn` | Lãnh đạo CN | Upload CN, giao chỉ tiêu, xem báo cáo | `manager` |
| `admin` (cũ) | = `admin_cn` | Toàn quyền CN | `admin_cn` |
| `manager` (cũ) | = `manager_cn` | Upload CN, giao chỉ tiêu | `manager_cn` |

**Workspace:** `ws_management` — toàn quyền CN, tổng hợp 22 PGD

---

## Phân hệ PGD

Dành cho Giám đốc PGD, Tổ trưởng KHNV, CBTD tại **21 Phòng giao dịch**.

| Role | Mô tả | Quyền | Tương thích ngược |
|---|---|---|---|
| `admin_pgd` | Quản trị PGD | Upload HSTD + quản lý user PGD + giao nhiệm vụ | — |
| `manager_pgd` | Lãnh đạo PGD | Upload HSTD + nhập kế hoạch + xem báo cáo | — |
| `user_pgd` | CBTD PGD | Tác nghiệp, chỉ thấy PGD mình | `user` |
| `user` (cũ) | = `user_pgd` | Tác nghiệp, chỉ thấy PGD mình | `user_pgd` |

**Workspace:** `ws_operation` — tác nghiệp địa bàn, chỉ thấy PGD được phân công

---

## Routing workspace

```
┌─────────────────────────────────────────────────────────────┐
│  CN roles                                                    │
│  ├── executive        ──→ ws_executive (dashboard vĩ mô)    │
│  ├── admin_cn         ──→ ws_management                     │
│  ├── manager_cn       ──→ ws_management                     │
│  ├── admin (cũ)       ──→ ws_management                     │
│  └── manager (cũ)     ──→ ws_management                     │
├─────────────────────────────────────────────────────────────┤
│  PGD roles                                                 │
│  ├── admin_pgd        ──→ ws_operation                      │
│  ├── manager_pgd      ──→ ws_operation                      │
│  ├── user_pgd         ──→ ws_operation                      │
│  └── user (cũ)        ──→ ws_operation                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Hàm helper trong auth.py

```python
from auth import la_phan_he_cn, la_phan_he_pgd
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

# Check phân hệ
if la_phan_he_cn(role):
    # executive, admin_cn, manager_cn, admin, manager
    pass

if la_phan_he_pgd(role):
    # admin_pgd, manager_pgd, user_pgd, user
    pass

# Check quyền cụ thể PGD
if co_quyen_upload_pgd(role):
    # admin_pgd, manager_pgd
    pass

if co_quyen_quan_ly_user_pgd(role):
    # admin_pgd only
    pass
```

---

## Lưu ý khi thêm tab mới

### ❌ KHÔNG check role cứng kiểu cũ:
```python
# KHÔNG dùng — chỉ check role cũ, bỏ sót role mới
if role not in ("admin", "manager", "user"):
    st.error("Không có quyền")
```

### ✅ PHẢI dùng một trong 2 cách:

**Cách 1:** Dùng hàm helper từ `auth.py` (khuyến nghị):
```python
from auth import la_phan_he_cn, la_phan_he_pgd
from auth import co_quyen_upload_pgd, co_quyen_quan_ly_user_pgd

if co_quyen_upload_pgd(role):
    # Cho phép upload
    pass
```

**Cách 2:** Thêm đủ cả role cũ lẫn role mới:
```python
ALLOWED_ROLES = (
    "admin", "manager", "user",
    "admin_cn", "manager_cn",
    "admin_pgd", "manager_pgd", "user_pgd"
)
if role not in ALLOWED_ROLES:
    st.error("Không có quyền")
```

---

## Danh sách role hợp lệ (config.py)

```python
# config.py
ROLES_CU = ["executive", "admin", "manager", "user"]
ROLES_MOI = [
    "executive",
    "admin_cn", "manager_cn",      # Phân hệ Chi nhánh
    "admin_pgd", "manager_pgd", "user_pgd",  # Phân hệ PGD
]
ALL_ROLES = list(dict.fromkeys(ROLES_CU + ROLES_MOI))

# Nhóm theo phân hệ
ROLES_PHAN_HE_CN  = ["executive", "admin_cn", "manager_cn", "admin", "manager"]
ROLES_PHAN_HE_PGD = ["admin_pgd", "manager_pgd", "user_pgd", "user"]

# Quyền cụ thể
ROLES_CO_QUYEN_UPLOAD_CN  = ["admin_cn", "manager_cn", "admin", "manager"]
ROLES_CO_QUYEN_UPLOAD_PGD = ["admin_pgd", "manager_pgd"]
ROLES_CO_QUYEN_QUAN_LY_USER_CN  = ["admin_cn", "admin"]
ROLES_CO_QUYEN_QUAN_LY_USER_PGD = ["admin_pgd"]
ROLES_CO_QUYEN_GIAO_NHIEM_VU    = ["admin_pgd", "manager_pgd", "admin", "manager"]
```

---

## Tài khoản mặc định theo PGD

Format: `admin_{slug_pgd}` / mật khẩu: `123456`

| Tài khoản | PGD quản lý |
|---|---|
| `admin_bien_hoa` | Hội sở Chi nhánh tỉnh (DON_VI_CHI_NHANH) |
| `admin_long_thanh` | PGD Long Thành |
| `admin_trang_bom` | PGD Trảng Bom |
| `admin_nhon_trach` | PGD Nhơn Trạch |
| `admin_xuan_loc` | PGD Xuân Lộc |
| ... | ... (21 PGD) |

**⚠️ Lưu ý:** Đổi mật khẩu sau khi bàn giao!
