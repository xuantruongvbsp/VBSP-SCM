"""Careful fix of hardcoded column names in tab_baocao.py."""
import re

path = r'd:\VBSP-SCM\tabs\tab_baocao.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# ── 1. Remove local constant (now from config import *) ──
if 'COT_DU_NO_KHOANH = "Dư nợ khoanh"\n' in content:
    content = content.replace('COT_DU_NO_KHOANH = "Dư nợ khoanh"\n', '', 1)
    changes += 1
    print('1. Removed local COT_DU_NO_KHOANH declaration')

# ── 2. Replace _COT_KHOANH definition ──
if '_COT_KHOANH = "Dư nợ khoanh"' in content:
    content = content.replace('_COT_KHOANH = "Dư nợ khoanh"', '_COT_KHOANH = COT_DU_NO_KHOANH', 1)
    changes += 1
    print('2. Fixed _COT_KHOANH definition')

# ── 3. Column list on lines ~90-95 ──
col_list_fixes = [
    ('"Tên xã"', 'COT_TEN_XA'),
    ('"Tên thôn"', 'COT_TEN_THON'),
    ('"Tên ĐVUT"', 'COT_DVUT'),
    ('"Tên tổ"', 'COT_TEN_TO'),
    ('"Số điện thoại"', 'COT_SDT'),
    ('"Địa chỉ"', 'COT_DIA_CHI'),
    ('"Nguồn vốn"', 'COT_NGUON_VON'),
]

# Only replace in the column list context (around lines 85-100)
lines = content.split('\n')
in_col_list = False
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('#'):
        continue
    if stripped.startswith(('COT_', '"Tên', '"Số', '"Địa', '"Nguồn')):
        in_col_list = True
    elif in_col_list and stripped.endswith(']') and not stripped.startswith('COT_'):
        in_col_list = False
    
for old_str, new_str in col_list_fixes:
    if old_str in content:
        content = content.replace(old_str, new_str)
        changes += 1
        print(f'3. Replaced {old_str} → {new_str}')

# ── 4. Line 316: nhom assignment ──
old = 'nhom = "Tên xã" if cap_xa == "Theo xã" else "Tên thôn"'
new = 'nhom = COT_TEN_XA if cap_xa == "Theo xã" else COT_TEN_THON'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('4. Fixed nhom assignment')

# ── 5. DataFrame operations with "Tên ĐVUT" ──
# Line 338: if "Tên ĐVUT" in df_base.columns:
old = 'if "Tên ĐVUT" in df_base.columns:'
new = 'if COT_DVUT in df_base.columns:'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('5. Fixed Tên ĐVUT check in df_base')

# Line 342: dbc_raw = df_kh.groupby("Tên ĐVUT").agg(
old = 'dbc_raw = df_kh.groupby("Tên ĐVUT").agg('
new = 'dbc_raw = df_kh.groupby(COT_DVUT).agg('
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('5b. Fixed Tên ĐVUT groupby')

# Line 356: khd = tong_hop_khong_hd(df_kh, nhom_theo="Tên ĐVUT")
old = 'khd = tong_hop_khong_hd(df_kh, nhom_theo="Tên ĐVUT")'
new = 'khd = tong_hop_khong_hd(df_kh, nhom_theo=COT_DVUT)'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('5c. Fixed Tên ĐVUT in tong_hop_khong_hd')

# Line 359: khd[["Tên ĐVUT", "Món_3m_KHĐ",
old = 'khd[["Tên ĐVUT"'
new = 'khd[[COT_DVUT'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('5d. Fixed Tên ĐVUT in khd select')

# Line 361: on="Tên ĐVUT", how="left"
old = 'on="Tên ĐVUT", how="left"'
new = 'on=COT_DVUT, how="left"'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('5e. Fixed Tên ĐVUT in merge')

# Line 375: ds_dvut = sorted(df_kh["Tên ĐVUT"].dropna().unique().tolist())
old = 'ds_dvut = sorted(df_kh["Tên ĐVUT"].dropna().unique().tolist())'
new = 'ds_dvut = sorted(df_kh[COT_DVUT].dropna().unique().tolist())'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('5f. Fixed Tên ĐVUT in ds_dvut')

# Line 385: df_kh, nhom_theo="Tên ĐVUT", gia_tri_nhom=gia_tri)
old = ', nhom_theo="Tên ĐVUT", gia_tri_nhom=gia_tri)'
new = ', nhom_theo=COT_DVUT, gia_tri_nhom=gia_tri)'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('5g. Fixed Tên ĐVUT in ds_chi_tiet_khong_hd')

# ── 6. "Nguồn vốn" in DataFrame operations (lines 427-430) ──
old = 'and "Nguồn vốn" in df_ct_th.columns:'
new = 'and COT_NGUON_VON in df_ct_th.columns:'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('6a. Fixed Nguồn vốn check')

old = 'df_ct_th = df_ct_th[df_ct_th["Nguồn vốn"] == 1]'
new = 'df_ct_th = df_ct_th[df_ct_th[COT_NGUON_VON] == 1]'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('6b. Fixed Nguồn vốn == 1')

old = 'df_ct_th = df_ct_th[df_ct_th["Nguồn vốn"] == 2]'
new = 'df_ct_th = df_ct_th[df_ct_th[COT_NGUON_VON] == 2]'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('6c. Fixed Nguồn vốn == 2')

# ── 7. Lines 510-526: filter with "Tên xã", "Tên ĐVUT" ──
old = '["Tất cả"]+sorted(df_base["Tên xã"].dropna().unique().tolist())\n                            if "Tên xã" in df_base.columns else ["Tất cả"],'
new = '["Tất cả"]+sorted(df_base[COT_TEN_XA].dropna().unique().tolist())\n                            if COT_TEN_XA in df_base.columns else ["Tất cả"],'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('7a. Fixed Tên xã filter')

