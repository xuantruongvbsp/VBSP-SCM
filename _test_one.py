import pandas as pd
from pathlib import Path
import os, time

with open('d:/VBSP-SCM/_merge_log.txt', 'w', encoding='utf-8') as log:
    try:
        log.write(f"Start: {time.strftime('%H:%M:%S')}\n")
        path = Path('d:/VBSP-SCM/pgd_data/pgd_binh_long/hstd_khnv.xlsx')
        log.write(f"Path: {path} | Exists: {path.exists()}\n")
        log.flush()
        
        df = pd.read_excel(str(path), sheet_name='BCQUERY', header=4)
        log.write(f"Shape: {df.shape}\n")
        df2 = df.iloc[:, 1:].dropna(how='all')
        log.write(f"After clean: {df2.shape}\n")
        log.write("SUCCESS\n")
    except Exception as e:
        log.write(f"ERROR: {e}\n")
        import traceback
        log.write(traceback.format_exc())
