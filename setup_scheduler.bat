@echo off
chcp 65001 > nul
setlocal

:: 현재 스크립트 위치를 작업 디렉터리로 사용
set SCRIPT_DIR=%~dp0
set PYTHON=python

:: 기존 작업이 있으면 삭제 후 재등록
schtasks /delete /tn "BRE-Scraper" /f 2>nul

:: BRE-Scraper: KST 06:00 시작, 1시간 간격, 14시간 동안 반복 (→ 20:00 마지막 실행)
schtasks /create ^
  /tn "BRE-Scraper" ^
  /tr "cmd /c \"cd /d \"%SCRIPT_DIR%\" && %PYTHON% run_local.py\"" ^
  /sc DAILY ^
  /st 06:00 ^
  /ri 60 ^
  /du 0014:00 ^
  /f

if %errorlevel% equ 0 (
    echo [완료] BRE-Scraper 작업이 등록되었습니다.
    echo  - 실행 시간: 매일 KST 06:00 ~ 20:00, 1시간 간격
    echo  - 작업 디렉터리: %SCRIPT_DIR%
) else (
    echo [오류] 작업 등록 실패. 관리자 권한으로 실행하세요.
)

echo.
echo [현재 등록된 BRE 작업 목록]
schtasks /query /tn "BRE-Scraper" /fo LIST 2>nul

pause
