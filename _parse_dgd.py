import pandas as pd, json, re

df = pd.read_excel('danh sách điểm giao dịch đồng nai.xlsx', header=None)
data = df.iloc[2:].copy()
data.columns = ['stt','ten_dgd','xa','pgd','tinh','ngay_gd','gio_gd','dia_diem','ngay_hl']
def is_pos_int(x):
    try:
        return int(str(x).strip()) > 0
    except Exception:
        return False

data = data[data['stt'].apply(is_pos_int)]
data = data.reset_index(drop=True)

def norm_pgd(s):
    s = str(s).strip()
    if 'Hội sở tỉnh' in s or 'Hội sở Chi nhánh' in s:
        return 'Hội sở Chi nhánh tỉnh'
    return s

def norm_xa(s):
    s = str(s).strip()
    # Thêm prefix "Phường " hoặc "Xã " nếu chưa có
    prefixes = ('Phường ', 'Xã ', 'Thị trấn ', 'Thị xã ')
    for p in prefixes:
        if s.startswith(p):
            return s
    # Tra ngược từ PGD_XA_MAP
    return s  # giữ nguyên — sẽ match bằng khop_xa_dgd

rows = []
for _, r in data.iterrows():
    stt = int(str(r['stt']).strip())
    ten = str(r['ten_dgd']).strip()
    xa = str(r['xa']).strip()
    pgd = norm_pgd(r['pgd'])
    ngay_gd_raw = r['ngay_gd']
    ngay = str(int(float(str(ngay_gd_raw)))) if pd.notna(ngay_gd_raw) and str(ngay_gd_raw).strip() not in ('', 'nan') else ''
    gio = str(r['gio_gd']).strip() if pd.notna(r['gio_gd']) else ''
    dia = str(r['dia_diem']).strip() if pd.notna(r['dia_diem']) else ''
    rows.append({'stt': stt, 'ten': ten, 'xa': xa, 'pgd': pgd, 'ngay_gd': ngay, 'gio_gd': gio, 'dia_diem': dia})

print(f'Total rows: {len(rows)}')
print('PGDs:', sorted(set(r['pgd'] for r in rows)))
print()
for r in rows[:5]:
    print(r)

# Generate Python code
lines = ['DGD_DANH_SACH: list[dict] = [']
for r in rows:
    lines.append(
        f'    {{"stt": {r["stt"]}, "ten": "{r["ten"]}", "xa": "{r["xa"]}", '
        f'"pgd": "{r["pgd"]}", "ngay_gd": "{r["ngay_gd"]}", '
        f'"gio_gd": "{r["gio_gd"]}", "dia_diem": "{r["dia_diem"]}"}},'
    )
lines.append(']')
code = '\n'.join(lines)
with open('_dgd_danh_sach_generated.txt', 'w', encoding='utf-8') as f:
    f.write(code)
print(f'\nGenerated {len(rows)} entries → _dgd_danh_sach_generated.txt')

# ── Append vào config.py ─────────────────────────────────────────────────────
helpers = '''

def lay_dgd_cho_pgd(pgd: str) -> list[dict]:
    """Trả về danh sách ĐGD thuộc một PGD."""
    return [d for d in DGD_DANH_SACH if d["pgd"] == pgd]


def lay_dgd_theo_xa(xa_short: str) -> list[dict]:
    """Trả về danh sách ĐGD thuộc một xã (khớp tên ngắn, không phân biệt hoa/thường)."""
    xa_norm = xa_short.strip().lower()
    return [d for d in DGD_DANH_SACH if d["xa"].strip().lower() == xa_norm]
'''

header = "\n\n# ── Danh sách 270 Điểm Giao Dịch Xã (nguồn: danh sách ĐGD Đồng Nai) ──────\n"
block = header + code + helpers

config_path = 'config.py'
existing = open(config_path, encoding='utf-8').read()

if 'DGD_DANH_SACH' in existing:
    print('DGD_DANH_SACH already in config.py — skip append')
else:
    with open(config_path, 'a', encoding='utf-8') as f:
        f.write(block)
    print(f'Appended DGD_DANH_SACH + helpers to config.py')

# Verify compile
import py_compile
py_compile.compile(config_path, doraise=True)
print('config.py compile OK')
