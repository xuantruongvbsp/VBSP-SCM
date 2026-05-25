"""Check baseline data storage."""
import sys
sys.path.insert(0, 'd:/VBSP-SCM')
import db

conn = db.get_conn()

# Check all tables with 'baseline' or '12' in name
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('All tables:', tables)

# Check kv_store for baseline
cur = conn.execute("SELECT key, value FROM kv_store WHERE key LIKE '%baseline%' OR key LIKE '%2025%' OR key LIKE '%2024%'")
rows = cur.fetchall()
print(f'\nKV store matches: {len(rows)}')
for r in rows[:10]:
    print(f'  {r[0]}: {str(r[1])[:50]}...')

# Check if there's any data with 2024 or 2025
cur = conn.execute("SELECT key FROM kv_store WHERE key LIKE '%nq11%' OR key LIKE '%gqvl%'")
keys = [r[0] for r in cur.fetchall()]
print(f'\nNQ11/GQVL related keys in kv_store: {keys}')
