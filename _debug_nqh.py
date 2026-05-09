import os, sys, pandas as pd
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

path = r'c:\VBSP-SCM\cache\hstd.parquet'
if not os.path.exists(path):
    print("No parquet cache at", path)
    sys.exit(0)

df = pd.read_parquet(path)
nqh_cols = [c for c in df.columns if any(k in c.lower() for k in ['nq','chuy','qua han','qua_h','cqh','no_'])]
print("Relevant columns:")
for c in nqh_cols:
    print(f"  '{c}': {df[c].dtype}")
print(f"\nTotal columns: {len(df.columns)}, rows: {len(df)}")

cot = "D\u01b0 n\u1ee3 qu\u00e1 h\u1ea1n"
if cot in df.columns:
    s = pd.to_numeric(df[cot], errors="coerce").fillna(0)
    print(f"\n'{cot}' min={s.min()} max={s.max()} >0 count={(s>0).sum()}")
else:
    similar = [c for c in df.columns if 'du' in c.lower() or 'qua' in c.lower()]
    print(f"\nColumn NOT found. Similar: {similar[:10]}")

print("\n--- Check specific columns ---")
targets = ["Chuy\u1ec3n QH trong th\u00e1ng", "CQH trong Qu\u00fd", "CQH N\u0103m",
           "Ng\u00e0y s\u1ed1 li\u1ec7u", "Ng\u00e0y chuy\u1ec3n QH", "Ng\u00e0y ph\u00e1t sinh NQH",
           "Ng\u00e0y \u0110H theo h\u1ee3p \u0111\u1ed3ng", "Ng\u00e0y \u0110H theo Gia h\u1ea1n",
           "Ng\u00e0y \u0110H theo GDXA"]
for t in targets:
    if t in df.columns:
        print(f"  '{t}' EXISTS")
    else:
        print(f"  '{t}' NOT in data")

print("\n--- First 120 columns ---")
for i, c in enumerate(df.columns[:120]):
    print(f"  [{i}] '{c}'")
