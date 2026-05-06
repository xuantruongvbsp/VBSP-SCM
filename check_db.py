import sys 
sys.path.insert(0, '.') 
from db import get_conn 
conn = get_conn() 
rows = conn.execute("SELECT key FROM kv_store ORDER BY key").fetchall() 
[print(r[0]) for r in rows] 
