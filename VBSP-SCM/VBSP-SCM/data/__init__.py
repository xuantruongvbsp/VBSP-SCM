"""
data/ — Package quản lý dữ liệu VBSP-SCM
─────────────────────────────────────────
Cấu trúc:
  core.py  → ts_file, excel_to_parquet
  hstd.py  → doc_file, doc_file_nq11, doc_file_gqvl, doc_dienbao, db_lookup
  pgd.py   → quản lý file riêng từng PGD (upload, đọc, gộp)
  khtd.py  → doc_khtd, luu_khtd, doc_phu_luc_qd, doc_cbtd, doc_kehoach

Import từ bên ngoài vẫn dùng: from data import ...
"""

# core
from data.core import ts_file, excel_to_parquet

# hstd
from data.hstd import (
    doc_file, doc_file_nq11, doc_file_gqvl, doc_file_sk_gqvl,
    doc_dienbao, db_lookup, db_nqh_con,
    danh_dau_khong_hd, tong_hop_khong_hd,
    ds_chi_tiet_khong_hd, canh_bao_migration,
)

# pgd
from data.pgd import (
    pgd_slug, duong_dan_pgd, duong_dan_gqvl_pgd,
    luu_file_pgd, luu_gqvl_pgd,
    ds_pgd_co_file, ds_pgd_co_gqvl,
    doc_hstd_pgd, doc_nq11_pgd,
    doc_gqvl_pgd, doc_gqvl_pgd_v2,
    doc_hstd_toan_cn_pgd, doc_gqvl_toan_cn_pgd,
    doc_gqvl_toan_cn, doc_nq11_toan_cn_pgd,
)

# cdtotkvv
from data.cdtotkvv import (
    doc_cdtotkvv,
    ds_thang_nam as ds_thang_nam_cdtotkvv,
    tong_hop_theo_pgd as tong_hop_cdtotkvv_theo_pgd,
)

# khtd
from data.khtd import (
    doc_khtd, luu_khtd,
    doc_kehoach, luu_kehoach,
    doc_cbtd, luu_cbtd,
    doc_phu_luc_qd, luu_phu_luc_qd,
    FILE_KH_QD,
)

# giao_ban
from data.giao_ban import xuat_bien_ban_giao_ban
