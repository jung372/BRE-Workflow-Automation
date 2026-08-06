[CmdletBinding()]
param(
    [string]$InstallRoot = 'D:\05 AI Study\BRE Workflow Automation',
    [string]$RuntimeRoot = 'D:\05 AI Study\BRE_Workflow_runtime',
    [switch]$NoPush
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$pointerPath = Join-Path $InstallRoot 'current_release.txt'
if (-not (Test-Path -LiteralPath $pointerPath)) {
    throw "현재 릴리스 포인터가 없습니다: $pointerPath"
}

$releasePath = (Get-Content -LiteralPath $pointerPath -Raw).Trim()
if (-not $releasePath) {
    throw "현재 릴리스 포인터가 비어 있습니다: $pointerPath"
}

$resolvedInstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$resolvedReleasePath = [System.IO.Path]::GetFullPath($releasePath)
if (-not $resolvedReleasePath.StartsWith(
    $resolvedInstallRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "릴리스 경로가 설치 루트 밖입니다: $resolvedReleasePath"
}

$resolvedRuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$pythonPath = Join-Path $resolvedReleasePath '.venv\Scripts\python.exe'
$appPath = Join-Path $resolvedReleasePath 'run_local.py'
$envPath = Join-Path $resolvedRuntimeRoot '.env'
$dataPath = Join-Path $resolvedRuntimeRoot 'publish'

foreach ($required in @($pythonPath, $appPath, $envPath, $dataPath)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "필요한 경로가 없습니다: $required"
    }
}

# 코드는 릴리스 폴더, 데이터는 publish clone, 로그·락은 RuntimeRoot 로 갈라진다.
$env:BRE_NODE_ROLE = 'server'
$env:BRE_DATA_DIR = $dataPath
$env:BRE_RUNTIME_DIR = $resolvedRuntimeRoot
$env:BRE_ENV_FILE = $envPath

$arguments = @($appPath)
if ($NoPush) {
    $arguments += '--no-push'
}

Set-Location -LiteralPath $resolvedReleasePath
& $pythonPath @arguments
exit $LASTEXITCODE
