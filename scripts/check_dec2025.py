"""Check for Dec 2025 baseline data."""
import sys
sys.path.insert(0, 'd:/VBSP-SCM')
import db

conn = db.get_conn()

# Check NQ11 for 2025-12
print('=== NQ11 ===')
cur = conn.execute("SELECT DISTINCT ky FROM nq11_snapshot WHERE ky LIKE '2025%'")
kys = [r[0] for r in cur.fetchall()]
print(f'2025 kys: {kys}')

cur = conn.execute("SELECT ky, ten_pgd, tong_du_no FROM nq11_snapshot WHERE ky='2025-12'")
rows = cur.fetchall()
print(f'2025-12 rows: {len(rows)}')
for r in rows[:3]:
    print(f'  {r}')

# Check GQVL for 2025-12
print('\n=== GQVL ===')
cur = conn.execute("SELECT DISTINCT ky FROM gqvl_snapshot WHERE ky LIKE '2025%'")
kys = [r[0] for r in cur.fetchall()]
print(f'2025 kys: {kys}')

cur = conn.execute("SELECT ky, ten_pgd, dn_th FROM gqvl_snapshot WHERE ky='2025-12'")
rows = cur.fetchall()
print(f'2025-12 rows: {len(rows)}')
for r in rows[:3]:
    print(f'  {r}')

# Check all years
print('\n=== ALL KYs ===')
for table in ['nq11_snapshot', 'gqvl_snapshot', 'cdtotkvv_snapshot']:
    cur = conn.execute(f"SELECT DISTINCT ky FROM {table} ORDER BY ky")
    all_kys = [r[0] for r in cur.fetchall()]
    print(f'{table}: {all_kys}')
