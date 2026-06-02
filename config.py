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


def baseline_pgd_path_loai(ten_don_vi: str, nam: int, loai: str) -> str:
    """Đường dẫn file baseline 31/12 theo đơn vị và loại: data/baseline_pgd/{slug}/{LOAI}_3112_{nam}.XLSX"""
    from data.pgd import pgd_slug
    slug = pgd_slug(ten_don_vi)
    d = BASELINE_PGD_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return str(d / f"{loai.upper()}_3112_{nam}.XLSX")


LOAI_BASELINE = ("hstd", "nq11", "gqvl", "cdtotkvv")


def danh_sach_nam_baseline_pgd() -> list[int]:
    """Quét BASELINE_PGD_DIR tìm tất cả năm đã có ít nhất 1 đơn vị upload."""
    if not BASELINE_PGD_DIR.exists():
        return []
    years = set()
    for loai in LOAI_BASELINE:
        for f in BASELINE_PGD_DIR.rglob(f"{loai.upper()}_3112_*.XLSX"):
            try:
                years.add(int(f.stem.split("_")[-1]))
            except ValueError:
                pass
    # Giữ tương thích với tên file cũ HSTD_3112_*.XLSX
    for f in BASELINE_PGD_DIR.rglob("HSTD_3112_*.XLSX"):
        try:
            years.add(int(f.stem.split("_")[-1]))
        except ValueError:
            pass
    return sorted(years, reverse=True)


def trang_thai_baseline_pgd(nam: int) -> dict[str, bool]:
    """Trả về {ten_don_vi: co_file_hstd} cho 22 đơn vị theo năm."""
    ds = [DON_VI_CHI_NHANH] + DS_PGD
    return {dv: os.path.exists(baseline_pgd_path(dv, nam)) for dv in ds}


def trang_thai_baseline_pgd_loai(nam: int, loai: str) -> dict[str, bool]:
    """Trả về {ten_don_vi: co_file} cho 22 đơn vị theo năm và loại."""
    ds = [DON_VI_CHI_NHANH] + DS_PGD
    return {dv: os.path.exists(baseline_pgd_path_loai(dv, nam, loai)) for dv in ds}


def baseline_cache_loai(nam: int, loai: str) -> str:
    """Đường dẫn cache parquet tổng hợp baseline theo năm và loại."""
    return str(CACHE_DIR / f"{loai.lower()}_baseline_{nam}.parquet")


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
    ("3_TW_NHCSXH", 3, "GQVL TW — NHCSXH huy động",  "TW", "GQVL"),
    ("3_TW_NSNN",   3, "GQVL TW — NSNN/Quỹ QG TW",   "TW", "GQVL"),
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
    ("3_DP_TINH",   3, "GQVL ĐP — Cấp tỉnh",          "DP", "GQVL"),
    ("3_DP_XA",     3, "GQVL ĐP — Cấp xã/khác",       "DP", "GQVL"),
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

# ── GQVL phân tầng: key giao KH và key theo dõi TH ───────────────────────────
# 3 key giao KH qua GSheet (CN tỉnh không giao 3_DP_XA)
GQVL_MA_KEY_GIAO = frozenset({"3_TW_NHCSXH", "3_TW_NSNN", "3_DP_TINH"})

# 4 key theo dõi TH từ HSTD (đủ 4 nhóm kể cả 3_DP_XA)
GQVL_MA_KEY_THEO_DOI = frozenset({
    "3_TW_NHCSXH", "3_TW_NSNN", "3_DP_TINH", "3_DP_XA"
})

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

# ── Biểu 01C (KHNV_01C.XLSX từ TTBC): mapping XD-code → ma_key nội bộ ────────
BIEU_01C_XD_MA_KEY: dict[str, str] = {
    "XD0009":  "1_TW",      # Hộ nghèo
    "XD00010": "9_TW",      # Cận nghèo
    "XD00011": "19_TW",     # Hộ mới thoát nghèo
    "XD00012": "2_TW",      # HSSV có hoàn cảnh khó khăn
    "XD00013": "3_TW_NSNN", # GQVL từ NSNN (Quỹ QG TW)
    "XD00014": "3_TW_NHCSXH",# GQVL TW – NHCSXH huy động
    "XD00015": "17_TW",     # Người lao động đi làm việc ở nước ngoài
    "XD00016": "6_TW",      # NS&VSMT nông thôn
    "XD00017": "10_TW",     # Hộ gia đình SXKD tại VKK
    "XD00018": "15_TW",     # Thương nhân tại VKK
    "XD00020": "21_TW",     # Người chấp hành xong án phạt tù
    "XD00021": "25_TW",     # Nhà ở xã hội
    "XD00022": "25_TW",     # Nhà ở XH – mua/thuê mua (sub, gộp vào 25_TW)
    # ĐP block (mã XD00040+)
    "XD00040": "1_DP",      # Hộ nghèo ĐP
    "XD00041": "9_DP",      # Cận nghèo ĐP
    "XD00042": "19_DP",     # Thoát nghèo ĐP
    "XD00044": "3_DP_TINH", # GQVL ĐP – Cấp tỉnh
    "XD00049": "21_DP",     # Người CHHXA phạm ĐP
    "XD00050": "25_DP",     # Nhà ở XH ĐP
}

# Biểu 02C – phần C: Thuyết minh chỉ tiêu (XD00057–XD00074)
BIEU_02C_THUYET_MINH_XD: dict[str, str] = {
    "XD00057": "so_ho_dan_cu",
    "XD00058": "so_ho_dtts",
    "XD00060": "so_ho_ngheo",
    "XD00062": "so_ho_can_ngheo",
    "XD00064": "so_ho_thoat_ngheo",
    "XD00068": "so_hssv",
    "XD00069": "so_ld_gqvl_ns",
    "XD00070": "so_ld_xkld",
    "XD00071": "so_ct_ns_vsmt",
    "XD00072": "so_can_nha_xh",
    "XD00073": "tong_so_xa",
    "XD00074": "so_xa_vkk",
}

# Nhãn tiếng Việt cho từng key thuyết minh (dùng trong form nhập liệu)
THUYET_MINH_LABELS: dict[str, str] = {
    "so_ho_dan_cu":      "Số hộ dân cư trú trên địa bàn",
    "so_ho_dtts":        "Số hộ đồng bào dân tộc thiểu số",
    "so_ho_ngheo":       "Số hộ nghèo theo chuẩn hiện hành",
    "so_ho_can_ngheo":   "Số hộ cận nghèo theo chuẩn hiện hành",
    "so_ho_thoat_ngheo": "Số hộ mới thoát nghèo",
    "so_hssv":           "Tổng số HSSV có hoàn cảnh khó khăn",
    "so_ld_gqvl_ns":     "Lao động có nhu cầu vay GQVL (từ NSNN)",
    "so_ld_xkld":        "Lao động có nhu cầu vay đi làm việc nước ngoài",
    "so_ct_ns_vsmt":     "Số công trình NS&VSMT nông thôn dự kiến XD",
    "so_can_nha_xh":     "Số căn nhà ở xã hội dự kiến cho vay",
    "tong_so_xa":        "Tổng số xã/phường/thị trấn trên địa bàn",
    "so_xa_vkk":         "Số xã thuộc vùng khó khăn",
}

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
COT_GIAI_NGAN_TRONG_NAM = "Giải ngân trong năm"   # cột GQVL — dùng /1e6 khi hiển thị (fmt_ty)

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
    "Giải ngân trong năm":     COT_GIAI_NGAN_TRONG_NAM,
    "Dư tk":                   "Dư tài khoản",
    "NQ11":                    "NQ11",
}

# HSTD — DS cho vay / thu nợ trong năm (tab Tổng quan bảng PGD; khớp GQVL + alias Excel)
HSTD_DS_CHO_VAY_NAM_ALIASES = (
    COT_GIAI_NGAN_TRONG_NAM,  # "Giải ngân trong năm" — tên cột GQVL chuẩn
    "Giải ngân Năm",
    "Giải ngân năm",
    "Doanh số cho vay năm",
    "Doanh số CV năm",
    "Cho vay trong năm",
)
HSTD_THU_NO_NAM_ALIASES = (
    "Thu nợ trong năm",   # tên thực tế trong HSTD BCQUERY
    "Thu nợ TH Năm",
    "Thu nợ QH Năm",
    "Thu nợ Khoanh Năm",
    "Doanh số thu nợ năm",
    "Thu nợ năm",
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
COT_NGAY_DH    = "Ngày ĐH theo Gia hạn"
COT_NGAY_DEN_HAN = COT_NGAY_DH  # alias cho module đến hạn
COT_NGAY_DH_HD   = "Ngày ĐH theo hợp đồng"   # cột gốc HĐ — chỉ dùng cho kiểm soát gia hạn
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
COT_NGAY_SL       = "Ngày số liệu"
COT_GOC_TRA       = "Gốc đã trả"
COT_LAI_DA_TRA    = "Lãi đã trả"
COT_DU_NO_KHOANH    = "Dư nợ khoanh"
COT_NGAY_HH_KHOANH = "Ngày hết hạn Khoanh"

# ── Tên cột bổ sung (tra cứu nâng cao) ──────────────────────────────────────
COT_CMND          = "Số CMND"           # hoặc CCCD
COT_NGAY_SINH     = "Ngày sinh"
COT_NGAY_CAP_CMND = "Ngày cấp CMND"
COT_NOI_CAP_CMND  = "Nơi cấp CMND"
COT_TEN_TO        = "Tên tổ"
COT_TEN_XA        = "Tên xã"
COT_TEN_THON      = "Tên thôn"
COT_NGUON_VON     = "Nguồn vốn"         # 1=TW, 2=ĐP
COT_MA_NHA_DAU_TU = "Mã nhà đầu tư"    # chỉ có khi ĐP
COT_TEN_NHA_DAU_TU = "Tên nhà đầu tư"
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
COT_HINH_THUC_VAY = "Hình thức vay"      # hình thức vay (1=NHCSXH, 2=ủy thác,...)
COT_SO_LAN_GH    = "Số lần gia hạn"    # số lượt đã gia hạn nợ (từ HSTD)
COT_NGAY_GH_GN   = "Ngày gia hạn gần nhất"  # ngày quyết định gia hạn gần nhất (từ HSTD)

# ── Tên cột HSTD đầy đủ (từ BCQUERY bank) ─────────────────────────────────────────
COT_MA_CN                   = "Mã CN"
COT_MA_PGD                  = "Mã PGD"
COT_MA_XA                   = "Mã xã"
COT_MA_THON                 = "Mã thôn"
COT_LOAI_KH                 = "Loại KH"
COT_GIOI_TINH               = "Giới tính"
COT_MA_DAN_TOC              = "Mã dân tộc"
COT_TEN_DT                  = "Tên DT"
COT_NGAY_CAP_CMND           = "Ngày cấp CMND"
COT_NOI_CAP_CMND            = "Nơi cấp CMND"
COT_MA_TO                   = "Mã tổ"
COT_TEN_TO_TRUONG            = "Tên tổ trưởng"
COT_LOAI_TO                 = "Loại tổ"

# ── Constants cho Điểm Giao Dịch ───────────────────────────────────────────────────
COT_MA_DGD                  = "Mã điểm giao dịch"
COT_TEN_DGD                 = "Tên điểm giao dịch"
COT_DIA_DIEM_DGD            = "Địa điểm ĐGD"
COT_NGAY_GD                 = "Ngày giao dịch"
COT_GIO_GD                  = "Giờ giao dịch"
COT_XA_DGD                  = "Xã ĐGD"
COT_PGD_DGD                 = "PGD ĐGD"
COT_MA_CIF_TT               = "Mã CIF TT"
COT_MA_DVUT                 = "Mã ĐVUT"
COT_NGAY_DH_GDXA            = "Ngày ĐH theo GDXA"
COT_NGAY_BD_TRA_GOC         = "Ngày BĐ trả gốc"
COT_NGAY_BD_TRA_LAI         = "Ngày BĐ trả lãi"
COT_NGAY_KTAHSV             = "Ngày KTAHSV"
COT_NGAY_GDXA               = "Ngày GDXA"
COT_CAP_QL_VON              = "Cấp QL vốn"
COT_TEN_CAP_QLV             = "Tên cấp QLV"
COT_DOI_TUONG_THU_HUONG     = "Đối tượng thụ hưởng"
COT_TEN_DTTH                = "Tên ĐTTH"
COT_MA_SP_CU_THE            = "Mã sản phẩm cụ thể"
COT_MA_SP_TIN_DUNG          = "Mã SP tín dụng"
COT_MA_DM_SP                = "Mã DM sản phẩm"
COT_MA_QUYET_DINH           = "Mã Quyết định"
COT_TEN_QUYET_DINH          = "Tên Quyết định"
COT_TONG_GIAI_NGAN          = "Tổng giải ngân"
COT_NGAY_GN_DAU_TIEN        = "Ngày GN đầu tiên"
COT_NGAY_GN_CUOI_CUNG       = "Ngày GN cuối cùng"
COT_GOC_DEN_HAN_LK          = "Gốc đến hạn LK"
COT_GOC_XOA                 = "Gốc xóa"
COT_LAI_XOA                 = "Lãi xóa"
COT_TONG_THU_LAI_TH         = "Tổng thu lãi TH"
COT_TONG_THU_LAI_QH         = "Tổng thu lãi QH"
COT_LAI_DT_CHUA_DEN_HAN     = "Lãi DT chưa đến hạn"
COT_LAI_TT_TRONG_THANG      = "Lãi TT trong tháng"
COT_THU_LAI_TH_THANG        = "Thu lãi TH tháng"
COT_THU_LAI_QH_THANG        = "Thu lãi QH Tháng"
COT_GIAI_NGAN_TRONG_THANG   = "Giải ngân trong tháng"
COT_DAO_KHOAN_GN_THANG      = "Đảo khoản GN tháng"
COT_LUU_VU_TRONG_THANG      = "Lưu vụ trong tháng"
COT_GIA_HAN_TRONG_THANG     = "Gia hạn trong tháng"
COT_CHUYEN_QH_TRONG_THANG   = "Chuyển QH trong tháng"
COT_CHUYEN_KHOANH_TRONG_THANG= "Chuyển khoanh trong tháng"
COT_THU_NO_TH_THANG         = "Thu nợ TH tháng"
COT_THU_NO_QH_THANG         = "Thu nợ QH tháng"
COT_THU_NO_KHOANH_THANG     = "Thu nợ khoanh tháng"
COT_GOC_XOA_TRONG_THANG     = "Gốc xóa trong tháng"
COT_LAI_DT_QUY              = "Lãi DT Quý"
COT_LAI_TT_QUY              = "Lãi TT Quý"
COT_THU_LAI_TH_QUY          = "Thu lãi TH Quý"
COT_THU_LAI_QH_QUY          = "Thu lãi QH Quý"
COT_GIAI_NGAN_TRONG_QUY     = "Giải ngân trong Quý"
COT_DAO_KHOAN_GN_QUY        = "Đảo khoản GN Quý"
COT_LUU_VU_TRONG_QUY        = "Lưu vụ trong Quý"
COT_GIA_HAN_TRONG_QUY       = "Gia hạn trong Quý"
COT_CQH_TRONG_QUY           = "CQH trong Quý"
COT_CHUYEN_KHOANH_QUY       = "Chuyển Khoanh Quý"
COT_THU_NO_TH_QUY           = "Thu nợ TH Quý"
COT_THU_NO_QH_QUY           = "Thu nợ QH Quý"
COT_THU_NO_KHOANH_QUY       = "Thu nợ Khoanh Quý"
COT_GOC_XOA_TRONG_QUY       = "Gốc xóa trong Quý"
COT_LAI_DT_NAM              = "Lãi DT Năm"
COT_LAI_TT_NAM              = "Lãi TT Năm"
COT_THU_LAI_TH_NAM          = "Thu lãi TH Năm"
COT_THU_LAI_QH_NAM          = "Thu lãi QH Năm"
COT_GIAI_NGAN_NAM           = "Giải ngân Năm"
COT_DAO_KHOAN_GN_NAM        = "Đảo khoản GN Năm"
COT_LUU_VU_NAM              = "Lưu vụ Năm"
COT_GIA_HAN_NAM             = "Gia hạn Năm"
COT_CQH_NAM                 = "CQH Năm"
COT_CHUYEN_KHOANH_NAM       = "Chuyển Khoanh Năm"
COT_THU_NO_TH_NAM           = "Thu nợ TH Năm"
COT_THU_NO_QH_NAM           = "Thu nợ QH Năm"
COT_THU_NO_KHOANH_NAM       = "Thu nợ Khoanh Năm"
COT_XOA_TRONG_NAM           = "Xóa trong Năm"
COT_TAI_KHOAN_TH            = "Tài khoản TH"
COT_TAI_KHOAN_QH            = "Tài khoản QH"
COT_TAI_KHOAN_KHOANH        = "Tài khoản khoanh"
COT_TAI_KHOAN_THU_LAI       = "Tài khoản thu lãi"
COT_TONG_THU_NO_TH          = "Tổng thu nợ TH"
COT_TONG_THU_NO_QH          = "Tổng thu nợ QH"
COT_TONG_THU_NO_KHOANH      = "Tổng thu nợ Khoanh"
COT_TONG_GIA_HAN_NO         = "Tổng gia hạn nợ"
COT_SO_THANG_DA_GH          = "Số tháng đã GH"
COT_TONG_CHUYEN_NO_QH       = "Tổng chuyển nợ QH"
COT_NGAY_CNQH_GN            = "Ngày CNQH gần nhất"
COT_TONG_CHUYEN_NO_KHOANH   = "Tổng chuyển nợ khoanh"
COT_GOC_HH_KHOANH           = "Gốc hết hạn Khoanh"
COT_NGAY_LUU_VU             = "Ngày lưu vụ"
COT_TON_RPA                 = "Tồn RPA"
COT_NGAY_DU_THU             = "Ngày dự thu"
COT_TONG_LAI_PHAI_HT        = "Tổng Lãi phải HT"
COT_LAI_CHUA_HO_TRO         = "Lãi chưa hỗ trợ"
COT_CHUAN_NGHEO_DP          = "Chuẩn nghèo ĐP"
COT_MA_PNKT51               = "Mã PNKT51"
COT_TEN_PNKT51              = "Tên PNKT51"
COT_MA_PNKT52               = "Mã PNKT52"
COT_MA_HQDT                 = "Mã HQĐT"
COT_TEN_HQDT                = "Tên HQĐT"
COT_GIA_TRI_HQDT1           = "Giá trị HQĐT1"
COT_GIA_TRI_HQDT2           = "Giá trị HQĐT2"
COT_KY_QUY                  = "Ký quý"
COT_MUC_DICH_NHA            = "Mục đích nhà"
COT_MUC_DICH_30A            = "Mục đích 30A"
COT_MA_DU_AN                = "Mã dự án"
COT_MA_HSSV                 = "Mã HSSV"
COT_CMND_HSSV               = "CMND HSSV"
COT_MA_TRUONG_HSSV          = "Mã trường HSSV"
COT_TEN_TRUONG              = "Tên trường"
COT_MA_HE_DAO_TAO           = "Mã Hệ đào tạo"
COT_TEN_HE_DT               = "Tên Hệ ĐT"
COT_MA_NGANH_DT             = "Mã ngành ĐT"
COT_TEN_NGANH_DT            = "Tên Ngành ĐT"
COT_MA_DT_HOC_PHI           = "Mã ĐT học phí"
COT_TEN_DT_HOC_PHI          = "Tên ĐT học phí"
COT_NGAY_NHAP_HOC           = "Ngày nhập học"
COT_NGAY_RA_TRUONG          = "Ngày ra trường"
COT_SO_ATM                  = "Số ATM"
COT_DON_VI_CAP_THE          = "Đơn vị cấp thẻ"
COT_TEN_LDXK                = "Tên LĐXK"
COT_NGAY_SINH_LDXK          = "Ngày sinh LĐXK"
COT_SO_THE_LDXK             = "Số thẻ LĐXK"
COT_NGAY_HOP_DONG_XK        = "Ngày hợp đồng XK"
COT_NGAY_HH_XK              = "Ngày hết hạn XK"
COT_LINH_VUC_LDXK           = "Lĩnh vực LĐXK"
COT_CONG_TY_XK              = "Công ty xuất khẩu"
COT_QUOC_GIA_XK             = "Quốc gia xuất khẩu"
COT_TEN_QUOC_GIA            = "Tên Quốc Gia"
COT_CONG_TY_MOI_GIOI_XK     = "Công ty môi giới XK"
COT_SO_TIET_KIEM_105        = "Sổ tiết kiệm 105"

# ── Cột dữ liệu NQ11 (khác tên so với HSTD) ──────────────────────────────────
COT_DNO_NQ11        = "DNO NQ11"
COT_NQ11_NO_TH      = "Nợ trong hạn"
COT_NQ11_NO_QH      = "Nợ quá hạn"
COT_NQ11_MA_KH      = "Mã khách hàng"
COT_NQ11_TEN_KH     = "Tên khách hàng"
COT_NQ11_SO_TIEN    = "Số tiền"
COT_NQ11_DU_NO      = "Dư nợ"
COT_NQ11_SO_TIEN_GN = "Số tiền giải ngân"
COT_NQ11_DEN_HAN_SC = "Đến hạn sau cùng"
COT_NQ11_NGAY_BC    = "Ngày báo cáo"

# ── Cột dữ liệu GQVL ────────────────────────────────────────────────────────
COT_GQVL_MA_PGD         = "Mã PGD"
COT_GQVL_DU_NO_KHOANH   = "Dư nợ khoanh"

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
    "admin_cn", "manager_cn", "chuyenvien_cn",      # Phân hệ Chi nhánh
    "admin_pgd", "manager_pgd", "user_pgd",  # Phân hệ PGD
]

