import sys
sys.path.insert(0, 'd:/VBSP-SCM')
import db

conn = db.get_conn()
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)

if 'cdtotkvv_snapshot' in tables:
    print('cdtotkvv_snapshot EXISTS')
    cur = conn.execute("PRAGMA table_info(cdtotkvv_snapshot)")
    cols = [r[1] for r in cur.fetchall()]
    print('Columns:', cols)
    
    cur = conn.execute("SELECT DISTINCT ky FROM cdtotkvv_snapshot")
    kys = [r[0] for r in cur.fetchall()]
    print('Kys:', kys)
else:
    print('cdtotkvv_snapshot NOT EXISTS')
