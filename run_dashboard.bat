@echo off
chcp 65001 > nul
title KOREC 모니터링 대시보드
echo ============================================
echo   KOREC 공지사항 모니터링 대시보드
echo   브라우저에서 http://localhost:5000 접속
echo ============================================
cd /d "%~dp0"
start cmd /c "py dashboard_app.py"
timeout /t 2 /nobreak > nul
start http://localhost:5000
pause
