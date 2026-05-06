# Prompt Trae — Unittest Toàn Bộ VBSP-SCM

> Copy toàn bộ nội dung bên dưới vào chat Trae.
> Trae sẽ tạo file, chạy test, báo kết quả.
> Bấm **Keep All** sau khi xong.

---

```
Viết unittest toàn bộ hệ thống VBSP-SCM.
Tạo file: tests/test_vbsp_scm_full.py

=======================================================
QUY ƯỚC CHUNG — ĐỌC TRƯỚC KHI VIẾT BẤT KỲ TEST NÀO
=======================================================

1. DB IN-MEMORY — bắt buộc:
   Đặt ở đầu file, TRƯỚC mọi import:
       import os
       os.environ["VBSP_SCM_DB_PATH"] = ":memory:"

2. setUp() mỗi TestCase phải reset DB sạch:
       import db
       db.reset_conn()
       db.init_db()

3. KHÔNG import streamlit trực tiếp trong test.
   Các module cần st → đã có sẵn trong project, không cần mock st,
   chỉ mock các sub-module thiếu (data.core, services.data_quality...).

4. Fixture dữ liệu:
   - Tên xã KHÔNG có tiền tố "Xã/Phường" (vd: "Phước Thái", "An Phước")
     vì data_quality validate domain theo config có tiền tố →
     dùng tên không prefix để bypass domain check trong test
   - Tiền tệ lưu VND (×1_000_000), không phải triệu

5. Chạy: pytest tests/test_vbsp_scm_full.py -v

=======================================================
MODULE 1 — db.py  (class TestDb)
=======================================================

Test kv_store:
  - ghi_kv + doc_kv: lưu dict → đọc lại bằng giá trị gốc
  - doc_kv key không tồn tại → None
  - doc_kv có default → trả về default
  - ghi_kv ghi đè giá trị cũ
  - updated_by lưu đúng username
  - ghi_kv các kiểu: list, int lớn, chuỗi Unicode, nested dict
  - list_kv_prefix chỉ trả key đúng tiền tố
  - list_kv_prefix không match → list rỗng
  - doc_kv_prefix trả {key: value} đầy đủ
  - doc_kv_nhieu trả dict chỉ key tồn tại
  - doc_kv_nhieu list rỗng → {} không raise

Test audit_log:
  - ghi_audit không raise
  - ghi_audit lưu đúng username / action / detail
  - ghi_audit nhiều lần → nhiều bản ghi riêng (autoincrement)
  - ghi_audit detail rỗng không lỗi
  - ts là chuỗi ISO datetime hợp lệ (datetime.fromisoformat không raise)

Test init_db:
  - Tạo đủ bảng: kv_store, users, audit_log, nhiem_vu
  - Gọi 2 lần không raise (CREATE TABLE IF NOT EXISTS)

=======================================================
MODULE 2 — auth.py  (class TestAuth)
=======================================================

setUp: seed 4 user bằng INSERT trực tiếp vào db.get_conn()
  - nv_pgd   / pass123 / role=user    / pgd="PGD Long Thành"
  - truong   / pass456 / role=manager / pgd="PGD Long Thành"
  - admin_hn / pass789 / role=admin   / pgd=None
  - bgd      / bgd2026 / role=executive / pgd=None

Test ma_hoa / kiem_tra:
  - Hash khác plaintext, bắt đầu "$2b$"
  - kiem_tra đúng mật khẩu → True
  - kiem_tra sai mật khẩu → False
  - 2 lần hash cùng pw → 2 hash khác nhau (bcrypt salt)
  - Cả 2 hash đều verify được

Test dang_nhap:
  - Đúng → (True, dict) với role và pgd đúng
  - Sai mật khẩu → (False, None)
  - Username không tồn tại → (False, None)
  - Username viết HOA → vẫn khớp (strip().lower())
  - admin → pgd là None
  - Thành công → tạo audit_log action='login'
  - Thất bại → tạo audit_log action='login_failed'

Test doc_users:
  - Trả về dict, len > 0
  - Có đủ 4 role: user, manager, admin, executive

=======================================================
MODULE 3 — utils.py  (class TestUtils)
=======================================================

Không cần DB. Import trực tiếp:
    from utils import fmt, fmt_tien, fmt_ty, fmt_pct, fmt_so, vn

Test fmt (hiển thị tiền tệ):
  - fmt(0) → "0"
  - fmt(1_000_000) → "1" (1 triệu)
  - fmt(1_500_000) → "1,5" hoặc "1.5" (1.5 triệu)
  - fmt(1_000_000_000) → "1.000" hoặc "1,000" (1 tỷ)
  - fmt(None) → "0" hoặc "-" (không raise)
  - fmt(-500_000) → có dấu âm

Test vn (làm tròn VN):
  - vn(1.234) → float, làm tròn 1 chữ số
  - vn(0) → 0.0 không raise

Test fmt_pct:
  - fmt_pct(0.856) → có "%" trong kết quả hoặc là "85.6"
  - fmt_pct(0) → "0" hoặc "0%" không raise

Test fmt_so:
  - fmt_so(1234) → có dấu phân cách hàng nghìn hoặc "1234"
  - fmt_so(None) → không raise

Test ten_file_xuat:
  - from utils import ten_file_xuat
  - ten_file_xuat("bao_cao") → chuỗi kết thúc ".xlsx"
  - ten_file_xuat("bao_cao", "pdf") → kết thúc ".pdf"
  - Kết quả chứa "bao_cao"

=======================================================
MODULE 4 — config.py  (class TestConfig)
=======================================================

Import: from config import DS_PGD, PGD_XA_MAP, DS_XA, XA_TO_PGD, MA_PGD_MAP

Test cấu trúc dữ liệu:
  - DS_PGD là list, len == 21
  - Tất cả DS_PGD bắt đầu bằng "PGD "
  - PGD_XA_MAP là dict, len == 21
  - Mỗi key trong PGD_XA_MAP là PGD trong DS_PGD
  - DS_XA là list, len == 95
  - Không có xã trùng trong DS_XA

Test XA_TO_PGD (tra cứu ngược):
  - Mọi xã trong DS_XA đều có entry trong XA_TO_PGD
  - XA_TO_PGD[xa] là PGD trong DS_PGD

Test MA_PGD_MAP:
  - Là dict, không rỗng
  - Mọi value trong MA_PGD_MAP là PGD trong DS_PGD

Test tim_ten_xa_trong_hstd:
  - from config import tim_ten_xa_trong_hstd
  - "Xã Long Thành" → "Long Thành" (bỏ prefix)
  - "Phường Biên Hòa" → "Biên Hòa"
  - "Thị trấn Vĩnh An" → "Vĩnh An"
  - Tên không có prefix → trả nguyên

=======================================================
MODULE 5 — data_quality.py  (class TestDataQuality)
=======================================================

Fixture _df_hstd():
    pd.DataFrame({
        "Số khế ước":      ["KU001", "KU002"],
        "Tên PGD":         ["PGD Long Thành", "PGD Long Thành"],
        "Tên xã":          ["Phước Thái", "An Phước"],
        "Nguồn vốn":       [1, 2],
        "Dư nợ trong hạn": [1_000_000, 2_000_000],
        "Dư nợ quá hạn":   [0, 0],
        "Tổng dư nợ":      [1_000_000, 2_000_000],
    })

Test kiem_tra_chat_luong("hstd"):
  - Hợp lệ → so_loi == 0
  - Trả về DataQualityResult
  - result.errors là list
  - report chứa key "tong_dong" == len(df)
  - report chứa key "loai" == "hstd"
  - report chứa key "ti_le_dat_chuan" trong [0.0, 100.0]

Test phát hiện lỗi:
  - Số khế ước trùng → so_loi > 0, duplicate_rows > 0
  - Tên xã null → so_loi > 0
  - Số khế ước null → so_loi > 0
  - Dư nợ trong hạn âm → so_loi > 0
  - Dư nợ quá hạn âm → so_loi > 0

Test chuan_hoa_ma_don_vi:
  - Mã PGD "004602" → thêm cột "Tên PGD" = "PGD Long Thành"
  - DataFrame đã có "Tên PGD" → không raise

Test edge cases:
  - DataFrame 0 dòng → không raise
  - loai="unknown" → không raise

=======================================================
MODULE 6 — khtd.py  (class TestKhtd)
=======================================================

setUp: reset DB + init_db.
Import: from khtd import doc_khtd, luu_khtd, doc_kehoach, luu_kehoach, doc_cbtd, luu_cbtd

Test luu_khtd / doc_khtd:
  - Lưu dict → đọc lại đúng
  - Ghi đè được
  - doc_khtd trả về dict (không raise khi chưa có data)

Test luu_kehoach / doc_kehoach:
  - Lưu kehoach toàn CN → đọc lại đúng
  - Lưu kehoach theo PGD: luu_kehoach(data, ten_pgd="PGD Long Thành") → doc_kehoach("PGD Long Thành") đúng
  - doc_kehoach(pgd) không tồn tại → trả dict rỗng hoặc None (không raise)

Test luu_cbtd / doc_cbtd:
  - Lưu list CBTD → đọc lại đúng
  - doc_cbtd khi chưa có → trả dict rỗng (không raise)

=======================================================
MODULE 7 — khtd_service.py  (class TestKhtdService)
=======================================================

Chỉ test các hàm PURE LOGIC không cần Google Sheets.
Import:
    from khtd_service import (
        _so_trieu_tu_oa, _kv_key, kv_key_dot,
        _parse_key_suffix, _dot_sort_key, ds_slug
    )

Test _so_trieu_tu_oa (parse số từ Excel):
  - None → 0.0
  - "" → 0.0
  - "nan" → 0.0
  - "1,500" → 1500.0 (dấu phẩy ngàn)
  - " 500 " → 500.0 (có khoảng trắng)
  - 250 (int) → 250.0
  - "abc" → 0.0 (không raise)

Test _kv_key:
  - _kv_key("pgd_bien_hoa", 2026, 3, "dot1")
    → "khtd_pgd_bien_hoa_2026_03_dot1"
  - tháng 1 chữ số → tự đệm 0: "...2026_01_..."
  - _kv_key == kv_key_dot (cùng kết quả)

Test _parse_key_suffix:
  - "2026_03_dot1" → (2026, "03", "dot1")
  - "2026_12_dau_nam" → (2026, "12", "dau_nam")
  - "invalid" → None

Test _dot_sort_key:
  - "dot1" < "dot2" (sort đúng thứ tự)
  - "dot10" > "dot9"
  - Chuỗi tự do → không raise

Test ds_slug:
  - Trả về list, len == 22 (hoi_so + 21 PGD)
  - "hoi_so" là phần tử đầu tiên
  - Mỗi phần tử chỉ có chữ thường + số + "_"

=======================================================
MODULE 8 — ct_discovery.py  (class TestCtDiscovery)
=======================================================

setUp: reset DB + init_db.
Import: from ct_discovery import _slug, doc_ct_registry, ghi_ct_registry

Test _slug:
  - "PGD Long Thành" → "pgd_long_thanh"
  - "PGD Biên Hòa"   → "pgd_bien_hoa"
  - "PGD Định Quán"  → "pgd_dinh_quan"
  - Kết quả chỉ có a-z, 0-9, "_"

Test doc_ct_registry / ghi_ct_registry:
  - Chưa ghi → doc_ct_registry() trả {} (không raise)
  - Ghi registry PGD cụ thể → đọc lại đúng
  - Ghi toàn hệ thống (pgd=None) → đọc lại với pgd=None
  - ghi_ct_registry MERGE (không xóa key cũ):
    Ghi {"HVN": [...]} rồi ghi {"HND": [...]}
    → đọc lại có cả HVN và HND
  - ghi_ct_registry ghi đúng updated_by vào kv_store

=======================================================
MODULE 9 — upload_service.py  (class TestUploadService)
=======================================================

setUpClass: mock các sub-module thiếu TRƯỚC khi import:

    import types, sys
    # mock data.core
    mc = types.ModuleType("data.core")
    mc.ts_file = lambda *a, **kw: 0.0
    mc.excel_to_parquet = lambda *a, **kw: None
    sys.modules.setdefault("data", types.ModuleType("data"))
    sys.modules["data.core"] = mc
    # mock data.pgd
    mp = types.ModuleType("data.pgd")
    mp.duong_dan_pgd = lambda *a, **kw: "/tmp/test.xlsx"
    sys.modules["data.pgd"] = mp
    # mock services.data_quality
    ms = types.ModuleType("services")
    md = types.ModuleType("services.data_quality")
    md.kiem_tra_chat_luong = lambda df, loai: None
    sys.modules.setdefault("services", ms)
    sys.modules["services.data_quality"] = md
    # import
    import importlib
    cls.us = importlib.import_module("upload_service")

Test kiem_tra_file:
  - .xlsx ≥ 1KB → (True, "OK")
  - .xls ≥ 1KB → (True, ...)
  - .XLSX hoa ≥ 1KB → (True, ...)
  - .txt → (False, msg có "định dạng" hoặc "xlsx")
  - .pdf → (False, ...)
  - .xlsx nhưng < 1KB → (False, msg có "nhỏ")
  - bytes rỗng → (False, ...)

Test KetQuaUpload:
  - KetQuaUpload(True, "OK", "/tmp/f.xlsx"):
    thanh_cong=True, thong_bao="OK", duong_dan="/tmp/f.xlsx"
  - KetQuaUpload(False, "Lỗi"):
    thanh_cong=False, duong_dan="" (default)
  - KetQuaUpload là dataclass → có __repr__ không raise

=======================================================
MODULE 10 — report_service.py  (class TestReportService)
=======================================================

Import: from report_service import xuat_bao_cao, ten_file_bao_cao, xuat_sheet_don
Import pandas và openpyxl để verify output.

Test ten_file_bao_cao:
  - Kết quả kết thúc ".xlsx"
  - Chứa prefix truyền vào
  - ten_file_bao_cao("bao_cao", "pdf") kết thúc ".pdf"

Test xuat_sheet_don:
  - import pandas as pd
    df = pd.DataFrame({"A": [1,2,3], "B": ["x","y","z"]})
    result = xuat_sheet_don(df, "Test Report", "admin")
  - Trả về bytes
  - len(result) > 0
  - Bytes là file xlsx hợp lệ:
    from io import BytesIO; import openpyxl
    wb = openpyxl.load_workbook(BytesIO(result))
    (không raise)

Test xuat_bao_cao (nhiều sheet):
  - sheets = {"Sheet1": df1, "Sheet2": df2}
  - result = xuat_bao_cao(sheets, "Báo cáo KHTD", "admin")
  - Trả về bytes, len > 0
  - File xlsx hợp lệ, có ≥ 2 sheets

=======================================================
MODULE 11 — giao_ban.py  (class TestGiaoBan)
=======================================================

Import: from giao_ban import tinh_so_lieu_van_xuoi, loc_theo_xa
Import config để lấy tên cột đúng.

Fixture df_xa:
    from config import (COT_TONG_DU_NO, COT_DU_NO_QH, COT_MA_KH,
                        COT_TEN_XA, COT_TEN_TO)
    df = pd.DataFrame({
        COT_TONG_DU_NO: [10_000_000, 5_000_000, 3_000_000],
        COT_DU_NO_QH:   [0, 500_000, 0],
        COT_MA_KH:      ["KH001", "KH002", "KH003"],
        COT_TEN_XA:     ["Phước Thái"] * 3,
        COT_TEN_TO:     ["Tổ 1", "Tổ 1", "Tổ 2"],
    })

Test tinh_so_lieu_van_xuoi:
  - Trả về dict
  - "{{tong_du_no}}" có trong keys
  - "{{so_kh}}" == "3"
  - "{{du_no_qh}}" có trong keys
  - "{{ty_le_nqh}}" là chuỗi số hợp lệ (float(val) không raise)
  - "{{tang_giam_thang}}" là "tăng" hoặc "giảm"
  - df_baseline=None không raise
  - DataFrame rỗng không raise

Test loc_theo_xa:
  - loc_theo_xa(df, "Phước Thái") trả về df đầy đủ (3 dòng)
  - loc_theo_xa(df, "Không tồn tại") trả về DataFrame rỗng

=======================================================
MODULE 12 — pgd.py  (class TestPgd)
=======================================================

Import: from pgd import pgd_slug, thu_muc_pgd, duong_dan_pgd, kiem_tra_file_ton_tai_pgd

Test pgd_slug:
  - "PGD Long Thành" → "pgd_long_thanh"
  - "PGD Biên Hòa"   → "pgd_bien_hoa"
  - "Hội sở"         → "hoi_so"
  - Kết quả chỉ có a-z, 0-9, "_"

Test thu_muc_pgd:
  - Trả về Path object
  - str(path) chứa "pgd_long_thanh"

Test duong_dan_pgd:
  - duong_dan_pgd("PGD Long Thành", "hstd") → chuỗi kết thúc ".xlsx"
  - duong_dan_pgd("PGD Long Thành", "nq11") → chuỗi khác hstd
  - Không raise với bất kỳ pgd hợp lệ

Test kiem_tra_file_ton_tai_pgd:
  - PGD chưa upload → trả False (không raise)
  - Trả về bool

=======================================================
MODULE 13 — data_priority_service.py  (class TestDataPriorityService)
=======================================================

setUp: reset DB + init_db.
Import: from data_priority_service import (
    kiem_tra_nguon_uu_tien, lay_thong_tin_nguon_hien_tai
)

Test kiem_tra_nguon_uu_tien:
  - Trả về dict
  - Có key "nguon" trong result
  - Không raise với PGD bất kỳ trong DS_PGD
  - Không raise với loai_file: "hstd", "nq11", "gqvl"

Test lay_thong_tin_nguon_hien_tai:
  - Trả về dict không raise
  - Có key "ten_don_vi" trong result

=======================================================
YÊU CẦU KỸ THUẬT
=======================================================
- Dùng unittest.TestCase, class riêng cho từng module
- setUp() reset DB (nếu dùng DB)
- Mỗi test method có docstring tiếng Việt 1 dòng
- subTest() cho các test tham số hoá (vd: test nhiều giá trị fmt)
- skipUnless nếu module có thể không import được:
    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl not installed")
- Tổng target: 80+ test cases
- Sau khi tạo file → chạy luôn: pytest tests/test_vbsp_scm_full.py -v
- Báo kết quả: X passed / Y failed, liệt kê từng failed test
```
