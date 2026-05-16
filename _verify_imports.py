#!/usr/bin/env python3
import sys, os
sys.path.insert(0, 'D:\\VBSP-SCM')
os.chdir('D:\\VBSP-SCM')

errors = []

def test(name, fn):
    try:
        fn()
        print(f"  OK: {name}")
    except Exception as e:
        errors.append(name)
        print(f"  FAIL: {name} -> {e}")

print("=" * 60)
print("VERIFICATION 1: pdf_service root imports")
print("=" * 60)
test("xuat_pdf", lambda: __import__("pdf_service", fromlist=["xuat_pdf"]))
test("xuat_pdf_bao_cao", lambda: __import__("pdf_service", fromlist=["xuat_pdf_bao_cao"]))
test("xuat_pdf_group_header", lambda: __import__("pdf_service", fromlist=["xuat_pdf_group_header"]))
test("xuat_pdf_bang", lambda: __import__("pdf_service", fromlist=["xuat_pdf_bang"]))
test("nut_xuat_pdf", lambda: __import__("pdf_service", fromlist=["nut_xuat_pdf"]))
test("render_huong_dan", lambda: __import__("pdf_service", fromlist=["render_huong_dan"]))
test("kiem_tra_pdf_dependency", lambda: __import__("pdf_service", fromlist=["kiem_tra_pdf_dependency"]))
test("_dang_ky_font", lambda: __import__("pdf_service", fromlist=["_dang_ky_font"]))

# Actually run kiem_tra_pdf_dependency
from pdf_service import kiem_tra_pdf_dependency
dep = kiem_tra_pdf_dependency()
print(f"  pdf_service dependency check: {dep}")

print()
print("=" * 60)
print("VERIFICATION 2: Workspace imports (via pdf_service)")
print("=" * 60)
test("ws_operation", lambda: __import__("workspaces.ws_operation"))
test("ws_management", lambda: __import__("workspaces.ws_management"))
test("ws_executive", lambda: __import__("workspaces.ws_executive"))

print()
print("=" * 60)
print("VERIFICATION 3: gen_dcgiam_sheet")
print("=" * 60)
test("gen_dcgiam_sheet", lambda: __import__("gen_dcgiam_sheet"))
test("_phan_loai_4_nhom", lambda: __import__("gen_dcgiam_sheet", fromlist=["_phan_loai_4_nhom"]))

print()
print("=" * 60)
print("VERIFICATION 4: Tab imports (use pdf_service)")
print("=" * 60)
test("tab_tongquan", lambda: __import__("tabs.tab_tongquan"))
test("tab_baocao", lambda: __import__("tabs.tab_baocao"))
test("tab_tracuu", lambda: __import__("tabs.tab_tracuu"))
test("tab_den_han", lambda: __import__("tabs.tab_den_han"))
test("tab_khtd", lambda: __import__("tabs.tab_khtd"))
test("tab_khtd_nhap", lambda: __import__("tabs.tab_khtd_nhap"))
test("tab_khtd_xuat", lambda: __import__("tabs.tab_khtd_xuat"))
test("tab_tien_do", lambda: __import__("tabs.tab_tien_do"))
test("tab_kh_gqvl", lambda: __import__("tabs.tab_kh_gqvl"))

print()
print("=" * 60)
print("VERIFICATION 5: Service imports (use pdf_service)")
print("=" * 60)
test("kiem_soat_service (services)", lambda: __import__("services.kiem_soat_service"))
test("kiem_soat_service (tabs)", lambda: __import__("tabs.kiem_soat_service"))

print()
print("=" * 60)
print("VERIFICATION 6: Config file paths exist")
print("=" * 60)
from config import (
    FILE_PATH, FILE_PATH_NQ11, FILE_PATH_DB, FILE_PATH_DB_PREV,
    PGD_DATA_DIR, CACHE_DIR, CACHE_HSTD, CACHE_NQ11
)
for name, path in [("FILE_PATH", FILE_PATH), ("FILE_PATH_NQ11", FILE_PATH_NQ11),
                    ("FILE_PATH_DB", FILE_PATH_DB), ("FILE_PATH_DB_PREV", FILE_PATH_DB_PREV)]:
    if os.path.exists(path):
        print(f"  OK: {name} -> {path} (exists)")
    else:
        print(f"  WARN: {name} -> {path} (NOT FOUND - needs upload)")
for name, path in [("PGD_DATA_DIR", PGD_DATA_DIR), ("CACHE_DIR", CACHE_DIR)]:
    if os.path.isdir(path):
        print(f"  OK: {name} -> {path} (exists)")
    else:
        errors.append(name)
        print(f"  FAIL: {name} -> {path} (NOT FOUND)")
for name, path in [("CACHE_HSTD", CACHE_HSTD), ("CACHE_NQ11", CACHE_NQ11)]:
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"  OK: {name} -> {size_mb:.1f} MB")
    else:
        print(f"  INFO: {name} (cache not built yet - will be created on first run)")

print()
print("=" * 60)
print("VERIFICATION 7: data/qd folder exists")
print("=" * 60)
qd_path = os.path.join("data", "qd")
if os.path.isdir(qd_path):
    files = os.listdir(qd_path)
    print(f"  OK: data/qd/ exists ({len(files)} items)")
else:
    print(f"  OK: data/qd/ not needed yet (will be created on upload)")
# Check subdirs
for sub in ["hdqt_tinh", "tw"]:
    sp = os.path.join(qd_path, sub)
    if os.path.isdir(sp):
        print(f"  OK: data/qd/{sub}/ exists")
    else:
        print(f"  INFO: data/qd/{sub}/ (will be created on first upload)")

print()
print("=" * 60)
if errors:
    print(f"FAILED: {len(errors)} errors: {errors}")
    sys.exit(1)
else:
    print("ALL VERIFICATIONS PASSED")
    sys.exit(0)
