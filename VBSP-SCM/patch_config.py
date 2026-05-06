"""
Chạy script này 1 lần để thêm DCGIAM_SHEET_ID và DCGIAM_CRED_FILE vào config.py
Cách dùng: python patch_config.py
"""
import os

# Đường dẫn config.py — chỉnh nếu cần
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.py")

LINES_TO_ADD = '''
# ── Module Điều chỉnh KHTD ────────────────────────────────────────────────────
DCGIAM_SHEET_ID  = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"
DCGIAM_CRED_FILE = str(BASE_DIR / "credentials.json")
'''

# Kiểm tra đã có chưa
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    content = f.read()

if "DCGIAM_SHEET_ID" in content:
    print("⚠️  DCGIAM_SHEET_ID đã tồn tại trong config.py — không thêm lại.")
else:
    with open(CONFIG_PATH, "a", encoding="utf-8") as f:
        f.write(LINES_TO_ADD)
    print("✅ Đã thêm DCGIAM_SHEET_ID và DCGIAM_CRED_FILE vào config.py")
