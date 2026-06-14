"""Chạy file này để test Telegram: python test_telegram.py"""
from services.telegram_service import gui_tin

ok = gui_tin("✅ VBSP-SCM đã kết nối Telegram thành công!")
print("Gửi thành công!" if ok else "Gửi thất bại — kiểm tra kết nối mạng")
input("Nhấn Enter để thoát...")
