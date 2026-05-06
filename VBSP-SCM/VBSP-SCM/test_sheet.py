from services import khtd_service

data, loi = khtd_service.doc_tu_sheet("hoi_so")
print("So dong doc duoc:", len(data))
print("Loi:", loi[:3] if loi else "Khong co")
