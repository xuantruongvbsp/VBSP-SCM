import pandas as pd, sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

try:
    print("Reading Excel...", flush=True)
    df = pd.read_excel(
        'd:/VBSP-SCM/pgd_data/hoi_so_chi_nhanh_tinh/hstd_latest.xlsx',
        sheet_name='BCQUERY',
        header=4
    )
    print('Shape:', df.shape, flush=True)
    print('Cols:', list(df.columns[:5]), flush=True)
    
    col1 = df.columns[1]
    print('Col 1 name:', col1, flush=True)
    vals = sorted(df.iloc[:, 1].dropna().unique())
    print('Unique values:', len(vals), flush=True)
    print('First 10:', vals[:10], flush=True)
    
    pgd_cols = [c for c in df.columns if 'PGD' in str(c)]
    print('PGD cols:', pgd_cols, flush=True)
    for c in pgd_cols:
        print(c + ': ', sorted(df[c].dropna().unique())[:5], flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
    import traceback
    traceback.print_exc()
