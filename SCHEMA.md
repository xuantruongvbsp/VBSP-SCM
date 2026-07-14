# SCHEMA.md — Sơ đồ Cơ sở Dữ liệu VBSP-SCM
> Nguồn thực tế: `db.py` → `init_db()`. Cập nhật khi thêm bảng/cột migration.
> **Tra ở đây trước khi viết query SQL** — không cần đọc db.py.
> Cập nhật: 2026-07-11

---

## Tổng quan

| # | Bảng | Dùng cho | Ghi chú |
|---|------|----------|---------|
| 1 | `users` | Tài khoản người dùng | PK: username |
| 2 | `kv_store` | Lưu trữ dữ liệu dạng JSON | PK: key — trung tâm của hệ thống |
| 3 | `kv_history` | Lịch sử thay đổi kv_store | FK → kv_store.key |
| 4 | `audit_log` | Nhật ký mọi thao tác ghi | Append-only |
| 5 | `nhiem_vu` | Nhiệm vụ giao ban định kỳ | chu_ky: thang/quy/nam |
| 6 | `nhiem_vu_ketqua` | Kết quả thực hiện nhiệm vụ | FK → nhiem_vu.id, UNIQUE(id, pgd) |
| 7 | `tien_do_task` | Task tiến độ 95 xã | cap_theo_doi: xa/pgd |
| 8 | `tien_do_ketqua` | Kết quả từng xã/PGD | FK → tien_do_task.id, UNIQUE(task_id, ten_xa) |
| 9 | `hstd_snapshot` | Snapshot HSTD theo kỳ | UNIQUE(ky, ten_pgd, ma_ct, nguon_von) |
| 9a | `uy_thac_snapshot` | Snapshot ủy thác đa chiều | UNIQUE theo kỳ/cấp/PGD/xã/Hội/Tổ |
| 10 | `nq11_snapshot` | Snapshot NQ11 theo kỳ | UNIQUE(ky, ten_pgd) |
| 11 | `gqvl_snapshot` | Snapshot GQVL theo kỳ | UNIQUE(ky, ten_pgd) |
| 12 | `cdtotkvv_snapshot` | Snapshot chất lượng tổ TKV | UNIQUE(ky, ten_pgd) |
| 13 | `qlnk_ket_qua` | Kiểm tra nợ khoanh | ma_mon_vay = Số khế ước |
| 14 | `qlnk_bo_sung` | Bổ sung thông tin khoanh | UNIQUE(ma_mon_vay) |
| 15 | `qlnk_ke_hoach` | Kế hoạch kiểm tra nợ khoanh | FK mềm → ten_pgd |
| 16 | `mau_bieu_cv368` | Biểu mẫu CV-368 | loai_mau + ten_pgd + nam + dot |

---

## Chi tiết từng bảng

### 1. `users`
```sql
username   TEXT PRIMARY KEY
ho_ten     TEXT NOT NULL
password   TEXT NOT NULL         -- bcrypt hash
role       TEXT NOT NULL DEFAULT 'user'
           -- Giá trị: executive | admin_cn | manager_cn | admin_pgd | manager_pgd | user_pgd | user
pgd        TEXT                  -- NULL nếu là role CN
ngay_tao   TEXT                  -- ISO 8601
```
> Query thường dùng: `SELECT * FROM users WHERE role NOT IN ('executive') ORDER BY pgd, username`

---

### 2. `kv_store`
```sql
key        TEXT PRIMARY KEY
value      TEXT NOT NULL DEFAULT '{}'   -- JSON serialized
updated_at TEXT                         -- ISO 8601
updated_by TEXT                         -- username
```
> Index: `idx_kv_key ON kv_store(key)` — tra theo prefix nhanh nhờ LIKE 'prefix_%'

**Key pattern chuẩn** (xem đầy đủ trong CLAUDE.md §5.1):

