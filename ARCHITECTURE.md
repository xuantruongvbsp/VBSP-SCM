# Kiến trúc Module — VBSP-SCM
> Tài liệu tham chiếu nhanh khi Cursor cần biết file nào làm gì.
> Cập nhật lần cuối: 05/2026 — thêm khtd_service, tab_khtd_giao_dc, 4 key DP mới, ws_operation tabs thực tế

---

## 1. Sơ đồ thư mục

```
VBSP-SCM/
│
├── app.py                    # Điểm vào: routing, session, load df
├── auth.py                   # Đăng nhập, RBAC, quản lý user
├── config.py                 # Hằng số toàn hệ thống
├── db.py                     # SQLite: kv_store, users, audit_log
├── utils.py                  # fmt(), Excel helpers, tự động điền Word
├── server.py                 # HTTP server nhẹ (store.json) — dùng cho khtd-targets-app
│
├── data/                     # Lớp đọc dữ liệu
│   ├── core.py               # ts_file(), excel_to_parquet(), parquet cache
│   ├── hstd.py               # doc_file(), cảnh báo 3 tháng KHĐ
│   ├── pgd.py                # Đọc/lưu pgd_data/{slug}/, pgd_slug()
│   ├── khtd.py               # KHTD, CBTD, KH, QĐ UBND
│   ├── ct_discovery.py       # Quét HSTD+GQVL+NQ11 → ct_registry
│   ├── cdtotkvv.py           # Đọc/tổng hợp Chấm điểm Tổ TK&VV:
│   │                         # doc_cdtotkvv(), doc_cdtotkvv_pgd(),
│   │                         # ds_thang_nam(), tong_hop_theo_pgd()
│   └── data_priority.py      # Kiểm tra trạng thái file pgd_data/ (sidebar widget)
│
├── services/                 # Lớp nghiệp vụ
│   ├── __init__.py           # Re-export các hàm chính
│   ├── upload_service.py     # Upload tập trung: KetQuaUpload,
│   │                         # luu_pgd_file, luu_file_he_thong,
│   │                         # luu_dienbao, merge_du_lieu_toan_cn
│   ├── upload_center.py      # Tab Quản trị: render_panel_upload(),
│   │                         # lay_trang_thai(), hien_thi_trang_thai_nho()
│   ├── report_service.py     # Logic tạo báo cáo Excel
│   ├── data_quality.py       # Kiểm tra chất lượng file upload
│   ├── data_source_status.py # Widget trạng thái nguồn dữ liệu (sidebar)
│   ├── data_priority_service.py # Ưu tiên nguồn dữ liệu: kiem_tra_nguon_uu_tien(),
│   │                         # bao_cao_trang_thai_nguon(), cap_nhat_nguon_uu_tien()
│   ├── khtd_service.py       # Giao KHTD & Điều chỉnh: Google Sheet, kv_store,
│   │                         # duyệt tập trung, lũy kế đợt
│   └── kiem_soat_service.py  # Kiểm soát CN: registry báo cáo, BaoCaoMeta,
│                             # render từng loại báo cáo kiểm soát
│
├── tabs/                     # Giao diện — mỗi file = 1 tab
│   ├── tab_tongquan.py       # Tổng quan danh mục tín dụng
│   ├── tab_tracuu.py         # Tra cứu hồ sơ khách hàng
│   ├── tab_candoi.py         # Cân đối nguồn vốn + điện báo
│   ├── tab_khtd.py           # Kế hoạch tín dụng (toàn CN)
│   ├── tab_khtd_pgd.py       # Kế hoạch tín dụng (PGD)
│   ├── tab_khtd_mau07.py     # Mẫu 07 KHTD
│   ├── tab_khtd_giao_dc.py   # Giao KHTD & Điều chỉnh KHTD (Google Sheet + kv_store)
│   ├── tab_cbtd.py           # Chuẩn bị tín dụng
│   ├── tab_gqvl.py           # Giải quyết việc làm (GQVL)
│   ├── tab_nq11.py           # Nghị quyết 11
│   ├── tab_cdtotkvv.py       # Chấm điểm Tổ TK&VV
│   ├── tab_kiem_soat.py      # Kiểm soát CN (chọn nhóm/báo cáo từ kiem_soat_service)
│   ├── tab_baocao.py         # Xuất báo cáo
│   ├── tab_danhsach.py       # Danh sách khách hàng
│   ├── tab_kehoach.py        # Kế hoạch chung
│   ├── tab_nhiem_vu.py       # Nhiệm vụ giao
│   ├── tab_upload_khnv.py    # Upload tập trung (Phòng KH-NV)
│   ├── tab_upload_pgd.py     # Upload địa bàn (PGD)
│   └── tab_trang_thai_nguon.py # Trạng thái nguồn dữ liệu
│
├── widgets/                  # Widget UI tái sử dụng
│   ├── data_source_status.py # Widget trạng thái 2 luồng (ws_operation vs ws_management)
│   └── status_widget.py      # Widget trạng thái compact cho sidebar
│
├── workspaces/               # Container workspace theo role
│   ├── ws_executive.py       # BGĐ: gauge, heatmap, tổng quan vĩ mô
│   ├── ws_management.py      # Điều hành: admin/manager (toàn CN)
│   └── ws_operation.py       # Tác nghiệp: user (theo PGD)
│
├── docs/                     # Tài liệu kỹ thuật nội bộ
│   ├── definition_of_ready_noxh_2026.md  # Định nghĩa "sẵn sàng" cho NỢ XH 2026
│   └── report_service.md                 # Hướng dẫn sử dụng report_service
│
├── data/                     # Thư mục runtime (không commit)
│   └── pgd_data/{slug}/      # File upload riêng từng PGD
│
├── cache/                    # Parquet cache (không commit)
│   ├── hstd.parquet
│   ├── nq11.parquet
│   └── gqvl.parquet
│
└── giao_ban.py               # Tính số liệu & tạo bảng Word giao ban xã
                              # (dùng cho cả ws_operation và ws_management)
```

