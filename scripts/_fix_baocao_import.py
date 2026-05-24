"""Temporary script: fix tab_baocao.py imports"""
path = "tabs/tab_baocao.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace from config import * with explicit COT_ imports
old = "from config import *"
new = """from config import (
    COT_DIA_CHI,
    COT_DU_NO_KHOANH,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_LAI_SUAT,
    COT_LAI_TON,
    COT_MA_KH,
    COT_NGAY_DH,
    COT_NGAY_VAY,
    COT_NGUON_VON,
    COT_SDT,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_THON,
    COT_TEN_TO,
    COT_TEN_XA,
    COT_THOI_HAN,
    COT_TINH_TRANG,
    COT_TONG_DU_NO,
)"""
content = content.replace(old, new)

# 2. Remove top-level import of tab_nq11
content = content.replace("from tabs import tab_nq11\n", "")

# 3. Lazy import tab_nq11 at the usage site
content = content.replace(
    "tab_nq11.render(st.container(), **kwargs)",
    'import importlib; tab_nq11 = importlib.import_module("tabs.tab_nq11"); tab_nq11.render(st.container(), **kwargs)'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("OK")
