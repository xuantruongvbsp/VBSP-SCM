import os
from pathlib import Path

# ── Thư mục gốc dự án (tự động xác định — không hardcode) ───────────────────
BASE_DIR = Path(__file__).parent.resolve()

# ── Thư mục con (tạo tự động nếu chưa có) ────────────────────────────────────
THU_MUC_DATA  = BASE_DIR / "data"
CACHE_DIR     = BASE_DIR / "cache"
PGD_DATA_DIR  = BASE_DIR / "pgd_data"
GQVL_PGD_DIR  = BASE_DIR / "gqvl_pgd"
TEMPLATES_DIR = BASE_DIR / "templates"

for _d in [THU_MUC_DATA, CACHE_DIR, PGD_DATA_DIR, GQVL_PGD_DIR, TEMPLATES_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── Tên file dữ liệu gốc ─────────────────────────────────────────────────────
TEN_FILE         = "HSTD_Du_lieu_tho.XLSX"
TEN_FILE_NQ11    = "SAO_KE_CT__NQ11_du_lieu_tho.XLSX"
TEN_FILE_DB      = "Dienbao_ht.xlsx"
TEN_FILE_DB_PREV = "Dienbao_prev.xlsx"

FILE_PATH         = str(THU_MUC_DATA / TEN_FILE)
FILE_PATH_NQ11    = str(THU_MUC_DATA / TEN_FILE_NQ11)
FILE_PATH_DB      = str(THU_MUC_DATA / TEN_FILE_DB)
FILE_PATH_DB_PREV = str(THU_MUC_DATA / TEN_FILE_DB_PREV)

# ── Tên file theo loại PGD ───────────────────────────────────────────────────
PGD_FILE_TYPES = {
    "hstd": "HSTD",
    "nq11": "NQ11",
    "gqvl": "GQVL",
}

# ── Cache Parquet ─────────────────────────────────────────────────────────────
CACHE_HSTD = str(CACHE_DIR / "hstd.parquet")
CACHE_NQ11 = str(CACHE_DIR / "nq11.parquet")

BASELINE_DIR = BASE_DIR / "data" / "baseline"
BASELINE_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_PGD_DIR = BASE_DIR / "data" / "baseline_pgd"
BASELINE_PGD_DIR.mkdir(parents=True, exist_ok=True)


def baseline_path(nam: int) -> str:
    """Đường dẫn file HSTD mốc 31/12 theo năm."""
    return str(BASELINE_DIR / f"HSTD_3112_{nam}.XLSX")


def baseline_cache(nam: int) -> str:
    return str(CACHE_DIR / f"hstd_baseline_{nam}.parquet")


def danh_sach_nam_baseline() -> list[int]:
    """Trả về list các năm đã có file baseline, sắp xếp giảm dần."""
    import os
    if not BASELINE_DIR.exists():
        return []
    files = list(BASELINE_DIR.glob("HSTD_3112_*.XLSX"))
    years = []
    for f in files:
        try:
            years.append(int(f.stem.split("_")[-1]))
        except ValueError:
            pass
    return sorted(years, reverse=True)


def baseline_pgd_path(ten_don_vi: str, nam: int) -> str:
    """Đường dẫn file HSTD mốc 31/12 theo đơn vị: data/baseline_pgd/{slug}/HSTD_3112_{nam}.XLSX"""
    from data.pgd import pgd_slug
    slug = pgd_slug(ten_don_vi)
    d = BASELINE_PGD_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return str(d / f"HSTD_3112_{nam}.XLSX")


def danh_sach_nam_baseline_pgd() -> list[int]:
    """Quét BASELINE_PGD_DIR tìm tất cả năm đã có ít nhất 1 đơn vị upload."""
    if not BASELINE_PGD_DIR.exists():
        return []
    years = set()
    for f in BASELINE_PGD_DIR.rglob("HSTD_3112_*.XLSX"):
        try:
            years.add(int(f.stem.split("_")[-1]))
        except ValueError:
            pass
    return sorted(years, reverse=True)


def trang_thai_baseline_pgd(nam: int) -> dict[str, bool]:
    """Trả về {ten_don_vi: co_file} cho 22 đơn vị theo năm."""
    ds = [DON_VI_CHI_NHANH] + DS_PGD
    return {dv: os.path.exists(baseline_pgd_path(dv, nam)) for dv in ds}


# Giữ lại hàm cũ để tương thích (sẽ xóa sau khi migrate xong)
def baseline_path_pgd(ten_pgd: str, nam: int) -> str:
    """Đường dẫn file HSTD mốc 31/12 theo PGD: pgd_data/{slug}/hstd_3112_{nam}.xlsx"""
    from data.pgd import thu_muc_pgd
    return str(thu_muc_pgd(ten_pgd) / f"hstd_3112_{nam}.xlsx")


# ── Danh sách chương trình KHTD (dùng cho tab_khtd) ─────────────────────────
# (ten_match, ten_hien_thi, nguon_von)
# ten_match: từ khóa để match với cột "Tên chương trình" trong HSTD
# nguon_von: "TW"=1, "DP"=2, "ALL"=cả hai
# ── Danh sách chương trình KHTD — cấu trúc 5-tuple ─────────────────────────
# (ma_key, ma_ct, ten_hien_thi, nguon_von, ten_match)
#   ma_key  : khóa nội bộ không đổi khi đổi tên hiển thị
#   ma_ct   : mã số chương trình (dùng match cột "Mã chương trình" trong HSTD)
#   ten_hien: tên hiển thị trên giao diện
#   nguon_von: "TW"=Trung ương, "DP"=Địa phương
#   ten_match: từ khóa match cột "Tên chương trình" trong HSTD (fallback)
CHUONG_TRINH_KHTD = [
    # (ma_key, ma_ct_hstd, ten_hien_thi, nguon_von, ten_match)
    # ma_ct_hstd lấy ĐÚNG từ cột "Mã chương trình" trong data/HSTD_Du_lieu_tho.XLSX

    # ── NGUỒN VỐN TRUNG ƯƠNG ──
    ("1_TW",   1,  "Cho vay ưu đãi hộ nghèo",                              "TW", "hộ nghèo"),
    ("2_TW",   2,  "Cho vay học sinh, sinh viên có hoàn cảnh khó khăn",    "TW", "học sinh sinh viên"),
    ("3_TW",   3,  "Cho vay giải quyết việc làm",                          "TW", "giải quyết việc làm"),
    ("4_TW",   4,  "Cho vay ĐTCS đi lao động có thời hạn ở nước ngoài",   "TW", "xuất khẩu lao động"),
    ("6_TW",   6,  "Cho vay nước sạch và vệ sinh môi trường nông thôn",   "TW", "nước sạch"),
    ("7_TW",   7,  "Cho vay hộ nghèo về nhà ở",                           "TW", "nhà ở hộ nghèo"),
    ("9_TW",   9,  "Cho vay hộ mới thoát nghèo theo QĐ 28",               "TW", "mới thoát nghèo"),
    ("12_TW", 12,  "Cho vay nhà ở xã hội theo Nghị định số 100",          "TW", "nhà ở xã hội"),
    ("17_TW", 17,  "Cho vay hộ đồng bào DTTS nghèo, đời sống khó khăn theo QĐ 755", "TW", "dân tộc thiểu số"),
    ("19_TW", 19,  "Cho vay hộ cận nghèo theo QĐ 15",                     "TW", "hộ cận nghèo"),
    ("26_TW", 26,  "Cho vay người chấp hành xong án phạt tù",             "TW", "chấp hành xong án"),
    ("10_TW", 10, "Cho vay hộ gia đình SXKD tại vùng khó khăn", "TW", "sxkd vùng khó khăn"),
    ("15_TW", 15, "Cho vay thương nhân vùng khó khăn",            "TW", "thương nhân vùng khó khăn"),
    ("21_TW", 21, "Cho vay hộ Dân tộc thiểu số QĐ 2085/2016",    "TW", "dân tộc thiểu số qđ 2085"),
    ("25_TW", 25, "Cho vay vùng dân tộc thiểu số và miền núi",   "TW", "vùng dân tộc thiểu số miền núi"),
    ("99_TW", 99,  "Cho vay khác",                                         "TW", "cho vay khác"),

    # ── NGUỒN VỐN ĐỊA PHƯƠNG ──
    ("1_DP",   1,  "Cho vay ưu đãi hộ nghèo (ĐP)",                        "DP", "hộ nghèo"),
    ("2_DP",   2,  "Cho vay học sinh, sinh viên (ĐP)",                     "DP", "học sinh sinh viên"),
    ("3_DP",   3,  "Cho vay giải quyết việc làm (ĐP)",                    "DP", "giải quyết việc làm"),
    ("6_DP",   6,  "Cho vay nước sạch và VSMT NT (ĐP)",                   "DP", "nước sạch"),
    ("9_DP",   9,  "Cho vay hộ mới thoát nghèo theo QĐ 28 (ĐP)",           "DP", "mới thoát nghèo"),
    ("12_DP", 12, "Cho vay nhà ở xã hội theo Nghị định số 100 (ĐP)",      "DP", "nhà ở xã hội"),
    ("17_DP", 17, "Cho vay hộ đồng bào DTTS nghèo theo QĐ 755 (ĐP)",     "DP", "dân tộc thiểu số"),
    ("26_DP", 26, "Cho vay người chấp hành xong án phạt tù (ĐP)",         "DP", "chấp hành xong án"),
    ("19_DP", 19,  "Cho vay hộ cận nghèo (ĐP)",                           "DP", "hộ cận nghèo"),
    ("10_DP", 10, "Cho vay hộ gia đình SXKD tại vùng khó khăn (ĐP)", "DP", "sxkd vùng khó khăn"),
    ("15_DP", 15, "Cho vay thương nhân vùng khó khăn (ĐP)",            "DP", "thương nhân vùng khó khăn"),
    ("21_DP", 21, "Cho vay hộ Dân tộc thiểu số QĐ 2085/2016 (ĐP)",    "DP", "dân tộc thiểu số qđ 2085"),
    ("25_DP", 25, "Cho vay vùng dân tộc thiểu số và miền núi (ĐP)",   "DP", "vùng dân tộc thiểu số miền núi"),
    ("99_DP", 99,  "Cho vay khác (ĐP)",                                    "DP", "cho vay khác"),
]

# Cấu trúc có bổ sung nhom để render bảng ma trận phân cấp (không đổi tuple gốc).
# nhom:
#   - "A": dòng nhóm cấp 1 (Kế hoạch)
#   - "I": nhóm nguồn vốn Trung ương
#   - "II": nhóm nguồn vốn Địa phương
#   - "con": chỉ tiêu chi tiết
CHUONG_TRINH_KHTD_NHOM = [
    {"ma_key": mk, "ma_ct": ma_ct, "ten_hien_thi": ten, "nguon_von": nv, "ten_match": ten_match, "nhom": ("I" if nv == "TW" else "II")}
    for mk, ma_ct, ten, nv, ten_match in CHUONG_TRINH_KHTD
]


# ── Tên chính thức (hiển thị) theo ma_key — dùng cho báo cáo ─────────────────
TEN_CHINH_THUC_CT = {row[0]: row[2] for row in CHUONG_TRINH_KHTD}

# Chỉ tiêu nguồn vốn (Phần I của KHTD)
NGUON_VON_KHTD = [
    "Tiền gửi tổ chức & cá nhân",
    "Huy động khác",
    "Nguồn vốn UTĐT địa phương",
]

# File JSON lưu kế hoạch tín dụng
FILE_KHTD    = str(BASE_DIR / "khtd.json")

# ── File GQVL (Sao kê Giải quyết Việc làm) ──────────────────────────────────
TEN_FILE_GQVL    = "SAO_KE_GQVL_du_lieu_tho.XLSX"
FILE_PATH_GQVL   = os.path.join(THU_MUC_DATA, TEN_FILE_GQVL)
CACHE_GQVL       = str(CACHE_DIR / "gqvl.parquet")

# File sao kê GQVL chi tiết (dùng để tra NQ11 cho món vay dư nợ = 0)
TEN_FILE_SK_GQVL  = "SK_GQVL_du_lieu_tho.xlsx"
FILE_PATH_SK_GQVL = str(THU_MUC_DATA / TEN_FILE_SK_GQVL)
CACHE_SK_GQVL     = str(CACHE_DIR / "sk_gqvl.parquet")

# Thư mục lưu file GQVL riêng từng PGD
# Tên file: gqvl_{ten_pgd_slug}.xlsx  (vd: gqvl_pgd_bien_hoa.xlsx)
GQVL_PGD_DIR  = BASE_DIR / "gqvl_pgd"


# ── Phân tầng GQVL theo PL NV + Mã NĐT ──────────────────────────────────────
# Dùng trong tab_khtd để tách GQVL thành 4 dòng riêng
# Cấu trúc: (ten_hien_thi, nguon_von, plnv, ma_ndt_contains)
#   nguon_von : "TW" hoặc "DP"
#   plnv      : 1=Quỹ QG/NSNN, 2=NHCSXH huy động, None=tất cả
#   ma_ndt    : chuỗi để match Mã nhà đầu tư, None=tất cả
# Đuôi mã NĐT cấp tỉnh — thêm mã mới vào đây nếu có
# Ví dụ: "0002662" = cấp tỉnh Đồng Nai
MA_NDT_CAP_TINH_DUOI = ["0002662"]

GQVL_PHAN_TANG = [
    ("GQVL TW — NHCSXH huy động",  "TW", 2, "cap_tinh_tw"),
    ("GQVL TW — NSNN (Quỹ QG TW)", "TW", 1, "cap_tinh_tw"),
    ("GQVL ĐP — Cấp tỉnh",         "DP", None, "cap_tinh"),
    ("GQVL ĐP — Cấp xã/khác",      "DP", None, "cap_xa"),
]

# Tên cột PL NV và Mã NĐT trong HSTD
COT_PL_NV  = "Phân loại NV"    # sau khi rename từ "PL NV"
COT_MA_NDT = "Mã nhà đầu tư"

# ── Tên cột GQVL (map sang tên chuẩn nội bộ) ─────────────────────────────────
GQVL_COT_MAP = {
    "Mã đơn vị":               "Mã PGD",
    "Mã xã":                   "Mã xã",
    "Tên xã":                  "Tên xã",
    "Tên Thôn":                "Tên thôn",
    "Mã tổ":                   "Mã tổ",
    "Tên tổ trưởng":           "Tên tổ trưởng",
    "Mã khách hàng":           "Mã KH",
    "Tên khách hàng":          "Tên KH",
    "Mã món vay":              "Số khế ước",
    "Ngày vay":                "Ngày vay",
    "Ngày đến hạn":            "Ngày ĐH lần đầu",
    "Unnamed: 12":             "Ngày ĐH sau cùng",
    "Thời hạn\nvay":          "Thời hạn vay",
    "Dư nợ\n trong hạn":      "Dư nợ trong hạn",
    "Dư nợ\nquá hạn":         "Dư nợ quá hạn",
    "Dư nợ\n khoanh":         "Dư nợ khoanh",
    "Nguồn\n vốn":            "Nguồn vốn",
    "PL NV":                   "Phân loại NV",
    "Tên phân loại nguồn vốn": "Tên phân loại NV",
    "Mã\nCAPQLV":             "Mã CAPQLV",
    "Mã PNKT":                 "Mã ngành SXKD",
    "Tên PNKT":                "Tên ngành SXKD",
    "Mã nhà đầu tư":           "Mã nhà đầu tư",
    "Tổng giải ngân":          "Tổng giải ngân",
    "Giải ngân trong năm":     "Giải ngân trong năm",
    "Dư tk":                   "Dư tài khoản",
    "NQ11":                    "NQ11",
}

# HSTD — DS cho vay / thu nợ trong năm (tab Tổng quan bảng PGD; khớp GQVL + alias Excel)
HSTD_DS_CHO_VAY_NAM_ALIASES = (
    GQVL_COT_MAP["Giải ngân trong năm"],
    "Giải ngân Năm",
    "Giải ngân năm",
)
HSTD_THU_NO_NAM_ALIASES = (
    "Thu nợ TH trong năm",
    "Thu nợ QH trong năm",
    "Thu nợ khoanh trong năm",
    "Thu nợ TH năm",
    "Thu nợ QH năm",
    "Thu nợ khoanh năm",
)

DB_HT_CACHE   = str(CACHE_DIR / "dienbao_ht.xlsx")
DB_PREV_CACHE = str(CACHE_DIR / "dienbao_prev.xlsx")

FILE_KEHOACH  = str(BASE_DIR / "kehoach.json")
FILE_CBTD     = str(BASE_DIR / "cbtd.json")
FILE_USERS    = str(BASE_DIR / "users.json")

# ── Tên cột HSTD ─────────────────────────────────────────────────────────────
COT_TEN_PGD    = "Tên PGD"
COT_MA_KH      = "Mã KH"
COT_TEN_KH     = "Tên KH"
COT_SO_KU      = "Số khế ước"
COT_NGAY_VAY   = "Ngày vay"
COT_NGAY_DH    = "Ngày ĐH theo hợp đồng"
COT_THOI_HAN   = "Thời hạn vay"
COT_LAI_SUAT   = "Lãi suất"
COT_MUC_VAY    = "Mức vay"
COT_DU_NO_TH   = "Dư nợ trong hạn"
COT_DU_NO_QH   = "Dư nợ quá hạn"
COT_TONG_DU_NO = "Tổng dư nợ"
COT_TEN_CT     = "Tên chương trình"
COT_TINH_TRANG = "Tình trạng món vay"
COT_DIA_CHI    = "Địa chỉ"
COT_SDT        = "Số điện thoại"
COT_NGAY_SL    = "Ngày số liệu"
COT_GOC_TRA    = "Gốc đã trả"

# ── Tên cột bổ sung (tra cứu nâng cao) ──────────────────────────────────────
COT_CMND          = "Số CMND"           # hoặc CCCD
COT_TEN_TO        = "Tên tổ"
COT_TEN_XA        = "Tên xã"
COT_TEN_THON      = "Tên thôn"
COT_NGUON_VON     = "Nguồn vốn"         # 1=TW, 2=ĐP
COT_MA_NHA_DAU_TU = "Mã nhà đầu tư"    # chỉ có khi ĐP
COT_MA_CHUONG_TRINH = "Mã chương trình"
COT_TEN_HSSV      = "Họ tên HSSV"       # tên học sinh sinh viên
COT_TEN_VC        = "Họ tên vợ/chồng"   # tên vợ / chồng

# ── Cột phân tích rủi ro & hoạt động ─────────────────────────────────────────
# Lãi tồn trong hạn — dùng để phát hiện "3 tháng không hoạt động"
COT_LAI_TON    = "Lãi tồn TH"
COT_LAI_TON_QH = "Lãi tồn QH"          # Lãi tồn quá hạn
COT_SO_DU_TG   = "Số dư tiền gửi 105"   # Số dư tiền gửi tiết kiệm TK105
# Lãi dự thu trong tháng — đại diện cho lãi 1 tháng của món vay
COT_LAI_THANG  = "Lãi DT trong tháng"
# Đơn vị ủy thác (Hội Phụ nữ / Nông dân / CCB / Thanh niên)
COT_DVUT       = "Tên ĐVUT"
# Phân loại nợ: E=Đủ tiêu chuẩn, D=Cần chú ý, C=Dưới tiêu chuẩn, ...
COT_PHAN_LOAI  = "Phân loại"
# Ngày giao dịch gần nhất (KU_NGAYGDGN từ core banking — cột 130 HSTD)
COT_NGAY_GDGN = "Ngày giao dịch gần nhất"

# Ngưỡng cảnh báo "không hoạt động": lãi tồn > N tháng lãi dự thu
NGUONG_KHONG_HĐ_THANG = 3   # 3 tháng

# ── Năm báo cáo ──────────────────────────────────────────────────────────────
NAM_HT   = "2026"
NAM_PREV = "2025"

# ── Thư mục templates văn bản ────────────────────────────────────────────────
import pathlib
BASE_DIR      = pathlib.Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"

# ── Phân quyền → Không gian làm việc ────────────────────────────────────────
# role "executive" dành riêng cho Ban Giám đốc (tạo trong Quản lý user)
WORKSPACE_MAP = {
    "executive": "🏛️ Lãnh đạo",
    "admin":     "⚙️ Điều hành",
    "manager":   "⚙️ Điều hành",
    "user":      "🛠️ Tác nghiệp",
}

# ── Roles cũ — giữ nguyên để tương thích ─────────────────────────────────────
ROLES_CU = ["executive", "admin", "manager", "user"]

# ── Roles mới — phân hệ 2 cấp ────────────────────────────────────────────────
ROLES_MOI = [
    "executive",
    "admin_cn", "manager_cn",      # Phân hệ Chi nhánh
    "admin_pgd", "manager_pgd", "user_pgd",  # Phân hệ PGD
]

# Tất cả roles hợp lệ (cũ + mới)
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

# ── Mapping cột dữ liệu ↔ tag trong file Word template ───────────────────────
# Thêm/sửa tại đây để hỗ trợ mẫu biểu mới mà không cần sửa code khác
TAG_MAP = {
    "{{ten_kh}}":        COT_TEN_KH,
    "{{ma_kh}}":         COT_MA_KH,
    "{{so_ku}}":         COT_SO_KU,
    "{{ngay_vay}}":      COT_NGAY_VAY,
    "{{ngay_dh}}":       COT_NGAY_DH,
    "{{thoi_han}}":      COT_THOI_HAN,
    "{{lai_suat}}":      COT_LAI_SUAT,
    "{{muc_vay}}":       COT_MUC_VAY,
    "{{du_no_th}}":      COT_DU_NO_TH,
    "{{no_qh}}":         COT_DU_NO_QH,
    "{{tong_du_no}}":    COT_TONG_DU_NO,
    "{{ten_ct}}":        COT_TEN_CT,
    "{{tinh_trang}}":    COT_TINH_TRANG,
    "{{dia_chi}}":       COT_DIA_CHI,
    "{{sdt}}":           COT_SDT,
    "{{ten_pgd}}":       COT_TEN_PGD,
    "{{ten_to}}":        "Tên tổ",
    "{{ten_xa}}":        "Tên xã",
    "{{cmnd}}":          "Số CMND",
    "{{goc_da_tra}}":    COT_GOC_TRA,
    
    # Tag cho điểm giao dịch
    "{{ten_dgd}}":       "ten_dgd",        # Tên điểm giao dịch
    "{{ds_thon}}":       "ds_thon",        # Danh sách thôn/ấp
}

# ── Tag mapping cho mẫu Thông báo KL giao ban ────────────────────────────────
# Bảng II — Kết quả thực hiện hoạt động ủy thác theo từng ĐVUT
# Tên ĐVUT thực tế trong HSTD:
#   "Hội nông dân"            → HND  (dòng 1 bảng)
#   "Hội liên hiệp phụ nữ"   → HPN  (dòng 2 bảng)
#   "Hội cựu chiến binh"      → HCCB (dòng 3 bảng)
#   "Đoàn thanh niên"         → ĐTN  (dòng 4 bảng)
# Cột cuối cùng bảng II: "Số khoản vay 3 tháng ko hoạt động"
TAG_MAP_KLGB = {
    # Thông tin PGD / ngày tháng (điền vào header)
    "{{ten_pgd}}":         COT_TEN_PGD,
    "{{ngay_in}}":         "ngay_in",       # tự động hôm nay
    "{{thang_bao_cao}}":   "thang_bao_cao",

    # Tổng toàn PGD (phần tổng kết)
    "{{tong_du_no}}":      COT_TONG_DU_NO,
    "{{du_no_trong_han}}": COT_DU_NO_TH,
    "{{du_no_qua_han}}":   COT_DU_NO_QH,
    "{{ty_le_nqh}}":       "ty_le_nqh",     # tính động

    # Cột cuối Bảng II — "Số khoản vay 3 tháng ko hoạt động"
    # Key khớp với tên ĐVUT thực tế trong file HSTD
    "{{mon_3m_hnd}}":      "mon_3m_Hội nông dân",
    "{{mon_3m_hpn}}":      "mon_3m_Hội liên hiệp phụ nữ",
    "{{mon_3m_hccb}}":     "mon_3m_Hội cựu chiến binh",
    "{{mon_3m_dtn}}":      "mon_3m_Đoàn thanh niên",
    "{{mon_3m_tong}}":     "mon_3m_tong",   # dòng Cộng

    # Cảnh báo amber (Đủ tiêu chuẩn có dấu hiệu chuyển sang 3m KHĐ)
    "{{mon_amber_tong}}":  "mon_amber_tong",
    
    # Tag cho điểm giao dịch trong báo cáo KLGB
    "{{ten_dgd}}":         "ten_dgd",      # Tên điểm giao dịch
    "{{ds_thon}}":         "ds_thon",      # Danh sách thôn/ấp
}

# Mapping tên ĐVUT thực tế → key tag (dùng trong _tinh_so_lieu_klgb)
DVUT_TAG_KEY = {
    "Hội nông dân":           "mon_3m_Hội nông dân",
    "Hội liên hiệp phụ nữ":   "mon_3m_Hội liên hiệp phụ nữ",
    "Hội cựu chiến binh":     "mon_3m_Hội cựu chiến binh",
    "Đoàn thanh niên":        "mon_3m_Đoàn thanh niên",
}

# ── Danh sách từ khóa nhận diện chương trình NQ11 ────────────────────────────
# Dùng để match với Tên chương trình hoặc Mã chương trình
NQ11_KEYWORDS = [
    "giải quyết việc làm",
    "gqvl",
    "nhà ở xã hội",
    "noxh",
    "hssv",
    "học sinh sinh viên",
    "máy tính",
    "sản xuất kinh doanh vùng khó khăn",
    "sxkd vkk",
    "nước sạch",
    "vệ sinh môi trường",
    "nsvsmt",
    "xuất khẩu lao động",
    "xklđ",
    "dân tộc thiểu số",
    "dtts",
    "nhà ở hộ nghèo",
]

# Nhãn nguồn vốn
NGUON_VON_LABEL = {1: "Trung ương", 2: "Địa phương", "1": "Trung ương", "2": "Địa phương"}

# ── Key kv_store cho registry chương trình toàn hệ thống ──────────────────────
KV_KEY_CT_REGISTRY_ALL = "ct_registry_all"

# ── Thông tin đơn vị ─────────────────────────────────────────────────────────
# "Hội sở Chi nhánh tỉnh" = PGD địa bàn Biên Hòa (key nội bộ, khớp cột Tên PGD trong HSTD)
# TEN_CHI_NHANH_HIEN_THI = nhãn hiển thị toàn Chi nhánh trên UI
DON_VI_CHI_NHANH = "Hội sở Chi nhánh tỉnh"
TEN_CHI_NHANH_HIEN_THI = "Chi nhánh NHCSXH tỉnh Đồng Nai"

# DS_PGD: 21 PGD (không bao gồm Hội sở Chi nhánh tỉnh vì đã có DON_VI_CHI_NHANH)
DS_PGD = [
    "PGD Long Thành",
    "PGD Trảng Bom",
    "PGD Long Khánh",
    "PGD Xuân Lộc",
    "PGD Định Quán",
    "PGD Vĩnh Cửu",
    "PGD Tân Phú",
    "PGD Thống Nhất",
    "PGD Cẩm Mỹ",
    "PGD Nhơn Trạch",
    "PGD Bình Long",
    "PGD Lộc Ninh",
    "PGD Bình Phước",
    "PGD Phước Long",
    "PGD Bù Đăng",
    "PGD Đồng Phú",
    "PGD Chơn Thành",
    "PGD Bù Đốp",
    "PGD Bù Gia Mập",
    "PGD Phú Riềng",
    "PGD Hớn Quản",
]

# ── Mapping Mã PGD (6 số) ↔ Tên PGD (dùng để xác thực file NQ11) ─────────────
# Mã "004601" là Hội sở Chi nhánh tỉnh (hardcode).
# Các mã còn lại được lấy từ cột "Mã PGD" trong file NQ11 thực tế.
# TODO: Xác nhận lại mã chính xác từ file NQ11/HSTD thực tế trên hệ thống.
MA_PGD_MAP: dict[str, str] = {
    "004601": "Hội sở Chi nhánh tỉnh",
    "004602": "PGD Long Thành",
    "004603": "PGD Trảng Bom",
    "004604": "PGD Long Khánh",
    "004605": "PGD Xuân Lộc",
    "004606": "PGD Định Quán",
    "004607": "PGD Vĩnh Cửu",
    "004608": "PGD Tân Phú",
    "004609": "PGD Thống Nhất",
    "004610": "PGD Cẩm Mỹ",
    "004611": "PGD Nhơn Trạch",
    "005024": "PGD Bình Long",
    "005025": "PGD Lộc Ninh",
    "005026": "PGD Bình Phước",
    "005027": "PGD Phước Long",
    "005028": "PGD Bù Đăng",
    "005029": "PGD Đồng Phú",
    "005034": "PGD Chơn Thành",
    "005036": "PGD Bù Đốp",
    "005037": "PGD Bù Gia Mập",
    "005038": "PGD Phú Riềng",
    "005039": "PGD Hớn Quản",
}

# Mapping ngược: Tên PGD → Mã PGD (tra cứu nhanh)
TEN_PGD_TO_MA: dict[str, str] = {v: k for k, v in MA_PGD_MAP.items()}

# Cấu trúc phân cấp: PGD → danh sách xã/phường trực thuộc
PGD_XA_MAP: dict[str, list[str]] = {
    "Hội sở Chi nhánh tỉnh": [
        "Phường Phước Tân", "Phường Biên Hòa", "Phường Trấn Biên",
        "Phường Long Hưng", "Phường Long Bình", "Phường Trảng Dài",
        "Phường Tam Phước", "Phường Hố Nai", "Phường Tam Hiệp",
    ],
    "PGD Long Thành": [
        "Xã Phước Thái", "Xã An Phước", "Xã Bình An",
        "Xã Long Thành", "Xã Long Phước",
    ],
    "PGD Trảng Bom": [
        "Xã An Viễn", "Xã Hưng Thịnh", "Xã Trảng Bom",
        "Xã Bầu Hàm", "Xã Bình Minh",
    ],
    "PGD Long Khánh": [
        "Phường Bảo Vinh", "Phường Xuân Lập", "Phường Xuân Khánh",
        "Phường Bình Lộc", "Phường Hàng Gòn",
    ],
    "PGD Xuân Lộc": [
        "Xã Xuân Thành", "Xã Xuân Bắc", "Xã Xuân Định",
        "Xã Xuân Lộc", "Xã Xuân Phú", "Xã Xuân Hòa",
    ],
    "PGD Định Quán": [
        "Xã Phú Vinh", "Xã Định Quán", "Xã Thanh Sơn",
        "Xã Phú Hòa", "Xã La Ngà",
    ],
    "PGD Vĩnh Cửu": [
        "Xã Tân An", "Phường Tân Triều", "Xã Trị An", "Xã Phú Lý",
    ],
    "PGD Tân Phú": [
        "Xã Phú Lâm", "Xã Nam Cát Tiên", "Xã Tân Phú",
        "Xã Tà Lài", "Xã Đak Lua",
    ],
    "PGD Thống Nhất": [
        "Xã Dầu Giây", "Xã Thống Nhất", "Xã Gia Kiệm",
    ],
    "PGD Cẩm Mỹ": [
        "Xã Xuân Quế", "Xã Xuân Đường", "Xã Cẩm Mỹ",
        "Xã Xuân Đông", "Xã Sông Ray",
    ],
    "PGD Nhơn Trạch": [
        "Xã Đại Phước", "Xã Nhơn Trạch", "Xã Phước An",
    ],
    "PGD Bình Long": [
        "Phường An Lộc", "Phường Bình Long",
    ],
    "PGD Lộc Ninh": [
        "Xã Lộc Tấn", "Xã Lộc Thạnh", "Xã Lộc Thành",
        "Xã Lộc Quang", "Xã Lộc Ninh", "Xã Lộc Hưng",
    ],
    "PGD Bình Phước": [
        "Phường Đồng Xoài", "Phường Bình Phước",
    ],
    "PGD Phước Long": [
        "Phường Phước Long", "Phường Phước Bình",
    ],
    "PGD Bù Đăng": [
        "Xã Thọ Sơn", "Xã Bù Đăng", "Xã Đăk Nhau",
        "Xã Phước Sơn", "Xã Bom Bo", "Xã Nghĩa Trung",
    ],
    "PGD Đồng Phú": [
        "Xã Thuận Lợi", "Xã Đồng Phú", "Xã Đồng Tâm", "Xã Tân Lợi",
    ],
    "PGD Chơn Thành": [
        "Phường Minh Hưng", "Xã Nha Bích", "Phường Chơn Thành",
    ],
    "PGD Bù Đốp": [
        "Xã Hưng Phước", "Xã Thiện Hưng", "Xã Tân Tiến",
    ],
    "PGD Bù Gia Mập": [
        "Xã Bù Gia Mập", "Xã Phú Nghĩa", "Xã Đa Kia", "Xã Đăk Ơ",
    ],
    "PGD Phú Riềng": [
        "Xã Bình Tân", "Xã Long Hà", "Xã Phú Trung", "Xã Phú Riềng",
    ],
    "PGD Hớn Quản": [
        "Xã Minh Đức", "Xã Tân Hưng", "Xã Tân Khai", "Xã Tân Quan",
    ],
}

# Danh sách xã phẳng (dùng cho dropdown/search toàn hệ thống)
DS_XA = [xa for ds in PGD_XA_MAP.values() for xa in ds]

# Tra cứu ngược: xã → PGD
XA_TO_PGD: dict[str, str] = {
    xa: pgd
    for pgd, ds in PGD_XA_MAP.items()
    for xa in ds
}

# ── Ngưỡng cảnh báo upload dữ liệu cũ (đơn vị: ngày) ────────────────────────
# Nếu file của một đơn vị cũ hơn ngưỡng → hiện badge ⚠️
UPLOAD_CANH_BAO_NGAY: dict[str, int] = {
    "hstd":     3,   # HSTD biến động hàng ngày → cảnh báo sau 3 ngày
    "nq11":     3,   # NQ11 tương tự
    "gqvl":     7,   # GQVL ít biến động hơn → cảnh báo sau 7 ngày
    "cdtotkvv": 35,  # Chấm điểm Tổ TK&VV upload theo tháng
}

# ── Chấm điểm Tổ TK&VV ───────────────────────────────────────────────────────
CDTOTKVV_DIR = BASE_DIR / "data" / "cdtotkvv"
CDTOTKVV_DIR.mkdir(parents=True, exist_ok=True)

# Các cột của file chấm điểm Tổ TK&VV (thứ tự cột A→T, index 0-based)
CDTOTKVV_COLS = [
    "stt", "ma_dv", "ten_dv", "ma_xa", "ten_xa", "ma_to",
    "ten_to_truong", "dvut", "loai_to", "du_no", "so_du_tk",
    "diem_gdtx", "diem_nqh", "diem_thu_no", "diem_thu_lai",
    "diem_tv_tiengui", "diem_ds_tg", "tong_diem", "xep_loai", "tinh_trang"
]
CDTOTKVV_DATA_ROW_START = 10  # dữ liệu bắt đầu từ row index 10 (0-based)

# ── Mapping tên xã: Config (có "Xã") → HSTD (không có "Xã") ─────────────────────
XA_NAME_MAP = {
    "Xã La Ngà": "La Ngà",
    "Xã Phú Hòa": "Phú Hòa",
    "Xã Phú Vinh": "Phú Vinh",
    "Xã Thanh Sơn": "Thanh Sơn",
    "Xã Định Quán": "Định Quán",
}


def tim_ten_xa_trong_hstd(ten_xa_config: str) -> str:
    """
    Map tên xã từ config sang tên trong HSTD.
    Xử lý: Config có 'Xã/Phường' nhưng HSTD không có.
    """
    # Thử exact match trước
    if ten_xa_config in XA_NAME_MAP:
        return XA_NAME_MAP[ten_xa_config]

    # Thử bỏ prefix 'Xã'/'Phường'/'Thị trấn'
    for prefix in ["Xã ", "Phường ", "Thị trấn ", "TT "]:
        if ten_xa_config.startswith(prefix):
            return ten_xa_config[len(prefix):]

    # Không match → trả nguyên gốc
    return ten_xa_config

DCGIAM_SHEET_ID  = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
DCGIAM_CRED_FILE = str(BASE_DIR / "credentials.json")