---

## 2. Luồng khởi động (app.py)

```
app.py
  1. init_db()                          # Khởi tạo SQLite
  2. auth.kiem_tra_dang_nhap()          # Session, RBAC
  3. _load_hstd(CACHE_HSTD, ts)        # Load df toàn CN
  4. _load_nq11(CACHE_NQ11, ts)        # Load df_nq11
  5. Xác định ws_hien_tai               # executive/management/operation
  6. Nếu ws_operation:
       role=user  → doc_hstd_pgd(pgd_user)
       role=admin → doc_hstd_toan_cn_pgd()
  7. Render workspace tương ứng
       ws_executive(df, df_nq11, ...)
       ws_management(df, df_nq11, ...)
       ws_operation(df, df_nq11, pgd_user, ...)
```

---

## 3. Luồng dữ liệu

```
┌─ Phòng KH-NV ──────────────────────────────────────┐
│  tab_upload_khnv                                    │
│    → luu_file_he_thong()                            │
│    → merge_du_lieu_toan_cn()                        │
│         → ghi cache/hstd.parquet (CACHE_HSTD)       │
│         → ghi cache/nq11.parquet (CACHE_NQ11)       │
│         → ghi cache/gqvl.parquet (CACHE_GQVL)       │
│  Dùng bởi: ws_management, ws_executive              │
└─────────────────────────────────────────────────────┘

┌─ Phòng Giao Dịch ──────────────────────────────────┐
│  tab_upload_pgd                                     │
│    → luu_pgd_file()                                 │
│         → ghi pgd_data/{slug}/hstd_latest.xlsx      │
│         → ghi pgd_data/{slug}/nq11_latest.xlsx      │
│         → ghi pgd_data/{slug}/gqvl_latest.xlsx      │
│  Dùng bởi: ws_operation                             │
└─────────────────────────────────────────────────────┘
```

---

## 4. Quan hệ giữa các module

