with open('config.py', 'r', encoding='utf-8') as f:
    content = f.read()

OLD = '1GxLC1sl0oD3xH7MHY9_9wSJ8WdaaykXS'
NEW = '15Ev2rTv6khLFaMpAiMwqJCVC_33ocJ-6cp016RGNkYk'

if OLD in content:
    content = content.replace(OLD, NEW)
    with open('config.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK - Da cap nhat SHEET_ID moi")
else:
    print("Khong tim thay ID cu - kiem tra lai config.py")
