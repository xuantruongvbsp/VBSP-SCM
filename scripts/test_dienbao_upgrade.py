"""Test nhanh các hàm nâng cấp Điện báo."""
import sys
sys.path.insert(0, r"D:\VBSP-SCM")

from data.hstd import doc_dienbao, doc_dienbao_matrix, liet_ke_sheet_dienbao, db_lookup

fp = r"D:\VBSP-SCM\docs\MAU BAO CAO KHNV\DIEN BAO NGAY CN.xlsx"

print("=== Test liet_ke_sheet_dienbao ===")
sheets = liet_ke_sheet_dienbao(fp)
for s in sheets:
    print(f"  {s['sheet']}: {s['format']}, {s['n_don_vi']} dv, {s['rows']} rows")

print("\n=== Test doc_dienbao_matrix (DB1) ===")
data = doc_dienbao_matrix(fp, 0, sheet_name="DB1")
print(f"  Units ({len(data['units'])}): {data['units'][:5]}...")
print(f"  Ngay: {data['ngay_bao_cao']}")
print(f"  Rows: {len(data['rows'])}")
for r in data["rows"][:8]:
    print(f"    {r['ten']}: {r['val']:,.0f}")

print("\n=== Test doc_dienbao_matrix (M) ===")
data2 = doc_dienbao_matrix(fp, 0, sheet_name="M")
print(f"  Units: {len(data2['units'])}")
print(f"  Ngay: {data2['ngay_bao_cao']}")
for r in data2["rows"][:5]:
    print(f"    {r['ten']}: {r['val']:,.0f}")

print("\n=== Test doc_dienbao (DB1) ===")
rows = doc_dienbao(fp, 0, sheet_name="DB1")
print(f"  Rows: {len(rows)}")
for r in rows[:8]:
    print(f"    {r['ten']}: {r['val']:,.0f}")

print("\n=== Test db_lookup ===")
for key in ["Tổng dư nợ", "Dư nợ Kế hoạch A", "Dư nợ hộ nghèo KHA", "Dư nợ GQVL KHA", "Dư nợ HSSV"]:
    val = db_lookup(rows, key)
    print(f"  {key}: {val:,.0f}")

print("\n=== ALL TESTS PASSED ===")