### config.py — không import module nội bộ nào
```
config.py ← được import bởi TẤT CẢ các module khác
```

### db.py — chỉ import config
```
db.py ← được import bởi: app, auth, upload_service, tất cả tabs
```

### upload_service.py — import config, db, data.pgd, data.core
```
upload_service.py
  ← được import bởi: tab_upload_khnv, tab_upload_pgd,
                      tab_candoi, tab_gqvl, tab_cdtotkvv
```

### upload_center.py — import upload_service, config, db
```
upload_center.py  (services/)
  Hàm chính:
    render_panel_upload(role, prefix)  → giao diện upload file hệ thống + Điện báo
    lay_trang_thai()                   → dict trạng thái file hiện tại
    hien_thi_trang_thai_nho()          → banner trạng thái mini cho tab không upload
  ← được import bởi: ws_management (tab Quản trị)
```

### khtd_service.py — import config, db, Google Sheets
```
khtd_service.py  (services/)
  Hàm chính:
    kv_key_dot(pgd_slug, nam, thang, dot)  → key kv_store cho 1 đợt
    doc dữ liệu KHTD từ Google Sheet
    luu/doc kv_store theo đợt giao
  ← được import bởi: tab_khtd_giao_dc
```

### kiem_soat_service.py — import config, db
```
kiem_soat_service.py  (services/)
  Hàm chính:
    BAO_CAO_REGISTRY        → danh sách báo cáo kiểm soát (BaoCaoMeta)
    chon_pgd_filter()       → selectbox lọc PGD
    render_*(cache, ...)    → hàm render từng loại báo cáo
  ← được import bởi: tab_kiem_soat
  Mở rộng: thêm BaoCaoMeta + hàm render_* → tự động xuất hiện trong tab
```

### data_priority_service.py — import config, db, data.pgd
```
data_priority_service.py  (services/)
  Hàm chính:
    kiem_tra_nguon_uu_tien(ten_don_vi, loai_file) → dict trạng thái nguồn
    bao_cao_trang_thai_nguon()                    → dict tổng hợp tất cả đơn vị
    cap_nhat_nguon_uu_tien(username)              → cập nhật + ghi audit
    render_widget_trang_thai(pgd_user)            → HTML widget trạng thái
```

### data/pgd.py — import config, db
```
data/pgd.py
  Hàm chính:
    pgd_slug(ten_pgd)              → "pgd_long_thanh"
    thu_muc_pgd(ten_pgd)           → Path("pgd_data/pgd_long_thanh/")
    duong_dan_pgd(ten_pgd, loai)   → "pgd_data/.../hstd_latest.xlsx"
    doc_hstd_pgd(ten_pgd, ts)      → DataFrame | None
    doc_nq11_pgd(ten_pgd, ts)      → DataFrame | None
    doc_hstd_toan_cn_pgd()         → DataFrame (gộp tất cả pgd_data/)
    doc_trang_thai_file(ten_pgd, loai) → {"co_file": bool, "ngay": str}
```

### giao_ban.py — import config, docx
```
giao_ban.py  (root)
  Hàm chính:
    tinh_so_lieu_van_xuoi(df, ten_xa, ...)  → dict số liệu giao ban
    tao_bang_dvut(doc, df_xa)               → điền bảng đơn vị thụ hưởng
    tao_bang_chuong_trinh(doc, ...)         → điền bảng chương trình
    tao_bang_ke_hoach(doc, ...)             → điền bảng kế hoạch
    xuat_bien_ban_giao_ban(...)             → xuất file Word giao ban xã
  ← dùng chung cho ws_operation (CBTD) và ws_management
```

### workspaces — import tabs
```
ws_executive.py  → tab_tongquan, tab_candoi, tab_baocao
ws_management.py → tất cả tabs (trừ tab_upload_pgd)
                   + tab_kiem_soat, tab_khtd_giao_dc
ws_operation.py  → tab_tracuu, tab_danhsach, tab_upload_pgd,
                   tab_gqvl, tab_nq11, tab_cdtotkvv, ...
```

