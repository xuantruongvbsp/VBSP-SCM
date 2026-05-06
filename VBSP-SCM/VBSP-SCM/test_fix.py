import warnings
warnings.filterwarnings('ignore')
import pandas as pd
from config import GQVL_COT_MAP
from services.data_quality import kiem_tra_chat_luong

df_hstd = pd.read_excel('HSTD_Du_lieu_tho.XLSX', sheet_name='BCQUERY', header=4)
df_hstd = df_hstd.iloc[:, 1:].dropna(how='all')

df_nq11 = pd.read_excel('SAO_KE_CT__NQ11_du_lieu_tho.XLSX', sheet_name='BCQUERY', header=4)
df_nq11 = df_nq11.iloc[:, 1:].dropna(how='all')

df_gqvl = pd.read_excel('SK_GQVL_004606_25042026.xlsx', sheet_name='Sheet1', header=7)
df_gqvl = df_gqvl.iloc[:, 1:].dropna(how='all').iloc[1:].rename(columns=GQVL_COT_MAP).reset_index(drop=True)

for loai, df in [('hstd', df_hstd), ('nq11', df_nq11), ('gqvl', df_gqvl)]:
    r = kiem_tra_chat_luong(df, loai)
    status = 'PASS' if r.is_valid else 'FAIL'
    print(f'{status} {loai.upper()} | {r.report["so_loi"]} loi | {r.report["ti_le_dat_chuan"]}%')
    for err in r.errors:
        print(f'  {err}')