"""Test tạm: verify dấu chấm nghìn trong PDF tổng hợp. Xóa sau khi chạy."""
import re
import warnings
import zlib

import pandas as pd

warnings.filterwarnings("ignore")

from tabs.tab_baocao.components.inline_filter import chuan_bi_du_lieu_bao_cao
from tabs.tab_baocao.reports.tong_hop_hstd_v2 import (
    _tao_tong_hop_theo_nhom,
    _tinh_tong_cong,
    _xuat_pdf_tong_hop,
)

df = chuan_bi_du_lieu_bao_cao(pd.read_parquet("cache/hstd.parquet"))
df_th, df_group, co_khoanh = _tao_tong_hop_theo_nhom(df, "pgd", "Tên PGD")
tc = _tinh_tong_cong(df_th, df_group)
b = _xuat_pdf_tong_hop(
    df_th, tc, "Tên PGD", "PGD", co_khoanh, "Bao cao tong hop PGD", "test", "BC_TH_PGD"
)

streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", b, re.DOTALL)
text = ""
ok, fail = 0, 0
for data in streams:
    try:
        text += zlib.decompressobj().decompress(data).decode("latin-1", "ignore")
        ok += 1
    except Exception:
        fail += 1
raw_all = b.decode("latin-1")

lines = [
    f"co_227.905: {'227.905' in text}",
    f"co_340.313: {'340.313' in text}",
    f"con_227905_khong_dau: {'227905' in text}",
    f"con_340313_khong_dau: {'340313' in text}",
]
with open("_tmp_pdf_fmt_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("DONE")
