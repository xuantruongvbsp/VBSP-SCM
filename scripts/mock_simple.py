"""Simple mock data generator."""
import sys
sys.path.insert(0, 'd:/VBSP-SCM')

print('Importing modules...')
try:
    import db
    print('db imported')
except Exception as e:
    print(f'Error importing db: {e}')
    sys.exit(1)

ky_target = '2025-12'

print(f'Creating data for {ky_target}...')

with db.get_conn() as conn:
    # Get existing PGD list
    cur = conn.execute("SELECT DISTINCT ten_pgd FROM cdtotkvv_snapshot WHERE ky='2026-05'")
    pgds = [r[0] for r in cur.fetchall()]
    print(f'Found PGDs: {pgds}')
    
    rows = []
    for pgd in pgds:
        # Mock data for Dec 2025 (lower than May 2026)
        so_to = 45
        so_tot = 12
        so_kha = 18
        so_tb = 10
        so_yeu = 5
        diem_tb = 72.5
        
        rows.append((ky_target, pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb, 'mock'))
    
    print(f'Inserting {len(rows)} rows...')
    conn.executemany('''
        INSERT OR REPLACE INTO cdtotkvv_snapshot
        (ky, ten_pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb, created_by)
        VALUES (?,?,?,?,?,?,?,?,?)
    ''', rows)
    conn.commit()
    print('Done!')

# Verify
print('Verifying...')
cur = conn.execute("SELECT DISTINCT ky FROM cdtotkvv_snapshot")
all_kys = [r[0] for r in cur.fetchall()]
print(f'All kys: {all_kys}')
