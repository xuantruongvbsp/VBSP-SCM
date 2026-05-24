"""Script: cập nhật data/dgd_helpers.py — xóa parse_excel_import, thêm xa_short + khop_xa_dgd."""
import re

path = 'data/dgd_helpers.py'
src = open(path, encoding='utf-8').read()

# ── 1. Xóa import BytesIO (chỉ dùng bởi parse_excel_import) ─────────────────
src = src.replace('from io import BytesIO\n', '')

# ── 2. Xóa hàm parse_excel_import (từ def đến hết return) ───────────────────
# Tìm block hàm bằng regex: từ "def parse_excel_import" đến dòng trống tiếp theo sau return
pattern = r'\n\ndef parse_excel_import\(.*?\n(?=\n\ndef )'
match = re.search(pattern, src, flags=re.DOTALL)
if match:
    src = src[:match.start()] + src[match.end() - 2:]  # giữ \n\n trước hàm tiếp theo
    print('Removed parse_excel_import OK')
else:
    print('WARNING: parse_excel_import not found by regex — trying manual approach')
    # Fallback: tìm theo dòng
    lines = src.splitlines(keepends=True)
    start_i = None
    end_i = None
    for i, line in enumerate(lines):
        if line.strip().startswith('def parse_excel_import('):
            start_i = i
        if start_i is not None and i > start_i + 2:
            # Hàm kết thúc khi gặp dòng trống + "def " tiếp theo
            if line.strip().startswith('def ') or (line.strip() == '' and i + 1 < len(lines) and lines[i+1].strip().startswith('def ')):
                end_i = i
                break
    if start_i is not None and end_i is not None:
        # Lùi về để xóa 2 dòng trống trước hàm
        if start_i >= 2 and lines[start_i-1].strip() == '' and lines[start_i-2].strip() == '':
            start_i -= 2
        elif start_i >= 1 and lines[start_i-1].strip() == '':
            start_i -= 1
        src = ''.join(lines[:start_i]) + ''.join(lines[end_i:])
        print(f'Removed parse_excel_import (manual, lines {start_i}-{end_i})')
    else:
        print(f'ERROR: could not locate parse_excel_import, start={start_i}, end={end_i}')

# ── 3. Thêm xa_short + khop_xa_dgd sau _split_ap_cell ───────────────────────
new_funcs = '''

def xa_short(ten_xa_full: str) -> str:
    """Bỏ prefix 'Xã '/'Phường '/'Thị trấn '/'Thị xã ' → trả tên ngắn."""
    s = str(ten_xa_full).strip()
    for prefix in ("Thị trấn ", "Thị xã ", "Phường ", "Xã "):
        if s.startswith(prefix):
            return s[len(prefix):]
    return s


def khop_xa_dgd(ten_xa_full: str, dgd_xa: str) -> bool:
    """So sánh tên xã đầy đủ (từ PGD_XA_MAP) với tên xã ngắn trong DGD_DANH_SACH."""
    return xa_short(ten_xa_full).strip().lower() == str(dgd_xa).strip().lower()
'''

# Chèn sau hàm _split_ap_cell (trước parse_excel_import cũ — nay đã xóa, chèn trước dem_thong_ke)
insert_before = '\ndef dem_thong_ke('
if insert_before in src:
    idx = src.index(insert_before)
    src = src[:idx] + new_funcs + src[idx:]
    print('Inserted xa_short + khop_xa_dgd OK')
else:
    # fallback: append trước pool_thon_cho_xa
    insert_before2 = '\ndef pool_thon_cho_xa('
    if insert_before2 in src:
        idx = src.index(insert_before2)
        src = src[:idx] + new_funcs + src[idx:]
        print('Inserted xa_short + khop_xa_dgd (fallback) OK')
    else:
        src += new_funcs
        print('Appended xa_short + khop_xa_dgd at end')

# ── 4. Ghi lại ───────────────────────────────────────────────────────────────
with open(path, 'w', encoding='utf-8') as f:
    f.write(src)
print('Written dgd_helpers.py')

# ── 5. Compile check ─────────────────────────────────────────────────────────
import py_compile
py_compile.compile(path, doraise=True)
print('dgd_helpers.py compile OK')

# ── 6. Import check ──────────────────────────────────────────────────────────
import importlib.util, sys
spec = importlib.util.spec_from_file_location('dgd_helpers', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('xa_short("Xã Trấn Biên") =', mod.xa_short('Xã Trấn Biên'))
print('khop_xa_dgd("Phường Biên Hòa", "Biên Hòa") =', mod.khop_xa_dgd('Phường Biên Hòa', 'Biên Hòa'))
print('has parse_excel_import:', hasattr(mod, 'parse_excel_import'))