| Pattern key | Nội dung |
|---|---|
| `khtd_cn` | KHTD toàn Chi nhánh (dict chương trình → số) |
| `khtd_pgd_{slug}` | KHTD từng PGD |
| `merge_meta_hstd` / `merge_meta_nq11` / `merge_meta_gqvl` | Metadata sau merge (ngày, dòng, PGD) |
| `no_rui_ro_{slug}_{yyyy}_{mm}` | Hồ sơ rủi ro PGD theo kỳ |
| `kehoach` | KH Điện báo toàn CN |
| `kehoach_pgd_{slug}` | KH Điện báo từng PGD |
| `dgd_map` | Danh sách điểm giao dịch |
| `ct_registry_{slug}` | Danh mục chương trình theo PGD |
| `kh_gqvl_cn_{nam}` | KH GQVL Chi nhánh |
| `khnv_phan_cong_list` | Phân công cán bộ KH-NV |
| `khnv_lich_list` | Lịch công tác KH-NV |

---

### 3. `kv_history`
```sql
id          INTEGER PRIMARY KEY AUTOINCREMENT
key         TEXT    NOT NULL                   -- FK mềm → kv_store.key
value       TEXT                               -- giá trị tại thời điểm thay đổi
changed_by  TEXT
changed_at  TEXT DEFAULT (datetime('now','localtime'))
note        TEXT
```
> Index: `idx_kv_history_key ON kv_history(key)`

---

### 4. `audit_log`
```sql
id       INTEGER PRIMARY KEY AUTOINCREMENT
ts       TEXT NOT NULL               -- datetime ISO 8601
username TEXT NOT NULL DEFAULT 'system'
action   TEXT NOT NULL               -- xem bảng action chuẩn dưới
detail   TEXT                        -- mô tả tự do
```
> **Action chuẩn**: `luu_khtd_cn`, `luu_khtd_pgd`, `upload_hstd`, `upload_nq11`, `upload_gqvl`, `merge_hstd`, `merge_nq11`, `merge_gqvl`, `luu_no_rui_ro`, `xuat_bieu_cn`, `xuat_01xln`, `xuat_02xln`, `upload_dienbao`

---

### 5. `nhiem_vu`
```sql
id            INTEGER PRIMARY KEY AUTOINCREMENT
tieu_de       TEXT NOT NULL
mo_ta         TEXT
chu_ky        TEXT NOT NULL              -- 'thang' | 'quy' | 'nam' | 'dot_xuat'
ky            TEXT NOT NULL              -- '2026-05' (tháng) | '2026-Q2' (quý)
pgd           TEXT                       -- NULL = giao toàn CN
trang_thai    TEXT NOT NULL DEFAULT 'cho_thuc_hien'
              -- 'cho_thuc_hien' | 'dang_thuc_hien' | 'hoan_thanh' | 'qua_han'
nguoi_tao     TEXT NOT NULL
ngay_tao      TEXT NOT NULL
ngay_deadline TEXT
ghi_chu_kh    TEXT
```

---

### 6. `nhiem_vu_ketqua`
```sql
id            INTEGER PRIMARY KEY AUTOINCREMENT
nhiem_vu_id   INTEGER NOT NULL REFERENCES nhiem_vu(id) ON DELETE CASCADE
pgd           TEXT NOT NULL
noi_dung_th   TEXT
so_lieu       TEXT
trang_thai    TEXT NOT NULL DEFAULT 'cho_duyet'
              -- 'cho_duyet' | 'da_duyet' | 'yeu_cau_bsung'
nguoi_nhap    TEXT NOT NULL
ngay_nhap     TEXT NOT NULL
nguoi_duyet   TEXT
ngay_duyet    TEXT
y_kien_duyet  TEXT
UNIQUE(nhiem_vu_id, pgd)
```

---

### 7. `tien_do_task`
```sql
id               INTEGER PRIMARY KEY AUTOINCREMENT
tieu_de          TEXT NOT NULL
mo_ta            TEXT
ngay_deadline    TEXT NOT NULL
ds_pgd           TEXT NOT NULL DEFAULT '[]'     -- JSON list tên PGD
loai             TEXT NOT NULL DEFAULT 'chung'   -- 'chung' | 'chuyen_de' | 'dot_xuat'
uu_tien          TEXT NOT NULL DEFAULT 'binh_thuong'
                 -- 'binh_thuong' | 'quan_trong' | 'khan_cap'
nguoi_tao        TEXT NOT NULL
ngay_tao         TEXT NOT NULL
trang_thai       TEXT NOT NULL DEFAULT 'dang_theo_doi'
                 -- 'dang_theo_doi' | 'hoan_thanh' | 'huy'
ghi_chu          TEXT
-- Migration columns (thêm sau):
cap_theo_doi     TEXT NOT NULL DEFAULT 'xa'     -- 'xa' | 'pgd'
ngay_bat_dau     TEXT
nguoi_phu_trach  TEXT
nguoi_thuc_hien_cn TEXT DEFAULT ''
cbtd_bien_hoa    TEXT DEFAULT ''
```
> Index: `idx_tiendo_deadline ON tien_do_task(ngay_deadline)`

