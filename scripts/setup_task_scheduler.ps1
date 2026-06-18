##############################################################################
# setup_task_scheduler.ps1
# Cài đặt Windows Task Scheduler cho VBSP-SCM
# Chạy bằng PowerShell quyền Administrator:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\scripts\setup_task_scheduler.ps1
##############################################################################

param(
    [string]$PythonPath = "",         # Để trống = tự tìm python.exe
    [string]$ProjectDir = "D:\VBSP-SCM"
)

$ErrorActionPreference = "Stop"

# ── Tìm Python ──────────────────────────────────────────────────────────────

if (-not $PythonPath) {
    $candidates = @(
        "C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c -ErrorAction SilentlyContinue) {
            $PythonPath = $c
            break
        }
        try {
            $found = (Get-Command $c -ErrorAction Stop).Source
            $PythonPath = $found
            break
        } catch {}
    }
}

if (-not $PythonPath) {
    Write-Error "Không tìm thấy python.exe. Truyền tham số -PythonPath 'C:\path\to\python.exe'"
    exit 1
}

Write-Host "Python   : $PythonPath"
Write-Host "Project  : $ProjectDir"
Write-Host ""

# ── Helper tạo task ─────────────────────────────────────────────────────────

function New-VbspTask {
    param(
        [string]$TaskName,
        [string]$ScriptFile,
        [string]$Trigger,       # "07:30" = daily; "07:30,14:00" = 2 lần/ngày
        [string]$Description
    )

    $action = New-ScheduledTaskAction `
        -Execute $PythonPath `
        -Argument "$ProjectDir\scripts\$ScriptFile" `
        -WorkingDirectory $ProjectDir

    $triggers = @()
    foreach ($t in $Trigger.Split(",")) {
        $h, $m = $t.Trim().Split(":")
        $triggers += New-ScheduledTaskTrigger `
            -Daily -At "$($h.Trim()):$($m.Trim())"
    }

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit "00:10:00" `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable

    # Chạy với tài khoản SYSTEM (không cần đăng nhập)
    $principal = New-ScheduledTaskPrincipal `
        -UserId "SYSTEM" `
        -LogonType ServiceAccount `
        -RunLevel Highest

    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "  Đã xóa task cũ: $TaskName"
    }

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $triggers `
        -Settings $settings `
        -Principal $principal `
        -Description $Description | Out-Null

    Write-Host "  [OK] $TaskName  ->  $ScriptFile  @  $Trigger"
}

# ── Tạo các task ────────────────────────────────────────────────────────────

Write-Host "=== Cài đặt Task Scheduler VBSP-SCM ===" -ForegroundColor Cyan
Write-Host ""

# 1. Báo cáo Excel + Telegram sáng (07:30)
New-VbspTask `
    -TaskName "VBSP-DailyReport" `
    -ScriptFile "daily_report.py" `
    -Trigger "07:30" `
    -Description "VBSP-SCM: Tạo báo cáo Excel hằng ngày + gửi tóm tắt qua Telegram"

# 2. Nhắc deadline + phát hiện submission mới (08:00 và 14:00)
New-VbspTask `
    -TaskName "VBSP-NhacDeadline" `
    -ScriptFile "nhac_deadline.py" `
    -Trigger "08:00,14:00" `
    -Description "VBSP-SCM: Nhắc PGD chưa nộp BC + phát hiện nộp mới từ GSheet"

# 3. Telegram 2 chiều — polling lệnh từ user (mỗi phút)
# Task Scheduler không hỗ trợ interval < 1 phút qua trigger Daily,
# nên dùng trigger RepetitionInterval 1 phút.
$pollingAction = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "$ProjectDir\scripts\telegram_polling.py" `
    -WorkingDirectory $ProjectDir

$pollingTrigger = New-ScheduledTaskTrigger -Daily -At "00:00"
$pollingTrigger.Repetition = New-ScheduledTaskRepetitionPattern `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Hours 24)

$pollingSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit "00:00:30" `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

$pollingPrincipal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName "VBSP-TelegramPolling" -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName "VBSP-TelegramPolling" -Confirm:$false
    Write-Host "  Đã xóa task cũ: VBSP-TelegramPolling"
}
Register-ScheduledTask `
    -TaskName "VBSP-TelegramPolling" `
    -Action $pollingAction `
    -Trigger $pollingTrigger `
    -Settings $pollingSettings `
    -Principal $pollingPrincipal `
    -Description "VBSP-SCM: Telegram bot 2 chiều — poll lệnh mỗi phút" | Out-Null
Write-Host "  [OK] VBSP-TelegramPolling  ->  telegram_polling.py  @  mỗi 1 phút"

Write-Host ""
Write-Host "=== Hoàn tất ===" -ForegroundColor Green
Write-Host ""

# ── Xác nhận ────────────────────────────────────────────────────────────────

Write-Host "Danh sách task VBSP-SCM đã đăng ký:" -ForegroundColor Yellow
Get-ScheduledTask | Where-Object { $_.TaskName -like "VBSP-*" } | `
    Select-Object TaskName, State | Format-Table -AutoSize

Write-Host "Chạy thủ công để test:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName 'VBSP-DailyReport'"
Write-Host "  Start-ScheduledTask -TaskName 'VBSP-NhacDeadline'"
Write-Host "  Start-ScheduledTask -TaskName 'VBSP-TelegramPolling'"