# Tất cả roles hợp lệ (cũ + mới)
ALL_ROLES = list(dict.fromkeys(ROLES_CU + ROLES_MOI))

# Nhóm theo phân hệ
ROLES_PHAN_HE_CN  = ["executive", "admin_cn", "manager_cn", "chuyenvien_cn", "admin", "manager"]
ROLES_PHAN_HE_PGD = ["admin_pgd", "manager_pgd", "user_pgd", "user"]

# Quyền cụ thể
ROLES_CO_QUYEN_UPLOAD_CN  = ["admin_cn", "manager_cn", "chuyenvien_cn", "admin", "manager"]
ROLES_CO_QUYEN_UPLOAD_PGD = ["admin_pgd", "manager_pgd"]
ROLES_CO_QUYEN_QUAN_LY_USER_CN  = ["admin_cn", "admin"]
ROLES_CO_QUYEN_QUAN_LY_USER_PGD = ["admin_pgd"]
ROLES_CO_QUYEN_GIAO_NHIEM_VU    = ["admin_pgd", "manager_pgd", "admin", "manager", "admin_cn", "manager_cn", "chuyenvien_cn"]

# ── Loại công việc & Ưu tiên (dùng chung tab_tien_do + tab_nhiem_vu) ──────────
LOAI_CONG_VIEC: dict[str, str] = {
    "chung":            "📋 Công việc chung",
    "chi_tieu_khtd":    "🎯 Chỉ tiêu KHTD",
    "ho_so_rui_ro":     "🗂️ Hồ sơ rủi ro",
    "khao_sat_nhu_cau": "📊 Khảo sát nhu cầu vay vốn",
    "bao_cao":          "📄 Báo cáo",
    "tap_huan":         "🎓 Tập huấn",
    "giao_dich_xa":     "📅 Giao dịch xã",
    "uy_thac":          "🤝 Hoạt động ủy thác",
    "nguon_von":        "💰 Nguồn vốn",
    "ban_dai_dien":     "📑 Ban đại diện HĐQT",
    "khac":             "Khác",
}
UU_TIEN_CV: dict[str, str] = {
    "khan_cap":    "🔴 Khẩn cấp",
    "quan_trong":  "🟡 Quan trọng",
    "binh_thuong": "🟢 Bình thường",
}

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

# ── Nguyên nhân rủi ro QĐ 62/2015/QĐ-TTg ────────────────────────────────────
NGUYEN_NHAN_RR = [
    "Thiên tai, dịch bệnh (QĐ62)",
    "Nhà nước thay đổi chính sách (QĐ62)",
    "Lao động về nước trước hạn (QĐ62)",
    "KH/TV hộ GĐ gặp rủi ro (QĐ62)",
    "Vắng mặt tại nơi cư trú (QĐ62)",
    "Rủi ro không làm kịp thời (QĐ62)",
    "Hết thời gian khoanh nợ (QĐ62)",
    "Nợ nhận bàn giao (QĐ62)",
]

# ── KV key prefix cho Nợ rủi ro ──────────────────────────────────────────────
KV_PREFIX_NO_RUI_RO = "no_rui_ro_"

# ── Lý do khoanh nợ theo QĐ62 (dùng trong QLNK) ─────────────────────────────
LY_DO_KHOANH_QD62 = {
    "k1_3nam":  "K1 — Thiên tai, dịch bệnh (thiệt hại 40–79%, khoanh 3 năm)",
    "k1_5nam":  "K1 — Thiên tai, dịch bệnh (thiệt hại 80–100%, khoanh 5 năm)",
    "k2_3nam":  "K2 — Nhà nước thay đổi chính sách (thiệt hại 40–79%, khoanh 3 năm)",
    "k2_5nam":  "K2 — Nhà nước thay đổi chính sách (thiệt hại 80–100%, khoanh 5 năm)",
    "k2_cham":  "K2 — Rủi ro K1/K2 nhưng xử lý chậm (khoanh 3 năm)",
    "k3":       "K3 — Biến động kinh tế - chính trị - xã hội (khoanh 3 năm)",
    "k4a":      "K4a — Mắc bệnh hiểm nghèo/tâm thần/mất NLHVDS/suy giảm KNLĐ ≥81%/chết/mất tích",
    "k4b":      "K4b — Bị bệnh cần chữa trị dài ngày (danh mục TT 46/2016/TT-BYT)",
    "k4c":      "K4c — Vắng mặt tại nơi cư trú ≥2 năm, không có thông tin xác thực",
    "k5":       "K5 — Có bản án/QĐ Tòa án, chưa đủ điều kiện thi hành án (khoanh 3 năm)",
    "k_bs":     "Khoanh nợ bổ sung — Hết hạn khoanh, chưa có khả năng trả nợ",
}