---

### 8. `tien_do_ketqua`
```sql
id               INTEGER PRIMARY KEY AUTOINCREMENT
task_id          INTEGER NOT NULL REFERENCES tien_do_task(id) ON DELETE CASCADE
pgd              TEXT NOT NULL
ten_xa           TEXT NOT NULL
trang_thai       TEXT NOT NULL DEFAULT 'chua_thuc_hien'
                 -- 'chua_thuc_hien' | 'da_thuc_hien' | 'khong_ap_dung'
ngay_hoan_thanh  TEXT
ghi_chu          TEXT
nguoi_nhap       TEXT
ngay_nhap        TEXT
-- Migration:
loai_noi_dung    TEXT
UNIQUE(task_id, ten_xa)
```
> Index: `idx_tiendo_kq_task`, `idx_tiendo_kq_pgd ON (task_id, pgd)`

---

### 9. `hstd_snapshot`
```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
ky           TEXT    NOT NULL      -- 'YYYY-MM' hoặc 'YYYY-QN'
ten_pgd      TEXT    NOT NULL      -- '__CN__' cho tổng toàn CN
ma_ct        TEXT    NOT NULL DEFAULT 'ALL'   -- Mã chương trình hoặc 'ALL'
nguon_von    TEXT    NOT NULL DEFAULT 'ALL'   -- '1' TW | '2' ĐP | 'ALL'
tong_du_no   REAL    NOT NULL DEFAULT 0
du_no_th     REAL    NOT NULL DEFAULT 0
du_no_qh     REAL    NOT NULL DEFAULT 0
du_no_khoanh REAL    NOT NULL DEFAULT 0
so_ho        INTEGER NOT NULL DEFAULT 0
so_ku        INTEGER NOT NULL DEFAULT 0
gn_nam       REAL    NOT NULL DEFAULT 0
ngay_so_lieu TEXT                             -- ngày dữ liệu gốc
created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
created_by   TEXT    NOT NULL DEFAULT 'system'
UNIQUE(ky, ten_pgd, ma_ct, nguon_von)
```
> ⚠️ Upsert-safe: dùng `INSERT OR REPLACE` hoặc `ON CONFLICT DO UPDATE`

---

### 9a. `uy_thac_snapshot`
```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
ky           TEXT    NOT NULL
cap_tong_hop TEXT    NOT NULL  -- CN | PGD | XA | HOI | TO
ten_pgd      TEXT    NOT NULL DEFAULT '__ALL__'
ten_xa       TEXT    NOT NULL DEFAULT '__ALL__'
dvut         TEXT    NOT NULL DEFAULT '__ALL__'
ten_to       TEXT    NOT NULL DEFAULT '__ALL__'
tong_du_no   REAL    NOT NULL DEFAULT 0
du_no_qh     REAL    NOT NULL DEFAULT 0
lai_ton      REAL    NOT NULL DEFAULT 0
so_du_tg     REAL    NOT NULL DEFAULT 0
so_kh        INTEGER NOT NULL DEFAULT 0
so_ku        INTEGER NOT NULL DEFAULT 0
so_to        INTEGER NOT NULL DEFAULT 0
ngay_so_lieu TEXT
created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
created_by   TEXT    NOT NULL DEFAULT 'system'
UNIQUE(ky, cap_tong_hop, ten_pgd, ten_xa, dvut, ten_to)
```
> Tự tạo sau merge HSTD. Lưu riêng từng cấp tổng hợp để số KH/Tổ dùng `nunique()` đúng cấp, không cộng dồn từ cấp dưới.

---

