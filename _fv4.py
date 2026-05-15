import sys
sys.stdout.reconfigure(encoding='utf-8')
def fx(p,r):
 with open(p,'r',encoding='utf-8') as f: c=f.read()
 n=0
 for o,e in r:
  if o in c: c=c.replace(o,e);n+=1
 if n:
  with open(p,'w',encoding='utf-8') as f: f.write(c)
 print(f"{p}: {n}")

# tab_khtd_giao_dc.py
fx(r"d:\VBSP-SCM\tabs\tab_khtd_giao_dc.py",[
 ('c1.metric("T\u1ed5ng KH giao TW", f"{tong_giao_tw:,.1f} tr.\u0111")',
  'c1.metric("T\u1ed5ng KH giao TW\\n(tri\u1ec7u \u0111\u1ed3ng)", f"{tong_giao_tw:,.0f}")'),
 ('c2.metric("T\u1ed5ng KH giao \u0110P", f"{tong_giao_dp:,.1f} tr.\u0111")',
  'c2.metric("T\u1ed5ng KH giao \u0110P\\n(tri\u1ec7u \u0111\u1ed3ng)", f"{tong_giao_dp:,.0f}")'),
])

# tab_ban_dai_dien.py
fx(r"d:\VBSP-SCM\tabs\tab_ban_dai_dien.py",[
 ('"D\u01b0 n\u1ee3 (t\u1ef7)"', '"D\u01b0 n\u1ee3 (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('"Trong h\u1ea1n (t\u1ef7)"', '"Trong h\u1ea1n (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('"Qu\u00e1 h\u1ea1n (t\u1ef7)"', '"Qu\u00e1 h\u1ea1n (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('"GN n\u0103m (t\u1ef7)"', '"GN n\u0103m (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('"KH (t\u1ef7)"', '"KH (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('"\u0110\u00e3 GN (t\u1ef7)"', '"\u0110\u00e3 GN (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('"Room c\u00f2n (t\u1ef7)"', '"Room c\u00f2n (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('/ 1e9', '/ 1e6'),
])

# tab_khtd_xuat.py
fx(r"d:\VBSP-SCM\tabs\tab_khtd_xuat.py",[
 ('"KH (t\u1ef7)"', '"KH (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('"TH (t\u1ef7)"', '"TH (tri\u1ec7u \u0111\u1ed3ng)"'),
 ('\u0110\u01a1n v\u1ecb: t\u1ef7 \u0111\u1ed3ng', '\u0110\u01a1n v\u1ecb: tri\u1ec7u \u0111\u1ed3ng'),
])

print("OK")
