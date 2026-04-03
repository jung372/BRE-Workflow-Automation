@echo off
chcp 65001 > nul
echo [%date% %time%] KOREC 모니터링 실행 중...
cd /d "%~dp0"
python korec_monitor.py
echo [%date% %time%] 완료.