### 10. `nq11_snapshot`
```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
ky           TEXT    NOT NULL
ten_pgd      TEXT    NOT NULL DEFAULT '__CN__'
tong_du_no   REAL    NOT NULL DEFAULT 0
no_th        REAL    NOT NULL DEFAULT 0
no_qh        REAL    NOT NULL DEFAULT 0
so_kh        INTEGER NOT NULL DEFAULT 0
gn_nam       REAL    NOT NULL DEFAULT 0
ngay_bc      TEXT
created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
created_by   TEXT    NOT NULL DEFAULT 'system'
UNIQUE(ky, ten_pgd)
```

---

### 11. `gqvl_snapshot`
```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
ky           TEXT    NOT NULL
ten_pgd      TEXT    NOT NULL DEFAULT '__CN__'
dn_th        REAL    NOT NULL DEFAULT 0
dn_qh        REAL    NOT NULL DEFAULT 0
dn_khoanh    REAL    NOT NULL DEFAULT 0
so_kh        INTEGER NOT NULL DEFAULT 0
gn_nam       REAL    NOT NULL DEFAULT 0
created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
created_by   TEXT    NOT NULL DEFAULT 'system'
UNIQUE(ky, ten_pgd)
```

---

### 12. `cdtotkvv_snapshot`
```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
ky           TEXT    NOT NULL
ten_pgd      TEXT    NOT NULL DEFAULT '__CN__'
so_to        INTEGER NOT NULL DEFAULT 0    -- tổng số tổ
so_tot       INTEGER NOT NULL DEFAULT 0    -- loại Tốt
so_kha       INTEGER NOT NULL DEFAULT 0    -- loại Khá
so_tb        INTEGER NOT NULL DEFAULT 0    -- loại Trung bình
so_yeu       INTEGER NOT NULL DEFAULT 0    -- loại Yếu
diem_tb      REAL    NOT NULL DEFAULT 0    -- điểm trung bình
created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
created_by   TEXT    NOT NULL DEFAULT 'system'
UNIQUE(ky, ten_pgd)
```

---

### 13. `qlnk_ket_qua` — Kết quả kiểm tra nợ khoanh
```sql
id                      INTEGER PRIMARY KEY AUTOINCREMENT
ma_mon_vay              TEXT    NOT NULL        -- = Số khế ước (HSTD)
ten_pgd                 TEXT    NOT NULL
ten_xa                  TEXT
ten_to_tkv              TEXT
ten_kh                  TEXT
ngay_bat_dau_khoanh     TEXT
so_thang_khoanh         INTEGER
so_quyet_dinh_khoanh    TEXT
ngay_kiem_tra           TEXT    NOT NULL
ngay_het_han_khoanh     TEXT                    -- Migration: thêm sau
can_bo_kiem_tra         TEXT
du_no_goc               REAL    DEFAULT 0       -- theo sổ sách
du_no_goc_khoanh        REAL    DEFAULT 0
so_tien_lai_con_no      REAL    DEFAULT 0
du_no_goc_thuc_te       REAL    DEFAULT 0       -- thực tế kiểm tra
du_no_khoanh_thuc_te    REAL    DEFAULT 0
so_tien_lai_thuc_te     REAL    DEFAULT 0
chenh_lech              REAL    DEFAULT 0
ly_do_chenh_lech        TEXT
thuc_trang_du_an        TEXT
tinh_hinh_khach_hang    TEXT
kha_nang_tra_no         TEXT
cam_ket_tra_no          TEXT
trang_thai              TEXT    NOT NULL DEFAULT 'luu_tam'
                        -- 'luu_tam' | 'da_duyet' | 'yeu_cau_sua'
nguoi_nhap              TEXT    NOT NULL
nguoi_phe_duyet         TEXT
ngay_phe_duyet          TEXT
created_at              TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
updated_at              TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
```
> Index: `idx_qlnk_kq_ma_mon`, `idx_qlnk_kq_pgd`, `idx_qlnk_kq_ngay_kt`, `idx_qlnk_kq_tt`

---

### 14. `qlnk_bo_sung` — Bổ sung thông tin khoanh
```sql
id                      INTEGER PRIMARY KEY AUTOINCREMENT
ma_mon_vay              TEXT    NOT NULL UNIQUE
ten_pgd                 TEXT    NOT NULL
ngay_bat_dau_khoanh     TEXT
so_thang_khoanh         INTEGER
so_quyet_dinh_khoanh    TEXT
ghi_chu                 TEXT
nguoi_cap_nhat          TEXT
updated_at              TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
```

