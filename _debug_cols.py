import pandas as pd
df = pd.read_parquet('d:\\VBSP-SCM\\cache\\hstd.parquet', engine='pyarrow')
cols = [c for c in df.columns if any(x in str(c).lower() for x in ['giai ngan', 'thu no', 'cho vay', 'doanh so'])]
with open('d:\\VBSP-SCM\\_debug_cols_output.txt', 'w', encoding='utf-8') as f:
    f.write("Found cols: " + str(cols) + "\n")
    f.write("All cols: " + str(list(df.columns)) + "\n")
