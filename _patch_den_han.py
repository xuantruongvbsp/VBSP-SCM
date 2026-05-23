"""Patch data/den_han.py: fix canh_bao_tap_trung to accept den_thang param."""
import pathlib

p = pathlib.Path(__file__).parent / "data" / "den_han.py"
txt = p.read_text(encoding="utf-8")

OLD_SIG = "def canh_bao_tap_trung(df, nguong_ty_le=0.30) -> list[dict]:"
NEW_SIG = "def canh_bao_tap_trung(df, nguong_ty_le=0.30, den_thang: int = 6) -> list[dict]:"

OLD_LOC = "    df_loc = loc_den_han_trong(df, tu_thang=0, den_thang=6)"
NEW_LOC = "    df_loc = loc_den_han_trong(df, tu_thang=0, den_thang=den_thang)"

OLD_GROUP_BLOCK = (
    "    canh_bao_list = []\n"
    "    grouped = df_loc.groupby([COT_TEN_PGD, \"T\u00e1ng \u0111\u1ebfn h\u1ea1n c\u00f2n l\u1ea1i\"])\n"
    "\n"
    "    today = date.today()\n"
    "    for (ten_pgd, thang_con_lai), grp in grouped:\n"
    "        tong_den_han = grp[COT_TONG_DU_NO].sum()\n"
    "        tong_pgd_val = tong_pgd.get(ten_pgd, 0)\n"
    "        if tong_pgd_val <= 0:\n"
    "            continue\n"
    "        ty_le = tong_den_han / tong_pgd_val\n"
    "        if ty_le >= nguong_ty_le:\n"
    "            thang_str = (today + relativedelta(months=int(thang_con_lai))).strftime(\"T\u00e1ng %m/%Y\")\n"
    "            canh_bao_list.append({\n"
    "                \"pgd\": ten_pgd,\n"
    "                \"thang\": thang_str,\n"
    "                \"thang_con_lai\": int(thang_con_lai),\n"
    "                \"so_khoan\": int(len(grp)),\n"
    "                \"tong_den_han\": int(tong_den_han),\n"
    "                \"tong_pgd\": int(tong_pgd_val),\n"
    "                \"ty_le\": float(ty_le),\n"
    "                \"muc_do\": \"high\" if ty_le >= 0.50 else \"medium\",\n"
    "            })"
)

NEW_GROUP_BLOCK = (
    "    canh_bao_list = []\n"
    "    grouped = df_loc.groupby(COT_TEN_PGD)\n"
    "\n"
    "    today = date.today()\n"
    "    thang_str = f\"trong {den_thang} th\u00e1ng t\u1edbi\"\n"
    "    for ten_pgd, grp in grouped:\n"
    "        tong_den_han = grp[COT_TONG_DU_NO].sum()\n"
    "        tong_pgd_val = tong_pgd.get(ten_pgd, 0)\n"
    "        if tong_pgd_val <= 0:\n"
    "            continue\n"
    "        ty_le = tong_den_han / tong_pgd_val\n"
    "        if ty_le >= nguong_ty_le:\n"
    "            canh_bao_list.append({\n"
    "                \"pgd\": ten_pgd,\n"
    "                \"thang\": thang_str,\n"
    "                \"thang_con_lai\": den_thang,\n"
    "                \"so_khoan\": int(len(grp)),\n"
    "                \"tong_den_han\": int(tong_den_han),\n"
    "                \"tong_pgd\": int(tong_pgd_val),\n"
    "                \"ty_le\": float(ty_le),\n"
    "                \"muc_do\": \"high\" if ty_le >= 0.50 else \"medium\",\n"
    "            })"
)

assert OLD_SIG in txt, "FAIL: signature not found"
assert OLD_LOC in txt, "FAIL: loc line not found"

txt = txt.replace(OLD_SIG, NEW_SIG, 1)
txt = txt.replace(OLD_LOC, NEW_LOC, 1)

# Replace groupby block — find exact Vietnamese string
old_grp_line = '    grouped = df_loc.groupby([COT_TEN_PGD, "T\u00e1ng \u0111\u1ebfn h\u1ea1n c\u00f2n l\u1ea1i"])'
if old_grp_line not in txt:
    # try actual unicode from file
    import re
    # find the groupby line dynamically
    m = re.search(r'    grouped = df_loc\.groupby\(\[COT_TEN_PGD[^\n]+\n', txt)
    if m:
        old_grp_actual = m.group(0).rstrip('\n')
        print(f"Found groupby line: {repr(old_grp_actual)}")
        txt = txt.replace(
            old_grp_actual,
            '    grouped = df_loc.groupby(COT_TEN_PGD)',
            1
        )
    else:
        print("FAIL: groupby line not found by regex either")
        import sys; sys.exit(1)
else:
    txt = txt.replace(old_grp_line, '    grouped = df_loc.groupby(COT_TEN_PGD)', 1)

# Replace loop header and thang_str
old_loop = '    for (ten_pgd, thang_con_lai), grp in grouped:'
new_loop_block = '    thang_str = f"trong {den_thang} th\u00e1ng t\u1edbi"\n    for ten_pgd, grp in grouped:'
assert old_loop in txt, "FAIL: loop header not found"
txt = txt.replace(old_loop, new_loop_block, 1)

# Remove the thang_str line inside the loop (old one computing from relativedelta)
import re
txt = re.sub(
    r"            thang_str = \(today \+ relativedelta\(months=int\(thang_con_lai\)\)\)\.strftime\([^\n]+\)\n",
    "",
    txt,
)

# Fix thang_con_lai refs inside the appended dict
txt = txt.replace(
    '                "thang_con_lai": int(thang_con_lai),',
    '                "thang_con_lai": den_thang,',
    1
)

p.write_text(txt, encoding="utf-8")
print("den_han.py patched OK")
