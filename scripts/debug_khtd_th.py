r"""
Debug script: phân tích chênh lệch TH KHTD giữa cấp CN và tổng 95 xã.
Phát hiện: 21/27 ma_key có CN < Xã, 2 key có CN > Xã (12_TW, 12_DP).

Chạy:
  cd D:\VBSP-SCM
  python scripts\debug_khtd_th.py > scripts\debug_khtd_out.txt 2>&1
"""
from __future__ import annotations

import sys, os
sys.dont_write_bytecode = True
os.environ["STREAMLIT_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_RUNNER_MAGIC"] = "0"

import warnings
warnings.filterwarnings("ignore")

import pyarrow.parquet as pq
import pandas as pd
import numpy as np

# ── Import project ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    CHUONG_TRINH_KHTD,
    COT_TEN_PGD, COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON,
    COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT,
    DS_PGD, PGD_XA_MAP, CACHE_HSTD, CACHE_GQVL,
)
from services.khtd_nhap_service import tinh_th_gqvl_phan_tang as _tinh_th_gqvl_phan_tang

# ── Hằng số ──
KV_KEY_CN  = "khtd_cn"
KV_KEY_XA  = "khtd_xa"
DS_MA_CT   = [row[0] for row in CHUONG_TRINH_KHTD]
CT_TW      = [(mk, ten) for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD if nv == "TW"]
CT_DP      = [(mk, ten) for mk, _, ten, nv, _ in CHUONG_TRINH_KHTD if nv == "DP"]
NGUON_VON_MA = {mk: nv for mk, _, _, nv, _ in CHUONG_TRINH_KHTD}
MA_CT_BY_MAKEY = {mk: int(ma_ct) for mk, ma_ct, _, _, _ in CHUONG_TRINH_KHTD}
TEN_BASE_BY_MACT: dict[int, str] = {}
for mk, ma_ct, ten, _nv, _ in CHUONG_TRINH_KHTD:
    TEN_BASE_BY_MACT.setdefault(int(ma_ct), str(ten))
GQVL_TW_TONG_KEY = "3_TW"
GQVL_DP_TONG_KEY = "3_DP"
MAKEY_BY_MACT_NV: dict[tuple[int, int], list[str]] = {}
for mk, ma_ct, ten, nv, _ in CHUONG_TRINH_KHTD:
    MAKEY_BY_MACT_NV.setdefault((int(ma_ct), 1 if nv == "TW" else 2), []).append(mk)

_LOOKUP_XA_CT: dict[tuple[int, int], str] = {}
for _mk, _ma_ct, _, _nv, _ in CHUONG_TRINH_KHTD:
    _LOOKUP_XA_CT.setdefault((int(_ma_ct), 1 if _nv == "TW" else 2), _mk)


def _tong_tu_keys(data: dict[str, float], keys: list[str]) -> float:
    return float(sum(float(data.get(key, 0.0) or 0.0) for key in keys))


def _dong_bo_gqvl_tong_keys(data: dict[str, float]) -> dict[str, float]:
    out = dict(data)
    tong_tw = _tong_tu_keys(out, ["3_TW_NHCSXH", "3_TW_NSNN"])
    tong_dp = _tong_tu_keys(out, ["3_DP_TINH", "3_DP_XA"])
    if tong_tw > 0 or any(k in out for k in ["3_TW_NHCSXH", "3_TW_NSNN"]):
        out[GQVL_TW_TONG_KEY] = tong_tw
    if tong_dp > 0 or any(k in out for k in ["3_DP_TINH", "3_DP_XA"]):
        out[GQVL_DP_TONG_KEY] = tong_dp
    return out


# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 1: ĐỌC DỮ LIỆU
# ══════════════════════════════════════════════════════════════════════════
print("=" * 90)
print("DEBUG CHI TIẾT CHÊNH LỆCH TH KHTD GIỮA CN VÀ TỔNG 95 XÃ")
print("=" * 90)

print("\n📂 Đọc HSTD...")
schema = pq.read_schema(CACHE_HSTD)
cols = [f.name for f in schema]
print(f"   HSTD columns: {len(cols)}")

