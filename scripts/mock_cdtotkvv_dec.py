"""Tao du lieu CDTOTKVV thang 12-2025 de test so sanh moc nam."""
import sys
sys.path.insert(0, 'd:/VBSP-SCM')

import db
from snapshot_service import danh_sach_ky_cdtotkvv

ky_target = '2025-12'
ky_base = '2026-05'

# Check existing
existing = danh_sach_ky_cdtotkvv()
print(f'Existing ky: {existing}')

if ky_target in existing:
    print(f'Ky {ky_target} da ton tai, bo qua')
    sys.exit(0)

# Tao data tu 2026-05
with db.get_conn() as conn:
    cur = conn.execute('SELECT * FROM cdtotkvv_snapshot WHERE ky=?', (ky_base,))
    base_data = cur.fetchall()
    
    if not base_data:
        print(f'Khong co du lieu {ky_base}')
        sys.exit(1)
    
    print(f'Co {len(base_data)} rows cho {ky_base}')
    
    rows = []
    for row in base_data:
        row_dict = dict(row)
        so_to = max(5, int(row_dict.get('so_to', 50) * 0.85))
        so_tot = max(2, int(row_dict.get('so_tot', 15) * 0.80))
        so_kha = max(3, int(row_dict.get('so_kha', 20) * 0.85))
        so_tb = max(1, int(row_dict.get('so_tb', 10) * 0.90))
        so_yeu = max(1, int(row_dict.get('so_yeu', 5) * 1.1))
        # Cột là diem_tb chứ không phải tl_tot_kha
        diem_tb = (so_tot * 90 + so_kha * 80 + so_tb * 60 + so_yeu * 40) / so_to if so_to > 0 else 0
        
        rows.append((
            ky_target,
            row_dict['ten_pgd'],
            so_to,
            so_tot,
            so_kha,
            so_tb,
            so_yeu,
            round(diem_tb, 2),
            'mock_data'
        ))
    
    conn.executemany('''
        INSERT OR REPLACE INTO cdtotkvv_snapshot
        (ky, ten_pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb, created_by)
        VALUES (?,?,?,?,?,?,?,?,?)
    ''', rows)
    conn.commit()
    print(f'Da tao {len(rows)} rows cho CDTOTKVV ky {ky_target}')

# Verify
from snapshot_service import danh_sach_ky_cdtotkvv
print(f'Sau khi tao: {danh_sach_ky_cdtotkvv()}')
