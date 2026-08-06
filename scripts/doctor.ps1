[CmdletBinding()]
param(
    [string]$InstallRoot = 'D:\05 AI Study\BRE Workflow Automation',
    [string]$RuntimeRoot = 'D:\05 AI Study\BRE_Workflow_runtime',
    [string]$TaskName = 'BRE Scraper',
    [string]$RunnerTaskName = 'BRE Workflow Runner',
    [string]$DashboardUrl = 'https://jung372.github.io/BRE-Workflow-Automation2/data/status.json',
    [int]$StaleHours = 3
)

$ErrorActionPreference = 'Continue'
$results = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $results.Add([pscustomobject]@{
        Check = $Name
        Status = if ($Passed) { 'PASS' } else { 'FAIL' }
        Detail = $Detail
    })
}

function Add-Warn {
    param([string]$Name, [string]$Detail)
    $results.Add([pscustomobject]@{ Check = $Name; Status = 'WARN'; Detail = $Detail })
}

$envPath = Join-Path $RuntimeRoot '.env'
$publishPath = Join-Path $RuntimeRoot 'publish'
$pointerPath = Join-Path $InstallRoot 'current_release.txt'
$deploymentPath = Join-Path $RuntimeRoot 'deployment.json'
$statePath = Join-Path $publishPath 'last_state.json'
$statusPath = Join-Path $publishPath 'data\status.json'

# --- 도구 ----------------------------------------------------------------
$python = Get-Command python -ErrorAction SilentlyContinue
$git = Get-Command git -ErrorAction SilentlyContinue
$gh = Get-Command gh -ErrorAction SilentlyContinue

Add-Check 'Python' ($null -ne $python) $(if ($python) { $python.Source } else { '설치 필요' })
Add-Check 'Git' ($null -ne $git) $(if ($git) { $git.Source } else { '설치 필요' })
Add-Check 'GitHub CLI' ($null -ne $gh) $(if ($gh) { $gh.Source } else { '러너 등록에 필요' })

# --- 환경파일 ------------------------------------------------------------
Add-Check '서버 .env' (Test-Path -LiteralPath $envPath) $envPath
if (Test-Path -LiteralPath $envPath) {
    $envLines = Get-Content -LiteralPath $envPath -Encoding UTF8
    $requiredKeys = @(
        'METMAST_SIRU_ID', 'METMAST_SIRU_PW',
        'METMAST_GOGK_ID', 'METMAST_GOGK_PW',
        'METMAST_DKAM_ID', 'METMAST_DKAM_PW'
    )
    $empty = @()
    foreach ($key in $requiredKeys) {
        $line = $envLines | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
        if (-not $line -or -not ($line -split '=', 2)[1].Trim()) {
            $empty += $key
        }
    }
    Add-Check '.env 필수 값' ($empty.Count -eq 0) `
        $(if ($empty.Count) { "비어 있음: $($empty -join ', ')" } else { '모두 입력됨' })

    # 값이 비면 계측기가 조용히 Offline 으로 보고되어 Teams 오탐이 발생한다.
    $blmuUrl = $envLines | Where-Object { $_ -match '^\s*METMAST_BLMU_URL\s*=' } | Select-Object -First 1
    if (-not $blmuUrl -or -not ($blmuUrl -split '=', 2)[1].Trim()) {
        Add-Warn 'BLMU URL' 'URL 미설정 - BLMU 는 항상 Offline 으로 보고됩니다'
    }
}

# --- 배포 상태 -----------------------------------------------------------
Add-Check '릴리스 포인터' (Test-Path -LiteralPath $pointerPath) $pointerPath
if (Test-Path -LiteralPath $pointerPath) {
    $releasePath = (Get-Content -LiteralPath $pointerPath -Raw).Trim()
    $venvPython = Join-Path $releasePath '.venv\Scripts\python.exe'
    Add-Check '현재 릴리스' (Test-Path -LiteralPath $releasePath) $releasePath
    Add-Check '릴리스 가상환경' (Test-Path -LiteralPath $venvPython) $venvPython

    # 릴리스에 데이터 사본이 남아 있으면 어느 쪽을 읽는지 혼란이 생긴다.
    $strayState = Join-Path $releasePath 'last_state.json'
    Add-Check '릴리스 데이터 미포함' (-not (Test-Path -LiteralPath $strayState)) `
        $(if (Test-Path -LiteralPath $strayState) { "제거 필요: $strayState" } else { '깨끗함' })
}

