"""Smoke test: verify all critical modules import correctly after changes."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

errors = []

def check(label, ok, detail=""):
    if ok:
        print(f"  OK  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        errors.append((label, detail))

# 1. Core modules
print("\n1. Core modules")
try:
    import auth
    check("auth.get_permissions(admin_cn)", True)
    perms = auth.get_permissions("admin_cn")
    check("admin_cn can_edit_khtd", perms.get("can_edit_khtd") is True)
except Exception as e:
    check("auth", False, str(e))

try:
    import config
    check("config.DS_PGD has entries", len(config.DS_PGD) > 0)
    check("config.PGD_XA_MAP has entries", len(config.PGD_XA_MAP) > 0)
except Exception as e:
    check("config", False, str(e))

try:
    from utils import fmt
    result = fmt(1500)
    check("utils.fmt(1500) works", isinstance(result, str))
except Exception as e:
    check("utils", False, str(e))

# 2. tab_khtd.py - nhóm chương trình mới
print("\n2. tab_khtd.py (group definitions)")
try:
    from tabs import tab_khtd
    groups = tab_khtd.KHTD_CN_NHOM_MA_CT
    group_names = [n for n, _ in groups]
    check("5 groups defined", len(groups) == 5, f"got {len(groups)}")
    check("Group 'DTTS' exists", any("DTTS" in n for n in group_names))
    check("Group 'Vung kho khan' exists", any("khó khăn" in n for n in group_names))
    for name, codes in groups:
        if "HSSV" in name:
            check("Ma 4 NOT in HSSV group", 4 not in codes)
        if "DTTS" in name:
            check("Ma 4 in DTTS group", 4 in codes)
            check("Ma 7 in DTTS group", 7 in codes)
            check("Ma 17 in DTTS group", 17 in codes)
            check("Ma 21 in DTTS group", 21 in codes)
            check("Ma 25 in DTTS group", 25 in codes)
except Exception as e:
    import traceback
    check("tab_khtd", False, traceback.format_exc())

# 3. tab_khtd_nhap.py (syntax check)
print("\n3. tab_khtd_nhap.py syntax")
import py_compile
try:
    py_compile.compile("tabs/tab_khtd_nhap.py", doraise=True)
    check("tab_khtd_nhap.py syntax OK", True)
except py_compile.PyCompileError as e:
    check("tab_khtd_nhap.py", False, str(e))

# 4. pdf_service
print("\n4. pdf_service")
try:
    from pdf_service import xuat_pdf_bang
    check("xuat_pdf_bang available", callable(xuat_pdf_bang))
except Exception as e:
    check("pdf_service", False, str(e))

# 5. app.py syntax
print("\n5. app.py syntax")
try:
    py_compile.compile("app.py", doraise=True)
    check("app.py syntax OK", True)
except py_compile.PyCompileError as e:
    check("app.py", False, str(e))

# 6. ws_operation.py syntax
print("\n6. ws_operation.py syntax")
try:
    py_compile.compile("workspaces/ws_operation.py", doraise=True)
    check("ws_operation.py syntax OK", True)
except py_compile.PyCompileError as e:
    check("ws_operation.py", False, str(e))

# 7. tab_tongquan.py syntax
print("\n7. tab_tongquan.py syntax")
try:
    py_compile.compile("tabs/tab_tongquan.py", doraise=True)
    check("tab_tongquan.py syntax OK", True)
except py_compile.PyCompileError as e:
    check("tab_tongquan.py", False, str(e))

# Summary
print(f"\n{'='*40}")
if errors:
    print(f"FAILED: {len(errors)} error(s)")
    for label, detail in errors:
        print(f"  - {label}: {detail}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)
