# Hướng dẫn setup máy mới

## 1. Copy file này vào global Claude Code

Chạy lệnh sau (PowerShell) hoặc copy tay:

```powershell
Copy-Item "_setup\global-claude.md" "$env:USERPROFILE\.claude\CLAUDE.md"
```

## 2. Nội dung file (tham khảo)

```
# Global Instructions — áp dụng cho MỌI project, MỌI tài khoản

## Hiện model ở đầu mỗi task (BẮT BUỘC)

Mỗi khi bắt đầu làm task thực sự (đọc file, sửa code, review, tìm kiếm...),
PHẢI hiện dòng đầu tiên theo format:

🤖 Model: [tên model]  |  [lý do 1 câu ngắn]

Ví dụ:
🤖 Model: Sonnet 4.6  |  Review + fix bug thường, không chạm auth/db
🤖 Model: Haiku 4.5   |  Chỉ đọc/grep, không sửa code
⚠️ Đề xuất: Opus 4.7  |  Task chạm db.py — restart: claude --model claude-opus-4-7

KHÔNG cần hiện khi: trả lời câu hỏi, giải thích, hỏi lại user.
```

## 3. Kiểm tra

Sau khi copy, restart Claude Code và thử giao task — dòng 🤖 phải xuất hiện đầu response.