old = '["Tất cả"]+sorted(df_base["Tên ĐVUT"].dropna().unique().tolist())\n                            if "Tên ĐVUT" in df_base.columns else ["Tất cả"],'
new = '["Tất cả"]+sorted(df_base[COT_DVUT].dropna().unique().tolist())\n                            if COT_DVUT in df_base.columns else ["Tất cả"],'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('7b. Fixed Tên ĐVUT filter')

# Lines 525-526
old = 'if loc_xa_ct   != "Tất cả" and "Tên xã"       in df_ct.columns: df_ct = df_ct[df_ct["Tên xã"]       == loc_xa_ct]'
new = 'if loc_xa_ct   != "Tất cả" and COT_TEN_XA       in df_ct.columns: df_ct = df_ct[df_ct[COT_TEN_XA]       == loc_xa_ct]'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('7c. Fixed Tên xã == loc_xa_ct')

old = 'if loc_dvut_ct != "Tất cả" and "Tên ĐVUT"     in df_ct.columns: df_ct = df_ct[df_ct["Tên ĐVUT"]     == loc_dvut_ct]'
new = 'if loc_dvut_ct != "Tất cả" and COT_DVUT     in df_ct.columns: df_ct = df_ct[df_ct[COT_DVUT]     == loc_dvut_ct]'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('7d. Fixed Tên ĐVUT == loc_dvut_ct')

# ── 8. Lines 585-587: groupby with "Tên xã" ──
old = 'if "Tên xã" in df_ct2.columns:\n                            t_xa = df_ct2.groupby("Tên xã").agg('
new = 'if COT_TEN_XA in df_ct2.columns:\n                            t_xa = df_ct2.groupby(COT_TEN_XA).agg('
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('8a. Fixed Tên xã groupby')

# ── 9. Lines 612-640: "Nguồn vốn" blocks ──
old = 'if "Nguồn vốn" in df_ct.columns:\n                        chon_nv = st.radio("Nguồn vốn",'
new = 'if COT_NGUON_VON in df_ct.columns:\n                        chon_nv = st.radio("Nguồn vốn",'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('9a. Fixed Nguồn vốn check')

old = 't_nv = df_ct.groupby("Nguồn vốn").agg('
new = 't_nv = df_ct.groupby(COT_NGUON_VON).agg('
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('9b. Fixed Nguồn vốn groupby')

old = 't_nv["Nguồn vốn"] = t_nv["Nguồn vốn"].map({1:"1 - TW",2:"2 - ĐP"}).fillna(t_nv["Nguồn vốn"].astype(str))'
new = 't_nv[COT_NGUON_VON] = t_nv[COT_NGUON_VON].map({1:"1 - TW",2:"2 - ĐP"}).fillna(t_nv[COT_NGUON_VON].astype(str))'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('9c. Fixed Nguồn vốn map')

old = 'df_nv = df_ct[df_ct["Nguồn vốn"] == nv_val]'
new = 'df_nv = df_ct[df_ct[COT_NGUON_VON] == nv_val]'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('9d. Fixed Nguồn vốn filter')

# ── 10. Lines 673-685: second column list ──
old = 'COLTEN_PGD, "Tên xã", "Tên ĐVUT", "Tên tổ",'
new = 'COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_TO,'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10a. Fixed col list 2')

old = 'COLTEN_MA_KH, COLTEN_KH, "Số điện thoại",'
new = 'COT_MA_KH, COT_TEN_KH, COT_SDT,'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10b. Fixed col list 2b')

# Line 676: COT_TONG_DU_NO, COT_DU_NO_QH, "Dư nợ khoanh", COT_LAI_TON, "Nguồn vốn",
old = 'COT_TONG_DU_NO, COT_DU_NO_QH, "Dư nợ khoanh", COT_LAI_TON, "Nguồn vốn",'
new = 'COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_LAI_TON, COT_NGUON_VON,'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10c. Fixed col list 2c')

# Line 685: sort cols
old = '_sort_kh = [c for c in ["Tên ĐVUT", "Tên tổ", COT_TEN_KH] if c in df_ct.columns]'
new = '_sort_kh = [c for c in [COT_DVUT, COT_TEN_TO, COT_TEN_KH] if c in df_ct.columns]'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10d. Fixed sort_kh')

old = 'if "Tên ĐVUT" in df_kh_rpt.columns:'
new = 'if COT_DVUT in df_kh_rpt.columns:'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10e. Fixed Tên ĐVUT rpt check')

old = 'df_kh_rpt.groupby("Tên ĐVUT").agg(**_agg_kh)'
new = 'df_kh_rpt.groupby(COT_DVUT).agg(**_agg_kh)'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10f. Fixed Tên ĐVUT rpt groupby')

# Line 714
old = '_sort_qh = [c for c in ["Tên ĐVUT", "Tên tổ", COT_TEN_KH] if c in df_ct.columns]'
new = '_sort_qh = [c for c in [COT_DVUT, COT_TEN_TO, COT_TEN_KH] if c in df_ct.columns]'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10g. Fixed sort_qh')

# Lines 731-734: separate replacements
old = 'if "Tên ĐVUT" in df_qh_rpt.columns:'
new = 'if COT_DVUT in df_qh_rpt.columns:'
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10h. Fixed Tên ĐVUT qh if')

old = 'df_qh_rpt.groupby("Tên ĐVUT").agg('
new = 'df_qh_rpt.groupby(COT_DVUT).agg('
if old in content:
    content = content.replace(old, new, 1)
    changes += 1
    print('10i. Fixed Tên ĐVUT qh groupby')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\n=== Total: {changes} replacements applied ===')
