"""
Script: xác định xã nào trong 4 PGD (Định Quán, Tân Phú, Thống Nhất, Vĩnh Cửu)
có GQVL ĐP dư nợ thuộc diện phân tầng (Mã NĐT cấp tỉnh).

Chạy:
  cd D:\VBSP-SCM
  venv\Scripts\python.exe scripts\phan_tang_check.py
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CACHE_HSTD, CACHE_GQVL
from db import doc_ndt_dp_rule_list, phan_loai_ndt_dp_cap

# ── 4 PGD cần kiểm tra ──
DS_KIEM_TRA = ["PGD Định Quán", "PGD Tân Phú", "PGD Thống Nhất", "PGD Vĩnh Cửu"]

print("=" * 90)
print("KIỂM TRA XÃ THUỘC DIỆN PHÂN TẦNG GQVL ĐP TRONG 4 PGD")
print("=" * 90)

# ── 1. Đọc rule Mã NĐT từ kv_store ──
rules = doc_ndt_dp_rule_list()
print(f"\n📋 Rule Mã NĐT ĐP (từ kv_store): {len(rules)} rules")
for r in rules:
    print(f"   ma_ct={r.get('ma_ct','ALL'):>3}  ma={r.get('ma',''):30s}  cap={r.get('cap','tinh'):5s}  ghi_chu={r.get('ghi_chu','')}")
print()

ma_tinh_list = [r["ma"] for r in rules if r.get("cap", "tinh") == "tinh" and r.get("ma_ct") == 3]
print(f"   Mã NĐT cấp tỉnh (GQVL): {ma_tinh_list}")

# ── 2. Đọc HSTD ──
schema = pq.read_schema(CACHE_HSTD)
cols = [f.name for f in schema]
print(f"\n📂 Đọc HSTD ({len(cols)} cột)...")

df = pq.read_table(CACHE_HSTD, columns=[
    "Tên PGD", "Tên xã",
    "Mã chương trình", "Nguồn vốn",
    "Mã nhà đầu tư",
    "Tổng dư nợ", "Dư nợ trong hạn", "Dư nợ quá hạn",
]).to_pandas()

df["Tổng dư nợ"] = pd.to_numeric(df["Tổng dư nợ"], errors="coerce").fillna(0)
df["Mã chương trình"] = pd.to_numeric(df["Mã chương trình"], errors="coerce").fillna(0).astype(int)
df["Nguồn vốn"] = pd.to_numeric(df["Nguồn vốn"], errors="coerce").fillna(0).astype(int)
df["Mã nhà đầu tư"] = df["Mã nhà đầu tư"].fillna("").astype(str).str.strip()

print(f"   HSTD rows: {len(df):,}")

# ── 3. Lọc 4 PGD + GQVL (ma_ct=3) + Nguồn vốn ĐP (nv=2) ──
mask_pgd = df["Tên PGD"].isin(DS_KIEM_TRA)
mask_ct3 = df["Mã chương trình"] == 3
mask_nv_dp = df["Nguồn vốn"] == 2
mask_dn = df["Tổng dư nợ"] != 0

# GQVL ĐP có dư nợ
df_gqvl_dp = df[mask_pgd & mask_ct3 & mask_nv_dp & mask_dn].copy()

print(f"\n{'─' * 90}")
print(f"PHÂN TÍCH GQVL ĐP (ma_ct=3, nv=2) TRONG 4 PGD")
print(f"{'─' * 90}")

# Phân loại cấp
df_gqvl_dp["cap"] = df_gqvl_dp["Mã nhà đầu tư"].map(lambda ma: phan_loai_ndt_dp_cap(3, ma))

# Tổng hợp theo PGD + Xã
for pgd in DS_KIEM_TRA:
    sub = df_gqvl_dp[df_gqvl_dp["Tên PGD"] == pgd]
    if sub.empty:
        print(f"\n📌 {pgd}: ❌ KHÔNG có GQVL ĐP dư nợ")
        continue
    
    print(f"\n📌 {pgd}: {len(sub):,} dòng GQVL ĐP")
    
    # Theo xã
    xa_summary = sub.groupby(["Tên xã", "cap"]).agg(
        tổng_dư_nợ=("Tổng dư nợ", "sum"),
        số_dòng=("Tổng dư nợ", "count"),
        mã_NĐT=("Mã nhà đầu tư", lambda x: list(x.unique())),
    ).reset_index()
    
    # Tính tỷ trọng
    tong_pgd = sub["Tổng dư nợ"].sum()
    
    for _, row in xa_summary.iterrows():
        pct = row["tổng_dư_nợ"] / tong_pgd * 100 if tong_pgd > 0 else 0
        ma_ndt_str = ", ".join(str(m) for m in row["mã_NĐT"])
        print(f"   Xã: {row['Tên xã']:25s}  cap={row['cap']:5s}  "
              f"dư_nợ={row['tổng_dư_nợ']:>15,.0f}  "
              f"({pct:>5.1f}%)  "
              f"số_dòng={row['số_dòng']:>4d}  "
              f"Mã NĐT=[{ma_ndt_str}]")
    
    # Tổng theo cap
    print(f"   ── Tổng PGD: {tong_pgd:>15,.0f}")
    for cap in ["tinh", "xa"]:
        cap_sum = sub.loc[sub["cap"] == cap, "Tổng dư nợ"].sum()
        if cap_sum > 0:
            print(f"     cap_{cap}: {cap_sum:>15,.0f}  ({cap_sum/tong_pgd*100:.1f}%)")

# ── 4. Kiểm tra Mã NĐT lạ (chưa có trong rule) ──
print(f"\n{'─' * 90}")
print("KIỂM TRA MÃ NĐT CHƯA CÓ TRONG RULE")
ma_tinh_set = set(ma_tinh_list)
ma_xa_seen = set()
ma_lạ = []

for _, row in df_gqvl_dp.iterrows():
    ma = row["Mã nhà đầu tư"]
    if not ma:
        continue
    if ma in ma_tinh_set:
        continue
    
    # Check if any rule matches this ma
    matched = False
    for r in rules:
        if r.get("ma") == ma:
            matched = True
            if r.get("cap", "tinh") == "xa":
                ma_xa_seen.add(ma)
            break
    
    if not matched:
        ma_lạ.append(ma)

if ma_lạ:
    print(f"\n⚠️ {len(set(ma_lạ))} Mã NĐT không có rule (mặc định = xa):")
    for ma in sorted(set(ma_lạ)):
        # Show which PGD and xã use this ma
        rows = df_gqvl_dp[df_gqvl_dp["Mã nhà đầu tư"] == ma]
        total_dn = rows["Tổng dư nợ"].sum()
        pgd_xa = rows.groupby(["Tên PGD", "Tên xã"]).size().to_dict()
        pgd_xa_str = "; ".join(f"{pgd}/{xa}" for (pgd, xa) in pgd_xa)
        print(f"   '{ma}' tổng={total_dn:>15,.0f}  locations=[{pgd_xa_str}]")
else:
    print("\n✅ Tất cả Mã NĐT đều có rule mapping.")

# ── 5. Kết luận ──
print(f"\n{'=' * 90}")
print("KẾT LUẬN")
print(f"{'=' * 90}")

for pgd in DS_KIEM_TRA:
    sub = df_gqvl_dp[df_gqvl_dp["Tên PGD"] == pgd]
    if sub.empty:
        print(f"\n{pgd}: KHÔNG có GQVL ĐP — không cần cap_xa")
        continue
    
    xa_tinh = sub[sub["cap"] == "tinh"]["Tên xã"].unique()
    xa_xa = sub[sub["cap"] == "xa"]["Tên xã"].unique()
    
    print(f"\n{pgd}:")
    print(f"   Xã cấp tỉnh (phân tầng): {len(xa_tinh)} xã — {list(xa_tinh) if len(xa_tinh) > 0 else 'không có'}")
    print(f"   Xã cấp xã (không phân tầng): {len(xa_xa)} xã — {list(xa_xa) if len(xa_xa) > 0 else 'không có'}")

# ── 6. So sánh với PGD_XA_MAP hiện tại ──
from config import PGD_XA_MAP
print(f"\n{'─' * 90}")
print("SO SÁNH VỚI PGD_XA_MAP HIỆN TẠI")
print(f"{'─' * 90}")

for pgd in DS_KIEM_TRA:
    xa_trong_map = PGD_XA_MAP.get(pgd, [])
    print(f"\n{pgd}: PGD_XA_MAP có {len(xa_trong_map)} xã")
    
    # Xã trong HSTD (GQVL ĐP) nhưng không trong PGD_XA_MAP
    xa_hstd = set(df_gqvl_dp[df_gqvl_dp["Tên PGD"] == pgd]["Tên xã"].unique())
    xa_map_set = set(xa_trong_map)
    
    missing_from_map = xa_hstd - xa_map_set
    extra_in_map = xa_map_set - xa_hstd
    
    if missing_from_map:
        print(f"   ⚠️ Xã có GQVL ĐP NHƯNG KHÔNG trong PGD_XA_MAP:")
        for x in sorted(missing_from_map):
            dn = df_gqvl_dp[(df_gqvl_dp["Tên PGD"] == pgd) & (df_gqvl_dp["Tên xã"] == x)]["Tổng dư nợ"].sum()
            caps = df_gqvl_dp[(df_gqvl_dp["Tên PGD"] == pgd) & (df_gqvl_dp["Tên xã"] == x)]["cap"].unique()
            print(f"     {x:25s}  dư_nợ={dn:>15,.0f}  cap={caps}")
    else:
        print(f"   ✅ Tất cả xã GQVL ĐP đều có trong PGD_XA_MAP")
    
    if extra_in_map:
        print(f"   📋 Xã trong PGD_XA_MAP nhưng không có GQVL ĐP trong HSTD: {sorted(extra_in_map)}")
