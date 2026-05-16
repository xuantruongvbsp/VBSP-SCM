import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_parquet('d:\\VBSP-SCM\\cache\\hstd.parquet')
cols = list(df.columns)
# Print column names that contain specific keywords
for c in cols:
    cu = c.upper()
    if 'CB' in cu or 'CAN' in cu or 'TO' in cu or 'DIEN' in cu or 'THOAI' in cu or 'SDT' in cu or 'QL' in cu:
        print(repr(c))
print('---TOTAL COLS:', len(cols))
print([c for c in cols[:20]])
