[CmdletBinding()]
param(
    [string]$SourcePath = '',
    [string]$InstallRoot = 'D:\05 AI Study\BRE Workflow Automation',
    [string]$RuntimeRoot = 'D:\05 AI Study\BRE_Workflow_runtime',
    [string]$RepositoryUrl = 'https://github.com/jung372/BRE-Workflow-Automation2.git',
    [string]$TaskName = 'BRE Scraper',
    [string]$StartTime = '06:00',
    [int]$RepeatHours = 14
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# 자격증명이 비어 있으면 계측기가 조용히 Offline 으로 보고되어
# Teams 알림이 매일 오탐을 낸다. 그래서 세팅 단계에서 막는다.
$RequiredEnvKeys = @(
    'METMAST_SIRU_ID', 'METMAST_SIRU_PW',
    'METMAST_GOGK_ID', 'METMAST_GOGK_PW',
    'METMAST_DKAM_ID', 'METMAST_DKAM_PW'
)

if ([string]::IsNullOrWhiteSpace($SourcePath)) {
    $scriptFilePath = $PSCommandPath
    if ([string]::IsNullOrWhiteSpace($scriptFilePath)) {
        $scriptFilePath = $MyInvocation.MyCommand.Path
    }
    if ([string]::IsNullOrWhiteSpace($scriptFilePath)) {
        throw '설치 스크립트 경로를 확인할 수 없습니다.'
    }
    $SourcePath = Split-Path -Parent (Split-Path -Parent $scriptFilePath)
}

$resolvedSource = (Resolve-Path -LiteralPath $SourcePath).Path
$resolvedInstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$resolvedRuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$envPath = Join-Path $resolvedRuntimeRoot '.env'
$publishPath = Join-Path $resolvedRuntimeRoot 'publish'

Write-Host "[SETUP] 소스: $resolvedSource"
Write-Host "[SETUP] 설치 루트: $resolvedInstallRoot"
Write-Host "[SETUP] 런타임 루트: $resolvedRuntimeRoot"

New-Item -ItemType Directory -Force -Path `
    $resolvedInstallRoot, $resolvedRuntimeRoot, (Join-Path $resolvedRuntimeRoot 'logs') |
    Out-Null

# --- 1. 환경파일 ---------------------------------------------------------
if (-not (Test-Path -LiteralPath $envPath)) {
    $legacyEnv = Join-Path $resolvedSource '.env'
    $exampleEnv = Join-Path $resolvedSource '.env.example'
    if (Test-Path -LiteralPath $legacyEnv) {
        Copy-Item -LiteralPath $legacyEnv -Destination $envPath
        Write-Host "[SETUP] 기존 .env 를 런타임으로 복사했습니다: $envPath"
    }
    else {
        Copy-Item -LiteralPath $exampleEnv -Destination $envPath
        Write-Warning "환경파일 템플릿을 만들었습니다. 실제 값을 입력한 뒤 이 스크립트를 다시 실행하세요: $envPath"
        exit 2
    }
}

$envLines = Get-Content -LiteralPath $envPath -Encoding UTF8
$missing = @()
foreach ($key in $RequiredEnvKeys) {
    $line = $envLines | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if (-not $line -or -not ($line -split '=', 2)[1].Trim()) {
        $missing += $key
    }
}
if ($missing.Count -gt 0) {
    Write-Warning "환경파일에 값이 비어 있습니다: $($missing -join ', ')"
    Write-Warning "실제 값을 입력한 뒤 다시 실행하세요: $envPath"
    exit 2
}
Write-Host '[SETUP] 환경파일 확인 완료'

# --- 2. 발행 전용 clone --------------------------------------------------
if (-not (Test-Path -LiteralPath (Join-Path $publishPath '.git'))) {
    Write-Host "[SETUP] 발행 전용 clone 생성: $publishPath"
    & git clone $RepositoryUrl $publishPath
    if ($LASTEXITCODE -ne 0) {
        throw "publish clone 생성 실패 (exit $LASTEXITCODE)"
    }
}
else {
    Write-Host '[SETUP] 발행 전용 clone 이 이미 존재합니다. 최신화합니다.'
    & git -C $publishPath pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        Write-Warning '[SETUP] publish clone 최신화 실패. 수동으로 확인하세요.'
    }
}

# 서버가 아직 push 하지 않은 상태가 있을 수 있으므로, 기존 파일이 더
# 최신이면 publish clone 쪽으로 옮긴다.
$legacyState = Join-Path $resolvedSource 'last_state.json'
$publishState = Join-Path $publishPath 'last_state.json'
if (Test-Path -LiteralPath $legacyState) {
    $shouldCopy = $true
    if (Test-Path -LiteralPath $publishState) {
        $legacyItem = Get-Item -LiteralPath $legacyState
        $publishItem = Get-Item -LiteralPath $publishState
        $shouldCopy = $legacyItem.LastWriteTimeUtc -gt $publishItem.LastWriteTimeUtc
    }
    if ($shouldCopy) {
        Copy-Item -LiteralPath $legacyState -Destination $publishState -Force
        Write-Host '[SETUP] 기존 last_state.json 을 publish clone 으로 이전했습니다.'
    }
    else {
        Write-Host '[SETUP] publish clone 의 last_state.json 이 더 최신입니다. 유지합니다.'
    }
}

# --- 3. 초기 배포 --------------------------------------------------------
$deployScript = Join-Path $resolvedSource 'scripts\deploy_server.ps1'
Write-Host '[SETUP] 초기 배포 실행 (스모크 생략)'
& $deployScript `
    -SourcePath $resolvedSource `
    -InstallRoot $resolvedInstallRoot `
    -RuntimeRoot $resolvedRuntimeRoot `
    -TaskName $TaskName `
    -CommitSha 'initial' `
    -SkipSmoke

# --- 4. 예약 작업 --------------------------------------------------------
# Teams 발송은 GitHub Actions(report.yml)에 그대로 두므로 작업은 하나만 등록한다.
$launcherPath = Join-Path $resolvedInstallRoot 'launcher\run_scrape.ps1'
if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "런처가 배치되지 않았습니다: $launcherPath"
}

$taskArguments = @(
    '-NoProfile'
    '-ExecutionPolicy Bypass'
    "-File `"$launcherPath`""
    "-InstallRoot `"$resolvedInstallRoot`""
    "-RuntimeRoot `"$resolvedRuntimeRoot`""
) -join ' '

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $taskArguments