if (Test-Path -LiteralPath $deploymentPath) {
    try {
        $deployment = Get-Content -LiteralPath $deploymentPath -Raw | ConvertFrom-Json
        Add-Check '배포 메타' $true "commit=$($deployment.commit_sha) at=$($deployment.deployed_at)"
    }
    catch {
        Add-Check '배포 메타' $false $_.Exception.Message
    }
}
else {
    Add-Check '배포 메타' $false $deploymentPath
}

# --- 발행 clone ----------------------------------------------------------
$publishIsRepo = Test-Path -LiteralPath (Join-Path $publishPath '.git')
Add-Check '발행 clone' $publishIsRepo $publishPath
if ($publishIsRepo -and $git) {
    $remoteHead = & $git.Source -C $publishPath ls-remote --heads origin main
    Add-Check '원격 도달성' ($LASTEXITCODE -eq 0 -and $remoteHead) `
        $(if ($LASTEXITCODE -eq 0) { 'origin/main 조회 성공' } else { '원격 접근 실패 - 자격증명 확인' })

    $unpushed = & $git.Source -C $publishPath log --oneline '@{u}..HEAD' 2>$null
    $unpushedCount = @($unpushed | Where-Object { $_ }).Count
    Add-Check '미푸시 commit' ($unpushedCount -eq 0) `
        $(if ($unpushedCount) { "$unpushedCount 건 미푸시 - push 실패 이력 확인" } else { '없음' })

    $dirty = & $git.Source -C $publishPath status --porcelain
    $dirtyOther = @($dirty | Where-Object {
        $_ -and $_ -notmatch 'last_state\.json$' -and $_ -notmatch 'status\.json$'
    })
    Add-Check '발행 clone 청결' ($dirtyOther.Count -eq 0) `
        $(if ($dirtyOther.Count) { "예상 외 변경: $($dirtyOther -join '; ')" } else { '데이터 파일 외 변경 없음' })
}

# --- 데이터 신선도 -------------------------------------------------------
foreach ($pair in @(
    @{ Name = 'last_state.json 신선도'; Path = $statePath },
    @{ Name = 'status.json 신선도'; Path = $statusPath }
)) {
    if (Test-Path -LiteralPath $pair.Path) {
        $age = (Get-Date) - (Get-Item -LiteralPath $pair.Path).LastWriteTime
        $fresh = $age.TotalHours -lt $StaleHours
        Add-Check $pair.Name $fresh ("{0:N1} 시간 전 갱신 (기준 {1}h)" -f $age.TotalHours, $StaleHours)
    }
    else {
        Add-Check $pair.Name $false $pair.Path
    }
}

# --- 예약 작업 -----------------------------------------------------------
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Add-Check '스크래퍼 작업' ($null -ne $task) $(if ($task) { $task.State } else { $TaskName })
if ($task) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($info) {
        # 종료코드 3 은 '배포 중이라 건너뜀'이므로 정상으로 취급한다.
        $ok = $info.LastTaskResult -in @(0, 3, 267009)
        Add-Check '스크래퍼 마지막 결과' $ok `
            "LastTaskResult=$($info.LastTaskResult) LastRunTime=$($info.LastRunTime)"
    }
}

$runnerTask = Get-ScheduledTask -TaskName $RunnerTaskName -ErrorAction SilentlyContinue
Add-Check '러너 작업' `
    ($null -ne $runnerTask -and $runnerTask.State -eq 'Running') `
    $(if ($runnerTask) { $runnerTask.State } else { $RunnerTaskName })

# --- 락 ------------------------------------------------------------------
foreach ($lock in @('run.lock', 'deploy.lock')) {
    $lockPath = Join-Path $RuntimeRoot $lock
    if (Test-Path -LiteralPath $lockPath) {
        $age = (Get-Date) - (Get-Item -LiteralPath $lockPath).LastWriteTime
        if ($age.TotalMinutes -gt 30) {
            Add-Check "$lock (고착)" $false ("{0:N0} 분째 존재 - 수동 삭제 필요" -f $age.TotalMinutes)
        }
        else {
            Add-Warn $lock ("{0:N0} 분 전 생성 - 작업 진행 중" -f $age.TotalMinutes)
        }
    }
}

# --- 공개 대시보드 -------------------------------------------------------
try {
    $published = Invoke-RestMethod -Uri $DashboardUrl -TimeoutSec 10
    Add-Check '공개 대시보드' ($null -ne $published.checked_at) "checked_at=$($published.checked_at)"
}
catch {
    Add-Check '공개 대시보드' $false $_.Exception.Message
}

$results | Format-Table -AutoSize
if ($results.Status -contains 'FAIL') {
    exit 1
}
exit 0
