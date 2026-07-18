$action = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument "run_local.py" `
    -WorkingDirectory "d:\05 AI Study\BRE Workflow Automation"

$trigger = New-ScheduledTaskTrigger `
    -Once -At "06:00AM" `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Hours 14)

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable $true

Register-ScheduledTask `
    -TaskName "BRE-Scraper" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Force -RunLevel Highest

Write-Host "BRE-Scraper 작업 등록 완료" -ForegroundColor Green
Write-Host "실행 시간: 매일 KST 06:00 ~ 20:00, 1시간 간격"
Pause