LY_DO_KHOANH_LABEL = {
    "k1_3nam":  "K1 — Thiên tai/dịch bệnh (3 năm)",
    "k1_5nam":  "K1 — Thiên tai/dịch bệnh (5 năm)",
    "k2_3nam":  "K2 — Thay đổi chính sách (3 năm)",
    "k2_5nam":  "K2 — Thay đổi chính sách (5 năm)",
    "k2_cham":  "K2 — Xử lý chậm (3 năm)",
    "k3":       "K3 — Biến động KT-CT-XH",
    "k4a":      "K4a — Bệnh hiểm nghèo/chết/mất tích",
    "k4b":      "K4b — Bệnh chữa trị dài ngày",
    "k4c":      "K4c — Vắng mặt ≥2 năm",
    "k5":       "K5 — Bản án/QĐ Tòa án",
    "k_bs":     "Khoanh bổ sung",
}

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
# Các mã được trích từ file NQ11 thực tế.
# Ghi chú: Khi upload file NQ11 mới, nếu mã không khớp thì hệ thống sẽ báo lỗi
# và không nhận diện được đơn vị — lúc đó cần cập nhật mapping này cho đúng.
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
        "Xã Bàu Hàm", "Xã Bình Minh",
    ],
    "PGD Long Khánh": [
        "Phường Bảo Vinh", "Phường Xuân Lập", "Phường Long Khánh",
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
        "Xã Tà Lài", "Xã Dak Lua",
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

# ── Danh mục thôn/ấp (nguồn: CN46_Danh muc thon_12-05-2026) ─────────────────
# Mapping: xã/phường → danh sách thôn/ấp/khu phố
XA_THON_MAP: dict[str, list[str]] = {
    'Phường An Lộc': ['Thanh hải', 'Thanh Tân', 'Cần Lê', 'Thanh Tuấn', 'Thanh hưng', 'Thanh Kiều', 'Thanh Bình', 'Thanh Thiện', 'Thanh An', 'Vườn Rau', 'Ấp 17', 'Sóc Bưng', 'Thanh Xuân', 'Thanh Sơn', 'Phú Lạc', 'Phú Long', 'Thanh Thủy', 'Phú Thành', 'Phú Xuân', 'Phú Hòa', 'Phú Thuận', 'KP Phú hưng', 'Thanh Thịnh', 'Thanh Hòa', 'Phố Lố', 'Sóc Bế', 'Thanh trung', 'Sóc Giếng', 'Thanh Hà'],
    'Phường Biên Hòa': ['Khu Phố Bửu Hòa 2', 'Khu Phố Bửu Hòa 3', 'Khu Phố Bửu Hòa  4', 'Khu Phố Bửu Hòa 5', 'An Hòa', 'Bình Hóa', 'Cầu Hang', 'Khu phố  Tân Hạnh 1', 'Khu phố  Tân Hạnh 2', 'Khu phố  Tân Hạnh 3', 'Khu phố  Tân Hạnh  4', 'Khu phố  Tân Vạn 1', 'Khu phố Tân Vạn 2', 'Khu phố Tân Vạn 4', 'Khu phố Bửu Hòa 1', 'Đồng Nai', 'Khu phố Tân Vạn 3'],
    'Phường Bình Long': ['Phú An', 'Phú Cường', 'Phú Trung II', 'Phú Bình', 'Phú Sơn', 'Bình An', 'An Bình', 'Sóc Du', 'Phú Tân Hưng Chiến', 'Phú Lộc', 'Phú Hòa 2', 'Phú Nghĩa', 'Phú Trọng', 'Xa cam 1', 'Xa cam 2', 'Đông Phất I', 'Bình Tây', 'Phú Tân Bình Long', 'Bình Ninh 1', 'Bình Ninh 2', 'Hưng Phú', 'Phú Trung I', 'Đông Phất II', 'Sóc Răng', 'Xa Cát', 'Sở Nhì II', 'KP hưng Thịnh', 'Bình Tân', 'Phú Hòa 1', 'Sở Nhì I', 'Chà Là'],
    'Phường Bình Lộc': ['Khu Phố 2', 'Khu Phố 3', 'Khu phố 4', 'Khu Phố Dưỡng Đường', 'Khu Phố Cáp Rang', 'Khu Phố Núi Tung', 'Khu Phố Xuân Thiện', 'Khu Phố Tín Nghĩa', 'Khu Phố 1', 'Khu Phố Suối Tre', 'Khu Phố Cây Da'],
    'Phường Bình Phước': ['KP Phú Cường', 'KP Phú Mỹ', 'KP Phú Thịnh', 'KP Phú Xuân', 'KP Tân Đồng 1', 'KP Tân Đồng 2', 'KP Tân Đồng 3', 'KP Tân Đồng 4', 'KP Thanh Bình', 'KP Tân Trà 2', 'KP Xuân Bình', 'KP Tân Xuân', 'KP Tân Tiến', 'KP Suối Đá', 'KP Phước Bình', 'KP Phước An', 'KP Tân Trà', 'KP Tân Thiện', 'KP Phước Thọ', 'KP Bình Thiện', 'KP Xuân Đồng', 'KP Phước Hòa', 'KP Phước Tân', 'KP Tiến Hưng 1', 'KP Tiến Hưng 2', 'KP Tiến Hưng 3', 'KP Tiến Hưng 4', 'KP Tiến Hưng 6', 'KP Tiến Hưng 7', 'KP Phú Tân', 'KP Phú Thanh', 'KP Tân Bình', 'KP Phú Lộc', 'KP Tân Đồng 5', 'KP Tân Trà 1', 'KP Xuân Lộc', 'KP Phước Thiện'],
    'Phường Bảo Vinh': ['Khu phố 18 Gia Đình', 'Khu phố Lác Chiếu', 'Khu phố Bàu Cối', 'Khu phố Ruộng Tre', 'Khu Phố Thọ An', 'Khu phố Bảo Vinh A', 'Khu phố Bảo Vinh B', 'Khu Phố Ruộng Lớn', 'Khu Phố Suối Chồn', 'Khu phố Ruộng Hời'],
    'Phường Chơn Thành': ['KP 1', 'KP 2', 'KP 3', 'KP 4', 'KP 5', 'KP 6', 'KP 8', 'Khu phố 9', 'Khu phố 10', 'Trung Lợi', 'Khu phố Hiếu Cảm', 'Minh Thành 2', 'Minh Thành 3', 'Minh Thành 4', 'Minh Thành 5', 'Thành Tâm 1', 'Thành Tâm 2', 'Hòa Vinh 2', 'Mỹ Hưng', 'Thủ Chánh', 'Đồng Tâm', 'KP 7', 'Minh Thành 1', 'Hòa Vinh 1'],
    'Phường Hàng Gòn': ['Khu phố Tân Phong', 'Khu phố Đồi Rìu', 'Khu phố Cẩm Tân', 'Khu Phố Xuân Tân', 'Khu phố Hàng Gòn', 'Khu Phố Nông Doanh'],
    'Phường Hố Nai': ['Khu phố 1', 'Khu phố 2', 'Khu phố 3', 'Khu phố 4', 'Khu phố 6', 'Khu phố 7', 'Khu phố 8', 'Khu phố 9', 'Khu phố 10', 'Khu phố 11', 'khu phố Ngũ Phúc', 'khu phố Thanh Hóa', 'khu phố Thái Hòa', 'khu phố Đông Hải', 'khu phố Lộ Đức', 'Khu phố 5', 'Khu phố 4A'],
    'Phường Long Bình': ['Khu phố 2 Hố Nai 2', 'Khu phố 3', 'Khu phố 4 Hố Nai 2', 'Khu phố 6', 'Khu phố 7', 'Khu phố 8', 'Khu phố 9', 'Khu phố 10', 'Khu phố 11', 'Khu phố 13', 'Khu phố 14', 'Khu  phố 17', 'Khu phố 15', 'Khu phố 16', 'Khu phố 5 Tân Biên', 'Khu phố 23', 'Khu phố 8 Tân Biên', 'Khu phố 22', 'Khu phố 21', 'Khu phố 24', 'Khu phố 25', 'Khu phố 19', 'Khu  phố 26', 'khu phố  27', 'Khu phố 29', 'Khu phố 30', 'Khu phố 31', 'khu phố  33', 'Khu phố 36', 'Khu phố 28', 'Khu phố 32', 'Khu phố 35', 'Khu phố 37', 'Khu phố 5', 'Khu phố 12', 'Khu phố 18', 'Khu phố 20', 'Khu phố 34', 'Khu phố 1'],
    'Phường Long Hưng': ['Khu phố 6', 'Khu phố 7', 'Thái Hòa', 'Khu phố Long Điềm', 'Khu phố Bình Dương', 'Khu phố 8', 'Khu phố 2', 'khu phố 03', 'khu phố 04', 'Khu phố Phước Hội', 'Khu phố An Xuân', 'Khu phố 5', 'Khu phố 1'],
    'Phường Long Khánh': ['Khu phố Bàu Trâm', 'Khu phố 25', 'Khu phố 26', 'Khu phố 1', 'Khu phố 2', 'Khu phố 3', 'Khuy phố 4', 'Khu phố 5', 'Khu phố 7', 'Khu phố 8', 'Khu phố 9', 'Khu phố 10', 'Khu phố 11', 'Khu phố 12', 'Khu phố 13', 'Khu phố 14', 'Khu phố 15', 'Khu phố 16', 'Khu Phố 18', 'Khu Phố 19', 'Khu Phố 20', 'Khu Phố 21', 'Khu phố 22', 'Khu phố 23', 'Khu Phố 24', 'Khu Phố Bàu Sầm', 'Khu Phố 6', 'Khu Phố 17'],
    'Phường Minh Hưng': ['Khu phố 1 Minh Hưng', 'Khu phố 2 Minh Hưng', 'Khu phố 3A', 'Khu phố 4 Minh Hưng', 'Khu phố 6 Minh Hưng', 'Khu phố 7 Minh Hưng', 'Khu phố 8', 'Khu phố 9', 'Khu phố 10', 'Khu phố 5 Minh Hưng', 'Minh Long 1', 'Khu phố 11', 'Khu phố 3B', 'Khu phố 12', 'Minh Long 2', 'Minh Long 3', 'Minh Long 4', 'Minh Long 5', 'Minh Long 6', 'Minh Long 7'],
    'Phường Phước Bình': ['Khu phố 1', 'Khu phố 2', 'Khu phố Phước Hiệp', 'Khu phố Phước Trung', 'Khu phố Phước Vĩnh', 'Khu phố Phước Sơn', 'Khu phố Phú Châu', 'Khu phố Bình Minh', 'Khu phố Bình Điền', 'Khu phố Sơn Hà 1', 'Khu phố Sơn Hà 2', 'Khu phố 10', 'Khu phố 3', 'Khu phố Long Điền 1', 'Khu phố Long Điền 2', 'Khu phố 8', 'Khu phố 6', 'Khu phố 9', 'Khu phố 7', 'Khu phố 4', 'Khu phố Nhơn Hoà 1', 'Khu phố Nhơn Hoà 2', 'Khu phố Bù Xiết', 'Khu phố An Lương', 'Khu phố Long Giang', 'Khu phố Phước An', 'Khu phố 5', 'Khu phố Long Phước'],
    'Phường Phước Long': ['Khu phố Thác Mơ 1', 'Khu phố Thác Mơ 3', 'Khu phố Thác Mơ 4', 'Khu phố Thác Mơ 5', 'Khu phố Bình Giang 1', 'Khu phố Bình Giang 2', 'Khu phố Hưng Lập', 'Khu phố Phước Thiện', 'Khu phố Phước Lộc', 'Khu phố Bàu Nghé', 'Khu phố Phước Yên', 'Khu phố Phước Quả', 'Khu phố Long Thuỷ 1', 'Khu phố Long Thuỷ 3', 'Khu phố Long Thuỷ 4', 'Khu phố Long Thuỷ 5', 'Khu phố Sơn Long', 'Khu phố Long Thuỷ 2', 'Khu phố Thác Mơ 2'],
    'Phường Phước Tân': ['Đồng', 'Hương Phước', 'Tân Cang', 'Tân Mai 2', 'Tân Lập', 'Miễu', 'Rạch Chiếc', 'Tân Mai', 'Vườn Dừa'],
    'Phường Tam Hiệp': ['khu phố 4', 'khu phố 5', 'khu phố 6', 'khu phố 7', 'Khu phố 8', 'khu phố 16', 'khu phố 17', 'khu phố 18', 'khu phố 19', 'khu phố 20', 'khu phố 21', 'khu phố 23', 'Khu phố 09', 'khu phố 25', 'khu phố 26', 'khu phố 27', 'khu phố 28', 'khu phố 12', 'khu phố 13', 'khu phố 14', 'Khu phố 15', 'khu phố 11', 'khu phố 29', 'khu phố 30', 'khu phố 32', 'khu phố 33', 'khu phố 34', 'khu phố 35', 'khu phố 1', 'khu phố 3', 'khu phố 31', 'khu phố 2', 'khu phố 24', 'khu phố 22', 'khu phố 10'],
    'Phường Tam Phước': ['Long Đức 1', 'Long Đức 3', 'Long Khánh 1', 'Long Khánh 2', 'Long Khánh 3', 'Thiên Bình', 'Long Đức 2'],
    'Phường Trảng Dài': ['Khu phố 6-7', 'Khu phố Ông Hường', 'Khu phố 02', 'Khu phố 03', 'Khu phố 04', 'khu phố 2A', 'khu phố 3A', 'khu phố 4A', 'khu phố 5A', 'Khu phố 01', 'khu phố 4B', 'Khu phố Vàm', 'Khu phố 05', 'khu phố 4C'],
    'Phường Trấn Biên': ['Khu phố Bình Đa', 'Khu Phố Bến Đá', 'khu phố Đồng Tâm', 'Khu phố An Bình', 'khu phố Lam Sơn', 'Khu phố An Hảo', 'Khu phố Đoàn Kết', 'Khu Công Nghiệp', 'Khu phố Tân Bình', 'Khu phố  An Bình', 'Nhị Hòa', 'Tam Hòa', 'Khu phố Hoa Lư', 'Khu phố Quang Vinh', 'Khu phố Cây Chàm', 'Khu phố Bình Thiền', 'Khu Phố Hoà Bình', 'Khu phố Xóm Vườn', 'Khu phố Thành Thái', 'Khu phố Tân Lân', 'Khu phố Sân Bay', 'Khu phố Bình Thành', 'Khu phố Tân Lại', 'Khu phố Tân Thành', 'Khu phố Tân Bửu', 'Khu phố Thống Nhất', 'Khu phố Mương Sao', 'Khu phố Nhà Xanh', 'Khu phố Gò Me', 'Khu phố Bình Trước', 'Khu phố Đại Phước', 'Khu phố Vinh Thạnh', 'Khu phố Vườn Mít', 'Khu phố Trung Dũng', 'Khu phố Biên Hùng', 'Khu phố Trung Kiên', 'Khu phố Phi Trường', 'Khu phố Ngã Ba Thành', 'Khu phố Thanh Bình', 'Khu phố Khánh Hưng', 'Khu phố Quyết Thắng', 'Khu phố Phước Lư', 'Khu phố Công Lý', 'Khu phố Bình An', 'Nhất Hòa', 'Khu phố Bửu Sơn', 'Khu phố Bửu Long', 'Khu phố Nam Hà', 'Khu phố Sông Phố'],
    'Phường Tân Triều': ['khu phố 01', 'khu phố 03', 'khu phố 04', 'khu phố 05', 'khu phố 06', 'khu phố 07', 'khu phố 08', 'khu phố 10', 'khu phố 11', 'khu phố 11A', 'Khu phố Phú Trạch', 'Khu phố Bình Thạnh', 'Khu phố Cây Đào', 'Khu phố Thạnh Phú', 'Khu phố Cây Da', 'Khu phố Tân Huệ', 'Khu phố Đa Lộc', 'Khu phố Long Chiến', 'Khu phố Bình Long', 'Khu phố Võ Sa', 'Khu phố Lợi Hòa', 'Khu phố Thới Sơn', 'Khu phố Bình Lục', 'Khu phố Bình Phước', 'Khu phố Bình Ý', 'Khu phố Tân Triều', 'Khu phố Vĩnh Hiệp', 'khu phố 02', 'khu phố 09', 'Khu phố Tân Phú', 'Khu phố Bình Thạch'],
    'Phường Xuân Lập': ['Khu Phố Núi Đỏ', 'Khu Phố Trung Tâm', 'Khu Phố Phú Mỹ', 'Khu phố Bàu Sen', 'Khu Phố Tân Thủy'],
    'Phường Đồng Xoài': ['Khu phố Suối Cam', 'KP Tiến Thành 2', 'KP Tiến Thành 4', 'Khu phố Làng Ba', 'Khu phố Bưng Trang', 'KP Tiến Thành 1', 'KP Tiến Thành 5', 'KP Tân Thành 3', 'Kp Tân Thành 4', 'KP Tân Thành 6', 'KP Tân Thành 7', 'KP Tân Thành 8', 'KP Bưng Sê', 'KP Tiến Thành 3', 'KP Tân Thành 2'],
    'Xã An Phước': ['ấp Tam An 2', 'ấp Tam An 3', 'ấp Tam An 4', 'ấp Tam An 5', 'Ấp 1 An Phước', 'Ấp 2 An Phước', 'Ấp 3 An Phước', 'Ấp 6', 'Ấp 7', 'Ấp 8', 'ấp Bàu Cá', 'ấp Tam An 1', 'Ấp 5 An Phước'],
    'Xã An Viễn': ['Tân Phát', 'Tân Đạt', 'Tân Thịnh', 'Tân hưng', 'Ấp 2', 'Ấp 3', 'Ấp 4', 'Ấp 5', 'Ấp 6', 'Ấp 1'],
    'Xã Bom Bo': ['Thôn 2 Bình Minh', 'Thôn 3 Bình Minh', 'Thôn 4 Bình Minh', 'Thôn 5 Bình Minh', 'Thôn 6 Bình Minh', 'Thôn 7 Bình Minh', 'Thôn 10 Bom Bo', 'Thôn 8 Bình Minh', 'Thôn 3 Bom Bo', 'Thôn 4 Bom Bo', 'Thôn 5 Bom Bo', 'Thôn 6 Bom Bo', 'Thôn 7 Bom Bo', 'Thôn 8 Bom Bo', 'Thôn 9 Bom Bo', 'Bom Bo'],
    'Xã Bình An': ['Khu 12', 'Khu 13', 'Khu 14', 'Khu 15', 'An Bình', 'An viễng', 'Sa cá', 'Bàu tre'],
    'Xã Bình Minh': ['Bùi Chu', 'Tân Thành', 'Phú Sơn', 'Trà Cổ', 'Tân Bình', 'Tân Bắc', 'An Chu', 'Sông Mây', 'Bắc Hòa'],
    'Xã Bình Tân': ['Thôn Long Hưng 2', 'Thôn Long Hưng 3', 'Thôn Long Hưng 4', 'Thôn Long Hưng 5', 'Thôn Long Hưng 6', 'Thôn Long Hưng 7', 'Thôn Long Bình 1', 'Thôn Long Bình 3', 'Thôn Long Bình 4', 'Thôn Long Bình 5', 'Thôn Long Bình 6', 'Thôn Long Bình 7', 'Thôn Long Bình 8', 'Thôn Long Bình 9', 'Phước Tân', 'Phước Lộc', 'Phước Hòa', 'Phước Thịnh', 'Phước An', 'Bình Hiếu', 'Hiếu Phong', 'Thôn Long Hưng 1', 'Thôn Long Bình 2', 'Thôn Long Bình 11'],
    'Xã Bù Gia Mập': ['Đak Côn', 'Bù Dốt', 'Bù La', 'Bù Nga', 'Bù Lư', 'Bù Rên', 'Cầu Sắt', 'Đak á'],
    'Xã Bù Đăng': ['Thôn Hòa Đồng', 'Thôn Hưng Phát', 'Thôn Đoàn Kết', 'Thôn Đức Phong', 'Thôn Đức Lợi', 'Thôn Đức Thọ', 'Thôn Đức Thiện', 'Thôn Đức Hòa', 'Thôn Tân Hưng', 'Thôn Hưng Tân', 'Thôn Minh Hưng', 'Thôn Hưng Thịnh', 'Thôn Minh Tâm', 'Thôn Hưng Phú', 'Thôn Hưng Phước', 'Thôn Hưng Vượng', 'Thôn Tân Quang', 'Thôn Hưng Đăng', 'Thôn Vĩnh Thiện', 'Thôn Vĩnh Hòa', 'Thôn Thiện Minh', 'Thôn Thiện Tân'],
    'Xã Bàu Hàm': ['Tân Hoa', 'Tân Hợp', 'Tân Việt', 'Cây Điều', 'Tân Lập 1', 'Tân Lập 2', 'Cây Điệp', 'Thuận Trường', 'Thuận Hòa', 'Thuận An', 'Trường An', 'Trung Tâm', 'Lợi Hà', 'Suối Tiên', 'Tân Thành'],
    'Xã Cẩm Mỹ': ['Suối Sóc', 'Cẩm Sơn', 'Đồng Tâm', 'Lò Than', 'Tân Xuân', 'Tân Bình', 'Tân Hoà', 'Tân Bảo', 'Tân Lập', 'Chính Nghĩa', 'Cam Tiên', 'Suối Cả', 'Suối Râm', 'Ấp 57', 'Láng Lớn', 'Duyên Lãng', 'Hoàn quân'],
    'Xã Dầu Giây': ['Ấp Lập Thành', 'Ấp Trần Hưng Đạo', 'Hưng Hiệp', 'Hưng Nghiã', 'Hưng Nhơn', 'ấp Lộ 25', 'ấp 9/4', 'Ngô quyền', 'Nguyễn Thái Học', 'ấp Lê Lợi', 'Ấp 3', 'Ấp 4', 'Ấp Phan Bội Châu', 'Ấp Trần Cao Vân', 'Ấp 1', 'Hưng Thạnh', 'Ấp 2'],
    'Xã Gia Kiệm': ['Nguyễn Huệ 1', 'Lê lợi 2', 'Bắc Sơn', 'Lạc Sơn', 'Đông Kim', 'Tây Nam', 'Võ Dõng 1', 'Võ Dõng 2', 'Võ Dõng 3', 'Phúc Nhạc 2', 'Tân Yên', 'Gia Yên', 'Nguyễn Huệ 2', 'Đông Bắc', 'Tây Kim', 'Nam Sơn', 'Phúc Nhạc 1'],
    'Xã Hưng Phước': ['Ấp 4', 'Ấp 5', 'Ấp 6', 'Bù Tam', 'Điện ảnh', 'Tân lập', 'Tân Trạch', 'Mười mẫu', 'Ấp 3', 'Phước Tiến', 'Tân phước', 'Tân hưng'],
    'Xã Hưng Thịnh': ['An Hoà', 'Nhân Hoà', 'Bàu Cá', 'An Bình', 'Quảng Đà', 'Hoà Bình', 'Hưng Long', 'Hưng Phát', 'Lộc Hoà', 'Hưng Bình'],
    'Xã La Ngà': ['Ấp 1', 'Ấp 4', 'Ấp 5', 'Vĩnh An', 'Phú Quý 1', 'Phú Quý 2', 'Ấp 94', 'Đồng Xoài', 'Hòa Bình', 'Đồn Điền 1', 'Đồn Điền 2', 'Suối Dzui', 'Đức Thắng', 'Ấp 3', 'Mít Nài'],
    'Xã Long Hà': ['Thôn 4', 'Thôn 6', 'Thôn 7', 'Thôn 8', 'Thôn 9', 'Thôn 10', 'Thôn 11', 'Thôn 1', 'Phù Mang 1', 'Phù Mang 3', 'Bù Ka 1', 'Bù Ka 2', 'Thôn Long Tân 1', 'Thôn Long Tân 2', 'Thôn Long Tân 3', 'Thôn Long Tân 4', 'Thôn Long Tân 5', 'Thôn Long Tân 6', 'Thôn Long Tân 7', 'Thôn 5A', 'Thôn 2', 'Thôn Thanh Long'],
    'Xã Long Phước': ['Đất mới', 'Phước hòa', 'Tập phước', 'Xóm gò bà ký', 'Ấp 1', 'Ấp 2', 'Ấp 3', 'Ấp 5 Bàu Cạn', 'Ấp 6', 'Ấp 7', 'Ấp 8', 'Suối cả', 'ấp Long Phước', 'Ấp 4'],
    'Xã Long Thành': ['An Bình', 'Bưng cơ', 'Bình Lâm', 'Hàng gòn', 'Thanh Bình', 'âp Cầu Xéo', 'ấp Phước Hải', 'ấp Phước Long', 'ấp Phước Thuận', 'ấp Văn Hải', 'Ấp 1 Long An', 'Ấp 2', 'Ấp 4', 'An lâm', 'Bưng môn', 'Xóm góc', 'Xóm trầu', 'ấp Bình Sơn', 'Ấp 6', 'Ấp 7', 'Ấp 8', 'Ấp 9', 'Ấp 10', 'Ấp 11', 'ấp Suối Trầu 1', 'ấp Suối Trầu 2', 'ấp Suối Trầu 3', 'ấp Long Phước', 'Suối Trầu', 'ấp Kim Sơn', 'Ấp 3', 'Ấp Xóm Đình', 'ấp Cẩm Đường', 'ấp Xã Hoàng'],
    'Xã Lộc Hưng': ['Ấp 2 Lộc Điền', 'Ấp 3 Lộc Điền', 'Ấp 4 Lộc Điền', 'Ấp 5 Lộc Điền', 'Ấp 8 Lộc Điền', 'Ấp 9 Lộc Điền', 'Quyết Thành', 'Sóc lớn', 'Bà ven', 'Cần lê', 'Chà đôn', 'Ấp 2 Lộc Hưng', 'Ấp 3 Lộc Hưng', 'Ấp 5 Lộc Hưng', 'Ấp 6 Lộc Hưng', 'Ấp 7 Lộc Hưng', 'Ấp 8 Lộc Hưng', 'Ấp 9 Lộc Hưng', 'Ấp 6 Lộc Điền', 'Ấp 1 Lộc Hưng', 'Ấp 1 Lộc Điền', 'Ấp 7 Lộc Điền', 'Đồi đá', 'Ấp 4 Lộc Hưng'],
    'Xã Lộc Ninh': ['Thôn Ninh Thuận', 'Thôn Ninh Hoà', 'Thôn Ninh Phú', 'Thôn Ninh Thái', 'Thôn Lộc Thái 1', 'Thôn Lộc Thái 2', 'Thôn Lộc Thái 3', 'Thôn Lộc Thái 4', 'Thôn Lộc Thái 6', 'Thôn Lộc Thái 7', 'Thôn Lộc Thái 8', 'Thôn Lộc Thái 9', 'Thôn Lộc Thuận 1', 'Thôn Lộc Thuận 3', 'Thôn Lộc Thuận 4', 'Thôn Lộc Thuận 5', 'Thôn Lộc Thuận 6', 'Thôn Lộc Thuận 7', 'Thôn Lộc Thuận 8', 'Thôn Lộc Thuận 9', 'Thôn Lộc Thuận 11', 'Thôn Lộc Thuận 3B', 'Thôn Ninh Thành', 'Thôn Lộc Thái 5', 'Thôn Lộc Thuận 2', 'Thôn Lộc Thuận 10', 'Thôn Ninh Phước', 'Thôn Ninh Thạnh', 'Thôn Ninh Thịnh'],
    'Xã Lộc Quang': ['Hiệp Thành Tân', 'Hiệp Thành', 'Hiệp Hòan A', 'Hiệp Hòan', 'Hiệp Tâm A', 'Hiệp Quyết', 'Chàng Hai', 'Việt Tân', 'Việt Quang', 'Bù Tam', 'Bồn Xăng', 'Tam nguyên', 'Bù Linh', 'Tân Lợi', 'Tân Hai', 'Bù Nồm', 'Soóc Rung', 'Thắng lợi', 'Hiệp Tâm', 'Vẻ vang'],
    'Xã Lộc Thành': ['Lộc Bình 2', 'Cần Dực', 'K liêu', 'Tà tê 2', 'Tà tê 1', 'Tân Bình 2', 'Tân Mai', 'Hưng Thịnh', 'Chà là', 'Hưng Thủy', 'Tà Thiết', 'Đồng tâm', 'Lộc Bình 1', 'Tân Bình 1', 'Cần lê'],
    'Xã Lộc Thạnh': ['Ấp 6', 'Ấp 7', 'Ấp 8', 'Ấp 8A', 'Ấp 8B', 'Ấp 8C', 'Ấp Suối Thôn', 'Thạnh Cường', 'Thạnh Trung', 'Thạnh Tân', 'Thạnh Biên', 'Hoa Lư', 'Thạnh Phú'],
    'Xã Lộc Tấn': ['Ấp 1B', 'Ấp 4A', 'Ấp 5A', 'Ấp 5B', 'Ấp 5C', 'Ấp 6A', 'Ấp 12', 'K57', 'Cây chặt', 'Bù núi A', 'Thạnh đông', 'Thạnh Tây', 'Ấp 1', 'Ấp 10', 'Ấp 11A', 'Ấp 11B', 'K54', 'Vườn bưởi', 'Ấp 6B', 'Bù núi B', 'Măng cải'],
    'Xã Minh Đức': ['Ấp 1A', 'Sóc Ruộng', 'Ấp 4', 'Tằng Hách', 'Sóc Rul', 'Phố Lố', 'An Tân', 'Ấp 1B', 'Đồng Dầu', 'Ấp 2A', 'Sóc Lộc Khê', 'Ấp 1', 'Ấp 2', 'Ấp 3', 'Sóc 6', 'Sóc Vàng', 'Bình Phú', 'Chà Lon', 'Sóc 5'],
    'Xã Nam Cát Tiên': ['Ấp 8', 'Ấp 10', 'Ấp 11', 'Ấp 1', 'Ấp 4', 'Ấp 5', 'ấp 6', 'Ấp 2', 'Ấp 9', 'Ấp 3', 'ấp 7'],
    'Xã Nghĩa Trung': ['Thôn 3', 'Thôn 14', 'Bình Minh', 'Thôn 5', 'Thôn 10', 'Thôn 16', 'Thôn 1', 'Thôn 2', 'Thôn 4', 'Thôn 6', 'Thôn 7', 'Thôn 8', 'Thôn 9', 'Thôn 15', 'Thôn 11', 'Thôn 12', 'Thôn 17', 'Bình Lợi', 'Bình Hòa', 'Bình Trung', 'Bình Thọ', 'Bình Tiến'],
    'Xã Nha Bích': ['Ấp 3 Nha Bích', 'Ấp 4 Nha Bích', 'Ấp 6 Nha Bích', 'Suối Ngang', 'Minh Lập 5', 'Minh Thắng 5', 'Ấp 5 Nha Bích', 'Minh Lập 1', 'Minh Lập 2', 'Minh Lập 3', 'Minh Lập 4', 'Minh Lập 6', 'Minh Lập 7', 'Minh Thắng 1', 'Minh Thắng 2', 'Minh Thắng 3', 'Minh Thắng 4', 'Minh Thắng 6', 'Minh Thắng 7', 'Ấp 1 Nha Bích', 'Ấp 2 Nha Bích'],
    'Xã Nhơn Trạch': ['Bình Phú', 'Long hiệu', 'Đất mới', 'Phú Mỹ 2', 'Phú Mỹ 1', 'Xóm Hố', 'Chợ', 'Trầu', 'Bến sắn', 'ấp Mỹ Khoan', 'ấp Phước Mỹ', 'ấp Phước Kiểng', 'ấp Phước Lai', 'ấp Phước Hiệp', 'Ấp 2', 'Ấp 3', 'Vĩnh tuy', 'Bến cam', 'Ấp 1'],
    'Xã Phú Hòa': ['Ấp Phú Hòa 1', 'Ấp Phú Hòa 2', 'Ấp Phú Hòa 3', 'Ấp Phú Lợi 1', 'Ấp Phú Lợi 2', 'Ấp Phú Lợi 3', 'Ấp Phú Lợi 4', 'Ấp Phú Lợi 5', 'Ấp Phú Điền 1', 'Ấp Phú Điền 2', 'Ấp Phú Điền 4', 'Ấp Phú Điền 5', 'Ấp Phú Hòa 4', 'Ấp Phú Điền 3'],
    'Xã Phú Lâm': ['Thanh thọ 3', 'Phương mai 1', 'Phương Lâm', 'Phương Mai', 'Thanh Thọ', 'Thanh lâm', 'Đa tôn', 'Suối Đá', 'Phú Dũng', 'Phú Tân', 'Phú Hợp A', 'Phú Cường', 'Phú Thành', 'Phú Lâm 1', 'Phú Lâm 3', 'Phú Lâm 4', 'Phú Lâm 5', 'Phú Thắng', 'Phú Thạch', 'Phú Yên', 'Thanh trung', 'Phú Hợp B', 'Phú Lợi'],
    'Xã Phú Lý': ['Ấp 1', 'Ấp 2', 'Ấp 3', 'Bình Chánh', 'Bầu Phụng', 'Cây cầy', 'Lý Lịch 1', 'Lý Lịch 2', 'Ấp 4'],
    'Xã Phú Nghĩa': ['Bù Kroai', 'Bù Gia Phúc 2', 'Tân Lập', 'Đak Son 2', 'Bình Đức 1', 'Bình đức 2', 'Phước sơn', 'Sơn Trung', 'Thôn 19/5', 'Bù Gia Phúc 1', 'Đak Son 1', 'Khắc Khoan', 'Hai Căn', 'Bù Cà Mau', 'Phú Nghĩa', 'Đức Lập', 'Thôn 1', 'Thôn 2', 'Thôn 3', 'Cây Da', 'Đak Khâu', 'Thác Dài'],
    'Xã Phú Riềng': ['Tân Phú', 'Tân Hòa', 'Phú Thành', 'Phú hưng', 'Phú Nguyên', 'Phú Bình', 'Phú Tân', 'Phú Thịnh', 'Phú Cường', 'Phú Hòa', 'Tân Phước', 'Tân Hiệp 1', 'Tân Hiệp 2', 'Tân Bình', 'Tân Lực', 'Phú Lợi', 'Phú Thuận', 'Tân Long', 'Phú Vinh'],
    'Xã Phú Trung':['Phú Nghĩa', 'Phú An', 'Phú Lâm', 'Phú Bình', 'Đồng Tiến', 'Bình Trung', 'Đồng Tâm', 'Đồng Tháp', 'Phú Tâm', 'Bù Tố', 'Phú Tiến', 'Bàu Đỉa'],
    'Xã Phú Vinh': ['Ấp 1', 'Ấp 3', 'Ấp 5', 'Ấp 6', 'Ấp 7', 'Ấp Phú Vinh 2', 'Ấp Phú Vinh 3', 'Ấp Phú Vinh 4', 'Ba Tầng', 'Suối Soong 1', 'Suối Soong 2', 'Ấp 2', 'Ấp 8', 'Ấp Phú Vinh 5', 'Ấp Phú Vinh 1'],
    'Xã Phước An': ['Ấp 1', 'Ấp 2', 'Ấp 3', 'Ấp 5', 'Bàu bông', 'Bà trường', 'Qưới thạnh', 'Vũng gấm', 'Chính nghiã', 'Đại thắng', 'Hoà Bình', 'Nhất trí', 'Sơn hà', 'Thành công', 'Thanh minh', 'Vĩnh cửu', 'Ấp 4', 'Đoàn kết', 'Thống nhất'],
    'Xã Phước Sơn': ['Thôn 1 Thống Nhất', 'Thôn 2 Thống Nhất', 'Thôn 3 Thống Nhất', 'Thôn 4 Thống Nhất', 'Thôn 5 Thống Nhất', 'Thôn 7 Thống Nhất', 'Thôn 8 Thống Nhất', 'Thôn 9 Thống Nhất', 'Thôn 10 Thống Nhất', 'Thôn 11 Thống Nhất', 'Thôn 12 Thống Nhất', 'Thôn 1', 'Thôn 2', 'Thôn 3', 'Thôn 8', 'Thôn 7', 'Thôn 5', 'Thôn 6', 'Thôn 2 Đăng Hà', 'Thôn 3 Đăng Hà', 'Thôn 4 Đăng Hà', 'Thôn 5 Đăng Hà', 'Thôn 6 Đăng Hà', 'Thôn 6 Thống Nhất', 'Thôn 4', 'Thôn 1 Đăng Hà'],
    'Xã Phước Thái': ['Ấp 3 Phước Thái', 'Ấp 1A', 'Ấp 1C', 'HIEN ĐUC', 'HIEN HOA', 'LONG PHU', 'ấp Tân Hiệp 1', 'ấp Tân Hiệp 3', 'ấp Tân Hiệp 4', 'ấp Tân Hiệp 5', 'ấp Phước Bình 1', 'ấp Phước Bình 2', 'ấp Phước Bình 3', 'ấp Phước Bình 5', 'ấp Phước Bình 7', 'Ấp 4 Phước Bình', 'Ấp 1B', 'ấp Tân Hiệp 2', 'ấp Phước Bình 6'],
    'Xã Sông Ray': ['ẤP 2', 'ẤP 3', 'ẤP 4', 'ẤP 6', 'Ấp 7', 'Ấp 9', 'Ấp 11', 'Ấp 12', 'Ấp 13', 'Ấp 14', 'ẤP 5', 'Ấp 10', 'Ấp 15', 'ẤP 1', 'Ấp 8', 'Ấp 16'],
    'Xã Thanh Sơn': ['Ấp 1', 'Ấp 2', 'Ấp 4', 'Ấp 5', 'Ấp 6', 'Ấp 7', 'Ấp 8', 'Ấp 3'],
    'Xã Thiện Hưng': ['Ấp 11', 'Ấp 12', 'Ấp 13', 'Ấp 14', 'Ấp 15', 'Ấp Thiện Cư', 'Ấp 17', 'Ấp 1', 'Ấp 3', 'Ấp 4', 'Ấp 5', 'Ấp 7', 'Ấp 8', 'Ấp 9', 'Ấp 2', 'Ấp Thanh Xuân', 'Ấp Thanh Thủy', 'Ấp Thanh Tâm', 'Ấp Thanh Sơn', 'Ấp Thanh Trung', 'Ấp 10', 'Ấp 16', 'Ấp 6', 'Ấp Thanh Bình'],
    'Xã Thuận Lợi': ['Thuận An', 'Thuận Hòa I', 'Thuận Hòa II', 'Thuận Thành II', 'Thuận Thành I', 'Thuận Tiến', 'Thuận Tân', 'Bù Xăng', 'Tân Phú', 'Thuận Phú II', 'Thuận Phú III', 'Đồng Búa', 'Cây Me', 'Thuận Hải', 'Thuận Bình', 'Thuận Phú I'],
    'Xã Thọ Sơn': ['Sơn Lợi', 'Thôn 1', 'Sơn Lang', 'Sơn Lập', 'Sơn Hiệp', 'Sơn Thọ', 'Sơn Hòa', 'Sơn Tùng', 'Sơn Thủy', 'Thôn 2', 'Thôn 3', 'Thôn 4', 'Thôn 5', 'Thôn 6', 'Sơn Phú', 'Sơn Thành', 'Sơn Tân', 'Sơn Qúy'],
    'Xã Thống Nhất': ['Cây Xăng', 'Cầu Ván', 'Chợ', 'Tam Bung 2', 'Suối Son', 'Thái Hoà', 'Bến Nôm 1', 'Bến Nôm 2', 'Phú Tâm', 'Phú Tân', 'Phú Thọ', 'Tam Bung Phú Cường', 'Phú Cường', 'Dốc Mơ 1', 'Dốc Mơ 3', 'Bạch Lâm 1', 'Bạch Lâm 2', 'Đức Long 2', 'Đức Long 3', 'Tân Lập', 'Phú Dòng', 'Dốc Mơ 2', 'Đức Long 1'],
    'Xã Trảng Bom': ['Ấp 1', 'Ấp 3', 'ấp 5', 'Xây Dựng', 'Độc Lập', 'Hoà Bình', 'Ấp 9', 'Ấp 10', 'Ấp 11', 'Ấp 12B', 'Ấp 6', 'Ấp 7', 'Quãng Hoà', 'Quãng Phát', 'Quãng Biên', 'Ấp 2', 'Đoàn Kết', 'Ấp 8', 'Ấp 4', 'Bảo Vệ', 'Ấp 12A', 'Quảng Lộc'],
    'Xã Trị An': ['ấp Vĩnh An 1', 'ấp Vĩnh An 2', 'ấp Vĩnh An 3', 'ấp Vĩnh An 4', 'ấp Vĩnh An 6', 'ấp Vĩnh An 7', 'ấp Vĩnh An 8', 'Ấp 1 Trị An 2', 'Ấp 2 Trị An 2', 'Ấp 3 Trị An 2', 'Hiếu Liêm', 'ấp Mã Đà', 'ấp Suối Rộp', 'ấp Cây Sung', 'ấp Suối Tượng', 'ấp Bà Hào', 'ấp Suối Trau', 'ấp Vĩnh An 5', 'Ấp 4 Trị An 2'],
    'Xã Tà Lài': ['Ấp 2', 'Ấp 4', 'Ấp 5', 'Ấp 3', 'Ấp Phú Lập 1', 'Ấp Phú Lập 2', 'Ấp Phú Lập 5', 'Ấp Phú Lập 3', 'Ấp Phú Lập 6', 'Ấp Phú Lập 7', 'Ấp Phú Thịnh 1', 'Ấp Phú Thịnh 3', 'Ấp Phú Thịnh 5', 'Ấp Phú Thịnh 6', 'Ấp Phú Thịnh 7', 'Ấp Phú Thịnh 2', 'Ấp 1', 'Ấp Phú Lập 4', 'Ấp Phú Thịnh 4'],
    'Xã Tân An': ['ấp 9 xã Tân An', 'ấp 8 xã Tân An', 'ấp 7 xã Tân An', 'Bình Chánh', 'Cây Xoài', 'Thái An', 'Ấp 1 Vĩnh Tân', 'Ấp 2 Vĩnh Tân', 'Ấp 3 Vĩnh Tân', 'Ấp 4', 'Ấp 6', 'Bình trung', 'Ấp 5'],
    'Xã Tân Hưng': ['Đông Hồ', 'Ấp 5', 'An Hòa', 'Phùm Lu - Tư Ly', 'An Qúy', 'Bù Dinh', 'An Sơn', 'Thuận An', 'Địa Hạt - Sóc Dầm', 'Trung Sơn', 'Xa Cô', 'Trà Thanh - Lồ Ô', 'Sóc Qủa', 'Hưng Yên', 'Hưng Lập A', 'Hưng Lập B', 'Lòng Hồ', 'Hưng Phát', 'Sở Xiêm', 'Ấp 2', 'Ấp 3', 'Ấp 4', 'Sóc Ruộng', 'Ấp 1', 'Thanh Sơn'],
    'Xã Tân Khai': ['Thôn 5', 'Đồng Nơ 3', 'Tân Hiệp 1', 'Sóc 5', 'Thôn 1', 'Thôn 2', 'Thôn Tàu Ô', 'Thôn 6', 'Thôn 7', 'Đồng Nơ 1', 'Đồng Nơ 2', 'Đồng Nơ 5', 'Đồng Tân', 'Bàu Lùng', 'Tân Hiệp 2', 'Tân Hiệp 3', 'Tân Hiệp 4', 'Tân Hiệp 5', 'Thôn 3', 'Đồng Nơ 4', 'Tân Lập'],
    'Xã Tân Lợi': ['Đồng Chắc', 'Đồng Xê', 'Đồng Tân', 'Cây Cầy', 'Papếch', 'Suối Nhung', 'Suối Da', 'Trảng Tranh', 'Thạch Màng', 'Đồng Bia', 'Suối Đôi', 'Bàu Le', 'Ấp 05', 'Quân Y'],
    'Xã Tân Phú': ['Tân Phú 1', 'Tân Phú 2', 'Tân Phú 6', 'Tân Phú 8', 'Tân Phú 3', 'Tân Phú 4', 'Tân Phú 7', 'Trà Cổ 11', 'Trà Cổ 13', 'Thọ lâm 1', 'Thọ lâm 2', 'Ngọc Lâm 4', 'Ngọc Lâm 5', 'Ngọc Lâm 1', 'Ngọc lâm 2', 'Ngọc lâm 3', 'Thanh Thọ', 'Bàu chim', 'Thọ Lâm', 'Phú Lộc 15', 'Phú Lộc 16', 'Phú Lộc 17', 'Phú Lộc 18', 'Tân Phú 5', 'Trà Cổ 12', 'Bầu mây', 'Phú Lộc 14', 'Tân Phú 9', 'Trà Cổ 10'],
    'Xã Tân Quan': ['Bào Teng', 'Chà Hòa', 'Tranh 3', 'Cây Gõ', 'Long Bình', 'Ấp 2', 'Xạc Lây', 'Ấp 4', 'Ruộng 1', 'Ruộng 2', 'Xa Lách', 'Sóc Lớn', 'Ấp 23 Lớn', 'Văn Hiên 1', 'Tổng Cui Nhỏ', 'Tổng Cui Lớn', 'Trường An', 'Trường THịnh', 'Xa Trạch 1', 'Xa trạch sóc', 'Sóc Tranh', 'Sóc dày', 'Sở líp', 'Sóc Trào A', 'Sóc Trào B', 'Quản Lợi B', 'Sóc Lếch', 'Phú Miên', 'Hưng Thạnh', 'Núi Gió', 'Bà Lành', 'Ruộng 3', 'Ấp 5', 'Văn Hiên 2', 'Xa Trạch 2', 'Quản Lợi A', 'Ấn Lợi'],
    'Xã Tân Tiến': ['Tân Thuận', 'Sóc Nê', 'Tân Bình', 'Tân phước', 'Tân an', 'Tân Hòa', 'Tân Nghĩa', 'Tân phong', 'Tân Hội', 'Tân phú', 'Tân Lợi', 'Tân Định', 'Tân Lập', 'Tân Đông', 'Ấp 1', 'Ấp 2', 'Ấp 3', 'Ấp 4', 'Ấp 7', 'Ấp 8', 'Ấp 54', 'Ấp 9', 'Tân Nhân', 'Tân Hiệp', 'Ấp 6'],
    'Xã Xuân Bắc': ['Ấp 1A xã Xuân Bắc', 'Ấp 3', 'Ấp 4', 'Ấp 5A xã Xuân Bắc', 'Ấp 6A xã Xuân Bắc', 'Ấp 1 Xuân Bắc', 'Ấp 2b', 'Ấp 3a', 'Ấp 4a', 'Ấp 4b', 'Ấp 5 Xuân Bắc', 'Ấp 6 Xuân Bắc', 'Bàu cối', 'Ấp 8', 'Chợ', 'Ấp 3b', 'Ấp 7', 'Ấp 2', 'Ấp 2a'],
    'Xã Xuân Hòa': ['ẤP XUÂN HƯNG 1', 'ẤP XUÂN HƯNG 2', 'ẤP XUÂN HƯNG 4', 'Ấp Xuân Hưng 1A', 'Ấp Xuân Hưng 2A', 'Ấp Xuân Hưng 3A', 'Ấp Xuân Tâm 1', 'Ấp Xuân Tâm 2', 'Ấp Xuân Tâm 4', 'Ấp Xuân Tâm 6', 'Ấp Xuân Tâm 7', 'Gia ui', 'ẤP XUÂN HOÀ 1', 'ẤP XUÂN HOÀ 2', 'ẤP XUÂN HOÀ 3', 'ẤP XUÂN HOÀ 4', 'Ấp Xuân Hưng 5', 'Ấp Xuân Tâm 3', 'Suối đục', 'ẤP XUÂN HƯNG 3', 'Ấp Xuân Tâm 5'],
    'Xã Xuân Lộc': ['Tân tiến', 'Việt Kiều 2', 'Bình Minh 2', 'Trung sơn', 'Trung nghĩa', 'Bàu sen', 'Trung hiếu', 'Trung hưng', 'Trung lương', 'Thọ Bình', 'Thọ chánh', 'Thọ tân', 'Thọ hòa', 'Thọ lộc', 'Thọ phước', 'Gia Ray 1', 'Gia Ray 3', 'Gia Ray 4', 'Gia Ray 5', 'Gia Ray 6', 'Gia Ray 7', 'Suối Cát 1', 'Suối Cát 2', 'Bình Minh 1', 'Việt Kiều 1', 'Tam hiệp', 'Gia hoà', 'Trung tín', 'Thọ trung', 'Gia Ray 2', 'Gia Ray 8'],
    'Xã Xuân Phú': ['Bình Hoà', 'Bình Tân', 'Bình Xuân 1', 'Bình Xuân 2', 'Đông minh', 'Tây minh', 'Tân Bình 1', 'Tân Bình 2', 'Bình Tiến'],
    'Xã Xuân Quế': ['Ấp Ông Quế', 'Ấp 57', 'Suối Râm', 'Ấp Thanh Bình', 'Ấp Sông Nhạn', 'Ấp 3', 'Ấp 4', 'Ấp 6', 'Ấp 61', 'Suối Đục', 'Ấp Trung Hậu', 'Ấp 5'],
    'Xã Xuân Thành': ['Trảng táo', 'Tân hợp', 'Tân hoà', 'Tân hữu', 'Chà rang', 'Bầu sình', 'Phượng vỹ', 'Gia tỵ', 'Cây da', 'Tân hưng', 'Gia lào'],
    'Xã Xuân Đông': ['Ấp 1', 'Ấp 3', 'Ấp 4', 'Ấp 5', 'Ấp 6', 'Ấp 7', 'Ấp 9', 'Ấp 10', 'Ấp 11', 'Ấp 12', 'Thoại Hương', 'La Hoa', 'Suối Nhát', 'Suối Lức', 'Cọ Dầu 1', 'Cọ Dầu 2', 'Láng Me 1', 'Bằng Lăng', 'Ấp 2', 'Ấp 8', 'Bể Bạc', 'Láng Me 2'],
    'Xã Xuân Đường': ['Ấp Xuân Đường', 'Ấp 2', 'Ấp 1', 'Cẩm Đường', 'Suối Quýt', 'Ấp 4', 'Ấp 8', 'Tự Túc', 'Ấp 3'],
    'Xã Xuân Định': ['Bảo Định', 'Bảo Thị', 'Nông Doanh', 'Tân Hạnh', 'Tân Mỹ', 'Hòa Bình', 'Hòa hợp', 'Bưng cần', 'Nam Hà', 'Chiến thắng'],
    'Xã Đa Kia': ['Thôn 6B', 'Thôn 4', 'Bình Giai', 'Thôn 1', 'Thôn 2A', 'Thôn 2B', 'Thôn 3A', 'Thôn 4A', 'Thôn 5A', 'Thôn 6A', 'Thôn 7', 'Thôn 8', 'Thôn 9', 'Thôn 2', 'Thôn 3', 'Thôn 5', 'Thôn 6', 'Bình Hà 1', 'Bình Thủy', 'Bình Tân', 'Bình Lợi', 'Bình Tiến 1', 'Bình tiến 2', 'Bình Hà 2', 'Bù Tam'],
    'Xã Dak Lua': ['Ấp 1', 'Ấp 2', 'Ấp 3', 'Ấp 4', 'ấp 5', 'Ấp 6', 'Ấp 7'],
    'Xã Đăk Nhau': ['Đak Xuyên', 'Thống Nhất', 'Đăng Nhau', 'Đak La', 'Đặk Liên', 'Thôn 2', 'Thôn 3', 'Thôn 4', 'Thôn 5', 'Đăng lang', 'Thôn 1', 'Thôn 6', 'Đak Uý'],
    'Xã Đăk Ơ': ['Bù Bưng', 'Thôn 3', 'Bù Khơn', 'Thôn 6', 'Thôn 7', 'Thôn 9', 'Đak U', 'Đak Lim', 'Thôn 4', 'Bù Ka', 'Thôn 10', 'Bù Xia'],
    'Xã Đại Phước': ['Câu kê', 'Cát lái', 'Phước lương', 'Rạch bảy', 'Bến ngự', 'Gông ông đông', 'Thị cầu', 'Bến cộ', 'Cù lao', 'Phước lý', 'Ấp 1', 'Ấp 3', 'Ấp 2', 'Phú tân', 'Bến Đình'],
    'Xã Định Quán': ['Ấp Gia Canh 1', 'Ấp Gia Canh 2', 'Ấp Gia Canh 7', 'Ấp Gia Canh 8', 'Ấp Gia Canh 9', 'Hiệp Quyết', 'Hiệp Tâm 1', 'Hiệp Tâm 2', 'Hiệp Lực', 'Hiệp Đồng', 'Hiệp Nghĩa', 'Hòa Thành', 'Hòa Thuận', 'Hòa Đồng', 'Hòa Hiệp', 'Ấp Phú Ngọc 2', 'Ấp Phú Ngọc 4', 'Ấp Phú Ngọc 5', 'Ấp Phú Ngọc 7', 'Ấp Gia Canh 5', 'Hiệp Nhất', 'Ấp Phú Ngọc 1', 'Ấp Gia Canh 3', 'Ấp 114', 'Hiệp Lợi', 'Hòa Trung', 'Ấp Phú Ngọc 3'],
    'Xã Đồng Phú': ['Thôn 3', 'Thôn 4', 'Thôn 6', 'Thôn 7', 'Thôn 8', 'Thôn 9', 'Thôn Tân An', 'Thôn Bàu Ké', 'Thôn Dên Dên', 'Thôn Tân Tiến', 'Thôn Thái Dũng', 'Thôn Minh Tân', 'Thôn Minh Hòa', 'Thôn Tân Hà', 'Thôn 1', 'Thôn 2', 'Thôn Thắng Lợi', 'Thôn Tân Liên', 'Thôn An Hòa', 'Thôn 5'],
    'Xã Đồng Tâm': ['Cây Điệp', 'Phước Tâm', 'Cầu Rạt', 'Phước Tân', 'Sắc Xi', 'Phước Tiến', 'Nam Đô', 'Ấp Đồng Tâm 2', 'Ấp Đồng Tâm 3', 'Ấp Đồng Tâm 4', 'Ấp Đồng Tâm 5', 'Ấp Đồng Tâm 6', 'Ấp Đồng Tiến 1', 'Ấp Đồng Tiến 2', 'Ấp Đồng Tiến 4', 'Ấp Đồng Tiến 5', 'Ấp Đồng Tiến 6', 'Ấp Suối Binh', 'Ấp Suối Đôi', 'Ấp Cầu Hai', 'Lam Sơn', 'Ấp Đồng Tâm 1', 'Ấp Đồng Tiến 3'],
}

# Tra cứu ngược: thôn → xã
THON_TO_XA: dict[str, str] = {
    thon: xa
    for xa, ds in XA_THON_MAP.items()
    for thon in ds
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


# ── Mapping mã Điểm Giao Dịch theo PGD (nguồn: file Excel MÃ ĐIỂM GIAO DỊCH ĐỒNG NAI.xlsx) ──────
DGD_MA_MAP: dict[str, dict[str, str]] = {
    "4601": {
        "TXN0460414": "Bửa Hòa",
        "TXN0460415": "Biên Hòa",
        "TXN0460417": "Tân Hạnh",
        "TXN0460418": "Tân Vạn",
        "TXN0462401": "Hố Nai",
        "TXN0460419": "Hiệp Hòa",
        "TXN0460420": "Thiện Tân",
        "TXN0460421": "An Bình",
        "TXN0460422": "Long Bình Tân",
        "TXN0460423": "Bửu Long",
        "TXN0460424": "Thống Nhất 2",
        "TXN0460425": "Tân Mai",
        "TXN0460426": "Hố Nai 3",
        "TXN0460427": "Tam Phước",
        "TXN0460428": "Phước Tân",
        "TXN0460429": "Trung Dũng",
        "TXN0460430": "Bửu Hòa",
        "TXN0460431": "Long Hưng",
        "TXN0460432": "An Hòa",
        "TXN0460433": "Trảng Dài",
        "TXN0460434": "Hố Nai 2",
        "TXN0460435": "Tân Biên",
        "TXN0460436": "Hố Nai",
        "TXN0460437": "Tam Hiệp",
        "TXN0460438": "Bình Đa",
        "TXN0460439": "Long Bình",
        "TXN0462402": "Tân Hiệp 3",
        "TXN0462403": "Thiện Tân 2",
        "TXN0462404": "Bình Minh",
        "TXN0462405": "Quảng Tiến",
        "TXN0462406": "Bắc Sơn",
    },
    "4602": {
        "TXN0460207": "Tam An",
        "TXN0460208": "An Phước",
        "TXN0460706": "Bình An",
        "TXN0460209": "Bình Sơn 2",
        "TXN0460210": "Phước Bình 2",
        "TXN0460211": "Lộc An 2",
        "TXN0460212": "Bàu Cạn",
        "TXN0460213": "Long Thành",
        "TXN0460214": "Long An",
        "TXN0460215": "Long Phước",
        "TXN0460216": "Tân Hiệp 2",
        "TXN0460217": "Bình An 2",
        "TXN0460218": "Phước Thái",
    },
    "4603": {
        "TXN0460302": "Đồi 61",
        "TXN0460303": "An Viễn",
        "TXN0460611": "Bàu Hàm 3",
        "TXN0460304": "Trảng Bom",
        "TXN0460305": "Bàu Hàm",
        "TXN0460306": "Đông Hòa",
        "TXN0460307": "Thanh Bình 2",
        "TXN0460308": "Bắc Sơn",
        "TXN0460309": "Quảng Tiến",
        "TXN0460310": "Đông Hà",
        "TXN0460311": "Bình Minh",
        "TXN0460312": "Hưng Thịnh",
        "TXN0460313": "Tân Đông",
        "TXN0460314": "Tây Ninh",
        "TXN0460315": "Đồng Nguồn",
    },
    "4604": {
        "TXN0460401": "Tân Phong",
        "TXN0460402": "Bình Minh",
        "TXN0460403": "Sông Trầu",
        "TXN0460404": "Bàu Sen",
        "TXN0460405": "Long An",
        "TXN0460406": "Vĩnh Tân",
        "TXN0460407": "Thạnh Phú",
        "TXN0460408": "Tân Hòa",
        "TXN0460409": "Bình Hòa",
        "TXN0460410": "Phước Thiện",
        "TXN0460411": "Long Định",
        "TXN0460412": "Tân Hiệp",
        "TXN0460413": "Ngãi Đăng",
    },
    "4605": {
        "TXN0460501": "Nguyễn Huệ",
        "TXN0460502": "Phước Lý",
        "TXN0460503": "Bình Mỹ",
        "TXN0460504": "Tân Phú",
        "TXN0460505": "Phước Tân",
        "TXN0460506": "Long Phước",
        "TXN0460507": "Tân Hạnh",
        "TXN0460508": "Vĩnh Cửu",
        "TXN0460509": "Mã Đà",
        "TXN0460510": "Trảng Bom",
        "TXN0460511": "Đắc Lua",
        "TXN0460512": "La Ngà",
        "TXN0460513": "Phước Lâm",
        "TXN0460514": "Tân Lập",
    },
    "4606": {
        "TXN0460601": "Long An",
        "TXN0460602": "Long Giao",
        "TXN0460603": "Bình Minh",
        "TXN0460604": "Phước Bình",
        "TXN0460605": "Sông Ray",
        "TXN0460606": "Ngãi Giao",
        "TXN0460607": "Bà Rịa",
        "TXN0460608": "Phước Hưng",
        "TXN0460609": "Suối Nghệ",
        "TXN0460610": "Hòa Long",
    },
    "4607": {
        "TXN0460701": "Long Mỹ",
        "TXN0460702": "Phước Tỉnh",
        "TXN0460703": "Đá Bạc",
        "TXN0460704": "Bàu Lâm",
        "TXN0460705": "Nguyễn Việt Khái",
        "TXN0460707": "Phước Hải",
        "TXN0460708": "Phước Tân",
        "TXN0460709": "Phước Hưng",
        "TXN0460710": "Tân Hải",
        "TXN0460711": "Lông Sơn",
    },
    "4608": {
        "TXN0460801": "Bình Châu",
        "TXN0460802": "Lộc An",
        "TXN0460803": "An Bình",
        "TXN0460804": "Tân Thạnh",
        "TXN0460805": "Tân Hải",
        "TXN0460806": "Tân Phong",
        "TXN0460807": "Tân Tiến",
        "TXN0460808": "Tân Thành",
        "TXN0460809": "Tân Việt",
        "TXN0460810": "Tân Hưng",
        "TXN0460811": "Tân Quý",
        "TXN0460812": "Tân Hội",
        "TXN0460813": "Tân Thới",
        "TXN0460814": "Tân Tây",
        "TXN0460815": "Tân Bắc",
    },
    "4609": {
        "TXN0460901": "Phước Tân",
        "TXN0460902": "Tân Phước",
        "TXN0460903": "Sông Xoài",
        "TXN0460904": "Tân Thành",
        "TXN0460905": "Tân Hiệp",
        "TXN0460906": "Tân Đông",
        "TXN0460907": "Tân Trung",
        "TXN0460908": "Tân Tây",
        "TXN0460909": "Tân Nam",
        "TXN0460910": "Tân Bắc",
        "TXN0460911": "Long Điền",
    },
    "4610": {
        "TXN0461001": "Long Đất",
        "TXN0461002": "Phước Tân",
        "TXN0461003": "An Ngãi",
        "TXN0461004": "Tam Phước",
        "TXN0461005": "Long Mỹ",
        "TXN0461006": "Lâm San",
        "TXN0461007": "Bình Thạnh",
        "TXN0461008": "Quả Cầu",
        "TXN0461009": "Suối Nhỏ",
        "TXN0461010": "Bình An",
        "TXN0461011": "Tân Hòa",
        "TXN0461012": "Tân Thạnh",
        "TXN0461013": "Tân Hải",
    },
    "4611": {
        "TXN0461101": "Cần Giờ",
        "TXN0461102": "Lý Nhơn",
        "TXN0461103": "Tam Thôn Hiệp",
        "TXN0461104": "An Thới Đông",
        "TXN0461105": "Bình Khánh",
        "TXN0461106": "Long Hòa",
        "TXN0461107": "Rạch Kiếc",
        "TXN0461108": "Thạnh An",
        "TXN0461109": "Tam Thôn Phước",
        "TXN0461110": "Vàm Sát",
        "TXN0461111": "Xà Lát",
        "TXN0461112": "Khu kinh tế mới",
    },
    "5024": {
        "TXN0502401": "Đồng Kho",
        "TXN0502402": "Tân Hiệp",
        "TXN0502403": "Đồng Nai",
        "TXN0502404": "Sông Trầu",
        "TXN0502405": "Tân Phong",
        "TXN0502406": "Đồng Nguồn",
        "TXN0502407": "Mã Đà",
    },
    "5025": {
        "TXN0502501": "Phước Thái",
        "TXN0502502": "Phước Bình",
        "TXN0502503": "Phước Tân",
        "TXN0502504": "Phước Lâm",
        "TXN0502505": "Phước Vinh",
        "TXN0502506": "Phước Hòa",
        "TXN0502507": "Phước An",
        "TXN0502508": "Phước Điền",
        "TXN0502509": "Phước Chánh",
        "TXN0502510": "Phước Khánh",
        "TXN0502511": "Phước Mỹ",
        "TXN0502512": "Phước Thạnh",
        "TXN0502513": "Phước Lý",
        "TXN0502514": "Phước Quý",
        "TXN0502515": "Phước Trung",
    },
    "5026": {
        "TXN0502601": "Tân Hòa",
        "TXN0502602": "Tân Minh",
        "TXN0502603": "Tân Thành",
        "TXN0502604": "Tân Hiệp",
        "TXN0502605": "Tân An",
        "TXN0502606": "Tân Hưng",
        "TXN0502607": "Tân Phú",
        "TXN0502608": "Tân Khánh",
    },
    "5027": {
        "TXN0502701": "Tân Tiến",
        "TXN0502702": "Tân Thạnh",
        "TXN0502703": "Tân Hội",
        "TXN0502704": "Tân Phước",
        "TXN0502705": "Tân Lập",
        "TXN0502706": "Tân Quý",
        "TXN0502707": "Tân Tây",
        "TXN0502708": "Tân Bắc",
    },
    "5028": {
        "TXN0502801": "Phước Lâm",
        "TXN0502802": "Phước Vinh",
        "TXN0502803": "Phước Hòa",
        "TXN0502804": "Phước An",
        "TXN0502805": "Phước Điền",
        "TXN0502806": "Phước Chánh",
        "TXN0502807": "Phước Khánh",
        "TXN0502808": "Phước Mỹ",
        "TXN0502809": "Phước Thạnh",
        "TXN0502810": "Phước Lý",
        "TXN0502811": "Phước Quý",
        "TXN0502812": "Phước Trung",
        "TXN0502813": "Phước Tân",
        "TXN0502814": "Phước Bình",
        "TXN0502815": "Phước Thái",
        "TXN0502816": "Phước Nam",
    },
    "5029": {
        "TXN0502901": "Tân Hưng",
        "TXN0502902": "Tân Phước",
        "TXN0502903": "Tân Thạnh",
        "TXN0502904": "Tân Hiệp",
        "TXN0502905": "Tân An",
        "TXN0502906": "Tân Minh",
        "TXN0502907": "Tân Thành",
        "TXN0502908": "Tân Hòa",
        "TXN0502909": "Tân Khánh",
        "TXN0502910": "Tân Phú",
        "TXN0502911": "Tân Lập",
    },
    "5034": {
        "TXN0503401": "Phước Bình",
        "TXN0503402": "Phước Vinh",
        "TXN0503403": "Phước Hòa",
        "TXN0503404": "Phước An",
        "TXN0503405": "Phước Điền",
        "TXN0503406": "Phước Chánh",
        "TXN0503407": "Phước Khánh",
        "TXN0503408": "Phước Mỹ",
    },
    "5036": {
        "TXN0503601": "Tân Hòa",
        "TXN0503602": "Tân Minh",
        "TXN0503603": "Tân Thành",
        "TXN0503604": "Tân Hiệp",
        "TXN0503605": "Tân An",
        "TXN0503606": "Tân Hưng",
        "TXN0503607": "Tân Phú",
        "TXN0503608": "Tân Khánh",
    },
    "5037": {
        "TXN0503701": "Phước Lâm",
        "TXN0503702": "Phước Vinh",
        "TXN0503703": "Phước Hòa",
        "TXN0503704": "Phước An",
        "TXN0503705": "Phước Điền",
        "TXN0503706": "Phước Chánh",
        "TXN0503707": "Phước Khánh",
        "TXN0503708": "Phước Mỹ",
    },
    "5038": {
        "TXN0503801": "Tân Tiến",
        "TXN0503802": "Tân Thạnh",
        "TXN0503803": "Tân Hội",
        "TXN0503804": "Tân Phước",
        "TXN0503805": "Tân Lập",
        "TXN0503806": "Tân Quý",
        "TXN0503807": "Tân Tây",
        "TXN0503808": "Tân Bắc",
        "TXN0503809": "Tân Nam",
    },
    "5039": {
        "TXN0503901": "Phước Thạnh",
        "TXN0503902": "Phước Lý",
        "TXN0503903": "Phước Quý",
        "TXN0503904": "Phước Trung",
        "TXN0503905": "Phước Tân",
        "TXN0503906": "Phước Bình",
        "TXN0503907": "Phước Thái",
        "TXN0503908": "Phước Nam",
        "TXN0503909": "Phước Khánh",
        "TXN0503910": "Phước Mỹ",
        "TXN0503911": "Phước Điền",
        "TXN0503912": "Phước Chánh",
        "TXN0503913": "Phước An",
    }
}

# ── Danh sách 270 Điểm Giao Dịch Xã (nguồn: danh sách ĐGD Đồng Nai) ──────
DGD_DANH_SACH: list[dict] = [
    {"stt": 1, "ma_dgd": "TXN0466703", "ten": "Trấn Biên", "xa": "Trấn Biên", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "6", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa khu phố Hoa Lư"},
    {"stt": 2, "ma_dgd": "TXN0460417", "ten": "Tân Hạnh", "xa": "Biên Hòa", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "6", "gio_gd": "8h30-10h30", "dia_diem": "UBMTTQVN phường Biên Hòa"},
    {"stt": 3, "ma_dgd": "TXN0466702", "ten": "Hiệp Hòa", "xa": "Trấn Biên", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "9", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa khu phố Nhất Hòa"},
    {"stt": 4, "ma_dgd": "TXN0460418", "ten": "Tân Vạn", "xa": "Biên Hòa", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "9", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa khu phố Tân Vạn 2"},
    {"stt": 5, "ten": "Tân Hiệp 3", "xa": "Tam Hiệp", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "10", "gio_gd": "8h30-10h30", "dia_diem": "Ban chỉ huy quân sự phường Tam Hiệp"},
    {"stt": 6, "ma_dgd": "TXN0466601", "ten": "Thiện Tân", "xa": "Trảng Dài", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "10", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa khu phố 6-7"},
    {"stt": 7, "ma_dgd": "TXN0466701", "ten": "An Bình", "xa": "Trấn Biên", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "11", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa khu phố An Bình"},
    {"stt": 8, "ma_dgd": "TXN0462801", "ten": "Long Bình Tân", "xa": "Long Hưng", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "11", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm phục vụ HCC phường Long Hưng"},
    {"stt": 9, "ma_dgd": "TXN0460415", "ten": "Biên Hòa", "xa": "Biên Hòa", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "12", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 10, "ma_dgd": "TXN0466704", "ten": "Bửu Long", "xa": "Trấn Biên", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "12", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa Tân Lại"},
    {"stt": 11, "ma_dgd": "TXN0466705", "ten": "Thống Nhất 2", "xa": "Trấn Biên", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "13", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa khu phố Thống Nhất"},
    {"stt": 12, "ma_dgd": "TXN0465803", "ten": "Tân Mai", "xa": "Tam Hiệp", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "13", "gio_gd": "8h30-10h00", "dia_diem": "Nhà văn hóa khu phố 21"},
    {"stt": 13, "ma_dgd": "TXN0462402", "ten": "Hố Nai 3", "xa": "Hố Nai", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "15", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND phường Hố Nai - Cơ sở 2"},
    {"stt": 14, "ma_dgd": "TXN0465901", "ten": "Tam Phước", "xa": "Tam Phước", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "15", "gio_gd": "9h00-11h30", "dia_diem": "Trung tâm Văn hóa thể thao Học tập cộng đồng phường"},
    {"stt": 15, "ma_dgd": "TXN0464902", "ten": "Phước Tân", "xa": "Phước Tân", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "16", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 16, "ma_dgd": "TXN0466706", "ten": "Trung Dũng", "xa": "Trấn Biên", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "17", "gio_gd": "08h30-11h", "dia_diem": "Trung tâm văn hóa thể thao, học tập cộng đồng"},
    {"stt": 17, "ten": "Bửu Hòa", "xa": "Biên Hòa", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "17", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa khu phố Bửu Hòa 2"},
    {"stt": 18, "ma_dgd": "TXN0462803", "ten": "Long Hưng", "xa": "Long Hưng", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "18", "gio_gd": "8h30-10h00", "dia_diem": "UBMTTQVN phường Long Hưng"},
    {"stt": 19, "ma_dgd": "TXN0462802", "ten": "An Hòa", "xa": "Long Hưng", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "18", "gio_gd": "8h30-10h30", "dia_diem": "Văn phòng khu phố 1"},
    {"stt": 20, "ma_dgd": "TXN0466602", "ten": "Trảng Dài", "xa": "Trảng Dài", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "19", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 21, "ma_dgd": "TXN0462601", "ten": "Hố Nai 2", "xa": "Long Bình", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "19", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm phục vụ HCC phường Long Bình"},
    {"stt": 22, "ma_dgd": "TXN0462602", "ten": "Tân Biên", "xa": "Long Bình", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "21", "gio_gd": "8h30-10h30", "dia_diem": "Văn phòng khu phố 19"},
    {"stt": 23, "ma_dgd": "TXN0462401", "ten": "Hố Nai", "xa": "Hố Nai", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "21", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 24, "ma_dgd": "TXN0465802", "ten": "Tam Hiệp", "xa": "Tam Hiệp", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "22", "gio_gd": "13h30-14h30", "dia_diem": "UBMTTQVN phường Tam Hiệp"},
    {"stt": 25, "ma_dgd": "TXN0465801", "ten": "Bình Đa", "xa": "Tam Hiệp", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "22", "gio_gd": "8h30-10h00", "dia_diem": "Trung tâm phục vụ HCC phường Tam Hiệp"},
    {"stt": 26, "ma_dgd": "TXN0462603", "ten": "Long Bình", "xa": "Long Bình", "pgd": "Hội sở Chi nhánh tỉnh", "ngay_gd": "22", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở Đảng ủy phường Long Bình"},
    {"stt": 27, "ma_dgd": "TXN0460207", "ten": "Tam An", "xa": "An Phước", "pgd": "PGD Long Thành", "ngay_gd": "6", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 28, "ten": "Bình Sơn 2", "xa": "Long Thành", "pgd": "PGD Long Thành", "ngay_gd": "7", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa ấp Bình Sơn"},
    {"stt": 29, "ten": "Phước Bình 2", "xa": "Phước Thái", "pgd": "PGD Long Thành", "ngay_gd": "9", "gio_gd": "9h00-11h30", "dia_diem": "Nhà văn hóa ấp Phước Bình 5"},
    {"stt": 30, "ma_dgd": "TXN0460208", "ten": "An Phước", "xa": "An Phước", "pgd": "PGD Long Thành", "ngay_gd": "10", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 31, "ten": "Lộc An 2", "xa": "Long Thành", "pgd": "PGD Long Thành", "ngay_gd": "11", "gio_gd": "8h30-10h30", "dia_diem": "Nhà VH ấp Bình Lâm"},
    {"stt": 32, "ma_dgd": "TXN0463002", "ten": "Bàu Cạn", "xa": "Long Phước", "pgd": "PGD Long Thành", "ngay_gd": "14", "gio_gd": "9h00-11h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 33, "ma_dgd": "TXN0463102", "ten": "Long Thành", "xa": "Long Thành", "pgd": "PGD Long Thành", "ngay_gd": "15", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 34, "ma_dgd": "TXN0463103", "ten": "Long An", "xa": "Long Thành", "pgd": "PGD Long Thành", "ngay_gd": "16", "gio_gd": "8h30-10h30", "dia_diem": "Nhà VH ấp 2"},
    {"stt": 35, "ma_dgd": "TXN0460706", "ten": "Bình An", "xa": "Bình An", "pgd": "PGD Long Thành", "ngay_gd": "17", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm phục vụ hành chính công xã xã Bình An"},
    {"stt": 36, "ma_dgd": "TXN0463001", "ten": "Long Phước", "xa": "Long Phước", "pgd": "PGD Long Thành", "ngay_gd": "18", "gio_gd": "09h-11h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 37, "ma_dgd": "TXN0465502", "ten": "Tân Hiệp 2", "xa": "Phước Thái", "pgd": "PGD Long Thành", "ngay_gd": "19", "gio_gd": "9h00-11h30", "dia_diem": "Nhà văn hóa ấp Tân Hiệp 3"},
    {"stt": 38, "ma_dgd": "TXN0460708", "ten": "Bình An 2", "xa": "Bình An", "pgd": "PGD Long Thành", "ngay_gd": "21", "gio_gd": "09h-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 39, "ma_dgd": "TXN0465501", "ten": "Phước Thái", "xa": "Phước Thái", "pgd": "PGD Long Thành", "ngay_gd": "22", "gio_gd": "9h00-11h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 40, "ma_dgd": "TXN0466501", "ten": "Trảng Bom", "xa": "Trảng Bom", "pgd": "PGD Trảng Bom", "ngay_gd": "5", "gio_gd": "08h30-10h30", "dia_diem": "Ban Chỉ huy quân sự xã Trảng Bom"},
    {"stt": 41, "ma_dgd": "TXN0460613", "ten": "Bàu Hàm", "xa": "Bàu Hàm", "pgd": "PGD Trảng Bom", "ngay_gd": "6", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm văn hóa học tập cộng đồng xã Bàu Hàm"},
    {"stt": 42, "ma_dgd": "TXN0462303", "ten": "Đông Hòa", "xa": "Hưng Thịnh", "pgd": "PGD Trảng Bom", "ngay_gd": "7", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp Hòa Bình, xã Hưng Thịnh"},
    {"stt": 43, "ten": "Thanh Bình 2", "xa": "Bàu Hàm", "pgd": "PGD Trảng Bom", "ngay_gd": "9", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa ấp Tân Thành, xã Bàu Hàm"},
    {"stt": 44, "ma_dgd": "TXN0461003", "ten": "Bắc Sơn", "xa": "Bình Minh", "pgd": "PGD Trảng Bom", "ngay_gd": "10", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm dịch vụ tổng hợp, xã Bình Minh"},
    {"stt": 45, "ma_dgd": "TXN0466504", "ten": "Quảng Tiến", "xa": "Trảng Bom", "pgd": "PGD Trảng Bom", "ngay_gd": "11", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm VH thể thao xã Trảng Bom"},
    {"stt": 46, "ma_dgd": "TXN0460302", "ten": "Đồi 61", "xa": "An Viễn", "pgd": "PGD Trảng Bom", "ngay_gd": "12", "gio_gd": "08h30-10h30", "dia_diem": "Đảng ủy xã An Viễn"},
    {"stt": 47, "ma_dgd": "TXN0462302", "ten": "Hưng Thịnh", "xa": "Hưng Thịnh", "pgd": "PGD Trảng Bom", "ngay_gd": "14", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 48, "ma_dgd": "TXN0466503", "ten": "Sông Trầu", "xa": "Trảng Bom", "pgd": "PGD Trảng Bom", "ngay_gd": "15", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa ấp 12A xã Trảng Bom"},
    {"stt": 49, "ma_dgd": "TXN0460303", "ten": "An Viễn", "xa": "An Viễn", "pgd": "PGD Trảng Bom", "ngay_gd": "16", "gio_gd": "08h30-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 50, "ma_dgd": "TXN0462304", "ten": "Hưng Thịnh 2", "xa": "Hưng Thịnh", "pgd": "PGD Trảng Bom", "ngay_gd": "17", "gio_gd": "08h30-10h30", "dia_diem": "Nhà văn hóa ấp Hưng Bình, xã Hưng Thịnh"},
    {"stt": 51, "ma_dgd": "TXN0466502", "ten": "Giang Điền", "xa": "Trảng Bom", "pgd": "PGD Trảng Bom", "ngay_gd": "18", "gio_gd": "08h30-10h30", "dia_diem": "Nhà văn hóa liên ấp Xây Dựng-Bảo Vệ, xã Trảng Bom"},
    {"stt": 52, "ten": "Bàu Hàm 1", "xa": "Bàu Hàm", "pgd": "PGD Trảng Bom", "ngay_gd": "19", "gio_gd": "8h30-10h30", "dia_diem": "Công an xã Bàu Hàm"},
    {"stt": 53, "ma_dgd": "TXN0460614", "ten": "Sông Thao", "xa": "Bàu Hàm", "pgd": "PGD Trảng Bom", "ngay_gd": "21", "gio_gd": "8h30-10h30", "dia_diem": "Đảng ủy xã Bàu Hàm"},
    {"stt": 54, "ma_dgd": "TXN0462301", "ten": "Tây Hòa", "xa": "Hưng Thịnh", "pgd": "PGD Trảng Bom", "ngay_gd": "22", "gio_gd": "8h30-10h30", "dia_diem": "Đảng ủy xã Hưng Thịnh"},
    {"stt": 55, "ma_dgd": "TXN0460514", "ten": "Bình Minh", "xa": "Bình Minh", "pgd": "PGD Trảng Bom", "ngay_gd": "23", "gio_gd": "08h30-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 56, "ma_dgd": "TXN0462102", "ten": "Xuân Tân", "xa": "Hàng Gòn", "pgd": "PGD Long Khánh", "ngay_gd": "6", "gio_gd": "8h30-10h30", "dia_diem": "Trung tập văn hóa thể thao - học tập công đồng"},
    {"stt": 57, "ma_dgd": "TXN0462902", "ten": "Phú Bình 2", "xa": "Long Khánh", "pgd": "PGD Long Khánh", "ngay_gd": "7", "gio_gd": "8h30-10h00", "dia_diem": "Trụ sở Nhà VH khu phố 2 Phú Bình cũ"},
    {"stt": 58, "ma_dgd": "TXN0460906", "ten": "Suối Tre", "xa": "Bình Lộc", "pgd": "PGD Long Khánh", "ngay_gd": "9", "gio_gd": "8h30-10h30", "dia_diem": "Nhà VH khu phố Suối Tre"},
    {"stt": 59, "ma_dgd": "TXN0462904", "ten": "Xuân Bình", "xa": "Long Khánh", "pgd": "PGD Long Khánh", "ngay_gd": "10", "gio_gd": "8h30-10h00", "dia_diem": "Trụ sở Nhà VH khu phố 5 Xuân Bình cũ"},
    {"stt": 60, "ma_dgd": "TXN0468001", "ten": "Xuân Lập", "xa": "Xuân Lập", "pgd": "PGD Long Khánh", "ngay_gd": "11", "gio_gd": "8h30-10h30", "dia_diem": "Ban chỉ huy quân sự phường Xuân Lập"},
    {"stt": 61, "ma_dgd": "TXN0461502", "ten": "Bảo Vinh", "xa": "Bảo Vinh", "pgd": "PGD Long Khánh", "ngay_gd": "12", "gio_gd": "8h30-10h30", "dia_diem": "Nhà VH khu Bảo Vinh B"},
    {"stt": 62, "ma_dgd": "TXN0468002", "ten": "Xuân Lập 2", "xa": "Xuân Lập", "pgd": "PGD Long Khánh", "ngay_gd": "14", "gio_gd": "8h30-10h30", "dia_diem": "Nhà VH ấp Trung Tâm"},
    {"stt": 63, "ma_dgd": "TXN0461501", "ten": "Bảo Quang", "xa": "Bảo Vinh", "pgd": "PGD Long Khánh", "ngay_gd": "15", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm HTCĐ Bảo Quang"},
    {"stt": 64, "ma_dgd": "TXN0462905", "ten": "Xuân Hòa 3", "xa": "Long Khánh", "pgd": "PGD Long Khánh", "ngay_gd": "16", "gio_gd": "8h30-10h00", "dia_diem": "Trụ sở Nhà VH khu phố 4 Xuân Hòa cũ"},
    {"stt": 65, "ma_dgd": "TXN0462903", "ten": "Long Khánh", "xa": "Long Khánh", "pgd": "PGD Long Khánh", "ngay_gd": "17", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBMTTQ thành phố Long Khánh cũ"},
    {"stt": 66, "ma_dgd": "TXN0460904", "ten": "Bình lộc", "xa": "Bình Lộc", "pgd": "PGD Long Khánh", "ngay_gd": "18", "gio_gd": "8h30-10h30", "dia_diem": "Nhà VH ấp 1 Bình lộc"},
    {"stt": 67, "ma_dgd": "TXN0462901", "ten": "Bàu Trâm", "xa": "Long Khánh", "pgd": "PGD Long Khánh", "ngay_gd": "19", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở Nhà VH ấp Bàu Trâm cũ"},
    {"stt": 68, "ma_dgd": "TXN0462101", "ten": "Hàng Gòn", "xa": "Hàng Gòn", "pgd": "PGD Long Khánh", "ngay_gd": "21", "gio_gd": "8h30-10h30", "dia_diem": "Nhà VH ấp Hàng Gòn"},
    {"stt": 69, "ma_dgd": "TXN0460913", "ten": "Xuân Thiện", "xa": "Bình Lộc", "pgd": "PGD Long Khánh", "ngay_gd": "22", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm học tập công đồng"},
    {"stt": 70, "ma_dgd": "TXN0468101", "ten": "Xuân Hiệp", "xa": "Xuân Lộc", "pgd": "PGD Xuân Lộc", "ngay_gd": "5", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp Tân Tiến"},
    {"stt": 71, "ma_dgd": "TXN0468703", "ten": "Bảo Hòa", "xa": "Xuân Định", "pgd": "PGD Xuân Lộc", "ngay_gd": "6", "gio_gd": "08h30-10h30", "dia_diem": "Hội trường Đảng ủy xã"},
    {"stt": 72, "ma_dgd": "TXN0468701", "ten": "Xuân Định", "xa": "Xuân Định", "pgd": "PGD Xuân Lộc", "ngay_gd": "7", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp Bảo Định xã"},
    {"stt": 73, "ma_dgd": "TXN0468103", "ten": "Xuân Thọ", "xa": "Xuân Lộc", "pgd": "PGD Xuân Lộc", "ngay_gd": "9", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp Thọ Lộc"},
    {"stt": 74, "ma_dgd": "TXN0468201", "ten": "Xuân Phú", "xa": "Xuân Phú", "pgd": "PGD Xuân Lộc", "ngay_gd": "10", "gio_gd": "08h30-10h30", "dia_diem": "Hội trường UBND xã"},
    {"stt": 75, "ma_dgd": "TXN0467801", "ten": "Suối Nho", "xa": "Xuân Bắc", "pgd": "PGD Xuân Lộc", "ngay_gd": "11", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm VH học tập công đồng xã Xuân Bắc"},
    {"stt": 76, "ma_dgd": "TXN0467901", "ten": "Xuân Hòa", "xa": "Xuân Hòa", "pgd": "PGD Xuân Lộc", "ngay_gd": "12", "gio_gd": "08h30-10h30", "dia_diem": "Hội trường UBND xã"},
    {"stt": 77, "ma_dgd": "TXN0468702", "ten": "Xuân Bảo", "xa": "Xuân Định", "pgd": "PGD Xuân Lộc", "ngay_gd": "13", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm HTCĐ xã"},
    {"stt": 78, "ma_dgd": "TXN0467902", "ten": "Xuân Tâm", "xa": "Xuân Hòa", "pgd": "PGD Xuân Lộc", "ngay_gd": "14", "gio_gd": "08h30-10h30", "dia_diem": "Trung tảm dich̀ vụ tổng hợp xã"},
    {"stt": 79, "ma_dgd": "TXN0467802", "ten": "Xuân Bắc", "xa": "Xuân Bắc", "pgd": "PGD Xuân Lộc", "ngay_gd": "15", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp 2B xã Xuân Bắc, tỉnh Đồng Nai"},
    {"stt": 80, "ma_dgd": "TXN0468402", "ten": "Suối Cao", "xa": "Xuân Thành", "pgd": "PGD Xuân Lộc", "ngay_gd": "16", "gio_gd": "08h30-10h30", "dia_diem": "Hội trường Đảng ủy xã"},
    {"stt": 81, "ma_dgd": "TXN0467903", "ten": "Xuân Hòa 2", "xa": "Xuân Hòa", "pgd": "PGD Xuân Lộc", "ngay_gd": "17", "gio_gd": "08h30-10h30", "dia_diem": "Trung tâm VH học tập công đồng xã Xuân Hòa"},
    {"stt": 82, "ma_dgd": "TXN0468102", "ten": "Xuân Trường", "xa": "Xuân Lộc", "pgd": "PGD Xuân Lộc", "ngay_gd": "18", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp Trung Hưng"},
    {"stt": 83, "ma_dgd": "TXN0468104", "ten": "Xuân Lộc", "xa": "Xuân Lộc", "pgd": "PGD Xuân Lộc", "ngay_gd": "19", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp Gia Ray 5"},
    {"stt": 84, "ma_dgd": "TXN0468105", "ten": "Suối Cát", "xa": "Xuân Lộc", "pgd": "PGD Xuân Lộc", "ngay_gd": "21", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp Việt Kiều 2"},
    {"stt": 85, "ma_dgd": "TXN0468401", "ten": "Xuân Thành", "xa": "Xuân Thành", "pgd": "PGD Xuân Lộc", "ngay_gd": "22", "gio_gd": "08h30-10h30", "dia_diem": "Nhà VH ấp Tân Hợp, xã"},
    {"stt": 86, "ma_dgd": "TXN0468202", "ten": "Lang Minh", "xa": "Xuân Phú", "pgd": "PGD Xuân Lộc", "ngay_gd": "23", "gio_gd": "08h30-10h30", "dia_diem": "Hội trường Đảng ủy xã"},
    {"stt": 87, "ma_dgd": "TXN0464402", "ten": "Phú Lợi", "xa": "Phú Hòa", "pgd": "PGD Định Quán", "ngay_gd": "7", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm VHTT-HTCĐ xã Phú Lợi Cũ"},
    {"stt": 88, "ma_dgd": "TXN0469203", "ten": "Ngọc Định", "xa": "Định Quán", "pgd": "PGD Định Quán", "ngay_gd": "9", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa ấp Phú Ngọc 4"},
    {"stt": 89, "ma_dgd": "TXN0462501", "ten": "La Ngà", "xa": "La Ngà", "pgd": "PGD Định Quán", "ngay_gd": "10", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm VH thể thao và HTCĐ xã La Ngà"},
    {"stt": 90, "ma_dgd": "TXN0469202", "ten": "Định Quán", "xa": "Định Quán", "pgd": "PGD Định Quán", "ngay_gd": "11", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 91, "ma_dgd": "TXN0464403", "ten": "Phú Điền", "xa": "Phú Hòa", "pgd": "PGD Định Quán", "ngay_gd": "12", "gio_gd": "9h00-11h00", "dia_diem": "Nhà Văn hóa ấp Phú Điền 3"},
    {"stt": 92, "ma_dgd": "TXN0469204", "ten": "Phú Ngọc", "xa": "Định Quán", "pgd": "PGD Định Quán", "ngay_gd": "13", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa ấp Phú Ngọc 3"},
    {"stt": 93, "ma_dgd": "TXN0466001", "ten": "Thanh Sơn", "xa": "Thanh Sơn", "pgd": "PGD Định Quán", "ngay_gd": "15", "gio_gd": "9h00-11h30", "dia_diem": "Trung tâm VHTT-HTCĐ xã Thanh Sơn"},
    {"stt": 94, "ma_dgd": "TXN0462502", "ten": "Túc Trưng", "xa": "La Ngà", "pgd": "PGD Định Quán", "ngay_gd": "17", "gio_gd": "9h00-11h00", "dia_diem": "Nhà VH ấp Đồn Điền 1"},
    {"stt": 95, "ma_dgd": "TXN0465002", "ten": "Phú Vinh", "xa": "Phú Vinh", "pgd": "PGD Định Quán", "ngay_gd": "18", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa ấp Phú Vinh 2"},
    {"stt": 96, "ma_dgd": "TXN0464401", "ten": "Phú Hòa", "xa": "Phú Hòa", "pgd": "PGD Định Quán", "ngay_gd": "19", "gio_gd": "8h30-10h30", "dia_diem": "Nhà VH ấp 2 xã Phú Hòa Cũ"},
    {"stt": 97, "ma_dgd": "TXN0465001", "ten": "Phú Tân", "xa": "Phú Vinh", "pgd": "PGD Định Quán", "ngay_gd": "21", "gio_gd": "8h30-10h30", "dia_diem": "Nhà Văn hóa ấp 1"},
    {"stt": 98, "ma_dgd": "TXN0469201", "ten": "Gia Canh", "xa": "Định Quán", "pgd": "PGD Định Quán", "ngay_gd": "22", "gio_gd": "8h30-11h00", "dia_diem": "Nhà văn hóa ấp Gia Canh 3"},
    {"stt": 99, "ma_dgd": "TXN0467001", "ten": "Tân An", "xa": "Tân An", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "5", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 100, "ma_dgd": "TXN0464601", "ten": "Phú Lý", "xa": "Phú Lý", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "7", "gio_gd": "09h-11h", "dia_diem": "Trung tâm VH thể thao HTCĐ xã Phú Lý"},
    {"stt": 101, "ma_dgd": "TXN0467701", "ten": "Tân Phong", "xa": "Tân Triều", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "10", "gio_gd": "9h00-11h00", "dia_diem": "Nhà VH Khu phố 3 phường tân triều (phường Tân Phong cũ)"},
    {"stt": 102, "ma_dgd": "TXN0467002", "ten": "Vĩnh Tân", "xa": "Tân An", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "11", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở Công An xã Tân An"},
    {"stt": 103, "ma_dgd": "TXN0466802", "ten": "Trị An 2", "xa": "Trị An", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "13", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 104, "ma_dgd": "TXN0467703", "ten": "Bình Lợi", "xa": "Tân Triều", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "15", "gio_gd": "09h-11h", "dia_diem": "Nhà Văn hóa khu phố Võ Sa phường Tân triều"},
    {"stt": 105, "ma_dgd": "TXN0466803", "ten": "Mã Đà", "xa": "Trị An", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "17", "gio_gd": "08h30-11h", "dia_diem": "Nhà VH ấp 1 Mã Đà xã Trị An"},
    {"stt": 106, "ma_dgd": "TXN0466801", "ten": "Trị An", "xa": "Trị An", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "19", "gio_gd": "08h-11h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 107, "ten": "Tân Bình 2", "xa": "Tân Triều", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "21", "gio_gd": "09h-11h", "dia_diem": "Trung tâm VH HTCĐ Tân Bình, phường Tân Triều"},
    {"stt": 108, "ma_dgd": "TXN0467702", "ten": "Tân Triều", "xa": "Tân Triều", "pgd": "PGD Vĩnh Cửu", "ngay_gd": "23", "gio_gd": "09h-11h", "dia_diem": "Trung tâm VH HTCĐ Thạnh Phú, phường Tân Triều"},
    {"stt": 109, "ma_dgd": "TXN0464501", "ten": "Phú Lâm 2", "xa": "Phú Lâm", "pgd": "PGD Tân Phú", "ngay_gd": "5", "gio_gd": "09h-11h", "dia_diem": "Nhà văn hóa ấp Phương Mai"},
    {"stt": 110, "ma_dgd": "TXN0464502", "ten": "Thanh Sơn 2", "xa": "Phú Lâm", "pgd": "PGD Tân Phú", "ngay_gd": "6", "gio_gd": "09h-11h", "dia_diem": "Nhà văn hóa ấp Đa Tôn, xã Phú Lâm"},
    {"stt": 111, "ma_dgd": "TXN0464503", "ten": "Phú Lâm", "xa": "Phú Lâm", "pgd": "PGD Tân Phú", "ngay_gd": "7", "gio_gd": "09h-11h", "dia_diem": "Nhà văn hóa ấp Phú Dũng, xã Phú Lâm"},
    {"stt": 112, "ma_dgd": "TXN0464002", "ten": "Nam Cát Tiên", "xa": "Nam Cát Tiên", "pgd": "PGD Tân Phú", "ngay_gd": "10", "gio_gd": "09h-11h00", "dia_diem": "Nhà văn hóa xã Nam Cát tiên"},
    {"stt": 113, "ma_dgd": "TXN0466901", "ten": "Tà Lài 2", "xa": "Tà Lài", "pgd": "PGD Tân Phú", "ngay_gd": "12", "gio_gd": "09h-11h00", "dia_diem": "Nhà VH dân tộc ấp 4 xã Tà Lài"},
    {"stt": 114, "ma_dgd": "TXN0466902", "ten": "Tà Lài", "xa": "Tà Lài", "pgd": "PGD Tân Phú", "ngay_gd": "13", "gio_gd": "09h-11h", "dia_diem": "Nhà văn hóa ấp Phú Lập 5 xã Tà Lài"},
    {"stt": 115, "ma_dgd": "TXN0467403", "ten": "Phú Thanh", "xa": "Tân Phú", "pgd": "PGD Tân Phú", "ngay_gd": "14", "gio_gd": "09h-11h", "dia_diem": "Nhà văn hóa ấp Ngọc Lâm 5, xã Tân Phú"},
    {"stt": 116, "ma_dgd": "TXN0467404", "ten": "Phú Xuân", "xa": "Tân Phú", "pgd": "PGD Tân Phú", "ngay_gd": "15", "gio_gd": "09h-11h", "dia_diem": "Trung Tâm văn hoá xã Phú Xuân cũ"},
    {"stt": 117, "ma_dgd": "TXN0464001", "ten": "Phú An", "xa": "Nam Cát Tiên", "pgd": "PGD Tân Phú", "ngay_gd": "16", "gio_gd": "09h-11h00", "dia_diem": "Nhà VH Ấp 2, xã Nam Cát Tiên (xã Phú An cũ)"},
    {"stt": 118, "ten": "Phú Sơn 2", "xa": "Phú Lâm", "pgd": "PGD Tân Phú", "ngay_gd": "17", "gio_gd": "09h-11h", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 119, "ma_dgd": "TXN0466903", "ten": "Phú Thịnh", "xa": "Tà Lài", "pgd": "PGD Tân Phú", "ngay_gd": "18", "gio_gd": "09h-11h", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 120, "ma_dgd": "TXN0467405", "ten": "Phú Lộc", "xa": "Tân Phú", "pgd": "PGD Tân Phú", "ngay_gd": "19", "gio_gd": "09h-11h", "dia_diem": "Nhà VH ấp 2, xã Tân Phú ( xã Phú Lộc cũ)"},
    {"stt": 121, "ma_dgd": "TXN0467402", "ten": "Trà Cổ", "xa": "Tân Phú", "pgd": "PGD Tân Phú", "ngay_gd": "21", "gio_gd": "09h-11h", "dia_diem": "Nhà VH ấp 5, xã Tân Phú (xã Trà Cổ cũ)"},
    {"stt": 122, "ten": "Đak Lua", "xa": "Dak Lua", "pgd": "PGD Tân Phú", "ngay_gd": "22", "gio_gd": "9h30-11h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 123, "ma_dgd": "TXN0467401", "ten": "Tân Phú", "xa": "Tân Phú", "pgd": "PGD Tân Phú", "ngay_gd": "23", "gio_gd": "09h-11h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 124, "ten": "Gia Kiệm 1", "xa": "Gia Kiệm", "pgd": "PGD Thống Nhất", "ngay_gd": "5", "gio_gd": "8h30-11h00", "dia_diem": "Văn phòng ấp Đông Bắc"},
    {"stt": 125, "ma_dgd": "TXN0461902", "ten": "Hưng Lộc", "xa": "Dầu Giây", "pgd": "PGD Thống Nhất", "ngay_gd": "6", "gio_gd": "8h30-11h00", "dia_diem": "Văn phòng ấp Hưng Nghĩa"},
    {"stt": 126, "ma_dgd": "TXN0466402", "ten": "Phú Cường", "xa": "Thống Nhất", "pgd": "PGD Thống Nhất", "ngay_gd": "7", "gio_gd": "8h30-10h30", "dia_diem": "Trung tâm học tập cộng đồng Phú Cường cũ"},
    {"stt": 127, "ten": "Gia Kiệm 2", "xa": "Gia Kiệm", "pgd": "PGD Thống Nhất", "ngay_gd": "9", "gio_gd": "8h30-11h00", "dia_diem": "Văn phòng ấp Tân Yên"},
    {"stt": 128, "ma_dgd": "TXN0466404", "ten": "Thống Nhất", "xa": "Thống Nhất", "pgd": "PGD Thống Nhất", "ngay_gd": "11", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 129, "ten": "Gia Kiệm 3", "xa": "Gia Kiệm", "pgd": "PGD Thống Nhất", "ngay_gd": "12", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 130, "ma_dgd": "TXN0466403", "ten": "Gia Tân 1", "xa": "Thống Nhất", "pgd": "PGD Thống Nhất", "ngay_gd": "14", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 131, "ma_dgd": "TXN0466401", "ten": "Phú Túc", "xa": "Thống Nhất", "pgd": "PGD Thống Nhất", "ngay_gd": "16", "gio_gd": "8h30-10h30", "dia_diem": "Nhà văn hóa ấp Cây Xăng"},
    {"stt": 132, "ma_dgd": "TXN0461904", "ten": "Lộ 25", "xa": "Dầu Giây", "pgd": "PGD Thống Nhất", "ngay_gd": "17", "gio_gd": "8h30-11h00", "dia_diem": "Văn phòng ấp 2 xã Dầu Giây"},
    {"stt": 133, "ma_dgd": "TXN0461901", "ten": "Dầu Giây", "xa": "Dầu Giây", "pgd": "PGD Thống Nhất", "ngay_gd": "18", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 134, "ma_dgd": "TXN0461903", "ten": "Bàu Hàm 2", "xa": "Dầu Giây", "pgd": "PGD Thống Nhất", "ngay_gd": "22", "gio_gd": "8h30-11h00", "dia_diem": "Văn phòng ấp Trần Cao Vân"},
    {"stt": 135, "ma_dgd": "TXN0465702", "ten": "LÂM SAN", "xa": "Sông Ray", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "5", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 136, "ma_dgd": "TXN0461704", "ten": "Cẩm Mỹ", "xa": "Cẩm Mỹ", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "6", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở ấp Suối Râm"},
    {"stt": 137, "ma_dgd": "TXN0468302", "ten": "Xuân Quế", "xa": "Xuân Quế", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "7", "gio_gd": "08h30-11h", "dia_diem": "Nhà văn hóa ấp 4, xã Xuân Quế"},
    {"stt": 138, "ma_dgd": "TXN0468601", "ten": "XUÂN ĐƯỜNG 2", "xa": "Xuân Đường", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "10", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở ấp Xuân Đường, xã Xuân Đường"},
    {"stt": 139, "ma_dgd": "TXN0461703", "ten": "NHÂN NGHĨA", "xa": "Cẩm Mỹ", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "11", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở ấp Tân Lập"},
    {"stt": 140, "ma_dgd": "TXN0468502", "ten": "XUÂN ĐÔNG", "xa": "Xuân Đông", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "12", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở ấp Cọ Dầu 2, xã Xuân Đông"},
    {"stt": 141, "ma_dgd": "TXN0461702", "ten": "BẢO BÌNH", "xa": "Cẩm Mỹ", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "14", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở ấp Tân Xuân, xã Cẩm Mỹ"},
    {"stt": 142, "ma_dgd": "TXN0468602", "ten": "CẨM ĐƯỜNG", "xa": "Xuân Đường", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "15", "gio_gd": "8h30-11h00", "dia_diem": "NHÀ VĂN HÓA THỂ THAO VÀ HỌC TẬP CỘNG ĐỒNG ẤP CẨM ĐƯỜNG, XÃ XUÂN ĐƯỜNG"},
    {"stt": 143, "ma_dgd": "TXN0468501", "ten": "XUÂN TÂY", "xa": "Xuân Đông", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "16", "gio_gd": "08h30-11h", "dia_diem": "Trụ sợ Ấp 4, xã Xuân Đông"},
    {"stt": 144, "ma_dgd": "TXN0468603", "ten": "Xuân Đường", "xa": "Xuân Đường", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "17", "gio_gd": "8h30-11h00", "dia_diem": "NHÀ VĂN HÓA THỂ THAO VÀ HỌC TẬP CỘNG ĐỒNG ẤP CẨM ĐƯỜNG, XÃ XUÂN ĐƯỜNG"},
    {"stt": 145, "ma_dgd": "TXN0468301", "ten": "XUÂN QUẾ 2", "xa": "Xuân Quế", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "18", "gio_gd": "08h30-11h", "dia_diem": "Trung tâm VH HTCĐ xã Xuân Quế cũ"},
    {"stt": 146, "ma_dgd": "TXN0465701", "ten": "SÔNG RAY", "xa": "Sông Ray", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "19", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 147, "ma_dgd": "TXN0461701", "ten": "XUÂN MỸ", "xa": "Cẩm Mỹ", "pgd": "PGD Cẩm Mỹ", "ngay_gd": "22", "gio_gd": "08h30-11h", "dia_diem": "Trụ sở ấp Láng Lớn"},
    {"stt": 148, "ma_dgd": "TXN0464304", "ten": "Thị trấn Hiệp Phước", "xa": "Nhơn Trạch", "pgd": "PGD Nhơn Trạch", "ngay_gd": "7", "gio_gd": "8h30-11h00", "dia_diem": "Trung tâm VH thể thao HTCĐ khu phố Mỹ khoan (Trụ sở trung tâm HTCĐ khu phố mỹ khoan, thị trấn Hiệp Phước cũ)"},
    {"stt": 149, "ma_dgd": "TXN0464302", "ten": "Nhơn Trạch", "xa": "Nhơn Trạch", "pgd": "PGD Nhơn Trạch", "ngay_gd": "9", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở HĐND-UBND xã Nhơn Trạch (trụ sở UBND huyện cũ)"},
    {"stt": 150, "ma_dgd": "TXN0464303", "ten": "Phước Thiền", "xa": "Nhơn Trạch", "pgd": "PGD Nhơn Trạch", "ngay_gd": "10", "gio_gd": "8h30-11h00", "dia_diem": "Nhà VH ấp Bến sắn (Trụ sở Nhà VH ấp Bến sắn, xã Phước Thiền cũ)"},
    {"stt": 151, "ma_dgd": "TXN0469101", "ten": "Phước Khánh", "xa": "Đại Phước", "pgd": "PGD Nhơn Trạch", "ngay_gd": "11", "gio_gd": "8h30-11h30", "dia_diem": "Nhà VH ấp 2 (Trụ sở Nhà VH ấp 2, xã Phước Khánh cũ)"},
    {"stt": 152, "ma_dgd": "TXN0465103", "ten": "Vĩnh Thanh", "xa": "Phước An", "pgd": "PGD Nhơn Trạch", "ngay_gd": "12", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở Quân sự xã (Trụ sở UBND xã Vĩnh Thanh củ)"},
    {"stt": 153, "ma_dgd": "TXN0464301", "ten": "Long Tân", "xa": "Nhơn Trạch", "pgd": "PGD Nhơn Trạch", "ngay_gd": "13", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở quân sự xã (Trụ sở UBND xã Long Tân cũ)"},
    {"stt": 154, "ma_dgd": "TXN0465402", "ten": "Phước An", "xa": "Phước An", "pgd": "PGD Nhơn Trạch", "ngay_gd": "14", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở Đảng ủy, UBND xã (Trụ sở xã Phước An củ)"},
    {"stt": 155, "ma_dgd": "TXN0465101", "ten": "Long Thọ", "xa": "Phước An", "pgd": "PGD Nhơn Trạch", "ngay_gd": "15", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở Công an xã (Trụ sở UBND xã Long Thọ củ)"},
    {"stt": 156, "ma_dgd": "TXN0469103", "ten": "Đại Phước", "xa": "Đại Phước", "pgd": "PGD Nhơn Trạch", "ngay_gd": "16", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở Đảng ủy-HĐND-UBND xã Đại Phước mới (trụ sở UBND xã Phú Đông cũ)"},
    {"stt": 157, "ma_dgd": "TXN0469104", "ten": "Đại Phước 2", "xa": "Đại Phước", "pgd": "PGD Nhơn Trạch", "ngay_gd": "17", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở Ủy ban MTTQVN và các TCCTXH xã (trụ sở UBND xã Đại Phước cũ)"},
    {"stt": 158, "ma_dgd": "TXN0469102", "ten": "Phú Hữu", "xa": "Đại Phước", "pgd": "PGD Nhơn Trạch", "ngay_gd": "18", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở công an xã Đại Phước (trụ sở UBND xã Phú Hữu cũ)"},
    {"stt": 159, "ma_dgd": "TXN0464305", "ten": "Phú Thạnh", "xa": "Nhơn Trạch", "pgd": "PGD Nhơn Trạch", "ngay_gd": "19", "gio_gd": "8h30-11h00", "dia_diem": "Nhà VH ấp 1 (Trụ sở Nhà VH ấp 1, xã Phú Thạnh cũ)"},
    {"stt": 160, "ma_dgd": "TXN0460118", "ten": "Thanh Phú", "xa": "An Lộc", "pgd": "PGD Bình Long", "ngay_gd": "6", "gio_gd": "8h-9h30", "dia_diem": "Nhà văn hóa khu phố Phú Xuân, phường An Lộc"},
    {"stt": 161, "ma_dgd": "TXN0460809", "ten": "Phú Đức", "xa": "Bình Long", "pgd": "PGD Bình Long", "ngay_gd": "7", "gio_gd": "8h-9h30", "dia_diem": "Nhà Văn hòa khu phố Phú Nghĩa"},
    {"stt": 162, "ma_dgd": "TXN0460814", "ten": "Bình Long", "xa": "Bình Long", "pgd": "PGD Bình Long", "ngay_gd": "10", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 163, "ma_dgd": "TXN0460107", "ten": "Thanh Lương", "xa": "An Lộc", "pgd": "PGD Bình Long", "ngay_gd": "12", "gio_gd": "08h-12h", "dia_diem": "Nhà Văn hóa khu phố Thanh Hòa"},
    {"stt": 164, "ma_dgd": "TXN0460803", "ten": "Hưng Chiến", "xa": "Bình Long", "pgd": "PGD Bình Long", "ngay_gd": "14", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 165, "ma_dgd": "TXN0460112", "ten": "An Lộc", "xa": "An Lộc", "pgd": "PGD Bình Long", "ngay_gd": "16", "gio_gd": "08h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 166, "ma_dgd": "TXN0460819", "ten": "Thanh Bình", "xa": "Bình Long", "pgd": "PGD Bình Long", "ngay_gd": "21", "gio_gd": "08h00-10h30", "dia_diem": "Nhà văn hòa khu phố Chà Là"},
    {"stt": 167, "ma_dgd": "TXN0463601", "ten": "Lộc Hoà", "xa": "Lộc Thạnh", "pgd": "PGD Lộc Ninh", "ngay_gd": "5", "gio_gd": "8h-10h", "dia_diem": "Hội trường ấp 8A"},
    {"stt": 168, "ma_dgd": "TXN0463602", "ten": "Lộc thạnh", "xa": "Lộc Thạnh", "pgd": "PGD Lộc Ninh", "ngay_gd": "7", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 169, "ma_dgd": "TXN0463401", "ten": "Lộc Hiệp", "xa": "Lộc Quang", "pgd": "PGD Lộc Ninh", "ngay_gd": "9", "gio_gd": "8h-10h", "dia_diem": "Ban chỉ huy quân sự xã Lộc Quang"},
    {"stt": 170, "ma_dgd": "TXN0463403", "ten": "Lộc quang", "xa": "Lộc Quang", "pgd": "PGD Lộc Ninh", "ngay_gd": "10", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 171, "ma_dgd": "TXN0463303", "ten": "Lộc Thuận", "xa": "Lộc Ninh", "pgd": "PGD Lộc Ninh", "ngay_gd": "11", "gio_gd": "8h-10h", "dia_diem": "Hội trường Thôn Lộc Thuận 6"},
    {"stt": 172, "ma_dgd": "TXN0463402", "ten": "Bồn Xăng", "xa": "Lộc Quang", "pgd": "PGD Lộc Ninh", "ngay_gd": "12", "gio_gd": "8h-10h", "dia_diem": "Công An xã Lộc Quang"},
    {"stt": 173, "ma_dgd": "TXN0463201", "ten": "Lộc Điền", "xa": "Lộc Hưng", "pgd": "PGD Lộc Ninh", "ngay_gd": "13", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 174, "ma_dgd": "TXN0463202", "ten": "Lộc Khánh", "xa": "Lộc Hưng", "pgd": "PGD Lộc Ninh", "ngay_gd": "14", "gio_gd": "8h-10h", "dia_diem": "Nhà văn hoá ấp Quyết Thành"},
    {"stt": 175, "ma_dgd": "TXN0463502", "ten": "Lộc Thịnh", "xa": "Lộc Thành", "pgd": "PGD Lộc Ninh", "ngay_gd": "15", "gio_gd": "8h-10h", "dia_diem": "Ban chỉ huy quân sự xã Lộc Thành"},
    {"stt": 176, "ma_dgd": "TXN0463203", "ten": "Lộc Hưng", "xa": "Lộc Hưng", "pgd": "PGD Lộc Ninh", "ngay_gd": "16", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 177, "ma_dgd": "TXN0463302", "ten": "Lộc Thái", "xa": "Lộc Ninh", "pgd": "PGD Lộc Ninh", "ngay_gd": "17", "gio_gd": "8h-10h", "dia_diem": "Hội trường Thôn Lộc Thái 5"},
    {"stt": 178, "ma_dgd": "TXN0463501", "ten": "Lộc Thành", "xa": "Lộc Thành", "pgd": "PGD Lộc Ninh", "ngay_gd": "18", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 179, "ma_dgd": "TXN0463702", "ten": "Lộc Thiện", "xa": "Lộc Tấn", "pgd": "PGD Lộc Ninh", "ngay_gd": "19", "gio_gd": "8h-10h", "dia_diem": "Hội trường ấp 1"},
    {"stt": 180, "ma_dgd": "TXN0463701", "ten": "Lộc Tấn", "xa": "Lộc Tấn", "pgd": "PGD Lộc Ninh", "ngay_gd": "21", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 181, "ma_dgd": "TXN0463301", "ten": "Lộc ninh", "xa": "Lộc Ninh", "pgd": "PGD Lộc Ninh", "ngay_gd": "22", "gio_gd": "8h-10h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 182, "ma_dgd": "TXN0469501", "ten": "Đồng Xoài", "xa": "Đồng Xoài", "pgd": "PGD Bình Phước", "ngay_gd": "6", "gio_gd": "08h00-11h00", "dia_diem": "Hội trường lầu 1 Trung tâm Phục vụ Hành chính công phường Đồng Xoài"},
    {"stt": 183, "ma_dgd": "TXN0461113", "ten": "Bình Phước", "xa": "Bình Phước", "pgd": "PGD Bình Phước", "ngay_gd": "9", "gio_gd": "8h-10h", "dia_diem": "Hội trường UBMTTQVN phường mới"},
    {"stt": 184, "ma_dgd": "TXN0461116", "ten": "Tân Xuân", "xa": "Bình Phước", "pgd": "PGD Bình Phước", "ngay_gd": "10", "gio_gd": "8h-10h", "dia_diem": "Nhà VH khu phố Tân Trà"},
    {"stt": 185, "ma_dgd": "TXN0461117", "ten": "Tân Thiện", "xa": "Bình Phước", "pgd": "PGD Bình Phước", "ngay_gd": "12", "gio_gd": "8h-10h", "dia_diem": "Nhà VH khu phố Bình Thiện"},
    {"stt": 186, "ma_dgd": "TXN0461118", "ten": "Tiến Hưng", "xa": "Bình Phước", "pgd": "PGD Bình Phước", "ngay_gd": "14", "gio_gd": "8h00-11h00", "dia_diem": "Nhà VH khu phố Tiến Hưng 1"},
    {"stt": 187, "ma_dgd": "TXN0469502", "ten": "Tân Thành", "xa": "Đồng Xoài", "pgd": "PGD Bình Phước", "ngay_gd": "16", "gio_gd": "8h00-11h30", "dia_diem": "Nhà VH khu phố Tân Thành 6"},
    {"stt": 188, "ma_dgd": "TXN0461114", "ten": "Tân Đồng", "xa": "Bình Phước", "pgd": "PGD Bình Phước", "ngay_gd": "18", "gio_gd": "8h-10h", "dia_diem": "Nhà văn hoá KP Tân Đồng 1"},
    {"stt": 189, "ma_dgd": "TXN0461115", "ten": "Tân Bình", "xa": "Bình Phước", "pgd": "PGD Bình Phước", "ngay_gd": "21", "gio_gd": "8h00-10h00", "dia_diem": "Nhà VH khu phố Thanh Bình"},
    {"stt": 190, "ma_dgd": "TXN0465202", "ten": "Bình sơn", "xa": "Phước Bình", "pgd": "PGD Phước Long", "ngay_gd": "6", "gio_gd": "8h00-9h30", "dia_diem": "Hội trường Khu phố Bình Điền, phường Phước Bình"},
    {"stt": 191, "ma_dgd": "TXN0465203", "ten": "Phước Bình", "xa": "Phước Bình", "pgd": "PGD Phước Long", "ngay_gd": "7", "gio_gd": "8h-9h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 192, "ma_dgd": "TXN0465303", "ten": "Phước Tín", "xa": "Phước Long", "pgd": "PGD Phước Long", "ngay_gd": "9", "gio_gd": "8h00-9h30", "dia_diem": "Hội trường Khu phố Phước Yên, phường Phước Long"},
    {"stt": 193, "ma_dgd": "TXN0465302", "ten": "Sơn Giang", "xa": "Phước Long", "pgd": "PGD Phước Long", "ngay_gd": "10", "gio_gd": "8h-9h30", "dia_diem": "Nhà văn hoá khu phố Bình Giang 2"},
    {"stt": 194, "ma_dgd": "TXN0465201", "ten": "Phước Vĩnh", "xa": "Phước Bình", "pgd": "PGD Phước Long", "ngay_gd": "12", "gio_gd": "8h-9h30", "dia_diem": "Hội trường Khu phố 2, phường Phước Bình"},
    {"stt": 195, "ma_dgd": "TXN0465304", "ten": "Phước Long", "xa": "Phước Long", "pgd": "PGD Phước Long", "ngay_gd": "14", "gio_gd": "8h-9h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 196, "ma_dgd": "TXN0465204", "ten": "Long Giang", "xa": "Phước Bình", "pgd": "PGD Phước Long", "ngay_gd": "16", "gio_gd": "8h00-9h30", "dia_diem": "Hội trường Khu phố Nhơn Hoà 1, phường Phước Bình"},
    {"stt": 197, "ma_dgd": "TXN0465301", "ten": "Thác Mơ", "xa": "Phước Long", "pgd": "PGD Phước Long", "ngay_gd": "18", "gio_gd": "8h-9h30", "dia_diem": "Hội trường Khu phố Thác Mơ 4"},
    {"stt": 198, "ten": "Bình Minh 2", "xa": "Bom Bo", "pgd": "PGD Bù Đăng", "ngay_gd": "5", "gio_gd": "8H30-11H", "dia_diem": "Nhà văn hóa Thôn 3 Bình Minh, xã Bom Bo"},
    {"stt": 199, "ma_dgd": "TXN0461402", "ten": "Minh Hưng 1", "xa": "Bù Đăng", "pgd": "PGD Bù Đăng", "ngay_gd": "6", "gio_gd": "8H30-11H", "dia_diem": "Nhà văn hóa Thôn Hưng Thịnh, xã Bù Đăng"},
    {"stt": 200, "ten": "Phước An 2", "xa": "Phước Sơn", "pgd": "PGD Bù Đăng", "ngay_gd": "7", "gio_gd": "8H30-11H", "dia_diem": "Nhà VH Thôn 2"},
    {"stt": 201, "ma_dgd": "TXN0468902", "ten": "Đường 10", "xa": "Đăk Nhau", "pgd": "PGD Bù Đăng", "ngay_gd": "9", "gio_gd": "8H30-11H", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 202, "ma_dgd": "TXN0464101", "ten": "Nghĩa Trung", "xa": "Nghĩa Trung", "pgd": "PGD Bù Đăng", "ngay_gd": "10", "gio_gd": "8H30-11H", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 203, "ma_dgd": "TXN0460513", "ten": "Bom Bo", "xa": "Bom Bo", "pgd": "PGD Bù Đăng", "ngay_gd": "11", "gio_gd": "8H30-11H", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 204, "ma_dgd": "TXN0465401", "ten": "Phước Sơn", "xa": "Phước Sơn", "pgd": "PGD Bù Đăng", "ngay_gd": "12", "gio_gd": "8H30-11H", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 205, "ma_dgd": "TXN0466303", "ten": "Phú Sơn", "xa": "Thọ Sơn", "pgd": "PGD Bù Đăng", "ngay_gd": "14", "gio_gd": "8H30-11H", "dia_diem": "Nhà văn hóa Thôn Sơn Phú, xã Thọ Sơn"},
    {"stt": 206, "ma_dgd": "TXN0464103", "ten": "Nghĩa Bình", "xa": "Nghĩa Trung", "pgd": "PGD Bù Đăng", "ngay_gd": "15", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 207, "ma_dgd": "TXN0465403", "ten": "Đăng Hà", "xa": "Phước Sơn", "pgd": "PGD Bù Đăng", "ngay_gd": "16", "gio_gd": "09h00 - 11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 208, "ma_dgd": "TXN0468901", "ten": "Đăk Nhau", "xa": "Đăk Nhau", "pgd": "PGD Bù Đăng", "ngay_gd": "17", "gio_gd": "8H30-11H", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 209, "ma_dgd": "TXN0461401", "ten": "Bù Đăng", "xa": "Bù Đăng", "pgd": "PGD Bù Đăng", "ngay_gd": "18", "gio_gd": "8H-10H", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 210, "ma_dgd": "TXN0466302", "ten": "Đồng Nai", "xa": "Thọ Sơn", "pgd": "PGD Bù Đăng", "ngay_gd": "19", "gio_gd": "8H30-11H", "dia_diem": "Nhà VH thôn 4"},
    {"stt": 211, "ma_dgd": "TXN0464102", "ten": "Nghĩa Thắng", "xa": "Nghĩa Trung", "pgd": "PGD Bù Đăng", "ngay_gd": "21", "gio_gd": "8H30-11H", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 212, "ma_dgd": "TXN0466301", "ten": "Thọ Sơn", "xa": "Thọ Sơn", "pgd": "PGD Bù Đăng", "ngay_gd": "22", "gio_gd": "8h30-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 213, "ma_dgd": "TXN0461403", "ten": "Đoàn Kết", "xa": "Bù Đăng", "pgd": "PGD Bù Đăng", "ngay_gd": "23", "gio_gd": "8H30-11H", "dia_diem": "Nhà văn hoá Thôn Vĩnh Hoà"},
    {"stt": 214, "ma_dgd": "TXN0467301", "ten": "Tân Hoà", "xa": "Tân Lợi", "pgd": "PGD Đồng Phú", "ngay_gd": "5", "gio_gd": "8h00-10h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 215, "ma_dgd": "TXN0469401", "ten": "Tân Phước", "xa": "Đồng Tâm", "pgd": "PGD Đồng Phú", "ngay_gd": "7", "gio_gd": "8h00-10h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 216, "ma_dgd": "TXN0469302", "ten": "Thái Dũng", "xa": "Đồng Phú", "pgd": "PGD Đồng Phú", "ngay_gd": "9", "gio_gd": "8h00-10h30", "dia_diem": "Nhà văn hóa thôn Tân Tiến, xã Đồng Phú"},
    {"stt": 217, "ma_dgd": "TXN0467302", "ten": "Suối Đôi", "xa": "Tân Lợi", "pgd": "PGD Đồng Phú", "ngay_gd": "11", "gio_gd": "8h00-10h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 218, "ma_dgd": "TXN0469402", "ten": "Đồng Tiến", "xa": "Đồng Tâm", "pgd": "PGD Đồng Phú", "ngay_gd": "13", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 219, "ma_dgd": "TXN0466201", "ten": "Thuận Hoà", "xa": "Thuận Lợi", "pgd": "PGD Đồng Phú", "ngay_gd": "15", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 220, "ma_dgd": "TXN0467303", "ten": "Tân Lợi", "xa": "Tân Lợi", "pgd": "PGD Đồng Phú", "ngay_gd": "17", "gio_gd": "8h00-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 221, "ma_dgd": "TXN0469303", "ten": "Tân Lập", "xa": "Đồng Phú", "pgd": "PGD Đồng Phú", "ngay_gd": "18", "gio_gd": "8h00-11h00", "dia_diem": "Nhà văn hóa Thôn 3, xã Đồng Phú"},
    {"stt": 222, "ma_dgd": "TXN0466202", "ten": "Thuận Lợi", "xa": "Thuận Lợi", "pgd": "PGD Đồng Phú", "ngay_gd": "19", "gio_gd": "8h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 223, "ma_dgd": "TXN0469403", "ten": "Đồng Tâm", "xa": "Đồng Tâm", "pgd": "PGD Đồng Phú", "ngay_gd": "21", "gio_gd": "8h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 224, "ma_dgd": "TXN0469301", "ten": "Đồng Phú", "xa": "Đồng Phú", "pgd": "PGD Đồng Phú", "ngay_gd": "23", "gio_gd": "8h00-10h00", "dia_diem": "Cơ quan Ủy ban mặt trận tổ quốc Việt Nam và các Đoàn thể xã Đồng Phú"},
    {"stt": 225, "ma_dgd": "TXN0463802", "ten": "Minh Long", "xa": "Minh Hưng", "pgd": "PGD Chơn Thành", "ngay_gd": "7", "gio_gd": "8h00-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 226, "ma_dgd": "TXN0461603", "ten": "Thành Tâm", "xa": "Chơn Thành", "pgd": "PGD Chơn Thành", "ngay_gd": "9", "gio_gd": "08h00-10h30", "dia_diem": "Nhà văn hóa Khu phố Thành Tâm 2"},
    {"stt": 227, "ma_dgd": "TXN0461602", "ten": "Minh Thành", "xa": "Chơn Thành", "pgd": "PGD Chơn Thành", "ngay_gd": "11", "gio_gd": "8h00-11h00", "dia_diem": "Nhà văn hóa khu phố Minh Thành 3"},
    {"stt": 228, "ma_dgd": "TXN0464201", "ten": "Minh Lập", "xa": "Nha Bích", "pgd": "PGD Chơn Thành", "ngay_gd": "13", "gio_gd": "8h00-11h00", "dia_diem": "Nhà VH ấp Minh Lập 6"},
    {"stt": 229, "ma_dgd": "TXN0463801", "ten": "Minh Hưng", "xa": "Minh Hưng", "pgd": "PGD Chơn Thành", "ngay_gd": "15", "gio_gd": "08h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 230, "ma_dgd": "TXN0461601", "ten": "Chơn Thành", "xa": "Chơn Thành", "pgd": "PGD Chơn Thành", "ngay_gd": "17", "gio_gd": "8h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 231, "ma_dgd": "TXN0464202", "ten": "Minh Thắng", "xa": "Nha Bích", "pgd": "PGD Chơn Thành", "ngay_gd": "19", "gio_gd": "8h00-10h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 232, "ma_dgd": "TXN0464203", "ten": "Nha Bích", "xa": "Nha Bích", "pgd": "PGD Chơn Thành", "ngay_gd": "22", "gio_gd": "08h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 233, "ma_dgd": "TXN0467602", "ten": "Tân Tiến", "xa": "Tân Tiến", "pgd": "PGD Bù Đốp", "ngay_gd": "6", "gio_gd": "8h30-11h30", "dia_diem": "Hội trường (UBND xã Tân Thành cũ)"},
    {"stt": 234, "ma_dgd": "TXN0466102", "ten": "Thanh Hòa", "xa": "Thiện Hưng", "pgd": "PGD Bù Đốp", "ngay_gd": "9", "gio_gd": "8h30-11h30", "dia_diem": "Nhà VH ấp 8"},
    {"stt": 235, "ma_dgd": "TXN0462202", "ten": "Phước Thiện", "xa": "Hưng Phước", "pgd": "PGD Bù Đốp", "ngay_gd": "10", "gio_gd": "8h30-11h", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 236, "ma_dgd": "TXN0466101", "ten": "Thiện Hưng", "xa": "Thiện Hưng", "pgd": "PGD Bù Đốp", "ngay_gd": "12", "gio_gd": "8h30-11h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 237, "ma_dgd": "TXN0467601", "ten": "Tân Nhân", "xa": "Tân Tiến", "pgd": "PGD Bù Đốp", "ngay_gd": "14", "gio_gd": "8h30-11h30", "dia_diem": "Hội trường (UBND xã Tân Tiến cũ)"},
    {"stt": 238, "ma_dgd": "TXN0466103", "ten": "Bù Đốp", "xa": "Thiện Hưng", "pgd": "PGD Bù Đốp", "ngay_gd": "16", "gio_gd": "8h30-11h30", "dia_diem": "Nhà Văn hóa Thôn 2"},
    {"stt": 239, "ma_dgd": "TXN0462201", "ten": "Hưng Phước", "xa": "Hưng Phước", "pgd": "PGD Bù Đốp", "ngay_gd": "18", "gio_gd": "8h30-11h", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 240, "ma_dgd": "TXN0467603", "ten": "Lộc An", "xa": "Tân Tiến", "pgd": "PGD Bù Đốp", "ngay_gd": "21", "gio_gd": "8h30-10h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 241, "ma_dgd": "TXN0468801", "ten": "Bình Thắng", "xa": "Đa Kia", "pgd": "PGD Bù Gia Mập", "ngay_gd": "7", "gio_gd": "8h00-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 242, "ma_dgd": "TXN0469001", "ten": "Đăk Ơ", "xa": "Đăk Ơ", "pgd": "PGD Bù Gia Mập", "ngay_gd": "9", "gio_gd": "08h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 243, "ma_dgd": "TXN0464701", "ten": "Đức Hạnh", "xa": "Phú Nghĩa", "pgd": "PGD Bù Gia Mập", "ngay_gd": "11", "gio_gd": "08h00-11h00", "dia_diem": "Hội trường thôn Bình Đức 2"},
    {"stt": 244, "ma_dgd": "TXN0464703", "ten": "Phú Văn", "xa": "Phú Nghĩa", "pgd": "PGD Bù Gia Mập", "ngay_gd": "13", "gio_gd": "08h00-11h00", "dia_diem": "Hội trường thôn 1"},
    {"stt": 245, "ma_dgd": "TXN0468803", "ten": "Phước Minh", "xa": "Đa Kia", "pgd": "PGD Bù Gia Mập", "ngay_gd": "15", "gio_gd": "08h00-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 246, "ma_dgd": "TXN0468802", "ten": "Đa Kia", "xa": "Đa Kia", "pgd": "PGD Bù Gia Mập", "ngay_gd": "17", "gio_gd": "8h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 247, "ma_dgd": "TXN0464702", "ten": "Phú Nghĩa", "xa": "Phú Nghĩa", "pgd": "PGD Bù Gia Mập", "ngay_gd": "19", "gio_gd": "08h00-11h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 248, "ma_dgd": "TXN0461301", "ten": "Bù Gia Mập", "xa": "Bù Gia Mập", "pgd": "PGD Bù Gia Mập", "ngay_gd": "21", "gio_gd": "08h00-11h00", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 249, "ma_dgd": "TXN0461203", "ten": "Phước Hòa", "xa": "Bình Tân", "pgd": "PGD Phú Riềng", "ngay_gd": "5", "gio_gd": "8h-10h30p", "dia_diem": "Hội trường thôn Phước Hoà - xã Bình Tân"},
    {"stt": 250, "ma_dgd": "TXN0462701", "ten": "Long Hà", "xa": "Long Hà", "pgd": "PGD Phú Riềng", "ngay_gd": "7", "gio_gd": "8h-10h30p", "dia_diem": "Trụ sở Trung tâm Dịch vụ tổng hợp xã Long Hà"},
    {"stt": 251, "ma_dgd": "TXN0464901", "ten": "Phú Trung", "xa": "Phú Trung", "pgd": "PGD Phú Riềng", "ngay_gd": "9", "gio_gd": "8h-10h30p", "dia_diem": "Trụ sở UBMTTQVN xã Phú Trung"},
    {"stt": 252, "ma_dgd": "TXN0464801", "ten": "Phú Riềng", "xa": "Phú Riềng", "pgd": "PGD Phú Riềng", "ngay_gd": "11", "gio_gd": "8h-10h30p", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 253, "ma_dgd": "TXN0462702", "ten": "Tân Long", "xa": "Long Hà", "pgd": "PGD Phú Riềng", "ngay_gd": "13", "gio_gd": "8h-10h30p", "dia_diem": "Hội trường thôn Long Tân 1 xã Long Hà"},
    {"stt": 254, "ten": "Phu Miêng", "xa": "Bình Tân", "pgd": "PGD Phú Riềng", "ngay_gd": "15", "gio_gd": "8h-10h30p", "dia_diem": "Công an xã Bình Tân"},
    {"stt": 255, "ma_dgd": "TXN0461201", "ten": "Bình Tân", "xa": "Bình Tân", "pgd": "PGD Phú Riềng", "ngay_gd": "17", "gio_gd": "8h-10h30p", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 256, "ten": "Phước Tân 2", "xa": "Phú Trung", "pgd": "PGD Phú Riềng", "ngay_gd": "19", "gio_gd": "8h-10h30p", "dia_diem": "Công an xã Phú Trung"},
    {"stt": 257, "ma_dgd": "TXN0464802", "ten": "Phú Hưng", "xa": "Phú Riềng", "pgd": "PGD Phú Riềng", "ngay_gd": "21", "gio_gd": "8h-10h30p", "dia_diem": "Hội trường thôn Phú Hưng"},
    {"stt": 258, "ma_dgd": "TXN0467203", "ten": "Tân Hiệp", "xa": "Tân Khai", "pgd": "PGD Hớn Quản", "ngay_gd": "6", "gio_gd": "08h00-11h00", "dia_diem": "Nhà VH thôn Tân Hiệp 3"},
    {"stt": 259, "ma_dgd": "TXN0467202", "ten": "Đồng Nơ", "xa": "Tân Khai", "pgd": "PGD Hớn Quản", "ngay_gd": "7", "gio_gd": "8h00-10h30", "dia_diem": "Nhà VH thôn Đồng Nơ 2"},
    {"stt": 260, "ma_dgd": "TXN0463903", "ten": "Minh Tâm", "xa": "Minh Đức", "pgd": "PGD Hớn Quản", "ngay_gd": "9", "gio_gd": "8h00-11h00", "dia_diem": "Nhà VH ấp 1A"},
    {"stt": 261, "ma_dgd": "TXN0467201", "ten": "Tân Khai", "xa": "Tân Khai", "pgd": "PGD Hớn Quản", "ngay_gd": "10", "gio_gd": "8h00-10h30", "dia_diem": "Trụ sở UBND mới"},
    {"stt": 262, "ma_dgd": "TXN0463901", "ten": "An Phú", "xa": "Minh Đức", "pgd": "PGD Hớn Quản", "ngay_gd": "11", "gio_gd": "8h00-10h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 263, "ma_dgd": "TXN0467101", "ten": "Thanh An", "xa": "Tân Hưng", "pgd": "PGD Hớn Quản", "ngay_gd": "12", "gio_gd": "8h30-12h00", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 264, "ma_dgd": "TXN0463902", "ten": "Minh Đức", "xa": "Minh Đức", "pgd": "PGD Hớn Quản", "ngay_gd": "14", "gio_gd": "08h00-11h00", "dia_diem": "Hội trường UBND xã Minh Đức"},
    {"stt": 265, "ma_dgd": "TXN0467501", "ten": "Quang Minh", "xa": "Tân Quan", "pgd": "PGD Hớn Quản", "ngay_gd": "15", "gio_gd": "8h00-10h30", "dia_diem": "Nhà VH ấp Bào Teng"},
    {"stt": 266, "ma_dgd": "TXN0467103", "ten": "An Khương", "xa": "Tân Hưng", "pgd": "PGD Hớn Quản", "ngay_gd": "16", "gio_gd": "8h30-11h30", "dia_diem": "Trụ sở UBND cũ"},
    {"stt": 267, "ma_dgd": "TXN0467502", "ten": "Hớn Quản", "xa": "Tân Quan", "pgd": "PGD Hớn Quản", "ngay_gd": "17", "gio_gd": "08h00-11h00", "dia_diem": "Công an xã Tân Quan"},
    {"stt": 268, "ma_dgd": "TXN0467102", "ten": "Tân Hưng", "xa": "Tân Hưng", "pgd": "PGD Hớn Quản", "ngay_gd": "18", "gio_gd": "8h30-11h30", "dia_diem": "Hội trường UBND xã Tân Hưng"},
    {"stt": 269, "ma_dgd": "TXN0467504", "ten": "Lợi Hưng", "xa": "Tân Quan", "pgd": "PGD Hớn Quản", "ngay_gd": "19", "gio_gd": "08h00-11h00", "dia_diem": "Trung tâm dịch vụ tổng hợp xã Tân Quan"},
    {"stt": 270, "ma_dgd": "TXN0467503", "ten": "Tân Quan", "xa": "Tân Quan", "pgd": "PGD Hớn Quản", "ngay_gd": "21", "gio_gd": "8h00-11h00", "dia_diem": "Trụ sở UBND mới"}
]

def lay_dgd_cho_pgd(pgd: str) -> list[dict]:
    """Trả về danh sách ĐGD thuộc một PGD."""
    return [d for d in DGD_DANH_SACH if d["pgd"] == pgd]


def lay_dgd_theo_xa(xa_short: str) -> list[dict]:
    """Trả về danh sách ĐGD thuộc một xã (khớp tên ngắn, không phân biệt hoa/thường)."""
    xa_norm = xa_short.strip().lower()
    return [d for d in DGD_DANH_SACH if d["xa"].strip().lower() == xa_norm]
