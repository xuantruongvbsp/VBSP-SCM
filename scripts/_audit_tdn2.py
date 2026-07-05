import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from config import CACHE_HSTD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_MA_KH, COT_NGUON_VON

df = pd.read_parquet(CACHE_HSTD)
for c in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH]:
    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
mask = (df[COT_TONG_DU_NO]>0)|(df[COT_DU_NO_QH]>0)|(df[COT_DU_NO_KHOANH]>0)
da = df[mask]
tdn = da[COT_TONG_DU_NO].sum()
dqh = da[COT_DU_NO_QH].sum()
dnk = da[COT_DU_NO_KHOANH].sum()
n_kh = da[COT_MA_KH].nunique() if COT_MA_KH in da.columns else 0

print('=== SO SANH BAO CAO KHNV (24/05/2026) ===')
print('Bao cao: TDN 13.219.326 trieu = 13.219 ty')
print(f'App HSTD: TDN {tdn/1e9:.3f} ty ({tdn/1e6:,.0f} trieu)')
print(f'Chenh: {(tdn/1e9 - 13.219326):.3f} ty ({(tdn/1e9/13.219326-1)*100:.2f}%)')
print()
print(f'Bao cao: 213.140 KH | App: {n_kh:,} KH')
print(f'Bao cao: QH 15.164 trieu | App QH {dqh/1e6:,.0f} trieu ({dqh/1e9:.3f} ty)')
print(f'Bao cao: Khoanh 6.775 trieu | App {dnk/1e6:,.0f} trieu')

if COT_NGUON_VON in da.columns:
    nv = pd.to_numeric(da[COT_NGUON_VON], errors='coerce').fillna(0).astype(int)
    tw = da.loc[nv==1, COT_TONG_DU_NO].sum()
    dp = da.loc[nv==2, COT_TONG_DU_NO].sum()
    khac = tdn - tw - dp
    print()
    print('=== NGUON VON (cot Nguon von) ===')
    print(f'  TW (1): {tw/1e9:.3f} ty  (bao cao 24/5: 10.608 ty)')
    print(f'  DP (2): {dp/1e9:.3f} ty  (bao cao 24/5: 2.611 ty)')
    print(f'  Khac:   {khac/1e9:.3f} ty')

# sample row magnitudes
s = da[COT_TONG_DU_NO]
print()
print('=== PHAN BO DONG ===')
print(f'  max dong ty: {s.max()/1e9:.4f}')
print(f'  median trieu: {s.median()/1e6:.1f}')
print(f'  dong > 100 ty: {(s>100e9).sum()}')
print(f'  dong < 1 trieu: {(s<1e6).sum()}')
