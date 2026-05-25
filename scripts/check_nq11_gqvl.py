"""Check NQ11 and GQVL snapshot data."""
import sys
sys.path.insert(0, 'd:/VBSP-SCM')
import db

conn = db.get_conn()

# Check tables exist
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('All tables:', [t for t in tables if 'snapshot' in t or t in ['nq11_snapshot', 'gqvl_snapshot', 'cdtotkvv_snapshot']])

# Check NQ11
if 'nq11_snapshot' in tables:
    print('\n=== NQ11 SNAPSHOT ===')
    cur = conn.execute("PRAGMA table_info(nq11_snapshot)")
    cols = [r[1] for r in cur.fetchall()]
    print('Columns:', cols)
    
    cur = conn.execute("SELECT DISTINCT ky FROM nq11_snapshot")
    kys = [r[0] for r in cur.fetchall()]
    print(f'Kys: {kys}')
    
    cur = conn.execute("SELECT COUNT(*) as cnt FROM nq11_snapshot")
    cnt = cur.fetchone()[0]
    print(f'Total rows: {cnt}')
    
    # Check ten_pgd values
    cur = conn.execute("SELECT DISTINCT ten_pgd FROM nq11_snapshot LIMIT 5")
    pgds = [r[0] for r in cur.fetchall()]
    print(f'Sample ten_pgd: {pgds}')
else:
    print('\n=== NQ11 SNAPSHOT: NOT EXISTS ===')

# Check GQVL
if 'gqvl_snapshot' in tables:
    print('\n=== GQVL SNAPSHOT ===')
    cur = conn.execute("PRAGMA table_info(gqvl_snapshot)")
    cols = [r[1] for r in cur.fetchall()]
    print('Columns:', cols)
    
    cur = conn.execute("SELECT DISTINCT ky FROM gqvl_snapshot")
    kys = [r[0] for r in cur.fetchall()]
    print(f'Kys: {kys}')
    
    cur = conn.execute("SELECT COUNT(*) as cnt FROM gqvl_snapshot")
    cnt = cur.fetchone()[0]
    print(f'Total rows: {cnt}')
    
    cur = conn.execute("SELECT DISTINCT ten_pgd FROM gqvl_snapshot LIMIT 5")
    pgds = [r[0] for r in cur.fetchall()]
    print(f'Sample ten_pgd: {pgds}')
else:
    print('\n=== GQVL SNAPSHOT: NOT EXISTS ===')
