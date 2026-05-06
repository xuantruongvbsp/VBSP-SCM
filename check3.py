import re
def slug(s): return re.sub(r'[a-z0-9]+','_',s.lower().strip()).strip('_')
print(slug('PGD Bien Hoa'))
print(slug('Hoi so Chi nhanh tinh'))
