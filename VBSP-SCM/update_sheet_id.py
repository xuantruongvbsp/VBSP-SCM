import re

with open('config.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r'DCGIAM_SHEET_ID\s*=\s*".*?"',
    'DCGIAM_SHEET_ID  = "15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk"',
    content
)

with open('config.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Đã cập nhật DCGIAM_SHEET_ID mới vào config.py")
