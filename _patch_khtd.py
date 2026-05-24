src = open('data/khtd.py', encoding='utf-8').read()

old = (
    "        for dgd_name, ap_list in dgd_block.items():\n"
    "            if dgd_name in ds_dgd:\n"
    "                for ap in (ap_list or []):\n"
    "                    ap_s = str(ap).strip()\n"
    "                    if ap_s:\n"
    "                        result.append((ten_xa, ap_s))"
)

new = (
    "        for dgd_name, ap_list in dgd_block.items():\n"
    "            if dgd_name in ds_dgd:\n"
    "                # Schema moi: ap_list co the la dict {\"thon\": [...]} hoac list cu\n"
    "                if isinstance(ap_list, dict):\n"
    "                    thon_items = ap_list.get(\"thon\", [])\n"
    "                elif isinstance(ap_list, list):\n"
    "                    thon_items = ap_list\n"
    "                else:\n"
    "                    thon_items = []\n"
    "                for ap in thon_items:\n"
    "                    ap_s = str(ap).strip()\n"
    "                    if ap_s:\n"
    "                        result.append((ten_xa, ap_s))"
)

if old in src:
    src2 = src.replace(old, new)
    open('data/khtd.py', 'w', encoding='utf-8').write(src2)
    print('PATCHED OK')
else:
    print('NOT FOUND — checking context:')
    idx = src.find('for dgd_name, ap_list in dgd_block.items()')
    print(repr(src[max(0, idx-5):idx+200]))