---

## 5. Workspace — Tab nào thuộc workspace nào

### ws_executive (BGĐ — chỉ đọc)
| Tab | Mô tả |
|---|---|
| tab_tongquan | Tổng quan KPI toàn CN |
| tab_candoi | Cân đối nguồn vốn |
| tab_baocao | Xuất báo cáo |

### ws_management (Phòng KH-NV — điều hành)
| Tab | Mô tả |
|---|---|
| tab_tongquan | Tổng quan KPI toàn CN |
| tab_tracuu | Tra cứu hồ sơ toàn CN |
| tab_khtd | Kế hoạch tín dụng toàn CN |
| tab_khtd_mau07 | Mẫu 07 |
| tab_khtd_giao_dc | Giao KHTD & Điều chỉnh KHTD |
| tab_gqvl | GQVL toàn CN |
| tab_nq11 | NQ11 toàn CN |
| tab_kiem_soat | Kiểm soát Chi nhánh |
| tab_candoi | Cân đối + điện báo |
| tab_baocao | Xuất báo cáo |
| tab_nhiem_vu | Giao nhiệm vụ |
| tab_upload_khnv | Upload 22 file + merge |

### ws_operation (Hỗ trợ địa bàn — PGD)
| Tab | Mô tả |
|---|---|
| tab_tracuu | Tra cứu hồ sơ PGD |
| tab_danhsach | Danh sách KH PGD |
| tab_khtd_pgd | KHTD PGD |
| tab_gqvl | GQVL PGD |
| tab_nq11 | NQ11 PGD |
| tab_cdtotkvv | Chấm điểm Tổ TK&VV |
| tab_upload_pgd | Upload file riêng PGD |

---

## 6. Tham chiếu nhanh — "Tôi cần sửa gì?"

| Yêu cầu | File cần sửa |
|---|---|
| Thêm KPI card mới vào Tổng quan | `tabs/tab_tongquan.py` |
| Thêm cột lọc tra cứu | `tabs/tab_tracuu.py` |
| Sửa logic merge 22 PGD | `services/upload_service.py` → `merge_du_lieu_toan_cn()` |
| Thêm tab mới cho PGD | `tabs/tab_ten_moi.py` + đăng ký trong `workspaces/ws_operation.py` |
| Thêm tab mới cho toàn CN | `tabs/tab_ten_moi.py` + đăng ký trong `workspaces/ws_management.py` |
| Thêm chương trình tín dụng mới | `config.py` → `CHUONG_TRINH_KHTD` |
| Thêm PGD mới | `config.py` → `DS_PGD`, `MA_PGD_MAP`, `PGD_XA_MAP` |
| Sửa format hiển thị tiền tệ | `utils.py` → `fmt()`, `fmt_ty()` |
| Sửa logic đọc file HSTD | `data/hstd.py` hoặc `data/core.py` |
| Sửa logic đọc/tổng hợp Chấm điểm Tổ TK&VV | `data/cdtotkvv.py` → `doc_cdtotkvv()`, `tong_hop_theo_pgd()` |
| Thêm loại file upload mới | `services/upload_service.py` + `config.py` → `PGD_FILE_TYPES` |
| Sửa quyền truy cập tab | `workspaces/ws_*.py` |
| Thêm user mới | `auth.py` → `tao_user()` |
| Thêm báo cáo kiểm soát mới | `services/kiem_soat_service.py` → thêm `BaoCaoMeta` + hàm `render_*` |
| Sửa logic giao KHTD / điều chỉnh | `services/khtd_service.py` + `tabs/tab_khtd_giao_dc.py` |
| Sửa widget trạng thái sidebar | `widgets/data_source_status.py` hoặc `widgets/status_widget.py` |
| Sửa upload file hệ thống (Quản trị) | `services/upload_center.py` → `render_panel_upload()` |
| Sửa tính toán số liệu giao ban | `giao_ban.py` → `tinh_so_lieu_van_xuoi()`, `xuat_bien_ban_giao_ban()` |