# KST 06:00 시작, 1시간 간격, 14시간 동안 반복 (마지막 실행 20:00)
$trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$repetitionSource = New-ScheduledTaskTrigger -Once -At $StartTime `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Hours $RepeatHours)
$trigger.Repetition = $repetitionSource.Repetition

# git push 자격증명(Windows 자격 증명 관리자)을 쓰려면 사용자 세션이 필요하다.
# self-hosted runner 도 같은 제약이므로 두 작업의 조건이 일치한다.
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description 'BRE Workflow 모니터링 스크래핑 (매시 06~20 KST)' `
    -Force |
    Out-Null

Write-Host "[SETUP] 예약 작업 등록 완료: $TaskName"
Write-Host "[SETUP]  - 실행: 매일 KST $StartTime 부터 1시간 간격, $RepeatHours 시간"
Write-Host ''
Write-Host '[SETUP] 서버 초기화 완료.'
Write-Host '[SETUP] 다음 단계:'
Write-Host '[SETUP]   1) .\scripts\setup_github_runner.ps1  (관리자 PowerShell)'
Write-Host '[SETUP]   2) 저장소 변수 SERVER_DEPLOY_ENABLED=true 설정'
Write-Host '[SETUP]   3) .\scripts\doctor.ps1 로 점검'
Write-Host ''
Write-Host '[SETUP] 수동 1회 실행으로 확인:'
Write-Host "[SETUP]   Start-ScheduledTask -TaskName '$TaskName'"
