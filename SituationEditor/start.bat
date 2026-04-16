@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Starting SituationEditor...
timeout /t 1 /nobreak >nul
start "" "http://localhost:8765"
python server.py
pause
