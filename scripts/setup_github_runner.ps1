[CmdletBinding()]
param(
    [string]$RepositoryUrl = 'https://github.com/jung372/BRE-Workflow-Automation2',
    [string]$RunnerRoot = 'D:\actions-runner-bre-workflow',
    [string]$RunnerName = 'desktop-evu6usl-bre',
    [string]$TaskName = 'BRE Workflow Runner',
    [string]$Labels = 'bre-workflow-server'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# 같은 서버 PC에서 Stock_Report_Codex 러너가 이미 돌고 있다.
# 러너 루트·이름·레이블·작업명을 모두 분리해 충돌을 피한다.

# 이 스크립트에 관리자 권한이 필요한 작업은 없다. 러너 다운로드·등록·예약
# 작업 생성 모두 사용자 권한으로 충분하다. 권한이 없으면 알리기만 하고 진행한다.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principalCheck = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principalCheck.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdministrator) {
    Write-Host '[RUNNER] 관리자 권한 없이 실행합니다. (필요하지 않습니다)'
}

$resolvedRunnerRoot = [System.IO.Path]::GetFullPath($RunnerRoot)
New-Item -ItemType Directory -Force -Path $resolvedRunnerRoot | Out-Null

$configPath = Join-Path $resolvedRunnerRoot 'config.cmd'
$runPath = Join-Path $resolvedRunnerRoot 'run.cmd'
$runnerMarker = Join-Path $resolvedRunnerRoot '.runner'

if (-not (Test-Path -LiteralPath $configPath)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Write-Host '[RUNNER] 최신 GitHub Actions 러너를 조회합니다.'
    $release = Invoke-RestMethod `
        -Uri 'https://api.github.com/repos/actions/runner/releases/latest' `
        -Headers @{ 'User-Agent' = 'BRE-Workflow-Setup' }
    $asset = $release.assets |
        Where-Object { $_.name -match '^actions-runner-win-x64-.*\.zip$' } |
        Select-Object -First 1
    if (-not $asset) {
        throw '최신 릴리스에 Windows x64 러너 아카이브가 없습니다.'
    }

    $archivePath = Join-Path $resolvedRunnerRoot $asset.name
    Write-Host "[RUNNER] 다운로드: $($asset.name)"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archivePath -UseBasicParsing
    Expand-Archive -LiteralPath $archivePath -DestinationPath $resolvedRunnerRoot -Force
    Remove-Item -LiteralPath $archivePath -Force
}

if (-not (Test-Path -LiteralPath $runnerMarker)) {
    $repositoryUri = [Uri]$RepositoryUrl
    $repositoryParts = $repositoryUri.AbsolutePath.Trim('/').Split('/')
    if ($repositoryUri.Host -ne 'github.com' -or $repositoryParts.Count -ne 2) {
        throw "지원하지 않는 GitHub 저장소 URL: $RepositoryUrl"
    }

    $repositoryOwner = $repositoryParts[0]
    $repositoryName = $repositoryParts[1] -replace '\.git$', ''
    $tokenEndpoint = (
        "repos/$repositoryOwner/$repositoryName/" +
        'actions/runners/registration-token'
    )
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $gh) {
        throw (
            'GitHub CLI 를 찾을 수 없습니다. 설치 후 gh auth login 을 먼저 실행하세요. ' +
            '또는 저장소 Settings > Actions > Runners 에서 등록 토큰을 발급받아 ' +
            "직접 실행하세요: cd `"$resolvedRunnerRoot`"; .\config.cmd --url $RepositoryUrl " +
            "--token <TOKEN> --name $RunnerName --labels $Labels --work _work --replace --unattended"
        )
    }

    Write-Host '[RUNNER] 단기 등록 토큰을 발급받습니다.'
    $registrationTokenOutput = & $gh.Source api --method POST $tokenEndpoint --jq '.token'
    if ($LASTEXITCODE -ne 0) {
        throw "러너 토큰 발급 실패 (exit $LASTEXITCODE)."
    }
    $registrationToken = (@($registrationTokenOutput) -join '').Trim()
    if ([string]::IsNullOrWhiteSpace($registrationToken)) {
        throw 'GitHub 가 빈 등록 토큰을 반환했습니다.'
    }

    try {
        Push-Location -LiteralPath $resolvedRunnerRoot
        try {
            & $configPath `
                --unattended `
                --url $RepositoryUrl `
                --token $registrationToken `
                --name $RunnerName `
                --labels $Labels `
                --work '_work' `
                --replace
            if ($LASTEXITCODE -ne 0) {
                throw "러너 설정 실패 (exit $LASTEXITCODE)."
            }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        $registrationToken = $null
        $registrationTokenOutput = $null
    }
}

if (-not (Test-Path -LiteralPath $runPath)) {
    throw "run.cmd 를 찾을 수 없습니다: $runPath"
}

# 러너는 서비스가 아니라 서버 사용자의 로그온 세션에서 실행한다.
# 그래야 예약 작업 제어와 git push 자격증명 접근이 가능하다.
$runnerLoop = @"
while (`$true) {
    & '$runPath'
    Start-Sleep -Seconds 5
}
"@
$encodedRunnerLoop = [Convert]::ToBase64String(
    [Text.Encoding]::Unicode.GetBytes($runnerLoop)
)
$taskArguments = (
    '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden ' +
    "-EncodedCommand $encodedRunnerLoop"
)
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument $taskArguments `
    -WorkingDirectory $resolvedRunnerRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# RunLevel Highest 는 등록 시 관리자 권한을 요구한다. 러너가 실행할 배포
# 스크립트는 사용자 소유 경로만 쓰므로 승격이 필요 없다.
$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650) `
    -MultipleInstances IgnoreNew

# CIM cmdlet 의 실패는 비종료 오류다. -ErrorAction Stop 으로 명시하고
# 사후 검증까지 해야 등록 실패를 성공으로 착각하지 않는다.
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $taskPrincipal `
    -Settings $settings `
    -Description 'GitHub Actions runner for BRE-Workflow-Automation2' `
    -Force `
    -ErrorAction Stop |
    Out-Null

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    throw "러너 예약 작업이 등록되지 않았습니다: $TaskName"
}

Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
Start-Sleep -Seconds 5
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if ($task.State -ne 'Running') {
    throw "러너 작업이 실행 중이 아닙니다. 현재 상태: $($task.State)"
}

Write-Host "[RUNNER] 설정 완료. 작업 상태: $($task.State)"
Write-Host "[RUNNER] 러너 이름: $RunnerName"
Write-Host "[RUNNER] 레이블: self-hosted, windows, x64, $Labels"
Write-Host '[RUNNER] 리스너 자동 재시작 루프: 활성'
Write-Host ''
Write-Host '[RUNNER] 마지막 단계: 저장소 변수 SERVER_DEPLOY_ENABLED=true 를 설정하세요.'
Write-Host '[RUNNER]   gh variable set SERVER_DEPLOY_ENABLED --body true'
