import sys 
sys.path.insert(0, '.') 
from db import get_conn 
import json 
conn = get_conn() 
row = conn.execute("SELECT value FROM kv_store WHERE key='merge_meta_hstd'").fetchone() 
if row: 
    data = json.loads(row[0]) 
    print('pgd_list:', data.get('pgd_list', [])) 
    print('row_count:', data.get('row_count', 0)) 
else: print('Khong co merge_meta_hstd') 