---

### 15. `qlnk_ke_hoach` — Kế hoạch kiểm tra đoàn
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
ten_pgd         TEXT NOT NULL
nam             INTEGER NOT NULL DEFAULT 0      -- Migration
thanh_phan_doan TEXT NOT NULL DEFAULT '[]'      -- JSON list cán bộ — Migration
ds_phan_cong    TEXT NOT NULL DEFAULT '[]'      -- JSON list phân công — Migration
ghi_chu         TEXT                            -- Migration
ngay_kiem_tra   TEXT                            -- Migration
trang_thai      TEXT NOT NULL DEFAULT 'luu_tam' -- 'luu_tam' | 'da_duyet'
nguoi_lap       TEXT NOT NULL
nguoi_duyet     TEXT                            -- Migration
ngay_duyet      TEXT                            -- Migration
created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```
> Index: `idx_qlnk_kh_pgd`, `idx_qlnk_kh_tt`, `idx_qlnk_kh_ngay`

---

### 16. `mau_bieu_cv368` — Biểu mẫu báo cáo CV-368
```sql
id          INTEGER PRIMARY KEY AUTOINCREMENT
loai_mau    TEXT NOT NULL       -- 'bieu_01' | 'bieu_02' | ...
ten_pgd     TEXT NOT NULL
nam         INTEGER NOT NULL
dot         INTEGER DEFAULT 1   -- đợt kiểm tra trong năm
noi_dung    TEXT NOT NULL       -- JSON dữ liệu biểu mẫu
nguoi_lap   TEXT
ngay_lap    TEXT
ghi_chu     TEXT
created_at  TEXT DEFAULT (datetime('now','localtime'))
```
> Index: `idx_mbcv368_pgd_loai_nam ON (ten_pgd, loai_mau, nam)`

---

## File Parquet (cache — không phải SQLite)

| File | Nội dung | Tạo bởi |
|------|----------|---------|
| `cache/hstd.parquet` | HSTD toàn CN sau merge 22 PGD | `merge_du_lieu_toan_cn('hstd')` |
| `cache/nq11.parquet` | NQ11 sau merge | `merge_du_lieu_toan_cn('nq11')` |
| `cache/gqvl.parquet` | GQVL sau merge | `merge_du_lieu_toan_cn('gqvl')` |
| `cache/sk_gqvl.parquet` | Sao kê GQVL chi tiết (NQ11 dư nợ = 0) | `upload_service` — file riêng `SK_GQVL_du_lieu_tho.xlsx` |
| `pgd_data/{slug}/hstd_latest.xlsx` | File PGD tự upload | `luu_pgd_file()` |

> Đọc bằng `pd.read_parquet(path)` hoặc trực tiếp qua DuckDB SQL (`_duckdb_query()` trong `data/core.py`). Không commit các file này.

---

## Query mẫu thường dùng

```sql
-- 20 audit log gần nhất
SELECT ts, username, action, detail
FROM audit_log ORDER BY ts DESC LIMIT 20;

-- Tất cả key kv_store
SELECT key, length(value) AS size, updated_by, updated_at
FROM kv_store ORDER BY updated_at DESC;

-- Merge đã chạy chưa?
SELECT key, json_extract(value,'$.so_dong') AS so_dong,
       json_extract(value,'$.ngay_merge') AS ngay_merge
FROM kv_store WHERE key LIKE 'merge_meta%';

-- Tiến độ task hiện tại
SELECT t.tieu_de, t.ngay_deadline, t.trang_thai,
       COUNT(k.id) AS tong_xa,
       SUM(k.trang_thai='da_thuc_hien') AS hoan_thanh
FROM tien_do_task t
LEFT JOIN tien_do_ketqua k ON k.task_id = t.id
WHERE t.trang_thai = 'dang_theo_doi'
GROUP BY t.id ORDER BY t.ngay_deadline;

-- Snapshot dư nợ so sánh 2 kỳ
SELECT ten_pgd, ky, tong_du_no/1e6 AS du_no_ty
FROM hstd_snapshot
WHERE ma_ct='ALL' AND nguon_von='ALL'
  AND ky IN ('2026-04','2026-05')
ORDER BY ten_pgd, ky;
```