df = pq.read_table(CACHE_HSTD, columns=[
    COT_TEN_PGD, COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON,
    COT_TONG_DU_NO, COT_DU_NO_TH, COT_TEN_CT,
]).to_pandas()
print(f"   HSTD rows: {len(df):,}")

# Xác định cột dư nợ
col_th = COT_TONG_DU_NO if COT_TONG_DU_NO in df.columns else COT_DU_NO_TH
df[col_th] = pd.to_numeric(df[col_th], errors="coerce").fillna(0)
df[COT_MA_CHUONG_TRINH] = pd.to_numeric(df[COT_MA_CHUONG_TRINH], errors="coerce").fillna(0).astype(int)
df[COT_NGUON_VON] = pd.to_numeric(df[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 2: TÍNH THEO CẤP CN (giống _tinh_thuc_hien_khtd_cn)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PHẦN 2: TÍNH TH CẤP CHI NHÁNH")
print("=" * 90)

tmp_cn = df[(df[COT_MA_CHUONG_TRINH] > 0) & (df[COT_NGUON_VON].isin([1, 2])) & (df[col_th] != 0)].copy()

cn_by_pair = tmp_cn.groupby([COT_MA_CHUONG_TRINH, COT_NGUON_VON])[col_th].sum()

cn_out: dict[str, float] = {}
for (ma_ct, nv_int), val in cn_by_pair.items():
    if int(ma_ct) == 3:
        cn_out[GQVL_TW_TONG_KEY if int(nv_int) == 1 else GQVL_DP_TONG_KEY] = float(val)
        continue
    for mk in MAKEY_BY_MACT_NV.get((int(ma_ct), int(nv_int)), []):
        cn_out[mk] = float(val)

# GQVL phân tầng
df_gqvl_path = CACHE_GQVL
if os.path.exists(df_gqvl_path):
    df_gqvl = pq.read_table(df_gqvl_path).to_pandas()
    print(f"\n📂 Đã đọc GQVL ({len(df_gqvl):,} dòng)")
    th_gqvl = _tinh_th_gqvl_phan_tang(df, df_gqvl)
else:
    th_gqvl = {}
    print("\n⚠️ Không tìm thấy GQVL cache")

if th_gqvl:
    cn_out.update({k: float(v or 0.0) for k, v in th_gqvl.items()})
    cn_out[GQVL_TW_TONG_KEY] = _tong_tu_keys(cn_out, ["3_TW_NHCSXH", "3_TW_NSNN"])
    cn_out[GQVL_DP_TONG_KEY] = _tong_tu_keys(cn_out, ["3_DP_TINH", "3_DP_XA"])

cn_out = _dong_bo_gqvl_tong_keys(cn_out)
print(f"   CN có {len(cn_out)} ma_key")
for k in sorted(cn_out):
    print(f"     {k:25s} = {cn_out[k]:>15.0f}")

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 3: TÍNH THEO XÃ (giống _tinh_th_xa_ct + PGD_XA_MAP)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PHẦN 3: TÍNH TH THEO 95 XÃ")
print("=" * 90)

# Tính toàn bộ mapping (ten_xa, ma_ct, nv) → VND
tmp_xa = df[(df[COT_MA_CHUONG_TRINH] > 0) & (df[COT_NGUON_VON].isin([1, 2]))].copy()
# KHÔNG filter (th != 0) để giống _tinh_th_xa_ct

xa_ct_raw: dict[tuple, float] = {}
for (xa, ma_ct, nv), s in tmp_xa.groupby([COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON])[col_th].sum().items():
    mk = _LOOKUP_XA_CT.get((int(ma_ct), int(nv)))
    if mk:
        xa_ct_raw[(str(xa), mk)] = float(s)

# Gom theo ma_key, chỉ lấy xã trong PGD_XA_MAP
xa_set = set()
for pgd, ds_xa in PGD_XA_MAP.items():
    for x in ds_xa:
        xa_set.add(x)
print(f"   Số xã trong PGD_XA_MAP: {len(xa_set)}")

xa_by_key: dict[str, float] = {}
xa_detail: dict[str, dict[str, float]] = {}  # ma_key → {ten_xa: vnd}
for (xa, mk), v in xa_ct_raw.items():
    if xa not in xa_set:
        continue
    xa_by_key[mk] = xa_by_key.get(mk, 0.0) + v
    if mk not in xa_detail:
        xa_detail[mk] = {}
    xa_detail[mk][xa] = xa_detail[mk].get(xa, 0.0) + v

print(f"   Xã có {len(xa_by_key)} ma_key")
for k in sorted(xa_by_key):
    print(f"     {k:25s} = {xa_by_key[k]:>15.0f}")

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 4: SO SÁNH & PHÂN TÍCH
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PHẦN 4: SO SÁNH CN vs XÃ")
print("=" * 90)

all_keys = sorted(set(list(cn_out.keys()) + list(xa_by_key.keys())))
print(f"{'ma_key':25s} {'CN':>15s} {'XÃ':>15s} {'CHÊNH LỆCH':>15s} {'%':>8s}")
print("-" * 80)
for k in all_keys:
    cn_v = cn_out.get(k, 0.0)
    xa_v = xa_by_key.get(k, 0.0)
    diff = cn_v - xa_v
    pct = (diff / max(cn_v, xa_v) * 100) if max(cn_v, xa_v) > 0 else 0
    print(f"{k:25s} {cn_v:>15.0f} {xa_v:>15.0f} {diff:>+15.0f} {pct:>+7.1f}%")

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 5: TRUY VẾT CHI TIẾT TỪNG KEY CHÊNH LỆCH
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PHẦN 5: TRUY VẾT CHI TIẾT TỪNG KEY CHÊNH LỆCH")
print("=" * 90)

# Xác định key chênh lệch đáng kể (>1 triệu)
threshold = 1_000_000
diff_keys = []
for k in all_keys:
    cn_v = cn_out.get(k, 0.0)
    xa_v = xa_by_key.get(k, 0.0)
    diff = abs(cn_v - xa_v)
    if diff > threshold:
        diff_keys.append(k)

print(f"\nPhát hiện {len(diff_keys)} key chênh lệch > {threshold:,} VND")
print()

for k in sorted(diff_keys):
    cn_v = cn_out.get(k, 0.0)
    xa_v = xa_by_key.get(k, 0.0)
    diff = cn_v - xa_v
    
    print(f"{'─' * 80}")
    print(f"  🔍 KEY: {k}")
    print(f"     CN    = {cn_v:>18,.0f} VND")
    print(f"     XÃ    = {xa_v:>18,.0f} VND")
    print(f"     CHÊNH = {diff:>+18,.0f} VND")
    
    # Xác định ma_ct và nv từ key
    ma_ct = None
    nv_int = None
    if k in MAKEY_BY_MACT_NV:
        # Đảo ngược: tìm (ma_ct, nv) từ key
        for (mc, nv_i), mk in MAKEY_BY_MACT_NV.items():
            if mk == k:
                ma_ct, nv_int = mc, nv_i
                break
    
    if ma_ct is None:
        # Xử lý key đặc biệt
        if k == GQVL_TW_TONG_KEY:
            ma_ct, nv_int = 3, 1
        elif k == GQVL_DP_TONG_KEY:
            ma_ct, nv_int = 3, 2
        elif k in ("3_TW_NHCSXH", "3_TW_NSNN", "cap_tinh_tw_nhcsxh", "cap_tinh_tw_nsnn"):
            ma_ct, nv_int = 3, 1
        elif k in ("3_DP_TINH", "3_DP_XA", "cap_tinh", "cap_xa", "cap_tinh_tw"):
            ma_ct, nv_int = 3, 2
    
    if diff > 0:
        # CN > Xã: có records không mapping được vào xã nào trong PGD_XA_MAP
        print(f"\n     ⚡ CHÊNH LỆCH DƯƠNG (CN > Xã):")
        print(f"     → Tìm records HSTD thuộc CN nhưng KHÔNG mapping vào xã PGD_XA_MAP...")
        
        if ma_ct is not None and nv_int is not None:
            # HSTD records cho ma_ct, nv này
            mask = (df[COT_MA_CHUONG_TRINH] == ma_ct) & (df[COT_NGUON_VON] == nv_int) & (df[col_th] != 0)
            subset = df[mask].copy()
            
            # Tag xã
            subset["_trong_xa_map"] = subset[COT_TEN_XA].isin(xa_set)
            
            orphan = subset[~subset["_trong_xa_map"]]
            matched = subset[subset["_trong_xa_map"]]
            
            orphan_sum = orphan[col_th].sum()
            matched_sum = matched[col_th].sum()
            
            print(f"       Tổng CN: {cn_v:>18,.0f}")
            print(f"       Tổng records trong XÃ MAP: {matched_sum:>18,.0f} ({len(matched):,} dòng)")
            print(f"       Tổng records NGOÀI XÃ MAP: {orphan_sum:>18,.0f} ({len(orphan):,} dòng)")
            
            if len(orphan) > 0:
                print(f"\n       📋 Records NGOÀI XÃ MAP (top 20):")
                orphan_summary = orphan.groupby(COT_TEN_PGD)[col_th].agg(["sum", "count"]).sort_values("sum", ascending=False)
                for pgd, row in orphan_summary.head(20).iterrows():
                    print(f"         PGD={pgd:25s}  sum={row['sum']:>15,.0f}  count={int(row['count']):,}")
                
                # Xem tên xã của orphans
                xa_orphan = orphan[COT_TEN_XA].value_counts().head(15)
                print(f"\n       📋 Tên xã không có trong PGD_XA_MAP (top 15):")
                for xa_n, cnt in xa_orphan.items():
                    print(f"         '{xa_n}' → {cnt:,} dòng")
    else:
        # CN < Xã: xã có data nhiều hơn CN
        print(f"\n     ⚡ CHÊNH LỆCH ÂM (CN < Xã):")
        print(f"     → Kiểm tra 2 nguyên nhân:")
        print(f"       1) CN filter (th != 0) — Xã KHÔNG filter")
        print(f"       2) Dữ liệu bị trùng/đếm 2 lần ở xã")
        
        if ma_ct is not None and nv_int is not None:
            mask = (df[COT_MA_CHUONG_TRINH] == ma_ct) & (df[COT_NGUON_VON] == nv_int)
            subset_all = df[mask].copy()
            subset_nonzero = subset_all[subset_all[col_th] != 0].copy()
            subset_zero = subset_all[subset_all[col_th] == 0].copy()
            
            all_sum = subset_all[col_th].sum()
            nonzero_sum = subset_nonzero[col_th].sum()
            zero_sum = subset_zero[col_th].sum()
            
            print(f"\n       Tổng HSTD (ma_ct={ma_ct}, nv={nv_int}):")
            print(f"         Tất cả records: {all_sum:>18,.0f} ({len(subset_all):,} dòng)")
            print(f"         Records ≠ 0:     {nonzero_sum:>18,.0f} ({len(subset_nonzero):,} dòng)")
            print(f"         Records = 0:     {zero_sum:>18,.0f} ({len(subset_zero):,} dòng)")
            
            # Chênh lệch sau khi loại zero
            fixed_xa = xa_v - zero_sum
            new_diff = cn_v - fixed_xa
            print(f"\n       → Nếu loại records=0 khỏi Xã: chênh = {new_diff:>+18,.0f}")
            
            # Kiểm tra duplicate xã trong PGD_XA_MAP
            all_xa_entries = []
            for pgd, xs in PGD_XA_MAP.items():
                for x in xs:
                    all_xa_entries.append((pgd, x))
            xa_df = pd.DataFrame(all_xa_entries, columns=["pgd", "xa"])
            dup_xa = xa_df[xa_df.duplicated(subset="xa", keep=False)]
            if len(dup_xa) > 0:
                print(f"\n       ⚠️ Xã xuất hiện ở NHIỀU PGD trong PGD_XA_MAP:")
                for xa_name, group in dup_xa.groupby("xa"):
                    pgds = group["pgd"].tolist()
                    print(f"         '{xa_name}' → {pgds}")

    print()

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 6: KIỂM TRA XÃ TRÙNG LẶP TRONG PGD_XA_MAP
# ══════════════════════════════════════════════════════════════════════════
print("=" * 90)
print("PHẦN 6: KIỂM TRA XÃ TRÙNG LẶP TRONG PGD_XA_MAP")
print("=" * 90)

all_xa_pairs = []
for pgd, xs in PGD_XA_MAP.items():
    for x in xs:
        all_xa_pairs.append((pgd, x))

xa_count = pd.DataFrame(all_xa_pairs, columns=["pgd", "xa"])
dup = xa_count[xa_count.duplicated(subset="xa", keep=False)]
if len(dup) > 0:
    print(f"⚠️ Phát hiện {dup['xa'].nunique()} xã xuất hiện ở nhiều PGD:")
    for xa, grp in dup.groupby("xa"):
        pgds = grp["pgd"].tolist()
        print(f"   '{xa}' → {pgds}")
else:
    print("✅ Không có xã nào trùng lặp.")

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 7: KIỂM TRA HSTD — TÊN XÃ CÓ TRONG PGD_XA_MAP KHÔNG
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PHẦN 7: KIỂM TRA TÊN XÃ TRONG HSTD vs PGD_XA_MAP")
print("=" * 90)

hstd_xa_set = set(df[COT_TEN_XA].dropna().unique())
map_xa_set = xa_set  # từ PGD_XA_MAP

# Xã trong HSTD nhưng không trong MAP
missing_in_map = hstd_xa_set - map_xa_set
extra_in_map = map_xa_set - hstd_xa_set

print(f"   Xã trong HSTD: {len(hstd_xa_set)}")
print(f"   Xã trong PGD_XA_MAP: {len(map_xa_set)}")
print(f"   Xã trong HSTD nhưng KHÔNG trong MAP: {len(missing_in_map)}")
if missing_in_map:
    for x in sorted(missing_in_map):
        # Tổng dư nợ cho xã này
        mask = (df[COT_TEN_XA] == x) & (df[col_th] != 0)
        tot = df.loc[mask, col_th].sum()
        pgds = df.loc[mask, COT_TEN_PGD].unique().tolist()
        print(f"     '{x}' — Tổng dư nợ: {tot:>15,.0f} — PGD: {pgds[:5]}")

print(f"\n   Xã trong MAP nhưng KHÔNG trong HSTD: {len(extra_in_map)}")
if extra_in_map:
    for x in sorted(extra_in_map):
        # Tìm trong các PGD
        for pgd, xs in PGD_XA_MAP.items():
            if x in xs:
                print(f"     '{x}' — thuộc {pgd}")
                break

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 8: PHÂN TÍCH CỤ THỂ KEY 12_DP & 12_TW (CN > Xã)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PHẦN 8: PHÂN TÍCH KEY 12_DP & 12_TW (CN > Xã)")
print("=" * 90)

for ma_ct, nv_int, label in [(12, 1, "12_TW"), (12, 2, "12_DP")]:
    mask = (df[COT_MA_CHUONG_TRINH] == ma_ct) & (df[COT_NGUON_VON] == nv_int) & (df[col_th] != 0)
    subset = df[mask].copy()
    print(f"\n  📋 {label}: {len(subset):,} dòng, Tổng={subset[col_th].sum():,.0f}")
    
    # Phân bố theo PGD
    pgd_sum = subset.groupby(COT_TEN_PGD)[col_th].agg(["sum", "count"]).sort_values("sum", ascending=False)
    print(f"     Phân bố PGD (top 10):")
    for pgd, row in pgd_sum.head(10).iterrows():
        in_xa = pgd in [p for p, _ in all_xa_pairs]  # always True
        print(f"       {pgd:25s}  sum={row['sum']:>15,.0f}  cnt={int(row['count']):,}")
    
    # Xã mapping
    subset["_trong_map"] = subset[COT_TEN_XA].isin(xa_set)
    orphan = subset[~subset["_trong_map"]]
    if len(orphan) > 0:
        print(f"\n     ⚠️ Records không mapping (orphan): {len(orphan):,} dòng, sum={orphan[col_th].sum():,.0f}")
        xa_orphan = orphan[COT_TEN_XA].value_counts().head(10)
        print(f"     Tên xã orphan (top 10):")
        for xa_n, cnt in xa_orphan.items():
            pgd_orphan = orphan[orphan[COT_TEN_XA] == xa_n][COT_TEN_PGD].iloc[0]
            s = orphan.loc[orphan[COT_TEN_XA] == xa_n, col_th].sum()
            print(f"       '{xa_n}' (PGD={pgd_orphan}) → {cnt:,} dòng, sum={s:,.0f}")

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 9: KIỂM TRA CỘT DƯ NỢ — CÓ NHIỀU CỘT KHÁC NHAU KHÔNG
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PHẦN 9: KIỂM TRA CỘT DƯ NỢ ĐƯỢC SỬ DỤNG")
print("=" * 90)

col_candidates = ["Tổng dư nợ", "Dư nợ trong hạn", "Dư nợ quá hạn", "Dư nợ khoanh"]
for c in col_candidates:
    if c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce").fillna(0)
        print(f"   {c:25s}: sum={s.sum():>20,.0f}  nonzero={(s>0).sum():,}  zero={(s==0).sum():,}")

# ══════════════════════════════════════════════════════════════════════════
#  PHẦN 10: KIỂM TRA ẢNH HƯỞNG CỦA FILTER (th != 0)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PHẦN 10: ẢNH HƯỞNG CỦA FILTER (th != 0)")
print("=" * 90)

# Giả lập xã KHÔNG filter (th != 0)
tmp_xa_no_filter = df[(df[COT_MA_CHUONG_TRINH] > 0) & (df[COT_NGUON_VON].isin([1, 2]))].copy()
xa_ct_no_filter: dict[tuple, float] = {}
for (xa, ma_ct, nv), s in tmp_xa_no_filter.groupby([COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON])[col_th].sum().items():
    mk = _LOOKUP_XA_CT.get((int(ma_ct), int(nv)))
    if mk:
        xa_ct_no_filter[(str(xa), mk)] = float(s)

xa_no_filter_by_key: dict[str, float] = {}
for (xa, mk), v in xa_ct_no_filter.items():
    if xa not in xa_set:
        continue
    xa_no_filter_by_key[mk] = xa_no_filter_by_key.get(mk, 0.0) + v

print(f"\nSo sánh XÃ (filter th=0) vs XÃ (no filter):")
print(f"{'ma_key':25s} {'XÃ (filter)':>15s} {'XÃ (th=0 có)':>15s} {'chênh':>15s}")
for k in sorted(set(list(xa_by_key.keys()) + list(xa_no_filter_by_key.keys()))):
    v1 = xa_by_key.get(k, 0.0)
    v2 = xa_no_filter_by_key.get(k, 0.0)
    d = v2 - v1
    if abs(d) > 0:
        print(f"{k:25s} {v1:>15.0f} {v2:>15.0f} {d:>+15.0f}")

# ══════════════════════════════════════════════════════════════════════════
#  KẾT LUẬN
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("KẾT LUẬN")
print("=" * 90)

# Phân loại nguyên nhân
print(f"""
PHÂN TÍCH NHANH:

1. GQVL sub-keys không tính ở xã (dự kiến):
   3_TW, 3_DP, 3_TW_NHCSXH, 3_TW_NSNN, 3_DP_TINH, 3_DP_XA
   cap_tinh, cap_xa, cap_tinh_tw_nhcsxh, cap_tinh_tw_nsnn, cap_tinh_tw
   
2. Key có CN > Xã (thiếu mapping xã):
   12_TW, 12_DP
   
3. Key có CN < Xã (đa số còn lại):
   Nguyên nhân có thể:
   a) Xã KHÔNG filter (th != 0) trong khi CN có filter
   b) Dữ liệu HSTD có records Tổng dư nợ = 0 nhưng vẫn được groupby → sum = 0 an toàn
   c) Khác biệt cột được dùng (Tổng dư nợ vs Dư nợ trong hạn)
""")

print("DONE")
